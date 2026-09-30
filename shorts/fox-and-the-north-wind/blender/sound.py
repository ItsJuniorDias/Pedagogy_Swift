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

# Ganho do fundo em relação às vozes. O assemble mistura o ambiente a 30% e a
# música a 16%; com o nível original a voz ficava só ~7 dB acima do fundo —
# pouco pra uma criança acompanhar. -6 dB leva a ~13 dB de folga.
AMBIENCE_GAIN_DB = -6.0
MUSIC_GAIN_DB = -6.0


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


def env(d, points, values):
    """Curva de volume por pontos (s → ganho), interpolada, com `d` segundos."""
    return np.interp(np.arange(int(d * SR)) / SR, points, values)


def _burst(ms, cutoff, decay_ms):
    k = int(ms / 1000 * SR)
    return lowpass(RNG.normal(0, 1, k), cutoff) * np.exp(-np.arange(k) / (decay_ms / 1000 * SR))


def place(d, events):
    """Soma sons curtos em instantes: events = [(t, amostra, ganho), ...]."""
    out = np.zeros(int(d * SR))
    for t, snd, g in events:
        i = int(t * SR)
        k = min(len(snd), len(out) - i)
        if k > 0:
            out[i:i + k] += snd[:k] * g
    return out


def steps(d, t0, t1, every, gain, cutoff=900):
    """Passos na neve / patinhas: rajadas curtas e abafadas."""
    ts = np.arange(t0, t1, every)
    return place(d, [(t + RNG.uniform(-0.03, 0.03), _burst(40, cutoff, 15), gain * RNG.uniform(0.7, 1.0))
                     for t in ts])


def creak(d, t0, gain=0.35):
    """Rangido de tampa de madeira: ruído em banda média com trêmulo rápido."""
    k = int(0.3 * SR)
    n = RNG.normal(0, 1, k)
    band = lowpass(n, 1200) - lowpass(n, 300)
    tt = np.arange(k) / SR
    snd = band * (0.6 + 0.4 * np.sin(2 * np.pi * 35 * tt)) * np.hanning(k)
    snd /= np.abs(snd).max() + 1e-9
    return place(d, [(t0, snd, gain)])


def pen(d, t0, t1, gain=0.05):
    """Caneta no papel: ruído agudo em pulsos de ~8 Hz."""
    n = int(d * SR)
    x = RNG.normal(0, 1, n)
    hi = x - lowpass(x, 3000)
    hi /= np.abs(hi).max() + 1e-9
    tt = np.arange(n) / SR
    gate = ((tt > t0) & (tt < t1)) * (0.4 + 0.6 * np.abs(np.sin(2 * np.pi * 4 * tt)))
    return hi * gate * gain


def hum(d, gain=0.1):
    """O vento 'humming one long, low note' do s07: um ré grave com harmônicos
    (a fundamental sozinha, a 98 Hz, sumia sob o vento e em alto-falante de celular)."""
    tt = np.arange(int(d * SR)) / SR
    f0 = 147.0
    tone = (np.sin(2 * np.pi * f0 * tt) + 0.6 * np.sin(2 * np.pi * 2 * f0 * tt)
            + 0.3 * np.sin(2 * np.pi * 3 * f0 * tt))
    return gain * tone * smooth_noise(len(tt), 0.3, 0.5, 1.0)


