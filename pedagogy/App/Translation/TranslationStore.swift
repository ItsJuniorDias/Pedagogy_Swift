//
//  TranslationStore.swift
//  pedagogy
//
//  ─── TRADUÇÃO NATIVA ────────────────────────────────────────────────────────
//  Traduz o conteúdo das histórias pro idioma escolhido usando o framework
//  Translation da Apple (iOS 18). Tudo roda no device: nenhum texto sai do
//  aparelho, então não há nada a declarar na Categoria Kids.
//
//  O QUE É TRADUZIDO
//
//  Padrão é o inglês original. Só traduz quando alguém escolhe um idioma.
//
//  Conteúdo das histórias — título, subtítulo, resumo, títulos de capítulo e
//  o texto corrido do reader. O idioma de origem é sempre inglês (é o idioma
//  dos JSONs e da narração).
//
//  POR SENTENÇA, NÃO POR PARÁGRAFO
//
//  O reader traduz cada sentença do `SentenceSplitter` separadamente. Custa
//  um pouco de contexto na tradução, mas mantém a contagem de sentenças
//  idêntica ao original — e é essa contagem que o destaque da narração usa.
//  Resultado: a criança lê em português enquanto a narração em inglês toca,
//  e a sentença destacada continua sendo a que está sendo narrada.
//
//  COMO A SESSÃO FUNCIONA
//
//  `TranslationSession` não é instanciável: ela só existe dentro do closure
//  de `.translationTask(_:action:)`, preso a uma view. Por isso o store não
//  traduz sozinho — ele mantém uma fila, e um `TranslationHost` (modifier) na
//  view mais ao topo abre a sessão e chama `process(_:)` pra drenar a fila.
//
//  Há dois hosts: a raiz do app e o reader. O reader é fullScreenCover, e o
//  pedido de download do idioma é uma sheet do sistema apresentada a partir
//  da view host — de baixo de um cover ela não aparece. Os hosts se empilham
//  (`pushHost`/`popHost`) e só o do topo responde.
//
//  CACHE
//
//  Em memória + JSON em Caches/, por idioma. Segundo launch abre traduzido
//  instantâneo. Caches/ pode ser limpo pelo sistema — sem problema, retraduz.
//  ────────────────────────────────────────────────────────────────────────────

import SwiftUI
import Translation

@Observable
final class TranslationStore {

    enum Availability: Equatable {
        case checking
        /// O par en → idioma escolhido não é suportado neste aparelho.
        case unavailable
        /// Suportado. Pode exigir download do idioma na primeira tradução.
        case available
    }

    static let sourceLanguage = Locale.Language(identifier: "en")

    /// Idioma escolhido pra leitura. `nil` = inglês original, que é o padrão:
    /// a tradução só existe quando alguém escolhe um idioma (Perfil ou menu
    /// do reader). Persistido. Trocar descarta a fila e troca o cache.
    var targetLanguage: Locale.Language? {
        didSet {
            guard targetLanguage != oldValue else { return }
            if let targetLanguage {
                UserDefaults.standard.set(targetLanguage.minimalIdentifier, forKey: Self.targetKey)
            } else {
                UserDefaults.standard.removeObject(forKey: Self.targetKey)
            }
            clearQueue()
            lastError = nil
            cache = Self.loadCache(for: targetLanguage)
            availability = .checking
            Task { await refreshAvailability() }
        }
    }

    /// Idiomas de destino que o framework oferece (sem inglês), ordenados
    /// pelo nome. Alimenta os seletores.
    private(set) var supportedLanguages: [Locale.Language] = []

    private(set) var availability: Availability = .checking

    /// Tradução de fato ligada: há idioma escolhido E o par é suportado.
    var isActive: Bool { targetLanguage != nil && availability == .available }

    /// Há texto na fila esperando tradução.
    var isTranslating: Bool { !queue.isEmpty }

    /// Mensagem da última falha (download recusado, idioma indisponível).
    private(set) var lastError: String?

    /// Nome do idioma nele mesmo ("Português (Brasil)", "Español").
    static func displayName(of language: Locale.Language) -> String {
        let id = language.minimalIdentifier
        let name = Locale(identifier: id).localizedString(forIdentifier: id) ?? id
        return name.prefix(1).uppercased() + name.dropFirst()
    }

