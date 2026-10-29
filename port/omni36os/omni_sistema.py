"""Ferramentas do sistema reescritas para o Omni36OS (sem dialog, osk nem tty).

Substituem os scripts de /opt/system:
- senha:      System/Change Password.sh
- rede USB:   System/USB Network Mode.sh (g_ether + dnsmasq/dhcp)
- calibração: System/R36S Battery Calibration Tool v1.3.sh (mesmos arquivos em
              /usr/local/etc/battery-cal, compatível com sessões já gravadas)
- DTB:        Advanced/dArkOSen_dtb_patcher_v1.2.sh (overclock e bateria no DTB)
- arquivos:   operações do navegador de arquivos do launcher
O launcher roda como root: nada aqui usa sudo.
"""
import csv
import glob
import os
import re
import shutil
import signal
import subprocess
import time

import omni


def sh(*cmd, timeout=30, inp=None):
    """(código, saída) de um comando; nunca levanta exceção."""
    try:
        r = subprocess.run(cmd, input=inp, capture_output=True, text=True, timeout=timeout)
        return r.returncode, (r.stdout + r.stderr).strip()
    except (OSError, subprocess.TimeoutExpired) as e:
        return 1, str(e)


def has(cmd):
    return shutil.which(cmd) is not None


# --- senha ---

def change_password(new):
    """Troca a senha do usuário ark (SSH, console) e a do Samba, se existir."""
    if len(new) < 3:
        return "A senha precisa de pelo menos 3 letras."
    rc, out = sh("chpasswd", inp=f"ark:{new}\n")
    if rc:
        return f"Erro: {out or 'chpasswd falhou'}"
    if has("smbpasswd"):
        sh("smbpasswd", "-s", "-a", "ark", inp=f"{new}\n{new}\n")
    return "Senha trocada. Vale para SSH, Samba e SFTP."


def samba_password(new):
    """Só a senha do Samba (compartilhamento de pastas); a do SSH não muda."""
    if not has("smbpasswd"):
        return "O Samba não está instalado neste sistema."
    if len(new) < 3:
        return "A senha precisa de pelo menos 3 letras."
    rc, out = sh("smbpasswd", "-s", "-a", "ark", inp=f"{new}\n{new}\n")
    if rc:
        return f"Erro: {out or 'smbpasswd falhou'}"
    sh("smbpasswd", "-e", "ark")
    return "Senha do Samba redefinida (usuário ark)."


# --- Wi-Fi (Sistema > Wi-Fi) ---
# Liga e desliga com os scripts do dArkOSen (carregam o módulo do adaptador USB); o resto pelo nmcli.

WIFI_ON, WIFI_OFF = "/usr/local/bin/wifi_enable.sh", "/usr/local/bin/wifi_disable.sh"


def _nm_fields(line):
    """Uma linha do nmcli -t: campos separados por ":" (o ":" dentro do nome vem como "\\:")."""
    out, cur, esc = [], "", False
    for ch in line:
        if esc:
            cur, esc = cur + ch, False
        elif ch == "\\":
            esc = True
        elif ch == ":":
            out, cur = out + [cur], ""
        else:
            cur += ch
    return out + [cur]


def wifi_iface():
    return next((n for n in sorted(os.listdir("/sys/class/net")) if n.startswith("wlan")), None)


def wifi_on():
    return bool(wifi_iface()) and sh("nmcli", "radio", "wifi")[1].strip() == "enabled"


def wifi_set(on):
    script = WIFI_ON if on else WIFI_OFF
    if os.path.exists(script):
        sh(script, timeout=60)
    else:
        sh("nmcli", "radio", "wifi", "on" if on else "off")
    if on and not wifi_iface():
        return "Não achei o adaptador de Wi-Fi. Confira se ele está no USB."
    return "Wi-Fi ligado." if on else "Wi-Fi desligado."


def wifi_current():
    """(rede, sinal %) da conexão ativa, ou (None, 0)."""
    for ln in sh("nmcli", "-t", "-f", "ACTIVE,SSID,SIGNAL", "device", "wifi")[1].splitlines():
        f = _nm_fields(ln)
        if len(f) >= 3 and f[0] == "yes":
            return f[1], int(f[2] or 0)
    return None, 0


def wifi_ip():
    dev = wifi_iface()
    if not dev:
        return ""
    m = re.search(r"inet (\d+\.\d+\.\d+\.\d+)", sh("ip", "-4", "-o", "addr", "show", dev)[1])
    return m.group(1) if m else ""


def wifi_saved():
    return [f[0] for f in map(_nm_fields, sh("nmcli", "-t", "-f", "NAME,TYPE", "connection", "show")[1].splitlines())
            if len(f) >= 2 and f[1] == "802-11-wireless"]


def wifi_scan():
    """[{rede, sinal, senha, atual, salva}] sem repetidas, a mais forte primeiro."""
    code, txt = sh("nmcli", "-t", "-f", "IN-USE,SSID,SIGNAL,SECURITY", "device", "wifi", "list", "--rescan", "yes",
                   timeout=30)
    saved, best = set(wifi_saved()), {}
    for ln in txt.splitlines() if code == 0 else []:
        f = _nm_fields(ln)
        if len(f) < 4 or not f[1]:
            continue
        n = {"rede": f[1], "sinal": int(f[2] or 0), "senha": f[3] not in ("", "--"), "atual": f[0] == "*",
             "salva": f[1] in saved}
        if n["rede"] not in best or n["sinal"] > best[n["rede"]]["sinal"] or n["atual"]:
            best[n["rede"]] = n
    return sorted(best.values(), key=lambda n: (not n["atual"], -n["sinal"]))


