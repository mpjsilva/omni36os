"""Biblioteca de jogos: o que o ES mostra, lido do es_systems.cfg e dos gamelist.xml.

Só lê: quem grava os gamelists é o ES. O índice fica em cache
(~/.config/omni36os/jogos.json) e cada sistema só é relido quando a data da
pasta ou do gamelist muda, porque varrer milhares de ROMs no cartão é lento.
"""
import hashlib
import json
import os
import re
import shlex
import time
import xml.etree.ElementTree as ET

import omni

ES_SYSTEMS = omni.ES_SYSTEMS
ES_SETTINGS = f"{omni.HOME}/.emulationstation/es_settings.cfg"
CACHE = f"{omni.HOME}/.config/omni36os/jogos.json"
CACHE_VER = 1
# sistemas que não são jogos (ou têm card próprio)
SKIP = {"ports", "omni36os", "sab", "tools", "options", "retropie", "settings", "kodi", "imageviewer"}
# pastas e arquivos que moram nas pastas de jogos e não são jogos
NOT_GAMES = {"gamelist.xml", "gamelist.xml.old", "neogeo.zip", "systeminfo.txt", "readme.txt", "_info.txt"}
MEDIA_DIRS = {"images", "videos", "media", "manuals", "snap", "snaps", "boxart", "box2d", "wheel",
              "marquees", "screenshots", "titles", "thumbnails", "downloaded_images", "downloaded_videos"}
COVER_KEYS = ("thumbnail", "image", "marquee")


def _xml(path):
    try:
        return ET.parse(path).getroot()
    except (OSError, ET.ParseError):
        return None


def settings():
    """Escolhas do ES por sistema: <sistema>.emulator / .core / .governor."""
    text = omni.read_text(ES_SETTINGS, "")
    return dict(re.findall(r'<string name="([^"]+)" value="([^"]*)"', text))


def systems():
    root = _xml(ES_SYSTEMS)
    out = []
    if root is None:
        return out
    seen = set()
    for s in root.findall("system"):
        name = (s.findtext("name") or "").strip()
        path = (s.findtext("path") or "").strip().rstrip("/")
        if not name or not path or name.lower() in SKIP or path.startswith("/opt"):
            continue
        if path in seen:        # dois sistemas na mesma pasta: conta uma vez
            continue
        seen.add(path)
        emus = []
        for e in s.findall("emulators/emulator"):
            cores = [c.text.strip() for c in e.findall("cores/core") if c.text]
            default = next((c.text.strip() for c in e.findall("cores/core") if c.get("default") == "true"), None)
            emus.append({"name": e.get("name"), "cores": cores, "default": default})
        out.append({"name": name, "full": (s.findtext("fullname") or name).strip(), "path": path,
                    "ext": sorted({x.lower() for x in (s.findtext("extension") or "").split()}),
                    "command": (s.findtext("command") or "").strip(), "emulators": emus})
    return out


def _gamelist(sysd):
    for p in (os.path.join(sysd["path"], "gamelist.xml"),
              f"{omni.HOME}/.emulationstation/gamelists/{sysd['name']}/gamelist.xml"):
        if os.path.isfile(p):
            return p
    return None


def _abs(base, p):
    if not p:
        return ""
    p = p.strip()
    if p.startswith("./"):
        p = os.path.join(base, p[2:])
    elif p.startswith("~/"):
        p = os.path.join(omni.HOME, p[2:])
    return os.path.normpath(p)


