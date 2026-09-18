# Narração

Estado da integração de áudio: o que existe, o que mudou nesta rodada e o que
falta você fazer.

---

## O que já estava pronto

A infraestrutura inteira. `AudioPlayerManager` com playback, Now Playing e
Remote Command Center; `MiniPlayerView` persistente acima da tab bar;
`MainTabView` ligando auto-play do próximo capítulo e sincronia com o
`LibraryProgress`; `ReaderView` com destaque de sentença; `UIBackgroundModes:
audio` no Info.plist.

Faltava exatamente uma coisa para tudo isso sair do papel: **os arquivos**.
`Content/Audio/` não existia.

---

## O elo que faltava: chunks → timings

A geração de áudio produz `<slug>-ch<N>.chunks.json`. O app lê
`<slug>-ch<N>.timings.json`. São formatos diferentes:

| | chunks.json | timings.json |
|---|---|---|
| unidade | pedaço de TTS, ~1400 chars, ~90s | sentença, ~3s |
| índice | por chunk | global no capítulo |
| origem do tempo | **medido** (é onde os MP3 foram concatenados) | derivado |

Os 150 `.timings.json` já estão em `Content/Audio/`, gerados dos seus chunks
e das suas histórias por `scripts-pedagogy/chunks_to_timings.py`.

**Por que isso é melhor que o `generate_timings.py` anterior.** O script
antigo estimava o capítulo inteiro por contagem de caracteres, de ponta a
ponta. Como a locução varia de 9 a 20 caracteres por segundo conforme o
trecho seja diálogo curto ou narração corrida, o erro ia somando e no fim do
capítulo podia passar de dez segundos. Aqui a conta é reancorada em cada
fronteira de chunk, que é timestamp medido: o erro nunca escapa do chunk em
que nasceu.

**Verificações que passaram nos 150 capítulos:**

- Todas as 14.980 sentenças do catálogo foram encontradas no texto narrado.
  Nenhuma aproximação, nenhum fallback.
- A contagem de sentenças bate exatamente com a que o `SentenceSplitter` do
  `ReaderView` calcula, nos 150. É isso que garante que o índice destacado é
  o certo.
- Cobertura contínua: sem buracos entre sentenças (buraco faria
  `sentenceIndex(atMs:)` devolver nil e o destaque piscar).
- Taxa implícita de locução entre 9,1 e 20,6 caracteres/segundo, mediana
  15,2, **zero** sentenças fora da faixa plausível. Se houvesse
  desalinhamento, apareceria aqui como sentença de 5 caracteres durando 20
  segundos.
- Os timestamps dos chunks conferem com a duração real dos MP3 medida com
  `ffprobe`: diferença de 0 ms nos 150.

**Precisão honesta:** exata a cada ~90s (fronteira de chunk), 1 a 3 segundos
de erro nas sentenças do meio de um chunk, sem acumular. Boa para acompanhar
a leitura. Insuficiente para karaokê palavra a palavra — isso exigiria
timestamps por palavra, que o Flux não devolve.

---

## O que mudou no código

### `AudioPlayerManager.swift`

**Sessão ativada no primeiro play, não no launch.** Era o furo mais caro:
`setActive(true)` no `init()` toma o foco de áudio do sistema, ou seja, abrir
o Pedagogy pra ver a Home calava o Spotify de quem nem ia ouvir narração.
Agora o `init` só descreve a categoria (barato, sem efeito colateral) e a
ativação acontece no `play()`. O `stop()` devolve o foco com
`.notifyOthersOnDeactivation`, que faz o app anterior voltar sozinho.

De quebra, o comentário do Info.plist que já citava
`configureAudioSession()` virou verdade — o método existe agora.

**Política `.longFormAudio`.** Marca o app como conteúdo de forma longa, como
audiolivro e podcast. Ganha roteamento AirPlay 2 correto: dá pra mandar a
narração pro HomePod da sala sem espelhar a tela.

