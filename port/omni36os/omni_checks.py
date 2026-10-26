#!/usr/bin/env python3
"""Omni36OS — diagnósticos por regras fixas (sem IA).

Cada verificação coleta fatos com as ferramentas de omni.py e devolve achados
(nível, texto) e as ações sugeridas. Níveis: "ok", "info", "aviso", "problema"
("info" não conta como alerta).

Uso: omni_checks.py [verificação]   (sem argumento lista as verificações)
"""
import glob
import json
import os
import sys

import omni

TEMP_QUENTE = 75      # °C: acima disso o aparelho está aquecendo
BATERIA_BAIXA = 20    # %
SD_LENTO = 10         # MB/s de escrita

# --- Ações (o único jeito de uma verificação mudar algo no aparelho) ---

ACTIONS = {
    "economizar_bateria": ("Ativar modo economia",
                           lambda: omni.set_preferred_governor({"governor": "powersave"})),
    "modo_desempenho": ("Ativar desempenho máximo",
                        lambda: omni.set_preferred_governor({"governor": "performance"})),
    "modo_equilibrado": ("Voltar ao modo equilibrado",
                         lambda: omni.set_preferred_governor({"governor": "ondemand"})),
    "baixar_brilho": ("Baixar o brilho para 30%", lambda: omni.set_screen_brightness({"value": 30})),
    "restaurar_audio": ("Restaurar o áudio do sistema", omni.restore_audio),
    "volume_60": ("Colocar o volume em 60%", lambda: omni.set_system_volume({"value": 60})),
    "restaurar_retroarch": ("Restaurar o RetroArch de fábrica", omni.restore_retroarch),
    "ligar_pendrive": ("Ligar o modo pendrive (reinicia)", omni.usb_on),
    "desligar_pendrive": ("Desligar o modo pendrive (reinicia)", omni.usb_off),
    "fix_dmc": ("Consertar o ajuste da RAM", omni.fix_dmc),
    "limpar_mac": ("Limpar o lixo do Mac", omni.clean_mac_junk),
    "cpu_padrao": ("Tirar o overclock (1296 MHz)", lambda: omni.set_cpu_max({"mhz": omni.CPU_SAFE_MHZ})),
}

ESPACO_POUCO_PCT = 90   # % de uso do cartão
ESPACO_POUCO_GB = 1.0


def run_action(name):
    return ACTIONS[name][1]() if name in ACTIONS else "Nada a fazer."


# --- Fatos ---

def battery_facts():
    return {
        "bateria_pct": int(omni.read_text("/sys/class/power_supply/battery/capacity", "0")),
        "bateria_estado": omni.read_text("/sys/class/power_supply/battery/status"),
    }


def cpu_facts():
    temp = omni.read_text("/sys/class/thermal/thermal_zone0/temp", "0")
    return {
        "temperatura_c": int(temp) // 1000 if temp.isdigit() else None,
        # o que vale no menu do ES (dentro do Omni36OS o ES sempre deixa "performance")
        "governador": omni.get_preferred_governor(),
        "freq_mhz": int(omni.read_text(f"{omni.CPUFREQ}/scaling_cur_freq", "0")) // 1000,
        "cpu_max_mhz": omni.get_cpu_max(),
        "gpu_max_mhz": omni.get_gpu_max(),
    }


def audio_facts():
    route = ""
    for line in omni.amixer("sget", "Playback Path").splitlines():
        if line.strip().startswith("Item0:"):
            route = line.split("'")[1]
    asound, backup = omni.read(f"{omni.HOME}/.asoundrc"), omni.read(f"{omni.HOME}/.asoundrcbak")
    return {
        "volume_pct": omni.get_volume(),
        "saida_audio": route,
        "saida_esperada": omni.device_alsa_path(),
        # O perfmax do dArkOS apaga o .asoundrc ao abrir qualquer port (o Omni36OS
        # inclusive) e o perfnorm o devolve ao sair: ausente é o normal aqui.
        "asoundrc_padrao": asound is None or backup is None or asound == backup,
    }


