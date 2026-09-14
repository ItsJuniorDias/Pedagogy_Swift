//
//  Shadow.swift
//  pedagogy
//
//  ─── SHADOWS ────────────────────────────────────────────────────────────────
//  Dois idiomas convivem porque servem propósitos diferentes:
//
//    • `.cardShadow()` / `.raisedShadow()` — sombras suaves. Cards de lista,
//      chips, botões neutros, modais. Mantém a sensação amigável nas telas
//      de navegação. Não carrega personalidade — é neutra por design.
//
//    • `.hardShadow()` / `.hardShadowSmall()` — offset SEM blur, tipo painel
//      de HQ. **É a assinatura visual do app.** Use em capas de história,
//      botões CTA grandes (primários, não secundários), headers de destaque.
//
//    • `.glowPrimary()` — brilho colorido rosa. Serve à
//      conversão do paywall e ao charme dos CTAs de banner.
//
//  IMPLEMENTAÇÃO
//
//  SwiftUI não tem sombra offset-sem-blur nativa igual `shadowRadius: 0` do
//  UIKit/RN. `.shadow(radius: 0)` renderiza NADA. A solução: desenhar um
//  retângulo escuro atrás do conteúdo, deslocado — é isso que o Mignola-hard
//  faz visualmente (é literalmente uma cópia do shape em preto atrás).
//
//  REGRA DE COMPOSIÇÃO
//
//  **Nunca misture card e hard na mesma peça.** Escolha um idioma por
//  elemento. Um card com sombra suave + botão dentro dele com sombra hard,
//  tudo bem. Um card com as duas sombras uma em cima da outra, nunca —
//  vira ruído visual.
//  ────────────────────────────────────────────────────────────────────────────

import SwiftUI

extension View {
    // ─── Suave — card em repouso ──
    func cardShadow() -> some View {
        self.shadow(
            color: Palette.inkDeep.opacity(0.08),
            radius: 8,
            x: 0,
            y: 3
        )
    }

    // ─── Suave — elemento flutuante (modal, header sobre conteúdo) ──
    func raisedShadow() -> some View {
        self.shadow(
            color: Palette.inkDeep.opacity(0.14),
            radius: 16,
            x: 0,
            y: 8
        )
    }

    // ─── Mignola-hard — offset sem blur, tipo painel de HQ ──
    // Requer `shape` porque o offset é um clone do shape atrás. Sem o shape
    // não dá pra saber o contorno da peça.
    func hardShadow<S: Shape>(_ shape: S,
                              offset: CGSize = CGSize(width: 3, height: 4),
                              color: Color = Palette.inkDeep) -> some View {
        self.background(
            shape
                .fill(color)
                .offset(offset)
        )
    }

    /// Variante compacta pra botões e chips pequenos.
    func hardShadowSmall<S: Shape>(_ shape: S,
                                   color: Color = Palette.inkDeep) -> some View {
        hardShadow(shape,
                   offset: CGSize(width: 2, height: 2),
                   color: color)
    }

    // ─── Brilho colorido — CTAs, banners ──
    func glowPrimary() -> some View {
        self.shadow(
            color: Palette.pink.opacity(0.35),
            radius: 14,
            x: 0,
            y: 6
        )
    }
}
