"""Cenário INTERIOR do curta "The Fox and the North Wind" (fox-3d): a sala da Farmor.

Usado nos planos k02 (geral, história junto ao fogão), k03/k10 (two-shot das duas
cadeiras) e k06 (Nell de casaco junto à porta, Farmor ao lado).

Roda dentro do Blender (`blender -b -P ...`). Tudo por código (bpy/bmesh),
determinístico (semente fixa), no visual do kit `toon3d`: faixas chapadas,
contorno preto grosso por casco invertido (0.009–0.022 m, o traço de nanquim
das ilustrações), emissão só no que brilha (fogo, brasas, cúpula da arandela,
estrelas de neve na janela).

    import sys; sys.path.insert(0, "/Users/alexandrejunior/Pedagogy_Swift/scripts/shorts")
    from sets3d import interior as I
    A = I.build_interior(sc)                 # constrói na cena e devolve as âncoras
    I.add_camera(sc, "cam_door")             # câmera pronta (loc, alvo e lente de CAMERAS)
    for n in I.CAMERA_HIDE.get("cam_door", ()):   # objetos a esconder nesse plano
        bpy.data.objects[n].hide_render = True    # (cam_door: INT_Chair_Left)

A sala é um "diorama": 5 m (x -2.5..2.5) × 4 m (y -2..2) × 2.6 m de pé-direito,
chão em z=0, ABERTA do lado -Y (sem parede) pra câmera olhar de dentro/de fora.
Parede do fundo (+Y): tábuas vermelhas com o painel de reboco creme atrás do
fogão (x -0.95..0.95); fogão grande de boca em arco com duas portinhas abertas
e lenha em brasa embaixo; prateleira dos bichinhos; cestos de vime; arandela.
Parede esquerda (-X): porta creme de almofadas vermelhas + cabideiro.
Parede direita (+X): janela com noite azul e uma estrela de neve por vidraça.
Tudo fica na coleção "Set_Interior" (luzes também). Como os cenários nascem
todos na origem, construa este numa cena própria.

Luz: o fogo é a luz-chave (dois pontos quentes que tremulam por driver de
`frame`, só termos lentos, determinístico, sem keyframes) + rebatido quente,
preenchimento frio e fraco vindo da janela, arandela fraca e fixa, ambiente
quase zero (mundo azul-noite escuro). O fogão, o cano e o fogo não projetam
sombra (senão escureceriam o reboco atrás, que no 2D é creme chapado). Os
materiais são do kit (`T.toon`, com shadow_tint/light_tint: sombra fria, luz
quente — ver TINT); brancos e cremes ficam sem tingir. As paredes vermelhas
têm faixas largas (0.06/0.93): ficam na cor base da paleta por inteiro.

Âncoras (todas tuplas (x, y, z) em metros, mundo):
  Convenção de "facing"/"rot": `*_facing` é o vetor unitário pra onde o
  personagem olha; `*_rot` é o Euler (0, 0, yaw) que gira um modelo cuja
  frente aponta pra -Y (padrão glTF/Tripo importado) até olhar pra `facing`.

  floor_center           (0, 0, 0) centro do chão da sala.
  chair_left_seat        centro do assento da cadeira da ESQUERDA, na altura do
                         tampo (onde vai o quadril). Sugestão: Nell (enrolada no
                         cobertor), como nas ilustrações.
  chair_left_facing      pra onde quem senta nela olha (pra cadeira da direita,
                         "roubando" 20° pra câmera em -Y: a Nell quase de perfil,
                         ouvindo) = (0.9397, -0.342, 0).
  chair_left_rot         Euler do yaw do personagem sentado nela = (0, 0, 1.2217).
  chair_right_seat       idem, cadeira da DIREITA. Sugestão: Farmor.
  chair_right_facing     rouba 42° pra câmera: a Farmor em 3/4 (é o rosto de
                         k02/k10) = (-0.7431, -0.6691, 0).
  chair_right_rot        = (0, 0, -0.8378).
  stove_fire             centro das chamas dentro do fogão (pra olhar/mirar).
  stove_door             centro da boca aberta do fogão (face da frente).
  stove_top              centro do tampo do fogão (ponto de apoio).
  fire_light             onde está a luz-chave quente (útil pra luz de personagem).
  shelf_top              centro do tampo da prateleira dos bichinhos entalhados.
  rug_center             centro do tapete de pele de rena (topo, z≈0.012).
  cat_basket             topo da almofada do cesto do gato (onde o gato deita).
  sconce                 centro da cúpula acesa da arandela (parede do fundo).
  door_inside            onde a Nell fica em pé, de casaco, junto à porta (k06), z=0.
  door_inside_facing / door_inside_rot   pra câmera cam_door, um pouco pra Farmor.
  farmor_by_door         onde a Farmor fica em pé ao lado dela (k06), z=0.
  farmor_by_door_facing  entre a Nell e a câmera (pro aceno de cabeça) ≈ (-0.1, -1).
  farmor_by_door_rot
  door_center            centro da folha da porta (face de dentro).
  door_knob              maçaneta.
  coat_hook              ponta do gancho do meio do cabideiro.
  window                 centro do vão da janela, na face de dentro.
  window_sill            topo do peitoril de dentro, no meio.
  window_snow            topo da neve no peitoril de fora.
  cam_wide / cam_wide_look          câmera geral de k02 (lente em CAMERAS).
  cam_twoshot / cam_twoshot_look    two-shot mais perto, k03/k10.
  cam_door / cam_door_look          canto da porta, k06 (esconda CAMERA_HIDE["cam_door"]).
  cam_close / cam_close_look        extra: mais fechado na Farmor com a Nell
                                    de ombro em primeiro plano (opção p/ k10).
"""

import math
import os
import random
import sys

import bmesh
import bpy
from mathutils import Euler, Matrix, Vector

_KIT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if not os.path.exists(os.path.join(_KIT, "toon3d.py")):
    _KIT = "/Users/alexandrejunior/Pedagogy_Swift/scripts/shorts"
if _KIT not in sys.path:
    sys.path.insert(0, _KIT)
import toon3d as T  # noqa: E402

SEED = 1907

# ─── Medidas da sala ────────────────────────────────────────────────────────
W2 = 2.5            # meia largura (x)
Y0, Y1 = -2.0, 2.0  # frente aberta, parede do fundo
H = 2.6             # pé-direito
PT = 0.035          # espessura das tábuas das paredes
GAP = 0.014         # fresta entre tábuas (mostra o fundo escuro = traço de tinta)
PLASTER_X = 0.95    # painel de reboco atrás do fogão: x -0.95..0.95

DOOR = (-0.25, 0.65, 0.0, 2.05)     # vão da porta na parede esquerda: y0, y1, z0, z1
WINDOW = (0.62, 1.48, 0.95, 2.0)    # vão da janela na parede direita: y0, y1, z0, z1

STOVE = (0.0, 1.55)                 # centro do fogão (x, y)
# corpo do fogão: largura, fundo, base e topo (o tampo fica ~na altura das cabeças sentadas)
STOVE_W, STOVE_D, STOVE_Z0, STOVE_Z1 = 0.8, 0.55, 0.24, 1.0
CHAIR_X, CHAIR_Y, SEAT_Z = 0.92, 0.75, 0.44
# graus que cada cadeira "rouba" pra câmera: a Nell (esq.) fica quase de perfil,
# ouvindo; a Farmor (dir.) abre em 3/4 pra câmera (é quem conta e quem chora)
CHAIR_CHEAT = {"left": 20.0, "right": 42.0}
RUG = (0.0, 0.45)
ANIMAL_SCALE = 1.3                  # bichinhos entalhados da prateleira (~20–27 cm)
BASKET = (0.0, 0.12)
BASKET_BIG = (1.2, 1.7)             # cestos de vime vazios (x, y)
BASKET_SMALL = (2.12, 0.98)

# Câmeras sugeridas: nome → (posição, alvo, lente mm).
CAMERAS = {
    "cam_wide": ((0.08, -3.2, 1.62), (0.08, 1.0, 1.02), 26.0),
    "cam_twoshot": ((0.0, -1.95, 1.06), (0.0, 0.95, 0.92), 34.0),
    "cam_door": ((0.75, -1.95, 1.38), (-1.72, 0.47, 0.98), 32.0),
    "cam_close": ((-1.62, 0.18, 1.2), (0.75, 0.86, 1.0), 40.0),
}
# Objetos do cenário que o diretor deve esconder (hide_render) em cada câmera.
# cam_door: a cadeira da esquerda (encosto de coração) rouba a atenção da Nell.
CAMERA_HIDE = {"cam_door": ("INT_Chair_Left",)}

# ─── Paleta (sRGB 0–255) e ajustes de faixa ────────────────────────────────
TINT = True
SHADOW_TINT = (0.92, 0.9, 1.12)   # faixa de sombra levemente fria/arroxeada
LIGHT_TINT = (1.1, 0.99, 0.8)     # faixa de luz quente (luz de fogo)

