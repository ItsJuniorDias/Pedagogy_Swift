//
//  Theme.swift
//  pedagogy
//
//  ─── DESIGN SYSTEM · Pedagogy v2.1 ──────────────────────────────────────────
//  Fonte única de verdade: tokens (cores, raios, espaço, traço).
//  Nenhuma view hardcoda hex — importe daqui.
//
//  DIREÇÃO ESTÉTICA
//
//  App infantil de leitura para 9–11 anos com estética Mignola/BPRD adaptada.
//  Blocos de sombra chapada, silhuetas com peso, grão de papel, cantos menos
//  arredondados que a versão bubbly anterior.
//
//  PALETA MINIMAL (v2.1 — refactor Sep 2026)
//
//  UMA cor de marca: rosa `#FF5B8D`. Todo o resto é neutro (creme, sépia,
//  cinza, preto). Vermelho reservado pra erro real (raro).
//
//  Removidos nessa versão: roxo, amarelo, verde, azul como tokens de chrome.
//  A cor entra na COVER ART das histórias — cada história tem sua paleta
//  visual própria na ilustração. O chrome (headers, cards, badges, CTAs)
//  não compete com a arte.
//
//  A estética não vem da paleta, vem da TIPOGRAFIA (Typography.swift), do
//  TRAÇO Mignola e das SOMBRAS hard (Shadow.swift).
//  ────────────────────────────────────────────────────────────────────────────

import SwiftUI

// ─── RAW PALETTE ────────────────────────────────────────────────────────────
// Matéria-prima. NÃO usar direto no chrome de tela — sempre passe por
// `Theme.Colors.*`. Só existem 3 famílias: neutros, rosa (marca), vermelho
// (erro). Menos que isso, o design vira mono; mais que isso, volta ao ruído
// visual da v2.0.

enum Palette {
    // ── Neutros ──
    // `inkDeep` é o preto verdadeiro que Mignola precisa em outlines e
    // sombras chapadas. `ink` fica pra títulos e texto principal (levemente
    // mais claro pra reduzir fadiga em leituras longas).
    static let inkDeep    = Color(hex: 0x0F0F0F)
    static let ink        = Color(hex: 0x1A1A1A)
    static let mutedInk   = Color(hex: 0x4A4A4A)
    static let softInk    = Color(hex: 0x6E6E78)
    static let faintInk   = Color(hex: 0x8E8E99)

    static let paper       = Color(hex: 0xFFF9F0)  // creme padrão
    static let paperSepia  = Color(hex: 0xF4E9D3)  // creme aged, capa "livro"
    static let surface     = Color(hex: 0xFFFFFF)
    static let surfaceElev = Color(hex: 0xFFFEFB)
    static let bone        = Color(hex: 0xECE8E0)  // bordas neutras quentes
    static let track       = Color(hex: 0xF1EEE8)  // trilho de progresso

    // ── Rosa (marca — ÚNICA cor de destaque) ──
    static let pink      = Color(hex: 0xFF5B8D)
    static let pinkDeep  = Color(hex: 0xE13B70)
    static let pinkSoft  = Color(hex: 0xFFB6CC)
    static let pinkTint  = Color(hex: 0xFFE3ED)
    static let pinkFaint = Color(hex: 0xFFF0F6)

    // ── Vermelho (erro/alerta — uso <1%, quase invisível na maioria dos
    // fluxos, mas existe pra casos onde precisa realmente comunicar erro) ──
    static let red      = Color(hex: 0xEF4444)
    static let redDeep  = Color(hex: 0xB91C1C)
    static let redTint  = Color(hex: 0xFEE2E2)
}

// ─── SEMANTIC TOKENS ────────────────────────────────────────────────────────

enum Theme {
    enum Colors {
        // ── Superfícies ──
        static let bg          = Palette.paper       // fundo padrão das telas
        static let bgSepia     = Palette.paperSepia  // fundo de capa de história
        static let surface     = Palette.surface     // cards, sheets, botões neutros
        static let surfaceElev = Palette.surfaceElev // superfície levemente destacada

        // ── Texto ──
        // Body de leitura: `textStrong` — corpo generoso e contraste alto
        // porque a criança vai ler 1500–2200 palavras. `textMuted` é o mínimo
        // pra corpo pequeno (secondary). `textFaint` só rótulos ≥13 e bold.
        static let ink        = Palette.ink
        static let inkDeep    = Palette.inkDeep
        static let textStrong = Palette.mutedInk
        static let textMuted  = Palette.softInk
        static let textFaint  = Palette.faintInk
        static let onAccent   = Color.white          // texto sobre rosa
        static let onInk      = Palette.paper        // texto sobre preto (streak inverted, etc)

        // ── Marca (rosa) ──
        // Único destaque colorido no app inteiro. Reservado pra:
        //   • CTA primário (Start reading, Continue, Subscribe)
        //   • Featured hero da Home (fundo sutil rosa)
        //   • Estado "selected" em cards de plano do paywall
        static let primary      = Palette.pink
        static let primaryDeep  = Palette.pinkDeep
        static let primarySoft  = Palette.pinkSoft
        static let primaryTint  = Palette.pinkTint
        static let primaryFaint = Palette.pinkFaint

        // ── Feedback ──
        // Vermelho é o único caso onde uma cor não-rosa aparece no chrome.
        // Reservado exclusivamente pra estado de erro real (validação
        // falhou, API deu 500, etc). Usar com parcimônia — se aparece com
        // frequência, é problema de UX, não de design.
        static let danger      = Palette.red
        static let dangerTint  = Palette.redTint

        // ── Estrutura ──
        static let border       = Palette.bone       // bordas neutras quentes
        static let borderStrong = Palette.mutedInk   // separador de peso
        static let stroke       = Palette.inkDeep    // traço Mignola-hard (outlines)
        static let track        = Palette.track      // trilho de barra de progresso
        static let overlay      = Color(hex: 0x0F0F0F).opacity(0.55) // backdrop de modais
    }

    // ─── Raios ──
    enum Radius {
        static let sharp: CGFloat = 0
        static let xs:    CGFloat = 4
        static let sm:    CGFloat = 8
        static let md:    CGFloat = 12
        static let lg:    CGFloat = 16
        static let xl:    CGFloat = 20
        static let xxl:   CGFloat = 24
        static let pill:  CGFloat = 999
    }

    // ─── Espaço (grade 4pt) ──
    enum Space {
        static let xs:   CGFloat = 4
        static let sm:   CGFloat = 8
        static let md:   CGFloat = 12
        static let lg:   CGFloat = 16
        static let xl:   CGFloat = 20
        static let xxl:  CGFloat = 24
        static let xxxl: CGFloat = 32
        static let huge: CGFloat = 40
    }

    // ─── Peso de traço ──
    enum Stroke {
        static let hair:   CGFloat = 1
        static let thin:   CGFloat = 1.5
        static let normal: CGFloat = 2
        static let thick:  CGFloat = 3
    }
}

// ─── TOUCH & A11Y ───────────────────────────────────────────────────────────
enum Touch {
    static let min: CGFloat = 44
}

// ─── Color(hex:) ────────────────────────────────────────────────────────────

extension Color {
    init(hex: UInt32, alpha: Double = 1) {
        let r = Double((hex >> 16) & 0xFF) / 255
        let g = Double((hex >>  8) & 0xFF) / 255
        let b = Double( hex        & 0xFF) / 255
        self.init(.sRGB, red: r, green: g, blue: b, opacity: alpha)
    }
}
