"""Botão de power do Omni36OS. O ogage chama o /usr/local/bin/finish.sh a cada toque no
power; com o botão ligado em Ajuda, aquele finish.sh chama este arquivo antes do original.

- FN + power: modo pânico. Fecha o que estiver na tela (jogo, port, ferramenta) e volta ao
  Omni36OS ou ao ES, com o processador sem overclock e o brilho e o som em níveis normais.
  Duas vezes em menos de 10 s: grava tudo e reinicia.
- Power sozinho: abre o menu de energia do Omni36OS (o dele, se estiver na tela; por cima
  do jogo, que congela; ou fechando o menu do ES, com a tela inicial ligada).
- Saída 0: tratado aqui. Qualquer outra saída (ou erro): o finish.sh roda o original, que
  desliga com segurança. Um segundo toque enquanto o menu não abriu também desliga.
"""
import fcntl
import os
import signal
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import omni           # noqa: E402
import omni_atalho as at   # noqa: E402

PAD = at.PAD
FN = 708
EVIOCGKEY = (2 << 30) | (96 << 16) | (ord("E") << 8) | 0x18   # 96 bytes = KEY_MAX 0x2ff
PRESS = "/dev/shm/omni36os-power-press"        # o Omni36OS grava quando o menu está na tela
PENDING = "/dev/shm/omni36os-power-pending"    # menu pedido, ainda abrindo (o ES fechando, o Omni36OS carregando)
MENU_FLAG = "/dev/shm/omni36os-power-menu"     # o Omni36OS abre direto no menu de energia
UI_PID = "/dev/shm/omni36os-ui-pid"
PANIC_LAST = "/dev/shm/omni36os-panic-last"
PANIC_MSG = "/dev/shm/omni36os-panic-msg"
PENDING_WINDOW = 25   # toques enquanto o menu abre são ignorados; depois disso, tenta de novo


