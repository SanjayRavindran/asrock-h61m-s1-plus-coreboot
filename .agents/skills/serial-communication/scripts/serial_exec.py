"""Run commands non-interactively on the H61M-S1 PLUS Linux serial console via COM5.

Reuses com_serial.py's Win32 CreateFileW helpers to avoid WCH CH340 driver Error 31
with pyserial/.NET SerialPort SetCommState().
"""

import argparse
import base64
import os
import re
import shlex
import sys
import time

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)
import com_serial  # noqa: E402

ANSI_RE = re.compile(
    r"\x1b(?:\][^\x07\x1b]*(?:\x07|\x1b\\)|\[[0-?]*[ -/]*[@-~]|[@-Z_\\-])"
)


def clean_text(data: bytes) -> str:
    txt = data.decode("utf-8", errors="replace")
    txt = ANSI_RE.sub("", txt)
    txt = txt.replace("\r\n", "\n").replace("\r", "\n")
    return txt


def slow_write(
    h, text: str, baud: int = 115200, chunk_size: int = 16, min_delay: float = 0.005
) -> None:
    raw = text.encode("utf-8")
    delay = max(min_delay, (chunk_size * 10.5) / max(baud, 1200))
    for i in range(0, len(raw), chunk_size):
        com_serial.write_bytes(h, raw[i : i + chunk_size])
        time.sleep(delay)


def read_until(h, predicate, timeout: float = 5.0) -> tuple[bool, bytes]:
    buf = bytearray()
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        chunk = com_serial.read_chunk(h, 4096)
        if chunk:
            buf.extend(chunk)
            if predicate(bytes(buf)):
                return True, bytes(buf)
        else:
            time.sleep(0.02)
    return False, bytes(buf)


def drain(h, wait: float = 0.25) -> bytes:
    buf = bytearray()
    deadline = time.monotonic() + wait
    while time.monotonic() < deadline:
        chunk = com_serial.read_chunk(h, 4096)
        if chunk:
            buf.extend(chunk)
            deadline = time.monotonic() + 0.1
        else:
            time.sleep(0.02)
    return bytes(buf)


def try_connect_at_baud(port: str, baud: int, user: str, password: str):
    h, _ = com_serial.open_com_port(port, baud=baud, read_timeout_ms=100, purge=True)
    user_marker = f"{user}@".encode("utf-8")
    prompt_tokens = (b"login:", b"password:", b"$ ", b"# ", b":~", user_marker)
    try:
        slow_write(h, "\r\n", baud=baud)
        ok, raw = read_until(
            h,
            lambda b: any(tok in b.lower() for tok in prompt_tokens),
            timeout=3.5,
        )
        txt = clean_text(raw)

        if not ok and not txt.strip():
            slow_write(h, "\r\n", baud=baud)
            ok, raw2 = read_until(
                h,
                lambda b: any(tok in b.lower() for tok in prompt_tokens),
                timeout=3.0,
            )
            raw += raw2
            txt = clean_text(raw)

        if not raw:
            com_serial.k32.CloseHandle(h)
            return None, 0, f"no data at {baud}"

        printable = sum(1 for c in txt if c == "\n" or c == "\t" or 32 <= ord(c) <= 126)
        if len(txt) > 0 and (printable / len(txt)) < 0.6:
            com_serial.k32.CloseHandle(h)
            return None, 0, f"garbled data at {baud}"

        lower = txt.lower()
        if "password:" in lower:
            slow_write(h, "\n", baud=baud)
            drain(h, 0.5)
            slow_write(h, "\r\n", baud=baud)
            _, raw_l = read_until(h, lambda b: b"login:" in b.lower(), timeout=5.0)
            txt += clean_text(raw_l)
            lower = txt.lower()

        if "login:" in lower:
            slow_write(h, f"{user}\n", baud=baud)
            _, raw_pw = read_until(
                h,
                lambda b: b"password:" in b.lower() or b"$ " in b or b"# " in b,
                timeout=5.0,
            )
            txt += clean_text(raw_pw)
            if b"password:" in raw_pw.lower():
                slow_write(h, f"{password}\n", baud=baud)
                _, raw_sh = read_until(
                    h,
                    lambda b: (
                        b"$ " in b
                        or b"# " in b
                        or b"incorrect" in b.lower()
                        or b"failed" in b.lower()
                    ),
                    timeout=8.0,
                )
                txt += clean_text(raw_sh)
                if b"incorrect" in raw_sh.lower() or b"failed" in raw_sh.lower():
                    com_serial.k32.CloseHandle(h)
                    return None, 0, f"login failed at {baud}"

        slow_write(h, "printf '%s%s\\n' '__SHELL_' 'READY__'\n", baud=baud)
        ok_ready, _ = read_until(h, lambda b: b"__SHELL_READY__" in b, timeout=5.0)
        if ok_ready:
            drain(h, 0.25)
            return h, baud, f"connected at {baud}"

        com_serial.k32.CloseHandle(h)
        return None, 0, f"no shell prompt at {baud}: {txt!r}"
    except Exception:
        com_serial.k32.CloseHandle(h)
        raise


