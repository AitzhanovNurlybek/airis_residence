"""
3D-модель Airis Residence: здание по техпаспорту + квартал по OpenStreetMap.

Запуск:
  blender.exe -b --factory-startup -P build_hotel.py -- <папка рендеров> [быстро]

Здание (поэтажные планы техпаспорта, масштаб 1:200):
  1 этаж (лит. Д, 1962): 22,80 × 11,96 м, высота 3,25;
  лобби-пристройка (лит. Д1, 2025): 10,80 × 11,32 м, высота 3,25 —
    с восточной стороны, у южного конца (план участка);
  2–3 этажи (лит. Д2, 2025): 22,80 × 15,76 м, этаж 3,00 —
    выступают над лобби на 3,8 м к востоку.
Ориентация — по контуру здания в OSM: длинная сторона идёт с севера на юг,
повёрнута на 5,5° к западу. Улица Наурызбай батыра в 56 м к западу.

Локальные оси здания: x — вдоль длинной стороны с юга на север (0…22,8),
y — поперёк с востока на запад (0 — восточный фасад верхних этажей), z — вверх.

1 этаж — по рисунку и рассказу управляющей (2026-11-25): основной корпус
(3 Comfort Plus, 2 Standart, Twin, завтрак с кухней, лестница), фойе со
входом, ресепшн и кофейней, второй одноэтажный корпус справа от входа
(служебные кабинеты, Standart, Apart). 2 и 3 этажи — по площади из
техпаспорта: по 3 Comfort и 1 Twin, одноместный на 2 этаже.

Режимы: «кадры» — четыре кадра для Higgsfield («этаж1» — только 1 этаж),
«точки» — где на кадре центры номеров и подписи зон 1 этажа.
"""

import json
import math
import os
import sys

import bmesh
import bpy
from mathutils import Matrix, Vector

ARGS = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
OUT = ARGS[0] if ARGS else "."
FAST = "быстро" in ARGS
HERE = os.path.dirname(os.path.abspath(__file__))
OSM = os.path.join(HERE, "osm", "around.json")

L = 22.80
D_UP = 15.76
D_1 = 11.96
Y1 = D_UP - D_1           # восточная стена 1 этажа (3,80)
H1 = 3.25
SLAB = 0.30
H_UP = 3.00
Z2 = H1 + SLAB
Z3 = Z2 + H_UP
Z_ROOF = Z3 + H_UP
WALL = 0.30
PART = 0.12
ANNEX_X = 10.80
ANNEX_D = 11.32
ROT = math.radians(95.5)  # локальная x → север с наклоном 5,5° к западу
CENTER_WORLD = Vector((0.05, -0.5, 0.0))   # центр контура в OSM

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
COLL: dict[str, bpy.types.Collection] = {}
FONT = bpy.data.fonts.load("C:/Windows/Fonts/arialbd.ttf")

root = bpy.data.objects.new("hotel_root", None)
scene.collection.objects.link(root)
root.rotation_euler = (0, 0, ROT)
root.location = CENTER_WORLD - Matrix.Rotation(ROT, 3, "Z") @ Vector((L / 2, D_UP / 2, 0))


def coll(name):
    if name not in COLL:
        c = bpy.data.collections.new(name)
        scene.collection.children.link(c)
        COLL[name] = c
    return COLL[name]


def mat(name, rgb, rough=0.7, metal=0.0, emit=0.0):
    m = bpy.data.materials.get(name)
    if m:
        return m
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (*rgb, 1)
    b.inputs["Roughness"].default_value = rough
    b.inputs["Metallic"].default_value = metal
    if emit:
        b.inputs["Emission Color"].default_value = (*rgb, 1)
        b.inputs["Emission Strength"].default_value = emit
    return m


M = {
    "cream": mat("cream", (0.84, 0.78, 0.66)),
    "band": mat("band", (0.36, 0.32, 0.29)),
    "taupe": mat("taupe", (0.30, 0.27, 0.25)),
    "glass": mat("glass", (0.07, 0.09, 0.11), rough=0.05, metal=0.5),
    "frame": mat("frame", (0.20, 0.20, 0.21)),
    "roof": mat("roof", (0.78, 0.78, 0.76)),
    "slab": mat("slab", (0.88, 0.87, 0.84)),
    "wall_in": mat("wall_in", (0.95, 0.94, 0.91)),
    "tile": mat("tile", (0.58, 0.59, 0.60), rough=0.4),
    "ceramic": mat("ceramic", (0.97, 0.97, 0.97), rough=0.2),
    "bed": mat("bed", (0.96, 0.96, 0.95), rough=0.95),
    "blanket": mat("blanket", (0.47, 0.49, 0.52), rough=0.95),
    "wood": mat("wood", (0.52, 0.36, 0.22)),
    "sofa": mat("sofa", (0.74, 0.70, 0.64), rough=0.95),
    "red": mat("red", (0.50, 0.05, 0.07), rough=0.9),
    "desk": mat("desk", (0.25, 0.25, 0.26), rough=0.4),
    "stair": mat("stair", (0.42, 0.30, 0.20)),
    "corridor": mat("corridor", (0.66, 0.60, 0.52)),
    "lobby_floor": mat("lobby_floor", (0.72, 0.71, 0.69), rough=0.3),
    "service": mat("service", (0.80, 0.80, 0.79)),
    "cat_comfort_plus": mat("cat_comfort_plus", (0.80, 0.52, 0.20), rough=0.9),
    "cat_comfort": mat("cat_comfort", (0.86, 0.68, 0.36), rough=0.9),
    "cat_apart": mat("cat_apart", (0.80, 0.42, 0.38), rough=0.9),
    "cat_standart": mat("cat_standart", (0.47, 0.54, 0.63), rough=0.9),
    "cat_twin": mat("cat_twin", (0.46, 0.62, 0.49), rough=0.9),
    "cat_single": mat("cat_single", (0.63, 0.53, 0.70), rough=0.9),
    "ground": mat("ground", (0.66, 0.65, 0.62), rough=1.0),
    "road": mat("road", (0.22, 0.22, 0.23), rough=0.9),
    "walk": mat("walk", (0.78, 0.77, 0.74), rough=0.9),
    "context": mat("context", (0.92, 0.91, 0.89), rough=0.8),
    "label": mat("label", (1.0, 1.0, 1.0), rough=0.5, emit=0.6),
    "sign": mat("sign", (0.97, 0.97, 0.98), rough=0.3, emit=1.5),
    "sign_text": mat("sign_text", (0.10, 0.18, 0.45), rough=0.4),
}


