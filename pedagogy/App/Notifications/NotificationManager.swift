//
//  NotificationManager.swift
//  pedagogy
//
//  ─── LOCAL NOTIFICATIONS MANAGER ────────────────────────────────────────────
//  Agenda notificações locais pra avisar quando novas histórias são
//  desbloqueadas (baseado em `Story.publishedAt`). Zero backend — tudo roda
//  no device.
//
//  POR QUE LOCAL E NÃO REMOTE (APNs)
//
//  1. Todas as 50 histórias já estão embarcadas no bundle com `publishedAt`
//     fixo. Nada dinâmico vem de servidor.
//  2. `Story.isFreeToRead(now:)` já usa esse `publishedAt` pra decidir a
//     janela grátis semanal — as notifs seguem a mesma verdade.
//  3. Zero infra: sem APNs key, sem certificado, sem provider, sem token.
//  4. Funciona offline. O device dispara sozinho baseado no relógio.
//  5. Sem custo, sem retenção de logs, sem GDPR/backend.
//
//  Se um dia surgirem eventos verdadeiramente dinâmicos (nova história
//  publicada FORA do calendário embarcado, ou pushes de retenção
//  segmentados), aí faz sentido adicionar APNs em cima disso — sem
//  remover este manager. Local resolve o caso "novas histórias liberadas
//  esta semana"; remote resolveria "campanhas".
//
//  ARQUITETURA
//
//  1. Este arquivo: @Observable @MainActor class com API pública clara.
//     Injetado via .environment(_:) no pedagogyApp.
//  2. NotificationsDelegate.swift: NSObject : UNUserNotificationCenterDelegate.
//     Trata apresentação em foreground e tap. Publica `openedStoryID`.
//  3. AppDelegate.swift: instala o delegate no UNUserNotificationCenter no
//     launch. Precisa ser feito ANTES de qualquer chamada de notification.
//
//  QUANDO AGENDAR
//
//  Chame `scheduleAllPending(stories:)` em 3 momentos:
//    • App launch (task do WindowGroup)
//    • Depois do usuário completar onboarding e conceder permissão
//    • Ao voltar do background (garante sync mesmo se o app ficou dias
//      fechado e alguma noti expirou naturalmente)
//
//  A operação é idempotente: cancela todas as pending "story-publish-*"
//  antes de re-agendar, então chamar múltiplas vezes é seguro.
//
//  LIMITE iOS
//
//  iOS permite até 64 notifs locais pendentes simultâneas por app. Este
//  app agenda até ~50 (uma por história futura). Se o número crescer,
//  filtre pra só agendar as próximas 60 e re-agende ao entrar foreground.
//  ────────────────────────────────────────────────────────────────────────────

import Foundation
import SwiftUI
import UserNotifications

// MARK: - AuthorizationStatus

/// Espelho simplificado do UNAuthorizationStatus. Mais fácil de raciocinar
/// em SwiftUI do que o enum bruto do UserNotifications (que tem casos como
/// `.provisional` e `.ephemeral` que não fazem sentido pra este app).
enum NotificationAuthStatus: Equatable {
    /// Nunca perguntamos ao usuário. UI deve mostrar affordance pra pedir.
    case notDetermined
    /// Usuário negou explicitamente. Não podemos re-pedir programaticamente
    /// — só levar ele pras Settings do sistema.
    case denied
    /// Concedeu. Podemos agendar.
    case authorized

    init(_ raw: UNAuthorizationStatus) {
        switch raw {
        case .notDetermined:                     self = .notDetermined
        case .denied:                            self = .denied
        case .authorized, .provisional, .ephemeral: self = .authorized
        @unknown default:                        self = .notDetermined
        }
    }
}

// MARK: - NotificationManager (@Observable — injetado via environment)

@Observable
@MainActor
final class NotificationManager {
    /// Prefixo do identifier de toda notif de "story publish". Usar prefixo
    /// permite limpar seletivamente sem tocar em outras notifs (streak, etc)
    /// que este manager talvez agende no futuro.
    private static let storyPublishPrefix = "story-publish-"

    /// Hora do dia em que as notifs de publish disparam (local time). 9am
    /// funciona bem: começo do dia, criança acorda, boa hora de "olha, nova
    /// história disponível". Se quiser configurável, exponha via
    /// @AppStorage e passe no scheduleAllPending().
    private static let publishHour = 9
    private static let publishMinute = 0

    /// Status atual de autorização. Atualiza automaticamente após
    /// `refreshAuthorizationStatus()` e `requestAuthorization()`.
    var authStatus: NotificationAuthStatus = .notDetermined

    /// Story ID que o usuário abriu tocando numa notificação. `nil` quando
    /// não há deep link pendente. Views (RootView / MainTabView) observam
    /// isso, navegam pra StoryDetail, e chamam `consumeOpenedStoryID()`
    /// pra limpar. Padrão de "pending navigation" — não navega direto daqui
    /// porque o manager não conhece o hierarchy de navegação.
    var openedStoryID: String? = nil

    private let center = UNUserNotificationCenter.current()

    init() {
        // No init: consulta status atual sem pedir permissão. O
        // request explícito acontece via requestAuthorization() quando
        // o usuário aceita o prompt de UI (na onboarding page 4).
        Task { await refreshAuthorizationStatus() }
    }

    // MARK: - Public API

