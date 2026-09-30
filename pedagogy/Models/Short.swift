//
//  Short.swift
//  pedagogy
//
//  ─── SHORT FILM MODEL ───────────────────────────────────────────────────────
//  Um filme da seção Watch. Três origens (ver `Kind`): curtas originais do
//  Pedagogy (scripts/shorts/), filmes abertos da Blender e clássicos em
//  domínio público do Internet Archive (scripts/classics/).
//
//  DE ONDE VEM
//
//  `Content/Shorts/shorts.json` — um array, escrito pelo
//  `produce_short.py publish`. Não se edita à mão: o `durationSeconds` sai
//  do arquivo final medido com ffprobe.
//
//  O vídeo em si é On-Demand Resource (tag `short-<id>`, ~40–80 MB cada) e
//  o pôster fica no bundle, pra seção da Home aparecer inteira sem rede.
//  ────────────────────────────────────────────────────────────────────────────

import Foundation

struct Short: Codable, Identifiable, Hashable {
    /// Slug. Bate com `shorts/<id>/film.json` e com os arquivos
    /// `short-<id>.mp4` / `short-<id>-poster.jpg`.
    let id: String

    let title: String
    let logline: String
    let durationSeconds: Int

    /// Mesma regra das histórias: premium exige assinatura. O piloto é free
    /// de propósito — é amostra do formato. Os filmes do Watch são premium
    /// com 3 grátis por semana em rodízio: pra decidir acesso use
    /// `isFreeToWatch(in:)`, nunca este campo direto.
    let isPremium: Bool

    /// Curta com data no futuro não aparece. Diferente das histórias (ver
    /// ROADMAP 2.6), aqui esconder é o comportamento certo: não existe
    /// "grátis esta semana" pra curta, então mostrar antes não teria motivo.
    let publishedAt: Date?

    /// De onde veio. Decide em qual fileira da seção Watch o filme entra.
    /// Opcional: entradas antigas sem o campo são originais.
    let kind: Kind?

    /// Ano de lançamento — só pra filmes de terceiros ("Classic · 1941").
    let year: Int?

    /// Autoria e licença. Obrigatórios na tela pra CC BY: a licença exige
    /// crédito visível a quem assiste, não só no arquivo.
    let credit: String?
    let license: String?
    let sourceURL: String?

    enum Kind: String, Codable {
        case original   // Pedagogy Originals, pipeline de scripts/shorts
        case open       // filmes abertos (Blender), CC BY
        case classic    // domínio público do Internet Archive
    }

    var resolvedKind: Kind { kind ?? .original }

    /// Linha de crédito do card: "Blender Foundation · CC BY 4.0".
    var attribution: String? {
        let parts = [credit, license].compactMap { $0 }.filter { !$0.isEmpty }
        return parts.isEmpty ? nil : parts.joined(separator: " · ")
    }

    /// "5 min" — arredondado, nunca "0 min".
    var durationLabel: String {
        "\(max(1, Int((Double(durationSeconds) / 60).rounded()))) min"
    }

    func isReleased(now: Date = .now) -> Bool {
        guard let publishedAt else { return true }
        return publishedAt <= now
    }
}

// MARK: - Grátis da semana

extension Short {
    /// Quantos filmes do Watch ficam grátis por semana.
    static let freePerWeek = 3

    /// Se o filme pode ser assistido SEM assinatura. Mesmo papel do
    /// `Story.isFreeToRead()`: a regra de acesso fica num lugar só.
    ///
    ///   • Não-premium → sempre grátis
    ///   • Premium do Watch (aberto ou clássico) no trio grátis da semana → grátis
    ///   • O resto → exige assinatura
    ///
    /// Precisa do catálogo porque o trio depende de quais filmes existem.
    func isFreeToWatch(in catalog: [Short], now: Date = .now) -> Bool {
        !isPremium || Short.freeThisWeek(in: catalog, now: now).contains(id)
    }

    /// Ids do trio grátis desta semana: rodízio pelos filmes premium do
    /// Watch, 3 por semana — com 36 filmes, cada um volta a ficar grátis a
    /// cada 12 semanas. Os originais ficam fora: o acesso deles é só o
    /// `isPremium`.
    ///
    /// A fila é embaralhada, mas fixa (hash do id): em ordem alfabética os
    /// filmes de uma série cairiam juntos (os três Caminandes na mesma semana).
    ///
    /// Calculado no aparelho, sem servidor e sem editar o JSON toda semana.
    /// Filme novo no catálogo reordena o rodízio na versão seguinte do app;
    /// nunca deixa uma semana sem grátis.
    static func freeThisWeek(in catalog: [Short], now: Date = .now) -> Set<String> {
        let pool = catalog
            .filter { $0.isPremium && $0.resolvedKind != .original }
            .map(\.id)
            .sorted { (fnv1a($0), $0) < (fnv1a($1), $1) }
        guard !pool.isEmpty else { return [] }
        let count = min(freePerWeek, pool.count)
        let start = ((weekIndex(now) * freePerWeek) % pool.count + pool.count) % pool.count
        return Set((0..<count).map { pool[(start + $0) % pool.count] })
    }

    /// FNV-1a 64 bits: igual em todo aparelho e toda execução (o `hashValue`
    /// do Swift muda a cada lançamento do app).
    private static func fnv1a(_ text: String) -> UInt64 {
        var hash: UInt64 = 0xcbf2_9ce4_8422_2325
        for byte in text.utf8 {
            hash = (hash ^ UInt64(byte)) &* 0x0000_0100_0000_01b3
        }
        return hash
    }

    /// Semanas desde a segunda-feira 5 jan 2026, no fuso do aparelho: o trio
    /// vira na segunda à meia-noite local, como a semana de quem assiste.
    private static func weekIndex(_ now: Date) -> Int {
        var calendar = Calendar(identifier: .iso8601)
        calendar.timeZone = .current
        guard let epoch = calendar.date(from: DateComponents(year: 2026, month: 1, day: 5)),
              let monday = calendar.dateInterval(of: .weekOfYear, for: now)?.start,
              let days = calendar.dateComponents([.day], from: epoch, to: monday).day
        else { return 0 }
        return days >= 0 ? days / 7 : (days - 6) / 7
    }
}
