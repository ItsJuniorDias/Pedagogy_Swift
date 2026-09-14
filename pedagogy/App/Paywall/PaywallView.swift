//
//  PaywallView.swift
//  pedagogy
//
//  ─── PAYWALL ────────────────────────────────────────────────────────────────
//  Sheet apresentada quando o usuário tenta abrir uma história premium sem
//  assinatura ativa. Consome direto o `Store` (StoreKit 2).
//
//  LAYOUT
//
//    ┌─────────────────────────────┐
//    │  ×                    Restore│  ← top row
//    │                              │
//    │   [Hero illustration or       │  ← placeholder até ter arte
//    │    decorative Grain panel]    │
//    │                              │
//    │   Unlock every story          │  ← title Alfa Slab
//    │                              │
//    │   ✓ Every story, every chapter│  ← benefits list
//    │   ✓ Beautiful illustrations   │
//    │   ✓ New stories every month   │
//    │   ✓ No ads, ever              │
//    │                              │
//    │   ┌──────────────────────┐   │
//    │   │  Annual (highlighted) │   │  ← plan cards, selecionáveis
//    │   │  7 days free · $39/yr │   │
//    │   └──────────────────────┘   │
//    │   ┌──────────────────────┐   │
//    │   │  Monthly $5.99/mo     │   │
//    │   └──────────────────────┘   │
//    │                              │
//    │  ┌────────────────────────┐  │  ← sticky CTA
//    │  │   Start free trial     │  │
//    │  └────────────────────────┘  │
//    │  Cancel anytime · Terms|Priv │
//    └─────────────────────────────┘
//
//  STATE
//
//  • `Store` (env) tem `products: [Product]`, `isLoading`, `isPremium`
//  • `@State selectedProductID` — plano que o usuário escolheu (default: anual)
//  • `@State isPurchasing` — trava CTA durante purchase
//  • `@State errorMessage` — mostra falhas de compra
//
//  Se `store.isPremium` virar true durante a sessão (compra deu certo, ou
//  restore encontrou assinatura), o paywall se dismissa automaticamente.
//
//  APP REVIEW REQUIREMENTS
//
//  A Apple exige em todo paywall:
//    ✓ Preço claro visível ANTES do tap final
//    ✓ Descrição do que renova ("subscription auto-renews")
//    ✓ Botão de restore purchases (link pequeno é OK)
//    ✓ Link pra Terms of Use e Privacy Policy
//  Todos cobertos aqui.
//  ────────────────────────────────────────────────────────────────────────────

import StoreKit
import SwiftUI

struct PaywallView: View {
    @Environment(Store.self) private var store
    @Environment(\.dismiss) private var dismiss

    /// De onde o paywall foi aberto. Vira o `source` do `paywall_view` e é o
    /// que permite comparar a conversão de cada porta de entrada quando
    /// existir mais de uma. Default mantém os call sites antigos compilando.
    var source: String = "story_detail"

    /// Plano selecionado (persistido só durante a sessão do paywall).
    /// Default: anual (o mais valor pro usuário e maior LTV pra você).
    @State private var selectedProductID: String = ProductID.annual

    @State private var isPurchasing = false
    @State private var errorMessage: String?

    /// Recarga manual dos produtos, disparada pelo botão do estado de falha.
    @State private var isRetryingLoad = false

    /// Trava o `paywall_products_empty` em um por apresentação do paywall.
    /// Sem isso, cada retry falho mandaria outro evento e o número deixaria
    /// de ser comparável com `paywall_view`.
    @State private var didReportEmptyProducts = false

    /// Parental gate do CTA de compra. Categoria Kids: o gate precede o ato
    /// de comprar, não a abertura do paywall — ver ParentalGate.swift.
    @State private var isPurchaseGatePresented = false

    /// Stories carregadas do bundle pra alimentar o mosaico de covers do
    /// Hero. Load é síncrono e barato (5 JSONs) — fine em .task.
    @State private var stories: [Story] = []

    // Estados de animação em cascata na entrada do paywall.
    // Hero tem suas próprias animações internas — não precisa de state
    // externo aqui. Title/Benefits/Plans usam a cascata escalonada abaixo.
    @State private var titleAppeared = false
    @State private var benefitsAppeared = false
    @State private var plansAppeared = false

    @Environment(\.accessibilityReduceMotion) private var reduceMotion

    private var selectedProduct: Product? {
        store.products.first { $0.id == selectedProductID }
    }