def _place(o, collection, local=True):
    for c in o.users_collection:
        c.objects.unlink(o)
    coll(collection).objects.link(o)
    if local:
        o.parent = root


def box(name, x0, y0, z0, x1, y1, z1, material, collection, local=True):
    """Параллелепипед по двум углам (в осях здания, если local)."""
    bpy.ops.mesh.primitive_cube_add(size=1)
    o = bpy.context.active_object
    o.name = name
    o.location = ((x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2)
    o.scale = (abs(x1 - x0), abs(y1 - y0), abs(z1 - z0))
    o.data.materials.append(M[material])
    _place(o, collection, local)
    return o


def cyl(name, x, y, z0, z1, r, material, collection):
    bpy.ops.mesh.primitive_cylinder_add(radius=r, depth=z1 - z0, location=(x, y, (z0 + z1) / 2), vertices=16)
    o = bpy.context.active_object
    o.name = name
    o.data.materials.append(M[material])
    _place(o, collection)
    return o


def text(name, body, size, material, collection, loc, rot_z=0.0, flat=True, local=False, extrude=0.02):
    cu = bpy.data.curves.new(name, "FONT")
    cu.body = body
    cu.font = FONT
    cu.size = size
    cu.align_x = "CENTER"
    cu.align_y = "CENTER"
    cu.extrude = extrude
    o = bpy.data.objects.new(name, cu)
    o.data.materials.append(M[material])
    scene.collection.objects.link(o)
    o.location = loc
    o.rotation_euler = (0 if flat else math.radians(90), 0, rot_z)
    _place(o, collection, local)
    return o


def rect_walls(prefix, x0, y0, x1, y1, z0, z1, material, collection, t=PART):
    """Четыре тонкие стены по контуру прямоугольника."""
    box(f"{prefix}_w1", x0, y0, z0, x1, y0 + t, z1, material, collection)
    box(f"{prefix}_w2", x0, y1 - t, z0, x1, y1, z1, material, collection)
    box(f"{prefix}_w3", x0, y0, z0, x0 + t, y1, z1, material, collection)
    box(f"{prefix}_w4", x1 - t, y0, z0, x1, y1, z1, material, collection)


ROOMS: dict[int, list[dict]] = {1: [], 2: [], 3: []}


def room(floor, name, cat, x0, y0, x1, y1, z, collection, window_side, sofa=True):
    """Пол номера цвета категории, мебель по категории. window_side: +1 — окно при y1, −1 — при y0."""
    box(f"{name}_floor", x0, y0, z + 0.02, x1, y1, z + 0.04, f"cat_{cat}", collection)
    ROOMS[floor].append({"name": name, "cat": cat, "x0": x0, "y0": y0, "x1": x1, "y1": y1})
    furnish(name, cat, x0, y0, x1, y1, z, collection, window_side, sofa)


def bed(name, x0, width, head_y, sgn, z, collection, length=2.0):
    foot = head_y - sgn * length
    a, b = sorted((head_y, foot))
    box(f"{name}_mattress", x0, a, z, x0 + width, b, z + 0.48, "bed", collection)
    a, b = sorted((foot + sgn * 0.85, foot))
    box(f"{name}_throw", x0 - 0.02, a, z + 0.48, x0 + width + 0.02, b, z + 0.50, "blanket", collection)
    a, b = sorted((head_y, head_y - sgn * 0.08))
    box(f"{name}_head", x0 - 0.18, a, z, x0 + width + 0.18, b, z + 1.15, "wood", collection)
    a, b = sorted((head_y - sgn * 0.12, head_y - sgn * 0.5))
    box(f"{name}_pillow", x0 + 0.08, a, z + 0.48, x0 + width - 0.08, b, z + 0.62, "bed", collection)


def furnish(name, cat, x0, y0, x1, y1, z, c, window_side, sofa=True):
    w = x1 - x0
    head = (y1 - 0.06) if window_side > 0 else (y0 + 0.06)
    sgn = window_side
    if cat == "twin":
        bed(f"{name}_b1", x0 + 0.25, 0.9, head, sgn, z, c)
        bed(f"{name}_b2", x1 - 1.15, 0.9, head, sgn, z, c)
    elif cat == "single":
        bed(f"{name}_b", x0 + (w - 0.9) / 2, 0.9, head, sgn, z, c)
    else:
        bw = 1.8 if cat in ("comfort", "comfort_plus") else 1.6
        bx = x0 + (w - bw) / 2 if w < 4.2 else x0 + 0.7
        bed(f"{name}_b", bx, bw, head, sgn, z, c)
        if w >= 4.2 and sofa:
            # диван и столик у второй стены
            far = head - sgn * 3.0
            a, b = sorted((far, far - sgn * 0.85))
            box(f"{name}_sofa", x1 - 2.3, a, z, x1 - 0.3, b, z + 0.72, "sofa", c)
            cyl(f"{name}_table", x1 - 1.3, far - sgn * 1.5, z, z + 0.7, 0.3, "wood", c)
        if cat == "apart":
            # мини-кухня вдоль стены
            a, b = sorted((head - sgn * 2.4, head - sgn * 3.6))
            box(f"{name}_kitchen", x0 + 0.1, a, z, x0 + 0.7, b, z + 0.9, "desk", c)


def bathroom(name, x0, y0, x1, y1, z, c):
    box(f"{name}_floor", x0, y0, z + 0.02, x1, y1, z + 0.045, "tile", c)
    rect_walls(name, x0, y0, x1, y1, z, z + 2.6, "wall_in", c, t=0.08)
    box(f"{name}_wc", x0 + 0.15, y0 + 0.15, z, x0 + 0.55, y0 + 0.65, z + 0.42, "ceramic", c)
    box(f"{name}_sink", x1 - 0.65, y0 + 0.12, z + 0.75, x1 - 0.15, y0 + 0.5, z + 0.88, "ceramic", c)


def windows_long(prefix, xs, y_face, sign, z0, z1, width, c):
    """Окна на длинном фасаде: стекло и рама чуть наружу."""
    for i, xc in enumerate(xs):
        a, b = sorted((y_face, y_face + sign * 0.07))
        box(f"{prefix}_{i}_f", xc - width / 2 - 0.08, a, z0 - 0.08, xc + width / 2 + 0.08, b, z1 + 0.08, "frame", c)
        a, b = sorted((y_face + sign * 0.07, y_face + sign * 0.09))
        box(f"{prefix}_{i}_g", xc - width / 2, a, z0, xc + width / 2, b, z1, "glass", c)


# ───────────────────────────── 1 этаж ─────────────────────────────
# Планировку 1 этажа нарисовала и объяснила управляющая отеля (видео
# 2026-11-25): основной корпус — номера, завтрак и лестница; посередине
# фойе со входом, ресепшн и кофейней; справа второй корпус — служебные
# кабинеты, Standart и Apart. Наружный контур — по техпаспорту, а
# перегородки внутри — по её рисунку (рисунок без масштаба, размеры
# комнат подобраны так, чтобы всё легло в контур).
#
# Основной корпус: x 0…22,8 (юг → север), y 3,8…15,76 (восток → запад).
# Запад (дальний ряд): Comfort Plus, Standart, Twin, Comfort Plus.
# Восток (у фойе):     завтрак с кухней, проход из фойе, лестница,
#                      Standart, Comfort Plus.
Y_E0, Y_E1 = Y1 + WALL, 8.9          # восточный ряд
Y_C0, Y_C1 = 8.9, 10.3               # коридор
Y_W0, Y_W1 = 10.3, D_UP - WALL       # западный ряд
PASSAGE = (7.4, 10.0)                # проём из фойе в корпус

# Места без кружков номеров: сайт кладёт поверх подписи (кириллицу
# генератор портит, поэтому в кадре текста нет).
ZONES: list[dict] = []


def zone(key, x, y):
    ZONES.append({"id": key, "x": x, "y": y})


def floor_one():
    c = "floor1"
    z = 0.0
    top = H1 - 0.05
    box("f1_floor", 0, Y1, -0.05, L, D_UP, 0.0, "slab", c)
    box("f1_wall_w", 0, D_UP - WALL, 0, L, D_UP, H1, "cream", c)
    box("f1_wall_e_s", 0, Y1, 0, PASSAGE[0], Y1 + WALL, H1, "cream", c)
    box("f1_wall_e_n", PASSAGE[1], Y1, 0, L, Y1 + WALL, H1, "cream", c)
    box("f1_wall_s", 0, Y1, 0, WALL, D_UP, H1, "cream", c)
    box("f1_wall_n", L - WALL, Y1, 0, L, D_UP, H1, "cream", c)

    # коридор вдоль корпуса и холл от проёма из фойе
    box("f1_corr", WALL, Y_C0, z + 0.02, L - WALL, Y_C1, z + 0.035, "corridor", c)
    box("f1_hall", 6.4, Y_E0, z + 0.02, 10.3, Y_C0, z + 0.035, "corridor", c)

    rooms = [
        # имя, категория, x0, x1, ряд (+1 запад / −1 восток)
        ("f1_cp_sw", "comfort_plus", WALL, 6.4, +1),
        ("f1_std_w", "standart", 6.4, 10.3, +1),
        ("f1_twin", "twin", 10.3, 14.4, +1),
        ("f1_cp_nw", "comfort_plus", 14.4, L - WALL, +1),
        ("f1_std_e", "standart", 11.9, 16.6, -1),
        ("f1_cp_ne", "comfort_plus", 16.6, L - WALL, -1),
    ]
    for name, cat, x0, x1, side in rooms:
        y0, y1 = (Y_W0, Y_W1) if side > 0 else (Y_E0, Y_E1)
        rect_walls(name, x0, y0, x1, y1, z, top, "wall_in", c)
        room(1, name, cat, x0 + PART, y0 + PART, x1 - PART, y1 - PART, z, c, side)
        w = x1 - x0
        if side > 0:
            bathroom(f"{name}_bath", x0 + 0.15, y0 + 0.15, x0 + min(1.7, w * 0.45), y0 + 2.4, z, c)
        else:
            bathroom(f"{name}_bath", x0 + 0.15, y1 - 2.4, x0 + min(1.7, w * 0.45), y1 - 0.15, z, c)

    # завтрак с кухней — у фойе, в юго-восточном углу корпуса
    x0, x1, y0, y1 = WALL, 6.4, Y_E0, Y_E1
    rect_walls("f1_breakfast", x0, y0, x1, y1, z, top, "wall_in", c)
    box("f1_breakfast_floor", x0 + PART, y0 + PART, z + 0.02, x1 - PART, y1 - PART, z + 0.04, "lobby_floor", c)
    box("f1_kitchen", x0 + 0.2, y0 + 0.4, z, x0 + 0.85, y1 - 0.4, z + 0.92, "desk", c)
    box("f1_kitchen_top", x0 + 0.15, y0 + 0.4, z + 0.92, x0 + 0.9, y1 - 0.4, z + 0.96, "ceramic", c)
    box("f1_buffet", 2.0, y1 - 1.0, z, 5.4, y1 - 0.4, z + 0.9, "wood", c)
    for i in range(2):
        for j in range(2):
            tx, ty = 2.6 + i * 2.0, y0 + 1.1 + j * 1.6
            cyl(f"f1_bf_table_{i}_{j}", tx, ty, z, z + 0.75, 0.42, "wood", c)
            for k, (dx, dy) in enumerate(((0.65, 0), (-0.65, 0))):
                cyl(f"f1_bf_chair_{i}_{j}_{k}", tx + dx, ty + dy, z, z + 0.5, 0.2, "sofa", c)
    zone("breakfast", 3.3, (y0 + y1) / 2)

    stair("f1", 10.3, Y_E0, 11.9, Y_E1, z, c)
    zone("stairs", 11.1, (Y_E0 + Y_E1) / 2)

    # окна запада: по два на большой номер, по одному на остальные
    xs = [1.8, 4.6, 8.35, 12.35, 16.6, 20.3]
    windows_long("f1_win_w", xs, D_UP, +1, 0.95, 2.45, 1.3, c)


def stair(prefix, x0, y0, x1, y1, z, c, height=None):
    height = height or (H1 + SLAB)
    box(f"{prefix}_stair_floor", x0, y0, z + 0.02, x1, y1, z + 0.035, "corridor", c)
    steps = 12
    run = (y1 - y0 - 0.3) / steps
    for i in range(steps):
        box(f"{prefix}_step{i}", x0 + 0.08, y0 + 0.15 + i * run, z,
            x1 - 0.08, y0 + 0.15 + (i + 1) * run, z + (i + 1) * height / 2 / steps, "stair", c)


# ───────────────────────────── фойе (Д1) ──────────────────────────
def lobby():
    c = "floor1"
    y_e = Y1 - ANNEX_D            # восточный фасад фойе
    box("lobby_floor", 0, y_e, -0.05, ANNEX_X, Y1, 0.02, "lobby_floor", c)
    box("lobby_wall_s", 0, y_e, 0, WALL, Y1, H1, "taupe", c)
    box("lobby_wall_n", ANNEX_X - WALL, y_e, 0, ANNEX_X, Y1, H1, "taupe", c)
    box("lobby_wall_e", 0, y_e, 0, ANNEX_X, y_e + WALL, H1, "taupe", c)
    box("lobby_roof", 0, y_e, H1, ANNEX_X, Y1 - 3.8, H1 + 0.35, "roof", "roof_lobby")
    # большие витрины на восток и юг, вход у северного конца — рядом со
    # вторым корпусом, как на рисунке и на фото входа
    box("lobby_glass_e1", 0.8, y_e - 0.06, 0.15, 5.6, y_e, 2.9, "glass", c)
    box("lobby_door", 7.6, y_e - 0.06, 0.0, 9.3, y_e, 2.5, "glass", c)
    box("lobby_canopy", 7.0, y_e - 1.4, 2.7, 10.0, y_e, 2.95, "taupe", c)
    box("lobby_glass_s", -0.06, y_e + 1.0, 0.15, 0.0, Y1 - 1.0, 2.9, "glass", c)
    zone("entrance", 8.45, y_e + 0.6)

    # ресепшн — новое место: у стены корпуса, напротив входа, рядом с
    # проходом к номерам и лестнице
    box("reception", 4.3, 1.2, 0, 7.0, 1.9, 1.1, "desk", c)
    box("reception_back", 3.9, Y1 - 0.6, 0, 7.3, Y1 - 0.3, 2.8, "wood", c)
    box("reception_accent", 4.6, Y1 - 0.65, 0.9, 6.6, Y1 - 0.6, 2.4, "red", c)
    zone("reception", 5.65, 1.55)

    # кофейня — южная часть фойе: полукруглая стойка и столики
    cx, cy, r = WALL, 0.6, 2.2
    for i in range(9):
        a = math.radians(-90 + i * 11.25)
        bx, by = cx + r * math.cos(a), cy + r * math.sin(a)
        box(f"coffee_bar_{i}", bx - 0.3, by - 0.3, 0, bx + 0.3, by + 0.3, 1.05, "wood", c)
    box("coffee_back", WALL, -1.4, 0, WALL + 0.5, 2.6, 2.2, "desk", c)
    for i in range(2):
        for j in range(2):
            tx, ty = 1.4 + i * 1.6, y_e + 1.6 + j * 1.9
            cyl(f"cafe_table_{i}_{j}", tx, ty, 0, 0.75, 0.38, "wood", c)
            for k, (dx, dy) in enumerate(((0.6, 0), (-0.6, 0))):
                cyl(f"cafe_chair_{i}_{j}_{k}", tx + dx, ty + dy, 0, 0.5, 0.22, "sofa", c)
    zone("coffee", 1.6, -1.6)

    # диваны посередине фойе
    for i, (sx, sy) in enumerate(((5.0, y_e + 2.0), (5.0, y_e + 4.6))):
        box(f"lobby_sofa{i}", sx, sy, 0, sx + 2.6, sy + 0.9, 0.75, "sofa", c)
    box("lobby_rug", 4.6, y_e + 1.6, 0.02, 8.0, y_e + 6.0, 0.03, "tile", c)
    # наружная лестница у входа
    for i in range(4):
        box(f"lobby_step{i}", 8.0, y_e - 0.3 * (i + 1), 0, 9.6, y_e - 0.3 * i, 0.15 * (4 - i), "walk", c)


# ───────────────────────────── второй корпус ──────────────────────
# Одноэтажный, справа от входа (на фото входа — коричневый объём с окном).
# По рисунку: служебные кабинеты у фасада, кабинет управляющей, Standart
# и в глубине Apart.
B2_X0, B2_X1 = ANNEX_X, 21.6
B2_Y0, B2_Y1 = -6.0, Y1


def second_building():
    c = "floor1"
    z = 0.0
    top = H1 - 0.05
    box("b2_floor", B2_X0, B2_Y0, -0.05, B2_X1, B2_Y1, 0.0, "slab", c)
    box("b2_wall_e", B2_X0, B2_Y0, 0, B2_X1, B2_Y0 + WALL, H1, "taupe", c)
    box("b2_wall_n", B2_X1 - WALL, B2_Y0, 0, B2_X1, B2_Y1, H1, "taupe", c)
    # крыша только у части, что выступает из-под верхних этажей
    box("b2_roof", B2_X0, B2_Y0, H1, B2_X1, 0.0, H1 + 0.35, "roof", "roof_lobby")
    # окна фасада: кабинеты
    for i, xc in enumerate((13.6, 18.8)):
        box(f"b2_win_{i}", xc - 0.9, B2_Y0 - 0.06, 0.9, xc + 0.9, B2_Y0, 2.4, "glass", c)

    x0, x1 = B2_X0 + WALL, B2_X1 - WALL
    # Apart в глубине, вдоль стены основного корпуса
    rect_walls("b2_apart", x0, 0.0, x1, Y1, z, top, "wall_in", c)
    room(1, "f1_apart", "apart", x0 + PART, PART, x1 - PART, Y1 - PART, z, c, +1, sofa=False)
    bathroom("b2_apart_bath", x1 - 2.0, 0.15, x1 - 0.15, 2.4, z, c)
    # Standart и кабинет управляющей — со стороны фойе, дальше коридор
    rect_walls("b2_std", x0, -3.0, 14.6, 0.0, z, top, "wall_in", c)
    room(1, "f1_std_b2", "standart", x0 + PART, -3.0 + PART, 14.6 - PART, -PART, z, c, +1, sofa=False)
    rect_walls("b2_office", 14.6, -3.0, 17.0, 0.0, z, top, "wall_in", c)
    box("b2_office_floor", 14.6, -3.0, z + 0.02, 17.0, 0.0, z + 0.035, "service", c)
    box("b2_office_desk", 15.0, -1.4, z, 16.6, -0.7, z + 0.75, "wood", c)
    box("b2_hall", 17.0, -3.0, z + 0.02, x1, 0.0, z + 0.035, "corridor", c)
    # два служебных кабинета у фасада
    for i, (a, b) in enumerate(((x0, 16.2), (16.2, x1))):
        rect_walls(f"b2_staff{i}", a, B2_Y0 + WALL, b, -3.0, z, top, "wall_in", c)
        box(f"b2_staff{i}_floor", a, B2_Y0 + WALL, z + 0.02, b, -3.0, z + 0.035, "service", c)
        box(f"b2_staff{i}_desk", a + 0.8, -4.6, z, a + 2.6, -3.9, z + 0.75, "wood", c)
    zone("staff", 16.2, -4.3)


# ───────────────────────────── 2–3 этажи ──────────────────────────
CAT_UP = {
    # запад (слева направо = с юга на север): пом. 3,4,7,9,10,13,14;
    # восток: 27,26,23,[лестница],22,19,18
    2: (["comfort", "standart", "standart", "single", "standart", "standart", "standart"],
        ["standart", "twin", "comfort", "comfort", "standart", "standart"]),
    3: (["comfort", "standart", "standart", "standart", "standart", "standart", "standart"],
        ["standart", "twin", "comfort", "comfort", "standart", "standart"]),
}
WIDTHS = {
    2: ([2.64, 2.96, 2.95, 2.95, 2.93, 2.95, 2.96], [2.74, 2.94, 5.20, 2.69, 4.47, 2.90, 2.97]),
    3: ([2.69, 2.97, 2.97, 2.97, 2.95, 2.95, 2.94], [2.92, 3.01, 4.69, 2.52, 4.70, 2.95, 2.96]),
}


def scaled(widths, total):
    k = total / sum(widths)
    return [w * k for w in widths]


def upper_floor(n, z):
    c = f"floor{n}"
    top = z + 2.80
    box(f"f{n}_floor", 0, 0, z - SLAB, L, D_UP, z, "slab", c)
    for name, x0, y0, x1, y1 in ((f"f{n}_wall_e", 0, 0, L, WALL), (f"f{n}_wall_w", 0, D_UP - WALL, L, D_UP),
                                 (f"f{n}_wall_s", 0, 0, WALL, D_UP), (f"f{n}_wall_n", L - WALL, 0, L, D_UP)):
        box(name, x0, y0, z, x1, y1, top + 0.2, "cream", c)

    inner = L - 2 * WALL
    y_e0, y_e1 = WALL, WALL + 6.58
    y_c0, y_c1 = y_e1 + PART, y_e1 + PART + 1.48
    y_w0, y_w1 = y_c1 + PART, D_UP - WALL
    box(f"f{n}_corr", WALL, y_c0, z + 0.02, L - WALL, y_c1, z + 0.035, "corridor", c)
    box(f"f{n}_corr_we", WALL, y_e1, z, L - WALL, y_c0, top, "wall_in", c)
    box(f"f{n}_corr_ww", WALL, y_c1, z, L - WALL, y_w0, top, "wall_in", c)

    west_w, east_w = WIDTHS[n]
    west_c, east_c = CAT_UP[n]
    win_e, win_w = [], []
    x = WALL
    for i, w in enumerate(scaled(west_w, inner - 6 * PART)):
        nm = f"f{n}_w{i}"
        room(n, nm, west_c[i], x, y_w0, x + w, y_w1, z, c, +1)
        bathroom(f"{nm}_bath", x + 0.05, y_w0 + 0.05, x + min(1.55, w * 0.55), y_w0 + 2.6, z, c)
        win_w.append(x + w / 2 + 0.3)
        x += w
        if i < 6:
            box(f"f{n}_pw{i}", x, y_w0, z, x + PART, y_w1, top, "wall_in", c)
            x += PART
    x = WALL
    k = 0
    for i, w in enumerate(scaled(east_w, inner - 6 * PART)):
        if i == 3:
            stair(f"f{n}", x, y_e0, x + w, y_e1, z, c, height=H_UP)
        else:
            nm = f"f{n}_e{k}"
            room(n, nm, east_c[k], x, y_e0, x + w, y_e1, z, c, -1)
            bathroom(f"{nm}_bath", x + 0.05, y_e1 - 2.6, x + min(1.55, w * 0.55), y_e1 - 0.05, z, c)
            win_e.append(x + w / 2 + 0.3)
            k += 1
        x += w
        if i < 6:
            box(f"f{n}_pe{i}", x, y_e0, z, x + PART, y_e1, top, "wall_in", c)
            x += PART
    windows_long(f"f{n}_win_w", win_w, D_UP, +1, z + 0.9, z + 2.35, 1.1, c)
    windows_long(f"f{n}_win_e", win_e, 0, -1, z + 0.9, z + 2.35, 1.1, c)


def facade_and_roof():
    c = "roof"
    box("roof", 0, 0, Z_ROOF, L, D_UP, Z_ROOF + 0.3, "roof", c)
    for name, x0, y0, x1, y1 in (("par_e", 0, 0, L, 0.25), ("par_w", 0, D_UP - 0.25, L, D_UP),
                                 ("par_s", 0, 0, 0.25, D_UP), ("par_n", L - 0.25, 0, L, D_UP)):
        box(name, x0, y0, Z_ROOF, x1, y1, Z_ROOF + 0.75, "cream", c)
    box("roof_hut", 10.6, 1.4, Z_ROOF, 13.4, 4.6, Z_ROOF + 2.4, "cream", c)
    for i, (vx, vy) in enumerate(((4, 5), (7, 11), (16, 4), (19, 12), (14, 9), (2.5, 12.5))):
        cyl(f"vent{i}", vx, vy, Z_ROOF, Z_ROOF + 1.0, 0.18, "band", c)
    # тёмные вертикальные вставки на фасадах (как на съёмке сверху)
    for i, bx in enumerate((7.6, 15.2)):
        box(f"band_e{i}", bx, -0.12, Z2 - SLAB, bx + 0.9, 0.0, Z_ROOF + 0.75, "band", "facade")
        box(f"band_w{i}", bx, D_UP, H1 * 0.0, bx + 0.9, D_UP + 0.12, Z_ROOF + 0.75, "band", "facade")
    # вывеска AIRIS HOTEL: светлый короб на тёмном объёме, юго-восточный угол
    box("sign_base", -0.6, -0.6, Z2, 0.4, 1.4, Z_ROOF + 1.4, "taupe", "facade")
    box("sign_box", -0.78, -0.55, Z2 + 0.6, -0.6, 1.35, Z_ROOF + 1.3, "sign", "facade")
    for i, ch in enumerate("AIRIS"):
        t = text(f"sign_{ch}{i}", ch, 1.0, "sign_text", "facade",
                 (-0.81, 0.4, Z_ROOF + 0.55 - i * 0.95), flat=False, local=True)
        t.rotation_euler = (math.radians(90), 0, math.radians(-90))
    t = text("sign_hotel", "HOTEL", 0.5, "sign_text", "facade", (-0.81, 0.4, Z2 + 1.3), flat=False, local=True)
    t.rotation_euler = (math.radians(90), 0, math.radians(-90))


# ───────────────────────────── квартал из OSM ─────────────────────
ROAD_W = {"secondary": 15, "tertiary": 11, "residential": 7.5, "service": 4.5, "living_street": 5,
          "footway": 1.8, "path": 1.5, "cycleway": 2, "pedestrian": 4, "steps": 1.8}
NAMES = {
    "Наурызбай Батыр көшесі": "ул. Наурызбай батыра",
    "Чайковский көшесі": "ул. Чайковского",
    "Құрманғазы көшесі": "ул. Курмангазы",
    "Шевченко көшесі": "ул. Шевченко",
    "Желтоқсан көшесі": "ул. Желтоксан",
    "Мәуленов көшесі": "ул. Мауленова",
    "Жамбыл көшесі": "ул. Жамбыла",
}


def strip(name, pts, width, material, z):
    bm = bmesh.new()
    for a, b in zip(pts, pts[1:]):
        d = Vector((b[0] - a[0], b[1] - a[1]))
        if d.length < 0.01:
            continue
        n = Vector((-d.y, d.x)).normalized() * width / 2
        v = [bm.verts.new((a[0] + s * n.x, a[1] + s * n.y, z)) for s in (1, -1)]
        v += [bm.verts.new((b[0] - s * n.x, b[1] - s * n.y, z)) for s in (1, -1)]
        bm.faces.new((v[0], v[1], v[3], v[2]) if False else (v[0], v[1], v[2], v[3]))
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    o = bpy.data.objects.new(name, me)
    o.data.materials.append(M[material])
    scene.collection.objects.link(o)
    _place(o, "site", local=False)


def prism(name, pts, height, material):
    bm = bmesh.new()
    vs = [bm.verts.new((x, y, 0)) for x, y in pts]
    try:
        f = bm.faces.new(vs)
    except ValueError:
        bm.free()
        return
    bmesh.ops.extrude_face_region(bm, geom=[f])
    top = [v for v in bm.verts if v.co.z == 0 and v not in vs]
    for v in top:
        v.co.z = height
    bm.normal_update()
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    o = bpy.data.objects.new(name, me)
    o.data.materials.append(M[material])
    scene.collection.objects.link(o)
    _place(o, "context", local=False)


def site():
    box("ground", -260, -260, -0.06, 260, 260, -0.01, "ground", "site", local=False)
    data = json.load(open(OSM, encoding="utf-8"))
    lat0, lon0 = 43.24489, 76.93818
    kx = 111320 * math.cos(math.radians(lat0))
    ky = 110540
    labels_done = set()
    road_i = [0]
    # подписи читаются слева направо с общей камеры (с юго-востока)
    cam_right = Vector((1.0, 0.75, 0.0)).normalized()
    for e in data["elements"]:
        t = e.get("tags", {})
        pts = [((p["lon"] - lon0) * kx, (p["lat"] - lat0) * ky) for p in e.get("geometry", [])]
        if len(pts) < 2:
            continue
        if "highway" in t:
            kind = t["highway"]
            w = ROAD_W.get(kind, 3)
            foot = kind in ("footway", "path", "cycleway", "steps", "pedestrian")
            road_i[0] += 1
            strip(f"road_{e['id']}", pts, w, "walk" if foot else "road",
                  (0.01 if foot else 0.03) + (road_i[0] % 9) * 0.004)
            name = NAMES.get(t.get("name", ""))
            if name and name not in labels_done and not foot:
                # подпись — у ближайшей к отелю точки улицы, вдоль неё
                i = min(range(len(pts) - 1), key=lambda j: math.hypot(*pts[j]))
                a, b = pts[i], pts[i + 1]
                d = Vector((b[0] - a[0], b[1] - a[1])).normalized()
                if d.dot(cam_right) < 0:
                    d = -d
                ang = math.atan2(d.y, d.x)
                text(f"label_{len(labels_done)}", name, 5.0, "label", "labels",
                     ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2, 0.12), rot_z=ang)
                labels_done.add(name)
        elif "building" in t and e["id"] != 51267895:
            try:
                levels = float(str(t.get("building:levels", "2")).split(";")[0])
            except ValueError:
                levels = 2
            if pts[0] == pts[-1]:
                pts = pts[:-1]
            prism(f"bld_{e['id']}", pts, max(3.0, levels * 3.2), "context")


