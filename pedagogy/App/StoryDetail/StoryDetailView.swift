//
//  StoryDetailView.swift
//  pedagogy
//
//  ─── STORY DETAIL ───────────────────────────────────────────────────────────
//  Landing entre HomeView (grid de cards) e ReaderView (leitura em si).
//
//  LAYOUT
//
//    ┌─────────────────────────────┐
//    │  ← back                      │  ← toolbar minimal
//    │                              │
//    │  ┌────────────────────────┐  │
//    │  │    COVER (5:4 grande) │  │  ← hero image
//    │  │                        │  │
//    │  └────────────────────────┘  │
//    │                              │
//    │        The House of Clocks   │  ← title Alfa Slab
//    │        A Fellwick Mystery    │  ← subtitle Lora italic
//    │                              │
//    │   [15 min] [3 chapters] [•]  │  ← meta chips
//    │                              │
//    │  Wren is spending the        │  ← summary Lora
//    │  summer with her great-aunt  │
//    │  in a village she has never  │
//    │  heard of…                   │
//    │                              │
//    │  ─── Chapters ───            │
//    │                              │
//    │  ①  The Backwards Clock    │  ← chapter breakdown
//    │      6 pages                 │
//    │  ②  Don't Look Behind You  │
//    │      5 pages                 │
//    │  ③  The Key                 │
//    │      7 pages                 │
//    │                              │
//    │                              │
//    │  ┌────────────────────────┐  │  ← sticky CTA
//    │  │    Start reading  →    │  │
//    │  └────────────────────────┘  │
//    └─────────────────────────────┘
//
//  CTA MUDA baseado em progresso:
//    • Nunca abriu:   "Start reading"
//    • Em progresso:  "Continue" (+ barra de progresso acima)
//    • Terminou:      "Read again"
//
//  Se `story.isPremium && !store.isPremium` — abre PaywallView em vez do
//  ReaderView. Não escondemos o CTA — o usuário ainda pode tocar e o paywall
//  é a fricção intencional pra converter.
//  ────────────────────────────────────────────────────────────────────────────

import SwiftUI

struct StoryDetailView: View {
    let story: Story

    @Environment(LibraryProgress.self) private var library
    @Environment(Store.self) private var store
    @Environment(AudioPlayerManager.self) private var audio
    @Environment(\.dismiss) private var dismiss

    @State private var isReaderPresented = false
    @State private var isPaywallPresented = false

    private var progress: StoryProgress { library.progress(for: story.id) }

    /// Fração 0..1. Baseada em capítulos (nova granularidade: cada chapter é
    /// uma "página" única no reader). Um usuário no chapter 1 mostra 33%, no
    /// chapter 2 (último) mostra 66%. Finished sempre = 100%.
    private var progressFraction: Double {
        if progress.isFinished { return 1 }
        guard !story.chapters.isEmpty else { return 0 }
        return min(1, Double(progress.chapterIndex) / Double(story.chapters.count))
    }

