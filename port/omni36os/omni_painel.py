#!/usr/bin/env python3
"""Tela certa no primeiro boot: acha o DTB da tela do console sozinho, com um toque de confirmação.

O kernel do dArkOSen não consegue perguntar à tela qual modelo ela é: com o DTB errado, a imagem
simplesmente não aparece. Então o Omni36OS testa as telas possíveis, uma por boot:

1. O hardware (chip, RAM, memória interna) diz se o console parece original ou clone, e isso
   decide a ordem: as telas da família provável vêm primeiro, a mais comum na frente.
2. A tela de agora mostra "Está vendo esta tela? Aperte qualquer botão" por 10 s, com um ding-dong
   no alto-falante; o LED pisca durante toda a busca (dá para acompanhar com a tela apagada).
3. Apertou: essa é a tela certa (toca um arpejo). O boot segue (e o primeiro boot expande a imagem).
4. Não apertou (tela preta, ninguém vê): instala a próxima tela do catálogo e reinicia.
5. Acabou a lista sem resposta: volta os arquivos originais e segue, como se nada tivesse mudado.

Segurança: o DTB de cada pasta do catálogo descreve um aparelho inteiro (energia, botões, u-boot), e
instalar o de outro aparelho pode impedir o boot (aconteceu: a pasta de um clone trouxe outro
boot.ini e outro DTB do u-boot, e o u-boot parou em "dtb load fail"). Por isso o detector nunca
copia arquivos do catálogo: monta cada teste a partir do DTB original deste console, trocando só as
propriedades da tela (sequência de início, tempos, atrasos, formato DSI). O boot.ini, o DTB do u-boot
e o resto do hardware ficam sempre os originais; o pior caso de uma tela errada é a tela apagada.
O DTB montado é conferido (abre, e a tela dentro dele é a pedida) antes de entrar no lugar do original,
e um limite de reinícios encerra a detecção com os originais se algo sair do esperado.

Roda como serviço (omni36os-painel.service) antes do firstboot e do launcher, só quando:
- /boot/firstboot.sh existe (primeiro boot de uma imagem nova, antes da expansão), ou
- /boot/omni36os-tela/testar existe (refazer a detecção: crie o arquivo pelo PC).
Estado em /boot/omni36os-tela/ (FAT, sobrevive aos reinícios); os arquivos originais ficam em
/boot/omni36os-tela/original/ até o fim.
"""
import glob
import hashlib
import io
import json
import math
import os
import select
import shutil
import struct
import subprocess
import sys
import threading
import time
import wave

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
WAIT = 10                           # segundos esperando um botão em cada tela (a pergunta aparece assim que a tela acende)
try:                                # medições: /boot/omni36os-tela/espera troca o tempo (segundos)
    with open("/boot/omni36os-tela/espera") as _f:
        WAIT = max(5.0, min(30.0, float(_f.read())))
except (OSError, ValueError):
    pass
TIMINGS = PANEL_NODE + "/display-timings"
# propriedades da tela que apontam para outras partes do aparelho (GPIO, regulador, luz de fundo):
# ficam sempre as do DTB original, porque os números (phandles) só valem dentro do próprio DTB
KEEP_PROPS = ("reg", "phandle", "linux,phandle", "backlight", "status", "pinctrl-0", "pinctrl-names")
KEEP_SUFFIX = ("-gpios", "-gpio", "-supply")
TEST_DTB = f"{DIR}/teste.dtb"
EXTRA_BOOTS = 3                     # reinícios a mais que a lista tolera antes de desistir
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


USB_PARAM = "usbcore.old_scheme_first=1"   # adaptadores Wi-Fi Realtek só sobem no boot com ele


def usb_param(path):
    """Põe o esquema antigo de USB na linha do kernel do boot.ini (o do catálogo não tem)."""
    try:
        with open(path) as f:
            text = f.read()
    except OSError:
        return
    if USB_PARAM in text or "rootwait rw " not in text:
        return
    with open(path + ".tmp", "w") as f:
        f.write(text.replace("rootwait rw ", f"rootwait rw {USB_PARAM} ", 1))
    os.replace(path + ".tmp", path)


def _props(dtb, node):
    return sh("fdtget", "-p", dtb, node).split()


def _get(dtb, node, prop):
    return sh("fdtget", "-t", "bx", dtb, node, prop).split()


def _put(dtb, node, prop, raw):
    """Grava os bytes crus de uma propriedade (propriedade vazia = verdadeira/sem valor)."""
    if raw:
        rc = subprocess.run(["fdtput", "-t", "bx", dtb, node, prop, *raw], capture_output=True).returncode
    else:     # fdtput não grava propriedade vazia: cria com um byte e corta (não há tela assim hoje)
        return False
    return rc == 0


