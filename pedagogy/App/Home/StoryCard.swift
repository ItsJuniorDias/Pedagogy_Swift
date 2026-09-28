//
//  StoryCard.swift
//  pedagogy
//
//  ─── STORY CARDS ────────────────────────────────────────────────────────────
//  Dois cards, mesmo dado (Story + StoryProgress). Structs separados em vez
//  de um StoryCard com `style` — as duas variantes têm layouts internos
//  fundamentalmente diferentes (vertical vs horizontal, com/sem CTA
//  embutido, com/sem barra de progresso separada). Um enum de estilo
//  esconderia isso atrás de dezenas de `if style == .hero`.
//
//  StoryHeroCard   → featured hero da Home. Grande, cover 5:4 no topo,
//                    fundo rosa faint sutil, CTA rosa embutido.
//  StoryCompactCard → cards do library grid. Layout horizontal: thumbnail
//                     3:2 à esquerda (~120pt largura), meta + título à
//                     direita. Cabem 4-5 na dobra.
//
//  CATEGORY BADGE (v2.1)
//
//  Antes: chip colorido com a cor do theme da história (roxo, amarelo, etc).
//  Agora: chip preto sobre creme, sempre. Uma cor só, sem competir com a
//  cover art. Fica no canto superior esquerdo da imagem em ambas variantes.
//
//  COVER PLACEHOLDER
//
//  Quando a arte não está no bundle, mostra placeholder com fundo sépia e
//  ícone de livro. Antes usava a cor do theme da história — agora não
//  existe theme, então neutro pra todos. O placeholder é temporário até a
//  arte ser gerada; não vale investir em variação.
//  ────────────────────────────────────────────────────────────────────────────

import SwiftUI

// ═══════════════════════════════════════════════════════════════════════════
// MARK: - Hero Card (Featured)
// ═══════════════════════════════════════════════════════════════════════════

/// Card grande do featured hero da Home. Um por tela, no topo.
struct StoryHeroCard: View {
    let story: Story
    let progress: StoryProgress

    @Environment(TranslationStore.self) private var translation

    private var progressFraction: Double {
        if progress.isFinished { return 1 }
        guard !story.chapters.isEmpty else { return 0 }
        return min(1, Double(progress.chapterIndex) / Double(story.chapters.count))
    }

    private var ctaLabel: String {
        if progress.isFinished { return "Read again" }
        if progress.isInProgress { return "Continue" }
        return "Start reading"
    }

    /// Label pequeno acima do título — "CONTINUE READING", "FEATURED",
    /// "FINISHED". Comunica o CONTEXTO de por que esta história está aqui.
    private var eyebrow: String {
        if progress.isFinished { return "READ AGAIN" }
        if progress.isInProgress { return "CONTINUE READING" }
        return "START HERE"
    }

    var body: some View {
        VStack(spacing: 0) {
            // ─── COVER (5:4) ──────────────────────────────────────────
            CoverImageSlot(story: story, showsBadge: true, motion: true)

            // ─── DIVIDER hairline preta ───────────────────────────────
            Rectangle()
                .fill(Theme.Colors.stroke)
                .frame(height: Theme.Stroke.normal)

            // ─── TEXT + CTA ───────────────────────────────────────────
            VStack(alignment: .leading, spacing: Theme.Space.sm) {
                // Eyebrow — contextualiza por que esta história é a
                // featured (continuando, começando, terminou)
                Text(eyebrow)
                    .font(.ui(11, weight: .bold))
                    .tracking(1.2)
                    .foregroundStyle(Theme.Colors.primary)

                // Título — display serif grande
                Text(translation.text(story.title))
                    .displayTitle(size: 26)
                    .multilineTextAlignment(.leading)
                    .fixedSize(horizontal: false, vertical: true)

                // Meta line (compacta)
                HStack(spacing: Theme.Space.xs) {
                    Text("\(story.readingTimeMinutes) min")
                    Text("·")
                    Text("\(story.chapters.count) chapters")
                    if progress.isFinished {
                        Text("·")
                        Image(systemName: "checkmark")
                            .font(.system(size: 10, weight: .bold))
                    }
                }
                .font(.ui(12, weight: .medium))
                .foregroundStyle(Theme.Colors.textMuted)

                // Barra de progresso (só quando em andamento)
                if progress.isInProgress {
                    ProgressBar(fraction: progressFraction)
                        .frame(height: 4)
                        .padding(.top, Theme.Space.xs)
                }

                // CTA embutido — botão rosa cheio
                CTAButton(label: ctaLabel)
                    .padding(.top, Theme.Space.md)
            }
            .padding(Theme.Space.xl)
            .frame(maxWidth: .infinity, alignment: .leading)
            .background(Theme.Colors.primaryFaint)  // rosa MUITO sutil
        }
        .clipShape(RoundedRectangle(cornerRadius: Theme.Radius.lg))
        .overlay(
            RoundedRectangle(cornerRadius: Theme.Radius.lg)
                .stroke(Theme.Colors.stroke, lineWidth: Theme.Stroke.thick)
        )
        .hardShadow(
            RoundedRectangle(cornerRadius: Theme.Radius.lg),
            offset: CGSize(width: 5, height: 6)
        )
        .accessibilityElement(children: .combine)
        .accessibilityLabel(accessibilityLabel)
        .accessibilityHint("Double tap to \(ctaLabel.lowercased())")
    }

