/* SPDX-License-Identifier: GPL-2.0-only */

#include <acpi/acpi.h>
#include <cpu/x86/smm.h>
#include <device/pnp_ops.h>
#include <superio/nuvoton/common/nuvoton.h>
#include <superio/nuvoton/nct6776/nct6776.h>

#define GPIO1_DEV	PNP_DEV(0x2e, NCT6776_WDT1_GPIO01A_V)
#define ACPI_DEV	PNP_DEV(0x2e, NCT6776_ACPI)

void mainboard_smi_sleep(u8 slp_typ)
{
	if (slp_typ < ACPI_S3)
		return;

	nuvoton_pnp_enter_conf_state(GPIO1_DEV);

	if (slp_typ == ACPI_S5) {
		/* Clear S5 keyboard wakeup and log power-off state */
		pnp_set_logical_device(ACPI_DEV);
		pnp_unset_and_set_config(ACPI_DEV, 0xe0, BIT(6), 0);
		pnp_unset_and_set_config(ACPI_DEV, 0xe6, 0, BIT(4));
	}

	pnp_set_logical_device(GPIO1_DEV);
	if (slp_typ == ACPI_S3) {
		/* Blink PLED during S3 suspend (CR 0xf5[7:6] = 10b) */
		pnp_unset_and_set_config(GPIO1_DEV, 0xf5, 0xc0, 0x80);
	} else {
		/* Turn off PLED in S4/S5 by releasing active-low GP10 */
		pnp_unset_and_set_config(GPIO1_DEV, 0xf5, 0xc0, 0x00);
		pnp_unset_and_set_config(GPIO1_DEV, 0xf1, 0x00, 0x01);
	}

	nuvoton_pnp_exit_conf_state(GPIO1_DEV);
}
