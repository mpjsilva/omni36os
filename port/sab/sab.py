#!/usr/bin/env python3
"""Sab — diagnóstico e ajustes do R36S. Só stdlib.

Uso: sab.py <ferramenta> ['{"arg": valor}']   (sem argumentos lista as ferramentas)
"""
import configparser
import glob
import hashlib
import json
import os
import shutil
import struct
import subprocess
import sys
import time

DT = "/proc/device-tree"
DSI = "dsi@ff450000"
CATALOG = "/boot/dtb"
DEVICES_INI = f"{CATALOG}/r36_devices.ini"
HOME = "/home/ark"
RA_DIR = f"{HOME}/.config/retroarch"
BACKLIGHT = "/sys/class/backlight/backlight"
CPUFREQ = "/sys/devices/system/cpu/cpufreq/policy0"


def read(path, default=None):
    try:
        with open(path, "rb") as f:
            return f.read()
    except OSError:
        return default


def read_text(path, default="N/A"):
    data = read(path)
    return data.split(b"\x00")[0].decode(errors="replace").strip() if data else default


def write_text(path, value):
    with open(path, "w") as f:
        f.write(str(value))


def clamp_pct(value):
    return max(0, min(100, int(value)))


# --- Device tree ---

def fdt_props(blob, wanted):
    """Lê um DTB e devolve {caminho_do_nó: {prop: bytes}} para os nós em `wanted`.

    `wanted(path)` decide se as propriedades do nó são guardadas.
    """
    magic, _, off_struct, off_strings = struct.unpack_from(">4I", blob, 0)
    if magic != 0xD00DFEED:
        return {}
    pos, stack, nodes = off_struct, [], {}
    while True:
        (token,) = struct.unpack_from(">I", blob, pos)
        pos += 4
        if token == 1:  # BEGIN_NODE
            end = blob.index(b"\x00", pos)
            stack.append(blob[pos:end].decode(errors="replace"))
            pos = (end + 4) & ~3
        elif token == 2:  # END_NODE
            stack.pop()
        elif token == 3:  # PROP
            length, nameoff = struct.unpack_from(">II", blob, pos)
            pos += 8
            path = "/" + "/".join(stack[1:])
            if wanted(path):
                name_end = blob.index(b"\x00", off_strings + nameoff)
                name = blob[off_strings + nameoff:name_end].decode()
                nodes.setdefault(path, {})[name] = blob[pos:pos + length]
            pos = (pos + length + 3) & ~3
        elif token == 4:  # NOP
            continue
        else:  # END
            return nodes


def is_panel_node(path):
    return path.startswith(f"/{DSI}/panel") and path.count("/") == 2


def panel_signature(model, props):
    return {
        "model": model,
        "compatible": props.get("compatible", b"").split(b"\x00")[0].decode(errors="replace"),
        "hash": hashlib.sha256(props.get("panel-init-sequence", b"")).hexdigest(),
    }


def live_panel():
    model = read_text(f"{DT}/model")
    nodes = sorted(glob.glob(f"{DT}/{DSI}/panel*"))
    if not nodes:
        return None
    props = {name: read(f"{nodes[0]}/{name}", b"") for name in ("compatible", "panel-init-sequence")}
    return panel_signature(model, props)


def catalog_panels():
    variants = {}
    if os.path.exists(DEVICES_INI):
        ini = configparser.ConfigParser(strict=False, interpolation=None)
        ini.read(DEVICES_INI, encoding="utf-8")
        variants = {s: ini[s].get("variant", "unknown") for s in ini.sections()}

    for dtb in sorted(glob.glob(f"{CATALOG}/*/*/rk3326-*-linux.dtb")):
        nodes = fdt_props(read(dtb, b""), lambda p: p == "/" or is_panel_node(p))
        panels = [p for p in sorted(nodes) if p != "/"]
        if not panels:
            continue
        model = nodes.get("/", {}).get("model", b"").split(b"\x00")[0].decode(errors="replace")
        entry = panel_signature(model, nodes[panels[0]])
        entry["folder"] = os.path.relpath(os.path.dirname(dtb), CATALOG)
        entry["variant"] = variants.get(os.path.basename(entry["folder"]), entry["folder"].split("/")[0])
        yield entry


