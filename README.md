# ASRock H61M-S1 PLUS — Coreboot + EDK2 UEFI Port

Open-source **Coreboot + EDK2 `UefiPayloadPkg`** board port, Sandy/Ivy Bridge chipset patches, build scripts, hardware bring-up documentation, and automated quarterly release pipeline for the **ASRock H61M-S1 PLUS** motherboard (LGA1155, Intel H61 Express `8086:1c5c`, Nuvoton `NCT6776F/D` Super I/O, Realtek `ALC662`, Realtek `RTL8111`, 8 MiB `W25Q64` SPI flash).

> **Public Releases**: See [**Releases**](../../releases) for pre-built 6.5 MiB open-source Coreboot + EDK2 BIOS-region binaries (`SHA256SUMS.txt` included) and the [`quarterly-release.yml`](.github/workflows/quarterly-release.yml) workflow aligned with upstream Coreboot `YY.03` / `YY.06` / `YY.09` / `YY.12` releases.

---

## Disclaimers (Read Before Use)

1. **Hardware Risk & Recovery**: Flashing motherboard SPI firmware can permanently brick hardware if interrupted or misconfigured. This project is provided **AS IS** with **NO WARRANTY**. Always capture and verify a full-chip stock backup with an external SPI flash programmer (e.g., CH341A / Dediprog / flashrom) before writing any ROM. Never flash raw `coreboot.rom` builds or redistributable BIOS-region slices directly onto the whole chip without assembling them with your stock Intel Flash Descriptor (IFD) and Intel ME via [`scripts/assemble_full_rom.sh`](scripts/assemble_full_rom.sh).
2. **Known Broken, Deferred, or Caveated Items**:
   - **Physical `VGA1` Dual-Head & Physical POST Card Readers**: Pure open-source `libgfxinit` configures simultaneous `HDMI1` + `Analog` pipes (`gma-mainboard.ads` / `Setup_Framebuffer`), `LPT1` is configured at `0x378` SPP (`0xf0=0x38`, `CR 2F=0x03`, `CR 1C=0x80`), and `LPC/TPM1` `CLKOUT_PCI1` gating (`PSEUDO_CLKRUN_EN`) is cleared (`GEN_PMCON_1=0x0a10`), with all registers verified live via `/dev/port` and `lspci`. However, live hardware testing used an `HDMI` monitor (`VGA-1` unplugged) and did not attach a physical DB25 or `LPC/TPM1` POST card display.
   - **ACPI S3 with NVIDIA vGPU Proprietary Driver (`535.309.01`)**: With `NVreg_PreserveVideoMemoryAllocations=1` in Linux, kernel `pm_suspend` requires writing `suspend` to `/proc/driver/nvidia/suspend` before sleeping (otherwise `nvidia` vetoes suspend with `-EIO`). Coreboot S3 suspend (`HWM_DEV` `LDN 0x0b CR 0xf7=0x44` `0.5 Hz` `PLED-` blink) and `rtcwake -m mem` wakeup + resume (`CR 0xf7=0x07` steady `PLED-`) are verified live with the procfs handshake.
   - **PCIe x16 Slot Bifurcation (`2x8` / `1x8+2x4`)**: Exposed in CFR and gated in `early_init.c` / `northbridge.c` (defaulting to `1x16`). On Intel Ivy Bridge LGA1155, physical lane grouping also requires `CFG[6:5]` hardware pin straps; only `1x16` (`PEG10` with Tesla P4) is tested on hardware.
   - **NVIDIA Tesla P4 (`10de:1bb3`)**: Although `PCIEXP_SUPPORT_RESIZABLE_BARS` and `PCIEXP_PLUGIN_SUPPORT` are enabled in Coreboot, the Pascal Tesla P4 card itself does not advertise hardware SR-IOV or Resizable BAR PCIe extended capabilities (vGPU uses `nvidia_vgpu_vfio` MDEV). At `P8` idle, PCIe link trains at `2.5GT/s x16`.
   - **ME-Cleaned Image Hardware Boot**: An 8 MiB `me_cleaner.py -S` image has been built and structurally verified (`AltMeDisable` bit set, `FTPR` RSA signature valid, identical 6.5 MiB BIOS region), but hardware boot testing with the ME-cleaned image is pending compared to the reboot/flash/S3-verified stock-ME 8 MiB image.
   - **DDR3-1600 / 1.65 V XMP Testing**: `CONFIG_NATIVE_RAMINIT_IGNORE_XMP_REQUESTED_VOLTAGE=y` and `Auto` SPD frequency are enabled, while the installed Kingston `99U5471-040.A00LF` pair is `1.5 V` `1333 MT/s` max (running at `666 MHz` / `1332 MT/s` `CL9`). `1600 MT/s` / `1.65 V` XMP DIMMs remain unverified on hardware.
   - **Runtime CBMEM Log in Ubuntu `7.0.0-43-generic`**: Stock kernel builds omit `drivers/firmware/google/` (`memconsole_coreboot` -> `/sys/firmware/log`); early firmware logs are viewable on-screen via `fb_console` (`HDMI`/`VGA`) at boot or captured over `COM1` (`115200 8N1`).
