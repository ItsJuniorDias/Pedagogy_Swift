//
//  AppDelegate.swift
//  pedagogy
//
//  ─── APPDELEGATE (mínimo, só pra notifications) ─────────────────────────────
//  SwiftUI @main App structs não são UIApplicationDelegate. Pra instalar um
//  UNUserNotificationCenter.delegate antes da primeira notif chegar (crítico
//  pra tap handling em cold-start), precisamos de um AppDelegate real
//  conectado via @UIApplicationDelegateAdaptor no pedagogyApp.
//
//  Este arquivo faz APENAS isso. Não gerencia state, não roda lógica de
//  business — só conecta o delegate. Toda a lógica de scheduling e
//  handling fica no NotificationManager.
//
//  ORDEM DE INICIALIZAÇÃO — importante
//
//  1. UIApplication cria o AppDelegate
//  2. AppDelegate cria o NotificationsDelegate e o NotificationManager
//  3. AppDelegate seta manager weak na NotificationsDelegate
//  4. AppDelegate seta NotificationsDelegate como UNUserNotificationCenter.delegate
//  5. SÓ ENTÃO o SwiftUI App é criado
//  6. pedagogyApp pega o manager via appDelegate e injeta no environment
//
//  Se essa ordem não fosse respeitada, um tap em notif que abre o app do
//  zero (cold start) chegaria antes do delegate existir — e seria perdido.
//  ────────────────────────────────────────────────────────────────────────────

import UIKit
import UserNotifications

final class AppDelegate: NSObject, UIApplicationDelegate {

    /// O manager de notificações. Criado aqui pra garantir que existe antes
    /// do UNUserNotificationCenter chamar o delegate. Exposto ao pedagogyApp
    /// via @UIApplicationDelegateAdaptor pra injeção no environment.
    let notificationManager = NotificationManager()

    /// Delegate leve que reage a eventos e delega ao manager. Mantido aqui
    /// (strong ref) pra o UNUserNotificationCenter não perder — ele guarda
    /// weak.
    private let notificationsDelegate = NotificationsDelegate()

    func application(
        _ application: UIApplication,
        didFinishLaunchingWithOptions launchOptions: [UIApplication.LaunchOptionsKey: Any]?
    ) -> Bool {
        notificationsDelegate.manager = notificationManager
        UNUserNotificationCenter.current().delegate = notificationsDelegate
        return true
    }
}
