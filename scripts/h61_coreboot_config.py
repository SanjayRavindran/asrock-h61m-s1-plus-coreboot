#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""
ASRock H61M-S1 PLUS — Coreboot Runtime Configuration Tool (TUI & CLI)

Features:
  1. Read/write Coreboot CFR firmware options exposed to Linux via SMMSTORE /
     EDK2 CfrSetupMenuDxe efivars (`*-ceae4c1d-335b-4685-a4a0-fc4a94eea085`).
  2. Export/import JSON option profiles and reset options to firmware defaults.
  3. Inspect live system identity, I/O port status (COM1 active vs LPT1 disabled),
     nct6776 + coretemp hwmon sensors, PCI/network inventory, and UEFI boot order.
  4. Configure Wake-on-LAN (ethtool) and ACPI wakeup sources (/proc/acpi/wakeup).
  5. Trigger S3 suspend safely with automatic NVIDIA /proc/driver/nvidia/suspend
     handshake, reboot directly to UEFI Setup (efibootmgr -n), and safely back up
     or flash the SPI BIOS region via flashrom (--ifd -i bios).

Run without arguments in a terminal for the interactive curses TUI, or pass
a subcommand (see `--help`) for scripted CLI automation.
"""

from __future__ import annotations

import argparse
import ctypes
import curses
import datetime as dt
import fcntl
import json
import os
import pathlib
import re
import shutil
import struct
import subprocess
import sys
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

CFR_GUID = "ceae4c1d-335b-4685-a4a0-fc4a94eea085"
EFIVARS_DIR = pathlib.Path("/sys/firmware/efi/efivars")
EFI_ATTR_NV_BS_RT = 0x00000007
FS_IMMUTABLE_FL = 0x00000010
FS_IOC_GETFLAGS = 0x80086601
FS_IOC_SETFLAGS = 0x40086602

FLASHROM_CHIP_8MIB = "W25Q64BV/W25Q64CV/W25Q64FV"
FLASHROM_CHIP_4MIB = "W25Q32BV/W25Q32CV/W25Q32FV"
ROM_SIZE_4MIB = 4 * 1024 * 1024
ROM_SIZE_8MIB = 8 * 1024 * 1024
DEFAULT_NIC = "eno0"


@dataclass(frozen=True)
class CfrOption:
    name: str
    ui_name: str
    form: str
    kind: str  # "enum" or "bool"
    default: int
    choices: Dict[int, str]
    aliases: Dict[str, int] = field(default_factory=dict)
    helptext: str = ""


CFR_OPTIONS: List[CfrOption] = [
    CfrOption(
        name="gfx_uma_size",
        ui_name="IGD UMA Size",
        form="System",
        kind="enum",
        default=0,
        choices={0: "32MB", 1: "64MB", 2: "96MB", 3: "128MB"},
        aliases={"32": 0, "32m": 0, "32mb": 0, "64": 1, "64m": 1, "64mb": 1, "96": 2, "96m": 2, "96mb": 2, "128": 3, "128m": 3, "128mb": 3},
        helptext="Memory preallocated for Intel HD Graphics (requires reboot).",
    ),
    CfrOption(
        name="dram_max_speed",
        ui_name="DRAM Max Frequency",
        form="System",
        kind="enum",
        default=0,
        choices={
            0: "Auto (SPD/JEDEC)",
            1: "DDR3-1600 (800 MHz)",
            2: "DDR3-1333 (666 MHz)",
            3: "DDR3-1066 (533 MHz)",
        },
        aliases={"auto": 0, "1600": 1, "ddr3-1600": 1, "1333": 2, "ddr3-1333": 2, "1066": 3, "ddr3-1066": 3},
        helptext="Maximum DDR3 memory clock; Auto uses SPD/XMP profile (1.65 V XMP allowed).",
    ),
    CfrOption(
        name="peg_bifurcation",
        ui_name="PCIe x16 Slot Bifurcation",
        form="System",
        kind="enum",
        default=0,
        choices={
            0: "1x16 (Default)",
            1: "2x8 (Req. CFG[5]=0 strap)",
            2: "1x8+2x4 (Req. CFG[6:5]=00 strap)",
        },
        aliases={"1x16": 0, "x16": 0, "2x8": 1, "x8x8": 1, "1x8+2x4": 2, "x8x4x4": 2},
        helptext="CPU PEG root port grouping on PCIE1 (2x8 / 1x8+2x4 also need Ivy Bridge CFG[6:5] straps).",
    ),
    CfrOption(
        name="hyper_threading",
        ui_name="Hyper-Threading",
        form="System",
        kind="bool",
        default=1,
        choices={0: "Disabled", 1: "Enabled"},
        aliases={"off": 0, "disable": 0, "disabled": 0, "false": 0, "no": 0, "on": 1, "enable": 1, "enabled": 1, "true": 1, "yes": 1},
        helptext="Enable or disable Intel Hyper-Threading Technology.",
    ),
    CfrOption(
        name="sata_mode",
        ui_name="SATA Mode",
        form="System",
        kind="enum",
        default=0,
        choices={0: "AHCI", 1: "IDE (compatible)", 2: "IDE (legacy)"},
        aliases={"ahci": 0, "ide": 1, "ide-compat": 1, "compatible": 1, "ide-legacy": 2, "legacy": 2},
        helptext="Operating mode for H61 PCH SATA controller (4 ports wired on H61M-S1 PLUS).",
    ),
    CfrOption(
        name="nmi",
        ui_name="Non-maskable Interrupts",
        form="System",
        kind="enum",
        default=0,
        choices={0: "Disabled", 1: "Enabled"},
        aliases={"off": 0, "disabled": 0, "on": 1, "enabled": 1},
        helptext="Enable or disable hardware Non-Maskable Interrupts.",
    ),
    CfrOption(
        name="me_state",
        ui_name="Intel ME Boot State",
        form="System",
        kind="enum",
        default=0,
        choices={0: "Normal (Enabled)", 1: "Disabled (Soft Temp Disable)"},
        aliases={"normal": 0, "on": 0, "enable": 0, "enabled": 0, "off": 1, "disable": 1, "disabled": 1},
        helptext="Enable or HECI Soft-Temporary-Disable Intel Management Engine (requires reboot).",
    ),
    CfrOption(
        name="fan_profile",
        ui_name="SmartFan IV Profile",
        form="Cooling & Display",
        kind="enum",
        default=0,
        choices={0: "Balanced (Default)", 1: "Quiet", 2: "Performance", 3: "Full Speed"},
        aliases={"balanced": 0, "quiet": 1, "perf": 2, "performance": 2, "full": 3, "full-speed": 3, "max": 3},
        helptext="NCT6776F closed-loop fan curve for CPU_FAN1 and CHA_FAN1 driven by CPU PECI0.",
    ),
    CfrOption(
        name="fb_debug_pause",
        ui_name="Monitor Debug/POST Pause",
        form="Cooling & Display",
        kind="enum",
        default=1,
        choices={0: "0s (Immediate)", 1: "3s (Default)", 2: "5s", 3: "10s"},
        aliases={"0": 0, "0s": 0, "immediate": 0, "3": 1, "3s": 1, "5": 2, "5s": 2, "10": 3, "10s": 3},
        helptext="Duration Coreboot holds the HDMI/VGA debug & POST console before launching UEFI.",
    ),
    CfrOption(
        name="power_on_after_fail",
        ui_name="Restore AC Power Loss",
        form="Power",
        kind="enum",
        default=0,
        choices={0: "Power off (S5)", 1: "Power on (S0)", 2: "Previous state"},
        aliases={"off": 0, "s5": 0, "poweroff": 0, "on": 1, "s0": 1, "poweron": 1, "prev": 2, "previous": 2, "keep": 2},
        helptext="System behavior after an AC power outage is restored.",
    ),
]

CFR_BY_NAME: Dict[str, CfrOption] = {o.name: o for o in CFR_OPTIONS}


def cfr_path(opt_name: str, efivars_dir: pathlib.Path = EFIVARS_DIR) -> pathlib.Path:
    return efivars_dir / f"{opt_name}-{CFR_GUID}"


def read_cfr_option(
    opt: CfrOption, efivars_dir: pathlib.Path = EFIVARS_DIR
) -> Tuple[int, Optional[int], bool]:
    """Return (value_int, attrs_or_None, exists_in_efivars)."""
    p = cfr_path(opt.name, efivars_dir)
    if not p.exists():
        return opt.default, None, False
    raw = p.read_bytes()
    if len(raw) < 8:
        raise ValueError(f"{p} truncated ({len(raw)} bytes, expected >= 8)")
    attrs, val = struct.unpack("<II", raw[:8])
    return val, attrs, True


def _clear_immutable(path: pathlib.Path) -> bool:
    """Clear FS_IMMUTABLE_FL on an efivarfs file if set; return True if cleared."""
    if not path.exists():
        return False
    cleared = False
    try:
        fd = os.open(path, os.O_RDONLY)
        try:
            buf = bytearray(8)
            fcntl.ioctl(fd, FS_IOC_GETFLAGS, buf, True)
            flags = struct.unpack("=Q", buf)[0]
            if flags & FS_IMMUTABLE_FL:
                new_flags = struct.pack("=Q", flags & ~FS_IMMUTABLE_FL)
                fcntl.ioctl(fd, FS_IOC_SETFLAGS, new_flags)
                cleared = True
        finally:
            os.close(fd)
        return cleared
    except OSError:
        chattr = shutil.which("chattr")
        if chattr:
            res = subprocess.run([chattr, "-i", str(path)], capture_output=True, text=True)
            if res.returncode == 0:
                return True
    return cleared


def _restore_immutable(path: pathlib.Path) -> None:
    try:
        fd = os.open(path, os.O_RDONLY)
        try:
            buf = bytearray(8)
            fcntl.ioctl(fd, FS_IOC_GETFLAGS, buf, True)
            flags = struct.unpack("=Q", buf)[0]
            if not (flags & FS_IMMUTABLE_FL):
                fcntl.ioctl(fd, FS_IOC_SETFLAGS, struct.pack("=Q", flags | FS_IMMUTABLE_FL))
        finally:
            os.close(fd)
    except OSError:
        chattr = shutil.which("chattr")
        if chattr:
            subprocess.run([chattr, "+i", str(path)], capture_output=True)


def write_cfr_option(
    opt: CfrOption,
    value: int,
    efivars_dir: pathlib.Path = EFIVARS_DIR,
    reapply_immutable: bool = True,
) -> None:
    if value not in opt.choices:
        valid = ", ".join(f"{k}={v}" for k, v in opt.choices.items())
        raise ValueError(f"Invalid value {value} for {opt.name}; valid: {valid}")

    is_real_efivars = efivars_dir == EFIVARS_DIR
    if is_real_efivars and os.geteuid() != 0:
        raise PermissionError(f"Writing {opt.name} to {EFIVARS_DIR} requires root privileges (run with sudo).")

    p = cfr_path(opt.name, efivars_dir)
    attrs = EFI_ATTR_NV_BS_RT
    if p.exists():
        try:
            old_raw = p.read_bytes()
            if len(old_raw) >= 4:
                attrs = struct.unpack("<I", old_raw[:4])[0]
        except OSError:
            pass
        _clear_immutable(p)

    payload = struct.pack("<II", attrs, value)
    flags = os.O_WRONLY | os.O_CREAT
    if not is_real_efivars:
        flags |= os.O_TRUNC
    fd = os.open(p, flags, 0o644)
    try:
        written = os.write(fd, payload)
        if written != len(payload):
            raise IOError(f"Short write to {p}: wrote {written}/{len(payload)} bytes")
    finally:
        os.close(fd)
        if is_real_efivars and reapply_immutable:
            _restore_immutable(p)

    rb_val, rb_attrs, exists = read_cfr_option(opt, efivars_dir)
    if not exists or rb_val != value:
        raise RuntimeError(
            f"Readback verification failed for {opt.name}: wrote {value} (attrs 0x{attrs:x}), "
            f"read {rb_val} (attrs={rb_attrs}, exists={exists})"
        )


def parse_cfr_value(opt: CfrOption, token: str) -> int:
    clean = token.strip().lower()
    if clean in opt.aliases:
        return opt.aliases[clean]
    try:
        num = int(clean, 0)
        if num in opt.choices:
            return num
    except ValueError:
        pass
    for k, label in opt.choices.items():
        if label.lower() == clean:
            return k
    valid = ", ".join(f"{k} ({v})" for k, v in opt.choices.items())
    raise ValueError(f"Unknown value '{token}' for {opt.name}. Valid values: {valid}")


def run_cmd(cmd: List[str], timeout: int = 30) -> Tuple[int, str, str]:
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    return proc.returncode, proc.stdout, proc.stderr


def read_text_safe(p: pathlib.Path, default: str = "") -> str:
    try:
        return p.read_text(encoding="utf-8", errors="replace").strip()
    except OSError:
        return default


def get_sensors() -> List[Dict[str, object]]:
    """Collect live hwmon readings (nct6776, coretemp, etc.)."""
    chips: List[Dict[str, object]] = []
    base = pathlib.Path("/sys/class/hwmon")
    if not base.exists():
        return chips
    for hw in sorted(base.iterdir()):
        name = read_text_safe(hw / "name", hw.name)
        temps = []
        fans = []
        volts = []
        pwms = []
        for idx in range(1, 20):
            tp = hw / f"temp{idx}_input"
            if tp.exists():
                val_mc = int(read_text_safe(tp, "0") or 0)
                lbl = read_text_safe(hw / f"temp{idx}_label", f"temp{idx}")
                temps.append({"id": f"temp{idx}", "label": lbl, "c": val_mc / 1000.0})
            fp = hw / f"fan{idx}_input"
            if fp.exists():
                rpm = int(read_text_safe(fp, "0") or 0)
                lbl = read_text_safe(hw / f"fan{idx}_label", f"fan{idx}")
                fans.append({"id": f"fan{idx}", "label": lbl, "rpm": rpm})
            vp = hw / f"in{idx}_input"
            if vp.exists():
                mv = int(read_text_safe(vp, "0") or 0)
                lbl = read_text_safe(hw / f"in{idx}_label", f"in{idx}")
                volts.append({"id": f"in{idx}", "label": lbl, "v": mv / 1000.0})
            pp = hw / f"pwm{idx}"
            if pp.exists():
                raw_pwm = int(read_text_safe(pp, "0") or 0)
                en = read_text_safe(hw / f"pwm{idx}_enable", "?")
                pwms.append({"id": f"pwm{idx}", "pct": round(raw_pwm * 100.0 / 255.0, 1), "raw": raw_pwm, "enable": en})
        chips.append({"hwmon": hw.name, "name": name, "temps": temps, "fans": fans, "volts": volts, "pwms": pwms})
    return chips


def get_wol(iface: str = DEFAULT_NIC) -> Dict[str, str]:
    ethtool = shutil.which("ethtool")
    if not ethtool:
        return {"supports": "ethtool not installed", "active": "unknown"}
    rc, out, _ = run_cmd([ethtool, iface])
    if rc != 0:
        return {"supports": "error", "active": "unknown"}
    sup = "?"
    act = "?"
    for line in out.splitlines():
        s = line.strip()
        if s.startswith("Supports Wake-on:"):
            sup = s.split(":", 1)[1].strip()
        elif s.startswith("Wake-on:"):
            act = s.split(":", 1)[1].strip()
    return {"supports": sup, "active": act}


def set_wol(iface: str, enabled: bool) -> Tuple[bool, str]:
    if os.geteuid() != 0:
        return False, "Setting WOL requires root privileges (sudo)."
    ethtool = shutil.which("ethtool")
    if not ethtool:
        return False, "ethtool binary not found."
    mode = "g" if enabled else "d"
    rc, out, err = run_cmd([ethtool, "-s", iface, "wol", mode])
    if rc != 0:
        return False, err.strip() or out.strip() or f"ethtool exited {rc}"
    cur = get_wol(iface)
    return True, f"{iface} Wake-on set to '{cur['active']}' (supports: {cur['supports']})"


def get_acpi_wakeup() -> List[Dict[str, str]]:
    p = pathlib.Path("/proc/acpi/wakeup")
    rows: List[Dict[str, str]] = []
    if not p.exists():
        return rows
    for line in read_text_safe(p).splitlines()[1:]:
        parts = line.split()
        if len(parts) >= 3:
            rows.append(
                {
                    "device": parts[0],
                    "s_state": parts[1],
                    "status": parts[2].lstrip("*"),
                    "sysfs": parts[3] if len(parts) > 3 else "",
                }
            )
    return rows


def set_acpi_wakeup(device: str, desired_enabled: Optional[bool] = None) -> Tuple[bool, str]:
    if os.geteuid() != 0:
        return False, "Changing /proc/acpi/wakeup requires root privileges (sudo)."
    rows = {r["device"]: r for r in get_acpi_wakeup()}
    if device not in rows:
        return False, f"ACPI wakeup device '{device}' not found."
    cur_en = rows[device]["status"] == "enabled"
    if desired_enabled is not None and cur_en == desired_enabled:
        return True, f"{device} already {'enabled' if cur_en else 'disabled'}"
    pathlib.Path("/proc/acpi/wakeup").write_text(device + "\n", encoding="utf-8")
    new_rows = {r["device"]: r for r in get_acpi_wakeup()}
    return True, f"{device} -> {new_rows.get(device, {}).get('status', '?')}"


def detect_io_ports() -> Dict[str, object]:
    pnp_ids: List[str] = []
    pnp_base = pathlib.Path("/sys/bus/pnp/devices")
    if pnp_base.exists():
        for dev in sorted(pnp_base.iterdir()):
            id_text = read_text_safe(dev / "id")
            if id_text:
                pnp_ids.extend(id_text.splitlines())
    ioports = read_text_safe(pathlib.Path("/proc/ioports"))
    has_com1 = ("PNP0501" in pnp_ids) or any("03f8-03ff" in l for l in ioports.splitlines())
    has_lpt1 = (
        ("PNP0400" in pnp_ids)
        or ("PNP0401" in pnp_ids)
        or any("0378-037" in l or "parport" in l for l in ioports.splitlines())
    )
    return {
        "com1_03f8_active": has_com1,
        "lpt1_0378_active": has_lpt1,
    }


EFI_GLOBAL_GUID = "8be4df61-93ca-11d2-aa0d-00e098032b8c"
EFI_IMAGE_SECURITY_GUID = "d719b2cb-3d3a-4596-a3bc-dad00e67656f"


def get_secure_boot_info(efivars_dir: pathlib.Path = EFIVARS_DIR) -> Dict[str, object]:
    """Inspect UEFI Secure Boot runtime variables and enrolled key stores in efivars."""
    def _read_u8(name: str, guid: str) -> Optional[int]:
        p = efivars_dir / f"{name}-{guid}"
        if not p.exists():
            return None
        try:
            raw = p.read_bytes()
            return raw[4] if len(raw) >= 5 else None
        except OSError:
            return None

    def _var_size(name: str, guid: str) -> int:
        p = efivars_dir / f"{name}-{guid}"
        try:
            return max(0, p.stat().st_size - 4) if p.exists() else 0
        except OSError:
            return 0

    sb = _read_u8("SecureBoot", EFI_GLOBAL_GUID)
    sm = _read_u8("SetupMode", EFI_GLOBAL_GUID)
    vk = _read_u8("VendorKeys", EFI_GLOBAL_GUID)
    pk_sz = _var_size("PK", EFI_GLOBAL_GUID)
    kek_sz = _var_size("KEK", EFI_GLOBAL_GUID)
    db_sz = _var_size("db", EFI_IMAGE_SECURITY_GUID)
    dbx_sz = _var_size("dbx", EFI_IMAGE_SECURITY_GUID)
    keys_enrolled = pk_sz > 0 and kek_sz > 0 and db_sz > 0
    return {
        "supported": sb is not None,
        "enabled": sb == 1,
        "setup_mode": sm == 1 if sm is not None else None,
        "vendor_keys": vk == 1 if vk is not None else None,
        "keys_enrolled": keys_enrolled,
        "sizes": {"PK": pk_sz, "KEK": kek_sz, "db": db_sz, "dbx": dbx_sz},
    }


def get_nvme_devices() -> List[Dict[str, str]]:
    """Detect NVMe PCIe controllers and block namespaces exposed by Linux."""
    devs: List[Dict[str, str]] = []
    seen_pci = set()
    nvme_sys = pathlib.Path("/sys/class/nvme")
    if nvme_sys.exists():
        for ctrl in sorted(nvme_sys.iterdir()):
            model = read_text_safe(ctrl / "model", "NVMe Controller")
            fw = read_text_safe(ctrl / "firmware_rev", "")
            dev_link = ""
            try:
                dev_link = (ctrl / "device").resolve().name
                seen_pci.add(dev_link)
            except OSError:
                pass
            devs.append({"name": ctrl.name, "pci": dev_link, "model": model, "fw": fw})
    pci_sys = pathlib.Path("/sys/bus/pci/devices")
    if pci_sys.exists():
        for pdev in sorted(pci_sys.iterdir()):
            if pdev.name in seen_pci:
                continue
            cls = read_text_safe(pdev / "class", "")
            if cls.startswith("0x0108"):
                ven = read_text_safe(pdev / "vendor", "?")
                did = read_text_safe(pdev / "device", "?")
                devs.append({"name": pdev.name, "pci": pdev.name, "model": f"PCIe NVMe ({ven}:{did})", "fw": ""})
    return devs


def get_system_info() -> Dict[str, object]:
    dmi = pathlib.Path("/sys/class/dmi/id")
    cpu_model = ""
    cpu_threads = 0
    for line in read_text_safe(pathlib.Path("/proc/cpuinfo")).splitlines():
        if line.startswith("model name") and not cpu_model:
            cpu_model = line.split(":", 1)[1].strip()
        elif line.startswith("processor"):
            cpu_threads += 1
    mem_kb = 0
    for line in read_text_safe(pathlib.Path("/proc/meminfo")).splitlines():
        if line.startswith("MemTotal:"):
            mem_kb = int(line.split()[1])
            break
    ip_out = ""
    if shutil.which("ip"):
        _, ip_out, _ = run_cmd(["ip", "-4", "-br", "addr", "show", DEFAULT_NIC])
    efiboot = ""
    if shutil.which("efibootmgr"):
        _, efiboot, _ = run_cmd(["efibootmgr"])
    io = detect_io_ports()
    return {
        "hostname": read_text_safe(pathlib.Path("/proc/sys/kernel/hostname"), "unknown"),
        "kernel": os.uname().release,
        "bios_vendor": read_text_safe(dmi / "bios_vendor"),
        "bios_version": read_text_safe(dmi / "bios_version"),
        "bios_date": read_text_safe(dmi / "bios_date"),
        "board": f"{read_text_safe(dmi / 'board_vendor')} {read_text_safe(dmi / 'board_name')}".strip(),
        "cpu_model": cpu_model,
        "cpu_threads": cpu_threads,
        "mem_gib": round(mem_kb / (1024 * 1024), 2),
        "nic_ip4": ip_out.strip(),
        "com1_active": io["com1_03f8_active"],
        "lpt1_active": io["lpt1_0378_active"],
        "secure_boot": get_secure_boot_info(),
        "nvme_devices": get_nvme_devices(),
        "efibootmgr": efiboot.strip(),
    }


def find_uefi_setup_bootnum() -> str:
    ebm = shutil.which("efibootmgr")
    if not ebm:
        return "0000"
    rc, out, _ = run_cmd([ebm])
    if rc == 0:
        for line in out.splitlines():
            m = re.match(r"Boot([0-9A-Fa-f]{4})\*?\s+(.*)$", line.strip())
            if m and any(k in m.group(2).lower() for k in ("enter setup", "uiapp", "frontpage", "setup")):
                return m.group(1).upper()
    return "0000"


def reboot_to_uefi(reboot_now: bool = False) -> Tuple[bool, str]:
    if os.geteuid() != 0:
        return False, "efibootmgr BootNext requires root privileges (sudo)."
    ebm = shutil.which("efibootmgr")
    if not ebm:
        return False, "efibootmgr not installed."
    bootnum = find_uefi_setup_bootnum()
    rc, out, err = run_cmd([ebm, "-n", bootnum])
    if rc != 0:
        return False, err.strip() or out.strip()
    msg = f"BootNext set to Boot{bootnum} (UEFI Setup)."
    if reboot_now:
        subprocess.Popen(["systemctl", "reboot"])
        msg += " Rebooting now..."
    return True, msg


def suspend_s3(wake_seconds: Optional[int] = None) -> Tuple[bool, str]:
    """Enter ACPI S3 suspend cleanly, handling NVIDIA NVreg_PreserveVideoMemoryAllocations=1."""
    if os.geteuid() != 0:
        return False, "S3 suspend requires root privileges (sudo)."
    nv_proc = pathlib.Path("/proc/driver/nvidia/suspend")
    nv_prepared = False
    try:
        if nv_proc.exists():
            nv_proc.write_text("suspend\n", encoding="utf-8")
            nv_prepared = True
        if wake_seconds is not None:
            rtcwake = shutil.which("rtcwake")
            if not rtcwake:
                return False, "rtcwake binary not found."
            rc, out, err = run_cmd([rtcwake, "-m", "mem", "-s", str(wake_seconds)], timeout=wake_seconds + 60)
        else:
            rc, out, err = run_cmd(["systemctl", "suspend"], timeout=60)
        if rc != 0:
            return False, err.strip() or out.strip() or f"Suspend exited {rc}"
        return True, "Resumed cleanly from ACPI S3."
    finally:
        if nv_prepared:
            try:
                nv_proc.write_text("resume\n", encoding="utf-8")
            except OSError:
                pass


def _flashrom_chip_for_size(rom_size: Optional[int] = None, chip_override: Optional[str] = None) -> Optional[str]:
    if chip_override:
        return chip_override
    if rom_size == ROM_SIZE_4MIB:
        return FLASHROM_CHIP_4MIB
    if rom_size == ROM_SIZE_8MIB:
        return FLASHROM_CHIP_8MIB
    return FLASHROM_CHIP_8MIB


def flashrom_backup_bios(out_path: pathlib.Path, chip: Optional[str] = None) -> Tuple[bool, str]:
    if os.geteuid() != 0:
        return False, "flashrom requires root privileges (sudo)."
    fr = shutil.which("flashrom")
    if not fr:
        return False, "flashrom binary not found."
    cmd = [fr, "-p", "internal"]
    if chip:
        cmd.extend(["-c", chip])
    cmd.extend(["--ifd", "-i", "bios", "-r", str(out_path)])
    rc, out, err = run_cmd(cmd, timeout=180)
    if rc != 0 and not chip:
        cmd = [fr, "-p", "internal", "-c", FLASHROM_CHIP_8MIB, "--ifd", "-i", "bios", "-r", str(out_path)]
        rc, out, err = run_cmd(cmd, timeout=180)
    if rc != 0:
        return False, (err or out).strip()
    return True, f"Read current SPI BIOS region cleanly via flashrom ({out_path})."


def flashrom_write_bios(rom_path: pathlib.Path, chip: Optional[str] = None) -> Tuple[bool, str]:
    if os.geteuid() != 0:
        return False, "flashrom requires root privileges (sudo)."
    if not rom_path.exists():
        return False, f"Image not found: {rom_path}"
    sz = rom_path.stat().st_size
    if sz not in (ROM_SIZE_4MIB, ROM_SIZE_8MIB):
        return False, (
            f"Expected complete 4 MiB ({ROM_SIZE_4MIB} B) or 8 MiB ({ROM_SIZE_8MIB} B) "
            f"flash image for '--ifd -i bios' address alignment, got {sz} B."
        )
    fr = shutil.which("flashrom")
    if not fr:
        return False, "flashrom binary not found."
    target_chip = _flashrom_chip_for_size(sz, chip)
    cmd = [fr, "-p", "internal"]
    if target_chip:
        cmd.extend(["-c", target_chip])
    cmd.extend(["--ifd", "-i", "bios", "--noverify-all", "-w", str(rom_path)])
    rc, out, err = run_cmd(cmd, timeout=240)
    if rc != 0 or "VERIFIED" not in out:
        return False, (out + "\n" + err).strip()
    return True, f"SPI BIOS region ({sz // (1024 * 1024)} MiB) flashed and VERIFIED cleanly (IFD/ME preserved)."


def backup_cfr_json(out_path: pathlib.Path, efivars_dir: pathlib.Path = EFIVARS_DIR) -> Dict[str, object]:
    data: Dict[str, object] = {
        "board": "ASRock H61M-S1 PLUS",
        "cfr_guid": CFR_GUID,
        "timestamp": dt.datetime.now(dt.timezone.utc).isoformat(),
        "options": {},
    }
    opts = {}
    for opt in CFR_OPTIONS:
        val, attrs, exists = read_cfr_option(opt, efivars_dir)
        opts[opt.name] = {
            "value": val,
            "label": opt.choices.get(val, str(val)),
            "attrs": f"0x{attrs:08x}" if attrs is not None else None,
            "present_in_efivars": exists,
        }
    data["options"] = opts
    out_path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return data


def restore_cfr_json(in_path: pathlib.Path, efivars_dir: pathlib.Path = EFIVARS_DIR) -> List[str]:
    data = json.loads(in_path.read_text(encoding="utf-8"))
    opts = data.get("options", {})
    changed = []
    for name, entry in opts.items():
        if name not in CFR_BY_NAME:
            continue
        opt = CFR_BY_NAME[name]
        val = int(entry["value"] if isinstance(entry, dict) else entry)
        cur, _, _ = read_cfr_option(opt, efivars_dir)
        if cur != val:
            write_cfr_option(opt, val, efivars_dir)
            changed.append(f"{name}: {cur} -> {val} ({opt.choices[val]})")
    return changed


def self_test(efivars_dir: pathlib.Path = EFIVARS_DIR) -> Tuple[bool, List[str]]:
    logs: List[str] = []
    present = 0
    for opt in CFR_OPTIONS:
        val, attrs, exists = read_cfr_option(opt, efivars_dir)
        status = f"{val}={opt.choices.get(val, '?')}"
        attr_s = f"0x{attrs:08x}" if attrs is not None else "missing"
        logs.append(f"  CFR {opt.name:<20s} : {status:<28s} attrs={attr_s} present={exists}")
        if exists and attrs == EFI_ATTR_NV_BS_RT:
            present += 1
    io = detect_io_ports()
    logs.append(f"  COM1 (0x3f8) active     : {io['com1_03f8_active']}")
    logs.append(f"  LPT1 (0x378) active     : {io['lpt1_0378_active']}")
    wol = get_wol(DEFAULT_NIC)
    logs.append(f"  {DEFAULT_NIC} WOL                : active={wol['active']} (supports={wol['supports']})")
    sb = get_secure_boot_info(efivars_dir if (efivars_dir / f"SecureBoot-{EFI_GLOBAL_GUID}").exists() else EFIVARS_DIR)
    sb_state = "Enabled" if sb["enabled"] else ("Disabled" if sb["supported"] else "Unsupported")
    sb_mode = "SetupMode" if sb["setup_mode"] else "UserMode"
    sz = sb["sizes"]
    logs.append(
        f"  UEFI Secure Boot        : {sb_state} ({sb_mode}, keys_enrolled={sb['keys_enrolled']}, "
        f"PK={sz['PK']}B KEK={sz['KEK']}B db={sz['db']}B dbx={sz['dbx']}B)"
    )
    nvmes = get_nvme_devices()
    logs.append(f"  NVMe PCIe controllers   : {len(nvmes)} detected")
    sensors = get_sensors()
    logs.append(f"  hwmon devices           : {', '.join(str(s['name']) for s in sensors) or 'none'}")
    ok = present == len(CFR_OPTIONS) and bool(io["com1_03f8_active"]) and bool(io["lpt1_0378_active"])
    return ok, logs


# ---------------------------------------------------------------------------
# Interactive Curses TUI
# ---------------------------------------------------------------------------
class H61Tui:
    TABS = ["1: BIOS CFR Options", "2: Power & Wake", "3: Live Sensors & HW", "4: Backup & Flash"]

    def __init__(self, stdscr, efivars_dir: pathlib.Path = EFIVARS_DIR):
        self.stdscr = stdscr
        self.efivars_dir = efivars_dir
        self.tab = 0
        self.cursor = [0, 0, 0, 0]
        self.pending: Dict[str, int] = {}
        self.cfr_state: Dict[str, Tuple[int, Optional[int], bool]] = {}
        self.wakeup_rows: List[Dict[str, str]] = []
        self.wol_info: Dict[str, str] = {}
        self.sys_info: Dict[str, object] = {}
        self.sensors: List[Dict[str, object]] = []
        self.status_msg = "Loaded firmware & system state."
        self.reload_all()

    def reload_all(self) -> None:
        self.cfr_state = {o.name: read_cfr_option(o, self.efivars_dir) for o in CFR_OPTIONS}
        self.wakeup_rows = get_acpi_wakeup()
        self.wol_info = get_wol(DEFAULT_NIC)
        self.sys_info = get_system_info()
        self.sensors = get_sensors()

    def _safe_addn(self, y: int, x: int, text: str, width: int, attr: int = 0) -> None:
        h, w = self.stdscr.getmaxyx()
        if y < 0 or y >= h or x >= w or width <= 0:
            return
        maxw = min(width, w - x)
        if maxw <= 0:
            return
        try:
            self.stdscr.addnstr(y, x, text, maxw, attr)
        except curses.error:
            pass

    def _prompt_input(self, prompt: str) -> str:
        h, w = self.stdscr.getmaxyx()
        self.stdscr.move(h - 2, 0)
        self.stdscr.clrtoeol()
        self._safe_addn(h - 2, 0, prompt, w - 1, curses.A_BOLD)
        self.stdscr.refresh()
        curses.echo()
        curses.curs_set(1)
        try:
            raw = self.stdscr.getstr(h - 2, min(len(prompt), w - 2), 160)
            return raw.decode("utf-8", errors="replace").strip()
        finally:
            curses.noecho()
            curses.curs_set(0)

    def draw(self) -> None:
        self.stdscr.erase()
        h, w = self.stdscr.getmaxyx()
        if h < 20 or w < 72:
            self._safe_addn(0, 0, f"Terminal too small ({w}x{h}). Need >= 72x20.", w - 1, curses.A_BOLD)
            self.stdscr.refresh()
            return

        # Header
        hdr = f" ASRock H61M-S1 PLUS Coreboot Configurator | Host: {self.sys_info.get('hostname')} | Root: {'YES' if os.geteuid()==0 else 'NO (read-only)'}"
        self._safe_addn(0, 0, hdr.ljust(w - 1), w - 1, curses.A_REVERSE | curses.A_BOLD)

        # Tabs
        x = 1
        for i, title in enumerate(self.TABS):
            label = f" [{title}] "
            attr = curses.A_REVERSE | curses.A_BOLD if i == self.tab else curses.A_DIM
            self._safe_addn(2, x, label, w - x - 1, attr)
            x += len(label) + 1
        self._safe_addn(3, 0, "-" * (w - 1), w - 1)

        if self.tab == 0:
            self._draw_cfr_tab(h, w)
        elif self.tab == 1:
            self._draw_power_tab(h, w)
        elif self.tab == 2:
            self._draw_sensors_tab(h, w)
        else:
            self._draw_flash_tab(h, w)

        # Status & keybind footer
        self._safe_addn(h - 3, 0, "-" * (w - 1), w - 1)
        self._safe_addn(h - 2, 1, f"Status: {self.status_msg}", w - 2, curses.A_BOLD)
        keys = " [1-4/Tab] Switch Tab  [Up/Down] Move  [Enter/Space] Edit/Run  [s] Save CFR  [d] Defaults  [r] Refresh  [q] Quit"
        self._safe_addn(h - 1, 0, keys.ljust(w - 1), w - 1, curses.A_REVERSE)
        self.stdscr.refresh()

    def _draw_cfr_tab(self, h: int, w: int) -> None:
        self._safe_addn(4, 2, "Coreboot CFR Options (stored in SMMSTORE UEFI efivars; takes effect on next reboot):", w - 4, curses.A_BOLD)
        y = 6
        cur_form = None
        row_idx = 0
        sel = self.cursor[0]
        for opt in CFR_OPTIONS:
            if opt.form != cur_form:
                cur_form = opt.form
                self._safe_addn(y, 2, f"[{cur_form}]", w - 4, curses.A_UNDERLINE | curses.A_BOLD)
                y += 1
            cur_val, attrs, exists = self.cfr_state[opt.name]
            shown_val = self.pending.get(opt.name, cur_val)
            dirty = "*" if opt.name in self.pending and self.pending[opt.name] != cur_val else " "
            src = "efivar" if exists else "default"
            line = f" {dirty} {opt.ui_name:<28s} : {opt.choices.get(shown_val, str(shown_val)):<30s} ({src})"
            attr = curses.A_REVERSE if row_idx == sel else (curses.A_BOLD if dirty == "*" else 0)
            self._safe_addn(y, 2, line.ljust(min(w - 4, 86)), w - 4, attr)
            y += 1
            row_idx += 1

        sel_opt = CFR_OPTIONS[sel]
        self._safe_addn(min(y + 1, h - 5), 2, f"Option '{sel_opt.name}': {sel_opt.helptext}", w - 4, curses.A_DIM)

    def _draw_power_tab(self, h: int, w: int) -> None:
        self._safe_addn(4, 2, "Power, Wake-on-LAN & ACPI Wakeup Controls (Immediate Runtime / One-Shot Actions):", w - 4, curses.A_BOLD)
        items = self._power_items()
        sel = self.cursor[1]
        y = 6
        for i, (_, label, detail) in enumerate(items):
            if y >= h - 4:
                break
            line = f"  {label:<32s}  {detail}"
            attr = curses.A_REVERSE if i == sel else 0
            self._safe_addn(y, 2, line.ljust(min(w - 4, 86)), w - 4, attr)
            y += 1

    def _power_items(self) -> List[Tuple[str, str, str]]:
        items: List[Tuple[str, str, str]] = [
            ("wol", f"NIC Wake-on-LAN ({DEFAULT_NIC})", f"Active: {self.wol_info.get('active', '?')}  (Supports: {self.wol_info.get('supports', '?')})"),
            ("uefi", "Reboot to EDK2 UEFI Setup", f"Sets BootNext=Boot{find_uefi_setup_bootnum()} (next boot enters Setup)"),
            ("s3_now", "Trigger ACPI S3 Suspend Now", "Runs /proc/driver/nvidia/suspend handshake + systemctl suspend"),
        ]
        for row in self.wakeup_rows:
            items.append((f"acpi:{row['device']}", f"ACPI Wake [{row['device']}] ({row['s_state']})", f"status={row['status']}  {row['sysfs']}"))
        return items

    def _draw_sensors_tab(self, h: int, w: int) -> None:
        self._safe_addn(4, 2, "Live System Identity & Hardware Sensors (Press 'r' to refresh):", w - 4, curses.A_BOLD)
        sb = self.sys_info.get("secure_boot") or {}
        sb_str = f"{'ON' if sb.get('enabled') else 'OFF'} ({'Enrolled' if sb.get('keys_enrolled') else 'Unenrolled'})"
        nvmes = self.sys_info.get("nvme_devices") or []
        nvme_str = ", ".join(d.get("model", "NVMe") for d in nvmes) if nvmes else "none installed (NvmExpressDxe ready)"
        lines = [
            f"Board  : {self.sys_info.get('board')} | BIOS: {self.sys_info.get('bios_vendor')} {self.sys_info.get('bios_version')}",
            f"CPU    : {self.sys_info.get('cpu_model')} ({self.sys_info.get('cpu_threads')} threads) | RAM: {self.sys_info.get('mem_gib')} GiB",
            f"Network: {self.sys_info.get('nic_ip4') or 'down'} | COM1 (0x3f8): {'ACTIVE' if self.sys_info.get('com1_active') else 'OFF'} | LPT1 (0x378): {'ACTIVE' if self.sys_info.get('lpt1_active') else 'DISABLED'}",
            f"SecBoot: {sb_str} | NVMe: {nvme_str}",
            "",
        ]
        for s in self.sensors:
            lines.append(f"[{s['hwmon']} : {s['name']}]")
            t_str = ", ".join(f"{t['label']}={t['c']:.1f}C" for t in s["temps"])
            if t_str:
                lines.append(f"  Temps : {t_str}")
            f_str = ", ".join(f"{f['label']}={f['rpm']} RPM" for f in s["fans"])
            if f_str:
                lines.append(f"  Fans  : {f_str}")
            p_str = ", ".join(f"{p['id']}={p['pct']}% (mode={p['enable']})" for p in s["pwms"])
            if p_str:
                lines.append(f"  PWM   : {p_str}")
            v_str = ", ".join(f"{v['label']}={v['v']:.3f}V" for v in s["volts"][:6])
            if v_str:
                lines.append(f"  Volts : {v_str}")
        offset = self.cursor[2]
        visible = h - 10
        offset = max(0, min(offset, max(0, len(lines) - visible)))
        self.cursor[2] = offset
        for i, line in enumerate(lines[offset : offset + visible]):
            self._safe_addn(6 + i, 2, line, w - 4)

    def _draw_flash_tab(self, h: int, w: int) -> None:
        self._safe_addn(4, 2, "Profile Export/Import & Internal SPI BIOS Flash Helpers:", w - 4, curses.A_BOLD)
        actions = [
            ("backup_cfr", "Backup CFR Options to JSON", f"Writes all {len(CFR_OPTIONS)} current CFR variables to a JSON file"),
            ("restore_cfr", "Restore CFR Options from JSON", "Loads & writes CFR options from a JSON backup"),
            ("backup_spi", "Backup SPI BIOS Region (flashrom)", "Reads BIOS region via flashrom --ifd -i bios (read-only)"),
            ("flash_spi", "Flash SPI BIOS Region (flashrom)", "Writes BIOS region ONLY (requires 4/8 MiB ROM + 'FLASH' confirm)"),
        ]
        sel = self.cursor[3]
        for i, (_, name, desc) in enumerate(actions):
            attr = curses.A_REVERSE if i == sel else 0
            self._safe_addn(6 + i, 2, f"  {name:<35s} {desc}".ljust(min(w - 4, 86)), w - 4, attr)
        self._safe_addn(12, 2, "Safety Note: IFD (0x000000..0x000fff) and Intel ME (0x001000..0x17ffff) are NEVER modified internally.", w - 4, curses.A_DIM)

    def handle_key(self, ch: int) -> bool:
        if ch in (ord("q"), ord("Q")):
            return False
        if ch in (9,):  # Tab
            self.tab = (self.tab + 1) % 4
            return True
        if ch in (ord("1"), ord("2"), ord("3"), ord("4")):
            self.tab = ch - ord("1")
            return True
        if ch in (ord("r"), ord("R")):
            self.reload_all()
            self.status_msg = "Refreshed sensors, wakeups, and CFR values."
            return True
        if ch in (ord("b"), ord("B")):
            p = pathlib.Path(f"/tmp/h61-cfr-backup-{int(time.time())}.json")
            backup_cfr_json(p, self.efivars_dir)
            self.status_msg = f"Saved CFR JSON backup to {p}"
            return True
        if ch in (ord("d"), ord("D")) and self.tab == 0:
            for opt in CFR_OPTIONS:
                self.pending[opt.name] = opt.default
            self.status_msg = "Staged all CFR defaults. Press 's' to write to UEFI SMMSTORE."
            return True
        if ch in (ord("s"), ord("S")) and self.tab == 0:
            self._save_pending_cfr()
            return True

        max_items = {0: len(CFR_OPTIONS), 1: len(self._power_items()), 2: 40, 3: 4}[self.tab]
        if ch in (curses.KEY_UP, ord("k")):
            self.cursor[self.tab] = max(0, self.cursor[self.tab] - 1)
        elif ch in (curses.KEY_DOWN, ord("j")):
            self.cursor[self.tab] = min(max(0, max_items - 1), self.cursor[self.tab] + 1)
        elif ch in (curses.KEY_LEFT, curses.KEY_RIGHT, ord(" "), 10, 13):
            step = -1 if ch == curses.KEY_LEFT else 1
            self._activate_item(step)
        return True

    def _save_pending_cfr(self) -> None:
        if not self.pending:
            self.status_msg = "No pending CFR changes to save."
            return
        saved = []
        try:
            for name, val in list(self.pending.items()):
                cur, _, _ = self.cfr_state[name]
                if cur != val:
                    write_cfr_option(CFR_BY_NAME[name], val, self.efivars_dir)
                    saved.append(f"{name}={val}")
            self.pending.clear()
            self.reload_all()
            self.status_msg = (
                f"Saved & verified ({', '.join(saved)}). Reboot for firmware settings to apply."
                if saved
                else "No effective CFR changes needed."
            )
        except Exception as exc:
            self.status_msg = f"ERROR saving CFR: {exc}"

    def _activate_item(self, step: int) -> None:
        if self.tab == 0:
            opt = CFR_OPTIONS[self.cursor[0]]
            keys = sorted(opt.choices.keys())
            cur = self.pending.get(opt.name, self.cfr_state[opt.name][0])
            idx = keys.index(cur) if cur in keys else 0
            nxt = keys[(idx + step) % len(keys)]
            self.pending[opt.name] = nxt
            self.status_msg = f"Staged {opt.name} = {opt.choices[nxt]} (press 's' to commit)"
        elif self.tab == 1:
            key, _, _ = self._power_items()[self.cursor[1]]
            if key == "wol":
                en = "g" not in self.wol_info.get("active", "")
                ok, msg = set_wol(DEFAULT_NIC, en)
                self.status_msg = msg if ok else f"WOL error: {msg}"
            elif key == "uefi":
                ok, msg = reboot_to_uefi(reboot_now=False)
                self.status_msg = msg
            elif key == "s3_now":
                ans = self._prompt_input("Type SUSPEND to enter S3 sleep now: ")
                if ans == "SUSPEND":
                    curses.def_prog_mode()
                    curses.endwin()
                    ok, msg = suspend_s3()
                    curses.reset_prog_mode()
                    self.status_msg = msg
                else:
                    self.status_msg = "S3 suspend cancelled."
            elif key.startswith("acpi:"):
                dev = key.split(":", 1)[1]
                ok, msg = set_acpi_wakeup(dev)
                self.status_msg = msg
            self.reload_all()
        elif self.tab == 3:
            idx = self.cursor[3]
            if idx == 0:
                path_s = self._prompt_input("Backup JSON path [/tmp/h61-cfr-backup.json]: ") or "/tmp/h61-cfr-backup.json"
                try:
                    backup_cfr_json(pathlib.Path(path_s), self.efivars_dir)
                    self.status_msg = f"CFR backup written to {path_s}"
                except Exception as exc:
                    self.status_msg = f"Backup failed: {exc}"
            elif idx == 1:
                path_s = self._prompt_input("Restore JSON path: ")
                if path_s:
                    try:
                        changed = restore_cfr_json(pathlib.Path(path_s), self.efivars_dir)
                        self.reload_all()
                        self.status_msg = f"Restored {len(changed)} option(s)."
                    except Exception as exc:
                        self.status_msg = f"Restore failed: {exc}"
            elif idx == 2:
                path_s = self._prompt_input("SPI BIOS backup path [/tmp/h61-spi-bios-backup.bin]: ") or "/tmp/h61-spi-bios-backup.bin"
                self.status_msg = "Reading SPI BIOS region with flashrom..."
                self.draw()
                ok, msg = flashrom_backup_bios(pathlib.Path(path_s))
                self.status_msg = msg
            elif idx == 3:
                path_s = self._prompt_input("Path to 4/8 MiB ROM for BIOS-region flash: ")
                if path_s:
                    conf = self._prompt_input("Type FLASH to write SPI BIOS region now: ")
                    if conf == "FLASH":
                        self.status_msg = "Flashing SPI BIOS region with flashrom..."
                        self.draw()
                        ok, msg = flashrom_write_bios(pathlib.Path(path_s))
                        self.status_msg = msg
                    else:
                        self.status_msg = "Flash cancelled."


def run_tui(efivars_dir: pathlib.Path = EFIVARS_DIR) -> int:
    def _main(stdscr):
        curses.curs_set(0)
        stdscr.keypad(True)
        app = H61Tui(stdscr, efivars_dir)
        while True:
            app.draw()
            ch = stdscr.getch()
            if not app.handle_key(ch):
                break

    curses.wrapper(_main)
    return 0


# ---------------------------------------------------------------------------
# CLI Dispatcher
# ---------------------------------------------------------------------------
def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="ASRock H61M-S1 PLUS Coreboot Configuration TUI & CLI"
    )
    p.add_argument(
        "--efivars-dir",
        type=pathlib.Path,
        default=EFIVARS_DIR,
        help="Override UEFI efivars directory (default: /sys/firmware/efi/efivars)",
    )
    sub = p.add_subparsers(dest="cmd")

    sub.add_parser("tui", help="Launch interactive curses TUI (default when no command given)")
    sub.add_parser("list", help=f"List all {len(CFR_OPTIONS)} Coreboot CFR options and live values")

    pg = sub.add_parser("get", help="Get one CFR option value")
    pg.add_argument("option", choices=list(CFR_BY_NAME.keys()))

    ps = sub.add_parser("set", help="Set a CFR option value (integer or slug, e.g. 'quiet', '1600', '3s')")
    ps.add_argument("option", choices=list(CFR_BY_NAME.keys()))
    ps.add_argument("value")

    sub.add_parser("reset", help="Reset all CFR options to firmware defaults")

    pb = sub.add_parser("backup", help="Export current CFR options to JSON")
    pb.add_argument("file", type=pathlib.Path)

    pr = sub.add_parser("restore", help="Restore CFR options from JSON")
    pr.add_argument("file", type=pathlib.Path)

    sub.add_parser("status", help="Show DMI, COM1/LPT1 status, NIC, sensors, WOL, and wakeup state")

    pw = sub.add_parser("wol", help="Configure Wake-on-LAN via ethtool")
    pw.add_argument("state", choices=["on", "off"])
    pw.add_argument("--iface", default=DEFAULT_NIC)

    pa = sub.add_parser("wakeup", help="Enable or disable an ACPI wakeup device in /proc/acpi/wakeup")
    pa.add_argument("device")
    pa.add_argument("state", choices=["on", "off", "toggle"])

    pu = sub.add_parser("reboot-uefi", help="Set UEFI BootNext to Enter Setup")
    pu.add_argument("--now", action="store_true", help="Reboot immediately")

    ps3 = sub.add_parser("s3", help="Trigger ACPI S3 suspend safely (NVIDIA procfs aware)")
    ps3.add_argument("--seconds", type=int, default=None, help="Optional rtcwake sleep duration")

    pbb = sub.add_parser("backup-bios", help="Read current SPI BIOS region using flashrom")
    pbb.add_argument("out", type=pathlib.Path)
    pbb.add_argument("--chip", default=None, help="Optional flashrom -c chip override")

    pfb = sub.add_parser("flash-bios", help="Safely flash SPI BIOS region ONLY from 4/8 MiB ROM (--ifd -i bios)")
    pfb.add_argument("rom", type=pathlib.Path)
    pfb.add_argument("--chip", default=None, help="Optional flashrom -c chip override")
    pfb.add_argument("--yes", action="store_true", help="Skip interactive FLASH confirmation")

    sub.add_parser("self-test", help="Verify runtime CFR efivars, COM1+LPT1 active, WOL, and hwmon")
    return p


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    cmd = args.cmd

    if cmd is None or cmd == "tui":
        if not sys.stdin.isatty() or not sys.stdout.isatty():
            parser.error("Interactive TUI requires a TTY. Pass a subcommand (e.g. 'status', 'list', 'self-test').")
        return run_tui(args.efivars_dir)

    if cmd == "list":
        print(f"{'Option':<20} {'Form':<18} {'Val':<4} {'Setting':<30} {'Attrs':<10} {'Stored'}")
        print("-" * 100)
        for opt in CFR_OPTIONS:
            val, attrs, exists = read_cfr_option(opt, args.efivars_dir)
            attr_s = f"0x{attrs:08x}" if attrs is not None else "n/a"
            print(f"{opt.name:<20} {opt.form:<18} {val:<4} {opt.choices.get(val, '?'):<30} {attr_s:<10} {'yes' if exists else 'default'}")
        return 0

    if cmd == "get":
        opt = CFR_BY_NAME[args.option]
        val, attrs, exists = read_cfr_option(opt, args.efivars_dir)
        print(f"{opt.name}={val} ({opt.choices.get(val, '?')}) [attrs={'0x%08x' % attrs if attrs is not None else 'missing'}, stored={exists}]")
        return 0

    if cmd == "set":
        opt = CFR_BY_NAME[args.option]
        val = parse_cfr_value(opt, args.value)
        write_cfr_option(opt, val, args.efivars_dir)
        print(f"Updated {opt.name}={val} ({opt.choices[val]}) in {cfr_path(opt.name, args.efivars_dir)}. Reboot to apply.")
        return 0

    if cmd == "reset":
        for opt in CFR_OPTIONS:
            write_cfr_option(opt, opt.default, args.efivars_dir)
            print(f"Reset {opt.name}={opt.default} ({opt.choices[opt.default]})")
        return 0

    if cmd == "backup":
        data = backup_cfr_json(args.file, args.efivars_dir)
        print(f"Exported {len(data['options'])} CFR options to {args.file}")
        return 0

    if cmd == "restore":
        changed = restore_cfr_json(args.file, args.efivars_dir)
        if changed:
            print("Restored:\n  " + "\n  ".join(changed))
        else:
            print("All CFR options already match backup.")
        return 0

    if cmd == "status":
        info = get_system_info()
        wol = get_wol(DEFAULT_NIC)
        print(f"Host   : {info['hostname']} | Kernel: {info['kernel']}")
        print(f"Board  : {info['board']} | BIOS: {info['bios_vendor']} {info['bios_version']} ({info['bios_date']})")
        print(f"CPU    : {info['cpu_model']} ({info['cpu_threads']} threads) | RAM: {info['mem_gib']} GiB")
        print(f"NIC    : {info['nic_ip4']} | WOL: active={wol['active']} (supports={wol['supports']})")
        print(f"Serial : COM1 (0x3f8)={'ACTIVE' if info['com1_active'] else 'OFF'} | Parallel LPT1 (0x378)={'ACTIVE' if info['lpt1_active'] else 'DISABLED'}")
        sb = info["secure_boot"]
        sz = sb["sizes"]
        sb_st = "Enabled" if sb["enabled"] else ("Disabled" if sb["supported"] else "Unsupported")
        print(
            f"SecBoot: {sb_st} ({'SetupMode' if sb['setup_mode'] else 'UserMode'}, "
            f"VendorKeys={sb['vendor_keys']}, PK={sz['PK']}B KEK={sz['KEK']}B db={sz['db']}B dbx={sz['dbx']}B)"
        )
        nvmes = info["nvme_devices"]
        print("NVMe   : " + (", ".join(f"{d['name']} ({d['model']})" for d in nvmes) if nvmes else "none installed (NvmExpressDxe enabled in UEFI)"))
        print("\nACPI Wakeup:")
        for r in get_acpi_wakeup():
            if r["status"] == "enabled" or r["device"] in ("RP01", "RP04", "PEGP", "EHC1", "EHC2", "PBTN"):
                print(f"  {r['device']:<6} {r['s_state']:<4} {r['status']:<9} {r['sysfs']}")
        print("\nSensors:")
        for s in get_sensors():
            print(f"  [{s['hwmon']}] {s['name']}:")
            if s["temps"]:
                print("    Temps: " + ", ".join(f"{t['label']}={t['c']:.1f}C" for t in s["temps"]))
            if s["fans"]:
                print("    Fans : " + ", ".join(f"{f['label']}={f['rpm']} RPM" for f in s["fans"]))
            if s["pwms"]:
                print("    PWM  : " + ", ".join(f"{p['id']}={p['pct']}% (en={p['enable']})" for p in s["pwms"]))
        return 0

    if cmd == "wol":
        ok, msg = set_wol(args.iface, args.state == "on")
        print(msg)
        return 0 if ok else 1

    if cmd == "wakeup":
        desired = None if args.state == "toggle" else (args.state == "on")
        ok, msg = set_acpi_wakeup(args.device, desired)
        print(msg)
        return 0 if ok else 1

    if cmd == "reboot-uefi":
        ok, msg = reboot_to_uefi(args.now)
        print(msg)
        return 0 if ok else 1

    if cmd == "s3":
        ok, msg = suspend_s3(args.seconds)
        print(msg)
        return 0 if ok else 1

    if cmd == "backup-bios":
        ok, msg = flashrom_backup_bios(args.out, args.chip)
        print(msg)
        return 0 if ok else 1

    if cmd == "flash-bios":
        if not args.yes:
            chip_hint = args.chip or "auto (W25Q32/W25Q64)"
            ans = input(f"Flash SPI BIOS region ({chip_hint}) from {args.rom}? Type FLASH to proceed: ").strip()
            if ans != "FLASH":
                print("Cancelled.")
                return 1
        ok, msg = flashrom_write_bios(args.rom, args.chip)
        print(msg)
        return 0 if ok else 1

    if cmd == "self-test":
        ok, logs = self_test(args.efivars_dir)
        print("H61M-S1 PLUS Self-Test:")
        for l in logs:
            print(l)
        print(f"RESULT: {'PASS' if ok else 'WARN/FAIL'}")
        return 0 if ok else 1

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