def wifi_connect(rede, senha=None):
    if rede in wifi_saved() and not senha:
        code, txt = sh("nmcli", "connection", "up", "id", rede, timeout=45)
    else:
        sh("nmcli", "connection", "delete", "id", rede)      # senha nova: some a antiga
        cmd = ["nmcli", "device", "wifi", "connect", rede] + (["password", senha] if senha else [])
        code, txt = sh(*cmd, timeout=45)
    if code == 0:
        ip = wifi_ip()
        return f"Conectado a {rede}." + (f" IP: {ip}" if ip else "")
    if "Secrets were required" in txt or "802-1X" in txt or "password" in txt.lower():
        sh("nmcli", "connection", "delete", "id", rede)
        return f"Não conectou a {rede}: senha errada."
    return f"Não conectou a {rede}. Chegue mais perto do roteador e tente de novo."


def wifi_disconnect():
    dev = wifi_iface()
    return "Desconectado." if dev and sh("nmcli", "device", "disconnect", dev)[0] == 0 else "Não estava conectado."


def wifi_forget(rede):
    return f"{rede} esquecida." if sh("nmcli", "connection", "delete", "id", rede)[0] == 0 else \
        f"Não achei {rede} nas redes salvas."


def wifi_status():
    """Achados para o painel da página Wi-Fi (atualiza sozinho)."""
    if not wifi_iface():
        return [("aviso", "Nenhum adaptador de Wi-Fi encontrado. O R36S usa um adaptador USB: confira se ele está "
                          "ligado e se o modo pendrive e a rede USB estão desligados.")]
    if not wifi_on():
        return [("info", "Wi-Fi desligado.")]
    rede, sinal = wifi_current()
    if not rede:
        n = len(wifi_saved())
        return [("info", "Wi-Fi ligado, sem conexão."),
                ("info", f"{n} rede(s) salva(s)." if n else "Nenhuma rede salva: escolha uma em Procurar redes.")]
    ip = wifi_ip()
    out = [("ok", f"Conectado a {rede}, sinal {sinal}%."),
           ("ok" if ip else "aviso", f"IP do console: {ip}" if ip else "Ainda sem IP.")]
    if ip:
        out.append(("info", f"No PC: ssh ark@{ip}  ·  sftp://ark@{ip}"))
    if sinal < 35:
        out.append(("aviso", "Sinal fraco: downloads podem falhar."))
    return out


# --- nome do jogador ---

CFG = os.path.expanduser("~ark/.config/omni36os")
PLAYER = f"{CFG}/jogador"
TELA = f"{CFG}/boas-vindas.raw"      # tela do boot com o nome (omni_tela.py); o omni36os-tela usa se existir


def player_name():
    return omni.read_text(PLAYER, "").strip()


def set_player_name(name):
    name = " ".join(name.split())[:20]
    omni.save_file(PLAYER, name + "\n")
    try:
        os.chown(CFG, 1000, 1000)
        os.chown(PLAYER, 1000, 1000)
    except OSError:
        pass
    try:
        import omni_tela
        if omni_tela.boas_vindas(name, TELA):
            os.chown(TELA, 1000, 1000)
    except Exception:   # sem a base ou sem a SDL_ttf: o boot mostra a tela padrão
        pass
    return name


# --- trava do console por senha ---
# A senha fica em texto simples no cartão do sistema (EASYROMS/senha/senha.txt), de
# propósito: quem esquecer abre o cartão no PC e lê. Apagar o arquivo desliga a trava.

LOCK_DIR = "/roms/senha"
LOCK_FILE = f"{LOCK_DIR}/senha.txt"


def lock_password():
    for ln in omni.read_text(LOCK_FILE, "").splitlines():
        if ln.lower().startswith("senha:"):
            return ln.split(":", 1)[1].strip()
    return None


def lock_on():
    return bool(lock_password())


def lock_set(pw):
    pw = pw.strip()
    if len(pw) < 3:
        return "A senha precisa de pelo menos 3 letras."
    omni.save_file(LOCK_FILE, "Senha da trava do Omni36OS (pedida ao ligar o console).\n"
                              "Para tirar a trava pelo PC, apague este arquivo.\n\n"
                              f"senha: {pw}\n")
    sh("sync")
    return "Trava ligada. A senha também está em EASYROMS/senha/senha.txt."


def lock_check(pw):
    return pw.strip() == (lock_password() or "")


def lock_clear():
    try:
        os.remove(LOCK_FILE)
    except OSError:
        pass
    sh("sync")
    return "Trava desligada."


# --- zerar a personalização ---

