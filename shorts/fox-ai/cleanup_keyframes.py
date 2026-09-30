#!/usr/bin/env python3
"""Retoques à mão nos quadros-chave gerados, antes do vídeo.

Neve dentro de casa: o estilo pedia "drifting snow particles" e os interiores
vieram com flocos flutuando na sala. O modelo de vídeo animaria isso como neve
caindo lá dentro. Aqui os flocos saem: pontos claros, pequenos e isolados
viram a mediana da vizinhança. A janela (neve lá fora é de verdade), os rostos
(brilho dos olhos) e o fogo ficam de fora.

O k03 vira um plano mais fechado recortado do k02 limpo (ver CLOSER).

O original fica em kNN.orig.png; rodar de novo parte sempre do original.

    python3 shorts/fox-ai/cleanup_keyframes.py            (grava)
    python3 shorts/fox-ai/cleanup_keyframes.py --debug    (só marca os flocos em vermelho)
"""

import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter

KEYFRAMES = Path(__file__).resolve().parent / "build" / "keyframes"

# Caixas (x0, y0, x1, y1) em pixels de 1344x768 que não são tocadas.
# Nas personagens só o que tem brilho redondo de verdade: rosto (olhos), mãos,
# manta xadrez, trança, caixa, cadarços. O resto do corpo passa pelo filtro de
# forma (floco é redondo; brilho de borda é comprido).
KEEP = {
    "k02": [(835, 80, 1240, 455),                        # janela
            (765, 300, 865, 420), (985, 260, 1110, 395),  # rostos
            (900, 380, 965, 445), (705, 390, 890, 645),   # mão da Farmor, manta
            (1020, 330, 1110, 470), (715, 595, 825, 670),  # trança, botas
            (420, 425, 605, 545), (415, 585, 550, 655),   # porta do fogão, lenha
            (0, 80, 290, 200), (480, 165, 670, 250)],     # bichinhos na prateleira
    "k06": [(885, 70, 1235, 460),
            (535, 125, 670, 300), (775, 110, 930, 265),
            (510, 300, 640, 405), (830, 200, 940, 390),   # caixa + mãos, trança
            (690, 405, 740, 460), (1000, 405, 1050, 480),  # mãos da Farmor
            (520, 590, 685, 690), (760, 620, 930, 700),   # botas, sapatos
            (990, 450, 1205, 695), (415, 430, 535, 545),  # cadeira, fogo
            (420, 590, 550, 665), (465, 175, 570, 300)],  # lenha, objeto na parede
    "k10": [(830, 65, 1235, 460),
            (650, 245, 790, 375), (835, 285, 950, 395),
            (770, 445, 885, 540), (755, 295, 815, 455),   # caixa, trança
            (835, 610, 945, 695), (680, 630, 820, 685),
            (985, 450, 1200, 695), (415, 430, 535, 545),
            (415, 585, 545, 655),
            (0, 80, 285, 200), (475, 165, 665, 250)],
}

# Plano mais fechado recortado de outro quadro. O k03 gerado veio quase com o
# mesmo enquadramento do k02 (e a manta da Nell trocava de vermelha pra cinza):
# no corte parecia erro. Recortado do k02, é o mesmo momento visto mais perto.
CLOSER = {"k03": ("k02", (448, 218, 1344, 722))}   # 896x504 → 1344x768

MEDIAN = 21          # maior que o maior floco (bokeh de ~14 px)
LIFT = 15            # quanto o floco é mais claro que a vizinhança (0–255)
MAX_AREA = 180       # componentes maiores que isso não são floco
MAX_SAT = 0.38       # flocos são claros e pouco saturados; o fogo não
MAX_SIDE = 16        # floco cabe numa caixa pequena…
MAX_ASPECT = 2.2     # …quase quadrada (brilho de borda é comprido)
MIN_FILL = 0.35      # e é cheio (arco de contorno não)


