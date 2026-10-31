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

# Contador de FPS, limite e captura de tela (Controles > Atalhos): o hud/omni_hud.so entra nos
# ports por LD_PRELOAD (ele também mede o FPS do processador Automático). Com tudo desligado, o
# port roda sem ele. Vão as duas versões: a de
# 64 bits e a omni_hud32.so (jogos armhf, como Asphalt 7); cada processo carrega a sua e o
# ld.so ignora a outra ("wrong ELF class", só um aviso no log).
hud_preload() {
    local lib="$OMNI_DIR/hud/omni_hud.so"
    [ -f "$lib" ] || return
    [ -f "$OMNI_DIR/hud/omni_hud32.so" ] && lib="$lib:$OMNI_DIR/hud/omni_hud32.so"
    python3 -c 'import sys; sys.path.insert(0, sys.argv[1]); import omni; c = omni.get_atalhos()
sys.exit(0 if c["fps"] or c["captura"] or c["limite"] or omni.cpu_auto() else 1)' "$OMNI_DIR" 2>/dev/null || return
    echo "$lib${LD_PRELOAD:+:$LD_PRELOAD}"
}

# Pasta do jogo (a mesma que o card Ports usa para a ficha): a captura de tela (FN + Y)
# vai para <pasta do jogo>/imagens, em qualquer cartão.
game_dir() {
    python3 -c 'import sys; sys.path.insert(0, sys.argv[1]); import omni_meta, os
p = sys.argv[2]
print(omni_meta.port_dir(p) or (p if os.path.isdir(p) else os.path.dirname(p)))' "$OMNI_DIR" "$1" 2>/dev/null
}

# O launcher caiu (erro no Python): guarda o fim do log, que o /tmp perde na próxima abertura.
CRASH_LOG=/var/log/omni36os-crash.log
crash_report() {
    {
        echo "=== $(date '+%d/%m/%Y %H:%M:%S') omni_ui.py saiu com código $1 (versão $(cat "$OMNI_DIR/VERSION" 2>/dev/null))"
        tail -n 60 /tmp/omni.log 2>/dev/null
    } | sudo tee -a "$CRASH_LOG" >/dev/null
    # o log não cresce sem fim no cartão
    if [ "$(sudo stat -c %s "$CRASH_LOG" 2>/dev/null || echo 0)" -gt 262144 ]; then
        sudo sh -c "tail -n 400 '$CRASH_LOG' > '$CRASH_LOG.tmp' && mv '$CRASH_LOG.tmp' '$CRASH_LOG'"
    fi
}

# Port com gptokeyb (teclado virtual do PortMaster): ele não pode sobrar depois do port,
# senão continua segurando o controle no Omni36OS.
kill_gptokeyb() {
    sudo pkill -f gptokeyb 2>/dev/null
    sleep 0.3
    sudo pkill -9 -f gptokeyb 2>/dev/null
}

# Cartão 2: monta em /roms2 sempre que ele estiver no console. O dArkOSen só montava depois do
# "Switch to SD2 for Roms" (que também mexe no ES); aqui ele aparece em Arquivos, na busca de
# ports e em Origem dos jogos sem nada a fazer. Mesmas opções do script do dArkOSen.
mount_card2() {
    local dev=/dev/mmcblk1p1 fs
    [ -b "$dev" ] || return
    mountpoint -q /roms2 && return
    fs=$(lsblk -no FSTYPE "$dev" 2>/dev/null)
    [ -n "$fs" ] || return
    [ "$fs" = "ntfs" ] && fs="ntfs-3g"
    sudo mkdir -p /roms2
    if [ "$fs" = "ext4" ]; then
        sudo mount -t ext4 -o noatime "$dev" /roms2
    else
        sudo mount -t "$fs" -o umask=0000,iocharset=utf8,uid=1000,gid=1000,noatime "$dev" /roms2
    fi
}
mount_card2

