#!/usr/bin/env bash
set -euo pipefail

# Assemble a flashable 4 MiB or 8 MiB SPI image from:
#   - User's stock SPI dump (--stock-dump) OR explicit --ifd + --me binaries
#   - Open-source Coreboot BIOS region (2.5M / 3.875M for 4 MiB, 6.5M / 7.875M for 8 MiB)
# Optional:
#   --vbt <data.vbt>       Inject user-extracted desktop VBT into CBFS as vbt.bin
#   --me-cleaner <py>      Run me_cleaner.py -S to strip non-essential ME partitions & set AltMeDisable
#   --bios-offset <hex>    Override BIOS region offset (default: 0x180000; 0x020000 for minimal ME)
#   --rom-size <bytes>     Target SPI ROM size in bytes: 4194304 or 8388608 (default: auto from BIOS size)

STOCK_DUMP=""
IFD_FILE=""
ME_FILE=""
BIOS_REGION=""
OUT_ROM=""
VBT_FILE=""
ME_CLEANER=""
BIOS_OFFSET=""
ROM_SIZE=""
CBFSTOOL="${CBFSTOOL:-cbfstool}"

while [ $# -gt 0 ]; do
  case "$1" in
    --stock-dump) STOCK_DUMP="$2"; shift 2 ;;
    --ifd) IFD_FILE="$2"; shift 2 ;;
    --me) ME_FILE="$2"; shift 2 ;;
    --bios-region) BIOS_REGION="$2"; shift 2 ;;
    --out) OUT_ROM="$2"; shift 2 ;;
    --vbt) VBT_FILE="$2"; shift 2 ;;
    --me-cleaner) ME_CLEANER="$2"; shift 2 ;;
    --bios-offset) BIOS_OFFSET="$2"; shift 2 ;;
    --rom-size) ROM_SIZE="$2"; shift 2 ;;
    --cbfstool) CBFSTOOL="$2"; shift 2 ;;
    *) echo "Unknown arg: $1" >&2; exit 2 ;;
  esac
done

if [ -z "$BIOS_REGION" ] || [ -z "$OUT_ROM" ] || { [ -z "$STOCK_DUMP" ] && { [ -z "$IFD_FILE" ] || [ -z "$ME_FILE" ]; }; }; then
  echo "Usage: $0 (--stock-dump <stock.bin> | --ifd <ifd.bin> --me <me.bin>) --bios-region <bios.bin> --out <full.rom> [--vbt data.vbt] [--me-cleaner path/to/me_cleaner.py] [--bios-offset 0x180000] [--rom-size 8388608]" >&2
  exit 2
fi

python3 - "$STOCK_DUMP" "$IFD_FILE" "$ME_FILE" "$BIOS_REGION" "$OUT_ROM" "$BIOS_OFFSET" "$ROM_SIZE" <<'PY'
import hashlib, struct, sys

stock_path, ifd_path, me_path, bios_path, out_path, off_s, rom_s = sys.argv[1:8]
bios = open(bios_path, "rb").read()

if stock_path:
    stock = open(stock_path, "rb").read()
    if len(stock) not in (4194304, 8388608):
        raise SystemExit(f"Stock dump must be 4 MiB or 8 MiB, got {len(stock)}")
    bios_off = int(off_s, 0) if off_s else 0x180000
    ifd = bytearray(stock[:0x1000])
    me = stock[0x1000:bios_off]
else:
    ifd = bytearray(open(ifd_path, "rb").read())
    me = open(me_path, "rb").read()
    if len(ifd) != 4096:
        raise SystemExit(f"IFD must be 4096 bytes, got {len(ifd)}")
    bios_off = int(off_s, 0) if off_s else (0x1000 + len(me))

if ifd[0x10:0x14] != b"\x5a\xa5\xf0\x0f":
    raise SystemExit("IFD missing Intel Flash Descriptor signature 5AA5F00F at 0x10")

if len(ifd) + len(me) != bios_off:
    raise SystemExit(f"IFD (0x1000) + ME (0x{len(me):x}) != bios_offset (0x{bios_off:x})")

target_size = int(rom_s, 0) if rom_s else (bios_off + len(bios))
if target_size not in (4194304, 8388608):
    raise SystemExit(f"Assembled ROM size must be 4 MiB or 8 MiB, got {target_size}")
if bios_off + len(bios) != target_size:
    raise SystemExit(f"BIOS offset (0x{bios_off:x}) + BIOS size (0x{len(bios):x}) != ROM size (0x{target_size:x})")

expected_flreg1 = (((target_size - 1) >> 12) << 16) | (bios_off >> 12)
expected_flreg2 = (((bios_off - 1) >> 12) << 16) | 0x0001
flreg1 = struct.unpack_from("<I", ifd, 0x44)[0]
flreg2 = struct.unpack_from("<I", ifd, 0x48)[0]
if flreg1 != expected_flreg1:
    print(f"Updating IFD FLREG1 0x{flreg1:08x} -> 0x{expected_flreg1:08x}")
    struct.pack_into("<I", ifd, 0x44, expected_flreg1)
if flreg2 != expected_flreg2:
    print(f"Updating IFD FLREG2 0x{flreg2:08x} -> 0x{expected_flreg2:08x}")
    struct.pack_into("<I", ifd, 0x48, expected_flreg2)

flcomp = struct.unpack_from("<I", ifd, 0x30)[0]
desired_density = 0x3 if target_size == 4194304 else 0x4
if (flcomp & 0x7) != desired_density:
    new_flcomp = (flcomp & ~0x7) | desired_density
    print(f"Updating IFD FLCOMP 0x{flcomp:08x} -> 0x{new_flcomp:08x}")
    struct.pack_into("<I", ifd, 0x30, new_flcomp)

full = bytes(ifd) + me + bios
assert len(full) == target_size
open(out_path, "wb").write(full)
print("Assembled:", out_path, "bytes:", len(full), "sha256:", hashlib.sha256(full).hexdigest())
PY

if [ -n "$VBT_FILE" ]; then
  echo "Injecting VBT ($VBT_FILE) into CBFS..."
  "$CBFSTOOL" "$OUT_ROM" add -f "$VBT_FILE" -n vbt.bin -t raw -c lzma
fi

if [ -n "$ME_CLEANER" ]; then
  echo "Running me_cleaner -S..."
  TMP_ME="${OUT_ROM}.mecleaned.tmp"
  python3 "$ME_CLEANER" -S -O "$TMP_ME" "$OUT_ROM"
  mv -f "$TMP_ME" "$OUT_ROM"
  python3 "$ME_CLEANER" -c "$OUT_ROM"
fi

sha256sum "$OUT_ROM"