def _scan(sysd):
    """Arquivos da pasta (até 2 níveis), separados em jogos e "não reconhecidos"."""
    games, unknown = {}, []
    exts = set(sysd["ext"])
    base = sysd["path"]

    def walk(d, depth):
        try:
            entries = list(os.scandir(d))
        except OSError:
            return
        for e in entries:
            n = e.name
            if n.startswith("."):
                continue
            if e.is_dir(follow_symlinks=False):
                if n.lower() in MEDIA_DIRS:
                    continue
                ext = os.path.splitext(n)[1].lower()
                if ext in exts:              # jogo em pasta (ex.: .ps3, .daphne)
                    games[e.path] = 0
                elif depth < 2:
                    walk(e.path, depth + 1)
                continue
            if n.lower() in NOT_GAMES:
                continue
            ext = os.path.splitext(n)[1].lower()
            try:
                size = e.stat().st_size
            except OSError:
                size = 0
            if ext in exts:
                games[e.path] = size
            elif ext not in (".png", ".jpg", ".jpeg", ".mp4", ".txt", ".xml", ".srm", ".sav", ".state",
                             ".cfg", ".bak", ".auto", ".opt", ".nfo", ".pdf", ".db", ".dat", ".ini") and not ext.startswith(".state"):
                unknown.append(os.path.relpath(e.path, base))

    walk(base, 0)
    # discos de um .m3u não contam como jogos separados
    m3u = [p for p in games if p.lower().endswith(".m3u")]
    for p in m3u:
        try:
            with open(p, errors="ignore") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        games.pop(os.path.normpath(os.path.join(os.path.dirname(p), line)), None)
        except OSError:
            pass
    # .cue: o .bin ao lado é parte dele
    for p in [p for p in games if p.lower().endswith(".cue")]:
        try:
            with open(p, errors="ignore") as f:
                for m in re.finditer(r'FILE\s+"([^"]+)"', f.read()):
                    b = os.path.normpath(os.path.join(os.path.dirname(p), m.group(1)))
                    games[p] += games.pop(b, 0)
        except OSError:
            pass
    return games, unknown


def _read_system(sysd):
    files, unknown = _scan(sysd)
    meta = {}
    gl = _gamelist(sysd)
    root = _xml(gl) if gl else None
    if root is not None:
        for g in root.findall("game"):
            p = _abs(sysd["path"], g.findtext("path"))
            if not p:
                continue
            m = {"name": (g.findtext("name") or "").strip()}
            for k in ("desc", "playcount", "lastplayed", "gametime", "emulator", "core", "governor"):
                v = g.findtext(k)
                if v:
                    m[k] = v.strip()
            for k in COVER_KEYS:
                v = _abs(sysd["path"], g.findtext(k))
                if v:
                    m["cover"] = v
                    break
            if (g.findtext("favorite") or "") == "true":
                m["fav"] = 1
            if (g.findtext("hidden") or "") == "true":
                m["hidden"] = 1
            meta[p] = m
    games = []
    for p, size in sorted(files.items()):
        m = meta.get(p, {})
        if m.get("hidden"):
            continue
        name = m.get("name") or os.path.splitext(os.path.basename(p))[0]
        g = {"path": p, "name": name, "size": size}
        for k in ("desc", "emulator", "core", "governor", "cover", "fav"):
            if k in m:
                g[k] = m[k]
        for src, dst in (("playcount", "plays"), ("gametime", "time")):
            v = m.get(src, "0")
            if v.isdigit() and int(v):
                g[dst] = int(v)
        if m.get("lastplayed"):
            g["last"] = m["lastplayed"]
        games.append(g)
    return {"name": sysd["name"], "full": sysd["full"], "path": sysd["path"], "games": games,
            "unknown": unknown[:200], "n_unknown": len(unknown)}


def _signature(sysd):
    sig = []
    for p in (sysd["path"], _gamelist(sysd)):
        try:
            sig.append(os.stat(p).st_mtime) if p else sig.append(0)
        except OSError:
            sig.append(0)
    return sig


def index(force=False):
    """Lista de sistemas com jogos. Usa o cache quando nada mudou."""
    try:
        with open(CACHE) as f:
            cache = json.load(f)
        if cache.get("ver") != CACHE_VER:
            cache = {}
    except (OSError, ValueError):
        cache = {}
    old = cache.get("systems", {})
    out, new, changed = [], {}, force or not old
    for s in systems():
        if not os.path.isdir(s["path"]):
            continue
        sig = _signature(s)
        hit = old.get(s["path"])
        if not force and hit and hit.get("sig") == sig:
            data = hit["data"]
        else:
            data, changed = _read_system(s), True
        new[s["path"]] = {"sig": sig, "data": data}
        if data["games"] or data["n_unknown"]:
            out.append(data)
    if changed or set(new) != set(old):
        try:
            os.makedirs(os.path.dirname(CACHE), exist_ok=True)
            with open(CACHE + ".tmp", "w") as f:
                json.dump({"ver": CACHE_VER, "at": time.time(), "systems": new}, f)
            os.replace(CACHE + ".tmp", CACHE)
        except OSError:
            pass
    out.sort(key=lambda d: d["full"].lower())
    return out


