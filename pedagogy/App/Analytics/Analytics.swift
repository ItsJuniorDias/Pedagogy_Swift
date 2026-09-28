//
//  Analytics.swift
//  pedagogy
//
//  ─── ANALYTICS FIRST-PARTY ──────────────────────────────────────────────────
//  Manda eventos pro backend próprio (pedagogy-analytics no Render). Sem SDK
//  de terceiro, sem IDFA, sem identificador de device ou usuário.
//
//  Isso não é purismo: a Categoria Kids proíbe analytics de terceiro, e a
//  App Store rejeita por isso. Um POST JSON pro seu próprio servidor não é
//  terceiro, e sem identificador nenhum não há o que declarar em rastreamento.
//
//  O QUE O SERVIDOR ESPERA
//
//      POST /events
//      { "event": "paywall_view",
//        "params": { "source": "story_detail" },
//        "ts": 1719950000000 }
//
//  Ou um array de até 50 desses. Responde 202. Os nomes que alimentam o funil
//  e o espelho do Meta CAPI são fixos — ver `AnalyticsEvent`.
//
//  POR QUE FILA E NÃO UM POST POR EVENTO
//
//  Três motivos, e o primeiro é o que decide:
//
//  1. **O Render dorme.** No plano free o serviço hiberna sem tráfego e a
//     primeira requisição depois disso leva dezenas de segundos pra responder.
//     Um POST solto por evento significaria perder justamente os primeiros
//     eventos do dia — que incluem o `paywall_view` de quem abriu o app pela
//     manhã.
//  2. Rede de celular em movimento cai. Com fila e retentativa, o evento
//     espera; sem fila, evapora.
//  3. Três eventos de funil em sequência (view → checkout → subscribe) viram
//     uma requisição em vez de três.
//
//  A fila é persistida em disco. Se o app morrer com eventos pendentes, eles
//  saem no próximo launch — o que importa pra conversão, que é exatamente o
//  momento em que o usuário pode fechar o app.
//
//  DESLIGADO EM DEBUG
//
//  Rodar no simulador enquanto se mexe no paywall geraria dezenas de
//  `paywall_view` falsos, e o funil é uma razão de volume: cinquenta views de
//  desenvolvimento derrubam a taxa de conversão do mês inteiro. Pra testar a
//  ligação de ponta a ponta, use o launch argument `-analytics.enabled YES`.
//  ────────────────────────────────────────────────────────────────────────────

import Foundation
import os
import UIKit

// MARK: - Eventos

/// Nomes canônicos. Os quatro primeiros NÃO podem ser renomeados sem mexer no
/// backend: `lib/funnel.ts` monta o funil com eles e `lib/capiMirror.ts` os
/// traduz pros eventos padrão do Meta (ViewContent, InitiateCheckout,
/// Purchase, StartTrial).
enum AnalyticsEvent: String {
    case paywallView = "paywall_view"
    case checkoutInitiated = "checkout_initiated"
    case subscribe = "subscribe"
    case startTrial = "start_trial"

    // Abaixo: sinal de produto, fora do funil. Aparecem em /stats/events.
    case storyOpen = "story_open"
    case storyComplete = "story_complete"
    case narrationPlay = "narration_play"
    case shortPlay = "short_play"
    case shortComplete = "short_complete"

    /// Alarme de infraestrutura, não métrica de produto: o paywall foi
    /// apresentado sem nenhum plano comprável. Em operação normal isso é
    /// sempre zero — qualquer volume aqui significa receita parando de
    /// entrar agora, e o número dele contra `paywall_view` é a estimativa
    /// direta de quantas conversões estão sendo perdidas.
    ///
    /// Vale um alerta no backend em vez de esperar alguém abrir o dashboard.
    case paywallProductsEmpty = "paywall_products_empty"

    // ─── AQUISIÇÃO / CICLO DE VIDA ──────────────────────────────────────────

    /// Uma vez por INSTALAÇÃO, e nunca mais. É o denominador que faltava:
    /// "210 paywall views" não diz se é bom ou ruim sem saber quantas pessoas
    /// entraram no app. Com ele, install → paywall → assinatura vira uma conta.
    ///
    /// Sem user id, "usuário novo" é "instalação nova" — reinstalar conta de
    /// novo. É a definição honesta possível num app sem identificador.
    case firstOpen = "first_open"