# Port do cartão 2: os scripts do PortMaster acham a pasta do jogo por "/$directory/ports/<pasta>", e o
# control.txt só usa roms2 quando o /etc/fstab cita /roms2 (o Omni36OS monta o cartão 2 sozinho). Por
# isso, enquanto um port do cartão 2 roda, /roms/ports mostra a pasta ports do cartão 2 (bind), e
# volta ao normal quando ele fecha. Uma sobra (o launcher caiu no meio de um jogo) é desfeita aqui.
PORTS_BOUND=""
# Desfaz o bind mesmo com sobra do jogo segurando arquivo (processo que não fechou): tenta de novo
# e, se ainda falhar, solta com -l (some na hora para quem abrir depois). Um bind esquecido esconde
# os ports do cartão 1 e duplica os do cartão 2 na biblioteca com "ambos".
ports_unbind() {
    mountpoint -q /roms/ports || return 0
    for _ in 1 2 3; do
        sudo umount /roms/ports 2>/dev/null && return 0
        sleep 0.5
    done
    sudo umount -l /roms/ports 2>/dev/null
}
ports_card2_begin() {
    ports_unbind                         # sobra de um jogo anterior: cada port começa do zero
    case "$1" in
        /roms2/ports/*)
            if [ -d /roms2/ports ]; then
                sudo mkdir -p /roms/ports
                sudo mount --bind /roms2/ports /roms/ports && PORTS_BOUND=1
            fi ;;
    esac
}
ports_card2_end() {
    [ -n "$PORTS_BOUND" ] && ports_unbind
    PORTS_BOUND=""
}
ports_unbind

# Runtimes do PortMaster que o port pede (Mono, Godot, Java...): baixa da internet
# antes de abrir. Ports antigos e independentes só montam o arquivo, sem o runtime_check.
port_deps() {
    case "$1" in
        *.sh|*.SH) sudo python3 -B "$OMNI_DIR/port_deps.py" "$1" > /tmp/omni36os-deps.log 2>&1 ;;
    esac
}

# Loop principal: launcher → port → launcher → ...
RESUME=""
CRASHES=0
while true; do
    # Limpar sinal anterior
    sudo rm -f /tmp/omni36os-next 2>/dev/null || rm -f /tmp/omni36os-next 2>/dev/null

    # Iniciar o launcher (UI principal)
    sudo OMNI_HUB="boot" OMNI_RESUME="$RESUME" SDL_GAMECONTROLLERCONFIG_FILE=/opt/inttools/gamecontrollerdb.txt \
        python3 omni_ui.py > /tmp/omni.log 2>&1
    rc=$?

    if [ ! -f /tmp/omni36os-next ]; then
        [ "$rc" -eq 0 ] && break          # saiu normalmente
        # caiu: registra e abre de novo, esperando mais a cada queda seguida (não trava o
        # processador num laço; o systemd também reinicia se este script sair)
        crash_report "$rc"
        CRASHES=$((CRASHES + 1))
        # versão recém-atualizada caindo: sai para o omni36os-start contar e, se for o caso, voltar
        # à anterior
        if [ -f /var/lib/omni36os-update/pending ] && [ "$CRASHES" -ge 3 ]; then
            exit 1
        fi
        RESUME=""
        sleep $(( CRASHES < 5 ? CRASHES : 5 ))
        continue
    fi
    CRASHES=0

    next="$(cat /tmp/omni36os-next 2>/dev/null)"
    sudo rm -f /tmp/omni36os-next 2>/dev/null || rm -f /tmp/omni36os-next 2>/dev/null

    case "$next" in
        # Mesmos comandos do launch.sh (é o que o omni_ui.py grava em /tmp/omni36os-next)
        # Card "Testar ports": o port tem a tela e o launcher volta com o resultado
        test:/roms/ports/*.sh|test:/roms2/ports/*.sh)
            port_deps "${next#test:}"
            port_begin
            ports_card2_begin "${next#test:}"
            bash "$OMNI_DIR/port_test.sh" "${next#test:}"
            kill_gptokeyb
            ports_card2_end
            port_end
            RESUME="testar"
            continue ;;
        # Card Jogos: mesmo comando do es_systems.cfg
        game$'\t'*)
            IFS=$'\t' read -r _ sys rom <<< "$next"
            cmd="$(python3 -c 'import sys, omni_games; print(omni_games.command(sys.argv[1], sys.argv[2]) or "")' "$sys" "$rom")"
            if [ -n "$cmd" ] && [ -e "$rom" ]; then
                port_deps "$rom"
                sudo chmod 666 /dev/tty1
                port_begin
                ports_card2_begin "$rom"
                OMNI_GAME_DIR="$(game_dir "$rom")" LD_PRELOAD="$(hud_preload)" bash -c "$cmd" > /tmp/omni36os-game.log 2>&1
                kill_gptokeyb             # port que caiu antes do pm_finish deixa o gptokeyb rodando
                ports_card2_end
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
                # (o caminho vai como argumento: um nome com aspas não quebra o comando)
                sudo python3 -c 'import sys; sys.path.insert(0, sys.argv[1]); import ports
ports.record_port_played(sys.argv[2])' "$OMNI_DIR" "$port_path" 2>/dev/null || true

                ports_unbind                     # pasta de port: sempre a do próprio cartão
                # Num subshell: o control.txt e o cd do port não vazam para o próximo
                (
                cd "$port_path" || exit

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

                    kill_gptokeyb
                    port_end
                else
                    echo "Nenhum executável encontrado em $port_path" > /tmp/omni36os-error
                    sleep 2
                fi
                )
                RESUME="port"
            fi
            continue ;;

        # Sair do launcher (desligar/reiniciar)
        exit:*)
            action="${next#exit:}"
            case "$action" in
                poweroff) sudo /usr/local/bin/omni36os-turbo; sudo poweroff ;;   # tudo no máximo: sai mais rápido
                reboot)   sudo /usr/local/bin/omni36os-turbo; sudo reboot ;;
            esac
            break ;;
        *)
            # Comando desconhecido, continuar no loop
            RESUME=""
            continue ;;
    esac
done

echo "Launcher encerrado."