    // MARK: - Estado interno

    private var cache: [String: String] = [:]
    private var queue: [String] = []
    private var queued: Set<String> = []
    private var isProcessing = false

    /// Pilha de hosts montados; o último é o que responde.
    private var hosts: [UUID] = []
    var activeHost: UUID? { hosts.last }

    /// Incrementado pra acordar o host ativo quando a fila ganha trabalho.
    private(set) var wakeCount = 0

    private var saveTask: Task<Void, Never>?

    private static let targetKey = "pedagogy.translation.target"
    private static let batchSize = 40

    init() {
        let saved = UserDefaults.standard.string(forKey: Self.targetKey)
        targetLanguage = saved.map { Locale.Language(identifier: $0) }
        cache = Self.loadCache(for: targetLanguage)
    }

    // MARK: - Leitura

    /// Texto traduzido se já estiver pronto; senão, o original.
    /// Nunca muta estado — seguro de chamar dentro de `body`.
    func text(_ original: String) -> String {
        guard isActive else { return original }
        return cache[original] ?? original
    }

    func text(_ original: String?) -> String? {
        original.map { text($0) }
    }

    // MARK: - Pedidos

    /// Enfileira textos pra tradução. Chame de `.task`, não de `body`.
    ///
    /// - Parameter priority: coloca na frente da fila (texto em tela agora).
    func request(_ strings: [String], priority: Bool = false) {
        guard isActive else { return }

        let missing = strings.filter { s in
            !s.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty
                && cache[s] == nil
                && !queued.contains(s)
        }
        guard !missing.isEmpty else { return }

        // Dedup preservando ordem (a mesma sentença pode repetir no capítulo).
        var seen: Set<String> = []
        let unique = missing.filter { seen.insert($0).inserted }

        queued.formUnion(unique)
        if priority {
            queue.insert(contentsOf: unique, at: 0)
        } else {
            queue.append(contentsOf: unique)
        }
        wake()
    }

    /// Metadados de todo o catálogo (~300 textos curtos): títulos, subtítulos,
    /// resumos e títulos de capítulo. Pedido de uma vez ao escolher o idioma, pra Home e
    /// Library já abrirem traduzidas sem cada card pedir o seu.
    func requestCatalog() {
        guard isActive, let stories = try? StoryLoader.loadAll() else { return }
        request(stories.flatMap(Self.metadataStrings))
    }

    static func metadataStrings(of story: Story) -> [String] {
        [story.title, story.subtitle, story.summary].compactMap { $0 }
            + story.chapters.map(\.title)
    }

    // MARK: - Disponibilidade

    func refreshAvailability() async {
        let checker = LanguageAvailability()

        if supportedLanguages.isEmpty {
            let all = await checker.supportedLanguages
            supportedLanguages = all
                .filter { $0.languageCode != Self.sourceLanguage.languageCode }
                .sorted { Self.displayName(of: $0) < Self.displayName(of: $1) }
        }

        guard let target = targetLanguage else { return }
        let status = await checker.status(from: Self.sourceLanguage, to: target)
        // O usuário pode ter trocado de idioma enquanto esperávamos.
        guard target == targetLanguage else { return }
        availability = status == .unsupported ? .unavailable : .available
        requestCatalog()
    }

    // MARK: - Hosts

    func pushHost(_ id: UUID) {
        hosts.removeAll { $0 == id }
        hosts.append(id)
        wake()
    }

    func popHost(_ id: UUID) {
        hosts.removeAll { $0 == id }
        wake()
    }

    private func wake() {
        // Com a sessão já drenando, o loop de `process` pega o que chegou.
        // Acordar de novo invalidaria a configuração e cancelaria o lote em voo.
        guard !isProcessing, !queue.isEmpty else { return }
        wakeCount &+= 1
    }

    // MARK: - Processamento

