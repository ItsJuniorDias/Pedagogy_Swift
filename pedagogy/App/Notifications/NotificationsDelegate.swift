//
//  NotificationsDelegate.swift
//  pedagogy
//
//  ─── UNUserNotificationCenterDelegate ───────────────────────────────────────
//  Responde a dois eventos do sistema:
//
//    1. willPresent — notif chegou enquanto o app tá em foreground.
//       Sem delegate, iOS suprime a notif silenciosamente. Aqui pedimos pra
//       ele mostrar banner + tocar som mesmo em foreground — o usuário
//       merece o feedback.
//
//    2. didReceive — usuário TOCOU numa notif (do lock screen, notification
//       center, ou banner). Extraímos o `story_id` do userInfo e passamos
//       pro NotificationManager, que expõe via `openedStoryID` pra views
//       navegarem.
//
//  ARQUITETURA — por que classe separada e não o próprio Manager?
//
//  UNUserNotificationCenterDelegate exige NSObject conformance. Nosso
//  NotificationManager é uma struct-like @Observable @MainActor final class
//  que não herda de NSObject (e não queremos que herde — polui a API).
//  Por isso um NSObject leve dedicado, que só delega pro manager real.
//
//  INSTALADO POR
//
//  AppDelegate.swift, em didFinishLaunchingWithOptions. PRECISA acontecer
//  ANTES da primeira notif chegar — se o app abrir a partir do tap numa
//  notif e o delegate ainda não estiver instalado, o tap é perdido.
//  ────────────────────────────────────────────────────────────────────────────

import UIKit
import UserNotifications

final class NotificationsDelegate: NSObject, UNUserNotificationCenterDelegate {

    /// Referência (weak) pro manager. Setada pelo AppDelegate depois de
    /// criar o manager. Weak pra não criar retain cycle com o environment
    /// injection do SwiftUI.
    weak var manager: NotificationManager?

    // MARK: - Foreground presentation

    /// Chamado quando uma notif chega e o app tá em foreground. Retornamos
    /// as opções de apresentação — sem isso, iOS suprime silenciosamente.
    /// `.banner` mostra o toast no topo; `.sound` toca; `.list` adiciona ao
    /// Notification Center.
    nonisolated func userNotificationCenter(
        _ center: UNUserNotificationCenter,
        willPresent notification: UNNotification
    ) async -> UNNotificationPresentationOptions {
        return [.banner, .sound, .list]
    }

    // MARK: - Tap handling

    /// Chamado quando o usuário toca na notif (foreground, background, ou
    /// cold-start via tap no lock screen). Extraímos o story_id do userInfo
    /// e delegamos pro manager.
    nonisolated func userNotificationCenter(
        _ center: UNUserNotificationCenter,
        didReceive response: UNNotificationResponse
    ) async {
        let userInfo = response.notification.request.content.userInfo
        guard let storyID = userInfo["story_id"] as? String else { return }

        // Hop pra main actor pra tocar no @MainActor manager.
        await MainActor.run {
            self.manager?.setOpenedStoryID(storyID)
        }
    }
}
