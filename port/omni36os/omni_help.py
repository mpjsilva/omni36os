"""Textos do card Ajuda: manual, cuidados, novidades e créditos.
Linhas que começam com "# " viram títulos no leitor."""

TELEGRAM = "t.me/r36sbr"

# A versão em uso vem do arquivo VERSION; a lista abaixo é o histórico.
NOVIDADES = [
    ("1.0.0", "26/10/2026", [
        "Primeira versão do Omni36OS, nascido da Sab 1.10: tudo que ela fazia (verificação, bateria, som, tela, "
        "desempenho, cartões, pendrive, RetroArch, teste de ports, backup) com nome, ícone e pastas próprios.",
        "Tela inicial do console: o Omni36OS abre no boot, antes do ES (sempre ou só com alertas); B vai para o ES "
        "e sair do ES volta para o Omni36OS. Segure B no boot para o BaRT ou L1 para pular.",
        "Atalho L3+R3: segure os dois analógicos por 1 s para abrir o Omni36OS no menu do ES; no modo beta, "
        "também por cima dos jogos.",
        "Tema claro e tema escuro (Ajuda > Tema).",
        "Instala ao lado da Sab sem conflito: pastas, configurações e serviços com nomes próprios.",
    ]),
]

MANUAL = """# O que é o Omni36OS
O Omni36OS é um assistente para o R36S com dArkOS. Ele verifica bateria, som, tela, processador e cartões, aponta o que está errado e corrige com um botão.
Ele não usa internet nem inteligência artificial: são verificações e scripts fixos.

# Como usar
Direcional ou analógico: andar pelos cards e opções.
A: abrir ou confirmar. B: voltar. Select + Start: fechar o Omni36OS.
L1/R1: rolam o diagnóstico (painel da esquerda) quando ele não cabe; "L1: N acima" e "R1: mais N" mostram o que está escondido. No manual e nas listas, L1/R1 pulam de bloco em bloco.
Nas opções de valor (volume, brilho, modo do processador), use esquerda e direita.
Se os seus botões A e B forem trocados no ES, o Omni36OS segue a mesma troca.

# Pontos de alerta
Um ponto amarelo (aviso) ou vermelho (problema) em um card mostra quantas coisas precisam de atenção ali. Abra o card para ver a causa.
Quando há conserto, ele aparece no topo das ações com a etiqueta SUGERIDO.
As verificações rodam na tela de carregamento. Depois de uma ação, o card verifica de novo sozinho; "Verificar de novo" força uma nova leitura.

# Verificar
Resumo geral: bateria, temperatura, som, espaço, overclock, cartões e serviços do sistema numa tela só.
"Testar o controle" e "Consertar atalhos" abrem as ferramentas do dArkOSen; o Omni36OS volta quando elas fecham.
Serviços que falham no boot aparecem aqui. A falha do dmc-governor (ajuste da RAM) tem conserto com um botão; a do systemd-remount-fs é conhecida e inofensiva no dArkOSen.

# Bateria
Mostra a carga da bateria e se está carregando. Ajuste o brilho e o modo do processador para a bateria durar mais.
"Calibrar a bateria" abre a ferramenta de calibração do dArkOSen: o Omni36OS fecha, a ferramenta abre em tela cheia e, ao terminar, o Omni36OS volta no card Bateria. Calibre quando a porcentagem pular ou o aparelho desligar com carga sobrando.

# Som
Volume e saída de som. "Restaurar áudio" volta a saída padrão, a configuração de som do sistema e o volume para 40%.

# Tela e sistema
Brilho e o modelo da sua tela. "Detalhes da tela" diz qual opção escolher no SELECT MODEL ao atualizar o dArkOS, e avisa se o aparelho é um clone.
Gamma: deixa a imagem mais clara (abaixo de 1.0) ou mais escura e contrastada (acima de 1.0). Vale na hora e fica salvo para o boot; as teclas de atalho de gamma do dArkOSen continuam a partir do valor escolhido.
Cor do LED: verde ou vermelho, também no boot. Com a bateria em 10% ou menos, o LED pisca.
"Informações do sistema", "Tela de boot" e "Backup e migração" abrem as ferramentas do dArkOSen em tela cheia; o Omni36OS fecha antes e volta quando elas fecham.

# Desempenho
Modo do processador: Economia, Equilibrado ou Máximo. A escolha fica salva em /etc/cpu-settings.conf, o mesmo arquivo do CPU Manager e do R36 Tuner, e vale no boot e depois de jogar.
Limite do processador: 1296 MHz é o padrão. De 1368 a 1512 MHz é overclock (OC).
Limite da GPU: 520 MHz é o padrão; 600 MHz é overclock.
O overclock só é liberado com o aparelho abaixo de 70 °C. Se ele esquentar com o OC ligado, o Omni36OS sugere voltar ao padrão.
O painel também mostra os limites atuais e a ZRAM (memória comprimida que ajuda nos jogos pesados).
"Cartões SD" abre a página dos cartões (veja abaixo). B volta para Desempenho.

# Pendrive USB
Liga o modo pendrive: com o cabo de dados no PC, a partição de jogos (ou a do sistema) aparece como um pendrive para copiar ROMs.
Ligar e desligar reinicia o aparelho. Enquanto estiver ligado, o Wi-Fi e o teclado USB não funcionam, porque usam a mesma porta.
Ao tirar o cabo ou ejetar no PC, o console monta a partição de novo e volta ao ES. Para sair sem o PC, aperte B ou Select + Start.
"Restaurar boot" volta o arquivo de boot original se algo der errado.
"Limpar lixo do Mac" apaga os arquivos ._ e .DS_Store que o macOS cria ao copiar. Eles aparecem como jogos fantasmas no ES. A busca leva até um minuto.
Se o USB Network Mode estiver ligado, o Omni36OS avisa: ele usa a mesma porta e precisa ser desligado antes.

# Cartões SD (dentro de Desempenho)
Fica no card Desempenho, no botão "Cartões SD". Os alertas dos cartões aparecem no ponto do card Desempenho.
Marca, tamanho, espaço livre e velocidade dos cartões. "Testar velocidade" leva até um minuto. Cartões genéricos sem marca costumam ser lentos e falhar mais.
O Omni36OS avisa quando um cartão passa de 90% de uso ou tem menos de 1 GB livre.
"Verificar e reparar o cartão de jogos" reinicia o aparelho e roda o reparo do dArkOSen (fsck.exfat) com o cartão desmontado. Depois o resultado aparece neste card, e o log fica em /boot/sd2_scan.log.

# RetroArch
Mostra o que foi mudado na configuração do RetroArch e restaura a de fábrica. Uma cópia da configuração atual fica guardada antes.
"Gerenciador do RetroArch" e "Restaurar opções dos cores" abrem as ferramentas do dArkOSen (o Omni36OS volta quando elas fecham).

# Testar ports
Mostra os ports da pasta que o ES exibe na lista de Ports. O ArkOS guarda os jogos em /roms2 (cartão de jogos) ou em /roms (cartão do sistema); o Omni36OS lê qual está em uso no es_systems.cfg e ignora a outra.
Escolha um port e aperte A: o Omni36OS fecha, o port abre como se fosse pelo ES e, depois de 15 segundos, é encerrado sozinho. O Omni36OS volta com o resultado.
Passou: o port ficou aberto os 15 segundos.
Falhou: o port fechou antes. O relatório fica em omni36os/logs/<nome do port>/ (dentro de /roms2/ports/omni36os) com a saída do port, os logs da pasta dele, as mensagens do kernel e o estado do sistema.
A lista mostra o último resultado de cada port, e as falhas viram alerta no card.
"Limpar avisos de falha" tira o alerta do card depois que você já viu as falhas. O resultado continua na lista até o port ser testado de novo; se o novo teste falhar, o aviso volta.
Ports com menu próprio (como Daytona USA e NFSU1) passam quando o menu abre: o teste não aperta botões.

# Mostrar no console (port ou sistema)
Na primeira vez que abre, o Omni36OS pergunta onde aparecer:
Lista de Ports: junto com os outros ports (o atalho Omni36OS.sh fica na pasta de ports).
Sistema no console: uma entrada própria "Omni36OS" no menu principal do console (o atalho fica em /roms2/omni36os/ e sai da lista de Ports).
Para trocar depois: Ajuda > Mostrar no console. A troca muda o es_systems.cfg (com backup em es_systems.cfg.omni36os-bak) e o ES reinicia quando o Omni36OS fecha. Nessa hora o Omni36OS também põe o ícone e a descrição dele na lista do ES e o logo do sistema no tema ativo (pasta omni36os/ do tema).
Se o seu tema não tiver arte para "Omni36OS", o ES mostra o nome em texto.

# Backup
Ajuda > Backup > escolha o módulo > Exportar ou Importar.
Omni36OS: resultados dos testes de ports e os ajustes de processador, GPU, RAM e gamma. O modo de exibição não entra: ele depende do ES de cada console.
RetroArch: retroarch.cfg, opções dos cores, configurações por jogo/core, remapeamentos, playlists e overlays (RetroArch e RetroArch32).
Emuladores standalone: DuckStation, Flycast, GZDoom, LZDoom, ECWolf, Mupen64Plus, PPSSPP, ScummVM, DraStic e retrorun.
EmulationStation: es_settings.cfg, controles, coleções, gamelists e scripts.
Exportar grava um .tar.gz em /roms2/backup/omni36os (no cartão de jogos: dá para copiar pelo modo pendrive). O caminho completo aparece ao terminar.
Importar abre a pasta dos backups; navegue pelas pastas com A ("..": voltar). Cada arquivo mostra de qual módulo é, e só o backup do módulo certo pode ser importado.
Antes de importar, o Omni36OS salva o que está valendo agora como "...-antes-de-importar.tar.gz".
Só configurações: saves, estados, cores, shaders, temas e bancos de dados ficam de fora.

# Ajuda
Este manual, os cuidados, as novidades de cada versão e os créditos.
"Tema": escuro ou claro, vale na hora e fica salvo.
"Tela inicial do console": Desligada (o console abre no ES, como sempre), Omni36OS no boot (o Omni36OS abre antes do ES; B na tela inicial vai para o ES e sair do ES volta para o Omni36OS) ou Só com alertas (o Omni36OS só abre no boot se a bateria estiver fraca, o console quente, um serviço falhando ou um cartão cheio). Vale a partir do próximo boot. No boot, segure B para o BaRT do dArkOSen ou L1 para pular o Omni36OS.
"Atalho L3+R3": segure os dois analógicos apertados por 1 s. No menu do ES, o Omni36OS abre e o ES volta quando ele fecha. Em "Menu e jogos (beta)", também dentro de um jogo: o jogo congela, o Omni36OS abre por cima e o jogo continua quando ele fecha (alguns emuladores não soltam a tela; aí o jogo volta na hora). Por cima de um jogo, testes de port e ferramentas de tela cheia ficam bloqueados.
"Restaurar o ES": "Só reiniciar" recarrega o menu do console quando o Omni36OS fecha (para um ES travado ou lista desatualizada). "Desfazer o Omni36OS" tira o sistema próprio, o ícone, a descrição e o logo que o Omni36OS pôs no ES (inclusive a tela inicial e o atalho), e ele volta para a lista de Ports."""

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
O Omni36OS não libera o overclock com o aparelho acima de 70 °C.

