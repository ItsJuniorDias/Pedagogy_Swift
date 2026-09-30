"""Props 3D do curta "The Fox and the North Wind" (fox-3d): mala, colar, rastros.

Roda dentro do Blender (`blender -b -P ...`). Tudo por código (bpy/bmesh),
determinístico (sementes fixas), no visual do kit `toon3d`: faixas chapadas,
contorno preto por casco invertido, emissão só no que brilha.

ENTRADA ÚNICA (como os outros sets):

    import sys; sys.path.insert(0, "/Users/alexandrejunior/Pedagogy_Swift/scripts/shorts")
    from sets3d import props as P
    A = P.build(sc, which=("suitcase", "necklace", "tracks"),
                suitcase=dict(at=(3, -1, 0), yaw=70),
                necklace=dict(at=(0, 0.6, 0.18), scale=1.3, drape=-0.07),
                tracks=dict(start=(4, -6), end=(0, 0.2), count=12, face=cam, animate=(1, 90)))
    A["suitcase.grip"]      # → (x, y, z) em mundo, onde vai a mão da Nell
    A["_roots"]["suitcase"] # → o Empty raiz (mover/girar/escalar leva o prop inteiro)

API fina (cada função nasce na origem, base em z=0, "frente" pra -Y, e devolve o
Empty RAIZ; `anchors(root)` relê as âncoras em coordenadas de MUNDO):

    suitcase(sc, ...)              mala de couro com alça trolley (padrão) ou correia (k01)
    necklace(sc, ...)              colar de ouro com pingente, na neve / no degrau (k05)
    fox_tracks(sc, start, end, count, face=cam, ...)   trilha de pegadas em pares (k04, k07, k09)
    animate_tracks(root, f0, f1)   as pegadas aparecem pata a pata (raposa andando)
    puffs_for_tracks(sc, root, f0, f1)  um pufe de neve a cada N pegadas, no mesmo tempo
    track_pairs(root)              as pegadas de uma trilha, em ordem
    snow_puff(sc, loc, frame=...)  pufe de neve de uma pisada
    anchors(root)                  dict nome → (x, y, z) em mundo

Unidades: 1 = 1 m, Z pra cima, chão em z=0. Nada é baixado, nada de add-on.
"""

import math
import random
import sys

import bmesh
import bpy
from mathutils import Matrix, Quaternion, Vector

_KIT = "/Users/alexandrejunior/Pedagogy_Swift/scripts/shorts"
if _KIT not in sys.path:
    sys.path.insert(0, _KIT)
import toon3d as T  # noqa: E402

# ─── Paleta (sRGB 0–255) ────────────────────────────────────────────────────
LEATHER = (124, 74, 44)        # couro da mala
LEATHER_DARK = (78, 46, 30)    # cintas, cantoneiras, alça, pegador
BRASS = (214, 172, 74)         # fechos, pezinhos, colares da haste
STEEL = (150, 154, 166)        # hastes do trolley
RUBBER = (40, 38, 44)          # rodinhas
GOLD = (232, 180, 58)          # corrente
GOLD_GLOW = (255, 216, 112)    # borda/estrela do pingente (emite)
GEM = (36, 60, 150)            # pedrinha azul do pingente
INK_FLAT = (12, 12, 16)        # "nanquim" chapado (silhueta do colar)
SNOW = (236, 240, 248)
PRINT = (46, 66, 116)          # fundo da pegada: azul escuro das ilustrações
PUFF = (212, 224, 244)         # neve espirrada: um tom abaixo da neve do chão


# ─── Utilidades ─────────────────────────────────────────────────────────────

def _collection(sc):
    """Coleção "Props" desta cena (uma por cena, pra não misturar cenas)."""
    for c in sc.collection.children:
        if c.get("props_of") == sc.name:
            return c
    c = bpy.data.collections.new("Props")
    c["props_of"] = sc.name
    sc.collection.children.link(c)
    return c


def _empty(sc, name, parent=None, loc=(0, 0, 0), size=0.05, kind="PLAIN_AXES"):
    ob = bpy.data.objects.new(name, None)
    ob.empty_display_type = kind
    ob.empty_display_size = size
    ob.location = loc
    _collection(sc).objects.link(ob)
    if parent is not None:
        ob.parent = parent
    return ob


def _anchor(sc, root, key, loc, parent=None):
    """Âncora: Empty filho (de `parent` ou da raiz), invisível no render."""
    ob = _empty(sc, f"{root.name}.{key}", parent or root, loc, size=0.03, kind="SPHERE")
    ob["anchor"] = key
    ob.hide_render = True
    return ob


def _mesh_ob(sc, name, bm, parent=None, loc=(0, 0, 0), smooth=False, warp=None):
    if warp is not None:
        for v in bm.verts:
            v.co = warp(v.co)
    if smooth:
        for f in bm.faces:
            f.smooth = True
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(name, me)
    ob.location = loc
    _collection(sc).objects.link(ob)
    if parent is not None:
        ob.parent = parent
    return ob


def _world_matrix(ob):
    """Matriz de mundo sem depender do depsgraph (vale pra qualquer cena)."""
    m = ob.matrix_basis.copy()
    while ob.parent is not None:
        m = ob.parent.matrix_basis @ ob.matrix_parent_inverse @ m
        ob = ob.parent
    return m


def anchors(root):
    """Todas as âncoras do prop `root` → {nome: (x, y, z)} em coordenadas de mundo."""
    out = {}

    def walk(ob):
        for ch in ob.children:
            if "anchor" in ch:
                p = _world_matrix(ch).translation
                out[ch["anchor"]] = (round(p.x, 4), round(p.y, 4), round(p.z, 4))
            walk(ch)

    walk(root)
    return out


def _fcurves(ob):
    """F-curves do objeto nas duas APIs (Action.fcurves antiga / camadas do 4.4+)."""
    ad = ob.animation_data
    if not ad or not ad.action:
        return []
    act = ad.action
    if hasattr(act, "fcurves"):
        return list(act.fcurves)
    out = []
    for layer in act.layers:
        for strip in layer.strips:
            for bag in strip.channelbags:
                out.extend(bag.fcurves)
    return out


