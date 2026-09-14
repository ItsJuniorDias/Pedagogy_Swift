# Pedagogy — o que falta implementar

Levantamento feito em 04/set/2026 sobre o zip do projeto (34 arquivos Swift, 50 histórias, build compilando).
Cada item tem a evidência no código. Ordenado por custo de errar, não por esforço.

---

## Tier 0 — Bloqueia o release

### 0.1 Áudio não vai tocar em background
`Info.plist` **não tem `UIBackgroundModes`**. Mas o `AudioPlayerManager` já configura tudo que
depende disso:

- `AVAudioSession(.playback, mode: .spokenAudio)` — AudioPlayerManager.swift:144
- `MPRemoteCommandCenter` (play/pause no lock screen) — :155-161
- `MPNowPlayingInfoCenter` (capa + título na tela de bloqueio) — :218-242

Sem a chave, o iOS suspende o áudio quando a tela trava ou o app vai pro background. Todo o mini
player e os controles de lock screen viram enfeite. Criança que ouve a história de olhos fechados
perde o áudio no primeiro auto-lock.

```xml
<key>UIBackgroundModes</key>
<array>
    <string>audio</string>
</array>
```

- [x] Chave adicionada ao `Info.plist`
- [ ] Testar com a tela travada assim que houver MP3 no bundle (hoje não há — item 0.5)
- [ ] Tratar interrupção (ligação, Siri): hoje `AudioPlayerManager` não observa
      `AVAudioSession.interruptionNotification`, então o áudio não retoma sozinho depois de uma
      chamada. Não bloqueia release, mas aparece em uso real

### 0.2 `PrivacyInfo.xcprivacy` não existe
O app usa `UserDefaults` em 3 lugares (ReadingProgress.swift:247, AchievementsStore.swift:120,
RootView.swift:27). `UserDefaults` é *required reason API* — sem o manifesto de privacidade o
App Store Connect reclama no upload.

- [ ] Criar `PrivacyInfo.xcprivacy` com `NSPrivacyAccessedAPICategoryUserDefaults` → motivo `CA92.1`
      (acesso só a dados do próprio app)
- [ ] Declarar coleta de dados: hoje é **nenhuma** — o que é um argumento de marketing forte num
      app infantil, então vale deixar explícito

### 0.3 Entitlement de push sem push
`pedagogy.entitlements` tem `aps-environment: development`, mas as notificações são 100% locais
(`UNCalendarNotificationTrigger`, NotificationManager.swift:243). Não existe
`registerForRemoteNotifications` em lugar nenhum.

Entitlement de APNs que o app não usa, e fixado em `development` num build de distribuição.

- [ ] Remover a chave (ou o arquivo inteiro, se não houver outra entitlement)

### 0.4 URLs de Terms e Privacy são placeholder
PaywallView.swift:784 e :791 apontam pra `https://pedagogy.app/terms` e `/privacy` com
`// TODO: apontar pra URL real hospedada`.

Política de privacidade é obrigatória pra qualquer app com assinatura, e o link é conferido no
review. Se o app for pra categoria Kids, é conferido com lupa.

- [x] URLs do Notion apontadas em `App/Paywall/LegalLinks.swift`
- [ ] Confirmar que as duas páginas estão com "Publish to web" ligado (janela anônima)
- [ ] Colar as mesmas URLs no App Store Connect (Privacy Policy URL e EULA)

### 0.5 Nenhum áudio no bundle
`Content/Audio/` só tem o `.gitkeep`. `hasAudioForNextChapter` é `false` em 100% das histórias,
então o botão **Listen** não aparece em lugar nenhum do app hoje.

- [ ] 150 MP3 (`generate_speech.py`) — em andamento
- [ ] 150 `.timings.json` (`generate_timings.py`)
- [ ] `sync_to_project.py` + Clean Build Folder

---

## Tier 1 — Risco na virada v1 → v2

O `MARKETING_VERSION` é 2.0.0 e o Store.swift descreve a substituição do RevenueCat da v1
(React Native) por StoreKit 2. Ou seja: **existe base instalada**. Um erro aqui não gera bug,
gera reembolso e review 1 estrela.

### 1.1 Confirmar os product IDs contra a v1
Store.swift:50-51 usa `com.alexandre-junior.pedagogy.annual` e `.monthly`, e o próprio cabeçalho
avisa: *"contanto que o productID seja EXATAMENTE o mesmo que a v1 usava. Confirme isso"*.

Se divergir por um caractere, `Transaction.currentEntitlements` não devolve nada e **todo assinante
da v1 vira não-assinante** ao atualizar.

- [ ] Abrir App Store Connect → Assinaturas → comparar string por string
- [ ] Testar com uma conta sandbox que já tenha a assinatura da v1