def sd_facts():
    cards = []
    mounts = omni.mmc_mounts()
    for dev in sorted(glob.glob("/sys/block/mmcblk*/device")):
        blk = dev.split("/")[3]
        manfid = int(omni.read_text(f"{dev}/manfid", "0"), 16)
        cards.append({
            "codigo": f"0x{manfid:02x}", "nome": omni.read_text(f"{dev}/name"),
            "cartao": "sistema" if "/" in mounts.get(blk, []) else "jogos",
            "fabricante": omni.SD_VENDORS.get(manfid, "desconhecido"),
            "tamanho_gb": round(int(omni.read_text(f"/sys/block/{blk}/size", "0")) * 512 / 1e9, 1),
        })
    return {"cartoes": cards}


def speed_facts():
    facts = {}
    for name, path in (("sistema", "/roms"), ("jogos", "/roms2")):
        if not os.path.ismount(path):
            continue
        for line in omni.test_microsd_speed({"path": path}).splitlines():
            if "Escrita" in line or "Leitura" in line:
                key = "escrita" if "Escrita" in line else "leitura"
                facts[f"{name}_{key}_mbs"] = float(line.split(":")[1].split()[0])
    return facts


def screen_facts():
    live = omni.live_panel() or {}
    entries = list(omni.catalog_panels()) if os.path.isdir(omni.CATALOG) else []
    same = [e for e in entries if e["hash"] == live.get("hash")]
    model = live.get("model", "")
    folders = [e["folder"] for e in same if e["model"] == model or e["model"].startswith(model + " ")]
    return {
        "modelo": model,
        "pastas": sorted(set(folders or [e["folder"] for e in same])),
        "clone": any(e["variant"] in ("clone", "soysauce") for e in same),
    }


# --- Regras ---

def check_temp(f, out):
    t = f["temperatura_c"]
    if t is None:
        return
    if t > TEMP_QUENTE:
        out.append(("problema", f"Está quente: {t} °C. Deixe esfriar e evite jogar carregando."))
    else:
        out.append(("ok", f"Temperatura normal: {t} °C."))


def check_overclock(f, out, acts):
    oc = f["cpu_max_mhz"] > omni.CPU_SAFE_MHZ
    if oc and (f["temperatura_c"] or 0) > TEMP_QUENTE:
        out.append(("aviso", f"Overclock ligado ({f['cpu_max_mhz']} MHz) com o aparelho quente."))
        acts.append("cpu_padrao")
    elif oc:
        out.append(("info", f"Overclock ligado: processador até {f['cpu_max_mhz']} MHz."))


def check_services(out, acts):
    for unit in omni.failed_services():
        txt, fix = omni.KNOWN_FAILS.get(unit, (None, None))
        if txt and not fix:
            out.append(("info", txt))
        elif txt:
            out.append(("aviso", txt))
            acts.append(fix)
        else:
            out.append(("aviso", f"O serviço {unit.removesuffix('.service')} falhou no boot."))


def check_disk(out):
    nomes = {"sistema": "do sistema", "roms": "/roms", "jogos": "de jogos"}
    for name, d in omni.disk_facts().items():
        if d["uso_pct"] >= ESPACO_POUCO_PCT or d["livre_gb"] < ESPACO_POUCO_GB:
            dica = " Atualizações podem falhar." if name == "sistema" else ""
            out.append(("aviso", f"Cartão {nomes[name]} quase cheio: {d['uso_pct']}% usado, "
                                 f"{d['livre_gb']} GB livres.{dica}"))
        else:
            out.append(("ok", f"Espaço {nomes[name]}: {d['livre_gb']} GB livres ({d['uso_pct']}% usado)."))


