"""Teclado na tela do Omni36OS: a lógica, igual em todo o sistema (launcher e janelas dos scripts).

Funciona como o teclado do Google no Android:
- começa em maiúscula, e a letra seguinte volta para minúscula sozinha;
- depois de ". ", "! " ou "? " a próxima letra volta a ser maiúscula (início de frase);
- a tecla de maiúsculas: um toque deixa só a próxima letra maiúscula (ou desfaz a automática);
  dois toques seguidos travam (caps lock); mais um toque destrava;
- Y troca entre letras e símbolos; X é espaço (a trava das maiúsculas fica só na tecla da tela).
Senhas não ganham maiúscula automática.
A fileira de números fica sempre no topo; o desenho fica com quem usa (omni_ui e omni_dialog).
"""
import time

LETTERS = ["1234567890", "qwertyuiop", "asdfghjkl-", "zxcvbnm_.@"]
SYMBOLS = ["1234567890", "!?@#$%&*()", "+-=/\\:;'\"_", ",.<>[]{}~|"]
BOTTOM = ["shift", "espaço", "apagar", "OK"]
BOTTOM_TEXT = ["shift", "espaço", "Enter", "apagar", "OK"]    # texto de várias linhas (bloco de notas)
WEIGHT = {"shift": 1, "espaço": 3, "Enter": 1.5, "apagar": 1, "OK": 2}
DOUBLE = 0.45                    # segundos entre dois toques na tecla de maiúsculas para travar


class Teclado:
    def __init__(self, value="", secret=False, limit=64, multiline=False):
        self.value, self.secret, self.limit, self.multiline = value, secret, limit, multiline
        self.pos = len(value)        # onde o próximo caractere entra (no fim, a não ser que mude de linha)
        self.r, self.c = 1, 0
        self.symbols = False
        self.shift = "off"       # "off", "once" (só a próxima letra) ou "lock"
        self.shift_t = -9.0
        self.auto()

    # --- estado ---

    def auto(self):
        """Maiúscula automática no começo do campo e de cada frase (nunca em senha, nem travada)."""
        if self.shift == "lock":
            return
        v = self.value[:self.pos].rstrip(" ")
        start = not v.strip() or v.endswith("\n") or v != self.value[:self.pos] and v[-1:] in ".!?"
        self.shift = "once" if start and not self.secret else "off"

    def pages(self):
        return SYMBOLS if self.symbols else LETTERS

    def rows(self):
        """As linhas como aparecem agora (a última é a de baixo: maiúsculas, espaço, apagar, OK)."""
        up = self.shift != "off" and not self.symbols
        out = [list(row.upper() if up and r else row) for r, row in enumerate(self.pages())]
        return out + [BOTTOM_TEXT if self.multiline else BOTTOM]

    def widths(self, row, last, total, gap):
        """Larguras das teclas de uma linha (a última tem teclas largas)."""
        if not last:
            return [(total - gap * (len(row) - 1)) / len(row)] * len(row)
        unit = (total - gap * (len(row) - 1)) / sum(WEIGHT[k] for k in row)
        return [unit * WEIGHT[k] for k in row]

    def shift_label(self):
        if self.symbols:
            return "abc"
        return {"off": "abc", "once": "Abc", "lock": "ABC"}[self.shift]

    def label(self, key):
        return self.shift_label() if key == "shift" else key

    # --- teclas ---

    def type(self, ch):
        if len(self.value) >= self.limit:
            return
        self.value = self.value[:self.pos] + ch + self.value[self.pos:]
        self.pos += len(ch)
        if self.shift == "once":
            self.shift = "off"
        self.auto()

    def backspace(self):
        if self.pos:
            self.value = self.value[:self.pos - 1] + self.value[self.pos:]
            self.pos -= 1
        self.auto()

    def set_pos(self, pos):
        self.pos = max(0, min(len(self.value), pos))
        self.auto()

    def press_shift(self):
        if self.symbols:                  # nos símbolos, a tecla volta para as letras
            self.symbols = False
            return
        now = time.monotonic()
        if self.shift == "off":
            self.shift = "once"
        elif self.shift == "once":
            self.shift = "lock" if now - self.shift_t < DOUBLE else "off"
        else:
            self.shift = "off"
        self.shift_t = now

    def toggle_symbols(self):
        """Y: letras ⇄ símbolos (a fileira de números e a de baixo não mudam)."""
        self.symbols = not self.symbols

    def move(self, cmd):
        rows = self.rows()
        if cmd in ("up", "down"):
            old = len(rows[self.r])
            self.r = (self.r + (1 if cmd == "down" else -1)) % len(rows)
            new = len(rows[self.r])
            self.c = min(new - 1, round(self.c * (new - 1) / max(1, old - 1)))
        elif cmd in ("left", "right"):
            self.c = (self.c + (1 if cmd == "right" else -1)) % len(rows[self.r])

    def input(self, cmd):
        """Um botão. Devolve "ok" (confirmar), "cancel" ou None."""
        if cmd in ("up", "down", "left", "right"):
            self.move(cmd)
        elif cmd == "back":
            self.backspace()
        elif cmd == "y":
            self.toggle_symbols()
        elif cmd == "x":
            self.type(" ")
        elif cmd == "select":
            return "cancel"
        elif cmd == "start":
            return "ok"
        elif cmd == "ok":
            key = self.rows()[self.r][self.c]
            if key == "shift":
                self.press_shift()
            elif key == "espaço":
                self.type(" ")
            elif key == "Enter":
                self.type("\n")
            elif key == "apagar":
                self.backspace()
            elif key == "OK":
                return "ok"
            else:
                self.type(key)
        return None
