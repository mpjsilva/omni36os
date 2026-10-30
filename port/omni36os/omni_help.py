"""Textos de Geral > Sobre: manual, cuidados, novidades e créditos.
Linhas que começam com "# " viram títulos no leitor."""


# A versão em uso vem do arquivo VERSION. Aqui fica só ela; o histórico completo está no NOVIDADES.md.
NOVIDADES = [
    ("1.15.10", "30/10/2026", [
        'Lista de ports: cada jogo mostra em qual cartão está (ícone de cartão SD com o número 1 ou 2), e a ficha do jogo diz "Cartão 1" ou "Cartão 2".',
    ]),
    ("1.15.9", "30/10/2026", [
        'Tela certa no primeiro boot mais segura: cada teste troca só a tela dentro do DTB original do console. O boot.ini, o u-boot e o resto do hardware nunca são trocados, então uma tela errada só deixa a tela apagada, sem travar o boot.',
        'Tela certa mais rápida: espera 10 s em cada tela e começa logo no início do boot. O pior caso, com 12 telas, caiu de uns 8 para uns 5 minutos.',
        'Durante a busca da tela, o LED pisca em vermelho e verde. A pergunta toca um ding-dong no alto-falante e a confirmação, um arpejo.',
    ]),
    ("1.15.8", "30/10/2026", [
        'Textos curtos (novidades, ajuda) não mostram mais os botões de rolar quando não há nada para rolar.',
    ]),
    ("1.15.7", "30/10/2026", [
        'Procurar atualização mostra as novidades da versão nova antes de instalar (botão Novidades), lidas do GitHub.',
        'Atualizar e Voltar à versão anterior abrem com "Agora não"/"Cancelar" escolhido, para um toque a mais não instalar nada sem querer.',
    ]),
    ("1.15.6", "30/10/2026", [
        'Rede pelo cabo USB: a página mostra qual modo está ligado ("Modo universal: ligado") e quando a rede está desligada.',
        "Compatibilidade da rede USB: o cliente DHCP aparece numa linha só; faltar o dhcpcd não é mais um problema (basta um cliente).",
    ]),
    ("1.15.5", "30/10/2026", [
        "Rede pelo cabo USB e modo pendrive se revezam sozinhos: ligar um desliga o outro, sem aviso para fazer à mão (sair do pendrive reinicia uma vez e a rede USB liga sozinha na volta).",
        "Procurar redes liga o Wi-Fi se ele estiver desligado. Sem adaptador de Wi-Fi, o card Rede só cita isso, sem alerta.",
        "Pílula de estado: o ícone do Wi-Fi mostra a força do sinal, fica apagado sem rede e riscado com o rádio desligado, e se atualiza em todas as telas.",
    ]),
    ("1.15.4", "30/10/2026", [
        "O Omni36OS agora tem licença aberta: GNU GPL v3.0.",
    ]),
    ("1.15.3", "30/10/2026", [
        "Créditos completos em Geral > Sobre: sistemas base, PortMaster, gptokeyb, ogage, 351Files, File Browser, BatteryPlus, SDL2, FFmpeg, fontes, ícones, fontes de dados e a comunidade do R36S, com os links.",
    ]),
    ("1.15.2", "30/10/2026", [
        "Desligar e reiniciar: a tela de despedida aparece direto, sem piscar o menu ou a boas-vindas antes.",
    ]),
    ("1.15.1", "30/10/2026", [
        "Teclado: X dá espaço e Y troca letras e símbolos. A trava das maiúsculas fica só na tecla da tela (dois toques). Vale em todo o sistema.",
    ]),
    ("1.15.0", "30/10/2026", [
        "Notas: abrir mostra a nota inteira para ler, com rolagem. A edita a nota toda, como numa máquina de escrever: o texto sobe quando a linha enche, o teclado ganha Enter e L1/R1 levam o cursor entre as linhas. START salva.",
    ]),
    ("1.14.2", "30/10/2026", [
        "Vídeos e Notas: as listas ficam em tela cheia, como as Músicas, com a pílula de estado (Wi-Fi, volume, bateria, temperatura e hora). O vídeo tocando continua em tela cheia, sem nada por cima. Apagar uma nota pede confirmação, com Cancelar já escolhido.",
    ]),
    ("1.14.1", "30/10/2026", [
        "Manual revisado para o lançamento: apresentação nova, caminhos EASYROMS das pastas de vídeos e notas, Cartões no Verificar tudo, créditos do SDL2 e do FFmpeg, e sem a menção ao RetroArch, que não vem mais no sistema.",
    ]),
    ("1.14.0", "30/10/2026", [
        "Teclado novo, igual em todo o sistema e parecido com o do Android: começa em maiúscula e volta à minúscula depois da primeira letra (e maiúscula de novo depois de ponto), a tecla de maiúsculas trava com dois toques, Y trava direto e X troca letras e símbolos. Senhas começam em minúscula.",
    ]),
    ("1.13.0", "30/10/2026", [
        "Aplicativos ganha Vídeos (tocador simples com os codecs abertos do ffmpeg) e Notas (bloco de notas com teclado e pontuação).",
        "No Arquivos, músicas, vídeos e textos abrem direto no app certo.",
    ]),
    ("1.12.7", "30/10/2026", [
        "O card Armazenamento passa a se chamar Cartões, com a fonte do mesmo tamanho dos outros; legenda Pendrive, espaço e reparo.",
    ]),
    ("1.12.6", "30/10/2026", [
        "O card Tela e som volta a ter esse título (o texto saía do card); a legenda continua com brilho, som e bateria.",
    ]),
    ("1.12.5", "30/10/2026", [
        "Aplicativos mostra só a lista de apps; as opções do Músicas (visualização, apagar a tela e subpastas) ficam dentro do app, no START.",
    ]),
    ("1.12.4", "30/10/2026", [
        "Músicas: a pílula de estado (Wi-Fi, volume, bateria, temperatura e hora) aparece no tocador, o nome da visualização usa o aviso do sistema, e a captura (FN) acende a tela apagada antes de gravar.",
    ]),
    ("1.12.3", "30/10/2026", [
        "Músicas: se o launcher reiniciar com a tela apagada, a luz da tela volta sozinha.",
    ]),
    ("1.12.2", "30/10/2026", [
        "Músicas: visualização Capa do álbum, com a imagem da pasta ou a capa embutida no mp3. A capa também aparece na barra do que está tocando.",
    ]),
    ("1.12.1", "30/10/2026", [
        "Samba com senha: só o usuário omni entra, e a rede mostra apenas Cartão 1 e Cartão 2.",
    ]),
    ("1.12.0", "30/10/2026", [
        "Aplicativos, o card novo: Músicas toca os mp3 das pastas musicas dos cartões, com pastas e subpastas, visualizações (Barras, Ondas, Anel e Aurora) e a tela apagando sozinha enquanto a música toca.",
        "Bateria agora mora em Tela, som e bateria. Ports fica no centro e recebe o destaque toda vez que o menu aparece.",
        "Cada card diz as três coisas que faz.",
    ]),
    ("1.11.11", "30/10/2026", [
        "Texto de Inverter botões mais curto.",
    ]),
    ("1.11.10", "30/10/2026", [
        "Textos do desbloqueio do overclock e da ajuda dos botões revisados.",
    ]),
    ("1.11.9", "30/10/2026", [
        "Com a trava por senha ligada, desbloquear o overclock pede a senha do console.",
    ]),
    ("1.11.8", "30/10/2026", [
        "Overclock com trava de verdade: as velocidades acima de 1296 MHz (processador) e 520 MHz (GPU) só aparecem depois de Desempenho > Desbloquear overclock. Bloquear overclock volta tudo ao padrão.",
    ]),
    ("1.11.7", "30/10/2026", [
        "Ferramentas > Busca automática: liga e desliga a busca de capas e descrições.",
        "A biblioteca diz o que está buscando: imagem e descrição, só a descrição ou só a imagem. O que não foi encontrado não é buscado de novo, e nada é buscado com um jogo aberto.",
    ]),
    ("1.11.6", "30/10/2026", [
        "A busca de capas e descrições só acontece com o Wi-Fi conectado.",
    ]),
    ("1.11.5", "30/10/2026", [
        "Biblioteca: \"Buscando a descrição...\" e \"Descrição não encontrada\" no lugar dos textos de ficha.",
    ]),
    ("1.11.4", "30/10/2026", [
        "Descrições pela Wikipédia: texto em português e ano dos ports que o PortMaster e a Steam não têm.",
    ]),
    ("1.11.3", "30/10/2026", [
        "Capas e descrições: quando o PortMaster e a Steam não têm, o Omni36OS procura no DuckDuckGo.",
    ]),
    ("1.11.2", "30/10/2026", [
        "Biblioteca só de ports: lê apenas as pastas ports dos cartões. Pastas de emuladores não aparecem, e a leitura ficou quase instantânea.",
    ]),
    ("1.11.1", "30/10/2026", [
        "Controles: uma opção só, Inverter botões (Ligado/Desligado), troca A com B e X com Y juntos.",
    ]),
    ("1.11.0", "30/10/2026", [
        "Boot mais rápido e sem tela preta: tudo no máximo até o menu ficar pronto (cerca de 3 s a menos) e "
        "depois no mínimo. O logo e a boas-vindas seguem direto até o Omni36OS abrir.",
        "Wi-Fi USB sobe sozinho no boot, data, hora e fuso se ajustam quando a internet chega, e o volume "
        "fica como você deixou.",
        "Tela e som com painel próprio de brilho, contraste e volume. Troca de A/B e de X/Y em Controles.",
        "FN + Y grava a tela também no menu, na pasta imagens. O Arquivos mostra imagens em tela cheia.",
        "Cartão 2 aparece sozinho. Power sempre abre o menu de energia; FN + power desliga gravando tudo.",
        "Acesso por SSH e pelo navegador com omni/omni. Serviços remotos só ligam com rede.",
        "Visual: ícones próprios, textos com mais contraste, legendas com a arte dos botões e alinhamento ao "
        "pixel. O card Rede não fica mais com alerta depois que o Wi-Fi conecta.",
    ]),
]

