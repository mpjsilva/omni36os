"""Ferramentas simples reescritas em Python (NATIVE) e os programas de tela cheia (APPS).

As ferramentas maiores (senha, rede USB, calibração, DTB, arquivos) ficam em
omni_sistema.py e abrem como subpáginas do launcher.
"""
import os
import shutil
import subprocess

import omni

ROOT = "/opt/system"
HOME = omni.HOME


def fix_hotkeys(_a=None):
    bak = "/etc/systemd/system/ogage.service.bak"
    run = lambda *a: subprocess.run(["systemctl", *a], capture_output=True)
    run("stop", "ogage")
    if os.path.exists(bak):           # nem toda imagem traz a cópia: sem ela, só religa o serviço
        shutil.copy2(bak, "/etc/systemd/system/ogage.service")
    run("daemon-reload")
    run("enable", "ogage")
    r = run("start", "ogage")
    return "Atalhos globais (brilho, volume) reiniciados" if r.returncode == 0 else "O serviço de atalhos não subiu."


def usb_mount(_a=None):
    if not os.path.exists("/dev/sda1"):
        return "Nenhum pendrive conectado (sda1)."
    os.makedirs("/mnt/usbdrive", exist_ok=True)
    fs = subprocess.run(["lsblk", "-no", "FSTYPE", "/dev/sda1"], capture_output=True, text=True).stdout.strip()
    fs = "ntfs-3g" if fs == "ntfs" else fs
    r = subprocess.run(["mount", "-t", fs, "/dev/sda1", "/mnt/usbdrive", "-o", "uid=1002"], capture_output=True)
    return f"Pendrive ({fs}) montado em /mnt/usbdrive" if r.returncode == 0 else \
        "Não consegui montar: use um pendrive FAT, FAT32, exFAT ou NTFS."


def usb_umount(_a=None):
    r = subprocess.run(["umount", "/mnt/usbdrive"], capture_output=True)
    os.sync()
    return "Pendrive desmontado: pode tirar" if r.returncode == 0 else "Não havia pendrive montado em /mnt/usbdrive."


NATIVE = {"fix_hotkeys": fix_hotkeys, "usb_mount": usb_mount, "usb_umount": usb_umount}

# Programas de tela cheia que continuam fora do launcher (o resto virou subpágina:
# ver omni_sistema.py). Abrem pelo handoff tool: do launch-direct.sh.
APPS = {
    "Tools/PortMaster.sh": ("PortMaster", "Loja de ports (precisa de internet)."),
    "351Files.sh": ("351Files (avançado)", "Gerenciador de arquivos completo, com visualizador de imagens e textos."),
}


def tools():
    """Programas de tela cheia que existem neste sistema."""
    return [{"path": os.path.join(ROOT, rel), "name": name, "desc": desc}
            for rel, (name, desc) in APPS.items() if os.path.isfile(os.path.join(ROOT, rel))]


def run_native(name):
    return NATIVE[name]()
