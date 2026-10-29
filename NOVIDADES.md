# Novidades do Omni36OS

Histórico completo. Dentro do console (Ajuda > Novidades) aparece só a versão em uso.

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