def reset_custom():
    """Volta ao primeiro boot: apaga nome, trava, tema e posição da biblioteca, desliga o zram e
    volta processador, GPU, atalhos e botão de power ao padrão.
    Ports, jogos, senhas do sistema/Samba e testes ficam."""
    for f in (PLAYER, TELA, LOCK_FILE, f"{CFG}/tema", "/tmp/omni36os-biblioteca.json", omni.ATALHOS_CONF):
        try:
            os.remove(f)
        except OSError:
            pass
    if zram_get():
        zram_set(0)
    # ajustes de uso nos padrões de fábrica: Equilibrado, 1296/520 MHz (sem OC), atalho e power
    for fn, arg in ((omni.set_preferred_governor, {"governor": "ondemand"}), (omni.set_cpu_max, {"mhz": 1296}),
                    (omni.set_gpu_max, {"mhz": 520}), (omni.set_atalho, {"key": "fps", "value": True}),
                    (omni.set_power_button, {"mode": "desligar"})):
        try:
            fn(arg)
        except Exception:     # um ajuste que falhe não impede o resto
            pass
    sh("sync")
    return "Sistema zerado."


# --- rede pelo cabo USB (g_ether) ---

USBNET_PID, USBNET_LEASES = "/tmp/dnsmasq-usbnet.pid", "/tmp/usbnet.leases"
USBNET_LOG = "/tmp/usbnet-dnsmasq.log"
DEV_MAC, HOST_MAC = "42:61:72:6b:6f:53", "42:61:72:6b:6f:54"
DHCP_CLIENTS = ("dhclient", "dhcpcd", "udhcpc")
UNIVERSAL_IP = "10.44.44.1"


def _lsmod(mod):
    return any(ln.split()[0] == mod for ln in omni.read_text("/proc/modules", "").splitlines() if ln)


def pendrive_on():
    """Modo pendrive do launcher: a porta subiu como "peripheral" (DTB do boot atual) e o gadget é dele."""
    return omni.read_text("/proc/device-tree/usb@ff300000/dr_mode", "").strip("\0\n ") == "peripheral"


def usb_ip():
    m = re.search(r"inet ([0-9.]+)", sh("ip", "-4", "addr", "show", "usb0")[1])
    return m.group(1) if m else ""


def usbnet_mode():
    if not _lsmod("g_ether"):
        return "desligada"
    if any(sh("pgrep", "-f", f"{c}.*usb0")[0] == 0 for c in DHCP_CLIENTS):
        return "internet"
    return "universal"


def remote_on():
    return sh("pgrep", "-x", "filebrowser")[0] == 0 or sh("systemctl", "is-active", "--quiet", "smbd")[0] == 0


def usbnet_status():
    """Achados para o painel da subpágina (atualiza sozinho)."""
    mode, ip = usbnet_mode(), usb_ip()
    out = []
    if mode == "desligada":
        out.append(("info", "Rede USB desligada: a porta OTG está no modo normal."))
    else:
        nome = {"universal": "universal (o console dá o IP ao PC)",
                "internet": "internet pelo PC (o PC compartilha a conexão)"}[mode]
        out.append(("ok", f"Rede USB ligada, modo {nome}."))
        out.append(("ok" if ip else "aviso", f"IP do console: {ip}" if ip else "Ainda sem IP."))
        if mode == "universal":
            if not _dhcp_alive():
                out.append(("problema", "O servidor DHCP parou: o PC não vai receber IP. Ligue o modo de novo."))
            else:
                leases = [ln.split() for ln in omni.read_text(USBNET_LEASES, "").splitlines() if ln.strip()]
                out.append(("ok" if leases else "info", "IP entregue ao PC: " + ", ".join(l[2] for l in leases if len(l) > 2)
                            if leases else "Servidor DHCP ativo, esperando o PC pedir IP."))
        if ip:
            out.append(("info", f"No PC: ssh ark@{ip}  ·  sftp://ark@{ip}"))
            if remote_on():
                out.append(("info", f"Web: http://{ip}  ·  Samba: smb://{ip}  (\\\\{ip} no Windows)"))
    out.append(("info", "Serviços remotos (web e Samba): " + ("ligados." if remote_on() else "desligados.")))
    if pendrive_on():
        out.append(("aviso", "O modo pendrive está ligado: ele usa a mesma porta. Desligue-o antes."))
    return out


def _kill_dhcp():
    for c in DHCP_CLIENTS:
        sh("pkill", "-f", f"{c}.*usb0")
    pid = omni.read_text(USBNET_PID, "").strip()
    if pid.isdigit():
        try:
            os.kill(int(pid), signal.SIGTERM)
        except OSError:
            pass


def _load_gadget():
    if _lsmod("g_ether") and omni.read_text("/sys/class/net/usb0/address", "").strip() != DEV_MAC:
        sh("rmmod", "g_ether")
        time.sleep(1)
    rc, err = sh("modprobe", "g_ether", f"dev_addr={DEV_MAC}", f"host_addr={HOST_MAC}",
                 "iProduct=R36S", "iManufacturer=Omni36OS")
    time.sleep(2)
    if os.path.exists("/sys/class/net/usb0"):
        return None
    if not glob.glob("/sys/class/udc/*"):
        return "A porta não funciona como dispositivo USB (sem controlador UDC: o DTB a deixou só como host)."
    if sh("modinfo", "g_ether")[0]:
        return "O kernel deste sistema não tem o módulo g_ether."
    if _lsmod("g_ether"):
        return "O g_ether carregou, mas o usb0 não apareceu: outro modo (pendrive?) está usando a porta."
    return f"O modprobe falhou: {err[:160]}" if err else "Motivo desconhecido."


def _unmanage():
    """Tira a usb0 do NetworkManager: senão ele roda um cliente DHCP nela e apaga o IP fixo do console."""
    if has("nmcli"):
        sh("nmcli", "device", "set", "usb0", "managed", "no")
        time.sleep(1)