MANUAL = """# O que é o Omni36OS
O Omni36OS é um sistema só de ports para o R36S, feito sobre o dArkOSen. Abre os ports, toca músicas e vídeos, guarda notas e cuida do console: verifica bateria, som, tela, processador e cartões, aponta o que está errado e corrige com um botão.
Não usa inteligência artificial: são verificações e scripts fixos. A internet só é usada para buscar capas e descrições, acertar a hora e procurar atualizações.

# Como usar
Direcional ou analógico: andar pelos cards e opções.
A: abrir ou confirmar. B: voltar. O botão de power abre Energia (suspender, reiniciar, desligar).
L1/R1: rolam o diagnóstico (painel da esquerda) quando ele não cabe; "L1: N acima" e "R1: mais N" mostram o que está escondido. No manual e nas listas, L1/R1 pulam de bloco em bloco.
Nas opções de valor (modo do processador, limites), use esquerda e direita. Em Tela e som, as barras (volume, brilho, contraste) e as escolhas mudam com o analógico esquerdo, e o direcional só navega.
Cada página explica a opção escolhida no topo do painel da esquerda (lâmpada roxa).
Se os botões A e B estiverem trocados no sistema, o Omni36OS segue a mesma troca.

# Pontos de alerta
Um ponto amarelo (aviso) ou vermelho (problema) em um card mostra quantas coisas precisam de atenção ali. Abra o card para ver a causa.
Quando há conserto, ele aparece no topo das ações com a etiqueta SUGERIDO.
As verificações rodam na tela de carregamento. Depois de uma ação, o card verifica de novo sozinho; "Atualizar status" força uma nova leitura.
Geral > "Verificar tudo" junta numa lista só os alertas de todos os cards.

# Ports (card do centro)
O console liga nos cards e entrega o destaque no Ports, no centro: A abre a biblioteca. É uma lista só, com os favoritos primeiro e o resto por nome. Cima/baixo escolhem o port, esquerda/direita pulam de 10 em 10 e L1/R1 pulam de letra. Ao lado aparece a ficha do jogo (capa, estúdio, data, gêneros e descrição); A abre o port e, ao fechar, a lista volta no mesmo lugar.
B volta para os cards. O botão de power abre Energia: suspender, reiniciar ou desligar.
A capa e a descrição vêm da pasta info do port (info.json, imagem e .txt) e, com o Wi-Fi conectado, do PortMaster, da Steam, da Wikipédia e do DuckDuckGo, buscados uma vez e guardados no cartão. Ferramentas > Busca automática liga e desliga a busca.

# Tela e som
"Brilho, contraste e volume" abre um painel com as três barras: cima/baixo escolhe, esquerda/direita ajusta na hora, A confirma e B desfaz o que mudou.
"Tema": escuro ou claro, vale na hora e fica salvo.
Brilho: a luz da tela.
Contraste: barra de 0 a 100% (50% é o normal, gamma 1.0); acima de 50% a imagem fica mais contrastada, abaixo mais clara. Vale na hora e fica salvo para o boot; as teclas de atalho de gamma do sistema continuam a partir do valor escolhido.
Volume: o som do console. O último volume fica salvo: ao ligar, o console volta com ele (antes voltava sempre em 40%). "Restaurar áudio" conserta o som quando ele some ou sai pelo lugar errado: põe de volta o arquivo de som do sistema (.asoundrc), aponta a saída para o lugar certo e deixa o volume em 40%.
A saída de som é automática: com o fone encaixado, o som sai só no fone; sem ele, só no alto-falante. A troca acontece na hora e vale também no boot e depois de um jogo que mexa no som.
Cor do LED: verde ou vermelho, também no boot. Com a bateria em 10% ou menos, o LED pisca.
"Detalhes da tela" mostra o modelo da sua tela, diz qual opção escolher no SELECT MODEL ao atualizar o Omni36OS e avisa se o aparelho é um clone.

# Rede
Data, hora e fuso se acertam sozinhos: na primeira vez que o console pega internet depois de ligar, o Omni36OS descobre o fuso pela conexão, acerta a hora, grava no relógio do console e desliga o serviço de hora até o próximo boot.
"Ligar o Wi-Fi" liga e desliga o adaptador, "Procurar redes" liga o Wi-Fi se ele estiver desligado e lista as redes por perto (com cadeado pede a senha no teclado; START confirma), "Redes salvas" conecta de novo ou esquece uma, "Desconectar" sai da rede atual. O painel mostra a rede, o sinal e o IP do console, e se atualiza sozinho. Na pílula de estado, o ícone do Wi-Fi aparece riscado sem adaptador ou com o rádio desligado, apagado quando está ligado sem rede e, conectado, com as ondas da força do sinal.
"Rede pelo cabo USB": o console vira uma placa de rede no cabo.
- Modo universal: o console dá o IP ao PC. No PC: ssh omni@10.44.44.1.
- Internet pelo PC: o PC compartilha a internet pelo cabo e o console recebe o IP dele.
- Serviços remotos: Ligados ou Desligados (esquerda/direita). Ligados, sobem o Samba e o navegador web de arquivos (usuário e senha: omni); o SSH fica sempre.
A página mostra o IP e os comandos para o PC, e se atualiza sozinha. A rede USB e o modo pendrive usam a mesma porta: ligar um desliga o outro sozinho (sair do pendrive reinicia o console uma vez, e a rede USB liga sozinha na volta).

# Controles
"Testar o controle" mostra o R36S com cada botão aceso ao apertar, os gatilhos L2/R2 e a posição dos analógicos. Para sair, segure SELECT + START por 1 segundo (B também é testado).
"Inverter botões": Ligado troca A com B e X com Y.
"Atalhos": combinações com o botão FN que valem dentro dos jogos (veja Atalhos abaixo).
Botão de power: um toque abre Energia (Cancelar, Suspender, Reiniciar e Desligar); outro toque com o menu aberto desliga com segurança. FN + power desliga na hora, fechando o jogo e gravando tudo antes. Segurar o power por uns 8 s sempre desliga à força: isso é do chip de energia, não do Omni36OS. O botão de reset reinicia por hardware e não pode ser mudado.
"Consertar atalhos" reinicia o serviço que cuida do brilho e do volume pelos botões.
Serviços que falham no boot aparecem aqui. A falha do dmc-governor (ajuste da RAM) tem conserto com um botão; a do systemd-remount-fs é conhecida e inofensiva no Omni36OS.

# Atalhos (dentro de Controles)
Valem com um port aberto. Cada atalho tem Ligado ou Desligado na página, e os botões abaixo são os que estão valendo agora:
«fps»: mostra ou esconde o contador. Ele fica no canto de cima e mostra quadros por segundo, temperatura e bateria. O FPS fica verde de 50 para cima, amarelo de 28 a 49 e vermelho abaixo disso. A temperatura fica amarela a partir de 65 °C e vermelha a partir de 75 °C. A bateria fica amarela até 30% e vermelha até 15%; carregando, aparece um raio verde.
«limite»: liga ou desliga o limite de 30 FPS. Em jogo leve, economiza bateria e esquenta menos. Um traço roxo no contador mostra que o limite está ligado.
«captura»: captura de tela na pasta imagens dentro da pasta do jogo (ex.: ports/daytona/imagens), em .bmp com o nome do port e a hora, sem o contador. Vale em qualquer cartão. Aparece "CAPTURA SALVA" no canto. Fora de um jogo, FN + Y grava a tela do Omni36OS em PNG na pasta imagens do cartão 1 (EASYROMS/imagens); dá para ver em Arquivos.
«fechar» (segure 1 s): fecha o jogo e volta ao Omni36OS. Serve para port travado ou sem opção de sair. Este é fixo.
"Personalizar um atalho": escolha o atalho e aperte a tecla nova; ele vira FN + essa tecla. O Omni36OS recusa o que já é do sistema ou de outro atalho. "Voltar aos botões padrão" desfaz (FN + X, FN + B e FN + Y).
Pelo botão de power, com um jogo aberto: o jogo congela e o menu Energia abre por cima com as mesmas opções (mostrar o contador, limitar a 30 FPS, captura de tela e fechar o jogo), além de suspender, reiniciar e desligar. Captura e contador valem quando o jogo volta.
O sistema (ogage) já usa: FN + cima/baixo e FN + volume para o brilho; FN com L1/R1, esquerda/direita, A, L3 e R3 para ajustes do sistema; SELECT + FN fala a bateria; FN + power desliga gravando tudo.
O contador, o limite e a captura funcionam em ports que desenham com OpenGL ES (a maioria). Ports em 32 bits ou que trocam o LD_PRELOAD não mostram o contador.

# Bateria (dentro de Tela e som)
O painel mostra a carga, se está carregando, o brilho e o modo do processador. Com o brilho alto ou o processador no máximo, aparece a dica de economia com um botão. O processador se ajusta em Desempenho.
Bateria no fim (a porcentagem do R36S não é confiável, por isso os limites são altos): em 30% o Omni36OS sugere conectar o carregador; em 15%, sugere salvar o progresso (num jogo, o contador surge com a bateria em vermelho). Em 10%, sem o carregador, o Omni36OS fecha o jogo dando tempo de ele salvar, grava tudo e desliga, em vez de o console apagar de repente.
"Calibrar a bateria" abre a página da calibração. Calibre quando a porcentagem pular ou o aparelho desligar com carga sobrando:
1. Carregue até o fim e tire o carregador.
2. Toque em "Iniciar a calibração" e use o console normalmente (pode jogar) até ele desligar sozinho. Uma amostra por minuto fica gravada em /usr/local/etc/battery-cal.
3. Ligue, carregue e toque em "Aplicar a curva". A porcentagem passa a seguir a sua bateria.
"Voltar à curva de fábrica" desfaz.

# Aplicativos
"Músicas" toca as músicas (mp3, e também ogg, flac e wav) das pastas musicas dos cartões: EASYROMS/musicas e, com o cartão 2, ROMS2/musicas. A pasta do cartão 1 é criada sozinha.
Cada pasta mostra as músicas soltas nela e as subpastas; A numa subpasta entra nela, A numa música toca a pasta a partir dela, Y toca a pasta inteira e B volta. Com "Ler subpastas" ligado, tocar uma pasta inclui as músicas das subpastas, nível por nível.
Na tela Tocando: A pausa, esquerda/direita trocam de música, L1/R1 voltam e avançam 10 s, Y troca a visualização e B volta à lista (a música continua; X volta para a tela Tocando). Sair das Músicas para a música.
Opções (START, dentro do app): "Visualização": Capa do álbum (a imagem da pasta, como cover.jpg, ou a capa embutida no mp3), Barras, Ondas, Anel ou Aurora, dançando com o som. "Apagar a tela": com a música tocando e sem apertar nada, a luz da tela apaga em 30 s, 1, 2 ou 5 minutos (ou Manter ligada); qualquer botão acende.
As pastas ficam num índice (nome, título e artista das tags): só a pasta que mudou é lida de novo, e a lista guarda só os caminhos.
"Vídeos" toca os vídeos das pastas videos dos cartões (EASYROMS/videos, criada sozinha, e ROMS2/videos), com os codecs abertos do ffmpeg: mp4, mkv, webm, avi e outros (H.264, H.265, VP8, VP9, AV1, MPEG-4). A pausa, esquerda/direita voltam e avançam 10 s, L1/R1 1 minuto, B volta. Vídeos até 720p rodam bem; acima disso, depende do codec. A música para enquanto o vídeo toca.
"Notas" é um bloco de notas simples: textos na pasta notas do cartão 1 (EASYROMS/notas). Na lista, a primeira linha cria uma nota e X apaga (com confirmação). Abrir uma nota mostra o texto inteiro: cima/baixo rolam e L1/R1 pulam a página. A edita a nota toda, como numa máquina de escrever: o texto quebra sozinho e sobe quando a linha enche, Enter começa uma linha nova, L1/R1 levam o cursor para a linha de cima ou de baixo, START salva e SELECT sai sem salvar.
No Arquivos, abrir uma música, um vídeo ou um texto (txt, md, log, ini, cfg, conf) abre o app certo; B volta para a pasta.

# Desempenho
No menu, o processador, a GPU e a memória ficam no mínimo: o console esfria e a bateria rende. Só um vídeo tocando faz o processador subir conforme a carga. Ao abrir um port, tudo sobe até os limites abaixo; ao voltar, desce de novo.
Limite do processador (nos ports): 1296 MHz é o padrão. De 1368 a 1512 MHz é overclock (OC).
Limite da GPU (nos ports): 520 MHz é o padrão; 600 MHz é overclock.
O overclock só é liberado com o aparelho abaixo de 70 °C. Se ele esquentar com o OC ligado, o Omni36OS sugere voltar ao padrão.
Memória extra (zram): desligada por padrão. 256, 512 ou 768 MB de memória comprimida na RAM, que segura ports pesados que fecham por falta de memória. Vale na hora e nos próximos boots; custa um pouco de processador.
"Liberar overclock" mexe no arquivo de hardware do boot (DTB): libera as frequências de 1368 a 1512 MHz e a GPU de 600 MHz. Tem trava: aviso vermelho com contagem e depois A apertado 5 vezes. Antes de mudar, o Omni36OS guarda uma cópia do DTB. Vale depois de reiniciar; o limite se escolhe em "Limite do processador" e "Limite da GPU".

# Cartões
Tudo sobre onde ficam os jogos: os cartões, o pendrive e a porta USB. As ações que reiniciam ou apagam ficam no fim da página.
"Origem dos jogos": ROMS (cartão 1), ROMS2 (cartão 2) ou ROMS e ROMS2. Ao sair da página depois de trocar (B ou START), o Omni36OS procura os jogos e os ports de novo, uma vez só, e atualiza a biblioteca e o Testar ports. Com as duas, o mesmo sistema dos dois cartões vira uma lista só. ROMS2 só entra se o segundo cartão estiver no console.
"Detalhe do cartão" (com dois cartões, "Detalhe dos cartões"): mostra a marca, o tamanho, o espaço livre e o ocupado do cartão inteiro e testa a escrita e a leitura de cada cartão; leva até um minuto. O espaço livre aparece no painel. Cartões genéricos sem marca costumam ser lentos e falhar mais: o detalhe avisa quando o cartão não tem marca identificada (não é alerta).
O Omni36OS avisa quando um cartão passa de 90% de uso ou tem menos de 1 GB livre.
"Verificar e reparar os jogos" reinicia o aparelho e roda o reparo do Omni36OS (fsck.exfat) com o cartão desmontado. Depois o resultado aparece neste card, e o log fica em /boot/sd2_scan.log (segundo cartão) ou /boot/sd1p3_scan.log (só o cartão do sistema).

Modo pendrive:
Liga o modo pendrive: com o cabo de dados no PC, a partição ROMS2 (cartão 2) ou ROMS (cartão 1, escolha em "Partição no PC") aparece como um pendrive para copiar ports.
Ligar e desligar reinicia o aparelho. Enquanto estiver ligado, o Wi-Fi não funciona, porque usa a mesma porta. Se a rede USB estiver ligada, ela desliga sozinha.
Ao conectar o PC, o Omni36OS fecha para soltar a partição. Ao tirar o cabo ou ejetar no PC, o console monta a partição de novo e o Omni36OS volta. Para sair sem o PC, aperte B ou Select + Start.
"Restaurar boot" volta o arquivo de boot original se algo der errado.
"Limpar lixo do Mac" apaga os arquivos ._ e .DS_Store que o macOS cria ao copiar. Eles aparecem como ports fantasmas na biblioteca. A busca leva até um minuto.
"Montar pendrive" monta um pendrive ligado no OTG em /mnt/usbdrive (FAT, exFAT ou NTFS). Com ele montado, o mesmo botão vira "Desmontar pendrive": use antes de tirar. Com essa opção escolhida, o painel da esquerda diz se o pendrive foi reconhecido, qual é e se já está montado.

# Ferramentas
"Arquivos": navega pelos cartões (/roms, /roms2) e pelo pendrive. A abre a pasta (ou a imagem, em tela cheia: esquerda/direita passa para a próxima, A mostra ou esconde o nome, B volta), B sobe um nível, X abre as opções do item (copiar, mover, renomear, apagar) e START abre as opções da pasta (colar aqui, nova pasta). Músicas, vídeos e textos abrem direto no app de Aplicativos. Para copiar: X > Copiar no item, vá até a pasta de destino e START > Colar aqui. Apagar pede confirmação, com Cancelar já escolhido.
"PortMaster" abre em tela cheia; o Omni36OS volta quando ele fecha. Para copiar, mover, renomear e apagar, use "Arquivos", aqui mesmo no Omni36OS.
As outras ferramentas do sistema ficam nos cards: Testar o controle (Controles), Trocar a senha (Geral > Segurança), Wi-Fi e rede pelo cabo (Rede), pendrive (Cartões), Calibrar a bateria (Tela e som), Liberar overclock (Desempenho). Tudo o que mexe no boot abre um aviso vermelho com contagem; Cancelar fica escolhido desde o início.

# Testar ports (dentro de Ferramentas)
Mostra os ports das pastas escolhidas em Cartões > Origem dos jogos.
Escolha um port e aperte A: o Omni36OS fecha, o port abre como pela biblioteca e, depois de 15 segundos, é encerrado sozinho. O Omni36OS volta com o resultado.
Passou: o port ficou aberto os 15 segundos.
Falhou: o port fechou antes. O relatório fica em omni36os/logs/<nome do port>/ (dentro de /opt/omni36os) com a saída do port, os logs da pasta dele, as mensagens do kernel e o estado do sistema.
A lista mostra o último resultado de cada port, e as falhas viram alerta no card.
"Limpar avisos de falha" tira o alerta do card depois que você já viu as falhas. O resultado continua na lista até o port ser testado de novo; se o novo teste falhar, o aviso volta.
Ports com menu próprio (como Daytona USA e NFSU1) passam quando o menu abre: o teste não aperta botões.
Quando o port falha, o Omni36OS lê o relatório e mostra a causa provável (script do Windows, arquivo sem permissão, falta de memória, runtime do PortMaster, biblioteca, glibc, arquivos do jogo, cartão exFAT, travamento). Se houver conserto seguro, aparece "Corrigir e testar de novo": ele corrige (permissão, formato dos scripts ou memória extra) e testa outra vez. Se ainda falhar, a correção é desfeita. O diagnóstico também fica no relatório.

# Geral
O que é seu e do Omni36OS, como nos Ajustes do iPhone, nesta ordem:
"Nome do jogador": aparece na saudação do menu.
"Segurança": senhas e trava (veja abaixo).
"Backup": exporta e importa as configurações (veja Backup abaixo).
"Procurar atualização" (precisa de Wi-Fi): procura uma versão nova no GitHub. Antes de instalar, o Omni36OS baixa e confere tudo; a versão de agora fica guardada. Se a nova não chegar ao menu em 3 tentativas, a anterior volta sozinha e um aviso explica. "Voltar à versão anterior" aparece depois de uma atualização e troca de volta a pedido. Deixe o carregador ligado durante a atualização.
"Verificar tudo": mostra só o que precisa de atenção em todos os cards (tela e som, bateria, desempenho, cartões e serviços), cada linha com o card de origem. Sem alertas, aparece "Tudo certo". O detalhe fica em cada card.
"Sobre": este manual, os cuidados, as novidades de cada versão e os créditos (com os projetos usados como base).
"Redefinir o sistema": volta ao primeiro boot. Apaga o nome do jogador, a trava por senha e o tema, desliga a memória extra (zram) e volta processador (Equilibrado, 1296 MHz), GPU (520 MHz) e atalhos ao padrão; depois pergunta o nome de novo. Ports, jogos, testes e as senhas do sistema e do Samba ficam.

# Segurança (dentro de Geral)
Tudo o que é senha fica aqui. B volta para Geral.
"Trocar a senha" muda a senha do usuário omni (SSH, SFTP e Samba; a senha padrão é omni) com o teclado na tela: direcional escolhe, A digita, B apaga, X dá espaço, Y troca letras e símbolos (as maiúsculas travam com dois toques na tecla da tela), START confirma e SELECT cancela (como no teclado do Android, começa em maiúscula; senha começa em minúscula). A senha é pedida duas vezes.
"Senha do Samba" redefine só a senha das pastas compartilhadas (usuário omni), sem mexer na do SSH.
"Trava por senha": com ela ligada, o console pede a senha ao ligar, antes de mostrar os jogos (o botão de power ainda abre Energia para desligar). A senha fica em texto simples em EASYROMS/senha/senha.txt: esqueceu, abra o cartão no PC e leia. Apagar esse arquivo desliga a trava. Para desligar pelo console, a senha atual é pedida.

# Backup
Geral > Backup > Exportar ou Importar.
Omni36OS: resultados dos testes de ports e os ajustes de processador, GPU, RAM e gamma. Os atalhos e o tema não entram.
Exportar pergunta onde salvar: cartão do sistema (/roms/backup/omni36os), segundo cartão (/roms2/backup/omni36os) ou pendrive (/mnt/usbdrive/backup/omni36os). Só aparece o que está no console agora, e o último lugar escolhido vem marcado. O caminho completo aparece ao terminar.
Importar abre a pasta dos backups; navegue pelas pastas com A ("..": voltar). Cada arquivo mostra de qual módulo é, e só o backup do módulo certo pode ser importado.
Antes de importar, o Omni36OS salva o que está valendo agora como "...-antes-de-importar.tar.gz".
Só configurações: saves, estados, cores, shaders, temas e bancos de dados ficam de fora."""

