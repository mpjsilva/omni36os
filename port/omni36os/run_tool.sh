#!/bin/bash
# Roda um script do Omni36OS (/opt/system) com as janelas do Omni36OS.
# O dialog, o msgbox e o osk são trocados pelo omni_dialog.py só dentro de um
# namespace de montagem deste script (unshare -m): fora dele nada muda, e se
# algo falhar o script roda com as janelas originais.
OMNI_DIR="$(cd "$(dirname "$(readlink -f "$0")")" && pwd)"
TOOL="$1"
SHIM=/tmp/omni36os-shim
[ -f "$TOOL" ] || exit 1

mkdir -p "$SHIM"
[ -x /tmp/omni36os-dialog.real ] || cp /usr/bin/dialog /tmp/omni36os-dialog.real
for n in dialog msgbox osk; do
  printf '#!/bin/bash\nOMNI_DIALOG_AS=%s exec python3 -B "%s/omni_dialog.py" "$@"\n' "$n" "$OMNI_DIR" > "$SHIM/$n"
  chmod 755 "$SHIM/$n"
done

sudo chmod 666 /dev/tty1
printf "\033c" > /dev/tty1
cd "$(dirname "$TOOL")"
sudo unshare -m --propagation private bash -c '
  for n in dialog msgbox osk; do
    t=$(command -v $n) && mount --bind "'"$SHIM"'/$n" "$t"
  done
  exec sudo -u ark -H env HOME=/home/ark TERM=linux bash "$1" > /dev/tty1 2>&1
' _ "$TOOL"
ret=$?

# a janela de aviso que ficou segurando a tela, o teclado virtual dos scripts
[ -f /tmp/omni36os-dialog-holder.pid ] && sudo kill "$(cat /tmp/omni36os-dialog-holder.pid)" 2>/dev/null
sudo rm -f /tmp/omni36os-dialog-holder.pid
sudo pkill -f gptokeyb 2>/dev/null
printf "\033c" > /dev/tty1
exit $ret
