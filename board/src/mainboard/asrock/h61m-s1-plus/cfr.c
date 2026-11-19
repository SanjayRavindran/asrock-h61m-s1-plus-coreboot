/* SPDX-License-Identifier: GPL-2.0-only */

#include <boot/coreboot_tables.h>
#include <cpu/intel/model_206ax/cfr.h>
#include <drivers/option/cfr_frontend.h>
#include <northbridge/intel/sandybridge/cfr.h>
#include <southbridge/intel/bd82x6x/cfr.h>

static const struct sm_object dram_max_speed = SM_DECLARE_ENUM({
	.opt_name	= "dram_max_speed",
	.ui_name	= "DRAM Max Frequency",
	.ui_helptext	= "Maximum DDR3 memory clock (Auto uses SPD/JEDEC maximum).",
	.default_value	= 0,
	.values		= (const struct sm_enum_value[]) {
				{ "Auto (SPD/JEDEC)",		0 },
				{ "DDR3-1600 (800 MHz)",	1 },
				{ "DDR3-1333 (666 MHz)",	2 },
				{ "DDR3-1066 (533 MHz)",	3 },
				SM_ENUM_VALUE_END		},
});

static struct sm_obj_form system = {
	.ui_name = "System",
	.obj_list = (const struct sm_object *[]) {
		&gfx_uma_size,
		&dram_max_speed,
		&hyper_threading,
		&sata_mode,
		&nmi,
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
	&power,
	NULL,
};

void mb_cfr_setup_menu(struct lb_cfr *cfr_root)
{
	cfr_write_setup_menu(cfr_root, sm_root);
}
