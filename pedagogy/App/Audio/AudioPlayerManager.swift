//
//  AudioPlayerManager.swift
//  pedagogy
//
//  ─── AUDIO PLAYER MANAGER ───────────────────────────────────────────────────
//  Reprodução dos MP3s narrados dos capítulos + tracking de sentença ativa
//  pra highlighting no ReaderView.
//
//  RESPONSABILIDADES
//
//    1. Playback: play, pause, seek, skip chapter (± 1)
//    2. Background: AVAudioSession(.playback) permite tocar com tela travada
//    3. Auto-play próximo capítulo: fim do cap N → começa cap N+1 automático,
//       com hop visual de 2s (StoryTimings.currentSentenceIndex fica nil
//       durante transition, o reader mostra "Chapter 2: The Second Night"
//       via callback onChapterChanged)
//    4. Sincronização com progresso: cada virada de sentença chama
//       library.updatePosition(...) — ouvir avança o LibraryProgress igual
//       ler (streak conta, achievements desbloqueiam, etc)
//    5. Timings tracking: publica currentSentenceIndex ObservableObject-style
//       pra highlighting reagir sem polling
//
//  QUANDO NÃO HÁ .timings.json
//
//  Toca o MP3 normal mas `currentSentenceIndex` fica sempre nil. Highlighting
//  no reader é opt-in por sentença — sem timings, ninguém fica destacado
//  (comportamento idêntico ao reader-only atual).
//
//  QUANDO NÃO HÁ MP3
//
//  play(story:chapter:) retorna sem tocar nada. Estado fica .idle. O UI
//  precisa checar `isPlaying` e/ou mostrar erro se relevante.
//
//  THREADING
//
//  Todos os métodos são @MainActor. AVAudioPlayer é thread-safe pra playback
//  mas mutações de state precisam vir do main. O Timer que atualiza
//  currentMs também roda no main.
//
//  NÃO INCLUI (fica pro Bloco 2)
//
//  • Live Activity (Dynamic Island / lock screen)
//  • Now Playing Info (metadata no lock screen)
//  • Remote Command Center (controles no lock screen)
//  • CarPlay
//
//  Todos requerem widget extension separado + entitlements. Isolar
//  simplifica.
//  ────────────────────────────────────────────────────────────────────────────

import AVFoundation
import Foundation
import MediaPlayer
import Observation
import SwiftUI

// MARK: - Public state

/// Estado do player. Menos abrangente que raw AVPlayer.timeControlStatus —
/// só o que a UI precisa. Codable pra debug/logs.
enum PlaybackState: Equatable {
    case idle           // nada carregado
    case loading        // MP3 carregando (rare — AVAudioPlayer é síncrono)
    case playing
    case paused
    case error(String)
}

/// Info do que está tocando. Referência weak-friendly pra propagar pra UI.
struct NowPlaying: Equatable {
    let storyID: String
    let storyTitle: String
    let chapter: Int
    let chapterTitle: String
    let coverAssetName: String
    /// Total de capítulos na story — usado pra decidir se auto-play próximo
    /// faz sentido (parar no fim).
    let totalChapters: Int
}

/// Velocidade de reprodução. Quatro passos fixos, não slider — escolher
/// velocidade é decisão demais pra uma criança de dez anos, e o pai que
/// configura isso às nove da noite quer um toque, não um controle fino.
///
/// 0.75× não é enfeite: é o que faz o app servir pra quem tem dislexia ou
/// lê inglês como segunda língua e precisa da voz mais devagar que a
/// leitura natural. 1.5× é pra releitura de capítulo já conhecido.
///
/// O AVAudioPlayer aceita 0.5–2.0 com `enableRate`; ficamos bem dentro.
enum PlaybackSpeed: Double, CaseIterable {
    case slow = 0.75
    case normal = 1.0
    case brisk = 1.25
    case fast = 1.5

