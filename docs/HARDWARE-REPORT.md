# ASRock H61M-S1 PLUS — Coreboot Implementation & Hardware Bring-Up Report (`v26.11.3`)

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
> **Hardware Test Status (`v26.11.3` 8 MiB `w25q64-8mb-mecleaned-compat` ROM)**: Internal `flashrom` Flashed (`VERIFIED`, exit `0`), `COM5` Live-Verified (`Delete` Key `Select USB Boot Device:` Popup Triggered + `ESC` Dismissed Cleanly into Ubuntu), **`LPT1` (`0x378`, `PNP0400`, `/dev/parport0`) + `COM1` (`0x3f8`) Active**, **`LPC/TPM1` Port `0x80` (`RCBA_GCS=0x00000c21`, `GEN_PMCON_1=0x0a10`) + TPM 1.2 Probe Verified**, All **10** Runtime CFR `efivars` Passed `self-test` (`h61_coreboot_config.py`), PCI `00:16.0` Hidden from Linux by `me_smm.c`, Zero `i915` Forcewake Warnings, Tesla P4 & I226-V & RTL8111 Active.

This report records the **Coreboot + EDK2 `UefiPayloadPkg`** port, verified **`v26.11.3`** hardware measurements (as well as the 4 MiB & 8 MiB minimal-ME variants), Delete-key USB Boot Menu live serial validation, `LPT1` + `COM1` Super I/O configuration, `LPC/TPM1` Port `0x80` & TPM 1.2 probe registers, Intel ME `8.1.20.1336` behavior on Cougar Point H61, runtime Linux `efivarfs` 10-option CFR TUI/CLI validation, and release SHA-256 checksums for the **ASRock H61M-S1 PLUS** (`H61M-VS4 G/A 1.00` / `R1.01` boardview, Xeon `E3-1275 v2`, Intel H61 `8086:1c5c`, `NCT6776F/D` Super I/O, Realtek `ALC662`, Realtek `RTL8111`, NVIDIA `Tesla P4` in `PCIE1`, Intel `I226-V` in `PCIE2`).

