"""Omni36OS — desenho com a SDL2 via ctypes (sem pygame no dArkOS).

Formas são triângulos (SDL_RenderGeometry) com cor por vértice: dá degradê,
borda suave (uma faixa de 1 px que some no alfa) e brilho/sombra (a mesma
faixa, larga) sem texturas. Texto com SDL2_ttf, ícones PNG com SDL2_image.
"""
import ctypes as C
import math
import os

sdl = C.CDLL("libSDL2-2.0.so.0")
ttf = C.CDLL("libSDL2_ttf-2.0.so.0")
img = C.CDLL("libSDL2_image-2.0.so.0")

P = C.c_void_p


class FPoint(C.Structure):
    _fields_ = [("x", C.c_float), ("y", C.c_float)]


class Color(C.Structure):
    _fields_ = [("r", C.c_uint8), ("g", C.c_uint8), ("b", C.c_uint8), ("a", C.c_uint8)]


class Vertex(C.Structure):
    _fields_ = [("position", FPoint), ("color", Color), ("tex_coord", FPoint)]


class FRect(C.Structure):
    _fields_ = [("x", C.c_float), ("y", C.c_float), ("w", C.c_float), ("h", C.c_float)]


class Rect(C.Structure):
    _fields_ = [("x", C.c_int), ("y", C.c_int), ("w", C.c_int), ("h", C.c_int)]


def _f(lib, name, res, *args):
    fn = getattr(lib, name)
    fn.restype, fn.argtypes = res, list(args)
    return fn


SDL_Init = _f(sdl, "SDL_Init", C.c_int, C.c_uint32)
SDL_Quit = _f(sdl, "SDL_Quit", None)
SDL_GetError = _f(sdl, "SDL_GetError", C.c_char_p)
SDL_SetHint = _f(sdl, "SDL_SetHint", C.c_int, C.c_char_p, C.c_char_p)
SDL_CreateWindow = _f(sdl, "SDL_CreateWindow", P, C.c_char_p, C.c_int, C.c_int, C.c_int, C.c_int, C.c_uint32)
SDL_CreateRenderer = _f(sdl, "SDL_CreateRenderer", P, P, C.c_int, C.c_uint32)
SDL_RenderSetLogicalSize = _f(sdl, "SDL_RenderSetLogicalSize", C.c_int, P, C.c_int, C.c_int)
SDL_SetRenderDrawBlendMode = _f(sdl, "SDL_SetRenderDrawBlendMode", C.c_int, P, C.c_int)
SDL_SetRenderDrawColor = _f(sdl, "SDL_SetRenderDrawColor", C.c_int, P, C.c_uint8, C.c_uint8, C.c_uint8, C.c_uint8)
SDL_RenderClear = _f(sdl, "SDL_RenderClear", C.c_int, P)
SDL_RenderPresent = _f(sdl, "SDL_RenderPresent", None, P)
SDL_RenderGeometry = _f(sdl, "SDL_RenderGeometry", C.c_int, P, P, C.POINTER(Vertex), C.c_int, P, C.c_int)
SDL_RenderCopyF = _f(sdl, "SDL_RenderCopyF", C.c_int, P, P, P, C.POINTER(FRect))
SDL_RenderSetClipRect = _f(sdl, "SDL_RenderSetClipRect", C.c_int, P, C.POINTER(Rect))
SDL_RenderReadPixels = _f(sdl, "SDL_RenderReadPixels", C.c_int, P, P, C.c_uint32, P, C.c_int)
SDL_CreateTexture = _f(sdl, "SDL_CreateTexture", P, P, C.c_uint32, C.c_int, C.c_int, C.c_int)
SDL_SetRenderTarget = _f(sdl, "SDL_SetRenderTarget", C.c_int, P, P)
SDL_GetRenderTarget = _f(sdl, "SDL_GetRenderTarget", P, P)
SDL_CreateTextureFromSurface = _f(sdl, "SDL_CreateTextureFromSurface", P, P, P)
SDL_FreeSurface = _f(sdl, "SDL_FreeSurface", None, P)
SDL_QueryTexture = _f(sdl, "SDL_QueryTexture", C.c_int, P, P, P, C.POINTER(C.c_int), C.POINTER(C.c_int))
SDL_SetTextureColorMod = _f(sdl, "SDL_SetTextureColorMod", C.c_int, P, C.c_uint8, C.c_uint8, C.c_uint8)
SDL_SetTextureAlphaMod = _f(sdl, "SDL_SetTextureAlphaMod", C.c_int, P, C.c_uint8)
SDL_SetTextureBlendMode = _f(sdl, "SDL_SetTextureBlendMode", C.c_int, P, C.c_int)
SDL_DestroyTexture = _f(sdl, "SDL_DestroyTexture", None, P)
SDL_PollEvent = _f(sdl, "SDL_PollEvent", C.c_int, P)
SDL_GetTicks = _f(sdl, "SDL_GetTicks", C.c_uint32)
SDL_Delay = _f(sdl, "SDL_Delay", None, C.c_uint32)
SDL_ShowCursor = _f(sdl, "SDL_ShowCursor", C.c_int, C.c_int)
SDL_NumJoysticks = _f(sdl, "SDL_NumJoysticks", C.c_int)
SDL_IsGameController = _f(sdl, "SDL_IsGameController", C.c_int, C.c_int)
SDL_GameControllerOpen = _f(sdl, "SDL_GameControllerOpen", P, C.c_int)
TTF_Init = _f(ttf, "TTF_Init", C.c_int)
TTF_OpenFont = _f(ttf, "TTF_OpenFont", P, C.c_char_p, C.c_int)
TTF_RenderUTF8_Blended = _f(ttf, "TTF_RenderUTF8_Blended", P, P, C.c_char_p, Color)
TTF_SizeUTF8 = _f(ttf, "TTF_SizeUTF8", C.c_int, P, C.c_char_p, C.POINTER(C.c_int), C.POINTER(C.c_int))
IMG_Load = _f(img, "IMG_Load", P, C.c_char_p)

