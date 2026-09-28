//
//  ProfileView.swift
//  pedagogy
//
//  ─── PROFILE (You tab) ──────────────────────────────────────────────────────
//  A terceira tab. Vitrine íntima do progresso de leitura do usuário.
//  Não é dashboard de gamificação — é uma "biblioteca pessoal" com
//  marcadores.
//
//  LAYOUT
//
//    ┌─────────────────────────────┐
//    │  Your reading life          │  ← greeting minimal
//    │                             │
//    │  ┌─── Stats ────────────┐   │  ← 3 colunas: streak · stories · time
//    │  │  12  ·  47  ·  180m  │   │
//    │  └──────────────────────┘   │
//    │                             │
//    │  ─── Marks ─────────────    │  ← seção header
//    │  ┌───┐  ┌───┐  ┌───┐        │
//    │  │ 1 │  │ 2 │  │ 3 │        │
//    │  └───┘  └───┘  └───┘        │
//    │  ┌───┐  ┌───┐  ┌───┐        │  ← grid 3×4 = 12 achievements
//    │  │ 4 │  │ 5 │  │ 6 │        │
//    │  └───┘  └───┘  └───┘        │
//    │  ...                        │
//    └─────────────────────────────┘
//
//  QUANDO CHECAR UNLOCKS
//
//  .task ao aparecer + .onChange nos snapshots do LibraryProgress. Isso
//  garante que se o usuário unlock algo em outra tab e trocar pra Profile,
//  o card já aparece unlocked. E se estiver na Profile e algo unlockar
//  (edge case: notif, deep link), refresha na hora.
//
//  Não uso "Marks" como header do grid literalmente porque some entre as
//  categorias. Uso o texto "Marks" pequeno + pink dot na seção.
//  ────────────────────────────────────────────────────────────────────────────

import SwiftUI

struct ProfileView: View {
    @Environment(LibraryProgress.self) private var library
    @Environment(AchievementsStore.self) private var achievements

    @State private var stories: [Story] = []
    @State private var loadError: String? = nil

    /// Achievement selecionado pra apresentar em modal. `nil` quando nada
    /// aberto. Populado ao tocar num card, limpo ao dismissar o sheet.
    /// Achievement é Identifiable (id: AchievementID), então funciona
    /// direto com .sheet(item:).
    @State private var selectedAchievement: Achievement? = nil

    /// Grid columns pro achievements — 3 fixed pra sensação de "vitrine".
    private let columns = [
        GridItem(.flexible(), spacing: Theme.Space.md),
        GridItem(.flexible(), spacing: Theme.Space.md),
        GridItem(.flexible(), spacing: Theme.Space.md),
    ]

    // MARK: - Derived stats

    /// Quantas stories o usuário terminou. Sobre stories carregadas — se
    /// alguma story foi removida do bundle mas o progress ficou, ignora.
    private var storiesFinished: Int {
        stories.filter { library.progress(for: $0.id).isFinished }.count
    }

    /// Tempo estimado somado: readingTimeMinutes de cada story finished.
    /// Não é medido de verdade — é bulk estimate. Ver docstring do card.
    private var totalMinutes: Int {
        stories
            .filter { library.progress(for: $0.id).isFinished }
            .reduce(0) { $0 + $1.readingTimeMinutes }
    }

