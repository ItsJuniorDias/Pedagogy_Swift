//
//  ReaderView.swift
//  pedagogy
//
//  ─── READER ─────────────────────────────────────────────────────────────────
//  Tela de leitura. Full-screen modal (fullScreenCover) — imersiva.
//
//  DECISÃO DE UX: 1 CAPÍTULO = 1 PÁGINA
//
//  Cada capítulo é uma unidade única de leitura. O TabView tem N tabs = N
//  capítulos (3 no piloto), e cada tab é um ScrollView vertical com TODOS
//  os parágrafos do capítulo concatenados. Sem ilustrações inline no reader.
//
//  Por quê? Uma criança de 10 anos lê melhor um capítulo inteiro em fluxo
//  contínuo do que interrompido por múltiplas viradas de página. E a
//  cadência natural de "ler um capítulo por dia" combina com o modelo de
//  cliffhanger que a história tem. Swipe horizontal entre capítulos é a
//  única navegação — simples e clara.
//
//  As ilustrações continuam declaradas no JSON (com prompts embarcados) pra
//  serem usadas em outros contextos futuros — capa do storycard, hero da
//  StoryDetail, print de "chapter opener" se voltar. Reader ignora as pages
//  internas e concatena os paragraphs.
//
//  PROGRESSO
//
//  A cada mudança de tab (chapter), chama `library.updatePosition()`.
//  Salva `chapterIndex = currentIndex, pageIndex = 0` (o pageIndex fica no
//  schema pra futuro-uso mas não é usado pelo reader agora).
//
//  Quando o usuário chega no último capítulo E toca "Back to library",
//  chama `markFinished()`. Antes disso ele pode continuar rolendo — só marcar
//  finished no botão explícito, não em swipe automático.
//
//  RESTAURAÇÃO
//
//  Ao abrir, se já existe progresso salvo, começa no chapter que o usuário
//  parou. "Read again" (finished) reinicia do chapter 0.
//  ────────────────────────────────────────────────────────────────────────────

import SwiftUI

struct ReaderView: View {
    let story: Story

    @Environment(LibraryProgress.self) private var library
    @Environment(\.dismiss) private var dismiss

    /// Índice do capítulo atual (0..<story.chapters.count).
    @State private var currentIndex: Int = 0

    /// Flag pra evitar salvar progresso antes de restaurar (senão o
    /// `onChange(currentIndex)` dispara com 0 na primeira render).
    @State private var didRestore = false

    /// True quando o header "CHAPTER N — Title" do conteúdo está visível
    /// no viewport. Quando sai (scroll pra baixo), o TopBar expande pra
    /// mostrar o mesmo título — evita duplicação estática mas mantém
    /// contexto visível o tempo todo.
    @State private var chapterHeaderVisible = true

    /// Progresso de leitura do capítulo atual (0..1). Alimenta a barra
    /// fina no bottom do TopBar. Reset a 0 ao trocar de chapter.
    @State private var chapterScrollProgress: Double = 0

    private var currentChapter: Chapter {
        story.chapters[safe: currentIndex] ?? story.chapters[0]
    }

    private var isLastChapter: Bool {
        currentIndex == story.chapters.count - 1
    }

