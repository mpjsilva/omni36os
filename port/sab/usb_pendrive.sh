#!/bin/bash
# usb-disco.sh — porta OTG do R36S como pendrive (USB Mass Storage).
# A interface é a Sab (Ferramentas > Pendrive USB); a Sab instala este arquivo
# em /home/ark porque o serviço precisa dele fora de /roms2, que é desmontada.
#
#   part [p]  mostra/escolhe a partição entregue ao PC (roms2 ou roms)
#   on|off    liga/desliga o modo pendrive (edita o DTB e reinicia)
#   restore   volta o DTB original salvo no primeiro "on" e reinicia
#   status    modo atual, partição escolhida, estado do cabo
#   daemon    (serviço de boot) espera o cabo do PC: ao conectar para o ES,
#             desmonta a partição e entrega ao PC; ao desconectar (ou ao
#             "ejetar" no PC) monta de novo e volta o ES
#
# O DTB de fábrica deixa a porta só como host, por isso a troca reinicia.
# No modo pendrive o dongle Wi-Fi/teclado na OTG não funcionam.
DTB=/boot/rk3326-r36s-linux.dtb
BAK=/boot/rk3326-r36s-linux.dtb.host-bak
UDC=ff300000.usb
G=/sys/kernel/config/usb_gadget/r36s
LUN=$G/functions/mass_storage.0/lun.0
SELF=/home/ark/usb-disco.sh
CFG=/home/ark/usb-disco.cfg
LOG=/home/ark/usb-disco.log
SVC=/etc/systemd/system/usb-disco.service
TTY=/dev/tty1
PART=roms2
[ -f $CFG ] && . $CFG
[ "$(id -u)" = 0 ] || exec sudo -n "$0" "$@"
export PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin

log() { echo "$(/bin/date '+%F %T') $*" >> $LOG; }
say() { printf '\033[H\033[2J\n\n  %b\n' "$*" > $TTY 2>/dev/null; }
mode() { tr -d '\0' < /proc/device-tree/usb@ff300000/dr_mode; }
dtb_mode() { fdtget -t s $DTB /usb@ff300000 dr_mode; }
dev() { findmnt -rno SOURCE /$PART 2>/dev/null || awk -v m=/$PART '$2==m{print $1}' /etc/fstab; }
udc_state() { cat /sys/class/udc/$UDC/state 2>/dev/null; }

# Layout A/B invertido? Vale a opção do ES (InvertButtons) ou a troca global
# do dArkOS (b_swap.sh, flag /var/cache/Switch_AB). Nos códigos do controle,
# 304 é o botão de baixo e 305 o da direita.
swapped() {
  [ -f /var/cache/Switch_AB ] ||
    grep -q 'name="InvertButtons" value="true"' /home/ark/.emulationstation/es_settings.cfg 2>/dev/null
}
if swapped; then OK_KEY=304 BACK_KEY=305; else OK_KEY=305 BACK_KEY=304; fi

set_dtb() {  # $1 = peripheral|otg
  [ -f $BAK ] || cp $DTB $BAK
  cp $DTB $DTB.tmp && fdtput -t s $DTB.tmp /usb@ff300000 dr_mode "$1" &&
    [ "$(fdtget -t s $DTB.tmp /usb@ff300000 dr_mode)" = "$1" ] &&
    mv $DTB.tmp $DTB && sync || { rm -f $DTB.tmp; echo "falha ao editar o DTB"; return 1; }
}

install_svc() {
  printf '[Unit]\nDescription=R36S modo pendrive USB\nAfter=local-fs.target emulationstation.service\n[Service]\nExecStart=%s daemon\nRestart=on-failure\n[Install]\nWantedBy=multi-user.target\n' "$SELF" > $SVC
  systemctl daemon-reload; systemctl enable usb-disco.service 2>/dev/null
  # o modo rede antigo disputaria a mesma porta
  systemctl disable usb-rede.service 2>/dev/null; rm -f /etc/systemd/system/usb-rede.service
}

on()  { install_svc; set_dtb peripheral && { echo "modo pendrive ativado; reiniciando..."; sleep 2; reboot; }; }
off() { set_dtb otg && { echo "porta OTG de volta ao normal; reiniciando..."; sleep 2; reboot; }; }
restore() {
  [ -f $BAK ] || { echo "sem backup em $BAK (o DTB nunca foi alterado)"; return 1; }
  cp $BAK $DTB.tmp && mv $DTB.tmp $DTB && sync && { echo "backup restaurado; reiniciando..."; sleep 2; reboot; }
}

status() {
  echo "Porta OTG agora: $(mode)   próximo boot: $(dtb_mode)"
  echo "Partição: /$PART ($(dev))   montada: $(findmnt -rno TARGET /$PART >/dev/null && echo sim || echo não)"
  echo "Botões: $(swapped && echo "invertidos (A embaixo, B à direita)" || echo "padrão (A à direita, B embaixo)")"
  echo "Cabo/PC: $(udc_state || echo -)   entregue ao PC: $( [ -n "$(cat $LUN/file 2>/dev/null)" ] && echo sim || echo não)"
}

# --- gadget e troca da partição ---

