#!/usr/bin/env bash
set -euo pipefail

# Reproducible build script for ASRock H61M-S1 PLUS Coreboot + EDK2 firmware.
# Supports both BIOS-region builds and complete flashable 4 MiB / 8 MiB ROMs.

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
COREBOOT_DIR="${COREBOOT_DIR:-$PWD/coreboot}"
DEFCONFIG="${DEFCONFIG:-$ROOT_DIR/configs/h61m-s1-plus-8mb.defconfig}"
OUT_DIR="${OUT_DIR:-$ROOT_DIR/outputs}"
RELEASE_TAG="${RELEASE_TAG:-custom}"
VARIANT_NAME="${VARIANT_NAME:-}"
VBT_FILE="${VBT_FILE:-}"
IFD_FILE="${IFD_FILE:-}"
ME_FILE="${ME_FILE:-}"
BIOS_OFFSET="${BIOS_OFFSET:-}"
EDK2_CACHE_FD="${EDK2_CACHE_FD:-}"

if [ -d /opt/xgcc/bin ]; then
  export PATH="/opt/xgcc/bin:$PATH"
fi

if [ ! -d "$COREBOOT_DIR/src/mainboard/asrock" ]; then
  echo "ERROR: COREBOOT_DIR='$COREBOOT_DIR' is not a valid coreboot checkout." >&2
  exit 1
fi

if [ -z "$VBT_FILE" ] && grep -q '^CONFIG_INTEL_GMA_ADD_VBT=y' "$DEFCONFIG" && [ -f "$ROOT_DIR/blobs/data.vbt" ]; then
  VBT_FILE="$ROOT_DIR/blobs/data.vbt"
elif [ "$VBT_FILE" = "none" ]; then
  VBT_FILE=""
fi

mkdir -p "$OUT_DIR"

echo "[1/6] Installing board port into $COREBOOT_DIR/src/mainboard/asrock/h61m-s1-plus"
rm -rf "$COREBOOT_DIR/src/mainboard/asrock/h61m-s1-plus"
cp -a "$ROOT_DIR/board/src/mainboard/asrock/h61m-s1-plus" \
      "$COREBOOT_DIR/src/mainboard/asrock/h61m-s1-plus"

if [ -n "$VBT_FILE" ]; then
  cp -f "$VBT_FILE" "$COREBOOT_DIR/src/mainboard/asrock/h61m-s1-plus/data.vbt"
fi

echo "[2/6] Applying Sandy Bridge / BD82x6x chipset patch (if not already applied)"
pushd "$COREBOOT_DIR" >/dev/null
PATCH1="$ROOT_DIR/patches/0001-sandybridge-h61m-s1-plus-igd-raminit.patch"
if git apply --check "$PATCH1" >/dev/null 2>&1; then
  git apply "$PATCH1"
elif git apply --reverse --check "$PATCH1" >/dev/null 2>&1; then
  echo "Chipset patch already applied."
else
  echo "WARNING: Chipset patch did not apply cleanly on this Coreboot revision; trying 3-way fallback..." >&2
  git apply --reject --whitespace=fix "$PATCH1" || true
fi