def detect_hardware_and_screen(_args=None):
    live = live_panel()
    if not live:
        return f"Aparelho: {read_text(DT + '/model')}\nPainel: nó não encontrado no device tree."

    lines = [
        f"Aparelho: {live['model']}",
        f"Controlador: {live['compatible']}",
        f"Assinatura da tela: {live['hash'][:16]}",
        "",
    ]
    if not os.path.isdir(CATALOG):
        lines.append("Catálogo de DTBs não encontrado (/boot/dtb).")
        return "\n".join(lines)

    entries = list(catalog_panels())
    same_screen = [e for e in entries if e["hash"] == live["hash"]]
    exact = [e for e in same_screen if e["model"] == live["model"]]
    # Os DTBs do catálogo costumam ter um sufixo no modelo ("R36S-V21 2024-12-18 2550")
    prefix = [e for e in same_screen if e["model"].startswith(live["model"] + " ")]
    same = [e for e in same_screen if e not in exact and e not in prefix]

    if exact:
        lines.append("No SELECT MODEL, use uma destas pastas:")
        lines += [f"  {e['folder']}" for e in exact]
    elif prefix:
        lines.append("No SELECT MODEL, qualquer uma destas pastas serve")
        lines.append("(mesmo modelo e mesma tela):")
        lines += [f"  {e['folder']}" for e in prefix]
    elif same:
        lines.append("Modelo não listado, mas a tela é igual à de:")
        lines += [f"  {e['folder']}" for e in same]
    else:
        lines.append("DTB personalizado: faça backup de /boot antes de atualizar.")

    if any(e["variant"] in ("clone", "soysauce") for e in exact or prefix or same):
        lines += ["", "Atenção: clones/soysauce são marcados como NÃO SUPORTADOS pelo dArkOS."]
    lines += ["", "Antes de trocar o DTB, copie a partição BOOT inteira para o PC."]
    return "\n".join(lines)


# --- Cartões SD ---

SD_VENDORS = {0x03: "SanDisk"}


def mmc_mounts():
    mounts = {}
    with open("/proc/mounts") as f:
        for line in f:
            dev, mnt = line.split()[:2]
            if dev.startswith("/dev/mmcblk"):
                blk = dev[5:].split("p")[0]
                mounts.setdefault(blk, []).append(mnt.replace("\\040", " "))
    return mounts


def check_microsd_info(_args=None):
    mounts = mmc_mounts()
    lines = []
    for dev in sorted(glob.glob("/sys/block/mmcblk*/device")):
        blk = dev.split("/")[3]
        manfid = int(read_text(f"{dev}/manfid", "0"), 16)
        sectors = int(read_text(f"/sys/block/{blk}/size", "0"))
        lines += [
            f"{blk}:",
            f"  Fabricante: {SD_VENDORS.get(manfid, f'não identificado (0x{manfid:02x})')}",
            f"  Nome: {read_text(dev + '/name')}  Fabricado: {read_text(dev + '/date')}",
            f"  Tamanho: {sectors * 512 / 1e9:.1f} GB",
            f"  Montado em: {', '.join(mounts.get(blk, ['-']))}",
        ]
    return "\n".join(lines) or "Nenhum cartão encontrado."


def test_microsd_speed(args):
    """Grava e lê 64 MB no ponto de montagem informado (nunca em /tmp, que é RAM)."""
    target = args.get("path", "/roms")
    if not any(target in m for m in mmc_mounts().values()):
        return f"{target} não é uma partição de cartão SD."
    test_file = os.path.join(target, ".sab_speedtest.bin")
    size_mb = 64
    block = os.urandom(1024 * 1024)
    try:
        start = time.monotonic()
        with open(test_file, "wb") as f:
            for _ in range(size_mb):
                f.write(block)
            f.flush()
            os.fsync(f.fileno())
        write_s = time.monotonic() - start

        write_text("/proc/sys/vm/drop_caches", 3)
        start = time.monotonic()
        with open(test_file, "rb") as f:
            while f.read(1024 * 1024):
                pass
        read_s = time.monotonic() - start
    except OSError as e:
        return f"Falha no teste: {e}"
    finally:
        if os.path.exists(test_file):
            os.remove(test_file)

    write_mbs, read_mbs = size_mb / write_s, size_mb / read_s
    verdict = "OK" if write_mbs >= 10 else "lento: jogos podem travar ao carregar"
    return (
        f"Cartão em {target} ({size_mb} MB):\n"
        f"  Escrita: {write_mbs:.1f} MB/s\n"
        f"  Leitura: {read_mbs:.1f} MB/s\n"
        f"  Avaliação: {verdict}"
    )


