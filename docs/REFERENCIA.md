# Omni36OS — referência do projeto (para retomar o trabalho)

Documento de entrada para quem (pessoa ou agente) vai continuar o projeto. Diz onde está cada coisa,
como se trabalha e o que não pode quebrar. Detalhes históricos de implementação: `docs/DESENVOLVIMENTO.md`.
O que mudou em cada versão: `NOVIDADES.md` (e `omni_help.NOVIDADES`, que é o que o console mostra).

## O que é

Sistema **só de ports** para o R36S (Rockchip RK3326, 1 GB, tela 640×480), em português, feito sobre o
**dArkOSen** (djparentx), que vem do dArkOS e do ArkOS (christianhaitian). O EmulationStation e o
RetroArch saem; no lugar entra um launcher próprio em Python + SDL2 (via ctypes, sem pygame).
Repositório público: https://github.com/mpjsilva/omni36os (GPL-3.0). Autor dos commits: `mpjsilva`.

## Pastas no PC (pirulito)

| Caminho | O que é |
|---|---|
| `~/Apps/Omni36OS/omni36os` | **O repositório.** Launcher, gerador da imagem, testes, docs |
| `~/Apps/Omni36OS/cartao/{BOOT,ROOTFS,EASYROMS}` | Cópia do cartão do console. Arquivos de sistema (fora do launcher) são editados **aqui** (ROOTFS é do root: `SUDO_ASKPASS=/usr/bin/ksshaskpass sudo -A`) |
| `~/Apps/Omni36OS/scripts/cartao.sh` | `cartao.sh launcher` copia o launcher do repositório para a cópia do cartão; `cartao.sh enviar` grava a diferença no SD (só quando pedido) |
| `~/Apps/Omni36OS/dArkOSen_R36_10152026.img` | Imagem original do dArkOSen: base da imagem do Omni36OS (nunca é alterada) |
| `~/Apps/Omni36OS/runtimes` | 14 runtimes do PortMaster (604 MB) que entram na imagem (Mono, gmtoolkit, FRT 3.x–4.x, Weston, Mesa) |
| `~/Apps/Omni36OS/telas` | Gerador das telas de boot/boas-vindas/desligar (`telas/out` entra na imagem) |
| `~/Apps/Omni36OS/output` | Imagens geradas (`Omni36OS-X.Y.Z.img.xz`), logs da geração e notas de release |
| `~/Apps/Omni36OS/prints` | Capturas que o usuário quer mostrar (abrir a mais recente) |
| `~/.cache/omni36os-steam` | Cache de capas/descrições do simulador |

## Pastas no repositório

| Caminho | O que é |
|---|---|
| `port/omni36os/` | O launcher inteiro (vai para `/opt/omni36os` no console) |
| `port/omni36os/VERSION` | Versão em uso |
| `imagem/gerar-imagem.sh` | Gera a imagem de distribuição (`sudo`). A lista `SIS=(...)` diz quais arquivos de sistema saem da cópia do cartão |
| `tests/run.py` | 33 testes (o hook de commit roda todos) |
| `docs/prints/` | Capturas do README |
| `NOVIDADES.md`, `README.md`, `LICENSE` | Histórico, apresentação, GPL-3.0 |

## Módulos do launcher (`port/omni36os`)

