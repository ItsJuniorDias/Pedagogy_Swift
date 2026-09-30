#!/usr/bin/env python3
"""Produz um curta-metragem original do Pedagogy a partir de um film.json.

O roteiro vive em `shorts/<slug>/film.json` como dados: personagens, vozes e
uma lista de planos (keyframe, movimento, som ambiente, falas). Este script
leva isso até um .mp4 pronto pro app, em etapas que se retomam sozinhas —
rodar de novo pula o que já existe.

    plan       valida o roteiro e mostra o custo estimado      (grátis)
    refs       folhas de modelo dos personagens e cenários     (pago)
    keyframes  o primeiro quadro de cada plano                 (pago)
    voice      narração e falas                                (pago, centavos)
    clips      vídeo de cada plano a partir do keyframe        (pago, o grosso)
    review     contact sheet HTML pra aprovar antes de seguir  (grátis)
    assemble   monta o filme com ffmpeg                        (grátis)
    publish    copia pro app e atualiza o catálogo             (grátis)

Toda etapa paga mostra a estimativa e para, a menos que receba --yes.

A ordem pensada é refs -> review -> keyframes -> review -> voice -> clips ->
review -> assemble. As duas primeiras revisões são baratas e são elas que
salvam dinheiro: um personagem errado na folha de modelo vira 37 planos
errados no vídeo.

Chave: OPENROUTER_API_KEY no ambiente ou num .env na raiz do repo.

Exemplos:
    python3 scripts/shorts/produce_short.py plan the-paper-whale
    python3 scripts/shorts/produce_short.py refs the-paper-whale --yes
    python3 scripts/shorts/produce_short.py clips the-paper-whale --only s01,s02 --yes
    python3 scripts/shorts/produce_short.py assemble the-paper-whale
"""

from __future__ import annotations

import argparse
import base64
import concurrent.futures
import html
import json
import os
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SHORTS = ROOT / "shorts"
APP_SHORTS = ROOT / "pedagogy" / "Content" / "Shorts"
FONT_DISPLAY = ROOT / "pedagogy" / "Resources" / "Fonts" / "AlfaSlabOne-Regular.ttf"
FONT_BODY = ROOT / "pedagogy" / "Resources" / "Fonts" / "Lora-Medium.ttf"
CARD_RENDERER = Path(__file__).resolve().parent / "render_card.swift"

API = "https://openrouter.ai/api/v1"

DEFAULT_MODELS = {
    "image": "google/gemini-2.5-flash-image",
    "video": "alibaba/wan-3.0",
    "tts": "openai/gpt-4o-mini-tts-2025-12-15",
}
VIDEO_RESOLUTION = "720p"
WIDTH, HEIGHT, FPS = 1280, 720, 24

# Estimativas quando a API de modelos não responde. Só pra ordem de grandeza.
FALLBACK_VIDEO_USD_PER_SECOND = 0.10
IMAGE_USD_EACH = 0.04
TTS_USD_PER_LINE = 0.002

AMBIENT_VOLUME = 0.30   # som gerado pelo modelo de vídeo, por baixo das vozes
MUSIC_VOLUME = 0.16     # music.mp3 opcional na pasta do filme
FADE = 0.6              # segundos de fade nas transições de cena
TITLE_SECONDS = 5.0
END_SECONDS = 6.0


# ─── Film ───────────────────────────────────────────────────────────────────

