//
//  HomeView.swift
//  pedagogy
//
//  ─── HOME v3 (Read tab) ─────────────────────────────────────────────────────
//  Vitrine editorial. NÃO é biblioteca — é a tela pra chegar de manhã, ver
//  o que tem de novo, e começar a ler. Biblioteca completa é na tab Library.
//
//  DIFERENÇA PRA v2.1
//
//  Antes: Featured hero + Library grid empilhado tudo na Home. Não escalava
//  além de ~5 histórias. Se você tinha 20, a Home virava scroll infinito.
//
//  Agora: 7 sections curadas + link pra Library. O tamanho da Home é
//  constante independente do catálogo total. 5 histórias ou 50, a Home
//  parece a mesma.
//
//  LAYOUT
//
//    ┌─────────────────────────────┐
//    │  Pedagogy         🔥 3      │  ← header compacto
//    │                             │
//    │  Welcome back.              │  ← greeting
//    │                             │
//    │  ─── Pedagogy Originals ─   │  ← curtas próprios, se houver
//    │  ▶ pôster 16:9  ▶ pôst…     │
//    │                             │
//    │  ┌─── Continue reading ──┐  │  ← só se in-progress
//    │  │ ▢ The Butterfly Garden│  │
//    │  │   Chapter 2 · 8 min   │  │
//    │  └───────────────────────┘  │
//    │                             │
//    │  ─── This week ─────────    │  ← nova da semana
//    │  ┌───────────────────────┐  │
//    │  │  cover 5:4            │  │
//    │  │  The Fox and the...   │  │
//    │  │  [Start reading]      │  │
//    │  └───────────────────────┘  │
//    │                             │
//    │  ─── Watch ─────────────    │  ← filmes abertos e clássicos, se houver
//    │  ▶ pôster 16:9              │
//    │                             │
//    │  ─── Browse by mood ────    │
//    │  [Mystery][Adventure]...    │  ← 5 chips, scroll horizontal
//    │                             │
//    │  ─── Featured picks ────    │
//    │  ▢▢▢ (horizontal scroll)    │  ← 3 covers curadas
//    │                             │
//    │  ┌───────────────────────┐  │
//    │  │  See all 50 stories → │  │  ← link pra Library
//    │  └───────────────────────┘  │
//    └─────────────────────────────┘
//
//  LÓGICAS DERIVADAS
//
//  • Continue reading: mais recente com isInProgress==true. Se nenhuma,
//    a seção some.
//  • This week: story com publishedAt no range [7 dias atrás, hoje],
//    preferindo a mais recente. Se nenhuma, a seção some (raro se drip
//    semanal for consistente).
//  • Featured picks: até 3 stories com isFeatured==true. Excluída a story
//    que já está em "This week" pra não repetir. Se nenhuma, seção some.
//  • Browse chips: sempre visível, todas as 5 categorias.
//
//  CLICK BEHAVIOR
//
//  • Continue reading: tap → StoryDetail
//  • This week hero: tap → StoryDetail
//  • Chip de categoria: tap → LibraryView com preselectedCategory
//  • Featured cover: tap → StoryDetail
//  • See all N: tap → LibraryView (sem filtro)
//  ────────────────────────────────────────────────────────────────────────────

import SwiftUI

struct HomeView: View {
    @Environment(LibraryProgress.self) private var library
    @Environment(Store.self) private var store
    @Environment(AudioPlayerManager.self) private var audio

    /// Callback pra MainTabView trocar de tab (Read → Library).
    /// - Recebe `StoryCategory?`: se nil, abre Library sem filtro ("See all").
    ///   Se algum case, abre Library com filtro pré-aplicado (chip de mood).
    /// Setada pela MainTabView; default é no-op pra permitir previews da
    /// HomeView isolada sem crashar.
    var onNavigateToLibrary: (StoryCategory?) -> Void = { _ in }

    @State private var stories: [Story] = []
    @State private var loadError: String?

    @State private var shorts: [Short] = []
    @State private var shortLauncher = ShortLauncher()
    @State private var isPaywallPresented = false

    // MARK: - Derived sections

