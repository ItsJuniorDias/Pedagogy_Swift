//
//  Achievement.swift
//  pedagogy
//
//  ─── ACHIEVEMENT MODEL ──────────────────────────────────────────────────────
//  Definição de cada "marcador de leitura" (não gamificação — ver README do
//  módulo Profile).
//
//  DESIGN
//
//  Não é enum discriminado com valores diferentes por caso. Cada achievement
//  é uma instância de `Achievement` com closures pra `progress` e `isUnlocked`.
//  Isso permite adicionar novos achievements sem editar mais que um lugar
//  (aqui) e sem tocar em nenhum switch statement.
//
//  IDENTIFICAÇÃO
//
//  `AchievementID` é enum String pra ser Codable estável (UserDefaults) e
//  determinístico independente da ordem em que aparecem na lista. Se um dia
//  remover um achievement, o UserDefaults só ignora IDs desconhecidos —
//  progresso do usuário não quebra.
//
//  ADIÇÃO DE NOVO ACHIEVEMENT
//
//  1. Adicione um case novo em `AchievementID`
//  2. Adicione uma entrada em `Achievement.all`
//  3. Não precisa mais nada — ProfileView e AchievementsStore descobrem
//     automaticamente
//  ────────────────────────────────────────────────────────────────────────────

import Foundation

// MARK: - AchievementID

/// Identificador estável de cada achievement. Codable pra UserDefaults.
/// Não renomeie um case existente sem plano de migração — o valor bruto
/// vira a chave persistida.
enum AchievementID: String, CaseIterable, Codable, Hashable {
    // Reading milestones
    case firstSentence
    case firstStory
    case fiveStories
    case halfwayThere
    case theWholeShelf

    // Streaks
    case oneWeek
    case oneMonth
    case aHundredDays

    // Category completion
    case everyMystery
    case everyAdventure
    case everyWonder

    // Cross-cutting
    case aCuriousMind

    /// Nome do imageset da ilustração do achievement, gerada por
    /// `scripts/generate_achievements.py`. Converte `firstSentence` →
    /// `first-sentence` e prefixa/sufixa pro formato de asset name.
    ///
    /// Se a imagem não existe no bundle, `AchievementCard` degrada
    /// graciosamente pro layout tipográfico anterior — permite rodar o
    /// app antes de gerar as artes.
    var iconAssetName: String {
        "achievement-\(kebabCased(rawValue))-icon"
    }
}

/// "firstSentence" → "first-sentence". Insere hífen antes de cada uppercase
/// que não seja a primeira letra. Sem dependência externa (Foundation
/// tem Locale-dependent behavior que evitamos aqui).
private func kebabCased(_ s: String) -> String {
    var out = ""
    for (i, ch) in s.enumerated() {
        if i > 0 && ch.isUppercase {
            out.append("-")
        }
        out.append(ch.lowercased())
    }
    return out
}

// MARK: - Achievement

/// Um achievement com título editorial, requirement checker, e progress
/// opcional. As closures recebem `LibraryProgress` + `stories: [Story]`
/// porque alguns requirements dependem do catálogo total (ex: "every
/// mystery" precisa saber quantas mysteries existem, não hardcodar 10).
struct Achievement: Identifiable {
    let id: AchievementID
    /// Título curto exibido no card. Máx ~24 chars pra caber em 1 linha.
    let title: String
    /// Frase descrevendo o que fazer pra unlockear. Aparece quando locked.
    /// Escrita imperativa curta.
    let requirement: String

    /// Retorna `true` se o requirement está satisfeito no estado atual.
    let isUnlocked: (LibraryProgress, [Story]) -> Bool

    /// Progresso corrente rumo ao unlock. Retorna nil quando o achievement
    /// é binário (ex: "First story" — ou você fez ou não). Retorna
    /// (current, target) pra achievements com contagem (ex: 6/10 mysteries).
    /// Usado pra hint discreto no card ("6/10") — não é barra de progresso.
    let progress: (LibraryProgress, [Story]) -> (Int, Int)?

    // MARK: - The list

