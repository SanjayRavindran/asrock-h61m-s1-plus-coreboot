## SPDX-License-Identifier: GPL-2.0-only

bootblock-y += early_init.c gpio.c post.c
romstage-y += early_init.c gpio.c post.c
postcar-y += post.c
ramstage-y += hda_verb.c mainboard.c post.c
ramstage-$(CONFIG_DRIVERS_OPTION_CFR) += cfr.c
ramstage-$(CONFIG_MAINBOARD_USE_LIBGFXINIT) += gma-mainboard.ads
smm-y += smihandler.c
