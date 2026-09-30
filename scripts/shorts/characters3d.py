"""Personagens 3D do Tripo dentro das cenas do Blender.

Roda dentro do Blender. Carrega os .glb gerados por `tripo_assets.py`
(shorts/<slug>/build/models/<id>/), deixa no visual toon do `toon3d.py` e
coloca em cena:

    holder = load(sc, MODELS, "nell", anim="biped-walk", height=1.35)
    play(holder, start=1, loop=True)                  # anda sem sair do lugar
    walk_path(holder, [(x0, y0), (x1, y1)], f0, f1)   # e a cena desloca
    play(holder, hold=173)                            # congela no último quadro (já sentada)

Cada personagem fica num Empty "holder" (posição/rotação/escala da cena);
o esqueleto e a malha do Tripo ficam dentro dele, com os pés em z=0 local.
Trocar de animação = carregar outro .glb e alternar visibilidade (como os
recortes do 2.5D), o que é simples e não mistura ações.
"""

import math
import os

import bpy
from mathutils import Vector

import toon3d as T

# Frente de cada modelo no arquivo do Tripo → rotação Z pra ele olhar pra -Y
# (a convenção das cenas). Medido em renders de teste com as 4 rotações:
# os humanos vêm olhando pra +X, a raposa andando pra +Y, a caixinha com o
# fecho de lado; a raposa sentada e a em reverência já olham pra -Y.
FACING_FIX = {"nell": -math.pi / 2, "farmor": -math.pi / 2, "fox": math.pi,
              "fox-sit": 0.0, "fox-bow": 0.0, "box": math.pi / 2}
# Pelagem/roupa clara: sombra do toon mais leve, senão o branco lê bege.
SHADOW = {"fox": 0.78, "fox-sit": 0.78, "fox-bow": 0.78}
# Luz de cada ambiente, pra tingir as faixas do toon dos personagens
# (mesmos valores do interior.py: sombra fria, luz quente do fogo).
INTERIOR_TINT = ((0.92, 0.90, 1.12), (1.10, 0.99, 0.80))
NIGHT_TINT = ((0.82, 0.88, 1.15), (0.96, 0.99, 1.06))       # lua: tudo um pouco mais frio
DAWN_TINT = ((0.95, 0.92, 1.05), (1.08, 1.0, 0.92))

# Ajuste da textura do Tripo (valor, saturação): a raposa veio creme-bege.
TEXTURE_FIX = {"fox": (1.22, 0.45), "fox-sit": (1.22, 0.45), "fox-bow": (1.22, 0.45)}


def _new_objects(before):
    return [o for o in bpy.data.objects if o.name not in before]


def _dedupe_images(new_images):
    """O importador do glTF cria uma cópia da textura 4K a cada import: junta
    com a que já existe (mesmo nome-base) pra não estourar a memória."""
    for img in new_images:
        base = img.name.split(".")[0]
        keep = next((i for i in bpy.data.images if i.name == base and i != img), None)
        if keep:
            img.user_remap(keep)
            bpy.data.images.remove(img)


