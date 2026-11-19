/* SPDX-License-Identifier: GPL-2.0-only */

#include <southbridge/intel/common/gpio.h>

/*
 * PCH GPIO configuration for ASRock H61M-S1 PLUS, verified against:
 * - Vendor PEI GPIO override table (SBPEI.efi)
 * - Live `inteltool -G` observation on H61M-S1+
 * - ASRock H61M-S1 PLUS Rev 1.01 boardview
 */

static const struct pch_gpio_set1 pch_gpio_set1_mode = {
	.gpio0 = GPIO_MODE_GPIO,
	.gpio1 = GPIO_MODE_GPIO,	/* Board pull-up (+3V via R252) */
	.gpio2 = GPIO_MODE_GPIO,	/* PIRQE# -> pull-down/unused */
	.gpio3 = GPIO_MODE_GPIO,	/* PIRQF# */
	.gpio4 = GPIO_MODE_GPIO,	/* PIRQG# */
	.gpio5 = GPIO_MODE_GPIO,	/* PIRQH# */
	.gpio6 = GPIO_MODE_GPIO,	/* FP_PRES# */
	.gpio7 = GPIO_MODE_GPIO,
	.gpio8 = GPIO_MODE_GPIO,
	.gpio9 = GPIO_MODE_NATIVE,	/* OC5# (shared OC0# net) */
	.gpio10 = GPIO_MODE_NATIVE,	/* OC6# (shared OC0# net) */
	.gpio11 = GPIO_MODE_NATIVE,	/* SMBALERT# */
	.gpio12 = GPIO_MODE_NATIVE,	/* LAN_PHY_PWR_CTRL */
	.gpio13 = GPIO_MODE_GPIO,	/* O_PME# (Super I/O PME) */
	.gpio14 = GPIO_MODE_NATIVE,
	.gpio15 = GPIO_MODE_GPIO,
	.gpio16 = GPIO_MODE_GPIO,
	.gpio17 = GPIO_MODE_GPIO,
	.gpio18 = GPIO_MODE_NATIVE,	/* CLKOUT_DP_N */
	.gpio19 = GPIO_MODE_NATIVE,	/* SATA1GP */
	.gpio20 = GPIO_MODE_NATIVE,	/* SMI# / CLKREQ_PCIE */
	.gpio21 = GPIO_MODE_NATIVE,	/* BIOS_WP# / SATA0GP */
	.gpio22 = GPIO_MODE_NATIVE,	/* SCLOCK */
	.gpio23 = GPIO_MODE_NATIVE,	/* LDRQ1# */
	.gpio24 = GPIO_MODE_NATIVE,	/* MEM_LED */
	.gpio25 = GPIO_MODE_NATIVE,
	.gpio26 = GPIO_MODE_NATIVE,
	.gpio27 = GPIO_MODE_GPIO,
	.gpio28 = GPIO_MODE_GPIO,
	.gpio29 = GPIO_MODE_GPIO,
	.gpio30 = GPIO_MODE_NATIVE,	/* SUS_PWR_DN_ACK */
	.gpio31 = GPIO_MODE_GPIO,	/* ACPRESENT */
};

static const struct pch_gpio_set1 pch_gpio_set1_direction = {
	.gpio0 = GPIO_DIR_INPUT,
	.gpio1 = GPIO_DIR_INPUT,
	.gpio2 = GPIO_DIR_OUTPUT,
	.gpio3 = GPIO_DIR_OUTPUT,
	.gpio4 = GPIO_DIR_OUTPUT,
	.gpio5 = GPIO_DIR_OUTPUT,
	.gpio6 = GPIO_DIR_INPUT,
	.gpio7 = GPIO_DIR_INPUT,
	.gpio8 = GPIO_DIR_OUTPUT,
	.gpio9 = GPIO_DIR_INPUT,
	.gpio10 = GPIO_DIR_OUTPUT,
	.gpio11 = GPIO_DIR_INPUT,
	.gpio12 = GPIO_DIR_OUTPUT,
	.gpio13 = GPIO_DIR_INPUT,
	.gpio14 = GPIO_DIR_INPUT,
	.gpio15 = GPIO_DIR_OUTPUT,
	.gpio16 = GPIO_DIR_INPUT,
	.gpio17 = GPIO_DIR_INPUT,
	.gpio18 = GPIO_DIR_INPUT,
	.gpio19 = GPIO_DIR_OUTPUT,
	.gpio20 = GPIO_DIR_INPUT,
	.gpio21 = GPIO_DIR_OUTPUT,
	.gpio22 = GPIO_DIR_OUTPUT,
	.gpio23 = GPIO_DIR_INPUT,
	.gpio24 = GPIO_DIR_OUTPUT,
	.gpio25 = GPIO_DIR_INPUT,
	.gpio26 = GPIO_DIR_INPUT,
	.gpio27 = GPIO_DIR_OUTPUT,
	.gpio28 = GPIO_DIR_INPUT,
	.gpio29 = GPIO_DIR_OUTPUT,
	.gpio30 = GPIO_DIR_INPUT,
	.gpio31 = GPIO_DIR_INPUT,
};