    /// Última história tocada que ainda não foi terminada.
    /// Retorna nil se nenhuma em progresso (seção "Continue" some).
    private var continueReading: Story? {
        stories
            .filter { library.progress(for: $0.id).isInProgress }
            .max { a, b in
                let ta = library.progress(for: a.id).lastReadAt ?? .distantPast
                let tb = library.progress(for: b.id).lastReadAt ?? .distantPast
                return ta < tb
            }
    }

    /// A "story of the week" — publishedAt dentro dos últimos 7 dias.
    /// Se múltiplas caem no range, pega a mais recente.
    /// Retorna nil se nenhuma qualifica (seção "This week" some).
    private var thisWeek: Story? {
        let now = Date()
        let sevenDaysAgo = Calendar.current.date(byAdding: .day, value: -7, to: now) ?? now
        return stories
            .compactMap { story -> (Story, Date)? in
                guard let pub = story.publishedAt, pub >= sevenDaysAgo, pub <= now else {
                    return nil
                }
                return (story, pub)
            }
            .max { $0.1 < $1.1 }?
            .0
    }

    /// Curtas próprios (scripts/shorts): a primeira seção da Home.
    private var originals: [Short] {
        shorts.filter { $0.resolvedKind == .original }
    }

    /// Filmes abertos e clássicos: a seção "Watch", mais abaixo.
    private var otherShorts: [Short] {
        shorts.filter { $0.resolvedKind != .original }
    }

    /// Até 3 stories marcadas isFeatured==true, excluindo a de "This week"
    /// pra não duplicar destaque.
    private var featuredPicks: [Story] {
        let thisWeekId = thisWeek?.id
        return stories
            .filter { $0.isFeatured == true && $0.id != thisWeekId }
            .prefix(3)
            .map { $0 }
    }

    // MARK: - Body

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: Theme.Space.xxl) {
                    Header(streakDays: library.streak.currentStreak)

                    Greeting(hasContinue: continueReading != nil)

                    if let loadError {
                        ErrorPanel(message: loadError)
                    } else if stories.isEmpty {
                        LoadingPanel()
                    } else {
                        // Seções em ordem editorial. Os curtas próprios abrem
                        // a Home: são a vitrine do que só o Pedagogy tem.
                        if !originals.isEmpty {
                            WatchSection(
                                title: "Pedagogy Originals",
                                shorts: originals,
                                launcher: shortLauncher,
                                isLocked: isLocked,
                                onTap: playShort
                            )
                            .announcesFailures()
                        }

                        if let cont = continueReading {
                            ContinueReadingSection(
                                story: cont,
                                progress: library.progress(for: cont.id)
                            )
                        }

                        if let week = thisWeek {
                            ThisWeekSection(
                                story: week,
                                progress: library.progress(for: week.id)
                            )
                        }

                        if !otherShorts.isEmpty {
                            WatchSection(
                                title: "Watch",
                                shorts: otherShorts,
                                launcher: shortLauncher,
                                isLocked: isLocked,
                                onTap: playShort
                            )
                            .announcesFailures()
                        }

                        BrowseByMoodSection(onCategoryTap: { category in
                            onNavigateToLibrary(category)
                        })

                        if !featuredPicks.isEmpty {
                            FeaturedPicksSection(
                                stories: featuredPicks,
                                library: library
                            )
                        }

                        SeeAllLink(
                            totalCount: stories.count,
                            onTap: { onNavigateToLibrary(nil) }
                        )
                    }

                    Spacer(minLength: 120)  // room pra tab bar liquid glass
                }
                .padding(.horizontal, Theme.Space.lg)
                .padding(.top, Theme.Space.md)
            }
            .background(Theme.Colors.bg.ignoresSafeArea())
            .toolbar(.hidden, for: .navigationBar)
            .task {
                loadStories()
            }
            .navigationDestination(for: Story.self) { story in
                StoryDetailView(story: story)
            }
            .sheet(isPresented: $isPaywallPresented) {
                PaywallView(source: "short")
            }
        }
    }

    private func isLocked(_ short: Short) -> Bool {
        short.isPremium && !store.isPremium
    }

    private func playShort(_ short: Short) {
        if isLocked(short) {
            isPaywallPresented = true
        } else {
            shortLauncher.toggle(short, audio: audio)
        }
    }

    private func loadStories() {
        do {
            stories = try StoryLoader.loadAll()
            shorts = ShortCatalog.loadAll()
        } catch {
            loadError = error.localizedDescription
        }
    }
}