def run_cmd(
    h, cmd: str, tag: str, timeout: float = 25.0, baud: int = 115200
) -> tuple[bool, str]:
    begin_marker = f"__BEGIN_{tag}__"
    end_marker = f"__END_{tag}__"
    b64 = base64.b64encode(cmd.encode("utf-8")).decode("ascii")
    # Single-line eval prevents sudo's tcsetattr(TCSAFLUSH) from wiping queued lines in ttyS0 RX.
    full_cmd = (
        f"printf '%s%s\\n' '__BEGIN_' '{tag}__'; "
        f"eval \"$(printf '%s' '{b64}' | base64 -d)\"; "
        f"printf '\\n%s%s\\n' '__END_' '{tag}__'\n"
    )
    drain(h, 0.1)
    slow_write(h, full_cmd, baud=baud)
    ok, raw = read_until(h, lambda b: end_marker.encode("ascii") in b, timeout=timeout)
    raw += drain(h, 0.25)
    txt = clean_text(raw)
    if begin_marker in txt:
        txt = txt.split(begin_marker, 1)[1]
    if end_marker in txt:
        txt = txt.split(end_marker, 1)[0]
    if not ok:
        txt += f"\n[WARNING: timed out waiting for {end_marker} after {timeout}s]\n"
    return ok, txt.strip() + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Execute commands over Windows COM serial to Linux serial-getty."
    )
    parser.add_argument("--port", default="COM5")
    parser.add_argument("--baud", type=int, default=115200)
    parser.add_argument("--fallback-baud", type=int, default=9600)
    parser.add_argument("--user", default="zero")
    parser.add_argument("--password", default="sanjay")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--cmd", help="Shell command string to run")
    group.add_argument("--cmd-file", help="Path to local shell script/command file")
    parser.add_argument("--timeout", type=float, default=25.0)
    parser.add_argument("--outfile", help="Optional path to save command output")
    parser.add_argument(
        "--sudo",
        action="store_true",
        help="Validate sudo using --password before executing --cmd",
    )
    args = parser.parse_args()

    if args.cmd_file:
        with open(args.cmd_file, "r", encoding="utf-8") as f:
            cmd_text = f.read()
    else:
        cmd_text = args.cmd

    bauds = [args.baud]
    if args.fallback_baud and args.fallback_baud != args.baud:
        bauds.append(args.fallback_baud)

    h = None
    active_baud = args.baud
    errors = []
    for b in bauds:
        h, active_baud, msg = try_connect_at_baud(args.port, b, args.user, args.password)
        sys.stderr.write(f"[serial_exec] {msg}\n")
        if h is not None:
            break
        errors.append(msg)

    if h is None:
        sys.stderr.write("[serial_exec] ERROR: " + "; ".join(errors) + "\n")
        return 2

    rc = 0
    out_text = ""
    try:
        init_cmd = "stty cols 200 rows 50; stty -echo; export SYSTEMD_PAGER=cat PAGER=cat"
        if args.sudo:
            pw_q = shlex.quote(args.password)
            init_cmd += (
                f"; printf '%s\\n' {pw_q} | sudo -S -p '' true && echo __SUDO_OK__ || echo __SUDO_FAIL__"
            )
        ok_init, init_out = run_cmd(h, init_cmd, "INIT", timeout=15.0, baud=active_baud)
        if not ok_init:
            sys.stderr.write(
                f"[serial_exec] ERROR: shell initialization timed out: {init_out!r}\n"
            )
            return 3
        if args.sudo and "__SUDO_OK__" not in init_out:
            sys.stderr.write(f"[serial_exec] ERROR: sudo failed: {init_out!r}\n")
            return 3

        ok_cmd, out_text = run_cmd(
            h, cmd_text, "CMD", timeout=args.timeout, baud=active_baud
        )
        if not ok_cmd:
            rc = 1

        if args.outfile:
            out_dir = os.path.dirname(os.path.abspath(args.outfile))
            os.makedirs(out_dir, exist_ok=True)
            with open(args.outfile, "w", encoding="utf-8") as f:
                f.write(out_text)

        if hasattr(sys.stdout, "buffer"):
            sys.stdout.buffer.write(out_text.encode("utf-8", errors="replace"))
        else:
            sys.stdout.write(out_text)

        slow_write(h, "stty echo\n", baud=active_baud)
        drain(h, 0.15)
    finally:
        com_serial.k32.CloseHandle(h)

    return rc


if __name__ == "__main__":
    raise SystemExit(main())
