//
//  MainTabView.swift
//  pedagogy
//
//  ─── MAIN TAB VIEW ──────────────────────────────────────────────────────────
//  Raiz de navegação depois do onboarding. Duas tabs no bottom:
//
//    • Read     → HomeView (vitrine curada, drop semanal, featured picks)
//    • Library  → LibraryView (todas as histórias, filtro por categoria)
//
//  LIQUID GLASS
//
//  A partir de iOS 26, TabView adota automaticamente o estilo Liquid Glass
//  quando compilado com Xcode 26+. Em iOS 18-25 vira tab bar padrão.
//
//  DECISÃO DE NAVEGAÇÃO
//
//  Cada tab tem sua própria NavigationStack (dentro da View respectiva).
//  Convenção iOS: cada tab preserva sua stack ao trocar.
//
//  COORDINATION ENTRE TABS
//
//  A Home tem 3 pontos que precisam MUDAR de tab (não fazer push interno):
//    • Chip de categoria → Library filtrada
//    • "See all N stories" → Library sem filtro
//
//  Isso é feito via `@State selectedTab` + `libraryPreselect` aqui, e
//  closures passadas pra HomeView. Alternativa (usar navigationDestination
//  na própria Home) não trocava de tab, só empilhava a Library dentro da
//  Read — confuso pra user que via a mesma tela em 2 tabs.
//
//  DEEP LINK VIA NOTIFICAÇÃO
//
//  Quando o usuário toca numa notif ("New story this week: The Fox..."), o
//  NotificationsDelegate seta `NotificationManager.openedStoryID`. Aqui a
//  gente observa via .onChange e apresenta a StoryDetail em .sheet.
//
//  Por que .sheet e não push na NavigationStack ativa?
//    • Tap em card = contexto (você tava navegando dentro de uma tab; back
//      leva você de volta ao card). NavigationStack push é natural.
//    • Tap em notif = SEM contexto (você não sabe qual tab tá ativa; nem
//      importa). Sheet modal é a semântica certa — abre por cima, fecha
//      com swipe-down, não polui nenhuma stack.
//
//  Consumimos o openedStoryID assim que apresentamos (chama
//  consumeOpenedStoryID()) — sem isso, re-renderizações reapresentariam.
//  ────────────────────────────────────────────────────────────────────────────

import SwiftUI

/// Tabs disponíveis. Hashable pra usar como `selection` do TabView.
enum AppTab: Hashable {
    case read
    case library
    case you
}

struct MainTabView: View {
    @Environment(NotificationManager.self) private var notifications
    @Environment(AudioPlayerManager.self) private var audio
    @Environment(LibraryProgress.self) private var library

    @State private var selectedTab: AppTab = .read

    /// Categoria pré-selecionada da próxima vez que a tab Library abrir.
    /// Setada pela HomeView quando um chip de categoria é tocado, resetada
    /// pra nil quando a tab Library aplicou o filtro.
    @State private var libraryPreselect: StoryCategory? = nil

    /// Story sendo apresentada via deep link de notif OU tap no mini-player.
    /// `nil` quando nada aberto. Populada em .onChange(of: notifications.openedStoryID)
    /// ou pelo callback onTap do MiniPlayerView.
    @State private var deepLinkedStory: Story? = nil

    /// Preamble visual mostrado por 2s antes do auto-play do próximo capítulo.
    /// Renderizado como overlay sobre o mini-player durante a transição.
    /// Formato: "Chapter 2: The Second Night" — dá ao usuário chance de
    /// interromper (pause) antes de sair do capítulo atual.
    @State private var preambleText: String? = nil

    /// Cola o mini-player no rodapé de UMA tab.
    ///
    /// POR QUE NO CONTEÚDO DA TAB E NÃO NO TabView
    ///
    /// Aplicado ao TabView, o `safeAreaInset` põe o mini-player na borda de
    /// baixo da TELA. No iOS 26 a tab bar é uma cápsula flutuante desenhada
    /// por cima do conteúdo, então os dois caem no mesmo lugar e sobra uma
    /// faixa de cada um.
    ///
    /// Aplicado ao conteúdo da tab, o mini-player entra no safe area DELA —
    /// que já desconta a altura da tab bar. Ele encosta logo acima da cápsula,
    /// e o conteúdo da tab encolhe sozinho pra caber, sem tapar nada.
    ///
    /// POR QUE NÃO O `tabViewBottomAccessory`
    ///
    /// É a API nativa pra isso no iOS 26 e seria mais bonita — o acessório
    /// minimiza junto com a barra no scroll. Mas ele reserva a cápsula de
    /// vidro pela PRESENÇA do modifier, não pelo conteúdo: com nada tocando,
    /// o `MiniPlayerView` não renderiza nada e mesmo assim fica uma cápsula
    /// cinza vazia na tela.
    ///
    /// Aplicar o modifier condicionalmente resolveria a cápsula e criaria
    /// coisa pior: o `if` troca o galho do ViewBuilder, o TabView é recriado,
    /// e a tab selecionada mais as NavigationStacks de dentro se perdem toda
    /// vez que o áudio começa ou para.
    ///
    /// O `safeAreaInset` não tem esse problema: conteúdo vazio ocupa zero.
    @ViewBuilder
    private func withMiniPlayer<Content: View>(@ViewBuilder _ content: () -> Content) -> some View {
        content()
            .safeAreaInset(edge: .bottom, spacing: 0) {
                MiniPlayerView(
                    preambleText: preambleText,
                    onTap: { storyID in
                        deepLinkedStory = loadStory(withID: storyID)
                    }
                )
                .animation(.spring(response: 0.35, dampingFraction: 0.85), value: audio.nowPlaying)
            }
    }

