"""Ferramentas do dArkOSen (o menu Opções do ES) dentro do Omni36OS.

Cada script de /opt/system entra em um de quatro jeitos:
- nativo: reescrito aqui em Python (os simples, que só copiam/apagam arquivos);
- janela: roda o script original, mas as janelas dele (dialog, msgbox, osk)
  aparecem no visual do Omni36OS (omni_dialog.py, num namespace de montagem
  só do script: nada muda no sistema);
- app: programas com tela própria (gerenciador de arquivos, PortMaster);
- perigoso: mexe no boot, no kernel ou no ES. Fica escondido atrás de aviso.
Scripts que aparecerem depois (atualização do dArkOSen) entram como "janela"
na categoria Outros.
"""
import glob
import os
import shutil
import subprocess
import tarfile

import omni

ROOT = "/opt/system"
HOME = omni.HOME


def _device_tag():
    """Sufixo dos arquivos de config por aparelho. O R36S do dArkOSen se apresenta como RG351MP."""
    dev = omni.read_text(f"{HOME}/.config/.DEVICE", "").strip().lower()
    return {"rg351mp": "351mp", "rg351v": "351v", "rgb10max": "rgb10max", "rk2023": "rk2023",
            "rgb30": "rgb30", "rg353m": "353m", "rg353v": "353v", "rg503": "503"}.get(dev, "351mp")


def _restore_from(backup_dir, target, prefix):
    tag = _device_tag()
    cands = [os.path.join(backup_dir, f"{prefix}.{tag}"), os.path.join(backup_dir, prefix)]
    src = next((c for c in cands if os.path.isfile(c)), None)
    if not src:
        return f"Não achei a configuração padrão em {backup_dir}."
    os.makedirs(os.path.dirname(target), exist_ok=True)
    if os.path.exists(target):
        shutil.copy2(target, target + ".omni36os-bak")
    shutil.copy2(src, target)
    return f"Padrão restaurado ({os.path.basename(src)}). A anterior ficou em {os.path.basename(target)}.omni36os-bak"


def drastic_default(_a=None):
    return _restore_from("/opt/drastic/config/backup", "/opt/drastic/config/drastic.cfg", "drastic.cfg")


def gzdoom_default(_a=None):
    return _restore_from(f"{HOME}/.config/gzdoom/backup", f"{HOME}/.config/gzdoom/gzdoom.ini", "gzdoom.ini")


def lzdoom_default(_a=None):
    return _restore_from(f"{HOME}/.config/lzdoom/backup", f"{HOME}/.config/lzdoom/lzdoom.ini", "lzdoom.ini")


def bigpemu_default(_a=None):
    d = "/opt/bigpemu/defaultconfigs"
    files = sorted(glob.glob(f"{d}/*{_device_tag()}*")) or sorted(glob.glob(f"{d}/*"))
    if not files:
        return "Não achei as configurações padrão do BigPEmu."
    target = f"{HOME}/.bigpemu_userdata/BigPEmuConfig.bigpcfg"
    os.makedirs(os.path.dirname(target), exist_ok=True)
    shutil.copy2(files[0], target)
    return f"BigPEmu restaurado ({os.path.basename(files[0])})"


def ppsspp_controls(_a=None):
    n = 0
    for root in ("/roms", "/roms2"):
        for f in ("controls.ini", "ppsspp.ini", "ppsspp.ini.sdl"):
            p = f"{root}/psp/ppsspp/PSP/SYSTEM/{f}"
            if os.path.exists(p):
                os.remove(p)
                n += 1
    return f"Controles do PPSSPP voltaram ao padrão ({n} arquivo(s) apagado(s); o PPSSPP recria ao abrir)"


def ecwolf_joystick(_a=None):
    p = f"{HOME}/.config/ecwolf/ecwolf.cfg"
    text = omni.read_text(p, "")
    if "JoystickEnabled" not in text:
        return "Não achei a configuração do ECWolf."
    lines = ["JoystickEnabled = 1;" if l.strip().startswith("JoystickEnabled") else l for l in text.splitlines()]
    omni.write_text(p, "\n".join(lines) + "\n")
    return "Controle do ECWolf ligado de novo"


def fix_hotkeys(_a=None):
    bak = "/etc/systemd/system/ogage.service.bak"
    if not os.path.exists(bak):
        return "Não achei o backup do serviço de atalhos (ogage.service.bak)."
    run = lambda *a: subprocess.run(["systemctl", *a], capture_output=True)
    run("stop", "ogage")
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


def es_running():
    return subprocess.run(["pgrep", "-x", "emulationstation"], capture_output=True).returncode == 0