PAL = {
    # chave: (cor, kwargs do T.toon)
    # paredes vermelhas: faixas largas, a parede toda fica na cor base (sem o
    # "arco de holofote" que a luz pontual desenha); só sombra de contato escurece
    "red_a": ((158, 44, 38), {"shadow": 0.62, "bands": (0.06, 0.93)}),
    "red_b": ((146, 40, 34), {"shadow": 0.62, "bands": (0.06, 0.93)}),
    "red_c": ((168, 50, 42), {"shadow": 0.62, "bands": (0.06, 0.93)}),
    "gap": ((40, 16, 14), {"shadow": 0.8, "light": 1.1}),
    "plaster": ((236, 222, 192), {"shadow": 0.76, "light": 1.08, "bands": (0.06, 0.22),
                                   "tint": False}),
    # brancos/cremes sem o tingimento frio (senão a sombra vira lilás)
    "trim": ((238, 232, 220), {"shadow": 0.72, "tint": False}),
    "door": ((232, 220, 196), {"shadow": 0.72, "tint": False}),
    "floor_a": ((170, 118, 70), {}),
    "floor_b": ((156, 106, 62), {}),
    "floor_c": ((182, 128, 78), {}),
    "floor_gap": ((34, 22, 16), {"shadow": 0.8, "light": 1.1}),
    "ceiling": ((150, 104, 64), {"shadow": 0.78}),     # forro de pinho claro (como no 2D)
    "ceiling_dk": ((52, 34, 24), {"shadow": 0.8}),
    "beam": ((124, 84, 52), {"shadow": 0.72}),
    "post": ((112, 72, 46), {}),
    "shelf": ((150, 100, 62), {}),
    "iron": ((30, 30, 36), {"shadow": 0.8, "light": 2.3}),
    "iron_hi": ((58, 56, 62), {"shadow": 0.7, "light": 1.9}),
    "hearth": ((66, 62, 64), {"shadow": 0.6, "light": 1.4}),
    "fire": ((255, 150, 60), {"shadow": 1.0, "light": 1.0, "emission": 1.6}),
    "fire_core": ((255, 222, 120), {"shadow": 1.0, "light": 1.0, "emission": 2.2}),
    "ember": ((255, 96, 40), {"shadow": 1.0, "light": 1.0, "emission": 1.4}),
    "log_glow": ((190, 64, 36), {"shadow": 1.0, "light": 1.0, "emission": 0.9}),
    "bark": ((70, 45, 35), {}),
    "log_end": ((205, 165, 112), {}),
    "chair": ((172, 50, 42), {"light": 1.2}),
    "chair_blue": ((62, 86, 128), {}),
    "chair_panel": ((232, 216, 184), {"shadow": 0.72, "tint": False}),
    "carve": ((198, 152, 100), {"light": 1.18}),
    "carve_dk": ((150, 104, 68), {"light": 1.18}),
    "carve_fox": ((196, 84, 50), {"light": 1.18}),
    "moose": ((176, 128, 80), {"light": 1.18}),
    "rug": ((228, 214, 186), {"shadow": 0.66, "tint": False}),
    "rug_brown": ((146, 104, 70), {}),
    "rag_blue": ((70, 92, 120), {}),
    "rag_red": ((158, 44, 38), {}),
    "rag_cream": ((228, 214, 186), {"shadow": 0.7, "tint": False}),
    "wicker": ((196, 158, 98), {}),
    "wicker_dk": ((150, 110, 62), {}),
    "cushion": ((238, 232, 220), {"shadow": 0.68, "tint": False}),
    "brass": ((206, 166, 84), {"light": 1.3}),
    "shade": ((250, 234, 196), {"shadow": 1.0, "light": 1.0, "emission": 1.5}),
    "shawl": ((200, 150, 60), {}),
    "frame_wood": ((112, 74, 48), {}),
    "snow": ((236, 240, 248), {"shadow": 0.62, "emission": 0.12}),
    "snow_far": ((150, 176, 214), {"shadow": 0.6, "emission": 0.35}),
    "pine": ((38, 66, 58), {"shadow": 0.62}),
    "flake": ((236, 240, 248), {"shadow": 1.0, "light": 1.0, "emission": 1.2}),
}


def _m(key):
    """Material toon do kit, com as faixas tingidas (sombra fria, luz quente)."""
    name = "INT_" + key
    mat = bpy.data.materials.get(name)
    if mat:
        return mat
    color, kw = PAL[key]
    shadow = kw.get("shadow", 0.5)
    light = kw.get("light", 1.15)
    emission = kw.get("emission", 0.0)
    tint = TINT and kw.get("tint", True) and not emission
    st = SHADOW_TINT if tint else (1.0, 1.0, 1.0)
    lt = LIGHT_TINT if tint else (1.0, 1.0, 1.0)
    args = dict(shadow=shadow, light=light, bands=kw.get("bands", (0.28, 0.62)), emission=emission)
    try:
        mat = T.toon(name, color, shadow_tint=st, light_tint=lt, **args)
    except TypeError:                       # kit antigo, sem os tints: pinta a rampa aqui
        mat = T.toon(name, color, **args)
        ramp = next(n for n in mat.node_tree.nodes if n.type == "VALTORGB")
        els = ramp.color_ramp.elements
        els[0].color = tuple(shadow * k for k in st) + (1.0,)
        els[len(els) - 1].color = tuple(light * k for k in lt) + (1.0,)
    mat.diffuse_color = T.lin(color)
    return mat


# ─── Geometria (bmesh) ──────────────────────────────────────────────────────

def _mat4(loc=(0, 0, 0), rot=(0, 0, 0), scale=(1, 1, 1)):
    return (Matrix.Translation(Vector(loc)) @ Euler(rot).to_matrix().to_4x4()
            @ Matrix.Diagonal((scale[0], scale[1], scale[2], 1.0)))


def _ccw(pts):
    area = sum(pts[i][0] * pts[(i + 1) % len(pts)][1] - pts[(i + 1) % len(pts)][0] * pts[i][1]
               for i in range(len(pts)))
    return list(pts) if area > 0 else list(reversed(pts))


class _Part:
    """Um objeto-malha montado de primitivas numa bmesh só (menos objetos, menos draw calls)."""

    def __init__(self, name):
        self.name = name
        self.bm = bmesh.new()
        self.mats = []

    def _idx(self, mat):
        if mat not in self.mats:
            self.mats.append(mat)
        return self.mats.index(mat)

    def _finish(self, verts, mat, smooth=False, sharp_deg=50.0):
        faces = {f for v in verts if v.is_valid for f in v.link_faces}
        i = self._idx(mat)
        for f in faces:
            f.material_index = i
            f.smooth = smooth
        if smooth:
            for f in faces:
                f.normal_update()
            lim = math.radians(sharp_deg)
            for e in {e for f in faces for e in f.edges}:
                if len(e.link_faces) == 2 and e.calc_face_angle(0.0) > lim:
                    e.smooth = False
        return faces

    def box(self, size, loc=(0, 0, 0), mat=None, rot=(0, 0, 0), bevel=0.0, segs=1, pre=None):
        M = _mat4(loc, rot, size)
        if pre is not None:
            M = pre @ M
        verts = bmesh.ops.create_cube(self.bm, size=1.0, matrix=M)["verts"]
        self._finish(verts, mat)
        if bevel > 0:
            edges = list({e for v in verts for e in v.link_edges})
            bmesh.ops.bevel(self.bm, geom=edges, offset=bevel, offset_type="OFFSET",
                            segments=segs, profile=0.5, affect="EDGES", clamp_overlap=True,
                            material=-1)
        return verts

    def cyl(self, r1, r2, depth, loc=(0, 0, 0), mat=None, rot=(0, 0, 0), segs=10,
            smooth=True, cap_mat=None, pre=None, caps=True):
        M = _mat4(loc, rot)
        if pre is not None:
            M = pre @ M
        verts = bmesh.ops.create_cone(self.bm, cap_ends=caps, cap_tris=False, segments=segs,
                                      radius1=r1, radius2=max(r2, 0.0004), depth=depth,
                                      matrix=M)["verts"]
        faces = self._finish(verts, mat, smooth)
        if cap_mat is not None:
            axis = (M.to_3x3() @ Vector((0, 0, 1))).normalized()
            ci = self._idx(cap_mat)
            for f in faces:
                f.normal_update()
                if abs(f.normal.dot(axis)) > 0.9:
                    f.material_index = ci
                    f.smooth = False
        return faces

    def sphere(self, r, loc=(0, 0, 0), mat=None, scale=(1, 1, 1), rot=(0, 0, 0), u=12, v=7,
               smooth=True, pre=None):
        M = _mat4(loc, rot, scale)
        if pre is not None:
            M = pre @ M
        verts = bmesh.ops.create_uvsphere(self.bm, u_segments=u, v_segments=v, radius=r,
                                          matrix=M)["verts"]
        return self._finish(verts, mat, smooth, sharp_deg=80.0)

    def prism(self, pts, h, M, mat, smooth=False):
        """Polígono 2D (plano local XY) extrudado `h` em +Z local, transformado por M."""
        pts = _ccw(pts)
        bm = self.bm
        bot = [bm.verts.new(M @ Vector((x, y, 0.0))) for x, y in pts]
        top = [bm.verts.new(M @ Vector((x, y, h))) for x, y in pts]
        bm.faces.new(top)
        bm.faces.new(list(reversed(bot)))
        n = len(pts)
        for i in range(n):
            j = (i + 1) % n
            bm.faces.new((bot[i], bot[j], top[j], top[i]))
        return self._finish(bot + top, mat, smooth)

    def torus(self, R, r, loc=(0, 0, 0), mat=None, rot=(0, 0, 0), segs=16, rsegs=6,
              scale=(1, 1, 1), pre=None):
        M = _mat4(loc, rot, scale)
        if pre is not None:
            M = pre @ M
        bm = self.bm
        rings = []
        for i in range(segs):
            a = 2 * math.pi * i / segs
            ring = []
            for j in range(rsegs):
                b = 2 * math.pi * j / rsegs
                p = Vector(((R + r * math.cos(b)) * math.cos(a),
                            (R + r * math.cos(b)) * math.sin(a), r * math.sin(b)))
                ring.append(bm.verts.new(M @ p))
            rings.append(ring)
        for i in range(segs):
            for j in range(rsegs):
                i2, j2 = (i + 1) % segs, (j + 1) % rsegs
                bm.faces.new((rings[i][j], rings[i2][j], rings[i2][j2], rings[i][j2]))
        return self._finish([v for ring in rings for v in ring], mat, True, sharp_deg=89.0)

    def lathe(self, prof, loc=(0, 0, 0), mat=None, segs=7, lean=(0.0, 0.0), smooth=True):
        """Sólido de revolução: `prof` = [(raio, z), ...] de baixo pra cima; o 1º e o
        último ponto com raio 0 viram polos. `lean` entorta a ponta (dx, dy por z²)."""
        bm = self.bm
        h = max(z for _, z in prof) or 1.0
        rings = []
        for r, z in prof:
            k = (z / h) ** 2
            off = Vector((loc[0] + lean[0] * k, loc[1] + lean[1] * k, loc[2] + z))
            if r <= 1e-6:
                rings.append([bm.verts.new(off)])
            else:
                rings.append([bm.verts.new(off + Vector((r * math.cos(2 * math.pi * i / segs),
                                                         r * math.sin(2 * math.pi * i / segs), 0)))
                              for i in range(segs)])
        for a, b in zip(rings, rings[1:]):
            for i in range(segs):
                j = (i + 1) % segs
                if len(a) == 1:
                    bm.faces.new((a[0], b[j], b[i]))
                elif len(b) == 1:
                    bm.faces.new((a[i], a[j], b[0]))
                else:
                    bm.faces.new((a[i], a[j], b[j], b[i]))
        return self._finish([v for ring in rings for v in ring], mat, smooth, sharp_deg=70.0)

    def build(self, coll, outline=0.0, loc=(0, 0, 0), rot=(0, 0, 0)):
        me = self.mesh()
        return _instance(me, self.name, coll, outline, loc, rot)

    def mesh(self):
        me = bpy.data.meshes.new(self.name)
        self.bm.to_mesh(me)
        self.bm.free()
        for m in self.mats:
            me.materials.append(m)
        return me


