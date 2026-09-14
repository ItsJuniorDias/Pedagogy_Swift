//
//  StoryTimings.swift
//  pedagogy
//
//  ─── STORY TIMINGS ──────────────────────────────────────────────────────────
//  Model + loader pros arquivos .timings.json gerados por
//  scripts/generate_timings.py. Consumido pelo AudioPlayerManager pra
//  saber qual sentença destacar durante a playback.
//
//  FORMATO (produzido pelo script Python)
//
//      {
//        "story_id": "fox-and-north-wind",
//        "chapter": 1,
//        "total_duration_ms": 480000,
//        "sentences": [
//          { "index": 0, "text": "In the north...", "start_ms": 0, "end_ms": 4200 },
//          { "index": 1, "text": "In winter...",   "start_ms": 4200, "end_ms": 9800 }
//        ]
//      }
//
//  PRECISION
//
//  Os arquivos são derivados dos *.chunks.json que saem junto do MP3
//  (scripts/chunks_to_timings.py). Cada chunk é um pedaço de TTS com
//  fronteiras MEDIDAS — conferidas contra o MP3 real com diferença de 0ms
//  nos 150 capítulos. Dentro de um chunk (~90s), a divisão em sentenças é
//  interpolada por caractere.
//
//  Resultado: exato a cada ~90s, 1 a 3s de erro nas sentenças do meio, e o
//  erro NÃO acumula — toda fronteira de chunk reancora a conta. Isso é o que
//  diferencia do gerador anterior, que estimava o capítulo inteiro de ponta
//  a ponta e acumulava dezenas de segundos até o fim.
//
//  Bom pra acompanhar a leitura. Insuficiente pra karaokê palavra a palavra,
//  que exigiria timestamps por palavra que o Flux não devolve.
//
//  ONDE FICAM
//
//  No bundle: Content/Audio/<slug>-ch<N>.timings.json (mesmo folder do MP3).
//  Se um .timings.json não existir pra um chapter (nunca gerado), o player
//  toca o áudio normalmente sem highlighting — falha suave.
//  ────────────────────────────────────────────────────────────────────────────

import Foundation

// MARK: - Model

struct StoryTimings: Codable, Equatable {
    let storyID: String
    let chapter: Int
    let totalDurationMs: Int
    let sentences: [SentenceTiming]

    enum CodingKeys: String, CodingKey {
        case storyID = "story_id"
        case chapter
        case totalDurationMs = "total_duration_ms"
        case sentences
    }

    /// Encontra o índice da sentença que está tocando num timestamp específico.
    /// Retorna nil se antes da 1ª sentença ou depois da última. Busca linear
    /// simples — o número de sentenças por capítulo é pequeno (~40) então
    /// isso é O(n) na prática mas não vale otimizar.
    func sentenceIndex(atMs ms: Int) -> Int? {
        for sentence in sentences {
            if ms >= sentence.startMs && ms < sentence.endMs {
                return sentence.index
            }
        }
        return nil
    }
}

struct SentenceTiming: Codable, Equatable, Identifiable {
    let index: Int
    let text: String
    let startMs: Int
    let endMs: Int

    var id: Int { index }

    enum CodingKeys: String, CodingKey {
        case index
        case text
        case startMs = "start_ms"
        case endMs = "end_ms"
    }
}

// MARK: - Loader

enum StoryTimingsLoaderError: Error, LocalizedError {
    case notFound(slug: String, chapter: Int)
    case decodingFailed(underlying: Error)

    var errorDescription: String? {
        switch self {
        case .notFound(let slug, let chapter):
            return "No timings file for \(slug) chapter \(chapter)"
        case .decodingFailed(let err):
            return "Timings decoding failed: \(err.localizedDescription)"
        }
    }
}

enum StoryTimingsLoader {
    /// Carrega o .timings.json do bundle pra uma story+chapter.
    ///
    /// Espera arquivo em Content/Audio/<slug>-ch<N>.timings.json. Se não
    /// achar (ainda não gerou), retorna .notFound — caller decide se
    /// degrada silenciosamente (AudioPlayerManager: toca sem highlight)
    /// ou reporta o erro.
    static func load(storySlug: String, chapter: Int) throws -> StoryTimings {
        let filename = "\(storySlug)-ch\(chapter).timings"
        guard let url = Bundle.main.url(
            forResource: filename,
            withExtension: "json",
            subdirectory: "Content/Audio"
        )
        // Fallback pra bundle root (dependendo de como o Xcode empacota
        // a pasta Content/Audio, o subdirectory pode não bater).
        ?? Bundle.main.url(forResource: filename, withExtension: "json") else {
            throw StoryTimingsLoaderError.notFound(slug: storySlug, chapter: chapter)
        }

        do {
            let data = try Data(contentsOf: url)
            return try JSONDecoder().decode(StoryTimings.self, from: data)
        } catch {
            throw StoryTimingsLoaderError.decodingFailed(underlying: error)
        }
    }

    /// Verifica se timings existem sem carregar. Útil pra decidir se
    /// mostra ou não indicador visual "sync disponível" no StoryDetail.
    static func exists(storySlug: String, chapter: Int) -> Bool {
        let filename = "\(storySlug)-ch\(chapter).timings"
        return Bundle.main.url(
            forResource: filename,
            withExtension: "json",
            subdirectory: "Content/Audio"
        ) != nil || Bundle.main.url(
            forResource: filename,
            withExtension: "json"
        ) != nil
    }
}
