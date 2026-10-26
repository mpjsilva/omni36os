# ROADMAP: Sab — Assistente de Diagnóstico e Ajustes para o R36S

> **Sab** é uma contração de *Saber* / *Sabrina*, em homenagem a uma youtuber que fala de ports do R36S e ajudou muito este projeto.

Utilitário local para o R36S e clones (Rockchip **RK3326**) rodando **dArkOS / ArkOS**, distribuído como port do **PortMaster**. Objetivo: permitir que usuários leigos diagnostiquem e ajustem o aparelho **sem terminal e sem editar arquivos**.

Princípios:

1. **Menu primeiro, LLM opcional.** Digitar com D-pad é lento; um menu resolve todas as ferramentas sem erro. A LLM só entra como atalho de texto livre (Fase 4) se as medições no aparelho justificarem.
2. **Somente leitura no que é perigoso.** A ferramenta de painel **informa**, nunca troca DTB.
3. **Nenhum dado sem fonte.** O que está marcado ✅ foi lido no aparelho de referência; ⚠️ ainda precisa ser confirmado.

---

## 0. Aparelho de referência (inspecionado em 2026-10-25)

| Item | Valor lido |
|---|---|
| Sistema | dArkOS, base Debian 13 (trixie), versão `10152026`, kernel 4.4.189 |
| Modelo (`/proc/device-tree/model` e `Hardware:` do `/proc/cpuinfo`) | `R36S-V21 2024-12-18` |
| Compatible | `rockchip,rk3326-r36s-linux`, `rockchip,rk3326` |
| RAM / swap | 895 MB visíveis, ~685 MB disponíveis em repouso / 511 MB swap |
| Painel | `elida,kd35t133` em `dsi@ff450000/panel@0`, 4 lanes, 640×480, 52×70 mm, timing `50Hz` (pixel clock 58 MHz) |
| Cartões | `mmcblk0` = SO (SanDisk `SB16G`, 2020); `mmcblk1` = ROMs (`manfid 0xfe`, nome `SD`, 2025 — genérico) |
| Python | 3.13.5, **sem pygame e sem PySDL2**; `dialog`, `whiptail` e `dtc`/`fdtget` instalados |
| Root | `sudo` sem senha para o usuário `ark`; `dmesg_restrict = 0` |

---

## 1. Arquitetura

```text
┌───────────────────────────────────────────────┐
│  UI: menu `dialog` no tty (já instalado)      │
│  controles via gptokeyb do PortMaster         │
└──────────────────────┬────────────────────────┘
                       ▼
┌───────────────────────────────────────────────┐
│  sab.py — ferramentas + executor              │
│  (só stdlib, sem shell=True, valores limitados)│
└──────────────────────┬────────────────────────┘
                       ▼  (Fase 4, opcional)
┌───────────────────────────────────────────────┐
│  llama-server (127.0.0.1) + gramática GBNF    │
│  POST /completion {prompt, grammar, ...}      │
└───────────────────────────────────────────────┘
```

- **`dialog` em vez de pygame:** já vem no dArkOS; pygame não está instalado e empacotá-lo para aarch64 + Python 3.13 é trabalho extra sem ganho para um menu.
- **`llama-server` em vez de `llama-cli -i`:** o modo interativo só imprime texto; o `/completion` aceita `grammar` por requisição e devolve o JSON ao orquestrador.

---

## 2. Fontes de dados (✅ = confirmado no aparelho de referência)

