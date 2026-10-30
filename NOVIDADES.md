# Novidades do Omni36OS

Histórico completo. Dentro do console (Geral > Sobre > Novidades) aparece só a versão em uso.

## 1.11.9 (30/10/2026)

- Desbloquear overclock: com a trava por senha ligada, depois do aviso (10 s + 5 toques) o teclado pede a senha da trava; senha errada mantém o overclock bloqueado.

## 1.11.8 (30/10/2026)

- Overclock: trava real (`/etc/omni36os/overclock`). Bloqueado, `cpu_freqs`/`gpu_freqs` só oferecem até 1296/520 MHz, `set_cpu_max`/`set_gpu_max` recusam acima e `apply_limits` corta qualquer configuração antiga. Desbloquear (aviso + 5 toques) cria a marca e, se o DTB não tiver as frequências, acrescenta; Bloquear tira a marca e volta os limites ao padrão.
- Boot: `cpu-governor` e `gpu-freq` não mexem em nada enquanto o `omni36os-turbo` está ativo; os limites de Desempenho entram com o menu pronto (antes o `gpu-freq` tirava a GPU do máximo no meio do boot).

## 1.11.7 (30/10/2026)

- Ferramentas > Busca automática (Ligada/Desligada, `~/.config/omni36os/busca`).
- Biblioteca: "Buscando imagem e descrição...", "Buscando a descrição..." (já tem capa) ou "Buscando imagem..." na capa (já tem descrição). Busca feita sem resultado não se repete ("Descrição não encontrada."); com a busca desligada, o texto diz onde religar.
- Nada é buscado no menu por cima de um jogo pausado (`OMNI_HUB=jogo`); a capa é gravada inteira ou nada (o launcher fecha ao abrir um port).

## 1.11.6 (30/10/2026)

- Biblioteca: a busca de capas e descrições só dispara com o Wi-Fi conectado (`operstate` up), não apenas com o adaptador presente. Sem conexão, mostra "Sem descrição: ligue o Wi-Fi para buscar." e não marca o jogo como tentado.

## 1.11.5 (30/10/2026)

- Biblioteca: "Buscando a descrição...", "Sem descrição: ligue o Wi-Fi para buscar." e "Descrição não encontrada." no lugar dos textos com "ficha" (agora são 4 fontes, não só PortMaster e Steam).

## 1.11.4 (30/10/2026)

- Fichas dos ports: Wikipédia como terceira camada (antes do DuckDuckGo). Busca na inglesa e só aceita a página com o nome do jogo (ou da série); a descrição vem da mesma página em português pelo link de idioma, com ano e imagem quando livres. Fichas incompletas são buscadas de novo uma vez.

## 1.11.3 (30/10/2026)

- Fichas dos ports (`omni_meta.py`): DuckDuckGo como terceira camada, só quando PortMaster e Steam não trazem capa ou descrição. Capa pela busca de imagens (jpg/png, preferindo larga); descrição pela resposta instantânea, quando existe. Fichas incompletas antigas são buscadas de novo uma vez.

## 1.11.2 (30/10/2026)

- Biblioteca só de ports (`omni_games.py`): lê apenas `/roms/ports` e `/roms2/ports` (conforme Origem dos jogos), só os `.sh` da raiz. Os outros sistemas do es_systems não são mais varridos; o cache antigo (versão 2) é descartado e refeito.

## 1.11.1 (30/10/2026)

- Controles: "Botões A e B" e "Botões X e Y" viram uma opção só, Inverter botões (Ligado/Desligado), que troca os dois pares juntos.

## 1.11.0 (30/10/2026)

- Boot: `omni36os-turbo` põe CPU, GPU e memória no máximo do início do boot até o menu ficar pronto (~27,4 s → ~24,3 s) e também ao desligar/reiniciar; o launcher volta ao mínimo quando termina de montar as páginas.
- Boot sem tela preta: logo redesenhado no começo do initramfs (`imagem/initrd-logo.sh`), boas-vindas sem esperar o cartão 2 (`omni36os-boas-vindas.service`) e o primeiro quadro do launcher já é a boas-vindas. Abertura igual à tela do boot, com pílula do tamanho do nome; telas sem barra falsa, reticências ou raio.
- Wi-Fi USB Realtek no boot (`omni36os-wifi-boot`, `usbcore.old_scheme_first=1`). Data, hora e fuso automáticos com a internet (`omni36os-hora`). Volume salvo entre reinícios.
- Tela e som com painel de brilho, contraste e volume. Troca de A/B e X/Y. FN + Y no menu grava em `/roms/imagens`; visualizador de imagens no Arquivos (sai o 351Files). Cartão 2 montado em `/roms2`.
- Power sempre com o menu de energia; FN + power desliga com segurança. Apelido omni/omni (SSH, SFTP e navegador de arquivos). Serviços remotos só com rede; Serviços remotos vira Ligados/Desligados.
- Volta rápida dos ports (estado na RAM). Legendas com arte dos botões, alinhamento ao pixel, ícones distintos, MUTED/FAINT mais claros. Rede refeita quando o Wi-Fi conecta (sem alerta fantasma).

