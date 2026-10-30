"""Músicas do Omni36OS: índice das pastas, o tocador (SDL_mixer) e o som para as visualizações.

Pastas: /roms/musicas e /roms2/musicas (a do cartão 2 só se ele estiver montado).
Cada pasta mostra as músicas soltas nela e as subpastas; entrar numa subpasta mostra as dela.
Com "Ler subpastas" ligado, a lista de uma pasta inclui as subpastas, nível por nível.

Índice: ~/.config/omni36os/musicas.json guarda, por pasta, a data dela, as subpastas e as músicas
(nome do arquivo, título e artista das tags). Uma pasta só é lida de novo quando a data muda, então
abrir o tocador não varre o cartão inteiro, e a lista de reprodução guarda só caminhos e títulos.
"""
import ctypes as C
import json
import math
import os
import struct
import threading

ROOTS = [("/roms/musicas", "Cartão 1"), ("/roms2/musicas", "Cartão 2")]
INDEX = os.environ.get("OMNI_MUSICA_INDEX") or "/home/ark/.config/omni36os/musicas.json"
EXT = (".mp3", ".ogg", ".flac", ".wav")
INDEX_VER = 1


# --- índice ---

def roots():
    """[(pasta, nome)] das pastas de música que existem agora. A do cartão 1 é criada se faltar,
    para o jogador saber onde pôr as músicas."""
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


def _text(enc, raw):
    try:
        if enc == 0:
            s = raw.decode("latin-1")
        elif enc == 1:
            s = raw.decode("utf-16")
        elif enc == 2:
            s = raw.decode("utf-16-be")
        else:
            s = raw.decode("utf-8", "replace")
    except (UnicodeDecodeError, ValueError):
        s = raw.decode("latin-1", "replace")
    return s.split("\x00")[0].strip()


def tags(path):
    """(título, artista) das tags ID3 (v2.3/2.4, depois v1). Só lê o começo e o fim do arquivo."""
    title = artist = ""
    try:
        with open(path, "rb") as f:
            head = f.read(10)
            if head[:3] == b"ID3" and len(head) == 10:
                ver = head[3]
                size = (head[6] << 21) | (head[7] << 14) | (head[8] << 7) | head[9]
                data = f.read(min(size, 256 * 1024))
                i = 0
                while i + 10 <= len(data) and not (title and artist):
                    fid = data[i:i + 4]
                    if not fid.strip(b"\x00"):
                        break
                    n = struct.unpack(">I", data[i + 4:i + 8])[0]
                    if ver == 4:                                  # 2.4: tamanho "syncsafe"
                        n = (n & 0x7f) | ((n >> 8) & 0x7f) << 7 | ((n >> 16) & 0x7f) << 14 | ((n >> 24) & 0x7f) << 21
                    body = data[i + 10:i + 10 + n]
                    if fid == b"TIT2" and body:
                        title = _text(body[0], body[1:])
                    elif fid == b"TPE1" and body:
                        artist = _text(body[0], body[1:])
                    i += 10 + n
            if not (title and artist) and path.lower().endswith(".mp3"):
                f.seek(-128, os.SEEK_END)
                tail = f.read(128)
                if tail[:3] == b"TAG":
                    title = title or tail[3:33].split(b"\x00")[0].decode("latin-1").strip()
                    artist = artist or tail[33:63].split(b"\x00")[0].decode("latin-1").strip()
    except (OSError, struct.error):
        pass
    return title, artist