CUIDADOS = """# Antes de qualquer coisa
Faça backup do cartão do sistema no PC de vez em quando. Uma imagem do cartão inteiro salva você de quase qualquer problema.

# Pendrive USB
Sempre ejete o pendrive no PC antes de tirar o cabo. Tirar no meio de uma cópia pode corromper os arquivos.
Não desligue o console enquanto ele estiver ligado no PC.
Com segundo cartão, prefira compartilhar /roms2. Sem ele, o PC recebe /roms (a partição de jogos do cartão do sistema): copie só para as pastas de jogos e ports.
Se o console não voltar ao normal, use "Restaurar boot" em Cartões (último item).

# Verificar e reparar o cartão
O aparelho reinicia e passa alguns minutos verificando. Não desligue nem tire o cartão nessa hora.
O reparo apaga entradas corrompidas: se o cartão já estava com erros, algum arquivo danificado pode sumir. Tenha backup.

# Restaurar e atualizar
Antes de atualizar o Omni36OS, copie a partição BOOT do cartão para o PC e veja em Tela e som > "Detalhes da tela" qual modelo escolher.

# Primeiro boot
Na primeira vez que liga, o Omni36OS acerta a tela sozinho: se aparecer "Está vendo esta tela?", aperte qualquer botão. Se a tela ficar apagada, não desligue: ele testa a próxima tela e reinicia sozinho (cada tentativa leva menos de um minuto). Se nenhuma for confirmada, volta tudo como estava.
Para refazer depois, crie pelo PC o arquivo omni36os-tela/testar na partição BOOT do cartão.

# Overclock
Overclock é usar o chip acima do que a fábrica garante. Pode causar travamentos e, com o tempo, desgaste maior.
O kernel do Omni36OS protege o aparelho: freia a 70 °C, limita a 85 °C e desliga a 115 °C. Mesmo assim, se travar ou fechar jogos sozinho, volte para 1296 MHz (CPU) e 520 MHz (GPU).
O Omni36OS não libera o overclock com o aparelho acima de 70 °C.

# Bateria e calor
Evite o overclock com a bateria fraca ou o aparelho quente.
Com a bateria fraca, carregue antes de usar o pendrive ou atualizar.

# Cartões
Cartões genéricos falham mais. Se um cartão aparecer como lento ou sem marca, mantenha backup dos seus saves.

# Teste de ports
O teste abre o port de verdade e o encerra à força depois de 15 segundos. Ports que gravam configuração ou save logo ao abrir podem perder o que estava sendo gravado; teste com o save já em backup.
Durante o teste não aperte botões: o port recebe os comandos.
Se o port travar a tela, segure o botão de ligar para reiniciar; o resultado não é gravado nesse caso.

# Backup e importação
Importar substitui as configurações do módulo pelas do arquivo. Use backups da mesma versão do Omni36OS: configurações de outra versão podem não funcionar.
Guarde cópias dos backups fora do console (no PC, pelo pendrive).

# Ao desligar
Desligue pelo menu Energia (botão de power), nunca segurando o power: pelo menu, o Omni36OS grava tudo e desmonta o boot antes de desligar.
Para fechar um port travado, use SELECT + START (segure 1 s) antes de pensar em desligar à força."""