| Informação | Fonte | Observação |
|---|---|---|
| Modelo da placa | `/proc/device-tree/model` ✅ | Igual à linha `Hardware:` do `/proc/cpuinfo` e ao campo `model` dos DTBs do catálogo |
| Nó do painel | `/proc/device-tree/dsi@ff450000/panel@0/` ✅ | Contém `compatible`, `panel-init-sequence`, `display-timings/` |
| Catálogo de DTBs | `/boot/dtb/{r36s,clone,soysauce}/<pasta>/rk3326-*-linux.dtb` ✅ | Distribuído pelo dArkOS; 47 modelos em `/boot/dtb/r36_devices.ini` |
| DTB em uso | `/boot/rk3326-r36s-linux.dtb` ✅ | Partição BOOT (vfat) montada em `/boot`; o `boot.ini` carrega esse nome |
| Seletor oficial | `/boot/SELECT MODEL.bat` → `dtb/select_device.ps1` ✅ | Roda **no PC**, com o cartão no leitor |
| Cartão SD | `/sys/block/mmcblk*/device/{manfid,oemid,name,date}` ✅ | Sem root |
| Bateria | `/sys/class/power_supply/battery/capacity` ✅ | Também existem `ac` e `usb` |
| Temperatura | `thermal_zone0` = `soc-thermal`, `thermal_zone1` = `gpu-thermal` ✅ | m°C |
| Brilho | `/sys/class/backlight/backlight/` ✅ | `max_brightness = 160` (não 255); arquivo `root:video 664` |
| Governador | `.../cpufreq/policy0/` ✅ | Padrão `ondemand`; disponíveis: interactive, conservative, ondemand, userspace, powersave, performance, schedutil; freq. 1008–1512 MHz (`max_cpufreq=1512` no boot) |
| Volume | `amixer -c 0 sset Playback` ✅ | **Sempre com `-c 0`**: sem ele o `amixer` usa o ctl do `.asoundrc` e às vezes não lista nada. `Master` aparece listado mas não é acessível. É o mesmo comando do `/usr/local/bin/boot_volume.sh` (padrão 40%) |
| Rota de áudio | `amixer -c 0 sget 'Playback Path'` ✅ | Enum `OFF`/`SPK`/`HP`/`SPK_HP`; atual `SPK_HP`. `/usr/local/bin/fixvolume.sh` recoloca `SPK_HP`; `checknswitchforusbdac.sh` troca para `HP`/`SPK` e para DAC USB |
| `/tmp` | **tmpfs** (448 MB) ✅ | Não serve para medir o SD |
| PortMaster | `/opt/system/Tools/PortMaster` ✅ | `/opt/system/Tools` fica no cartão de ROMs |
| Ports | `/roms/ports` ou `/roms2/ports` ✅ | No aparelho de referência, `/roms2` = `mmcblk1p1` |
| RetroArch | `~/.config/retroarch/retroarch.cfg` ✅ | `retroarch.cfg.bak` (dono root, 2026-07-28) é a cópia de fábrica; difere do atual em 10 linhas. Idem `retroarch-core-options.cfg.bak`. Também existe `~/.config/retroarch32/` |
| ALSA | `~/.asoundrc` = `~/.asoundrcbak` ✅ | dmix em `hw:0,0`, 44100 Hz. `perfnorm` copia `.asoundrcbak` → `.asoundrc` ao sair de cada jogo |
| PortMaster por distro | `mod_dArkOS.txt`, `mod_ArkOS.txt` ✅ | `control.txt` define `directory` (`roms`/`roms2`), `$ESUDO` (`sudo --preserve-env=...`) e `$GPTOKEYB` |

**Armadilha:** `/proc/device-tree` é symlink — `find /proc/device-tree -name ...` não desce nele; usar o caminho direto ou `find /proc/device-tree/`.

---

## 3. Ferramentas

### 3.1 Painel e modelo da placa (somente leitura)

**Problema real:** existem dezenas de placas R36S e clones, com painéis diferentes. Gravar o DTB errado resulta em tela preta.

**O que o dArkOS já resolve:** o catálogo em `/boot/dtb/` e o seletor `SELECT MODEL` — mas o seletor roda no PC e o usuário precisa saber qual pasta escolher.

**O que o Sab acrescenta:** com a tela funcionando, dizer **qual pasta do catálogo corresponde ao aparelho**, para o usuário anotar antes de atualizar ou reinstalar.

