//
//  OnboardingPage.swift
//  pedagogy
//
//  ─── ONBOARDING PAGES v2.1 ──────────────────────────────────────────────────
//  Rewrite completo. Antes: 3 páginas genéricas com título + subtitle +
//  ilustração 1:1 estilo "welcome/features/streak". Agora: 3 páginas que
//  MOSTRAM o produto em vez de descrevê-lo.
//
//  As 3 páginas
//
//    1. "A quiet place to read"
//       — Preview de uma página real do reader (Lora serif, texto longo).
//       O usuário vê imediatamente o que vai ler.
//
//    2. "Come back tomorrow"
//       — Preview de um chapter ending com "Chapter 2 of 3" e cliffhanger.
//       O usuário sente o loop de "quero saber o que acontece".
//
//    3. "The House of Clocks"
//       — Capa real da primeira história (que é grátis) + CTA "Start reading".
//       O usuário já sai lendo, não caindo em Home fria.
//
//  Modelo simplificado
//
//  Antes: OnboardingPageModel tinha title, subtitle, image, accent, background.
//  Agora: cada página é uma view própria (Page1Content, Page2Content, etc)
//  porque cada uma tem layout único — não faz sentido forçar template. O
//  container OnboardingView só sabe "existem 3 páginas, indexadas 0-2".
//  ────────────────────────────────────────────────────────────────────────────

import SwiftUI

// MARK: - Page 1: "A quiet place to read"
//
// Mostra uma página aberta do reader com Lora serif. Texto real de um
// parágrafo da primeira história (House of Clocks) — sem placeholder,
// sem lorem ipsum. O leitor já vê o que vai encontrar.

struct OnboardingPage1: View {
    var body: some View {
        VStack(spacing: Theme.Space.xxxl) {
            Spacer(minLength: Theme.Space.xxl)

            // ─── PREVIEW: página aberta ────────────────────────────
            BookPagePreview()
                .padding(.horizontal, Theme.Space.xxl)

            Spacer(minLength: Theme.Space.xxl)

            // ─── COPY ──────────────────────────────────────────────
            VStack(spacing: Theme.Space.md) {
                Text("A quiet place\nto read")
                    .displayTitle(size: 34)
                    .multilineTextAlignment(.center)
                    .fixedSize(horizontal: false, vertical: true)

                Text("Long-form stories. One chapter at a time.")
                    .font(.body(16, weight: .regular))
                    .foregroundStyle(Theme.Colors.textMuted)
                    .multilineTextAlignment(.center)
                    .padding(.horizontal, Theme.Space.xxl)
            }

            Spacer(minLength: Theme.Space.xxxl)
        }
    }
}

/// Preview visual de uma página do reader. Título de capítulo + 2 parágrafos
/// em Lora serif, contido num "papel" branco com sombra hard Mignola.
private struct BookPagePreview: View {
    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Space.md) {
            // Chapter header
            VStack(alignment: .leading, spacing: 4) {
                Text("CHAPTER 1")
                    .font(.ui(10, weight: .bold))
                    .tracking(1.5)
                    .foregroundStyle(Theme.Colors.textMuted)
                Text("The Backwards Clock")
                    .font(.display(18, weight: .bold))
                    .foregroundStyle(Theme.Colors.ink)
            }

            // Hairline divider
            Rectangle()
                .fill(Theme.Colors.border)
                .frame(height: 1)
                .padding(.vertical, Theme.Space.xs)

            // 2 parágrafos em serif
            VStack(alignment: .leading, spacing: Theme.Space.md) {
                Text("The train pulled away from the tiny station, and Wren was alone on the platform.")
                    .font(.body(15, weight: .regular))
                    .foregroundStyle(Theme.Colors.textStrong)
                    .lineSpacing(6)

                Text("Fellwick was smaller than she had expected. Two streets, a bakery, a post office…")
                    .font(.body(15, weight: .regular))
                    .foregroundStyle(Theme.Colors.textStrong)
                    .lineSpacing(6)
                    .lineLimit(2)
            }
        }
        .padding(Theme.Space.xl)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(Theme.Colors.surface)
        .clipShape(RoundedRectangle(cornerRadius: Theme.Radius.md))
        .overlay(
            RoundedRectangle(cornerRadius: Theme.Radius.md)
                .stroke(Theme.Colors.stroke, lineWidth: Theme.Stroke.normal)
        )
        .hardShadow(
            RoundedRectangle(cornerRadius: Theme.Radius.md),
            offset: CGSize(width: 4, height: 5)
        )
    }
}

// MARK: - Page 2: "Come back tomorrow"
//
// Mostra o final de um capítulo com "Chapter 2 of 3" no header (indicando
// que ainda tem mais) e a última linha de um cliffhanger. Comunica o
// mecanismo do produto: cada história tem 3 chapters, cada chapter termina
// em cliffhanger, streak cresce com o hábito diário.

struct OnboardingPage2: View {
    var body: some View {
        VStack(spacing: Theme.Space.xxxl) {
            Spacer(minLength: Theme.Space.xxl)

            // ─── PREVIEW: fim de capítulo ──────────────────────────
            CliffhangerPreview()
                .padding(.horizontal, Theme.Space.xxl)

            Spacer(minLength: Theme.Space.xxl)

            // ─── COPY ──────────────────────────────────────────────
            VStack(spacing: Theme.Space.md) {
                Text("Come back\ntomorrow")
                    .displayTitle(size: 34)
                    .multilineTextAlignment(.center)
                    .fixedSize(horizontal: false, vertical: true)

                Text("Each chapter ends with a cliffhanger. Your streak grows daily.")
                    .font(.body(16, weight: .regular))
                    .foregroundStyle(Theme.Colors.textMuted)
                    .multilineTextAlignment(.center)
                    .padding(.horizontal, Theme.Space.xxl)
            }

            Spacer(minLength: Theme.Space.xxxl)
        }
    }
}