# --- Sistema ---

def get_system_status(_args=None):
    temp = read_text("/sys/class/thermal/thermal_zone0/temp", "")
    temp_c = f"{int(temp) // 1000}°C" if temp.isdigit() else "N/A"
    bright = int(read_text(f"{BACKLIGHT}/brightness", "0"))
    maxb = int(read_text(f"{BACKLIGHT}/max_brightness", "1")) or 1
    freq = read_text(f"{CPUFREQ}/scaling_cur_freq", "0")
    return (
        f"Bateria: {read_text('/sys/class/power_supply/battery/capacity')}% "
        f"({read_text('/sys/class/power_supply/battery/status')})\n"
        f"Temperatura CPU: {temp_c}\n"
        f"CPU: {int(freq) // 1000} MHz, governador {read_text(CPUFREQ + '/scaling_governor')}\n"
        f"Brilho: {round(bright * 100 / maxb)}%\n"
        f"Volume: {get_volume()}%"
    )


def get_brightness(_args=None):
    maxb = int(read_text(f"{BACKLIGHT}/max_brightness", "1")) or 1
    return round(int(read_text(f"{BACKLIGHT}/brightness", "0")) * 100 / maxb)


def set_screen_brightness(args):
    pct = clamp_pct(args["value"])
    maxb = int(read_text(f"{BACKLIGHT}/max_brightness", "160"))
    write_text(f"{BACKLIGHT}/brightness", max(1, round(pct / 100 * maxb)))
    return f"Brilho: {pct}%"


def amixer(*args):
    return subprocess.run(["amixer", "-c", "0", *args], capture_output=True, text=True).stdout


def get_volume(_args=None):
    for line in amixer("sget", "Playback").splitlines():
        if "[" in line and "%]" in line:
            return int(line.split("[")[1].split("%")[0])
    return 0


def set_system_volume(args):
    pct = clamp_pct(args["value"])
    amixer("-q", "sset", "Playback", f"{pct}%")
    return f"Volume: {pct}%"


def get_cpu_governors(_args=None):
    return read_text(f"{CPUFREQ}/scaling_available_governors", "").split()


# O ES põe a CPU em "performance" (perfmax) ao abrir qualquer port, a Sab
# inclusive, e o perfnorm volta o modo quando o port fecha. O dArkOSen guarda
# o modo e o limite de frequência em /etc/cpu-settings.conf (o CPU Manager e o
# R36 Tuner usam o mesmo arquivo; o cpu-governor.service o aplica no boot).
# A Sab grava ali também e faz o perfnorm ler dali: um lugar só para tudo.
CPU_CONF = "/etc/cpu-settings.conf"
GPU_CONF = "/etc/gpu-settings.conf"
DMC_CONF = "/etc/dmc-settings.conf"
GOV_PREF = f"{HOME}/.config/sab/governor"   # versões até 1.5.0 (migrado)
PERFNORM = "/usr/local/bin/perfnorm"
PERFNORM_ORIG = "echo ondemand > /sys/devices/system/cpu/cpufreq/policy0/scaling_governor"
PERFNORM_OLD = ('echo "$(cat /home/ark/.config/sab/governor 2>/dev/null || echo ondemand)" '
                "> /sys/devices/system/cpu/cpufreq/policy0/scaling_governor  # Sab")
