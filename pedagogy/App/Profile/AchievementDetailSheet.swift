//
//  AchievementDetailSheet.swift
//  pedagogy
//
//  ─── ACHIEVEMENT DETAIL SHEET ───────────────────────────────────────────────
//  Modal apresentado quando o usuário toca num AchievementCard no ProfileView.
//
//  CONTEÚDO
//
//    • Close button (×) no canto superior direito
//    • Ilustração grande e centralizada (mesma que aparece no card)
//    • Título display grande
//    • Divider hairline
//    • Descrição (o requirement, prosa completa)
//    • Estado corrente:
//        - Unlocked: "UNLOCKED SEP 3" em pink small caps
//        - Locked com progress: "IN PROGRESS · 3 OF 5" muted
//        - Locked sem progress: "NOT YET" muted
//
//  APRESENTAÇÃO
//
//  Bottom sheet com detent `.medium`. Menos intrusivo que fullscreen —
//  o usuário pode dismissar arrastando pra baixo ou tocando fora. Se
//  quiser inspecionar mais devagar, pode arrastar pra `.large`.
//
//  DESIGN DECISIONS
//
//  • Sem CTA "compartilhar" ou "definir como próximo objetivo". O modal é
//    puramente informativo — vem do tom quiet-editorial do app. Se
//    aparecerem features sociais no futuro (share quote, etc), aí sim.
//  • Ilustração ocupa ~40% da altura do sheet. É o herói visual.
//  • Locked state tem a mesma ilustração em grayscale + opacity — coerente
//    com o card. Não escondemos ou trocamos por placeholder.
//  ────────────────────────────────────────────────────────────────────────────

import SwiftUI

struct AchievementDetailSheet: View {
    let achievement: Achievement
    let unlockedAt: Date?
    let progress: (Int, Int)?
    let onClose: () -> Void

    private var isUnlocked: Bool { unlockedAt != nil }
    private var iconExists: Bool {
        UIImage(named: achievement.id.iconAssetName) != nil
    }

