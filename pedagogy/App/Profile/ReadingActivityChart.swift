//
//  ReadingActivityChart.swift
//  pedagogy
//
//  ─── READING ACTIVITY CHART ─────────────────────────────────────────────────
//  Bar chart de 7 barras mostrando o pattern semanal de leitura do usuário:
//  em que dia da semana ele lê mais, considerando os últimos 90 dias.
//
//  DADOS
//
//  Consome `ReadingLog.countsByWeekday()` do LibraryProgress. Cada barra é
//  um weekday no locale do usuário (a ordem começa em `Calendar.firstWeekday`,
//  então usuários brasileiros veem D-S-T-Q-Q-S-S ou similar dependendo do
//  locale do device).
//
//  DESIGN
//
//  • Barra do "top weekday" (único vencedor) fica em pink #FF5B8D.
//  • Outras barras em cinza discreto (Theme.Colors.textMuted @ 40%).
//  • Se houver empate no topo ou sem dados, todas em cinza (neutro).
//  • Eixo Y escondido (números específicos não importam; o que importa é
//    a forma da distribuição).
//  • Labels do eixo X: veryShortWeekdaySymbols do locale ("S", "M", "T"...).
//  • Título editorial "When you read" + subtítulo contextual embaixo.
//
//  EMPTY STATES
//
//  • 0 sessões: card mostra placeholder "A picture will grow here."
//  • 1-4 sessões: chart real + subtitle "Just getting started."
//  • 5+ sessões com winner claro: subtitle "You read most on {day}."
//  • 5+ sessões empatadas no topo: subtitle "Reading spread across the week."
//
//  Threshold 5 é arbitrário mas pragmático: menos que isso, o "top" é ruído.
//
//  POR QUE SWIFT CHARTS
//
//  Framework nativo iOS 16+ (o app já é iOS 17+ por causa de @Observable).
//  Zero dependência externa. Anima transições automaticamente. Suporta dark
//  mode. Acessibilidade via VoiceOver embutida (cada BarMark vira elemento
//  acessível descrevendo dia + valor).
//  ────────────────────────────────────────────────────────────────────────────

import SwiftUI
import Charts

// MARK: - Data point

/// Ponto do chart: um weekday + contagem. Identifiable pra ForEach do Chart.
private struct WeekdayCount: Identifiable {
    let id: Int          // weekday number (1-7, Calendar convention)
    let label: String    // "S" / "M" / etc — locale-aware
    let count: Int
    let isTop: Bool      // true se é o único top-weekday (highlight em pink)
}

// MARK: - The view

struct ReadingActivityChart: View {
    let log: ReadingLog

    /// Threshold acima do qual o chart mostra "You read most on X" com
    /// confiança. Abaixo disso, mostra subtitle mais suave. Constante local
    /// porque só o chart usa.
    private static let insightThreshold = 5

    // MARK: - Derived data

    private var totalSessions: Int { log.sessions.count }
    private var topWeekday: Int? { log.mostFrequentWeekday() }

    /// Data points na ORDEM de exibição do locale. Se o Calendar diz que
    /// firstWeekday=1 (domingo), começa em domingo; se firstWeekday=2
    /// (segunda), começa em segunda. Aplica ao label e à ordem visual.
    private var dataPoints: [WeekdayCount] {
        let cal = Calendar.current
        let counts = log.countsByWeekday()
        let symbols = cal.veryShortWeekdaySymbols   // ["S", "M", "T", "W", "T", "F", "S"]
        let firstWeekday = cal.firstWeekday          // 1 = Sunday, 2 = Monday

        return (0..<7).map { offset in
            // weekday number (1-7) shifted pelo firstWeekday do locale
            let weekday = ((firstWeekday - 1 + offset) % 7) + 1
            let symbolIndex = weekday - 1
            return WeekdayCount(
                id: weekday,
                label: symbols[symbolIndex],
                count: counts[weekday, default: 0],
                isTop: weekday == topWeekday
            )
        }
    }