class Film:
    def __init__(self, slug: str):
        self.dir = SHORTS / slug
        path = self.dir / "film.json"
        if not path.exists():
            sys.exit(f"não achei {path.relative_to(ROOT)}")
        self.data = json.loads(path.read_text())
        self.slug = self.data["id"]
        if self.slug != slug:
            sys.exit(f"id do film.json ({self.slug}) diferente da pasta ({slug})")
        self.models = {**DEFAULT_MODELS, **self.data.get("models", {})}
        self.build = self.dir / "build"
        for sub in ("refs", "keyframes", "clips", "voice", "segments"):
            (self.build / sub).mkdir(parents=True, exist_ok=True)

    @property
    def shots(self) -> list[dict]:
        return self.data["shots"]

    @property
    def characters(self) -> dict:
        return self.data["characters"]

    def ref_path(self, key: str) -> Path:
        return self.build / "refs" / f"{key}.png"

    def keyframe_path(self, shot_id: str) -> Path:
        return self.build / "keyframes" / f"{shot_id}.png"

    def clip_path(self, shot_id: str) -> Path:
        return self.build / "clips" / f"{shot_id}.mp4"

    def job_path(self, shot_id: str) -> Path:
        return self.build / "clips" / f"{shot_id}.job.json"

    def voice_path(self, shot_id: str, index: int) -> Path:
        return self.build / "voice" / f"{shot_id}-{index}.mp3"

    def select(self, only: str | None) -> list[dict]:
        if not only:
            return self.shots
        wanted = {s.strip() for s in only.split(",") if s.strip()}
        unknown = wanted - {s["id"] for s in self.shots}
        if unknown:
            sys.exit(f"planos inexistentes: {', '.join(sorted(unknown))}")
        return [s for s in self.shots if s["id"] in wanted]

    def validate(self) -> list[str]:
        problems = []
        seen = set()
        for shot in self.shots:
            sid = shot["id"]
            if sid in seen:
                problems.append(f"{sid}: id repetido")
            seen.add(sid)
            for key in shot.get("characters", []):
                if key not in self.characters:
                    problems.append(f"{sid}: personagem desconhecido '{key}'")
            for line in shot.get("lines", []):
                if line["who"] not in self.data["voices"]:
                    problems.append(f"{sid}: voz desconhecida '{line['who']}'")
                # ~2,6 palavras/s é o ritmo da narração calma. Passou disso o
                # assemble estica o plano congelando o último quadro — funciona,
                # mas fica visível. Melhor saber antes de pagar pelo vídeo.
                words = len(line["text"].split())
                budget = (shot["duration"] - line.get("at", 0.5) - 0.6) * 2.6
                if words > budget:
                    problems.append(
                        f"{sid}: fala com {words} palavras pra {shot['duration']}s "
                        f"(cabe ~{int(budget)}) — o plano vai ser esticado")
        if self.data.get("posterShot") not in seen:
            problems.append("posterShot não aponta pra um plano existente")
        return problems


# ─── OpenRouter ─────────────────────────────────────────────────────────────

def api_key() -> str:
    key = os.environ.get("OPENROUTER_API_KEY")
    env_file = ROOT / ".env"
    if not key and env_file.exists():
        for line in env_file.read_text().splitlines():
            if line.startswith("OPENROUTER_API_KEY="):
                key = line.split("=", 1)[1].strip().strip('"').strip("'")
    if not key:
        sys.exit("defina OPENROUTER_API_KEY (ambiente ou .env na raiz do repo)")
    return key


def request(method: str, path: str, body: dict | None = None, *, raw: bool = False,
            auth: bool = True, timeout: int = 300):
    headers = {"Content-Type": "application/json"}
    if auth:
        headers["Authorization"] = f"Bearer {api_key()}"
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(f"{API}{path}", data=data, headers=headers, method=method)
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                payload = resp.read()
                return payload if raw else json.loads(payload)
        except urllib.error.HTTPError as err:
            detail = err.read().decode(errors="replace")[:500]
            # 429 e 5xx são passageiros; o resto é erro de verdade no pedido.
            if err.code == 429 or err.code >= 500:
                wait = 10 * (attempt + 1)
                print(f"    HTTP {err.code}, tentando de novo em {wait}s")
                time.sleep(wait)
                continue
            raise RuntimeError(f"HTTP {err.code} em {path}: {detail}") from None
        except (urllib.error.URLError, TimeoutError) as err:
            wait = 10 * (attempt + 1)
            print(f"    rede: {err}, tentando de novo em {wait}s")
            time.sleep(wait)
    raise RuntimeError(f"desisti de {path} depois de 4 tentativas")


def data_url(path: Path) -> str:
    """Imagem como data URL. PNG grande vira JPEG antes, pra caber no pedido."""
    if path.suffix == ".png" and path.stat().st_size > 1_500_000:
        jpg = path.with_suffix(".send.jpg")
        if not jpg.exists() or jpg.stat().st_mtime < path.stat().st_mtime:
            subprocess.run(["sips", "-s", "format", "jpeg", "-s", "formatOptions", "88",
                            str(path), "--out", str(jpg)], check=True, capture_output=True)
        path = jpg
    mime = "image/jpeg" if path.suffix in (".jpg", ".jpeg") else "image/png"
    return f"data:{mime};base64,{base64.b64encode(path.read_bytes()).decode()}"


def video_price_per_second(model: str) -> float:
    try:
        models = request("GET", "/videos/models", auth=False, timeout=30)["data"]
        entry = next(m for m in models if m["id"] == model)
        skus = entry.get("pricing_skus") or {}
        price = skus.get(f"duration_seconds_{VIDEO_RESOLUTION}") or skus.get("duration_seconds")
        if price:
            return float(price)
    except Exception:
        pass
    return FALLBACK_VIDEO_USD_PER_SECOND


