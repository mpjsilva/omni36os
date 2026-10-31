"""Atalhos do Omni36OS dentro dos jogos.

Roda como serviço (omni36os-atalho.service) e lê o controle direto do /dev/input,
sem bibliotecas (struct input_event). O que existe, os botões padrão e os nomes ficam em
omni_combos.py; o jogador liga, desliga e troca os botões em Controles > Atalhos
(~/.config/omni36os/atalhos.json). Padrão:

- FN + X: contador de FPS (com temperatura e bateria); de novo, junto a frequência do processador e
  da GPU; de novo, esconde.
- FN + B: liga ou desliga o limite de 30 FPS.
- FN + Y: captura de tela em <pasta do jogo>/imagens; fora de um jogo, a do menu em /roms/imagens.
- SELECT + START (segurar 1 s): fecha o jogo e volta ao Omni36OS.

O contador, a captura e o limite são desenhados pelo hud/omni_hud.so, carregado nos
ports com LD_PRELOAD pelo launch-direct.sh; aqui só mudam os arquivos em /dev/shm.
"""
import fcntl
import json
import os
import pwd
import select
import signal
import struct
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import omni_audio          # noqa: E402
import omni_combos as oc   # noqa: E402
import omni_cpuauto        # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
PAD = "/dev/input/by-path/platform-odroidgo3-joypad-event-joystick"
HOLD = 1.0
EV_SYN, EV_KEY, EV_ABS = 0, 1, 3
EVIOCGRAB = 0x40044590
EVENT = struct.Struct("llHHi")   # timeval (64 bits no aarch64), tipo, código, valor
USER = pwd.getpwnam("ark")
CONF = os.path.join(USER.pw_dir, ".config/omni36os/atalhos.json")
HUD_FLAG = "/dev/shm/omni36os-hud"
CAP_FLAG = "/dev/shm/omni36os-fpscap"
SHOT_FLAG = "/dev/shm/omni36os-shot"
FPS_FLAG = omni_cpuauto.FPS_FILE   # o HUD escreve o FPS do jogo (usado pelo processador automático)
UI_SHOT = "/dev/shm/omni36os-power/shot"   # fora de um jogo (o omni_ui.py lê e apaga)
HUD_LIB = os.path.join(HERE, "hud", "omni_hud.so")
BAT = "/sys/class/power_supply/battery"
POWER_SHM = "/dev/shm/omni36os-power"           # o mesmo do power_button.py: o aviso aparece no Omni36OS
BAT_FLAG = f"{POWER_SHM}/bateria"                # o Omni36OS aberto por cima de uma ferramenta, só para o aviso
# A % da bateria do R36S não é confiável (pula e cai de repente): os limites ficam altos de propósito.
BAT_WARN, BAT_CLOSE, BAT_OFF, BAT_OFF_MV = 30, 15, 10, 3350   # aviso, pedido para fechar, desligar (% e mV)
BAT_EVERY = 30                                  # segundos entre leituras
_conf = (None, None)


def conf():
    """Escolhas do jogador; relidas só quando o arquivo muda."""
    global _conf
    try:
        mt = os.stat(CONF).st_mtime
    except OSError:
        return oc.defaults()
    if _conf[0] != mt:
        try:
            with open(CONF) as f:
                _conf = (mt, oc.normalize(json.load(f)))
        except (OSError, ValueError):
            return oc.defaults()
    return _conf[1]


def put(path, text):
    with open(path, "w") as f:
        f.write(str(text))
    os.chmod(path, 0o666)


def apply_flags(c=None):
    """Estado inicial do HUD: contador escondido e limite desligado (o atalho liga no jogo)."""
    put(HUD_FLAG, "0")
    put(CAP_FLAG, "0")
    put(FPS_FLAG, "")      # criado aqui 0666: o jogo (ark ou root) só reescreve


def pgrep(*args):
    r = subprocess.run(["pgrep", *args], capture_output=True, text=True)
    return [int(p) for p in r.stdout.split()]


def children():
    """pid -> filhos, de /proc."""
    tree = {}
    for d in os.listdir("/proc"):
        if not d.isdigit():
            continue
        try:
            with open(f"/proc/{d}/stat") as f:
                ppid = int(f.read().rsplit(")", 1)[1].split()[1])
        except (OSError, IndexError, ValueError):
            continue
        tree.setdefault(ppid, []).append(int(d))
    return tree


def descendants(pid, tree):
    out, todo = [], list(tree.get(pid, []))
    while todo:
        p = todo.pop()
        out.append(p)
        todo += tree.get(p, [])
    return out


def signal_all(pids, sig):
    for p in pids:
        try:
            os.kill(p, sig)
        except ProcessLookupError:
            pass


