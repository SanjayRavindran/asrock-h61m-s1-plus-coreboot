# ASRock H61M-S1 PLUS — Coreboot Implementation & Hardware Bring-Up Report (`v26.11.4`)

**Quick Navigation:**
[**Home (`README.md`)**](../README.md) ·
[**Features Catalog**](COREBOOT-FEATURES-CATALOG.md) ·
[**Supported CPUs**](SUPPORTED-CPUS.md) ·
[**Hardware Map**](HARDWARE-MAP.md) ·
[**Porting & Lessons**](PORTING-AND-LESSONS-LEARNED.md) ·
[**Hardware Report**](HARDWARE-REPORT.md) ·
[**Blobs & Licenses**](../BLOBS.md)

## Overview

> [!NOTE]
> **Hardware Test Status (`v26.11.4` 8 MiB `w25q64-8mb-mecleaned-compat` ROM)**: Internal `flashrom` Flashed (`VERIFIED`, exit `0`), **`COM5` Live-Verified (`Delete` Key `Select USB Boot Device:` Showing `USB Device` -> Ubuntu Server USB GRUB `UEFI Firmware Settings` `fwsetup` -> Immediate Automatic Cold Reset into `UiApp` with Zero Shutdown)**, **`Secure Boot Configuration` Screen Live-Verified (`Disabled`, `Default` Microsoft Keys, `Standard Mode`)**, **`LPT1` (`0x378`, `PNP0400`, `/dev/parport0`) + `COM1` (`0x3f8`) Active**, **`LPC/TPM1` Port `0x80` (`RCBA_GCS=0x00000c21`, `GEN_PMCON_1=0x0a10`) + TPM 1.2 Probe Verified**, All **10** Runtime CFR `efivars` Passed `self-test` (`h61_coreboot_config.py`), PCI `00:16.0` Hidden from Linux by `me_smm.c`, `I915_CLEAN`, Tesla P4 & I226-V & RTL8111 Active.

This report records the **Coreboot + EDK2 `UefiPayloadPkg`** port, verified **`v26.11.4`** hardware measurements (as well as all four 4 MiB & 8 MiB variants), Delete-key USB Boot Menu live serial validation with a physical Ubuntu Server USB drive, USB GRUB `fwsetup` automatic cold reset into `UiApp`, UEFI Secure Boot DXE & NVMe (`NvmExpressDxe`) components, `LPT1` + `COM1` Super I/O configuration, `LPC/TPM1` Port `0x80` & TPM 1.2 probe registers, Intel ME `8.1.20.1336` behavior on Cougar Point H61, runtime Linux `efivarfs` 10-option CFR TUI/CLI validation, and release SHA-256 checksums for the **ASRock H61M-S1 PLUS** (`H61M-VS4 G/A 1.00` / `R1.01` boardview, Xeon `E3-1275 v2`, Intel H61 `8086:1c5c`, `NCT6776F/D` Super I/O, Realtek `ALC662`, Realtek `RTL8111`, NVIDIA `Tesla P4` in `PCIE1`, Intel `I226-V` in `PCIE2`).

