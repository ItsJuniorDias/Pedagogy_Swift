"""Os 20 planos de The Fox and the North Wind, montados no Blender.

Roda dentro do Blender:

    exec(open(".../shots.py").read())
    build("s02")          # um plano
    build_all()           # todos

Cada plano é uma cena do Blender com o nome do id (s01…s20). A duração vem
do film.json; o que cada plano mostra, do ROTEIRO.md. Posições em metros:
`depth` é a distância até a câmera; `floor` é a altura da base do recorte.
"""

import json
import math

exec(open("/Users/alexandrejunior/Pedagogy_Swift/scripts/shorts/blender_kit.py").read())

FILM = json.load(open(ROOT + "/film.json"))
DUR = {s["id"]: s["duration"] for s in FILM["shots"]}
B = MEMORY_BLUE


def frames(sc):
    return sc.frame_end


def push(sc, dy=1.5, dz=0.0, dx=0.0, start=(0.0, 0.0, 0.0), rot_end=None):
    """Câmera: sai de `start` (deslocamento) e avança `dy` com ease-in-out."""
    cam = sc.camera
    s = (start[0], CAM_Y + start[1], start[2])
    e = (s[0] + dx, s[1] + dy, s[2] + dz)
    key(cam, "location", [(1, s), (frames(sc), e)])
    if rot_end:
        key(cam, "rotation_euler", [(1, tuple(cam.rotation_euler)), (frames(sc), rot_end)])
    for fc in _fcurves(cam):
        for kp in fc.keyframe_points:
            kp.easing = "EASE_IN_OUT"


def walk(ob, x0, x1, f0, f1, bob=0.04):
    """Anda em x de f0 a f1, com um balanço vertical de passo."""
    key(ob, "location", [(f0, (x0, ob.location.y, ob.location.z)),
                         (f1, (x1, ob.location.y, ob.location.z))], interp="LINEAR")
    sway(ob, "location", 2, bob, 0.55)


# ─── Cenários ───────────────────────────────────────────────────────────────

def house(sc, tint=None, snowy=True):
    layer(sc, "house/sky", depth=80, overscan=1.35, z=8, tint=tint)
    layer(sc, "house/far", depth=45, overscan=1.0, z=2.2, tint=tint)
    layer(sc, "house/mid", depth=25, overscan=1.3, z=-2.6, tint=tint)
    layer(sc, "house/near", depth=9, overscan=1.3, z=-0.6, tint=tint)
    if snowy:
        snow(sc, depth=14, count=600)
        snow(sc, depth=30, count=900, size=0.1, name="SnowFar")


def living(sc):
    layer(sc, "living/back", depth=14, overscan=1.15)
    layer(sc, "living/mid", depth=9, overscan=1.15, z=-1.3)
    layer(sc, "living/near", depth=4, overscan=1.3)


def bedroom(sc):
    layer(sc, "bedroom/back", depth=10, overscan=1.15)
    layer(sc, "bedroom/mid", depth=7, overscan=1.1, z=-1.0)
    layer(sc, "bedroom/near", depth=3.5, overscan=1.3, x=-0.3, z=-0.4)


def kitchen(sc, table=True):
    layer(sc, "kitchen/back", depth=10, overscan=1.15)
    if table:
        layer(sc, "kitchen/mid", depth=6, overscan=1.2, z=-1.1)


def forest(sc, tint=None):
    layer(sc, "forest/sky", depth=80, overscan=1.3, z=4, tint=tint)
    layer(sc, "forest/far", depth=40, overscan=1.2, z=-1.0, tint=tint)
    layer(sc, "forest/mid", depth=22, overscan=1.25, z=-0.8, tint=tint)
    layer(sc, "forest/near", depth=7, overscan=1.3, tint=tint)
    snow(sc, depth=12, count=500)


def doorstep(sc):
    layer(sc, "flashback/back", depth=10, overscan=1.12, tint=B)


# ─── Planos ─────────────────────────────────────────────────────────────────

