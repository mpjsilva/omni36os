"""Testar ports: causa provável de uma falha e correções conhecidas.

Lê o relatório que o port_test.sh grava (saída do port, logs da pasta e dmesg),
reconhece falhas comuns e, quando há conserto seguro, aplica e guarda como
desfazer. O launcher testa de novo; se o teste falhar outra vez, desfaz.
Regras novas: acrescente em RULES (a ordem é a prioridade).
"""
import json
import os
import re
import shutil

PENDING = os.path.expanduser("~ark/.config/omni36os/correcao_pendente.json")

# (id, regex no relatório, causa, dica, correção automática ou None)
RULES = [
    ("crlf", r"\r: command not found|bad interpreter: .*\^M|/bin/bash\^M|\$'\\r'",
     "O script foi salvo no Windows (fim de linha CRLF).",
     "Converter os scripts do port para o formato do Linux.", "crlf"),
    ("permissao", r"Permission denied",
     "Um arquivo do port está sem permissão para rodar (comum depois de copiar pelo PC).",
     "Dar permissão de execução aos arquivos do port.", "chmod"),
    ("memoria", r"Out of memory|oom-kill|Killed process|^Killed$|\bKilled\b",
     "Faltou memória: o sistema matou o port.",
     "Ligar a memória extra (zram) com 768 MB.", "zram"),
    ("runtime", r"libs/([\w.\-]+)\.squashfs|runtime[^\n]*(not found|missing|não)",
     "O port precisa de um runtime do PortMaster que não foi baixado.",
     "Abra Ferramentas › PortMaster (com internet) e instale o port de novo: ele baixa o runtime.", None),
    ("glibc", r"GLIBC_[\d.]+' not found",
     "O port foi feito para um sistema mais novo (glibc).",
     "Sem conserto aqui: procure outra versão do port.", None),
    ("biblioteca", r"error while loading shared libraries: ([\w.+\-]+)",
     "Falta uma biblioteca para o port.",
     "Reinstale o port pelo PortMaster; se continuar, ele não é compatível com este sistema.", None),
    ("symlink", r"(ln|symlink)[^\n]*Operation not permitted",
     "O cartão de jogos é exFAT e não aceita atalhos (links simbólicos).",
     "Instale o port pelo PortMaster, que já contorna isso.", None),
    ("dados", r"\.(wad|pak|pk3|win|iso|dat|bin|grp|zip)['\"]?[^\n]*(not found|No such file)|"
              r"(game ?data|gamedata|data files?)[^\n]*(not found|missing)",
     "Faltam os arquivos do jogo original.",
     "Copie os arquivos do jogo para a pasta do port (veja o README dele).", None),
    ("segfault", r"Segmentation fault|SIGSEGV",
     "O port travou (falha de memória do próprio programa).",
     "Teste com o processador em Máximo e sem overclock (Desempenho).", None),
]


def _report_text(path):
    try:
        with open(path, errors="replace") as f:
            return f.read()
    except OSError:
        return ""


def port_script(report):
    m = re.search(r"^Script:\s+(.+)$", _report_text(report), re.M)
    return m.group(1).strip() if m else ""


def port_dirs(script):
    """Pastas do port: GAMEDIR do script e as pastas com o nome dele."""
    base, name = os.path.dirname(script), os.path.basename(script)[:-3]
    out = [os.path.join(base, name), os.path.join(base, name.lower().replace(" ", "_"))]
    try:
        with open(script, errors="replace") as f:
            for m in re.finditer(r'GAMEDIR="?([^"\s]+)"?', f.read()):
                d = m.group(1).replace("/$directory/", "/roms/").replace("${directory}", "roms")
                out.append(d if d.startswith("/") else os.path.join(base, d))
    except OSError:
        pass
    seen = []
    for d in out:
        if os.path.isdir(d) and d not in seen:
            seen.append(d)
    return seen


def diagnose(report):
    """Causas prováveis, da mais forte para a mais fraca: [{id, causa, dica, fix, extra}]."""
    text = _report_text(report)
    out = []
    for rid, rx, causa, dica, fix in RULES:
        m = re.search(rx, text, re.M | re.I)
        if not m:
            continue
        extra = next((g for g in m.groups() if g and len(g) > 2), "") if m.groups() else ""
        out.append({"id": rid, "causa": causa, "dica": dica, "fix": fix, "extra": extra})
    return out