    /// Rótulo do botão. "1×" em vez de "1.0×" — menos ruído no mini-player.
    var label: String {
        switch self {
        case .slow:   return "0.75×"
        case .normal: return "1×"
        case .brisk:  return "1.25×"
        case .fast:   return "1.5×"
        }
    }

    /// Lido pelo VoiceOver — "1.25×" sai horrível na síntese.
    var accessibilityLabel: String {
        switch self {
        case .slow:   return "Playback speed, three quarters"
        case .normal: return "Playback speed, normal"
        case .brisk:  return "Playback speed, one and a quarter"
        case .fast:   return "Playback speed, one and a half"
        }
    }

    /// Próximo passo do ciclo. Ordem: 1× → 1.25× → 1.5× → 0.75× → 1×.
    /// Começa subindo porque quem toca no botão quase sempre quer acelerar;
    /// o 0.75× fica no fim do ciclo, a um toque de voltar ao normal.
    var next: PlaybackSpeed {
        switch self {
        case .normal: return .brisk
        case .brisk:  return .fast
        case .fast:   return .slow
        case .slow:   return .normal
        }
    }
}

// MARK: - Manager

@Observable
@MainActor
final class AudioPlayerManager {

    // ─── Published state (lido pela UI via @Environment) ────────────

    /// Estado corrente do player.
    private(set) var state: PlaybackState = .idle

    /// O que está tocando (nil quando .idle).
    private(set) var nowPlaying: NowPlaying? = nil

    /// Índice da sentença destacada agora, baseado em currentMs + timings.
    /// nil quando: não tem timings, está entre chapters, ou o tempo caiu
    /// fora dos ranges (edge case).
    private(set) var currentSentenceIndex: Int? = nil

    /// Tempo corrente em ms. Atualiza via timer @ 10Hz durante playback.
    /// Usado pra progress bar e pra derivar currentSentenceIndex.
    private(set) var currentMs: Int = 0

    /// Duração total do capítulo em ms. Derivada do player após load.
    private(set) var durationMs: Int = 0

    /// Velocidade atual. Alterada por `cycleSpeed()`/`setSpeed(_:)`, nunca
    /// por atribuição direta — trocar velocidade tem efeito colateral (mexe
    /// no player e no lock screen) e um setter explícito deixa isso à vista.
    private(set) var speed: PlaybackSpeed = .normal

    var isPlaying: Bool {
        if case .playing = state { return true }
        return false
    }

    // ─── Private ────────────────────────────────────────────────────

    private var player: AVAudioPlayer?

    /// A sessão já tomou o foco de áudio do sistema? Ver `activateSession()`.
    private var sessionIsActive = false

    /// Estava tocando quando a interrupção começou? Decide se retoma quando
    /// ela acaba. Sem isso, uma ligação recebida com o áudio JÁ pausado
    /// faria a narração começar sozinha ao desligar.
    private var wasPlayingBeforeInterruption = false

    /// Tokens dos observers de interrupção/rota.
    ///
    /// `nonisolated(unsafe)` porque o `deinit` não é isolado ao main actor e
    /// precisa alcançá-los pra soltar. `@ObservationIgnored` porque não é
    /// estado de UI — a macro não deve rastrear.
    @ObservationIgnored
    private nonisolated(unsafe) var sessionObservers: [NSObjectProtocol] = []

    /// Contador de ticks desde o último save de posição. A 10Hz, 50 ticks
    /// = 5s: se o app morrer (crash, force quit, OOM), perde-se no máximo isso.
    private var ticksSinceSave = 0

    /// Timer que atualiza currentMs @ 10Hz durante playback. Suficiente
    /// pra sentence-level (típico: 3-6s por sentença). Se um dia migrar
    /// pra word-level, sobe pra 20-30Hz.
    private var progressTimer: Timer?

    /// Timings da chapter atual (nil quando não há .timings.json).
    private var timings: StoryTimings? = nil

