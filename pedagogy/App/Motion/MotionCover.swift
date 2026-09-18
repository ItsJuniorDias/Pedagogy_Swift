//
//  MotionCover.swift
//  pedagogy
//
//  ─── CAPA QUE RESPIRA ───────────────────────────────────────────────────────
//  Mostra a capa estática e, quando existe clipe pra história, funde um vídeo
//  em loop por cima.
//
//  A CAPA ESTÁTICA NUNCA SAI DE BAIXO
//
//  O vídeo entra por cima, com fade, só depois que o AVPlayerLayer avisa que
//  tem quadro pronto. Isso resolve três coisas de uma vez: nada de flash preto
//  no lugar da arte enquanto o player carrega; se o clipe não existir, o card
//  é o de sempre e ninguém percebe ausência; e quando o loop é interrompido
//  (Reduce Motion, bateria fraca, app em background) o que sobra é a
//  ilustração, não um buraco.
//
//  O CLIPE CHEGA DEPOIS
//
//  Os clipes são On-Demand Resources (ver ContentPacks.swift). Na primeira
//  vez que uma capa aparece, o clipe dela (~1,6 MB) baixa enquanto a capa
//  estática já está na tela, e entra pelo mesmo fade de sempre. Sem rede, a
//  capa simplesmente fica estática.
//
//  POR QUE AVPlayerLooper E NÃO seek(to: .zero)
//
//  O truque comum — observar `AVPlayerItemDidPlayToEndTime` e voltar pro
//  começo — dá um engasgo visível a cada volta, porque o seek acontece DEPOIS
//  do item terminar. O `AVPlayerLooper` mantém o próximo item já enfileirado
//  e a emenda é feita pelo próprio AVFoundation.
//
//  Somado ao crossfade que o optimize_motion.py grava no arquivo, o loop fica
//  contínuo nos dois níveis: sem engasgo de player e sem salto de imagem.
//
//  ONDE ISTO É USADO
//
//  Só em duas telas, as duas com capa grande e foco único: o hero da Home
//  ("THIS WEEK") e o header do detalhe da história. NÃO vai na grade da
//  Library nem nos thumbs — meia dúzia de AVPlayerLayer decodificando dentro
//  de um ScrollView é memória e bateria queimadas por um efeito que ninguém
//  registra num card de 160pt.
//  ────────────────────────────────────────────────────────────────────────────

import AVFoundation
import SwiftUI
import UIKit

// MARK: - Camada de vídeo

/// UIView cuja própria layer é a AVPlayerLayer.
///
/// Trocar `layerClass` evita a camada extra que existiria se a AVPlayerLayer
/// fosse adicionada como sublayer — e evita ter que sincronizar o frame dela
/// na mão a cada mudança de tamanho.
final class LoopingVideoView: UIView {

    override class var layerClass: AnyClass { AVPlayerLayer.self }

    private var playerLayer: AVPlayerLayer {
        // swiftlint:disable:next force_cast
        layer as! AVPlayerLayer
    }

    private var player: AVQueuePlayer?
    private var looper: AVPlayerLooper?
    private var readyObservation: NSKeyValueObservation?

    /// Disparado quando há quadro pronto pra exibir. É o gatilho do fade.
    var onReadyForDisplay: (() -> Void)?

    func configure(url: URL) {
        guard player == nil else { return }

        let queue = AVQueuePlayer()
        // Os clipes já vêm sem faixa de áudio, mas ser explícito garante que
        // este player jamais dispute a sessão de áudio com a narração.
        queue.isMuted = true
        // Sem isto, um loop decorativo de 4s segura a tela acesa
        // indefinidamente — o default do AVPlayer é `true`.
        queue.preventsDisplaySleepDuringVideoPlayback = false

        looper = AVPlayerLooper(player: queue, templateItem: AVPlayerItem(url: url))
        playerLayer.player = queue
        // Combina com o `.aspectRatio(5/4, contentMode: .fill)` da imagem
        // embaixo, pra vídeo e capa ficarem alinhados pixel a pixel.
        playerLayer.videoGravity = .resizeAspectFill
        player = queue

        readyObservation = playerLayer.observe(\.isReadyForDisplay, options: [.initial, .new]) { [weak self] layer, _ in
            guard layer.isReadyForDisplay else { return }
            Task { @MainActor in self?.onReadyForDisplay?() }
        }
    }

