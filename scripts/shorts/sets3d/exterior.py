"""Exterior set for "The Fox and the North Wind" (3D toon diorama).

Used by shots k01, k04, k05, k07, k08, k09 and k11. Everything is procedural
(bpy + bmesh), deterministic (fixed seeds) and shaded with the toon kit
(`scripts/shorts/toon3d.py`): every material is born from `T.toon`, every
drawn edge is `T.outline`, the sky is `T.sky`, the lights are
`T.moonlight` / `T.warm_light`.

    import sys
    sys.path.insert(0, "/Users/alexandrejunior/Pedagogy_Swift/scripts/shorts/sets3d")
    import exterior as X
    anchors = X.build_exterior(bpy.context.scene, variant="night")

Variants
--------
- "night"  (k01 k04 k07 k08 k09): deep Arctic-blue gradient sky, big crescent
  moon, stars, three green aurora curtains low in the north, falling snow,
  cold moonlight from the front-left, warm lit window + door lantern.
- "dawn"   (k11): pale blue-to-peach sky, no moon/stars/aurora, low soft sun
  from the south-east (long blue shadows across the forest path), sparse
  slow snow. The house is still built but the k11 camera looks away from it.
- "memory" (k05): the night set, re-tinted desaturated blue by a SCENE-LEVEL
  COMPOSITOR (see `apply_memory_tint`): saturation x0.12, multiply by a cold
  blue, a small blue lift and a soft vignette. Because it works on the final
  image, the Tripo characters and props added later are tinted too, with no
  work from the director. The world and moonlight are also made greyer/bluer
  and the snow falls a little slower. Replaces any compositor on that scene.

Collections: everything lives in `Exterior_<variant>` (children Ext_House,
Ext_Forest, Ext_Ground, Ext_Sky, Ext_Snow, Ext_Lights) linked to the scene.
Materials are named `ExtN_* / ExtD_* / ExtM_*` per variant so several variants
can live in one .blend. Outlines are the kit's `T.outline`; their material is
then swapped for "ExtInk" (a kit `T.ink`, made opaque with back-face culling in
the shadow pass): same look as "Ink", ~7x faster renders (see `_fast_ink`).

Render cost (this Mac, EEVEE, 16 samples): ~1-1.8 s per frame at 640x360 and
about the same at 1280x720 (GPU bound), plus a ~1-2 s shader warm-up on the
first frame of a session.
~600 objects (580 pines as linked duplicates of 4 meshes), ~310k triangles
including the outline hulls, ~8-12k snow flakes (20-tri icospheres).

Useful objects
--------------
- `Ext_DoorLeaf`: origin on the hinge (left jamb). rotation_euler.z = +80deg
  opens it inward; behind it the doorway shows a warm emissive glow.
- `Ext_FoxTracks`: small paw prints from treeline_path to the steps (k04).
  Hidden unless `fox_tracks=True`, or toggle `hide_render` yourself.
- `Ext_SnowFill` + `Ext_SnowEmitter` (particles "Ext?_SnowFill"/"Ext?_Snow"):
  falling snow. The fill box releases a full air-volume of flakes on the first
  snow frame, so the snow is already falling on frame 1; the top plane keeps
  feeding. Render frames IN ORDER from the first frame (render -a does); for a
  single still at a later frame call `prime_snow(sc, frame)` first.
  `set_snow_speed` keyframes the fall speed (k08).
- `fit_ink(sc, cam)`: call once per shot camera (or keyframe at the start and
  end of a camera move) so the ink lines keep ~constant pixel width. The
  static thicknesses are only good for 5-10 m; at 20 m+ lines vanish without it.

Anchors returned by build_exterior (x, y, z in metres, ground z=0):
- door            centre of the front doorway at ground level (house faces -Y).
- door_threshold  same x/y at floor height (z=0.45, top of the landing).
- doorstep_top    centre of the porch landing (top step) - necklace (k05).
- doorstep_front  snow 0.5 m in front of the lowest step, where Nell stands
                  facing -Y toward the fox (k07/k08).
- box_mark        snow ~0.6 m in front of Nell: the offering box (k08/k09).
- fox_mark        snow ~2 m from doorstep_front, where the fox sits facing +Y
                  (toward the door and Nell).
- fox_bow         where the fox stands to bow its head over the box (k09).
- window          centre of the lit ground-floor window, on the facade plane.
- lake_start      a low camera start over the frozen lake (k01), 0.9 m high.
- lake_end        where the k01 glide can end (in front of the yard, 1.6 m).
- lake_centre     centre of the ice at z=0.
- nell_walk_start snow at the west edge of the yard where Nell appears with
                  the suitcase (k01); the lane to doorstep_front is flat.
- treeline_path   forest edge east of the house where the fox enters/leaves
                  (k07/k09); the corridor to fox_mark is flat and clear.
- forest_path_near first point of the dawn forest path (fox starts k11 here).
- forest_path_mid  middle of that path.
- forest_path_far  far end of the path between the pines (k11 end mark).
- tracks_start / tracks_end  first / last fox print (k04 camera targets).
- chimney_top     top of the chimney (smoke, if ever wanted).
- house_centre    footprint centre at ground level.
- cam_k01 / look_k01, cam_k04_start / look_k04_start (house corner, wind),
  cam_k04 / look_k04 (down on the tracks), cam_k05 / look_k05,
  cam_k07 / look_k07, cam_k11 / look_k11: the preview cameras (suggestions;
  lenses used: k01 28 mm, k04 30, k05 30, k07 28, k11 35).
"""

import math
import random
import sys

import bmesh
import bpy
from mathutils import Euler, Matrix, Vector, noise

_KIT = "/Users/alexandrejunior/Pedagogy_Swift/scripts/shorts"
if _KIT not in sys.path:
    sys.path.insert(0, _KIT)
import toon3d as T  # noqa: E402

__all__ = ["build_exterior", "set_snow_speed", "prime_snow", "apply_memory_tint", "snow_systems",
           "fit_ink"]

# ─── Palette (sRGB 0-255) ───────────────────────────────────────────────────
HOUSE_RED = (158, 44, 38)
TRIM = (238, 232, 220)
ROOF = (70, 92, 120)
SNOW = (236, 240, 248)
ICE = (118, 148, 186)
PINE = (38, 66, 58)
BARK = (70, 45, 35)
SKY_TOP = (8, 14, 38)
SKY_HORIZON = (34, 58, 104)
AURORA = (90, 230, 170)
MOON = (245, 230, 190)
FIRE = (255, 150, 60)
PLASTER = (236, 222, 192)
STONE = (98, 104, 118)
DOOR_RED = (132, 36, 32)
STEP_RED = (146, 40, 34)
BRICK = (128, 52, 42)
IRON = (30, 30, 36)
GLASS = (38, 56, 90)
WINDOW_GLOW = (255, 206, 128)
POOL = (250, 228, 176)
STAR = (250, 242, 214)
TRACK = (150, 168, 206)

# ─── Layout (metres; house centred on the origin, front facing -Y) ─────────
HW, HD = 3.0, 3.5                      # half width (X), half depth (Y)
FOUND_H = 0.45                         # stone plinth / floor height
EAVE_Z = FOUND_H + 3.0                 # 3 m walls
PITCH = math.radians(50)
RIDGE_Z = EAVE_Z + HW * math.tan(PITCH)
DOOR_X, DOOR_W, DOOR_H = 1.45, 0.95, 2.0
WIN_X, WIN_W, WIN_H, WIN_SILL = -1.35, 1.0, 1.15, 1.3
LANDING_D, STEP_D = 1.15, 0.32
STEP_FRONT_Y = -HD - LANDING_D - 2 * STEP_D

LAKE_C = (0.5, -19.5)
LAKE_R = (11.5, 8.5)

TREELINE = (10.5, -6.5)
FOREST_PATH = [(10.5, -6.5), (15.0, -5.4), (19.5, -2.6), (24.0, 1.4),
               (28.5, 6.4), (33.0, 11.6), (37.0, 16.2), (41.0, 20.6)]
NELL_LANE = [(-24.0, -7.2), (-15.0, -6.6), (-8.0, -6.2), (DOOR_X - 0.6, -5.8)]
FOX_LANE = [TREELINE, (6.0, -7.4), (DOOR_X, -7.8)]
SNOW_TOP = 13.0
SNOW_FALL = 0.9                         # m/s at time_tweak 1

VARIANTS = ("night", "dawn", "memory")
_PREFIX = {"night": "ExtN_", "dawn": "ExtD_", "memory": "ExtM_"}


# ─── Small math helpers ─────────────────────────────────────────────────────

def _smooth(x, a, b):
    """Smoothstep from a (0) to b (1)."""
    if b == a:
        return 0.0 if x < a else 1.0
    t = max(0.0, min(1.0, (x - a) / (b - a)))
    return t * t * (3 - 2 * t)


def _seg_dist(p, a, b):
    ax, ay = a
    bx, by = b
    dx, dy = bx - ax, by - ay
    L2 = dx * dx + dy * dy
    t = 0.0 if L2 == 0 else max(0.0, min(1.0, ((p[0] - ax) * dx + (p[1] - ay) * dy) / L2))
    return math.hypot(p[0] - ax - t * dx, p[1] - ay - t * dy)


def _poly_dist(p, pts):
    return min(_seg_dist(p, pts[i], pts[i + 1]) for i in range(len(pts) - 1))


def _poly_point(pts, s):
    """Point at fraction s (0-1) of the polyline length, plus its direction."""
    lens = [math.dist(pts[i], pts[i + 1]) for i in range(len(pts) - 1)]
    total = sum(lens)
    d = s * total
    for i, L in enumerate(lens):
        if d <= L or i == len(lens) - 1:
            t = 0 if L == 0 else min(1.0, d / L)
            a, b = pts[i], pts[i + 1]
            dirv = Vector((b[0] - a[0], b[1] - a[1])).normalized()
            return (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t), dirv
        d -= L
    return pts[-1], Vector((1, 0))


def _lake_r(th):
    return 1.0 + 0.06 * math.sin(3 * th + 0.7) + 0.04 * math.sin(5 * th + 2.1) \
        + 0.022 * math.sin(9 * th + 0.3)


def _lake_sd(x, y):
    """Approximate signed distance (m) to the ice edge; negative on the ice."""
    cx, cy = LAKE_C
    rx, ry = LAKE_R
    dx, dy = (x - cx) / rx, (y - cy) / ry
    rho = math.hypot(dx, dy)
    if rho < 1e-6:
        return -min(rx, ry)
    r = _lake_r(math.atan2(dy, dx))
    return math.hypot(x - cx, y - cy) * (1.0 - r / rho)


def _lake_point(th, grow=0.0):
    cx, cy = LAKE_C
    rx, ry = LAKE_R
    r = _lake_r(th)
    p = Vector((cx + rx * r * math.cos(th), cy + ry * r * math.sin(th)))
    if grow:
        n = Vector(((p.x - cx) / (rx * rx), (p.y - cy) / (ry * ry))).normalized()
        p += n * grow
    return p


def _yard_sd(x, y):
    """Signed distance to the clear yard rectangle around the house."""
    x0, x1, y0, y1 = -9.5, 9.5, -11.5, 5.0
    dx = max(x0 - x, 0.0, x - x1)
    dy = max(y0 - y, 0.0, y - y1)
    if dx == 0 and dy == 0:
        return -min(x - x0, x1 - x, y - y0, y1 - y)
    return math.hypot(dx, dy)


# ─── Mesh builder ───────────────────────────────────────────────────────────