    /// Callbacks pro exterior sincronizar state (ex: LibraryProgress
    /// avançar sentence-by-sentence, reader auto-scrollar).
    var onSentenceChanged: ((Int) -> Void)?
    var onChapterFinished: (() -> Void)?

    // ─── Init ───────────────────────────────────────────────────────

    /// Delegate helper — objeto separado que herda de NSObject só pra
    /// conformar a AVAudioPlayerDelegate. Mantido strong pra o AVAudioPlayer
    /// não perder (ele guarda weak).
    private let playerDelegate = AudioPlayerDelegateHelper()

    init() {
        // Conecta o helper a self — quando eventos do delegate chegarem,
        // ele chama de volta os métodos aqui.
        playerDelegate.owner = self

        // Restaura a velocidade escolhida na sessão anterior.
        let stored = UserDefaults.standard.double(forKey: Self.speedKey)
        speed = PlaybackSpeed(rawValue: stored) ?? .normal

        configureAudioSession()
        observeSessionEvents()
        setupRemoteCommands()
    }

    deinit {
        for token in sessionObservers {
            NotificationCenter.default.removeObserver(token)
        }
    }

    // MARK: - Sessão de áudio

    /// Descreve a categoria da sessão. NÃO ativa.
    ///
    /// A distinção importa: `setCategory` só declara a intenção e é barato,
    /// mas `setActive(true)` TOMA o foco de áudio do sistema — ou seja, mata
    /// a música que o usuário estava ouvindo. Fazer isso no init significa
    /// que abrir o Pedagogy pra ver a Home cala o Spotify de quem nem ia
    /// ouvir narração nenhuma. Por isso a ativação foi pro primeiro play().
    ///
    /// `.playback` mantém o áudio vivo com a tela travada e ignora o switch
    /// de silencioso (criança deita, aperta o botão lateral, a história
    /// continua). Depende do `UIBackgroundModes: audio` no Info.plist.
    ///
    /// `.spokenAudio` diz ao sistema que isso é fala contínua: quando o Siri
    /// ou o GPS interrompe, ele PAUSA a narração em vez de abaixar o volume
    /// por cima dela. Perder três segundos de história abafados é pior do
    /// que pausar e voltar.
    ///
    /// `.longFormAudio` marca o app como conteúdo de forma longa, do jeito
    /// que audiolivro e podcast fazem. Ganha roteamento AirPlay 2 correto —
    /// dá pra mandar a narração pro HomePod da sala sem espelhar a tela.
    private func configureAudioSession() {
        do {
            try AVAudioSession.sharedInstance().setCategory(
                .playback,
                mode: .spokenAudio,
                policy: .longFormAudio,
                options: []
            )
        } catch {
            // Não é fatal: sem a categoria certa o áudio ainda toca, só que
            // para no lock e obedece o silencioso. Degrada, não quebra.
            print("[AudioPlayerManager] AVAudioSession setup failed: \(error)")
        }
    }

    /// Toma o foco de áudio. Chamado no primeiro play, não no launch.
    @discardableResult
    private func activateSession() -> Bool {
        guard !sessionIsActive else { return true }
        do {
            try AVAudioSession.sharedInstance().setActive(true)
            sessionIsActive = true
            return true
        } catch {
            print("[AudioPlayerManager] AVAudioSession activation failed: \(error)")
            return false
        }
    }

    /// Devolve o foco. `.notifyOthersOnDeactivation` faz o app que estava
    /// tocando antes voltar sozinho em vez de o silêncio simplesmente ficar.
    private func deactivateSession() {
        guard sessionIsActive else { return }
        do {
            try AVAudioSession.sharedInstance().setActive(false, options: [.notifyOthersOnDeactivation])
            sessionIsActive = false
        } catch {
            print("[AudioPlayerManager] AVAudioSession deactivation failed: \(error)")
        }
    }

