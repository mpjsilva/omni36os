"""Saída de som automática: fone encaixado = HP (só o fone), sem fone = SPK (só o alto-falante).

O R36S avisa o encaixe do fone pelo hp-det-gpio do DTB (rk817-sound): o kernel cria um
dispositivo de entrada com a chave SW_HEADPHONE_INSERT. O ogage do dArkOSen troca a saída só no
momento do encaixe; se o fone já estava no boot ou um programa mexeu na saída, ela ficava errada.
O serviço omni36os-atalho chama AutoRoute.tick() o tempo todo e corrige na hora.
"""
import fcntl
import glob
import os
import subprocess
import time

SW_HEADPHONE_INSERT = 2
EVIOCGSW = (2 << 30) | (8 << 16) | (ord("E") << 8) | 0x1b      # estado das chaves (8 bytes)
HP, SPK = "HP", "SPK"


def jack_device():
    """/dev/input/eventN que informa o fone, ou None (sem detecção: a saída fica como está)."""
    for d in sorted(glob.glob("/sys/class/input/event*")):
        try:
            with open(f"{d}/device/capabilities/sw") as f:
                bits = int(f.read().split()[-1], 16)
        except (OSError, ValueError, IndexError):
            continue
        if bits & (1 << SW_HEADPHONE_INSERT):
            return "/dev/input/" + os.path.basename(d)
    return None


def headphones_in(dev=None):
    """True/False com o fone encaixado ou não; None se não dá para saber."""
    dev = dev or jack_device()
    if not dev:
        return None
    try:
        fd = os.open(dev, os.O_RDONLY | os.O_NONBLOCK)
        try:
            buf = bytearray(8)
            fcntl.ioctl(fd, EVIOCGSW, buf)
        finally:
            os.close(fd)
    except OSError:
        return None
    return bool(buf[0] & (1 << SW_HEADPHONE_INSERT))


def amixer(*args):
    return subprocess.run(["amixer", "-c", "0", *args], capture_output=True, text=True, timeout=5).stdout


def current_path():
    for line in amixer("sget", "Playback Path").splitlines():
        if line.strip().startswith("Item0:") and "'" in line:
            return line.split("'")[1]
    return ""


def expected_path(dev=None):
    """HP ou SPK conforme o fone; None sem detecção do fone."""
    hp = headphones_in(dev)
    return None if hp is None else (HP if hp else SPK)


def apply(dev=None):
    """Põe a saída certa agora. Devolve a saída aplicada (ou None sem detecção)."""
    want = expected_path(dev)
    if want and current_path() != want:
        amixer("-q", "cset", "name=Playback Path", want)
    return want


class AutoRoute:
    """Confere o fone a cada segundo e a saída a cada 10 s (alguém pode ter mudado)."""

    def __init__(self):
        self.dev, self.last_hp, self.next_dev, self.next_check = None, None, 0.0, 0.0
        self.last_tick = 0.0

    def tick(self):
        now = time.monotonic()
        if now - self.last_tick < 1:
            return
        self.last_tick = now
        if not self.dev and now >= self.next_dev:
            self.dev, self.next_dev = jack_device(), now + 30
        if not self.dev:
            return
        hp = headphones_in(self.dev)
        if hp is None:
            self.dev = None                     # sumiu: procura de novo
            return
        if hp != self.last_hp or now >= self.next_check:
            self.last_hp, self.next_check = hp, now + 10
            apply(self.dev)