def _set_interp(ob, kind="CONSTANT", path=None):
    for fc in _fcurves(ob):
        if path is None or fc.data_path == path:
            for kp in fc.keyframe_points:
                kp.interpolation = kind


# ─── Geometria (bmesh) ──────────────────────────────────────────────────────

def _box(bm, size, center=(0, 0, 0), bevel=0.0, segments=1):
    """Caixa `size` (x, y, z) centrada em `center`, com quinas chanfradas."""
    mtx = Matrix.Translation(center) @ Matrix.Diagonal((size[0], size[1], size[2], 1.0))
    verts = bmesh.ops.create_cube(bm, size=1.0, matrix=mtx)["verts"]
    if bevel > 0:
        edges = list({e for v in verts for e in v.link_edges})
        bmesh.ops.bevel(bm, geom=edges, offset=bevel, segments=segments, profile=0.5,
                        affect="EDGES", clamp_overlap=True)
    return verts


def _cylinder(bm, radius, depth, center=(0, 0, 0), segments=16, rot=None):
    mtx = Matrix.Translation(center)
    if rot is not None:
        mtx = mtx @ rot
    return bmesh.ops.create_cone(bm, cap_ends=True, cap_tris=False, segments=segments,
                                 radius1=radius, radius2=radius, depth=depth,
                                 matrix=mtx)["verts"]


def _tube(bm, pts, radius, sides=6, closed=False, cap=False):
    """Tubo ao longo de uma polilinha (moldura por transporte paralelo, sem torção).

    `radius` número = seção redonda; (r_n, r_b) = seção oval/chata: r_n na direção
    da "normal" (≈ Z pra curvas deitadas), r_b na lateral. Fita chata = (fino, largo).
    """
    rn, rb = (radius, radius) if isinstance(radius, (int, float)) else radius
    pts = [Vector(p) for p in pts]
    n = len(pts)
    tans = []
    for i in range(n):
        if closed:
            t = pts[(i + 1) % n] - pts[(i - 1) % n]
        else:
            t = pts[min(i + 1, n - 1)] - pts[max(i - 1, 0)]
        tans.append(t.normalized())
    ref = Vector((0, 0, 1)) if abs(tans[0].z) < 0.9 else Vector((1, 0, 0))
    nrm = (ref - tans[0] * ref.dot(tans[0])).normalized()
    rings = []
    for i in range(n):
        if i:
            nrm = tans[i - 1].rotation_difference(tans[i]) @ nrm
            nrm = (nrm - tans[i] * nrm.dot(tans[i])).normalized()
        bi = tans[i].cross(nrm)
        rings.append([bm.verts.new(pts[i] + rn * math.cos(a) * nrm + rb * math.sin(a) * bi)
                      for a in (2 * math.pi * k / sides for k in range(sides))])
    faces = []
    for i in range(n if closed else n - 1):
        r0, r1 = rings[i], rings[(i + 1) % n]
        for k in range(sides):
            k1 = (k + 1) % sides
            faces.append(bm.faces.new((r0[k], r0[k1], r1[k1], r1[k])))
    if cap and not closed:
        faces.append(bm.faces.new(list(reversed(rings[0]))))
        faces.append(bm.faces.new(rings[-1]))
    return faces


def _stadium(length, width, n_arc=5):
    """Contorno de um elo (retângulo de pontas redondas) no plano XY, eixo longo em X."""
    r = width / 2
    c = length / 2 - r
    pts = []
    for k in range(n_arc + 1):  # ponta +X
        a = -math.pi / 2 + math.pi * k / n_arc
        pts.append((c + r * math.cos(a), r * math.sin(a), 0))
    for k in range(n_arc + 1):  # ponta -X
        a = math.pi / 2 + math.pi * k / n_arc
        pts.append((-c + r * math.cos(a), r * math.sin(a), 0))
    return pts


# ─── Mala ───────────────────────────────────────────────────────────────────