    var body: some View {
        ZStack(alignment: .top) {
            Theme.Colors.bg.ignoresSafeArea()

            // ─── PAGED CONTENT ───────────────────────────────────────
            TabView(selection: $currentIndex) {
                ForEach(Array(story.chapters.enumerated()), id: \.offset) { index, chapter in
                    ChapterView(
                        storyID: story.id,
                        chapter: chapter,
                        accent: Theme.Colors.primary,
                        isLastChapter: index == story.chapters.count - 1,
                        onFinishTap: {
                            library.markFinished(storyID: story.id)
                            Analytics.shared.track(.storyComplete, [
                                "content_id": story.id,
                                "source": "reader",
                            ])
                            dismiss()
                        },
                        onHeaderVisibilityChange: { visible in
                            // Só a chapter view ativa reporta — evita
                            // conflito com views pré-renderizadas do
                            // TabView (o iOS pode ter chapters vizinhos
                            // já hidratados pra swipe rápido).
                            guard index == currentIndex else { return }
                            chapterHeaderVisible = visible
                        },
                        onScrollProgressChange: { progress in
                            guard index == currentIndex else { return }
                            chapterScrollProgress = progress
                        }
                    )
                    .tag(index)
                }
            }
            .tabViewStyle(.page(indexDisplayMode: .never))
            .ignoresSafeArea(edges: [.horizontal])

            // ─── TOP BAR ─────────────────────────────────────────────
            TopBar(
                story: story,
                chapterNumber: currentChapter.number,
                chapterTitle: currentChapter.title,
                currentIndex: currentIndex,
                totalChapters: story.chapters.count,
                accent: Theme.Colors.primary,
                showFullTitle: !chapterHeaderVisible,
                scrollProgress: chapterScrollProgress,
                onClose: {
                    saveProgress()
                    dismiss()
                }
            )
        }
        .onAppear {
            restoreProgress()

            // Abertura da leitura. Junto com `story_complete`, é o par que
            // mostra quais histórias prendem e quais são abandonadas —
            // sinal que o RevenueCat não tem como enxergar.
            Analytics.shared.track(.storyOpen, [
                "content_id": story.id,
                "source": "reader",
            ])
        }
        .onChange(of: currentIndex) { _, _ in
            // Ao trocar de chapter (swipe), reseta pra assumir que o novo
            // chapter header está visível (scroll do novo chapter começa
            // no topo). Se não estiver, o próprio ChapterView.onScrollVisibilityChange
            // corrige imediatamente na primeira render.
            chapterHeaderVisible = true
            chapterScrollProgress = 0
            guard didRestore else { return }
            saveProgress()
        }
    }

    // MARK: - Progress persistence

    private func restoreProgress() {
        let saved = library.progress(for: story.id)

        // Se está finished, começa do 0 (é "read again").
        // Senão, restaura chapter salvo (o pageIndex antigo é ignorado —
        // MVP tem 1 chapter = 1 unidade de leitura).
        let targetChapter: Int
        if saved.isFinished {
            targetChapter = 0
        } else {
            targetChapter = min(saved.chapterIndex, story.chapters.count - 1)
        }

        currentIndex = max(0, targetChapter)

        // Delay pra didRestore ativar DEPOIS do binding do TabView aplicar.
        DispatchQueue.main.async {
            didRestore = true
        }
    }

    private func saveProgress() {
        library.updatePosition(
            storyID: story.id,
            chapter: currentIndex,
            page: 0
        )
    }
}

// MARK: - Chapter View (uma tab do TabView)

/// Renderiza um capítulo inteiro: título grande no topo + todos os parágrafos
/// concatenados de todas as `pages` do JSON. Sem ilustrações — reader é
/// text-focused. Se for o último capítulo, mostra "The End" + botão de
/// voltar pra library no fim do scroll.
///
/// AUDIO HIGHLIGHTING
///
/// Quando o AudioPlayerManager está tocando ESTA story + ESTE chapter, a
/// sentença ativa (currentSentenceIndex) fica destacada dentro do parágrafo
/// dela. As outras sentenças ficam dimmed pra guiar a atenção. Se não tá
/// tocando (ou tocando outra story), tudo aparece em cor normal.
private struct ChapterView: View {
    let storyID: String
    let chapter: Chapter
    let accent: Color
    let isLastChapter: Bool
    let onFinishTap: () -> Void

    /// Reporta pro parent (ReaderView) quando o header "CHAPTER N — Title"
    /// do conteúdo aparece ou some do viewport. Usado pra decidir se o
    /// TopBar sticky deve mostrar o título expandido (evita duplicação).
    let onHeaderVisibilityChange: (Bool) -> Void

    /// Reporta scroll progress (0..1) pro parent, que renderiza a barra
    /// de progresso no TopBar. Calculado como offset_y / (content_h - viewport_h).
    let onScrollProgressChange: (Double) -> Void

