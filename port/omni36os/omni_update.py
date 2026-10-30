"""Atualização do Omni36OS pelo GitHub, com volta automática.

1. check(): procura a maior tag omni-vX.Y.Z do repositório, maior que a VERSION em uso.
2. install(): baixa o código dessa tag, monta em /opt/omni36os.new e confere tudo (sintaxe do
   Python e dos .sh, arquivos essenciais, VERSION igual à tag) antes de mexer no que funciona.
   Depois troca: a versão em uso vira /opt/omni36os.prev e a nova entra no lugar, numa troca de
   nome (o cartão nunca fica com metade de cada).
3. O /usr/local/bin/omni36os-start (fora desta pasta, para não ser trocado junto) conta as
   aberturas da versão nova; se ela não chegar ao menu em 3 tentativas, volta a anterior.
   confirm_ok() é chamado pelo Omni36OS quando o menu aparece e encerra a contagem.
"""
import io
import json
import os
import re
import shutil
import subprocess
import tarfile
import time
import urllib.request

REPO = "mpjsilva/omni36os"
TAG = re.compile(r"^omni-v(\d+)\.(\d+)\.(\d+)$")
OMNI = os.path.dirname(os.path.abspath(__file__))
NEW, PREV = OMNI + ".new", OMNI + ".prev"
STATE = "/var/lib/omni36os-update"
PENDING = f"{STATE}/pending"          # json: de, para, quando (a versão nova ainda não abriu o menu)
TRIES = f"{STATE}/tries"              # aberturas da versão nova (o omni36os-start soma)
ROLLED = f"{STATE}/rolled-back"       # texto do aviso: a nova não abriu e a anterior voltou
ESSENTIAL = ("omni_ui.py", "omni.py", "gfx.py", "launch-direct.sh", "VERSION")
KEEP = ("logs",)                      # o que é deste console e não vem do GitHub


def version_tuple(v):
    m = re.match(r"^(\d+)\.(\d+)\.(\d+)", (v or "").strip())
    return tuple(int(x) for x in m.groups()) if m else (0, 0, 0)


def current():
    try:
        with open(os.path.join(OMNI, "VERSION")) as f:
            return f.read().strip()
    except OSError:
        return "0.0.0"


def _get(url, timeout=20):
    req = urllib.request.Request(url, headers={"User-Agent": "Omni36OS", "Accept": "application/vnd.github+json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def latest():
    """(versão, tag) mais nova publicada, ou None."""
    tags = json.loads(_get(f"https://api.github.com/repos/{REPO}/tags?per_page=100"))
    best = None
    for t in tags:
        m = TAG.match(t.get("name", ""))
        if m:
            v = tuple(int(x) for x in m.groups())
            if best is None or v > best[0]:
                best = (v, t["name"])
    return (".".join(map(str, best[0])), best[1]) if best else None


def check():
    """{"atual", "nova" (ou None), "tag"}; levanta OSError sem internet."""
    cur = current()
    found = latest()
    if found and version_tuple(found[0]) > version_tuple(cur):
        return {"atual": cur, "nova": found[0], "tag": found[1]}
    return {"atual": cur, "nova": None, "tag": None}


def validate(path, version):
    """Lista de problemas da versão montada em `path` (vazia = pode instalar)."""
    bad = [f"falta {f}" for f in ESSENTIAL if not os.path.exists(os.path.join(path, f))]
    if bad:
        return bad
    with open(os.path.join(path, "VERSION")) as f:
        if f.read().strip() != version:
            bad.append("VERSION diferente da tag")
    for dirpath, _dirs, files in os.walk(path):
        for n in files:
            full = os.path.join(dirpath, n)
            if n.endswith(".py"):
                try:
                    with open(full, "rb") as f:
                        compile(f.read(), full, "exec")
                except (SyntaxError, ValueError) as e:
                    bad.append(f"{n}: linha {getattr(e, 'lineno', '?')}")
            elif n.endswith(".sh") and subprocess.run(["bash", "-n", full], capture_output=True).returncode:
                bad.append(f"{n}: erro de sintaxe")
    return bad


def _extract(data, dest):
    """Só a pasta port/omni36os do pacote, sem caminhos para fora (filter="data")."""
    shutil.rmtree(dest, ignore_errors=True)
    os.makedirs(dest)
    with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as tar:
        for m in tar.getmembers():
            parts = m.name.split("/", 1)
            if len(parts) < 2 or not parts[1].startswith("port/omni36os/"):
                continue
            m.name = parts[1][len("port/omni36os/"):]
            if m.name:
                tar.extract(m, dest, filter="data")


def install(tag, version):
    data = _get(f"https://codeload.github.com/{REPO}/tar.gz/refs/tags/{tag}", timeout=120)
    try:
        _extract(data, NEW)
        bad = validate(NEW, version)
    except (tarfile.TarError, OSError) as e:
        bad = [f"pacote ilegível: {e}"]
    if bad:
        shutil.rmtree(NEW, ignore_errors=True)
        return "Não instalei: a versão baixada tem problemas (" + "; ".join(bad[:3]) + ")."
    for k in KEEP:
        src = os.path.join(OMNI, k)
        if os.path.isdir(src):
            shutil.copytree(src, os.path.join(NEW, k), dirs_exist_ok=True)
    for dirpath, _dirs, files in os.walk(NEW):
        for n in files:
            if n.endswith(".sh"):
                os.chmod(os.path.join(dirpath, n), 0o755)
    os.makedirs(STATE, exist_ok=True)
    with open(PENDING, "w") as f:
        json.dump({"de": current(), "para": version, "quando": time.time()}, f)
    with open(TRIES, "w") as f:
        f.write("0")
    os.sync()
    shutil.rmtree(PREV, ignore_errors=True)
    os.rename(OMNI, PREV)
    os.rename(NEW, OMNI)
    os.sync()
    # reabre pelo omni36os-start (que conta as tentativas); este processo some junto
    subprocess.run(["systemd-run", "--no-block", "--collect", "--unit", f"omni36os-update-{int(time.time())}",
                    "bash", "-c", "sleep 2; systemctl restart omni36os-atalho omni36os-launcher"])
    return f"Omni36OS {version} instalado. Abrindo de novo..."


def confirm_ok():
    """O menu apareceu: a versão nova vale (para de contar e não volta mais)."""
    for f in (PENDING, TRIES):
        try:
            os.remove(f)
        except OSError:
            pass


def rolled_back_message():
    """Aviso de uma volta automática (uma vez só)."""
    try:
        with open(ROLLED) as f:
            msg = f.read().strip()
        os.remove(ROLLED)
        return msg
    except OSError:
        return ""


def can_go_back():
    return os.path.isfile(os.path.join(PREV, "VERSION"))


def go_back():
    """Volta à versão anterior a pedido (Geral > Voltar à versão anterior)."""
    if not can_go_back():
        return "Não há versão anterior guardada."
    with open(os.path.join(PREV, "VERSION")) as f:
        old = f.read().strip()
    tmp = OMNI + ".swap"
    shutil.rmtree(tmp, ignore_errors=True)
    os.rename(OMNI, tmp)
    os.rename(PREV, OMNI)
    os.rename(tmp, PREV)
    confirm_ok()
    os.sync()
    subprocess.run(["systemd-run", "--no-block", "--collect", "--unit", f"omni36os-update-{int(time.time())}",
                    "bash", "-c", "sleep 2; systemctl restart omni36os-atalho omni36os-launcher"])
    return f"Voltando ao Omni36OS {old}..."