// MARK: - Header

/// Header minimal — só o badge de streak à direita (se houver).
/// Antes tinha "Pedagogy" à esquerda, removido pra dar mais peso ao
/// greeting "Welcome back" / "Ready to read?" que aparece logo abaixo.
/// Se streakDays == 0, o header vira uma linha invisível de padding —
/// mantém alinhamento vertical estável independente de ter streak ou não.
private struct Header: View {
    let streakDays: Int

    var body: some View {
        HStack {
            Spacer()

            if streakDays > 0 {
                StreakBadge(days: streakDays)
            }
        }
        // Reserva altura mínima igual à do badge (evita "colapso" da linha
        // quando streak == 0, o que faria o greeting subir).
        .frame(minHeight: 32)
    }
}

/// Badge do streak. Preto sobre creme (paleta minimal — sem amarelo).
private struct StreakBadge: View {
    let days: Int

    var body: some View {
        HStack(spacing: 4) {
            Image(systemName: "flame.fill")
                .font(.system(size: 12, weight: .semibold))
            Text("\(days)")
                .font(.ui(13, weight: .bold))
        }
        .foregroundStyle(Theme.Colors.onInk)
        .padding(.horizontal, Theme.Space.md)
        .padding(.vertical, Theme.Space.xs + 2)
        .background(
            Capsule().fill(Theme.Colors.ink)
        )
        .accessibilityElement()
        .accessibilityLabel("Streak: \(days) day\(days == 1 ? "" : "s")")
    }
}

// MARK: - Greeting

private struct Greeting: View {
    let hasContinue: Bool

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Space.xs) {
            Text(hasContinue ? "Welcome back." : "Ready to read?")
                .font(.display(30, weight: .bold))
                .foregroundStyle(Theme.Colors.ink)

            Text(hasContinue
                 ? "Pick up where you left off."
                 : "A new story every week.")
                .font(.body(15, weight: .regular))
                .foregroundStyle(Theme.Colors.textMuted)
                .lineSpacing(2)
        }
    }
}

// MARK: - Continue Reading

/// Mini card horizontal — cover pequena à esquerda, meta à direita.
/// Só aparece se há história em progresso.
private struct ContinueReadingSection: View {
    let story: Story
    let progress: StoryProgress

    @Environment(TranslationStore.self) private var translation

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Space.md) {
            SectionLabel(text: "Continue reading")

            NavigationLink(value: story) {
                HStack(spacing: Theme.Space.md) {
                    ThumbnailImage(story: story, size: 72)

                    VStack(alignment: .leading, spacing: 2) {
                        Text(translation.text(story.title))
                            .font(.display(15, weight: .semibold))
                            .foregroundStyle(Theme.Colors.ink)
                            .lineLimit(1)

                        Text("Chapter \((progress.chapterIndex + 1)) of \(story.chapters.count)")
                            .font(.ui(12, weight: .medium))
                            .foregroundStyle(Theme.Colors.textMuted)

                        // Barra de progresso mini
                        ProgressLine(
                            fraction: Double((progress.chapterIndex + 1) - 1) / Double(story.chapters.count)
                        )
                        .padding(.top, Theme.Space.xs)
                    }
                    .frame(maxWidth: .infinity, alignment: .leading)

                    Image(systemName: "chevron.right")
                        .font(.system(size: 13, weight: .semibold))
                        .foregroundStyle(Theme.Colors.textMuted)
                }
                .padding(Theme.Space.md)
                .background(
                    RoundedRectangle(cornerRadius: Theme.Radius.md)
                        .fill(Theme.Colors.surface)
                        .overlay(
                            RoundedRectangle(cornerRadius: Theme.Radius.md)
                                .stroke(Theme.Colors.stroke, lineWidth: Theme.Stroke.thin)
                        )
                )
            }
            .buttonStyle(.plain)
        }
    }
}

/// Linha de progresso fininha. Rosa preenchida sobre trilho neutro.
private struct ProgressLine: View {
    let fraction: Double

    var body: some View {
        GeometryReader { geo in
            ZStack(alignment: .leading) {
                Capsule().fill(Theme.Colors.track)
                Capsule()
                    .fill(Theme.Colors.primary)
                    .frame(width: geo.size.width * max(0, min(1, fraction)))
            }
        }
        .frame(height: 3)
    }
}