    @Environment(\.accessibilityReduceMotion) private var reduceMotion
    @Environment(AudioPlayerManager.self) private var audio

    // Estados de animação de entrada — cascata sequencial pra criar
    // sensação de "abertura de capítulo" cinematográfica.
    @State private var chapterNumberAppeared = false
    @State private var titleAppeared = false
    @State private var dividerAppeared = false

    /// Todos os parágrafos do capítulo, concatenados em ordem (ignora a
    /// separação em `pages` do JSON — no reader é fluxo único).
    private var allParagraphs: [String] {
        chapter.pages.flatMap { $0.paragraphs }
    }

    /// Sentenças por parágrafo, pré-computadas. Split usa a MESMA regex de
    /// scripts/generate_timings.py — divergência aqui = sentenças destacadas
    /// erradas.
    private var sentencesByParagraph: [[String]] {
        allParagraphs.map { SentenceSplitter.split($0) }
    }

    /// Índice global da PRIMEIRA sentença de cada parágrafo. Se paragraph 0
    /// tem 3 sentenças e paragraph 1 tem 2, offsets = [0, 3, 5]. Passado
    /// pro SentenceHighlightingParagraph pra ele saber onde começa no
    /// fluxo global de sentenças do chapter.
    private var paragraphSentenceOffsets: [Int] {
        var offsets: [Int] = []
        var running = 0
        for sentences in sentencesByParagraph {
            offsets.append(running)
            running += sentences.count
        }
        return offsets
    }

    /// Índice ativo pra highlighting. nil quando não tocando esta story+chapter
    /// específica. Quando nil, o parágrafo renderiza tudo em cor normal (sem
    /// dim, sem highlight) — comportamento idêntico ao reader puro.
    private var activeSentenceIndex: Int? {
        guard let np = audio.nowPlaying,
              np.storyID == storyID,
              np.chapter == chapter.number
        else { return nil }
        return audio.currentSentenceIndex
    }

