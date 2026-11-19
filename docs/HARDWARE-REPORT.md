# ASRock H61M-S1 PLUS — Coreboot Implementation & Hardware Bring-Up Report (`v26.11.2`)

## Overview

This report records the **Coreboot + EDK2 `UefiPayloadPkg`** port, verified `v26.11.2` (and prior `v26.11.1`) hardware measurements, `COM1`-only / `LPT1`-disabled Super I/O configuration, runtime Linux `efivarfs` CFR TUI/CLI validation, power-regulation architecture, microcode/peripheral audit, and public GitHub repository release details for the **ASRock H61M-S1 PLUS** (`H61M-VS4 G/A 1.00` / `R1.01` boardview, Xeon `E3-1275 v2`, Intel H61 `8086:1c5c`, `NCT6776F/D` Super I/O, Realtek `ALC662`, Realtek `RTL8111`, NVIDIA `Tesla P4` in `PCIE1`).

- **Public GitHub Repository**: [SanjayRavindran/asrock-h61m-s1-plus-coreboot](https://github.com/SanjayRavindran/asrock-h61m-s1-plus-coreboot)
- **Coreboot Base**: Commit `df45ea2c49b4c7f6a1d2a969934cf6c6a2cb9018` + `patches/0001-sandybridge-h61m-s1-plus-igd-raminit.patch`
- **Payload**: EDK2 `UefiPayloadPkg` (`https://github.com/mrchromebox/edk2`, commit `f248a68be339831b69a880d9c932a6a3cf3c461a`, `CONFIG_EDK2_RELEASE=y`, `CONFIG_EDK2_BOOT_MANAGER_ESCAPE=y`, `-D BOOTSPLASH_IMAGE=FALSE`, `5s` timeout)
- **Companion Documentation**:
  - [`docs/COREBOOT-FEATURES-CATALOG.md`](COREBOOT-FEATURES-CATALOG.md) — Exhaustive Coreboot software & hardware feature tables
  - [`docs/SUPPORTED-CPUS.md`](SUPPORTED-CPUS.md) — Complete LGA1155 Sandy/Ivy Bridge/Xeon CPU compatibility matrix
  - [`docs/HARDWARE-MAP.md`](HARDWARE-MAP.md) — Verified boardview-to-software pin, BDF, GPIO, Super I/O & Linux sysfs map
  - [`docs/PORTING-AND-LESSONS-LEARNED.md`](PORTING-AND-LESSONS-LEARNED.md) — Accumulated platform engineering knowledge base

---

## `v26.11.2` (`v3.1`) Verified Changes & Hardware Measurements

> **Hardware Test Status (`v26.11.2` 8 MiB ROM): Internal `flashrom` Flashed (`VERIFIED`), Reboot-Verified via `COM5` (`190,586` B captured), `COM1`-Only / `LPT1`-Disabled Verified Live, All 9 Runtime CFR `efivars` Read/Write Verified Live (`h61_coreboot_config.py`).**

### 1. Parallel Port (`LPT1`) Disabled at Boot, `COM1` Active (`115200 8N1`)
- **`devicetree.cb`**: Migrated the 9 `NCT6776F` global multi-function/clock-mux registers (`CR 0x13..0x2f`, including `0x2a = 0x60` for `COM1`) onto **`device pnp 2e.2 on`** (`COM1`, `0x3f8` IRQ 4) and set **`device pnp 2e.1 off end`** (`LPT1`).
- **`early_init.c` & `mainboard.c`**: Replaced `lpt_setup()` with `lpt_disable()` (`LDN 0x01 CR 0x30 = 0x00`) in bootblock and romstage (`mainboard_early_init`), removed `post.c` (`0x378` POST writes), cleared `LPT_LPC_EN` (`00:1f.0` `LPC_EN` bit 2), and set `#undef NCT6776_SHOW_PP` in `acpi/superio.asl`.
- **Live Hardware Proof**:
  - Coreboot bootlog: `PNP: 002e.1: enabled 0` (`LPT1`), `PNP: 002e.2: enabled 1` (`COM1`), `LPC: GEN_PMCON_1=0x0a10 RCBA_GCS=0x00000c21 LPC_EN=0x3c0b` (bit 2 `LPT_LPC_EN` = `0`, bit 0 `COMA_LPC_EN` = `1`).
  - Direct Super I/O `/dev/port` probe on live Ubuntu `7.0.0-43-generic`: `LPT(0x01): CR30=0x00`, `COM1(0x02): CR30=0x01 IO0=0x03f8 IRQ0=4`, `HWM(0x0b): CR30=0xe1 IO0=0x0290 CRf7=0x07`.
  - Linux `/sys/bus/pnp/devices`: `PNP0501` (`COM1`), `PNP0303` (`PS/2` KB), `PNP0f13` (`PS/2` MS) — zero `PNP0400`/`parport0`.
  - Linux root `/proc/ioports`: `03f8-03ff : serial` only (`0378` absent).

### 2. OS-Writable Runtime Coreboot CFR (`CFR_OPTFLAG_RUNTIME`) & `h61_coreboot_config.py`
- **`cfr.c`**: Added `.flags = CFR_OPTFLAG_RUNTIME` to all 9 CFR options (`gfx_uma_size`, `dram_max_speed`, `peg_bifurcation`, `hyper_threading`, `sata_mode`, `nmi`, `fan_profile`, `fb_debug_pause`, `power_on_after_fail`).
- **Live Linux `efivarfs` Proof (`GUID ceae4c1d-335b-4685-a4a0-fc4a94eea085`)**:
  - All 9 variables appear in `/sys/firmware/efi/efivars/` as 8-byte `<II` records (`attrs = 0x00000007` = `NV|BS|RT`, `FS_IMMUTABLE_FL` set).
  - Live read/write round-trip verified on `fb_debug_pause`: `1 -> 2` (`0700000002000000`) -> restored `1` (`0700000001000000`), immutable bit restored cleanly (`----i----`).
  - `sudo h61-coreboot-config self-test` -> `PASS`; interactive 4-tab `curses` TUI verified in real PTY (`TUI_EXIT_CODE=0`, all 4 tabs rendered).

### 3. Carried & Re-Verified Platform Fixes (`v26.11.1` + `v26.11.2`)
- **Bus-0 `< 4 GiB` MMIO Clamps (`gma.c`, `azalia.c`, `me.c`, `smbus.c`)**: Keeps `00:02.0` (`0xdec00000`/`0xe0000000`), `00:1b.0` (`0xdebfc000`, `codec_mask = 09`, `ALC662 rev1` + `Intel CougarPoint HDMI`), `00:16.0` (`0xdebf7000`) `< 4 GiB` while `01:00.0` Tesla P4 retains Above-4G BARs (`0xfe0000000`/`0xff0000000`). **Zero** `i915` forcewake warnings pre- or post-S3; `VT-d`/`DMAR` active (`IOMMU group 2`).
- **On-Screen Debug Console (`fb_console.c`) & EDK2 GOP**: `FB_CONSOLE: rendered 3840x2160 debug log (2820 lines, last_post=0x9c, pause=3s)` before EDK2 GOP UEFI handoff (`-D BOOTSPLASH_IMAGE=FALSE`).
- **SmartFan IV & Live Sensors (`hwmon0 nct6776`, `hwmon1 coretemp`)**: `Balanced` PECI0 fan profile active (`fan1=4787 RPM @ pwm1=34.9% mode=5`, `fan2=1785 RPM @ pwm2=29.8% mode=5`, `SYSTIN=34.0°C`, `AUXTIN=34.0°C`, `Package id 0=45.0°C`).
- **`LPC/TPM1` Free-Running Clock & S3 `PLED-`**: `GEN_PMCON_1=0x0a10` (`CLK_PCH_PORT80` active), `HWM_DEV` `LDN 0x0b CR 0xf7` (`0x07` S0 steady, `0x44` S3 `0.5 Hz` blink in `smihandler.c`, `gpe0_en=0x2a40`, `PEGP`/`RP01`/`EHC1`/`EHC2` `*enabled`).

### 4. Firmware Checksums (`v26.11.2`)

| Artifact | Size (Bytes) | SHA-256 | Notes |
|---|---:|---|---|
| **Full 8 MiB ROM (Stock ME + VBT)** | `8,388,608` | `1356bf6200b6502e0a2ed16d35aee0257ff07e6700f5f9ebb1471ef6c3ab1bbf` | Hardware-flashed & boot-verified (`outputs/h61m-s1-plus-coreboot-8mb-full.rom`) |
| **ME-Cleaned 8 MiB ROM (`me_cleaner -S`)** | `8,388,608` | `279d7db87edd8784f78a2e5e49e5803718996478ea2d3dc1ce64137e7e31b05f` | `AltMeDisable` set, `FTPR` RSA valid, byte-identical 6.5 MiB BIOS region (`outputs/h61m-s1-plus-coreboot-8mb-full-mecleaned.rom`) |
| **8 MiB BIOS Region (`0x180000..0x7fffff`, local build)** | `6,815,744` | `2e6add5822c29cb5d41ce2c4cc78cf393e4eb5eba907d7e020e57109d83b9426` | Matches `0x180000..0x7fffff` of both 8 MiB ROMs |

*(Redistributable GitHub Release `v26.11.2` strips `vbt.bin` from the 6.5 MiB BIOS region — see [`BLOBS.md`](../BLOBS.md) and the release `SHA256SUMS.txt`.)*
