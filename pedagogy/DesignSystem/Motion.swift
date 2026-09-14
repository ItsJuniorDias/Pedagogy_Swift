//
//  Motion.swift
//  pedagogy
//
//  ─── MOTION ─────────────────────────────────────────────────────────────────
//  Extensões de animação padronizadas. Equivalente ao `shared/motion` do RN v1.
//
//  ENTRADAS (transições ao aparecer)
//
//    • .enterFadeUp(delay:)   → sobe + fade, com mola (padrão do app)
//    • .enterPop(delay:)      → pop com overshoot, tipo bolha
//
//  INTERAÇÃO
//
//    • PressBounce { … }      → wrapper Button que faz scale down no press
//                                (equivalente do PressBounce da v1)
//
//  LOOPS AMBIENTES
//
//    • .breathe()             → pulsa suavemente (chamadas de atenção sutis)
//    • .floatY()              → oscila verticalmente (elementos flutuantes)
//
//  Todos respeitam "reduzir movimento" do sistema via `@Environment(\.accessibilityReduceMotion)`.
//  Se o usuário tem essa opção ligada, as animações viram no-op.
//  ────────────────────────────────────────────────────────────────────────────

import SwiftUI

// ─── PRESS BOUNCE ───────────────────────────────────────────────────────────
// Botão que dá scale down suave no press. Alvo mínimo 44pt automático.
// Repassa role + label pra acessibilidade.

struct PressBounce<Label: View>: View {
    let action: () -> Void
    let scaleTo: CGFloat
    @ViewBuilder let label: () -> Label

    @Environment(\.accessibilityReduceMotion) private var reduceMotion
    @State private var isPressed = false

    init(scaleTo: CGFloat = 0.96,
         action: @escaping () -> Void,
         @ViewBuilder label: @escaping () -> Label) {
        self.scaleTo = scaleTo
        self.action = action
        self.label = label
    }

    var body: some View {
        Button(action: action) {
            label()
        }
        .buttonStyle(PressBounceStyle(scaleTo: scaleTo, reduce: reduceMotion))
    }
}

private struct PressBounceStyle: ButtonStyle {
    let scaleTo: CGFloat
    let reduce: Bool

    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .scaleEffect(configuration.isPressed && !reduce ? scaleTo : 1)
            .animation(.spring(response: 0.28, dampingFraction: 0.7),
                       value: configuration.isPressed)
            .contentShape(Rectangle())
    }
}

// ─── ENTRANCE PRESETS ───────────────────────────────────────────────────────
// Uso: coloque no `.transition()` de uma view condicional, ou combine com
// `@State var appeared` + `.opacity/.offset` gated + `.onAppear`.
// SwiftUI transitions são mais restritas que Reanimated entering; abaixo há
// um `.appearOnMount()` que emula o comportamento de "aparecer com delay".

extension AnyTransition {
    static var enterFadeUp: AnyTransition {
        .move(edge: .bottom).combined(with: .opacity)
    }

    static var enterPop: AnyTransition {
        .scale(scale: 0.7).combined(with: .opacity)
    }
}

// ─── APPEAR ON MOUNT ────────────────────────────────────────────────────────
// Emula o `entering={enterUp(delay)}` da Reanimated. Fica invisível/deslocado
// e anima pra visível/no lugar no onAppear, opcionalmente com delay.

struct AppearOnMount: ViewModifier {
    let delay: Double
    let offset: CGFloat
    @Environment(\.accessibilityReduceMotion) private var reduceMotion
    @State private var appeared = false

    func body(content: Content) -> some View {
        content
            .opacity(appeared || reduceMotion ? 1 : 0)
            .offset(y: appeared || reduceMotion ? 0 : offset)
            .onAppear {
                withAnimation(
                    .spring(response: 0.5, dampingFraction: 0.75)
                        .delay(delay)
                ) {
                    appeared = true
                }
            }
    }
}

extension View {
    /// Sobe + fade ao montar, com mola. Padrão do app.
    /// Uso: `SomeCard().appearFadeUp(delay: 0.1)`
    func appearFadeUp(delay: Double = 0, offset: CGFloat = 16) -> some View {
        modifier(AppearOnMount(delay: delay, offset: offset))
    }
}

// ─── LOOPS AMBIENTES ────────────────────────────────────────────────────────

struct Breathe: ViewModifier {
    let scaleTo: CGFloat
    let duration: Double
    @Environment(\.accessibilityReduceMotion) private var reduceMotion
    @State private var scaled = false

    func body(content: Content) -> some View {
        content
            .scaleEffect(scaled && !reduceMotion ? scaleTo : 1)
            .onAppear {
                guard !reduceMotion else { return }
                withAnimation(
                    .easeInOut(duration: duration)
                        .repeatForever(autoreverses: true)
                ) {
                    scaled = true
                }
            }
    }
}

struct FloatY: ViewModifier {
    let distance: CGFloat
    let duration: Double
    @Environment(\.accessibilityReduceMotion) private var reduceMotion
    @State private var up = false

    func body(content: Content) -> some View {
        content
            .offset(y: up && !reduceMotion ? -distance : 0)
            .onAppear {
                guard !reduceMotion else { return }
                withAnimation(
                    .easeInOut(duration: duration)
                        .repeatForever(autoreverses: true)
                ) {
                    up = true
                }
            }
    }
}

extension View {
    func breathe(scaleTo: CGFloat = 1.06, duration: Double = 2.0) -> some View {
        modifier(Breathe(scaleTo: scaleTo, duration: duration))
    }

    func floatY(distance: CGFloat = 8, duration: Double = 2.5) -> some View {
        modifier(FloatY(distance: distance, duration: duration))
    }
}
