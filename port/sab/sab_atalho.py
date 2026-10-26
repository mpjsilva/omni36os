"""Atalho global da Sab: segurar L3+R3 (os dois analógicos) por 1 s abre a Sab.

Roda como serviço (sab-atalho.service, ligado em Ajuda > Atalho L3+R3).
- No menu do ES: com a tela inicial ligada, fecha o ES e o hub.sh abre a Sab
  (ao sair dela o ES volta). Sem a tela inicial, um job do systemd para o ES,
  abre a Sab e sobe o ES de novo.
- Dentro de um jogo (modo "jogo", experimental): congela o jogo (SIGSTOP),
  abre a Sab por cima e descongela quando ela fecha. Se a Sab não conseguir a
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
COMBO = {706, 707}            # L3 e R3 (b14 e b15 no gamecontrollerdb do R36S)
HOLD = 1.0
EV_KEY = 1
EVENT = struct.Struct("llHHi")   # timeval (64 bits no aarch64), tipo, código, valor
CONF = "/home/ark/.config/sab/atalho"
HUB_OPEN = "/dev/shm/sab-hub-open"
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
    if pgrep("-f", "sab_ui.py"):
        return                                   # já aberta
    es = pgrep("-x", "emulationstation")
    if not es:
        return
    game = descendants(es[0], children())
    if not game:                                 # menu do ES
        if pgrep("-f", f"{HERE}/hub.sh"):
            with open(HUB_OPEN, "w"):
                pass
            os.chown(HUB_OPEN, USER.pw_uid, USER.pw_gid)   # o hub (usuário ark) apaga depois
            os.kill(es[0], signal.SIGTERM)       # o ES salva as listas e sai; o hub abre a Sab
        else:
            launch = " ".join(as_ark(["bash", f"{HERE}/launch.sh"], SAB_HUB="atalho"))
            subprocess.run(["systemd-run", "--no-block", "--collect", "--unit", f"sab-atalho-{int(time.time())}",
                            "bash", "-c", f"systemctl stop emulationstation; {launch}; "
                                          "systemctl start emulationstation"])
        return
    if mode() != "jogo":
        return
    signal_all(game, signal.SIGSTOP)
    try:
        subprocess.run(as_ark(["bash", f"{HERE}/launch.sh"], SAB_HUB="jogo"), timeout=3600)
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
                if typ != EV_KEY or code not in COMBO:
                    continue
                (down.add if val else down.discard)(code)
                since = time.monotonic() if down == COMBO else None
        if since is not None and time.monotonic() - since >= HOLD:
            since, down = None, set()
            if mode() != "desligado":
                open_sab()


if __name__ == "__main__":
    main()
