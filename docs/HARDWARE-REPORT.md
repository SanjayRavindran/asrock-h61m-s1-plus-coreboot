# ASRock H61M-S1 PLUS — Coreboot Implementation & Hardware Bring-Up Report

## Overview

This document records the Coreboot + EDK2 `UefiPayloadPkg` port, build artifacts, hardware bring-up logs, peripheral/VRM/microcode audits, Linux OS configuration, and public GitHub release setup for the **ASRock H61M-S1 PLUS** motherboard (`H61M-VS4 G/A 1.00` / `R1.01` boardview, Xeon E3-1275 v2, H61 `8086:1c5c`, NCT6776F/D Super I/O, ALC662, Realtek RTL8111, NVIDIA Tesla P4 in `PCIE1`).

- **Public GitHub Repository**: [SanjayRavindran/asrock-h61m-s1-plus-coreboot](https://github.com/SanjayRavindran/asrock-h61m-s1-plus-coreboot) (`v26.11.1` latest + `v26.11` initial + automated quarterly release workflow)
- **Build Host**: Ubuntu 26.04 Coreboot build host (`~/coreboot-work/h61m-s1-plus`, branch `h61m-s1-plus-port`, pinned Coreboot commit `df45ea2c49b4c7f6a1d2a969934cf6c6a2cb9018`)
- **Payload**: EDK2 `UefiPayloadPkg` (`https://github.com/mrchromebox/edk2`, commit `f248a68be339831b69a880d9c932a6a3cf3c461a`, `CONFIG_EDK2_RELEASE=y`, `CONFIG_EDK2_BOOT_MANAGER_ESCAPE=y`, `-D BOOTSPLASH_IMAGE=FALSE`, `5s` boot timeout)

---

## v26.11.1 (`v3`) Verified Fixes & Hardware Measurements

> **Hardware Test Status (`v26.11.1` 8 MiB ROM): Internal `flashrom` Flashed, Reboot-Verified, S3 Suspend/Resume Verified, UEFI Monitor Setup Verified.**

### 1. Root-Cause Fix for Above-4G 32-Bit `ramstage` Truncation (`gma.c`, `me.c`, `azalia.c`, `smbus.c`)
- **Problem**: Coreboot `ramstage` on Sandy/Ivy Bridge is `x86_32`. With `CONFIG_ALWAYS_ALLOW_ABOVE_4G_ALLOCATION=y`, `resource_allocator_v4` placed bus-0 64-bit BARs (`00:02.0` IGD `0x0fffc00000`/`0x0fd0000000`, `00:16.0` MEI1 `0x0fffafa000`, `00:1b.0` HDA `0x0fffafc000`, `00:1f.3` SMBus `0x0fffafb000`) above 4 GiB, causing 32-bit drivers and Ada `libgfxinit` to hit SPI flash MMIO instead of hardware (`GT init timeout`, `lightup_ok=0` blank UEFI monitor, `i915` Ivybridge `forcewake` timeout, `Azalia` codec `0x38a04bdd`, `3801 ms` `MEI1` stall).
- **Fix & Verified Result**: Clamped `IORESOURCE_MEM` `res->limit <= 0xffffffffULL` in `.read_resources` for those 4 bus-0 devices while leaving `CONFIG_ALWAYS_ALLOW_ABOVE_4G_ALLOCATION=y` intact for discrete PCIe add-in cards:
  - `01:00.0` (Tesla P4): `BAR14` `0x0fe0000000` (256 MiB) & `BAR1C` `0x0ff0000000` (32 MiB) stay **Above 4 GiB**.
  - `00:02.0` (IGD): `0xdec00000` / `0xe0000000` (`libgfxinit` initializes `3840x2160` 32bpp GOP framebuffer; **zero** `GT init timeout`; **zero** Linux `i915` forcewake warnings!).
  - `00:1b.0` (Azalia): `0xdebfc000`, `codec_mask = 09`, clean init for `Realtek ALC662 rev1` (`0x10ec0662`) and `Intel CougarPoint HDMI` (`0x80862805`).
  - `00:16.0` (MEI1): `0xdebf7000`, finishes in `137 ms` (down from `3801 ms`).

### 2. On-Screen Debug/POST Console & UEFI Monitor Display (`fb_console.c`, `-D BOOTSPLASH_IMAGE=FALSE`)
- `fb_console.c` renders the Coreboot CBMEM console tail, latest `POST: 0xXX`, active SmartFan IV profile, PEG bifurcation mode, and GOP geometry (`3840x2160 @ 0xe0000000`) onto the `libgfxinit` linear framebuffer at `BS_PAYLOAD_LOAD` (`BS_ON_ENTRY`) with a CFR-configurable pause (`fb_debug_pause`: `0s`/`3s`/`5s`/`10s`), followed cleanly by EDK2 GOP `ConOut` & UEFI Setup (`Boot0000* Enter Setup`).

### 3. `LPC/TPM1` Clock (`CLKOUT_PCI1`), `LPT1` POST, S3 `PLED-`, & Wake-on-LAN / USB Wake
- **`LPC/TPM1` & `LPT1`**: `mainboard.c` clears `CLKRUN_EN | PSEUDO_CLKRUN_EN` (`00:1f.0 GEN_PMCON_1 = 0x0a10`), keeping `CLK_PCH_PORT80` (`CLKOUT_PCI1` -> `LPC/TPM1` pin 1) free-running alongside `LPT1` (`0x378`, `CR 2F=0x03`, `CR 1C=0x80`, `LDN 0x01 CR f0=0x38`, `RCBA_GCS=0x00000c21`, `LPC_EN=0x3c0f`).
- **S3 `PLED-` Fix (`smihandler.c` & `early_init.c`)**: Switched from broken `LDN 0x08 CR 0xf5` (WDT1) to hardware Front Panel Green LED register `HWM_DEV` `LDN 0x0b CR 0xf7` (`0x44` = `0.5 Hz` blink with `GRN_LED_RST#=1` in S3; `0x00` in S4/S5; `early_init.c` restores `0x07` steady ON on both cold boot and S3 resume).
- **ACPI Wake (`devicetree.cb` + `dsdt.asl`)**: Set `register "gpe0_en" = "0x00002a40"` and added `Name (_PRW, Package () { 0x09, 4 })` on `PEGP`, `RP01`, `RP04`. Linux `/proc/acpi/wakeup` reports `PEGP S4 *enabled`, `RP01 S4 *enabled pci:0000:00:1c.0` (RTL8111 `02:00.0`, `Supports Wake-on: pumbg`), `EHC1 S4 *enabled`, `EHC2 S4 *enabled`.
- **Live S3 Suspend/Resume Result**: Verified with `rtcwake -m mem -s 12` (using `/proc/driver/nvidia/suspend` procfs handshake for `NVreg_PreserveVideoMemoryAllocations=1`): Coreboot executes S3 resume path (`OS waking vector is 0x00099200` -> `POST: 0xfd`), Linux resumes cleanly with continuous uptime, zero `i915` forcewake warnings post-S3, and `LDN 0x0b CR 0xf7` restored to `0x07`.

### 4. Firmware Features & Checksums (`v26.11.1`)
- **Release `v26.11.1` BIOS Region (VBT-free)**: `h61m-s1-plus-coreboot-v26.11.1-8mb-bios-region.bin` (`6,815,744` B, SHA-256 `59197b481373b5aa0cd99a544f96828bbc607353f0835fbd180de1a697b82785`).
- **Hardware-Verified 8 MiB Full ROM (Stock ME + VBT)**: SHA-256 `823ad5faa84a35d87d66e3f13b3c9983dfcdf6956646144b635168defc449190` (`0x180000..0x7fffff` BIOS region `c90ac66db8ab3e6656a054bdd274d2b4ccfc9df327e85152125b24ee994f7d54`).
- **Structurally Verified 8 MiB ME-Cleaned ROM (`me_cleaner -S`)**: SHA-256 `dac4580c646398cae66ff37b1a814cfa50aa336532c67f737ef7232c6bf69f85` (`AltMeDisable` set, `FTPR` RSA valid, identical BIOS region `c90ac66d...`).

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