def load(sc, models_dir, asset, anim=None, height=None, name=None, outline=0.012, tint=None):
    """Importa `<asset>/anim-<anim>.glb` (ou rigged/model) e devolve o holder.

    `height`: altura final em metros (pés no chão). `outline`: espessura do
    contorno no espaço do modelo já escalado (m). `tint`: (shadow_tint,
    light_tint) da luz da cena — ex.: INTERIOR_TINT perto do fogo.
    """
    folder = os.path.join(models_dir, asset)
    fname = f"anim-{anim}.glb" if anim else ("rigged.glb" if os.path.exists(os.path.join(folder, "rigged.glb")) else "model.glb")
    path = os.path.join(folder, fname)
    before = {o.name for o in bpy.data.objects}
    imgs_before = {i.name for i in bpy.data.images}
    acts_before = {a.name for a in bpy.data.actions}
    if bpy.context.window:                            # sem janela (blender -b) não há o que trocar
        bpy.context.window.scene = sc
    bpy.ops.import_scene.gltf(filepath=path)
    new = _new_objects(before)
    _dedupe_images([i for i in bpy.data.images if i.name not in imgs_before])

    # lixo do Tripo: uma icosfera solta de 2 m
    for o in list(new):
        if o.type == "MESH" and o.parent is None and len(o.data.vertices) < 100 and any(x.type == "ARMATURE" for x in new):
            new.remove(o)
            bpy.data.objects.remove(o, do_unlink=True)

    for o in new:                                     # tudo vai pra cena pedida
        for c in list(o.users_collection):
            c.objects.unlink(o)
        sc.collection.objects.link(o)

    meshes = [o for o in new if o.type == "MESH"]
    arm = next((o for o in new if o.type == "ARMATURE"), None)
    root = arm or meshes[0]
    label = name or f"{asset}_{anim or 'static'}"

    # material toon por cima da pintura do Tripo
    for m in meshes:
        tex = None
        for mat in m.data.materials:
            if mat and mat.use_nodes:
                tex = next((n.image for n in mat.node_tree.nodes if n.type == "TEX_IMAGE" and n.image), tex)
        st, lt = tint or ((1.0, 1.0, 1.0), (1.0, 1.0, 1.0))
        key = "" if not tint else "_" + "_".join(f"{v:.2f}" for v in (*st, *lt))
        tm = T.toon(f"Toon_{asset}{key}", (255, 255, 255), image=tex, shadow=SHADOW.get(asset, 0.62),
                    light=1.08, shadow_tint=st, light_tint=lt)
        fix = TEXTURE_FIX.get(asset)
        if fix and not any(n.type == "HUE_SAT" for n in tm.node_tree.nodes):
            nt = tm.node_tree
            tex_node = next(n for n in nt.nodes if n.type == "TEX_IMAGE")
            link = next(l for l in nt.links if l.from_node == tex_node and l.from_socket.name == "Color")
            dest = link.to_socket
            nt.links.remove(link)
            hsv = nt.nodes.new("ShaderNodeHueSaturation")
            hsv.inputs["Value"].default_value = fix[0]
            hsv.inputs["Saturation"].default_value = fix[1]
            nt.links.new(tex_node.outputs["Color"], hsv.inputs["Color"])
            nt.links.new(hsv.outputs["Color"], dest)
        m.data.materials.clear()
        m.data.materials.append(tm)

    # altura e chão, medidos na pose de descanso/1º quadro
    sc.frame_set(1)
    bpy.context.view_layer.update()
    pts = [m.matrix_world @ Vector(c) for m in meshes for c in m.bound_box]
    zmin, zmax = min(p.z for p in pts), max(p.z for p in pts)
    k = (height / (zmax - zmin)) if height else 1.0

    # holder (posição/rotação na cena) → pivot (frente, escala, pés no chão) → esqueleto.
    # A ação do Tripo anima o transform do próprio esqueleto; por isso a
    # correção de frente e a escala ficam num nível que a ação não toca.
    holder = bpy.data.objects.new(f"CHAR_{label}", None)
    holder.empty_display_type = "ARROWS"
    holder.empty_display_size = 0.3
    sc.collection.objects.link(holder)
    pivot = bpy.data.objects.new(f"PIVOT_{label}", None)
    pivot.empty_display_size = 0.1
    sc.collection.objects.link(pivot)
    pivot.parent = holder
    pivot.rotation_euler.z = FACING_FIX.get(asset, 0.0)
    pivot.scale = (k, k, k)
    pivot.location = (0, 0, -zmin * k)
    root.parent = pivot

    for m in meshes:
        T.outline(m, outline / k)                     # espessura em metros depois da escala
    holder["asset"] = asset
    holder["anim"] = anim or ""
    holder["armature"] = arm.name if arm else ""
    new_actions = [a for a in bpy.data.actions if a.name not in acts_before]
    holder["action"] = new_actions[0].name if new_actions else ""
    return holder


def _armature(holder):
    return bpy.data.objects.get(holder["armature"]) if holder.get("armature") else None


