#!/usr/bin/env python3
"""Omni36OS — interface gráfica (SDL2) do assistente do R36S.

Tela inicial com 9 cartões; cada cartão abre uma página com o diagnóstico
(regras fixas de omni_checks.py) à esquerda e os controles à direita.
Controle: direcional/analógico navega, A confirma, B volta; o power abre Energia.
Os botões A/B seguem a inversão do sistema ou do Omni36OS.

Variáveis: OMNI_FAKE=1 (dados de mentira, para desenhar no PC),
OMNI_WINDOWED=1, OMNI_DEMO="right,ok,wait800,shot,..." + OMNI_SHOT_DIR (roteiro
com screenshots PPM, para testar sem mãos).
"""
import ctypes as C
import json
import math
import os
import signal
import struct
import threading
import time

import gfx
from gfx import W, H, hexc, mix, alpha

FAKE = os.environ.get("OMNI_FAKE") == "1"
if not FAKE:
    import omni
    import omni_backup
    import omni_checks
    import omni_games
    import omni_ports_fix
    import omni_sistema
    import omni_tools
else:   # simulador: a ficha da Steam vem de verdade, mas o cache fica no PC
    os.environ.setdefault("OMNI_META_DIR", os.path.expanduser("~/.cache/omni36os-steam"))
import omni_meta  # noqa: E402
import omni_combos  # noqa: E402

# --- paleta ---

# Tema escuro e claro (Ajuda > Tema). INK é a cor dos véus e contornos: branco
# sobre o fundo escuro, azul-marinho sobre o claro. ON_TEXT é o texto em cima da
# cor de destaque (item escolhido), branco nos dois temas.
from omni_theme import THEMES  # noqa: E402
ON_TEXT = (255, 255, 255, 255)
THEME = "escuro"


def apply_theme(name):
    global THEME, BG_TOP, BG_BOT, TEXT, MUTED, FAINT, INK, GLASS, GLASS_HI, MODAL_A, MODAL_B, TOAST, BLOB_A
    THEME = name if name in THEMES else "escuro"
    t = THEMES[THEME]
    BG_TOP, BG_BOT, TEXT, MUTED, FAINT = (hexc(t[k]) for k in ("BG_TOP", "BG_BOT", "TEXT", "MUTED", "FAINT"))
    MODAL_A, MODAL_B, TOAST = hexc(t["MODAL_A"]), hexc(t["MODAL_B"]), hexc(t["TOAST"])
    INK = hexc(t["INK"])[:3]
    GLASS, GLASS_HI = (*INK, 14), (*INK, 26)
    BLOB_A = t["BLOB"]


def ink(a):
    return (*INK, a)


THEME_FILE = os.path.expanduser("~ark/.config/omni36os/tema")


def saved_theme():
    if FAKE:
        return os.environ.get("OMNI_TEMA", "escuro")
    try:
        with open(THEME_FILE) as f:
            return f.read().strip()
    except OSError:
        return "escuro"


apply_theme(saved_theme())
LEVEL = {"ok": hexc("34d399"), "aviso": hexc("fbbf24"), "problema": hexc("f87171"), "info": hexc("60a5fa"),
         "dica": hexc("c084fc")}   # dica: mini explicação do item escolhido
LEVEL_ICON = {"ok": "check", "aviso": "alert-triangle", "problema": "x", "info": "info-circle", "dica": "bulb"}

CARDS = [
    # id, título, ícone, cor 1, cor 2
    ("ports", "Ports", "device-gamepad-2", "c084fc", "7c3aed"),     # abre a biblioteca
    ("bateria", "Bateria", "battery-charging", "a3e635", "16a34a"),
    ("tela", "Sistema", "settings", "fbbf24", "f97316"),
    ("desempenho", "Desempenho", "gauge", "fb7185", "e11d48"),
    ("pendrive", "USB", "usb", "818cf8", "4f46e5"),
    ("cartoes", "Cartões SD", "device-sd-card", "2dd4bf", "0284c7"),
    ("checkup", "Verificar", "stethoscope", "22d3ee", "3b82f6"),
    ("ferramentas", "Ferramentas", "adjustments", "94a3b8", "475569"),
    ("ajuda", "Ajuda", "help-circle", "60a5fa", "a78bfa"),
]
COLS = 3
# Páginas abertas de dentro de outro card: B volta para o card de origem e os
# alertas delas aparecem no ponto do card de origem.
TWO_COLS = {"tela"}   # cartões sem painel de diagnóstico: as ações vêm em duas colunas
SUBPAGES = {            "calibracao": ("Calibrar a bateria", "battery-2", "a3e635", "16a34a", "bateria"),
            "usbrede": ("Rede pelo cabo USB", "network", "38bdf8", "4f46e5", "pendrive"),
            "seguranca": ("Segurança", "lock", "fbbf24", "f97316", "tela"),
            "wifi": ("Wi-Fi", "wifi", "38bdf8", "0ea5e9", "tela"),
            "backup": ("Backup", "device-floppy", "60a5fa", "a78bfa", "tela"),
            "atalhos": ("Atalhos", "keyboard", "fbbf24", "f97316", "tela"),
            "testar": ("Testar ports", "player-play", "34d399", "059669", "ferramentas")}
PARENT = {cid: v[4] for cid, v in SUBPAGES.items()}
SOURCE_NAMES = {"roms": "ROMS", "roms2": "ROMS2", "ambos": "ROMS e ROMS2"}
ZRAM_SIZES = [0, 256, 512, 768]   # MB do zram (Desempenho); 0 = desligado, o padrão
LIVE = {"usbrede": 3.0, "calibracao": 10.0, "wifi": 5.0}   # subpáginas com estado que muda sozinho: relê a cada N s


LIB_CARD = ("jogos", "Jogos", "device-gamepad-2", "c084fc", "7c3aed")   # cor da biblioteca (tela inicial)


def card_info(cid):
    """(id, título, ícone, cor 1, cor 2) de um card ou subpágina."""
    if cid == "jogos":
        return LIB_CARD
    if cid in SUBPAGES:
        return (cid, *SUBPAGES[cid][:4])
    return next(c for c in CARDS if c[0] == cid)
FPS_ACTIVE, FPS_IDLE, IDLE_AFTER = 30, 10, 4.0   # quadros/s; segundos sem botão até ficar parado
LIB_POS = "/tmp/omni36os-biblioteca.json"
HUB = os.environ.get("OMNI_HUB", "")         # boot: shell do sistema; jogo: por cima de um jogo (botão de power)
POWER_SHM = "/dev/shm/omni36os-power"          # mesma pasta do power_button.py (lá está o porquê)
POWER_PRESS = f"{POWER_SHM}/press"               # menu na tela: o pid deste Omni36OS
POWER_PENDING = f"{POWER_SHM}/pending"
POWER_FLAG = f"{POWER_SHM}/menu"                 # abrir já no menu de energia
PANIC_MSG = f"{POWER_SHM}/panic-msg"
RESUME = os.environ.get("OMNI_RESUME", "")   # "testar": o Omni36OS voltou de um teste de port

import omni_help

HERE = os.path.dirname(os.path.abspath(__file__))


def omni_version():
    try:
        with open(os.path.join(HERE, "VERSION")) as f:
            return f.read().strip() or "?"
    except OSError:
        return "?"


def about_findings():
    """Painel da Ajuda: qual Omni36OS e qual Omni36OS estão rodando."""
    ver = omni_version()
    inst = time.strftime("%d/%m/%Y %H:%M", time.localtime(os.path.getmtime(os.path.join(HERE, "omni_ui.py"))))
    out = [("info", f"Omni36OS versão {ver}, instalado em {inst}.")]
    news = next((n for n in omni_help.NOVIDADES if n[0] == ver), None)
    if news:
        out.append(("info", f"Novidades desta versão: {news[2][0]}"))
    try:
        with open("/home/ark/.config/.VERSION") as f:
            d = f.read().strip()
        out.append(("info", f"Omni36OS de {d[2:4]}/{d[:2]}/{d[4:]}." if len(d) == 8 else f"Omni36OS {d}."))
    except OSError:
        pass
    return out

FAKE_CARD = os.path.expanduser("~/Apps/Omni36OS/cartao/EASYROMS/ports")   # cópia do cartão no PC
FAKE_GAMES = [
    {"name": "ports", "full": "Ports", "path": "/roms2/ports", "n_unknown": 0, "unknown": [], "games": [
        {"path": "/roms2/ports/Stardew Valley.sh", "name": "Stardew Valley", "size": 524288000, "fav": 1,
         "plays": 12, "time": 18400, "last": "20261024T201000"},
        {"path": "/roms2/ports/Celeste.sh", "name": "Celeste", "size": 1200000000, "plays": 3,
         "time": 3600, "last": "20261020T101000"},
        {"path": "/roms2/ports/Undertale.sh", "name": "Undertale", "size": 180000000, "fav": 1},
        {"path": FAKE_CARD + "/Daytona USA.sh", "name": "Daytona USA", "size": 90000000},   # pasta info
        {"path": FAKE_CARD + "/Halo - Combat Evolved.sh", "name": "Halo - Combat Evolved", "size": 50000000},
        {"path": FAKE_CARD + "/McpeLauncher.sh", "name": "Minecraft", "size": 300000000},
        {"path": "/roms2/ports/Half-Life.sh", "name": "Half-Life", "size": 400000000},
        {"path": "/roms2/ports/Hollow Knight.sh", "name": "Hollow Knight", "size": 900000000}]},
]

FAKE_PORTS = [{"dir": "/roms2/ports", "label": "/roms2/ports (cartão de jogos)", "es": True,
               "ports": ["/roms2/ports/Daytona USA.sh", "/roms2/ports/NFSU1.sh", "/roms2/ports/Undertale.sh"]}]
GAMMAS = [0.6, 0.8, 0.9, 1.0, 1.1, 1.2, 1.4, 1.6]
GOV_NAMES = {"powersave": "Economia", "ondemand": "Equilibrado", "schedutil": "Equilibrado (kernel)",
             "performance": "Máximo"}


def swapped_ab():
    if os.path.exists("/var/cache/Switch_AB"):
        return True
    try:
        with open("/home/ark/.emulationstation/es_settings.cfg") as f:
            return 'name="InvertButtons" value="true"' in f.read()
    except OSError:
        return False


# --- dados (reais ou de mentira) ---

class Data:
    def status(self):
        if FAKE:
            return {"bat": 87, "carregando": False, "temp": 52, "wifi": True, "gov": "ondemand"}
        t = omni.read_text("/sys/class/thermal/thermal_zone0/temp", "0")
        return {
            "bat": int(omni.read_text("/sys/class/power_supply/battery/capacity", "0")),
            "carregando": omni.read_text("/sys/class/power_supply/battery/status") in ("Charging", "Full"),
            "temp": int(t) // 1000 if t.isdigit() else 0,
            "wifi": os.path.exists("/sys/class/net/wlan0"),
            "gov": omni.get_preferred_governor(),
        }

    def check(self, name):
        if FAKE:
            time.sleep(0.4)
            sd = ("aviso", "Cartão de jogos sem marca identificada (código 0xfe), comum em cartões genéricos.")
            som = ("problema", "A saída de som está em SPK, o certo é SPK_HP.")
            fake = {
                "checkup": (["restaurar_audio"], [("problema", "Sistema: " + som[1]), ("aviso", "Cartões SD: " + sd[1]),
                                                  ("info", "Cada card mostra o detalhe do seu assunto.")]),
                "bateria": ([], [("ok", "Bateria em 87%, descarregando."), ("ok", "Brilho em 40%."),
                                 ("ok", "Processador em modo ondemand no menu.")]),
                "atualizar": (["restaurar_audio"], [("ok", "Volume em 60%."), som]),
                "desempenho": ([], [("ok", "Temperatura normal: 52 °C."),
                                    ("ok", "Processador a 1008 MHz, modo Equilibrado."),
                                    ("info", "Limites: processador 1296 MHz, GPU 520 MHz. ZRAM 0 MB (0 MB em uso).")]),
                "cartoes": ([], [sd, ("ok", "Cartão do sistema: 16 GB, SanDisk."),
                                 ("ok", "Espaço do sistema: 4.7 GB livres (50% usado)."),
                                 ("ok", "Espaço de jogos: 31.2 GB livres (50% usado).")]),
                "pc": (["ligar_pendrive"], [("ok", "A partição /roms2 (31.2 GB livres) vai aparecer no PC como pendrive."),
                                            ("info", "Ligar reinicia o aparelho; o Wi-Fi para até desligar.")]),
            }
            acts, found = fake.get(name, ([], [("ok", "Tudo certo (dados de teste).")]))
            nivel = "problema" if any(l == "problema" for l, _ in found) else \
                "aviso" if any(l == "aviso" for l, _ in found) else "ok"
            return {"nivel": nivel, "acoes": acts, "achados": found}
        return omni_checks.CHECKS[name]()

    def action(self, name):
        if FAKE:
            time.sleep(1)
            return "Feito!"
        return omni_checks.run_action(name)

    def label(self, name):
        if FAKE:
            return {"restaurar_audio": "Restaurar o áudio do sistema",
                    "ligar_pendrive": "Ligar o modo pendrive (reinicia)"}.get(name, name)
        return omni_checks.ACTIONS[name][0]

    def get(self, what):
        if FAKE:
            if what in self.__dict__.get("fake_vals", {}):   # simulador: guarda o que foi mudado
                return self.fake_vals[what]
            if what.startswith("at_"):
                return omni_combos.defaults()[what[3:]]
            return {"brilho": 40, "volume": 60, "gov": "ondemand", "govs": ["powersave", "ondemand", "performance"],
                    "part": "roms2", "pendrive": False, "cpu_max": 1296, "cpu_freqs": [1296, 1416, 1512],
                    "gpu_max": 520, "gpu_freqs": [400, 480, 520, 600], "zram": 0, "fonte": "roms", "gamma": 1.0, "contraste": 50, "led": "verde",
                    "power": "desligar", "tema": THEME}[what]
        if what == "brilho":
            return omni.get_brightness()
        if what == "volume":
            return omni.get_volume()
        if what == "gov":
            return omni.get_preferred_governor()
        if what == "govs":
            return [g for g in ("powersave", "ondemand", "schedutil", "performance") if g in omni.get_cpu_governors()]
        if what == "part":
            return omni.usb_run("part") or ("roms2" if os.path.ismount("/roms2") else "roms")
        if what == "pendrive":
            return omni.usb_facts()["modo_pendrive_ligado"]
        if what == "cpu_max":
            return omni.get_cpu_max()
        if what == "cpu_freqs":
            return omni.cpu_freqs()
        if what == "gpu_max":
            return omni.get_gpu_max()
        if what == "gpu_freqs":
            return omni.gpu_freqs()
        if what == "zram":
            return omni_sistema.zram_get()
        if what == "fonte":
            return omni.get_game_source()
        if what == "gamma":
            return omni.get_gamma()
        if what == "contraste":
            return int(round((self.get("gamma") - 0.5) * 100))
        if what == "led":
            return omni.get_led()
        if what == "tema":
            return THEME
        if what.startswith("at_"):          # Sistema > Atalhos
            return omni.get_atalhos()[what[3:]]
        if what == "power":
            return omni.get_power_button()

    def set(self, what, value):
        if what == "tema":
            apply_theme(value)
            if not FAKE:
                os.makedirs(os.path.dirname(THEME_FILE), exist_ok=True)
                with open(THEME_FILE, "w") as f:
                    f.write(value)
            return "tema"
        if FAKE:
            self.__dict__.setdefault("fake_vals", {})[what] = value
            return "ok"
        if what == "brilho":
            return omni.set_screen_brightness({"value": max(10, value)})
        if what == "volume":
            return omni.set_system_volume({"value": value})
        if what == "gov":
            return omni.set_preferred_governor({"governor": value})
        if what == "part":
            return omni.usb_set_partition({"part": value})
        if what == "cpu_max":
            return omni.set_cpu_max({"mhz": value})
        if what == "gpu_max":
            return omni.set_gpu_max({"mhz": value})
        if what == "zram":
            return omni_sistema.zram_set(value)
        if what == "fonte":
            return omni.set_game_source({"source": value})
        if what == "gamma":
            return omni.set_gamma({"value": value})
        if what == "contraste":
            return self.set("gamma", 0.5 + value / 100)
        if what == "led":
            return omni.set_led({"color": value})
        if what.startswith("at_"):
            return omni.set_atalho({"key": what[3:], "value": value})
        if what == "power":
            return omni.set_power_button({"mode": value})

    def run(self, tool, args=None):
        if FAKE:
            time.sleep(1.2)
            return "Escrita: 18.2 MB/s\nLeitura: 41.0 MB/s"
        return omni.run_tool({"tool": tool, "args": args or {}})


D = Data()
if not FAKE:
    try:
        omni.migrate_cpu_settings()   # modo do processador de versões antigas
        omni.relax_clocks()           # o perfmax de um port deixou tudo no máximo
    except OSError:
        pass


# --- controles de uma página ---

class Action:
    def __init__(self, label, icon, fn, confirm=None, danger=False):
        self.label, self.icon, self.fn, self.confirm, self.danger = label, icon, fn, confirm, danger


class Slider:
    def __init__(self, label, icon, key, step=10, lo=0):
        self.label, self.icon, self.key, self.step, self.lo = label, icon, key, step, lo
        self.value = D.get(key)
        self.shown = float(self.value)


# ferramentas perigosas: (segundos de espera, segurar A, o que pode dar errado, como desfazer)
BOOT_UNDO = ("Segure L1 ao ligar para pular o Omni36OS, ou B para o BaRT. Se a tela não ligar, só gravando "
             "de novo o cartão do sistema (tenha um backup).")
DANGER = {
    "dArkOSen_dtb_patcher_v1.2.sh": (10, True, "Um DTB errado deixa a tela preta ou o console sem ligar.", BOOT_UNDO),
    "60hz_display_timing_patcher.sh": (10, True, "A tela pode não aceitar o novo tempo e ficar preta.", BOOT_UNDO),
    "Restore dArkOSen.sh": (10, True, "Troca o kernel e o sistema pelos originais do dArkOSen: ajustes feitos depois "
                                      "somem.", BOOT_UNDO),
    "fix-sd2-mount.sh": (10, False, "Recompila os DTB do boot; se falhar no meio, o boot pode quebrar.", BOOT_UNDO),
    "Enable Quick Mode.sh": (5, False, "Muda o que sobe no boot.", "Rode de novo para voltar ao modo normal."),
    "Remove Kodi.sh": (5, False, "Apaga o Kodi e as configurações dele.", "Só reinstalando o Kodi."),
}
ONOFF = {True: "Ligado", False: "Desligado"}
HUD_FLAG, CAP_FLAG, SHOT_FLAG = "/dev/shm/omni36os-hud", "/dev/shm/omni36os-fpscap", "/dev/shm/omni36os-shot"


def flag(path):
    try:
        with open(path) as f:
            return f.read().strip()
    except OSError:
        return ""


def put_flag(path, value):
    with open(path, "w") as f:
        f.write(str(value))
    try:
        os.chmod(path, 0o666)
    except OSError:
        pass
PAD_DEV = "/dev/input/by-path/platform-odroidgo3-joypad-event-joystick"   # a gravação de atalho lê direto daqui
# simulador: comandos do teclado -> botões do controle (KP8 = FN), só na gravação de atalho
SIM_BUTTONS = {"ok": 305, "back": 304, "x": 307, "y": 308, "l1": 310, "r1": 311, "start": 705, "select": 704,
               "up": 544, "down": 545, "left": 546, "right": 547, "fn": 708}
# o que o ogage (serviço do dArkOSen) já faz com o FN: nenhum atalho do Omni36OS usa essas combinações
FN_SYSTEM = [("info", "FN + cima/baixo: brilho da tela. FN + volume: brilho fino."),
             ("info", "FN + L1/R1, esquerda/direita, A, L3 e R3: ajustes do sistema (gamma, Wi-Fi, Bluetooth, saves)."),
             ("info", "SELECT + FN: fala a carga da bateria. FN + power: modo pânico (fecha o jogo e acalma o console).")]


class Choice:
    def __init__(self, label, icon, key, options, names=None):
        self.label, self.icon, self.key, self.options = label, icon, key, options
        self.names = names or {}
        cur = D.get(key)
        self.index = options.index(cur) if cur in options else 0


def subpage(action, cid):
    """Marca o botão que abre uma subpágina (o B dela volta com ele selecionado)."""
    action.sub = cid
    return action


def tip(item, text):
    """Mini explicação do controle: aparece no topo do painel da esquerda quando ele está escolhido."""
    item.tip = text
    return item


