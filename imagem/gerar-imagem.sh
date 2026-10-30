#!/bin/bash
# Gera a imagem de distribuição do Omni36OS a partir da imagem original do dArkOSen.
#
#   sudo imagem/gerar-imagem.sh            -> output/Omni36OS-<versão>.img.xz
#
# 1. Copia a imagem original (ela não é tocada) e monta as partições.
# 2. Tira o que não é de um sistema só de ports: EmulationStation, RetroArch e núcleos,
#    emuladores avulsos, Kodi, temas do ES, cache de atualização e as pastas de sistemas do
#    EASYROMS (o roms.tar que o primeiro boot extrai é refeito só com ports, PortMaster e backup).
# 3. Instala o Omni36OS (launcher do repositório + arquivos de sistema da lista abaixo, tirados da
#    cópia do cartão). Nada pessoal entra: nome, tema, Wi-Fi, logs, saves, SSH ligado.
# 4. Devolve o espaço livre (fstrim) para a compressão ficar pequena, e comprime com xz.
# O primeiro boot continua o do dArkOSen (expande a imagem), com a tela certa do Omni36OS antes.
set -euo pipefail

BASE=/home/jamersonferreira/Apps/Omni36OS
ORIG="$BASE/dArkOSen_R36_10152026.img"
REPO="$BASE/omni36os"
CARD="$BASE/cartao/ROOTFS"
TELAS="$BASE/telas/out"
VER=$(cat "$REPO/port/omni36os/VERSION")
OUT="$BASE/output"
IMG="$OUT/Omni36OS-$VER.img"
MNT=/mnt/omni36os-imagem

[ "$(id -u)" = 0 ] || { echo "Rode com sudo."; exit 1; }
mkdir -p "$OUT" "$MNT/boot" "$MNT/root"

echo "== copiando a imagem original"
cp --sparse=always "$ORIG" "$IMG"
LOOP=$(losetup -f --show -P "$IMG")
limpar() { sync; umount "$MNT/boot" "$MNT/root" 2>/dev/null || true; losetup -d "$LOOP" 2>/dev/null || true; }
trap limpar EXIT
mount "${LOOP}p1" "$MNT/boot"
mount -o compress=zlib:1 "${LOOP}p2" "$MNT/root"
R="$MNT/root"; B="$MNT/boot"
[ -f "$R/etc/systemd/system/emulationstation.service" ] && [ -f "$B/firstboot.sh" ] || { echo "Imagem inesperada."; exit 1; }

echo "== tirando ES, RetroArch e emuladores"
rm -rf "$R/usr/bin/emulationstation"
for d in kodi scummvm duckstation ppsspp ppsspp-2021 advanceddrastic drastic flycastsa retroarch bigpemu \
         mednafen dingux openmsx gzdoom lzdoom hypseus-singe solarus yabasanshiro applewin ti99sim \
         mupen64plus mvem ecwolf gametank OpenBor fake08 linapple xroar piemu; do
  rm -rf "${R:?}/opt/$d"
done
rm -rf "$R/usr/local/bin/retrorun" "$R/usr/local/bin/retrorun32" "$R/usr/local/bin/freej2me_files"
H="$R/home/ark"
rm -rf "$H/.config/retroarch" "$H/.config/retroarch32" "$H/.config/duckstation" "$H/.config/gzdoom" \
       "$H/.config/lzdoom" "$H/.config/mupen64plus" "$H/.kodi" "$H/.mednafen" "$H/.update" "$H/.benchmark_data"
# o primeiro boot faz "cd /tempthemes" e copia "." para /roms/themes: a pasta fica, vazia
find "$R/tempthemes" -mindepth 1 -delete

echo "== refazendo o roms.tar (só ports, PortMaster e backup)"
T=$(mktemp -d)
tar -xf "$R/roms.tar" -C "$T" roms/ports roms/backup roms/tools/PortMaster roms/tools/PortMaster.sh
mkdir -p "$T/roms/themes" "$T/roms/bios"
tar -cf "$R/roms.tar" -C "$T" roms
rm -rf "$T"

