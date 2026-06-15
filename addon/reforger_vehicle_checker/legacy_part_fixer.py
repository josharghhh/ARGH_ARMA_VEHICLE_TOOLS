"""Reforger Part Fixer — Blender N-panel addon.

Workflow for turning a separated-but-unnamed vehicle model into named,
rig-ready part groups for Arma Reforger/Enfusion:

  1. AUTO-SETUP   one click: rescale (wheelbase-calibrated), apply transforms,
                  assign every piece into reviewable part COLLECTIONS.
  2. ORGANIZE     rename pieces to their part (door_FL.123 ...) so the
                  outliner groups/searches cleanly; color-tag collections.
  3. REVIEW       quick-select a part, ghost the rest, TEST-OPEN a door on its
                  hinge — wrongly assigned pieces swing out and float in air;
                  select them and one-click send them back to interior/exterior.
  4. FINALIZE     joins each collection into its named object, sets hinge /
                  wheel-center / column origins, parents door windows to doors.

Panel: View3D sidebar (N) -> "Part Fixer" tab.
"""

bl_info = {
    "name": "Reforger Part Fixer",
    "author": "ARGH Vehicle Tools contributors",
    "version": (0, 8, 6),
    "blender": (4, 0, 0),
    "location": "View3D > Sidebar > Part Fixer",
    "description": "Assign, review (test-open doors) and finalize vehicle parts for Enfusion rigging",
    "category": "Object",
}

import bpy
import bmesh
import time
from collections import Counter
from mathutils import Vector, Matrix

# ----------------------------------------------------------------------------
# configuration
# ----------------------------------------------------------------------------

TARGET_WHEELBASE = 3.0
TEXDIR = ""

ROOT_COLL = "PARTS"
ASSET_NAME = "Vehicle"
EXPORT_ROOT = ""

PART_ORDER = [
    "door_FL", "door_FR", "door_RL", "door_RR", "door_trunk",
    "window_FL", "window_FR", "window_RL", "window_RR", "window_trunk",
    "wheel_FL", "wheel_FR", "wheel_RL", "wheel_RR",
    "brake_FL", "brake_FR", "brake_RL", "brake_RR",
    "Steering_Wheel", "Pedal_Brake", "Pedal_Accelerator",
    "lights_front", "lights_rear", "lights_emergency",
    "windows_body", "interior", "exterior",
]

DOORS = ("door_FL", "door_FR", "door_RL", "door_RR", "door_trunk")
DOOR_WINDOW = {"door_FL": "window_FL", "door_FR": "window_FR",
               "door_RL": "window_RL", "door_RR": "window_RR",
               "door_trunk": "window_trunk"}
DOOR_BONE = {"door_FL": "v_door_l01", "door_FR": "v_door_r01",
             "door_RL": "v_door_l02", "door_RR": "v_door_r02",
             "door_trunk": "v_trunk"}

COLL_COLORS = {
    "door_FL": 'COLOR_01', "door_FR": 'COLOR_01', "door_RL": 'COLOR_01', "door_RR": 'COLOR_01',
    "window_FL": 'COLOR_05', "window_FR": 'COLOR_05', "window_RL": 'COLOR_05', "window_RR": 'COLOR_05',
    "windows_body": 'COLOR_05',
    "wheel_FL": 'COLOR_02', "wheel_FR": 'COLOR_02', "wheel_RL": 'COLOR_02', "wheel_RR": 'COLOR_02',
    "brake_FL": 'COLOR_03', "brake_FR": 'COLOR_03', "brake_RL": 'COLOR_03', "brake_RR": 'COLOR_03',
    "Steering_Wheel": 'COLOR_06', "Pedal_Brake": 'COLOR_06', "Pedal_Accelerator": 'COLOR_06',
    "lights_front": 'COLOR_04', "lights_rear": 'COLOR_04', "lights_emergency": 'COLOR_04',
    "interior": 'COLOR_07', "exterior": 'COLOR_08',
}

PFX = "Police_Interceptor_SUV"

# session-verified seeds (object name suffixes of the original asset)
SEED = {
    "Steering_Wheel": ["824", "825"] + [str(i) for i in range(826, 845)],
    "Pedal_Brake": ["2287", "1988"],
    "Pedal_Accelerator": ["2289"],
    "wheel_FR": ["2697", "2701", "2702", "2703", "2704", "2705", "2706", "2707",
                 "2708", "2709", "2710", "2711", "2712"],
    "wheel_FL": ["2735", "2736", "2737", "2738", "2739", "2740", "2741", "2742",
                 "2743", "2744", "2745", "2746", "2747"],
    "wheel_RR": ["485", "480", "481", "486", "487", "488", "489", "490", "491",
                 "492", "493", "494", "495"],
    "wheel_RL": ["501", "496", "497", "502", "503", "504", "505", "506", "507",
                 "508", "509", "510", "511"],
    "brake_FL": ["2678", "2679"],
    "brake_FR": ["2730", "2731"],
    "brake_RR": ["512", "513"],
    "brake_RL": ["514", "515"],
}
FUSED_SKINS = ["1637", "1648"]
SKIN_SEAM_Y = -0.222
GLASS_SEED = {"window_FL": ["745"], "window_FR": ["1900"],
              "window_RL": ["693"], "window_RR": ["1699"],
              "windows_body": ["1689", "1880", "1657", "1659"]}


# ----------------------------------------------------------------------------
# helpers
# ----------------------------------------------------------------------------

def wbbox(o):
    pts = [o.matrix_world @ Vector(c) for c in o.bound_box]
    mn = Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
    mx = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
    return mn, mx


def all_meshes():
    return [o for o in bpy.data.objects if o.type == 'MESH']


def get_coll(name):
    c = bpy.data.collections.get(name)
    if c is None:
        c = bpy.data.collections.new(name)
    root = bpy.data.collections.get(ROOT_COLL)
    if root is None:
        root = bpy.data.collections.new(ROOT_COLL)
        bpy.context.scene.collection.children.link(root)
    if c.name not in [cc.name for cc in root.children] and c.name != ROOT_COLL:
        try:
            root.children.link(c)
        except RuntimeError:
            pass
    return c


def move_to_coll(o, coll_name):
    c = get_coll(coll_name)
    for uc in list(o.users_collection):
        uc.objects.unlink(o)
    c.objects.link(o)


def part_of(o):
    for uc in o.users_collection:
        if uc.name in PART_ORDER:
            return uc.name
    return None


def _solid_display(o):
    """Colliders stay wireframe no matter what review loops do."""
    return 'WIRE' if o.name.startswith(COLLIDER_PFX) else 'TEXTURED'


def apply_review_state(context, o):
    """Display/lock an object according to the active review session."""
    reviewing = context.scene.get("rpf_reviewing", "")
    if not reviewing:
        o.display_type = _solid_display(o)
        o.hide_select = False
        o.hide_set(False)
        return
    if o.name in {m.name for m in part_objects(reviewing)}:
        o.display_type = _solid_display(o)
        o.hide_select = False
        o.hide_set(False)
    else:
        o.hide_select = True
        if context.scene.rpf_ghost_hide:
            o.hide_set(True)
        else:
            o.hide_set(False)
            o.display_type = 'WIRE'


def part_objects(part):
    """Resolve a part to objects: its collection pieces (pre-finalize) OR the
    single joined object with that exact name (post-finalize), wherever the
    user has moved it in the outliner. Doors include their window object."""
    out = []
    c = bpy.data.collections.get(part)
    if c:
        out += [o for o in c.objects if o.type == 'MESH']
    o = bpy.data.objects.get(part)
    if o and o.type == 'MESH' and o not in out:
        out.append(o)
    if part.startswith("window_"):     # post-finalize door panes: door_XX_window
        w = bpy.data.objects.get(f"door_{part[7:]}_window")
        if w and w.type == 'MESH' and w not in out:
            out.append(w)
    if part in DOOR_WINDOW:
        w = bpy.data.objects.get(part + "_window")
        if w and w not in out:
            out.append(w)
        wc = bpy.data.collections.get(DOOR_WINDOW[part])
        if wc:
            out += [x for x in wc.objects if x.type == 'MESH' and x not in out]
    return out


def containment(mn, mx, vmn, vmx):
    ox = max(0, min(mx.x, vmx.x) - max(mn.x, vmn.x))
    oy = max(0, min(mx.y, vmx.y) - max(mn.y, vmn.y))
    oz = max(0, min(mx.z, vmx.z) - max(mn.z, vmn.z))
    vol = max(mx.x - mn.x, 1e-6) * max(mx.y - mn.y, 1e-6) * max(mx.z - mn.z, 1e-6)
    return ox * oy * oz / vol


def dominant_material(o):
    mats = [ms.material.name if ms.material else "" for ms in o.material_slots]
    if not mats:
        return ""
    cnt = Counter()
    for p in o.data.polygons:
        cnt[mats[min(p.material_index, len(mats) - 1)]] += 1
    return cnt.most_common(1)[0][0] if cnt else ""


def checkpoint(tag):
    if bpy.data.filepath:
        path = bpy.data.filepath.replace(".blend", f"_{tag}_{time.strftime('%H%M%S')}.blend")
        bpy.ops.wm.save_as_mainfile(filepath=path, copy=True)
        return path
    return None


def join_objects(objs, new_name):
    objs = [o for o in objs if o and o.type == 'MESH']
    if not objs:
        return None
    bpy.ops.object.select_all(action='DESELECT')
    for o in objs:
        o.hide_set(False)
        o.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]
    if len(objs) > 1:
        bpy.ops.object.join()
    res = bpy.context.view_layer.objects.active
    res.name = new_name
    return res


def set_origin(o, point):
    bpy.ops.object.select_all(action='DESELECT')
    o.hide_set(False)
    o.select_set(True)
    bpy.context.view_layer.objects.active = o
    bpy.context.scene.cursor.location = Vector(point)
    bpy.ops.object.origin_set(type='ORIGIN_CURSOR')