- **Public GitHub Repository**: [SanjayRavindran/asrock-h61m-s1-plus-coreboot](https://github.com/SanjayRavindran/asrock-h61m-s1-plus-coreboot)
- **Coreboot Base**: Commit `df45ea2c49b4c7f6a1d2a969934cf6c6a2cb9018` + [`patches/0001-sandybridge-h61m-s1-plus-igd-raminit.patch`](../patches/0001-sandybridge-h61m-s1-plus-igd-raminit.patch)
- **Payload**: EDK2 `UefiPayloadPkg` (`https://github.com/mrchromebox/edk2`, commit `f248a68be339831b69a880d9c932a6a3cf3c461a`) + [`patches/0002-edk2-delete-key-usb-boot-menu.patch`](../patches/0002-edk2-delete-key-usb-boot-menu.patch) (`CONFIG_EDK2_RELEASE=y`, `CONFIG_EDK2_BOOT_MANAGER_ESCAPE=y`, `-D BOOTSPLASH_IMAGE=FALSE`, `5s` timeout)
- **Blobs Included in Release**: Desktop `data.vbt` (`3,902` B), host-unlocked IFDs (`FLMSTR1=0xffff0000`), Stock / Compat / `124 KiB` Minimal ME (`blobs/`)

---

## `v26.11.3` Verified Changes & Hardware Measurements

### 1. Internal `flashrom` Flash & `W25Q64` Verification
Flashed `h61m-s1-plus-coreboot-v26.11.3-w25q64-8mb-mecleaned-compat-full.rom` (`8,388,608` B, SHA-256 `a4a54e31d1dd8c9d2edfad635e27a1e19000e02969c7cf088be5403fc2761d14`) onto live `h61` (`192.168.1.24`):

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

### 2. Live `COM5` Verification of `Delete`-Key USB Boot Menu
- **`patches/0002-edk2-delete-key-usb-boot-menu.patch`** adds:
  - Dedicated `USB_ONLY` mode in `BootManagerMenuApp` (`BootManagerMenu.c`), filtering `IsUsbBootOption()` (`MSG_USB_DP` / `MSG_USB_CLASS_DP` / `MSG_USB_WWID_DP` AND short-form `MEDIA_HARDDRIVE_DP` paths cross-referenced via `gEfiBlockIoProtocolGuid`).
  - Always displays **`Select USB Boot Device:`** even for 1 or >1 USB bootable disks, safely renders `"No bootable USB devices found."` on 0 disks, and supports `Up/Down`, `Enter`, `R` (rescan), and `ESC` (cancel and continue boot).
  - Registers hidden `Boot0001* USB Boot Menu` (`LOAD_OPTION_CATEGORY_APP`, `OptionalData = L"USB_ONLY"`) bound to `SCAN_DELETE` in `PlatformBootManager.c`.
  - Extends `TerminalConIn.c` so `TerminalTypePcAnsi` decodes VT220 `ESC [ 3 ~` (`\x1b[3~`) into `SCAN_DELETE` alongside `0x7f` and `ESC [ X` (instead of flushing `ESC` via `UnicodeToEfiKeyFlushState`).
- **Live Serial Proof (`COM5`, `outputs/v26.11.3-del-usb-menu-pass.txt`)**:
  - Coreboot handed off to `fallback/payload` (`@0x4e640`, `1,601,696` B).
  - EDK2 printed:
    ```text
    Esc              to enter Setup Option Menu.
    Del              to select USB Boot Device.
    ENTER            to boot directly.
    ```
  - Sending `Delete` (`\x1b[3~`) opened the popup window:
    ```text
    Select USB Boot Device:
    No bootable USB devices found.
    Up/Down to move, ENTER to boot USB
    R to rescan USB devices
    ESC to cancel and continue boot
    ```
  - Sending `ESC` dismissed the USB Boot Menu and resumed normal GRUB (`GNU GRUB version 2.14`) -> Ubuntu `7.0.0-43-generic` boot.
- **Linux `efibootmgr -v` Verification**:
  ```text
  Boot0001* USB Boot Menu	FvVol(8063c21a-8e58-4576-95ce-089e87975d23)/FvFile(eec25bdc-67f2-4d95-b1d5-f81b2039d11d)5500530042005f004f004e004c0059000000
      data: 55 00 53 00 42 00 5f 00 4f 00 4e 00 4c 00 59 00 00 00
  ```

### 3. Parallel Port (`LPT1`) + `COM1` Super I/O (`NCT6776F`) Live Verification
- **Board Changes**: `devicetree.cb` (`device pnp 2e.1 on`: `0x378`, `IRQ 5`, `DRQ 4`, `CRf0=0x38`), `early_init.c` (`lpt_setup()`), `acpi/superio.asl` (`#define NCT6776_SHOW_PP`), `mainboard.c` (`LPC_EN |= LPT_LPC_EN | COMA_LPC_EN`, `LPC_IO_DEC` `0x0010`), `post.c` omitted so `0x378` stays clean for standard parallel peripherals.
- **Live Coreboot + Linux Proof**:
  - Coreboot `ramstage`: `PNP: 002e.1: enabled 1` (`0x378`, IRQ 5, DRQ 4, `CRf0=0x38`), `PNP: 002e.2: enabled 1` (`0x3f8`, IRQ 4 + global registers `0x13..0x2f`).
  - Direct Super I/O `/dev/port` probe (`Boot Test #1`): `SIO LDN 0x01 CR30=0x01 IO=0x0378 IRQ=5 DRQ=4 CRf0=0x38`.
  - Linux `/sys/bus/pnp/devices/*/id`: `PNP0400` (`LPT1`), `PNP0501` (`COM1`), `PNP0303` (`PS/2` KB), `PNP0f13` (`PS/2` MS).
  - Linux `/proc/ioports` & `/dev/parport0`: `0378-037a : parport0`, `03f8-03ff : serial`, `crw-rw---- 1 root lp 99, 0 /dev/parport0`.
  - `sudo h61-coreboot-config self-test`: `COM1 (0x3f8) active : True`, `LPT1 (0x378) active : True`.

### 4. `LPC/TPM1` Port `0x80` POST & LPC TPM Probe Verification
- **Board & EDK2 Changes**: `board/Kconfig` selects `DEFAULT_POST_ON_LPC`, `MAINBOARD_HAS_TPM1`, `MEMORY_MAPPED_TPM`; `devicetree.cb` adds `chip drivers/pc80/tpm` (`device pnp 0c31.0 on end`); `mainboard.c` clears `RCBA32(GCS) &= ~0x04` (when `BILD == 0`) & keeps `GEN_PMCON_1` bits `3:2` cleared (`CLK_PCH_PORT80` active); `PlatformBootManager.c` emits BDS Port `0x80` codes (`0xE1..0xE8`).
- **Live Register & Probe Proof**:
  - Coreboot `ramstage`: `pc80_tpm_probe: No TPM device found` (header unpopulated, cleanly disabled), `LPC: GEN_PMCON_1=0x0a10 RCBA_GCS=0x00000c21 LPC_EN=0x3c0f LPC_IO_DEC=0x0010` (`RPR_Port80_PCI=0`, `33 MHz` `CLKOUT_PCI1` un-gated).

### 5. Intel ME `8.1.20.1336` Behavior on Cougar Point H61 (`me_state` vs `me_smm` vs Minimal `124 KiB` ME)
- Tested toggling runtime CFR `me_state=1` (`Disabled / Soft Temp Disable`, `.flags = CFR_OPTFLAG_RUNTIME` in `src/southbridge/intel/bd82x6x/cfr.c`) on live `h61` (`outputs/v26.11.3-me-disable-boot.txt`, `295,580` B):
  - Because `H61` (`Cougar Point`, `8086:1c5c`) routes through Coreboot's `ME_GEN_7` MKHI path while stock ME `8.1.20.1336` uses `MBP`, `me_state=1` logs `ME: response is not complete` / `failed to enter Soft Temporary Disable mode` (+~1.3s init).
  - Crucially, **`me_smm.c` (`RCBA32_OR(FD2, PCH_DISABLE_MEI1)`) hides PCI `00:16.0` before Linux OS handoff regardless** (`lspci -s 00:16.0` returns empty!).
  - **Recommended Runtime Setting**: Keep `me_state=0` (`Normal`, verified `init finished in 137 msecs` with `00:16.0` still hidden in Linux). For true hardware `AltMeDisable=1` + stripped **`124 KiB`** ME (`me_cleaner -S -r -t -d`), flash `w25q64-8mb-minimal-me-full.rom` (or `w25q32-4mb-minimal-me-full.rom`) externally onto socketed `U3`.

### 6. Live OS Runtime CFR, Hardware Inventory, & Sensors (`v26.11.3`)
- **`sudo h61-coreboot-config self-test`**: **`RESULT: PASS`** across all **10** runtime CFR options (`gfx_uma_size`, `dram_max_speed`, `peg_bifurcation`, `hyper_threading`, `sata_mode`, `nmi`, `me_state=0`, `fan_profile`, `fb_debug_pause=1`, `power_on_after_fail`, all `attrs=0x00000007 present=True`).
- **`dmidecode -t bios`**: `Vendor: coreboot`, `Version: df45ea2c49b4-dirty`, `Release Date: 11/14/2026`, `ROM Size: 8 MB`, `SMBIOS 3.1.0`.
- **PCIe / Graphics / Audio / NICs (`lspci -nnk`)**:
  - `00:02.0` (`8086:016a`, `[1849:016a]`): `libgfxinit` + `vbt.bin` (`1,241` B LZMA), `i915` **`I915_CLEAN`** (zero forcewake/error messages).
  - `00:1b.0` (`8086:1c20`, `[1849:a662]`): `snd_hda_intel` (`ALC662` + `HDMI` audio).
  - `01:00.0` (`10de:1bb3`, `[10de:11d8]`): `NVIDIA Tesla P4`, `nvidia` active (`GPU 0: Tesla P4`), Above-4G MMIO + `VT-d`/`DMAR` active.
  - `02:00.0` (`8086:125c`): `Intel I226-V 2.5GbE` in `PCIE2` (`pcie_rp1`), `igc` active.
  - `03:00.0` (`10ec:8168`, `[1849:8168]`): `Realtek RTL8111` (`pcie_rp4`), `r8169` (`eno0` DHCP via Netplan MAC match).
- **Sensors (`hwmon0 nct6776`, `hwmon1 coretemp`) & Wakeups**:
  - `SYSTIN=33.0C`, `AUXTIN=33.5C`, `fan1=4753 RPM` (`pwm1=34.9%`, `en=5`), `fan2=1708 RPM` (`pwm2=29.8%`, `en=5`), `Package id 0=40.0C` (`Core 0..3`: `37-40C`).
  - `/proc/acpi/wakeup`: `PEGP`, `RP01`, `RP04`, `EHC1`, `EHC2` all `S4 enabled`.

---

## `v26.11.3` Release Checksums (All 4 Variants + Blobs)

All images verified on build host `.15` with `ifdtool -d`, `me_cleaner.py -c` (`FTPR` RSA VALID), and `cbfstool`:

| Release File | Size (Bytes) | CBFS Free Space | SHA-256 |
|---|---:|---:|---|
| **`h61m-s1-plus-coreboot-v26.11.3-w25q64-8mb-minimal-me-full.rom`** | `8,388,608` | `5,949,604` | `0db27e89b2cd8d723f3dea20264d59827cc507bca3afb1b9ccc0b4173dcbe3c9` |
| **`h61m-s1-plus-coreboot-v26.11.3-w25q64-8mb-mecleaned-compat-full.rom`** | `8,388,608` | `4,507,748` | `a4a54e31d1dd8c9d2edfad635e27a1e19000e02969c7cf088be5403fc2761d14` |
| **`h61m-s1-plus-coreboot-v26.11.3-w25q32-4mb-minimal-me-full.rom`** | `4,194,304` | `1,755,300` | `f295ae70e0bf4aa11bbd4a9cc377d9802b2985f7d9ae03628a30d642f1fa9038` |
| **`h61m-s1-plus-coreboot-v26.11.3-w25q32-4mb-stock-me-full.rom`** | `4,194,304` | `313,444` | `fe879af638e109b2065c218e7e941dcebf15bbbb6a69632daa084b711ee2786a` |
| `h61m-s1-plus-coreboot-v26.11.3-w25q64-8mb-minimal-me-bios-region.bin` | `8,257,536` | `5,949,604` | `f1f46013e1d7de2eeadc217e35a2e3effa369776c270414f646bf42165b12e9d` |
| `h61m-s1-plus-coreboot-v26.11.3-w25q64-8mb-mecleaned-compat-bios-region.bin` | `6,815,744` | `4,507,748` | `5844a777bb99640b87d9fc5df9f89b615ffc42ab1ae84de1c4f7a41554bc7050` |
| `h61m-s1-plus-coreboot-v26.11.3-w25q32-4mb-minimal-me-bios-region.bin` | `4,063,232` | `1,755,300` | `cbbd0b0a7dc2c63ef3c2e038449afb40cce3b6322579c428cab2e0a51a5d084b` |
| `h61m-s1-plus-coreboot-v26.11.3-w25q32-4mb-stock-me-bios-region.bin` | `2,621,440` | `313,444` | `65278d79d32498c91533160e2ce093aaf7cc4fc6cb9ee06741786249e1fb11cc` |

---

## Historical `v26.11.2` Baseline Notes

Earlier `v26.11.2` established the clean `< 4 GiB` Bus-0 MMIO clamp fix (`gma.c`, `azalia.c`, `me.c`, `smbus.c`), `fb_console.c`, S3 `PLED-` `LDN 0x0b CR 0xf7 = 0x44` blink, and initial 9-option `CFR_OPTFLAG_RUNTIME` bring-up (`COM1`-only mode before `LPT1`, `LPC/TPM1`, `Delete`-key USB Boot Menu, and 4-variant blob-included builds were added in `v26.11.3`).
