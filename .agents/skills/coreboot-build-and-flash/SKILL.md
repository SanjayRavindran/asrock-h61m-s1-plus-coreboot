---
name: coreboot-build-and-flash
description: >-
  Build, assemble, validate, and safely prepare Coreboot + EDK2 UefiPayloadPkg
  firmware images for the ASRock H61M-S1 PLUS on build host 192.168.1.15. Use
  this skill whenever modifying Coreboot board/northbridge/payload configs,
  building 4 MiB or 8 MiB SPI ROMs, inspecting CBFS/FMAP/IFD layouts, syncing
  artifacts to Windows, or planning internal/external SPI flashing.
---

# ASRock H61M-S1 PLUS Coreboot Build & Flash Workflow (`v26.11.4`)

## Environment & Immutable Backups

- **Build Host**: `192.168.1.15` (SSH user `zero`, Ubuntu 26.04)
- **Coreboot Tree**: `/home/zero/coreboot-work/h61m-s1-plus` (branch `h61m-s1-plus-port`, pinned Coreboot commit `df45ea2c49b4c7f6a1d2a969934cf6c6a2cb9018`) + [`patches/0001-sandybridge-h61m-s1-plus-igd-raminit.patch`](../../../patches/0001-sandybridge-h61m-s1-plus-igd-raminit.patch) (bus-0 `< 4 GiB` MMIO clamp, PEG bifurcation/NRI, `me_state` runtime CFR flag)
- **EDK2 Payload**: `https://github.com/mrchromebox/edk2` pinned at `f248a68be339831b69a880d9c932a6a3cf3c461a` (`CONFIG_EDK2_RELEASE=y`, `CONFIG_EDK2_BOOT_MANAGER_ESCAPE=y`, `CONFIG_EDK2_SECURE_BOOT_SUPPORT=y`, `CONFIG_EDK2_CUSTOM_BUILD_PARAMS="-D BOOTSPLASH_IMAGE=FALSE -D NVME_ENABLE=TRUE"`, `5s` boot timeout) + [`patches/0002-edk2-delete-key-usb-boot-menu.patch`](../../../patches/0002-edk2-delete-key-usb-boot-menu.patch) + [`patches/0003-edk2-cf9-reset-and-secureboot-components.patch`](../../../patches/0003-edk2-cf9-reset-and-secureboot-components.patch) (**CRLF line endings — never convert to LF!**)
- **Board Target**: `src/mainboard/asrock/h61m-s1-plus/` (`BOARD_ASROCK_H61M_S1_PLUS`)
- **Two Preserved Immutable OEM BIOS Backups (`chmod 400/444` on `.15` — NEVER modify or run `me_cleaner.py` without copying to `/tmp` + `-O`!)**:
  - **OEM Backup #1 (Physical Full-Chip Read)**: `~/coreboot-work/inputs/h61m-s1-plus-full-chip-read0.bin` on `.15` / [h61m-s1-plus-read0.bin](../../../H61M-S1+/h61m-s1-plus-read0.bin) on Windows (`4,194,304` B, SHA-256 `27cb55b24a644eb664790313631fd9ab681398e4a3ea9ec990d367f5539405bb`)
  - **OEM Backup #2 (Official ASRock AMI P1.10)**: `~/coreboot-work/inputs/H61MS1P1.10` on `.15` / [H61MS1P1.10](../../../H61M-S1+/H61MS1P1.10) on Windows (`4,194,304` B, SHA-256 `e0474ec1054ecbb224211459a1090123aefcecbf582cc2dd00669c661835919c`)
- **Committed Blobs Directory ([`blobs/`](../../../blobs/))** (see [`BLOBS.md`](../../../BLOBS.md) & [`edk2-usb-boot-and-me-variants`](../edk2-usb-boot-and-me-variants/SKILL.md)):
  - `data.vbt` (`3,902` B, `c6500a60...`)
  - `me-stock-8.1.20.1336.bin` (`1,568,768` B, `c9c21e31...`), `me-cleaned-1532k-compat.bin` (`1,568,768` B, `4bfc580c...`), `me-minimal-124k.bin` (`126,976` B = `0x1f000`, `c96a4d75...`)
  - 4 Host-unlocked (`FLMSTR1=0xffff0000`) IFDs: `ifd-4mb-stock-unlocked.bin` (`1f683134...`), `ifd-4mb-minimal-me-unlocked.bin` (`28a71d1d...`), `ifd-8mb-minimal-me-unlocked.bin` (`e7ead7f6...`), `ifd-8mb-mecleaned-compat-unlocked.bin` (`829a0dbc...`)

## Key Board Implementation Rules (`v26.11.3`)

