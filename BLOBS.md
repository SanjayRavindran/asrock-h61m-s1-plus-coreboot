# External Firmware Blobs, Provenance & Licenses

This repository contains **open-source source files, configuration, patches, build scripts, and documentation only**. Proprietary motherboard vendor binaries (Intel Flash Descriptor, Intel Management Engine firmware, and the stock desktop Video BIOS Table) are **not** included in Git or GitHub Release binaries.

## Components Required for a Complete 8 MiB Flashable Image

| Component | Flash Region / File | Provenance & Official Download | SHA-256 (Tested Hardware Baseline) | License / Redistribution |
|---|---|---|---|---|
| **Coreboot Firmware (`bios-region`)** | `0x180000–0x7fffff` (`6,815,744` B) | Built from Coreboot ([coreboot/coreboot](https://github.com/coreboot/coreboot), commit `df45ea2c49b4c7f6a1d2a969934cf6c6a2cb9018`) + this repo's board port | `v26.11` BIOS region (`vbt.bin`-free): `c399baeda9383c3fcc29a7ae36ee17cb43900c58f78a2cd58576c923f5729f46` | Open-source (`GPL-2.0-only` / `GPL-2.0-or-later`) |
| **EDK2 UefiPayloadPkg** | `fallback/payload` in CBFS | [mrchromebox/edk2](https://github.com/mrchromebox/edk2), commit `f248a68be339831b69a880d9c932a6a3cf3c461a` (`uefipayload_2608` tree) | Built from source during Coreboot `make` | `BSD-2-Clause-Patent` ([`LICENSES/BSD-2-Clause-Patent.txt`](LICENSES/BSD-2-Clause-Patent.txt)) |
| **Intel CPU Microcode** | `cpu_microcode_blob.bin` (`26,624` B) | [intel/Intel-Linux-Processor-Microcode-Data-Files](https://github.com/intel/Intel-Linux-Processor-Microcode-Data-Files) (`06-3a-09` rev `0x21`, `06-2a-07` rev `0x2f` — latest upstream) | Bundled via Coreboot `3rdparty/intel-microcode` | [`LICENSES/Intel-Microcode-License.txt`](LICENSES/Intel-Microcode-License.txt) |
| **Intel Flash Descriptor (IFD)** | `0x000000–0x000fff` (`4,096` B) | Extracted from user's own stock SPI dump or [ASRock H61M-S1 PLUS](https://www.asrock.com/mb/Intel/H61M-S1%20PLUS/index.asp) | `b751064c357c3a2028c784e1f183c096cd250733351fc1985b767f19e7b164cc` | Proprietary (Intel / ASRock); supply from your own backup |
| **Intel ME `8.1.20.1336`** | `0x001000–0x17ffff` (`1,568,768` B) | Extracted from user's own stock SPI dump or [ASRock H61M-S1 PLUS](https://www.asrock.com/mb/Intel/H61M-S1%20PLUS/index.asp); optionally stripped with [corna/me_cleaner](https://github.com/corna/me_cleaner) (`me_cleaner.py -S`) | Stock ME: `c9c21e3144b7211df19ac52bdecbe4dfd504c2f139c2db6d94728df8226c93df` | Proprietary (Intel); supply from your own backup |
| **Desktop VBT (`vbt.bin`)** *(Optional)* | `vbt.bin` in CBFS (`3,902` B) | Extracted from stock ASRock AMI `CSMCORE` (`$VBT SNB/IVB-DESKTOP`, VBT 1.00/BDB 1.66) via `UEFIExtract` / `UEFITool` | `c6500a60f9cf76ac3c554e0c6dfe80611463b8a2c2a85e0988a0195907baa193` | Proprietary (Intel / ASRock); stripped from public release artifacts |

## Operating System Peripheral Firmware (Loaded by Linux, Not in SPI ROM)

- **Realtek RTL8111/8168E LAN (`02:00.0`, `10ec:8168`, XID `2c9`)**: Uses `rtl_nic/rtl8168e-3.fw` from upstream Linux `linux-firmware`: [kernel.org linux-firmware](https://git.kernel.org/pub/scm/linux/kernel/git/firmware/linux-firmware.git/tree/rtl_nic).
- **NVIDIA Tesla P4 (`01:00.0`, `10de:1bb3`)**: Uses onboard SPI VBIOS (`86.04.8C.00.10`); does not require an external CBFS VBIOS blob.
- **Audio (`ALC662 rev1`), Super I/O (`NCT6776F/D`), VRMs (`RT8876`/`RT9624`), and H61 PCH**: Fixed-function silicon with no loadable peripheral firmware files.