def _ok(cmd):
    return subprocess.run(cmd, capture_output=True).returncode == 0


def _copyable(prop):
    return prop not in KEEP_PROPS and not prop.endswith(KEEP_SUFFIX)


def build_test(base, cand, out):
    """Monta em `out` o DTB original (`base`) com a tela do DTB do catálogo (`cand`). True se deu certo."""
    shutil.copy2(base, out)
    if not _props(out, PANEL_NODE) or not _props(cand, PANEL_NODE):
        return False
    # 1. propriedades do painel: tira as copiáveis do original e põe as do catálogo
    for prop in _props(out, PANEL_NODE):
        if _copyable(prop):
            _ok(["fdtput", "-d", out, PANEL_NODE, prop])
    for prop in _props(cand, PANEL_NODE):
        if _copyable(prop) and not _put(out, PANEL_NODE, prop, _get(cand, PANEL_NODE, prop)):
            return False
    # 2. modos de vídeo: os do catálogo no lugar dos originais; o modo nativo herda o phandle do
    # nativo original, assim o native-mode (que aponta para ele) continua valendo
    native = _get(out, TIMINGS, "native-mode")
    cand_native = _get(cand, TIMINGS, "native-mode")
    for child in sh("fdtget", "-l", out, TIMINGS).split():
        if not _ok(["fdtput", "-r", out, f"{TIMINGS}/{child}"]):
            return False
    for child in sh("fdtget", "-l", cand, TIMINGS).split():
        src, dst = f"{TIMINGS}/{child}", f"{TIMINGS}/{child}"
        if not _ok(["fdtput", "-c", out, dst]):
            return False
        for prop in _props(cand, src):
            if prop in ("phandle", "linux,phandle"):
                continue
            if not _put(out, dst, prop, _get(cand, src, prop)):
                return False
        if native and cand_native and _get(cand, src, "phandle") == cand_native:
            if not _put(out, dst, "phandle", native):
                return False
    # 3. conferência: o DTB abre e a tela dentro dele é a pedida
    if not _ok(["fdtdump", out]):
        return False
    got, want = panel_info(out), panel_info(cand)
    return bool(got and want and got == want)


def base_dtb():
    """O DTB do kernel original deste console (o que estava instalado antes da detecção)."""
    return kernel_dtb(ORIG)


def install(folder):
    """Põe no lugar do DTB do kernel o original com a tela da pasta. False se não deu para montar."""
    base = base_dtb()
    cand = kernel_dtb(folder)
    if not base or not cand or not build_test(base, cand, TEST_DTB):
        return False
    target = f"{BOOT}/{os.path.basename(base)}"
    shutil.copy2(TEST_DTB, target + ".tmp")
    os.replace(target + ".tmp", target)
    os.remove(TEST_DTB)
    os.sync()
    return True


def restore_original():
    for f in glob.glob(f"{BOOT}/*.dtb"):
        os.remove(f)
    for f in glob.glob(f"{ORIG}/*"):
        shutil.copy2(f, BOOT)
    os.sync()


# --- LED: pisca (vermelho/verde) enquanto procura a tela, para quem está com a tela apagada ---

LED = "/sys/class/gpio/gpio77"
LED_FIX = "/usr/local/bin/fix_power_led"     # a cor escolhida em Tela e som (vermelho ou verde)


class Blink:
    def __init__(self):
        self.stop = threading.Event()
        self.thread = None

    def start(self):
        try:
            if not os.path.exists(LED):
                with open("/sys/class/gpio/export", "w") as f:
                    f.write("77")
            with open(f"{LED}/direction", "w") as f:
                f.write("out")
        except OSError:
            return                       # sem o LED neste aparelho: segue sem piscar
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

    def _run(self):
        on = False
        while not self.stop.wait(0.4):
            on = not on
            try:
                with open(f"{LED}/value", "w") as f:
                    f.write("1" if on else "0")
            except OSError:
                return

    def done(self):
        """Para de piscar e volta a cor escolhida."""
        self.stop.set()
        if self.thread:
            self.thread.join(1)
        if os.path.exists(LED_FIX):
            subprocess.run(["bash", LED_FIX], capture_output=True)


# --- som: um "ding" suave na pergunta e um acorde curto na confirmação, sempre no alto-falante ---

PATH_CTL = "Playback Path"          # rk817: OFF, SPK, HP, SPK_HP (na instalação ninguém usa fone)
RATE = 44100


