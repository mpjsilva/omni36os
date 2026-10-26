"""Textos do card Ajuda: manual, cuidados, novidades e créditos.
Linhas que começam com "# " viram títulos no leitor."""

TELEGRAM = "t.me/r36sbr"

# A versão em uso vem do arquivo VERSION; a lista abaixo é o histórico.
NOVIDADES = [
    ("1.7.0", "26/10/2026", [
        "Card Testar ports: abre um port por 15 s e fecha sozinho; se ele fechar antes, gera um relatório em sab/logs/<port>/.",
        "Ports listados por cartão (/roms2 ou /roms), indicando qual pasta o ES mostra (lida do es_systems.cfg).",
        "Último resultado de cada port na lista e falhas como alerta no card.",
        "Tela inicial com 10 cards em 4 linhas.",
    ]),
    ("1.6.0", "26/10/2026", [
        "Recursos do dArkOSen dentro da Sab: overclock de CPU e GPU, gamma, cor do LED e ZRAM.",
        "Modo do processador unificado com o CPU Manager e o R36 Tuner (/etc/cpu-settings.conf).",
        "Verifica serviços que falham no boot e conserta o ajuste da RAM (dmc-governor).",
        "Alerta de cartão quase cheio e resultado da última verificação de cartão.",
        "Verificar e reparar o cartão de jogos (no boot) e limpar o lixo do Mac.",
        "Atalhos para a calibração da bateria e o backup e migração do dArkOSen.",
        "Aviso quando o USB Network Mode está ligado (usa a mesma porta do pendrive).",
    ]),
    ("1.5.0", "26/10/2026", [
        "Card Ajuda: manual, cuidados, novidades e créditos.",
        "Versão da Sab e do dArkOS visíveis na Ajuda.",
        "Tela de carregamento: as verificações rodam antes do menu e a animação fica fluida.",
        "Fim do alerta falso de som (o dArkOS apaga o .asoundrc enquanto um port roda).",
    ]),
    ("1.4.0", "25/10/2026", [
        "Pontos de alerta nos cards, com a causa listada ao abrir.",
        "O modo do processador escolhido na Sab não é mais desfeito pelo ES.",
        "Botões de ação aumentam de altura para caber o texto.",
        "Créditos com QR code do grupo no Telegram.",
    ]),
    ("1.3.0", "24/10/2026", [
        "Menu gráfico novo, sem aparência de terminal.",
        "A Sab abre e fecha como um port normal: volta para a lista de Ports.",
        "Sem inteligência artificial: só verificações e scripts.",
    ]),
    ("1.2.0", "23/10/2026", [
        "Pendrive USB: a partição de jogos aparece no PC pelo cabo.",
        "Detecção dos botões A/B trocados.",
    ]),
]

