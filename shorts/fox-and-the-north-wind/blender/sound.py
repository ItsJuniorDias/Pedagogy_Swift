#!/usr/bin/env python3
"""Som sintetizado do curta: ambiente por plano e a caixinha de música.

Sem biblioteca de efeitos: tudo é gerado aqui, determinístico (seed fixa).

    vento    ruído marrom filtrado, com rajadas lentas
    fogo     ronco grave + estalos esparsos
    relógio  tique-taque seco a cada segundo
    música   caixinha de música: canção de ninar original em ré menor, 3/4

Saída:
    build/ambience/<plano>.wav   (vai por baixo das vozes, como "ambiente")
    music.mp3                    (o assemble do pipeline mistura sozinho)

    python3 blender/sound.py
"""

import json
import subprocess
import wave
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
FILM_DIR = HERE.parent
SR = 48000
RNG = np.random.default_rng(7)


def lowpass(x, cutoff):
    """Passa-baixa de um polo com corte fixo, vetorizado (convolução pela resposta ao impulso)."""
    a = np.exp(-2 * np.pi * cutoff / SR)
    k = int(np.ceil(np.log(1e-4) / np.log(a)))          # cauda até -80 dB
    kernel = (1 - a) * a ** np.arange(k)
    return np.convolve(x, kernel)[: len(x)]


def smooth_noise(n, rate_hz, lo=0.0, hi=1.0):
    """Curva aleatória lenta entre lo e hi (pra rajadas e oscilações)."""
    pts = int(n / SR * rate_hz) + 3
    ctrl = RNG.uniform(lo, hi, pts)
    return np.interp(np.arange(n), np.linspace(0, n, pts), ctrl)


def wind(seconds, strength=1.0, muffled=False, fade_out=False):
    n = int(seconds * SR)
    white = RNG.normal(0, 1, n)
    gust = smooth_noise(n, 0.35, 0.25, 1.0)
    scale = 0.35 if muffled else 1.0
    # rajada = mistura entre um vento grave e um mais aberto (corte fixo, vetorizado)
    dark = lowpass(lowpass(white, 250 * scale), 250 * scale)
    bright = lowpass(lowpass(white, 1150 * scale), 1150 * scale)
    dark /= np.abs(dark).max() + 1e-9
    bright /= np.abs(bright).max() + 1e-9
    body = dark * (1 - gust) + bright * gust
    # assobio: banda estreita que aparece nas rajadas fortes
    whistle = lowpass(white, 1800) - lowpass(white, 1500)
    whistle /= np.abs(whistle).max() + 1e-9
    out = body * (0.6 + 0.8 * gust) + whistle * 0.25 * gust ** 3 * (0 if muffled else 1)
    out *= strength / (np.abs(out).max() + 1e-9) * 0.5
    if fade_out:
        out *= np.linspace(1, 0.08, n) ** 1.5
    return out


def fire(seconds):
    n = int(seconds * SR)
    rumble = lowpass(lowpass(RNG.normal(0, 1, n), 180), 180)
    rumble *= 0.35 / (np.abs(rumble).max() + 1e-9)
    crackle = np.zeros(n)
    for t in RNG.uniform(0, seconds, int(seconds * 6)):
        i = int(t * SR)
        k = min(n - i, int(0.02 * SR))
        burst = RNG.normal(0, 1, k) * np.exp(-np.arange(k) / (0.003 * SR))
        crackle[i:i + k] += burst * RNG.uniform(0.2, 0.9)
    crackle = crackle - lowpass(crackle, 900)
    crackle *= 0.4 / (np.abs(crackle).max() + 1e-9)
    return rumble * smooth_noise(n, 0.8, 0.6, 1.0) + crackle


def clock(seconds):
    n = int(seconds * SR)
    out = np.zeros(n)
    for k in range(int(seconds)):
        i = int((k + 0.3) * SR)
        m = min(n - i, int(0.012 * SR))
        if m <= 0:
            break
        tone = 1900 if k % 2 else 1500
        out[i:i + m] += np.sin(2 * np.pi * tone * np.arange(m) / SR) * np.exp(-np.arange(m) / (0.0025 * SR))
    return out * 0.12


