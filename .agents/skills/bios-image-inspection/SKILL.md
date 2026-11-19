---
name: bios-image-inspection
description: >-
  Perform read-only inspection and evidence extraction from stock/vendor AMI Aptio
  BIOS dumps (UEFITool/UEFIExtract and AMI MMTool A4/A5) and follow evidence-gated
  Coreboot porting stages A-E. Use this skill when analyzing vendor firmware
  images, comparing ROM variants, extracting VBT/SMBIOS/ACPI/GPIO clues, or
  onboarding/auditing a Coreboot board port.
---

# Safe BIOS Image Inspection & Evidence-Gated Porting

Follow strict read-only provenance and verification gates before treating any vendor firmware dump or board clue as implementation truth.

## Non-Negotiable Safeguards

1. **Preserve all vendor/stock dumps unchanged**: Work strictly on copies; record byte size and SHA-256 for every image and variant separately. Never treat partial region dumps or update capsules as full-chip backups.
2. **Never use vendor UEFI binaries as Coreboot code**: Extracted PEI/DXE modules, `HDAudioSmi`, DSDT, or VBT tables are hardware-clue evidence only. Use Coreboot's native silicon/board drivers where supported.
3. **MMTool A4/A5 safety (`UBU_v1.79.17\mmtool_a4.exe`, `mmtool_a5.exe`)**: Use read-only inspection/extraction on analysis copies only; note both executables are unsigned (`NotSigned`). Cross-check any extracted module/offset against `UEFITool` / `UEFIExtract` before citing it. Never flash an MMTool-saved file or bypass parser warnings by hex-editing.
4. **Evidence-gated Coreboot porting (Gates A–E)**:
   - **Gate A**: Confirm board PCB rev, flash-chip ID/capacity, verified full-chip backup, and external SPI recovery path.
   - **Gate B**: Identify exact Coreboot upstream silicon support at a pinned commit.
   - **Gate C**: Build an evidence table distinguishing measured board facts (`superiotool`, `inteltool`, boardview) from vendor-BIOS clues.
   - **Gate D**: Implement the smallest native port without guessing GPIO levels or straps.
   - **Gate E**: Verify compiled FMAP/IFD/CBFS regions and run hardware validation under serial logging.

## Detailed Workspace Reference Workflows

Load the specific reference file matching your task:
- Coreboot porting history, vendor BIOS analysis & lessons learned: [`docs/PORTING-AND-LESSONS-LEARNED.md`](../../../docs/PORTING-AND-LESSONS-LEARNED.md)
- Complete software-to-hardware connection map (boardview, GPIOs, Super I/O, VRMs): [`docs/HARDWARE-MAP.md`](../../../docs/HARDWARE-MAP.md)
- Supported LGA1155 CPUs & microcode guide: [`docs/SUPPORTED-CPUS.md`](../../../docs/SUPPORTED-CPUS.md)
- Coreboot software & hardware feature catalog: [`docs/COREBOOT-FEATURES-CATALOG.md`](../../../docs/COREBOOT-FEATURES-CATALOG.md)
- Historical H61M-S1 PLUS evidence dossier & boardview pinouts: [`H61M-S1+/bios_porting_documentation.md`](../../../docs/PORTING-AND-LESSONS-LEARNED.md)
- Current post-hardware bring-up report: [`docs/HARDWARE-REPORT.md`](../../../docs/HARDWARE-REPORT.md) and [`H61M-S1-PLUS-COREBOOT-REPORT.md`](../../../docs/HARDWARE-REPORT.md)
