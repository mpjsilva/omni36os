#!/bin/bash
# Sab — assistente de diagnóstico e ajustes do R36S
# Sab = homenagem a Sabrina Broch, youtuber que fala de ports do R36S.
# Launcher de verdade. O ES chega aqui por um atalho: Ports/Sab.sh (modo port)
# ou <cartão>/sab/Sab.sh (modo sistema, entrada própria no menu do ES).
# Roda como qualquer port: não para o ES, que volta para a tela de onde a Sab
# foi aberta quando ela fecha.

SAB_DIR="$(cd "$(dirname "$(readlink -f "$0")")" && pwd)"
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

# Troca do modo de exibição ou importação do backup do ES: o ES relê tudo
if [ -f /tmp/sab-restart-es ]; then
  sudo rm -f /tmp/sab-restart-es
  sudo systemctl restart emulationstation
fi
