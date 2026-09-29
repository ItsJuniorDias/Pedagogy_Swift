"""Montagem 2.5D no Blender — funções usadas pelos planos do curta.

Roda DENTRO do Blender (via MCP ou `blender -b -P`). Convenções:

- A câmera olha pra +Y. Profundidade = distância no eixo Y até a câmera.
- Cada camada é um plano com a imagem, sem luz (emissão), com alpha. Assim a
  cor sai igual à ilustração em qualquer motor de render.
- `fit_plane` dimensiona a camada pra cobrir o quadro inteiro naquela
  profundidade, com folga (`overscan`) pra câmera poder se mover.
- Tudo é recriável: `new_shot_scene` apaga e refaz a cena do plano.

    exec(open(".../blender_kit.py").read())
    sc = new_shot_scene("s01", seconds=13)
    layer(sc, "house/sky", depth=60)
"""

import math
import os

import bpy

ROOT = "/Users/alexandrejunior/Pedagogy_Swift/shorts/fox-and-the-north-wind"
LAYERS = ROOT + "/build/layers"
FPS = 24
RES = (1920, 1080)
LENS = 35.0
SENSOR = 36.0
CAM_Y = -10.0


def srgb_to_linear(c):
    c = c / 255
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


# ─── Cena ───────────────────────────────────────────────────────────────────

def new_shot_scene(shot_id, seconds, bg=(20, 28, 48)):
    """Cena nova e vazia pro plano, com câmera, fps, resolução e fundo."""
    # Cria a nova antes de apagar a antiga: o Blender não remove a última cena.
    sc = bpy.data.scenes.new(shot_id + "__new")
    bpy.context.window.scene = sc
    old = bpy.data.scenes.get(shot_id)
    if old:
        for ob in list(old.collection.all_objects):
            bpy.data.objects.remove(ob, do_unlink=True)
        bpy.data.scenes.remove(old)
    sc.name = shot_id
    sc.render.fps = FPS
    sc.frame_start = 1
    sc.frame_end = int(round(seconds * FPS))
    sc.render.resolution_x, sc.render.resolution_y = RES
    sc.render.resolution_percentage = 100
    sc.view_settings.view_transform = "Standard"

    world = bpy.data.worlds.get(f"World_{shot_id}") or bpy.data.worlds.new(f"World_{shot_id}")
    world.color = tuple(srgb_to_linear(v) for v in bg)
    world.use_nodes = True
    node = next(n for n in world.node_tree.nodes if n.type == "BACKGROUND")
    node.inputs[0].default_value = (*world.color, 1)
    sc.world = world

    cam_data = bpy.data.cameras.new(f"Cam_{shot_id}")
    cam_data.lens = LENS
    cam_data.sensor_width = SENSOR
    cam_data.clip_end = 500
    cam = bpy.data.objects.new(f"Cam_{shot_id}", cam_data)
    sc.collection.objects.link(cam)
    cam.location = (0, CAM_Y, 0)
    cam.rotation_euler = (math.radians(90), 0, 0)
    sc.camera = cam

    set_engine(sc)
    bpy.context.window.scene = sc
    return sc


def set_engine(sc, engine="BLENDER_EEVEE"):
    try:
        sc.render.engine = engine
    except TypeError as e:
        print("engine:", e)
    if sc.render.engine == "BLENDER_EEVEE":
        try:
            sc.eevee.taa_render_samples = 16
        except AttributeError:
            pass


# ─── Camadas ────────────────────────────────────────────────────────────────

def _image(layer_id):
    alpha = f"{LAYERS}/{layer_id}.alpha.png"
    path = alpha if os.path.exists(alpha) else f"{LAYERS}/{layer_id}.png"
    return bpy.data.images.load(path, check_existing=True)


MEMORY_BLUE = (0.45, 0.62, 1.0)   # tinta dos flashbacks


