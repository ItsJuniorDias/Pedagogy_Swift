//
//  MotionCatalog.swift
//  pedagogy
//
//  ─── ONDE MORAM OS CLIPES ───────────────────────────────────────────────────
//  Resolve o arquivo de motion de uma história e decide se é hora de animar.
//
//  CONVENÇÃO DE NOME
//
//      Content/Motion/<slug-da-historia>.mp4
//
//  Mesmo slug do `Story.id`, mesma cola que a narração usa. Loop de 4s, HEVC,
//  sem faixa de áudio, gerado pelo optimize_motion.py.
//
//  Os clipes são On-Demand Resources (tag `motion-<slug>`, ver
//  ContentPacks.swift): `url(slug:)` só acha um clipe depois que o pacote
//  dele foi baixado e está seguro por um `ContentPackAccess`. Quem pede o
//  pacote é a `MotionCover`.
//
//  QUANDO NÃO ANIMAR
//
//  As duas checagens abaixo não são zelo excessivo — são as duas situações em
//  que um vídeo em loop passa de encanto a incômodo:
//
//  • Reduce Motion ligado. Quem liga isso liga por enxaqueca, vertigem ou
//    sensibilidade vestibular. Um loop rodando sem parar debaixo do título é
//    exatamente o que a configuração existe pra evitar. E vale lembrar que o
//    público aqui é criança de 9 a 11 anos, faixa em que os pais configuram o
//    device justamente por causa disso.
//
//  • Modo de baixo consumo. Decodificar HEVC continuamente num card que a
//    pessoa talvez nem esteja olhando é o tipo de gasto que se corta primeiro
//    quando a bateria está em 10%.
//
//  Nos dois casos a capa estática continua lá, intacta. Nada some.
//  ────────────────────────────────────────────────────────────────────────────

import Foundation

enum MotionCatalog {

    /// Subpastas testadas, em ordem. `nil` = raiz do bundle.
    ///
    /// Depende de como a pasta entra no projeto: grupo sincronizado achata os
    /// recursos na raiz, folder reference preserva a estrutura. Testar as duas
    /// custa dois lookups e evita o bug que só aparece no device.
    private static let searchPaths: [String?] = ["Content/Motion", "Motion", nil]

    static func url(slug: String) -> URL? {
        for sub in searchPaths {
            if let url = Bundle.main.url(forResource: slug, withExtension: "mp4", subdirectory: sub) {
                return url
            }
        }
        return nil
    }

    /// Lido no momento em que a view aparece, não observado continuamente.
    ///
    /// O sistema publica `NSProcessInfoPowerStateDidChange` e dava pra
    /// escutar, mas o ganho seria o loop parar no instante exato em que a
    /// bateria cruza 20% — em vez de parar da próxima vez que a tela for
    /// aberta. Não paga a complexidade de um observer por card.
    static var isLowPowerMode: Bool {
        ProcessInfo.processInfo.isLowPowerModeEnabled
    }
}
