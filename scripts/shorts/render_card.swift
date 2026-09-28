// Renderiza uma cartela (título ou "The End") como PNG, com as fontes do app.
//
// Existe porque o ffmpeg do Homebrew vem sem libfreetype, então sem drawtext.
// AppKit desenha texto com a mesma tipografia do app e sem dependência extra.
//
//   swift render_card.swift <out.png> <w> <h> <title> <subtitle> <display.ttf> <body.ttf> [fundo.png]
//
// Com fundo: a imagem entra escurecida por baixo do texto. Sem fundo: tinta
// chapada (#1A1A1A), a mesma cor de `Theme.Colors.ink`.

import AppKit
import CoreText

let args = CommandLine.arguments
guard args.count >= 8 else {
    FileHandle.standardError.write("uso: render_card.swift out w h title subtitle display.ttf body.ttf [bg]\n".data(using: .utf8)!)
    exit(2)
}
let out = URL(fileURLWithPath: args[1])
let width = CGFloat(Double(args[2])!), height = CGFloat(Double(args[3])!)
let title = args[4], subtitle = args[5]
let background = args.count > 8 ? NSImage(contentsOfFile: args[8]) : nil

func font(_ path: String, size: CGFloat) -> NSFont {
    let url = URL(fileURLWithPath: path) as CFURL
    CTFontManagerRegisterFontsForURL(url, .process, nil)
    guard let descriptors = CTFontManagerCreateFontDescriptorsFromURL(url) as? [CTFontDescriptor],
          let first = descriptors.first else { return .systemFont(ofSize: size) }
    return CTFontCreateWithFontDescriptor(first, size, nil) as NSFont
}

let ink = NSColor(red: 0x1A / 255, green: 0x1A / 255, blue: 0x1A / 255, alpha: 1)
let paper = NSColor(red: 0xFF / 255, green: 0xF9 / 255, blue: 0xF0 / 255, alpha: 1)
let pink = NSColor(red: 0xFF / 255, green: 0x5B / 255, blue: 0x8D / 255, alpha: 1)

let rep = NSBitmapImageRep(bitmapDataPlanes: nil, pixelsWide: Int(width), pixelsHigh: Int(height),
                           bitsPerSample: 8, samplesPerPixel: 4, hasAlpha: true, isPlanar: false,
                           colorSpaceName: .deviceRGB, bytesPerRow: 0, bitsPerPixel: 0)!
NSGraphicsContext.saveGraphicsState()
NSGraphicsContext.current = NSGraphicsContext(bitmapImageRep: rep)

let bounds = NSRect(x: 0, y: 0, width: width, height: height)
ink.setFill()
bounds.fill()

if let background {
    // Aspect fill, centralizado.
    let scale = max(width / background.size.width, height / background.size.height)
    let size = NSSize(width: background.size.width * scale, height: background.size.height * scale)
    background.draw(in: NSRect(x: (width - size.width) / 2, y: (height - size.height) / 2,
                               width: size.width, height: size.height))
    ink.withAlphaComponent(0.62).setFill()
    bounds.fill(using: .sourceOver)
}

let center = NSMutableParagraphStyle()
center.alignment = .center

let titleAttrs: [NSAttributedString.Key: Any] = [
    .font: font(args[6], size: height * 0.11), .foregroundColor: paper, .paragraphStyle: center,
]
let subtitleAttrs: [NSAttributedString.Key: Any] = [
    .font: font(args[7], size: height * 0.035), .foregroundColor: paper.withAlphaComponent(0.8),
    .paragraphStyle: center, .kern: height * 0.004,
]

let titleText = NSAttributedString(string: title, attributes: titleAttrs)
let subtitleText = NSAttributedString(string: subtitle.uppercased(), attributes: subtitleAttrs)
let titleBox = titleText.boundingRect(with: NSSize(width: width * 0.8, height: height),
                                      options: [.usesLineFragmentOrigin])
let gap = height * 0.05
let rule = height * 0.006
let block = titleBox.height + gap + rule + gap + subtitleText.size().height
var y = (height + block) / 2

y -= titleBox.height
titleText.draw(with: NSRect(x: width * 0.1, y: y, width: width * 0.8, height: titleBox.height),
               options: [.usesLineFragmentOrigin])
y -= gap + rule
pink.setFill()
NSRect(x: (width - height * 0.08) / 2, y: y, width: height * 0.08, height: rule).fill()
y -= gap + subtitleText.size().height
subtitleText.draw(in: NSRect(x: 0, y: y, width: width, height: subtitleText.size().height))

NSGraphicsContext.restoreGraphicsState()
try! rep.representation(using: .png, properties: [:])!.write(to: out)