# Ambiente de cada plano (o assemble toca por baixo das vozes a 30%).
AMBIENCE = {
    "s01": lambda d: wind(d, 0.8),
    "s02": lambda d: wind(d, 0.9),
    "s03": lambda d: fire(d) + wind(d, 0.25, muffled=True),
    "s04": lambda d: wind(d, 1.1),
    "s05": lambda d: wind(d, 0.5),
    "s06": lambda d: fire(d) + wind(d, 0.25, muffled=True),
    "s07": lambda d: wind(d, 1.0, muffled=True),
    "s08": lambda d: wind(d, 0.9),
    "s09": lambda d: wind(d, 0.5, muffled=True) + clock(d),
    "s10": lambda d: wind(d, 0.4, muffled=True) + clock(d),
    "s11": lambda d: wind(d, 0.5),
    "s12": lambda d: wind(d, 0.7, muffled=True) + clock(d),
    "s13": lambda d: wind(d, 0.8, muffled=True),
    "s14": lambda d: fire(d) * 0.6 + wind(d, 0.5, muffled=True),
    "s15": lambda d: wind(d, 0.9),
    "s16": lambda d: wind(d, 0.9, fade_out=True),      # o vento amansa durante a canção
    "s17": lambda d: wind(d, 0.12),
    "s18": lambda d: fire(d),
    "s19": lambda d: clock(d) + wind(d, 0.1, muffled=True),
    "s20": lambda d: wind(d, 0.08),
}


# ─── Caixinha de música ─────────────────────────────────────────────────────

# Canção de ninar original, ré menor, 3/4. (nota MIDI, tempos); None = pausa.
D, E, F, G, A, Bb, C5, D5 = 62, 64, 65, 67, 69, 70, 72, 74
MELODY = [
    (A, 1), (D5, 1), (C5, 1),   (A, 2), (G, 1),   (F, 1), (G, 1), (A, 1),   (D, 3),
    (F, 1), (G, 1), (A, 1),     (Bb, 2), (A, 1),  (G, 1), (F, 1), (E, 1),   (F, 3),
    (A, 1), (D5, 1), (C5, 1),   (A, 2), (G, 1),   (F, 1), (E, 1), (G, 1),   (A, 3),
    (G, 1), (F, 1), (E, 1),     (F, 2), (E, 1),   (D, 2), (None, 1),        (D, 3),
]
BASS = [50, 45, 46, 45, 50, 45, 43, 50]   # um por compasso (duas voltas por 8 compassos)
BPM = 66


def bell(midi, seconds, vel=1.0):
    f = 440 * 2 ** ((midi - 69) / 12)
    t = np.arange(int(seconds * SR)) / SR
    # parciais levemente inarmônicos: timbre de lâmina de caixinha
    tone = (np.sin(2 * np.pi * f * t) + 0.35 * np.sin(2 * np.pi * f * 2.0 * t) * np.exp(-t * 3)
            + 0.18 * np.sin(2 * np.pi * f * 4.07 * t) * np.exp(-t * 6))
    attack = np.minimum(1, t / 0.004)
    return tone * attack * np.exp(-t * 2.2) * vel


def music(seconds):
    beat = 60 / BPM
    n = int(seconds * SR)
    out = np.zeros(n + SR * 4)
    t = 1.0
    bar = 0
    while t < seconds:
        pos = 0
        for i, (note, beats) in enumerate(MELODY):
            if note is not None:
                s = bell(note, 3.0, 0.55)
                i0 = int((t + pos * beat) * SR)
                out[i0:i0 + len(s)] += s[: max(0, len(out) - i0)]
            pos += beats
        for k in range(12):                    # 12 compassos de 3 tempos por volta
            s = bell(BASS[(bar + k) % len(BASS)], 3.0, 0.22)
            i0 = int((t + k * 3 * beat) * SR)
            out[i0:i0 + len(s)] += s[: max(0, len(out) - i0)]
        t += pos * beat + 2 * beat
        bar += 12
    out = out[:n]
    fade = int(3 * SR)
    out[-fade:] *= np.linspace(1, 0, fade)
    return out * 0.6 / (np.abs(out).max() + 1e-9)


# ─── Arquivos ───────────────────────────────────────────────────────────────

def write_wav(path, mono):
    path.parent.mkdir(parents=True, exist_ok=True)
    mono = np.clip(mono, -1, 1)
    stereo = np.repeat((mono * 32767).astype(np.int16)[:, None], 2, axis=1)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(stereo.tobytes())


def main():
    film = json.loads((FILM_DIR / "film.json").read_text())
    for shot in film["shots"]:
        sid = shot["id"]
        out = FILM_DIR / "build" / "ambience" / f"{sid}.wav"
        if out.exists():
            continue
        # +1 s de sobra: o assemble corta no tamanho do plano
        write_wav(out, AMBIENCE[sid](shot["duration"] + 1))
        print("  ambiente", sid)
    total = sum(s["duration"] for s in film["shots"]) + 11   # + cartelas
    wav = FILM_DIR / "build" / "music.wav"
    write_wav(wav, music(total))
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(wav), "-b:a", "160k",
                    str(FILM_DIR / "music.mp3")], check=True)
    print("  music.mp3", f"{total}s")


if __name__ == "__main__":
    main()