def tone(notes, dur=0.18, vol=0.35):
    """WAV em memória: as notas uma depois da outra, cada uma com subida e descida suaves."""
    # silêncio na frente: o amplificador do alto-falante do rk817 leva uns 300 ms para ligar e
    # engoliria um som curto inteiro (só se ouviria o chiado dele ligando)
    frames = bytearray(int(RATE * 0.5) * 4)
    n = int(RATE * dur)
    for hz in notes:
        for i in range(n):
            env = min(1.0, i / (RATE * 0.01)) * (1 - i / n) ** 2      # ataque de 10 ms, cauda macia
            v = int(32767 * vol * env * math.sin(2 * math.pi * hz * i / RATE))
            frames += struct.pack("<hh", v, v)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes(bytes(frames))
    return buf.getvalue()


VOL_CTL = "Playback Volume"         # o volume salvo só volta mais tarde no boot: o bip usa o próprio
BEEP_VOL = "180,180"                # de 0 a 237 (o volume do sistema fica de fora)


def _enum(ctl):
    out = sh("amixer", "sget", ctl)
    return next((ln.split("'")[1] for ln in out.splitlines() if "Item0:" in ln), "")


DING_DONG = [659, 523]              # Mi, Dó: campainha ("olhe aqui")
ARPEJO = [660, 880, 1320]           # Mi, Lá, Mi: subindo ("deu certo")


def beep(notes, wait=False, dur=0.18):
    """Toca no alto-falante e devolve caminho e volume como estavam. Sem som pronto: segue calado."""
    def play():
        try:
            end = time.monotonic() + 6       # a placa de som aparece alguns segundos depois do detector
            while "rk817" not in open("/proc/asound/cards").read() and time.monotonic() < end:
                time.sleep(0.2)
            prev_path = _enum(PATH_CTL)
            prev_vol = sh("amixer", "cget", f"name={VOL_CTL}").rsplit("values=", 1)[-1].strip()
            subprocess.run(["amixer", "-q", "sset", PATH_CTL, "SPK"], capture_output=True, timeout=3)
            subprocess.run(["amixer", "-q", "cset", f"name={VOL_CTL}", BEEP_VOL], capture_output=True, timeout=3)
            rc = subprocess.run(["aplay", "-q", "-D", "plughw:0,0", "-"], input=tone(notes, dur),
                                capture_output=True, timeout=5)
            if prev_vol.replace(",", "").isdigit():
                subprocess.run(["amixer", "-q", "cset", f"name={VOL_CTL}", prev_vol], capture_output=True, timeout=3)
            if prev_path and prev_path != "SPK":
                subprocess.run(["amixer", "-q", "sset", PATH_CTL, prev_path], capture_output=True, timeout=3)
            if rc.returncode:
                log("bip sem som: " + rc.stderr.decode(errors="replace").strip()[-120:])
        except (OSError, subprocess.SubprocessError) as e:
            log(f"bip sem som: {e}")
    t = threading.Thread(target=play, daemon=True)
    t.start()
    if wait:
        t.join(8)


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
    st["boots"] = st.get("boots", 0) + 1
    save_state(st)
    if st["boots"] > len(st["lista"]) + EXTRA_BOOTS:      # algo saiu do esperado: nunca fica em laço
        log("reinícios demais: volta a tela original")
        restore_original()
        finish(st, False)
        subprocess.run(["reboot"])
        return 0
    blink = Blink()
    blink.start()
    try:
        return run(st)
    finally:
        blink.done()


def run(st):
    cur = st["lista"][st["i"]]
    log(f"testando {st['i'] + 1}/{len(st['lista'])}: {cur['pasta']}")
    drain_keys()
    show_prompt()
    beep(DING_DONG, dur=0.4)        # chama a atenção para a pergunta (toca mesmo com a tela apagada)
    if wait_any_key(WAIT):
        beep(ARPEJO, wait=True)     # confirmado
        base = base_dtb()
        if base and panel_info(base) == panel_info(f"{BOOT}/{os.path.basename(base)}"):
            restore_original()      # é a tela do DTB original: volta o arquivo original, byte a byte
        finish(st, True)
        subprocess.run(["/usr/local/bin/omni36os-tela", "carregando"], capture_output=True)
        return 0
    while True:
        st["i"] += 1
        if st["i"] >= len(st["lista"]):
            st["i"] -= 1
            restore_original()
            finish(st, False)
            subprocess.run(["reboot"])      # volta a tela original para o resto do boot
            return 0
        save_state(st)
        if install(st["lista"][st["i"]]["pasta"]):
            break
        log(f"pulando {st['i'] + 1}: não deu para montar a tela dela no DTB original")
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