def _dhcp_alive():
    pid = omni.read_text(USBNET_PID, "").strip()
    return pid.isdigit() and os.path.exists(f"/proc/{pid}")


def usbnet_universal():
    if pendrive_on():
        return "Desligue o modo pendrive antes (ele usa a mesma porta)."
    if not has("dnsmasq"):
        return "Falta o dnsmasq no sistema: o modo universal não funciona."
    _kill_dhcp()
    err = _load_gadget()
    if err:
        return "Erro: " + err
    _unmanage()
    sh("ip", "addr", "flush", "dev", "usb0")
    sh("ip", "addr", "add", f"{UNIVERSAL_IP}/24", "dev", "usb0")
    sh("ip", "link", "set", "usb0", "up")
    sh("systemctl", "start", "ssh")
    for f in (USBNET_LEASES, USBNET_LOG):
        try:
            os.remove(f)
        except OSError:
            pass
    rc, err = sh("dnsmasq", "--interface=usb0", "--bind-interfaces", "--except-interface=lo", "--port=0",
                 "--dhcp-range=10.44.44.10,10.44.44.100,255.255.255.0,12h", "--dhcp-authoritative",
                 "--dhcp-option=3", "--dhcp-option=6", "--user=root", "--log-dhcp",
                 f"--log-facility={USBNET_LOG}", f"--pid-file={USBNET_PID}",
                 f"--dhcp-leasefile={USBNET_LEASES}", "--conf-file=/dev/null")
    time.sleep(1)
    if rc or not _dhcp_alive():
        return "Erro: o servidor DHCP não subiu. " + (err or omni.read_text(USBNET_LOG, "")[-160:]).strip()
    if usb_ip() != UNIVERSAL_IP:
        return "Erro: o IP do console sumiu da usb0 (outro programa mexeu nela)."
    return f"Modo universal ligado. Ligue o cabo no PC e use: ssh ark@{UNIVERSAL_IP}"


def _ask_ip():
    c = next((c for c in DHCP_CLIENTS if has(c)), None)
    if c == "dhclient":
        sh("dhclient", "-1", "usb0", timeout=22)
    elif c == "dhcpcd":
        sh("dhcpcd", "-1", "usb0", timeout=22)
    elif c == "udhcpc":
        sh("udhcpc", "-i", "usb0", "-n", "-q", "-t", "5", timeout=22)
    if usb_ip():
        return ""
    for addr, gw in (("10.42.0.2/24", "10.42.0.1"), ("192.168.137.2/24", "192.168.137.1")):
        sh("ip", "addr", "flush", "dev", "usb0")
        sh("ip", "addr", "add", addr, "dev", "usb0")
        if sh("ping", "-I", "usb0", "-c", "1", "-W", "2", gw)[0] == 0:
            sh("ip", "route", "add", "default", "via", gw, "dev", "usb0")
            if "nameserver" not in omni.read_text("/etc/resolv.conf", ""):
                with open("/etc/resolv.conf", "a") as f:
                    f.write("nameserver 1.1.1.1\n")
            return " (endereço fixo)"
    sh("ip", "addr", "flush", "dev", "usb0")
    return None


def usbnet_internet():
    if pendrive_on():
        return "Desligue o modo pendrive antes (ele usa a mesma porta)."
    _kill_dhcp()
    err = _load_gadget()
    if err:
        return "Erro: " + err
    _unmanage()
    sh("ip", "addr", "flush", "dev", "usb0")
    sh("ip", "link", "set", "usb0", "up")
    via = _ask_ip()
    if via is None:
        return "O PC não deu IP. Ligue o compartilhamento de internet no PC e tente de novo."
    sh("systemctl", "start", "ssh")
    net = sh("ping", "-c", "2", "-W", "3", "8.8.8.8", timeout=10)[0] == 0
    if net:
        sh("timedatectl", "set-ntp", "1")
    return (f"Modo internet ligado. IP {usb_ip()}{via}. "
            + ("Internet funcionando." if net else "Sem rota para a internet: confira o PC."))


