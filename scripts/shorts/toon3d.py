"""Kit toon 3D — o visual "diorama" dos curtas em 3D.

Roda dentro do Blender (GUI via MCP ou `blender -b -P`). Tudo é por código e
recriável. O visual:

- `toon(name, color)`: sombreamento em faixas chapadas (Shader to RGB →
  ColorRamp constante). A luz real da cena decide a faixa; a cor final sai
  exata, sem degradê — como tinta chapada das capas.
- `outline(ob)`: contorno preto por casco invertido (Solidify com normais
  invertidas + material que só mostra a face de trás). Barato no EEVEE.
- `render_setup`, `sky`, `moonlight`, `warm_light`: cena, céu em degradê e luzes.

Convenção de cor: tuplas sRGB 0–255 (como nas ilustrações); o kit converte.
"""

import math

import bpy


def lin(c):
    """sRGB 0–255 → linear 0–1 (o que o Blender espera nos nós)."""
    def f(v):
        v = v / 255
        return v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4
    return (f(c[0]), f(c[1]), f(c[2]), 1.0)


def shade(c, k):
    """Escurece (k<1) ou clareia (k>1) uma cor sRGB 0–255."""
    return tuple(max(0, min(255, int(v * k))) for v in c[:3])


# ─── Materiais ──────────────────────────────────────────────────────────────

def toon(name, color, shadow=0.55, light=1.12, bands=(0.28, 0.62), emission=0.0,
         image=None, backface=False, shadow_tint=(1.0, 1.0, 1.0), light_tint=(1.0, 1.0, 1.0)):
    """Material toon de 3 faixas: sombra / base / luz.

    `color` sRGB 0–255, ou `image` (bpy.types.Image) pra modelos texturizados:
    a textura é multiplicada pelas faixas de luz, então o Tripo continua
    com a pintura dele, só que com luz chapada.
    `emission` > 0 faz o material brilhar por conta própria (janela acesa, fogo).
    `shadow_tint` / `light_tint`: multiplicam a faixa de sombra / de luz (RGB).
    As faixas saem de um cinza, então a cor da lâmpada não tinge o toon;
    é aqui que a luz do fogo vira quente e a sombra da noite vira fria.
    """
    mat = bpy.data.materials.get(name)
    if mat:
        return mat
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    diffuse = nt.nodes.new("ShaderNodeBsdfDiffuse")
    diffuse.inputs["Color"].default_value = (1, 1, 1, 1)
    to_rgb = nt.nodes.new("ShaderNodeShaderToRGB")
    nt.links.new(diffuse.outputs[0], to_rgb.inputs[0])
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.interpolation = "CONSTANT"
    el = ramp.color_ramp.elements
    el[0].position, el[0].color = 0.0, tuple(shadow * t for t in shadow_tint) + (1,)
    el[1].position, el[1].color = bands[0], (1, 1, 1, 1)
    extra = el.new(bands[1])
    extra.color = tuple(light * t for t in light_tint) + (1,)
    bw = nt.nodes.new("ShaderNodeRGBToBW")
    nt.links.new(to_rgb.outputs["Color"], bw.inputs[0])
    nt.links.new(bw.outputs[0], ramp.inputs["Fac"])

    mul = nt.nodes.new("ShaderNodeMix")
    mul.data_type = "RGBA"
    mul.blend_type = "MULTIPLY"
    mul.inputs["Factor"].default_value = 1.0
    nt.links.new(ramp.outputs["Color"], mul.inputs["B"])
    if image is not None:
        tex = nt.nodes.new("ShaderNodeTexImage")
        tex.image = image
        nt.links.new(tex.outputs["Color"], mul.inputs["A"])
    else:
        mul.inputs["A"].default_value = lin(color)

    em = nt.nodes.new("ShaderNodeEmission")
    nt.links.new(mul.outputs["Result"], em.inputs["Color"])
    em.inputs["Strength"].default_value = 1.0
    if emission:
        glow = nt.nodes.new("ShaderNodeEmission")
        glow.inputs["Color"].default_value = lin(color)
        glow.inputs["Strength"].default_value = emission
        add = nt.nodes.new("ShaderNodeAddShader")
        nt.links.new(em.outputs[0], add.inputs[0])
        nt.links.new(glow.outputs[0], add.inputs[1])
        nt.links.new(add.outputs[0], out.inputs["Surface"])
    else:
        nt.links.new(em.outputs[0], out.inputs["Surface"])
    mat.use_backface_culling = backface
    return mat


