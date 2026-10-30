"""Tela de boas-vindas do boot com o nome do jogador.

A base (boas-vindas-base.raw, gerada no PC pelo telas/gerar_telas.py) já tem o cartão de sessão
vazio; aqui entram a inicial e o nome (centrado na altura do cartão), com a SDL2_ttf (sem PIL no console). O
resultado vai para ~/.config/omni36os/boas-vindas.raw, que o omni36os-tela prefere à tela padrão.
Pixels crus BGRA 640x480, iguais aos do framebuffer.
"""
import ctypes as C
import os

import gfx

W, H = 640, 480
BASE = os.environ.get("OMNI_TELA_BASE") or "/opt/omni36os-telas/boas-vindas-base.raw"
CARTAO = (190, 370)                     # canto do cartão de sessão, o mesmo do gerar_telas.py
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
    x0, y0 = CARTAO
    _put(buf, _font(16), nome[0].upper(), x0 + 26, y0 + 25, ESCURO, center=True)
    _put(buf, _font(16), nome, x0 + 56, y0 + 25, TEXT, vcenter=True)
    with open(dest, "wb") as f:
        f.write(buf)
    return dest