// MARK: - This Week

/// Hero da semana. Cover 5:4 grande + título + CTA rosa. Substitui o
/// featured hero da v2.1 — mesma prominência visual, mas com significado
/// "isto é novo" em vez de "escolha do editor".
private struct ThisWeekSection: View {
    let story: Story
    let progress: StoryProgress

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Space.md) {
            SectionLabel(text: "This week", accent: true)

            NavigationLink(value: story) {
                StoryHeroCard(story: story, progress: progress)
            }
            .buttonStyle(.plain)
        }
    }
}

// MARK: - Browse by Mood

/// 5 chips das categorias. Tap → troca pra tab Library com preselectedCategory.
/// Scroll horizontal se não couber (em iPhone SE, 5 pills apertam).
private struct BrowseByMoodSection: View {
    let onCategoryTap: (StoryCategory) -> Void

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Space.md) {
            SectionLabel(text: "Browse by mood")

            ScrollView(.horizontal, showsIndicators: false) {
                HStack(spacing: Theme.Space.sm) {
                    ForEach(StoryCategory.allCases.sorted { $0.displayOrder < $1.displayOrder }, id: \.self) { cat in
                        Button {
                            onCategoryTap(cat)
                        } label: {
                            MoodChip(category: cat)
                        }
                        .buttonStyle(.plain)
                    }
                }
                // Extend edge-to-edge (compensa o padding da HomeView)
                .padding(.horizontal, Theme.Space.lg)
            }
            .padding(.horizontal, -Theme.Space.lg)
        }
    }
}

private struct MoodChip: View {
    let category: StoryCategory

    var body: some View {
        Text(category.displayName)
            .font(.ui(13, weight: .semibold))
            .foregroundStyle(Theme.Colors.ink)
            .padding(.horizontal, Theme.Space.md)
            .padding(.vertical, Theme.Space.sm)
            .background(
                Capsule()
                    .fill(Theme.Colors.surface)
                    .overlay(
                        Capsule().stroke(Theme.Colors.border, lineWidth: Theme.Stroke.thin)
                    )
            )
    }
}

// MARK: - Featured Picks

/// Carousel horizontal de até 3 covers curadas. isFeatured==true nos JSONs.
/// Edite mensalmente pra manter fresh.
private struct FeaturedPicksSection: View {
    let stories: [Story]
    let library: LibraryProgress

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Space.md) {
            SectionLabel(text: "Featured picks")

            ScrollView(.horizontal, showsIndicators: false) {
                HStack(alignment: .top, spacing: Theme.Space.md) {
                    ForEach(stories) { story in
                        NavigationLink(value: story) {
                            FeaturedThumb(story: story)
                        }
                        .buttonStyle(.plain)
                    }
                }
                .padding(.horizontal, Theme.Space.lg)
            }
            .padding(.horizontal, -Theme.Space.lg)
        }
    }
}

/// Thumb do featured — cover 5:4 + título curto. Mais compacto que thumb
/// da Library (aqui tem 3 side-by-side, precisa ser menor).
private struct FeaturedThumb: View {
    let story: Story

    @Environment(TranslationStore.self) private var translation

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Space.sm) {
            ThumbnailImage(story: story, size: 160)

            Text(translation.text(story.title))
                .font(.display(13, weight: .semibold))
                .foregroundStyle(Theme.Colors.ink)
                .lineLimit(2)
                .multilineTextAlignment(.leading)
                .frame(width: 160, alignment: .leading)
        }
    }
}

// MARK: - See All Link

/// Link visualmente destacado pra Library. Fica no fim da Home.
/// Ao tocar, MainTabView troca pra tab Library (não empilha na Home stack).
private struct SeeAllLink: View {
    let totalCount: Int
    let onTap: () -> Void

    var body: some View {
        Button(action: onTap) {
            HStack {
                Text("See all \(totalCount) stories")
                    .font(.ui(15, weight: .semibold))
                    .foregroundStyle(Theme.Colors.ink)

                Spacer()

                Image(systemName: "arrow.right")
                    .font(.system(size: 13, weight: .bold))
                    .foregroundStyle(Theme.Colors.ink)
            }
            .padding(Theme.Space.lg)
            .frame(maxWidth: .infinity)
            .background(
                RoundedRectangle(cornerRadius: Theme.Radius.md)
                    .fill(Theme.Colors.surface)
                    .overlay(
                        RoundedRectangle(cornerRadius: Theme.Radius.md)
                            .stroke(Theme.Colors.stroke, lineWidth: Theme.Stroke.thin)
                    )
            )
        }
        .buttonStyle(.plain)
    }
}

