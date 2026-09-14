//
//  ReadingProgress.swift
//  pedagogy
//
//  ─── READING PROGRESS ───────────────────────────────────────────────────────
//  Persistência do progresso do usuário: última página lida por história,
//  streak diária, timestamp de última leitura.
//
//  ONDE PERSISTE
//
//  UserDefaults, chave "pedagogy.library-progress.v1". A escolha:
//    • Não usa SwiftData porque o volume é pequeno (dezenas de bytes por
//      história, 1 registro global de streak). SwiftData adicionaria uma
//      dependência de schema migration desnecessária pra esse volume.
//    • Não usa @AppStorage porque @Observable + @AppStorage têm interação
//      esquisita (o wrapper é feito pra ser property wrapper em View).
//      Encapsular em UserDefaults direto é mais previsível.
//
//  Se um dia o volume crescer (sync entre devices, backup na nuvem, histórico
//  detalhado por sessão), migra pra CloudKit + SwiftData sem quebrar API —
//  os métodos públicos daqui são estáveis.
//
//  STREAK
//
//  Registrada globalmente (não por história). Regra:
//    • Primeira leitura em qualquer dia: streak = 1, guarda dia
//    • Leitura em dia consecutivo ao último: streak += 1
//    • Leitura no mesmo dia: no-op (não conta duplo)
//    • Gap > 1 dia: streak reseta pra 1
//
//  Usa `Calendar.current.isDate(_:inSameDayAs:)` — respeita timezone local.
//  Se o usuário viajar de fuso, a leitura pode "não contar" um dia; aceitamos
//  esse trade-off pra evitar cálculo em UTC que confunde criança que leu
//  às 23h de segunda e às 7h de terça.
//  ────────────────────────────────────────────────────────────────────────────

import Foundation
import SwiftUI

// MARK: - StoryProgress (por história)

struct StoryProgress: Codable, Equatable {
    /// Índice do capítulo atual (0-indexed no array `Story.chapters`).
    var chapterIndex: Int = 0
    /// Índice da página atual dentro do capítulo (0-indexed).
    var pageIndex: Int = 0
    /// Última vez que essa história foi tocada.
    var lastReadAt: Date? = nil
    /// True quando o usuário completou a última página do último capítulo.
    var isFinished: Bool = false

    /// Nunca foi aberta.
    var isFresh: Bool { lastReadAt == nil && !isFinished }

    /// Aberta pelo menos uma vez mas não terminada.
    var isInProgress: Bool { lastReadAt != nil && !isFinished }
}

// MARK: - Streak (global)

struct Streak: Codable, Equatable {
    var currentStreak: Int = 0
    var lastActiveDay: Date? = nil

    /// Registra atividade no `date` dado (padrão: agora).
    ///
    /// Regras:
    ///   • Primeira atividade de todos: streak vira 1
    ///   • Mesmo dia que a última: no-op
    ///   • Dia consecutivo ao último: streak++
    ///   • Gap > 1 dia: streak reseta pra 1
    mutating func recordActivity(on date: Date = .now) {
        let cal = Calendar.current

        guard let last = lastActiveDay else {
            currentStreak = 1
            lastActiveDay = date
            return
        }

        if cal.isDate(last, inSameDayAs: date) {
            return   // já contou hoje
        }

        if let yesterday = cal.date(byAdding: .day, value: -1, to: date),
           cal.isDate(last, inSameDayAs: yesterday) {
            currentStreak += 1
            lastActiveDay = date
        } else {
            currentStreak = 1
            lastActiveDay = date
        }
    }
}

// MARK: - ReadingLog (rolling window de sessões)

/// Sessões de leitura recentes, com rolling window de 90 dias. Guarda apenas
/// um timestamp por dia (dedupe) — se o usuário abre o reader várias vezes
/// no mesmo dia, ainda conta como 1 sessão. Isso evita inflar métricas em
/// sessões curtas seguidas (ex: usuário abrindo/fechando pra ver o cover).
///
/// USO
///
/// Consumido pelo `ReadingActivityChart` no ProfileView pra mostrar o
/// pattern semanal ("em que dia da semana você lê mais").
///
/// TAMANHO
///
/// Rolling 90 dias × 1 Date por dia = no máximo ~2KB serializado. Tranquilo
/// pro UserDefaults. Se um dia expandir análises (ex: "your reading year"),
/// aumentar a janela pra 365 ou migrar pra SwiftData.
///
/// MIGRATION
///
/// Snapshot inclui `readingLog` como Optional pra retrocompat — usuários
/// que instalaram antes desta versão simplesmente começam com log vazio,
/// o chart mostra empty state, e populam à medida que leem.
struct ReadingLog: Codable, Equatable {
    var sessions: [Date] = []