3. **LLM / AI-Assisted Engineering Disclaimer**: Portions of the board port source files, northbridge/southbridge patches, automation utilities, and documentation were authored or refined with **Large Language Model (LLM)** assistance under human supervision, and cross-checked against the ASRock `H61M-VS4 G/A 1.00` boardview, Intel/Nuvoton/Realtek/Winbond datasheets, stock SPI dumps, and live physical hardware telemetry.

---

## Verified Hardware Status (`v26.11.1` — `coreboot` `df45ea2c49b4` + EDK2 `f248a68be339`)

Tested via internal `flashrom -p internal -c "W25Q64BV/W25Q64CV/W25Q64FV" --ifd -i bios --noverify-all` on physical ASRock H61M-S1 PLUS (`Intel Xeon E3-1275 v2`, 2× 8 GB DDR3, NVIDIA Tesla P4 in `PCIE1`, Ubuntu 26.04 `7.0.0-43-generic`):

| Subsystem | Observed Hardware Result (`v26.11.1`) |
|---|---|
| **SPI Flash (`W25Q64`)** | `SF: Detected ef 4017` (`8 MiB`), `RW_MRC_CACHE` (`64 KiB`), `SMMSTORE` (`256 KiB` EFI FV persisting Setup/Boot variables), `COREBOOT` (`6.5 MiB`); `BIOS` region read-write via internal `flashrom` |
| **Memory** | Dual-channel `16 GiB` Kingston `99U5471-040.A00LF` at `666 MHz` (`1332 MT/s`, `1.5 V`, `CL9`); `CONFIG_NATIVE_RAMINIT_IGNORE_XMP_REQUESTED_VOLTAGE=y` enabled |
| **IGD (`00:02.0`, `8086:016a`) & Display** | `< 4 GiB` MMIO clamp (`0xdec00000` / `0xe0000000`) fixes 32-bit `ramstage` truncation: **`libgfxinit` produces 4K `3840x2160` GOP**, `fb_console` renders Coreboot POST/CBMEM log on monitor, EDK2 Setup/ConOut visible on HDMI, and **Linux `i915` boots/resumes with ZERO `forcewake` timeout errors** |
| **Discrete GPU (`01:00.0`, Tesla P4)** | Retains **Above-4G BARs** (`0xfe0000000` 256M, `0xff0000000` 32M) while bus-0 chipset BARs stay `< 4 GiB`; VT-d/DMAR IOMMU group 2, `nvidia_vgpu_vfio` MDEV active |
| **Audio (`00:1b.0`, ALC662 + HDMI)** | `< 4 GiB` MMIO (`0xdebfc000`) fixes HDA init (`codec_mask = 09`): `Realtek ALC662 rev1` (`hwC0D0`: `0x10ec0662`) + `Intel CougarPoint HDMI` (`hwC0D3`: `0x80862805`) |
| **Ethernet (`02:00.0`, RTL8111)** | `r8169` (`RTL8168evl`), `1000Mb/s Full`, MSI-X IRQ 29, `ASPM Disabled`, persistent DHCP on `eno0`, ACPI `RP01 S4 *enabled` (`Supports Wake-on: pumbg`) |
| **Super I/O (`NCT6776F/D`)** | `COM1` (`0x3f8` IRQ 4) end-to-end `115200 8N1`, `LPT1` (`0x378` SPP `0xf0=0x38`, `CR 2F=0x03`, `CR 1C=0x80`), `LPC/TPM1` free-running clock (`GEN_PMCON_1=0x0a10`), `nct6775` `hwmon` (`PECI0` SmartFan IV CFR profiles) |
| **S3 Suspend/Resume & Wake** | Verified live via `rtcwake -m mem -s 12`: `smihandler.c` sets `HWM_DEV` `LDN 0x0b CR 0xf7=0x44` (`0.5 Hz` `PLED-` blink in S3), `early_init.c` restores `0x07` on resume; `gpe0_en=0x2a40` + `PEGP`/`RP01`/`RP04`/`EHC1`/`EHC2` `_PRW` S4 wakeup enabled |

---

## Configuring the BIOS (`ESC` -> EDK2 / Coreboot CFR Setup)

