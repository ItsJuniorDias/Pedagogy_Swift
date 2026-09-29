//
//  ShortCatalog.swift
//  pedagogy
//
//  ─── ONDE MORAM OS CURTAS ───────────────────────────────────────────────────
//  Lê o catálogo e acha pôster e vídeo de cada curta no bundle.
//
//      Content/Shorts/shorts.json               catálogo (no bundle)
//      Content/Shorts/short-<id>-poster.jpg     pôster 16:9 (no bundle)
//      Content/Shorts/short-<id>.mp4            filme (On-Demand, tag short-<id>)
//
//  O prefixo `short-` não é enfeite: o grupo sincronizado achata tudo na
//  raiz do bundle, e sem ele um curta com o mesmo slug de uma história
//  colidiria com o `<slug>.mp4` do motion.
//
//  O vídeo só é achado depois que o pacote foi baixado e está seguro por um
//  `ContentPackAccess` — quem pede é o `ShortPlayerView`.
//
//  Sem `shorts.json` no bundle, `loadAll()` devolve vazio e a seção "Watch"
//  da Home simplesmente não aparece.
//  ────────────────────────────────────────────────────────────────────────────

import Foundation

enum ShortCatalog {

    /// Mesma lógica do `MotionCatalog`: grupo sincronizado achata, folder
    /// reference preserva. Testar as duas evita o bug que só aparece no device.
    private static let searchPaths: [String?] = ["Content/Shorts", "Shorts", nil]

    /// Filmes já lançados, na ordem do catálogo — o script que o escreve já
    /// ordena (originais primeiro, depois por ano).
    static func loadAll(now: Date = .now) -> [Short] {
        guard let url = find("shorts", ext: "json") else { return [] }
        do {
            let data = try Data(contentsOf: url)
            return try makeDecoder().decode([Short].self, from: data)
                .filter { $0.isReleased(now: now) }
        } catch {
            print("[ShortCatalog] Failed to decode shorts.json:", error)
            return []
        }
    }

    static func posterURL(id: String) -> URL? {
        find("short-\(id)-poster", ext: "jpg")
    }

    static func videoURL(id: String) -> URL? {
        find("short-\(id)", ext: "mp4")
    }

    private static func find(_ name: String, ext: String) -> URL? {
        for sub in searchPaths {
            if let url = Bundle.main.url(forResource: name, withExtension: ext, subdirectory: sub) {
                return url
            }
        }
        return nil
    }

    /// Datas "2026-10-05", igual ao `StoryLoader`.
    private static func makeDecoder() -> JSONDecoder {
        let formatter = DateFormatter()
        formatter.locale = Locale(identifier: "en_US_POSIX")
        formatter.timeZone = TimeZone(secondsFromGMT: 0)
        formatter.dateFormat = "yyyy-MM-dd"
        let decoder = JSONDecoder()
        decoder.dateDecodingStrategy = .formatted(formatter)
        return decoder
    }
}