    var body: some View {
        VStack(spacing: 0) {
            // ─── TOP ROW ─────────────────────────────────────────────
            TopRow(
                onClose: { dismiss() },
                onRestore: {
                    Task { await store.restore() }
                }
            )

            // ─── SCROLLABLE BODY ─────────────────────────────────────
            ScrollView {
                VStack(alignment: .leading, spacing: Theme.Space.xxl) {
                    // Hero tem sua própria cascata interna animada
                    // (cover central + laterais entram sequencialmente).
                    // Sem opacity/offset externo pra evitar sobreposição.
                    Hero(stories: stories)

                    TitleBlock()
                        .opacity(titleAppeared ? 1 : 0)
                        .offset(y: titleAppeared ? 0 : 12)

                    Benefits()
                        .opacity(benefitsAppeared ? 1 : 0)
                        .offset(y: benefitsAppeared ? 0 : 12)

                    PlanCards(
                        products: store.products,
                        selectedProductID: $selectedProductID,
                        isLoading: store.isLoading || isRetryingLoad,
                        onRetry: retryLoadProducts
                    )
                    .opacity(plansAppeared ? 1 : 0)
                    .offset(y: plansAppeared ? 0 : 12)

                    if let error = errorMessage {
                        ErrorBanner(message: error)
                    }

                    Spacer(minLength: 160) // room pro sticky CTA + last benefit
                }
                .padding(.horizontal, Theme.Space.lg)
                .padding(.top, Theme.Space.lg)
            }
            .background(Theme.Colors.bg)
        }
        .background(Theme.Colors.bg.ignoresSafeArea())
        .safeAreaInset(edge: .bottom) {
            StickyCTA(
                product: selectedProduct,
                isPurchasing: isPurchasing,
                hasNoPlanAvailable: !store.isLoading && store.products.isEmpty,
                onTap: purchaseTapped
            )
        }
        .parentalGate(isPresented: $isPurchaseGatePresented) {
            purchaseSelected()
        }
        .onChange(of: store.isPremium) { _, newValue in
            // Compra ou restore deu certo → some
            if newValue {
                dismiss()
            }
        }
        .task {
            // Carrega stories pro mosaico do Hero — não bloqueia render
            // (Hero mostra fallback se stories estiver vazia).
            if stories.isEmpty {
                stories = (try? StoryLoader.loadAll()) ?? []
            }
            triggerEntranceCascade()

            // O topo do funil. Uma vez por apresentação do paywall — `.task`
            // roda na entrada da view, não a cada re-render.
            Analytics.shared.track(.paywallView, ["source": source])

            syncSelectionWithLoadedProducts()
            reportEmptyProductsIfNeeded()
        }
        .onChange(of: store.products) { _, _ in
            // O paywall pode abrir antes de `store.load()` terminar. Este
            // onChange é o que cobre a corrida: quando os produtos chegam,
            // a seleção se ajusta ao que existe de verdade.
            syncSelectionWithLoadedProducts()
        }
        .onChange(of: store.isLoading) { _, isLoading in
            // Só dá pra afirmar "veio vazio" depois que o load terminou.
            if !isLoading { reportEmptyProductsIfNeeded() }
        }
    }

    /// Sequência de entrada em cascata — cada seção aparece com fade + slide
    /// vertical. Delays escalonam pra criar cadência "de descoberta".
    ///
    /// Sequência de entrada em cascata pros textos e planos. Hero tem
    /// sua própria cascata interna e não é orquestrado aqui.
    ///
    /// Timing:
    ///   0.12s → Title
    ///   0.22s → Benefits
    ///   0.32s → Plans
    ///
    /// Reduce Motion: pula tudo pra visível instantâneo.
    private func triggerEntranceCascade() {
        if reduceMotion {
            titleAppeared = true
            benefitsAppeared = true
            plansAppeared = true
            return
        }

        withAnimation(.smooth(duration: 0.5).delay(0.12)) {
            titleAppeared = true
        }
        withAnimation(.smooth(duration: 0.5).delay(0.22)) {
            benefitsAppeared = true
        }
        withAnimation(.smooth(duration: 0.5).delay(0.32)) {
            plansAppeared = true
        }
    }

    // MARK: - Product loading

    /// Garante que `selectedProductID` aponta pra um produto que realmente
    /// carregou.
    ///
    /// O default é `ProductID.annual`, escolhido antes de qualquer produto
    /// existir. Se o anual não vier — mismatch de ID, indisponível na
    /// storefront, aprovado só ele — `selectedProduct` fica nil mesmo com o
    /// card mensal visível na tela, e o CTA continua morto ao lado de um
    /// plano perfeitamente comprável. Cai no primeiro disponível, que por
    /// vir ordenado por preço decrescente é o de maior valor.
    private func syncSelectionWithLoadedProducts() {
        guard !store.products.isEmpty else { return }
        guard !store.products.contains(where: { $0.id == selectedProductID }) else { return }
        selectedProductID = store.products[0].id
    }