**Interrupções.** Não havia tratamento. Na prática: ligação recebida matava a
narração e ela nunca voltava. Agora pausa no `.began` e retoma no `.ended` —
mas só se o sistema autorizar (`.shouldResume`) **e** se estava tocando
antes. Voltar sozinho depois de uma ligação de vinte minutos, com o telefone
no bolso, seria pior que ficar parado.

**Fone desconectado.** Também não havia. Tirar o fone jogava a história no
viva-voz no meio do ônibus. Agora pausa em `.oldDeviceUnavailable`.

**Velocidade.** O cabeçalho do `MiniPlayerView` já descrevia um botão de
velocidade no layout, mas ele nunca foi implementado. Agora existe:
`enableRate` no player, quatro passos (0.75× / 1× / 1.25× / 1.5×), persistido
em `UserDefaults`. O 0.75× não é enfeite — é o que faz o app servir pra quem
tem dislexia ou lê inglês como segunda língua.

O `MPNowPlayingInfoPropertyPlaybackRate` agora manda a velocidade real em vez
de 1.0 fixo. Com 1.5× e rate declarado 1.0, o relógio da tela de bloqueio
atrasa progressivamente.

**Retomada por capítulo.** Posição salva a cada 5s e no pause; reabrir o
capítulo continua de onde parou, 2 segundos atrás pra não cair no meio de uma
palavra. Zera quando o capítulo termina.

**`unload()` separado de `stop()`.** Na troca de capítulo, o `stop()` antigo
desativava a sessão e o `play()` seguinte reativava — o sistema acordava o
app anterior no intervalo, com blip audível entre um capítulo e outro. Agora
só o `stop()` do usuário devolve o foco.

### `MiniPlayerView.swift`

Botão de velocidade, à esquerda do play. Cicla 1× → 1.25× → 1.5× → 0.75×,
começando pra cima porque quem toca quer acelerar; o 0.75× fica a um toque de
voltar ao normal.

### `MainTabView.swift`

**O mini-player brigava com a tab bar.** A partir do iOS 26 a tab bar é uma
cápsula flutuante desenhada por cima do conteúdo. O `safeAreaInset(edge:
.bottom)` estava aplicado ao **TabView**, o que põe o mini-player na borda de
baixo da TELA — mesmo lugar da cápsula. Sobrava uma faixa de cada um.

Agora o `safeAreaInset` é aplicado ao **conteúdo de cada tab** (helper
`withMiniPlayer`). Ali o mini-player entra no safe area da tab, que já
desconta a altura da tab bar: encosta logo acima da cápsula e o conteúdo
encolhe sozinho pra caber.

**O `tabViewBottomAccessory` foi tentado e descartado.** É a API nativa pra
isso no iOS 26 e seria mais bonita — o acessório minimiza junto com a barra
no scroll. Mas ele reserva a cápsula de vidro pela PRESENÇA do modifier, não
pelo conteúdo: com nada tocando, o `MiniPlayerView` não renderiza nada e
mesmo assim ficava uma cápsula cinza vazia na tela.

Aplicar o modifier condicionalmente resolveria a cápsula e criaria coisa
pior: o `if` troca o galho do ViewBuilder, o TabView é recriado, e a tab
selecionada mais as NavigationStacks de dentro se perdem toda vez que o áudio
começa ou para. O `safeAreaInset` não tem esse problema — conteúdo vazio
ocupa zero.

### `ReaderView.swift`

Botão de play/pause da narração na TopBar, à esquerda do contador de
capítulos. Toca o capítulo que está na tela; vira pause quando está tocando
ESSE capítulo (tocar outra história não deixa o botão daqui em estado de
pause). Some quando o capítulo não tem MP3 no bundle.

Ficou no topo em vez de flutuando sobre o texto porque o reader é uma coluna
de leitura — botão boiando por cima tapa palavra justo quando a criança está
acompanhando.

