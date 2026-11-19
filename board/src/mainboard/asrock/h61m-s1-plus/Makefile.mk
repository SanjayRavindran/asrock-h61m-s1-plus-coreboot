## SPDX-License-Identifier: GPL-2.0-only

bootblock-y += early_init.c gpio.c
romstage-y += early_init.c gpio.c
ramstage-y += fb_console.c hda_verb.c mainboard.c
ramstage-$(CONFIG_DRIVERS_OPTION_CFR) += cfr.c
ramstage-$(CONFIG_MAINBOARD_USE_LIBGFXINIT) += gma-mainboard.ads
smm-y += smihandler.c
