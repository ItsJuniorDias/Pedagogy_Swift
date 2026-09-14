//
//  StoryLoader.swift
//  pedagogy
//
//  ─── STORY LOADER ───────────────────────────────────────────────────────────
//  Carrega histórias do bundle da aplicação.
//
//  ONDE ESTÃO OS ARQUIVOS
//
//  `pedagogy/Content/Stories/*.json` no disco. O Xcode moderno usa
//  `PBXFileSystemSynchronizedRootGroup`, que descobre esses JSONs
//  automaticamente e os empacota no bundle da app. Não precisa registrar
//  arquivo por arquivo no pbxproj.
//
//  IMPORTANTE — path dentro do bundle
//
//  Por padrão, o Xcode empacota resources FLAT no root do bundle — ele NÃO
//  preserva a subpasta `Content/Stories/` a menos que a pasta seja adicionada
//  como "folder reference" (blue folder). Com synchronized root group, isso
//  não é o comportamento default.
//
//  Por isso o loader tenta AMBOS os caminhos:
//    1. `Bundle.main.url(forResource: id, subdirectory: "Stories")`  — preservada
//    2. `Bundle.main.url(forResource: id, subdirectory: nil)`         — flat
//
//  Se um dia você quiser preservar a hierarquia (útil pra ter muitas
//  histórias organizadas), transforme `Content/Stories/` em folder reference
//  via Xcode → drag pasta pro navigator → "Create folder references".
//
//  CACHE
//
//  Sem cache por enquanto — o volume é pequeno, `loadAll()` roda em <10ms
//  pra dezenas de JSONs pequenos. Se um dia forem 500 histórias com 5KB cada,
//  vale cachear. Por ora, chama uma vez no launch e guarda em memória via
//  @Observable class que envolve isso.
//
//  ERROS
//
//  Uma história com JSON malformado NÃO derruba o app — o loader loga e
//  continua com as outras. Se todas falharem, joga `noStoriesFound`.
//  ────────────────────────────────────────────────────────────────────────────

import Foundation

// MARK: - Errors

enum StoryLoaderError: Error, LocalizedError {
    case noStoriesFound
    case bundleReadFailed(URL, Error)

    var errorDescription: String? {
        switch self {
        case .noStoriesFound:
            return "No story JSON files found in the app bundle."
        case .bundleReadFailed(let url, let err):
            return "Failed to read \(url.lastPathComponent): \(err.localizedDescription)"
        }
    }
}

// MARK: - Loader

enum StoryLoader {

    /// Carrega todas as histórias do bundle. Ordem alfabética por filename.
    ///
    /// - Throws: `StoryLoaderError.noStoriesFound` se nada foi encontrado.
    ///   JSONs individuais malformados são logados e ignorados.
    static func loadAll() throws -> [Story] {
        let urls = discoverStoryURLs()

        guard !urls.isEmpty else {
            throw StoryLoaderError.noStoriesFound
        }

        let decoder = Self.makeDecoder()
        var loaded: [Story] = []

        for url in urls {
            do {
                let data = try Data(contentsOf: url)
                let story = try decoder.decode(Story.self, from: data)
                loaded.append(story)
            } catch {
                // Não é fatal — 1 história malformada não derruba a app.
                // Loga pra você ver no console durante dev.
                print("[StoryLoader] Failed to decode \(url.lastPathComponent):", error)
            }
        }

        if loaded.isEmpty {
            throw StoryLoaderError.noStoriesFound
        }

        return loaded.sorted { $0.id < $1.id }
    }

    /// Carrega uma história específica por ID (slug do filename).
    /// Retorna `nil` se o arquivo não existe.
    static func load(id: String) throws -> Story? {
        // Tenta primeiro na subpasta, depois no root do bundle
        let url = Bundle.main.url(forResource: id, withExtension: "json", subdirectory: "Stories")
               ?? Bundle.main.url(forResource: id, withExtension: "json")

        guard let url else { return nil }

        do {
            let data = try Data(contentsOf: url)
            return try Self.makeDecoder().decode(Story.self, from: data)
        } catch {
            throw StoryLoaderError.bundleReadFailed(url, error)
        }
    }

    // MARK: - Discovery

    /// Descobre todos os JSONs de história no bundle. Tenta ambos os locais
    /// (subpasta preservada + flat no root).
    private static func discoverStoryURLs() -> [URL] {
        var urls: [URL] = []

        // 1) Subpasta preservada (folder reference)
        if let inSubdir = Bundle.main.urls(
            forResourcesWithExtension: "json",
            subdirectory: "Stories"
        ) {
            urls.append(contentsOf: inSubdir)
        }

        // 2) Flat no root do bundle (comportamento default do Xcode)
        //    Filtra pra não pegar JSONs de config que possam existir depois
        //    (Products.storekit é .storekit, não .json, então já sai fora).
        if let inRoot = Bundle.main.urls(
            forResourcesWithExtension: "json",
            subdirectory: nil
        ) {
            urls.append(contentsOf: inRoot)
        }

        // Dedup por lastPathComponent — o mesmo arquivo pode aparecer nos dois
        // resultados se estiver em subpasta E o Xcode achatar (raro mas evita)
        var seen: Set<String> = []
        return urls.filter { seen.insert($0.lastPathComponent).inserted }
                   .sorted { $0.lastPathComponent < $1.lastPathComponent }
    }

    /// Decoder configurado pra parsear datas ISO 8601 date-only ("2026-09-03")
    /// no campo `publishedAt`. Sem esse formatter, o Codable padrão espera
    /// número unix timestamp e falha silenciosamente.
    ///
    /// Usa DateFormatter com locale POSIX pra evitar parse errado em regiões
    /// com formato de data diferente (BR usa dd/mm/yyyy por default, quebraria).
    private static func makeDecoder() -> JSONDecoder {
        let decoder = JSONDecoder()

        let formatter = DateFormatter()
        formatter.locale = Locale(identifier: "en_US_POSIX")
        formatter.timeZone = TimeZone(secondsFromGMT: 0)
        formatter.dateFormat = "yyyy-MM-dd"

        decoder.dateDecodingStrategy = .formatted(formatter)
        return decoder
    }
}