    // MARK: - Body

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: Theme.Space.xxl) {

                    // ─── Header ─────────────────────────────────────
                    Header()

                    TranslationCard()

                    // ─── Loading / error / content ─────────────────
                    if let loadError {
                        ErrorPanel(message: loadError)
                    } else if stories.isEmpty {
                        LoadingPanel()
                    } else {
                        // Stats card
                        ReadingStatsCard(
                            streakDays: library.streak.currentStreak,
                            storiesFinished: storiesFinished,
                            totalMinutes: totalMinutes
                        )

                        // Weekday pattern chart. Ordena visualmente entre os
                        // stats (contexto quantitativo) e os achievements
                        // (contexto qualitativo/milestones). É reflexivo,
                        // não motivacional — mostra ao usuário o pattern
                        // dele sem cobrar mais.
                        ReadingActivityChart(log: library.readingLog)

                        // Section header pros achievements
                        SectionHeader(title: "Marks", subtitle: markSubtitle)

                        // Grid
                        LazyVGrid(columns: columns, spacing: Theme.Space.md) {
                            ForEach(Achievement.all) { achievement in
                                AchievementCard(
                                    achievement: achievement,
                                    unlockedAt: achievements.unlockedAt(achievement.id),
                                    progress: achievement.progress(library, stories),
                                    onTap: {
                                        selectedAchievement = achievement
                                    }
                                )
                            }
                        }
                    }

                    Spacer(minLength: 120)   // room pra tab bar liquid glass
                }
                .padding(.horizontal, Theme.Space.lg)
                .padding(.top, Theme.Space.md)
            }
            .background(Theme.Colors.bg.ignoresSafeArea())
            .toolbar(.hidden, for: .navigationBar)
            .task {
                loadStories()
                achievements.checkForUnlocks(library: library, stories: stories)
            }
            // Se progresso mudar enquanto Profile está visível (raro — usuário
            // não deve estar lendo com Profile aberta — mas cobre o caso de
            // notification deep link ou state change externo), re-avalia.
            .onChange(of: library.stories.count) { _, _ in
                achievements.checkForUnlocks(library: library, stories: stories)
            }
            .onChange(of: library.streak.currentStreak) { _, _ in
                achievements.checkForUnlocks(library: library, stories: stories)
            }
            .sheet(item: $selectedAchievement) { achievement in
                AchievementDetailSheet(
                    achievement: achievement,
                    unlockedAt: achievements.unlockedAt(achievement.id),
                    progress: achievement.progress(library, stories),
                    onClose: { selectedAchievement = nil }
                )
            }
        }
    }

    private var markSubtitle: String {
        let total = Achievement.all.count
        let unlocked = Achievement.all.filter { achievements.isUnlocked($0.id) }.count
        return "\(unlocked) of \(total)"
    }

    private func loadStories() {
        do {
            stories = try StoryLoader.loadAll()
        } catch {
            loadError = error.localizedDescription
        }
    }
}

// MARK: - Header

/// Header minimal, mesmo padrão do HomeView (sem "Pedagogy" à esquerda,
/// só título editorial grande).
private struct Header: View {
    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Space.xs) {
            Text("Your reading life")
                .displayTitle(size: 30)
                .fixedSize(horizontal: false, vertical: true)

            Text("Marks and minutes.")
                .font(.body(15, weight: .regular))
                .foregroundStyle(Theme.Colors.textMuted)
        }
    }
}

// MARK: - Translation Card

/// Idioma de leitura das histórias. Mesmo estado do menu de tradução no
/// reader. Padrão: inglês original.
///
/// Mesmo acabamento do `ReadingStatsCard` (borda grossa + sombra hard). O
/// nome do idioma fica em destaque à esquerda e o seletor é só um botão
/// "Change" — nomes como "Português (Brasil)" não cabem ao lado de um título
/// sem quebrar linha.
private struct TranslationCard: View {
    @Environment(TranslationStore.self) private var translation

    private var languageName: String {
        translation.targetLanguage.map(TranslationStore.displayName(of:)) ?? "English"
    }

