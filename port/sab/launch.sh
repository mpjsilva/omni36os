#!/bin/bash
# Sab — assistente de diagnóstico e ajustes do R36S
# Sab = homenagem a Sabrina Broch, youtuber que fala de ports do R36S.
# Launcher de verdade. O ES chega aqui por um atalho: Ports/Sab.sh (modo port)
# ou <cartão>/sab/Sab.sh (modo sistema, entrada própria no menu do ES).
# Roda como qualquer port: não para o ES, que volta para a tela de onde a Sab
# foi aberta quando ela fecha. Também é chamado pelo hub.sh (tela inicial) e
# pelo sab_atalho.py (L3+R3); aí SAB_HUB diz de onde: boot, atalho, saida, jogo.

SAB_DIR="$(cd "$(dirname "$(readlink -f "$0")")" && pwd)"
cd "$SAB_DIR"
RESUME=""

while true; do
  sudo rm -f /tmp/sab-next
  sudo SAB_HUB="$SAB_HUB" SAB_RESUME="$RESUME" SDL_GAMECONTROLLERCONFIG_FILE=/opt/inttools/gamecontrollerdb.txt \
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
    # Ferramentas de tela cheia do dArkOSen: rodam como no menu Opções do ES
    # e, quando fecham, a Sab volta no card de onde foram abertas
    tool:*:/opt/system/*)
      rest="${next#tool:}"
      RESUME="${rest%%:*}"
      tool="${rest#*:}"
      if [ -f "$tool" ]; then
        sudo chmod 666 /dev/tty1
        bash "$tool" 2>&1 > /dev/tty1
        printf "\033c" > /dev/tty1
        sudo pkill -f gptokeyb 2>/dev/null
      fi
      continue ;;
  esac
  break
done

# Ícone e descrição da Sab no ES: aplicados uma vez por versão da arte
ART_MARK="$HOME/.config/sab/arte-es"
ART_VER="1"
case "$(cat "$ART_MARK" 2>/dev/null)" in
  "$ART_VER"|off) ;;     # off: Ajuda > Restaurar o ES tirou a arte, não pôr de volta
  *) sudo touch /tmp/sab-restart-es ;;
esac

# Troca do modo, importação do backup do ES ou arte nova: o ES relê tudo.
# Para, aplica a arte e sobe de novo num job à parte do systemd: com o ES
# aberto ele reescreveria o gamelist.xml, e o job não morre junto com ele.
# Por cima de um jogo congelado (atalho no jogo): deixa para a próxima vez.
[ "$SAB_HUB" = jogo ] && exit 0
if [ -f /tmp/sab-restart-es ] && [ "$SAB_HUB" = atalho ]; then
  # o job do atalho já parou o ES e vai subir ele: só aplicar a arte
  sudo rm -f /tmp/sab-restart-es
  mkdir -p "$(dirname "$ART_MARK")"
  if [ -f /tmp/sab-es-clean ]; then echo off > "$ART_MARK"; else echo "$ART_VER" > "$ART_MARK"; fi
  sudo python3 es_art.py
elif [ -f /tmp/sab-restart-es ]; then
  sudo rm -f /tmp/sab-restart-es
  mkdir -p "$(dirname "$ART_MARK")"
  if [ -f /tmp/sab-es-clean ]; then echo off > "$ART_MARK"; else echo "$ART_VER" > "$ART_MARK"; fi
  sudo systemd-run --no-block --collect --unit="sab-es-$$" bash -c \
    "systemctl stop emulationstation; cd '$SAB_DIR' && python3 es_art.py; systemctl start emulationstation"
fi
