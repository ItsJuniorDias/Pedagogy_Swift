# Image Prompts — Pedagogy v2

Todos os prompts que você precisa gerar pra ter a v2 visualmente completa
nas telas atualmente construídas (Onboarding + Home).

## Estilo consistente entre todas as imagens

Repita esta seção como preâmbulo em todos os prompts:

> Mike Mignola style adapted for children ages 9-11: heavy black inks, thick
> confident brushstrokes, flat shadows (no gradients or soft shading), warm
> cream and sepia palette with occasional pink/purple/yellow accents.
> Cozy but atmospheric — never scary, never dark. Think "Coraline" softened
> for younger readers, or Roald Dahl illustrated.

## Regras universais de composição

**Safe padding**: 8% em cada lado (~100px em 1400px de largura). Personagem
ou foco principal SEMPRE no centro, cantos sempre "airy". Isso protege contra:

- Cantos arredondados do card cortarem detalhe importante
- Overlay futuro escurecer bordas
- Cropping em telas de aspect ratio diferente (iPhone SE vs iPad)

**Sem texto**: NUNCA incluir texto, título ou tipografia na imagem. O app
adiciona texto em áreas separadas fora da imagem.

**Sem borders/frames**: a imagem não precisa de moldura própria — o card
tem sua própria borda.

## Fluxo de geração recomendado

Cada prompt tem `MODEL: any` (funciona em qualquer generator). Se você usar:

- **Midjourney 6**: adicione `--ar 5:4` (ou 1:1 pra onboarding), `--style raw`, `--stylize 100`
- **DALL-E 3** (via ChatGPT/API): peça "no text, no typography, no letters" explicitamente
- **Nano-banana / Gemini Image**: pede em português também, funciona
- **Sora / Firefly / Ideogram**: use o prompt como está

Depois de gerar, salve com o **NOME EXATO** que o código espera (listado
abaixo em cada prompt como `NAME:`) e adicione no `Assets.xcassets` do Xcode.

---

# 🎨 Onboarding — 3 imagens

Todas quadradas, 1:1, resolução mínima 1368×1368px (@4x pra iPhone Pro Max).

## 1. `onboarding-1-reading`

**Layout target**: card 1:1 no topo da tela de onboarding, ~342×342pt, com
sombra hard e cantos arredondados `Theme.Radius.xl` (20pt).

**Accent color da página**: pink (`#FF5B8D`) — o fundo da tela é pinkFaint
(`#FFF0F6`) muito claro. A imagem deve harmonizar com essa base.

**PROMPT**:

> Square illustration, 1:1 aspect ratio, minimum 1368×1368px. Mike Mignola
> style adapted for children ages 9-11: heavy black inks, thick brushstrokes,
> flat shadows, warm cream and sepia palette with soft pink accents.
> 
> Composition: a young girl around 10 years old, sitting cross-legged in a
> big cozy armchair by a tall window, reading a hardcover book that glows
> faintly warm. Late afternoon light comes through the window in warm sepia
> tones. She is completely absorbed in the book, one hand resting on the
> page. Around her armchair, a stack of two or three books sit on the floor.
> 
> Character centered in frame, filling ~60% of the vertical space. Keep 100px
> safety padding on all edges — armchair and body silhouette should not
> touch the borders. Warm, inviting, focused mood. No fantasy elements yet —
> this is the "welcome to reading" moment.
> 
> Do not include any text, title, or typography.

---

## 2. `onboarding-2-illustrations`

**Layout target**: mesmo container 1:1 da anterior.

**Accent color da página**: purple (`#6C5CE7`) — o fundo é accentTint
(`#E4E0FF`).

**PROMPT**:

> Square illustration, 1:1 aspect ratio, minimum 1368×1368px. Mike Mignola
> style adapted for children ages 9-11: heavy black inks, thick brushstrokes,
> flat shadows, warm cream palette with purple and gold accents.
> 
> Composition: an open storybook lying flat, seen from above at a slight
> angle. Out of the pages, magical scenes rise upward like pop-up book
> illustrations coming to life — a small castle on a hill, a whale in the
> clouds, a lantern-lit forest path. Everything is stylized silhouettes with
> Mignola-like flat shading, in warm sepias and purples with occasional
> glowing gold accents.
> 
> Book centered in frame. Rising elements filling upper 60% of the composition.
> Keep 100px safety padding on all edges. Whimsical, wondrous mood — this is
> the "look what waits inside" moment.
> 
> Do not include any text, title, or typography — the book pages should show
> only tiny illegible glyphs or abstract line marks, never actual readable
> words.