    /// Interrupções (ligação, Siri, alarme) e mudança de rota (fone saiu).
    ///
    /// Sem estes dois, dois furos reais aparecem em uso normal: uma ligação
    /// recebida mata a narração e ela nunca volta, e tirar o fone do ouvido
    /// joga a história no viva-voz no meio do ônibus.
    ///
    /// Os valores são extraídos AQUI, na closure que roda na main queue, e
    /// só `UInt` atravessa pro Task — `Notification` não é Sendable.
    private func observeSessionEvents() {
        let center = NotificationCenter.default
        let session = AVAudioSession.sharedInstance()

        sessionObservers.append(
            center.addObserver(
                forName: AVAudioSession.interruptionNotification,
                object: session,
                queue: .main
            ) { [weak self] note in
                let type = note.userInfo?[AVAudioSessionInterruptionTypeKey] as? UInt
                let options = note.userInfo?[AVAudioSessionInterruptionOptionKey] as? UInt
                Task { @MainActor in self?.handleInterruption(type: type, options: options) }
            }
        )

        sessionObservers.append(
            center.addObserver(
                forName: AVAudioSession.routeChangeNotification,
                object: session,
                queue: .main
            ) { [weak self] note in
                let reason = note.userInfo?[AVAudioSessionRouteChangeReasonKey] as? UInt
                Task { @MainActor in self?.handleRouteChange(reason: reason) }
            }
        )
    }

    private func handleInterruption(type: UInt?, options: UInt?) {
        guard let raw = type,
              let kind = AVAudioSession.InterruptionType(rawValue: raw) else { return }

        switch kind {
        case .began:
            wasPlayingBeforeInterruption = isPlaying
            if isPlaying { pause() }

        case .ended:
            let opts = AVAudioSession.InterruptionOptions(rawValue: options ?? 0)
            // Só retoma se o sistema autorizar E se estava tocando antes.
            // Voltar sozinho depois de uma ligação de vinte minutos, com o
            // telefone no bolso, seria pior do que ficar parado.
            if opts.contains(.shouldResume), wasPlayingBeforeInterruption {
                resume()
            }
            wasPlayingBeforeInterruption = false

        @unknown default:
            break
        }
    }

    private func handleRouteChange(reason: UInt?) {
        guard let raw = reason,
              let kind = AVAudioSession.RouteChangeReason(rawValue: raw),
              kind == .oldDeviceUnavailable else { return }
        if isPlaying { pause() }
    }

    // MARK: - Velocidade

    private static let speedKey = "audio.playbackSpeed"

    /// Define a velocidade e aplica no player em curso.
    func setSpeed(_ newSpeed: PlaybackSpeed) {
        speed = newSpeed
        player?.rate = Float(newSpeed.rawValue)
        UserDefaults.standard.set(newSpeed.rawValue, forKey: Self.speedKey)
        updateNowPlayingInfo()
    }

    /// Avança um passo no ciclo — é o que o botão do mini-player chama.
    func cycleSpeed() {
        setSpeed(speed.next)
    }

    // MARK: - Posição salva

    private static func positionKey(storyID: String, chapter: Int) -> String {
        "audio.position.\(storyID)-ch\(chapter)"
    }

    /// Salva onde parou, pra reabrir o capítulo continuar de lá.
    ///
    /// Perto do fim não salva: senão reabrir o capítulo cairia nos últimos
    /// dois segundos e ele terminaria na hora. Antes de 5s também não —
    /// não vale guardar "quase o começo".
    private func savePosition() {
        guard let np = nowPlaying, durationMs > 0 else { return }
        let key = Self.positionKey(storyID: np.storyID, chapter: np.chapter)
        if currentMs >= durationMs - 5_000 || currentMs <= 5_000 {
            UserDefaults.standard.removeObject(forKey: key)
        } else {
            UserDefaults.standard.set(currentMs, forKey: key)
        }
    }

    private func restoredPosition(storyID: String, chapter: Int) -> Int {
        let stored = UserDefaults.standard.integer(forKey: Self.positionKey(storyID: storyID, chapter: chapter))
        guard stored > 5_000 else { return 0 }
        // Volta 2s: retomar exatamente no ponto do corte perde o contexto
        // da frase que estava no meio.
        return max(0, stored - 2_000)
    }