# Mini explicações por rótulo (o começo basta); o card USB põe as dele direto nos itens.
TIPS = {
    "Wi-Fi": "Liga e desliga o Wi-Fi, conecta a uma rede, esquece as salvas e mostra o IP do console.",
    "Atualizar status": "Roda a verificação deste card de novo e atualiza o painel.",
    "Testar o controle": "Mostra cada botão, direcional e analógico na tela enquanto você aperta. Bom para achar "
                         "botão falhando ou analógico descalibrado.",
    "Consertar atalhos": "Reinicia o serviço que cuida de brilho e volume pelos botões. Use quando eles pararem "
                         "de responder.",
    "Calibrar a bateria": "Mede a sua bateria de cheia até vazia para a % ficar certa. Leva algumas horas de uso "
                          "sem o carregador.",
    "Iniciar a calibração": "Comece com a bateria cheia e sem o carregador. Use o console normalmente até "
                            "desligar; a medição continua sozinha.",
    "Parar a calibração": "Interrompe a medição. O que já foi medido fica guardado.",
    "Aplicar a curva": "Usa a última calibração completa: a % da bateria passa a seguir a sua bateria.",
    "Voltar à curva de fábrica": "Apaga a curva calibrada e volta à % padrão do sistema.",
    "Trocar a senha": "Troca a senha do usuário ark, usada no SSH e no sftp.",
    "Senha do Samba": "Troca a senha das pastas compartilhadas na rede (Samba).",
    "Trava por senha": "Pede a senha ao ligar o console, antes de abrir o menu.",
    "Processador no menu": "Como o processador trabalha enquanto você está no menu. Economia gasta menos "
                           "bateria; os jogos usam o ajuste de cada port.",
    "Limite do processador": "Frequência máxima do processador. Acima de 1296 MHz é overclock: esquenta mais.",
    "Limite da GPU": "Frequência máxima da GPU. Acima de 520 MHz é overclock: esquenta mais.",
    "Memória extra (zram)": "Usa parte da RAM comprimida como memória extra. Ajuda ports pesados que fecham por "
                            "falta de memória, com um pouco mais de uso do processador.",
    "Liberar overclock": "Libera 1512 MHz no processador e 600 MHz na GPU. Pode esquentar e travar; o aviso "
                         "explica como desfazer.",
    "Ligar: modo universal": "O console dá o IP ao PC (funciona em qualquer PC). Depois use ssh ark@10.44.44.1.",
    "Ligar: internet pelo PC": "Usa a internet do PC no console. O PC precisa compartilhar a conexão pelo cabo.",
    "Serviços remotos: ligar": "Liga o gerenciador de arquivos pela web e o Samba, para mexer no cartão pelo PC.",
    "Serviços remotos: desligar": "Desliga a web e o Samba. O SSH continua.",
    "Desligar a rede USB": "Desliga a rede e devolve a porta OTG ao modo normal.",
    "Compatibilidade": "Confere se o kernel, a porta e os programas deste sistema suportam a rede USB.",
    "Jogos lidos de": "Em qual cartão o Omni36OS procura os ports: ROMS, ROMS2 ou os dois.",
    "Detalhes": "Tamanho, espaço livre, sistema de arquivos e saúde dos cartões.",
    "Testar velocidade": "Mede a leitura e a escrita de cada cartão. Cartão lento deixa os ports lentos "
                         "para abrir.",
    "Verificar e reparar": "Reinicia, procura e corrige erros na partição dos jogos (/roms2, ou /roms sem segundo cartão) e volta sozinho. Leva alguns "
                           "minutos.",
    "Arquivos": "Copiar, mover, renomear e apagar nos cartões e no pendrive, aqui dentro.",
    "Testar ports": "Abre um port por 15 s, mostra a causa provável se falhar e oferece a correção.",
    "Escolher o port": "Escolha um port da lista para abrir e testar.",
    "Limpar avisos de falha": "Apaga os avisos de ports que falharam no teste.",
    "Botão de power": "O que o botão de power faz: desligar como no Omni36OS ou abrir o menu de energia.",
    "Manual": "Como usar cada card do Omni36OS.",
    "Cuidados": "O que pode dar errado com overclock, DTB e cartões, e como evitar.",
    "Novidades": "O que mudou em cada versão.",
    "Créditos": "Quem fez o Omni36OS e os projetos em que ele se apoia.",
}


def add_tips(items):
    for it in items:
        if not getattr(it, "tip", None):
            it.tip = next((t for k, t in TIPS.items() if it.label.startswith(k)), None)
    return items


def tagged(action, name):
    """Marca o controle com a ação de omni_checks que ele faz (evita repetir a sugestão)."""
    action.act = name
    return action


# --- animação ---

def approach(cur, target, dt, speed=14.0):
    return target + (cur - target) * math.exp(-speed * dt)