    /// Recarrega os produtos. Cobre o caso banal — rede caiu no launch — sem
    /// obrigar o usuário a matar o app e voltar.
    private func retryLoadProducts() {
        guard !isRetryingLoad else { return }
        isRetryingLoad = true
        Task {
            await store.load()
            syncSelectionWithLoadedProducts()
            isRetryingLoad = false
        }
    }

    /// Registra que o paywall foi visto sem nenhum plano comprável.
    private func reportEmptyProductsIfNeeded() {
        guard !didReportEmptyProducts,
              !store.isLoading,
              store.products.isEmpty
        else { return }

        didReportEmptyProducts = true
        Analytics.shared.track(.paywallProductsEmpty, [
            "source": source,
            "reason": store.loadError ?? "empty_without_error",
        ])
    }

    // MARK: - Actions

    /// Tap no CTA: abre o gate. A compra só roda depois que ele passa.
    /// Checa as mesmas guardas antes pra não abrir gate que não leva a nada
    /// (produto ainda carregando, ou compra já em andamento).
    private func purchaseTapped() {
        guard let product = selectedProduct, !isPurchasing else { return }

        // Intenção, medida ANTES do gate. Até aqui o funil ia de `paywall_view`
        // direto pra `checkout_initiated`, que só dispara DEPOIS do gate passar
        // — então quem tocava "assinar" e desistia no desafio matemático não
        // gerava evento nenhum, e a queda inteira ficava debitada no preço.
        Analytics.shared.track(.paywallCTATapped, [
            "content_id": product.id,
            "value": product.price,
            "currency": product.priceFormatStyle.currencyCode,
            "source": source,
        ])
        Analytics.shared.track(.parentalGateShown, ["source": source])

        isPurchaseGatePresented = true
    }

    /// Compra de fato. Só chamada pelo `onPass` do gate.
    private func purchaseSelected() {
        guard let product = selectedProduct else { return }
        guard !isPurchasing else { return }

        // Passou o gate. `parental_gate_shown` menos `parental_gate_passed`
        // neste `source` é exatamente quanta receita o gate está segurando.
        Analytics.shared.track(.parentalGatePassed, ["source": source])

        isPurchasing = true
        errorMessage = nil

        Task {
            // Elegibilidade ao trial é medida ANTES da compra: depois dela o
            // usuário deixa de ser elegível e a resposta viraria sempre false,
            // classificando toda conversão como `subscribe`.
            let startsTrial = await eligibleForFreeTrial(product)

            Analytics.shared.track(.checkoutInitiated, [
                "content_id": product.id,
                "value": product.price,
                "currency": product.priceFormatStyle.currencyCode,
                "source": source,
            ])

            do {
                let outcome = try await store.purchase(product)
                switch outcome {
                case .success:
                    // `start_trial` e `subscribe` contam igual no funil; a
                    // distinção existe pro Meta CAPI, que os traduz em
                    // StartTrial e Purchase.
                    Analytics.shared.track(startsTrial ? .startTrial : .subscribe, [
                        "content_id": product.id,
                        "value": product.price,
                        "currency": product.priceFormatStyle.currencyCode,
                        "source": source,
                    ])
                    // isPremium vira true, onChange dismissa
                    break
                case .userCancelled:
                    break  // silent, user cancelou intencionalmente
                case .pending:
                    errorMessage = "Purchase is pending approval (Ask to Buy)."
                }
            } catch {
                errorMessage = error.localizedDescription
            }
            isPurchasing = false
        }
    }

    /// O usuário vai realmente entrar em trial ao comprar este produto?
    ///
    /// Ter oferta introdutória não basta: quem já assinou antes não é elegível
    /// de novo, e a Apple cobra o preço cheio direto.
    private func eligibleForFreeTrial(_ product: Product) async -> Bool {
        guard let subscription = product.subscription,
              subscription.introductoryOffer?.paymentMode == .freeTrial
        else { return false }
        return await subscription.isEligibleForIntroOffer
    }
}

// MARK: - Top Row

private struct TopRow: View {
    let onClose: () -> Void
    let onRestore: () -> Void

