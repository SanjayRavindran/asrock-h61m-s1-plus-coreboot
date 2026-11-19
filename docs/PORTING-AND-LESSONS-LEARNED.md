# ASRock H61M-S1 PLUS — Coreboot Porting History & Lessons Learned

This knowledge base consolidates every hardware discovery, boardview correlation, debugging breakthrough, and Linux integration pitfall uncovered while porting **Coreboot (`df45ea2c49b4`) + EDK2 `UefiPayloadPkg` (`f248a68be339`)** from a stock 4 MiB AMI Aptio `P1.10` BIOS to a verified **8 MiB** open-source firmware (`v26.11.2`).

---

## 1. Pre-Port Reconnaissance & Board Identity

- **Boardview vs Silkscreen Identity**: The authoritative ASRock boardview file `ASROCK H61M-S1 PLUS R1.01 70-MXGU40-A01 (BOARDVIEW).fz` is a zlib-compressed text netlist whose internal title reads `H61M-VS4 G/A 1.00` (dated `2013-03-06`). ASRock reuses the `H61M-VS4` PCB design across `H61M-S1 PLUS`; SMBIOS (`H61MS1P1.10`) and full-chip dumps confirm `H61M-S1 PLUS` with socketed DIP-8 SPI flash (`U3`).
- **Stock 4 MiB Layout (`W25Q32`)**:
  - `IFD` (`0x000000–0x000fff`, 4 KiB)
  - `Intel ME 8.1.20.1336` (`0x001000–0x17ffff`, 1,568,768 B)
  - `BIOS` (`0x180000–0x3fffff`, 2.5 MiB — too tight once debug EDK2 UEFI + `SMMSTORE` + `RW_MRC_CACHE` + Ada `libgfxinit` grew beyond ~2.2 MiB)
- **8 MiB SPI Upgrade (`W25Q64`, `ef 40 17`)**:
  - Migrating `U3` from `W25Q32` (4 MiB) to `W25Q64` (8 MiB) and resizing `FLREG1 = 0x07ff0180` in the IFD expands the `BIOS` region from 2.5 MiB to **6.5 MiB (`0x180000–0x7fffff`)**, giving `256 KiB` `SMMSTORE`, `64 KiB` `RW_MRC_CACHE`, and **`~4.5 MiB` free CBFS** without touching `IFD` or `ME` offsets!
- **Vendor Image Evidence Safety Rule**:
  - Stock `H61MS1P1.10` had `FPT` metadata warnings in UEFITool (`NVCL`/`NVCP`/etc. invalid NVRAM entries) which are normal for live factory dumps and **not** corruption. Extracted VBT (`SNB/IVB-DESKTOP`, `0xf3e` B) or `SBPEI` GPIO tables serve strictly as hardware-wiring clues — never transplant vendor PEI/DXE binaries into Coreboot.

---

## 2. Critical Silicon & Firmware Bugs Solved

### Bug 1: Above-4G 32-Bit `ramstage` Truncation (`gma.c`, `me.c`, `azalia.c`, `smbus.c`)
- **Symptoms**: Enabling `CONFIG_ALWAYS_ALLOW_ABOVE_4G_ALLOCATION=y` (required for the `NVIDIA Tesla P4` `256 MiB` + `32 MiB` 64-bit BARs) caused Coreboot `resource_allocator_v4` (top-down allocation) to place **Bus-0 chipset MMIO BARs above `4 GiB`** (`0x0fffc00000` for IGD `00:02.0`, `0x0fffafa000` for `MEI1` `00:16.0`, `0x0fffafc000` for `Azalia` `00:1b.0`, `0x0fffafb000` for `SMBus` `00:1f.3`).
- **Why It Broke**: Coreboot's Sandy/Ivy Bridge `ramstage` runs in **32-bit x86 protected mode** (`uintptr_t` = 32-bit, flat MMIO access)! Truncating `0x0fffc00000` to 32-bit `0xffc00000` aimed Ada `libgfxinit`, `azalia.c`, and `me.c` straight into the **memory-mapped SPI flash window (`0xff800000–0xffffffff`)**, causing:
  1. Coreboot `GT init timeout` & `lightup_ok=0` -> completely blank UEFI display + Linux `i915` Ivybridge `forcewake` timed-out warnings.
  2. `Azalia: codec_mask = 0` or garbage `0x38a04bdd` -> dead `ALC662` & HDMI audio.
  3. `MEI1` stalling for `3,801 ms` every boot.
