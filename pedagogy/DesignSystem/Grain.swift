//
//  Grain.swift
//  pedagogy
//
//  ─── GRAIN ──────────────────────────────────────────────────────────────────
//  Textura de papel Mignola implementada com Canvas (nativo, sem asset).
//
//  COMO USAR
//
//  Renderize DENTRO de cards/capas/painéis — nunca full-screen atrás de
//  conteúdo scrollável (re-render de grão por frame é desperdício de GPU sem
//  ganho visual). Padrão de composição:
//
//      ZStack {
//          RoundedRectangle(cornerRadius: Theme.Radius.lg)
//              .fill(Theme.Colors.bgSepia)
//          Grain()
//          Text("...")
//      }
//
//  FAIXA ÚTIL
//
//    opacity: 0.04–0.12
//      Abaixo de 0.04 o grão some. Acima de 0.12 polui o texto.
//      Padrão 0.08 — legibilidade preservada, textura sentida.
//
//    density: 400–1200 (número de pontos por 100pt²)
//      Menor = grão mais grosso (papel encorpado).
//      Maior = grão mais fino (papel de linho).
//      Padrão 700.
//
//  IMPLEMENTAÇÃO
//
//  Canvas do SwiftUI desenha uma matriz determinística de pontos pseudo-
//  aleatórios em cada tamanho. É determinística (seed fixo) pra não "cintilar"
//  quando o container re-renderizar. Custo: ~2ms num iPhone SE moderno pra
//  um card 400×200pt — imperceptível.
//
//  Alternativa se algum dia precisar de mais performance: substituir por um
//  Image tileable 128×128 PNG no assets e usar `.resizable(resizingMode: .tile)`.
//  Não fiz isso agora pra não adicionar asset — Canvas resolve.
//  ────────────────────────────────────────────────────────────────────────────

import SwiftUI

struct Grain: View {
    /// 0.04–0.12 (padrão 0.08). Acima disso polui a leitura.
    var opacity: Double = 0.08
    /// Cor do grão. Padrão: preto inkDeep.
    var color: Color = Palette.inkDeep
    /// Densidade de pontos por 10.000pt² (padrão 700). Menor = grão mais grosso.
    var density: Int = 700
    /// Seed determinística. Mude se quiser variar visualmente entre superfícies.
    var seed: UInt64 = 3

    var body: some View {
        Canvas { context, size in
            var rng = SeededGenerator(seed: seed)
            let area = size.width * size.height / 10_000
            let count = Int(area) * density / 100

            let dotColor = color.opacity(opacity)

            for _ in 0..<count {
                let x = Double.random(in: 0...size.width, using: &rng)
                let y = Double.random(in: 0...size.height, using: &rng)
                let r = Double.random(in: 0.3...0.7, using: &rng)

                let rect = CGRect(x: x - r, y: y - r, width: r * 2, height: r * 2)
                context.fill(Path(ellipseIn: rect), with: .color(dotColor))
            }
        }
        .allowsHitTesting(false)
    }
}

// ─── SEEDED RNG ─────────────────────────────────────────────────────────────
// Gerador determinístico (xorshift). O `Random` padrão do Swift é global e
// não aceita seed — precisa disso pra o grão ficar consistente entre frames.

private struct SeededGenerator: RandomNumberGenerator {
    private var state: UInt64

    init(seed: UInt64) {
        self.state = seed == 0 ? 0xDEAD_BEEF : seed
    }

    mutating func next() -> UInt64 {
        state ^= state << 13
        state ^= state >> 7
        state ^= state << 17
        return state
    }
}

// ─── PREVIEW ────────────────────────────────────────────────────────────────

#Preview {
    VStack(spacing: 16) {
        ForEach([0.04, 0.08, 0.12], id: \.self) { op in
            ZStack {
                RoundedRectangle(cornerRadius: Theme.Radius.md)
                    .fill(Theme.Colors.bgSepia)
                Grain(opacity: op)
                VStack {
                    Spacer()
                    Text("opacity \(op, specifier: "%.2f")")
                        .uiLabel(color: Theme.Colors.ink)
                        .padding(Theme.Space.md)
                }
            }
            .frame(height: 110)
        }
    }
    .padding()
    .background(Theme.Colors.bg)
}
