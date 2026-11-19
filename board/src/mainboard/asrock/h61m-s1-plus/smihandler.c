/* SPDX-License-Identifier: GPL-2.0-only */

#include <acpi/acpi.h>
#include <cpu/x86/smm.h>
#include <device/pnp_ops.h>
#include <superio/nuvoton/common/nuvoton.h>
#include <superio/nuvoton/nct6776/nct6776.h>

#define ACPI_DEV	PNP_DEV(0x2e, NCT6776_ACPI)
#define HWM_DEV		PNP_DEV(0x2e, NCT6776_HWM_FPLED)

void mainboard_smi_sleep(u8 slp_typ)
{
	if (slp_typ < ACPI_S3)
		return;

	nuvoton_pnp_enter_conf_state(HWM_DEV);

	if (slp_typ == ACPI_S5) {
		/* Clear S5 keyboard wakeup and log power-off state */
		pnp_set_logical_device(ACPI_DEV);
		pnp_unset_and_set_config(ACPI_DEV, 0xe0, BIT(6), 0);
		pnp_unset_and_set_config(ACPI_DEV, 0xe6, 0, BIT(4));
	}

	/*
	 * PLED- is muxed onto NCT6776F GRN_LED (LDN 0x08 CR 0xf4 = 0x01) and
	 * controlled by Front Panel Green LED register LDN 0x0b CR 0xf7:
	 * - S3: Manual, GRN_LED_RST#=1 (survives S3), active-low, 0.5 Hz blink (0x44)
	 * - S4/S5: Manual, High-Z off (0x00)
	 */
	pnp_set_logical_device(HWM_DEV);
	if (slp_typ == ACPI_S3)
		pnp_write_config(HWM_DEV, 0xf7, 0x44);
	else
		pnp_write_config(HWM_DEV, 0xf7, 0x00);

	nuvoton_pnp_exit_conf_state(HWM_DEV);
}