- **Root-Cause Fix**: Clamp `IORESOURCE_MEM` `res->limit = min(res->limit, 0xffffffffULL)` inside `.read_resources` in those 4 Bus-0 chipset drivers (`src/northbridge/intel/sandybridge/gma.c` and `src/southbridge/intel/bd82x6x/{me.c,azalia.c,smbus.c}`) while leaving `CONFIG_ALWAYS_ALLOW_ABOVE_4G_ALLOCATION=y` enabled for PCIe bridges/endpoints (`01:00.0` Tesla P4 keeps `0xfe0000000`/`0xff0000000` Above-4G!). Boot results: `00:02.0`=`0xdec00000`/`0xe0000000` (3840×2160 GOP works, zero `i915` forcewake warnings), `00:1b.0`=`0xdebfc000` (`ALC662`+`HDMI`), `00:16.0`=`0xdebf7000` (`137 ms`).

### Bug 2: EDK2 `BOOTSPLASH_IMAGE` Hiding Console Text
- MrChromebox's `UefiPayloadPkg.dsc` defaults to `DEFINE BOOTSPLASH_IMAGE = TRUE` even when `CONFIG_EDK2_BOOTSPLASH_FILE=""` is set! Without `CONFIG_EDK2_CUSTOM_BUILD_PARAMS="-D BOOTSPLASH_IMAGE=FALSE"`, EDK2 hides framebuffer console text. Setting `-D BOOTSPLASH_IMAGE=FALSE` plus `board/fb_console.c` ensures full Coreboot POST + CBMEM log tail and full UEFI setup menus appear natively on HDMI/VGA.

### Bug 3: NCT6776F Global Registers Placed Inside `device pnp 2e.1` (LPT1)
- Coreboot's devicetree compiler only emits PnP register writes for **enabled** (`on`) logical devices! Because the initial `devicetree.cb` placed NCT6776F's 9 global multi-function/clock-mux registers (`irq 0x13..0x2f`, including `0x2a = 0x60` which enables COM1 TX/RX pins!) under `device pnp 2e.1` (LPT1), simply changing `2e.1` to `off` would have stopped `COM1` in `ramstage`. Moving global registers `0x13..0x2f` onto `device pnp 2e.2 on` (**COM1**) keeps `COM1` rock-solid while cleanly disabling `LPT1` (`CR 0x30=0x00`, `#undef NCT6776_SHOW_PP`, `LPC_EN &= ~LPT_LPC_EN`).

### Bug 4: NCT6776F S3 `PLED-` Blink Register (`LDN 0x0b CR 0xf7` vs WDT1 `LDN 0x08 CR 0xf5`)
- An earlier assumption poked `LDN 0x08 CR 0xf5` for front-panel `PLED-` blink — which on NCT6776F is actually `WDT1` configuration, not an LED! Inspection of the NCT6776F datasheet proved `GP10` is muxed to `GRN_LED` (`LDN 0x08 CR 0xf4 = 0x01`), whose blink/state is driven by **Hardware Monitor & Front-Panel LED logical device `LDN 0x0b CR 0xf7`**: `0x07` = active-low steady ON (S0 cold boot & S3 resume in `early_init.c`), `0x44` = `0.5 Hz` blink with `GRN_LED_RST#=1` surviving `LRESET#` during S3 (`smihandler.c`), `0x00` = High-Z off in S4/S5.

### Bug 5: `LPC/TPM1` Pin-1 Clock (`CLK_PCH_PORT80`) Gating & PCIe RP Renumbering
- `bd82x6x` `enable_clock_gating()` sets `CLKRUN_EN` and `PSEUDO_CLKRUN_EN` bits (`GEN_PMCON_1` bits `3:2`), silencing `CLKOUT_PCI1` (`CLK_PCH_PORT80`) on idle LPC cycles. Clearing bits `3:2` in `mainboard.c` (`GEN_PMCON_1=0x0a10`) keeps `CLK_PCH_PORT80` continuously ticking for `LPC/TPM1` readers.
- Also note Cougar Point PCIe Root Port renumbering: when `PCIE2` (`pcie_rp1`) has no card inserted, Coreboot assigns onboard `RTL8111` (`pcie_rp4`, `8086:1c16`) to BDF **`00:1c.0`** (ACPI `RP01`), so `_PRW` for WOL must cover both `RP01` and `RP04` in `dsdt.asl` along with `register "gpe0_en" = "0x00002a40"`.