    var body: some View {
        HStack {
            Button(action: onClose) {
                Image(systemName: "xmark")
                    .font(.system(size: 15, weight: .bold))
                    .foregroundStyle(Theme.Colors.ink)
                    .frame(width: Touch.min, height: Touch.min)
            }
            .accessibilityLabel("Close")

            Spacer()

            Button(action: onRestore) {
                Text("Restore")
                    .font(.ui(13, weight: .semibold))
                    .foregroundStyle(Theme.Colors.textMuted)
                    .frame(minHeight: Touch.min)
                    .padding(.horizontal, Theme.Space.md)
            }
            .accessibilityLabel("Restore previous purchases")
        }
        .padding(.horizontal, Theme.Space.sm)
    }
}

// MARK: - Hero

/// Hero visual do paywall — mosaico de 3 covers reais empilhadas em
/// perspectiva. Sem card wrapper — mosaico ocupa toda a largura útil
/// direto sobre o fundo cream do paywall, mais airy e moderno.
///
/// ANIMAÇÕES (3 camadas, do transitório ao contínuo)
///
///   1. ENTRADA EM CASCATA (0.7s total, dispara no onAppear)
///      • Laterais entram deslizando de fora (slide horizontal + fade),
///        esquerda primeiro (0.00s), direita logo em seguida (0.10s)
///      • Central faz "pop-in" com spring bounce leve (0.30s delay,
///        scale 0.6 → 1.0 + fade)
///      Cria sensação de "livros sendo colocados no lugar".
///
///   2. IDLE BREATHING (contínua, começa 1.0s após entrada)
///      Cover central pulsa scale 1.00 ↔ 1.02 em loop lento (2.5s).
///      Muito sutil — sensação de "vivo" sem tirar foco do conteúdo.
///
///   3. IDLE FLOATING (contínua, começa 1.0s após entrada)
///      Laterais oscilam rotação em torno da base (±0.5° extra) em loop
///      lento (3s). Combina com breathing pra criar composição orgânica.
///
/// Todas respeitam `accessibilityReduceMotion` — pulam pra estado final
/// instantâneo se ligado.
private struct Hero: View {
    let stories: [Story]

    @Environment(\.accessibilityReduceMotion) private var reduceMotion

    // Estados de entrada (uma vez)
    @State private var leftAppeared = false
    @State private var rightAppeared = false
    @State private var centerAppeared = false

    // Estados contínuos (loop infinito depois de entrada)
    @State private var breathing = false
    @State private var floating = false

    /// Até 3 covers, priorizando premium.
    private var showcaseStories: [Story] {
        let withCovers = stories.filter {
            guard let name = $0.coverImage else { return false }
            return UIImage(named: name) != nil
        }
        let premium = withCovers.filter(\.isPremium)
        let pool = premium.isEmpty ? withCovers : premium
        return Array(pool.prefix(3))
    }

    var body: some View {
        Group {
            if showcaseStories.count >= 3 {
                stackedCovers
            } else if showcaseStories.count > 0 {
                singleCover(showcaseStories[0])
            } else {
                fallbackContent
            }
        }
        .frame(maxWidth: .infinity)
        .frame(height: 220)
        .onAppear {
            triggerAnimations()
        }
    }

    /// Layout de 3 covers em pilha animadas. Cada cover tem seu próprio
    /// state de aparição + delta contínuo (breathing/floating) aplicado
    /// via rotationEffect/scaleEffect adicional.
    private var stackedCovers: some View {
        ZStack {
            // Cover esquerda — atrás, rotação -5° + oscilação
            miniCover(showcaseStories[1])
                .rotationEffect(.degrees(-5 + (floating ? -0.5 : 0.5)))
                .offset(x: leftAppeared ? -62 : -220, y: 8)
                .opacity(leftAppeared ? 1 : 0)
                .zIndex(0)

            // Cover direita — atrás, rotação +5° + oscilação oposta
            miniCover(showcaseStories[2])
                .rotationEffect(.degrees(5 + (floating ? 0.5 : -0.5)))
                .offset(x: rightAppeared ? 62 : 220, y: 8)
                .opacity(rightAppeared ? 1 : 0)
                .zIndex(1)

            // Cover central — destaque na frente, breathing scale
            miniCover(showcaseStories[0], featured: true)
                .scaleEffect(centerAppeared ? (breathing ? 1.02 : 1.0) : 0.6)
                .opacity(centerAppeared ? 1 : 0)
                .zIndex(2)
        }
    }