    func setPlaying(_ playing: Bool) {
        if playing {
            player?.play()
        } else {
            player?.pause()
        }
    }

    func teardown() {
        readyObservation = nil
        player?.pause()
        playerLayer.player = nil
        looper?.disableLooping()
        looper = nil
        player = nil
    }
}

private struct LoopingVideo: UIViewRepresentable {

    let url: URL
    let isPlaying: Bool
    let onReady: () -> Void

    func makeUIView(context: Context) -> LoopingVideoView {
        let view = LoopingVideoView()
        view.backgroundColor = .clear
        view.onReadyForDisplay = onReady
        view.configure(url: url)
        view.setPlaying(isPlaying)
        return view
    }

    func updateUIView(_ view: LoopingVideoView, context: Context) {
        view.onReadyForDisplay = onReady
        view.setPlaying(isPlaying)
    }

    static func dismantleUIView(_ view: LoopingVideoView, coordinator: ()) {
        view.teardown()
    }
}

// MARK: - Capa

struct MotionCover: View {

    let story: Story

    /// Nome do imageset da capa. Vem do chamador, que já checou que existe —
    /// assim esta view não repete a checagem nem precisa de placeholder.
    let imageName: String

    /// Desligue em contextos onde o loop não se paga (grades, listas).
    var motionEnabled: Bool = true

    @Environment(\.scenePhase) private var scenePhase
    @Environment(\.accessibilityReduceMotion) private var reduceMotion

    /// A view está montada e visível? `onAppear`/`onDisappear` cobrem troca de
    /// tab e navegação — em TabView os dois disparam na troca.
    @State private var onScreen = false
    @State private var videoOpacity: Double = 0

    /// O clipe, quando já está acessível. Preenchido por `loadClip()`.
    @State private var clipURL: URL?

    /// Segura o pacote do clipe no device enquanto esta capa existir.
    @State private var clipAccess: ContentPackAccess?

    /// Tudo o que precisa ser verdade pra animar, menos ter o clipe. É também
    /// a condição pra BAIXAR o clipe: com Reduce Motion ou bateria fraca o
    /// vídeo nunca tocaria, então nem vale gastar rede com ele.
    private var wantsMotion: Bool {
        motionEnabled
            && onScreen
            && scenePhase == .active
            && !reduceMotion
            && !MotionCatalog.isLowPowerMode
    }

    private var shouldPlay: Bool {
        clipURL != nil && wantsMotion
    }

    var body: some View {
        ZStack {
            Image(imageName)
                .resizable()
                .aspectRatio(5/4, contentMode: .fill)

            if let clipURL, shouldPlay {
                LoopingVideo(url: clipURL, isPlaying: true) {
                    // Meio segundo: rápido o bastante pra não parecer
                    // carregamento, lento o bastante pra ninguém ver a troca.
                    withAnimation(.easeIn(duration: 0.5)) { videoOpacity = 1 }
                }
                .opacity(videoOpacity)
                // O card inteiro é um botão; o vídeo não pode comer o toque.
                .allowsHitTesting(false)
            }
        }
        .onAppear { onScreen = true }
        .onDisappear {
            onScreen = false
            videoOpacity = 0
        }
        .onChange(of: shouldPlay) { _, playing in
            // Zera a opacidade ao sair do ar pra que a próxima entrada volte
            // pelo fade, e não com o vídeo já aceso sobre a capa.
            if !playing { videoOpacity = 0 }
        }
        // Sair da tela no meio do download cancela o download — quem
        // passou rápido pela capa não precisa do clipe.
        .task(id: wantsMotion) {
            guard wantsMotion, clipURL == nil else { return }
            await loadClip()
        }
    }

    private func loadClip() async {
        // Falha (sem rede, sem espaço, clipe sem tag) é silenciosa. Se o
        // arquivo não aparecer, fica a capa estática — exatamente o que
        // existia antes do motion.
        clipAccess = try? await ContentPackAccess.fetch(.motion(storyID: story.id))
        guard !Task.isCancelled else { return }
        clipURL = MotionCatalog.url(slug: story.id)
    }
}
