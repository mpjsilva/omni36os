#!/bin/bash
# Sab — assistente de diagnóstico e ajustes do R36S
# Sab = homenagem a Sabrina Broch, youtuber que fala de ports do R36S.
# Roda como qualquer port: o ES libera a tela enquanto a Sab está aberta e
# volta para a lista de Ports quando ela fecha.

SAB_DIR="$(cd "$(dirname "$0")" && pwd)/sab"
cd "$SAB_DIR"
sudo rm -f /tmp/sab-next
sudo SDL_GAMECONTROLLERCONFIG_FILE=/opt/inttools/gamecontrollerdb.txt python3 sab_ui.py > /tmp/sab.log 2>&1

# Ferramentas de tela cheia do dArkOSen (calibração da bateria, backup) não
# rodam com a Sab na tela: ela grava qual abrir e fecha; o script roda aqui.
if [ -f /tmp/sab-next ]; then
  next="$(cat /tmp/sab-next)"
  sudo rm -f /tmp/sab-next
  case "$next" in
    /opt/system/*) [ -f "$next" ] && bash "$next" ;;
  esac
fi
