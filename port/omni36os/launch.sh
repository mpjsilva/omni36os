#!/bin/bash
# Omni36OS — assistente de diagnóstico e ajustes do R36S
# Omni36OS: nasceu da Sab, assistente feito em homenagem a Sabrina Broch (youtuber de ports do R36S).
# Launcher de verdade. O ES chega aqui por um atalho: Ports/Omni36OS.sh (modo port)
# ou <cartão>/omni36os/Omni36OS.sh (modo sistema, entrada própria no menu do ES).
# Roda como qualquer port: não para o ES, que volta para a tela de onde o Omni36OS
# foi aberta quando ela fecha. Também é chamado pelo hub.sh (tela inicial) e
# pelo omni_atalho.py (L3+R3); aí OMNI_HUB diz de onde: boot, atalho, saida, jogo.

OMNI_DIR="$(cd "$(dirname "$(readlink -f "$0")")" && pwd)"
cd "$OMNI_DIR"
RESUME=""

while true; do
  sudo rm -f /tmp/omni36os-next
  sudo OMNI_HUB="$OMNI_HUB" OMNI_RESUME="$RESUME" SDL_GAMECONTROLLERCONFIG_FILE=/opt/inttools/gamecontrollerdb.txt \
    python3 omni_ui.py > /tmp/omni.log 2>&1
  [ -f /tmp/omni36os-next ] || break
  next="$(cat /tmp/omni36os-next)"
  sudo rm -f /tmp/omni36os-next
  case "$next" in
    # Testar ports: o Omni36OS fecha para o port ter a tela, e volta com o resultado
    test:/roms/ports/*.sh|test:/roms2/ports/*.sh)
      bash "$OMNI_DIR/port_test.sh" "${next#test:}"
      RESUME="testar"
      continue ;;
    # Jogo aberto pelo card Jogos: o mesmo comando do ES (emulador, core e
    # governador escolhidos lá), e o Omni36OS volta no card Jogos
    game$'\t'*)
      IFS=$'\t' read -r _ sys rom <<< "$next"
      cmd="$(python3 -c 'import sys, omni_games; print(omni_games.command(sys.argv[1], sys.argv[2]) or "")' "$sys" "$rom")"
      if [ -n "$cmd" ] && [ -e "$rom" ]; then
        sudo chmod 666 /dev/tty1
        bash -c "$cmd" > /tmp/omni36os-game.log 2>&1
        printf "\033c" > /dev/tty1
      fi
      RESUME="biblioteca"
      continue ;;
    # Ferramentas de tela cheia do dArkOSen: rodam como no menu Opções do ES
    # e, quando fecham, o Omni36OS volta no card de onde foram abertas
    tool:*:/opt/system/*)
      rest="${next#tool:}"
      RESUME="${rest%%:*}"
      tool="${rest#*:}"
      [ -f "$tool" ] && bash "$OMNI_DIR/run_tool.sh" "$tool"
      continue ;;
  esac
  break
done

# Ícone e descrição do Omni36OS no ES: aplicados uma vez por versão da arte
ART_MARK="$HOME/.config/omni36os/arte-es"
ART_VER="1"
case "$(cat "$ART_MARK" 2>/dev/null)" in
  "$ART_VER"|off) ;;     # off: Ajuda > Restaurar o ES tirou a arte, não pôr de volta
  *) sudo touch /tmp/omni36os-restart-es ;;
esac

# Troca do modo, importação do backup do ES ou arte nova: o ES relê tudo.
# Para, aplica a arte e sobe de novo num job à parte do systemd: com o ES
# aberto ele reescreveria o gamelist.xml, e o job não morre junto com ele.
# Por cima de um jogo congelado (atalho no jogo): deixa para a próxima vez.
[ "$OMNI_HUB" = jogo ] && exit 0
if [ -f /tmp/omni36os-restart-es ] && [ "$OMNI_HUB" = atalho ]; then
  # o job do atalho já parou o ES e vai subir ele: só aplicar a arte
  sudo rm -f /tmp/omni36os-restart-es
  mkdir -p "$(dirname "$ART_MARK")"
  if [ -f /tmp/omni36os-es-clean ]; then echo off > "$ART_MARK"; else echo "$ART_VER" > "$ART_MARK"; fi
  sudo python3 es_art.py
elif [ -f /tmp/omni36os-restart-es ]; then
  sudo rm -f /tmp/omni36os-restart-es
  mkdir -p "$(dirname "$ART_MARK")"
  if [ -f /tmp/omni36os-es-clean ]; then echo off > "$ART_MARK"; else echo "$ART_VER" > "$ART_MARK"; fi
  sudo systemd-run --no-block --collect --unit="omni36os-es-$$" bash -c \
    "systemctl stop emulationstation; cd '$OMNI_DIR' && python3 es_art.py; systemctl start emulationstation"
fi