class _MB:
    """Accumulates many parts (with material indices) into one mesh object."""

    def __init__(self):
        self.V, self.F, self.M = [], [], []

    def add(self, verts, faces, mat=0):
        o = len(self.V)
        self.V.extend(tuple(v) for v in verts)
        for f in faces:
            self.F.append([o + i for i in f])
            self.M.append(mat)

    def add_bm(self, bm, mat=0, matrix=None):
        if matrix is not None:
            bm.transform(matrix)
        bm.verts.index_update()
        self.add([v.co.copy() for v in bm.verts],
                 [[v.index for v in f.verts] for f in bm.faces], mat)
        bm.free()

    def add_closed(self, verts, faces, mat=0, matrix=None):
        """Add a closed part, fixing the normals so they all point outward."""
        bm = bmesh.new()
        vs = [bm.verts.new(v) for v in verts]
        for f in faces:
            try:
                bm.faces.new([vs[i] for i in f])
            except ValueError:
                pass
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
        self.add_bm(bm, mat, matrix)

    def box(self, size, loc, rot=(0, 0, 0), bevel=0.0, mat=0):
        bm = bmesh.new()
        bmesh.ops.create_cube(bm, size=1.0)
        bmesh.ops.scale(bm, vec=Vector(size), verts=bm.verts)
        if bevel > 0:
            bmesh.ops.bevel(bm, geom=list(bm.edges), offset=min(bevel, min(size) * 0.45),
                            segments=1, affect="EDGES", profile=0.5, clamp_overlap=True)
        m = Matrix.Translation(Vector(loc)) @ Euler(rot).to_matrix().to_4x4()
        self.add_bm(bm, mat, m)

    def ico(self, loc, scale, mat=0, subdiv=1, rot=(0, 0, 0)):
        bm = bmesh.new()
        bmesh.ops.create_icosphere(bm, subdivisions=subdiv, radius=1.0)
        bmesh.ops.scale(bm, vec=Vector(scale), verts=bm.verts)
        m = Matrix.Translation(Vector(loc)) @ Euler(rot).to_matrix().to_4x4()
        self.add_bm(bm, mat, m)

    def cyl(self, r, z0, z1, sides=6, mat=0, matrix=None, r_top=None, caps=True):
        r_top = r if r_top is None else r_top
        V = []
        for z, rr in ((z0, r), (z1, r_top)):
            for j in range(sides):
                a = 2 * math.pi * j / sides
                V.append((rr * math.cos(a), rr * math.sin(a), z))
        F = [[j, (j + 1) % sides, sides + (j + 1) % sides, sides + j] for j in range(sides)]
        if caps:
            F.append(list(range(sides))[::-1])
            F.append(list(range(sides, 2 * sides)))
        if matrix is not None:
            V = [tuple(matrix @ Vector(v)) for v in V]
        self.add(V, F, mat)

    def prism(self, pts, z0, z1, mat=0, matrix=None):
        """Polygon `pts` (local XY) extruded from z0 to z1 (local Z)."""
        n = len(pts)
        area = sum(pts[i][0] * pts[(i + 1) % n][1] - pts[(i + 1) % n][0] * pts[i][1]
                   for i in range(n))
        if area < 0:
            pts = pts[::-1]
        V = [(x, y, z0) for x, y in pts] + [(x, y, z1) for x, y in pts]
        F = [list(range(n))[::-1], list(range(n, 2 * n))]
        F += [[i, (i + 1) % n, n + (i + 1) % n, n + i] for i in range(n)]
        if matrix is not None:
            V = [tuple(matrix @ Vector(v)) for v in V]
        self.add(V, F, mat)

    def loft(self, rings, mat=0, caps=True):
        """Closed tube through rings of equal vertex count, normals fixed."""
        k = len(rings[0])
        V = [tuple(p) for ring in rings for p in ring]
        F = []
        for r in range(len(rings) - 1):
            a, b = r * k, (r + 1) * k
            for j in range(k):
                F.append([a + j, a + (j + 1) % k, b + (j + 1) % k, b + j])
        if caps:
            F.append(list(range(k)))
            F.append(list(range((len(rings) - 1) * k, len(rings) * k)))
        self.add_closed(V, F, mat)

    def build(self, name, mats, coll, outline=0.0, smooth=False, shadow=True):
        me = bpy.data.meshes.new(name)
        me.from_pydata(self.V, [], self.F)
        me.update(calc_edges=True)
        if self.M:
            me.polygons.foreach_set("material_index", self.M)
        for m in mats:
            me.materials.append(m)
        if smooth:
            me.shade_smooth()
        ob = bpy.data.objects.new(name, me)
        coll.objects.link(ob)
        if outline:
            T.outline(ob, outline)
            ob["ext_ink"] = outline
        ob.visible_shadow = shadow
        return ob


# ─── Materials (all born from the kit's toon) ──────────────────────────────

def _node(nt, idname):
    return next((n for n in nt.nodes if n.bl_idname == idname), None)


def _sock(node, identifier):
    return next(s for s in node.inputs if s.identifier == identifier)


def _grade(mat, shadow_rgb, light_rgb, shadow=0.55, light=1.12):
    """Tint the toon bands: coloured shadow band (moonlit blue) / light band."""
    ramp = _node(mat.node_tree, "ShaderNodeValToRGB")
    if ramp is None:
        return
    el = ramp.color_ramp.elements
    el[0].color = tuple(shadow * c for c in shadow_rgb) + (1.0,)
    el[-1].color = tuple(light * c for c in light_rgb) + (1.0,)


def _planks(mat, spacing=0.3, line=0.1, dark=0.6, axis="XY"):
    """Board lines: stripes of darker colour every `spacing` m along X+Y
    (object space), so on any wall facing X or Y they run vertically."""
    nt = mat.node_tree
    mul = next(n for n in nt.nodes if n.bl_idname == "ShaderNodeMix" and n.blend_type == "MULTIPLY")
    a = _sock(mul, "A_Color")
    if a.is_linked:
        return
    base = tuple(a.default_value)
    tc = nt.nodes.new("ShaderNodeTexCoord")
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    nt.links.new(tc.outputs["Object"], sep.inputs[0])
    add = nt.nodes.new("ShaderNodeMath")
    add.operation = "ADD"
    if axis == "Z":
        nt.links.new(sep.outputs["Z"], add.inputs[0])
        add.inputs[1].default_value = 0.0
    else:
        nt.links.new(sep.outputs["X"], add.inputs[0])
        nt.links.new(sep.outputs["Y"], add.inputs[1])
    div = nt.nodes.new("ShaderNodeMath")
    div.operation = "DIVIDE"
    nt.links.new(add.outputs[0], div.inputs[0])
    div.inputs[1].default_value = spacing
    fr = nt.nodes.new("ShaderNodeMath")
    fr.operation = "FRACT"
    nt.links.new(div.outputs[0], fr.inputs[0])
    lt = nt.nodes.new("ShaderNodeMath")
    lt.operation = "LESS_THAN"
    nt.links.new(fr.outputs[0], lt.inputs[0])
    lt.inputs[1].default_value = line
    mix = nt.nodes.new("ShaderNodeMix")
    mix.data_type = "RGBA"
    nt.links.new(lt.outputs[0], _sock(mix, "Factor_Float"))
    _sock(mix, "A_Color").default_value = base
    _sock(mix, "B_Color").default_value = tuple(c * dark for c in base[:3]) + (1.0,)
    nt.links.new(mix.outputs[2], a)


def _unlit(mat):
    """A flat toon (shadow = light = 1) never changes with light, so drop its
    Diffuse / Shader-to-RGB chain: same colour, and EEVEE skips the lighting
    (big win on the large blended aurora and the thousands of flakes)."""
    nt = mat.node_tree
    if mat.get("ext_unlit"):
        return
    mul = next((n for n in nt.nodes if n.bl_idname == "ShaderNodeMix" and n.blend_type == "MULTIPLY"), None)
    if mul is None:
        return
    base = tuple(_sock(mul, "A_Color").default_value)
    for l in list(nt.links):
        if l.from_node == mul:
            to = l.to_socket
            nt.links.remove(l)
            to.default_value = base
    for n in list(nt.nodes):
        if n.bl_idname in ("ShaderNodeBsdfDiffuse", "ShaderNodeShaderToRGB", "ShaderNodeRGBToBW",
                           "ShaderNodeValToRGB") or n == mul:
            nt.nodes.remove(n)
    mat["ext_unlit"] = True


def _fast_ink(objects):
    """Swap the kit's shared "Ink" on these objects for a kit-born "ExtInk" that
    is plain opaque emission with back-face culling in the shadow pass.

    Same picture as the kit ink (the hull's light-facing side is culled when
    casting, so it never shadows its own object), but it avoids the
    transparent-shadow path: the exterior renders ~7x faster (7 s -> 1 s per
    640x360 frame). Suggested as the default for toon3d.ink()."""
    ink = T.ink("ExtInk")
    if not ink.get("ext_fast"):
        nt = ink.node_tree
        em = next(n for n in nt.nodes if n.bl_idname == "ShaderNodeEmission")
        out = next(n for n in nt.nodes if n.bl_idname == "ShaderNodeOutputMaterial")
        nt.links.new(em.outputs[0], out.inputs["Surface"])
        for n in list(nt.nodes):
            if n.bl_idname in ("ShaderNodeLightPath", "ShaderNodeBsdfTransparent", "ShaderNodeMixShader"):
                nt.nodes.remove(n)
        for attr, val in (("use_transparent_shadow", False), ("use_backface_culling_shadow", True),
                          ("use_backface_culling", True)):
            try:
                setattr(ink, attr, val)
            except (AttributeError, TypeError):
                pass
        ink["ext_fast"] = True
    seen = set()
    for ob in objects:
        me = ob.data if ob.type == "MESH" else None
        if me is None or me.name in seen:
            continue
        seen.add(me.name)
        for i, m in enumerate(me.materials):
            if m is not None and m.name == "Ink":
                me.materials[i] = ink
    return ink


def _surface_link(mat):
    nt = mat.node_tree
    out = _node(nt, "ShaderNodeOutputMaterial")
    link = next(l for l in nt.links if l.to_node == out and l.to_socket.name == "Surface")
    return nt, out, link.from_socket


def _add_gloss(mat, amount=0.22, roughness=0.12):
    """Adds a faint glossy sheen on top of the toon colour (ice)."""
    nt, out, src = _surface_link(mat)
    if mat.get("ext_gloss"):
        return
    gl = nt.nodes.new("ShaderNodeBsdfGlossy")
    gl.inputs["Color"].default_value = (amount, amount, amount, 1)
    gl.inputs["Roughness"].default_value = roughness
    add = nt.nodes.new("ShaderNodeAddShader")
    nt.links.new(src, add.inputs[0])
    nt.links.new(gl.outputs[0], add.inputs[1])
    nt.links.new(add.outputs[0], out.inputs["Surface"])
    mat["ext_gloss"] = True


def _make_transparent(mat, alpha_socket):
    """Mix the toon surface with Transparent by `alpha_socket` (1 = opaque)."""
    nt, out, src = _surface_link(mat)
    tr = nt.nodes.new("ShaderNodeBsdfTransparent")
    mix = nt.nodes.new("ShaderNodeMixShader")
    nt.links.new(alpha_socket, mix.inputs[0])
    nt.links.new(tr.outputs[0], mix.inputs[1])
    nt.links.new(src, mix.inputs[2])
    nt.links.new(mix.outputs[0], out.inputs["Surface"])
    for attr, val in (("surface_render_method", "BLENDED"), ("blend_method", "BLEND"),
                      ("use_transparent_shadow", True)):
        try:
            setattr(mat, attr, val)
        except (AttributeError, TypeError):
            pass
    mat.use_backface_culling = False


