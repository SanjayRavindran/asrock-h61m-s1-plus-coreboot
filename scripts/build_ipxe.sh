#!/usr/bin/env bash
set -euo pipefail

# Build pinned upstream iPXE UEFI (x86_64-efi-sb) binaries for ASRock H61M-S1 PLUS:
#   - ipxe-full.efi      : All iPXE drivers (~344 KiB LZMA) for 8 MiB & 4 MiB minimal-ME ROMs
#   - ipxe-h61-slim.efi  : Targeted realtek + intel + intelx + snp (~142 KiB LZMA) for 4 MiB stock-ME ROM

COREBOOT_DIR="${COREBOOT_DIR:-$PWD/coreboot}"
IPXE_REV="${IPXE_REV:-7c39c04a537ce29dccc6f2bae9749d1d371429c1}"
IPXE_REPO="${IPXE_REPO:-https://github.com/ipxe/ipxe.git}"
IPXE_WORK_DIR="${IPXE_WORK_DIR:-$COREBOOT_DIR/payloads/external/iPXE/ipxe}"
IPXE_OUT_DIR="${IPXE_OUT_DIR:?must set IPXE_OUT_DIR}"

mkdir -p "$(dirname "$IPXE_WORK_DIR")" "$IPXE_OUT_DIR"

if [ ! -d "$IPXE_WORK_DIR/.git" ]; then
  echo "Cloning iPXE ($IPXE_REPO) into $IPXE_WORK_DIR..."
  git clone --filter=blob:none --no-checkout "$IPXE_REPO" "$IPXE_WORK_DIR"
fi

if ! git -C "$IPXE_WORK_DIR" cat-file -e "${IPXE_REV}^{commit}" 2>/dev/null; then
  echo "Fetching iPXE commit $IPXE_REV..."
  git -C "$IPXE_WORK_DIR" fetch --depth 1 origin "$IPXE_REV"
fi

git -C "$IPXE_WORK_DIR" checkout --detach -f "$IPXE_REV"

mkdir -p "$IPXE_WORK_DIR/src/config/local"

cat > "$IPXE_WORK_DIR/src/config/local/general.h" <<'EOF'
/* Local iPXE feature configuration for ASRock H61M-S1 PLUS */
#define DOWNLOAD_PROTO_HTTPS
#define IMAGE_TRUST_CMD
#define PING_CMD
#define NSLOOKUP_CMD
#define REBOOT_CMD
#define POWEROFF_CMD
#define NTP_CMD
#define CERT_CMD
EOF

cat > "$IPXE_WORK_DIR/src/config/local/console.h" <<'EOF'
/* Keep EFI console only; EDK2 TerminalDxe already mirrors to COM1 115200 8N1 */
#undef CONSOLE_SERIAL
EOF

echo "Building iPXE ($IPXE_REV) EFI binaries..."
make -C "$IPXE_WORK_DIR/src" -j"$(nproc)" NO_WERROR=1 \
  bin-x86_64-efi-sb/ipxe.efi \
  bin-x86_64-efi-sb/realtek--intel--intelx--snp.efi

cp -f "$IPXE_WORK_DIR/src/bin-x86_64-efi-sb/ipxe.efi" "$IPXE_OUT_DIR/ipxe-full.efi"
cp -f "$IPXE_WORK_DIR/src/bin-x86_64-efi-sb/realtek--intel--intelx--snp.efi" "$IPXE_OUT_DIR/ipxe-h61-slim.efi"

for efi in "$IPXE_OUT_DIR/ipxe-full.efi" "$IPXE_OUT_DIR/ipxe-h61-slim.efi"; do
  if [ ! -s "$efi" ]; then
    echo "ERROR: Built iPXE binary missing or empty: $efi" >&2
    exit 1
  fi
  magic="$(od -An -tx1 -N2 "$efi" | tr -d ' \n')"
  if [ "$magic" != "4d5a" ]; then
    echo "ERROR: Invalid PE/MZ header ($magic) in $efi" >&2
    exit 1
  fi
  raw_sz="$(stat -c%s "$efi")"
  if command -v xz >/dev/null 2>&1; then
    lzma_sz="$(xz --format=lzma -9 -c "$efi" | wc -c)"
    echo "Verified $efi: raw=${raw_sz} B, lzma=${lzma_sz} B"
  else
    echo "Verified $efi: raw=${raw_sz} B"
  fi
done
