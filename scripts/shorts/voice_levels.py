#!/usr/bin/env python3
"""Nivela as falas de um curta e confere se cada uma cabe no plano.

O TTS devolve cada voz num volume: a narradora sai mais alta que a criança, e
no filme montado uma fala some sob o ambiente enquanto a outra estoura. Aqui
toda fala vai pra -17 LUFS (ganho fixo medido + limitador em -1,5 dBTP, sem
compressão dinâmica), e o relatório mostra, com a duração real de cada fala e
a mesma regra do `assemble`, quanto sobra em cada plano — ou quanto o plano
vai ser esticado congelando o último quadro.

O original do TTS fica em build/voice_orig/. Rodar de novo só reprocessa o que
mudou (fala regerada pelo `voice --force` é reconhecida pelo conteúdo).

    python3 scripts/shorts/voice_levels.py <slug>
    python3 scripts/shorts/voice_levels.py <slug> --report     (só o relatório)
"""

import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TARGET = -17.0
LIMIT = 10 ** (-1.5 / 20)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def loudness(path):
    log = subprocess.run(["ffmpeg", "-hide_banner", "-i", str(path), "-af", "ebur128=framelog=quiet",
                          "-f", "null", "-"], capture_output=True, text=True).stderr
    return float([l for l in log.splitlines() if l.strip().startswith("I:")][-1].split()[1])


def duration(path):
    return float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                                 "-of", "csv=p=0", str(path)], capture_output=True, text=True).stdout)


def level(build):
    voice, orig = build / "voice", build / "voice_orig"
    orig.mkdir(exist_ok=True)
    manifest_path = orig / "normalized.json"
    manifest = json.loads(manifest_path.read_text()) if manifest_path.exists() else {}
    for mp3 in sorted(voice.glob("*.mp3")):
        if manifest.get(mp3.name) == sha(mp3):
            continue                                    # já nivelado
        mp3.replace(orig / mp3.name)                    # TTS novo (ou regerado): vira o original
        gain = TARGET - loudness(orig / mp3.name)
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(orig / mp3.name),
                        "-af", f"volume={gain:.2f}dB,alimiter=limit={LIMIT:.3f}:level=disabled",
                        "-c:a", "libmp3lame", "-b:a", "160k", str(mp3)], check=True)
        manifest[mp3.name] = sha(mp3)
        print(f"  {mp3.name}: {gain:+.1f} dB")
    manifest_path.write_text(json.dumps(manifest, indent=1) + "\n")


def report(film, build):
    """Mesma regra do assemble: 1ª fala em `at`; as seguintes em
    max(at, fim da anterior + 0,35); o plano estica se a última passar de
    duração - 0,6."""
    total_words = total_speech = 0.0
    tight = []
    for shot in film["shots"]:
        cursor, cues = None, []
        for i, line in enumerate(shot.get("lines", [])):
            d = duration(build / "voice" / f"{shot['id']}-{i}.mp3")
            start = line.get("at", 0.5) if cursor is None else max(line.get("at", 0), cursor + 0.35)
            cursor = start + d
            cues.append(f"{line['who']} {start:.1f}–{cursor:.1f}")
            total_words += len(line["text"].split())
            total_speech += d
        if cursor is None:
            continue
        spare = shot["duration"] - 0.6 - cursor
        flag = "  ← ESTICA" if spare < 0 else ("  (justo)" if spare < 0.4 else "")
        print(f"  {shot['id']} {shot['duration']:>2}s  sobra {spare:+.1f}s  {' | '.join(cues)}{flag}")
        if spare < 0:
            tight.append(shot["id"])
    print(f"\n  {total_words:.0f} palavras, {total_speech:.0f}s de fala em "
          f"{sum(s['duration'] for s in film['shots'])}s de planos")
    print("  " + (f"planos que vão esticar: {', '.join(tight)}" if tight else "todas as falas cabem nos planos"))


if __name__ == "__main__":
    slug = sys.argv[1]
    film_dir = ROOT / "shorts" / slug
    film = json.loads((film_dir / "film.json").read_text())
    if "--report" not in sys.argv:
        level(film_dir / "build")
    report(film, film_dir / "build")