def check_battery(f, out):
    pct, estado = f["bateria_pct"], f["bateria_estado"]
    carregando = estado in ("Charging", "Full")
    if pct < BATERIA_BAIXA and not carregando:
        out.append(("problema", f"Bateria baixa: {pct}%. Coloque para carregar."))
    else:
        out.append(("ok", f"Bateria em {pct}%" + (" (carregando)." if carregando else ".")))


def check_audio(f, out):
    if f["volume_pct"] == 0:
        out.append(("problema", "O volume está zerado."))
    elif f["volume_pct"] < 20:
        out.append(("aviso", f"O volume está baixo ({f['volume_pct']}%)."))
    else:
        out.append(("ok", f"Volume em {f['volume_pct']}%."))
    if f["saida_audio"] and f["saida_audio"] != f["saida_esperada"]:
        out.append(("problema", f"A saída de som está em {f['saida_audio']}, o certo é {f['saida_esperada']}."))
    if not f["asoundrc_padrao"]:
        out.append(("aviso", "A configuração de som foi alterada por algum jogo ou app."))


def checkup():
    f = {**battery_facts(), **cpu_facts(), **audio_facts(), **sd_facts()}
    out, acts = [], []
    check_battery(f, out)
    check_temp(f, out)
    check_audio(f, out)
    check_overclock(f, out, acts)
    check_services(out, acts)
    check_disk(out)
    for c in f["cartoes"]:
        lvl = "aviso" if c["fabricante"] == "desconhecido" else "ok"
        if lvl == "ok":
            txt = f"Cartão de {c['cartao']}: {c['tamanho_gb']} GB, {c['fabricante']}."
        else:
            txt = (f"Cartão de {c['cartao']}: {c['tamanho_gb']} GB, fabricante não identificado "
                   f"(código {c['codigo']}, nome \"{c['nome']}\"), comum em cartões genéricos.")
        out.append((lvl, txt))
    if f["bateria_pct"] < BATERIA_BAIXA and f["governador"] == "performance":
        acts.append("economizar_bateria")
    if f["saida_audio"] != f["saida_esperada"] or not f["asoundrc_padrao"]:
        acts.append("restaurar_audio")
    return finish(out, acts, f)


def bateria():
    f = {**battery_facts(), **cpu_facts(), "brilho_pct": omni.get_brightness()}
    out, acts = [], []
    check_battery(f, out)
    if f["brilho_pct"] > 60:
        out.append(("aviso", f"Brilho alto ({f['brilho_pct']}%): a tela é o que mais gasta bateria."))
        acts.append("baixar_brilho")
    else:
        out.append(("ok", f"Brilho em {f['brilho_pct']}%."))
    if f["governador"] == "performance":
        out.append(("aviso", "O processador está em desempenho máximo, que gasta mais."))
        acts.append("economizar_bateria")
    else:
        out.append(("ok", f"Processador em modo {f['governador']} no menu."))
    return finish(out, acts, f)


def sem_som():
    f = audio_facts()
    out, acts = [], []
    check_audio(f, out)
    if f["volume_pct"] < 20:
        acts.append("volume_60")
    if f["saida_audio"] != f["saida_esperada"] or not f["asoundrc_padrao"]:
        acts.append("restaurar_audio")
    return finish(out, acts, f)


def lento():
    f = {**cpu_facts(), **speed_facts()}
    out, acts = [], []
    check_temp(f, out)
    if f["governador"] == "powersave":
        out.append(("aviso", "O processador está em modo economia, o que deixa os jogos lentos."))
        acts.append("modo_equilibrado")
    else:
        out.append(("ok", f"Processador em modo {f['governador']} ({f['freq_mhz']} MHz agora)."))
    check_overclock(f, out, acts)
    for card in ("sistema", "jogos"):
        w = f.get(f"{card}_escrita_mbs")
        if w is None:
            continue
        r = f.get(f"{card}_leitura_mbs", 0)
        if w < SD_LENTO:
            out.append(("problema", f"Cartão de {card} lento: {w} MB/s de escrita. Vale trocar por um melhor."))
        else:
            out.append(("ok", f"Cartão de {card}: {w} MB/s escrita, {r} MB/s leitura."))
    if f["governador"] != "performance" and (f["temperatura_c"] or 0) <= TEMP_QUENTE:
        acts.append("modo_desempenho")
    return finish(out, acts, f)