def _math(nt, op, a=None, b=None, va=None, vb=None, clamp=False):
    n = nt.nodes.new("ShaderNodeMath")
    n.operation = op
    n.use_clamp = clamp
    if a is not None:
        nt.links.new(a, n.inputs[0])
    elif va is not None:
        n.inputs[0].default_value = va
    if b is not None:
        nt.links.new(b, n.inputs[1])
    elif vb is not None:
        n.inputs[1].default_value = vb
    return n.outputs[0]


class _Ctx:
    """Per-build state: variant, material cache, collections."""

    GRADES = {
        # shadow-band tint, light-band tint
        "night": ((0.78, 0.86, 1.22), (1.0, 1.0, 1.0)),
        "memory": ((0.80, 0.86, 1.18), (1.0, 1.0, 1.02)),
        "dawn": ((0.84, 0.90, 1.18), (1.05, 1.01, 0.93)),
    }

    def __init__(self, sc, variant):
        self.sc = sc
        self.variant = variant
        self.p = _PREFIX[variant]
        self.mats = {}
        self.root = bpy.data.collections.new(f"Exterior_{variant}")
        sc.collection.children.link(self.root)
        self.coll = {}
        for key in ("House", "Forest", "Ground", "Sky", "Snow", "Lights"):
            c = bpy.data.collections.new(f"Ext_{key}")
            self.root.children.link(c)
            self.coll[key.lower()] = c

    def mat(self, key, color, flat=False, emission=0.0, shadow=0.55, light=1.12, **kw):
        if key in self.mats:
            return self.mats[key]
        if flat:
            m = T.toon(self.p + key, color, shadow=1.0, light=1.0, emission=emission, **kw)
            _unlit(m)
        else:
            m = T.toon(self.p + key, color, shadow=shadow, light=light, emission=emission, **kw)
            s_rgb, l_rgb = self.GRADES[self.variant]
            _grade(m, s_rgb, l_rgb, shadow, light)
        self.mats[key] = m
        return m

    def light(self, ob, name):
        ob.name = name
        for c in list(ob.users_collection):
            c.objects.unlink(ob)
        self.coll["lights"].objects.link(ob)
        return ob


def _materials(ctx):
    v = ctx.variant
    M = {}
    M["snow"] = ctx.mat("Snow", SNOW, shadow=0.6)
    M["ice"] = ctx.mat("Ice", ICE, shadow=0.62)
    M["icesnow"] = ctx.mat("IceSnow", (206, 218, 238), shadow=0.62)
    _add_gloss(M["ice"])
    M["planks"] = ctx.mat("Planks", HOUSE_RED)
    _planks(M["planks"], spacing=0.3, line=0.1, dark=0.62)
    M["door"] = ctx.mat("Door", DOOR_RED)
    _planks(M["door"], spacing=0.16, line=0.14, dark=0.65)
    M["steps"] = ctx.mat("Steps", STEP_RED)
    _planks(M["steps"], spacing=0.16, line=0.12, dark=0.66, axis="Z")
    M["trim"] = ctx.mat("Trim", TRIM)
    M["roof"] = ctx.mat("Roof", ROOF)
    M["stone"] = ctx.mat("Stone", STONE)
    M["brick"] = ctx.mat("Brick", BRICK)
    M["iron"] = ctx.mat("Iron", IRON)
    M["plaster"] = ctx.mat("Plaster", PLASTER)
    M["glass"] = ctx.mat("Glass", GLASS, shadow=0.8, light=1.3)
    M["glow"] = ctx.mat("WindowGlow", WINDOW_GLOW, flat=True, emission=0.3)
    M["doorglow"] = ctx.mat("DoorGlow", (255, 186, 110), flat=True, emission=0.25)
    M["lantern"] = ctx.mat("LanternGlow", (255, 196, 100), flat=True, emission=0.8)
    M["pool"] = ctx.mat("LightPool", POOL, flat=True, emission=0.05)
    M["pine"] = ctx.mat("Pine", PINE if v != "dawn" else (60, 96, 90), shadow=0.6, light=1.28)
    M["bark"] = ctx.mat("Bark", BARK)
    M["track"] = ctx.mat("Track", TRACK, flat=True)
    M["path"] = ctx.mat("Path", (206, 216, 238), shadow=0.6)
    if v == "dawn":
        M["far1"] = ctx.mat("FarTrees1", (96, 124, 156), flat=True)
        M["far2"] = ctx.mat("FarTrees2", (150, 172, 198), flat=True)
    else:
        M["far1"] = ctx.mat("FarTrees1", (16, 30, 44), flat=True)
        M["far2"] = ctx.mat("FarTrees2", (26, 44, 72), flat=True)
    M["flake"] = ctx.mat("Flake", (246, 248, 255), flat=True, emission=0.6)
    return M


# ─── Ground, lake, tracks ───────────────────────────────────────────────────

def _flat_mask(x, y):
    """0 where the ground must stay flat (staging areas), 1 where drifts may be."""
    m = _smooth(_yard_sd(x, y), 0.0, 4.0)
    m = min(m, _smooth(_poly_dist((x, y), NELL_LANE), 1.6, 4.0))
    m = min(m, _smooth(_poly_dist((x, y), FOX_LANE), 1.4, 3.5))
    m = min(m, _smooth(_poly_dist((x, y), FOREST_PATH), 1.2, 3.2))
    return m


def _ground_h(x, y):
    n1 = noise.noise(Vector((x / 11.0, y / 11.0, 0.37)))
    n2 = noise.noise(Vector((x / 4.3 + 13.1, y / 4.3 - 7.7, 1.9)))
    h = 0.34 * (0.5 + 0.5 * n1) + 0.10 * n2
    h = max(h, 0.0) * _flat_mask(x, y)
    # snow blown against the back and the west wall (north wind)
    if -HW - 3.0 < x < HW + 3.0 and y > HD:
        h += 0.5 * math.exp(-(y - HD - 0.1) / 1.3) * _smooth(HW + 3.0 - abs(x), 0.0, 2.5)
    if x < -HW and -HD - 1.0 < y < HD + 3.0:
        h += 0.35 * math.exp(-(-HW - x) / 1.1) * _smooth(y + HD + 1.0, 0.0, 2.0)
    # forest path: a soft trough
    dp = _poly_dist((x, y), FOREST_PATH)
    if dp < 1.6:
        h -= 0.06 * (1.0 - _smooth(dp, 0.0, 1.6)) * _smooth(math.dist((x, y), TREELINE), 1.0, 4.0)
    # lake: ground sinks under the ice
    sd = _lake_sd(x, y)
    if sd < 2.6:
        h = -0.12 + (h + 0.12) * _smooth(sd, 0.45, 2.6)
    return h


def _axis(lo, hi, fine_lo, fine_hi, fine, coarse):
    pts = []
    x = lo
    while x < fine_lo:
        pts.append(x)
        x += coarse
    x = fine_lo
    while x < fine_hi:
        pts.append(x)
        x += fine
    x = fine_hi
    while x <= hi + 1e-6:
        pts.append(x)
        x += coarse
    return pts


def _ground(ctx, M):
    xs = _axis(-200, 200, -44, 52, 1.0, 5.0)
    ys = _axis(-200, 200, -40, 36, 1.0, 5.0)
    nx = len(xs)
    V = [(x, y, _ground_h(x, y)) for y in ys for x in xs]
    F = []
    for j in range(len(ys) - 1):
        for i in range(nx - 1):
            a = j * nx + i
            F.append([a, a + 1, a + nx + 1, a + nx])
    mb = _MB()
    mb.add(V, F, 0)
    g = mb.build("Ext_Ground", [M["snow"]], ctx.coll["ground"], outline=0.0, smooth=True)

    # ice sheet
    n = 96
    ring = [_lake_point(2 * math.pi * i / n) for i in range(n)]
    mb = _MB()
    mb.add([(p.x, p.y, 0.0) for p in ring] + [(LAKE_C[0], LAKE_C[1], 0.0)],
           [[i, (i + 1) % n, n] for i in range(n)], 0)
    ice = mb.build("Ext_Ice", [M["ice"]], ctx.coll["ground"], outline=0.0)

    # snow bank along the shore (drawn edge on the ice)
    prof = [(-0.4, -0.02), (-0.18, 0.1), (0.15, 0.2), (0.6, 0.13), (1.2, -0.06)]
    rings = []
    for k, (s, z) in enumerate(prof):
        rr = []
        for i in range(n):
            th = 2 * math.pi * i / n
            p = _lake_point(th, grow=s)
            wob = 0.03 * math.sin(i * 1.7) if 0 < k < len(prof) - 1 else 0.0
            rr.append((p.x, p.y, z + wob))
        rings.append(rr)
    mb = _MB()
    V = [p for r in rings for p in r]
    F = []
    for r in range(len(rings) - 1):
        a, b = r * n, (r + 1) * n
        for i in range(n):
            F.append([a + i, b + i, b + (i + 1) % n, a + (i + 1) % n])
    mb.add_closed(V, F, 0)
    bank = mb.build("Ext_LakeBank", [M["snow"]], ctx.coll["ground"], outline=0.02, smooth=True)

    # wind-swept snow patches on the ice
    rng = random.Random(21)
    mb = _MB()
    placed = 0
    tries = 0
    while placed < 18 and tries < 600:
        tries += 1
        cx = rng.uniform(LAKE_C[0] - LAKE_R[0], LAKE_C[0] + LAKE_R[0])
        cy = rng.uniform(LAKE_C[1] - LAKE_R[1], LAKE_C[1] + LAKE_R[1])
        R = rng.uniform(0.35, 1.5)
        if _lake_sd(cx, cy) > -(R * 2.2 + 0.8):
            continue
        if abs(cx - 0.6) < R * 2.2 + 1.0 and R > 0.7:   # only small floes under the k01 glide
            continue
        k = 14
        ang = rng.uniform(0, math.pi)
        pts = []
        for i in range(k):
            a = 2 * math.pi * i / k
            rr = R * (1 + 0.3 * math.sin(3 * a + ang * 3) + 0.16 * math.sin(5 * a + ang))
            x, y = rr * math.cos(a) * 2.2, rr * math.sin(a) * 0.55
            pts.append((cx + x * math.cos(ang) - y * math.sin(ang),
                        cy + x * math.sin(ang) + y * math.cos(ang)))
        mb.prism(pts, -0.01, 0.045, 0)
        placed += 1
    patches = mb.build("Ext_IcePatches", [M["icesnow"]], ctx.coll["ground"], outline=0.012)
    for ob in (g, ice, bank, patches):
        ob["ext_part"] = "ground"