class Ledger:
    """Quanto cada coisa custou, segundo o que a API devolveu."""

    def __init__(self, film: Film):
        self.path = film.build / "ledger.json"
        self.entries = json.loads(self.path.read_text()) if self.path.exists() else {}

    def add(self, key: str, cost: float | None):
        if cost is None:
            return
        self.entries[key] = round(self.entries.get(key, 0) + float(cost), 4)
        self.path.write_text(json.dumps(self.entries, indent=2, sort_keys=True))

    @property
    def total(self) -> float:
        return sum(self.entries.values())


def confirm_spend(what: str, usd: float, yes: bool):
    print(f"\n{what}: ~US$ {usd:.2f}")
    if usd == 0:
        print("nada a gerar.")
        sys.exit(0)
    if not yes:
        print("(estimativa — rode de novo com --yes pra gerar)")
        sys.exit(0)


# ─── Stages ─────────────────────────────────────────────────────────────────

def stage_plan(film: Film, args):
    price = video_price_per_second(film.models["video"])
    seconds = sum(s["duration"] for s in film.shots)
    lines = sum(len(s.get("lines", [])) for s in film.shots)
    print(f"{film.data['title']}  ({film.slug})")
    print(f"  {len(film.shots)} planos, {seconds}s de vídeo gerado "
          f"(~{(seconds + TITLE_SECONDS + END_SECONDS) / 60:.1f} min com cartelas)")
    print(f"  modelos: {film.models['image']} | {film.models['video']} {VIDEO_RESOLUTION} | "
          f"{film.models['tts']}\n")

    scene = None
    for s in film.shots:
        if s["scene"] != scene:
            scene = s["scene"]
            print(f"  ── {scene}")
        who = ", ".join(s.get("characters", [])) or "—"
        speech = " / ".join(f"{l['who']}: {l['text']}" for l in s.get("lines", []))
        print(f"  {s['id']} {s['duration']:>2}s  [{who}]  {speech[:90]}")

    refs = len(film.characters)
    cost_refs = refs * IMAGE_USD_EACH
    cost_keys = len(film.shots) * IMAGE_USD_EACH
    cost_voice = lines * TTS_USD_PER_LINE
    cost_video = seconds * price
    print(f"\n  custo estimado da primeira passada:")
    print(f"    refs       {refs:>3} imagens     US$ {cost_refs:6.2f}")
    print(f"    keyframes  {len(film.shots):>3} imagens     US$ {cost_keys:6.2f}")
    print(f"    voice      {lines:>3} falas       US$ {cost_voice:6.2f}")
    print(f"    clips      {seconds:>3}s × {price:.3f}  US$ {cost_video:6.2f}")
    print(f"    total                      US$ {cost_refs + cost_keys + cost_voice + cost_video:6.2f}")
    print("  (refazer planos custa à parte — conte com 20–40% a mais)")

    ledger = Ledger(film)
    if ledger.entries:
        print(f"\n  já gasto neste filme: US$ {ledger.total:.2f}")

    problems = film.validate()
    if problems:
        print("\n  avisos:")
        for p in problems:
            print(f"    • {p}")


def generate_image(film: Film, prompt: str, refs: list[Path], out: Path, ledger_key: str,
                   ledger: Ledger, aspect: str):
    body = {
        "model": film.models["image"],
        "prompt": prompt,
        "n": 1,
        "aspect_ratio": aspect,
        "output_format": "png",
    }
    if refs:
        body["input_references"] = [
            {"type": "image_url", "image_url": {"url": data_url(p)}} for p in refs
        ]
    resp = request("POST", "/images", body)
    item = resp["data"][0]
    out.write_bytes(base64.b64decode(item["b64_json"]))
    ledger.add(ledger_key, (resp.get("usage") or {}).get("cost"))


def stage_refs(film: Film, args):
    todo = [k for k in film.characters if args.force or not film.ref_path(k).exists()]
    if args.only:
        todo = [k for k in todo if k in args.only.split(",")]
    confirm_spend(f"refs: {len(todo)} imagens", len(todo) * IMAGE_USD_EACH, args.yes)
    ledger = Ledger(film)
    for key in todo:
        print(f"  ref {key}")
        prompt = f"{film.data['style']}\n\n{film.characters[key]['refPrompt']}"
        generate_image(film, prompt, [], film.ref_path(key), f"ref:{key}", ledger, "16:9")
    print(f"\nrefs em {film.build.relative_to(ROOT)}/refs — revise com `review` antes dos keyframes")


