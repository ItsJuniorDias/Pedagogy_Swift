//
//  ParentalGate.swift
//  pedagogy
//
//  ─── PARENTAL GATE ──────────────────────────────────────────────────────────
//  Tela de verificação que precisa ser passada antes de qualquer ação que a
//  Apple restringe na categoria Kids.
//
//  O QUE PRECISA FICAR ATRÁS DO GATE (Guideline 1.3 + o anúncio de set/2019)
//
//    1. Link out do app        → Terms e Privacy no rodapé do paywall
//    2. Solicitar permissões   → o prompt de notificação no onboarding
//    3. Oportunidade de compra → o paywall inteiro
//
//  O item 3 é o que define a arquitetura aqui. A guideline fala em "designated
//  area behind a parental gate": a área designada é o PAYWALL INTEIRO, com o
//  gate na entrada. Por isso o gate não fica no botão de comprar — fica antes
//  do sheet abrir. Consequência boa: os links de Terms/Privacy vivem dentro do
//  paywall, então já nascem atrás do gate e não precisam do seu próprio.
//
//  DESENHO DO DESAFIO
//
//  Uma conta da tabuada, em dígitos ("7 × 8").
//
//  Honestidade sobre o que isso segura: a faixa do app é 9–11 anos, e nessa
//  idade a tabuada já está decorada — uma criança determinada passa. Foi uma
//  escolha de produto consciente: o gate que segurava a criança também fazia
//  o PAI parar pra fazer conta de dois dígitos na hora de assinar, e isso
//  custava venda. Nenhum gate resolve os dois lados; a Apple também não pede
//  que resolva. O que este aqui entrega, e é o que a guideline persegue:
//
//    • impossível passar por toque acidental — é preciso ler e responder
//    • números sorteados a cada apresentação (decorar a tela não ajuda)
//    • resposta nunca visível na tela
//    • 3 tentativas; errou as 3, o desafio inteiro é trocado
//    • nada de data de nascimento — isso seria coletar dado pessoal de menor,
//      justamente o que a 5.1.4 quer evitar
//
//  COMO USAR
//
//      @State private var showThing = false
//
//      SomeButton { showThing = true }
//          .parentalGate(isPresented: $showThing) {
//              // roda só depois de passar
//          }
//
//  O modifier NÃO executa a ação se o usuário cancelar. Cancelar é um caminho
//  de primeira classe: criança que caiu aqui sem querer precisa conseguir sair
//  sem se sentir punida.
//  ────────────────────────────────────────────────────────────────────────────

import SwiftUI

// MARK: - Challenge

/// Um desafio sorteado. `struct` sem estado externo pra ser trivial de testar:
/// `ParentalGateChallenge.random()` e depois compara `answer`.
struct ParentalGateChallenge: Equatable {

    let left: Int
    let right: Int

    var answer: Int { left * right }

    /// Enunciado com dígitos — "33 × 24".
    var prompt: String {
        "\(left) × \(right)"
    }

    /// Sorteia uma conta da tabuada: dois fatores de 2 a 9.
    ///
    /// Fora do sorteio: o 1 e o 10 (multiplicar por eles não é conta, é
    /// copiar o outro número) e os dois fatores iguais (os quadrados são as
    /// linhas mais decoradas da tabuada). Sobram respostas de 6 a 72, ou seja
    /// no máximo dois dígitos — é daí que vem o `maxDigits` do campo.
    static func random() -> ParentalGateChallenge {
        let a = Int.random(in: 2...9)
        var b = Int.random(in: 2...9)
        while b == a { b = Int.random(in: 2...9) }
        return ParentalGateChallenge(left: a, right: b)
    }
}

// MARK: - View

struct ParentalGateView: View {

    /// Chamado quando o desafio é resolvido. O dismiss é responsabilidade do
    /// modifier, não daqui.
    let onPass: () -> Void
    let onCancel: () -> Void

    @State private var challenge = ParentalGateChallenge.random()
    @State private var entry = ""
    @State private var attemptsLeft = 3
    @State private var showError = false
    @FocusState private var isFocused: Bool

    private let maxDigits = 2   // maior resposta possível: 8 × 9 = 72

