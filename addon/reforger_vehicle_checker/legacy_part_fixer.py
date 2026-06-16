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
    "version": (0, 8, 7),
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

try:
    from .rvc_core.rig_roles import (
        SAMPLECAR_PARENT,
        is_road_wheel_name,
        is_steering_name,
        opposite_bone_name,
        resolve_target_bone,
        target_bone_for_role,
    )
except Exception:
    from rvc_core.rig_roles import (
        SAMPLECAR_PARENT,
        is_road_wheel_name,
        is_steering_name,
        opposite_bone_name,
        resolve_target_bone,
        target_bone_for_role,
    )

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
    "rotator_FL", "rotator_FR", "rotator_RL", "rotator_RR",
    "suspension_FL", "suspension_FR", "suspension_RL", "suspension_RR",
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
    "rotator_FL": 'COLOR_03', "rotator_FR": 'COLOR_03', "rotator_RL": 'COLOR_03', "rotator_RR": 'COLOR_03',
    "suspension_FL": 'COLOR_06', "suspension_FR": 'COLOR_06', "suspension_RL": 'COLOR_06', "suspension_RR": 'COLOR_06',
    "brake_FL": 'COLOR_03', "brake_FR": 'COLOR_03', "brake_RL": 'COLOR_03', "brake_RR": 'COLOR_03',
    "Steering_Wheel": 'COLOR_06', "Pedal_Brake": 'COLOR_06', "Pedal_Accelerator": 'COLOR_06',
    "lights_front": 'COLOR_04', "lights_rear": 'COLOR_04', "lights_emergency": 'COLOR_04',
    "interior": 'COLOR_07', "exterior": 'COLOR_08',
}

PFX = "Police_Interceptor_SUV"

VEHICLE_GAMEMAT = "{CE9253778DD8FBDE}Common/Materials/Game/metal.gamemat"
VEHICLE_BODY_GAMEMAT = "{D3A4A761377F28DE}Common/Materials/Game/VehicleParts/vehicle_body.gamemat"
VEHICLE_BOTTOM_GAMEMAT = "{D9FA05910FD9A1AB}Common/Materials/Game/VehicleParts/vehicle_body_bottom_slide.gamemat"
TIRE_GAMEMAT = "{8F1BCCA995D7FA4B}Common/Materials/Game/rubber_tire.gamemat"
TIRE_4MM_GAMEMAT = "{C2BF4F9689827271}Common/Materials/Game/RubberTire/rubber_tire_4mm_min.gamemat"
FIREGEO_METAL_GAMEMAT = "{EDB153DC99889624}Common/Materials/Game/Metal/metal_3mm.gamemat"
WHEEL_METAL_GAMEMAT = "{1950188BB10D20EA}Common/Materials/Game/Metal/metal_5mm.gamemat"
LIGHT_PLASTIC_GAMEMAT = "{C17486F3DA1510F6}Common/Materials/Game/Plastic/plastic_3mm.gamemat"
THIN_GLASS_GAMEMAT = "{8D1F0255D835F302}Common/Materials/Game/Glass/glass_2mm_min.gamemat"
FABRIC_GAMEMAT = "{5EE22D6E62DCE04A}Common/Materials/Game/Fabric/fabric_6mm_min.gamemat"
LAMINATED_GLASS_GAMEMAT = "{9CF9352E79A84A2A}Common/Materials/Game/Glass/glass_laminated_4mm.gamemat"
ARMORED_GLASS_GAMEMAT = "{7BE37DA4E6BA2358}Common/Materials/Game/GlassArmored/glass_armored_10mm.gamemat"
COMPONENT_GAMEMATS = {
    "Battery": "{5D38201F93B9DE65}Common/Materials/Game/VehicleParts/vehicle_battery.gamemat",
    "Engine": "{0B9EB7B9C8DCC6A5}Common/Materials/Game/VehicleParts/engine.gamemat",
    "FuelTank": "{2E934203697527B6}Common/Materials/Game/VehicleParts/fuel_tank.gamemat",
    "Gearbox": "{427C6C77966E41CB}Common/Materials/Game/VehicleParts/differential.gamemat",
    "Differential": "{427C6C77966E41CB}Common/Materials/Game/VehicleParts/differential.gamemat",
    "DriveShaft": "{BAD01E74E21D5031}Common/Materials/Game/VehicleParts/drive_shaft.gamemat",
}
COLLIDER_LAYER_PRESET_ITEMS = (
    ('Vehicle', "Vehicle", "Main rigid vehicle collision"),
    ('FireGeo', "FireGeo", "Damage and hit geometry"),
    ('VehicleComplex', "VehicleComplex", "Wheel slot/detail collision"),
    ('MineTrigger', "MineTrigger", "Wheel mine trigger collision"),
    ('GlassFire', "GlassFire", "Legacy/master glass fire layer"),
    ('Glass', "Glass", "Glass view/collision preset"),
    ('VehicleFire', "VehicleFire", "Vehicle fire hit layer"),
    ('VehicleFireView', "VehicleFireView", "Vehicle fire/view layer"),
    ('VehicleComplexView', "VehicleComplexView", "Vehicle complex view layer"),
    ('VehicleSimple', "VehicleSimple", "Simple vehicle layer"),
    ('VehicleRotorDisc', "VehicleRotorDisc", "Rotor disc layer"),
    ('Door', "Door", "Door interaction/collision layer"),
    ('DoorFireView', "DoorFireView", "Door fire/view layer"),
    ('FireView', "FireView", "Fire/view layer"),
    ('ViewGeo', "ViewGeo", "View geometry layer"),
    ('Interaction', "Interaction", "Interaction layer"),
    ('InteractionFireGeo', "InteractionFireGeo", "Interaction FireGeo layer"),
    ('Prop', "Prop", "Prop layer"),
    ('PropFireView', "PropFireView", "Prop fire/view layer"),
    ('Default', "Default", "Default layer preset"),
    ('None', "None", "No collision layer preset"),
)
COLLIDER_GAMEMAT_PRESETS = (
    ('NO_CHANGE', "No material change", "Keep existing material slots", ""),
    ('AUTO_POLICY', "Auto vehicle policy", "Use this addon's SampleCar vehicle policy", ""),
    ('VEHICLE_METAL', "Vehicle Metal", "Generic metal vehicle hull", VEHICLE_GAMEMAT),
    ('VEHICLE_BODY', "Vehicle Body", "Vehicle body panels", VEHICLE_BODY_GAMEMAT),
    ('VEHICLE_BOTTOM', "Vehicle Bottom Slide", "Vehicle underside/bottom slide", VEHICLE_BOTTOM_GAMEMAT),
    ('METAL_3MM', "Metal 3mm", "Thin metal FireGeo", FIREGEO_METAL_GAMEMAT),
    ('METAL_5MM', "Metal 5mm", "Wheel rim or stronger metal", WHEEL_METAL_GAMEMAT),
    ('RUBBER_TIRE', "Rubber Tire", "Generic tire rubber", TIRE_GAMEMAT),
    ('RUBBER_TIRE_4MM', "Rubber Tire 4mm", "Sample wheel VehicleComplex tire rubber", TIRE_4MM_GAMEMAT),
    ('PLASTIC_3MM', "Plastic 3mm", "Light covers, trims, plastic panels", LIGHT_PLASTIC_GAMEMAT),
    ('GLASS_2MM', "Glass 2mm", "Thin glass", THIN_GLASS_GAMEMAT),
    ('GLASS_LAMINATED', "Laminated Glass", "Default DST vehicle glass", LAMINATED_GLASS_GAMEMAT),
    ('GLASS_ARMORED', "Armored Glass", "Armored DST glass", ARMORED_GLASS_GAMEMAT),
    ('FABRIC_6MM', "Fabric 6mm", "Seats, carpet, soft interior", FABRIC_GAMEMAT),
    ('ENGINE', "Vehicle Engine", "Engine component hit material", COMPONENT_GAMEMATS["Engine"]),
    ('BATTERY', "Vehicle Battery", "Battery component hit material", COMPONENT_GAMEMATS["Battery"]),
    ('FUEL_TANK', "Fuel Tank", "Fuel tank component hit material", COMPONENT_GAMEMATS["FuelTank"]),
    ('DIFFERENTIAL', "Differential", "Differential/gearbox vehicle part", COMPONENT_GAMEMATS["Differential"]),
    ('DRIVE_SHAFT', "Drive Shaft", "Drive shaft vehicle part", COMPONENT_GAMEMATS["DriveShaft"]),
)
COLLIDER_GAMEMAT_BY_KEY = {key: resource for key, _label, _desc, resource in COLLIDER_GAMEMAT_PRESETS}
ENFUSION_LAYER_COLORS = {
    "Vehicle": (1.0, 0.42, 0.0, 0.62),
    "FireGeo": (1.0, 0.05, 0.0, 0.72),
    "GlassFire": (0.0, 0.65, 1.0, 0.62),
    "MineTrigger": (0.15, 1.0, 0.1, 0.58),
    "VehicleComplex": (1.0, 0.72, 0.05, 0.62),
}
ENFUSION_LAYER_COLORS_IDLE = {
    key: (value[0], value[1], value[2], min(value[3], 0.42))
    for key, value in ENFUSION_LAYER_COLORS.items()
}

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
    if name.startswith("UCL_VC_"):
        return "VehicleComplex"
    if name.startswith("UCX_MainCol_"):
        return "Vehicle"
    if name.startswith("UTM_VC_"):
        return "VehicleComplex"
    if name.startswith("UTM_GlassFire") or name == "UTM_Detail_Glass":
        return "GlassFire"
    if name.startswith("UTM_Glass"):
        return "FireGeo"
    if name.startswith(("UCX_FG_", "UTM_")):
        return "FireGeo"
    return "Vehicle"


def _name_has_any(name, tokens):
    lower = name.lower()
    return any(token in lower for token in tokens)


def _detail_surface_properties(name, default_metal):
    if _name_has_any(name, ("rubber", "tire", "tyre")):
        return [TIRE_4MM_GAMEMAT]
    if _name_has_any(name, ("glass", "window", "windscreen", "windshield", "lamp",
                           "lamps", "light", "led", "indicator", "blinker", "amber",
                           "mirror")):
        return [THIN_GLASS_GAMEMAT]
    if _name_has_any(name, ("plastic", "panel", "trim", "bumper", "fender_flare", "grille")):
        return [LIGHT_PLASTIC_GAMEMAT]
    if _name_has_any(name, ("fabric", "cloth", "carpet", "leather", "seat")):
        return [FABRIC_GAMEMAT]
    return [default_metal]


def _vehicle_surface_properties(name, armored_body=False):
    """SampleCar-style stock gamemat policy for generated vehicle colliders."""
    if name.startswith("UCL_MT_"):
        return [TIRE_GAMEMAT]
    if name.startswith("UCL_VC_"):
        return [TIRE_4MM_GAMEMAT]
    if name.startswith("UTM_VC_"):
        return _detail_surface_properties(name, WHEEL_METAL_GAMEMAT)
    if name.startswith(("UCX_MainCol_", "UBX_MainCol_")):
        return [VEHICLE_GAMEMAT]
    if name.startswith("UTM_FG_Wheel") and _name_has_any(name, ("tire", "tyre", "rubber")):
        return [TIRE_4MM_GAMEMAT]
    if name.startswith("UTM_FG_Wheel") and _name_has_any(name, ("rim", "hub", "middle", "metal", "inner")):
        return [WHEEL_METAL_GAMEMAT]
    if name.startswith("UTM_FG_Wheel"):
        return [TIRE_4MM_GAMEMAT, WHEEL_METAL_GAMEMAT]
    for component, resource in COMPONENT_GAMEMATS.items():
        if name in (f"UCX_FG_{component}", f"UTM_FG_{component}"):
            return [resource]
    if name.startswith(("UTM_FG_Light", "UCX_FG_Light")):
        return [LIGHT_PLASTIC_GAMEMAT]
    if name.startswith("UTM_Glass") or name == "UTM_Detail_Glass":
        return [ARMORED_GLASS_GAMEMAT if armored_body else LAMINATED_GLASS_GAMEMAT]
    if name.startswith(("UCX_FG_", "UTM_")):
        return _detail_surface_properties(name, FIREGEO_METAL_GAMEMAT)
    return []


def _gamemat_material(resource):
    from pathlib import PurePosixPath
    guid = resource[1:17] if resource.startswith("{") else ""
    path = resource.split("}", 1)[-1] if "}" in resource else resource
    stem = PurePosixPath(path).stem
    name = f"{stem}_{guid}"[:64] if guid else stem[:64]
    material = bpy.data.materials.get(name)
    if material is None:
        material = bpy.data.materials.new(name)
        material.diffuse_color = (0.95, 0.55, 0.08, 0.55)
    material["rpf_gamemat"] = resource
    material["rpf_gamemat_resource"] = resource
    material["ebt_resource_name"] = resource
    material["resourceName"] = resource
    material["ResourceName"] = resource
    try:
        material.ebt_resource_name = resource
    except Exception:
        pass
    return material


def _gamemat_resource_from_material(material):
    if material is None:
        return ""
    for key in ("rpf_gamemat", "rpf_gamemat_resource", "ebt_resource_name",
                "resourceName", "ResourceName"):
        value = material.get(key)
        if isinstance(value, str) and ".gamemat" in value:
            return value
    value = getattr(material, "ebt_resource_name", "")
    if isinstance(value, str) and ".gamemat" in value:
        return value
    name = material.name
    if ".gamemat" in name and "Common/Materials/Game/" in name:
        return name
    return ""


def _sync_collider_surface_properties(obj):
    resources = []
    if obj.type == 'MESH':
        for material in obj.data.materials:
            resource = _gamemat_resource_from_material(material)
            if resource and resource not in resources:
                resources.append(resource)
    obj["rpf_surface_properties"] = "|".join(resources)
    return resources


def _collider_layer_items(_self, _context):
    return COLLIDER_LAYER_PRESET_ITEMS


def _collider_gamemat_items(_self, _context):
    return tuple((key, label, desc) for key, label, desc, _resource in COLLIDER_GAMEMAT_PRESETS)


def _assign_collider_material_slots(obj, resources, clear=True):
    if obj.type != 'MESH':
        return []
    if clear:
        obj.data.materials.clear()
    slot_indices = []
    for resource in resources:
        material = _gamemat_material(resource)
        if material.name not in [mat.name for mat in obj.data.materials if mat]:
            obj.data.materials.append(material)
        slot_indices.append(max(0, list(obj.data.materials).index(material)))
    if clear and slot_indices:
        for polygon in obj.data.polygons:
            polygon.material_index = slot_indices[min(polygon.material_index, len(slot_indices) - 1)]
    return _sync_collider_surface_properties(obj)


def _selected_collider_objects(context):
    return [
        obj for obj in context.selected_objects
        if obj.type == 'MESH' and obj.name.startswith(COLLISION_PFX)
    ]


def _assign_selected_utm_faces_material(context, resource):
    obj = context.object
    if not obj or obj.type != 'MESH' or not obj.name.startswith("UTM_"):
        return 0
    mesh = obj.data
    material = _gamemat_material(resource)
    if material.name not in [mat.name for mat in mesh.materials if mat]:
        mesh.materials.append(material)
    material_index = list(mesh.materials).index(material)
    bm = bmesh.from_edit_mesh(mesh)
    count = 0
    for face in bm.faces:
        if face.select:
            face.material_index = material_index
            count += 1
    bmesh.update_edit_mesh(mesh)
    _sync_collider_surface_properties(obj)
    return count


def _apply_vehicle_collision_materials(obj, armored_body=False):
    usage = _collider_usage(obj.name)
    resources = _vehicle_surface_properties(obj.name, armored_body)
    _place_ebt_collider(obj, usage)
    obj["usage"] = usage
    if not resources:
        _sync_collider_surface_properties(obj)
        return usage, []
    _assign_collider_material_slots(obj, resources, clear=True)
    return usage, resources


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
    obj.color = ENFUSION_LAYER_COLORS_IDLE.get(usage, (1.0, 0.5, 0.0, 0.4))
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


GLASS_FACE_MAT_TOKENS = (
    "glass", "window", "windscreen", "windshield", "clear", "transparent",
    "translucent", "lens",
)


def _material_index_has_tokens(obj, material_index, tokens):
    if material_index < 0 or material_index >= len(obj.data.materials):
        return False
    material = obj.data.materials[material_index]
    name = material.name.lower() if material else ""
    return any(token in name for token in tokens)


def _copy_face_subset(obj, name, tokens, *, side=None, include_matching=True):
    """Copy only matching material faces from one mesh, preserving UV/custom data.

    `side` is vehicle local/world X side: "L" keeps x < 0, "R" keeps x >= 0.
    If the object itself is named as glass/window but materials are generic, the
    object name is accepted as the match source so finalized mixed parts still
    produce DST panes.
    """
    if not obj or obj.type != 'MESH' or not obj.data.polygons:
        return None
    object_is_glass = _is_glass_part(obj.name) or _is_glass_part(part_of(obj) or "")
    mesh = obj.data.copy()
    copy = bpy.data.objects.new(name, mesh)
    bpy.context.scene.collection.objects.link(copy)
    copy.matrix_world = obj.matrix_world.copy()
    for vertex_group in list(copy.vertex_groups):
        copy.vertex_groups.remove(vertex_group)
    for modifier in list(copy.modifiers):
        copy.modifiers.remove(modifier)

    bm = bmesh.new()
    bm.from_mesh(mesh)
    bm.faces.ensure_lookup_table()
    keep = []
    for face in bm.faces:
        match = _material_index_has_tokens(obj, face.material_index, tokens) or object_is_glass
        if include_matching != match:
            continue
        if side:
            center = obj.matrix_world @ face.calc_center_median()
            if side == "L" and center.x >= 0:
                continue
            if side == "R" and center.x < 0:
                continue
        keep.append(face)
    if not keep:
        bm.free()
        bpy.data.objects.remove(copy, do_unlink=True)
        return None
    delete = [face for face in bm.faces if face not in keep]
    if delete:
        bmesh.ops.delete(bm, geom=delete, context='FACES')
    bm.to_mesh(mesh)
    bm.free()
    mesh.update()
    if not mesh.polygons:
        bpy.data.objects.remove(copy, do_unlink=True)
        return None
    return copy


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


def _selected_face_temp_objects(context, split_loose=True):
    """Copy Edit Mode selected faces into temporary world-space mesh objects.

    This deliberately mirrors the manual workflow that works well on vehicles:
    select a curved/hard-edged shell area, separate that region, then convexify it.
    The original mesh is not modified.
    """
    source = context.edit_object
    if not source or source.type != 'MESH' or context.mode != 'EDIT_MESH':
        return [], None
    bm = bmesh.from_edit_mesh(source.data)
    selected = [face for face in bm.faces if face.select]
    if not selected:
        return [], source
    islands = []
    if split_loose:
        remaining = set(selected)
        while remaining:
            seed = remaining.pop()
            stack = [seed]
            island = [seed]
            while stack:
                face = stack.pop()
                for edge in face.edges:
                    for other in edge.link_faces:
                        if other in remaining:
                            remaining.remove(other)
                            stack.append(other)
                            island.append(other)
            islands.append(island)
    else:
        islands = [selected]

    made = []
    for idx, faces in enumerate(islands, 1):
        vert_map = {}
        verts = []
        out_faces = []
        for face in faces:
            indices = []
            for vert in face.verts:
                if vert not in vert_map:
                    vert_map[vert] = len(verts)
                    verts.append(tuple(source.matrix_world @ vert.co))
                indices.append(vert_map[vert])
            if len(indices) >= 3:
                out_faces.append(indices)
        if len(verts) < 4 or not out_faces:
            continue
        mesh = bpy.data.meshes.new(f"_rpf_selected_faces_{idx:02d}")
        mesh.from_pydata(verts, [], out_faces)
        mesh.update(calc_edges=True)
        obj = bpy.data.objects.new(mesh.name, mesh)
        bpy.context.scene.collection.objects.link(obj)
        obj["rpf_temp_selected_faces"] = True
        obj["rpf_source_object"] = source.name
        made.append(obj)
    return made, source


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
        default=False,
        description="Remove prior selected-part UCX hulls generated by this tool",
    )

    def execute(self, context):
        temp_sources = []
        edit_source = None
        if context.mode == 'EDIT_MESH':
            temp_sources, edit_source = _selected_face_temp_objects(context, True)
            if not temp_sources:
                self.report({'ERROR'}, "Select faces first, or switch to Object Mode for whole-part convex")
                return {'CANCELLED'}
            bpy.ops.object.mode_set(mode='OBJECT')
            sources = temp_sources
        else:
            if context.mode != 'OBJECT':
                bpy.ops.object.mode_set(mode='OBJECT')
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
        for source_i, source in enumerate(sources, 1):
            source_name = edit_source.name if edit_source else source.name
            suffix = f"_sel{source_i:02d}" if edit_source else ""
            name = f"UCX_MainCol_{index:02d}_{_safe_name_token(source_name)}{suffix}"
            hull = _part_convex_hull(source, name, self.max_faces)
            if hull is None:
                skipped.append(source_name)
                continue
            if edit_source:
                hull["rpf_ucx_source"] = edit_source.name
                hull["rpf_ucx_selection_source"] = edit_source.name
            made.append(hull)
            index += 1

        for temp in temp_sources:
            if temp.name in bpy.data.objects:
                bpy.data.objects.remove(temp, do_unlink=True)

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