    static var all: [Achievement] {
        [
            // ─── Reading milestones ────────────────────────────────
            Achievement(
                id: .firstSentence,
                title: "First sentence",
                requirement: "Open your first chapter",
                isUnlocked: { library, _ in
                    library.stories.values.contains { $0.lastReadAt != nil }
                },
                progress: { _, _ in nil }
            ),
            Achievement(
                id: .firstStory,
                title: "First story",
                requirement: "Finish your first story",
                isUnlocked: { library, _ in
                    library.stories.values.contains { $0.isFinished }
                },
                progress: { _, _ in nil }
            ),
            Achievement(
                id: .fiveStories,
                title: "Five stories",
                requirement: "Finish 5 stories",
                isUnlocked: { library, _ in finishedCount(library) >= 5 },
                progress: { library, _ in (min(finishedCount(library), 5), 5) }
            ),
            Achievement(
                id: .halfwayThere,
                title: "Halfway there",
                requirement: "Finish 25 stories",
                isUnlocked: { library, _ in finishedCount(library) >= 25 },
                progress: { library, _ in (min(finishedCount(library), 25), 25) }
            ),
            Achievement(
                id: .theWholeShelf,
                title: "The whole shelf",
                requirement: "Finish every story",
                isUnlocked: { library, stories in
                    finishedCount(library) >= stories.count && !stories.isEmpty
                },
                progress: { library, stories in
                    (min(finishedCount(library), stories.count), stories.count)
                }
            ),

            // ─── Streaks ───────────────────────────────────────────
            Achievement(
                id: .oneWeek,
                title: "One week",
                requirement: "Read seven days in a row",
                isUnlocked: { library, _ in library.streak.currentStreak >= 7 },
                progress: { library, _ in (min(library.streak.currentStreak, 7), 7) }
            ),
            Achievement(
                id: .oneMonth,
                title: "One month",
                requirement: "Read thirty days in a row",
                isUnlocked: { library, _ in library.streak.currentStreak >= 30 },
                progress: { library, _ in (min(library.streak.currentStreak, 30), 30) }
            ),
            Achievement(
                id: .aHundredDays,
                title: "A hundred days",
                requirement: "Read a hundred days in a row",
                isUnlocked: { library, _ in library.streak.currentStreak >= 100 },
                progress: { library, _ in (min(library.streak.currentStreak, 100), 100) }
            ),

            // ─── Category completion ───────────────────────────────
            categoryAchievement(
                id: .everyMystery,
                title: "Every mystery",
                requirement: "Finish every mystery",
                category: .mystery
            ),
            categoryAchievement(
                id: .everyAdventure,
                title: "Every adventure",
                requirement: "Finish every adventure",
                category: .adventure
            ),
            categoryAchievement(
                id: .everyWonder,
                title: "Every wonder",
                requirement: "Finish every wonder",
                category: .wonder
            ),

            // ─── Cross-cutting ─────────────────────────────────────
            Achievement(
                id: .aCuriousMind,
                title: "A curious mind",
                requirement: "Finish one story of each category",
                isUnlocked: { library, stories in
                    let finished = finishedStories(library, stories)
                    let coveredCategories = Set(finished.map(\.category))
                    return coveredCategories.count == StoryCategory.allCases.count
                },
                progress: { library, stories in
                    let finished = finishedStories(library, stories)
                    let coveredCategories = Set(finished.map(\.category))
                    return (coveredCategories.count, StoryCategory.allCases.count)
                }
            ),
        ]
    }

    /// Helper pra achievements de "finish every X". Extraído porque todas
    /// as categorias seguem o mesmo shape.
    private static func categoryAchievement(
        id: AchievementID,
        title: String,
        requirement: String,
        category: StoryCategory
    ) -> Achievement {
        Achievement(
            id: id,
            title: title,
            requirement: requirement,
            isUnlocked: { library, stories in
                let inCat = stories.filter { $0.category == category }
                guard !inCat.isEmpty else { return false }
                return inCat.allSatisfy { library.progress(for: $0.id).isFinished }
            },
            progress: { library, stories in
                let inCat = stories.filter { $0.category == category }
                let finished = inCat.filter { library.progress(for: $0.id).isFinished }
                return (finished.count, inCat.count)
            }
        )
    }
}

// MARK: - Small helpers usados por múltiplas closures acima

private func finishedCount(_ library: LibraryProgress) -> Int {
    library.stories.values.filter(\.isFinished).count
}

private func finishedStories(_ library: LibraryProgress, _ stories: [Story]) -> [Story] {
    stories.filter { library.progress(for: $0.id).isFinished }
}