def atualizar():
    f = screen_facts()
    out = []
    if f["clone"]:
        out.append(("problema", "Este aparelho é um clone: o dArkOS não tem suporte oficial."))
    if f["pastas"]:
        out.append(("ok", "No SELECT MODEL, escolha: " + ", ".join(f["pastas"]) + "."))
    else:
        out.append(("aviso", "Não achei sua tela no catálogo do dArkOS."))
    out.append(("info", "Antes de atualizar, copie a partição BOOT do cartão para o PC."))
    return finish(out, [], f)


def retroarch():
    # linhas "arquivo: N linha(s) diferentes ..." ou "arquivo: sem cópia de fábrica"
    f = {}
    for line in omni.retroarch_changes().splitlines():
        name, _, rest = line.partition(": ")
        f[name] = int(rest.split()[0]) if rest[:1].isdigit() else None
    out, acts = [], []
    for name, n in f.items():
        core = "core-options" in name
        if n is None:
            out.append(("info", f"{name}: sem cópia de fábrica para comparar."))
        elif core:
            out.append(("info", f"{name}: {n} linhas mudaram (normal: cada núcleo grava as suas opções)."))
        elif n > 20:
            out.append(("aviso", f"{name}: {n} linhas mudaram desde a fábrica."))
        else:
            out.append(("ok", f"{name}: quase como veio de fábrica ({n} linhas mudaram)."))
    if any(n and n > 20 for k, n in f.items() if "core-options" not in k):
        out.append(("info", "Se os controles estão estranhos, restaurar resolve (guarda uma cópia)."))
        acts.append("restaurar_retroarch")
    return finish(out, acts, f)


def pc():
    f = omni.usb_facts()
    warn = []
    if omni.usb_net_active():
        warn.append(("aviso", "O USB Network Mode está ligado: ele usa a mesma porta. Desligue-o antes do pendrive."))
    part = f["particao_para_o_pc"]
    livre = f["livre_gb"].get(part)
    espaco = f" ({livre} GB livres)" if livre is not None else ""
    if f["modo_pendrive_ligado"]:
        out = [("ok", f"Modo pendrive ligado: /{part}{espaco} aparece no PC."),
               ("ok", "Conecte o cabo de dados, copie, ejete no PC e desconecte (ou aperte B)."),
               ("info", "Wi-Fi e teclado USB ficam desligados nesse modo.")]
        return finish(warn + out, ["desligar_pendrive"], f)
    out = [("ok", f"A partição /{part}{espaco} vai aparecer no PC como pendrive."),
           ("info", "Ligar reinicia o aparelho; Wi-Fi e teclado USB param até desligar."),
           ("info", "Copiou do Mac? \"Limpar lixo do Mac\" apaga os arquivos ._ que ele cria.")]
    return finish(warn + out, ["ligar_pendrive"], f)


ORDER = {"problema": 0, "aviso": 1, "ok": 2, "info": 3}


def finish(out, acts, facts):
    out = sorted(out, key=lambda a: ORDER.get(a[0], 9))   # alertas primeiro
    worst = "ok"
    for lvl, _ in out:
        if lvl == "problema" or (lvl == "aviso" and worst == "ok"):
            worst = lvl
    return {"nivel": worst, "achados": out, "acoes": acts, "fatos": facts}


CHECKS = {
    "checkup": checkup, "bateria": bateria, "sem_som": sem_som, "lento": lento,
    "atualizar": atualizar, "retroarch": retroarch, "pc": pc,
}

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("\n".join(CHECKS))
    else:
        print(json.dumps(CHECKS[sys.argv[1]](), ensure_ascii=False, indent=1))
