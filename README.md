# Sab: assistente do R36S

Port para o R36S com dArkOSen que verifica e ajusta o aparelho com um menu gráfico (Python 3 + SDL2 via ctypes, sem dependências extras). Não usa IA nem internet: são regras fixas em `sab_checks.py` e ações em `sab.py`.

## Estrutura

| Arquivo | Função |
|---|---|
| `port/Sab.sh` | Launcher em Ports. Não para o ES. Lê `/tmp/sab-next`: `test:<port>` roda o teste e reabre a Sab (`SAB_RESUME=testar`); `/opt/system/...` abre a ferramenta do dArkOSen |
| `port/sab/sab_ui.py` | Interface: cards, páginas, tela de carregamento, leitor de textos |
| `port/sab/gfx.py` | Desenho com SDL2: caches de geometria, texto, sprites e camadas |
| `port/sab/sab.py` | Ferramentas que leem e mudam o sistema (`python3 sab.py` lista todas) |
| `port/sab/sab_checks.py` | Verificações de cada card e ações sugeridas |
| `port/sab/sab_help.py` | Manual, cuidados, créditos e histórico de versões (NOVIDADES) |
| `port/sab/port_test.sh` | Teste de port: roda por 15 s; se o port fechar antes, gera o relatório em `sab/logs/<port>/` |
| `port/sab/usb_pendrive.sh` | Modo pendrive (gadget mass storage), instalado em `~/usb-disco.sh` |
| `port/sab/VERSION` | Versão instalada, mostrada no card Ajuda |

## O que a Sab mexe no sistema

- `/etc/cpu-settings.conf` (GOV, FREQ), `/etc/gpu-settings.conf`, `/etc/dmc-settings.conf` e `/etc/gamma-settings.conf`: os mesmos arquivos que os serviços do dArkOSen aplicam no boot.
- `/usr/local/bin/perfnorm`, linha do governador: passa a ler o modo de `/etc/cpu-settings.conf`. O backup fica em `perfnorm.sab-bak`.
- `/usr/local/bin/fix_power_led` e `batt_life_warning.py`: cor do LED, copiadas das variantes `.red` e `.green`.
- `/boot/recovery.sh`: só ao pedir a verificação do cartão. O script do dArkOSen roda no boot e se apaga ao terminar.
- `port/sab/logs/`: relatórios de testes que falharam e `resultados.txt` (último resultado de cada port).
- `/boot/rk3326-r36s-linux.dtb`: só no modo pendrive. O backup fica em `.host-bak`.

## Lançar uma versão

1. Suba `port/sab/VERSION`.
2. Adicione a entrada no topo de `NOVIDADES` em `sab_help.py`.
3. Atualize `MANUAL` e `CUIDADOS` se algum card mudou.
4. Copie `port/Sab.sh` para `/roms2/ports/` e `port/sab/` para `/roms2/ports/sab/`.
5. Faça um commit com a tag `vX.Y.Z`.

Teste no PC: `SAB_FAKE=1 python3 sab_ui.py` (dados de mentira). No console, use `SDL_VIDEODRIVER=offscreen SAB_DEMO=...` para tirar prints sem parar o ES.
