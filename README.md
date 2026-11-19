# ASRock H61M-S1 PLUS — Coreboot + EDK2 UEFI Port

Open-source **Coreboot + EDK2 `UefiPayloadPkg`** board port, northbridge patches, build scripts, hardware bring-up documentation, and automated quarterly release pipeline for the **ASRock H61M-S1 PLUS** motherboard (LGA1155, Intel H61 Express `8086:1c5c`, Nuvoton `NCT6776F/D` Super I/O, Realtek `ALC662`, Realtek `RTL8111`, 8 MiB `W25Q64` SPI flash).

> **Public Releases**: See [**Releases**](../../releases) for pre-built 6.5 MiB open-source Coreboot + EDK2 BIOS-region binaries (`SHA256SUMS.txt` included) and the [`quarterly-release.yml`](.github/workflows/quarterly-release.yml) workflow aligned with upstream Coreboot `YY.03` / `YY.06` / `YY.09` / `YY.12` releases.

---

## Disclaimers (Read Before Use)

1. **Hardware Risk & Recovery**: Flashing motherboard SPI firmware can permanently brick hardware if interrupted or misconfigured. This project is provided **AS IS** with **NO WARRANTY**. Always capture and verify a full-chip stock backup with an external SPI flash programmer (e.g., CH341A / Dediprog / flashrom) before writing any ROM. Never flash raw `coreboot.rom` builds or redistributable BIOS-region slices directly onto the whole chip without assembling them with your stock Intel Flash Descriptor (IFD) and Intel ME via [`scripts/assemble_full_rom.sh`](scripts/assemble_full_rom.sh).
2. **Known Broken, Deferred, or Caveated Items**:
   - **LPT1 Parallel POST Output**: Switched to SPP mode (`0x38`) with `STROBE#` pulsing in `post.c`, but physical DB25 POST card latching reliability remains unverified/deferred (`LPT` header works in Linux as `parport0`).
   - **Intel `i915` Ivybridge Forcewake Warning**: Linux `7.0.0-43-generic` logs non-fatal `[drm] *ERROR* render: timed out waiting for forcewake ack request` / `No MT forcewake available on Ivybridge`; `i915`, `fb0`, and HDMI output still function normally.
   - **NVIDIA Tesla P4 (`10de:1bb3`)**: Although `PCIEXP_SUPPORT_RESIZABLE_BARS` and `PCIEXP_PLUGIN_SUPPORT` are enabled in Coreboot, the Pascal Tesla P4 card itself does not advertise hardware SR-IOV or Resizable BAR PCIe extended capabilities (vGPU uses `nvidia_vgpu_vfio` MDEV). At `P8` idle, PCIe link trains at `2.5GT/s x16`.
   - **ME-Cleaned Image Hardware Boot**: An 8 MiB `me_cleaner.py -S` image has been built and structurally verified (`AltMeDisable` bit set, `FTPR` RSA signature valid, identical 6.5 MiB BIOS region), but hardware boot testing with the ME-cleaned image is pending compared to the reboot-verified stock-ME 8 MiB image.
   - **DDR3-1600 Re-Testing**: Native raminit unclamps SPD frequency via `Auto`, and the installed Kingston `99U5471-040.A00LF` pair runs at its verified `1333 MT/s` (`666 MHz`) SPD maximum. DDR3-1600 DIMMs remain unverified on hardware in v2.
   - **Runtime CBMEM Log in Ubuntu `7.0.0-43-generic`**: Stock kernel builds omit `drivers/firmware/google/` (`memconsole_coreboot` -> `/sys/firmware/log`); capture early firmware logs via `COM1` (`115200 8N1`).
3. **LLM / AI-Assisted Engineering Disclaimer**: Portions of the board port source files, northbridge diagnostic patches, automation utilities, and documentation were authored or refined with **Large Language Model (LLM)** assistance under human supervision, and cross-checked against the ASRock `H61M-VS4 G/A 1.00` boardview, Intel/Nuvoton/Realtek/Winbond datasheets, stock SPI dumps, and live physical hardware telemetry.

---

## Verified Hardware Status (v26.11 Baseline — `coreboot` `df45ea2c49b4` + EDK2 `f248a68be339`)

Tested on physical ASRock H61M-S1 PLUS (`Intel Xeon E3-1275 v2`, 2× 8 GB DDR3, NVIDIA Tesla P4 in `PCIE1`, Ubuntu 26.04 `7.0.0-43-generic`):

