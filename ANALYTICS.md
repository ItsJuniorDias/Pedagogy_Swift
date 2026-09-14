# Analytics

Eventos first-party para `https://pedagogy-analytics.onrender.com`. Sem SDK de
terceiro, sem IDFA, sem identificador de device ou de usuário.

Isso não é purismo: a Categoria Kids proíbe analytics de terceiro e a App
Store rejeita por isso. Um POST JSON pro seu próprio servidor não é terceiro,
e sem identificador nenhum não há o que declarar como rastreamento.

---

## O que é enviado

| Evento | Quando | Params |
|---|---|---|
| `paywall_view` | paywall aparece | `source`: `onboarding` ou `story_detail` |
| `checkout_initiated` | usuário passa o parental gate e a compra começa | `content_id`, `value`, `currency`, `source` |
| `start_trial` | compra concluída **com** trial | idem |
| `subscribe` | compra concluída **sem** trial | idem |
| `story_open` | reader abre | `content_id`, `source` |
| `story_complete` | último capítulo terminado (lendo ou ouvindo) | `content_id`, `source` |
| `narration_play` | narração de um capítulo começa a carregar | `content_id`, `chapter` |

Os quatro primeiros são os nomes que o backend conhece: `lib/funnel.ts` monta
o funil com eles e `lib/capiMirror.ts` os traduz para ViewContent,
InitiateCheckout, StartTrial e Purchase no Meta. **Renomear qualquer um deles
no app quebra o funil silenciosamente** — o evento continua sendo gravado, só
para de contar.

Os três últimos ficam fora do funil e aparecem em `/stats/events`. Existem
porque `story_open` + `story_complete` mostram quais histórias prendem e quais
são abandonadas — sinal que o RevenueCat não tem como enxergar.

### Duas portas de entrada do paywall

`source` separa as duas, e a distinção importa na leitura dos números:
`story_detail` pega alguém que já quer uma história específica — intenção
alta. `onboarding` pega todo mundo, inclusive quem ainda não leu uma linha.
A segunda converte mais em volume e pior em taxa, então **é esperado ver a
taxa do funil cair quando o paywall de introdução entra**, sem que nada tenha
piorado. Como o backend indexa `source` em coluna própria, dá pra comparar as
duas separadas em vez de olhar a média que esconde ambas.

### Trial medido antes da compra

`start_trial` vs `subscribe` sai de `isEligibleForIntroOffer`, consultado
**antes** de chamar `store.purchase`. Depois da compra o usuário deixa de ser
elegível e a resposta viraria sempre `false`, classificando toda conversão
como `subscribe`. No funil os dois contam igual; a distinção existe pro Meta.

---

## ⚠️ Um bug no backend: a receita vai dar zero

`src/db/sqlite.ts` e `src/db/postgres.ts` calculam receita com:

```sql
WHERE event = 'purchase'
```

Mas `lib/funnel.ts` e `lib/capiMirror.ts` usam `subscribe`. Nenhum lugar do
sistema emite `purchase`. Do jeito que está, ou o app manda `subscribe` e
`/stats/revenue` fica sempre zerado, ou manda `purchase` e o funil nunca
registra conversão nem espelha pro Meta.

O app manda `subscribe`, que é o nome canônico. **A correção é de uma linha,
nos dois drivers:**

```diff
- WHERE event = 'purchase' AND ts >= $1 AND ts <= $2
+ WHERE event IN ('subscribe', 'start_trial') AND ts >= $1 AND ts <= $2
```

(no `sqlite.ts` os placeholders são `?` em vez de `$1`/`$2`)

Detalhe bom: o `extract.ts` grava `value` e `currency` em coluna própria **no
momento do insert**, não na hora da consulta. Então corrigir a query depois faz
os eventos já armazenados passarem a contar retroativamente — não se perde
nada por deixar pra depois.

---

## Como o cliente funciona

`App/Analytics/Analytics.swift`. Chamada única: `Analytics.shared.track(_:_:)`.
Nunca bloqueia, nunca lança, nunca falha visível.

**Fila persistida em disco, não um POST por evento.** O motivo principal é o
Render: no plano free o serviço hiberna sem tráfego e a primeira requisição
depois disso leva dezenas de segundos. Com POST solto, os eventos perdidos
seriam justamente os primeiros do dia — incluindo o `paywall_view` de quem
abriu o app pela manhã. A fila também sobrevive a rede de celular caindo e ao
app ser morto: o que não saiu vai no próximo launch, que importa porque o
usuário costuma fechar o app logo depois de comprar.

