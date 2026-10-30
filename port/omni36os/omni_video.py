"""Vídeos do Omni36OS: um tocador simples com o ffmpeg do sistema (codecs abertos).

O ffmpeg decodifica no ritmo do vídeo (-re): a imagem sai já no tamanho da tela, em RGB, por um
pipe que o launcher desenha; o som vai direto para o ALSA. Pausar congela o processo (SIGSTOP);
avançar ou voltar reinicia o ffmpeg na posição nova (-ss). Sem decodificação por hardware: vídeos
até 480p ficam leves; 720p depende do codec.

Pastas: /roms/videos (criada se faltar) e /roms2/videos (com o cartão 2).
"""
import json
import os
import signal
import subprocess
import threading
import time

ROOTS = [("/roms/videos", "Cartão 1"), ("/roms2/videos", "Cartão 2")]
EXT = (".mp4", ".mkv", ".webm", ".avi", ".mov", ".m4v", ".ogv", ".mpg", ".mpeg", ".3gp", ".flv", ".wmv")
SCREEN = (640, 480)


def is_video(name):
    return name.lower().endswith(EXT)


def roots():
    """[(pasta, nome)] das pastas de vídeo que existem agora. A do cartão 1 é criada se faltar."""
    out = []
    for path, name in ROOTS:
        base = os.path.dirname(path)
        if not os.path.isdir(path) and path.startswith("/roms/") and os.path.isdir(base):
            try:
                os.makedirs(path, exist_ok=True)
            except OSError:
                pass
        if os.path.isdir(path) and (base == "/roms" or os.path.ismount(base)):
            out.append((path, name))
    return out


def probe(path):
    """{w, h, fps, dur, audio} do vídeo, pelo ffprobe. None se não for um vídeo legível."""
    try:
        out = subprocess.run(["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", path],
                             capture_output=True, text=True, timeout=10).stdout
        info = json.loads(out[out.find("{"):])     # o ffmpeg do dArkOSen imprime a versão da librga antes
    except (OSError, ValueError, subprocess.TimeoutExpired):
        return None
    vs = [s for s in info.get("streams", []) if s.get("codec_type") == "video"
          and not s.get("disposition", {}).get("attached_pic")]
    if not vs:
        return None
    v = vs[0]
    num, _, den = (v.get("avg_frame_rate") or v.get("r_frame_rate") or "30/1").partition("/")
    try:
        fps = float(num) / float(den or 1)
    except (ValueError, ZeroDivisionError):
        fps = 0
    try:
        dur = float(info.get("format", {}).get("duration") or v.get("duration") or 0)
    except ValueError:
        dur = 0
    return {"w": int(v.get("width") or 0), "h": int(v.get("height") or 0), "fps": fps if 1 <= fps <= 120 else 30.0,
            "dur": dur, "audio": any(s.get("codec_type") == "audio" for s in info.get("streams", []))}


def fit(w, h):
    """Tamanho de saída: cabe na tela sem deformar, com largura e altura pares."""
    sw, sh = SCREEN
    if not w or not h:
        return sw, sh
    k = min(sw / w, sh / h)
    return max(2, int(w * k) // 2 * 2), max(2, int(h * k) // 2 * 2)


class Player:
    def __init__(self):
        self.proc = None
        self.info = None
        self.path = None
        self.error = None
        self.frame = None            # bytes RGB do quadro mais novo
        self.serial = 0              # conta quadros novos (o launcher só reenvia quando muda)
        self.paused = False
        self.ended = False
        self.start_pos = 0.0
        self.frames = 0
        self.lock = threading.Lock()

    def open(self, path):
        self.close()
        self.info = probe(path)
        if not self.info:
            self.error = "Este arquivo não parece um vídeo que o Omni36OS consiga abrir."
            return False
        self.path, self.error = path, None
        self.size = fit(self.info["w"], self.info["h"])
        return self.start(0.0)

    def start(self, pos):
        self.stop()
        w, h = self.size
        cmd = ["ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-threads", "4", "-re",
               "-ss", f"{max(0.0, pos):.2f}", "-i", self.path,
               "-map", "0:v:0", "-vf", f"scale={w}:{h}:flags=fast_bilinear", "-pix_fmt", "rgb24",
               "-f", "rawvideo", "pipe:1"]
        if self.info["audio"]:
            cmd += ["-map", "0:a:0", "-ac", "2", "-ar", "44100", "-f", "alsa", "default"]
        try:
            self.proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, bufsize=0)
        except OSError as e:
            self.error = f"Não consegui abrir o ffmpeg: {e}"
            return False
        self.start_pos, self.frames, self.paused, self.ended = max(0.0, pos), 0, False, False
        threading.Thread(target=self._read, args=(self.proc,), daemon=True).start()
        return True

    def _read(self, proc):
        w, h = self.size
        size = w * h * 3
        pipe = proc.stdout
        while True:
            buf = bytearray(size)
            view, got = memoryview(buf), 0
            while got < size:
                n = pipe.readinto(view[got:])
                if not n:
                    break
                got += n
            if got < size:
                break
            with self.lock:
                if proc is not self.proc:
                    return
                self.frame = bytes(buf)
                self.serial += 1
                self.frames += 1
        with self.lock:
            if proc is self.proc:
                self.ended = True

    def stop(self):
        p, self.proc = self.proc, None
        if p:
            try:
                p.send_signal(signal.SIGCONT)
                p.kill()
                p.wait(timeout=2)
            except (OSError, subprocess.TimeoutExpired):
                pass

    def close(self):
        self.stop()
        self.frame, self.info, self.path = None, None, None

    def toggle(self):
        if not self.proc or self.ended:
            return
        self.paused = not self.paused
        try:
            self.proc.send_signal(signal.SIGSTOP if self.paused else signal.SIGCONT)
        except OSError:
            pass

    def position(self):
        if not self.info:
            return 0.0
        return self.start_pos + self.frames / self.info["fps"]

    def duration(self):
        return self.info["dur"] if self.info else 0.0

    def seek(self, delta):
        if not self.info:
            return
        pos = self.position() + delta
        dur = self.duration()
        if dur:
            pos = min(pos, max(0.0, dur - 1))
        was = self.paused
        self.start(max(0.0, pos))
        if was:
            time.sleep(0.15)          # um quadro na posição nova antes de congelar
            self.toggle()
