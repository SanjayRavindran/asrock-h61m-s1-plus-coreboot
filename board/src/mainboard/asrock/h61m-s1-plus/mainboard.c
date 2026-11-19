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
#include <superio/nuvoton/common/hwm.h>
#include <types.h>

/* HWM base address configured in devicetree.cb */
#define HWM_IOBASE	0x290

/* NCT6776F fan banks: Bank 1 = SYSFAN (CHA_FAN1), Bank 2 = CPUFAN (CPU_FAN1) */
#define BANK_SYSFAN	1
#define BANK_CPUFAN	2

struct smartfan_profile {
	const char *name;
	struct nuvoton_fan_curve fans[2];
};

#define DEFINE_FAN_CURVE(_name, _bank, _t0, _t1, _t2, _t3, _d0, _d1, _d2, _d3, _su, _sd) 	{ 		.name			= (_name), 		.bank			= (_bank), 		.source			= NUVOTON_FAN_SOURCE_PECI0, 		.temp			= { (_t0), (_t1), (_t2), (_t3) }, 		.duty			= { 			NUVOTON_PERCENT_TO_DUTY(_d0), 			NUVOTON_PERCENT_TO_DUTY(_d1), 			NUVOTON_PERCENT_TO_DUTY(_d2), 			NUVOTON_PERCENT_TO_DUTY(_d3), 		}, 		.temp_tolerance		= 2, 		.step_up_time		= 1, 		.step_down_time		= 1, 		.duty_per_step_up	= (_su), 		.duty_per_step_down	= (_sd), 		.crit_temp		= 95, 		.crit_duty_en		= 1, 		.crit_duty		= 255, 		.crit_temp_tolerance	= 2, 	}

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

static void platform_late_init(void *arg)
{
	u8 tjmax = (rdmsr(MSR_TEMPERATURE_TARGET).lo >> 16) & 0xff;
	unsigned int profile = get_uint_option("fan_profile", 0);

	if (!tjmax)
		tjmax = 105;
	if (profile >= ARRAY_SIZE(fan_profiles))
		profile = 0;

	/* Configure thermistor channels wired to MB_TEMP on H61M-S1 PLUS */
	nuvoton_hwm_set_sensor_type(HWM_IOBASE, NUVOTON_TEMP_SRC_SYSTIN,
				    NUVOTON_TEMP_SENSOR_THERMISTOR);
	nuvoton_hwm_set_sensor_type(HWM_IOBASE, NUVOTON_TEMP_SRC_AUXTIN0,
				    NUVOTON_TEMP_SENSOR_THERMISTOR);

	/* Enable PECI Agent 0 (CPU die temperature via NCT6776F pin 115) */
	nuvoton_hwm_enable_peci(HWM_IOBASE, tjmax);

	printk(BIOS_INFO, "HWM: Applying SmartFan IV profile '%s' (TjMax=%u C)\n",
	       fan_profiles[profile].name, tjmax);
	for (size_t i = 0; i < ARRAY_SIZE(fan_profiles[profile].fans); i++)
		nuvoton_hwm_configure_fan(HWM_IOBASE, &fan_profiles[profile].fans[i]);

	/*
	 * Keep CLKOUT_PCI1 (CLK_PCH_PORT80 on LPC/TPM1 pin 1) free-running by
	 * clearing CLKRUN_EN / PSEUDO_CLKRUN_EN set in bd82x6x enable_clock_gating().
	 */
	struct device *lpc = pcidev_on_root(0x1f, 0);
	if (lpc) {
		u16 pmcon1 = pci_read_config16(lpc, GEN_PMCON_1);
		pmcon1 &= ~(3 << 2);
		pci_write_config16(lpc, GEN_PMCON_1, pmcon1);
		printk(BIOS_INFO, "LPC: GEN_PMCON_1=0x%04x RCBA_GCS=0x%08x LPC_EN=0x%04x\n",
		       pci_read_config16(lpc, GEN_PMCON_1),
		       RCBA32(GCS),
		       pci_read_config16(lpc, LPC_EN));
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
