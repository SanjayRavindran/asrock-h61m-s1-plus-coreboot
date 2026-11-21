---
name: h61m-s1-plus-linux-bringup
description: >-
  Configure and verify Ubuntu Linux on the Coreboot-flashed ASRock H61M-S1 PLUS
  (host h61 via DHCP on eno0 at 192.168.1.24), including h61-coreboot-config TUI/CLI
  10-option CFR management, COM1 115200 8N1 serial console/getty + LPT1 (0x378 parport0)
  enabled, Netplan eno0 DHCP, NCT6776 hwmon sensors, S3 NVIDIA handshake, and
  IGD/Tesla P4 checks. Use after flashing Coreboot, reinstalling Ubuntu, or
  configuring BIOS options from OS.
---

# ASRock H61M-S1 PLUS Linux Bring-Up & Verification (`v26.11.5`)

Use this runbook to verify, configure Coreboot CFR options, or restore OS state on `h61` (`192.168.1.24` via DHCP on `eno0`) over SSH or `COM5` (see `serial-communication` and [serial_exec.py](../serial-communication/scripts/serial_exec.py)).

## 1. OS Runtime BIOS & Hardware Configuration (`h61-coreboot-config`)

[`scripts/h61_coreboot_config.py`](../../../scripts/h61_coreboot_config.py) is installed on `h61` at `/usr/local/bin/h61-coreboot-config` (stdlib-only Python 3 TUI + CLI):

- **All 10 Coreboot CFR options** (`gfx_uma_size`, `dram_max_speed`, `peg_bifurcation`, `hyper_threading`, `sata_mode`, `nmi`, `me_state`, `fan_profile`, `fb_debug_pause`, `power_on_after_fail`) are exposed via `SMMSTORE` under `/sys/firmware/efi/efivars/*-ceae4c1d-335b-4685-a4a0-fc4a94eea085` with attributes `0x00000007` (`NV|BS|RT`, `8` bytes `<II`) and `FS_IMMUTABLE_FL` managed automatically.
- **Secure Boot & NVMe**: `status` and `self-test` inspect `SecureBoot`, `SetupMode`, `VendorKeys`, `PK`/`KEK`/`db`/`dbx` in `efivars` (Microsoft 2011+2023 keys pre-enrolled, disabled by default until enabled under `System Configuration` -> `Secure Boot Configuration`) and any PCIe NVMe controllers (`NvmExpressDxe`).
- **GRUB `fwsetup` / `reboot-uefi`**: With EDK2 patch `0003` (`ResetSystemLib.c` CF9 `0x02 -> 0x06`), selecting **UEFI Firmware Settings** in GRUB or running `sudo h61-coreboot-config reboot-uefi --now` / `systemctl reboot --firmware-setup` automatically hard-resets straight into UEFI Setup without powering off.
- **Note on `me_state`**: Leave `me_state=0` (`Normal`) when booted with locked `FREG2` stock/compat ME (`8.1.20.1336` triggers a harmless ~1.3s `ME_GEN_7` MKHI timeout warning in Coreboot if `me_state=1` is set). Coreboot SMM (`me_smm.c` `RCBA32_OR(FD2, PCH_DISABLE_MEI1)`) already hides PCI `00:16.0` before OS handoff so `lspci -s 00:16.0` is empty in Linux. For physical hardware `AltMeDisable=1` + `124 KiB` stripped ME, flash `w25q64-8mb-minimal-me-full.rom` externally onto socketed `U3`.
- **Common commands**:
  ```bash
  sudo h61-coreboot-config                  # Launch 4-tab interactive curses TUI
  sudo h61-coreboot-config self-test        # Verify 10 efivars, COM1 active, LPT1 active, WOL, hwmon
  sudo h61-coreboot-config status           # Live CPU, DRAM, COM1/LPT1, ACPI wakeups, sensors
  sudo h61-coreboot-config list             # List all 10 CFR options & values
  sudo h61-coreboot-config set fan_profile quiet
  sudo h61-coreboot-config backup /tmp/cfr-profile.json
  sudo h61-coreboot-config wol on
  sudo h61-coreboot-config s3 --seconds 15  # Runs /proc/driver/nvidia/suspend handshake automatically
  sudo h61-coreboot-config reboot-uefi --now
  ```

