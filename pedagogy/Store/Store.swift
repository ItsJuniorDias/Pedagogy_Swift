//
//  Store.swift
//  pedagogy
//
//  ─── STORE (StoreKit 2) ─────────────────────────────────────────────────────
//  Camada única de assinatura/compra. Substitui `react-native-purchases`
//  (RevenueCat) da v1 por StoreKit 2 nativo — sem SDK terceirizado no binário
//  (bom pra categoria Kids), sem custo mensal, e sem coleta de IDFA.
//
//  O QUE ESTA CLASSE FAZ
//
//    1. Carrega produtos da App Store por ID (`Product.products(for:)`)
//    2. Ouve `Transaction.updates` em background pra pegar renovações mesmo
//       com o app ativo (a Apple entrega renovações via essa stream)
//    3. Recomputa `isPremium` toda vez que uma transação aparece/some
//    4. Expõe `purchase(_:)` e `restore()` pra UI
//
//  O QUE ESTA CLASSE NÃO FAZ
//
//    • Analytics de venda — RevenueCat dava trial conversion, MRR, churn.
//      Sem RC, essa métrica vem do App Store Connect → Sales/Trends.
//    • Server-side receipt validation — em produção você quer validar o JWS
//      no seu backend Render pra prevenir modding. Marquei o ponto exato onde
//      essa validação entra (procure "// TODO: server verify" abaixo).
//    • Coin packs consumíveis — a v1 tinha coin_small/medium/large/mega pro
//      farm-game. O v2 não tem esse jogo, então só assinatura.
//
//  MIGRAÇÃO DE ASSINANTES DA v1 (RevenueCat)
//
//  A COMPRA em si acontece na Apple — RevenueCat só espelhava. Quando um
//  assinante da v1 abrir o v2, `Transaction.currentEntitlements` já devolve
//  a compra ativa dele automaticamente. Zero migration necessária, contanto
//  que o `productID` seja EXATAMENTE o mesmo que a v1 usava. Confirme isso
//  no App Store Connect antes de subir a v2.
//  ────────────────────────────────────────────────────────────────────────────

import Foundation
import StoreKit

// ─── PRODUCT IDs ────────────────────────────────────────────────────────────
// Estes valores precisam ser IDÊNTICOS aos do App Store Connect →
// Monetization → Subscriptions. Product ID no ASC é IMUTÁVEL depois de criado,
// então quem se ajusta é este arquivo, nunca o outro lado.
//
// Conferidos no ASC (grupo 22134361, ambos Approved):
//   annual_pedagogy   → 1 year
//   monthly_pedagogy  → 1 month
//
// ⚠️  ARMADILHA QUE JÁ CUSTOU UMA RELEASE
//
//  `Product.products(for:)` NÃO lança erro quando um ID não existe na App
//  Store — ele apenas não devolve aquele produto. ID errado vira array vazio,
//  `loadError` nil, e o paywall renderiza o caminho de sucesso com zero planos:
//  botão cinza, sem mensagem, sem nada no console.
//
//  Pior: com um arquivo .storekit ativo no scheme (Product → Scheme → Edit →
//  Run → Options → StoreKit Configuration), o simulador responde do arquivo
//  local e nunca consulta a Apple. Tudo funciona em debug e quebra só na
//  App Store. Foi exatamente isso que aconteceu na v2.
//
//  Por isso `Products.storekit` usa os MESMOS IDs daqui. Se um dia divergirem
//  de novo, o bug volta invisível. Antes de publicar, valide sempre pelo
//  TestFlight, que usa os produtos reais.

enum ProductID {
    static let annual  = "annual_pedagogy"
    static let monthly = "monthly_pedagogy"

    static let all: [String] = [annual, monthly]

    /// IDs que dão acesso premium. Se você adicionar plano vitalício depois,
    /// põe aqui.
    static let premiumEntitlementIDs: Set<String> = [annual, monthly]
}

// ─── STORE (Observable) ─────────────────────────────────────────────────────
// `@Observable` (Swift 5.9+) substitui `@Published` do Combine — não precisa
// de `ObservableObject`, não precisa de `@Published` em cada prop.
// Injete via `.environment(store)` no `App` e leia via `@Environment(Store.self)`.

@Observable
@MainActor
final class Store {
    // ── State público ──
    private(set) var products: [Product] = []
    private(set) var purchasedIDs: Set<String> = []
    private(set) var isLoading: Bool = false
    private(set) var loadError: String?

    /// True se o usuário tem qualquer entitlement premium ativo.
    /// Fonte da verdade da gate de conteúdo premium.
    var isPremium: Bool {
        !purchasedIDs.isDisjoint(with: ProductID.premiumEntitlementIDs)
    }