def _unlit_material(name, img, tint=None):
    """Imagem sem luz, com alpha. `tint` multiplica a cor (flashback azul)."""
    if tint:
        name += "_tint_" + "_".join(f"{c:.2f}" for c in tint)
    mat = bpy.data.materials.get(name)
    if mat:
        return mat
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    tex = nt.nodes.new("ShaderNodeTexImage")
    tex.image = img
    tex.interpolation = "Linear"
    em = nt.nodes.new("ShaderNodeEmission")
    tr = nt.nodes.new("ShaderNodeBsdfTransparent")
    mix = nt.nodes.new("ShaderNodeMixShader")
    color = tex.outputs["Color"]
    if tint:
        # Dessatura um pouco e multiplica pelo azul: parece lembrança, não noite.
        hsv = nt.nodes.new("ShaderNodeHueSaturation")
        hsv.inputs["Saturation"].default_value = 0.35
        nt.links.new(color, hsv.inputs["Color"])
        mul = nt.nodes.new("ShaderNodeMix")
        mul.data_type = "RGBA"
        mul.blend_type = "MULTIPLY"
        mul.inputs["Factor"].default_value = 1.0
        nt.links.new(hsv.outputs["Color"], mul.inputs["A"])
        mul.inputs["B"].default_value = (*tint, 1)
        color = mul.outputs["Result"]
    nt.links.new(color, em.inputs["Color"])
    nt.links.new(tex.outputs["Alpha"], mix.inputs[0])
    nt.links.new(tr.outputs[0], mix.inputs[1])
    nt.links.new(em.outputs[0], mix.inputs[2])
    nt.links.new(mix.outputs[0], out.inputs["Surface"])
    # Blender 4.2+: "BLENDED" dá borda suave no alpha; versões antigas usam blend_method.
    for attr, val in (("surface_render_method", "BLENDED"), ("blend_method", "BLEND")):
        try:
            setattr(mat, attr, val)
            break
        except (AttributeError, TypeError):
            continue
    return mat


def _plane(name, w, h):
    me = bpy.data.meshes.new(name)
    me.from_pydata([(-w / 2, 0, -h / 2), (w / 2, 0, -h / 2), (w / 2, 0, h / 2), (-w / 2, 0, h / 2)], [], [(0, 1, 2, 3)])
    uv = me.uv_layers.new()
    for loop, co in zip(uv.data, [(0, 0), (1, 0), (1, 1), (0, 1)]):
        loop.uv = co
    return me


def frame_width_at(depth):
    """Largura visível do quadro a `depth` metros da câmera."""
    return depth * SENSOR / LENS


def layer(sc, layer_id, depth, overscan=1.25, x=0.0, z=0.0, width=None, name=None,
          tint=None, flip=False):
    """Camada de cenário a `depth` da câmera, cobrindo o quadro com folga.

    `width` fixa a largura em metros (pra objetos e personagens); sem ela o
    plano cobre o quadro inteiro naquela profundidade × overscan.
    """
    img = _image(layer_id)
    iw, ih = img.size
    w = width if width else frame_width_at(depth) * overscan
    h = w * ih / iw
    name = name or f"{sc.name}_{layer_id.replace('/', '_')}"
    ob = bpy.data.objects.new(name, _plane(name, w, h))
    ob.data.materials.append(_unlit_material("M_" + layer_id.replace("/", "_"), img, tint))
    sc.collection.objects.link(ob)
    ob.location = (x, CAM_Y + depth, z)
    if flip:
        ob.scale.x = -1
    return ob


def puppet(sc, layer_id, depth, height, x=0.0, floor=0.0, name=None, tint=None,
           flip=False, breathe=True):
    """Personagem recortado com a base da imagem em `floor` e `height` metros de altura.

    `breathe` dá uma respiração sutil (escala vertical ±0,8%, ciclo de ~3,5 s)
    ancorada na base, pra ninguém parecer congelado.
    """
    img = _image(layer_id)
    iw, ih = img.size
    w = height * iw / ih
    ob = layer(sc, layer_id, depth, width=w, x=x, name=name, tint=tint, flip=flip)
    # Origem na base da imagem: escala e respiração não tiram o pé do chão.
    for v in ob.data.vertices:
        v.co.z += height / 2
    ob.location.z = floor
    if breathe:
        sway(ob, "scale", 2, 0.008, 3.5, phase=(sum(map(ord, ob.name)) % 628) / 100)
    return ob


