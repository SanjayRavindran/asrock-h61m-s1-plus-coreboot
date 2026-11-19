# ASRock H61M-S1 PLUS — Coreboot + EDK2 UEFI Port

Open-source **Coreboot + EDK2 `UefiPayloadPkg`** board port, Sandy/Ivy Bridge chipset patches, Linux OS runtime TUI/CLI configurator ([`scripts/h61_coreboot_config.py`](scripts/h61_coreboot_config.py)), build/assembly scripts, comprehensive hardware/CPU/feature documentation, AI agent skills ([`.agents/skills/`](.agents/skills/)), and automated quarterly release pipeline for the **ASRock H61M-S1 PLUS** motherboard (`H61M-VS4 G/A 1.00`, LGA1155, Intel H61 Express `8086:1c5c`, Nuvoton `NCT6776F/D` Super I/O, Realtek `ALC662`, Realtek `RTL8111`, 8 MiB `W25Q64` SPI flash).

> **Public Releases**: See [**Releases**](../../releases) for pre-built 6.5 MiB open-source Coreboot + EDK2 BIOS-region binaries (`SHA256SUMS.txt` included) and [`quarterly-release.yml`](.github/workflows/quarterly-release.yml) aligned with upstream Coreboot `YY.03` / `YY.06` / `YY.09` / `YY.12` cycles.

---

## Disclaimers (Read Before Use)

1. **Hardware Risk & Recovery**: Flashing motherboard SPI firmware can permanently brick hardware if interrupted or misconfigured. This project is provided **AS IS** with **NO WARRANTY**. Always capture and verify a full-chip stock backup with an external SPI flash programmer (e.g., CH341A / Dediprog / flashrom) before writing any ROM. Never flash raw `coreboot.rom` builds or redistributable BIOS-region slices directly onto the whole chip without assembling them with your stock Intel Flash Descriptor (IFD) and Intel ME via [`scripts/assemble_full_rom.sh`](scripts/assemble_full_rom.sh).
2. **Known Disabled, Deferred, or Caveated Items (`v26.11.2`)**:
   - **Parallel Port (`LPT1`) Intentionally Disabled at Boot (`COM1`-Only)**: As of `v26.11.2`, `NCT6776F` `LDN 0x01` (`LPT1` `0x378`), ACPI `PNP0400`, `0x378` LPT POST mirroring (`post.c`), and PCH `LPC_EN[2]` (`LPT_LPC_EN`) are **disabled at boot** so only `COM1` (`0x3f8`, IRQ 4, `115200 8N1`) is active.
   - **Physical `VGA1` Dual-Head & Physical `LPC/TPM1` POST Card**: Pure open-source `libgfxinit` configures both `HDMI1` + `Analog` pipes (`gma-mainboard.ads`), and `LPC/TPM1` `CLKOUT_PCI1` gating (`PSEUDO_CLKRUN_EN`) is cleared (`GEN_PMCON_1=0x0a10`), with all registers verified live via `/dev/port` and `lspci`. Live tests used an `HDMI` monitor (`VGA-1` unplugged) without attaching a hardware LPC POST reader.
   - **ACPI S3 with NVIDIA Proprietary / vGPU Driver (`NVreg_PreserveVideoMemoryAllocations=1`)**: Linux requires writing `suspend` to `/proc/driver/nvidia/suspend` before sleeping (and `resume` afterward), otherwise `nvidia` vetoes `pm_suspend` with `-EIO`. [`scripts/h61_coreboot_config.py`](scripts/h61_coreboot_config.py) (`s3` command & TUI) performs this handshake automatically.
   - **PCIe x16 Slot Bifurcation (`2x8` / `1x8+2x4`)**: Exposed in runtime CFR (`peg_bifurcation`) and gated in `early_init.c`/`northbridge.c` (defaulting to `1x16`). On Ivy Bridge LGA1155, splitting lanes also requires CPU `CFG[6:5]` physical hardware straps; only `1x16` (`PCIE1`) is tested on hardware.
   - **NVIDIA Tesla P4 (`10de:1bb3`)**: Pascal Tesla P4 does not advertise hardware SR-IOV or Resizable BAR capabilities despite Coreboot ReBAR/plugin support; vGPU uses `nvidia_vgpu_vfio` MDEV, idling at `P8` `2.5GT/s x16`.
   - **ME-Cleaned Image Hardware Boot**: An 8 MiB `me_cleaner.py -S` image is built and structurally validated (`AltMeDisable` set, `FTPR` RSA valid, byte-identical BIOS region); live boot validation on hardware remains pending vs the hardware-verified stock-ME 8 MiB image.
   - **DDR3-1600 / 1.65 V XMP Testing**: `CONFIG_NATIVE_RAMINIT_IGNORE_XMP_REQUESTED_VOLTAGE=y` and `Auto` SPD frequency are enabled, while the tested Kingston `99U5471-040.A00LF` pair is `1.5 V` `1333 MT/s` max (`666 MHz` / `1332 MT/s` `CL9`). True `1600+ MT/s` / `1.65 V` XMP sticks await testing.
   - **Runtime CBMEM Log on Stock Ubuntu Kernels**: Stock Ubuntu kernels omit `drivers/firmware/google/` (`memconsole_coreboot`); view Coreboot logs at boot on-screen via `fb_console` or capture over `COM1` (`115200 8N1`).