**Método (validado):**
1. Ler `model` e o SHA-256 de `panel-init-sequence` do DT em execução.
2. Para cada DTB do catálogo, extrair os mesmos dois campos com `fdtget` (ou parser FDT em Python).
3. Resultado:
   - **model + hash iguais** → "Seu aparelho usa a pasta X" (pode haver várias pastas equivalentes);
   - **só o hash igual** → "mesma sequência de inicialização de tela que X, Y, Z" (provável compatibilidade);
   - **nada igual** → "DTB personalizado; faça backup de `/boot` antes de atualizar".

**Por que não usar só o hash:** a mesma sequência aparece em placas e controladores diferentes (ex.: `3f7a1a32…` é usado por clones "Panel 8" com `elida,kd35t133` e por "Variant 2 Panel 1" com `sitronix,st7703`). O par **model + hash** é o identificador.

**Por que não o MD5 do `.dtb`:** o DTB em uso no aparelho de referência (`170a8bad…`) não é byte a byte igual a nenhum do catálogo, embora o painel seja idêntico ao das pastas V21/V22. Qualquer ajuste no DTB muda o hash do arquivo.

#### Catálogo de painéis (extraído de `/boot/dtb` do dArkOS `10152026`)

| Hash `panel-init-sequence` (16 primeiros) | Bytes | Controlador | Pastas do catálogo |
|---|---|---|---|
| `29bb3a98cbf8030f` | 763 | elida,kd35t133 | r36s/R36S-V21 2024-12-18 (2529, 2544, 2550, 2551, 2552); r36s/R36S-V22 2024-12-18 (base, 2534¹, 2535, 2545, 2548); r36s/R36S-V30 2025-11-18 2603¹; r36s/R36XX-V21; r36s/HL-R36H-V21 2024-11-18 — **aparelho de referência** |
| `b98004a555bc0a00` | 773 | elida,kd35t133 | r36s/R36S-V12 Panel 4; r36s/HL-R36H-V20 2024-05-18; r36s/R36S-V21 2547 ("fix by lxc") |
| `972f614858caa119` | 370 | elida,kd35t133 | r36s/R36S-V12 Panel 0 |
| `cbe5698d25e42d93` | 928 | elida,kd35t133 | r36s/R36S-V21 2537 |
| `6538f38f289c5d30` | 326 | elida,kd35t133 | r36s/R36S-Plus-V20 2025-03-18 2551 |
| `3f7a1a3231d1b301` | 370 | elida,kd35t133 / sitronix,st7703 | clone/G80C(A)-MB … Panel 8 (V1.1, V1.2, V1.3); clone/R36S-V12 Variant 1 Panel 8 A; clone/R36S-V12 Variant 2 Panel 1 (e 1 A, st7703); r36s/R36S-Y02 |
| `ee05de3b4a3a54ca` | 753 | elida,kd35t133 / sitronix,st7703 | clone/G80C(A)-MB … Panel 9; clone/R36S-V12 Variant 1 Panel 3 A; clone/R36S-V12 Variant 3 Panel 3 (st7703) |
| `8ea86fccd4b15799` | 375 | sitronix,st7703 | clone/R36S-V12 Variant 3 Panel A |
| `63b5e523257da711` | 375 | elida,kd35t133 | soysauce/Y3506_V03 (20241104, 20241210) |
| `9f1bc58060336bb9` | 755 | elida,kd35t133 | soysauce/Y3506_V03_20250317; soysauce/Y3506_V04_20250529 2548 |
| `a4e17d2b39fcc34a` | 323 | elida,kd35t133 | soysauce/Y3506_V05_20251215 2551 |
| `df75a0f24f74a1b0` | 420 | elida,kd35t133 | soysauce/Y3506_V05_20251215 2601 |

¹ `compatible` = `simple-panel-dsi` nesses DTBs.