| Arquivo | Papel |
|---|---|
| `omni_ui.py` | Interface inteira: cards, páginas, biblioteca, apps (Músicas, Vídeos, Notas, Arquivos), pílula de estado, modais, leitor, teclado |
| `gfx.py` | Desenho com SDL2 via ctypes (formas, texto Poppins, ícones Tabler, texturas) |
| `omni.py` | Leituras e ajustes do aparelho (bateria, CPU/GPU, brilho, som, LED, energia, pendrive) |
| `omni_sistema.py` | Ferramentas do sistema reescritas (Wi-Fi, rede USB, calibração de bateria, DTB, segurança, adaptador Realtek preso) |
| `omni_checks.py` | Diagnóstico de cada card por regras fixas (níveis ok/info/aviso/problema) |
| `omni_games.py`, `ports.py` | Lista de ports (dois cartões), gamelist, comando de lançamento, histórico |
| `omni_meta.py` | Ficha do port: pasta info → PortMaster → Steam → Wikipédia → DuckDuckGo; cache em `~/.config/omni36os/steam`. Força IPv4 no `getaddrinfo` (roteador sem resposta AAAA) |
| `omni_update.py` | Atualização pelo GitHub (maior tag `omni-vX.Y.Z`), com volta automática se a nova não abrir |
| `omni_painel.py` | Tela certa no primeiro boot (ver abaixo) |
| `omni_atalho.py` | Serviço root: atalhos FN nos jogos, contador de FPS, guarda da bateria (avisos 30/15%, desliga em 10%) |
| `power_button.py` | Botão de power: menu de energia, inclusive por cima de jogo/ferramenta congelados (SIGSTOP) |
| `launch-direct.sh` | Laço launcher → jogo/ferramenta → launcher (o `omni_ui.py` grava o pedido em `/tmp/omni36os-next`). Monta o cartão 2 e, durante um port do cartão 2, faz bind de `/roms2/ports` em `/roms/ports` |
| `run_tool.sh`, `omni_dialog.py` | Ferramentas de `/opt/system` com as janelas do Omni36OS no lugar de dialog/msgbox/osk |
| `omni_teclado.py` | Teclado na tela (estilo Android), usado no launcher e nas janelas |
| `omni_musica.py`, `omni_video.py` | Tocador de música (SDL_mixer) e de vídeo (ffmpeg em pipe) |
| `omni_help.py` | Manual, cuidados, créditos e `NOVIDADES` |
| `port_test.sh`, `omni_ports_fix.py` | Testar ports e correções conhecidas |
| `usb_pendrive.sh` | Modo pendrive da porta OTG (vira `/home/ark/usb-disco.sh`) |

Serviços no console: `omni36os-launcher` (o launcher), `omni36os-atalho`, `omni36os-painel` (tela certa),
`omni36os-turbo`, `omni36os-boas-vindas`, `omni36os-tela-saida`, `omni36os-hora`, `omni36os-wifi-boot`.

## Console de teste

- R36S original, painel R36S-V21 2024-12-18 (2529). Wi-Fi por adaptador USB Realtek RTL8821CU na porta OTG.
- SSH: `omni@192.168.1.11` com a chave `K="/home/jamersonferreira/Apps/recomp/DAYTONA USA/.ssh/daytona_ed25519"`
  (`omni` tem o mesmo uid 1000 do `ark`; sudo sem senha). Cartão gravado do zero não tem a chave: o usuário
  roda `ssh-copy-id` (o agente nunca digita senha).
- Às vezes o console está fora da rede (Wi-Fi não subiu, rede USB, cartão no leitor).

## Rotina de cada mudança

1. Editar no repositório (ou na cópia do cartão, se for arquivo de sistema, e pôr o caminho na lista `SIS`).
2. `python3 tests/run.py` (o commit roda de novo).
3. Versão nova: `port/omni36os/VERSION`, tupla no topo de `omni_help.NOVIDADES`, seção `## X.Y.Z (dd/mm/aaaa)` no topo de `NOVIDADES.md`.
4. Instalar no console:
   ```
   rsync -e "ssh -i '$K'" -a --delete --exclude __pycache__ --exclude imagens --exclude logs \
     --rsync-path="sudo rsync" port/omni36os/ omni@192.168.1.11:/opt/omni36os/
   ssh -i "$K" omni@192.168.1.11 'sudo chown -R ark:ark /opt/omni36os; sudo systemctl restart omni36os-launcher'
   ```
5. `cd ~/Apps/Omni36OS && scripts/cartao.sh launcher`.
6. Commit `git -c user.name=mpjsilva -c user.email=mpjsilvaa@gmail.com commit` e `git tag omni-vX.Y.Z`.
7. Abrir o simulador: `cd port/omni36os; OMNI_FAKE=1 OMNI_WINDOWED=1 OMNI_JOGADOR=Jamerson python3 omni_ui.py` (teclas do numpad).
   Capturas automáticas: `OMNI_DEMO="wait2500,ok,shot,..." OMNI_SHOT_DIR=...` (gera PPM). Guardar em `imagens/runN`.