floor_one()
lobby()
second_building()
box("slab_2", 0, 0, H1, L, D_UP, Z2, "slab", "floor2")
upper_floor(2, Z2)
upper_floor(3, Z3)
facade_and_roof()
site()

# ───────────────────────────── свет и рендер ──────────────────────
world = bpy.data.worlds.new("world")
world.use_nodes = True
bg = world.node_tree.nodes["Background"]
bg.inputs["Color"].default_value = (0.78, 0.84, 0.93, 1)
bg.inputs["Strength"].default_value = 0.8
scene.world = world
bpy.ops.object.light_add(type="SUN", rotation=(math.radians(52), 0, math.radians(-140)))
sun = bpy.context.active_object
sun.data.energy = 3.8
sun.data.angle = math.radians(3)

scene.render.engine = "CYCLES"
scene.cycles.samples = 24 if FAST else 96
scene.cycles.use_denoising = True
scene.view_settings.view_transform = "AgX"
scene.view_settings.look = "AgX - Medium High Contrast"

bpy.ops.object.camera_add()
cam = bpy.context.active_object
scene.camera = cam
target = bpy.data.objects.new("target", None)
scene.collection.objects.link(target)
con = cam.constraints.new("TRACK_TO")
con.target = target
con.track_axis = "TRACK_NEGATIVE_Z"
con.up_axis = "UP_Y"


