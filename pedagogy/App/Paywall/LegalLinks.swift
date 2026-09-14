//
//  LegalLinks.swift
//  pedagogy
//
//  ─── LINKS LEGAIS ───────────────────────────────────────────────────────────
//  URLs de Terms of Use (EULA) e Política de Privacidade, num lugar só.
//
//  POR QUE UM ARQUIVO PRÓPRIO
//
//  Hoje só o paywall usa (LegalFooter). Mas esses dois links precisam aparecer
//  em pelo menos mais um lugar antes do release — a tela de Settings, pra quem
//  já assinou e não vê mais o paywall. Se as strings ficarem duplicadas nas
//  duas telas, uma hora uma some do ar e a outra não é atualizada.
//
//  ONDE MAIS ESSAS URLS PRECISAM ESTAR (fora do app)
//
//    • App Store Connect → App Privacy → Privacy Policy URL
//    • App Store Connect → App Information → EULA (se usar EULA custom em vez
//      do padrão da Apple; como aqui é EULA próprio, precisa colar lá)
//
//  As duas páginas são Notion. O que identifica a página é o ID hexadecimal no
//  fim da URL — o slug antes dele é derivado do título, então renomear a página
//  no Notion NÃO quebra o link (o Notion redireciona pelo ID). Mudar a página
//  de workspace ou despublicar, sim.
//
//  ⚠️ As páginas precisam estar com "Share → Publish to web" LIGADO. Uma página
//  privada abre tela de login — o App Review trata isso como link quebrado e
//  rejeita (Guideline 3.1.2, assinatura sem termos acessíveis).
//  ────────────────────────────────────────────────────────────────────────────

import Foundation

enum LegalLinks {

    /// Terms of Use / EULA. Exigido pela Apple em todo paywall de assinatura.
    static let termsOfUse = URL(
        string: "https://infrequent-dogsled-350.notion.site/Terms-of-Use-EULA-Pedagogy-3790df0a2e798017b3d2d9d60a5d8308"
    )

    /// Política de Privacidade. Exigida pra qualquer app com IAP, e conferida
    /// com lupa se o app for pra categoria Kids.
    static let privacyPolicy = URL(
        string: "https://infrequent-dogsled-350.notion.site/Pol-tica-de-Privacidade-Pedagogy-3750df0a2e798004a8fcd6029d729866"
    )
}