class App:
    def __init__(self):
        if not FAKE:
            os.environ.setdefault("SDL_GAMECONTROLLERCONFIG_FILE", "/opt/inttools/gamecontrollerdb.txt")
        self.g = gfx.Gfx()
        self.swap = swapped_ab()
        self.running = True
        self.last_input = time.monotonic()
        self.t = 0.0
        self.sel = 0
        self.sel_x, self.sel_y = 0.0, 0.0
        self.accent = [hexc(CARDS[0][3]), hexc(CARDS[0][4])]
        self.page = None              # id do cartão aberto
        self.vol, self.vol_at = None, 0.0   # volume da pílula: lido no início e após os botões de volume
        self.last_page = None         # a página que está saindo (na transição)
        self.snap = None              # (página, última) já desenhadas nas camadas
        self.warm = [c[0] for c in CARDS] + list(SUBPAGES)  # páginas a pré-montar
        self.page_anim = 0.0          # 0 = início, 1 = página
        self.status = D.status()
        self.status_at = 0.0
        self.home_check = None
        self.modal = None             # {"title","text","icon","buttons":[...], "sel"}
        self.reader = None            # texto longo com rolagem (Ajuda)
        self.find_top = self.find_max = 0   # rolagem do diagnóstico (L1/R1)
        self.find_scroll = 0.0
        self.picker = None            # lista de ports para testar
        self.view = "menu"            # menu: os cards (tela inicial); lib: a biblioteca (card Ports)
        self.lib = {"sys": 0, "game": 0, "top": 0.0, "stop": 0.0}
        try:                          # volta para o mesmo jogo depois de jogar
            with open(LIB_POS) as f:
                self.lib.update(json.load(f))
        except (OSError, ValueError):
            pass
        self.toast = None             # (texto, nível, até)
        self.player = os.environ.get("OMNI_JOGADOR", "") if FAKE else omni_sistema.player_name()
        if not FAKE and self.player and not os.path.exists(omni_sistema.TELA):   # nome de antes da tela com nome
            threading.Thread(target=omni_sistema.set_player_name, args=(self.player,), daemon=True).start()
        self.want_power = self.want_msg = False
        self.msg_t = -9.0
        signal.signal(signal.SIGUSR1, lambda *_: setattr(self, "want_power", True))
        try:
            if os.environ.get("SDL_VIDEODRIVER") == "offscreen":
                raise OSError("teste fora da tela")
            os.makedirs(POWER_SHM, exist_ok=True)
            try:
                os.chmod(POWER_SHM, 0o777)
            except OSError:
                pass
            with open(f"{POWER_SHM}/ui-pid", "w") as f:   # o power_button.py só sinaliza este
                f.write(str(os.getpid()))
            os.chmod(f"{POWER_SHM}/ui-pid", 0o666)
        except OSError:
            pass
        signal.signal(signal.SIGUSR2, lambda *_: setattr(self, "want_msg", True))
        self.busy = None              # texto enquanto uma tarefa roda
        self.held = {}                # direção -> próximo repeat
        self.combo = set()
        self.pending = []
        self.alerts = {}              # cartão -> (pior nível, quantos alertas)
        self.results = {}             # cartão -> última verificação
        # Tela de carregamento: as verificações rodam antes do menu aparecer,
        # para não disputar o processador com a animação depois.
        self.loading = True
        self.load_done, self.load_total, self.load_label = 0, 1, "Preparando..."
        self.load_shown = 0.0
        self.worker(self.check_all, self._all_checked, quiet=True)

    # --- tarefas em segundo plano ---

    def worker(self, fn, done, busy=None, quiet=False):
        if busy:
            self.busy = busy

        def run():
            try:
                res = fn()
            except Exception as e:  # mostra o erro em vez de travar a tela
                res = e
            self.pending.append((done, res, bool(busy)))
        threading.Thread(target=run, daemon=True).start()

    def _home_checked(self, res):
        if not isinstance(res, Exception):
            self.home_check = res

    # Verificação de cada cartão (sem o teste de velocidade, que é demorado):
    # dá os pontos de notificação da tela inicial.
    def card_check(self, cid):
        if cid == "desempenho" and not FAKE:
            return self._lento_rapido()
        if cid == "cartoes" and not FAKE:
            return self._cartoes()
        if cid == "testar":
            return self._testar()
        if cid == "ports":
            idx = self.games()
            n = sum(len(s["games"]) for s in idx)
            return {"nivel": "ok", "acoes": [], "achados": [("ok", f"{n} Jogos e ports na biblioteca.")]}
        if cid == "backup":
            return self._backup()
        if cid == "ferramentas":
            return self._ferramentas()
        if cid == "wifi" and FAKE:
            on = getattr(self, "fake_wifi", True)
            return {"nivel": "ok", "acoes": [], "achados": [("ok", "Conectado a Casa, sinal 72%."),
                                                            ("ok", "IP do console: 192.168.0.42")] if on else
                    [("info", "Wi-Fi desligado.")]}
        if cid == "wifi":
            return omni_checks.finish(omni_sistema.wifi_status(), [], {})
        if cid in ("usbrede", "calibracao"):
            if FAKE:
                return {"nivel": "ok", "acoes": [], "achados": [("ok", f"{cid}: tudo certo (dados de teste).")]}
            fn = {"usbrede": omni_sistema.usbnet_status, "calibracao": omni_sistema.cal_status}[cid]
            return omni_checks.finish(fn(), [], {})
        if cid == "atalhos":
            hud = FAKE or os.path.exists(os.path.join(os.path.dirname(os.path.abspath(__file__)), "hud", "omni_hud.so"))
            return {"nivel": "ok" if hud else "aviso", "acoes": [], "achados": [
                ("ok" if hud else "aviso", "Os atalhos valem dentro dos jogos. Aqui você liga, desliga e troca os botões."
                 if hud else "Falta o hud/omni_hud.so: contador, limite e captura não funcionam."),
                *FN_SYSTEM]}
        if cid == "seguranca":
            locked = (os.environ.get("OMNI_TRAVA") == "1") if FAKE else omni_sistema.lock_on()
            return {"nivel": "ok", "acoes": [], "achados": [
                ("ok", "Trava ligada: o console pede a senha ao ligar. A senha fica em EASYROMS/senha/senha.txt."
                 if locked else "Trava desligada: o console abre direto nos jogos."),
                ("ok", "Usuário do sistema e do Samba: ark. Trocar a senha muda as duas.")]}
        if cid == "tela" and not FAKE:    # Sistema = tela + som: as duas verificações juntas
            a, b = D.check("atualizar"), D.check("sem_som")
            return omni_checks.finish(a["achados"] + b["achados"], a["acoes"] + b["acoes"],
                                      {**a.get("fatos", {}), **b.get("fatos", {})})
        name = {"tela": "atualizar", "pendrive": "pc"}.get(cid, cid)
        return D.check(name)

    def check_all(self):
        out = {}
        todo = [c for c in CARDS + [card_info(c) for c in SUBPAGES]
                if c[0] != "ajuda" and (RESUME != "testar" or c[0] == "testar")]
        self.warm.insert(0, "home")
        self.load_total = len(todo) + len(self.warm)
        for k, (cid, title, *_) in enumerate(todo):
            self.load_label = f"Verificando {title.lower()}..."
            self.load_done = k
            try:
                out[cid] = self.card_check(cid)
            except Exception as e:
                out[cid] = {"nivel": "problema", "achados": [("problema", f"Erro: {e}")], "acoes": []}
        return out

    def _all_checked(self, res):
        if isinstance(res, Exception):
            return
        self.home_check = res.get("checkup")
        for cid, r in res.items():
            self.set_result(cid, r)

    def set_result(self, cid, r):
        self.results[cid] = r
        home = PARENT.get(cid, cid)
        worst, n = "ok", 0
        for c in [home] + [k for k, p in PARENT.items() if p == home]:
            rc = self.results.get(c)
            if not rc:
                continue
            k = sum(1 for lvl, _ in rc["achados"] if lvl in ("aviso", "problema"))
            if k:
                n += k
                worst = "problema" if "problema" in (worst, rc["nivel"]) else "aviso"
        if n:
            self.alerts[home] = (worst, n)
        else:
            self.alerts.pop(home, None)

    # --- páginas ---

    def open_page(self, cid):
        self.page = self.last_page = cid
        self.items, self.item_sel, self.item_y, self.item_h = self.build_items(cid), 0, 0.0, 0.0
        self.act_off = 0.0
        self.findings, self.info = None, []
        self.find_top, self.find_max, self.find_scroll = 0, 0, 0.0
        if cid in self.results:       # já verificado no carregamento
            self._got_findings(self.results[cid])
        else:
            self.reload_findings()

    def reload_findings(self, quiet=False):
        cid = self.page
        if cid == "ajuda":
            self.findings = {"nivel": "ok", "achados": about_findings(), "acoes": []}
            return
        if not quiet:                 # quiet: mantém o diagnóstico na tela até o novo chegar
            self.findings = None

        def done(res):
            if not isinstance(res, Exception):
                self.set_result(cid, res)
            if self.page == cid:
                self._got_findings(res)
        self.worker(lambda: self.card_check(cid), done)

    def _lento_rapido(self):
        f = omni_checks.cpu_facts()
        out = []
        omni_checks.check_temp(f, out)
        out.append(("ok", f"Processador a {f['freq_mhz']} MHz, modo {GOV_NAMES.get(f['governador'], f['governador'])}."))
        omni_checks.check_overclock(f, out, [])   # tirar o OC é o seletor "Limite do processador" daqui
        acts = []
        z = omni.zram_facts()
        out.append(("info", f"Limites: processador {f['cpu_max_mhz']} MHz, GPU {f['gpu_max_mhz']} MHz. "
                            f"ZRAM {z['zram_mb']} MB ({z['zram_usado_mb']} MB em uso)."))
        return omni_checks.finish(out, acts, f)

    def _testar(self):
        groups = FAKE_PORTS if FAKE else omni.port_groups()
        res = {} if FAKE else omni.port_results()
        out = []
        self.port_count = sum(len(g["ports"]) for g in groups)
        acks = set() if FAKE else omni.port_acks()
        for g in groups:
            out.append(("ok", f"{len(g['ports'])} Ports em {g['label']}."))
        names = {os.path.basename(p)[:-3] for g in groups for p in g["ports"]}
        fails = sorted(n for n, r in res.items() if r[0] == "falhou" and n in names
                       and f"{n}|{r[1]}" not in acks)
        seen = sum(1 for n, r in res.items() if r[0] == "falhou" and n in names and f"{n}|{r[1]}" in acks)
        if seen:
            out.append(("info", f"{seen} Falha(s) já vista(s): continuam marcadas na lista até um novo teste."))
        oks = sum(1 for n, r in res.items() if r[0] == "ok" and n in names)
        for n in fails:
            out.append(("aviso", f"{n} falhou no teste de {res[n][1]}. Relatório em omni36os/logs/{n}/."))
        if oks:
            out.append(("ok", f"{oks} Port(s) passaram no último teste."))
        out.append(("info", "O teste abre o port por 15 s e fecha sozinho. Se ele fechar antes, é falha."))
        return omni_checks.finish(out, [], {}) if not FAKE else {
            "nivel": "aviso" if fails else "ok", "achados": out, "acoes": []}

    def games(self, force=False):
        if FAKE:
            self.games_idx = FAKE_GAMES
        elif force or not getattr(self, "games_idx", None):
            self.games_idx = omni_games.index(force)
        return self.games_idx

    def _backup(self):
        if FAKE:
            return {"nivel": "ok", "acoes": [], "achados": [("info", "Omni36OS: nenhum backup ainda.")]}
        out = [("info", f"Ao exportar, você escolhe onde salvar. Último lugar: {omni_backup.backup_dir()}.")]
        last = omni_backup.last_backups()
        for mod, (name, *_x) in omni_backup.MODULES.items():
            if mod in last:
                out.append(("ok", f"{name}: último backup em {last[mod][1]}."))
            else:
                out.append(("info", f"{name}: nenhum backup ainda."))
        out.append(("info", "Só configurações: saves, estados, cores, temas e bancos de dados ficam de fora."))
        return omni_checks.finish(out, [], {})

    def _cartoes(self):
        out = []
        for c in omni_checks.sd_facts()["cartoes"]:
            lvl = "ok" if c["fabricante"] != "desconhecido" else "aviso"
            fab = c["fabricante"] if lvl == "ok" else f"marca não identificada ({c['codigo']})"
            out.append((lvl, f"Cartão de {c['cartao']}: {c['tamanho_gb']} GB, {fab}."))
        omni_checks.check_disk(out)
        for part, r in omni.last_scan().items():
            ok = r["resultado"] == "clean"
            txt = {"clean": "sem erros", "repaired": "erros encontrados e reparados",
                   "failed": "a verificação falhou"}.get(r["resultado"], r["resultado"])
            out.append(("ok" if ok else "aviso", f"Última verificação de /{part} ({r['quando']}): {txt}."))
        return omni_checks.finish(out, [], {})

    def _got_findings(self, res):
        if isinstance(res, Exception):
            self.findings = {"nivel": "problema", "achados": [("problema", f"Erro: {res}")], "acoes": []}
            return
        # alertas das subpáginas (ex.: Cartões SD em Desempenho) aparecem aqui também
        extra_alerts = []
        for sub, parent in PARENT.items():
            r = self.results.get(sub)
            if parent == self.page and r:
                n = sum(1 for lvl, _ in r["achados"] if lvl in ("aviso", "problema"))
                if n:
                    extra_alerts.append((r["nivel"], f"{SUBPAGES[sub][0]}: {n} alerta(s). Abra \"{SUBPAGES[sub][0]}\" para ver."))
        if extra_alerts:
            order = {"problema": 0, "aviso": 1, "ok": 2, "info": 3}
            res = dict(res, achados=sorted(extra_alerts + list(res["achados"]), key=lambda x: order.get(x[0], 9)))
            if res["nivel"] == "ok" or "problema" in (lvl for lvl, _ in extra_alerts):
                res["nivel"] = "problema" if any(l == "problema" for l, _ in extra_alerts) else "aviso"
        self.findings = res
        # ações sugeridas pela verificação entram no topo da lista
        base = [i for i in self.items if not getattr(i, "suggested", False)]
        extra = []
        for a in res.get("acoes", []):
            if any(isinstance(i, Action) and getattr(i, "act", None) == a for i in base):
                continue
            act = Action(D.label(a), "bolt", lambda a=a: self.do_action(a),
                         confirm=f"{D.label(a)}?")
            act.suggested, act.act = True, a
            act.tip = "Sugerido pela verificação deste card: resolve um dos avisos do painel."
            extra.append(act)
        self.items = extra + base
        self.item_sel = min(self.item_sel, len(self.items) - 1)

    def build_items(self, cid):
        return add_tips(self._build_items(cid))

    def _build_items(self, cid):
        A = Action
        recheck = A("Atualizar status", "refresh", self.reload_findings)
        if cid == "checkup":
            return [A("Testar o controle", "device-gamepad-2", self.open_pad),
                    A("Detalhes da tela", "device-tv", lambda: self.run_info("Tela e modelo", "detect_hardware_and_screen")),
                    A("Consertar atalhos", "adjustments", lambda: self.native("fix_hotkeys", "Reiniciando os atalhos..."),
                      confirm="Reiniciar o serviço de atalhos (brilho e volume pelos botões)?"),
                    recheck]
        if cid == "bateria":
            out = [subpage(A("Calibrar a bateria", "battery-2", lambda: self.open_page("calibracao")), "calibracao")]
            return out + [recheck]
        if cid == "tela":
            out = [Slider("Volume", "volume", "volume"),
                   Slider("Brilho", "sun", "brilho", lo=10),
                   Slider("Contraste", "adjustments", "contraste"),
                   Choice("Tema", "sun", "tema", list(THEMES), {"escuro": "Escuro", "claro": "Claro"}),
                   Choice("Cor do LED", "bulb", "led", ["verde", "vermelho"], {"verde": "Verde", "vermelho": "Vermelho"})]
            return out + [subpage(A("Segurança", "lock", lambda: self.open_page("seguranca")), "seguranca"),
                          subpage(A("Wi-Fi", "wifi", lambda: self.open_page("wifi")), "wifi"),
                          A(f"Nome do jogador: {self.player or '(sem nome)'}", "users",
                            lambda: self.ask_name(first=False)),
                          tagged(A("Restaurar áudio", "rotate", lambda: self.do_action("restaurar_audio"),
                                   confirm="Restaurar o áudio do sistema?\nSaída de som padrão e volume em 40%."),
                                 "restaurar_audio"),
                          subpage(A("Atalhos", "keyboard", lambda: self.open_page("atalhos")), "atalhos"),
                          subpage(A("Backup", "device-floppy", lambda: self.open_page("backup")), "backup"),
                          A("Redefinir o sistema", "rotate", self.ask_reset)]
        if cid == "atalhos":
            combos = D.get("at_combos")
            out = [tip(Choice(f"{name} · {omni_combos.text(combos[k])}", icon, "at_" + k, [True, False], ONOFF),
                       omni_combos.tip(k, combos))
                   for k, (name, icon, *_x) in omni_combos.ACTIONS.items()]
            return out + [tip(A("Personalizar um atalho", "pencil", self.pick_atalho),
                              "Escolha um atalho e aperte a tecla nova: ele vira FN + essa tecla. SELECT + START (fechar "
                              "o jogo) é fixo. Os nomes nesta página, nas dicas e no manual mudam junto."),
                          tip(A("Voltar aos botões padrão", "rotate", self.reset_combos,
                                confirm="Voltar todos os atalhos aos botões padrão?\nO que está ligado ou desligado "
                                        "não muda."),
                              "FN + X, FN + B e FN + Y, como vieram.")]
        if cid == "seguranca":
            locked = (os.environ.get("OMNI_TRAVA") == "1") if FAKE else omni_sistema.lock_on()
            return [A("Trocar a senha", "lock", self.ask_password),
                    A("Senha do Samba", "device-floppy", self.ask_samba),
                    A("Trava por senha: " + ("ligada" if locked else "desligada"), "lock", self.ask_lock)]
        if cid == "desempenho":
            return [Choice("Processador no menu", "cpu", "gov", D.get("govs"), GOV_NAMES),
                    Choice("Limite do processador", "gauge", "cpu_max", D.get("cpu_freqs"),
                           {f: f"{f} MHz" + (" (OC)" if f > 1296 else "") for f in D.get("cpu_freqs")}),
                    Choice("Limite da GPU", "device-gamepad-2", "gpu_max", D.get("gpu_freqs"),
                           {f: f"{f} MHz" + (" (OC)" if f > 520 else "") for f in D.get("gpu_freqs")}),
                    Choice("Memória extra (zram)", "database", "zram", ZRAM_SIZES,
                           {m: f"{m} MB" if m else "Desligada" for m in ZRAM_SIZES}),
                    A("Liberar overclock (1512 MHz, GPU 600)", "gauge", self.ask_overclock)]
        if cid == "pendrive":
            on = D.get("pendrive")
            tog = A("Desligar pendrive" if on else "Ligar pendrive", "power",
                    lambda: self.do_action("desligar_pendrive" if on else "ligar_pendrive"),
                    confirm=("Desligar o modo pendrive?\nO aparelho reinicia e o Wi-Fi volta." if on else
                             "Ligar o modo pendrive?\nO aparelho reinicia; o Wi-Fi para até desligar."))
            tog.act = "desligar_pendrive" if on else "ligar_pendrive"
            return [tip(tog, "O console vira um pendrive para o PC: ligue o cabo na porta OTG e copie jogos direto "
                             "para o cartão. Reinicia ao ligar e ao desligar; o Wi-Fi para enquanto estiver ligado."),
                    tip(subpage(A("Rede pelo cabo USB", "network", lambda: self.open_page("usbrede")), "usbrede"),
                        "O cabo USB vira uma rede entre o console e o PC: SSH, arquivos pela web e Samba, ou "
                        "internet do PC no console. Não reinicia."),
                    tip(A("Montar pendrive", "plug", lambda: self.native("usb_mount", "Montando o pendrive...")),
                        "Lê um pendrive ligado no console (OTG) em /mnt/usbdrive. Aceita FAT, exFAT e NTFS. "
                        "É o contrário do modo pendrive."),
                    tip(A("Desmontar pendrive", "x", lambda: self.native("usb_umount", "Desmontando...")),
                        "Termina de gravar e solta o pendrive montado. Use antes de tirar do console."),
                    tip(Choice("Partição no PC", "device-floppy", "part",
                               ["roms2", "roms"] if FAKE or os.path.ismount("/roms2") else ["roms"],
                               {"roms2": "/roms2 (segundo cartão)", "roms": "/roms (cartão do sistema)"}),
                        "Qual partição o PC enxerga no modo pendrive: /roms2 (segundo cartão, se houver) ou /roms "
                        "(cartão do sistema). Sem segundo cartão, só /roms aparece."),
                    tip(A("Status", "info-circle", lambda: self.run_info("Pendrive USB", "usb_status")),
                        "Mostra o estado da porta OTG: modo pendrive, partição exposta e o que está montado."),
                    tip(tagged(A("Limpar lixo do Mac", "x", lambda: self.do_action("limpar_mac", "Procurando o lixo do Mac... (até 1 minuto)"),
                                 confirm="Apagar os arquivos ._ e .DS_Store que o Mac cria?\nSeus jogos não são tocados."),
                               "limpar_mac"),
                        "Apaga os arquivos ._ e .DS_Store que o Mac deixa ao copiar. Eles aparecem como jogos "
                        "falsos na lista. Seus jogos não são tocados."),
                    tip(A("Restaurar boot", "arrow-back-up", lambda: self.run_tool_toast("usb_restore"),
                          confirm="Voltar o arquivo de boot original?\nO aparelho reinicia.", danger=True),
                        "Se o modo pendrive deixou a porta presa, volta o arquivo de boot (DTB) original salvo "
                        "antes da primeira vez e reinicia.")]
        if cid == "cartoes":
            return [Choice("Jogos lidos de", "folder", "fonte", list(SOURCE_NAMES), SOURCE_NAMES),
                    A("Detalhes", "info-circle", lambda: self.run_info("Cartões SD", "check_microsd_info")),
                    A("Testar velocidade", "brand-speedtest", self.speed_test),
                    A("Verificar e reparar os jogos", "device-sd-card", lambda: self.run_tool_toast("schedule_scan"),
                      confirm="Verificar e reparar a partição dos jogos?\nO aparelho reinicia, verifica o cartão e "
                              "volta sozinho. Leva alguns minutos.", danger=True)]
        if cid == "ferramentas":
            out = [A("Arquivos", "folder", self.open_files),
                   subpage(A("Testar ports", "player-play", lambda: self.open_page("testar")), "testar")]
            out += [tip(A(t["name"], "device-gamepad-2" if "PortMaster" in t["name"] else "folder",
                          lambda t=t: self.ask_tool(t)),
                        f"{t.get('desc', '')} Abre em tela cheia e o Omni36OS volta ao fechar.".strip())
                    for t in self.tool_list()]
            return out
        if cid == "wifi":
            on = getattr(self, "fake_wifi", True) if FAKE else omni_sistema.wifi_on()
            return [tip(A("Desligar o Wi-Fi" if on else "Ligar o Wi-Fi", "wifi-off" if on else "wifi",
                          lambda: self.wifi_toggle(not on)),
                        "Desliga o adaptador para poupar bateria." if on else
                        "Liga o adaptador USB de Wi-Fi; ele volta para a última rede salva."),
                    tip(A("Procurar redes", "refresh", self.wifi_scan),
                        "Lista as redes por perto, a mais forte primeiro. A rede com cadeado pede a senha."),
                    tip(A("Redes salvas", "device-floppy", self.wifi_saved),
                        "As redes que o console já conhece: conecte de novo ou esqueça uma."),
                    tip(A("Desconectar", "x", lambda: self.wifi_run(omni_sistema.wifi_disconnect if not FAKE else
                                                                    (lambda: "Desconectado."), "Desconectando...")),
                        "Sai da rede atual sem desligar o Wi-Fi."),
                    recheck]
        if cid == "usbrede":
            S = omni_sistema if not FAKE else None
            run = lambda fn, busy: (lambda: self.worker(fn if S else (lambda: "teste"), self._sys_done, busy=busy))
            return [A("Ligar: modo universal", "usb", run(S and S.usbnet_universal, "Ligando a rede USB..."),
                      confirm="Ligar a rede USB no modo universal?\nO console dá o IP ao PC: ligue o cabo de dados "
                              "na porta OTG e use ssh ark@10.44.44.1."),
                    A("Ligar: internet pelo PC", "wifi", run(S and S.usbnet_internet, "Pedindo IP ao PC... (até 30 s)"),
                      confirm="Ligar a rede USB usando a internet do PC?\nO PC precisa já estar compartilhando a "
                              "conexão pelo cabo."),
                    A("Serviços remotos: ligar", "device-floppy", run(S and (lambda: S.usbnet_services(True)),
                                                                     "Ligando web e Samba...")),
                    A("Serviços remotos: desligar", "x", run(S and (lambda: S.usbnet_services(False)), "Desligando...")),
                    A("Desligar a rede USB", "power", run(S and S.usbnet_stop, "Desligando...")),
                    A("Compatibilidade", "info-circle", lambda: self.worker(
                        (S and S.usbnet_compat) or (lambda: "teste"),
                        lambda r: self.read("Compatibilidade da rede USB", "network", str(r)), busy="Verificando..."))]
        if cid == "calibracao":
            S = omni_sistema if not FAKE else None
            run = lambda fn, busy: (lambda: self.worker(fn if S else (lambda: "teste"), self._sys_done, busy=busy))
            return [A("Iniciar a calibração", "player-play", run(S and S.cal_start, "Começando..."),
                      confirm="Iniciar uma calibração nova?\nA bateria precisa estar cheia e sem o carregador. "
                              "A sessão anterior é apagada."),
                    A("Parar a calibração", "x", run(S and S.cal_stop, "Parando...")),
                    A("Aplicar a curva", "check", run(S and S.cal_apply, "Calculando a curva..."),
                      confirm="Aplicar a curva da última calibração?\nA % da bateria passa a seguir a sua bateria."),
                    A("Voltar à curva de fábrica", "rotate", run(S and S.cal_restore, "Restaurando..."),
                      confirm="Voltar à curva de fábrica?\nA curva calibrada é apagada.", danger=True)]
        if cid == "testar":
            return [A("Escolher o port", "player-play", self.open_picker),
                    A("Limpar avisos de falha", "check", lambda: self.run_tool_toast("clear_port_alerts")), recheck]
        if cid == "backup":
            where = "/roms/backup/omni36os" if FAKE else omni_backup.backup_dir()
            return [tip(A("Exportar", "device-floppy", lambda: self.backup_where("omni36os")),
                        "Salva as configurações do Omni36OS (testes de ports, processador, GPU, RAM e gamma) num "
                        ".tar.gz. Você escolhe onde: cartão do sistema, segundo cartão ou pendrive."),
                    tip(A("Importar", "arrow-back-up", lambda: self.backup_browse("omni36os", where)),
                        "Abre as pastas para escolher um backup. Antes de importar, o que vale agora é salvo como "
                        "\"antes-de-importar\".")]
        if cid == "ajuda":
            return [*([] if FAKE else [Choice("Botão de power", "power", "power", list(omni.POWER_NAMES),
                                              omni.POWER_NAMES)]),
                    A("Manual", "book", lambda: self.read("Manual", "book", omni_help.manual(D.get("at_combos")))),
                    A("Cuidados", "alert-triangle", lambda: self.read("Cuidados", "alert-triangle", omni_help.CUIDADOS)),
                    A("Novidades", "tag", lambda: self.read(f"Novidades · Omni36OS {omni_version()}", "tag",
                                                          omni_help.novidades_text())),
                    A("Créditos", "users", lambda: self.read("Créditos", "users", omni_help.CREDITOS))]
        return [recheck]

    # --- ações ---

    def do_action(self, name, busy="Fazendo..."):
        self.worker(lambda: D.action(name), self._action_done, busy=busy)

    def _action_done(self, res):
        txt = f"Erro: {res}" if isinstance(res, Exception) else (str(res).splitlines() or ["Feito."])[0]
        self.toast = (txt, "problema" if isinstance(res, Exception) else "ok", self.t + 3.5)
        if self.page:
            keep = self.item_sel
            self.items = self.build_items(self.page)
            self.item_sel = min(keep, len(self.items) - 1)
            self.reload_findings()

    def run_info(self, title, tool):
        def done(res):
            self.modal = {"title": title, "text": str(res), "icon": "info-circle", "buttons": ["OK"], "sel": 0}
        self.worker(lambda: D.run(tool), done, busy="Lendo...")

    def busy_game(self):
        if HUB == "jogo":
            self.toast = ("Feche o jogo antes: o Omni36OS está por cima dele", "aviso", self.t + 3.5)
            return True
        return False

    def run_tool_toast(self, tool):
        self.worker(lambda: D.run(tool), self._action_done, busy="Fazendo...")

    def speed_test(self):
        def fn():
            if FAKE:
                return D.run("x")
            return omni_checks.velocidade()

        def done(res):
            if isinstance(res, dict):
                self.findings = res
                self.toast = ("Teste dos cartões concluído", "ok", self.t + 3)
            else:
                self.modal = {"title": "Velocidade", "text": str(res), "icon": "brand-speedtest",
                              "buttons": ["OK"], "sel": 0}
        self.worker(fn, done, busy="Testando os cartões... (até 1 minuto)")

    def show_list(self, title, icon, rows, on_ok, ok_label, start=None):
        """rows: {"head", "tag", "tagc"} (título de grupo) ou {"name", "right", "icon", ...}.
        on_ok(row) roda no A; start é a linha escolhida ao abrir (padrão: a primeira)."""
        items = [i for i, r in enumerate(rows) if "name" in r]
        if not items:
            return False
        self.picker = {"title": title, "icon": icon, "rows": rows,
                       "sel": start if start in items else items[0], "top": 0,
                       "scroll": 0.0, "on_ok": on_ok, "ok_label": ok_label}
        return True

    def picker_input(self, cmd):
        pk = self.picker
        items = [i for i, r in enumerate(pk["rows"]) if "name" in r]
        k = items.index(pk["sel"])
        if pk.get("letters") and cmd in ("l1", "r1"):     # pula para a próxima/anterior letra
            first = lambda i: (pk["rows"][i]["name"][:1] or " ").upper()
            cur = first(pk["sel"])
            if cmd == "r1":
                nxt = next((i for i in items[k:] if first(i) != cur), items[-1])
            else:
                prev = [i for i in items[:k] if first(i) != cur]
                nxt = next((i for i in items if prev and first(i) == first(prev[-1])), items[0])
            pk["sel"] = nxt
            return
        step = {"up": -1, "down": 1, "left": -6, "right": 6, "l1": -6, "r1": 6}.get(cmd)
        if cmd in ("up", "down"):         # passou do fim volta ao começo (e vice-versa)
            pk["sel"] = items[(k + step) % len(items)]
        elif step:                        # pulos de página param na ponta
            pk["sel"] = items[max(0, min(len(items) - 1, k + step))]
        elif cmd == "back":
            self.picker = None
            if pk.get("on_back"):
                pk["on_back"]()
        elif cmd == "ok":
            pk["on_ok"](pk["rows"][pk["sel"]])
        elif cmd == "x" and pk.get("on_x"):
            pk["on_x"](pk["rows"][pk["sel"]])
        elif cmd == "start" and pk.get("on_start"):
            pk["on_start"](pk["rows"][pk["sel"]])

    def draw_picker(self, dt):
        g, pk = self.g, self.picker
        g.rrect(0, 0, W, H, 0, (5, 7, 20, 190), feather=0)
        mx, my, mw, mh = 24, 20, W - 48, H - 40
        g.rrect(mx, my, mw, mh, 22, MODAL_A, MODAL_B)
        g.stroke(mx, my, mw, mh, 22, ink(25))
        a1, a2 = self.accent
        g.rrect(mx + 20, my + 16, 36, 36, 12, a1, a2)
        g.icon(pk["icon"], mx + 28, my + 24, 20, ON_TEXT)
        title = pk["title"]
        while g.measure("Bold", 18, title)[0] > mw - 100 and len(title) > 8:
            title = "…" + title[2:]          # caminhos longos: mostra o fim
        g.text("Bold", 18, title, mx + 68, my + 22, TEXT)
        rows = pk["rows"]
        hs = [34 if "head" in r else 40 for r in rows]
        ty, th = my + 66, mh - 66 - 44
        ys = [sum(hs[:i]) for i in range(len(rows))]
        # rola para manter a linha escolhida visível (com o título do grupo)
        sel_y, sel_h = ys[pk["sel"]], hs[pk["sel"]]
        if sel_y - pk["top"] < 40:
            pk["top"] = max(0, sel_y - 40)
        elif sel_y + sel_h - pk["top"] > th:
            pk["top"] = sel_y + sel_h - th
        pk["scroll"] = approach(pk["scroll"], pk["top"], dt, 18)
        g.clip(mx, ty, mw, th)
        for i, r in enumerate(rows):
            y = ty + ys[i] - pk["scroll"]
            if y + hs[i] < ty or y > ty + th:
                continue
            if "head" in r:
                g.text("SemiBold", 11, r["head"].upper(), mx + 30, y + 12, FAINT)
                if r.get("tag"):
                    tw = g.measure("Bold", 9, r["tag"])[0] + 14
                    g.rrect(mx + mw - 40 - tw, y + 9, tw, 18, 9, alpha(r["tagc"], 60))
                    g.text("Bold", 9, r["tag"], mx + mw - 40 - tw / 2, y + 18.5, TEXT, "c", "m")
                continue
            on = i == pk["sel"]
            if on:
                g.rrect(mx + 16, y + 2, mw - 44, 36, 12, a1, a2)
            x = mx + 30
            if r.get("icon"):
                g.icon(r["icon"], x, y + 11, 18, ON_TEXT if on else MUTED)
                x += 28
            g.text("SemiBold" if on else "Regular", 14, r["name"], x, y + 10, ON_TEXT if on else TEXT)
            if r.get("right"):
                lab, c = r["right"]
                lw = g.measure("SemiBold", 11, lab)[0]
                g.circle(mx + mw - 60 - lw, y + 20, 4, c)
                g.text("SemiBold", 11, lab, mx + mw - 50 - lw, y + 13, ON_TEXT if on else c)
        g.clip()
        total = sum(hs)
        if total > th:
            bh = max(30, th * th / total)
            by = ty + (th - bh) * min(1, pk["scroll"] / max(1, total - th))
            g.rrect(mx + mw - 14, ty, 4, th, 2, ink(18))
            g.rrect(mx + mw - 14, by, 4, bh, 2, alpha(a1, 220))
        self.btn_glyph(mx + 24, my + mh - 32, "A", TEXT)
        g.text("Regular", 12, f"{pk['ok_label']}  ·  " + (pk.get("hint") or ("L1/R1: letra" if pk.get("letters") else
                                                                            "Esquerda/direita: pular")),
               mx + 50, my + mh - 30, MUTED)
        self.btn_glyph(mx + mw - 110, my + mh - 32, "B", TEXT)
        g.text("Regular", 12, "Voltar", mx + mw - 82, my + mh - 30, MUTED)

    # --- ferramentas do Omni36OS ---

    def tool_list(self):
        """Programas de tela cheia que continuam fora do launcher (PortMaster, 351Files)."""
        if FAKE:
            return [{"path": "/opt/system/Tools/PortMaster.sh", "name": "PortMaster",
                     "desc": "Loja de ports (precisa de internet)."}]
        if not getattr(self, "tools_cache", None):
            self.tools_cache = omni_tools.tools()
        return self.tools_cache

    def _ferramentas(self):
        ts = self.tool_list()
        self.tool_count = len(ts) + 1
        out = [("info", "Testar o controle fica em Verificar; senha em Sistema; rede USB e pendrive no card "
                        "USB; calibração em Bateria; overclock em Desempenho.")]
        return {"nivel": "ok", "achados": out, "acoes": []} if FAKE else omni_checks.finish(out, [], {})

    def ask_tool(self, t):
        self.modal = {"title": t["name"], "icon": "adjustments", "sel": 0, "buttons": ["Abrir", "Voltar"],
                      "text": t["desc"] + "\nAbre em tela cheia e o Omni36OS volta quando ela fechar.",
                      "fn": lambda: self.run_tool(t)}

    def run_tool(self, t):
        if self.busy_game():
            return
        if FAKE:
            self.toast = (f"Abriria {t['name']}", "ok", self.t + 3)
            return
        omni.write_text(omni.HANDOFF, f"tool:ferramentas:{t['path']}")
        self.running = False          # o launch-direct.sh roda o programa e reabre o Omni36OS

    def native(self, name, busy="Fazendo..."):
        """Ferramenta reescrita em Python (omni_tools.NATIVE): roda aqui e mostra o resultado."""
        fn = (lambda: "teste") if FAKE else (lambda: omni_tools.run_native(name))
        self.worker(fn, self._sys_done, busy=busy)

    def _sys_done(self, res):
        """Resultado de uma ferramenta do sistema: aviso curto ou janela, e a página relê o estado."""
        txt = f"Erro: {res}" if isinstance(res, Exception) else str(res)
        bad = isinstance(res, Exception) or txt.startswith(("Erro", "Não", "Falta", "Desligue", "Tire", "Carregue",
                                                            "Poucas", "Pare", "Ligue", "O PC"))
        if len(txt) > 60:
            self.modal = {"title": "Pronto" if not bad else "Atenção", "icon": "alert-triangle" if bad else "check",
                          "buttons": ["OK"], "sel": 0, "text": txt}
        else:
            self.toast = (txt, "aviso" if bad else "ok", self.t + 3.5)
        if self.page:
            self.reload_findings(quiet=True)

    def live_refresh(self):
        """Subpáginas com estado vivo (rede USB, calibração) se releem sozinhas."""
        every = LIVE.get(self.page)
        if not every or self.busy or self.t < getattr(self, "live_at", 0):
            return
        self.live_at = self.t + every
        self.reload_findings(quiet=True)

    # --- teclado na tela ---

    KEYS = ["1234567890", "qwertyuiop", "asdfghjkl-", "zxcvbnm_.@", ["ABC", "espaço", "apagar", "OK"]]

    def keyboard(self, title, on_done, secret=False, value="", hint="", locked=False):
        """Teclado do Omni36OS: direcional escolhe, A digita, B apaga, Start confirma, Select cancela.
        locked: tela da trava (não dá para cancelar; o power abre Energia)."""
        self.kbd = {"title": title, "value": value, "secret": secret, "fn": on_done, "r": 1, "c": 0,
                    "shift": False, "hint": hint, "locked": locked}

    def kbd_row(self, r):
        row = self.KEYS[r]
        if isinstance(row, str):
            return list(row.upper() if self.kbd["shift"] else row)
        return ["abc" if self.kbd["shift"] else "ABC"] + row[1:]

    def kbd_input(self, cmd):
        k = self.kbd
        if cmd in ("up", "down"):
            old = len(self.kbd_row(k["r"]))
            k["r"] = (k["r"] + (1 if cmd == "down" else -1)) % len(self.KEYS)
            new = len(self.kbd_row(k["r"]))
            k["c"] = min(new - 1, round(k["c"] * (new - 1) / max(1, old - 1)))
        elif cmd in ("left", "right"):
            k["c"] = (k["c"] + (1 if cmd == "right" else -1)) % len(self.kbd_row(k["r"]))
        elif cmd == "back":
            k["value"] = k["value"][:-1]
        elif cmd == "select":
            if not k.get("locked"):   # travado: nada (Energia é pelo botão de power)
                self.kbd = None
        elif cmd == "start":
            self.kbd = None
            k["fn"](k["value"])
        elif cmd == "ok":
            key = self.kbd_row(k["r"])[k["c"]]
            if key in ("ABC", "abc"):
                k["shift"] = not k["shift"]
            elif key == "espaço":
                k["value"] += " "
            elif key == "apagar":
                k["value"] = k["value"][:-1]
            elif key == "OK":
                self.kbd = None
                k["fn"](k["value"])
            elif len(k["value"]) < 64:
                k["value"] += key

    def draw_keyboard(self, dt):
        g, k = self.g, self.kbd
        a1, a2 = self.accent
        if k.get("locked"):               # travado: nada do que está atrás aparece
            self.draw_bg(dt)
        else:
            g.rrect(0, 0, W, H, 0, (5, 7, 20, 190), feather=0)
        mx, my, mw, mh = 40, 40, W - 80, H - 80
        g.rrect(mx, my, mw, mh, 22, MODAL_A, MODAL_B)
        g.stroke(mx, my, mw, mh, 22, ink(25))
        g.rrect(mx + 20, my + 16, 36, 36, 12, a1, a2)
        g.icon("lock" if k.get("locked") else "keyboard", mx + 28, my + 24, 20, ON_TEXT)
        g.text("Bold", 17, k["title"], mx + 68, my + 23, TEXT)
        # campo
        shown = "•" * len(k["value"]) if k["secret"] else k["value"]
        g.rrect(mx + 20, my + 64, mw - 40, 40, 12, ink(16))
        g.stroke(mx + 20, my + 64, mw - 40, 40, 12, alpha(a1, 160))
        while shown and g.measure("SemiBold", 17, shown)[0] > mw - 80:
            shown = shown[1:]
        tw = g.text("SemiBold", 17, shown, mx + 34, my + 84.5, TEXT, "l", "m") if shown else 0
        if int(self.t * 2) % 2 == 0:
            g.rrect(mx + 36 + tw, my + 74, 2, 21, 1, a1)
        if k["hint"] and not k["value"]:
            g.text("Regular", 13, k["hint"], mx + 44, my + 84.5, FAINT, "l", "m")
        # teclas
        ky, kh, gap = my + 118, 34, 6
        for r in range(len(self.KEYS)):
            row = self.kbd_row(r)
            if r < len(self.KEYS) - 1:
                ws = [(mw - 40 - gap * (len(row) - 1)) / len(row)] * len(row)
            else:
                unit = (mw - 40 - gap * (len(row) - 1)) / 7
                ws = [unit, unit * 3, unit, unit * 2]
            x = mx + 20
            for c, key in enumerate(row):
                on = r == k["r"] and c == k["c"]
                act = key == "abc"
                if on:
                    g.rrect(x, ky, ws[c], kh, 10, a1, a2)
                else:
                    g.rrect(x, ky, ws[c], kh, 10, alpha(a1, 70) if act else ink(18))
                g.text("SemiBold", 15 if len(key) == 1 else 12, key, x + ws[c] / 2, ky + kh / 2 + 0.5,
                       ON_TEXT if on else TEXT, "c", "m")
                x += ws[c] + gap
            ky += kh + gap
        self.draw_footer_at(my + mh - 30, [("A", "Digitar", TEXT), ("B", "Apagar", TEXT),
                                           ("START", "Confirmar", TEXT),
                                           *([] if k.get("locked") else [("SELECT", "Cancelar", TEXT)])], mx + 22)

    def draw_footer_at(self, y, hints, x):
        g = self.g
        for letter, label, c in hints:
            if letter in ("A", "B"):
                self.btn_glyph(x, y - 2, letter, c)
                w = 24
            else:
                pw = g.measure("Bold", 9, letter)[0] + 12
                g.rrect(x, y, pw, 17, 8, ink(40))
                g.text("Bold", 9, letter, x + pw / 2, y + 9, TEXT, "c", "m")
                w = pw + 6
            x += w + g.text("Medium", 12, label, x + w, y + 8.5, MUTED, "l", "m") + 16

    def ask_password(self):
        def second(new):
            if len(new) < 3:
                self.toast = ("A senha precisa de pelo menos 3 letras", "aviso", self.t + 3.5)
                return

            def check(again):
                if again != new:
                    self.toast = ("As duas senhas não batem: nada mudou", "aviso", self.t + 3.5)
                    return
                fn = (lambda: "teste") if FAKE else (lambda: omni_sistema.change_password(new))
                self.worker(fn, self._sys_done, busy="Trocando a senha...")
            self.keyboard("Repita a nova senha", check, secret=True)
        self.keyboard("Nova senha do usuário ark", second, secret=True, hint="SSH, Samba e SFTP usam esta senha")

    # --- jogador, trava e Samba ---

    def first_screens(self):
        """No boot: a trava (se ligada) e depois o nome do jogador (só na primeira vez)."""
        def after_lock():
            if not self.player and HUB in ("boot", ""):
                self.ask_name(first=True)
        locked = (os.environ.get("OMNI_TRAVA") == "1") if FAKE else omni_sistema.lock_on()
        if locked and RESUME == "":
            self.lock_screen(after_lock)
        else:
            after_lock()

    def ask_reset(self):
        def go():
            def done(res):
                self.player = ""
                apply_theme("escuro")
                self.g.flush()
                self.open_page("tela")
                self.toast = (str(res), "ok", self.t + 3)
                self.ask_name(first=True)
            self.worker((lambda: "Sistema zerado.") if FAKE else omni_sistema.reset_custom, done, busy="Zerando...")
        self.warn("Redefinir o sistema", "Volta o Omni36OS ao primeiro boot: apaga o nome do jogador, a trava por "
                  "senha e o tema, desliga a memória extra (zram) e volta processador (Equilibrado, 1296 MHz), "
                  "GPU (520 MHz), atalhos (FN + X, FN + B, FN + Y, todos ligados) e botão de power ao padrão.", go, secs=5,
                  risk="O nome e a senha da trava somem; o Omni36OS pergunta o nome de novo. Ports, jogos, testes e as "
                       "senhas do sistema e do Samba não mudam.",
                  undo="Não tem volta automática: ajuste de novo em Sistema. Se exportou um backup antes, Backup > "
                       "Importar devolve nome, tema, atalhos, processador e GPU.")

    def lock_screen(self, then):
        def check(pw):
            ok = (pw == os.environ.get("OMNI_TRAVA_SENHA", "1234")) if FAKE else omni_sistema.lock_check(pw)
            if ok:
                self.toast = (f"Bem-vindo de volta, {self.player}!" if self.player else "Destravado", "ok",
                              self.t + 3)
                then()
            else:
                self.toast = ("Senha errada", "problema", self.t + 3)
                self.lock_screen(then)
        self.keyboard("Console travado: digite a senha", check, secret=True, locked=True,
                      hint="Esqueceu? Veja EASYROMS/senha/senha.txt no PC")

    def ask_name(self, first=False):
        def done(name):
            name = " ".join(name.split())[:20]
            if not name:
                if first:
                    self.toast = ("Sem nome por enquanto: dá para pôr depois em Ajuda", "ok", self.t + 4)
                return
            self.player = name if FAKE else omni_sistema.set_player_name(name)
            self.toast = (f"Prazer, {self.player}!", "ok", self.t + 3.5)
            if self.page:
                keep = self.item_sel
                self.items = self.build_items(self.page)
                self.item_sel = min(keep, len(self.items) - 1)
        self.keyboard("Qual é o seu nome?" if first else "Nome do jogador", done, value=self.player,
                      hint="Aparece na saudação do menu")

    # --- Wi-Fi ---

    def wifi_run(self, fn, busy):
        def done(res):
            self._sys_done(res)
            if self.page == "wifi":
                keep = self.item_sel
                self.items = self.build_items("wifi")
                self.item_sel = min(keep, len(self.items) - 1)
                self.reload_findings(quiet=True)
        self.worker(fn, done, busy=busy)

    def wifi_toggle(self, on):
        if FAKE:
            self.fake_wifi = on
        self.wifi_run((lambda: "Wi-Fi ligado." if on else "Wi-Fi desligado.") if FAKE else
                      (lambda: omni_sistema.wifi_set(on)), "Ligando o Wi-Fi..." if on else "Desligando o Wi-Fi...")

    def wifi_connect(self, rede, senha=None):
        self.wifi_run((lambda: f"Conectado a {rede}. IP: 192.168.0.42") if FAKE else
                      (lambda: omni_sistema.wifi_connect(rede, senha)), f"Conectando a {rede}... (até 45 s)")

    def wifi_scan(self):
        def done(nets):
            if isinstance(nets, Exception) or not nets:
                self.toast = ("Nenhuma rede encontrada. O Wi-Fi está ligado?", "aviso", self.t + 3.5)
                return
            rows = [{"name": n["rede"], "icon": "lock" if n["senha"] else "wifi", "net": n,
                     "right": ("Conectada" if n["atual"] else "Salva" if n["salva"] else f"{n['sinal']}%", MUTED)}
                    for n in nets]

            def ok(row):
                n = row["net"]
                self.picker = None
                if n["senha"] and not n["salva"]:
                    self.keyboard(f"Senha de {n['rede']}", lambda pw: pw and self.wifi_connect(n["rede"], pw),
                                  secret=True, hint="Digite a senha da rede")
                else:
                    self.wifi_connect(n["rede"])
            self.show_list("Redes por perto", "wifi", rows, ok, "Conectar")
        fake = [{"rede": "Casa", "sinal": 72, "senha": True, "atual": True, "salva": True},
                {"rede": "Vizinho 5G", "sinal": 40, "senha": True, "atual": False, "salva": False},
                {"rede": "Café aberto", "sinal": 28, "senha": False, "atual": False, "salva": False}]
        self.worker((lambda: fake) if FAKE else omni_sistema.wifi_scan, done, busy="Procurando redes...")

    def wifi_saved(self):
        def done(names):
            if isinstance(names, Exception) or not names:
                self.toast = ("Nenhuma rede salva ainda", "aviso", self.t + 3.5)
                return
            rows = [{"name": n, "icon": "wifi"} for n in names]

            def ok(row):
                self.picker = None
                self.modal = {"title": row["name"], "icon": "wifi", "sel": 0, "buttons": ["Conectar", "Esquecer", "Voltar"],
                              "text": "Conectar a esta rede ou esquecê-la (a senha salva é apagada)?",
                              "fns": [lambda: self.wifi_connect(row["name"]),
                                      lambda: self.wifi_run((lambda: f"{row['name']} esquecida.") if FAKE else
                                                            (lambda: omni_sistema.wifi_forget(row["name"])),
                                                            "Esquecendo..."),
                                      lambda: None]}
            self.show_list("Redes salvas", "device-floppy", rows, ok, "Escolher")
        self.worker((lambda: ["Casa", "Trabalho"]) if FAKE else omni_sistema.wifi_saved, done, busy="Lendo as redes...")

    def ask_samba(self):
        def first(new):
            if len(new) < 3:
                self.toast = ("A senha precisa de pelo menos 3 letras", "aviso", self.t + 3.5)
                return

            def again(rep):
                if rep != new:
                    self.toast = ("As duas senhas não batem: nada mudou", "aviso", self.t + 3.5)
                    return
                fn = (lambda: "teste") if FAKE else (lambda: omni_sistema.samba_password(new))
                self.worker(fn, self._sys_done, busy="Redefinindo...")
            self.keyboard("Repita a senha do Samba", again, secret=True)
        self.keyboard("Nova senha do Samba", first, secret=True, hint="Para abrir as pastas do console pelo PC")

    def ask_lock(self):
        locked = (os.environ.get("OMNI_TRAVA") == "1") if FAKE else omni_sistema.lock_on()

        def refresh(res):
            self._sys_done(res)
            if self.page:
                keep = self.item_sel
                self.items = self.build_items(self.page)
                self.item_sel = min(keep, len(self.items) - 1)
        if locked:
            def off():
                def check(pw):
                    ok = True if FAKE else omni_sistema.lock_check(pw)
                    if not ok:
                        self.toast = ("Senha errada: a trava continua", "problema", self.t + 3.5)
                        return
                    self.worker((lambda: "teste") if FAKE else omni_sistema.lock_clear, refresh, busy="Desligando...")
                self.keyboard("Senha atual da trava", check, secret=True)
            self.modal = {"title": "Trava por senha", "icon": "lock", "sel": 0, "buttons": ["Desligar", "Voltar"],
                          "text": "A trava está ligada: o console pede a senha ao ligar.\nA senha fica em "
                                  "EASYROMS/senha/senha.txt (abra o cartão no PC se esquecer).", "fn": off}
            return

        def first(pw):
            if len(pw) < 3:
                self.toast = ("A senha precisa de pelo menos 3 letras", "aviso", self.t + 3.5)
                return

            def again(rep):
                if rep != pw:
                    self.toast = ("As duas senhas não batem: nada mudou", "aviso", self.t + 3.5)
                    return
                self.worker((lambda: "teste") if FAKE else (lambda: omni_sistema.lock_set(pw)), refresh,
                            busy="Ligando a trava...")
            self.keyboard("Repita a senha da trava", again, secret=True)
        self.modal = {"title": "Trava por senha", "icon": "lock", "sel": 0, "buttons": ["Ligar", "Voltar"],
                      "text": "Ao ligar o console, o Omni36OS pede esta senha antes de mostrar os jogos.\n"
                              "Ela fica guardada em texto simples em EASYROMS/senha/senha.txt, para você "
                              "recuperar pelo PC. Apagar esse arquivo desliga a trava.",
                      "fn": lambda: self.keyboard("Senha da trava", first, secret=True)}

    # --- teste do controle ---

    PAD_NAMES = {0: "A", 1: "B", 2: "X", 3: "Y", 4: "SELECT", 6: "START", 7: "L3", 8: "R3", 9: "L1", 10: "R1",
                 11: "CIMA", 12: "BAIXO", 13: "ESQUERDA", 14: "DIREITA", 5: "GUIDE", 15: "MISC"}

    def open_pad(self):
        self.pad = {"down": set(), "axes": [0] * 6, "last": "Aperte qualquer botão", "exit_at": None, "count": 0}

    def pad_event(self, kind, num, val, now):
        p = self.pad
        if kind == "btn":
            if val:
                p["down"].add(num)
                p["count"] += 1
                p["last"] = f"{self.PAD_NAMES.get(num, f'botão {num}')}  (SDL {num})"
            else:
                p["down"].discard(num)
            both = {4, 6} <= p["down"]
            p["exit_at"] = (p["exit_at"] or now + 1.0) if both else None
        else:
            p["axes"][num] = val
            if num >= 4 and abs(val) > 8000:
                p["last"] = f"{'L2' if num == 4 else 'R2'}  (eixo {num}: {val})"

    def pad_tick(self, now):
        p = self.pad
        if p["exit_at"] and now >= p["exit_at"]:
            self.pad = None
            self.held.clear()
            self.toast = (f"Teste do controle: {p['count']} toques", "ok", self.t + 3)

    def draw_pad(self, dt):
        g, p = self.g, self.pad
        a1, a2 = self.accent
        g.rrect(0, 0, W, H, 0, (5, 7, 20, 200), feather=0)
        mx, my, mw, mh = 24, 20, W - 48, H - 40
        g.rrect(mx, my, mw, mh, 22, MODAL_A, MODAL_B)
        g.stroke(mx, my, mw, mh, 22, ink(25))
        g.rrect(mx + 20, my + 16, 36, 36, 12, a1, a2)
        g.icon("device-gamepad-2", mx + 28, my + 24, 20, ON_TEXT)
        g.text("Bold", 18, "Testar o controle", mx + 68, my + 22, TEXT)
        d = p["down"]
        lit = lambda b: (a1 if b in d else ink(22))
        txt = lambda b: ON_TEXT if b in d else MUTED
        # ombros
        ax = p["axes"]
        for x, b, lab in ((mx + 40, 9, "L1"), (mx + mw - 130, 10, "R1")):
            g.rrect(x, my + 70, 90, 26, 10, lit(b))
            g.text("Bold", 12, lab, x + 45, my + 83.5, txt(b), "c", "m")
        for x, k, lab in ((mx + 140, 4, "L2"), (mx + mw - 230, 5, "R2")):
            on = ax[k] > 8000
            g.rrect(x, my + 70, 90, 26, 10, a1 if on else ink(22))
            g.text("Bold", 12, lab, x + 45, my + 83.5, ON_TEXT if on else MUTED, "c", "m")
        # direcional
        cx, cy = mx + 120, my + 190
        for b, dx, dy in ((11, 0, -1), (12, 0, 1), (13, -1, 0), (14, 1, 0)):
            g.rrect(cx - 18 + dx * 38, cy - 18 + dy * 38, 36, 36, 9, lit(b))
        g.rrect(cx - 18, cy - 18, 36, 36, 9, ink(12))
        # ABXY (posição do R36S: A à direita, B embaixo, X em cima, Y à esquerda)
        bx, by = mx + mw - 120, my + 190
        for b, dx, dy in ((0, 1, 0), (1, 0, 1), (2, 0, -1), (3, -1, 0)):
            g.circle(bx + dx * 40, by + dy * 40, 19, lit(b))
            g.text("Bold", 14, self.PAD_NAMES[b], bx + dx * 40, by + dy * 40 + 0.5, txt(b), "c", "m")
        # select / start
        for x, b in ((W / 2 - 80, 4), (W / 2 + 10, 6)):
            g.rrect(x, my + 150, 70, 22, 11, lit(b))
            g.text("Bold", 10, self.PAD_NAMES[b], x + 35, my + 161.5, txt(b), "c", "m")
        # analógicos
        for k, (sx, b) in enumerate(((W / 2 - 75, 7), (W / 2 + 75, 8))):
            sy = my + 290
            g.circle(sx, sy, 44, ink(14))
            g.stroke(sx - 44, sy - 44, 88, 88, 44, ink(30))
            g.circle(sx, sy, 44 * 0.12, ink(20))            # zona morta aproximada
            vx, vy = ax[k * 2] / 32768, ax[k * 2 + 1] / 32768
            g.circle(sx + vx * 34, sy + vy * 34, 15, a1 if b in d else a2)
            g.text("Regular", 10, f"{vx:+.2f} {vy:+.2f}", sx, sy + 56, MUTED, "c")
        g.text("SemiBold", 13, p["last"], W / 2, my + 222, TEXT, "c", "m")
        g.text("Regular", 12, "Segure SELECT + START por 1 segundo para sair", W / 2, my + mh - 24, MUTED, "c", "m")

    # --- arquivos ---

    def open_files(self, path=None, start=None):
        if path is None:
            roots = [r for r in (["/roms", "/roms2", "/mnt/usbdrive"] if not FAKE else ["/roms", "/roms2"])
                     if FAKE or os.path.ismount(r) or os.path.isdir(r)]
            names = {"/roms": "Cartão do sistema (/roms)", "/roms2": "Cartão de jogos (/roms2)",
                     "/mnt/usbdrive": "Pendrive (/mnt/usbdrive)"}
            rows = [{"name": names[r], "icon": "device-sd-card" if r != "/mnt/usbdrive" else "usb", "path": r,
                     "dir": True} for r in roots]
            self.files_at = None
            self.show_list("Arquivos", "folder", rows, lambda r: self.open_files(r["path"]), "Abrir")
            self.picker["hint"] = "Escolha um cartão"
            return
        self.files_at = path
        items = ([("ports", True, 0), ("Daytona USA.sh", False, 2400)] if FAKE else omni_sistema.listdir(path))
        rows = [{"name": "..", "icon": "arrow-up", "up": True}]
        rows += [{"name": n, "icon": "folder" if d else "file", "dir": d, "path": os.path.join(path, n),
                  "right": None if d else (omni_sistema.human(sz) if not FAKE else f"{sz} B", MUTED)}
                 for n, d, sz in items]
        clip = getattr(self, "clip", None)
        self.show_list(path, "folder", rows, self.file_ok, "Abrir", start)
        pk = self.picker
        pk["on_back"] = lambda: self.file_up()
        pk["on_x"] = self.file_menu
        pk["on_start"] = self.folder_menu
        pk["hint"] = ("START: colar " + ("e mais" if clip else "") if clip else "X: opções  ·  START: pasta")

    def file_up(self):
        path = self.files_at
        if not path or path in ("/roms", "/roms2", "/mnt/usbdrive"):
            self.open_files()
            return
        parent = os.path.dirname(path)
        self.open_files(parent)
        rows = self.picker["rows"]
        self.picker["sel"] = next((i for i, r in enumerate(rows) if r.get("path") == path), 0)

    def file_ok(self, r):
        if r.get("up"):
            self.file_up()
        elif r.get("dir"):
            self.open_files(r["path"])
        else:
            self.file_menu(r)

    def _fs(self, fn, busy="Fazendo..."):
        here = self.files_at
        sel = self.picker["sel"] if self.picker else 0

        def done(res):
            txt = f"Erro: {res}" if isinstance(res, Exception) else str(res)
            self.toast = (txt, "problema" if isinstance(res, Exception) else "ok", self.t + 3.5)
            self.open_files(here, sel)
        self.worker((lambda: "teste") if FAKE else fn, done, busy=busy)

    def file_menu(self, r):
        if r.get("up") or "path" not in r:
            return
        path, name = r["path"], os.path.basename(r["path"])

        def rename():
            self.keyboard(f"Novo nome para {name}", lambda new: self._fs(lambda: omni_sistema.fs_rename(path, new)),
                          value=name)

        def delete():
            self.ask(f"Apagar {name}?\n" + ("A pasta e tudo dentro dela somem." if r.get("dir") else
                                            "O arquivo some de vez."),
                     lambda: self._fs(lambda: omni_sistema.fs_delete(path), "Apagando..."), danger=True)

        def mark(move):
            self.clip = (path, move)
            self.toast = (("Recortado: " if move else "Copiado: ") + name + ". Vá até a pasta e aperte START",
                          "ok", self.t + 4)
            self.open_files(self.files_at, self.picker["sel"] if self.picker else None)
        self.picker = None
        back = lambda: self.open_files(self.files_at)
        self.modal = {"title": name, "icon": "folder" if r.get("dir") else "file", "sel": 0,
                      "buttons": ["Copiar", "Mover", "Renomear", "Apagar"],
                      "text": ("Pasta" if r.get("dir") else f"Arquivo, {r['right'][0]}") + f"\n{path}",
                      "fns": [lambda: mark(False), lambda: mark(True), rename, delete], "on_back": back}

    def folder_menu(self, _r=None):
        here = self.files_at
        if not here:
            return
        clip = getattr(self, "clip", None)
        btns, fns = [], []
        if clip:
            src, move = clip

            def paste():
                self.clip = None
                self._fs(lambda: omni_sistema.fs_paste(src, here, move), "Movendo..." if move else "Copiando...")
            btns.append("Colar aqui")
            fns.append(paste)
        btns.append("Nova pasta")
        fns.append(lambda: self.keyboard("Nome da pasta nova", lambda n: self._fs(lambda: omni_sistema.fs_mkdir(here, n))))
        btns.append("Voltar")
        fns.append(lambda: self.open_files(here))
        self.picker = None
        text = f"Pasta atual: {here}"
        if clip:
            text += f"\n{'Mover' if clip[1] else 'Copiar'}: {os.path.basename(clip[0])}"
        self.modal = {"title": "Esta pasta", "icon": "folder-plus", "sel": 0, "buttons": btns, "fns": fns,
                      "text": text, "on_back": lambda: self.open_files(here)}

    # --- biblioteca (tela inicial) ---

    def lib_lists(self):
        """[(título, ícone, [(sistema, jogo)])]: uma lista só, com todos os ports em ordem de nome."""
        pairs = [(s, g) for s in self.games() for g in s["games"]]
        pairs.sort(key=lambda p: (not p[1].get("fav"), p[1]["name"].lower()))   # favoritos primeiro
        return [("Ports", "device-gamepad-2", pairs)] if pairs else []

    def library_input(self, cmd):
        lists, lb = self.lib_lists(), self.lib
        if cmd == "back":                 # B: de volta aos cards, com Ports escolhido
            self.view = "menu"
            self.sel = 0
            return
        if not lists:
            return
        lb["sys"] = 0
        games = lists[0][2]
        if cmd in ("up", "down"):
            lb["game"] = (lb["game"] + (1 if cmd == "down" else -1)) % len(games)
        elif cmd in ("left", "right"):     # página de 10 (para nas pontas)
            lb["game"] = max(0, min(len(games) - 1, lb["game"] + (10 if cmd == "right" else -10)))
        elif cmd in ("l1", "r1"):
            first = lambda i: (games[i][1]["name"][:1] or " ").upper()
            k, cur = lb["game"], first(lb["game"])
            if cmd == "r1":
                lb["game"] = next((i for i in range(k, len(games)) if first(i) != cur), len(games) - 1)
            else:
                prev = [i for i in range(k) if first(i) != cur]
                lb["game"] = next((i for i in range(len(games)) if prev and first(i) == first(prev[-1])), 0)
        elif cmd == "ok":
            s, g = games[min(lb["game"], len(games) - 1)]
            self.open_sheet(s, g)

    def meta(self, name, path=""):
        """Ficha do jogo (cache em memória): pasta info do port + PortMaster/Steam.
        Pede a busca na internet uma vez, se houver Wi-Fi; a pasta info manda sobre ela."""
        cache = self.__dict__.setdefault("meta_cache", {})
        if name not in cache:
            net = omni_meta.cached(name)
            loc = omni_meta.local(path)
            cache[name] = (net, dict(net or {}, **loc) if loc else net)
        net, info = cache[name]
        if net is None and self.status.get("wifi") and name not in self.__dict__.setdefault("meta_tried", set()):
            self.meta_tried.add(name)
            omni_meta.want(name, path, lambda n: cache.pop(n, None))   # ao terminar, relê do disco
        return info

    def draw_library(self, dt, fade):
        g, lb = self.g, self.lib
        lists = self.lib_lists()
        a1, a2 = self.accent
        if not lists:
            g.text("Bold", 20, "Nenhum port encontrado", W / 2, 200, TEXT, "c")
            g.text("Regular", 13, "Instale ports pelo PortMaster (Ferramentas) ou copie para a pasta ports.",
                   W / 2, 232, MUTED, "c")
            self.draw_footer([("B", "Voltar", TEXT)])
            return
        title, icon, games = lists[0]
        lb["sys"] = 0
        lb["game"] = min(lb["game"], len(games) - 1)
        rh, bot_y = 30, H - 44
        # jogos (esquerda)
        gx, gw = 16, 250
        g.text("Bold", 20, title, gx + 4, 58, TEXT)
        g.text("Regular", 12, f"{len(games)} Jogos", gx + 6 + g.measure("Bold", 20, title)[0] + 10, 66, MUTED)
        ly, lh = 92, bot_y - 92
        g.rrect(gx, ly - 6, gw, lh + 6, 18, alpha(GLASS, 14 * fade))
        vis = int(lh // rh)
        want = max(0, min(lb["game"] - vis // 2, len(games) - vis))
        lb["top"] = approach(lb.get("top", 0.0), want * rh, dt, 18)
        g.clip(gx, ly, gw, lh)
        first_row = max(0, int(lb["top"] // rh) - 1)
        for i in range(first_row, min(len(games), first_row + vis + 3)):
            s, game = games[i]
            y = ly + i * rh - lb["top"]
            on = i == lb["game"]
            if on:
                g.rrect(gx + 6, y, gw - 12, rh - 2, 10, a1, a2)
            name = game["name"]
            while g.measure("Regular", 14, name)[0] > gw - 50 and len(name) > 6:
                name = name[:-2]
            if name != game["name"]:
                name = name.rstrip() + "…"
            g.text("SemiBold" if on else "Regular", 14, name, gx + 16, y + 6, ON_TEXT if on else TEXT)
            if game.get("fav"):
                g.icon("check", gx + gw - 30, y + 7, 14, ON_TEXT if on else FAINT)   # favorito
        g.clip()
        if len(games) > vis:
            bh = max(24, lh * vis / len(games))
            by = ly + (lh - bh) * min(1, lb["top"] / max(1, (len(games) - vis) * rh))
            g.rrect(gx + gw - 5, by, 3, bh, 2, alpha(a1, 220))
        # ficha do jogo (direita): capa e dados da Steam + o que o console sabe
        s, game = games[lb["game"]]
        info = self.meta(game["name"], game.get("path", ""))
        px, py, pw, ph = gx + gw + 14, 50, W - (gx + gw + 14) - 16, bot_y - 50
        g.rrect(px, py, pw, ph, 18, alpha(GLASS, 14 * fade))
        cw_, ch_ = pw - 24, round((pw - 24) * 215 / 460)
        cover = info and info.get("capa")
        g.rrect(px + 12, py + 12, cw_, ch_, 12, ink(12))
        if not (cover and g.picture(cover, px + 12, py + 12, cw_, ch_, 255 * fade)):
            g.icon("device-gamepad-2", px + 12 + cw_ / 2 - 24, py + 12 + ch_ / 2 - 24, 48, FAINT)
        y = py + ch_ + 22
        name = (info or {}).get("nome") or game["name"]
        for ln in g.wrap("Bold", 17, name, pw - 28)[:2]:
            g.text("Bold", 17, ln, px + 14, y, TEXT)
            y += 22
        sub = " · ".join(x for x in ((info or {}).get("estudio", "")[:30], (info or {}).get("lancamento", "")) if x)
        if sub:
            g.text("Medium", 11, sub, px + 14, y + 2, a1)
            y += 18
        if (info or {}).get("generos"):
            g.text("Regular", 11, info["generos"], px + 14, y + 2, MUTED)
            y += 18
        desc = (info or {}).get("descricao") or game.get("desc") or (
            "Buscando a ficha..." if info is None and self.status.get("wifi") else
            "Sem ficha: ligue o Wi-Fi para buscar." if info is None else "Sem ficha no PortMaster ou na Steam.")
        local = []
        if (info or {}).get("porter"):
            local.append("Port: " + info["porter"][:28])
        if info and "pronto" in info and not info["pronto"]:
            local.append("Precisa dos arquivos do jogo")
        if game.get("plays"):
            local.append(f"Jogado {game['plays']} vez(es)")
        if game.get("time"):
            local.append(f"{game['time'] // 3600}h{game['time'] % 3600 // 60:02d}")
        room = int((py + ph - (30 if local else 12) - y - 4) // 17)
        lines = g.wrap("Regular", 12, desc, pw - 28)
        for k, ln in enumerate(lines[:max(0, room)]):
            if k == room - 1 and len(lines) > room:
                ln = ln.rstrip(" .,") + "…"
            g.text("Regular", 12, ln, px + 14, y + 4 + 17 * k, TEXT)
        if local:
            ln = " · ".join(local)
            while g.measure("Medium", 11, ln)[0] > pw - 28 and len(local) > 1:
                local.pop(0)                  # sem espaço: fica o mais útil (o fim)
                ln = " · ".join(local)
            g.text("Medium", 11, ln, px + 14, py + ph - 24, FAINT)
        self.draw_footer([("A", "Ver o jogo", TEXT), ("LR", "Página", MUTED), ("L1 / R1", "Letra", MUTED),
                          ("B", "Voltar", MUTED)])

    def power_menu(self, button=False):
        """Botão de power (Cancelar vem primeiro e apertar o power
        de novo desliga: o power_button.py vê o pedido em aberto)."""
        rows = [{"name": "Suspender", "icon": "clock", "do": "suspend"},
                {"name": "Reiniciar o console", "icon": "refresh", "do": "reboot"},
                {"name": "Desligar o console", "icon": "power", "do": "poweroff"}]
        if HUB == "jogo" or os.environ.get("OMNI_JOGO") == "1":   # aberto por cima de um jogo
            hud, cap = flag(HUD_FLAG) == "1", flag(CAP_FLAG) not in ("", "0")
            rows = [{"name": "Esconder o contador de FPS" if hud else "Mostrar o contador de FPS", "icon": "gauge",
                     "do": "hud"},
                    {"name": "Tirar o limite de 30 FPS" if cap else "Limitar a 30 FPS", "icon": "battery-2",
                     "do": "cap"},
                    {"name": "Captura de tela", "icon": "device-tv", "do": "shot"},
                    {"name": "Fechar o jogo", "icon": "x", "do": "close"}] + rows
        if button:
            rows = [{"name": "Cancelar", "icon": "x", "do": "cancel"}] + rows

        def done():
            try:
                os.remove(POWER_PRESS)
            except OSError:
                pass

        def back():
            done()
            if getattr(self, "power_return", False):
                self.quit()           # volta para o jogo (que descongela)

        def go(r):
            self.picker = None
            if r["do"] == "cancel":
                return back()
            done()
            if r["do"] in ("hud", "cap", "shot", "close"):
                return self.game_action(r["do"])
            if r["do"] != "cancel" and not FAKE:
                omni.power({"what": r["do"]})
        self.show_list("Energia", "power", rows, go, "Escolher")
        if self.picker and button:
            self.picker["on_back"] = back
            for path in (POWER_PRESS, POWER_PENDING):   # o menu está na tela: outro toque desliga
                try:
                    if path == POWER_PRESS:
                        with open(path, "w") as f:
                            f.write(str(os.getpid()))
                    else:
                        os.remove(path)
                except OSError:
                    pass

    def game_action(self, what):
        """Menu de energia por cima de um jogo: o contador, o limite e a captura são do hud/omni_hud.so
        (arquivos em /dev/shm, valem quando o jogo volta); fechar encerra o jogo congelado."""
        if FAKE:
            self.toast = (f"Teste: {what}", "ok", self.t + 3)
            return
        if what == "hud":
            put_flag(HUD_FLAG, "0" if flag(HUD_FLAG) == "1" else "1")
        elif what == "cap":
            put_flag(CAP_FLAG, "0" if flag(CAP_FLAG) not in ("", "0") else omni_combos.CAP_FPS)
        elif what == "shot":
            put_flag(SHOT_FLAG, int(time.time() * 1000))   # o jogo volta e salva o primeiro quadro
        elif what == "close":
            import omni_atalho
            omni_atalho.close_game(omni_atalho.game_pids())
        self.quit()                    # volta para o jogo (que descongela) ou para o Omni36OS

    def power_check(self):
        """Sinais do power_button.py: USR1 abre o menu de energia, USR2 mostra o aviso do pânico."""
        if self.loading:
            return                    # depois da tela de abertura, para o aviso não sumir nela
        if self.want_power:
            self.want_power = False
            self.sheet = self.danger = self.modal = None
            self.power_menu(button=True)
        if self.want_msg or self.t - self.msg_t > 1.5:
            self.want_msg, self.msg_t = False, self.t
            try:
                with open(PANIC_MSG) as f:
                    msg = f.read().strip()
                os.remove(PANIC_MSG)
                if msg:
                    self.toast = (msg, "aviso", self.t + 3.5)
            except OSError:
                pass

    # --- jogos ---

    def flush_source(self):
        res = getattr(self, "source_dirty", None)
        if res is not None:
            self.source_dirty = None
            self.rescan_source(res)

    def rescan_source(self, res):
        """Trocou de onde os jogos são lidos: busca os ports e relê a biblioteca."""
        if isinstance(res, str) and res != "ok":
            self.toast = (res, "aviso", self.t + 4)

        def scan():
            if FAKE:
                time.sleep(1.0)
            idx = self.games(force=True)
            ports = self._testar()
            return idx, ports

        def done(out):
            if isinstance(out, Exception):
                self.toast = (f"Erro ao ler os jogos: {out}", "problema", self.t + 4)
                return
            idx, ports = out
            self.set_result("testar", ports)
            self.lib = {"sys": 0, "game": 0, "top": 0.0, "stop": 0.0}
            n = sum(len(s["games"]) for s in idx)
            self.toast = (f"Lista atualizada: {n} jogos, {self.port_count} ports", "ok", self.t + 4)
        self.worker(scan, done, busy="Procurando jogos e ports...")

    def open_sheet(self, s, g, back=None):
        self.picker = None
        # só a biblioteca joga; no menu do START a ficha é só para ver
        playable = self.view == "lib" and back is None
        self.sheet = {"s": s, "g": g, "sel": 0 if playable else 1, "back": back, "play": playable}

    def sheet_input(self, cmd):
        sh = self.sheet
        if cmd in ("left", "right") and sh["play"]:
            sh["sel"] = 1 - sh["sel"]
        elif cmd == "back" or (cmd == "ok" and sh["sel"] == 1):
            self.sheet = None
            if sh["back"]:
                sh["back"]()
        elif cmd == "ok":
            self.play(sh["s"], sh["g"])

    def play(self, s, g):
        if self.busy_game():
            return
        if FAKE:
            self.toast = (f"Abriria {g['name']}", "ok", self.t + 3)
            return
        try:
            with open(LIB_POS, "w") as f:
                json.dump({k: self.lib[k] for k in ("sys", "game")}, f)
        except OSError:
            pass
        omni_games.play(s["name"], g["path"])
        self.running = False          # o launch-direct.sh abre o jogo e reabre o Omni36OS na biblioteca

    def draw_sheet(self, dt):
        g, sh = self.g, self.sheet
        s, game = sh["s"], sh["g"]
        G = omni_games if not FAKE else None
        g.rrect(0, 0, W, H, 0, (5, 7, 20, 190), feather=0)
        mx, my, mw, mh = 28, 24, W - 56, H - 48
        g.rrect(mx, my, mw, mh, 22, MODAL_A, MODAL_B)
        g.stroke(mx, my, mw, mh, 22, ink(25))
        a1, a2 = self.accent
        cx, cy, cw, ch = mx + 22, my + 22, 210, mh - 100
        g.rrect(cx, cy, cw, ch, 16, ink(14))
        cover = game.get("cover")
        if not (cover and os.path.exists(cover) and g.picture(cover, cx + 8, cy + 8, cw - 16, ch - 16)):
            g.rrect(cx + cw / 2 - 40, cy + ch / 2 - 40, 80, 80, 24, a1, a2)
            g.icon("device-gamepad-2", cx + cw / 2 - 22, cy + ch / 2 - 22, 44, ON_TEXT)
        tx, tw = cx + cw + 22, mw - cw - 66
        y = cy + 2
        for line in g.wrap("Bold", 18, game["name"], tw)[:3]:
            g.text("Bold", 18, line, tx, y, TEXT)
            y += 24
        g.text("SemiBold", 12, s["full"].upper(), tx, y + 4, alpha(a1, 255))
        y += 30
        facts = [f"{os.path.basename(game['path'])}" + (f" · {G.human_size(game['size'])}" if G else "")]
        if game.get("plays") or game.get("time"):
            facts.append(f"Jogado {game.get('plays', 0)} vez(es)" +
                         (f" · {G.human_time(game['time'])}" if G and game.get("time") else ""))
        if game.get("last") and G:
            facts.append(f"Última vez: {G.human_date(game['last'])}")
        if game.get("fav"):
            facts.append("Favorito")
        for f in facts:
            for line in g.wrap("Regular", 12, f, tw)[:2]:
                g.text("Regular", 12, line, tx, y, MUTED)
                y += 18
        desc = game.get("desc")
        if desc:
            y += 8
            room = int((my + mh - 70 - y) // 18)
            lines = g.wrap("Regular", 12, " ".join(desc.split()), tw)
            for line in lines[:max(0, room)]:
                g.text("Regular", 12, line, tx, y, TEXT)
                y += 18
        bw, by = (mw - 56) / 2, my + mh - 58
        for k, label in enumerate(("Jogar", "Voltar")):
            if not sh["play"] and k == 0:
                continue
            bx = mx + 22 + k * (bw + 12) if sh["play"] else mx + 22
            if not sh["play"]:
                bw = mw - 44
            if k == sh["sel"]:
                g.rrect(bx, by, bw, 38, 14, a1, a2)
            else:
                g.rrect(bx, by, bw, 38, 14, ink(22))
            g.text("SemiBold", 13, label, bx + bw / 2, by + 19.5, ON_TEXT if k == sh["sel"] else TEXT, "c", "m")

    # --- teste de ports ---

    def open_picker(self):
        if self.busy_game():
            return
        groups = FAKE_PORTS if FAKE else omni.port_groups()
        res = {} if FAKE else omni.port_results()
        rows = []
        for g in groups:
            rows.append({"head": g["label"], "tag": "NA BIBLIOTECA", "tagc": LEVEL["ok"]})
            for p in g["ports"]:
                name = os.path.basename(p)[:-3]
                r = res.get(name)
                right = None
                if r:
                    ok = r[0] == "ok"
                    right = (("Passou " if ok else "Falhou ") + r[1].split(" ")[0], LEVEL["ok" if ok else "aviso"])
                rows.append({"name": name, "path": p, "right": right})

        def pick(row):
            self.ask(f"Testar {row['name']}?\nA Omni36OS fecha, o port abre por 15 segundos e fecha sozinho. "
                     "Depois o Omni36OS volta com o resultado.", lambda: self.start_test(row["path"]))
        if not self.show_list("Escolha o port", "player-play", rows, pick, "Testar"):
            self.toast = ("Nenhum port instalado", "aviso", self.t + 3)

    def start_test(self, path):
        res = "ok" if FAKE else D.run("test_port", {"path": path})
        if res == "ok":
            self.running = False      # o launch-direct.sh roda o teste e reabre o Omni36OS
        else:
            self.toast = (res, "aviso", self.t + 3.5)

    def show_test_result(self):
        if FAKE:      # OMNI_FAKE_TESTE=falhou|ok mostra um resultado de teste no simulador
            kind = os.environ.get("OMNI_FAKE_TESTE", "")
            if not kind:
                return
            r = {"nome": "Halo - Combat Evolved", "resultado": kind, "segundos": "2", "relatorio": ""}
            found = [] if kind == "ok" else [
                {"id": "permissao", "causa": "Um arquivo do port está sem permissão para rodar (comum depois de "
                                             "copiar pelo PC).", "dica": "Dar permissão de execução aos arquivos do port.",
                 "fix": "chmod", "extra": ""}]
            settled = ""
        else:
            r = omni.last_test()
            if not r:
                return
            settled = omni_ports_fix.settle(r["nome"], r["resultado"] == "ok")
            found = [] if r["resultado"] == "ok" or not r["relatorio"] else omni_ports_fix.diagnose(r["relatorio"])
            if found:
                omni_ports_fix.note(r["relatorio"], found)
        buttons, fns = ["OK"], [lambda: None]
        if r["resultado"] == "ok":
            text = f"{r['nome']} abriu e ficou rodando 15 segundos. Funcionou!"
            icon = "check"
        else:
            rel = r["relatorio"].split("/omni36os/", 1)[-1] if r["relatorio"] else ""
            text = f"{r['nome']} fechou sozinho após {r['segundos']} s."
            if found:
                d = found[0]
                text += f"\nCausa provável: {d['causa']}" + (f" ({d['extra']})" if d["extra"] else "")
                text += f"\nO que fazer: {d['dica']}"
                if d["fix"] and not settled:      # uma tentativa por teste: depois de desfeita, não repete
                    buttons, fns = ["Corrigir e testar de novo", "Agora não"], \
                        [lambda: self.fix_and_retest(r, d["fix"]), lambda: None]
            if rel:
                text += f"\nRelatório: omni36os/{rel}"
            icon = "alert-triangle"
        if settled:
            text = settled + "\n" + text
        self.modal = {"title": "Teste de port", "text": text, "icon": icon, "buttons": buttons, "sel": 0, "fns": fns}

    def fix_and_retest(self, r, fix):
        if FAKE:
            self.toast = ("Correção aplicada (teste)", "ok", self.t + 3)
            return
        def done(script):
            if isinstance(script, Exception) or not script:
                self.toast = ("Não consegui aplicar a correção", "problema", self.t + 3.5)
                return
            self.start_test(script)
        self.worker(lambda: omni_ports_fix.apply(r["relatorio"], fix), done, busy="Corrigindo...")

    def quit(self):
        self.running = False

    # --- backup ---

    def backup_where(self, module):
        """Pergunta onde salvar: só os lugares disponíveis agora (cartão do sistema sempre; o de jogos e
        o pendrive quando montados). O escolhido vem marcado da próxima vez."""
        opts = ([("Cartão do sistema", "/roms/backup/omni36os", 12.4), ("Pendrive", "/mnt/usbdrive/backup/omni36os", 7.1)]
                if FAKE else omni_backup.places())
        last = None if FAKE else omni_backup.backup_dir()
        rows = [{"name": name, "right": (f"{free:.1f} GB livres", MUTED), "dir": d,
                 "icon": "usb" if "usbdrive" in d else "device-sd-card"} for name, d, free in opts]

        def go(row):
            self.picker = None
            if FAKE:
                self.toast = (f"Teste: salvaria em {row['dir']}", "ok", self.t + 3)
                return
            self.backup_export(module, row["dir"])
        start = next((i for i, r in enumerate(rows) if r["dir"] == last), None)
        self.show_list("Onde salvar o backup?", "device-floppy", rows, go, "Salvar aqui", start)

    def backup_export(self, module, dest=None):
        def done(res):
            if isinstance(res, Exception):
                self.toast = (f"Erro: {res}", "problema", self.t + 4)
                return
            path, info = res
            if not path:
                self.toast = (info, "aviso", self.t + 3.5)
                return
            self.modal = {"title": "Backup salvo", "icon": "check", "buttons": ["OK"], "sel": 0,
                          "text": f"{info} salvos em:\n{path}"}
            self.reload_findings()
        self.worker(lambda: omni_backup.export(module, dest=dest), done, busy="Exportando...")

    def backup_browse(self, module, path):
        if FAKE:                      # simulador: uma pasta de teste com um backup
            path, entries = path, [{"name": "..", "path": "/roms/backup", "dir": True},
                                   {"name": "omni36os-20261029-120000.tar.gz", "path": path + "/x.tar.gz", "dir": False}]
        else:
            path, entries = omni_backup.browse(path)
        rows = [{"head": path}]
        for e in entries:
            if e["dir"]:
                rows.append({"name": e["name"], "path": e["path"], "dir": True,
                             "icon": "arrow-back-up" if e["name"] == ".." else "folder"})
            else:
                m = {"module": module, "date": "29/10/2026 12:00"} if FAKE else omni_backup.manifest(e["path"]) or {}
                mod = m.get("module")
                ok = mod == module
                right = (m.get("date", "").split(" ")[0] if ok else
                         (omni_backup.MODULES.get(mod, ("não é backup do Omni36OS",))[0] if mod else "não é backup do Omni36OS"),
                         LEVEL["ok" if ok else "info"])
                rows.append({"name": e["name"], "path": e["path"], "dir": False, "ok": ok,
                             "icon": "device-floppy", "right": right})

        def pick(row):
            if row["dir"]:
                self.backup_browse(module, row["path"])
            elif not row["ok"]:
                self.toast = (f"Este arquivo não é um backup de {omni_backup.MODULES[module][0]}", "aviso",
                              self.t + 3.5)
            else:
                self.ask(f"Importar {row['name']}?\nAs configurações atuais do Omni36OS "
                         "são salvas antes, como \"antes-de-importar\".",
                         lambda: self.backup_import(module, row["path"]), danger=True)
        start = next((i for i, r in enumerate(rows) if r.get("ok")), None)   # o backup compatível
        if not self.show_list(f"Importar · {path}", "folder", rows, pick, "Abrir / importar", start):
            self.toast = ("Pasta vazia", "aviso", self.t + 3)

    def backup_import(self, module, path):
        def done(res):
            self.picker = None
            if isinstance(res, Exception):
                self.toast = (f"Erro: {res}", "problema", self.t + 4)
                return
            text = str(res)
            self.modal = {"title": "Importação", "icon": "device-floppy", "buttons": ["OK"], "sel": 0,
                          "text": text}
            self.reload_findings()
        self.worker(lambda: "Teste: nada importado" if FAKE else omni_backup.import_(module, path), done,
                    busy="Importando...")

    # --- atalhos personalizados ---

    def pick_atalho(self):
        combos = D.get("at_combos")
        rows = [{"name": name, "right": (omni_combos.text(combos[k]), MUTED), "icon": icon, "key": k}
                for k, (name, icon, *_x) in omni_combos.ACTIONS.items() if k not in omni_combos.FIXED]
        def go(r):
            self.picker = None
            self.start_capture(r["key"])
        self.show_list("Personalizar um atalho", "keyboard", rows, go, "Gravar")

    def start_capture(self, key):
        """Grava a tecla que vai com o FN: o jogador aperta uma tecla e o atalho vira FN + ela. No
        console lê o controle direto (o SDL não vê todas as teclas); no simulador, a tecla do teclado."""
        fd = None
        if not FAKE:
            try:
                fd = os.open(PAD_DEV, os.O_RDONLY | os.O_NONBLOCK)
            except OSError:
                self.toast = ("Não consegui ler o controle", "problema", self.t + 4)
                return
        self.capture = {"key": key, "fd": fd, "seen": set(), "down": set(), "t0": self.t, "last": self.t}

    def capture_poll(self):
        c = getattr(self, "capture", None)
        if not c:
            return
        if c["fd"] is not None:
            ev = struct.Struct("llHHi")
            try:
                data = os.read(c["fd"], ev.size * 64)
            except BlockingIOError:
                data = b""
            for k in range(0, len(data) - ev.size + 1, ev.size):
                _s, _us, typ, code, val = ev.unpack_from(data, k)
                if typ != 1 or val == 2 or code not in omni_combos.BUTTONS:
                    continue
                if val == 1 and code != omni_combos.FN:
                    c["seen"].add(code)
                    break
        done = bool(c["seen"])
        if done:
            self.finish_capture()
        elif not c["seen"] and self.t - c["t0"] > 8:
            self.end_capture()
            self.toast = ("Nenhum botão: o atalho não mudou", "aviso", self.t + 3)

    def end_capture(self):
        c, self.capture = self.capture, None
        if c and c["fd"] is not None:
            os.close(c["fd"])

    def finish_capture(self):
        c = self.capture
        self.end_capture()
        key, codes = c["key"], [omni_combos.FN, *c["seen"]]
        combos = dict(D.get("at_combos"))
        err = omni_combos.problem(key, codes, combos)
        name = omni_combos.ACTIONS[key][0]
        if err:
            self.modal = {"title": "Atalho não gravado", "icon": "alert-triangle", "buttons": ["Tentar de novo", "Cancelar"],
                          "sel": 0, "text": err, "fns": [lambda: self.start_capture(key), lambda: None]}
            return

        def save():
            combos[key] = codes
            D.set("at_combos", combos)
            self.refresh_atalhos(f"{name}: {omni_combos.text(codes)}")
        self.ask(f"Usar {omni_combos.text(codes)} para {name}?", save)

    def reset_combos(self):
        D.set("at_combos", omni_combos.defaults()["combos"])
        self.refresh_atalhos("Botões padrão de volta")

    def refresh_atalhos(self, msg):
        keep = self.item_sel
        self.items = self.build_items(self.page)
        self.item_sel = min(keep, len(self.items) - 1)
        self.toast = (msg, "ok", self.t + 3.5)

    def draw_capture(self):
        g, c = self.g, self.capture
        g.rrect(0, 0, W, H, 0, (5, 7, 20, 200), feather=0)
        mw, mh = 420, 210
        mx, my = (W - mw) / 2, (H - mh) / 2
        g.glow(mx, my, mw, mh, 22, alpha(self.accent[0], 60), 26)
        g.rrect(mx, my, mw, mh, 22, MODAL_A, MODAL_B)
        g.stroke(mx, my, mw, mh, 22, ink(25))
        g.icon("keyboard", mx + 24, my + 22, 24, alpha(self.accent[0], 255))
        g.text("Bold", 17, f"Novo atalho: {omni_combos.ACTIONS[c['key']][0]}", mx + 58, my + 22, TEXT)
        g.text("Medium", 13, "Aperte a tecla que vai junto com o FN.", mx + 24, my + 62, MUTED)
        now = "FN + " + (omni_combos.text(c["seen"]) if c["seen"] else "...")
        g.text("Bold", 26, now, W / 2, my + 118, TEXT, "c", "m")
        left = max(0, 8 - (self.t - c["t0"])) if not c["seen"] else None
        g.text("Medium", 12, f"Sem tecla em {left:.0f} s, cancela." if left is not None else "",
               W / 2, my + mh - 30, FAINT, "c")

    def read(self, title, icon, text):
        self.reader = {"title": title, "icon": icon, "text": text, "scroll": 0.0, "top": 0}

    def ask(self, text, fn, danger=False):
        if danger:
            return self.warn("Atenção", text, fn, secs=5)
        self.modal = {"title": "Confirmar", "text": text, "icon": "alert-triangle" if danger else "info-circle",
                      "buttons": ["Sim, fazer", "Cancelar"], "sel": 1 if danger else 0, "fn": fn}

    # --- aviso com contagem (estilo "opções perigosas" da Xiaomi) ---

    def ask_overclock(self):
        """Único ajuste de DTB que ficou: a trava (aviso + 5 toques em A) protege o boot."""
        S = omni_sistema if not FAKE else None
        go = ((lambda: self.worker(S.dtb_overclock, self._sys_done, busy="Mexendo no DTB...")) if S else
              (lambda: setattr(self, "toast", ("Teste: passou", "ok", self.t + 3))))
        self.warn("Liberar overclock", "Acrescenta frequências de 1368 a 1512 MHz no processador e 600 MHz na GPU, "
                  "com a tensão do dArkOSen. Depois, escolha o limite em Desempenho.", go, 10, True,
                  key="Liberar overclock", risk="Um DTB errado deixa a tela preta ou o console sem ligar.",
                  undo=BOOT_UNDO + " Antes de mudar, o Omni36OS guarda uma cópia do DTB.")

    def warn(self, title, text, fn, secs=10, hold=False, key=None, risk="", undo="", back=None):
        """Continuar só acende depois de `secs` s; Cancelar começa escolhido. Com `hold`, ainda é
        preciso apertar A 5 vezes. Quem já passou pelo aviso de `key` nesta sessão não espera de novo."""
        seen = getattr(self, "warned", set())
        self.warned = seen
        if key and key in seen:
            secs, hold = 0, False
        self.danger = {"title": title, "text": text, "risk": risk, "undo": undo, "fn": fn, "back": back,
                       "secs": secs, "hold": hold, "t0": time.monotonic(), "sel": 1, "taps": 0, "tap_t": 0.0, "key": key,
                       "nudge": -9}

    def danger_left(self):
        d = self.danger
        return max(0.0, d["secs"] - (time.monotonic() - d["t0"]))

    def danger_input(self, cmd):
        d = self.danger
        if cmd in ("left", "right"):
            d["sel"] = 1 - d["sel"]
        elif cmd == "back" or (cmd == "ok" and d["sel"] == 1):
            self.danger = None
            if d["back"]:
                d["back"]()
        elif cmd == "ok":
            if self.danger_left() > 0:
                d["nudge"] = time.monotonic()          # ainda não: o botão treme
            elif d["hold"]:
                now = time.monotonic()                 # 5 toques em A; parar por 2 s zera a contagem
                d["taps"] = (d["taps"] if now - d["tap_t"] < 2 else 0) + 1
                d["tap_t"] = now
                if d["taps"] >= 5:
                    self.danger_go()
            else:
                self.danger_go()

    def danger_go(self):
        d = self.danger
        self.danger = None
        if d["key"]:
            self.warned.add(d["key"])
        d["fn"]()

    def draw_danger(self, dt):
        g, d = self.g, self.danger
        red, red2 = hexc("ef4444"), hexc("b91c1c")
        g.rrect(0, 0, W, H, 0, (40, 4, 10, 215), feather=0)
        mx, my, mw, mh = 34, 34, W - 68, H - 68
        g.glow(mx, my, mw, mh, 24, alpha(red, 70), 26)
        g.rrect(mx, my, mw, mh, 24, MODAL_A, MODAL_B)
        g.stroke(mx, my, mw, mh, 24, alpha(red, 120), 1.5)
        g.circle(mx + 52, my + 52, 26, alpha(red, 60))
        g.icon("alert-triangle", mx + 38, my + 38, 28, red)
        g.text("Bold", 20, d["title"], mx + 92, my + 30, TEXT)
        g.text("SemiBold", 11, "LEIA ANTES DE CONTINUAR", mx + 92, my + 58, red)
        y = my + 96
        for label, body, col in (("", d["text"], TEXT), ("O que pode dar errado", d["risk"], TEXT),
                                 ("Como desfazer", d["undo"], TEXT)):
            if not body:
                continue
            if label:
                g.text("SemiBold", 11, label.upper(), mx + 28, y, FAINT)
                y += 18
            for para in body.split("\n"):
                for line in g.wrap("Regular", 13, para, mw - 56):
                    if y < my + mh - 110:
                        g.text("Regular", 13, line, mx + 28, y, col)
                    y += 19
            y += 8
        left = self.danger_left()
        if d["taps"] and time.monotonic() - d["tap_t"] >= 2:
            d["taps"] = 0                               # demorou: recomeça do zero
        bw, by = (mw - 68) / 2, my + mh - 66
        shake = 6 * math.sin((time.monotonic() - d["nudge"]) * 40) if time.monotonic() - d["nudge"] < 0.35 else 0
        bx = mx + 28 + shake
        ready = left <= 0
        on = d["sel"] == 0
        if ready:
            g.rrect(bx, by, bw, 42, 15, red if on else alpha(red, 90), red2 if on else alpha(red2, 90))
        else:
            g.rrect(bx, by, bw, 42, 15, ink(14))
            if on:
                g.stroke(bx, by, bw, 42, 15, ink(60), 1.5)
        if not ready:
            label = f"Continuar ({int(left) + 1})"
            # arco que fecha junto com a contagem
            cx_, cy_ = bx + 26, by + 21
            g.arc(cx_, cy_, 11, 3, -90, -90 + 360 * (1 - left / max(1, d["secs"])), alpha(red, 230))
            g.text("SemiBold", 14, label, bx + bw / 2 + 10, by + 21.5, FAINT, "c", "m")
        elif d["hold"]:
            k = d["taps"] / 5
            if k:
                g.rrect(bx, by, bw * k, 42, 15, (255, 255, 255, 60))
            g.text("SemiBold", 14, "Aperte A 5 vezes" if not k else f"Mais {5 - d['taps']} vez(es)",
                   bx + bw / 2, by + 21.5, ON_TEXT, "c", "m")
        else:
            g.text("SemiBold", 14, "Continuar", bx + bw / 2, by + 21.5, ON_TEXT, "c", "m")
        cb = mx + 40 + bw
        if d["sel"] == 1:
            g.rrect(cb, by, bw, 42, 15, self.accent[0], self.accent[1])
        else:
            g.rrect(cb, by, bw, 42, 15, ink(22))
        g.text("SemiBold", 14, "Cancelar", cb + bw / 2, by + 21.5, ON_TEXT if d["sel"] == 1 else TEXT, "c", "m")

    # --- entrada ---

    def handle(self, cmd):
        if cmd in ("vleft", "vright"):   # analógico para os lados: fora de uma barra/escolha, navega
            over = (getattr(self, "kbd", None) or getattr(self, "danger", None) or self.reader or self.modal
                    or getattr(self, "sheet", None) or self.picker)
            it = self.items[self.item_sel] if self.page and self.items and not over else None
            if self.page and not over:
                if not isinstance(it, (Slider, Choice)):
                    return                # numa página o analógico só ajusta valores
            else:
                cmd = cmd[1:]
        self.last_input = time.monotonic()
        if self.busy or self.loading:
            return
        if getattr(self, "capture", None):        # gravando um atalho: os botões são do atalho
            if FAKE and cmd in SIM_BUTTONS and cmd != "fn":
                self.capture["seen"].add(SIM_BUTTONS[cmd])
            return
        if getattr(self, "kbd", None) and not self.modal:
            self.kbd_input(cmd)
            return
        if getattr(self, "danger", None):
            self.danger_input(cmd)
            return
        if self.reader:
            r = self.reader
            step = {"up": -1, "down": 1, "left": -8, "right": 8, "l1": -8, "r1": 8}.get(cmd)
            if step:
                r["top"] = max(0, min(r.get("max", 0), r["top"] + step))
            elif cmd in ("back", "ok"):
                self.reader = None
            return
        if self.modal:
            m = self.modal
            if cmd in ("left", "right") and len(m["buttons"]) > 1:
                m["sel"] = (m["sel"] + (1 if cmd == "right" else -1)) % len(m["buttons"])
            elif cmd == "ok":
                self.modal = None
                if m.get("fns"):
                    m["fns"][m["sel"]]()
                elif m["sel"] == 0 and m.get("fn"):
                    m["fn"]()
            elif cmd == "back":
                self.modal = None
                if m.get("on_back"):
                    m["on_back"]()
            return
        if getattr(self, "sheet", None):
            self.sheet_input(cmd)
            return
        if self.picker:
            self.picker_input(cmd)
            return
        if self.page is None and self.view == "lib":
            self.library_input(cmd)
            return
        if cmd in ("start", "select"):
            return                        # sem atalhos: Ports é o primeiro card; Energia é o botão de power
        if self.page is None and cmd == "back":
            return                        # tela inicial: B não sai do sistema
        if self.page is None:
            cols, n = COLS, len(CARDS)
            r, c = divmod(self.sel, cols)
            rows = (n + cols - 1) // cols
            in_row = min(cols, n - r * cols)      # a última linha pode ter menos cards
            if cmd == "left":
                self.sel = r * cols + (c - 1) % in_row
            elif cmd == "right":
                self.sel = r * cols + (c + 1) % in_row
            elif cmd in ("up", "down"):
                r = (r + (1 if cmd == "down" else -1)) % rows
                self.sel = min(r * cols + c, n - 1)
            elif cmd == "ok" and CARDS[self.sel][0] == "ports":
                self.view = "lib"
            elif cmd == "ok":
                self.open_page(CARDS[self.sel][0])
            elif cmd == "back":
                self.running = False
            return
        it = self.items[self.item_sel] if self.items else None
        if cmd in ("l1", "r1"):           # rola o diagnóstico (painel da esquerda)
            self.find_top = max(0, min(self.find_max, self.find_top + (1 if cmd == "r1" else -1)))
            return
        if cmd == "up":
            self.item_sel = (self.item_sel - 1) % len(self.items)
        elif cmd == "down":
            self.item_sel = (self.item_sel + 1) % len(self.items)
        elif cmd == "back":
            if self.page in PARENT:       # subpágina: volta ao card de origem
                sub = self.page
                self.open_page(PARENT[sub])
                self.item_sel = next((i for i, x in enumerate(self.items)
                                      if getattr(x, "sub", None) == sub), 0)
            else:
                self.page = None
                self.flush_source()
        elif cmd in ("left", "right") and self.page in TWO_COLS:   # direcional: troca de coluna
            half = (len(self.items) + 1) // 2
            k = self.item_sel + (half if self.item_sel < half else -half)
            self.item_sel = max(0, min(len(self.items) - 1, k))
        elif isinstance(it, Slider) and cmd in ("vleft", "vright"):
            it.value = max(it.lo, min(100, it.value + (it.step if cmd == "vright" else -it.step)))
            D.set(it.key, it.value)
            if it.key == "volume":            # a pílula do topo mostra o volume novo na hora
                self.vol = it.value
        elif isinstance(it, Choice) and cmd in ("left", "right", "vleft", "vright", "ok"):
            it.index = (it.index + (-1 if cmd in ("left", "vleft") else 1)) % len(it.options)
            res = D.set(it.key, it.options[it.index])
            if isinstance(res, str) and res.startswith(("Está quente", "Frequência", "Este sistema")):
                cur = D.get(it.key)     # recusado: volta ao valor que está valendo
                it.index = it.options.index(cur) if cur in it.options else 0
                self.toast = (res, "aviso", self.t + 4)
            elif it.key in ("cpu_max", "gpu_max") and "overclock" in str(res):
                self.toast = (str(res) + ": fique de olho na temperatura", "aviso", self.t + 3.5)
            if it.key == "gov":
                self.status = D.status()
            if it.key == "tema":
                self.g.flush()
            if it.key == "fonte":         # a busca espera o jogador sair da página: trocar várias
                self.source_dirty = res   # vezes seguidas não relê os cartões a cada toque
            if (it.key == "power" or it.key.startswith("at_")) and isinstance(res, str) and res != "ok":
                self.toast = (res, "ok", self.t + 4)
        elif isinstance(it, Action) and cmd == "ok":
            if it.confirm:
                self.ask(it.confirm, it.fn, it.danger)
            else:
                it.fn()

    def poll(self):
        ev = (C.c_uint8 * 64)()
        now = time.monotonic()
        while gfx.SDL_PollEvent(ev):
            typ = int.from_bytes(bytes(ev[0:4]), "little")
            if typ == 0x100:  # SDL_QUIT
                self.running = False
            elif typ == 0x653:  # controle conectado
                gfx.SDL_GameControllerOpen(int.from_bytes(bytes(ev[8:12]), "little", signed=True))
            elif typ in (0x651, 0x652):   # SDL_CONTROLLERBUTTONDOWN / UP
                if getattr(self, "pad", None):     # teste do controle: todo botão vai para ele
                    self.last_input = now
                    self.pad_event("btn", ev[12], typ == 0x651, now)
                    continue
                self.button(ev[12], typ == 0x651, now)
            elif typ == 0x650:          # SDL_CONTROLLERAXISMOTION
                axis = ev[12]
                val = int.from_bytes(bytes(ev[16:18]), "little", signed=True)
                if getattr(self, "pad", None):
                    self.pad_event("axis", axis, val, now)
                    continue
                if axis in (0, 1):   # eixo X do analógico esquerdo ajusta valores; o direcional navega
                    neg, pos = ("vleft", "vright") if axis == 0 else ("up", "down")
                    for d, on in ((neg, val < -20000), (pos, val > 20000)):
                        self.direction(d, on, now)
            elif typ == 0x401 and FAKE:   # mouse no simulador: esquerdo = A, direito = B
                btn = ev[16]
                mx, my = (int.from_bytes(bytes(ev[o:o + 4]), "little", signed=True) for o in (20, 24))
                if btn == 1 and not self.mouse_pick(mx, my):
                    self.handle("ok")
                elif btn == 3:
                    self.handle("back")
            elif typ == 0x403 and FAKE:   # roda do mouse no simulador: cima/baixo
                wy = int.from_bytes(bytes(ev[20:24]), "little", signed=True)
                if wy:
                    self.handle("up" if wy > 0 else "down")
            elif typ in (0x300, 0x301):  # teclado (para testar no PC)
                sym = int.from_bytes(bytes(ev[20:24]), "little")
                down, rep = typ == 0x300, ev[13]
                if FAKE and down and sym in (0x40000057, 0x40000056):   # simulador: KP+ / KP- = botões de volume
                    v = D.get("volume")                                   # (no console quem muda é o ogage)
                    D.set("volume", max(0, min(100, v + (10 if sym == 0x40000057 else -10))))
                    self.vol_at = self.t + 0.15
                    for it in self.items or []:
                        if isinstance(it, Slider) and it.key == "volume":
                            it.value = D.get("volume")
                    continue
                if sym in (0x4000007F, 0x40000080, 0x40000081) and not down:
                    self.vol_at = self.t + 0.15   # VOLUP/VOLDOWN/MUTE: o ogage muda o som; relê o volume
                keys = {0x4000004F: "right", 0x40000050: "left", 0x40000051: "down", 0x40000052: "up",
                        0x4000005F: "vleft", 0x40000061: "vright"}   # KP7/KP9: analógico esquerdo
                if sym in keys:
                    if not rep:
                        self.direction(keys[sym], down, now)
                elif down and not rep:
                    # teclado numérico (Num Lock ligado): 2=A, 1=B, 5=X, 4=Y, 6=L1, 3=R1;
                    # Enter=START, Shift direito=SELECT
                    self.handle({0x4000005A: "ok", 0x40000059: "back", 0x4000005D: "x", 0x4000005C: "y",
                                 0x4000005E: "l1", 0x4000005B: "r1", 13: "start", 0x40000058: "start",
                                 0x400000E5: "select"}.get(sym, ""))
                    if FAKE and sym == 0x40000060:   # simulador: KP8 = FN (só na gravação de atalho)
                        self.handle("fn")
                    if FAKE and sym == 0x40000062:   # simulador: KP0 = botão de power
                        self.want_power = True
        for d, nxt in list(self.held.items()):
            if now >= nxt:
                self.handle(d)
                self.held[d] = now + 0.09

    def direction(self, d, on, now):
        if on and d not in self.held:
            self.handle(d)
            self.held[d] = now + 0.35
        elif not on:
            self.held.pop(d, None)

    def button(self, b, down, now):
        # SDL: 0 A (direita no R36S), 1 B (baixo), 4 back, 6 start, 9 L1, 10 R1, 11-14 direcional
        dpad = {11: "up", 12: "down", 13: "left", 14: "right"}
        if b in dpad:
            self.direction(dpad[b], down, now)
            return
        if b in (4, 6):
            if down:
                self.combo.add(b)
                self.combo_used = getattr(self, "combo_used", False) or {4, 6} <= self.combo
            else:
                if not getattr(self, "combo_used", False) and self.combo == {b}:
                    self.handle("start" if b == 6 else "select")
                self.combo.discard(b)
                if not self.combo:
                    self.combo_used = False
            return
        ok_b, back_b = (1, 0) if self.swap else (0, 1)
        if b == ok_b:
            self.ok_held = down
        if not down:
            return
        if b in (2, 3):
            self.handle("x" if b == 2 else "y")
        elif b in (9, 10):
            self.handle("l1" if b == 9 else "r1")
        elif b == ok_b:
            self.handle("ok")
        elif b == back_b:
            self.handle("back")

    # --- desenho ---

    def draw_bg(self, dt):
        g = self.g
        g.vgradient(BG_TOP, BG_BOT)
        a1, a2 = self.accent
        t = self.t
        g.blob(120 + math.sin(t * 0.35) * 60, 90 + math.cos(t * 0.27) * 40, 300, alpha(a1, 46))
        g.blob(540 + math.cos(t * 0.3) * 50, 400 + math.sin(t * 0.33) * 40, 320, alpha(a2, 52))
        g.blob(360 + math.sin(t * 0.2) * 120, 240, 220, (90, 70, 200, 22))

    def draw_header(self):
        g = self.g
        if self.t - self.status_at > 5:
            self.status, self.status_at = D.status(), self.t
        s = self.status
        # marca
        g.image("logo-64", 22, 18, 30, smooth=True)
        g.text("Bold", 20, "Omni36OS", 62, 18, TEXT)
        # pílula de estado
        hora = time.strftime("%H:%M")
        bat = f"{s['bat']}%"
        temp = f"{s['temp']}°"
        if self.vol_at is not None and self.t >= self.vol_at:   # sem leitura periódica: só no início
            self.vol_at = None                                  # e logo depois dos botões de volume
            v = D.get("volume")
            self.vol = v if isinstance(v, int) else None
        vol = self.vol
        vtxt = f"{vol}%" if vol is not None else ""
        w = (24 + g.measure("SemiBold", 13, vtxt)[0] + 12 if vtxt else 0) + 46 + g.measure("SemiBold", 13, bat)[0] + 36 + g.measure("SemiBold", 13, temp)[0] + 22 + \
            g.measure("SemiBold", 13, hora)[0] + 30
        x = W - 22 - w
        g.rrect(x, 16, w, 34, 17, GLASS_HI)
        cx = x + 14
        g.icon("wifi" if s["wifi"] else "wifi-off", cx, 24, 18, TEXT if s["wifi"] else FAINT)
        cx += 26
        if vtxt:                                  # volume do som
            vc = TEXT if vol else FAINT
            g.icon("volume", cx, 24, 18, vc)
            cx += 24 + g.text("SemiBold", 13, vtxt, cx + 22, 33, vc, "l", "m") + 12
        batc = LEVEL["problema"] if s["bat"] < 20 and not s["carregando"] else TEXT
        g.icon("battery-charging" if s["carregando"] else "battery-2", cx, 24, 18, batc)
        cx += 22 + g.text("SemiBold", 13, bat, cx + 22, 33, batc, "l", "m") + 10
        tc = LEVEL["problema"] if s["temp"] > 75 else TEXT
        g.icon("temperature", cx, 24, 18, tc)
        cx += 20 + g.text("SemiBold", 13, temp, cx + 20, 33, tc, "l", "m") + 12
        g.text("SemiBold", 13, hora, cx, 33, TEXT, "l", "m")

    def btn_glyph(self, x, y, letter, c):
        g = self.g
        g.circle(x + 10, y + 10, 10, c)
        g.text("Bold", 11, letter, x + 10, y + 10.5, BG_TOP, "c", "m")

    def draw_footer(self, hints):
        g = self.g
        x = 22
        for letter, label, c in hints:
            if letter in ("A", "B"):
                self.btn_glyph(x, H - 32, letter, c)
                w = 26
            elif letter == "LR":
                g.rrect(x, H - 32, 40, 20, 10, ink(40))
                g.chevron(x + 12, H - 22, 7, TEXT, left=True)
                g.chevron(x + 28, H - 22, 7, TEXT)
                w = 46
            else:
                pw = g.measure("Bold", 10, letter)[0] + 16
                g.rrect(x, H - 32, pw, 20, 10, ink(40))
                g.text("Bold", 10, letter, x + pw / 2, H - 21.5, TEXT, "c", "m")
                w = pw + 6
            x += w + g.text("Medium", 12, label, x + w, H - 21.5, MUTED, "l", "m") + 18

    def card_subtitle(self, cid):
        s = self.status
        return {
            "checkup": self._home_summary(),
            "bateria": f"{s['bat']}%" + (" · Carregando" if s["carregando"] else ""),
            "tela": "Som, tela e segurança",
            "desempenho": GOV_NAMES.get(s["gov"], s["gov"]) + f" · {s['temp']}°C",
            "pendrive": "Pendrive e rede no cabo",
            "cartoes": "Espaço, marca e velocidade",
            "ferramentas": "Arquivos, testes e PortMaster",
            "ajuda": f"Manual · versão {omni_version()}",
            "ports": f"{sum(len(s['games']) for s in self.games())} Jogos",
            "testar": f"{self.port_count} Ports instalados" if getattr(self, "port_count", 0) else "Abre e fecha em 15 s",
        }[cid]

    def _home_summary(self):
        hc = self.home_check
        if not hc:
            return "Analisando..."
        n = sum(1 for l, _ in hc["achados"] if l in ("aviso", "problema"))
        return "Tudo certo" if n == 0 else f"{n} Ponto{'s' if n > 1 else ''} de atenção"

    def mouse_pick(self, mx, my):
        """Simulador: clique num cartão/item que não está em foco só o seleciona."""
        if self.page is not None:
            hits, cur = getattr(self, "hits_page", []), self.item_sel
        elif self.view == "menu":
            hits, cur = getattr(self, "hits_home", []), self.sel
        else:
            return False
        for k, x, y, w, h in hits:
            if x <= mx < x + w and y <= my < y + h:
                if k == cur:
                    return False
                if self.page is not None:
                    self.item_sel = k
                else:
                    self.sel = k
                return True
        return False

    def draw_home(self, dt, fade):
        if self.view == "lib":
            return self.draw_library(dt, fade)
        g = self.g
        hour = time.localtime().tm_hour
        hello = "Bom dia" if 5 <= hour < 12 else "Boa tarde" if 12 <= hour < 18 else "Boa noite"
        hello += f", {self.player}!" if self.player else "!"
        g.text("Bold", 26, hello, 22, 66, alpha(TEXT, 255 * fade))
        hc = self.home_check
        if hc:
            lvl = hc["nivel"]
            n = len(self.alerts)
            if n == 0:
                lvl, msg = "ok", "Seu R36S está em ótima forma."
            else:
                lvl = "problema" if any(l == "problema" for l, _ in self.alerts.values()) else "aviso"
                total = sum(k for _, k in self.alerts.values())   # a soma dos pontos dos cards
                msg = f"{total} Alerta" + ("s" if total != 1 else "")
            g.circle(29, 115, 5, alpha(LEVEL[lvl], 255 * fade))
            g.text("Regular", 13, msg, 42, 105, alpha(MUTED, 255 * fade))
        else:
            g.arc(29, 115, 6, 2.5, self.t * 360, self.t * 360 + 270, alpha(MUTED, 255 * fade))
            g.text("Regular", 13, "Dando uma olhada no aparelho...", 42, 105, alpha(MUTED, 255 * fade))

        rows = (len(CARDS) + COLS - 1) // COLS
        cw, x0, y0 = 192, 22, 136
        ch, gap = (94, 10) if rows <= 3 else (68, 8)
        col, row = self.sel % COLS, self.sel // COLS
        self.sel_x = approach(self.sel_x, x0 + col * (cw + gap), dt, 18)
        self.sel_y = approach(self.sel_y, y0 + row * (ch + gap), dt, 18)
        pos = lambda i: (x0 + (i % COLS) * (cw + gap), y0 + (i // COLS) * (ch + gap))
        self.hits_home = [(i, *pos(i), cw, ch) for i in range(len(CARDS))]
        for i in range(len(CARDS)):
            x, y = pos(i)
            g.rrect(x, y, cw, ch, 18, alpha(GLASS, 14 * fade))
            g.stroke(x, y, cw, ch, 18, ink(18 * fade))
        # o destaque desliza entre os cartões
        sx, sy = self.sel_x, self.sel_y
        pulse = 0.5 + 0.5 * math.sin(self.t * 3)
        a1, a2 = self.accent
        g.sprite(("hl-glow", a1), cw + 4, ch + 4, 20,
                 lambda ox, oy: g.glow(ox, oy, cw + 4, ch + 4, 20, alpha(a1, 110), 20),
                 sx - 2, sy - 3, (0.64 + 0.36 * pulse) * 255 * fade)
        g.sprite(("hl", a1, a2), cw + 4, ch + 4, 1, lambda ox, oy: (
                 g.rrect(ox, oy, cw + 4, ch + 4, 20, alpha(a1, 235), alpha(a2, 235)),
                 g.rrect(ox, oy, cw + 4, (ch + 4) * 0.5, 20, (255, 255, 255, 30), (255, 255, 255, 0))),
                 sx - 2, sy - 3, 255 * fade)
        for i, (cid, title, ic, c1, c2) in enumerate(CARDS):
            x, y = pos(i)
            on = i == self.sel
            lift = -3 if on else 0
            bx, by = x + 14, y + (ch - 46) / 2 + lift
            if on:
                g.rrect(bx, by, 46, 46, 14, (255, 255, 255, 60 * fade))
            else:
                g.rrect(bx, by, 46, 46, 14, alpha(hexc(c1), 255 * fade), alpha(hexc(c2), 255 * fade))
            g.icon(ic, bx + 10, by + 10, 26, alpha(ON_TEXT, 255 * fade))   # sempre sobre cor
            tw = cw - 72 - 10
            size = next((sz for sz in (15, 14, 13, 12) if g.measure("SemiBold", sz, title)[0] <= tw), 12)
            sub = g.wrap("Regular", 11, self.card_subtitle(cid), cw - 82)[:2]
            ty = y + ch / 2 - (size + 4 + 15 * len(sub)) / 2 + lift
            g.text("SemiBold", size, title, x + 72, ty, alpha(ON_TEXT if on else TEXT, 255 * fade))
            if cid in self.alerts:
                lvl, n = self.alerts[cid]
                bc = LEVEL[lvl]
                px_, py_ = bx + 44, by + 2           # no canto do ícone: o texto usa a largura toda
                ring = 0.5 + 0.5 * math.sin(self.t * 4 + i)
                g.sprite(("ring", lvl), 26, 26, 1, lambda ox, oy, bc=bc: g.circle(ox + 13, oy + 13, 13, alpha(bc, 90)),
                         px_ - 13, py_ - 13, 255 * ring * fade)
                g.circle(px_, py_, 10, alpha(bc, 255 * fade))
                g.text("Bold", 11, str(n), px_, py_ + 0.5, alpha(hexc("10142a"), 255 * fade), "c", "m")
            for k, ln in enumerate(sub):
                g.text("Regular", 11, ln, x + 72, ty + size + 6 + 15 * k,
                       alpha(ON_TEXT if on else MUTED, (230 if on else 255) * fade))
        self.draw_footer([("A", "Abrir", TEXT), ("POWER", "Energia", MUTED)])

    def draw_page(self, dt, fade):
        g = self.g
        cid, title, ic, c1, c2 = card_info(self.page)
        off = 0
        a = 255 * fade
        # título
        g.rrect(22 + off, 66, 44, 44, 14, alpha(hexc(c1), a), alpha(hexc(c2), a))
        g.icon(ic, 32 + off, 76, 24, alpha(ON_TEXT, a))
        g.text("Bold", 22, title, 78 + off, 64, alpha(TEXT, a))
        f = self.findings
        if f:
            lvl = f["nivel"]
            msg = {"ok": "Tudo certo por aqui", "aviso": "Alguns avisos", "problema": "Precisa de atenção"}[lvl]
            if cid == "ajuda":
                lvl, msg = "info", "Manual, cuidados e créditos"
            g.circle(83 + off, 102, 4, alpha(LEVEL[lvl], a))
            g.text("Medium", 12, msg, 92 + off, 93, alpha(MUTED, a))
        else:
            g.text("Medium", 12, "Verificando...", 78 + off, 93, alpha(MUTED, a))

        two = cid in TWO_COLS
        # diagnóstico (esquerda); Sistema não tem: as ações ocupam as duas colunas
        px, py, pw, ph = 22 + off, 126, 330, 300
        if two:
            f = None
        if two:
            pass
        elif not f:
            g.rrect(px, py, pw, ph, 20, alpha(GLASS, 14 * fade))
            g.stroke(px, py, pw, ph, 20, ink(16 * fade))
            for k in range(3):
                yy = py + 44 + k * 52
                sh = 0.5 + 0.5 * math.sin(self.t * 4 - k)
                g.rrect(px + 18, yy, pw - 36, 38, 12, ink((10 + 12 * sh) * fade))
        else:
            g.rrect(px, py, pw, ph, 20, alpha(GLASS, 14 * fade))
            g.stroke(px, py, pw, ph, 20, ink(16 * fade))
            g.clip(px, py, pw, ph)
            # Altura de cada item; se não couberem todos, L1/R1 rolam um item por vez.
            top, bottom = py + 14, py + ph - 12
            blocks = []
            sel = self.items[self.item_sel] if self.items else None
            hint = [("dica", sel.tip)] if getattr(sel, "tip", None) else []
            for lvl, txt in hint + f["achados"]:
                lines = g.wrap("Regular", 13, txt, pw - 74)
                blocks.append((lvl, lines, max(40, 14 + 19 * len(lines))))
            offs = [0]
            for *_x, bh in blocks:
                offs.append(offs[-1] + bh + 8)
            room = bottom - top
            if offs[-1] - 8 > room:
                bottom -= 18                          # espaço para "R1: mais N"
                room = bottom - top
            # o último início que ainda mostra o fim da lista
            self.find_max = next((k for k in range(len(blocks)) if offs[-1] - 8 - offs[k] <= room),
                                 len(blocks) - 1) if blocks else 0
            self.find_top = min(self.find_top, self.find_max)
            self.find_scroll = approach(self.find_scroll, offs[self.find_top], dt, 16)
            if abs(self.find_scroll - offs[self.find_top]) < 0.5:
                self.find_scroll = float(offs[self.find_top])
            sc = round(self.find_scroll)              # inteiro: menos geometria nova
            g.clip(px, top, pw, bottom - top)
            # itens que não aparecem inteiros embaixo (o de cima pode aparecer cortado)
            below = sum(1 for k, b in enumerate(blocks) if top + offs[k] - sc + b[2] > bottom + 2)
            for k, (lvl, lines, bh) in enumerate(blocks):
                yy = top + offs[k] - sc
                if yy + bh < top:
                    continue
                if yy >= bottom:
                    break
                c = LEVEL[lvl]
                g.rrect(px + 12, yy, pw - 24, bh, 12, alpha(c, 22 * fade))
                g.circle(px + 32, yy + 20, 11, alpha(c, 230 * fade))
                g.icon(LEVEL_ICON[lvl], px + 24, yy + 12, 16, alpha(hexc("10142a"), a))
                for n, line in enumerate(lines):
                    g.text("Regular", 13, line, px + 52, yy + 8 + 19 * n, alpha(TEXT, a))
            g.clip(px, py, pw, ph)
            if self.find_top > 0:
                g.text("Medium", 11, f"L1: {self.find_top} acima", px + pw - 18, py + ph - 24, alpha(FAINT, a), "r")
            if below:
                g.text("Medium", 12, f"R1: mais {below} item(ns)", px + 18, py + ph - 24, alpha(FAINT, a))
        g.clip()

        # controles (direita)
        cx, cy, cw = 366 + off * 1.5, 126, 252
        half = (len(self.items) + 1) // 2 if two else len(self.items)
        if two:                                 # 6 linhas por coluna: mais baixas e a partir de mais acima
            cw, cx, cy = (W - 44 - 16) / 2, 22, 116
        xs = [cx if k < half else cx + cw + 16 for k in range(len(self.items))]
        # Altura de cada item: ações com nome longo quebram em linhas (ao lado
        # da etiqueta SUGERIDO, se houver) e o botão cresce para caber tudo.
        gap, tag = 10, "SUGERIDO"
        tw = g.measure("Bold", 9, tag)[0] + 14
        layout, y = [], cy + 22
        for k, it in enumerate(self.items):
            if k == half:
                y = cy + 22                     # segunda coluna recomeça no topo
            lines = None
            ih = 44 if two else 50
            if isinstance(it, Action):
                lines = g.wrap("SemiBold", 14, it.label, cw - 46 - 14)
                extra = 20 if getattr(it, "suggested", False) else 0   # selo SUGERIDO em cima
                ih = max(44 if two else 50, 16 + 19 * len(lines) + extra)
            layout.append((y, ih, lines))
            y += ih + (5 if two else gap)
        # muitas ações (Ajuda): a coluna rola para o item escolhido caber acima do rodapé
        top, bottom = cy + 18, H - 52
        sy, sh = layout[self.item_sel][:2] if layout else (cy + 22, 50)
        want = max(0, sy + sh - bottom) if sy - (cy + 22) > 0 else 0
        self.act_off = approach(getattr(self, "act_off", 0), want, dt, 18)
        same = lambda k: (k < half) == (self.item_sel < half)   # só a coluna do item escolhido rola
        layout = [(y - (self.act_off if same(k) else 0), ih, lines) for k, (y, ih, lines) in enumerate(layout)]
        sel_y, sel_h = layout[self.item_sel][:2] if layout else (cy + 22, 50)
        g.clip(cx - 20, top, (xs[-1] if xs else cx) + cw + 40 - cx, bottom - top + 4)
        self.item_y = approach(self.item_y or sel_y, sel_y, dt, 18)
        sel_x = xs[self.item_sel] if xs else cx
        self.item_x = sel_x if not two else approach(getattr(self, "item_x", None) or sel_x, sel_x, dt, 18)
        self.item_h = approach(getattr(self, "item_h", 0) or sel_h, sel_h, dt, 18)
        a1, a2 = self.accent
        ih_ = round(self.item_h)
        g.sprite(("it", a1, a2, ih_), cw, ih_, 16, lambda ox, oy: (
                 g.glow(ox, oy, cw, ih_, 16, alpha(a1, 80), 16),
                 g.rrect(ox, oy, cw, ih_, 16, alpha(a1, 235), alpha(a2, 235))),
                 self.item_x, self.item_y, 255 * fade)
        self.hits_page = [(k, xs[k], y, cw, ih) for k, (y, ih, _) in enumerate(layout) if top <= y + ih / 2 <= bottom]
        for k, it in enumerate(self.items):
            y, ih, lines = layout[k]
            cx = xs[k]
            on = k == self.item_sel
            if not on:
                g.rrect(cx, y, cw, ih, 16, alpha(GLASS, 16 * fade))
            danger = getattr(it, "danger", False)
            icol = LEVEL["problema"] if danger and not on else (ON_TEXT if on else TEXT)
            g.icon(it.icon, cx + 14, y + ih / 2 - 11, 22, alpha(icol, a))
            if isinstance(it, Slider):
                it.shown = approach(it.shown, it.value, dt, 16)
                g.text("SemiBold", 13, it.label, cx + 46, y + 8, alpha(ON_TEXT if on else TEXT, a))
                g.text("SemiBold", 13, f"{it.value}%", cx + cw - 14, y + 8, alpha(ON_TEXT if on else TEXT, a), "r")
                bx, by, bw = cx + 46, y + 33, cw - 60
                g.rrect(bx, by, bw, 6, 3, ((255, 255, 255) if on else INK) + ((70 if on else 30) * fade,))
                g.rrect(bx, by, max(6, bw * it.shown / 100), 6, 3, alpha(TEXT if on else hexc(c1), a))
                g.circle(bx + bw * it.shown / 100, by + 3, 7 if on else 5, alpha(ON_TEXT if on else TEXT, a))
            elif isinstance(it, Choice):
                g.text("Regular", 11, it.label, cx + 46, y + 7, alpha(ON_TEXT if on else MUTED, a))
                val = str(it.names.get(it.options[it.index], it.options[it.index]))
                g.text("SemiBold", 14, val, cx + 46, y + 22, alpha(ON_TEXT if on else TEXT, a))
                if on:
                    g.chevron(cx + cw - 44, y + ih / 2, 9, alpha(ON_TEXT if on else TEXT, a), left=True)
                    g.chevron(cx + cw - 20, y + ih / 2, 9, alpha(ON_TEXT if on else TEXT, a))
            else:
                sug = getattr(it, "suggested", False)
                ty = y + (ih - 19 * len(lines) - (20 if sug else 0)) / 2 + (20 if sug else 0)
                if sug:
                    g.rrect(cx + 46, ty - 21, tw, 16, 8, (255, 255, 255, 60) if on else alpha(LEVEL["aviso"], 70))
                    g.text("Bold", 9, tag, cx + 46 + tw / 2, ty - 12.5, alpha(ON_TEXT if on else TEXT, a), "c", "m")
                for n, ln in enumerate(lines):
                    g.text("SemiBold", 14, ln, cx + 46, ty + 19 * n + 9.5, alpha(ON_TEXT if on else TEXT, a), "l", "m")
        g.clip()
        it = self.items[self.item_sel] if self.items else None
        hints = [("A", "Confirmar", TEXT), ("B", "Voltar", MUTED)]
        if isinstance(it, Slider) or (isinstance(it, Choice) and self.page in TWO_COLS):
            hints.insert(1, ("Analógico", "Ajustar", MUTED))   # o direcional fica para navegar
        elif isinstance(it, Choice):
            hints.insert(1, ("LR", "Ajustar", MUTED))
        if f and self.find_max > 0:
            hints.append(("L1 / R1", "Rolar", MUTED))
        self.draw_footer(hints)

    def draw_overlays(self, dt):
        g = self.g
        if self.picker:
            self.draw_picker(dt)
        if getattr(self, "sheet", None):
            self.draw_sheet(dt)
        if getattr(self, "danger", None):
            self.draw_danger(dt)
        if getattr(self, "capture", None):
            self.draw_capture()
        if self.busy:
            g.rrect(0, 0, W, H, 0, (5, 7, 20, 170), feather=0)
            g.circle(W / 2, H / 2 - 20, 30, ink(20))
            g.arc(W / 2, H / 2 - 20, 30, 5, self.t * 400, self.t * 400 + 280, alpha(self.accent[0], 255))
            g.text("Medium", 14, self.busy, W / 2, H / 2 + 30, TEXT, "c")
        if self.modal:
            m = self.modal
            g.rrect(0, 0, W, H, 0, (5, 7, 20, 175), feather=0)
            lines = []
            for ln in g.wrap("Regular", 13, m["text"], 380):
                lines.append(ln)
            lines = lines[:12]
            img = m.get("image")
            mh = 152 + 19 * len(lines) + (220 if img else 0)
            mx, my, mw = (W - 440) / 2, (H - mh) / 2, 440
            g.glow(mx, my, mw, mh, 24, alpha(self.accent[0], 60), 26)
            g.rrect(mx, my, mw, mh, 24, MODAL_A, MODAL_B)
            g.stroke(mx, my, mw, mh, 24, ink(25))
            g.rrect(mx + 24, my + 22, 38, 38, 12, self.accent[0], self.accent[1])
            g.icon(m["icon"], mx + 32, my + 30, 22, ON_TEXT)
            g.text("Bold", 18, m["title"], mx + 74, my + 28, TEXT)
            for k, ln in enumerate(lines):
                g.text("Regular", 13, ln, mx + 30, my + 74 + 19 * k, TEXT)
            if img:
                qy = my + 82 + 19 * len(lines)
                g.rrect(W / 2 - 98, qy, 196, 196, 16, (255, 255, 255, 255))
                g.image(img, W / 2 - 88, qy + 10, 176)
                if m.get("url"):
                    g.text("SemiBold", 13, m["url"], W / 2, qy + 204, TEXT, "c")
            bw = (mw - 60 - 12 * (len(m["buttons"]) - 1)) / len(m["buttons"])
            for k, label in enumerate(m["buttons"]):
                bx, by = mx + 30 + k * (bw + 12), my + mh - 54
                if k == m["sel"]:
                    g.rrect(bx, by, bw, 38, 14, self.accent[0], self.accent[1])
                else:
                    g.rrect(bx, by, bw, 38, 14, ink(22))
                g.text("SemiBold", 13, label, bx + bw / 2, by + 19.5, ON_TEXT if k == m["sel"] else TEXT, "c", "m")
        if self.reader:
            self.draw_reader(dt)
        if getattr(self, "pad", None):
            self.draw_pad(dt)
        if getattr(self, "kbd", None):
            self.draw_keyboard(dt)
        if self.toast:
            txt, lvl, until = self.toast
            left = until - self.t
            if left <= 0:
                self.toast = None
            else:
                k = min(1, left / 0.3, (3.5 - left) / 0.3 + 0.0001 if left > 3.2 else 1)
                tw = min(560, g.measure("Medium", 13, txt)[0] + 70)
                tx, ty = (W - tw) / 2, H - 96 + (1 - k) * 30
                g.rrect(tx, ty, tw, 40, 20, alpha(TOAST, 245 * k))
                g.circle(tx + 22, ty + 20, 9, alpha(LEVEL[lvl], 255 * k))
                g.icon(LEVEL_ICON[lvl], tx + 15, ty + 13, 14, alpha(hexc("10142a"), 255 * k))
                g.text("Medium", 13, txt, tx + 40, ty + 20.5, alpha(TEXT, 255 * k), "l", "m")

    def reader_lines(self, text, width):
        """(peso, tamanho, texto, altura) de cada linha; "# " vira título."""
        key = ("reader", text, width)
        hit = self.g.wcache.get(key)
        if hit is None:
            hit = []
            for para in text.split("\n"):
                if para.startswith("# "):
                    if hit:
                        hit.append(("Regular", 8, "", 8))
                    for ln in self.g.wrap("SemiBold", 15, para[2:], width):
                        hit.append(("SemiBold", 15, ln, 24))
                elif not para.strip():
                    hit.append(("Regular", 8, "", 10))
                else:
                    for ln in self.g.wrap("Regular", 13, para, width):
                        hit.append(("Regular", 13, ln, 20))
            self.g.wcache[key] = hit
        return hit

    def draw_reader(self, dt):
        g, r = self.g, self.reader
        g.rrect(0, 0, W, H, 0, (5, 7, 20, 190), feather=0)
        mx, my, mw, mh = 24, 20, W - 48, H - 40
        g.rrect(mx, my, mw, mh, 22, MODAL_A, MODAL_B)
        g.stroke(mx, my, mw, mh, 22, ink(25))
        a1, a2 = self.accent
        g.rrect(mx + 20, my + 16, 36, 36, 12, a1, a2)
        g.icon(r["icon"], mx + 28, my + 24, 20, ON_TEXT)
        g.text("Bold", 18, r["title"], mx + 68, my + 22, TEXT)
        lines = self.reader_lines(r["text"], mw - 70)
        ty, th = my + 66, mh - 66 - 44
        # rolagem por linha: "top" é a primeira linha visível
        heights = [ln[3] for ln in lines]
        total, fit = sum(heights), 0
        acc = 0
        for h_ in reversed(heights):        # quantas linhas do fim cabem na tela
            if acc + h_ > th:
                break
            acc += h_
            fit += 1
        r["max"] = max(0, len(lines) - fit)
        r["top"] = min(r["top"], r["max"])
        r["scroll"] = approach(r["scroll"], sum(heights[:r["top"]]), dt, 18)
        g.clip(mx, ty, mw, th)
        y = ty - r["scroll"]
        for weight, size, txt, h_ in lines:
            if y + h_ > ty - 30 and y < ty + th and txt:
                col = TEXT if weight == "SemiBold" else TEXT
                g.text(weight, size, txt, mx + 32, y, col)
            y += h_
        g.clip()
        if total > th:   # barra de rolagem
            bh = max(30, th * th / total)
            by = ty + (th - bh) * (r["scroll"] / max(1, sum(heights[:r["max"]])))
            g.rrect(mx + mw - 14, ty, 4, th, 2, ink(18))
            g.rrect(mx + mw - 14, by, 4, bh, 2, alpha(a1, 220))
        g.text("Regular", 12, "Cima/baixo: rolar  ·  Esquerda/direita: pular", mx + 24, my + mh - 30, MUTED)
        self.btn_glyph(mx + mw - 110, my + mh - 32, "B", TEXT)
        g.text("Regular", 12, "Voltar", mx + mw - 82, my + mh - 30, MUTED)

    def frame(self, dt):
        self.t += dt
        if getattr(self, "pad", None):
            self.pad_tick(time.monotonic())
        if self.page and not self.loading:
            self.live_refresh()
        while self.pending:
            done, res, had_busy = self.pending.pop(0)
            if had_busy:
                self.busy = None
            done(res)
        if self.page is None and self.view == "lib":
            tgt = card_info("jogos")
        elif self.page is None:
            tgt = CARDS[self.sel]
        else:
            tgt = card_info(self.page)
        # cor troca de uma vez: uma cor intermediária por quadro refaria a geometria
        self.accent = [hexc(tgt[3]), hexc(tgt[4])]
        self.page_anim = approach(self.page_anim, 1.0 if self.page else 0.0, dt, 12)
        g = self.g
        g.clear()
        self.draw_bg(dt)
        if self.loading:
            self.draw_loading(dt)
            return
        self.draw_header()
        p = self.page_anim
        if p < 0.01 or p > 0.99:
            self.snap = None
        if p < 0.01 and not self.page:
            self.draw_home(dt, 1)
        elif p > 0.99 and self.page:
            self.draw_page(dt, 1)
        else:
            # Transição: cada tela vai inteira (opaca, no lugar) para uma
            # textura, e a GPU só mistura as duas. Mudar o alfa e a posição das
            # formas a cada quadro anularia o cache de geometria.
            # As telas não mudam nesses 0,3 s: desenha uma vez só, no início.
            home, page = g.layer("home"), g.layer("page")
            key = (self.page, self.last_page)
            if self.snap != key:
                self.snap = key
                g.begin_layer(home)
                self.draw_home(dt, 1)
                g.begin_layer(page)
                cur, self.page = self.page, self.page or self.last_page
                self.draw_page(dt, 1)
                self.page = cur
                g.end_layer()
            g.draw_layer(home, -24 * p, 255 * (1 - p))
            g.draw_layer(page, 24 * (1 - p), 255 * p)
        self.draw_overlays(dt)

    def draw_loading(self, dt):
        g = self.g
        if self.results and self.warm:
            self.load_label = "Montando o menu..."
            self.load_done = self.load_total - len(self.warm)
        elif self.results:
            self.load_done = self.load_total
        frac = self.load_done / max(1, self.load_total)
        self.load_shown = approach(self.load_shown, frac, dt, 10)
        a1, a2 = self.accent
        cx, cy = W / 2, H / 2 - 40
        g.glow(cx - 40, cy - 40, 80, 80, 24, alpha(a1, 90), 20)
        g.image("logo-160", cx - 40, cy - 40, 80, smooth=True)
        g.arc(cx, cy, 62, 4, self.t * 300 % 360, self.t * 300 % 360 + 260, alpha(a1, 230))
        g.text("Bold", 24, f"Bem-vindo, {self.player}" if self.player else "Bem-vindo", cx, cy + 82, TEXT, "c", "m")
        if self.results and not self.warm and self.load_shown > 0.98:
            self.loading = False
            self.first_screens()
            if RESUME == "testar":
                self.sel = next(i for i, c in enumerate(CARDS) if c[0] == "ferramentas")
                self.open_page("testar")
                self.show_test_result()
            elif RESUME in ("biblioteca", "port"):   # voltou de um jogo: a lista no mesmo lugar
                self.view = "lib"
            elif RESUME in [c[0] for c in CARDS]:    # voltou de uma ferramenta do Omni36OS
                self.sel = next(i for i, c in enumerate(CARDS) if c[0] == RESUME)
                self.open_page(RESUME)
            elif RESUME in SUBPAGES:                 # ferramenta aberta de uma subpágina (ex.: RetroArch)
                self.sel = next(i for i, c in enumerate(CARDS) if c[0] == PARENT[RESUME])
                self.open_page(RESUME)
            try:
                os.remove(POWER_PRESS)                   # de um menu que não fechou direito
            except OSError:
                pass
            try:
                if time.time() - os.path.getmtime(POWER_FLAG) < 60:
                    self.want_power = self.power_return = True   # aberto pelo power num jogo
                os.remove(POWER_FLAG)
            except OSError:
                pass

    def prewarm(self):
        """Monta a geometria e o texto de uma página por quadro, fora da tela,
        para a primeira abertura de cada uma não engasgar."""
        if not self.warm or self.page or self.page_anim > 0.01 or not self.results:
            return
        cid = self.warm.pop(0)
        if cid == "home":
            keep = (self.sel_x, self.sel_y)
            self.g.begin_layer(self.g.layer("warm"))
            for i, c in enumerate(CARDS):   # destaque, selo e cor de cada cartão
                self.sel, self.accent = i, [hexc(c[3]), hexc(c[4])]
                self.draw_header()
                self.draw_home(0.016, 1)
            self.sel, (self.sel_x, self.sel_y) = 0, keep
            self.accent = [hexc(CARDS[0][3]), hexc(CARDS[0][4])]
            self.g.end_layer()
            return
        saved = (self.page, getattr(self, "items", None), getattr(self, "item_sel", 0),
                 getattr(self, "findings", None), getattr(self, "item_y", 0.0))
        self.page = cid
        self.items = self.build_items(cid) if cid != "pendrive" else []
        self.item_sel, self.findings, self.item_y = 0, self.home_check, 0.0
        self.g.begin_layer(self.g.layer("warm"))
        self.draw_page(0.016, 1)
        self.g.end_layer()
        self.page, self.items, self.item_sel, self.findings, self.item_y = saved

    def run(self):
        demo = [s for s in os.environ.get("OMNI_DEMO", "").split(",") if s]
        shot_dir = os.environ.get("OMNI_SHOT_DIR", ".")
        shots, next_demo = 0, time.monotonic() + 1.0
        last = time.monotonic()
        while self.running:
            now = time.monotonic()
            dt = min(0.05, now - last)
            last = now
            self.poll()
            self.capture_poll()
            self.power_check()
            if demo and now >= next_demo and not self.busy:
                cmd = demo.pop(0)
                next_demo = now + 0.45
                if cmd.startswith("wait"):
                    next_demo = now + int(cmd[4:]) / 1000
                elif cmd == "shot":
                    shots += 1
                    self.frame(dt)
                    self.g.screenshot(os.path.join(shot_dir, f"{shots:02d}.ppm"))
                    self.g.present()
                    continue
                elif cmd == "power":
                    self.want_power = True
                elif cmd == "quit":
                    self.running = False
                elif cmd.startswith("pad:"):       # teste: aperta (ou solta, com -) um botão no teste do controle
                    n = int(cmd[4:])
                    self.pad_event("btn", abs(n), n >= 0 and not cmd[4:].startswith("-"), now)
                elif cmd.startswith("axis:"):
                    k, v = cmd[5:].split("=")
                    self.pad_event("axis", int(k), int(v), now)
                elif cmd.startswith("warn:"):      # teste: abre o aviso sem rodar nada
                    secs, hold, risk, undo = DANGER[cmd[5:]]
                    self.warn(cmd[5:], "Teste do aviso.", lambda: setattr(self, "toast", ("teste: passou", "ok", self.t + 3.5)),
                              secs, hold, risk=risk, undo=undo)
                elif cmd in ("hold", "release"):
                    self.ok_held = cmd == "hold"
                    if cmd == "hold":
                        self.handle("ok")
                else:
                    self.handle(cmd)
            self.frame(dt)
            self.g.present()
            if self.loading:
                self.prewarm()
            # Ritmo: 30 quadros/s em uso e 10 parado. A 60 quadros/s sem parar a
            # Omni36OS ocupava 70% de um núcleo e deixava o aparelho perto de 80 °C.
            moving = (self.loading or self.busy or getattr(self, "danger", None) or self.toast or 0.01 < self.page_anim < 0.99
                      or getattr(self, "kbd", None) or getattr(self, "pad", None)
                      or now - self.last_input < IDLE_AFTER)
            spare = 1 / (FPS_ACTIVE if moving else FPS_IDLE) - (time.monotonic() - now)
            if spare > 0:
                time.sleep(spare)
        gfx.SDL_Quit()


if __name__ == "__main__":
    App().run()