    /// Cover do mosaico. `featured=true` = cover central grande com
    /// traço mais grosso pra dominar visualmente.
    private func miniCover(_ story: Story, featured: Bool = false) -> some View {
        Group {
            if let name = story.coverImage, UIImage(named: name) != nil {
                Image(name)
                    .resizable()
                    .aspectRatio(5/4, contentMode: .fill)
            } else {
                Theme.Colors.bgSepia
            }
        }
        .frame(width: featured ? 200 : 145, height: featured ? 160 : 116)
        .clipShape(RoundedRectangle(cornerRadius: Theme.Radius.md))
        .overlay(
            RoundedRectangle(cornerRadius: Theme.Radius.md)
                .stroke(
                    Theme.Colors.stroke,
                    lineWidth: featured ? Theme.Stroke.thick : Theme.Stroke.normal
                )
        )
        .hardShadow(
            RoundedRectangle(cornerRadius: Theme.Radius.md),
            offset: featured ? CGSize(width: 4, height: 5) : CGSize(width: 3, height: 4)
        )
    }

    /// Fallback pra 1 cover disponível.
    private func singleCover(_ story: Story) -> some View {
        miniCover(story, featured: true)
    }

    /// Fallback pra 0 covers (dev inicial). Sparkles rosa centralizados.
    private var fallbackContent: some View {
        Image(systemName: "sparkles")
            .font(.system(size: 56, weight: .light))
            .foregroundStyle(Theme.Colors.primary)
    }

    // MARK: - Animation orchestration

    /// Dispara entrada em cascata + agenda loops contínuos pra 1s depois
    /// (que é ~quando a entrada termina). Reduce Motion pula pra estado
    /// final instantâneo, sem loops (evita animação contínua indesejada).
    private func triggerAnimations() {
        if reduceMotion {
            leftAppeared = true
            rightAppeared = true
            centerAppeared = true
            return
        }

        // Entrada — laterais deslizam de fora, central faz pop-in
        withAnimation(.smooth(duration: 0.6)) {
            leftAppeared = true
        }
        withAnimation(.smooth(duration: 0.6).delay(0.1)) {
            rightAppeared = true
        }
        withAnimation(.spring(response: 0.55, dampingFraction: 0.7).delay(0.3)) {
            centerAppeared = true
        }

        // Loops contínuos começam DEPOIS que a entrada termina —
        // evita conflito de springs sobrepondo cascata inicial.
        DispatchQueue.main.asyncAfter(deadline: .now() + 1.0) {
            withAnimation(
                .easeInOut(duration: 2.5).repeatForever(autoreverses: true)
            ) {
                breathing = true
            }
            withAnimation(
                .easeInOut(duration: 3.0).repeatForever(autoreverses: true)
            ) {
                floating = true
            }
        }
    }
}

// MARK: - Title Block

private struct TitleBlock: View {
    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Space.sm) {
            Text("Unlock every story")
                .displayTitle(size: 34)
                .multilineTextAlignment(.leading)
                .fixedSize(horizontal: false, vertical: true)

            Text("Full library access, always.")
                .font(.body(16, weight: .medium))
                .foregroundStyle(Theme.Colors.textMuted)
                .italic()
        }
    }
}

// MARK: - Benefits

private struct Benefits: View {
    private let items: [(icon: String, text: String)] = [
        ("book.pages", "Every story, every chapter"),
        ("paintpalette", "Beautiful illustrations"),
        ("sparkles",     "New stories every month"),
        ("nosign",       "No ads, ever"),
    ]

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Space.md) {
            ForEach(items, id: \.text) { item in
                HStack(spacing: Theme.Space.md) {
                    Image(systemName: item.icon)
                        .font(.system(size: 16, weight: .bold))
                        .foregroundStyle(Theme.Colors.primary)
                        .frame(width: 28)

                    Text(item.text)
                        .font(.body(16, weight: .medium))
                        .foregroundStyle(Theme.Colors.ink)

                    Spacer()
                }
            }
        }
    }
}

// MARK: - Plan Cards

private struct PlanCards: View {
    let products: [Product]
    @Binding var selectedProductID: String
    let isLoading: Bool
    let onRetry: () -> Void

    private var annual: Product? { products.first { $0.id == ProductID.annual } }
    private var monthly: Product? { products.first { $0.id == ProductID.monthly } }

    /// Deliberadamente NÃO é `products.isEmpty`.
    ///
    /// Os dois cards são filtrados por ID exato. Se `products` trouxer algo
    /// que não bate com nenhum dos IDs conhecidos, o array não está vazio mas
    /// nenhum card renderiza — e o `else` abaixo produziria um VStack vazio,
    /// que é exatamente o buraco silencioso que se está fechando aqui. A
    /// pergunta certa não é "veio produto?", é "tem card pra mostrar?".
    private var hasNoPlanToShow: Bool { annual == nil && monthly == nil }