def _fox_tracks(ctx, M):
    """Single-file fox prints from the treeline to the lowest step (k04)."""
    pts = [TREELINE, (7.5, -7.2), (4.8, -7.3), (2.8, -6.6), (DOOR_X + 0.1, STEP_FRONT_Y - 0.25)]
    mb = _MB()
    total = sum(math.dist(pts[i], pts[i + 1]) for i in range(len(pts) - 1))
    step = 0.3
    n = int(total / step)
    first = last = None
    for i in range(n + 1):
        (x, y), d = _poly_point(pts, i / n)
        side = 1 if i % 2 else -1
        nrm = Vector((-d.y, d.x))
        x += nrm.x * 0.045 * side
        y += nrm.y * 0.045 * side
        ang = math.atan2(d.y, d.x)
        k = 7
        oval = []
        for j in range(k):
            a = 2 * math.pi * j / k
            px, py = 0.045 * math.cos(a), 0.032 * math.sin(a)
            oval.append((x + px * math.cos(ang) - py * math.sin(ang),
                         y + px * math.sin(ang) + py * math.cos(ang), 0.006))
        mb.add(oval, [list(range(k))], 0)
        first = first or (x, y, 0.0)
        last = (x, y, 0.0)
    ob = mb.build("Ext_FoxTracks", [M["track"]], ctx.coll["ground"], outline=0.0, shadow=False)
    return ob, first, last


def _forest_path_decal(ctx, M):
    """A trodden strip of bluer snow along the dawn forest path (k11)."""
    mb = _MB()
    n = 90
    rng = random.Random(31)
    left, right = [], []
    for i in range(n + 1):
        (x, y), d = _poly_point(FOREST_PATH, i / n)
        nrm = Vector((-d.y, d.x))
        w = 0.55 + 0.12 * math.sin(i * 0.7) + rng.uniform(-0.05, 0.05)
        taper = min(1.0, i / 6.0)
        z = max(_ground_h(x, y), 0.0) + 0.012
        for side, lst in ((1, left), (-1, right)):
            px, py = x + nrm.x * w * side * taper, y + nrm.y * w * side * taper
            lst.append((px, py, max(_ground_h(px, py), 0.0) + 0.012))
    V = left + right
    F = [[i, i + 1, n + 2 + i, n + 1 + i] for i in range(n)]
    mb.add(V, F, 0)
    ob = mb.build("Ext_ForestPath", [M["path"]], ctx.coll["ground"], outline=0.0, shadow=False)
    ob.data.shade_smooth()
    return ob


# ─── House ──────────────────────────────────────────────────────────────────

def _window(trim, glass, centre, facing, w, h, pane_mat):
    """White frame + cross + sill + pane on a wall. facing in -Y/+X/-X/+Y."""
    ang = {"-Y": 0.0, "+X": math.pi / 2, "-X": -math.pi / 2, "+Y": math.pi}[facing]
    R = Matrix.Rotation(ang, 4, "Z")
    c = Vector(centre)

    def put(mb, size, a, out, b, mat=0, bevel=0.012):
        loc = c + (R @ Vector((a, -out, b)))
        mb.box(size, loc, (0, 0, ang), bevel=bevel, mat=mat)

    t = 0.1
    put(trim, (t, 0.07, h + 2 * t), -(w / 2 + t / 2), 0.035, 0)
    put(trim, (t, 0.07, h + 2 * t), (w / 2 + t / 2), 0.035, 0)
    put(trim, (w + 2 * t + 0.08, 0.09, t + 0.02), 0, 0.045, h / 2 + t / 2 + 0.01)
    put(trim, (w + 2 * t + 0.14, 0.16, 0.07), 0, 0.08, -h / 2 - 0.035)
    put(trim, (0.06, 0.05, h), 0, 0.03, 0, bevel=0.0)
    put(trim, (w, 0.05, 0.06), 0, 0.03, 0.08, bevel=0.0)
    put(glass, (w, 0.02, h), 0, 0.01, 0, mat=pane_mat, bevel=0.0)


def _slope_frame(side, ridge_y=0.0, apex=(0.0, RIDGE_Z), pitch=PITCH):
    """Unit vectors for one roof slope: d (down the slope), n (outward)."""
    c, s = math.cos(pitch), math.sin(pitch)
    if side > 0:
        d, n = Vector((c, 0, -s)), Vector((s, 0, c))
    else:
        d, n = Vector((-c, 0, -s)), Vector((-s, 0, c))
    R = Vector((apex[0], ridge_y, apex[1]))
    return R, d, n


def _roof_snow(mb, side, apex, pitch, half_w, y0, y1, L, seed, mat=0, thick=(0.15, 0.3)):
    """Snow blanket lying on one slope, with a scalloped lower edge."""
    R, d, n = _slope_frame(side, 0.0, apex, pitch)
    Y = Vector((0, 1, 0))
    rng = random.Random(seed)
    ph = rng.uniform(0, 6)
    cols = max(6, int((y1 - y0) / 0.45))
    wb, wt = thick
    rings = []
    for i in range(cols + 1):
        v = y0 + (y1 - y0) * i / cols
        u0 = -0.05
        u1 = L - 0.18 - (0.16 + 0.12 * math.sin(v * 2.1 + ph) + 0.07 * math.sin(v * 5.3 + 2 * ph))
        sec = [(u0, wb), (u1 - 0.05, wb), (u1 + 0.04, (wb + wt) * 0.5), (u1 - 0.1, wt), (u0, wt)]
        rings.append([R + d * u + Y * v + n * w for u, w in sec])
    mb.loft(rings, mat)


def _house(ctx, M):
    C = ctx.coll["house"]
    fz, ez, rz = FOUND_H, EAVE_Z, RIDGE_Z
    dl, dr, dt = DOOR_X - DOOR_W / 2, DOOR_X + DOOR_W / 2, FOUND_H + DOOR_H
    jy = -HD + 0.22

    # body: pentagon prism with a doorway notch and a lit reveal
    fr = [(-HW, fz), (dl, fz), (dl, dt), (dr, dt), (dr, fz), (HW, fz), (HW, ez), (0, rz), (-HW, ez)]
    bk = [(-HW, fz), (HW, fz), (HW, ez), (0, rz), (-HW, ez)]
    V = [(x, -HD, z) for x, z in fr] + [(x, HD, z) for x, z in bk]
    f = list(range(9))
    b = [9 + i for i in range(5)]
    j1, j2, j3, j4 = 14, 15, 16, 17
    V += [(dl, jy, fz), (dl, jy, dt), (dr, jy, dt), (dr, jy, fz)]
    faces = [
        (f, 0),
        ([b[0], b[4], b[3], b[2], b[1]], 0),
        ([f[5], b[1], b[2], f[6]], 0),
        ([b[0], f[0], f[8], b[4]], 0),
        ([f[6], b[2], b[3], f[7]], 0),
        ([f[7], b[3], b[4], f[8]], 0),
        ([f[0], b[0], b[1], f[5]], 0),
        ([f[1], j1, j2, f[2]], 1),
        ([f[4], f[3], j3, j4], 1),
        ([f[2], j2, j3, f[3]], 1),
        ([f[1], f[4], j4, j1], 1),
        ([j1, j4, j3, j2], 2),
    ]
    mb = _MB()
    mb.V = [tuple(v) for v in V]
    for fc, m in faces:
        mb.F.append(list(fc))
        mb.M.append(m)
    body = mb.build("Ext_HouseBody", [M["planks"], M["plaster"], M["doorglow"]], C, outline=0.03)

    # stone plinth
    mb = _MB()
    mb.box((2 * HW + 0.2, 2 * HD + 0.2, fz + 0.02), (0, 0, (fz + 0.02) / 2), bevel=0.03)
    mb.build("Ext_Plinth", [M["stone"]], C, outline=0.025)

    # roof slabs
    L = HW / math.cos(PITCH) + 0.5
    mb = _MB()
    for side in (1, -1):
        R, d, n = _slope_frame(side)
        centre = R + d * (L / 2 - 0.03) + n * 0.08
        mb.box((L, 2 * HD + 0.8, 0.16), centre, (0, side * PITCH, 0), bevel=0.03)
    roof = mb.build("Ext_Roof", [M["roof"]], C, outline=0.03)

    # snow on the roof + ridge cap + chimney snow + porch roof snow
    snow = _MB()
    for side, seed in ((1, 3), (-1, 4)):
        _roof_snow(snow, side, (0.0, RIDGE_Z), PITCH, HW, -HD - 0.42, HD + 0.42, L, seed)
    snow.cyl(0.2, -HD - 0.42, HD + 0.42, sides=7, mat=0,
             matrix=Matrix.Translation((0, 0, RIDGE_Z + 0.2)) @ Matrix.Rotation(-math.pi / 2, 4, "X"))

    # chimney
    cx, cy = 0.55, -1.2
    ch = _MB()
    ch.box((0.62, 0.62, 3.0), (cx, cy, 7.1), bevel=0.02, mat=0)
    ch.box((0.82, 0.82, 0.14), (cx, cy, 8.67), bevel=0.02, mat=1)
    ch.build("Ext_Chimney", [M["brick"], M["iron"]], C, outline=0.025)
    snow.box((0.8, 0.8, 0.14), (cx, cy, 8.8), bevel=0.06, mat=0)
    chimney_top = (cx, cy, 8.87)

    # porch (farstukvist): landing, steps, posts, small gable roof
    pz, pr = 2.62, 1.0
    p_pitch = math.radians(40)
    p_rz = pz + pr * math.tan(p_pitch)
    py0, py1 = -HD, -HD - LANDING_D - 0.07
    steps = _MB()
    steps.box((1.9, LANDING_D, FOUND_H), (DOOR_X, -HD - LANDING_D / 2, FOUND_H / 2), bevel=0.025)
    steps.box((1.6, STEP_D, 0.30), (DOOR_X, -HD - LANDING_D - STEP_D / 2, 0.15), bevel=0.025)
    steps.box((1.6, STEP_D, 0.15), (DOOR_X, -HD - LANDING_D - 1.5 * STEP_D, 0.075), bevel=0.025)
    steps.build("Ext_Steps", [M["steps"]], C, outline=0.022)
    for sx in (-1, 1):
        for yy, zz in ((-HD - LANDING_D - STEP_D / 2, 0.30), (-HD - LANDING_D - 1.5 * STEP_D, 0.15),
                       (-HD - LANDING_D + 0.12, FOUND_H)):
            snow.ico((DOOR_X + sx * 0.7, yy, zz + 0.02), (0.17, 0.13, 0.07))

    trim = _MB()
    glass = _MB()
    for sx in (-1, 1):
        trim.box((0.12, 0.12, pz - FOUND_H), (DOOR_X + sx * 0.85, -HD - LANDING_D + 0.2,
                                              (pz + FOUND_H) / 2), bevel=0.015)
    trim.box((2.1, 0.12, 0.15), (DOOR_X, -HD - LANDING_D + 0.2, pz - 0.02), bevel=0.015)
    Lp = pr / math.cos(p_pitch) + 0.2
    proof = _MB()
    for side in (1, -1):
        R, d, n = _slope_frame(side, 0.0, (DOOR_X, p_rz), p_pitch)
        cen = R + d * (Lp / 2 - 0.02) + n * 0.05 + Vector((0, (py0 + py1) / 2, 0))
        proof.box((Lp, py0 - py1 + 0.02, 0.1), cen, (0, side * p_pitch, 0), bevel=0.02)
        # barge boards on the porch gable
        cen_b = R + d * (Lp / 2 - 0.05) - n * 0.09 + Vector((0, py1 + 0.08, 0))
        trim.box((Lp, 0.05, 0.16), cen_b, (0, side * p_pitch, 0), bevel=0.01)
    proof.build("Ext_PorchRoof", [M["roof"]], C, outline=0.022)
    ped = _MB()
    tri = [(DOOR_X - pr, pz), (DOOR_X + pr, pz), (DOOR_X, p_rz)]
    ped.prism(tri, 0, 0.06, 0, matrix=Matrix.Translation((0, py1 + 0.12, 0)) @
              Matrix.Rotation(math.pi / 2, 4, "X"))
    ped.build("Ext_PorchGable", [M["planks"]], C, outline=0.02)
    for side, seed in ((1, 7), (-1, 8)):
        yy0, yy1 = py1 - 0.03, py0 - 0.05
        R, d, n = _slope_frame(side, 0.0, (DOOR_X, p_rz), p_pitch)
        Y = Vector((0, 1, 0))
        rng = random.Random(seed)
        rings = []
        cols = 5
        for i in range(cols + 1):
            v = yy0 + (yy1 - yy0) * i / cols
            u1 = Lp - 0.12 - (0.1 + 0.06 * math.sin(v * 5 + rng.uniform(0, 1)))
            sec = [(-0.04, 0.09), (u1 - 0.04, 0.09), (u1 + 0.03, 0.15), (u1 - 0.08, 0.21), (-0.04, 0.21)]
            rings.append([R + d * u + Y * v + n * w for u, w in sec])
        snow.loft(rings, 0)
    snow.cyl(0.1, py1 - 0.03, py0 - 0.05, sides=6, mat=0,
             matrix=Matrix.Translation((DOOR_X, 0, p_rz + 0.1)) @ Matrix.Rotation(-math.pi / 2, 4, "X"))

    # trim: corner boards, eave band, barge boards, door casing
    for sx in (-1, 1):
        for sy in (-1, 1):
            trim.box((0.17, 0.17, ez - fz), (sx * HW, sy * HD, (fz + ez) / 2), bevel=0.015)
    for sy in (-1, 1):
        trim.box((2 * HW + 0.24, 0.07, 0.17), (0, sy * (HD + 0.035), ez + 0.02), bevel=0.015)
        for side in (1, -1):
            R, d, n = _slope_frame(side, sy * (HD + 0.37))
            Lb = HW / math.cos(PITCH) + 0.42
            cen = R + d * (Lb / 2 - 0.02) - n * 0.1
            trim.box((Lb, 0.07, 0.22), cen, (0, side * PITCH, 0), bevel=0.012)
    trim.box((0.13, 0.06, DOOR_H + 0.13), (dl - 0.065, -HD - 0.03, fz + (DOOR_H + 0.13) / 2), bevel=0.01)
    trim.box((0.13, 0.06, DOOR_H + 0.13), (dr + 0.065, -HD - 0.03, fz + (DOOR_H + 0.13) / 2), bevel=0.01)
    trim.box((DOOR_W + 0.34, 0.08, 0.14), (DOOR_X, -HD - 0.04, dt + 0.07), bevel=0.012)

    # windows (glass mesh: material 0 = dark glass, 1 = warm glow)
    _window(trim, glass, (WIN_X, -HD, WIN_SILL + WIN_H / 2), "-Y", WIN_W, WIN_H, 1)
    _window(trim, glass, (0.0, -HD, 4.55), "-Y", 0.78, 0.88, 0)
    _window(trim, glass, (HW, -1.3, 1.9), "+X", 1.0, 1.1, 0)
    _window(trim, glass, (HW, 1.6, 1.9), "+X", 1.0, 1.1, 0)
    _window(trim, glass, (-HW, -1.3, 1.9), "-X", 1.0, 1.1, 1)
    _window(trim, glass, (-HW, 1.6, 1.9), "-X", 1.0, 1.1, 0)
    _window(trim, glass, (0.9, HD, 1.9), "+Y", 1.0, 1.1, 0)
    _window(trim, glass, (0.0, HD, 4.55), "+Y", 0.78, 0.88, 0)
    trim.build("Ext_Trim", [M["trim"]], C, outline=0.016)
    glass.build("Ext_Windows", [M["glass"], M["glow"]], C, outline=0.0)
    snow.build("Ext_RoofSnow", [M["snow"]], C, outline=0.025, smooth=False)

    # door leaf, pivot on the hinge
    lw = DOOR_W - 0.03
    leaf = _MB()
    leaf.box((lw, 0.05, DOOR_H - 0.01), (lw / 2, 0, (DOOR_H - 0.01) / 2), bevel=0.012, mat=0)
    leaf.ico((lw - 0.12, -0.05, 1.0), (0.035, 0.035, 0.035), mat=1)
    door = leaf.build("Ext_DoorLeaf", [M["door"], M["iron"]], C, outline=0.015)
    door.location = (dl + 0.015, -HD + 0.03, FOUND_H + 0.005)

    # wall lantern right of the door
    lx, ly, lz = DOOR_X + 0.72, -HD - 0.16, 2.05
    lan = _MB()
    lan.box((0.2, 0.2, 0.05), (lx, ly, lz - 0.14), bevel=0.01, mat=1)
    lan.box((0.24, 0.24, 0.06), (lx, ly, lz + 0.15), bevel=0.01, mat=1)
    lan.cyl(0.13, lz + 0.18, lz + 0.3, sides=4, mat=1, r_top=0.02,
            matrix=Matrix.Translation((lx, ly, 0)) @ Matrix.Rotation(math.pi / 4, 4, "Z"))
    lan.box((0.04, 0.16, 0.04), (lx, ly + 0.1, lz + 0.1), mat=1)
    lan.box((0.15, 0.15, 0.24), (lx, ly, lz), mat=0)
    lan.build("Ext_Lantern", [M["lantern"], M["iron"]], C, outline=0.012)

    # warm light pool on the snow under the lit window
    pool = _MB()
    y_near, y_far = -HD - 0.15, -HD - 1.9
    xa, xb = WIN_X - 0.55, WIN_X + 0.55
    xc, xd = WIN_X - 0.8, WIN_X + 0.95
    gap = 0.07

    def lerp(a, b, t):
        return a + (b - a) * t
    for (u0, u1) in ((0.0, 0.5 - gap / 2), (0.5 + gap / 2, 1.0)):
        for (t0, t1) in ((0.0, 0.5 - gap / 2), (0.5 + gap / 2, 1.0)):
            q = []
            for (u, t) in ((u0, t0), (u1, t0), (u1, t1), (u0, t1)):
                y = lerp(y_near, y_far, t)
                x = lerp(lerp(xa, xc, t), lerp(xb, xd, t), u)
                q.append((x, y, 0.008))
            pool.add(q, [[0, 1, 2, 3]], 0)
    pool.build("Ext_WindowPool", [M["pool"]], C, outline=0.0, shadow=False)

    return {"chimney_top": chimney_top, "lantern": (lx, ly, lz), "body": body, "door": door}