def cmdline(pid):
    try:
        with open(f"/proc/{pid}/cmdline", "rb") as f:
            return f.read().replace(b"\0", b" ").decode(errors="ignore")
    except OSError:
        return ""


def game_pids():
    """Os processos do que está na tela, fora o Omni36OS: jogo, port ou ferramenta (filhos do launch-direct.sh)."""
    tree = children()
    out = []
    for h in pgrep("-f", f"{HERE}/launch-direct.sh"):
        for p in descendants(h, tree):
            c = cmdline(p)
            if "omni_ui.py" in c or "power_button" in c or not c:
                continue
            out.append(p)
    return out


def ui_env():
    return {**os.environ, "OMNI_HUB": "jogo", "SDL_GAMECONTROLLERCONFIG_FILE": "/opt/inttools/gamecontrollerdb.txt",
            "SDL_VIDEO_EGL_DRIVER": "libEGL.so", "XDG_RUNTIME_DIR": f"/run/user/{USER.pw_uid}"}


def freeze_and_open(game):
    """Botão de power num jogo: congela o jogo (SIGSTOP), abre o Omni36OS por cima e descongela quando ele fecha. Se o
    Omni36OS não conseguir a tela (alguns ports não soltam o vídeo), o jogo volta na hora."""
    signal_all(game, signal.SIGSTOP)
    try:
        subprocess.run([sys.executable, os.path.join(HERE, "omni_ui.py")], cwd=HERE, env=ui_env(), timeout=3600)
    except subprocess.TimeoutExpired:
        pass
    finally:
        signal_all(game, signal.SIGCONT)


def close_game(game):
    signal_all(game, signal.SIGCONT)        # congelados precisam acordar para morrer
    signal_all(game, signal.SIGTERM)
    end = time.monotonic() + 2.5
    while time.monotonic() < end and any(os.path.exists(f"/proc/{p}") for p in game):
        time.sleep(0.1)
    signal_all(game, signal.SIGKILL)


def read_flag(path, dflt="0"):
    try:
        with open(path) as f:
            return f.read().strip() or dflt
    except OSError:
        return dflt


def active(kind):
    """{chave: botões} dos atalhos ligados de um tipo ("toque" ou "segurar")."""
    c = conf()
    return {k: set(c["combos"][k]) for k, a in oc.ACTIONS.items() if c[k] and a[2] == kind}


def tap(key):
    if not game_pids():
        if key == "captura":             # no menu: o próprio Omni36OS grava a tela (em /roms/imagens)
            os.makedirs(os.path.dirname(UI_SHOT), exist_ok=True)
            put(UI_SHOT, int(time.time() * 1000))
        return
    if key == "fps":
        # ciclo: desligado -> FPS -> FPS + frequência do processador e da GPU -> desligado
        put(HUD_FLAG, {"0": "1", "1": "2"}.get(read_flag(HUD_FLAG), "0"))
    elif key == "captura":
        put(SHOT_FLAG, int(time.time() * 1000))
    elif key == "limite":
        put(CAP_FLAG, "0" if read_flag(CAP_FLAG) != "0" else oc.CAP_FPS)


def held(key):
    game = game_pids()
    if not game:
        return
    if key == "fechar":
        close_game(game)


# --- bateria crítica ---
# Com a bateria no fim o R36S apaga de repente: o jogo perde o save e o cartão pode ficar com
# arquivo pela metade. Aqui ele avisa em 30%, pede para salvar e fechar em 15% e, em 10% (ou
# abaixo de 3,35 V), fecha o jogo com SIGTERM (dá tempo de salvar), grava tudo e desliga. Duas
# leituras seguidas para desligar: um pico de consumo não desliga ninguém. Carregando, nada
# acontece; cada aviso aparece uma vez por descarga.

def battery():
    """(%, mV, carregando) ou None sem bateria (simulador, PC)."""
    try:
        pct = int(read_flag(f"{BAT}/capacity", "-1"))
        mv = int(read_flag(f"{BAT}/voltage_now", "0")) // 1000
    except ValueError:
        return None
    if pct < 0:
        return None
    return pct, mv, read_flag(f"{BAT}/status", "") in ("Charging", "Full")