8. **Push só quando pedido**: cada tag publicada vira atualização em todos os consoles ("Procurar atualização").

O que a atualização pelo GitHub troca: **só `/opt/omni36os`**. Arquivos de sistema (serviços, scripts em
`/usr/local/bin`, DTB) só chegam por imagem nova ou pela cópia do cartão.

## Imagem e release

```
sudo imagem/gerar-imagem.sh        # -> ~/Apps/Omni36OS/output/Omni36OS-<VERSION>.img.xz (+ .sha256), ~15 min
```
- Parte da imagem original do dArkOSen, tira ES/RetroArch/emuladores, refaz o `roms.tar` (ports, PortMaster,
  backup e os runtimes), instala o launcher e os arquivos `SIS`, faz fstrim e comprime com xz.
- O GitHub aceita no máximo 2 GB por arquivo: `split -b 1400M` → `.001`, `.002`, `.003`; as notas explicam como juntar
  (modelo em `output/release-1.15.4/notas.md`). Release: `gh release create omni-vX.Y.Z <partes> <sha256> --notes-file ...`.

## Primeiro boot e tela certa (`omni_painel.py`)

- Roda em `omni36os-painel.service` (cedo: só precisa da `/boot`), quando existe `/boot/firstboot.sh` ou `/boot/omni36os-tela/testar`.
- Lista as telas 640×480 do catálogo `/boot/dtb/{r36s,clone,soysauce}/*/` (uma por sequência de início), com a tela atual primeiro.
- **Cada teste monta o DTB original com só as propriedades da tela trocadas** (`fdtput`). Nunca copia `boot.ini`
  nem DTB do u-boot do catálogo — a pasta de um clone já travou o boot com "dtb load fail".
- Pergunta "Está vendo esta tela?" por 10 s, com ding-dong no alto-falante e o LED piscando; confirmação = arpejo.
  Sem resposta: próxima tela e reinicia (~29 s por tela; 12 telas ≈ 5 min). Fim da lista: volta os originais.
  Limite de reinícios (lista + 3). Estado e log em `/boot/omni36os-tela/`. `/boot/omni36os-tela/espera` muda o tempo (medições).

## Pegadinhas conhecidas

- PortMaster: o `control.txt` usa `/roms2` só se o `/etc/fstab` citar `roms2`; o Omni36OS monta o cartão 2 sozinho,
  por isso o bind de `/roms2/ports` em `/roms/ports` durante um port do cartão 2.
- Runtimes do PortMaster: ports antigos/independentes (ex.: TMNT/Mono) só montam `/roms/tools/PortMaster/libs/<runtime>.squashfs`
  sem `runtime_check`. O `port_deps.py` roda antes de cada port (launch-direct.sh: Jogos e Testar ports), acha os
  runtimes citados no `.sh` e copia do cartão 2 (`/roms2/tools/PortMaster/libs`) ou baixa (URL/md5 do `config/runtimes.json`).
- Adaptador Realtek liga como disco (`0bda:1a2b`) e o udev troca para Wi-Fi (`0bda:c820`); a troca às vezes se perde
  → `omni_sistema.wifi_dongle_fix()` ao abrir o menu. O driver deixa a interface "up" sem rede: conectado = carrier + IPv4.
- Bluetooth do adaptador (hci0) não funciona: firmware não carrega (btusb e rtk_btusb disputam); serviço desligado.
- Alto-falante (rk817): o amplificador leva ~300 ms para ligar; sons curtos precisam de silêncio na frente.
  Controles: `Playback Path` (OFF/SPK/HP/SPK_HP) e `Playback Volume` (0–237).
- ffprobe do dArkOSen imprime linhas da librga antes do JSON: ler a partir do primeiro "{".
- GitHub limita arquivo de release a 2 GB.
- Nunca `rm -f $X/*` sem guarda: usar `"${X:?}"`.

## Convenções

- Tudo em pt-BR; textos de interface começam com maiúscula (inclusive "4 Jogos").
- Identidade visual: cards e páginas com vidro, pílula de estado no topo, ícones Tabler, fonte Poppins.
- Mostrar no simulador antes de mexer no console/imagem/cartão quando a mudança for visual e o usuário pedir.