def world_of(x, y, z=0.0):
    return root.matrix_world @ Vector((x, y, z))


def shot(name, cam_loc, look, lens, hide=(), res=(1920, 1080)):
    for c_name, c in COLL.items():
        c.hide_render = c_name in hide
    scene.render.resolution_x, scene.render.resolution_y = res
    cam.data.type = "PERSP"
    cam.location = cam_loc
    target.location = look
    cam.data.lens = lens
    scene.render.filepath = os.path.join(OUT, f"{name}.png")
    bpy.ops.render.render(write_still=True)


bpy.context.view_layer.update()
mid = world_of(L / 2, D_UP / 2, 4)
east = world_of(L / 2 - 4, -45, 0)
# Кадры для Higgsfield: одна камера на все четыре вида — тогда переход
# «крыша уходит → этаж» в видео совпадает. Подписи улиц не даём: генератор
# портит кириллицу, их кладёт сайт поверх картинки.
# Точки номеров на кадрах «кадры»: центр пола каждого номера через ту же
# камеру → доли ширины и высоты кадра. По ним сайт ставит кружки на картинки.
if "точки" in ARGS:
    from bpy_extras.object_utils import world_to_camera_view
    cam_l, look = world_of(-6, -30, 36), world_of(L / 2 + 0.5, D_UP / 2 - 3.5, 2)
    cam.location, target.location, cam.data.lens = cam_l, look, 30
    scene.render.resolution_x, scene.render.resolution_y = 1920, 1080
    bpy.context.view_layer.update()
    floor_z = {1: 1.3, 2: Z2 + 1.3, 3: Z3 + 1.3}  # середина высоты стен: так глаз видит центр комнаты
    out = {}
    for n, rooms in ROOMS.items():
        out[n] = []
        for r in rooms:
            c = world_of((r["x0"] + r["x1"]) / 2, (r["y0"] + r["y1"]) / 2, floor_z[n])
            v = world_to_camera_view(scene, cam, c)
            out[n].append({"id": r["name"], "cat": r["cat"], "x": round(v.x * 100, 2),
                           "y": round((1 - v.y) * 100, 2),
                           "area": round((r["x1"] - r["x0"]) * (r["y1"] - r["y0"]), 1)})
    out["zones"] = []
    for zn in ZONES:
        v = world_to_camera_view(scene, cam, world_of(zn["x"], zn["y"], 1.0))
        out["zones"].append({"id": zn["id"], "x": round(v.x * 100, 2), "y": round((1 - v.y) * 100, 2)})
    json.dump(out, open(os.path.join(OUT, "room_points.json"), "w"), ensure_ascii=False, indent=1)
    print("DONE")
    sys.stdout.flush()
    os._exit(0)