MANUAL = """# O que é a Sab
A Sab é um assistente para o R36S com dArkOS. Ela verifica bateria, som, tela, processador e cartões, aponta o que está errado e corrige com um botão.
Ela não usa internet nem inteligência artificial: são verificações e scripts fixos.

# Como usar
Direcional ou analógico: andar pelos cards e opções.
A: abrir ou confirmar. B: voltar. Select + Start: fechar a Sab.
Nas opções de valor (volume, brilho, modo do processador), use esquerda e direita.
Se os seus botões A e B forem trocados no ES, a Sab segue a mesma troca.

# Pontos de alerta
Um ponto amarelo (aviso) ou vermelho (problema) em um card mostra quantas coisas precisam de atenção ali. Abra o card para ver a causa.
Quando há conserto, ele aparece no topo das ações com a etiqueta SUGERIDO.
As verificações rodam na tela de carregamento. Depois de uma ação, o card verifica de novo sozinho; "Verificar de novo" força uma nova leitura.

# Verificar
Resumo geral: bateria, temperatura, som, espaço, overclock, cartões e serviços do sistema numa tela só.
Serviços que falham no boot aparecem aqui. A falha do dmc-governor (ajuste da RAM) tem conserto com um botão; a do systemd-remount-fs é conhecida e inofensiva no dArkOSen.

# Bateria
Mostra a carga da bateria e se está carregando. Ajuste o brilho e o modo do processador para a bateria durar mais.
"Calibrar a bateria" abre a ferramenta de calibração do dArkOSen: a Sab fecha, a ferramenta abre em tela cheia e, ao terminar, você volta para Ports. Calibre quando a porcentagem pular ou o aparelho desligar com carga sobrando.

# Som
Volume e saída de som. "Restaurar áudio" volta a saída padrão, a configuração de som do sistema e o volume para 40%.

# Tela e sistema
Brilho e o modelo da sua tela. "Detalhes da tela" diz qual opção escolher no SELECT MODEL ao atualizar o dArkOS, e avisa se o aparelho é um clone.
Gamma: deixa a imagem mais clara (abaixo de 1.0) ou mais escura e contrastada (acima de 1.0). Vale na hora e fica salvo para o boot; as teclas de atalho de gamma do dArkOSen continuam a partir do valor escolhido.
Cor do LED: verde ou vermelho, também no boot. Com a bateria em 10% ou menos, o LED pisca.
"Backup e migração" abre o assistente de backup do dArkOSen em tela cheia (a Sab fecha antes).

# Desempenho
Modo do processador: Economia, Equilibrado ou Máximo. A escolha fica salva em /etc/cpu-settings.conf, o mesmo arquivo do CPU Manager e do R36 Tuner, e vale no boot e depois de jogar.
Limite do processador: 1296 MHz é o padrão. De 1368 a 1512 MHz é overclock (OC).
Limite da GPU: 520 MHz é o padrão; 600 MHz é overclock.
O overclock só é liberado com o aparelho abaixo de 70 °C. Se ele esquentar com o OC ligado, a Sab sugere voltar ao padrão.
O painel também mostra os limites atuais e a ZRAM (memória comprimida que ajuda nos jogos pesados).
"Testar cartões" mede a velocidade dos cartões SD; leva até um minuto.

# Pendrive USB
Liga o modo pendrive: com o cabo de dados no PC, a partição de jogos (ou a do sistema) aparece como um pendrive para copiar ROMs.
Ligar e desligar reinicia o aparelho. Enquanto estiver ligado, o Wi-Fi e o teclado USB não funcionam, porque usam a mesma porta.
Ao tirar o cabo ou ejetar no PC, o console monta a partição de novo e volta ao ES. Para sair sem o PC, aperte B ou Select + Start.
"Restaurar boot" volta o arquivo de boot original se algo der errado.
"Limpar lixo do Mac" apaga os arquivos ._ e .DS_Store que o macOS cria ao copiar. Eles aparecem como jogos fantasmas no ES. A busca leva até um minuto.
Se o USB Network Mode estiver ligado, a Sab avisa: ele usa a mesma porta e precisa ser desligado antes.

# Cartões SD
Marca, tamanho, espaço livre e velocidade dos cartões. Cartões genéricos sem marca costumam ser lentos e falhar mais.
A Sab avisa quando um cartão passa de 90% de uso ou tem menos de 1 GB livre.
"Verificar e reparar o cartão de jogos" reinicia o aparelho e roda o reparo do dArkOSen (fsck.exfat) com o cartão desmontado. Depois o resultado aparece neste card, e o log fica em /boot/sd2_scan.log.

# RetroArch
Mostra o que foi mudado na configuração do RetroArch e restaura a de fábrica. Uma cópia da configuração atual fica guardada antes.

# Testar ports
Mostra os ports instalados separados por cartão: /roms2/ports (cartão de jogos) e /roms/ports (cartão do sistema). O ArkOS usa um ou outro para os jogos; a etiqueta "O ES MOSTRA" indica a pasta que aparece na lista de Ports (lida do es_systems.cfg). Ports na outra pasta estão instalados mas não aparecem no ES.
Escolha um port e aperte A: a Sab fecha, o port abre como se fosse pelo ES e, depois de 15 segundos, é encerrado sozinho. A Sab volta com o resultado.
Passou: o port ficou aberto os 15 segundos.
Falhou: o port fechou antes. O relatório fica em sab/logs/<nome do port>/ (dentro de /roms2/ports/sab) com a saída do port, os logs da pasta dele, as mensagens do kernel e o estado do sistema.
A lista mostra o último resultado de cada port, e as falhas viram alerta no card.
Ports com menu próprio (como Daytona USA e NFSU1) passam quando o menu abre: o teste não aperta botões.

# Ajuda
Este manual, os cuidados, as novidades de cada versão e os créditos."""