    var body: some View {
        VStack(spacing: 0) {
            // ─── Header: close button ──────────────────────────────
            HStack {
                Spacer()
                Button(action: onClose) {
                    Image(systemName: "xmark")
                        .font(.system(size: 14, weight: .bold))
                        .foregroundStyle(Theme.Colors.textStrong)
                        .frame(width: 32, height: 32)
                        .background(
                            Circle()
                                .fill(Theme.Colors.surface)
                                .overlay(
                                    Circle().stroke(Theme.Colors.stroke, lineWidth: Theme.Stroke.normal)
                                )
                        )
                        .hardShadow(Circle(), offset: CGSize(width: 2, height: 3))
                }
                .accessibilityLabel("Close")
            }
            .padding(.horizontal, Theme.Space.lg)
            .padding(.top, Theme.Space.md)

            Spacer(minLength: 0)

            // ─── Illustration ──────────────────────────────────────
            Group {
                if iconExists {
                    Image(achievement.id.iconAssetName)
                        .resizable()
                        .aspectRatio(1, contentMode: .fit)
                        .grayscale(isUnlocked ? 0 : 1)
                        .opacity(isUnlocked ? 1 : 0.35)
                } else {
                    // Fallback tipográfico — mesmo tratamento do card.
                    // O app roda antes das artes serem geradas.
                    ZStack {
                        Theme.Colors.bgSepia
                        Text(achievement.title)
                            .font(.display(28, weight: .bold))
                            .foregroundStyle(isUnlocked ? Theme.Colors.ink : Theme.Colors.textMuted)
                            .multilineTextAlignment(.center)
                            .padding(Theme.Space.xl)
                    }
                    .aspectRatio(1, contentMode: .fit)
                    .clipShape(RoundedRectangle(cornerRadius: Theme.Radius.md))
                }
            }
            .frame(maxWidth: 260)
            .clipShape(RoundedRectangle(cornerRadius: Theme.Radius.md))
            .overlay(
                RoundedRectangle(cornerRadius: Theme.Radius.md)
                    .stroke(
                        isUnlocked ? Theme.Colors.stroke : Theme.Colors.border,
                        lineWidth: isUnlocked ? Theme.Stroke.thick : Theme.Stroke.normal
                    )
            )
            .hardShadow(
                RoundedRectangle(cornerRadius: Theme.Radius.md),
                offset: isUnlocked ? CGSize(width: 5, height: 6) : CGSize(width: 2, height: 3)
            )
            .padding(.horizontal, Theme.Space.xxl)

            Spacer(minLength: Theme.Space.xl)

            // ─── Título ────────────────────────────────────────────
            Text(achievement.title)
                .displayTitle(size: 28)
                .foregroundStyle(isUnlocked ? Theme.Colors.ink : Theme.Colors.textStrong)
                .multilineTextAlignment(.center)
                .padding(.horizontal, Theme.Space.xl)

            // Hairline
            Rectangle()
                .fill(Theme.Colors.border)
                .frame(width: 40, height: 1)
                .padding(.vertical, Theme.Space.md)

            // ─── Descrição ─────────────────────────────────────────
            Text(achievement.requirement)
                .font(.body(15, weight: .regular))
                .foregroundStyle(Theme.Colors.textStrong)
                .multilineTextAlignment(.center)
                .padding(.horizontal, Theme.Space.xxl)
                .fixedSize(horizontal: false, vertical: true)

            // ─── Estado ────────────────────────────────────────────
            StateLabel(
                isUnlocked: isUnlocked,
                unlockedAt: unlockedAt,
                progress: progress
            )
            .padding(.top, Theme.Space.lg)

            Spacer(minLength: Theme.Space.xxxl)
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .background(Theme.Colors.bg.ignoresSafeArea())
        .presentationDetents([.medium, .large])
        .presentationDragIndicator(.visible)
        .presentationBackground(Theme.Colors.bg)
    }
}

// MARK: - StateLabel

/// Pequeno label na parte inferior mostrando estado do achievement. 3
/// variantes visuais dependendo do estado:
///   • Unlocked: pink text
///   • Locked com progress: muted + números
///   • Locked sem progress: muted + "not yet"
private struct StateLabel: View {
    let isUnlocked: Bool
    let unlockedAt: Date?
    let progress: (Int, Int)?

    var body: some View {
        if isUnlocked, let date = unlockedAt {
            HStack(spacing: Theme.Space.xs) {
                Circle()
                    .fill(Theme.Colors.primary)
                    .frame(width: 8, height: 8)
                Text("UNLOCKED \(dateLabel(date))")
                    .font(.ui(12, weight: .bold))
                    .tracking(1.5)
                    .foregroundStyle(Theme.Colors.primary)
            }
        } else if let (current, target) = progress, current > 0 {
            Text("IN PROGRESS · \(current) OF \(target)")
                .font(.ui(12, weight: .bold))
                .tracking(1.5)
                .foregroundStyle(Theme.Colors.textMuted)
        } else {
            Text("NOT YET")
                .font(.ui(12, weight: .bold))
                .tracking(1.5)
                .foregroundStyle(Theme.Colors.textMuted)
        }
    }

    private func dateLabel(_ date: Date) -> String {
        let f = DateFormatter()
        f.dateFormat = "MMM d, yyyy"
        return f.string(from: date).uppercased()
    }
}

#Preview("Unlocked") {
    AchievementDetailSheet(
        achievement: Achievement.all.first { $0.id == .firstSentence }!,
        unlockedAt: Date(),
        progress: nil,
        onClose: {}
    )
}

#Preview("Locked with progress") {
    AchievementDetailSheet(
        achievement: Achievement.all.first { $0.id == .fiveStories }!,
        unlockedAt: nil,
        progress: (2, 5),
        onClose: {}
    )
}

#Preview("Locked no progress") {
    AchievementDetailSheet(
        achievement: Achievement.all.first { $0.id == .aHundredDays }!,
        unlockedAt: nil,
        progress: (0, 100),
        onClose: {}
    )
}
