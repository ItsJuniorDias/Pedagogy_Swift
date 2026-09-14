//
//  AchievementCard.swift
//  pedagogy
//
//  ─── ACHIEVEMENT CARD v2 ────────────────────────────────────────────────────
//  Card do grid do ProfileView. Layout: ilustração quadrada no topo,
//  título + estado abaixo. 3 estados visuais:
//
//    1. LOCKED
//       — imagem em grayscale + opacity reduzida
//       — título e requirement muted
//       — sem pink dot
//       — se tem progress (ex: 6/10), mostra o par
//
//    2. UNLOCKED
//       — imagem colorida cheia (pink accent do prompt visível)
//       — pink dot no canto superior direito
//       — data em small caps ("SEP 12")
//       — stroke mais grosso, sombra hard mais deslocada
//
//    3. IMAGEM AUSENTE (fallback)
//       — o app roda antes das artes serem geradas
//       — mostra retângulo bg com título grande centrado
//       — mesma paleta cream + stroke Mignola
//       — degrada graciosamente sem crash
//
//  ILUSTRAÇÕES
//
//  Geradas por scripts/generate_achievements.py (12 imagens ~$0.17 total).
//  Nome do imageset: achievement-<kebab-id>-icon.imageset — bate com
//  AchievementID.iconAssetName no model.
//
//  Se você adicionar achievement novo no enum, roda o script pra gerar
//  a arte correspondente. Sem arte gerada, o card mostra o fallback
//  tipográfico automaticamente.
//  ────────────────────────────────────────────────────────────────────────────

import SwiftUI

struct AchievementCard: View {
    let achievement: Achievement
    let unlockedAt: Date?
    let progress: (Int, Int)?
    /// Chamado quando o usuário toca no card. Padrão: exibir o
    /// AchievementDetailSheet. Ficar externo mantém o card puramente
    /// visual e permite reuso em contextos que não sejam ProfileView
    /// (ex: preview num toast de unlock).
    let onTap: () -> Void

    private var isUnlocked: Bool { unlockedAt != nil }
    private var iconExists: Bool {
        UIImage(named: achievement.id.iconAssetName) != nil
    }

    var body: some View {
        PressBounce(scaleTo: 0.94, action: onTap) {
            cardContent
        }
        // Accessibility: PressBounce já envolve num Button, então o hint
        // aqui completa o label com o estado.
        .accessibilityHint("Double tap for details")
    }

    // MARK: - Card body (extracted so PressBounce wraps only the visual)

    private var cardContent: some View {
        VStack(spacing: 0) {
            // ─── Top: ilustração quadrada + pink dot overlay ───────
            ZStack(alignment: .topTrailing) {
                Group {
                    if iconExists {
                        Image(achievement.id.iconAssetName)
                            .resizable()
                            .aspectRatio(1, contentMode: .fill)
                            .grayscale(isUnlocked ? 0 : 1)
                            .opacity(isUnlocked ? 1 : 0.35)
                    } else {
                        FallbackIcon(title: achievement.title, isUnlocked: isUnlocked)
                    }
                }
                .clipped()

                if isUnlocked {
                    Circle()
                        .fill(Theme.Colors.primary)
                        .frame(width: 14, height: 14)
                        .overlay(
                            Circle().stroke(Theme.Colors.stroke, lineWidth: 1.5)
                        )
                        .padding(Theme.Space.sm)
                }
            }
            .frame(maxWidth: .infinity)
            .aspectRatio(1, contentMode: .fit)

            // Hairline separator entre ilustração e texto
            Rectangle()
                .fill(Theme.Colors.border)
                .frame(height: 1)

            // ─── Bottom: texto ─────────────────────────────────────
            VStack(alignment: .leading, spacing: 4) {
                Text(achievement.title)
                    .font(.display(14, weight: .bold))
                    .foregroundStyle(isUnlocked ? Theme.Colors.ink : Theme.Colors.textMuted.opacity(0.7))
                    .lineLimit(2)
                    .fixedSize(horizontal: false, vertical: true)
                    .frame(maxWidth: .infinity, alignment: .leading)

                if isUnlocked, let date = unlockedAt {
                    Text(unlockDateLabel(date))
                        .font(.ui(9, weight: .bold))
                        .tracking(1.2)
                        .foregroundStyle(Theme.Colors.primary)
                } else if let (current, target) = progress, current > 0 {
                    Text("\(current) of \(target)")
                        .font(.ui(9, weight: .bold))
                        .tracking(0.8)
                        .foregroundStyle(Theme.Colors.textMuted)
                } else {
                    Text(achievement.requirement)
                        .font(.ui(9, weight: .regular))
                        .foregroundStyle(Theme.Colors.textMuted)
                        .lineLimit(2)
                        .fixedSize(horizontal: false, vertical: true)
                        .frame(maxWidth: .infinity, alignment: .leading)
                }
            }
            .padding(.horizontal, Theme.Space.sm)
            .padding(.vertical, Theme.Space.sm)
            .frame(maxWidth: .infinity, minHeight: 56, alignment: .topLeading)
        }
        .background(Theme.Colors.surface)
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
            offset: isUnlocked ? CGSize(width: 3, height: 4) : CGSize(width: 1, height: 2)
        )
        .accessibilityElement(children: .combine)
        .accessibilityLabel(accessibilityLabel)
    }

    // MARK: - Helpers

    private func unlockDateLabel(_ date: Date) -> String {
        let formatter = DateFormatter()
        formatter.dateFormat = "MMM d"
        return formatter.string(from: date).uppercased()
    }

    private var accessibilityLabel: String {
        if isUnlocked, let date = unlockedAt {
            let f = DateFormatter()
            f.dateStyle = .medium
            return "\(achievement.title). Unlocked \(f.string(from: date))."
        }
        var base = "\(achievement.title). Locked. \(achievement.requirement)."
        if let (current, target) = progress, current > 0 {
            base += " Progress: \(current) of \(target)."
        }
        return base
    }
}

// MARK: - Fallback Icon

/// Mostrado quando a ilustração ainda não foi gerada. Não é placeholder feio
/// tipo box com "?" — é uma composição tipográfica limpa com o título do
/// achievement. Assim o app roda perfeitamente antes de você rodar o script
/// de geração de artes, e um developer novo pega uma versão utilizável na
/// primeira compilação.
private struct FallbackIcon: View {
    let title: String
    let isUnlocked: Bool

    var body: some View {
        ZStack {
            Theme.Colors.bgSepia
            Text(title)
                .font(.display(14, weight: .bold))
                .foregroundStyle(isUnlocked ? Theme.Colors.ink : Theme.Colors.textMuted)
                .multilineTextAlignment(.center)
                .padding(Theme.Space.sm)
        }
        .grayscale(isUnlocked ? 0 : 1)
        .opacity(isUnlocked ? 1 : 0.6)
    }
}
