---
name: coreboot-build-and-flash
description: >-
  Build, assemble, validate, and safely prepare Coreboot + EDK2 UefiPayloadPkg
  firmware images for the ASRock H61M-S1 PLUS on build host <build-host>. Use
  this skill whenever modifying Coreboot board/northbridge/payload configs,
  building 4 MiB or 8 MiB SPI ROMs, inspecting CBFS/FMAP/IFD layouts, syncing
  artifacts to Windows, or planning internal/external SPI flashing.
---

# ASRock H61M-S1 PLUS Coreboot Build & Flash Workflow (`v26.11.2`)

## Environment & Immutable Backups

- **Build Host**: `<build-host>` (SSH user `zero`, Ubuntu 26.04)
- **Coreboot Tree**: `/home/zero/coreboot-work/h61m-s1-plus` (branch `h61m-s1-plus-port`, pinned Coreboot commit `df45ea2c49b4c7f6a1d2a969934cf6c6a2cb9018`) + bus-0 `< 4 GiB` MMIO clamp patch (`gma.c`, `azalia.c`, `me.c`, `smbus.c`) + PEG bifurcation/NRI patches
- **EDK2 Payload**: `https://github.com/mrchromebox/edk2` pinned at `f248a68be339831b69a880d9c932a6a3cf3c461a` (`CONFIG_EDK2_RELEASE=y`, `CONFIG_EDK2_BOOT_MANAGER_ESCAPE=y`, `CONFIG_EDK2_CUSTOM_BUILD_PARAMS="-D BOOTSPLASH_IMAGE=FALSE"`, `5s` boot timeout)
- **Board Target**: `src/mainboard/asrock/h61m-s1-plus/` (`BOARD_ASROCK_H61M_S1_PLUS`)
- **Two Preserved OEM BIOS Backups (NEVER modify or overwrite)**:
  - **OEM Backup #1 (Physical Full-Chip Read)**: `~/coreboot-work/inputs/h61m-s1-plus-full-chip-read0.bin` on `.15` / [h61m-s1-plus-read0.bin](<stock-spi-backup-1.bin>) on Windows (`4,194,304` B, SHA-256 `27cb55b24a644eb664790313631fd9ab681398e4a3ea9ec990d367f5539405bb`)
  - **OEM Backup #2 (Official ASRock AMI P1.10)**: `~/coreboot-work/inputs/H61MS1P1.10` on `.15` / [H61MS1P1.10](<stock-spi-backup-2.bin>) on Windows (`4,194,304` B, SHA-256 `e0474ec1054ecbb224211459a1090123aefcecbf582cc2dd00669c661835919c`)
- **Preserved Non-BIOS Regions**:
  - Original 4 MiB IFD (`0x000000–0x000fff`, `4,096` B): `b751064c...`
  - Resized 8 MiB IFD (`FLREG1 = 0x07ff0180`, `0x000000–0x000fff`): `b57a922ac505e534f0b12e624193e2d007b721fc2fa452204cb2562f82eecf83`
  - Intel ME 8.1.20.1336 (`0x001000–0x17ffff`, `1,568,768` B): `c9c21e3144b7211df19ac52bdecbe4dfd504c2f139c2db6d94728df8226c93df`

## Key Board Implementation Rules (`v26.11.2`)

1. **COM1-Only Serial / LPT1 Disabled**:
   - `NCT6776F` global multi-function registers (`0x13..0x2f`, including `0x2a = 0x60` for COM1) MUST live inside `device pnp 2e.2 on` (COM1) in `devicetree.cb` because `device pnp 2e.1 off end` (`LPT1`) skips all devicetree register writes.
   - `early_init.c` calls `lpt_disable()` (`LDN 0x01 CR 0x30 = 0x00`), `acpi/superio.asl` uses `#undef NCT6776_SHOW_PP`, and `mainboard.c` clears `LPT_LPC_EN` (`0x0004`) in `LPC_EN` (`0x3c0b`) while clearing `CLKRUN_EN | PSEUDO_CLKRUN_EN` (`GEN_PMCON_1=0x0a10`) for `LPC/TPM1` pin 1.
