#!/usr/bin/env python3
"""Omni36OS — interface gráfica (SDL2) do assistente do R36S.

Tela inicial com 8 cartões; cada cartão abre uma página com o diagnóstico
(regras fixas de omni_checks.py) à esquerda e os controles à direita.
Controle: direcional/analógico navega, A confirma, B volta, Select+Start sai.
Os botões A/B seguem a inversão do ES ou do dArkOS.

Variáveis: OMNI_FAKE=1 (dados de mentira, para desenhar no PC),
OMNI_WINDOWED=1, OMNI_DEMO="right,ok,wait800,shot,..." + OMNI_SHOT_DIR (roteiro
com screenshots PPM, para testar sem mãos).
"""
import ctypes as C
import json
import math
import os
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
    import omni_tools

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
LEVEL = {"ok": hexc("34d399"), "aviso": hexc("fbbf24"), "problema": hexc("f87171"), "info": hexc("60a5fa")}
LEVEL_ICON = {"ok": "check", "aviso": "alert-triangle", "problema": "x", "info": "info-circle"}

CARDS = [
    # id, título, ícone, cor 1, cor 2
    ("checkup", "Verificar", "stethoscope", "22d3ee", "3b82f6"),
    ("bateria", "Bateria", "battery-charging", "a3e635", "16a34a"),
    ("som", "Som", "volume", "f472b6", "a855f7"),
    ("tela", "Tela e sistema", "sun", "fbbf24", "f97316"),
    ("desempenho", "Desempenho", "gauge", "fb7185", "e11d48"),
    ("pendrive", "Pendrive USB", "usb", "818cf8", "4f46e5"),
    ("jogos", "Jogos", "device-gamepad-2", "c084fc", "7c3aed"),
    ("testar", "Testar ports", "player-play", "34d399", "059669"),
    ("ferramentas", "Ferramentas", "adjustments", "94a3b8", "475569"),
    ("ajuda", "Ajuda", "help-circle", "60a5fa", "a78bfa"),
]
COLS = 3
# Páginas abertas de dentro de outro card: B volta para o card de origem e os
# alertas delas aparecem no ponto do card de origem.
SUBPAGES = {"cartoes": ("Cartões SD", "device-sd-card", "2dd4bf", "0284c7", "desempenho"),
            "backup": ("Backup", "device-floppy", "60a5fa", "a78bfa", "ajuda"),
            "retroarch": ("RetroArch", "adjustments", "c084fc", "7c3aed", "ajuda")}
PARENT = {cid: v[4] for cid, v in SUBPAGES.items()}


def card_info(cid):
    """(id, título, ícone, cor 1, cor 2) de um card ou subpágina."""
    if cid in SUBPAGES:
        return (cid, *SUBPAGES[cid][:4])
    return next(c for c in CARDS if c[0] == cid)
FPS_ACTIVE, FPS_IDLE, IDLE_AFTER = 30, 10, 4.0   # quadros/s; segundos sem botão até ficar parado
LIB_POS = "/tmp/omni36os-biblioteca.json"
HUB = os.environ.get("OMNI_HUB", "")         # boot/atalho/saida: tela inicial; jogo: por cima de um jogo
RESUME = os.environ.get("OMNI_RESUME", "")   # "testar": o Omni36OS voltou de um teste de port

import omni_help
from omni_help import TELEGRAM

HERE = os.path.dirname(os.path.abspath(__file__))


def omni_version():
    try:
        with open(os.path.join(HERE, "VERSION")) as f:
            return f.read().strip() or "?"
    except OSError:
        return "?"


def about_findings():
    """Painel da Ajuda: qual Omni36OS e qual dArkOS estão rodando."""
    ver = omni_version()
    inst = time.strftime("%d/%m/%Y %H:%M", time.localtime(os.path.getmtime(os.path.join(HERE, "omni_ui.py"))))
    out = [("info", f"Omni36OS versão {ver}, instalado em {inst}.")]
    news = next((n for n in omni_help.NOVIDADES if n[0] == ver), None)
    if news:
        out.append(("info", f"Novidades desta versão: {news[2][0]}"))
    try:
        with open("/home/ark/.config/.VERSION") as f:
            d = f.read().strip()
        out.append(("info", f"dArkOS de {d[2:4]}/{d[:2]}/{d[4:]}." if len(d) == 8 else f"dArkOS {d}."))
    except OSError:
        pass
    out.append(("info", "Comunidade R36S Brasil no Telegram: " + TELEGRAM))
    return out