// MARK: - Shared

/// Label de seção. Uppercase pequeno, ink escuro. Se `accent`, ponto rosa
/// à esquerda pra destacar "This week" das outras seções.
private struct SectionLabel: View {
    let text: String
    var accent: Bool = false

    var body: some View {
        HStack(spacing: Theme.Space.sm) {
            if accent {
                Circle()
                    .fill(Theme.Colors.primary)
                    .frame(width: 6, height: 6)
            }
            Text(text)
                .font(.ui(11, weight: .bold))
                .kerning(1.2)
                .foregroundStyle(Theme.Colors.textStrong)
                .textCase(.uppercase)
        }
    }
}

/// Thumbnail 5:4 reutilizável. Usada em Continue reading (72pt largura),
/// e Featured picks (160pt largura). Adiciona overlay bloqueado
/// automaticamente quando a história está gated (`!isFreeToRead()`).
private struct ThumbnailImage: View {
    let story: Story
    let size: CGFloat

    var body: some View {
        ZStack {
            Group {
                if let name = story.coverImage, UIImage(named: name) != nil {
                    Image(name)
                        .resizable()
                        .aspectRatio(5/4, contentMode: .fill)
                } else {
                    Theme.Colors.bgSepia
                        .overlay(
                            Image(systemName: "book.closed.fill")
                                .font(.system(size: size * 0.3, weight: .light))
                                .foregroundStyle(Theme.Colors.textFaint)
                        )
                }
            }

            // Overlay premium — mesmo tratamento do CoverImageSlot no
            // StoryCard. Compacto por padrão pra caber em thumbnails
            // pequenas (72pt) sem ficar poluído.
            if !story.isFreeToRead() {
                CompactLockedOverlay()
            }
        }
        .frame(width: size, height: size * (4.0/5.0))
        .clipShape(RoundedRectangle(cornerRadius: Theme.Radius.sm))
        .overlay(
            RoundedRectangle(cornerRadius: Theme.Radius.sm)
                .stroke(Theme.Colors.stroke, lineWidth: Theme.Stroke.thin)
        )
    }
}

/// Versão compacta do LockedOverlay pra thumbnails pequenos — só o cadeado,
/// sem label "PREMIUM" (não caberia em 72pt). O overlay dessaturado
/// continua ajudando a sinalizar "gated" mesmo à distância.
private struct CompactLockedOverlay: View {
    var body: some View {
        ZStack(alignment: .topTrailing) {
            Color.black.opacity(0.35)

            Image(systemName: "lock.fill")
                .font(.system(size: 10, weight: .bold))
                .foregroundStyle(Color.white)
                .frame(width: 20, height: 20)
                .background(
                    Circle()
                        .fill(Color.black.opacity(0.85))
                        .overlay(
                            Circle()
                                .stroke(Color.white.opacity(0.15), lineWidth: 0.5)
                        )
                )
                .padding(Theme.Space.xs)
        }
    }
}

// MARK: - State Panels

private struct LoadingPanel: View {
    var body: some View {
        VStack {
            ProgressView()
                .tint(Theme.Colors.primary)
            Text("Loading stories…")
                .font(.ui(13, weight: .medium))
                .foregroundStyle(Theme.Colors.textMuted)
                .padding(.top, Theme.Space.sm)
        }
        .frame(maxWidth: .infinity)
        .padding(.vertical, Theme.Space.huge)
    }
}

private struct ErrorPanel: View {
    let message: String

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Space.sm) {
            Text("Something went wrong")
                .font(.ui(14, weight: .bold))
                .foregroundStyle(Theme.Colors.danger)
            Text(message)
                .font(.body(13))
                .foregroundStyle(Theme.Colors.textStrong)
                .lineSpacing(3)
        }
        .padding(Theme.Space.lg)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(
            RoundedRectangle(cornerRadius: Theme.Radius.md)
                .fill(Theme.Colors.dangerTint)
        )
    }
}