CREDITOS = """# Omni36OS
Sistema só de ports para o R36S, feito por mpjsilva, com a ajuda do Claude (Anthropic) no desenvolvimento. Licença GNU GPL v3.0. github.com/mpjsilva/omni36os

# Sistemas usados como base
ArkOS, de christianhaitian: o sistema original do R36S e de vários portáteis RK3326, com o kernel, o ogage e os scripts de sistema. github.com/christianhaitian/arkos
dArkOS, de christianhaitian: o ArkOS sobre Debian. github.com/christianhaitian/dArkOS
dArkOSen, de djparentx: a imagem usada como base do Omni36OS, com o catálogo de telas dos modelos R36, a ferramenta de calibração da bateria (que o Omni36OS reescreveu), o patch do DTB e o desligamento seguro. github.com/djparentx/dArkOSen-R36S

# Ports e ferramentas
PortMaster e sua comunidade: a loja de ports, os ports e os dados dos jogos. github.com/PortsMaster/PortMaster-GUI
gptokeyb: o controle como teclado e mouse nos ports. github.com/PortsMaster/gptokeyb
ogage: as teclas de atalho do sistema. github.com/christianhaitian/ogage
351Files: gerenciador de arquivos de tela cheia. github.com/351ELEC/351Files
File Browser: o navegador de arquivos pela rede. github.com/filebrowser/filebrowser
BatteryPlus, de Mikhailzrick. github.com/Mikhailzrick/knubat.components

# Bibliotecas e programas livres
SDL2, SDL2_ttf, SDL2_image e SDL2_mixer, licença zlib: tela, controles, fontes, imagens e músicas. libsdl.org
FFmpeg, licença LGPL/GPL: os vídeos. ffmpeg.org
Debian, Linux, NetworkManager, Samba, systemd e todo o software livre por baixo.
Fonte Poppins, licença OFL: github.com/itfoundry/Poppins
Ícones Tabler, licença MIT: github.com/tabler/tabler-icons

# Dados da biblioteca
Steam (capas e descrições), Wikipédia (descrições em português; texto sob CC BY-SA 4.0) e DuckDuckGo (imagens quando as outras fontes não têm).

# Comunidade
A comunidade do R36S, que documenta modelos, telas, clones e consertos e torna este projeto possível. Obrigado!"""


def novidades_text():
    out = []
    for ver, data, itens in NOVIDADES:
        out.append(f"# Versão {ver} ({data})")
        out += [f"• {i}" for i in itens]
        out.append("")
    return "\n".join(out).strip()



def manual(combos=None):
    """O manual com os botões dos atalhos que estão valendo (Controles > Atalhos)."""
    import omni_combos
    combos = combos or omni_combos.defaults()["combos"]
    text = MANUAL
    for k in omni_combos.ACTIONS:
        text = text.replace(f"«{k}»", omni_combos.text(combos[k]))
    return text