def ink(name="Ink", color=(12, 12, 16)):
    """Material do contorno: preto, só visível pelas costas (casco invertido)."""
    mat = bpy.data.materials.get(name)
    if mat:
        return mat
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    em = nt.nodes.new("ShaderNodeEmission")
    em.inputs["Color"].default_value = lin(color)
    # O casco envolve o objeto: se projetasse sombra, o objeto inteiro ficaria
    # na sombra dele mesmo (e perderia as faixas). Pra raios de sombra, some.
    path = nt.nodes.new("ShaderNodeLightPath")
    clear = nt.nodes.new("ShaderNodeBsdfTransparent")
    mix = nt.nodes.new("ShaderNodeMixShader")
    nt.links.new(path.outputs["Is Shadow Ray"], mix.inputs[0])
    nt.links.new(em.outputs[0], mix.inputs[1])
    nt.links.new(clear.outputs[0], mix.inputs[2])
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    nt.links.new(mix.outputs[0], out.inputs["Surface"])
    mat.use_backface_culling = True
    for attr, val in (("use_transparent_shadow", True), ("shadow_method", "NONE")):
        try:
            setattr(mat, attr, val)
        except (AttributeError, TypeError):
            pass
    return mat


def outline(ob, thickness=0.025):
    """Contorno preto em volta do objeto (casco invertido).

    `thickness` em metros no espaço do objeto; ~2–3 cm lê bem de 5–15 m.
    """
    if ob.type != "MESH":
        return
    mats = ob.data.materials
    if "Ink" not in [m.name for m in mats if m]:
        mats.append(ink())
    mod = ob.modifiers.get("Outline") or ob.modifiers.new("Outline", "SOLIDIFY")
    mod.thickness = thickness
    mod.offset = 1.0
    mod.use_flip_normals = True
    mod.use_rim = False
    mod.material_offset = len(mats) - 1
    mod.material_offset_rim = len(mats) - 1


def assign(ob, mat, outline_thickness=0.025):
    """Material toon + contorno, de uma vez."""
    ob.data.materials.clear()
    ob.data.materials.append(mat)
    if outline_thickness:
        outline(ob, outline_thickness)
    return ob


# ─── Cena, céu e luz ────────────────────────────────────────────────────────

def render_setup(sc, width=1280, height=720, fps=24):
    sc.render.resolution_x, sc.render.resolution_y = width, height
    sc.render.resolution_percentage = 100
    sc.render.fps = fps
    try:
        sc.render.engine = "BLENDER_EEVEE"
    except TypeError:
        pass
    sc.view_settings.view_transform = "Standard"
    try:
        sc.eevee.taa_render_samples = 16
    except AttributeError:
        pass
    sc.render.film_transparent = False


def sky(sc, top=(8, 14, 38), horizon=(34, 58, 104), name="Sky"):
    """Céu em degradê vertical (topo → horizonte), sem sol: noite ártica."""
    world = bpy.data.worlds.get(name) or bpy.data.worlds.new(name)
    world.use_nodes = True
    nt = world.node_tree
    nt.nodes.clear()
    coord = nt.nodes.new("ShaderNodeTexCoord")
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    nt.links.new(coord.outputs["Generated"], sep.inputs[0])
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].position = 0.5
    ramp.color_ramp.elements[0].color = lin(horizon)
    ramp.color_ramp.elements[1].position = 0.85
    ramp.color_ramp.elements[1].color = lin(top)
    nt.links.new(sep.outputs["Z"], ramp.inputs["Fac"])
    bg = nt.nodes.new("ShaderNodeBackground")
    nt.links.new(ramp.outputs["Color"], bg.inputs["Color"])
    out = nt.nodes.new("ShaderNodeOutputWorld")
    nt.links.new(bg.outputs[0], out.inputs["Surface"])
    sc.world = world
    return world


def _light(sc, name, kind, color, energy, loc, rot=(0, 0, 0)):
    data = bpy.data.lights.new(name, kind)
    data.color = lin(color)[:3]
    data.energy = energy
    ob = bpy.data.objects.new(name, data)
    sc.collection.objects.link(ob)
    ob.location = loc
    ob.rotation_euler = rot
    return ob


def moonlight(sc, energy=3.0, color=(170, 190, 255), angle=(55, 0, 125)):
    """Luz da lua: sol frio, de cima e de lado/por trás em relação a uma câmera em -Y
    (luz vinda da câmera acende tudo por igual e as faixas do toon somem)."""
    ob = _light(sc, "Moon", "SUN", color, energy, (0, 0, 20),
                tuple(math.radians(a) for a in angle))
    ob.data.angle = math.radians(2)
    return ob


def warm_light(sc, loc, energy=300.0, color=(255, 170, 90), radius=0.3, name="Warm"):
    """Luz quente pontual: janela acesa, fogão, lareira."""
    ob = _light(sc, name, "POINT", color, energy, loc)
    ob.data.shadow_soft_size = radius
    return ob


def camera(sc, loc, look_at, lens=35.0, name="Cam"):
    data = bpy.data.cameras.new(name)
    data.lens = lens
    data.clip_end = 1000
    ob = bpy.data.objects.new(name, data)
    sc.collection.objects.link(ob)
    ob.location = loc
    aim(ob, look_at)
    sc.camera = ob
    return ob


def aim(ob, target):
    """Aponta o objeto (câmera/luz) pra um ponto."""
    from mathutils import Vector
    d = Vector(target) - Vector(ob.location)
    ob.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()