static const struct pch_gpio_set1 pch_gpio_set1_level = {
	.gpio8 = GPIO_LEVEL_HIGH,
	.gpio17 = GPIO_LEVEL_HIGH,
	.gpio18 = GPIO_LEVEL_HIGH,
	.gpio20 = GPIO_LEVEL_HIGH,
	.gpio23 = GPIO_LEVEL_HIGH,
	.gpio25 = GPIO_LEVEL_HIGH,
	.gpio29 = GPIO_LEVEL_HIGH,
};

static const struct pch_gpio_set1 pch_gpio_set1_reset = {
	/* All GPIO0..31 reset on PWROK */
};

static const struct pch_gpio_set1 pch_gpio_set1_invert = {
	.gpio13 = GPIO_INVERT,		/* Active-low O_PME# */
};

static const struct pch_gpio_set1 pch_gpio_set1_blink = {
	.gpio18 = GPIO_BLINK,		/* Chipset default (native mode ignores) */
};

static const struct pch_gpio_set2 pch_gpio_set2_mode = {
	.gpio32 = GPIO_MODE_GPIO,	/* PM_CLKRUN# */
	.gpio33 = GPIO_MODE_GPIO,
	.gpio34 = GPIO_MODE_GPIO,
	.gpio35 = GPIO_MODE_NATIVE,
	.gpio36 = GPIO_MODE_NATIVE,
	.gpio37 = GPIO_MODE_NATIVE,
	.gpio38 = GPIO_MODE_NATIVE,	/* SLOAD */
	.gpio39 = GPIO_MODE_NATIVE,	/* SDATAOUT0 */
	.gpio40 = GPIO_MODE_NATIVE,	/* OC1# (shared OC0# net) */
	.gpio41 = GPIO_MODE_NATIVE,	/* OC2# (shared OC0# net) */
	.gpio42 = GPIO_MODE_NATIVE,	/* OC3# (shared OC0# net) */
	.gpio43 = GPIO_MODE_NATIVE,	/* OC4# (shared OC0# net) */
	.gpio44 = GPIO_MODE_NATIVE,
	.gpio45 = GPIO_MODE_NATIVE,
	.gpio46 = GPIO_MODE_NATIVE,
	.gpio47 = GPIO_MODE_NATIVE,	/* PEG_B_CLKREQ# */
	.gpio48 = GPIO_MODE_NATIVE,	/* SDATAOUT1 */
	.gpio49 = GPIO_MODE_GPIO,	/* TEMP_ALERT# */
	.gpio50 = GPIO_MODE_NATIVE,	/* REQ1# */
	.gpio51 = GPIO_MODE_NATIVE,	/* GNT1# */
	.gpio52 = GPIO_MODE_NATIVE,	/* REQ2# */
	.gpio53 = GPIO_MODE_NATIVE,	/* GNT2# */
	.gpio54 = GPIO_MODE_NATIVE,	/* REQ3# */
	.gpio55 = GPIO_MODE_NATIVE,	/* GNT3# */
	.gpio56 = GPIO_MODE_NATIVE,	/* PEG_A_CLKREQ# */
	.gpio57 = GPIO_MODE_GPIO,
	.gpio58 = GPIO_MODE_NATIVE,	/* SML1CLK */
	.gpio59 = GPIO_MODE_NATIVE,	/* OC0# */
	.gpio60 = GPIO_MODE_NATIVE,	/* SML0ALERT# */
	.gpio61 = GPIO_MODE_NATIVE,	/* SUS_STAT# */
	.gpio62 = GPIO_MODE_NATIVE,	/* SUSCLK */
	.gpio63 = GPIO_MODE_NATIVE,	/* SLP_S5# */
};

static const struct pch_gpio_set2 pch_gpio_set2_direction = {
	.gpio32 = GPIO_DIR_OUTPUT,
	.gpio33 = GPIO_DIR_OUTPUT,
	.gpio34 = GPIO_DIR_INPUT,
	.gpio35 = GPIO_DIR_OUTPUT,
	.gpio36 = GPIO_DIR_OUTPUT,
	.gpio37 = GPIO_DIR_OUTPUT,
	.gpio38 = GPIO_DIR_OUTPUT,
	.gpio39 = GPIO_DIR_OUTPUT,
	.gpio40 = GPIO_DIR_INPUT,
	.gpio41 = GPIO_DIR_INPUT,
	.gpio42 = GPIO_DIR_INPUT,
	.gpio43 = GPIO_DIR_INPUT,
	.gpio44 = GPIO_DIR_INPUT,
	.gpio45 = GPIO_DIR_INPUT,
	.gpio46 = GPIO_DIR_INPUT,
	.gpio47 = GPIO_DIR_INPUT,
	.gpio48 = GPIO_DIR_OUTPUT,
	.gpio49 = GPIO_DIR_INPUT,
	.gpio50 = GPIO_DIR_INPUT,
	.gpio51 = GPIO_DIR_OUTPUT,
	.gpio52 = GPIO_DIR_INPUT,
	.gpio53 = GPIO_DIR_OUTPUT,
	.gpio54 = GPIO_DIR_INPUT,
	.gpio55 = GPIO_DIR_OUTPUT,
	.gpio56 = GPIO_DIR_INPUT,
	.gpio57 = GPIO_DIR_INPUT,
	.gpio58 = GPIO_DIR_INPUT,
	.gpio59 = GPIO_DIR_INPUT,
	.gpio60 = GPIO_DIR_INPUT,
	.gpio61 = GPIO_DIR_OUTPUT,
	.gpio62 = GPIO_DIR_OUTPUT,
	.gpio63 = GPIO_DIR_OUTPUT,
};