    /// Esquece a retomada de um capítulo. Chamado quando ele termina e
    /// disponível pro "read again" zerar o áudio junto com o texto.
    func clearSavedPosition(storyID: String, chapter: Int) {
        UserDefaults.standard.removeObject(forKey: Self.positionKey(storyID: storyID, chapter: chapter))
    }

    // MARK: - Remote Command Center (lock screen / AirPods / CarPlay)

    /// Configura os handlers do MPRemoteCommandCenter uma vez no init.
    /// Play/pause funcionam com o player interno diretamente. Next/previous
    /// disparam callbacks pra o caller (MainTabView/ReaderView) que tem
    /// acesso à Story completa — o manager não segura ref à Story pra
    /// evitar retain cycle.
    private func setupRemoteCommands() {
        let center = MPRemoteCommandCenter.shared()

        center.playCommand.addTarget { [weak self] _ in
            guard let self else { return .commandFailed }
            Task { @MainActor in self.resume() }
            return .success
        }
        center.pauseCommand.addTarget { [weak self] _ in
            guard let self else { return .commandFailed }
            Task { @MainActor in self.pause() }
            return .success
        }
        center.togglePlayPauseCommand.addTarget { [weak self] _ in
            guard let self else { return .commandFailed }
            Task { @MainActor in self.togglePlayback() }
            return .success
        }
        center.nextTrackCommand.addTarget { [weak self] _ in
            guard let self else { return .commandFailed }
            Task { @MainActor in self.onRemoteNextTrack?() }
            return .success
        }
        center.previousTrackCommand.addTarget { [weak self] _ in
            guard let self else { return .commandFailed }
            Task { @MainActor in self.onRemotePreviousTrack?() }
            return .success
        }
        // Skip forward/backward 15s — comum em audiobooks
        center.skipForwardCommand.preferredIntervals = [15]
        center.skipForwardCommand.addTarget { [weak self] _ in
            guard let self else { return .commandFailed }
            Task { @MainActor in self.seek(toMs: min(self.currentMs + 15_000, self.durationMs)) }
            return .success
        }
        center.skipBackwardCommand.preferredIntervals = [15]
        center.skipBackwardCommand.addTarget { [weak self] _ in
            guard let self else { return .commandFailed }
            Task { @MainActor in self.seek(toMs: max(self.currentMs - 15_000, 0)) }
            return .success
        }
        // Scrubbing na progress bar do lock screen
        center.changePlaybackPositionCommand.addTarget { [weak self] event in
            guard let self,
                  let e = event as? MPChangePlaybackPositionCommandEvent
            else { return .commandFailed }
            Task { @MainActor in self.seek(toMs: Int(e.positionTime * 1000)) }
            return .success
        }
    }

    /// Callbacks pra "next/previous chapter" via Remote Command Center.
    /// Setados pelo caller que conhece a Story ativa (MainTabView).
    var onRemoteNextTrack: (() -> Void)?
    var onRemotePreviousTrack: (() -> Void)?

    // MARK: - Now Playing Info (metadata no lock screen)