### Bug 6: Exposing Coreboot CFR Options to Linux (`CFR_OPTFLAG_RUNTIME` + `efivarfs`)
- EDK2 `CfrSetupMenuDxe` (`SetupMenuCfr.c`) sets `EFI_VARIABLE_RUNTIME_ACCESS` **only** when Coreboot's option declares `.flags = CFR_OPTFLAG_RUNTIME`. Without it, `SMMSTORE` variables (`GUID ceae4c1d-335b-4685-a4a0-fc4a94eea085`) are invisible to Linux `/sys/firmware/efi/efivars/`. Adding `CFR_OPTFLAG_RUNTIME` in `cfr.c` and doing a fresh `--ifd -i bios` flash (clearing old `SMMSTORE` once) exposes all 9 `<opt>-ceae4c1d-...` variables cleanly (`0x00000007` = `NV|BS|RT`, 8 bytes `<II`). Linux's `efivarfs` sets `FS_IMMUTABLE_FL` (`----i----`), which must be cleared (`ioctl` / `chattr -i`) before atomic `os.write()` (`write_cfr_option` in `scripts/h61_coreboot_config.py`).

### Bug 7: `savedefconfig` Silently Dropping `# CONFIG_INTEL_GMA_ADD_VBT is not set`
- Because `INTEL_GMA_HAVE_VBT` is selected in `board/Kconfig`, running `make savedefconfig` when `data.vbt` is enabled writes an `INTEL_GMA_ADD_VBT=y` config, whereas stripping `CONFIG_INTEL_GMA_ADD_VBT=y` *without* `# CONFIG_INTEL_GMA_ADD_VBT is not set` causes `olddefconfig` to re-enable it as the default! Public repo `configs/h61m-s1-plus-8mb.defconfig` explicitly keeps `# CONFIG_INTEL_GMA_ADD_VBT is not set`.

---

## 3. Linux OS & Tooling Lessons Learned (`h61`, Ubuntu `7.0.0-43-generic`)

| Area | Symptom / Pitfall | Root Cause & Permanent Fix |
|---|---|---|
| **Netplan NIC Naming (`eno0` vs `br0`)** | Network dropped or failed DHCP after Coreboot migration | Coreboot SMBIOS reports `DeviceName: Ethernet controller`, giving `eno0` (`enp2s0` alt), whereas `01-br0.yaml` referenced non-existent `enp3s0` + competing `enp2s0` alphabetical systemd matching. Fixed permanently via `/etc/netplan/00-installer-config.yaml` matching `macaddress: d0:50:99:7c:84:dd` with DHCP on `eno0`. |
| **NCT6776 `CPUTIN` Anomaly** | `sensors` / `hwmon0` shows `CPUTIN=123.5°C` | Analog `CPUTIN` thermistor pin is floating/unwired on this board; true CPU die temps (`36–45 °C`) arrive over single-wire **`PECI0`** (which drives SmartFan IV in hardware and appears under Linux **`coretemp`** `hwmon1`). `SYSTIN` & `AUXTIN` (`~34 °C`) are wired board thermistors. |
| **ACPI S3 + NVIDIA vGPU `535.309.01`** | Kernel `rtcwake -m mem` fails with `-EIO` (`-5`) | `/etc/modprobe.d/blacklist-nouveau.conf` enables `NVreg_PreserveVideoMemoryAllocations=1`. Kernel expects `echo suspend > /proc/driver/nvidia/suspend` before sleeping and `echo resume > ...` afterward (`h61_coreboot_config.py s3` handles this automatically). |
| **`flashrom v1.6.0` Internal Flashing** | Ambiguous chip error + read-locked ME refusal | `ef 40 17` matches multiple `W25Q64*` entries and `FREG2` (ME) is read-locked. Always pass `-c "W25Q64BV/W25Q64CV/W25Q64FV" --ifd -i bios --noverify-all -w <8mb_full_rom.rom>`. |
| **Windows `COM5` CH340 Driver Bug** | `pyserial` & `.NET SerialPort` fail `SetCommState()` with **Win32 Error 31** | WCH `CH340` Windows driver `3.9.2024.9` rejects full `DCB` writes. Use `.agents/skills/serial-communication/scripts/com_serial.py` (`CreateFileW` + `GetCommState` + conditional `mode COM5`), and single-line base64 `eval` in `serial_exec.py` to survive `sudo tcsetattr(TCSAFLUSH)`. |
| **CBMEM Log on Ubuntu `7.0.0`** | `/sys/firmware/log` absent | Stock Ubuntu kernels disable `CONFIG_GOOGLE_MEMCONSOLE_COREBOOT`; read Coreboot stage logs on monitor via `fb_console.c` at boot or over `COM1` (`115200 8N1`). |
