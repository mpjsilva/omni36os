# Omni36OS

Sistema **só de ports** para o R36S (RK3326). A base é a imagem dArkOSen_R36_10152026, com Debian trixie em aarch64.

O EmulationStation sai de cena. No boot, sobe direto um launcher gráfico próprio, feito em Python 3 + SDL2 via ctypes, sem dependências extras. Esse launcher abre os ports, verifica o aparelho e reúne as ferramentas do sistema num único visual.

Versão atual: **1.5.0** (`port/omni36os/VERSION`). Testada no PC em modo de teste. **Ainda falta o teste no console.**

## Como sobe

```
boot (logo.bmp = frame 0 de "Carregando")
  → omni36os-launcher.service → launch-direct.sh
    → omni_ui.py (root)  ⇄  port / PortMaster / 351Files
  → power: omni36os-tela desligando|reiniciando
```

- **`launch-direct.sh`** roda em loop. Abre o launcher; ao sair, lê o comando em `/tmp/omni36os-next`, executa e volta ao launcher com `OMNI_RESUME` (o card de origem). Os comandos aceitos são:
  - `test:<port>`
  - `game<TAB>…`
  - `tool:<card>:<caminho>`
- **Telas de sistema** (boas-vindas, carregando, desligando, reiniciando): `/usr/local/bin/omni36os-tela <nome>`.
  - Escreve BGRA 640×480 cru direto na página visível do `/dev/fb0` com `dd`, sem mmap, porque o ffmpeg fbdev falha com EINVAL depois que a GPU usou a tela.
  - Os arquivos ficam em `/opt/omni36os-telas/*.raw`, gerados por `telas/gerar_telas.py`.
- **`perfmax`/`perfnorm`** mostram "Carregando" ao abrir um port.
- **Primeira abertura:** se a trava estiver ligada, aparece a tela de senha (só no boot, não ao voltar de um port). Se o nome do jogador ainda não foi informado, o launcher pergunta.

## Cards (grade 3×3)

| Card | O que tem |
|---|---|
| **Ports** | Abre a biblioteca (lista única dos ports + ficha) |
| **Tela e som** | Duas colunas. Brilho, Volume e Contraste (barras no analógico esquerdo), Tema, Cor do LED, Detalhes da tela, Restaurar áudio (só aparece se algum jogo mexeu no som). Saída fone/alto-falante automática |
| **Rede** | Wi-Fi (ligar/desligar, procurar redes e conectar com senha, redes salvas, desconectar; painel com rede, sinal e IP, via nmcli) e subpágina **Rede pelo cabo USB** |
| **Controles** | Testar o controle (sair segurando SELECT+START), subpágina **Atalhos**, Botão de power, Consertar atalhos (reinicia o `ogage`) |
| **Bateria** | Carga, brilho e modo do processador. Subpágina **Calibrar a bateria** (`/usr/local/etc/battery-cal`) |
| **Desempenho** | No menu, CPU/GPU/memória sempre no mínimo (`relax_clocks`: powersave). Limites de CPU/GPU (valem nos ports), **Memória extra (zram)** 0/256/512/768 MB, Liberar overclock |
| **Armazenamento** | Origem dos jogos (ROMS, ROMS2 ou ROMS e ROMS2), Cartão 1 / Cartão 2 no painel, detalhe do(s) cartão(ões) com teste de velocidade, modo pendrive (+ partição no PC), montar/desmontar pendrive, estado da porta USB, limpar lixo do Mac; por último as ações que reiniciam: verificar e reparar, restaurar boot |
| **Ferramentas** | Arquivos, subpágina **Testar ports** (15 s; causa provável e "Corrigir e testar de novo", `omni_ports_fix.py`), PortMaster, 351Files |
| **Geral** | Nome do jogador, subpáginas **Segurança** e **Backup**, Procurar atualização / Voltar à versão anterior, **Verificar tudo** (resumo dos avisos de todos os cards), **Sobre** (Manual, Cuidados, Novidades, Créditos), Redefinir o sistema (último) |

Regra das páginas: o mais usado primeiro, escolhas antes das ações, o que reinicia ou apaga sempre por último.

**Tela inicial**: os cards; Ports é o primeiro (lista única dos ports + ficha). B volta aos cards. START e SELECT não têm atalho; Energia abre pelo botão de power.

**Todas as listas dão a volta:** para baixo no último item vai ao primeiro, e vice-versa (pulos de página com L1/R1 param na ponta).

