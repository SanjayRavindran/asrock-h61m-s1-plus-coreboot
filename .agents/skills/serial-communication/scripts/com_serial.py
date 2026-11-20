#!/usr/bin/env python3
r"""
Win32 Serial Helper for ASRock H61M-S1 PLUS Coreboot Bring-Up (COM5 <-> Board COM1 0x3f8).

Works around the WCH CH340 Windows driver 3.9.2024.9 bug where SetCommState()
fails with Win32 Error 31 (ERROR_GEN_FAILURE), breaking pyserial and .NET SerialPort.
Opens \\.\COMx directly with Win32 CreateFileW + SetCommTimeouts + ReadFile/WriteFile.
"""

import argparse
import ctypes
import ctypes.wintypes as w
import datetime
import os
import subprocess
import sys
import time

k32 = ctypes.windll.kernel32
GENERIC_READ = 0x80000000
GENERIC_WRITE = 0x40000000
OPEN_EXISTING = 3
INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value
PURGE_ALL = 0x000F


class DCB(ctypes.Structure):
    _fields_ = [
        ("DCBlength", w.DWORD),
        ("BaudRate", w.DWORD),
        ("flags", w.DWORD),
        ("wReserved", w.WORD),
        ("XonLim", w.WORD),
        ("XoffLim", w.WORD),
        ("ByteSize", w.BYTE),
        ("Parity", w.BYTE),
        ("StopBits", w.BYTE),
        ("XonChar", ctypes.c_char),
        ("XoffChar", ctypes.c_char),
        ("ErrorChar", ctypes.c_char),
        ("EofChar", ctypes.c_char),
        ("EvtChar", ctypes.c_char),
        ("wReserved1", w.WORD),
    ]


class COMMTIMEOUTS(ctypes.Structure):
    _fields_ = [
        ("ReadIntervalTimeout", w.DWORD),
        ("ReadTotalTimeoutMultiplier", w.DWORD),
        ("ReadTotalTimeoutConstant", w.DWORD),
        ("WriteTotalTimeoutMultiplier", w.DWORD),
        ("WriteTotalTimeoutConstant", w.DWORD),
    ]


class COMSTAT(ctypes.Structure):
    _fields_ = [
        ("flags", w.DWORD),
        ("cbInQue", w.DWORD),
        ("cbOutQue", w.DWORD),
    ]


k32.CreateFileW.restype = w.HANDLE