    var body: some View {
        ScrollViewReader { proxy in
            ScrollView {
                VStack(alignment: .leading, spacing: Theme.Space.xl) {
                    // Espaço reservado pro top bar não sobrepor o conteúdo
                    Color.clear.frame(height: 70)

                    // ─── CHAPTER HEADER ──────────────────────────────────
                    // Sequência de entrada em cascata:
                    //   0.00s → "CHAPTER N" fade-in + slide down curto
                    //   0.15s → título fade-in + slide down maior
                    //   0.35s → divider expande horizontalmente
                    // Cria a sensação de "abertura de livro" antes do texto
                    // corrido começar. Reduce Motion → tudo aparece instantâneo.
                    VStack(alignment: .leading, spacing: Theme.Space.sm) {
                        Text("CHAPTER \(chapter.number)")
                            .uiLabel(size: 12, weight: .bold, color: accent)
                            .opacity(chapterNumberAppeared ? 1 : 0)
                            .offset(y: chapterNumberAppeared ? 0 : -6)

                        Text(chapter.title)
                            .displayTitle(size: 32)
                            .multilineTextAlignment(.leading)
                            .fixedSize(horizontal: false, vertical: true)
                            .opacity(titleAppeared ? 1 : 0)
                            .offset(y: titleAppeared ? 0 : 8)
                    }
                    .padding(.horizontal, Theme.Space.xl)
                    .padding(.bottom, Theme.Space.md)
                    .onScrollVisibilityChange(threshold: 0.15) { visible in
                        onHeaderVisibilityChange(visible)
                    }

                    // Divider "draw" — expande da esquerda pra direita ao
                    // aparecer. `scaleEffect(x: 0, anchor: .leading)` cresce
                    // como se estivesse sendo traçado.
                    Rectangle()
                        .fill(Theme.Colors.stroke)
                        .frame(height: Theme.Stroke.thin)
                        .padding(.horizontal, Theme.Space.xl)
                        .scaleEffect(x: dividerAppeared ? 1 : 0, anchor: .leading)

                    // ─── PARAGRAPHS ──────────────────────────────────────
                    // Cada parágrafo faz fade-in + slide sutil ao entrar no
                    // viewport durante o scroll. Cria cadência de "descoberta"
                    // sem tirar velocidade da leitura.
                    //
                    // Se o AudioPlayerManager está tocando ESTA story+chapter,
                    // a sentença ativa fica destacada e as outras dim — guia
                    // atenção sem competir com o reader-only quando o áudio
                    // não está ligado.
                    //
                    // ID pra scroll-to: usamos "para-P" pra cada parágrafo.
                    // Granularidade de parágrafo é suficiente pra manter a
                    // sentença ativa visível (sentença cabe no viewport uma
                    // vez o parágrafo dela estiver alinhado).
                    VStack(alignment: .leading, spacing: Theme.Space.lg) {
                        ForEach(Array(sentencesByParagraph.enumerated()), id: \.offset) { pIndex, sentences in
                            SentenceHighlightingParagraph(
                                sentences: sentences,
                                sentenceOffset: paragraphSentenceOffsets[safe: pIndex] ?? 0,
                                activeSentenceIndex: activeSentenceIndex
                            )
                            .id("para-\(pIndex)")
                        }
                    }
                    .padding(.horizontal, Theme.Space.xl)
                    .padding(.top, Theme.Space.sm)

                    // ─── FINISH CTA (último capítulo) ────────────────────
                    if isLastChapter {
                        FinishCTA(accent: accent, onTap: onFinishTap)
                            .padding(.horizontal, Theme.Space.xl)
                            .padding(.top, Theme.Space.xxxl)
                    }

                    Spacer(minLength: Theme.Space.huge)
                }
            }
            // Track scroll progress pra alimentar a barra de progresso no
            // TopBar. `onScrollGeometryChange` (iOS 18+) dispara com metrics
            // do scroll — offset atual + tamanho total do content.
            .onScrollGeometryChange(for: Double.self) { geometry in
                let offset = geometry.contentOffset.y
                let scrollableHeight = max(1, geometry.contentSize.height - geometry.containerSize.height)
                return min(1.0, max(0.0, offset / scrollableHeight))
            } action: { _, progress in
                onScrollProgressChange(progress)
            }
            .onAppear {
                triggerEntranceCascade()
            }
            // Auto-scroll: quando a sentença ativa muda, scrolla pro parágrafo
            // dela. Ancora no `.top` com pequeno padding pra manter contexto
            // visual (não gruda no topo agressivamente).
            //
            // Sem heurística de "usuário rolou manualmente" — pra o tom
            // reflexivo do app, quem tá ouvindo geralmente quer que a
            // sentença apareça. Se atrapalhar, o usuário pausa.
            .onChange(of: activeSentenceIndex) { _, newIndex in
                guard let newIndex else { return }
                // Encontra o parágrafo que contém essa sentença
                for (pIndex, offset) in paragraphSentenceOffsets.enumerated() {
                    let count = sentencesByParagraph[safe: pIndex]?.count ?? 0
                    if newIndex >= offset && newIndex < offset + count {
                        withAnimation(.easeInOut(duration: 0.5)) {
                            proxy.scrollTo("para-\(pIndex)", anchor: .top)
                        }
                        break
                    }
                }
            }
        }
    }

    /// Dispara a cascata de entrada. Chamado no onAppear da ChapterView —
    /// cada capítulo tem sua própria cascata quando o user swipe entre eles.
    ///
    /// Timing:
    ///   0.00s → CHAPTER N (opacity + slide down 6pt)
    ///   0.15s → Title (opacity + slide down 8pt)
    ///   0.35s → Divider (scale x 0 → 1, anchor leading)
    ///
    /// Curva `.smooth` (iOS-nativa) pra evitar bounce artificial. Duração
    /// 0.5s em cada elemento — longa o suficiente pra ser percebida como
    /// "abertura", curta pra não atrasar leitura.
    private func triggerEntranceCascade() {
        // Reduce Motion: pula animação, mostra tudo instantâneo
        if reduceMotion {
            chapterNumberAppeared = true
            titleAppeared = true
            dividerAppeared = true
            return
        }

        // Reset (importante ao voltar pra um chapter já visitado)
        chapterNumberAppeared = false
        titleAppeared = false
        dividerAppeared = false

        withAnimation(.smooth(duration: 0.5)) {
            chapterNumberAppeared = true
        }
        withAnimation(.smooth(duration: 0.5).delay(0.15)) {
            titleAppeared = true
        }
        withAnimation(.smooth(duration: 0.6).delay(0.35)) {
            dividerAppeared = true
        }
    }
}