Efeito colateral bom: como o `ChapterView` já destaca a sentença ativa, dar
play por aqui acende o read-along na hora, sem passar pela StoryDetail.

### `Models/StoryTimings.swift`

Só o comentário de precisão, que descrevia o gerador antigo.

---

## O que falta você fazer

**1. Nada, quanto aos arquivos.** Os 150 MP3 e os 150 `.timings.json` já
estão em `Content/Audio/` — 275 MB, 13,2 horas de narração. A verificação
passou: todo capítulo com áudio, timings e contagem de sentenças alinhada.

Os `.chunks.json` ficaram de fora do bundle de propósito: são insumo de
build, não recurso do app. Guarde a pasta original — é dela que os timings
são regerados quando uma história muda.

Quando gerar áudio novo:

```bash
chmod +x ~/Documents/scripts-pedagogy/install_narration_audio.sh
~/Documents/scripts-pedagogy/install_narration_audio.sh ~/Downloads/audio
```

Copia os MP3, apaga os `._nome.mp3` do Finder, regera os timings e verifica.

**2. Conferir a capability.** `Signing & Capabilities` → **Background Modes →
Audio, AirPlay, and Picture in Picture**. A chave já está no `Info.plist`, mas
você perdeu essa capability uma vez no Grimoire ao extrair zip por cima do
`project.pbxproj`. Vale o olhar de dois segundos depois de extrair.

**3. Testar no device, não no simulador.** Interrupção, fone e AirPlay não
existem no simulador. O teste mínimo: começar um capítulo, bloquear a tela
(tem que continuar), ligar pro próprio número (tem que pausar e voltar),
tirar o fone (tem que pausar).

---

## Tamanho do app — On-Demand Resources

Os 272 MB de narração **não vão mais no download da App Store**. Cada história
é uma tag de On-Demand Resources (`narration-<slug>`, ~5,5 MB com os três
capítulos) que o app baixa no primeiro Listen. Detalhes em
`pedagogy/Content/ContentPacks.swift`.

- **Tag por história, não por capítulo:** o auto-play do capítulo 2 não para
  pra baixar nada.
- **Os `.timings.json` ficam no bundle** (2,4 MB): são o índice de "este
  capítulo tem narração". `hasNarration` olha pra eles, porque o MP3 só
  aparece no bundle depois de baixado. MP3 com tag e sem timings fica
  invisível — o install nunca pode pular a etapa dos timings.
- **Na UI:** o mini-player aparece na hora com spinner e a barra mostrando o
  download; sem rede, o play vira ↻ pra tentar de novo. O Reader é full
  screen e cobre o mini-player, então o botão de narração dele mostra o
  mesmo estado.

**Depois de instalar áudio novo, rode:**

```bash
python3 scripts/tag_ondemand_resources.py
```

Ele regrava as tags no `project.pbxproj` a partir de `Content/Audio` e
`Content/Motion` (com o Xcode fechado). `--check` só confere. Arquivo sem tag
não quebra nada: vai pro bundle principal e toca normalmente — só volta a
pesar no download. Vale chamar o script no fim do `install_narration_audio.sh`.

**Testar:** rode pelo Xcode (Cmd+R). É o Xcode que serve os pacotes em
desenvolvimento; instalar o `.app` na mão com `simctl` faz todo download
falhar. O Debug Navigator → Disk mostra o estado de cada tag. Em TestFlight e
na App Store os pacotes vêm da Apple.

---

## Ideias que ficaram de fora

- **Sleep timer** ("parar em 15 min"). Cabe demais num app de hora de dormir e
  são umas 30 linhas. Ficou fora pra não inchar esta revisão.
- **Ler junto sem tocar áudio**: hoje o destaque só acontece com narração
  rodando.
- **Karaokê palavra a palavra**: precisaria de timestamps por palavra na
  geração.
