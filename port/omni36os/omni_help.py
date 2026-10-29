"""Textos do card Ajuda: manual, cuidados, novidades e créditos.
Linhas que começam com "# " viram títulos no leitor."""


# A versão em uso vem do arquivo VERSION. Aqui fica só ela; o histórico completo está no NOVIDADES.md.
NOVIDADES = [
    ("1.8.0", "29/10/2026", [
        "Ajuda > Procurar atualização: baixa a versão nova do GitHub, confere tudo antes de instalar e guarda "
        "a de agora. Se a nova não abrir em 3 tentativas, a anterior volta sozinha; \"Voltar à versão "
        "anterior\" faz o mesmo a pedido.",
        "Bateria no fim: aviso em 5% e, em 2%, o jogo é fechado com tempo de salvar e o console desliga com "
        "segurança, em vez de apagar de repente.",
        "Wi-Fi: ligar e desligar mexem só no rádio, sem derrubar o modo pendrive nem a rede USB.",
        "Verificar e reparar os jogos não repara mais uma partição que não desmontou de verdade (o reparo "
        "nela podia estragar o cartão).",
        "Testes automáticos rodam antes de cada mudança no código do Omni36OS.",
    ]),
]

MANUAL = """# O que é o Omni36OS
O Omni36OS é um assistente para o R36S com Omni36OS. Ele verifica bateria, som, tela, processador e cartões, aponta o que está errado e corrige com um botão.
Ele não usa internet nem inteligência artificial: são verificações e scripts fixos.

# Como usar
Direcional ou analógico: andar pelos cards e opções.
A: abrir ou confirmar. B: voltar. O botão de power abre Energia (suspender, reiniciar, desligar).
L1/R1: rolam o diagnóstico (painel da esquerda) quando ele não cabe; "L1: N acima" e "R1: mais N" mostram o que está escondido. No manual e nas listas, L1/R1 pulam de bloco em bloco.
Nas opções de valor (modo do processador, limites), use esquerda e direita. Em Sistema, as barras (volume, brilho, contraste) e as escolhas mudam com o analógico esquerdo, e o direcional só navega.
Cada página explica a opção escolhida no topo do painel da esquerda (lâmpada roxa).
Se os botões A e B estiverem trocados no sistema, o Omni36OS segue a mesma troca.

# Pontos de alerta
Um ponto amarelo (aviso) ou vermelho (problema) em um card mostra quantas coisas precisam de atenção ali. Abra o card para ver a causa.
Quando há conserto, ele aparece no topo das ações com a etiqueta SUGERIDO.
As verificações rodam na tela de carregamento. Depois de uma ação, o card verifica de novo sozinho; "Atualizar status" força uma nova leitura.

# Verificar
Resumo: mostra só o que precisa de atenção em todos os cards (bateria, sistema, desempenho, cartões e serviços), cada linha com o card de origem. Sem alertas, aparece "Tudo certo". O detalhe fica em cada card.
"Testar o controle" mostra o R36S com cada botão aceso ao apertar, os gatilhos L2/R2 e a posição dos analógicos. Para sair, segure SELECT + START por 1 segundo (B também é testado).
"Consertar atalhos" reinicia o serviço que cuida do brilho e do volume pelos botões.
"Detalhes da tela" mostra o modelo da sua tela, diz qual opção escolher no SELECT MODEL ao atualizar o Omni36OS e avisa se o aparelho é um clone.
Serviços que falham no boot aparecem aqui. A falha do dmc-governor (ajuste da RAM) tem conserto com um botão; a do systemd-remount-fs é conhecida e inofensiva no Omni36OS.

# Bateria
Mostra a carga, se está carregando, o brilho e o modo do processador. Com o brilho alto ou o processador no máximo, aparece a dica de economia com um botão. O brilho se ajusta em Sistema e o processador em Desempenho.
Bateria no fim: em 5% aparece um aviso (num jogo, o contador surge com a bateria em vermelho). Em 2%, sem o carregador, o Omni36OS fecha o jogo dando tempo de ele salvar, grava tudo e desliga, em vez de o console apagar de repente.
"Calibrar a bateria" abre a página da calibração. Calibre quando a porcentagem pular ou o aparelho desligar com carga sobrando:
1. Carregue até o fim e tire o carregador.
2. Toque em "Iniciar a calibração" e use o console normalmente (pode jogar) até ele desligar sozinho. Uma amostra por minuto fica gravada em /usr/local/etc/battery-cal.
3. Ligue, carregue e toque em "Aplicar a curva". A porcentagem passa a seguir a sua bateria.
"Voltar à curva de fábrica" desfaz.

# Sistema
Som, tela e segurança num card só, nesta ordem: Volume, Brilho e Contraste. As barras mudam com o analógico esquerdo; o direcional navega entre os itens e troca de coluna.
Volume: o som do console. "Restaurar áudio" conserta o som quando ele some ou sai pelo lugar errado: põe de volta o arquivo de som do sistema (.asoundrc), aponta a saída para o alto-falante/fone certo deste modelo e deixa o volume em 40%.
Brilho: a luz da tela.
Contraste: barra de 0 a 100% (50% é o normal, gamma 1.0); acima de 50% a imagem fica mais contrastada, abaixo mais clara. Vale na hora e fica salvo para o boot; as teclas de atalho de gamma do sistema continuam a partir do valor escolhido.
Cor do LED: verde ou vermelho, também no boot. Com a bateria em 10% ou menos, o LED pisca.
"Redefinir o sistema" (último item): volta ao primeiro boot. Apaga o nome do jogador, a trava por senha e o tema, desliga a memória extra (zram) e volta processador (Equilibrado, 1296 MHz), GPU (520 MHz), atalhos e botão de power ao padrão; depois pergunta o nome de novo. Ports, jogos, testes e as senhas do sistema e do Samba ficam.

"Nome do jogador": aparece na saudação do menu. "Tema": escuro ou claro, vale na hora e fica salvo.
"Wi-Fi": liga e desliga o adaptador, "Procurar redes" lista as redes por perto (com cadeado pede a senha no teclado; START confirma), "Redes salvas" conecta de novo ou esquece uma, "Desconectar" sai da rede atual. O painel mostra a rede, o sinal e o IP do console, e se atualiza sozinho.
"Atalhos": combinações com o botão FN que valem dentro dos jogos (veja Atalhos abaixo).
"Backup": exporta e importa as configurações do Omni36OS (veja Backup abaixo).

# Atalhos (dentro de Sistema)
Valem com um port aberto. Cada atalho tem Ligado ou Desligado na página, e os botões abaixo são os que estão valendo agora:
«fps»: mostra ou esconde o contador. Ele fica no canto de cima e mostra quadros por segundo, temperatura e bateria. O FPS fica verde de 50 para cima, amarelo de 28 a 49 e vermelho abaixo disso. A temperatura fica amarela a partir de 65 °C e vermelha a partir de 75 °C. A bateria fica amarela até 30% e vermelha até 15%; carregando, aparece um raio verde.
«limite»: liga ou desliga o limite de 30 FPS. Em jogo leve, economiza bateria e esquenta menos. Um traço roxo no contador mostra que o limite está ligado.
«captura»: captura de tela na pasta imagens dentro da pasta do jogo (ex.: ports/daytona/imagens), em .bmp com o nome do port e a hora, sem o contador. Vale em qualquer cartão. Aparece "CAPTURA SALVA" no canto.
«fechar» (segure 1 s): fecha o jogo e volta ao Omni36OS. Serve para port travado ou sem opção de sair. Este é fixo.
"Personalizar um atalho": escolha o atalho e aperte a tecla nova; ele vira FN + essa tecla. O Omni36OS recusa o que já é do sistema ou de outro atalho. "Voltar aos botões padrão" desfaz (FN + X, FN + B e FN + Y).
Pelo botão de power, com um jogo aberto: o jogo congela e o menu Energia abre por cima com as mesmas opções (mostrar o contador, limitar a 30 FPS, captura de tela e fechar o jogo), além de suspender, reiniciar e desligar. Captura e contador valem quando o jogo volta.
O sistema (ogage) já usa: FN + cima/baixo e FN + volume para o brilho; FN com L1/R1, esquerda/direita, A, L3 e R3 para ajustes do sistema; SELECT + FN fala a bateria; FN + power é o modo pânico.
O contador, o limite e a captura funcionam em ports que desenham com OpenGL ES (a maioria). Ports em 32 bits ou que trocam o LD_PRELOAD não mostram o contador.

# Segurança (dentro de Sistema)
Tudo o que é senha fica aqui. B volta para Sistema.
"Trocar a senha" muda a senha do usuário ark (SSH, SFTP e Samba) com o teclado na tela: direcional escolhe, A digita, B apaga, START confirma e SELECT cancela. A senha é pedida duas vezes.
"Senha do Samba" redefine só a senha das pastas compartilhadas (usuário ark), sem mexer na do SSH.
"Trava por senha": com ela ligada, o console pede a senha ao ligar, antes de mostrar os jogos (o botão de power ainda abre Energia para desligar). A senha fica em texto simples em EASYROMS/senha/senha.txt: esqueceu, abra o cartão no PC e leia. Apagar esse arquivo desliga a trava. Para desligar pelo console, a senha atual é pedida.

# Desempenho
Modo do processador: Economia, Equilibrado ou Máximo. A escolha fica salva em /etc/cpu-settings.conf, e vale no boot e depois de jogar.
Limite do processador: 1296 MHz é o padrão. De 1368 a 1512 MHz é overclock (OC).
Limite da GPU: 520 MHz é o padrão; 600 MHz é overclock.
O overclock só é liberado com o aparelho abaixo de 70 °C. Se ele esquentar com o OC ligado, o Omni36OS sugere voltar ao padrão.
Memória extra (zram): desligada por padrão. 256, 512 ou 768 MB de memória comprimida na RAM, que segura ports pesados que fecham por falta de memória. Vale na hora e nos próximos boots; custa um pouco de processador.
"Liberar overclock" mexe no arquivo de hardware do boot (DTB): libera as frequências de 1368 a 1512 MHz e a GPU de 600 MHz. Tem trava: aviso vermelho com contagem e depois A apertado 5 vezes. Antes de mudar, o Omni36OS guarda uma cópia do DTB. Vale depois de reiniciar; o limite se escolhe em "Limite do processador" e "Limite da GPU".

# USB
Liga o modo pendrive: com o cabo de dados no PC, a partição /roms2 (segundo cartão) ou /roms (cartão do sistema) aparece como um pendrive para copiar ports.
Ligar e desligar reinicia o aparelho. Enquanto estiver ligado, o Wi-Fi não funciona, porque usa a mesma porta.
Ao conectar o PC, o Omni36OS fecha para soltar a partição. Ao tirar o cabo ou ejetar no PC, o console monta a partição de novo e o Omni36OS volta. Para sair sem o PC, aperte B ou Select + Start.
"Restaurar boot" volta o arquivo de boot original se algo der errado.
"Limpar lixo do Mac" apaga os arquivos ._ e .DS_Store que o macOS cria ao copiar. Eles aparecem como ports fantasmas na biblioteca. A busca leva até um minuto.
"Montar pendrive" monta um pendrive ligado no OTG em /mnt/usbdrive (FAT, exFAT ou NTFS). Com ele montado, o mesmo botão vira "Desmontar pendrive": use antes de tirar.
"Rede pelo cabo USB": o console vira uma placa de rede no cabo.
- Modo universal: o console dá o IP ao PC. No PC: ssh ark@10.44.44.1.
- Internet pelo PC: o PC compartilha a internet pelo cabo e o console recebe o IP dele.
- Serviços remotos: liga o Samba e o navegador web de arquivos (usuário e senha: ark).
A página mostra o IP e os comandos para o PC, e se atualiza sozinha. A rede USB e o modo pendrive usam a mesma porta: desligue um antes de ligar o outro.

# Cartões SD
Card próprio (no lugar do antigo card Jogos).
"Jogos lidos de": ROMS (cartão do sistema), ROMS2 (segundo cartão) ou ROMS e ROMS2. Ao sair da página depois de trocar (B ou START), o Omni36OS procura os jogos e os ports de novo, uma vez só, e atualiza a biblioteca e o Testar ports. Com as duas, o mesmo sistema dos dois cartões vira uma lista só. ROMS2 só entra se o segundo cartão estiver no console.
Marca, tamanho, espaço livre e velocidade dos cartões. "Testar velocidade" leva até um minuto. Cartões genéricos sem marca costumam ser lentos e falhar mais.
O Omni36OS avisa quando um cartão passa de 90% de uso ou tem menos de 1 GB livre.
"Verificar e reparar os jogos" reinicia o aparelho e roda o reparo do Omni36OS (fsck.exfat) com o cartão desmontado. Depois o resultado aparece neste card, e o log fica em /boot/sd2_scan.log (segundo cartão) ou /boot/sd1p3_scan.log (só o cartão do sistema).


# Ports (primeiro card)
O console liga nos cards, com Ports já escolhido: A abre a biblioteca. É uma lista só, com os favoritos primeiro e o resto por nome. Cima/baixo escolhem o port, esquerda/direita pulam de 10 em 10 e L1/R1 pulam de letra. Ao lado aparece a ficha do jogo (capa, estúdio, data, gêneros e descrição); A abre o port e, ao fechar, a lista volta no mesmo lugar.
B volta para os cards. O botão de power abre Energia: suspender, reiniciar ou desligar.
A ficha vem da pasta info do port (info.json, imagem e .txt), e depois do PortMaster e da Steam, buscados uma vez com Wi-Fi e guardados no cartão.

# Ferramentas
"Arquivos": navega pelos cartões (/roms, /roms2) e pelo pendrive. A abre a pasta, B sobe um nível, X abre as opções do item (copiar, mover, renomear, apagar) e START abre as opções da pasta (colar aqui, nova pasta). Para copiar: X > Copiar no item, vá até a pasta de destino e START > Colar aqui.
"PortMaster" e "351Files" abrem em tela cheia; o Omni36OS volta quando eles fecham.
As outras ferramentas do sistema ficam nos cards: Testar o controle (Verificar), Trocar a senha (Sistema), rede USB e pendrive (USB), Calibrar a bateria (Bateria), Liberar overclock (Desempenho). Tudo o que mexe no boot abre um aviso vermelho com contagem; Cancelar fica escolhido desde o início.

# Testar ports (dentro de Ferramentas)
Mostra os ports das pastas escolhidas em Cartões SD > Jogos lidos de.
Escolha um port e aperte A: o Omni36OS fecha, o port abre como pela biblioteca e, depois de 15 segundos, é encerrado sozinho. O Omni36OS volta com o resultado.
Passou: o port ficou aberto os 15 segundos.
Falhou: o port fechou antes. O relatório fica em omni36os/logs/<nome do port>/ (dentro de /opt/omni36os) com a saída do port, os logs da pasta dele, as mensagens do kernel e o estado do sistema.
A lista mostra o último resultado de cada port, e as falhas viram alerta no card.
"Limpar avisos de falha" tira o alerta do card depois que você já viu as falhas. O resultado continua na lista até o port ser testado de novo; se o novo teste falhar, o aviso volta.
Ports com menu próprio (como Daytona USA e NFSU1) passam quando o menu abre: o teste não aperta botões.
Quando o port falha, o Omni36OS lê o relatório e mostra a causa provável (script do Windows, arquivo sem permissão, falta de memória, runtime do PortMaster, biblioteca, glibc, arquivos do jogo, cartão exFAT, travamento). Se houver conserto seguro, aparece "Corrigir e testar de novo": ele corrige (permissão, formato dos scripts ou memória extra) e testa outra vez. Se ainda falhar, a correção é desfeita. O diagnóstico também fica no relatório.

# Backup
Sistema > Backup > Exportar ou Importar.
Omni36OS: resultados dos testes de ports e os ajustes de processador, GPU, RAM e gamma. Os atalhos e o tema não entram.
Exportar pergunta onde salvar: cartão do sistema (/roms/backup/omni36os), segundo cartão (/roms2/backup/omni36os) ou pendrive (/mnt/usbdrive/backup/omni36os). Só aparece o que está no console agora, e o último lugar escolhido vem marcado. O caminho completo aparece ao terminar.
Importar abre a pasta dos backups; navegue pelas pastas com A ("..": voltar). Cada arquivo mostra de qual módulo é, e só o backup do módulo certo pode ser importado.
Antes de importar, o Omni36OS salva o que está valendo agora como "...-antes-de-importar.tar.gz".
Só configurações: saves, estados, cores, shaders, temas e bancos de dados ficam de fora.

# Ajuda
Este manual, os cuidados, as novidades de cada versão, os créditos (com os projetos usados como base) e o botão de power.
"Botão de power": Menu de energia (um toque abre Cancelar, Suspender, Reiniciar e Desligar; outro toque com o menu aberto desliga com segurança) ou Como no Omni36OS (suspende, ou desliga se a opção de trocar power e suspender estiver ligada). Com o menu ligado, FN + power é o modo pânico: fecha o que estiver na tela, tira o overclock, põe o processador no modo normal, sobe o brilho se estiver quase apagado e abaixa o som se estiver no máximo. Duas vezes em menos de 10 s, o console grava tudo e reinicia. Segurar o power por uns 8 s sempre desliga à força: isso é do chip de energia, não do Omni36OS. O botão de reset reinicia por hardware e não pode ser mudado.
"Procurar atualização" (precisa de Wi-Fi): procura uma versão nova no GitHub. Antes de instalar, o Omni36OS baixa e confere tudo; a versão de agora fica guardada. Se a nova não chegar ao menu em 3 tentativas, a anterior volta sozinha e um aviso explica. "Voltar à versão anterior" aparece depois de uma atualização e troca de volta a pedido. Deixe o carregador ligado durante a atualização."""