class Library:
    def __init__(self):
        self.lock = threading.Lock()
        try:
            with open(INDEX) as f:
                data = json.load(f)
            self.idx = data["pastas"] if data.get("ver") == INDEX_VER else {}
        except (OSError, ValueError, KeyError):
            self.idx = {}
        self.dirty = False

    def listing(self, path):
        """{"dirs": [nomes], "songs": [{"f", "t", "a"}]} da pasta, do índice se ela não mudou."""
        try:
            mtime = os.stat(path).st_mtime
        except OSError:
            return {"dirs": [], "songs": []}
        with self.lock:
            hit = self.idx.get(path)
        if hit and hit["m"] == mtime:
            return hit
        old = {s["f"]: s for s in (hit or {}).get("songs", [])}
        dirs, songs = [], []
        try:
            entries = sorted(os.scandir(path), key=lambda e: e.name.lower())
        except OSError:
            entries = []
        for e in entries:
            if e.name.startswith("."):
                continue
            if e.is_dir(follow_symlinks=False):
                dirs.append(e.name)
            elif e.name.lower().endswith(EXT):
                s = old.get(e.name)
                if not s:
                    t, a = tags(e.path)
                    s = {"f": e.name, "t": t or os.path.splitext(e.name)[0], "a": a}
                songs.append(s)
        hit = {"m": mtime, "dirs": dirs, "songs": songs}
        with self.lock:
            self.idx[path] = hit
            self.dirty = True
        return hit

    def playlist(self, path, deep=False):
        """[(caminho, título, artista)] da pasta; com `deep`, as subpastas também, nível por nível."""
        out, queue = [], [path]
        while queue:
            here = queue.pop(0)
            li = self.listing(here)
            out += [(os.path.join(here, s["f"]), s["t"], s["a"]) for s in li["songs"]]
            if deep:
                queue += [os.path.join(here, d) for d in li["dirs"]]
        self.save()
        return out

    def save(self):
        with self.lock:
            if not self.dirty:
                return
            # pastas que sumiram do cartão saem do índice
            self.idx = {p: v for p, v in self.idx.items() if os.path.isdir(p)}
            data = json.dumps({"ver": INDEX_VER, "pastas": self.idx}, ensure_ascii=False)
            self.dirty = False
        try:
            os.makedirs(os.path.dirname(INDEX), exist_ok=True)
            with open(INDEX + ".tmp", "w") as f:
                f.write(data)
            os.replace(INDEX + ".tmp", INDEX)
        except OSError:
            pass


# --- tocador ---

_mix = None
AUDIO_S16SYS = 0x8010
INIT_AUDIO = 0x10
POSTMIX = C.CFUNCTYPE(None, C.c_void_p, C.POINTER(C.c_uint8), C.c_int)
WIN = 1024                                    # amostras (estéreo, 16 bits) guardadas para a visualização


def _lib():
    global _mix
    if _mix is None:
        m = C.CDLL("libSDL2_mixer-2.0.so.0")
        for name, res, args in (("Mix_OpenAudio", C.c_int, [C.c_int, C.c_uint16, C.c_int, C.c_int]),
                                ("Mix_CloseAudio", None, []), ("Mix_LoadMUS", C.c_void_p, [C.c_char_p]),
                                ("Mix_FreeMusic", None, [C.c_void_p]), ("Mix_PlayMusic", C.c_int, [C.c_void_p, C.c_int]),
                                ("Mix_HaltMusic", C.c_int, []), ("Mix_PauseMusic", None, []),
                                ("Mix_ResumeMusic", None, []), ("Mix_PlayingMusic", C.c_int, []),
                                ("Mix_PausedMusic", C.c_int, []), ("Mix_SetMusicPosition", C.c_int, [C.c_double]),
                                ("Mix_GetMusicPosition", C.c_double, [C.c_void_p]),
                                ("Mix_MusicDuration", C.c_double, [C.c_void_p]),
                                ("Mix_SetPostMix", None, [POSTMIX, C.c_void_p])):
            fn = getattr(m, name)
            fn.restype, fn.argtypes = res, args
        _mix = m
    return _mix