    /// Atualiza `authStatus` lendo o estado real do sistema. Chame ao
    /// entrar foreground (usuário pode ter mudado nas Settings enquanto o
    /// app estava fechado).
    func refreshAuthorizationStatus() async {
        let settings = await center.notificationSettings()
        self.authStatus = NotificationAuthStatus(settings.authorizationStatus)
    }

    /// Pede permissão pro sistema. Chama SÓ depois de mostrar UI de valor
    /// (ex: OnboardingPage4). O iOS mostra o alert nativo uma única vez —
    /// se o usuário negar, não podemos re-pedir programaticamente.
    ///
    /// Retorna `true` se concedeu. Após retornar, `authStatus` já está
    /// atualizado.
    @discardableResult
    func requestAuthorization() async -> Bool {
        do {
            let granted = try await center.requestAuthorization(
                options: [.alert, .sound, .badge]
            )
            await refreshAuthorizationStatus()
            return granted
        } catch {
            // Erros aqui são raros (só acontecem se o processo de sistema
            // estiver anormal). Silenciar — a UI vai ver authStatus como
            // .notDetermined ou .denied e reagir apropriadamente.
            print("[NotificationManager] requestAuthorization failed: \(error)")
            await refreshAuthorizationStatus()
            return false
        }
    }

    /// Idempotente: cancela todas as pending "story-publish-*" e agenda
    /// uma por história com `publishedAt` no futuro. Chame no launch, após
    /// onboarding, e ao voltar do background.
    ///
    /// Se `authStatus != .authorized`, sai silenciosamente — não faz
    /// sentido agendar pra depois falhar na hora de mostrar.
    func scheduleAllPending(stories: [Story], now: Date = .now) async {
        guard authStatus == .authorized else { return }

        // 1. Limpa as pending de "story-publish-*" antes de agendar. Não
        //    toca em outros identifiers (streak, custom, etc).
        let pending = await center.pendingNotificationRequests()
        let toRemove = pending
            .map(\.identifier)
            .filter { $0.hasPrefix(Self.storyPublishPrefix) }
        if !toRemove.isEmpty {
            center.removePendingNotificationRequests(withIdentifiers: toRemove)
        }

        // 2. Agenda uma por story com publishedAt no futuro. iOS limita a
        //    64 pending por app; se um dia tivermos mais que isso de
        //    stories futuras, filtramos pras próximas 60 aqui.
        let cal = Calendar.current
        let future = stories.compactMap { story -> (Story, Date)? in
            guard let pub = story.publishedAt, pub > now else { return nil }
            // Move o disparo pra 9am local do dia de publish (o Date no
            // JSON é meia-noite UTC — pouco útil como hora de push).
            var comps = cal.dateComponents([.year, .month, .day], from: pub)
            comps.hour = Self.publishHour
            comps.minute = Self.publishMinute
            guard let fireDate = cal.date(from: comps), fireDate > now else {
                return nil
            }
            return (story, fireDate)
        }

        // 3. Cria uma request por story. Preserva a ordem por data de
        //    publish (mais próxima primeiro) — importante caso caiamos no
        //    limite de 64 e precisemos truncar no futuro.
        let sorted = future.sorted { $0.1 < $1.1 }
        for (story, fireDate) in sorted {
            let request = makePublishRequest(story: story, fireDate: fireDate)
            do {
                try await center.add(request)
            } catch {
                print("[NotificationManager] add(request) failed for \(story.id): \(error)")
            }
        }
    }

    /// Cancela todas as pending deste manager. Útil pra debug/settings
    /// (ex: "desabilitar lembretes"). Não revoga permissão do sistema.
    func cancelAll() async {
        let pending = await center.pendingNotificationRequests()
        let toRemove = pending
            .map(\.identifier)
            .filter { $0.hasPrefix(Self.storyPublishPrefix) }
        center.removePendingNotificationRequests(withIdentifiers: toRemove)
    }

    /// View chama isso APÓS navegar pra história. Limpa o pending pra evitar
    /// re-navegação em re-renderizações. Padrão action-then-consume.
    func consumeOpenedStoryID() {
        openedStoryID = nil
    }

    /// Chamado pelo NotificationsDelegate quando o usuário toca numa
    /// notification e o payload aponta pra uma story. Interno — não chame
    /// direto de views.
    func setOpenedStoryID(_ id: String) {
        openedStoryID = id
    }

    // MARK: - Private: request builders

    private func makePublishRequest(story: Story, fireDate: Date) -> UNNotificationRequest {
        let content = UNMutableNotificationContent()
        content.title = "New story this week"
        content.body = story.title
        content.sound = .default
        // Payload usado pelo delegate pra deep link. Sempre inclua "story_id"
        // pra qualquer notif que deva abrir uma história.
        content.userInfo = ["story_id": story.id]
        // Categoria facilita ações rápidas no futuro (ex: "Read now",
        // "Remind me later"). Por ora sem actions.
        content.categoryIdentifier = "STORY_PUBLISH"

        let comps = Calendar.current.dateComponents(
            [.year, .month, .day, .hour, .minute],
            from: fireDate
        )
        let trigger = UNCalendarNotificationTrigger(
            dateMatching: comps,
            repeats: false
        )

        return UNNotificationRequest(
            identifier: "\(Self.storyPublishPrefix)\(story.id)",
            content: content,
            trigger: trigger
        )
    }
}