def note(report, items, line=""):
    """Acrescenta o diagnóstico ao relatório."""
    try:
        with open(report, "a") as f:
            f.write("\n--- Diagnóstico do Omni36OS ---\n")
            for d in items:
                f.write(f"Causa provável: {d['causa']}" + (f" ({d['extra']})" if d["extra"] else "") +
                        f"\nO que fazer: {d['dica']}\n")
            if line:
                f.write(line + "\n")
    except OSError:
        pass


# --- correções (cada uma devolve o desfazer) ---

def _files(dirs, script):
    out = [script]
    for d in dirs:
        for root, _, names in os.walk(d):
            out += [os.path.join(root, n) for n in names]
    return [f for f in out if os.path.isfile(f) and not os.path.islink(f)]


def _fix_chmod(script, dirs):
    changed = []
    for f in _files(dirs, script):
        try:
            with open(f, "rb") as h:
                head = h.read(4)
        except OSError:
            continue
        if head[:2] != b"#!" and head != b"\x7fELF":
            continue
        mode = os.stat(f).st_mode
        if not mode & 0o111:
            os.chmod(f, mode | 0o755)
            changed.append([f, mode])
    return {"chmod": changed}


def _fix_crlf(script, dirs):
    changed = []
    for f in _files(dirs, script):
        if not f.endswith((".sh", ".txt", ".cfg", ".ini")) and f != script:
            continue
        try:
            with open(f, "rb") as h:
                data = h.read()
        except OSError:
            continue
        if b"\r\n" not in data or b"\0" in data:
            continue
        bak = f + ".omni36os-crlf"
        shutil.copy2(f, bak)
        with open(f, "wb") as h:
            h.write(data.replace(b"\r\n", b"\n"))
        changed.append([f, bak])
    return {"crlf": changed}


def _fix_zram(script, dirs):
    import omni_sistema
    if omni_sistema.zram_get():
        return {"zram": None}
    omni_sistema.zram_set(768)
    return {"zram": 0}


FIXES = {"chmod": _fix_chmod, "crlf": _fix_crlf, "zram": _fix_zram}
FIX_DONE = {"chmod": "permissão de execução dada aos arquivos do port",
            "crlf": "scripts convertidos para o formato do Linux",
            "zram": "memória extra (zram) ligada com 768 MB"}


def apply(report, fix):
    """Aplica a correção e guarda o desfazer para depois do novo teste. Devolve o script do port."""
    script = port_script(report)
    if not script or fix not in FIXES:
        return ""
    undo = FIXES[fix](script, port_dirs(script))
    os.makedirs(os.path.dirname(PENDING), exist_ok=True)
    with open(PENDING, "w") as f:
        json.dump({"script": script, "fix": fix, "undo": undo, "report": report}, f)
    return script


def undo(state):
    u = state.get("undo", {})
    for f, mode in u.get("chmod") or []:
        try:
            os.chmod(f, mode)
        except OSError:
            pass
    for f, bak in u.get("crlf") or []:
        try:
            shutil.move(bak, f)
        except OSError:
            pass
    if u.get("zram") == 0:
        import omni_sistema
        omni_sistema.zram_set(0)


def settle(name, ok):
    """Depois do novo teste: mantém a correção (passou) ou desfaz (falhou). Texto para o resultado."""
    try:
        with open(PENDING) as f:
            state = json.load(f)
        os.remove(PENDING)
    except (OSError, ValueError):
        return ""
    if os.path.basename(state["script"])[:-3] != name:
        undo(state)
        return ""
    what = FIX_DONE.get(state["fix"], state["fix"])
    if ok:
        for f, bak in state.get("undo", {}).get("crlf") or []:
            try:
                os.remove(bak)
            except OSError:
                pass
        note(state["report"], [], f"Correção que resolveu: {what}.")
        return f"A correção funcionou: {what}."
    undo(state)
    return f"A correção ({what}) não resolveu e foi desfeita."
