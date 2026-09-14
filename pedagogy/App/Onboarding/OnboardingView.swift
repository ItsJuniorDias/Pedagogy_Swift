//
//  OnboardingView.swift
//  pedagogy
//
//  ─── ONBOARDING CONTAINER v2.2 ──────────────────────────────────────────────
//  Wrapper minimalista. Gerencia:
//    • Paginação horizontal via TabView com PageStyle
//    • Page indicator custom (preto sobre creme, sem cor de acento)
//    • CTA que muda de "Next" pra "Enable notifications" (page 3) pra
//      "Start reading" (última página)
//    • Fundo estático creme (antes tinha tint por página, agora paleta
//      minimal = fundo uniforme)
//
//  MUDANÇAS DA v2.2
//
//  Adicionada OnboardingPageNotifications (index 2) entre "Come back tomorrow"
//  e "Your first story is waiting". Sequência atualizada:
//    0. "A quiet place to read"       — mostra o reader
//    1. "Come back tomorrow"          — mostra cliffhanger + streak
//    2. "Never miss a story"          — pede permissão de notif
//    3. "Your first story is waiting" — cover + CTA "Start reading"
//
//  A ordem foi escolhida pra que a Page 3 (com "Start reading") continue
//  sendo o clímax emocional. Colocar notif DEPOIS quebraria esse ritmo.
//
//  MUDANÇAS DA v2.1
//
//  1. Páginas não são mais modelos — são views concretas. Ver OnboardingPage.swift.
//  2. Fundo uniforme creme (bg).
//  3. CTA sempre rosa.
//  4. Última página muda o CTA pra "Start reading".
//  ────────────────────────────────────────────────────────────────────────────

import SwiftUI

struct OnboardingView: View {
    /// Chamado quando o usuário toca CTA na última página. RootView marca
    /// onboarding completed=true e mostra Home. A Home naturalmente vai
    /// mostrar House of Clocks como featured (regra: primeira não lida).
    let onFinish: () -> Void

    /// Manager de notificações injetado via environment. Usado na página 3
    /// (index 2) pra pedir permissão quando o usuário toca "Enable notifications".
    @Environment(NotificationManager.self) private var notifications

    @State private var currentIndex = 0

    /// Gate que precede o pedido de permissão de notificação. A categoria Kids
    /// exige parental gate antes de "request permissions", não só antes de
    /// compra e link externo. Ver ParentalGate.swift.
    @State private var isParentalGatePresented = false

    /// Páginas já contabilizadas. O TabView deixa voltar com swipe, e sem este
    /// guard alguém indeciso viraria seis "views" da página 2 — o que faria a
    /// página parecer mais popular quanto MAIS confusa ela fosse.
    @State private var pagesTracked: Set<Int> = []

    private let pageCount = 4
    private var isLastPage: Bool { currentIndex == pageCount - 1 }
    private var isNotificationsPage: Bool { currentIndex == 2 }

    /// CTA muda de significado por página. Extraído em prop pra deixar o
    /// body legível.
    private var ctaTitle: String {
        if isNotificationsPage { return "Enable notifications" }
        return isLastPage ? "Start reading" : "Next"
    }