# ─── Visibilidade e objetos ─────────────────────────────────────────────────

def visible(ob, frames):
    """Liga/desliga o objeto: frames = [(quadro, True/False), ...], em degrau."""
    for f, on in frames:
        ob.hide_render = not on
        ob.hide_viewport = not on
        ob.keyframe_insert("hide_render", frame=f)
        ob.keyframe_insert("hide_viewport", frame=f)
    for fc in _fcurves(ob):
        if fc.data_path in ("hide_render", "hide_viewport"):
            for kp in fc.keyframe_points:
                kp.interpolation = "CONSTANT"


def pop_in(ob, frame, dur=8):
    """Aparece em `frame` com um pequeno salto de escala (0 → 1,08 → 1)."""
    s = tuple(ob.scale)
    key(ob, "scale", [(frame, (0.001, 0.001, 0.001)),
                      (frame + dur * 0.7, tuple(v * 1.08 for v in s)),
                      (frame + dur, s)])
    visible(ob, [(1, False), (frame, True)])


def tracks(sc, start, end, n=8, size=0.18, name="Tracks", tint=None):
    """Pegadas: pares de elipses escuras deitadas no chão, de `start` a `end` (x, y, z)."""
    color = (0.12, 0.16, 0.28)
    if tint:
        color = tuple(c * t for c, t in zip(color, tint))
    mat = bpy.data.materials.get("M_" + name) or bpy.data.materials.new("M_" + name)
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    em = nt.nodes.new("ShaderNodeEmission")
    em.inputs["Color"].default_value = (*color, 1)
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    nt.links.new(em.outputs[0], out.inputs["Surface"])
    obs = []
    for i in range(n):
        t = i / max(1, n - 1)
        x = start[0] + (end[0] - start[0]) * t + (0.12 if i % 2 else -0.12)
        y = start[1] + (end[1] - start[1]) * t
        z = start[2] + (end[2] - start[2]) * t
        bpy.ops.mesh.primitive_circle_add(vertices=16, radius=size, fill_type="NGON")
        ob = bpy.context.active_object
        for c in ob.users_collection:
            c.objects.unlink(ob)
        sc.collection.objects.link(ob)
        ob.name = f"{name}_{i}"
        ob.location = (x, CAM_Y + y, z)
        ob.scale = (0.6, 1.8, 1.0)          # elipse deitada no chão; alongada em Y porque a câmera a vê quase de lado
        ob.data.materials.append(mat)
        obs.append(ob)
    return obs


def glow_orb(sc, loc, radius=0.25, color=(1.0, 0.85, 0.45), name="Orb"):
    """Luz flutuante: esfera de emissão forte + halo (bloom do EEVEE)."""
    bpy.ops.mesh.primitive_uv_sphere_add(radius=radius, segments=24, ring_count=12)
    ob = bpy.context.active_object
    for c in ob.users_collection:
        c.objects.unlink(ob)
    sc.collection.objects.link(ob)
    ob.name = f"{sc.name}_{name}"
    ob.location = (loc[0], CAM_Y + loc[1], loc[2])
    mat = bpy.data.materials.new("M_" + ob.name)
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    em = nt.nodes.new("ShaderNodeEmission")
    em.inputs["Color"].default_value = (*color, 1)
    em.inputs["Strength"].default_value = 6.0
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    nt.links.new(em.outputs[0], out.inputs["Surface"])
    ob.data.materials.append(mat)
    return ob


# ─── Movimento ──────────────────────────────────────────────────────────────

