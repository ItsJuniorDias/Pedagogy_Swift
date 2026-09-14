//
//  OnboardingPageNotifications.swift
//  pedagogy
//
//  ─── ONBOARDING PAGE: NOTIFICATIONS ─────────────────────────────────────────
//  Terceira página do onboarding (index 2). Pede permissão pra notificações
//  locais que avisam quando uma nova história é publicada.
//
//  ORDEM EDITORIAL — por que fica ANTES da "Your first story is waiting"
//
//  A Page3 ("Your first story is waiting" + CTA "Start reading") é o clímax
//  emocional do onboarding — a última coisa que o usuário vê antes de cair
//  no app. Colocar a página de notificações DEPOIS quebraria esse ritmo
//  (o "Start reading" iria pra... uma tela de permissão? Frio).
//
//  Colocando ANTES: usuário sente a promessa do produto (pages 1-2 mostram
//  o reader), aceita o compromisso de retornar (notifs), e enfim entra na
//  primeira história. Sequência natural: valor → contrato → ação.
//
//  DESIGN
//
//  Preview visual = um mock de banner de notif iOS mostrando exatamente o
//  que o usuário vai ver na tela dele quando uma história nova sair. Isso
//  é dispositivo persuasivo direto — "aqui está o que vai chegar, não é
//  spam".
//
//  Copy calibrada pra tom quiet: "once a week, no more". Sem hype, sem
//  urgência falsa.
//
//  CTA (no container OnboardingView) muda pra "Enable notifications" nesta
//  página. Ao tocar, chama requestAuthorization() e avança. Se o usuário
//  negar no sistema, avança do mesmo jeito — a página seguinte não sabe se
//  concedeu ou não; o scheduling silenciosamente no-op se authStatus != .authorized.
//  ────────────────────────────────────────────────────────────────────────────

import SwiftUI

struct OnboardingPageNotifications: View {
    var body: some View {
        VStack(spacing: Theme.Space.xxxl) {
            Spacer(minLength: Theme.Space.xxl)

            // ─── PREVIEW: banner de notif iOS ──────────────────────
            NotificationBannerPreview()
                .padding(.horizontal, Theme.Space.xxl)

            Spacer(minLength: Theme.Space.xxl)

            // ─── COPY ──────────────────────────────────────────────
            VStack(spacing: Theme.Space.md) {
                Text("Never miss\na story")
                    .displayTitle(size: 34)
                    .multilineTextAlignment(.center)
                    .fixedSize(horizontal: false, vertical: true)

                Text("We'll ping you gently when a new story\narrives. Once a week, no more.")
                    .font(.body(16, weight: .regular))
                    .foregroundStyle(Theme.Colors.textMuted)
                    .multilineTextAlignment(.center)
                    .padding(.horizontal, Theme.Space.xxl)
            }

            Spacer(minLength: Theme.Space.xxxl)
        }
    }
}

// MARK: - Notification Banner Preview

/// Mock visual de um banner de notif iOS. Formato: card branco com sombra
/// suave, ícone do app à esquerda, título em bold, corpo em regular, hora
/// à direita. Mostra o texto EXATO que o usuário verá quando uma história
/// nova sair — nada de placeholder.
private struct NotificationBannerPreview: View {
    var body: some View {
        HStack(alignment: .top, spacing: Theme.Space.md) {
            // ─── App icon mock (rounded, com sombra hard Mignola) ──
            RoundedRectangle(cornerRadius: 12, style: .continuous)
                .fill(Theme.Colors.primary)
                .frame(width: 44, height: 44)
                .overlay(
                    Image(systemName: "book.fill")
                        .font(.system(size: 20, weight: .bold))
                        .foregroundStyle(Theme.Colors.onAccent)
                )
                .overlay(
                    RoundedRectangle(cornerRadius: 12, style: .continuous)
                        .stroke(Theme.Colors.stroke, lineWidth: Theme.Stroke.normal)
                )

            // ─── Texto da notif ────────────────────────────────────
            VStack(alignment: .leading, spacing: 2) {
                HStack {
                    Text("PEDAGOGY")
                        .font(.ui(11, weight: .bold))
                        .tracking(0.5)
                        .foregroundStyle(Theme.Colors.textMuted)
                    Spacer()
                    Text("now")
                        .font(.ui(11, weight: .regular))
                        .foregroundStyle(Theme.Colors.textMuted)
                }
                Text("New story this week")
                    .font(.ui(14, weight: .semibold))
                    .foregroundStyle(Theme.Colors.ink)
                    .lineLimit(1)
                Text("The Fox and the North Wind")
                    .font(.ui(14, weight: .regular))
                    .foregroundStyle(Theme.Colors.textStrong)
                    .lineLimit(2)
            }
        }
        .padding(Theme.Space.md)
        .background(Theme.Colors.surface)
        .clipShape(RoundedRectangle(cornerRadius: Theme.Radius.md))
        .overlay(
            RoundedRectangle(cornerRadius: Theme.Radius.md)
                .stroke(Theme.Colors.stroke, lineWidth: Theme.Stroke.normal)
        )
        .hardShadow(
            RoundedRectangle(cornerRadius: Theme.Radius.md),
            offset: CGSize(width: 4, height: 5)
        )
    }
}