    /// Drena a fila em lotes. Chamado pelo `TranslationHost` de dentro do
    /// closure do `.translationTask` — único lugar onde a sessão existe.
    func process(_ session: TranslationSession) async {
        guard !isProcessing else { return }
        isProcessing = true

        // A sessão é presa ao idioma com que foi aberta. Se o usuário trocar
        // no meio, o host recria a configuração; os lotes desta sessão
        // não podem cair no cache do idioma novo.
        let sessionTarget = targetLanguage

        var cancelled = false
        while isActive, !queue.isEmpty, targetLanguage == sessionTarget {
            let batch = Array(queue.prefix(Self.batchSize))
            let requests = batch.enumerated().map { index, text in
                TranslationSession.Request(sourceText: text, clientIdentifier: String(index))
            }

            do {
                let responses = try await session.translations(from: requests)
                guard targetLanguage == sessionTarget else { break }
                for response in responses {
                    guard let id = response.clientIdentifier,
                          let index = Int(id),
                          batch.indices.contains(index)
                    else { continue }
                    cache[batch[index]] = response.targetText
                }
            } catch where error is CancellationError || Task.isCancelled {
                // Host saiu de cena (reader fechou). Não é falha: a fila fica
                // e o próximo host assume.
                cancelled = true
                break
            } catch {
                // Download recusado, sem rede pra baixar o idioma, par não
                // suportado. Desliga pra não ficar em loop pedindo de novo.
                print("[Translation] Failed:", error)
                // Volta pro inglês antes de gravar o erro: o didSet limpa
                // `lastError`.
                targetLanguage = nil
                lastError = "Couldn't translate right now. Try again later."
                break
            }

            queue.removeFirst(min(batch.count, queue.count))
            queued.subtract(batch)
            scheduleSave()
        }

        isProcessing = false
        if cancelled || targetLanguage != sessionTarget { wake() }
    }

    private func clearQueue() {
        queue.removeAll()
        queued.removeAll()
    }

    // MARK: - Cache em disco

    private static func cacheURL(for language: Locale.Language) -> URL {
        let dir = FileManager.default.urls(for: .cachesDirectory, in: .userDomainMask)[0]
        return dir.appendingPathComponent("translations-\(language.minimalIdentifier).json")
    }

    private static func loadCache(for language: Locale.Language?) -> [String: String] {
        guard let language,
              let data = try? Data(contentsOf: cacheURL(for: language)),
              let dict = try? JSONDecoder().decode([String: String].self, from: data)
        else { return [:] }
        return dict
    }

    /// Debounce de 1s: um capítulo chega em vários lotes seguidos, e gravar
    /// o JSON inteiro a cada lote seria desperdício.
    private func scheduleSave() {
        saveTask?.cancel()
        guard let targetLanguage else { return }
        let snapshot = cache
        let url = Self.cacheURL(for: targetLanguage)
        saveTask = Task {
            try? await Task.sleep(for: .seconds(1))
            guard !Task.isCancelled else { return }
            await Task.detached(priority: .utility) {
                if let data = try? JSONEncoder().encode(snapshot) {
                    try? data.write(to: url, options: .atomic)
                }
            }.value
        }
    }
}

// MARK: - Host

/// Abre a `TranslationSession` pra esta view e drena a fila do store quando
/// este é o host do topo. Aplicar na raiz do app e em cada fullScreenCover
/// que exiba texto traduzível.
private struct TranslationHost: ViewModifier {
    @Environment(TranslationStore.self) private var store

    @State private var id = UUID()
    @State private var configuration: TranslationSession.Configuration?

    func body(content: Content) -> some View {
        content
            .translationTask(configuration) { session in
                await store.process(session)
            }
            .onAppear { store.pushHost(id) }
            .onDisappear { store.popHost(id) }
            // Configuração nova pro idioma novo; o próximo `wake` a cria.
            .onChange(of: store.targetLanguage) { _, _ in
                configuration = nil
            }
            .onChange(of: store.wakeCount) { _, _ in
                guard store.activeHost == id, let target = store.targetLanguage else { return }
                if configuration == nil {
                    configuration = TranslationSession.Configuration(
                        source: TranslationStore.sourceLanguage,
                        target: target
                    )
                } else {
                    configuration?.invalidate()
                }
            }
    }
}

extension View {
    func translationHost() -> some View {
        modifier(TranslationHost())
    }
}
