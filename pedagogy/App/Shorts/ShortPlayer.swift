//
//  ShortPlayer.swift
//  pedagogy
//
//  ─── PLAYER DE CURTAS ───────────────────────────────────────────────────────
//  Baixa o curta (On-Demand Resource), abre em tela cheia e devolve tudo
//  como estava quando fecha.
//
//  POR QUE AVPlayerViewController APRESENTADO PELO UIKit
//
//  Embutido numa view SwiftUI (`VideoPlayer` ou representable), o player
//  mostra os controles "inline": sem botão de fechar, sem gesto de arrastar
//  pra baixo, e um botão de fechar nosso por cima brigaria com os dele.
//  Apresentado modal pelo UIKit ele vira o player de tela cheia do sistema:
//  X nativo, swipe pra fechar, menu de legendas (a faixa mov_text que o
//  pipeline grava), AirPlay e PiP de graça — o mesmo player que a criança
//  já conhece de qualquer outro app.
//
//  DOWNLOAD NO CARD, NÃO NUMA TELA DE LOADING
//
//  O progresso aparece no próprio card da Home. Uma tela preta com barra
//  por 20 segundos parece travamento; o card com o anel enchendo deixa a
//  criança continuar vendo a Home, e dá pra tocar de novo pra cancelar.
//
//  ORIENTAÇÃO
//
//  O app é retrato no iPhone. Filme 16:9 em retrato vira uma faixa de 200pt,
//  então enquanto o player está aberto o `OrientationLock` libera paisagem,
//  e ao fechar força a volta pra retrato. Ver AppDelegate.
//  ────────────────────────────────────────────────────────────────────────────

import AVKit
import SwiftUI
import UIKit

// MARK: - Orientation lock

/// Máscara de orientação que o AppDelegate devolve pro sistema.
///
/// O Info.plist declara paisagem no iPhone só pra ela ser *permitida*; quem
/// decide quando é esta máscara. Fora do player, o iPhone continua travado
/// em retrato como sempre foi. No iPad nada muda: ele já girava livre.
enum OrientationLock {
    @MainActor static var mask: UIInterfaceOrientationMask = defaultMask

    @MainActor static var defaultMask: UIInterfaceOrientationMask {
        UIDevice.current.userInterfaceIdiom == .pad ? .all : .portrait
    }

    /// Volta à máscara padrão e pede pro sistema girar se precisar.
    /// Sem o `requestGeometryUpdate`, quem fecha o filme em paisagem ficaria
    /// com a Home deitada até girar o aparelho.
    @MainActor static func restore() {
        mask = defaultMask
        guard let scene = UIApplication.shared.connectedScenes
            .compactMap({ $0 as? UIWindowScene }).first else { return }
        scene.keyWindow?.rootViewController?.setNeedsUpdateOfSupportedInterfaceOrientations()
        scene.requestGeometryUpdate(.iOS(interfaceOrientations: mask))
    }
}

// MARK: - Launcher

/// Cuida do ciclo de um curta: download → player → limpeza.
/// Uma instância por tela que mostra cards de curta (hoje, a Home).
@MainActor
@Observable
final class ShortLauncher {

    /// Fração 0…1 do download, por id. Presente = baixando.
    private(set) var downloading: [String: Double] = [:]

    /// Último curta que falhou ao baixar. O card mostra "tente de novo".
    private(set) var failedID: String?

    /// Segura o pacote no device enquanto o filme estiver aberto.
    /// Solto ao fechar: o arquivo fica em disco até o sistema precisar do
    /// espaço, e ver de novo não baixa outra vez.
    private var access: ContentPackAccess?
    private var task: Task<Void, Never>?

    /// Toque no card. Se já está baixando, o segundo toque cancela.
    func toggle(_ short: Short, audio: AudioPlayerManager) {
        if downloading[short.id] != nil {
            task?.cancel()
            downloading[short.id] = nil
            return
        }
        // Um de cada vez: outro baixando, ou um filme já aberto.
        guard downloading.isEmpty, access == nil else { return }

        failedID = nil
        downloading[short.id] = 0
        task = Task { [weak self] in
            do {
                let access = try await ContentPackAccess.fetch(.short(id: short.id), urgent: true) { fraction in
                    self?.downloading[short.id] = fraction
                }
                guard let self else { return }
                self.downloading[short.id] = nil
                guard !Task.isCancelled, let url = ShortCatalog.videoURL(id: short.id) else {
                    if !Task.isCancelled { self.failedID = short.id }
                    return
                }
                self.access = access
                self.present(short: short, url: url, audio: audio)
            } catch {
                self?.downloading[short.id] = nil
                if !(error is CancellationError) && !Task.isCancelled {
                    print("[ShortLauncher] download failed for \(short.id): \(error)")
                    self?.failedID = short.id
                }
            }
        }
    }

    private func present(short: Short, url: URL, audio: AudioPlayerManager) {
        guard let presenter = UIApplication.shared.topViewController else {
            access = nil
            return
        }

        let player = AVPlayer(url: url)
        let controller = FilmPlayerController()
        controller.player = player
        controller.modalPresentationStyle = .fullScreen
        // PiP tiraria o controller da tela com o filme ainda tocando, e o
        // ciclo de limpeza abaixo depende de "saiu da tela = acabou".
        controller.allowsPictureInPicturePlayback = false

        audio.beginVideoPlayback()
        OrientationLock.mask = .allButUpsideDown

        let endObserver = NotificationCenter.default.addObserver(
            forName: AVPlayerItem.didPlayToEndTimeNotification,
            object: player.currentItem,
            queue: .main
        ) { _ in
            // queue: .main garante a thread; o compilador só não sabe disso.
            MainActor.assumeIsolated {
                Analytics.shared.track(.shortComplete, ["content_id": short.id])
            }
        }

        controller.onDismiss = { [weak self] in
            player.pause()
            NotificationCenter.default.removeObserver(endObserver)
            audio.endVideoPlayback()
            OrientationLock.restore()
            self?.access = nil
        }

        Analytics.shared.track(.shortPlay, ["content_id": short.id])
        presenter.present(controller, animated: true) {
            player.play()
        }
    }
}

// MARK: - Player controller

/// `AVPlayerViewController` que avisa quando foi fechado — pelo X, pelo
/// swipe ou por qualquer outro caminho. Só `viewDidDisappear` pega todos.
final class FilmPlayerController: AVPlayerViewController {
    var onDismiss: (() -> Void)?

    override var supportedInterfaceOrientations: UIInterfaceOrientationMask { .allButUpsideDown }

    override func viewDidDisappear(_ animated: Bool) {
        super.viewDidDisappear(animated)
        if isBeingDismissed || presentingViewController == nil {
            onDismiss?()
            onDismiss = nil
        }
    }
}

// MARK: - Top view controller

private extension UIApplication {
    /// O controller mais de cima da janela ativa — de onde dá pra apresentar
    /// por cima de sheets e fullScreenCovers do SwiftUI.
    var topViewController: UIViewController? {
        let scene = connectedScenes
            .compactMap { $0 as? UIWindowScene }
            .first { $0.activationState == .foregroundActive }
        var top = scene?.keyWindow?.rootViewController
        while let presented = top?.presentedViewController {
            top = presented
        }
        return top
    }
}