    private var footnote: String {
        if let error = translation.lastError { return error }
        guard translation.targetLanguage != nil else {
            return "Stories are in their original English. Pick a language to translate them on this device."
        }
        if translation.availability == .unavailable {
            return "This language isn't available on this device."
        }
        return "Translated on this device. Narration stays in English."
    }

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Space.md) {
            HStack(alignment: .center, spacing: Theme.Space.md) {
                VStack(alignment: .leading, spacing: 2) {
                    Text("STORY LANGUAGE")
                        .font(.ui(10, weight: .bold))
                        .tracking(1.0)
                        .foregroundStyle(Theme.Colors.textMuted)

                    Text(languageName)
                        .font(.display(22, weight: .bold))
                        .foregroundStyle(Theme.Colors.ink)
                        .lineLimit(1)
                        .minimumScaleFactor(0.7)
                }

                Spacer(minLength: 0)

                Menu {
                    TranslationLanguagePicker()
                } label: {
                    HStack(spacing: 6) {
                        Image(systemName: "translate")
                            .font(.system(size: 12, weight: .bold))
                        Text("Change")
                            .font(.ui(13, weight: .bold))
                    }
                    .foregroundStyle(Theme.Colors.onAccent)
                    .padding(.horizontal, Theme.Space.md)
                    .padding(.vertical, Theme.Space.sm)
                    .background(
                        Capsule()
                            .fill(Theme.Colors.primary)
                            .overlay(
                                Capsule()
                                    .stroke(Theme.Colors.stroke, lineWidth: Theme.Stroke.thin)
                            )
                    )
                    .fixedSize()
                }
                .accessibilityLabel("Change story language, currently \(languageName)")
            }

            Rectangle()
                .fill(Theme.Colors.border)
                .frame(height: Theme.Stroke.hair)

            Text(footnote)
                .font(.ui(12, weight: .regular))
                .foregroundStyle(Theme.Colors.textMuted)
                .fixedSize(horizontal: false, vertical: true)
        }
        .padding(Theme.Space.lg)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(Theme.Colors.surface)
        .clipShape(RoundedRectangle(cornerRadius: Theme.Radius.md))
        .overlay(
            RoundedRectangle(cornerRadius: Theme.Radius.md)
                .stroke(Theme.Colors.stroke, lineWidth: Theme.Stroke.thick)
        )
        .hardShadow(
            RoundedRectangle(cornerRadius: Theme.Radius.md),
            offset: CGSize(width: 4, height: 5)
        )
    }
}

// MARK: - Section Header

/// Header de seção reutilizando o padrão visual do HomeView (dot pink +
/// título tracking, subtítulo à direita).
private struct SectionHeader: View {
    let title: String
    let subtitle: String?

    var body: some View {
        HStack(alignment: .firstTextBaseline) {
            HStack(spacing: Theme.Space.xs) {
                Circle()
                    .fill(Theme.Colors.primary)
                    .frame(width: 6, height: 6)
                Text(title.uppercased())
                    .font(.ui(11, weight: .bold))
                    .tracking(1.5)
                    .foregroundStyle(Theme.Colors.ink)
            }

            Spacer()

            if let subtitle {
                Text(subtitle)
                    .font(.ui(11, weight: .regular))
                    .foregroundStyle(Theme.Colors.textMuted)
            }
        }
    }
}

// MARK: - Loading / Error Panels
//
// Reaproveitam o design dos panels que já existem em HomeView (silo pra
// depois extrair pra um lugar comum se aparecer em mais views). Simples
// e locais por enquanto pra não criar dependência circular na fase de rewrite.

private struct LoadingPanel: View {
    var body: some View {
        HStack {
            Spacer()
            ProgressView()
                .tint(Theme.Colors.textMuted)
            Spacer()
        }
        .padding(.vertical, Theme.Space.xxxl)
    }
}

private struct ErrorPanel: View {
    let message: String

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Space.sm) {
            Text("Couldn't load your progress")
                .font(.display(17, weight: .bold))
                .foregroundStyle(Theme.Colors.ink)
            Text(message)
                .font(.ui(13, weight: .regular))
                .foregroundStyle(Theme.Colors.textMuted)
        }
        .padding(Theme.Space.lg)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(Theme.Colors.surface)
        .clipShape(RoundedRectangle(cornerRadius: Theme.Radius.md))
        .overlay(
            RoundedRectangle(cornerRadius: Theme.Radius.md)
                .stroke(Theme.Colors.stroke, lineWidth: Theme.Stroke.normal)
        )
    }
}

#Preview {
    ProfileView()
        .environment(LibraryProgress())
        .environment(AchievementsStore())
        .environment(TranslationStore())
}
