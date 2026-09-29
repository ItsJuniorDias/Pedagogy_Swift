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
    /// de propósito — é amostra do formato.
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
