"""Botão de power do Omni36OS. O ogage chama o /usr/local/bin/pause.sh a cada toque no
power; com o botão ligado em Ajuda, aquele pause.sh chama este arquivo antes do original.

- FN + power: desliga na hora, com segurança: fecha o jogo (que salva o que sabe salvar), grava
  tudo e desmonta o /boot antes de desligar.
- Power sozinho: abre o menu de energia do Omni36OS (o dele, se estiver na tela, ou por cima
  do jogo, que congela).
- Power com o menu de energia já na tela: desliga com segurança.
- Saída 0: tratado aqui. Qualquer outra saída (ou erro): o pause.sh roda o original (suspende).
"""
import fcntl
import os
import signal
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import omni_atalho as at   # noqa: E402

PAD = at.PAD
FN = 708
EVIOCGKEY = (2 << 30) | (96 << 16) | (ord("E") << 8) | 0x18   # 96 bytes = KEY_MAX 0x2ff
# Numa pasta própria, aberta e sem o bit sticky: no /dev/shm (sticky) com fs.protected_regular=2 o
# root (este arquivo) e o ark (o Omni36OS) não conseguem regravar nem apagar os arquivos um do outro,
# e um "menu na tela" que ficasse para trás fazia todo toque cair no pause.sh original (suspender).
SHM = "/dev/shm/omni36os-power"
PRESS = f"{SHM}/press"            # o Omni36OS grava o pid dele quando o menu está na tela
PENDING = f"{SHM}/pending"        # menu pedido, ainda abrindo (o Omni36OS carregando)
MENU_FLAG = f"{SHM}/menu"         # o Omni36OS abre direto no menu de energia
UI_PID = f"{SHM}/ui-pid"
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


def shm_dir():
    os.makedirs(SHM, exist_ok=True)
    try:
        os.chmod(SHM, 0o777)
    except OSError:
        pass


def put(path, text):
    shm_dir()
    with open(path, "w") as f:
        f.write(text)
    os.chmod(path, 0o666)   # o Omni36OS apaga


def is_ui(pid):
    """O processo é o python do Omni36OS (não o sudo nem o shell em volta, que repassariam o sinal)?"""
    try:
        with open(f"/proc/{pid}/cmdline", "rb") as f:
            argv = f.read().split(b"\0")
    except OSError:
        return False
    return os.path.basename(argv[0]).startswith(b"python") and any(a.endswith(b"omni_ui.py") for a in argv[1:])


def ui_pids():
    """O Omni36OS na tela: o pid que ele grava em UI_PID ao abrir ou, se o arquivo falhar, o
    procurado no /proc (o mais novo: o que abriu por cima de um jogo)."""
    try:
        pid = int(open(UI_PID).read().strip())
        if is_ui(pid):
            return [pid]
    except (OSError, ValueError):
        pass
    found = [p for p in ui_any() if is_ui(p)]
    return found[-1:]


def ui_any():
    return at.pgrep("-f", "omni_ui.py")


def front():
    """Os processos do que está na tela, fora o Omni36OS: jogo, port ou ferramenta."""
    return at.game_pids()


def close_front():
    pids = front()
    if not pids:
        return False
    at.close_game(pids)
    try:
        with open("/dev/tty1", "w") as t:
            t.write("\033c")
    except OSError:
        pass
    return True


def safe(what):
    """Como o finish.sh original: fecha o Omni36OS, desmonta o /boot e grava tudo."""
    os.sync()
    subprocess.run(["systemd-run", "--no-block", "--collect", "--unit", f"omni36os-power-{int(time.time())}",
                    "bash", "-c", "/usr/local/bin/omni36os-turbo; systemctl stop omni36os-launcher; "
                                  f"/usr/local/bin/omni36os-tela {'reiniciando' if what == 'reboot' else 'desligando'}; "
                                  "mountpoint -q /boot && umount /boot; "
                                  f"sync; sleep 1; systemctl {what}"])


def menu():
    """0 se o toque foi tratado aqui; 1 para o pause.sh rodar o original (suspender)."""
    ui = ui_pids()
    if ui and stamp(PRESS) == ui[0]:
        safe("poweroff")                   # toque com o menu na tela: desliga (o original suspenderia)
        return 0
    if time.time() - stamp(PENDING) < PENDING_WINDOW:
        return 0                           # o menu ainda está abrindo: não desligar por engano
    game = front()
    if ui:                                 # Omni36OS na tela (sozinho ou por cima de um jogo congelado)
        put(PENDING, str(time.time()))
        for p in ui:
            os.kill(p, signal.SIGUSR1)
        return 0
    if game:
        # o jogo congela e o Omni36OS abre por cima, já no menu; se ele não pegar a tela, o jogo
        # volta e um segundo toque desliga
        put(PENDING, str(time.time()))
        put(MENU_FLAG, str(time.time()))
        subprocess.run(["systemd-run", "--no-block", "--collect", "--unit", f"omni36os-power-menu-{int(time.time())}",
                        "/usr/bin/python3", os.path.abspath(__file__), "--freeze"])
        return 0
    return 1


def main():
    if "--freeze" in sys.argv:
        game = front()
        if game:
            at.freeze_and_open(game)
        return 0
    if fn_held():
        close_front()
        safe("poweroff")
        return 0
    return menu()


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        sys.exit(1)
