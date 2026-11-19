/* SPDX-License-Identifier: GPL-2.0-only */

#include <boot/coreboot_tables.h>
#include <drivers/option/cfr_frontend.h>
#include <southbridge/intel/common/pmutil.h>

static const struct sm_object gfx_uma_size = SM_DECLARE_ENUM({
	.flags		= CFR_OPTFLAG_RUNTIME,
	.opt_name	= "gfx_uma_size",
	.ui_name	= "IGD UMA Size",
	.ui_helptext	= "Size of memory preallocated for internal graphics.",
	.default_value	= CONFIG_IGD_DEFAULT_UMA_INDEX,
	.values		= (const struct sm_enum_value[]) {
				{ " 32MB", 0 },
				{ " 64MB", 1 },
				{ " 96MB", 2 },
				{ "128MB", 3 },
				SM_ENUM_VALUE_END },
});

static const struct sm_object dram_max_speed = SM_DECLARE_ENUM({
	.flags		= CFR_OPTFLAG_RUNTIME,
	.opt_name	= "dram_max_speed",
	.ui_name	= "DRAM Max Frequency",
	.ui_helptext	= "Maximum DDR3 memory clock (Auto uses SPD/JEDEC maximum).",
	.default_value	= 0,
	.values		= (const struct sm_enum_value[]) {
				{ "Auto (SPD/JEDEC)",		0 },
				{ "DDR3-1600 (800 MHz)",	1 },
				{ "DDR3-1333 (666 MHz)",	2 },
				{ "DDR3-1066 (533 MHz)",	3 },
				SM_ENUM_VALUE_END },
});

static const struct sm_object peg_bifurcation = SM_DECLARE_ENUM({
	.flags		= CFR_OPTFLAG_RUNTIME,
	.opt_name	= "peg_bifurcation",
	.ui_name	= "PCIe x16 Slot Bifurcation",
	.ui_helptext	= "Configure CPU PEG root ports (2x8 / 1x8+2x4 also require Ivy Bridge CPU CFG[6:5] hardware straps).",
	.default_value	= 0,
	.values		= (const struct sm_enum_value[]) {
				{ "1x16 (Default)",			0 },
				{ "2x8 (Req. CFG[5]=0 strap)",		1 },
				{ "1x8+2x4 (Req. CFG[6:5]=00 strap)",	2 },
				SM_ENUM_VALUE_END },
});

static const struct sm_object hyper_threading = SM_DECLARE_BOOL({
	.flags		= CFR_OPTFLAG_RUNTIME,
	.opt_name	= "hyper_threading",
	.ui_name	= "Hyper-Threading",
	.ui_helptext	= "Enable or disable Hyper-Threading",
	.default_value	= true,
});

static const struct sm_object sata_mode = SM_DECLARE_ENUM({
	.flags		= CFR_OPTFLAG_RUNTIME,
	.opt_name	= "sata_mode",
	.ui_name	= "SATA Mode",
	.ui_helptext	= "Specify mode of the SATA controller",
	.default_value	= 0,
	.values		= (const struct sm_enum_value[]) {
				{ "AHCI",		0 },
				{ "IDE (compatible)",	1 },
				{ "IDE (legacy)",	2 },
				SM_ENUM_VALUE_END },
});

static const struct sm_object nmi = SM_DECLARE_ENUM({
	.flags		= CFR_OPTFLAG_RUNTIME,
	.opt_name	= "nmi",
	.ui_name	= "Non-maskable Interrupts",
	.ui_helptext	= "Enable or disable non-maskable interrupts",
	.default_value	= 0,
	.values		= (const struct sm_enum_value[]) {
				{ "Disabled",	0 },
				{ "Enabled",	1 },
				SM_ENUM_VALUE_END },
});

static const struct sm_object fan_profile = SM_DECLARE_ENUM({
	.flags		= CFR_OPTFLAG_RUNTIME,
	.opt_name	= "fan_profile",
	.ui_name	= "SmartFan IV Profile",
	.ui_helptext	= "Fan curve profile for NCT6776F CPU_FAN1 and CHA_FAN1 driven by CPU PECI0 temperature.",
	.default_value	= 0,
	.values		= (const struct sm_enum_value[]) {
				{ "Balanced (Default)",	0 },
				{ "Quiet",		1 },
				{ "Performance",	2 },
				{ "Full Speed",		3 },
				SM_ENUM_VALUE_END },
});

static const struct sm_object fb_debug_pause = SM_DECLARE_ENUM({
	.flags		= CFR_OPTFLAG_RUNTIME,
	.opt_name	= "fb_debug_pause",
	.ui_name	= "Monitor Debug/POST Pause",
	.ui_helptext	= "How long to display Coreboot POST and CBMEM log on HDMI/VGA before launching UEFI.",
	.default_value	= 1,
	.values		= (const struct sm_enum_value[]) {
				{ "0s (Immediate)",	0 },
				{ "3s (Default)",	1 },
				{ "5s",			2 },
				{ "10s",		3 },
				SM_ENUM_VALUE_END },
});

static const struct sm_object power_on_after_fail = SM_DECLARE_ENUM({
	.flags		= CFR_OPTFLAG_RUNTIME,
	.opt_name	= "power_on_after_fail",
	.ui_name	= "Restore AC Power Loss",
	.ui_helptext	= "Specify what to do when power is re-applied after a power loss.",
	.default_value	= CONFIG_MAINBOARD_POWER_FAILURE_STATE,
	.values		= (const struct sm_enum_value[]) {
				{ "Power off (S5)", MAINBOARD_POWER_OFF },
				{ "Power on  (S0)", MAINBOARD_POWER_ON },
				{ "Previous state", MAINBOARD_POWER_KEEP },
				SM_ENUM_VALUE_END },
});

static struct sm_obj_form system = {
	.ui_name = "System",
	.obj_list = (const struct sm_object *[]) {
		&gfx_uma_size,
		&dram_max_speed,
		&peg_bifurcation,
		&hyper_threading,
		&sata_mode,
		&nmi,
		NULL,
	},
};

static struct sm_obj_form cooling_display = {
	.ui_name = "Cooling & Display",
	.obj_list = (const struct sm_object *[]) {
		&fan_profile,
		&fb_debug_pause,
		NULL,
	},
};

static struct sm_obj_form power = {
	.ui_name = "Power",
	.obj_list = (const struct sm_object *[]) {
		&power_on_after_fail,
		NULL,
	},
};

static struct sm_obj_form *sm_root[] = {
	&system,
	&cooling_display,
	&power,
	NULL,
};

void mb_cfr_setup_menu(struct lb_cfr *cfr_root)
{
	cfr_write_setup_menu(cfr_root, sm_root);
}
