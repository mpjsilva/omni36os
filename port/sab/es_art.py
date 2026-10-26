"""Arte da Sab no ES: ícone e descrição na lista, logo do sistema no tema.

Roda com o ES parado (ver launch.sh): o ES guarda as listas na memória e
reescreve o gamelist.xml ao sair, então editar com ele aberto não adianta.
"""
import os
import re
import shutil
import xml.etree.ElementTree as ET

import sab

ASSETS = os.path.join(sab.SAB_DIR, "assets")
DESC = ("Assistente do R36S: checkup do console, bateria, som, tela, desempenho, "
        "cartões SD, RetroArch, teste de ports e backup. Tudo pelo controle, sem internet.")
THEME_XML = """<theme>
\t<formatVersion>4</formatVersion>
\t<include>./../theme.xml</include>
\t<view name="system">
\t\t<image name="logo">
\t\t\t<path>./system.png</path>
\t\t</image>
\t</view>
\t<view name="basic">
\t\t<image name="system" extra="true">
\t\t\t<origin>0.5 0</origin>
\t\t\t<pos>0.5 0.0025</pos>
\t\t\t<maxSize>1 .25</maxSize>
\t\t\t<path>./system.png</path>
\t\t\t<zIndex>3</zIndex>
\t\t</image>
\t</view>
</theme>
"""


def gamelist(folder):
    """Entrada da Sab no gamelist.xml de `folder`, sem mexer nas outras."""
    path = os.path.join(folder, "gamelist.xml")
    try:
        tree = ET.parse(path)
        root = tree.getroot()
    except (OSError, ET.ParseError):
        root = ET.Element("gameList")
        tree = ET.ElementTree(root)
    game = next((g for g in root.findall("game") if (g.findtext("path") or "").endswith("/Sab.sh")), None)
    if game is None:
        game = ET.SubElement(root, "game")
        ET.SubElement(game, "path").text = "./Sab.sh"
    for tag, value in (("name", "Sab"), ("desc", DESC), ("image", os.path.join(ASSETS, "es-icon.png")),
                       ("developer", "R36S Brasil"), ("favorite", "true")):
        el = game.find(tag)
        if el is None:
            el = ET.SubElement(game, tag)
        el.text = value
    ET.indent(tree, "\t")
    tree.write(path, encoding="utf-8", xml_declaration=True)


def themes():
    """Pastas do tema ativo (o ES procura em mais de um lugar)."""
    m = re.search(r'name="ThemeSet" value="([^"]+)"', sab.read_text(f"{sab.HOME}/.emulationstation/es_settings.cfg", ""))
    name = m.group(1) if m else ""
    dirs = {os.path.realpath(d) for d in (f"{sab.HOME}/.emulationstation/themes/{name}", f"/roms/themes/{name}",
                                          f"/roms2/themes/{name}", f"/etc/emulationstation/themes/{name}")}
    return [d for d in sorted(dirs) if name and os.path.isfile(os.path.join(d, "theme.xml"))]


def theme_art():
    for t in themes():
        d = os.path.join(t, "sab")
        os.makedirs(d, exist_ok=True)
        shutil.copyfile(os.path.join(ASSETS, "es-system.png"), os.path.join(d, "system.png"))
        sab.write_text(os.path.join(d, "theme.xml"), THEME_XML)


def apply():
    mode = sab.get_mode() or "port"
    folder = sab.system_dir() if mode == "sistema" else sab.es_ports_dir()
    if os.path.isdir(folder):
        gamelist(folder)
    theme_art()


if __name__ == "__main__":
    apply()
