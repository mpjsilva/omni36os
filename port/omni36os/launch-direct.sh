#!/bin/bash
# =============================================================================
# launch-direct.sh — Lançador direto de ports (launcher como shell principal)
#
# Usado quando o Omni36OS é o shell principal (omnilaut=true), ignorando
# completamente o EmulationStation.
#
# Fluxo:
#   1. Inicia o omni_ui.py (menu principal do launcher)
#   2. Se o usuário selecionar um port, o omni_ui.py grava em /tmp/omni36os-next
#      algo como: launch:/caminho/do/port
#   3. Este script lê o comando, para o launcher, lança o port via PortMaster
#   4. Quando o port termina, volta ao passo 1
# =============================================================================

OMNI_DIR="$(cd "$(dirname "$(readlink -f "$0")")" && pwd)"
cd "$OMNI_DIR"

# Verificar se estamos em modo launcher shell (omnilaut)
OMNILAUT="false"
if grep -q "omnilaut=true" /proc/cmdline 2>/dev/null; then
    OMNILAUT="true"
fi

# Fonte do control.txt do PortMaster (variáveis de ambiente)
CONTROL_FOLDER=""
if [ -d "/opt/system/Tools/PortMaster/" ]; then
    CONTROL_FOLDER="/opt/system/Tools/PortMaster"
elif [ -d "/opt/tools/PortMaster/" ]; then
    CONTROL_FOLDER="/opt/tools/PortMaster"
elif [ -d "$HOME/.local/share/PortMaster/" ]; then
    CONTROL_FOLDER="$HOME/.local/share/PortMaster"
else
    CONTROL_FOLDER="/roms/ports/PortMaster"
fi

if [ -f "${CONTROL_FOLDER}/control.txt" ]; then
    source "${CONTROL_FOLDER}/control.txt"
fi

# Antes de um port: libera memória e CPU para ele. Depois: devolve tudo como estava.
# Serviços remotos só param se ninguém estiver conectado (SSH/Samba/filebrowser).
PORT_STOPPED=""
port_begin() {
    PORT_STOPPED=""
    # fn-menu-watcher só serve ao RetroArch; es-status-daemon só ao ES
    for s in fn-menu-watcher es-status-daemon; do
        systemctl is-active -q "$s" && sudo systemctl stop "$s" && PORT_STOPPED="$PORT_STOPPED $s"
    done
    if ! ss -tnH state established 2>/dev/null | grep -qE ':(22|80|139|445) '; then
        for s in smbd nmbd; do
            systemctl is-active -q "$s" && sudo systemctl stop "$s" && PORT_STOPPED="$PORT_STOPPED $s"
        done
        pgrep -x filebrowser >/dev/null && sudo pkill -x filebrowser && PORT_STOPPED="$PORT_STOPPED filebrowser"
    fi
    # CPU, GPU e memória no máximo do DTB (o perfmax do port faz o mesmo; aqui vale
    # também para port que não chama perfmax). O launcher relaxa de novo ao reabrir.
    for g in /sys/devices/system/cpu/cpufreq/policy0/scaling_governor \
             /sys/devices/platform/ff400000.gpu/devfreq/ff400000.gpu/governor \
             /sys/devices/platform/dmc/devfreq/dmc/governor; do
        echo performance | sudo tee "$g" >/dev/null 2>&1
    done
    # cache limpo e memória compactada: o port ganha blocos grandes livres
    sync
    echo 3 | sudo tee /proc/sys/vm/drop_caches >/dev/null
    echo 1 | sudo tee /proc/sys/vm/compact_memory >/dev/null 2>&1
    # o port (filho deste shell) herda prioridade de disco alta
    sudo ionice -c 2 -n 0 -p $$ 2>/dev/null
}
port_end() {
    sudo ionice -c 2 -n 4 -p $$ 2>/dev/null
    for s in $PORT_STOPPED; do
        if [ "$s" = filebrowser ]; then
            sudo setsid filebrowser -a 0.0.0.0 -p 80 -d /home/ark/.config/filebrowser.db -r / >/dev/null 2>&1 < /dev/null &
        else
            sudo systemctl start "$s" &
        fi
    done
    PORT_STOPPED=""
}

# Contador de FPS, limite e captura de tela (Sistema > Atalhos): o hud/omni_hud.so entra nos
# ports por LD_PRELOAD. Com os três desligados, o port roda sem ele.
hud_preload() {
    local lib="$OMNI_DIR/hud/omni_hud.so"
    [ -f "$lib" ] || return
    python3 -c 'import sys; sys.path.insert(0, sys.argv[1]); import omni; c = omni.get_atalhos()
sys.exit(0 if c["fps"] or c["captura"] or c["limite"] else 1)' "$OMNI_DIR" 2>/dev/null || return
    echo "$lib${LD_PRELOAD:+:$LD_PRELOAD}"
}

