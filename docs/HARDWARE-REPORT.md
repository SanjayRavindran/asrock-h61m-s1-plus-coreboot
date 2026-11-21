# ASRock H61M-S1 PLUS — Coreboot Implementation & Hardware Bring-Up Report (`v26.11.5`)

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
> **Hardware Test Status (`v26.11.5` 8 MiB `w25q64-8mb-mecleaned-compat` ROM)**: Internal `flashrom` Flashed (`VERIFIED`, exit `0`), **`COM5` Live-Verified (`h61 login:`)**, **`NCT6776F` HWM + `SmartFan IV` (`0x0c` `PECI0`) Live-Verified (`PECI0` 34.5 -> 60.0 -> 33.5°C, `pwm1`/`pwm2` 89/76 -> 148/152 -> 89/76, `CHA_FAN1` 1920 -> 3040 -> 1909 RPM)**, **`CPUTIN = 123.5°C` & All Operational HWM Alarms Eliminated**, **`lm-sensors` (`/etc/sensors.d/asrock-h61m-s1-plus.conf`) + `h61-coreboot-config self-test` (`RESULT: PASS`) Verified**, Carried `v26.11.4` `Delete` USB Menu + GRUB `fwsetup` Auto-Reset + `Secure Boot Configuration` + `LPT1`/`COM1`/`LPC Port 0x80` Active, `I915_CLEAN`, Tesla P4 & I226-V & RTL8111 Active.

This report records the **Coreboot + EDK2 `UefiPayloadPkg`** port, verified **`v26.11.5`** hardware measurements (as well as all four 4 MiB & 8 MiB variants), `NCT6776F` HWM/SmartFan IV calibration & live multi-core CPU thermal tracking test, `lm-sensors` + `h61-coreboot-config` runtime verification, carried `v26.11.4` Delete-key USB Boot Menu & GRUB `fwsetup` cold reset into `UiApp`, UEFI Secure Boot DXE & NVMe (`NvmExpressDxe`) components, `LPT1` + `COM1` Super I/O configuration, `LPC/TPM1` Port `0x80` & TPM 1.2 probe registers, Intel ME `8.1.20.1336` behavior, and release SHA-256 checksums for the **ASRock H61M-S1 PLUS** (`H61M-VS4 G/A 1.00` / `R1.01` boardview, Xeon `E3-1275 v2`, Intel H61 `8086:1c5c`, `NCT6776F/D` Super I/O, Realtek `ALC662`, Realtek `RTL8111`, NVIDIA `Tesla P4` in `PCIE1`, Intel `I226-V` in `PCIE2`).

