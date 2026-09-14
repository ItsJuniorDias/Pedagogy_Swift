//
//  MiniPlayerView.swift
//  pedagogy
//
//  ─── MINI PLAYER ────────────────────────────────────────────────────────────
//  Bar persistente na parte inferior das tabs quando algo está tocando.
//  Some quando nowPlaying == nil (idle state).
//
//  LAYOUT
//
//    ╭─────────────────────────────────────────────────╮
//    │            ──────────────                        │
//    │ [cover]  The Fox... · Ch 1       1×   ▐▐    ×   │
//    ╰─────────────────────────────────────────────────╯
//
//    • Cover 40×40 rounded
//    • Título + chapter number, 1 linha cada
//    • Speed toggle (cicla 1× → 1.25× → 1.5× → 0.75×)
//    • Play/pause icon
//    • Close (para playback)
//    • Progress capsule recuada no topo do card
//
//  FORMA
//
//  Card solto, cantos de 32pt, contorno inteiro, 8pt de margem embaixo e nas
//  laterais. A referência é a cápsula flutuante da tab bar logo abaixo: duas
//  peças soltas do mesmo tipo, não uma faixa colada na base sob uma cápsula.
//
//  POSICIONAMENTO
//
//  Fica no MainTabView via .safeAreaInset(edge: .bottom) aplicado ao conteúdo
//  de CADA tab — não ao TabView. Ver `withMiniPlayer` lá, que explica por quê
//  (e por que o tabViewBottomAccessory do iOS 26 não serviu).
//
//  TAP NA BAR
//
//  Tap no card → abre StoryDetail da story que está tocando (deep link
//  reuso da infraestrutura de notif). Isso permite ao usuário voltar pro
//  reader/detail rapidamente enquanto ouve.
//  ────────────────────────────────────────────────────────────────────────────

import SwiftUI

struct MiniPlayerView: View {
    @Environment(AudioPlayerManager.self) private var audio

    /// Texto do preamble mostrado durante transição entre capítulos
    /// (auto-play do próximo). nil quando não há transição. Renderiza
    /// como overlay sobre o card padrão, com fade in/out suave.
    let preambleText: String?

    /// Callback quando o usuário toca no card (não nos botões). Padrão:
    /// abrir StoryDetail da story que toca. Ficar externo mantém o
    /// mini-player desacoplado do sistema de navegação.
    let onTap: (String) -> Void

    /// Raio do card. Fora da escala `Theme.Radius` (que para em 24) de
    /// propósito: aqui o card precisa rimar com a cápsula flutuante da tab
    /// bar logo abaixo, não com os cards de conteúdo.
    ///
    /// O card tem ~59pt de altura, então o SwiftUI clampeia esse raio em
    /// metade da altura e o resultado é uma cápsula. Deixado em 32 mesmo
    /// assim: se um dia o card crescer, ele volta a ser um retângulo com
    /// cantos generosos em vez de virar um comprimido.
    private let cardRadius: CGFloat = 32

    private var cardShape: RoundedRectangle {
        RoundedRectangle(cornerRadius: cardRadius, style: .continuous)
    }

    var body: some View {
        // Só renderiza quando algo tá tocando (playing OR paused mas
        // carregado). Idle/error = mini-player sumiu.
        if let np = audio.nowPlaying {
            ZStack {
                content(np: np)
                // Preamble overlay — cobre o card durante os 2s de transição
                if let text = preambleText {
                    preambleOverlay(text: text)
                }
            }
            // Margens que soltam o card das bordas. A de baixo (8pt) é o
            // respiro pedido; a horizontal existe porque sem ela as pontas
            // arredondadas encostariam na borda da tela e o raio pareceria
            // um erro de recorte em vez de uma escolha. Mesmo valor nos dois
            // eixos pra leitura simétrica.
            .padding(.horizontal, Theme.Space.sm)
            .padding(.bottom, Theme.Space.sm)
            .animation(.easeInOut(duration: 0.3), value: preambleText)
            .transition(.move(edge: .bottom).combined(with: .opacity))
        }
    }

    // MARK: - Preamble overlay