PERFNORM_SAB = ('echo "$(. /etc/cpu-settings.conf 2>/dev/null; echo ${GOV:-ondemand})" '
                "> /sys/devices/system/cpu/cpufreq/policy0/scaling_governor  # Sab")
GPU_DEV = "/sys/class/devfreq/ff400000.gpu"
CPU_SAFE_MHZ = 1296      # padrão do dArkOSen; acima disso é overclock
OC_MAX_TEMP = 70         # °C: não libera overclock acima disso (1º ponto de corte do kernel)


def read_conf(path):
    out = {}
    for line in read_text(path, "").splitlines():
        k, sep, v = line.strip().partition("=")
        if sep and k and not k.startswith("#"):
            out[k.strip()] = v.strip().strip('"')
    return out


def write_conf(path, **values):
    """Troca só as chaves pedidas, mantendo as outras linhas do arquivo."""
    lines, seen = [], set()
    for line in read_text(path, "").splitlines():
        k = line.split("=", 1)[0].strip()
        if k in values:
            lines.append(f"{k}={values[k]}")
            seen.add(k)
        elif line.strip():
            lines.append(line)
    lines += [f"{k}={v}" for k, v in values.items() if k not in seen]
    write_text(path, "\n".join(lines) + "\n")


def temp_c():
    t = read_text("/sys/class/thermal/thermal_zone0/temp", "0")
    return int(t) // 1000 if t.isdigit() else 0


def get_preferred_governor(_args=None):
    gov = read_conf(CPU_CONF).get("GOV")
    if not gov and os.path.exists(GOV_PREF):
        gov = read_text(GOV_PREF)
    return gov or "ondemand"


def patch_perfnorm():
    """Faz o perfnorm ler o modo de /etc/cpu-settings.conf (backup em perfnorm.sab-bak)."""
    text = (read(PERFNORM) or b"").decode()
    if PERFNORM_SAB in text:
        return True
    old = PERFNORM_OLD if PERFNORM_OLD in text else PERFNORM_ORIG if PERFNORM_ORIG in text else None
    if not old:
        return False
    if not os.path.exists(PERFNORM + ".sab-bak"):
        shutil.copy2(PERFNORM, PERFNORM + ".sab-bak")
    write_text(PERFNORM, text.replace(old, PERFNORM_SAB, 1))
    return True


def migrate_cpu_settings():
    """Versões antigas da Sab guardavam o modo em ~/.config/sab/governor."""
    if os.path.exists(GOV_PREF):
        if "GOV" not in read_conf(CPU_CONF):
            write_conf(CPU_CONF, GOV=read_text(GOV_PREF))
        os.remove(GOV_PREF)
    if PERFNORM_OLD in (read(PERFNORM) or b"").decode():
        patch_perfnorm()


def set_preferred_governor(args):
    name = args["governor"]
    if name not in get_cpu_governors():
        return f"Governador indisponível. Opções: {', '.join(get_cpu_governors())}"
    write_conf(CPU_CONF, GOV=name)
    if not patch_perfnorm():
        return f"Modo {name} salvo para o boot, mas o perfnorm deste sistema é diferente."
    return f"Processador: {name} ao voltar para o menu"


# --- Overclock (CPU e GPU) ---

