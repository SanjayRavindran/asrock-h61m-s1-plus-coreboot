/* SPDX-License-Identifier: GPL-2.0-or-later */

#include <bootblock_common.h>
#include <device/pnp_ops.h>
#include <northbridge/intel/sandybridge/sandybridge.h>
#include <superio/nuvoton/common/nuvoton.h>
#include <superio/nuvoton/nct6776/nct6776.h>

#define SIO_BASE	PNP_DEV(0x2e, 0)
#define PP_DEV		PNP_DEV(0x2e, NCT6776_PP)
#define SERIAL_DEV	PNP_DEV(0x2e, NCT6776_SP1)
#define GPIO1_DEV	PNP_DEV(0x2e, NCT6776_WDT1_GPIO01A_V)
#define ACPI_DEV	PNP_DEV(0x2e, NCT6776_ACPI)
#define HWM_DEV		PNP_DEV(0x2e, NCT6776_HWM_FPLED)

/* Enable Parallel Port (LPT1, LDN 0x01) at 0x378 IRQ 5 SPP mode */
static void lpt_setup(void)
{
	pnp_set_logical_device(PP_DEV);
	pnp_write_config(PP_DEV, 0x30, 0x00);
	pnp_write_config(PP_DEV, 0x60, 0x03);
	pnp_write_config(PP_DEV, 0x61, 0x78);
	pnp_write_config(PP_DEV, 0x70, 0x05);
	pnp_write_config(PP_DEV, 0x74, 0x04);	/* no DMA */
	pnp_write_config(PP_DEV, 0xf0, 0x38);
	pnp_write_config(PP_DEV, 0x30, 0x01);
}

static void sio_pinmux_setup(void)
{
	/* Global multi-function and 48 MHz clock strapping */
	pnp_write_config(SIO_BASE, 0x13, 0xff);
	pnp_write_config(SIO_BASE, 0x14, 0xff);
	pnp_write_config(SIO_BASE, 0x1b, 0x68);
	pnp_write_config(SIO_BASE, 0x1c, 0x80);
	pnp_write_config(SIO_BASE, 0x24, 0x5c);
	pnp_write_config(SIO_BASE, 0x27, 0x80);
	pnp_write_config(SIO_BASE, 0x2a, 0x60);
	pnp_write_config(SIO_BASE, 0x2c, 0x80);
	pnp_write_config(SIO_BASE, 0x2f, 0x03);
}

static void sio_pled_steady_on(void)
{
	/* LDN 0x08: Mux GP10 to GRN_LED and ensure WDT1 is disabled */
	pnp_set_logical_device(GPIO1_DEV);
	pnp_write_config(GPIO1_DEV, 0xf0, 0xd8);
	pnp_write_config(GPIO1_DEV, 0xf1, 0x1e);
	pnp_write_config(GPIO1_DEV, 0xf4, 0x01);
	pnp_write_config(GPIO1_DEV, 0xf5, 0x00);

	/* LDN 0x0b: Steady active-low PLED- on GRN_LED (0x07), YLW off */
	pnp_set_logical_device(HWM_DEV);
	pnp_write_config(HWM_DEV, 0xf7, 0x07);
	pnp_write_config(HWM_DEV, 0xf8, 0x00);
}

void bootblock_mainboard_early_init(void)
{
	nuvoton_pnp_enter_conf_state(SIO_BASE);

	sio_pinmux_setup();
	lpt_setup();
	sio_pled_steady_on();

	/* LDN 0x0a: ACPI routing/power-loss defaults */
	pnp_set_logical_device(ACPI_DEV);
	pnp_write_config(ACPI_DEV, 0xe6, 0x4c);
	pnp_write_config(ACPI_DEV, 0xf0, 0x40);

	nuvoton_pnp_exit_conf_state(SIO_BASE);

	/* Keep COM1 active on 0x3f8 */
	nuvoton_enable_serial(SERIAL_DEV, CONFIG_TTYS0_BASE);
}

#if defined(__ROMSTAGE__)
/*
 * Super I/O logical devices are reset by LRESET#/PLTRST# (including after CF9
 * or S3 resume), so keep LPT1 enabled and re-assert pin-muxing and PLED-.
 */
void mainboard_early_init(bool s3resume)
{
	nuvoton_pnp_enter_conf_state(SIO_BASE);
	sio_pinmux_setup();
	lpt_setup();
	sio_pled_steady_on();
	nuvoton_pnp_exit_conf_state(SIO_BASE);
}
#endif