CUIDADOS = """# Antes de qualquer coisa
Faça backup do cartão do sistema no PC de vez em quando. Uma imagem do cartão inteiro salva você de quase qualquer problema.

# Pendrive USB
Sempre ejete o pendrive no PC antes de tirar o cabo. Tirar no meio de uma cópia pode corromper os arquivos.
Não desligue o console enquanto ele estiver ligado no PC.
Prefira compartilhar /roms2 (jogos). Mexer em /roms (sistema) pelo PC pode estragar o dArkOS.
Se o console não voltar ao normal, use "Restaurar boot" no card Pendrive USB.
Não ligue o USB Network Mode e o pendrive ao mesmo tempo.

# Verificar e reparar o cartão
O aparelho reinicia e passa alguns minutos verificando. Não desligue nem tire o cartão nessa hora.
O reparo apaga entradas corrompidas: se o cartão já estava com erros, algum arquivo danificado pode sumir. Tenha backup.

# Restaurar e atualizar
"Restaurar de fábrica" do RetroArch apaga os seus ajustes (uma cópia fica guardada).
Antes de atualizar o dArkOS, copie a partição BOOT do cartão para o PC e veja em "Detalhes da tela" qual modelo escolher.

# Overclock
Overclock é usar o chip acima do que a fábrica garante. Pode causar travamentos e, com o tempo, desgaste maior.
O kernel do dArkOSen protege o aparelho: freia a 70 °C, limita a 85 °C e desliga a 115 °C. Mesmo assim, se travar ou fechar jogos sozinho, volte para 1296 MHz (CPU) e 520 MHz (GPU).
A Sab não libera o overclock com o aparelho acima de 70 °C.

# Bateria e calor
Evite o modo Máximo com a bateria fraca ou o aparelho quente.
Com a bateria fraca, carregue antes de usar o pendrive ou atualizar.

# Cartões
Cartões genéricos falham mais. Se um cartão aparecer como lento ou sem marca, mantenha backup dos seus saves.

# Teste de ports
O teste abre o port de verdade e o encerra à força depois de 15 segundos. Ports que gravam configuração ou save logo ao abrir podem perder o que estava sendo gravado; teste com o save já em backup.
Durante o teste não aperte botões: o port recebe os comandos.
Se o port travar a tela, segure o botão de ligar para reiniciar; o resultado não é gravado nesse caso.

# Ao fechar
Saia da Sab com B ou Select + Start, nunca desligando o console direto: ao sair, o dArkOS devolve as configurações de som e do processador."""

CREDITOS = """# Sab
Assistente do R36S, feita por mpjsilva.

# Homenagem
O nome é uma homenagem a Sabrina Broch, youtuber que fala de ports do R36S.

# Comunidade
Grupo R36S Brasil no Telegram: """ + TELEGRAM + """
Abra "Grupo no Telegram" nas ações para ver o QR code.

# Bibliotecas
Fonte Poppins (licença OFL) e ícones Tabler (licença MIT)."""


def novidades_text():
    out = []
    for ver, data, itens in NOVIDADES:
        out.append(f"# Versão {ver} ({data})")
        out += [f"• {i}" for i in itens]
        out.append("")
    return "\n".join(out).strip()
