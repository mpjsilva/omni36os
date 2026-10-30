"""Tela de boas-vindas do boot com o nome do jogador.

A base (boas-vindas-base.raw, gerada no PC pelo telas/gerar_telas.py) não tem o cartão de sessão;
aqui entra o cartão do tamanho do nome (pílula centrada, com a inicial num círculo), com a SDL2_ttf (sem PIL no console). O
resultado vai para ~/.config/omni36os/boas-vindas.raw, que o omni36os-tela prefere à tela padrão.
Pixels crus BGRA 640x480, iguais aos do framebuffer.
"""
import ctypes as C
import os

import gfx

W, H = 640, 480
BASE = os.environ.get("OMNI_TELA_BASE") or "/opt/omni36os-telas/boas-vindas-base.raw"
# cartão de sessão: as mesmas medidas e cores do gerar_telas.py (e da abertura do omni_ui.py)
CARTAO_Y, CARTAO_H, CARTAO_PAD = 370, 50, 22
PILL_FILL, PILL_LINE, CIANO = (0x1B, 0x1F, 0x42), (0x2A, 0x30, 0x60), (0x2D, 0xE2, 0xE6)
TEXT, ESCURO = (0xF4, 0xF6, 0xFF), (0x0B, 0x10, 0x24)


class Surface(C.Structure):
    _fields_ = [("flags", C.c_uint32), ("format", C.c_void_p), ("w", C.c_int), ("h", C.c_int),
                ("pitch", C.c_int), ("pixels", C.c_void_p)]


def _font(size):
    gfx.TTF_Init()
    return gfx.TTF_OpenFont(os.path.join(gfx.HERE, "assets", "fonts", "Poppins-SemiBold.ttf").encode(), size)


def _put(buf, font, text, x, y, cor, center=False, vcenter=False):
    """Mistura o texto (branco + alfa, ARGB8888) na cor `cor` sobre o buffer BGRA."""
    sp = gfx.TTF_RenderUTF8_Blended(font, text.encode(), gfx.Color(255, 255, 255, 255))
    if not sp:
        return
    s = Surface.from_address(sp)
    px = C.string_at(s.pixels, s.pitch * s.h)
    if center:
        x, y = x - s.w // 2, y - s.h // 2
    elif vcenter:
        y = y - s.h // 2
    for j in range(s.h):
        for i in range(s.w):
            a = px[j * s.pitch + i * 4 + 3]
            X, Y = x + i, y + j
            if a and 0 <= X < W and 0 <= Y < H:
                o = (Y * W + X) * 4
                for k, c in enumerate(reversed(cor)):       # B, G, R
                    buf[o + k] = (c * a + buf[o + k] * (255 - a)) // 255
    gfx.SDL_FreeSurface(sp)


def _blend(buf, X, Y, cor, a):
    if a <= 0 or not (0 <= X < W and 0 <= Y < H):
        return
    a = min(1.0, a)
    o = (Y * W + X) * 4
    for k, c in enumerate(reversed(cor)):                   # B, G, R
        buf[o + k] = int(c * a + buf[o + k] * (1 - a))


def _cartao(buf, x0, y0, w):
    """Pílula (raio = metade da altura) com contorno de 1 px e o círculo da inicial, com borda suave."""
    r = CARTAO_H / 2
    ay, ax1, ax2 = y0 + r, x0 + r, x0 + w - r                # eixo da pílula
    cx, cy, cr = x0 + 26, y0 + 25, 16
    for Y in range(y0 - 1, y0 + CARTAO_H + 1):
        for X in range(x0 - 1, x0 + w + 1):
            px, py = X + 0.5, Y + 0.5
            dx = px - min(max(px, ax1), ax2)
            dist = (dx * dx + (py - ay) ** 2) ** 0.5
            inside = r - dist + 0.5                          # cobertura da pílula
            if inside <= 0:
                continue
            _blend(buf, X, Y, PILL_FILL, inside)
            _blend(buf, X, Y, PILL_LINE, 1 - abs(dist - (r - 0.5)))
            dc = ((px - cx) ** 2 + (py - cy) ** 2) ** 0.5
            _blend(buf, X, Y, CIANO, cr - dc + 0.5)


def _text_w(font, text):
    w, h = C.c_int(0), C.c_int(0)
    gfx.TTF_SizeUTF8(font, text.encode(), C.byref(w), C.byref(h))
    return w.value


def boas_vindas(nome, dest):
    """Grava a tela com `nome` em `dest`; sem nome apaga, e volta a tela padrão ("Jogador")."""
    if not nome:
        try:
            os.remove(dest)
        except OSError:
            pass
        return None
    with open(BASE, "rb") as f:
        buf = bytearray(f.read())
    font = _font(16)
    w = 56 + _text_w(font, nome) + CARTAO_PAD
    x0, y0 = (W - w) // 2, CARTAO_Y
    _cartao(buf, x0, y0, w)
    _put(buf, font, nome[0].upper(), x0 + 26, y0 + 25, ESCURO, center=True)
    _put(buf, font, nome, x0 + 56, y0 + 25, TEXT, vcenter=True)
    with open(dest, "wb") as f:
        f.write(buf)
    return dest
