#!/usr/bin/env python3
"""Pós do The Camel and the Well: áudio dos clipes e a música.

Áudio:
- s18 e s19 vieram com sopros de voz e um zumbido tonal (audio_check.py);
  s03 com um "sting" musical no fim. Viram ambiente sintetizado: brisa do
  fim de tarde, o quarto quieto à luz da lamparina.
- s07 tem o mesmo sting só no último meio segundo: fica o áudio gerado, com
  fade antes dele.
- A tempestade (s09–s13) veio com um rugido bom, mas alto demais: o s11 a
  -8,6 LUFS, acima da própria narração. Fica o rugido, no volume certo; o
  s09, sem falas, mais alto, pra muralha de areia impressionar.

Música: tema original no modo Hijaz em ré, 4/4 — alaúde (oud) dedilhado,
tambor de moldura no passo do camelo e um sopro de ney. Cala na
tempestade (o vento é a trilha), volta quando Farouk guia os três pra casa,
tema inteiro na vila ao pôr do sol e resolve em ré maior sob "The End".

    python3 shorts/the-camel-and-the-well/post.py
"""

import sys
from pathlib import Path

import numpy as np

FILM = Path(__file__).resolve().parent
sys.path.insert(0, str(FILM.parents[1] / "scripts" / "shorts"))
import post_kit as k  # noqa: E402

snd = k.sound

AMBIENCE = {
    "s03": (lambda d: snd.wind(d, 0.12, muffled=True), -50),
    "s18": (lambda d: snd.wind(d, 0.35), -44),
    "s19": (lambda d: snd.wind(d, 0.1, muffled=True) + snd.fire(d) * 0.08, -50),
}
LEVELS = {  # (LUFS, fade no fim)
    "s07": (None, 7.3),
    "s09": (-24, None),
    "s10": (-29, None),
    "s11": (-29, None),
    "s12": (-30, None),
    "s13": (-27, None),
}

# ─── Música ─────────────────────────────────────────────────────────────────

BPM = 90
BEAT = 60 / BPM
D3, D4, EB4, FS4, G4, A4, BB4, C5, D5 = 50, 62, 63, 66, 67, 69, 70, 72, 74
D, CM, GM, EB = (50, 57, 62, 66), (48, 55, 63), (43, 50, 58), (51, 58, 63)
DMAJ = (38, 50, 57, 62, 66)

THEME = [  # 8 compassos de 4 tempos
    [(A4, 1), (BB4, .5), (A4, .5), (G4, 1), (FS4, 1)],
    [(G4, 1), (A4, 1), (FS4, 1), (EB4, .5), (D4, .5)],
    [(D4, 1), (FS4, 1), (G4, 1), (A4, 1)],
    [(BB4, 1.5), (A4, .5), (A4, 2)],
    [(D5, 1), (C5, .5), (BB4, .5), (A4, 1), (G4, 1)],
    [(A4, 1), (BB4, 1), (A4, 1), (G4, .5), (FS4, .5)],
    [(G4, 1), (FS4, 1), (EB4, 1), (FS4, 1)],
    [(D4, 4)],
]
CHORDS = [D, CM, D, GM, GM, D, CM, D]


def oud(m):
    return k.pluck(m, 2.0, 1.0, bright=0.85, decay=2.4, body=0.25)


def ney(chord, seconds, vel=1.0):
    return k.pad(chord, seconds, vel, attack=0.8, release=1.0, air=0.4)


def theme(out, t, bars=range(8), gain=1.0, drum=True, pad=True):
    for i, bar in enumerate(bars):
        start = t + i * 4 * BEAT
        k.melody(out, start, THEME[bar], BEAT, oud, gain)
        root = CHORDS[bar][0]
        k.place(out, start, k.pluck(root - 12 if root > 45 else root, 2.5, 0.8, bright=0.6, decay=1.3, body=0.4), gain * 0.8)
        k.place(out, start + 2 * BEAT, k.pluck(root - 12 if root > 45 else root, 2.0, 0.6, bright=0.6, decay=1.5), gain * 0.6)
        if pad:
            k.place(out, start, ney(CHORDS[bar], 4 * BEAT + 0.6, 0.7), gain)
        if drum:
            gait(out, start, 4 * BEAT, gain)
    return t + len(bars) * 4 * BEAT


