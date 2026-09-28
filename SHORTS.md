# Curtas-metragens

Filmes originais de 3 a 8 minutos, com roteiro próprio, na aba Read da Home
(seção **Watch**). O piloto é **The Paper Whale** (~4min50s, 37 planos).

---

## Como um curta é feito

O roteiro é dado, não texto: `shorts/<slug>/film.json` tem os personagens
(descrição + prompt da folha de modelo), as vozes e a lista de planos. Cada
plano tem keyframe, movimento, som ambiente e as falas.

```
film.json ──refs──▶ folhas de modelo ──keyframes──▶ 1º quadro de cada plano
                                                    │
                          voice (TTS) ◀─────────────┤
                                                    ▼
                                   clips (image-to-video, 1º quadro fixado)
                                                    │
                                   assemble (ffmpeg) ▼
                        cartela + planos + falas + ambiente + legenda ─▶ HEVC
```

**Consistência de personagem** é o problema central de filme gerado por IA.
Resolve-se em duas travas: toda imagem de keyframe recebe as folhas de modelo
dos personagens do plano como `input_references`, e todo clipe começa
*exatamente* no keyframe (`frame_images: first_frame`). O vídeo não inventa
personagem — só anima o que já foi aprovado.

**Vozes vêm do TTS, não do modelo de vídeo.** O modelo de vídeo geraria uma
voz diferente em cada plano. O áudio dele entra só como ambiente (ondas,
vento, papel), a 30% e por baixo das falas. Por isso o roteiro é conduzido pelo
narrador e as falas em cena são curtas, com o personagem de costas ou em
plano aberto: não há sincronia labial.

---

## Rodar

```bash
python3 scripts/shorts/produce_short.py plan the-paper-whale
```

Mostra o roteiro plano a plano, o custo estimado e avisos (fala longa demais
pro plano, personagem inexistente). É grátis, então rode sempre antes.

Chave em `OPENROUTER_API_KEY` ou num `.env` na raiz (já está no .gitignore).

| etapa | o que faz | custo (piloto) |
|---|---|---|
| `refs` | 6 folhas de modelo | ~US$ 0,24 |
| `keyframes` | 37 quadros iniciais | ~US$ 1,50 |
| `voice` | 35 falas | ~US$ 0,07 |
| `clips` | 275 s de vídeo, Wan 3.0 720p | ~US$ 27,50 |
| `review` | contact sheet HTML | — |
| `assemble` | monta o filme | — |
| `publish` | copia pro app e atualiza o catálogo | — |

As etapas pagas só estimam e param. Pra gerar de verdade, passe `--yes`.

**A ordem que economiza dinheiro:**

```bash
produce_short.py refs the-paper-whale --yes
produce_short.py review the-paper-whale        # aprovar os personagens
produce_short.py keyframes the-paper-whale --yes
produce_short.py review the-paper-whale        # aprovar os 37 quadros
produce_short.py voice the-paper-whale --yes
produce_short.py clips the-paper-whale --only s01,s02,s03 --yes   # amostra
produce_short.py clips the-paper-whale --yes                      # o resto
produce_short.py review the-paper-whale
produce_short.py assemble the-paper-whale
produce_short.py publish the-paper-whale
python3 scripts/tag_ondemand_resources.py      # com o Xcode fechado
```

Uma folha de modelo errada vira 37 planos errados. As duas primeiras
revisões custam US$ 1,74 somadas e protegem os US$ 27 do vídeo.

**Refazer um plano:** edite o prompt no `film.json` e rode a etapa com
`--only s14 --force`. Refazer keyframe exige refazer o clipe desse plano.

**Retomar:** tudo é pulado se já existe. Um clipe submetido e ainda não
baixado fica em `clips/<id>.job.json`, e rodar de novo só consulta esse job
em vez de pagar outro.

**Trilha sonora:** um `music.mp3` na pasta do filme entra por baixo de tudo,
a 16%, com fade de 3 s no fim. Não há modelo de música no OpenRouter, então
ela vem de fora (licença livre ou encomenda).

---

## O arquivo final

| | |
|---|---|
| vídeo | HEVC `hvc1`, 1280×720, 24 fps, CRF 24 |
| áudio | AAC 128k, loudnorm −16 LUFS (alvo de conteúdo mobile) |
| legenda | faixa `mov_text` em inglês, das próprias falas do roteiro |
| peso | ~40–80 MB por curta |

Planos em que a fala não cabe são esticados congelando o último quadro, em
vez de cortar a voz. O `plan` avisa antes, e o `assemble` marca "(esticado)".

As cartelas de abertura e fim são desenhadas em Alfa Slab por
`render_card.swift`. O ffmpeg do Homebrew vem sem `drawtext`.

---

## No app

| arquivo | papel |
|---|---|
| `Models/Short.swift` | modelo; curta com `publishedAt` no futuro não aparece |
| `Content/ShortCatalog.swift` | lê `shorts.json`, acha pôster e vídeo |
| `App/Shorts/WatchSection.swift` | seção e card na Home |
| `App/Shorts/ShortPlayer.swift` | download, player, orientação |

O vídeo é On-Demand Resource (tag `short-<id>`); o pôster e o catálogo ficam
no bundle. O download acontece **no card**, com um anel de progresso. Tocar
de novo cancela.

O player é o `AVPlayerViewController` apresentado em tela cheia pelo UIKit,
e não embutido em SwiftUI. Só assim vêm o X nativo, o swipe pra fechar, o
menu de legendas e o AirPlay de vídeo.

**Paisagem só durante o filme.** O Info.plist agora *permite* paisagem no
iPhone, mas o AppDelegate devolve `OrientationLock.mask`, que é retrato fora
do player. O iPad continua girando livre, como antes.

**Narração x filme.** Abrir um curta pausa a narração (o mini-player fica lá
pra retomar) e troca a sessão para `.moviePlayback`, porque `.longFormAudio`
mandaria só o som pro AirPlay. Fechar devolve a categoria de narração. Isso
fica no `AudioPlayerManager`, que é quem sabe se a sessão está ativa.

Curta com `isPremium: true` abre o paywall (`source: "short"`). O piloto é
free, de propósito: é a amostra do formato.

Analytics: `short_play` e `short_complete`.

---

## Próximo curta

1. Copie `shorts/the-paper-whale/film.json` para `shorts/<novo-slug>/`
2. Troque `id`, roteiro, personagens e `publishedAt`
3. `plan` até não sobrar aviso, e siga a ordem acima