3. **LLM / AI-Assisted Engineering Disclaimer**: Portions of the board port source files, chipset patches, Python TUI/CLI configurator, skill workflows, and documentation were authored or refined with **Large Language Model (LLM)** assistance under human supervision, and cross-checked against the ASRock `H61M-VS4 G/A 1.00` boardview, Intel/Nuvoton/Realtek/Winbond datasheets, stock SPI dumps, and live physical hardware telemetry.

---

## Documentation Index

| Document | Contents |
|---|---|
| [`docs/COREBOOT-FEATURES-CATALOG.md`](docs/COREBOOT-FEATURES-CATALOG.md) | Exhaustive tables of **all** Coreboot software & hardware features for the H61M-S1 PLUS (`vboot`, Heads/LinuxBoot, SeaBIOS/iPXE/Memtest86+, `CFR`/`SMMSTORE`, `libgfxinit`, `NRI` XMP, SmartFan IV, TPM/SPI locks, quick-pick recipes) |
| [`docs/SUPPORTED-CPUS.md`](docs/SUPPORTED-CPUS.md) | Complete **Supported LGA1155 CPUs** list (Xeon E3-1200 v1/v2, Core i7/i5/i3 2xxx/3xxx, Pentium, Celeron, microcode revisions, `UP701` `RT8876` 95 W VRM ceiling, IGD/VT-d/PCIe 3.0 caveats) |
| [`docs/HARDWARE-MAP.md`](docs/HARDWARE-MAP.md) | Full **Software-to-Hardware Connection Map** (CPU `U1` PEG/CFG pins, PCH GPIOs `0..75`, `NCT6776F` LDNs & pin-mux, VRM rails, HDA verbs, SPI flash layout) |
| [`docs/PORTING-AND-LESSONS-LEARNED.md`](docs/PORTING-AND-LESSONS-LEARNED.md) | Accumulated platform engineering knowledge (Above-4G 32-bit `ramstage` bug fix, EDK2 `BOOTSPLASH_IMAGE`, `NCT6776` `LDN 0x0b CR 0xf7`, `CLKRUN`, `efivarfs`, Netplan `eno0`, NVIDIA S3, CH340 Error 31) |
| [`docs/HARDWARE-REPORT.md`](docs/HARDWARE-REPORT.md) | Live hardware bring-up telemetry, `flashrom` verification logs, and `v26.11.2` release checksums |
| [`BLOBS.md`](BLOBS.md) & [`LICENSES/`](LICENSES/) | Open-source licenses (`GPL-2.0-only`, `GPL-2.0-or-later`, `BSD-2-Clause-Patent`, Intel Microcode) and binary blob provenance/download notes |
| [`.agents/skills/`](.agents/skills/) | Reusable sanitized AI agent workflows & Win32 `COM` serial tools (`com_serial.py`, `serial_exec.py`) |

---

## Software-to-Hardware Connection Map

### Topology Diagram