def keyframe_prompt(film: Film, shot: dict) -> str:
    cast = [film.characters[k]["description"] for k in shot.get("characters", [])]
    parts = [film.data["style"], f"Shot: {shot['keyframe']}"]
    if cast:
        parts.append("Keep these designs exactly as in the reference images: " + "; ".join(cast) + ".")
    parts.append("Cinematic 16:9 film frame. Keep important detail away from the edges.")
    return "\n\n".join(parts)


def stage_keyframes(film: Film, args):
    shots = [s for s in film.select(args.only) if args.force or not film.keyframe_path(s["id"]).exists()]
    missing_refs = {k for s in shots for k in s.get("characters", []) if not film.ref_path(k).exists()}
    if missing_refs:
        sys.exit(f"faltam refs: {', '.join(sorted(missing_refs))} — rode `refs` antes")
    confirm_spend(f"keyframes: {len(shots)} imagens", len(shots) * IMAGE_USD_EACH, args.yes)
    ledger = Ledger(film)

    def one(shot):
        refs = [film.ref_path(k) for k in shot.get("characters", [])]
        generate_image(film, keyframe_prompt(film, shot), refs, film.keyframe_path(shot["id"]),
                       f"keyframe:{shot['id']}", ledger, "16:9")
        return shot["id"]

    with concurrent.futures.ThreadPoolExecutor(max_workers=args.concurrency) as pool:
        for sid in pool.map(one, shots):
            print(f"  keyframe {sid}")


def stage_voice(film: Film, args):
    todo = []
    for shot in film.select(args.only):
        for i, line in enumerate(shot.get("lines", [])):
            if args.force or not film.voice_path(shot["id"], i).exists():
                todo.append((shot, i, line))
    confirm_spend(f"voice: {len(todo)} falas", len(todo) * TTS_USD_PER_LINE, args.yes)
    ledger = Ledger(film)
    for shot, i, line in todo:
        voice = film.data["voices"][line["who"]]
        body = {
            "model": film.models["tts"],
            "input": line["text"],
            "voice": voice["voice"],
            "response_format": "mp3",
        }
        if voice.get("instructions"):
            body["instructions"] = voice["instructions"]
        audio = request("POST", "/audio/speech", body, raw=True)
        film.voice_path(shot["id"], i).write_bytes(audio)
        ledger.add(f"voice:{shot['id']}-{i}", len(line["text"]) * 0.000015)
        print(f"  voice {shot['id']}-{i} ({line['who']}) {probe_duration(film.voice_path(shot['id'], i)):.1f}s")


def clip_prompt(film: Film, shot: dict) -> str:
    cast = [film.characters[k]["description"] for k in shot.get("characters", [])]
    parts = [film.data["motionStyle"], shot["keyframe"], shot["motion"]]
    if cast:
        parts.append("Characters: " + "; ".join(cast) + ".")
    # O áudio do modelo entra só como ambiente. Voz gerada aqui não teria a
    # mesma voz de um plano pro outro — as falas vêm do TTS, por cima.
    parts.append(f"Audio: ambient sound effects only — {shot['sfx']}. No speech, no voices, no music.")
    return " ".join(parts)