    @ViewBuilder
    private func preambleOverlay(text: String) -> some View {
        VStack(spacing: 4) {
            Text("UP NEXT")
                .font(.ui(9, weight: .bold))
                .tracking(1.5)
                .foregroundStyle(Theme.Colors.primary)
            Text(text)
                .font(.display(14, weight: .bold))
                .foregroundStyle(Theme.Colors.ink)
                .lineLimit(1)
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        // Mesma forma do card: um retângulo opaco aqui vazaria pelos cantos
        // arredondados durante os 2s de transição.
        .background(cardShape.fill(Theme.Colors.surface))
        .transition(.opacity)
    }

    @ViewBuilder
    private func content(np: NowPlaying) -> some View {
        VStack(spacing: 0) {
            // ─── Progress bar fina no topo ────────────────────────
            // Recuada nas laterais: encostada nas bordas ela entraria na
            // curva dos cantos e apareceria com as pontas comidas.
            ProgressStrip(fraction: fraction)
                .padding(.horizontal, Theme.Space.xxl)
                .padding(.top, Theme.Space.xs)

            // ─── Body do card ─────────────────────────────────────
            HStack(spacing: Theme.Space.md) {
                // Cover
                Button {
                    onTap(np.storyID)
                } label: {
                    coverImage(np: np)
                }
                .buttonStyle(.plain)

                // Título + chapter
                Button {
                    onTap(np.storyID)
                } label: {
                    VStack(alignment: .leading, spacing: 2) {
                        Text(np.storyTitle)
                            .font(.display(14, weight: .bold))
                            .foregroundStyle(Theme.Colors.ink)
                            .lineLimit(1)

                        Text("Chapter \(np.chapter) · \(np.chapterTitle)")
                            .font(.ui(11, weight: .regular))
                            .foregroundStyle(Theme.Colors.textMuted)
                            .lineLimit(1)
                    }
                    .frame(maxWidth: .infinity, alignment: .leading)
                }
                .buttonStyle(.plain)

                // Velocidade — cicla 1× → 1.25× → 1.5× → 0.75×.
                // Fica antes do play/pause de propósito: é o controle menos
                // usado dos três, e o polegar em repouso cai no play.
                Button {
                    audio.cycleSpeed()
                } label: {
                    Text(audio.speed.label)
                        .font(.ui(11, weight: .bold))
                        .monospacedDigit()
                        .foregroundStyle(Theme.Colors.textMuted)
                        .frame(width: 42, height: 28)
                        .background(
                            Capsule().stroke(Theme.Colors.stroke, lineWidth: 1)
                        )
                }
                .buttonStyle(.plain)
                .accessibilityLabel(audio.speed.accessibilityLabel)

                // Play/pause
                Button {
                    audio.togglePlayback()
                } label: {
                    Image(systemName: audio.isPlaying ? "pause.fill" : "play.fill")
                        .font(.system(size: 16, weight: .bold))
                        .foregroundStyle(Theme.Colors.onAccent)
                        .frame(width: 36, height: 36)
                        .background(
                            Circle()
                                .fill(Theme.Colors.primary)
                                .overlay(
                                    Circle().stroke(Theme.Colors.stroke, lineWidth: 1.5)
                                )
                        )
                        .hardShadow(Circle(), offset: CGSize(width: 2, height: 3))
                }
                .accessibilityLabel(audio.isPlaying ? "Pause" : "Play")

                // Close
                Button {
                    audio.stop()
                } label: {
                    Image(systemName: "xmark")
                        .font(.system(size: 12, weight: .bold))
                        .foregroundStyle(Theme.Colors.textMuted)
                        .frame(width: 28, height: 28)
                }
                .accessibilityLabel("Stop playback")
            }
            // 16 e não 12: a ponta arredondada come espaço útil na
            // esquerda, e a capa de 40pt colada nela ficava apertada.
            .padding(.horizontal, Theme.Space.lg)
            .padding(.vertical, Theme.Space.sm)
        }
        .background(cardShape.fill(Theme.Colors.surface))
        // Contorno inteiro no lugar do fio que havia só no topo. Aquele fio
        // fazia sentido quando o card era uma faixa colada na base da tela e
        // ele era a única separação; num card solto, o que define a borda é
        // o contorno todo.
        .overlay(
            cardShape.stroke(Theme.Colors.stroke, lineWidth: Theme.Stroke.hair)
        )
    }

    // MARK: - Cover image

    @ViewBuilder
    private func coverImage(np: NowPlaying) -> some View {
        Group {
            if !np.coverAssetName.isEmpty,
               UIImage(named: np.coverAssetName) != nil {
                Image(np.coverAssetName)
                    .resizable()
                    .aspectRatio(contentMode: .fill)
            } else {
                // Fallback quando cover não existe (build antes de gerar
                // artes ou story sem cover atribuído)
                Rectangle()
                    .fill(Theme.Colors.bgSepia)
                    .overlay(
                        Image(systemName: "book.closed.fill")
                            .foregroundStyle(Theme.Colors.textMuted)
                    )
            }
        }
        .frame(width: 40, height: 40)
        .clipShape(RoundedRectangle(cornerRadius: 6, style: .continuous))
        .overlay(
            RoundedRectangle(cornerRadius: 6, style: .continuous)
                .stroke(Theme.Colors.stroke, lineWidth: 1)
        )
    }

    // MARK: - Progress fraction

    private var fraction: Double {
        guard audio.durationMs > 0 else { return 0 }
        return Double(audio.currentMs) / Double(audio.durationMs)
    }
}

// MARK: - Progress strip

/// Barra fina de progresso, cheia em cinza + fill pink. Fica no TOPO do
/// card do mini-player pra dar sinal visual de andamento sem competir
/// com o conteúdo.
private struct ProgressStrip: View {
    let fraction: Double

    var body: some View {
        GeometryReader { geo in
            ZStack(alignment: .leading) {
                Capsule()
                    .fill(Theme.Colors.border)
                Capsule()
                    .fill(Theme.Colors.primary)
                    .frame(width: geo.size.width * max(0, min(1, fraction)))
            }
        }
        // Capsule em vez de Rectangle, e 3pt em vez de 2: solta do card, uma
        // barra de pontas retas destoa de tudo em volta.
        .frame(height: 3)
    }
}