**Redefinir o sistema:** apaga nome, trava e tema, desliga o zram e volta processador (Equilibrado, 1296 MHz), GPU (520 MHz), atalhos (FN + X, FN + B, FN + Y, ligados) e botão de power ao padrão; depois pergunta o nome de novo.

**Testar ports — correções conhecidas:** automáticas (com desfazer se o novo teste falhar): script CRLF → LF, permissão de execução, zram 768 MB por falta de memória. Só aviso: runtime do PortMaster, biblioteca, glibc, arquivos do jogo, exFAT sem links, segfault.

**Saudação:** o cabeçalho mostra "Bom dia/Boa tarde/Boa noite, {jogador}!" (5–12 h, 12–18 h, resto). O nome fica em `~ark/.config/omni36os/jogador`.

**Trava por senha:** a senha fica em texto simples em `EASYROMS/senha/senha.txt` (linha `senha: X`), para poder ser recuperada pelo PC. Na tela travada, o botão de power abre Energia.

**Atalhos nos jogos:** `omni_atalho.py` (serviço `omni36os-atalho`) lê o controle e muda arquivos em `/dev/shm`; `hud/omni_hud.so` (LD_PRELOAD pelo `launch-direct.sh`) desenha o contador de FPS, aplica o limite de 30 FPS e salva capturas em `<pasta do jogo>/imagens`. Botões e nomes em `omni_combos.py`: FN + X / FN + B / FN + Y (personalizáveis, sempre FN + tecla) e SELECT + START segurado (fixo, fecha o jogo). O power num jogo congela o jogo e abre Energia com as mesmas opções. Recompilar o HUD: `aarch64-linux-gnu-gcc -O2 -shared -fPIC -nostdlib -fno-builtin -Wno-builtin-declaration-mismatch -o hud/omni_hud.so hud/omni_hud.c`.

## Estrutura

| Arquivo | Função |
|---|---|
| `port/omni36os/launch-direct.sh` | Shell do sistema: loop launcher → port/ferramenta → launcher |
| `port/omni36os/omni_ui.py` | Interface: `CARDS`, `SUBPAGES`, `build_items`, teclado na tela, teste de controle, navegador de arquivos, trava |
| `port/omni36os/gfx.py`, `omni_theme.py`, `assets/` | Desenho SDL2, cores, fontes Poppins e ícones Tabler 96×96 |
| `port/omni36os/omni.py` | Núcleo: leitura e ajuste do sistema, power, logs |
| `port/omni36os/omni_sistema.py` | Senhas (sistema/Samba), jogador, trava, rede USB, calibração da bateria, patch do DTB, operações de arquivo |
| `port/omni36os/omni_checks.py` | Verificações de cada card, resumo do Verificar tudo e ações sugeridas |
| `port/omni36os/omni_ports_fix.py` | Diagnóstico de falhas do Testar ports (`RULES`) e correções com desfazer |
| `port/omni36os/omni_tools.py` | Nativas (atalhos, montar/desmontar pendrive) e apps de tela cheia (PortMaster, 351Files) |
| `port/omni36os/run_tool.sh`, `omni_dialog.py` | Rodam os apps de tela cheia com as janelas do Omni36OS |
| `port/omni36os/omni_backup.py` | Exporta e importa configurações por módulo (`.tar.gz`) |
| `port/omni36os/omni_help.py` | Manual, cuidados, créditos e `NOVIDADES` (só a versão atual; histórico em `NOVIDADES.md`) |
| `port/omni36os/ports.py`, `port_test.sh` | Lista, histórico e teste de ports |
| `port/omni36os/power_button.py` | Menu do botão de power |
| `port/omni36os/usb_pendrive.sh` | Gadget mass storage (alterna `dr_mode` do DTB) |
| `port/omni36os/omni_games.py` | Leitura da biblioteca (tela inicial) |
| `port/omni36os/test_ssh.sh` | Teste por SSH da fase ES (legado) |

Fora desta pasta (`~/Apps/Omni36OS`):

| Caminho | Função |
|---|---|
| `dArkOSen_R36_10152026/overlay/` | Arquivos do sistema: `omni36os-launcher.service`, `omni36os-tela-saida.service`, drop-ins de `welcome-message` e `boot_volume`, `omni36os-tela`, `/opt/omni36os-telas`, `/etc/omni36os/launcher.conf` |
| `telas/gerar_telas.py` | Gera as telas `.raw`/`.png` e o `logo.bmp` do BOOT |
| `scripts/` | `instalar-launcher.sh`, `trocar-shell.sh` (launcher ↔ ES, reversível), `aplicar-telas-e-marca.sh`, gravação do cartão, `validar-implementacao.sh` |

