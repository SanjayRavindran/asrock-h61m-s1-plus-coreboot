# External Firmware Blobs, Provenance & Licenses

**Quick Navigation:**
[**Home (`README.md`)**](README.md) ·
[**Features Catalog**](docs/COREBOOT-FEATURES-CATALOG.md) ·
[**Supported CPUs**](docs/SUPPORTED-CPUS.md) ·
[**Hardware Map**](docs/HARDWARE-MAP.md) ·
[**Porting & Lessons**](docs/PORTING-AND-LESSONS-LEARNED.md) ·
[**Hardware Report**](docs/HARDWARE-REPORT.md)

> [!IMPORTANT]
> Since **`v26.11.3`**, this repository and its public GitHub Releases **include all required motherboard/chipset binary blobs in [`blobs/`](blobs/)** alongside the complete, ready-to-flash **4 MiB (`W25Q32`)** and **8 MiB (`W25Q64`)** SPI ROM images (as well as pure BIOS-region slices, `.defconfig` files, and source patches for anyone who wants to inspect or rebuild from scratch).

---

## 1. Committed Blobs in [`blobs/`](blobs/)

| Blob File | Size (Bytes) | SHA-256 | Provenance & Purpose | License / Redistribution |
|---|---:|---|---|---|
| [`blobs/data.vbt`](blobs/data.vbt) | `3,902` | `c6500a60f9cf76ac3c554e0c6dfe80611463b8a2c2a85e0988a0195907baa193` | Desktop Video BIOS Table (`$VBT SNB/IVB-DESKTOP`, VBT 1.00 / BDB 1.66) extracted from stock ASRock `H61M-S1 PLUS` `CSMCORE`; injected into CBFS as `vbt.bin` | Proprietary Intel / ASRock OEM VBT (redistributed unmodified for ASRock H61M-S1 PLUS `libgfxinit`/GOP display parity) |
| [`blobs/me-stock-8.1.20.1336.bin`](blobs/me-stock-8.1.20.1336.bin) | `1,568,768` | `c9c21e3144b7211df19ac52bdecbe4dfd504c2f139c2db6d94728df8226c93df` | Stock Intel ME `8.1.20.1336` (`0x001000..0x17ffff`, 15 partitions, `FTPR` RSA valid) from physical `W25Q32` dump | Proprietary Intel / ASRock ME (used in `w25q32-4mb-stock-me`) |
| [`blobs/me-cleaned-1532k-compat.bin`](blobs/me-cleaned-1532k-compat.bin) | `1,568,768` | `4bfc580ca91958cd62e80a61c46064ac5cdb8099690d3ff62667ebcf808bd842` | `me_cleaner.py -S -d` cleaned ME preserving stock `0x180000` BIOS offset (`FTPR` RSA valid, non-essential partitions removed) | Derived via Coreboot `util/me_cleaner/me_cleaner.py` (GPL-3.0) from stock ME |
| [`blobs/me-minimal-124k.bin`](blobs/me-minimal-124k.bin) | `126,976` | `c96a4d75067b79b8185d032fca67e5351110bfb020e705608e3416e81976d2d8` | Minimal `me_cleaner.py -S -r -t -d` relocated `FTPR` (`ROMP` + `BUP`, `98,304` B raw) `0xff`-padded to `0x1f000` (`124 KiB`) so `BIOS` aligns on `0x020000` | Derived via `me_cleaner.py` (`AltMeDisable=1` + valid `FTPR` prevents Cougar Point 30-min watchdog reset) |
| [`blobs/ifd-8mb-minimal-me-unlocked.bin`](blobs/ifd-8mb-minimal-me-unlocked.bin) | `4,096` | `e7ead7f6de31dc866c61c9eb83a4c41605ef000b06f27322feb1f0769aa76054` | Host-unlocked (`FLMSTR1=0xffff0000`, `FLMSTR2=0x04040000`) 8 MiB IFD: `AltMeDisable=1`, `FLREG2=0x001f0001`, `FLREG1=0x07ff0020`, `Density=8MB` | Intel Flash Descriptor generated via `ifdtool` / `me_cleaner.py` |
| [`blobs/ifd-8mb-mecleaned-compat-unlocked.bin`](blobs/ifd-8mb-mecleaned-compat-unlocked.bin) | `4,096` | `829a0dbc3fad48f7d8712f1cf346017ec50e36b84e47ed15bb633cb25835a459` | Host-unlocked (`FLMSTR1=0xffff0000`, `FLMSTR2=0x04040000`) 8 MiB IFD: `AltMeDisable=1`, `FLREG2=0x017f0001`, `FLREG1=0x07ff0180`, `Density=8MB` | Intel Flash Descriptor (for `W25Q64` `0x180000` compat layout) |
| [`blobs/ifd-4mb-minimal-me-unlocked.bin`](blobs/ifd-4mb-minimal-me-unlocked.bin) | `4,096` | `28a71d1d5d09e054bc1d48dde7de88159d8cb24c8dbd826fdf7ae040a64692a1` | Host-unlocked (`FLMSTR1=0xffff0000`, `FLMSTR2=0x04040000`) 4 MiB IFD: `AltMeDisable=1`, `FLREG2=0x001f0001`, `FLREG1=0x03ff0020`, `Density=4MB` | Intel Flash Descriptor (for `W25Q32` `124 KiB` minimal-ME layout) |
| [`blobs/ifd-4mb-stock-unlocked.bin`](blobs/ifd-4mb-stock-unlocked.bin) | `4,096` | `1f683134faa1a5138794d2ee87a1d7e82f4d076002bb889febd9867fd447bb7b` | Host-unlocked (`FLMSTR1=0xffff0000`, `FLMSTR2=0x00000000`) 4 MiB IFD: `AltMeDisable=0`, `FLREG2=0x017f0001`, `FLREG1=0x03ff0180`, `Density=4MB` | Intel Flash Descriptor (for `W25Q32` `0x180000` stock-ME layout) |