    private var ctaLabel: String {
        // Bloqueada e user não é premium → CTA vira convite explícito
        // pra assinar, não "start reading" (que iria abrir e frustrar).
        if !story.isFreeToRead() && !store.isPremium {
            return "Unlock story"
        }
        if progress.isFinished { return "Read again" }
        if progress.isInProgress { return "Continue" }
        return "Start reading"
    }

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: Theme.Space.xxl) {
                // ─── BACK BUTTON ───────────────────────────────────────
                // Vive dentro do scroll content, no topo. Alinhado à
                // esquerda respeitando o padding lateral da screen
                // (Theme.Space.lg — mesmo padding dos outros elementos).
                // Rola junto — sai da tela ao rolar, edge-swipe do iOS
                // continua funcionando pra voltar.
                Button(action: { dismiss() }) {
                    BackButtonLabel()
                }
                .accessibilityLabel("Back")

                // ─── COVER ─────────────────────────────────────────────
                LargeCoverImage(story: story)

                // ─── TITLE BLOCK ───────────────────────────────────────
                VStack(alignment: .leading, spacing: Theme.Space.sm) {
                    Text(story.title)
                        .displayTitle(size: 36)
                        .multilineTextAlignment(.leading)
                        .fixedSize(horizontal: false, vertical: true)

                    if let subtitle = story.subtitle {
                        Text(subtitle)
                            .font(.body(17, weight: .medium))
                            .foregroundStyle(Theme.Colors.textMuted)
                            .italic()
                    }
                }

                // ─── META CHIPS ────────────────────────────────────────
                MetaChipRow(story: story, progress: progress)

                // ─── SUMMARY ───────────────────────────────────────────
                Text(story.summary)
                    .readingBody(size: 16)

                // ─── CHAPTERS SECTION ──────────────────────────────────
                VStack(alignment: .leading, spacing: Theme.Space.md) {
                    SectionHeader(title: "Chapters")

                    ForEach(Array(story.chapters.enumerated()), id: \.offset) { index, chapter in
                        ChapterRow(
                            chapter: chapter,
                            state: chapterState(for: index),
                            accent: Theme.Colors.primary
                        )
                    }
                }

                Spacer(minLength: 100)  // room pro sticky CTA (tab bar hidden nesta tela)
            }
            .padding(.horizontal, Theme.Space.lg)
            .padding(.top, Theme.Space.md)
            .padding(.bottom, Theme.Space.xl)
        }
        .background(Theme.Colors.bg.ignoresSafeArea())
        .safeAreaInset(edge: .bottom) {
            ctaBar
        }
        // Esconde a tab bar quando o user navega pra StoryDetail —
        // convenção iOS: tab bar some em telas de detalhe, aparece só
        // nas raízes das tabs (Home / Library).
        .toolbar(.hidden, for: .tabBar)
        // Esconde a nav bar (title bar) inteira. Back button vira parte
        // do scroll content (no topo), rola junto com a cover.
        .toolbar(.hidden, for: .navigationBar)
        .fullScreenCover(isPresented: $isReaderPresented) {
            ReaderView(story: story)
        }
        .sheet(isPresented: $isPaywallPresented) {
            PaywallView(source: "story_detail")
        }
    }

    // MARK: - CTA bar

    /// Barra sticky do bottom. Vive numa computed property (não inline no
    /// `.safeAreaInset`) pra ser type-checked separada do `body` — o body
    /// já é uma única expressão enorme (ScrollView + 6 modifiers) e cada
    /// sub-expressão que sai dela alivia o solver.
    private var ctaBar: some View {
        StickyCTABar(
            label: ctaLabel,
            accent: Theme.Colors.primary,
            progressFraction: progress.isInProgress ? progressFraction : nil,
            onTap: startReadingTapped,
            onListen: listenAction
        )
    }

    /// Ação do botão Listen — `nil` esconde o botão (sem MP3 no bundle pro
    /// chapter que abriria; silêncio é melhor que botão morto).
    ///
    /// ⚠️ NÃO reescrever como `hasAudioForNextChapter ? listenTapped : nil`
    /// dentro do body. Era exatamente isso que causava o
    /// "Ambiguous use of 'init'" no `ScrollView`: um ternário que junta uma
    /// referência de método @MainActor (`listenTapped`) com `nil` deixa o
    /// type-checker com dois caminhos igualmente válidos pra chegar em
    /// `(() -> Void)?` (converter a isolação antes ou depois de embrulhar
    /// no Optional). Ele não decide, e o erro estoura no call site mais
    /// externo que também tem 2 candidatos — `ScrollView.init`.
    /// `guard` + closure literal dá UM caminho só.
    private var listenAction: (() -> Void)? {
        guard hasAudioForNextChapter else { return nil }
        return { listenTapped() }
    }

    // MARK: - Actions

    private func startReadingTapped() {
        // Regra de acesso centralizada em Story.isFreeToRead(): considera
        // isPremium + janela semanal (story of the week fica free por 7 dias).
        if story.isFreeToRead() || store.isPremium {
            isReaderPresented = true
        } else {
            // Abre o paywall direto. O parental gate mora DENTRO dele, nos
            // pontos de ação (comprar, Terms, Privacy) — ver PaywallView.
            isPaywallPresented = true
        }
    }

    /// Chamado pelo botão "Listen" no StickyCTABar. Toca o chapter que
    /// o CTA de leitura abriria (mesma lógica de "onde continuar"). Se
    /// story está bloqueada, redireciona pro paywall igual o Read.
    private func listenTapped() {
        if !story.isFreeToRead() && !store.isPremium {
            isPaywallPresented = true
            return
        }
        audio.play(story: story, chapter: chapterToStart)
    }

    /// Qual chapter começar. Mesma regra do reader: se finished, do 1
    /// (re-listen); senão do chapter em progresso.
    private var chapterToStart: Int {
        if progress.isFinished { return 1 }
        // chapterIndex é 0-indexed; chapters são 1-indexed na UI/audio.
        return max(1, progress.chapterIndex + 1)
    }

    /// Existe MP3 no bundle pro chapter que seria tocado? Se não, esconde
    /// o botão Listen do CTA bar. Falha silenciosa (não confunde usuário
    /// com "áudio indisponível" durante o processo gradual de gerar todos).
    private var hasAudioForNextChapter: Bool {
        let name = "\(story.id)-ch\(chapterToStart)"
        return Bundle.main.url(forResource: name, withExtension: "mp3", subdirectory: "Content/Audio") != nil
            || Bundle.main.url(forResource: name, withExtension: "mp3") != nil
    }

    // MARK: - Helpers

    private func chapterState(for index: Int) -> ChapterRow.State {
        if progress.isFinished { return .completed }
        if index < progress.chapterIndex { return .completed }
        if index == progress.chapterIndex && progress.isInProgress { return .current }
        return .upcoming
    }
}