// MARK: - Top Bar

/// Barra fixa no topo do Reader. Comportamento:
///
///   • Estado default (chapter header visível no scroll):
///     mostra só X à esquerda + counter "N/M" à direita. Título
///     não aparece — evita duplicar o header grande logo abaixo.
///
///   • Estado expandido (scroll passou do chapter header):
///     mostra "Chapter N — Title" no centro com animação suave
///     (opacity + slide vertical), pra manter contexto de onde
///     o usuário está enquanto lê parágrafos longe do header.
///
/// Fundo é cor sólida `bg` (sem `.ultraThinMaterial` blur) e sem
/// `.ignoresSafeArea` — a barra respira dentro do safe area top
/// e não sangra sobre o status bar / notch com efeito translúcido.
private struct TopBar: View {
    /// Necessária pro botão de narração — o player monta o NowPlaying a
    /// partir dela (título, capa, total de capítulos).
    let story: Story

    let chapterNumber: Int
    let chapterTitle: String
    let currentIndex: Int
    let totalChapters: Int
    let accent: Color
    let showFullTitle: Bool
    let scrollProgress: Double
    let onClose: () -> Void

    @Environment(AudioPlayerManager.self) private var audio

    /// O player está com ESTE capítulo desta história — tocando, pausado,
    /// baixando ou com falha? Tocar outra coisa não mexe no botão daqui.
    private var playerHasThisChapter: Bool {
        guard let np = audio.nowPlaying else { return false }
        return np.storyID == story.id && np.chapter == chapterNumber
    }

    private var isPlayingThisChapter: Bool {
        playerHasThisChapter && audio.isPlaying
    }

    private func toggleNarration() {
        if isPlayingThisChapter {
            audio.pause()
        } else {
            // play() já resume quando é o mesmo capítulo carregado, troca
            // quando é outro e tenta de novo depois de uma falha — não
            // precisa distinguir aqui.
            audio.play(story: story, chapter: chapterNumber)
        }
    }

    /// Miolo do botão de narração. O reader é full screen e cobre o
    /// mini-player, então o download da narração (On-Demand Resources) e a
    /// falha dele precisam aparecer aqui mesmo.
    @ViewBuilder
    private var narrationGlyph: some View {
        if playerHasThisChapter, audio.state == .loading {
            ProgressView()
                .controlSize(.small)
                .tint(Theme.Colors.ink)
        } else if playerHasThisChapter, case .error = audio.state {
            Image(systemName: "arrow.clockwise")
                .font(.system(size: 14, weight: .bold))
                .foregroundStyle(Theme.Colors.ink)
        } else {
            Image(systemName: isPlayingThisChapter ? "pause.fill" : "play.fill")
                .font(.system(size: 14, weight: .bold))
                .foregroundStyle(isPlayingThisChapter ? Theme.Colors.onAccent : Theme.Colors.ink)
                // O triângulo do play é opticamente descentrado;
                // 1pt corrige dentro do círculo.
                .offset(x: isPlayingThisChapter ? 0 : 1)
        }
    }

    private var narrationLabel: String {
        guard playerHasThisChapter else { return "Play narration" }
        switch audio.state {
        case .loading: return "Downloading narration"
        case .error:   return "Couldn't load narration, try again"
        default:       return audio.isPlaying ? "Pause narration" : "Play narration"
        }
    }