def open_com_port(port: str, baud: int = 115200, read_timeout_ms: int = 200, purge: bool = False):
    dev_path = port if port.startswith("\\\\.\\") else f"\\\\.\\{port}"
    h = k32.CreateFileW(dev_path, GENERIC_READ | GENERIC_WRITE, 0, None, OPEN_EXISTING, 0, None)
    if h == INVALID_HANDLE_VALUE:
        err = k32.GetLastError()
        raise RuntimeError(f"CreateFileW({dev_path}) failed with Win32 error {err}")

    dcb = DCB()
    dcb.DCBlength = ctypes.sizeof(DCB)
    if not k32.GetCommState(h, ctypes.byref(dcb)):
        err = k32.GetLastError()
        k32.CloseHandle(h)
        raise RuntimeError(f"GetCommState({dev_path}) failed with Win32 error {err}")

    if dcb.BaudRate != baud or dcb.ByteSize != 8 or dcb.Parity != 0 or dcb.StopBits != 0:
        k32.CloseHandle(h)
        port_name = port.replace("\\\\.\\", "")
        subprocess.run(
            ["cmd", "/c", f"mode {port_name} BAUD={baud} PARITY=n DATA=8 STOP=1"],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        h = k32.CreateFileW(dev_path, GENERIC_READ | GENERIC_WRITE, 0, None, OPEN_EXISTING, 0, None)
        if h == INVALID_HANDLE_VALUE:
            err = k32.GetLastError()
            raise RuntimeError(f"Re-open CreateFileW({dev_path}) failed with Win32 error {err}")
        k32.GetCommState(h, ctypes.byref(dcb))

    to = COMMTIMEOUTS(20, 0, read_timeout_ms, 0, 500)
    k32.SetCommTimeouts(h, ctypes.byref(to))
    if purge:
        k32.PurgeComm(h, PURGE_ALL)
    return h, dcb


def read_chunk(h, size: int = 512) -> bytes:
    errs = w.DWORD(0)
    comstat = COMSTAT()
    k32.ClearCommError(h, ctypes.byref(errs), ctypes.byref(comstat))
    buf = ctypes.create_string_buffer(size)
    nread = w.DWORD(0)
    ok = k32.ReadFile(h, buf, size, ctypes.byref(nread), None)
    if not ok:
        raise RuntimeError(f"ReadFile failed with Win32 error {k32.GetLastError()}")
    return buf.raw[: nread.value]


def write_bytes(h, data: bytes) -> int:
    nwritten = w.DWORD(0)
    ok = k32.WriteFile(h, data, len(data), ctypes.byref(nwritten), None)
    if not ok:
        raise RuntimeError(f"WriteFile failed with Win32 error {k32.GetLastError()}")
    return nwritten.value


def cmd_status(args):
    h, dcb = open_com_port(args.port, args.baud, purge=False)
    ms = w.DWORD(0)
    k32.GetCommModemStatus(h, ctypes.byref(ms))
    k32.CloseHandle(h)
    print(
        f"PORT={args.port} OPEN=OK baud={dcb.BaudRate} bits={dcb.ByteSize} "
        f"parity={dcb.Parity} stop={dcb.StopBits} flags=0x{dcb.flags:08x}"
    )
    print(
        f"MODEM=0x{ms.value:02x} CTS={bool(ms.value & 0x10)} "
        f"DSR={bool(ms.value & 0x20)} RING={bool(ms.value & 0x40)} RLSD={bool(ms.value & 0x80)}"
    )


def cmd_capture(args):
    h, dcb = open_com_port(args.port, args.baud, read_timeout_ms=200, purge=args.purge)
    print(
        f"[{datetime.datetime.now().isoformat(timespec='seconds')}] "
        f"Listening on {args.port} ({dcb.BaudRate} 8N1) for {args.duration}s..."
    )
    if args.outfile:
        os.makedirs(os.path.dirname(os.path.abspath(args.outfile)), exist_ok=True)
        out_f = open(args.outfile, "ab")
    else:
        out_f = None

    total = 0
    post_codes = []
    buf_acc = b""
    del_sent = False
    t0 = time.time()
    try:
        while time.time() - t0 < args.duration:
            chunk = read_chunk(h, 512)
            if chunk:
                total += len(chunk)
                buf_acc += chunk
                if out_f:
                    out_f.write(chunk)
                    out_f.flush()
                if args.raw_hex:
                    ts = datetime.datetime.now().strftime("%H:%M:%S.%f")[:-3]
                    ascii_preview = "".join(chr(b) if 32 <= b < 127 else "." for b in chunk)
                    print(f"[{ts}] ({len(chunk)}B) {chunk.hex(' ')} | {ascii_preview}", flush=True)
                else:
                    sys.stdout.write(chunk.decode("utf-8", errors="replace"))
                    sys.stdout.flush()
                if args.send_esc_on_boot and b"Press" in chunk:
                    write_bytes(h, b"\x1b")
                if args.send_del_on_boot and not del_sent and b"to select USB Boot Device" in buf_acc:
                    write_bytes(h, b"\x1b[3~")
                    time.sleep(0.15)
                    write_bytes(h, b"\x1b[3~")
                    del_sent = True
                if args.stop_on and args.stop_on.encode() in buf_acc:
                    print(f"\n[Matched stop pattern: {args.stop_on}]")
                    break
    finally:
        if out_f:
            out_f.close()
        k32.CloseHandle(h)

    for line in buf_acc.decode("utf-8", errors="replace").splitlines():
        if "POST:" in line:
            post_codes.append(line.strip())

    print(f"\n--- Capture Complete: {total} bytes received ---")
    if post_codes:
        print(f"POST codes seen ({len(post_codes)}): {', '.join(post_codes[-10:])}")


def cmd_send(args):
    h, _ = open_com_port(args.port, args.baud, read_timeout_ms=200, purge=False)
    try:
        if args.esc:
            payload = b"\x1b" * args.repeat
        elif args.del_key:
            payload = b"\x1b[3~" * args.repeat
        else:
            text = args.text.encode("utf-8").decode("unicode_escape").encode("latin1")
            if args.crlf and not text.endswith(b"\r\n"):
                text += b"\r\n"
            payload = text * args.repeat
        written = write_bytes(h, payload)
        print(f"Sent {written} bytes to {args.port}: {repr(payload)}")
        if args.read_wait > 0:
            t0 = time.time()
            rx = b""
            while time.time() - t0 < args.read_wait:
                rx += read_chunk(h, 512)
            print(f"Received ({len(rx)} bytes): {repr(rx)}")
    finally:
        k32.CloseHandle(h)


def cmd_loopback(args):
    import paramiko

    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(args.host, username=args.user, password=args.password, timeout=10)

    def ssh_run(cmd):
        i, o, e = c.exec_command(f"sudo -S -p '' {cmd}", timeout=15)
        i.write(args.password + "\n")
        i.flush()
        return o.read().decode(errors="replace").strip()

    print("BEFORE:", ssh_run("cat /proc/tty/driver/serial | head -n 2"))
    ssh_run(f"stty -F {args.remote_tty} {args.baud} cs8 -cstopb -parenb raw -echo -crtscts clocal")

    h, dcb = open_com_port(args.port, args.baud, read_timeout_ms=200, purge=True)
    try:
        chan1 = c.get_transport().open_session()
        chan1.exec_command(
            f"sudo -S -p '' bash -c \"for i in 1 2 3; do printf 'H61_COM1_PING_%s\\r\\n' \\$i > {args.remote_tty}; sleep 0.2; done\""
        )
        chan1.send(args.password + "\n")
        rx_win = b""
        t0 = time.time()
        while time.time() - t0 < 1.8:
            rx_win += read_chunk(h, 256)
        print(f"TX (.63 -> {args.port}): {len(rx_win)} bytes: {repr(rx_win)}")

        chan2 = c.get_transport().open_session()
        py_rd = (
            f"import os,select,time; fd=os.open('{args.remote_tty}',os.O_RDONLY|os.O_NONBLOCK); "
            "d=b''; t0=time.time()\n"
            "while time.time()-t0<1.8:\n"
            " r,_,_=select.select([fd],[],[],0.2)\n"
            " if r: d+=os.read(fd,256)\n"
            "os.close(fd); print('RX_ON_H61:',len(d),repr(d))"
        )
        chan2.exec_command(f"sudo -S -p '' python3 -c \"{py_rd}\"")
        chan2.send(args.password + "\n")
        time.sleep(0.25)
        for _ in range(3):
            write_bytes(h, b"WIN_COM5_PONG\r\n")
            time.sleep(0.2)
        print(chan2.makefile().read().decode(errors="replace").strip())
    finally:
        k32.CloseHandle(h)
        print("AFTER:", ssh_run("cat /proc/tty/driver/serial | head -n 2"))
        c.close()


def main():
    p = argparse.ArgumentParser(description="Win32 Serial Helper for H61M-S1+ Coreboot Bring-Up")
    p.add_argument("--port", default="COM5", help="Windows COM port (default: COM5)")
    p.add_argument("--baud", type=int, default=115200, help="Baud rate (default: 115200)")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("status", help="Check Windows COM port status without SetCommState Error 31")

    p_cap = sub.add_parser("capture", help="Capture serial boot log from COM port")
    p_cap.add_argument("--duration", type=float, default=60.0, help="Capture duration in seconds")
    p_cap.add_argument("--outfile", default="", help="Optional file path to save raw serial log")
    p_cap.add_argument("--purge", action="store_true", help="Purge RX/TX buffers before capture")
    p_cap.add_argument("--stop-on", default="", help="Stop early when substring appears in log")
    p_cap.add_argument("--send-esc-on-boot", action="store_true", help="Send ESC when prompt is seen")
    p_cap.add_argument("--send-del-on-boot", action="store_true", help="Send ANSI Delete (ESC[3~) when boot prompt is seen")
    p_cap.add_argument("--raw-hex", action="store_true", help="Print timestamped hex dump + ASCII preview")

    p_snd = sub.add_parser("send", help="Send text, ESC, or DEL key over COM port")
    p_snd.add_argument("--text", default="", help="Text string to send")
    p_snd.add_argument("--esc", action="store_true", help="Send ESC (0x1b) key")
    p_snd.add_argument("--del", dest="del_key", action="store_true", help="Send ANSI Delete (ESC[3~) key")
    p_snd.add_argument("--crlf", action="store_true", help="Append CRLF to text")
    p_snd.add_argument("--repeat", type=int, default=1, help="Repeat count")
    p_snd.add_argument("--read-wait", type=float, default=1.0, help="Seconds to read response")

    p_lb = sub.add_parser("loopback-test", help="Run two-way test against booted Linux host via SSH")
    p_lb.add_argument("--host", default="192.168.1.63")
    p_lb.add_argument("--user", default="zero")
    p_lb.add_argument("--password", default="sanjay")
    p_lb.add_argument("--remote-tty", default="/dev/ttyS0")

    args = p.parse_args()
    if args.cmd == "status":
        cmd_status(args)
    elif args.cmd == "capture":
        cmd_capture(args)
    elif args.cmd == "send":
        cmd_send(args)
    elif args.cmd == "loopback-test":
        cmd_loopback(args)


if __name__ == "__main__":
    main()