### 1.2 Progresso da v1 não é migrado
A v2 lê `pedagogy.library-progress.v1` do `UserDefaults` (ReadingProgress.swift:172). Se a v1 em
React Native usava AsyncStorage (o default do RN), os dados estão num arquivo separado dentro do
container, não no `UserDefaults` — a v2 não enxerga.

Consequência: usuário atualiza e perde streak, progresso e achievements. Num app cuja tela de
perfil é streak + gráfico de atividade, isso dói.

- [ ] Verificar como a v1 persistia (AsyncStorage? MMKV? `UserDefaults` via lib nativa?)
- [ ] Se for AsyncStorage: ler o store antigo uma vez no primeiro launch da v2 e importar
- [ ] Se decidir não migrar: decisão consciente, e vale um aviso no release notes

### 1.3 `Products.storekit` com `"products": []`
O arquivo local só tem localização `pt_BR` / storefront `BRA`. Não afeta produção (produção lê do
ASC), mas impede testar preço/trial em outro storefront.

- [ ] Adicionar localização `en_US` se for vender fora do Brasil (ver 2.4)

### 1.4 Validação de recibo no servidor
Store.swift:147 marca `// TODO: server verify`. Hoje a verificação é só client-side via
`Transaction.verified`. Dá pra viver assim numa v1 de release; o ponto de entrada já está marcado
e você já tem backend no Render.

- [ ] Opcional pro lançamento, decidir se entra agora ou depois

---

## Tier 2 — Produto incompleto

### 2.1 Não existe tela de Settings
Não há nenhum `SettingsView` no projeto. Hoje o usuário **não consegue**, dentro do app:

- desligar as notificações (só indo nos Ajustes do iOS)
- gerenciar/cancelar a assinatura (`showManageSubscriptions`)
- mudar o tamanho da fonte (ver 2.2)
- ler termos e privacidade fora do paywall
- apagar o progresso

Os métodos de reset já existem e estão comentados como *"útil pra futura tela de settings"*
(AchievementsStore.swift:104, ReadingProgress.swift:224). Falta a tela.

- [ ] `SettingsView` acessível pelo Profile

### 2.2 O app de leitura não respeita Dynamic Type
`Typography.swift` monta todas as fontes com `.custom(name, size:)` (:106, :113, :118) — sem
`relativeTo:`. E o corpo da história tem `fontSize` fixo em 18pt (ReaderView.swift:620).

Criança de 9 anos com o texto do sistema aumentado abre a história e o texto continua 18pt. Numa
categoria onde ler *é* o produto, é o gap de acessibilidade mais caro da lista.

- [ ] Trocar pra `.custom(_, size:relativeTo:)`, **ou** botão A/A no reader com o tamanho salvo
- [ ] Testar com Accessibility Inspector nos tamanhos extremos

### 2.3 Library sem busca
LibraryView tem filtro por categoria e 4 ordenações, mas nenhum `.searchable`. Com 50 histórias
passa; com 100 não.

- [ ] Baixa prioridade, mas é um `.searchable` de uma linha

### 2.4 UI em inglês, assinatura configurada pro Brasil
Não existe `.lproj` nem `.xcstrings` — toda a UI é inglês hardcoded. Mas o `Products.storekit`
está em `pt_BR` / storefront `BRA`, com as descrições das assinaturas em português.

Decisão de produto pendente: o público é criança brasileira lendo em inglês (aí a **UI em pt-BR
ajuda o pai, que é quem assina**) ou é mercado global? O conteúdo continua em inglês nos dois
casos. Você já roda esse pipeline (pt-BR / en / es) nos jogos.

- [ ] Decidir, e se for localizar: `Localizable.xcstrings` + revisar o paywall primeiro

### 2.5 iPad declarado mas não adaptado
`TARGETED_DEVICE_FAMILY = "1,2"` e o `Info.plist` libera as 4 orientações no iPad. O design é
portrait-first com espaçamentos fixos.

Shippar iPad significa screenshots de iPad no ASC e o review testando em iPad. É trabalho real.

- [ ] Ou testar e ajustar o layout, ou baixar pra `"1"` (só iPhone) e ligar iPad depois

### 2.6 "New story this week" avisa sobre história já visível
45 histórias têm `publishedAt` no futuro (até jul/2027) e o `StoryLoader` **não filtra por data** —
todas as 50 já aparecem na Library hoje. A notificação diz "New story this week"
(NotificationManager.swift:229), mas a história já estava lá desde o primeiro dia; o que muda é ela
ficar grátis por 7 dias (`isFreeToRead`, Story.swift:98).

- [ ] Ou esconder as não publicadas, ou trocar a copy pra algo tipo "Free this week: <título>"

### 2.7 Truncamento das 64 notificações não implementado
`scheduleAllPending` agenda **45 notificações** de uma vez. O limite do iOS é 64 pendentes. O
comentário em NotificationManager.swift:171 diz *"se um dia tivermos mais que isso de stories
futuras, filtramos pras próximas 60 aqui"* — o filtro não existe.