def _instance(me, name, coll, outline=0.0, loc=(0, 0, 0), rot=(0, 0, 0), scale=(1, 1, 1)):
    ob = bpy.data.objects.new(name, me)
    coll.objects.link(ob)
    ob.location = loc
    ob.rotation_euler = rot
    ob.scale = scale
    if outline:
        T.outline(ob, outline)
    return ob


def _subtract(segs, z0, z1):
    out = []
    for s0, s1 in segs:
        if z1 <= s0 or z0 >= s1:
            out.append((s0, s1))
            continue
        if z0 > s0:
            out.append((s0, z0))
        if z1 < s1:
            out.append((z1, s1))
    return out


def _plank_run(a0, a1, rnd, openings=(), target=0.2, jitter=0.2):
    """Tábuas verticais entre a0..a1 (cortes alinhados às bordas dos vãos).

    Devolve [(a, b, [(z0, z1), ...]), ...].
    """
    cuts = sorted({a0, a1} | {e for o in openings for e in o[:2] if a0 < e < a1})
    out = []
    for c0, c1 in zip(cuts, cuts[1:]):
        L = c1 - c0
        n = max(1, round(L / target))
        ws = [rnd.uniform(1 - jitter, 1 + jitter) for _ in range(n)]
        s = sum(ws)
        a = c0
        for w in ws:
            b = a + L * w / s
            segs = [(0.0, H)]
            mid = (a + b) / 2
            for o0, o1, z0, z1 in openings:
                if o0 < mid < o1:
                    segs = _subtract(segs, z0, z1)
            out.append((a, b, segs))
            a = b
    return out


# ─── Partes da sala ─────────────────────────────────────────────────────────

def _walls(coll, rnd):
    reds = [_m("red_a"), _m("red_b"), _m("red_c")]
    gap = _m("gap")

    # Fundo escuro atrás das tábuas (aparece nas frestas como traço).
    back = _Part("INT_WallBacking")
    back.box((2 * W2 + 0.16, 0.08, H), (0, Y1 + 0.04, H / 2), gap)
    back.box((0.08, Y1 - Y0, H), (-W2 - 0.04, 0, H / 2), gap)
    y0, y1, z0, z1 = WINDOW
    xr = W2 + 0.04
    back.box((0.08, y0 - Y0, H), (xr, (Y0 + y0) / 2, H / 2), gap)
    back.box((0.08, Y1 - y1, H), (xr, (y1 + Y1) / 2, H / 2), gap)
    back.box((0.08, y1 - y0, z0), (xr, (y0 + y1) / 2, z0 / 2), gap)
    back.box((0.08, y1 - y0, H - z1), (xr, (y0 + y1) / 2, (z1 + H) / 2), gap)
    back.build(coll)

    planks = _Part("INT_WallPlanks")
    # Parede do fundo: tábuas dos dois lados do reboco.
    for a0, a1 in ((-W2, -PLASTER_X - 0.04), (PLASTER_X + 0.04, W2)):
        for a, b, segs in _plank_run(a0, a1, rnd):
            for s0, s1 in segs:
                planks.box((b - a - GAP, PT, s1 - s0), ((a + b) / 2, Y1 - PT / 2, (s0 + s1) / 2),
                           rnd.choice(reds))
    # Paredes laterais (tábuas ao longo de y), com os vãos de porta e janela.
    for side, opening in ((-1, DOOR), (1, WINDOW)):
        x = side * (W2 - PT / 2)
        for a, b, segs in _plank_run(Y0, Y1 - PT, rnd, openings=(opening,)):
            for s0, s1 in segs:
                if s1 - s0 < 0.03:
                    continue
                planks.box((PT, b - a - GAP, s1 - s0), (x, (a + b) / 2, (s0 + s1) / 2),
                           rnd.choice(reds))
    planks.build(coll, outline=0.009)

    # Reboco creme atrás do fogão + montantes de madeira nas bordas.
    plaster = _Part("INT_Plaster")
    plaster.box((2 * PLASTER_X, 0.03, H), (0, Y1 - 0.015, H / 2), _m("plaster"))
    plaster.build(coll, outline=0.012)

    wood = _Part("INT_Posts")
    post = _m("post")
    for sx in (-1, 1):
        wood.box((0.08, 0.05, H), (sx * (PLASTER_X + 0.0), Y1 - 0.045, H / 2), post, bevel=0.008)
        # quinas do fundo e da frente do diorama
        wood.box((0.1, 0.1, H), (sx * (W2 - 0.05), Y1 - 0.05, H / 2), post, bevel=0.01)
        wood.box((0.1, 0.1, H), (sx * (W2 - 0.03), Y0 + 0.05, H / 2), post, bevel=0.01)
    # rodapés
    bb = 0.11
    wood.box((2 * W2, 0.022, bb), (0, Y1 - 0.045, bb / 2), post, bevel=0.004)
    wood.box((0.022, Y1 - Y0, bb), (W2 - PT - 0.011, 0, bb / 2), post, bevel=0.004)
    d0, d1 = DOOR[0] - 0.08, DOOR[1] + 0.08
    wood.box((0.022, d0 - Y0, bb), (-W2 + PT + 0.011, (Y0 + d0) / 2, bb / 2), post, bevel=0.004)
    wood.box((0.022, Y1 - d1, bb), (-W2 + PT + 0.011, (d1 + Y1) / 2, bb / 2), post, bevel=0.004)
    # travessa no alto das paredes (encontro com o forro)
    wood.box((2 * W2, 0.05, 0.1), (0, Y1 - 0.05, H - 0.05), _m("beam"), bevel=0.006)
    wood.box((0.05, Y1 - Y0, 0.1), (-W2 + 0.05, 0, H - 0.05), _m("beam"), bevel=0.006)
    wood.box((0.05, Y1 - Y0, 0.1), (W2 - 0.05, 0, H - 0.05), _m("beam"), bevel=0.006)
    wood.build(coll, outline=0.015)


def _floor_and_ceiling(coll, rnd):
    slab = _Part("INT_FloorBase")
    slab.box((2 * W2 + 0.2, Y1 - Y0 + 0.5, 0.07), (0, (Y0 + Y1) / 2 - 0.15, -0.065), _m("floor_gap"))
    slab.build(coll)

    boards = _Part("INT_FloorBoards")
    woods = [_m("floor_a"), _m("floor_b"), _m("floor_c")]
    fy0, fy1 = Y0 - 0.4, Y1 - PT
    for a, b, _ in _plank_run(-W2, W2, rnd, target=0.19, jitter=0.15):
        y = fy0
        while y < fy1 - 0.05:
            L = rnd.uniform(1.3, 2.8)
            y2 = min(fy1, y + L)
            if fy1 - y2 < 0.4:
                y2 = fy1
            boards.box((b - a - 0.01, y2 - y - 0.01, 0.03), ((a + b) / 2, (y + y2) / 2, -0.015),
                       rnd.choice(woods))
            y = y2
    boards.build(coll)

    ceil = _Part("INT_Ceiling")
    ceil.box((2 * W2 + 0.2, Y1 - Y0 + 0.2, 0.08), (0, 0, H + 0.04), _m("ceiling_dk"))
    ceil.build(coll)

    cboards = _Part("INT_CeilingBoards")
    cw = _m("ceiling")
    for a, b, _ in _plank_run(-W2, W2, rnd, target=0.22, jitter=0.12):
        cboards.box((b - a - 0.012, Y1 - Y0, 0.03), ((a + b) / 2, 0, H - 0.015), cw)
    cboards.build(coll)

    beams = _Part("INT_Beams")
    for y in (-1.45, -0.45, 0.45, 1.22):
        beams.box((2 * W2, 0.14, 0.14), (0, y, H - 0.03 - 0.07), _m("beam"), bevel=0.012)
    beams.build(coll, outline=0.02)