def stage_clips(film: Film, args):
    shots = [s for s in film.select(args.only) if args.force or not film.clip_path(s["id"]).exists()]
    missing = [s["id"] for s in shots if not film.keyframe_path(s["id"]).exists()]
    if missing:
        sys.exit(f"faltam keyframes: {', '.join(missing)} — rode `keyframes` antes")
    if args.limit:
        shots = shots[: args.limit]

    # Job já submetido e não baixado não é cobrado de novo: só volta a ser consultado.
    pending_jobs = [s for s in shots if film.job_path(s["id"]).exists() and not args.force]
    new = [s for s in shots if s not in pending_jobs]
    if not shots:
        print("nada a gerar.")
        return
    if new:
        price = video_price_per_second(film.models["video"])
        confirm_spend(f"clips: {len(new)} novos ({sum(s['duration'] for s in new)}s)"
                      + (f" + {len(pending_jobs)} já submetidos" if pending_jobs else ""),
                      sum(s["duration"] for s in new) * price, args.yes)
    else:
        print(f"retomando {len(pending_jobs)} jobs já submetidos (sem custo novo)")
    ledger = Ledger(film)

    def one(shot):
        sid = shot["id"]
        job_file = film.job_path(sid)
        if job_file.exists() and not args.force:
            job_id = json.loads(job_file.read_text())["id"]
        else:
            body = {
                "model": film.models["video"],
                "prompt": clip_prompt(film, shot),
                "duration": shot["duration"],
                "resolution": VIDEO_RESOLUTION,
                "aspect_ratio": "16:9",
                "generate_audio": True,
                "seed": shot.get("seed", 1000 + film.shots.index(shot)),
                "frame_images": [{
                    "type": "image_url",
                    "image_url": {"url": data_url(film.keyframe_path(sid))},
                    "frame_type": "first_frame",
                }],
            }
            job = request("POST", "/videos", body)
            job_id = job["id"]
            job_file.write_text(json.dumps({"id": job_id, "submittedAt": time.time()}))
            print(f"  {sid} submetido ({job_id})")

        while True:
            status = request("GET", f"/videos/{job_id}")
            state = status["status"]
            if state == "completed":
                break
            if state == "failed":
                job_file.unlink(missing_ok=True)
                raise RuntimeError(f"{sid} falhou: {status.get('error')}")
            time.sleep(15)

        video = request("GET", f"/videos/{job_id}/content?index=0", raw=True, timeout=600)
        film.clip_path(sid).write_bytes(video)
        ledger.add(f"clip:{sid}", (status.get("usage") or {}).get("cost"))
        job_file.unlink(missing_ok=True)
        return sid

    failures = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.concurrency) as pool:
        futures = {pool.submit(one, s): s["id"] for s in shots}
        for fut in concurrent.futures.as_completed(futures):
            try:
                print(f"  clip {fut.result()} pronto")
            except Exception as err:
                failures.append(futures[fut])
                print(f"  ✗ {err}")
    print(f"\ngasto até agora neste filme: US$ {ledger.total:.2f}")
    if failures:
        sys.exit(f"falharam: {', '.join(sorted(failures))} — rode de novo com --only")


# ─── Review ─────────────────────────────────────────────────────────────────

def stage_review(film: Film, args):
    out = film.build / "review.html"

    def rel(p: Path) -> str:
        return p.relative_to(film.build).as_posix()

    refs = "".join(
        f'<figure><img src="{rel(film.ref_path(k))}"><figcaption>{k}</figcaption></figure>'
        for k in film.characters if film.ref_path(k).exists())
    rows = []
    for s in film.shots:
        kf, clip = film.keyframe_path(s["id"]), film.clip_path(s["id"])
        media = (f'<video src="{rel(clip)}" controls preload="metadata" poster="{rel(kf)}"></video>' if clip.exists()
                 else f'<img src="{rel(kf)}">' if kf.exists() else '<div class="empty">sem keyframe</div>')
        lines = "".join(f"<p><b>{html.escape(l['who'])}:</b> {html.escape(l['text'])}</p>" for l in s.get("lines", []))
        rows.append(
            f'<section><div class="media">{media}</div><div class="meta">'
            f'<h3>{s["id"]} · {s["scene"]} · {s["duration"]}s</h3>'
            f'<p class="dim">{html.escape(s["keyframe"])}</p><p class="dim">↳ {html.escape(s["motion"])}</p>'
            f'{lines}</div></section>')
    out.write_text(f"""<!doctype html><meta charset="utf-8"><title>{html.escape(film.data['title'])} — review</title>
<style>
body{{font:14px/1.45 -apple-system,sans-serif;background:#1a1a1a;color:#fff9f0;margin:0;padding:24px}}
h1{{font-weight:800}} .refs{{display:flex;gap:12px;flex-wrap:wrap}} .refs img{{height:180px;border-radius:8px}}
figure{{margin:0}} figcaption{{opacity:.6}} section{{display:flex;gap:20px;padding:16px 0;border-top:1px solid #333}}
.media{{flex:0 0 480px}} .media img,.media video{{width:480px;border-radius:8px;display:block}}
.empty{{width:480px;height:270px;background:#2a2a2a;border-radius:8px;display:grid;place-items:center;opacity:.5}}
.dim{{opacity:.6}} h3{{margin:0 0 6px}}
</style><h1>{html.escape(film.data['title'])}</h1><h2>Referências</h2><div class="refs">{refs or '—'}</div>
<h2>Planos</h2>{''.join(rows)}""")
    print(f"abra: open {out}")


# ─── Assemble ───────────────────────────────────────────────────────────────

def probe_duration(path: Path) -> float:
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                          "-of", "csv=p=0", str(path)], capture_output=True, text=True, check=True)
    return float(out.stdout.strip())


def has_audio(path: Path) -> bool:
    out = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "a", "-show_entries",
                          "stream=index", "-of", "csv=p=0", str(path)], capture_output=True, text=True)
    return bool(out.stdout.strip())