CUIDADOS = """# Antes de qualquer coisa
Faça backup do cartão do sistema no PC de vez em quando. Uma imagem do cartão inteiro salva você de quase qualquer problema.

# Pendrive USB
Sempre ejete o pendrive no PC antes de tirar o cabo. Tirar no meio de uma cópia pode corromper os arquivos.
Não desligue o console enquanto ele estiver ligado no PC.
Com segundo cartão, prefira compartilhar /roms2. Sem ele, o PC recebe /roms (a partição de jogos do cartão do sistema): copie só para as pastas de jogos e ports.
Se o console não voltar ao normal, use "Restaurar boot" no card USB.
Não ligue a rede USB e o modo pendrive ao mesmo tempo.

# Verificar e reparar o cartão
O aparelho reinicia e passa alguns minutos verificando. Não desligue nem tire o cartão nessa hora.
O reparo apaga entradas corrompidas: se o cartão já estava com erros, algum arquivo danificado pode sumir. Tenha backup.

# Restaurar e atualizar
"Restaurar de fábrica" do RetroArch apaga os seus ajustes (uma cópia fica guardada).
Antes de atualizar o Omni36OS, copie a partição BOOT do cartão para o PC e veja em Verificar > "Detalhes da tela" qual modelo escolher.

# Overclock
Overclock é usar o chip acima do que a fábrica garante. Pode causar travamentos e, com o tempo, desgaste maior.
O kernel do Omni36OS protege o aparelho: freia a 70 °C, limita a 85 °C e desliga a 115 °C. Mesmo assim, se travar ou fechar jogos sozinho, volte para 1296 MHz (CPU) e 520 MHz (GPU).
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
Importar substitui as configurações do módulo pelas do arquivo. Use backups da mesma versão do Omni36OS: configurações de outra versão podem não funcionar.
Guarde cópias dos backups fora do console (no PC, pelo pendrive).

# Ao desligar
Desligue pelo menu Energia (botão de power), nunca segurando o power: pelo menu, o Omni36OS grava tudo e desmonta o boot antes de desligar.
Para fechar um port travado, use SELECT + START (segure 1 s) antes de pensar em desligar à força."""

