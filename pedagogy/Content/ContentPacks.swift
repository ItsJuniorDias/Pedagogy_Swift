//
//  ContentPacks.swift
//  pedagogy
//
//  ─── ON-DEMAND RESOURCES ────────────────────────────────────────────────────
//  Narração e motion não vêm no download da App Store. Ficam hospedados pela
//  Apple em pacotes que o app pede na hora em que precisa.
//
//  O QUE SAI DO BUNDLE
//
//      narration-<slug>   os MP3 dos capítulos   ~5,5 MB cada   272 MB no total
//      motion-<slug>      o loop da capa         ~1,6 MB cada    81 MB no total
//
//  Uma tag por história, não por capítulo: quem ouve o capítulo 1 quase
//  sempre segue pro 2 pelo auto-play, e com a história inteira já no device
//  a virada de capítulo não para pra baixar nada.
//
//  O QUE FICA
//
//  Capas, JSONs das histórias e os .timings.json (2,4 MB somados). Os timings
//  ficam de propósito: são eles que dizem "este capítulo tem narração" antes
//  de qualquer download. Ver `AudioPlayerManager.hasNarration`.
//
//  ONDE AS TAGS SÃO DEFINIDAS
//
//  No project.pbxproj, em `assetTagsByRelativePath`, gerado por
//  `scripts/tag_ondemand_resources.py` a partir das pastas Content/Audio e
//  Content/Motion. Rode de novo sempre que entrar arquivo novo. Esquecer não
//  quebra nada: o arquivo sem tag vai pro bundle principal, os lookups acham
//  ele lá e tudo funciona — só volta a pesar no download.
//
//  DEPRECAÇÃO
//
//  O SDK do iOS 27 marca NSBundleResourceRequest como deprecado em favor do
//  Background Assets. O substituto hospedado pela Apple (AssetPackManager)
//  exige iOS 26, e o app ainda roda no 18. Tudo que toca na API está neste
//  arquivo, pra migração ficar aqui dentro quando o piso subir.
//  ────────────────────────────────────────────────────────────────────────────

import Foundation

/// Um pacote de conteúdo sob demanda.
enum ContentPack: Hashable {
    case narration(storyID: String)
    case motion(storyID: String)

    /// A tag no project.pbxproj. Precisa bater com o script que as grava.
    var tag: String {
        switch self {
        case .narration(let id): return "narration-\(id)"
        case .motion(let id):    return "motion-\(id)"
        }
    }
}

/// Segura um pacote no device enquanto este objeto viver.
///
/// O sistema pode apagar um pacote baixado sempre que o disco apertar e
/// nenhum pedido o estiver segurando. Por isso quem usa o arquivo guarda este
/// objeto pelo tempo em que usa: o player enquanto a história está carregada,
/// a capa enquanto está montada. Soltar a referência não apaga nada — o
/// pacote continua no disco até faltar espaço, e o próximo pedido sai sem
/// download.
final class ContentPackAccess {

    let pack: ContentPack

    /// Guardado só pela vida útil: é a existência dele que protege o pacote.
    /// Desalocar encerra o acesso, não precisa de `endAccessingResources()`.
    private let request: NSBundleResourceRequest

    private init(pack: ContentPack, request: NSBundleResourceRequest) {
        self.pack = pack
        self.request = request
    }

    /// Garante o pacote no device, baixando se precisar. Depois que retorna,
    /// os arquivos do pacote aparecem no `Bundle.main` como qualquer outro.
    ///
    /// - Parameters:
    ///   - urgent: alguém está parado esperando (tocou em play). Passa à
    ///     frente dos outros downloads do sistema.
    ///   - onProgress: fração 0…1 do download. Não é chamado quando o pacote
    ///     já estava no device.
    /// - Throws: erro de rede ou de espaço. Cancelar a Task interrompe o
    ///   download de verdade e também cai aqui.
    static func fetch(
        _ pack: ContentPack,
        urgent: Bool = false,
        onProgress: (@MainActor @Sendable (Double) -> Void)? = nil
    ) async throws -> ContentPackAccess {
        let request = NSBundleResourceRequest(tags: [pack.tag])
        if urgent {
            request.loadingPriority = NSBundleResourceRequestLoadingPriorityUrgent
        }

        // Já no device: libera na hora, sem tocar na rede.
        if await request.conditionallyBeginAccessingResources() {
            return ContentPackAccess(pack: pack, request: request)
        }

        let progress = request.progress
        // `@Sendable` explícito: o KVO chega na thread de quem baixa, e sem
        // isso a closure herdaria o isolamento do main actor.
        let observation = onProgress.map { report in
            progress.observe(\.fractionCompleted) { @Sendable progress, _ in
                let fraction = progress.fractionCompleted
                Task { @MainActor in report(fraction) }
            }
        }
        defer { observation?.invalidate() }

        try await withTaskCancellationHandler {
            try await request.beginAccessingResources()
        } onCancel: {
            progress.cancel()
        }
        return ContentPackAccess(pack: pack, request: request)
    }
}
