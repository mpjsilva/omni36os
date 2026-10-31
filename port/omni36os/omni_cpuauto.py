"""Omni36OS — "Limite do processador" e "Limite da GPU" em Automático.

Roda dentro do serviço de atalhos (omni_atalho.py chama tick() no laço dele). No jogo, o
launch-direct.sh põe processador e GPU em "performance", então eles andam no teto
(scaling_max_freq / max_freq); aqui esse teto começa no mínimo e sobe um degrau por vez enquanto o
jogo não chega no FPS alvo: o limite de FPS (FN + B) se estiver ligado, senão 60. Parado no alvo,
tenta descer um degrau de vez em quando; se o FPS cair, volta e espera mais antes de tentar de novo.

Com os dois em Automático, a carga da GPU decide quem mexe: GPU ocupada (>= 80%) sobe primeiro,
senão sobe o processador; para descer, a GPU folgada (< 50%) desce primeiro. Só um em Automático:
só ele mexe, o outro fica no limite fixo dele.

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
GPU_BUSY, GPU_IDLE = 80, 50            # % de carga da GPU


def _num(path, dflt=0):
    try:
        with open(path) as f:
            return int(f.read().strip() or dflt)
    except (OSError, ValueError):
        return dflt


class Knob:
    """Um teto controlado: o do processador ou o da GPU."""

    def __init__(self, enabled, steps, path, scale):
        self.enabled, self.steps, self.path, self.scale = enabled, steps, path, scale
        self.reset()

    def reset(self):
        self.idx, self.mhz, self.hold, self.down_at, self.cur = 0, None, 0.0, -99.0, [0]

    def refresh(self):
        self.cur = self.steps()          # o teto muda com o overclock e com a temperatura
        self.idx = min(self.idx, len(self.cur) - 1)

    def apply(self):
        mhz = self.cur[self.idx]
        if mhz != self.mhz:
            omni.write_text(self.path, mhz * self.scale)
            self.mhz = mhz

    def can_up(self):
        return self.idx < len(self.cur) - 1

    def can_down(self, now):
        return self.idx > 0 and now >= self.hold


class AutoCpu:
    def __init__(self):
        self.cpu = Knob(omni.cpu_auto, omni.auto_steps, f"{omni.CPUFREQ}/scaling_max_freq", 1000)
        self.gpu = Knob(omni.gpu_auto, omni.gpu_auto_steps, f"{omni.GPU_DEV}/max_freq", 1000000)
        self.last = 0.0
        self.in_game = False
        self.settle = self.ok_since = 0.0

    def tick(self):
        now = time.monotonic()
        if now - self.last < 1.0:
            return
        self.last = now
        knobs = []
        for k in (self.cpu, self.gpu):
            if k.enabled():
                knobs.append(k)
            elif k.mhz is not None:
                k.reset()                # saiu do Automático: o limite fixo já foi escrito
        if not knobs:
            self.in_game = False
            return
        try:
            fresh = time.time() - os.stat(FPS_FILE).st_mtime < 2.5
        except OSError:
            fresh = False
        for k in knobs:
            k.refresh()
        if not fresh:                    # sem jogo desenhando: teto liberado
            self.in_game = False
            for k in knobs:
                k.idx = len(k.cur) - 1
                k.apply()
            return
        if not self.in_game:             # o jogo começou a desenhar: começa do mínimo
            self.in_game, self.ok_since = True, 0.0
            for k in knobs:
                k.idx, k.hold, k.down_at = 0, 0.0, -99.0
                k.apply()
            self.settle = now + SETTLE_UP
            return
        if now < self.settle:
            return
        fps = _num(FPS_FILE, -1)
        cap = _num(CAP_FLAG)
        target = cap if cap > 0 else 60
        load = omni.gpu_load()
        gpu_first = self.gpu in knobs
        if 0 <= fps < target - max(1, target * 0.05):
            self.ok_since = 0.0
            for k in knobs:              # a descida de agora derrubou o FPS
                if now - k.down_at < SETTLE_DOWN + 3:
                    k.hold = now + BACKOFF
            order = [self.gpu, self.cpu] if gpu_first and load >= GPU_BUSY else [self.cpu, self.gpu]
            k = next((k for k in order if k in knobs and k.can_up()), None)
            if k:
                k.idx += 1
                self.settle = now + SETTLE_UP
        else:
            self.ok_since = self.ok_since or now
            if now - self.ok_since >= STEADY:
                order = [self.gpu, self.cpu] if gpu_first and 0 <= load < GPU_IDLE else [self.cpu, self.gpu]
                k = next((k for k in order if k in knobs and k.can_down(now)), None)
                if k:
                    k.idx -= 1
                    k.down_at, self.ok_since = now, 0.0
                    self.settle = now + SETTLE_DOWN
        for k in knobs:
            k.apply()
