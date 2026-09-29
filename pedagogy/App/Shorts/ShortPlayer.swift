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

    /// Último curta que falhou ao baixar ou abrir. O card mostra "tente de novo".
    private(set) var failedID: String?

    /// Segura o pacote no device enquanto o filme estiver aberto.
    /// Solto ao fechar: o arquivo fica em disco até o sistema precisar do
    /// espaço, e ver de novo não baixa outra vez.
    private var access: ContentPackAccess?
    private var task: Task<Void, Never>?

    /// Identidade do download em curso. Um download cancelado ainda termina
    /// de desenrolar depois do cancel — sem isso, ele apagaria o anel de um
    /// download novo do mesmo card, ou chegaria a abrir um segundo player.
    /// Todo retorno de download confere o token antes de mexer em estado.
    private var downloadToken: UUID?

    /// Um filme aberto agora. Não dá pra usar `access != nil` pra isso: filme
    /// que já está no bundle abre sem pacote nenhum.
    private var isPresenting = false

    /// Toque no card. Se já está baixando, o segundo toque cancela.
    func toggle(_ short: Short, audio: AudioPlayerManager) {
        if downloading[short.id] != nil {
            endDownload(cancel: true)
            return
        }
        // Um de cada vez: outro baixando, ou um filme já aberto.
        guard downloading.isEmpty, !isPresenting else { return }
        failedID = nil

        // Arquivo já acessível: sem tag no bundle (esqueceram de rodar o
        // tag_ondemand_resources.py) ou pacote baixado e ainda seguro. Mesma
        // ordem da narração em `AudioPlayerManager.play`. Pedir o pacote
        // primeiro quebrava o primeiro caso: o NSBundleResourceRequest
        // rejeita tag que não existe no projeto, com o filme ali no bundle.
        if let url = ShortCatalog.videoURL(id: short.id) {
            present(short: short, url: url, audio: audio)
            return
        }

        let token = UUID()
        downloadToken = token
        downloading[short.id] = 0
        task = Task { [weak self] in
            do {
                let access = try await ContentPackAccess.fetch(.short(id: short.id), urgent: true) { fraction in
                    guard self?.downloadToken == token else { return }
                    self?.downloading[short.id] = fraction
                }
                guard let self, self.downloadToken == token else { return }
                self.endDownload(cancel: false)
                guard let url = ShortCatalog.videoURL(id: short.id) else {
                    print("[ShortLauncher] pack \(short.id) downloaded but the mp4 isn't in it")
                    self.failedID = short.id
                    return
                }
                self.access = access
                self.present(short: short, url: url, audio: audio)
            } catch {
                guard let self, self.downloadToken == token else { return }
                self.endDownload(cancel: false)
                if !(error is CancellationError) {
                    print("[ShortLauncher] download failed for \(short.id): \(error)")
                    self.failedID = short.id
                }
            }
        }
    }

    private func endDownload(cancel: Bool) {
        if cancel { task?.cancel() }
        task = nil
        downloadToken = nil
        downloading.removeAll()
    }

    private func present(short: Short, url: URL, audio: AudioPlayerManager) {
        guard !isPresenting else { return }

        // Download terminou com o app em segundo plano: não abre sozinho na
        // volta — isso brigaria com um deep link de notificação que abre o
        // app no mesmo instante. O pacote fica seguro em `access` e o arquivo
        // já é achado no bundle, então o próximo toque no card toca na hora.
        guard let presenter = UIApplication.shared.topViewController else { return }

        // Uma sheet abrindo ou fechando recusa o present (o UIKit só loga um
        // aviso e nunca chama a completion). Espera a transição terminar; o
        // async tira a nova tentativa de dentro do callout do próprio UIKit.
        if let coordinator = presenter.transitionCoordinator {
            coordinator.animate(alongsideTransition: nil) { [weak self] _ in
                DispatchQueue.main.async {
                    self?.present(short: short, url: url, audio: audio)
                }
            }
            return
        }

        isPresenting = true

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
            self?.isPresenting = false
        }

        presenter.present(controller, animated: true) {
            player.play()
        }

        // O UIKit liga `presentingViewController` na hora em que aceita o
        // present. Nil aqui = recusado: desfaz sessão de áudio, orientação e
        // o `isPresenting`, que senão travariam todo curta até reabrir o app.
        guard controller.presentingViewController != nil else {
            print("[ShortLauncher] presentation of \(short.id) was refused")
            controller.onDismiss?()
            controller.onDismiss = nil
            failedID = short.id
            return
        }
        FilmPlayerController.current = controller
        Analytics.shared.track(.shortPlay, ["content_id": short.id])
    }
}

// MARK: - Player controller

/// `AVPlayerViewController` que avisa quando foi fechado — pelo X, pelo
/// swipe ou por qualquer outro caminho. Só `viewDidDisappear` pega todos.
final class FilmPlayerController: AVPlayerViewController {
    var onDismiss: (() -> Void)?

    /// O filme em tela cheia agora, se houver.
    static weak var current: FilmPlayerController?

    override var supportedInterfaceOrientations: UIInterfaceOrientationMask { .allButUpsideDown }

    override func viewDidDisappear(_ animated: Bool) {
        super.viewDidDisappear(animated)
        if isBeingDismissed || presentingViewController == nil {
            onDismiss?()
            onDismiss = nil
        }
    }

    /// Fecha o filme aberto (se houver) e só então chama `then`.
    ///
    /// O filme é apresentado pelo UIKit por cima de tudo; enquanto ele está
    /// na tela, uma `.sheet` do SwiftUI não tem de onde abrir. Quem precisa
    /// abrir algo por cima (o deep link de notificação) fecha o filme antes.
    ///
    /// Filme no meio de uma transição (abrindo, ou fechando por swipe) recusa
    /// o dismiss sem chamar a completion — o deep link se perderia. Espera a
    /// transição e tenta de novo. O dismiss parte de quem apresentou o filme,
    /// não do filme: assim também fecha o que estiver por cima dele (o seletor
    /// de AirPlay, por exemplo).
    static func dismissCurrent(then: @escaping () -> Void) {
        guard let film = current, let presenter = film.presentingViewController else {
            then()
            return
        }
        if let coordinator = film.transitionCoordinator ?? presenter.transitionCoordinator {
            coordinator.animate(alongsideTransition: nil) { _ in
                DispatchQueue.main.async { dismissCurrent(then: then) }
            }
            return
        }
        presenter.dismiss(animated: true, completion: then)
    }
}

// MARK: - Top view controller

private extension UIApplication {
    /// O controller mais de cima da janela em primeiro plano — de onde dá pra
    /// apresentar por cima de sheets e fullScreenCovers do SwiftUI.
    ///
    /// `.foregroundInactive` também serve (Central de Controle aberta, banner
    /// de notificação por cima): apresentar nesse estado funciona. Um
    /// controller que está sendo fechado não serve de base — pula pra baixo.
    var topViewController: UIViewController? {
        let scenes = connectedScenes.compactMap { $0 as? UIWindowScene }
        let scene = scenes.first { $0.activationState == .foregroundActive }
            ?? scenes.first { $0.activationState == .foregroundInactive }
        var top = scene?.keyWindow?.rootViewController
        while let presented = top?.presentedViewController, !presented.isBeingDismissed {
            top = presented
        }
        return top
    }
}