```text
                           +---------------------------------------------------+
                           |    2x 240-pin DDR3 UDIMM Slots                    |
                           |    DDR3_A1 (SPD 0x50)  |  DDR3_B1 (SPD 0x52)      |
                           +-------------------------+-------------------------+
                                                     ^  SMBus 0x400 + Dual-Channel IMC
                                                     v  (sandybridge/raminit_native.c)
+---------------------------------------------------------------------------------------------------+
|  Socket U1 (LGA1155) — Intel Xeon E3-1275 v2 / 2nd & 3rd Gen Core / Pentium / Celeron             |
|  * IGD 00:02.0 (8086:016a, <4G 0xe0000000) --+-> PCH CRT/DAC ---> VGA1 (D-Sub, libgfxinit Analog) |
|                                              +-> PCH DDPB    ---> HDMI1 (TMDS, libgfxinit HDMI1)  |
|  * PEG10 00:01.0 (x16, CFG[6:5] on U1) --------> PCIE1 x16  ---> Add-in GPU / Tesla P4 (>4G)     |
|  * Intel SVID Bus ------------------------------> UP701 (RT8876 3+1 VRM) + UP751 (RT9624 VAXG)     |
|  * Single-Wire PECI (pin 115 on U1007) ---------> NCT6776F PECI Agent 0 (SmartFan IV + coretemp)   |
+----------------------------------------------------+----------------------------------------------+
                                                     | DMI Link
                                                     v
+---------------------------------------------------------------------------------------------------+
|  Intel H61 Express PCH (BD82x6x, PCI 00:1f.0 ID 8086:1c5c)                                        |
|  +-- 00:16.0 MEI1 (8086:1c3a, <4G) --------> Intel ME 8.1.20.1336 (FREG2 0x1000..0x17ffff)       |
|  +-- 00:1a.0 EHCI2 / 00:1d.0 EHCI1 --------> USB 2.0 Ports 0-5, 8-9 (shared OC0#, S4 Wake *_PRW*) |
|  +-- 00:1b.0 HD Audio (<4G) --> ALC662 (AUDIO2, HD_AUDIO1, SPDIF_OUT1, PCBEEP) + HDMI Audio (D3) |
|  +-- 00:1c.0 PCIe RP4* (8086:1c16) -> 02:00.0 Realtek RTL8111 (10ec:8168) -> r8169 eno0 (WOL S4)  |
|  +-- 00:1f.2 SATA AHCI (8086:1c02, map 0x33) -> SATA_0 (P0), SATA_1 (P1), SATA_2 (P4), SATA_3(P5) |
|  +-- 00:1f.3 SMBus (8086:1c22, I/O 0x400) -> DDR3 SPD 0x50 / 0x52 (i2c_i801)                     |
|  +-- 00:1f.0 SPI Bus -> Socketed DIP-8 U3 (W25Q64 8 MiB: IFD 4K + ME 1532K + BIOS 6.5 MiB)        |
|  +-- 00:1f.0 LPC Bus (33 MHz CLK_PCH_PORT80 free-running: GEN_PMCON_1=0x0a10, LPC_EN=0x3c0b)      |
|        +-- 18-pin LPC/TPM1 Header (Port 0x80 POST & optional discrete LPC TPM)                    |
|        +-- U1007 NCT6776F/D Super I/O (PNP 0x2e, ID 0xc333, HWM 0x290)                            |
|              +-- LDN 0x01 LPT1     : DISABLED at boot (CR 0x30=0x00, no PNP0400, no parport0)     |
|              +-- LDN 0x02 COM1     : 0x3f8 IRQ4 -> U11 -> COM1 DB9 (/dev/ttyS0 115200 8N1)        |
|              +-- LDN 0x05 KBC      : 0x60/0x64 IRQ1/12 -> PS/2 Keyboard & Mouse                   |
|              +-- LDN 0x0b HWM/FLED : 0x290 -> CPU_FAN1 (Bank2), CHA_FAN1 (Bank1), PLED- (CR 0xf7) |
+---------------------------------------------------------------------------------------------------+
```

### Hardware <-> Firmware <-> Linux Quick Reference