def ffmpeg(*args: str):
    cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", *args]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        sys.exit(f"ffmpeg falhou:\n{' '.join(cmd)}\n{result.stderr}")


SEGMENT_ENCODE = ["-c:v", "libx264", "-crf", "14", "-preset", "veryfast", "-pix_fmt", "yuv420p",
                  "-r", str(FPS), "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2"]


def render_card(out: Path, title: str, subtitle: str, background: Path | None):
    args = ["swift", str(CARD_RENDERER), str(out), str(WIDTH), str(HEIGHT), title, subtitle,
            str(FONT_DISPLAY), str(FONT_BODY)]
    if background and background.exists():
        args.append(str(background))
    result = subprocess.run(args, capture_output=True, text=True)
    if result.returncode != 0:
        sys.exit(f"render_card falhou:\n{result.stderr}")


def card_segment(image: Path, seconds: float, out: Path):
    vf = (f"scale={WIDTH}:{HEIGHT},setsar=1,fps={FPS},"
          f"fade=t=in:st=0:d={FADE},fade=t=out:st={seconds - FADE}:d={FADE}")
    ffmpeg("-loop", "1", "-t", str(seconds), "-i", str(image),
           "-f", "lavfi", "-t", str(seconds), "-i", "anullsrc=r=48000:cl=stereo",
           "-vf", vf, "-shortest", *SEGMENT_ENCODE, str(out))


def shot_segment(film: Film, shot: dict, fade_in: bool, fade_out: bool, allow_missing: bool,
                 out: Path) -> tuple[float, list[tuple[float, float, str]]]:
    """Monta um plano: vídeo + ambiente + falas. Devolve duração e as legendas."""
    sid = shot["id"]
    lines = shot.get("lines", [])

    # Posiciona as falas: a primeira em `at`, as seguintes logo depois da anterior.
    cues, cursor = [], None
    for i, line in enumerate(lines):
        path = film.voice_path(sid, i)
        if not path.exists():
            if not allow_missing:
                sys.exit(f"falta voz {path.name} — rode `voice`")
            continue
        start = line.get("at", 0.5) if cursor is None else max(line.get("at", 0), cursor + 0.35)
        dur = probe_duration(path)
        # `subtitle` opcional: legenda diferente do que a voz fala (ex.: canção + tradução)
        cues.append((start, dur, path, line.get("subtitle", line["text"])))
        cursor = start + dur

    length = float(shot["duration"])
    if cues:
        # Fala mais longa que o plano: estica congelando o último quadro em vez de cortar a voz.
        length = max(length, cues[-1][0] + cues[-1][1] + 0.6)

    clip = film.clip_path(sid)
    keyframe = film.keyframe_path(sid)
    if clip.exists():
        video_in = ["-i", str(clip)]
        ambient = has_audio(clip)
    elif allow_missing and keyframe.exists():
        video_in = ["-loop", "1", "-t", str(length), "-i", str(keyframe)]
        ambient = False
    elif allow_missing:
        video_in = ["-f", "lavfi", "-t", str(length), "-i", f"color=c=0x2a2622:s={WIDTH}x{HEIGHT}:r={FPS}"]
        ambient = False
    else:
        sys.exit(f"falta clipe {clip.name} — rode `clips` (ou --allow-missing pra testar a montagem)")

    inputs = list(video_in)
    for _, _, path, _ in cues:
        inputs += ["-i", str(path)]

    v = (f"[0:v]scale={WIDTH}:{HEIGHT}:force_original_aspect_ratio=increase,crop={WIDTH}:{HEIGHT},"
         f"setsar=1,fps={FPS},tpad=stop_mode=clone:stop_duration={length},"
         f"trim=duration={length},setpts=PTS-STARTPTS")
    if fade_in:
        v += f",fade=t=in:st=0:d={FADE}"
    if fade_out:
        v += f",fade=t=out:st={length - FADE}:d={FADE}"
    graph = [v + "[v]"]

    amb = "[0:a]" if ambient else f"anullsrc=r=48000:cl=stereo,atrim=duration={length},"
    graph.append(f"{amb}aresample=48000,volume={AMBIENT_VOLUME},apad,atrim=duration={length}[amb]")
    mix = ["[amb]"]
    for i, (start, _, _, _) in enumerate(cues, start=1):
        ms = int(start * 1000)
        graph.append(f"[{i}:a]aresample=48000,aformat=channel_layouts=stereo,adelay={ms}|{ms}[vo{i}]")
        mix.append(f"[vo{i}]")
    a = f"{''.join(mix)}amix=inputs={len(mix)}:normalize=0:duration=first,atrim=duration={length}"
    if fade_in:
        a += f",afade=t=in:st=0:d={FADE}"
    if fade_out:
        a += f",afade=t=out:st={length - FADE}:d={FADE}"
    graph.append(a + "[a]")

    ffmpeg(*inputs, "-filter_complex", ";".join(graph), "-map", "[v]", "-map", "[a]",
           "-t", str(length), *SEGMENT_ENCODE, str(out))
    return length, [(start, dur, text) for start, dur, _, text in cues]


