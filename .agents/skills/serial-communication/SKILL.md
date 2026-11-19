---
name: serial-communication
description: >-
  Capture Coreboot, EDK2, and Linux serial console boot logs, send keystrokes
  (such as ESC for UEFI setup), and run non-interactive UART shell commands or
  diagnostics between ASRock H61M-S1 PLUS COM1 (0x3f8) and Windows COM5 (CH340).
  Use this skill whenever flashing, booting, debugging serial output, or
  executing commands over COM5 on the H61M-S1 PLUS board.
---

# Serial Communication for ASRock H61M-S1 PLUS

Use [com_serial.py](./scripts/com_serial.py) for boot-log captures and keystrokes, and [serial_exec.py](./scripts/serial_exec.py) for non-interactive Linux shell execution over Windows `COM5`.

## Hardware & Wiring Topology

- **Target Board**: ASRock H61M-S1 PLUS (`h61`, Ubuntu DHCP on `eno0` at `<target-ip>`)
  - Super I/O: Nuvoton `NCT6776F/D` (`0x2e`), `COM1` (`LDN 0x02`) at `0x3f8`, IRQ 4 (`/dev/ttyS0` in Linux)
  - Connector: Motherboard DB9 header `COM1` behind RS-232 line driver `U11`
- **Windows Workstation**: `COM5` (`USB-SERIAL CH340`, `USB\VID_1A86&PID_7523`, `wch.cn` driver `3.9.2024.9`)
  - Cable: RS-232 null-modem crossover (`DB9 <-> DB9`)
- **Serial Parameters**: `115200 8N1` end-to-end across Coreboot -> EDK2 -> GRUB (`/etc/default/grub.d/99-serial-console.cfg`) -> Linux (`console=tty0 console=ttyS0,115200n8`) -> `serial-getty@ttyS0` (`/etc/systemd/system/serial-getty@ttyS0.service.d/10-baud-115200.conf`), verified across reboot with no flow control (`-crtscts`, `XON/XOFF` off). (`serial_exec.py` still retains `--fallback-baud 9600` for unconfigured images.)

## Critical Windows CH340 Driver Workaround (`SetCommState` Error 31)

Do **not** use `pyserial` (`serial.Serial("COM5", 115200)`) or `.NET` (`System.IO.Ports.SerialPort`) on `COM5` with WCH CH340 driver `3.9.2024.9`: both call Win32 `SetCommState()`, which fails with `PermissionError(..., 31)` (`ERROR_GEN_FAILURE`).

Both [com_serial.py](./scripts/com_serial.py) and [serial_exec.py](./scripts/serial_exec.py) open `\\.\COM5` using Win32 `CreateFileW`, `GetCommState`, `SetCommTimeouts`, `PurgeComm`, `ReadFile`, and `WriteFile` (only invoking `mode COM5` when switching away from `115200`). *(Downgrading the WCH driver to `3.5.2019.1` resolves Error 31 for GUI apps like PuTTY.)*

## Non-Interactive Linux Shell Execution (`serial_exec.py`)

Use [serial_exec.py](./scripts/serial_exec.py) whenever running Linux commands over `COM5`:

```powershell
# Read-only check (tries 115200 first, falls back cleanly to 9600)
python ".agents/skills/serial-communication/scripts/serial_exec.py" --cmd "hostname; ip -br addr"

# Privileged command from script file, saving clean output
python ".agents/skills/serial-communication/scripts/serial_exec.py" --sudo --timeout 60 --cmd-file "path\to\script.sh" --outfile "outputs/serial-out.txt"
```

Key design details and traps already handled by [serial_exec.py](./scripts/serial_exec.py):
- **Single-line base64 `eval` framing**: `sudo` calls `tcsetattr(TCSAFLUSH)`, which flushes queued bytes out of the Linux `ttyS0` RX buffer if multi-line commands are streamed raw. Wrapping commands in a single `;`-separated line (`printf __BEGIN_; eval "$(printf ... | base64 -d)"; printf __END_`) avoids dropped lines, quoting issues, and early marker matches from TTY echo.
- **Baud-aware pacing & pager protection**: Writes 16-byte chunks paced to the active baud rate and exports `SYSTEMD_PAGER=cat PAGER=cat` so `systemctl`/`networkctl` never block in `less`.
- **Never restart `serial-getty@ttyS0` over `ttyS0`**: Restarting `serial-getty@ttyS0` (or using `enable --now`) from inside a live `ttyS0` shell immediately kills the connection mid-command. Use `systemctl enable` + `daemon-reload` for boot-time changes.
- **Never `exit` cleanly inside `--cmd`**: Exiting logs out mid-wrapper before the end marker prints.
- **PowerShell 5.1 syntax**: Never use `&&` or `||` in PowerShell calls; use `;`.

## Coreboot / EDK2 Capture Workflows (`com_serial.py`)

1. **Check `COM5` readiness before power-on**:
   ```powershell
   python ".agents/skills/serial-communication/scripts/com_serial.py" --port COM5 status
   ```
   Verify `PORT=COM5 OPEN=OK baud=115200 bits=8 parity=0 stop=0`.

2. **Capture live Coreboot + EDK2 boot logs during power-on**:
   Start capture *before* pressing the board power button:
   ```powershell
   python ".agents/skills/serial-communication/scripts/com_serial.py" --port COM5 capture --duration 90 --purge --outfile "outputs/coreboot-bootlog.txt"
   ```

3. **Enter EDK2 Boot Manager / Coreboot CFR Setup (`ESC`)**:
   ```powershell
   python ".agents/skills/serial-communication/scripts/com_serial.py" --port COM5 capture --duration 60 --send-esc-on-boot --outfile "outputs/coreboot-setup.txt"
   ```
   Or send bursts: `python ".agents/skills/serial-communication/scripts/com_serial.py" --port COM5 send --esc --repeat 10 --read-wait 3`.

4. **Two-way UART verification while Ubuntu is booted (`<target-ip>`)**:
   ```powershell
   python ".agents/skills/serial-communication/scripts/com_serial.py" --port COM5 loopback-test --host <target-ip> --user zero --password <password>
   ```

## Validation Checklist

- `status` prints `OPEN=OK baud=115200` with `CTS=True DSR=True` when the board is powered on.
- Captured Coreboot `v26.11.2` logs show `bootblock` -> `romstage` (`SF: Detected ef 4017 ... 0x800000` on 8 MiB `W25Q64`, native DDR3 init) -> `ramstage` (`PNP: 002e.1: enabled 0` LPT1 off, `PNP: 002e.2: enabled 1` COM1 on, `azalia_audio`, `Nuvoton HWM`, `ACPI: * DMAR`, `FB_CONSOLE`) -> `UEFIPAYLOAD.fd`.
- `serial_exec.py` exits `0` without `[WARNING: timed out ...]` and restores `stty echo`.
