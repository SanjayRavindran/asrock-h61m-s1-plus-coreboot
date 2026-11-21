/* SPDX-License-Identifier: GPL-2.0-only */

#include <bootstate.h>
#include <console/console.h>
#include <cpu/x86/msr.h>
#include <cpu/intel/model_206ax/model_206ax.h>
#include <device/device.h>
#include <device/pci_ops.h>
#include <drivers/intel/gma/int15.h>
#include <option.h>
#include <southbridge/intel/bd82x6x/pch.h>
#include <southbridge/intel/common/lpc_def.h>
#include <superio/nuvoton/common/hwm.h>
#include <types.h>

/* HWM base address configured in devicetree.cb */
#define HWM_IOBASE	0x290

/* NCT6776F fan banks: Bank 1 = SYSFAN (CHA_FAN1), Bank 2 = CPUFAN (CPU_FAN1) */
#define BANK_SYSFAN	1
#define BANK_CPUFAN	2
#define BANK_AUXFAN	3

/*
 * Coreboot's shared superio/nuvoton/common/hwm.h defines
 * NUVOTON_FAN_SOURCE_PECI0 as 0x10 (correct for NCT6791D/NCT6796D).
 * On NCT6776F (datasheet rev 1.2 sections 9.52, 9.100, 9.251-9.256),
 * 0x10 is PCH_CPU_TEMP (always 0 C here because U1007 pins 75/76 MSCL/MSDA
 * are unconnected), while PECI Agent 0 is 0x0c and SYSTIN is 0x01.
 */
#define NCT6776_TEMP_SRC_SYSTIN		0x01
#define NCT6776_TEMP_SRC_PECI0		0x0c

struct smartfan_profile {
	const char *name;
	struct nuvoton_fan_curve fans[2];
};

#define DEFINE_FAN_CURVE(_name, _bank, _t0, _t1, _t2, _t3, _d0, _d1, _d2, _d3, _su, _sd) 	{ 		.name			= (_name), 		.bank			= (_bank), 		.source			= NCT6776_TEMP_SRC_PECI0, 		.temp			= { (_t0), (_t1), (_t2), (_t3) }, 		.duty			= { 			NUVOTON_PERCENT_TO_DUTY(_d0), 			NUVOTON_PERCENT_TO_DUTY(_d1), 			NUVOTON_PERCENT_TO_DUTY(_d2), 			NUVOTON_PERCENT_TO_DUTY(_d3), 		}, 		.temp_tolerance		= 2, 		.step_up_time		= 1, 		.step_down_time		= 1, 		.duty_per_step_up	= (_su), 		.duty_per_step_down	= (_sd), 		.crit_temp		= 95, 		.crit_duty_en		= 1, 		.crit_duty		= 255, 		.crit_temp_tolerance	= 2, 	}

static const struct smartfan_profile fan_profiles[] = {
	[0] = {
		.name = "Balanced",
		.fans = {
			DEFINE_FAN_CURVE("SYSFAN", BANK_SYSFAN, 40, 55, 70, 85, 35, 50, 75, 100, 4, 2),
			DEFINE_FAN_CURVE("CPUFAN", BANK_CPUFAN, 40, 55, 70, 85, 30, 50, 80, 100, 6, 3),
		},
	},
	[1] = {
		.name = "Quiet",
		.fans = {
			DEFINE_FAN_CURVE("SYSFAN", BANK_SYSFAN, 45, 62, 76, 88, 25, 38, 62, 100, 3, 2),
			DEFINE_FAN_CURVE("CPUFAN", BANK_CPUFAN, 45, 60, 75, 88, 20, 35, 65, 100, 4, 2),
		},
	},
	[2] = {
		.name = "Performance",
		.fans = {
			DEFINE_FAN_CURVE("SYSFAN", BANK_SYSFAN, 35, 48, 62, 75, 50, 68, 85, 100, 6, 3),
			DEFINE_FAN_CURVE("CPUFAN", BANK_CPUFAN, 35, 48, 62, 75, 45, 65, 88, 100, 8, 4),
		},
	},
	[3] = {
		.name = "Full Speed",
		.fans = {
			DEFINE_FAN_CURVE("SYSFAN", BANK_SYSFAN, 30, 35, 40, 45, 100, 100, 100, 100, 10, 5),
			DEFINE_FAN_CURVE("CPUFAN", BANK_CPUFAN, 30, 35, 40, 45, 100, 100, 100, 100, 10, 5),
		},
	},
};