def usbnet_services(on):
    if on:
        if usbnet_mode() == "desligada":
            return "Ligue a rede USB primeiro."
        sh("systemctl", "start", "ssh")
        sh("systemctl", "start", "smbd")
        sh("systemctl", "start", "nmbd")
        if has("filebrowser"):
            sh("pkill", "-x", "filebrowser")
            subprocess.Popen(["filebrowser", "-a", "0.0.0.0", "-p", "80", "-d",
                              "/home/ark/.config/filebrowser.db", "-r", "/"],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
        return "Serviços remotos ligados (usuário e senha: ark)."
    for u in ("smbd", "nmbd"):
        sh("systemctl", "stop", u)
    sh("pkill", "-x", "filebrowser")
    return "Serviços remotos desligados (o SSH continua)."


def usbnet_stop():
    if usbnet_mode() == "desligada":
        return "A rede USB já está desligada."
    usbnet_services(False)
    _kill_dhcp()
    sh("ip", "addr", "flush", "dev", "usb0")
    sh("ip", "link", "set", "usb0", "down")
    sh("rmmod", "g_ether")
    return "Rede USB desligada: a porta OTG voltou ao normal."


def usbnet_compat():
    """Relatório de compatibilidade (texto para o leitor)."""
    out = ["# Módulos do kernel"]
    for m in ("g_ether", "libcomposite", "usb_f_rndis", "usb_f_ecm"):
        st = "carregado" if _lsmod(m) else ("disponível" if sh("modinfo", m)[0] == 0 else "não existe")
        out.append(f"{m}: {st}")
    out.append("# Controlador USB (UDC)")
    udcs = glob.glob("/sys/class/udc/*")
    out += [f"{os.path.basename(u)}: {omni.read_text(u + '/state', '?').strip()}" for u in udcs] or \
           ["Nenhum: a porta só funciona como host (precisa de outro DTB)."]
    out.append("# dr_mode no DTB")
    seen = set()
    for f in glob.glob("/proc/device-tree/*usb*/dr_mode"):
        node = os.path.basename(os.path.dirname(f))
        if node not in seen:
            seen.add(node)
            out.append(f"{node}: {omni.read_text(f, '').strip(chr(0))}")
    out.append("# Programas")
    for c in ("ip", "dnsmasq", *DHCP_CLIENTS, "filebrowser", "smbd"):
        out.append(f"{c}: {'ok' if has(c) else 'falta'}")
    return "\n".join(out)


# --- calibração da bateria (mesmos arquivos do script original) ---

PS = "/sys/class/power_supply/battery"
CAL_DIR = "/usr/local/etc/battery-cal"
SESSION = f"{CAL_DIR}/session.csv"
CURVE = f"{CAL_DIR}/curve.conf"
CAL_UNIT = "battery-cal.service"
SAMPLER_UNIT = "omni36os-bateria-amostras"
DAEMON = "/usr/local/bin/battery-cal-daemon.sh"
CHARGE_MIN_MV, CUTOFF_MV, MIN_SAMPLES = 4050, 3000, 10


def bat_mv():
    v = omni.read_text(f"{PS}/voltage_now", "0").strip()
    return int(v) // 1000 if v.isdigit() else 0


def bat_state():
    return omni.read_text(f"{PS}/status", "").strip()


def cal_running():
    return sh("systemctl", "is-active", "--quiet", SAMPLER_UNIT)[0] == 0


def cal_samples():
    try:
        with open(SESSION) as f:
            return [r for r in csv.DictReader(f) if r.get("voltage_mv", "").isdigit()]
    except OSError:
        return []


def cal_service_on():
    return sh("systemctl", "is-active", "--quiet", CAL_UNIT)[0] == 0


def cal_status():
    s = cal_samples()
    mv, st = bat_mv(), bat_state()
    out = [("info", f"Bateria agora: {mv} mV, {omni.read_text(PS + '/capacity', '?').strip()}%"
                    f" ({ {'Charging': 'carregando', 'Full': 'cheia', 'Discharging': 'descarregando'}.get(st, st.lower())})")]
    if cal_running():
        out.append(("ok", f"Calibração em andamento: {len(s)} amostras (uma por minuto). "
                          "Jogue normalmente até o console desligar sozinho."))
    elif s:
        mins = (int(s[-1]["timestamp"]) - int(s[0]["timestamp"])) // 60 if len(s) > 1 else 0
        lvl = "ok" if len(s) >= MIN_SAMPLES else "aviso"
        out.append((lvl, f"Última sessão: {len(s)} amostras em {mins} min, de {s[0]['voltage_mv']} a "
                         f"{s[-1]['voltage_mv']} mV." + ("" if lvl == "ok" else " Poucas para aplicar.")))
    else:
        out.append(("info", "Nenhuma sessão gravada ainda."))
    if os.path.exists(CURVE):
        out.append(("ok" if cal_service_on() else "aviso",
                    "Curva calibrada " + ("ATIVA: a % da bateria já usa a sua curva." if cal_service_on()
                                          else "gravada, mas o serviço está desligado.")))
    else:
        out.append(("info", "Usando a curva de fábrica (a % pode pular no fim da carga)."))
    out.append(("info", "Como calibrar: carregue até 100%, tire o cabo, toque em Iniciar e use o console até ele "
                        "desligar. Depois carregue e toque em Aplicar."))
    return out


SAMPLER = r'''
import csv, os, time
PS = "/sys/class/power_supply/battery"
def rd(n):
    try:
        return open(f"{PS}/{n}").read().strip()
    except OSError:
        return ""
first = prev = 0
buf, settling = [], True
while rd("status") != "Charging":
    mv = int(rd("voltage_now") or 0) // 1000
    row = [int(time.time()), mv, rd("capacity"), rd("health") or "Good"]
    if settling:
        if prev and prev - mv < 50:          # a tensão parou de cair rápido (carga de superfície)
            settling = False
            rows = ([] if first - mv > 150 else buf) + [row]
        else:
            first = first or mv
            buf.append(row)
            rows = []
        prev = mv
    else:
        rows = [row]
    if rows:
        with open("%s", "a", newline="") as f:
            csv.writer(f).writerows(rows)
    if mv <= %d:
        break
    time.sleep(60)
''' % (SESSION, CUTOFF_MV)


def cal_start():
    if cal_running():
        return "A calibração já está rodando."
    if bat_state() == "Charging":
        return "Tire o carregador antes de começar."
    if bat_mv() < CHARGE_MIN_MV:
        return f"Carregue até o fim antes (agora {bat_mv()} mV; precisa de {CHARGE_MIN_MV} mV ou mais)."
    if cal_service_on():                       # a curva antiga não pode mexer nas leituras
        sh("systemctl", "disable", "--now", CAL_UNIT)
    os.makedirs(CAL_DIR, exist_ok=True)
    with open(SESSION, "w") as f:
        f.write("timestamp,voltage_mv,stock_pct,health\n")
    for f in ("session.bad", "session.checked", "session.incomplete"):
        try:
            os.remove(f"{CAL_DIR}/{f}")
        except OSError:
            pass
    # unidade transitória do systemd: continua com o launcher fechado e durante os jogos
    rc, out = sh("systemd-run", f"--unit={SAMPLER_UNIT}", "--collect", "python3", "-c", SAMPLER)
    return "Calibração iniciada. Use o console até ele desligar sozinho." if rc == 0 else f"Erro: {out}"


def cal_stop():
    if not cal_running():
        return "Nenhuma calibração rodando."
    sh("systemctl", "stop", SAMPLER_UNIT)
    return f"Calibração parada com {len(cal_samples())} amostras."


def _fit(rows):
    """Mesmo ajuste do script original: % real pela ordem das amostras -> tabela mV:%."""
    rows = sorted(rows, key=lambda r: int(r["timestamp"]))
    n = len(rows) - 1
    pts = sorted((round(100 - i / n * 100), int(r["voltage_mv"])) for i, r in enumerate(rows))
    pcts, mvs = [p for p, _ in pts], [m for _, m in pts]

    def mv_at(t):
        if t >= pcts[-1]:
            return mvs[-1]
        if t <= pcts[0]:
            return mvs[0]
        for i in range(len(pcts) - 1):
            if pcts[i] <= t <= pcts[i + 1]:
                span = pcts[i + 1] - pcts[i]
                return mvs[i] if span == 0 else round(mvs[i] + (t - pcts[i]) / span * (mvs[i + 1] - mvs[i]))
    out, last = [], -1
    for mv, p in sorted((mv_at(p), p) for p in range(101)):
        last = max(last, p)
        out.append((mv, last))
    return out


DAEMON_SH = r'''#!/bin/bash
# Gerado pelo Omni36OS (calibração da bateria): troca a % de fábrica pela curva calibrada.
PS=/sys/class/power_supply/battery
FAKE_CAP=/run/battery_capacity
CURVE=/usr/local/etc/battery-cal/curve.conf
trap 'grep -q "$PS/capacity" /proc/mounts && umount "$PS/capacity"; rm -f "$FAKE_CAP"' EXIT
[ -f "$CURVE" ] || exit 1
while true; do
  MV=$(( $(cat $PS/voltage_now) / 1000 )); ST=$(cat $PS/status)
  if [ "$ST" = Full ]; then PCT=100; else
    PCT=$(awk -F: -v mv="$MV" '{v[NR]=$1;p[NR]=$2} END{if(mv<=v[1]){print p[1];exit} if(mv>=v[NR]){print p[NR];exit}
      for(i=1;i<NR;i++) if(v[i]<=mv && mv<=v[i+1]){print int(p[i]+(mv-v[i])/(v[i+1]-v[i])*(p[i+1]-p[i]));exit}}' "$CURVE")
  fi
  echo "$PCT" > "$FAKE_CAP"
  for i in $(seq 30); do sleep 1; [ "$(cat $PS/status)" != "$ST" ] && break; done
done
'''

# Sem o "Requires=" do original (ele dependia do ES, que o Omni36OS não tem).
CAL_SERVICE = '''[Unit]
Description=Battery Calibration Daemon (Omni36OS)
StartLimitIntervalSec=0

[Service]
Type=simple
Restart=always
RestartSec=3
ExecStartPre=/bin/bash -c 'echo 0 > /run/battery_capacity && mount --bind /run/battery_capacity /sys/class/power_supply/battery/capacity'
ExecStart=/usr/local/bin/battery-cal-daemon.sh
ExecStopPost=-/bin/umount /sys/class/power_supply/battery/capacity

[Install]
WantedBy=multi-user.target
'''


def cal_apply():
    if cal_running():
        return "Pare a calibração antes de aplicar (ou espere o console desligar)."
    s = cal_samples()
    if len(s) < MIN_SAMPLES:
        return f"Poucas amostras ({len(s)}): faça uma calibração completa antes."
    curve = _fit(s)
    omni.save_file(CURVE, "".join(f"{mv}:{p}\n" for mv, p in curve))
    omni.save_file(f"{CAL_DIR}/curve.source", "session.csv\n")
    omni.save_file(DAEMON, DAEMON_SH)
    os.chmod(DAEMON, 0o755)
    omni.save_file(f"/etc/systemd/system/{CAL_UNIT}", CAL_SERVICE)
    sh("systemctl", "daemon-reload")
    sh("systemctl", "enable", "--now", CAL_UNIT)
    pts = {p: mv for mv, p in curve}
    resumo = "  ".join(f"{p}%={pts[p]}mV" for p in (100, 50, 20, 5) if p in pts)
    return ("Curva aplicada. " + resumo) if cal_service_on() else "Curva gravada, mas o serviço não subiu."


def cal_restore():
    sh("systemctl", "disable", "--now", CAL_UNIT)
    for f in (f"/etc/systemd/system/{CAL_UNIT}", CURVE):
        try:
            os.remove(f)
        except OSError:
            pass
    sh("systemctl", "daemon-reload")
    return "Curva de fábrica de volta."


# --- DTB: overclock e bateria (mesmo patch do dArkOSen_dtb_patcher_v1.2) ---

DTB = "/boot/rk3326-r36s-linux.dtb"
OC_FREQS = (1368, 1416, 1440, 1464, 1488, 1512)
OPP_UV = {1368: "0x149970"}           # 1,35 V; as outras usam 0x155cc0 (1,40 V)
NEW_DZ = "0x180"
BAT = {"ocv_table": "3400 3442 3494 3537 3574 3604 3633 3666 3697 3726 3760 3790 3812 3842 3886 3928 3955 3990 "
                    "4036 4105 4177", "design_capacity": "3140", "design_qmax": "3454", "bat_res": "100",
       "power_off_thresd": "3300"}


def _dts(path=None):
    try:
        r = subprocess.run(["dtc", "-q", "-I", "dtb", "-O", "dts", path or DTB], capture_output=True, text=True,
                           timeout=60)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return r.stdout if r.returncode == 0 and r.stdout.startswith("/dts-v1/") else None


def dtb_status():
    if not has("dtc"):
        return [("problema", "Falta o dtc (device-tree-compiler) no sistema.")]
    if not os.path.exists(DTB):
        return [("aviso", f"{DTB} não existe nesta placa (DTB de outro modelo).")]
    d = _dts()
    if d is None:
        return [("problema", "Não deu para ler o DTB.")]
    oc = all(f"opp-{f}000000" in d for f in OC_FREQS)
    gpu = "opp-600000000" in d
    m = re.search(r"design_capacity = <(0x[0-9a-f]+|\d+)>", d)
    cap = int(m.group(1), 0) if m else None
    out = [("ok" if oc else "info", "Overclock do processador até 1512 MHz: " + ("liberado." if oc else "não aplicado.")),
           ("ok" if gpu else "info", "GPU até 600 MHz: " + ("liberada." if gpu else "não aplicada.")),
           ("ok" if cap == 3140 else "info", f"Bateria no DTB: {cap or '?'} mAh"
            + (" (tabela corrigida)." if cap == 3140 else " (tabela de fábrica)."))]
    baks = sorted(glob.glob(DTB + ".*.omni36os.bak"))
    out.append(("info", f"Cópia de segurança: {os.path.basename(baks[-1])}" if baks else "Sem cópia de segurança ainda."))
    out.append(("info", "Os limites de frequência ficam em Desempenho. A mudança vale depois de reiniciar."))
    return out


def _compile(dts, target):
    tmp = target + ".new"
    rc, out = sh("dtc", "-q", "-I", "dts", "-O", "dtb", "-o", tmp, "-", inp=dts, timeout=60)
    if rc or _dts(tmp) is None:
        try:
            os.remove(tmp)
        except OSError:
            pass
        return f"Erro ao compilar (nada foi mudado): {out[:200]}"
    os.replace(tmp, target)
    sh("sync")
    return None


def _backup():
    bak = DTB + "." + time.strftime("%Y%m%d-%H%M%S") + ".omni36os.bak"
    shutil.copy2(DTB, bak)
    return bak


def dtb_overclock():
    d = _dts()
    if d is None:
        return "Não deu para ler o DTB."
    if all(f"opp-{f}000000" in d for f in OC_FREQS) and "opp-600000000" in d:
        return "O overclock já está aplicado."
    lines, out, i = d.split("\n"), [], 0
    patched = False
    while i < len(lines):
        ln = lines[i]
        out.append(ln)
        anchor = re.search(r"\b(opp-1296000000|opp-520000000) \{", ln)
        if anchor:
            ind = ln[:len(ln) - len(ln.lstrip())]
            i += 1
            while not lines[i].startswith(ind + "};"):
                out.append(lines[i])
                i += 1
            out.append(lines[i])
            if anchor.group(1) == "opp-1296000000":
                for f in OC_FREQS:
                    if f"opp-{f}000000" in d:
                        continue
                    uv = OPP_UV.get(f, "0x155cc0")
                    out += [f"{ind}opp-{f}000000 {{", f"{ind}\topp-hz = <0x00 {f * 1000000:#x}>;",
                            f"{ind}\topp-microvolt = <{uv} {uv} {uv}>;",
                            *[f"{ind}\topp-microvolt-L{k} = <{uv} {uv} {uv}>;" for k in range(4)],
                            f"{ind}\tclock-latency-ns = <0x9c40>;", f"{ind}}};"]
                    patched = True
            elif "opp-600000000" not in d:
                out += [f"{ind}opp-600000000 {{", f"{ind}\topp-microvolt = <0x115b5c>;",
                        f"{ind}\topp-microvolt-L0 = <0x10f9b4>;", f"{ind}\topp-hz = <0x00 0x23c34600>;", f"{ind}}};"]
                patched = True
        i += 1
    if not patched:
        return "Não achei a tabela de frequências esperada neste DTB: nada foi mudado."
    d = "\n".join(out)
    # tensão máxima do processador e do regulador acompanham as frequências novas
    d = re.sub(r"(cpu0-opp-table \{.*?rockchip,max-volt = <)0x[0-9a-f]+(>)", r"\g<1>0x155cc0\2", d, count=1, flags=re.S)
    d = re.sub(r"(DCDC_REG2 \{.*?regulator-max-microvolt = <)0x[0-9a-f]+(>)", r"\g<1>0x155cc0\2", d, count=1, flags=re.S)
    d = re.sub(r"(button-adc-deadzone = <)[^>]+(>)", rf"\g<1>{NEW_DZ}\2", d)
    bak = _backup()
    err = _compile(d, DTB)
    return err or f"Overclock liberado. Reinicie para valer. Cópia: {os.path.basename(bak)}"


def dtb_battery():
    d = _dts()
    if d is None:
        return "Não deu para ler o DTB."
    if 'compatible = "rk817,battery"' not in d:
        return "Este DTB não tem o nó de bateria rk817: nada foi mudado."
    if re.search(r"design_capacity = <(0xc44|3140)>", d):
        return "A tabela da bateria já está corrigida."
    for k, v in BAT.items():
        d = re.sub(rf"(\b{k}\s*=\s*)<[^>]*>", rf"\g<1><{v}>", d)
    bak = _backup()
    err = _compile(d, DTB)
    return err or f"Tabela da bateria corrigida. Reinicie para valer. Cópia: {os.path.basename(bak)}"


def dtb_restore():
    baks = sorted(glob.glob(DTB + ".*.omni36os.bak"))
    if not baks:
        return "Não há cópia de segurança para voltar."
    shutil.copy2(baks[-1], DTB)
    os.remove(baks[-1])
    sh("sync")
    return f"DTB de antes voltou ({os.path.basename(baks[-1])}). Reinicie para valer."


# --- zram (swap comprimido na RAM) ---

ZRAM_CONF = "/etc/zram.conf"
ZRAM_SIZES = [0, 256, 512, 768]     # MB; 0 = desligado (padrão)


def zram_get():
    """Tamanho do zram em MB (0 = desligado), pelo que está valendo agora."""
    try:
        with open("/proc/swaps") as f:
            if "/dev/zram0" not in f.read():
                return 0
        with open("/sys/block/zram0/disksize") as f:
            return int(f.read()) // (1024 * 1024)
    except (OSError, ValueError):
        return 0


def zram_set(mb):
    """Liga o zram com mb MB (até 768) ou desliga (0). Vale na hora e nos próximos boots."""
    mb = max(0, min(768, int(mb)))
    omni.save_file(ZRAM_CONF, f"ENABLED={1 if mb else 0}\n# O kernel 4.4 do R36S não tem lz4 no crypto: lzo é o "
                              f"mais rápido\nALGORITHM=lzo\nSIZE={mb * 1024 * 1024}\n")
    # o que estiver no swap volta para a RAM antes de trocar o tamanho
    sh("swapoff", "/dev/zram0", timeout=120)
    try:
        with open("/sys/block/zram0/reset", "w") as f:
            f.write("1")
    except OSError:
        pass
    if mb:
        sh("systemctl", "enable", "zram_autostart.service")
        sh("/usr/local/bin/zram_autostart.sh", timeout=30)
    else:
        sh("systemctl", "disable", "zram_autostart.service")
    got = zram_get()
    if mb and got == 0:
        return "Não foi possível ligar o zram"
    return f"Memória extra (zram) de {got} MB ligada" if got else "Memória extra (zram) desligada"


# --- arquivos ---

ROOTS = ("/roms", "/roms2", "/mnt/usbdrive")


def human(n):
    for u in ("B", "KB", "MB", "GB"):
        if n < 1024 or u == "GB":
            return f"{n:.0f} {u}" if u == "B" else f"{n:.1f} {u}"
        n /= 1024


def listdir(path):
    """[(nome, é_pasta, tamanho)] com as pastas primeiro."""
    out = []
    try:
        with os.scandir(path) as it:
            for e in it:
                if e.name.startswith("._"):
                    continue
                try:
                    d = e.is_dir()
                    out.append((e.name, d, 0 if d else e.stat().st_size))
                except OSError:
                    continue
    except OSError:
        return []
    return sorted(out, key=lambda x: (not x[1], x[0].lower()))


def fs_delete(path):
    if os.path.isdir(path) and not os.path.islink(path):
        shutil.rmtree(path)
    else:
        os.remove(path)
    sh("sync")
    return f"Apagado: {os.path.basename(path)}"


def fs_paste(src, dest_dir, move):
    dst = os.path.join(dest_dir, os.path.basename(src))
    if os.path.abspath(dst) == os.path.abspath(src):
        return "A origem e o destino são o mesmo lugar."
    if os.path.exists(dst):
        return f"Já existe {os.path.basename(dst)} aqui."
    if (dest_dir + "/").startswith(src.rstrip("/") + "/"):
        return "Não dá para colocar uma pasta dentro dela mesma."
    if move:
        shutil.move(src, dst)
    elif os.path.isdir(src):
        shutil.copytree(src, dst)
    else:
        shutil.copy2(src, dst)
    sh("sync")
    return ("Movido: " if move else "Copiado: ") + os.path.basename(src)


def fs_rename(path, new):
    new = new.strip().replace("/", "_")
    if not new:
        return "Nome vazio."
    dst = os.path.join(os.path.dirname(path), new)
    if os.path.exists(dst):
        return f"Já existe {new} aqui."
    os.rename(path, dst)
    return f"Renomeado para {new}"


def fs_mkdir(path, name):
    name = name.strip().replace("/", "_")
    if not name:
        return "Nome vazio."
    os.makedirs(os.path.join(path, name), exist_ok=False)
    return f"Pasta criada: {name}"
