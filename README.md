# Pedagogy v2 — Swift/SwiftUI

App infantil de leitura para 9–11 anos. Rewrite completo do Pedagogy v1
(React Native/Expo) para Swift/SwiftUI nativo, mantendo o mesmo bundle ID
`com.alexandre-junior.pedagogy` — a Apple trata como upgrade da v1, não
como app novo.

## Estado atual

**Design System montado e validável.** Não tem features de negócio ainda —
essa entrega é a fundação visual que todo o resto vai consumir. A tela
inicial (`ShowcaseView`) renderiza todos os tokens em device pra você validar
o visual antes de construir Home/Reader/Paywall.

## Stack

- **Swift 5** + **SwiftUI** (sem UIKit, sem Storyboards)
- **Deploy target: iOS 18.0** — cobre iPhone XR/XS/11 e todos mais novos
- **StoreKit 2** — assinaturas nativas, sem RevenueCat, sem coleta de IDFA
- **Xcode 26.6+** — usa `PBXFileSystemSynchronizedRootGroup` (arquivos novos
  na pasta são descobertos automaticamente pelo Xcode; não precisa registrar
  no pbxproj)

## Estrutura

```
pedagogy/
├── pedagogyApp.swift              # entry point + injeção do Store
├── App/
│   └── ShowcaseView.swift          # tela de validação do DS
├── DesignSystem/
│   ├── Theme.swift                 # Palette + Colors + Radius + Space + Stroke
│   ├── Typography.swift            # Font.display/.body/.ui + TypeScale + Text extensions
│   ├── Shadow.swift                # .cardShadow(), .hardShadow(), .glowPrimary() etc
│   ├── Grain.swift                 # textura de papel via Canvas
│   └── Motion.swift                # PressBounce + .breathe() + .floatY() + .appearFadeUp()
├── Store/
│   ├── Store.swift                 # @Observable actor com StoreKit 2
│   └── Products.storekit           # config de teste local (compra no simulator)
├── Resources/
│   └── Fonts/
│       ├── AlfaSlabOne-Regular.ttf # display (Google Fonts, OFL)
│       └── Lora-VariableFont.ttf   # body serif (Google Fonts, OFL)
└── Assets.xcassets/
    ├── AccentColor.colorset        # #FF5B8D (rosa da marca)
    └── AppIcon.appiconset          # vazio — adicionar depois
```

## Como buildar

1. Extraia o zip e abra `pedagogy.xcodeproj` no Xcode
2. Selecione um simulator (recomendado: iPhone 16 Pro pra ver Liquid Glass;
   ou iPhone SE 3rd gen pra testar layouts apertados)
3. **Cmd+R** para rodar

Vai abrir direto na `ShowcaseView` — role até o fim.

## Validação visual — o que checar no device

Antes de partir pra próxima etapa (Home real), valide os 4 pontos críticos:

1. **Fontes carregam?** — O título "A Casa dos Relógios" no topo tem que
   renderizar em Alfa Slab (slab robusta, "pôster de aventura"). Se sair
   em sans-serif, as fontes não foram registradas. Cheque
   `INFOPLIST_KEY_UIAppFonts` no project.pbxproj.

2. **Serif no corpo?** — Os parágrafos "Cora empurrou a porta" têm que ter
   serifas (Lora). Se sair sans, mesmo problema acima.

3. **Sombra hard tem offset visível?** — Na seção "SOMBRAS", o card "hard"
   deve ter uma cópia preta atrás, deslocada 4pt à direita e 5pt pra baixo
   (tipo painel de HQ). Se parecer sombra suave desfocada, o modificador
   não está sendo aplicado corretamente.

4. **Grão aparece?** — Na seção "GRÃO", o card opacity 0.04 quase some,
   0.08 é sentido, 0.12 é visível. Se todos parecerem iguais, o Canvas
   não está desenhando (raro, mas cheque na versão do iOS).

## StoreKit — como testar compras localmente

O arquivo `pedagogy/Store/Products.storekit` já traz dois produtos configurados
(anual R$ 399,90 com trial de 7 dias, mensal R$ 59,90) em pt-BR.

Pra usar no simulator sem sandbox account:

1. No Xcode: **Edit Scheme** → **Run** → **Options**
2. Em **StoreKit Configuration**, selecione **Products.storekit**
3. Rode o app — quando a UI de paywall chamar `Store.purchase(_:)`, vai
   abrir a sheet nativa da Apple direto com os preços fake configurados

Pra testar em device real (com sandbox account real):

1. Deixe **StoreKit Configuration = None** no scheme
2. No device: **Settings → App Store → Sandbox Account** → login com uma
   conta de teste criada em App Store Connect → Users and Access
3. Rode o app pelo Xcode

## Product IDs — IMPORTANTE antes de subir

Os IDs em `Store.swift` (`ProductID.annual` e `.monthly`) são:

```swift
com.alexandre-junior.pedagogy.annual
com.alexandre-junior.pedagogy.monthly
```

**Se os IDs configurados no App Store Connect da v1 forem diferentes**,
atualize aqui pra bater. Product IDs no ASC são imutáveis depois de criados
— se divergir, `Product.products(for:)` devolve vazio e o paywall fica preso
em "carregando".

Pra descobrir os IDs atuais: App Store Connect → seu app → In-App Purchases
→ Subscriptions → cada assinatura tem um "Product ID" abaixo do nome.

## Próximos passos sugeridos

O DS está pronto. As camadas a construir em ordem sugerida:

1. **Story model + schema JSON** — como uma história de 10–15 min é estruturada
2. **1 história piloto** completa em JSON — pra validar tom e schema
3. **HomeView** — grid 2 colunas com capas
4. **ReaderView** — leitura página-a-página (swipe horizontal)
5. **PaywallView** — usando o Store já existente
6. **OnboardingView** — 3 telas com CTA no final
7. **AnalyticsClient** — POST HTTP simples pro backend Render existente

## Migração de assinantes da v1 (RevenueCat → StoreKit 2)

**Assinaturas ativas continuam ativas automaticamente.** A compra em si sempre
foi da Apple — RevenueCat era só interface. Quando o usuário da v1 abrir a
v2, `Transaction.currentEntitlements` devolve a compra ativa dele; o
`Store.isPremium` retorna `true`; a gate premium libera.

**Pré-condição:** o `productID` no App Store Connect precisa ser exatamente
o mesmo. Se você usava algo tipo `pedagogy_annual_399` na v1, edite o
`ProductID.annual` no `Store.swift` pra bater.

**O que você perde:** o dashboard do RevenueCat (MRR, cohorts, churn).
Substitutos: App Store Connect → Sales/Trends dá receita e volume;
seu backend Render pode agregar eventos de compra próprios.

## Licenças de fonte

- **Alfa Slab One** — SIL Open Font License 1.1 — © 2016 Alfa Slab One Project
  Authors (info@jmsole.cl)
- **Lora** — SIL Open Font License 1.1 — © 2011 The Lora Project Authors
  (github.com/cyrealtype/Lora-Cyrillic)

OFL permite uso, modificação e redistribuição — inclusive comercial e embarcada
em software. Você não precisa exibir crédito nem link no app, mas é boa prática
mencionar no Settings/About quando essa tela existir.
