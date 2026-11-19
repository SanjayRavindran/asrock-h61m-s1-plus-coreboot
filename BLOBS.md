# External Firmware Blobs, Provenance & Licenses

**Quick Navigation:**
[**Home (`README.md`)**](README.md) ·
[**Features Catalog**](docs/COREBOOT-FEATURES-CATALOG.md) ·
[**Supported CPUs**](docs/SUPPORTED-CPUS.md) ·
[**Hardware Map**](docs/HARDWARE-MAP.md) ·
[**Porting & Lessons**](docs/PORTING-AND-LESSONS-LEARNED.md) ·
[**Hardware Report**](docs/HARDWARE-REPORT.md)

> [!IMPORTANT]
> This repository contains **open-source code, configuration, patches, build/configuration scripts, and documentation only**. Proprietary motherboard vendor binaries (Intel Flash Descriptor, Intel Management Engine firmware, and the stock desktop Video BIOS Table) are **never** committed to Git or bundled inside public GitHub Release binaries.

---

## 1. Components Required for a Complete 8 MiB Flashable Image

| Component | Flash Region / File | Provenance & Official Download | SHA-256 (`v26.11.2` Tested Hardware Baseline) | License / Redistribution |
|---|---|---|---|---|
| **Coreboot Firmware (`bios-region`)** | `0x180000–0x7fffff` (`6,815,744` B) | Built from [coreboot/coreboot](https://github.com/coreboot/coreboot) (`df45ea2c49b4c7f6a1d2a969934cf6c6a2cb9018`) + this repository's board port & chipset patch | • **Release (`vbt.bin`-free)**: `f01b9226e07e44209aeb9d8995a4aaa8e7d0e3bb92495f9125d4dbd185021f96`<br>• **With local `vbt.bin`**: `2e6add5822c29cb5d41ce2c4cc78cf393e4eb5eba907d7e020e57109d83b9426` | Open-source (`GPL-2.0-only` / `GPL-2.0-or-later`) |
| **EDK2 `UefiPayloadPkg`** | `fallback/payload` in CBFS | [mrchromebox/edk2](https://github.com/mrchromebox/edk2) (`f248a68be339831b69a880d9c932a6a3cf3c461a`, `uefipayload_2608` tree) | Built from source during Coreboot `make` | `BSD-2-Clause-Patent` ([`LICENSES/BSD-2-Clause-Patent.txt`](LICENSES/BSD-2-Clause-Patent.txt)) |
| **Intel CPU Microcode** | `cpu_microcode_blob.bin` (`26,624` B) | [intel/Intel-Linux-Processor-Microcode-Data-Files](https://github.com/intel/Intel-Linux-Processor-Microcode-Data-Files) (`06-3a-09` rev `0x21`, `06-2a-07` rev `0x2f` — latest upstream) | Bundled via Coreboot `3rdparty/intel-microcode` | [`LICENSES/Intel-Microcode-License.txt`](LICENSES/Intel-Microcode-License.txt) |
| **Intel Flash Descriptor (`IFD`)** | `0x000000–0x000fff` (`4,096` B) | Extracted from your own stock SPI dump or [ASRock H61M-S1 PLUS (`P1.10`)](https://www.asrock.com/mb/Intel/H61M-S1%20PLUS/index.asp) and resized to 8 MiB (`FLREG1 = 0x07ff0180`) by [`scripts/assemble_full_rom.sh`](scripts/assemble_full_rom.sh) | • **Stock 4 MiB IFD**: `b751064c357c3a2028c784e1f183c096cd250733351fc1985b767f19e7b164cc`<br>• **Resized 8 MiB IFD**: `b57a922ac505e534f0b12e624193e2d007b721fc2fa452204cb2562f82eecf83` | Proprietary (Intel / ASRock); supply from your own backup |
| **Intel ME `8.1.20.1336`** | `0x001000–0x17ffff` (`1,568,768` B) | Extracted from your own stock SPI dump; optionally stripped/disabled via [corna/me_cleaner](https://github.com/corna/me_cleaner) (`me_cleaner.py -S`) | • **Stock ME**: `c9c21e3144b7211df19ac52bdecbe4dfd504c2f139c2db6d94728df8226c93df` | Proprietary (Intel); supply from your own backup |
| **Desktop VBT (`vbt.bin`)** *(Optional)* | `vbt.bin` in CBFS (`3,902` B) | Extracted from stock ASRock AMI `CSMCORE` (`$VBT SNB/IVB-DESKTOP`, VBT 1.00 / BDB 1.66) via `UEFIExtract` / `UEFITool` | `c6500a60f9cf76ac3c554e0c6dfe80611463b8a2c2a85e0988a0195907baa193` | Proprietary (Intel / ASRock); stripped from public release artifacts |

> [!TIP]
> Use [`scripts/assemble_full_rom.sh`](scripts/assemble_full_rom.sh) to automatically extract the 4 KiB IFD and 1.5 MiB ME region from your stock 4 MiB or 8 MiB dump, patch `FLREG1` for 8 MiB (`W25Q64`), and stitch the 6.5 MiB Coreboot BIOS region into a complete `8,388,608`-byte flashable ROM.

---

## 2. Two Verified Stock OEM BIOS Backups (Local Recovery Reference)

| Backup Slot | File Name | Size | SHA-256 | Provenance |
|---|---|---:|---|---|
| **OEM Backup #1** | `h61m-s1-plus-read0.bin` | `4,194,304` B (4 MiB) | `27cb55b24a644eb664790313631fd9ab681398e4a3ea9ec990d367f5539405bb` | Full-chip external SPI dump of the physical motherboard's original 4 MiB flash |
| **OEM Backup #2** | `H61MS1P1.10` | `4,194,304` B (4 MiB) | `e0474ec1054ecbb224211459a1090123aefcecbf582cc2dd00669c661835919c` | Official ASRock `H61M-S1 PLUS` AMI Aptio `P1.10` stock vendor BIOS release |

---

## 3. Operating System Peripheral Firmware (Loaded by Linux, Not in SPI ROM)

- **Realtek RTL8111/8168E LAN (`02:00.0`, `10ec:8168`, XID `2c9`)**: Uses `rtl_nic/rtl8168e-3.fw` from upstream Linux `linux-firmware` ([kernel.org `linux-firmware`](https://git.kernel.org/pub/scm/linux/kernel/git/firmware/linux-firmware.git/tree/rtl_nic)).
- **NVIDIA Tesla P4 (`01:00.0`, `10de:1bb3`)**: Uses its own onboard GPU SPI VBIOS (`86.04.8C.00.10`); requires no CBFS VBIOS blob.
- **Audio (`ALC662 rev1`), Super I/O (`NCT6776F/D`), VRMs (`RT8876`/`RT9624`), and H61 PCH**: Fixed-function / SVID hardware with zero field-updatable firmware.
