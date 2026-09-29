#!/usr/bin/env python3
"""Camadas 2.5D de um curta montado no Blender.

O `produce_short.py` gera um quadro inteiro por plano, pensado pra virar vídeo
por IA. Um curta de recorte de papel precisa de outra coisa: cada cenário em
camadas (céu, fundo, meio, frente) e cada personagem recortado, pra câmera do
Blender passear entre eles com parallax.

As camadas vivem em `film.json → layers`:

    {"id": "house/mid", "prompt": "...", "refs": ["house"], "aspect": "16:9", "alpha": true}

    generate   gera as imagens que faltam                     (pago)
    key        tira o fundo magenta das camadas com alpha     (grátis)
    sheet      folha de contato pra revisar                   (grátis)

O modelo de imagem não devolve transparência. Por isso as camadas com
`alpha: true` são pedidas sobre magenta chapado (#FF00FF) e o `key` troca o
magenta por transparência. Magenta e não branco: a raposa é branca.

Saída: shorts/<slug>/build/layers/<id>.png (cru) e <id>.alpha.png (recortado).

    python3 scripts/shorts/layers.py generate fox-and-the-north-wind --yes
    python3 scripts/shorts/layers.py generate fox-and-the-north-wind --only fox/sit --force --yes
    python3 scripts/shorts/layers.py key fox-and-the-north-wind
"""

from __future__ import annotations

import argparse
import concurrent.futures
import html
import importlib.util
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location("produce_short", HERE / "produce_short.py")
ps = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ps)

MAGENTA = (255, 0, 255)

ALPHA_SUFFIX = (
    "Draw ONLY the elements described above, isolated on a completely flat, solid, "
    "pure magenta (#FF00FF) background that fills everything else. No shadow on the "
    "background, no ground, no floor, no border, no frame, no vignette."
)
OPAQUE_SUFFIX = "Full-bleed background plate that fills the whole frame. No characters."


def layers(film: ps.Film) -> list[dict]:
    return film.data.get("layers", [])


def raw_path(film: ps.Film, layer_id: str) -> Path:
    return film.build / "layers" / f"{layer_id}.png"


def alpha_path(film: ps.Film, layer_id: str) -> Path:
    return film.build / "layers" / f"{layer_id}.alpha.png"


def select(film: ps.Film, only: str | None) -> list[dict]:
    items = layers(film)
    if not only:
        return items
    wanted = [w.strip() for w in only.split(",") if w.strip()]
    # "fox" pega fox/sit, fox/walk...; "fox/sit" pega só ele
    return [l for l in items if any(l["id"] == w or l["id"].startswith(w + "/") for w in wanted)]


def prompt_for(film: ps.Film, layer: dict) -> str:
    parts = [film.data["style"], "Layer for a cut-paper 2.5D animated film.", layer["prompt"]]
    cast = [film.characters[k]["description"] for k in layer.get("refs", []) if k in film.characters]
    if cast:
        parts.append("Keep these designs exactly as in the reference images: " + "; ".join(cast) + ".")
    parts.append(ALPHA_SUFFIX if layer.get("alpha", True) else OPAQUE_SUFFIX)
    return "\n\n".join(parts)


def stage_generate(film: ps.Film, args):
    todo = [l for l in select(film, args.only) if args.force or not raw_path(film, l["id"]).exists()]
    missing = {r for l in todo for r in l.get("refs", []) if not film.ref_path(r).exists()}
    if missing:
        sys.exit(f"faltam refs: {', '.join(sorted(missing))} — rode `produce_short.py refs` antes")
    ps.confirm_spend(f"layers: {len(todo)} imagens", len(todo) * ps.IMAGE_USD_EACH, args.yes)
    ledger = ps.Ledger(film)

    # `data_url` converte PNG grande em .send.jpg na primeira vez. Várias camadas
    # usam a mesma ref; em paralelo, dois `sips` gravando o mesmo arquivo quebram.
    # Converte cada ref uma vez aqui, antes das threads — elas só leem o cache.
    for ref in sorted({r for l in todo for r in l.get("refs", [])}):
        ps.data_url(film.ref_path(ref))

    def one(layer):
        out = raw_path(film, layer["id"])
        out.parent.mkdir(parents=True, exist_ok=True)
        refs = [film.ref_path(r) for r in layer.get("refs", [])]
        ps.generate_image(film, prompt_for(film, layer), refs, out, f"layer:{layer['id']}",
                          ledger, layer.get("aspect", "16:9"))
        return layer["id"]

    with concurrent.futures.ThreadPoolExecutor(max_workers=args.concurrency) as pool:
        for lid in pool.map(one, todo):
            print(f"  layer {lid}")
    print("\nagora: `key` pra recortar o magenta, depois `sheet` pra revisar")


