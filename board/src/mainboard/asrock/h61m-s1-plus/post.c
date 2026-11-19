/* SPDX-License-Identifier: GPL-2.0-only */

#include <arch/io.h>
#include <console/console.h>
#include <types.h>

#define LPT1_BASE	0x378
#define LPT_DATA	(LPT1_BASE + 0)
#define LPT_STATUS	(LPT1_BASE + 1)
#define LPT_CONTROL	(LPT1_BASE + 2)

/*
 * Mirror Coreboot 8-bit POST codes onto LPT1 (DB25 pins 2..9, DATA0..DATA7)
 * in addition to LPC port 0x80 and the COM1 log.
 *
 * - The control register is forced to a known idle state first: bit 5 = 0
 *   (data lines are outputs), INIT# (bit 2) high, AUTOFEED/SELECT-IN idle.
 * - The code is then presented on the data lines and STROBE# (pin 1) is
 *   pulsed low->high, so that latch-style LPT POST cards (which sample on
 *   the STROBE# edge) as well as plain LED boards show the same value.
 * - The data lines are left holding the code until the next one.
 */
void mainboard_post(uint8_t value)
{
	outb(0x04, LPT_CONTROL);
	outb(value, LPT_DATA);

	/* STROBE# is hardware-inverted: writing bit 0 = 1 drives pin 1 low. */
	outb(0x05, LPT_CONTROL);
	/* ~3 us of LPC read cycles as pulse width, no timer needed this early */
	inb(LPT_STATUS);
	inb(LPT_STATUS);
	inb(LPT_STATUS);
	outb(0x04, LPT_CONTROL);
}
