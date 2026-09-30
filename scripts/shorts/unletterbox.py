#!/usr/bin/env python3
"""Tira as tarjas pretas (letterbox) que o gerador de imagem às vezes põe.

O modelo devolve 16:9, mas às vezes com uma faixa preta em cima e/ou embaixo:
a imagem "de cinema" dentro do quadro. Numa folha de referência isso ensina o
keyframe a sair com tarja; num keyframe, a tarja vira parte do vídeo.

Aqui as linhas pretas das bordas saem (com 3 px de folga pro degradê da borda),
e o que sobra é recortado no centro de volta pra proporção original e
redimensionado pro tamanho original. O arquivo original fica ao lado como
<nome>.orig.png; rodar de novo parte dele. Imagem sem tarja não é tocada.

    python3 scripts/shorts/unletterbox.py shorts/<slug>/build/refs/*.png
    python3 scripts/shorts/unletterbox.py shorts/<slug>/build/keyframes/*.png
"""

import sys
from pathlib import Path

import numpy as np
from PIL import Image

DARK = 14          # média de luminância abaixo disso = linha de tarja
MIN_BAR = 6        # tarja mais fina que isso é só sombra de borda
MARGIN = 3


def bars(lum):
    """Quantas linhas pretas no topo e na base."""
    dark = (lum.mean(axis=1) < DARK) & (lum.std(axis=1) < 6)
    top = int(np.argmin(dark)) if not dark.all() else len(dark)
    bottom = int(np.argmin(dark[::-1])) if not dark.all() else len(dark)
    return (top if top >= MIN_BAR else 0), (bottom if bottom >= MIN_BAR else 0)


def fix(path: Path) -> str:
    if path.name.endswith(".orig.png"):
        return "original, ignorado"
    orig = path.with_name(path.stem + ".orig.png")
    src = orig if orig.exists() else path
    im = Image.open(src).convert("RGB")
    w, h = im.size
    lum = np.asarray(im.convert("L")).astype(np.float32)
    top, bottom = bars(lum)
    if not top and not bottom:
        return "sem tarja"
    y0 = top + MARGIN if top else 0
    y1 = h - (bottom + MARGIN if bottom else 0)
    keep_h = y1 - y0
    keep_w = round(keep_h * w / h)                      # mesma proporção do quadro
    x0 = (w - keep_w) // 2
    out = im.crop((x0, y0, x0 + keep_w, y1)).resize((w, h), Image.LANCZOS)
    if not orig.exists():
        path.replace(orig)
    out.save(path)
    return f"tarja {top}px em cima, {bottom}px embaixo → recortado {keep_w}x{keep_h}"


if __name__ == "__main__":
    for arg in sys.argv[1:]:
        p = Path(arg)
        print(f"  {p.parent.name}/{p.name}: {fix(p)}")
