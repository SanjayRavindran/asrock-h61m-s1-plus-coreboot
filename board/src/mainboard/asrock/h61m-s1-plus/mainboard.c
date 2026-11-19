/* SPDX-License-Identifier: GPL-2.0-only */

#include <bootstate.h>
#include <cpu/x86/msr.h>
#include <cpu/intel/model_206ax/model_206ax.h>
#include <device/device.h>
#include <drivers/intel/gma/int15.h>
#include <superio/nuvoton/common/hwm.h>

/* HWM base address configured in devicetree.cb */
#define HWM_IOBASE	0x290

/* NCT6776F fan banks: Bank 1 = SYSFAN (CHA_FAN1), Bank 2 = CPUFAN (CPU_FAN1) */
#define BANK_SYSFAN	1
#define BANK_CPUFAN	2

static const struct nuvoton_fan_curve fans[] = {
	{
		.name			= "SYSFAN",
		.bank			= BANK_SYSFAN,
		.source			= NUVOTON_FAN_SOURCE_PECI0,
		.temp			= { 40, 55, 70, 85 },
		.duty			= {
			NUVOTON_PERCENT_TO_DUTY(35),
			NUVOTON_PERCENT_TO_DUTY(50),
			NUVOTON_PERCENT_TO_DUTY(75),
			NUVOTON_PERCENT_TO_DUTY(100),
		},
		.temp_tolerance		= 2,
		.step_up_time		= 1,
		.step_down_time		= 1,
		.duty_per_step_up	= 4,
		.duty_per_step_down	= 2,
		.crit_temp		= 95,
		.crit_duty_en		= 1,
		.crit_duty		= 255,
		.crit_temp_tolerance	= 2,
	},
	{
		.name			= "CPUFAN",
		.bank			= BANK_CPUFAN,
		.source			= NUVOTON_FAN_SOURCE_PECI0,
		.temp			= { 40, 55, 70, 85 },
		.duty			= {
			NUVOTON_PERCENT_TO_DUTY(30),
			NUVOTON_PERCENT_TO_DUTY(50),
			NUVOTON_PERCENT_TO_DUTY(80),
			NUVOTON_PERCENT_TO_DUTY(100),
		},
		.temp_tolerance		= 2,
		.step_up_time		= 1,
		.step_down_time		= 1,
		.duty_per_step_up	= 6,
		.duty_per_step_down	= 3,
		.crit_temp		= 95,
		.crit_duty_en		= 1,
		.crit_duty		= 255,
		.crit_temp_tolerance	= 2,
	},
};

static void hwm_init(void *arg)
{
	u8 tjmax = (rdmsr(MSR_TEMPERATURE_TARGET).lo >> 16) & 0xff;

	if (!tjmax)
		tjmax = 105;

	/* Configure thermistor channels wired to MB_TEMP on H61M-S1 PLUS */
	nuvoton_hwm_set_sensor_type(HWM_IOBASE, NUVOTON_TEMP_SRC_SYSTIN,
				    NUVOTON_TEMP_SENSOR_THERMISTOR);
	nuvoton_hwm_set_sensor_type(HWM_IOBASE, NUVOTON_TEMP_SRC_AUXTIN0,
				    NUVOTON_TEMP_SENSOR_THERMISTOR);

	/* Enable PECI Agent 0 (CPU die temperature via NCT6776F pin 115) */
	nuvoton_hwm_enable_peci(HWM_IOBASE, tjmax);

	for (size_t i = 0; i < ARRAY_SIZE(fans); i++)
		nuvoton_hwm_configure_fan(HWM_IOBASE, &fans[i]);
}

BOOT_STATE_INIT_ENTRY(BS_POST_DEVICE, BS_ON_EXIT, hwm_init, NULL);

static void mainboard_enable(struct device *dev)
{
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
