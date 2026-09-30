"""Kit de pós dos curtas de IA: ambiente sintetizado, linha do tempo e música.

Usado pelo shorts/<slug>/post.py de cada filme (o do fox-ai veio antes e tem
a própria cópia). O som vem do kit do curta 2.5D (sound.py: vento, fogo,
passos, envelopes); aqui ficam o que é comum aos filmes novos:

- replace_ambience: troca o áudio de um clipe gerado (que veio com fala,
  música ou cantarolado — ver audio_check.py) por ambiente sintetizado, no
  volume alvo. O clipe original fica em <id>.orig.mp4; rodar de novo parte
  dele. O vídeo é copiado sem recodificar.
- timeline: início de cada plano no filme montado, com a mesma regra do
  `assemble` (cartela de 5 s; falas empurram o plano).
- pluck / pad / drum / chord: instrumentos aditivos simples, vetorizados.
- write_music: grava shorts/<slug>/music.mp3 no mesmo volume integrado da
  música do fox-ai (-20,8 LUFS), que com o MUSIC_VOLUME do assemble deixa
  ~15 dB de folga pras vozes.
"""

import importlib.util
import json
import subprocess
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location(
    "sound", ROOT / "shorts" / "fox-and-the-north-wind" / "blender" / "sound.py")
sound = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(sound)
SR = sound.SR
MUSIC_LUFS = -20.8
TITLE_SECONDS, END_SECONDS = 5.0, 6.0


# ─── Medidas ────────────────────────────────────────────────────────────────

def duration(path):
    return float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                                 "-of", "csv=p=0", str(path)], capture_output=True, text=True).stdout)


def loudness(path):
    log = subprocess.run(["ffmpeg", "-hide_banner", "-i", str(path), "-af", "ebur128=framelog=quiet",
                          "-f", "null", "-"], capture_output=True, text=True).stderr
    return float([l for l in log.splitlines() if l.strip().startswith("I:")][-1].split()[1])


# ─── Ambiente ───────────────────────────────────────────────────────────────

def click(d, t, gain=0.5):
    """Obturador mecânico: dois estalos secos (abre/fecha) a ~60 ms."""
    out = np.zeros(int(d * SR))
    for dt, g in ((0.0, 1.0), (0.06, 0.7)):
        i = int((t + dt) * SR)
        k = min(len(out) - i, int(0.012 * SR))
        if k <= 0:
            continue
        n = sound.RNG.normal(0, 1, k)
        hi = n - sound.lowpass(n, 2500)
        out[i:i + k] += hi * np.exp(-np.arange(k) / (0.0015 * SR)) * g * gain
    return out


def splashes(d, t0, t1, every, gain=0.25):
    """Passos em água rasa: estouro mais agudo e mais longo que passo na neve."""
    ts = np.arange(t0, t1, every)
    events = []
    for t in ts:
        k = int(0.12 * SR)
        n = sound.RNG.normal(0, 1, k)
        band = sound.lowpass(n, 3500) - sound.lowpass(n, 400)
        env = np.exp(-np.arange(k) / (0.035 * SR))
        events.append((t + sound.RNG.uniform(-0.04, 0.04), band * env, gain * sound.RNG.uniform(0.7, 1.0)))
    return sound.place(d, events)


def replace_ambience(film_dir, sid, make, target_lufs):
    """Troca o áudio do clipe por `make(segundos)` no volume `target_lufs`."""
    clips = Path(film_dir) / "build" / "clips"
    clip, orig = clips / f"{sid}.mp4", clips / f"{sid}.orig.mp4"
    if not orig.exists():
        clip.replace(orig)
    seconds = duration(orig)
    wav = clips / f"{sid}.ambience.wav"
    sound.write_wav(wav, make(seconds + 0.5))
    gain = target_lufs - loudness(wav)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(orig), "-i", str(wav),
                    "-map", "0:v", "-map", "1:a", "-af", f"volume={gain:.2f}dB",
                    "-c:v", "copy", "-c:a", "aac", "-b:a", "160k", "-ar", "48000",
                    "-t", f"{seconds:.3f}", str(clip)], check=True)
    wav.unlink()


def set_level(film_dir, sid, target_lufs, fade_out_at=None):
    """Mantém o áudio gerado, só muda o volume (ex.: a tempestade veio mais
    alta que a narração) e, se pedido, some com o fim a partir de
    `fade_out_at` s (um "sting" musical nos últimos segundos)."""
    clips = Path(film_dir) / "build" / "clips"
    clip, orig = clips / f"{sid}.mp4", clips / f"{sid}.orig.mp4"
    if not orig.exists():
        clip.replace(orig)
    seconds = duration(orig)
    gain = target_lufs - loudness(orig)
    af = f"volume={gain:.2f}dB"
    if fade_out_at is not None:
        af += f",afade=t=out:st={fade_out_at}:d=0.5"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(orig), "-map", "0:v", "-map", "0:a",
                    "-af", af, "-c:v", "copy", "-c:a", "aac", "-b:a", "160k", "-ar", "48000",
                    "-t", f"{seconds:.3f}", str(clip)], check=True)