## 1.10.0 (30/10/2026)

- Tela certa no primeiro boot (`omni_painel.py`, serviço `omni36os-painel`): antes da expansão da imagem, o Omni36OS testa as telas do catálogo do dArkOSen, uma por boot. O hardware (RAM, memória interna) escolhe a ordem (original ou clone, as mais comuns primeiro); a tela que acender pergunta "Está vendo esta tela?" e qualquer botão confirma. Sem toque em 20 s, instala a próxima e reinicia; acabou a lista, volta os originais. Refazer: arquivo `omni36os-tela/testar` na BOOT.
- Armazenamento: Detalhe do cartão (marca, espaço do cartão inteiro e velocidade numa opção), Cartão 1 / Cartão 2, Origem dos jogos, Partição no PC só ROMS/ROMS2; estado do pendrive na dica de Montar/Desmontar.
- Cartão sem marca deixa de ser alerta (aparece só no Detalhe). Créditos sem a seção Origem e com o QR do repositório.

## 1.9.0 (29/10/2026)

- Menu reorganizado, no mesmo desenho: cada coisa no card do seu assunto. Novos cards Tela e som, Rede, Controles, Armazenamento e Geral; saem Sistema, USB, Cartões SD, Verificar e Ajuda.
- Rede junta o Wi-Fi e a rede pelo cabo USB. Controles junta o teste do controle, os atalhos e o botão de power. Armazenamento junta cartões e pendrive.
- Geral, como nos Ajustes do iPhone: nome, segurança, backup, atualização, Verificar tudo, Sobre (manual, cuidados, novidades e créditos) e, por último, Redefinir.
- Em todas as páginas, o que reinicia ou apaga fica por último.
- No menu, processador, GPU e memória ficam sempre no mínimo; os limites valem nos ports.

## 1.8.1 (29/10/2026)

- Bateria: como a porcentagem do R36S não é confiável, os limites subiram. Em 30% o Omni36OS sugere conectar o carregador, em 15% sugere salvar o progresso e, em 10%, salva tudo e desliga com segurança. Os avisos aparecem num alerta com OK, como no iPhone.

## 1.8.0 (29/10/2026)

- Ajuda > Procurar atualização: baixa a versão nova do GitHub, confere tudo antes de instalar e guarda a de agora. Se a nova não abrir em 3 tentativas, a anterior volta sozinha; "Voltar à versão anterior" faz o mesmo a pedido.
- Bateria no fim: aviso em 5% e, em 2%, o jogo é fechado com tempo de salvar e o console desliga com segurança, em vez de apagar de repente.
- Wi-Fi: ligar e desligar mexem só no rádio, sem derrubar o modo pendrive nem a rede USB.
- Verificar e reparar os jogos não repara mais uma partição que não desmontou de verdade (o reparo nela podia estragar o cartão).
- Testes automáticos rodam antes de cada mudança no código do Omni36OS.

## 1.7.0 (29/10/2026)

- Sistema > Wi-Fi: ligar e desligar, procurar redes e conectar com senha, redes salvas (conectar ou esquecer) e desconectar. O painel mostra a rede, o sinal e o IP do console.
- Botão de power: o menu de energia voltou a abrir (o toque suspendia o console). Com o menu já aberto, outro toque desliga com segurança.
- Boas-vindas com o seu nome: a tela do boot e a de carregamento dizem "Bem-vindo" com o nome do jogador, sem barra de progresso.
- Mais resistente: um erro numa tela não fecha mais o Omni36OS; se ele cair, volta sozinho e o erro fica em /var/log/omni36os-crash.log. Configurações são gravadas sem risco de ficarem pela metade se a bateria acabar.
- Atalhos e modo pendrive se recuperam sozinhos: o serviço espera o controle no boot, e uma queda no modo pendrive devolve a partição e o Omni36OS.
- Ports: o teclado virtual do PortMaster (gptokeyb) é fechado quando o jogo sai, e um port não deixa mais as variáveis dele para o próximo.
- USB: Montar e Desmontar pendrive viraram um botão só, que muda conforme o pendrive está montado.
- Ficha dos ports só com PortMaster e Steam (o IGDB saiu: pedia credenciais). Cabeçalho só com Omni36OS. Detalhes da tela foi para Verificar.

## 1.6.0 (29/10/2026)