    var body: some View {
        VStack(spacing: 0) {
            HStack(alignment: .center, spacing: Theme.Space.sm) {
                // Close button
                Button(action: onClose) {
                    Image(systemName: "xmark")
                        .font(.system(size: 15, weight: .bold))
                        .foregroundStyle(Theme.Colors.ink)
                        .frame(width: 36, height: 36)
                        .background(
                            Circle()
                                .fill(Theme.Colors.surface)
                                .overlay(
                                    Circle()
                                        .stroke(Theme.Colors.border, lineWidth: Theme.Stroke.hair)
                                )
                        )
                }
                .accessibilityLabel("Close reader")

                Spacer(minLength: 0)

                // Chapter indicator (center) — só quando expandido.
                // Container reservado (fixedSize false) pra layout não pular
                // ao aparecer/desaparecer — Spacer flexível absorve.
                if showFullTitle {
                    VStack(spacing: 0) {
                        Text("Chapter \(chapterNumber)")
                            .font(.ui(11, weight: .bold))
                            .foregroundStyle(accent)
                        Text(chapterTitle)
                            .font(.ui(13, weight: .semibold))
                            .foregroundStyle(Theme.Colors.textMuted)
                            .lineLimit(1)
                    }
                    .transition(
                        .asymmetric(
                            insertion: .opacity.combined(with: .move(edge: .top)),
                            removal:   .opacity.combined(with: .move(edge: .top))
                        )
                    )
                }

                Spacer(minLength: 0)

                // ─── NARRAÇÃO ────────────────────────────────────────
                // Play/pause do capítulo em tela.
                //
                // Fica no topo e não flutuando sobre o texto: o reader é uma
                // coluna de leitura, e qualquer coisa boiando por cima dela
                // tapa palavra justo quando a criança está acompanhando. Aqui
                // o controle está sempre à mão e nunca no caminho do olho.
                //
                // Some quando o capítulo não tem narração — botão que
                // promete áudio e entrega silêncio é pior que botão ausente.
                if AudioPlayerManager.hasNarration(storyID: story.id, chapter: chapterNumber) {
                    Button(action: toggleNarration) {
                        narrationGlyph
                            .frame(width: 36, height: 36)
                            .background(
                                Circle()
                                    .fill(isPlayingThisChapter ? accent : Theme.Colors.surface)
                                    .overlay(
                                        Circle()
                                            .stroke(Theme.Colors.border, lineWidth: Theme.Stroke.hair)
                                    )
                            )
                    }
                    .accessibilityLabel(narrationLabel)
                }

                // Chapter counter — sempre visível (contexto mínimo)
                Text("\(currentIndex + 1) / \(totalChapters)")
                    .font(.ui(12, weight: .bold))
                    .foregroundStyle(Theme.Colors.textMuted)
                    .frame(minWidth: 48)
            }
            .padding(.horizontal, Theme.Space.md)
            .padding(.vertical, Theme.Space.sm)

            // ─── PROGRESS BAR ────────────────────────────────────────
            // Linha fininha (1.5pt) na base do TopBar. Cresce da esquerda
            // conforme o user rola o capítulo. Cor accent (rosa da marca)
            // sobre trilho neutro sutil. Anima suave com o scroll.
            GeometryReader { geo in
                ZStack(alignment: .leading) {
                    Rectangle()
                        .fill(Theme.Colors.track)

                    Rectangle()
                        .fill(accent)
                        .frame(width: geo.size.width * scrollProgress)
                        .animation(.smooth(duration: 0.2), value: scrollProgress)
                }
            }
            .frame(height: 1.5)
        }
        // Fundo sólido, sem material blur. Não usa ignoresSafeArea —
        // respeita o safe area do notch, sem estender sob a status bar.
        .background(Theme.Colors.bg)
        // Anima a mudança de estado (título aparece/some suave).
        // .smooth é curva iOS-nativa; 0.28s dá tempo pro user perceber.
        .animation(.smooth(duration: 0.28), value: showFullTitle)
    }
}

// MARK: - Finish CTA

/// CTA de fim de história. Animações:
///   • Entrada: fade in + slide up 12pt (0.6s smooth) na primeira vez
///     que aparece no viewport — sensação de "descoberta" ao terminar
///   • Breathing: pulse sutil (scale 1.00 ↔ 1.03) do botão principal,
///     em loop lento (~2s) enquanto o CTA está visível. Convida a
///     tocar sem ser aggressive. Respeita reduce motion.
private struct FinishCTA: View {
    let accent: Color
    let onTap: () -> Void