    /// Uma vez por launch do processo. Volume de sessão — não é DAU (não dá
    /// pra distinguir uma pessoa abrindo 5 vezes de 5 pessoas abrindo 1).
    case appOpen = "app_open"

    // ─── ONBOARDING ─────────────────────────────────────────────────────────
    //
    // Os quatro `onboarding_page` formam o funil de entrada. Cada um manda o
    // nome da página em `source` — que é coluna indexada no backend, então dá
    // pra agrupar. Um param novo qualquer ficaria só no JSON, consultável mas
    // não agregável.

    case onboardingStart = "onboarding_start"
    case onboardingPage = "onboarding_page"
    case onboardingComplete = "onboarding_complete"

    case notificationsPrompt = "notifications_prompt"
    case notificationsGranted = "notifications_granted"
    case notificationsDenied = "notifications_denied"
    case notificationsSkipped = "notifications_skipped"

    // ─── PARENTAL GATE ──────────────────────────────────────────────────────
    //
    // Ponto cego que existia até agora: quem tocava "Assinar" e desistia no
    // gate não gerava evento NENHUM. A queda de paywall_view → checkout ficava
    // toda debitada no preço, quando parte dela pode ser o desafio matemático.
    //
    // `shown` menos `passed` é exatamente quanta gente o gate está barrando.
    // O `.parentalGate` só expõe `onPass`, então medimos pela diferença em vez
    // de mexer no componente.

    case parentalGateShown = "parental_gate_shown"
    case parentalGatePassed = "parental_gate_passed"

    // ─── PAYWALL ────────────────────────────────────────────────────────────

    /// Toque no CTA, ANTES do gate. Junto com `checkout_initiated` (que só
    /// dispara depois do gate) isola intenção de fricção.
    case paywallCTATapped = "paywall_cta_tapped"
}

// MARK: - Cliente

@MainActor
final class Analytics {

    static let shared = Analytics()

    private let endpoint = URL(string: "https://pedagogy-analytics.onrender.com/events")!

    /// Chave de ingest. Só necessária se você ligar `INGEST_TOKEN` no Render —
    /// hoje está vazio lá, então o header não é enviado.
    private let ingestToken: String? = nil

    /// Desligado em DEBUG: nada sai do simulador nem do build rodado pelo
    /// Xcode, pra não sujar o funil com `paywall_view` de desenvolvimento.
    /// Nem enfileira — assim nada acumula no disco e vaza quando o mesmo
    /// aparelho rodar um build de release.
    ///
    /// Pra testar a ligação de ponta a ponta em DEBUG: Product → Scheme → Edit
    /// → Run → Arguments, e adicione `-analytics.enabled YES`. O UserDefaults
    /// lê launch arguments nesse formato sozinho. Depois, limpe os eventos de
    /// teste antes de publicar —
    ///
    ///     curl -X DELETE "https://pedagogy-analytics.onrender.com/admin/clear?confirm=DELETE_ALL" \
    ///       -H "Authorization: Bearer $ADMIN_TOKEN"
    ///
    /// Em release, `-analytics.disabled YES` continua silenciando.
    private var isEnabled: Bool {
        #if DEBUG
        UserDefaults.standard.bool(forKey: "analytics.enabled")
        #else
        !UserDefaults.standard.bool(forKey: "analytics.disabled")
        #endif
    }

    private let log = Logger(subsystem: "pedagogy", category: "analytics")

    /// `print` e não `Logger` de propósito: em DEBUG o que se quer é ver a
    /// linha no console do Xcode sem configurar nível de log nem abrir o
    /// Console.app. Some inteiro em release.
    private func debugLog(_ message: String) {
        #if DEBUG
        print("[analytics] \(message)")
        #endif
    }

    /// Teto da fila. Um app que ficou uma semana offline não deve acumular
    /// milhares de eventos velhos — e eventos de funil velhos não valem nada.
    /// Ao estourar, os MAIS ANTIGOS caem.
    private let maxQueued = 200