    // MARK: - Body

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Space.md) {
            // Header
            VStack(alignment: .leading, spacing: 4) {
                Text("When you read")
                    .font(.display(18, weight: .bold))
                    .foregroundStyle(Theme.Colors.ink)

                Text(subtitle)
                    .font(.ui(12, weight: .regular))
                    .foregroundStyle(Theme.Colors.textMuted)
            }

            // Chart or empty placeholder
            if totalSessions == 0 {
                EmptyChartPlaceholder()
            } else {
                chartView
            }
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

    // MARK: - Chart

    private var chartView: some View {
        Chart(dataPoints) { point in
            BarMark(
                x: .value("Day", point.label),
                y: .value("Sessions", point.count),
                width: .ratio(0.65)
            )
            .foregroundStyle(
                point.isTop
                    ? Theme.Colors.primary
                    : Theme.Colors.textMuted.opacity(0.35)
            )
            .cornerRadius(4)
        }
        .chartYAxis(.hidden)
        .chartXAxis {
            AxisMarks(values: .automatic) { _ in
                AxisValueLabel()
                    .font(.system(size: 11, weight: .semibold))
                    .foregroundStyle(Theme.Colors.textMuted)
            }
        }
        .chartPlotStyle { plotArea in
            plotArea
                .background(Color.clear)
        }
        .frame(height: 140)
        // Preserva ordem do dataPoints (sem alfabetizar labels dos dias)
        .chartXScale(domain: dataPoints.map(\.label))
    }

    // MARK: - Subtitle

    /// Texto contextual embaixo do título. Varia por quantidade de dados
    /// e clareza do padrão. Tom quiet-Ghibli — observacional, não motivacional.
    private var subtitle: String {
        if totalSessions == 0 {
            return "A picture will grow here."
        }
        if totalSessions < Self.insightThreshold {
            return "Just getting started."
        }
        guard let top = topWeekday else {
            return "Reading spread across the week."
        }
        let weekdayName = Calendar.current.standaloneWeekdaySymbols[top - 1]
        return "You read most on \(weekdayName)s."
    }
}

// MARK: - Empty state

/// Mostrado quando o log está vazio. Não é um placeholder cinza feio — é
/// uma composição sutil com 7 barras "fantasma" muito claras, sugerindo
/// o que vai aparecer aqui. Reforça a mensagem do subtitle sem gritar.
private struct EmptyChartPlaceholder: View {
    var body: some View {
        HStack(alignment: .bottom, spacing: 12) {
            ForEach(0..<7, id: \.self) { i in
                RoundedRectangle(cornerRadius: 3)
                    .fill(Theme.Colors.textMuted.opacity(0.15))
                    // Alturas variadas pra dar sensação de "curva possível"
                    // sem prometer nada específico. Padrão determinístico
                    // (não random) pra não mudar entre renders.
                    .frame(height: [30, 55, 40, 70, 45, 80, 25][i])
            }
        }
        .frame(height: 140)
        .frame(maxWidth: .infinity)
    }
}

// MARK: - Preview

#Preview("Empty") {
    ReadingActivityChart(log: ReadingLog())
        .padding()
        .background(Theme.Colors.bg)
}

#Preview("Just started (3 sessions)") {
    let cal = Calendar.current
    let now = Date()
    var log = ReadingLog()
    log.sessions = [
        cal.date(byAdding: .day, value: -1, to: now)!,
        cal.date(byAdding: .day, value: -3, to: now)!,
        cal.date(byAdding: .day, value: -5, to: now)!,
    ]
    return ReadingActivityChart(log: log)
        .padding()
        .background(Theme.Colors.bg)
}

#Preview("Clear winner (Sundays)") {
    let cal = Calendar.current
    let now = Date()
    var log = ReadingLog()
    // Simula 12 semanas com leituras concentradas em domingos + algumas
    // outras aleatórias durante a semana
    for weeksAgo in 0..<12 {
        // Sunday of that week
        if let sunday = cal.date(byAdding: .day, value: -weeksAgo * 7, to: now) {
            log.sessions.append(sunday)
        }
    }
    // Umas terças e quintas espalhadas
    for daysAgo in [4, 11, 18, 32, 46, 60] {
        if let d = cal.date(byAdding: .day, value: -daysAgo, to: now) {
            log.sessions.append(d)
        }
    }
    return ReadingActivityChart(log: log)
        .padding()
        .background(Theme.Colors.bg)
}