def _arch_pts(x0, x1, z0, z1, rise, n=9):
    """Retângulo x0..x1 × z0..z1 com o topo em arco (flecha `rise`), anti-horário."""
    cx, hw, zb = (x0 + x1) / 2, (x1 - x0) / 2, z1 - rise
    arc = [(cx + hw * math.cos(math.pi * i / n), zb + rise * math.sin(math.pi * i / n))
           for i in range(1, n)]
    return [(x0, z0), (x1, z0), (x1, zb)] + arc + [(x0, zb)]


def _no_shadow(ob):
    """O objeto não projeta sombra (o fogão não escurece o reboco atrás dele)."""
    if hasattr(ob, "visible_shadow"):
        ob.visible_shadow = False
    return ob


# boca da fornalha: largura, base e topo (arco no alto, como nas ilustrações)
MOUTH_W, MOUTH_Z0, MOUTH_Z1, MOUTH_RISE = 0.52, 0.42, 0.88, 0.14


def _stove(coll):
    sx, sy = STOVE
    iron, iron_hi = _m("iron"), _m("iron_hi")
    anchors = {}

    hearth = _Part("INT_Hearth")
    hearth.box((1.35, 1.05, 0.04), (sx, sy - 0.08, 0.02), _m("hearth"), bevel=0.012)
    hearth.build(coll, outline=0.02)

    st = _Part("INT_Stove")
    bw, bd, bz0, bz1 = STOVE_W, STOVE_D, STOVE_Z0, STOVE_Z1
    ow, oz0, oz1 = MOUTH_W, MOUTH_Z0, MOUTH_Z1
    fy = sy - bd / 2                     # face da frente
    # Corpo com a fornalha escavada: inset na face da frente (reposicionado pra
    # boca ficar no alto do corpo, com uma "testa" embaixo) + extrusão pra dentro.
    verts = bmesh.ops.create_cube(st.bm, size=1.0, matrix=_mat4((sx, sy, (bz0 + bz1) / 2), (0, 0, 0),
                                                                  (bw, bd, bz1 - bz0)))["verts"]
    faces = st._finish(verts, iron)
    for f in faces:
        f.normal_update()
    front = min(faces, key=lambda f: f.normal.y)
    bmesh.ops.inset_individual(st.bm, faces=[front], thickness=0.12, depth=0.0)
    zmid = sum(v.co.z for v in front.verts) / len(front.verts)
    for v in front.verts:
        v.co.x = sx + (ow / 2 if v.co.x > sx else -ow / 2)
        v.co.z = oz1 if v.co.z > zmid else oz0
    ext = bmesh.ops.extrude_face_region(st.bm, geom=[front])
    nv = [g for g in ext["geom"] if isinstance(g, bmesh.types.BMVert)]
    bmesh.ops.translate(st.bm, verts=nv, vec=(0.0, bd - 0.16, 0.0))
    # a face original fica tampando a boca: remove; e as normais da fornalha
    # têm de apontar pro ar (senão o casco de contorno pinta a boca de preto)
    if front.is_valid:
        bmesh.ops.delete(st.bm, geom=[front], context="FACES_ONLY")
    bmesh.ops.recalc_face_normals(st.bm, faces=list(st.bm.faces))
    # tampo, base, pés
    st.box((bw + 0.08, bd + 0.06, 0.045), (sx, sy, bz1 + 0.0225), iron_hi, bevel=0.012)
    st.box((bw + 0.04, bd + 0.03, 0.035), (sx, sy, bz0 + 0.0175), iron_hi, bevel=0.01)
    for dx in (-1, 1):
        for dy in (-1, 1):
            st.box((0.065, 0.065, bz0), (sx + dx * (bw / 2 - 0.05), sy + dy * (bd / 2 - 0.05), bz0 / 2),
                   iron, rot=(0, 0, math.radians(45)), bevel=0.008)
    # moldura em volta da boca + os cantos de cima fechados em arco
    fr = 0.035
    st.box((ow + 2 * fr, 0.02, fr), (sx, fy - 0.01, oz1 + fr / 2), iron_hi, bevel=0.004)
    st.box((ow + 2 * fr, 0.02, fr), (sx, fy - 0.01, oz0 - fr / 2), iron_hi, bevel=0.004)
    st.box((fr, 0.02, oz1 - oz0), (sx - ow / 2 - fr / 2, fy - 0.01, (oz0 + oz1) / 2), iron_hi, bevel=0.004)
    st.box((fr, 0.02, oz1 - oz0), (sx + ow / 2 + fr / 2, fy - 0.01, (oz0 + oz1) / 2), iron_hi, bevel=0.004)
    w, zb, rise = ow / 2 + 0.002, oz1 - MOUTH_RISE, MOUTH_RISE - 0.012
    spandrel = [(-w, oz1), (-w, zb)] + \
        [(w * math.cos(math.pi * (1 - i / 10)), zb + rise * math.sin(math.pi * (1 - i / 10)))
         for i in range(1, 10)] + [(w, zb), (w, oz1)]
    rx = Matrix.Rotation(math.radians(90), 4, "X")      # local XY → mundo XZ, +Z local → -Y
    st.prism(spandrel, 0.038, Matrix.Translation((sx, fy + 0.03, 0)) @ rx, iron_hi)
    # beiral da boca (onde cai a cinza)
    st.box((ow + 0.12, 0.07, 0.025), (sx, fy - 0.03, oz0 - fr - 0.0125), iron_hi, bevel=0.006)
    # par de portinhas abertas (meio arco cada), dobradiças nas laterais da boca.
    # Duas folhas curtas: abertas, não avançam sobre os joelhos de quem senta.
    hw, dh = ow / 2 + fr, oz1 - oz0 + 2 * fr
    zb, rise = dh / 2 - (MOUTH_RISE + 0.02), MOUTH_RISE + 0.02
    half = [(0.0, -dh / 2), (hw, -dh / 2)] + \
        [(hw + hw * math.cos(math.pi / 2 + math.pi / 2 * i / 6), zb + rise * math.sin(math.pi / 2 + math.pi / 2 * i / 6))
         for i in range(7)]
    for side in (-1, 1):
        hinge = Matrix.Translation((sx + side * hw, fy - 0.02, (oz0 + oz1) / 2)) @ \
            Matrix.Rotation(math.radians(112 * side), 4, "Z")
        pts = half if side < 0 else [(-u, v) for u, v in reversed(half)]
        st.prism(pts, 0.022, hinge @ rx, iron_hi)
        st.box((hw - 0.07, 0.01, dh * 0.42), (-side * hw / 2, -0.027, -dh * 0.14), iron, pre=hinge,
               bevel=0.003)
        st.sphere(0.02, (-side * (hw - 0.04), -0.045, 0.0), _m("brass"), pre=hinge, u=8, v=5)
    # alça lateral e botão de ar
    st.cyl(0.013, 0.013, 0.1, (sx + bw / 2 + 0.05, sy - 0.08, 0.8), iron_hi, rot=(0, math.radians(90), 0), segs=6)
    st.sphere(0.03, (sx + bw / 2 + 0.1, sy - 0.08, 0.8), iron_hi, u=8, v=5)
    _no_shadow(st.build(coll, outline=0.022))

    # Cano até o forro.
    pipe = _Part("INT_StovePipe")
    pz0, pz1 = bz1 + 0.045, H - 0.03
    pipe.cyl(0.08, 0.08, pz1 - pz0, (sx, sy + 0.05, (pz0 + pz1) / 2), iron, segs=12)
    pipe.cyl(0.098, 0.098, 0.06, (sx, sy + 0.05, pz0 + 0.03), iron_hi, segs=12)
    pipe.cyl(0.094, 0.094, 0.04, (sx, sy + 0.05, 1.5), iron_hi, segs=12)
    pipe.cyl(0.14, 0.14, 0.03, (sx, sy + 0.05, H - 0.045), iron_hi, segs=12)
    _no_shadow(pipe.build(coll, outline=0.018))

    # Fogo: brasas + lenha (um objeto), chamas (outro, pra tremular a escala).
    fire_y = fy + 0.2
    logs = _Part("INT_FireLogs")
    logs.box((ow - 0.04, 0.3, 0.03), (sx, fire_y + 0.02, oz0 + 0.015), _m("ember"))
    for (dx, dy, dz, rz, L) in ((0.0, 0.07, 0.06, 8, 0.44), (0.0, -0.06, 0.055, -6, 0.42),
                                (0.04, 0.0, 0.105, 62, 0.34)):
        logs.cyl(0.04, 0.04, L, (sx + dx, fire_y + dy, oz0 + dz), _m("bark"),
                 rot=(0, math.radians(90), math.radians(rz)), segs=7, cap_mat=_m("ember"))
    _no_shadow(logs.build(coll, outline=0.009))

    flames = _Part("INT_FireFlames")
    base_z = oz0 + 0.085
    k = 1.3
    # chamas em gota (revolução) com a ponta entortada, as de dentro mais amarelas
    for (dx, dy, h, r, lean, key) in ((-0.085, 0.03, 0.18, 0.055, -0.05, "fire"),
                                     (0.0, 0.06, 0.26, 0.075, 0.03, "fire"),
                                     (0.085, 0.02, 0.2, 0.058, 0.05, "fire"),
                                     (-0.03, -0.035, 0.15, 0.042, -0.03, "fire_core"),
                                     (0.04, -0.045, 0.12, 0.036, 0.035, "fire_core")):
        h, r = h * k, r * k
        prof = [(0.0, 0.0), (0.75 * r, 0.04 * h), (r, 0.2 * h), (0.85 * r, 0.42 * h),
                (0.45 * r, 0.7 * h), (0.0, h)]
        flames.lathe(prof, (dx * k, dy, -0.01), _m(key), segs=7, lean=(lean * k, 0.0), smooth=False)
    fl = _no_shadow(flames.build(coll, outline=0.008, loc=(sx, fire_y, base_z)))

    # Lenha em brasa empilhada embaixo da fornalha, entre os pés (como no 2D).
    under = _Part("INT_UnderLogs")
    uy = sy - 0.09
    under.box((0.4, 0.34, 0.02), (sx, uy, 0.05), _m("ember"))
    for (dx, z) in ((-0.1, 0.0), (0.0, 0.0), (0.1, 0.0), (-0.05, 1.0), (0.05, 1.0)):
        under.cyl(0.037, 0.037, 0.3, (sx + dx, uy - 0.01 * z, 0.04 + 0.037 + z * 0.066), _m("log_glow"),
                  rot=(math.radians(90), 0, 0), segs=7, cap_mat=_m("ember"))
    _no_shadow(under.build(coll, outline=0.009))

    anchors["stove_fire"] = (sx, fire_y, base_z + 0.13)
    anchors["stove_door"] = (sx, fy, (oz0 + oz1) / 2)
    anchors["stove_top"] = (sx, sy, bz1 + 0.045)
    return anchors, fl