def cpu_freqs(_args=None):
    top = int(read_text(f"{CPUFREQ}/cpuinfo_max_freq", "0")) // 1000
    avail = [int(f) // 1000 for f in read_text(f"{CPUFREQ}/scaling_available_frequencies", "").split()]
    return [f for f in sorted(set(avail)) if CPU_SAFE_MHZ <= f <= top] or [CPU_SAFE_MHZ]


def get_cpu_max(_args=None):
    return int(read_text(f"{CPUFREQ}/scaling_max_freq", "0")) // 1000


def set_cpu_max(args):
    mhz = int(args["mhz"])
    if mhz not in cpu_freqs():
        return f"Frequência indisponível: {mhz} MHz."
    if mhz > CPU_SAFE_MHZ and temp_c() >= OC_MAX_TEMP:
        return f"Está quente ({temp_c()} °C): o overclock só é liberado abaixo de {OC_MAX_TEMP} °C."
    write_conf(CPU_CONF, FREQ=mhz * 1000)
    write_text(f"{CPUFREQ}/scaling_max_freq", mhz * 1000)
    return f"Processador até {mhz} MHz" + (" (overclock)" if mhz > CPU_SAFE_MHZ else "")


def gpu_freqs(_args=None):
    return sorted(int(f) // 1000000 for f in read_text(f"{GPU_DEV}/available_frequencies", "").split())


def get_gpu_max(_args=None):
    return int(read_text(f"{GPU_DEV}/max_freq", "0")) // 1000000


def set_gpu_max(args):
    mhz = int(args["mhz"])
    if mhz not in gpu_freqs():
        return f"Frequência indisponível: {mhz} MHz."
    if mhz > 520 and temp_c() >= OC_MAX_TEMP:
        return f"Está quente ({temp_c()} °C): o overclock só é liberado abaixo de {OC_MAX_TEMP} °C."
    write_conf(GPU_CONF, FREQ=mhz * 1000000)
    write_text(f"{GPU_DEV}/max_freq", mhz * 1000000)
    return f"GPU até {mhz} MHz" + (" (overclock)" if mhz > 520 else "")


def zram_facts(_args=None):
    size = read_text("/sys/block/zram0/disksize", "0")
    stat = read_text("/sys/block/zram0/mm_stat", "").split()
    return {"zram_mb": int(size) // 1048576 if size.isdigit() else 0,
            "zram_usado_mb": int(stat[0]) // 1048576 if stat else 0}


# --- Serviços do sistema ---

# Falhas conhecidas: o que significam e se a Sab sabe consertar.
KNOWN_FAILS = {
    "dmc-governor.service": ("O ajuste de frequência da RAM falha no boot (configuração vazia).", "fix_dmc"),
    "systemd-remount-fs.service": ("Falha conhecida e inofensiva do dArkOSen: o sistema já monta o "
                                   "cartão certo no boot.", None),
}


def failed_services(_args=None):
    r = subprocess.run(["systemctl", "--failed", "--no-legend", "--plain"], capture_output=True, text=True)
    return [line.split()[0] for line in r.stdout.splitlines() if line.strip()]


def fix_dmc(_args=None):
    freqs = sorted(int(f) for f in read_text("/sys/class/devfreq/dmc/available_frequencies", "").split())
    if not freqs:
        return "Este aparelho não expõe a frequência da RAM."
    write_conf(DMC_CONF, FREQ=freqs[-1])
    subprocess.run(["systemctl", "reset-failed", "dmc-governor.service"], capture_output=True)
    r = subprocess.run(["systemctl", "restart", "dmc-governor.service"], capture_output=True, text=True)
    if r.returncode:
        return "Não consegui consertar: " + (r.stderr.strip() or "o serviço falhou de novo.")
    return f"RAM: frequência máxima {freqs[-1] // 1000000} MHz, serviço consertado"


# --- Espaço e limpeza ---

def disk_facts(_args=None):
    out = {}
    for name, path in (("sistema", "/"), ("roms", "/roms"), ("jogos", "/roms2")):
        if path != "/" and not os.path.ismount(path):
            continue
        u = shutil.disk_usage(path)
        out[name] = {"livre_gb": round(u.free / 1e9, 1), "uso_pct": round(100 * u.used / u.total)}
    return out


MAC_JUNK = (".DS_Store", ".Trashes", ".Spotlight-V100", ".fseventsd")


def mac_junk(roots=("/roms", "/roms2")):
    """Arquivos que o macOS cria ao copiar: ._nome (resource forks) e pastas de índice.
    O find é bem mais rápido que os.walk nos cartões cheios do R36S."""
    roots = [r for r in roots if os.path.ismount(r)]
    if not roots:
        return []
    names = []
    for n in MAC_JUNK:
        names += ["-name", n, "-o"]
    r = subprocess.run(["find", *roots, "(", *names, "-name", "._*", ")", "-prune", "-print"],
                       capture_output=True, text=True)
    return [p for p in r.stdout.splitlines() if p]


def clean_mac_junk(_args=None):
    junk = mac_junk()
    for path in junk:
        if os.path.isdir(path):
            shutil.rmtree(path, ignore_errors=True)
        else:
            try:
                os.remove(path)
            except OSError:
                pass
    os.sync()
    return f"{len(junk)} arquivo(s) do Mac removido(s)" if junk else "Nenhum lixo do Mac encontrado"


# --- Verificação de cartão (roda no boot, com o cartão desmontado) ---

# O dArkOSen roda /boot/recovery.sh no boot (recovery-check.service) e os scripts
# de scan se apagam ao terminar. Os logs ficam em /boot.
SCANS = {"roms2": ("/usr/local/bin/Scan_SD2.sh", "/boot/sd2_scan.log", "SD2 scan result:"),
         "roms": ("/usr/local/bin/Scan_SD1p3.sh", "/boot/sd1p3_scan.log", "SD1p3 scan result:")}


def schedule_scan(args):
    src, _log, _ = SCANS[args.get("part", "roms2")]
    if not os.path.exists(src):
        return "Este sistema não tem o verificador de cartão do dArkOSen."
    shutil.copy(src, "/boot/recovery.sh")
    os.chmod("/boot/recovery.sh", 0o755)
    os.sync()
    subprocess.Popen(["sh", "-c", "sleep 2; reboot"])
    return "Reiniciando para verificar o cartão..."


def last_scan(_args=None):
    out = {}
    for part, (_src, log, marker) in SCANS.items():
        text = read_text(log, "")
        res = next((ln.split(":", 1)[1].strip() for ln in text.splitlines() if ln.startswith(marker)), None)
        if res:
            out[part] = {"resultado": res, "quando": time.strftime("%d/%m/%Y", time.localtime(os.path.getmtime(log)))}
    return out


# --- Tela: gamma e LED ---

GAMMA_CONF = "/etc/gamma-settings.conf"


def get_gamma(_args=None):
    cur = read_text("/dev/shm/CURRENT_GAMMA", "") or read_conf(GAMMA_CONF).get("GAMMA", "1.0")
    try:
        return round(float(cur), 1)
    except ValueError:
        return 1.0


def set_gamma(args):
    g = round(min(1.8, max(0.5, float(args["value"]))), 1)
    tone = read_text("/dev/shm/CURRENT_TONE", "") or read_conf(GAMMA_CONF).get("TONE", "")
    cmd = ["/usr/local/bin/gamma", "-s", str(g)] + (["-t", tone] if tone else [])
    subprocess.run(cmd, capture_output=True)
    write_conf(GAMMA_CONF, GAMMA=g)         # o gamma-persist.service aplica no boot
    write_text("/dev/shm/CURRENT_GAMMA", g)  # e as teclas de atalho continuam daqui
    os.chmod("/dev/shm/CURRENT_GAMMA", 0o666)
    return f"Gamma {g}"


LED_GPIO = "/sys/class/gpio/gpio77/value"
LED_FIX = "/usr/local/bin/fix_power_led"


def get_led(_args=None):
    return "vermelho" if read(LED_FIX) == read(LED_FIX + ".red") else "verde"


def set_led(args):
    """Igual aos scripts Change LED to Red/Green do dArkOSen, sem reiniciar o ES."""
    color = args["color"]
    suf = {"vermelho": "red", "verde": "green"}[color]
    if not os.path.exists(f"{LED_FIX}.{suf}"):
        return "Este sistema não tem a troca de cor do LED."
    if not os.path.exists("/sys/class/gpio/gpio77"):
        write_text("/sys/class/gpio/export", "77")
        write_text("/sys/class/gpio/gpio77/direction", "out")
    write_text(LED_GPIO, "1" if suf == "red" else "0")
    shutil.copy(f"{LED_FIX}.{suf}", LED_FIX)                       # cor no boot
    warn = "/usr/local/bin/batt_life_warning.py"
    if os.path.exists(f"{warn}.{suf}"):
        shutil.copy(f"{warn}.{suf}", warn)                         # pisca com bateria baixa
        subprocess.run(["systemctl", "restart", "batt_led"], capture_output=True)
    return f"LED {color}"


# --- Conflitos com outros scripts ---

def usb_net_active(_args=None):
    """O 'USB Network Mode.sh' (de terceiros) usa a mesma porta OTG que o pendrive."""
    mods = read_text("/proc/modules", "")
    return any(m in mods.split() for m in ("g_ether", "g_cdc", "g_multi")) or os.path.exists("/sys/class/net/usb0")


# --- Ferramentas de tela cheia do dArkOSen ---

# Elas desenham no terminal e não podem rodar com a Sab na tela: a Sab fecha,
# o Sab.sh roda a ferramenta e o ES volta para Ports quando ela termina.
HANDOFF = "/tmp/sab-next"
SYSTOOLS = {
    "calibrar_bateria": "/opt/system/System/R36S Battery Calibration Tool v1.3.sh",
    "backup": "/opt/system/System/R36 Backup and Migration Assistant.sh",
    "backup_config": "/opt/system/Advanced/Backup dArkOS Settings.sh",
}


def systool_available(name):
    return os.path.exists(SYSTOOLS.get(name, ""))


def handoff(args):
    path = SYSTOOLS[args["tool"]]
    if not os.path.exists(path):
        return "Ferramenta não encontrada neste sistema."
    write_text(HANDOFF, path)
    return "ok"


def set_cpu_governor(args):
    name = args["governor"]
    if name not in get_cpu_governors():
        return f"Governador indisponível. Opções: {', '.join(get_cpu_governors())}"
    write_text(f"{CPUFREQ}/scaling_governor", name)
    return f"Governador: {name}"


# --- Restaurações ---

def device_alsa_path():
    if os.path.exists(DEVICES_INI):
        ini = configparser.ConfigParser(strict=False, interpolation=None)
        ini.read(DEVICES_INI, encoding="utf-8")
        hardware = read_text(f"{DT}/model")
        if ini.has_section(hardware):
            return ini[hardware].get("alsa_path", "SPK_HP")
    return "SPK_HP"


def restore_audio(_args=None):
    """Repete o que o dArkOS faz: perfnorm (.asoundrc), fixvolume.sh (rota) e boot_volume.sh (40%)."""
    lines = []
    backup = f"{HOME}/.asoundrcbak"
    if os.path.exists(backup):
        shutil.copy(backup, f"{HOME}/.asoundrc")
        os.chown(f"{HOME}/.asoundrc", 1000, 1000)
        lines.append(".asoundrc restaurado do backup do sistema")
    route = device_alsa_path()
    amixer("-q", "cset", "name=Playback Path", route)
    amixer("-q", "sset", "Playback", "40%")
    lines += [f"Saída de áudio: {route}", "Volume: 40%"]
    return "\n".join(lines)


RA_FILES = ("retroarch.cfg", "retroarch-core-options.cfg")


def retroarch_changes(_args=None):
    lines = []
    for name in RA_FILES:
        cur, bak = f"{RA_DIR}/{name}", f"{RA_DIR}/{name}.bak"
        if not (os.path.exists(cur) and os.path.exists(bak)):
            lines.append(f"{name}: sem cópia de fábrica")
            continue
        with open(cur, errors="replace") as a, open(bak, errors="replace") as b:
            changed = len(set(a.read().splitlines()) ^ set(b.read().splitlines()))
        lines.append(f"{name}: {changed} linha(s) diferentes da cópia de fábrica")
    return "\n".join(lines)


def restore_retroarch(_args=None):
    stamp = time.strftime("%Y%m%d-%H%M%S")
    lines = []
    for name in RA_FILES:
        cur, bak = f"{RA_DIR}/{name}", f"{RA_DIR}/{name}.bak"
        if not os.path.exists(bak):
            continue
        if os.path.exists(cur):
            shutil.copy2(cur, f"{cur}.sab-{stamp}")
        shutil.copy(bak, cur)
        os.chown(cur, 1000, 1000)
        lines.append(f"{name} restaurado (anterior salvo como {name}.sab-{stamp})")
    return "\n".join(lines) or "Nenhuma cópia de fábrica encontrada."


# --- Pendrive USB (porta OTG) ---
# O trabalho fica em usb_pendrive.sh, instalado em /home/ark/usb-disco.sh: o
# serviço de boot roda de lá porque /roms2 é desmontada enquanto o PC a usa.

USB_SRC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "usb_pendrive.sh")
USB_BIN = f"{HOME}/usb-disco.sh"


def usb_install():
    if read(USB_SRC) != read(USB_BIN):
        shutil.copy(USB_SRC, USB_BIN)
        os.chmod(USB_BIN, 0o755)
        os.chown(USB_BIN, 1000, 1000)


def usb_run(*args):
    usb_install()
    r = subprocess.run([USB_BIN, *args], capture_output=True, text=True)
    return (r.stdout + r.stderr).strip()


def usb_facts(_args=None):
    part = usb_run("part") or "roms2"
    dtb = subprocess.run(["fdtget", "-t", "s", "/boot/rk3326-r36s-linux.dtb", "/usb@ff300000", "dr_mode"],
                         capture_output=True, text=True).stdout.strip()
    free = {}
    for p in ("roms", "roms2"):
        if os.path.ismount(f"/{p}"):
            st = os.statvfs(f"/{p}")
            free[p] = round(st.f_bavail * st.f_frsize / 1e9, 1)
    return {
        "modo_pendrive_ligado": dtb == "peripheral",
        "particao_para_o_pc": part,
        "livre_gb": free,
        "wifi_usb_conectado": os.path.exists("/sys/class/net/wlan0"),
    }


def usb_status(_args=None):
    return usb_run("status")


def usb_set_partition(args):
    return usb_run("part", args["part"])


def usb_on(_args=None):
    return usb_run("on")


def usb_off(_args=None):
    return usb_run("off")


def usb_restore(_args=None):
    return usb_run("restore")


# --- Executor (usado pela interface e por sab_checks.py) ---

TOOLS = {
    "detect_hardware_and_screen": detect_hardware_and_screen,
    "check_microsd_info": check_microsd_info,
    "test_microsd_speed": test_microsd_speed,
    "get_system_status": get_system_status,
    "get_brightness": get_brightness,
    "set_screen_brightness": set_screen_brightness,
    "get_volume": get_volume,
    "set_system_volume": set_system_volume,
    "get_cpu_governors": get_cpu_governors,
    "set_cpu_governor": set_cpu_governor,
    "get_preferred_governor": get_preferred_governor,
    "set_preferred_governor": set_preferred_governor,
    "restore_audio": restore_audio,
    "cpu_freqs": cpu_freqs, "get_cpu_max": get_cpu_max, "set_cpu_max": set_cpu_max,
    "gpu_freqs": gpu_freqs, "get_gpu_max": get_gpu_max, "set_gpu_max": set_gpu_max,
    "zram_facts": zram_facts, "failed_services": failed_services, "fix_dmc": fix_dmc,
    "disk_facts": disk_facts, "clean_mac_junk": clean_mac_junk,
    "schedule_scan": schedule_scan, "last_scan": last_scan,
    "get_gamma": get_gamma, "set_gamma": set_gamma, "get_led": get_led, "set_led": set_led,
    "usb_net_active": usb_net_active, "handoff": handoff,
    "retroarch_changes": retroarch_changes,
    "restore_retroarch": restore_retroarch,
    "usb_facts": usb_facts,
    "usb_status": usb_status,
    "usb_set_partition": usb_set_partition,
    "usb_on": usb_on,
    "usb_off": usb_off,
    "usb_restore": usb_restore,
}


def run_tool(call):
    tool = TOOLS.get(call.get("tool"))
    if not tool:
        return "Comando não reconhecido."
    try:
        result = tool(call.get("args", {}))
    except (KeyError, ValueError, OSError) as e:
        return f"Erro: {e}"
    return " ".join(result) if isinstance(result, list) else str(result)


if __name__ == "__main__":
    if len(sys.argv) > 1:
        args = json.loads(sys.argv[2]) if len(sys.argv) > 2 else {}
        print(run_tool({"tool": sys.argv[1], "args": args}))
    else:
        print("\n".join(TOOLS))
