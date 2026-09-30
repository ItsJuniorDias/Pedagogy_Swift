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
    # balanço de passo que se apaga nos últimos 6 quadros: parado, ninguém quica
    fc = ob.driver_add("location", 2)
    fc.driver.type = "SCRIPTED"
    fc.driver.expression = (f"{ob.location.z:.4f} + {bob:.4f}*sin(2*pi*frame/{0.55 * FPS:.2f})"
                            f"*min(1, max(0, ({f1} - frame)/6))")
    for m in list(fc.modifiers):
        fc.modifiers.remove(m)


# ─── Cenários ───────────────────────────────────────────────────────────────

def house(sc, tint=None, snowy=True, cam_depth=0.0):
    """Exterior da casa. `cam_depth` = quanto a câmera já está à frente no plano
    (o `start[1]`/avanço do push). A neve é posta a partir dali: se ficasse na
    profundidade fixa, a câmera dos planos da porta passaria por dentro dela e
    os flocos colados na lente piscariam como manchas brancas enormes."""
    layer(sc, "house/sky", depth=80, overscan=1.35, z=8, tint=tint)
    layer(sc, "house/far", depth=45, overscan=1.0, z=2.2, tint=tint)
    layer(sc, "house/mid", depth=25, overscan=1.3, z=-2.6, tint=tint)
    layer(sc, "house/near", depth=9, overscan=1.3, z=-0.6, tint=tint)
    if snowy:
        if cam_depth:
            # faixa entre 2,5 m à frente do ponto mais avançado da câmera e a casa
            front, back = cam_depth + 2.5, 24.5
            snow(sc, depth=(front + back) / 2, count=450, thickness=back - front)
        else:
            snow(sc, depth=14, count=600)
        snow(sc, depth=max(30, cam_depth + 16), count=900, size=0.1, name="SnowFar")


def living(sc, chairs=True):
    """`chairs=False` tira a camada do meio (cadeiras, tapete, cesto): em pé,
    os personagens pareciam estar dentro das cadeiras."""
    layer(sc, "living/back", depth=14, overscan=1.15)
    if chairs:
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
    # entra já livre do pinheiro da esquerda, inteira no quadro, e chega perto da casa
    # walk-clean: o recorte sem o monte de neve que deslizava junto (cleanup_layers.py)
    nell = puppet(sc, "nell/walk-clean", depth=13, height=3.2, x=-4.3, floor=-3.5)
    walk(nell, -4.3, 1.0, 1, frames(sc) - 24)
    push(sc, dy=1.2)


def s03(sc):
    living(sc)
    puppet(sc, "nell/sit-blanket", depth=8.5, height=3.0, x=-2.3, floor=-2.35)
    puppet(sc, "farmor/sit-stove", depth=8.5, height=3.1, x=2.3, floor=-2.35)
    push(sc, dy=1.5)


def s04(sc):
    forest(sc, tint=B)
    end = frames(sc)
    # "...and at his door, the light became a small white fox" (~7,2–8,9 s):
    # a luz chega e vira raposa nessa hora, não depois da fala.
    arrive = int(end * 0.52)
    sailor = puppet(sc, "sailor/walk", depth=12, height=3.8, x=-5.0, floor=-3.8, tint=B)
    walk(sailor, -5.0, 1.2, 1, arrive, bob=0.03)
    orb = glow_orb(sc, (-1.0, 12, -1.0), radius=0.18)
    key(orb, "location", [(1, (-1.0, orb.location.y, -1.0)), (arrive, (3.4, orb.location.y, -2.3))])
    sway(orb, "delta_location", 2, 0.15, 2.0)       # delta: não briga com a descida keyada
    key(orb, "scale", [(arrive, (1, 1, 1)), (int(end * 0.60), (0.01, 0.01, 0.01))])
    fox = puppet(sc, "fox/sit", depth=12, height=1.8, x=3.4, floor=-3.4, tint=B)
    pop_in(fox, int(end * 0.55), dur=10)
    push(sc, dy=1.0)


def s05(sc):
    doorstep(sc)
    end = frames(sc)
    # no degrau, dentro do quadro (antes a borda de baixo cortava os três)
    for i, (pid, x) in enumerate([("props/coin", -1.3), ("props/bread", 0.0), ("props/feather", 1.3)]):
        ob = layer(sc, pid, depth=9.0, width=1.15, x=x * 1.2, z=-1.7, tint=B)
        # "And a gift (6,4 s) must be given (7,7 s). Honestly (8,75 s)." — antes
        # a moeda aparecia antes de ela falar em presente
        pop_in(ob, (154, 185, 210)[i])
    tracks(sc, (3.8, 9.3, -2.1), (1.8, 9.4, -2.05), n=6, size=0.14, tint=B, tilt=6)
    push(sc, dy=0.8)


