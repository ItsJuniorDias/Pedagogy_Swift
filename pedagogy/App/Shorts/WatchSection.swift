//
//  WatchSection.swift
//  pedagogy
//
//  ─── WATCH (Home) ───────────────────────────────────────────────────────────
//  Seção dos curtas-metragens na Home. Some quando não há nenhum lançado.
//
//    ─── ● Watch ─────────────────
//    ┌─────────────────────────┐
//    │  pôster 16:9        ▶   │   ← anel de progresso aqui durante o download
//    └─────────────────────────┘
//    SHORT FILM · 5 MIN
//    The Paper Whale
//    When fog swallows the harbor…
//
//  Um curta: card na largura toda. Dois ou mais: carrossel horizontal com
//  o próximo card aparecendo na borda, pra ficar óbvio que rola.
//  ────────────────────────────────────────────────────────────────────────────

import SwiftUI
import UIKit

struct WatchSection: View {
    let shorts: [Short]
    let launcher: ShortLauncher
    let isLocked: (Short) -> Bool
    let onTap: (Short) -> Void

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Space.md) {
            HStack(spacing: Theme.Space.sm) {
                Circle()
                    .fill(Theme.Colors.primary)
                    .frame(width: 6, height: 6)
                Text("Watch")
                    .font(.ui(11, weight: .bold))
                    .kerning(1.2)
                    .foregroundStyle(Theme.Colors.textStrong)
                    .textCase(.uppercase)
            }

            if shorts.count == 1, let short = shorts.first {
                card(short)
            } else {
                ScrollView(.horizontal, showsIndicators: false) {
                    HStack(alignment: .top, spacing: Theme.Space.lg) {
                        ForEach(shorts) { short in
                            card(short).frame(width: 280)
                        }
                    }
                    // Espaço pra sombra hard não ser cortada pelo ScrollView.
                    .padding(.bottom, Theme.Space.xs)
                    .padding(.trailing, Theme.Space.xs)
                }
            }
        }
    }

    private func card(_ short: Short) -> some View {
        ShortCard(
            short: short,
            isLocked: isLocked(short),
            downloadFraction: launcher.downloading[short.id],
            failed: launcher.failedID == short.id,
            action: { onTap(short) }
        )
    }
}

// MARK: - Card

struct ShortCard: View {
    let short: Short
    let isLocked: Bool
    /// Presente = baixando.
    let downloadFraction: Double?
    let failed: Bool
    let action: () -> Void

    private var shape: RoundedRectangle {
        RoundedRectangle(cornerRadius: Theme.Radius.lg)
    }

    var body: some View {
        Button(action: action) {
            VStack(alignment: .leading, spacing: Theme.Space.sm) {
                poster
                    .aspectRatio(16 / 9, contentMode: .fit)
                    .clipShape(shape)
                    .overlay(shape.stroke(Theme.Colors.stroke, lineWidth: Theme.Stroke.normal))
                    .hardShadow(shape)
                    .padding(.bottom, Theme.Space.sm)

                HStack(spacing: Theme.Space.xs) {
                    if isLocked {
                        Image(systemName: "lock.fill")
                            .font(.system(size: 10, weight: .bold))
                    }
                    Text("Short film · \(short.durationLabel)")
                        .kerning(0.8)
                        .textCase(.uppercase)
                }
                .font(.ui(11, weight: .bold))
                .foregroundStyle(Theme.Colors.textMuted)

                Text(short.title)
                    .font(.display(20, weight: .bold))
                    .foregroundStyle(Theme.Colors.ink)

                Text(failed ? "Couldn't download the film. Tap to try again." : short.logline)
                    .font(.body(14, weight: .regular))
                    .foregroundStyle(failed ? Theme.Colors.danger : Theme.Colors.textMuted)
                    .lineLimit(3)
                    .lineSpacing(2)
                    .fixedSize(horizontal: false, vertical: true)
            }
            .frame(maxWidth: .infinity, alignment: .leading)
        }
        .buttonStyle(.plain)
        .accessibilityElement(children: .ignore)
        .accessibilityLabel("Short film: \(short.title), \(short.durationLabel)")
        .accessibilityValue(downloadFraction.map { "Downloading, \(Int($0 * 100)) percent" } ?? "")
        .accessibilityHint(downloadFraction != nil ? "Double tap to cancel" : isLocked ? "Requires a subscription" : "Plays the film")
        .accessibilityAddTraits(.isButton)
    }

    private var poster: some View {
        ZStack {
            Theme.Colors.bgSepia

            if let image = PosterCache.image(id: short.id) {
                Image(uiImage: image)
                    .resizable()
                    .scaledToFill()
            }

            if let fraction = downloadFraction {
                Theme.Colors.overlay
                DownloadRing(fraction: fraction)
            } else {
                PlayBadge()
            }
        }
    }
}

/// Botão de play: círculo creme com borda de tinta, no estilo dos chips.
private struct PlayBadge: View {
    var body: some View {
        Image(systemName: "play.fill")
            .font(.system(size: 20, weight: .bold))
            .foregroundStyle(Theme.Colors.ink)
            .offset(x: 2)  // o triângulo parece descentralizado sem isso
            .frame(width: 56, height: 56)
            .background(Circle().fill(Theme.Colors.bg))
            .overlay(Circle().stroke(Theme.Colors.stroke, lineWidth: Theme.Stroke.normal))
            .hardShadowSmall(Circle())
    }
}

/// Anel de download com um "×" no meio — tocar de novo cancela.
private struct DownloadRing: View {
    let fraction: Double

    var body: some View {
        ZStack {
            Circle()
                .stroke(Theme.Colors.onInk.opacity(0.25), lineWidth: 4)
            Circle()
                .trim(from: 0, to: max(0.03, fraction))
                .stroke(Theme.Colors.primary, style: StrokeStyle(lineWidth: 4, lineCap: .round))
                .rotationEffect(.degrees(-90))
                .animation(.linear(duration: 0.2), value: fraction)
            Image(systemName: "xmark")
                .font(.system(size: 14, weight: .bold))
                .foregroundStyle(Theme.Colors.onInk)
        }
        .frame(width: 52, height: 52)
    }
}

/// Pôster decodificado uma vez. Sem isso o JPEG seria lido do disco a cada
/// tick do anel de download, que re-renderiza o card várias vezes por segundo.
private enum PosterCache {
    private static var images: [String: UIImage] = [:]

    static func image(id: String) -> UIImage? {
        if let cached = images[id] { return cached }
        guard let url = ShortCatalog.posterURL(id: id),
              let image = UIImage(contentsOfFile: url.path) else { return nil }
        images[id] = image
        return image
    }
}