# Pasta do jogo (a mesma que o card Ports usa para a ficha): a captura de tela (FN + Y)
# vai para <pasta do jogo>/imagens, em qualquer cartão.
game_dir() {
    python3 -c 'import sys; sys.path.insert(0, sys.argv[1]); import omni_meta, os
p = sys.argv[2]
print(omni_meta.port_dir(p) or (p if os.path.isdir(p) else os.path.dirname(p)))' "$OMNI_DIR" "$1" 2>/dev/null
}

# Loop principal: launcher → port → launcher → ...
RESUME=""
while true; do
    # Limpar sinal anterior
    sudo rm -f /tmp/omni36os-next 2>/dev/null || rm -f /tmp/omni36os-next 2>/dev/null

    # Iniciar o launcher (UI principal)
    sudo OMNI_HUB="boot" OMNI_RESUME="$RESUME" SDL_GAMECONTROLLERCONFIG_FILE=/opt/inttools/gamecontrollerdb.txt \
        python3 omni_ui.py > /tmp/omni.log 2>&1

    # Se não houve próximo comando, sair do loop
    [ -f /tmp/omni36os-next ] || break

    next="$(cat /tmp/omni36os-next 2>/dev/null)"
    sudo rm -f /tmp/omni36os-next 2>/dev/null || rm -f /tmp/omni36os-next 2>/dev/null

    case "$next" in
        # Mesmos comandos do launch.sh (é o que o omni_ui.py grava em /tmp/omni36os-next)
        # Card "Testar ports": o port tem a tela e o launcher volta com o resultado
        test:/roms/ports/*.sh|test:/roms2/ports/*.sh)
            port_begin
            bash "$OMNI_DIR/port_test.sh" "${next#test:}"
            port_end
            RESUME="testar"
            continue ;;
        # Card Jogos: mesmo comando do es_systems.cfg
        game$'\t'*)
            IFS=$'\t' read -r _ sys rom <<< "$next"
            cmd="$(python3 -c 'import sys, omni_games; print(omni_games.command(sys.argv[1], sys.argv[2]) or "")' "$sys" "$rom")"
            if [ -n "$cmd" ] && [ -e "$rom" ]; then
                sudo chmod 666 /dev/tty1
                port_begin
                OMNI_GAME_DIR="$(game_dir "$rom")" LD_PRELOAD="$(hud_preload)" bash -c "$cmd" > /tmp/omni36os-game.log 2>&1
                port_end
                printf "\033c" > /dev/tty1
            fi
            RESUME="biblioteca"
            continue ;;
        # Ferramentas de tela cheia do sistema (/opt/system)
        tool:*:/opt/system/*)
            rest="${next#tool:}"
            RESUME="${rest%%:*}"
            tool="${rest#*:}"
            [ -f "$tool" ] && bash "$OMNI_DIR/run_tool.sh" "$tool"
            continue ;;

        # Lançar um port diretamente
        launch:*)
            port_path="${next#launch:}"
            if [ -n "$port_path" ] && [ -d "$port_path" ]; then
                # Registrar no histórico via omni.py
                sudo python3 -c "
import importlib.util
spec = importlib.util.spec_from_file_location('omni_ports', 'ports.py')
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
mod.record_port_played('$port_path')
" 2>/dev/null || true

                # Entrar no diretório do port
                cd "$port_path"

                # Carregar variáveis do PortMaster
                [ -f control.txt ] && source control.txt

                # Variáveis para o port
                export GAMEDIR="$port_path"

                # Procurar executável
                exec_file=""
                for cand in Omni36OS.sh launch.sh main.sh start.sh; do
                    if [ -f "$cand" ]; then
                        exec_file="$cand"
                        break
                    fi
                done

                if [ -n "$exec_file" ]; then
                    # Rodar com GPTOKEYB se disponível
                    if [ -n "$GPTOKEYB" ] && [ -f gptk ]; then
                        $GPTOKEYB "./$exec_file" -c "gptk" &
                    fi

                    # Rodar o port (bloqueante)
                    port_begin
                    export LD_PRELOAD="$(hud_preload)" OMNI_GAME_DIR="$port_path"
                    if [ -n "$ESUDO" ]; then
                        $ESUDO "./$exec_file" > /tmp/omni36os-port.log 2>&1
                    else
                        "./$exec_file" > /tmp/omni36os-port.log 2>&1
                    fi
                    unset LD_PRELOAD OMNI_GAME_DIR

                    port_end
                    # Port terminou, retornar ao launcher
                    RESUME="port"
                else
                    echo "Nenhum executável encontrado em $port_path" > /tmp/omni36os-error
                    sleep 2
                    RESUME=""
                fi

                # Voltar ao diretório do launcher
                cd "$OMNI_DIR"
            fi
            continue ;;

        # Sair do launcher (desligar/reiniciar)
        exit:*)
            action="${next#exit:}"
            case "$action" in
                poweroff) sudo poweroff ;;
                reboot)   sudo reboot ;;
            esac
            break ;;
        *)
            # Comando desconhecido, continuar no loop
            RESUME=""
            continue ;;
    esac
done

echo "Launcher encerrado."