static const struct pch_gpio_set2 pch_gpio_set2_level = {
	.gpio32 = GPIO_LEVEL_HIGH,
	.gpio33 = GPIO_LEVEL_HIGH,
	.gpio34 = GPIO_LEVEL_HIGH,
	.gpio49 = GPIO_LEVEL_HIGH,
	.gpio51 = GPIO_LEVEL_HIGH,
	.gpio53 = GPIO_LEVEL_HIGH,
	.gpio55 = GPIO_LEVEL_HIGH,
	.gpio58 = GPIO_LEVEL_HIGH,
	.gpio61 = GPIO_LEVEL_HIGH,
	.gpio63 = GPIO_LEVEL_HIGH,
};

static const struct pch_gpio_set2 pch_gpio_set2_reset = {
	/* All GPIO32..63 reset on PWROK */
};

static const struct pch_gpio_set3 pch_gpio_set3_mode = {
	.gpio64 = GPIO_MODE_NATIVE,	/* CLKOUTFLEX0 */
	.gpio65 = GPIO_MODE_NATIVE,	/* CLKOUTFLEX1 */
	.gpio66 = GPIO_MODE_NATIVE,	/* CLKOUTFLEX2 -> LAN_25M (RTL8111 UG5) */
	.gpio67 = GPIO_MODE_NATIVE,	/* CLKOUTFLEX3 -> PCH_CK_48M_SIO (NCT6776F) */
	.gpio68 = GPIO_MODE_GPIO,	/* Board pull-up */
	.gpio69 = GPIO_MODE_GPIO,	/* Board pull-up */
	.gpio70 = GPIO_MODE_NATIVE,	/* PCH_GPIO70 */
	.gpio71 = GPIO_MODE_NATIVE,	/* PCH_GPIO71 */
	.gpio72 = GPIO_MODE_GPIO,	/* BATLOW# */
	.gpio73 = GPIO_MODE_NATIVE,	/* PCIECLKRQ0# */
	.gpio74 = GPIO_MODE_NATIVE,	/* SML1ALERT# */
	.gpio75 = GPIO_MODE_NATIVE,	/* SML1DATA */
};

static const struct pch_gpio_set3 pch_gpio_set3_direction = {
	.gpio64 = GPIO_DIR_OUTPUT,
	.gpio65 = GPIO_DIR_OUTPUT,
	.gpio66 = GPIO_DIR_OUTPUT,
	.gpio67 = GPIO_DIR_OUTPUT,
	.gpio68 = GPIO_DIR_INPUT,
	.gpio69 = GPIO_DIR_INPUT,
	.gpio70 = GPIO_DIR_INPUT,
	.gpio71 = GPIO_DIR_INPUT,
	.gpio72 = GPIO_DIR_INPUT,
	.gpio73 = GPIO_DIR_INPUT,
	.gpio74 = GPIO_DIR_INPUT,
	.gpio75 = GPIO_DIR_INPUT,
};

static const struct pch_gpio_set3 pch_gpio_set3_level = {
	.gpio70 = GPIO_LEVEL_HIGH,
	.gpio71 = GPIO_LEVEL_HIGH,
};

static const struct pch_gpio_set3 pch_gpio_set3_reset = {
	/* All GPIO64..75 reset on PWROK */
};

const struct pch_gpio_map mainboard_gpio_map = {
	.set1 = {
		.mode		= &pch_gpio_set1_mode,
		.direction	= &pch_gpio_set1_direction,
		.level		= &pch_gpio_set1_level,
		.reset		= &pch_gpio_set1_reset,
		.invert		= &pch_gpio_set1_invert,
		.blink		= &pch_gpio_set1_blink,
	},
	.set2 = {
		.mode		= &pch_gpio_set2_mode,
		.direction	= &pch_gpio_set2_direction,
		.level		= &pch_gpio_set2_level,
		.reset		= &pch_gpio_set2_reset,
	},
	.set3 = {
		.mode		= &pch_gpio_set3_mode,
		.direction	= &pch_gpio_set3_direction,
		.level		= &pch_gpio_set3_level,
		.reset		= &pch_gpio_set3_reset,
	},
};