## Cópia do cartão no PC (poupa o SD)

As 3 partições ficam copiadas em `~/Apps/Omni36OS/cartao/{BOOT,ROOTFS,EASYROMS}` (ROOTFS com dono, permissões e links; sem xattrs SELinux). **Toda alteração é feita na cópia**; o SD só recebe o que mudou, quando o teste no console for pedido.

```bash
scripts/cartao.sh launcher   # instala port/omni36os na cópia (ROOTFS/opt/omni36os)
scripts/cartao.sh conferir   # mostra o que seria gravado no SD, sem gravar
scripts/cartao.sh enviar     # grava no SD só a diferença (rsync)
scripts/cartao.sh puxar      # traz para a cópia o que mudou no SD (depois de usar no console)
```

Partições: p1 `BOOT` (FAT), p2 `ROOTFS` (btrfs), p3 `EASYROMS` (exFAT, vira `/roms`).

## Testar no PC

```bash
cd port/omni36os
OMNI_FAKE=1 OMNI_WINDOWED=1 python3 omni_ui.py
```

**Prints automáticos:**
- Use `OMNI_SHOT_DIR=<pasta>` com `OMNI_DEMO="wait6000,start,right,a,shot,quit"`.
- Comandos extras do demo: `pad:N` (aperta) / `pad:-N` (solta) e `axis:K=V`.
- O `wait6000` (às vezes `wait8000`) é necessário para passar do carregamento; a tela inicial é a biblioteca, `start` abre os cards e `ok` confirma.
- Sem janela: `SDL_VIDEODRIVER=offscreen` (é o que os testes usam). `OMNI_DEMO_STEP=<s>` encurta o intervalo entre passos (padrão 0,45).

**Variáveis do modo de teste:**
- `OMNI_JOGADOR=<nome>`
- `OMNI_TRAVA=1`
- `OMNI_TRAVA_SENHA` (padrão `1234`)
- `OMNI_RESUME=testar` + `OMNI_FAKE_TESTE=falhou|ok`: mostra o resultado de um teste de port
- Cada card tem dados de teste próprios (o "Detalhe dos cartões" de Armazenamento mostra o aviso de cartão sem marca)

**Teclas do simulador** (Num Lock ligado): setas = direcional, 2 = A, 1 = B, Enter = START, Shift direito = SELECT, 5/4 = X/Y, 6/3 = L1/R1, 0 = botão de power, 7/9 = analógico esquerdo para os lados, 8 = FN (só ao gravar atalho). `OMNI_JOGO=1` simula o menu Energia por cima de um jogo. Mouse: clique esquerdo = A, direito = B, roda = cima/baixo. + / - do teclado numérico = botões de volume.

Ficha dos ports (`omni_meta.py`). Primeiro a pasta `info` do port (`ports/<pasta do port>/info/`; a pasta é a de mesmo nome do .sh, a que o .sh cita ou a que começa igual): `info.json` com `nome`, `descricao`, `estudio`, `lancamento`, `generos` (texto ou lista), `porter`, `pronto`, `capa` (arquivo na pasta); todos opcionais, JSON com erro é ignorado. Reservas: 1º .txt = descrição, 1ª imagem = capa, depois `ports/images/<nome>-image.png` do ES. Manda sobre a internet. Depois 2 camadas: 1) catálogo do PortMaster (ports.json, acha pelo .sh; título, descrição, porter, gêneros, se precisa dos arquivos do jogo, screenshot; índice enxuto renovado a cada 7 dias); 2) loja Steam, sem chave, só com nome igual. Cada camada completa a anterior; descrição em pt-BR quando alguma tiver; capa Steam > PortMaster. Cache em `~ark/.config/omni36os/steam/` (no simulador, `~/.cache/omni36os-steam`).

Prints de cada rodada ficam em `imagens/runN`.

### Testes automáticos

`python3 tests/run.py` (cerca de 30 s). Rodam sozinhos antes de cada commit pelo gancho `.githooks/pre-commit`; num clone novo, ative uma vez com `git config core.hooksPath .githooks`. Cobrem gravação atômica, atalhos, botão de power (inclusive o aviso velho que fazia suspender), bateria crítica, atualização com volta automática (pacote quebrado, pacote que tenta gravar fora da pasta, 3 tentativas e volta), backup, sintaxe de todos os `.sh`, pyflakes, VERSION = NOVIDADES e o simulador sem janela percorrendo todos os cards.