/* Configure NCT6776F sensor routing, PWM output mode, limits, and latches. */
static void nct6776_hwm_board_init(u8 tjmax)
{
	u8 cr46;

	/* Thermistor mode on MB_TEMP; clear open-diode mode on floating CPUTIN */
	nuvoton_hwm_set_sensor_type(HWM_IOBASE, NUVOTON_TEMP_SRC_SYSTIN,
				    NUVOTON_TEMP_SENSOR_THERMISTOR);
	nuvoton_hwm_set_sensor_type(HWM_IOBASE, NUVOTON_TEMP_SRC_CPUTIN,
				    NUVOTON_TEMP_SENSOR_THERMISTOR);
	nuvoton_hwm_set_sensor_type(HWM_IOBASE, NUVOTON_TEMP_SRC_AUXTIN0,
				    NUVOTON_TEMP_SENSOR_THERMISTOR);

	/* Ensure VBAT monitoring and SYSFANOUT PWM mode are enabled in Bank 0 */
	nuvoton_hwm_select_bank(HWM_IOBASE, 0);
	pnp_write_hwm5_index(HWM_IOBASE, 0x5d,
			     pnp_read_hwm5_index(HWM_IOBASE, 0x5d) | 0x01);
	pnp_write_hwm5_index(HWM_IOBASE, 0x04,
			     pnp_read_hwm5_index(HWM_IOBASE, 0x04) & ~0x01);

	/* Enable PECI Agent 0 (CPU die temp via pin 115) preserving bit 4 */
	nuvoton_hwm_enable_peci(HWM_IOBASE, tjmax);
	nuvoton_hwm_select_bank(HWM_IOBASE, 7);
	pnp_write_hwm5_index(HWM_IOBASE, 0x01, 0x95);

	/* Route SMIOVT1->SYSTIN, SMIOVT2->PECI0; deduplicate remaining channels */
	nuvoton_hwm_select_bank(HWM_IOBASE, 6);
	pnp_write_hwm5_index(HWM_IOBASE, 0x21, NCT6776_TEMP_SRC_SYSTIN);
	pnp_write_hwm5_index(HWM_IOBASE, 0x22, NCT6776_TEMP_SRC_PECI0);
	pnp_write_hwm5_index(HWM_IOBASE, 0x23, NCT6776_TEMP_SRC_SYSTIN);
	pnp_write_hwm5_index(HWM_IOBASE, 0x24, NCT6776_TEMP_SRC_SYSTIN);
	pnp_write_hwm5_index(HWM_IOBASE, 0x25, NCT6776_TEMP_SRC_SYSTIN);
	pnp_write_hwm5_index(HWM_IOBASE, 0x26, NCT6776_TEMP_SRC_SYSTIN);

	nuvoton_hwm_select_bank(HWM_IOBASE, BANK_AUXFAN);
	pnp_write_hwm5_index(HWM_IOBASE, NUVOTON_FAN_SOURCE, NCT6776_TEMP_SRC_SYSTIN);

	/* Program sane voltage and SMIOVT1 temperature thresholds in Bank 0 */
	nuvoton_hwm_select_bank(HWM_IOBASE, 0);
	pnp_write_hwm5_index(HWM_IOBASE, 0x2b, 0xc8); /* in0 Vcore high: 1.600 V */
	pnp_write_hwm5_index(HWM_IOBASE, 0x2c, 0x32); /* in0 Vcore low:  0.400 V */
	pnp_write_hwm5_index(HWM_IOBASE, 0x2d, 0xfc); /* in1 +12V raw hi: 2.016 V */
	pnp_write_hwm5_index(HWM_IOBASE, 0x2e, 0xa0); /* in1 +12V raw lo: 1.280 V */
	pnp_write_hwm5_index(HWM_IOBASE, 0x2f, 0xe8); /* in2 AVCC high:  3.712 V */
	pnp_write_hwm5_index(HWM_IOBASE, 0x30, 0xb8); /* in2 AVCC low:   2.944 V */
	pnp_write_hwm5_index(HWM_IOBASE, 0x31, 0xe8); /* in3 +3.3V high: 3.712 V */
	pnp_write_hwm5_index(HWM_IOBASE, 0x32, 0xb8); /* in3 +3.3V low:  2.944 V */
	pnp_write_hwm5_index(HWM_IOBASE, 0x33, 0xff); /* in4 IMON high: full scale */
	pnp_write_hwm5_index(HWM_IOBASE, 0x34, 0x00); /* in4 IMON low:  full scale */
	pnp_write_hwm5_index(HWM_IOBASE, 0x35, 0xee); /* in5 +5V raw hi: 1.904 V */
	pnp_write_hwm5_index(HWM_IOBASE, 0x36, 0xba); /* in5 +5V raw lo: 1.488 V */
	pnp_write_hwm5_index(HWM_IOBASE, 0x37, 0xff); /* in6 MB_TEMP hi: full scale */
	pnp_write_hwm5_index(HWM_IOBASE, 0x38, 0x00); /* in6 MB_TEMP lo: full scale */
	pnp_write_hwm5_index(HWM_IOBASE, 0x39, 75);   /* SYSTIN max:     75 C */
	pnp_write_hwm5_index(HWM_IOBASE, 0x3a, 70);   /* SYSTIN hyst:    70 C */

	/* SMIOVT2 (PECI0) and SMIOVT3 limits in Bank 1 and Bank 2 */
	nuvoton_hwm_select_bank(HWM_IOBASE, BANK_SYSFAN);
	pnp_write_hwm5_index(HWM_IOBASE, 0x55, 85);
	pnp_write_hwm5_index(HWM_IOBASE, 0x56, 0x00);
	pnp_write_hwm5_index(HWM_IOBASE, 0x53, 80);
	pnp_write_hwm5_index(HWM_IOBASE, 0x54, 0x00);

	nuvoton_hwm_select_bank(HWM_IOBASE, BANK_CPUFAN);
	pnp_write_hwm5_index(HWM_IOBASE, 0x55, 75);
	pnp_write_hwm5_index(HWM_IOBASE, 0x56, 0x00);
	pnp_write_hwm5_index(HWM_IOBASE, 0x53, 70);
	pnp_write_hwm5_index(HWM_IOBASE, 0x54, 0x00);

	/* 3VSB and VBAT thresholds in Bank 5 */
	nuvoton_hwm_select_bank(HWM_IOBASE, 5);
	pnp_write_hwm5_index(HWM_IOBASE, 0x54, 0xe8); /* in7 3VSB high: 3.712 V */
	pnp_write_hwm5_index(HWM_IOBASE, 0x55, 0xb8); /* in7 3VSB low:  2.944 V */
	pnp_write_hwm5_index(HWM_IOBASE, 0x56, 0xe8); /* in8 Vbat high: 3.712 V */
	pnp_write_hwm5_index(HWM_IOBASE, 0x57, 0x96); /* in8 Vbat low:  2.400 V */

	/* Clear stale CASEOPEN0/CASEOPEN1 intrusion latches in Bank 0 CR 46h */
	nuvoton_hwm_select_bank(HWM_IOBASE, 0);
	cr46 = pnp_read_hwm5_index(HWM_IOBASE, 0x46);
	pnp_write_hwm5_index(HWM_IOBASE, 0x46, cr46 | 0xc0);
	pnp_write_hwm5_index(HWM_IOBASE, 0x46, cr46 & ~0xc0);
}

