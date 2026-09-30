#!/usr/bin/env python3
"""Recortes derivados, à mão, das camadas geradas.

nell/walk-clean: a pose de Nell andando veio com um monte de neve e flocos
pintados em volta. No s02 esse monte deslizava junto com ela pela tela.
Aqui a neve sai e fica só Nell, a mala e as botas.

    python3 blender/cleanup_layers.py      (roda depois de `layers.py key`)
"""

from pathlib import Path

import numpy as np
from PIL import Image

LAYERS = Path(__file__).resolve().parent.parent / "build" / "layers"


def keep_big_components(mask, min_share=0.05):
    """Máscara só com as componentes conectadas (4-vizinhança) grandes."""
    h, w = mask.shape
    labels = np.zeros((h, w), dtype=np.int32)
    sizes = [0]
    for y0, x0 in zip(*np.nonzero(mask)):
        if labels[y0, x0]:
            continue
        lab = len(sizes)
        stack, n = [(y0, x0)], 0
        labels[y0, x0] = lab
        while stack:
            y, x = stack.pop()
            n += 1
            for yy, xx in ((y + 1, x), (y - 1, x), (y, x + 1), (y, x - 1)):
                if 0 <= yy < h and 0 <= xx < w and mask[yy, xx] and not labels[yy, xx]:
                    labels[yy, xx] = lab
                    stack.append((yy, xx))
        sizes.append(n)
    sizes = np.array(sizes)
    big = sizes >= max(sizes) * min_share
    big[0] = False
    return big[labels].astype(np.uint8)


def nell_walk_clean():
    src = LAYERS / "nell" / "walk-suitcase.alpha.png"
    im = np.asarray(Image.open(src).convert("RGBA")).copy()
    h, w = im.shape[:2]
    rgb = im[..., :3].astype(int)
    alpha = im[..., 3]

    lo, hi = rgb.min(axis=-1), rgb.max(axis=-1)
    cream = (lo > 175) & (hi - lo < 70)                 # neve / flocos / hálito
    ys, xs = np.mgrid[0:h, 0:w]
    # o gorro tem listras creme: preserva a caixa do gorro
    hat = (xs > 0.45 * w) & (xs < 0.61 * w) & (ys > 0.19 * h) & (ys < 0.31 * h)
    alpha[cream & ~hat] = 0

    soles = int(0.752 * h)                              # abaixo das solas: só monte de neve
    alpha[soles:] = 0
    band = (ys > 0.575 * h) & (ys <= soles)             # altura das pernas e da mala
    alpha[band & ((xs < 0.225 * w) | (xs > 0.685 * w))] = 0

    # Os flocos tinham contorno escuro: sobram anéis soltos no ar. Fica só o
    # que está conectado às maiores regiões (Nell + mala pela alça).
    alpha[:] = alpha * keep_big_components(alpha > 40)

    out = LAYERS / "nell" / "walk-clean.alpha.png"
    Image.fromarray(im).save(out)
    return out, soles / h


def forest_near_shadow():
    """A sombra pintada dos galhos da frente veio grená semitransparente: na
    cena sem tinta azul (s20) virava uma mancha roxa. Vira sombra escura.
    Idempotente."""
    p = LAYERS / "forest" / "near.alpha.png"
    im = np.asarray(Image.open(p).convert("RGBA")).copy()
    rgb = im[..., :3].astype(int)
    a = im[..., 3]
    m = (a > 25) & (a < 230) & (rgb[..., 0] > rgb[..., 1] + 30)
    im[m, :3] = (24, 20, 28)
    Image.fromarray(im).save(p)
    return int(m.sum())


if __name__ == "__main__":
    path, feet = nell_walk_clean()
    print(f"{path.name}: solas a {feet:.1%} da altura da imagem")
    print(f"forest/near: {forest_near_shadow()} px de sombra grená → escura")
