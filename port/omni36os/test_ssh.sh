#!/bin/bash
# Só para testes pelo SSH (o ES está na tela e não a libera): tira o ES,
# roda o Omni36OS e devolve o ES no fim. Pelo menu Ports, use o Omni36OS.sh.
cd "$(dirname "$0")"
systemctl stop emulationstation --no-block >/dev/null 2>&1
sleep 0.5
systemctl kill -s SIGKILL emulationstation >/dev/null 2>&1
sleep 1
trap 'systemctl start emulationstation >/dev/null 2>&1' EXIT
SDL_GAMECONTROLLERCONFIG_FILE=/opt/inttools/gamecontrollerdb.txt python3 omni_ui.py