def _shelf_and_animals(coll):
    shelf = _Part("INT_Shelf")
    wood = _m("shelf")
    sz, sd = 1.62, 0.2
    y_front = Y1 - 0.03 - sd
    shelf.box((1.7, sd, 0.05), (0, Y1 - 0.03 - sd / 2, sz + 0.025), wood, bevel=0.01)
    # mãos-francesas: perfil em "L" com curva, no plano YZ
    M_yz = Matrix(((0, 0, 1, 0), (1, 0, 0, 0), (0, 1, 0, 0), (0, 0, 0, 1)))
    prof = [(Y1 - 0.03, sz), (y_front + 0.02, sz), (y_front + 0.03, sz - 0.05),
            (Y1 - 0.08, sz - 0.1), (Y1 - 0.1, sz - 0.2), (Y1 - 0.03, sz - 0.26)]
    for x in (-0.62, 0.62):
        shelf.prism(prof, 0.05, Matrix.Translation((x - 0.025, 0, 0)) @ M_yz, wood)
    shelf.build(coll, outline=0.014)

    top = sz + 0.05
    yy = Y1 - 0.03 - sd / 2
    k = ANIMAL_SCALE
    _animal_bear(coll, (-0.55, yy, top), 0.0).scale = (k, k, k)
    _animal_fox(coll, (-0.25, yy, top), math.pi).scale = (k, k, k)
    _animal_moose(coll, (0.52, yy, top), math.pi, 1.0, "INT_Moose").scale = (k, k, k)
    _animal_moose(coll, (0.25, yy + 0.01, top), 0.0, 0.62, "INT_MooseCalf").scale = (k, k, k)
    return (0.0, yy, top)


def _animal_bear(coll, loc, rz):
    p = _Part("INT_Bear")
    m = _m("carve_dk")
    p.box((0.13, 0.075, 0.07), (0, 0, 0.068), m, bevel=0.014)
    p.box((0.05, 0.055, 0.03), (0.02, 0, 0.105), m, bevel=0.01)          # corcova
    for dx in (-0.045, 0.045):
        for dy in (-0.022, 0.022):
            p.box((0.026, 0.024, 0.04), (dx, dy, 0.02), m, bevel=0.006)
    p.box((0.055, 0.055, 0.05), (0.083, 0, 0.088), m, bevel=0.012)       # cabeça
    p.box((0.032, 0.03, 0.026), (0.118, 0, 0.078), m, bevel=0.007)       # focinho
    for dy in (-0.019, 0.019):
        p.sphere(0.011, (0.078, dy, 0.117), m, u=6, v=4, smooth=False)
    return p.build(coll, outline=0.008 / ANIMAL_SCALE, loc=loc, rot=(0, 0, rz))


def _animal_fox(coll, loc, rz):
    p = _Part("INT_CarvedFox")
    m = _m("carve_fox")
    p.box((0.1, 0.042, 0.042), (0, 0, 0.066), m, bevel=0.01)
    for dx in (-0.035, 0.035):
        for dy in (-0.012, 0.012):
            p.box((0.014, 0.014, 0.048), (dx, dy, 0.024), m)
    p.box((0.04, 0.04, 0.036), (0.062, 0, 0.096), m, bevel=0.008)
    p.cyl(0.017, 0.0, 0.04, (0.098, 0, 0.09), m, rot=(0, math.radians(90), 0), segs=5, smooth=False)
    for dy in (-0.012, 0.012):
        p.cyl(0.011, 0.0, 0.028, (0.058, dy, 0.125), m, segs=4, smooth=False)
    p.cyl(0.02, 0.004, 0.075, (-0.075, 0, 0.085), m, rot=(0, math.radians(-120), 0), segs=6)
    return p.build(coll, outline=0.007 / ANIMAL_SCALE, loc=loc, rot=(0, 0, rz))


def _animal_moose(coll, loc, rz, s, name):
    p = _Part(name)
    m = _m("moose")
    k = s
    p.box((0.15 * k, 0.062 * k, 0.07 * k), (0, 0, 0.118 * k), m, bevel=0.012 * k)
    p.box((0.05 * k, 0.05 * k, 0.03 * k), (0.045 * k, 0, 0.155 * k), m, bevel=0.008 * k)  # cernelha
    for dx in (-0.055, 0.055):
        for dy in (-0.02, 0.02):
            p.box((0.02 * k, 0.02 * k, 0.09 * k), (dx * k, dy * k, 0.045 * k), m)
    p.box((0.035 * k, 0.03 * k, 0.05 * k), (0.085 * k, 0, 0.15 * k), m, rot=(0, math.radians(-30), 0))
    p.box((0.075 * k, 0.034 * k, 0.034 * k), (0.115 * k, 0, 0.165 * k), m,
          rot=(0, math.radians(25), 0), bevel=0.008 * k)                      # cabeça comprida
    if s > 0.8:
        for side in (-1, 1):
            p.box((0.05, 0.008, 0.035), (0.09, side * 0.04, 0.2), m,
                  rot=(math.radians(side * -35), 0, 0), bevel=0.003)
            p.box((0.014, 0.008, 0.03), (0.085, side * 0.022, 0.185), m)
    else:
        for dy in (-0.01, 0.01):
            p.cyl(0.008 * k * 1.4, 0.0, 0.03 * k, (0.095 * k, dy * k, 0.19 * k), m, segs=4, smooth=False)
    return p.build(coll, outline=0.007 / ANIMAL_SCALE, loc=loc, rot=(0, 0, rz))


def _heart(n=28, size=0.1):
    pts = []
    for i in range(n):
        t = 2 * math.pi * i / n
        x = 16 * math.sin(t) ** 3
        y = 13 * math.cos(t) - 5 * math.cos(2 * t) - 2 * math.cos(3 * t) - math.cos(4 * t)
        pts.append((x * size / 32, (y + 3) * size / 32))
    return pts


