//
//  pedagogyApp.swift
//  pedagogy
//
//  Entry point do app.
//
//  Responsabilidades:
//    1. Cria as instâncias únicas de `Store` (StoreKit 2) e `LibraryProgress`
//       (progresso de leitura) e injeta ambas via environment.
//    2. Injeta o `NotificationManager` que vive dentro do AppDelegate (ele
//       precisa ser criado ANTES do App pra o UNUserNotificationCenter delegate
//       ficar pronto pra taps em cold-start). Ver AppDelegate.swift.
//    3. Carrega os produtos StoreKit no launch (task assíncrona não bloqueia UI).
//    4. Agenda notifs locais de "nova história esta semana" no launch e
//       toda vez que o app volta pro foreground — mantém sync mesmo se
//       ficou dias fechado ou o usuário mudou permissão nas Settings.
//    5. Aponta pra `RootView`, que decide entre onboarding e home baseado em
//       `@AppStorage("pedagogy.onboarding.completed")`.
//

import SwiftUI

@main
struct pedagogyApp: App {
    /// AppDelegate leve que existe SÓ pra instalar o UNUserNotificationCenter
    /// delegate antes de o SwiftUI App existir (crítico pra tap handling em
    /// cold-start). Traz junto o NotificationManager que injetamos no env.
    @UIApplicationDelegateAdaptor(AppDelegate.self) private var appDelegate

    // `@State` guarda instâncias que sobrevivem a re-renderizações do App.
    // Ambas são `@Observable`, então mudanças propagam automaticamente pra
    // views que leem via `@Environment(Type.self)`.
    @State private var store = Store()
    @State private var library = LibraryProgress()
    @State private var achievements = AchievementsStore()
    /// Player global — vive no App scope pra manter playback rodando
    /// enquanto o usuário navega entre tabs / abre sheets / etc.
    @State private var audio = AudioPlayerManager()
    /// Tradução nativa (framework Translation) do conteúdo das histórias.
    @State private var translation = TranslationStore()

    /// Precisamos observar quando o app volta do background pra re-agendar
    /// notifs (podem ter expirado; permissão pode ter mudado nas Settings).
    @Environment(\.scenePhase) private var scenePhase

    /// Versão marketing (CFBundleShortVersionString). Vai junto do `app_open`
    /// pra dar pra distinguir, na lista de eventos crus do dashboard, o que veio
    /// da build nova e o que ainda é de quem não atualizou.
    ///
    /// Fica só no JSON do params (o backend indexa `source`, `content_id`,
    /// `currency` e `value` em coluna). Serve pra ler evento a evento, não pra
    /// agrupar — se um dia você quiser adoção por versão, precisa de coluna.
    private static var appVersion: String {
        Bundle.main.object(forInfoDictionaryKey: "CFBundleShortVersionString") as? String ?? "?"
    }

    init() {
        #if DEBUG
        FontDebug.report()
        #endif
    }

    var body: some Scene {
        WindowGroup {
            RootView()
                // Precisa vir antes do `.environment(translation)` — o host lê
                // o store do environment.
                .translationHost()
                .environment(store)
                .environment(library)
                .environment(achievements)
                .environment(audio)
                .environment(appDelegate.notificationManager)
                .environment(translation)
                .task {
                    // Não bloqueia nada: até responder, `text(_:)` devolve
                    // o original.
                    await translation.refreshAvailability()
                }
                .task {
                    // Topo do funil. Roda antes de tudo porque `first_open` é
                    // o denominador de todas as taxas — se ele se perder num
                    // await que falhou, o resto do dia fica sem base.
                    //
                    // Ordem proposital: `first_open` antes de `app_open`, pra
                    // a primeira sessão de uma instalação nova chegar no
                    // backend na sequência que se lê.
                    Analytics.shared.trackFirstOpen()
                    Analytics.shared.track(.appOpen, ["app_version": Self.appVersion])

                    // Carrega os produtos StoreKit em background no primeiro
                    // launch. Se o usuário chegar no paywall antes de terminar,
                    // o paywall mostra loading — não trava a Home.
                    await store.load()

                    // Agenda as notifs locais de publish. Idempotente: cancela
                    // pending "story-publish-*" e re-agenda pra cada story
                    // futura. Se authStatus != .authorized, sai silenciosamente.
                    // Roda em paralelo com o store.load acima.
                    await rescheduleNotifications()

                    // Re-avalia achievements com o snapshot atual. Cobre o
                    // caso de usuário que leu offline, streak avançou por
                    // conta do tempo, ou app atualizou pra versão com
                    // achievements novos que agora satisfazem requirements
                    // antigos.
                    await checkAchievements()
                }
        }
        .onChange(of: scenePhase) { _, newPhase in
            // Ao voltar pro foreground: refresh status (usuário pode ter
            // trocado permissão nas Settings) e re-agenda notifs (pode ter
            // ficado dias fechado e algumas expiraram naturalmente).
            if newPhase == .active {
                Task {
                    await appDelegate.notificationManager.refreshAuthorizationStatus()
                    await rescheduleNotifications()
                    await checkAchievements()
                }
            }
        }
    }