    var body: some View {
        VStack(spacing: Theme.Space.xl) {

            // ─── HEADER ────────────────────────────────────────────────
            VStack(spacing: Theme.Space.sm) {
                Text("Ask a grown-up")
                    .font(.display(28))
                    .foregroundStyle(Theme.Colors.inkDeep)
                    .multilineTextAlignment(.center)

                Text("Solve this to continue.")
                    .font(.ui(14, weight: .medium))
                    .foregroundStyle(Theme.Colors.textMuted)
                    .multilineTextAlignment(.center)
            }
            .padding(.top, Theme.Space.xxxl)

            // ─── DESAFIO ───────────────────────────────────────────────
            Text(challenge.prompt)
                .font(.display(30))
                .foregroundStyle(Theme.Colors.inkDeep)
                .multilineTextAlignment(.center)
                .minimumScaleFactor(0.6)
                .lineLimit(2)
                .padding(.horizontal, Theme.Space.lg)
                .padding(.vertical, Theme.Space.xl)
                .frame(maxWidth: .infinity)
                .background(
                    RoundedRectangle(cornerRadius: Theme.Radius.lg)
                        .fill(Theme.Colors.bgSepia)
                        .overlay(
                            RoundedRectangle(cornerRadius: Theme.Radius.lg)
                                .stroke(Theme.Colors.stroke, lineWidth: Theme.Stroke.normal)
                        )
                )
                .hardShadow(RoundedRectangle(cornerRadius: Theme.Radius.lg))
                // Sem isso o VoiceOver lê o "×" como "multiplication sign"
                // no meio da conta. "times" soa como uma pergunta de verdade.
                .accessibilityLabel(
                    "What is \(challenge.left) times \(challenge.right)?"
                )

            // ─── CAMPO ─────────────────────────────────────────────────
            VStack(spacing: Theme.Space.sm) {
                TextField("", text: $entry)
                    .keyboardType(.numberPad)
                    .multilineTextAlignment(.center)
                    .font(.display(32))
                    .foregroundStyle(Theme.Colors.inkDeep)
                    .focused($isFocused)
                    .padding(.vertical, Theme.Space.md)
                    .background(
                        RoundedRectangle(cornerRadius: Theme.Radius.md)
                            .fill(Theme.Colors.surface)
                            .overlay(
                                RoundedRectangle(cornerRadius: Theme.Radius.md)
                                    .stroke(
                                        showError ? Theme.Colors.danger : Theme.Colors.stroke,
                                        lineWidth: Theme.Stroke.normal
                                    )
                            )
                    )
                    .accessibilityLabel("Answer")
                    .onChange(of: entry) { _, new in
                        // Só dígitos, e trava o tamanho. numberPad já filtra
                        // no teclado da tela, mas teclado bluetooth e colar
                        // passam por cima.
                        let digits = new.filter(\.isNumber).prefix(maxDigits)
                        if String(digits) != new { entry = String(digits) }
                        if showError { showError = false }
                    }

                // Espaço reservado sempre — sem isso o layout pula quando o
                // erro aparece, e o botão foge do dedo.
                Text(errorText)
                    .font(.ui(12, weight: .medium))
                    .foregroundStyle(Theme.Colors.danger)
                    .opacity(showError ? 1 : 0)
                    .accessibilityHidden(!showError)
            }

            Spacer(minLength: Theme.Space.md)

            // ─── AÇÕES ─────────────────────────────────────────────────
            VStack(spacing: Theme.Space.md) {
                PressBounce(action: submit) {
                    Text("Continue")
                        .font(.ui(16, weight: .semibold))
                        .foregroundStyle(Theme.Colors.onAccent)
                        .frame(maxWidth: .infinity)
                        .padding(.vertical, Theme.Space.md)
                        .background(
                            RoundedRectangle(cornerRadius: Theme.Radius.md)
                                .fill(canSubmit ? Theme.Colors.primary : Theme.Colors.primarySoft)
                                .overlay(
                                    RoundedRectangle(cornerRadius: Theme.Radius.md)
                                        .stroke(Theme.Colors.stroke, lineWidth: Theme.Stroke.thick)
                                )
                        )
                        .hardShadow(
                            RoundedRectangle(cornerRadius: Theme.Radius.md),
                            offset: CGSize(width: 3, height: 4)
                        )
                }
                .disabled(!canSubmit)

                Button {
                    onCancel()
                } label: {
                    Text("Never mind")
                        .font(.ui(13, weight: .medium))
                        .foregroundStyle(Theme.Colors.textMuted)
                        .padding(.vertical, Theme.Space.xs)
                }
                .accessibilityLabel("Cancel and go back")
            }
            .padding(.bottom, Theme.Space.xl)
        }
        .padding(.horizontal, Theme.Space.xl)
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .background(Theme.Colors.bg.ignoresSafeArea())
        .onAppear { isFocused = true }
    }

