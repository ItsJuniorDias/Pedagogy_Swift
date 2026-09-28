//
//  LibraryView.swift
//  pedagogy
//
//  ─── LIBRARY ────────────────────────────────────────────────────────────────
//  Segunda tab do app. Vitrine completa das histórias, otimizada pra
//  navegar catálogos grandes (design pensado pra escalar até ~50).
//
//  LAYOUT
//
//    ┌─────────────────────────────┐
//    │  Library         [↕]        │  ← header + sort
//    │                             │
//    │  [All][Mystery][Adventure]  │  ← category pills, horizontal scroll
//    │                             │
//    │  ┌────────┐  ┌────────┐    │
//    │  │ cover  │  │ cover  │    │  ← grid 2-col, StoryThumbCard
//    │  ├────────┤  ├────────┤    │
//    │  │ title  │  │ title  │    │
//    │  │ 15 min │  │ 14 min │    │
//    │  └────────┘  └────────┘    │
//    │  ┌────────┐  ┌────────┐    │
//    │  ...                        │
//    └─────────────────────────────┘
//
//  FILTRO POR CATEGORIA
//
//  Pills no topo. "All" mostra tudo (default). Categoria selecionada tem
//  fundo rosa. Chip escolhida na Home vem já selecionada aqui via
//  `preselectedCategory` no init.
//
//  SORT
//
//  4 opções via Menu:
//    • Newest first    (default — publishedAt desc)
//    • Alphabetical    (title asc)
//    • Unread first    (progresso == none primeiro)
//    • By category     (agrupa por displayOrder da categoria)
//
//  STATE
//
//  Local por tab. NavigationStack próprio (não compartilha com Home).
//  Ao trocar de tab e voltar, mantém categoria selecionada e sort.
//  ────────────────────────────────────────────────────────────────────────────

import SwiftUI

// MARK: - Sort Options

enum LibrarySort: String, CaseIterable {
    case newest       = "Newest first"
    case alphabetical = "Alphabetical"
    case unread       = "Unread first"
    case byCategory   = "By category"

    var systemImage: String {
        switch self {
        case .newest:       return "calendar"
        case .alphabetical: return "textformat"
        case .unread:       return "circle.dashed"
        case .byCategory:   return "square.grid.2x2"
        }
    }
}

// MARK: - Category Filter (nil = All)

/// Optional wrapper — nil significa "All categories".
/// Não uso `StoryCategory?` diretamente no state pra ficar mais explícito
/// em cada uso ("selectedCategory == nil ? show all : filter").
typealias CategoryFilter = StoryCategory?

// MARK: - LibraryView

struct LibraryView: View {
    @Environment(LibraryProgress.self) private var library

    /// Categoria pré-selecionada. Vem de fora (MainTabView) via binding pra
    /// permitir que a Home dispare o filtro ao tocar num chip de mood mesmo
    /// quando a LibraryView já está instanciada.
    ///
    /// Ao detectar mudança pra não-nil, aplicamos como `selectedCategory` e
    /// **limpamos o binding** pra que próximos taps do mesmo chip disparem
    /// novamente (senão o `onChange` não detecta "mesma categoria de novo").
    @Binding var preselectedCategory: StoryCategory?

    @State private var stories: [Story] = []
    @State private var loadError: String?
    @State private var selectedCategory: CategoryFilter = nil
    @State private var sort: LibrarySort = .newest

    init(preselectedCategory: Binding<StoryCategory?> = .constant(nil)) {
        self._preselectedCategory = preselectedCategory
    }

    // MARK: - Derived

    /// Histórias após aplicar filtro de categoria e sort.
    private var visibleStories: [Story] {
        let filtered: [Story]
        if let cat = selectedCategory {
            filtered = stories.filter { $0.category == cat }
        } else {
            filtered = stories
        }
        return applySort(filtered)
    }

    private func applySort(_ input: [Story]) -> [Story] {
        switch sort {
        case .newest:
            // publishedAt nil vai pro fim (histórias sem data são antigas)
            return input.sorted { a, b in
                switch (a.publishedAt, b.publishedAt) {
                case (let da?, let db?): return da > db
                case (_?, nil):          return true
                case (nil, _?):          return false
                case (nil, nil):         return a.title < b.title
                }
            }
        case .alphabetical:
            return input.sorted { $0.title.localizedCaseInsensitiveCompare($1.title) == .orderedAscending }
        case .unread:
            return input.sorted { a, b in
                let pa = library.progress(for: a.id)
                let pb = library.progress(for: b.id)
                // Unread (nem completo nem em progresso) primeiro
                let aUnread = !pa.isFinished && !pa.isInProgress
                let bUnread = !pb.isFinished && !pb.isInProgress
                if aUnread != bUnread { return aUnread }
                return a.title < b.title
            }
        case .byCategory:
            return input.sorted { a, b in
                if a.category.displayOrder != b.category.displayOrder {
                    return a.category.displayOrder < b.category.displayOrder
                }
                return a.title < b.title
            }
        }
    }