def srt_time(t: float) -> str:
    ms = int(round(t * 1000))
    return f"{ms // 3600000:02}:{ms // 60000 % 60:02}:{ms // 1000 % 60:02},{ms % 1000:03}"


def stage_assemble(film: Film, args):
    seg_dir = film.build / "segments"
    for old in seg_dir.glob("*"):
        old.unlink()

    poster_src = film.keyframe_path(film.data["posterShot"])
    segments: list[Path] = []
    subtitles: list[tuple[float, float, str]] = []
    clock = 0.0

    print("  cartela de abertura")
    title_png = film.build / "title.png"
    render_card(title_png, film.data["title"], "A Pedagogy Original", poster_src)
    title_seg = seg_dir / "000-title.mp4"
    card_segment(title_png, TITLE_SECONDS, title_seg)
    segments.append(title_seg)
    clock += TITLE_SECONDS

    shots = film.shots
    for i, shot in enumerate(shots):
        fade_in = shot.get("transition") == "fade"
        nxt = shots[i + 1] if i + 1 < len(shots) else None
        fade_out = nxt is None or nxt.get("transition") == "fade"
        out = seg_dir / f"{i + 1:03}-{shot['id']}.mp4"
        length, cues = shot_segment(film, shot, fade_in, fade_out, args.allow_missing, out)
        for start, dur, text in cues:
            subtitles.append((clock + start, clock + start + dur, text))
        print(f"  {shot['id']}  {length:4.1f}s" + ("  (esticado)" if length > shot["duration"] else ""))
        segments.append(out)
        clock += length

    print("  cartela final")
    end_png = film.build / "end.png"
    render_card(end_png, "The End", film.data["title"], None)
    end_seg = seg_dir / "999-end.mp4"
    card_segment(end_png, END_SECONDS, end_seg)
    segments.append(end_seg)
    clock += END_SECONDS

    concat_list = seg_dir / "concat.txt"
    concat_list.write_text("".join(f"file '{p.name}'\n" for p in segments))
    joined = film.build / "joined.mp4"
    ffmpeg("-f", "concat", "-safe", "0", "-i", str(concat_list), "-c", "copy", str(joined))

    srt = film.build / "subtitles.srt"
    srt.write_text("".join(f"{n}\n{srt_time(a)} --> {srt_time(b)}\n{text}\n\n"
                           for n, (a, b, text) in enumerate(subtitles, start=1)))

    # O concat por cópia de segmentos AAC deixa pacotes sobrepostos nas emendas:
    # um decodificador sequencial vai atrasando a voz (~0,65 s no fim de 3 min).
    # aresample=async realinha o áudio pelos timestamps antes da mixagem.
    #
    # Final: HEVC com tag hvc1 (sem ela o AVPlayer não toca HEVC em .mp4),
    # loudnorm em -16 LUFS (alvo de conteúdo pra celular) e legenda como faixa
    # mov_text — o AVPlayerViewController mostra no menu de legendas.
    final = film.build / "final.mp4"
    music = film.dir / "music.mp3"
    # Sem falas (ex.: --allow-missing antes do `voice`) não há legenda: um
    # .srt vazio como entrada derruba o ffmpeg no último passo.
    inputs = ["-i", str(joined)]
    subtitle_args: list[str] = []
    if subtitles:
        inputs += ["-i", str(srt)]
        subtitle_args = ["-map", "1:s", "-c:s", "mov_text", "-metadata:s:s:0", "language=eng"]
    if music.exists():
        music_index = len(inputs) // 2
        inputs += ["-stream_loop", "-1", "-i", str(music)]
        audio = (f"[0:a]aresample=async=1:min_hard_comp=0.01:first_pts=0[j];"
                 f"[{music_index}:a]volume={MUSIC_VOLUME},atrim=duration={clock},"
                 f"afade=t=out:st={clock - 3}:d=3[m];[j][m]amix=inputs=2:normalize=0:duration=first,"
                 f"loudnorm=I=-16:TP=-1.5:LRA=11[a]")
    else:
        audio = "[0:a]aresample=async=1:min_hard_comp=0.01:first_pts=0,loudnorm=I=-16:TP=-1.5:LRA=11[a]"
    ffmpeg(*inputs, "-filter_complex", audio, "-map", "0:v", "-map", "[a]", *subtitle_args,
           "-c:v", "libx265", "-crf", str(args.crf), "-preset", "medium", "-tag:v", "hvc1",
           "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "128k", "-ar", "48000",
           "-metadata", f"title={film.data['title']}", "-movflags", "+faststart", str(final))

    poster = film.build / "poster.jpg"
    if poster_src.exists():
        ffmpeg("-i", str(poster_src), "-vf", f"scale={WIDTH}:{HEIGHT}:force_original_aspect_ratio=increase,"
               f"crop={WIDTH}:{HEIGHT}", "-q:v", "3", str(poster))

    size = final.stat().st_size / 1e6
    print(f"\n{final.relative_to(ROOT)}  {int(clock // 60)}min{int(clock % 60):02}s  {size:.1f} MB")
    print(f"legendas: {len(subtitles)} falas")


