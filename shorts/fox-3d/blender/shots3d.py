"""Os 11 planos de The Fox and the North Wind em 3D (toon diorama).

Roda dentro do Blender (GUI via MCP, ou `blender -b` pros testes/render):

    exec(open(".../shots3d.py").read())
    sc = build("k02")

Cada plano é uma cena (k01…k11) com o cenário do sets3d, os personagens do
Tripo (characters3d) e a câmera. Durações e falas vêm do film.json.
"""

import json
import math
import os
import sys

import bpy

REPO = "/Users/alexandrejunior/Pedagogy_Swift"
sys.path.insert(0, REPO + "/scripts/shorts")
import toon3d as T                     # noqa: E402
import characters3d as C               # noqa: E402
from sets3d import interior as I       # noqa: E402

ROOT = REPO + "/shorts/fox-3d"
MODELS = ROOT + "/build/models"
FILM = json.load(open(ROOT + "/film.json"))
DUR = {s["id"]: s["duration"] for s in FILM["shots"]}
FPS = 24
NELL_H, FARMOR_H = 1.35, 1.5
SIT_HOLD = 30                           # o "sit" do Tripo é um agachamento: no começo (tronco reto,
                                        # mãos nos joelhos, coxas na horizontal) ele é uma pose de cadeira


def new_scene(shot_id):
    """Cena nova e vazia pro plano (recria se já existir)."""
    sc = bpy.data.scenes.new(shot_id + "__new")
    if bpy.context.window:
        bpy.context.window.scene = sc
    old = bpy.data.scenes.get(shot_id)
    if old:
        for ob in list(old.collection.all_objects):
            bpy.data.objects.remove(ob, do_unlink=True)
        bpy.data.scenes.remove(old)
    sc.name = shot_id
    T.render_setup(sc, 1280, 720, FPS)
    sc.frame_start, sc.frame_end = 1, int(round(DUR[shot_id] * FPS))
    return sc


def cam_move(sc, start, end, look0, look1, lens):
    """Câmera que vai de start→end olhando de look0→look1, com ease-in-out."""
    cam = T.camera(sc, start, look0, lens=lens, name=f"Cam_{sc.name}")
    target = bpy.data.objects.new(f"Look_{sc.name}", None)
    sc.collection.objects.link(target)
    target.location = look0
    con = cam.constraints.new("TRACK_TO")
    con.target = target
    con.track_axis = "TRACK_NEGATIVE_Z"
    con.up_axis = "UP_Y"
    for ob, a, b in ((cam, start, end), (target, look0, look1)):
        ob.location = a
        ob.keyframe_insert("location", frame=1)
        ob.location = b
        ob.keyframe_insert("location", frame=sc.frame_end)
    return cam


def interior(sc):
    A = I.build_interior(sc)
    return A


def v(a, k=1.0, dz=0.0):
    return (a[0] * k, a[1] * k, a[2] + dz)


# ─── Planos do interior ─────────────────────────────────────────────────────

def k02(sc):
    """Farmor conta a história; Nell escuta. Os dois sentados junto ao fogão."""
    A = interior(sc)
    nell = C.load(sc, MODELS, "nell", "biped-sit", NELL_H, name="nell_k02", tint=C.INTERIOR_TINT)
    C.play(nell, hold=SIT_HOLD)
    C.sit_on(nell, A["chair_left_seat"], A["chair_left_rot"][2], SIT_HOLD)
    farmor = C.load(sc, MODELS, "farmor", "biped-sit", FARMOR_H, name="farmor_k02", tint=C.INTERIOR_TINT)
    C.play(farmor, hold=SIT_HOLD)
    C.sit_on(farmor, A["chair_right_seat"], A["chair_right_rot"][2], SIT_HOLD)
    cl, look, lens = I.CAMERAS["cam_wide"]
    cam_move(sc, cl, (cl[0], cl[1] + 0.5, cl[2] - 0.05), look, look, lens)


def seated_pair(sc, A, tag):
    """Nell na cadeira da esquerda, Farmor na da direita (k02/k03)."""
    nell = C.load(sc, MODELS, "nell", "biped-sit", NELL_H, name=f"nell_{tag}", tint=C.INTERIOR_TINT)
    C.play(nell, hold=SIT_HOLD)
    C.sit_on(nell, A["chair_left_seat"], A["chair_left_rot"][2], SIT_HOLD)
    farmor = C.load(sc, MODELS, "farmor", "biped-sit", FARMOR_H, name=f"farmor_{tag}", tint=C.INTERIOR_TINT)
    C.play(farmor, hold=SIT_HOLD)
    C.sit_on(farmor, A["chair_right_seat"], A["chair_right_rot"][2], SIT_HOLD)
    return nell, farmor