private struct CliffhangerPreview: View {
    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Space.md) {
            // Chapter progress indicator
            HStack(spacing: Theme.Space.xs) {
                Text("CHAPTER 2 OF 3")
                    .font(.ui(10, weight: .bold))
                    .tracking(1.5)
                    .foregroundStyle(Theme.Colors.textMuted)
                Spacer()
                // Streak mock
                HStack(spacing: 3) {
                    Image(systemName: "flame.fill")
                        .font(.system(size: 9, weight: .bold))
                    Text("2")
                        .font(.ui(11, weight: .bold))
                }
                .foregroundStyle(Theme.Colors.ink)
            }

            Rectangle()
                .fill(Theme.Colors.border)
                .frame(height: 1)
                .padding(.vertical, Theme.Space.xs)

            // Trecho final do capítulo (cliffhanger)
            VStack(alignment: .leading, spacing: Theme.Space.md) {
                Text("The clock on the wall began to tick.")
                    .font(.body(15, weight: .regular))
                    .foregroundStyle(Theme.Colors.textStrong)
                    .lineSpacing(6)

                Text("Then it began to tick backwards.")
                    .font(.body(15, weight: .medium))
                    .italic()
                    .foregroundStyle(Theme.Colors.ink)
                    .lineSpacing(6)
            }

            // "To be continued" affordance
            HStack(spacing: Theme.Space.xs) {
                Text("Continue tomorrow")
                    .font(.ui(11, weight: .bold))
                    .foregroundStyle(Theme.Colors.primary)
                Image(systemName: "arrow.right")
                    .font(.system(size: 10, weight: .bold))
                    .foregroundStyle(Theme.Colors.primary)
            }
            .padding(.top, Theme.Space.sm)
        }
        .padding(Theme.Space.xl)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(Theme.Colors.surface)
        .clipShape(RoundedRectangle(cornerRadius: Theme.Radius.md))
        .overlay(
            RoundedRectangle(cornerRadius: Theme.Radius.md)
                .stroke(Theme.Colors.stroke, lineWidth: Theme.Stroke.normal)
        )
        .hardShadow(
            RoundedRectangle(cornerRadius: Theme.Radius.md),
            offset: CGSize(width: 4, height: 5)
        )
    }
}

// MARK: - Page 3: "The House of Clocks"
//
// Mostra a capa real da primeira história (free), título grande, CTA rosa
// destacado. É a CONVERSÃO — não descreve o produto, entrega a primeira
// experiência de leitura literal.

struct OnboardingPage3: View {
    var body: some View {
        VStack(spacing: Theme.Space.xxxl) {
            Spacer(minLength: Theme.Space.xxl)

            // ─── COVER da história ─────────────────────────────────
            FirstStoryCover()
                .padding(.horizontal, Theme.Space.xxl)

            Spacer(minLength: Theme.Space.xxl)

            // ─── COPY ──────────────────────────────────────────────
            VStack(spacing: Theme.Space.md) {
                Text("Your first story\nis waiting")
                    .displayTitle(size: 32)
                    .multilineTextAlignment(.center)
                    .fixedSize(horizontal: false, vertical: true)

                Text("The House of Clocks — free to read, fifteen minutes.")
                    .font(.body(15, weight: .regular))
                    .foregroundStyle(Theme.Colors.textMuted)
                    .multilineTextAlignment(.center)
                    .padding(.horizontal, Theme.Space.xxl)
            }

            Spacer(minLength: Theme.Space.xxxl)
        }
    }
}

/// Cover mockup da House of Clocks. Se a arte real existe no bundle usa
/// ela; senão, placeholder tipográfico com nome da história.
private struct FirstStoryCover: View {
    var body: some View {
        ZStack(alignment: .topLeading) {
            Theme.Colors.bgSepia

            if UIImage(named: "story-house-of-clocks-cover") != nil {
                Image("story-house-of-clocks-cover")
                    .resizable()
                    .aspectRatio(5/4, contentMode: .fill)
            } else {
                // Placeholder tipográfico — melhor que ícone genérico
                // pra este contexto específico (é uma história nomeada).
                VStack(spacing: Theme.Space.sm) {
                    Image(systemName: "clock")
                        .font(.system(size: 44, weight: .light))
                        .foregroundStyle(Theme.Colors.textMuted.opacity(0.6))
                    Text("The House of Clocks")
                        .font(.display(15, weight: .bold))
                        .foregroundStyle(Theme.Colors.textStrong)
                        .multilineTextAlignment(.center)
                }
                .padding()
            }

            // Category badge no topo
            Text("MYSTERY")
                .font(.ui(10, weight: .bold))
                .tracking(1.0)
                .foregroundStyle(Theme.Colors.onInk)
                .padding(.horizontal, Theme.Space.sm)
                .padding(.vertical, 4)
                .background(Capsule().fill(Theme.Colors.inkDeep))
                .padding(Theme.Space.md)
        }
        .aspectRatio(5/4, contentMode: .fit)
        .clipShape(RoundedRectangle(cornerRadius: Theme.Radius.md))
        .overlay(
            RoundedRectangle(cornerRadius: Theme.Radius.md)
                .stroke(Theme.Colors.stroke, lineWidth: Theme.Stroke.thick)
        )
        .hardShadow(
            RoundedRectangle(cornerRadius: Theme.Radius.md),
            offset: CGSize(width: 5, height: 6)
        )
    }
}
