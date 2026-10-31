"""Omni36OS — "Limite do processador" em Automático.

Roda dentro do serviço de atalhos (omni_atalho.py chama tick() no laço dele). No jogo, o
launch-direct.sh põe o processador em "performance", então ele anda no scaling_max_freq; aqui
esse teto começa no mínimo e sobe um degrau por vez enquanto o jogo não chega no FPS alvo:
o limite de FPS (FN + B) se estiver ligado, senão 60. Parado no alvo, tenta descer um degrau
de vez em quando; se o FPS cair, volta e espera mais antes de tentar de novo.

O FPS vem do hud/omni_hud.so (/dev/shm/omni36os-fps, reescrito a cada meio segundo). Arquivo
parado = nenhum jogo desenhando: o teto volta ao máximo permitido (carregamento, vídeo e o
menu, que fica no modo economia de qualquer jeito).
"""
import os
import time

import omni

FPS_FILE = "/dev/shm/omni36os-fps"
CAP_FLAG = "/dev/shm/omni36os-fpscap"
SETTLE_UP, SETTLE_DOWN = 2.0, 3.0      # s para o FPS refletir a troca
STEADY = 8.0                           # s no alvo antes de tentar descer
BACKOFF = 30.0                         # s sem tentar descer depois de uma descida que falhou


def _num(path, dflt=0):
    try:
        with open(path) as f:
            return int(f.read().strip() or dflt)
    except (OSError, ValueError):
        return dflt


class AutoCpu:
    def __init__(self):
        self.last = 0.0
        self.in_game = False
        self.idx = 0
        self.mhz = None
        self.settle = self.ok_since = self.down_at = self.hold = 0.0

    def set(self, mhz):
        if mhz != self.mhz:
            omni.write_text(f"{omni.CPUFREQ}/scaling_max_freq", mhz * 1000)
            self.mhz = mhz

    def tick(self):
        now = time.monotonic()
        if now - self.last < 1.0:
            return
        self.last = now
        if not omni.cpu_auto():
            self.in_game, self.mhz = False, None
            return
        try:
            fresh = time.time() - os.stat(FPS_FILE).st_mtime < 2.5
        except OSError:
            fresh = False
        steps = omni.auto_steps()      # o teto muda com o overclock e com a temperatura
        if not fresh:
            if self.in_game or self.mhz is None:
                self.in_game = False
                self.set(steps[-1])
            return
        if not self.in_game:            # o jogo começou a desenhar: começa do mínimo
            self.in_game, self.idx, self.ok_since, self.hold = True, 0, 0.0, 0.0
            self.set(steps[0])
            self.settle = now + SETTLE_UP
            return
        self.idx = min(self.idx, len(steps) - 1)
        if now < self.settle:
            return
        fps = _num(FPS_FILE, -1)
        cap = _num(CAP_FLAG)
        target = cap if cap > 0 else 60
        if 0 <= fps < target - max(1, target * 0.05):
            self.ok_since = 0.0
            if now - self.down_at < SETTLE_DOWN + 3:   # a descida de agora derrubou o FPS
                self.hold = now + BACKOFF
            if self.idx < len(steps) - 1:
                self.idx += 1
                self.settle = now + SETTLE_UP
        else:
            self.ok_since = self.ok_since or now
            if now - self.ok_since >= STEADY and self.idx > 0 and now >= self.hold:
                self.idx -= 1
                self.ok_since, self.down_at = 0.0, now
                self.settle = now + SETTLE_DOWN
        self.set(steps[self.idx])