    private var accessibilityLabel: String {
        var parts = ["Featured story", translation.text(story.title)]
        if let sub = translation.text(story.subtitle) { parts.append(sub) }
        parts.append("\(story.readingTimeMinutes) minutes, \(story.chapters.count) chapters")
        if progress.isFinished { parts.append("finished") }
        else if progress.isInProgress {
            parts.append("in progress, \(Int(progressFraction * 100)) percent read")
        }
        return parts.joined(separator: ", ")
    }
}

// ═══════════════════════════════════════════════════════════════════════════
// MARK: - Compact Card (Library)
// ═══════════════════════════════════════════════════════════════════════════

/// Card compacto pra library. Layout horizontal: thumbnail à esquerda,
/// meta+título à direita. Sem CTA embutido — o card inteiro é o tap target.
struct StoryCompactCard: View {
    let story: Story
    let progress: StoryProgress

    @Environment(TranslationStore.self) private var translation

    private var progressFraction: Double {
        if progress.isFinished { return 1 }
        guard !story.chapters.isEmpty else { return 0 }
        return min(1, Double(progress.chapterIndex) / Double(story.chapters.count))
    }

    var body: some View {
        HStack(spacing: Theme.Space.md) {
            // ─── THUMBNAIL 5:4 ───────────────────────────────────────
            CoverImageSlot(story: story, showsBadge: false)
                .frame(width: 120)
                .clipShape(RoundedRectangle(cornerRadius: Theme.Radius.sm))
                .overlay(
                    RoundedRectangle(cornerRadius: Theme.Radius.sm)
                        .stroke(Theme.Colors.stroke, lineWidth: Theme.Stroke.thin)
                )

            // ─── INFO ────────────────────────────────────────────────
            VStack(alignment: .leading, spacing: Theme.Space.xs) {
                // Category badge (preto pequeno)
                CategoryBadge(category: story.category)

                // Título — 2 linhas max
                Text(translation.text(story.title))
                    .font(.display(17, weight: .bold))
                    .foregroundStyle(Theme.Colors.ink)
                    .lineLimit(2)
                    .multilineTextAlignment(.leading)
                    .fixedSize(horizontal: false, vertical: true)

                // Meta line
                HStack(spacing: Theme.Space.xs) {
                    Text("\(story.readingTimeMinutes) min")
                    Text("·")
                    Text("\(story.chapters.count) ch")
                    if progress.isFinished {
                        Text("·")
                        Image(systemName: "checkmark")
                            .font(.system(size: 9, weight: .bold))
                    } else if progress.isInProgress {
                        Text("·")
                        Text("\(Int(progressFraction * 100))%")
                    }
                }
                .font(.ui(11, weight: .medium))
                .foregroundStyle(Theme.Colors.textMuted)

                Spacer(minLength: 0)
            }

            Spacer(minLength: 0)

            // ─── CHEVRON (afordância "abre algo") ───────────────────
            Image(systemName: "chevron.right")
                .font(.system(size: 12, weight: .semibold))
                .foregroundStyle(Theme.Colors.textFaint)
        }
        .padding(Theme.Space.md)
        .background(Theme.Colors.surface)
        .clipShape(RoundedRectangle(cornerRadius: Theme.Radius.md))
        .overlay(
            RoundedRectangle(cornerRadius: Theme.Radius.md)
                .stroke(Theme.Colors.border, lineWidth: Theme.Stroke.hair)
        )
        .accessibilityElement(children: .combine)
        .accessibilityLabel(accessibilityLabel)
        .accessibilityHint("Double tap to open")
    }

    private var accessibilityLabel: String {
        var parts = [story.category.badgeName.lowercased().capitalized, translation.text(story.title)]
        parts.append("\(story.readingTimeMinutes) minutes, \(story.chapters.count) chapters")
        if progress.isFinished { parts.append("finished") }
        else if progress.isInProgress {
            parts.append("\(Int(progressFraction * 100)) percent read")
        }
        return parts.joined(separator: ", ")
    }
}

// ═══════════════════════════════════════════════════════════════════════════
// ═══════════════════════════════════════════════════════════════════════════
// MARK: - Thumb Card (Library grid)
// ═══════════════════════════════════════════════════════════════════════════

