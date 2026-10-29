"""Janelas do Omni36OS para os scripts do Omni36OS: substitui dialog, msgbox e osk.

Os scripts de /opt/system chamam `dialog --menu ...`, `msgbox "..."` e
`osk "..."`. O run_tool.sh monta este programa por cima deles só dentro do
namespace do script (mount --bind num unshare -m): o sistema não muda e, fora
do script, o dialog de verdade continua lá.

Compatível com o que os scripts usam: --msgbox --infobox --yesno --menu
--radiolist --checklist --inputbox --passwordbox --gauge --textbox
--progressbox --pause e as opções de título e botões. O resultado vai para o
stderr (ou stdout com --stdout), e o código de saída é o do dialog:
0 OK/Sim, 1 Cancelar/Não, 2 Ajuda, 3 Extra, 255 Esc. Qualquer outra coisa
cai no dialog original (/tmp/omni36os-dialog.real).
"""
import os
import re
import select
import signal
import sys
import time

REAL_DIALOG = "/tmp/omni36os-dialog.real"
HOLDER = "/tmp/omni36os-dialog-holder.pid"
HERE = os.path.dirname(os.path.abspath(__file__))
W, H = 640, 480

WIDGETS = {"--msgbox", "--infobox", "--yesno", "--menu", "--radiolist", "--checklist", "--inputbox",
           "--passwordbox", "--gauge", "--textbox", "--progressbox", "--pause", "--programbox"}
WITH_ARG = {"--backtitle", "--title", "--cancel-label", "--ok-label", "--yes-label", "--no-label",
            "--extra-label", "--help-label", "--default-item", "--exit-label", "--default-button",
            "--timeout", "--hline", "--column-separator", "--output-separator", "--sleep", "--item-help-label"}
WITH_TWO = {"--begin"}


def release_holder():
    """Fecha a janela de "infobox" que ficou na tela esperando a próxima."""
    try:
        pid = int(open(HOLDER).read())
        os.kill(pid, signal.SIGTERM)
        for _ in range(40):
            os.kill(pid, 0)
            time.sleep(0.05)
    except (OSError, ValueError):
        pass


def parse(argv):
    o = {"ok": "OK", "cancel": "Cancelar", "yes": "Sim", "no": "Não", "extra": None, "help": None,
         "title": "", "backtitle": "", "default": None, "stdout": False, "separate": False, "nocancel": False,
         "widget": None, "args": [], "timeout": 0, "defaultno": False}
    i = 0
    while i < len(argv):
        a = argv[i]
        if a in WIDGETS and o["widget"] is None:
            o["widget"] = a[2:]
            o["args"] = argv[i + 1:]
            break
        if a == "--and-widget":
            return None                       # vários widgets numa chamada: deixa com o dialog original
        key = {"--ok-label": "ok", "--cancel-label": "cancel", "--yes-label": "yes", "--no-label": "no",
               "--extra-label": "extra", "--help-label": "help", "--title": "title", "--backtitle": "backtitle",
               "--default-item": "default", "--exit-label": "ok"}.get(a)
        if key:
            o[key] = argv[i + 1] if i + 1 < len(argv) else ""
            i += 2
            continue
        if a == "--timeout":
            o["timeout"] = int(argv[i + 1]) if i + 1 < len(argv) and argv[i + 1].isdigit() else 0
            i += 2
            continue
        if a in WITH_ARG:
            i += 2
            continue
        if a in WITH_TWO:
            i += 3
            continue
        o["stdout"] |= a == "--stdout"
        o["separate"] |= a == "--separate-output"
        o["nocancel"] |= a in ("--no-cancel", "--nocancel")
        o["defaultno"] |= a == "--defaultno"
        if a == "--extra-button" and not o["extra"]:
            o["extra"] = "Extra"
        if a == "--help-button" and not o["help"]:
            o["help"] = "Ajuda"
        i += 1
    if o["widget"] is None:
        return None
    return o


def clean(text):
    text = text.replace("\\n", "\n")
    text = re.sub(r"\\Z[0-9bBuUrRn]", "", text)                 # cores do --colors
    text = re.sub(r"\x1b\[[0-9;]*[A-Za-z]", "", text)           # cores ANSI
    return text