class Player:
    """Toca uma lista de reprodução. tick() a cada quadro passa para a próxima quando uma acaba."""

    def __init__(self, sdl):
        self.sdl, self.m = sdl, None
        self.mus, self.list, self.i = None, [], 0
        self.ok, self.error = False, ""
        self.buf = (C.c_int16 * (WIN * 2))()
        self._hook = POSTMIX(self._postmix)

    def _postmix(self, _udata, stream, length):
        # roda na linha de áudio: só copia as últimas amostras (o cálculo é feito ao desenhar)
        n = min(length, WIN * 4)
        C.memmove(self.buf, C.addressof(stream.contents) + length - n, n)

    def open(self):
        if self.ok:
            return True
        try:
            self.m = _lib()
            self.sdl.SDL_InitSubSystem(INIT_AUDIO)
            if self.m.Mix_OpenAudio(44100, AUDIO_S16SYS, 2, 2048) != 0:
                self.error = "Não consegui abrir a saída de som."
                return False
            self.m.Mix_SetPostMix(self._hook, None)
            self.ok = True
        except OSError:
            self.error = "Falta a biblioteca de som (SDL2_mixer)."
        return self.ok

    def close(self):
        if not self.ok:
            return
        self.stop()
        self.m.Mix_SetPostMix(POSTMIX(), None)
        self.m.Mix_CloseAudio()
        self.sdl.SDL_QuitSubSystem(INIT_AUDIO)
        self.ok = False

    def play(self, playlist, i=0):
        self.list, self.i = playlist, i
        return self._load()

    def _load(self):
        self.stop()
        if not self.list or not self.open():
            return False
        for _ in range(len(self.list)):           # pula arquivos que não abrem
            self.mus = self.m.Mix_LoadMUS(self.list[self.i][0].encode())
            if self.mus and self.m.Mix_PlayMusic(self.mus, 0) == 0:
                C.memset(self.buf, 0, C.sizeof(self.buf))
                return True
            if self.mus:
                self.m.Mix_FreeMusic(self.mus)
                self.mus = None
            self.i = (self.i + 1) % len(self.list)
        self.error = "Nenhuma música desta lista abriu."
        return False

    def stop(self):
        if self.mus:
            self.m.Mix_HaltMusic()
            self.m.Mix_FreeMusic(self.mus)
            self.mus = None

    def step(self, d):
        if self.list:
            self.i = (self.i + d) % len(self.list)
            self._load()

    def toggle(self):
        if not self.mus:
            return self._load()
        if self.m.Mix_PausedMusic():
            self.m.Mix_ResumeMusic()
        else:
            self.m.Mix_PauseMusic()

    @property
    def paused(self):
        return bool(self.mus and self.m.Mix_PausedMusic())

    def seek(self, secs):
        if self.mus:
            pos = max(0.0, min(self.position() + secs, max(0.0, self.duration() - 1)))
            self.m.Mix_SetMusicPosition(pos)

    def position(self):
        return max(0.0, self.m.Mix_GetMusicPosition(self.mus)) if self.mus else 0.0

    def duration(self):
        return max(0.0, self.m.Mix_MusicDuration(self.mus)) if self.mus else 0.0

    def current(self):
        return self.list[self.i] if self.list else None

    def tick(self):
        """Acabou a música: vai para a próxima (a lista recomeça no fim)."""
        if self.mus and not self.m.Mix_PlayingMusic():
            self.step(1)

    def samples(self, n=128):
        """n amostras mono (-1 a 1) do que está tocando, para as visualizações."""
        b, step = self.buf, max(1, WIN // n)
        return [(b[2 * k] + b[2 * k + 1]) / 65536 for k in range(0, WIN, step)][:n]


# --- som em barras ---

BANDS = 16
_tw = None


def spectrum(samples, bands=BANDS):
    """Energia de cada faixa (graves à esquerda), sem escala (quem desenha ajusta o ganho). Uma DFT pequena em faixas espaçadas
    como o ouvido (log): leve o bastante para o processador do R36S a 30 quadros por segundo."""
    global _tw
    n = len(samples)
    if _tw is None or len(_tw[0][0]) != n or len(_tw) != bands:
        _tw = []
        for b in range(bands):
            k = max(1, round(2 ** (b * math.log2(n / 2 - 1) / (bands - 1))))
            win = [0.5 - 0.5 * math.cos(2 * math.pi * j / n) for j in range(n)]
            _tw.append(([math.cos(2 * math.pi * k * j / n) * win[j] for j in range(n)],
                        [math.sin(2 * math.pi * k * j / n) * win[j] for j in range(n)]))
    out = []
    for cs, sn in _tw:
        re = sum(s * c for s, c in zip(samples, cs))
        im = sum(s * c for s, c in zip(samples, sn))
        out.append(math.sqrt(re * re + im * im) / n)
    return out