## O que o Omni36OS mexe no sistema

- **CPU, GPU, memória e gamma:** `/etc/cpu-settings.conf`, `gpu-settings.conf`, `dmc-settings.conf`, `gamma-settings.conf`, os mesmos arquivos que os serviços do dArkOSen aplicam no boot.
- **Telas:**
  - `perfnorm`/`perfmax` mostram "Carregando".
  - `fix_power_led` e `batt_life_warning.py` controlam a cor do LED.
- **DTB:**
  - `/boot/rk3326-r36s-linux.dtb` muda no modo pendrive (`dr_mode`) e no overclock.
  - Antes, o launcher guarda uma cópia `.omni36os.bak` ou `.host-bak`.
- **Bateria:** `/usr/local/etc/battery-cal/`, `battery-cal-daemon.sh` e `battery-cal.service` (sem depender do ES).
- **Senhas:** sistema e Samba, via `chpasswd`/`smbpasswd`. A da trava fica em `/roms/senha/senha.txt`.
- **Configurações:** `~ark/.config/omni36os/` (jogador e outras).
- **Testes de ports:** `port/omni36os/logs/` guarda os relatórios (com a seção "Diagnóstico do Omni36OS") e `resultados.txt`. Correção pendente em `~ark/.config/omni36os/correcao_pendente.json`.
- **zram:** `/etc/zram.conf` e o `zram_autostart.service` (desligado por padrão). `/etc/sysctl.d/90-omni36os.conf`: swappiness 100, page-cluster 0, vfs_cache_pressure 50, min_free_kbytes 16384.
- **Ao abrir um port** (`launch-direct.sh`, `port_begin`/`port_end`): limpa o cache, compacta a memória, CPU/GPU/DMC em performance, ionice alto, pausa `fn-menu-watcher`, `es-status-daemon` e (sem ninguém conectado) Samba e filebrowser; devolve tudo ao fechar.
- **Removido do cartão (sistema mais leve, −3,1 GB):** EmulationStation, RetroArch, 25 emuladores, Kodi, DinguxCommander e suas configurações. O `es_systems.cfg` ficou (a biblioteca lê). Não há mais volta ao ES pelo `trocar-shell.sh`.
- **Serviços desligados no boot:** `es-status-daemon`, `fn-menu-watcher`, `remote-autostart`, `cron` e os timers `apt-daily*`, `dpkg-db-backup`, `e2scrub_all`, `xfs_scrub_all`. O **SSH** sobe direto.
- **Abertura e atualização:** `omni36os-launcher.service` roda `/usr/local/bin/omni36os-start` (original em `port/omni36os/omni36os-start`), que conta as aberturas depois de uma atualização e volta a `/opt/omni36os.prev` se a nova não chegar ao menu em 3 tentativas. Estado em `/var/lib/omni36os-update/`. Quedas do launcher ficam em `/var/log/omni36os-crash.log`. As duas unidades têm `StartLimitIntervalSec=0` (o systemd nunca desiste).
- **Bateria crítica:** o `omni36os-atalho` avisa em 30%, pede para salvar e fechar em 15% e, em 10% ou abaixo de 3,35 V (duas leituras seguidas, sem carregador), fecha o jogo com SIGTERM, grava tudo e desliga.
- **Verificar o cartão:** o `/boot/recovery.sh` é a cópia do `Scan_SD*.sh` do dArkOSen sem o `umount -l` (fsck numa partição ainda em uso pode estragá-la).
- **Wi-Fi:** liga e desliga só o rádio (`rfkill` + `nmcli`). O `wifi_disable.sh` do dArkOSen não é usado: ele faz blacklist, mascara o `wpa_supplicant` e reinicia o controlador USB.
- **`emulationstation.service` mascarado** (→ `/dev/null`): o PortMaster roda `systemctl restart emulationstation` depois de instalar um port, e o conflito com o serviço do launcher derrubaria o launcher.

## Lançar uma versão

1. Suba `VERSION`. Troque `NOVIDADES` (`omni_help.py`) pela entrada da versão nova (o console mostra só ela) e adicione a mesma entrada no topo do `NOVIDADES.md` (histórico completo).
2. Atualize o `MANUAL` e os `CUIDADOS` se algum card mudou.
3. Teste no PC com prints e instale no cartão (seção acima).
4. Faça o boot de teste no console: abrir, usar, voltar com B; num port, FN + X/B/Y, SELECT + START e o power no meio.
5. Commit `vX.Y.Z: resumo` (os testes rodam sozinhos) e tag `omni-vX.Y.Z`.
6. `git push --tags`: o "Procurar atualização" dos consoles só enxerga tags `omni-vX.Y.Z` publicadas no GitHub.

