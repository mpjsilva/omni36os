"""Atalhos dentro dos jogos (Controles > Atalhos): o que existe, os botões padrão e os nomes.

Fonte única para o serviço (omni_atalho.py), o Omni36OS (omni_ui.py), o omni.py e o manual.
Os botões são códigos evdev do controle do R36S (rk3326-r36s-linux.dtb).
"""

FN, SELECT, START = 708, 704, 705
BUTTONS = {708: "FN", 704: "SELECT", 705: "START", 310: "L1", 311: "R1", 312: "L2", 313: "R2", 706: "L3",
           707: "R3", 305: "A", 304: "B", 307: "X", 308: "Y", 544: "Cima", 545: "Baixo", 546: "Esquerda",
           547: "Direita", 115: "Vol+", 114: "Vol-"}
ORDER = list(BUTTONS)            # ordem em que os nomes aparecem: FN primeiro, direcional por último

# chave: (nome, ícone, tipo, botões padrão, ligado por padrão). "toque" age quando a combinação
# fecha; "segurar" pede a combinação parada por 1 s. Personalizar troca só a tecla que vai com o
# FN; o de sair do jogo (FIXED) é sempre SELECT + START.
ACTIONS = {
    "fps": ("Contador de FPS", "gauge", "toque", [FN, 307], True),
    "limite": ("Limite de 30 FPS", "battery-2", "toque", [FN, 304], True),
    "captura": ("Captura de tela", "device-tv", "toque", [FN, 308], True),
    "fechar": ("Fechar o jogo", "x", "segurar", [SELECT, START], True),
}
CAP_FPS = 30
FIXED = {"fechar"}

# o que o ogage (serviço do dArkOSen) já faz com o FN: um atalho novo não pode usar
SYSTEM = [({FN, 544}, "brilho"), ({FN, 545}, "brilho"), ({FN, 546}, "gamma"), ({FN, 547}, "gamma"),
          ({FN, 115}, "brilho"), ({FN, 114}, "brilho"), ({FN, 310}, "ajuste do sistema"), ({FN, 311}, "ajuste do sistema"),
          ({FN, 305}, "ajuste do sistema"), ({FN, 706}, "ajuste do sistema"), ({FN, 707}, "ajuste do sistema"),
          ({SELECT, FN}, "a bateria falada")]


def defaults():
    return {**{k: a[4] for k, a in ACTIONS.items()}, "combos": {k: list(a[3]) for k, a in ACTIONS.items()}}


def normalize(c):
    """Escolhas gravadas (inclusive de versões anteriores) -> {chave: bool, "combos": {...}}."""
    out = defaults()
    c = c if isinstance(c, dict) else {}
    for k in ACTIONS:
        v = c.get(k, out[k])
        if k == "fps" and isinstance(v, str):            # 1.5.0 antiga: "fn" | "sempre" | "desligado"
            v = v != "desligado"
        elif k == "limite" and not isinstance(v, bool):   # 1.5.0 antiga: 0 | 30 | 45
            v = bool(v)
        out[k] = bool(v)
    for k, cb in (c.get("combos") or {}).items():
        if k in ACTIONS and k not in FIXED and isinstance(cb, list) and len(cb) >= 2 and all(b in BUTTONS for b in cb):
            out["combos"][k] = cb
    return out


def text(codes):
    """[708, 307] -> "FN + X"."""
    return " + ".join(BUTTONS[b] for b in sorted(set(codes), key=ORDER.index))


def problem(key, codes, combos):
    """Por que essa combinação não serve (ou None)."""
    s = set(codes)
    if key in FIXED:
        return "Este atalho é fixo."
    if len(s) < 2:
        return "Escolha uma tecla para ir junto com o FN."
    if 116 in s:
        return "O power não entra em atalhos."
    if s == {SELECT, START} or s == {FN, SELECT, START}:
        return "SELECT + START é o atalho fixo de fechar o jogo."
    for cb, what in SYSTEM:
        if s == cb:
            return f"{text(cb)} já é do sistema ({what})."
    for k, cb in combos.items():
        if k != key and set(cb) == s:
            return f"{text(cb)} já é o atalho de {ACTIONS[k][0]}."
    return None


def tip(key, combos):
    t = text(combos[key])
    return {
        "fps": f"{t} mostra e esconde, no jogo, uma pílula com quadros por segundo, temperatura e bateria. As "
               "cores avisam: FPS baixo, console quente, bateria no fim.",
        "limite": f"{t} trava o jogo em {CAP_FPS} FPS e solta de novo. Em jogo leve economiza bateria e esquenta "
                  "menos. Um traço roxo no contador mostra que está ligado.",
        "captura": f"{t} salva a tela do jogo (sem o contador) na pasta imagens dentro da pasta do jogo.",
        "fechar": f"Segure {t} por 1 s: o jogo fecha e o Omni36OS volta. Para port travado ou sem opção de sair.",
    }[key]