def notify(title, msg):
    """Alerta no Omni36OS (se estiver na tela) e, num jogo, o contador aparece com a bateria em vermelho."""
    os.makedirs(POWER_SHM, exist_ok=True)
    try:
        os.chmod(POWER_SHM, 0o777)
    except OSError:
        pass
    put(f"{POWER_SHM}/bat-msg", f"{title}\n{msg}")
    try:
        ui = int(read_flag(f"{POWER_SHM}/ui-pid", "0"))
        if ui:
            os.kill(ui, signal.SIGUSR2)
    except (ValueError, OSError):
        pass
    front = game_pids()
    if front and any("run_tool.sh" in cmdline(p) for p in front) and not ui_running():
        # ferramenta do sistema na tela (sem contador de FPS): ela congela e o Omni36OS abre por cima
        # só com o aviso; o OK fecha o aviso e a ferramenta continua de onde estava
        put(BAT_FLAG, str(time.time()))
        subprocess.run(["systemd-run", "--no-block", "--collect", "--unit", f"omni36os-bat-aviso-{int(time.time())}",
                        sys.executable, os.path.join(HERE, "power_button.py"), "--freeze"])
    elif front:
        put(HUD_FLAG, "1")


def ui_running():
    return any("omni_ui.py" in cmdline(p) for p in pgrep("-f", "omni_ui.py"))


def safe_poweroff():
    game = game_pids()
    if game:
        close_game(game)
    os.sync()
    subprocess.run(["systemd-run", "--no-block", "--collect", "--unit", f"omni36os-bateria-{int(time.time())}",
                    "bash", "-c", "systemctl stop omni36os-launcher; /usr/local/bin/omni36os-tela desligando; "
                                  "mountpoint -q /boot && umount /boot; sync; sleep 1; systemctl poweroff"])


class BatteryGuard:
    def __init__(self):
        self.last, self.low, self.warned = 0.0, 0, set()

    def tick(self):
        now = time.monotonic()
        if now - self.last < BAT_EVERY:
            return
        self.last = now
        b = battery()
        if not b:
            return
        pct, mv, charging = b
        if charging:
            self.low, self.warned = 0, set()
            return
        critical = pct <= BAT_OFF or 0 < mv <= BAT_OFF_MV
        self.low = self.low + 1 if critical else 0
        if self.low >= 2:
            print(f"bateria crítica ({pct}%, {mv} mV): desligando", file=sys.stderr, flush=True)
            notify("Desligando", "A bateria está muito fraca. Salvando tudo e desligando com segurança.")
            time.sleep(3)
            safe_poweroff()
            self.low = -999                  # uma vez só
        elif pct <= BAT_CLOSE and "fechar" not in self.warned:
            self.warned |= {"fechar", "aviso"}
            notify("Bateria fraca", f"Restam {pct}%. Salve seu progresso quando puder. Em {BAT_OFF}%, o "
                   "console salva tudo e desliga com segurança.")
        elif pct <= BAT_WARN and "aviso" not in self.warned:
            self.warned.add("aviso")
            notify("Bateria fraca", f"Restam {pct}%. Conecte o carregador quando puder.")


def safe_call(fn, key):
    """Um atalho que falha (arquivo, processo sumido) não pode derrubar o serviço."""
    try:
        fn(key)
    except Exception as e:
        print(f"atalho {key}: {e}", file=sys.stderr, flush=True)


class FnGate:
    """FN como chave: enquanto ele está apertado, o controle fica só com o Omni36OS (EVIOCGRAB),
    então a tecla de um atalho (FN + X...) não chega ao jogo. Outra tecla com o FN (os atalhos do
    ogage: brilho, gamma, ajustes) solta o controle e é devolvida a todos (escrever no evdev injeta
    o evento), igual a antes. Ao soltar o FN, ele também é devolvido: ninguém fica com o FN preso.
    Os analógicos com o FN apertado ficam guardados e são devolvidos na posição final.

    O kernel guarda o estado de cada tecla e descarta evento repetido: o que já passou por ele
    durante o grab só chega aos outros se for devolvido como "vai e volta" (o oposto, depois o
    real). O Omni36OS também lê o que devolve: esses ecos são reconhecidos e pulados."""

    def __init__(self, fd):
        self.fd, self.on, self.since, self.abs, self.echo = fd, False, 0.0, {}, []

    def grab(self, flag):
        try:
            fcntl.ioctl(self.fd, EVIOCGRAB, 1 if flag else 0)
            self.on, self.since = flag, time.monotonic()
        except OSError as e:
            self.on = False
            print(f"fn grab: {e}", file=sys.stderr, flush=True)

    def inject(self, events):
        out = []
        for t, c, v in events:
            for x in ((t, c, 0 if v else 1), (t, c, v)) if t == EV_KEY else ((t, c, v + 1), (t, c, v)):
                out.append(EVENT.pack(0, 0, *x) + EVENT.pack(0, 0, EV_SYN, 0, 0))
                self.echo.append(x)
        try:
            os.write(self.fd, b"".join(out))
        except OSError as e:
            self.echo = []
            print(f"fn inject: {e}", file=sys.stderr, flush=True)

    def release(self, pending):
        """Solta o controle e devolve o que só o Omni36OS viu."""
        self.grab(False)
        self.inject([(EV_ABS, c, v) for c, v in self.abs.items()] + pending)
        self.abs = {}

    def filter(self, events, keys):
        """events: [(tipo, código, valor)] de uma leitura; keys: teclas dos atalhos com FN.
        Devolve os eventos sem os ecos do que o próprio Omni36OS devolveu. Eventos lidos com o
        controle agarrado só chegaram aqui: os que não são atalho voltam para todos."""
        out, owed = [], False            # owed: o resto desta leitura também foi só nosso
        for ev in events:
            typ, code, val = ev
            if typ == EV_SYN:
                continue
            if self.echo and ev == self.echo[0]:
                self.echo.pop(0)
                continue
            out.append(ev)
            if self.on:
                if typ == EV_ABS:
                    self.abs[code] = val
                elif typ == EV_KEY and code not in keys:
                    self.release([ev])                 # FN solto ou atalho do sistema: volta ao normal
                    owed = True
                continue                               # a tecla do atalho: só o Omni36OS
            if typ == EV_KEY and code == oc.FN and val == 1 and keys:
                self.grab(True)                        # o FN em si já chegou a todos
                owed = False
            elif owed:
                self.inject([ev])
        if len(self.echo) > 64:          # eco perdido (controle reaberto): não pula evento de verdade
            self.echo = []
        return out


