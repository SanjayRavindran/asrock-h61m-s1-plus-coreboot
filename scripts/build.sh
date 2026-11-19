#!/usr/bin/env bash
set -euo pipefail

# Reproducible build script for ASRock H61M-S1 PLUS open-source Coreboot + EDK2 BIOS region.
# Requires a Coreboot checkout and Coreboot toolchain (including Ada/gnat for libgfxinit).

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
COREBOOT_DIR="${COREBOOT_DIR:-$PWD/coreboot}"
DEFCONFIG="${DEFCONFIG:-$ROOT_DIR/configs/h61m-s1-plus-8mb.defconfig}"
OUT_DIR="${OUT_DIR:-$ROOT_DIR/outputs}"
RELEASE_TAG="${RELEASE_TAG:-custom}"
VBT_FILE="${VBT_FILE:-}"

if [ -d /opt/xgcc/bin ]; then
  export PATH="/opt/xgcc/bin:$PATH"
fi

if [ ! -d "$COREBOOT_DIR/src/mainboard/asrock" ]; then
  echo "ERROR: COREBOOT_DIR='$COREBOOT_DIR' is not a valid coreboot checkout." >&2
  exit 1
fi

mkdir -p "$OUT_DIR"

echo "[1/5] Installing board port into $COREBOOT_DIR/src/mainboard/asrock/h61m-s1-plus"
rm -rf "$COREBOOT_DIR/src/mainboard/asrock/h61m-s1-plus"
cp -a "$ROOT_DIR/board/src/mainboard/asrock/h61m-s1-plus" \
      "$COREBOOT_DIR/src/mainboard/asrock/h61m-s1-plus"

if [ -n "$VBT_FILE" ]; then
  cp -f "$VBT_FILE" "$COREBOOT_DIR/src/mainboard/asrock/h61m-s1-plus/data.vbt"
fi

echo "[2/5] Applying Sandy Bridge northbridge patch (if not already applied)"
pushd "$COREBOOT_DIR" >/dev/null
PATCH="$ROOT_DIR/patches/0001-sandybridge-h61m-s1-plus-igd-raminit.patch"
if git apply --check "$PATCH" >/dev/null 2>&1; then
  git apply "$PATCH"
elif git apply --reverse --check "$PATCH" >/dev/null 2>&1; then
  echo "Patch already applied."
else
  echo "WARNING: Patch did not apply cleanly on this Coreboot revision; trying 3-way fallback..." >&2
  git apply --reject --whitespace=fix "$PATCH" || true
fi

echo "[3/5] Generating .config from $DEFCONFIG"
cp -f "$DEFCONFIG" .config
if [ -n "$VBT_FILE" ]; then
  sed -i '/CONFIG_INTEL_GMA_ADD_VBT/d' .config
  echo "CONFIG_INTEL_GMA_ADD_VBT=y" >> .config
fi
make olddefconfig UPDATED_SUBMODULES=1

echo "[4/5] Building Coreboot + EDK2 UefiPayloadPkg"
make -j"$(nproc)" UPDATED_SUBMODULES=1

echo "[5/5] Extracting 6.5 MiB redistributable BIOS region (0x180000..0x7fffff)"
OUT_BIOS="$OUT_DIR/h61m-s1-plus-coreboot-${RELEASE_TAG}-8mb-bios-region.bin"
python3 - <<PY
rom = open("build/coreboot.rom", "rb").read()
assert len(rom) == 8388608, f"Expected 8 MiB coreboot.rom, got {len(rom)}"
bios = rom[0x180000:]
assert len(bios) == 6815744
open("$OUT_BIOS", "wb").write(bios)
PY

{
  echo "=== CBFS PRINT ==="
  ./build/cbfstool build/coreboot.rom print
  echo ""
  echo "=== FMAP LAYOUT ==="
  ./build/cbfstool build/coreboot.rom layout -w
} > "$OUT_DIR/cbfs-layout.txt"

(cd "$OUT_DIR" && sha256sum "$(basename "$OUT_BIOS")" > SHA256SUMS.txt)
popd >/dev/null
echo "Done: $OUT_BIOS"