    /// Carrega TODAS as histórias do bundle e passa pro manager. O
    /// StoryLoader é rápido (<10ms pra dezenas de JSONs) então roda a cada
    /// scheduling — evita cachear em outro estado observável só pra isso.
    private func rescheduleNotifications() async {
        do {
            let stories = try StoryLoader.loadAll()
            await appDelegate.notificationManager.scheduleAllPending(stories: stories)
        } catch {
            print("[pedagogyApp] Failed to load stories for scheduling: \(error)")
        }
    }

    /// Roda o check de achievements no launch e ao voltar do foreground.
    /// Duplica o load do StoryLoader mas isso é aceitável (<10ms) e evita
    /// criar um cache observável só pra economizar. Se um dia o loader
    /// virar caro, faz cache separado.
    private func checkAchievements() async {
        do {
            let stories = try StoryLoader.loadAll()
            achievements.checkForUnlocks(library: library, stories: stories)
        } catch {
            print("[pedagogyApp] Failed to load stories for achievements: \(error)")
        }
    }
}

// MARK: - Font Debug

/// Diagnóstico completo das fontes custom. Roda uma vez no launch em DEBUG.
///
/// Investiga 4 níveis em ordem, do menor pro maior escopo:
///
///   1. Info.plist do bundle — o valor real de UIAppFonts que o iOS vê
///   2. Filesystem — quais .ttf estão fisicamente no bundle
///   3. Runtime — cada uma das 8 fontes esperadas: registrou ou não
///   4. Runtime — TODAS as famílias custom registradas (não filtradas)
///
/// Com esses 4 blocos você sabe EXATAMENTE em que camada o problema está:
///
///   • UIAppFonts com paths errados / mal formatado → aparece no bloco 1
///   • TTFs não copiadas pro bundle → bloco 2 vazio
///   • Nome PostScript diferente do esperado → bloco 3 falha mas bloco 4 lista
///   • TTFs no bundle mas UIAppFonts as excluiu → bloco 2 lista mas 3+4 vazios
#if DEBUG
enum FontDebug {
    static let expected = [
        "AlfaSlabOne-Regular",
        "Lora-Regular", "Lora-Medium", "Lora-SemiBold", "Lora-Bold",
    ]

    static func report() {
        print("")
        print("═══════════════════════════════════════════════════════════")
        print("[Font Debug] Iniciando diagnóstico de fontes custom")
        print("═══════════════════════════════════════════════════════════")

        reportInfoPlistFonts()
        reportBundledTTFs()
        reportExpectedFonts()
        reportAllCustomFamilies()

        print("═══════════════════════════════════════════════════════════")
        print("")
    }

    // MARK: 1. Info.plist real do bundle

    /// Lê o valor de UIAppFonts DIRETO do Info.plist embutido no .app.
    /// Se depois de aplicar o fix isso ainda mostrar paths tipo
    /// "Resources/Fonts/...", significa que o Xcode não recompilou o plist
    /// (cache) — precisa Clean Build Folder e Delete app do simulador.
    private static func reportInfoPlistFonts() {
        print("")
        print("[1] Info.plist → UIAppFonts (o que o iOS vê ao lançar):")

        guard let raw = Bundle.main.object(forInfoDictionaryKey: "UIAppFonts") else {
            print("  ⚠️  UIAppFonts não existe no Info.plist do bundle")
            print("      → build settings não gerou a chave. Verifique")
            print("        INFOPLIST_KEY_UIAppFonts nas Build Settings.")
            return
        }

        if let array = raw as? [String] {
            print("  Formato: Array<String> (correto)")
            for entry in array {
                let hasPath = entry.contains("/")
                let marker = hasPath ? "❌" : "✓ "
                print("    \(marker) \(entry)\(hasPath ? "  <- TEM PATH, iOS não vai achar" : "")")
            }
        } else if let s = raw as? String {
            print("  Formato: String única (INESPERADO — deveria ser Array)")
            print("    conteúdo: \(s)")
        } else {
            print("  Formato inesperado: \(type(of: raw))")
            print("    valor: \(raw)")
        }
    }

    // MARK: 2. TTFs fisicamente no bundle