def suitcase(sc, name="Suitcase", tilt=30.0, strap_angle=35.0, ink=0.016,
             handle_style="trolley", strap_yaw=0.0, handle_len=0.38, sink=0.004):
    """Mala vintage de couro marrom, 0.52 × 0.22 × 0.36 m, cintas, cantoneiras e fechos.

    Nasce na origem (centro da base em z=0 quando tilt=0), frente (fechos) pra -Y.
    A mala ANDA pra +X local: gire a raiz em Z pra alinhar +X com a caminhada da Nell.

    handle_style "trolley" (padrão, como layers/nell/walk-suitcase.png): duas hastes
                 de aço saem do topo, na ponta +X, e sobem `handle_len` m ao longo do
                 eixo da mala até uma barra-T (o pegador). Rodinhas na quina de baixo +X,
                 pezinhos de latão na -X.
                 tilt = graus que o TOPO tomba pra +X (pra mão), girando sobre o eixo
                 das rodinhas, que ficam sempre no chão. 30 = puxada (padrão), 0 = em pé.
                 Com tilt=30: pegador a ~0.67 m do chão, bom pra mão de uma menina de
                 1.35 m com o braço um pouco pra trás.
                 strap_yaw = graus: gira a mala inteira em torno do eixo vertical que
                 passa pelas rodinhas (o pegador vai pro lado, as rodas ficam).
                 Útil pra levar o pegador até a mão da Nell em A-pose (~0.3 m pro lado).
    handle_style "strap" (antigo): correia de couro com leve barriga (catenária) e laço
                 na ponta, presa na lateral +X. tilt levanta a ponta +X girando sobre a
                 quina arredondada de baixo -X (~10–15 = arrastada); strap_angle = graus
                 da correia sobre a horizontal (em mundo); strap_yaw gira a correia pro
                 lado. O Empty `<name>.strap` é o pivô dela.
    ink          contorno do corpo (m). 0.016 lê até ~6–8 m em 640×360. Com a câmera a
                 mais de 8 m (k01 plano geral) use ink=0.022. Os detalhes usam frações
                 (tampa/cintas/cantoneiras 0.55, latão 0.45, hastes/alças 0.5).
    sink         quanto a mala afunda na neve (m).

    Âncoras (`anchors(root)`, mundo):
        grip       centro do pegador: barra-T (trolley) ou laço da correia (strap)
        strap_base onde a haste/correia sai da mala
        handle     topo da alça de mão em cima da tampa (pra carregar)
        top        centro da tampa
        front      centro da face da frente (-Y), pra mirar câmera
        drag_edge  ponto de contato com o chão, sob as rodinhas (trolley) ou sob a quina
                   arrastada (strap). Fica em z=0 com qualquer tilt/strap_yaw: é por
                   onde a mala "encosta" no caminho.
    """
    W, D, H = 0.52, 0.22, 0.36
    trolley = handle_style != "strap"
    leather = T.toon("PropLeather", LEATHER, shadow=0.6, light=1.18)
    dark = T.toon("PropLeatherDark", LEATHER_DARK, shadow=0.6, light=1.22)
    brass = T.toon("PropBrass", BRASS, shadow=0.62, light=1.25)

    # Espaço "da mala": centro da base na origem, z pra cima. Pivô do tilt:
    if trolley:
        zb = 0.014                               # rodinhas/pezinhos erguem o corpo
        Rw = 0.028
        axle = Vector((W / 2 - 0.016, 0, Rw - sink - zb))    # eixo das rodinhas
        piv_root = Vector((axle.x, 0, Rw - sink))
    else:
        zb = 0.0
        # Centro do arco da cantoneira de baixo -X (chanfro 0.026): girando em volta
        # dele, a quina arredondada rola no chão e a mala não flutua com o tilt.
        axle = Vector((-W / 2 + 0.020, 0, 0.021))
        piv_root = Vector((axle.x, 0, axle.z - sink))
    root = _empty(sc, name, size=0.3)
    yaw_e = _empty(sc, f"{name}.yaw", root, (piv_root.x, 0, 0), size=0.06)
    if trolley:
        yaw_e.rotation_euler.z = math.radians(strap_yaw)
    pivot = _empty(sc, f"{name}.tilt", yaw_e, (0, 0, piv_root.z), size=0.08)
    pivot.rotation_euler.y = math.radians(tilt) if trolley else -math.radians(tilt)
    off = tuple(-axle)   # peças modeladas no espaço da mala → deslocadas pro pivô

    def part(label, build, mat, thick, smooth=False, parent=None, loc=off):
        bm = bmesh.new()
        build(bm)
        ob = _mesh_ob(sc, f"{name}.{label}", bm, parent or pivot, loc, smooth)
        T.assign(ob, mat, thick)
        return ob

    part("body", lambda bm: _box(bm, (W, D, H), (0, 0, H / 2), 0.026, 2), leather, ink)
    # Tampa: friso escuro em volta, a ~3/4 da altura.
    part("lid", lambda bm: _box(bm, (W + 0.008, D + 0.008, 0.02), (0, 0, 0.27), 0.008, 1),
         dark, ink * 0.55)

    def belts(bm):
        for x in (-0.14, 0.14):
            _box(bm, (0.042, D + 0.010, H + 0.010), (x, 0, H / 2), 0.03, 2)

    part("belts", belts, dark, ink * 0.55)

    def caps(bm):  # cantoneiras nas 4 quinas (vistas de frente)
        for sx in (-1, 1):
            for z in (0.028, H - 0.028):
                _box(bm, (0.066, D + 0.008, 0.066), (sx * (W / 2 - 0.027), 0, z), 0.026, 2)

    part("caps", caps, dark, ink * 0.55)

    def handle(bm):
        pts = []
        for k in range(9):
            a = math.pi * k / 8
            pts.append((-0.085 * math.cos(a), 0, H + 0.004 + 0.054 * math.sin(a) ** 0.6))
        _tube(bm, pts, 0.013, sides=6, cap=True)

    part("handle", handle, dark, ink * 0.5, smooth=True)

    x_rod = W / 2 - 0.035

    def metal(bm):
        for x in (-0.085, 0.085):                       # suportes da alça
            _box(bm, (0.032, 0.04, 0.016), (x, 0, H + 0.005), 0.004)
        for x in (-0.14, 0.14):                          # fivelas das cintas
            _box(bm, (0.052, 0.012, 0.04), (x, -D / 2 - 0.009, 0.19), 0.004)
        _box(bm, (0.064, 0.014, 0.046), (0, -D / 2 - 0.007, 0.27), 0.005)  # fecho central
        if trolley:
            for y in (-0.065, 0.065):                    # colares onde as hastes entram
                _box(bm, (0.034, 0.03, 0.016), (x_rod, y, H + 0.006), 0.004)
            for y in (-(D / 2 - 0.045), D / 2 - 0.045):  # pezinhos do lado -X
                hz = zb + sink + 0.004
                _box(bm, (0.03, 0.03, hz), (-W / 2 + 0.05, y, 0.004 - hz / 2), 0.004)
        else:
            _box(bm, (0.014, 0.044, 0.056), (W / 2 + 0.007, 0, 0.26), 0.004)  # rebite

    part("brass", metal, brass, ink * 0.45)

    if trolley:
        steel = T.toon("PropSteel", STEEL, shadow=0.6, light=1.2)
        rubber = T.toon("PropRubber", RUBBER, shadow=0.7, light=1.4)
        top_z = H + handle_len

        def rods(bm):
            for y in (-0.065, 0.065):
                _tube(bm, [(x_rod, y, H - 0.01), (x_rod, y, top_z)], 0.008, sides=6, cap=True)

        part("rods", rods, steel, ink * 0.5, smooth=True)

        def tbar(bm):   # pegador: barra-T grossa de couro escuro
            _tube(bm, [(x_rod, -0.09, top_z), (x_rod, 0.09, top_z)], 0.014, sides=8, cap=True)
            _box(bm, (0.03, 0.17, 0.02), (x_rod, 0, top_z - 0.012), 0.006)

        part("tbar", tbar, dark, ink * 0.5, smooth=True)

        def wheels(bm):
            rot = Matrix.Rotation(math.pi / 2, 4, "X")
            for y in (-(D / 2 - 0.032), D / 2 - 0.032):
                _cylinder(bm, Rw, 0.024, (axle.x, y, axle.z), segments=12, rot=rot)

        part("wheels", wheels, rubber, ink * 0.5)
        _anchor(sc, root, "grip", Vector((x_rod, 0, top_z)) + Vector(off), parent=pivot)
        _anchor(sc, root, "strap_base", Vector((x_rod, 0, H)) + Vector(off), parent=pivot)
    else:
        # Correia: objeto próprio com a origem no ponto onde prende (gire o Y pra erguer).
        attach = Vector((W / 2 + 0.014, 0, 0.26))
        strap_len = 0.52
        strap = _empty(sc, f"{name}.strap", pivot, attach + Vector(off), size=0.06)
        strap.rotation_euler.y = -math.radians(strap_angle - tilt)
        strap.rotation_euler.z = math.radians(strap_yaw)

        def ribbon(bm):
            sag, n = 0.035, 9
            pts = [(strap_len * k / (n - 1), 0,
                    -4 * sag * (k / (n - 1)) * (1 - k / (n - 1))) for k in range(n)]
            _tube(bm, pts, (0.004, 0.015), sides=6, cap=True)
            # alça-laço na ponta (couro enrolado): elo achatado no plano XY da correia
            loop = [(p[0] + strap_len + 0.045, p[1], 0) for p in _stadium(0.12, 0.06, 5)]
            _tube(bm, loop, 0.009, sides=5, closed=True)

        bm = bmesh.new()
        ribbon(bm)
        s_ob = _mesh_ob(sc, f"{name}.strap_mesh", bm, strap, smooth=True)
        T.assign(s_ob, dark, ink * 0.5)
        _anchor(sc, root, "grip", (strap_len + 0.06, 0, 0), parent=strap)
        _anchor(sc, root, "strap_base", (0, 0, 0), parent=strap)

    _anchor(sc, root, "handle", Vector((0, 0, H + 0.065)) + Vector(off), parent=pivot)
    _anchor(sc, root, "top", Vector((0, 0, H)) + Vector(off), parent=pivot)
    _anchor(sc, root, "front", Vector((0, -D / 2, H / 2)) + Vector(off), parent=pivot)
    _anchor(sc, root, "drag_edge", (0, 0, 0), parent=yaw_e)
    return root