# Ambiente de cada plano (o assemble toca por baixo das vozes a 30%).
# Tempos em segundos dentro do plano; batem com shots.py e com as falas do film.json.
AMBIENCE = {
    "s01": lambda d: wind(d, 0.8),
    "s02": lambda d: wind(d, 0.9) + steps(d, 0.3, d - 2.0, 0.45, 0.25),   # Nell para aos 9 s
    "s03": lambda d: fire(d) + wind(d, 0.25, muffled=True),
    # o vento morre quando a luz vira raposa (~7,3 s) e encontra o do s05 no corte
    "s04": lambda d: wind(d, 1.1) * env(d, [0, 7.3, 11.0, d], [1.0, 1.0, 0.45, 0.45]),
    "s05": lambda d: wind(d, 0.5),
    "s06": lambda d: fire(d) + wind(d, 0.25, muffled=True),
    "s07": lambda d: wind(d, 1.0, muffled=True) + hum(d),
    "s08": lambda d: wind(d, 0.9),
    "s09": lambda d: wind(d, 0.5, muffled=True) + clock(d),
    "s10": lambda d: wind(d, 0.4, muffled=True) + clock(d),
    "s11": lambda d: wind(d, 0.5),
    "s12": lambda d: wind(d, 0.7, muffled=True) + clock(d),
    "s13": lambda d: wind(d, 0.8, muffled=True),
    "s14": lambda d: fire(d) * 0.6 + wind(d, 0.5, muffled=True),
    "s15": lambda d: wind(d, 0.9),
    # a canção cala o vento: -20 dB no fim da fala (8,5 s), quase nada no corte
    "s16": lambda d: wind(d, 0.9) * env(d, [0, 1.8, 8.5, d], [1.0, 1.0, 0.1, 0.05]),
    # continua calmo (antes voltava 9 dB mais alto no corte) + patinhas indo à caixa e embora
    "s17": lambda d: wind(d, 0.045) + steps(d, 0.2, 1.1, 0.18, 0.08, 1500) + steps(d, 3.5, 7.0, 0.18, 0.1, 1500),
    "s18": lambda d: fire(d) * 0.6,                   # o fundo mais alto do filme; a fala é baixinha
    "s19": lambda d: clock(d) + wind(d, 0.1, muffled=True) + pen(d, 1.0, 4.2),
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


def bell(midi, seconds, vel=1.0, decay=2.2):
    f = 440 * 2 ** ((midi - 69) / 12)
    t = np.arange(int(seconds * SR)) / SR
    # parciais levemente inarmônicos: timbre de lâmina de caixinha
    tone = (np.sin(2 * np.pi * f * t) + 0.35 * np.sin(2 * np.pi * f * 2.0 * t) * np.exp(-t * 3)
            + 0.18 * np.sin(2 * np.pi * f * 4.07 * t) * np.exp(-t * 6))
    attack = np.minimum(1, t / 0.004)
    return tone * attack * np.exp(-t * decay) * vel


PASS_BEATS = sum(b for _, b in MELODY) + 2      # uma volta da melodia + respiro


def lullaby_pass(out, t, vel=1.0, bar=0):
    """Uma volta da canção (melodia + baixo) a partir de `t` segundos."""
    beat = 60 / BPM
    pos = 0
    for note, beats in MELODY:
        if note is not None:
            snd = bell(note, 3.0, 0.55 * vel)
            i0 = int((t + pos * beat) * SR)
            out[i0:i0 + len(snd)] += snd[: max(0, len(out) - i0)]
        pos += beats
    for k in range(12):                        # 12 compassos de 3 tempos
        snd = bell(BASS[(bar + k) % len(BASS)], 3.0, 0.22 * vel)
        i0 = int((t + k * 3 * beat) * SR)
        out[i0:i0 + len(snd)] += snd[: max(0, len(out) - i0)]


def music(seconds, song_at, marks):
    """A caixinha de música acompanha a história.

    Até o clímax, a canção de ninar fica baixa sob as falas e se apaga antes
    do s16. No s16 uma volta nova começa na primeira palavra de Nell (`song_at`)
    — é a canção dela, a que Farmor chama de "my mother's song" no s18 — e
    segue mais baixa até resolver na nota grave sob "The End". Nunca recomeça
    sobre a cartela final.

    `marks`: instantes (s) de início de s16, s17, s18 e da cartela final.
    """
    beat = 60 / BPM
    n = int(seconds * SR)
    bed = np.zeros(n + SR * 4)
    t, bar = 3.0, 0                            # 3 s de silêncio no título: o loudnorm não infla a música
    while t < marks["s16"]:
        lullaby_pass(bed, t, bar=bar)
        t += PASS_BEATS * beat
        bar += 12
    song = np.zeros(n + SR * 4)
    lullaby_pass(song, song_at)
    bed, song = bed[:n], song[:n]
    ref = np.abs(bed).max() + 1e-9            # normaliza pela base: a canção fica acima dela, não o contrário
    # base -12 dB sob as falas; some antes do clímax
    g_bed = env(seconds, [0, marks["s16"] - 2.0, marks["s16"] - 0.4, seconds], [0.5, 0.5, 0.0, 0.0])
    # a canção: cheia no s16, sob a narração no s17, baixa no reencontro, some no fim
    g_song = env(seconds,
                 [0, marks["s17"] - 0.5, marks["s17"] + 0.5, marks["s18"], marks["end"], seconds - 2.5, seconds],
                 [2.8, 2.8, 1.0, 0.8, 0.8, 0.8, 0.0])
    out = bed * g_bed[:n] + song * g_song[:n]
    # acorde final sob "The End": ré grave + lá + ré, soando até o fim
    tail = seconds - marks["end"]
    for midi, vel in ((38, 0.5), (50, 0.45), (57, 0.3), (62, 0.35)):
        snd = bell(midi, tail, vel, decay=0.55)   # decaimento lento: dura a cartela toda
        i0 = int((marks["end"] + 0.3) * SR)
        out[i0:i0 + len(snd)] += snd[: max(0, n - i0)] * 0.8
    return out * 0.6 / ref


def assembled_timeline(film):
    """Início de cada plano no filme montado, com a mesma regra do assemble:
    cartela de 5 s; a fala seguinte começa em max(at, fim da anterior + 0,35);
    o plano estica se a última fala passar de duração - 0,6."""
    t, starts = 5.0, {}
    for shot in film["shots"]:
        starts[shot["id"]] = t
        cursor, length = None, float(shot["duration"])
        for i, line in enumerate(shot.get("lines", [])):
            path = FILM_DIR / "build" / "voice" / f"{shot['id']}-{i}.mp3"
            dur = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                                        "-of", "csv=p=0", str(path)], capture_output=True, text=True).stdout)
            start = line.get("at", 0.5) if cursor is None else max(line.get("at", 0), cursor + 0.35)
            cursor = start + dur
        if cursor is not None:
            length = max(length, cursor + 0.6)
        t += length
    return starts, t


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
        # +1 s de sobra: o assemble corta no tamanho do plano
        write_wav(out, AMBIENCE[sid](shot["duration"] + 1) * 10 ** (AMBIENCE_GAIN_DB / 20))
        print("  ambiente", sid)
    starts, end = assembled_timeline(film)
    total = end + 6.0                                   # + cartela final
    s16 = next(x for x in film["shots"] if x["id"] == "s16")
    marks = {"s16": starts["s16"], "s17": starts["s17"], "s18": starts["s18"], "end": end}
    song_at = starts["s16"] + s16["lines"][0]["at"]      # primeira palavra de Nell
    wav = FILM_DIR / "build" / "music.wav"
    write_wav(wav, music(total, song_at, marks) * 10 ** (MUSIC_GAIN_DB / 20))
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(wav), "-b:a", "160k",
                    str(FILM_DIR / "music.mp3")], check=True)
    print("  music.mp3", f"{total:.2f}s; canção de Nell em {song_at:.2f}s")


if __name__ == "__main__":
    main()