if "кадры" in ARGS:
    scene.cycles.samples = 64
    cam_l, look = world_of(-6, -30, 36), world_of(L / 2 + 0.5, D_UP / 2 - 3.5, 2)
    if "этаж1" not in ARGS:
        shot("s0_exterior", cam_l, look, 30, hide=("labels",))
        shot("s1_floor3", cam_l, look, 30, hide=("roof", "facade", "labels"))
        shot("s2_floor2", cam_l, look, 30, hide=("floor3", "roof", "facade", "labels"))
    shot("s3_floor1", cam_l, look, 30, hide=("floor2", "floor3", "roof", "roof_lobby", "facade", "labels"))
    print("DONE")
    sys.stdout.flush()
    os._exit(0)

# 0. Квартал с подписями улиц
shot("00_map", Vector((130, -150, 165)), Vector((8, -6, 0)), 32)
# 1. Крупный вид сверху: восточный фасад с лобби и входом
shot("01_hero", world_of(-22, -58, 48), world_of(L / 2 - 2, D_UP / 2 - 5, 3), 34)
# 2. Ближе: вход и вывеска
shot("02_entrance", world_of(-14, -32, 16), world_of(6, 0, 5), 32)
above = ("floor2", "floor3", "roof", "roof_lobby", "facade")
# 3–5. Этажи без крыши
shot("03_floor1", world_of(-12, -30, 34), world_of(L / 2, D_UP / 2 - 3, 0), 30,
     hide=("floor2", "floor3", "roof", "roof_lobby", "facade", "labels"))