// MARK: - Large Cover Image

/// Cover em tamanho maior que o card da home. Aspect 5:4, largura total do
/// content area (- padding). Traço grosso + sombra hard.
///
/// Quando a história está bloqueada (`!isFreeToRead()`), adiciona badge
/// PREMIUM no canto superior direito. NÃO usa overlay dessaturado como
/// os thumbs — hero grande fica linda vista assim, escurecer descaracteriza.
/// O badge sozinho + o CTA "Start reading" abrindo paywall já sinaliza claro.
private struct LargeCoverImage: View {
    let story: Story

    var body: some View {
        ZStack(alignment: .topTrailing) {
            ZStack {
                Theme.Colors.bgSepia

                if let name = story.coverImage, UIImage(named: name) != nil {
                    MotionCover(story: story, imageName: name)
                } else {
                    placeholder
                }
            }
            .aspectRatio(5/4, contentMode: .fit)
            .frame(maxWidth: .infinity)
            .clipShape(RoundedRectangle(cornerRadius: Theme.Radius.lg))
            .overlay(
                RoundedRectangle(cornerRadius: Theme.Radius.lg)
                    .stroke(Theme.Colors.stroke, lineWidth: Theme.Stroke.thick)
            )
            .hardShadow(
                RoundedRectangle(cornerRadius: Theme.Radius.lg),
                offset: CGSize(width: 5, height: 6)
            )

            // Badge PREMIUM — só aparece se história gated
            if !story.isFreeToRead() {
                HStack(spacing: 5) {
                    Image(systemName: "lock.fill")
                        .font(.system(size: 11, weight: .bold))
                    Text("PREMIUM")
                        .font(.ui(12, weight: .bold))
                        .kerning(0.8)
                }
                .foregroundStyle(Color.white)
                .padding(.horizontal, Theme.Space.md)
                .padding(.vertical, 7)
                .background(
                    Capsule()
                        .fill(Color.black.opacity(0.85))
                        .overlay(
                            Capsule()
                                .stroke(Color.white.opacity(0.15), lineWidth: 0.5)
                        )
                )
                .padding(Theme.Space.md)
            }
        }
    }

    private var placeholder: some View {
        ZStack {
            Grain(opacity: 0.06, color: Theme.Colors.textMuted)

            VStack(spacing: Theme.Space.sm) {
                Image(systemName: "book.closed.fill")
                    .font(.system(size: 56, weight: .light))
                    .foregroundStyle(Theme.Colors.textMuted.opacity(0.5))

                Text(story.coverImage ?? "no coverImage set")
                    .font(.ui(11, weight: .semibold))
                    .foregroundStyle(Theme.Colors.textMuted.opacity(0.7))

                Text("5:4 · 1432×1146 @4x")
                    .font(.ui(10, weight: .medium))
                    .foregroundStyle(Theme.Colors.textMuted.opacity(0.5))
            }
        }
    }
}

// MARK: - Meta Chip Row

private struct MetaChipRow: View {
    let story: Story
    let progress: StoryProgress