# ─── Linha do tempo ─────────────────────────────────────────────────────────

def timeline(film_dir):
    """({plano: início}, {plano: (início da 1ª fala, fim da última)}, fim dos planos)."""
    film_dir = Path(film_dir)
    film = json.loads((film_dir / "film.json").read_text())
    t, starts, speech = TITLE_SECONDS, {}, {}
    for shot in film["shots"]:
        starts[shot["id"]] = t
        cursor, first, length = None, None, float(shot["duration"])
        for i, line in enumerate(shot.get("lines", [])):
            d = duration(film_dir / "build" / "voice" / f"{shot['id']}-{i}.mp3")
            start = line.get("at", 0.5) if cursor is None else max(line.get("at", 0), cursor + 0.35)
            first = start if first is None else first
            cursor = start + d
        if cursor is not None:
            length = max(length, cursor + 0.6)
            speech[shot["id"]] = (t + first, t + cursor)
        t += length
    return starts, speech, t


# ─── Instrumentos ───────────────────────────────────────────────────────────

def hz(midi):
    return 440 * 2 ** ((midi - 69) / 12)


def pluck(midi, seconds=2.5, vel=1.0, bright=1.0, decay=2.0, body=0.0):
    """Corda dedilhada aditiva: parciais 1/n com decaimento mais rápido nos
    agudos. `bright` sobe os agudos (charango); `body` soma um grave oco (oud)."""
    t = np.arange(int(seconds * SR)) / SR
    f = hz(midi)
    out = np.zeros_like(t)
    for n in range(1, 9):
        if f * n > 9000:
            break
        amp = (1 / n) * (bright ** (n - 1)) * (1.0 if n == 1 else 0.8)
        out += amp * np.sin(2 * np.pi * f * n * t * (1 + 0.0007 * n)) * np.exp(-t * decay * (1 + 0.45 * (n - 1)))
    if body:
        out += body * np.sin(2 * np.pi * f * 0.5 * t) * np.exp(-t * decay * 1.6)
    attack = np.minimum(1, t / 0.003)
    return out * attack * vel * 0.5


def pad(midis, seconds, vel=1.0, attack=1.5, release=2.0, air=0.0):
    """Acorde sustentado e macio (vozes levemente desafinadas entre si).
    `air` soma sopro filtrado, tipo flauta de bambu."""
    n = int(seconds * SR)
    t = np.arange(n) / SR
    out = np.zeros(n)
    for m in midis:
        f = hz(m)
        for det in (-0.12, 0.0, 0.12):
            ff = f * 2 ** (det / 12 / 4)
            out += (np.sin(2 * np.pi * ff * t) + 0.25 * np.sin(2 * np.pi * 2 * ff * t)) / 3
    if air:
        noise = sound.RNG.normal(0, 1, n)
        out += air * (sound.lowpass(noise, 2200) - sound.lowpass(noise, 700)) * 2
    env = np.minimum(1, t / attack) * np.minimum(1, (seconds - t) / release)
    return out * np.clip(env, 0, 1) * vel * 0.12 / max(1, len(midis))


def drum(vel=1.0, low=True):
    """Tambor de moldura (bendir): batida grave com esteira de ruído."""
    t = np.arange(int(0.6 * SR)) / SR
    if low:
        f = 55 + 45 * np.exp(-t * 30)
        tone = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 7)
    else:
        tone = np.sin(2 * np.pi * 180 * t) * np.exp(-t * 25) * 0.5
    n = sound.RNG.normal(0, 1, len(t))
    buzz = (n - sound.lowpass(n, 1500)) * np.exp(-t * 18) * 0.15
    return (tone + buzz) * vel * 0.5


def place(out, t, snd, gain=1.0):
    i = int(t * SR)
    if i >= len(out) or i + len(snd) <= 0:
        return
    k = min(len(snd), len(out) - i)
    out[i:i + k] += snd[:k] * gain


def melody(out, t, notes, beat, make, gain=1.0):
    """Toca [(midi|None, tempos), ...] a partir de `t`; devolve o fim."""
    for m, beats in notes:
        if m is not None:
            place(out, t, make(m), gain)
        t += beats * beat
    return t


def write_music(film_dir, samples):
    """Grava music.mp3 no volume integrado da música do fox-ai."""
    film_dir = Path(film_dir)
    wav = film_dir / "build" / "music.wav"
    samples = samples / (np.abs(samples).max() + 1e-9) * 0.5
    sound.write_wav(wav, samples)
    gain = MUSIC_LUFS - loudness(wav)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(wav), "-af",
                    f"volume={gain:.2f}dB,alimiter=limit=0.89:level=disabled",
                    "-b:a", "160k", str(film_dir / "music.mp3")], check=True)
    wav.unlink()
    return loudness(film_dir / "music.mp3")