def k03(sc):
    """Mais perto: 'And if you don't?' / 'Then the fox takes something else.'"""
    A = interior(sc)
    seated_pair(sc, A, "k03")
    cl, look, lens = I.CAMERAS["cam_twoshot"]
    cam_move(sc, cl, (cl[0], cl[1] + 0.25, cl[2]), look, look, lens)


def k06(sc):
    """Terceira noite, junto à porta: Nell de casaco com a caixinha; Farmor concorda."""
    A = interior(sc)
    nell = C.load(sc, MODELS, "nell", "biped-standing_relax", NELL_H, name="nell_k06", tint=C.INTERIOR_TINT)
    C.play(nell)
    nell.location = A["door_inside"]
    nell.rotation_euler = A["door_inside_rot"]
    box = C.load(sc, MODELS, "box", None, 0.22, name="box_k06", tint=C.INTERIOR_TINT)
    hand_box(nell, box)
    farmor = C.load(sc, MODELS, "farmor", "biped-agree", FARMOR_H, name="farmor_k06", tint=C.INTERIOR_TINT)
    C.play(farmor, start=int(3.4 * FPS), loop=False)     # concorda depois de "I need to do this on my own"
    farmor.location = A["farmor_by_door"]
    farmor.rotation_euler = A["farmor_by_door_rot"]
    cl, look, lens = I.CAMERAS["cam_door"]
    cam_move(sc, cl, (cl[0] - 0.2, cl[1] + 0.3, cl[2]), look, look, lens)


def k10(sc):
    """'You sang.' / 'Mama's lullaby.' / 'My mother's song.' — Farmor, comovida."""
    A = interior(sc)
    nell = C.load(sc, MODELS, "nell", "biped-sit", NELL_H, name="nell_k10", tint=C.INTERIOR_TINT)
    C.play(nell, hold=SIT_HOLD)
    C.sit_on(nell, A["chair_left_seat"], A["chair_left_rot"][2], SIT_HOLD)
    box = C.load(sc, MODELS, "box", None, 0.2, name="box_k10", tint=C.INTERIOR_TINT)
    # no colo: entre os joelhos e o quadril, apoiada nas coxas
    hip, knee = C.bone_world(nell, "Pelvis", 1), C.bone_world(nell, "L_Calf", 1)
    box.location = ((hip.x + knee.x) / 2, (hip.y + knee.y) / 2, max(hip.z, knee.z) - 0.02)
    box.rotation_euler = A["chair_left_rot"]
    farmor = C.load(sc, MODELS, "farmor", "biped-cry", FARMOR_H, name="farmor_k10", tint=C.INTERIOR_TINT)
    C.play(farmor, start=int(0.3 * FPS), loop=False)
    seat = A["chair_right_seat"]
    farmor.location = (seat[0] - 0.1, seat[1] - 0.35, 0.0)          # de pé, ao lado da cadeira
    farmor.rotation_euler = A["chair_right_rot"]
    cl, look, lens = I.CAMERAS["cam_twoshot"]
    cam_move(sc, cl, (cl[0], cl[1] + 0.35, cl[2] + 0.05), look, look, lens)


def hand_box(holder, box, bone_l="L_Hand", bone_r="R_Hand"):
    """Prende a caixinha entre as mãos: segue o ponto médio dos dois ossos."""
    arm = C._armature(holder)
    names = [b.name for b in arm.pose.bones]
    bl = next((n for n in names if bone_l in n), None)
    br = next((n for n in names if bone_r in n), None)
    con = box.constraints.new("COPY_LOCATION")
    con.target, con.subtarget = arm, bl
    con2 = box.constraints.new("COPY_LOCATION")
    con2.target, con2.subtarget, con2.influence = arm, br, 0.5
    rot = box.constraints.new("COPY_ROTATION")
    rot.target = holder


SHOTS = {"k02": k02, "k03": k03, "k06": k06, "k10": k10}


def build(shot_id):
    sc = new_scene(shot_id)
    SHOTS[shot_id](sc)
    sc.frame_set(1)
    return sc