    var body: some View {
        HStack(spacing: Theme.Space.sm) {
            Chip(icon: "clock", text: "\(story.readingTimeMinutes) min")
            Chip(icon: "book", text: "\(story.chapters.count) chapters")

            if progress.isFinished {
                Chip(
                    icon: "checkmark.circle.fill",
                    text: "Finished",
                    color: Theme.Colors.ink
                )
            }

            Spacer()
        }
    }
}

private struct Chip: View {
    let icon: String
    let text: String
    var color: Color = Theme.Colors.textMuted

    var body: some View {
        HStack(spacing: 4) {
            Image(systemName: icon)
                .font(.system(size: 10, weight: .bold))
            Text(text)
                .font(.ui(11, weight: .bold))
        }
        .foregroundStyle(color)
        .padding(.horizontal, Theme.Space.sm + 2)
        .padding(.vertical, Theme.Space.xs + 1)
        .background(
            Capsule()
                .fill(Theme.Colors.track)
        )
    }
}

// MARK: - Section Header

private struct SectionHeader: View {
    let title: String

    var body: some View {
        HStack(spacing: Theme.Space.sm) {
            Text(title)
                .font(.display(20, weight: .bold))
                .foregroundStyle(Theme.Colors.ink)
            Rectangle()
                .fill(Theme.Colors.border)
                .frame(height: 1)
        }
    }
}

// MARK: - Chapter Row

private struct ChapterRow: View {
    let chapter: Chapter
    let state: State
    let accent: Color

    enum State {
        case completed
        case current
        case upcoming
    }

    var body: some View {
        HStack(alignment: .center, spacing: Theme.Space.md) {
            // Circle badge com número ou check
            ZStack {
                Circle()
                    .fill(circleFill)
                    .frame(width: 36, height: 36)
                    .overlay(
                        Circle()
                            .stroke(circleStroke, lineWidth: Theme.Stroke.normal)
                    )

                if state == .completed {
                    Image(systemName: "checkmark")
                        .font(.system(size: 14, weight: .bold))
                        .foregroundStyle(Theme.Colors.onAccent)
                } else {
                    Text("\(chapter.number)")
                        .font(.ui(14, weight: .bold))
                        .foregroundStyle(numberColor)
                }
            }

            VStack(alignment: .leading, spacing: 2) {
                Text(chapter.title)
                    .font(.display(16, weight: state == .current ? .bold : .semibold))
                    .foregroundStyle(Theme.Colors.ink)

                Text("\(chapter.pages.count) pages")
                    .font(.ui(11, weight: .medium))
                    .foregroundStyle(Theme.Colors.textFaint)
            }

            Spacer()

            if state == .current {
                Text("HERE")
                    .font(.ui(9, weight: .bold))
                    .foregroundStyle(accent)
                    .padding(.horizontal, Theme.Space.sm)
                    .padding(.vertical, 4)
                    .background(
                        Capsule().fill(accent.opacity(0.15))
                    )
            }
        }
        .padding(.vertical, Theme.Space.sm)
    }

    private var circleFill: Color {
        switch state {
        case .completed: return accent
        case .current:   return Theme.Colors.surface
        case .upcoming:  return Theme.Colors.surface
        }
    }

    private var circleStroke: Color {
        switch state {
        case .completed: return accent
        case .current:   return accent
        case .upcoming:  return Theme.Colors.border
        }
    }

    private var numberColor: Color {
        switch state {
        case .completed: return Theme.Colors.onAccent
        case .current:   return accent
        case .upcoming:  return Theme.Colors.textMuted
        }
    }
}

// MARK: - Sticky CTA Bar

/// Barra grudada no bottom safe area com o CTA principal + progress bar
/// opcional (só aparece se a história está em andamento).
private struct StickyCTABar: View {
    let label: String
    let accent: Color
    let progressFraction: Double?
    let onTap: () -> Void
    /// Opcional. Se fornecido, renderiza botão circular "Listen" à esquerda
    /// do CTA principal. Se nil (áudio não disponível pro chapter), o CTA
    /// principal ocupa toda a largura como antes.
    var onListen: (() -> Void)? = nil