static void platform_late_init(void *arg)
{
	u8 tjmax = (rdmsr(MSR_TEMPERATURE_TARGET).lo >> 16) & 0xff;
	unsigned int profile = get_uint_option("fan_profile", 0);

	if (!tjmax)
		tjmax = 105;
	if (profile >= ARRAY_SIZE(fan_profiles))
		profile = 0;

	nct6776_hwm_board_init(tjmax);

	printk(BIOS_INFO, "HWM: Applying SmartFan IV profile '%s' (TjMax=%u C)\n",
	       fan_profiles[profile].name, tjmax);
	for (size_t i = 0; i < ARRAY_SIZE(fan_profiles[profile].fans); i++)
		nuvoton_hwm_configure_fan(HWM_IOBASE, &fan_profiles[profile].fans[i]);

	nuvoton_hwm_select_bank(HWM_IOBASE, 0);

	/*
	 * Keep CLKOUT_PCI1 (CLK_PCH_PORT80 on LPC/TPM1 pin 1) free-running by
	 * clearing CLKRUN_EN / PSEUDO_CLKRUN_EN set in bd82x6x enable_clock_gating().
	 */
	struct device *lpc = pcidev_on_root(0x1f, 0);
	if (lpc) {
		u16 pmcon1 = pci_read_config16(lpc, GEN_PMCON_1);
		pmcon1 &= ~(3 << 2);
		pci_write_config16(lpc, GEN_PMCON_1, pmcon1);

		/* Enable PCH LPT1 (0x378-0x37f), COM1 (0x3f8-0x3ff), and LPC Port 0x80 */
		u16 lpc_en = pci_read_config16(lpc, LPC_EN);
		lpc_en |= LPT_LPC_EN | COMA_LPC_EN;
		pci_write_config16(lpc, LPC_EN, lpc_en);

		u16 lpc_io_dec = pci_read_config16(lpc, LPC_IO_DEC);
		lpc_io_dec &= ~((0x3 << 8) | (0x7 << 0)); /* LPT=0x378, COMA=0x3f8 */
		pci_write_config16(lpc, LPC_IO_DEC, lpc_io_dec);

		/* Route Port 0x80 POST codes to LPC (GCS.RPR = 0) if GCS is not locked */
		if (!(RCBA32(GCS) & 0x1))
			RCBA32(GCS) &= ~0x04;

		printk(BIOS_INFO,
		       "LPC: GEN_PMCON_1=0x%04x RCBA_GCS=0x%08x LPC_EN=0x%04x LPC_IO_DEC=0x%04x\n",
		       pci_read_config16(lpc, GEN_PMCON_1),
		       RCBA32(GCS),
		       pci_read_config16(lpc, LPC_EN),
		       pci_read_config16(lpc, LPC_IO_DEC));
	}
}

BOOT_STATE_INIT_ENTRY(BS_POST_DEVICE, BS_ON_EXIT, platform_late_init, NULL);

static void mainboard_enable(struct device *dev)
{
	unsigned int peg_mode = get_uint_option("peg_bifurcation", 0);
	struct device *peg11 = pcidev_on_root(1, 1);
	struct device *peg12 = pcidev_on_root(1, 2);

	if (peg_mode < 1 && peg11)
		peg11->enabled = 0;
	if (peg_mode < 2 && peg12)
		peg12->enabled = 0;

	if (CONFIG(INTEL_INT15)) {
		install_intel_vga_int15_handler(GMA_INT15_ACTIVE_LFP_NONE,
						GMA_INT15_PANEL_FIT_DEFAULT,
						GMA_INT15_BOOT_DISPLAY_CRT |
						GMA_INT15_BOOT_DISPLAY_EFP, 0);
	}
}

struct chip_operations mainboard_ops = {
	.enable_dev = mainboard_enable,
};
