#!/usr/bin/env python3
# =============================================================================
# ports.py — Gerenciador de ports para o Omni36OS (launcher como shell principal)
#
# Funções:
#   - Varrer /roms/ports/ e /roms2/ports/ em busca de ports instalados
#   - Ler control.txt do PortMaster para cada port
#   - Retornar lista de ports com metadados (nome, caminho, ícone, último acesso)
#   - Lançar port diretamente (sem EmulationStation)
# =============================================================================

import os
import glob
import json
import subprocess
import time
from pathlib import Path

# Diretórios de ports (prioridade: roms2 primeiro, depois roms)
PORTS_DIRS = [
    "/roms2/ports",
    "/roms/ports",
]

# Caminho do control.txt do PortMaster
PORTMASTER_CONTROL = "/opt/system/Tools/PortMaster/control.txt"

# Arquivo de histórico de ports jogados
PORTS_HISTORY = os.path.expanduser("~/.config/omni36os/ports_history.json")

# Ícone padrão se não houver
DEFAULT_ICON = None


def ensure_dirs():
    """Garante que os diretórios de config existam."""
    os.makedirs(os.path.dirname(PORTS_HISTORY), exist_ok=True)


def load_history():
    """Carrega histórico de ports jogados (caminho -> timestamp)."""
    ensure_dirs()
    if os.path.exists(PORTS_HISTORY):
        try:
            with open(PORTS_HISTORY, "r") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def save_history(history):
    """Salva histórico de ports jogados."""
    ensure_dirs()
    try:
        with open(PORTS_HISTORY, "w") as f:
            json.dump(history, f, indent=2)
    except Exception:
        pass


def record_port_played(port_path):
    """Registra que um port foi jogado agora."""
    history = load_history()
    history[port_path] = time.time()
    save_history(history)


def find_ports():
    """
    Varre os diretórios de ports e retorna uma lista de dicionários com metadados.

    Cada dicionário contém:
        - name: nome do port (nome da pasta)
        - path: caminho absoluto da pasta do port
        - icon: caminho do ícone (ou None)
        - control: conteúdo do control.txt (ou None)
        - executable: executável principal (ou None)
        - last_played: timestamp do último acesso (ou 0)
    """
    ports = []
    seen = set()

    for ports_dir in PORTS_DIRS:
        if not os.path.isdir(ports_dir):
            continue

        for entry in sorted(os.listdir(ports_dir)):
            port_path = os.path.join(ports_dir, entry)
            if not os.path.isdir(port_path):
                continue

            if port_path in seen:
                continue
            seen.add(port_path)

            # Procurar ícone
            icon = None
            for img in ("icon.png", "icon.jpg", "es-icon.png", "es-system.png"):
                cand = os.path.join(port_path, img)
                if os.path.isfile(cand):
                    icon = cand
                    break

            # Procurar control.txt do PortMaster
            control = None
            control_path = os.path.join(port_path, "control.txt")
            if os.path.isfile(control_path):
                try:
                    with open(control_path, "r") as f:
                        control = f.read()
                except Exception:
                    pass

            # Tentar adivinhar executável (sh ou py na pasta)
            executable = None
            for cand in ("Omni36OS.sh", "launch.sh", "main.sh", "start.sh"):
                if os.path.isfile(os.path.join(port_path, cand)):
                    executable = cand
                    break

            # Histórico
            history = load_history()
            last_played = history.get(port_path, 0)

            ports.append({
                "name": entry,
                "path": port_path,
                "icon": icon,
                "control": control,
                "executable": executable,
                "last_played": last_played,
            })

    # Ordenar por último jogado (mais recente primeiro)
    ports.sort(key=lambda p: p["last_played"], reverse=True)
    return ports


def get_portmaster_env():
    """
    Fonte o control.txt do PortMaster e retorna as variáveis de ambiente
    necessárias para lançar um port.
    Retorna dicionário com variáveis ou None se falhar.
    """
    if not os.path.isfile(PORTMASTER_CONTROL):
        return None

    env = {}
    try:
        # Usar subprocess para source o control.txt e capturar variáveis
        cmd = f"bash -c 'source {PORTMASTER_CONTROL} && env | grep -E \"^(directory|ESUDO|GPTOKEYB|CFW_NAME|controlfolder|GAMEDIR)\"'"
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            for line in result.stdout.strip().split("\n"):
                if "=" in line:
                    key, val = line.split("=", 1)
                    env[key] = val
    except Exception:
        pass

    return env


def launch_port(port_info):
    """
    Lança um port diretamente, sem passar pelo EmulationStation.

    Fluxo:
      1. Salva estado do launcher (para restauração posterior)
      2. Fonte control.txt do PortMaster
      3. Executa get_controls
      4. Lança o executável do port
      5. Aguarda término
      6. Registra no histórico
      7. Retorna controle ao launcher

    Retorna True se o port foi lançado com sucesso, False caso contrário.
    """
    port_path = port_info["path"]
    executable = port_info["executable"]

    if not executable:
        return False, "Nenhum executável encontrado na pasta do port"

    # Carregar ambiente do PortMaster
    env = get_portmaster_env()
    if env is None:
        return False, "PortMaster control.txt não encontrado"

    # Montar comando de lançamento
    full_exec = os.path.join(port_path, executable)

    # Variáveis de ambiente para o port
    launch_env = os.environ.copy()
    launch_env.update(env)
    launch_env["GAMEDIR"] = port_path

    # Construir comando com GPTOKEYB se disponível
    gptkeyb = launch_env.get("GPTOKEYB", "")
    esudo = launch_env.get("ESUDO", "sudo --preserve-env=")

    cmd_parts = []
    if gptkeyb:
        gptkeyb_conf = os.path.join(port_path, "gptk")
        if os.path.isfile(gptkeyb_conf):
            cmd_parts.append(f"{gptkeyb} \"{executable}\" -c \"{gptkeyb_conf}\" &")
    if esudo:
        cmd_parts.append(f"{esudo} ./{executable}")
    else:
        cmd_parts.append(f"./{executable}")

    launch_cmd = " ".join(cmd_parts)

    try:
        # Registrar antes de lançar
        record_port_played(port_path)

        # Executar o port (bloqueante até terminar)
        result = subprocess.run(
            launch_cmd,
            shell=True,
            cwd=port_path,
            env=launch_env,
            timeout=None,
        )

        return True, f"Port finalizado com código {result.returncode}"

    except Exception as e:
        return False, str(e)


def list_ports_summary():
    """
    Retorna uma lista simplificada para exibição na UI.
    """
    ports = find_ports()
    summary = []
    for p in ports:
        summary.append({
            "name": p["name"],
            "path": p["path"],
            "icon": p["icon"],
            "last_played": p["last_played"],
        })
    return summary