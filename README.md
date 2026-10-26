# Sab: assistente do R36S

Port para o R36S com dArkOSen que verifica e ajusta o aparelho com um menu gráfico (Python 3 + SDL2 via ctypes, sem dependências extras). Não usa IA nem internet: são regras fixas em `sab_checks.py` e ações em `sab.py`.

## Instalação

1. Baixe o `Sab-vX.Y.Z.zip` da [última release](https://github.com/mpjsilva/sab-r36s/releases/latest).
2. Extraia e copie **o `Sab.sh` e a pasta `sab/` juntos** para a pasta de ports do cartão que o ES usa:
   - dois cartões: `/roms2/ports/` (cartão de jogos, na partição `EASYROMS`);
   - um cartão só: `/roms/ports/`.
3. No console, atualize a lista (Start > Configurações de jogos > Atualizar lista) ou reinicie, e abra **Ports > Sab**.

Para atualizar, copie por cima: as configurações ficam em `~/.config/sab` e os resultados em `sab/logs`.

## Modos: port ou sistema

Na primeira execução a Sab pergunta onde quer aparecer:

- **Lista de Ports**: a Sab fica em Ports, como qualquer port. Nada muda no ES.
- **Sistema no console**: a Sab ganha a própria entrada no menu principal do ES, com logo e ícone. Ela sai de Ports, um atalho é criado em `<cartão>/sab/Sab.sh` e um bloco marcado é adicionado ao `es_systems.cfg` (backup em `es_systems.cfg.sab-bak`).

Para trocar depois: **Ajuda > Mostrar no console**. Ao fechar a Sab, o ES reinicia uma vez para aplicar a troca, o ícone e a descrição.

## Telas

| | | |
|---|---|---|
| ![Início](docs/prints/02-inicio.png) | ![Verificar](docs/prints/03-verificar.png) | ![Bateria](docs/prints/04-bateria.png) |
| ![Som](docs/prints/05-som.png) | ![Tela e sistema](docs/prints/08-tela.png) | ![Desempenho](docs/prints/07-desempenho.png) |
| ![Pendrive USB](docs/prints/06-pendrive.png) | ![RetroArch](docs/prints/09-retroarch.png) | ![Testar ports](docs/prints/10-testar-ports.png) |
| ![Ajuda](docs/prints/11-ajuda.png) | ![Carregando](docs/prints/01-loading.png) | |

## Estrutura

| Arquivo | Função |
|---|---|
| `port/Sab.sh` | Atalho em Ports (modo port). No modo sistema ele sai de Ports e um atalho igual fica em `/roms2/sab/` |
| `port/sab/launch.sh` | Launcher de verdade. Não para o ES. Lê `/tmp/sab-next`: `test:<port>` roda o teste e reabre a Sab (`SAB_RESUME=testar`); `/opt/system/...` abre a ferramenta do dArkOSen. Reinicia o ES no fim se existir `/tmp/sab-restart-es` |
| `port/sab/sab_ui.py` | Interface: cards, páginas, tela de carregamento, leitor de textos |
| `port/sab/gfx.py` | Desenho com SDL2: caches de geometria, texto, sprites e camadas |
| `port/sab/sab.py` | Ferramentas que leem e mudam o sistema (`python3 sab.py` lista todas) |
| `port/sab/sab_checks.py` | Verificações de cada card e ações sugeridas |
| `port/sab/sab_backup.py` | Exportar e importar as configurações por módulo (`.tar.gz` com manifesto) em `/roms2/backup/sab` |
| `port/sab/sab_help.py` | Manual, cuidados, créditos e histórico de versões (NOVIDADES) |
| `port/sab/port_test.sh` | Teste de port: roda por 15 s; se o port fechar antes, gera o relatório em `sab/logs/<port>/` |
| `port/sab/usb_pendrive.sh` | Modo pendrive (gadget mass storage), instalado em `~/usb-disco.sh` |
| `port/sab/VERSION` | Versão instalada, mostrada no card Ajuda |

## O que a Sab mexe no sistema

- `/etc/cpu-settings.conf` (GOV, FREQ), `/etc/gpu-settings.conf`, `/etc/dmc-settings.conf` e `/etc/gamma-settings.conf`: os mesmos arquivos que os serviços do dArkOSen aplicam no boot.
- `/usr/local/bin/perfnorm`, linha do governador: passa a ler o modo de `/etc/cpu-settings.conf`. O backup fica em `perfnorm.sab-bak`.
- `/usr/local/bin/fix_power_led` e `batt_life_warning.py`: cor do LED, copiadas das variantes `.red` e `.green`.
- `/boot/recovery.sh`: só ao pedir a verificação do cartão. O script do dArkOSen roda no boot e se apaga ao terminar.
- `/etc/emulationstation/es_systems.cfg`: no modo sistema, um bloco `<system>` entre os marcadores `<!-- Sab ... -->`. O backup fica em `es_systems.cfg.sab-bak`.
- `~/.config/sab/modo`: `port` ou `sistema`.
- `port/sab/logs/`: relatórios de testes que falharam e `resultados.txt` (último resultado de cada port).
- `/boot/rk3326-r36s-linux.dtb`: só no modo pendrive. O backup fica em `.host-bak`.

## Lançar uma versão

1. Suba `port/sab/VERSION`.
2. Adicione a entrada no topo de `NOVIDADES` em `sab_help.py`.
3. Atualize `MANUAL` e `CUIDADOS` se algum card mudou.
4. Gere o zip: `cd port && zip -r Sab-vX.Y.Z.zip Sab.sh sab -x "sab/logs/*" "*__pycache__*"`.
5. Copie `port/Sab.sh` para `/roms2/ports/` e `port/sab/` para `/roms2/ports/sab/`.
6. Faça um commit com a tag `vX.Y.Z` e publique a release com o zip.

Teste no PC: `SAB_FAKE=1 python3 sab_ui.py` (dados de mentira). No console, use `SDL_VIDEODRIVER=offscreen SAB_DEMO=...` para tirar prints sem parar o ES.