def play(holder, start=1, speed=1.0, loop=True, hold=None, offset=0, scene_end=None):
    """Toca a ação do personagem pelo NLA.

    - loop: repete até o fim da cena (`scene_end`, padrão: fim da cena).
    - hold: congela no quadro `hold` da ação (ex.: último quadro do "sit").
    - offset: começa a ação a partir desse quadro (pula o começo).
    """
    arm = _armature(holder)
    if not arm or not holder.get("action"):
        return
    act = bpy.data.actions[holder["action"]]
    ad = arm.animation_data or arm.animation_data_create()
    ad.action = None
    for tr in list(ad.nla_tracks):
        ad.nla_tracks.remove(tr)
    track = ad.nla_tracks.new()
    a0, a1 = act.frame_range
    strip = track.strips.new(act.name, int(start), act)
    if hold is not None:
        strip.action_frame_start = hold
        strip.action_frame_end = hold + 0.01
        strip.frame_end = (scene_end or bpy.context.scene.frame_end) + 1
        strip.extrapolation = "HOLD"
        return strip
    strip.action_frame_start = a0 + offset
    strip.action_frame_end = a1
    strip.scale = 1.0 / speed
    if loop:
        length = (a1 - a0 - offset) / speed
        end = (scene_end or bpy.context.scene.frame_end) - start + 1
        strip.repeat = max(1.0, end / max(length, 1))
    strip.extrapolation = "HOLD"
    return strip


def place(holder, x, y, z=0.0, face=None):
    """Posiciona o holder; `face` = ponto (x, y) pro qual ele olha."""
    holder.location = (x, y, z)
    if face is not None:
        d = Vector((face[0] - x, face[1] - y))
        # o modelo olha pra -Y com rotação 0
        holder.rotation_euler.z = math.atan2(d.x, -d.y)


def walk_path(holder, points, f0, f1, face_motion=True):
    """Desloca o holder por uma polilinha (x, y) de f0 a f1, em velocidade
    constante, virando pra direção do movimento."""
    segs = [Vector(b) - Vector(a) for a, b in zip(points[:-1], points[1:])]
    total = sum(s.length for s in segs) or 1.0
    f, acc = f0, 0.0
    for i, p in enumerate(points):
        frame = f0 + (f1 - f0) * acc / total
        holder.location = (p[0], p[1], holder.location.z)
        holder.keyframe_insert("location", frame=frame)
        if face_motion:
            s = segs[min(i, len(segs) - 1)]
            holder.rotation_euler.z = math.atan2(s.x, -s.y)
            holder.keyframe_insert("rotation_euler", index=2, frame=frame)
        if i < len(segs):
            acc += segs[i].length
    ad = holder.animation_data
    if ad and ad.action:
        try:
            curves = list(ad.action.fcurves)
        except AttributeError:
            curves = [fc for lay in ad.action.layers for st in lay.strips for bag in st.channelbags for fc in bag.fcurves]
        for fc in curves:
            for kp in fc.keyframe_points:
                kp.interpolation = "LINEAR"


def visible(ob, frames):
    """Liga/desliga o holder e tudo dentro dele: frames = [(quadro, bool)]."""
    objs = [ob] + list(ob.children_recursive)
    for o in objs:
        for f, on in frames:
            o.hide_render = not on
            o.hide_viewport = not on
            o.keyframe_insert("hide_render", frame=f)
            o.keyframe_insert("hide_viewport", frame=f)


def bone_world(holder, bone, frame):
    """Posição de mundo da cabeça de um osso num quadro (avaliando o NLA)."""
    arm = _armature(holder)
    sc = bpy.context.scene
    sc.frame_set(frame)
    bpy.context.view_layer.update()
    pb = arm.pose.bones.get(bone) or next(b for b in arm.pose.bones if bone in b.name)
    return arm.matrix_world @ pb.head


def sit_on(holder, seat, yaw, frame, hip_bone="Pelvis", drop=0.07):
    """Senta o personagem (já com `play(hold=...)` numa pose sentada) sobre o
    assento `seat` (x, y, z do topo do assento), virado pra `yaw`.

    Mede onde o quadril fica naquela pose e desloca o holder pra ele encostar
    no assento: a altura do assento da animação do Tripo não é a da cadeira.
    """
    holder.location = (seat[0], seat[1], 0.0)
    holder.rotation_euler = (0.0, 0.0, yaw)
    hip = bone_world(holder, hip_bone, frame)
    holder.location = (holder.location.x + (seat[0] - hip.x),
                       holder.location.y + (seat[1] - hip.y),
                       seat[2] + drop - hip.z)
    return holder