def door_hinge(door_name):
    """Hinge point for a door. Side doors: front edge (max-Y band), vertical axis.
    Trunk/tailgate: top edge (max-Z band), horizontal X axis."""
    objs = part_objects(door_name)
    pts = []
    for o in objs:
        if o.type != 'MESH':
            continue
        mw = o.matrix_world
        pts += [mw @ v.co for v in o.data.vertices]
    if not pts:
        return None
    if door_name == "door_trunk":
        zmax = max(p.z for p in pts)
        edge = [p for p in pts if p.z > zmax - 0.06]
        hy = sorted(p.y for p in edge)[len(edge) // 2]
        return Vector((0.0, hy, zmax - 0.02))
    # adaptive X band: drop the outboard 15% of verts (mirrors etc.) instead of
    # a fixed |x|<1.0 cutoff, which empties out on wide vehicles (Bearcat)
    xs = sorted(abs(p.x) for p in pts)
    xlim = xs[min(int(len(xs) * 0.85), len(xs) - 1)] + 0.02
    band = [p for p in pts if abs(p.x) <= xlim] or pts
    ymax = max(p.y for p in band)
    edge = [p for p in band if p.y > ymax - 0.06]
    if not edge:
        return None
    hx = sorted(p.x for p in edge)[len(edge) // 2]
    hz = (min(p.z for p in edge) + max(p.z for p in edge)) / 2
    return Vector((hx, ymax - 0.02, hz))


def frame_view(context):
    for area in context.screen.areas:
        if area.type == 'VIEW_3D':
            region = next(r for r in area.regions if r.type == 'WINDOW')
            with context.temp_override(area=area, region=region):
                bpy.ops.view3d.view_selected()
            return


# ----------------------------------------------------------------------------
# 0) INITIAL DISCOVERY — first contact with ANY vehicle model
# ----------------------------------------------------------------------------

class RPF_OT_discover(bpy.types.Operator):
    bl_idname = "rpf.discover"
    bl_label = "0. Initial Discovery"
    bl_description = ("First step on any vehicle: split single-mesh imports into "
                      "loose pieces, then measure and report everything needed to "
                      "drive Auto-Setup (units, wheelbase, tires, materials)")
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        meshes = all_meshes()
        # single/few-mesh import -> separate into loose pieces first
        if 0 < len(meshes) < 20:
            bpy.ops.object.select_all(action='DESELECT')
            for o in meshes:
                o.hide_set(False)
                o.select_set(True)
            context.view_layer.objects.active = meshes[0]
            bpy.ops.object.mode_set(mode='EDIT')
            bpy.ops.mesh.select_all(action='SELECT')
            bpy.ops.mesh.separate(type='LOOSE')
            bpy.ops.object.mode_set(mode='OBJECT')
            meshes = all_meshes()

        mn = Vector((1e9,) * 3); mx = Vector((-1e9,) * 3)
        polys = 0
        for o in meshes:
            a, b = wbbox(o)
            mn.x = min(mn.x, a.x); mn.y = min(mn.y, a.y); mn.z = min(mn.z, a.z)
            mx.x = max(mx.x, b.x); mx.y = max(mx.y, b.y); mx.z = max(mx.z, b.z)
            polys += len(o.data.polygons)
        size = mx - mn
        unit_guess = "INCHES (scale x0.0254 needed)" if size.length > 50 else \
                     "METERS (looks plausible)" if 3 < max(size) < 8 else "UNKNOWN — check manually"

        # tire candidates: round in YZ regardless of current unit scale
        tires = []
        for o in meshes:
            a, b = wbbox(o)
            d = b - a; c = (a + b) / 2
            if d.y > 1e-6 and d.z > 1e-6 and abs(d.y - d.z) / max(d.y, d.z) < 0.06 \
               and d.x < 0.6 * d.y and c.z < mn.z + 0.45 * size.z and d.y > 0.08 * size.y:
                tires.append((o.name, [round(v, 3) for v in c], round(d.y, 3)))
        wb = 0.0
        if len(tires) >= 4:
            ys = sorted(t[1][1] for t in tires)
            wb = ys[-1] - ys[0]

        mats = {}
        for o in meshes:
            for ms in o.material_slots:
                if ms.material:
                    mats[ms.material.name] = mats.get(ms.material.name, 0) + 1

        print("=" * 60)
        print("RPF DISCOVERY REPORT")
        print("=" * 60)
        print(f"pieces: {len(meshes)}   polys: {polys}")
        print(f"bbox size: {[round(v, 3) for v in size]}   units: {unit_guess}")
        print(f"long axis: {'Y (ok, +Y should be NOSE — verify!)' if size.y > size.x else 'X (vehicle needs 90deg rotation!)'}")
        print(f"tire candidates: {len(tires)}")
        for t in tires[:8]:
            print("   ", t)
        if wb:
            print(f"wheelbase (current units): {wb:.4f} -> set TARGET_WHEELBASE for this vehicle")
        print(f"materials: {mats}")
        print("next: 1. Auto-Setup  ->  review parts  ->  finalize  ->  export")
        self.report({'INFO'}, f"discovery: {len(meshes)} pieces, {len(tires)} tire candidates — see console")
        return {'FINISHED'}


# ----------------------------------------------------------------------------
# 0b) FIREGEO BUILDER — stock SampleCar collider conventions
# ----------------------------------------------------------------------------

def _decimate_copy(src, name, ratio):
    dec = src.modifiers.new("RPF_DEC", 'DECIMATE')
    dec.ratio = ratio
    dg = bpy.context.evaluated_depsgraph_get()
    me = bpy.data.meshes.new_from_object(src.evaluated_get(dg))
    src.modifiers.remove(src.modifiers["RPF_DEC"])
    me.name = name
    o = bpy.data.objects.new(name, me)
    o.display_type = 'WIRE'
    _place_ebt_collider(o)
    o.matrix_world = src.matrix_world.copy()
    for vg in list(o.vertex_groups):
        o.vertex_groups.remove(vg)
    for m in list(o.modifiers):
        o.modifiers.remove(m)
    return o


def _decimate_part(part, name, ratio):
    """FireGeo from a WHOLE part: gather its meshes (collection pieces, a single joined
    object, or name-prefixed pieces like 'exterior.metal'), bare-join a copy, decimate.
    Robust to multi-object parts so FireGeo works on imported/renamed vehicles."""
    pieces = [o for o in part_objects(part) if o.type == 'MESH']
    if not pieces:
        pieces = [o for o in bpy.data.objects
                  if o.type == 'MESH' and not o.name.startswith(COLLIDER_PFX)
                  and (o.name == part or o.name.startswith(part + "."))]
    if not pieces:
        return None
    copies = []
    for p in pieces:
        c = bpy.data.objects.new(f"_fgtmp_{p.name}", p.data.copy())
        bpy.context.scene.collection.objects.link(c)
        c.matrix_world = p.matrix_world.copy()
        for vg in list(c.vertex_groups):
            c.vertex_groups.remove(vg)
        for m in list(c.modifiers):
            c.modifiers.remove(m)
        copies.append(c)
    bpy.ops.object.select_all(action='DESELECT')
    for c in copies:
        c.select_set(True)
    bpy.context.view_layer.objects.active = copies[0]
    if len(copies) > 1:
        bpy.ops.object.join()
    joined = bpy.context.view_layer.objects.active
    out = _decimate_copy(joined, name, ratio)
    bpy.data.objects.remove(joined, do_unlink=True)
    return out


def _collider_usage(name):
    """Match the stock Enfusion layer preset implied by a collider name."""
    if name.startswith("UCL_MT_"):
        return "MineTrigger"
    if name.startswith("UCX_MainCol_"):
        return "Vehicle"
    if name.startswith("UTM_Glass"):
        return "GlassFire"
    if name.startswith(("UCX_FG_", "UTM_")):
        return "FireGeo"
    return "Vehicle"


def _place_ebt_collider(obj, usage=None):
    """Put a collider in the collection structure expected by Enfusion Tools."""
    usage = usage or _collider_usage(obj.name)
    root = bpy.data.collections.get("Colliders")
    if root is None:
        root = bpy.data.collections.new("Colliders")
        bpy.context.scene.collection.children.link(root)
    root["is_ebt_collection"] = True

    layer = bpy.data.collections.get(usage)
    if layer is None:
        layer = bpy.data.collections.new(usage)
    if layer.name not in {child.name for child in root.children}:
        try:
            root.children.link(layer)
        except RuntimeError:
            pass
    layer["is_ebt_collection"] = True

    for collection in list(obj.users_collection):
        collection.objects.unlink(obj)
    layer.objects.link(obj)
    obj["usage"] = usage
    colors = {
        "Vehicle": (1.0, 0.22, 0.03, 0.32),
        "FireGeo": (1.0, 0.03, 0.03, 0.50),
        "GlassFire": (0.0, 0.65, 1.0, 0.45),
        "MineTrigger": (0.1, 1.0, 0.15, 0.45),
    }
    obj.color = colors.get(usage, (1.0, 0.5, 0.0, 0.4))
    visual_review = bpy.context.scene.get("rpf_collider_visual_review", False)
    is_main_hull = obj.name.startswith(("UCX_MainCol_", "UBX_MainCol_"))
    obj.display_type = 'SOLID' if visual_review and is_main_hull else 'WIRE'
    obj.show_wire = visual_review
    obj.show_all_edges = visual_review
    obj.show_in_front = visual_review
    obj.hide_render = True
    return obj


def _normalize_ebt_colliders():
    """Repair preset properties/collections on current and legacy colliders."""
    prefixes = ("UBX_", "UCX_", "USP_", "UCS_", "UCL_", "UTM_")
    normalized = []
    for obj in bpy.data.objects:
        if obj.type == 'MESH' and obj.name.startswith(prefixes):
            _place_ebt_collider(obj)
            normalized.append(obj.name)
    return normalized


def _remove_glass_faces(obj):
    """Keep door FireGeo metal-only; UTM_Glass owns window collision."""
    import bmesh
    glass_slots = {
        index for index, material in enumerate(obj.data.materials)
        if material and "glass" in material.name.lower()
    }
    if not glass_slots:
        return 0
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    faces = [face for face in bm.faces if face.material_index in glass_slots]
    bmesh.ops.delete(bm, geom=faces, context='FACES')
    bm.to_mesh(obj.data)
    bm.free()
    for index in sorted(glass_slots, reverse=True):
        obj.data.materials.pop(index=index)
    obj.data.update()
    return len(faces)


def _box(name, mn, mx):
    import bmesh as _bm
    me = bpy.data.meshes.new(name)
    bm = _bm.new()
    _bm.ops.create_cube(bm, size=1.0)
    c = (Vector(mn) + Vector(mx)) / 2
    d = Vector(mx) - Vector(mn)
    for v in bm.verts:
        v.co = Vector((v.co.x * d.x, v.co.y * d.y, v.co.z * d.z)) + c
    bm.to_mesh(me)
    bm.free()
    o = bpy.data.objects.new(name, me)
    return _place_ebt_collider(o)


def _tapered_prism(name, rear_y, front_y, rear_section, front_section):
    """Create a guaranteed-convex vehicle blockout from eight profile corners.

    A section is (bottom_half_width, top_half_width, bottom_z, top_z).
    Independent front/rear sections capture armored-body taper and slope
    without turning the physics hull into render geometry.
    """
    rbw, rtw, rbz, rtz = rear_section
    fbw, ftw, fbz, ftz = front_section
    verts = [
        (-rbw, rear_y, rbz), (rbw, rear_y, rbz),
        (-rtw, rear_y, rtz), (rtw, rear_y, rtz),
        (-fbw, front_y, fbz), (fbw, front_y, fbz),
        (-ftw, front_y, ftz), (ftw, front_y, ftz),
    ]
    # Differently tapered front/rear sections can make hand-authored quad
    # sides non-planar. Re-hull the corners so every exported face is planar
    # and the result is mathematically convex.
    me = _convex_mesh_from_points(name, [Vector(vertex) for vertex in verts])
    if me is None:
        raise RuntimeError(f"could not build convex profile collider {name}")
    return _place_ebt_collider(bpy.data.objects.new(name, me))


def _next_main_col_index():
    indices = []
    for obj in bpy.data.objects:
        if not obj.name.startswith("UCX_MainCol_"):
            continue
        token = obj.name[len("UCX_MainCol_"):].split("_", 1)[0]
        if token.isdigit():
            indices.append(int(token))
    return max(indices, default=0) + 1


def _safe_name_token(name):
    token = "".join(c if c.isalnum() else "_" for c in name).strip("_")
    while "__" in token:
        token = token.replace("__", "_")
    return token[:48] or "Part"


def _evaluated_world_vertices(obj):
    depsgraph = bpy.context.evaluated_depsgraph_get()
    evaluated = obj.evaluated_get(depsgraph)
    mesh = evaluated.to_mesh()
    try:
        return [evaluated.matrix_world @ vertex.co for vertex in mesh.vertices]
    finally:
        evaluated.to_mesh_clear()


def _sample_hull_points(points, resolution):
    """Voxel-sample points while preserving axis extrema."""
    if len(points) <= 8:
        return points
    mn = Vector((min(p.x for p in points), min(p.y for p in points), min(p.z for p in points)))
    mx = Vector((max(p.x for p in points), max(p.y for p in points), max(p.z for p in points)))
    span = mx - mn
    cells = {}
    for point in points:
        key = tuple(
            min(resolution - 1, int((point[i] - mn[i]) / max(span[i], 1e-6) * resolution))
            for i in range(3)
        )
        cells.setdefault(key, [Vector(), 0])
        cells[key][0] += point
        cells[key][1] += 1
    sampled = [total / count for total, count in cells.values()]
    for axis in range(3):
        sampled.append(min(points, key=lambda p: p[axis]))
        sampled.append(max(points, key=lambda p: p[axis]))
    return sampled


def _reject_outliers(points):
    """Drop a few stray vertices far from the part so the convex hull doesn't spike.
    MAD-based and conservative: clean parts are untouched, and a genuinely large/spread
    part (where dropping would exceed 12% of verts) is kept whole."""
    if len(points) < 8:
        return points
    points = [p if isinstance(p, Vector) else Vector(p) for p in points]
    centre = sum(points, Vector()) / len(points)
    dists = [(p - centre).length for p in points]
    ordered = sorted(dists)
    med = ordered[len(ordered) // 2]
    mad = sorted(abs(x - med) for x in ordered)[len(ordered) // 2] or 1e-6
    limit = med + 6.0 * mad
    kept = [p for p, d in zip(points, dists) if d <= limit]
    if len(kept) < len(points) * 0.88 or len(kept) < 4:
        return points
    return kept


def _convex_mesh_from_points(name, points):
    mesh = bpy.data.meshes.new(name)
    bm = bmesh.new()
    try:
        for point in points:
            bm.verts.new(point)
        bm.verts.ensure_lookup_table()
        bmesh.ops.remove_doubles(bm, verts=list(bm.verts), dist=0.0005)
        if len(bm.verts) < 4:
            return None
        result = bmesh.ops.convex_hull(bm, input=list(bm.verts), use_existing_faces=False)
        discarded = {
            elem for elem in result.get("geom_interior", []) + result.get("geom_unused", [])
            if isinstance(elem, bmesh.types.BMVert) and elem.is_valid
        }
        if discarded:
            bmesh.ops.delete(bm, geom=list(discarded), context='VERTS')
        if not bm.faces:
            return None
        bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
        bmesh.ops.triangulate(bm, faces=list(bm.faces))  # planar tris -> reliable convex test
        bm.to_mesh(mesh)
        mesh.update()
        return mesh
    except (RuntimeError, ValueError):
        return None
    finally:
        bm.free()
        if not mesh.polygons:
            bpy.data.meshes.remove(mesh)


def _part_convex_hull(source, name, max_faces):
    points = _reject_outliers(_evaluated_world_vertices(source))
    if len(points) < 4:
        return None
    # Reduce input points, then rebuild the hull. Never decimate the final
    # hull because that can make an Enfusion UCX collider non-convex.
    best = None
    for resolution in (12, 10, 8, 6, 5, 4, 3, 2, 1):
        mesh = _convex_mesh_from_points(name, _sample_hull_points(points, resolution))
        if mesh is None:
            continue
        if best:
            bpy.data.meshes.remove(best)
        best = mesh
        if len(mesh.polygons) <= max_faces:
            break
    if best is None:
        return None
    if len(best.polygons) > max_faces:
        bpy.data.meshes.remove(best)
        return None
    obj = bpy.data.objects.new(name, best)
    obj["rpf_ucx_source"] = source.name
    obj["rpf_ucx_face_cap"] = max_faces
    armature_modifiers = [mod for mod in source.modifiers if mod.type == 'ARMATURE' and mod.object]
    rigid_groups = [group.name for group in source.vertex_groups if group.name.startswith(("v_", "w_"))]
    if len(armature_modifiers) == 1 and len(rigid_groups) == 1:
        group = obj.vertex_groups.new(name=rigid_groups[0])
        group.add(range(len(obj.data.vertices)), 1.0, 'REPLACE')
        modifier = obj.modifiers.new("Armature", 'ARMATURE')
        modifier.object = armature_modifiers[0].object
        modifier.use_vertex_groups = True
        modifier.use_bone_envelopes = False
        obj["rpf_ucx_bone"] = rigid_groups[0]
    return _place_ebt_collider(obj, "Vehicle")


def _mesh_is_convex(obj, tolerance=0.0005):
    """Return False when any vertex lies outside one of the mesh face planes."""
    vertices = [vertex.co for vertex in obj.data.vertices]
    if len(vertices) < 4 or not obj.data.polygons:
        return False
    center = sum(vertices, Vector()) / len(vertices)
    for polygon in obj.data.polygons:
        normal = polygon.normal.normalized()
        point = vertices[polygon.vertices[0]]
        if (center - point).dot(normal) > 0:
            normal.negate()
        if any((vertex - point).dot(normal) > tolerance for vertex in vertices):
            return False
    return True


def _cyl_x(name, center, radius, depth, segs=16):
    """Cylinder along the X axis (wheel axis) at a world center."""
    import bmesh as _bm
    me = bpy.data.meshes.new(name)
    bm = _bm.new()
    _bm.ops.create_cone(bm, cap_ends=True, segments=segs,
                        radius1=radius, radius2=radius, depth=depth)
    for v in bm.verts:                       # Z-aligned -> X-aligned
        v.co = Vector((v.co.z, v.co.y, -v.co.x)) + Vector(center)
    bm.to_mesh(me)
    bm.free()
    o = bpy.data.objects.new(name, me)
    return _place_ebt_collider(o)


class RPF_OT_build_colliders(bpy.types.Operator):
    bl_idname = "rpf.build_colliders"
    bl_label = "Build Perceptive UCX Colliders"
    bl_description = ("One click: stock-convention physics colliders measured off the "
                      "rig — a chain of individually convex low-LOD profile blocks for "
                      "chassis, armored rear body, windshield, hood and roof turret "
                      "(bottoms lifted, never "
                      "ground-grazing), UCL_MT_wheel_* mine-trigger cylinders at the "
                      "wheel bones, UCX_FG_Engine/Battery/FuelTank/Gearbox hitzone "
                      "boxes. Enfusion layer presets are assigned through usage.")
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        meshes = [o for o in all_meshes() if not o.name.startswith(COLLIDER_PFX)]
        if not meshes:
            self.report({'ERROR'}, "no meshes")
            return {'CANCELLED'}
        for o in list(bpy.data.objects):
            if o.name.startswith(("UCX_MainCol", "UCL_MT_wheel", "UCX_FG_")):
                bpy.data.objects.remove(o)

        mn = Vector((1e9,) * 3); mx = Vector((-1e9,) * 3)
        for o in meshes:
            a, b = wbbox(o)
            mn.x = min(mn.x, a.x); mn.y = min(mn.y, a.y); mn.z = min(mn.z, a.z)
            mx.x = max(mx.x, b.x); mx.y = max(mx.y, b.y); mx.z = max(mx.z, b.z)
        H = mx.z
        r = context.scene.rpf_wheel_radius
        arm = _get_armature()

        def bone_w(n):
            if arm and n in arm.data.bones:
                return arm.matrix_world @ arm.data.bones[n].head_local
            return None

        wheels = {wn: (bone_w(WHEEL_BONES[wn][0]) or _obj_origin(wn))
                  for wn in WHEEL_BONES}
        if all(p is not None for p in wheels.values()):
            wz = sum(p.z for p in wheels.values()) / 4
            y_f = (wheels["wheel_FL"].y + wheels["wheel_FR"].y) / 2
            y_r = (wheels["wheel_RL"].y + wheels["wheel_RR"].y) / 2
        else:
            wz, y_f, y_r = r, mx.y - 1.2, mn.y + 1.4
        # body half-width from door bones (mirrors inflate the bbox)
        door_x = [abs(bone_w(b).x) for b in ("v_door_l01", "v_door_r01")
                  if bone_w(b) is not None]
        halfw = max(door_x) if door_x else (mx.x - mn.x) / 2 - 0.30
        z_floor = max(0.30, wz * 0.80)        # NEVER ground-grazing (bounce bug)

        # Keep collision just inside the visual shell. A single collider cannot
        # follow this concave side outline, so use a chain of convex prisms that
        # meet at the hood, windshield, roof, rear wall, and turret breakpoints.
        rear_tip = max(mn.y + 0.20, y_r - 1.45)
        front_tip = min(mx.y - 0.20, y_f + 1.15)
        cabin_split = (y_f + y_r) * 0.5
        windshield_y = min(front_tip - 0.55, y_f - 0.25)
        hood_y = windshield_y - 0.10
        roof_h = H * 0.93
        lower_top = max(wz + 0.42, H * 0.32)
        cabin_bottom = max(z_floor + 0.34, H * 0.27)
        turret_front = min(windshield_y - 0.22, cabin_split + 0.95)
        turret_rear = max(rear_tip + 0.65, turret_front - 1.20)

        made = []
        made.append(_tapered_prism(
            "UCX_MainCol_01_LowerChassis",
            rear_tip, front_tip,
            (halfw * 0.78, halfw * 0.82, z_floor, lower_top),
            (halfw * 0.72, halfw * 0.68, z_floor + 0.05, lower_top - 0.08),
        ).name)
        made.append(_tapered_prism(
            "UCX_MainCol_02_RearCabin",
            rear_tip + 0.10, cabin_split + 0.12,
            (halfw * 0.82, halfw * 0.88, cabin_bottom, roof_h - 0.04),
            (halfw * 0.90, halfw * 0.84, cabin_bottom, roof_h),
        ).name)
        made.append(_tapered_prism(
            "UCX_MainCol_03_FrontCabin",
            cabin_split - 0.10, windshield_y,
            (halfw * 0.90, halfw * 0.84, cabin_bottom, roof_h),
            (halfw * 0.82, halfw * 0.70, cabin_bottom + 0.02, H * 0.70),
        ).name)
        made.append(_tapered_prism(
            "UCX_MainCol_04_Hood",
            hood_y, front_tip,
            (halfw * 0.74, halfw * 0.68, lower_top - 0.10, H * 0.52),
            (halfw * 0.64, halfw * 0.58, lower_top - 0.05, H * 0.43),
        ).name)
        made.append(_tapered_prism(
            "UCX_MainCol_05_Turret",
            turret_rear, turret_front,
            (halfw * 0.54, halfw * 0.58, roof_h, H - 0.04),
            (halfw * 0.54, halfw * 0.58, roof_h, H - 0.04),
        ).name)

        mt = {"wheel_FL": "UCL_MT_wheel_L01", "wheel_RL": "UCL_MT_wheel_L02",
              "wheel_FR": "UCL_MT_wheel_R01", "wheel_RR": "UCL_MT_wheel_R02"}
        for wn, cn in mt.items():
            p = wheels.get(wn)
            if p is not None:
                made.append(_cyl_x(cn, p, r * 0.98, 0.28).name)

        made.append(_box("UCX_FG_Engine",
                         (-0.42, y_f + 0.30, wz - 0.05),
                         (0.42, mx.y - 0.40, wz + 0.55)).name)
        made.append(_box("UCX_FG_Battery",
                         (-halfw * 0.75, y_f + 0.35, wz + 0.25),
                         (-halfw * 0.75 + 0.32, y_f + 0.70, wz + 0.50)).name)
        made.append(_box("UCX_FG_FuelTank",
                         (-0.35, y_r + 0.45, z_floor),
                         (0.35, y_r + 1.10, z_floor + 0.25)).name)
        made.append(_box("UCX_FG_Gearbox",
                         (-0.25, (y_f + y_r) / 2 - 0.35, wz - 0.05),
                         (0.25, (y_f + y_r) / 2 + 0.35, wz + 0.35)).name)

        _normalize_ebt_colliders()
        print("RPF COLLIDERS:", made)
        self.report({'INFO'}, f"built {len(made)} colliders in Enfusion preset layers — "
                              f"review the convex profile blocks, then Build FireGeo")
        return {'FINISHED'}


class RPF_OT_build_firegeo(bpy.types.Operator):
    bl_idname = "rpf.build_firegeo"
    bl_label = "Build FireGeo (stock style)"
    bl_description = ("Rebuild fire geometry to SampleCar conventions: UTM_FG_Body_01, "
                      "skinned UTM_FG_Door_L01..R02 + UTM_FG_Trunk, UCX_FG hitzone boxes. "
                      "Run after parts are finalized")
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        arm = bpy.data.objects.get("Armature")
        # drop non-stock leftovers
        for n in ("UTM_FG_Engine", "UTM_FG_Battery", "UTM_FG_Gearbox",
                  "UTM_Detail_Glass", "UTM_Detail_Undershell", "UTM_Detail_BodyShell",
                  "UTM_FG_Body_01", "UTM_FG_Trunk",
                  "UTM_FG_Door_L01", "UTM_FG_Door_R01", "UTM_FG_Door_L02", "UTM_FG_Door_R02"):
            o = bpy.data.objects.get(n)
            if o:
                bpy.data.objects.remove(o)

        made = []
        body = _decimate_part("exterior", "UTM_FG_Body_01", 0.06)
        if body:
            made.append(body.name)

        fg_map = {"door_FL": "UTM_FG_Door_L01", "door_FR": "UTM_FG_Door_R01",
                  "door_RL": "UTM_FG_Door_L02", "door_RR": "UTM_FG_Door_R02",
                  "door_trunk": "UTM_FG_Trunk"}
        for part, fgname in fg_map.items():
            fg = _decimate_part(part, fgname, 0.10)
            if not fg:
                continue
            _remove_glass_faces(fg)
            bone = DOOR_BONE.get(part)
            if arm and bone:
                vg = fg.vertex_groups.new(name=bone)
                vg.add(range(len(fg.data.vertices)), 1.0, 'REPLACE')
                mod = fg.modifiers.new("Armature", 'ARMATURE')
                mod.object = arm
            made.append(fgname)

        _normalize_ebt_colliders()
        self.report({'INFO'}, f"firegeo built: {made}")
        return {'FINISHED'}


class RPF_OT_selected_parts_to_ucx(bpy.types.Operator):
    bl_idname = "rpf.selected_parts_to_ucx"
    bl_label = "Selected Parts -> UCX Convex"
    bl_description = ("Create one guaranteed-convex Vehicle UCX collider per selected "
                      "render part. Input points are reduced until each hull is at or "
                      "below the face cap; the final convex hull is never decimated")
    bl_options = {'REGISTER', 'UNDO'}

    max_faces: bpy.props.IntProperty(
        name="Maximum Faces",
        default=200,
        min=12,
        max=200,
        description="Maximum polygon count for each generated convex UCX hull",
    )

    replace_generated: bpy.props.BoolProperty(
        name="Replace Previous Generated Hulls",
        default=True,
        description="Remove prior selected-part UCX hulls generated by this tool",
    )

    def execute(self, context):
        sources = [
            obj for obj in context.selected_objects
            if obj.type == 'MESH' and not obj.name.startswith(COLLIDER_PFX)
        ]
        if not sources:
            self.report({'ERROR'}, "Select one or more render-part meshes")
            return {'CANCELLED'}

        checkpoint("pre_part_ucx")
        if self.replace_generated:
            for obj in list(bpy.data.objects):
                if obj.get("rpf_ucx_source"):
                    bpy.data.objects.remove(obj, do_unlink=True)

        made = []
        skipped = []
        index = _next_main_col_index()
        for source in sources:
            name = f"UCX_MainCol_{index:02d}_{_safe_name_token(source.name)}"
            hull = _part_convex_hull(source, name, self.max_faces)
            if hull is None:
                skipped.append(source.name)
                continue
            made.append(hull)
            index += 1

        bpy.ops.object.select_all(action='DESELECT')
        for obj in made:
            obj.select_set(True)
        if made:
            context.view_layer.objects.active = made[0]
        details = ", ".join(f"{o.name}:{len(o.data.polygons)}f" for o in made)
        print("RPF PART UCX:", details)
        self.report(
            {'INFO'} if made else {'ERROR'},
            f"created {len(made)} convex UCX hulls <= {self.max_faces} faces"
            + (f"; skipped {len(skipped)}" if skipped else ""),
        )
        return {'FINISHED'} if made else {'CANCELLED'}


class RPF_OT_validate_ucx(bpy.types.Operator):
    bl_idname = "rpf.validate_ucx"
    bl_label = "Validate UCX Physics"
    bl_description = "Check UCX physics hull face caps, transforms, naming, and Vehicle presets"
    bl_options = {'REGISTER'}

    def execute(self, context):
        issues = []
        hulls = [
            obj for obj in bpy.data.objects
            if obj.type == 'MESH' and obj.name.startswith(("UCX_MainCol_", "UBX_MainCol_"))
        ]
        for obj in hulls:
            if len(obj.data.polygons) > 200:
                issues.append(f"{obj.name}: {len(obj.data.polygons)} faces")
            if not _mesh_is_convex(obj):
                issues.append(f"{obj.name}: non-convex geometry")
            if obj.get("usage") != "Vehicle":
                issues.append(f"{obj.name}: usage={obj.get('usage')!r}")
            if "Vehicle" not in {collection.name for collection in obj.users_collection}:
                issues.append(f"{obj.name}: not in Vehicle preset collection")
            if any(abs(value - 1.0) > 1e-5 for value in obj.scale):
                issues.append(f"{obj.name}: unapplied scale")
            if obj.name.rsplit(".", 1)[-1].isdigit():
                issues.append(f"{obj.name}: Blender numeric suffix")
            source = bpy.data.objects.get(obj.get("rpf_ucx_source", ""))
            source_bones = [
                group.name for group in source.vertex_groups
                if group.name.startswith(("v_", "w_"))
            ] if source else []
            if len(source_bones) == 1 and obj.get("rpf_ucx_bone") != source_bones[0]:
                issues.append(f"{obj.name}: missing rigid binding to {source_bones[0]}")
            if len(source_bones) == 1:
                if source_bones[0] not in {group.name for group in obj.vertex_groups}:
                    issues.append(f"{obj.name}: missing vertex group {source_bones[0]}")
                if not any(mod.type == 'ARMATURE' and mod.object for mod in obj.modifiers):
                    issues.append(f"{obj.name}: missing Armature modifier")
        print("RPF UCX VALIDATION:", issues or "OK")
        self.report(
            {'ERROR'} if issues else {'INFO'},
            f"{len(issues)} UCX issues across {len(hulls)} physics hulls",
        )
        return {'FINISHED'}


class RPF_OT_convexify_selected_ucx(bpy.types.Operator):
    bl_idname = "rpf.convexify_selected_ucx"
    bl_label = "Convexify Selected UCX"
    bl_description = ("Rebuild selected UCX faces as a true convex hull from their "
                      "current adjusted points; preserves transforms, presets, and binding")
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        selected = [
            obj for obj in context.selected_objects
            if obj.type == 'MESH' and obj.name.startswith(("UCX_", "UBX_"))
        ]
        if not selected:
            self.report({'ERROR'}, "Select one or more UCX/UBX colliders")
            return {'CANCELLED'}
        repaired = []
        skipped = []
        for obj in selected:
            mesh = _convex_mesh_from_points(
                f"{obj.name}_ConvexMesh",
                [vertex.co.copy() for vertex in obj.data.vertices],
            )
            if mesh is None:
                skipped.append(obj.name)
                continue
            old_mesh = obj.data
            rigid_groups = [group.name for group in obj.vertex_groups]
            obj.data = mesh
            while obj.vertex_groups:
                obj.vertex_groups.remove(obj.vertex_groups[0])
            for group_name in rigid_groups:
                group = obj.vertex_groups.new(name=group_name)
                if len(rigid_groups) == 1:
                    group.add(range(len(obj.data.vertices)), 1.0, 'REPLACE')
            if old_mesh.users == 0:
                bpy.data.meshes.remove(old_mesh)
            repaired.append(obj.name)
        self.report(
            {'INFO'} if repaired else {'ERROR'},
            f"convexified {len(repaired)} selected UCX"
            + (f"; skipped {len(skipped)}" if skipped else ""),
        )
        return {'FINISHED'} if repaired else {'CANCELLED'}


class RPF_OT_collision_view(bpy.types.Operator):
    bl_idname = "rpf.collision_view"
    bl_label = "Collision Review View"
    bl_description = "Show only the requested Enfusion collision section with the render model"
    bl_options = {'REGISTER'}

    mode: bpy.props.EnumProperty(
        items=[
            ('MODEL', "Model", "Render model only"),
            ('UCX', "UCX", "Vehicle physics and MineTrigger with model"),
            ('FIRE', "FireGeo", "FireGeo and GlassFire with model"),
            ('ALL', "All", "All render and collision sections"),
        ],
        default='UCX',
    )

    def execute(self, context):
        collider_prefixes = ("UCX_", "UBX_", "UCL_", "UTM_", "USP_", "UCS_")
        for obj in bpy.data.objects:
            if obj.type != 'MESH':
                continue
            is_collider = obj.name.startswith(collider_prefixes)
            usage = obj.get("usage", "")
            if not is_collider:
                visible = True
                obj.display_type = 'TEXTURED' if self.mode in {'MODEL', 'UCX'} else 'WIRE'
                obj.show_in_front = False
            elif self.mode == 'MODEL':
                visible = False
            elif self.mode == 'UCX':
                visible = usage in {"Vehicle", "MineTrigger"}
            elif self.mode == 'FIRE':
                visible = usage in {"FireGeo", "GlassFire"}
            else:
                visible = True
            obj.hide_set(not visible)
            if is_collider:
                obj.show_wire = visible
                obj.show_all_edges = visible
                obj.show_in_front = visible
                obj.display_type = 'SOLID' if visible and usage == "Vehicle" else 'WIRE'
        context.scene["rpf_collision_view"] = self.mode
        self.report({'INFO'}, f"collision review: {self.mode}")
        return {'FINISHED'}


class RPF_OT_view_axis(bpy.types.Operator):
    bl_idname = "rpf.view_axis"
    bl_label = "Set Review Axis"
    bl_description = "Switch all 3D viewports to a collision-review direction and frame the vehicle"
    bl_options = {'REGISTER'}

    axis: bpy.props.EnumProperty(
        items=[
            ('LEFT', "Left", "Left side"),
            ('RIGHT', "Right", "Right side"),
            ('FRONT', "Front", "Front"),
            ('BACK', "Back", "Rear"),
            ('TOP', "Top", "Top"),
            ('BOTTOM', "Bottom", "Bottom"),
        ],
        default='LEFT',
    )

    def execute(self, context):
        changed = 0
        for window in context.window_manager.windows:
            for area in window.screen.areas:
                if area.type != 'VIEW_3D':
                    continue
                region = next((r for r in area.regions if r.type == 'WINDOW'), None)
                if not region:
                    continue
                with context.temp_override(window=window, area=area, region=region):
                    bpy.ops.view3d.view_axis(type=self.axis, align_active=False)
                    bpy.ops.view3d.view_all(center=False)
                changed += 1
        self.report({'INFO'}, f"{self.axis.lower()} review view in {changed} viewport(s)")
        return {'FINISHED'}


class RPF_OT_sort_collapse(bpy.types.Operator):
    bl_idname = "rpf.sort_collapse"
    bl_label = "Sort + Collapse Enfusion"
    bl_description = ("Normalize collider objects into Enfusion preset collections, "
                      "sort collection children, and collapse Outliner hierarchies")
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        normalized = _normalize_ebt_colliders()
        root = bpy.data.collections.get("Colliders")
        if root:
            for name in ("Vehicle", "MineTrigger", "FireGeo", "GlassFire"):
                layer = bpy.data.collections.get(name)
                if layer and layer.name not in {child.name for child in root.children}:
                    root.children.link(layer)
        collapsed = 0
        for window in context.window_manager.windows:
            for area in window.screen.areas:
                if area.type != 'OUTLINER':
                    continue
                region = next((r for r in area.regions if r.type == 'WINDOW'), None)
                if not region:
                    continue
                with context.temp_override(window=window, area=area, region=region):
                    for _ in range(8):
                        bpy.ops.outliner.show_one_level(open=False)
                collapsed += 1
        self.report({'INFO'}, f"sorted {len(normalized)} colliders; collapsed {collapsed} Outliner(s)")
        return {'FINISHED'}


# ----------------------------------------------------------------------------
# 1) AUTO-SETUP
# ----------------------------------------------------------------------------

class RPF_OT_auto_setup(bpy.types.Operator):
    bl_idname = "rpf.auto_setup"
    bl_label = "1. Auto-Setup (scale + assign)"
    bl_description = ("Rescale to real wheelbase, apply transforms, split fused door "
                      "skins, assign all pieces into reviewable part collections")
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        cp = checkpoint("preauto")

        meshes = all_meshes()
        mn = Vector((1e9,) * 3); mx = Vector((-1e9,) * 3)
        for o in meshes:
            a, b = wbbox(o)
            mn.x = min(mn.x, a.x); mn.y = min(mn.y, a.y); mn.z = min(mn.z, a.z)
            mx.x = max(mx.x, b.x); mx.y = max(mx.y, b.y); mx.z = max(mx.z, b.z)
        if (mx - mn).length > 50:
            S = Matrix.Scale(0.0254, 4)
            for o in meshes:
                if o.parent is None:
                    o.matrix_world = S @ o.matrix_world
            context.view_layer.update()

        tires = []
        for o in meshes:
            a, b = wbbox(o)
            d = b - a; c = (a + b) / 2
            if 0.55 < d.y < 0.95 and 0.55 < d.z < 0.95 and abs(d.y - d.z) < 0.05 \
               and d.x < 0.45 and c.z < 0.8:
                tires.append((o, c))
        wb_target = context.scene.rpf_wheelbase or TARGET_WHEELBASE
        if len(tires) >= 4:
            ys = sorted(c.y for _, c in tires)
            wb = ys[-1] - ys[0]
            k = wb_target / wb
        else:
            wb = 0.0
            k = 1.0
            self.report({'WARNING'}, "tire detection failed; wheelbase not calibrated")
        if abs(k - 1.0) > 0.001:
            S = Matrix.Scale(k, 4)
            for o in meshes:
                if o.parent is None:
                    o.matrix_world = S @ o.matrix_world
            context.view_layer.update()

        mn = Vector((1e9,) * 3); mx = Vector((-1e9,) * 3)
        for o in meshes:
            a, b = wbbox(o)
            mn.x = min(mn.x, a.x); mn.y = min(mn.y, a.y); mn.z = min(mn.z, a.z)
            mx.x = max(mx.x, b.x); mx.y = max(mx.y, b.y); mx.z = max(mx.z, b.z)
        ctr = (mn + mx) / 2
        T = Matrix.Translation(Vector((-ctr.x, -ctr.y, -mn.z)))
        for o in meshes:
            if o.parent is None:
                o.matrix_world = T @ o.matrix_world
        context.view_layer.update()

        bpy.ops.object.select_all(action='DESELECT')
        for o in meshes:
            o.hide_set(False)
            o.select_set(True)
        context.view_layer.objects.active = meshes[0]
        bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)
        bpy.ops.object.select_all(action='DESELECT')

        kk = wb_target / 2.947 if wb else 1.0
        context.scene["rpf_k"] = kk

        import bmesh
        seam = SKIN_SEAM_Y * kk
        front_skins = {}
        for suf in FUSED_SKINS:
            o = bpy.data.objects.get(f"{PFX}.{suf}")
            if not o:
                continue
            bpy.ops.object.select_all(action='DESELECT')
            o.hide_set(False); o.select_set(True)
            context.view_layer.objects.active = o
            bpy.ops.object.mode_set(mode='EDIT')
            bm = bmesh.from_edit_mesh(o.data)
            mwo = o.matrix_world
            for f in bm.faces:
                f.select = (mwo @ f.calc_center_median()).y >= seam
            bmesh.update_edit_mesh(o.data)
            before = set(bpy.data.objects.keys())
            bpy.ops.mesh.separate(type='SELECTED')
            bpy.ops.object.mode_set(mode='OBJECT')
            new = list(set(bpy.data.objects.keys()) - before)
            if new:
                front_skins[suf] = new[0]

        for part, sufs in SEED.items():
            for suf in sufs:
                o = bpy.data.objects.get(f"{PFX}.{suf}")
                if o:
                    move_to_coll(o, part)
        skin_map = {"1637": ("door_RL", front_skins.get("1637")),
                    "1648": ("door_RR", front_skins.get("1648"))}
        for suf, (rear_part, front_name) in skin_map.items():
            o = bpy.data.objects.get(f"{PFX}.{suf}")
            if o:
                move_to_coll(o, rear_part)
            if front_name:
                fo = bpy.data.objects.get(front_name)
                if fo:
                    move_to_coll(fo, "door_FL" if rear_part == "door_RL" else "door_FR")

        doorvols = {
            "door_FL": (Vector((-1.19, -0.26, 0.30)) * kk, Vector((-0.62, 1.03, 1.66)) * kk),
            "door_FR": (Vector((0.62, -0.26, 0.30)) * kk, Vector((1.19, 1.03, 1.66)) * kk),
            "door_RL": (Vector((-1.19, -1.33, 0.30)) * kk, Vector((-0.62, -0.19, 1.66)) * kk),
            "door_RR": (Vector((0.62, -1.33, 0.30)) * kk, Vector((1.19, -0.19, 1.66)) * kk),
        }
        unassigned = [o for o in all_meshes() if part_of(o) is None]
        for o in unassigned:
            a, b = wbbox(o)
            d = b - a
            best, bestc = None, 0.0
            for kpart, (vmn, vmx) in doorvols.items():
                c = containment(a, b, vmn, vmx)
                if c > bestc:
                    bestc, best = c, kpart
            if best and bestc > 0.90:
                if d.y > 1.40 * kk or d.z > 1.45 * kk:
                    continue
                move_to_coll(o, best)

        # known glass panes
        for wpart, sufs in GLASS_SEED.items():
            for suf in sufs:
                o = bpy.data.objects.get(f"{PFX}.{suf}")
                if o:
                    move_to_coll(o, wpart)

        for o in [o for o in all_meshes() if part_of(o) is None]:
            a, b = wbbox(o)
            d = b - a; c = (a + b) / 2
            if a.z > 1.66 * kk and d.y < 1.2 * kk and abs(c.x) < 1.0 * kk:
                move_to_coll(o, "lights_emergency")
            elif c.y > 2.30 * kk and 0.62 * kk < c.z < 1.08 * kk and 0.40 * kk < abs(c.x) < 1.05 * kk \
                    and d.z < 0.5 * kk and d.x < 0.7 * kk:
                move_to_coll(o, "lights_front")
            elif c.y < -2.30 * kk and 0.70 * kk < c.z < 1.25 * kk and 0.35 * kk < abs(c.x) < 1.05 * kk \
                    and d.z < 0.6 * kk and d.x < 0.7 * kk:
                move_to_coll(o, "lights_rear")

        for o in [o for o in all_meshes() if part_of(o) is None]:
            move_to_coll(o, "interior" if dominant_material(o) == "interior" else "exterior")

        bpy.ops.wm.save_mainfile()
        n = {p: len(bpy.data.collections[p].objects) for p in PART_ORDER
             if bpy.data.collections.get(p)}
        self.report({'INFO'}, f"auto-setup done, k={kk:.4f}; counts: {n}; checkpoint: {cp}")
        return {'FINISHED'}


# ----------------------------------------------------------------------------
# 2) ORGANIZE — readable outliner
# ----------------------------------------------------------------------------

class RPF_OT_organize(bpy.types.Operator):
    bl_idname = "rpf.organize"
    bl_label = "2. Organize Outliner"
    bl_description = ("Rename every piece to its part (door_FL.123 ...), color-tag "
                      "collections, sort part collections under PARTS")
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        renamed = 0
        for p in PART_ORDER:
            coll = bpy.data.collections.get(p)
            if not coll:
                continue
            if p in COLL_COLORS:
                coll.color_tag = COLL_COLORS[p]
            for o in coll.objects:
                if o.name.startswith(p + "."):
                    continue
                if "rpf_orig" not in o:
                    o["rpf_orig"] = o.name
                suffix = o.name.split(".")[-1] if "." in o.name else o.name
                o.name = f"{p}.{suffix}"
                renamed += 1
        # remove stale empty collections that are not part of the system
        for c in list(bpy.data.collections):
            if c.name not in PART_ORDER and c.name != ROOT_COLL and not c.objects \
               and not c.children:
                bpy.data.collections.remove(c)
        bpy.ops.wm.save_mainfile()
        self.report({'INFO'}, f"renamed {renamed} pieces to part-prefixed names")
        return {'FINISHED'}


# ----------------------------------------------------------------------------
# 3) REVIEW — quick select, ghost, door test-open
# ----------------------------------------------------------------------------

def _part_items(self, context):
    return [(p, p, "") for p in PART_ORDER]


class RPF_OT_quick_select(bpy.types.Operator):
    bl_idname = "rpf.quick_select"
    bl_label = "Quick Select"
    bl_description = "Select all pieces of this part (doors include their window) and frame the view"
    part: bpy.props.StringProperty()

    def execute(self, context):
        context.scene.rpf_active_part = self.part
        # if a review session is running, retarget the ghost/lock to this part
        if context.scene.get("rpf_reviewing", ""):
            bpy.ops.rpf.review()
        bpy.ops.object.select_all(action='DESELECT')
        n = 0
        for o in part_objects(self.part):
            o.hide_set(False)
            o.hide_select = False
            o.select_set(True)
            context.view_layer.objects.active = o
            n += 1
        if n:
            frame_view(context)
        self.report({'INFO'}, f"{self.part}: {n} pieces selected")
        return {'FINISHED'}


class RPF_OT_review(bpy.types.Operator):
    bl_idname = "rpf.review"
    bl_label = "Ghost Others"
    bl_description = "Show active part solid, ghost the rest of the car as wireframe"

    def execute(self, context):
        part = context.scene.rpf_active_part
        members = {o.name for o in part_objects(part)}
        hide_others = context.scene.rpf_ghost_hide
        for o in all_meshes():
            if o.name in members:
                o.hide_set(False)
                o.hide_select = False
                o.display_type = _solid_display(o)
            else:
                # ghosted pieces are LOCKED so box-select etc. can't touch them
                o.hide_select = True
                if hide_others:
                    o.hide_set(True)
                else:
                    o.hide_set(False)
                    o.display_type = 'WIRE'
        context.scene["rpf_reviewing"] = part
        self.report({'INFO'}, f"reviewing {part} ({len(members)} pieces) — others "
                              f"{'hidden' if hide_others else 'wireframed'} + locked")
        return {'FINISHED'}


class RPF_OT_stop_review(bpy.types.Operator):
    bl_idname = "rpf.stop_review"
    bl_label = "Stop Review"
    bl_description = "Restore normal display for all objects"

    def execute(self, context):
        for o in all_meshes():
            o.display_type = _solid_display(o)
            o.hide_select = False
            o.hide_set(False)
        context.scene["rpf_reviewing"] = ""
        return {'FINISHED'}


class RPF_OT_door_open(bpy.types.Operator):
    bl_idname = "rpf.door_open"
    bl_label = "Test-Open Door"
    bl_description = ("Swing this door open on its hinge. Pieces that wrongly belong "
                      "to the door swing out with it — select them and use "
                      "'Send Selected -> interior'")
    door: bpy.props.StringProperty()

    def execute(self, context):
        bpy.ops.rpf.doors_close()
        hinge = door_hinge(self.door)
        if hinge is None:
            self.report({'ERROR'}, "could not compute hinge")
            return {'CANCELLED'}
        # NO parenting: rotate each piece's matrix directly around the hinge
        # axis and remember the exact original matrix for a perfect restore.
        # (Parenting needed a depsgraph update before reading emp.matrix_world
        # and silently translated the door instead of rotating it.)
        if self.door == "door_trunk":
            # tailgate: hinge at top edge, swings UP around the X axis
            M = (Matrix.Translation(hinge)
                 @ Matrix.Rotation(-1.0, 4, 'X')
                 @ Matrix.Translation(-hinge))
        else:
            sign = -1.0 if hinge.x < 0 else 1.0
            M = (Matrix.Translation(hinge)
                 @ Matrix.Rotation(sign * 1.0, 4, 'Z')   # ~57 degrees
                 @ Matrix.Translation(-hinge))
        objs = part_objects(self.door)
        for o in objs:
            if o.type != 'MESH':
                continue
            if "rpf_saved_mw" not in o.keys():     # never overwrite a saved state
                o["rpf_saved_mw"] = [v for row in o.matrix_world for v in row]
            o.matrix_world = M @ o.matrix_world
        # visual hinge axis indicator only — nothing is parented to it
        emp = bpy.data.objects.new(f"RPF_HINGE_{self.door}", None)
        emp.empty_display_type = 'ARROWS'
        emp.empty_display_size = 0.3
        emp.location = hinge
        get_coll(self.door).objects.link(emp)
        context.view_layer.update()
        context.scene["rpf_open_door"] = self.door
        self.report({'INFO'}, f"{self.door} opened — wrongly assigned pieces now float in mid-air")
        return {'FINISHED'}


class RPF_OT_doors_close(bpy.types.Operator):
    bl_idname = "rpf.doors_close"
    bl_label = "Close All Doors"
    bl_description = "Reset all test-opened doors and remove hinge helpers"

    def execute(self, context):
        n = 0
        for o in bpy.data.objects:
            if o.type == 'MESH' and "rpf_saved_mw" in o.keys():
                v = list(o["rpf_saved_mw"])
                o.matrix_world = Matrix((v[0:4], v[4:8], v[8:12], v[12:16]))
                del o["rpf_saved_mw"]
                n += 1
        for emp in [o for o in bpy.data.objects if o.name.startswith("RPF_HINGE_")]:
            bpy.data.objects.remove(emp)
        context.view_layer.update()
        context.scene["rpf_open_door"] = ""
        if n:
            self.report({'INFO'}, f"restored {n} pieces to exact saved positions")
        return {'FINISHED'}


class RPF_OT_send_interior(bpy.types.Operator):
    bl_idname = "rpf.send_interior"
    bl_label = "Send Selected → interior"
    bl_description = ("Closes any test-opened door first, then moves the selected "
                      "pieces into the interior collection")
    bl_options = {'REGISTER', 'UNDO'}

    target: bpy.props.StringProperty(default="interior")

    def execute(self, context):
        picked = [o.name for o in context.selected_objects if o.type == 'MESH']
        bpy.ops.rpf.doors_close()
        n = 0
        for name in picked:
            o = bpy.data.objects.get(name)
            if o:
                move_to_coll(o, self.target)
                base = o.name.split(".")[-1]
                o.name = f"{self.target}.{base}"
                apply_review_state(context, o)
                n += 1
        self.report({'INFO'}, f"moved {n} pieces to {self.target} (doors closed first)")
        return {'FINISHED'}


class RPF_OT_add_selected(bpy.types.Operator):
    bl_idname = "rpf.add_selected"
    bl_label = "Add Selected → Active Part"
    bl_description = "Move the selected objects into the active part collection"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        part = context.scene.rpf_active_part
        picked = [o.name for o in context.selected_objects if o.type == 'MESH']
        bpy.ops.rpf.doors_close()
        n = 0
        for name in picked:
            o = bpy.data.objects.get(name)
            if o:
                move_to_coll(o, part)
                base = o.name.split(".")[-1]
                o.name = f"{part}.{base}"
                apply_review_state(context, o)
                n += 1
        self.report({'INFO'}, f"moved {n} objects into {part}")
        return {'FINISHED'}


class RPF_OT_move_selected(bpy.types.Operator):
    bl_idname = "rpf.move_selected"
    bl_label = "Move Selected → Target"
    bl_description = "Move the selected objects into the chosen target collection"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        target = context.scene.rpf_move_target
        picked = [o.name for o in context.selected_objects if o.type == 'MESH']
        bpy.ops.rpf.doors_close()
        n = 0
        for name in picked:
            o = bpy.data.objects.get(name)
            if o:
                move_to_coll(o, target)
                base = o.name.split(".")[-1]
                o.name = f"{target}.{base}"
                apply_review_state(context, o)
                n += 1
        self.report({'INFO'}, f"moved {n} objects into {target}")
        return {'FINISHED'}


class RPF_OT_snap_back(bpy.types.Operator):
    bl_idname = "rpf.snap_back"
    bl_label = "Snap Back All Parts"
    bl_description = ("RESCUE: restore every piece to the shared base position "
                      "(fixes doors/parts frozen in mid-air). Only valid before Finalize")
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        from collections import Counter as _C
        meshes = all_meshes()
        if len(meshes) < 50:
            self.report({'ERROR'}, "scene looks finalized (few objects) — snap-back would wreck origins")
            return {'CANCELLED'}
        # restore any saved open-door states first
        bpy.ops.rpf.doors_close()
        locs = _C(tuple(round(v, 6) for v in o.location) for o in meshes)
        base = Vector(locs.most_common(1)[0][0])
        n = 0
        for o in meshes:
            if (o.location - base).length > 1e-6 or any(abs(r) > 1e-9 for r in o.rotation_euler):
                o.location = base
                o.rotation_euler = (0, 0, 0)
                n += 1
        context.view_layer.update()
        self.report({'INFO'}, f"snapped {n} pieces back to base position")
        return {'FINISHED'}


class RPF_OT_check_transforms(bpy.types.Operator):
    bl_idname = "rpf.check_transforms"
    bl_label = "Check Transforms"
    bl_description = "Verify every piece has applied scale/rotation; apply if not"

    def execute(self, context):
        bad = [o for o in all_meshes()
               if any(abs(s - 1) > 1e-5 for s in o.scale)
               or any(abs(r) > 1e-5 for r in o.rotation_euler)]
        if not bad:
            self.report({'INFO'}, "all transforms applied — scale 1.0, rotation 0")
            return {'FINISHED'}
        bpy.ops.object.select_all(action='DESELECT')
        for o in bad:
            o.hide_set(False)
            o.select_set(True)
        context.view_layer.objects.active = bad[0]
        bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)
        self.report({'INFO'}, f"applied transforms on {len(bad)} stragglers")
        return {'FINISHED'}


# ----------------------------------------------------------------------------
# 4) TEXTURES
# ----------------------------------------------------------------------------

TEX_EXTS = (".png", ".jpg", ".jpeg", ".tga", ".tif", ".tiff", ".bmp", ".exr")

# map-type token -> recognized filename suffixes (Enfusion BCR/NMO, Substance,
# V-Ray and generic naming). Matched against the LAST '_' token first so set
# names containing words like 'metal' don't misclassify the map.
MAP_TOKENS = {
    "base":   {"bcr", "basecolor", "albedo", "diffuse", "diff", "color", "col", "alb"},
    "normal": {"nmo", "normal", "nrm", "nor", "norm"},
    "rough":  {"rough", "roughness"},
    "gloss":  {"gloss", "glossines", "glossiness"},
    "metal":  {"metal", "metallic", "metalness"},
    "emit":   {"illumination", "illum", "emissive", "emission", "glow"},
    "ao":     {"ao", "occlusion"},
}


def _norm(s):
    return "".join(ch for ch in s.lower() if ch.isalnum())


def _texture_folder(path):
    """Resolve the texture source: a folder is used as-is, a .zip is extracted
    once to a sibling '<name>_rpf_tex' folder."""
    import os, zipfile
    path = bpy.path.abspath(path).strip('"') if path else ""
    if not path or not os.path.exists(path):
        return None, f"texture path not found: {path}"
    if os.path.isfile(path):
        if not path.lower().endswith(".zip"):
            return None, "texture file must be a .zip (or point at a folder)"
        dst = os.path.splitext(path)[0] + "_rpf_tex"
        if not os.path.isdir(dst):
            with zipfile.ZipFile(path) as z:
                z.extractall(dst)
        return dst, None
    return path, None


def _scan_textures(folder):
    """Recursively index images as (normalized set name, map type, full path)."""
    import os
    out = []
    for root, _dirs, files in os.walk(folder):
        for f in files:
            stem, ext = os.path.splitext(f)
            if ext.lower() not in TEX_EXTS:
                continue
            toks = [t for t in stem.replace("-", "_").split("_") if t]
            last = _norm(toks[-1]) if toks else ""
            mtype = next((k for k, keys in MAP_TOKENS.items() if last in keys), None)
            if mtype:
                setname = _norm("".join(toks[:-1]))
            else:
                stemn = _norm(stem)
                setname = stemn
                for k, keys in MAP_TOKENS.items():
                    if any(key in stemn for key in keys if len(key) > 3):
                        mtype = k
                        break
            if mtype and setname:
                out.append((setname, mtype, os.path.join(root, f)))
    return out


class RPF_OT_apply_textures(bpy.types.Operator):
    bl_idname = "rpf.apply_textures"
    bl_label = "Apply Textures"
    bl_description = ("Build PBR node setups for EVERY material that matches a texture "
                      "set in the texture path (folder OR .zip — zips are auto-"
                      "extracted). Understands Enfusion _BCR/_NMO packed maps and "
                      "diffuse/albedo/rough/gloss/metal/normal/illumination naming")
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        folder, err = _texture_folder(context.scene.rpf_tex_path)
        if err:
            self.report({'ERROR'}, err)
            return {'CANCELLED'}
        entries = _scan_textures(folder)
        if not entries:
            self.report({'ERROR'}, f"no recognizable textures under {folder}")
            return {'CANCELLED'}

        done, unmatched = {}, []
        for mat in bpy.data.materials:
            mn_ = _norm(mat.name)
            if not mn_:
                continue
            # exact set-name match beats substring; longer set name beats shorter
            # (RearDoorFrames must win over doorframes)
            best = {}
            for setn, mtype, p in entries:
                if setn in mn_ or mn_ in setn:
                    score = (setn == mn_, len(setn))
                    if mtype not in best or score > best[mtype][0]:
                        best[mtype] = (score, p)
            maps = {k: v[1] for k, v in best.items()}
            if not maps:
                unmatched.append(mat.name)
                continue
            mat.use_nodes = True
            nt = mat.node_tree
            nt.nodes.clear()
            outn = nt.nodes.new("ShaderNodeOutputMaterial"); outn.location = (600, 0)
            bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled"); bsdf.location = (250, 0)
            nt.links.new(bsdf.outputs["BSDF"], outn.inputs["Surface"])

            def tex(p, noncolor=False, loc=(0, 0)):
                img = bpy.data.images.load(p, check_existing=True)
                if noncolor:
                    img.colorspace_settings.name = 'Non-Color'
                n = nt.nodes.new("ShaderNodeTexImage")
                n.image = img; n.location = loc
                return n

            import os as _os
            if "base" in maps:
                d = tex(maps["base"], loc=(-500, 300))
                nt.links.new(d.outputs["Color"], bsdf.inputs["Base Color"])
                stem = _norm(_os.path.splitext(_os.path.basename(maps["base"]))[0].split("_")[-1])
                if stem == "bcr":            # Enfusion BCR: roughness packed in alpha
                    d.image.alpha_mode = 'CHANNEL_PACKED'
                    nt.links.new(d.outputs["Alpha"], bsdf.inputs["Roughness"])
            if "rough" in maps:
                r = tex(maps["rough"], noncolor=True, loc=(-500, 0))
                nt.links.new(r.outputs["Color"], bsdf.inputs["Roughness"])
            elif "gloss" in maps:
                g = tex(maps["gloss"], noncolor=True, loc=(-500, 0))
                inv = nt.nodes.new("ShaderNodeInvert"); inv.location = (-200, 0)
                nt.links.new(g.outputs["Color"], inv.inputs["Color"])
                nt.links.new(inv.outputs["Color"], bsdf.inputs["Roughness"])
            if "metal" in maps:
                m = tex(maps["metal"], noncolor=True, loc=(-750, 100))
                nt.links.new(m.outputs["Color"], bsdf.inputs["Metallic"])
            if "normal" in maps:
                nm = tex(maps["normal"], noncolor=True, loc=(-500, -350))
                nmap = nt.nodes.new("ShaderNodeNormalMap"); nmap.location = (-200, -350)
                nt.links.new(nm.outputs["Color"], nmap.inputs["Color"])
                nt.links.new(nmap.outputs["Normal"], bsdf.inputs["Normal"])
            if "emit" in maps and "Emission Color" in bsdf.inputs:
                il = tex(maps["emit"], loc=(-500, -650))
                nt.links.new(il.outputs["Color"], bsdf.inputs["Emission Color"])
                bsdf.inputs["Emission Strength"].default_value = 1.0
            done[mat.name] = sorted(maps)
        print("RPF TEXTURES:", done)
        if unmatched:
            print("RPF TEXTURES unmatched materials:", unmatched)
        self.report({'INFO'}, f"textured {len(done)} materials ({len(unmatched)} unmatched — see console)")
        return {'FINISHED'}


# ----------------------------------------------------------------------------
# 5) FINALIZE
# ----------------------------------------------------------------------------

class RPF_OT_finalize(bpy.types.Operator):
    bl_idname = "rpf.finalize"
    bl_label = "4. Finalize (join + origins)"
    bl_description = ("Join each part collection into one named object, set hinge/"
                      "wheel/column origins, parent door windows to doors")
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        bpy.ops.rpf.doors_close()
        cp = checkpoint("prefinal")
        kk = context.scene.get("rpf_k", 1.0)

        def coll_objs(name):
            c = bpy.data.collections.get(name)
            return list(c.objects) if c else []

        results = {}
        hinges = {}
        for dn in DOORS:
            hinge = door_hinge(dn)
            d = join_objects(coll_objs(dn), dn)
            if not d:
                continue
            if hinge:
                set_origin(d, tuple(hinge))
                hinges[dn] = tuple(hinge)
            move_to_coll(d, dn)
            results[dn] = len(d.data.polygons)

        for dn, wn in DOOR_WINDOW.items():
            w = join_objects(coll_objs(wn), dn + "_window")
            if not w:
                continue
            set_origin(w, hinges.get(dn, (0, 0, 0)))
            door = bpy.data.objects.get(dn)
            if door:
                w.parent = door
                w.matrix_parent_inverse = door.matrix_world.inverted()
            move_to_coll(w, wn)
            results[dn + "_window"] = len(w.data.polygons)

        for wn in ("wheel_FL", "wheel_FR", "wheel_RL", "wheel_RR"):
            w = join_objects(coll_objs(wn), wn)
            if not w:
                continue
            a, b = wbbox(w)
            set_origin(w, ((a.x + b.x) / 2, (a.y + b.y) / 2, (a.z + b.z) / 2))
            move_to_coll(w, wn)
            results[wn] = len(w.data.polygons)

        for bn, wn in [("brake_FL", "wheel_FL"), ("brake_FR", "wheel_FR"),
                       ("brake_RL", "wheel_RL"), ("brake_RR", "wheel_RR")]:
            br = join_objects(coll_objs(bn), bn)
            if not br:
                continue
            wheel = bpy.data.objects.get(wn)
            set_origin(br, tuple(wheel.location) if wheel else tuple(br.location))
            move_to_coll(br, bn)
            results[bn] = len(br.data.polygons)

        sw = join_objects(coll_objs("Steering_Wheel"), "Steering_Wheel")
        if sw:
            wc = Vector((-0.418, 0.502, 1.111)) * kk
            cc = Vector((-0.418, 0.727, 0.985)) * kk
            org = wc + (cc - wc).normalized() * 0.09 * kk
            set_origin(sw, tuple(org))
            move_to_coll(sw, "Steering_Wheel")
            results["Steering_Wheel"] = len(sw.data.polygons)

        pb = join_objects(coll_objs("Pedal_Brake"), "Pedal_Brake")
        if pb:
            set_origin(pb, tuple(Vector((-0.415, 1.015, 0.65)) * kk))
            move_to_coll(pb, "Pedal_Brake")
        pa = join_objects(coll_objs("Pedal_Accelerator"), "Pedal_Accelerator")
        if pa:
            set_origin(pa, tuple(Vector((-0.229, 0.961, 0.61)) * kk))
            move_to_coll(pa, "Pedal_Accelerator")

        for gn in ("lights_front", "lights_rear", "lights_emergency",
                   "windows_body", "interior", "exterior"):
            g = join_objects(coll_objs(gn), gn)
            if g:
                set_origin(g, (0, 0, 0))
                move_to_coll(g, gn)
                results[gn] = len(g.data.polygons)

        bpy.ops.wm.save_mainfile()
        self.report({'INFO'}, f"finalized: {results}; checkpoint: {cp}")
        return {'FINISHED'}


# ----------------------------------------------------------------------------
# 5b) EXPLODE / REJOIN — temporary piece mode for joined parts
# ----------------------------------------------------------------------------

def _merge_into_named_part(piece, part):
    """Join a loose piece into the post-finalize object named `part`,
    re-binding its skinning to that part's bone first."""
    tgt = bpy.data.objects.get(part)
    if not tgt or tgt.type != 'MESH' or tgt is piece:
        return False
    vgname = tgt.vertex_groups[0].name if len(tgt.vertex_groups) else None
    for vg in list(piece.vertex_groups):
        piece.vertex_groups.remove(vg)
    if vgname:
        vg = piece.vertex_groups.new(name=vgname)
        vg.add(range(len(piece.data.vertices)), 1.0, 'REPLACE')
    bpy.ops.object.select_all(action='DESELECT')
    piece.hide_set(False); piece.hide_select = False; piece.select_set(True)
    tgt.hide_set(False); tgt.select_set(True)
    bpy.context.view_layer.objects.active = tgt
    bpy.ops.object.join()
    return True


class RPF_OT_explode_part(bpy.types.Operator):
    bl_idname = "rpf.explode_part"
    bl_label = "Explode Part (pieces)"
    bl_description = ("Temporarily split the active joined part into its loose pieces "
                      "so they can be clicked and moved in Object Mode. Use 'Rejoin "
                      "All Parts' when done")
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        part = context.scene.rpf_active_part
        obj = bpy.data.objects.get(part)
        if not obj or obj.type != 'MESH' or not len(obj.vertex_groups):
            self.report({'WARNING'}, f"{part} is not a joined part object — already pieces?")
            return {'CANCELLED'}
        bpy.ops.rpf.doors_close()
        # remember origin so Rejoin can restore it exactly
        context.scene[f"rpf_origin_{part}"] = list(obj.location)
        bpy.ops.object.select_all(action='DESELECT')
        obj.hide_set(False); obj.hide_select = False; obj.select_set(True)
        context.view_layer.objects.active = obj
        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.mesh.select_all(action='SELECT')
        bpy.ops.mesh.separate(type='LOOSE')
        bpy.ops.object.mode_set(mode='OBJECT')
        pieces = list(context.selected_objects)
        coll = get_coll(part)
        for p in pieces:
            for uc in list(p.users_collection):
                uc.objects.unlink(p)
            coll.objects.link(p)
        exploded = [e for e in context.scene.get("rpf_exploded", "").split(",") if e]
        if part not in exploded:
            exploded.append(part)
        context.scene["rpf_exploded"] = ",".join(exploded)
        # ghost+lock everything else so only the pieces are clickable
        context.scene["rpf_reviewing"] = part
        bpy.ops.rpf.review()
        self.report({'INFO'}, f"{part} exploded into {len(pieces)} clickable pieces — "
                              f"move strays, then 'Rejoin All Parts'")
        return {'FINISHED'}


class RPF_OT_rejoin_parts(bpy.types.Operator):
    bl_idname = "rpf.rejoin_parts"
    bl_label = "Rejoin All Parts"
    bl_description = ("Stitch all exploded pieces back into their part objects "
                      "(pieces you moved get re-skinned to their new part's bone), "
                      "restore origins, end piece mode")
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        bpy.ops.rpf.doors_close()
        bpy.ops.rpf.stop_review()
        merged = 0
        for part in PART_ORDER:
            coll = bpy.data.collections.get(part)
            if not coll:
                continue
            for piece in [o for o in list(coll.objects)
                          if o.type == 'MESH' and o.name != part]:
                if _merge_into_named_part(piece, part):
                    merged += 1
        # restore stored origins
        for part in PART_ORDER:
            key = f"rpf_origin_{part}"
            if key in context.scene.keys():
                o = bpy.data.objects.get(part)
                if o:
                    set_origin(o, tuple(context.scene[key]))
                del context.scene[key]
        context.scene["rpf_exploded"] = ""
        bpy.ops.object.select_all(action='DESELECT')
        self.report({'INFO'}, f"rejoined: {merged} pieces merged back into parts")
        return {'FINISHED'}


# ----------------------------------------------------------------------------
# 6) EXTRACT (edit-mode helper) + ENFUSION MULTI-FBX EXPORT
# ----------------------------------------------------------------------------

class RPF_OT_extract_selection(bpy.types.Operator):
    bl_idname = "rpf.extract_selection"
    bl_label = "Extract Edit-Selection → Target"
    bl_description = ("In Edit Mode: separate the selected geometry into a new object "
                      "and move it to the Target part collection (e.g. pull strobe "
                      "lenses out of a joined mesh)")
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.mode == 'EDIT_MESH'

    def execute(self, context):
        target = context.scene.rpf_move_target
        src = context.edit_object
        before = set(bpy.data.objects.keys())
        bpy.ops.mesh.separate(type='SELECTED')
        bpy.ops.object.mode_set(mode='OBJECT')
        new = [bpy.data.objects[n] for n in set(bpy.data.objects.keys()) - before]
        for o in new:
            move_to_coll(o, target)
            o.name = f"{target}.from_{src.name.split('.')[0]}"
        self.report({'INFO'}, f"extracted {len(new)} object(s) -> {target}")
        return {'FINISHED'}


def _fbx_export(path, objs):
    import os
    os.makedirs(os.path.dirname(path), exist_ok=True)
    export_objs = []
    for o in objs:
        if o and o.name in bpy.context.scene.objects and o not in export_objs:
            export_objs.append(o)
    # A selected skinned mesh is useless to Enfusion without its armature.
    for o in list(export_objs):
        if o.type != 'MESH':
            continue
        for mod in o.modifiers:
            if mod.type == 'ARMATURE' and mod.object and mod.object not in export_objs:
                export_objs.append(mod.object)
    if not export_objs:
        raise ValueError(f"nothing to export to {path}")

    hidden = {o: (o.hide_get(), o.hide_viewport, o.hide_select) for o in export_objs}
    bpy.ops.object.select_all(action='DESELECT')
    for o in export_objs:
        o.hide_viewport = False
        o.hide_select = False
        o.hide_set(False)
        o.select_set(True)
    bpy.context.view_layer.objects.active = export_objs[0]
    armatures = [o for o in export_objs if o.type == 'ARMATURE']
    try:
        bpy.ops.export_scene.fbx(
            filepath=path, use_selection=True,
            object_types={'MESH', 'ARMATURE', 'EMPTY'},
            add_leaf_bones=False, use_custom_props=True,
            mesh_smooth_type='FACE', use_mesh_modifiers=True,
            use_armature_deform_only=False,
            primary_bone_axis='Y', secondary_bone_axis='X',
            axis_forward='-Z', axis_up='Y',
            # Master vehicle FBXs carry the skeleton only. Vehicle actions are
            # exported separately as TXA/ANM resources.
            bake_anim=False,
            bake_anim_use_all_actions=False,
            bake_anim_use_nla_strips=False)
    finally:
        for o, (was_hidden, was_viewport_hidden, was_select_locked) in hidden.items():
            o.hide_select = was_select_locked
            o.hide_viewport = was_viewport_hidden
            o.hide_set(was_hidden)
    return path


def _bare_copy(src, name, at_origin=False):
    """Visual-only duplicate: no vgroups, no modifiers, no parent."""
    me = src.data.copy()
    o = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(o)
    o.matrix_world = src.matrix_world.copy()
    if at_origin:
        o.location = (0, 0, 0)
    for vg in list(o.vertex_groups):
        o.vertex_groups.remove(vg)
    for m in list(o.modifiers):
        o.modifiers.remove(m)
    return o


def _export_identity_path(export_root):
    import os
    return os.path.join(bpy.path.abspath(export_root), "rvc_export_identity.json")


def _export_identity_error(export_root, asset_name):
    """Block a saved vehicle blend from exporting over another vehicle."""
    import json, os
    marker = _export_identity_path(export_root)
    if not os.path.isfile(marker):
        return ""
    try:
        identity = json.loads(open(marker, encoding="utf-8").read())
    except Exception as exc:
        return f"invalid export identity marker: {exc}"
    expected_asset = identity.get("asset_name", "")
    if expected_asset and expected_asset.casefold() != asset_name.casefold():
        return f"export directory belongs to {expected_asset}, not {asset_name}"
    expected_source_dir = identity.get("source_directory", "")
    current_source_dir = os.path.dirname(bpy.data.filepath)
    if expected_source_dir and current_source_dir:
        expected = os.path.normcase(os.path.normpath(expected_source_dir))
        current = os.path.normcase(os.path.normpath(current_source_dir))
        if expected != current:
            return "export directory is locked to a different vehicle source folder"
    return ""


def _write_export_identity(export_root, asset_name):
    import json, os
    os.makedirs(bpy.path.abspath(export_root), exist_ok=True)
    payload = {
        "asset_name": asset_name,
        "source_directory": os.path.dirname(bpy.data.filepath),
        "source_blend": bpy.data.filepath,
    }
    with open(_export_identity_path(export_root), "w", encoding="utf-8") as stream:
        json.dump(payload, stream, indent=2)
        stream.write("\n")


# --- robust slot-class name detection -----------------------------------------
# Imported / renamed vehicles rarely use the exact stock part names, so the master
# body XOB used to leak wheels and windows. These matchers keep slot-owned visuals
# out of the body by intent (any naming), while guarding genuine body parts such as
# wheel arches and fenders.
import re as _rpf_re

_WHEEL_BODY_GUARD = ("arch", "well", "house", "fender", "guard", "mudflap",
                     "mud_flap", "flare", "skirt")
_WHEEL_RE = _rpf_re.compile(r'(?:^|[_.\s])(?:wheel|wheels|tyre|tire)(?:$|[_.\s\d])', _rpf_re.I)
_GLASS_RE = _rpf_re.compile(r'(?:^|[_.\s])(?:glass|window|windows|windshield|windscreen)(?:$|[_.\s\d])', _rpf_re.I)
_LIGHT_RE = _rpf_re.compile(r'(?:^|[_.\s])(?:headlight|brakelight|taillight|tail_light|light|lights|lamp|indicator|blinker)(?:$|[_.\s\d])', _rpf_re.I)


def _is_wheel_part(name):
    low = name.lower()
    if any(g in low for g in _WHEEL_BODY_GUARD):
        return False  # wheel arch / fender / mudguard are BODY, not the tire
    return bool(_WHEEL_RE.search("_" + name + "_"))


def _is_glass_part(name):
    return bool(_GLASS_RE.search("_" + name + "_"))


def _is_light_part(name):
    return bool(_LIGHT_RE.search("_" + name + "_"))


# ----------------------------------------------------------------------------
# WHEEL SEPARATION + V-HACD MULTI-HULL CONVEX DECOMPOSITION
# ----------------------------------------------------------------------------

class RPF_OT_separate_wheels(bpy.types.Operator):
    bl_idname = "rpf.separate_wheels"
    bl_label = "Separate Wheels -> wheel_FL/FR/RL/RR"
    bl_description = ("Detect wheel meshes by name (any naming), split joined wheel sets "
                      "into loose parts, then cluster and name each by position "
                      "(front/rear by Y, left/right by X) and move it to its wheel_XX "
                      "part collection so the rig and wheel-slot export pick it up")
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        checkpoint("pre_separate_wheels")
        srcs = [o for o in context.scene.objects
                if o.type == 'MESH' and not o.name.startswith(COLLIDER_PFX)
                and _is_wheel_part(o.name)]
        if not srcs:
            self.report({'ERROR'}, "no wheel-named meshes (name them e.g. 'wheel', 'tyre')")
            return {'CANCELLED'}
        if context.mode != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')
        # split every wheel source into loose parts (a 'wheel pair' becomes singles;
        # a tyre+rim+lugs wheel becomes several pieces that re-cluster below)
        bpy.ops.object.select_all(action='DESELECT')
        for o in srcs:
            o.hide_set(False); o.hide_viewport = False; o.select_set(True)
        context.view_layer.objects.active = srcs[0]
        try:
            bpy.ops.object.mode_set(mode='EDIT')
            bpy.ops.mesh.select_all(action='SELECT')
            bpy.ops.mesh.separate(type='LOOSE')
        except RuntimeError:
            pass
        finally:
            if context.mode != 'OBJECT':
                bpy.ops.object.mode_set(mode='OBJECT')
        wheels = [o for o in context.scene.objects
                  if o.type == 'MESH' and not o.name.startswith(COLLIDER_PFX)
                  and _is_wheel_part(o.name)]
        if not wheels:
            self.report({'ERROR'}, "wheel split produced nothing")
            return {'CANCELLED'}

        def centroid(o):
            mn, mx = wbbox(o)
            return (mn + mx) * 0.5

        cents = [centroid(o) for o in wheels]
        mid = sum(cents, Vector()) / len(cents)
        # cluster every loose piece into one of four quadrants around the centre
        groups = {"FL": [], "FR": [], "RL": [], "RR": []}
        for o, c in zip(wheels, cents):
            tag = ("F" if c.y >= mid.y else "R") + ("L" if c.x <= mid.x else "R")
            groups[tag].append(o)
        made = []
        for tag, objs in groups.items():
            if not objs:
                continue
            bpy.ops.object.select_all(action='DESELECT')
            for o in objs:
                o.select_set(True)
            context.view_layer.objects.active = objs[0]
            if len(objs) > 1:
                bpy.ops.object.join()
            wheel = context.view_layer.objects.active
            wheel.name = f"wheel_{tag}"
            move_to_coll(wheel, f"wheel_{tag}")
            made.append(wheel.name)
        self.report({'INFO'}, "wheels -> " + ", ".join(sorted(made))
                    + "  (front=+Y, left=-X; flip parts if your forward axis differs)")
        return {'FINISHED'}


def _blender_python_exe():
    import os
    import sys
    for cand in (os.path.join(sys.prefix, "bin", "python.exe"),
                 os.path.join(sys.prefix, "bin", "python3.exe"),
                 os.path.join(sys.prefix, "bin", "python"),
                 os.path.join(sys.prefix, "bin", "python3"),
                 sys.executable):
        if cand and os.path.isfile(cand):
            return cand
    return sys.executable


def _world_tris(obj):
    """Evaluated world-space vertices and triangle indices for decomposition."""
    deps = bpy.context.evaluated_depsgraph_get()
    ev = obj.evaluated_get(deps)
    me = ev.to_mesh()
    mw = obj.matrix_world
    verts = [tuple(mw @ v.co) for v in me.vertices]
    me.calc_loop_triangles()
    faces = [(t.vertices[0], t.vertices[1], t.vertices[2]) for t in me.loop_triangles]
    ev.to_mesh_clear()
    return verts, faces


def _reduce_mesh(verts, faces, target_tris):
    """Decimate a (verts, faces) soup to ~target_tris so decomposition is fast and
    Blender does not lock up on a dense body. Collision/LOD geo never needs full res."""
    if target_tris <= 0 or len(faces) <= target_tris:
        return verts, faces
    me = bpy.data.meshes.new("_rpf_vhacd_tmp")
    try:
        me.from_pydata([list(v) for v in verts], [], [list(f) for f in faces])
        me.update()
    except Exception:
        bpy.data.meshes.remove(me)
        return verts, faces
    obj = bpy.data.objects.new("_rpf_vhacd_tmp", me)
    bpy.context.scene.collection.objects.link(obj)
    mod = obj.modifiers.new("d", 'DECIMATE')
    mod.ratio = max(0.02, min(1.0, target_tris / float(len(faces))))
    deps = bpy.context.evaluated_depsgraph_get()
    ev = obj.evaluated_get(deps)
    em = ev.to_mesh()
    nv = [tuple(v.co) for v in em.vertices]
    em.calc_loop_triangles()
    nf = [(t.vertices[0], t.vertices[1], t.vertices[2]) for t in em.loop_triangles]
    ev.to_mesh_clear()
    bpy.data.objects.remove(obj, do_unlink=True)
    bpy.data.meshes.remove(me)
    if len(nv) < 4 or not nf:
        return verts, faces
    return nv, nf


def _vhacd_coacd(verts, faces, threshold):
    """Convex decomposition via the CoACD python module. Returns hull point-lists."""
    try:
        import numpy as np
        import coacd
    except Exception:
        return None
    try:
        mesh = coacd.Mesh(np.asarray(verts, dtype="float64"),
                          np.asarray(faces, dtype="int32"))
        try:
            parts = coacd.run_coacd(mesh, threshold=threshold)
        except TypeError:
            parts = coacd.run_coacd(mesh)
    except Exception:
        return None
    hulls = []
    for part in parts:
        v = part[0]
        hulls.append([(float(p[0]), float(p[1]), float(p[2])) for p in v])
    return hulls or None


def _vhacd_exe(verts, faces, exe):
    """Convex decomposition via an external V-HACD executable (v4 TestVHACD)."""
    import os
    import subprocess
    import tempfile
    if not exe or not os.path.isfile(exe):
        return None
    work = tempfile.mkdtemp(prefix="rpf_vhacd_")
    inp = os.path.join(work, "input.obj")
    try:
        with open(inp, "w", encoding="utf-8") as stream:
            for v in verts:
                stream.write("v %.6f %.6f %.6f\n" % (v[0], v[1], v[2]))
            for a, b, c in faces:
                stream.write("f %d %d %d\n" % (a + 1, b + 1, c + 1))
        subprocess.run([exe, inp], cwd=work, capture_output=True,
                       text=True, timeout=600)
    except Exception:
        return None
    out = next((os.path.join(work, n) for n in
                ("decomp.obj", "input_decomp.obj", "output.obj")
                if os.path.isfile(os.path.join(work, n))), None)
    if not out:
        return None
    allv = []
    hulls = []
    cur = None
    try:
        with open(out, encoding="utf-8", errors="ignore") as stream:
            for line in stream:
                if line.startswith("v "):
                    parts = line.split()
                    allv.append((float(parts[1]), float(parts[2]), float(parts[3])))
                elif line[:2] in ("o ", "g "):
                    cur = set()
                    hulls.append(cur)
                elif line.startswith("f ") and cur is not None:
                    for tok in line.split()[1:]:
                        i = int(tok.split("/")[0])
                        cur.add(i - 1 if i > 0 else len(allv) + i)
    except Exception:
        return None
    pts = [[allv[i] for i in sorted(g) if 0 <= i < len(allv)] for g in hulls if g]
    return pts or None


def _capped_hull_obj(name, points, max_faces):
    """Build a single convex hull object from points, reduced to <= max_faces."""
    # Decomposition backends hand back plain tuples; _sample_hull_points expects
    # Vectors (.x/.y/.z), so normalise first.
    points = [p if isinstance(p, Vector) else Vector(p) for p in points]
    points = _reject_outliers(points)
    best = None
    for resolution in (12, 10, 8, 6, 5, 4, 3, 2, 1):
        mesh = _convex_mesh_from_points(name, _sample_hull_points(points, resolution))
        if mesh is None:
            continue
        if best:
            bpy.data.meshes.remove(best)
        best = mesh
        if len(mesh.polygons) <= max_faces:
            break
    if best is None:
        return None
    if len(best.polygons) > max_faces:
        bpy.data.meshes.remove(best)
        return None
    return bpy.data.objects.new(name, best)


def _collision_for_part(part, index, decimate_target, threshold, max_hulls, max_faces, exe):
    """Grouped collision: merge a whole part/category (its render pieces, minus
    glass/lights/wheels) into one mass, then convex-decompose THAT. Produces far fewer,
    cleaner UCX hulls than per-sub-object. Returns (made_objects, next_index)."""
    pieces = [o for o in part_objects(part) if o.type == 'MESH']
    if not pieces:
        pieces = [o for o in bpy.data.objects
                  if o.type == 'MESH' and not o.name.startswith(COLLIDER_PFX)
                  and (o.name == part or o.name.startswith(part + "."))]
    pieces = [o for o in pieces if not _is_glass_part(o.name)
              and not _is_light_part(o.name) and not _is_wheel_part(o.name)]
    if not pieces:
        return [], index
    copies = []
    for p in pieces:
        c = bpy.data.objects.new(f"_coltmp_{p.name}", p.data.copy())
        bpy.context.scene.collection.objects.link(c)
        c.matrix_world = p.matrix_world.copy()
        for vg in list(c.vertex_groups):
            c.vertex_groups.remove(vg)
        for m in list(c.modifiers):
            c.modifiers.remove(m)
        copies.append(c)
    bpy.ops.object.select_all(action='DESELECT')
    for c in copies:
        c.select_set(True)
    bpy.context.view_layer.objects.active = copies[0]
    if len(copies) > 1:
        bpy.ops.object.join()
    merged = bpy.context.view_layer.objects.active
    verts, faces = _world_tris(merged)
    bpy.data.objects.remove(merged, do_unlink=True)
    if len(verts) < 4 or not faces:
        return [], index
    verts, faces = _reduce_mesh(verts, faces, decimate_target)
    print(f"RPF COLLISION: {part} ({len(pieces)} pieces) -> decompose {len(faces)} tris",
          flush=True)
    hulls = _vhacd_coacd(verts, faces, threshold) or _vhacd_exe(verts, faces, exe)
    token = _safe_name_token(part)
    made = []
    if not hulls:
        obj = _capped_hull_obj(f"UCX_MainCol_{index:02d}_{token}", verts, max_faces)
        if obj:
            obj["rpf_ucx_source"] = part
            _place_ebt_collider(obj, "Vehicle")
            made.append(obj)
            index += 1
        return made, index
    for hi, pts in enumerate(hulls[:max_hulls]):
        if len(pts) < 4:
            continue
        obj = _capped_hull_obj(f"UCX_MainCol_{index:02d}_{token}_{hi:02d}", pts, max_faces)
        if obj is None:
            continue
        obj["rpf_ucx_source"] = part
        obj["rpf_ucx_face_cap"] = max_faces
        _place_ebt_collider(obj, "Vehicle")
        made.append(obj)
        index += 1
    return made, index


class RPF_OT_vhacd_selected(bpy.types.Operator):
    bl_idname = "rpf.vhacd_selected"
    bl_label = "V-HACD -> Multi-Hull UCX"
    bl_description = ("Convex-decompose each selected render mesh into multiple "
                      "individually convex UCX_MainCol hulls (CoACD if installed, else "
                      "an external V-HACD exe, else a single convex fallback). Each hull "
                      "is rebuilt convex and capped to the face limit")
    bl_options = {'REGISTER', 'UNDO'}

    max_hulls: bpy.props.IntProperty(name="Max hulls / part", default=16, min=1, max=64)
    max_faces: bpy.props.IntProperty(name="Max faces / hull", default=200, min=12, max=200)
    threshold: bpy.props.FloatProperty(name="Concavity", default=0.05, min=0.01, max=1.0,
                                       description="CoACD concavity threshold (lower = more hulls)")
    decimate_target: bpy.props.IntProperty(
        name="Decimate input to", default=4000, min=0, max=80000,
        description="Reduce each part to ~this many tris before decomposition so Blender "
                    "doesn't freeze on dense meshes (0 = use full resolution)")
    replace_generated: bpy.props.BoolProperty(name="Replace previous hulls", default=True)

    def execute(self, context):
        sources = [o for o in context.selected_objects
                   if o.type == 'MESH' and not o.name.startswith(COLLIDER_PFX)]
        if not sources:
            self.report({'ERROR'}, "select one or more render-part meshes")
            return {'CANCELLED'}
        checkpoint("pre_vhacd")
        if self.replace_generated:
            for obj in list(bpy.data.objects):
                if obj.get("rpf_ucx_source"):
                    bpy.data.objects.remove(obj, do_unlink=True)
        exe = context.scene.rpf_vhacd_exe
        made = []
        backend = "none"
        index = _next_main_col_index()
        for i, src in enumerate(sources):
            print(f"RPF V-HACD {i + 1}/{len(sources)}: {src.name} ...", flush=True)
            verts, faces = _world_tris(src)
            if len(verts) < 4 or not faces:
                continue
            verts, faces = _reduce_mesh(verts, faces, self.decimate_target)
            hulls = _vhacd_coacd(verts, faces, self.threshold)
            if hulls is not None:
                backend = "coacd"
            else:
                hulls = _vhacd_exe(verts, faces, exe)
                if hulls is not None:
                    backend = "vhacd-exe"
            token = _safe_name_token(src.name)
            if not hulls:
                # graceful fallback: single guaranteed-convex hull
                hull = _part_convex_hull(src, f"UCX_MainCol_{index:02d}_{token}", self.max_faces)
                if hull:
                    made.append(hull)
                    index += 1
                if backend == "none":
                    backend = "convex-fallback"
                continue
            for hi, pts in enumerate(hulls[:self.max_hulls]):
                if len(pts) < 4:
                    continue
                name = f"UCX_MainCol_{index:02d}_{token}_{hi:02d}"
                obj = _capped_hull_obj(name, pts, self.max_faces)
                if obj is None:
                    continue
                obj["rpf_ucx_source"] = src.name
                obj["rpf_ucx_face_cap"] = self.max_faces
                _place_ebt_collider(obj, "Vehicle")
                made.append(obj)
                index += 1
        bpy.ops.object.select_all(action='DESELECT')
        for obj in made:
            obj.select_set(True)
        if made:
            context.view_layer.objects.active = made[0]
        self.report({'INFO'} if made else {'ERROR'},
                    f"{backend}: {len(made)} convex UCX hulls (<= {self.max_faces}f)")
        return {'FINISHED'} if made else {'CANCELLED'}


class RPF_OT_install_vhacd_deps(bpy.types.Operator):
    bl_idname = "rpf.install_vhacd_deps"
    bl_label = "Install V-HACD deps (CoACD)"
    bl_description = ("Install CoACD + numpy into Blender's bundled Python so V-HACD "
                      "multi-hull decomposition works without an external exe. Run once; "
                      "restart Blender if the import check reports a failure")
    bl_options = {'REGISTER'}

    def execute(self, context):
        import subprocess
        py = _blender_python_exe()
        try:
            subprocess.run([py, "-m", "ensurepip", "--upgrade"],
                           capture_output=True, text=True)
            result = subprocess.run([py, "-m", "pip", "install", "--upgrade", "coacd", "numpy"],
                                    capture_output=True, text=True)
        except Exception as exc:
            self.report({'ERROR'}, f"pip launch failed: {exc}")
            return {'CANCELLED'}
        if result.returncode != 0:
            self.report({'ERROR'}, "pip failed: " + (result.stderr or result.stdout)[-260:])
            return {'CANCELLED'}
        try:
            import importlib
            importlib.invalidate_caches()
            import coacd  # noqa: F401
        except Exception as exc:
            self.report({'WARNING'}, f"installed; restart Blender to load CoACD ({exc})")
            return {'FINISHED'}
        self.report({'INFO'}, "CoACD installed and importable")
        return {'FINISHED'}


COLLISION_PFX = ("UCX_", "UBX_", "UCL_", "UTM_", "USP_", "UCS_")


def _collision_objects():
    return [o for o in bpy.data.objects
            if o.type == 'MESH' and o.name.startswith(COLLISION_PFX)]


def _collider_is_bad(o):
    if o.name.rsplit(".", 1)[-1].isdigit():
        return True
    if any(abs(s - 1.0) > 1e-5 for s in o.scale):
        return True
    if not o.data.polygons:
        return True
    if o.name.startswith(("UCX_MainCol_", "UBX_MainCol_")):
        if len(o.data.polygons) > 200 or not _mesh_is_convex(o):
            return True
    return False


class RPF_OT_cleanup_colliders(bpy.types.Operator):
    bl_idname = "rpf.cleanup_colliders"
    bl_label = "Tidy / Remove Colliders"
    bl_description = ("Remove generated, invalid, or all collision objects "
                      "(UCX/UBX/UCL/UTM/USP/UCS) and prune empty collider collections. "
                      "Door hinges and render meshes are never touched")
    bl_options = {'REGISTER', 'UNDO'}

    mode: bpy.props.EnumProperty(
        name="Remove",
        default='GENERATED',
        items=[('GENERATED', "Generated", "Only colliders this tool created (tagged rpf_ucx_source)"),
               ('INVALID', "Invalid only", "Non-convex, over-cap, unapplied-scale, numeric-suffix or empty"),
               ('ALL', "All collision", "Every UCX/UBX/UCL/UTM/USP/UCS collider")])

    def execute(self, context):
        checkpoint("pre_cleanup_colliders")
        removed = []
        for o in list(_collision_objects()):
            if self.mode == 'GENERATED' and not o.get("rpf_ucx_source"):
                continue
            if self.mode == 'INVALID' and not _collider_is_bad(o):
                continue
            removed.append(o.name)
            bpy.data.objects.remove(o, do_unlink=True)
        pruned = 0
        root = bpy.data.collections.get("Colliders")
        if root:
            for child in list(root.children):
                if not child.objects and not child.children:
                    bpy.data.collections.remove(child)
                    pruned += 1
            if not root.objects and not root.children:
                bpy.data.collections.remove(root)
                pruned += 1
        self.report({'INFO'}, f"removed {len(removed)} colliders, pruned {pruned} collections")
        print("RPF CLEANUP:", removed)
        return {'FINISHED'}


class RPF_OT_fix_ucx(bpy.types.Operator):
    bl_idname = "rpf.fix_ucx"
    bl_label = "Fix UCX Hulls"
    bl_description = ("Repair what Validate reports: apply stray scale, strip Blender numeric "
                      "suffixes, re-assign the Vehicle preset/collection, and rebuild any "
                      "non-convex or over-cap hull as a guaranteed-convex hull (removed only "
                      "if it cannot be rebuilt)")
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        checkpoint("pre_fix_ucx")
        if context.mode != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')
        hulls = [o for o in bpy.data.objects
                 if o.type == 'MESH' and o.name.startswith(("UCX_MainCol_", "UBX_MainCol_"))]
        fixed, removed = [], []
        for o in hulls:
            if any(abs(s - 1.0) > 1e-5 for s in o.scale):
                bpy.ops.object.select_all(action='DESELECT')
                o.select_set(True)
                context.view_layer.objects.active = o
                bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)
            if o.name.rsplit(".", 1)[-1].isdigit():
                o.name = o.name.rsplit(".", 1)[0]
            if (not o.data.polygons) or (not _mesh_is_convex(o)) or len(o.data.polygons) > 200:
                pts = [o.matrix_world @ v.co for v in o.data.vertices]
                rebuilt = _capped_hull_obj(o.name + "_fix", pts, 200)
                if rebuilt is None:
                    removed.append(o.name)
                    bpy.data.objects.remove(o, do_unlink=True)
                    continue
                name, src = o.name, o.get("rpf_ucx_source")
                bpy.data.objects.remove(o, do_unlink=True)
                rebuilt.name = name
                if src:
                    rebuilt["rpf_ucx_source"] = src
                _place_ebt_collider(rebuilt, "Vehicle")
                fixed.append(rebuilt.name)
                continue
            _place_ebt_collider(o, "Vehicle")
            fixed.append(o.name)
        self.report({'INFO'}, f"fixed {len(fixed)} hulls, removed {len(removed)} unrepairable")
        return {'FINISHED'}


class RPF_OT_build_all_physics(bpy.types.Operator):
    bl_idname = "rpf.build_all_physics"
    bl_label = "1-Click: Clean + Collision + FireGeo + LOD"
    bl_description = ("Run the whole physics/geo pass in order: tidy old generated colliders, "
                      "build collision (V-HACD multi-hull if available, else perceptive convex), "
                      "build FireGeo, bake LODs, then validate")
    bl_options = {'REGISTER', 'UNDO'}

    use_vhacd: bpy.props.BoolProperty(name="Use V-HACD", default=True)
    do_lod: bpy.props.BoolProperty(name="Bake LOD", default=True)

    def execute(self, context):
        steps = []
        bpy.ops.rpf.cleanup_colliders(mode='GENERATED')
        steps.append("cleaned")
        have = False
        if self.use_vhacd:
            try:
                import coacd  # noqa: F401
                have = True
            except Exception:
                have = bool(context.scene.rpf_vhacd_exe)
        if have:
            # GROUPED collision: merge each category into one mass, decompose THAT.
            # Body shell + one hull-set per door = far fewer, cleaner hulls than
            # decomposing 80+ tiny sub-material parts.
            cats = ["exterior", "door_FL", "door_FR", "door_RL", "door_RR", "door_trunk"]
            index = _next_main_col_index()
            exe = context.scene.rpf_vhacd_exe
            dec = context.scene.rpf_ucx_decimate
            thr = context.scene.rpf_ucx_concavity
            mh = context.scene.rpf_ucx_max_hulls
            total = []
            for cat in cats:
                made, index = _collision_for_part(cat, index, dec, thr, mh, 200, exe)
                total += made
            steps.append(f"collision:grouped({len(total)}h)")
        else:
            try:
                bpy.ops.rpf.build_colliders()
                steps.append("collision:perceptive")
            except Exception as exc:
                steps.append(f"collision-err({exc})")
        for op_name, idname in (("firegeo", "build_firegeo"),
                                ("lod", "bake_lod") if self.do_lod else (None, None)):
            if op_name is None:
                continue
            try:
                getattr(bpy.ops.rpf, idname)()
                steps.append(op_name)
            except Exception as exc:
                steps.append(f"{op_name}-skip")
        try:
            bpy.ops.rpf.fix_ucx()
            steps.append("fixed")
        except Exception:
            pass
        try:
            bpy.ops.rpf.validate_ucx()
        except Exception:
            pass
        self.report({'INFO'}, " | ".join(steps))
        print("RPF BUILD-ALL:", steps)
        return {'FINISHED'}


class RPF_OT_export_enfusion(bpy.types.Operator):
    bl_idname = "rpf.export_enfusion"
    bl_label = "5. Export Enfusion Set"
    bl_description = ("Slot-architecture export: body FBX (no wheels/glass/lights) + "
                      "separate wheel, glass and light-group FBXs for prefab slots")
    bl_options = {'REGISTER'}

    def execute(self, context):
        import os, bmesh as _bm
        done = []
        EXPORT_ROOT = context.scene.rpf_export_root
        ASSET_NAME = context.scene.rpf_asset_name
        if not EXPORT_ROOT:
            self.report({'ERROR'}, "set an Export Directory first")
            return {'CANCELLED'}
        identity_error = _export_identity_error(EXPORT_ROOT, ASSET_NAME)
        if identity_error:
            self.report({'ERROR'}, identity_error)
            return {'CANCELLED'}
        bpy.ops.rpf.doors_close()

        arm = _get_armature()
        if not arm or not arm.data.bones:
            self.report({'ERROR'}, "no vehicle armature/bones - run Build Bones first")
            return {'CANCELLED'}

        # Export must never silently mutate a finalized rig. Repair bindings
        # deliberately with "Skin All Parts", then export only after validation.
        binding_issues = _rig_binding_issues(arm)
        if binding_issues:
            self.report({'ERROR'}, "invalid rig bindings - run Skin All Parts: "
                        + "; ".join(binding_issues[:4]))
            return {'CANCELLED'}

        def include_master(o):
            name = o.name
            if o.type not in ('MESH', 'ARMATURE', 'EMPTY'):
                return False
            if name.startswith(("WT_", "RPF_HINGE_")):
                return False
            # Collision / FireGeo classes are routed by their prefix FIRST, so a
            # collider that happens to be named like a wheel/glass still classifies
            # correctly instead of being dropped as a slot visual.
            if name.startswith("UTM_Glass"):
                return context.scene.rpf_export_glass_firegeo
            if name.startswith(("UTM_FG_", "UCX_FG_")):
                return context.scene.rpf_export_firegeo
            if name.startswith(("UCL_", "UCX_")):
                return context.scene.rpf_export_vehicle_collision
            if o.type == 'ARMATURE':
                return context.scene.rpf_export_armature
            if o.type == 'EMPTY':
                return context.scene.rpf_export_memory
            # Slot-owned VISUALS never belong in the master body XOB. Name-robust
            # detection keeps wheels / windows / light lenses out of the body even
            # when the vehicle uses non-stock part names (the export-tickbox bug).
            if _is_wheel_part(name):
                return False
            if _is_light_part(name):
                return False
            if _is_glass_part(name):
                return context.scene.rpf_export_visual_glass
            return context.scene.rpf_export_render

        # ---- 1) master: selected render/skeleton/memory/collision classes.
        body = [o for o in context.scene.objects if include_master(o)]
        done.append(_fbx_export(os.path.join(EXPORT_ROOT, f"{ASSET_NAME}.fbx"), body))

        # ---- 2) wheel: single wheel at origin + stock-named colliders
        #      (matches SampleCar_01_wheel.xob: UCL_VC_wheel00 + UTM_FG_Wheel_L01)
        wheel_src = bpy.data.objects.get("wheel_FL") or next(
            (o for o in context.scene.objects
             if o.type == 'MESH' and _is_wheel_part(o.name)), None)
        if wheel_src and context.scene.rpf_export_wheel_slot:
            w = _bare_copy(wheel_src, "wheel", at_origin=True)

            def _cyl(name, radius, depth, segs):
                me = bpy.data.meshes.new(name)
                bm = _bm.new()
                _bm.ops.create_cone(bm, cap_ends=True, segments=segs,
                                    radius1=radius, radius2=radius, depth=depth)
                for v in bm.verts:   # cylinder along Z -> rotate onto X (wheel axis)
                    v.co = Vector((v.co.z, v.co.y, -v.co.x))
                bm.to_mesh(me); bm.free()
                o = bpy.data.objects.new(name, me)
                bpy.context.scene.collection.objects.link(o)
                return o

            ucl = _cyl("UCL_VC_wheel00", 0.39, 0.25, 16)     # vehicle collision
            fgw = _cyl("UTM_FG_Wheel_L01", 0.397, 0.25, 24)  # fire geometry
            done.append(_fbx_export(os.path.join(EXPORT_ROOT, "VehParts", f"{ASSET_NAME}_Wheel.fbx"), [w, ucl, fgw]))
            bpy.data.objects.remove(w); bpy.data.objects.remove(ucl); bpy.data.objects.remove(fgw)
        elif context.scene.rpf_export_wheel_slot:
            self.report({'WARNING'}, "wheel_FL not found - skipped wheel FBX")
            print("ENFUSION EXPORT: wheel_FL not found; skipped wheel FBX")

        # ---- 3) glass: door windows + split body glass (F/R/quarters)
        #      door/trunk panes get a 'snap_glass' empty at the door hinge:
        #      base-prefab slots use PivotID v_door_xx + ChildPivotID snap_glass
        GLASS_DOOR = {"door_FL_window": ("FL", "door_FL"), "door_FR_window": ("FR", "door_FR"),
                      "door_RL_window": ("RL", "door_RL"), "door_RR_window": ("RR", "door_RR"),
                      "door_trunk_window": ("R", "door_trunk"),
                      "glass_windshield": ("F", None)}
        for dn, (tag, door) in GLASS_DOOR.items() if context.scene.rpf_export_dst_glass else ():
            src = bpy.data.objects.get(dn)
            if not src:
                continue
            g = _bare_copy(src, f"Glass_{tag}")
            extras = [g]
            hinge = door_hinge(door) if door else None
            if hinge:
                snap = bpy.data.objects.new("snap_glass", None)
                snap.empty_display_type = 'PLAIN_AXES'
                snap.empty_display_size = 0.1
                snap.location = hinge
                bpy.context.scene.collection.objects.link(snap)
                extras.append(snap)
            done.append(_fbx_export(os.path.join(EXPORT_ROOT, "Dst", f"{ASSET_NAME}_Glass_{tag}.fbx"), extras))
            for e in extras:
                bpy.data.objects.remove(e)
        # quarters + partition glass stay in the body (no stock slots for them);
        # standard light lenses stay in the body — base-prefab VehicleLight
        # components at v_light_* pivots provide the actual illumination

        self.report({'INFO'}, f"exported {len(done)} FBX files to {EXPORT_ROOT}")
        _write_export_identity(EXPORT_ROOT, ASSET_NAME)
        print("ENFUSION EXPORT SET:")
        for d in done:
            print("  ", d)
        return {'FINISHED'}


# ----------------------------------------------------------------------------
# 7) PER-LAMP EMERGENCY LIGHT EXPORT
#    Each lamp = own FBX centered on its v_light_em_* socket, so a slot prefab
#    (VehicleEmissiveSurface_Base + ParametricMaterialInstanceComponent + flash
#    script) drops exactly into place at PivotID v_light_em_*.
# ----------------------------------------------------------------------------

# socket -> (lamp tag, island gather radius, split_by_x)
# split_by_x: two-color bars become _L and _R lamps — Arma emission is
# whole-mesh/one-material, so red and blue halves MUST be separate prefabs
# to flash independently (.Age confirmed; stock has no per-material emissive)
EM_LAMPS = {
    "v_light_em_grille_L":   ("Grille_L",   0.20, False),
    "v_light_em_grille_R":   ("Grille_R",   0.20, False),
    "v_light_em_bumper_L":   ("Bumper_L",   0.30, False),
    "v_light_em_bumper_R":   ("Bumper_R",   0.30, False),
    "v_light_em_tailgate_L": ("Tailgate_L", 0.22, False),
    "v_light_em_tailgate_R": ("Tailgate_R", 0.22, False),
    "v_light_em_rbumper_L":  ("RBumper_L",  0.30, False),
    "v_light_em_rbumper_R":  ("RBumper_R",  0.30, False),
    "v_light_em_rear_bar":   ("RearBar",    0.75, True),
    "v_light_em_roofbar":    ("Roofbar",    1.30, True),
}


def _em_side_material(side):
    """One material per vehicle side -> one .emat per side after import;
    set its Emissive color (red/blue) once in Workbench."""
    name = f"Explorer_EM_{side}"
    mat = bpy.data.materials.get(name)
    if not mat:
        mat = bpy.data.materials.new(name)
        mat.use_nodes = True
        bsdf = mat.node_tree.nodes.get("Principled BSDF")
        if bsdf:
            col = (0.0, 0.1, 1.0, 1.0) if side == "L" else (1.0, 0.0, 0.0, 1.0)
            bsdf.inputs["Base Color"].default_value = col
            if "Emission Color" in bsdf.inputs:
                bsdf.inputs["Emission Color"].default_value = col
                bsdf.inputs["Emission Strength"].default_value = 2.0
    return mat


class RPF_OT_export_em_lamps(bpy.types.Operator):
    bl_idname = "rpf.export_em_lamps"
    bl_label = "6. Export Emergency Lamps"
    bl_description = ("Split lights_emergency into per-socket lamp meshes and export "
                      "each as its own FBX (origin at the socket) for slot light prefabs")
    bl_options = {'REGISTER'}

    def execute(self, context):
        import os, bmesh as _bm
        EXPORT_ROOT = context.scene.rpf_export_root
        ASSET_NAME = context.scene.rpf_asset_name
        src = bpy.data.objects.get("lights_emergency")
        if not src:
            self.report({'ERROR'}, "lights_emergency object not found")
            return {'CANCELLED'}
        mw = src.matrix_world
        me = src.data
        # vertex islands
        parent = list(range(len(me.vertices)))
        def find(a):
            while parent[a] != a:
                parent[a] = parent[parent[a]]; a = parent[a]
            return a
        for e in me.edges:
            ra, rb = find(e.vertices[0]), find(e.vertices[1])
            if ra != rb:
                parent[rb] = ra
        groups = {}
        for i in range(len(me.vertices)):
            groups.setdefault(find(i), []).append(i)
        centers = {}
        for root, vids in groups.items():
            pts = [mw @ me.vertices[i].co for i in vids]
            mn = Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
            mx = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
            centers[root] = (mn + mx) / 2

        def _export_lamp(tag, side, roots, sp):
            keep_v = set()
            for r in roots:
                keep_v.update(groups[r])
            lamp = _bare_copy(src, f"EM_{tag}")
            bmm = _bm.new(); bmm.from_mesh(lamp.data)
            bmm.verts.ensure_lookup_table()
            _bm.ops.delete(bmm, geom=[v for v in bmm.verts if v.index not in keep_v],
                           context='VERTS')
            bmm.to_mesh(lamp.data); bmm.free()
            # single side-material so each lamp imports with its own colorable emat
            lamp.data.materials.clear()
            lamp.data.materials.append(_em_side_material(side))
            # origin at the socket: shift world so socket -> (0,0,0)
            lamp.matrix_world = Matrix.Translation(-sp) @ lamp.matrix_world
            p = _fbx_export(
                os.path.join(EXPORT_ROOT, "Lights", "Lamps", f"{ASSET_NAME}_EM_{tag}.fbx"),
                [lamp])
            bpy.data.objects.remove(lamp)
            return p

        done, unclaimed = [], set(groups.keys())
        for socket_name, (tag, radius, split_x) in EM_LAMPS.items():
            sock = bpy.data.objects.get(socket_name)
            if not sock:
                continue
            sp = sock.matrix_world.translation
            roots = [r for r in unclaimed if (centers[r] - sp).length < radius]
            if not roots:
                continue
            unclaimed -= set(roots)
            if split_x:
                left = [r for r in roots if centers[r].x < sp.x]
                right = [r for r in roots if centers[r].x >= sp.x]
                if left:
                    done.append(_export_lamp(f"{tag}_L", "L", left, sp))
                if right:
                    done.append(_export_lamp(f"{tag}_R", "R", right, sp))
            else:
                side = "L" if tag.endswith("_L") else "R"
                done.append(_export_lamp(tag, side, roots, sp))
        print("EM LAMP EXPORTS:")
        for d in done:
            print("  ", d)
        print("unclaimed strobe islands left in lights_emergency:", len(unclaimed))
        self.report({'INFO'}, f"exported {len(done)} lamp FBXs; {len(unclaimed)} islands unclaimed")
        return {'FINISHED'}


# ----------------------------------------------------------------------------
# 8) RIG — one-click armature + skinning (SampleCar conventions, all +Y roll 0)
# ----------------------------------------------------------------------------

BONE_TAIL = 0.12
STEER_DIR = Vector((0.0, 0.84, -0.54))   # SampleCar_01 column axis

# wheel part -> (wheel bone, suspension bone, rotator bone or None, axle bone)
WHEEL_BONES = {"wheel_FL": ("v_wheel_l01", "v_suspension_l01", "v_rotator_l01", "v_axle_01"),
               "wheel_FR": ("v_wheel_r01", "v_suspension_r01", "v_rotator_r01", "v_axle_01"),
               "wheel_RL": ("v_wheel_l02", "v_suspension_l02", None, "v_axle_02"),
               "wheel_RR": ("v_wheel_r02", "v_suspension_r02", None, "v_axle_02")}

COLLIDER_PFX = ("UCX_", "UBX_", "UCL_", "UTM_", "USP_", "UCS_", "RPF_HINGE_")


def _obj_origin(name):
    o = bpy.data.objects.get(name)
    return o.matrix_world.translation.copy() if o else None


def _fuzzy_center(token):
    """Bbox center of the first mesh whose name contains the token (any case)."""
    for o in all_meshes():
        if token in o.name.lower() and not o.name.startswith(COLLIDER_PFX):
            a, b = wbbox(o)
            return (a + b) / 2
    return None


def _get_armature():
    o = bpy.data.objects.get("Armature")
    if o and o.type == 'ARMATURE':
        return o
    for o in bpy.data.objects:
        if o.type == 'ARMATURE':
            return o
    return None


class RPF_OT_build_rig(bpy.types.Operator):
    bl_idname = "rpf.build_rig"
    bl_label = "Build Bones (auto-place)"
    bl_description = ("One click: SampleCar-convention armature with every bone at its "
                      "measured spot — v_root/v_body, axles+suspension+rotators+wheels "
                      "from wheel origins, door bones at hinges, v_trunk, steering "
                      "along column, pedals, handbrake. ALL bones +Y forward roll 0. "
                      "Run AFTER Finalize (part origins must be set)")
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        wheels = {n: _obj_origin(n) for n in WHEEL_BONES}
        wheels = {n: p for n, p in wheels.items() if p is not None}
        est = ""
        if len(wheels) < 4:
            # no wheel meshes (e.g. body-only blend): estimate axle positions
            # from the vehicle bbox + the wheelbase/radius settings
            meshes = [o for o in all_meshes() if not o.name.startswith(COLLIDER_PFX)]
            if not meshes:
                self.report({'ERROR'}, "no wheels and no meshes to estimate from")
                return {'CANCELLED'}
            bmn = Vector((1e9,) * 3); bmx = Vector((-1e9,) * 3)
            for o in meshes:
                a, b = wbbox(o)
                bmn.x = min(bmn.x, a.x); bmn.y = min(bmn.y, a.y); bmn.z = min(bmn.z, a.z)
                bmx.x = max(bmx.x, b.x); bmx.y = max(bmx.y, b.y); bmx.z = max(bmx.z, b.z)
            wb = context.scene.rpf_wheelbase
            r = context.scene.rpf_wheel_radius
            cy = (bmn.y + bmx.y) / 2
            ht = max((bmx.x - bmn.x) / 2 - 0.30, 0.55)   # half-track, minus mirrors
            wheels = {"wheel_FL": Vector((-ht, cy + wb / 2, r)),
                      "wheel_FR": Vector((ht, cy + wb / 2, r)),
                      "wheel_RL": Vector((-ht, cy - wb / 2, r)),
                      "wheel_RR": Vector((ht, cy - wb / 2, r))}
            est = " — wheel/axle bones ESTIMATED (set Wheelbase + Wheel radius in Setup, nudge in Edit Mode)"
        cp = checkpoint("prerig")
        bpy.ops.rpf.doors_close()

        old = _get_armature()
        if old:
            bpy.data.objects.remove(old)
        arm = bpy.data.armatures.new("Armature")
        ob = bpy.data.objects.new("Armature", arm)
        context.scene.collection.objects.link(ob)
        bpy.ops.object.select_all(action='DESELECT')
        ob.select_set(True)
        context.view_layer.objects.active = ob
        bpy.ops.object.mode_set(mode='EDIT')
        eb = arm.edit_bones

        def bone(name, head, parent=None, axis=None):
            b = eb.new(name)
            b.head = Vector(head)
            d = axis.normalized() if axis else Vector((0, 1, 0))
            b.tail = Vector(head) + d * BONE_TAIL
            b.roll = 0.0
            if parent:
                b.parent = eb[parent]
            return b

        zw = sum(p.z for p in wheels.values()) / len(wheels)
        y_f = (wheels["wheel_FL"].y + wheels["wheel_FR"].y) / 2
        y_r = (wheels["wheel_RL"].y + wheels["wheel_RR"].y) / 2

        bone("v_root", (0, 0, 0))
        bone("v_body", (0, 0, zw), "v_root")
        bone("v_axle_01", (0, y_f, zw), "v_body")
        bone("v_axle_02", (0, y_r, zw), "v_body")
        for wn, (wbone, sbone, rbone, abone) in WHEEL_BONES.items():
            p = wheels[wn]
            bone(sbone, (p.x * 0.85, p.y, p.z), abone)
            par = sbone
            if rbone:                      # front wheels steer through the rotator
                bone(rbone, tuple(p), sbone)
                par = rbone
            bone(wbone, tuple(p), par)
        for dn, bn in DOOR_BONE.items():
            h = _obj_origin(dn) or door_hinge(dn)
            if h is not None:
                bone(bn, tuple(h), "v_body")
        s = _obj_origin("Steering_Wheel")
        if s is None:
            s = _fuzzy_center("steering")
        if s is not None:
            bone("v_steering_wheel", tuple(s), "v_body", axis=STEER_DIR)
        pb = _obj_origin("Pedal_Brake") or _fuzzy_center("pedal_b")
        if pb is not None:
            bone("v_pedal_brake", tuple(pb), "v_body")
        pa = _obj_origin("Pedal_Accelerator") or _fuzzy_center("pedal_a")
        if pa is not None:
            bone("v_pedal_throttle", tuple(pa), "v_body")
        hb = s if s is not None else Vector((0, 0.5, 1.0))
        bone("v_handbrake", (0.0, hb.y - 0.35, max(hb.z - 0.45, 0.5)), "v_body")

        bpy.ops.object.mode_set(mode='OBJECT')
        ob.show_in_front = True
        self.report({'INFO'}, f"armature built: {len(arm.bones)} bones, all +Y roll 0{est}; checkpoint {cp}")
        return {'FINISHED'}


class RPF_OT_recenter(bpy.types.Operator):
    bl_idname = "rpf.recenter"
    bl_label = "Re-Center Vehicle + Rig"
    bl_description = ("Translate the whole vehicle so the body is centered on X/Y and "
                      "the lowest point sits on Z=0, then normalize the armature so "
                      "v_root is exactly at the world origin. X midline comes from the "
                      "L/R door pairs (immune to mirrors/stray shells skewing the bbox). "
                      "TIP: with meshes SELECTED, centers on the selection bbox instead")
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        sel = [o for o in context.selected_objects if o.type == 'MESH']
        meshes = sel or [o for o in all_meshes() if not o.name.startswith(COLLIDER_PFX)]
        if not meshes:
            self.report({'ERROR'}, "no meshes")
            return {'CANCELLED'}
        mn = Vector((1e9,) * 3); mx = Vector((-1e9,) * 3)
        for o in meshes:
            a, b = wbbox(o)
            mn.x = min(mn.x, a.x); mn.y = min(mn.y, a.y); mn.z = min(mn.z, a.z)
            mx.x = max(mx.x, b.x); mx.y = max(mx.y, b.y); mx.z = max(mx.z, b.z)
        delta = Vector((-(mn.x + mx.x) / 2, -(mn.y + mx.y) / 2, -mn.z))
        src = "selection bbox" if sel else "bbox"
        if not sel:
            # bbox X center lies whenever mirrors or stray shells stick out on one
            # side — symmetric door pairs give the true body midline
            def pair_mid(ln, rn):
                lo = [o for o in part_objects(ln) if o.type == 'MESH']
                ro = [o for o in part_objects(rn) if o.type == 'MESH']
                if not lo or not ro:
                    return None
                def cx(objs):
                    lo_x = min(wbbox(o)[0].x for o in objs)
                    hi_x = max(wbbox(o)[1].x for o in objs)
                    return (lo_x + hi_x) / 2
                return (cx(lo) + cx(ro)) / 2
            for ln, rn in (("door_FL", "door_FR"), ("door_RL", "door_RR")):
                m = pair_mid(ln, rn)
                if m is not None:
                    delta.x = -m
                    src = f"door midline {ln}/{rn} + bbox Y/Z"
                    break
        T = Matrix.Translation(delta)
        for o in bpy.data.objects:
            if o.parent is None:
                o.matrix_world = T @ o.matrix_world
        context.view_layer.update()
        # normalize the armature: bake its object transform into the bone data so
        # the object sits at identity (v_root at world origin) without anything moving
        arm = _get_armature()
        if arm:
            if arm.matrix_world != Matrix.Identity(4):
                kids = {c: c.matrix_world.copy() for c in arm.children}
                arm.data.transform(arm.matrix_world)
                arm.matrix_world = Matrix.Identity(4)
                context.view_layer.update()
                for c, m in kids.items():
                    c.matrix_world = m
                context.view_layer.update()
            # v_root must sit exactly at the world origin (moving it does not
            # move child bones, so this is always safe)
            if context.mode != 'OBJECT':
                bpy.ops.object.mode_set(mode='OBJECT')
            bpy.ops.object.select_all(action='DESELECT')
            arm.hide_set(False)
            arm.select_set(True)
            context.view_layer.objects.active = arm
            bpy.ops.object.mode_set(mode='EDIT')
            eb = arm.data.edit_bones
            vr = eb.get("v_root")
            if vr:
                vr.head = (0, 0, 0)
                vr.tail = (0, BONE_TAIL, 0)
                vr.roll = 0.0
            vb = eb.get("v_body")
            if vb:
                wz = [eb[n].head.z for n in ("v_wheel_l01", "v_wheel_r01",
                                             "v_wheel_l02", "v_wheel_r02") if n in eb]
                vb.head = (0, 0, sum(wz) / len(wz) if wz else vb.head.z)
                vb.tail = Vector(vb.head) + Vector((0, BONE_TAIL, 0))
                vb.roll = 0.0
            bpy.ops.object.mode_set(mode='OBJECT')
        self.report({'INFO'}, f"recentered by {[round(v, 4) for v in delta]} (from {src})"
                              f"{' + armature normalized, v_root at origin' if arm else ''}")
        return {'FINISHED'}


def _skin_bone_for(name):
    if name in DOOR_BONE:
        return DOOR_BONE[name]
    if name.endswith("_window") and name[:-7] in DOOR_BONE:
        return DOOR_BONE[name[:-7]]
    if name in WHEEL_BONES:
        return WHEEL_BONES[name][0]
    return {"brake_FL": "v_rotator_l01", "brake_FR": "v_rotator_r01",
            "brake_RL": "v_suspension_l02", "brake_RR": "v_suspension_r02",
            "Steering_Wheel": "v_steering_wheel", "Pedal_Brake": "v_pedal_brake",
            "Pedal_Accelerator": "v_pedal_throttle"}.get(name, "v_body")


def _rigid_bind(o, arm, bone_name):
    """Rigid-skin one mesh in armature space without changing its placement."""
    if bone_name not in arm.data.bones:
        return False
    # Enfusion expects skinned vehicle meshes in armature space. Bake the
    # object's current transform into its vertices, then leave clean 0/0/0,
    # 0/0/0, 1/1/1 transforms under the armature.
    to_arm = arm.matrix_world.inverted() @ o.matrix_world
    if o.data.users > 1:
        o.data = o.data.copy()
    o.data.transform(to_arm)
    for vg in list(o.vertex_groups):
        o.vertex_groups.remove(vg)
    vg = o.vertex_groups.new(name=bone_name)
    vg.add(range(len(o.data.vertices)), 1.0, 'REPLACE')
    for mod in [m for m in o.modifiers if m.type == 'ARMATURE']:
        o.modifiers.remove(mod)
    mod = o.modifiers.new("Armature", 'ARMATURE')
    mod.object = arm
    mod.use_vertex_groups = True
    mod.use_bone_envelopes = False
    o.parent = arm
    o.parent_type = 'OBJECT'
    o.parent_bone = ""
    o.matrix_parent_inverse = Matrix.Identity(4)
    o.matrix_basis = Matrix.Identity(4)
    return True


def _rig_binding_issues(arm):
    """Return export-blocking movable-part binding problems.

    Wheels are optional: a missing mesh is never an issue.
    """
    movable = set(DOORS) | set(WHEEL_BONES) | {
        "brake_FL", "brake_FR", "brake_RL", "brake_RR",
        "Steering_Wheel", "Pedal_Brake", "Pedal_Accelerator",
    }
    issues = []
    for name in sorted(movable):
        o = bpy.data.objects.get(name)
        if not o or o.type != 'MESH':
            continue
        bone_name = _skin_bone_for(name)
        if bone_name not in arm.data.bones:
            issues.append(f"{name}: missing bone {bone_name}")
            continue
        if not o.vertex_groups.get(bone_name):
            issues.append(f"{name}: not weighted to {bone_name}")
        if not any(m.type == 'ARMATURE' and m.object == arm for m in o.modifiers):
            issues.append(f"{name}: missing Armature modifier")
        if o.parent != arm:
            issues.append(f"{name}: not parented to {arm.name}")
        elif o.parent_type != 'OBJECT':
            issues.append(f"{name}: bone-parented and armature-skinned (double transform)")
    return issues


class RPF_OT_skin_parts(bpy.types.Operator):
    bl_idname = "rpf.skin_parts"
    bl_label = "Skin All Parts (rigid 1.0)"
    bl_description = ("One click: rigid-skin every finalized part to its bone "
                      "(single vertex group weight 1.0 + Armature modifier, parented "
                      "to the armature). Doors->door bones, windows->their door bone, "
                      "wheels->wheel bones, front brakes->rotators, everything "
                      "else->v_body. Run after Build Bones")
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        arm = _get_armature()
        if not arm:
            self.report({'ERROR'}, "no armature — run Build Bones first")
            return {'CANCELLED'}
        bpy.ops.rpf.doors_close()
        targets = set(PART_ORDER) | {d + "_window" for d in DOORS} \
            | {"glass_windshield", "glass_quarters", "glass_partition"}
        done, missing, skipped = {}, [], 0
        for o in all_meshes():
            if o.name not in targets:
                if not o.name.startswith(COLLIDER_PFX):
                    skipped += 1
                continue
            bn = _skin_bone_for(o.name)
            if bn not in arm.data.bones:
                missing.append(f"{o.name}->{bn}")
                continue
            _rigid_bind(o, arm, bn)
            done[o.name] = bn
        if missing:
            self.report({'WARNING'}, f"skinned {len(done)}; skipped missing bones: {', '.join(missing)}")
        else:
            self.report({'INFO'}, f"skinned {len(done)} parts ({skipped} non-part meshes untouched): {done}")
        return {'FINISHED'}


class RPF_OT_select_bone(bpy.types.Operator):
    bl_idname = "rpf.select_bone"
    bl_label = "Select Bone"
    bl_description = "Pose-select this bone and frame it for review"
    bone: bpy.props.StringProperty()

    def execute(self, context):
        arm = _get_armature()
        if not arm or self.bone not in arm.data.bones:
            self.report({'ERROR'}, f"bone {self.bone} not found")
            return {'CANCELLED'}
        if context.mode != 'OBJECT' and context.active_object:
            bpy.ops.object.mode_set(mode='OBJECT')
        bpy.ops.object.select_all(action='DESELECT')
        arm.hide_set(False)
        arm.select_set(True)
        context.view_layer.objects.active = arm
        bpy.ops.object.mode_set(mode='POSE')
        for b in arm.data.bones:
            b.select = (b.name == self.bone)
        arm.data.bones.active = arm.data.bones[self.bone]
        frame_view(context)
        h = arm.matrix_world @ arm.data.bones[self.bone].head_local
        self.report({'INFO'}, f"{self.bone} head at {[round(v, 3) for v in h]}")
        return {'FINISHED'}


class RPF_OT_pose_reset(bpy.types.Operator):
    bl_idname = "rpf.pose_reset"
    bl_label = "Reset Pose + Object Mode"
    bl_description = "Clear all pose transforms and return to Object Mode"

    def execute(self, context):
        arm = _get_armature()
        if arm:
            for pb in arm.pose.bones:
                pb.matrix_basis.identity()
        if context.mode != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')
        return {'FINISHED'}


# ----------------------------------------------------------------------------
# 8b) WHEEL TARGETS — ARP-style placement gizmos for wheel/rotator bones
# ----------------------------------------------------------------------------

WT_COLL = "RIG_TARGETS"
WT_PAIRS = {"01": ("wheel_FL", "wheel_FR"), "02": ("wheel_RL", "wheel_RR")}


class RPF_OT_wheel_targets(bpy.types.Operator):
    bl_idname = "rpf.wheel_targets"
    bl_label = "Add Wheel Targets"
    bl_description = ("Create 4 draggable sphere gizmos (WT_wheel_*) at the current "
                      "wheel-bone positions, sized to the wheel radius. Drag them "
                      "into the wheel arches, then 'Apply Targets -> Bones'")
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        arm = _get_armature()
        r = context.scene.rpf_wheel_radius
        coll = get_coll(WT_COLL)
        made = []
        for idx, names in WT_PAIRS.items():
            for i, wn in enumerate(names):
                bn = WHEEL_BONES[wn][0]
                if arm and bn in arm.data.bones:
                    pos = arm.matrix_world @ arm.data.bones[bn].head_local
                else:
                    pos = _obj_origin(wn) or Vector(((-1 if i == 0 else 1) * 0.9,
                                                     0.9 if idx == "01" else -0.9, r))
                t = bpy.data.objects.get("WT_" + wn)
                if t is None:
                    t = bpy.data.objects.new("WT_" + wn, None)
                    t.empty_display_type = 'SPHERE'
                    coll.objects.link(t)
                t.empty_display_size = r
                t.location = pos
                made.append(t.name)
        self.report({'INFO'}, f"targets ready: {made} — drag into the arches, then Apply")
        return {'FINISHED'}


class RPF_OT_apply_wheel_targets(bpy.types.Operator):
    bl_idname = "rpf.apply_wheel_targets"
    bl_label = "Apply Targets → Bones"
    bl_description = ("Move axle/suspension/rotator/wheel bones to the WT_wheel_* "
                      "gizmo positions. With Mirror X on, left/right pairs are "
                      "symmetrized (drag one side, the other follows). Also updates "
                      "the Wheel radius from the gizmo display size")
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        arm = _get_armature()
        if not arm:
            self.report({'ERROR'}, "no armature — run Build Bones first")
            return {'CANCELLED'}
        mirror = context.scene.rpf_mirror_x
        pos = {}
        for idx, (ln, rn) in WT_PAIRS.items():
            lt, rt = bpy.data.objects.get("WT_" + ln), bpy.data.objects.get("WT_" + rn)
            if not lt or not rt:
                self.report({'ERROR'}, "targets missing — Add Wheel Targets first")
                return {'CANCELLED'}
            lp = lt.matrix_world.translation.copy()
            rp = rt.matrix_world.translation.copy()
            if mirror:
                x = (abs(lp.x) + abs(rp.x)) / 2
                y = (lp.y + rp.y) / 2
                z = (lp.z + rp.z) / 2
                lp, rp = Vector((-x, y, z)), Vector((x, y, z))
                lt.location, rt.location = lp, rp       # write the symmetry back
            pos[ln], pos[rn] = lp, rp

        if context.mode != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')
        bpy.ops.object.select_all(action='DESELECT')
        arm.hide_set(False)
        arm.select_set(True)
        context.view_layer.objects.active = arm
        bpy.ops.object.mode_set(mode='EDIT')
        eb = arm.data.edit_bones
        inv = arm.matrix_world.inverted()

        def place(name, world_head):
            b = eb.get(name)
            if not b:
                return
            h = inv @ Vector(world_head)
            d = (b.tail - b.head)
            b.head = h
            b.tail = h + d          # keep the bone's existing direction (+Y)

        moved = []
        for idx, (ln, rn) in WT_PAIRS.items():
            lp, rp = pos[ln], pos[rn]
            place(f"v_axle_{idx}", (0, (lp.y + rp.y) / 2, (lp.z + rp.z) / 2))
            for wn, p in ((ln, lp), (rn, rp)):
                wbone, sbone, rbone, _ab = WHEEL_BONES[wn]
                place(sbone, (p.x * 0.85, p.y, p.z))
                if rbone:
                    place(rbone, p)
                place(wbone, p)
                moved += [wbone]
        bpy.ops.object.mode_set(mode='OBJECT')
        # sync wheel radius from the FL gizmo's display size
        t = bpy.data.objects.get("WT_wheel_FL")
        if t:
            context.scene.rpf_wheel_radius = t.empty_display_size * max(t.scale)
        # sanity: at rest the wheel center height should ~equal the tire radius,
        # otherwise the tire floats or clips underground in Workbench
        r = context.scene.rpf_wheel_radius
        bad = [n for n, p in pos.items() if abs(p.z - r) > 0.10]
        if bad:
            self.report({'WARNING'}, f"wheel center z vs radius {r:.2f} mismatch on {bad} "
                                     f"— tire would float/clip; drag gizmo Z to ~{r:.2f} and re-Apply")
        else:
            self.report({'INFO'}, f"bones placed from targets{' (X-mirrored)' if mirror else ''}: "
                                  f"axles + suspension + rotators + {moved}")
        return {'FINISHED'}


class RPF_OT_clear_wheel_targets(bpy.types.Operator):
    bl_idname = "rpf.clear_wheel_targets"
    bl_label = "Clear Targets"
    bl_description = "Delete the WT_wheel_* gizmos (do this before export)"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        n = 0
        for o in [o for o in bpy.data.objects if o.name.startswith("WT_")]:
            bpy.data.objects.remove(o)
            n += 1
        c = bpy.data.collections.get(WT_COLL)
        if c and not c.objects:
            bpy.data.collections.remove(c)
        self.report({'INFO'}, f"removed {n} targets")
        return {'FINISHED'}


# ----------------------------------------------------------------------------
# 9) MEMORY POINTS — socket empties (prefab pivot names, exact case)
# ----------------------------------------------------------------------------

SOCKET_COLL = "SOCKETS"


def _socket(name, loc):
    coll = get_coll(SOCKET_COLL)
    o = bpy.data.objects.get(name)
    if o is None:
        o = bpy.data.objects.new(name, None)
        o.empty_display_type = 'PLAIN_AXES'
        o.empty_display_size = 0.08
        coll.objects.link(o)
    o.location = Vector(loc)
    return o


class RPF_OT_add_sockets(bpy.types.Operator):
    bl_idname = "rpf.add_sockets"
    bl_label = "Add Memory Points (auto-place)"
    bl_description = ("One click: create/refresh the SampleCar pivot sockets at "
                      "estimated spots — v_light_FL/FR/RL/RR, v_light_interior, "
                      "v_fuel_cap, v_fx_exhaust, crew getIn/idle points. Names are "
                      "exact prefab case. Review each with the socket buttons and "
                      "nudge as needed")
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        meshes = [o for o in all_meshes() if not o.name.startswith(COLLIDER_PFX)]
        if not meshes:
            self.report({'ERROR'}, "no meshes")
            return {'CANCELLED'}
        mn = Vector((1e9,) * 3); mx = Vector((-1e9,) * 3)
        for o in meshes:
            a, b = wbbox(o)
            mn.x = min(mn.x, a.x); mn.y = min(mn.y, a.y); mn.z = min(mn.z, a.z)
            mx.x = max(mx.x, b.x); mx.y = max(mx.y, b.y); mx.z = max(mx.z, b.z)
        made = []

        lf = bpy.data.objects.get("lights_front")
        if lf:
            a, b = wbbox(lf)
            y, z = b.y - 0.02, (a.z + b.z) / 2
            xl, xr = a.x + 0.15 * (b.x - a.x), b.x - 0.15 * (b.x - a.x)
        else:
            y, z, xl, xr = mx.y - 0.10, 0.75, mn.x + 0.25, mx.x - 0.25
        made += [_socket("v_light_FL", (xl, y, z)).name,
                 _socket("v_light_FR", (xr, y, z)).name]
        lr = bpy.data.objects.get("lights_rear")
        if lr:
            a, b = wbbox(lr)
            y, z = a.y + 0.02, (a.z + b.z) / 2
            xl, xr = a.x + 0.15 * (b.x - a.x), b.x - 0.15 * (b.x - a.x)
        else:
            y, z, xl, xr = mn.y + 0.10, 0.85, mn.x + 0.25, mx.x - 0.25
        made += [_socket("v_light_RL", (xl, y, z)).name,
                 _socket("v_light_RR", (xr, y, z)).name]

        s = _obj_origin("Steering_Wheel") or Vector((min(mn.x + 0.45, -0.35), 0.5, 1.05))
        sgn = -1.0 if s.x < 0 else 1.0            # driver side sign
        made.append(_socket("v_light_interior", (0, s.y - 0.5, mx.z - 0.25)).name)
        made.append(_socket("v_fuel_cap", (mn.x + 0.03, 0.55 * mn.y, 0.85)).name)
        made.append(_socket("v_fx_exhaust", (-sgn * 0.40, mn.y + 0.05, 0.30)).name)

        dfront = _obj_origin("door_FL" if sgn < 0 else "door_FR") or Vector((sgn * mx.x, s.y + 0.4, 1.0))
        drear = _obj_origin("door_RL" if sgn < 0 else "door_RR") or Vector((sgn * mx.x, s.y - 0.9, 1.0))
        seat_z = max(s.z - 0.25, 0.55)
        made += [
            _socket("driver_idle", (s.x, s.y - 0.45, seat_z)).name,
            _socket("codriver_idle", (-s.x, s.y - 0.45, seat_z)).name,
            _socket("driver_getIn", (dfront.x + sgn * 0.70, dfront.y - 0.55, 0.0)).name,
            _socket("codriver_getIn", (-(dfront.x + sgn * 0.70), dfront.y - 0.55, 0.0)).name,
            _socket("passengerl_idle", (-abs(s.x), drear.y - 0.45, seat_z)).name,
            _socket("passengerr_idle", (abs(s.x), drear.y - 0.45, seat_z)).name,
            _socket("passengerc_idle", (0.0, drear.y - 0.45, seat_z)).name,
            _socket("passengerl_getin", (-(abs(drear.x) + 0.70), drear.y - 0.55, 0.0)).name,
            _socket("passengerr_getin", (abs(drear.x) + 0.70, drear.y - 0.55, 0.0)).name,
        ]
        self.report({'INFO'}, f"{len(made)} sockets placed in {SOCKET_COLL} — review + nudge each")
        return {'FINISHED'}


LIGHT_MAT_TOKENS = ("light", "lamp", "headl", "taill", "beacon", "strobe")
LIGHT_PARTS = ("lights_front", "lights_rear", "lights_emergency")


def _light_clusters(merge_dist=0.28):
    """Find lamp geometry (light-named materials, or meshes in lights_* parts),
    split it into islands, merge nearby islands into clusters.
    Returns [(center Vector, size Vector, vert_count)] sorted biggest first."""
    islands = []
    for o in all_meshes():
        if o.name.startswith(COLLIDER_PFX):
            continue
        mats = [ms.material.name.lower() if ms.material else "" for ms in o.material_slots]
        light_slots = {i for i, m in enumerate(mats)
                       if any(t in m for t in LIGHT_MAT_TOKENS)}
        in_part = part_of(o) in LIGHT_PARTS or o.name.split(".")[0] in LIGHT_PARTS
        if not light_slots and not in_part:
            continue
        me = o.data
        mw = o.matrix_world
        if light_slots:
            faces = [p for p in me.polygons if p.material_index in light_slots]
        else:
            faces = list(me.polygons)
        if not faces:
            continue
        parent = {}

        def find(a):
            parent.setdefault(a, a)
            while parent[a] != a:
                parent[a] = parent[parent[a]]
                a = parent[a]
            return a

        for p in faces:
            r0 = find(p.vertices[0])
            for v in p.vertices[1:]:
                rv = find(v)
                if rv != r0:
                    parent[rv] = r0
        groups = {}
        for v in parent:
            groups.setdefault(find(v), []).append(v)
        for vids in groups.values():
            pts = [mw @ me.vertices[i].co for i in vids]
            mn = Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
            mx = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
            islands.append([mn, mx, len(vids)])
    # agglomerate close islands into clusters
    changed = True
    while changed:
        changed = False
        for i in range(len(islands)):
            for j in range(i + 1, len(islands)):
                ci = (islands[i][0] + islands[i][1]) / 2
                cj = (islands[j][0] + islands[j][1]) / 2
                if (ci - cj).length < merge_dist:
                    a, b = islands[i], islands[j]
                    mn = Vector((min(a[0].x, b[0].x), min(a[0].y, b[0].y), min(a[0].z, b[0].z)))
                    mx = Vector((max(a[1].x, b[1].x), max(a[1].y, b[1].y), max(a[1].z, b[1].z)))
                    islands[i] = [mn, mx, a[2] + b[2]]
                    islands.pop(j)
                    changed = True
                    break
            if changed:
                break
    out = [((mn + mx) / 2, mx - mn, n) for mn, mx, n in islands]
    return sorted(out, key=lambda c: -c[2])


class RPF_OT_scan_lights(bpy.types.Operator):
    bl_idname = "rpf.scan_lights"
    bl_label = "Scan Lights → Sockets"
    bl_description = ("Detect lamp geometry (light-named materials / lights_* parts), "
                      "cluster the lenses, and place/re-center v_light_FL/FR/RL/RR on "
                      "the outermost front and rear clusters. Every other cluster is "
                      "printed to the console as an EM-socket candidate")
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        clusters = _light_clusters()
        if not clusters:
            self.report({'ERROR'}, "no lamp geometry found (light materials or lights_* parts)")
            return {'CANCELLED'}
        ymax = max(c[0].y for c in clusters)
        ymin = min(c[0].y for c in clusters)
        front = [c for c in clusters if c[0].y > ymax - 0.6]
        rear = [c for c in clusters if c[0].y < ymin + 0.6]
        placed = []

        def best_pair(group):
            """Largest L/R cluster pair that mirrors across X (headlights/taillights
            come in symmetric pairs — beats picking each side independently)."""
            left = [c for c in group if c[0].x < -0.05]
            right = [c for c in group if c[0].x > 0.05]
            best, score = None, -1
            for lc in left:
                for rc in right:
                    err = (abs(lc[0].x + rc[0].x) + abs(lc[0].y - rc[0].y)
                           + abs(lc[0].z - rc[0].z))
                    if err > 0.20:
                        continue
                    # head/taillights sit OUTBOARD and have tall lenses — weight
                    # those over big centered marker/grille clusters
                    s = (lc[2] + rc[2]) * (0.5 + abs(lc[0].x)) \
                        * (1.0 + lc[1].z + rc[1].z)
                    if s > score:
                        best, score = (lc, rc), s
            return best

        for ln, rn, group in (("v_light_FL", "v_light_FR", front),
                              ("v_light_RL", "v_light_RR", rear)):
            pair = best_pair(group)
            if pair:
                _socket(ln, pair[0][0])
                _socket(rn, pair[1][0])
                placed += [f"{ln}@{[round(v, 2) for v in pair[0][0]]}",
                           f"{rn}@{[round(v, 2) for v in pair[1][0]]}"]
        print("=" * 60)
        print(f"RPF LIGHT SCAN — {len(clusters)} clusters")
        for ctr, size, n in clusters:
            print(f"  center {[round(v, 3) for v in ctr]}  size {[round(v, 2) for v in size]}  verts {n}")
        print("placed:", placed)
        print("other clusters above = EM/beacon candidates -> name + 'Add Socket @ Cursor'")
        self.report({'INFO'}, f"{len(clusters)} lamp clusters; placed {len(placed)} sockets — see console")
        return {'FINISHED'}


class RPF_OT_add_socket_cursor(bpy.types.Operator):
    bl_idname = "rpf.add_socket_cursor"
    bl_label = "Add Socket @ Cursor"
    bl_description = ("Create a named socket empty at the 3D cursor (e.g. "
                      "v_light_em_roofbar) — snap the cursor to a face first "
                      "(Shift+Right-Click)")
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        name = context.scene.rpf_socket_name.strip()
        if not name:
            self.report({'ERROR'}, "type a socket name first")
            return {'CANCELLED'}
        o = _socket(name, context.scene.cursor.location)
        self.report({'INFO'}, f"{o.name} at {[round(v, 3) for v in o.location]}")
        return {'FINISHED'}


class RPF_OT_add_bench_seats(bpy.types.Operator):
    bl_idname = "rpf.add_bench_seats"
    bl_label = "Add Bench Seats (multi)"
    bl_description = ("Multi-seat vehicles (APCs, trucks): detect bench/seat meshes, "
                      "place the chosen number of passengerNN_idle sockets spaced "
                      "along the benches (half left, half right), plus a "
                      "passenger_getin_rear marker behind the rear doors. Nudge "
                      "sockets after with the Mem quick-select grid")
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        n = context.scene.rpf_seat_count
        bench_points = []
        fallback_points = []
        for o in all_meshes():
            if o.name.startswith(COLLIDER_PFX):
                continue
            nm = o.name.lower()
            mats = [ms.material.name.lower() if ms.material else "" for ms in o.material_slots]
            for poly in o.data.polygons:
                mat = mats[poly.material_index] if poly.material_index < len(mats) else ""
                points = bench_points if ("bench" in nm or "bench" in mat) else fallback_points
                if "bench" in nm or "bench" in mat or "seat" in nm or "seat" in mat:
                    points.extend(o.matrix_world @ o.data.vertices[i].co for i in poly.vertices)
        points = bench_points or fallback_points
        if not points:
            self.report({'ERROR'}, "no seat/bench meshes found (name or material must contain seat/bench)")
            return {'CANCELLED'}

        def side_box(side_points):
            mn = Vector((min(p.x for p in side_points), min(p.y for p in side_points),
                         min(p.z for p in side_points)))
            mx = Vector((max(p.x for p in side_points), max(p.y for p in side_points),
                         max(p.z for p in side_points)))
            return mn, mx

        # Split actual bench vertices, not whole objects. Combined interior meshes
        # otherwise put every generated seat on the vehicle centerline.
        left = [p for p in points if p.x < 0]
        right = [p for p in points if p.x >= 0]
        nl = n // 2
        nr = n - nl
        made, idx = [], 1
        for side_points, count in ((left, nl), (right, nr)):
            if not side_points or count <= 0:
                continue
            mn, mx = side_box(side_points)
            cx = (mn.x + mx.x) / 2
            cx -= (1 if cx > 0 else -1) * context.scene.rpf_seat_inset
            for i in range(count):
                y = mn.y + (i + 0.5) * (mx.y - mn.y) / count + context.scene.rpf_seat_forward
                made.append(_socket(f"passenger{idx:02d}_idle", (cx, y, mx.z + 0.02)).name)
                idx += 1
        for stale_idx in range(idx, 33):
            stale = bpy.data.objects.get(f"passenger{stale_idx:02d}_idle")
            if stale:
                bpy.data.objects.remove(stale, do_unlink=True)
        # rear load/unload marker: center behind the rear doors at ground level
        vmn = Vector((1e9,) * 3)
        for o in all_meshes():
            if not o.name.startswith(COLLIDER_PFX):
                a, _b = wbbox(o)
                vmn.y = min(vmn.y, a.y)
        made.append(_socket("passenger_getin_rear", (0.0, vmn.y - 0.70, 0.0)).name)
        self.report({'INFO'}, f"placed {len(made)} seat/getin sockets: {made}")
        return {'FINISHED'}


class RPF_OT_select_socket(bpy.types.Operator):
    bl_idname = "rpf.select_socket"
    bl_label = "Select Socket"
    bl_description = "Select this memory point and frame it for review"
    socket: bpy.props.StringProperty()

    def execute(self, context):
        o = bpy.data.objects.get(self.socket)
        if not o:
            return {'CANCELLED'}
        if context.mode != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')
        bpy.ops.object.select_all(action='DESELECT')
        o.hide_set(False)
        o.select_set(True)
        context.view_layer.objects.active = o
        frame_view(context)
        self.report({'INFO'}, f"{o.name} at {[round(v, 3) for v in o.matrix_world.translation]}")
        return {'FINISHED'}


# ----------------------------------------------------------------------------
# 10) LOD BAKE — decimate visual parts down to an adjustable tri budget
# ----------------------------------------------------------------------------

def _tris(o):
    return sum(max(len(p.vertices) - 2, 0) for p in o.data.polygons)


class RPF_OT_bake_lod(bpy.types.Operator):
    bl_idname = "rpf.bake_lod"
    bl_label = "Bake LOD (decimate to target)"
    bl_description = ("Decimate-collapse every visual part proportionally until the "
                      "whole vehicle fits the target tri budget. Keeps UVs, vertex "
                      "groups and materials; meshes under the 'protect below' size "
                      "are left untouched. Saves a checkpoint first")
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        target = context.scene.rpf_lod_target * 1000
        protect = context.scene.rpf_lod_min
        meshes = [o for o in all_meshes() if not o.name.startswith(COLLIDER_PFX)]
        total = sum(_tris(o) for o in meshes)
        if total <= target:
            self.report({'INFO'}, f"already {total:,} tris <= target {target:,} — nothing to do")
            return {'FINISHED'}
        cp = checkpoint("prelod")
        bpy.ops.rpf.doors_close()
        victims = [o for o in meshes if _tris(o) > protect]
        fixed = total - sum(_tris(o) for o in victims)
        ratio = max((target - fixed) / max(sum(_tris(o) for o in victims), 1), 0.02)
        rows = []
        for o in victims:
            before = _tris(o)
            if o.data.users > 1:
                o.data = o.data.copy()
            mod = o.modifiers.new("RPF_LOD", 'DECIMATE')
            mod.ratio = ratio
            bpy.ops.object.select_all(action='DESELECT')
            o.hide_set(False)
            o.select_set(True)
            context.view_layer.objects.active = o
            bpy.ops.object.modifier_move_to_index(modifier="RPF_LOD", index=0)
            bpy.ops.object.modifier_apply(modifier="RPF_LOD")
            rows.append((o.name, before, _tris(o)))
        after = sum(_tris(o) for o in meshes)
        print("=" * 60)
        print(f"RPF LOD BAKE  ratio={ratio:.3f}  {total:,} -> {after:,} tris (target {target:,})")
        for name, b, a in sorted(rows, key=lambda r: -r[1]):
            print(f"  {name:<28} {b:>8,} -> {a:>8,}")
        print(f"protected (<{protect:,} tris): {len(meshes) - len(victims)} meshes")
        print(f"checkpoint: {cp}")
        self.report({'INFO'}, f"LOD baked: {total:,} -> {after:,} tris (ratio {ratio:.3f}); checkpoint saved — see console")
        return {'FINISHED'}


# ----------------------------------------------------------------------------
# panel
# ----------------------------------------------------------------------------

class RPF_PT_panel(bpy.types.Panel):
    bl_label = "Reforger Part Fixer"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Part Fixer"

    def draw(self, context):
        l = self.layout
        sc = context.scene
        l.row().prop(sc, "rpf_tab", expand=True)
        tab = sc.rpf_tab

        if tab == 'SETUP':
            box = l.box()
            box.label(text="Vehicle", icon='AUTO')
            box.prop(sc, "rpf_asset_name", text="Asset")
            box.prop(sc, "rpf_export_root", text="Export")
            box.prop(sc, "rpf_wheelbase", text="Wheelbase (m)")
            box.prop(sc, "rpf_wheel_radius", text="Wheel radius (m)")
            box.prop(sc, "rpf_tex_path", text="Textures (.zip/dir)")
            l.operator("rpf.discover", icon='ZOOM_ALL')
            l.operator("rpf.recenter", icon='ORIENTATION_GLOBAL')
            l.operator("rpf.auto_setup", icon='AUTO')
            l.operator("rpf.organize", icon='OUTLINER')
            l.operator("rpf.apply_textures", icon='TEXTURE')
            l.operator("rpf.check_transforms", icon='CON_SIZELIMIT')

        elif tab == 'PARTS':
            box = l.box()
            box.label(text="Quick Select", icon='RESTRICT_SELECT_OFF')
            grid = box.grid_flow(columns=2, even_columns=True)
            for p in PART_ORDER:
                if not part_objects(p):
                    continue
                op = grid.operator("rpf.quick_select", text=p)
                op.part = p

            box = l.box()
            box.label(text="Door Test-Open", icon='DRIVER_ROTATIONAL_DIFFERENCE')
            row = box.row(align=True)
            for dn in DOORS:
                op = row.operator("rpf.door_open", text=dn[-2:])
                op.door = dn
            box.operator("rpf.doors_close", icon='X')
            box.operator("rpf.send_interior", icon='HOME')
            box.operator("rpf.snap_back", icon='LOOP_BACK')

            box = l.box()
            box.label(text="Review / Move", icon='VIEWZOOM')
            box.prop(sc, "rpf_active_part", text="Part")
            box.prop(sc, "rpf_ghost_hide", text="Hide others (instead of wire)")
            row = box.row(align=True)
            row.operator("rpf.review", icon='HIDE_OFF')
            row.operator("rpf.stop_review", text="", icon='X')
            row = box.row(align=True)
            row.operator("rpf.explode_part", icon='MOD_EXPLODE')
            row.operator("rpf.rejoin_parts", text="Rejoin", icon='FULLSCREEN_EXIT')
            exploded = sc.get("rpf_exploded", "")
            if exploded:
                box.label(text=f"EXPLODED: {exploded}", icon='ERROR')
            box.operator("rpf.add_selected", icon='IMPORT')
            row = box.row(align=True)
            row.prop(sc, "rpf_move_target", text="")
            row.operator("rpf.move_selected", text="Move", icon='EXPORT')
            box.operator("rpf.extract_selection", icon='MOD_EXPLODE')
            l.operator("rpf.finalize", icon='CHECKMARK')

        elif tab == 'RIG':
            l.operator("rpf.recenter", icon='ORIENTATION_GLOBAL')
            l.operator("rpf.build_rig", icon='ARMATURE_DATA')
            l.operator("rpf.skin_parts", icon='MOD_VERTEX_WEIGHT')
            box = l.box()
            box.label(text="Wheel Placement", icon='GIZMO')
            box.operator("rpf.wheel_targets", icon='SPHERE')
            box.prop(sc, "rpf_mirror_x", text="Mirror X (L/R symmetric)")
            row = box.row(align=True)
            row.operator("rpf.apply_wheel_targets", icon='CHECKMARK')
            row.operator("rpf.clear_wheel_targets", text="", icon='X')
            arm = _get_armature()
            if arm:
                box = l.box()
                box.label(text=f"Bones ({len(arm.data.bones)}) — click to review", icon='BONE_DATA')
                grid = box.grid_flow(columns=2, even_columns=True)
                for b in sorted(arm.data.bones, key=lambda b: b.name):
                    op = grid.operator("rpf.select_bone", text=b.name)
                    op.bone = b.name
                l.operator("rpf.pose_reset", icon='LOOP_BACK')
            else:
                l.label(text="no armature yet — Build Bones", icon='INFO')

        elif tab == 'MEMORY':
            l.operator("rpf.add_sockets", icon='EMPTY_AXIS')
            l.operator("rpf.scan_lights", icon='LIGHT_SPOT')
            row = l.row(align=True)
            row.prop(sc, "rpf_seat_count", text="Rear bench seats")
            row.operator("rpf.add_bench_seats", text="Place", icon='EMPTY_ARROWS')
            row = l.row(align=True)
            row.prop(sc, "rpf_seat_inset", text="Inward")
            row.prop(sc, "rpf_seat_forward", text="Forward")
            row = l.row(align=True)
            row.prop(sc, "rpf_socket_name", text="")
            row.operator("rpf.add_socket_cursor", text="@Cursor", icon='PIVOT_CURSOR')
            coll = bpy.data.collections.get(SOCKET_COLL)
            sockets = sorted(o.name for o in coll.objects) if coll else []
            groups = [("Lights", [n for n in sockets if n.startswith("v_light") and "_em_" not in n]),
                      ("EM Lights", [n for n in sockets if "_em_" in n]),
                      ("Crew", [n for n in sockets if "get" in n.lower() or "idle" in n]),
                      ("Other", [n for n in sockets if not n.startswith("v_light")
                                 and "get" not in n.lower() and "idle" not in n])]
            for title, names in groups:
                if not names:
                    continue
                box = l.box()
                box.label(text=title, icon='EMPTY_DATA')
                grid = box.grid_flow(columns=2, even_columns=True)
                for n in names:
                    op = grid.operator("rpf.select_socket", text=n)
                    op.socket = n

        elif tab == 'LOD':
            box = l.box()
            box.label(text="LOD Bake", icon='MOD_DECIM')
            box.prop(sc, "rpf_lod_target", text="Target (k tris)")
            box.prop(sc, "rpf_lod_min", text="Protect below (tris)")
            meshes = [o for o in all_meshes() if not o.name.startswith(COLLIDER_PFX)]
            box.label(text=f"current: {sum(_tris(o) for o in meshes):,} tris in {len(meshes)} meshes")
            box.operator("rpf.bake_lod", icon='MOD_DECIM')

        elif tab == 'BUILD':
            box = l.box()
            box.label(text="Collision Review", icon='HIDE_OFF')
            row = box.row(align=True)
            for mode, label in (('MODEL', "Model"), ('UCX', "UCX"),
                                ('FIRE', "FireGeo"), ('ALL', "All")):
                op = row.operator("rpf.collision_view", text=label)
                op.mode = mode
            row = box.row(align=True)
            for axis, label in (('LEFT', "L"), ('RIGHT', "R"), ('FRONT', "F"),
                                ('BACK', "B"), ('TOP', "Top")):
                op = row.operator("rpf.view_axis", text=label)
                op.axis = axis
            box.operator("rpf.sort_collapse", icon='OUTLINER_COLLECTION')
            onebox = l.box()
            onebox.label(text="One-Click Physics + Tidy", icon='MODIFIER')
            onebox.operator("rpf.build_all_physics", icon='AUTO')
            frow = onebox.row(align=True)
            frow.operator("rpf.fix_ucx", icon='CHECKMARK')
            frow.operator("rpf.cleanup_colliders", text="Tidy (generated)", icon='TRASH').mode = 'GENERATED'
            frow2 = onebox.row(align=True)
            frow2.operator("rpf.cleanup_colliders", text="Remove invalid", icon='TRASH').mode = 'INVALID'
            frow2.operator("rpf.cleanup_colliders", text="Remove all", icon='TRASH').mode = 'ALL'
            cbox = l.box()
            cbox.label(text="Collision (UCX)", icon='MESH_CUBE')
            cbox.operator("rpf.build_colliders", icon='MESH_CUBE')
            crow = cbox.row(align=True)
            crow.operator("rpf.selected_parts_to_ucx", icon='MESH_ICOSPHERE')
            crow.operator("rpf.validate_ucx", text="Validate", icon='CHECKMARK')
            cbox.operator("rpf.convexify_selected_ucx", icon='MESH_ICOSPHERE')
            vbox = l.box()
            vbox.label(text="V-HACD multi-hull (collision / LOD geo)", icon='MOD_REMESH')
            vbox.prop(sc, "rpf_vhacd_exe", text="V-HACD exe (optional)")
            vrow = vbox.row(align=True)
            vrow.operator("rpf.vhacd_selected", icon='MESH_ICOSPHERE')
            vrow.operator("rpf.install_vhacd_deps", text="Install deps", icon='IMPORT')
            gbox = l.box()
            gbox.label(text="Geometry / Parts", icon='MESH_ICOSPHERE')
            gbox.operator("rpf.build_firegeo", text="Build FireGeo", icon='MESH_ICOSPHERE')
            gbox.operator("rpf.separate_wheels", icon='MESH_CIRCLE')

        elif tab == 'EXPORT':
            box = l.box()
            box.label(text="Collision Review", icon='HIDE_OFF')
            row = box.row(align=True)
            for mode, label in (('MODEL', "Model"), ('UCX', "UCX"),
                                ('FIRE', "FireGeo"), ('ALL', "All")):
                op = row.operator("rpf.collision_view", text=label)
                op.mode = mode
            box.operator("rpf.sort_collapse", icon='OUTLINER_COLLECTION')
            box = l.box()
            box.label(text="Export Target", icon='FILE_FOLDER')
            box.prop(sc, "rpf_asset_name", text="Asset")
            box.prop(sc, "rpf_export_root", text="Directory")
            box = l.box()
            box.label(text="Master FBX Includes", icon='CHECKMARK')
            box.prop(sc, "rpf_export_render", text="Render exterior / interior / doors")
            box.prop(sc, "rpf_export_armature", text="Armature")
            box.prop(sc, "rpf_export_memory", text="Memory points / sockets")
            box.prop(sc, "rpf_export_vehicle_collision", text="Vehicle collision (UCL / UCX)")
            box.prop(sc, "rpf_export_firegeo", text="FireGeo / component hit zones")
            box.prop(sc, "rpf_export_glass_firegeo", text="Armored glass FireGeo (UTM_Glass)")
            box.prop(sc, "rpf_export_visual_glass", text="Visual glass in master (bulletproof)")
            box = l.box()
            box.label(text="Separate Slot Exports", icon='OUTLINER_COLLECTION')
            box.prop(sc, "rpf_export_wheel_slot", text="Wheel FBX (optional)")
            box.prop(sc, "rpf_export_dst_glass", text="DST glass FBXs")
            l.operator("rpf.export_enfusion", icon='EXPORT')
            l.operator("rpf.export_em_lamps", icon='LIGHT_SUN')

        open_door = context.scene.get("rpf_open_door", "")
        if open_door:
            l.label(text=f"OPEN: {open_door}", icon='ERROR')
        rev = context.scene.get("rpf_reviewing", "")
        if rev:
            l.label(text=f"reviewing: {rev}", icon='INFO')


CLASSES = (RPF_OT_discover, RPF_OT_build_colliders, RPF_OT_build_firegeo,
           RPF_OT_selected_parts_to_ucx, RPF_OT_validate_ucx,
           RPF_OT_convexify_selected_ucx,
           RPF_OT_separate_wheels, RPF_OT_vhacd_selected, RPF_OT_install_vhacd_deps,
           RPF_OT_cleanup_colliders, RPF_OT_fix_ucx, RPF_OT_build_all_physics,
           RPF_OT_collision_view, RPF_OT_view_axis, RPF_OT_sort_collapse,
           RPF_OT_auto_setup, RPF_OT_organize, RPF_OT_quick_select, RPF_OT_review,
           RPF_OT_stop_review, RPF_OT_door_open, RPF_OT_doors_close,
           RPF_OT_send_interior, RPF_OT_add_selected, RPF_OT_move_selected,
           RPF_OT_snap_back, RPF_OT_check_transforms, RPF_OT_apply_textures,
           RPF_OT_finalize, RPF_OT_explode_part, RPF_OT_rejoin_parts,
           RPF_OT_extract_selection, RPF_OT_export_enfusion, RPF_OT_export_em_lamps,
           RPF_OT_build_rig, RPF_OT_skin_parts, RPF_OT_select_bone, RPF_OT_pose_reset,
           RPF_OT_recenter, RPF_OT_wheel_targets, RPF_OT_apply_wheel_targets,
           RPF_OT_clear_wheel_targets,
           RPF_OT_add_sockets, RPF_OT_add_socket_cursor, RPF_OT_add_bench_seats, RPF_OT_select_socket,
           RPF_OT_scan_lights,
           RPF_OT_bake_lod,
           RPF_PT_panel)


def register():
    for c in CLASSES:
        try:
            bpy.utils.register_class(c)
        except ValueError:
            bpy.utils.unregister_class(c)
            bpy.utils.register_class(c)
    bpy.types.Scene.rpf_active_part = bpy.props.EnumProperty(
        name="Part", items=_part_items)
    bpy.types.Scene.rpf_move_target = bpy.props.EnumProperty(
        name="Target", items=_part_items)
    bpy.types.Scene.rpf_ghost_hide = bpy.props.BoolProperty(
        name="Hide others", default=False,
        description="During review, hide other parts completely instead of wireframing them")
    bpy.types.Scene.rpf_tab = bpy.props.EnumProperty(
        name="Tab", default='PARTS',
        items=[('SETUP', "Setup", "Discovery, auto-setup, vehicle settings"),
               ('PARTS', "Parts", "Quick select, door test-open, review/move, finalize"),
               ('RIG', "Rig", "Build bones, skin parts, per-bone review"),
               ('MEMORY', "Mem", "Memory point sockets — auto-place + review"),
               ('LOD', "LOD", "Decimate to an adjustable tri budget"),
               ('BUILD', "Build", "One-click physics: collision, FireGeo, LOD, V-HACD, tidy/fix"),
               ('EXPORT', "Exp", "Enfusion FBX exports")])
    bpy.types.Scene.rpf_asset_name = bpy.props.StringProperty(
        name="Asset", default=ASSET_NAME,
        description="Asset/file base name used by the exporters")
    bpy.types.Scene.rpf_export_root = bpy.props.StringProperty(
        name="Export Root", default=EXPORT_ROOT, subtype='DIR_PATH',
        description="Addon asset folder the FBX set is written into")
    bpy.types.Scene.rpf_export_render = bpy.props.BoolProperty(
        name="Render meshes", default=True)
    bpy.types.Scene.rpf_export_armature = bpy.props.BoolProperty(
        name="Armature", default=True)
    bpy.types.Scene.rpf_export_memory = bpy.props.BoolProperty(
        name="Memory points", default=True)
    bpy.types.Scene.rpf_export_vehicle_collision = bpy.props.BoolProperty(
        name="Vehicle collision", default=True)
    bpy.types.Scene.rpf_export_firegeo = bpy.props.BoolProperty(
        name="FireGeo", default=True)
    bpy.types.Scene.rpf_export_glass_firegeo = bpy.props.BoolProperty(
        name="Glass FireGeo", default=True)
    bpy.types.Scene.rpf_export_visual_glass = bpy.props.BoolProperty(
        name="Visual glass in master", default=False,
        description="Include fixed visual glass in the master XOB for non-DST/bulletproof vehicles")
    bpy.types.Scene.rpf_export_wheel_slot = bpy.props.BoolProperty(
        name="Wheel slot FBX", default=False,
        description="Export a separate visual wheel FBX; sockets and wheel colliders remain in the master")
    bpy.types.Scene.rpf_export_dst_glass = bpy.props.BoolProperty(
        name="DST glass FBXs", default=True,
        description="Export separate destructible glass slot FBXs; visual glass stays out of the master")
    bpy.types.Scene.rpf_vhacd_exe = bpy.props.StringProperty(
        name="V-HACD exe", default="", subtype='FILE_PATH',
        description="Optional path to an external V-HACD executable (TestVHACD v4). "
                    "Used only when the CoACD python module is not installed")
    bpy.types.Scene.rpf_wheelbase = bpy.props.FloatProperty(
        name="Wheelbase", default=TARGET_WHEELBASE, min=1.0, max=6.0, precision=3,
        description="Real-world wheelbase (m) the model is rescaled to in Auto-Setup")
    bpy.types.Scene.rpf_wheel_radius = bpy.props.FloatProperty(
        name="Wheel radius", default=0.397, min=0.15, max=0.90, precision=3,
        description="Tire radius (m) — used to estimate axle height when the blend has no wheels")
    bpy.types.Scene.rpf_tex_path = bpy.props.StringProperty(
        name="Textures", default=TEXDIR, subtype='FILE_PATH',
        description="Texture source for Apply Textures: a folder OR a .zip archive "
                    "(extracted automatically next to itself)")
    bpy.types.Scene.rpf_mirror_x = bpy.props.BoolProperty(
        name="Mirror X", default=True,
        description="Apply Targets symmetrizes left/right wheel pairs across X "
                    "(drag one side, the other matches)")
    bpy.types.Scene.rpf_socket_name = bpy.props.StringProperty(
        name="Socket", default="v_light_em_",
        description="Name for a new socket empty created at the 3D cursor")
    bpy.types.Scene.rpf_seat_count = bpy.props.IntProperty(
        name="Rear bench seats", default=6, min=2, max=32,
        description="Number of passengerNN_idle sockets placed across the two rear benches")
    bpy.types.Scene.rpf_seat_inset = bpy.props.FloatProperty(
        name="Seat inward offset", default=0.24, min=0, max=1, precision=3,
        description="Pull side-facing bench seat origins inward from the side walls")
    bpy.types.Scene.rpf_seat_forward = bpy.props.FloatProperty(
        name="Seat forward offset", default=0.15, min=-1, max=1, precision=3,
        description="Move generated rear bench seat origins forward along Blender +Y")
    bpy.types.Scene.rpf_lod_target = bpy.props.IntProperty(
        name="Target k-tris", default=120, min=10, max=1000,
        description="Whole-vehicle LOD0 triangle budget, in thousands (e.g. 120 = 120k)")
    bpy.types.Scene.rpf_lod_min = bpy.props.IntProperty(
        name="Protect below", default=1500, min=0, max=50000,
        description="Meshes with fewer tris than this are never decimated (glass, pedals...)")


def unregister():
    for c in reversed(CLASSES):
        try:
            bpy.utils.unregister_class(c)
        except RuntimeError:
            pass


if __name__ == "__main__":
    register()