# ─── Colar ──────────────────────────────────────────────────────────────────

def _necklace_curve(t):
    """Laço frouxo em forma de coração, ~0.25 m; t=-π/2 é o ponto de baixo (-Y)."""
    x = 0.118 * math.cos(t) + 0.008 * math.sin(3 * t)
    y = 0.080 * math.sin(t) + 0.006 * math.cos(2 * t)
    y -= 0.040 * math.exp(-((t - math.pi / 2) / 0.42) ** 2)    # dobra pra dentro em cima
    y -= 0.016 * math.exp(-((t + math.pi / 2) / 0.35) ** 2)    # bico embaixo (peso do pingente)
    return Vector((x, y, 0.0))


def _drape_fn(edge, r=0.012):
    """Dobra tudo que estiver à frente (y < edge) por cima da quina de um degrau:
    a parte de trás fica deitada no piso (z=0), a da frente desce colada no espelho
    (face vertical em y=edge), com uma curvinha de raio r na quina."""
    if edge is None:
        return None
    e = edge + r
    quarter = math.pi * r / 2

    def f(co):
        d = e - co.y
        if d <= 0:
            return co
        z = co.z
        if d < quarter:
            ph = d / r
            return Vector((co.x, e - (r + z) * math.sin(ph), -r + (r + z) * math.cos(ph)))
        return Vector((co.x, e - r - z, -r - (d - quarter)))

    return f


def _halo_material(name, color, strength):
    """Brilho suave e ADITIVO (emissão sobre transparente, some na borda) — 'ouro na
    neve': na neve escura do flashback vira um halo quente; na neve clara quase some."""
    mat = bpy.data.materials.get(name)
    if mat:
        return mat
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    tc = nt.nodes.new("ShaderNodeTexCoord")
    grad = nt.nodes.new("ShaderNodeTexGradient")
    grad.gradient_type = "SPHERICAL"
    nt.links.new(tc.outputs["Object"], grad.inputs["Vector"])
    pw = nt.nodes.new("ShaderNodeMath")
    pw.operation = "POWER"
    pw.inputs[1].default_value = 2.2
    nt.links.new(grad.outputs["Fac"], pw.inputs[0])
    mul = nt.nodes.new("ShaderNodeMath")
    mul.operation = "MULTIPLY"
    mul.inputs[1].default_value = strength
    nt.links.new(pw.outputs[0], mul.inputs[0])
    em = nt.nodes.new("ShaderNodeEmission")
    em.inputs["Color"].default_value = T.lin(color)
    nt.links.new(mul.outputs[0], em.inputs["Strength"])
    clear = nt.nodes.new("ShaderNodeBsdfTransparent")
    add = nt.nodes.new("ShaderNodeAddShader")       # aditivo: só clareia, nunca suja
    nt.links.new(clear.outputs[0], add.inputs[0])
    nt.links.new(em.outputs[0], add.inputs[1])
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    nt.links.new(add.outputs[0], out.inputs["Surface"])
    try:
        mat.surface_render_method = "BLENDED"
    except (AttributeError, TypeError):
        pass
    return mat