def key(ob, path, frames_values, interp="BEZIER", index=-1):
    """Keyframes: [(quadro, valor), ...]. Valor escalar pra um índice, tupla pro vetor."""
    for f, v in frames_values:
        if index >= 0:
            getattr(ob, path)[index] = v
            ob.keyframe_insert(path, index=index, frame=f)
        else:
            setattr(ob, path, v)
            ob.keyframe_insert(path, frame=f)
    if ob.animation_data and ob.animation_data.action:
        for fc in _fcurves(ob):
            for kp in fc.keyframe_points:
                kp.interpolation = interp


def _fcurves(ob):
    act = ob.animation_data.action
    try:
        return list(act.fcurves)
    except AttributeError:
        # Blender 5 (actions em camadas): curvas ficam nos channelbags
        out = []
        for lay in act.layers:
            for strip in lay.strips:
                for bag in strip.channelbags:
                    out.extend(bag.fcurves)
        return out


def sway(ob, path, index, amp, period_s, phase=0.0):
    """Oscilação contínua (driver), pra respiração, balanço de galho, etc."""
    base = getattr(ob, path)[index]
    fc = ob.driver_add(path, index)
    fc.driver.type = "SCRIPTED"
    fc.driver.expression = f"{base:.4f} + {amp:.4f}*sin(2*pi*frame/{period_s * FPS:.2f} + {phase:.3f})"
    for m in list(fc.modifiers):
        fc.modifiers.remove(m)


# ─── Neve ───────────────────────────────────────────────────────────────────

def snow(sc, depth, count=400, drift=1.0, size=0.06, name="Snow"):
    """Flocos caindo numa faixa de profundidade: partículas de uma esfera branca sem luz."""
    w = frame_width_at(depth) * 1.6
    h = w * 0.7
    emitter_me = _plane(name + "_emitter", w, w * 0.5)
    emitter = bpy.data.objects.new(name + "_emitter", emitter_me)
    sc.collection.objects.link(emitter)
    emitter.location = (0, CAM_Y + depth, h / 2 + 1)
    emitter.rotation_euler = (math.radians(90), 0, 0)   # plano horizontal no alto
    # Não usar hide_render: esconder o emissor esconde as partículas junto.
    emitter.show_instancer_for_render = False
    emitter.show_instancer_for_viewport = False

    bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=1, radius=size)
    flake = bpy.context.active_object
    flake.name = name + "_flake"
    for c in flake.users_collection:
        c.objects.unlink(flake)
    sc.collection.objects.link(flake)
    flake.location = (0, 0, -1000)
    white = bpy.data.materials.get("M_snow") or bpy.data.materials.new("M_snow")
    white.use_nodes = True
    nt = white.node_tree
    nt.nodes.clear()
    em = nt.nodes.new("ShaderNodeEmission")
    em.inputs["Color"].default_value = (0.95, 0.95, 0.9, 1)
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    nt.links.new(em.outputs[0], out.inputs["Surface"])
    flake.data.materials.append(white)

    mod = emitter.modifiers.new(name, "PARTICLE_SYSTEM")
    ps = mod.particle_system.settings
    ps.count = count
    ps.frame_start = -200                     # já está nevando no quadro 1
    ps.frame_end = sc.frame_end
    ps.lifetime = 400
    ps.emit_from = "FACE"
    ps.normal_factor = 0
    ps.factor_random = 0.2
    ps.effector_weights.gravity = 0.02
    ps.object_align_factor = (drift * 0.3, 0, -0.6)
    ps.render_type = "OBJECT"
    ps.instance_object = flake
    ps.particle_size = 1
    ps.size_random = 0.6
    ps.use_rotations = False
    # O cache começa no frame_start da cena; sem isso, o que foi "emitido antes"
    # não é simulado e o plano abre sem neve.
    cache = mod.particle_system.point_cache
    cache.frame_start = int(ps.frame_start)
    cache.frame_end = int(sc.frame_end)
    return emitter