def s01(sc):
    house(sc)
    push(sc, dy=4, dz=-0.3)


def s02(sc):
    house(sc)
    nell = puppet(sc, "nell/walk-suitcase", depth=13, height=3.2, x=-6.0, floor=-4.4)
    walk(nell, -6.0, -0.8, 1, frames(sc) - 24)
    push(sc, dy=1.2)


def s03(sc):
    living(sc)
    puppet(sc, "nell/sit-blanket", depth=8.5, height=3.0, x=-2.3, floor=-2.35)
    puppet(sc, "farmor/sit-stove", depth=8.5, height=3.1, x=2.3, floor=-2.35)
    push(sc, dy=1.5)


def s04(sc):
    forest(sc, tint=B)
    sailor = puppet(sc, "sailor/walk", depth=12, height=3.8, x=-5.0, floor=-3.8, tint=B)
    end = frames(sc)
    walk(sailor, -5.0, 1.2, 1, int(end * 0.75), bob=0.03)
    orb = glow_orb(sc, (-1.5, 12, -1.0), radius=0.18)
    key(orb, "location", [(1, (-1.0, orb.location.y, -1.0)), (int(end * 0.75), (3.6, orb.location.y, -1.6))])
    sway(orb, "location", 2, 0.15, 2.0)
    # a luz vira raposa
    key(orb, "scale", [(int(end * 0.75), (1, 1, 1)), (int(end * 0.82), (0.01, 0.01, 0.01))])
    fox = puppet(sc, "fox/sit", depth=12, height=1.8, x=3.4, floor=-3.4, tint=B)
    pop_in(fox, int(end * 0.78), dur=10)
    push(sc, dy=1.0)


def s05(sc):
    doorstep(sc)
    end = frames(sc)
    for i, (pid, x) in enumerate([("props/coin", -1.3), ("props/bread", 0.0), ("props/feather", 1.3)]):
        ob = layer(sc, pid, depth=9.0, width=1.15, x=x * 1.2, z=-2.2, tint=B)
        pop_in(ob, 12 + i * int(end / 3.4))
    tracks(sc, (3.8, 9.3, -2.55), (1.8, 9.4, -2.5), n=6, size=0.09, tint=B)
    push(sc, dy=0.8)


def s06(sc):
    living(sc)
    puppet(sc, "nell/sit-blanket", depth=8.5, height=3.0, x=-2.0, floor=-2.35)
    puppet(sc, "farmor/sit-stove", depth=8.5, height=3.1, x=2.0, floor=-2.35)
    push(sc, dy=1.0, start=(0, 3.0, -0.3))


def s07(sc):
    bedroom(sc)
    nell = puppet(sc, "nell/nightgown-window", depth=8.3, height=3.2, x=2.6, floor=-2.4)
    walk(nell, 2.6, 0.2, 1, 72, bob=0.02)
    push(sc, dy=1.2)


def s08(sc):
    house(sc)
    # pegadas na faixa de neve da frente da casa, vindo da floresta até a porta
    tracks(sc, (-1.5, 23.4, -5.08), (4.1, 23.4, -5.08), n=12, size=0.11)
    push(sc, dy=6.0, dx=2.2, dz=-3.3, start=(0, 5.0, -0.5))


def s09(sc):
    kitchen(sc, table=False)
    puppet(sc, "farmor/coffee", depth=7, height=3.6, x=-0.9, floor=-2.3)
    push(sc, dy=0.8)


def s10(sc):
    kitchen(sc)
    end = frames(sc)
    closed = layer(sc, "props/box-closed", depth=5.7, width=1.2, x=-1.75, z=-1.15)
    opened = layer(sc, "props/box-open", depth=5.7, width=1.2, x=-1.75, z=-1.15)
    visible(closed, [(1, True), (int(end * 0.55), False)])
    visible(opened, [(1, False), (int(end * 0.55), True)])
    push(sc, dy=1.6, dz=-0.35)