def gait(out, t0, seconds, gain=1.0):
    """Passo do camelo no tambor: dum . tek . dum dum tek ."""
    pattern = [(0, True, 1.0), (1, False, 0.6), (2, True, 0.8), (2.5, True, 0.6), (3, False, 0.6)]
    t = t0
    while t < t0 + seconds - 1e-6:
        for pos, low, v in pattern:
            if t + pos * BEAT < t0 + seconds:
                k.place(out, t + pos * BEAT, k.drum(v, low), gain * 0.9)
        t += 4 * BEAT


def compose(st, speech, end):
    total = end + k.END_SECONDS
    out = np.zeros(int((total + 4) * k.SR))
    # vila, o mapa, a partida ao amanhecer (título → s04): duas voltas
    t = theme(out, 1.5, drum=False)
    theme(out, t)
    # a travessia e o poço (s05–s07): uma volta com o passo
    theme(out, st["s05"], gain=1.1)
    # s08: Sidi para — o tambor para, fica um sopro que some
    k.place(out, st["s08"], ney(D, st["s09"] - st["s08"] + 1.0, 0.8))
    # s09 (sem falas): a muralha — ré grave e quinta, crescendo
    k.place(out, st["s09"], k.pad((26, 38, 45, 50), st["s10"] - st["s09"] + 1.5, 1.6, attack=3.5, release=1.5, air=0.2))
    # s10–s13: tempestade, sem música
    # s14–s15: depois da tempestade, sopro baixo e incerto: Sol m → Ré
    k.place(out, st["s14"] + 1.0, ney(GM, st["s15"] - st["s14"] + 1.0, 0.7))
    k.place(out, st["s15"] + 0.5, ney(D, st["s16"] - st["s15"] + 0.5, 0.6))
    # s16: depois de "Take us home. Please." — uma frase do alaúde
    k.melody(out, speech["s16"][1] + 0.4, THEME[2] + THEME[3], BEAT, oud, 0.9)
    # s17: o passo volta, Farouk guiando (compassos 1–4)
    t = theme(out, st["s17"], bars=range(4), gain=0.9)
    # s18: a vila ao pôr do sol — o tema completo (compassos 5–8), mais cheio
    theme(out, max(t, st["s18"]), bars=range(4, 8), gain=1.15)
    # s19–s20: à luz da lamparina, sem tambor, baixo
    theme(out, st["s19"] + 0.5, gain=0.65, drum=False)
    # "The End": ré maior, arpejo do alaúde e um "dum"
    t_end = end + 0.3
    k.place(out, t_end, k.pad(DMAJ, total - t_end, 1.3, attack=0.8, release=3.0, air=0.3))
    for i, m in enumerate((D3, 57, D4, FS4, A4, D5)):
        k.place(out, t_end + i * 0.3, k.pluck(m, 5.0, 0.9, bright=0.9, decay=0.8, body=0.2))
    k.place(out, t_end, k.drum(1.0, True))
    out = out[: int(total * k.SR)]
    fade = np.ones_like(out)
    n = int(2.5 * k.SR)
    fade[-n:] = np.linspace(1, 0, n)
    return out * fade


if __name__ == "__main__":
    for sid, (make, lufs) in AMBIENCE.items():
        k.replace_ambience(FILM, sid, make, lufs)
        print(f"  {sid}: ambiente sintetizado ({lufs} LUFS)")
    for sid, (lufs, fade) in LEVELS.items():
        target = lufs if lufs is not None else k.loudness(FILM / "build" / "clips" / (
            f"{sid}.orig.mp4" if (FILM / "build" / "clips" / f"{sid}.orig.mp4").exists() else f"{sid}.mp4"))
        k.set_level(FILM, sid, target, fade)
        print(f"  {sid}: áudio gerado a {target:.0f} LUFS" + (f", fade em {fade}s" if fade else ""))
    st, speech, end = k.timeline(FILM)
    level = k.write_music(FILM, compose(st, speech, end))
    print(f"  music.mp3 {end + k.END_SECONDS:.1f}s, {level:.1f} LUFS")
