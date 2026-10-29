"""Ficha dos ports em 2 camadas, guardada no cartão (busca uma vez por jogo, com Wi-Fi).

1. PortMaster: catálogo oficial dos ports (ports.json do PortMaster-New). Acha o port pelo
   .sh instalado e traz título, descrição, gêneros, quem portou, o que precisa e a imagem.
2. Steam: a loja (a mesma base que o SteamDB mostra), sem chave. Descrição em pt-BR quando há.

Antes de tudo vale a pasta "info" do port (<pasta do port>/info/): info.json com os campos
da ficha (nome, descricao, estudio, lancamento, generos, porter, pronto, capa); sem JSON, a
primeira imagem (png/jpg) vira a capa e o primeiro .txt a descrição. Lida do cartão, sem internet, e manda
sobre as outras camadas.

Cada camada completa o que as de cima não trouxeram. Erro de rede não grava nada (tenta de
novo na próxima vez que o launcher abrir); jogo sem ficha em nenhuma grava cache vazio.
"""
import html
import json
import os
import re
import threading
import time
import urllib.parse
import urllib.request

CACHE = os.environ.get("OMNI_META_DIR") or "/home/ark/.config/omni36os/steam"
STEAM = "https://store.steampowered.com/api"
PM_LIST = "https://github.com/PortsMaster/PortMaster-New/releases/latest/download/ports.json"
PM_RAW = "https://raw.githubusercontent.com/PortsMaster/PortMaster-New/main/ports"
PM_INDEX = os.path.join(CACHE, "_portmaster.json")   # versão enxuta do catálogo
UA = {"User-Agent": "Omni36OS"}
_busy = set()
_lock = threading.Lock()
_pm_lock = threading.Lock()
_pm = None


def _slug(name):
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") or "jogo"


def _norm(name):
    """Nome do port → termo de busca: tira extensão, parênteses e versões."""
    name = re.sub(r"\.(sh|zip|port)$", "", name, flags=re.I)
    name = re.sub(r"[\(\[].*?[\)\]]", " ", name)
    name = re.sub(r"\b(v?\d+(\.\d+)+|port|r36s)\b", " ", name, flags=re.I)
    return re.sub(r"[_\s]+", " ", name).strip()


def _key(name):
    return re.sub(r"[^a-z0-9]", "", name.lower())


def _get(url, data=None, headers=None):
    req = urllib.request.Request(url, data=data, headers={**UA, **(headers or {})})
    with urllib.request.urlopen(req, timeout=10) as r:
        return r.read()


def _clean(text):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", text or ""))).strip()


def paths(name):
    base = os.path.join(CACHE, _slug(name))
    return base + ".json", base + ".jpg"


def cached(name):
    """Ficha guardada (dict), {} se já se sabe que não há, ou None se ainda não buscou."""
    js, _ = paths(name)
    try:
        with open(js) as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


# --- 0. pasta "info" do port ---

IMG_EXT = (".png", ".jpg", ".jpeg")


SKIP_DIRS = {"images", "videos", "manuals", "portmaster", "autoinstall", "info"}


def port_dir(path):
    """Pasta do port, ao lado do .sh: a de mesmo nome (sem maiúsculas, espaços ou _); senão a
    que o .sh cita ("/halo"); senão a que começa igual ("daytona" para "Daytona USA.sh")."""
    base, sh = os.path.split(path or "")
    want = _key(os.path.splitext(sh)[0])
    if not want:
        return None
    try:
        dirs = [d for d in os.listdir(base) if d.lower() not in SKIP_DIRS and os.path.isdir(os.path.join(base, d))]
    except OSError:
        return None
    hit = next((d for d in dirs if _key(d) == want), None)
    if not hit:
        try:
            with open(path, errors="replace") as f:
                text = f.read(20000)
            hit = next((d for d in dirs if re.search(r"/" + re.escape(d) + r"(?=[\"'/\s]|$)", text, re.M)), None)
        except OSError:
            pass
    if not hit:
        hit = next((d for d in sorted(dirs, key=len, reverse=True)
                    if len(_key(d)) >= 4 and want.startswith(_key(d))), None)
    return os.path.join(base, hit) if hit else None


def es_image(path):
    """Imagem do gamelist do ES (ports/images/<nome>-image.png), se houver."""
    base, sh = os.path.split(path or "")
    stem = os.path.splitext(sh)[0]
    for suf in ("-image", "-thumb"):
        for ext in IMG_EXT:
            f = os.path.join(base, "images", stem + suf + ext)
            if os.path.isfile(f):
                return f
    return None


FIELDS = ("nome", "descricao", "estudio", "lancamento", "generos", "porter", "pronto")


def local(path):
    """Ficha da pasta info do port: info.json (campos de FIELDS + "capa"), o .txt como reserva
    da descrição e a primeira imagem como reserva da capa. JSON com erro é ignorado."""
    d = port_dir(path)
    info_dir = d and next((os.path.join(d, x) for x in sorted(os.listdir(d)) if x.lower() == "info"), None)
    if not info_dir or not os.path.isdir(info_dir):
        img = es_image(path)
        return {"capa": img} if img else {}
    files = sorted(os.listdir(info_dir))
    out = {}
    js = next((f for f in files if f.lower() == "info.json"), None) or \
        next((f for f in files if f.lower().endswith(".json")), None)
    if js:
        try:
            with open(os.path.join(info_dir, js), encoding="utf-8") as fh:
                data = json.load(fh)
            out = {k: data[k] for k in FIELDS if data.get(k) not in (None, "")}
            if isinstance(out.get("generos"), list):
                out["generos"] = ", ".join(out["generos"])
            cap = data.get("capa")
            if cap and os.path.isfile(os.path.join(info_dir, cap)):
                out["capa"] = os.path.join(info_dir, cap)
        except (OSError, ValueError, AttributeError):
            out = {}
    for f in files:
        full, low = os.path.join(info_dir, f), f.lower()
        if low.endswith(IMG_EXT) and "capa" not in out:
            out["capa"] = full
        elif low.endswith(".txt") and "descricao" not in out:
            try:
                with open(full, encoding="utf-8", errors="replace") as fh:
                    out["descricao"] = re.sub(r"\s+", " ", fh.read(4000)).strip()
            except OSError:
                pass
    if "capa" not in out and es_image(path):
        out["capa"] = es_image(path)
    return out