shot("04_floor2", world_of(-12, -26, 36), world_of(L / 2, D_UP / 2, Z2), 30,
     hide=("floor3", "roof", "facade", "labels"))
shot("05_floor3", world_of(-12, -26, 39), world_of(L / 2, D_UP / 2, Z3), 30,
     hide=("roof", "facade", "labels"))

# 6–8. Планы сверху для интерактивной схемы на сайте: ортокамера в осях здания
root.rotation_euler = (0, 0, 0)
root.location = (0, 0, 0)
bpy.context.view_layer.update()
cam.constraints.remove(con)
cam.data.type = "ORTHO"
SCALE = 27.0
W_PX, H_PX = 2000, int(2000 * 24.0 / SCALE)
cam.data.ortho_scale = SCALE
CX, CY = L / 2, (D_UP + Y1 - ANNEX_D) / 2
cam.location = (CX, CY, 40)
cam.rotation_euler = (0, 0, 0)
plans = {}
for n, hide in ((1, ("floor2", "floor3", "roof", "roof_lobby", "facade", "context", "labels", "site")),
                (2, ("floor3", "roof", "facade", "context", "labels", "site")),
                (3, ("roof", "facade", "context", "labels", "site"))):
    for c_name, c in COLL.items():
        c.hide_render = c_name in hide
    scene.render.resolution_x, scene.render.resolution_y = W_PX, H_PX
    scene.render.film_transparent = True
    scene.render.filepath = os.path.join(OUT, f"plan_floor{n}.png")
    bpy.ops.render.render(write_still=True)

    def to_px(x, y):
        k = W_PX / SCALE
        return round(W_PX / 2 + (x - CX) * k, 1), round(H_PX / 2 - (y - CY) * k, 1)

    plans[n] = []
    for r in ROOMS[n]:
        (ax, ay), (bx, by) = to_px(r["x0"], r["y1"]), to_px(r["x1"], r["y0"])
        plans[n].append({"id": r["name"], "cat": r["cat"], "x": ax, "y": ay, "w": round(bx - ax, 1), "h": round(by - ay, 1)})
json.dump({"width": W_PX, "height": H_PX, "floors": plans}, open(os.path.join(OUT, "plan_rooms.json"), "w"),
          ensure_ascii=False, indent=1)
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(HERE, "airis_v2.blend"))
print("DONE")
