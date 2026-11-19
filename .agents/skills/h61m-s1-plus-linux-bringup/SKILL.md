---
name: h61m-s1-plus-linux-bringup
description: >-
  Configure and verify Ubuntu Linux on the Coreboot-flashed ASRock H61M-S1 PLUS
  (host h61 via DHCP on eno0 at <target-ip>), including h61-coreboot-config TUI/CLI
  CFR management, COM1-only 115200 8N1 serial console/getty (LPT1 disabled),
  Netplan eno0 DHCP, NCT6776 hwmon sensors, S3 NVIDIA handshake, and IGD/Tesla P4
  checks. Use after flashing Coreboot, reinstalling Ubuntu, or configuring BIOS options from OS.
---

# ASRock H61M-S1 PLUS Linux Bring-Up & Verification (`v26.11.2`)

Use this runbook to verify, configure Coreboot CFR options, or restore OS state on `h61` (`<target-ip>` via DHCP on `eno0`) over SSH or `COM5` (see `serial-communication` and [serial_exec.py](../serial-communication/scripts/serial_exec.py)).

## 1. OS Runtime BIOS & Hardware Configuration (`h61-coreboot-config`)

[`scripts/h61_coreboot_config.py`](../../../scripts/h61_coreboot_config.py) is installed on `h61` at `/usr/local/bin/h61-coreboot-config` (stdlib-only Python 3 TUI + CLI):

- **All 9 Coreboot CFR options** (`gfx_uma_size`, `dram_max_speed`, `peg_bifurcation`, `hyper_threading`, `sata_mode`, `nmi`, `fan_profile`, `fb_debug_pause`, `power_on_after_fail`) are exposed via `SMMSTORE` under `/sys/firmware/efi/efivars/*-ceae4c1d-335b-4685-a4a0-fc4a94eea085` with attributes `0x00000007` (`NV|BS|RT`, `8` bytes `<II`) and `FS_IMMUTABLE_FL` managed automatically.
- **Common commands**:
  ```bash
  sudo h61-coreboot-config                  # Launch 4-tab interactive curses TUI
  sudo h61-coreboot-config self-test        # Verify 9 efivars, COM1 active, LPT1 disabled, WOL, hwmon
  sudo h61-coreboot-config status           # Live CPU, DRAM, COM1/LPT1, ACPI wakeups, sensors
  sudo h61-coreboot-config list             # List all 9 CFR options & values
  sudo h61-coreboot-config set fan_profile quiet
  sudo h61-coreboot-config backup /tmp/cfr-profile.json
  sudo h61-coreboot-config wol on
  sudo h61-coreboot-config s3 --seconds 15  # Runs /proc/driver/nvidia/suspend handshake automatically
  sudo h61-coreboot-config reboot-uefi --now
  ```

## 2. COM1-Only `115200 8N1` Serial Console (`LPT1` Disabled)

Coreboot and EDK2 use `COM1` (`0x3f8`, `/dev/ttyS0`) at `115200 8N1`; **`LPT1` (`0x378`) is disabled at boot** in `v26.11.2`:

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
4. **Verify LPT1 disabled & COM1 active**:
   - `grep . /sys/bus/pnp/devices/*/id` -> `PNP0501` (`COM1`), `PNP0303`, `PNP0f13` (no `PNP0400`).
   - `sudo grep -iE 'serial|parport|0378|03f8' /proc/ioports` -> ONLY `03f8-03ff : serial`.

## 3. Netplan NIC Naming & `eno0` DHCP Configuration

- Under Coreboot, onboard Realtek `RTL8111` (`02:00.0`, `10ec:8168`, `r8169`, MAC `d0:50:99:7c:84:dd`) enumerates as `eno0` (`ID_NET_NAME_ONBOARD=eno0`, alt `enp2s0`, NOT `enp3s0`).
- `/etc/netplan/00-installer-config.yaml` matches `macaddress: d0:50:99:7c:84:dd` -> `eno0` DHCP (`<target-ip>/24`).
- **Pitfall if Adding a Linux Bridge**: Any competing `enp2s0:` Netplan stanza sorts alphabetically before `enp3s0`, stealing `eno0` and blackholing outbound IP replies.

## 4. `NCT6776F/D` Hardware Monitor & ACPI S3

- `/etc/modules-load.d/h61m-s1-plus-coreboot.conf` loads `i2c-dev` and `nct6775`.
- `hwmon0` (`nct6776`) exposes live `SYSTIN`, `AUXTIN`, `fan1`/`fan2` RPM, and `pwm1`/`pwm2` (mode `5` SmartFan IV driven by `PECI0`). Analog `CPUTIN` (~`123.5°C`) is an unwired board pin; read real CPU die temperatures from `hwmon1` (`coretemp`).
- `PEGP`, `RP01` (`00:1c.0` -> RTL8111 `02:00.0`, `Supports Wake-on: pumbg`), `EHC1`, and `EHC2` show `S4 *enabled` in `/proc/acpi/wakeup`.
- With NVIDIA vGPU `535.309.01` (`NVreg_PreserveVideoMemoryAllocations=1`), use `sudo h61-coreboot-config s3` (writes `suspend` / `resume` to `/proc/driver/nvidia/suspend` around sleep).

## 5. Platform Hardware Health Checklist

- **Firmware & SPI**: `sudo dmidecode -t bios` -> `Vendor: coreboot`, `ROM Size: 8 MB`.
- **IGD (`00:02.0`, `8086:016a`)**: `< 4 GiB` BARs (`0xdec00000`/`0xe0000000`), `i915` cleanly bound with zero `forcewake` timeout errors pre/post-S3, `ALC662` + `Intel CougarPoint HDMI` active in `/proc/asound/cards`.
- **IOMMU & Tesla P4 (`01:00.0`, `10de:1bb3`)**: `DMAR` VT-d active (`IOMMU group 2`), Above-4G BARs (`0xfe0000000` 256M, `0xff0000000` 32M), `nvidia-smi -L`.
- **Reference Documentation**: [`docs/HARDWARE-REPORT.md`](../../../docs/HARDWARE-REPORT.md), [`docs/HARDWARE-MAP.md`](../../../docs/HARDWARE-MAP.md), [`docs/COREBOOT-FEATURES-CATALOG.md`](../../../docs/COREBOOT-FEATURES-CATALOG.md), [`docs/SUPPORTED-CPUS.md`](../../../docs/SUPPORTED-CPUS.md), and [`docs/PORTING-AND-LESSONS-LEARNED.md`](../../../docs/PORTING-AND-LESSONS-LEARNED.md).
