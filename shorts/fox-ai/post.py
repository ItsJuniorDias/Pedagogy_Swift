#!/usr/bin/env python3
"""Pós dos clipes gerados e música do curta, antes do `assemble`.

Áudio: o modelo de vídeo gera um ambiente por clipe, mas em três ele não
obedeceu ao "no speech, no music": o k03 veio com fala, o k05 com melodia e o
k08 com um tom sustentado (cantarolado) por baixo da canção da Nell. Nesses, o
áudio vira ambiente sintetizado com o mesmo kit do curta 2.5D (sound.py).

Lembrança: o k05 começa no quadro-chave azulado, mas o modelo devolve a cor
normal no meio do plano. Aqui o plano inteiro recebe o tom de lembrança (azul,
dessaturado), com o dourado do colar preservado.

Música: a mesma caixinha de música do 2.5D. A canção de Nell começa na
primeira palavra dela no k08, fica sob o k09, baixa no k10 e resolve no acorde
final sob "The End".

O clipe original fica em build/clips/kNN.orig.mp4; rodar de novo parte dele.

    python3 shorts/fox-ai/post.py                 (clipes + música)
    python3 shorts/fox-ai/post.py --preview       (só 4 quadros do k05 graduado)
"""

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import numpy as np

FILM_DIR = Path(__file__).resolve().parent
CLIPS = FILM_DIR / "build" / "clips"
_spec = importlib.util.spec_from_file_location(
    "sound", FILM_DIR.parent / "fox-and-the-north-wind" / "blender" / "sound.py")
sound = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(sound)
SR = sound.SR

# Ambiente sintetizado por plano (s → amostras) e o volume alvo dele (LUFS).
# Os vizinhos gerados pelo modelo ficam entre -25 (fogo) e -48 (patinhas).
AMBIENCE = {
    "k03": (lambda d: sound.fire(d) + sound.wind(d, 0.25, muffled=True), -29.0),
    "k05": (lambda d: sound.wind(d, 0.5, muffled=True), -33.0),
    # a canção cala o vento: some ao longo da fala de Nell (1,0 s → ~8 s)
    "k08": (lambda d: sound.wind(d, 0.9) * sound.env(d, [0, 1.2, 7.5, d], [1.0, 1.0, 0.1, 0.05]), -30.0),
}
MEMORY = {"k05"}


# ─── Vídeo ──────────────────────────────────────────────────────────────────

def probe(path, entries):
    out = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                          f"stream={entries}", "-of", "csv=p=0", str(path)],
                         capture_output=True, text=True, check=True).stdout.strip()
    return out.split(",")


def memory_grade(frame, vignette):
    """Lembrança: azul-prata, dessaturado, pretos levantados. O dourado quente
    (colar) mantém parte da cor, pra ainda brilhar no meio do azul."""
    f = frame.astype(np.float32) / 255
    r, g, b = f[..., 0], f[..., 1], f[..., 2]
    lum = f @ np.array([0.299, 0.587, 0.114], dtype=np.float32)
    mx, mn = f.max(-1), f.min(-1)
    sat = (mx - mn) / np.maximum(mx, 1e-4)
    warm = (r >= g) & (g >= b)
    ratio = g / np.maximum(r, 1e-4)                     # ~0,78 = ouro
    gold = (np.clip((sat - 0.35) / 0.2, 0, 1) * np.clip((mx - 0.5) / 0.2, 0, 1)
            * np.clip(1 - np.abs(ratio - 0.78) / 0.2, 0, 1) * warm)[..., None]
    keep = 0.22 + 0.6 * gold
    out = lum[..., None] + (f - lum[..., None]) * keep
    tint = np.array([0.84, 0.94, 1.14], dtype=np.float32)
    out = out * (tint + (1 - tint) * gold)
    out = out * 0.9 + 0.06 * np.array([0.72, 0.84, 1.0], dtype=np.float32)
    out *= vignette[..., None]
    return (np.clip(out, 0, 1) * 255 + 0.5).astype(np.uint8)


def make_vignette(w, h):
    y, x = np.mgrid[0:h, 0:w].astype(np.float32)
    d = ((x - w / 2) / (w / 2)) ** 2 + ((y - h / 2) / (h / 2)) ** 2
    return (1 - 0.22 * np.clip(d / 2, 0, 1) ** 1.2).astype(np.float32)


def graded_frames(src):
    w, h, rate = probe(src, "width,height,r_frame_rate")
    w, h = int(w), int(h)
    dec = subprocess.Popen(["ffmpeg", "-v", "error", "-i", str(src), "-f", "rawvideo",
                            "-pix_fmt", "rgb24", "-"], stdout=subprocess.PIPE)
    vig = make_vignette(w, h)
    size = w * h * 3
    while True:
        buf = dec.stdout.read(size)
        if len(buf) < size:
            break
        yield w, h, rate, memory_grade(np.frombuffer(buf, np.uint8).reshape(h, w, 3), vig)
    dec.wait()


