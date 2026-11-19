/* SPDX-License-Identifier: GPL-2.0-only */

Method (_PTS, 1)
{
	\_SB.PCI0.LPCB.SIO0.SIOS (Arg0)
}

Method (_WAK, 1)
{
	\_SB.PCI0.LPCB.SIO0.SIOW (Arg0)
	Return (Package() {0, 0})
}