1. **COM1 + LPT1 Enabled + LPC/TPM1 Port `0x80` POST & TPM Probe**:
   - `NCT6776F` global multi-function registers (`0x13..0x2f`, including `0x2a = 0x60`) live on `device pnp 2e.2 on` (`COM1` `0x3f8` IRQ 4).
   - `LPT1` (`device pnp 2e.1 on`: `0x378`, IRQ 5, DRQ 4, `CRf0=0x38` SPP) is **enabled** in `devicetree.cb`, `early_init.c` (`lpt_setup()`), `acpi/superio.asl` (`#define NCT6776_SHOW_PP`), and `mainboard.c` (`LPC_EN |= LPT_LPC_EN | COMA_LPC_EN`, `LPC_IO_DEC` `0x378`/`0x3f8`).
   - Do **not** re-add `post.c` (`0x378` LPT POST writes) so `LPT1` stays clean for parallel peripherals while `CONFIG_DEFAULT_POST_ON_LPC=y` + `RCBA32(GCS) &= ~0x04` (if not `BILD`-locked) + `GEN_PMCON_1=0x0a10` (`CLKRUN` off) send all Coreboot + EDK2 BDS (`0xE1..0xE8`) Port `0x80` POST codes to the 18-pin `LPC/TPM1` header.
   - `MAINBOARD_HAS_TPM1` + `MEMORY_MAPPED_TPM` + `chip drivers/pc80/tpm` (`0c31.0`) probe `0xfed40000` safely (`pc80_tpm_probe: No TPM device found` when empty).
2. **All 10 CFR Options Exposed to Linux (`CFR_OPTFLAG_RUNTIME`)**:
   - Every option in `cfr.c` (plus `me_state` in `src/southbridge/intel/bd82x6x/cfr.c`) sets `.flags = CFR_OPTFLAG_RUNTIME` so `CfrSetupMenuDxe` creates `NV|BS|RT` (`0x00000007`) UEFI variables under `ceae4c1d-335b-4685-a4a0-fc4a94eea085`.

## Build & Multi-Variant Assembly (On `192.168.1.15`)

[`scripts/build_all_roms.sh`](../../../scripts/build_all_roms.sh) builds and validates all **4** `W25Q32` (`4 MiB`) and `W25Q64` (`8 MiB`) ROMs (caching `UEFIPAYLOAD.fd` across variants for speed):

1. **Force a clean EDK2 rebuild when `patches/0002` or `0003` changes**:
   ```bash
   rm -f /home/zero/coreboot-work/h61m-s1-plus/build/UEFIPAYLOAD.fd
   rm -rf /home/zero/coreboot-work/h61m-s1-plus/payloads/external/edk2/workspace/Build
   ```
2. **Build all 4 variants**:
   ```bash
   cd /home/zero/coreboot-work/asrock-h61m-s1-plus-coreboot
   COREBOOT_DIR=/home/zero/coreboot-work/h61m-s1-plus \
   OUT_DIR=/home/zero/coreboot-work/outputs/v26.11.4-build \
   RELEASE_TAG=v26.11.4 \
     bash scripts/build_all_roms.sh
   ```
3. Or build a single custom variant with `DEFCONFIG=... VARIANT_NAME=... IFD_FILE=... ME_FILE=... BIOS_OFFSET=... bash scripts/build.sh`. (`scripts/build.sh` also audits `UEFIPAYLOAD.txt` to confirm `NvmExpressDxe`, `SecureBootConfigDxe`, `EnrollDefaultKeys`, `Pkcs7VerifyDxe`, `RngDxe`, `Hash2DxeCrypto`, `DxeImageVerificationLib`, `SecurityStubDxe`, and `ResetSystemRuntimeDxe`.)

## Structural Validation Checklist

1. Full ROMs = `8,388,608` B (`W25Q64`) or `4,194,304` B (`W25Q32`); BIOS slices match `rom_size - bios_offset` (`0x7e0000` / `0x680000` / `0x3e0000` / `0x280000`).
2. `ifdtool -d` confirms `FLMSTR1=0xffff0000` (host unlocked) and expected `FLREG1`/`FLREG2`/`Density`.
3. `me_cleaner.py -c` confirms **`FTPR` RSA signature VALID** and `AltMeDisable=1` (on minimal/cleaned variants).
4. `cbfstool build/coreboot.rom print` confirms `cpu_microcode_blob.bin`, `fallback/romstage`, `fallback/ramstage`, `fallback/dsdt.aml`, `fallback/postcar`, `fallback/payload`, `vbt.bin`, `bootblock`, plus `SMMSTORE` (`0x40000`) & `RW_MRC_CACHE` (`0x10000`).

## Flashing & Recovery Rules

- **Start `COM5` boot capture first** (`115200 8N1`) before rebooting after a flash; see `serial-communication`.
- **Internal Flash (`flashrom` on booted `h61` with stock locked `FREG2`)**:
  - Can ONLY write `FREG1` (`0x180000+`); use `*-w25q64-8mb-mecleaned-compat-full.rom` (`8 MiB`) or `*-w25q32-4mb-stock-me-full.rom` (`4 MiB`):
    ```bash
    sudo flashrom -p internal -c "W25Q64BV/W25Q64CV/W25Q64FV" --ifd -i bios --noverify-all -w h61m-s1-plus-coreboot-v26.11.4-w25q64-8mb-mecleaned-compat-full.rom
    ```
- **External SPI Flash (Recommended once on socketed DIP-8 `U3`)**:
  - To switch to the **Minimal ME (`124 KiB`, `AltMeDisable=1`, `FLMSTR1=0xffff0000`)** layout (`w25q64-8mb-minimal-me-full.rom` or `w25q32-4mb-minimal-me-full.rom`), flash once externally because stock `FREG2` locks internal writes to IFD/ME.
- **Active ROMs**: Keep ONLY active `v26.11.4` build outputs in `/home/zero/coreboot-work/outputs/` on `.15` (and `outputs\v26.11.4\` on Windows, gitignored — NEVER commit `.rom` outputs to git). See [`docs/HARDWARE-REPORT.md`](../../../docs/HARDWARE-REPORT.md).