def s06(sc):
    living(sc)
    puppet(sc, "nell/sit-blanket", depth=8.5, height=3.0, x=-1.35, floor=-2.35)
    puppet(sc, "farmor/sit-stove", depth=8.5, height=3.1, x=1.35, floor=-2.35)
    push(sc, dy=1.0, start=(0, 3.0, -0.3))


def s07(sc):
    bedroom(sc)
    nell = puppet(sc, "nell/nightgown-window", depth=8.3, height=3.2, x=2.6, floor=-2.4)
    walk(nell, 2.6, 0.2, 1, 72, bob=0.02)
    push(sc, dy=1.2)


def s08(sc):
    house(sc, cam_depth=11.0)
    # pegadas na faixa de neve da frente da casa, vindo da floresta até a porta
    tracks(sc, (-1.5, 23.4, -5.08), (3.5, 23.4, -5.08), n=10, size=0.2, tilt=12)
    push(sc, dy=6.0, dx=2.2, dz=-3.3, start=(0, 5.0, -0.5))


def s09(sc):
    kitchen(sc, table=False)
    puppet(sc, "farmor/coffee", depth=7, height=3.6, x=-0.9, floor=-2.3)
    push(sc, dy=0.8)


def s10(sc):
    kitchen(sc)
    end = frames(sc)
    # a caixinha é o assunto: maior, e a câmera termina nela (não na tigela).
    # Só a arte aberta: a "fechada" gerada era outra caixa (clara, pontas azuis).
    layer(sc, "props/box-open", depth=5.7, width=1.5, x=-1.5, z=-0.73)
    push(sc, dy=1.6, dx=-0.8, dz=-0.35)


def s11(sc):
    doorstep(sc)
    end = frames(sc)
    cut = int(end * 0.62)
    leave = int(end * 0.48)          # sai em "and left" (4,8 s), não em "looked at it"
    # Astrid estende o colar PARA a raposa, que senta na frente da porta
    astrid = puppet(sc, "youngfarmor/necklace", depth=9, height=3.4, x=-1.9, floor=-2.8, tint=B, flip=True)
    necklace = layer(sc, "props/necklace", depth=8.9, width=0.45, x=-1.3, z=-0.6)   # sem tinta: o ouro destaca
    sit = puppet(sc, "fox/sit", depth=9.2, height=1.9, x=0.6, floor=-2.8, tint=B)
    trot = puppet(sc, "fox/trot", depth=9.2, height=2.2, x=0.6, floor=-3.15, tint=B)
    visible(sit, [(1, True), (leave, False)])
    visible(trot, [(1, False), (leave, True)])
    key(trot, "location", [(leave, (0.6, trot.location.y, trot.location.z)),
                           (cut, (5.0, trot.location.y, trot.location.z))], interp="LINEAR")
    sway(trot, "delta_location", 2, 0.03, 0.4)      # passo
    # corte seco: na manhã seguinte, o pratinho vazio em cima da cômoda do quarto
    room = layer(sc, "bedroom/back", depth=5, overscan=1.2, tint=B, name="s11_room")
    dresser = layer(sc, "bedroom/near", depth=4.95, overscan=1.3, x=1.3, z=-0.9, tint=B, name="s11_dresser")
    dish = layer(sc, "props/ring-dish", depth=4.9, width=0.9, x=0.25, z=-0.35, tint=B)   # ao lado da vela, não sobre ela
    for ob in (room, dresser, dish):
        visible(ob, [(1, False), (cut, True)])
    for ob in (astrid, necklace):
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
    # Uma caixinha só em cena: Nell com ela; Farmor sentada, olhando.
    # (Sem a camada das cadeiras: em pé, Nell parecia estar dentro de uma.)
    living(sc, chairs=False)
    puppet(sc, "nell/hold-box", depth=7.5, height=3.0, x=-0.9, floor=-2.2)
    puppet(sc, "farmor/sit-stove", depth=8.3, height=3.1, x=1.5, floor=-2.35)
    push(sc, dy=0.8)


# A cena da canção acontece no degrau. Posições comuns a s15–s17:
NELL_X, FOX_X, BOX_X, FLOOR = 4.0, 2.5, 3.35, -5.05


