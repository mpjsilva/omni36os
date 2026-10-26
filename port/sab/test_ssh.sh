#!/bin/bash
# Só para testes pelo SSH (o ES está na tela e não a libera): tira o ES,
# roda a Sab e devolve o ES no fim. Pelo menu Ports, use o Sab.sh.
cd "$(dirname "$0")"
systemctl stop emulationstation --no-block >/dev/null 2>&1
sleep 0.5
systemctl kill -s SIGKILL emulationstation >/dev/null 2>&1
sleep 1
trap 'systemctl start emulationstation >/dev/null 2>&1' EXIT
SDL_GAMECONTROLLERCONFIG_FILE=/opt/inttools/gamecontrollerdb.txt python3 sab_ui.py