FAKE_GAMES = [
    {"name": "snes", "full": "Super NES", "path": "/roms2/snes", "n_unknown": 0, "unknown": [], "games": [
        {"path": "/roms2/snes/Chrono Trigger.sfc", "name": "Chrono Trigger", "size": 4194304, "fav": 1,
         "plays": 12, "time": 18400, "last": "20261024T201000",
         "desc": "Crono e os amigos viajam no tempo para impedir o fim do mundo."},
        {"path": "/roms2/snes/Super Mario World.sfc", "name": "Super Mario World", "size": 524288, "plays": 3,
         "time": 3600, "last": "20261020T101000"},
        {"path": "/roms2/snes/Zelda.sfc", "name": "The Legend of Zelda: A Link to the Past", "size": 1048576}]},
    {"name": "psx", "full": "PlayStation", "path": "/roms2/psx", "n_unknown": 2, "unknown": ["leia.txt.bak", "x.zip"],
     "games": [{"path": "/roms2/psx/Crash.chd", "name": "Crash Bandicoot", "size": 420000000, "fav": 1}]},
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
            return {"nivel": "aviso", "acoes": ["restaurar_audio", "ligar_pendrive"] if name == "checkup" else [], "achados": [
                ("ok", "Bateria em 87%."), ("ok", "Temperatura normal: 52 °C."),
                ("aviso", "Cartão de jogos: 62.5 GB, fabricante não identificado (código 0xfe, nome \"SD\"), "
                          "comum em cartões genéricos."),
                ("problema", "A saída de som está em SPK, o certo é SPK_HP.")]}
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
            return {"brilho": 40, "volume": 60, "gov": "ondemand", "govs": ["powersave", "ondemand", "performance"],
                    "part": "roms2", "pendrive": False, "cpu_max": 1296, "cpu_freqs": [1296, 1416, 1512],
                    "gpu_max": 520, "gpu_freqs": [400, 480, 520, 600], "gamma": 1.0, "led": "verde",
                    "hub": "desligada", "atalho": "desligado", "tema": THEME}[what]
        if what == "brilho":
            return omni.get_brightness()
        if what == "volume":
            return omni.get_volume()
        if what == "gov":
            return omni.get_preferred_governor()
        if what == "govs":
            return [g for g in ("powersave", "ondemand", "schedutil", "performance") if g in omni.get_cpu_governors()]
        if what == "part":
            return omni.usb_run("part") or "roms2"
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
        if what == "gamma":
            return omni.get_gamma()
        if what == "led":
            return omni.get_led()
        if what == "tema":
            return THEME
        if what == "hub":
            return omni.get_hub()
        if what == "atalho":
            return omni.get_hotkey()

    def set(self, what, value):
        if what == "tema":
            apply_theme(value)
            if not FAKE:
                os.makedirs(os.path.dirname(THEME_FILE), exist_ok=True)
                with open(THEME_FILE, "w") as f:
                    f.write(value)
            return "tema"
        if FAKE:
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
        if what == "gamma":
            return omni.set_gamma({"value": value})
        if what == "led":
            return omni.set_led({"color": value})
        if what == "hub":
            return omni.set_hub({"mode": value})
        if what == "atalho":
            return omni.set_hotkey({"mode": value})

    def run(self, tool, args=None):
        if FAKE:
            time.sleep(1.2)
            return "Escrita: 18.2 MB/s\nLeitura: 41.0 MB/s"
        return omni.run_tool({"tool": tool, "args": args or {}})


D = Data()
if not FAKE:
    try:
        omni.migrate_cpu_settings()   # modo do processador de versões antigas
        omni.relax_clocks()           # o perfmax do ES deixou tudo no máximo
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


KIND_NAMES = {"nativo": "Nativo", "janela": "Janelas", "app": "App", "perigoso": "Cuidado"}
HUB_NAMES = {"desligada": "Desligada (ES direto)", "sempre": "Omni36OS no boot", "alertas": "Só com alertas"}
HOTKEY_NAMES = {"desligado": "Desligado", "ligado": "No menu do ES", "jogo": "Menu e jogos (beta)"}


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
        self.view = "lib"             # lib: biblioteca de jogos (tela inicial); menu: os cards (START)
        self.lib = {"sys": 0, "game": 0, "top": 0.0, "stop": 0.0}
        try:                          # volta para o mesmo jogo depois de jogar
            with open(LIB_POS) as f:
                self.lib.update(json.load(f))
        except (OSError, ValueError):
            pass
        self.toast = None             # (texto, nível, até)
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
        if cid == "backup":
            return self._backup()
        if cid == "jogos":
            return self._jogos()
        if cid == "ferramentas":
            return self._ferramentas()
        name = {"som": "sem_som", "tela": "atualizar", "pendrive": "pc"}.get(cid, cid)
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

    def reload_findings(self):
        cid = self.page
        if cid == "ajuda":
            self.findings = {"nivel": "ok", "achados": about_findings(), "acoes": []}
            return
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
        acts = []
        omni_checks.check_overclock(f, out, acts)
        z = omni.zram_facts()
        out.append(("info", f"Limites: processador {f['cpu_max_mhz']} MHz, GPU {f['gpu_max_mhz']} MHz. "
                            f"ZRAM {z['zram_mb']} MB ({z['zram_usado_mb']} MB em uso)."))
        out.append(("ok", "Abra \"Cartões SD\" se os jogos demoram para carregar."))
        return omni_checks.finish(out, acts, f)

    def _testar(self):
        groups = FAKE_PORTS if FAKE else omni.port_groups()
        res = {} if FAKE else omni.port_results()
        out = []
        self.port_count = sum(len(g["ports"]) for g in groups)
        acks = set() if FAKE else omni.port_acks()
        for g in groups:
            out.append(("ok", f"{len(g['ports'])} ports em {g['label']}, a pasta que o ES mostra."))
        names = {os.path.basename(p)[:-3] for g in groups for p in g["ports"]}
        fails = sorted(n for n, r in res.items() if r[0] == "falhou" and n in names
                       and f"{n}|{r[1]}" not in acks)
        seen = sum(1 for n, r in res.items() if r[0] == "falhou" and n in names and f"{n}|{r[1]}" in acks)
        if seen:
            out.append(("info", f"{seen} falha(s) já vista(s): continuam marcadas na lista até um novo teste."))
        oks = sum(1 for n, r in res.items() if r[0] == "ok" and n in names)
        for n in fails:
            out.append(("aviso", f"{n} falhou no teste de {res[n][1]}. Relatório em omni36os/logs/{n}/."))
        if oks:
            out.append(("ok", f"{oks} port(s) passaram no último teste."))
        out.append(("info", "O teste abre o port por 15 s e fecha sozinho. Se ele fechar antes, é falha."))
        return omni_checks.finish(out, [], {}) if not FAKE else {
            "nivel": "aviso" if fails else "ok", "achados": out, "acoes": []}

    def games(self, force=False):
        if FAKE:
            self.games_idx = FAKE_GAMES
        elif force or not getattr(self, "games_idx", None):
            self.games_idx = omni_games.index(force)
        return self.games_idx

    def _jogos(self):
        G = omni_games if not FAKE else None
        idx = self.games(force=getattr(self, "games_reindex", False))
        self.games_reindex = False
        games = [g for s in idx for g in s["games"]]
        total = sum(g["size"] for g in games)
        self.game_count = len(games)
        size = (G.human_size(total) if G else f"{total / 1e9:.1f} GB")
        out = [("ok", f"{len(games)} jogos em {sum(1 for s in idx if s['games'])} sistemas · {size}.")]
        if FAKE:
            out += [("problema", "PlayStation: falta a BIOS scph5501.bin (em /roms2/bios). Sem ela os jogos não abrem."),
                    ("aviso", "PlayStation: 2 arquivo(s) que o ES não mostra (extensão errada ou pasta trocada)."),
                    ("info", "Último jogado: Chrono Trigger (Super NES), 24/10/2026.")]
            return {"nivel": "problema", "achados": out, "acoes": []}
        sm = G.summary(idx)
        if sm["ultimo"]:
            last = max((g["last"] for g in games if g.get("last")), default="")
            out.append(("info", f"Último jogado: {sm['ultimo'][0]} ({sm['ultimo'][1]}), {G.human_date(last)}."))
        for s, missing, odd in G.bios_check(idx):
            if missing:
                out.append(("problema", f"{s['full']}: falta a BIOS {', '.join(missing)} (em {G.bios_dir()}). "
                                        "Sem ela os jogos não abrem."))
            if odd:
                out.append(("aviso", f"{s['full']}: BIOS {', '.join(odd)} com versão desconhecida; se der erro, "
                                     "troque por uma conhecida."))
        for s in idx:
            if s["n_unknown"]:
                cut = lambda n: n if len(n) <= 22 else n[:20] + "…"
                ex = ", ".join(cut(os.path.basename(u)) for u in s["unknown"][:2])
                out.append(("aviso", f"{s['full']}: {s['n_unknown']} arquivo(s) que o ES não mostra ({ex}...). "
                                     "Extensão errada ou pasta trocada."))
        dups = G.duplicates(idx)
        if dups:
            out.append(("info", f"{len(dups)} jogo(s) parecem repetidos (mesmo nome, outra versão). "
                                "Veja em \"Repetidos\"."))
        big = max((s for s in idx if s["games"]), key=lambda s: sum(g["size"] for g in s["games"]), default=None)
        if big:
            out.append(("info", f"O que mais ocupa: {big['full']}, "
                                f"{G.human_size(sum(g['size'] for g in big['games']))}."))
        nc = sum(n for _s, n in G.no_cover(idx))
        if nc:
            out.append(("info", f"{nc} jogo(s) sem capa no ES."))
        return omni_checks.finish(out, [], {})

    def _backup(self):
        if FAKE:
            return {"nivel": "ok", "acoes": [], "achados": [("info", "Os backups ficam em /roms2/backup/omni36os.")]}
        out = [("info", f"Os backups ficam em {omni_backup.backup_dir()} (dá para copiar pelo pendrive).")]
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
            extra.append(act)
        self.items = extra + base
        self.item_sel = min(self.item_sel, len(self.items) - 1)

    def systool(self, tool, label, icon, what):
        """Ferramenta do dArkOSen, se existir neste sistema. O Omni36OS volta ao fechar."""
        if not (FAKE or omni.systool_available(tool)):
            return []
        return [Action(label, icon, lambda: self.handoff(tool),
                       confirm=f"Abrir {what} do dArkOSen?\nA Omni36OS fecha, a ferramenta abre em tela cheia "
                               "e o Omni36OS volta quando ela fechar.")]

    def build_items(self, cid):
        A = Action
        recheck = A("Verificar de novo", "refresh", self.reload_findings)
        if cid == "checkup":
            return (self.systool("controle", "Testar o controle", "device-gamepad-2", "o teste de controle")
                    + self.systool("atalhos", "Consertar atalhos", "adjustments", "o conserto dos atalhos globais")
                    + [recheck])
        if cid == "bateria":
            # as sugestões de economia mexem nestes mesmos controles
            out = [Choice("Processador no menu", "cpu", "gov", D.get("govs"), GOV_NAMES),
                   Slider("Brilho", "sun", "brilho", lo=10)]
            out += self.systool("calibrar_bateria", "Calibrar a bateria", "battery-2", "a calibração da bateria")
            return out + [recheck]
        if cid == "som":
            return [Slider("Volume", "volume", "volume"),
                    tagged(A("Restaurar áudio", "rotate", lambda: self.do_action("restaurar_audio"),
                             confirm="Restaurar o áudio do sistema?\nSaída de som padrão e volume em 40%."),
                           "restaurar_audio"), recheck]
        if cid == "tela":
            out = [Slider("Brilho", "sun", "brilho", lo=10),
                   Choice("Gamma (contraste)", "adjustments", "gamma", GAMMAS, {g: f"{g:.1f}" for g in GAMMAS}),
                   Choice("Cor do LED", "bulb", "led", ["verde", "vermelho"], {"verde": "Verde", "vermelho": "Vermelho"}),
                   A("Detalhes da tela", "device-tv", lambda: self.run_info("Tela e modelo", "detect_hardware_and_screen"))]
            out += self.systool("info", "Informações do sistema", "info-circle", "as informações do sistema")
            out += self.systool("splash", "Tela de boot", "power", "o gerenciador da tela de boot")
            out += self.systool("backup", "Backup e migração", "device-floppy", "o assistente de backup e migração")
            return out
        if cid == "desempenho":
            return [Choice("Processador no menu", "cpu", "gov", D.get("govs"), GOV_NAMES),
                    Choice("Limite do processador", "gauge", "cpu_max", D.get("cpu_freqs"),
                           {f: f"{f} MHz" + (" (OC)" if f > 1296 else "") for f in D.get("cpu_freqs")}),
                    Choice("Limite da GPU", "device-gamepad-2", "gpu_max", D.get("gpu_freqs"),
                           {f: f"{f} MHz" + (" (OC)" if f > 520 else "") for f in D.get("gpu_freqs")}),
                    subpage(A("Cartões SD", "device-sd-card", lambda: self.open_page("cartoes")), "cartoes")]
        if cid == "pendrive":
            on = D.get("pendrive")
            tog = A("Desligar pendrive" if on else "Ligar pendrive", "power",
                    lambda: self.do_action("desligar_pendrive" if on else "ligar_pendrive"),
                    confirm=("Desligar o modo pendrive?\nO aparelho reinicia e o Wi-Fi volta." if on else
                             "Ligar o modo pendrive?\nO aparelho reinicia; Wi-Fi e teclado USB param até desligar."))
            tog.act = "desligar_pendrive" if on else "ligar_pendrive"
            return [tog, Choice("Partição no PC", "device-floppy", "part", ["roms2", "roms"],
                                {"roms2": "/roms2 (jogos)", "roms": "/roms (sistema)"}),
                    A("Status", "info-circle", lambda: self.run_info("Pendrive USB", "usb_status")),
                    tagged(A("Limpar lixo do Mac", "x", lambda: self.do_action("limpar_mac", "Procurando o lixo do Mac... (até 1 minuto)"),
                             confirm="Apagar os arquivos ._ e .DS_Store que o Mac cria?\nSeus jogos não são tocados."),
                           "limpar_mac"),
                    A("Restaurar boot", "arrow-back-up", lambda: self.run_tool_toast("usb_restore"),
                      confirm="Voltar o arquivo de boot original?\nO aparelho reinicia.", danger=True)]
        if cid == "cartoes":
            return [A("Detalhes", "info-circle", lambda: self.run_info("Cartões SD", "check_microsd_info")),
                    A("Testar velocidade", "brand-speedtest", self.speed_test),
                    A("Verificar e reparar o cartão de jogos", "device-sd-card", lambda: self.run_tool_toast("schedule_scan"),
                      confirm="Verificar e reparar o cartão de jogos?\nO aparelho reinicia, verifica o cartão e "
                              "volta sozinho. Leva alguns minutos.", danger=True)]
        if cid == "ferramentas":
            cats = [c for c in ("Sistema", "Emuladores", "Jogos", "Outros", "Perigoso")
                    if any(t["cat"] == c for t in self.tool_list())]
            icons = {"Sistema": "cpu", "Emuladores": "device-gamepad-2", "Jogos": "folder", "Outros": "adjustments",
                     "Perigoso": "alert-triangle"}
            return [A(c if c != "Perigoso" else "Perigoso (mexe no boot)", icons[c],
                      lambda c=c: self.open_tools(c)) for c in cats]
        if cid == "jogos":
            return [A("Por sistema", "device-gamepad-2", self.open_systems),
                    A("Favoritos", "check", lambda: self.open_games("Favoritos", self.pick("fav"))),
                    A("Recentes", "clock", lambda: self.open_games("Recentes", self.pick("recent"))),
                    A("Mais jogados", "gauge", lambda: self.open_games("Mais jogados", self.pick("most"))),
                    A("Repetidos", "alert-triangle", self.open_dups),
                    A("Atualizar a lista", "refresh", self.reindex_games)]
        if cid == "testar":
            return [A("Escolher o port", "player-play", self.open_picker),
                    A("Limpar avisos de falha", "check", lambda: self.run_tool_toast("clear_port_alerts")), recheck]
        if cid == "backup":
            return [A(name, icon, lambda m=mod: self.backup_menu(m)) for mod, name, icon in (
                ("omni36os", "Omni36OS", "help-circle"), ("retroarch", "RetroArch", "device-gamepad-2"),
                ("standalone", "Emuladores standalone", "cpu"), ("es", "EmulationStation", "device-tv"))]
        if cid == "ajuda":
            mode = "Sistema no console" if not FAKE and omni.get_mode() == "sistema" else "Lista de Ports"
            return [subpage(A("Backup", "device-floppy", lambda: self.open_page("backup")), "backup"),
                    subpage(A("RetroArch", "adjustments", lambda: self.open_page("retroarch")), "retroarch"),
                    A(f"Mostrar no console: {mode}", "device-tv", self.ask_mode),
                    Choice("Tema", "sun", "tema", list(THEMES), {"escuro": "Escuro", "claro": "Claro"}),
                    Choice("Tela inicial do console", "power", "hub", list(HUB_NAMES), HUB_NAMES),
                    Choice("Atalho L3+R3 / FN+SELECT", "device-gamepad-2", "atalho", list(HOTKEY_NAMES), HOTKEY_NAMES),
                    A("Manual", "book", lambda: self.read("Manual", "book", omni_help.MANUAL)),
                    A("Cuidados", "alert-triangle", lambda: self.read("Cuidados", "alert-triangle", omni_help.CUIDADOS)),
                    A("Novidades", "tag", lambda: self.read(f"Novidades · Omni36OS {omni_version()}", "tag",
                                                          omni_help.novidades_text())),
                    A("Créditos", "users", lambda: self.read("Créditos", "users", omni_help.CREDITOS)),
                    A("Grupo no Telegram", "brand-telegram", self.show_qr),
                    A("Restaurar o ES", "rotate", self.ask_restore_es)]
        if cid == "retroarch":
            return ([tagged(A("Restaurar de fábrica", "rotate", lambda: self.do_action("restaurar_retroarch"),
                             confirm="Restaurar o RetroArch de fábrica?\nUma cópia das configurações atuais fica guardada.",
                             danger=True), "restaurar_retroarch")]
                    + self.systool("ra_manager", "Gerenciador do RetroArch", "adjustments", "o gerenciador do RetroArch")
                    + self.systool("ra_cores", "Restaurar opções dos cores", "cpu", "a restauração das opções dos cores")
                    + [recheck])
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

    def handoff(self, tool):
        if self.busy_game():
            return
        res = "ok" if FAKE else D.run("handoff", {"tool": tool, "card": self.page or ""})
        if res == "ok":
            self.running = False      # o Omni36OS.sh abre a ferramenta
        else:
            self.toast = (res, "aviso", self.t + 3.5)

    def run_tool_toast(self, tool):
        self.worker(lambda: D.run(tool), self._action_done, busy="Fazendo...")

    def speed_test(self):
        def fn():
            if FAKE:
                return D.run("x")
            return omni_checks.lento()

        def done(res):
            if isinstance(res, dict):
                self.findings = res
                self.toast = ("Teste dos cartões concluído", "ok", self.t + 3)
            else:
                self.modal = {"title": "Velocidade", "text": str(res), "icon": "brand-speedtest",
                              "buttons": ["OK"], "sel": 0}
        self.worker(fn, done, busy="Testando os cartões... (até 1 minuto)")

    def show_qr(self):
        self.modal = {"title": "Grupo R36S Brasil", "icon": "brand-telegram", "buttons": ["Fechar"], "sel": 0,
                      "text": "Aponte a câmera do celular para o código:", "image": "qr-telegram", "url": TELEGRAM}

    # --- lista com rolagem (ports para testar, arquivos de backup) ---

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
        if step:
            pk["sel"] = items[max(0, min(len(items) - 1, k + step))]
        elif cmd == "back":
            self.picker = None
            if pk.get("on_back"):
                pk["on_back"]()
        elif cmd == "ok":
            pk["on_ok"](pk["rows"][pk["sel"]])

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
        g.text("Regular", 12, f"{pk['ok_label']}  ·  " + ("L1/R1: letra" if pk.get("letters") else
                                                          "Esquerda/direita: pular"),
               mx + 50, my + mh - 30, MUTED)
        self.btn_glyph(mx + mw - 110, my + mh - 32, "B", TEXT)
        g.text("Regular", 12, "Voltar", mx + mw - 82, my + mh - 30, MUTED)

    # --- ferramentas do dArkOSen ---

    def tool_list(self):
        if FAKE:
            return [{"path": "/opt/system/x.sh", "name": "Calibrar a bateria", "cat": "Sistema", "kind": "janela",
                     "desc": "Ensina ao sistema a carga real da bateria.", "native": None},
                    {"path": "/opt/system/y.sh", "name": "Montar pendrive", "cat": "Sistema", "kind": "nativo",
                     "desc": "Pendrive no OTG.", "native": "usb_mount"},
                    {"path": "/opt/system/z.sh", "name": "Patch do DTB", "cat": "Perigoso", "kind": "perigoso",
                     "desc": "Mexe no boot.", "native": None}]
        if not getattr(self, "tools_cache", None):
            self.tools_cache = omni_tools.tools()
        return self.tools_cache

    def _ferramentas(self):
        ts = self.tool_list()
        self.tool_count = len(ts)
        n = lambda k: sum(1 for t in ts if t["kind"] == k)
        out = [("ok", f"{len(ts)} ferramentas do dArkOSen, as mesmas do menu Opções do ES."),
               ("info", f"{n('nativo')} rodam aqui dentro; {n('janela')} abrem com as janelas do Omni36OS; "
                        f"{n('app')} têm tela própria."),
               ("info", "Ao fechar uma ferramenta, o Omni36OS volta neste card.")]
        if n("perigoso"):
            out.append(("info", f"{n('perigoso')} mexem no boot, no kernel ou no ES: ficam em \"Perigoso\", "
                                 "com aviso duplo."))
        return {"nivel": "ok", "achados": out, "acoes": []} if FAKE else omni_checks.finish(out, [], {})

    def open_tools(self, cat, start=None):
        ts = [t for t in self.tool_list() if t["cat"] == cat]
        colors = {"nativo": LEVEL["ok"], "janela": LEVEL["info"], "app": MUTED, "perigoso": LEVEL["problema"]}
        rows = [{"name": t["name"], "right": (KIND_NAMES[t["kind"]], colors[t["kind"]]), "tool": t} for t in ts]
        self.show_list(cat, "adjustments", rows, lambda r: self.ask_tool(r["tool"], cat, rows.index(r)),
                       "Abrir", start)

    def ask_tool(self, t, cat, k):
        self.picker = None
        back = lambda: self.open_tools(cat, k)
        if t["kind"] == "nativo":
            text = t["desc"] + "\nRoda aqui dentro do Omni36OS."
        elif t["kind"] == "perigoso":
            text = (t["desc"] + "\nEsta ferramenta mexe em arquivos do boot ou do sistema. Se der errado, o console "
                    "pode não ligar: tenha um backup do cartão.")
        else:
            text = t["desc"] + "\nA ferramenta abre em tela cheia e o Omni36OS volta quando ela fechar."

        def go():
            if t["kind"] == "perigoso":
                self.modal = {"title": "Tem certeza?", "icon": "alert-triangle", "sel": 1,
                              "buttons": ["Abrir mesmo assim", "Cancelar"],
                              "text": f"Última chance: {t['name']} mexe no boot. Continuar?",
                              "fns": [lambda: self.run_tool(t), back]}
            else:
                self.run_tool(t)
        self.modal = {"title": t["name"], "icon": "alert-triangle" if t["kind"] == "perigoso" else "adjustments",
                      "sel": 0, "buttons": ["Abrir", "Voltar"], "text": text, "fns": [go, back]}

    def run_tool(self, t):
        if self.busy_game():
            return
        if FAKE:
            self.toast = (f"Abriria {t['name']}", "ok", self.t + 3)
            return
        if t["kind"] == "nativo":
            def done(res):
                txt = f"Erro: {res}" if isinstance(res, Exception) else str(res)
                self.modal = {"title": t["name"], "icon": "check", "buttons": ["OK"], "sel": 0, "text": txt}
            self.worker(lambda: omni_tools.run_native(t["native"]), done, busy="Fazendo...")
            return
        omni.write_text(omni.HANDOFF, f"tool:ferramentas:{t['path']}")
        self.running = False          # o launch.sh roda a ferramenta (run_tool.sh) e reabre o Omni36OS

    # --- biblioteca (tela inicial) ---

    def lib_lists(self):
        """[(título, ícone, [(sistema, jogo)])]: coleções e depois cada sistema."""
        idx = self.games()
        out = []
        for title, icon, what in (("Favoritos", "check", "fav"), ("Recentes", "clock", "recent")):
            pairs = self.pick(what)
            if pairs:
                out.append((title, icon, pairs))
        out += [(s["full"], "device-gamepad-2", [(s, g) for g in s["games"]]) for s in idx if s["games"]]
        return out

    def library_input(self, cmd):
        lists, lb = self.lib_lists(), self.lib
        if cmd == "start":
            self.view = "menu"
            return
        if cmd == "select":
            self.power_menu()
            return
        if not lists:
            return
        lb["sys"] = min(lb["sys"], len(lists) - 1)
        games = lists[lb["sys"]][2]
        if cmd in ("left", "right"):
            lb["sys"] = (lb["sys"] + (1 if cmd == "right" else -1)) % len(lists)
            lb["game"] = 0
        elif cmd in ("up", "down"):
            lb["game"] = (lb["game"] + (1 if cmd == "down" else -1)) % len(games)
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

    def draw_library(self, dt, fade):
        g, lb = self.g, self.lib
        lists = self.lib_lists()
        a1, a2 = self.accent
        if not lists:
            g.text("Bold", 20, "Nenhum jogo encontrado", W / 2, 200, TEXT, "c")
            g.text("Regular", 13, "Copie as ROMs para as pastas de cada sistema no cartão de jogos.", W / 2, 232, MUTED, "c")
            self.draw_footer([("START", "Opções", TEXT), ("SELECT", "Energia", MUTED)])
            return
        lb["sys"] = min(lb["sys"], len(lists) - 1)
        title, icon, games = lists[lb["sys"]]
        lb["game"] = min(lb["game"], len(games) - 1)
        # sistemas (esquerda)
        sx, sy, sw, rh = 16, 64, 200, 30
        top_y, bot_y = sy, H - 44
        vis = int((bot_y - top_y) // rh)
        want = max(0, min(lb["sys"] - vis // 2, len(lists) - vis))
        lb["stop"] = approach(lb.get("stop", 0.0), want * rh, dt, 16)
        g.rrect(sx, sy - 4, sw, bot_y - sy + 4, 18, alpha(GLASS, 14 * fade))
        g.clip(sx, sy, sw, bot_y - sy)
        for i, (t, ic, pairs) in enumerate(lists):
            y = sy + 4 + i * rh - lb["stop"]
            if y < sy - rh or y > bot_y:
                continue
            on = i == lb["sys"]
            if on:
                g.rrect(sx + 6, y, sw - 12, rh - 4, 10, a1, a2)
            name = t if g.measure("SemiBold", 13, t)[0] < sw - 70 else t[:16] + "…"
            g.text("SemiBold" if on else "Regular", 13, name, sx + 16, y + 6, ON_TEXT if on else TEXT)
            g.text("Medium", 11, str(len(pairs)), sx + sw - 18, y + 8, ON_TEXT if on else FAINT, "r")
        g.clip()
        # jogos (direita)
        gx, gw = sx + sw + 14, W - (sx + sw + 14) - 16
        g.text("Bold", 20, title, gx + 4, 58, TEXT)
        g.text("Regular", 12, f"{len(games)} jogos", gx + 6 + g.measure("Bold", 20, title)[0] + 10, 66, MUTED)
        ly, lh = 92, bot_y - 92
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
                g.rrect(gx, y, gw, rh - 2, 10, a1, a2)
            name = game["name"]
            while g.measure("Regular", 14, name)[0] > gw - 110 and len(name) > 6:
                name = name[:-2]
            if name != game["name"]:
                name = name.rstrip() + "…"
            g.text("SemiBold" if on else "Regular", 14, name, gx + 12, y + 6, ON_TEXT if on else TEXT)
            tag = s["full"] if title in ("Favoritos", "Recentes") else ("★" if game.get("fav") else "")
            if tag:
                g.text("Medium", 10, tag[:14], gx + gw - 12, y + 9, ON_TEXT if on else FAINT, "r")
        g.clip()
        if len(games) > vis:
            th = lh
            bh = max(24, th * vis / len(games))
            by = ly + (th - bh) * min(1, lb["top"] / max(1, (len(games) - vis) * rh))
            g.rrect(W - 12, ly, 3, th, 2, ink(18))
            g.rrect(W - 12, by, 3, bh, 2, alpha(a1, 220))
        self.draw_footer([("A", "Ver o jogo", TEXT), ("LR", "Sistema", MUTED), ("L1 / R1", "Letra", MUTED),
                          ("START", "Opções", MUTED), ("SELECT", "Energia", MUTED)])

    def power_menu(self):
        rows = [{"name": "Abrir o EmulationStation", "icon": "device-tv", "do": "es"},
                {"name": "Reiniciar o console", "icon": "refresh", "do": "reboot"},
                {"name": "Desligar o console", "icon": "power", "do": "poweroff"}]

        def go(r):
            self.picker = None
            if r["do"] == "es":
                self.quit()           # no sistema (tela inicial), sair do Omni36OS abre o ES
            elif not FAKE:
                omni.power({"what": r["do"]})
        self.show_list("Energia", "power", rows, go, "Escolher")

    # --- jogos ---

    def pick(self, what):
        idx = self.games()
        if FAKE:
            pairs = [(s, g) for s in idx for g in s["games"]]
            return {"fav": [p for p in pairs if p[1].get("fav")], "recent": [p for p in pairs if p[1].get("last")],
                    "most": [p for p in pairs if p[1].get("time")]}[what]
        return {"fav": omni_games.favorites, "recent": omni_games.recent, "most": omni_games.most_played}[what](idx)

    def open_systems(self, start=None):
        idx = [s for s in self.games() if s["games"]]
        rows = [{"name": s["full"], "right": (f"{len(s['games'])} jogos", MUTED), "sys": s} for s in idx]
        if not self.show_list("Jogos por sistema", "device-gamepad-2", rows,
                              lambda r: self.open_games(r["sys"]["full"], [(r["sys"], g) for g in r["sys"]["games"]],
                                                        back=lambda k=rows.index(r): self.open_systems(k)),
                              "Ver os jogos", start):
            self.toast = ("Nenhum jogo encontrado nas pastas do ES", "aviso", self.t + 3)

    def open_games(self, title, pairs, back=None, start=None):
        mixed = len({s["name"] for s, _g in pairs}) > 1
        rows = []
        for s, g in pairs:
            right = None
            if mixed:
                right = (s["full"], MUTED)
            elif g.get("fav"):
                right = ("Favorito", LEVEL["aviso"])
            rows.append({"name": g["name"], "right": right, "pair": (s, g)})
        reopen = lambda k: self.open_games(title, pairs, back, k)
        if not self.show_list(title, "device-gamepad-2", rows,
                              lambda r: self.open_sheet(*r["pair"], back=lambda k=rows.index(r): reopen(k)),
                              "Ver o jogo", start):
            self.toast = ("Nada aqui ainda", "info", self.t + 3)
            return
        self.picker["letters"] = not mixed and title not in ("Recentes", "Mais jogados")
        self.picker["on_back"] = back

    def open_dups(self):
        idx = self.games()
        dups = [] if FAKE else omni_games.duplicates(idx)
        rows = []
        for s, gs in dups:
            rows.append({"head": f"{s['full']} · {gs[0]['name']}"})
            rows += [{"name": os.path.basename(g["path"]), "pair": (s, g),
                      "right": (omni_games.human_size(g["size"]), MUTED)} for g in gs]
        if not self.show_list("Jogos repetidos", "alert-triangle", rows,
                              lambda r: self.open_sheet(*r["pair"], back=self.open_dups), "Ver o jogo"):
            self.toast = ("Nenhum jogo repetido", "ok", self.t + 3)

    def reindex_games(self):
        self.games_reindex = True
        self.worker(lambda: self._jogos(), lambda res: (self.set_result("jogos", res), self.reload_findings(),
                                                       setattr(self, "toast", ("Lista atualizada", "ok",
                                                                               self.t + 3))),
                    busy="Lendo as pastas de jogos...")

    def open_sheet(self, s, g, back=None):
        self.picker = None
        self.sheet = {"s": s, "g": g, "sel": 0, "back": back}

    def sheet_input(self, cmd):
        sh = self.sheet
        if cmd in ("left", "right"):
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
        self.running = False          # o launch.sh abre o jogo e reabre o Omni36OS no card Jogos

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
            facts.append("Favorito no ES")
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
            bx = mx + 22 + k * (bw + 12)
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
            rows.append({"head": g["label"], "tag": "O ES MOSTRA", "tagc": LEVEL["ok"]})
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
            self.running = False      # o launch.sh roda o teste e reabre o Omni36OS
        else:
            self.toast = (res, "aviso", self.t + 3.5)

    def show_test_result(self):
        r = None if FAKE else omni.last_test()
        if not r:
            return
        if r["resultado"] == "ok":
            text = f"{r['nome']} abriu e ficou rodando 15 segundos. Funcionou!"
            icon = "check"
        else:
            rel = r["relatorio"].split("/omni36os/", 1)[-1] if r["relatorio"] else ""
            text = (f"{r['nome']} fechou sozinho após {r['segundos']} s.\n"
                    f"O relatório ficou em omni36os/{rel}" if rel else f"{r['nome']} fechou sozinho.")
            icon = "alert-triangle"
        self.modal = {"title": "Teste de port", "text": text, "icon": icon, "buttons": ["OK"], "sel": 0}

    # --- modo de exibição (port ou sistema no ES) ---

    def ask_mode(self, first=False):
        if not first and self.busy_game():
            return
        cur = None if FAKE else omni.get_mode()
        text = ("Onde o Omni36OS deve aparecer no console?\n" if first else "") + \
            ("Lista de Ports: junto com os outros ports.\n"
             "Sistema: uma entrada própria no menu principal do console.\n"
             "Trocar reinicia o menu do console quando o Omni36OS fechar. Dá para mudar depois em Ajuda.")
        self.modal = {"title": "Como mostrar o Omni36OS", "text": text, "icon": "help-circle",
                      "buttons": ["Lista de Ports", "Sistema no console"], "sel": 1 if cur == "sistema" else 0,
                      "fns": [lambda: self.choose_mode("port", first), lambda: self.choose_mode("sistema", first)]}

    def choose_mode(self, mode, first):
        if FAKE:
            return
        cur = omni.get_mode() or "port"
        if mode == cur:          # nada muda no ES; só guarda a escolha
            omni.remember_mode({"mode": mode})
            if not first:
                self.toast = ("O Omni36OS já está assim", "ok", self.t + 3)
            return
        res = D.run("set_mode", {"mode": mode})
        self.modal = {"title": "Pronto", "icon": "check", "buttons": ["Fechar o Omni36OS"], "sel": 0,
                      "text": res + ".\nO menu do console reinicia quando o Omni36OS fechar.", "fns": [self.quit]}

    def quit(self):
        self.running = False

    def ask_restore_es(self):
        self.modal = {"title": "Restaurar o ES", "icon": "rotate", "sel": 0,
                      "buttons": ["Só reiniciar", "Desfazer o Omni36OS", "Cancelar"],
                      "text": "Só reiniciar: o menu do console recarrega quando o Omni36OS fechar (ES travado ou "
                              "lista desatualizada).\nDesfazer o Omni36OS: tira o sistema próprio, o ícone e o logo "
                              "que o Omni36OS pôs no ES; ele volta para a lista de Ports.",
                      "fns": [lambda: self.restore_es("restart_es"), lambda: self.restore_es("restore_es"),
                              lambda: None]}

    def restore_es(self, tool):
        if FAKE:
            return
        res = D.run(tool)
        if not res.startswith("Não"):
            self.modal = {"title": "Pronto", "icon": "check", "buttons": ["Fechar o Omni36OS", "Depois"], "sel": 0,
                          "text": res + ".", "fns": [self.quit, lambda: None]}
        else:
            self.toast = (res, "problema", self.t + 4)

    # --- backup ---

    def backup_menu(self, module):
        name = omni_backup.MODULES[module][0]
        where = omni_backup.backup_dir()
        self.modal = {"title": f"Backup · {name}", "icon": "device-floppy", "buttons": ["Exportar", "Importar"],
                      "sel": 0, "text": f"Exportar salva as configurações de {name} em:\n{where}\n"
                                        "Importar abre as pastas para escolher o arquivo.",
                      "fns": [lambda: self.backup_export(module), lambda: self.backup_browse(module, where)]}

    def backup_export(self, module):
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
        self.worker(lambda: omni_backup.export(module), done, busy="Exportando...")

    def backup_browse(self, module, path):
        path, entries = omni_backup.browse(path)
        rows = [{"head": path}]
        for e in entries:
            if e["dir"]:
                rows.append({"name": e["name"], "path": e["path"], "dir": True,
                             "icon": "arrow-back-up" if e["name"] == ".." else "folder"})
            else:
                m = omni_backup.manifest(e["path"]) or {}
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
                self.ask(f"Importar {row['name']}?\nAs configurações atuais de {omni_backup.MODULES[module][0]} "
                         "são salvas antes, como \"antes-de-importar\".",
                         lambda: self.backup_import(module, row["path"]))
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
            if module == "es" and "restaurado" in text:
                omni.restart_es_on_exit()
                text += ".\nO ES reinicia quando o Omni36OS fechar, para ler as configurações."
            elif module == "retroarch" and "restaurado" in text:
                text += ".\nVale a partir do próximo jogo aberto no RetroArch."
            self.modal = {"title": "Importação", "icon": "device-floppy", "buttons": ["OK"], "sel": 0,
                          "text": text}
            self.reload_findings()
        self.worker(lambda: omni_backup.import_(module, path), done, busy="Importando...")

    def read(self, title, icon, text):
        self.reader = {"title": title, "icon": icon, "text": text, "scroll": 0.0, "top": 0}

    def ask(self, text, fn, danger=False):
        self.modal = {"title": "Confirmar", "text": text, "icon": "alert-triangle" if danger else "info-circle",
                      "buttons": ["Sim, fazer", "Cancelar"], "sel": 1 if danger else 0, "fn": fn}

    # --- entrada ---

    def handle(self, cmd):
        self.last_input = time.monotonic()
        if self.busy or self.loading:
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
        if cmd == "select":
            self.power_menu()
            return
        if self.page is None and cmd in ("start", "back"):
            self.view = "lib"             # do menu de opções de volta para os jogos
            return
        if cmd == "start":
            self.page, self.view = None, "lib"
            return
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
        elif isinstance(it, Slider) and cmd in ("left", "right"):
            it.value = max(it.lo, min(100, it.value + (it.step if cmd == "right" else -it.step)))
            D.set(it.key, it.value)
        elif isinstance(it, Choice) and cmd in ("left", "right", "ok"):
            it.index = (it.index + (-1 if cmd == "left" else 1)) % len(it.options)
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
            if it.key in ("hub", "atalho") and isinstance(res, str):
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
                self.button(ev[12], typ == 0x651, now)
            elif typ == 0x650:          # SDL_CONTROLLERAXISMOTION
                axis = ev[12]
                val = int.from_bytes(bytes(ev[16:18]), "little", signed=True)
                if axis in (0, 1):
                    neg, pos = ("left", "right") if axis == 0 else ("up", "down")
                    for d, on in ((neg, val < -20000), (pos, val > 20000)):
                        self.direction(d, on, now)
            elif typ in (0x300, 0x301):  # teclado (para testar no PC)
                sym = int.from_bytes(bytes(ev[20:24]), "little")
                down, rep = typ == 0x300, ev[13]
                keys = {0x4000004F: "right", 0x40000050: "left", 0x40000051: "down", 0x40000052: "up"}
                if sym in keys:
                    if not rep:
                        self.direction(keys[sym], down, now)
                elif down and not rep:
                    self.handle({13: "ok", 27: "back", 8: "back",
                                 0x4000004B: "l1", 0x4000004E: "r1"}.get(sym, ""))   # PageUp/PageDown
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
                if {4, 6} <= self.combo:
                    self.running = False      # SELECT+START: fecha (no sistema, abre o ES)
            else:
                if not getattr(self, "combo_used", False) and self.combo == {b}:
                    self.handle("start" if b == 6 else "select")
                self.combo.discard(b)
                if not self.combo:
                    self.combo_used = False
            return
        if not down:
            return
        ok_b, back_b = (1, 0) if self.swap else (0, 1)
        if b in (9, 10):
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
        g.text("Regular", 11, "assistente do R36S", 70 + g.measure("Bold", 20, "Omni36OS")[0], 26, MUTED)
        # pílula de estado
        hora = time.strftime("%H:%M")
        bat = f"{s['bat']}%"
        temp = f"{s['temp']}°"
        w = 46 + g.measure("SemiBold", 13, bat)[0] + 36 + g.measure("SemiBold", 13, temp)[0] + 22 + \
            g.measure("SemiBold", 13, hora)[0] + 30
        x = W - 22 - w
        g.rrect(x, 16, w, 34, 17, GLASS_HI)
        cx = x + 14
        g.icon("wifi" if s["wifi"] else "wifi-off", cx, 24, 18, TEXT if s["wifi"] else FAINT)
        cx += 26
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
            "bateria": f"{s['bat']}%" + (" · carregando" if s["carregando"] else ""),
            "som": "Volume e saída",
            "tela": "Brilho e modelo",
            "desempenho": GOV_NAMES.get(s["gov"], s["gov"]) + f" · {s['temp']}°C",
            "pendrive": "Cabo no PC",
            "cartoes": "Info e velocidade",
            "retroarch": "Restaurar padrão",
            "ferramentas": f"{self.tool_count} do dArkOSen" if getattr(self, "tool_count", 0) else "Do dArkOSen",
            "jogos": f"{self.game_count} jogos" if getattr(self, "game_count", 0) else "Biblioteca",
            "ajuda": f"Manual · versão {omni_version()}",
            "testar": f"{self.port_count} ports instalados" if getattr(self, "port_count", 0) else "Abre e fecha em 15 s",
        }[cid]

    def _home_summary(self):
        hc = self.home_check
        if not hc:
            return "Analisando..."
        n = sum(1 for l, _ in hc["achados"] if l in ("aviso", "problema"))
        return "Tudo certo" if n == 0 else f"{n} ponto{'s' if n > 1 else ''} de atenção"

    def draw_home(self, dt, fade):
        if self.view == "lib":
            return self.draw_library(dt, fade)
        g = self.g
        hour = time.localtime().tm_hour
        hello = "Bom dia!" if 5 <= hour < 12 else "Boa tarde!" if hour < 18 else "Boa noite!"
        g.text("Bold", 26, hello, 22, 66, alpha(TEXT, 255 * fade))
        hc = self.home_check
        if hc:
            lvl = hc["nivel"]
            n = len(self.alerts)
            if n == 0:
                lvl, msg = "ok", "Seu R36S está em ótima forma."
            else:
                lvl = "problema" if any(l == "problema" for l, _ in self.alerts.values()) else "aviso"
                msg = (f"{n} cartão com alerta: veja o ponto nele." if n == 1 else
                       f"{n} cartões com alertas: veja os pontos neles.")
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
            g.text("SemiBold", 14, title, x + 72, y + ch / 2 - 23 + lift, alpha(ON_TEXT if on else TEXT, 255 * fade))
            if cid in self.alerts:
                lvl, n = self.alerts[cid]
                bc = LEVEL[lvl]
                px_, py_ = x + cw - 18, y + 15 + lift
                ring = 0.5 + 0.5 * math.sin(self.t * 4 + i)
                g.sprite(("ring", lvl), 26, 26, 1, lambda ox, oy, bc=bc: g.circle(ox + 13, oy + 13, 13, alpha(bc, 90)),
                         px_ - 13, py_ - 13, 255 * ring * fade)
                g.circle(px_, py_, 10, alpha(bc, 255 * fade))
                g.text("Bold", 11, str(n), px_, py_ + 0.5, alpha(hexc("10142a"), 255 * fade), "c", "m")
            g.text("Regular", 11, self.card_subtitle(cid), x + 72, y + ch / 2 + 1 + lift,
                   alpha(ON_TEXT if on else MUTED, (230 if on else 255) * fade))
        self.draw_footer([("A", "Abrir", TEXT), ("B", "Voltar aos jogos", MUTED), ("SELECT", "Energia", MUTED)])

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

        # diagnóstico (esquerda)
        px, py, pw, ph = 22 + off, 126, 330, 300
        g.rrect(px, py, pw, ph, 20, alpha(GLASS, 14 * fade))
        g.stroke(px, py, pw, ph, 20, ink(16 * fade))
        g.text("SemiBold", 11, "SOBRE" if cid == "ajuda" else "DIAGNÓSTICO", px + 18, py + 14, alpha(FAINT, a))
        g.clip(px, py, pw, ph)
        if not f:
            for k in range(3):
                yy = py + 44 + k * 52
                sh = 0.5 + 0.5 * math.sin(self.t * 4 - k)
                g.rrect(px + 18, yy, pw - 36, 38, 12, ink((10 + 12 * sh) * fade))
        else:
            # Altura de cada item; se não couberem todos, L1/R1 rolam um item por vez.
            top, bottom = py + 40, py + ph - 12
            blocks = []
            for lvl, txt in f["achados"]:
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
                g.text("Medium", 11, f"L1: {self.find_top} acima", px + pw - 18, py + 14, alpha(FAINT, a), "r")
            if below:
                g.text("Medium", 12, f"R1: mais {below} item(ns)", px + 18, py + ph - 24, alpha(FAINT, a))
        g.clip()

        # controles (direita)
        cx, cy, cw = 366 + off * 1.5, 126, 252
        g.text("SemiBold", 11, "AÇÕES", cx + 4, cy + 2, alpha(FAINT, a))
        # Altura de cada item: ações com nome longo quebram em linhas (ao lado
        # da etiqueta SUGERIDO, se houver) e o botão cresce para caber tudo.
        gap, tag = 10, "SUGERIDO"
        tw = g.measure("Bold", 9, tag)[0] + 14
        layout, y = [], cy + 22
        for it in self.items:
            lines = None
            ih = 50
            if isinstance(it, Action):
                lines = g.wrap("SemiBold", 14, it.label, cw - 46 - 14)
                extra = 20 if getattr(it, "suggested", False) else 0   # selo SUGERIDO em cima
                ih = max(50, 16 + 19 * len(lines) + extra)
            layout.append((y, ih, lines))
            y += ih + gap
        # muitas ações (Ajuda): a coluna rola para o item escolhido caber acima do rodapé
        top, bottom = cy + 18, H - 52
        sy, sh = layout[self.item_sel][:2] if layout else (cy + 22, 50)
        want = max(0, sy + sh - bottom) if sy - (cy + 22) > 0 else 0
        self.act_off = approach(getattr(self, "act_off", 0), want, dt, 18)
        layout = [(y - self.act_off, ih, lines) for y, ih, lines in layout]
        sel_y, sel_h = layout[self.item_sel][:2] if layout else (cy + 22, 50)
        g.clip(cx - 20, top, cw + 40, bottom - top + 4)
        self.item_y = approach(self.item_y or sel_y, sel_y, dt, 18)
        self.item_h = approach(getattr(self, "item_h", 0) or sel_h, sel_h, dt, 18)
        a1, a2 = self.accent
        ih_ = round(self.item_h)
        g.sprite(("it", a1, a2, ih_), cw, ih_, 16, lambda ox, oy: (
                 g.glow(ox, oy, cw, ih_, 16, alpha(a1, 80), 16),
                 g.rrect(ox, oy, cw, ih_, 16, alpha(a1, 235), alpha(a2, 235))),
                 cx, self.item_y, 255 * fade)
        for k, it in enumerate(self.items):
            y, ih, lines = layout[k]
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
        if isinstance(it, (Slider, Choice)):
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
        g.text("Bold", 24, "Omni36OS", cx, cy + 82, TEXT, "c", "m")
        bw, by = 300, cy + 124
        g.rrect(cx - bw / 2, by, bw, 8, 4, ink(30))
        g.rrect(cx - bw / 2, by, max(8, bw * self.load_shown), 8, 4, a1, a2)
        g.text("Regular", 13, self.load_label, cx, by + 28, MUTED, "c", "m")
        if self.results and not self.warm and self.load_shown > 0.98:
            self.loading = False
            if RESUME == "testar":
                self.sel = next(i for i, c in enumerate(CARDS) if c[0] == "testar")
                self.open_page("testar")
                self.show_test_result()
            elif RESUME == "biblioteca":
                self.view = "lib"
            elif RESUME in [c[0] for c in CARDS]:    # voltou de uma ferramenta do dArkOSen
                self.sel = next(i for i, c in enumerate(CARDS) if c[0] == RESUME)
                self.open_page(RESUME)
            elif RESUME in SUBPAGES:                 # ferramenta aberta de uma subpágina (ex.: RetroArch)
                self.sel = next(i for i, c in enumerate(CARDS) if c[0] == PARENT[RESUME])
                self.open_page(RESUME)
            elif not FAKE and omni.get_mode() is None:   # primeira execução
                self.ask_mode(first=True)

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
                elif cmd == "quit":
                    self.running = False
                else:
                    self.handle(cmd)
            self.frame(dt)
            self.g.present()
            if self.loading:
                self.prewarm()
            # Ritmo: 30 quadros/s em uso e 10 parado. A 60 quadros/s sem parar a
            # Omni36OS ocupava 70% de um núcleo e deixava o aparelho perto de 80 °C.
            moving = (self.loading or self.busy or self.toast or 0.01 < self.page_anim < 0.99
                      or now - self.last_input < IDLE_AFTER)
            spare = 1 / (FPS_ACTIVE if moving else FPS_IDLE) - (time.monotonic() - now)
            if spare > 0:
                time.sleep(spare)
        gfx.SDL_Quit()


if __name__ == "__main__":
    App().run()