gadget_up() {
  [ -d $G ] && return
  modprobe libcomposite; modprobe usb_f_mass_storage
  mkdir -p $G && cd $G || return 1
  echo 0x1d6b > idVendor; echo 0x0104 > idProduct
  mkdir -p strings/0x409
  echo R36S > strings/0x409/manufacturer; echo "R36S $PART" > strings/0x409/product
  cut -c1-16 /etc/machine-id > strings/0x409/serialnumber
  mkdir -p functions/mass_storage.0 configs/c.1/strings/0x409
  echo 1 > $LUN/removable
  echo 250 > configs/c.1/MaxPower; echo Pendrive > configs/c.1/strings/0x409/configuration
  ln -s functions/mass_storage.0 configs/c.1/
  echo $UDC > UDC; cd /
}

# Para o ES, desmonta e entrega a partição ao PC.
give() {
  local d; d=$(dev); [ -b "$d" ] || { log "partição /$PART não encontrada"; return 1; }
  log "PC conectado: entregando $d (/$PART)"
  say "Conectado ao PC.\n\n  Preparando /$PART..."
  systemctl stop emulationstation
  sync
  [ $PART = roms2 ] && umount /opt/system/Tools 2>/dev/null
  if ! umount /$PART 2>/dev/null; then
    fuser -km /$PART 2>/dev/null; sleep 1
    umount /$PART || { log "não desmontou /$PART"; mount -a; systemctl start emulationstation; return 1; }
  fi
  echo "$d" > $LUN/file
  say "MODO PENDRIVE\n\n  /$PART está aberta no computador.\n\n  Ejete no PC e desconecte o cabo,\n  ou aperte B, para voltar aos jogos."
}

# Tira a partição do PC, monta de novo e volta o ES.
take_back() {
  log "devolvendo /$PART ao R36S"
  say "Desconectado.\n\n  Montando /$PART e voltando ao EmulationStation..."
  # sem forced_eject no 4.4: desligar o UDC libera a trava do PC
  echo "" > $G/UDC 2>/dev/null
  sync
  echo "" > $LUN/file 2>/dev/null
  mount /$PART || log "falha ao montar /$PART"
  [ $PART = roms2 ] && mount /opt/system/Tools 2>/dev/null
  systemctl start emulationstation
  echo $UDC > $G/UDC 2>/dev/null
}

# Contador da interrupção do dwc2: com o PC ligado ele cresce sempre (o PC
# consulta o pendrive a cada ~2 s); parado = cabo fora. O estado do UDC não
# serve: sem o sinal de VBUS ele continua "configured" com o cabo solto.
irqs() { awk '/ff300000.usb/{s=0; for(i=2;i<=NF&&$i~/^[0-9]+$/;i++) s+=$i; print s}' /proc/interrupts; }

# B (ou Select+Start) no controle devolve a partição na hora; o código do B
# segue o layout (BACK_KEY).
watch_pad() {
  BACK_KEY=$BACK_KEY python3 - <<'PY' &
import evdev, os
back = int(os.environ["BACK_KEY"])
d = evdev.InputDevice("/dev/input/event2"); held = set()
for e in d.read_loop():
    if e.type != evdev.ecodes.EV_KEY: continue
    (held.add if e.value else held.discard)(e.code)
    if e.code == back and e.value == 1 or {704, 705} <= held:
        open("/run/usb-disco.back", "w").close(); break
PY
  PAD=$!
}

daemon() {
  [ "$(mode)" = peripheral ] || exit 0
  gadget_up || exit 1
  log "daemon: esperando o cabo (/$PART)"
  local given=0 idle=0 s n last
  PAD=""
  trap '[ $given = 1 ] && take_back; exit 0' TERM INT
  while sleep 1; do
    s=$(udc_state)
    if [ $given = 0 ]; then
      n=$(irqs)
      if [ "$s" = configured ] && [ "$n" != "${prev:-$n}" ] && give; then
        given=1; idle=0; last=$(irqs); rm -f /run/usb-disco.back; watch_pad
      fi
      prev=$n
      continue
    fi
    n=$(irqs)
    if [ "$n" = "$last" ]; then idle=$((idle + 1)); else idle=0; last=$n; fi
    why=""
    [ -z "$(cat $LUN/file)" ] && why="ejetado no PC"
    [ -f /run/usb-disco.back ] && why="botão no controle"
    [ $idle -ge 8 ] && why="cabo desconectado (sem atividade USB há 8 s, estado $s)"
    [ -n "$why" ] || continue
    log "$why"
    [ -n "$PAD" ] && kill $PAD 2>/dev/null; PAD=""; rm -f /run/usb-disco.back
    take_back; given=0
    # Só arma de novo depois do cabo sair (5 s sem tráfego) e voltar
    # (tráfego novo): com o cabo ainda no PC, ejetar não reentrega a partição.
    # O UDC fica "configured" sem cabo, por isso conta o tráfego e não o estado.
    idle=0; last=$(irqs)
    while [ $idle -lt 5 ]; do
      sleep 1; n=$(irqs); [ "$n" = "$last" ] && idle=$((idle + 1)) || { idle=0; last=$n; }
    done
    log "cabo fora; esperando conectar de novo"
    while [ "$(irqs)" = "$last" ]; do sleep 1; done
    log "atividade USB de novo"; prev=""; sleep 2
  done
}

case "$1" in
  on) on;; off) off;; restore) restore;; status) status;; daemon) daemon;;
  part) case "$2" in roms|roms2) echo "PART=$2" > $CFG; chown ark:ark $CFG;;
        *) echo "$PART";; esac;;
  give|take_back) gadget_up; $1;;   # testes manuais
  *) echo "uso: $0 on|off|restore|status|part [roms|roms2]"; exit 1;;
esac