- `r36_devices.ini` diz que as seções são "strings exatas da linha `Hardware:` do `/proc/cpuinfo`" e classifica cada modelo como `r36s`, `clone` ou `soysauce`; o seletor do PC marca `clone` e `soysauce` como **UNSUPPORTED**. O Sab deve repetir esse aviso.
- O seletor apaga os `.dtb` da raiz da BOOT e copia **toda** a pasta escolhida (inclusive `boot.ini`). Por isso o Sab recomenda backup de `/boot` antes.
- O significado dos sufixos numéricos das pastas (2529, 2550…) não está documentado: a linha `Hardware:` do aparelho de referência é `R36S-V21 2024-12-18`, sem sufixo. ⚠️ Perguntar na comunidade e não exibir interpretação ao usuário.
- O catálogo muda a cada versão do dArkOS. O Sab deve **gerar a tabela em tempo de execução** a partir de `/boot/dtb`, e não embutir a tabela acima; ela fica aqui como referência e caso de teste.
- Em ArkOS e outras distros sem `/boot/dtb`, mostrar só modelo, controlador e hash. ⚠️ verificar onde o ArkOS guarda as variantes de painel.

### 3.2 Cartões MicroSD

- **Identificação** pelo CID, para cada `mmcblk*`, informando o papel de cada um (SO, ROMs) a partir de `mount`.
- **Fabricantes:** `0x000003` = SanDisk ✅ (cartão do aparelho de referência, OEM `SD`, nome `SB16G`). O segundo cartão (`manfid 0xfe`, OEM `0x3432`, nome `SD`) é o perfil típico de cartão genérico — exibir como "fabricante não identificado", sem afirmar que é falsificado. Ampliar a tabela só com cartões verificados.
- **Velocidade:** escrever e ler 64 MB na partição do cartão testado (ex.: `/roms` ou `/roms2`, exFAT), com `fsync` e `echo 3 > /proc/sys/vm/drop_caches` antes da leitura. **Nunca em `/tmp`** (tmpfs confirmado).
- **Capacidade falsa:** teste estilo `f3` (preencher o espaço livre com padrão conhecido e reler), opcional, com confirmação e barra de progresso.

### 3.3 Energia e desempenho

- Governador: oferecer só o que estiver em `scaling_available_governors`. Atenção: o dArkOS usa `perfmax`/`perfnorm` ao abrir/fechar jogos; o Sab deve restaurar o governador anterior ao sair.
- Brilho: `round(pct/100 * 160)` no aparelho de referência — sempre ler `max_brightness`; mínimo 1.
- Volume: `amixer -c 0 -q sset Playback <pct>%`.

### 3.4 Restaurar áudio / RetroArch

- **Áudio** (tudo com scripts que o próprio dArkOS já usa):
  1. `cp ~/.asoundrcbak ~/.asoundrc` (o mesmo que o `perfnorm` faz);
  2. rota: `alsa_path` do modelo em `r36_devices.ini` (`SPK_HP` ou `SPK`; fallback `SPK_HP`, como no `fixvolume.sh`), aplicada com `amixer -c 0 cset name='Playback Path' <rota>`;
  3. volume em 40% (`boot_volume.sh`).
- **RetroArch:** copiar o atual para `retroarch.cfg.sab-<data>` e restaurar a partir de `retroarch.cfg.bak` (e `retroarch-core-options.cfg.bak`). Antes, mostrar o número de linhas diferentes.

---

## 4. Código

> **Implementação atual:** `port/` (`Sab.sh` + `sab/sab.py`, `sab/sab_menu.sh`, `sab/sab.gptk`), instalada em `/roms2/ports/` no aparelho de referência. Os trechos abaixo são o esboço original; o código em `port/` é a referência. Diferenças principais: parser de DTB em Python puro (não depende de `fdtget`), casamento de modelo por prefixo (os DTBs do catálogo têm sufixo, ex. `… 2550`), menu no padrão dos scripts do dArkOS (`/opt/inttools/gptokeyb`, fonte Terminus 22×11).

### 4.1 `sab.py` (núcleo, só stdlib)

