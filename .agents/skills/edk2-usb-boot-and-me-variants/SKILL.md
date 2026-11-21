---
name: edk2-usb-boot-and-me-variants
description: >-
  Maintain the EDK2 UefiPayloadPkg Delete-key USB Boot Menu, BDS Port 0x80 POST
  codes, CRLF patch workflow, and 4 MiB (W25Q32) / 8 MiB (W25Q64) Intel ME
  variants for the ASRock H61M-S1 PLUS. Use when modifying EDK2 hotkeys/menus,
  regenerating patches/0002-edk2-delete-key-usb-boot-menu.patch, or tuning IFD
  and me_cleaner regions across 4 MiB and 8 MiB SPI flash chips.
---

# EDK2 Delete-Key USB Boot Menu, CF9 Reset, Secure Boot & ME Variants (`v26.11.4`)

## 1. EDK2 Patches (`0002` & `0003`) & Critical CRLF Rule

Two CRLF-preserving EDK2 patches apply cleanly onto MrChromebox EDK2 commit `f248a68be339831b69a880d9c932a6a3cf3c461a` (`UefiPayloadPkg`):
- [`patches/0002-edk2-delete-key-usb-boot-menu.patch`](../../../patches/0002-edk2-delete-key-usb-boot-menu.patch): Delete-key USB Boot Menu, `TerminalTypePcAnsi` `\x1b[3~` decode, BDS Port `0x80` POST codes (`0xE1..0xE8`).
- [`patches/0003-edk2-cf9-reset-and-secureboot-components.patch`](../../../patches/0003-edk2-cf9-reset-and-secureboot-components.patch): Fixes PCH CF9 cold/warm reset shutdown bug (`0x0a -> 0x0e` with `LEGACY_RESET_FULL` changed to `0x02 -> 0x06` matching Coreboot FADT) and adds `Pkcs7VerifyDxe` (+ `RngDxe` / `Hash2DxeCrypto` even when `NETWORK_DRIVER_ENABLE == FALSE`) alongside `SecureBootConfigDxe`, `EnrollDefaultKeys`, and `NvmExpressDxe`.

### A. Dedicated USB Selection Popup (`MdeModulePkg/Application/BootManagerMenuApp/`)
- **`BootManagerMenu.{c,h}`, `BootManagerMenuApp.inf`, `BootManagerMenuStrings.uni`**:
  - Activated when launched with `LoadedImage->LoadOptions` starting with `L"USB_ONLY"`.
  - **Always opens the popup window (`"Select USB Boot Device:"`)** even when only **1** bootable USB disk is present (or `> 1`), so tapping `Delete` consistently lets the user confirm or choose between multiple USB disks.
  - Filters `EFI_BOOT_MANAGER_LOAD_OPTION` entries via `IsUsbBootOption()`:
    - `IsUsbDevicePath()` matches `MESSAGING_DEVICE_PATH` nodes with `MSG_USB_DP`, `MSG_USB_CLASS_DP`, or `MSG_USB_WWID_DP`.
    - Also matches short-form UEFI OS `MEDIA_HARDDRIVE_DP` (`Boot####`) paths by scanning `gEfiBlockIoProtocolGuid` handles whose full device path contains USB messaging nodes (`FindHardDriveNode()`).
  - Safely displays `"No bootable USB devices found."` (`HasBootableItems = FALSE`) when 0 USB disks are present instead of hitting upstream `BootManagerMenuApp`'s zero-item `ASSERT` or skipping the menu.
  - Keys inside popup: `Up/Down` (`SelectItem`), `Enter` (`BootFromSelectOption` via `OptionMap`), `R`/`r` (rescan `EfiBootManagerConnectAll()` + `EfiBootManagerRefreshAllBootOption()`), `ESC` (cancel and resume normal boot).