    @Environment(\.accessibilityReduceMotion) private var reduceMotion
    @State private var hasAppeared = false
    @State private var breathing = false

    var body: some View {
        VStack(spacing: Theme.Space.lg) {
            Rectangle()
                .fill(Theme.Colors.stroke)
                .frame(height: Theme.Stroke.normal)

            VStack(spacing: Theme.Space.sm) {
                Text("The End")
                    .font(.display(28, weight: .bold))
                    .foregroundStyle(Theme.Colors.ink)

                Text("You finished the story.")
                    .font(.body(15, weight: .medium))
                    .foregroundStyle(Theme.Colors.textMuted)
                    .italic()
                    .multilineTextAlignment(.center)
                    .frame(maxWidth: .infinity)
            }
            .padding(.vertical, Theme.Space.md)

            PressBounce(action: onTap) {
                HStack(spacing: Theme.Space.sm) {
                    Text("Back to library")
                        .font(.ui(15, weight: .bold))
                    Image(systemName: "arrow.right")
                        .font(.system(size: 13, weight: .bold))
                }
                .foregroundStyle(Theme.Colors.onAccent)
                .frame(maxWidth: .infinity, minHeight: Touch.min + 4)
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
                // Breathing pulse — subtle scale entre 1.00 e 1.03 em loop.
                // Só o botão pulsa (não o card inteiro), pra chamar
                // atenção sem parecer nervoso.
                .scaleEffect(breathing ? 1.03 : 1.0)
            }
        }
        // Entrada: fade in + slide up 12pt quando aparece pela primeira vez
        .opacity(hasAppeared ? 1 : 0)
        .offset(y: hasAppeared ? 0 : 12)
        .onAppear {
            guard !reduceMotion else {
                hasAppeared = true
                return
            }

            withAnimation(.smooth(duration: 0.6)) {
                hasAppeared = true
            }

            // Start breathing loop depois da entrada terminar
            DispatchQueue.main.asyncAfter(deadline: .now() + 0.7) {
                withAnimation(
                    .easeInOut(duration: 1.8).repeatForever(autoreverses: true)
                ) {
                    breathing = true
                }
            }
        }
    }
}

// MARK: - Sentence-Highlighting Paragraph

/// Parágrafo que suporta highlighting de sentença individual. Renderiza:
///   • Fade-in + slide-up ao entrar no viewport (mesmo do FadeInParagraph antigo)
///   • Sentença ativa (activeSentenceIndex) em cor destaque
///   • Sentenças não-ativas dimmed (quando activeSentenceIndex != nil)
///   • Todo texto em cor normal quando activeSentenceIndex == nil (áudio off)
///
/// Split em sentenças usa `SentenceSplitter` — precisa bater com o Python
/// script que gera os timings, senão as sentenças ficam desalinhadas com o áudio.
///
/// AttributedString em vez de Text+ concatenation porque:
///   • Precisamos foreground color por segmento (Text+ suporta) mas também
///     transitions animadas (Text+ não anima cores por segmento).
///   • AttributedString + Text(_:) anima naturalmente na mudança de content.
private struct SentenceHighlightingParagraph: View {
    let sentences: [String]
    let sentenceOffset: Int
    let activeSentenceIndex: Int?

    @Environment(\.accessibilityReduceMotion) private var reduceMotion
    @State private var hasAppeared = false

    private var isVisible: Bool { reduceMotion || hasAppeared }

    /// Fonte base do parágrafo. Mesma que `readingBody(size: 18)` usava,
    /// só que aqui aplicada por segmento via AttributedString.
    private let fontSize: CGFloat = 18