def all_games(idx):
    for s in idx:
        for g in s["games"]:
            yield s, g


def summary(idx):
    games = [g for _s, g in all_games(idx)]
    last = max(((g["last"], s, g) for s, g in all_games(idx) if g.get("last")), default=None,
               key=lambda t: t[0])
    return {"jogos": len(games), "sistemas": sum(1 for s in idx if s["games"]),
            "bytes": sum(g["size"] for g in games), "favoritos": sum(1 for g in games if g.get("fav")),
            "ultimo": (last[2]["name"], last[1]["full"]) if last else None}


def favorites(idx):
    return sorted(((s, g) for s, g in all_games(idx) if g.get("fav")), key=lambda t: t[1]["name"].lower())


def recent(idx, n=30):
    return sorted(((s, g) for s, g in all_games(idx) if g.get("last")), key=lambda t: t[1]["last"],
                  reverse=True)[:n]


def most_played(idx, n=30):
    return sorted(((s, g) for s, g in all_games(idx) if g.get("time") or g.get("plays")),
                  key=lambda t: (t[1].get("time", 0), t[1].get("plays", 0)), reverse=True)[:n]


def human_size(b):
    for unit, k in (("GB", 1e9), ("MB", 1e6), ("KB", 1e3)):
        if b >= k:
            return f"{b / k:.1f} {unit}".replace(".", ",")
    return f"{b} B"