```python
#!/usr/bin/env python3
import glob
import hashlib
import json
import os
import struct
import subprocess
import sys

DT = "/proc/device-tree"
PANEL = f"{DT}/dsi@ff450000/panel@0"
CATALOG = "/boot/dtb"


def read(path, default=None):
    try:
        with open(path, "rb") as f:
            return f.read()
    except OSError:
        return default


def read_text(path, default="N/A"):
    data = read(path)
    return data.split(b"\x00")[0].decode(errors="replace").strip() if data else default


def clamp_pct(value):
    return max(0, min(100, int(value)))


# --- Painel / modelo ---

def fdtget(dtb, node, prop, raw=False):
    args = ["fdtget", "-t", "bx" if raw else "s", dtb, node, prop]
    out = subprocess.run(args, capture_output=True, text=True).stdout.strip()
    return bytes.fromhex("".join(b.zfill(2) for b in out.split())) if raw else out


def catalog_entries():
    for dtb in sorted(glob.glob(f"{CATALOG}/*/*/rk3326-*-linux.dtb")):
        panels = [n for n in fdtget_list(dtb, "/dsi@ff450000") if n.startswith("panel")]
        if not panels:
            continue
        node = f"/dsi@ff450000/{panels[0]}"
        seq = fdtget(dtb, node, "panel-init-sequence", raw=True)
        yield {
            "model": fdtget(dtb, "/", "model"),
            "hash": hashlib.sha256(seq).hexdigest(),
            "folder": os.path.relpath(os.path.dirname(dtb), CATALOG),
        }


def fdtget_list(dtb, node):
    out = subprocess.run(["fdtget", "-l", dtb, node], capture_output=True, text=True).stdout
    return out.split()


def detect_hardware_and_screen():
    model = read_text(f"{DT}/model")
    seq = read(f"{PANEL}/panel-init-sequence")
    if seq is None:
        return f"Aparelho: {model}\nPainel: nó não encontrado em {PANEL}"

    digest = hashlib.sha256(seq).hexdigest()
    entries = list(catalog_entries()) if os.path.isdir(CATALOG) else []
    exact = sorted({e["folder"] for e in entries if e["hash"] == digest and e["model"] == model})
    same_panel = sorted({e["folder"] for e in entries if e["hash"] == digest} - set(exact))

    lines = [
        f"Aparelho: {model}",
        f"Controlador: {read_text(PANEL + '/compatible')}",
        f"Assinatura do painel: {digest[:16]}",
    ]
    if exact:
        lines.append("Pasta(s) do SELECT MODEL para este aparelho:")
        lines += [f"  {f}" for f in exact]
    elif same_panel:
        lines.append("Mesma tela que (modelo diferente):")
        lines += [f"  {f}" for f in same_panel]
    elif entries:
        lines.append("DTB personalizado: faça backup de /boot antes de atualizar.")
    return "\n".join(lines)


# --- SD ---

SD_VENDORS = {0x03: "SanDisk"}


def mount_points():
    mounts = {}
    with open("/proc/mounts") as f:
        for line in f:
            dev, mnt = line.split()[:2]
            if dev.startswith("/dev/mmcblk"):
                mounts.setdefault(dev[5:].split("p")[0], []).append(mnt)
    return mounts


def check_microsd_info():
    mounts = mount_points()
    lines = []
    for dev in sorted(glob.glob("/sys/block/mmcblk*/device")):
        blk = dev.split("/")[3]
        vendor = SD_VENDORS.get(int(read_text(f"{dev}/manfid", "0"), 16), "não identificado")
        sectors = int(read_text(f"/sys/block/{blk}/size", "0"))
        lines.append(
            f"{blk}: {vendor}, {read_text(dev + '/name')}, {sectors * 512 / 1e9:.1f} GB, "
            f"fab. {read_text(dev + '/date')}, em {' '.join(mounts.get(blk, ['-']))}"
        )
    return "\n".join(lines) or "Nenhum cartão encontrado."


# --- Sistema ---

def get_system_status():
    bat = read_text("/sys/class/power_supply/battery/capacity")
    temp = read_text("/sys/class/thermal/thermal_zone0/temp", "")
    temp_c = f"{int(temp) // 1000}°C" if temp.isdigit() else "N/A"
    gov = read_text("/sys/devices/system/cpu/cpufreq/policy0/scaling_governor")
    return f"Bateria: {bat}% | CPU: {temp_c} | Governador: {gov}"


def set_screen_brightness(pct):
    base = "/sys/class/backlight/backlight"
    maxb = int(read_text(f"{base}/max_brightness", "160"))
    with open(f"{base}/brightness", "w") as f:
        f.write(str(max(1, round(clamp_pct(pct) / 100 * maxb))))
    return f"Brilho: {clamp_pct(pct)}%"


def set_system_volume(pct):
    subprocess.run(["amixer", "-c", "0", "-q", "sset", "Playback", f"{clamp_pct(pct)}%"], check=False)
    return f"Volume: {clamp_pct(pct)}%"


def set_cpu_governor(name):
    base = "/sys/devices/system/cpu/cpufreq/policy0"
    available = read_text(f"{base}/scaling_available_governors", "").split()
    if name not in available:
        return f"Governador indisponível. Opções: {', '.join(available)}"
    with open(f"{base}/scaling_governor", "w") as f:
        f.write(name)
    return f"Governador: {name}"


# --- Executor (usado pelo menu e, na Fase 4, pela LLM) ---

TOOLS = {
    "detect_hardware_and_screen": lambda a: detect_hardware_and_screen(),
    "check_microsd_info": lambda a: check_microsd_info(),
    "get_system_status": lambda a: get_system_status(),
    "set_screen_brightness": lambda a: set_screen_brightness(a["value"]),
    "set_system_volume": lambda a: set_system_volume(a["value"]),
    "set_cpu_governor": lambda a: set_cpu_governor(a["governor"]),
}


def run_tool(call):
    tool = TOOLS.get(call.get("tool"))
    if not tool:
        return "Comando não reconhecido."
    try:
        return tool(call.get("args", {}))
    except (KeyError, ValueError, OSError) as e:
        return f"Erro: {e}"


if __name__ == "__main__":
    if len(sys.argv) > 1:
        args = json.loads(sys.argv[2]) if len(sys.argv) > 2 else {}
        print(run_tool({"tool": sys.argv[1], "args": args}))
    else:
        print("\n".join(TOOLS))
```