def fn_held():
    try:
        fd = os.open(PAD, os.O_RDONLY | os.O_NONBLOCK)
        try:
            buf = bytearray(96)
            fcntl.ioctl(fd, EVIOCGKEY, buf)
        finally:
            os.close(fd)
        return bool(buf[FN // 8] & (1 << (FN % 8)))
    except OSError:
        return False


def stamp(path):
    try:
        return float(open(path).read().strip() or 0)
    except (OSError, ValueError):
        return 0.0


def put(path, text):
    with open(path, "w") as f:
        f.write(text)
    os.chmod(path, 0o666)   # o Omni36OS apaga


def cmdline(pid):
    try:
        with open(f"/proc/{pid}/cmdline", "rb") as f:
            return f.read().replace(b"\0", b" ").decode(errors="ignore")
    except OSError:
        return ""


def ui_pids():
    """O python do Omni36OS que entende o botão (ele grava o pid em UI_PID ao abrir). Um Omni36OS
    de antes da atualização morreria com o SIGUSR1; o sudo em volta repassaria o sinal."""
    try:
        pid = int(open(UI_PID).read().strip())
        with open(f"/proc/{pid}/cmdline", "rb") as f:
            return [pid] if b"omni_ui.py" in f.read() else []
    except (OSError, ValueError):
        return []


def ui_any():
    return at.pgrep("-f", "omni_ui.py")


def front():
    """Os processos do que está na tela, fora o Omni36OS: jogo, port ou ferramenta."""
    tree = at.children()
    hosts = at.pgrep("-f", f"{HERE}/launch.sh") + at.pgrep("-x", "emulationstation")
    out = []
    for h in hosts:
        for p in at.descendants(h, tree):
            c = cmdline(p)
            if "omni_ui.py" in c or "launch.sh" in c or "power_button" in c:
                continue
            out.append(p)
    return out


def close_front():
    pids = front()
    if not pids:
        return False
    at.signal_all(pids, signal.SIGCONT)      # congelados por cima: precisam acordar para morrer
    at.signal_all(pids, signal.SIGTERM)
    end = time.monotonic() + 2.5
    while time.monotonic() < end and any(os.path.exists(f"/proc/{p}") for p in pids):
        time.sleep(0.1)
    at.signal_all(pids, signal.SIGKILL)
    try:
        with open("/dev/tty1", "w") as t:
            t.write("\033c")
    except OSError:
        pass
    return True


def calm():
    """Volta ao seguro o que pode travar ou esquentar: overclock, modo do processador, tela, som."""
    done = []
    try:
        omni.relax_clocks()
        if omni.get_cpu_max() > omni.CPU_SAFE_MHZ:
            omni.write_text(f"{omni.CPUFREQ}/scaling_max_freq", omni.CPU_SAFE_MHZ * 1000)
            done.append(f"processador em {omni.CPU_SAFE_MHZ} MHz")
    except Exception:
        pass
    try:
        if omni.get_brightness() < 20:
            omni.set_screen_brightness({"value": 50})
            done.append("brilho em 50%")
    except Exception:
        pass
    try:
        omni.amixer("-q", "sset", "Playback", "unmute")
        if omni.get_volume() > 85:
            omni.set_system_volume({"value": 70})
            done.append("volume em 70%")
    except Exception:
        pass
    return done


def safe(what):
    """Como o finish.sh original: fecha o ES (ele grava as listas), desmonta o /boot e grava tudo."""
    os.sync()
    subprocess.run(["systemd-run", "--no-block", "--collect", "--unit", f"omni36os-power-{int(time.time())}",
                    "bash", "-c", "systemctl stop emulationstation; mountpoint -q /boot && umount /boot; "
                                  f"sync; systemctl {what}"])


def panic():
    now = time.time()
    last = stamp(PANIC_LAST)
    put(PANIC_LAST, str(now))
    if now - last < 10:
        put(PANIC_MSG, "Pânico duas vezes: reiniciando com segurança")
        safe("reboot")
        return
    closed = close_front()
    done = calm()
    msg = "Pânico: " + ("o que estava na tela foi fechado" if closed else "nada para fechar")
    if done:
        msg += "; " + ", ".join(done)
    put(PANIC_MSG, msg)
    for p in ui_pids():
        try:
            os.kill(p, signal.SIGUSR2)     # o Omni36OS na tela mostra o aviso na hora
        except ProcessLookupError:
            pass


def menu():
    """0 se o menu de energia vai abrir; 1 para o finish.sh desligar."""
    if os.path.exists(PRESS) and ui_pids():
        return 1                           # toque com o menu na tela: desliga
    if time.time() - stamp(PENDING) < PENDING_WINDOW:
        return 0                           # o menu ainda está abrindo: não desligar por engano
    ui = ui_pids()
    if ui_any() and not ui:
        return 1                           # Omni36OS de antes da atualização: desliga como sempre
    game = front()
    if ui:                                 # Omni36OS na tela (sozinho ou por cima de um jogo congelado)
        put(PENDING, str(time.time()))
        for p in ui:
            os.kill(p, signal.SIGUSR1)
        return 0
    es = at.pgrep("-x", "emulationstation")
    if game:
        # o jogo congela e o Omni36OS abre por cima, já no menu; se ele não pegar a tela, o jogo
        # volta e um segundo toque desliga
        put(PENDING, str(time.time()))
        put(MENU_FLAG, str(time.time()))
        subprocess.run(["systemd-run", "--no-block", "--collect", "--unit", f"omni36os-power-menu-{int(time.time())}",
                        "/usr/bin/python3", os.path.abspath(__file__), "--freeze"])
        return 0
    if es and at.pgrep("-f", f"{HERE}/hub.sh"):
        # menu do ES com a tela inicial ligada: o ES grava e sai, o hub abre o Omni36OS no menu
        put(PENDING, str(time.time()))
        put(MENU_FLAG, str(time.time()))
        with open(at.HUB_OPEN, "w"):
            pass
        os.chown(at.HUB_OPEN, at.USER.pw_uid, at.USER.pw_gid)
        os.kill(es[0], signal.SIGTERM)
        return 0
    return 1


def main():
    if "--freeze" in sys.argv:
        game = front()
        if game:
            at.freeze_and_open(game)
        return 0
    if fn_held():
        panic()
        return 0
    return menu()


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        sys.exit(1)