def slow_snow(sc, frames_values):
    """Neve mais lenta (a canção acalma a noite): time_tweak das partículas."""
    for ob in sc.objects:
        for psys in ob.particle_systems:
            key(psys.settings, "time_tweak", frames_values)


def s15(sc):
    house(sc, cam_depth=16.0)
    end = frames(sc)
    puppet(sc, "nell/hold-box", depth=23.2, height=1.75, x=4.3, floor=FLOOR)
    fox_walk = puppet(sc, "fox/walk", depth=23.0, height=1.1, x=-2.5, floor=-5.28)
    fox_sit = puppet(sc, "fox/sit", depth=23.0, height=0.9, x=2.6, floor=FLOOR, flip=True)   # de frente pra Nell
    arrive = int(end * 0.7)
    key(fox_walk, "location", [(1, (-2.5, fox_walk.location.y, fox_walk.location.z)),
                               (arrive, (2.6, fox_walk.location.y, fox_walk.location.z))], interp="LINEAR")
    visible(fox_walk, [(1, True), (arrive, False)])
    visible(fox_sit, [(1, False), (arrive, True)])
    sway(fox_walk, "delta_location", 2, 0.02, 0.45)
    push(sc, dy=1.0, start=(3.0, 15.0, -4.0))


# s16 começa mais perto que o fim do s15 (corte de aproximação claro) e
# termina exatamente onde o s17 começa.
S16_START = (3.2, 18.0, -4.0)     # mais baixo que isso Nell parece ajoelhada na fundação da casa
S16_END = (3.3, 18.8, -4.1)


def s16(sc):
    house(sc, cam_depth=S16_END[1])
    end = frames(sc)
    kneel = 36                        # Nell ainda de pé com a caixa; ajoelha e a põe no degrau
    stand = puppet(sc, "nell/hold-box", depth=23.2, height=1.75, x=4.3, floor=FLOOR)
    sing = puppet(sc, "nell/kneel-sing", depth=23.2, height=1.5, x=NELL_X, floor=FLOOR)
    box = layer(sc, "props/box-open", depth=22.95, width=0.55, x=BOX_X, z=-4.77)
    visible(stand, [(1, True), (kneel, False)])
    visible(sing, [(1, False), (kneel, True)])
    visible(box, [(1, False), (kneel, True)])
    puppet(sc, "fox/sit", depth=23.0, height=0.9, x=FOX_X, floor=FLOOR, flip=True)
    # a canção desacelera a neve até quase parar
    slow_snow(sc, [(kneel, 1.0), (int(end * 0.6), 0.15)])
    push(sc, dy=S16_END[1] - S16_START[1], dx=S16_END[0] - S16_START[0],
         dz=S16_END[2] - S16_START[2], start=(S16_START[0], S16_START[1], S16_START[2]))


def s17(sc):
    house(sc, cam_depth=S16_END[1])
    end = frames(sc)
    puppet(sc, "nell/kneel-sing", depth=23.2, height=1.5, x=NELL_X, floor=FLOOR)
    layer(sc, "props/box-open", depth=22.95, width=0.55, x=BOX_X, z=-4.77)
    # "The fox bowed its head (~1,3 s), once, like someone accepting a gift, and was gone (~4,5 s)"
    w0, w1, t_bow, t_go = 4, 26, 28, int(end * 0.5)
    sit = puppet(sc, "fox/sit", depth=23.0, height=0.9, x=FOX_X, floor=FLOOR, flip=True)
    walker = puppet(sc, "fox/walk", depth=23.0, height=1.1, x=FOX_X, floor=-5.28)
    bow = puppet(sc, "fox/bow", depth=23.0, height=1.0, x=2.9, floor=-5.24, flip=True)
    trot = puppet(sc, "fox/trot", depth=23.0, height=1.1, x=2.9, floor=-5.24, flip=True)
    key(walker, "location", [(w0, (FOX_X, walker.location.y, walker.location.z)),
                             (w1, (2.9, walker.location.y, walker.location.z))], interp="LINEAR")
    visible(sit, [(1, True), (w0, False)])
    visible(walker, [(1, False), (w0, True), (t_bow, False)])
    visible(bow, [(1, False), (t_bow, True), (t_go, False)])
    visible(trot, [(1, False), (t_go, True)])
    sway(walker, "delta_location", 2, 0.02, 0.45)
    sway(trot, "delta_location", 2, 0.02, 0.4)
    key(trot, "location", [(t_go, (2.9, trot.location.y, trot.location.z)),
                           (end, (-3.5, trot.location.y + 2.0, trot.location.z + 0.15))], interp="LINEAR")
    slow_snow(sc, [(0, 1.0), (1, 0.15)])       # pré-rolagem normal, depois a calma do fim do s16
    # recua devagar enquanto a raposa vai embora
    push(sc, dy=-3.0, dx=-0.8, dz=0.4, start=S16_END)


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
    # em cima da mesa, ao lado do tinteiro (antes flutuava na frente da janela)
    layer(sc, "props/box-open", depth=6.3, width=0.8, x=-0.6, z=-0.24)
    push(sc, dy=0.8)