---

## 2. Why Cougar Point H61 Needs `124 KiB` Minimal ME (`ROMP` + `BUP`) Instead of Zero ME

On Intel 6-Series (`Cougar Point`, H61 `8086:1c5c`), wiping the Intel ME SPI region completely triggers an internal hardware **ME watchdog reset/power-off after 30 minutes** because `FTPR` (`ROMP` + `BUP`) is missing or fails RSA verification at hardware bring-up. Running `me_cleaner.py -S -r -t -d`:
1. Strips every non-essential ME runtime module (`KERNEL`, `POLICY`, network/AMT/manageability partitions) down to only `FTPR` (`ROMP` + `BUP`, **`98,304` B** raw), preserving a **valid Intel RSA signature**.
2. Relocates `FTPR` to the bottom of `FREG2` and sets **`AltMeDisable = 1`** in PCH Strap 10 inside the IFD (`Halt` / disable ME right after basic clock/power init).
3. Pads `me-minimal-124k.bin` with `0xff` up to **`126,976` B (`0x1f000`)** so the Coreboot `BIOS` (`FREG1`) region starts cleanly on a **64 KiB FMAP boundary (`0x020000`)** — expanding usable `COREBOOT` flash space to **`7.875 MiB`** on `W25Q64` and **`3.875 MiB`** on `W25Q32`.

> [!NOTE]
> All 4 IFD blobs set **`FLMSTR1 = 0xffff0000`** so once flashed with an external SPI programmer, future updates to IFD, ME, and BIOS can all be performed directly from Linux via `flashrom -p internal`. If your board currently boots with a vendor-locked IFD (`FREG2` locked internally), flash `w25q64-8mb-mecleaned-compat-full.rom` via `flashrom -p internal --ifd -i bios` (updates `FREG1` only), or pull socketed DIP-8 `U3` once and flash `w25q64-8mb-minimal-me-full.rom` externally to reclaim all `7.875 MiB` + enable `AltMeDisable=1` + permanently unlock `FLMSTR1`.

---

## 3. Open-Source Firmware & Reproduction Components

| Component | Version / Pin | Provenance | License |
|---|---|---|---|
| **Coreboot Core & Board Port** | Commit `df45ea2c49b4` + [`patches/0001-sandybridge-h61m-s1-plus-igd-raminit.patch`](patches/0001-sandybridge-h61m-s1-plus-igd-raminit.patch) | [coreboot/coreboot](https://github.com/coreboot/coreboot) + [`board/`](board/) | `GPL-2.0-only` / `GPL-2.0-or-later` |
| **EDK2 `UefiPayloadPkg`** | Commit `f248a68be339` + [`patches/0002-edk2-delete-key-usb-boot-menu.patch`](patches/0002-edk2-delete-key-usb-boot-menu.patch) | [mrchromebox/edk2](https://github.com/mrchromebox/edk2) (`uefipayload_2608` tree) | `BSD-2-Clause-Patent` ([`LICENSES/BSD-2-Clause-Patent.txt`](LICENSES/BSD-2-Clause-Patent.txt)) |
| **Intel CPU Microcode** | `06-3a-09` rev `0x21`, `06-2a-07` rev `0x2f` (`26,624` B) | Coreboot `3rdparty/intel-microcode` ([Intel](https://github.com/intel/Intel-Linux-Processor-Microcode-Data-Files)) | [`LICENSES/Intel-Microcode-License.txt`](LICENSES/Intel-Microcode-License.txt) |

### Master Stock OEM Reference Dumps (Checksums)

| Backup Slot | File Name | Size | SHA-256 | Provenance |
|---|---|---:|---|---|
| **OEM Backup #1** | `h61m-s1-plus-read0.bin` | `4,194,304` B (4 MiB) | `27cb55b24a644eb664790313631fd9ab681398e4a3ea9ec990d367f5539405bb` | Full-chip external SPI dump of the physical motherboard's original 4 MiB flash |
| **OEM Backup #2** | `H61MS1P1.10` | `4,194,304` B (4 MiB) | `e0474ec1054ecbb224211459a1090123aefcecbf582cc2dd00669c661835919c` | Official ASRock `H61M-S1 PLUS` AMI Aptio `P1.10` stock vendor BIOS release |

---

## 4. Operating System Peripheral Firmware (Loaded by Linux, Not in SPI ROM)

- **Realtek RTL8111/8168E LAN (`10ec:8168`, XID `2c9`)**: Uses `rtl_nic/rtl8168e-3.fw` from upstream Linux `linux-firmware` ([kernel.org `linux-firmware`](https://git.kernel.org/pub/scm/linux/kernel/git/firmware/linux-firmware.git/tree/rtl_nic)).
- **Intel I226-V 2.5GbE Add-in NIC (`8086:125c`, when populated in `PCIE2`)**: Driven natively by mainline Linux `igc`.
- **NVIDIA Tesla P4 (`01:00.0`, `10de:1bb3`)**: Uses its own onboard GPU SPI VBIOS (`86.04.8C.00.10`); requires no CBFS VBIOS blob.
- **Audio (`ALC662 rev1`), Super I/O (`NCT6776F/D`), VRMs (`RT8876`/`RT9624`), and H61 PCH**: Fixed-function / SVID hardware with zero field-updatable firmware.