- Sistema > Atalhos (no lugar do Atalho L3+R3): dentro dos jogos, FN + X mostra o contador de FPS com temperatura e bateria, FN + B liga o limite de 30 FPS, FN + Y salva a tela e SELECT + START (segurar) fecha o jogo. Cada um liga e desliga, e "Personalizar um atalho" troca a tecla que vai com o FN; os textos acompanham.
- Sem depender do segundo cartão: o backup pergunta onde salvar (cartão do sistema, segundo cartão ou pendrive); modo pendrive, reparo e testes usam /roms quando não há /roms2.
- Botão de power num jogo: o menu Energia ganhou mostrar o contador de FPS, limitar a 30 FPS, captura de tela e fechar o jogo.
- Restos do EmulationStation removidos: modo pendrive, botão de power e atalhos agora tratam o Omni36OS como o menu do console; saíram Mostrar no console, Restaurar o ES, o card Jogos e o manual do ES.
- Sistema: Contraste virou barra (0 a 100%, 50% = normal). Volume, brilho e contraste mudam com o analógico esquerdo; o direcional só navega e troca de coluna. Tema subiu para a esquerda, Restaurar áudio foi para a direita e Zerar virou Redefinir o sistema.
- Cada página explica a opção escolhida no topo do painel da esquerda (lâmpada roxa); os rótulos AÇÕES, DIAGNÓSTICO e STATUS DA BATERIA saíram.
- Rede pelo cabo USB: o NetworkManager não mexe mais na usb0, então o PC volta a receber IP no modo universal; o painel mostra o IP entregue.
- Backup: Exportar e Importar direto na página, sem a janela intermediária.
- Modo pendrive: o aviso fala só do Wi-Fi (o console não usa teclado USB).

## 1.5.0 (28/10/2026)

- Ports: uma lista só (sem sistemas), favoritos primeiro. Ao lado, a ficha do jogo (PortMaster e Steam): capa, estúdio, data, gêneros e descrição. Busca uma vez por jogo com Wi-Fi e guarda no cartão. Uma pasta info dentro da pasta do port (info.json, imagem e .txt) vale sobre a internet.
- Sistema mais leve: EmulationStation, RetroArch e emuladores removidos (3 GB livres); serviços e timers do dArkOSen que não servem a ports desligados no boot. O SSH continua ligado.
- Sem repetição entre cards: Verificar virou resumo só dos alertas; cada card mostra o seu assunto. Cartões SD virou card no lugar de Jogos (a biblioteca continua na tela inicial). O processador se ajusta só em Desempenho, e o código do RetroArch saiu.
- Os cards viraram a tela inicial; Ports é o primeiro card e abre a biblioteca. Testar ports foi para Ferramentas. Ao fechar um port, a biblioteca volta no mesmo lugar.
- Cartões SD > Jogos lidos de: ROMS, ROMS2 ou os dois; ao sair da página, busca jogos e ports uma vez e atualiza a lista.
- Testar ports: causa provável da falha e "Corrigir e testar de novo" para falhas conhecidas (permissão, script do Windows, memória); a correção é desfeita se não resolver.
- Backup, nome do jogador, tema e atalho L3+R3 foram de Ajuda para Sistema. Créditos agora listam os projetos usados como base, com o GitHub de cada um; o grupo do Telegram saiu.
- Sistema > Segurança: trocar a senha, senha do Samba e trava por senha numa página só. Sistema na ordem Volume, Brilho, Gamma; o brilho saiu de Bateria (era repetido) e a "Tela inicial do console" (do tempo do ES) saiu de Ajuda.
- Sistema > Redefinir o sistema: apaga nome, trava e tema, volta zram, processador, GPU, atalho e power ao padrão.
- Listas dão a volta: para baixo no último item vai ao primeiro, e vice-versa.
- Desempenho > Memória extra (zram): até 768 MB, desligada por padrão. Ao abrir um port, o Omni36OS limpa o cache, põe CPU, GPU e memória no máximo e pausa os serviços que ninguém está usando.
- Ferramentas do sistema reescritas dentro do Omni36OS, sem telas de terminal: abrem como páginas dos cards.
- Verificar > Testar o controle: desenho do R36S com cada botão, gatilho e analógico. Sai segurando SELECT + START por 1 s.
- Sistema > Trocar a senha, com teclado na tela do Omni36OS (A digita, B apaga, START confirma).
- Card USB: rede pelo cabo USB (modo universal ou internet pelo PC, SSH, web e Samba) e montar ou desmontar pendrive.
- Bateria > Calibrar a bateria: amostras em segundo plano, curva aplicada sem o EmulationStation.
- Desempenho > Liberar overclock: libera 1512 MHz e GPU 600 MHz, com cópia do DTB antes de mudar. As outras opções de DTB saíram: o risco de quebrar o boot é grande.
- Sistema sem painel de diagnóstico: as ações aparecem em duas colunas.
- Bateria: "Atualizar status" no lugar de "Verificar de novo"; o painel virou "Status da bateria".
- Ferramentas > Arquivos: copiar, mover, renomear, apagar e criar pastas nos cartões e no pendrive.
- Nome do jogador: perguntado na primeira vez e usado na saudação (Bom dia, Boa tarde, Boa noite) e no topo da tela. Troque em Ajuda > Nome do jogador.
- Sistema > Trava por senha: o console pede a senha ao ligar. A senha fica em texto simples em EASYROMS/senha/senha.txt para recuperar pelo PC; apagar o arquivo desliga a trava.
- Sistema > Senha do Samba: redefine só a senha das pastas compartilhadas.
- Menu com 9 cards: o Som entrou no card Sistema (volume e restaurar áudio junto do brilho).