### B. Hotkey Binding & BDS Port `0x80` POST Codes (`UefiPayloadPkg/Library/PlatformBootManagerLib/`)
- **`PlatformBootManager.c`, `PlatformBootManagerLib.inf`**:
  - `PlatformRegisterUsbBootMenuOption()` registers a hidden `LOAD_OPTION_CATEGORY_APP` `Boot####` entry `"USB Boot Menu"` (`mUsbBootMenuFileGuid = eec25bdc-67f2-4d95-b1d5-f81b2039d11d`) with `OptionalData = L"USB_ONLY"`.
  - `PlatformBootManagerBeforeConsole()` clears stale `SCAN_DELETE` key options via `EfiBootManagerDeleteKeyOptionVariable()` and binds `SCAN_DELETE` -> `UsbOptionNumber` (`EfiBootManagerAddKeyOptionVariable`), alongside `RegisterKeyNotify` (`UsbBootMenuEntryNotifyCallback`).
  - Serial/GOP prompts advertise **`Esc to enter Setup Option Menu. / Del to select USB Boot Device.`** (`Press ESC for Setup, DEL for USB Boot Menu`).
  - BDS writes Port `0x80` POST codes via `IoLib`: `0xE1` (pre-console), `0xE2` (devices connected), `0xE3` (boot prompt/wait), `0xE5` (entering USB Boot Menu), `0xE8` (launching default OS boot).

### C. Serial Console `Delete` Key Decode (`MdeModulePkg/Universal/Console/TerminalDxe/TerminalConIn.c`)
- `UefiPayloadPkg` defaults `DEFAULT_TERMINAL_TYPE = 0` (`TerminalTypePcAnsi` / `gPcAnsiTerminal` in `PlatformConsole.c`).
- Upstream `TerminalConIn.c` only accepts VT220 `ESC [ 3 ~` (`\x1b[3~`) under `TerminalTypeTtyTerm`, causing `TerminalTypePcAnsi` to flush `\x1b[3~` via `UnicodeToEfiKeyFlushState()` as standalone `SCAN_ESC` (accidentally opening `UiApp` Setup!).
- Our patch extends `TerminalConIn.c` (`INPUT_STATE_ESC | INPUT_STATE_LEFTOPENBRACKET` and `INPUT_STATE_LEFTOPENBRACKET_TTY`) to allow **both `TerminalTypeTtyTerm` and `TerminalTypePcAnsi`** to decode VT220 `ESC [ 3 ~` -> `SCAN_DELETE`, alongside `0x7f`, `ESC [ X`, and physical USB/PS/2 `Delete`.

### D. CF9 Reset (`ResetSystemLib.c`) for GRUB `fwsetup` & OS `BootToFwUi`
- MrChromebox's `UefiPayloadPkg/Library/ResetSystemLib/ResetSystemLib.c` overrides Coreboot FADT `CF9=0x06` with `0x0a -> 0x0e` (`LEGACY_RESET_FULL`, `BIT3` + `BIT2` + `BIT1`).
- On `ASRock H61M-S1 PLUS` (`H61` + `NCT6776F` `LDN 0x0a` AC power-loss off / `S5`), asserting `CF9 BIT3` (`FULL_RST`) drops `SLP_S5#` / `PSON#` into power-off instead of immediately rebooting back into UEFI Setup when selecting GRUB **`UEFI Firmware Settings`** (`fwsetup` / `EfiResetCold`).
- `patches/0003` restores `0x02 -> 0x06` (`LEGACY_RESET_SYSTEM` -> `LEGACY_RESET_CPU | LEGACY_RESET_SYSTEM`) in `ResetCold()` (and `ResetWarm()` when `ResetValue == 0x06`), giving instant automatic reset into `UiApp`.

### E. NVMe (`NvmExpressDxe`) & Secure Boot Component Audit
- Defconfigs explicitly pass `-D BOOTSPLASH_IMAGE=FALSE -D NVME_ENABLE=TRUE`, and `scripts/build.sh` verifies `UEFIPAYLOAD.txt` contains `NvmExpressDxe`, `SecureBootConfigDxe`, `EnrollDefaultKeys`, `Pkcs7VerifyDxe`, `RngDxe`, `Hash2DxeCrypto`, `DxeImageVerificationLib`, `SecurityStubDxe`, and `ResetSystemRuntimeDxe`.
- `EnrollDefaultKeys` provisions Microsoft 2011 + 2023 `PK`, `KEK`, `db`, and `dbx` in `SMMSTORE` on first boot, leaving `SecureBoot=0` by default (`CONFIG_EDK2_SECURE_BOOT_DEFAULT_ENABLE` unset) until toggled ON under `Device Manager / System Configuration` -> `Secure Boot Configuration`.

