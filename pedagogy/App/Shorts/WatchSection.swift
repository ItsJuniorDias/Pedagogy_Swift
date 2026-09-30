//
//  WatchSection.swift
//  pedagogy
//
//  ─── WATCH (Home) ───────────────────────────────────────────────────────────
//  Seção de filmes na Home, uma fileira por origem (originais, abertos da
//  Blender, clássicos). Some quando não há nenhum lançado.
//
//  A Home usa duas: "Pedagogy Originals" (só os originais, a primeira seção
//  da tela) e "Watch" (abertos e clássicos, mais abaixo). O título vem de
//  quem chama; as fileiras saem dos filmes que cada uma recebe.
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
//
//  Filme premium no trio grátis da semana (`Short.freeThisWeek`) ganha o
//  selo "Free this week" no pôster; os outros premium mostram o cadeado.
//  ────────────────────────────────────────────────────────────────────────────

import SwiftUI
import UIKit

struct WatchSection: View {
    let title: LocalizedStringKey
    let shorts: [Short]
    let launcher: ShortLauncher
    let isLocked: (Short) -> Bool
    let onTap: (Short) -> Void
    /// Premium liberado pelo rodízio da semana (selo "Free this week").
    var isFreeThisWeek: (Short) -> Bool = { _ in false }

    /// Uma fileira por origem, na ordem: originais, abertos, clássicos.
    /// Fileira vazia não aparece.
    private var rows: [Row] {
        [Short.Kind.original, .open, .classic].compactMap { kind in
            let items = shorts.filter { $0.resolvedKind == kind }
            return items.isEmpty ? nil : Row(kind: kind, shorts: items)
        }
    }

    private struct Row: Identifiable {
        let kind: Short.Kind
        let shorts: [Short]
        var id: Short.Kind { kind }
    }

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Space.xl) {
            HStack(spacing: Theme.Space.sm) {
                Circle()
                    .fill(Theme.Colors.primary)
                    .frame(width: 6, height: 6)
                Text(title)
                    .font(.ui(11, weight: .bold))
                    .kerning(1.2)
                    .foregroundStyle(Theme.Colors.textStrong)
                    .textCase(.uppercase)
            }

            ForEach(rows) { row in
                VStack(alignment: .leading, spacing: Theme.Space.md) {
                    // Com uma fileira só, o título da seção já diz tudo.
                    if rows.count > 1 {
                        Text(row.kind.rowTitle)
                            .font(.display(17, weight: .bold))
                            .foregroundStyle(Theme.Colors.ink)
                    }
                    if row.shorts.count == 1, let short = row.shorts.first {
                        card(short)
                    } else {
                        // Mesmo padrão do FeaturedPicks: o carrossel vaza até a
                        // borda da tela (padding negativo) e devolve a margem
                        // por dentro, senão os cards cortam no meio da margem.
                        // O respiro em cima e embaixo é pra borda de 2pt e a
                        // sombra hard não serem cortadas pelo ScrollView.
                        ScrollView(.horizontal, showsIndicators: false) {
                            HStack(alignment: .top, spacing: Theme.Space.lg) {
                                ForEach(row.shorts) { short in
                                    card(short).frame(width: 280)
                                }
                            }
                            .padding(.horizontal, Theme.Space.lg)
                            .padding(.top, Theme.Stroke.normal)
                            .padding(.bottom, Theme.Space.xs)
                        }
                        .padding(.horizontal, -Theme.Space.lg)
                    }
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
            action: { onTap(short) },
            isFreeThisWeek: isFreeThisWeek(short)
        )
    }
}

extension WatchSection {
    /// Falha de download acontece sem toque nenhum (o download roda sozinho),
    /// então quem usa VoiceOver precisa ouvir — só mudar o texto do card não
    /// chega até ele.
    func announcesFailures() -> some View {
        onChange(of: launcher.failedID) { _, id in
            guard let id, let short = shorts.first(where: { $0.id == id }) else { return }
            AccessibilityNotification.Announcement("Couldn't open \(short.title). Tap the card to try again.").post()
        }
    }
}