    /// Dispara o envio quando a fila chega aqui. O backend aceita até 50.
    private let batchSize = 10

    private var queue: [Payload] = []
    private var isFlushing = false
    private var observers: [NSObjectProtocol] = []

    private lazy var session: URLSession = {
        let config = URLSessionConfiguration.default
        // Espera a rede voltar em vez de falhar na hora. Como nada na UI
        // depende desta resposta, esperar é sempre melhor que perder o evento.
        config.waitsForConnectivity = true
        // Generoso de propósito: cold start do Render free passa de 30s.
        config.timeoutIntervalForRequest = 60
        config.timeoutIntervalForResource = 120
        return URLSession(configuration: config)
    }()

    private var storeURL: URL {
        let dir = FileManager.default.urls(for: .applicationSupportDirectory, in: .userDomainMask)[0]
        try? FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
        return dir.appendingPathComponent("analytics-queue.json")
    }

    private init() {
        loadQueue()
        observeLifecycle()
    }

    // MARK: - API

    /// Enfileira um evento. Nunca bloqueia, nunca lança, nunca falha visível.
    ///
    /// `params` aceita String, número e Bool. As chaves que o backend indexa
    /// em coluna própria são `content_id`, `currency`, `value` e `source` —
    /// o resto fica no JSON e continua consultável, só não agregável.
    func track(_ event: AnalyticsEvent, _ params: [String: Any] = [:]) {
        guard isEnabled else {
            debugLog("ignorado (analytics desligado): \(event.rawValue)")
            return
        }

        queue.append(Payload(event: event.rawValue,
                             params: params,
                             ts: Int(Date().timeIntervalSince1970 * 1000)))

        if queue.count > maxQueued {
            queue.removeFirst(queue.count - maxQueued)
        }
        saveQueue()
        debugLog("na fila: \(event.rawValue) \(params) — fila com \(queue.count)")

        // Eventos de conversão saem na hora: são poucos, são os que mais
        // importam, e o usuário pode fechar o app logo depois de comprar.
        let urgent: Set<AnalyticsEvent> = [.subscribe, .startTrial, .checkoutInitiated]
        if urgent.contains(event) || queue.count >= batchSize {
            flush()
        }
    }

    /// Dispara `first_open` UMA VEZ por instalação e nunca mais.
    ///
    /// A marca vive em UserDefaults, que é apagado junto com o app na
    /// desinstalação — então reinstalar conta como instalação nova, que é o
    /// comportamento certo: sem user id, não há como saber que é a mesma pessoa.
    ///
    /// ⚠️ Quem JÁ completou o onboarding não é instalação nova — é usuário da
    /// base abrindo esta versão pela primeira vez. Sem este guard, o dia do
    /// release viraria um pico de "usuários novos" formado inteiramente por
    /// gente antiga, e a taxa install → assinatura despencaria sem que nada
    /// tivesse piorado. A flag é marcada de qualquer jeito, então o desconto
    /// acontece uma vez só por instalação.
    func trackFirstOpen() {
        let key = "analytics.once.\(AnalyticsEvent.firstOpen.rawValue)"
        guard !UserDefaults.standard.bool(forKey: key) else { return }

        // Marca ANTES de enfileirar. Se o app morrer no meio, o pior caso é
        // perder um evento — melhor que contar a mesma instalação duas vezes,
        // porque denominador inflado estraga toda taxa calculada sobre ele.
        UserDefaults.standard.set(true, forKey: key)

        let jaPassouPeloOnboarding = UserDefaults.standard.bool(
            forKey: "pedagogy.onboarding.completed"
        )
        guard !jaPassouPeloOnboarding else {
            debugLog("first_open suprimido — instalação antiga atualizando")
            return
        }

        track(.firstOpen)
    }