### F. Critical CRLF Rule for EDK2 Patches (`0002` & `0003`)
- Upstream EDK2 source files use **CRLF (`\r\n`)** line endings.
- **Never** convert `patches/0002-*.patch` or `patches/0003-*.patch` to LF (`\r\n -> \n`) when editing or syncing between Windows and Linux — doing so causes `git apply` to fail cleanly! Always transfer/store `.patch` files as raw binary bytes.
- To rebuild EDK2 cleanly on `192.168.1.15`, remove `build/UEFIPAYLOAD.fd` and `payloads/external/edk2/workspace/Build/` before running [`scripts/build_all_roms.sh`](../../../scripts/build_all_roms.sh).

---

## 2. Four SPI ROM Variants & Minimal-ME Generation Rules

H61 (`Cougar Point` PCH) hardware enforces an Intel ME 30-minute power-off timer if the flash descriptor/ME region lacks a valid `FTPR` (`ROMP` + `BUP`) partition. Thus the **minimum hardware-stable ME on H61** is produced by `me_cleaner.py -S -r -t -d`:

| Variant (`VARIANT_NAME`) | Target Chip | IFD Blob (`blobs/`) | ME Blob (`blobs/`) | BIOS Offset / Size | `AltMeDisable` | Flash Method |
|---|---|---|---|---|---|---|
| `w25q64-8mb-minimal-me` | `W25Q64` (`8 MiB`) | `ifd-8mb-minimal-me-unlocked.bin` (`FLREG1=0x07ff0020`) | `me-minimal-124k.bin` (`126,976` B) | `0x020000` (`7.875 MiB`) | **Yes (`1`)** | **External SPI** once (or internal after IFD unlocked) |
| `w25q64-8mb-mecleaned-compat` | `W25Q64` (`8 MiB`) | `ifd-8mb-mecleaned-compat-unlocked.bin` (`FLREG1=0x07ff0180`) | `me-cleaned-1532k-compat.bin` (`1,568,768` B) | `0x180000` (`6.5 MiB`) | Yes (`1`, ignored by stock `FREG2`) | **Internal `flashrom --ifd -i bios`** on stock-IFD systems |
| `w25q32-4mb-minimal-me` | `W25Q32` (`4 MiB`) | `ifd-4mb-minimal-me-unlocked.bin` (`FLREG1=0x03ff0020`) | `me-minimal-124k.bin` (`126,976` B) | `0x020000` (`3.875 MiB`) | **Yes (`1`)** | **External SPI** once on `4 MiB` chips |
| `w25q32-4mb-stock-me` | `W25Q32` (`4 MiB`) | `ifd-4mb-stock-unlocked.bin` (`FLREG1=0x03ff0180`) | `me-stock-8.1.20.1336.bin` (`1,568,768` B) | `0x180000` (`2.5 MiB`) | No (`0`) | Internal `--ifd -i bios` on stock `4 MiB` boards |

### Safety & Alignment Rules for `me_cleaner.py`
1. **NEVER run `me_cleaner.py` without `-O <output>`** against an input backup! Without `-O`, `me_cleaner.py` edits the input image **in-place**. Always copy inputs to `/tmp` (`chmod 644`) first and keep `~/coreboot-work/inputs/*` read-only (`chmod 400`/`444`).
2. `me_cleaner.py -S -r -t -d` truncates ME to `0x18000` (`96 KiB`), which is not 64 KiB block-aligned with Coreboot's FMAP (`BIOS` must start on a 64 KiB boundary). Pad `me-minimal-124k.bin` with `0xff` up to `126,976` B (`0x1f000`) so `4,096` B IFD + `126,976` B ME puts `BIOS` at **`0x020000`**, with `FLREG2=0x001f0001` and `FLREG1=0x03ff0020` (`4 MiB`) or `0x07ff0020` (`8 MiB`), `FLMSTR1=0xffff0000`, `FLMSTR2=0x04040000`.
3. `CONFIG_SMMSTORE_SIZE` (`0x40000`) and `CONFIG_MRC_SETTINGS_CACHE_SIZE` (`0x10000`) stay identical across all 4 variants; only `CONFIG_COREBOOT_ROMSIZE_KB` (`4096`/`8192`) and `CONFIG_CBFS_SIZE` (`0x280000` / `0x3e0000` / `0x680000` / `0x7e0000`) vary.
