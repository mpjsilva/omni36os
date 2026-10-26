#!/bin/bash
# Sab — assistente de diagnóstico e ajustes do R36S
# Sab = homenagem a Sabrina Broch, youtuber que fala de ports do R36S.
# Roda como qualquer port: o ES libera a tela enquanto a Sab está aberta e
# volta para a lista de Ports quando ela fecha.

SAB_DIR="$(cd "$(dirname "$0")" && pwd)/sab"
cd "$SAB_DIR"
RESUME=""

while true; do
  sudo rm -f /tmp/sab-next
  sudo SAB_RESUME="$RESUME" SDL_GAMECONTROLLERCONFIG_FILE=/opt/inttools/gamecontrollerdb.txt \
    python3 sab_ui.py > /tmp/sab.log 2>&1
  [ -f /tmp/sab-next ] || break
  next="$(cat /tmp/sab-next)"
  sudo rm -f /tmp/sab-next
  case "$next" in
    # Testar ports: a Sab fecha para o port ter a tela, e volta com o resultado
    test:/roms/ports/*.sh|test:/roms2/ports/*.sh)
      bash "$SAB_DIR/port_test.sh" "${next#test:}"
      RESUME="testar"
      continue ;;
    # Ferramentas de tela cheia do dArkOSen (calibração da bateria, backup)
    /opt/system/*)
      [ -f "$next" ] && bash "$next" ;;
  esac
  break
done