    // MARK: - Body

    var body: some View {
        NavigationStack {
            // VStack fixo respeita safe area top do notch automaticamente.
            // Header vai FORA do ScrollView — não rola com o content.
            VStack(spacing: 0) {
                // ─── HEADER FIXO ──────────────────────────────────────
                // "Library" à esquerda em Alfa Slab, sort button à direita.
                // Fica ancorado abaixo da status bar / notch.
                HStack(alignment: .center) {
                    Text("Library")
                        .font(.display(34))
                        .foregroundStyle(Theme.Colors.ink)

                    Spacer()

                    sortMenu
                }
                .padding(.horizontal, Theme.Space.lg)
                .padding(.top, Theme.Space.md)
                .padding(.bottom, Theme.Space.md)

                // ─── CONTENT SCROLLÁVEL ───────────────────────────────
                // Pills sticky no topo do scroll, grid abaixo.
                ScrollView {
                    LazyVStack(spacing: Theme.Space.xl, pinnedViews: [.sectionHeaders]) {
                        Section {
                            content
                                .padding(.horizontal, Theme.Space.lg)
                                .padding(.top, Theme.Space.md)
                        } header: {
                            CategoryPills(
                                selected: $selectedCategory,
                                categoryCounts: categoryCounts
                            )
                        }
                    }
                    // Room pra tab bar liquid glass — ~80-90pt em iOS 26+
                    .padding(.bottom, 120)
                }
            }
            .background(Theme.Colors.bg.ignoresSafeArea())
            // Esconde nav bar do system inteira — usamos header custom acima.
            .toolbar(.hidden, for: .navigationBar)
            .task {
                loadStories()
                // Se já veio com preselect no primeiro launch, aplica.
                applyPreselectIfNeeded()
            }
            // Reage a mudanças posteriores (Home tocou um chip enquanto a
            // Library já estava instanciada). Limpa o binding pra próximo
            // tap do mesmo chip disparar de novo.
            .onChange(of: preselectedCategory) { _, _ in
                applyPreselectIfNeeded()
            }
            .navigationDestination(for: Story.self) { story in
                StoryDetailView(story: story)
            }
        }
    }

    /// Aplica preselectedCategory como filtro ativo se houver um valor,
    /// depois limpa o binding. Idempotente (nil ignorado).
    private func applyPreselectIfNeeded() {
        guard let pre = preselectedCategory else { return }
        selectedCategory = pre
        preselectedCategory = nil
    }

    // MARK: - Content

    @ViewBuilder
    private var content: some View {
        if let loadError {
            ErrorPanel(message: loadError)
        } else if stories.isEmpty {
            LoadingPanel()
        } else if visibleStories.isEmpty {
            EmptyCategoryPanel(category: selectedCategory)
        } else {
            grid
        }
    }

    /// Grid 2-col de thumbs. LazyVGrid pra suportar catálogos grandes sem
    /// carregar tudo de uma vez.
    private var grid: some View {
        LazyVGrid(
            columns: [
                GridItem(.flexible(), spacing: Theme.Space.md),
                GridItem(.flexible(), spacing: Theme.Space.md)
            ],
            spacing: Theme.Space.xl
        ) {
            ForEach(visibleStories) { story in
                NavigationLink(value: story) {
                    StoryThumbCard(
                        story: story,
                        progress: library.progress(for: story.id)
                    )
                }
                .buttonStyle(.plain)
            }
        }
    }

    private var sortMenu: some View {
        Menu {
            ForEach(LibrarySort.allCases, id: \.self) { option in
                Button {
                    sort = option
                } label: {
                    Label(option.rawValue, systemImage: option.systemImage)
                    if option == sort {
                        Image(systemName: "checkmark")
                    }
                }
            }
        } label: {
            // Botão circular flutuante (como se fosse chip da nav bar) —
            // precisa do próprio background porque não está mais dentro
            // do UIToolbar do system.
            Image(systemName: "arrow.up.arrow.down")
                .font(.system(size: 15, weight: .semibold))
                .foregroundStyle(Theme.Colors.ink)
                .frame(width: 36, height: 36)
                .background(
                    Circle()
                        .fill(Theme.Colors.surface)
                        .overlay(
                            Circle()
                                .stroke(Theme.Colors.border, lineWidth: Theme.Stroke.hair)
                        )
                )
        }
        .accessibilityLabel("Sort library")
    }