| Physical Hardware / Connector | Hardware Address / Pin / Net | Coreboot File(s) | Linux Driver / Sysfs Interface |
|---|---|---|---|
| **SPI Flash `U3` (`W25Q64`, DIP-8)** | SPI (`ef 40 17`), IFD `4K` + ME `1532K` + BIOS `6.5M` | `board/Kconfig`, `SMMSTORE` `0x190000` | `flashrom -p internal -c "W25Q64BV/W25Q64CV/W25Q64FV" --ifd -i bios` |
| **COM1 Serial (`U1007` `LDN 0x02` + `U11`)** | I/O `0x3f8`, IRQ `4`, global `CR 0x2a=0x60` | `devicetree.cb` (`2e.2`), `early_init.c` | `/dev/ttyS0` (`PNP0501`, `115200 8N1`) |
| **Parallel Port `LPT1` (`U1007` `LDN 0x01`)** | **Disabled** (`CR 0x30=0x00`, `LPC_EN[2]=0`) | `devicetree.cb` (`2e.1 off`), `mainboard.c` | Disabled (`no PNP0400`, `no parport0`) |
| **Front-Panel `PLED-`, Fans & Sensors** | `0x290`, `PECI0` (pin 115), `LDN 0x0b CR 0xf7` | `mainboard.c`, `smihandler.c`, `early_init.c` | `nct6775` (`/sys/class/hwmon/hwmon0`), `coretemp` |
| **`PCIE1` (`x16`) & `CFG[6:5]` Straps** | `00:01.0` -> `01:00.0`, PEG lanes `0–15` | `cfr.c`, `northbridge.c`, `dsdt.asl` (`PEGP`) | `pcieport`, `nvidia` / IOMMU `DMAR` |
| **Integrated Graphics (`VGA1` + `HDMI1`)** | `00:02.0` (`8086:016a`, `<4G 0xe0000000`) | `gma.c`, `gma-mainboard.ads`, `fb_console.c` | `i915` (`/dev/dri/card1`, `fb0`) |
| **Realtek `RTL8111` GbE LAN & WOL** | `00:1c.0` (`8086:1c16`) -> `02:00.0` (`10ec:8168`) | `devicetree.cb` (`pcie_rp4`), `dsdt.asl` (`RP01`) | `r8169` (`eno0` DHCP, `ethtool wol`, `/proc/acpi/wakeup`) |
| **HD Audio (`ALC662` + HDMI DDPB)** | `00:1b.0` (`<4G 0xdebfc000`), Codecs `0` & `3` | `hda_verb.c`, `bd82x6x/azalia.c` | `snd_hda_intel`, `snd_hda_codec_alc662` |
| **UEFI CFR NVRAM Options (All 9 Runtime)** | GUID `ceae4c1d-335b-4685-a4a0-fc4a94eea085` | `cfr.c` (`CFR_OPTFLAG_RUNTIME`), `SMMSTORE` | `/sys/firmware/efi/efivars/*-ceae4c1d-...` |

See [`docs/HARDWARE-MAP.md`](docs/HARDWARE-MAP.md) for the complete `U1` PEG pin table, `PCH GPIO 0..75` map, `U1007` pinout, and VRM chip mapping (`UP701`, `UP751`, `PU6`, `U1016`, `PTU3`, `U1018`).

---

## Verified Hardware Status (`v26.11.2` — `coreboot` `df45ea2c49b4` + EDK2 `f248a68be339`)

Tested via internal `flashrom -p internal -c "W25Q64BV/W25Q64CV/W25Q64FV" --ifd -i bios --noverify-all` on physical ASRock H61M-S1 PLUS (`Intel Xeon E3-1275 v2`, 2× 8 GB DDR3, NVIDIA Tesla P4 in `PCIE1`, Ubuntu 26.04 `7.0.0-43-generic`):

| Subsystem | Observed Hardware Result (`v26.11.2`) |
|---|---|
| **SPI Flash (`W25Q64`)** | `SF: Detected ef 4017` (`8 MiB`), `RW_MRC_CACHE` (`64 KiB`), `SMMSTORE` (`256 KiB` EFI FV), `COREBOOT` (`6.5 MiB`); `VERIFIED` internal flash |
| **Serial & Super I/O (`NCT6776F`)** | `COM1` (`0x3f8` IRQ 4) end-to-end `115200 8N1` (`PNP: 002e.2 enabled`, `PNP0501`); **`LPT1` cleanly disabled** (`PNP: 002e.1 disabled`, `CR30=0x00`, `LPC_EN=0x3c0b`, zero `parport0`); `nct6775` SmartFan IV `Balanced` live |
| **OS Runtime CFR (`efivarfs`)** | All **9 CFR options** exposed in `/sys/firmware/efi/efivars/*-ceae4c1d-335b-4685-a4a0-fc4a94eea085` (`0x00000007` `NV / BS / RT`), verified read/write round-trip + TUI smoke test via `h61_coreboot_config.py` |
| **Memory** | Dual-channel `16 GiB` Kingston `99U5471-040.A00LF` at `666 MHz` (`1332 MT/s`, `1.5 V`, `CL9`); `CONFIG_NATIVE_RAMINIT_IGNORE_XMP_REQUESTED_VOLTAGE=y` enabled |
| **IGD (`00:02.0`, `8086:016a`)** | `< 4 GiB` MMIO (`0xdec00000`/`0xe0000000`): **`libgfxinit` 4K `3840x2160` GOP**, `fb_console` on-screen POST/CBMEM log, EDK2 Setup on HDMI, **zero `i915` forcewake warnings** |
| **Discrete GPU (`01:00.0`, Tesla P4)** | Retains **Above-4G BARs** (`0xfe0000000`/`0xff0000000`), `VT-d`/`DMAR` IOMMU Group 2, `nvidia_vgpu_vfio` MDEV active |
| **Audio (`00:1b.0`, ALC662 + HDMI)** | `< 4 GiB` MMIO (`0xdebfc000`), `codec_mask = 09`: `Realtek ALC662 rev1` (`0x10ec0662`) + `Intel CougarPoint HDMI` (`0x80862805`) |
| **Ethernet (`02:00.0`, RTL8111) & S3** | `r8169` (`eno0` DHCP), `RP01` `S4 *enabled` (`Supports Wake-on: pumbg`), `GEN_PMCON_1=0x0a10`, `LDN 0x0b CR 0xf7` S3 `0.5 Hz` `PLED-` blink |

