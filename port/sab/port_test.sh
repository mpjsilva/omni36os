#!/bin/bash
# Teste de port da Sab: roda o port como o ES roda (nice -19, já sob perfmax),
# espera TEMPO segundos e encerra. Se o port fechar sozinho antes disso, conta
# como falha e gera um relatório em sab/logs/<nome do port>/.
# Uso: port_test.sh "/roms2/ports/Nome.sh"

PORT="$1"
TEMPO=15
SAB_DIR="$(cd "$(dirname "$0")" && pwd)"
NAME="$(basename "$PORT" .sh)"
SAFE="$(printf '%s' "$NAME" | tr -c 'A-Za-z0-9._ -' '_')"
OUT="/tmp/sab-port-out.log"
RESULT="/tmp/sab-test-result"
RESULTS="$SAB_DIR/logs/resultados.txt"   # nome|resultado|data|segundos

mkdir -p "$SAB_DIR/logs"
sudo dmesg -c > /dev/null 2>&1           # o relatório mostra só o que o port causou
START=$(date +%s)
STAMP_START="$(date '+%Y-%m-%d %H:%M:%S')"

# setsid: o port e tudo que ele abrir ficam num grupo só, para encerrar junto
setsid nice -n -19 bash "$PORT" > "$OUT" 2>&1 < /dev/null &
PID=$!

alive=1
for _ in $(seq $((TEMPO * 2))); do
  sleep 0.5
  if ! kill -0 "$PID" 2>/dev/null; then
    alive=0
    break
  fi
done
ELAPSED=$(( $(date +%s) - START ))

if [ "$alive" = 1 ]; then
  STATUS="ok"
  # encerra o grupo (com sudo: muitos ports rodam o jogo como root)
  sudo kill -TERM -- "-$PID" 2>/dev/null
  for _ in 1 2 3 4 5 6; do
    kill -0 "$PID" 2>/dev/null || break
    sleep 0.5
  done
  sudo kill -KILL -- "-$PID" 2>/dev/null
  CODE="-"
else
  wait "$PID"
  CODE=$?
  STATUS="falhou"
fi
# sobra comum de ports: o mapeador de controle
sudo pkill -f gptokeyb 2>/dev/null
printf "\033c" > /dev/tty1 2>/dev/null

REPORT=""
if [ "$STATUS" = "falhou" ]; then
  DIR="$SAB_DIR/logs/$SAFE"
  mkdir -p "$DIR"
  REPORT="$DIR/$(date '+%Y-%m-%d_%H-%M-%S').txt"
  {
    echo "RELATÓRIO DE TESTE DE PORT (Sab)"
    echo "================================"
    echo "Port:        $NAME"
    echo "Script:      $PORT"
    echo "Início:      $STAMP_START"
    echo "Fechou após: ${ELAPSED}s (o teste espera ${TEMPO}s)"
    echo "Código de saída: $CODE"
    echo
    echo "--- Saída do port (stdout/stderr, últimas 200 linhas) ---"
    tail -n 200 "$OUT"
    echo
    echo "--- Logs na pasta do port (modificados no teste) ---"
    for d in "$(dirname "$PORT")/$NAME" "$(dirname "$PORT")/$(echo "$NAME" | tr 'A-Z ' 'a-z_')"; do
      [ -d "$d" ] || continue
      find "$d" -maxdepth 2 -type f \( -iname '*.log' -o -iname 'log.txt' \) -newermt "$STAMP_START" 2>/dev/null |
        while read -r f; do echo "## $f"; tail -n 80 "$f"; echo; done
    done
    echo "--- Kernel (dmesg durante o teste) ---"
    sudo dmesg 2>/dev/null | tail -n 60
    echo
    echo "--- Sistema ---"
    echo "Temperatura: $(( $(cat /sys/class/thermal/thermal_zone0/temp) / 1000 )) °C"
    echo "Bateria: $(cat /sys/class/power_supply/battery/capacity)%"
    free -m
    df -h / /roms /roms2 2>/dev/null
    echo
    echo "--- Script do port (primeiras 60 linhas) ---"
    head -n 60 "$PORT"
  } > "$REPORT" 2>&1
fi

# histórico (uma linha por port, a mais recente vale) e resultado para a Sab
touch "$RESULTS"
awk -F'|' -v n="$NAME" '$1 != n' "$RESULTS" > "$RESULTS.tmp" 2>/dev/null
echo "$NAME|$STATUS|$(date '+%d/%m/%Y %H:%M')|$ELAPSED" >> "$RESULTS.tmp"
mv "$RESULTS.tmp" "$RESULTS"
printf '%s\n%s\n%s\n%s\n' "$NAME" "$STATUS" "$ELAPSED" "$REPORT" > "$RESULT"
chown -R ark:ark "$SAB_DIR/logs" 2>/dev/null || sudo chown -R ark:ark "$SAB_DIR/logs"
exit 0
