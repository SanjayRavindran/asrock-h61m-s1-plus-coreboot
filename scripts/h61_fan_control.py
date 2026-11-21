#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""
ASRock H61M-S1 PLUS — Fail-Safe Combined GPU + CPU Fan Control Daemon

Monitors:
  1. NVIDIA GPU temperature (via libnvidia-ml / NVML ctypes, falling back to nvidia-smi)
  2. CPU package temperature (via NCT6776F PECI Agent 0, falling back to coretemp)
  3. Motherboard ambient temperature (via NCT6776F SYSTIN)

Drives NCT6776F pwm1 and pwm2 (H61M-S1 PLUS shares CFANOUT across CPU_FAN1 pin 4
and CHA_FAN1 pin 4) using manual mode (pwm*_enable=1) from the maximum required duty
of GPU (100% at >= 60 C by default), CPU, and M/B curves with asymmetric smoothing and
2.0 C cooldown hysteresis. Always restores hardware SmartFan IV (pwm*_enable=5)
cleanly on exit/SIGTERM/SIGINT or via systemd ExecStopPost `--restore-hw`.
"""

from __future__ import annotations

import argparse
import ctypes
import ctypes.util
import pathlib
import shutil
import signal
import subprocess
import sys
import time
from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Tuple

HWMON_BASE = pathlib.Path("/sys/class/hwmon")
PCI_DEVICES = pathlib.Path("/sys/bus/pci/devices")
NVIDIA_PCI_VENDOR = "0x10de"

DEFAULT_GPU_FULL_TEMP_C = 60.0
MIN_DUTY_PCT = 30.0
MAX_DUTY_PCT = 100.0
MIN_PWM_RAW = 76
MAX_PWM_RAW = 255
FAILSAFE_GPU_UNREADABLE_PCT = 75.0
HYSTERESIS_C = 2.0
MAX_STEP_UP_PCT = 25.0
MAX_STEP_DOWN_PCT = 4.0

CPU_CURVE: List[Tuple[float, float]] = [
    (40.0, 30.0),
    (55.0, 50.0),
    (70.0, 80.0),
    (85.0, 100.0),
]

MB_CURVE: List[Tuple[float, float]] = [
    (45.0, 30.0),
    (55.0, 60.0),
    (65.0, 100.0),
]


def build_gpu_curve(gpu_full_temp: float = DEFAULT_GPU_FULL_TEMP_C) -> List[Tuple[float, float]]:
    """Build piecewise-linear GPU temp->duty curve hitting 100% at gpu_full_temp."""
    base_low = 35.0
    if gpu_full_temp <= base_low + 4.0:
        gpu_full_temp = base_low + 4.0
    span = gpu_full_temp - base_low
    return [
        (base_low, 30.0),
        (round(base_low + span * (7.0 / 25.0), 1), 45.0),
        (round(base_low + span * (13.0 / 25.0), 1), 60.0),
        (round(base_low + span * (19.0 / 25.0), 1), 80.0),
        (round(gpu_full_temp, 1), 100.0),
    ]


def interpolate_curve(temp_c: float, points: Sequence[Tuple[float, float]]) -> float:
    """Linearly interpolate fan duty % across sorted (temp_c, duty_pct) points."""
    if temp_c <= points[0][0]:
        return points[0][1]
    for (t0, d0), (t1, d1) in zip(points, points[1:]):
        if temp_c <= t1:
            if t1 <= t0:
                return d1
            return d0 + (temp_c - t0) * (d1 - d0) / (t1 - t0)
    return points[-1][1]


def pct_to_pwm(pct: float) -> int:
    clamped_pct = max(MIN_DUTY_PCT, min(MAX_DUTY_PCT, pct))
    return max(MIN_PWM_RAW, min(MAX_PWM_RAW, int(round(clamped_pct * 255.0 / 100.0))))


def read_text_safe(path: pathlib.Path) -> Optional[str]:
    try:
        return path.read_text(encoding="utf-8", errors="replace").strip()
    except OSError:
        return None


def write_text_safe(path: pathlib.Path, value: str) -> bool:
    try:
        path.write_text(f"{value}\n", encoding="utf-8")
        return True
    except OSError:
        return False


def find_hwmon_by_name(target_name: str) -> Optional[pathlib.Path]:
    if not HWMON_BASE.exists():
        return None
    for hw in sorted(HWMON_BASE.iterdir()):
        if read_text_safe(hw / "name") == target_name:
            return hw
    return None


def find_labeled_temp_c(hw: Optional[pathlib.Path], label: str) -> Optional[float]:
    if not hw or not hw.exists():
        return None
    for idx in range(1, 20):
        lbl = read_text_safe(hw / f"temp{idx}_label")
        if lbl == label:
            raw = read_text_safe(hw / f"temp{idx}_input")
            if raw is not None:
                try:
                    return int(raw) / 1000.0
                except ValueError:
                    return None
    return None


def detect_nvidia_pci_present() -> bool:
    if not PCI_DEVICES.exists():
        return False
    for dev in PCI_DEVICES.iterdir():
        ven = read_text_safe(dev / "vendor")
        if ven and ven.lower() == NVIDIA_PCI_VENDOR:
            return True
    return False


class NvmlReader:
    """Zero-fork NVML temperature reader with nvidia-smi subprocess fallback."""

    def __init__(self) -> None:
        self._lib = None
        self._init_ok = False
        self._handles: List[ctypes.c_void_p] = []

    def _ensure_init(self) -> bool:
        if self._init_ok and self._handles:
            return True
        lib_name = ctypes.util.find_library("nvidia-ml") or "libnvidia-ml.so.1"
        try:
            lib = ctypes.CDLL(lib_name)
            if lib.nvmlInit_v2() != 0:
                return False
            count = ctypes.c_uint(0)
            if lib.nvmlDeviceGetCount_v2(ctypes.byref(count)) != 0 or count.value == 0:
                lib.nvmlShutdown()
                return False
            handles: List[ctypes.c_void_p] = []
            for idx in range(count.value):
                h = ctypes.c_void_p()
                if lib.nvmlDeviceGetHandleByIndex_v2(idx, ctypes.byref(h)) == 0:
                    handles.append(h)
            if not handles:
                lib.nvmlShutdown()
                return False
            self._lib = lib
            self._handles = handles
            self._init_ok = True
            return True
        except OSError:
            return False

    def shutdown(self) -> None:
        if self._lib is not None and self._init_ok:
            try:
                self._lib.nvmlShutdown()
            except Exception:
                pass
        self._init_ok = False
        self._handles = []

    def read_max_temp_c(self) -> Optional[float]:
        if self._ensure_init() and self._lib is not None:
            temps: List[float] = []
            for h in self._handles:
                t = ctypes.c_uint(0)
                if self._lib.nvmlDeviceGetTemperature(h, 0, ctypes.byref(t)) == 0:
                    temps.append(float(t.value))
            if temps:
                return max(temps)
            self.shutdown()

        nsmi = shutil.which("nvidia-smi")
        if not nsmi:
            return None
        try:
            proc = subprocess.run(
                [nsmi, "--query-gpu=temperature.gpu", "--format=csv,noheader,nounits"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if proc.returncode != 0:
                return None
            vals = [float(line.strip()) for line in proc.stdout.splitlines() if line.strip()]
            return max(vals) if vals else None
        except (OSError, subprocess.SubprocessError, ValueError):
            return None


@dataclass
class ThermalState:
    gpu_c: Optional[float]
    cpu_c: Optional[float]
    mb_c: Optional[float]
    cha_rpm: int
    cpu_rpm: int
    pwm1_now: int
    pwm2_now: int
    pwm1_en: str
    pwm2_en: str


class ChannelLatch:
    """Applies upward instant-latch and downward cooldown hysteresis per sensor."""

    def __init__(self, hyst_c: float = HYSTERESIS_C) -> None:
        self.hyst_c = hyst_c
        self.effective: Dict[str, float] = {}

    def update(self, key: str, raw_c: Optional[float]) -> Optional[float]:
        if raw_c is None:
            self.effective.pop(key, None)
            return None
        prev = self.effective.get(key)
        if prev is None or raw_c >= prev or (prev - raw_c) >= self.hyst_c:
            self.effective[key] = raw_c
        return self.effective[key]


class FanController:
    """Combines GPU + CPU + M/B thermal curves with hysteresis and smoothing."""

    def __init__(
        self,
        gpu_full_temp: float = DEFAULT_GPU_FULL_TEMP_C,
        hyst_c: float = HYSTERESIS_C,
    ) -> None:
        self.gpu_full_temp = gpu_full_temp
        self.gpu_curve = build_gpu_curve(gpu_full_temp)
        self.latch = ChannelLatch(hyst_c=hyst_c)
        self.cur_pct: Optional[float] = None
        self.gpu_fail_streak = 0

    def compute_target(
        self,
        gpu_c: Optional[float],
        cpu_c: Optional[float],
        mb_c: Optional[float],
        gpu_expected: bool,
    ) -> Tuple[float, str, bool]:
        if cpu_c is None:
            return MAX_DUTY_PCT, "failsafe-cpu", True

        if gpu_c is None and gpu_expected:
            self.gpu_fail_streak += 1
        else:
            self.gpu_fail_streak = 0

        eff_gpu = self.latch.update("gpu", gpu_c)
        eff_cpu = self.latch.update("cpu", cpu_c)
        eff_mb = self.latch.update("mb", mb_c)

        candidates: List[Tuple[float, str]] = [
            (interpolate_curve(eff_cpu if eff_cpu is not None else cpu_c, CPU_CURVE), "cpu"),
        ]
        if eff_mb is not None:
            candidates.append((interpolate_curve(eff_mb, MB_CURVE), "mb"))
        if eff_gpu is not None:
            candidates.append((interpolate_curve(eff_gpu, self.gpu_curve), "gpu"))
        elif gpu_expected and self.gpu_fail_streak >= 3:
            candidates.append((FAILSAFE_GPU_UNREADABLE_PCT, "failsafe-gpu"))

        best_pct, best_src = max(candidates, key=lambda item: (item[0], 1 if item[1] == "gpu" else 0))
        emergency = bool(
            (gpu_c is not None and gpu_c >= self.gpu_full_temp)
            or cpu_c >= CPU_CURVE[-1][0]
            or (mb_c is not None and mb_c >= MB_CURVE[-1][0])
        )
        return best_pct, best_src, emergency

    def step(
        self,
        gpu_c: Optional[float],
        cpu_c: Optional[float],
        mb_c: Optional[float],
        gpu_expected: bool,
    ) -> Tuple[float, int, str]:
        target_pct, src, emergency = self.compute_target(gpu_c, cpu_c, mb_c, gpu_expected)
        if self.cur_pct is None or emergency:
            next_pct = target_pct
        elif target_pct > self.cur_pct:
            next_pct = min(target_pct, self.cur_pct + MAX_STEP_UP_PCT)
        elif target_pct < self.cur_pct:
            next_pct = max(target_pct, self.cur_pct - MAX_STEP_DOWN_PCT)
        else:
            next_pct = self.cur_pct
        self.cur_pct = max(MIN_DUTY_PCT, min(MAX_DUTY_PCT, next_pct))
        return self.cur_pct, pct_to_pwm(self.cur_pct), src


def read_thermal_state(nct: Optional[pathlib.Path], core: Optional[pathlib.Path], nvml: NvmlReader) -> ThermalState:
    gpu_c = nvml.read_max_temp_c()
    cpu_c = find_labeled_temp_c(nct, "PECI Agent 0")
    if cpu_c is None:
        cpu_c = find_labeled_temp_c(core, "Package id 0")
    mb_c = find_labeled_temp_c(nct, "SYSTIN")

    def _read_int(path: Optional[pathlib.Path]) -> int:
        if not path:
            return 0
        txt = read_text_safe(path)
        try:
            return int(txt) if txt is not None else 0
        except ValueError:
            return 0

    return ThermalState(
        gpu_c=gpu_c,
        cpu_c=cpu_c,
        mb_c=mb_c,
        cha_rpm=_read_int(nct / "fan1_input" if nct else None),
        cpu_rpm=_read_int(nct / "fan2_input" if nct else None),
        pwm1_now=_read_int(nct / "pwm1" if nct else None),
        pwm2_now=_read_int(nct / "pwm2" if nct else None),
        pwm1_en=(read_text_safe(nct / "pwm1_enable") if nct else None) or "?",
        pwm2_en=(read_text_safe(nct / "pwm2_enable") if nct else None) or "?",
    )


def restore_hw_smartfan(nct: Optional[pathlib.Path] = None) -> bool:
    hw = nct or find_hwmon_by_name("nct6776")
    if not hw:
        return False
    ok1 = write_text_safe(hw / "pwm1_enable", "5")
    ok2 = write_text_safe(hw / "pwm2_enable", "5")
    return ok1 and ok2


def apply_manual_pwm(nct: pathlib.Path, pwm_val: int) -> bool:
    ok = True
    for idx in (1, 2):
        en_path = nct / f"pwm{idx}_enable"
        if read_text_safe(en_path) != "1":
            ok = write_text_safe(en_path, "1") and ok
        ok = write_text_safe(nct / f"pwm{idx}", str(pwm_val)) and ok
    return ok


def run_self_test() -> int:
    ctrl = FanController(gpu_full_temp=DEFAULT_GPU_FULL_TEMP_C, hyst_c=2.0)

    def _near(val: float, expected: float, tol: float = 0.2) -> bool:
        return abs(val - expected) <= tol

    checks: List[Tuple[str, bool]] = []
    # GPU curve checkpoints (hitting 100% at >= 60 C)
    p35, src35, _ = ctrl.compute_target(35.0, 35.0, 32.0, True)
    checks.append((f"GPU 35C -> {p35:.1f}% == 30.0%", _near(p35, 30.0)))
    p48, _, _ = ctrl.compute_target(48.0, 35.0, 32.0, True)
    checks.append((f"GPU 48C -> {p48:.1f}% == 60.0%", _near(p48, 60.0)))
    p54, _, _ = ctrl.compute_target(54.0, 35.0, 32.0, True)
    checks.append((f"GPU 54C -> {p54:.1f}% == 80.0%", _near(p54, 80.0)))
    p60, src60, em60 = ctrl.compute_target(60.0, 35.0, 32.0, True)
    checks.append((f"GPU 60C -> {p60:.1f}% == 100.0% (src={src60}, em={em60})", _near(p60, 100.0) and src60 == "gpu" and em60))
    p65, _, _ = ctrl.compute_target(65.0, 35.0, 32.0, True)
    checks.append((f"GPU 65C -> {p65:.1f}% == 100.0%", _near(p65, 100.0)))

    # Hysteresis hold vs release + emergency + cooldown smoothing
    sm = FanController(gpu_full_temp=60.0, hyst_c=2.0)
    pct_e, pwm_e, _ = sm.step(60.0, 36.0, 32.0, True)
    checks.append((f"Emergency 60C immediate -> {pct_e:.1f}% (pwm={pwm_e})", _near(pct_e, 100.0) and pwm_e == 255))
    pct_hold, _, _ = sm.step(58.5, 36.0, 32.0, True)
    checks.append((f"Hysteresis hold 58.5C -> {pct_hold:.1f}% == 100.0%", _near(pct_hold, 100.0)))
    pct_cool, _, _ = sm.step(57.5, 36.0, 32.0, True)
    checks.append((f"Hysteresis release 57.5C -> {pct_cool:.1f}% == 96.0%", _near(pct_cool, 96.0)))

    # CPU dominance when GPU is cool
    cpu_ctrl = FanController(gpu_full_temp=60.0, hyst_c=2.0)
    cp55, csrc, _ = cpu_ctrl.compute_target(35.0, 55.0, 32.0, True)
    checks.append((f"CPU 55C (GPU 35C) -> {cp55:.1f}% == 50.0% (src={csrc})", _near(cp55, 50.0) and csrc == "cpu"))
    cp70, _, _ = cpu_ctrl.compute_target(35.0, 70.0, 32.0, True)
    checks.append((f"CPU 70C (GPU 35C) -> {cp70:.1f}% == 80.0%", _near(cp70, 80.0)))
    cp85, _, _ = cpu_ctrl.compute_target(35.0, 85.0, 32.0, True)
    checks.append((f"CPU 85C -> {cp85:.1f}% == 100.0%", _near(cp85, 100.0)))

    for desc, ok in checks:
        print(f"  [{'PASS' if ok else 'FAIL'}] {desc}")
    all_ok = all(ok for _, ok in checks)
    print(f"RESULT: {'PASS' if all_ok else 'FAIL'}")
    return 0 if all_ok else 1


def main(argv: Optional[List[str]] = None) -> int:
    p = argparse.ArgumentParser(description="ASRock H61M-S1 PLUS GPU + CPU Fan Control")
    p.add_argument("--interval", type=float, default=2.0, help="Poll interval seconds (default: 2.0)")
    p.add_argument("--gpu-full-temp", type=float, default=DEFAULT_GPU_FULL_TEMP_C, help="GPU temp for 100%% fan speed (default: 60.0 C)")
    p.add_argument("--log-delta", type=float, default=5.0, help="Log daemon duty changes >= DELTA%% (default: 5.0)")
    p.add_argument("--once", action="store_true", help="Print live temps and target duty once without modifying PWM")
    p.add_argument("--self-test", action="store_true", help="Run thermal curve & hysteresis unit tests")
    p.add_argument("--restore-hw", action="store_true", help="Restore NCT6776F SmartFan IV mode 5 and exit")
    p.add_argument("--test-override-gpu", type=float, default=None, help="Bounded live verification substituting GPU temp (C)")
    p.add_argument("--duration", type=float, default=10.0, help="Seconds to run --test-override-gpu before restoring mode 5")
    args = p.parse_args(argv)

    if args.self_test:
        return run_self_test()

    nct = find_hwmon_by_name("nct6776")
    if args.restore_hw:
        ok = restore_hw_smartfan(nct)
        print("Restored NCT6776F pwm1_enable=5, pwm2_enable=5" if ok else "ERROR: Failed to restore NCT6776F SmartFan IV mode 5")
        return 0 if ok else 1

    if not nct:
        print("ERROR: nct6776 hwmon device not found.", file=sys.stderr)
        return 1

    core = find_hwmon_by_name("coretemp")
    nvml = NvmlReader()
    gpu_expected = detect_nvidia_pci_present()
    ctrl = FanController(gpu_full_temp=args.gpu_full_temp)

    if args.once:
        try:
            st = read_thermal_state(nct, core, nvml)
            pct, pwm_target, src = ctrl.step(st.gpu_c, st.cpu_c, st.mb_c, gpu_expected)
            print(
                f"GPU={st.gpu_c if st.gpu_c is not None else 'n/a'} C | "
                f"CPU(PECI)={st.cpu_c if st.cpu_c is not None else 'n/a'} C | "
                f"MB={st.mb_c if st.mb_c is not None else 'n/a'} C | "
                f"Target={pct:.1f}% (pwm={pwm_target}, src={src}) | "
                f"Actual pwm1={st.pwm1_now}/255 (en={st.pwm1_en}) pwm2={st.pwm2_now}/255 (en={st.pwm2_en}) | "
                f"CHA_FAN1={st.cha_rpm} RPM CPU_FAN1={st.cpu_rpm} RPM"
            )
            return 0
        finally:
            nvml.shutdown()

    stop_requested = False

    def _handle_sig(_signum, _frame):
        nonlocal stop_requested
        stop_requested = True

    signal.signal(signal.SIGTERM, _handle_sig)
    signal.signal(signal.SIGINT, _handle_sig)

    start_ts = time.monotonic()
    last_logged_pct: Optional[float] = None
    last_src = ""
    override = args.test_override_gpu

    print(
        f"h61-fan-control starting: nct6776={nct.name}, gpu_expected={gpu_expected}, "
        f"gpu_full_temp={args.gpu_full_temp:.1f} C, interval={args.interval:.1f}s",
        flush=True,
    )

    try:
        while not stop_requested:
            st = read_thermal_state(nct, core, nvml)
            eff_gpu_in = override if override is not None else st.gpu_c
            pct, pwm_val, src = ctrl.step(eff_gpu_in, st.cpu_c, st.mb_c, gpu_expected)
            if not apply_manual_pwm(nct, pwm_val):
                print("WARNING: Failed writing PWM sysfs attributes", file=sys.stderr, flush=True)

            should_log = (
                override is not None
                or last_logged_pct is None
                or abs(pct - last_logged_pct) >= args.log_delta
                or (src != last_src and src.startswith("failsafe"))
            )
            if should_log:
                print(
                    f"GPU={eff_gpu_in if eff_gpu_in is not None else 'n/a'}C "
                    f"CPU={st.cpu_c if st.cpu_c is not None else 'n/a'}C "
                    f"MB={st.mb_c if st.mb_c is not None else 'n/a'}C -> "
                    f"duty={pct:.1f}% (pwm={pwm_val}/255, src={src}) "
                    f"[CHA_FAN1={st.cha_rpm} RPM, CPU_FAN1={st.cpu_rpm} RPM]",
                    flush=True,
                )
                last_logged_pct = pct
                last_src = src

            if override is not None and (time.monotonic() - start_ts) >= args.duration:
                break
            time.sleep(args.interval)
    finally:
        restored = restore_hw_smartfan(nct)
        nvml.shutdown()
        print(f"h61-fan-control stopped cleanly (SmartFan IV mode 5 restored={restored}).", flush=True)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