echo "== instalando o Omni36OS"
rsync -a --delete --exclude __pycache__ --exclude imagens --exclude logs "$REPO/port/omni36os/" "$R/opt/omni36os/"
chmod +x "$R"/opt/omni36os/*.sh "$R/opt/omni36os/omni36os-start"
chown -R 1000:1000 "$R/opt/omni36os"
# arquivos de sistema do Omni36OS (da cópia do cartão; a lista é fechada para nada pessoal entrar)
SIS=(etc/hostname etc/hosts etc/zram.conf etc/hostapd/hostapd.conf
     etc/NetworkManager/conf.d/omni36os-usb0.conf etc/omni36os etc/sysctl.d/90-omni36os.conf
     etc/systemd/system/emulationstation.service etc/systemd/system/firstboot.service
     etc/systemd/system/omni36os-atalho.service etc/systemd/system/omni36os-launcher.service
     etc/systemd/system/omni36os-painel.service etc/systemd/system/omni36os-tela-saida.service
     etc/systemd/system/rotate-boot-logo.service etc/systemd/system/boot_volume.service.d
     etc/systemd/system/emulationstation.service.d etc/systemd/system/welcome-message.service.d
     etc/systemd/system/omni36os-launcher.service.wants
     etc/systemd/system/multi-user.target.wants/omni36os-atalho.service
     etc/systemd/system/multi-user.target.wants/omni36os-launcher.service
     etc/systemd/system/multi-user.target.wants/omni36os-painel.service
     etc/systemd/system/multi-user.target.wants/omni36os-tela-saida.service
     etc/update-motd.d/00-header etc/update-motd.d/10-help-text
     usr/local/bin/BaRT_QuickMode.sh usr/local/bin/arkos_ap_mode.sh usr/local/bin/b_swap.sh
     usr/local/bin/finish.sh usr/local/bin/omni36os-start usr/local/bin/omni36os-tela
     usr/local/bin/perfmax usr/local/bin/perfnorm usr/local/bin/perfnorm.omni36os-bak
     usr/share/plymouth/themes/text.plymouth opt/inttools/osk.py opt/omni36os-telas home/ark/usb-disco.sh)
for f in "${SIS[@]}"; do
  mkdir -p "$R/$(dirname "$f")"
  cp -a "$CARD/$f" "$R/$(dirname "$f")/"
done
rm -f "$R/etc/systemd/system/multi-user.target.wants/emulationstation.service"
cp "$TELAS/tela-certa.raw" "$TELAS/tela-certa.png" "$R/opt/omni36os-telas/"
mkdir -p "$H/.config/omni36os" && chown 1000:1000 "$H/.config/omni36os" "$H/usb-disco.sh"
touch "$R/var/log/omni36os.log"

echo "== BOOT: logo, bateria e textos do primeiro boot"
cp "$TELAS/logo.bmp" "$TELAS/low_battery.bmp" "$B/"
sed -i -e 's/Firstboot setup of dArkOSen/Primeira inicialização do Omni36OS/' \
       -e 's/Expanding rootfs and exfat partitions.  Please wait.../Preparando o cartão. Isso leva alguns minutos, não desligue.../' \
       -e 's/EASYROMS partition expansion and conversion to exfat in process.  The device will now reboot to continue the process.../Preparando o cartão. O console vai reiniciar uma vez e continuar sozinho.../' \
       -e 's/Completed expansion of root filesystem and EASYROMS partition and conversion to exfat. The system will now reboot and load dArkOSen./Tudo pronto! O console vai reiniciar e abrir o Omni36OS./' \
       -e 's/System will reboot and load dArkOSen now./O console vai reiniciar e abrir o Omni36OS./' "$B/expandtoexfat.sh"

echo "== devolvendo o espaço livre"
fstrim -v "$R" || true
fstrim -v "$B" || true
df -h "$R" | tail -1
limpar
trap - EXIT

echo "== comprimindo"
rm -f "$IMG.xz"
xz -T0 -6 -v "$IMG"
chown 1000:1000 "$IMG.xz"
ls -la "$IMG.xz"
sha256sum "$IMG.xz" | tee "$IMG.xz.sha256"