def components(mask):
    """Rótulos das componentes conectadas (8-vizinhança) e o tamanho de cada."""
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
            for dy in (-1, 0, 1):
                for dx in (-1, 0, 1):
                    yy, xx = y + dy, x + dx
                    if 0 <= yy < h and 0 <= xx < w and mask[yy, xx] and not labels[yy, xx]:
                        labels[yy, xx] = lab
                        stack.append((yy, xx))
        sizes.append(n)
    return labels, np.array(sizes)


def dilate(mask, r):
    img = Image.fromarray(mask.astype(np.uint8) * 255)
    return np.asarray(img.filter(ImageFilter.MaxFilter(2 * r + 1))) > 0


def snow_mask(im, keep):
    rgb = np.asarray(im).astype(np.float32)
    lum = rgb @ np.array([0.299, 0.587, 0.114], dtype=np.float32)
    med = np.asarray(Image.fromarray(lum.astype(np.uint8)).filter(ImageFilter.MedianFilter(MEDIAN)))
    hi, lo = rgb.max(axis=-1), rgb.min(axis=-1)
    sat = (hi - lo) / np.maximum(hi, 1)
    cand = (lum - med > LIFT) & (sat < MAX_SAT)
    for x0, y0, x1, y1 in keep:
        cand[y0:y1, x0:x1] = False
    labels, sizes = components(cand)
    n = len(sizes)
    ys, xs = np.nonzero(labels)
    lab = labels[ys, xs]
    y0 = np.full(n, 1 << 30); y1 = np.zeros(n, int)
    x0 = np.full(n, 1 << 30); x1 = np.zeros(n, int)
    np.minimum.at(y0, lab, ys); np.maximum.at(y1, lab, ys)
    np.minimum.at(x0, lab, xs); np.maximum.at(x1, lab, xs)
    bw, bh = x1 - x0 + 1, y1 - y0 + 1
    long_side = np.maximum(bw, bh)
    aspect = long_side / np.maximum(np.minimum(bw, bh), 1)
    fill = sizes / np.maximum(bw * bh, 1)
    flake = (sizes <= MAX_AREA) & (long_side <= MAX_SIDE) & (aspect <= MAX_ASPECT) & (fill >= MIN_FILL)
    flake[0] = False
    return flake[labels]


def clean(kid, debug=False):
    path = KEYFRAMES / f"{kid}.png"
    orig = KEYFRAMES / f"{kid}.orig.png"
    if not orig.exists():
        orig.write_bytes(path.read_bytes())
    im = Image.open(orig).convert("RGB")
    mask = snow_mask(im, KEEP[kid])
    grown = dilate(mask, 3)                              # o halo mole do floco também
    if debug:
        out = np.asarray(im).copy()
        out[grown] = (255, 0, 0)
        dbg = KEYFRAMES.parent / f"{kid}.snow-debug.png"
        Image.fromarray(out).save(dbg)
        return dbg, int(mask.sum())
    fill = np.asarray(im.filter(ImageFilter.MedianFilter(MEDIAN))).astype(np.float32)
    soft = np.asarray(Image.fromarray(grown.astype(np.uint8) * 255)
                      .filter(ImageFilter.GaussianBlur(1.2))).astype(np.float32)[..., None] / 255
    out = np.asarray(im).astype(np.float32) * (1 - soft) + fill * soft
    Image.fromarray(out.round().astype(np.uint8)).save(path)
    return path, int(mask.sum())


def closer(kid, src, box):
    path = KEYFRAMES / f"{kid}.png"
    orig = KEYFRAMES / f"{kid}.orig.png"
    if not orig.exists():
        orig.write_bytes(path.read_bytes())
    im = Image.open(KEYFRAMES / f"{src}.png").convert("RGB")
    im.crop(box).resize(im.size, Image.LANCZOS).save(path)
    return path


if __name__ == "__main__":
    debug = "--debug" in sys.argv
    for kid in KEEP:
        p, n = clean(kid, debug)
        print(f"{kid}: {n} px de floco → {p.name}")
    if not debug:
        for kid, (src, box) in CLOSER.items():
            print(f"{kid}: recorte do {src} → {closer(kid, src, box).name}")