    /// Popula MPNowPlayingInfoCenter com metadata do que está tocando.
    /// Cover vem do bundle via UIImage lookup. Chamado em play() e a cada
    /// tick pra manter currentTime sincronizado com a UI do lock screen.
    private func updateNowPlayingInfo() {
        guard let np = nowPlaying else {
            MPNowPlayingInfoCenter.default().nowPlayingInfo = nil
            return
        }

        var info: [String: Any] = [
            MPMediaItemPropertyTitle: np.storyTitle,
            MPMediaItemPropertyArtist: "Pedagogy",
            MPMediaItemPropertyAlbumTitle: "Chapter \(np.chapter) · \(np.chapterTitle)",
            MPMediaItemPropertyPlaybackDuration: Double(durationMs) / 1000.0,
            MPNowPlayingInfoPropertyElapsedPlaybackTime: Double(currentMs) / 1000.0,
            // A velocidade REAL, nao 1.0 fixo: e dela que o relogio do lock
            // screen tira o ritmo pra andar sozinho sem o app acordar. Com
            // 1.5x e rate 1.0 declarado, o tempo mostrado atrasa na tela.
            MPNowPlayingInfoPropertyPlaybackRate: isPlaying ? speed.rawValue : 0.0,
            MPNowPlayingInfoPropertyDefaultPlaybackRate: speed.rawValue,
            MPNowPlayingInfoPropertyPlaybackQueueIndex: np.chapter - 1,
            MPNowPlayingInfoPropertyPlaybackQueueCount: np.totalChapters,
        ]

        // Artwork — cover da story se disponível no bundle
        if !np.coverAssetName.isEmpty, let uiImage = UIImage(named: np.coverAssetName) {
            let artwork = MPMediaItemArtwork(boundsSize: uiImage.size) { _ in uiImage }
            info[MPMediaItemPropertyArtwork] = artwork
        }

        MPNowPlayingInfoCenter.default().nowPlayingInfo = info
    }

    // ─── Public API ─────────────────────────────────────────────────

    /// Existe narração pra este capítulo no bundle?
    ///
    /// Estático de propósito: a UI precisa decidir se MOSTRA um botão de
    /// áudio antes de qualquer coisa ser carregada, e isso não pode depender
    /// do estado do player. Mesma busca do `play()` — se um dia o caminho
    /// mudar, muda nos dois.
    static func hasNarration(storyID: String, chapter: Int) -> Bool {
        let name = "\(storyID)-ch\(chapter)"
        return Bundle.main.url(forResource: name, withExtension: "mp3", subdirectory: "Content/Audio") != nil
            || Bundle.main.url(forResource: name, withExtension: "mp3") != nil
    }

    /// Toca um capítulo de uma story. Se já estiver tocando o MESMO
    /// chapter, resume (não recarrega). Se for outro, para o atual e
    /// carrega o novo.
    ///
    /// Segurança: se o MP3 não existir no bundle, entra em .error e
    /// nowPlaying fica nil.
    func play(story: Story, chapter: Int) {
        // Já tocando o mesmo chapter? Resume.
        if let np = nowPlaying, np.storyID == story.id, np.chapter == chapter {
            resume()
            return
        }

        // Trocando de chapter/story: descarrega o atual SEM devolver o foco
        // de áudio. Usar stop() aqui daria um blip audível — o sistema
        // acordaria o app anterior no intervalo entre um capítulo e outro.
        unload()

        // Localiza MP3 no bundle. Naming produzido pelo generate_speech.py.
        let mp3Name = "\(story.id)-ch\(chapter)"
        guard let url = Bundle.main.url(forResource: mp3Name, withExtension: "mp3", subdirectory: "Content/Audio")
            ?? Bundle.main.url(forResource: mp3Name, withExtension: "mp3") else {
            state = .error("Audio not found for \(story.id) chapter \(chapter)")
            return
        }

        // Toma o foco de áudio agora — é o primeiro momento em que de fato
        // vamos fazer barulho.
        guard activateSession() else {
            state = .error("Could not activate audio session")
            return
        }

        // Carrega o player
        do {
            let p = try AVAudioPlayer(contentsOf: url)
            p.delegate = playerDelegate
            // enableRate PRECISA vir antes do prepareToPlay, senão o rate é
            // silenciosamente ignorado depois.
            p.enableRate = true
            p.prepareToPlay()
            self.player = p
            self.durationMs = Int(p.duration * 1000)
        } catch {
            state = .error("Failed to load audio: \(error.localizedDescription)")
            return
        }

        // Carrega timings (opcional — falha suave)
        self.timings = try? StoryTimingsLoader.load(storySlug: story.id, chapter: chapter)
        self.currentSentenceIndex = nil

        // Retoma de onde parou neste capítulo (0 se nunca ouviu ou se
        // terminou da última vez).
        let resumeMs = restoredPosition(storyID: story.id, chapter: chapter)
        player?.currentTime = Double(resumeMs) / 1000.0
        self.currentMs = resumeMs

        // Publica nowPlaying
        let chapterData = safeChapter(story: story, index: chapter - 1)
        self.nowPlaying = NowPlaying(
            storyID: story.id,
            storyTitle: story.title,
            chapter: chapter,
            chapterTitle: chapterData?.title ?? "Chapter \(chapter)",
            coverAssetName: story.coverImage ?? "",
            totalChapters: story.chapters.count
        )

        // Play
        player?.play()
        // O rate só "pega" com o player rodando — por isso vem depois do play.
        player?.rate = Float(speed.rawValue)
        state = .playing

        // Só no play que CARREGA um capítulo — resume não passa por aqui, e
        // contar cada retomada infliria o número sem dizer nada novo.
        Analytics.shared.track(.narrationPlay, [
            "content_id": story.id,
            "chapter": chapter,
        ])
        updateCurrentSentence()
        startProgressTimer()
        updateNowPlayingInfo()
    }

