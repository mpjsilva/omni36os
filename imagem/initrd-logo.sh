#!/bin/bash
# Põe o logo do Omni36OS no começo do initramfs:  imagem/initrd-logo.sh <uInitrd original> <saída> <carregando.raw>
# O driver de vídeo do kernel apaga o logo do u-boot e o initramfs leva ~2 s até o systemd: sem
# isto, a tela fica preta nesse meio. Não desmonta o original: acrescenta um segundo cpio (o kernel
# lê os dois em sequência, o de depois sobrepõe arquivos) e refaz tamanho e CRCs do cabeçalho uImage.
set -euo pipefail
ORIG=$1; OUT=$2; RAW=$3
DIR=$(dirname "$(readlink -f "$0")")
T=$(mktemp -d); trap 'rm -rf "$T"' EXIT
mkdir -p "$T/x" "$T/add/scripts/init-top" "$T/add/omni36os"
dd if="$ORIG" bs=64 skip=1 status=none | gunzip | (cd "$T/x" && cpio -id --quiet scripts/init-top/ORDER 2>/dev/null)
grep -q omni36os-logo "$T/x/scripts/init-top/ORDER" && { echo "Esse uInitrd já tem o logo."; exit 1; }
install -m755 "$DIR/initrd/omni36os-logo" "$T/add/scripts/init-top/"
{ echo '/scripts/init-top/omni36os-logo "$@"'; cat "$T/x/scripts/init-top/ORDER"; } > "$T/add/scripts/init-top/ORDER"
cp "$RAW" "$T/add/omni36os/carregando.raw"
(cd "$T/add" && find . -mindepth 1 | sed 's|^\./||' | cpio -o -H newc -R 0:0 --quiet | gzip -9) > "$T/add.gz"
python3 - "$ORIG" "$T/add.gz" "$OUT" <<'PY'
import struct, sys, zlib
o = open(sys.argv[1], "rb").read()
hdr, data = bytearray(o[:64]), o[64:]
magic, _, _, size, _, _, dcrc = struct.unpack(">7I", hdr[:28])
assert magic == 0x27051956 and size == len(data) and zlib.crc32(data) == dcrc, "uInitrd inesperado"
data += open(sys.argv[2], "rb").read()
struct.pack_into(">I", hdr, 12, len(data))
struct.pack_into(">I", hdr, 24, zlib.crc32(data))
struct.pack_into(">I", hdr, 4, 0)
struct.pack_into(">I", hdr, 4, zlib.crc32(bytes(hdr)))
open(sys.argv[3], "wb").write(bytes(hdr) + data)
PY