def _chair_mesh():
    """Cadeira sueca pintada (vermelha, faixa azul, encosto creme com coração).

    Local: origem no chão sob o centro do assento, frente pra -Y, encosto em +Y.
    """
    p = _Part("INT_Chair")
    red, blue, cream = _m("chair"), _m("chair_blue"), _m("chair_panel")
    sw, sd, st = 0.42, 0.4, 0.045
    p.box((sw, sd, st), (0, 0, SEAT_Z - st / 2), red, bevel=0.01)
    p.box((sw + 0.004, sd + 0.004, 0.02), (0, 0, SEAT_Z - st - 0.01), blue, bevel=0.004)
    lx, ly = sw / 2 - 0.03, sd / 2 - 0.03
    for dx in (-lx, lx):
        p.box((0.04, 0.04, SEAT_Z - st), (dx, -ly, (SEAT_Z - st) / 2), red, bevel=0.006)
        p.box((0.042, 0.042, 0.98), (dx, ly, 0.49), red, bevel=0.006)          # montante
        p.sphere(0.03, (dx, ly, 1.0), red, u=8, v=6)                          # pinha
        p.box((0.028, sd - 0.06, 0.028), (dx, 0, 0.16), red)                  # travessa lateral
    p.box((sw - 0.06, 0.028, 0.028), (0, -ly, 0.13), red)
    p.box((sw - 0.06, 0.028, 0.028), (0, ly, 0.2), red)
    # encosto: painel arqueado creme com faixas azuis e coração vermelho
    M = Matrix.Translation((0, ly + 0.008, 0)) @ Matrix.Rotation(math.radians(90), 4, "X")
    arch = [(-0.17, 0.56), (0.17, 0.56), (0.17, 0.86)] + \
        [(0.17 * math.cos(a), 0.86 + 0.06 * math.sin(a)) for a in
         (math.radians(d) for d in (20, 50, 80, 100, 130, 160))] + [(-0.17, 0.86)]
    p.prism(arch, 0.022, M, cream)
    for bx in (-0.12, 0.12):
        p.prism([(bx - 0.018, 0.57), (bx + 0.018, 0.57), (bx + 0.018, 0.86), (bx - 0.018, 0.86)],
                0.004, Matrix.Translation((0, ly - 0.015, 0)) @ Matrix.Rotation(math.radians(90), 4, "X"),
                blue)
    heart = [(x, y + 0.7) for x, y in _heart(size=0.17)]
    p.prism(heart, 0.006, Matrix.Translation((0, ly - 0.016, 0)) @ Matrix.Rotation(math.radians(90), 4, "X"),
            red)
    p.box((sw - 0.02, 0.05, 0.04), (0, ly, 0.54), red, bevel=0.008)          # travessa sob o painel
    return p.mesh()


def _chairs(coll):
    me = _chair_mesh()
    out = {}
    for side, key in ((-1, "left"), (1, "right")):
        a = math.radians(CHAIR_CHEAT[key])
        facing = Vector((-side * math.cos(a), -math.sin(a), 0.0))
        yaw = math.atan2(facing.x, -facing.y)
        loc = (side * CHAIR_X, CHAIR_Y, 0.0)
        _instance(me, "INT_Chair_" + key.capitalize(), coll, 0.022, loc, (0, 0, yaw))
        out["chair_%s_seat" % key] = (loc[0], loc[1], SEAT_Z)
        out["chair_%s_facing" % key] = tuple(round(v, 4) for v in facing)
        out["chair_%s_rot" % key] = (0.0, 0.0, round(yaw, 4))
    return out


def _rug(coll, rnd):
    cx, cy = RUG
    n = 72
    pts = []
    for i in range(n):
        th = 2 * math.pi * i / n
        r = 1.0 + 0.05 * math.sin(3 * th + 0.5) + 0.035 * math.sin(7 * th + 1.3)
        for c, amp in ((math.radians(35), 0.2), (math.radians(145), 0.2), (math.radians(215), 0.22),
                       (math.radians(325), 0.22), (math.radians(90), 0.12)):
            d = math.atan2(math.sin(th - c), math.cos(th - c))
            r += amp * math.exp(-(d / 0.14) ** 2)
        r += rnd.uniform(-0.012, 0.012)
        pts.append((1.02 * r * math.cos(th), 0.74 * r * math.sin(th)))
    rug = _Part("INT_Rug")
    rug.prism(pts, 0.012, Matrix.Translation((cx, cy, 0.0005)), _m("rug"))
    rug.build(coll, outline=0.015)
    # mancha marrom do lombo (sem contorno, como pintura)
    spine = _Part("INT_RugSpine")
    sp = []
    for i in range(40):
        th = 2 * math.pi * i / 40
        r = 1.0 + 0.08 * math.sin(4 * th + 0.3) + rnd.uniform(-0.03, 0.03)
        sp.append((0.62 * r * math.cos(th), 0.2 * r * math.sin(th) * (1.0 - 0.35 * math.cos(th))))
    spine.prism(sp, 0.003, Matrix.Translation((cx - 0.05, cy + 0.03, 0.012)), _m("rug_brown"))
    spine.build(coll)
    return (cx, cy, 0.0125)


def _rag_rug(coll):
    """Trasmatta (tapete de retalhos listrado) diante da porta."""
    p = _Part("INT_RagRug")
    x0, x1, y0, y1 = -2.28, -1.58, -0.3, 0.72
    p.box((x1 - x0, y1 - y0, 0.01), ((x0 + x1) / 2, (y0 + y1) / 2, 0.005), _m("rag_cream"), bevel=0.003)
    p_top = _Part("INT_RagRugStripes")
    cols = [_m("rag_blue"), _m("rag_cream"), _m("rag_red"), _m("rag_cream")]
    y = y0 + 0.06
    i = 0
    while y < y1 - 0.08:
        w = 0.05 if i % 2 else 0.075
        p_top.box((x1 - x0 - 0.06, w, 0.002), ((x0 + x1) / 2, y + w / 2, 0.011), cols[i % 4])
        y += w
        i += 1
    p.build(coll, outline=0.012)
    p_top.build(coll)


def _wicker(p, r0, r1, h, inside=False):
    """Cesto de vime aberto (fundo r0, boca r1, altura h) com aro e alças; origem no chão."""
    wick, wdk = _m("wicker"), _m("wicker_dk")
    faces = p.cyl(r0, r1, h, (0, 0, h / 2), wick, segs=16)
    top = max(faces, key=lambda f: f.calc_center_median().z)
    bmesh.ops.delete(p.bm, geom=[top], context="FACES_ONLY")
    p.torus(r1, 0.024 * r1 / 0.27, (0, 0, h), wdk, segs=18, rsegs=6)
    for f in (0.32, 0.67):
        p.torus(r0 + (r1 - r0) * f + 0.002, 0.011, (0, 0, h * f), wdk, segs=16, rsegs=4)
    for sx in (-1, 1):
        p.torus(0.05 * r1 / 0.27, 0.012, (sx * (r1 + 0.005), 0, h + 0.035 * r1 / 0.27), wdk,
                rot=(math.radians(90), 0, 0), segs=10, rsegs=4)
    if inside:                          # miolo escuro logo abaixo do aro (lê como fundo do cesto)
        p.cyl(r1 - 0.03, r1 - 0.03, 0.006, (0, 0, h - 0.035), _m("gap"), segs=16, smooth=False)


def _basket(coll):
    bx, by = BASKET
    p = _Part("INT_CatBasket")
    _wicker(p, 0.21, 0.27, 0.2)
    p.build(coll, outline=0.016, loc=(bx, by, 0.0))

    c = _Part("INT_Cushion")
    c.sphere(1.0, (0, 0, 0.19), _m("cushion"), scale=(0.235, 0.215, 0.07), u=16, v=8)
    c.sphere(1.0, (0.12, 0.1, 0.235), _m("cushion"), scale=(0.07, 0.05, 0.035), u=8, v=5)  # ponta dobrada
    c.build(coll, outline=0.012, loc=(bx, by, 0.0))

    # dois cestos de vime vazios, como no 2D: um grande contra a parede do fundo
    # à direita do fogão, outro menor junto à parede da janela
    big = _Part("INT_WickerBasket")
    _wicker(big, 0.19, 0.23, 0.32, inside=True)
    big.build(coll, outline=0.016, loc=BASKET_BIG + (0.0,), rot=(0, 0, 0.3))
    small = _Part("INT_WickerBasketSmall")
    _wicker(small, 0.16, 0.2, 0.24, inside=True)
    small.build(coll, outline=0.014, loc=BASKET_SMALL + (0.0,), rot=(0, 0, 1.4))
    return (bx, by, 0.255)