- **Public GitHub Repository**: [SanjayRavindran/asrock-h61m-s1-plus-coreboot](https://github.com/SanjayRavindran/asrock-h61m-s1-plus-coreboot)
- **Coreboot Base**: Commit `df45ea2c49b4c7f6a1d2a969934cf6c6a2cb9018` + [`patches/0001-sandybridge-h61m-s1-plus-igd-raminit.patch`](../patches/0001-sandybridge-h61m-s1-plus-igd-raminit.patch)
- **Payload**: EDK2 `UefiPayloadPkg` (`https://github.com/mrchromebox/edk2`, commit `f248a68be339831b69a880d9c932a6a3cf3c461a`) + [`patches/0002-edk2-delete-key-usb-boot-menu.patch`](../patches/0002-edk2-delete-key-usb-boot-menu.patch) + [`patches/0003-edk2-cf9-reset-and-secureboot-components.patch`](../patches/0003-edk2-cf9-reset-and-secureboot-components.patch) (`CONFIG_EDK2_RELEASE=y`, `CONFIG_EDK2_BOOT_MANAGER_ESCAPE=y`, `-D BOOTSPLASH_IMAGE=FALSE -D NVME_ENABLE=TRUE`, `5s` timeout)
- **Blobs Included in Release**: Desktop `data.vbt` (`3,902` B), host-unlocked IFDs (`FLMSTR1=0xffff0000`), Stock / Compat / `124 KiB` Minimal ME (`blobs/`)

---

## `v26.11.4` Verified Changes & Hardware Measurements

### 1. Internal `flashrom` Flash & `W25Q64` Verification
Flashed `h61m-s1-plus-coreboot-v26.11.4-w25q64-8mb-mecleaned-compat-full.rom` (`8,388,608` B, SHA-256 `d32818a115ad1c99a47c80dc7f7711c6c57cc30cbbf3ce9f78a1db578e7f7882`) onto live `h61` (`192.168.1.24`):

```text
flashrom v1.6.0 on Linux 7.0.0-43-generic (x86_64)
coreboot table found at 0x7fe46000.
Found chipset "Intel H61".
FREG0: Flash Descriptor region (0x00000000-0x00000fff) is read-only.
FREG1: BIOS region (0x00180000-0x007fffff) is read-write.
FREG2: Management Engine region (0x00001000-0x0017ffff) is locked.
Found Winbond flash chip "W25Q64BV/W25Q64CV/W25Q64FV" (8192 kB, SPI) mapped at physical address 0x00000000ff800000.
Updating flash chip contents... Erase/write done from 180000 to 7fffff
Verifying flash... VERIFIED.
```

### 2. Live `COM5` Verification: `Delete` USB Menu -> Ubuntu USB GRUB -> `fwsetup` Auto-Reset -> `UiApp`
- **`patches/0003-edk2-cf9-reset-and-secureboot-components.patch`** fixes `UefiPayloadPkg/Library/ResetSystemLib/ResetSystemLib.c` so `ResetCold()` (and `ResetWarm()` when `ResetValue == 0x06`) writes `0x02 -> 0x06` (`LEGACY_RESET_SYSTEM` -> `LEGACY_RESET_CPU | LEGACY_RESET_SYSTEM`) to port `0xcf9` instead of `0x0a -> 0x0e` (`LEGACY_RESET_FULL`), which asserted `BIT3` and dropped `SLP_S5#` into power-off whenever Coreboot `power_on_after_fail=S5`.
- **Live End-to-End Serial Proof (`COM5`, `outputs/v26.11.4-usb-fwsetup-test.txt`)**:
  1. Booted with a physical `3.7 GiB` Ubuntu Server USB drive (`/dev/sdb1`, `UBUNTU-SERV`, `Boot0003* USB Device`):
     - Coreboot loaded `fallback/payload` (`@0x4e680`, `1,700,717` B) and displayed `Esc to enter Setup Option Menu. / Del to select USB Boot Device. / ENTER to boot directly.`
  2. Sent **`Delete`** (`\x1b[3~`), opening **`Select USB Boot Device:`** listing **`USB Device`**:
     ```text
     Select USB Boot Device:
     USB Device
     Up/Down to move, ENTER to boot USB
     R to rescan USB devices
     ESC to cancel and continue boot
     ```
  3. Pressed `Enter` on `USB Device`, booting `GNU GRUB version 2.14` from `/dev/sdb1`:
     ```text
     *Try or Install Ubuntu Server
      Boot from next volume
      UEFI Firmware Settings
     ```
  4. Highlighted **`*UEFI Firmware Settings`** (`fwsetup`) and pressed `Enter`:
     - System executed an **immediate automatic cold reset** (`reset_offset=234871` -> `coreboot-df45ea2c49b4-dirty ... x86_32 bootblock starting`, `bytes_after_reset=241702`, zero shutdown!) and **automatically entered `UiApp`**:
     ```text
     ASRock H61M-S1 PLUS
      FW: df45ea2c49b4-dirty 11/14/2026
     CPU: Intel(R) Xeon(R) E3-1275 V2
     RAM: 16384 MB
     Default Boot
     Boot Menu
     Boot Manager
     System Configuration
     Reboot
     ```

### 3. Live `COM5` Verification: UEFI Secure Boot DXE Stack & `NVME_ENABLE`
- **`patches/0003`** adds `Pkcs7VerifyDxe`, `RngDxe`, and `Hash2DxeCrypto` alongside `SecureBootConfigDxe`, `EnrollDefaultKeys`, `DxeImageVerificationLib`, and `SecurityStubDxe` even when `iPXE` is disabled; all 4 defconfigs pass `-D BOOTSPLASH_IMAGE=FALSE -D NVME_ENABLE=TRUE`.
- **FV Verification (`UEFIPAYLOAD.txt`)**: Confirmed `NvmExpressDxe.inf`, `ResetSystemRuntimeDxe.inf`, `SecurityStubDxe.inf`, `SecureBootConfigDxe.inf`, `EnrollDefaultKeys.inf` (Microsoft 2011+2023 PK/KEK/db/dbx keys), `Pkcs7VerifyDxe.inf`, `RngDxe.inf`, `Hash2DxeCrypto.inf`, and `DxeImageVerificationLibConstructor`.
- **Live UI Capture (`COM5`, `outputs/v26.11.4-secureboot-ui.txt`)**: `System Configuration` -> `Secure Boot Configuration` displayed:
  ```text
  Secure Boot Configuration
  Current Secure Boot State    Disabled
  Secure Boot Keys             Default
  [ ] Attempt Secure Boot
  [Standard Mode] Secure Boot Mode
  Reset Secure Boot Keys
  ```
- **OS `efivarfs` Verification (`sudo h61-coreboot-config status`)**:
  `SecBoot: Disabled (UserMode, VendorKeys=True, PK=1575B KEK=3066B db=7636B dbx=21416B)`
  `NVMe   : none installed (NvmExpressDxe enabled in UEFI)` (physical NVMe SSD not attached on `h61`).

### 4. Parallel Port (`LPT1`) + `COM1` + `LPC/TPM1` Port `0x80` + Intel ME
- **`COM1` & `LPT1` (`NCT6776F`)**: Both `PNP: 002e.1: enabled 1` (`0x378` IRQ 5 DRQ 4 `CRf0=0x38`) and `PNP: 002e.2: enabled 1` (`0x3f8` IRQ 4); `/dev/parport0` (`crw-rw---- 1 root lp 99, 0`), `self-test` reports `COM1 (0x3f8) active: True` and `LPT1 (0x378) active: True`.
- **`LPC/TPM1` Port `0x80` & TPM Probe**: Coreboot `ramstage` reports `pc80_tpm_probe: No TPM device found` (header unpopulated), `LPC: GEN_PMCON_1=0x0a10 RCBA_GCS=0x00000c21 LPC_EN=0x3c0f LPC_IO_DEC=0x0010` (`RPR_Port80_PCI=0`, `33 MHz` `CLK_PCH_PORT80` active).
- **Intel ME (`me_smm.c` vs Minimal `124 KiB` ME)**: Keep CFR `me_state=0` when booting locked `FREG2` compat/stock ME `8.1.20.1336`; `me_smm.c` (`RCBA32_OR(FD2, PCH_DISABLE_MEI1)`) still hides PCI `00:16.0` before Linux handoff (`lspci -s 00:16.0` returns empty).

### 5. Live OS Runtime CFR, GPU, Display & Sensors (`v26.11.4`)
- **`sudo h61-coreboot-config self-test`**: **`RESULT: PASS`** across all **10** runtime CFR options (`gfx_uma_size=0`, `dram_max_speed=0`, `peg_bifurcation=0`, `hyper_threading=1`, `sata_mode=0`, `nmi=0`, `me_state=0`, `fan_profile=0`, `fb_debug_pause=1`, `power_on_after_fail=0`, all `attrs=0x00000007 present=True`).
- **`dmidecode -t bios`**: `Vendor: coreboot`, `Version: df45ea2c49b4-dirty`, `Release Date: 11/14/2026`, `ROM Size: 8 MB`, `SMBIOS 3.1.0`.
- **GPU & IGD**: `nvidia-smi -L`: `GPU 0: Tesla P4 (UUID: GPU-cef98b3e-4422-7b2b-6e5f-e6e3ba03f603)`; `dmesg` `i915`: **`I915_CLEAN`**.
- **Sensors (`hwmon0 nct6776`, `hwmon1 coretemp`) & Wakeups**:
  `SYSTIN=32.0C`, `AUXTIN=32.0C`, `fan1=4736 RPM` (`pwm1=34.9%`, `en=5`), `fan2=1753 RPM` (`pwm2=29.8%`, `en=5`), `Package id 0=40.0C` (`Core 0..3`: `37-40C`); `/proc/acpi/wakeup`: `PEGP`, `RP01`, `RP04`, `EHC1`, `EHC2` all `S4 enabled`.

---

## `v26.11.4` Release Checksums (All 4 Variants + BIOS Regions)

All images verified on build host `192.168.1.15` (`scripts/build_all_roms.sh`) and SHA-256 verified against `SHA256SUMS.txt`:

| Release File | Size (Bytes) | CBFS Free Space | SHA-256 |
|---|---:|---:|---|
| **`h61m-s1-plus-coreboot-v26.11.4-w25q64-8mb-minimal-me-full.rom`** | `8,388,608` | `5,850,532` | `737110f472874d382a9b5b561da9399f76ed45903d10f86d43151903da2d2441` |
| **`h61m-s1-plus-coreboot-v26.11.4-w25q64-8mb-mecleaned-compat-full.rom`** | `8,388,608` | `4,408,676` | `d32818a115ad1c99a47c80dc7f7711c6c57cc30cbbf3ce9f78a1db578e7f7882` |
| **`h61m-s1-plus-coreboot-v26.11.4-w25q32-4mb-minimal-me-full.rom`** | `4,194,304` | `1,656,228` | `dc77fad456aaded59497566b49b12726bf4cacf62a74523a941fd901c27c1455` |
| **`h61m-s1-plus-coreboot-v26.11.4-w25q32-4mb-stock-me-full.rom`** | `4,194,304` | `214,372` | `4a0f5596e0fd237bea29a18241dd9d977407591610199904a9bd1d8ba871bac7` |
| `h61m-s1-plus-coreboot-v26.11.4-w25q64-8mb-minimal-me-bios-region.bin` | `8,257,536` | `5,850,532` | `1f5acc5271743b9be2ad5ed0da05d02878128407b08cfcb0175c2af2fc51e5bc` |
| `h61m-s1-plus-coreboot-v26.11.4-w25q64-8mb-mecleaned-compat-bios-region.bin` | `6,815,744` | `4,408,676` | `a245546e839c7305b81b0ae4b89184b75432af80955fd6effeea08df6fc7c274` |
| `h61m-s1-plus-coreboot-v26.11.4-w25q32-4mb-minimal-me-bios-region.bin` | `4,063,232` | `1,656,228` | `81f846b6251de039885e459b78d0a7bb9bb79a4346a1291db24583270f637ca4` |
| `h61m-s1-plus-coreboot-v26.11.4-w25q32-4mb-stock-me-bios-region.bin` | `2,621,440` | `214,372` | `5dfa395facd90cc6046fbdc8785676c3e371a80441677763ce62d32bf08d954d` |

---

## Historical Release Baselines (`v26.11.3` & `v26.11.2`)

- **`v26.11.3`**: Added the dedicated `Delete`-key `USB_ONLY` Boot Menu (`patches/0002`, initially verified in empty state `"No bootable USB devices found."` + `ESC`), enabled `LPT1` (`0x378` IRQ 5 `/dev/parport0`), enabled `LPC/TPM1` Port `0x80` POST + TPM 1.2 probe, exposed `me_state` (`10` total CFR options), and introduced 4 public blob-included `W25Q32`/`W25Q64` ROM variants (`me_cleaner` `124 KiB` minimal ME).
- **`v26.11.2`**: Established the `< 4 GiB` Bus-0 MMIO clamp fix (`patches/0001`: `gma.c`, `azalia.c`, `me.c`, `smbus.c`), `fb_console.c`, S3 `PLED-` `LDN 0x0b CR 0xf7 = 0x44` blink, and initial 9-option `CFR_OPTFLAG_RUNTIME` bring-up.