# ─── Forest ─────────────────────────────────────────────────────────────────

PINES = {  # key: (height, tiers, base radius / height, outline)
    "S": (2.6, 3, 0.40, 0.02),
    "M": (5.2, 4, 0.36, 0.03),
    "L": (8.2, 5, 0.33, 0.04),
    "XL": (11.8, 6, 0.30, 0.05),
}


def _pine_mesh(ctx, M, key):
    h, tiers, wr, _ = PINES[key]
    rng = random.Random({"S": 1, "M": 2, "L": 3, "XL": 4}[key])
    mb = _MB()
    trunk_top = h * 0.32
    mb.cyl(max(0.07, 0.03 * h), -0.3, trunk_top, sides=6, mat=2, r_top=max(0.05, 0.02 * h))
    crown_b = h * 0.13
    R0 = h * wr
    sides = 10
    for i in range(tiers):
        t = i / tiers
        zb = crown_b + (h - crown_b) * 0.8 * t
        zt = h if i == tiers - 1 else crown_b + (h - crown_b) * 0.8 * (i + 1) / tiers + (h - crown_b) * 0.2
        zt = min(zt, h)
        th = zt - zb
        r = R0 * (1 - 0.78 * t)
        rot = rng.uniform(0, math.pi)
        # green tier: jagged skirt, apex, concave underside
        ring = []
        for j in range(sides):
            a = rot + 2 * math.pi * j / sides
            rr = r * (1.0 if j % 2 == 0 else 0.84)
            zz = zb + (0.0 if j % 2 == 0 else 0.1 * th)
            ring.append((rr * math.cos(a), rr * math.sin(a), zz))
        V = ring + [(0, 0, zt), (0, 0, zb + 0.28 * th)]
        apex, under = sides, sides + 1
        F = [[j, (j + 1) % sides, apex] for j in range(sides)]
        F += [[(j + 1) % sides, j, under] for j in range(sides)]
        mb.add(V, F, 0)
        # snow cap: scalloped cone on the upper part of the tier
        ns = 2 * sides
        cap = []
        for j in range(ns):
            a = rot + 2 * math.pi * j / ns
            drop = 0.5 + (0.22 if j % 2 == 0 else 0.0) + rng.uniform(-0.05, 0.05)
            zz = zt - th * drop
            rr = r * (zt - zz) / th * 1.07 + 0.02 * h ** 0.5
            cap.append((rr * math.cos(a), rr * math.sin(a), zz))
        V = cap + [(0, 0, zt + 0.035 * th)]
        F = [[j, (j + 1) % ns, ns] for j in range(ns)]
        mb.add(V, F, 1)
    me = bpy.data.meshes.new(f"{ctx.p}Pine{key}")
    me.from_pydata(mb.V, [], mb.F)
    me.update(calc_edges=True)
    me.polygons.foreach_set("material_index", mb.M)
    for m in (M["pine"], M["snow"], M["bark"]):
        me.materials.append(m)
    return me


FRAMING = [  # hand-placed trees: (x, y, size, scale)
    (-8.6, -10.2, "XL", 1.05), (8.6, -12.9, "XL", 1.1), (-11.6, -13.8, "L", 1.0),
    (12.8, -14.2, "M", 1.0), (-6.9, 3.4, "L", 1.0), (-8.3, -1.6, "M", 1.0),
    (7.3, 3.9, "L", 1.05), (8.5, -1.8, "M", 0.95), (5.8, 7.8, "XL", 1.0),
    (-4.8, 8.3, "XL", 1.05), (1.2, 9.6, "L", 1.0), (-9.6, 7.0, "L", 1.1),
    (11.4, -3.9, "L", 1.0), (11.9, -9.4, "M", 1.0), (13.4, -8.2, "S", 1.0),
    (-12.2, -4.2, "M", 1.0), (-12.8, -9.2, "S", 1.1),
]
KEEP_CLEAR = [  # camera spots (x, y, radius)
    (11.8, -8.6, 1.6), (-2.2, -9.6, 1.5), (-2.2, -8.8, 1.2), (4.6, -8.0, 1.5),
]


def _forest_density(x, y):
    r = math.hypot(x, y + 4.0)
    if r > 66:
        return 0.0
    if _yard_sd(x, y) < 0.0:
        return 0.0
    if _lake_sd(x, y) < 3.0:
        return 0.0
    if _poly_dist((x, y), NELL_LANE) < 2.6:
        return 0.0
    if _poly_dist((x, y), FOREST_PATH) < 2.2:
        return 0.0
    for cx, cy, cr in KEEP_CLEAR:
        if math.hypot(x - cx, y - cy) < cr + 1.5:
            return 0.0
    base = 0.92 if y > 6.0 else (0.75 if y > -12.0 else 0.55)
    if y < -30:
        base = 0.62
    base *= 1.0 - _smooth(r, 50.0, 66.0)
    base *= _smooth(_yard_sd(x, y), 0.0, 2.5) * 0.6 + 0.4
    return base