    var body: some View {
        ZStack {
            Theme.Colors.bg.ignoresSafeArea()

            TabView(selection: $currentIndex) {
                OnboardingPage1().tag(0)
                OnboardingPage2().tag(1)
                OnboardingPageNotifications().tag(2)
                OnboardingPage3().tag(3)
            }
            .tabViewStyle(.page(indexDisplayMode: .never))
        }
        .safeAreaInset(edge: .bottom) {
            // ─── FOOTER: page indicator + CTA ────────────────────────
            VStack(spacing: Theme.Space.xl) {
                PageIndicator(count: pageCount, current: currentIndex)

                PressBounce(action: advance) {
                    HStack(spacing: Theme.Space.sm) {
                        Text(ctaTitle)
                            .font(.ui(16, weight: .bold))
                        Image(systemName: "arrow.right")
                            .font(.system(size: 14, weight: .bold))
                    }
                    .foregroundStyle(Theme.Colors.onAccent)
                    .frame(maxWidth: .infinity, minHeight: Touch.min + 8)
                    .background(
                        RoundedRectangle(cornerRadius: Theme.Radius.md)
                            .fill(Theme.Colors.primary)
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
                .padding(.horizontal, Theme.Space.xl)

                // Skip link — só aparece na página de notificações.
                // Respeita agency: se o usuário não quer notif, um único
                // tap discreto pula sem penalidade. Ele avança MESMO se
                // pular (não trava o onboarding).
                if isNotificationsPage {
                    Button {
                        skipNotifications()
                    } label: {
                        Text("Skip for now")
                            .font(.ui(13, weight: .medium))
                            .foregroundStyle(Theme.Colors.textMuted)
                            .padding(.vertical, Theme.Space.xs)
                    }
                    .accessibilityLabel("Skip notifications and continue")
                } else {
                    // Reserva o espaço vertical pra evitar layout jump
                    // entre páginas. Height ~= altura visual do Skip
                    // button acima (13pt font + padding).
                    Color.clear.frame(height: 28)
                }
            }
            .padding(.top, Theme.Space.md)
            .padding(.bottom, Theme.Space.lg)
        }
        .parentalGate(isPresented: $isParentalGatePresented) {
            requestNotificationsAndAdvance()
        }
        .task {
            // Entrada no onboarding. `first_open` conta a instalação; este conta
            // quem chegou a ver a primeira tela — os dois quase sempre batem, e
            // quando não baterem é sinal de crash no launch.
            Analytics.shared.track(.onboardingStart)
            trackPage(currentIndex)
        }
        .onChange(of: currentIndex) { _, newIndex in
            trackPage(newIndex)
        }
    }

    // MARK: - Analytics

    /// Nome legível da página, mandado em `source` — que é coluna indexada no
    /// backend. Um param novo (tipo `page: 2`) ficaria só dentro do JSON:
    /// consultável, mas não agrupável, e é justamente o agrupamento que
    /// responde "onde as pessoas desistem".
    private static func pageName(_ index: Int) -> String {
        switch index {
        case 0: return "reader"
        case 1: return "streak"
        case 2: return "notifications"
        case 3: return "first_story"
        default: return "page_\(index)"
        }
    }

    /// Só a PRIMEIRA vez que cada página aparece.
    private func trackPage(_ index: Int) {
        guard pagesTracked.insert(index).inserted else { return }
        Analytics.shared.track(.onboardingPage, ["source": Self.pageName(index)])
    }

    /// Contexto do gate. Existe outro gate no paywall com `source` diferente —
    /// os dois medem coisas distintas e não podem cair no mesmo balde.
    private var gateSource: String { "onboarding_notifications" }

    // MARK: - Actions

    private func advance() {
        if isNotificationsPage {
            Analytics.shared.track(.parentalGateShown, ["source": gateSource])
            // NÃO pede permissão direto: abre o gate primeiro. O prompt do
            // iOS só aparece depois que um adulto resolve o desafio.
            // Se cancelar, nada acontece — continua na página, e o
            // "Skip for now" segue disponível pra avançar sem permissão.
            isParentalGatePresented = true
            return
        }

        if isLastPage {
            Analytics.shared.track(.onboardingComplete)
            onFinish()
        } else {
            withAnimation(.spring(response: 0.4, dampingFraction: 0.75)) {
                currentIndex += 1
            }
        }
    }

    /// Pede a permissão e avança. Só chamada DEPOIS do parental gate passar.
    /// Async, mas Task fire-and-forget porque a UI já pode animar em paralelo.
    /// O request do iOS mostra alert nativo — a UI do app fica esperando ele
    /// fechar antes do advance visual acontecer.
    private func requestNotificationsAndAdvance() {
        // Passou o gate. `shown` menos `passed` é quanta gente o desafio
        // matemático barrou aqui.
        Analytics.shared.track(.parentalGatePassed, ["source": gateSource])
        Analytics.shared.track(.notificationsPrompt, ["source": gateSource])

        Task {
            let granted = await notifications.requestAuthorization()
            await MainActor.run {
                // Permissão de notificação é a alavanca de retorno deste app —
                // a notif de "nova história" é o que traz a criança de volta.
                // Saber a taxa de concessão vale tanto quanto saber a de compra.
                Analytics.shared.track(
                    granted ? .notificationsGranted : .notificationsDenied,
                    ["source": gateSource]
                )
                withAnimation(.spring(response: 0.4, dampingFraction: 0.75)) {
                    currentIndex += 1
                }
            }
        }
    }

    /// Avança sem pedir permissão. authStatus continua .notDetermined —
    /// o usuário pode habilitar depois via Settings do sistema ou (futuro)
    /// tela in-app de configurações.
    private func skipNotifications() {
        Analytics.shared.track(.notificationsSkipped, ["source": gateSource])
        withAnimation(.spring(response: 0.4, dampingFraction: 0.75)) {
            currentIndex += 1
        }
    }
}

// MARK: - Page Indicator

/// Indicator preto sobre creme. Um dot expandido pro atual, dots fixos pros
/// outros. Sem cor de acento (paleta minimal).
private struct PageIndicator: View {
    let count: Int
    let current: Int

    var body: some View {
        HStack(spacing: Theme.Space.sm) {
            ForEach(0..<count, id: \.self) { index in
                Capsule()
                    .fill(index == current ? Theme.Colors.ink : Theme.Colors.ink.opacity(0.2))
                    .frame(
                        width: index == current ? 24 : 8,
                        height: 8
                    )
                    .animation(.spring(response: 0.4, dampingFraction: 0.7), value: current)
            }
        }
        .accessibilityElement()
        .accessibilityLabel("Page \(current + 1) of \(count)")
    }
}