    /// Pausa (mantém carregado).
    func pause() {
        player?.pause()
        state = .paused
        stopProgressTimer()
        savePosition()
        updateNowPlayingInfo()
    }

    /// Retoma playback pausado. No-op se não houver player carregado.
    func resume() {
        guard player != nil else { return }
        guard activateSession() else { return }
        player?.play()
        player?.rate = Float(speed.rawValue)
        state = .playing
        startProgressTimer()
        updateNowPlayingInfo()
    }

    /// Toggle play/pause. Usado pelo mini-player.
    func togglePlayback() {
        switch state {
        case .playing: pause()
        case .paused:  resume()
        default:       break
        }
    }

    /// Descarrega o player sem devolver o foco de áudio ao sistema.
    /// Uso interno na troca de capítulo — ver comentário em `play()`.
    private func unload() {
        savePosition()
        player?.stop()
        player = nil
        state = .idle
        nowPlaying = nil
        currentSentenceIndex = nil
        currentMs = 0
        durationMs = 0
        timings = nil
        ticksSinceSave = 0
        stopProgressTimer()
    }

    /// Para playback, descarrega e devolve o foco de áudio. É o botão de
    /// fechar do mini-player — ação explícita do usuário, não acontece só
    /// porque o reader fechou.
    func stop() {
        unload()
        updateNowPlayingInfo()  // limpa lock screen
        deactivateSession()
    }

    /// Seek pra timestamp específico. Clampeia dentro do range.
    func seek(toMs ms: Int) {
        guard let p = player else { return }
        let clamped = max(0, min(ms, durationMs))
        p.currentTime = Double(clamped) / 1000.0
        currentMs = clamped
        updateCurrentSentence()
        updateNowPlayingInfo()
    }

    /// Seek pra sentença específica. Usado quando o usuário toca numa
    /// sentença highlighted no reader.
    func seek(toSentence index: Int) {
        guard let timings = timings,
              let sentence = timings.sentences.first(where: { $0.index == index }) else { return }
        seek(toMs: sentence.startMs)
    }

    /// Skip pra próximo capítulo. Requer nowPlaying set + story disponível.
    /// Chama loadStory externo via callback (evita acoplamento com StoryLoader).
    func skipToNextChapter(story: Story) {
        guard let np = nowPlaying, np.chapter < np.totalChapters else { return }
        play(story: story, chapter: np.chapter + 1)
    }

    func skipToPreviousChapter(story: Story) {
        guard let np = nowPlaying, np.chapter > 1 else { return }
        play(story: story, chapter: np.chapter - 1)
    }

    // ─── Private: progress timer ────────────────────────────────────