Teste via SSH: `sudo python3 sab.py detect_hardware_and_screen` — no aparelho de referência deve listar as pastas `r36s/R36S-V21 2024-12-18 …`.

### 4.2 Menu (`sab_menu.sh`)

`dialog --menu` chamando `sab.py <ferramenta>` e exibindo o resultado com `dialog --msgbox`. Brilho e volume via `dialog --rangebox` (0–100). Rodar no `/dev/tty1` com `TERM=linux`.

### 4.3 `tools.gbnf` (Fase 4)

```bnf
root ::= "{" ws "\"tool\":" ws call ws "}"

call ::= noarg | pct-tool | gov-tool | none

noarg    ::= "\"" ("detect_hardware_and_screen" | "check_microsd_info" | "get_system_status") "\""
pct-tool ::= "\"" ("set_screen_brightness" | "set_system_volume") "\"" ws "," ws "\"args\":" ws "{" ws "\"value\":" ws pct ws "}"
gov-tool ::= "\"set_cpu_governor\"" ws "," ws "\"args\":" ws "{" ws "\"governor\":" ws gov ws "}"
none     ::= "\"none\""

pct ::= [0-9] | [1-9] [0-9] | "100"
gov ::= "\"" ("performance" | "powersave" | "schedutil" | "ondemand" | "conservative" | "interactive") "\""

ws ::= [ \t\n]?
```

### 4.4 `Sab.sh` (lançador padrão PortMaster)