def necklace(sc, name="Necklace", halo=0.6, ink=0.003, link_len=0.028, lift=0.0,
             drape=None, silhouette=True):
    """Colar de ouro (corrente de elos + pingente redondo com estrela e pedra azul)
    deitado, ~0.25 m de largura. Pingente pra -Y (frente, pra câmera).

    k05 (câmera a ~2.5–3 m, altura dos olhos da raposa): use root.scale = 1.3 (o
    exagero de livro ilustrado) e, de preferência, `drape` na quina do degrau, que
    põe o pingente de frente pra lente. Sem degrau, use `lift` ≈ 12.

    halo        > 0 põe um brilho dourado ADITIVO sob o colar (não faz sombra; na neve
                escura do flashback vira halo quente, na neve clara some). 0 desliga.
    link_len    comprimento de cada elo (m). 0.028 = elos grossos como no 2D.
    ink         contorno de cada elo (m).
    silhouette  fita preta chata sob a corrente, 3.5 mm mais larga de cada lado: dá à
                corrente um contorno grosso de nanquim que não some de longe.
    lift        graus: inclina o colar pra câmera girando sobre a ponta da frente (o
                pingente fica no chão, a parte de trás sobe). Pra colar em cima de um
                montinho de neve. Deixe 0 com `drape`.
    drape       y LOCAL (m, antes da escala da raiz) da face da frente do degrau: tudo
                à frente disso cai pela quina e fica pendurado colado no espelho.
                Ponha a raiz no piso do degrau (z = altura do degrau) com y=0 a
                ~0.07 m atrás da quina e use drape=-0.07: o pingente pendura ~0.12 m.
                O espelho precisa ter pelo menos isso de altura.

    Âncoras (`anchors(root)`, mundo):
        center    centro do laço, no chão: pra mirar a câmera / a raposa cheirar
        pendant   centro da face do pingente (com drape: pendurado na frente do degrau)
        pick      ponto de cima da corrente (lado +Y): onde uma mão pega o colar
    """
    gold = T.toon("PropGold", GOLD, shadow=0.72, light=1.35, bands=(0.22, 0.55), emission=0.12)
    glow = T.toon("PropGoldGlow", GOLD_GLOW, shadow=0.85, light=1.2, bands=(0.2, 0.5),
                  emission=1.1)
    gem = T.toon("PropGem", GEM, shadow=0.6, light=1.6, emission=0.25)
    warp = _drape_fn(drape)

    N = 480
    dense = [_necklace_curve(-math.pi / 2 + 2 * math.pi * i / N) for i in range(N)]
    bottom = dense[0]
    R = 0.025
    pc = Vector((bottom.x, bottom.y - 0.030 - R * 0.55, 0.0))   # centro do pingente

    root = _empty(sc, name, size=0.15)
    y_piv = drape if drape is not None else pc.y - R
    pivot = _empty(sc, f"{name}.lift", root, (0, y_piv, 0), size=0.05)
    pivot.rotation_euler.x = math.radians(lift)
    off = Vector((0, -y_piv, 0))

    def mesh(label, bm, mat, thick, smooth=False):
        ob = _mesh_ob(sc, f"{name}.{label}", bm, pivot, off, smooth, warp)
        T.assign(ob, mat, thick)
        return ob

    # Corrente: elos alternando deitado/em pé ao longo da curva, num só mesh.
    cum = [0.0]
    for i in range(1, N + 1):
        cum.append(cum[-1] + (dense[i % N] - dense[i - 1]).length)
    total = cum[-1]
    pitch = link_len * 0.68
    count = max(8, int(round(total / pitch)))
    if count % 2:
        count += 1
    width = link_len * 0.62
    wire = link_len * 0.11

    def at(s):
        s %= total
        j = 1
        while cum[j] < s:
            j += 1
        a, b = dense[j - 1], dense[j % N]
        f = (s - cum[j - 1]) / max(cum[j] - cum[j - 1], 1e-9)
        return a.lerp(b, f), (b - a).normalized()

    bm = bmesh.new()
    base = _stadium(link_len, width, 4)
    top_pt, top_y = None, -1e9
    for i in range(1, count):          # o elo 0 (ponto de baixo) vira a argola do pingente
        p, tan = at(i * total / count)
        side = Vector((0, 0, 1)).cross(tan)
        if i % 2:   # deitado
            ex, ey, z = tan, side, wire
        else:       # em pé
            ex, ey, z = tan, Vector((0, 0, 1)), width / 2
        c = Vector((p.x, p.y, z))
        pts = [c + ex * q[0] + ey * q[1] for q in base]
        _tube(bm, pts, wire, sides=5, closed=True)
        if p.y > top_y:
            top_y, top_pt = p.y, p
    mesh("chain", bm, gold, ink, smooth=True)

    if silhouette:
        # Fita preta chata, colada no chão, sob a corrente inteira: vira a "linha de
        # nanquim" grossa em volta da corrente em qualquer distância.
        bm = bmesh.new()
        loop = [Vector((p.x, p.y, 0.0012)) for p in dense[::6]]
        _tube(bm, loop, (0.0011, width / 2 + 0.0035), sides=6, closed=True)
        mesh("silhouette", bm, T.toon("PropInkFlat", INK_FLAT, shadow=1.0, light=1.0), 0)

    # Pingente: disco + tampinha chata (argola) no mesmo mesh.
    bm = bmesh.new()
    _box(bm, (0.013, 0.024, 0.007), (bottom.x, bottom.y - 0.016, 0.0035), 0.003, 2)
    _cylinder(bm, R, 0.005, (pc.x, pc.y, 0.0025), segments=20)
    mesh("pendant", bm, gold, ink * 1.2)

    # Borda e estrela emissivas + pedra azul.
    bm = bmesh.new()
    rim = [(pc.x + R * math.cos(a), pc.y + R * math.sin(a), 0.0052)
           for a in (2 * math.pi * k / 20 for k in range(20))]
    _tube(bm, rim, 0.0022, sides=5, closed=True)
    star_pts, z0, z1 = [], 0.005, 0.0068
    for k in range(16):
        a = math.pi / 2 + 2 * math.pi * k / 16
        r = 0.0175 if k % 2 == 0 else 0.0066
        star_pts.append((pc.x + r * math.cos(a), pc.y + r * math.sin(a)))
    lo = [bm.verts.new((x, y, z0)) for x, y in star_pts]
    hi = [bm.verts.new((x, y, z1)) for x, y in star_pts]
    bm.faces.new(hi)
    for k in range(16):
        k1 = (k + 1) % 16
        bm.faces.new((lo[k], lo[k1], hi[k1], hi[k]))
    mesh("glint", bm, glow, ink * 0.5)

    bm = bmesh.new()
    bmesh.ops.create_icosphere(bm, subdivisions=2, radius=0.0055,
                               matrix=Matrix.Translation((pc.x, pc.y, 0.0068))
                               @ Matrix.Diagonal((1, 1, 0.6, 1)))
    mesh("gem", bm, gem, ink * 0.5, smooth=True)

    if halo > 0:
        bm = bmesh.new()
        bmesh.ops.create_circle(bm, cap_ends=True, segments=24, radius=1.0)
        if drape is None:
            hc, hy = -0.02, 0.20
        else:   # só no piso do degrau, atrás da quina
            hc, hy = (drape + 0.075) / 2, (0.075 - drape) / 2 + 0.05
        h = _mesh_ob(sc, f"{name}.halo", bm, pivot, Vector((0, hc, 0.0015)) + off)
        h.scale = (0.24, hy, 1.0)
        h.data.materials.append(_halo_material(f"PropGoldHalo{halo:.2f}", GOLD_GLOW, halo))
        h.visible_shadow = False

    def a(key, p):
        p = Vector(p)
        _anchor(sc, root, key, (warp(p) if warp else p) + off, parent=pivot)

    a("center", (0, 0, 0))
    a("pendant", (pc.x, pc.y, 0.006))
    a("pick", (top_pt.x, top_pt.y, 0.01))
    return root