    /// Envia o que estiver na fila. Chamado por lote cheio, evento de
    /// conversão, ida pro background e volta do app.
    func flush() {
        guard isEnabled, !isFlushing, !queue.isEmpty else { return }

        let batch = Array(queue.prefix(50))
        isFlushing = true

        var request = URLRequest(url: endpoint)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        if let ingestToken {
            request.setValue(ingestToken, forHTTPHeaderField: "x-api-key")
        }

        guard let body = try? JSONSerialization.data(withJSONObject: batch.map(\.dictionary)) else {
            // Payload impossível de serializar: descarta em vez de travar a
            // fila pra sempre atrás de um evento defeituoso.
            log.error("payload inválido — descartando \(batch.count) evento(s)")
            queue.removeFirst(batch.count)
            saveQueue()
            isFlushing = false
            return
        }
        request.httpBody = body

        session.dataTask(with: request) { [weak self] _, response, error in
            Task { @MainActor in
                guard let self else { return }
                self.isFlushing = false

                let status = (response as? HTTPURLResponse)?.statusCode ?? 0
                if error == nil, (200..<300).contains(status) {
                    self.queue.removeFirst(min(batch.count, self.queue.count))
                    self.saveQueue()
                    self.debugLog("enviados \(batch.count) — HTTP \(status)")
                    // Sobrou coisa na fila (mais de 50)? Continua.
                    if !self.queue.isEmpty { self.flush() }
                } else if (400..<500).contains(status), status != 429 {
                    // 4xx que não seja rate limit é payload que o servidor
                    // nunca vai aceitar. Reenviar é loop infinito — descarta.
                    self.log.error("rejeitado com \(status) — descartando \(batch.count) evento(s)")
                    self.debugLog("REJEITADO com HTTP \(status) — \(batch.count) evento(s) descartado(s)")
                    self.queue.removeFirst(min(batch.count, self.queue.count))
                    self.saveQueue()
                } else {
                    // Rede caiu, servidor dormindo, 5xx: mantém na fila e
                    // tenta no próximo gatilho.
                    self.log.debug("envio adiado (status \(status))")
                    self.debugLog("adiado — HTTP \(status), erro: \(error?.localizedDescription ?? "nenhum"), \(self.queue.count) na fila")
                }
            }
        }.resume()
    }

    // MARK: - Ciclo de vida

    private func observeLifecycle() {
        let center = NotificationCenter.default
        observers.append(
            center.addObserver(forName: UIApplication.didEnterBackgroundNotification,
                               object: nil, queue: .main) { [weak self] _ in
                Task { @MainActor in self?.flush() }
            }
        )
        observers.append(
            center.addObserver(forName: UIApplication.didBecomeActiveNotification,
                               object: nil, queue: .main) { [weak self] _ in
                // Pega o que ficou de sessões anteriores — inclusive de um
                // launch em que o app foi morto antes de conseguir enviar.
                Task { @MainActor in self?.flush() }
            }
        )
    }

    // MARK: - Persistência

    private struct Payload: Codable {
        let event: String
        let params: [String: CodableValue]
        let ts: Int

        init(event: String, params: [String: Any], ts: Int) {
            self.event = event
            self.params = params.compactMapValues(CodableValue.init)
            self.ts = ts
        }

        var dictionary: [String: Any] {
            ["event": event, "params": params.mapValues(\.raw), "ts": ts]
        }
    }

    /// `[String: Any]` não é Codable. Este envelope aceita os três tipos que
    /// fazem sentido num parâmetro de evento e descarta o resto.
    private enum CodableValue: Codable {
        case string(String)
        case number(Double)
        case bool(Bool)

        init?(_ value: Any) {
            switch value {
            case let v as String: self = .string(v)
            case let v as Bool: self = .bool(v)
            case let v as Int: self = .number(Double(v))
            case let v as Double: self = .number(v)
            case let v as Decimal: self = .number(NSDecimalNumber(decimal: v).doubleValue)
            default: return nil
            }
        }

        var raw: Any {
            switch self {
            case .string(let v): return v
            case .number(let v): return v
            case .bool(let v): return v
            }
        }
    }

    private func saveQueue() {
        guard let data = try? JSONEncoder().encode(queue) else { return }
        try? data.write(to: storeURL, options: .atomic)
    }

    private func loadQueue() {
        guard let data = try? Data(contentsOf: storeURL),
              let saved = try? JSONDecoder().decode([Payload].self, from: data) else { return }
        queue = saved
    }
}
