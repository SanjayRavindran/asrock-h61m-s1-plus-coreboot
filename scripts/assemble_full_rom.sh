#!/usr/bin/env bash
set -euo pipefail

# Assemble a flashable 8 MiB SPI image from:
#   - User's stock SPI dump (supplies 4 KiB IFD + Intel ME at 0x000000..0x17ffff)
#   - Open-source Coreboot 6.5 MiB BIOS region (0x180000..0x7fffff)
# Optional:
#   --vbt <data.vbt>   Inject user-extracted desktop VBT into CBFS as vbt.bin
#   --me-cleaner <py>  Run me_cleaner.py -S to strip non-essential ME partitions & set AltMeDisable

STOCK_DUMP=""
BIOS_REGION=""
OUT_ROM=""
VBT_FILE=""
ME_CLEANER=""
CBFSTOOL="${CBFSTOOL:-cbfstool}"

while [ $# -gt 0 ]; do
  case "$1" in
    --stock-dump) STOCK_DUMP="$2"; shift 2 ;;
    --bios-region) BIOS_REGION="$2"; shift 2 ;;
    --out) OUT_ROM="$2"; shift 2 ;;
    --vbt) VBT_FILE="$2"; shift 2 ;;
    --me-cleaner) ME_CLEANER="$2"; shift 2 ;;
    --cbfstool) CBFSTOOL="$2"; shift 2 ;;
    *) echo "Unknown arg: $1" >&2; exit 2 ;;
  esac
done

if [ -z "$STOCK_DUMP" ] || [ -z "$BIOS_REGION" ] || [ -z "$OUT_ROM" ]; then
  echo "Usage: $0 --stock-dump <stock_dump.bin> --bios-region <8mb_bios_region.bin> --out <full_8mb.rom> [--vbt data.vbt] [--me-cleaner path/to/me_cleaner.py]" >&2
  exit 2
fi

python3 - "$STOCK_DUMP" "$BIOS_REGION" "$OUT_ROM" <<'PY'
import hashlib, struct, sys

stock = open(sys.argv[1], "rb").read()
bios = open(sys.argv[2], "rb").read()
if len(stock) not in (4194304, 8388608):
    raise SystemExit(f"Stock dump must be 4 MiB or 8 MiB, got {len(stock)}")
if stock[0x10:0x14] != b"\x5a\xa5\xf0\x0f":
    raise SystemExit("Stock dump missing Intel Flash Descriptor signature 5AA5F00F at 0x10")
if len(bios) != 6815744:
    raise SystemExit(f"BIOS region must be 6815744 bytes (6.5 MiB), got {len(bios)}")

ifd_me = bytearray(stock[:0x180000])
flreg1 = struct.unpack_from("<I", ifd_me, 0x44)[0]
if flreg1 != 0x07FF0180:
    print(f"Updating IFD FLREG1 0x{flreg1:08x} -> 0x07ff0180 (8 MiB BIOS region)")
    struct.pack_into("<I", ifd_me, 0x44, 0x07FF0180)
    flcomp = struct.unpack_from("<I", ifd_me, 0x30)[0]
    if (flcomp & 0x7) == 0x3:
        new_flcomp = (flcomp & ~0x7) | 0x4
        print(f"Updating IFD FLCOMP 0x{flcomp:08x} -> 0x{new_flcomp:08x}")
        struct.pack_into("<I", ifd_me, 0x30, new_flcomp)

full = bytes(ifd_me) + bios
assert len(full) == 8388608
open(sys.argv[3], "wb").write(full)
print("Assembled:", sys.argv[3], "bytes:", len(full), "sha256:", hashlib.sha256(full).hexdigest())
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