def _forest(ctx, M):
    C = ctx.coll["forest"]
    meshes = {k: _pine_mesh(ctx, M, k) for k in PINES}
    rng = random.Random(1234)
    spots = []
    grid = {}

    def free(x, y, dmin):
        gx, gy = int(math.floor(x / 3)), int(math.floor(y / 3))
        for i in range(gx - 1, gx + 2):
            for j in range(gy - 1, gy + 2):
                for (px, py) in grid.get((i, j), ()):
                    if math.hypot(px - x, py - y) < dmin:
                        return False
        return True

    def clear_of_cameras(x, y, key, s):
        rad = PINES[key][0] * PINES[key][2] * s
        return all(math.hypot(x - cx, y - cy) > cr + rad * 0.9 for cx, cy, cr in KEEP_CLEAR)

    def put(x, y, key, s, rot):
        if not clear_of_cameras(x, y, key, s):
            return
        spots.append((x, y, key, s, rot))
        grid.setdefault((int(math.floor(x / 3)), int(math.floor(y / 3))), []).append((x, y))

    for x, y, key, s in FRAMING:
        put(x, y, key, s, rng.uniform(0, 6.28))
    # trees lining the dawn forest path, alternating sides
    n = 16
    for i in range(1, n):
        (x, y), d = _poly_point(FOREST_PATH, i / n)
        side = 1 if i % 2 else -1
        off = rng.uniform(2.5, 3.5)
        px, py = x - d.y * off * side, y + d.x * off * side
        key = rng.choice(["M", "L", "L", "XL", "S"])
        if free(px, py, 2.0):
            put(px, py, key, rng.uniform(0.9, 1.15), rng.uniform(0, 6.28))
    step = 3.2
    for gy in range(int(-66 / step), int(80 / step) + 1):
        for gx in range(int(-72 / step), int(72 / step) + 1):
            x = gx * step + rng.uniform(-1.3, 1.3)
            y = gy * step + rng.uniform(-1.3, 1.3)
            dens = _forest_density(x, y)
            roll = rng.random()
            key_roll = rng.random()
            s = rng.uniform(0.85, 1.18)
            rot = rng.uniform(0, 6.28)
            if roll > dens or not free(x, y, 2.3):
                continue
            edge = min(_yard_sd(x, y), _lake_sd(x, y), _poly_dist((x, y), FOREST_PATH),
                       _poly_dist((x, y), NELL_LANE))
            if edge < 7.0:
                w = (("S", 0.22), ("M", 0.38), ("L", 0.28), ("XL", 0.12))
            else:
                w = (("S", 0.05), ("M", 0.22), ("L", 0.4), ("XL", 0.33))
            acc = 0.0
            key = w[-1][0]
            for k, p in w:
                acc += p
                if key_roll < acc:
                    key = k
                    break
            put(x, y, key, s, rot)

    for i, (x, y, key, s, rot) in enumerate(spots):
        ob = bpy.data.objects.new(f"Ext_Pine{key}.{i:03d}", meshes[key])
        C.objects.link(ob)
        ob.location = (x, y, max(0.0, _ground_h(x, y)) - 0.05)
        ob.rotation_euler = (0, 0, rot)
        ob.scale = (s, s, s * rng.uniform(0.95, 1.08))
        T.outline(ob, PINES[key][3])
        ob["ext_ink"] = PINES[key][3]
    return len(spots)


def _far_treelines(ctx, M):
    """Two cheap jagged silhouette rings that close the horizon."""
    C = ctx.coll["forest"]
    rng = random.Random(99)
    for name, radius, hmin, hmax, mat, step in (("Ext_FarTrees1", 82.0, 9.0, 17.0, "far1", 1.3),
                                                ("Ext_FarTrees2", 150.0, 14.0, 30.0, "far2", 1.0)):
        mb = _MB()
        n = int(360 / step)
        for i in range(n):
            a0 = math.radians(i * step + rng.uniform(-0.3, 0.3))
            w = math.radians(step * rng.uniform(0.9, 1.6))
            rr = radius + rng.uniform(-6, 6)
            hh = rng.uniform(hmin, hmax)
            cx, cy = 0.0, -4.0
            p0 = (cx + rr * math.sin(a0 - w), cy + rr * math.cos(a0 - w), -2.0)
            p1 = (cx + rr * math.sin(a0 + w), cy + rr * math.cos(a0 + w), -2.0)
            p2 = (cx + rr * math.sin(a0), cy + rr * math.cos(a0), hh)
            # a stacked spruce silhouette: a thin triangle plus two side notches
            mid = hh * 0.45
            q0 = (cx + rr * math.sin(a0 - w * 0.55), cy + rr * math.cos(a0 - w * 0.55), mid)
            q1 = (cx + rr * math.sin(a0 + w * 0.55), cy + rr * math.cos(a0 + w * 0.55), mid)
            mb.add([p0, p1, q1, p2, q0], [[0, 1, 2, 3, 4]], 0)
        ob = mb.build(name, [M[mat]], C, outline=0.0, shadow=False)
        ob.data.materials[0].use_backface_culling = False


# ─── Sky: moon, stars, aurora ───────────────────────────────────────────────

MOON_POS = Vector((-62.0, 190.0, 80.0))
MOON_R = 17.0


def _facing_matrix(pos, target=(0, -6, 2)):
    q = (Vector(target) - pos).to_track_quat("Z", "Y")
    return Matrix.Translation(pos) @ q.to_matrix().to_4x4()


def _moon(ctx):
    C = ctx.coll["sky"]
    mat = ctx.mat("Moon", MOON, flat=True, emission=0.35)
    R = MOON_R
    c, r = Vector((0.5 * R, 0.28 * R)), 0.9 * R
    d, phi = c.length, math.atan2(c.y, c.x)
    alpha = math.acos((R * R - r * r + d * d) / (2 * d) / R)
    no, ni = 56, 44
    poly = []
    for i in range(no + 1):
        t = phi + alpha + (2 * math.pi - 2 * alpha) * i / no
        poly.append((R * math.cos(t), R * math.sin(t)))

    def inner_angle(t):
        q = Vector((R * math.cos(t), R * math.sin(t))) - c
        return (math.atan2(q.y, q.x) - phi) % (2 * math.pi)
    g1, g2 = inner_angle(phi + alpha), inner_angle(phi - alpha)
    for i in range(1, ni):
        t = phi + g2 + (g1 - g2) * i / ni
        poly.append((c.x + r * math.cos(t), c.y + r * math.sin(t)))
    mb = _MB()
    M4 = _facing_matrix(MOON_POS)
    mb.prism(poly, -0.6, 0.6, 0, matrix=M4)
    moon = mb.build("Ext_Moon", [mat], C, outline=0.35, shadow=False)

    # soft halo disc behind it
    halo_m = ctx.mat("MoonHalo", MOON, flat=True, emission=0.2)
    if not halo_m.get("ext_alpha"):
        nt = halo_m.node_tree
        tc = nt.nodes.new("ShaderNodeTexCoord")
        dist = nt.nodes.new("ShaderNodeVectorMath")
        dist.operation = "LENGTH"
        nt.links.new(tc.outputs["Object"], dist.inputs[0])
        a = _math(nt, "DIVIDE", dist.outputs["Value"], vb=R * 2.6)
        a = _math(nt, "SUBTRACT", va=1.0, b=a, clamp=True)
        a = _math(nt, "POWER", a, vb=2.2)
        a = _math(nt, "MULTIPLY", a, vb=0.32)
        _make_transparent(halo_m, a)
        halo_m["ext_alpha"] = True
    mb = _MB()
    k = 40
    ring = [(R * 2.6 * math.cos(2 * math.pi * i / k), R * 2.6 * math.sin(2 * math.pi * i / k), -3.0)
            for i in range(k)]
    mb.add(ring + [(0, 0, -3.0)], [[i, (i + 1) % k, k] for i in range(k)], 0)
    halo = mb.build("Ext_MoonHalo", [halo_m], C, outline=0.0, shadow=False)
    halo.matrix_world = M4
    return moon