| Subsystem | Observed Hardware Result |
|---|---|
| **SPI Flash (`W25Q64`)** | `SF: Detected ef 4017` (`8 MiB`), `RW_MRC_CACHE` (`64 KiB`), `SMMSTORE` (`256 KiB`), `COREBOOT` (`6.5 MiB`) |
| **Memory** | Dual-channel `16 GiB` Kingston `99U5471-040.A00LF` at `666 MHz` (`1332 MT/s`, `1.5 V`, `CL9`, matching SPD max `1333 MT/s`) |
| **IGD (`00:02.0`, `8086:016a`)** | Primary VGA (`ONBOARD_VGA_IS_PRIMARY=y`), `libgfxinit` + framebuffer, `HDMI` monitor active (`i915`, `card0-HDMI-A-1:connected`) |
| **Discrete GPU (`01:00.0`, Tesla P4)** | Coexists with primary IGD; Above-4G BARs (`0xfe0000000` 256M, `0xff0000000` 32M), VT-d/DMAR IOMMU group 2, `nvidia_vgpu_vfio` MDEV active |
| **Ethernet (`02:00.0`, RTL8111)** | `r8169` (`RTL8168evl`), `1000Mb/s Full`, MSI-X IRQ 29, `ASPM Disabled`, persistent DHCP on `eno0` |
| **Audio (`00:1b.0`, ALC662 + HDMI)** | `Realtek ALC662 rev1` (`hwC0D0`: rear/front/S/PDIF/beep) + Intel Display Audio (`hwC0D3`, HDMI `pcm=3,7,8`) |
| **Super I/O (`NCT6776F/D`)** | `COM1` (`0x3f8` IRQ 4) end-to-end `115200 8N1` (Coreboot -> EDK2 -> GRUB -> Linux `ttyS0`), `parport0`, PS/2 KBC, `nct6775` `hwmon` (`temp`/`fan`/`in`) |
| **USB / SATA / Power** | Both `EHCI` controllers active, `AHCI` SATA `3.0 Gbps` (`ata1`), ACPI S0/S3/S4/S5 & `O_PME#` / `PLED-` SMM handlers |

---

## Configuring the BIOS (`ESC` -> EDK2 / Coreboot CFR Setup)

1. Connect a `115200 8N1` serial console (no flow control) to `COM1` (`0x3f8`), or attach a monitor to `HDMI`/`VGA` + USB/PS2 keyboard.
2. Press **`ESC`** during early payload boot (default timeout `2s`) to enter the **EDK2 Boot Manager**. From Linux UEFI you can also request setup on next boot with `sudo efibootmgr -n 0000 && sudo reboot` (when `Boot0000` is `Enter Setup`).
3. Open **`Coreboot Configuration`** (`CONFIG_DRIVERS_OPTION_CFR_ENABLED=y`, persisted in `256 KiB` `SMMSTORE`):
   - **`System`**: `IGD UMA Size` (`gfx_uma_size`), `DRAM Max Frequency` (`dram_max_speed`: `Auto`, `DDR3-1600`, `DDR3-1333`, `DDR3-1066`), `Hyper-Threading`, `SATA Mode` (`AHCI`/`IDE`), `NMI`.
   - **`Power`**: `Restore AC Power Loss` (`power_on_after_fail`).
4. To add new firmware options, edit [`board/src/mainboard/asrock/h61m-s1-plus/cfr.c`](board/src/mainboard/asrock/h61m-s1-plus/cfr.c), rebuild with `scripts/build.sh`, and reflash the BIOS region.

---

## Useful Coreboot Software & Hardware Features Available for Expansion

| Category | Option / Feature | Purpose & Use Case |
|---|---|---|
| **Security & Integrity** | `vboot` Verified Boot (`CONFIG_VBOOT`) + Coreboot measured boot | Cryptographically sign RW/RO firmware stages with automatic recovery fallback if an update fails |
| **Security** | **Heads** or **LinuxBoot (`u-root` / `kexec`)** payload | Replace EDK2 with a verified Linux kernel + initramfs in flash for fast kexec and minimal UEFI attack surface |
| **Security** | Descriptor lock (`ifdtool -l` `FLMSTR` lock) | Prevent internal OS `flashrom` overwrites to IFD/BIOS regions once testing stabilizes |
| **Recovery / Boot** | **Dual Payload in CBFS (`SeaBIOS` + `EDK2` / `iPXE`)** | Add Legacy BIOS CSM or network iPXE ROM alongside EDK2 on the spacious 6.5 MiB CBFS (`~4.5 MiB` currently free) |
| **Diagnostics** | `cbmemc` / `memconsole` + **`nvramcui` / `coreinfo` / `Memtest86+`** | Bundle standalone hardware diagnostics directly inside the 8 MiB SPI flash |
| **Hardware Tuning** | **PCIe x16 Bifurcation (`x8/x8`, `x8/x4/x4`)** in `northbridge` | Add CPU strap/lane-grouping override support for Ivy Bridge Xeon E3 v2 (`PCIE1` carries all 16 CPU PEG lanes) |
| **Hardware Tuning** | **XMP > 1.50 V Support** (`CONFIG_NATIVE_RAMINIT_IGNORE_XMP_REQUESTED_VOLTAGE`) | Allows Sandy/Ivy native raminit to attempt `1.65 V` XMP DDR3 modules (verify `VCCM_OV*` hardware rails first) |
| **Hardware Tuning** | **SmartFan IV Profiles via CFR** (`mainboard.c` + `cfr.c`) | Expose custom temperature thresholds and PWM fan duty curves for `CPU_FAN1` and `CHA_FAN1` in Setup |
| **Power / Thermal** | **Intel ME Cleaning (`me_cleaner -S`)** & **`S3`/`S4` Wake Tuning** | Remove non-essential Intel ME partitions and set `AltMeDisable`, plus tune ACPI S3 wake events (`USB` / `LAN WOL`) |
| **Display** | **`VGA` + `HDMI` Dual-Head Libgfxinit Testing** | Validate simultaneous analog CRT (`VGA1`) + `HDMI1` console/GOP output using pure open-source `libgfxinit` |

