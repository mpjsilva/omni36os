#!/bin/bash
# Sab como tela inicial do console (Ajuda > Tela inicial).
# O emulationstation.service passa a rodar este script (drop-in sab-hub.conf)
# no lugar do emulationstation.sh. A ordem fica:
#   boot -> Sab -> (Jogar / B) -> ES -> (sair do ES ou atalho L3+R3) -> Sab ...
# Redes de segurança: segurar B no boot mantém o BaRT do dArkOSen, segurar L1
# pula a Sab, e se a Sab cair logo ao abrir o ES sobe direto.

SAB_DIR="$(cd "$(dirname "$(readlink -f "$0")")" && pwd)"
ES=/usr/bin/emulationstation/emulationstation.sh
CONF="$HOME/.config/sab/hub"          # sempre | alertas
BOOTED=/dev/shm/sab-hub-booted        # tmpfs: some no boot
OPEN=/dev/shm/sab-hub-open            # o atalho L3+R3 pediu a Sab
CRASH="$HOME/.config/sab/hub-falhou"  # a Sab caiu no último boot

held() {   # botão segurado agora? (mesmo teste do buttonmon.sh do dArkOSen)
  evtest --query /dev/input/by-path/platform-odroidgo3-joypad-event-joystick EV_KEY "$1" 2>/dev/null
  [ "$?" -eq 10 ]
}

stopping() {
  case "$(systemctl is-system-running 2>/dev/null)" in stopping) return 0 ;; esac
  return 1
}

run_sab() {   # $1: motivo (boot, atalho, saida)
  start=$(date +%s)
  SAB_HUB="$1" bash "$SAB_DIR/launch.sh"
  # caiu em menos de 3 s: algo quebrado, não prender o console na Sab
  if [ $(( $(date +%s) - start )) -lt 3 ] && grep -q Traceback /tmp/sab.log 2>/dev/null; then
    touch "$CRASH"
    return 1
  fi
  rm -f "$CRASH"
}

first=1
[ -f "$BOOTED" ] && first=0   # restart do serviço (troca de modo etc.): vai direto ao ES
touch "$BOOTED"

while true; do
  stopping && exit 0
  show=0
  if [ -f "$OPEN" ]; then
    rm -f "$OPEN"; show=1; why=atalho
  elif [ "$first" = 1 ]; then
    why=boot
    if held BTN_SOUTH || held BTN_TL || [ -f "$CRASH" ]; then
      show=0                                  # B (BaRT), L1 ou falha anterior
    elif [ "$(cat "$CONF" 2>/dev/null)" = "alertas" ]; then
      ( cd "$SAB_DIR" && python3 -c "import sab, sys; sys.exit(0 if sab.hub_alerts() else 1)" >/dev/null 2>&1 ) && show=1
    else
      show=1
    fi
  fi
  first=0
  [ "$show" = 1 ] && run_sab "$why"
  stopping && exit 0
  "$ES" "$@"
  ret=$?
  stopping && exit $ret
  [ -f "$OPEN" ] && continue      # o atalho fechou o ES para abrir a Sab
  # o ES saiu pelo menu (Sair do ES): volta para a Sab
  printf "\033c" > /dev/tty1 2>/dev/null
  touch "$OPEN"
done