    var body: some View {
        VStack(spacing: Theme.Space.md) {
            if isLoading && hasNoPlanToShow {
                LoadingPlaceholder()
            } else if hasNoPlanToShow {
                PlansUnavailable(onRetry: onRetry)
            } else {
                if let annualProduct = annual {
                    PlanCard(
                        product: annualProduct,
                        isSelected: selectedProductID == annualProduct.id,
                        badge: trialBadge(for: annualProduct),
                        savings: computedSavings(),
                        onTap: { selectedProductID = annualProduct.id }
                    )
                }

                if let monthlyProduct = monthly {
                    PlanCard(
                        product: monthlyProduct,
                        isSelected: selectedProductID == monthlyProduct.id,
                        badge: nil,
                        savings: nil,
                        onTap: { selectedProductID = monthlyProduct.id }
                    )
                }
            }
        }
    }

    /// Se o produto anual tem intro offer de trial, mostra "N days free".
    private func trialBadge(for product: Product) -> String? {
        guard let intro = product.subscription?.introductoryOffer,
              intro.paymentMode == .freeTrial
        else { return nil }
        let days = intro.period.value * daysPerUnit(intro.period.unit)
        return "\(days) days free"
    }

    /// Calcula "SAVE X%" comparando anual vs mensal × 12.
    private func computedSavings() -> String? {
        guard let annual = annual, let monthly = monthly else { return nil }
        let annualPrice = NSDecimalNumber(decimal: annual.price).doubleValue
        let monthlyPrice = NSDecimalNumber(decimal: monthly.price).doubleValue
        let monthlyEquivalent = monthlyPrice * 12
        guard monthlyEquivalent > 0 else { return nil }
        let savingsPercent = (1 - annualPrice / monthlyEquivalent) * 100
        guard savingsPercent > 5 else { return nil }
        return "SAVE \(Int(savingsPercent))%"
    }

    private func daysPerUnit(_ unit: Product.SubscriptionPeriod.Unit) -> Int {
        switch unit {
        case .day: return 1
        case .week: return 7
        case .month: return 30
        case .year: return 365
        @unknown default: return 1
        }
    }
}

private struct PlanCard: View {
    let product: Product
    let isSelected: Bool
    let badge: String?
    let savings: String?
    let onTap: () -> Void

    var body: some View {
        PressBounce(scaleTo: 0.98, action: onTap) {
            HStack(alignment: .top, spacing: Theme.Space.md) {
                // Radio dot
                ZStack {
                    Circle()
                        .fill(isSelected ? Theme.Colors.primary : Theme.Colors.surface)
                        .frame(width: 22, height: 22)
                        .overlay(
                            Circle()
                                .stroke(
                                    isSelected ? Theme.Colors.primary : Theme.Colors.border,
                                    lineWidth: Theme.Stroke.normal
                                )
                        )

                    if isSelected {
                        Circle()
                            .fill(Theme.Colors.onAccent)
                            .frame(width: 8, height: 8)
                    }
                }

                VStack(alignment: .leading, spacing: Theme.Space.xs) {
                    HStack(spacing: Theme.Space.sm) {
                        Text(planName(for: product))
                            .font(.display(17, weight: .bold))
                            .foregroundStyle(Theme.Colors.ink)

                        if let badge {
                            Text(badge)
                                .font(.ui(10, weight: .bold))
                                .foregroundStyle(Theme.Colors.onInk)
                                .padding(.horizontal, Theme.Space.sm)
                                .padding(.vertical, 3)
                                .background(
                                    Capsule().fill(Theme.Colors.inkDeep)
                                )
                        }

                        Spacer()

                        if let savings {
                            Text(savings)
                                .font(.ui(10, weight: .bold))
                                .foregroundStyle(Theme.Colors.primary)
                        }
                    }

                    Text(priceLine(for: product))
                        .font(.body(14, weight: .medium))
                        .foregroundStyle(Theme.Colors.textMuted)
                }

                Spacer()
            }
            .padding(Theme.Space.lg)
            .background(
                RoundedRectangle(cornerRadius: Theme.Radius.md)
                    .fill(isSelected ? Theme.Colors.primaryFaint : Theme.Colors.surface)
                    .overlay(
                        RoundedRectangle(cornerRadius: Theme.Radius.md)
                            .stroke(
                                isSelected ? Theme.Colors.primary : Theme.Colors.border,
                                lineWidth: isSelected ? Theme.Stroke.normal : Theme.Stroke.hair
                            )
                    )
            )
        }
        .accessibilityElement(children: .combine)
        .accessibilityAddTraits(isSelected ? [.isSelected] : [])
    }