    // MARK: - Estado derivado

    private var canSubmit: Bool { !entry.isEmpty }

    private var errorText: String {
        attemptsLeft == 1
            ? "Not quite — one more try."
            : "Not quite. Try again."
    }

    // MARK: - Ações

    private func submit() {
        guard let value = Int(entry) else { return }

        if value == challenge.answer {
            onPass()
            return
        }

        attemptsLeft -= 1
        entry = ""

        if attemptsLeft <= 0 {
            // Esgotou: troca o desafio inteiro e reseta. Não fecha a tela —
            // fechar sozinho parece bug. E desafio novo impede resolver por
            // tentativa e erro num alvo fixo.
            challenge = .random()
            attemptsLeft = 3
        }

        withAnimation(.spring(response: 0.3, dampingFraction: 0.6)) {
            showError = true
        }
    }
}

// MARK: - Modifier

extension View {

    /// Apresenta o parental gate e só roda `onPass` se o desafio for resolvido.
    ///
    /// - Parameters:
    ///   - isPresented: binding que abre o gate. Zerado nos dois desfechos.
    ///   - onPass: ação liberada. Roda depois do sheet fechar, pra não brigar
    ///     com outra apresentação (abrir um sheet enquanto outro fecha faz o
    ///     segundo ser engolido silenciosamente no SwiftUI).
    func parentalGate(isPresented: Binding<Bool>,
                      onPass: @escaping () -> Void) -> some View {
        modifier(ParentalGateModifier(isPresented: isPresented, onPass: onPass))
    }
}

extension View {

    /// Versão pra quando a ação depende de QUAL item foi tocado — os dois
    /// links do rodapé do paywall usam o mesmo gate, mas abrem URLs
    /// diferentes. Setar o item abre o gate; cancelar zera o item sozinho,
    /// então não sobra estado pendente pra vazar pro próximo toque.
    func parentalGate<Item: Identifiable>(item: Binding<Item?>,
                                          onPass: @escaping (Item) -> Void) -> some View {
        modifier(ParentalGateItemModifier(item: item, onPass: onPass))
    }
}

private struct ParentalGateModifier: ViewModifier {

    @Binding var isPresented: Bool
    let onPass: () -> Void

    /// Marca que passou, pra disparar `onPass` no `onDismiss` do sheet em vez
    /// de dentro dele. Ver a nota sobre sheets concorrentes acima.
    @State private var didPass = false

    func body(content: Content) -> some View {
        content
            .sheet(isPresented: $isPresented, onDismiss: {
                if didPass {
                    didPass = false
                    onPass()
                }
            }) {
                ParentalGateView(
                    onPass: {
                        didPass = true
                        isPresented = false
                    },
                    onCancel: {
                        didPass = false
                        isPresented = false
                    }
                )
                // Não permite arrastar pra fechar por acidente durante a
                // digitação; sair é pelo "Never mind".
                .interactiveDismissDisabled()
            }
    }
}

private struct ParentalGateItemModifier<Item: Identifiable>: ViewModifier {

    @Binding var item: Item?
    let onPass: (Item) -> Void

    /// Guarda o item aprovado pra rodar `onPass` no `onDismiss` — mesma razão
    /// do modifier acima: disparar de dentro do sheet atropela a próxima
    /// apresentação.
    @State private var passed: Item?

    func body(content: Content) -> some View {
        content
            .sheet(item: $item, onDismiss: {
                if let passed {
                    self.passed = nil
                    onPass(passed)
                }
            }) { _ in
                ParentalGateView(
                    onPass: {
                        passed = item
                        item = nil
                    },
                    onCancel: {
                        passed = nil
                        item = nil
                    }
                )
                .interactiveDismissDisabled()
            }
    }
}