- **Public GitHub Repository**: [SanjayRavindran/asrock-h61m-s1-plus-coreboot](https://github.com/SanjayRavindran/asrock-h61m-s1-plus-coreboot)
- **Coreboot Base**: Commit `df45ea2c49b4c7f6a1d2a969934cf6c6a2cb9018` + [`patches/0001-sandybridge-h61m-s1-plus-igd-raminit.patch`](../patches/0001-sandybridge-h61m-s1-plus-igd-raminit.patch)
- **Payload**: EDK2 `UefiPayloadPkg` (`https://github.com/mrchromebox/edk2`, commit `f248a68be339831b69a880d9c932a6a3cf3c461a`) + [`patches/0002-edk2-delete-key-usb-boot-menu.patch`](../patches/0002-edk2-delete-key-usb-boot-menu.patch) + [`patches/0003-edk2-cf9-reset-and-secureboot-components.patch`](../patches/0003-edk2-cf9-reset-and-secureboot-components.patch) (`CONFIG_EDK2_RELEASE=y`, `CONFIG_EDK2_BOOT_MANAGER_ESCAPE=y`, `-D BOOTSPLASH_IMAGE=FALSE -D NVME_ENABLE=TRUE`, `5s` timeout)
- **Blobs & OS Configs Included**: Desktop `data.vbt` (`3,902` B), host-unlocked IFDs (`FLMSTR1=0xffff0000`), Stock / Compat / `124 KiB` Minimal ME (`blobs/`), and [`configs/asrock-h61m-s1-plus-sensors.conf`](../configs/asrock-h61m-s1-plus-sensors.conf)

---

## `v26.11.5` Verified Changes & Hardware Measurements

### 1. Internal `flashrom` Flash & `W25Q64` Verification
Flashed `h61m-s1-plus-coreboot-v26.11.5-w25q64-8mb-mecleaned-compat-full.rom` (`8,388,608` B, SHA-256 `48745677fae8c8f3fb75c884f9ea56fae745747a5c9248e9ff045917c45bf976`) onto live `h61` (`192.168.1.24`):

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

Captured `COM5` boot (`229,124` bytes to `h61 login:`): `HWM: Applying SmartFan IV profile 'Balanced' (TjMax=105 C)`, `Nuvoton HWM: configuring fan SYSFAN (bank 1)`, `Nuvoton HWM: configuring fan CPUFAN (bank 2)`, `LPC: GEN_PMCON_1=0x0a10 RCBA_GCS=0x00000c21 LPC_EN=0x3c0f LPC_IO_DEC=0x0010`.

### 2. Live `NCT6776F` `lm-sensors` Telemetry & 15s Multi-Core SmartFan IV Verification (`v26.11.5`)
- **`sudo sensors -s && sensors` on `h61`** (`/etc/sensors.d/asrock-h61m-s1-plus.conf`):
  ```text
  nct6776-isa-0290
  Adapter: ISA adapter
  Vcore:             1.03 V  (min =  +0.40 V, max =  +1.60 V)
  +12V:             10.61 V  (min =  +9.98 V, max = +13.20 V)
  AVCC:              3.41 V  (min =  +2.98 V, max =  +3.63 V)
  +3.3V:             3.39 V  (min =  +2.98 V, max =  +3.63 V)
  +5V:               5.21 V  (min =  +4.51 V, max =  +5.50 V)
  3VSB:              3.46 V  (min =  +2.98 V, max =  +3.63 V)
  Vbat:              3.28 V  (min =  +2.70 V, max =  +3.63 V)
  CHA_FAN1:        1920 RPM  (min =    0 RPM)
  CPU_FAN1:        1781 RPM  (min =    0 RPM)
  M/B Temp:         +32.0°C  (high = +75.0°C, hyst = +70.0°C)  sensor = thermistor
  CPU Temp (PECI):  +34.5°C  (high = +85.0°C, hyst = +80.0°C)
                             (crit = +105.0°C)
  pwm1:                 44%  (mode = pwm)
  pwm2:                 38%  (mode = pwm)
  beep_enable:     disabled

  coretemp-isa-0000
  Adapter: ISA adapter
  Package id 0:  +38.0°C  (high = +85.0°C, crit = +105.0°C)
  Core 0:        +34.0°C  (high = +85.0°C, crit = +105.0°C)
  Core 1:        +37.0°C  (high = +85.0°C, crit = +105.0°C)
  Core 2:        +36.0°C  (high = +85.0°C, crit = +105.0°C)
  Core 3:        +36.0°C  (high = +85.0°C, crit = +105.0°C)
  ```
- **15-Second Multi-Core CPU Load & Cooldown Test (Proving Closed-Loop `PECI0` SmartFan IV)**:
  ```text
  baseline     | PECI0= 34.5 C | CorePkg= 38.0 C | pwm1= 89/255 (1920 RPM) | pwm2= 76/255 (1781 RPM)
  load_3s      | PECI0= 58.5 C | CorePkg= 58.0 C | pwm1=139/255 (2772 RPM) | pwm2=142/255 (1776 RPM)
  load_6s      | PECI0= 59.0 C | CorePkg= 60.0 C | pwm1=144/255 (2934 RPM) | pwm2=147/255 (1767 RPM)
  load_9s      | PECI0= 59.5 C | CorePkg= 59.0 C | pwm1=148/255 (2967 RPM) | pwm2=152/255 (1767 RPM)
  load_12s     | PECI0= 59.5 C | CorePkg= 60.0 C | pwm1=148/255 (3013 RPM) | pwm2=152/255 (1771 RPM)
  load_15s     | PECI0= 60.0 C | CorePkg= 60.0 C | pwm1=148/255 (3040 RPM) | pwm2=152/255 (1711 RPM)
  cool_5s      | PECI0= 35.0 C | CorePkg= 37.0 C | pwm1= 89/255 (1906 RPM) | pwm2= 76/255 (1732 RPM)
  cool_10s     | PECI0= 33.5 C | CorePkg= 34.0 C | pwm1= 89/255 (1904 RPM) | pwm2= 76/255 (1732 RPM)
  cool_15s     | PECI0= 33.5 C | CorePkg= 33.0 C | pwm1= 89/255 (1909 RPM) | pwm2= 76/255 (1728 RPM)
  ```
  `PECI Agent 0` (`temp7`) tracked `coretemp Package id 0` within `0.0–1.0°C` under load, and SmartFan IV smoothly ramped `pwm1`/`pwm2` from idle (`89/76`) up to `148/152` (`CHA_FAN1` `1920 -> 3040 RPM` on the shared `CFANOUT` PWM trace) and back down to `89/76` (`1909 RPM`) on cooldown!

### 3. Live `h61-coreboot-config self-test` & `status` (`v26.11.5`)
- **`sudo h61-coreboot-config self-test`**: **`RESULT: PASS`** across all **10** runtime CFR options (`attrs=0x00000007 present=True`), `COM1 (0x3f8) active: True`, `LPT1 (0x378) active: True`, `UEFI Secure Boot: Disabled (UserMode, keys_enrolled=True, PK=1575B KEK=3066B db=7636B dbx=21416B)`, `NCT6776 M/B Temp: 32.0 C`, `NCT6776 CPU Temp (PECI): 33.5 C`, `CHA_FAN1=1909 RPM, CPU_FAN1=1728 RPM`, and **`NCT6776 HWM alarms: 0 (none) [CI1 open/unjumpered]`**.
- **`sudo h61-coreboot-config status`**: Reported scaled `Vcore=0.752V, +12V=10.666V, AVCC=3.392V, +3.3V=3.392V, +5V=5.208V, 3VSB=3.456V, Vbat=3.280V`, `pwm1=34.9% (PWM, en=5, src=7)`, `pwm2=29.8% (PWM, en=5, src=7)`, `Tesla P4: 35 C, 10.12 W`, zero `sudo dmesg` `i915` forcewake/error messages (`I915_SUDO_DMESG_CLEAN`), and `MEI_PCI_00_16_0: ''` (hidden by `me_smm.c`).

### 4. Combined GPU (`Tesla P4 >= 60°C -> 100%`) + CPU Fan Control (`h61-fan-control.service`)
- Installed [`scripts/h61_fan_control.py`](../scripts/h61_fan_control.py) (`/usr/local/bin/h61-fan-control`) + [`configs/h61-fan-control.service`](../configs/h61-fan-control.service) on `h61` (`systemd` enabled & `active`), polling NVML GPU temp + `PECI Agent 0` + `SYSTIN` every 2s (`max(gpu_curve, cpu_curve, mb_curve)` with `2.0°C` cooldown hysteresis).
- **Live Verification Results (`h61`)**:
  - `h61-fan-control --self-test`: **`RESULT: PASS`** (all 11 thermal-curve & hysteresis checks).
  - **Live `GPU=61.0°C` Override Test (`6s`)**: `pwm1`/`pwm2` jumped immediately to **`255/255` (`100%`)**, spinning `CHA_FAN1` up to **`4770–4787 RPM`** and restoring SmartFan IV `mode 5` cleanly on exit.
  - **Fail-Safe Restoration**: `systemctl stop` restored `pwm1_enable=5`, `pwm2_enable=5` via `ExecStopPost`; `systemctl start` resumed `active` (`pwm1_enable=1`, `pwm2_enable=1`).
  - **10s CPU Load Test Under Daemon**: Ramped `pwm1`/`pwm2` smoothly from `76/255` (`1628 RPM`) -> `150/255` (`2986 RPM`) during load (`PECI0` `34.0 -> 59.5°C`), then stepped back cleanly (`3082 -> 2311 RPM`, `pwm=99/255`) during cooldown (`h61-coreboot-config self-test` -> **`RESULT: PASS`**, `[fanctl] h61-fan-control: active`).

---

## Carried-Forward Hardware Verifications (`v26.11.4` Baseline)

### 1. Live `COM5` Verification: `Delete` USB Menu -> Ubuntu USB GRUB -> `fwsetup` Auto-Reset -> `UiApp`
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

### 2. Live `COM5` Verification: UEFI Secure Boot DXE Stack & `NVME_ENABLE`
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

### 3. Parallel Port (`LPT1`) + `COM1` + `LPC/TPM1` Port `0x80` + Intel ME
- **`COM1` & `LPT1` (`NCT6776F`)**: Both `PNP: 002e.1: enabled 1` (`0x378` IRQ 5 DRQ 4 `CRf0=0x38`) and `PNP: 002e.2: enabled 1` (`0x3f8` IRQ 4); `/dev/parport0` (`crw-rw---- 1 root lp 99, 0`), `self-test` reports `COM1 (0x3f8) active: True` and `LPT1 (0x378) active: True`.
- **`LPC/TPM1` Port `0x80` & TPM Probe**: Coreboot `ramstage` reports `pc80_tpm_probe: No TPM device found` (header unpopulated), `LPC: GEN_PMCON_1=0x0a10 RCBA_GCS=0x00000c21 LPC_EN=0x3c0f LPC_IO_DEC=0x0010` (`RPR_Port80_PCI=0`, `33 MHz` `CLK_PCH_PORT80` active).
- **Intel ME (`me_smm.c` vs Minimal `124 KiB` ME)**: Keep CFR `me_state=0` when booting locked `FREG2` compat/stock ME `8.1.20.1336`; `me_smm.c` (`RCBA32_OR(FD2, PCH_DISABLE_MEI1)`) still hides PCI `00:16.0` before Linux handoff (`lspci -s 00:16.0` returns empty).

---

## `v26.11.5` Release Checksums (All 4 Variants + BIOS Regions)

All images verified on build host `192.168.1.15` (`scripts/build_all_roms.sh`) and SHA-256 verified against `SHA256SUMS.txt`:

| Release File | Size (Bytes) | CBFS Free Space | SHA-256 |
|---|---:|---:|---|
| **`h61m-s1-plus-coreboot-v26.11.5-w25q64-8mb-minimal-me-full.rom`** | `8,388,608` | `5,850,340` | `5f949411157872ad70c397d9189a4afa17e065faf213fae36e6d87924226d3f9` |
| **`h61m-s1-plus-coreboot-v26.11.5-w25q64-8mb-mecleaned-compat-full.rom`** | `8,388,608` | `4,408,548` | `48745677fae8c8f3fb75c884f9ea56fae745747a5c9248e9ff045917c45bf976` |
| **`h61m-s1-plus-coreboot-v26.11.5-w25q32-4mb-minimal-me-full.rom`** | `4,194,304` | `1,655,972` | `59c861d17d3b33b904db029b35f323f9edd9c16a9a0f3f8991da496a08b7f402` |
| **`h61m-s1-plus-coreboot-v26.11.5-w25q32-4mb-stock-me-full.rom`** | `4,194,304` | `214,180` | `8e99f4e2481dc61ff4b75f9b055e42ef337d50c47db9b401e345f5dd9f5f228e` |
| `h61m-s1-plus-coreboot-v26.11.5-w25q64-8mb-minimal-me-bios-region.bin` | `8,257,536` | `5,850,340` | `fa4fca7ff73899fcefa82bd08a38ae429c782419c80a28e08409d2df7078cc90` |
| `h61m-s1-plus-coreboot-v26.11.5-w25q64-8mb-mecleaned-compat-bios-region.bin` | `6,815,744` | `4,408,548` | `b8df2d1327f18d234134f81842cf526b721be64fe574e4fde3d167fa8decf4dd` |
| `h61m-s1-plus-coreboot-v26.11.5-w25q32-4mb-minimal-me-bios-region.bin` | `4,063,232` | `1,655,972` | `28587af037e5af62e067eb37d30602835b6f7b4b10dab4ca84dd65fb50ce31c7` |
| `h61m-s1-plus-coreboot-v26.11.5-w25q32-4mb-stock-me-bios-region.bin` | `2,621,440` | `214,180` | `664f75a87269d10149668787d024d54c3b44669f3ef36697f04bdf302bc6ed75` |

---

## Historical Release Baselines (`v26.11.4`, `v26.11.3`, & `v26.11.2`)

- **`v26.11.4`**: Fixed GRUB `fwsetup` shutdown bug (`patches/0003`: `CF9 0x02/0x06`), completed the EDK2 Secure Boot DXE stack (`Pkcs7VerifyDxe`, `RngDxe`, `Hash2DxeCrypto`), explicitly enabled `-D NVME_ENABLE=TRUE`, and verified `Delete` USB Boot Menu with a physical Ubuntu Server USB stick.
- **`v26.11.3`**: Added the dedicated `Delete`-key `USB_ONLY` Boot Menu (`patches/0002`, initially verified in empty state `"No bootable USB devices found."` + `ESC`), enabled `LPT1` (`0x378` IRQ 5 `/dev/parport0`), enabled `LPC/TPM1` Port `0x80` POST + TPM 1.2 probe, exposed `me_state` (`10` total CFR options), and introduced 4 public blob-included `W25Q32`/`W25Q64` ROM variants (`me_cleaner` `124 KiB` minimal ME).
- **`v26.11.2`**: Established the `< 4 GiB` Bus-0 MMIO clamp fix (`patches/0001`: `gma.c`, `azalia.c`, `me.c`, `smbus.c`), `fb_console.c`, S3 `PLED-` `LDN 0x0b CR 0xf7 = 0x44` blink, and initial 9-option `CFR_OPTFLAG_RUNTIME` bring-up.