def _stars(ctx):
    C = ctx.coll["sky"]
    mat = ctx.mat("Star", STAR, flat=True, emission=1.2)
    rng = random.Random(5)
    mb = _MB()
    dome = 420.0
    for i in range(340):
        e = math.asin(rng.uniform(math.sin(math.radians(9)), math.sin(math.radians(86))))
        az = rng.uniform(0, 2 * math.pi)
        p = Vector((math.cos(e) * math.sin(az), math.cos(e) * math.cos(az), math.sin(e))) * dome
        s = 0.3 + 1.1 * rng.random() ** 3
        V = [p + Vector(v) * s for v in ((1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1))]
        F = [[0, 2, 4], [2, 1, 4], [1, 3, 4], [3, 0, 4], [2, 0, 5], [1, 2, 5], [3, 1, 5], [0, 3, 5]]
        mb.add(V, F, 0)
    # a few four-point sparkles like in the illustrations
    for i in range(16):
        e = math.radians(rng.uniform(14, 70))
        az = rng.uniform(-1.4, 1.4) if i < 11 else rng.uniform(0, 2 * math.pi)
        p = Vector((math.cos(e) * math.sin(az), math.cos(e) * math.cos(az), math.sin(e))) * dome
        s = rng.uniform(2.0, 3.4)
        M4 = _facing_matrix(p, (0, 0, 0))
        pts = []
        for j in range(8):
            a = math.pi / 2 * (j // 2) + (math.pi / 4 if j % 2 else 0)
            rr = s if j % 2 == 0 else s * 0.28
            pts.append(M4 @ Vector((rr * math.cos(a), rr * math.sin(a), 0)))
        mb.add(pts + [M4 @ Vector((0, 0, 0))], [[j, (j + 1) % 8, 8] for j in range(8)], 0)
    ob = mb.build("Ext_Stars", [mat], C, outline=0.0, shadow=False)
    mat.use_backface_culling = False
    return ob


def _aurora(ctx):
    C = ctx.coll["sky"]
    mat = ctx.mat("Aurora", AURORA, flat=True, emission=0.5)
    if not mat.get("ext_alpha"):
        nt = mat.node_tree
        tc = nt.nodes.new("ShaderNodeTexCoord")
        sep = nt.nodes.new("ShaderNodeSeparateXYZ")
        nt.links.new(tc.outputs["UV"], sep.inputs[0])
        u, v = sep.outputs["X"], sep.outputs["Y"]
        fade = _math(nt, "SUBTRACT", va=1.0, b=v, clamp=True)
        fade = _math(nt, "POWER", fade, vb=1.25)
        foot = _math(nt, "MULTIPLY", v, vb=6.0, clamp=True)
        comb = nt.nodes.new("ShaderNodeCombineXYZ")
        nt.links.new(_math(nt, "MULTIPLY", u, vb=26.0), comb.inputs["X"])
        nt.links.new(_math(nt, "MULTIPLY", v, vb=0.6), comb.inputs["Y"])
        nz = nt.nodes.new("ShaderNodeTexNoise")
        nz.inputs["Scale"].default_value = 1.0
        nz.inputs["Detail"].default_value = 2.0
        nt.links.new(comb.outputs[0], nz.inputs["Vector"])
        # slow shimmer of the rays: 4D noise whose W follows the frame
        try:
            nz.noise_dimensions = "4D"
            fc = nz.inputs["W"].driver_add("default_value")
            fc.driver.type = "SCRIPTED"
            fc.driver.expression = "frame * 0.012"
        except (AttributeError, TypeError, KeyError):
            pass
        rays = nt.nodes.new("ShaderNodeMapRange")
        rays.inputs["From Min"].default_value = 0.32
        rays.inputs["From Max"].default_value = 0.7
        rays.inputs["To Min"].default_value = 0.3
        rays.inputs["To Max"].default_value = 1.0
        nt.links.new(nz.outputs["Fac"], rays.inputs["Value"])
        e0 = _math(nt, "MULTIPLY", u, vb=7.0, clamp=True)
        e1 = _math(nt, "MULTIPLY", _math(nt, "SUBTRACT", va=1.0, b=u), vb=7.0, clamp=True)
        a = _math(nt, "MULTIPLY", fade, rays.outputs[0])
        a = _math(nt, "MULTIPLY", a, foot)
        a = _math(nt, "MULTIPLY", a, e0)
        a = _math(nt, "MULTIPLY", a, e1)
        a = _math(nt, "MULTIPLY", a, vb=0.9)
        _make_transparent(mat, a)
        mat["ext_alpha"] = True

    ribbons = [  # az0, az1 (deg from north, +east), radius, base z, height, phase
        (-80, -14, 190, 16.0, 80, 0.3),
        (-32, 30, 230, 24.0, 100, 1.7),
        (16, 72, 178, 14.0, 66, 3.1),
    ]
    obs = []
    for k, (a0, a1, R, zb, H, ph) in enumerate(ribbons):
        bm = bmesh.new()
        uv = bm.loops.layers.uv.new("UVMap")
        seg = 56
        rows = (0.0, 0.3, 1.0)
        grid = []
        for i in range(seg + 1):
            t = i / seg
            az = math.radians(a0 + (a1 - a0) * t)
            rr = R + 14 * math.sin(t * math.pi * 2.3 + ph)
            z0 = zb + 3.5 * math.sin(t * 7.0 + ph)
            hh = H * (0.62 + 0.38 * math.sin(t * math.pi * 1.6 + ph * 2))
            col = []
            for v in rows:
                r2 = rr + 10.0 * v
                col.append(bm.verts.new((r2 * math.sin(az), r2 * math.cos(az) - 4.0, z0 + hh * v)))
            grid.append(col)
        for i in range(seg):
            for j in range(len(rows) - 1):
                f = bm.faces.new((grid[i][j], grid[i + 1][j], grid[i + 1][j + 1], grid[i][j + 1]))
                for loop, (ii, jj) in zip(f.loops, ((i, j), (i + 1, j), (i + 1, j + 1), (i, j + 1))):
                    loop[uv].uv = (ii / seg, rows[jj])
        me = bpy.data.meshes.new(f"Ext_Aurora{k + 1}")
        bm.to_mesh(me)
        bm.free()
        me.materials.append(mat)
        ob = bpy.data.objects.new(f"Ext_Aurora{k + 1}", me)
        C.objects.link(ob)
        ob.visible_shadow = False
        obs.append(ob)
    return obs


def _world(ctx):
    sc, v = ctx.sc, ctx.variant
    if v == "dawn":
        w = T.sky(sc, top=(120, 160, 205), horizon=(250, 206, 170), name=ctx.p + "Sky")
        ramp = _node(w.node_tree, "ShaderNodeValToRGB")
        el = ramp.color_ramp.elements
        el[0].position, el[0].color = 0.0, T.lin((252, 200, 160))
        el[1].position, el[1].color = 0.55, T.lin((112, 152, 200))
        mid = el.new(0.12)
        mid.color = T.lin((240, 220, 200))
        ambient = 0.3
    elif v == "memory":
        w = T.sky(sc, top=(14, 20, 38), horizon=(52, 66, 96), name=ctx.p + "Sky")
        ramp = _node(w.node_tree, "ShaderNodeValToRGB")
        ramp.color_ramp.elements[0].position = 0.02
        ramp.color_ramp.elements[1].position = 0.55
        ambient = 1.0
    else:
        w = T.sky(sc, top=SKY_TOP, horizon=SKY_HORIZON, name=ctx.p + "Sky")
        ramp = _node(w.node_tree, "ShaderNodeValToRGB")
        el = ramp.color_ramp.elements
        el[0].position = 0.02
        el[1].position = 0.55
        ambient = 1.0
    # the camera sees the full sky; diffuse lighting only a fraction of it
    nt = w.node_tree
    bg = _node(nt, "ShaderNodeBackground")
    out = _node(nt, "ShaderNodeOutputWorld")
    if ambient != 1.0 and bg is not None:
        src = next(l.from_socket for l in nt.links if l.to_socket == bg.inputs["Color"])
        bg2 = nt.nodes.new("ShaderNodeBackground")
        bg2.inputs["Strength"].default_value = ambient
        nt.links.new(src, bg2.inputs["Color"])
        lp = nt.nodes.new("ShaderNodeLightPath")
        mix = nt.nodes.new("ShaderNodeMixShader")
        nt.links.new(lp.outputs["Is Camera Ray"], mix.inputs[0])
        nt.links.new(bg2.outputs[0], mix.inputs[1])
        nt.links.new(bg.outputs[0], mix.inputs[2])
        nt.links.new(mix.outputs[0], out.inputs["Surface"])
    return w


def _sun_angles(from_dir):
    """Euler (degrees) for T.moonlight so the light comes FROM `from_dir`."""
    e = Vector(from_dir).normalized().to_track_quat("Z", "Y").to_euler()
    return tuple(math.degrees(a) for a in e)


def _lights(ctx, house):
    sc, v = ctx.sc, ctx.variant
    if v == "dawn":
        sun = T.moonlight(sc, energy=7.0, color=(255, 238, 220),
                          angle=_sun_angles((0.7, -0.6, 0.46)))
        sun.data.angle = math.radians(6)
    elif v == "memory":
        sun = T.moonlight(sc, energy=2.6, color=(175, 190, 230),
                          angle=_sun_angles((-0.55, -0.62, 0.72)))
    else:
        sun = T.moonlight(sc, energy=2.8, color=(170, 190, 255),
                          angle=_sun_angles((-0.55, -0.62, 0.72)))
    ctx.light(sun, "Ext_Moonlight" if v != "dawn" else "Ext_Sun")
    win = T.warm_light(sc, (WIN_X, -HD - 0.45, WIN_SILL + WIN_H / 2 - 0.1),
                       energy=90.0 if v != "dawn" else 30.0, radius=0.5, name="Ext_WindowLight")
    ctx.light(win, "Ext_WindowLight")
    lx, ly, lz = house["lantern"]
    lan = T.warm_light(sc, (lx, ly - 0.2, lz), energy=35.0 if v != "dawn" else 0.0,
                       radius=0.15, name="Ext_LanternLight")
    ctx.light(lan, "Ext_LanternLight")
    return sun


# ─── Snow ───────────────────────────────────────────────────────────────────

def snow_systems(sc):
    """All exterior snow particle settings in the scene."""
    out = []
    for ob in sc.objects:
        for ps in getattr(ob, "particle_systems", ()):
            if ps.settings.get("ext_snow"):
                out.append(ps.settings)
    return out


def set_snow_speed(sc, value, frame=None):
    """Keyframe the snowfall speed (particle time_tweak) at `frame`.

    1.0 = normal fall (~0.9 m/s); k08: e.g. set_snow_speed(sc, 1.0, 24) then
    set_snow_speed(sc, 0.05, 150) and the flakes slow almost to a stop.
    The particle cache is re-simulated from the pre-roll on the next
    frame change (render frames in order, or call sc.frame_set on each).
    """
    f = sc.frame_current if frame is None else frame
    sts = snow_systems(sc)
    for st in sts:
        st.time_tweak = value
        st.keyframe_insert("time_tweak", frame=f)
    _reset_snow(sc)
    return sts


def fit_ink(sc, cam=None, px=14.0, frame=None, lo=0.004, hi=0.3):
    """Make the exterior ink lines ~`px` pixels wide (at 1280 px width) as
    seen from `cam` (default: scene camera), whatever the distance.

    A fixed outline thickness in metres reads as a heavy line at 5 m and
    vanishes at 25 m; this sets every exterior "Outline" modifier from the
    object's distance to the camera (nearest point of its bounding box).
    Small parts (trim, lumps) keep their thinner base ratio. With `frame`,
    the thickness is keyframed there, so a camera move (k01 glide) can get
    one call at its first and one at its last frame.
    Only objects built by this module (custom prop "ext_ink") are touched.
    """
    cam = cam or sc.camera
    if cam is None:
        return 0
    back = sc.frame_current
    if frame is not None:
        sc.frame_set(frame)
    for vl in sc.view_layers:       # fresh matrix_world for camera and objects
        vl.update()
    res = sc.render.resolution_x * sc.render.resolution_percentage / 100.0
    cd = cam.data
    ppr = res * cd.lens / max(cd.sensor_width, 1e-3)       # pixels per radian
    px_here = px * res / 1280.0
    cpos = cam.matrix_world.translation
    n = 0
    for ob in sc.objects:
        base = ob.get("ext_ink")
        mod = ob.modifiers.get("Outline") if base else None
        if mod is None:
            continue
        bb = [ob.matrix_world @ Vector(c) for c in ob.bound_box]
        mn = [min(v[i] for v in bb) for i in range(3)]
        mx = [max(v[i] for v in bb) for i in range(3)]
        q = Vector([max(mn[i], min(cpos[i], mx[i])) for i in range(3)])
        d = max((q - cpos).length, 0.3)
        weight = max(0.75, min(1.0, base / 0.025))
        scale = max(abs(s) for s in ob.scale) or 1.0
        dims = sorted(x for x in ob.dimensions if x > 1e-4)
        cap = min(hi, 0.35 * dims[0]) if dims else hi
        mod.thickness = max(lo, min(cap, px_here * d / ppr * weight)) / scale
        if frame is not None:
            mod.keyframe_insert("thickness", frame=frame)
        n += 1
    if frame is not None and frame != back:
        sc.frame_set(back)
        _reset_snow(sc)             # the jump left a non-continuous snow cache
    return n


def _reset_snow(sc):
    """Throw away the snow particle cache (it re-simulates from its first frame)."""
    for st in snow_systems(sc):
        st.brownian_factor = st.brownian_factor


def prime_snow(sc, frame):
    """Step the scene frame by frame from the snow start up to `frame`.

    Unbaked particles are only correct when frames are evaluated in order.
    Rendering an animation (-a, or render(animation=True)) from the shot's
    first frame does that by itself; call this before rendering a single
    still at a later frame (or after jumping around the timeline).
    """
    starts = [int(st.frame_start) for st in snow_systems(sc)]
    f0 = min(starts) if starts else sc.frame_start
    for f in range(f0, int(frame) + 1):
        sc.frame_set(f)


def _snow_settings(ctx, name, flake, count, f0, f1, life, speed, velocity):
    st = bpy.data.particles.new(name)
    st["ext_snow"] = True
    st.count = max(10, int(count))
    st.frame_start = f0
    st.frame_end = f1
    st.lifetime = life
    st.distribution = "RAND"
    st.use_emit_random = True
    st.physics_type = "NEWTON"
    st.normal_factor = 0.0
    st.object_align_factor = velocity          # object space = world (no rotation)
    st.factor_random = 0.1
    st.brownian_factor = 0.9
    st.effector_weights.gravity = 0.0
    st.render_type = "OBJECT"
    st.instance_object = flake
    st.particle_size = 0.03
    st.size_random = 0.5
    st.time_tweak = speed
    st.display_percentage = 100
    try:
        st.display_method = "DOT"
    except TypeError:
        pass
    return st


def _snow(ctx, M, density=1.0, speed=1.0, wind=0.0, frame_start=1, frame_end=600):
    """Falling snow = two particle systems sharing one flake:
    - Ext_SnowFill: a box filling the whole air volume, emitting ALL its
      flakes on `frame_start` (so the snow is already falling on the first
      frame, no negative-frame pre-roll, which Blender does not keep);
    - Ext_SnowEmitter: a plane at the top that keeps feeding new flakes.
    Flakes fall at SNOW_FALL m/s (x time_tweak), drift with `wind` toward -Y
    and wobble (brownian). They sink under the ground when they land."""
    C = ctx.coll["snow"]
    fps = ctx.sc.render.fps or 24
    fall_frames = int(SNOW_TOP / SNOW_FALL * fps)
    drift = wind * SNOW_TOP / SNOW_FALL
    x0, x1, y0, y1 = -26.0, 44.0, -34.0, 26.0 + drift
    w, h = x1 - x0, y1 - y0
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2

    fm = bpy.data.meshes.new("Ext_Flake")
    bm = bmesh.new()
    bmesh.ops.create_icosphere(bm, subdivisions=1, radius=1.0)
    bm.to_mesh(fm)
    bm.free()
    fm.materials.append(M["flake"])
    flake = bpy.data.objects.new("Ext_Flake", fm)
    C.objects.link(flake)
    flake.location = (0, 0, -60)
    flake.visible_shadow = False

    density = 0.16 * density                             # flakes per m^3
    velocity = (0.0, -wind, -SNOW_FALL)
    life = fall_frames + 14

    # top plane: steady feed
    me = bpy.data.meshes.new("Ext_SnowEmitter")
    me.from_pydata([(-w / 2, -h / 2, 0), (w / 2, -h / 2, 0), (w / 2, h / 2, 0), (-w / 2, h / 2, 0)],
                   [], [[0, 1, 2, 3]])
    top = bpy.data.objects.new("Ext_SnowEmitter", me)
    C.objects.link(top)
    top.location = (cx, cy, SNOW_TOP)
    rate = density * w * h * SNOW_FALL / fps               # flakes per frame
    st = _snow_settings(ctx, ctx.p + "Snow", flake, rate * (frame_end - frame_start + 1),
                        frame_start, frame_end, life, speed, velocity)
    st.emit_from = "FACE"

    # volume fill: everything at once on the first frame
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    bmesh.ops.scale(bm, vec=Vector((w, h, SNOW_TOP)), verts=bm.verts)
    fill_me = bpy.data.meshes.new("Ext_SnowFill")
    bm.to_mesh(fill_me)
    bm.free()
    fill = bpy.data.objects.new("Ext_SnowFill", fill_me)
    C.objects.link(fill)
    fill.location = (cx, cy, SNOW_TOP / 2)
    st2 = _snow_settings(ctx, ctx.p + "SnowFill", flake, density * w * h * SNOW_TOP,
                         frame_start, frame_start, life, speed, velocity)
    st2.emit_from = "VOLUME"

    for ob, settings, seed in ((top, st, 11), (fill, st2, 12)):
        ob.show_instancer_for_render = False
        ob.show_instancer_for_viewport = False
        ob.visible_shadow = False
        mod = ob.modifiers.new("Snow", "PARTICLE_SYSTEM")
        mod.particle_system.settings = settings
        mod.particle_system.seed = seed
        pc = mod.particle_system.point_cache
        pc.frame_start = frame_start
        pc.frame_end = frame_end
    return top


# ─── Memory tint (scene-level compositor) ───────────────────────────────────

def apply_memory_tint(sc, saturation=0.12, tint=(0.56, 0.74, 1.12), lift=(0.01, 0.025, 0.07),
                      vignette=0.6):
    """Re-tint the final image desaturated cold blue (k05 flashback).

    Builds a compositor node group (Blender 5.x `scene.compositing_node_group`):
    Render Layers -> Hue/Saturation (saturation) -> Multiply by `tint` ->
    Add `lift` -> soft elliptical vignette (edges x `vignette`) -> Output.
    Works on everything rendered, so characters/props need no extra work.
    Call again with other numbers to change it; replaces any compositor.
    """
    name = "Ext_MemoryTint"
    old = bpy.data.node_groups.get(name)
    if old:
        bpy.data.node_groups.remove(old)
    ng = bpy.data.node_groups.new(name, "CompositorNodeTree")
    ng.interface.new_socket("Image", in_out="OUTPUT", socket_type="NodeSocketColor")
    rl = ng.nodes.new("CompositorNodeRLayers")
    rl.scene = sc
    hs = ng.nodes.new("CompositorNodeHueSat")
    hs.inputs["Saturation"].default_value = saturation
    ng.links.new(rl.outputs["Image"], hs.inputs["Image"])

    def mix(blend, a_out, color=None, fac=1.0, b_out=None):
        n = ng.nodes.new("ShaderNodeMix")
        n.data_type = "RGBA"
        n.blend_type = blend
        _sock(n, "Factor_Float").default_value = fac
        ng.links.new(a_out, _sock(n, "A_Color"))
        if b_out is not None:
            ng.links.new(b_out, _sock(n, "B_Color"))
        else:
            _sock(n, "B_Color").default_value = tuple(color) + (1.0,)
        return n.outputs[2]

    img = mix("MULTIPLY", hs.outputs["Image"], tint)
    img = mix("ADD", img, lift)
    el = ng.nodes.new("CompositorNodeEllipseMask")
    try:
        el.inputs["Size"].default_value = (0.95, 0.9)
    except (TypeError, ValueError):
        el.inputs["Size"].default_value = (0.95, 0.9, 0.0)
    bl = ng.nodes.new("CompositorNodeBlur")
    try:
        bl.inputs["Size"].default_value = (120, 120)
    except (TypeError, ValueError):
        pass
    ng.links.new(el.outputs["Mask"], bl.inputs["Image"])
    # mask 1 inside -> keep; 0 at edges -> multiply by `vignette`
    edge = mix("MULTIPLY", img, (vignette, vignette, vignette * 1.04))
    fin = ng.nodes.new("ShaderNodeMix")
    fin.data_type = "RGBA"
    ng.links.new(bl.outputs["Image"], _sock(fin, "Factor_Float"))
    ng.links.new(edge, _sock(fin, "A_Color"))
    ng.links.new(img, _sock(fin, "B_Color"))
    out = ng.nodes.new("NodeGroupOutput")
    ng.links.new(fin.outputs[2], out.inputs[0])
    sc.compositing_node_group = ng
    sc.render.use_compositing = True
    return ng


# ─── Entry point ────────────────────────────────────────────────────────────

def build_exterior(sc, variant="night", *, snow=True, snow_density=None, snow_speed=None,
                   wind=0.0, snow_frames=None, fox_tracks=False, fast_ink=True):
    """Build the exterior set into scene `sc` and return the anchors dict.

    variant: "night" (default) | "dawn" (k11) | "memory" (k05, blue flashback).
    snow: add the falling-snow particle system (pre-rolled; see set_snow_speed).
    snow_density: flakes multiplier (default 1.0 night/memory, 0.35 dawn).
    snow_speed: initial time_tweak (default 1.0 night, 0.7 memory, 0.55 dawn).
    wind: m/s of north wind pushing the snow toward -Y (k04: ~1.5). Build-time.
    snow_frames: (first, last) frame of the snowfall; default (scene.frame_start,
        max(scene.frame_end, start + 300)). Snow is already falling on `first`.
    fox_tracks: show the fox prints in the snow (k04).
    fast_ink: give the exterior outlines the opaque "ExtInk" (see _fast_ink);
        False keeps the kit's shared "Ink" (same look, ~7x slower render).

    Returns {name: (x, y, z)}; see the module docstring for every anchor.
    The scene camera/render settings are NOT touched (the director owns them),
    except `apply_memory_tint` for variant="memory" and the world.
    """
    if variant not in VARIANTS:
        raise ValueError(f"variant must be one of {VARIANTS}")
    ctx = _Ctx(sc, variant)
    M = _materials(ctx)
    _world(ctx)
    _ground(ctx, M)
    house = _house(ctx, M)
    tracks, t0, t1 = _fox_tracks(ctx, M)
    tracks.hide_render = not fox_tracks
    tracks.hide_viewport = not fox_tracks
    _forest_path_decal(ctx, M)
    ntrees = _forest(ctx, M)
    _far_treelines(ctx, M)
    if variant != "dawn":
        _moon(ctx)
        _stars(ctx)
        _aurora(ctx)
    _lights(ctx, house)
    if snow:
        dens = snow_density if snow_density is not None else (0.35 if variant == "dawn" else 1.0)
        spd = snow_speed if snow_speed is not None else {"night": 1.0, "memory": 0.7, "dawn": 0.55}[variant]
        f0, f1 = snow_frames or (sc.frame_start, max(sc.frame_end, sc.frame_start + 300))
        _snow(ctx, M, dens, spd, wind, f0, f1)
    if variant == "memory":
        apply_memory_tint(sc)
    if fast_ink:
        _fast_ink(ctx.root.all_objects)
    ctx.root["ext_trees"] = ntrees

    doorstep_front = (DOOR_X, STEP_FRONT_Y - 0.5, 0.0)
    fp_mid, _ = _poly_point(FOREST_PATH, 0.5)
    anchors = {
        "door": (DOOR_X, -HD, 0.0),
        "door_threshold": (DOOR_X, -HD, FOUND_H),
        "doorstep_top": (DOOR_X, -HD - LANDING_D / 2, FOUND_H),
        "doorstep_front": doorstep_front,
        "box_mark": (DOOR_X - 0.1, doorstep_front[1] - 0.6, 0.0),
        "fox_mark": (DOOR_X - 0.25, doorstep_front[1] - 2.0, 0.0),
        "fox_bow": (DOOR_X - 0.15, doorstep_front[1] - 1.05, 0.0),
        "window": (WIN_X, -HD, WIN_SILL + WIN_H / 2),
        "lake_start": (0.5, -25.0, 0.9),
        "lake_end": (0.9, -11.5, 1.6),
        "lake_centre": (LAKE_C[0], LAKE_C[1], 0.0),
        "nell_walk_start": (-12.0, -6.5, 0.0),
        "treeline_path": (TREELINE[0], TREELINE[1], 0.0),
        "forest_path_near": (FOREST_PATH[1][0], FOREST_PATH[1][1], 0.0),
        "forest_path_mid": (fp_mid[0], fp_mid[1], 0.0),
        "forest_path_far": (FOREST_PATH[-1][0], FOREST_PATH[-1][1], 0.0),
        "tracks_start": t0,
        "tracks_end": t1,
        "chimney_top": house["chimney_top"],
        "house_centre": (0.0, 0.0, 0.0),
        # preview cameras (suggestions)
        "cam_k01": (0.5, -25.0, 1.0), "look_k01": (0.4, -2.0, 3.4),
        "cam_k04_start": (5.8, -9.2, 3.0), "look_k04_start": (HW - 0.4, -HD, 2.0),
        "cam_k04": (4.6, -8.0, 2.6), "look_k04": (2.2, -5.6, 0.2),
        "cam_k05": (-2.2, -8.8, 0.8), "look_k05": (2.2, -5.2, 0.6),
        "cam_k07": (-2.2, -9.6, 0.85), "look_k07": (1.4, -6.2, 0.9),
        "cam_k11": (11.8, -8.6, 1.1), "look_k11": (33.0, 12.0, 2.8),
    }
    return {k: tuple(round(c, 3) for c in v) for k, v in anchors.items()}