    // MARK: - Data

    /// Contagem de histórias por categoria. Usado nos pills pra mostrar "(10)"
    /// discretamente ao lado do nome da categoria.
    private var categoryCounts: [StoryCategory: Int] {
        Dictionary(grouping: stories, by: \.category).mapValues(\.count)
    }

    private func loadStories() {
        do {
            stories = try StoryLoader.loadAll()
        } catch {
            loadError = error.localizedDescription
        }
    }
}

// MARK: - Category Pills (sticky header)

/// Barra horizontal de pills fixa no topo enquanto o grid rola. Aparece
/// como sectionHeader do LazyVStack — pinnedViews mantém sticky.
///
/// Pill "All" sempre primeiro. Cada pill mostra o nome da categoria + count
/// discreto entre parênteses (só se count > 0). Selecionada tem fundo rosa
/// (única cor de destaque no app).
private struct CategoryPills: View {
    @Binding var selected: CategoryFilter
    let categoryCounts: [StoryCategory: Int]

    private var allCount: Int {
        categoryCounts.values.reduce(0, +)
    }

    var body: some View {
        ScrollView(.horizontal, showsIndicators: false) {
            HStack(spacing: Theme.Space.sm) {
                Pill(
                    label: "All",
                    count: allCount,
                    isSelected: selected == nil
                ) {
                    selected = nil
                }

                ForEach(StoryCategory.allCases.sorted { $0.displayOrder < $1.displayOrder }, id: \.self) { cat in
                    Pill(
                        label: cat.displayName,
                        count: categoryCounts[cat] ?? 0,
                        isSelected: selected == cat
                    ) {
                        selected = cat
                    }
                }
            }
            .padding(.horizontal, Theme.Space.lg)
            .padding(.vertical, Theme.Space.sm)
        }
        // Fundo creme sólido pra pills não misturarem com o grid ao ficar
        // sticky. Border sutil no bottom marca separação.
        .background(
            Theme.Colors.bg
                .overlay(
                    Rectangle()
                        .fill(Theme.Colors.border)
                        .frame(height: 0.5),
                    alignment: .bottom
                )
                .ignoresSafeArea(edges: .horizontal)
        )
    }
}

private struct Pill: View {
    let label: String
    let count: Int
    let isSelected: Bool
    let action: () -> Void

    var body: some View {
        Button(action: action) {
            HStack(spacing: Theme.Space.xs) {
                Text(label)
                    .font(.ui(13, weight: .semibold))

                if count > 0 {
                    Text("\(count)")
                        .font(.ui(11, weight: .medium))
                        .opacity(0.7)
                }
            }
            .foregroundStyle(isSelected ? Theme.Colors.onAccent : Theme.Colors.ink)
            .padding(.horizontal, Theme.Space.md)
            .padding(.vertical, Theme.Space.sm)
            .background(
                Capsule()
                    .fill(isSelected ? Theme.Colors.primary : Theme.Colors.surface)
                    .overlay(
                        Capsule()
                            .stroke(
                                isSelected ? Theme.Colors.primaryDeep : Theme.Colors.border,
                                lineWidth: Theme.Stroke.thin
                            )
                    )
            )
        }
        .buttonStyle(.plain)
        .accessibilityAddTraits(isSelected ? [.isSelected] : [])
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

/// Aparece quando o filtro selecionado não tem nenhuma história.
/// Comum enquanto o catálogo cresce — "Legends" pode estar vazio no início.
private struct EmptyCategoryPanel: View {
    let category: StoryCategory?

    var body: some View {
        VStack(spacing: Theme.Space.md) {
            Image(systemName: "books.vertical")
                .font(.system(size: 40, weight: .light))
                .foregroundStyle(Theme.Colors.textFaint)

            Text("No stories yet in \(category?.displayName ?? "this section")")
                .font(.display(17, weight: .semibold))
                .foregroundStyle(Theme.Colors.ink)

            Text("Check back soon — new stories drop every week.")
                .font(.body(13))
                .foregroundStyle(Theme.Colors.textMuted)
                .multilineTextAlignment(.center)
                .lineSpacing(3)
        }
        .frame(maxWidth: .infinity)
        .padding(.vertical, Theme.Space.huge)
        .padding(.horizontal, Theme.Space.xl)
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

#Preview {
    LibraryView()
        .environment(Store())
        .environment(LibraryProgress())
        .environment(TranslationStore())
}