def _door_and_hooks(coll):
    y0, y1, z0, z1 = DOOR
    xw = -W2
    p = _Part("INT_Door")
    # folha creme com almofadas de moldura vermelha e miolo creme (como no 2D),
    # guarnição de madeira natural
    door, red, casing = _m("door"), _m("rag_red"), _m("shelf")
    p.box((0.035, y1 - y0 - 0.04, z1 - 0.03), (xw + 0.0175, (y0 + y1) / 2, (z1 - 0.03) / 2 + 0.01), door)
    for zc, hh in ((1.52, 0.72), (0.6, 0.78)):
        p.box((0.012, y1 - y0 - 0.26, hh), (xw + 0.041, (y0 + y1) / 2, zc), red, bevel=0.005)
        p.box((0.004, y1 - y0 - 0.34, hh - 0.08), (xw + 0.049, (y0 + y1) / 2, zc), door)
    # guarnição
    cw = 0.08
    p.box((0.06, cw, z1 + cw), (xw + 0.03, y0 - cw / 2 + 0.01, (z1 + cw) / 2), casing, bevel=0.008)
    p.box((0.06, cw, z1 + cw), (xw + 0.03, y1 + cw / 2 - 0.01, (z1 + cw) / 2), casing, bevel=0.008)
    p.box((0.07, y1 - y0 + 2 * cw + 0.04, 0.1), (xw + 0.035, (y0 + y1) / 2, z1 + 0.05), casing, bevel=0.01)
    p.box((0.08, y1 - y0, 0.02), (xw + 0.04, (y0 + y1) / 2, 0.01), _m("post"), bevel=0.004)
    # dobradiças escuras e maçaneta
    for zc in (0.35, 1.7):
        p.box((0.008, 0.12, 0.035), (xw + 0.039, y1 - 0.1, zc), _m("iron"))
    knob = (xw + 0.07, y0 + 0.1, 1.0)
    p.cyl(0.03, 0.03, 0.01, (xw + 0.04, knob[1], knob[2]), _m("brass"), rot=(0, math.radians(90), 0), segs=10)
    p.sphere(0.026, knob, _m("brass"), u=10, v=6)
    p.build(coll, outline=0.018)

    # cabideiro entre a porta e o canto do fundo, xale mostarda pendurado
    h = _Part("INT_CoatRail")
    hy0, hy1, hz = 0.88, 1.58, 1.66
    xr = -W2 + PT
    h.box((0.025, hy1 - hy0, 0.1), (xr + 0.0125, (hy0 + hy1) / 2, hz), _m("shelf"), bevel=0.008)
    tip = None
    for i, yy in enumerate((hy0 + 0.13, (hy0 + hy1) / 2, hy1 - 0.13)):
        h.cyl(0.016, 0.016, 0.11, (xr + 0.07, yy, hz + 0.01), _m("post"),
              rot=(0, math.radians(72), 0), segs=8)
        h.sphere(0.022, (xr + 0.122, yy, hz + 0.028), _m("post"), u=8, v=5)
        if i == 1:
            tip = (xr + 0.122, yy, hz + 0.028)
    h.build(coll, outline=0.012)

    s = _Part("INT_Shawl")
    sy = hy1 - 0.13
    M = Matrix.Translation((xr + 0.1, sy, 0)) @ Matrix(((0, 0, 1, 0), (1, 0, 0, 0), (0, 1, 0, 0), (0, 0, 0, 1)))
    shape = [(-0.05, hz + 0.03), (0.05, hz + 0.03), (0.15, hz - 0.3), (0.13, hz - 0.62),
             (0.02, hz - 0.7), (-0.1, hz - 0.64), (-0.14, hz - 0.32)]
    s.prism([(u, v) for u, v in shape], 0.035, M @ Matrix.Translation((0, 0, -0.03)), _m("shawl"))
    for zz in (hz - 0.42, hz - 0.5):
        s.box((0.04, 0.27, 0.03), (xr + 0.1, sy + 0.012, zz), _m("trim"))
    s.build(coll, outline=0.012)

    return {
        "door_center": (xw + 0.035, (y0 + y1) / 2, 1.0),
        "door_knob": knob,
        "coat_hook": tip,
    }


def _window(coll):
    y0, y1, z0, z1 = WINDOW
    xw = W2
    trim = _m("trim")
    p = _Part("INT_Window")
    cw = 0.075
    xin = xw - PT - 0.025                  # face da guarnição de dentro
    depth = 0.2
    xc = xin + depth / 2 - 0.01
    p.box((depth, cw, z1 - z0 + 2 * cw), (xc, y0 - cw / 2 + 0.02, (z0 + z1) / 2), trim, bevel=0.008)
    p.box((depth, cw, z1 - z0 + 2 * cw), (xc, y1 + cw / 2 - 0.02, (z0 + z1) / 2), trim, bevel=0.008)
    p.box((depth, y1 - y0 + 2 * cw, cw), (xc, (y0 + y1) / 2, z1 + cw / 2 - 0.02), trim, bevel=0.008)
    # peitoril de dentro + avental
    p.box((0.26, y1 - y0 + 0.24, 0.045), (xw - 0.1, (y0 + y1) / 2, z0 - 0.0225), trim, bevel=0.01)
    p.box((0.025, y1 - y0 + 0.1, 0.12), (xin + 0.0125, (y0 + y1) / 2, z0 - 0.105), trim, bevel=0.005)
    # caixilho e pinázios: 2 colunas × 3 linhas
    xs = xw + 0.035
    fw = 0.045
    p.box((0.045, fw, z1 - z0), (xs, y0 + fw / 2, (z0 + z1) / 2), trim)
    p.box((0.045, fw, z1 - z0), (xs, y1 - fw / 2, (z0 + z1) / 2), trim)
    p.box((0.045, y1 - y0, fw), (xs, (y0 + y1) / 2, z0 + fw / 2), trim)
    p.box((0.045, y1 - y0, fw), (xs, (y0 + y1) / 2, z1 - fw / 2), trim)
    p.box((0.04, 0.035, z1 - z0), (xs, (y0 + y1) / 2, (z0 + z1) / 2), trim)
    for k in (1, 2):
        p.box((0.04, y1 - y0, 0.035), (xs, (y0 + y1) / 2, z0 + (z1 - z0) * k / 3), trim)
    # peitoril de fora
    p.box((0.2, y1 - y0 + 0.08, 0.045), (xw + 0.17, (y0 + y1) / 2, z0 - 0.03), trim, bevel=0.008)
    p.build(coll, outline=0.016)

    snow = _Part("INT_SillSnow")
    snow.box((0.17, y1 - y0 - 0.02, 0.09), (xw + 0.165, (y0 + y1) / 2, z0 + 0.03), _m("snow"),
             bevel=0.04, segs=3)
    snow.box((0.1, 0.16, 0.07), (xw + 0.15, y0 + 0.1, z0 + 0.08), _m("snow"), bevel=0.03, segs=2)
    snow.box((0.1, 0.2, 0.06), (xw + 0.15, y1 - 0.12, z0 + 0.07), _m("snow"), bevel=0.028, segs=2)
    snow.build(coll, outline=0.012)
    return {
        "window": (xin, (y0 + y1) / 2, (z0 + z1) / 2),
        "window_sill": (xw - 0.1, (y0 + y1) / 2, z0),
        "window_snow": (xw + 0.165, (y0 + y1) / 2, z0 + 0.075),
    }


def _outside(coll):
    """O que se vê pela janela: neve azulada, pinheiros pequenos lá longe (o céu é
    o mundo) e uma estrela de neve grande em cada vidraça, como nas ilustrações."""
    g = _Part("INT_OutsideSnow")
    g.box((60.0, 80.0, 0.1), (W2 + 0.2 + 30.0, 2.0, -0.05), _m("snow_far"))
    g.build(coll)
    t = _Part("INT_Pine")
    pine = _m("pine")
    t.cyl(0.12, 0.1, 0.6, (0, 0, 0.3), _m("bark"), segs=6, smooth=False)
    for z, r, hh in ((0.5, 1.0, 1.5), (1.3, 0.78, 1.3), (2.0, 0.55, 1.2), (2.6, 0.3, 0.9)):
        t.cyl(r, 0.0, hh, (0, 0, z + hh / 2), pine, segs=7, smooth=False)
    me = t.mesh()
    rnd = random.Random(SEED + 5)
    # longe (28–52 m): pela janela viram silhuetas pequenas (pontas à mostra) sob
    # o céu, sem a cunha verde que os pinheiros perto faziam nas vidraças
    spots = [(28.0, 9.0), (31.0, 2.0), (34.0, 15.0), (36.0, -5.0), (40.0, 8.0), (44.0, 20.0),
             (46.0, 1.0), (50.0, 13.0), (30.0, 22.0), (52.0, 26.0), (38.0, 31.0), (33.0, -12.0)]
    for i, (x, y) in enumerate(spots):
        s = rnd.uniform(1.5, 2.1)
        _instance(me, "INT_Pine.%02d" % i, coll, 0.0, (x, y, 0.0), (0, 0, rnd.uniform(0, 6.28)), (s, s, s))
    # uma estrela de neve (6 pontas) por vidraça, 2 colunas × 3 linhas, logo além
    # do caixilho e virada ~30° pra frente (-Y) pra ler também da câmera geral.
    # O diretor pode animá-las caindo (objeto INT_Flakes).
    fk = _Part("INT_Flakes")
    y0, y1, z0, z1 = WINDOW
    face = Matrix.Rotation(math.radians(30), 4, "Z") @ \
        Matrix(((0, 0, -1, 0), (1, 0, 0, 0), (0, 1, 0, 0), (0, 0, 0, 1)))
    for c in range(2):
        for r_ in range(3):
            cy = y0 + (y1 - y0) * (0.25 + 0.5 * c) + 0.03 + rnd.uniform(-0.03, 0.03)
            cz = z0 + (z1 - z0) * (1 / 6 + r_ / 3) + rnd.uniform(-0.04, 0.04)
            r = rnd.uniform(0.055, 0.075)
            cz = max(cz, z0 + 0.16 + r)          # acima do monte de neve do peitoril
            a0 = rnd.uniform(0, math.pi / 3)
            pts = [((r if k % 2 == 0 else r * 0.36) * math.cos(a0 + math.pi * k / 6),
                    (r if k % 2 == 0 else r * 0.36) * math.sin(a0 + math.pi * k / 6)) for k in range(12)]
            fk.prism(pts, 0.004, Matrix.Translation((W2 + 0.11, cy, cz)) @ face, _m("flake"))
    fk.build(coll)


