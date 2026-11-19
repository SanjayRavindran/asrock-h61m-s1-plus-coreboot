/* SPDX-License-Identifier: GPL-2.0-only */

#include <acpi/acpi.h>

DefinitionBlock(
	"dsdt.aml",
	"DSDT",
	ACPI_DSDT_REV_2,
	OEM_ID,
	ACPI_TABLE_CREATOR,
	0x20261115
)
{
	#include <acpi/dsdt_top.asl>
	#include "acpi/platform.asl"
	#include <cpu/intel/common/acpi/cpu.asl>
	#include <southbridge/intel/common/acpi/platform.asl>
	#include <southbridge/intel/bd82x6x/acpi/globalnvs.asl>
	#include <southbridge/intel/common/acpi/sleepstates.asl>

	Device (\_SB.PCI0)
	{
		#include <northbridge/intel/sandybridge/acpi/sandybridge.asl>
		#include <southbridge/intel/bd82x6x/acpi/pch.asl>

		/* Wake-on-LAN / PCIe WAKE# -> GPE0 bit 9 (PCI_EXP), deepest state S4 */
		Scope (PEGP)
		{
			Name (_PRW, Package () { 0x09, 4 })
		}

		Scope (RP01)
		{
			Name (_PRW, Package () { 0x09, 4 })
		}

		Scope (RP04)
		{
			Name (_PRW, Package () { 0x09, 4 })
		}
	}
}