def _vhacd_props_from_scene(scene):
    return {
        "max_hulls": scene.rpf_ucx_max_hulls,
        "resolution": scene.rpf_vhacd_resolution,
        "volume_error": scene.rpf_vhacd_volume_error,
        "recursion_depth": scene.rpf_vhacd_recursion_depth,
        "shrink_wrap": scene.rpf_vhacd_shrinkwrap,
        "fill_mode": scene.rpf_vhacd_fill_mode,
        "max_vertices": scene.rpf_vhacd_max_vertices,
        "min_edge_length": scene.rpf_vhacd_min_edge_length,
        "split_hulls": scene.rpf_vhacd_split_hulls,
        "pre_scale": scene.rpf_vhacd_pre_scale,
    }


class RPF_OT_selected_faces_to_ucx(bpy.types.Operator):
    bl_idname = "rpf.selected_faces_to_ucx"
    bl_label = "Edit Selection -> UCX"
    bl_description = ("Edit Mode workflow: select vehicle shell faces, then create "
                      "controlled convex UCX_MainCol hulls from only that region. "
                      "Split selected loose islands to follow curves and hard edges")
    bl_options = {'REGISTER', 'UNDO'}

    use_decomposition: bpy.props.BoolProperty(name="Use decomposition", default=True)
    split_loose: bpy.props.BoolProperty(name="Split loose islands", default=True)
    replace_generated: bpy.props.BoolProperty(name="Replace prior selection hulls", default=False)

    def execute(self, context):
        if context.mode != 'EDIT_MESH':
            self.report({'ERROR'}, "Enter Edit Mode and select faces on the vehicle shell")
            return {'CANCELLED'}
        temp_objects, source = _selected_face_temp_objects(context, self.split_loose)
        if not temp_objects:
            self.report({'ERROR'}, "No selected faces found")
            return {'CANCELLED'}
        checkpoint("pre_selected_faces_ucx")
        if self.replace_generated:
            for obj in list(bpy.data.objects):
                if obj.get("rpf_ucx_selection_source"):
                    bpy.data.objects.remove(obj, do_unlink=True)
        bpy.ops.object.mode_set(mode='OBJECT')
        made = []
        backend_used = "convex-fallback"
        index = _next_main_col_index()
        props = _vhacd_props_from_scene(context.scene)
        exe = context.scene.rpf_vhacd_exe
        backend = context.scene.rpf_ucx_backend
        for region_idx, temp in enumerate(temp_objects, 1):
            verts, faces = _world_tris(temp)
            verts, faces = _reduce_mesh(verts, faces, context.scene.rpf_ucx_decimate)
            hulls = None
            if _too_dense_for_decomposition(len(faces), context.scene.rpf_ucx_decimate):
                backend_used = "convex-fallback:dense-open-input"
                print(
                    f"RPF V-HACD: selected face region still has {len(faces)} tris; using capped convex fallback",
                    flush=True,
                )
            elif self.use_decomposition and backend != 'FALLBACK':
                backend_used, hulls = _decompose_hulls(
                    verts,
                    faces,
                    context.scene.rpf_ucx_concavity,
                    exe,
                    backend,
                    props,
                )
            token = _safe_name_token(source.name if source else "selection")
            if not hulls:
                obj = _capped_hull_obj(
                    f"UCX_MainCol_{index:02d}_{token}_sel{region_idx:02d}",
                    verts,
                    context.scene.rpf_ucx_max_faces,
                )
                if obj:
                    obj["rpf_ucx_source"] = source.name if source else ""
                    obj["rpf_ucx_selection_source"] = source.name if source else ""
                    obj["rpf_ucx_face_cap"] = context.scene.rpf_ucx_max_faces
                    _place_ebt_collider(obj, "Vehicle")
                    _apply_vehicle_collision_materials(obj)
                    made.append(obj)
                    index += 1
                continue
            selected_hulls = _select_representative_hulls(
                hulls,
                context.scene.rpf_ucx_max_hulls,
                f"{token}_selected_faces",
            )
            for hull_idx, points in enumerate(selected_hulls):
                obj = _capped_hull_obj(
                    f"UCX_MainCol_{index:02d}_{token}_sel{region_idx:02d}_{hull_idx:02d}",
                    points,
                    context.scene.rpf_ucx_max_faces,
                )
                if not obj:
                    continue
                obj["rpf_ucx_source"] = source.name if source else ""
                obj["rpf_ucx_selection_source"] = source.name if source else ""
                obj["rpf_ucx_face_cap"] = context.scene.rpf_ucx_max_faces
                _place_ebt_collider(obj, "Vehicle")
                _apply_vehicle_collision_materials(obj)
                made.append(obj)
                index += 1
        for temp in temp_objects:
            bpy.data.objects.remove(temp, do_unlink=True)
        bpy.ops.object.select_all(action='DESELECT')
        for obj in made:
            obj.select_set(True)
            obj.display_type = 'SOLID'
            obj.show_in_front = True
        if made:
            context.view_layer.objects.active = made[0]
        self.report(
            {'INFO'} if made else {'ERROR'},
            f"{backend_used}: {len(made)} UCX hulls from selected faces",
        )
        return {'FINISHED'} if made else {'CANCELLED'}


class RPF_OT_apply_collision_materials(bpy.types.Operator):
    bl_idname = "rpf.apply_collision_materials"
    bl_label = "Fix Layer + Gamemats"
    bl_description = ("Apply SampleCar vehicle layer presets and stock gamemat material "
                      "slots to selected colliders, or every collider if none selected")
    bl_options = {'REGISTER', 'UNDO'}

    selected_only: bpy.props.BoolProperty(name="Selected only", default=False)
    armored_body: bpy.props.BoolProperty(name="Armored body/glass", default=False)

    def execute(self, context):
        selected = [obj for obj in context.selected_objects
                    if obj.type == 'MESH' and obj.name.startswith(COLLISION_PFX)]
        targets = selected if (self.selected_only or selected) else _collision_objects()
        if not targets:
            self.report({'ERROR'}, "No collision objects found")
            return {'CANCELLED'}
        fixed = []
        missing = []
        for obj in targets:
            usage, resources = _apply_vehicle_collision_materials(obj, self.armored_body)
            fixed.append((obj.name, usage, len(resources)))
            if not resources:
                missing.append(obj.name)
        print("RPF COLLISION MATERIALS:",
              [{"name": name, "usage": usage, "surfaces": count}
               for name, usage, count in fixed])
        msg = f"fixed {len(fixed)} collider layer/material assignments"
        if missing:
            msg += f"; {len(missing)} had no gamemat rule"
        self.report({'INFO'}, msg)
        return {'FINISHED'}


class RPF_OT_collider_setup(bpy.types.Operator):
    bl_idname = "rpf.collider_setup"
    bl_label = "Collider Setup"
    bl_description = ("Assign an Enfusion layer preset and stock game material to selected "
                      "colliders. In Edit Mode on UTM meshes, only selected faces get the gamemat")
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        if context.mode == 'EDIT_MESH':
            obj = context.object
            return bool(obj and obj.type == 'MESH' and obj.name.startswith("UTM_"))
        return any(obj.type == 'MESH' and obj.name.startswith(COLLIDER_PFX)
                   for obj in context.selected_objects)

    def execute(self, context):
        scene = context.scene
        layer = scene.rpf_collider_setup_layer
        material_key = scene.rpf_collider_setup_gamemat
        sort = scene.rpf_collider_setup_sort
        resource = COLLIDER_GAMEMAT_BY_KEY.get(material_key, "")

        if context.mode == 'EDIT_MESH':
            obj = context.object
            if not obj or obj.type != 'MESH' or not obj.name.startswith("UTM_"):
                self.report({'ERROR'}, "Edit Mode collider setup needs an active UTM mesh")
                return {'CANCELLED'}
            obj["usage"] = layer
            if material_key == 'AUTO_POLICY':
                self.report({'ERROR'}, "Auto vehicle policy works in Object Mode; choose a specific gamemat for selected UTM faces")
                return {'CANCELLED'}
            face_count = 0
            if resource:
                face_count = _assign_selected_utm_faces_material(context, resource)
                if face_count == 0:
                    self.report({'ERROR'}, "No selected UTM faces to assign")
                    return {'CANCELLED'}
            else:
                _sync_collider_surface_properties(obj)
            self.report({'INFO'}, f"{obj.name}: {layer}, {face_count} selected faces")
            return {'FINISHED'}

        targets = _selected_collider_objects(context)
        if not targets:
            self.report({'ERROR'}, "Select one or more collider objects")
            return {'CANCELLED'}

        for obj in targets:
            if material_key == 'AUTO_POLICY':
                _apply_vehicle_collision_materials(obj, scene.rpf_collider_setup_armored)
                continue
            obj["usage"] = layer
            if sort:
                _place_ebt_collider(obj, layer)
            else:
                obj.color = ENFUSION_LAYER_COLORS_IDLE.get(layer, (1.0, 0.5, 0.0, 0.4))
            if resource:
                _assign_collider_material_slots(obj, [resource], clear=True)
            else:
                _sync_collider_surface_properties(obj)

        self.report({'INFO'}, f"collider setup applied to {len(targets)} object(s)")
        return {'FINISHED'}


def _object_tri_count(obj):
    if obj.type != 'MESH':
        return 0
    mesh = obj.data
    mesh.calc_loop_triangles()
    return len(mesh.loop_triangles)


def _mesh_boundary_ratio(obj):
    """Approximate openness from boundary edges. Open shells need safer settings."""
    if obj.type != 'MESH' or not obj.data.polygons:
        return 0.0
    counts = {}
    for poly in obj.data.polygons:
        verts = list(poly.vertices)
        for a, b in zip(verts, verts[1:] + verts[:1]):
            key = tuple(sorted((a, b)))
            counts[key] = counts.get(key, 0) + 1
    if not counts:
        return 0.0
    boundary = sum(1 for count in counts.values() if count == 1)
    return boundary / max(len(counts), 1)


def _bbox_span_for_objects(objects):
    mn = Vector((1e9, 1e9, 1e9))
    mx = Vector((-1e9, -1e9, -1e9))
    for obj in objects:
        a, b = wbbox(obj)
        mn.x = min(mn.x, a.x); mn.y = min(mn.y, a.y); mn.z = min(mn.z, a.z)
        mx.x = max(mx.x, b.x); mx.y = max(mx.y, b.y); mx.z = max(mx.z, b.z)
    return mx - mn


