//
//  Typography.swift
//  pedagogy
//
//  ─── TYPOGRAPHY ─────────────────────────────────────────────────────────────
//  Três famílias, três papéis distintos:
//
//    • Font.display(_:weight:) → Alfa Slab One  → capas, títulos, CTAs.
//    • Font.body(_:weight:)    → Lora serif     → texto corrido de história.
//    • Font.ui(_:weight:)      → SF Pro sistema → chips, labels pequenos.
//
//  DISPLAY = ALFA SLAB ONE (v2.2 — Sep 2026)
//
//  Voltamos ao display do DS oficial. Alfa Slab One é slab pesada — carrega
//  a estética Mignola adaptada (traço grosso, peso gráfico) que o resto do
//  sistema (sombra hard, grão) foi calibrado pra combinar. Fredoka
//  arredondada afrouxava o contraste; Alfa dá o peso que o resto pede.
//
//  UM ÚNICO PESO
//
//  Alfa Slab One só tem 1 peso (Regular) — não existem Medium/Bold/Black.
//  O parâmetro `weight:` do `Font.display()` ficou preservado por
//  compatibilidade com callsites existentes, mas é IGNORADO — sempre
//  retorna AlfaSlabOne-Regular.
//
//  Isso é fine: Alfa Slab Regular já é visualmente heavy (slab robusta). A
//  hierarquia de peso vem do TAMANHO, não da variação de weight — 44px vs
//  22px comunica mais hierarquia que Regular vs Bold na mesma família slab.
//
//  Nunca use display abaixo de 15px — o miolo grudento da slab enche.
//
//  O CORPO CONTINUA SERIF (Lora)
//
//  Serif no corpo é o que a criança de 9-11 espera (é o que vê em livro
//  impresso). Contraste display slab / body serif ajuda hierarquia visual.
//
//  4 ARQUIVOS DE LORA (não variable font)
//
//  SwiftUI aplica `weight` via UIFontDescriptor.traits, mas variable fonts
//  precisam do axis `wght` via `kCTFontVariationAttribute` — o caminho
//  `.custom(...).weight(...)` NÃO faz essa tradução. Solução: 4 arquivos
//  static, selecionados por peso.
//  ────────────────────────────────────────────────────────────────────────────

import SwiftUI

// ─── POSTSCRIPT FONT NAMES ──────────────────────────────────────────────────

private enum FontName {
    // Alfa Slab One — display (só existe 1 peso)
    static let alfaSlabOne = "AlfaSlabOne-Regular"

    // Lora — body (4 pesos)
    static let loraRegular  = "Lora-Regular"
    static let loraMedium   = "Lora-Medium"
    static let loraSemiBold = "Lora-SemiBold"
    static let loraBold     = "Lora-Bold"

    /// Lora por peso.
    static func lora(for weight: Font.Weight) -> String {
        switch weight {
        case .ultraLight, .thin, .light, .regular:
            return loraRegular
        case .medium:
            return loraMedium
        case .semibold:
            return loraSemiBold
        case .bold, .heavy, .black:
            return loraBold
        default:
            return loraRegular
        }
    }
}

// ─── TYPE SCALE ─────────────────────────────────────────────────────────────

enum TypeScale {
    static let caption:   CGFloat = 12
    static let small:     CGFloat = 14
    static let body:      CGFloat = 17
    static let bodyLg:    CGFloat = 19
    static let h3:        CGFloat = 22
    static let h2:        CGFloat = 28
    static let h1:        CGFloat = 34
    static let display:   CGFloat = 44
    static let displayXl: CGFloat = 56
}

// ─── FONT FACTORIES ─────────────────────────────────────────────────────────

extension Font {
    /// Alfa Slab One — capas, títulos, botões CTA, headers de personalidade.
    ///
    /// O parâmetro `weight:` foi preservado por compatibilidade com callsites
    /// existentes (`.font(.display(24, weight: .bold))` continua compilando)
    /// mas é IGNORADO — Alfa Slab só tem 1 peso disponível. A hierarquia
    /// visual vem do tamanho.
    ///
    /// Nunca use abaixo de 15px (o miolo grudento da slab enche).
    static func display(_ size: CGFloat,
                        weight: Font.Weight = .regular) -> Font {
        // weight ignorado — Alfa Slab só tem Regular.
        // Suprime warning "unused parameter" sem literal `_ = weight` verboso.
        _ = weight
        return .custom(FontName.alfaSlabOne, size: size)
    }

    /// Lora serif — texto de leitura. Padrão 17px regular.
    /// Pra parágrafos LONGOS, combine com `.lineSpacing(size * 0.55)`.
    static func body(_ size: CGFloat = TypeScale.body,
                     weight: Font.Weight = .regular) -> Font {
        .custom(FontName.lora(for: weight), size: size)
    }

    /// SF Pro do sistema — chips, botões pequenos, badges, labels, metadados.
    static func ui(_ size: CGFloat = TypeScale.small,
                   weight: Font.Weight = .semibold) -> Font {
        .system(size: size, weight: weight, design: .default)
    }
}

// ─── TEXT CONVENIENCE ───────────────────────────────────────────────────────

extension Text {
    /// Texto de leitura longa. Fonte Lora, line-spacing pra serif respirar,
    /// cor `textStrong`.
    func readingBody(size: CGFloat = TypeScale.body,
                     weight: Font.Weight = .regular) -> some View {
        self
            .font(.body(size, weight: weight))
            .foregroundStyle(Theme.Colors.textStrong)
            .lineSpacing(size * 0.55)
    }

    /// Título de personalidade — Alfa Slab (peso ignorado).
    func displayTitle(size: CGFloat = TypeScale.display,
                      weight: Font.Weight = .regular,
                      color: Color = Theme.Colors.ink) -> some View {
        self
            .font(.display(size, weight: weight))
            .foregroundStyle(color)
            .lineSpacing(size * 0.12)
    }

    /// Rótulo UI — chips, badges, metadados.
    func uiLabel(size: CGFloat = TypeScale.small,
                 weight: Font.Weight = .semibold,
                 color: Color = Theme.Colors.textMuted) -> some View {
        self
            .font(.ui(size, weight: weight))
            .foregroundStyle(color)
    }
}