## 2. COM1 (`115200 8N1`) & LPT1 (`0x378` IRQ 5) Super I/O Verification

Coreboot and EDK2 use `COM1` (`0x3f8`, `/dev/ttyS0`) at `115200 8N1`, and **`v26.11.3` enables `LPT1` (`LDN 0x01`, `0x378`, IRQ 5, SPP `CRf0=0x38`, `PNP0400`)** while keeping LPT1 free for standard parallel devices (`post.c` 0x378 POST writes stay removed; Port `0x80` POST goes only to LPC):

1. `/etc/default/grub.d/99-serial-console.cfg`:
   ```bash
   GRUB_CMDLINE_LINUX="${GRUB_CMDLINE_LINUX} console=tty0 console=ttyS0,115200n8"
   GRUB_TERMINAL="console serial"
   GRUB_SERIAL_COMMAND="serial --speed=115200 --unit=0 --word=8 --parity=no --stop=1"
   ```
   Apply with `sudo update-grub`.
2. `/etc/systemd/system/serial-getty@ttyS0.service.d/10-baud-115200.conf`:
   ```ini
   [Service]
   ExecStart=
   ExecStart=-/usr/sbin/agetty --noreset --noclear --issue-file=/etc/issue:/etc/issue.d:/run/issue.d:/usr/lib/issue.d 115200 - $TERM
   ```
3. Enable for boot **without** restarting inside an active `ttyS0` shell (`sudo systemctl daemon-reload; sudo systemctl enable serial-getty@ttyS0.service ssh.socket`).
4. **Verify LPT1 + COM1 active & LPC Port `0x80` unlocked**:
   - `grep . /sys/bus/pnp/devices/*/id` -> `PNP0400` (`LPT1`), `PNP0501` (`COM1`), `PNP0303`, `PNP0f13`.
   - `sudo grep -iE 'serial|parport|0378|03f8' /proc/ioports` -> `0378-037a : parport0` and `03f8-03ff : serial`.
   - `efibootmgr -v` -> `Boot0001* USB Boot Menu` (`FvFile(eec25bdc-67f2-4d95-b1d5-f81b2039d11d)`, data `USB_ONLY`).

## 3. Netplan NIC Naming & `eno0` DHCP Configuration

- Under Coreboot, onboard Realtek `RTL8111` (`10ec:8168`, `r8169`, MAC `d0:50:99:7c:84:dd`) stays `eno0` (`192.168.1.24/24`, matched by MAC in `/etc/netplan/00-installer-config.yaml`). Note: if an add-in PCIe NIC is installed in `PCIE2` (`00:1c.0`, e.g., Intel `I226-V` at `02:00.0`), Coreboot enumerates onboard `RTL8111` (`pcie_rp4` `00:1c.3`) at `03:00.0` (`RP04`), while systemd MAC matching keeps `eno0` unchanged.
- **Pitfall if Adding a Linux Bridge**: Any competing `enp2s0:` Netplan stanza sorts alphabetically before `enp3s0`, stealing `eno0` and blackholing outbound IP replies.

## 4. `NCT6776F/D` Hardware Monitor, `lm-sensors`, & ACPI S3

