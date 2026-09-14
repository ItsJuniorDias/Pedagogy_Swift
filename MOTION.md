# Motion — capas em loop

Clipe curto rodando sobre a capa estática, em duas telas: o hero da Home
("THIS WEEK") e o header do detalhe da história.

---

## Os arquivos

`Content/Motion/<slug>.mp4` — 50 clipes, mesmo slug do `Story.id`.

| | cru (OpenRouter) | no app |
|---|---|---|
| codec | H.264 | HEVC (`hvc1`) |
| duração | 5,0 s | 4,0 s |
| resolução | 1072×858 | 1072×858 |
| áudio | nenhum | nenhum |
| peso | 267 MB | **84 MB** |

Resolução e frame rate ficaram intactos de propósito: 1072px é quase
exatamente a largura do card no 3x, e mexer nisso apareceria. O ganho veio só
da troca de codec.

Denoise foi testado e descartado — no clipe mais pesado deu 4,0 MB com e sem.
O peso aqui é movimento de verdade, não ruído de geração, então o filtro só
arriscaria borrar o traço de tinta em troca de nada.

CRF 26 é conservador com arte de linha, onde a compressão come as bordas da
tinta antes de estragar as áreas chapadas. Se no device aguentar, `--crf 28`
corta quase pela metade de novo.

---

## O loop fecha agora

O prompt pede pro modelo terminar onde começou. Ele tenta e não consegue.

Medindo: no clipe cru do whale-road, a diferença entre o último quadro e o
primeiro dá **13,5 dB** de PSNR. Dois quadros VIZINHOS quaisquer desse mesmo
material ficam entre 20 e 27 dB. Ou seja, a emenda do loop era um salto muito
maior que qualquer movimento normal — e o olho pega isso a cada 5 segundos.

O `optimize_motion.py` corrige no build, cruzando a cauda sobre a cabeça:

```
entrada (5s):   [cabeça 0-1s][miolo 1-4s][cauda 4-5s]
saída   (4s):   [cauda ✕ cabeça][miolo]
```

O primeiro quadro da saída é a cauda em t=4s; o último quadro do miolo também
é t≈4s. O loop fecha em cima do mesmo instante do vídeo original.

Resultado numa amostra de 6 clipes, cru → tratado:

```
crossings                    11,7 → 19,3 dB
river-that-remembers-names   17,6 → 27,8 dB
butterfly-garden             14,3 → 21,2 dB
honey-map                    14,2 → 23,5 dB
clockmaker-of-praha          15,1 → 20,5 dB
owl-in-the-oak               16,1 → 31,2 dB
```

Todos entraram na faixa de dois quadros vizinhos — indistinguível de
movimento comum. Custo: 1 segundo de duração.

---

## O código

**`App/Motion/MotionCatalog.swift`** — acha o arquivo no bundle e decide se é
hora de animar.

**`App/Motion/MotionCover.swift`** — a capa estática com o vídeo fundido por
cima.

### Decisões

**A capa estática nunca sai de baixo.** O vídeo entra por cima, com fade, só
depois que o `AVPlayerLayer` avisa que tem quadro pronto. Resolve três coisas
de uma vez: nada de flash preto enquanto o player carrega; se o clipe não
existir, o card é o de sempre; e quando o loop é interrompido, o que sobra é a
ilustração, não um buraco.

**`AVPlayerLooper`, não `seek(to: .zero)`.** O truque comum de observar
`AVPlayerItemDidPlayToEndTime` e voltar pro começo engasga a cada volta,
porque o seek acontece depois do item terminar. O looper mantém o próximo item
enfileirado e a emenda é do próprio AVFoundation. Somado ao crossfade gravado
no arquivo, o loop fica contínuo nos dois níveis.

**`preventsDisplaySleepDuringVideoPlayback = false`.** O default do AVPlayer é
`true` — sem essa linha, um loop decorativo de 4 segundos segura a tela do
device acesa indefinidamente.

**`isMuted = true`,** mesmo os clipes não tendo faixa de áudio. Garante que
este player jamais dispute a sessão de áudio com a narração.

**Só em duas telas.** Nada de motion na grade da Library nem nos thumbs: meia
dúzia de `AVPlayerLayer` decodificando dentro de um ScrollView é memória e
bateria queimadas por um efeito que ninguém registra num card de 160pt.

**Para sozinho em quatro situações:** view fora da tela (`onAppear`/
`onDisappear`, que em TabView disparam na troca de aba), app em background,
**Reduce Motion** ligado e **modo de baixo consumo**.

Os dois últimos não são zelo excessivo. Quem liga Reduce Motion liga por
enxaqueca, vertigem ou sensibilidade vestibular, e um loop rodando sem parar
debaixo do título é exatamente o que a configuração existe pra evitar — ainda
mais num app cujo público são crianças de 9 a 11 anos, faixa em que os pais
configuram o device justamente por isso.

---

## Instalar os clipes

Eles vêm num zip separado. Extraia e arraste a pasta `Motion` inteira pra
dentro de `pedagogy/Content/` no Finder — com o grupo sincronizado do Xcode,
não precisa arrastar nada pra dentro do projeto.

```
pedagogy/pedagogy/Content/
  Audio/      ← narração (já lá)
  Motion/     ← os 50 mp4 (arraste aqui)
  Stories/
```

Confira depois: `ls pedagogy/Content/Motion/*.mp4 | wc -l` tem que dar 50.

---

## Peso do app

| | |
|---|---|
| narração | 275 MB |
| arte | 98 MB |
| motion | 84 MB |
| **total** | **~460 MB** |

Sem a otimização seriam ~640 MB. A App Store pede confirmação pra baixar
acima de 200 MB na rede celular de qualquer forma, mas 460 é bem diferente de
640 na hora de alguém decidir se espera o wi-fi.

Se quiser cortar mais, o motion é o candidato óbvio para On-Demand Resources:
é decorativo, o app funciona inteiro sem ele, e o `MotionCatalog` é o único
lugar que resolve caminho de arquivo.

---

## Regerar

```bash
python3 generate_motion.py videos --yes                    # clipes crus
python3 optimize_motion.py output/motion --crf 26          # loop + HEVC
```

O `--limit N` processa em lotes sem prender o terminal por dez minutos;
rodar de novo continua de onde parou.