INIT_VIDEO, INIT_GAMECONTROLLER = 0x20, 0x2000
WINDOW_FULLSCREEN, WINDOW_SHOWN = 0x1, 0x4
RENDERER_ACCELERATED, RENDERER_PRESENTVSYNC = 0x2, 0x4
BLEND = 1
PIXELFORMAT_RGB24 = 0x17101803
PIXELFORMAT_ABGR8888 = 0x16762004
TEXTUREACCESS_TARGET = 2

W, H = 640, 480
HERE = os.path.dirname(os.path.abspath(__file__))


def mix(a, b, t):
    return tuple(a[i] + (b[i] - a[i]) * t for i in range(len(a)))


def hexc(s, a=255):
    s = s.lstrip("#")
    return (int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16), a)


def alpha(c, a):
    return (c[0], c[1], c[2], a)


class Gfx:
    def __init__(self, title="Omni36OS"):
        if SDL_Init(INIT_VIDEO | INIT_GAMECONTROLLER) != 0:
            raise RuntimeError(SDL_GetError().decode())
        SDL_SetHint(b"SDL_RENDER_SCALE_QUALITY", b"1")
        flags = WINDOW_SHOWN | (0 if os.environ.get("OMNI_WINDOWED") else WINDOW_FULLSCREEN)
        self.win = SDL_CreateWindow(title.encode(), 0, 0, W, H, flags)
        if not self.win:
            raise RuntimeError(SDL_GetError().decode())
        self.r = SDL_CreateRenderer(self.win, -1, RENDERER_ACCELERATED | RENDERER_PRESENTVSYNC) \
            or SDL_CreateRenderer(self.win, -1, 0)
        SDL_RenderSetLogicalSize(self.r, W, H)
        SDL_SetRenderDrawBlendMode(self.r, BLEND)
        SDL_ShowCursor(0)
        TTF_Init()
        self.fonts, self.text_cache, self.icons = {}, {}, {}
        # Formas prontas: montar vértices em Python é o caro (a CPU do R36S
        # fazia ~1 quadro/s); cada forma é montada uma vez e reaproveitada.
        self.vcache = {}
        self.wcache = {}
        self.sprites = {}
        self.blob_tex = self._make_blob()

    # --- triângulos ---

    @staticmethod
    def build(verts):
        n = len(verts)
        return (Vertex * n)(*[((x, y), tuple(0 if k < 0 else 255 if k > 255 else int(k) for k in c), (0, 0))
                              for x, y, c in verts]), n

    def tris(self, verts):
        arr, n = self.build(verts)
        SDL_RenderGeometry(self.r, None, arr, n, None, 0)

    def cached(self, key, make):
        hit = self.vcache.get(key)
        if hit is None:
            if len(self.vcache) > 8000:
                self.vcache.clear()
            hit = self.vcache[key] = self.build(make())
        SDL_RenderGeometry(self.r, None, hit[0], hit[1], None, 0)

    @staticmethod
    def q(*vals):
        """Chave de cache: posições em meio pixel, cores inteiras (alfa em passos de 8)."""
        out = []
        for v in vals:
            if isinstance(v, tuple):
                out.append(tuple(int(k) for k in v[:3]) + ((int(v[3]) >> 3,) if len(v) > 3 else ()))
            elif isinstance(v, float):
                out.append(round(v * 2))
            else:
                out.append(v)
        return tuple(out)

    @staticmethod
    def outline(x, y, w, h, r):
        """Contorno do retângulo arredondado: (ponto, normal) em sentido horário."""
        r = max(0.5, min(r, w / 2, h / 2))
        seg = max(3, min(7, int(r / 3.5)))
        pts = []
        for cx, cy, a0 in ((x + w - r, y + r, -90), (x + w - r, y + h - r, 0),
                           (x + r, y + h - r, 90), (x + r, y + r, 180)):
            for i in range(seg + 1):
                a = math.radians(a0 + 90 * i / seg)
                nx, ny = math.cos(a), math.sin(a)
                pts.append((cx + nx * r, cy + ny * r, nx, ny))
        return pts

    def rrect(self, x, y, w, h, r, c1, c2=None, feather=1.0):
        """Retângulo arredondado cheio; c2 = cor de baixo (degradê vertical)."""
        c2 = c2 or c1
        self.cached(self.q("r", x, y, w, h, r, c1, c2, feather),
                    lambda: self._rrect(x, y, w, h, r, c1, c2, feather))

    def _rrect(self, x, y, w, h, r, c1, c2, feather):
        pts = self.outline(x, y, w, h, r)
        c1, c2 = (*c1[:3], c1[3] if len(c1) > 3 else 255), (*c2[:3], c2[3] if len(c2) > 3 else 255)
        c1, c2 = (*c1[:3], c1[3] // 8 * 8), (*c2[:3], c2[3] // 8 * 8)
        col = lambda py: mix(c1, c2, (py - y) / h if h else 0)
        cx, cy = x + w / 2, y + h / 2
        cc = col(cy)
        v = []
        n = len(pts)
        for i in range(n):
            ax, ay, anx, any_ = pts[i]
            bx, by, bnx, bny = pts[(i + 1) % n]
            ca, cb = col(ay), col(by)
            v += [(cx, cy, cc), (ax, ay, ca), (bx, by, cb)]
            if feather:
                qa = (ax + anx * feather, ay + any_ * feather, alpha(ca, 0))
                qb = (bx + bnx * feather, by + bny * feather, alpha(cb, 0))
                v += [(ax, ay, ca), (bx, by, cb), qa, qa, (bx, by, cb), qb]
        return v

    def glow(self, x, y, w, h, r, c, spread):
        """Halo em volta do retângulo: some do alfa de c até 0 em `spread` px."""
        self.cached(self.q("g", x, y, w, h, r, c, spread), lambda: self._glow(x, y, w, h, r, c, spread))

    def _glow(self, x, y, w, h, r, c, spread):
        c = (*c[:3], int(c[3]) // 8 * 8)
        pts = self.outline(x, y, w, h, r)
        v = []
        n = len(pts)
        c0 = alpha(c, 0)
        for i in range(n):
            ax, ay, anx, any_ = pts[i]
            bx, by, bnx, bny = pts[(i + 1) % n]
            qa = (ax + anx * spread, ay + any_ * spread, c0)
            qb = (bx + bnx * spread, by + bny * spread, c0)
            v += [(ax, ay, c), (bx, by, c), qa, qa, (bx, by, c), qb]
        return v

    def stroke(self, x, y, w, h, r, c, width=1.0):
        self.cached(self.q("s", x, y, w, h, r, c, width), lambda: self._stroke(x, y, w, h, r, c, width))

    def _stroke(self, x, y, w, h, r, c, width):
        c = (*c[:3], int(c[3]) // 8 * 8)
        pts = self.outline(x, y, w, h, r)
        v = []
        n = len(pts)
        for i in range(n):
            ax, ay, anx, any_ = pts[i]
            bx, by, bnx, bny = pts[(i + 1) % n]
            ia, ib = (ax - anx * width, ay - any_ * width, c), (bx - bnx * width, by - bny * width, c)
            v += [(ax, ay, c), (bx, by, c), ia, ia, (bx, by, c), ib]
        return v

    def circle(self, cx, cy, rad, c1, c2=None, feather=1.0):
        self.rrect(cx - rad, cy - rad, rad * 2, rad * 2, rad, c1, c2, feather)

    def _make_blob(self):
        """Mancha de luz branca numa textura, desenhada uma vez; a cor vem do color mod."""
        size = 128
        tex = SDL_CreateTexture(self.r, PIXELFORMAT_ABGR8888, TEXTUREACCESS_TARGET, size, size)
        if not tex:
            return None
        SDL_SetTextureBlendMode(tex, BLEND)
        SDL_SetRenderTarget(self.r, tex)
        SDL_SetRenderDrawColor(self.r, 255, 255, 255, 0)
        SDL_RenderClear(self.r)
        seg, c, c0, m = 48, (255, 255, 255, 255), (255, 255, 255, 0), size / 2
        v = []
        for i in range(seg):  # em anéis, para o degradê sair suave
            a, b = 2 * math.pi * i / seg, 2 * math.pi * (i + 1) / seg
            for k in range(4):
                r0, r1 = m * k / 4, m * (k + 1) / 4
                a0, a1 = (1 - k / 4) ** 2, (1 - (k + 1) / 4) ** 2
                p = [(m + math.cos(t) * rr, m + math.sin(t) * rr) for t, rr in ((a, r0), (b, r0), (a, r1), (b, r1))]
                ca, cb = alpha(c, 255 * a0), alpha(c, 255 * a1)
                v += [(*p[0], ca), (*p[1], ca), (*p[2], cb), (*p[2], cb), (*p[1], ca), (*p[3], cb)]
        self.tris(v)
        SDL_SetRenderTarget(self.r, None)
        SDL_SetRenderDrawBlendMode(self.r, BLEND)
        return tex

    def blob(self, cx, cy, rad, c):
        """Mancha de luz: centro com alfa de c, some até a borda."""
        if not self.blob_tex:
            return
        SDL_SetTextureColorMod(self.blob_tex, int(c[0]), int(c[1]), int(c[2]))
        SDL_SetTextureAlphaMod(self.blob_tex, int(c[3]))
        SDL_RenderCopyF(self.r, self.blob_tex, None, C.byref(FRect(cx - rad, cy - rad, rad * 2, rad * 2)))

    def arc(self, cx, cy, rad, width, a0, a1, c):
        seg = max(6, int(abs(a1 - a0) / 8))
        v = []
        for i in range(seg):
            a = math.radians(a0 + (a1 - a0) * i / seg)
            b = math.radians(a0 + (a1 - a0) * (i + 1) / seg)
            # cauda que some: alfa cresce ao longo do arco
            ca, cb = alpha(c, c[3] * i / seg), alpha(c, c[3] * (i + 1) / seg)
            o1, o2 = (cx + math.cos(a) * rad, cy + math.sin(a) * rad), (cx + math.cos(b) * rad, cy + math.sin(b) * rad)
            i1 = (cx + math.cos(a) * (rad - width), cy + math.sin(a) * (rad - width))
            i2 = (cx + math.cos(b) * (rad - width), cy + math.sin(b) * (rad - width))
            v += [(*o1, ca), (*o2, cb), (*i1, ca), (*i1, ca), (*o2, cb), (*i2, cb)]
        self.tris(v)

    def chevron(self, cx, cy, size, c, left=False):
        """Seta cheia (triângulo) apontando para a direita ou esquerda."""
        d = -1 if left else 1
        self.tris([(cx - d * size * 0.45, cy - size * 0.6, c), (cx + d * size * 0.55, cy, c),
                   (cx - d * size * 0.45, cy + size * 0.6, c)])

    def vgradient(self, c1, c2):
        self.cached(("bg", c1, c2), lambda: [(0, 0, c1), (W, 0, c1), (0, H, c2), (0, H, c2), (W, 0, c1), (W, H, c2)])

    def clip(self, x=None, y=0, w=0, h=0):
        SDL_RenderSetClipRect(self.r, None if x is None else C.byref(Rect(int(x), int(y), int(w), int(h))))

    # --- texto ---

    def font(self, weight, size):
        key = (weight, size)
        if key not in self.fonts:
            path = os.path.join(HERE, "assets", "fonts", f"Poppins-{weight}.ttf")
            self.fonts[key] = TTF_OpenFont(path.encode(), size)
        return self.fonts[key]

    def _text_tex(self, font, text):
        key = (font, text)
        hit = self.text_cache.get(key)
        if hit:
            return hit
        surf = TTF_RenderUTF8_Blended(font, text.encode(), Color(255, 255, 255, 255))
        if not surf:
            return None
        tex = SDL_CreateTextureFromSurface(self.r, surf)
        SDL_FreeSurface(surf)
        w, h = C.c_int(), C.c_int()
        SDL_QueryTexture(tex, None, None, C.byref(w), C.byref(h))
        SDL_SetTextureBlendMode(tex, BLEND)
        if len(self.text_cache) > 600:
            for t, _, _ in self.text_cache.values():
                SDL_DestroyTexture(t)
            self.text_cache.clear()
        self.text_cache[key] = (tex, w.value, h.value)
        return self.text_cache[key]

    def measure(self, weight, size, text):
        w, h = C.c_int(), C.c_int()
        TTF_SizeUTF8(self.font(weight, size), text.encode(), C.byref(w), C.byref(h))
        return w.value, h.value

    def text(self, weight, size, s, x, y, c=(255, 255, 255, 255), align="l", valign="t"):
        if not s:
            return 0
        t = self._text_tex(self.font(weight, size), s)
        if not t:
            return 0
        tex, w, h = t
        if align == "c":
            x -= w / 2
        elif align == "r":
            x -= w
        if valign == "m":
            y -= h / 2
        SDL_SetTextureColorMod(tex, int(c[0]), int(c[1]), int(c[2]))
        SDL_SetTextureAlphaMod(tex, int(max(0, min(255, c[3]))))
        SDL_RenderCopyF(self.r, tex, None, C.byref(FRect(x, y, w, h)))
        return w

    def wrap(self, weight, size, s, width):
        key = (weight, size, s, width)
        hit = self.wcache.get(key)
        if hit is None:
            if len(self.wcache) > 500:
                self.wcache.clear()
            hit = self.wcache[key] = self._wrap(weight, size, s, width)
        return hit

    def _wrap(self, weight, size, s, width):
        lines = []
        for para in s.split("\n"):
            cur = ""
            for word in para.split(" "):
                cand = f"{cur} {word}".strip()
                if cur and self.measure(weight, size, cand)[0] > width:
                    lines.append(cur)
                    cur = word
                else:
                    cur = cand
            lines.append(cur)
        return lines

    # --- ícones ---

    def icon(self, name, x, y, size, c=(255, 255, 255, 255)):
        tex = self.icons.get(name)
        if tex is None:
            surf = IMG_Load(os.path.join(HERE, "assets", "icons", f"{name}.png").encode())
            tex = SDL_CreateTextureFromSurface(self.r, surf) if surf else 0
            if surf:
                SDL_FreeSurface(surf)
                SDL_SetTextureBlendMode(tex, BLEND)
            self.icons[name] = tex
        if not tex:
            return
        SDL_SetTextureColorMod(tex, int(c[0]), int(c[1]), int(c[2]))
        SDL_SetTextureAlphaMod(tex, int(max(0, min(255, c[3]))))
        SDL_RenderCopyF(self.r, tex, None, C.byref(FRect(x, y, size, size)))

    def image(self, name, x, y, size, smooth=False, a=255):
        """PNG de assets/ (sem tingir), quadrado de `size` px; sem suavizar por padrão (QR code)."""
        key = ("img", name, smooth)
        tex = self.icons.get(key)
        if tex is None:
            SDL_SetHint(b"SDL_RENDER_SCALE_QUALITY", b"1" if smooth else b"0")
            surf = IMG_Load(os.path.join(HERE, "assets", f"{name}.png").encode())
            tex = SDL_CreateTextureFromSurface(self.r, surf) if surf else 0
            if surf:
                SDL_FreeSurface(surf)
            SDL_SetHint(b"SDL_RENDER_SCALE_QUALITY", b"1")
            self.icons[key] = tex
        if tex:
            SDL_SetTextureAlphaMod(tex, int(max(0, min(255, a))))
            SDL_RenderCopyF(self.r, tex, None, C.byref(FRect(x, y, size, size)))

    # --- camadas (transições) ---

    def picture(self, path, x, y, w, h, a=255):
        """Imagem de qualquer pasta (capa de jogo), encaixada em w x h sem distorcer.
        Guarda poucas: capas são grandes e a memória do R36S é curta."""
        pics = self.__dict__.setdefault("pics", {})
        hit = pics.get(path)
        if hit is None:
            if len(pics) >= 6:
                old = next(iter(pics))
                if pics[old][0]:
                    SDL_DestroyTexture(pics[old][0])
                del pics[old]
            SDL_SetHint(b"SDL_RENDER_SCALE_QUALITY", b"1")
            surf = IMG_Load(path.encode())
            tex = SDL_CreateTextureFromSurface(self.r, surf) if surf else 0
            if surf:
                SDL_FreeSurface(surf)
            tw, th = C.c_int(0), C.c_int(0)
            if tex:
                SDL_QueryTexture(tex, None, None, C.byref(tw), C.byref(th))
            hit = pics[path] = (tex, tw.value, th.value)
        tex, tw, th = hit
        if not tex or not tw or not th:
            return False
        k = min(w / tw, h / th)
        dw, dh = tw * k, th * k
        SDL_SetTextureAlphaMod(tex, int(max(0, min(255, a))))
        SDL_RenderCopyF(self.r, tex, None, C.byref(FRect(x + (w - dw) / 2, y + (h - dh) / 2, dw, dh)))
        return True

    def flush(self):
        """Esquece geometria e sprites (troca de tema: as cores mudaram)."""
        for t in self.sprites.values():
            SDL_DestroyTexture(t)
        self.sprites.clear()
        self.vcache.clear()

    def sprite(self, key, w, h, pad, draw, x, y, a=255):
        """Desenha formas uma vez numa textura e depois só a copia para (x, y).
        Para o que se move ou pulsa: geometria nova a cada quadro custa caro
        no Python do R36S, já mover uma textura é de graça para a GPU."""
        tex = self.sprites.get(key)
        if tex is None:
            if len(self.sprites) > 150:
                for t in self.sprites.values():
                    SDL_DestroyTexture(t)
                self.sprites.clear()
            tw, th = int(w + 2 * pad + 1), int(h + 2 * pad + 1)
            tex = SDL_CreateTexture(self.r, PIXELFORMAT_ABGR8888, TEXTUREACCESS_TARGET, tw, th)
            SDL_SetTextureBlendMode(tex, BLEND)
            prev = SDL_GetRenderTarget(self.r)
            SDL_SetRenderTarget(self.r, tex)
            SDL_SetRenderDrawColor(self.r, 0, 0, 0, 0)
            SDL_RenderClear(self.r)
            draw(pad, pad)
            SDL_SetRenderTarget(self.r, prev)
            self.sprites[key] = tex
        SDL_SetTextureAlphaMod(tex, int(max(0, min(255, a))))
        SDL_RenderCopyF(self.r, tex, None, C.byref(FRect(x - pad, y - pad, int(w + 2 * pad + 1), int(h + 2 * pad + 1))))

    def layer(self, name):
        """Textura do tamanho da tela para desenhar uma tela inteira e misturar depois."""
        key = ("layer", name)
        tex = self.icons.get(key)
        if tex is None:
            tex = SDL_CreateTexture(self.r, PIXELFORMAT_ABGR8888, TEXTUREACCESS_TARGET, W, H)
            SDL_SetTextureBlendMode(tex, BLEND)
            self.icons[key] = tex
        return tex

    def begin_layer(self, tex):
        SDL_SetRenderTarget(self.r, tex)
        SDL_SetRenderDrawColor(self.r, 0, 0, 0, 0)
        SDL_RenderClear(self.r)

    def end_layer(self):
        SDL_SetRenderTarget(self.r, None)

    def draw_layer(self, tex, x, a):
        SDL_SetTextureAlphaMod(tex, int(max(0, min(255, a))))
        SDL_RenderCopyF(self.r, tex, None, C.byref(FRect(x, 0, W, H)))

    # --- quadro ---

    def clear(self):
        SDL_SetRenderDrawColor(self.r, 0, 0, 0, 255)
        SDL_RenderClear(self.r)

    def present(self):
        SDL_RenderPresent(self.r)

    def screenshot(self, path):
        buf = C.create_string_buffer(W * H * 3)
        SDL_RenderReadPixels(self.r, None, PIXELFORMAT_RGB24, buf, W * 3)
        with open(path, "wb") as f:
            f.write(b"P6\n%d %d\n255\n" % (W, H) + buf.raw)