echo "[3/6] Preparing and patching EDK2 UefiPayloadPkg workspace"
EDK2_DIR="$COREBOOT_DIR/payloads/external/edk2/workspace/mrchromebox"
EDK2_REV="$(sed -n 's/^CONFIG_EDK2_TAG_OR_REV="\([^"]*\)"$/\1/p' "$DEFCONFIG" | head -n 1)"
EDK2_REV="${EDK2_REV:-f248a68be339831b69a880d9c932a6a3cf3c461a}"
if [ ! -d "$EDK2_DIR/.git" ]; then
  mkdir -p "$(dirname "$EDK2_DIR")"
  git clone --recurse-submodules -j5 https://github.com/mrchromebox/edk2 "$EDK2_DIR"
  git -C "$EDK2_DIR" checkout --detach "$EDK2_REV" -f
  git -C "$EDK2_DIR" submodule update --init --checkout --recursive
fi

PATCH2="$ROOT_DIR/patches/0002-edk2-delete-key-usb-boot-menu.patch"
if [ -f "$PATCH2" ]; then
  if git -C "$EDK2_DIR" apply --check "$PATCH2" >/dev/null 2>&1; then
    git -C "$EDK2_DIR" apply "$PATCH2"
    echo "Applied EDK2 Delete-key USB boot menu & Port 80 patch."
  elif git -C "$EDK2_DIR" apply --reverse --check "$PATCH2" >/dev/null 2>&1; then
    echo "EDK2 patch already applied."
  else
    echo "ERROR: Failed to apply $PATCH2 cleanly on $EDK2_DIR" >&2
    exit 1
  fi
fi

echo "[4/6] Generating .config from $DEFCONFIG"
cp -f "$DEFCONFIG" .config
if [ -n "$VBT_FILE" ]; then
  sed -i '/CONFIG_INTEL_GMA_ADD_VBT/d' .config
  echo "CONFIG_INTEL_GMA_ADD_VBT=y" >> .config
fi
make olddefconfig UPDATED_SUBMODULES=1

if [ -n "$EDK2_CACHE_FD" ] && [ -f "$EDK2_CACHE_FD" ]; then
  mkdir -p build
  cp -f "$EDK2_CACHE_FD" build/UEFIPAYLOAD.fd
  touch build/UEFIPAYLOAD.fd
  echo "Reusing cached EDK2 payload: $EDK2_CACHE_FD"
fi

echo "[5/6] Building Coreboot + EDK2 UefiPayloadPkg"
rm -f build/coreboot.rom build/coreboot.pre build/fmap.fmd build/fmap.fmap
make -j"$(nproc)" UPDATED_SUBMODULES=1

if [ -n "$EDK2_CACHE_FD" ] && [ ! -f "$EDK2_CACHE_FD" ] && [ -f build/UEFIPAYLOAD.fd ]; then
  cp -f build/UEFIPAYLOAD.fd "$EDK2_CACHE_FD"
fi

echo "[6/6] Extracting BIOS region, validating layout, and assembling full ROM (if IFD/ME supplied)"
if [ -z "$VARIANT_NAME" ]; then
  BASE_NAME="h61m-s1-plus-coreboot-${RELEASE_TAG}-8mb"
  LAYOUT_FILE="$OUT_DIR/cbfs-layout.txt"
else
  BASE_NAME="h61m-s1-plus-coreboot-${RELEASE_TAG}-${VARIANT_NAME}"
  LAYOUT_FILE="$OUT_DIR/cbfs-layout-${VARIANT_NAME}.txt"
fi
OUT_BIOS="$OUT_DIR/${BASE_NAME}-bios-region.bin"

python3 - "$BIOS_OFFSET" "$OUT_BIOS" <<'PY'
import re, sys

cfg = open(".config", "r").read()
m_rom = re.search(r"^CONFIG_COREBOOT_ROMSIZE_KB=(\d+)$", cfg, re.M)
m_cbfs = re.search(r"^CONFIG_CBFS_SIZE=(0x[0-9a-fA-F]+|\d+)$", cfg, re.M)
rom_size = int(m_rom.group(1)) * 1024
cbfs_size = int(m_cbfs.group(1), 0)
bios_off = int(sys.argv[1], 0) if sys.argv[1] else ((rom_size - cbfs_size) & ~0xffff)

rom = open("build/coreboot.rom", "rb").read()
assert len(rom) == rom_size, f"Expected {rom_size} B coreboot.rom, got {len(rom)}"
bios = rom[bios_off:]
assert len(bios) == rom_size - bios_off, f"Unexpected BIOS slice len {len(bios)}"
open(sys.argv[2], "wb").write(bios)
print(f"Extracted BIOS region: offset=0x{bios_off:06x} size={len(bios)} B -> {sys.argv[2]}")
PY

{
  echo "=== CBFS PRINT ($BASE_NAME) ==="
  ./build/cbfstool build/coreboot.rom print
  echo ""
  echo "=== FMAP LAYOUT ($BASE_NAME) ==="
  ./build/cbfstool build/coreboot.rom layout -w
} > "$LAYOUT_FILE"

if [ -n "$IFD_FILE" ] && [ -n "$ME_FILE" ]; then
  OUT_FULL="$OUT_DIR/${BASE_NAME}-full.rom"
  CBFSTOOL="$COREBOOT_DIR/build/cbfstool" \
    bash "$ROOT_DIR/scripts/assemble_full_rom.sh" \
      --ifd "$IFD_FILE" \
      --me "$ME_FILE" \
      --bios-region "$OUT_BIOS" \
      --out "$OUT_FULL" \
      ${BIOS_OFFSET:+--bios-offset "$BIOS_OFFSET"}

  if [ ! -x "$COREBOOT_DIR/util/ifdtool/ifdtool" ]; then
    make -C "$COREBOOT_DIR/util/ifdtool" -j"$(nproc)"
  fi
  echo "=== IFDTOOL VERIFY ($BASE_NAME) ==="
  "$COREBOOT_DIR/util/ifdtool/ifdtool" -d "$OUT_FULL" | grep -E "FLREG|FLMSTR|Density|AltMeDisable"
  echo "=== ME_CLEANER CHECK ($BASE_NAME) ==="
  python3 "$COREBOOT_DIR/util/me_cleaner/me_cleaner.py" -c "$OUT_FULL"
fi

popd >/dev/null
echo "Done: $BASE_NAME"
