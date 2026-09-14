//
//  RootView.swift
//  pedagogy
//
//  ─── ROOT VIEW ──────────────────────────────────────────────────────────────
//  Decide qual tela mostrar na abertura do app.
//
//  FLUXO
//
//    • Primeira abertura (nunca completou onboarding) → OnboardingView
//    • Ao terminar o onboarding → paywall de introdução, uma única vez
//    • Depois disso → MainTabView
//
//  O PAYWALL DE INTRODUÇÃO
//
//  Até aqui o paywall só aparecia por conteúdo: o usuário tentava abrir uma
//  história premium e batia nele. Agora ele também aparece uma vez logo depois
//  do onboarding.
//
//  A troca tem custo e vale saber qual: o paywall por conteúdo pega alguém que
//  já quer uma história específica — intenção alta, contexto claro. O de
//  introdução pega todo mundo, inclusive quem ainda não leu uma linha. Converte
//  mais em volume e converte pior em taxa, e é normal ver a taxa do funil cair
//  quando ele entra, sem que nada tenha piorado.
//
//  Por isso ele manda `source: "onboarding"` e o outro manda
//  `source: "story_detail"`: o backend indexa `source` em coluna própria, então
//  dá pra comparar as duas portas separadas em vez de olhar uma média que
//  esconde as duas.
//
//  REGRAS
//
//  • Uma vez só, marcada em `@AppStorage`. Dispensou, não volta — inclusive nos
//    launches seguintes.
//  • Não aparece pra quem já é premium (reinstalação com restore, por exemplo).
//  • Sheet, não fullScreenCover: dá swipe pra dispensar. Num app da Categoria
//    Kids, uma saída óbvia do paywall é o que se quer mostrar na revisão da
//    App Store — e a compra em si continua atrás do parental gate.
//
//  PERSISTÊNCIA
//
//  `@AppStorage` grava em UserDefaults. Não uso LibraryProgress pra isso
//  porque é config leve e independente do progresso de leitura — se o
//  usuário resetar o progresso, não deve ver o onboarding de novo.
//  ────────────────────────────────────────────────────────────────────────────

import SwiftUI

struct RootView: View {
    @AppStorage("pedagogy.onboarding.completed") private var onboardingCompleted = false

    /// Marcado no instante em que o paywall de introdução é agendado, não
    /// quando ele é fechado. Se o app morrer com ele aberto, não reaparece —
    /// insistir com quem já viu é o caminho curto pra desinstalação.
    @AppStorage("pedagogy.paywall.introShown") private var introPaywallShown = false

    @Environment(Store.self) private var store

    @State private var isIntroPaywallPresented = false

    var body: some View {
        Group {
            if onboardingCompleted {
                // MainTabView traz a tab bar bottom (liquid glass no iOS 26+).
                // Read (Home) e Library ficam abaixo dessa raiz.
                MainTabView()
            } else {
                OnboardingView {
                    finishOnboarding()
                }
            }
        }
        .sheet(isPresented: $isIntroPaywallPresented) {
            PaywallView(source: "onboarding")
        }
    }

    private func finishOnboarding() {
        onboardingCompleted = true

        guard !introPaywallShown, !store.isPremium else { return }
        introPaywallShown = true

        // O onboarding sai de cena com animação. Apresentar a sheet no mesmo
        // frame coloca duas transições disputando a mesma janela — o SwiftUI
        // engole uma das duas e o paywall simplesmente não abre. Meio segundo
        // deixa a primeira terminar.
        Task {
            try? await Task.sleep(for: .milliseconds(500))
            isIntroPaywallPresented = true
        }
    }
}