---

## 3. `onboarding-3-streak`

**Layout target**: mesmo container 1:1.

**Accent color da página**: yellow (`#FFD93D`) — o fundo é highlightTint
(`#FFF5C2`).

**PROMPT**:

> Square illustration, 1:1 aspect ratio, minimum 1368×1368px. Mike Mignola
> style adapted for children ages 9-11: heavy black inks, thick brushstrokes,
> flat shadows, warm cream palette with yellow and orange accents.
> 
> Composition: a calendar page or almanac-style grid seen from a three-quarter
> angle, with small hand-drawn flames or lantern flames marking consecutive
> days in a row. The flames are stylized Mignola-flame silhouettes — flat
> yellow and orange with heavy black outlines, no rendered fire. Behind the
> calendar, a warm cozy background suggests a bedside table with a small
> lantern and a closed book.
> 
> Calendar centered in frame, tilted slightly. Flames rising off the marked
> days. Keep 100px safety padding on all edges. Warm, hearth-like mood —
> this is the "keep the fire going" moment about daily reading habit.
> 
> Do not include any text, title, or typography — calendar day numbers can
> be small abstract marks (dots, tallies) rather than actual numerals.

---

# 📖 Home — Story card cover

## `story-house-of-clocks-cover`

**Layout target**: parte superior do StoryCard na Home. Aspect ratio 5:4.
Cantos superiores arredondados `Theme.Radius.lg` (16pt). Não tem overlay
nem texto sobreposto — a imagem ocupa a área integral, sem escurecimento.

**Theme color**: purple (`#6C5CE7`) — o card tem detalhes de UI em roxo
(CTA "Continue reading" em purple). A imagem NÃO precisa ser roxa; só
combinar com essa acentuação.

**PROMPT** (já também gravado no JSON como `coverImagePrompt`):

> Story card cover illustration. Aspect ratio 5:4 (wider than tall), render
> at 1432×1146px minimum. Mike Mignola style adapted for children ages 9-11:
> heavy black inks, thick brushstrokes, flat shadows, warm cream and sepia
> palette.
> 
> Composition: a 10-year-old English girl named Wren with short dark hair
> and a serious curious expression, standing in a dim Victorian hallway
> lined with clocks of every size and shape — grandfather clocks in corners,
> cuckoo clocks on walls, small brass clocks on shelves. One clock in the
> background glows faintly warm. Character positioned center-left, filling
> roughly 45% of frame height.
> 
> Keep 100px safety padding on all sides — no crucial details near the
> borders (the card has rounded corners that will crop the edges, and
> future overlays may darken the bottom). Warm inviting atmosphere despite
> the mystery — cozy, not scary.
> 
> Do not include text, title, or any typography — text will be added by the
> app in a separate area below the image.

---

# 📅 A fazer nas próximas levas

Não gerar ainda — o layout onde essas imagens vão aparecer não está construído:

- **10 illustrations dentro da história** (`ch1-p1-arrival`, `ch1-p3-hall-of-clocks`, `ch1-p5-backwards-clock`, `ch2-p1-hallway-frozen`, `ch2-p3-listening`, `ch2-p5-empty-hallway`, `ch3-p2-music-box`, `ch3-p4-turning-the-key`, `ch3-p5-thomas-appears`, `ch3-p7-morning`) — todas dependem do layout do Reader (aspect ratio, safe zones dentro da página). Vou revisar cada prompt quando o Reader estiver pronto.

- **Chapter opener images** — dependem do layout de abertura de capítulo no Reader.

- **Paywall hero image** — depende do layout do paywall.

---

# Como adicionar as imagens no projeto

1. Salva cada imagem com o nome exato listado (ex: `onboarding-1-reading.png`)
2. Abre `Assets.xcassets` no Xcode
3. Arrasta a imagem pra dentro do catálogo
4. O Xcode cria automaticamente o `.imageset`
5. Recomendo adicionar as 3 versões (1x, 2x, 3x) — mas se só tiver uma versão em alta resolução, marca ela como 3x e o iOS faz downscale
6. Rebuild — a imagem aparece no lugar do placeholder

**Dica**: se preferir manter apenas 1 arquivo por imagem em alta resolução,
marca todas as suas imagens como "Single Scale" nas opções do imageset e
coloca a versão @3x lá — funciona em todos os devices.