    private func startProgressTimer() {
        stopProgressTimer()
        let timer = Timer(timeInterval: 0.1, repeats: true) { [weak self] _ in
            Task { @MainActor in
                self?.tick()
            }
        }
        RunLoop.main.add(timer, forMode: .common)
        progressTimer = timer
    }

    private func stopProgressTimer() {
        progressTimer?.invalidate()
        progressTimer = nil
    }

    /// Atualiza currentMs a partir do player + deriva currentSentenceIndex.
    private func tick() {
        guard let p = player, p.isPlaying else { return }
        currentMs = Int(p.currentTime * 1000)
        updateCurrentSentence()

        // Salva a posicao a cada ~5s (50 ticks a 10Hz).
        ticksSinceSave += 1
        if ticksSinceSave >= 50 {
            ticksSinceSave = 0
            savePosition()
        }
    }

    /// Recalcula currentSentenceIndex baseado em currentMs + timings.
    /// Dispara `onSentenceChanged` só quando o valor MUDA (evita chamar o
    /// callback 10x por segundo — só na virada real).
    private func updateCurrentSentence() {
        guard let timings = timings else {
            if currentSentenceIndex != nil { currentSentenceIndex = nil }
            return
        }
        let newIndex = timings.sentenceIndex(atMs: currentMs)
        if newIndex != currentSentenceIndex {
            currentSentenceIndex = newIndex
            if let idx = newIndex {
                onSentenceChanged?(idx)
            }
        }
    }

    // ─── Helpers ────────────────────────────────────────────────────

    /// Acesso seguro a chapter por índice. Retorna nil se OOB.
    private func safeChapter(story: Story, index: Int) -> Chapter? {
        guard index >= 0, index < story.chapters.count else { return nil }
        return story.chapters[index]
    }
    // MARK: - Delegate callbacks (chamados pelo AudioPlayerDelegateHelper)

    /// Chapter terminou naturalmente (não por stop() do usuário). Dispara
    /// callback pro caller (MainTabView) que decide se auto-play próximo
    /// capítulo, sync com library, etc.
    fileprivate func handlePlaybackFinished() {
        self.state = .paused
        self.stopProgressTimer()
        // Capitulo terminou: nao ha o que retomar. Sem isso, ouvir de novo
        // comecaria nos ultimos segundos.
        if let np = self.nowPlaying {
            self.clearSavedPosition(storyID: np.storyID, chapter: np.chapter)
        }
        self.onChapterFinished?()
    }

    /// Erro de decode do MP3 — muito raro. Publica no state pra UI reagir.
    fileprivate func handleDecodeError(_ error: Error?) {
        self.state = .error(error?.localizedDescription ?? "Decode error")
        self.stopProgressTimer()
    }
}

// MARK: - AVAudioPlayerDelegate helper (NSObject isolado)

/// Objeto separado que herda de NSObject só pra conformar a
/// AVAudioPlayerDelegate. Isolado do AudioPlayerManager porque combinar
/// @Observable + NSObject subclass causa problemas de resolução de tipos
/// no @Environment do SwiftUI (o macro @Observable não brinca bem com
/// NSObject inheritance em alguns contextos).
///
/// Todos os callbacks fazem forward pro AudioPlayerManager no main actor.
private final class AudioPlayerDelegateHelper: NSObject, AVAudioPlayerDelegate {
    /// Reference weak pro owner. Setada logo após init pra evitar
    /// dependência circular no init do manager.
    weak var owner: AudioPlayerManager?

    func audioPlayerDidFinishPlaying(_ player: AVAudioPlayer, successfully flag: Bool) {
        Task { @MainActor [weak owner] in
            owner?.handlePlaybackFinished()
        }
    }

    func audioPlayerDecodeErrorDidOccur(_ player: AVAudioPlayer, error: Error?) {
        Task { @MainActor [weak owner] in
            owner?.handleDecodeError(error)
        }
    }
}