# ─── Pegadas da raposa ──────────────────────────────────────────────────────

def _print_mesh(name, size, depth, snow):
    """Uma pegada oval afundada na neve (eixo longo em Y local).

    A pegada não fura o chão (o chão da cena cobriria): é uma bordinha baixa de neve
    em volta de um fundo azul escuro. A bordinha usa um material quase sem faixas
    (nunca fica cinza), então a pegada lê como um buraco azul chapado, não um pires.
    """
    bm = bmesh.new()
    seg = 14
    a, b = 0.030 * size, 0.038 * size          # semi-eixos: lado × frente
    h = depth * size
    rings = ((1.35, -0.006), (1.12, h), (0.97, h * 0.8), (0.72, 0.004))  # base, crista, beira, fundo
    vr = [[bm.verts.new((k_r * a * math.cos(t), k_r * b * math.sin(t), z))
           for t in (2 * math.pi * k / seg for k in range(seg))] for k_r, z in rings]
    centre = bm.verts.new((0, 0, 0.003))
    for r in range(len(rings) - 1):
        for k in range(seg):
            k1 = (k + 1) % seg
            f = bm.faces.new((vr[r][k], vr[r][k1], vr[r + 1][k1], vr[r + 1][k]))
            f.material_index = 1 if r >= 2 else 0   # parede de dentro = azul
            f.smooth = True
    for k in range(seg):
        f = bm.faces.new((vr[-1][k], vr[-1][(k + 1) % seg], centre))
        f.material_index = 1
        f.smooth = True
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    me.materials.append(snow or T.toon("PropPrintRim", SNOW, shadow=0.97, light=1.0))
    me.materials.append(T.toon("PropPrint", PRINT, shadow=0.8, light=1.05, bands=(0.2, 0.7)))
    return me


def _tilt_k(h, d):
    """Fração da inclinação pela elevação da câmera: sen(elev) = h/d.
    elev ≥ ~20° → 0 (de cima a pegada já lê); elev ≤ ~6° → 1 (rasante)."""
    return min(1.0, max(0.0, (0.35 - h / max(d, 0.01)) / 0.25))


def _driver_var(drv, name, kind, ob, ttype=None, ob2=None):
    v = drv.variables.new()
    v.name = name
    v.type = kind
    if kind == "TRANSFORMS":
        t = v.targets[0]
        t.id = ob
        t.transform_type = ttype
        t.transform_space = "WORLD_SPACE"
    else:  # LOC_DIFF
        v.targets[0].id = ob
        v.targets[1].id = ob2
    return v


def _aim_print(ob, trk, cam, root, yaw, tilt_rad):
    """Liga a pegada à câmera por drivers de expressão simples (sem Python):
    x = inclinação pela elevação REAL da câmera (acompanha o movimento),
    z = mantém a direção da caminhada (compensa o giro do rastreador)."""
    ob.rotation_mode = "ZYX"            # matriz = Rx(tilt) @ Rz(yaw): gira, depois inclina
    fc = ob.driver_add("rotation_euler", 0)
    d = fc.driver
    d.type = "SCRIPTED"
    _driver_var(d, "cz", "TRANSFORMS", cam, "LOC_Z")
    _driver_var(d, "tz", "TRANSFORMS", trk, "LOC_Z")
    _driver_var(d, "d", "LOC_DIFF", trk, ob2=cam)
    d.expression = f"{tilt_rad:.6f}*min(1.0,max(0.0,(0.35-(cz-tz)/max(d,0.01))/0.25))"

    fc = ob.driver_add("rotation_euler", 2)
    d = fc.driver
    d.type = "SCRIPTED"
    for n, tt in (("cx", "LOC_X"), ("cy", "LOC_Y")):
        _driver_var(d, n, "TRANSFORMS", cam, tt)
    for n, tt in (("tx", "LOC_X"), ("ty", "LOC_Y")):
        _driver_var(d, n, "TRANSFORMS", trk, tt)
    _driver_var(d, "rz", "TRANSFORMS", root, "ROT_Z")
    d.expression = f"{yaw:.6f}+rz-atan2(cy-ty,cx-tx)-{math.pi / 2:.6f}"