2. **All 9 CFR Options Exposed to Linux (`CFR_OPTFLAG_RUNTIME`)**:
   - Every option in `cfr.c` sets `.flags = CFR_OPTFLAG_RUNTIME` so `CfrSetupMenuDxe` creates `NV|BS|RT` (`0x00000007`) UEFI variables under `ceae4c1d-335b-4685-a4a0-fc4a94eea085`. After changing `.flags`, wipe/flash `SMMSTORE` cleanly via `--ifd -i bios` so EDK2 recreates variables with `RT` access.
3. **Public GitHub Config Defconfig Note**:
   - Never commit `data.vbt` (`vbt.bin` stripped from public release assets via `cbfstool ... remove -n vbt.bin`). Always keep `# CONFIG_INTEL_GMA_ADD_VBT is not set` explicitly in `configs/h61m-s1-plus-8mb.defconfig` (otherwise `olddefconfig` re-enables `y` via `INTEL_GMA_HAVE_VBT`).

## Build, Assembly & ME Cleaning (On `<build-host>`)

1. **Snapshot `.config` and verify 8 MiB `W25Q64` sizing**:
   - `BOARD_ROMSIZE_KB_8192=y`, `CONFIG_CBFS_SIZE=0x680000`, `CONFIG_SMMSTORE_SIZE=0x40000` (BIOS region `0x180000–0x7fffff`, `6,815,744` B).
2. **Regenerate config & compile**:
   ```bash
   cd ~/coreboot-work/h61m-s1-plus
   make olddefconfig
   make -j4
   ```
3. **Assemble full 8 MiB ROM & optional ME-cleaned ROM**:
   - Concatenate `[8 MiB IFD 0x0000..0x0fff] + [Stock ME 0x1000..0x17ffff] + [build/coreboot.rom 0x180000..0x7fffff]` into `~/coreboot-work/outputs/h61m-s1-plus-coreboot-8mb-full.rom` (`8,388,608` B).
   - Generate ME-cleaned image cleanly:
     ```bash
     python3 util/me_cleaner/me_cleaner.py -S \
       -O ~/coreboot-work/outputs/h61m-s1-plus-coreboot-8mb-full-mecleaned.rom \
       ~/coreboot-work/outputs/h61m-s1-plus-coreboot-8mb-full.rom
     python3 util/me_cleaner/me_cleaner.py -c ~/coreboot-work/outputs/h61m-s1-plus-coreboot-8mb-full-mecleaned.rom
     ```

## Structural Validation Checklist

1. Full ROMs = `8,388,608` B; BIOS slice = `6,815,744` B (`ifdtool -d` shows `FLREG1 = 0x07ff0180`).
2. `me_cleaner -c` confirms `AltMeDisable` set and `FTPR` RSA valid; BIOS slices `[0x180000:]` match byte-for-byte between full and ME-cleaned ROMs.
3. `./build/cbfstool build/coreboot.rom print` confirms `cpu_microcode_blob.bin`, `fallback/romstage`, `fallback/ramstage`, `fallback/dsdt.aml`, `fallback/postcar`, `fallback/payload`, `bootblock`, plus FMAP `SMMSTORE` (`0x40000`) & `RW_MRC_CACHE` (`0x10000`).

## Flashing & Recovery Rules

- **Start `COM5` boot capture first** (`115200 8N1`) before rebooting after a flash; see `serial-communication`.
- **Internal Flash (`flashrom v1.6.0` on booted `h61`)**: Never pass `--noverify-all` blindly without `-c` and `--ifd -i bios` — `ef 40 17` is ambiguous and `FREG2` (ME) is read-locked:
  ```bash
  sudo flashrom -p internal -c "W25Q64BV/W25Q64CV/W25Q64FV" --ifd -i bios --noverify-all -w h61m-s1-plus-coreboot-8mb-full.rom
  ```
- **Current verified `v26.11.2` ROMs**: Keep ONLY the 2 active full 8 MiB ROMs in `outputs/`. See [`H61M-S1-PLUS-COREBOOT-REPORT.md`](../../../docs/HARDWARE-REPORT.md) and [`docs/HARDWARE-REPORT.md`](../../../docs/HARDWARE-REPORT.md).