private extension Short.Kind {
    var rowTitle: String {
        switch self {
        case .original: return "Pedagogy Originals"
        case .open:     return "Animated shorts"
        case .classic:  return "Classic cartoons"
        }
    }
}

extension Short {
    /// "Short film · 5 min", "Animated short · 2019 · 8 min", "Classic · 1941 · 9 min"
    var kindLabel: String {
        let prefix: String
        switch resolvedKind {
        case .original: prefix = "Short film"
        case .open:     prefix = "Animated short"
        case .classic:  prefix = "Classic"
        }
        return ([prefix] + (year.map { ["\($0)"] } ?? []) + [durationLabel]).joined(separator: " · ")
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
    /// Premium que está no trio grátis da semana: selo no pôster.
    var isFreeThisWeek = false

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
                    Text(short.kindLabel)
                        .kerning(0.8)
                        .textCase(.uppercase)
                }
                .font(.ui(11, weight: .bold))
                .foregroundStyle(Theme.Colors.textMuted)

                Text(short.title)
                    .font(.display(20, weight: .bold))
                    .foregroundStyle(Theme.Colors.ink)

                Text(failed ? "Couldn't open the film. Tap to try again." : short.logline)
                    .font(.body(14, weight: .regular))
                    .foregroundStyle(failed ? Theme.Colors.danger : Theme.Colors.textMuted)
                    .lineLimit(3)
                    .lineSpacing(2)
                    .fixedSize(horizontal: false, vertical: true)

                // Crédito visível: exigência da CC BY, e justo com o
                // domínio público também.
                if let attribution = short.attribution {
                    Text(attribution)
                        .font(.ui(11, weight: .medium))
                        .foregroundStyle(Theme.Colors.textFaint)
                        .lineLimit(2)
                }
            }
            .frame(maxWidth: .infinity, alignment: .leading)
        }
        .buttonStyle(.plain)
        .accessibilityElement(children: .ignore)
        .accessibilityLabel(accessibilityLabel)
        .accessibilityValue(accessibilityValue)
        .accessibilityHint(accessibilityHint)
        .accessibilityAddTraits(.isButton)
    }

    // O card ignora os filhos (é um botão só), então tudo que está escrito
    // nele precisa estar aqui: cadeado, sinopse e o crédito da licença.
    private var accessibilityLabel: String {
        var parts = ["\(short.kindLabel): \(short.title)"]
        if isLocked { parts.append("Locked") }
        if isFreeThisWeek { parts.append("Free this week") }
        parts.append(short.logline)
        if let attribution = short.attribution { parts.append(attribution) }
        return parts.joined(separator: ". ")
    }

    private var accessibilityValue: String {
        if let fraction = downloadFraction { return "Downloading, \(Int(fraction * 100)) percent" }
        return failed ? "Couldn't open the film" : ""
    }

    private var accessibilityHint: String {
        if downloadFraction != nil { return "Double tap to cancel" }
        if failed { return "Double tap to try again" }
        return isLocked ? "Requires a subscription" : "Plays the film"
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
        .overlay(alignment: .topLeading) {
            if isFreeThisWeek {
                FreeThisWeekBadge()
                    .padding(Theme.Space.md)
            }
        }
    }
}

/// Selo do trio grátis da semana: pílula rosa com borda de tinta, no estilo
/// dos botões do app. Já é anunciado no label do card.
private struct FreeThisWeekBadge: View {
    var body: some View {
        Text("Free this week")
            .font(.ui(10, weight: .bold))
            .tracking(0.8)
            .textCase(.uppercase)
            .foregroundStyle(Theme.Colors.onAccent)
            .padding(.horizontal, Theme.Space.sm)
            .padding(.vertical, 4)
            .background(Capsule().fill(Theme.Colors.primary))
            .overlay(Capsule().stroke(Theme.Colors.stroke, lineWidth: Theme.Stroke.normal))
            .accessibilityHidden(true)
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