def key_magenta(src: Path, dst: Path):
    """Magenta → transparente, com borda suave e sem franja rosa."""
    try:
        import numpy as np
        from PIL import Image
    except ImportError:
        sys.exit("o `key` precisa de Pillow e numpy: python3 -m pip install pillow numpy")

    rgb = np.asarray(Image.open(src).convert("RGB")).astype(np.float32)
    r, g, b = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    # O modelo não pinta #FF00FF exato: sai um rosa-magenta mais escuro, que
    # varia de imagem pra imagem. A cor de referência é a mediana da moldura
    # de 8px — o fundo ocupa as bordas em toda camada recortável.
    border = np.concatenate([rgb[:8].reshape(-1, 3), rgb[-8:].reshape(-1, 3),
                             rgb[:, :8].reshape(-1, 3), rgb[:, -8:].reshape(-1, 3)])
    # Às vezes o modelo põe faixas pretas de letterbox em cima e embaixo; aí a
    # moldura é metade preta. Só conta a borda que parece magenta.
    br, bgc, bb = border[:, 0], border[:, 1], border[:, 2]
    pinkish = border[(br > 120) & (bb > 60) & (br - bgc > 60) & (bb - bgc > 30)]
    bg = np.median(pinkish if len(pinkish) > 50 else border, axis=0)
    # Distância à cor do fundo, com peso maior no desvio de matiz: sombra e
    # luz no próprio fundo mudam o brilho, não a cor.
    dist = np.sqrt(((rgb - bg) ** 2).sum(axis=-1))
    alpha = np.clip((dist - 45) / (110 - 45), 0, 1)
    # Letterbox: linhas inteiras quase pretas coladas no topo ou na base somem.
    dark_row = rgb.max(axis=-1).mean(axis=1) < 25
    # +3 linhas de margem: a transição preto→magenta deixa um fio que o limiar
    # de cor não pega.
    h = len(dark_row)
    top = next((y for y in range(h) if not dark_row[y]), h)
    bottom = next((y for y in reversed(range(h)) if not dark_row[y]), -1)
    if top > 0:
        alpha[:top + 3] = 0
    if bottom < h - 1:
        alpha[bottom - 2:] = 0
    # Despill: R e B acima de G é o "rosa" que o fundo deixa na borda. Tira
    # esse excesso, proporcional a quanto o pixel ainda é fundo. No desenho
    # opaco quase não age — o estilo não usa roxo nem rosa-choque.
    m = np.clip(np.minimum(r, b) - g, 0, None)
    spill = m * np.clip(1.25 - alpha, 0, 1)
    out = rgb.copy()
    out[..., 0] -= spill
    out[..., 2] -= spill
    out = np.clip(out, 0, 255)
    rgba = np.dstack([out, alpha * 255]).astype(np.uint8)
    Image.fromarray(rgba).save(dst)
    return float(1 - alpha.mean())


def stage_key(film: ps.Film, args):
    for layer in select(film, args.only):
        if not layer.get("alpha", True):
            continue
        src = raw_path(film, layer["id"])
        if not src.exists():
            print(f"  (falta) {layer['id']}")
            continue
        dst = alpha_path(film, layer["id"])
        if dst.exists() and not args.force and dst.stat().st_mtime >= src.stat().st_mtime:
            continue
        cut = key_magenta(src, dst)
        flag = "  ← pouco magenta, confira" if cut < 0.05 else ""
        print(f"  key {layer['id']}: {cut:.0%} removido{flag}")


def stage_sheet(film: ps.Film, args):
    rows = []
    for layer in select(film, args.only):
        img = alpha_path(film, layer["id"]) if layer.get("alpha", True) else raw_path(film, layer["id"])
        if not img.exists():
            img = raw_path(film, layer["id"])
        src = img.relative_to(film.build).as_posix() if img.exists() else ""
        rows.append(
            f'<figure><div class="img">{f"<img src={src!r}>" if src else "falta"}</div>'
            f"<figcaption><b>{html.escape(layer['id'])}</b><br>{html.escape(layer['prompt'])}</figcaption></figure>")
    out = film.build / "layers.html"
    out.write_text(
        "<!doctype html><meta charset=utf-8><title>Camadas</title><style>"
        "body{font:13px system-ui;background:#222;color:#ddd;margin:24px}"
        "main{display:grid;grid-template-columns:repeat(auto-fill,minmax(340px,1fr));gap:18px}"
        ".img{background:repeating-conic-gradient(#555 0 25%,#444 0 50%) 0 0/20px 20px;border-radius:8px;overflow:hidden}"
        "img{width:100%;display:block}figcaption{margin-top:6px;color:#aaa}b{color:#fff}"
        f"</style><h1>{html.escape(film.data['title'])} — camadas</h1><main>{''.join(rows)}</main>")
    print(f"abra {out.relative_to(ps.ROOT)}")


STAGES = {"generate": stage_generate, "key": stage_key, "sheet": stage_sheet}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("stage", choices=STAGES)
    ap.add_argument("slug")
    ap.add_argument("--only", help="ids ou prefixos separados por vírgula (ex.: fox,house/mid)")
    ap.add_argument("--force", action="store_true", help="refaz mesmo se já existe")
    ap.add_argument("--yes", action="store_true", help="confirma o gasto sem perguntar")
    ap.add_argument("--concurrency", type=int, default=4)
    args = ap.parse_args()
    STAGES[args.stage](ps.Film(args.slug), args)


if __name__ == "__main__":
    main()