def clear_last_played(_a=None):
    if es_running():
        return "Feche o ES antes (o ES reescreve as listas ao sair). Abra o Omni36OS pelo boot e tente de novo."
    n = 0
    for pat in ("/roms/*/gamelist.xml", "/roms2/*/gamelist.xml", "/opt/*/gamelist.xml",
                "/roms*/pico-8/*/gamelist.xml"):
        for f in glob.glob(pat):
            try:
                with open(f, encoding="utf-8", errors="ignore") as fh:
                    lines = fh.readlines()
                keep = [l for l in lines if "<lastplayed>" not in l and "<playcount>" not in l]
                if len(keep) != len(lines):
                    shutil.copy2(f, f + ".omni-bak")     # para desfazer: copie de volta
                    with open(f + ".tmp", "w", encoding="utf-8") as fh:
                        fh.writelines(keep)
                    os.replace(f + ".tmp", f)
                    n += 1
            except OSError:
                pass
    return f"Últimos jogados zerados em {n} lista(s)"


def remove_dot_underscore(_a=None):
    return omni.clean_mac_junk()


BACKUP_FILES = [
    f"{HOME}/.config/panel_settings.txt", "/etc/NetworkManager/system-connections",
    f"{HOME}/.config/retroarch/retroarch.cfg", f"{HOME}/.config/retroarch/config",
    f"{HOME}/.config/retroarch/retroarch-core-options.cfg", f"{HOME}/.config/retroarch32/retroarch.cfg",
    f"{HOME}/.config/retroarch32/retroarch-core-options.cfg", f"{HOME}/.config/retroarch32/config",
    f"{HOME}/.emulationstation/collections", f"{HOME}/.emulationstation/es_settings.cfg",
    "/opt/amiberry/savestates", "/opt/amiberry/whdboot", "/opt/mupen64plus/InputAutoCfg.ini",
    "/opt/drastic/config/drastic.cfg", f"{HOME}/.config/filebrowser.db", f"{HOME}/.bigpemu_userdata",
    f"{HOME}/.config/.BRMODE",
]


def backup_darkos(_a=None):
    """O mesmo arquivo do "Backup dArkOS Settings" (o "Restore" do dArkOSen lê ele)."""
    root = "/roms2" if os.path.ismount("/roms2") else "/roms"
    dest = f"{root}/backup/arkosbackup.tar.gz"
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    tz = omni.read_text("/etc/timezone", "")
    if tz:
        omni.write_text("/dev/shm/TZ", tz)
    n = 0
    with tarfile.open(dest, "w:gz", dereference=True) as tar:
        for p in BACKUP_FILES + (["/dev/shm/TZ"] if tz else []):
            if os.path.exists(p):
                tar.add(p, arcname=p.lstrip("/"))
                n += 1
    os.sync()
    return f"Backup do dArkOS salvo em {dest} ({n} item(ns))"


def update_cheats(_a=None):
    tmp = "/tmp/omni36os-cheats"
    shutil.rmtree(tmp, ignore_errors=True)
    r = subprocess.run(["git", "clone", "--depth=1", "--filter=blob:none", "--sparse",
                        "https://github.com/libretro/libretro-database.git", tmp], capture_output=True, text=True,
                       timeout=600)
    if r.returncode:
        return "Sem internet ou o GitHub não respondeu. Ligue o Wi-Fi e tente de novo."
    subprocess.run(["git", "-C", tmp, "sparse-checkout", "set", "cht"], capture_output=True, timeout=600)
    dest = f"{HOME}/.config/retroarch/cheats"
    os.makedirs(dest, exist_ok=True)
    subprocess.run(["cp", "-af", f"{tmp}/cht/.", dest])
    subprocess.run(["chown", "-R", "ark:ark", dest])
    cfg = f"{HOME}/.config/retroarch32/retroarch.cfg"
    text = omni.read_text(cfg, "")
    if text:
        lines = ['cheat_database_path = "~/.config/retroarch/cheats"' if l.startswith("cheat_database_path =")
                 else l for l in text.splitlines()]
        omni.write_text(cfg, "\n".join(lines) + "\n")
    shutil.rmtree(tmp, ignore_errors=True)
    return "Trapaças do RetroArch atualizadas"


NATIVE = {
    "drastic_default": drastic_default, "gzdoom_default": gzdoom_default, "lzdoom_default": lzdoom_default,
    "bigpemu_default": bigpemu_default, "ppsspp_controls": ppsspp_controls, "ecwolf_joystick": ecwolf_joystick,
    "fix_hotkeys": fix_hotkeys, "usb_mount": usb_mount, "usb_umount": usb_umount,
    "clear_last_played": clear_last_played, "remove_dot_underscore": remove_dot_underscore,
    "backup_darkos": backup_darkos, "update_cheats": update_cheats,
}

