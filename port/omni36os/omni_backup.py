"""Backup do Omni36OS: exporta e importa as configurações de cada módulo como .tar.gz.

Só configuração: saves, estados, cores, shaders, temas e bancos de dados ficam
de fora (são grandes e não são "opções"). Cada arquivo leva um manifesto
(omni36os-backup.txt) com o módulo, e a importação só extrai caminhos desse módulo.
"""
import fnmatch
import glob
import io
import os
import tarfile
import time

import omni

HOME = omni.HOME

# módulo -> (nome na tela, caminhos/globs incluídos, pedaços de caminho excluídos)
MODULES = {
    "omni36os": ("Omni36OS", [
        f"{HOME}/.config/omni36os", f"{omni.OMNI_DIR}/logs/resultados.txt", f"{omni.OMNI_DIR}/logs/avisos_limpos.txt",
        "/etc/cpu-settings.conf", "/etc/gpu-settings.conf", "/etc/dmc-settings.conf", "/etc/gamma-settings.conf",
    ], ["/.config/omni36os/modo"]),   # o modo depende do es_systems.cfg deste console: não se importa
}
MANIFEST = "omni36os-backup.txt"


# Onde um backup pode ser salvo: o jogador escolhe ao exportar. /roms2 e o pendrive só valem montados.
PLACES = (("/roms", "Cartão do sistema"), ("/roms2", "Cartão de jogos"), ("/mnt/usbdrive", "Pendrive"))
LAST_DIR = f"{HOME}/.config/omni36os/backup_onde"


def places():
    """[(nome, pasta dos backups, GB livres)] dos lugares disponíveis agora."""
    out = []
    for root, name in PLACES:
        if root == "/roms" and os.path.isdir(root) or os.path.ismount(root):
            st = os.statvfs(root)
            out.append((name, f"{root}/backup/omni36os", round(st.f_bavail * st.f_frsize / 1e9, 1)))
    return out


def backup_dir():
    """Último lugar escolhido, se ainda estiver disponível; senão o primeiro disponível."""
    dirs = [d for _n, d, _f in places()]
    last = omni.read_text(LAST_DIR, "").strip()
    return last if last in dirs else (dirs[0] if dirs else "/roms/backup/omni36os")


def _files(module):
    _name, paths, excl = MODULES[module]
    out = []
    for pat in paths:
        for p in sorted(glob.glob(pat)):
            if os.path.isdir(p):
                for dirpath, dirs, files in os.walk(p):
                    dirs[:] = [d for d in dirs if not any(x in f"{dirpath}/{d}" for x in excl)]
                    out += [os.path.join(dirpath, f) for f in files]
            elif os.path.isfile(p):
                out.append(p)
    return [f for f in out if not any(x in f for x in excl)]


def allowed(module, member):
    """O caminho (sem a / inicial) pertence ao módulo? Protege a importação."""
    path = "/" + member.lstrip("/")
    if ".." in path.split("/"):
        return False
    _name, paths, excl = MODULES[module]
    if any(x in path for x in excl):
        return False
    for pat in paths:
        if "*" in pat:   # glob só no nome do arquivo, na mesma pasta
            if os.path.dirname(path) == os.path.dirname(pat) and fnmatch.fnmatch(os.path.basename(path),
                                                                                  os.path.basename(pat)):
                return True
        elif path == pat or path.startswith(pat + "/"):
            return True
    return False


def export(module, tag="", dest=None):
    files = _files(module)
    if not files:
        return None, f"Nada para exportar em {MODULES[module][0]}."
    if dest:                                   # escolha do jogador: vira o padrão das próximas vezes
        omni.write_text(LAST_DIR, dest)
    dest = dest or backup_dir()
    os.makedirs(dest, exist_ok=True)
    name = f"{module}-{time.strftime('%Y%m%d-%H%M%S')}{tag}.tar.gz"
    path = os.path.join(dest, name)
    info = f"module={module}\nsab={read_version()}\ndate={time.strftime('%d/%m/%Y %H:%M')}\nfiles={len(files)}\n"
    with tarfile.open(path, "w:gz") as tar:
        data = info.encode()
        ti = tarfile.TarInfo(MANIFEST)
        ti.size, ti.mtime = len(data), time.time()
        tar.addfile(ti, io.BytesIO(data))
        for f in files:
            tar.add(f, arcname=f.lstrip("/"), recursive=False)
    os.sync()
    return path, f"{len(files)} arquivo(s)"


def read_version():
    return omni.read_text(os.path.join(omni.OMNI_DIR, "VERSION"), "?")


def manifest(path):
    try:
        with tarfile.open(path, "r:gz") as tar:
            f = tar.extractfile(MANIFEST)
            text = f.read().decode() if f else ""
    except (tarfile.TarError, OSError, KeyError):
        return None
    return dict(line.split("=", 1) for line in text.splitlines() if "=" in line)


def import_(module, path):
    m = manifest(path)
    if not m:
        return "Este arquivo não é um backup do Omni36OS."
    if m.get("module") != module:
        other = MODULES.get(m.get("module"), ("outro módulo",))[0]
        return f"Este backup é de {other}, não de {MODULES[module][0]}."
    # cópia do que está valendo agora, para poder voltar
    export(module, "-antes-de-importar")
    n = 0
    with tarfile.open(path, "r:gz") as tar:
        for mem in tar.getmembers():
            if mem.name == MANIFEST or not (mem.isfile() or mem.isdir()) or not allowed(module, mem.name):
                continue
            tar.extract(mem, "/", filter="fully_trusted")   # mantém dono e permissões
            n += mem.isfile()
    os.sync()
    return f"{n} arquivo(s) restaurado(s) de {os.path.basename(path)}"


def last_backups():
    """módulo -> (arquivo, data) do backup mais recente."""
    out = {}
    for module in MODULES:
        files = sorted((f for _n, d, _f in places() for f in glob.glob(os.path.join(d, f"{module}-*.tar.gz"))),
                       key=os.path.getmtime)
        files = [f for f in files if "-antes-de-importar" not in f] or files
        if files:
            out[module] = (os.path.basename(files[-1]),
                           time.strftime("%d/%m/%Y", time.localtime(os.path.getmtime(files[-1]))))
    return out


# --- navegação para escolher o arquivo a importar ---

BROWSE_ROOTS = ("/roms", "/roms2", "/mnt/usbdrive", HOME)


def browse(path):
    """Pastas e .tar.gz em `path`. Não sobe acima dos cartões e da pasta do usuário."""
    path = os.path.realpath(path)
    if not any(path == r or path.startswith(r + "/") for r in BROWSE_ROOTS):
        path = backup_dir() if os.path.isdir(backup_dir()) else BROWSE_ROOTS[0]
    entries = []
    try:
        names = sorted(os.listdir(path), key=str.lower)
    except OSError:
        names = []
    for n in names:
        if n.startswith("."):
            continue
        full = os.path.join(path, n)
        if os.path.isdir(full):
            entries.append({"name": n, "path": full, "dir": True})
        elif n.endswith(".tar.gz"):
            entries.append({"name": n, "path": full, "dir": False})
    entries.sort(key=lambda e: (not e["dir"], e["name"].lower()))
    up = os.path.dirname(path)
    if path not in BROWSE_ROOTS:
        entries.insert(0, {"name": "..", "path": up, "dir": True})
    else:   # nos topos, dá para pular entre os cartões
        entries = [{"name": r, "path": r, "dir": True} for r in BROWSE_ROOTS
                   if r != path and (r in ("/roms", HOME) and os.path.isdir(r) or os.path.ismount(r))] + entries
    return path, entries
