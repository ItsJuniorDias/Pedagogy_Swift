#!/usr/bin/env python3
"""Pós do The Sky Mirror: áudio dos clipes e a música.

Áudio: s02, s03, s07, s14 e s17 vieram com tom, sopro de voz ou cantarolado
(audio_check.py); s15 e s16 com rajadas de vento no volume da narração, bem
no momento da foto. Viram brisa sintetizada; o s03 ganha os passos na água
(que vieram junto com a voz) e o s15 o clique do obturador logo depois de
"He made the picture". O s18 fica com o ronco do jipe gerado.

Música: tema andino original em lá menor, 3/4 — corda dedilhada (charango)
sobre um acorde de sopro. Entra com a chegada ao salar, vira só céu e
estrelas na noite, sobe no s14 (o pai com a câmera nas mãos) e chega ao auge
no s16, a filha sozinha no espelho, sem falas. Resolve em lá maior sob
"The End".

    python3 shorts/the-sky-mirror/post.py
"""

import sys
from pathlib import Path

import numpy as np

FILM = Path(__file__).resolve().parent
sys.path.insert(0, str(FILM.parents[1] / "scripts" / "shorts"))
import post_kit as k  # noqa: E402

snd = k.sound

AMBIENCE = {
    "s02": (lambda d: snd.wind(d, 0.3), -44),
    "s03": (lambda d: snd.wind(d, 0.25) + k.splashes(d, 3.4, 6.8, 0.5, 0.3), -42),
    "s07": (lambda d: snd.wind(d, 0.15, muffled=True), -48),
    "s14": (lambda d: snd.wind(d, 0.2), -46),
    "s15": (lambda d: snd.wind(d, 0.2) + k.click(d, 6.3, 0.35), -44),
    "s16": (lambda d: snd.wind(d, 0.25), -44),
    "s17": (lambda d: snd.wind(d, 0.2), -46),
}

# ─── Música ─────────────────────────────────────────────────────────────────

BPM = 76
BEAT = 60 / BPM
A3, C4, D4, E4, G4 = 57, 60, 62, 64, 67
A4, C5, D5, E5, G5, A5 = 69, 72, 74, 76, 79, 81
AM, C, G = (A3, E4, A4), (C4, G4, C5), (55, 62, G4)
DM, EM = (D4, 65, A4), (52, 59, E4)
AMAJ = (A3, 61, E4, A4)                      # lá maior: o final abre

THEME = [  # 12 compassos de 3 tempos
    (A4, 1), (C5, 1), (D5, 1),   (E5, 2), (D5, 1),   (C5, 1), (A4, 1), (G4, 1),   (A4, 3),
    (C5, 1), (D5, 1), (E5, 1),   (G5, 2), (E5, 1),   (D5, 1), (C5, 1), (D5, 1),   (E5, 3),
    (G5, 1), (E5, 1), (D5, 1),   (C5, 2), (A4, 1),   (G4, 1), (A4, 1), (C5, 1),   (A4, 3),
]
CHORDS = [AM, AM, G, AM, C, G, DM, EM, G, AM, G, AM]


def charango(m):
    return k.pluck(m, 2.2, 1.0, bright=1.15, decay=2.6)


def bass(m):
    return k.pluck(m - 12, 3.0, 0.9, bright=0.7, decay=1.2)