1. Attach an `HDMI` or `VGA` monitor + keyboard, and/or connect a `115200 8N1` serial console to `COM1` (`0x3f8`). During early boot, `fb_console` displays the Coreboot POST code, hardware summary, and CBMEM log tail on the monitor (default `3s` pause) before handing off to EDK2 UEFI (`-D BOOTSPLASH_IMAGE=FALSE`).
2. Press **`ESC`** during the `5s` boot prompt to enter **EDK2 Boot Manager** -> **`Coreboot Configuration`** (persisted in `256 KiB` `SMMSTORE`). From Linux UEFI, run `sudo efibootmgr -n 0000 && sudo reboot` when `Boot0000` is `Enter Setup`.
3. Available CFR Menus (`cfr.c`):
   - **`System`**: `IGD UMA Size` (`gfx_uma_size`), `DRAM Max Frequency` (`dram_max_speed`: `Auto`, `DDR3-1600`, `DDR3-1333`, `DDR3-1066`), `PCIe x16 Slot Bifurcation` (`peg_bifurcation`: `1x16` default, `2x8`, `1x8+2x4` with hardware `CFG[6:5]` strap note), `Hyper-Threading`, `SATA Mode` (`AHCI`/`IDE`), `NMI`.
   - **`Cooling & Display`**: `SmartFan IV Profile` (`fan_profile`: `Balanced`, `Quiet`, `Performance`, `Full Speed` for `CPU_FAN1` + `CHA_FAN1`), `Monitor Debug/POST Pause` (`fb_debug_pause`: `0s`, `3s`, `5s`, `10s`).
   - **`Power`**: `Restore AC Power Loss` (`power_on_after_fail`).

---

## Useful Coreboot Software & Hardware Features Available for Further Expansion

| Category | Option / Feature | Purpose & Use Case |
|---|---|---|
| **Security & Integrity** | `vboot` Verified Boot (`CONFIG_VBOOT`) + Coreboot measured boot | Cryptographically sign RW/RO firmware stages with automatic recovery fallback if an update fails |
| **Security** | **Heads** or **LinuxBoot (`u-root` / `kexec`)** payload | Replace EDK2 with a verified Linux kernel + initramfs in flash for fast kexec and minimal UEFI attack surface |
| **Security** | Descriptor lock (`ifdtool -l` `FLMSTR` lock) | Prevent internal OS `flashrom` overwrites to IFD/BIOS regions once testing stabilizes |
| **Recovery / Boot** | **Dual Payload in CBFS (`SeaBIOS` + `EDK2` / `iPXE`)** | Add Legacy BIOS CSM or network iPXE ROM alongside EDK2 on the spacious 6.5 MiB CBFS (`~4.5 MiB` currently free) |
| **Diagnostics** | `cbmemc` / `memconsole` + **`nvramcui` / `coreinfo` / `Memtest86+`** | Bundle standalone hardware diagnostics directly inside the 8 MiB SPI flash |

---

## Power Regulation Architecture (Boardview Verified)

Inspection of the ASRock `H61M-S1 PLUS R1.01` (`H61M-VS4 G/A 1.00`) boardview confirms **active switching and linear analog controllers**, **not** passive regulation and with **zero programmable/flashable VRM firmware**:

- **`UP701` (Richtek `RT8876`-series QFN-56 VR12/SVID PWM Controller)**: Integrated 3-phase drivers (`UGATE1..3`, `PHASE1..3`, `LGATE1..3`, `ISEN1..3`) regulate CPU **`VCORE`** from `+12V` under dynamic **Intel SVID** control (`VR_VIDCLK`, `VR_VIDSOUT`, `VR_VIDALERT#`), plus thermal/current telemetry (`VRHOT#`, `TSEN`, `IMON`, `VR_RDY`).
- **`UP751` (Richtek `RT9624` DFN-8 driver)**: Driven by `UP701` `PWMA` (`RT8876_PWMA`) to regulate the single **`VAXG`** (Intel HD Graphics) phase.
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
bash scripts/assemble_full_rom.sh   --stock-dump your_stock_spi_backup.bin   --bios-region h61m-s1-plus-coreboot-v26.11.1-8mb-bios-region.bin   --out h61m-s1-plus-8mb-full.rom   --me-cleaner /path/to/me_cleaner.py
```

- Add `--vbt your_extracted_data.vbt` to inject your desktop VBT (`vbt.bin`) into CBFS (pure `libgfxinit` works without VBT; adding VBT matches the hardware-tested configuration).
- Omit `--me-cleaner` to keep the stock Intel ME untouched (`c9c21e31...`), or keep `--me-cleaner` to strip unneeded partitions and set `AltMeDisable`.

### 2. Build From Source
Inside `coreboot/coreboot-sdk:latest` or a host with Coreboot's Ada-enabled toolchain (`i386-elf-gnatbind`):

```bash
git clone https://github.com/coreboot/coreboot.git
COREBOOT_DIR="$PWD/coreboot" RELEASE_TAG="custom" bash scripts/build.sh
```

See [`BLOBS.md`](BLOBS.md) for all blob links/checksums and [`docs/HARDWARE-REPORT.md`](docs/HARDWARE-REPORT.md) for complete hardware logs.