**Eventos de conversão saem na hora.** `checkout_initiated`, `start_trial` e
`subscribe` forçam flush imediato em vez de esperar o lote de 10. São poucos e
são os que pagam a conta.

**Descarte é deliberado.** 4xx que não seja 429 significa payload que o
servidor nunca vai aceitar — reenviar seria loop infinito, então descarta. 5xx,
timeout e rede caída mantêm na fila. A fila tem teto de 200 e derruba os mais
antigos: um app que ficou uma semana offline não deve acumular milhares de
eventos de funil que já não valem nada.

**Ligado sempre, inclusive em DEBUG.** A primeira versão desligava em DEBUG
pra não sujar o funil, e o efeito prático foi pior: como se testa em DEBUG, a
integração parecia quebrada e não havia nada no console dizendo por quê.

A troca é limpar antes de publicar (o `admin/clear` abaixo). Pra silenciar
durante o desenvolvimento sem mexer em código: Product → Scheme → Edit → Run →
Arguments, e adicione `-analytics.disabled YES`.

Em DEBUG cada evento imprime no console do Xcode:

```
[analytics] na fila: paywall_view ["source": "onboarding"] — fila com 1
[analytics] enviados 1 — HTTP 202
```

Se aparecer `adiado`, é rede ou o Render acordando — o evento fica na fila. Se
aparecer `REJEITADO`, o servidor recusou o payload e ele foi descartado.

---

## Testar a ligação

Com o app rodando (e `isEnabled` liberado em DEBUG):

```bash
curl -s "https://pedagogy-analytics.onrender.com/health"

curl -s "https://pedagogy-analytics.onrender.com/stats/events" \
  -H "Authorization: Bearer $ADMIN_TOKEN"
```

Ou direto no dashboard: `https://pedagogy-analytics.onrender.com`.

Um evento na mão, sem passar pelo app:

```bash
curl -X POST "https://pedagogy-analytics.onrender.com/events" \
  -H "Content-Type: application/json" \
  -d '{"event":"paywall_view","params":{"source":"curl"},"ts":'$(date +%s000)'}'
```

Resposta esperada: `202` com `{"ok":true,"accepted":1}`.

**Antes de publicar**, limpe os eventos de teste e de seed:

```bash
curl -X DELETE "https://pedagogy-analytics.onrender.com/admin/clear?confirm=DELETE_ALL" \
  -H "Authorization: Bearer $ADMIN_TOKEN"
```

---

## Duas pendências de App Store

**1. Privacy manifest.** O projeto não tem `PrivacyInfo.xcprivacy`. Até agora
não precisava — o app era inteiramente offline. Com uma chamada de rede que
carrega dados de uso, ele passa a precisar, e a Apple rejeita builds sem o
arquivo quando há coleta a declarar.

O que declarar: **Product Interaction**, marcado como *não vinculado à
identidade do usuário* e *não usado para rastreamento*. Ambos são verdade aqui
— não vai identificador nenhum no payload. Nada de `NSPrivacyTrackingDomains`,
que é só para domínios de rastreamento.

**2. Questionário de privacidade do App Store Connect.** Mesma resposta:
Product Interaction, não vinculado, não usado para rastreamento.

Se um dia você adicionar o `anon_id` que o README do backend sugere como
upgrade (UUID aleatório por instalação, guardado local — não é IDFA), as duas
respostas mudam: passa a ser dado vinculado a um identificador, e num app da
Categoria Kids isso merece uma leitura cuidadosa da 1.3 antes.

---

## Limite do que esses números dizem

Sem identificador, o funil é razão de **volume de eventos**, não conversão por
usuário. Cem `paywall_view` e dez `subscribe` não querem dizer que dez pessoas
em cem converteram — pode ser uma pessoa que abriu o paywall dez vezes.

Serve muito bem como sinal direcional: mostra **onde está a maior queda** e se
uma mudança melhorou ou piorou. Para conversão por usuário, o RevenueCat já
mede — os dois juntos fecham o quadro, e é por isso que este backend existe
medindo justamente o pedaço pré-compra que o RevenueCat não enxerga.