# Bateria e calor
Evite o modo Máximo com a bateria fraca ou o aparelho quente.
Com a bateria fraca, carregue antes de usar o pendrive ou atualizar.

# Cartões
Cartões genéricos falham mais. Se um cartão aparecer como lento ou sem marca, mantenha backup dos seus saves.

# Teste de ports
O teste abre o port de verdade e o encerra à força depois de 15 segundos. Ports que gravam configuração ou save logo ao abrir podem perder o que estava sendo gravado; teste com o save já em backup.
Durante o teste não aperte botões: o port recebe os comandos.
Se o port travar a tela, segure o botão de ligar para reiniciar; o resultado não é gravado nesse caso.

# Backup e importação
Importar substitui as configurações do módulo pelas do arquivo. Use backups da mesma versão do dArkOS: configurações de outra versão podem não funcionar.
Depois de importar o EmulationStation, o ES reinicia quando o Omni36OS fechar; não desligue o console nessa hora.
Guarde cópias dos backups fora do console (no PC, pelo pendrive).

# Ao fechar
Saia do Omni36OS com B ou Select + Start, nunca desligando o console direto: ao sair, o dArkOS devolve as configurações de som e do processador."""

CREDITOS = """# Omni36OS
Assistente do R36S, feita por mpjsilva.

# Origem
O Omni36OS nasceu da Sab, o assistente do R36S feito em homenagem a Sabrina Broch, youtuber que fala de ports do R36S. Omni (tudo) + R36S: a mesma ajuda, agora tomando conta do console inteiro.

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