def _picture_and_firewood(coll):
    p = _Part("INT_Picture")
    px, pz, y = 1.78, 1.58, Y1 - PT - 0.012
    p.box((0.46, 0.024, 0.36), (px, y, pz), _m("frame_wood"), bevel=0.008)
    p.box((0.36, 0.01, 0.26), (px, y - 0.014, pz), _m("plaster"))
    M = Matrix.Translation((px, y - 0.02, pz)) @ Matrix.Rotation(math.radians(90), 4, "X")
    p.prism([(-0.07, -0.09), (0.07, -0.09), (0.07, 0.0), (0.0, 0.06), (-0.07, 0.0)], 0.004,
            M, _m("rag_red"))
    p.prism([(0.1, -0.09), (0.16, -0.09), (0.13, 0.04)], 0.004, M, _m("pine"))
    p.build(coll, outline=0.012)

    w = _Part("INT_Firewood")
    rnd = random.Random(SEED + 9)
    fx, fy = 1.64, Y1 - PT - 0.2
    rows = ((3, 0.055), (2, 0.155), (1, 0.25))
    for n, z in rows:
        for i in range(n):
            x = fx + (i - (n - 1) / 2) * 0.115
            w.cyl(0.055, 0.055, 0.38 + rnd.uniform(-0.03, 0.03), (x, fy + rnd.uniform(-0.02, 0.02), z),
                  _m("bark"), rot=(math.radians(90), 0, rnd.uniform(-0.1, 0.1)), segs=7,
                  cap_mat=_m("log_end"))
    w.build(coll, outline=0.014)

    # balde de ferro com atiçadores, do lado esquerdo do fogão
    b = _Part("INT_HearthTools")
    bx, by = -0.6, 1.72
    b.cyl(0.085, 0.1, 0.22, (bx, by, 0.15), _m("iron"), segs=12)
    b.torus(0.1, 0.008, (bx, by, 0.26), _m("iron_hi"), segs=12, rsegs=4)
    for dx, tilt in ((-0.025, -10), (0.03, 12)):
        b.cyl(0.009, 0.009, 0.52, (bx + dx, by, 0.32), _m("iron_hi"), rot=(0, math.radians(tilt), 0), segs=5)
        b.sphere(0.018, (bx + dx + math.sin(math.radians(tilt)) * 0.26, by, 0.58), _m("brass"), u=6, v=4)
    b.build(coll, outline=0.012)


def _sconce(coll):
    """Arandela de latão com cúpula creme acesa, entre o quadro e a janela."""
    x, z = SCONCE
    yw = Y1 - PT                          # face das tábuas do fundo
    p = _Part("INT_Sconce")
    brass = _m("brass")
    p.box((0.07, 0.014, 0.14), (x, yw - 0.007, z - 0.05), brass, bevel=0.006)        # espelho
    p.cyl(0.011, 0.011, 0.1, (x, yw - 0.055, z - 0.08), brass, rot=(math.radians(90), 0, 0), segs=6)
    p.cyl(0.011, 0.011, 0.07, (x, yw - 0.11, z - 0.06), brass, segs=6)                # braço
    p.cyl(0.03, 0.03, 0.015, (x, yw - 0.12, z - 0.03), brass, segs=10)                # copinho
    p.cyl(0.075, 0.045, 0.1, (x, yw - 0.12, z + 0.01), _m("shade"), segs=12, smooth=False)
    p.build(coll, outline=0.012)
    return (x, yw - 0.12, z)


# ─── Luz ────────────────────────────────────────────────────────────────────
KEY_W = 100.0      # fogo: luz-chave na frente da boca do fogão (tremula ±9%)
GLOW_W = 40.0      # fogo: dentro da boca, faz a poça de luz no chão (tremula ±22%)
BOUNCE_W = 28.0    # rebatido quente e fraco, alto e na frente (sustenta a faixa média)
WINDOW_W = 70.0    # preenchimento frio da janela (fora, alto: entra pelo vão)
SCONCE_W = 6.0     # arandela de latão na parede do fundo (quente, fixa, sem sombra)
SCONCE = (2.2, 1.74)                # arandela: x na parede do fundo, z do centro da cúpula


def _flicker(idb, path, base, amp, phase, index=-1):
    """Driver determinístico (só `frame` e senos: expressão simples, roda sem Python)."""
    fc = idb.driver_add(path) if index < 0 else idb.driver_add(path, index)
    for mod in list(fc.modifiers):
        fc.modifiers.remove(mod)
    d = fc.driver
    d.type = "SCRIPTED"
    p = phase
    # só termos lentos (≤ 2 rad/quadro): um termo rápido "serrilharia" a 24 fps e
    # faria a borda das faixas do toon tremer quadro a quadro no rosto dos personagens
    d.expression = (
        "%.4f*(1+%.4f*(0.65*sin(frame*0.71+%.2f)+0.35*sin(frame*1.93+%.2f)))"
        % (base, amp, p, p * 2.1 + 0.4))
    return fc


def _lights(sc, coll, flames):
    sx, sy = STOVE
    fy = sy - STOVE_D / 2
    made = []
    key = T.warm_light(sc, (sx, fy - 0.35, 0.82), energy=KEY_W, color=(255, 160, 80), radius=0.02,
                       name="INT_FireKey")
    glow = T.warm_light(sc, (sx, fy + 0.02, MOUTH_Z0 + 0.13), energy=GLOW_W, color=(255, 140, 60),
                        radius=0.02, name="INT_FireGlow")
    bounce = T.warm_light(sc, (sx, -0.6, 2.3), energy=BOUNCE_W, color=(255, 205, 160), radius=0.8,
                          name="INT_Bounce")
    win = T.warm_light(sc, (W2 + 1.1, (WINDOW[0] + WINDOW[1]) / 2, 2.8), energy=WINDOW_W,
                       color=(150, 180, 255), radius=0.5, name="INT_WindowFill")
    lamp = T.warm_light(sc, (SCONCE[0], Y1 - PT - 0.12, SCONCE[1]), energy=SCONCE_W,
                        color=(255, 200, 130), radius=0.05, name="INT_SconceLight")
    bounce.data.use_shadow = False       # rebatido não projeta sombra (seria penumbra ruidosa)
    lamp.data.use_shadow = False         # a cúpula não recorta a luz (senão faria cones duros)
    made += [key, glow, bounce, win, lamp]
    for ob in made:
        for c in list(ob.users_collection):
            c.objects.unlink(ob)
        coll.objects.link(ob)
    _flicker(key.data, "energy", KEY_W, 0.09, 0.3)
    _flicker(glow.data, "energy", GLOW_W, 0.22, 1.7)
    fc = flames.driver_add("scale", 2)
    for mod in list(fc.modifiers):
        fc.modifiers.remove(mod)
    fc.driver.type = "SCRIPTED"
    fc.driver.expression = "1+0.13*sin(frame*0.93+0.4)+0.07*sin(frame*2.41+1.9)+0.04*sin(frame*5.3)"
    fc = flames.driver_add("scale", 0)
    for mod in list(fc.modifiers):
        fc.modifiers.remove(mod)
    fc.driver.type = "SCRIPTED"
    fc.driver.expression = "1+0.06*sin(frame*1.37+2.2)"
    return {"fire_light": tuple(key.location)}


# ─── Entrada ────────────────────────────────────────────────────────────────

def _norm2(x, y):
    n = math.hypot(x, y)
    return (x / n, y / n, 0.0)


def _yaw(f):
    return (0.0, 0.0, round(math.atan2(f[0], -f[1]), 4))


def build_interior(sc, world=True, flicker=True):
    """Constrói a sala da Farmor na cena `sc` e devolve o dict de âncoras (ver docstring do módulo).

    `world=True` põe um céu noturno escuro no mundo da cena (é o que se vê pela
    janela e dá o ambiente quase nulo). `flicker=False` tira os drivers do fogo.
    Não mexe em render/câmera: use `T.render_setup` e `add_camera`/CAMERAS.
    """
    rnd = random.Random(SEED)
    coll = bpy.data.collections.new("Set_Interior")
    sc.collection.children.link(coll)

    if world:
        T.sky(sc, top=(8, 14, 38), horizon=(34, 58, 104), name="INT_NightSky")

    A = {"floor_center": (0.0, 0.0, 0.0)}
    _walls(coll, rnd)
    _floor_and_ceiling(coll, rnd)
    stove_a, flames = _stove(coll)
    A.update(stove_a)
    A["shelf_top"] = _shelf_and_animals(coll)
    A.update(_chairs(coll))
    A["rug_center"] = _rug(coll, rnd)
    _rag_rug(coll)
    A["cat_basket"] = _basket(coll)
    A.update(_door_and_hooks(coll))
    A.update(_window(coll))
    _outside(coll)
    _picture_and_firewood(coll)
    A["sconce"] = _sconce(coll)
    lights = _lights(sc, coll, flames)
    if not flicker:
        for ob in coll.objects:
            for idb in (ob, ob.data):
                if idb is not None and getattr(idb, "animation_data", None):
                    idb.animation_data_clear()
    A.update(lights)

    # Em pé junto à porta (k06).
    A["door_inside"] = (-1.9, 0.15, 0.0)
    A["door_inside_facing"] = _norm2(0.93, -0.38)
    A["door_inside_rot"] = _yaw(A["door_inside_facing"])
    A["farmor_by_door"] = (-1.55, 0.8, 0.0)
    A["farmor_by_door_facing"] = _norm2(-0.1, -1.0)   # entre a Nell e a câmera (acena pra ela)
    A["farmor_by_door_rot"] = _yaw(A["farmor_by_door_facing"])

    for name, (loc, look, _lens) in CAMERAS.items():
        A[name] = tuple(loc)
        A[name + "_look"] = tuple(look)

    A = {k: tuple(round(float(c), 4) for c in v) for k, v in A.items()}
    coll["anchors"] = {k: list(v) for k, v in A.items()}
    coll["camera_lens"] = {k: v[2] for k, v in CAMERAS.items()}
    return A


def add_camera(sc, which="cam_wide", name=None):
    """Cria (e ativa) a câmera sugerida `which` de CAMERAS via `T.camera`."""
    loc, look, lens = CAMERAS[which]
    return T.camera(sc, loc, look, lens=lens, name=name or ("INT_" + which))