## 1.4.0 (26/10/2026)

- Botão de power abre o menu de energia (Cancelar, Suspender, Reiniciar, Desligar); apertar o power de novo com o menu aberto desliga. Ligue ou desligue em Ajuda > Botão de power.
- FN + power: modo pânico. Fecha o jogo, port ou ferramenta na tela e volta o processador, o brilho e o som para níveis seguros. Duas vezes em 10 s: grava tudo e reinicia.
- Desligar e reiniciar pelo Omni36OS agora fecham o ES e gravam tudo antes, como o power do Omni36OS.
- Atalho L3+R3 desligado: a troca entre o Omni36OS e o ES é pelo menu (SELECT > Abrir o ES).

## 1.3.1 (26/10/2026)

- Lista de ferramentas mais limpa: sem as etiquetas Nativo/Janelas/App.
- FN+SELECT não alterna mais entre o Omni36OS e o ES (no ES só esmaecia a tela); use SELECT > Abrir o ES.
- START+SELECT juntos não fecham mais o Omni36OS (para ir ao ES: SELECT > Abrir o ES).
- Jogos só abrem pela lista da tela inicial; no card Jogos do menu a ficha é só para consultar.

## 1.3.0 (26/10/2026)

- Aviso com contagem antes do que é perigoso: tela vermelha dizendo o que a ação faz, o que pode dar errado e como desfazer. Continuar só acende depois de 10 s (o que pode impedir o boot) ou 5 s (o resto); Cancelar já começa escolhido.
- Patch do DTB, Tela em 60 Hz e Restaurar o Omni36OS pedem ainda apertar A 5 vezes (parar por 2 s recomeça a contagem). Passou uma vez, não espera de novo até reiniciar.
- O aviso também vale para desfazer o Omni36OS no ES, importar backup, consertar o cartão, restaurar o RetroArch e o arquivo de boot.
- Zerar últimos jogados guarda uma cópia (gamelist.xml.omni-bak) antes de apagar.

## 1.2.0 (26/10/2026)

- O Omni36OS é a tela inicial do console: liga direto na biblioteca de jogos (sistemas à esquerda, jogos à direita, A abre a ficha e joga).
- A tela inicial são os cards; Ports é o primeiro. START e SELECT não têm atalho: Energia (suspender, reiniciar, desligar) abre pelo botão de power.
- Card Ferramentas: as 47 ferramentas do menu Opções do Omni36OS. 13 reescritas aqui dentro; as outras abrem com as janelas do Omni36OS (menus, mensagens, teclado na tela) no lugar das janelas de terminal.
- Ferramentas que mexem no boot ficam em Perigoso, com aviso duplo.

## 1.1.0 (26/10/2026)

- Card Jogos: os jogos que o ES mostra, por sistema, com favoritos, recentes, mais jogados e repetidos. L1/R1 pulam de letra em letra.
- Ficha do jogo com capa, descrição, tempo de jogo e o botão Jogar: abre com o mesmo emulador, core e governador do ES, e o Omni36OS volta no card Jogos quando o jogo fecha.
- Diagnóstico da biblioteca: BIOS que faltam, arquivos que o ES não mostra, jogos repetidos e sem capa.
- RetroArch foi para Ajuda > RetroArch.
- FN+SELECT (ou L3+R3) alterna entre o Omni36OS e o ES.

## 1.0.0 (26/10/2026)

- Primeira versão do Omni36OS, nascido da Sab 1.10: tudo que ela fazia (verificação, bateria, som, tela, desempenho, cartões, pendrive, RetroArch, teste de ports, backup) com nome, ícone e pastas próprios.
- Tela inicial do console: o Omni36OS abre no boot, antes do ES (sempre ou só com alertas); B vai para o ES e sair do ES volta para o Omni36OS. Segure B no boot para o BaRT ou L1 para pular.
- Atalho L3+R3: segure os dois analógicos por 1 s para abrir o Omni36OS no menu do ES; no modo beta, também por cima dos jogos.
- Tema claro e tema escuro (Ajuda > Tema).
- Instala ao lado da Sab sem conflito: pastas, configurações e serviços com nomes próprios.