def open_pad():
    """Espera o controle aparecer (no boot ele pode vir depois deste serviço)."""
    while True:
        try:
            return os.open(PAD, os.O_RDWR)    # escrita: devolver teclas ao jogo (FnGate)
        except OSError:
            time.sleep(1)


def main():
    apply_flags()
    try:                                 # o power sempre abre o menu de energia (pause.sh com o desvio)
        import omni
        omni.set_power_button({"mode": "menu"})
        omni.ensure_swap_xy()            # X e Y trocados continuam trocados depois de atualizar o PortMaster
    except Exception as e:
        print(f"power: {e}", file=sys.stderr, flush=True)
    try:                                 # apelido omni/omni para o SSH e o SFTP
        import omni_sistema
        omni_sistema.ensure_alias()
    except Exception as e:
        print(f"apelido: {e}", file=sys.stderr, flush=True)
    signal.signal(signal.SIGHUP, lambda *_: apply_flags())
    fd = open_pad()
    gate = FnGate(fd)
    down, since, waiting = set(), None, None
    guard, route, cpu = BatteryGuard(), omni_audio.AutoRoute(), omni_cpuauto.AutoCpu()
    while True:
        try:
            cpu.tick()                   # "Limite do processador" em Automático
        except Exception as e:
            print(f"cpu automático: {e}", file=sys.stderr, flush=True)
        try:
            guard.tick()
        except Exception as e:           # a leitura da bateria nunca derruba os atalhos
            print(f"bateria: {e}", file=sys.stderr, flush=True)
        try:
            route.tick()                 # fone encaixado = fone; sem fone = alto-falante
        except Exception as e:
            print(f"som: {e}", file=sys.stderr, flush=True)
        try:
            r, _, _ = select.select([fd], [], [], 0.2)
            data = os.read(fd, EVENT.size * 64) if r else b""
        except OSError:                   # controle sumiu (driver reiniciado): abre de novo
            try:
                os.close(fd)
            except OSError:
                pass
            fd, down, since, waiting = open_pad(), set(), None, None
            gate = FnGate(fd)
            continue
        if data:
            evs = [EVENT.unpack_from(data, k)[2:] for k in range(0, len(data) - EVENT.size + 1, EVENT.size)]
            try:
                evs = gate.filter(evs, {c for cb in active("toque").values() if oc.FN in cb for c in cb - {oc.FN}})
            except Exception as e:       # a chave do FN nunca derruba os atalhos
                print(f"fn: {e}", file=sys.stderr, flush=True)
            for typ, code, val in evs:
                if typ != EV_KEY or val == 2:
                    continue
                if val:
                    down.add(code)
                    for key, cb in active("toque").items():   # a combinação fechou agora
                        if down == cb:
                            safe_call(tap, key)
                else:
                    down.discard(code)
                waiting = next((key for key, cb in active("segurar").items() if down == cb), None)
                since = time.monotonic() if waiting else None
        elif gate.on and time.monotonic() - gate.since > 15:   # FN agarrado sem soltar: devolve
            gate.release([])
        if since is not None and time.monotonic() - since >= HOLD:
            key, since, waiting = waiting, None, None
            down = set()
            safe_call(held, key)


if __name__ == "__main__":
    main()
