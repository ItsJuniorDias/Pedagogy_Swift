//
//  Story.swift
//  pedagogy
//
//  ─── STORY MODEL ────────────────────────────────────────────────────────────
//  Estrutura de uma história.
//
//  DECISÕES DE SCHEMA
//
//  1. Página é struct simples com `image` opcional (não enum discriminado).
//     O reader pode decidir layout com `if page.image != nil`. Menos código
//     Codable pra manter, e o ganho de type safety do enum não compensa aqui.
//
//  2. Convenção rígida: TODA história tem 3 capítulos, os capítulos 1 e 2
//     terminam em cliffhanger. Isso não é enforcado no schema (chapters é
//     `[Chapter]` livre) mas é norma editorial.
//
//  3. Progresso salvo por chapter index (reader agrupa cada chapter como
//     uma unidade única de leitura). `pageIndex` fica no schema pra futuro
//     mas o reader não usa.
//
//  4. Ilustrações são referenciadas por nome de arquivo. Se a imagem não
//     existe no bundle, o reader/card mostra placeholder — permite dev sem
//     arte pronta.
//
//  5. `imagePrompt` fica gravado no JSON mesmo depois da arte pronta.
//     Facilita regenerar num estilo diferente sem reescrever o JSON.
//
//  6. Category = agrupamento narrativo (Mystery, Adventure, Wonder, Journey,
//     Legend). Fica como badge no card e permite futura filtragem/organização.
//
//  REMOVIDO NA v2.1 (paleta minimal)
//
//  O campo `theme` (StoryTheme com pink/purple/yellow/green/blue) foi
//  removido. Cada história não tem mais uma "cor de chrome" própria — o
//  chrome é neutro em todo o app. A personalidade visual de cada história
//  vem da cover art, não de uma cor arbitrária atribuída ao card.
//  ────────────────────────────────────────────────────────────────────────────

import SwiftUI

// MARK: - Story

struct Story: Codable, Identifiable, Hashable {
    /// Slug único. Bate com o filename: "house-of-clocks" → house-of-clocks.json
    let id: String

    let title: String
    let subtitle: String?
    let author: String?
    let summary: String
    let readingTimeMinutes: Int

    let coverImage: String?
    let coverImagePrompt: String?

    /// Agrupamento narrativo — permite badge no card e futura filtragem.
    /// Cada história pertence a exatamente uma categoria.
    let category: StoryCategory

    /// Se true, requer assinatura ativa (`Store.isPremium`) pra abrir o
    /// reader. A primeira história costuma ser free pra atrair.
    let isPremium: Bool

    /// Data em que a história foi publicada. Usada pra "This week" na Home
    /// (a história com publishedAt mais recente nos últimos 7 dias).
    /// Opcional: JSONs antigos sem esse campo simplesmente não aparecem
    /// como "this week" — nada quebra.
    /// Formato JSON: "2026-09-03" (ISO 8601 date-only).
    let publishedAt: Date?

    /// Se true, aparece no carousel "Featured picks" da Home. Rotação
    /// editorial manual — você edita nos JSONs quando quer trocar os
    /// destaques (recomendação: mensal). Máximo 3 exibidos por vez.
    /// Opcional: JSONs sem esse campo tratam como false.
    let isFeatured: Bool?

    let chapters: [Chapter]

    /// Total de páginas somando todos os capítulos. Usado pra metadata.
    var totalPages: Int {
        chapters.reduce(0) { $0 + $1.pages.count }
    }

    /// Se a história pode ser aberta SEM assinatura ativa.
    ///
    /// Regra:
    ///   • Não-premium (`isPremium == false`) → sempre free
    ///   • Premium mas é a "story of the week" (publishedAt nos últimos 7
    ///     dias) → free por 7 dias, funciona como amostra grátis semanal
    ///   • Premium fora da janela semanal → requer assinatura
    ///
    /// Usada em toda checagem de gate (StoryDetail CTA, badges no card, etc)
    /// pra manter a regra em um lugar só. Nunca chame `isPremium` direto
    /// pra decidir acesso — use este método.
    ///
    /// `now` injetável só pra testes; produção sempre passa `.now`.
    func isFreeToRead(now: Date = .now) -> Bool {
        if !isPremium { return true }
        guard let pub = publishedAt else { return false }
        let sevenDaysAgo = Calendar.current.date(byAdding: .day, value: -7, to: now) ?? now
        return pub >= sevenDaysAgo && pub <= now
    }
}

// MARK: - Chapter

struct Chapter: Codable, Identifiable, Hashable {
    var id: Int { number }

    /// 1-indexed pra bater com a mental model do usuário ("Chapter 1").
    let number: Int
    let title: String

    let openerImage: String?
    let openerPrompt: String?

    let pages: [Page]
}

// MARK: - Page

struct Page: Codable, Hashable {
    /// Cada string é um parágrafo. Reader concatena todos os paragraphs de
    /// todas as pages do chapter em fluxo único.
    let paragraphs: [String]

    let image: String?
    let imagePrompt: String?

    var hasIllustration: Bool { image != nil }
}

// MARK: - StoryCategory

/// Agrupamento narrativo. Aparece como badge preto discreto no card.
/// Ordem definida por `displayOrder` (usada em futuras views de filtro).
enum StoryCategory: String, Codable, Hashable, CaseIterable {
    case mystery
    case adventure
    case wonder
    case journey
    case legend

    /// Nome exibido em headers de seção (quando/se voltarem). Plural
    /// evocativo.
    var displayName: String {
        switch self {
        case .mystery:   return "Mysteries"
        case .adventure: return "Adventures"
        case .wonder:    return "Wonders"
        case .journey:   return "Journeys"
        case .legend:    return "Legends"
        }
    }

    /// Nome no singular pra badge no card, small caps.
    var badgeName: String {
        switch self {
        case .mystery:   return "MYSTERY"
        case .adventure: return "ADVENTURE"
        case .wonder:    return "WONDER"
        case .journey:   return "JOURNEY"
        case .legend:    return "LEGEND"
        }
    }

    /// Descrição curta — voice da categoria. Preservada pra uso futuro
    /// (por exemplo, tela de exploração por categoria).
    var tagline: String {
        switch self {
        case .mystery:   return "Things that don't quite add up"
        case .adventure: return "Getting there is half the story"
        case .wonder:    return "The world is stranger than it looks"
        case .journey:   return "You're not the same when you come back"
        case .legend:    return "Stories older than memory"
        }
    }

    /// Ordem de exibição (menor = primeiro). Usada quando/se voltarmos a
    /// agrupar histórias por categoria.
    var displayOrder: Int {
        switch self {
        case .mystery:   return 0
        case .adventure: return 1
        case .wonder:    return 2
        case .journey:   return 3
        case .legend:    return 4
        }
    }
}
