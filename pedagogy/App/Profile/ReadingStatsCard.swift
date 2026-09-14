//
//  ReadingStatsCard.swift
//  pedagogy
//
//  ─── READING STATS CARD ─────────────────────────────────────────────────────
//  Card destacado no topo do ProfileView com os 3 números que importam:
//
//    • Current streak (flame icon)
//    • Stories finished (livro fechado icon)
//    • Total reading time estimado (relógio)
//
//  DESIGN
//
//  Layout horizontal em 3 colunas, dividers verticais entre elas. Cada
//  coluna: número grande em display font, label pequena em small caps.
//
//  Cream surface com stroke Mignola. Sem cor de acento nos números
//  (mantém a paleta minimal) — a única cor viva na tela vem dos pink
//  dots dos achievements unlockeds abaixo.
//
//  TEMPO DE LEITURA
//
//  Estimado: cada story finished conta como `readingTimeMinutes` da story
//  (default 15). Não é exato — não medimos tempo real de leitura porque
//  isso exigiria tracking de session que não temos hoje. É suficiente pra
//  passar a sensação de "quanto de tempo eu já investi aqui".
//  ────────────────────────────────────────────────────────────────────────────

import SwiftUI

struct ReadingStatsCard: View {
    let streakDays: Int
    let storiesFinished: Int
    let totalMinutes: Int

    var body: some View {
        HStack(spacing: 0) {
            StatColumn(
                value: "\(streakDays)",
                label: streakDays == 1 ? "DAY STREAK" : "DAY STREAK",
                sublabel: streakDays == 0 ? "start today" : nil
            )

            Divider()
                .frame(width: 1)
                .overlay(Theme.Colors.border)
                .padding(.vertical, Theme.Space.md)

            StatColumn(
                value: "\(storiesFinished)",
                label: storiesFinished == 1 ? "STORY" : "STORIES",
                sublabel: "finished"
            )

            Divider()
                .frame(width: 1)
                .overlay(Theme.Colors.border)
                .padding(.vertical, Theme.Space.md)

            StatColumn(
                value: formatTime(totalMinutes),
                label: totalMinutes >= 60 ? "READ" : "MINUTES",
                sublabel: totalMinutes >= 60 ? nil : "read"
            )
        }
        .padding(.vertical, Theme.Space.xl)
        .frame(maxWidth: .infinity)
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

    /// "23m" pra < 1h, "4h" pra >= 1h e < 1 dia, "2d" pra >= 24h. Sempre
    /// curto pra não quebrar o layout do card. Menos preciso mas mais legível.
    private func formatTime(_ minutes: Int) -> String {
        if minutes < 60 { return "\(minutes)" }
        let hours = minutes / 60
        if hours < 24 { return "\(hours)h" }
        return "\(hours / 24)d"
    }
}

// MARK: - StatColumn (interna)

private struct StatColumn: View {
    let value: String
    let label: String
    let sublabel: String?

    var body: some View {
        VStack(spacing: 4) {
            Text(value)
                .font(.display(34, weight: .bold))
                .foregroundStyle(Theme.Colors.ink)
                .lineLimit(1)
                .minimumScaleFactor(0.6)

            Text(label)
                .font(.ui(10, weight: .bold))
                .tracking(1.0)
                .foregroundStyle(Theme.Colors.textMuted)

            if let sublabel {
                Text(sublabel)
                    .font(.ui(10, weight: .regular))
                    .foregroundStyle(Theme.Colors.textMuted)
            } else {
                // Reserva espaço vertical pra colunas não desalinharem
                // quando alguns têm sublabel e outros não.
                Color.clear.frame(height: 12)
            }
        }
        .frame(maxWidth: .infinity)
    }
}