- `/etc/modules-load.d/h61m-s1-plus-coreboot.conf` loads `i2c-dev` and `nct6775`.
- Install `lm-sensors` and deploy [`configs/asrock-h61m-s1-plus-sensors.conf`](../../../configs/asrock-h61m-s1-plus-sensors.conf) (`sudo install -m 0644 configs/asrock-h61m-s1-plus-sensors.conf /etc/sensors.d/asrock-h61m-s1-plus.conf && sudo sensors -s`):
  - `temp1` (`M/B Temp`, `SYSTIN` thermistor `TRMB8`), `temp7` (`CPU Temp (PECI)`, `SMIOVT2=0x0c` tracking `coretemp` at `0.5°C` resolution with `TjMax=105°C` crit), `fan1` (`CHA_FAN1`), `fan2` (`CPU_FAN1`), and SmartFan IV closed-loop `pwm1`/`pwm2` (`mode=1`, `temp_sel=7` -> `PECI0`).
  - Voltage scaling: `in0` (`Vcore`), `in1` (`+12V` `@ * 6.6` per stock ASRock `PE2`), `in2` (`AVCC`), `in3` (`+3.3V`), `in5` (`+5V` `@ * 3` `20k/10k` divider `OR374/OR375`), `in7` (`3VSB`), `in8` (`Vbat`); ignores `in4` (`SIO_IMON`), `in6` (`MB_TEMP`), unwired `fan3..fan5`, unwired `PCH_*` (`temp8..temp10`), floating `CASEOPEN1#` (`intrusion1`), and open `CI1` (`intrusion0`, held low by `Q11`/`OR4` when unjumpered).
- `h61-coreboot-config self-test` verifies `M/B Temp`, `CPU Temp (PECI)`, `CHA_FAN1`/`CPU_FAN1`, and `0` operational HWM threshold alarms, while `status` displays scaled voltages, PWM modes, `nvidia-smi` (`Tesla P4`) telemetry, and `h61-fan-control` service state.
- **Combined GPU + CPU Fan Daemon (`h61-fan-control.service`)**: Install [`scripts/h61_fan_control.py`](../../../scripts/h61_fan_control.py) (`/usr/local/bin/h61-fan-control`) + [`configs/h61-fan-control.service`](../../../configs/h61-fan-control.service) and enable with `sudo systemctl enable --now h61-fan-control.service` so `CHA_FAN1` / `CPU_FAN1` (`pwm1`/`pwm2`) ramp automatically for **`max(Tesla P4 >= 60°C -> 100%, CPU PECI0, SYSTIN)`** and restore hardware SmartFan IV (`mode 5`) via `ExecStopPost` whenever stopped. Verify with `h61-fan-control --self-test` and `sudo h61-fan-control --once`.
- `PEGP`, `RP01` (`00:1c.0` -> RTL8111/I226-V), `RP04`, `EHC1`, and `EHC2` show `S4 enabled` in `/proc/acpi/wakeup`.
- With NVIDIA vGPU `535.309.01` (`NVreg_PreserveVideoMemoryAllocations=1`), use `sudo h61-coreboot-config s3` (writes `suspend` / `resume` to `/proc/driver/nvidia/suspend` around sleep).

## 5. Platform Hardware Health Checklist

- **Firmware & SPI**: `sudo dmidecode -t bios` -> `Vendor: coreboot`, `ROM Size: 8 MB`.
- **IGD (`00:02.0`, `8086:016a`)**: `< 4 GiB` BARs (`0xdec00000`/`0xe0000000`), `i915` cleanly bound with zero `forcewake` timeout errors pre/post-S3, `ALC662` + `Intel CougarPoint HDMI` active in `/proc/asound/cards`.
- **IOMMU & Tesla P4 (`01:00.0`, `10de:1bb3`)**: `DMAR` VT-d active (`IOMMU group 2`), Above-4G BARs (`0xfe0000000` 256M, `0xff0000000` 32M), `nvidia-smi -L`.
- **Reference Documentation**: [`docs/HARDWARE-REPORT.md`](../../../docs/HARDWARE-REPORT.md), [`docs/HARDWARE-MAP.md`](../../../docs/HARDWARE-MAP.md), [`docs/COREBOOT-FEATURES-CATALOG.md`](../../../docs/COREBOOT-FEATURES-CATALOG.md), [`docs/SUPPORTED-CPUS.md`](../../../docs/SUPPORTED-CPUS.md), and [`docs/PORTING-AND-LESSONS-LEARNED.md`](../../../docs/PORTING-AND-LESSONS-LEARNED.md).