---

## Configuring Coreboot from Linux (`scripts/h61_coreboot_config.py`) OR UEFI (`ESC`)

### Method A: Directly from Linux (`h61_coreboot_config.py` TUI / CLI)
No external dependencies required (pure Python 3 standard library). Copy [`scripts/h61_coreboot_config.py`](scripts/h61_coreboot_config.py) to the target system (`sudo install -m 0755 scripts/h61_coreboot_config.py /usr/local/bin/h61-coreboot-config`):

```bash
# Interactive 4-tab curses TUI (CFR Options, Power/Wake, Live Sensors, Backup/Flash)
sudo h61-coreboot-config

# Scripted CLI examples
sudo h61-coreboot-config self-test
sudo h61-coreboot-config status
sudo h61-coreboot-config list
sudo h61-coreboot-config set fan_profile quiet
sudo h61-coreboot-config set fb_debug_pause 3s
sudo h61-coreboot-config set dram_max_speed 1600
sudo h61-coreboot-config wol on
sudo h61-coreboot-config backup my-cfr-profile.json
sudo h61-coreboot-config s3 --seconds 15          # Handles NVIDIA procfs suspend automatically
sudo h61-coreboot-config reboot-uefi --now        # Sets BootNext=Boot0000 & reboots to Setup
```

### Method B: Pre-OS UEFI Setup (`ESC`)
Press **`ESC`** during the `5s` EDK2 prompt -> **`Device Manager`** -> **`Coreboot Configuration`**:
- **`System`**: `IGD UMA Size` (`gfx_uma_size`), `DRAM Max Frequency` (`dram_max_speed`), `PCIe x16 Slot Bifurcation` (`peg_bifurcation`), `Hyper-Threading`, `SATA Mode` (`sata_mode`), `NMI`.
- **`Cooling & Display`**: `SmartFan IV Profile` (`fan_profile`: `Balanced`, `Quiet`, `Performance`, `Full Speed`), `Monitor Debug/POST Pause` (`fb_debug_pause`: `0s`, `3s`, `5s`, `10s`).
- **`Power`**: `Restore AC Power Loss` (`power_on_after_fail`).

---

## Building & Assembling Your Full Flashable ROM

### 1. Download Release + Assemble with Your Stock Backup
Download `h61m-s1-plus-coreboot-<tag>-8mb-bios-region.bin` from [**Releases**](../../releases), provide your own stock SPI dump (`4 MiB` or `8 MiB`), and run:

```bash
bash scripts/assemble_full_rom.sh   --stock-dump your_stock_spi_backup.bin   --bios-region h61m-s1-plus-coreboot-v26.11.2-bios-region-6.5mb-no-blobs.bin   --out h61m-s1-plus-8mb-full.rom   --me-cleaner /path/to/me_cleaner.py
```

- Add `--vbt your_extracted_data.vbt` to inject your desktop VBT (`vbt.bin`) into CBFS (pure `libgfxinit` works without VBT; adding VBT matches the hardware-tested build).
- Omit `--me-cleaner` to keep the stock Intel ME untouched (`c9c21e31...`), or keep `--me-cleaner` to strip non-essential partitions and set `AltMeDisable`.

### 2. Build From Source
Inside `coreboot/coreboot-sdk:latest` or a host with Coreboot's Ada-enabled toolchain (`i386-elf-gnatbind`):

```bash
git clone https://github.com/coreboot/coreboot.git
COREBOOT_DIR="$PWD/coreboot" RELEASE_TAG="custom" bash scripts/build.sh
```