    /// Escaneia o bundle inteiro procurando arquivos .ttf. Mostra o CAMINHO
    /// completo — se aparecerem em subpastas tipo "Resources/Fonts/" isso é
    /// atípico e sugere que o Xcode preservou estrutura (raro com sync
    /// group), o que quebra o registro via UIAppFonts (que espera flat).
    private static func reportBundledTTFs() {
        print("")
        print("[2] Arquivos .ttf fisicamente no bundle:")

        let bundlePath = Bundle.main.bundlePath
        guard let enumerator = FileManager.default.enumerator(atPath: bundlePath) else {
            print("  ⚠️  Não consegui enumerar o bundle path: \(bundlePath)")
            return
        }

        var ttfs: [String] = []
        for case let path as String in enumerator {
            if path.lowercased().hasSuffix(".ttf") || path.lowercased().hasSuffix(".otf") {
                ttfs.append(path)
            }
        }

        if ttfs.isEmpty {
            print("  ❌ NENHUM arquivo .ttf/.otf encontrado no bundle!")
            print("     → O file system sync do Xcode NÃO copiou as fontes.")
            print("     → Possíveis causas:")
            print("        (a) As TTFs estão em pasta que o sync ignora")
            print("        (b) Uma PBXFileSystemSynchronizedBuildFileExceptionSet")
            print("            está excluindo essas fontes desse target")
            print("        (c) O membership do target não inclui essas fontes")
        } else {
            print("  Encontrei \(ttfs.count) arquivo(s):")
            for path in ttfs.sorted() {
                print("    • \(path)")
            }
        }
    }

    // MARK: 3. Fontes esperadas registradas?

    /// Testa cada uma das 8 fontes que a Typography.swift referencia.
    /// UIFont(name:) retorna nil se a fonte não estiver registrada — é o
    /// teste real de "posso usar essa fonte agora?".
    private static func reportExpectedFonts() {
        print("")
        print("[3] Fontes esperadas (o que Typography.swift precisa):")

        var missing: [String] = []
        for name in expected {
            if UIFont(name: name, size: 12) != nil {
                print("  ✅ \(name)")
            } else {
                print("  ❌ \(name)  <- NÃO CARREGOU")
                missing.append(name)
            }
        }

        if missing.isEmpty {
            print("  🎉 Todas as 8 fontes carregaram. Pode remover FontDebug.")
        }
    }

    // MARK: 4. TODAS as famílias custom

    /// Lista TODAS as famílias registradas que não são system fonts. Sem
    /// filtro. Se alguma Alfa/Lora aparecer aqui com nome diferente do
    /// esperado, ajuste os literais em Typography.swift → FontName pra
    /// bater. Se nada aparecer, o problema é que as fontes não registraram.
    private static func reportAllCustomFamilies() {
        print("")
        print("[4] TODAS as famílias custom registradas:")

        // Lista bem grande de prefixos de famílias system pra filtrar
        // (não é exaustiva; qualquer coisa que passar aparece — se aparecer
        // muito lixo, aumente essa lista).
        let systemPrefixes = [
            "System", ".", "Academy", "Al ", "Al N", "American", "Apple",
            "Arial", "Avenir", "Baskerville", "Bodoni", "Bradley", "Chalkboard",
            "Chalkduster", "Cochin", "Copperplate", "Courier", "Damascus",
            "Devanagari", "Didot", "DIN ", "Euphemia", "Farah", "Futura",
            "Galvji", "Geeza", "Georgia", "Gill", "Grantha", "Gujarati",
            "Gurmukhi", "Helvetica", "Hiragino", "Hoefler", "Impact", "Kailasa",
            "Kannada", "Kefa", "Khmer", "Kohinoor", "Lao", "Malayalam",
            "Marion", "Marker", "Menlo", "Mishafi", "Mukta", "Muna", "Myanmar",
            "Nanum", "New ", "Noteworthy", "Noto", "Optima", "Oriya", "Palatino",
            "Papyrus", "Party", "PingFang", "Rockwell", "Sana", "SF ", "Savoye",
            "Sinhala", "Snell", "STIX", "Symbol", "Tamil", "Telugu", "Thonburi",
            "Times", "Trebuchet", "Verdana", "Zapf",
        ]

        let custom = UIFont.familyNames
            .filter { family in
                !systemPrefixes.contains { family.hasPrefix($0) }
            }
            .sorted()

        if custom.isEmpty {
            print("  ❌ NENHUMA família custom registrada.")
            print("     → Se [2] mostrou TTFs no bundle mas nada aqui,")
            print("       o UIAppFonts está desconfigurado (veja [1]).")
            print("     → Se [2] estava vazio também, é problema de bundling.")
        } else {
            print("  Encontrei \(custom.count) família(s):")
            for family in custom {
                print("  Family: \(family)")
                for name in UIFont.fontNames(forFamilyName: family) {
                    print("    PostScript: \(name)")
                }
            }
        }
    }
}
#endif