# script (relativo a /opt/system) -> (nome, categoria, jeito, descrição, nativo)
CATALOG = {
    # Sistema
    "System/System Info.sh": ("Informações do sistema", "Sistema", "janela", "Versão, memória, cartões e rede.", None),
    "System/Change Password.sh": ("Trocar a senha", "Sistema", "janela", "Senha do usuário ark (SSH e Samba).", None),
    "System/R36S Battery Calibration Tool v1.3.sh": ("Calibrar a bateria", "Sistema", "janela",
                                                     "Ensina ao sistema a carga real da bateria.", None),
    "System/R36 Backup and Migration Assistant.sh": ("Backup e migração", "Sistema", "janela",
                                                     "Leva suas configurações para outro cartão.", None),
    "System/Boot Splash Manager.sh": ("Tela de boot", "Sistema", "janela", "Troca a imagem que aparece ao ligar.", None),
    "System/R36.Tuner.Next.sh": ("R36 Tuner", "Sistema", "janela", "Ajustes avançados do dArkOSen.", None),
    "System/USB Network Mode.sh": ("Rede pelo cabo USB", "Sistema", "janela", "Internet e SSH pelo cabo no PC.", None),
    "System/USB Drive Mount.sh": ("Montar pendrive", "Sistema", "nativo", "Pendrive no OTG em /mnt/usbdrive.",
                                  "usb_mount"),
    "System/USB Drive Unmount.sh": ("Desmontar pendrive", "Sistema", "nativo", "Para tirar o pendrive com segurança.",
                                    "usb_umount"),
    "System/Remove ._ Files.sh": ("Apagar arquivos ._ do Mac", "Sistema", "nativo",
                                  "Lixo que o macOS deixa ao copiar ROMs.", "remove_dot_underscore"),
    "Advanced/Fix Global Hotkeys.sh": ("Consertar atalhos globais", "Sistema", "nativo",
                                       "Reinicia o serviço de brilho e volume pelos botões.", "fix_hotkeys"),
    "Advanced/Controller Tester.sh": ("Testar o controle", "Sistema", "app", "Mostra cada botão apertado.", None),
    "Advanced/Backup dArkOS Settings.sh": ("Backup das configurações do dArkOS", "Sistema", "nativo",
                                           "Grava backup/arkosbackup.tar.gz no cartão.", "backup_darkos"),
    "Advanced/Restore dArkOS Settings.sh": ("Restaurar configurações do dArkOS", "Sistema", "janela",
                                            "Lê o arkosbackup.tar.gz e reinicia.", None),
    "Advanced/Clear Last Played Collection.sh": ("Zerar \"últimos jogados\"", "Jogos", "nativo",
                                                 "Apaga o histórico de jogos recentes.", "clear_last_played"),
    # Emuladores
    "Advanced/Retroarch Manager.sh": ("Gerenciador do RetroArch", "Emuladores", "janela",
                                      "Escolhe versões e opções do RetroArch.", None),
    "Advanced/Reset Retroarch Settings.sh": ("RetroArch: configuração de fábrica", "Emuladores", "janela",
                                             "Para quando o menu do RetroArch não abre mais.", None),
    "Advanced/Reset Retroarch32 Settings.sh": ("RetroArch32: configuração de fábrica", "Emuladores", "janela",
                                               "O mesmo, para o RetroArch de 32 bits.", None),
    "Advanced/Reset Retroarch Core Settings.sh": ("RetroArch: opções dos cores", "Emuladores", "janela",
                                                  "Para cores que não abrem depois de mexer nas opções.", None),
    "Advanced/Reset Retroarch32 Core Settings.sh": ("RetroArch32: opções dos cores", "Emuladores", "janela",
                                                    "O mesmo, para o RetroArch de 32 bits.", None),
    "Advanced/Update Retroarch Cheats.sh": ("Atualizar trapaças do RetroArch", "Emuladores", "nativo",
                                            "Baixa as trapaças do libretro (precisa de internet).", "update_cheats"),
    "Advanced/Restore Default Drastic Settings.sh": ("Drastic (DS): padrão", "Emuladores", "nativo",
                                                     "Configuração de fábrica do Drastic.", "drastic_default"),
    "Advanced/Drastic Bilinear Filter Mode.sh": ("Drastic: filtro bilinear", "Emuladores", "janela",
                                                 "Liga ou desliga a suavização do DS.", None),
    "Advanced/Restore Default GZdoom Settings.sh": ("GZDoom: padrão", "Emuladores", "nativo",
                                                    "Configuração de fábrica do GZDoom.", "gzdoom_default"),
    "Advanced/Restore Default LZdoom Settings.sh": ("LZDoom: padrão", "Emuladores", "nativo",
                                                    "Configuração de fábrica do LZDoom.", "lzdoom_default"),
    "Advanced/Restore Default BigPEmu Settings.sh": ("BigPEmu (Jaguar): padrão", "Emuladores", "nativo",
                                                     "Configuração de fábrica do BigPEmu.", "bigpemu_default"),
    "Advanced/Restore Default PPSSPP Controls.sh": ("PPSSPP: controles padrão", "Emuladores", "nativo",
                                                    "Apaga os controles do PSP; ele recria ao abrir.",
                                                    "ppsspp_controls"),
    "Advanced/Restore ECWolf Joystick.sh": ("ECWolf: ligar o controle", "Emuladores", "nativo",
                                            "Volta a aceitar o controle no Wolfenstein.", "ecwolf_joystick"),
    "Tools/Dave's Modern Shaders.sh": ("Shaders modernos (Dave)", "Emuladores", "janela",
                                       "Instala e escolhe shaders do RetroArch.", None),
    "Tools/Dave's Retro Shaders 2.2.sh": ("Shaders retrô (Dave)", "Emuladores", "janela",
                                          "Instala e escolhe shaders retrô.", None),
    # Jogos e arquivos
    "Advanced/PSX - CHD to ISO.sh": ("PS1: CHD para ISO", "Jogos", "janela", "Converte jogos de PS1.", None),
    "Advanced/PSP - CHD to ISO.sh": ("PSP: CHD para ISO", "Jogos", "janela", "Converte jogos de PSP.", None),
    "Advanced/Convert GIF to MP4.sh": ("Converter GIF em MP4", "Jogos", "janela", "Para vídeos de prévia no ES.", None),
    "Advanced/Convert Loading Animations.sh": ("Converter animações de carregamento", "Jogos", "janela",
                                               "Ajusta as animações para o R36S.", None),
    "Tools/R36 SD MP4 Video Converter.sh": ("Converter vídeos MP4", "Jogos", "janela",
                                            "Deixa vídeos no tamanho da tela.", None),
    "351Files.sh": ("Arquivos (351Files)", "Jogos", "app", "Gerenciador de arquivos.", None),
    "File Manager.sh": ("Arquivos (DinguxCommander)", "Jogos", "app", "Gerenciador de arquivos em duas colunas.", None),
    "Tools/PortMaster.sh": ("PortMaster", "Jogos", "app", "Loja de ports (precisa de internet).", None),
    "Tools/Install.PortMaster.sh": ("Instalar o PortMaster", "Jogos", "janela", "Baixa e instala o PortMaster.", None),
    "Tools/ThemeMaster.sh": ("ThemeMaster", "Jogos", "app", "Temas do ES.", None),
    "Tools/R36S Theme Patcher.sh": ("Ajustar temas para o R36S", "Jogos", "janela", "Corrige temas do ES.", None),
    # Perigosos
    "Advanced/dArkOSen_dtb_patcher_v1.2.sh": ("Patch do DTB (tela)", "Perigoso", "perigoso",
                                              "Mexe no arquivo de hardware do boot. Errado = tela preta.", None),
    "Advanced/60hz_display_timing_patcher.sh": ("Tela em 60 Hz", "Perigoso", "perigoso",
                                                "Muda o tempo da tela no DTB. Pode não ligar a tela.", None),
    "Advanced/fix-sd2-mount.sh": ("Consertar o 2º cartão (DTB)", "Perigoso", "perigoso",
                                  "Recompila os DTB do boot.", None),
    "Advanced/Restore dArkOSen.sh": ("Restaurar o dArkOSen", "Perigoso", "perigoso",
                                     "Troca o kernel, o ES e o ogage pelos originais.", None),
    "Advanced/Enable Quick Mode.sh": ("Modo rápido", "Perigoso", "perigoso", "Muda o que sobe no boot.", None),
    "Advanced/Remove Kodi.sh": ("Remover o Kodi", "Perigoso", "perigoso", "Apaga o Kodi do sistema.", None),
}
CATEGORIES = ("Sistema", "Emuladores", "Jogos", "Outros", "Perigoso")
KIND_LABEL = {"nativo": "No Omni36OS", "janela": "Janelas do Omni36OS", "app": "Tela própria", "perigoso": "Cuidado"}


def tools():
    """Ferramentas que existem neste sistema, com as desconhecidas em Outros."""
    out = []
    found = set()
    for rel, (name, cat, kind, desc, native) in CATALOG.items():
        p = os.path.join(ROOT, rel)
        if os.path.isfile(p):
            out.append({"path": p, "name": name, "cat": cat, "kind": kind, "desc": desc, "native": native})
            found.add(p)
    for p in sorted(glob.glob(f"{ROOT}/*.sh") + glob.glob(f"{ROOT}/*/*.sh")):
        if p not in found:
            name = os.path.splitext(os.path.basename(p))[0]
            out.append({"path": p, "name": name, "cat": "Outros", "kind": "janela",
                        "desc": "Script do dArkOSen.", "native": None})
    return out


def run_native(name):
    return NATIVE[name]()
