#!/usr/bin/env bash
set -euo pipefail

# Build all 4 verified W25Q32 (4 MiB) & W25Q64 (8 MiB) ASRock H61M-S1 PLUS ROMs
# including committed blobs (IFD + ME + desktop VBT), validate every image,
# and emit SHA256SUMS.txt.

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
COREBOOT_DIR="${COREBOOT_DIR:-$PWD/coreboot}"
OUT_DIR="${OUT_DIR:-$ROOT_DIR/outputs}"
RELEASE_TAG="${RELEASE_TAG:-v26.11.5}"

mkdir -p "$OUT_DIR"
rm -f "$OUT_DIR/SHA256SUMS.txt"

EDK2_CACHE_FD="$(mktemp /tmp/h61m-uefipayload.XXXXXX.fd)"
trap 'rm -f "$EDK2_CACHE_FD"' EXIT
rm -f "$EDK2_CACHE_FD"

build_variant() {
  local variant="$1"
  local defconfig="$2"
  local ifd="$3"
  local me="$4"
  local bios_off="$5"

  echo ""
  echo "=================================================================="
  echo " Building variant: $variant"
  echo "=================================================================="
  COREBOOT_DIR="$COREBOOT_DIR" \
  DEFCONFIG="$ROOT_DIR/configs/$defconfig" \
  OUT_DIR="$OUT_DIR" \
  RELEASE_TAG="$RELEASE_TAG" \
  VARIANT_NAME="$variant" \
  VBT_FILE="$ROOT_DIR/blobs/data.vbt" \
  IFD_FILE="$ROOT_DIR/blobs/$ifd" \
  ME_FILE="$ROOT_DIR/blobs/$me" \
  BIOS_OFFSET="$bios_off" \
  EDK2_CACHE_FD="$EDK2_CACHE_FD" \
    bash "$ROOT_DIR/scripts/build.sh"

  cp -f "$ROOT_DIR/configs/$defconfig" "$OUT_DIR/"
}

build_variant \
  "w25q64-8mb-mecleaned-compat" \
  "h61m-s1-plus-w25q64-8mb-mecleaned-compat.defconfig" \
  "ifd-8mb-mecleaned-compat-unlocked.bin" \
  "me-cleaned-1532k-compat.bin" \
  "0x180000"

build_variant \
  "w25q64-8mb-minimal-me" \
  "h61m-s1-plus-w25q64-8mb-minimal-me.defconfig" \
  "ifd-8mb-minimal-me-unlocked.bin" \
  "me-minimal-124k.bin" \
  "0x020000"

build_variant \
  "w25q32-4mb-minimal-me" \
  "h61m-s1-plus-w25q32-4mb-minimal-me.defconfig" \
  "ifd-4mb-minimal-me-unlocked.bin" \
  "me-minimal-124k.bin" \
  "0x020000"

build_variant \
  "w25q32-4mb-stock-me" \
  "h61m-s1-plus-w25q32-4mb-stock-me.defconfig" \
  "ifd-4mb-stock-unlocked.bin" \
  "me-stock-8.1.20.1336.bin" \
  "0x180000"

(
  cd "$OUT_DIR"
  sha256sum h61m-s1-plus-coreboot-"${RELEASE_TAG}"-*.rom h61m-s1-plus-coreboot-"${RELEASE_TAG}"-*-bios-region.bin > SHA256SUMS.txt
)

echo ""
echo "=== ALL 4 VARIANTS BUILT & VERIFIED ==="
cat "$OUT_DIR/SHA256SUMS.txt"