Passando de 64, o iOS descarta silenciosamente as excedentes. Hoje cabe; na próxima leva de
histórias, não.

- [ ] `.prefix(60)` no array já ordenado por data

---

## Tier 3 — Se for submeter na categoria Kids

Store.swift:8 cita a categoria Kids como motivo de tirar o RevenueCat. A Apple exige parental gate
em três situações (Guideline 1.3 + anúncio de 12/set/2019): **link out do app, solicitar
permissões, e apresentar oportunidade de compra.**

- [x] **Parental gate implementado** — `App/ParentalGate/ParentalGate.swift`, desafio de
      multiplicação por extenso, sorteado a cada apresentação
- [x] Gate no CTA de compra, dentro do paywall (o paywall abre livre; o gate precede o ato de
      comprar) — PaywallView
- [x] Gate nos links de Terms e Privacy do rodapé do paywall
- [x] Gate antes do prompt de permissão de notificação — OnboardingView
- [ ] **Decidir se o app vai mesmo pra categoria Kids.** O gate custa conversão; se a resposta for
      não, é remover os três `.parentalGate(...)` e o arquivo
- [ ] Se o review reclamar de 1.3 mesmo com o gate, a leitura alternativa da guideline é gatear a
      ENTRADA do paywall ("designated area behind a parental gate") em vez do botão de comprar —
      é mover uma linha pro StoryDetailView
- [ ] **Analytics de terceiros são proibidos** na categoria Kids, junto com transmitir informação
      pessoal ou de dispositivo a terceiros. Impacta diretamente o item 4.1 — o Grimoire é backend
      próprio (não é terceiro), mas não pode mandar identificador de dispositivo
- [ ] Rever o gate no TestFlight com uma criança de verdade antes de submeter

Se não for Kids, nada disso se aplica, mas aí é preciso definir a classificação etária.

---

## Tier 4 — Instrumentação e testes

### 4.1 Zero analytics
Não há nenhum tracking no app. O próprio Store.swift:20 nota que sem RevenueCat sumiram trial
conversion, MRR e churn, e manda olhar o ASC → Sales/Trends.

Você já tem o backend próprio (Node/Postgres no Render) com cliente Swift. O funil que interessa:
paywall visto → CTA tocado → compra, mais capítulos concluídos e retenção D1/D7.

Atenção: a categoria Kids **proíbe analytics de terceiros** e a transmissão de informação pessoal
ou de dispositivo a terceiros. O Grimoire é seu, então não é "terceiro" — mas não pode carregar
identificador de dispositivo junto.

- [ ] Plugar o cliente Swift e instrumentar o funil do paywall

### 4.2 Nenhum teste
Não existe test target no projeto. Alvos com melhor retorno, todos lógica pura:

- [ ] `isFreeToRead(now:)` — foi feito com `now` injetável **explicitamente pra teste**
      (Story.swift:100) e não tem teste. Virada de semana, fuso, `publishedAt` nulo
- [ ] Streak em `ReadingProgress` (dia seguinte, pulou um dia, mesmo dia duas vezes)
- [ ] Desbloqueio dos 12 achievements
- [ ] `SentenceSplitter` vs o split do Python — se divergirem, o highlight desalinha
- [ ] `ParentalGateChallenge.random()` — invariantes do sorteio (fatores de 2 a 9, nunca iguais,
      resposta sempre ≤ 72) e `answer` batendo com `left * right`

---

## Tier 5 — Conteúdo e polimento

- [x] Covers: 50/50 no `Assets.xcassets`
- [x] Achievements: 12/12 ilustrações
- [ ] Áudio: 0/150 (Tier 0.5)
- [ ] Timings: 0/150
- [ ] **AppIcon**: só a variante clara tem arquivo. As entradas `dark` e `tinted` estão declaradas
      no `Contents.json` sem `filename` — o iOS cai pra clara, mas fica sem ícone escuro no iOS 18
- [ ] **Nomes de página do House of Clocks** sem prefixo (`ch1-p1-arrival.png`) enquanto as outras
      usam prefixo. Colide se outra história usar o mesmo padrão. Já anotado no README dos scripts;
      só vira bug se você voltar com arte inline nos capítulos

---

## O que já está pronto (pra não perder de vista)

Navegação e telas completas (Home, Library, Reader, StoryDetail, Profile, Paywall, Onboarding),
StoreKit 2 com `Transaction.updates` e Restore, notificações locais com deep link, achievements
com persistência, gráfico de atividade, design system consistente (fontes, sombra hard, grain,
motion), 50 histórias × 3 capítulos com covers, e o pipeline de áudio pronto pra rodar.

O grosso do app existe. O que falta é quase todo **plumbing de release** — e um item de
acessibilidade (2.2) que vale mais que vários dos outros juntos.
