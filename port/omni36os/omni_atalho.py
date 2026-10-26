"""Atalho global do Omni36OS: segurar L3+R3 (os dois analógicos) ou FN+SELECT por
1 s alterna entre o Omni36OS e o que estiver na tela (ES ou jogo).

Roda como serviço (omni36os-atalho.service, ligado em Ajuda > Atalho L3+R3).
- No menu do ES: com a tela inicial ligada, fecha o ES e o hub.sh abre o Omni36OS
  (ao sair dela o ES volta). Sem a tela inicial, um job do systemd para o ES,
  abre o Omni36OS e sobe o ES de novo.
- Dentro de um jogo (modo "jogo", experimental): congela o jogo (SIGSTOP),
  abre o Omni36OS por cima e descongela quando ela fecha. Se o Omni36OS não conseguir a
  tela (alguns emuladores não soltam o vídeo), o jogo volta na hora.
Lê o controle direto do /dev/input, sem bibliotecas: struct input_event.
"""
import os
import pwd
import select
import signal
import struct
import subprocess
import time

HERE = os.path.dirname(os.path.abspath(__file__))
PAD = "/dev/input/by-path/platform-odroidgo3-joypad-event-joystick"
# L3+R3 (b14 e b15 no gamecontrollerdb do R36S) e FN+SELECT (708 e 704)
COMBOS = ({706, 707}, {708, 704})
WATCH = set().union(*COMBOS)
HOLD = 1.0
EV_KEY = 1
EVENT = struct.Struct("llHHi")   # timeval (64 bits no aarch64), tipo, código, valor
CONF = "/home/ark/.config/omni36os/atalho"
HUB_OPEN = "/dev/shm/omni36os-hub-open"
USER = pwd.getpwnam("ark")


def mode():
    try:
        with open(CONF) as f:
            return f.read().strip()
    except OSError:
        return "ligado"


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


def as_ark(cmd, **env):
    e = {"HOME": USER.pw_dir, "USER": "ark", "PATH": "/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin",
         "SDL_VIDEO_EGL_DRIVER": "libEGL.so", "XDG_RUNTIME_DIR": f"/run/user/{USER.pw_uid}", **env}
    return ["runuser", "-u", "ark", "--", "env", *[f"{k}={v}" for k, v in e.items()], *cmd]


def open_sab():
    ui = pgrep("-f", "python3 omni_ui.py")
    if ui:                                       # já aberto: fecha e volta para o ES ou o jogo
        signal_all(ui, signal.SIGTERM)
        return
    es = pgrep("-x", "emulationstation")
    if not es:
        # jogo aberto pelo card Jogos (sem o ES): o jogo é filho do launch.sh do hub
        hosts = pgrep("-f", f"{HERE}/launch.sh")
        tree = children()
        game = [p for h in hosts for p in descendants(h, tree)]
        if game and mode() == "jogo":
            freeze_and_open(game)
        return
    game = descendants(es[0], children())
    if not game:                                 # menu do ES
        if pgrep("-f", f"{HERE}/hub.sh"):
            with open(HUB_OPEN, "w"):
                pass
            os.chown(HUB_OPEN, USER.pw_uid, USER.pw_gid)   # o hub (usuário ark) apaga depois
            os.kill(es[0], signal.SIGTERM)       # o ES salva as listas e sai; o hub abre o Omni36OS
        else:
            launch = " ".join(as_ark(["bash", f"{HERE}/launch.sh"], OMNI_HUB="atalho"))
            subprocess.run(["systemd-run", "--no-block", "--collect", "--unit", f"omni36os-atalho-{int(time.time())}",
                            "bash", "-c", f"systemctl stop emulationstation; {launch}; "
                                          "systemctl start emulationstation"])
        return
    if mode() == "jogo":
        freeze_and_open(game)


def freeze_and_open(game):
    signal_all(game, signal.SIGSTOP)
    try:
        subprocess.run(as_ark(["bash", f"{HERE}/launch.sh"], OMNI_HUB="jogo"), timeout=3600)
    except subprocess.TimeoutExpired:
        pass
    finally:
        signal_all(game, signal.SIGCONT)


def main():
    fd = os.open(PAD, os.O_RDONLY)
    down, since = set(), None
    while True:
        r, _, _ = select.select([fd], [], [], 0.2)
        if r:
            data = os.read(fd, EVENT.size * 64)
            for k in range(0, len(data) - EVENT.size + 1, EVENT.size):
                _s, _us, typ, code, val = EVENT.unpack_from(data, k)
                if typ != EV_KEY or code not in WATCH:
                    continue
                (down.add if val else down.discard)(code)
                since = time.monotonic() if down in COMBOS else None
        if since is not None and time.monotonic() - since >= HOLD:
            since, down = None, set()
            if mode() != "desligado":
                open_sab()


if __name__ == "__main__":
    main()
