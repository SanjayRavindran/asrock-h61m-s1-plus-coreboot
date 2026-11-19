# ASRock H61M-S1 PLUS — Coreboot Implementation & Hardware Bring-Up Report

## Overview

This document records the Coreboot + EDK2 `UefiPayloadPkg` port, build artifacts, hardware bring-up logs, peripheral/VRM/microcode audits, Linux OS configuration, and public GitHub release setup for the **ASRock H61M-S1 PLUS** motherboard (`H61M-VS4 G/A 1.00` / `R1.01` boardview, Xeon E3-1275 v2, H61 `8086:1c5c`, NCT6776F/D Super I/O, ALC662, Realtek RTL8111, NVIDIA Tesla P4 in `PCIE1`).

- **Public GitHub Repository**: [SanjayRavindran/asrock-h61m-s1-plus-coreboot](https://github.com/SanjayRavindran/asrock-h61m-s1-plus-coreboot) (Release `v26.11` + automated quarterly Coreboot release workflow)
- **Build Host**: Ubuntu 26.04 Coreboot build host (`~/coreboot-work/h61m-s1-plus`, branch `h61m-s1-plus-port`, pinned Coreboot commit `df45ea2c49b4c7f6a1d2a969934cf6c6a2cb9018`)
- **Payload**: EDK2 `UefiPayloadPkg` (`https://github.com/mrchromebox/edk2`, commit `f248a68be339831b69a880d9c932a6a3cf3c461a`, `CONFIG_EDK2_RELEASE=y` + `CONFIG_EDK2_BOOT_MANAGER_ESCAPE=y`)
- **Authoritative Evidence & Captures**:
  - Boardview: [`H61M-S1+/ASROCK H61M-S1 PLUS R1.01 70-MXGU40-A01 (BOARDVIEW).fz`](H61M-S1+/ASROCK%20H61M-S1%20PLUS%20R1.01%2070-MXGU40-A01%20(BOARDVIEW).fz)
  - Pre-flash porting dossier & register dumps: [`H61M-S1+/bios_porting_documentation.md`](H61M-S1+/bios_porting_documentation.md), [`inputs/nct6776-dump.txt`](inputs/nct6776-dump.txt)
  - v1 4 MiB hardware boot log: [`logs/coreboot-bootlog-clean.txt`](logs/coreboot-bootlog-clean.txt)
  - v2 8 MiB end-to-end reboot capture (`115200 8N1`): [`logs/coreboot-v2-full-bootlog.txt`](logs/coreboot-v2-full-bootlog.txt)
  - Post-reboot full peripheral & SPD review: [`logs/peripheral-review-v2.txt`](logs/peripheral-review-v2.txt)
  - Earlier v2 diagnostics: [`logs/serial-diag-v2.txt`](logs/serial-diag-v2.txt), [`logs/serial-diag-v2-plat.txt`](logs/serial-diag-v2-plat.txt), [`logs/serial-post-config-v2.txt`](logs/serial-post-config-v2.txt), [`logs/serial-net-dhcp-v2.txt`](logs/serial-net-dhcp-v2.txt)

> **Hardware Test Status (2026-11-19): Booted, Reboot-Verified & End-to-End Serial Confirmed (v2 8 MiB ROM).**
> `h61` cleanly cold/warm reboots across Coreboot v2 -> EDK2 UEFI -> GRUB -> Ubuntu (`Linux 7.0.0-43-generic`) with full `115200 8N1` `COM1`/`ttyS0` console & login prompt, permanent DHCP on `eno0` (`192.168.1.24`), working HDMI display (`00:02.0` `i915`), dual-channel 16 GiB DDR3 (`1332 MT/s` matching DIMM SPD max), `ALC662` + HDMI audio, VT-d/IOMMU, Tesla P4 (`86.04.8C.00.10` VBIOS, Above-4G BARs, MDEV), and autoloaded `NCT6776` `hwmon` sensors. The ME-cleaned 8 MiB ROM (`outputs/h61m-s1-plus-coreboot-8mb-full-mecleaned.rom`) is assembled and verified with `me_cleaner -c`, `ifdtool`, and `cbfstool`, awaiting first flash/boot test on hardware.

---

## Output Firmware Artifacts & Integrity Hashes

`outputs/` has been cleaned to retain only the two flash-ready 8 MiB full-chip ROM images. The stock 4 MiB backup remains immutable at [`H61M-S1+/h61m-s1-plus-read0.bin`](H61M-S1+/h61m-s1-plus-read0.bin).

| Artifact | Path | Size (Bytes) | SHA-256 | Hardware Status |
|---|---|---|---|---|
| **v2 Full 8 MiB ROM (Stock ME)** | [`outputs/h61m-s1-plus-coreboot-8mb-full.rom`](outputs/h61m-s1-plus-coreboot-8mb-full.rom) | 8,388,608 | `0E7CD411ACD79A9246C9F95BAF5B717F5A9BFDEE3673AC56746E9FA4A7EAB175` | **Active flashed & reboot-verified** |
| **v2 Full 8 MiB ROM (ME-Cleaned `-S`)** | [`outputs/h61m-s1-plus-coreboot-8mb-full-mecleaned.rom`](outputs/h61m-s1-plus-coreboot-8mb-full-mecleaned.rom) | 8,388,608 | `87F30AB1139F6690DE6CD0B52784C0C15484C56DE6A23B8A2F8C789896688488` | Structurally verified (`AltMeDisable` set, FTPR RSA valid, identical 6.5 MiB BIOS region `F288F84F...`); **not yet boot-tested on hardware** |
| Stock 4 MiB Full-Chip Backup | [`H61M-S1+/h61m-s1-plus-read0.bin`](H61M-S1+/h61m-s1-plus-read0.bin) | 4,194,304 | `27CB55B24A644EB664790313631FD9AB681398E4A3EA9EC990D367F5539405BB` | Immutable stock AMI P1.10 backup |
| Preserved Stock IFD (`0x000000–0x000fff`) | Inside stock / full ROMs | 4,096 | `B751064C357C3A2028C784E1F183C096CD250733351FC1985B767F19E7B164CC` | Unchanged byte-for-byte |
| Preserved Stock ME (`0x001000–0x17ffff`) | Inside `...-8mb-full.rom` | 1,568,768 | `C9C21E3144B7211DF19AC52BDECBE4DFD504C2F139C2DB6D94728DF8226C93DF` | Unchanged `8.1.20.1336` in stock-ME build |
| v2 6.5 MiB BIOS Region Slice | Embedded (`0x180000–0x7fffff`) | 6,815,744 | `F288F84F32828A4F22CB742749289FC14AC7BF3B9C1DBB0BE46E1F4DCB9F6EBA` | Identical in both 8 MiB full ROMs |

Exported diffs and config: [`coreboot_diff.patch`](coreboot_diff.patch), [`h61m-s1-plus/.config`](h61m-s1-plus/.config).

---

## v1 -> v2 Coreboot Changes & Live Boot Verification

1. **8 MiB Flash Sizing (`Kconfig`)**: Switched from 4 MiB to `BOARD_ROMSIZE_KB_8192` + `CBFS_SIZE=0x680000` (`SMMSTORE_SIZE=0x40000`) to match the physical `W25Q64` (`SF: Detected ef 4017 with sector size 0x1000, total 0x800000`).
2. **IGD + Headless Tesla P4 Coexistence (`src/northbridge/intel/sandybridge/early_init.c`, `.config`)**:
   - Enabled `CONFIG_ONBOARD_VGA_IS_PRIMARY=y` and `CONFIG_GENERIC_LINEAR_FRAMEBUFFER=y` (resolving v1's `Disabling IGD.` when Tesla P4 occupied `PCIE1`).
   - Verified in [`logs/coreboot-v2-full-bootlog.txt`](logs/coreboot-v2-full-bootlog.txt): `SA: CAPID0_A=e200e292 CAPID0_B=164000d0 DEVEN_pre=00000019 DEVEN_post=00000019 GGC=0028`, `SA: IGD 00:02.0 MMCONF=016a8086 CF8=016a8086`, `GMA: Found valid VBT in CBFS`, `IGD decoded, subtracting 32M UMA and 2M GTT`, and `IGD OPREGION 9. 0x7fe56000`.
3. **RAM Frequency Scaling & SPD Ground Truth (`cfr.c`, `raminit.c`, `raminit_common.c`, `raminit_native.c`)**:
   - Removed artificial frequency clamping and exposed `dram_max_speed` in CFR (`Auto (SPD/JEDEC)`, `DDR3-1600`, `DDR3-1333`, `DDR3-1066`).
   - Hardware `decode-dimms` + `i2cdump` on `0-0050`/`0-0052` confirm the two installed 8 GB Dual-Rank Kingston `99U5471-040.A00LF` modules have an SPD **Maximum module speed of `1333 MT/s` (`PC3-10600`, `tCK = 1.500 ns`, `1.5 V`)** with no higher JEDEC/XMP profile. Coreboot trains and runs them at `Selected DRAM frequency: 666 MHz`, `Selected CAS latency: 9T` (`Configured Memory Speed: 1332 MT/s`). A genuine DDR3-1600 (`tCK = 1.250 ns`) stick scales automatically under `Auto`.
4. **PCIe Capabilities (`.config`)**: Enabled `CONFIG_ALWAYS_ALLOW_ABOVE_4G_ALLOCATION=y`, `CONFIG_PCIEXP_PLUGIN_SUPPORT=y`, `CONFIG_PCIEXP_SUPPORT_RESIZABLE_BARS=y` (`bits=34`), `CONFIG_PCIEXP_ASPM=y`, `CONFIG_PCIEXP_CLK_PM=y`, `CONFIG_PCIEXP_COMMON_CLOCK=y`, `CONFIG_PCIEXP_LANE_ERR_STAT_CLEAR=y`, and hotplug options.
5. **LPT1 POST Mode (`early_init.c`, `devicetree.cb`, `post.c`)**: Switched `LDN 0x01` to SPP (`0x38`, `drq=4`) with `__ROMSTAGE__` re-init and a `STROBE#` pulse in `mainboard_post()` (further LPT POST card testing deferred per user).

---

## Post-Reboot Peripheral Verification ([`logs/peripheral-review-v2.txt`](logs/peripheral-review-v2.txt))

- **Serial Console**: End-to-end `115200 8N1` confirmed across Coreboot (`ttyS0` `0x3f8` IRQ 4) -> EDK2 -> GRUB -> kernel (`console=tty0 console=ttyS0,115200n8`) -> `serial-getty@ttyS0` (`speed 115200 baud`).
- **Networking (`eno0`, `02:00.0`, `10ec:8168`, `r8169`)**: Permanently switched to DHCP on `eno0` (`192.168.1.24/24`, `1000Mb/s Full`, `Link detected: yes`, `ASPM Disabled`, `MSI-X` IRQ 29, `br0` removed, `ssh.socket` active).
- **Graphics & Display (`00:02.0`, `8086:016a`)**: `i915` bound, `card0-HDMI-A-1:connected`, `/dev/fb0` active. *(Logs non-fatal Ivybridge `render: timed out waiting for forcewake ack request` / `No MT forcewake available`.)*
- **Audio (`00:1b.0`, `8086:1c20`)**: `HDA-Intel` (`card 0`) with `hwC0D0` (`Realtek ALC662 rev1` line/mic/front-panel/S/PDIF) and `hwC0D3` (HDMI audio `pcmC0D3p`, `pcmC0D7p`, `pcmC0D8p`).
- **Tesla P4 (`01:00.0`, `10de:1bb3`) & VT-d**: `DMAR` active (`x2apic` + queued invalidation, IOMMU group 2), Above-4G BARs (`0xfe0000000` 256M, `0xff0000000` 32M), `nvidia` `535.309.01` + `nvidia_vgpu_vfio` MDEV loaded (`VBIOS 86.04.8C.00.10`). *Note: Pascal Tesla P4 advertises neither hardware SR-IOV nor Resizable BAR PCIe caps and idles at `P8` `LnkSta: 2.5GT/s x16`.*
- **Super I/O Sensors (`NCT6776F/D`)**: `i2c-dev` + `nct6775` autoloaded via `/etc/modules-load.d/h61m-s1-plus-coreboot.conf`; `hwmon0` (`nct6776` at `0x2e:0x290`) reports live fans (`fan1=4821 RPM`, `fan2=1724 RPM`), board/aux temps (`33.0 °C`, `33.5 °C`), and rail voltages with zero ACPI resource conflicts (`hwmon1` `coretemp` `36–40 °C`).
- **USB, Storage, Parallel, PS/2**: `ehci-pci` #1/#2 (`Bus 001`/`002`, Keychron V6 detected), `ahci` `00:1f.2` (`ata1` `EVM SSD 238.5G` `3.0 Gbps` `UDMA/133`), `parport0` (`0x378` IRQ 5), `i8042` (`IRQ 1/12`).

---

## Power Regulation Architecture (Boardview `H61M-VS4 G/A 1.00`)

Power regulation on the H61M-S1 PLUS uses **active switching and linear analog controllers** with **no flashable VRM firmware**:

- **CPU Core (`VCORE`, 3 phases) + Integrated Graphics (`VAXG`, 1 phase)**:
  - **`UP701` (Richtek `RT8876`-series QFN-56 VR12/SVID PWM controller)**: Integrates 3 internal MOSFET gate drivers for `VCORE` (`UGATE1..3`, `PHASE1..3`, `LGATE1..3`, `ISEN1..3`, `BOOT1..3`) powered by `+12V` and communicates dynamically with the CPU over **Intel SVID** (`VR_VIDCLK`, `VR_VIDSOUT`, `VR_VIDALERT#`), plus thermal/current telemetry (`VRHOT#`, `TSEN`, `IMON`, `VR_RDY`).
  - **`UP751` (Richtek `RT9624` DFN-8 driver)**: Receives PWM channel `RT8876_PWMA` from `UP701` to drive the single `VAXG` (`IGD`) power phase (`VCORE_UGA`, `VCORE_PHASEA`, `VCORE_LGA`).
- **Auxiliary & Memory Rails**:
  - **`PU6` (SOIC-8 synchronous buck controller, `RT9120`-class pinout) + `PQ7`/`PQ8`**: Active switching regulation (`+1.8V_DUAL`).
  - **`U1016` (SOIC-8 synchronous buck controller)**: Active switching regulation for `+1.05V_PCH` (`VTT` / `VCCIO` rail).
  - **`PTU3` (SOIC-8 VTT termination regulator)**: Linear DDR3 termination (`+VTTDDR` derived from `VCCM`).
  - **`U1018` (SOIC-8 dual op-amp)**: Linear drive control for `+VCCSA_DRV` and `+1.8V_PLL_DRV`.
  - **`U1007` (`NCT6776F/D` pins 116–118)**: Exposes `VCCM_OV1..3` open-drain/resistor-divider voltage offset pins (static hardware straps, no PMBus/I2C VRM telemetry or EEPROM).

---

## Peripheral Firmware & Microcode Audit

- **Intel CPU Microcode**: Bundled `06-3a-09` (Ivy Bridge E1, rev `0x21`, date `0x02132019`) and `06-2a-07` (Sandy Bridge D2, rev `0x2f`, date `0x02172019`) in Coreboot `3rdparty/intel-microcode` match the **latest revisions** in `intel/Intel-Linux-Processor-Microcode-Data-Files` (confirmed via `gh api`). *(Linux's `SRBDS: Vulnerable: No microcode` is expected hardware behavior for Ivy Bridge).*
- **Intel ME (`8.1.20.1336`)**: Can be kept stock or reduced/disabled via `me_cleaner.py -S` (`outputs/h61m-s1-plus-coreboot-8mb-full-mecleaned.rom`, keeping only `FTPR` `ROMP`+`BUP` with valid RSA signature and `AltMeDisable` set).
- **Realtek `r8169` (`02:00.0`, XID `2c9`)**: Loads `rtl_nic/rtl8168e-3.fw` from Linux `linux-firmware` (no Coreboot CBFS LAN firmware required; board has no LAN SPI EEPROM).
- **NVIDIA Tesla P4**: Runs onboard SPI VBIOS `86.04.8C.00.10`.
- **ALC662, NCT6776F/D, H61 PCH, VRMs**: No field-updatable firmware.

---

## Known Caveats & Deferred Items

1. **ME-Cleaned ROM Hardware Boot Test**: Verified statically (`me_cleaner -c`, `ifdtool`, `cbfstool`); flash and cold-boot test pending when ready to switch from stock ME.
2. **Ubuntu Kernel `7.0.0-43-generic` Gaps**: `drivers/firmware/google/` (`memconsole_coreboot` -> `/sys/firmware/log`) and `cbmem` are absent; capture Coreboot logs via `COM5`. Host `nvidia-smi` also shows a pre-existing OS mismatch (`580.178.04` tool vs `535.309.01` driver).
3. **1600 MT/s DDR3 & LPT POST Card**: Current dual-DIMM Kingston kit is rated `1333 MT/s` max; re-testing a true `1600 MT/s` stick and troubleshooting LPT1 DB25 POST cards remain optional future items.