    var body: some View {
        VStack(spacing: Theme.Space.sm) {
            if let fraction = progressFraction {
                ProgressBar(fraction: fraction, color: accent)
                    .frame(height: 4)
                    .padding(.horizontal, Theme.Space.xl)
            }

            HStack(spacing: Theme.Space.md) {
                // ─── LISTEN BUTTON (opcional) ─────────────────────
                // Botão circular à esquerda do CTA principal. Aparece só
                // quando o áudio está disponível pro chapter que abriria.
                if let onListen = onListen {
                    PressBounce(scaleTo: 0.90, action: onListen) {
                        ListenButtonLabel(accent: accent)
                    }
                    .accessibilityLabel("Listen")
                }

                // ─── MAIN CTA ──────────────────────────────────────
                PressBounce(action: onTap) {
                    HStack(spacing: Theme.Space.sm) {
                        Text(label)
                            .font(.ui(16, weight: .bold))
                        Image(systemName: "arrow.right")
                            .font(.system(size: 14, weight: .bold))
                    }
                    .foregroundStyle(Theme.Colors.onAccent)
                    .frame(maxWidth: .infinity, minHeight: Touch.min + 8)
                    .background(
                        RoundedRectangle(cornerRadius: Theme.Radius.md)
                            .fill(accent)
                            .overlay(
                                RoundedRectangle(cornerRadius: Theme.Radius.md)
                                    .stroke(Theme.Colors.stroke, lineWidth: Theme.Stroke.thick)
                            )
                    )
                    .hardShadow(
                        RoundedRectangle(cornerRadius: Theme.Radius.md),
                        offset: CGSize(width: 3, height: 4)
                    )
                }
            }
            .padding(.horizontal, Theme.Space.lg)
            .padding(.bottom, Theme.Space.md)
        }
        .padding(.top, Theme.Space.sm)
        .background(
            // Fade sutil do bg pra dar sensação de camada acima do conteúdo
            // Fade forte do bg pra esconder texto que estaria passando por
            // trás do CTA. endPoint=.bottom (não .center) garante que o
            // gradient cobre a barra toda com o creme opaco na parte de
            // baixo, evitando o texto do summary vazar visivelmente por
            // trás do botão rosa.
            LinearGradient(
                colors: [Theme.Colors.bg.opacity(0), Theme.Colors.bg, Theme.Colors.bg],
                startPoint: .top,
                endPoint: .bottom
            )
            .ignoresSafeArea()
        )
    }
}

// MARK: - Progress Bar (interno — duplicado do StoryCard mas privado aqui)

private struct ProgressBar: View {
    let fraction: Double
    let color: Color

    var body: some View {
        GeometryReader { geo in
            ZStack(alignment: .leading) {
                Capsule().fill(Theme.Colors.track)
                Capsule()
                    .fill(color)
                    .frame(width: geo.size.width * fraction)
                    .animation(.spring(response: 0.6, dampingFraction: 0.8), value: fraction)
            }
        }
    }
}

// MARK: - Back Button Label

/// Extraído do body do StoryDetailView pra aliviar o type-checker (o body
/// é uma expressão só, e cada pedaço fora dela ajuda). Vale manter, mas
/// NÃO era a causa do "Ambiguous use of 'init'" no ScrollView — a causa
/// real era o ternário `cond ? listenTapped : nil`; ver `listenAction`.
///
/// Se um dia precisar adicionar mais um back button noutra tela, este
/// componente pode virar público num arquivo próprio.
private struct BackButtonLabel: View {
    var body: some View {
        let circleBackground = Circle()
            .fill(Theme.Colors.surface)
            .overlay(
                Circle().stroke(Theme.Colors.border, lineWidth: Theme.Stroke.hair)
            )

        Image(systemName: "chevron.left")
            .font(.system(size: 15, weight: .bold))
            .foregroundStyle(Theme.Colors.ink)
            .frame(width: 36, height: 36)
            .background(circleBackground)
    }
}

// MARK: - Listen Button Label

/// Extraído do StickyCTABar pra manter o body dele leve. Estruturalmente
/// idêntico ao inline anterior. (Não era a causa do erro de ambiguidade —
/// ver `StoryDetailView.listenAction`.)
private struct ListenButtonLabel: View {
    let accent: Color

    var body: some View {
        let circleBackground = Circle()
            .fill(Theme.Colors.surface)
            .overlay(
                Circle().stroke(Theme.Colors.stroke, lineWidth: Theme.Stroke.thick)
            )

        Image(systemName: "play.fill")
            .font(.system(size: 16, weight: .bold))
            .foregroundStyle(accent)
            .frame(width: Touch.min + 8, height: Touch.min + 8)
            .background(circleBackground)
            .hardShadow(Circle(), offset: CGSize(width: 3, height: 4))
    }
}