def theme(out, t, bars=range(12), gain=1.0, with_pad=True):
    """Toca os compassos pedidos do tema (melodia + baixo + sopro)."""
    bar_notes, pos = [], 0
    for m, b in THEME:
        bar_notes.append((pos // 3, m, b, pos))
        pos += b
    t0 = t
    for i, bar in enumerate(bars):
        start = t0 + i * 3 * BEAT
        for bar_i, m, b, p in bar_notes:
            if bar_i == bar:
                k.place(out, start + (p - bar * 3) * BEAT, charango(m), gain)
        chord = CHORDS[bar]
        k.place(out, start, bass(chord[0]), gain * 0.8)
        if with_pad:
            k.place(out, start, k.pad(chord, 3 * BEAT + 0.8, 1.0, attack=0.6, release=0.8, air=0.25), gain)
    return t0 + len(bars) * 3 * BEAT


def stars(out, t0, t1, gain=0.5):
    """Noite: notas agudas esparsas, como estrelas acendendo."""
    rng = np.random.default_rng(11)
    t = t0
    while t < t1:
        k.place(out, t, k.pluck(rng.choice([A5, E5 + 12, G5, D5 + 12]), 3.0, 0.6, bright=1.2, decay=1.4), gain)
        t += rng.uniform(1.8, 3.2)


def compose(st, end):
    total = end + k.END_SECONDS
    out = np.zeros(int((total + 4) * k.SR))
    # abertura + chegada (título → s06): duas voltas do tema
    t = theme(out, 1.5)
    theme(out, t, bars=range(12), gain=0.9)
    # noite (s07–s09): sopro parado + estrelas
    night0, night1 = st["s07"], st["s10"]
    k.place(out, night0, k.pad((A3, E4, A4), (night1 - night0) / 2 + 1, 0.9, attack=2.5, release=2.0, air=0.35))
    k.place(out, night0 + (night1 - night0) / 2, k.pad((52, 59, E4), (night1 - night0) / 2 + 1, 0.9,
                                                        attack=2.0, release=2.5, air=0.35))
    stars(out, night0 + 1.0, night1 - 1.5)
    # quatro dias + pôr do sol (s10–s11): o tema volta, 8 compassos
    theme(out, st["s10"], bars=range(8))
    # amanhecer e o pedido (s12–s13): só sopro, C → G → Am
    dawn0 = st["s12"]
    for i, ch in enumerate((C, G, AM)):
        k.place(out, dawn0 + i * 5.5, k.pad(ch, 7.0, 0.8, attack=2.0, release=2.5, air=0.3))
    # s14 (sem falas): o motivo sobe, esperando
    t = st["s14"] + 0.4
    for m in (A4, C5, D5, E5):
        k.place(out, t, charango(m), 1.1)
        t += 1.3
    k.place(out, st["s14"], k.pad(C, st["s15"] - st["s14"] + 1.5, 0.9, attack=1.5, release=1.5, air=0.3))
    # s15: segura no acorde até o clique (6,3 s dentro do plano)
    k.place(out, st["s15"], k.pad(G, 7.5, 0.7, attack=1.0, release=2.0, air=0.3))
    # s16 (sem falas, Elena sozinha no espelho): o auge — compassos 5–8, mais alto;
    # os compassos 9–12 descem pra baixo das falas do s17
    t = theme(out, st["s16"], bars=range(4, 8), gain=1.35)
    theme(out, t, bars=range(8, 12), gain=0.85)
    # final (s18–s19): 9 compassos, terminando em sol no começo do "The End",
    # que resolve em lá maior (VII → I); a volta inteira invadiria o acorde final
    theme(out, st["s18"], bars=range(9), gain=0.85)
    # "The End": lá maior, arpejo e sopro até o fim
    t_end = end + 0.3
    k.place(out, t_end, k.pad(AMAJ, total - t_end, 1.2, attack=0.8, release=3.0, air=0.3))
    for i, m in enumerate((A3, 61, E4, A4, 73, E5)):
        k.place(out, t_end + i * 0.35, k.pluck(m, 5.0, 0.9, bright=1.1, decay=0.9))
    out = out[: int(total * k.SR)]
    fade = np.ones_like(out)
    n = int(2.5 * k.SR)
    fade[-n:] = np.linspace(1, 0, n)
    return out * fade


if __name__ == "__main__":
    for sid, (make, lufs) in AMBIENCE.items():
        k.replace_ambience(FILM, sid, make, lufs)
        print(f"  {sid}: ambiente sintetizado ({lufs} LUFS)")
    st, _, end = k.timeline(FILM)
    level = k.write_music(FILM, compose(st, end))
    print(f"  music.mp3 {end + k.END_SECONDS:.1f}s, {level:.1f} LUFS")