---

## Power Regulation Architecture (Boardview Verified)

Inspection of the ASRock `H61M-S1 PLUS R1.01` (`H61M-VS4 G/A 1.00`) boardview confirms **active switching and linear analog controllers**, **not** passive regulation and with **zero programmable/flashable VRM firmware**:

- **`UP701` (Richtek `RT8876`-series QFN-56 VR12/SVID PWM Controller)**: Integrated 3-phase drivers (`UGATE1..3`, `PHASE1..3`, `LGATE1..3`, `ISEN1..3`) regulate CPU **`VCORE`** from `+12V` under dynamic **Intel SVID** control (`VR_VIDCLK`, `VR_VIDSOUT`, `VR_VIDALERT#`), plus thermal/current telemetry (`VRHOT#`, `TSEN`, `IMON`, `VR_RDY`).
- **`UP751` (Richtek `RT9624` DFN-8 Driver)**: Driven by `UP701` `PWMA` (`RT8876_PWMA`) to regulate the single **`VAXG`** (Intel HD Graphics) phase.
- **`PU6` (`RT9120`-class SOIC-8 Synchronous Buck) + `PQ7`/`PQ8`**: Active switching step-down regulator (`+1.8V_DUAL`).
- **`U1016` (SOIC-8 Synchronous Buck)**: Active switching regulator for **`+1.05V_PCH`** (`VTT` / `VCCIO`).
- **`PTU3` (SOIC-8 LDO)**: DDR3 VTT termination regulator (`+VTTDDR` sourced from `VCCM`).
- **`U1018` (SOIC-8 Dual Op-Amp)**: Linear drive regulation for **`+VCCSA_DRV`** and **`+1.8V_PLL_DRV`**.
- **`U1007` (`NCT6776F/D`)**: `VCCM_OV1..3` pins (116–118) provide static resistor-divider voltage offsets; there is no PMBus/I2C VRM controller on SMBus.

---

## Building & Assembling Your Full Flashable ROM

### 1. Download Release + Assemble with Your Stock Backup
Download `h61m-s1-plus-coreboot-<tag>-8mb-bios-region.bin` from [**Releases**](../../releases), provide your own stock SPI dump (`4 MiB` or `8 MiB`), and run:

```bash
bash scripts/assemble_full_rom.sh   --stock-dump your_stock_spi_backup.bin   --bios-region h61m-s1-plus-coreboot-v26.11-8mb-bios-region.bin   --out h61m-s1-plus-8mb-full.rom   --me-cleaner /path/to/me_cleaner.py
```

- Add `--vbt your_extracted_data.vbt` to inject your desktop VBT (`vbt.bin`) into CBFS.
- Omit `--me-cleaner` to keep the stock Intel ME untouched (`c9c21e31...`), or keep `--me-cleaner` to strip unneeded partitions and set `AltMeDisable`.

### 2. Build From Source
Inside `coreboot/coreboot-sdk:latest` or a host with Coreboot's Ada-enabled toolchain (`i386-elf-gnatbind`):

```bash
git clone https://github.com/coreboot/coreboot.git
COREBOOT_DIR="$PWD/coreboot" RELEASE_TAG="custom" bash scripts/build.sh
```

See [`BLOBS.md`](BLOBS.md) for all blob links/checksums and [`docs/HARDWARE-REPORT.md`](docs/HARDWARE-REPORT.md) for complete hardware logs.