def s20(sc):
    forest(sc)
    # sem flip: a imagem já trota pra direita/fundo (com flip ela andava de ré)
    fox = puppet(sc, "fox/trot", depth=7, height=2.2, x=-0.6, floor=-2.4)
    key(fox, "location", [(1, (-0.6, fox.location.y, -2.4)), (frames(sc), (0.8, fox.location.y + 7, -1.9))],
        interp="LINEAR")                             # já trotando desde o 1º quadro
    sway(fox, "delta_location", 2, 0.04, 0.4)
    push(sc, dy=0.6, dz=0.2)


SHOTS = {f"s{i:02d}": globals()[f"s{i:02d}"] for i in range(1, 21)}


BLEND = ROOT + "/blender/fox.blend"


def build(shot_id):
    # O Blender aberto é compartilhado: se outro projeto estiver aberto, montar
    # aqui apagaria as cenas dele com o mesmo nome (s01…) — recusa.
    if bpy.data.filepath != BLEND:
        raise RuntimeError(f"o Blender está com {bpy.data.filepath or 'um arquivo sem nome'} aberto, "
                           f"não com {BLEND}; abra o fox.blend antes de montar")
    sc = new_shot_scene(shot_id, seconds=DUR[shot_id])
    SHOTS[shot_id](sc)
    sc.frame_set(1)
    return sc


def build_all():
    for sid in SHOTS:
        build(sid)


# ─── Render ─────────────────────────────────────────────────────────────────

FRAMES = ROOT + "/build/frames"
FRAMES_V2 = ROOT + "/build/frames_v2"   # polish: renders novos sem apagar os antigos


def render_range(shot_id, f0, f1, width=1280, height=720, root=None):
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
    out = f"{root or FRAMES}/{shot_id}"
    os.makedirs(out, exist_ok=True)
    t = time.time()
    done = 0
    todo = [f for f in range(f0, min(f1, sc.frame_end) + 1)
            if not os.path.exists(f"{out}/f_{f:04d}.png")]
    if not todo:
        return 0, 0.0
    # A neve é simulação: pular direto pro quadro N não simula o que caiu antes.
    # Avança quadro a quadro desde o começo do cache até o primeiro a renderizar.
    starts = [int(ps.point_cache.frame_start) for ob in sc.objects for ps in ob.particle_systems]
    if starts:
        for f in range(min(starts), todo[0]):
            sc.frame_set(f)
    for f in todo:
        path = f"{out}/f_{f:04d}.png"
        if os.path.exists(path):
            continue
        sc.frame_set(f)
        sc.render.filepath = path
        bpy.ops.render.render(write_still=True, scene=shot_id)
        done += 1
    return done, time.time() - t


def render_next(max_frames=200, root=None):
    """Renderiza os próximos quadros que faltam, até `max_frames` no total,
    emendando planos. Feito pra ser chamado repetidamente, uma chamada por
    vez: cada chamada cabe no tempo limite da conexão com o Blender."""
    import os
    root = root or FRAMES_V2

    def missing(sid):
        n = int(round(DUR[sid] * FPS))
        return [f for f in range(1, n + 1) if not os.path.exists(f"{root}/{sid}/f_{f:04d}.png")]

    budget, log = max_frames, []
    for sid in SHOTS:
        if budget <= 0:
            break
        m = missing(sid)
        if not m:
            continue
        build(sid)
        done, secs = render_range(sid, m[0], m[0] + budget - 1, root=root)
        log.append(f"{sid} {m[0]}-{m[0] + done - 1} ({secs:.0f}s)")
        budget -= done
    left = sum(len(missing(s)) for s in SHOTS)
    return (" + ".join(log) or "nada") + f" | faltam {left}"