# --- 1. PortMaster ---

def _pm_index():
    """{chave do .sh ou do título: ficha}; o catálogo é baixado de novo a cada 7 dias."""
    global _pm
    with _pm_lock:
        if _pm is not None:
            return _pm
        try:
            fresh = time.time() - os.path.getmtime(PM_INDEX) < 7 * 86400
        except OSError:
            fresh = False
        if not fresh:
            ports = json.loads(_get(PM_LIST)).get("ports", {})
            idx = {}
            for zipname, p in ports.items():
                a, folder = p.get("attr", {}), zipname[:-4]
                shot = (a.get("image") or {}).get("screenshot")
                e = {"titulo": a.get("title", ""), "descricao": a.get("desc", ""),
                     "porter": ", ".join(a.get("porter") or []),
                     "generos": ", ".join(g.title() for g in a.get("genres") or []),
                     "pronto": bool(a.get("rtr")),
                     "img": f"{PM_RAW}/{folder}/{shot}" if shot else ""}
                for it in p.get("items") or []:
                    if it.lower().endswith(".sh"):
                        idx.setdefault(_key(it[:-3]), e)
                idx.setdefault(_key(e["titulo"]), e)
            os.makedirs(CACHE, exist_ok=True)
            with open(PM_INDEX, "w") as f:
                json.dump(idx, f, ensure_ascii=False)
        with open(PM_INDEX) as f:
            _pm = json.load(f)
        return _pm


def portmaster(name, path):
    idx = _pm_index()
    sh = os.path.splitext(os.path.basename(path or ""))[0]
    return idx.get(_key(sh)) or idx.get(_key(name)) or idx.get(_key(_norm(name)))


# --- 2. Steam ---

def steam(term):
    q = urllib.parse.urlencode({"term": term, "l": "brazilian", "cc": "BR"})
    found = json.loads(_get(f"{STEAM}/storesearch/?{q}")).get("items") or []
    app = next((i for i in found if _key(i.get("name", "")) == _key(term)), None)
    if not app:
        return None                   # só aceita nome igual: a busca da Steam devolve parecidos
    aid = app["id"]
    d = json.loads(_get(f"{STEAM}/appdetails?appids={aid}&l=brazilian&cc=BR"))[str(aid)]
    d = d.get("data", {}) if d.get("success") else {}
    return {"nome": d.get("name") or app.get("name"), "descricao": _clean(d.get("short_description")),
            "estudio": ", ".join(d.get("developers") or []),
            "generos": ", ".join(g["description"] for g in d.get("genres") or [])[:60],
            "lancamento": (d.get("release_date") or {}).get("date", ""),
            "img": d.get("header_image") or "", "steamdb": f"https://steamdb.info/app/{aid}/"}


def _pt(text):
    """Descrição parece português? (a Steam devolve inglês quando não há tradução)"""
    words = set(re.findall(r"[a-zà-ú]+", (text or "").lower()))
    return len(words & {"o", "a", "de", "que", "um", "uma", "do", "da", "em", "para", "com", "você"}) >= 3


def fetch(name, path=""):
    pm = portmaster(name, path)
    term = (pm or {}).get("titulo") or _norm(name)
    info, descs, imgs = {}, [], []
    for src, d in (("PortMaster", pm), ("Steam", steam(term))):
        if not d:
            continue
        info.setdefault("fontes", []).append(src)
        d = dict(d, nome=d.get("nome") or d.get("titulo"))
        for k in ("nome", "estudio", "lancamento", "generos", "porter", "steamdb"):
            if d.get(k) and not info.get(k):
                info[k] = d[k]
        if "pronto" in d:
            info["pronto"] = d["pronto"]
        if d.get("descricao"):
            descs.append(d["descricao"])
        if d.get("img"):
            imgs.append(d["img"])
    if descs:   # em português se alguma camada tiver; senão a do PortMaster (fala do port)
        info["descricao"] = next((t for t in descs if _pt(t)), descs[0])
    os.makedirs(CACHE, exist_ok=True)
    js, jpg = paths(name)
    for url in reversed(imgs):        # capa: Steam (larga), depois PortMaster
        try:
            with open(jpg, "wb") as f:
                f.write(_get(url))
            info["capa"] = jpg
            break
        except OSError:
            continue
    with open(js, "w") as f:
        json.dump(info, f, ensure_ascii=False)
    return info


def want(name, path="", done=None):
    """Pede a ficha em segundo plano (uma busca por jogo de cada vez)."""
    with _lock:
        if name in _busy:
            return
        _busy.add(name)

    def run():
        try:
            fetch(name, path)
        except Exception:
            pass                      # sem internet ou serviço fora: fica para a próxima
        finally:
            with _lock:
                _busy.discard(name)
            if done:
                done(name)
    threading.Thread(target=run, daemon=True).start()