    private func planName(for product: Product) -> String {
        switch product.subscription?.subscriptionPeriod.unit {
        case .year:  return "Annual"
        case .month: return "Monthly"
        case .week:  return "Weekly"
        default:     return product.displayName
        }
    }

    /// Ex: "R$ 399,90 per year" ou "Then R$ 399,90/year"
    private func priceLine(for product: Product) -> String {
        let base = "\(product.displayPrice) / \(periodString(product))"
        if product.subscription?.introductoryOffer?.paymentMode == .freeTrial {
            return "Then " + base
        }
        return base
    }

    private func periodString(_ product: Product) -> String {
        switch product.subscription?.subscriptionPeriod.unit {
        case .year:  return "year"
        case .month: return "month"
        case .week:  return "week"
        default:     return "period"
        }
    }
}

private struct LoadingPlaceholder: View {
    var body: some View {
        VStack(spacing: Theme.Space.md) {
            ForEach(0..<2, id: \.self) { _ in
                RoundedRectangle(cornerRadius: Theme.Radius.md)
                    .fill(Theme.Colors.track)
                    .frame(height: 76)
                    .overlay(
                        ProgressView().tint(Theme.Colors.primary)
                    )
            }
        }
    }
}

// MARK: - Plans Unavailable

/// O que aparece no lugar dos planos quando nenhum carregou.
///
/// Antes daqui, esse caso não tinha representação nenhuma: os dois `if let`
/// não renderizavam, o VStack ficava vazio e o único sinal visível era o CTA
/// cinza lá embaixo, com um rótulo — "Select a plan" — que instrui a fazer
/// algo impossível. O usuário conclui que o app está quebrado e sai; nada
/// distingue "sem rede" de "produto mal configurado", nem pro usuário nem
/// pra quem for depurar depois.
///
/// A cópia fala de conexão porque é a causa que o usuário pode resolver.
/// Configuração errada de produto tem a mesma aparência aqui, mas quem
/// conserta isso é você, avisado pelo `paywall_products_empty` — não ele.
private struct PlansUnavailable: View {
    let onRetry: () -> Void

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Space.md) {
            HStack(alignment: .top, spacing: Theme.Space.sm) {
                Image(systemName: "exclamationmark.triangle.fill")
                    .font(.system(size: 15, weight: .bold))
                    .foregroundStyle(Theme.Colors.danger)

                VStack(alignment: .leading, spacing: Theme.Space.xs) {
                    Text("Plans couldn't load")
                        .font(.ui(15, weight: .bold))
                        .foregroundStyle(Theme.Colors.ink)

                    Text("Check your connection and try again. You won't be charged for anything until you pick a plan.")
                        .font(.body(13, weight: .medium))
                        .foregroundStyle(Theme.Colors.textStrong)
                        .fixedSize(horizontal: false, vertical: true)
                }

                Spacer(minLength: 0)
            }

            PressBounce(action: onRetry) {
                Text("Try again")
                    .font(.ui(15, weight: .bold))
                    .foregroundStyle(Theme.Colors.ink)
                    .frame(maxWidth: .infinity, minHeight: Touch.min)
                    .background(
                        RoundedRectangle(cornerRadius: Theme.Radius.sm)
                            .fill(Theme.Colors.surface)
                            .overlay(
                                RoundedRectangle(cornerRadius: Theme.Radius.sm)
                                    .stroke(Theme.Colors.stroke, lineWidth: Theme.Stroke.normal)
                            )
                    )
            }
            .accessibilityLabel("Try loading plans again")
        }
        .padding(Theme.Space.md)
        .background(
            RoundedRectangle(cornerRadius: Theme.Radius.md)
                .fill(Theme.Colors.dangerTint)
        )
    }
}

// MARK: - Error Banner

private struct ErrorBanner: View {
    let message: String

    var body: some View {
        HStack(alignment: .top, spacing: Theme.Space.sm) {
            Image(systemName: "exclamationmark.triangle.fill")
                .font(.system(size: 14, weight: .bold))
                .foregroundStyle(Theme.Colors.danger)
            Text(message)
                .font(.body(13, weight: .medium))
                .foregroundStyle(Theme.Colors.ink)
                .fixedSize(horizontal: false, vertical: true)
            Spacer()
        }
        .padding(Theme.Space.md)
        .background(
            RoundedRectangle(cornerRadius: Theme.Radius.sm)
                .fill(Theme.Colors.dangerTint)
        )
    }
}

// MARK: - Sticky CTA