/// Card compacto pra grid 2-col da Library. Layout vertical (cover em cima,
/// meta embaixo), aspect 5:4 da cover mantido. Sem CTA, sem barra de
/// progresso — tap abre StoryDetail que tem tudo.
///
/// TAMANHO
///
/// Otimizado pra grid 2-col em iPhone (~155pt de largura cada card).
/// Cover ocupa quase toda a área do card, título + categoria abaixo em
/// 2 linhas fixas pra alinhar horizontalmente entre cards.
///
/// PROGRESSO
///
/// Indicado sutil: se a história está completa, checkmark discreto sobre a
/// cover; se está em progresso, ponto rosa. Não usa barra de progresso
/// (economiza altura vertical no grid denso).
struct StoryThumbCard: View {
    let story: Story
    let progress: StoryProgress

    @Environment(TranslationStore.self) private var translation

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Space.sm) {
            // Cover com badge de categoria + indicador de progresso opcional
            ZStack(alignment: .topLeading) {
                CoverImageSlot(story: story, showsBadge: true)

                // Indicador de progresso — canto superior direito
                if progress.isFinished || progress.isInProgress {
                    ProgressIndicator(isCompleted: progress.isFinished)
                        .padding(Theme.Space.sm)
                        .frame(maxWidth: .infinity, alignment: .trailing)
                }
            }
            .clipShape(RoundedRectangle(cornerRadius: Theme.Radius.md))
            .overlay(
                RoundedRectangle(cornerRadius: Theme.Radius.md)
                    .stroke(Theme.Colors.stroke, lineWidth: Theme.Stroke.thin)
            )

            // Título (max 2 linhas — fixo pra grid alinhar)
            Text(translation.text(story.title))
                .font(.display(15, weight: .semibold))
                .foregroundStyle(Theme.Colors.ink)
                .lineLimit(2)
                .multilineTextAlignment(.leading)
                .frame(maxWidth: .infinity, alignment: .leading)
                // fixedSize garante que 2 linhas sempre ocupam mesmo espaço,
                // mesmo se título for curto — grid fica alinhado
                .frame(height: 40, alignment: .top)

            // Meta: tempo de leitura
            Text("\(story.readingTimeMinutes) min")
                .font(.ui(11, weight: .medium))
                .foregroundStyle(Theme.Colors.textMuted)
        }
        .accessibilityElement(children: .combine)
        .accessibilityLabel("\(translation.text(story.title)). \(story.category.displayName). \(story.readingTimeMinutes) minutes.\(progress.isFinished ? " Completed." : progress.isInProgress ? " In progress." : "")")
    }
}

/// Indicador compacto de progresso no canto do thumb.
/// - Completo: círculo preto com checkmark branco
/// - Em progresso: ponto rosa pequeno
private struct ProgressIndicator: View {
    let isCompleted: Bool

    var body: some View {
        Group {
            if isCompleted {
                Image(systemName: "checkmark")
                    .font(.system(size: 10, weight: .heavy))
                    .foregroundStyle(Theme.Colors.onInk)
                    .frame(width: 20, height: 20)
                    .background(
                        Circle().fill(Theme.Colors.ink)
                    )
                    .overlay(
                        Circle().stroke(Theme.Colors.bg, lineWidth: 1.5)
                    )
            } else {
                Circle()
                    .fill(Theme.Colors.primary)
                    .frame(width: 10, height: 10)
                    .overlay(
                        Circle().stroke(Theme.Colors.bg, lineWidth: 1.5)
                    )
            }
        }
    }
}

// ═══════════════════════════════════════════════════════════════════════════
// MARK: - Shared Sub-components
// ═══════════════════════════════════════════════════════════════════════════

/// Slot da cover (5:4). Compartilhado entre hero e compact — só o tamanho
/// muda via `.frame()` externo. Badge é opcional (compact card não mostra
/// no thumbnail pequeno pra não poluir).
private struct CoverImageSlot: View {
    let story: Story
    let showsBadge: Bool

    /// Liga o vídeo em loop sobre a capa. Só o hero usa: nos cards compactos
    /// e nos thumbs da grade seriam vários AVPlayerLayer decodificando dentro
    /// de um ScrollView, e o efeito nem se lê num card de 160pt.
    var motion: Bool = false

    var body: some View {
        ZStack(alignment: .topLeading) {
            // Fundo sépia neutro — mesmo tratamento pra toda história.
            // Placeholder e "baseline" caso imagem tenha borda irregular.
            Theme.Colors.bgSepia

            if let imageName = story.coverImage, UIImage(named: imageName) != nil {
                MotionCover(story: story, imageName: imageName, motionEnabled: motion)
            } else {
                placeholder
            }

            if showsBadge {
                CategoryBadge(category: story.category)
                    .padding(Theme.Space.md)
            }

            // Lock badge — canto superior direito quando a história é
            // premium E não está na janela de "story of the week" grátis.
            // Escurece levemente a cover com overlay pra destacar que
            // está gated sem esconder a arte.
            if !story.isFreeToRead() {
                LockedOverlay()
            }
        }
        .aspectRatio(5/4, contentMode: .fit)
        .clipped()
    }