class RPF_OT_autotune_collision_settings(bpy.types.Operator):
    bl_idname = "rpf.autotune_collision_settings"
    bl_label = "Auto Tune From Mesh"
    bl_description = ("Read selected mesh/parts and set VHACD/CoACD controls for that "
                      "input. Full open body shells get broader stable settings; small "
                      "selected panels get tighter settings")
    bl_options = {'REGISTER', 'UNDO'}

    scope: bpy.props.EnumProperty(
        name="Scope",
        default='SELECTED',
        items=[
            ('SELECTED', "Selected", "Tune from selected render meshes"),
            ('VISIBLE', "Visible", "Tune from visible render meshes if nothing is selected"),
        ],
    )

    def execute(self, context):
        selected = [
            obj for obj in context.selected_objects
            if obj.type == 'MESH' and not obj.name.startswith(COLLIDER_PFX)
        ]
        if selected:
            sources = selected
            source_label = "selected"
        else:
            sources = [
                obj for obj in context.scene.objects
                if obj.type == 'MESH' and not obj.name.startswith(COLLIDER_PFX)
                and not obj.hide_get()
            ]
            source_label = "visible"
        if not sources:
            self.report({'ERROR'}, "Select render mesh parts first, or show the render mesh")
            return {'CANCELLED'}

        tri_count = sum(_object_tri_count(obj) for obj in sources)
        open_ratio = max((_mesh_boundary_ratio(obj) for obj in sources), default=0.0)
        span = _bbox_span_for_objects(sources)
        max_dim = max(span.x, span.y, span.z, 0.001)
        volume = max(span.x, 0.001) * max(span.y, 0.001) * max(span.z, 0.001)
        text = " ".join(_object_semantic_text(obj) for obj in sources)
        small_region = len(sources) <= 2 and max_dim < 2.2 and tri_count < 35000
        detail_surface = (
            _is_glass_part(text) or _is_light_part(text) or _is_wheel_part(text)
            or any(token in text for token in ("seat", "interior", "carpet", "belt"))
        )

        sc = context.scene
        sc.rpf_ucx_backend = 'AUTO'
        sc.rpf_ucx_max_faces = 200
        sc.rpf_vhacd_pre_scale = 1.0
        sc.rpf_vhacd_shrinkwrap = True
        sc.rpf_vhacd_fill_mode = 'flood'
        sc.rpf_vhacd_min_edge_length = 2
        sc.rpf_vhacd_volume_error = 1.0

        if detail_surface:
            sc.rpf_ucx_max_hulls = 12
            sc.rpf_ucx_decimate = min(2500, max(800, tri_count // 8 or 800))
            sc.rpf_ucx_concavity = 0.12
            sc.rpf_vhacd_resolution = 60000
            sc.rpf_vhacd_recursion_depth = 8
            sc.rpf_vhacd_max_vertices = 48
            sc.rpf_vhacd_split_hulls = False
            advice = "detail surface: prefer Selected -> FireGeo/VehicleComplex over main UCX"
        elif small_region:
            sc.rpf_ucx_max_hulls = 18 if open_ratio > 0.08 else 12
            sc.rpf_ucx_decimate = min(3000, max(1200, tri_count // 3 or 1200))
            sc.rpf_ucx_concavity = 0.055 if open_ratio < 0.06 else 0.075
            sc.rpf_vhacd_resolution = 120000
            sc.rpf_vhacd_recursion_depth = 10
            sc.rpf_vhacd_max_vertices = 64
            sc.rpf_vhacd_split_hulls = True
            advice = "small region: use Edit Faces -> UCX or V-HACD selected"
        elif tri_count > 60000 or open_ratio > 0.08 or volume > 6.0:
            sc.rpf_ucx_max_hulls = 48
            sc.rpf_ucx_decimate = 3500
            sc.rpf_ucx_concavity = 0.09
            sc.rpf_vhacd_resolution = 90000
            sc.rpf_vhacd_recursion_depth = 10
            sc.rpf_vhacd_max_vertices = 64
            sc.rpf_vhacd_split_hulls = False
            advice = "large/open shell: broad pass only, then refine by selected regions"
        else:
            sc.rpf_ucx_max_hulls = 32
            sc.rpf_ucx_decimate = 4000
            sc.rpf_ucx_concavity = 0.075
            sc.rpf_vhacd_resolution = 100000
            sc.rpf_vhacd_recursion_depth = 10
            sc.rpf_vhacd_max_vertices = 64
            sc.rpf_vhacd_split_hulls = True
            advice = "medium body part: selected V-HACD is appropriate"

        sc["rpf_autotune_summary"] = (
            f"{source_label}: {len(sources)} mesh(es), {tri_count:,} tris, "
            f"open {open_ratio:.2f}, span {[round(v, 2) for v in span]} -> {advice}"
        )
        print("RPF AUTO TUNE:", sc["rpf_autotune_summary"])
        self.report({'INFO'}, sc["rpf_autotune_summary"][:240])
        return {'FINISHED'}


def _join_bare_copies(objs, name):
    """Bare-copy (no vgroups/modifiers) and join a list of meshes into one object."""
    copies = []
    for o in objs:
        c = bpy.data.objects.new(f"_jbc_{o.name}", o.data.copy())
        bpy.context.scene.collection.objects.link(c)
        c.matrix_world = o.matrix_world.copy()
        for vg in list(c.vertex_groups):
            c.vertex_groups.remove(vg)
        for m in list(c.modifiers):
            c.modifiers.remove(m)
        copies.append(c)
    if not copies:
        return None
    bpy.ops.object.select_all(action='DESELECT')
    for c in copies:
        c.select_set(True)
    bpy.context.view_layer.objects.active = copies[0]
    if len(copies) > 1:
        bpy.ops.object.join()
    joined = bpy.context.view_layer.objects.active
    joined.name = name
    return joined


class RPF_OT_selected_to_direct_collision(bpy.types.Operator):
    bl_idname = "rpf.selected_to_direct_collision"
    bl_label = "Selected -> Direct Collision Copy"
    bl_description = ("Duplicate selected render meshes as exact-position Enfusion "
                      "collision/detail geometry. Best for FireGeo, DST glass, light "
                      "covers, and wheel/detail hit surfaces. Main Vehicle physics "
                      "should still use convex UCX hulls")
    bl_options = {'REGISTER', 'UNDO'}

    mode: bpy.props.EnumProperty(
        name="Target Layer",
        default='FIREGEO',
        items=[
            ('UCXVEHICLE', "UCX Vehicle", "Copy selected surfaces to UCX_MainCol_* on Vehicle; validate/convexify before export"),
            ('FIREGEO', "FireGeo", "Copy selected surfaces to UTM_FG_* on FireGeo"),
            ('GLASSFIRE', "GlassFire", "Copy selected surfaces to UTM_GlassFire_* on GlassFire"),
            ('VEHICLECOMPLEX', "VehicleComplex", "Copy selected surfaces to UTM_VC_* on VehicleComplex"),
        ],
    )
    decimate_ratio: bpy.props.FloatProperty(
        name="Decimate Ratio",
        default=1.0,
        min=0.01,
        max=1.0,
        precision=3,
        description="1.0 keeps the selected mesh exactly; lower values reduce FireGeo/detail cost",
    )
    merge_selected: bpy.props.BoolProperty(
        name="Merge Selected",
        default=False,
        description="Join all selected copies into one collider object instead of one per source mesh",
    )
    replace_previous: bpy.props.BoolProperty(
        name="Replace Previous Direct Copies",
        default=False,
        description="Remove prior colliders made by this exact-copy tool before creating new ones",
    )

    def _target(self):
        if self.mode == 'UCXVEHICLE':
            return "Vehicle", "UCX_MainCol"
        if self.mode == 'GLASSFIRE':
            return "GlassFire", "UTM_GlassFire"
        if self.mode == 'VEHICLECOMPLEX':
            return "VehicleComplex", "UTM_VC"
        return "FireGeo", "UTM_FG"

    def _copy_name(self, prefix, source, index, base_ucx_index):
        token = _safe_name_token(source.get("rpf_source_object", source.name))
        if self.mode == 'UCXVEHICLE':
            return f"{prefix}_{base_ucx_index + index - 1:02d}_{token}_copy"
        return f"{prefix}_{token}_{index:02d}"

    def _copy_source(self, source, name):
        obj = bpy.data.objects.new(name, source.data.copy())
        bpy.context.scene.collection.objects.link(obj)
        obj.matrix_world = source.matrix_world.copy()
        for vg in list(obj.vertex_groups):
            obj.vertex_groups.remove(vg)
        for modifier in list(obj.modifiers):
            obj.modifiers.remove(modifier)
        if self.decimate_ratio < 0.999:
            dec = obj.modifiers.new("RPF_DIRECT_COPY_DECIMATE", 'DECIMATE')
            dec.ratio = self.decimate_ratio
            bpy.ops.object.select_all(action='DESELECT')
            obj.select_set(True)
            bpy.context.view_layer.objects.active = obj
            try:
                bpy.ops.object.modifier_apply(modifier=dec.name)
            except RuntimeError:
                obj.modifiers.remove(dec)
        return obj

    def execute(self, context):
        temp_sources = []
        if context.mode == 'EDIT_MESH':
            temp_sources, _source = _selected_face_temp_objects(context, True)
            if not temp_sources:
                self.report({'ERROR'}, "Select faces first, or switch to Object Mode for whole-mesh copy")
                return {'CANCELLED'}
            bpy.ops.object.mode_set(mode='OBJECT')
            sources = temp_sources
        else:
            sources = [
                obj for obj in context.selected_objects
                if obj.type == 'MESH' and not obj.name.startswith(COLLIDER_PFX)
            ]
        if not sources:
            self.report({'ERROR'}, "Select one or more render meshes to duplicate as collision")
            return {'CANCELLED'}
        checkpoint("pre_direct_collision_copy")
        if self.replace_previous:
            for obj in list(bpy.data.objects):
                if obj.get("rpf_direct_collision_copy"):
                    bpy.data.objects.remove(obj, do_unlink=True)

        # UCX vehicle physics colliders MUST be convex. Build guaranteed-convex,
        # face-capped, outlier-rejected hulls from the selection (one per part, or a
        # single hull when Merge Selected is on) so "Selected -> UCX" yields valid
        # colliders directly instead of a non-convex raw copy.
        if self.mode == 'UCXVEHICLE':
            hull_sources, temp_merge = sources, None
            if self.merge_selected and len(sources) > 1:
                temp_merge = _join_bare_copies(sources, "UCX_copy_merge_src")
                if temp_merge:
                    hull_sources = [temp_merge]
            made = []
            idx = _next_main_col_index()
            for src in hull_sources:
                token = _safe_name_token(src.get("rpf_source_object", src.name))
                hull = _part_convex_hull(src, f"UCX_MainCol_{idx:02d}_{token}_copy", 200)
                if hull is None:
                    continue
                hull["rpf_direct_collision_copy"] = True
                hull["rpf_collision_source"] = src.name
                hull["rpf_collision_copy_mode"] = self.mode
                _apply_vehicle_collision_materials(hull)
                hull.display_type = 'SOLID'; hull.show_in_front = True
                made.append(hull); idx += 1
            if temp_merge and temp_merge.name in bpy.data.objects:
                bpy.data.objects.remove(temp_merge, do_unlink=True)
            for temp in temp_sources:
                if temp.name in bpy.data.objects:
                    bpy.data.objects.remove(temp, do_unlink=True)
            bpy.ops.object.select_all(action='DESELECT')
            for o in made:
                o.select_set(True)
            if made:
                context.view_layer.objects.active = made[0]
            faces = sum(len(o.data.polygons) for o in made)
            self.report({'INFO'} if made else {'ERROR'},
                        f"{len(made)} convex UCX collider(s), {faces:,} faces (<=200, validated convex)")
            print("RPF UCX COPY:", [o.name for o in made])
            return {'FINISHED'} if made else {'CANCELLED'}

        usage, prefix = self._target()
        base_ucx_index = _next_main_col_index()
        copies = []
        for index, source in enumerate(sources, 1):
            name = self._copy_name(prefix, source, index, base_ucx_index)
            copy = self._copy_source(source, name)
            copy["rpf_direct_collision_copy"] = True
            copy["rpf_collision_source"] = source.name
            copy["rpf_collision_copy_mode"] = self.mode
            copies.append(copy)
        if self.merge_selected and len(copies) > 1:
            bpy.ops.object.select_all(action='DESELECT')
            for obj in copies:
                obj.select_set(True)
            context.view_layer.objects.active = copies[0]
            bpy.ops.object.join()
            merged = context.view_layer.objects.active
            if self.mode == 'UCXVEHICLE':
                merged.name = f"{prefix}_{base_ucx_index:02d}_Selected_{_safe_name_token(sources[0].name)}"
            else:
                merged.name = f"{prefix}_Selected_{_safe_name_token(sources[0].name)}"
            merged["rpf_direct_collision_copy"] = True
            merged["rpf_collision_source"] = ",".join(source.name for source in sources[:24])
            merged["rpf_collision_copy_mode"] = self.mode
            copies = [merged]
        for temp in temp_sources:
            if temp.name in bpy.data.objects:
                bpy.data.objects.remove(temp, do_unlink=True)
        for obj in copies:
            _place_ebt_collider(obj, usage)
            _apply_vehicle_collision_materials(obj)
            obj.display_type = 'SOLID'
            obj.show_wire = False
            obj.show_all_edges = False
            obj.show_in_front = True
        bpy.ops.object.select_all(action='DESELECT')
        for obj in copies:
            obj.select_set(True)
        context.view_layer.objects.active = copies[0]
        faces = sum(len(obj.data.polygons) for obj in copies)
        note = "; run Validate/Fix UCX before export" if self.mode == 'UCXVEHICLE' else ""
        self.report({'INFO'}, f"{len(copies)} {usage} direct copy object(s), {faces:,} faces{note}")
        print("RPF DIRECT COLLISION COPY:",
              {"usage": usage, "objects": [obj.name for obj in copies], "faces": faces})
        return {'FINISHED'}


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
            ('UCX', "UCX", "Vehicle physics with model"),
            ('FIRE', "FireGeo", "FireGeo and GlassFire with model"),
            ('GLASS', "Glass", "Glass collision with model"),
            ('WHEELS', "All Wheel", "All wheel VehicleComplex, MineTrigger and FireGeo collision with model"),
            ('WHEEL_VC', "VehicleComplex", "All VehicleComplex collision, including UCL_VC wheel slots and UTM_VC detail copies"),
            ('WHEEL_FG', "Wheel FireGeo", "Wheel FireGeo tire/rim hit geometry only"),
            ('WHEEL_MT', "MineTrigger", "Wheel mine-trigger collision only"),
            ('ALL', "All", "All render and collision sections"),
        ],
        default='UCX',
    )

    def execute(self, context):
        collider_prefixes = ("UCX_", "UBX_", "UCL_", "UTM_", "USP_", "UCS_")
        wheel_modes = {'WHEELS', 'WHEEL_VC', 'WHEEL_FG', 'WHEEL_MT'}
        solid_review_modes = {'UCX', 'FIRE', 'GLASS', 'WHEELS', 'WHEEL_VC', 'WHEEL_FG', 'WHEEL_MT', 'ALL'}
        for obj in bpy.data.objects:
            if obj.type != 'MESH':
                continue
            name = obj.name
            is_collider = obj.name.startswith(collider_prefixes)
            usage = obj.get("usage", "")
            if not is_collider:
                visible = True
                obj.display_type = 'TEXTURED' if self.mode in {'MODEL', 'UCX'} else 'WIRE'
                obj.show_in_front = False
            elif self.mode == 'MODEL':
                visible = False
            elif self.mode == 'UCX':
                visible = usage == "Vehicle"
            elif self.mode == 'FIRE':
                visible = usage in {"FireGeo", "GlassFire"}
            elif self.mode == 'GLASS':
                visible = name.startswith(("UTM_Glass", "UTM_GlassFire")) or usage == "GlassFire"
            elif self.mode == 'WHEELS':
                visible = (
                    name.startswith(("UCL_MT_wheel", "UCL_VC_wheel", "UTM_FG_Wheel"))
                    or (usage in {"MineTrigger", "VehicleComplex"} and "wheel" in name.lower())
                )
            elif self.mode == 'WHEEL_VC':
                visible = name.startswith(("UCL_VC_", "UTM_VC_")) or usage == "VehicleComplex"
            elif self.mode == 'WHEEL_FG':
                visible = name.startswith("UTM_FG_Wheel") or (usage == "FireGeo" and "wheel" in name.lower())
            elif self.mode == 'WHEEL_MT':
                visible = name.startswith("UCL_MT_wheel") or (usage == "MineTrigger" and "wheel" in name.lower())
            else:
                visible = True
            obj.hide_set(not visible)
            if is_collider:
                obj.show_wire = visible and self.mode == 'UCX'
                obj.show_all_edges = visible and self.mode == 'UCX'
                obj.show_in_front = visible
                obj.color = ENFUSION_LAYER_COLORS.get(usage, obj.color)
                obj.display_type = 'SOLID' if visible and self.mode in solid_review_modes else 'WIRE'
                if visible and self.mode in {'FIRE', 'GLASS'} | wheel_modes:
                    obj.show_wire = False
                    obj.show_all_edges = False
        for area in context.screen.areas:
            if area.type != 'VIEW_3D':
                continue
            for space in area.spaces:
                if space.type != 'VIEW_3D':
                    continue
                space.shading.type = 'SOLID'
                space.shading.color_type = 'OBJECT'
                space.shading.show_xray = self.mode in {'FIRE', 'GLASS'} | wheel_modes
                space.shading.xray_alpha = 0.35
                if self.mode in {'FIRE', 'GLASS'} | wheel_modes:
                    space.overlay.show_wireframes = False
                    space.overlay.wireframe_opacity = 0.0
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
            for name in ("Vehicle", "MineTrigger", "VehicleComplex", "FireGeo", "GlassFire"):
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
    view_layer = bpy.context.view_layer
    selected_before = [o for o in view_layer.objects if o.select_get()]
    active_before = view_layer.objects.active
    # Do not use bpy.ops.object.select_all here. When the export operator is
    # launched from Blender side panels or Workbench-driven contexts, that
    # operator can fail its poll even though object data selection is valid.
    for o in view_layer.objects:
        try:
            o.select_set(False)
        except RuntimeError:
            pass
    for o in export_objs:
        o.hide_viewport = False
        o.hide_select = False
        o.hide_set(False)
        o.select_set(True)
    view_layer.objects.active = export_objs[0]
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
        for o in view_layer.objects:
            try:
                o.select_set(False)
            except RuntimeError:
                pass
        for o in selected_before:
            if o.name in bpy.data.objects:
                try:
                    o.select_set(True)
                except RuntimeError:
                    pass
        if active_before and active_before.name in bpy.data.objects:
            view_layer.objects.active = active_before
        for o, (was_hidden, was_viewport_hidden, was_select_locked) in hidden.items():
            o.hide_select = was_select_locked
            o.hide_viewport = was_viewport_hidden
            o.hide_set(was_hidden)
    return path


def _material_named(name):
    mat = bpy.data.materials.get(name)
    if mat is None:
        mat = bpy.data.materials.new(name)
    return mat


def _temporary_master_material_overrides(objs):
    """Return a restore callback after applying export-only material policy.

    Workbench's Materials panel groups by material name, not Blender part name.
    If an object named/collected as `interior` still has body/bottom material
    slots on many faces, Workbench will show those faces under body/bottom and
    the `interior` isolate looks like only a few door cards. Coerce the master
    FBX export copy path by temporarily making interior-part faces use the
    `interior` source material, then restore the Blender scene immediately.
    """
    backups = []
    for obj in objs:
        if not obj or obj.type != 'MESH':
            continue
        if obj.name.startswith(COLLIDER_PFX):
            continue
        part = (part_of(obj) or obj.name.split(".", 1)[0]).lower()
        if part != "interior":
            continue
        mesh = obj.data
        backups.append((
            obj,
            [material for material in mesh.materials],
            [polygon.material_index for polygon in mesh.polygons],
        ))
        mesh.materials.clear()
        mesh.materials.append(_material_named("interior"))
        for polygon in mesh.polygons:
            polygon.material_index = 0

    def restore():
        for obj, materials, indices in backups:
            if obj.name not in bpy.data.objects:
                continue
            mesh = obj.data
            mesh.materials.clear()
            for material in materials:
                mesh.materials.append(material)
            for polygon, index in zip(mesh.polygons, indices):
                polygon.material_index = index

    return restore


def _ensure_mesh_uvs(obj):
    """Ensure generated slot/collider meshes import with texture coordinates.

    Do not touch existing UV maps. Wheel slot export uses real visual wheel
    meshes, and rebuilding those UVs destroys the tire/rim texture layout.
    """
    if not obj or obj.type != 'MESH' or not obj.data.vertices or not obj.data.polygons:
        return
    mesh = obj.data
    if mesh.uv_layers:
        return
    mesh.uv_layers.new(name="UVMap")
    layer = mesh.uv_layers.active
    coords = [vertex.co for vertex in mesh.vertices]
    mins = [min(co[i] for co in coords) for i in range(3)]
    maxs = [max(co[i] for co in coords) for i in range(3)]
    spans = [max(maxs[i] - mins[i], 1e-6) for i in range(3)]
    axes = sorted(range(3), key=lambda axis: spans[axis], reverse=True)[:2]
    axis_u, axis_v = axes[0], axes[1]
    for polygon in mesh.polygons:
        for loop_index in polygon.loop_indices:
            co = mesh.vertices[mesh.loops[loop_index].vertex_index].co
            layer.data[loop_index].uv = (
                (co[axis_u] - mins[axis_u]) / spans[axis_u],
                (co[axis_v] - mins[axis_v]) / spans[axis_v],
            )


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


def _centered_visual_copy(src, name):
    """Duplicate visual mesh around its world bbox center for slot FBX export.

    The source object is never moved. This bakes evaluated world-space geometry
    into a new identity object at the origin, so wheel FBXs pivot around the
    tire centre even when the source mesh origin was elsewhere.
    """
    depsgraph = bpy.context.evaluated_depsgraph_get()
    evaluated = src.evaluated_get(depsgraph)
    mesh = evaluated.to_mesh()
    try:
        verts_world = [evaluated.matrix_world @ vertex.co for vertex in mesh.vertices]
        if verts_world:
            center = sum(verts_world, Vector()) / len(verts_world)
        else:
            mn, mx = wbbox(src)
            center = (mn + mx) * 0.5
        new_mesh = bpy.data.meshes.new(name)
        new_mesh.from_pydata(
            [tuple(vertex - center) for vertex in verts_world],
            [],
            [list(poly.vertices) for poly in mesh.polygons],
        )
        new_mesh.update()
        for material in src.data.materials:
            new_mesh.materials.append(material)
        for dst_poly, src_poly in zip(new_mesh.polygons, mesh.polygons):
            dst_poly.material_index = src_poly.material_index
        if mesh.uv_layers.active:
            src_uvs = mesh.uv_layers.active.data
            uv_layer = new_mesh.uv_layers.new(name=mesh.uv_layers.active.name or "UVMap")
            for index, dst_uv in enumerate(uv_layer.data):
                if index < len(src_uvs):
                    dst_uv.uv = src_uvs[index].uv
    finally:
        evaluated.to_mesh_clear()
    obj = bpy.data.objects.new(name, new_mesh)
    bpy.context.scene.collection.objects.link(obj)
    obj.matrix_world = Matrix.Identity(4)
    return obj


def _centered_visual_copy_many(sources, name):
    sources = [src for src in sources if src and src.type == 'MESH']
    if len(sources) == 1:
        return _centered_visual_copy(sources[0], name)
    depsgraph = bpy.context.evaluated_depsgraph_get()
    datasets = []
    all_world = []
    for src in sources:
        evaluated = src.evaluated_get(depsgraph)
        mesh = evaluated.to_mesh()
        try:
            verts_world = [evaluated.matrix_world @ vertex.co for vertex in mesh.vertices]
            faces = [list(poly.vertices) for poly in mesh.polygons]
            material_indices = [poly.material_index for poly in mesh.polygons]
            materials = [material for material in src.data.materials]
            if mesh.uv_layers.active:
                src_uvs = mesh.uv_layers.active.data
                face_uvs = [
                    [src_uvs[loop_index].uv.copy() for loop_index in poly.loop_indices]
                    for poly in mesh.polygons
                ]
                uv_name = mesh.uv_layers.active.name or "UVMap"
            else:
                face_uvs = None
                uv_name = "UVMap"
            datasets.append((src, verts_world, faces, material_indices, materials, face_uvs, uv_name))
            all_world.extend(verts_world)
        finally:
            evaluated.to_mesh_clear()
    if not all_world:
        return None
    center = sum(all_world, Vector()) / len(all_world)
    verts = []
    faces = []
    face_materials = []
    face_uvs_out = []
    uv_name_out = "UVMap"
    materials = []
    material_lookup = {}
    for _src, verts_world, src_faces, material_indices, src_materials, src_face_uvs, src_uv_name in datasets:
        vert_offset = len(verts)
        verts.extend(tuple(vertex - center) for vertex in verts_world)
        mat_offset_by_index = {}
        for index, material in enumerate(src_materials):
            if material is None:
                continue
            if material.name not in material_lookup:
                material_lookup[material.name] = len(materials)
                materials.append(material)
            mat_offset_by_index[index] = material_lookup[material.name]
        for face, material_index in zip(src_faces, material_indices):
            faces.append([vertex + vert_offset for vertex in face])
            face_materials.append(mat_offset_by_index.get(material_index, 0))
        if src_face_uvs is not None:
            face_uvs_out.extend(src_face_uvs)
            uv_name_out = src_uv_name
        else:
            face_uvs_out.extend(None for _face in src_faces)
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(verts, [], faces)
    mesh.update()
    for material in materials:
        mesh.materials.append(material)
    for polygon, material_index in zip(mesh.polygons, face_materials):
        polygon.material_index = material_index
    if any(face_uvs is not None for face_uvs in face_uvs_out):
        uv_layer = mesh.uv_layers.new(name=uv_name_out)
        loop_index = 0
        for polygon, face_uvs in zip(mesh.polygons, face_uvs_out):
            if face_uvs is None:
                loop_index += len(polygon.loop_indices)
                continue
            for uv in face_uvs:
                if loop_index < len(uv_layer.data):
                    uv_layer.data[loop_index].uv = uv
                loop_index += 1
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.scene.collection.objects.link(obj)
    obj.matrix_world = Matrix.Identity(4)
    return obj


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
_DOOR_RE = _rpf_re.compile(r'(?:^|[_.\s])(?:door|doors)(?:$|[_.\s\d])', _rpf_re.I)
_HOOD_RE = _rpf_re.compile(r'(?:^|[_.\s])(?:hood|bonnet)(?:$|[_.\s\d])', _rpf_re.I)
_TRUNK_RE = _rpf_re.compile(r'(?:^|[_.\s])(?:trunk|boot|hatch|tailgate|decklid)(?:$|[_.\s\d])', _rpf_re.I)
_REAR_AREA_RE = _rpf_re.compile(r'(?:^|[_.\s])(?:tray|bed|cargo|load|rearbody|tub)(?:$|[_.\s\d])', _rpf_re.I)
_INTERIOR_RE = _rpf_re.compile(r'(?:^|[_.\s])(?:interior|inside|seat|seats|dash|dashboard|console|pedal|steering|wheelhouse|carpet|fabric)(?:$|[_.\s\d])', _rpf_re.I)
_MECH_RE = _rpf_re.compile(r'(?:^|[_.\s])(?:engine|motor|battery|fuel|tank|gearbox|transmission|diff|differential|exhaust|suspension|axle|driveshaft|chassis|undercarriage|underbody)(?:$|[_.\s\d])', _rpf_re.I)
_BRAKE_RE = _rpf_re.compile(r'(?:^|[_.\s])(?:brake|caliper|disc|rotor)(?:$|[_.\s\d])', _rpf_re.I)


def _is_wheel_part(name):
    low = name.lower()
    if any(g in low for g in _WHEEL_BODY_GUARD):
        return False  # wheel arch / fender / mudguard are BODY, not the tire
    return is_road_wheel_name(name)


def _is_glass_part(name):
    return bool(_GLASS_RE.search("_" + name + "_"))


def _is_light_part(name):
    return bool(_LIGHT_RE.search("_" + name + "_"))


def _object_semantic_text(obj):
    bits = [obj.name]
    bits.extend(collection.name for collection in obj.users_collection)
    bits.extend(slot.material.name for slot in obj.material_slots if slot.material)
    return " ".join(bits).lower()


def _scene_render_meshes():
    return [
        obj for obj in bpy.context.scene.objects
        if obj.type == 'MESH' and not obj.name.startswith(COLLIDER_PFX)
    ]


def _combined_bbox(meshes):
    mn = Vector((1e9, 1e9, 1e9))
    mx = Vector((-1e9, -1e9, -1e9))
    for obj in meshes:
        a, b = wbbox(obj)
        mn.x = min(mn.x, a.x); mn.y = min(mn.y, a.y); mn.z = min(mn.z, a.z)
        mx.x = max(mx.x, b.x); mx.y = max(mx.y, b.y); mx.z = max(mx.z, b.z)
    return mn, mx


def _lr_tag(center, mn, mx):
    mid = (mn.x + mx.x) * 0.5
    return "L" if center.x <= mid else "R"


def _fr_tag(center, mn, mx):
    mid = (mn.y + mx.y) * 0.5
    return "F" if center.y >= mid else "R"


def _wheel_or_brake_group(prefix, center, mn, mx):
    return f"{prefix}_{_fr_tag(center, mn, mx)}{_lr_tag(center, mn, mx)}"


def _door_group(center, mn, mx, text):
    if "trunk" in text or "boot" in text or "hatch" in text or "tailgate" in text:
        return "door_trunk"
    front_hint = any(token in text for token in ("front", "_fl", "_fr", ".fl", ".fr", "l01", "r01"))
    rear_hint = any(token in text for token in ("rear", "_rl", "_rr", ".rl", ".rr", "l02", "r02"))
    side = _lr_tag(center, mn, mx)
    if front_hint and not rear_hint:
        row = "F"
    elif rear_hint and not front_hint:
        row = "R"
    else:
        row = _fr_tag(center, mn, mx)
    return f"door_{row}{side}"


def _material_family(text):
    if any(token in text for token in ("glass", "window", "windscreen", "windshield")):
        return "glass"
    if any(token in text for token in ("rubber", "tire", "tyre")):
        return "rubber"
    if any(token in text for token in ("fabric", "cloth", "carpet", "seat")):
        return "fabric"
    if any(token in text for token in ("plastic", "lamp", "lens", "trim")):
        return "plastic"
    if any(token in text for token in ("metal", "steel", "iron", "chrome", "aluminium", "aluminum")):
        return "metal"
    return "unknown"


def _semantic_from_existing_part(part, center, mn, mx):
    if not part:
        return None
    if part.startswith("wheel_"):
        return {"category": "wheel", "group": part, "role": "wheel-slot"}
    if part.startswith("brake_"):
        return {"category": "brake", "group": part, "role": "firegeo"}
    if part.startswith("window_") or part == "windows_body":
        return {"category": "glass", "group": part, "role": "dst-glass"}
    if part.startswith("lights_"):
        return {"category": "light_cover", "group": part, "role": "firegeo"}
    if part in DOORS:
        return {"category": "door", "group": part, "role": "vehicle"}
    if part in {"Steering_Wheel", "Pedal_Brake", "Pedal_Accelerator", "interior"}:
        return {"category": "interior", "group": "interior", "role": "firegeo"}
    if part == "exterior":
        y_span = max(mx.y - mn.y, 1e-6)
        z_span = max(mx.z - mn.z, 1e-6)
        y_norm = (center.y - mn.y) / y_span
        z_norm = (center.z - mn.z) / z_span
        if z_norm > 0.42 and 0.25 < y_norm < 0.82:
            return {"category": "cab", "group": "cab", "role": "vehicle"}
        if y_norm < 0.30:
            return {"category": "rear_area", "group": "rear_area", "role": "vehicle"}
        return {"category": "exterior", "group": "exterior", "role": "vehicle"}
    return None


def _classify_vehicle_object(obj, mn, mx):
    text = _object_semantic_text(obj)
    a, b = wbbox(obj)
    center = (a + b) * 0.5
    existing = _semantic_from_existing_part(part_of(obj), center, mn, mx)
    if existing:
        result = existing
    elif _is_wheel_part(text):
        result = {"category": "wheel", "group": _wheel_or_brake_group("wheel", center, mn, mx), "role": "wheel-slot"}
    elif _BRAKE_RE.search("_" + text + "_"):
        result = {"category": "brake", "group": _wheel_or_brake_group("brake", center, mn, mx), "role": "firegeo"}
    elif _is_glass_part(text) or _material_family(text) == "glass":
        result = {"category": "glass", "group": "glass", "role": "dst-glass"}
    elif _is_light_part(text):
        group = "lights_front" if center.y >= (mn.y + mx.y) * 0.5 else "lights_rear"
        result = {"category": "light_cover", "group": group, "role": "firegeo"}
    elif _DOOR_RE.search("_" + text + "_"):
        result = {"category": "door", "group": _door_group(center, mn, mx, text), "role": "vehicle"}
    elif _HOOD_RE.search("_" + text + "_"):
        result = {"category": "hood", "group": "hood", "role": "vehicle"}
    elif _TRUNK_RE.search("_" + text + "_"):
        result = {"category": "trunk", "group": "door_trunk", "role": "vehicle"}
    elif _REAR_AREA_RE.search("_" + text + "_"):
        result = {"category": "rear_area", "group": "rear_area", "role": "vehicle"}
    elif _MECH_RE.search("_" + text + "_"):
        group = "undercarriage" if center.z < mn.z + (mx.z - mn.z) * 0.45 else "mechanical"
        result = {"category": "mechanical", "group": group, "role": "firegeo"}
    elif _INTERIOR_RE.search("_" + text + "_"):
        result = {"category": "interior", "group": "interior", "role": "firegeo"}
    else:
        y_span = max(mx.y - mn.y, 1e-6)
        z_span = max(mx.z - mn.z, 1e-6)
        y_norm = (center.y - mn.y) / y_span
        z_norm = (center.z - mn.z) / z_span
        if z_norm > 0.43 and 0.24 < y_norm < 0.82:
            result = {"category": "cab", "group": "cab", "role": "vehicle"}
        elif y_norm < 0.30:
            result = {"category": "rear_area", "group": "rear_area", "role": "vehicle"}
        elif z_norm < 0.22:
            result = {"category": "undercarriage", "group": "undercarriage", "role": "vehicle"}
        else:
            result = {"category": "exterior", "group": "exterior", "role": "vehicle"}
    result["material"] = _material_family(text)
    result["center"] = center
    result["bbox"] = (a, b)
    return result


def _semantic_collision_groups():
    preferred = [
        "exterior", "cab", "rear_area", "hood", "undercarriage",
        "door_FL", "door_FR", "door_RL", "door_RR", "door_trunk",
    ]
    groups = {
        obj.get("rpf_collision_group") for obj in _scene_render_meshes()
        if obj.get("rpf_collision_role") == "vehicle" and obj.get("rpf_collision_group")
    }
    ordered = [group for group in preferred if group in groups]
    ordered.extend(sorted(group for group in groups if group not in preferred))
    return ordered


def _semantic_group_objects(group):
    return [
        obj for obj in _scene_render_meshes()
        if obj.get("rpf_collision_group") == group
    ]


class RPF_OT_analyze_vehicle_parts(bpy.types.Operator):
    bl_idname = "rpf.analyze_vehicle_parts"
    bl_label = "Analyze Vehicle Parts"
    bl_description = ("Classify render meshes into exterior, cab, rear area, doors, "
                      "glass, light covers, wheels, brakes and mechanical groups. "
                      "Tags are used by grouped CoACD/V-HACD collision without moving meshes")
    bl_options = {'REGISTER', 'UNDO'}

    select_vehicle_groups: bpy.props.BoolProperty(
        name="Select Vehicle Groups",
        default=False,
        description="Select meshes that will feed main Vehicle UCX collision after analysis",
    )

    def execute(self, context):
        meshes = _scene_render_meshes()
        if not meshes:
            self.report({'ERROR'}, "no render meshes to analyze")
            return {'CANCELLED'}
        mn, mx = _combined_bbox(meshes)
        counts = Counter()
        roles = Counter()
        for obj in meshes:
            info = _classify_vehicle_object(obj, mn, mx)
            obj["rpf_category"] = info["category"]
            obj["rpf_collision_group"] = info["group"]
            obj["rpf_collision_role"] = info["role"]
            obj["rpf_material_hint"] = info["material"]
            counts[info["group"]] += 1
            roles[info["role"]] += 1
        groups = _semantic_collision_groups()
        if groups:
            context.scene.rpf_build_categories = ",".join(groups)
        summary = ", ".join(f"{name}:{counts[name]}" for name in sorted(counts))
        context.scene["rpf_semantic_summary"] = summary
        context.scene["rpf_semantic_roles"] = ", ".join(f"{name}:{roles[name]}" for name in sorted(roles))
        print("RPF SEMANTIC ANALYSIS:", summary)
        print("RPF SEMANTIC VEHICLE GROUPS:", groups)
        if self.select_vehicle_groups:
            bpy.ops.object.select_all(action='DESELECT')
            selected = []
            for obj in meshes:
                if obj.get("rpf_collision_role") == "vehicle":
                    obj.select_set(True)
                    selected.append(obj)
            if selected:
                context.view_layer.objects.active = selected[0]
                frame_view(context)
        self.report({'INFO'}, f"analyzed {len(meshes)} meshes; Vehicle groups: {', '.join(groups) or 'none'}")
        return {'FINISHED'}


class RPF_OT_select_semantic_group(bpy.types.Operator):
    bl_idname = "rpf.select_semantic_group"
    bl_label = "Select Analyzed Group"
    bl_description = "Select meshes tagged by Analyze Vehicle Parts for review"
    bl_options = {'REGISTER'}

    group: bpy.props.StringProperty()

    def execute(self, context):
        group = self.group.strip()
        if not group:
            return {'CANCELLED'}
        objects = _semantic_group_objects(group)
        if not objects:
            self.report({'WARNING'}, f"no analyzed meshes in {group}; run Analyze Vehicle Parts")
            return {'CANCELLED'}
        bpy.ops.object.select_all(action='DESELECT')
        for obj in objects:
            obj.hide_set(False)
            obj.select_set(True)
        context.view_layer.objects.active = objects[0]
        frame_view(context)
        self.report({'INFO'}, f"selected {len(objects)} mesh(es): {group}")
        return {'FINISHED'}


# ----------------------------------------------------------------------------
# WHEEL SEPARATION + V-HACD MULTI-HULL CONVEX DECOMPOSITION
# ----------------------------------------------------------------------------

def _wheel_bones_world():
    """World positions of the four wheel bones keyed by their wheel_XX name."""
    arm = _get_armature()
    if not arm:
        return {}
    bmap = {'v_wheel_l01': 'wheel_FL', 'v_wheel_r01': 'wheel_FR',
            'v_wheel_l02': 'wheel_RL', 'v_wheel_r02': 'wheel_RR'}
    out = {}
    for bone_name, wheel_name in bmap.items():
        bone = arm.data.bones.get(bone_name)
        if bone:
            out[wheel_name] = arm.matrix_world @ bone.head_local
    return out


def _separate_wheels_by_bones(context, radius=0.55, corner_radius=0.78):
    """Extract wheels that are baked into body meshes, by proximity to v_wheel_* bones.
    Island-based, so the body shell (centroid far from any wheel bone) is never grabbed."""
    import bmesh as _bm
    bones = _wheel_bones_world()
    if not bones:
        return []
    bodies = [o for o in context.scene.objects
              if o.type == 'MESH' and not o.name.startswith(COLLIDER_PFX)
              and not _is_wheel_part(o.name) and not _is_glass_part(o.name)
              and not _is_light_part(o.name)]
    if context.mode != 'OBJECT':
        bpy.ops.object.mode_set(mode='OBJECT')
    tmp_objs = []
    for body in bodies:
        mw = body.matrix_world
        bm = _bm.new(); bm.from_mesh(body.data); bm.verts.ensure_lookup_table()
        seen = set(); wheelidx = set()
        for v in bm.verts:
            if v.index in seen:
                continue
            stack = [v]; comp = []
            while stack:
                cur = stack.pop()
                if cur.index in seen:
                    continue
                seen.add(cur.index); comp.append(cur)
                for e in cur.link_edges:
                    ov = e.other_vert(cur)
                    if ov.index not in seen:
                        stack.append(ov)
            centre = sum((mw @ x.co for x in comp), Vector()) / len(comp)
            if any((centre - bp).length < radius for bp in bones.values()):
                wheelidx.update(x.index for x in comp)
        bm.free()
        if not wheelidx:
            continue
        bpy.ops.object.select_all(action='DESELECT')
        body.select_set(True); context.view_layer.objects.active = body
        bpy.ops.object.mode_set(mode='EDIT'); bpy.ops.mesh.select_all(action='DESELECT')
        bpy.ops.object.mode_set(mode='OBJECT')
        for i in wheelidx:
            body.data.vertices[i].select = True
        bpy.ops.object.mode_set(mode='EDIT'); before = set(bpy.data.objects.keys())
        bpy.ops.mesh.separate(type='SELECTED'); bpy.ops.object.mode_set(mode='OBJECT')
        tmp_objs += [bpy.data.objects[n] for n in set(bpy.data.objects.keys()) - before]
    if not tmp_objs:
        return []
    bpy.ops.object.select_all(action='DESELECT')
    for t in tmp_objs:
        t.select_set(True)
    context.view_layer.objects.active = tmp_objs[0]
    if len(tmp_objs) > 1:
        bpy.ops.object.join()
    pool = context.view_layer.objects.active
    made = []
    for wheel_name, bp in bones.items():
        if not pool or pool.name not in bpy.data.objects:
            break
        bpy.ops.object.select_all(action='DESELECT')
        pool.select_set(True); context.view_layer.objects.active = pool
        bpy.ops.object.mode_set(mode='EDIT'); bpy.ops.mesh.select_all(action='DESELECT')
        bpy.ops.object.mode_set(mode='OBJECT')
        hit = 0
        for v in pool.data.vertices:
            if (pool.matrix_world @ v.co - bp).length < corner_radius:
                v.select = True; hit += 1
        if hit == 0:
            continue
        bpy.ops.object.mode_set(mode='EDIT'); before = set(bpy.data.objects.keys())
        bpy.ops.mesh.separate(type='SELECTED'); bpy.ops.object.mode_set(mode='OBJECT')
        new = [bpy.data.objects[k] for k in set(bpy.data.objects.keys()) - before]
        if not new:
            continue
        wheel = new[0]; wheel.name = wheel_name
        move_to_coll(wheel, wheel_name)
        made.append(wheel_name)
    if pool and pool.name in bpy.data.objects and len(pool.data.vertices) < 24:
        bpy.data.objects.remove(pool, do_unlink=True)
    return made


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
            # No wheel-named meshes: wheels are likely baked into the body. Extract
            # them by proximity to the v_wheel_* bones (island-based, body-safe).
            made = _separate_wheels_by_bones(context)
            if made:
                self.report({'INFO'}, "wheels by bone proximity -> " + ", ".join(sorted(made)))
                return {'FINISHED'}
            self.report({'ERROR'}, "no wheel-named meshes, and no v_wheel_* bones with "
                                   "nearby geometry to extract")
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
    nv, nf = [], []
    try:
        mod = obj.modifiers.new("RPF_VHACD_INPUT_DECIMATE", 'DECIMATE')
        mod.ratio = max(0.01, min(1.0, target_tris / float(len(faces))))
        mod.use_collapse_triangulate = True
        bpy.context.view_layer.update()
        deps = bpy.context.evaluated_depsgraph_get()
        ev = obj.evaluated_get(deps)
        em = ev.to_mesh()
        try:
            nv = [tuple(v.co) for v in em.vertices]
            em.calc_loop_triangles()
            nf = [(t.vertices[0], t.vertices[1], t.vertices[2]) for t in em.loop_triangles]
        finally:
            ev.to_mesh_clear()
    finally:
        bpy.data.objects.remove(obj, do_unlink=True)
        if me.users == 0:
            bpy.data.meshes.remove(me)
    if len(nv) < 4 or not nf:
        return verts, faces
    if len(nf) > max(target_tris * 2, target_tris + 500):
        print(
            f"RPF V-HACD: decimate missed target ({len(faces)} -> {len(nf)} tris, target {target_tris}); using fallback-safe input",
            flush=True,
        )
        return verts, faces
    print(f"RPF V-HACD: reduced input {len(faces)} -> {len(nf)} tris", flush=True)
    return nv, nf


def _too_dense_for_decomposition(face_count, target_tris):
    return target_tris > 0 and face_count > max(target_tris * 2, target_tris + 500)


def _hull_stats(points):
    pts = [p if isinstance(p, Vector) else Vector(p) for p in points]
    if not pts:
        return Vector(), 0.0
    mn = Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
    mx = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
    center = (mn + mx) * 0.5
    span = mx - mn
    volume = max(span.x, 0.001) * max(span.y, 0.001) * max(span.z, 0.001)
    return center, volume


def _select_representative_hulls(hulls, max_hulls, label):
    """Limit backend hull output without dropping whole vehicle regions.

    CoACD can return 100+ hulls for an open car shell. Taking the first N is
    arbitrary and caused missing exterior sections. This keeps the largest hull,
    then uses farthest-point sampling weighted by size so the final set covers
    the car length/width/height instead of only the first backend partition.
    """
    valid = [hull for hull in hulls if len(hull) >= 4]
    if len(valid) <= max_hulls:
        return valid
    stats = [(hull, *_hull_stats(hull)) for hull in valid]
    stats.sort(key=lambda item: item[2], reverse=True)
    chosen = [stats.pop(0)]
    while stats and len(chosen) < max_hulls:
        best_index = 0
        best_score = -1.0
        for index, item in enumerate(stats):
            _hull, center, volume = item
            nearest = min((center - chosen_item[1]).length for chosen_item in chosen)
            score = nearest * (volume ** 0.25)
            if score > best_score:
                best_score = score
                best_index = index
        chosen.append(stats.pop(best_index))
    selected = [item[0] for item in chosen]
    print(
        f"RPF V-HACD: {label} returned {len(valid)} hulls; selected {len(selected)} representative hulls",
        flush=True,
    )
    return selected


def _vhacd_coacd(verts, faces, threshold, props=None):
    """Convex decomposition via the CoACD python module. Returns hull point-lists."""
    try:
        import numpy as np
        import coacd
    except Exception:
        return None
    try:
        mesh = coacd.Mesh(np.asarray(verts, dtype="float64"),
                          np.asarray(faces, dtype="int32"))
        props = props or {}
        kwargs = {
            "threshold": threshold,
            "max_convex_hull": int(props.get("max_hulls", 24)),
            "max_ch_vertex": int(props.get("max_vertices", 64)),
        }
        try:
            parts = coacd.run_coacd(mesh, **kwargs)
        except TypeError:
            kwargs.pop("max_ch_vertex", None)
            try:
                parts = coacd.run_coacd(mesh, **kwargs)
            except TypeError:
                kwargs.pop("max_convex_hull", None)
                try:
                    parts = coacd.run_coacd(mesh, **kwargs)
                except TypeError:
                    parts = coacd.run_coacd(mesh)
    except Exception:
        return None
    hulls = []
    for part in parts:
        v = part[0]
        hulls.append([(float(p[0]), float(p[1]), float(p[2])) for p in v])
    return hulls or None


def _vhacd_vhacdx(verts, faces, props):
    """Convex decomposition through Enfusion Tools' optional vhacdx backend."""
    try:
        import numpy as np
        import vhacdx
    except Exception:
        return None
    try:
        arr_verts = np.asarray(verts, dtype="float64")
        arr_faces = np.asarray(faces, dtype="uint32").reshape((-1, 3))
        scale = float(props.get("pre_scale", 1.0))
        if 1.0 - scale > 0.01 and len(arr_verts):
            centroid = arr_verts.mean(axis=0)
            arr_verts = (arr_verts - centroid) * scale + centroid
        convex_hulls = vhacdx.compute_vhacd(
            arr_verts,
            arr_faces.ravel(),
            maxConvexHulls=int(props.get("max_hulls", 16)),
            resolution=int(props.get("resolution", 100000)),
            minimumVolumePercentErrorAllowed=float(props.get("volume_error", 1.0)),
            maxRecursionDepth=int(props.get("recursion_depth", 10)),
            shrinkWrap=bool(props.get("shrink_wrap", True)),
            fillMode=str(props.get("fill_mode", "flood")),
            maxNumVerticesPerCH=int(props.get("max_vertices", 64)),
            asyncACD=True,
            minEdgeLength=int(props.get("min_edge_length", 2)),
            findBestPlane=bool(props.get("split_hulls", False)),
        )
    except Exception as exc:
        print(f"RPF VHACDX failed: {exc}", flush=True)
        return None
    hulls = []
    for hull_verts, _hull_faces in convex_hulls:
        hulls.append([(float(p[0]), float(p[1]), float(p[2])) for p in hull_verts])
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


def _find_vhacd_executable():
    """Find a user-installed V-HACD/TestVHACD executable without scanning the whole disk."""
    import os
    import shutil
    candidates = []
    names = (
        "TestVHACD.exe", "VHACD.exe", "V-HACD.exe", "testvhacd.exe",
        "vhacd.exe", "testVHACD", "vhacd", "TestVHACD",
    )
    for name in names:
        found = shutil.which(name)
        if found:
            candidates.append(found)
    env_keys = ("VHACD_EXE", "VHACD_PATH", "TESTVHACD_EXE", "COACD_VHACD_EXE")
    for key in env_keys:
        value = os.environ.get(key)
        if value:
            candidates.append(value)
    addon_dir = os.path.dirname(os.path.abspath(__file__))
    for name in names:
        candidates.append(os.path.join(addon_dir, "tools", "vhacd", name))
    roots = [
        os.path.dirname(bpy.data.filepath) if bpy.data.filepath else "",
        os.path.expanduser("~/Desktop"),
        os.path.expanduser("~/Downloads"),
        os.path.expanduser("~/Documents"),
        os.path.join(os.path.expanduser("~"), "Tools"),
        os.path.join(os.path.expanduser("~"), "bin"),
    ]
    for root in roots:
        if not root or not os.path.isdir(root):
            continue
        for name in names:
            candidates.append(os.path.join(root, name))
        for folder in ("VHACD", "V-HACD", "TestVHACD", "CoACD", "coacd"):
            for name in names:
                candidates.append(os.path.join(root, folder, name))
    for candidate in candidates:
        candidate = bpy.path.abspath(candidate)
        if os.path.isfile(candidate) and os.access(candidate, os.X_OK):
            return candidate
    return ""


def _decompose_hulls(verts, faces, threshold, exe, backend, vhacd_props=None):
    """Return (backend_used, hull_point_lists)."""
    backend = backend or 'AUTO'
    if backend in {'AUTO', 'COACD'}:
        hulls = _vhacd_coacd(verts, faces, threshold, vhacd_props)
        if hulls is not None:
            return "coacd", hulls
        if backend == 'COACD':
            return "none", None
    if backend in {'AUTO', 'VHACDX'}:
        hulls = _vhacd_vhacdx(verts, faces, vhacd_props or {})
        if hulls is not None:
            return "vhacdx", hulls
        if backend == 'VHACDX':
            return "none", None
    if backend in {'AUTO', 'EXE'}:
        hulls = _vhacd_exe(verts, faces, exe)
        if hulls is not None:
            return "vhacd-exe", hulls
        if backend == 'EXE':
            return "none", None
    return "convex-fallback", None


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


def _collision_for_part(part, index, decimate_target, threshold, max_hulls, max_faces, exe, backend, vhacd_props=None):
    """Grouped collision: merge a whole part/category (its render pieces, minus
    glass/lights/wheels) into one mass, then convex-decompose THAT. Produces far fewer,
    cleaner UCX hulls than per-sub-object. Returns (made_objects, next_index)."""
    pieces = [o for o in part_objects(part) if o.type == 'MESH']
    if not pieces:
        pieces = _semantic_group_objects(part)
    if not pieces:
        pieces = [o for o in bpy.data.objects
                  if o.type == 'MESH' and not o.name.startswith(COLLIDER_PFX)
                  and (o.name == part or o.name.startswith(part + "."))]
    pieces = [o for o in pieces if not _is_glass_part(o.name)
              and not _is_light_part(o.name) and not _is_wheel_part(o.name)
              and o.get("rpf_collision_role", "vehicle") == "vehicle"]
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
    if _too_dense_for_decomposition(len(faces), decimate_target):
        backend_used, hulls = "convex-fallback:dense-open-input", None
        print(
            f"RPF COLLISION: {part} input still {len(faces)} tris after decimate target {decimate_target}; using capped convex fallback",
            flush=True,
        )
    else:
        backend_used, hulls = _decompose_hulls(verts, faces, threshold, exe, backend, vhacd_props)
    print(f"RPF COLLISION: {part} backend={backend_used}", flush=True)
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
    selected_hulls = _select_representative_hulls(hulls, max_hulls, part)
    for hi, pts in enumerate(selected_hulls):
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
    backend: bpy.props.EnumProperty(
        name="Backend",
        default='AUTO',
        items=[('AUTO', "Auto", "CoACD, then external V-HACD, then convex fallback"),
               ('COACD', "CoACD", "Use Blender Python CoACD only"),
               ('VHACDX', "VHACD Python", "Use Enfusion Tools-style vhacdx Python backend only"),
               ('EXE', "External", "Use external V-HACD executable only"),
               ('FALLBACK', "Fallback", "Do not decompose; single capped convex hull")])
    threshold: bpy.props.FloatProperty(name="Concavity", default=0.05, min=0.01, max=1.0,
                                       description="CoACD concavity threshold (lower = more hulls)")
    decimate_target: bpy.props.IntProperty(
        name="Decimate input to", default=4000, min=0, max=80000,
        description="Reduce each part to ~this many tris before decomposition so Blender "
                    "doesn't freeze on dense meshes (0 = use full resolution)")
    replace_generated: bpy.props.BoolProperty(name="Replace previous hulls", default=False)
    thread_count: bpy.props.IntProperty(
        name="Worker threads",
        default=1,
        min=1,
        max=8,
        description="Run decomposition for multiple selected meshes in parallel. Blender object creation still runs on the main thread",
    )

    def execute(self, context):
        import concurrent.futures
        temp_sources = []
        edit_source = None
        if context.mode == 'EDIT_MESH':
            temp_sources, edit_source = _selected_face_temp_objects(
                context,
                context.scene.rpf_selected_faces_split_loose,
            )
            if not temp_sources:
                self.report({'ERROR'}, "Select faces first, or switch to Object Mode for whole-part V-HACD")
                return {'CANCELLED'}
            bpy.ops.object.mode_set(mode='OBJECT')
            sources = temp_sources
        else:
            if context.mode != 'OBJECT':
                bpy.ops.object.mode_set(mode='OBJECT')
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
        jobs = []
        for i, src in enumerate(sources):
            source_name = edit_source.name if edit_source else src.name
            job_name = f"{source_name}_sel{i + 1:02d}" if edit_source else source_name
            print(f"RPF V-HACD prep {i + 1}/{len(sources)}: {job_name} ...", flush=True)
            verts, faces = _world_tris(src)
            if len(verts) < 4 or not faces:
                continue
            verts, faces = _reduce_mesh(verts, faces, self.decimate_target)
            jobs.append((job_name, verts, faces, source_name))

        for temp in temp_sources:
            if temp.name in bpy.data.objects:
                bpy.data.objects.remove(temp, do_unlink=True)

        props = _vhacd_props_from_scene(context.scene)
        workers = min(
            max(1, self.thread_count),
            max(1, len(jobs)),
            max(1, int(context.scene.rpf_ucx_threads)),
        )

        def run_job(job):
            src_name, verts, faces, source_name = job
            if _too_dense_for_decomposition(len(faces), self.decimate_target):
                used, hulls = "convex-fallback:dense-open-input", None
                print(
                    f"RPF V-HACD: {src_name} still has {len(faces)} tris after target {self.decimate_target}; using capped convex fallback",
                    flush=True,
                )
            else:
                used, hulls = _decompose_hulls(
                    verts,
                    faces,
                    self.threshold,
                    exe,
                    self.backend,
                    props,
                )
            return src_name, verts, used, hulls, source_name

        if workers > 1 and len(jobs) > 1 and self.backend != 'EXE':
            print(f"RPF V-HACD: running {len(jobs)} decomposition jobs on {workers} worker threads", flush=True)
            results = []
            with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
                future_by_name = {pool.submit(run_job, job): job[0] for job in jobs}
                for future in concurrent.futures.as_completed(future_by_name):
                    try:
                        results.append(future.result())
                    except Exception as exc:
                        print(f"RPF V-HACD worker failed for {future_by_name[future]}: {exc}", flush=True)
            order = {name: i for i, (name, _verts, _faces, _source_name) in enumerate(jobs)}
            results.sort(key=lambda result: order.get(result[0], 9999))
        else:
            results = [run_job(job) for job in jobs]

        for src_name, verts, backend, hulls, source_name in results:
            token = _safe_name_token(src_name)
            if not hulls:
                # graceful fallback: single guaranteed-convex hull
                hull = _capped_hull_obj(f"UCX_MainCol_{index:02d}_{token}", verts, self.max_faces)
                if hull:
                    hull["rpf_ucx_source"] = source_name
                    if edit_source:
                        hull["rpf_ucx_selection_source"] = source_name
                    hull["rpf_ucx_face_cap"] = self.max_faces
                    _place_ebt_collider(hull, "Vehicle")
                    made.append(hull)
                    index += 1
                if backend == "none":
                    backend = "convex-fallback"
                continue
            selected_hulls = _select_representative_hulls(hulls, self.max_hulls, src_name)
            for hi, pts in enumerate(selected_hulls):
                if len(pts) < 4:
                    continue
                name = f"UCX_MainCol_{index:02d}_{token}_{hi:02d}"
                obj = _capped_hull_obj(name, pts, self.max_faces)
                if obj is None:
                    continue
                obj["rpf_ucx_source"] = source_name
                if edit_source:
                    obj["rpf_ucx_selection_source"] = source_name
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
        vhacdx_result = subprocess.run(
            [py, "-m", "pip", "install", "--upgrade", "vhacdx==0.0.6"],
            capture_output=True,
            text=True,
        )
        try:
            import importlib
            importlib.invalidate_caches()
            import coacd  # noqa: F401
        except Exception as exc:
            self.report({'WARNING'}, f"installed; restart Blender to load CoACD ({exc})")
            return {'FINISHED'}
        found = _find_vhacd_executable()
        vhacdx_note = "; vhacdx installed" if vhacdx_result.returncode == 0 else "; vhacdx unavailable"
        if found:
            context.scene.rpf_vhacd_exe = found
            self.report({'INFO'}, "CoACD installed; V-HACD exe found" + vhacdx_note)
        else:
            self.report({'INFO'}, "CoACD installed; external V-HACD exe not found" + vhacdx_note)
        return {'FINISHED'}


class RPF_OT_find_vhacd_exe(bpy.types.Operator):
    bl_idname = "rpf.find_vhacd_exe"
    bl_label = "Auto-find V-HACD exe"
    bl_description = ("Search PATH and common user folders for TestVHACD/VHACD. "
                      "CoACD does not require this external executable")
    bl_options = {'REGISTER'}

    def execute(self, context):
        found = _find_vhacd_executable()
        if not found:
            self.report({'WARNING'}, "no external V-HACD exe found; use Backend Auto/CoACD")
            return {'CANCELLED'}
        context.scene.rpf_vhacd_exe = found
        self.report({'INFO'}, f"V-HACD exe: {found}")
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

    use_vhacd: bpy.props.BoolProperty(name="Use V-HACD", default=False)
    do_lod: bpy.props.BoolProperty(name="Bake LOD", default=False)

    def execute(self, context):
        steps = []
        if context.scene.rpf_auto_analyze_collision:
            try:
                bpy.ops.rpf.analyze_vehicle_parts()
                steps.append("analyzed")
            except Exception as exc:
                steps.append(f"analyze-skip({exc})")
        bpy.ops.rpf.cleanup_colliders(mode='GENERATED')
        steps.append("cleaned")
        have = False
        backend = context.scene.rpf_ucx_backend
        if self.use_vhacd and backend != 'FALLBACK':
            have = True
        if have:
            # GROUPED collision: merge each category into one mass, decompose THAT.
            # Body shell + one hull-set per door = far fewer, cleaner hulls than
            # decomposing 80+ tiny sub-material parts.
            cats = [
                token.strip() for token in context.scene.rpf_build_categories.split(",")
                if token.strip()
            ] or ["exterior"]
            index = _next_main_col_index()
            exe = context.scene.rpf_vhacd_exe
            dec = context.scene.rpf_ucx_decimate
            thr = context.scene.rpf_ucx_concavity
            mh = context.scene.rpf_ucx_max_hulls
            mf = context.scene.rpf_ucx_max_faces
            props = _vhacd_props_from_scene(context.scene)
            total = []
            for cat in cats:
                made, index = _collision_for_part(cat, index, dec, thr, mh, mf, exe, backend, props)
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
            bpy.ops.rpf.apply_collision_materials()
            steps.append("gamemats")
        except Exception as exc:
            steps.append(f"gamemats-skip({exc})")
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

        # Export must never silently ship broken door/wheel animation bindings.
        # When enabled, run the same checkpointed rigid-skin repair the user can
        # trigger from the Rig tab, then re-check before writing FBX files.
        binding_issues = _rig_binding_issues(arm)
        if binding_issues and context.scene.rpf_auto_skin_before_export:
            try:
                bpy.ops.rpf.skin_parts()
            except Exception as exc:
                self.report({'ERROR'}, f"auto skin failed - run Skin All Parts manually: {exc}")
                return {'CANCELLED'}
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
            if name.startswith(("UCL_", "UCX_", "UBX_")):
                return context.scene.rpf_export_vehicle_collision
            if o.type == 'ARMATURE':
                return context.scene.rpf_export_armature
            if o.type == 'EMPTY':
                return context.scene.rpf_export_memory
            # Slot-owned VISUALS never belong in the master body XOB. Name-robust
            # detection keeps wheels / windows / light lenses out of the body even
            # when the vehicle uses non-stock part names (the export-tickbox bug).
            if _is_steering_mesh_name(name):
                return context.scene.rpf_export_render
            if o.type == 'MESH':
                role, _slot, target = _rig_role_for_obj(o)
                if role in {"ROTATOR", "SUSPENSION", "HANDBRAKE", "PEDAL_BRAKE", "PEDAL_THROTTLE"}:
                    return context.scene.rpf_export_render
                if target.startswith(("v_rotator_", "v_suspension_")):
                    return context.scene.rpf_export_render
            if _is_wheel_part(name):
                return False
            if _is_light_part(name):
                return False
            if _is_glass_part(name):
                return context.scene.rpf_export_visual_glass
            return context.scene.rpf_export_render

        # ---- 1) master: selected render/skeleton/memory/collision classes.
        body = [o for o in context.scene.objects if include_master(o)]
        restore_master_materials = _temporary_master_material_overrides(body)
        try:
            done.append(_fbx_export(os.path.join(EXPORT_ROOT, f"{ASSET_NAME}.fbx"), body))
        finally:
            restore_master_materials()

        # ---- 2) wheel: single wheel at origin + stock-named colliders.
        #      SampleCar uses UCL_VC_wheel00 plus one UTM_FG_Wheel_L01 carrying
        #      rubber+metal face materials. Keep that shape so Workbench imports
        #      one valid wheel FireGeo collider with both surface properties.
        def _wheel_source(name):
            obj = bpy.data.objects.get(name)
            return obj if obj and obj.type == 'MESH' else None

        def _first_wheel(names):
            for name in names:
                obj = _wheel_source(name)
                if obj:
                    return obj
            return next((o for o in context.scene.objects
                         if o.type == 'MESH' and _is_wheel_part(o.name)), None)

        def _wheel_export_jobs():
            mode = context.scene.rpf_export_wheel_slot_mode
            if mode == 'SELECTED':
                selected = [o for o in context.selected_objects
                            if o.type == 'MESH' and _is_wheel_part(o.name)]
                return [("Alt", selected)] if selected else []
            if mode == 'ALL':
                return [(tag, [obj]) for tag, obj in (
                    ("FL", _wheel_source("wheel_FL")),
                    ("FR", _wheel_source("wheel_FR")),
                    ("RL", _wheel_source("wheel_RL")),
                    ("RR", _wheel_source("wheel_RR")),
                ) if obj]
            if mode == 'FRONT_REAR':
                front = _first_wheel(("wheel_FL", "wheel_FR"))
                rear = _first_wheel(("wheel_RL", "wheel_RR"))
                jobs = []
                if front:
                    jobs.append(("Front", [front]))
                if rear and rear != front:
                    jobs.append(("Rear", [rear]))
                return jobs
            single = _first_wheel(("wheel_FL", "wheel_FR", "wheel_RL", "wheel_RR"))
            return [("Wheel", [single])] if single else []

        if context.scene.rpf_export_wheel_slot:
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

            def _wheel_firegeo(name, tire_radius, rim_radius, depth, segs):
                me = bpy.data.meshes.new(name)
                bm = _bm.new()

                def add_cylinder(radius, cylinder_depth, segments, mat_index):
                    result = _bm.ops.create_cone(
                        bm, cap_ends=True, segments=segments,
                        radius1=radius, radius2=radius, depth=cylinder_depth,
                    )
                    for v in result.get("verts", []):
                        v.co = Vector((v.co.z, v.co.y, -v.co.x))
                    faces = result.get("faces")
                    if faces is None:
                        faces = [g for g in result.get("geom", []) if isinstance(g, _bm.types.BMFace)]
                    for face in faces:
                        face.material_index = mat_index

                add_cylinder(tire_radius, depth, segs, 0)
                add_cylinder(rim_radius, depth * 1.12, max(12, segs // 2), 1)
                bm.to_mesh(me); bm.free()
                obj = bpy.data.objects.new(name, me)
                bpy.context.scene.collection.objects.link(obj)
                _apply_vehicle_collision_materials(obj)
                _ensure_mesh_uvs(obj)
                return obj

            radius = context.scene.rpf_wheel_radius
            jobs = _wheel_export_jobs()
            if not jobs:
                self.report({'WARNING'}, "no wheel source found - skipped wheel FBX")
                print("ENFUSION EXPORT: no wheel source found; skipped wheel FBX")
            for slot, sources in jobs:
                w = _centered_visual_copy_many(sources, "wheel")
                if not w:
                    continue
                ucl = _cyl("UCL_VC_wheel00", radius * 0.98, 0.28, 16)  # rubber VehicleComplex
                _apply_vehicle_collision_materials(ucl)
                _ensure_mesh_uvs(ucl)
                fg = _wheel_firegeo("UTM_FG_Wheel_L01", radius, radius * 0.48, 0.30, 24)
                _ensure_mesh_uvs(w)
                suffix = "" if slot == "Wheel" else f"_{slot}"
                paths = [os.path.join(EXPORT_ROOT, "VehParts", f"{ASSET_NAME}_Wheel{suffix}.fbx")]
                if slot == "Front":
                    # Backward-compatible default wheel slot for prefab templates.
                    paths.append(os.path.join(EXPORT_ROOT, "VehParts", f"{ASSET_NAME}_Wheel.fbx"))
                for path in paths:
                    done.append(_fbx_export(path, [w, ucl, fg]))
                for obj in (w, ucl, fg):
                    bpy.data.objects.remove(obj, do_unlink=True)

        # ---- 3) glass: door windows + split body glass (F/R/quarters)
        #      door/trunk panes get a 'snap_glass' empty at the door hinge:
        #      base-prefab slots use PivotID v_door_xx + ChildPivotID snap_glass
        glass_slots = (
            ("F", None, ("glass_windshield", "windshield", "windscreen", "window_F", "windows_front")),
            ("FL", "door_FL", ("window_FL", "door_FL_window", "glass_FL")),
            ("FR", "door_FR", ("window_FR", "door_FR_window", "glass_FR")),
            ("RL", "door_RL", ("window_RL", "door_RL_window", "glass_RL")),
            ("RR", "door_RR", ("window_RR", "door_RR_window", "glass_RR")),
            ("R", "door_trunk", ("window_trunk", "door_trunk_window", "glass_rear", "rear_window")),
        )

        def _is_export_render_mesh(obj):
            if not obj or obj.type != 'MESH':
                return False
            if obj.name.startswith(COLLIDER_PFX) or obj.get("usage"):
                return False
            if _is_wheel_part(obj.name) or _is_wheel_part(part_of(obj) or ""):
                return False
            return True

        def _objects_in_named_collections(names):
            wanted = {name.lower() for name in names}
            out, seen = [], set()
            for collection in bpy.data.collections:
                if collection.name.lower() not in wanted:
                    continue
                for obj in collection.objects:
                    if _is_export_render_mesh(obj) and obj.name not in seen:
                        out.append(obj)
                        seen.add(obj.name)
            return out

        def _find_glass_slot_sources(names):
            found, seen = [], set()
            for obj in _objects_in_named_collections(names):
                found.append(obj)
                seen.add(obj.name)
            for source_name in names:
                obj = bpy.data.objects.get(source_name)
                if _is_export_render_mesh(obj) and obj.name not in seen:
                    found.append(obj)
                    seen.add(obj.name)
            wanted = {name.lower() for name in names}
            for obj in context.scene.objects:
                if not _is_export_render_mesh(obj) or obj.name in seen:
                    continue
                base = obj.name.split(".", 1)[0].lower()
                part = (part_of(obj) or "").lower()
                if base in wanted or part in wanted:
                    found.append(obj)
                    seen.add(obj.name)
            return found

        def _fallback_glass_sources(tag):
            candidates = [
                obj for obj in context.scene.objects
                if _is_export_render_mesh(obj)
                and (_is_glass_part(obj.name) or _is_glass_part(part_of(obj) or ""))
            ]
            if not candidates:
                return []
            boxes = [(obj, *wbbox(obj)) for obj in candidates]
            y_min = min(mn.y for _obj, mn, _mx in boxes)
            y_max = max(mx.y for _obj, _mn, mx in boxes)
            y_span = max(y_max - y_min, 1e-6)
            out = []
            for obj, mn, mx in boxes:
                center = (mn + mx) * 0.5
                if tag == "F" and center.y >= y_max - y_span * 0.28:
                    out.append(obj)
                elif tag == "R" and center.y <= y_min + y_span * 0.28:
                    out.append(obj)
                elif tag in {"FL", "RL"} and center.x < 0:
                    out.append(obj)
                elif tag in {"FR", "RR"} and center.x >= 0:
                    out.append(obj)
            return out

        def _light_sources_for(names, tag):
            sources, seen = [], set()
            for obj in _objects_in_named_collections(names):
                sources.append(obj)
                seen.add(obj.name)
            wanted = {name.lower() for name in names}
            for obj in context.scene.objects:
                if not _is_export_render_mesh(obj) or obj.name in seen:
                    continue
                base = obj.name.split(".", 1)[0].lower()
                part = (part_of(obj) or "").lower()
                if base in wanted or part in wanted:
                    sources.append(obj)
                    seen.add(obj.name)
            if sources:
                return sources
            candidates = [
                obj for obj in context.scene.objects
                if _is_export_render_mesh(obj)
                and (_is_light_part(obj.name) or _is_light_part(part_of(obj) or ""))
            ]
            if not candidates:
                return []
            all_render = [obj for obj in context.scene.objects if _is_export_render_mesh(obj)]
            if not all_render:
                return []
            vehicle_y_mid = sum((wbbox(obj)[0].y + wbbox(obj)[1].y) * 0.5 for obj in all_render) / len(all_render)
            want_front = tag == "Front"
            return [
                obj for obj in candidates
                if (((wbbox(obj)[0].y + wbbox(obj)[1].y) * 0.5) >= vehicle_y_mid) == want_front
            ]

        def _export_dst_glass(tag, sources, door=None):
            if not sources:
                return False
            g = _join_bare_copies(sources, f"Glass_{tag}")
            collision = _join_bare_copies(sources, "UTM_Glass")
            if not g or not collision:
                for obj in (g, collision):
                    if obj and obj.name in bpy.data.objects:
                        bpy.data.objects.remove(obj, do_unlink=True)
                return False
            _ensure_mesh_uvs(g)
            _apply_vehicle_collision_materials(collision)
            _ensure_mesh_uvs(collision)
            extras = [g, collision]
            hinge = door_hinge(door) if door else None
            if hinge:
                snap = bpy.data.objects.new("snap_glass", None)
                snap.empty_display_type = 'PLAIN_AXES'
                snap.empty_display_size = 0.1
                snap.location = hinge
                bpy.context.scene.collection.objects.link(snap)
                extras.append(snap)
            done.append(_fbx_export(os.path.join(EXPORT_ROOT, "Dst", f"{ASSET_NAME}_Glass_{tag}.fbx"), extras))
            for obj in extras:
                bpy.data.objects.remove(obj, do_unlink=True)
            return True

        for tag, door, names in glass_slots if context.scene.rpf_export_dst_glass else ():
            sources = _find_glass_slot_sources(names) or _fallback_glass_sources(tag)
            _export_dst_glass(tag, sources, door)
        if context.scene.rpf_export_dst_glass:
            light_glass_jobs = (
                ("Light_FL", ("lights_front",), "Front", "L"),
                ("Light_FR", ("lights_front",), "Front", "R"),
                ("Light_RL", ("lights_rear",), "Rear", "L"),
                ("Light_RR", ("lights_rear",), "Rear", "R"),
            )
            for tag, names, light_tag, side in light_glass_jobs:
                temp_sources = []
                for source in _light_sources_for(names, light_tag):
                    copy = _copy_face_subset(
                        source,
                        f"_rpf_{tag}_{source.name}",
                        GLASS_FACE_MAT_TOKENS,
                        side=side,
                        include_matching=True,
                    )
                    if copy:
                        temp_sources.append(copy)
                try:
                    _export_dst_glass(tag, temp_sources)
                finally:
                    for obj in temp_sources:
                        if obj.name in bpy.data.objects:
                            bpy.data.objects.remove(obj, do_unlink=True)
        # quarters + partition glass stay in the body (no stock slots for them);
        # base-prefab VehicleLight components at v_light_* pivots provide the
        # actual illumination. Optional light-slot FBXs are still useful for
        # vehicles that carry replaceable/slot-owned lens meshes.
        if context.scene.rpf_export_light_slots:
            light_jobs = (
                ("Front", ("lights_front",)),
                ("Rear", ("lights_rear",)),
            )
            for tag, names in light_jobs:
                sources = _light_sources_for(names, tag)
                if not sources:
                    continue
                lens = _centered_visual_copy_many(sources, f"Light_{tag}")
                if not lens:
                    continue
                _ensure_mesh_uvs(lens)
                done.append(_fbx_export(
                    os.path.join(EXPORT_ROOT, "Lights", f"{ASSET_NAME}_Lights_{tag}.fbx"),
                    [lens],
                ))
                bpy.data.objects.remove(lens, do_unlink=True)

        self.report({'INFO'}, f"exported {len(done)} FBX files to {EXPORT_ROOT}")
        _write_export_identity(EXPORT_ROOT, ASSET_NAME)
        print("ENFUSION EXPORT SET:")
        for d in done:
            print("  ", d)
        if context.scene.rpf_open_web_after_export:
            try:
                url = _open_rvc_web_helper(context)
                self.report({'INFO'}, f"exported {len(done)} FBX files; web helper opened: {url}")
            except Exception as exc:
                self.report({'WARNING'}, f"exported {len(done)} FBX files; web helper failed: {exc}")
        return {'FINISHED'}


class RPF_OT_export_selected_fbx(bpy.types.Operator):
    bl_idname = "rpf.export_selected_fbx"
    bl_label = "Export Selected Object(s)"
    bl_description = "Export the current selected mesh/armature/empty objects as one standalone FBX"
    bl_options = {'REGISTER'}

    def execute(self, context):
        import os
        EXPORT_ROOT = context.scene.rpf_export_root
        ASSET_NAME = context.scene.rpf_asset_name
        if not EXPORT_ROOT:
            self.report({'ERROR'}, "set an Export Directory first")
            return {'CANCELLED'}
        identity_error = _export_identity_error(EXPORT_ROOT, ASSET_NAME)
        if identity_error:
            self.report({'ERROR'}, identity_error)
            return {'CANCELLED'}
        selected = [
            obj for obj in context.selected_objects
            if obj.type in {'MESH', 'ARMATURE', 'EMPTY'} and obj.name in context.scene.objects
        ]
        if not selected:
            self.report({'ERROR'}, "select at least one mesh, armature, or memory empty")
            return {'CANCELLED'}
        if len(selected) == 1:
            name = _safe_name_token(selected[0].name)
        else:
            name = f"{_safe_name_token(ASSET_NAME)}_Selected_{len(selected)}"
        path = os.path.join(EXPORT_ROOT, "Selected", f"{name}.fbx")
        _fbx_export(path, selected)
        self.report({'INFO'}, f"exported selected FBX: {path}")
        print("RPF SELECTED EXPORT:", path)
        return {'FINISHED'}


def _guess_addon_root_from_export(export_root):
    from pathlib import Path
    root = Path(bpy.path.abspath(export_root)).resolve()
    start = root if root.is_dir() else root.parent
    for candidate in (start, *start.parents):
        try:
            if any(candidate.glob("*.gproj")):
                return str(candidate)
        except OSError:
            pass
    parts = list(start.parts)
    if "Assets" in parts:
        return str(Path(*parts[:parts.index("Assets")]))
    return str(start)


def _rvc_web_query(context):
    from urllib.parse import urlencode
    sc = context.scene
    export_root = bpy.path.abspath(sc.rpf_export_root)
    params = {
        "addon_root": _guess_addon_root_from_export(export_root),
        "asset_name": sc.rpf_asset_name,
        "output_directory": export_root,
        "source_blend": bpy.data.filepath,
        "template": "SampleCar",
        "wheelbase": f"{sc.rpf_wheelbase:.3f}",
        "wheel_radius": f"{sc.rpf_wheel_radius:.3f}",
    }
    return urlencode({k: v for k, v in params.items() if v})


def _open_rvc_web_helper(context):
    import webbrowser
    try:
        from .rvc_web import app as web_app
    except Exception:
        import importlib
        # Use this module's actual package name (under Blender 4.5 that is
        # bl_ext.<repo>.reforger_vehicle_checker, NOT a bare 'reforger_vehicle_checker').
        web_app = importlib.import_module(__package__ + ".rvc_web.app")
    web_app.serve_in_thread(open_browser=False)
    url = f"http://127.0.0.1:{web_app.PORT}/?{_rvc_web_query(context)}"
    webbrowser.open(url)
    return url


class RPF_OT_open_build_import_web_tool(bpy.types.Operator):
    bl_idname = "rpf.open_build_import_web_tool"
    bl_label = "Open Build / Import Web Tool"
    bl_description = "Open the local post-export vehicle setup helper with this vehicle's current export settings prefilled"
    bl_options = {'REGISTER'}

    def execute(self, context):
        try:
            url = _open_rvc_web_helper(context)
        except Exception as exc:
            self.report({'ERROR'}, f"web helper failed: {exc}")
            return {'CANCELLED'}
        self.report({'INFO'}, f"Build/Import web tool at {url}")
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
            _ensure_mesh_uvs(lamp)
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


def _vehicle_center_x():
    """Stable mirror plane. Door pairs win; bbox is fallback."""
    def _part_center_x(part):
        objs = [o for o in part_objects(part) if o.type == 'MESH']
        if not objs:
            obj = bpy.data.objects.get(part)
            objs = [obj] if obj and obj.type == 'MESH' else []
        if not objs:
            return None
        mn = min(wbbox(o)[0].x for o in objs)
        mx = max(wbbox(o)[1].x for o in objs)
        return (mn + mx) * 0.5

    for left, right in (("door_FL", "door_FR"), ("door_RL", "door_RR")):
        lx = _part_center_x(left)
        rx = _part_center_x(right)
        if lx is not None and rx is not None:
            return (lx + rx) * 0.5

    meshes = [o for o in all_meshes() if not o.name.startswith(COLLIDER_PFX)]
    if not meshes:
        return 0.0
    mn = min(wbbox(o)[0].x for o in meshes)
    mx = max(wbbox(o)[1].x for o in meshes)
    return (mn + mx) * 0.5


def _mirror_point_x(point, center_x=None):
    p = Vector(point)
    cx = _vehicle_center_x() if center_x is None else center_x
    p.x = (2.0 * cx) - p.x
    return p


def _mirror_name_lr(name, direction):
    """Return counterpart name for common vehicle bone/socket naming."""
    if direction == 'RIGHT_TO_LEFT':
        left_markers = ("_FL", "_RL", "_left", "left", "passengerl", "l01", "l02")
        if (any(marker in name for marker in left_markers)
                or name.endswith(("_L", "_l")) or "_L_" in name or "_l_" in name
                or name.startswith("driver")):
            return ""
    elif direction == 'LEFT_TO_RIGHT':
        right_markers = ("_FR", "_RR", "_right", "right", "passengerr", "r01", "r02")
        if (any(marker in name for marker in right_markers)
                or name.endswith(("_R", "_r")) or "_R_" in name or "_r_" in name
                or name.startswith("codriver")):
            return ""
    replacements = []
    if direction == 'RIGHT_TO_LEFT':
        replacements = [
            ("_FR", "_FL"), ("_RR", "_RL"), ("_R", "_L"), ("_r", "_l"),
            ("_right", "_left"), ("right", "left"), ("codriver", "driver"),
            ("passengerr", "passengerl"), ("r01", "l01"), ("r02", "l02"),
        ]
    elif direction == 'LEFT_TO_RIGHT':
        replacements = [
            ("_FL", "_FR"), ("_RL", "_RR"), ("_L", "_R"), ("_l", "_r"),
            ("_left", "_right"), ("left", "right"), ("driver", "codriver"),
            ("passengerl", "passengerr"), ("l01", "r01"), ("l02", "r02"),
        ]
    for old, new in replacements:
        if old in name:
            return name.replace(old, new, 1)
    return ""


def _copy_empty_display(src, dst):
    dst.empty_display_type = src.empty_display_type
    dst.empty_display_size = src.empty_display_size
    dst.rotation_euler = src.rotation_euler.copy()
    dst.scale = src.scale.copy()


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


class RPF_OT_mirror_door_bones(bpy.types.Operator):
    bl_idname = "rpf.mirror_door_bones"
    bl_label = "Mirror Door Bones"
    bl_description = ("Mirror side door bones across the vehicle centerline. Use R->L "
                      "when the right door works and the left door snapped to a bad "
                      "fallback position; use L->R for the opposite")
    bl_options = {'REGISTER', 'UNDO'}

    direction: bpy.props.EnumProperty(
        name="Direction",
        default='RIGHT_TO_LEFT',
        items=[
            ('RIGHT_TO_LEFT', "R -> L", "Copy right-side door bone positions to mirrored left-side bones"),
            ('LEFT_TO_RIGHT', "L -> R", "Copy left-side door bone positions to mirrored right-side bones"),
            ('BOTH_FROM_MESH', "From Mesh Hinges", "Place all door bones from the current door mesh hinge/origin positions"),
        ],
    )

    def execute(self, context):
        arm = _get_armature()
        if not arm:
            self.report({'ERROR'}, "no armature - run Build Bones first")
            return {'CANCELLED'}
        checkpoint("pre_mirror_door_bones")
        if context.mode != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')
        bpy.ops.object.select_all(action='DESELECT')
        arm.hide_set(False)
        arm.select_set(True)
        context.view_layer.objects.active = arm
        bpy.ops.object.mode_set(mode='EDIT')
        eb = arm.data.edit_bones
        center_x = _vehicle_center_x()
        made = []

        def parent_name(src_bone):
            return src_bone.parent.name if src_bone.parent else "v_body"

        def ensure_bone(name, src=None):
            bone = eb.get(name)
            if bone:
                return bone
            bone = eb.new(name)
            if src:
                bone.head = src.head.copy()
                bone.tail = src.tail.copy()
                bone.roll = src.roll
                parent = eb.get(parent_name(src))
                if parent:
                    bone.parent = parent
            else:
                parent = eb.get("v_body")
                if parent:
                    bone.parent = parent
            return bone

        def mirror_pair(src_name, dst_name):
            src = eb.get(src_name)
            if not src:
                return
            dst = ensure_bone(dst_name, src)
            dst.head = arm.matrix_world.inverted() @ _mirror_point_x(arm.matrix_world @ src.head, center_x)
            dst.tail = arm.matrix_world.inverted() @ _mirror_point_x(arm.matrix_world @ src.tail, center_x)
            dst.roll = src.roll
            parent = eb.get(parent_name(src))
            if parent:
                dst.parent = parent
            made.append(f"{src_name}->{dst_name}")

        if self.direction == 'RIGHT_TO_LEFT':
            mirror_pair("v_door_r01", "v_door_l01")
            mirror_pair("v_door_r02", "v_door_l02")
        elif self.direction == 'LEFT_TO_RIGHT':
            mirror_pair("v_door_l01", "v_door_r01")
            mirror_pair("v_door_l02", "v_door_r02")
        else:
            for door, bone_name in DOOR_BONE.items():
                hinge = _obj_origin(door) or door_hinge(door)
                if hinge is None:
                    continue
                bone = ensure_bone(bone_name)
                head = arm.matrix_world.inverted() @ hinge
                bone.head = head
                bone.tail = head + Vector((0, BONE_TAIL, 0))
                bone.roll = 0.0
                parent = eb.get("v_body")
                if parent:
                    bone.parent = parent
                made.append(f"{door}->{bone_name}")
        bpy.ops.object.mode_set(mode='OBJECT')
        self.report(
            {'INFO'} if made else {'WARNING'},
            f"mirrored/placed {len(made)} door bones around X={center_x:.4f}: {', '.join(made) or 'none'}",
        )
        return {'FINISHED'} if made else {'CANCELLED'}


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


def _is_steering_mesh_name(name):
    return is_steering_name(name)


def _manual_rig_props(obj):
    if not obj:
        return "", "", ""
    return (
        str(obj.get("rpf_rig_role", "")),
        str(obj.get("rpf_slot", "")),
        str(obj.get("rpf_target_bone", "")),
    )


def _rig_role_for_obj(obj):
    role, slot, target = _manual_rig_props(obj)
    if target or role:
        return resolve_target_bone(obj.name, role, slot, target)
    return resolve_target_bone(obj.name)


_RIG_BODY_LIKE_ROLES = {"BODY", "INTERIOR", "LIGHT", "GLASS"}


def _binding_target_for_obj(context, obj):
    """Resolve the bone a bind action should write.

    Manual object props are authoritative. If the object name already resolves
    to a moving vehicle role, keep that. If the name only falls back to body-like
    roles, use the currently selected UI role/slot so generic meshes can be
    bound as rotators, suspension parts, doors, etc. without renaming first.
    """
    manual_role, manual_slot, manual_target = _manual_rig_props(obj)
    if manual_target or manual_role:
        return resolve_target_bone(obj.name, manual_role, manual_slot, manual_target)

    guessed_role, guessed_slot, guessed_target = resolve_target_bone(obj.name)
    scene_role = context.scene.rpf_rig_role
    scene_slot = context.scene.rpf_rig_slot
    scene_custom = context.scene.rpf_rig_custom_bone.strip()
    scene_target = target_bone_for_role(scene_role, scene_slot, scene_custom)
    if guessed_role in _RIG_BODY_LIKE_ROLES and scene_target:
        return scene_role, scene_slot, scene_target
    return guessed_role, guessed_slot, guessed_target


def _bone_world_head(arm, bone_name):
    if arm and bone_name in arm.data.bones:
        return arm.matrix_world @ arm.data.bones[bone_name].head_local
    return None


def _selected_mesh_center(context):
    meshes = [obj for obj in context.selected_objects if obj.type == 'MESH']
    if not meshes and context.object and context.object.type == 'MESH':
        meshes = [context.object]
    if not meshes:
        return Vector((0, 0, 0))
    mn, mx = _combined_bbox(meshes)
    return (mn + mx) * 0.5


def _ensure_armature_modifier(obj, arm):
    mod = next((m for m in obj.modifiers if m.type == 'ARMATURE'), None)
    if mod is None:
        mod = obj.modifiers.new("Armature", 'ARMATURE')
    mod.object = arm
    mod.use_vertex_groups = True
    mod.use_bone_envelopes = False
    return mod


def _skin_bone_for(name):
    obj = bpy.data.objects.get(name)
    if obj:
        _role, _slot, target = _rig_role_for_obj(obj)
        if target:
            return target
    if name in DOOR_BONE:
        return DOOR_BONE[name]
    if name.endswith("_window") and name[:-7] in DOOR_BONE:
        return DOOR_BONE[name[:-7]]
    if name in WHEEL_BONES:
        return WHEEL_BONES[name][0]
    if _is_steering_mesh_name(name):
        return "v_steering_wheel"
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


def _is_skin_target_name(name):
    targets = set(PART_ORDER) | {d + "_window" for d in DOORS} \
        | {"glass_windshield", "glass_quarters", "glass_partition"}
    obj = bpy.data.objects.get(name)
    return name in targets or _is_steering_mesh_name(name) or bool(obj and obj.get("rpf_target_bone"))


def _weighted_vertex_count(o, bone_name):
    group = o.vertex_groups.get(bone_name)
    if not group:
        return 0
    count = 0
    for vertex in o.data.vertices:
        try:
            if group.weight(vertex.index) > 0.0:
                count += 1
        except RuntimeError:
            pass
    return count


def _rig_check_objects():
    movable = set(DOORS) | set(WHEEL_BONES) | {
        "brake_FL", "brake_FR", "brake_RL", "brake_RR",
        "Steering_Wheel", "Pedal_Brake", "Pedal_Accelerator",
    }
    objects, seen = [], set()
    for name in sorted(movable):
        obj = bpy.data.objects.get(name)
        if obj and obj.type == 'MESH' and obj.name not in seen:
            objects.append(obj)
            seen.add(obj.name)
    for obj in all_meshes():
        if obj.name in seen or obj.name.startswith(COLLIDER_PFX):
            continue
        if _is_steering_mesh_name(obj.name) or obj.get("rpf_target_bone"):
            objects.append(obj)
            seen.add(obj.name)
    return objects


def _rig_binding_issues(arm):
    """Return export-blocking movable-part binding problems.

    Wheels are optional: a missing mesh is never an issue.
    """
    issues = []
    for o in _rig_check_objects():
        bone_name = _skin_bone_for(o.name)
        if bone_name not in arm.data.bones:
            issues.append(f"{o.name}: missing bone {bone_name}")
            continue
        if _weighted_vertex_count(o, bone_name) < len(o.data.vertices):
            issues.append(f"{o.name}: not fully weighted to {bone_name}")
        if not any(m.type == 'ARMATURE' and m.object == arm for m in o.modifiers):
            issues.append(f"{o.name}: missing Armature modifier")
        if o.parent != arm:
            issues.append(f"{o.name}: not parented to {arm.name}")
        elif o.parent_type != 'OBJECT':
            issues.append(f"{o.name}: bone-parented and armature-skinned (double transform)")
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
        done, missing, skipped = {}, [], 0
        for o in all_meshes():
            if not _is_skin_target_name(o.name):
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


class RPF_OT_assign_rig_role(bpy.types.Operator):
    bl_idname = "rpf.assign_rig_role"
    bl_label = "Assign Selected Object To Bone"
    bl_description = "Mark selected mesh objects with the chosen rig role/slot/bone. Manual assignment overrides name guessing"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        role = context.scene.rpf_rig_role
        slot = context.scene.rpf_rig_slot
        custom = context.scene.rpf_rig_custom_bone.strip()
        target = target_bone_for_role(role, slot, custom)
        if not target:
            self.report({'ERROR'}, "choose a rig role/slot or custom bone")
            return {'CANCELLED'}
        meshes = [obj for obj in context.selected_objects if obj.type == 'MESH']
        if not meshes and context.object and context.object.type == 'MESH':
            meshes = [context.object]
        if not meshes:
            self.report({'ERROR'}, "select one or more mesh objects")
            return {'CANCELLED'}
        for obj in meshes:
            obj["rpf_rig_role"] = role
            obj["rpf_slot"] = slot
            obj["rpf_target_bone"] = target
        context.scene.rpf_rig_custom_bone = target
        self.report({'INFO'}, f"assigned {len(meshes)} object(s) to {target}")
        return {'FINISHED'}


class RPF_OT_rename_to_rig_role(bpy.types.Operator):
    bl_idname = "rpf.rename_to_rig_role"
    bl_label = "Rename To Role"
    bl_description = "Rename selected objects to the current rig role and slot without changing their geometry"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        role = context.scene.rpf_rig_role
        slot = context.scene.rpf_rig_slot
        names = {
            "STEERING": "Steering_Wheel",
            "HANDBRAKE": "Handbrake",
            "PEDAL_BRAKE": "Pedal_Brake",
            "PEDAL_THROTTLE": "Pedal_Accelerator",
            "BODY": "body",
            "INTERIOR": "interior",
            "LIGHT": "lights",
            "GLASS": "glass",
            "WHEEL": f"wheel_{slot}",
            "ROTATOR": f"rotator_{slot}",
            "SUSPENSION": f"suspension_{slot}",
            "DOOR": "door_trunk" if slot == "TRUNK" else f"door_{slot}",
            "CUSTOM": context.scene.rpf_rig_custom_bone.strip() or "custom_bone_part",
        }
        base = names.get(role, role.lower())
        meshes = [obj for obj in context.selected_objects if obj.type == 'MESH']
        if not meshes:
            self.report({'ERROR'}, "select mesh objects to rename")
            return {'CANCELLED'}
        for index, obj in enumerate(meshes, 1):
            obj.name = base if len(meshes) == 1 else f"{base}_{index:02d}"
        self.report({'INFO'}, f"renamed {len(meshes)} object(s) as {base}")
        return {'FINISHED'}


class RPF_OT_create_missing_rig_bone(bpy.types.Operator):
    bl_idname = "rpf.create_missing_rig_bone"
    bl_label = "Create Missing Bone"
    bl_description = "Create the selected role's SampleCar-style bone at the selected mesh center if it is missing"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        arm = _get_armature()
        if not arm:
            self.report({'ERROR'}, "no armature - run Build Bones first")
            return {'CANCELLED'}
        role = context.scene.rpf_rig_role
        slot = context.scene.rpf_rig_slot
        custom = context.scene.rpf_rig_custom_bone.strip()
        bone_name = target_bone_for_role(role, slot, custom)
        if not bone_name:
            self.report({'ERROR'}, "choose a target bone")
            return {'CANCELLED'}
        if bone_name in arm.data.bones:
            self.report({'INFO'}, f"{bone_name} already exists")
            return {'FINISHED'}
        parent_name = SAMPLECAR_PARENT.get(bone_name, "v_body")
        head_world = _selected_mesh_center(context)
        if context.mode != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')
        bpy.ops.object.select_all(action='DESELECT')
        arm.hide_set(False)
        arm.select_set(True)
        context.view_layer.objects.active = arm
        bpy.ops.object.mode_set(mode='EDIT')
        eb = arm.data.edit_bones
        parent = eb.get(parent_name) or eb.get("v_body") or eb.get("v_root")
        bone = eb.new(bone_name)
        bone.head = arm.matrix_world.inverted() @ head_world
        axis = STEER_DIR if bone_name == "v_steering_wheel" else Vector((0, 1, 0))
        bone.tail = bone.head + axis.normalized() * BONE_TAIL
        bone.roll = 0.0
        if parent:
            bone.parent = parent
        bpy.ops.object.mode_set(mode='OBJECT')
        self.report({'INFO'}, f"created {bone_name} parented to {parent.name if parent else 'none'}")
        return {'FINISHED'}


class RPF_OT_bind_selected_to_rig_bone(bpy.types.Operator):
    bl_idname = "rpf.bind_selected_to_rig_bone"
    bl_label = "Bind Whole Object 100%"
    bl_description = "Rigid-bind selected mesh objects to their manual target bone, or to the role resolver's guessed bone"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        arm = _get_armature()
        if not arm:
            self.report({'ERROR'}, "no armature - run Build Bones first")
            return {'CANCELLED'}
        meshes = [obj for obj in context.selected_objects if obj.type == 'MESH']
        if not meshes and context.object and context.object.type == 'MESH':
            meshes = [context.object]
        if not meshes:
            self.report({'ERROR'}, "select mesh objects to bind")
            return {'CANCELLED'}
        done, missing = [], []
        for obj in meshes:
            role, slot, bone_name = _binding_target_for_obj(context, obj)
            if not bone_name or bone_name not in arm.data.bones:
                missing.append(f"{obj.name}->{bone_name or '?'}")
                continue
            obj["rpf_rig_role"] = role
            obj["rpf_slot"] = slot
            obj["rpf_target_bone"] = bone_name
            _rigid_bind(obj, arm, bone_name)
            done.append(f"{obj.name}->{bone_name}")
        if missing:
            self.report({'WARNING'}, f"bound {len(done)}; missing bones: {', '.join(missing)}")
        else:
            self.report({'INFO'}, f"bound {len(done)} object(s): {', '.join(done[:4])}")
        return {'FINISHED'} if done else {'CANCELLED'}


class RPF_OT_bind_edit_selection_to_rig_bone(bpy.types.Operator):
    bl_idname = "rpf.bind_edit_selection_to_rig_bone"
    bl_label = "Bind Edit Selection 100%"
    bl_description = "In Edit Mode, set selected vertices/faces to weight 1.0 on the chosen bone without rebaking object transforms"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        arm = _get_armature()
        obj = context.object
        if not arm or not obj or obj.type != 'MESH':
            self.report({'ERROR'}, "select a mesh and ensure the armature exists")
            return {'CANCELLED'}
        role, slot, bone_name = _binding_target_for_obj(context, obj)
        if not bone_name or bone_name not in arm.data.bones:
            self.report({'ERROR'}, f"missing target bone {bone_name or '?'}")
            return {'CANCELLED'}
        was_edit = context.mode == 'EDIT_MESH'
        if was_edit:
            bpy.ops.object.mode_set(mode='OBJECT')
        selected = [v.index for v in obj.data.vertices if v.select]
        if not selected:
            self.report({'ERROR'}, "no selected vertices/faces")
            if was_edit:
                bpy.ops.object.mode_set(mode='EDIT')
            return {'CANCELLED'}
        group = obj.vertex_groups.get(bone_name) or obj.vertex_groups.new(name=bone_name)
        group.add(selected, 1.0, 'REPLACE')
        _ensure_armature_modifier(obj, arm)
        obj.parent = arm
        obj.parent_type = 'OBJECT'
        obj.parent_bone = ""
        obj["rpf_rig_role"] = role or context.scene.rpf_rig_role
        obj["rpf_slot"] = slot or context.scene.rpf_rig_slot
        obj["rpf_target_bone"] = bone_name
        if was_edit:
            bpy.ops.object.mode_set(mode='EDIT')
        self.report({'INFO'}, f"weighted {len(selected)} vertices on {obj.name} to {bone_name}")
        return {'FINISHED'}


class RPF_OT_mirror_selected_rig_bone(bpy.types.Operator):
    bl_idname = "rpf.mirror_selected_rig_bone"
    bl_label = "Mirror Opposite Bone"
    bl_description = "Mirror the selected/target bone to its opposite left/right counterpart across the vehicle centerline"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        arm = _get_armature()
        if not arm:
            self.report({'ERROR'}, "no armature - run Build Bones first")
            return {'CANCELLED'}
        bone_name = context.scene.rpf_rig_custom_bone.strip()
        if not bone_name and context.object and context.object.type == 'MESH':
            _role, _slot, bone_name = _rig_role_for_obj(context.object)
        if not bone_name and arm.data.bones.active:
            bone_name = arm.data.bones.active.name
        dst_name = opposite_bone_name(bone_name)
        if not bone_name or not dst_name:
            self.report({'ERROR'}, "choose a left/right source bone")
            return {'CANCELLED'}
        if bone_name not in arm.data.bones:
            self.report({'ERROR'}, f"source bone {bone_name} missing")
            return {'CANCELLED'}
        if context.mode != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')
        bpy.ops.object.select_all(action='DESELECT')
        arm.hide_set(False)
        arm.select_set(True)
        context.view_layer.objects.active = arm
        bpy.ops.object.mode_set(mode='EDIT')
        eb = arm.data.edit_bones
        src = eb.get(bone_name)
        dst = eb.get(dst_name)
        if not dst:
            dst = eb.new(dst_name)
        center_x = _vehicle_center_x()
        dst.head = arm.matrix_world.inverted() @ _mirror_point_x(arm.matrix_world @ src.head, center_x)
        dst.tail = arm.matrix_world.inverted() @ _mirror_point_x(arm.matrix_world @ src.tail, center_x)
        dst.roll = src.roll
        parent_name = SAMPLECAR_PARENT.get(dst_name) or (src.parent.name if src.parent else "")
        parent = eb.get(parent_name)
        if parent:
            dst.parent = parent
        bpy.ops.object.mode_set(mode='OBJECT')
        self.report({'INFO'}, f"mirrored {bone_name} -> {dst_name}")
        return {'FINISHED'}


class RPF_OT_validate_rig_assignments(bpy.types.Operator):
    bl_idname = "rpf.validate_rig_assignments"
    bl_label = "Validate Rig"
    bl_description = "Check manually assigned/guessed moving parts for missing bones, vertex groups, and armature modifiers"
    bl_options = {'REGISTER'}

    def execute(self, context):
        arm = _get_armature()
        if not arm:
            self.report({'ERROR'}, "no armature")
            return {'CANCELLED'}
        issues = _rig_binding_issues(arm)
        if issues:
            self.report({'WARNING'}, f"{len(issues)} rig issue(s): " + "; ".join(issues[:5]))
        else:
            self.report({'INFO'}, "rig assignments valid")
        return {'FINISHED'}


class RPF_OT_select_bone(bpy.types.Operator):
    bl_idname = "rpf.select_bone"
    bl_label = "Select Bone"
    bl_description = "Edit-select this bone and frame it for review/movement"
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
        bpy.ops.object.mode_set(mode='EDIT')
        for b in arm.data.edit_bones:
            b.select = b.select_head = b.select_tail = (b.name == self.bone)
        arm.data.edit_bones.active = arm.data.edit_bones[self.bone]
        frame_view(context)
        h = arm.matrix_world @ arm.data.edit_bones[self.bone].head
        context.scene.rpf_rig_custom_bone = self.bone
        self.report({'INFO'}, f"editing {self.bone} head at {[round(v, 3) for v in h]}")
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


class RPF_OT_mirror_memory_points(bpy.types.Operator):
    bl_idname = "rpf.mirror_memory_points"
    bl_label = "Mirror Memory Points"
    bl_description = ("Mirror socket/memory empties across the vehicle centerline. "
                      "Creates missing opposite-side sockets and preserves display size/type")
    bl_options = {'REGISTER', 'UNDO'}

    direction: bpy.props.EnumProperty(
        name="Direction",
        default='RIGHT_TO_LEFT',
        items=[
            ('RIGHT_TO_LEFT', "R -> L", "Copy right-side sockets to mirrored left-side sockets"),
            ('LEFT_TO_RIGHT', "L -> R", "Copy left-side sockets to mirrored right-side sockets"),
        ],
    )
    selected_only: bpy.props.BoolProperty(
        name="Selected only",
        default=False,
        description="Mirror only selected socket empties; otherwise mirror all known left/right sockets",
    )

    def execute(self, context):
        checkpoint("pre_mirror_memory_points")
        coll = get_coll(SOCKET_COLL)
        center_x = _vehicle_center_x()
        if self.selected_only:
            sources = [
                obj for obj in context.selected_objects
                if obj.type == 'EMPTY' and obj.name in bpy.data.objects
            ]
        else:
            sources = [obj for obj in bpy.data.objects if obj.type == 'EMPTY']
            sources = [
                obj for obj in sources
                if obj.name in {socket.name for socket in coll.objects}
                or obj.name.startswith(("v_light", "driver", "codriver", "passenger"))
            ]
        made = []
        for src in sources:
            dst_name = _mirror_name_lr(src.name, self.direction)
            if not dst_name or dst_name == src.name:
                continue
            dst = bpy.data.objects.get(dst_name)
            if dst is None:
                dst = bpy.data.objects.new(dst_name, None)
                coll.objects.link(dst)
            elif dst.name not in {obj.name for obj in coll.objects}:
                try:
                    coll.objects.link(dst)
                except RuntimeError:
                    pass
            _copy_empty_display(src, dst)
            dst.location = _mirror_point_x(src.matrix_world.translation, center_x)
            dst["rpf_mirrored_from"] = src.name
            made.append(f"{src.name}->{dst.name}")
        bpy.ops.object.select_all(action='DESELECT')
        for pair in made:
            dst_name = pair.split("->", 1)[1]
            obj = bpy.data.objects.get(dst_name)
            if obj:
                obj.select_set(True)
        self.report(
            {'INFO'} if made else {'WARNING'},
            f"mirrored {len(made)} memory points around X={center_x:.4f}: {', '.join(made[:8])}"
            + ("..." if len(made) > 8 else ""),
        )
        return {'FINISHED'} if made else {'CANCELLED'}


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

COLLISION_REVIEW_MODES = (
    ('MODEL', "Model"),
    ('UCX', "UCX"),
    ('FIRE', "FireGeo"),
    ('GLASS', "Glass"),
    ('WHEELS', "All Wheel"),
    ('ALL', "All"),
)

WHEEL_REVIEW_MODES = (
    ('WHEEL_VC', "VehicleComplex"),
    ('WHEEL_FG', "Wheel FireGeo"),
    ('WHEEL_MT', "MineTrigger"),
)


def _draw_accordion(layout, scene, prop_name, title, icon='NONE'):
    box = layout.box()
    expanded = bool(getattr(scene, prop_name, True))
    row = box.row(align=True)
    row.prop(
        scene,
        prop_name,
        text=title,
        icon='TRIA_DOWN' if expanded else 'TRIA_RIGHT',
        emboss=False,
    )
    if icon != 'NONE':
        row.label(text="", icon=icon)
    return box if expanded else None


def _draw_collision_review_controls(layout, scene):
    active_mode = scene.get("rpf_collision_view", "MODEL")
    row = layout.row(align=True)
    for mode, label in COLLISION_REVIEW_MODES:
        op = row.operator("rpf.collision_view", text=label, depress=(active_mode == mode))
        op.mode = mode
    row = layout.row(align=True)
    for mode, label in WHEEL_REVIEW_MODES:
        op = row.operator("rpf.collision_view", text=label, depress=(active_mode == mode))
        op.mode = mode
    row = layout.row(align=True)
    for axis, label in (('LEFT', "L"), ('RIGHT', "R"), ('FRONT', "F"),
                        ('BACK', "B"), ('TOP', "Top")):
        op = row.operator("rpf.view_axis", text=label)
        op.axis = axis
    layout.operator("rpf.sort_collapse", icon='OUTLINER_COLLECTION')
    selected = [obj for obj in bpy.context.selected_objects if obj.type == 'MESH' and obj.name.startswith(COLLIDER_PFX)]
    if selected:
        obj = selected[0]
        usage = obj.get("usage", _collider_usage(obj.name))
        surfaces = obj.get("rpf_surface_properties", "") or "|".join(_sync_collider_surface_properties(obj))
        layout.label(text=f"{obj.name}: {usage}", icon='MATERIAL')
        if surfaces:
            parts = surfaces.split("|")
            layout.label(text=parts[0][:96], icon='INFO')
            if len(parts) > 1:
                layout.label(text=f"+ {len(parts) - 1} more surface material(s)", icon='MATERIAL')


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
            box = _draw_accordion(l, sc, "rpf_ui_rig_assignment", "Rig Assignment / Binding", 'GROUP_VERTEX')
            if box:
                obj = context.object if context.object and context.object.type == 'MESH' else None
                if obj:
                    role, slot, target = _rig_role_for_obj(obj)
                    box.label(text=f"active: {obj.name} -> {target or 'unresolved'}", icon='OBJECT_DATA')
                    if role:
                        box.label(text=f"role: {role}{(' ' + slot) if slot else ''}", icon='INFO')
                row = box.row(align=True)
                row.prop(sc, "rpf_rig_role", text="Role")
                row.prop(sc, "rpf_rig_slot", text="Slot")
                box.prop(sc, "rpf_rig_custom_bone", text="Bone")
                row = box.row(align=True)
                row.operator("rpf.assign_rig_role", icon='BONE_DATA')
                row.operator("rpf.rename_to_rig_role", text="Rename To Role", icon='SORTALPHA')
                row = box.row(align=True)
                row.operator("rpf.create_missing_rig_bone", icon='ADD')
                row.operator("rpf.mirror_selected_rig_bone", icon='MOD_MIRROR')
                row = box.row(align=True)
                row.operator("rpf.bind_selected_to_rig_bone", icon='MOD_VERTEX_WEIGHT')
                row.operator("rpf.bind_edit_selection_to_rig_bone", text="Bind Edit Selection 100%", icon='FACESEL')
                box.operator("rpf.validate_rig_assignments", icon='CHECKMARK')
            box = _draw_accordion(l, sc, "rpf_ui_rig_door_repair", "Door Bone Repair", 'BONE_DATA')
            if box:
                row = box.row(align=True)
                op = row.operator("rpf.mirror_door_bones", text="Mirror R -> L")
                op.direction = 'RIGHT_TO_LEFT'
                op = row.operator("rpf.mirror_door_bones", text="Mirror L -> R")
                op.direction = 'LEFT_TO_RIGHT'
                op = box.operator("rpf.mirror_door_bones", text="Place Door Bones From Mesh Hinges")
                op.direction = 'BOTH_FROM_MESH'
                box.operator("rpf.skin_parts", icon='MOD_VERTEX_WEIGHT')
            box = _draw_accordion(l, sc, "rpf_ui_rig_wheel_placement", "Wheel Placement", 'GIZMO')
            if box:
                box.label(text="Visual road wheels are Blender references; master export excludes them.")
                box.operator("rpf.wheel_targets", icon='SPHERE')
                box.prop(sc, "rpf_mirror_x", text="Mirror X (L/R symmetric)")
                row = box.row(align=True)
                row.operator("rpf.apply_wheel_targets", icon='CHECKMARK')
                row.operator("rpf.clear_wheel_targets", text="", icon='X')
            arm = _get_armature()
            if arm:
                box = _draw_accordion(l, sc, "rpf_ui_rig_bone_review", f"Bones ({len(arm.data.bones)}) - click to edit", 'BONE_DATA')
                if box:
                    grid = box.grid_flow(columns=2, even_columns=True)
                    for b in sorted(arm.data.bones, key=lambda b: b.name):
                        op = grid.operator("rpf.select_bone", text=b.name)
                        op.bone = b.name
                    box.operator("rpf.pose_reset", icon='LOOP_BACK')
            else:
                l.label(text="no armature yet — Build Bones", icon='INFO')

        elif tab == 'MEMORY':
            l.operator("rpf.add_sockets", icon='EMPTY_AXIS')
            box = l.box()
            box.label(text="Mirror Memory Points", icon='MOD_MIRROR')
            row = box.row(align=True)
            op = row.operator("rpf.mirror_memory_points", text="Mirror R -> L")
            op.direction = 'RIGHT_TO_LEFT'
            op.selected_only = False
            op = row.operator("rpf.mirror_memory_points", text="Mirror L -> R")
            op.direction = 'LEFT_TO_RIGHT'
            op.selected_only = False
            row = box.row(align=True)
            op = row.operator("rpf.mirror_memory_points", text="Selected R -> L")
            op.direction = 'RIGHT_TO_LEFT'
            op.selected_only = True
            op = row.operator("rpf.mirror_memory_points", text="Selected L -> R")
            op.direction = 'LEFT_TO_RIGHT'
            op.selected_only = True
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
            box = _draw_accordion(l, sc, "rpf_ui_build_review", "Collision Review", 'HIDE_OFF')
            if box:
                _draw_collision_review_controls(box, sc)

            abox = _draw_accordion(l, sc, "rpf_ui_build_analysis", "Smart Part Analysis", 'VIEWZOOM')
            if abox:
                row = abox.row(align=True)
                row.operator("rpf.analyze_vehicle_parts", icon='ZOOM_SELECTED')
                op = row.operator("rpf.analyze_vehicle_parts", text="Analyze + Select", icon='RESTRICT_SELECT_OFF')
                op.select_vehicle_groups = True
                summary = sc.get("rpf_semantic_summary", "")
                roles = sc.get("rpf_semantic_roles", "")
                if summary:
                    abox.label(text=summary[:96])
                if roles:
                    abox.label(text=roles[:96])
                grid = abox.grid_flow(columns=3, even_columns=True)
                for group in ("exterior", "cab", "rear_area", "hood", "undercarriage",
                              "door_FL", "door_FR", "door_RL", "door_RR", "door_trunk",
                              "glass", "lights_front", "lights_rear", "wheel_FL", "wheel_FR",
                              "wheel_RL", "wheel_RR"):
                    op = grid.operator("rpf.select_semantic_group", text=group)
                    op.group = group

            onebox = _draw_accordion(l, sc, "rpf_ui_build_oneclick", "One-Click Physics + Tidy", 'MODIFIER')
            if onebox:
                row = onebox.row(align=True)
                row.prop(sc, "rpf_auto_analyze_collision", text="Analyze")
                row.prop(sc, "rpf_build_use_vhacd", text="Use V-HACD/CoACD")
                row.prop(sc, "rpf_build_do_lod", text="Bake LOD")
                onebox.prop(sc, "rpf_build_categories", text="Groups")
                op = onebox.operator("rpf.build_all_physics", icon='AUTO')
                op.use_vhacd = sc.rpf_build_use_vhacd
                op.do_lod = sc.rpf_build_do_lod
                frow = onebox.row(align=True)
                frow.operator("rpf.fix_ucx", icon='CHECKMARK')
                frow.operator("rpf.cleanup_colliders", text="Tidy (generated)", icon='TRASH').mode = 'GENERATED'
                frow2 = onebox.row(align=True)
                frow2.operator("rpf.cleanup_colliders", text="Remove invalid", icon='TRASH').mode = 'INVALID'
                frow2.operator("rpf.cleanup_colliders", text="Remove all", icon='TRASH').mode = 'ALL'

            cbox = _draw_accordion(l, sc, "rpf_ui_build_ucx", "Collision (UCX)", 'MESH_CUBE')
            if cbox:
                cbox.operator("rpf.build_colliders", icon='MESH_CUBE')
                crow = cbox.row(align=True)
                op = crow.operator("rpf.selected_parts_to_ucx", icon='MESH_ICOSPHERE')
                op.replace_generated = sc.rpf_ucx_replace_existing
                crow.operator("rpf.validate_ucx", text="Validate", icon='CHECKMARK')
                row = cbox.row(align=True)
                op = row.operator("rpf.selected_faces_to_ucx", text="Edit Faces -> UCX", icon='FACESEL')
                op.use_decomposition = sc.rpf_selected_faces_use_decomp
                op.split_loose = sc.rpf_selected_faces_split_loose
                op.replace_generated = sc.rpf_ucx_replace_existing
                row.operator("rpf.apply_collision_materials", text="Fix Layer + Gamemats", icon='MATERIAL')
                row = cbox.row(align=True)
                row.prop(sc, "rpf_selected_faces_use_decomp", text="Decompose")
                row.prop(sc, "rpf_selected_faces_split_loose", text="Split islands")
                cbox.prop(sc, "rpf_ucx_replace_existing", text="Replace existing generated UCX")
                cbox.operator("rpf.convexify_selected_ucx", icon='MESH_ICOSPHERE')

            mbox = _draw_accordion(l, sc, "rpf_ui_build_materials", "Collider Materials", 'MATERIAL')
            if mbox:
                row = mbox.row(align=True)
                row.prop(sc, "rpf_collider_setup_layer", text="Layer")
                row.prop(sc, "rpf_collider_setup_gamemat", text="Gamemat")
                row = mbox.row(align=True)
                row.prop(sc, "rpf_collider_setup_sort", text="Sort into collections")
                row.prop(sc, "rpf_collider_setup_armored", text="Armored policy")
                row = mbox.row(align=True)
                row.operator("rpf.collider_setup", text="Apply To Selected", icon='MATERIAL')
                row.operator("rpf.apply_collision_materials", text="Auto Vehicle Policy", icon='AUTO')
                mbox.label(text="Edit Mode on UTM: assigns gamemat to selected faces only.", icon='INFO')

            vbox = _draw_accordion(l, sc, "rpf_ui_build_vhacd", "V-HACD multi-hull (collision / LOD geo)", 'MOD_REMESH')
            if vbox:
                vbox.prop(sc, "rpf_ucx_backend", text="Backend")
                vbox.prop(sc, "rpf_vhacd_exe", text="V-HACD exe (optional)")
                vbox.operator("rpf.autotune_collision_settings", icon='AUTO')
                autotune = sc.get("rpf_autotune_summary", "")
                if autotune:
                    vbox.label(text=autotune[:96], icon='INFO')
                row = vbox.row(align=True)
                row.prop(sc, "rpf_ucx_max_hulls", text="Max Hulls")
                row.prop(sc, "rpf_ucx_max_faces", text="Face Cap")
                row = vbox.row(align=True)
                row.prop(sc, "rpf_ucx_decimate", text="Input Tris")
                row.prop(sc, "rpf_ucx_concavity", text="Concavity")
                vbox.prop(sc, "rpf_ucx_threads", text="Worker Threads")
                adv = _draw_accordion(vbox, sc, "rpf_ui_build_vhacd_advanced", "Enfusion/VHACD controls", 'TOOL_SETTINGS')
                if adv:
                    row = adv.row(align=True)
                    row.prop(sc, "rpf_vhacd_resolution", text="Voxel Res")
                    row.prop(sc, "rpf_vhacd_volume_error", text="Vol Err")
                    row = adv.row(align=True)
                    row.prop(sc, "rpf_vhacd_recursion_depth", text="Depth")
                    row.prop(sc, "rpf_vhacd_max_vertices", text="Max Verts")
                    row = adv.row(align=True)
                    row.prop(sc, "rpf_vhacd_shrinkwrap", text="Shrinkwrap")
                    row.prop(sc, "rpf_vhacd_split_hulls", text="Best split")
                    row = adv.row(align=True)
                    row.prop(sc, "rpf_vhacd_fill_mode", text="Fill")
                    row.prop(sc, "rpf_vhacd_min_edge_length", text="Min Edge")
                    adv.prop(sc, "rpf_vhacd_pre_scale", text="Pre-scale")
                vrow = vbox.row(align=True)
                op = vrow.operator("rpf.vhacd_selected", icon='MESH_ICOSPHERE')
                op.max_hulls = sc.rpf_ucx_max_hulls
                op.max_faces = sc.rpf_ucx_max_faces
                op.decimate_target = sc.rpf_ucx_decimate
                op.threshold = sc.rpf_ucx_concavity
                op.backend = sc.rpf_ucx_backend
                op.thread_count = sc.rpf_ucx_threads
                op.replace_generated = sc.rpf_ucx_replace_existing
                vrow.operator("rpf.find_vhacd_exe", text="", icon='VIEWZOOM')
                vrow.operator("rpf.install_vhacd_deps", text="Install deps", icon='IMPORT')

            gbox = _draw_accordion(l, sc, "rpf_ui_build_geometry", "Geometry / Parts", 'MESH_ICOSPHERE')
            if gbox:
                gbox.operator("rpf.build_firegeo", text="Build FireGeo", icon='MESH_ICOSPHERE')
                row = gbox.row(align=True)
                row.prop(sc, "rpf_direct_copy_ratio", text="Copy Ratio")
                row.prop(sc, "rpf_direct_copy_merge", text="Merge")
                row = gbox.row(align=True)
                op = row.operator("rpf.selected_to_direct_collision", text="Selected -> UCX Copy", icon='DUPLICATE')
                op.mode = 'UCXVEHICLE'
                op.decimate_ratio = sc.rpf_direct_copy_ratio
                op.merge_selected = sc.rpf_direct_copy_merge
                op = row.operator("rpf.selected_to_direct_collision", text="Selected -> UTM FireGeo", icon='DUPLICATE')
                op.mode = 'FIREGEO'
                op.decimate_ratio = sc.rpf_direct_copy_ratio
                op.merge_selected = sc.rpf_direct_copy_merge
                row = gbox.row(align=True)
                op = row.operator("rpf.selected_to_direct_collision", text="Glass", icon='DUPLICATE')
                op.mode = 'GLASSFIRE'
                op.decimate_ratio = sc.rpf_direct_copy_ratio
                op.merge_selected = sc.rpf_direct_copy_merge
                op = row.operator("rpf.selected_to_direct_collision", text="UTM VehicleComplex Detail", icon='DUPLICATE')
                op.mode = 'VEHICLECOMPLEX'
                op.decimate_ratio = sc.rpf_direct_copy_ratio
                op.merge_selected = sc.rpf_direct_copy_merge
                gbox.operator("rpf.separate_wheels", icon='MESH_CIRCLE')

        elif tab == 'EXPORT':
            box = _draw_accordion(l, sc, "rpf_ui_export_review", "Collision Review", 'HIDE_OFF')
            if box:
                _draw_collision_review_controls(box, sc)

            box = _draw_accordion(l, sc, "rpf_ui_export_target", "Export Target", 'FILE_FOLDER')
            if box:
                box.prop(sc, "rpf_asset_name", text="Asset")
                box.prop(sc, "rpf_export_root", text="Directory")
                box.prop(sc, "rpf_open_web_after_export", text="Open web helper after export")
                box.operator("rpf.open_build_import_web_tool", icon='URL')

            box = _draw_accordion(l, sc, "rpf_ui_export_master", "Master FBX Includes", 'CHECKMARK')
            if box:
                box.prop(sc, "rpf_export_render", text="Render exterior / interior / doors")
                box.prop(sc, "rpf_export_armature", text="Armature")
                box.prop(sc, "rpf_export_memory", text="Memory points / sockets")
                box.prop(sc, "rpf_auto_skin_before_export", text="Auto repair rigid part bindings")
                box.operator("rpf.skin_parts", text="Skin All Parts Now", icon='MOD_VERTEX_WEIGHT')
                box.prop(sc, "rpf_export_vehicle_collision", text="Vehicle collision (UCL / UCX)")
                box.prop(sc, "rpf_export_firegeo", text="FireGeo / component hit zones")
                box.prop(sc, "rpf_export_glass_firegeo", text="Armored glass FireGeo (UTM_Glass)")
                box.prop(sc, "rpf_export_visual_glass", text="Visual glass in master (bulletproof)")

            box = _draw_accordion(l, sc, "rpf_ui_export_slots", "Separate Slot Exports", 'OUTLINER_COLLECTION')
            if box:
                box.prop(sc, "rpf_export_wheel_slot", text="Wheel FBX (optional)")
                if sc.rpf_export_wheel_slot:
                    box.prop(sc, "rpf_export_wheel_slot_mode", text="Wheel mode")
                box.prop(sc, "rpf_export_dst_glass", text="DST glass FBXs")
                box.prop(sc, "rpf_export_light_slots", text="Light cover FBXs")
                box.operator("rpf.export_selected_fbx", text="Export Selected FBX", icon='EXPORT')
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
           RPF_OT_selected_faces_to_ucx, RPF_OT_apply_collision_materials,
           RPF_OT_collider_setup,
           RPF_OT_autotune_collision_settings,
           RPF_OT_convexify_selected_ucx,
           RPF_OT_analyze_vehicle_parts, RPF_OT_select_semantic_group,
           RPF_OT_selected_to_direct_collision,
           RPF_OT_separate_wheels, RPF_OT_vhacd_selected, RPF_OT_install_vhacd_deps,
           RPF_OT_find_vhacd_exe,
           RPF_OT_cleanup_colliders, RPF_OT_fix_ucx, RPF_OT_build_all_physics,
           RPF_OT_collision_view, RPF_OT_view_axis, RPF_OT_sort_collapse,
           RPF_OT_auto_setup, RPF_OT_organize, RPF_OT_quick_select, RPF_OT_review,
           RPF_OT_stop_review, RPF_OT_door_open, RPF_OT_doors_close,
           RPF_OT_send_interior, RPF_OT_add_selected, RPF_OT_move_selected,
           RPF_OT_snap_back, RPF_OT_check_transforms, RPF_OT_apply_textures,
           RPF_OT_finalize, RPF_OT_explode_part, RPF_OT_rejoin_parts,
           RPF_OT_extract_selection, RPF_OT_export_enfusion, RPF_OT_open_build_import_web_tool,
           RPF_OT_export_selected_fbx, RPF_OT_export_em_lamps,
           RPF_OT_build_rig, RPF_OT_mirror_door_bones,
           RPF_OT_assign_rig_role, RPF_OT_rename_to_rig_role,
           RPF_OT_create_missing_rig_bone, RPF_OT_bind_selected_to_rig_bone,
           RPF_OT_bind_edit_selection_to_rig_bone, RPF_OT_mirror_selected_rig_bone,
           RPF_OT_validate_rig_assignments,
           RPF_OT_skin_parts, RPF_OT_select_bone, RPF_OT_pose_reset,
           RPF_OT_recenter, RPF_OT_wheel_targets, RPF_OT_apply_wheel_targets,
           RPF_OT_clear_wheel_targets,
           RPF_OT_add_sockets, RPF_OT_mirror_memory_points,
           RPF_OT_add_socket_cursor, RPF_OT_add_bench_seats, RPF_OT_select_socket,
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
    for prop_name, label in (
        ("rpf_ui_build_review", "Build collision review"),
        ("rpf_ui_build_analysis", "Build smart part analysis"),
        ("rpf_ui_build_oneclick", "Build one-click physics"),
        ("rpf_ui_build_ucx", "Build UCX collision"),
        ("rpf_ui_build_materials", "Build collider material setup"),
        ("rpf_ui_build_vhacd", "Build V-HACD controls"),
        ("rpf_ui_build_vhacd_advanced", "Build advanced V-HACD controls"),
        ("rpf_ui_build_geometry", "Build geometry parts"),
        ("rpf_ui_export_review", "Export collision review"),
        ("rpf_ui_export_target", "Export target"),
        ("rpf_ui_export_master", "Export master FBX includes"),
        ("rpf_ui_export_slots", "Export slot FBXs"),
        ("rpf_ui_rig_assignment", "Rig assignment"),
        ("rpf_ui_rig_door_repair", "Rig door repair"),
        ("rpf_ui_rig_wheel_placement", "Rig wheel placement"),
        ("rpf_ui_rig_bone_review", "Rig bone review"),
    ):
        setattr(
            bpy.types.Scene,
            prop_name,
            bpy.props.BoolProperty(name=label, default=True),
        )
    bpy.types.Scene.rpf_rig_role = bpy.props.EnumProperty(
        name="Rig role",
        default='STEERING',
        items=[
            ('STEERING', "Steering Wheel", "Bind to v_steering_wheel"),
            ('WHEEL', "Wheel", "Road wheel slot reference mesh"),
            ('ROTATOR', "Rotator", "Steering rotator mesh/bone"),
            ('SUSPENSION', "Suspension", "Suspension/strut mesh/bone"),
            ('DOOR', "Door", "Door or trunk movable mesh"),
            ('BODY', "Body", "Rigid body mesh bound to v_body"),
            ('INTERIOR', "Interior", "Interior mesh bound to v_body"),
            ('LIGHT', "Light", "Light or lens mesh bound to v_body"),
            ('GLASS', "Glass", "Glass render mesh bound to v_body or door if assigned"),
            ('HANDBRAKE', "Handbrake", "Bind to v_handbrake"),
            ('PEDAL_BRAKE', "Brake Pedal", "Bind to v_pedal_brake"),
            ('PEDAL_THROTTLE', "Throttle Pedal", "Bind to v_pedal_throttle"),
            ('CUSTOM', "Custom Bone", "Use the custom bone field directly"),
        ])
    bpy.types.Scene.rpf_rig_slot = bpy.props.EnumProperty(
        name="Rig slot",
        default='FL',
        items=[
            ('FL', "FL/L01", "Front left / l01"),
            ('FR', "FR/R01", "Front right / r01"),
            ('RL', "RL/L02", "Rear left / l02"),
            ('RR', "RR/R02", "Rear right / r02"),
            ('TRUNK', "Trunk", "Trunk/tailgate slot"),
        ])
    bpy.types.Scene.rpf_rig_custom_bone = bpy.props.StringProperty(
        name="Target bone",
        default="v_steering_wheel",
        description="Explicit target bone for manual assignment, custom roles, and mirror/review operations")
    bpy.types.Scene.rpf_asset_name = bpy.props.StringProperty(
        name="Asset", default=ASSET_NAME,
        description="Asset/file base name used by the exporters")
    bpy.types.Scene.rpf_export_root = bpy.props.StringProperty(
        name="Export Root", default=EXPORT_ROOT, subtype='DIR_PATH',
        description="Addon asset folder the FBX set is written into")
    bpy.types.Scene.rpf_open_web_after_export = bpy.props.BoolProperty(
        name="Open web helper after export", default=True,
        description="After FBX export, open the local browser helper prefilled with this vehicle's export settings")
    bpy.types.Scene.rpf_export_render = bpy.props.BoolProperty(
        name="Render meshes", default=True)
    bpy.types.Scene.rpf_export_armature = bpy.props.BoolProperty(
        name="Armature", default=True)
    bpy.types.Scene.rpf_export_memory = bpy.props.BoolProperty(
        name="Memory points", default=True)
    bpy.types.Scene.rpf_auto_skin_before_export = bpy.props.BoolProperty(
        name="Auto repair rigid part bindings", default=True,
        description="Before export, run Skin All Parts automatically if doors, wheels, brakes, steering, or pedals lost rigid armature binding")
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
    bpy.types.Scene.rpf_export_wheel_slot_mode = bpy.props.EnumProperty(
        name="Wheel slot mode",
        default='FRONT_REAR',
        items=[
            ('SINGLE', "Single", "Export one wheel slot FBX from the first available wheel"),
            ('FRONT_REAR', "Front + Rear", "Export separate front and rear wheel slot FBXs; useful for rear dually wheels"),
            ('ALL', "All four", "Export FL/FR/RL/RR wheel slot FBXs"),
            ('SELECTED', "Selected Alt", "Export selected wheel meshes together as an alternate wheel slot FBX"),
        ],
        description="Wheel slot export variant for vehicles with different front/rear/alternate wheel geometry")
    bpy.types.Scene.rpf_export_dst_glass = bpy.props.BoolProperty(
        name="DST glass FBXs", default=True,
        description="Export separate destructible glass slot FBXs; visual glass stays out of the master")
    bpy.types.Scene.rpf_export_light_slots = bpy.props.BoolProperty(
        name="Light cover FBXs", default=False,
        description="Export lights_front and lights_rear as separate slot FBXs")
    bpy.types.Scene.rpf_vhacd_exe = bpy.props.StringProperty(
        name="V-HACD exe", default="", subtype='FILE_PATH',
        description="Optional path to an external V-HACD executable (TestVHACD v4). "
                    "Used only when the CoACD python module is not installed")
    bpy.types.Scene.rpf_ucx_backend = bpy.props.EnumProperty(
        name="UCX backend",
        default='AUTO',
        items=[('AUTO', "Auto", "CoACD, vhacdx, external V-HACD, then capped convex fallback"),
               ('COACD', "CoACD", "Use Blender Python CoACD only"),
               ('VHACDX', "VHACD Python", "Use Enfusion Tools-style vhacdx Python backend only"),
               ('EXE', "External", "Use external V-HACD executable only"),
               ('FALLBACK', "Fallback", "Skip decomposition and use capped convex fallback")])
    bpy.types.Scene.rpf_ucx_max_hulls = bpy.props.IntProperty(
        name="Max UCX hulls", default=24, min=1, max=96,
        description="Maximum convex hulls generated per grouped vehicle part")
    bpy.types.Scene.rpf_ucx_max_faces = bpy.props.IntProperty(
        name="UCX face cap", default=200, min=12, max=200,
        description="Maximum faces per generated UCX hull")
    bpy.types.Scene.rpf_ucx_decimate = bpy.props.IntProperty(
        name="Input triangle target", default=6000, min=0, max=100000,
        description="Reduce input mesh to roughly this many triangles before decomposition; 0 uses full resolution")
    bpy.types.Scene.rpf_ucx_concavity = bpy.props.FloatProperty(
        name="CoACD concavity", default=0.035, min=0.005, max=1.0, precision=3,
        description="Lower values create more hulls and follow curves/hard edges more closely")
    bpy.types.Scene.rpf_ucx_threads = bpy.props.IntProperty(
        name="UCX worker threads", default=1, min=1, max=8,
        description="Parallel decomposition jobs for multiple selected meshes. Blender object creation stays single-threaded")
    bpy.types.Scene.rpf_ucx_replace_existing = bpy.props.BoolProperty(
        name="Replace existing generated UCX",
        default=False,
        description="When enabled, selected UCX/V-HACD builds remove prior generated hulls first. Leave off to build panel-by-panel")
    bpy.types.Scene.rpf_selected_faces_use_decomp = bpy.props.BoolProperty(
        name="Decompose selected faces", default=True,
        description="Use the selected VHACD/CoACD backend for Edit Faces -> UCX instead of a single convex hull")
    bpy.types.Scene.rpf_selected_faces_split_loose = bpy.props.BoolProperty(
        name="Split selected face islands", default=True,
        description="Build each disconnected selected face island separately so hulls follow hard body breaks")
    bpy.types.Scene.rpf_vhacd_resolution = bpy.props.IntProperty(
        name="Voxel resolution", default=100000, min=1000, max=10000000,
        description="VHACD voxel resolution; higher follows curved panels more closely and takes longer")
    bpy.types.Scene.rpf_vhacd_volume_error = bpy.props.FloatProperty(
        name="Volume error percent", default=1.0, min=0.001, max=10.0, precision=3,
        description="VHACD allowed volume error percentage; lower is tighter and slower")
    bpy.types.Scene.rpf_vhacd_recursion_depth = bpy.props.IntProperty(
        name="Recursion depth", default=10, min=1, max=32,
        description="VHACD recursive split depth")
    bpy.types.Scene.rpf_vhacd_shrinkwrap = bpy.props.BoolProperty(
        name="Shrinkwrap", default=True,
        description="Shrink VHACD hulls back toward the source surface")
    bpy.types.Scene.rpf_vhacd_fill_mode = bpy.props.EnumProperty(
        name="Fill mode",
        default='flood',
        items=[('flood', "Flood", "Flood-fill interior voxels"),
               ('surface', "Surface", "Surface fill"),
               ('raycast', "Raycast", "Raycast fill")],
        description="VHACD interior fill mode")
    bpy.types.Scene.rpf_vhacd_max_vertices = bpy.props.IntProperty(
        name="Max hull vertices", default=64, min=9, max=256,
        description="Maximum vertices per VHACD output hull before our final face cap")
    bpy.types.Scene.rpf_vhacd_min_edge_length = bpy.props.IntProperty(
        name="Min voxel edge", default=2, min=1, max=32,
        description="Smallest voxel edge length allowed before recursion stops")
    bpy.types.Scene.rpf_vhacd_split_hulls = bpy.props.BoolProperty(
        name="Best split plane", default=False,
        description="Ask VHACD to search for a better split plane instead of midpoint splits")
    bpy.types.Scene.rpf_vhacd_pre_scale = bpy.props.FloatProperty(
        name="Pre-scale", default=1.0, min=0.001, max=1.0, precision=3,
        description="Temporarily shrink source verts before VHACD; useful for reducing outward air gaps")
    bpy.types.Scene.rpf_build_use_vhacd = bpy.props.BoolProperty(
        name="Use V-HACD/CoACD in 1-click", default=False,
        description="When disabled, 1-click uses the quick perceptive UCX builder instead of decomposition")
    bpy.types.Scene.rpf_build_do_lod = bpy.props.BoolProperty(
        name="Bake LOD in 1-click", default=False,
        description="Keep off while iterating collision; bake LOD only after collision review")
    bpy.types.Scene.rpf_auto_analyze_collision = bpy.props.BoolProperty(
        name="Analyze before collision", default=True,
        description="Run semantic vehicle analysis before one-click collision so grouped UCX follows exterior, cab, rear area and door boundaries")
    bpy.types.Scene.rpf_build_categories = bpy.props.StringProperty(
        name="Grouped collision categories",
        default="exterior,cab,rear_area,hood,undercarriage,door_FL,door_FR,door_RL,door_RR,door_trunk",
        description="Comma-separated part/category names decomposed by 1-click V-HACD/CoACD")
    bpy.types.Scene.rpf_collider_setup_layer = bpy.props.EnumProperty(
        name="Layer preset",
        default='FireGeo',
        items=_collider_layer_items,
        description="Enfusion collision layer preset to write to selected colliders")
    bpy.types.Scene.rpf_collider_setup_gamemat = bpy.props.EnumProperty(
        name="Game material",
        default='NO_CHANGE',
        items=_collider_gamemat_items,
        description="Stock Enfusion gamemat assigned to selected colliders or selected UTM faces")
    bpy.types.Scene.rpf_collider_setup_sort = bpy.props.BoolProperty(
        name="Sort into collections",
        default=True,
        description="Move selected colliders into Colliders/<LayerPreset> like Enfusion Blender Tools")
    bpy.types.Scene.rpf_collider_setup_armored = bpy.props.BoolProperty(
        name="Armored body/glass policy",
        default=False,
        description="When using Auto vehicle policy, use armored glass/body choices where applicable")
    bpy.types.Scene.rpf_direct_copy_ratio = bpy.props.FloatProperty(
        name="Direct copy ratio", default=1.0, min=0.01, max=1.0, precision=3,
        description="Decimation ratio for selected render meshes copied directly to FireGeo/detail collision")
    bpy.types.Scene.rpf_direct_copy_merge = bpy.props.BoolProperty(
        name="Merge direct copies", default=False,
        description="Join selected direct collision copies into a single collider object")
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