class Win:
    """A janela: mesmo fundo, fontes e tema do Omni36OS."""

    def __init__(self):
        sys.path.insert(0, HERE)
        import gfx
        from omni_theme import THEMES
        self.gfx = gfx
        theme = "escuro"
        try:
            theme = open(os.path.expanduser("~ark/.config/omni36os/tema")).read().strip()
        except OSError:
            pass
        t = THEMES.get(theme, THEMES["escuro"])
        hx = gfx.hexc
        self.BG1, self.BG2 = hx(t["BG_TOP"]), hx(t["BG_BOT"])
        self.TEXT, self.MUTED, self.FAINT = hx(t["TEXT"]), hx(t["MUTED"]), hx(t["FAINT"])
        self.INK = hx(t["INK"])[:3]
        self.PANEL1, self.PANEL2 = hx(t["MODAL_A"]), hx(t["MODAL_B"])
        self.A1, self.A2 = hx("60a5fa"), hx("a78bfa")
        self.g = gfx.Gfx("Omni36OS")
        self.swap = False
        self.held = {}

    def ink(self, a):
        return (*self.INK, a)

    def events(self):
        """Comandos do controle (o teclado é ignorado: o gptokeyb do script também gera teclas)."""
        out = []
        import ctypes as C
        ev = (C.c_uint8 * 64)()
        now = time.monotonic()
        while self.gfx.SDL_PollEvent(ev):
            typ = int.from_bytes(bytes(ev[0:4]), "little")
            if typ == 0x100:          # SDL_QUIT (o SDL troca o SIGTERM por este evento): sai como Esc
                os._exit(255)
            if typ == 0x653:
                self.gfx.SDL_GameControllerOpen(int.from_bytes(bytes(ev[8:12]), "little", signed=True))
            elif typ in (0x651, 0x652):
                b, down = ev[12], typ == 0x651
                dpad = {11: "up", 12: "down", 13: "left", 14: "right"}
                if b in dpad:
                    if down:
                        out.append(dpad[b])
                        self.held[dpad[b]] = now + 0.35
                    else:
                        self.held.pop(dpad[b], None)
                elif down:
                    out.append({0: "ok", 1: "back", 2: "x", 3: "y", 9: "l1", 10: "r1", 6: "start",
                                4: "select"}.get(b, ""))
            elif typ == 0x650:
                axis, val = ev[12], int.from_bytes(bytes(ev[16:18]), "little", signed=True)
                if axis in (0, 1):
                    neg, pos = ("left", "right") if axis == 0 else ("up", "down")
                    for d, on in ((neg, val < -20000), (pos, val > 20000)):
                        if on and d not in self.held:
                            out.append(d)
                            self.held[d] = now + 0.35
                        elif not on and d in self.held and d not in ("up", "down", "left", "right"):
                            pass
                        elif not on:
                            self.held.pop(d, None)
        for d, nxt in list(self.held.items()):
            if now >= nxt:
                out.append(d)
                self.held[d] = now + 0.09
        return [c for c in out if c]

    # --- desenho ---

    def frame_start(self, title, backtitle):
        g = self.g
        g.clear()
        g.vgradient(self.BG1, self.BG2)
        g.image("logo-64", 22, 16, 26, smooth=True)
        g.text("Bold", 16, "Omni36OS", 56, 18, self.TEXT)
        if backtitle:
            bt = clean(backtitle).strip()
            while g.measure("Regular", 11, bt)[0] > W - 200 and len(bt) > 8:
                bt = bt[:-2]
            g.text("Regular", 11, bt, W - 22, 22, self.MUTED, "r")
        return title

    def panel(self, title, top=64, bottom=H - 20):
        g = self.g
        mx, my, mw, mh = 24, top, W - 48, bottom - top
        g.rrect(mx, my, mw, mh, 22, self.PANEL1, self.PANEL2)
        g.stroke(mx, my, mw, mh, 22, self.ink(25))
        y = my + 18
        if title:
            t = clean(title).strip()
            g.rrect(mx + 20, my + 16, 30, 30, 10, self.A1, self.A2)
            g.icon("adjustments", mx + 26, my + 22, 18, (255, 255, 255, 255))
            g.text("Bold", 17, t[:48], mx + 62, my + 20, self.TEXT)
            y = my + 60
        return mx, my, mw, mh, y

    def buttons(self, labels, sel, mx, my, mw, mh):
        g = self.g
        n = len(labels)
        bw = (mw - 40 - 12 * (n - 1)) / n
        by = my + mh - 54
        for k, lab in enumerate(labels):
            bx = mx + 20 + k * (bw + 12)
            if k == sel:
                g.rrect(bx, by, bw, 38, 14, self.A1, self.A2)
            else:
                g.rrect(bx, by, bw, 38, 14, self.ink(22))
            g.text("SemiBold", 13, lab, bx + bw / 2, by + 19.5,
                   (255, 255, 255, 255) if k == sel else self.TEXT, "c", "m")
        return by

    def text_block(self, text, x, y, w, maxy, top=0, size=13):
        g = self.g
        lines = []
        for para in clean(text).split("\n"):
            lines += g.wrap("Regular", size, para, w) if para.strip() else [""]
        vis = int((maxy - y) // (size + 6))
        for k, line in enumerate(lines[top:top + vis]):
            g.text("Regular", size, line, x, y + k * (size + 6), self.TEXT)
        return len(lines), vis

    def present(self):
        shot = os.environ.get("OMNI_DIALOG_SHOT")      # testes: salva o 5º quadro e sai
        self.frames = getattr(self, "frames", 0) + 1
        if shot and self.frames == 5:
            self.g.screenshot(shot)
            os._exit(254)
        self.g.present()
        time.sleep(1 / 30)


# --- widgets ---

def button_set(o, kind):
    if kind == "yesno":
        labs = [o["yes"], o["no"]]
        codes = [0, 1]
    else:
        labs, codes = [o["ok"]], [0]
        if o["extra"]:
            labs.append(o["extra"])
            codes.append(3)
        if kind != "msg" and not o["nocancel"]:
            labs.append(o["cancel"])
            codes.append(1)
    if o["help"]:
        labs.append(o["help"])
        codes.append(2)
    return labs, codes


def run_message(w, o, text, kind):
    labs, codes = button_set(o, kind)
    sel = 1 if kind == "yesno" and o["defaultno"] else 0
    top = 0
    deadline = time.monotonic() + o["timeout"] if o["timeout"] else None
    while True:
        for c in w.events():
            if c in ("left", "right"):
                sel = (sel + (1 if c == "right" else -1)) % len(labs)
            elif c == "up":
                top = max(0, top - 1)
            elif c == "down":
                top += 1
            elif c == "ok":
                return codes[sel], ""
            elif c == "back":
                return (1 if kind == "yesno" else 0 if kind == "msg" else 1), ""
        if deadline and time.monotonic() > deadline:
            return 0, ""
        w.frame_start(o["title"], o["backtitle"])
        mx, my, mw, mh, y = w.panel(o["title"])
        n, vis = w.text_block(text, mx + 24, y, mw - 48, my + mh - 70, top)
        top = min(top, max(0, n - vis))
        w.buttons(labs, sel, mx, my, mw, mh)
        w.present()


def run_info(w, o, text, hold):
    """infobox: desenha e sai; um filho segura a imagem até a próxima janela (máx. 20 s)."""
    w.frame_start(o["title"], o["backtitle"])
    mx, my, mw, mh, y = w.panel(o["title"], top=150, bottom=330)
    w.text_block(text, mx + 24, y, mw - 48, my + mh - 16)
    w.g.present()
    if not hold:
        return 0, ""
    if os.fork() == 0:              # filho: mantém a janela até alguém pedir
        os.setsid()
        open(HOLDER, "w").write(str(os.getpid()))
        signal.signal(signal.SIGTERM, lambda *_: os._exit(0))
        time.sleep(20)              # só segura a tela (sem desenhar: GPU depois de fork é arriscado)
        os._exit(0)
    return 0, ""


def parse_items(args, per):
    items = []
    for k in range(0, len(args) - per + 1, per):
        items.append(args[k:k + per])
    return items


def run_list(w, o, text, items, mode):
    """menu (tag, item), radiolist/checklist (tag, item, on/off)."""
    if not items:
        return 1, ""
    on = [len(it) > 2 and it[2].lower() in ("on", "1", "yes") for it in items]
    sel = 0
    if o["default"] is not None:
        sel = next((k for k, it in enumerate(items) if it[0] == o["default"]), 0)
    elif mode == "radio" and any(on):
        sel = on.index(True)
    labs, codes = button_set(o, "list")
    bsel, top = 0, 0
    while True:
        for c in w.events():
            if c in ("up", "down"):
                sel = (sel + (1 if c == "down" else -1)) % len(items)
            elif c in ("l1", "r1"):
                sel = max(0, min(len(items) - 1, sel + (-6 if c == "l1" else 6)))
            elif c in ("left", "right"):
                bsel = (bsel + (1 if c == "right" else -1)) % len(labs)
            elif c in ("x", "y", "select") and mode in ("radio", "check"):
                if mode == "radio":
                    on = [k == sel for k in range(len(items))]
                else:
                    on[sel] = not on[sel]
            elif c == "ok":
                code = codes[bsel]
                if mode == "menu":
                    return code, items[sel][0] if code in (0, 3) else ""
                if mode == "radio":
                    if code == 0 and not any(on):
                        on = [k == sel for k in range(len(items))]
                    return code, next((it[0] for k, it in enumerate(items) if on[k]), "")
                if mode == "check" and code == 0 and labs[bsel] == o["ok"] and not any(on):
                    on[sel] = True
                tags = [it[0] for k, it in enumerate(items) if on[k]]
                return code, ("\n".join(tags) + "\n") if o["separate"] else " ".join(f'"{t}"' for t in tags)
            elif c == "back":
                return 1, ""
        g = w.g
        w.frame_start(o["title"], o["backtitle"])
        mx, my, mw, mh, y = w.panel(o["title"])
        if text.strip():
            n, _v = w.text_block(text, mx + 24, y, mw - 48, y + 44, 0, 12)
            y += min(2, n) * 18 + 6
        rh, ly, lb = 32, y, my + mh - 64
        vis = max(1, int((lb - ly) // rh))
        top = min(max(top, sel - vis + 1), sel)
        g.clip(mx + 10, ly, mw - 20, lb - ly)
        for k in range(top, min(len(items), top + vis)):
            it = items[k]
            yy = ly + (k - top) * rh
            cur = k == sel
            if cur:
                g.rrect(mx + 16, yy, mw - 32, rh - 4, 10, w.A1, w.A2)
            x = mx + 28
            if mode in ("radio", "check"):
                box = None
                if mode == "check":
                    g.rrect(x, yy + 7, 14, 14, 4, w.ink(60) if not on[k] else (255, 255, 255, 230))
                    if on[k]:
                        g.rrect(x + 3, yy + 10, 8, 8, 2, w.A2)
                else:
                    g.circle(x + 7, yy + 14, 7, w.ink(60) if not on[k] else (255, 255, 255, 230))
                    if on[k]:
                        g.circle(x + 7, yy + 14, 3.5, w.A2)
                x += 24
            label = clean(it[1] if len(it) > 1 and it[1].strip() else it[0])
            tag = clean(it[0]) if len(it) > 1 and it[1].strip() and not re.fullmatch(r"\d+\)?|[A-Z]\)?", it[0]) \
                else ""
            if tag and len(tag) < 18:
                g.text("SemiBold", 13, tag, x, yy + 6, (255, 255, 255, 220) if cur else w.MUTED)
                x += max(60, g.measure("SemiBold", 13, tag)[0] + 14)
            while g.measure("Regular", 13, label)[0] > mx + mw - 30 - x and len(label) > 4:
                label = label[:-2]
            g.text("SemiBold" if cur else "Regular", 13, label, x, yy + 6, (255, 255, 255, 255) if cur else w.TEXT)
        g.clip()
        if mode in ("radio", "check"):
            g.text("Regular", 11, "X / Y: marcar", mx + mw - 24, lb + 2, w.FAINT, "r")
        w.buttons(labs, bsel, mx, my, mw, mh)
        w.present()


KEYS = ["1234567890", "qwertyuiop", "asdfghjkl@", "zxcvbnm.-_"]


def run_osk(w, o, prompt, init="", password=False):
    """Teclado na tela: direcional escolhe, A digita, B apaga, X espaço, Y maiúsculas, START confirma."""
    text, r, c, upper = init, 1, 0, False
    extra = ["Espaço", "Apagar", "Maiúsc.", "OK", "Cancelar"]
    while True:
        for cmd in w.events():
            rows = len(KEYS) + 1
            if cmd in ("up", "down"):
                r = (r + (1 if cmd == "down" else -1)) % rows
                c = min(c, (len(extra) if r == len(KEYS) else len(KEYS[r])) - 1)
            elif cmd in ("left", "right"):
                n = len(extra) if r == len(KEYS) else len(KEYS[r])
                c = (c + (1 if cmd == "right" else -1)) % n
            elif cmd == "back":
                text = text[:-1]
            elif cmd == "x":
                text += " "
            elif cmd == "y":
                upper = not upper
            elif cmd == "start":
                return 0, text
            elif cmd == "select":
                return 1, ""
            elif cmd == "ok":
                if r < len(KEYS):
                    ch = KEYS[r][c]
                    text += ch.upper() if upper else ch
                else:
                    act = extra[c]
                    if act == "Espaço":
                        text += " "
                    elif act == "Apagar":
                        text = text[:-1]
                    elif act == "Maiúsc.":
                        upper = not upper
                    elif act == "OK":
                        return 0, text
                    else:
                        return 1, ""
        g = w.g
        w.frame_start(o["title"], o["backtitle"])
        mx, my, mw, mh, y = w.panel(o["title"] or "Digite")
        y2 = y
        if prompt.strip():
            n, _v = w.text_block(prompt, mx + 24, y, mw - 48, y + 40, 0, 12)
            y2 = y + min(2, n) * 18 + 4
        g.rrect(mx + 20, y2, mw - 40, 34, 10, w.ink(20))
        shown = ("•" * len(text)) if password else text
        g.text("SemiBold", 15, shown[-40:] + "_", mx + 32, y2 + 8, w.TEXT)
        ky = y2 + 46
        kw, kh = (mw - 40) / 10, 34
        for rr, row in enumerate(KEYS):
            for cc, ch in enumerate(row):
                x = mx + 20 + cc * kw
                yy = ky + rr * (kh + 4)
                cur = rr == r and cc == c
                g.rrect(x + 2, yy, kw - 4, kh, 8, (w.A1 if cur else w.ink(22)), (w.A2 if cur else w.ink(22)))
                g.text("SemiBold", 14, ch.upper() if upper else ch, x + kw / 2, yy + kh / 2,
                       (255, 255, 255, 255) if cur else w.TEXT, "c", "m")
        yy = ky + len(KEYS) * (kh + 4)
        ew = (mw - 40) / len(extra)
        for cc, lab in enumerate(extra):
            x = mx + 20 + cc * ew
            cur = r == len(KEYS) and cc == c
            g.rrect(x + 2, yy, ew - 4, kh, 8, (w.A1 if cur else w.ink(22)), (w.A2 if cur else w.ink(22)))
            g.text("SemiBold", 12, lab, x + ew / 2, yy + kh / 2, (255, 255, 255, 255) if cur else w.TEXT, "c", "m")
        g.text("Regular", 11, "A digita · B apaga · X espaço · Y maiúsculas · START confirma · SELECT cancela",
               W / 2, my + mh - 18, w.FAINT, "c")
        w.present()


def run_stream(w, o, text, kind):
    """gauge (porcentagem pelo stdin) e progressbox (texto pelo stdin), até o stdin fechar."""
    pct, lines, buf = 0, [], ""
    msg = text
    fd = sys.stdin.fileno()
    xxx, block = False, []
    while True:
        r, _, _ = select.select([fd], [], [], 0.05)
        if r:
            chunk = os.read(fd, 4096)
            if not chunk:
                break
            buf += chunk.decode(errors="ignore")
            while "\n" in buf:
                line, buf = buf.split("\n", 1)
                s = line.strip()
                if kind == "gauge":
                    if s == "XXX":
                        if xxx and block:
                            if block[0].isdigit():
                                pct = int(block[0])
                            msg = "\n".join(block[1:]) or msg
                        xxx, block = not xxx, []
                    elif xxx:
                        block.append(line)
                    elif s.isdigit():
                        pct = int(s)
                else:
                    lines.append(clean(line))
                    lines = lines[-200:]
        w.events()
        g = w.g
        w.frame_start(o["title"], o["backtitle"])
        if kind == "gauge":
            mx, my, mw, mh, y = w.panel(o["title"], top=140, bottom=340)
            w.text_block(msg, mx + 24, y, mw - 48, my + mh - 50)
            bx, by, bw = mx + 24, my + mh - 40, mw - 48
            g.rrect(bx, by, bw, 10, 5, w.ink(30))
            g.rrect(bx, by, max(10, bw * min(100, pct) / 100), 10, 5, w.A1, w.A2)
            g.text("SemiBold", 12, f"{pct}%", bx + bw, by - 18, w.MUTED, "r")
        else:
            mx, my, mw, mh, y = w.panel(o["title"])
            if text.strip():
                g.text("Regular", 12, clean(text).split("\n")[0][:70], mx + 24, y, w.MUTED)
                y += 22
            vis = int((my + mh - 20 - y) // 17)
            for k, line in enumerate(lines[-vis:]):
                g.text("Regular", 12, line[:90], mx + 24, y + k * 17, w.TEXT)
        w.present()
    return 0, ""


def run_textbox(w, o, path):
    try:
        text = open(path, errors="ignore").read()
    except OSError:
        text = f"(não consegui abrir {path})"
    return run_message(w, o, text, "msg")


def dialog_main(argv):
    o = parse(argv)
    if o is None:
        os.execv(REAL_DIALOG, [REAL_DIALOG] + argv)
    a = o["args"]
    text = a[0] if a else ""
    release_holder()
    w = Win()
    kind = o["widget"]
    if kind == "msgbox":
        return run_message(w, o, text, "msg")
    if kind == "yesno":
        return run_message(w, o, text, "yesno")
    if kind == "pause":
        o["timeout"] = int(a[3]) if len(a) > 3 and a[3].isdigit() else 0
        return run_message(w, o, text, "msg")
    if kind == "infobox":
        return run_info(w, o, text, hold=True)
    if kind == "menu":
        return run_list(w, o, text, parse_items(a[4:], 2), "menu")
    if kind in ("radiolist", "checklist"):
        return run_list(w, o, text, parse_items(a[4:], 3), "radio" if kind == "radiolist" else "check")
    if kind in ("inputbox", "passwordbox"):
        return run_osk(w, o, text, a[3] if len(a) > 3 else "", kind == "passwordbox")
    if kind == "gauge":
        return run_stream(w, o, text, "gauge")
    if kind in ("progressbox", "programbox"):
        return run_stream(w, o, text if len(a) > 2 else "", "progress")
    if kind == "textbox":
        return run_textbox(w, o, text)
    os.execv(REAL_DIALOG, [REAL_DIALOG] + argv)


def main():
    prog = os.path.basename(sys.argv[0])
    mode = os.environ.get("OMNI_DIALOG_AS") or prog
    # o resultado vai para o fd original; o SDL e o librga escrevem no stdout/stderr e sujariam a resposta
    out_fd, err_fd = os.dup(1), os.dup(2)
    devnull = os.open(os.devnull, os.O_WRONLY)
    os.dup2(devnull, 1)
    os.dup2(devnull, 2)
    argv = sys.argv[1:]
    if mode == "msgbox":
        release_holder()
        code, res = run_message(Win(), parse(["--msgbox"] + argv[:1]) or {}, argv[0] if argv else "", "msg")
        res = ""
        fd = out_fd
    elif mode == "osk":
        release_holder()
        o = parse(["--inputbox", argv[0] if argv else "", "0", "0"])
        code, res = run_osk(Win(), o, argv[0] if argv else "")
        res += "\n"
        fd = out_fd
    else:
        code, res = dialog_main(argv)
        o = parse(argv)
        fd = out_fd if o and o["stdout"] else err_fd
    if res:
        os.write(fd, res.encode())
    os._exit(code if code is not None else 0)


if __name__ == "__main__":
    main()