    private var placeholder: some View {
        ZStack {
            Grain(opacity: 0.06, color: Theme.Colors.textMuted)

            VStack(spacing: Theme.Space.xs) {
                Image(systemName: "book.closed.fill")
                    .font(.system(size: 40, weight: .light))
                    .foregroundStyle(Theme.Colors.textMuted.opacity(0.5))

                if let imageName = story.coverImage {
                    Text(imageName)
                        .font(.ui(9, weight: .semibold))
                        .foregroundStyle(Theme.Colors.textMuted.opacity(0.7))
                        .lineLimit(1)
                        .truncationMode(.middle)
                        .padding(.horizontal, 4)
                }
            }
        }
    }
}

// MARK: - Locked Overlay

/// Tratamento visual pra histórias bloqueadas (premium fora da janela
/// semanal grátis). Duas camadas:
///
///   1. Overlay preto semi-transparente (opacity 0.35) na cover inteira —
///      dessatura sem esconder a arte. Sinaliza "não é grátis" mesmo com
///      cover thumbnail bem pequena.
///
///   2. Cadeado em círculo preto no canto superior direito. Só o ícone,
///      sem label "PREMIUM" — o overlay dessaturado já comunica o gate,
///      e o texto poluía visualmente sobre a cover art.
///
/// Usada dentro do CoverImageSlot — aparece automaticamente sempre que
/// `story.isFreeToRead() == false`. Não precisa ser passada manualmente.
private struct LockedOverlay: View {
    var body: some View {
        ZStack(alignment: .topTrailing) {
            // Overlay dessaturado — sinal ambiente de "bloqueado"
            Color.black.opacity(0.35)

            // Cadeado circular — contraste alto sobre qualquer cover art
            Image(systemName: "lock.fill")
                .font(.system(size: 12, weight: .bold))
                .foregroundStyle(Color.white)
                .frame(width: 28, height: 28)
                .background(
                    Circle()
                        .fill(Color.black.opacity(0.85))
                        .overlay(
                            Circle()
                                .stroke(Color.white.opacity(0.15), lineWidth: 0.5)
                        )
                )
                .padding(Theme.Space.md)
        }
    }
}

/// Category badge preto. Substitui a versão colorida antiga.
/// Sempre preto sobre creme, uma cor só — não compete com a cover art.
struct CategoryBadge: View {
    let category: StoryCategory

    var body: some View {
        Text(category.badgeName)
            .font(.ui(9, weight: .bold))
            .tracking(0.8)
            .foregroundStyle(Theme.Colors.onInk)
            .padding(.horizontal, Theme.Space.sm)
            .padding(.vertical, 3)
            .background(
                Capsule().fill(Theme.Colors.inkDeep)
            )
            .accessibilityHidden(true)  // já anunciado no card label
    }
}

/// Botão CTA rosa cheio — usado no hero card (Continue, Start reading).
/// Não é reutilizado em outros lugares (Paywall tem o próprio, Onboarding
/// idem) porque cada contexto quer variação sutil de peso/altura.
private struct CTAButton: View {
    let label: String

    var body: some View {
        HStack(spacing: Theme.Space.sm) {
            Text(label)
                .font(.ui(15, weight: .bold))
            Image(systemName: "arrow.right")
                .font(.system(size: 13, weight: .bold))
        }
        .foregroundStyle(Theme.Colors.onAccent)
        .frame(maxWidth: .infinity, minHeight: Touch.min)
        .background(
            RoundedRectangle(cornerRadius: Theme.Radius.md)
                .fill(Theme.Colors.primary)
                .overlay(
                    RoundedRectangle(cornerRadius: Theme.Radius.md)
                        .stroke(Theme.Colors.stroke, lineWidth: Theme.Stroke.normal)
                )
        )
        .hardShadow(
            RoundedRectangle(cornerRadius: Theme.Radius.md),
            offset: CGSize(width: 2, height: 3)
        )
    }
}

/// Barra de progresso preta. Antes tinha cor por theme da história, agora
/// preto pra todas — consistência.
private struct ProgressBar: View {
    let fraction: Double

    var body: some View {
        GeometryReader { geo in
            ZStack(alignment: .leading) {
                Capsule()
                    .fill(Theme.Colors.track)
                Capsule()
                    .fill(Theme.Colors.ink)
                    .frame(width: geo.size.width * fraction)
                    .animation(.spring(response: 0.6, dampingFraction: 0.8), value: fraction)
            }
        }
    }
}