    init() {
        // Task de background que fica ouvindo a stream de updates. Isso pega
        // renovação, cancelamento, reembolso enquanto o app está aberto.
        //
        // Não armazenamos referência ao Task nem fazemos cleanup no deinit:
        //   1. `Store` é única (nasce em pedagogyApp, morre com o app);
        //   2. `[weak self]` + `guard let self` faz o Task terminar sozinho
        //      caso a `Store` seja desalocada (que não acontece na prática);
        //   3. `deinit` em Swift é nonisolated e não pode tocar em property
        //      MainActor-isolated — se armazenássemos o Task numa property,
        //      Swift 6 concurrency recusaria compilar.
        Task { [weak self] in
            for await update in Transaction.updates {
                guard let self else { return }
                await self.handle(update)
            }
        }
    }

    // ─── CARREGAMENTO DE PRODUTOS ─────────────────────────────────────────
    // Chame no launch do app (`pedagogyApp.task { await store.load() }`).
    // Refaz o cálculo de entitlements toda vez que rodar.

    func load() async {
        isLoading = true
        loadError = nil
        defer { isLoading = false }

        do {
            products = try await Product.products(for: ProductID.all)
                .sorted { $0.price > $1.price }  // maior preço primeiro (anual antes de mensal)

            // Array vazio NÃO cai no catch. A App Store devolve 200 com lista
            // vazia quando nenhum dos IDs pedidos existe — do ponto de vista
            // do StoreKit foi um sucesso. Sem esta checagem, `loadError` fica
            // nil e a UI acha que carregou.
            //
            // Quando isso dispara, a causa é quase sempre uma destas:
            //   1. ID divergente entre ProductID e o App Store Connect
            //   2. Assinatura não Approved no ASC
            //   3. Assinatura sem preço/disponibilidade na storefront do usuário
            //   4. Paid Apps Agreement expirado
            if products.isEmpty {
                loadError = "No plans available."
                print("[Store] products(for:) devolveu VAZIO para \(ProductID.all)")
                print("[Store] confira: IDs batem com o ASC? assinaturas Approved? disponíveis nesta storefront?")
            } else {
                // Carregou alguma coisa mas não tudo. Não quebra o paywall
                // (o que carregou aparece), mas é sintoma do mesmo problema
                // e some no silêncio se ninguém logar.
                let missing = Set(ProductID.all).subtracting(products.map(\.id))
                if !missing.isEmpty {
                    print("[Store] IDs não encontrados na App Store: \(missing.sorted())")
                }
            }

            await refreshEntitlements()
        } catch {
            loadError = "Falha ao carregar produtos: \(error.localizedDescription)"
            print("[Store] load error:", error)
        }
    }

    /// Rechecca todas as compras ativas. Chamada no launch e depois de
    /// qualquer purchase/restore.
    func refreshEntitlements() async {
        var active: Set<String> = []
        for await result in Transaction.currentEntitlements {
            if let tx = try? checkVerified(result) {
                active.insert(tx.productID)
            }
        }
        purchasedIDs = active
    }

    // ─── COMPRA ───────────────────────────────────────────────────────────

    enum PurchaseOutcome {
        case success
        case userCancelled
        case pending   // aguarda aprovação parental (Ask to Buy) ou outra fricção
    }

    func purchase(_ product: Product) async throws -> PurchaseOutcome {
        let result = try await product.purchase()

        switch result {
        case .success(let verification):
            // Assinatura JWS já veio verificada pela Apple. Se você quer
            // validação adicional no seu backend, o payload vai aqui.
            let transaction = try checkVerified(verification)

            // TODO: server verify — em produção, envie o `verification` (JWS)
            // pro seu backend Render pra revalidar antes de liberar acesso.
            // Referência: https://developer.apple.com/documentation/appstoreserverapi

            await transaction.finish()
            await refreshEntitlements()
            return .success

        case .userCancelled:
            return .userCancelled

        case .pending:
            return .pending

        @unknown default:
            return .userCancelled
        }
    }

    // ─── RESTORE ──────────────────────────────────────────────────────────
    // Botão obrigatório pela Apple em todo paywall. Força re-sincronização
    // com o servidor da App Store — útil quando o usuário troca de device
    // ou reinstala.

    func restore() async {
        try? await AppStore.sync()
        await refreshEntitlements()
    }

    // ─── HANDLING de updates de background ────────────────────────────────

    private func handle(_ result: VerificationResult<Transaction>) async {
        guard let transaction = try? checkVerified(result) else { return }
        await transaction.finish()
        await refreshEntitlements()
    }

    // ─── VERIFICAÇÃO ──────────────────────────────────────────────────────
    // A Apple entrega transações num envelope `VerificationResult`.
    // Se veio `.unverified`, a assinatura JWS não bate (adulterada) — descarta.

    enum StoreError: Error, LocalizedError {
        case failedVerification

        var errorDescription: String? {
            switch self {
            case .failedVerification:
                return "A verificação da compra falhou. Tente novamente."
            }
        }
    }

    private func checkVerified<T>(_ result: VerificationResult<T>) throws -> T {
        switch result {
        case .verified(let value):
            return value
        case .unverified:
            throw StoreError.failedVerification
        }
    }
}
