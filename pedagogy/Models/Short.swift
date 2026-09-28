//
//  Short.swift
//  pedagogy
//
//  ─── SHORT FILM MODEL ───────────────────────────────────────────────────────
//  Um curta-metragem original do Pedagogy. Não é adaptação de história: tem
//  roteiro próprio, produzido pelo pipeline em scripts/shorts/.
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

    /// "5 min" — arredondado, nunca "0 min".
    var durationLabel: String {
        "\(max(1, Int((Double(durationSeconds) / 60).rounded()))) min"
    }

    func isReleased(now: Date = .now) -> Bool {
        guard let publishedAt else { return true }
        return publishedAt <= now
    }
}