    var body: some View {
        TabView(selection: $selectedTab) {
            Tab("Read", systemImage: "book.fill", value: AppTab.read) {
                withMiniPlayer {
                    HomeView(
                        onNavigateToLibrary: { category in
                            // Seta filtro (ou nil pra "See all") e troca tab.
                            // LibraryView vai consumir libraryPreselect no seu
                            // .task, aplicar o filtro, e limpar via callback.
                            libraryPreselect = category
                            selectedTab = .library
                        }
                    )
                }
            }

            Tab("Library", systemImage: "books.vertical.fill", value: AppTab.library) {
                withMiniPlayer {
                    LibraryView(preselectedCategory: $libraryPreselect)
                }
            }

            Tab("You", systemImage: "bookmark.fill", value: AppTab.you) {
                withMiniPlayer {
                    ProfileView()
                }
            }
        }
        // Tint dos ícones e label da tab selecionada. Rosa é a única cor
        // de marca — o liquid glass do iOS 26 mantém esse acento visível
        // sobre o material translúcido.
        .tint(Theme.Colors.primary)
        // Deep link: quando openedStoryID muda pra não-nil, carrega a story
        // do bundle e apresenta em sheet. Consumimos imediatamente pra não
        // re-apresentar em re-renders.
        .onChange(of: notifications.openedStoryID) { _, newID in
            guard let id = newID else { return }
            deepLinkedStory = loadStory(withID: id)
            notifications.consumeOpenedStoryID()
        }
        .sheet(item: $deepLinkedStory) { story in
            // NavigationStack dentro do sheet permite que StoryDetailView
            // faça seu próprio push (pra ReaderView) sem afetar as tabs.
            NavigationStack {
                StoryDetailView(story: story)
            }
        }
        // Wire callbacks do AudioPlayerManager. Aqui é o lugar certo porque
        // temos acesso ao library (pra sync progresso) e podemos carregar
        // Story fresh do bundle (o manager não segura ref pra evitar cycle).
        .task {
            audio.onChapterFinished = { [audio, library] in
                Task { @MainActor in
                    guard let np = audio.nowPlaying else { return }

                    // 1. Sync com progresso de leitura: chapter terminou =
                    //    marca como lido no LibraryProgress. Isso avança a
                    //    streak, dispara achievements, marca story finished
                    //    se foi o último chapter.
                    if np.chapter >= np.totalChapters {
                        library.markFinished(storyID: np.storyID)
                        Analytics.shared.track(.storyComplete, [
                            "content_id": np.storyID,
                            "source": "narration",
                        ])
                    } else {
                        // updatePosition espera chapter 0-indexed
                        library.updatePosition(
                            storyID: np.storyID,
                            chapter: np.chapter,   // np.chapter (1-idx) → 0-idx do próximo (que é np.chapter no 0-idx)
                            page: 0
                        )
                    }

                    // 2. Auto-play próximo capítulo se houver
                    if np.chapter < np.totalChapters {
                        await autoPlayNextChapter(from: np)
                    }
                }
            }

            // Remote Command Center → next/previous track
            audio.onRemoteNextTrack = { [audio] in
                Task { @MainActor in
                    guard let np = audio.nowPlaying,
                          let story = loadStory(withID: np.storyID) else { return }
                    audio.skipToNextChapter(story: story)
                }
            }
            audio.onRemotePreviousTrack = { [audio] in
                Task { @MainActor in
                    guard let np = audio.nowPlaying,
                          let story = loadStory(withID: np.storyID) else { return }
                    audio.skipToPreviousChapter(story: story)
                }
            }
        }
    }

    /// Auto-play próximo capítulo com preamble visual de 2s.
    /// Mostra "Chapter N: Title" no mini-player, dá tempo pro usuário
    /// interromper (tocar pause) se quiser parar, depois carrega o próximo.
    private func autoPlayNextChapter(from current: NowPlaying) async {
        guard let story = loadStory(withID: current.storyID) else { return }
        let nextChapter = current.chapter + 1
        guard nextChapter <= story.chapters.count else { return }

        let nextChapterData = story.chapters[nextChapter - 1]
        preambleText = "Next: Chapter \(nextChapter) · \(nextChapterData.title)"

        // Espera 2s. Se o usuário tocar pause nesse intervalo, cancelamos
        // o auto-play (respeita a intenção).
        try? await Task.sleep(nanoseconds: 2_000_000_000)

        // Se o state mudou (ex: usuário parou tudo, ou já começou outra story),
        // cancela silenciosamente.
        guard let stillCurrent = audio.nowPlaying,
              stillCurrent.storyID == current.storyID,
              stillCurrent.chapter == current.chapter else {
            preambleText = nil
            return
        }

        audio.play(story: story, chapter: nextChapter)
        preambleText = nil
    }

    /// Carrega uma story do bundle pelo id. Retorna nil se não achar (raro
    /// — só aconteceria se o id da notif fosse pra uma story removida entre
    /// o momento do schedule e o tap).
    private func loadStory(withID id: String) -> Story? {
        do {
            let all = try StoryLoader.loadAll()
            return all.first { $0.id == id }
        } catch {
            print("[MainTabView] Failed to load stories for deep link: \(error)")
            return nil
        }
    }
}

// MARK: - Mini-player

#Preview {
    MainTabView()
        .environment(Store())
        .environment(LibraryProgress())
        .environment(TranslationStore())
        .environment(NotificationManager())
        .environment(AchievementsStore())
        .environment(AudioPlayerManager())
}