# ─── Áudio ──────────────────────────────────────────────────────────────────

def loudness(wav):
    log = subprocess.run(["ffmpeg", "-hide_banner", "-i", str(wav), "-af", "ebur128=framelog=quiet",
                          "-f", "null", "-"], capture_output=True, text=True).stderr
    line = [l for l in log.splitlines() if l.strip().startswith("I:")][-1]
    return float(line.split()[1])


def ambience_wav(sid, seconds, out):
    make, target = AMBIENCE[sid]
    sound.write_wav(out, make(seconds + 0.5))
    gain = target - loudness(out)
    return gain


# ─── Clipes ─────────────────────────────────────────────────────────────────

def fix_clip(sid):
    clip = CLIPS / f"{sid}.mp4"
    orig = CLIPS / f"{sid}.orig.mp4"
    if not orig.exists():
        clip.replace(orig)
    seconds = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                                    "-of", "csv=p=0", str(orig)], capture_output=True, text=True).stdout)
    tmp_wav = CLIPS / f"{sid}.ambience.wav"
    audio_in, audio_filter = ["-i", str(orig)], []      # entrada 1: áudio (original ou sintetizado)
    if sid in AMBIENCE:
        gain = ambience_wav(sid, seconds, tmp_wav)
        audio_in = ["-i", str(tmp_wav)]
        audio_filter = ["-af", f"volume={gain:.2f}dB"]
    enc_audio = ["-c:a", "aac", "-b:a", "160k", "-ar", "48000", "-t", f"{seconds:.3f}"]

    if sid in MEMORY:
        frames = graded_frames(orig)
        w, h, rate, first = next(frames)
        enc = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24",
                                "-s", f"{w}x{h}", "-r", rate, "-i", "-", *audio_in,
                                "-map", "0:v", "-map", "1:a", *audio_filter,
                                "-c:v", "libx264", "-crf", "15", "-preset", "slow", "-pix_fmt", "yuv420p",
                                *enc_audio, str(clip)], stdin=subprocess.PIPE)
        enc.stdin.write(first.tobytes())
        for _, _, _, fr in frames:
            enc.stdin.write(fr.tobytes())
        enc.stdin.close()
        if enc.wait():
            sys.exit(f"{sid}: ffmpeg falhou")
    else:
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(orig), *audio_in,
                        "-map", "0:v", "-map", "1:a", *audio_filter,
                        "-c:v", "copy", *enc_audio, str(clip)], check=True)
    tmp_wav.unlink(missing_ok=True)
    print(f"  {sid}: " + ", ".join(x for x in ("tom de lembrança" if sid in MEMORY else "",
                                                "ambiente sintetizado" if sid in AMBIENCE else "") if x))


def preview():
    """4 quadros do k05 graduado lado a lado com o original, pra conferir o tom."""
    from PIL import Image
    src = CLIPS / ("k05.orig.mp4" if (CLIPS / "k05.orig.mp4").exists() else "k05.mp4")
    frames = list(graded_frames(src))
    picks = [frames[int(i * (len(frames) - 1) / 3)] for i in range(4)]
    w, h = picks[0][0], picks[0][1]
    sheet = Image.new("RGB", (w // 2 * 4, h // 2), "white")
    for i, (_, _, _, fr) in enumerate(picks):
        sheet.paste(Image.fromarray(fr).resize((w // 2, h // 2)), (i * w // 2, 0))
    out = FILM_DIR / "build" / "k05-grade-preview.png"
    sheet.save(out)
    print(out)


# ─── Música ─────────────────────────────────────────────────────────────────

def assembled_timeline(film):
    """Início de cada plano no filme montado (mesma regra do assemble)."""
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


def make_music():
    film = json.loads((FILM_DIR / "film.json").read_text())
    starts, end = assembled_timeline(film)
    total = end + 6.0                                   # + cartela final
    k08 = next(s for s in film["shots"] if s["id"] == "k08")
    # os nomes do 2.5D: s16 = Nell canta, s17 = a raposa aceita, s18 = reencontro
    marks = {"s16": starts["k08"], "s17": starts["k09"], "s18": starts["k10"], "end": end}
    song_at = starts["k08"] + k08["lines"][0]["at"]
    wav = FILM_DIR / "build" / "music.wav"
    sound.write_wav(wav, sound.music(total, song_at, marks) * 10 ** (sound.MUSIC_GAIN_DB / 20))
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(wav), "-b:a", "160k",
                    str(FILM_DIR / "music.mp3")], check=True)
    wav.unlink()
    print(f"  music.mp3 {total:.2f}s; canção de Nell em {song_at:.2f}s")


if __name__ == "__main__":
    if "--preview" in sys.argv:
        preview()
        sys.exit()
    for sid in sorted(set(AMBIENCE) | MEMORY):
        fix_clip(sid)
    make_music()