CREDITOS = """# Omni36OS
Assistente do R36S, feita por mpjsilva.

# Origem
O Omni36OS nasceu da Sab, o assistente do R36S feito em homenagem a Sabrina Broch, youtuber que fala de ports do R36S. Omni (tudo) + R36S: a mesma ajuda, agora tomando conta do console inteiro.

# Projetos usados como base
ArkOS, de christianhaitian: o sistema original do R36S e de vários portáteis RK3326. github.com/christianhaitian/arkos
dArkOS, de christianhaitian: o ArkOS sobre Debian. github.com/christianhaitian/dArkOS
dArkOSen, de djparent: a imagem usada como base do Omni36OS, e a ferramenta de calibração da bateria e o patch do DTB que o Omni36OS reescreveu. github.com/djparentx
PortMaster: a loja de ports. github.com/PortsMaster/PortMaster-GUI

# Bibliotecas
Fonte Poppins, licença OFL: github.com/itfoundry/Poppins
Ícones Tabler, licença MIT: github.com/tabler/tabler-icons"""


def novidades_text():
    out = []
    for ver, data, itens in NOVIDADES:
        out.append(f"# Versão {ver} ({data})")
        out += [f"• {i}" for i in itens]
        out.append("")
    return "\n".join(out).strip()



def manual(combos=None):
    """O manual com os botões dos atalhos que estão valendo (Sistema > Atalhos)."""
    import omni_combos
    combos = combos or omni_combos.defaults()["combos"]
    text = MANUAL
    for k in omni_combos.ACTIONS:
        text = text.replace(f"«{k}»", omni_combos.text(combos[k]))
    return text