def s11(sc):
    doorstep(sc)
    end = frames(sc)
    cut = int(end * 0.62)
    astrid = puppet(sc, "youngfarmor/necklace", depth=9, height=3.4, x=-1.9, floor=-2.8, tint=B)
    sit = puppet(sc, "fox/sit", depth=9.2, height=1.9, x=1.5, floor=-2.8, tint=B)
    trot = puppet(sc, "fox/trot", depth=9.2, height=1.7, x=1.5, floor=-2.8, tint=B)
    visible(sit, [(1, True), (int(end * 0.35), False)])
    visible(trot, [(1, False), (int(end * 0.35), True)])
    key(trot, "location", [(int(end * 0.35), (1.5, trot.location.y, trot.location.z)),
                           (cut, (5.0, trot.location.y, trot.location.z))], interp="LINEAR")
    # corte seco pro pratinho vazio onde ficava o anel
    dark = layer(sc, "flashback/back", depth=5, overscan=1.2, tint=(0.18, 0.24, 0.42), name="s11_dark")
    dish = layer(sc, "props/ring-dish", depth=4.9, width=1.3, z=-0.3, tint=B)
    for ob in (dark, dish):
        visible(ob, [(1, False), (cut, True)])
    for ob in (astrid,):
        visible(ob, [(1, True), (cut, False)])
    push(sc, dy=0.6)


def s12(sc):
    kitchen(sc, table=False)
    puppet(sc, "nell/sit-blanket", depth=7.5, height=2.8, x=-2.1, floor=-2.2)
    puppet(sc, "farmor/knead", depth=7.0, height=3.2, x=1.3, floor=-2.1)
    push(sc, dy=0.8)


def s13(sc):
    bedroom(sc)
    puppet(sc, "nell/in-bed", depth=5.0, height=3.0, x=0.0, floor=-1.6, breathe=True)
    push(sc, dy=1.4, dz=-0.2)


def s14(sc):
    living(sc)
    puppet(sc, "nell/hold-box", depth=7.5, height=3.0, x=-1.5, floor=-2.2)
    puppet(sc, "farmor/give-box", depth=7.8, height=3.2, x=0.9, floor=-2.3)
    push(sc, dy=0.8)


# A cena da canção acontece no degrau: a câmera chega perto da porta (a casa
# está a 25 m; aqui a câmera fica a ~11 m dela, baixa, na altura do degrau).
DOOR = dict(x=3.6, start=(3.0, 13.0, -3.6))


def s15(sc):
    house(sc)
    end = frames(sc)
    puppet(sc, "nell/hold-box", depth=23.2, height=1.75, x=4.3, floor=-5.05)
    fox_walk = puppet(sc, "fox/walk", depth=23.0, height=0.85, x=-2.5, floor=-5.05)
    fox_sit = puppet(sc, "fox/sit", depth=23.0, height=0.9, x=2.6, floor=-5.05)
    arrive = int(end * 0.7)
    key(fox_walk, "location", [(1, (-2.5, fox_walk.location.y, fox_walk.location.z)),
                               (arrive, (2.6, fox_walk.location.y, fox_walk.location.z))], interp="LINEAR")
    visible(fox_walk, [(1, True), (arrive, False)])
    visible(fox_sit, [(1, False), (arrive, True)])
    push(sc, dy=1.0, start=DOOR["start"])


def s16(sc):
    house(sc)
    puppet(sc, "nell/kneel-sing", depth=23.2, height=1.5, x=4.0, floor=-5.05)
    layer(sc, "props/box-closed", depth=23.0, width=0.4, x=3.3, z=-4.9)
    puppet(sc, "fox/sit", depth=23.0, height=0.9, x=2.5, floor=-5.05)
    # aproxima devagar durante a canção
    push(sc, dy=4.0, dx=0.3, dz=0.35, start=(3.0, 14.0, -3.8))