def fox_tracks(sc, start, end, count, via=(), name="FoxTracks", size=1.4, depth=0.012,
               face=None, face_tilt=24.0, snow=None, ink=0.0, z=0.0, seed=7):
    """Trilha de pegadas de raposa, de `start` (x, y) até `end` (x, y), em `count` PARES.

    Cada par = duas pegadas ovais azul-escuras, lado a lado e defasadas (o "••"
    das ilustrações, s08), com uma bordinha baixa de neve em volta. Todas as
    pegadas são duplicatas ligadas de UM mesh (barato); um leve zigue-zague/giro
    determinístico (`seed`) tira a cara de carimbo. Não projetam sombra.

    start, end   (x, y) em coordenadas da raiz (que nasce na origem do mundo, em z)
    count        número de pares (≥1), igualmente espaçados; o 1º em start, o último em end
    via          pontos (x, y) intermediários opcionais: trilha em curva/polilinha
    size         escala da pegada. 1.0 ≈ pegada real de raposa (~7 cm). Use 1.1 quando
                 a raposa estiver no quadro (k07, k09) e 1.4 (padrão) só em trilha sem
                 raposa vista de 4–10 m (k04).
    depth        altura da bordinha de neve (m, antes de `size`)
    face         a CÂMERA do plano (o objeto) — RECOMENDADO. Cada pegada se inclina pra
                 lente conforme a elevação REAL da câmera, quadro a quadro: rasante
                 (≤6°) inclina `face_tilt` inteiro, a partir de ~20° não inclina. No k04
                 (câmera desce do alto até as pegadas) a trilha acompanha o movimento
                 sozinha. Custa um Empty rastreador + 2 drivers de expressão simples por
                 pegada. A câmera precisa existir antes; não apague a câmera depois.
                 Alternativa estática: (x, y, z) da câmera no espaço da raiz (a
                 inclinação é calculada uma vez; num movimento, passe a posição FINAL);
                 (x, y) assume z=1.0. None = pegadas deitadas.
    snow         material da bordinha. None = "PropPrintRim" (neve sem faixa de sombra).
                 Passar a neve do set casa o tom, mas traz as faixas dela junto.
    ink          contorno preto nas bordas (m); 0 = sem (mais parecido com o 2D)

    Cada pegada é um objeto `<name>.NNN.L|R` com ["t"] = fração 0..1 ao longo da
    trilha e ["pair"] = índice do par (ver `animate_tracks`, `puffs_for_tracks`).

    Âncoras (`anchors(root)`, mundo):
        first   centro do 1º par (em start)
        last    centro do último par (em end)
        mid     centro do par do meio
    """
    rng = random.Random(seed)
    cam = face if (face is not None and hasattr(face, "location")) else None
    fixed = None
    if cam is None and face is not None:
        fixed = (face[0], face[1], face[2] if len(face) > 2 else 1.0)
    root = _empty(sc, name, loc=(0, 0, z), size=0.2)
    path = [Vector((p[0], p[1], 0.0)) for p in (start, *via, end)]
    lens = [(path[i + 1] - path[i]).length for i in range(len(path) - 1)]
    total = sum(lens) or 1e-6

    def at(s):
        for i, L in enumerate(lens):
            if s <= L or i == len(lens) - 1:
                f = 0.0 if L == 0 else min(s / L, 1.0)
                d = (path[i + 1] - path[i])
                return path[i].lerp(path[i + 1], f), (d.normalized() if L else Vector((0, 1, 0)))
            s -= L

    me = _print_mesh(f"{name}.print", size, depth, snow)
    count = max(1, int(count))
    tilt_rad = math.radians(face_tilt)
    centres = []
    for i in range(count):
        t = i / (count - 1) if count > 1 else 0.0
        p, d = at(t * total)
        side = Vector((d.y, -d.x, 0))       # direita de quem anda
        p = p + side * (0.018 * size * (1 if i % 2 else -1) + rng.uniform(-0.01, 0.01))
        yaw = math.atan2(d.y, d.x) - math.pi / 2 + math.radians(rng.uniform(-7, 7))
        centres.append(p)
        for tag, lat, lon in (("L", -0.032, -0.045), ("R", 0.032, 0.045)):
            q = p + side * (lat * size) + d * (lon * size)
            y_i = yaw + math.radians(rng.uniform(-6, 6))
            ob = bpy.data.objects.new(f"{name}.{i:03d}.{tag}", me)
            _collection(sc).objects.link(ob)
            if cam is not None:
                trk = _empty(sc, f"{name}.{i:03d}.{tag}.aim", root, q, size=0.04)
                con = trk.constraints.new("LOCKED_TRACK")
                con.target = cam
                con.track_axis = "TRACK_NEGATIVE_Y"
                con.lock_axis = "LOCK_Z"
                ob.parent = trk
                _aim_print(ob, trk, cam, root, y_i, tilt_rad)
            else:
                ob.parent = root
                ob.location = q
                ob.rotation_mode = "QUATERNION"
                rot = Quaternion((0, 0, 1), y_i)
                if fixed is not None:
                    to_cam = Vector((fixed[0] - q.x, fixed[1] - q.y, 0))
                    dist = to_cam.length
                    if dist > 1e-6:
                        k = _tilt_k(fixed[2], math.hypot(dist, fixed[2]))
                        axis = Vector((0, 0, 1)).cross(to_cam.normalized())
                        rot = Quaternion(axis, tilt_rad * k) @ rot
                ob.rotation_quaternion = rot
            ob["t"] = t
            ob["pair"] = i
            ob.visible_shadow = False
            if ink:
                T.outline(ob, ink)
    _anchor(sc, root, "first", tuple(centres[0]))
    _anchor(sc, root, "last", tuple(centres[-1]))
    _anchor(sc, root, "mid", tuple(centres[len(centres) // 2]))
    return root


def track_pairs(root):
    """As pegadas de uma trilha, na ordem da caminhada (as duas de um par, juntas)."""
    out = []

    def walk(ob):
        for c in ob.children:
            if "t" in c:
                out.append(c)
            walk(c)

    walk(root)
    return sorted(out, key=lambda c: (c["t"], c.name))


def _print_frames(root, frame_start, frame_end, reverse=False):
    """[(pegada, frame)] na ordem da caminhada: cada par em seu passo, e a pata que
    fica à frente na direção da caminhada meio passo depois da outra."""
    prints = track_pairs(root)
    if not prints:
        return []
    n = max(ob["pair"] for ob in prints) + 1
    late = "L" if reverse else "R"
    span = frame_end - frame_start
    out = []
    for ob in prints:
        k = (n - 1 - ob["pair"]) if reverse else ob["pair"]
        pos = k + (0.5 if ob.name.endswith("." + late) else 0.0)
        out.append((ob, int(round(frame_start + span * pos / max(n - 0.5, 0.5)))))
    return sorted(out, key=lambda x: (x[1], x[0].name))


def animate_tracks(root, frame_start, frame_end, reverse=False):
    """As pegadas aparecem pata a pata entre frame_start e frame_end (escala 0 → 1,
    corte seco); a pata da frente de cada par aparece meio passo depois da outra.
    reverse=True: a raposa anda de end pra start."""
    for ob, f in _print_frames(root, frame_start, frame_end, reverse):
        ob.scale = (0, 0, 0)
        ob.keyframe_insert("scale", frame=f - 1)
        ob.scale = (1, 1, 1)
        ob.keyframe_insert("scale", frame=f)
        _set_interp(ob, "CONSTANT", "scale")
    return root


def puffs_for_tracks(sc, root, frame_start, frame_end, every=2, reverse=False, **puff_kw):
    """Um `snow_puff` animado a cada `every` pegadas, no MESMO frame em que
    `animate_tracks(root, frame_start, frame_end, reverse)` faz a pegada aparecer.
    Devolve a lista das raízes dos pufes."""
    out = []
    for i, (ob, f) in enumerate(_print_frames(root, frame_start, frame_end, reverse)):
        if i % max(1, every):
            continue
        loc = _world_matrix(ob).translation
        out.append(snow_puff(sc, (loc.x, loc.y, loc.z), frame=f,
                             name=f"{root.name}.puff{i:03d}", seed=11 + i, **puff_kw))
    return out


# ─── Pufe de neve ───────────────────────────────────────────────────────────

def snow_puff(sc, loc, frame=None, name="SnowPuff", count=12, radius=0.16, size=0.014,
              height=0.12, duration=16, seed=3):
    """Pufe de neve de uma pisada: `count` bolinhas de neve azulada com contorno de
    nanquim (como os flocos do 2D) que saltam pra fora e pra cima e somem.

    loc       (x, y, z) do pé no chão (a raiz nasce aí)
    size      raio médio de cada bolinha (m)
    frame     None = pose estática no meio do salto (preview/still);
              número = anima: aparece em `frame`, abre até frame+duration*0.3,
              cai e encolhe até sumir em frame+duration
    Devolve a raiz (Empty). Âncora: `center` (o ponto da pisada).
    """
    rng = random.Random(seed)
    mat = T.toon("PropSnowPuff", PUFF, shadow=0.8, light=1.1)
    root = _empty(sc, name, loc=loc, size=0.1)
    bm = bmesh.new()
    bmesh.ops.create_icosphere(bm, subdivisions=2, radius=size)
    me = bpy.data.meshes.new(f"{name}.bit")
    bm.to_mesh(me)
    bm.free()
    for p in me.polygons:
        p.use_smooth = True
    me.materials.append(mat)
    for i in range(count):
        a = 2 * math.pi * (i + rng.uniform(-0.3, 0.3)) / count
        d = Vector((math.cos(a), math.sin(a), 0))
        r = radius * rng.uniform(0.45, 1.0)
        zt = height * rng.uniform(0.5, 1.0)
        s = rng.uniform(0.6, 1.3)
        ob = bpy.data.objects.new(f"{name}.{i:02d}", me)
        _collection(sc).objects.link(ob)
        ob.parent = root
        ob.visible_shadow = False
        T.outline(ob, 0.003)
        if frame is None:
            ob.location = d * r * 0.8 + Vector((0, 0, zt * 0.8))
            ob.scale = (s,) * 3
            continue
        keys = ((frame - 1, Vector((0, 0, 0.01)), 0.0),
                (frame, d * r * 0.15 + Vector((0, 0, 0.02)), s * 0.6),
                (frame + duration * 0.3, d * r * 0.75 + Vector((0, 0, zt)), s),
                (frame + duration * 0.65, d * r + Vector((0, 0, zt * 0.55)), s * 0.8),
                (frame + duration, d * r * 1.1, 0.0))
        for f, p, sc_ in keys:
            ob.location = p
            ob.scale = (sc_,) * 3
            ob.keyframe_insert("location", frame=f)
            ob.keyframe_insert("scale", frame=f)
    _anchor(sc, root, "center", (0, 0, 0))
    return root


# ─── Entrada única ──────────────────────────────────────────────────────────

_MAKERS = {"suitcase": suitcase, "necklace": necklace, "tracks": fox_tracks, "puff": snow_puff}
_DEFAULTS = {"tracks": {"start": (0.0, -4.0), "end": (0.0, -0.3), "count": 10},
             "puff": {"loc": (0.0, 0.0, 0.0)}}


def build(sc, which=("suitcase", "necklace", "tracks"), **kw):
    """Constrói os props pedidos na cena `sc` e DEVOLVE um dict de âncoras em mundo.

    which   quais: "suitcase", "necklace", "tracks", "puff" (qualquer subconjunto)
    kw      um dict de opções por prop, com o mesmo nome: suitcase=dict(...),
            necklace=dict(...), tracks=dict(...), puff=dict(...). As opções são as
            da função (`suitcase`, `necklace`, `fox_tracks`, `snow_puff`) mais:
              at=(x, y, z)   posição da raiz        yaw=graus   giro da raiz em Z
              scale=s|(x,y,z) escala da raiz
              tracks: animate=(f0, f1) ou (f0, f1, reverse) → animate_tracks;
                      puffs=N → puffs_for_tracks a cada N pegadas (precisa de animate)
            tracks sem start/end/count: trilha de 10 pares de (0,-4) até (0,-0.3).

    Devolve {"suitcase.grip": (x, y, z), ..., "tracks.first": ..., "_roots": {nome: Empty}}.
    As âncoras de cada prop estão documentadas na função dele.
    """
    bad = [k for k in list(which) + list(kw) if k not in _MAKERS]
    if bad:
        raise ValueError(f"props.build: não conheço {bad}; use {sorted(_MAKERS)}")
    out, roots = {}, {}
    for key in which:
        opts = dict(_DEFAULTS.get(key, {}))
        opts.update(kw.get(key) or {})
        place_at = opts.pop("at", None)
        yaw = opts.pop("yaw", None)
        scale = opts.pop("scale", None)
        anim = opts.pop("animate", None)
        every = opts.pop("puffs", None)
        root = _MAKERS[key](sc, **opts)
        if place_at is not None:
            root.location = place_at
        if yaw:
            root.rotation_euler.z = math.radians(yaw)
        if scale is not None:
            root.scale = (scale,) * 3 if isinstance(scale, (int, float)) else scale
        if key == "tracks" and anim:
            animate_tracks(root, *anim)
            if every:
                puffs_for_tracks(sc, root, anim[0], anim[1], every=every,
                                 reverse=bool(anim[2]) if len(anim) > 2 else False)
        roots[key] = root
        for k, v in anchors(root).items():
            out[f"{key}.{k}"] = v
    out["_roots"] = roots
    return out
