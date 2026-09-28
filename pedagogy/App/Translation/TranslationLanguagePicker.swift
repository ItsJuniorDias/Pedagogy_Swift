//
//  TranslationLanguagePicker.swift
//  pedagogy
//
//  Seletor do idioma de leitura: "English (original)" + os idiomas que o
//  framework Translation oferece. Usado no menu do reader e no Perfil — os
//  dois mexem no mesmo `TranslationStore.targetLanguage`.
//

import SwiftUI

struct TranslationLanguagePicker: View {
    @Environment(TranslationStore.self) private var translation

    var body: some View {
        @Bindable var translation = translation

        Picker("Story language", selection: $translation.targetLanguage) {
            Text("English (original)")
                .tag(Locale.Language?.none)

            ForEach(translation.supportedLanguages, id: \.self) { language in
                Text(TranslationStore.displayName(of: language))
                    .tag(Optional(language))
            }
        }
    }
}