def s17(sc):
    house(sc)
    end = frames(sc)
    puppet(sc, "nell/kneel-sing", depth=23.2, height=1.5, x=4.0, floor=-5.05)
    layer(sc, "props/box-closed", depth=23.0, width=0.4, x=3.3, z=-4.9)
    bow = puppet(sc, "fox/bow", depth=23.0, height=0.9, x=2.6, floor=-5.05)
    sit = puppet(sc, "fox/sit", depth=23.0, height=0.9, x=2.5, floor=-5.05)
    trot = puppet(sc, "fox/trot", depth=23.0, height=0.85, x=2.5, floor=-5.05, flip=True)
    t_bow, t_go = int(end * 0.25), int(end * 0.55)
    visible(sit, [(1, True), (t_bow, False)])
    visible(bow, [(1, False), (t_bow, True), (t_go, False)])
    visible(trot, [(1, False), (t_go, True)])
    key(trot, "location", [(t_go, (2.5, trot.location.y, trot.location.z)),
                           (end, (-3.5, trot.location.y + 2.0, trot.location.z + 0.15))], interp="LINEAR")
    # recua devagar enquanto a raposa vai embora
    push(sc, dy=-3.0, dx=-0.8, dz=0.4, start=(3.3, 18.0, -3.45))


def s18(sc):
    living(sc)
    puppet(sc, "nell/sit-blanket", depth=8.2, height=3.0, x=-2.0, floor=-2.35)
    layer(sc, "props/box-open", depth=8.0, width=0.6, x=-1.5, z=-1.0)
    puppet(sc, "farmor/tears", depth=8.2, height=3.1, x=1.9, floor=-2.35)
    push(sc, dy=1.2, start=(0, 1.5, -0.2))


def s19(sc):
    kitchen(sc, table=False)
    end = frames(sc)
    puppet(sc, "farmor/write", depth=6.5, height=3.2, x=0.2, floor=-2.1)
    opened = layer(sc, "props/box-open", depth=6.3, width=0.8, x=-1.35, z=-0.8)
    closed = layer(sc, "props/box-closed", depth=6.3, width=0.8, x=-1.35, z=-0.8)
    visible(opened, [(1, True), (int(end * 0.75), False)])
    visible(closed, [(1, False), (int(end * 0.75), True)])
    push(sc, dy=0.8)


def s20(sc):
    forest(sc)
    fox = puppet(sc, "fox/trot", depth=7, height=2.2, x=-0.6, floor=-2.4, flip=True)
    key(fox, "location", [(1, (-0.6, fox.location.y, -2.4)), (frames(sc), (0.8, fox.location.y + 7, -1.9))])
    push(sc, dy=0.6, dz=0.2)


SHOTS = {f"s{i:02d}": globals()[f"s{i:02d}"] for i in range(1, 21)}


def build(shot_id):
    sc = new_shot_scene(shot_id, seconds=DUR[shot_id])
    SHOTS[shot_id](sc)
    sc.frame_set(1)
    return sc


def build_all():
    for sid in SHOTS:
        build(sid)


# ─── Render ─────────────────────────────────────────────────────────────────

FRAMES = ROOT + "/build/frames"


def render_range(shot_id, f0, f1, width=1280, height=720):
    """Renderiza os quadros f0..f1 (inclusive) em build/frames/<plano>/f_####.png.

    Roda por dentro do Blender aberto: o EEVEE no modo `-b` desta máquina é
    ~100× mais lento. Pula quadros que já existem — dá pra retomar.
    """
    import os
    import time
    sc = bpy.data.scenes[shot_id]
    bpy.context.window.scene = sc
    sc.render.resolution_x, sc.render.resolution_y = width, height
    sc.render.resolution_percentage = 100
    sc.render.image_settings.file_format = "PNG"
    out = f"{FRAMES}/{shot_id}"
    os.makedirs(out, exist_ok=True)
    t = time.time()
    done = 0
    for f in range(f0, min(f1, sc.frame_end) + 1):
        path = f"{out}/f_{f:04d}.png"
        if os.path.exists(path):
            continue
        sc.frame_set(f)
        sc.render.filepath = path
        bpy.ops.render.render(write_still=True, scene=shot_id)
        done += 1
    return done, time.time() - t
