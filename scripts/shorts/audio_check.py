#!/usr/bin/env python3
"""Acha fala, canto ou música no áudio que o modelo de vídeo gera.

O prompt pede "ambient sound effects only — no speech, no music", mas quando
uma boca mexe ou o sfx soa musical o modelo às vezes inventa voz, melodia ou
um cantarolado. Vento, areia, passos e fogo são ruído; voz e música são
tonais: formam linhas estáveis no espectro (harmônicos). Aqui um quadro de
64 ms conta como "tonal" quando tem pelo menos dois picos estreitos
(100–4000 Hz) que persistem por ~80 ms. Muito tempo tonal, ou trechos tonais
longos, marcam o clipe.

Calibrado nos clipes do fox-ai: k03 (fala), k05 (melodia) e k08 (tom
cantarolado) marcam; vento, fogo e passos não.

    python3 scripts/shorts/audio_check.py shorts/<slug>/build/clips/*.mp4
"""

import subprocess
import sys
from pathlib import Path

import numpy as np

SR = 16000
NFFT, HOP = 1024, 256                            # 64 ms, passo de 16 ms
LO, HI = 100, 4000                               # onde moram voz e melodia
PROMINENCE = 12.0                                # dB acima do espectro vizinho
PERSIST = 5                                      # quadros seguidos (~80 ms)
FLAG_SHARE, FLAG_RUN = 0.25, 1.0                 # fox-ai: problemas 74–96%, limpos 0–13%


def load(path):
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-ac", "1", "-ar", str(SR),
                          "-f", "s16le", "-"], capture_output=True).stdout
    return np.frombuffer(raw, np.int16).astype(np.float32) / 32768


def tonal_frames(x):
    """Quadro tonal = pelo menos 2 picos espectrais estreitos que persistem
    (harmônicos de voz ou nota). Ruído (vento, areia, fogo, passos) não
    forma linhas estáveis."""
    n = 1 + max(0, (len(x) - NFFT) // HOP)
    frames = np.lib.stride_tricks.sliding_window_view(x, NFFT)[::HOP][:n] * np.hanning(NFFT)
    db = 20 * np.log10(np.abs(np.fft.rfft(frames, axis=1)) + 1e-9)
    freqs = np.fft.rfftfreq(NFFT, 1 / SR)
    band = (freqs >= LO) & (freqs <= HI)
    k = 15
    padded = np.pad(db, ((0, 0), (k, k)), mode="edge")
    base = np.median(np.lib.stride_tricks.sliding_window_view(padded, 2 * k + 1, axis=1), axis=2)
    local_max = (db >= np.roll(db, 1, axis=1)) & (db >= np.roll(db, -1, axis=1))
    # só descarta o quase-silêncio: um portão relativo à mediana do próprio
    # clipe some com a melodia quando ela toca o clipe inteiro
    loud = db.max(axis=1) > db.max() - 45
    peaks = (db - base > PROMINENCE) & local_max & band & loud[:, None]
    # espalha ±2 bins pra tolerar vibrato e deslize de nota
    spread = peaks.copy()
    for s in (1, 2):
        spread |= np.roll(peaks, s, axis=1) | np.roll(peaks, -s, axis=1)
    persistent = peaks.copy()
    for t in range(1, PERSIST):
        persistent[t:] &= spread[:-t]
        persistent[:t] = False
    return persistent.sum(axis=1) >= 2


def runs(mask):
    out, start = [], None
    for i, v in enumerate(np.append(mask, False)):
        if v and start is None:
            start = i
        elif not v and start is not None:
            out.append((start * HOP / SR, i * HOP / SR))
            start = None
    return out


def check(path):
    x = load(path)
    if len(x) < NFFT:
        return 0.0, 0.0, [], "sem áudio"
    mask = tonal_frames(x)
    segs = [(a, b) for a, b in runs(mask) if b - a >= 0.15]
    share = mask.mean()
    longest = max((b - a for a, b in segs), default=0.0)
    flag = "SUSPEITO" if share > FLAG_SHARE or longest > FLAG_RUN else "ok"
    return share, longest, segs, flag


if __name__ == "__main__":
    for arg in sys.argv[1:]:
        p = Path(arg)
        share, longest, segs, flag = check(p)
        where = ", ".join(f"{a:.1f}–{b:.1f}" for a, b in segs[:6])
        print(f"  {p.stem:10s} tonal {share:5.1%}  maior trecho {longest:4.1f}s  {flag:8s} {where}")