def human_time(sec):
    h, m = divmod(int(sec) // 60, 60)
    return f"{h} h {m:02d} min" if h else f"{m} min"


def human_date(es):
    """20261026T132514 -> 26/10/2026."""
    m = re.match(r"(\d{4})(\d{2})(\d{2})", es or "")
    return f"{m.group(3)}/{m.group(2)}/{m.group(1)}" if m else ""


# --- diagnóstico ---

def _norm(name):
    name = re.sub(r"\([^)]*\)|\[[^\]]*\]", "", name.lower())
    return re.sub(r"[^a-z0-9]", "", name)


def duplicates(idx):
    """Mesmo jogo duas vezes no mesmo sistema (nome igual tirando região/versão)."""
    out = []
    for s in idx:
        groups = {}
        for g in s["games"]:
            groups.setdefault(_norm(g["name"]), []).append(g)
        for gs in groups.values():
            if len(gs) > 1:
                out.append((s, gs))
    return out


def no_cover(idx):
    return [(s, sum(1 for g in s["games"] if not g.get("cover") or not os.path.exists(g["cover"])))
            for s in idx if s["games"]]


# BIOS por sistema: (arquivo, md5s conhecidos, obrigatório). Grupo com "|" = basta um deles.
BIOS = {
    "psx": [("scph5501.bin|scph1001.bin|scph7001.bin|scph101.bin|psxonpsp660.bin",
             {"490f666e1afb15b7362b406ed1cea246", "924e392ed05558ffdb115408c263dccf",
              "1e68c231d0896b7eadcad1d7d8e76129", "6e3735ff4c7dc899ee98981385f6f3d0",
              "c53ca5908936d412331790f4426c6c33"}, True)],
    "segacd": [("bios_CD_U.bin|bios_CD_E.bin|bios_CD_J.bin",
                {"2efd74e3232ff260e371b99f84024f7f", "e66fa1dc5820d254611fdcdba0662372",
                 "278a9397d192149e84e820ac621a8edd"}, True)],
    "pcenginecd": [("syscard3.pce", {"38179df8f4ac870017db21ebcbf53114"}, True)],
    "turbografxcd": [("syscard3.pce", {"38179df8f4ac870017db21ebcbf53114"}, True)],
    "dreamcast": [("dc/dc_boot.bin", {"e10c53c2f8b90bab96ead2d368858623"}, True),
                  ("dc/dc_flash.bin", {"0a93f7940c455905bea6e392dfde92a4"}, False)],
    "saturn": [("saturn_bios.bin|sega_101.bin|mpr-17933.bin",
                {"af5828fdff51384f99b3c4926be27762", "85ec9ca47d8f6807718151cbcca8b964",
                 "3240872c70984b6cbfda1586cab68dbe"}, False)],
    "famicom disk system": [("disksys.rom", {"ca30b50f880eb660a320674ed365ef7a"}, True)],
    "fds": [("disksys.rom", {"ca30b50f880eb660a320674ed365ef7a"}, True)],
    "gba": [("gba_bios.bin", {"a860e8c0b6d573d191e4ec7db1b1e4f6"}, False)],
    "atari5200": [("5200.rom", {"281f20ea4320404ec820fb7ec0693b38"}, True)],
    "atarilynx": [("lynxboot.img", {"fcd403db69f54290b51035d82f835e7b"}, True)],
    "coleco": [("colecovision.rom", {"2c66f5911e5b42b8ebe113403548eee7"}, True)],
    "intellivision": [("exec.bin", set(), True), ("grom.bin", set(), True)],
    "odyssey2": [("o2rom.bin", {"562d5ebf9e030a40d6fabfc2f33139fd"}, True)],
    "channelf": [("sl31253.bin", set(), True), ("sl31254.bin", set(), True)],
    "neogeo": [("neogeo.zip", set(), True)],
    "naomi": [("naomi.zip", set(), True)],
    "Sega Atomiswave": [("awbios.zip", set(), True)],
    "3do": [("panafz10.bin|panafz1.bin|goldstar.bin", set(), True)],
    "n64dd": [("64DD_IPL.bin", set(), True)],
}


def bios_dir():
    m = re.search(r'^system_directory\s*=\s*"([^"]*)"', omni.read_text(f"{omni.HOME}/.config/retroarch/retroarch.cfg", ""),
                  re.M)
    d = m.group(1) if m else ""
    if d.startswith("~/"):
        d = os.path.join(omni.HOME, d[2:])
    return d if d and d != "default" else "/roms2/bios" if os.path.isdir("/roms2/bios") else "/roms/bios"


def _md5(path):
    h = hashlib.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def bios_check(idx):
    """Só para os sistemas que têm jogos: (sistema, faltando, versão desconhecida)."""
    bdir = bios_dir()
    out = []
    for s in idx:
        rules = BIOS.get(s["name"])
        if not rules or not s["games"]:
            continue
        missing, odd = [], []
        for files, md5s, required in rules:
            names = files.split("|")
            found = None
            for n in names:
                for d in (bdir, s["path"]):
                    p = os.path.join(d, n)
                    if os.path.isfile(p):
                        found = p
                        break
                if found:
                    break
            if not found:
                if required:
                    missing.append(names[0] if len(names) == 1 else " ou ".join(names[:2]))
            elif md5s and os.path.getsize(found) < 32 << 20 and _md5(found) not in md5s:
                odd.append(os.path.basename(found))
        if missing or odd:
            out.append((s, missing, odd))
    return out


# --- jogar pelo Omni36OS ---

def command(sysd_name, game_path):
    """Monta o comando que o ES usaria: mesmo emulador, core e governador."""
    sysd = next((s for s in systems() if s["name"] == sysd_name), None)
    if not sysd:
        return None
    st = settings()
    g = next((g for s in index() if s["name"] == sysd_name for g in s["games"] if g["path"] == game_path), {})
    emus = sysd["emulators"]
    emu = g.get("emulator") or st.get(f"{sysd_name}.emulator") or (emus[0]["name"] if emus else "")
    e = next((x for x in emus if x["name"] == emu), emus[0] if emus else None)
    core = g.get("core") or st.get(f"{sysd_name}.core") or (e and (e["default"] or (e["cores"][0] if e["cores"] else ""))) or ""
    gov = g.get("governor") or st.get(f"{sysd_name}.governor", "")
    cmd = sysd["command"]
    for k, v in (("%ROM%", shlex.quote(game_path)), ("%EMULATOR%", emu), ("%CORE%", core),
                 ("%GOVERNOR%", gov), ("%BASENAME%", shlex.quote(os.path.splitext(os.path.basename(game_path))[0])),
                 ("%ROM_RAW%", game_path)):
        cmd = cmd.replace(k, v)
    return cmd


def play(sys_name, path):
    """Pede ao launch.sh para abrir o jogo (o Omni36OS fecha e volta depois)."""
    omni.write_text(omni.HANDOFF, f"game\t{sys_name}\t{path}")