## Pendências

- **Teste no console** de tudo (nada desta rodada rodou no aparelho):
  - boot sem ES e com os serviços desligados; SSH subindo sozinho; `systemd-analyze blame | head -20; free -m; swapon; systemctl --failed`;
  - nome e saudação, trava, Segurança, Samba, Zerar o sistema;
  - zram no Desempenho; abrir um port e ver Samba/SSH voltarem;
  - PortMaster: instalar um port, fechar, o launcher volta e mostra o port;
  - Testar ports com um port que falhe (diagnóstico e "Corrigir e testar de novo");
  - teste do controle, arquivos, rede USB, DTB, calibração, telas "Carregando" e "Desligando".
- **Testar no console:** HUD (Mali, códigos de botão do DTB), captura em `<pasta do jogo>/imagens`, menu Energia por cima do jogo, DHCP da rede USB.
- Depois do teste, apagar os scripts antigos em `/opt/system` (Change Password, Controller Tester, Battery Calibration, USB Network Mode, dtb patcher).
- Prints em `docs/prints/` são da fase ES. A biblioteca ainda lê `es_systems.cfg` e `gamelist.xml` (só dados; o ES não existe mais).
- Os botões que só existiam no card Jogos (Atualizar a lista, jogos repetidos, BIOS) ficaram sem acesso.
- `scripts/enviar.sh IP`: instalar no console pela rede (rsync por SSH), sem trocar o cartão.
- **Próximos passos de desempenho:** cartão (`noatime`, btrfs `compress=zstd:1`, tmpfs, escalonador), kernel (`dirty_ratio`, afinidade de CPU), ajustes por port (gl4es, resolução interna, perfil por port).
- **Plano:** DTB multi-placa com detecção automática.
- A tela de boas-vindas ainda diz "Jogador": regerar com o nome.

## Ideias: temas além das cores (para discutir)

Hoje o tema é só a paleta (escuro/claro). Um tema completo poderia trocar:

- **Layout:** grade 3×3 (atual), carrossel horizontal com o card central grande, ou lista vertical. Na biblioteca: lista com capa, grade de capas ou capa em tela cheia.
- **Tipografia:** fonte própria (pixelada, arredondada, monoespaçada) e tamanhos (tema "fácil de ler").
- **Ícones:** conjunto próprio (pixel art ampliada sem suavizar, preenchidos, linha fina), ícone por sistema/port.
- **Formas:** cantos arredondados, retos ou chanfrados; vidro fosco ou contorno grosso; seleção por destaque, moldura, seta ou "mão" de RPG.
- **Fundo:** imagem, gradiente animado, partículas, parallax com o direcional; fundo pela hora do dia (combina com a saudação), pela bateria ou temperatura.
- **Movimento:** transições (deslizar, desvanecer, zoom), animação da seleção, opção "sem animação" para poupar bateria.
- **Som:** sons de navegar/confirmar/voltar por tema e música baixinha no menu (precisa de SDL_mixer ou ALSA).
- **Telas do sistema:** boot, carregando, desligando e bateria fraca geradas pelo `gerar_telas.py` a partir do tema.
- **Personalidade:** saudações e mensagens no tom do tema ("Bem-vindo de volta, aventureiro!").

Exemplos: **Omni** (atual), **Retrô 16 bits** (lista, pixel art, scanlines, bipes), **Console de sala** (carrossel, arte do jogo no fundo), **RPG** (janelas com borda, cursor de mão), **Terminal** (verde no preto, monoespaçada), **Fácil** (fonte grande, alto contraste).

Como seria por dentro: `temas/<nome>/tema.json` (cores, fonte, cantos, layout, animações, sons) com `fontes/`, `icones/`, `sons/`, `fundos/`; o `omni_ui.py` passa a desenhar a tela inicial e a biblioteca por "layouts" escolhidos no tema; temas podem ficar em `/roms/temas` para instalar pelo PC.

Limites: tela 640×480, GPU fraca e 1 GB de RAM (efeitos leves e modo sem animação), som exige biblioteca nova, fontes e imagens só com licença livre.

Ordem sugerida: (1) fonte, ícones e cantos; (2) fundo, inclusive por hora do dia; (3) sons; (4) layouts lista e carrossel; (5) telas de boot geradas pelo tema.