    var body: some View {
        Text(attributedText)
            .lineSpacing(fontSize * 0.55)
            .fixedSize(horizontal: false, vertical: true)
            .frame(maxWidth: .infinity, alignment: .leading)
            .opacity(isVisible ? 1 : 0)
            .offset(y: isVisible ? 0 : 8)
            .animation(
                reduceMotion ? nil : .easeOut(duration: 0.5),
                value: hasAppeared
            )
            // Anima transições de highlighting (cor/peso das sentenças).
            // 200ms é suficiente pra não parecer flash mas rápido pra
            // acompanhar áudio.
            .animation(
                reduceMotion ? nil : .easeInOut(duration: 0.2),
                value: activeSentenceIndex
            )
            .onScrollVisibilityChange(threshold: 0.15) { visible in
                if visible && !hasAppeared {
                    hasAppeared = true
                }
            }
    }

    /// Constrói o texto attributed com styling por sentença. Recalculado
    /// sempre que activeSentenceIndex muda — barato (sentenças de um
    /// parágrafo típico são 2-8).
    private var attributedText: AttributedString {
        // Fonts pra estados ativo/inativo
        let baseFont: Font = .body(fontSize, weight: .regular)
        let activeFont: Font = .body(fontSize, weight: .semibold)

        // Cores — quando activeSentenceIndex é nil (sem áudio), tudo em
        // textStrong normal (comportamento reader-only). Quando não-nil,
        // ativa fica ink escuro e outras dim.
        let noHighlight = activeSentenceIndex == nil
        let normalColor = Color(Theme.Colors.textStrong)
        let dimColor = Color(Theme.Colors.textStrong).opacity(0.35)
        let activeColor = Color(Theme.Colors.ink)

        var result = AttributedString()
        for (localIdx, sentence) in sentences.enumerated() {
            var chunk = AttributedString(sentence)
            let globalIdx = sentenceOffset + localIdx
            let isActive = globalIdx == activeSentenceIndex

            if noHighlight {
                chunk.foregroundColor = normalColor
                chunk.font = baseFont
            } else if isActive {
                chunk.foregroundColor = activeColor
                chunk.font = activeFont
            } else {
                chunk.foregroundColor = dimColor
                chunk.font = baseFont
            }
            result += chunk

            // Espaço entre sentenças (herda estilo neutral pra não animar)
            if localIdx < sentences.count - 1 {
                result += AttributedString(" ")
            }
        }
        return result
    }
}

// MARK: - Sentence Splitter

/// Split de texto em sentenças. Precisa bater com scripts/generate_timings.py
/// senão o highlighting desalinha do áudio. Regex idêntica:
///
///     (?<=[.!?])\s+(?=\S)
///
/// Split em . ! ? seguido de whitespace + próximo caracter não-whitespace.
/// Aceita falsos positivos em abreviações ("Dr. Smith" → 2 sentenças) —
/// tanto no Python quanto aqui — pra manter alinhamento.
enum SentenceSplitter {
    private static let regex: NSRegularExpression = {
        try! NSRegularExpression(pattern: #"(?<=[.!?])\s+(?=\S)"#)
    }()

    static func split(_ text: String) -> [String] {
        let trimmed = text.trimmingCharacters(in: .whitespacesAndNewlines)
        if trimmed.isEmpty { return [] }

        let ns = trimmed as NSString
        let range = NSRange(location: 0, length: ns.length)
        let matches = regex.matches(in: trimmed, range: range)

        if matches.isEmpty { return [trimmed] }

        var result: [String] = []
        var lastEnd = 0
        for match in matches {
            let sentenceRange = NSRange(location: lastEnd, length: match.range.location - lastEnd)
            let sentence = ns.substring(with: sentenceRange).trimmingCharacters(in: .whitespaces)
            if !sentence.isEmpty { result.append(sentence) }
            lastEnd = match.range.location + match.range.length
        }
        // Última sentença
        if lastEnd < ns.length {
            let sentence = ns.substring(from: lastEnd).trimmingCharacters(in: .whitespaces)
            if !sentence.isEmpty { result.append(sentence) }
        }
        return result
    }
}

// MARK: - Safe Array Access

private extension Array {
    subscript(safe index: Int) -> Element? {
        indices.contains(index) ? self[index] : nil
    }
}