```bash
#!/bin/bash
# PORTMASTER: Sab — diagnóstico e ajustes do R36S

XDG_DATA_HOME=${XDG_DATA_HOME:-$HOME/.local/share}

if [ -d "/opt/system/Tools/PortMaster/" ]; then
  controlfolder="/opt/system/Tools/PortMaster"
elif [ -d "/opt/tools/PortMaster/" ]; then
  controlfolder="/opt/tools/PortMaster"
elif [ -d "$XDG_DATA_HOME/PortMaster/" ]; then
  controlfolder="$XDG_DATA_HOME/PortMaster"
else
  controlfolder="/roms/ports/PortMaster"
fi

source $controlfolder/control.txt
[ -f "${controlfolder}/mod_${CFW_NAME}.txt" ] && source "${controlfolder}/mod_${CFW_NAME}.txt"
get_controls

GAMEDIR="/$directory/ports/sab"
cd "$GAMEDIR"

$GPTOKEYB "dialog" -c "$GAMEDIR/sab.gptk" &
$ESUDO env TERM=linux bash "$GAMEDIR/sab_menu.sh" > /dev/tty1 < /dev/tty1

pm_finish
```

`$directory` resolve para `roms` ou `roms2`; não fixar `/storage/roms` (caminho do JELOS/ROCKNIX).

### 4.5 `sab.gptk`

```text
up = up
down = down
left = left
right = right
a = enter
b = esc
start = enter
back = esc
l1 = pageup
r1 = pagedown
x = tab
```

Formato confirmado no `ccleste.gptk` instalado: `a`, `b`, `x`, `y`, `l1`, `l2`, `r1`, `r2`, `start`, `up`/`down`/`left`/`right` e `left_analog_*`. ⚠️ o nome do botão Select (`back` ou `select`) ainda não foi confirmado.

---

## 5. LLM (Fase 4, opcional)

Orçamento: ~685 MB disponíveis em repouso no aparelho de referência, com 511 MB de swap em cartão (lento; não contar com ela).

| Métrica | Como medir | Meta |
|---|---|---|
| RAM residente do `llama-server` | `ps -o rss` | deixar ≥ 300 MB livres |
| Latência prompt → JSON | `curl` em `/completion` com o prompt real | < 3 s |
| Acerto da ferramenta | 50 frases em português escritas à mão | ≥ 90 % |
| Velocidade bruta | `llama-bench -m <modelo> -t 4` | registrar pp/tg |

Candidatos (nesta ordem): Qwen2.5-0.5B-Instruct Q4_K_M, SmolLM2-360M-Instruct Q4_K_M, SmolLM2-135M-Instruct Q8_0. Evitar Q2_K em modelos < 1B.

---

## 6. Fases

* [x] **Fase 0 — Inspeção do aparelho de referência** (2026-10-25, dArkOS 10152026, R36S-V21 2024-12-18): painel, catálogo de DTBs, áudio, RetroArch, PortMaster
* [~] **Fase 1 — Núcleo e menu** — código em `port/`; ferramentas testadas via SSH em 2026-10-25 (painel em 2,1 s, SD, status, brilho/volume/governador com restauração dos valores, rejeição de valores inválidos e de `/tmp`). Falta: abrir o menu pelo EmulationStation e testar `restore_audio`/`restore_retroarch` no aparelho
  * `sab.py` + `sab_menu.sh` com `dialog`; testar cada ferramenta via SSH.
  * Restaurar governador e brilho originais ao sair.
* [ ] **Fase 2 — Identificação de painel**
  * Geração do catálogo em tempo de execução a partir de `/boot/dtb`; validar contra a tabela da seção 3.1.
  * Repetir a inspeção em ArkOS e em pelo menos um clone (G80CA ou soysauce).
* [ ] **Fase 3 — SD e restauração**
  * Velocidade na partição do cartão; verificação de capacidade estilo `f3`.
  * Restauração de áudio (`alsa_path` do `r36_devices.ini`) e RetroArch com backup.
* [ ] **Fase 4 — LLM opcional**
  * Compilar `llama-server`/`llama-bench` para aarch64 e executar as medições da seção 5.
* [ ] **Fase 5 — Pacote PortMaster**
  * `.zip` com `Sab.sh` + pasta `sab/`, extraível em `roms/ports/`.
  * Testar em cartão limpo no dArkOS e no ArkOS.
