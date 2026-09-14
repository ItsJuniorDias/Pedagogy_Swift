//
//  AchievementsStore.swift
//  pedagogy
//
//  ─── ACHIEVEMENTS STORE ─────────────────────────────────────────────────────
//  Guarda quais achievements o usuário já unlocou, com a data em que
//  isso aconteceu. Persiste em UserDefaults.
//
//  QUANDO CHAMAR checkForUnlocks(library:stories:)
//
//  O store é passivo — ele não observa LibraryProgress diretamente. Callers
//  precisam chamar quando faz sentido re-avaliar:
//    • ProfileView.task            (usuário abriu a tela)
//    • App.foreground              (voltou do background)
//    • Após markFinished / update  (opcional; garante unlock imediato mesmo
//                                    se o usuário fechar antes de abrir Profile)
//
//  Chamar múltiplas vezes é sempre seguro — o store só grava data nova
//  quando um achievement passa de locked pra unlocked. Uma vez unlocked,
//  a data original é preservada.
//
//  POR QUE UserDefaults e não SwiftData
//
//  Volume tiny (12 IDs + 12 datas ~ <500 bytes). SwiftData seria overkill.
//  Mesma decisão que LibraryProgress.
//
//  MIGRATION
//
//  Se um dia remover um achievement do enum, o UserDefaults ainda vai ter
//  o ID antigo. O decoder pula (não crash) mas o achievement fica "órfão"
//  no dicionário. Isso é benigno — não afeta UI porque Achievement.all
//  só lista os atuais. Se quiser limpar, adicione lógica de sweep no load().
//  ────────────────────────────────────────────────────────────────────────────

import Foundation
import SwiftUI

@Observable
@MainActor
final class AchievementsStore {
    private static let storageKey = "pedagogy.achievements.v1"

    /// Mapa de ID → data em que foi unlocked. Ausente = ainda locked.
    /// Público (readable) pra UI consultar diretamente sem passar por método.
    var unlocked: [AchievementID: Date] = [:]

    /// Achievement mais recente que passou de locked pra unlocked. Serve
    /// pra UI mostrar toast/animation quando um unlock acontece durante
    /// uma session. `nil` na maior parte do tempo. Consumido por quem
    /// mostra a UI, similar ao openedStoryID do NotificationManager.
    var recentlyUnlocked: AchievementID? = nil

    init() {
        load()
    }

    // MARK: - Public API

    /// True se o achievement já foi unlocked (a qualquer momento).
    func isUnlocked(_ id: AchievementID) -> Bool {
        unlocked[id] != nil
    }

    /// Data em que o achievement foi unlocked. Nil se ainda locked.
    func unlockedAt(_ id: AchievementID) -> Date? {
        unlocked[id]
    }

    /// Roda todos os requirements contra o library + stories atuais. Se
    /// algum achievement passou de locked pra unlocked, grava com Date.now
    /// e persiste. Se todos já unlocked ou nenhum mudou, no-op.
    ///
    /// Retorna os IDs que foram unlocked nesta chamada (pra caller mostrar
    /// UI se quiser).
    @discardableResult
    func checkForUnlocks(library: LibraryProgress, stories: [Story]) -> [AchievementID] {
        var newlyUnlocked: [AchievementID] = []
        let now = Date()

        for achievement in Achievement.all {
            guard unlocked[achievement.id] == nil else { continue }
            if achievement.isUnlocked(library, stories) {
                unlocked[achievement.id] = now
                newlyUnlocked.append(achievement.id)
            }
        }

        if !newlyUnlocked.isEmpty {
            save()
            // Guarda o último pra UI reagir (só o mais recente — se
            // múltiplos disparam junto, mostra um. Melhor UX que uma pilha).
            recentlyUnlocked = newlyUnlocked.last
        }

        return newlyUnlocked
    }

    /// Caller (view) chama depois de consumir/mostrar o toast/animation.
    /// Limpa pra não re-mostrar em re-renders.
    func consumeRecentlyUnlocked() {
        recentlyUnlocked = nil
    }

    /// Debug: zera tudo. Útil pra QA e pra futura tela de settings.
    func resetAll() {
        unlocked.removeAll()
        recentlyUnlocked = nil
        save()
    }

    // MARK: - Persistence

    /// Snapshot leve pra Codable. Chave é raw value do enum pra ser
    /// human-readable no plist (ajuda debugging via Simulator > Files).
    private struct Snapshot: Codable {
        var unlocked: [String: Date]
    }

    private func load() {
        guard let data = UserDefaults.standard.data(forKey: Self.storageKey),
              let snap = try? JSONDecoder().decode(Snapshot.self, from: data)
        else { return }

        var result: [AchievementID: Date] = [:]
        for (raw, date) in snap.unlocked {
            if let id = AchievementID(rawValue: raw) {
                result[id] = date
            }
            // IDs desconhecidos são silenciosamente ignorados (achievement
            // removido em versão nova do app). Não crash.
        }
        unlocked = result
    }

    private func save() {
        let snap = Snapshot(
            unlocked: Dictionary(uniqueKeysWithValues: unlocked.map { ($0.key.rawValue, $0.value) })
        )
        guard let data = try? JSONEncoder().encode(snap) else {
            print("[AchievementsStore] Failed to encode snapshot")
            return
        }
        UserDefaults.standard.set(data, forKey: Self.storageKey)
    }
}