    /// Registra uma sessão no dia dado. Dedupe: se já tem uma sessão hoje,
    /// no-op. Aplica rolling window: remove entradas mais antigas que 90
    /// dias em relação à sessão que está sendo adicionada.
    mutating func log(on date: Date = .now) {
        let cal = Calendar.current
        // Dedupe: uma entrada por dia
        if sessions.contains(where: { cal.isDate($0, inSameDayAs: date) }) {
            return
        }
        sessions.append(date)
        // Rolling window de 90 dias — aplicado a cada log pra manter enxuto
        if let cutoff = cal.date(byAdding: .day, value: -90, to: date) {
            sessions = sessions.filter { $0 >= cutoff }
        }
    }

    /// Contagem de sessões por weekday (chaves 1-7 no formato do Calendar,
    /// 1 = domingo). Retorna sempre 7 entradas, com 0 pros dias sem sessão.
    /// Consumida diretamente pelo chart.
    func countsByWeekday(now: Date = .now) -> [Int: Int] {
        let cal = Calendar.current
        var result: [Int: Int] = Dictionary(uniqueKeysWithValues: (1...7).map { ($0, 0) })
        for date in sessions {
            let weekday = cal.component(.weekday, from: date)
            result[weekday, default: 0] += 1
        }
        return result
    }

    /// Weekday mais frequente. Retorna nil quando:
    ///   • Log está vazio
    ///   • Existe empate entre 2+ weekdays no topo (não faz sentido
    ///     dizer "você lê mais em X" se X e Y estão empatados)
    ///
    /// Consumido pelo chart pra destacar UMA barra em pink e pra gerar
    /// a mensagem contextual embaixo.
    func mostFrequentWeekday(now: Date = .now) -> Int? {
        let counts = countsByWeekday(now: now)
        let sorted = counts.sorted { $0.value > $1.value }
        guard let top = sorted.first, top.value > 0 else { return nil }
        if sorted.count > 1, sorted[1].value == top.value { return nil }
        return top.key
    }
}

// MARK: - LibraryProgress (@Observable — injetado via environment)

@Observable
@MainActor
final class LibraryProgress {
    private static let storageKey = "pedagogy.library-progress.v1"

    /// Dicionário storyID → progresso individual.
    var stories: [String: StoryProgress] = [:]
    var streak: Streak = Streak()

    /// Rolling window de 90 dias de sessões de leitura, uma entrada por
    /// dia (dedupe). Consumido pelo ReadingActivityChart no ProfileView.
    var readingLog: ReadingLog = ReadingLog()

    init() {
        load()
    }

    // MARK: - Public API

    /// Progresso da história dada (retorna `StoryProgress()` fresh se nunca
    /// foi aberta — nunca retorna nil, simplifica call sites).
    func progress(for storyID: String) -> StoryProgress {
        stories[storyID] ?? StoryProgress()
    }

    /// Atualiza posição de leitura. Chama a cada virada de página no reader.
    /// Registra atividade na streak automaticamente e loga sessão do dia
    /// no readingLog (dedupe: 1 entrada por dia mesmo com múltiplas viradas).
    func updatePosition(storyID: String, chapter: Int, page: Int) {
        var p = progress(for: storyID)
        p.chapterIndex = chapter
        p.pageIndex = page
        p.lastReadAt = .now
        stories[storyID] = p
        streak.recordActivity()
        readingLog.log()
        save()
    }

    /// Marca história como completa. Chamar quando o usuário chegar na última
    /// página do último capítulo.
    func markFinished(storyID: String) {
        var p = progress(for: storyID)
        p.isFinished = true
        p.lastReadAt = .now
        stories[storyID] = p
        save()
    }

    /// Zera progresso de uma história (útil pra "read again" ou debug).
    func resetProgress(storyID: String) {
        stories.removeValue(forKey: storyID)
        save()
    }

    /// Zera TUDO (debug/settings).
    func resetAll() {
        stories.removeAll()
        streak = Streak()
        readingLog = ReadingLog()
        save()
    }

    // MARK: - Persistence

    /// Envelope Codable pra serializar tudo num único blob JSON no UserDefaults.
    ///
    /// `readingLog` é Optional pra retrocompat — usuários que instalaram antes
    /// desta versão têm snapshots sem esse campo. O decoder trata como nil,
    /// e o load() abaixo faz fallback pra ReadingLog() vazio. Não precisa
    /// bump de versão da chave storageKey.
    private struct Snapshot: Codable {
        var stories: [String: StoryProgress]
        var streak: Streak
        var readingLog: ReadingLog?
    }

    private func load() {
        guard let data = UserDefaults.standard.data(forKey: Self.storageKey),
              let snap = try? JSONDecoder().decode(Snapshot.self, from: data)
        else { return }

        stories = snap.stories
        streak = snap.streak
        readingLog = snap.readingLog ?? ReadingLog()
    }

    private func save() {
        let snap = Snapshot(stories: stories, streak: streak, readingLog: readingLog)
        guard let data = try? JSONEncoder().encode(snap) else {
            print("[LibraryProgress] Failed to encode snapshot")
            return
        }
        UserDefaults.standard.set(data, forKey: Self.storageKey)
    }
}