# ─── Publish ────────────────────────────────────────────────────────────────

def stage_publish(film: Film, args):
    final, poster = film.build / "final.mp4", film.build / "poster.jpg"
    if not final.exists() or not poster.exists():
        sys.exit("rode `assemble` antes")
    APP_SHORTS.mkdir(parents=True, exist_ok=True)
    catalog_path = APP_SHORTS / "shorts.json"
    existing = json.loads(catalog_path.read_text()) if catalog_path.exists() else []
    # Antes de copiar: um id que já é de um filme da Blender ou clássico
    # teria o vídeo e o pôster dele sobrescritos.
    clash = next((e for e in existing if e["id"] == film.slug and e.get("kind", "original") != "original"), None)
    if clash:
        sys.exit(f"id '{film.slug}' já é de outro filme ({clash.get('sourceURL')}) — renomeie a pasta do filme")
    shutil.copy2(final, APP_SHORTS / f"short-{film.slug}.mp4")
    shutil.copy2(poster, APP_SHORTS / f"short-{film.slug}-poster.jpg")

    catalog_path = APP_SHORTS / "shorts.json"
    catalog = json.loads(catalog_path.read_text()) if catalog_path.exists() else []
    entry = {
        "id": film.slug,
        "kind": "original",
        "title": film.data["title"],
        "logline": film.data["logline"],
        "durationSeconds": int(round(probe_duration(final))),
        "isPremium": film.data.get("isPremium", True),
        "publishedAt": film.data.get("publishedAt"),
    }
    catalog = [e for e in catalog if e["id"] != film.slug] + [entry]
    # Originais primeiro (mais novo antes), depois abertos e clássicos — mesma
    # ordem do scripts/classics/harvest_classics.py.
    order = {"original": 0, "open": 1, "classic": 2}
    catalog.sort(key=lambda e: e.get("publishedAt") or str(e.get("year") or ""), reverse=True)
    catalog.sort(key=lambda e: order.get(e.get("kind", "original"), 9))
    catalog_path.write_text(json.dumps(catalog, indent=2, ensure_ascii=False) + "\n")

    print(f"copiado pra {APP_SHORTS.relative_to(ROOT)}")
    print("agora, com o Xcode fechado: python3 scripts/tag_ondemand_resources.py")


# ─── CLI ────────────────────────────────────────────────────────────────────

STAGES = {
    "plan": stage_plan, "refs": stage_refs, "keyframes": stage_keyframes, "voice": stage_voice,
    "clips": stage_clips, "review": stage_review, "assemble": stage_assemble, "publish": stage_publish,
}


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("stage", choices=STAGES)
    parser.add_argument("slug", help="pasta em shorts/, ex.: the-paper-whale")
    parser.add_argument("--yes", action="store_true", help="autoriza o gasto das etapas pagas")
    parser.add_argument("--only", help="lista de planos (ou refs) separados por vírgula")
    parser.add_argument("--force", action="store_true", help="refaz mesmo o que já existe")
    parser.add_argument("--limit", type=int, help="clips: no máximo N planos nesta rodada")
    parser.add_argument("--concurrency", type=int, default=4, help="pedidos em paralelo (default 4)")
    parser.add_argument("--allow-missing", action="store_true",
                        help="assemble: usa keyframe/placeholder onde faltar clipe ou voz")
    parser.add_argument("--crf", type=int, default=24, help="assemble: qualidade HEVC (default 24)")
    args = parser.parse_args()
    STAGES[args.stage](Film(args.slug), args)


if __name__ == "__main__":
    main()
