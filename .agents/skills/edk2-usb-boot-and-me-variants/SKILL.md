---
name: edk2-usb-boot-and-me-variants
description: >-
  Maintain the EDK2 UefiPayloadPkg Delete-key USB Boot Menu, BDS Port 0x80 POST
  codes, CRLF patch workflow, and 4 MiB (W25Q32) / 8 MiB (W25Q64) Intel ME
  variants for the ASRock H61M-S1 PLUS. Use when modifying EDK2 hotkeys/menus,
  regenerating patches/0002-edk2-delete-key-usb-boot-menu.patch, or tuning IFD
  and me_cleaner regions across 4 MiB and 8 MiB SPI flash chips.
---

# EDK2 Delete-Key USB Boot Menu & Multi-Chip ME Variants (`v26.11.3`)

## 1. EDK2 Delete-Key USB Boot Menu & Port `0x80` (`patches/0002`)

[`patches/0002-edk2-delete-key-usb-boot-menu.patch`](../../../patches/0002-edk2-delete-key-usb-boot-menu.patch) applies cleanly onto MrChromebox EDK2 commit `f248a68be339831b69a880d9c932a6a3cf3c461a` (`UefiPayloadPkg`) and modifies 7 upstream files:

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

### D. Critical CRLF Rule for `patches/0002`
- Upstream EDK2 source files use **CRLF (`\r\n`)** line endings.
- **Never** convert `patches/0002-edk2-delete-key-usb-boot-menu.patch` to LF (`\r\n -> \n`) when editing or syncing between Windows and Linux — doing so causes `git apply` to fail cleanly! Always transfer/store `.patch` files as raw binary bytes.
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
