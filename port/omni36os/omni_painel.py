#!/usr/bin/env python3
"""Tela certa no primeiro boot: acha o DTB da tela do console sozinho, com um toque de confirmação.

O kernel do dArkOSen não consegue perguntar à tela qual modelo ela é: com o DTB errado, a imagem
simplesmente não aparece. Então o Omni36OS testa as telas possíveis, uma por boot:

1. O hardware (chip, RAM, memória interna) diz se o console parece original ou clone, e isso
   decide a ordem: as telas da família provável vêm primeiro, a mais comum na frente.
2. A tela de agora mostra "Está vendo esta tela? Aperte qualquer botão" por 20 s.
3. Apertou: essa é a tela certa. O boot segue (e o primeiro boot expande a imagem).
4. Não apertou (tela preta, ninguém vê): instala a próxima tela do catálogo e reinicia.
5. Acabou a lista sem resposta: volta os arquivos originais e segue, como se nada tivesse mudado.

Roda como serviço (omni36os-painel.service) antes do firstboot e do launcher, só quando:
- /boot/firstboot.sh existe (primeiro boot de uma imagem nova, antes da expansão), ou
- /boot/omni36os-tela/testar existe (refazer a detecção: crie o arquivo pelo PC).
Estado em /boot/omni36os-tela/ (FAT, sobrevive aos reinícios); os arquivos originais ficam em
/boot/omni36os-tela/original/ até o fim.
"""
import glob
import hashlib
import json
import os
import select
import shutil
import struct
import subprocess
import sys
import time

BOOT = "/boot"
CATALOG = f"{BOOT}/dtb"
DIR = f"{BOOT}/omni36os-tela"
STATE = f"{DIR}/estado.json"
ORIG = f"{DIR}/original"
DONE = f"{DIR}/pronto"
RETRY = f"{DIR}/testar"
LOG = f"{DIR}/log.txt"
PANEL = "/proc/device-tree/dsi@ff450000/panel@0"
PANEL_NODE = "/dsi@ff450000/panel@0"
WAIT = 20                           # segundos esperando um botão em cada tela
EV_KEY = 1
EVENT = struct.Struct("llHHi")      # input_event no aarch64: timeval (2 longs), type, code, value


def log(msg):
    os.makedirs(DIR, exist_ok=True)
    with open(LOG, "a") as f:
        f.write(time.strftime("%d/%m %H:%M:%S ") + msg + "\n")


def sh(*cmd):
    return subprocess.run(cmd, capture_output=True, text=True).stdout


# --- quem é este console ---

def hardware():
    """Família provável pelo hardware: 'r36s' (original) ou 'clone'. Não depende do DTB."""
    with open("/proc/meminfo") as f:
        mem_mb = int(f.readline().split()[1]) // 1024
    emmc = any(os.path.exists(f"/sys/block/{os.path.basename(b)}boot0")
               for b in glob.glob("/sys/block/mmcblk*") if "boot" not in b)
    family = "clone" if emmc or mem_mb < 800 else "r36s"
    return {"familia": family, "ram_mb": mem_mb, "emmc": emmc}


def panel_hash_live():
    try:
        with open(f"{PANEL}/panel-init-sequence", "rb") as f:
            return hashlib.sha256(f.read()).hexdigest()
    except OSError:
        return ""


def panel_info(dtb):
    """(hash da sequência de início da tela, largura, altura) de um DTB do catálogo."""
    seq = sh("fdtget", "-t", "bx", dtb, PANEL_NODE, "panel-init-sequence").split()
    if not seq:
        return None
    h = hashlib.sha256(bytes(int(x, 16) for x in seq)).hexdigest()
    # a resolução está no primeiro modo de display-timings (todos os modos de uma tela têm o mesmo tamanho)
    timings = sh("fdtget", "-l", dtb, PANEL_NODE + "/display-timings").split()
    size = (0, 0)
    if timings:
        node = f"{PANEL_NODE}/display-timings/{timings[0]}"
        try:
            size = (int(sh("fdtget", dtb, node, "hactive")), int(sh("fdtget", dtb, node, "vactive")))
        except ValueError:
            pass
    return h, size


def kernel_dtb(folder):
    """O DTB do kernel na pasta (o nome muda: r36s, r36h, r45h...); o do u-boot fica de fora."""
    dtbs = [f for f in glob.glob(f"{folder}/*.dtb") if "uboot" not in f and "kernel" not in f]
    return dtbs[0] if dtbs else None


def candidates(fam):
    """Uma pasta do catálogo por tela diferente, só telas 640x480 (a do R36S).
    Ordem: a tela de agora primeiro (já está instalada: testa sem reiniciar); depois as da família
    provável, as mais comuns antes; por fim as da outra família."""
    groups = {}
    for folder in sorted(glob.glob(f"{CATALOG}/*/*/")):
        folder = folder.rstrip("/")
        variant = os.path.basename(os.path.dirname(folder))
        dtb = kernel_dtb(folder)
        info = dtb and panel_info(dtb)
        if not info or info[1] != (640, 480):
            continue
        groups.setdefault(info[0], []).append((variant, folder))
    live = panel_hash_live()

    def rank(item):
        h, members = item
        same = [m for m in members if m[0] == fam]
        return (h != live, not same, -len(members))

    out = []
    for h, members in sorted(groups.items(), key=rank):
        # a pasta que representa a tela: da família provável e de um R36S (as HL-R36H/R45H... são
        # outros aparelhos, com outros botões), a de nome mais simples primeiro
        pick = sorted(members, key=lambda m: (m[0] != fam, not os.path.basename(m[1]).startswith("R36S-"),
                                              os.path.basename(kernel_dtb(m[1])) != "rk3326-r36s-linux.dtb",
                                              m[1]))[0]
        out.append({"pasta": pick[1], "tela": h[:12], "iguais": len(members), "atual": h == live})
    return out