private struct StickyCTA: View {
    let product: Product?
    let isPurchasing: Bool
    let hasNoPlanAvailable: Bool
    let onTap: () -> Void

    private var buttonLabel: String {
        if isPurchasing { return "Processing…" }
        // "Select a plan" só faz sentido quando existe plano pra selecionar.
        // Com a lista vazia, o rótulo mandava o usuário fazer algo que a tela
        // não permitia — o card acima já explica o que houve.
        if hasNoPlanAvailable { return "Unavailable" }
        guard let product else { return "Select a plan" }
        if product.subscription?.introductoryOffer?.paymentMode == .freeTrial {
            return "Start free trial"
        }
        return "Continue"
    }

    var body: some View {
        VStack(spacing: Theme.Space.sm) {
            PressBounce(action: onTap) {
                HStack(spacing: Theme.Space.sm) {
                    if isPurchasing {
                        ProgressView()
                            .tint(Theme.Colors.onAccent)
                            .scaleEffect(0.85)
                    }
                    Text(buttonLabel)
                        .font(.ui(16, weight: .bold))
                }
                .foregroundStyle(Theme.Colors.onAccent)
                .frame(maxWidth: .infinity, minHeight: Touch.min + 8)
                .background(
                    RoundedRectangle(cornerRadius: Theme.Radius.md)
                        .fill(product == nil || isPurchasing
                              ? Theme.Colors.textFaint
                              : Theme.Colors.primary)
                        .overlay(
                            RoundedRectangle(cornerRadius: Theme.Radius.md)
                                .stroke(Theme.Colors.stroke, lineWidth: Theme.Stroke.thick)
                        )
                )
                .hardShadow(
                    RoundedRectangle(cornerRadius: Theme.Radius.md),
                    offset: CGSize(width: 3, height: 4)
                )
            }
            .disabled(product == nil || isPurchasing)

            // Legal footer — obrigatório pra App Review
            LegalFooter(product: product)
        }
        .padding(.horizontal, Theme.Space.lg)
        .padding(.bottom, Theme.Space.md)
        .padding(.top, Theme.Space.sm)
        .background(
            LinearGradient(
                colors: [Theme.Colors.bg.opacity(0), Theme.Colors.bg],
                startPoint: .top,
                endPoint: .center
            )
            .ignoresSafeArea()
        )
    }
}

// MARK: - Legal Footer

/// Wrapper Identifiable pra URL, exigido pelo `.parentalGate(item:)`. Existe
/// só porque URL não é Identifiable — nada além disso.
private struct GatedLink: Identifiable {
    let id = UUID()
    let url: URL
}

private struct LegalFooter: View {
    let product: Product?

    /// SwiftUI nativo em vez de UIApplication.shared.open — este arquivo só
    /// importa SwiftUI e StoreKit, e o UIKit vinha por reexport implícito.
    @Environment(\.openURL) private var openURL

    /// Link aguardando o parental gate. Setar abre o gate; o gate devolve o
    /// mesmo item no onPass e a URL abre aí. Categoria Kids exige gate antes
    /// de qualquer link que saia do app.
    @State private var pendingLink: GatedLink?

    var body: some View {
        VStack(spacing: Theme.Space.xs) {
            Text(disclosureText)
                .font(.ui(10, weight: .medium))
                .foregroundStyle(Theme.Colors.textFaint)
                .multilineTextAlignment(.center)

            HStack(spacing: Theme.Space.md) {
                Button("Terms") { openTerms() }
                Text("·")
                Button("Privacy") { openPrivacy() }
            }
            .font(.ui(10, weight: .semibold))
            .foregroundStyle(Theme.Colors.textMuted)
        }
        .parentalGate(item: $pendingLink) { link in
            openURL(link.url)
        }
    }

    private var disclosureText: String {
        guard let product else {
            return "Subscription auto-renews. Cancel anytime in Settings."
        }
        let period = product.subscription?.subscriptionPeriod.unit == .year
            ? "yearly" : "monthly"
        return "Auto-renews \(period) at \(product.displayPrice) until cancelled."
    }

    private func openTerms() {
        requestOpen(LegalLinks.termsOfUse)
    }

    private func openPrivacy() {
        requestOpen(LegalLinks.privacyPolicy)
    }

    /// Enfileira o link pro gate. Se a URL não parsear (só aconteceria se
    /// alguém quebrasse a string em LegalLinks), não faz nada em vez de
    /// crashar no paywall — é a última tela onde a gente quer um crash.
    private func requestOpen(_ url: URL?) {
        guard let url else { return }
        pendingLink = GatedLink(url: url)
    }
}
