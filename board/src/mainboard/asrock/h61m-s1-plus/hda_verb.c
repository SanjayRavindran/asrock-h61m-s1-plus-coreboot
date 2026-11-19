/* SPDX-License-Identifier: GPL-2.0-only */

#include <stdint.h>
#include <device/azalia_codec/realtek.h>
#include <device/azalia_device.h>

/*
 * HDA verb tables for ASRock H61M-S1 PLUS:
 * - AU1 (Realtek ALC662 rev1): SDATA-IN wired to PCH HDA_SDIN0 (codec address 0)
 *   with rear 3-jack stack AUDIO2, front-panel header HD_AUDIO1 (SENSE_B),
 *   2-pin internal SPDIF_OUT1 header, and PCH SPKR -> PCBEEP input.
 * - Intel CougarPoint HDMI Audio (codec address 3): only DDPB (pin 0x05) is
 *   connected to the rear HDMI1 connector.
 */

static const u32 alc662_verbs[] = {
	AZALIA_SUBVENDOR(0, 0x1849a662),
	/* Rear Green Line-Out (AUDIO2, SENSE_A) */
	AZALIA_PIN_CFG(0, ALC662_FRONT,      0x01014010),
	/* Unused multi-channel outputs */
	AZALIA_PIN_CFG(0, ALC662_SURROUND,   AZALIA_PIN_CFG_NC(0)),
	AZALIA_PIN_CFG(0, ALC662_CENTER_LFE, AZALIA_PIN_CFG_NC(0)),
	/* Rear Pink Mic-In (AUDIO2, SENSE_A) */
	AZALIA_PIN_CFG(0, ALC662_MIC1,       0x01a19030),
	/* Front-panel Pink Mic-In (HD_AUDIO1, SENSE_B) */
	AZALIA_PIN_CFG(0, ALC662_MIC2,       0x02a19040),
	/* Rear Blue Line-In (AUDIO2, SENSE_A) */
	AZALIA_PIN_CFG(0, ALC662_LINE1,      0x0181303f),
	/* Front-panel Green Headphone-Out (HD_AUDIO1, SENSE_B) */
	AZALIA_PIN_CFG(0, ALC662_LINE2,      0x0221401f),
	/* Unused CD-In */
	AZALIA_PIN_CFG(0, ALC662_CD,         AZALIA_PIN_CFG_NC(0)),
	/* PC Beep wired from PCH SPKR */
	AZALIA_PIN_CFG(0, ALC662_PC_BEEP,    0x40a4c601),
	/* Internal 2-pin SPDIF_OUT1 header */
	AZALIA_PIN_CFG(0, ALC662_SPDIF_OUT1, 0x01446120),
};

static const u32 intel_display_audio_verbs[] = {
	AZALIA_SUBVENDOR(3, 0x80860101),
	/* DDPB -> HDMI1 connector */
	AZALIA_PIN_CFG(3, 0x05, 0x18560010),
	/* DDPC / DDPD unconnected */
	AZALIA_PIN_CFG(3, 0x06, AZALIA_PIN_CFG_NC(3)),
	AZALIA_PIN_CFG(3, 0x07, AZALIA_PIN_CFG_NC(3)),
};

const u32 pc_beep_verbs[] = {};

struct azalia_codec mainboard_azalia_codecs[] = {
	{
		.name         = "Realtek ALC662",
		.vendor_id    = 0x10ec0662,
		.subsystem_id = 0x1849a662,
		.address      = 0,
		.verbs        = alc662_verbs,
		.verb_count   = ARRAY_SIZE(alc662_verbs),
	},
	{
		.name         = "Intel Display Audio (HDMI/DP)",
		.vendor_id    = 0x80862805,
		.subsystem_id = 0x80860101,
		.address      = 3,
		.verbs        = intel_display_audio_verbs,
		.verb_count   = ARRAY_SIZE(intel_display_audio_verbs),
	},
};

AZALIA_ARRAY_SIZES;