# --- arquivos de boot ---

def boot_files():
    return [f for f in glob.glob(f"{BOOT}/*.dtb")] + [f"{BOOT}/boot.ini"]


def save_original():
    if os.path.isdir(ORIG):
        return
    os.makedirs(ORIG)
    for f in boot_files():
        if os.path.isfile(f):
            shutil.copy2(f, ORIG)
    os.sync()


def install(folder):
    """Como o SELECT MODEL do dArkOSen: tira os .dtb da raiz e copia os .dtb e o boot.ini da pasta.
    O logo e a tela de bateria do Omni36OS ficam (não copia as imagens do dArkOSen)."""
    for f in glob.glob(f"{BOOT}/*.dtb"):
        os.remove(f)
    for f in glob.glob(f"{folder}/*.dtb") + glob.glob(f"{folder}/boot.ini"):
        shutil.copy2(f, BOOT)
    os.sync()


def restore_original():
    for f in glob.glob(f"{BOOT}/*.dtb"):
        os.remove(f)
    for f in glob.glob(f"{ORIG}/*"):
        shutil.copy2(f, BOOT)
    os.sync()


# --- tela e botões ---

def show_prompt():
    subprocess.run(["/usr/local/bin/omni36os-tela", "tela-certa"], capture_output=True)


def wait_any_key(secs):
    """True se qualquer botão (controle, power, volume) for apertado dentro de `secs`."""
    fds = []
    for dev in glob.glob("/dev/input/event*"):
        try:
            fds.append(os.open(dev, os.O_RDONLY | os.O_NONBLOCK))
        except OSError:
            pass
    end = time.monotonic() + secs
    try:
        while fds and time.monotonic() < end:
            ready, _, _ = select.select(fds, [], [], max(0.0, end - time.monotonic()))
            for fd in ready:
                try:
                    data = os.read(fd, EVENT.size * 32)
                except OSError:
                    continue
                for i in range(0, len(data) - EVENT.size + 1, EVENT.size):
                    _s, _us, typ, _code, value = EVENT.unpack_from(data, i)
                    if typ == EV_KEY and value == 1:
                        return True
        return False
    finally:
        for fd in fds:
            os.close(fd)


def drain_keys():
    """Esquece o que já estava apertado antes da pergunta (ex.: o power do boot)."""
    wait_any_key(0.05)


# --- o fluxo ---

def load_state():
    try:
        with open(STATE) as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def save_state(st):
    tmp = STATE + ".tmp"
    with open(tmp, "w") as f:
        json.dump(st, f, ensure_ascii=False, indent=1)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, STATE)
    os.sync()


def finish(st, ok):
    st["resultado"] = st["lista"][st["i"]]["pasta"] if ok else "original (nenhuma confirmada)"
    st["fim"] = time.strftime("%d/%m/%Y %H:%M")
    save_state(st)
    with open(DONE, "w") as f:
        f.write(st["resultado"] + "\n")
    for f in (RETRY,):
        if os.path.exists(f):
            os.remove(f)
    os.sync()
    log("fim: " + st["resultado"])


def needed():
    if os.path.exists(RETRY):
        return True
    return os.path.exists(f"{BOOT}/firstboot.sh") and not os.path.exists(DONE)


def main():
    if not needed():
        return 0
    st = load_state()
    if st is None or os.path.exists(RETRY) and st.get("fim"):
        if os.path.exists(DONE):
            os.remove(DONE)
        hw = hardware()
        save_original()
        st = {"hardware": hw, "lista": candidates(hw["familia"]), "i": 0, "inicio": time.strftime("%d/%m/%Y %H:%M")}
        if not st["lista"]:
            log("catálogo sem telas 640x480: nada a testar")
            st["lista"], st["i"] = [{"pasta": "original"}], 0
            finish(st, False)
            return 0
        save_state(st)
        log(f"início: {hw}, {len(st['lista'])} telas a testar")
    cur = st["lista"][st["i"]]
    log(f"testando {st['i'] + 1}/{len(st['lista'])}: {cur['pasta']}")
    drain_keys()
    show_prompt()
    if wait_any_key(WAIT):
        finish(st, True)
        subprocess.run(["/usr/local/bin/omni36os-tela", "carregando"], capture_output=True)
        return 0
    st["i"] += 1
    if st["i"] >= len(st["lista"]):
        st["i"] -= 1
        restore_original()
        finish(st, False)
        subprocess.run(["reboot"])      # volta a tela original para o resto do boot
        return 0
    save_state(st)
    install(st["lista"][st["i"]]["pasta"])
    log("sem resposta: próxima tela, reiniciando")
    subprocess.run(["reboot"])
    return 0


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--listar":     # diagnóstico, não muda nada
        hw = hardware()
        print(json.dumps({"hardware": hw, "tela_agora": panel_hash_live()[:12],
                          "lista": candidates(hw["familia"])}, ensure_ascii=False, indent=1))
        sys.exit(0)
    sys.exit(main())
