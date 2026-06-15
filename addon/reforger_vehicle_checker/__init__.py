"""Reforger Vehicle Checker Blender addon.

The existing rpf.* workflow remains registered through legacy_part_fixer.
RVC adds deterministic checks, checkpointed safe repairs, canonical SampleCar
rig preparation, export blocking, and the localhost setup wizard.
"""

bl_info = {
    "name": "Reforger Vehicle Checker",
    "author": "ARGH Vehicle Tools contributors",
    "version": (0, 11, 0),
    "blender": (4, 0, 0),
    "location": "View3D > Sidebar > RVC",
    "description": "Prepare, validate, repair, and export Enfusion vehicles",
    "category": "Object",
}

import importlib
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import time

import bpy
from mathutils import Vector

from . import legacy_part_fixer, texture_packer


CANONICAL_SAMPLE_FBX = str(
    Path.home()
    / "Documents"
    / "My Games"
    / "ArmaReforgerWorkbench"
    / "addons"
    / "SampleMod_NewCar"
    / "Assets"
    / "Vehicles"
    / "Wheeled"
    / "SampleCar_01"
    / "SampleCar_01.fbx"
)
EXPECTED_BONES = {
    "v_root", "v_body", "v_axle_01", "v_axle_02",
    "v_wheel_l01", "v_wheel_r01", "v_wheel_l02", "v_wheel_r02",
    "v_suspension_l01", "v_suspension_r01", "v_suspension_l02", "v_suspension_r02",
    "v_rotator_l01", "v_rotator_r01", "v_door_l01", "v_door_r01",
    "v_door_l02", "v_door_r02", "v_trunk", "v_steering_wheel",
    "v_pedal_brake", "v_pedal_throttle", "v_pedal_clutch", "v_handbrake",
    "v_gearshift", "v_dashboard_rpm", "v_dashboard_speed",
    "v_dashboard_fuel", "v_dashboard_coolant_temp", "hood_jiggle",
}
CANONICAL_PARENT = {
    "v_root": None, "v_body": "v_root", "hood_jiggle": "v_root",
    "v_axle_01": "v_body", "v_axle_02": "v_body", "v_trunk": "v_body",
    "v_steering_wheel": "v_body", "v_door_l01": "v_body", "v_door_r01": "v_body",
    "v_door_l02": "v_body", "v_door_r02": "v_body", "v_gearshift": "v_body",
    "v_handbrake": "v_body", "v_pedal_throttle": "v_body",
    "v_pedal_brake": "v_body", "v_pedal_clutch": "v_body",
    "v_dashboard_rpm": "v_body", "v_dashboard_speed": "v_body",
    "v_dashboard_fuel": "v_body", "v_dashboard_coolant_temp": "v_body",
    "v_suspension_l01": "v_axle_01", "v_suspension_r01": "v_axle_01",
    "v_rotator_l01": "v_suspension_l01", "v_rotator_r01": "v_suspension_r01",
    "v_wheel_l01": "v_rotator_l01", "v_wheel_r01": "v_rotator_r01",
    "v_suspension_l02": "v_axle_02", "v_suspension_r02": "v_axle_02",
    "v_wheel_l02": "v_suspension_l02", "v_wheel_r02": "v_suspension_r02",
}
PART_BONES = {
    "door_FL": "v_door_l01", "door_FR": "v_door_r01",
    "door_RL": "v_door_l02", "door_RR": "v_door_r02",
    "door_trunk": "v_trunk", "Steering_Wheel": "v_steering_wheel",
    "Pedal_Brake": "v_pedal_brake", "Pedal_Accelerator": "v_pedal_throttle",
    "wheel_FL": "v_wheel_l01", "wheel_FR": "v_wheel_r01",
    "wheel_RL": "v_wheel_l02", "wheel_RR": "v_wheel_r02",
}
WINDOW_BONES = {
    "window_FL": "v_door_l01", "window_FR": "v_door_r01",
    "window_RL": "v_door_l02", "window_RR": "v_door_r02",
    "door_FL_window": "v_door_l01", "door_FR_window": "v_door_r01",
    "door_RL_window": "v_door_l02", "door_RR_window": "v_door_r02",
}
REQUIRED_CREW_PIVOTS = (
    "driver_idle", "driver_getIn", "codriver_idle", "codriver_getIn",
    "passengerl_idle", "passengerl_getin",
    "passengerr_idle", "passengerr_getin", "passengerc_idle",
)


def _armature():
    arms = [o for o in bpy.context.scene.objects if o.type == "ARMATURE"]
    return next((o for o in arms if o.name == "Armature"), arms[0] if arms else None)


def _world_bbox(obj):
    points = [obj.matrix_world @ Vector(corner) for corner in obj.bound_box]
    return (
        tuple(min(p[i] for p in points) for i in range(3)),
        tuple(max(p[i] for p in points) for i in range(3)),
    )


def _bbox_delta(before, after):
    return max(abs(before[j][i] - after[j][i]) for j in range(2) for i in range(3))


def _checkpoint(tag):
    if not bpy.data.filepath:
        return ""
    stem, ext = os.path.splitext(bpy.data.filepath)
    path = f"{stem}_{tag}_{time.strftime('%H%M%S')}{ext}"
    bpy.ops.wm.save_as_mainfile(filepath=path, copy=True)
    return path


def _part_bone(obj):
    if obj.name in PART_BONES:
        return PART_BONES[obj.name]
    if obj.name in WINDOW_BONES:
        return WINDOW_BONES[obj.name]
    for name, bone in {**PART_BONES, **WINDOW_BONES}.items():
        if obj.name.startswith(name + "."):
            return bone
    return None


def _armature_modifiers(obj):
    return [m for m in obj.modifiers if m.type == "ARMATURE"]


def _binding_issues(obj, arm, bone):
    issues = []
    if obj.parent != arm or obj.parent_type != "OBJECT" or obj.parent_bone:
        issues.append("must be object-parented to vehicle armature")
    mods = _armature_modifiers(obj)
    if len(mods) != 1 or mods[0].object != arm:
        issues.append("must have exactly one Armature modifier targeting vehicle armature")
    groups = [g for g in obj.vertex_groups if g.name != bone and any(
        g.index == member.group and member.weight > 1e-5
        for vertex in obj.data.vertices for member in vertex.groups
    )]
    target = obj.vertex_groups.get(bone)
    if target is None:
        issues.append(f"missing exact group {bone}")
    else:
        for vertex in obj.data.vertices:
            weights = [member.weight for member in vertex.groups if member.group == target.index]
            if len(weights) != 1 or not math.isclose(weights[0], 1.0, abs_tol=1e-5):
                issues.append(f"vertices are not rigidly weighted 1.0 to {bone}")
                break
    if groups:
        issues.append("has non-target weighted groups: " + ", ".join(g.name for g in groups))
    if any(abs(v) > 1e-5 for v in (*obj.location, *obj.rotation_euler)):
        issues.append("local location/rotation is not identity")
    if any(not math.isclose(v, 1.0, abs_tol=1e-5) for v in obj.scale):
        issues.append("local scale is not identity")
    return issues


def build_scene_report():
    arm = _armature()
    issues = []
    facts = {
        "blend": bpy.data.filepath,
        "mesh_count": sum(o.type == "MESH" for o in bpy.context.scene.objects),
        "triangle_count": sum(
            sum(len(poly.vertices) - 2 for poly in o.data.polygons)
            for o in bpy.context.scene.objects
            if o.type == "MESH" and not o.name.startswith(("UTM_", "UCL_", "UCX_"))
        ),
        "armature": arm.name if arm else "",
        "bone_count": len(arm.data.bones) if arm else 0,
        "visual_wheels": [name for name in PART_BONES if name.startswith("wheel_") and bpy.data.objects.get(name)],
    }
    if not arm:
        issues.append(("rig.armature", "error", "Vehicle armature is missing", True))
    else:
        missing = sorted(EXPECTED_BONES - set(arm.data.bones.keys()))
        if missing:
            issues.append(("rig.canonical_bones", "error", "Missing canonical bones: " + ", ".join(missing), True))
        if len(arm.data.bones) != 30:
            issues.append(("rig.canonical_count", "error", f"Expected SampleCar 30 bones; found {len(arm.data.bones)}", True))
        for obj in bpy.context.scene.objects:
            bone = _part_bone(obj) if obj.type == "MESH" else None
            if bone:
                for detail in _binding_issues(obj, arm, bone):
                    issues.append((f"binding.{obj.name}", "error", detail, True))
    if facts["triangle_count"] > bpy.context.scene.rvc_triangle_budget:
        issues.append(("geometry.triangle_budget", "warning", f"{facts['triangle_count']} triangles exceeds target", False))
    if not facts["visual_wheels"]:
        issues.append(("geometry.visual_wheels", "warning", "No visual wheel meshes; wheel FBX export will be skipped", False))
    for obj in bpy.context.scene.objects:
        if obj.type == "MESH" and obj.name.lower().startswith("utm_glass"):
            break
    else:
        issues.append(("collision.utm_glass", "warning", "No UTM_Glass collider object detected", False))
    for name in REQUIRED_CREW_PIVOTS:
        marker = bpy.data.objects.get(name)
        if marker is None:
            issues.append((
                f"crew_pivot.{name}", "error",
                f"Required crew pivot {name} is missing", False,
            ))
        elif marker.matrix_world.translation.length < 0.05:
            issues.append((
                f"crew_pivot.{name}", "error",
                f"Required crew pivot {name} is collapsed at vehicle origin", False,
            ))
    return {"facts": facts, "issues": [
        {"rule_id": rule, "severity": severity, "evidence": evidence, "safe_fix_available": safe}
        for rule, severity, evidence, safe in issues
    ]}


def _write_report(report):
    path = Path(bpy.path.abspath(bpy.context.scene.rvc_report_path))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    bpy.context.scene["rvc_last_report"] = json.dumps(report)
    return path


def _rigid_bind_preserve(obj, arm, bone):
    before = _world_bbox(obj)
    world = obj.matrix_world.copy()
    mesh_to_arm = arm.matrix_world.inverted() @ world
    obj.data.transform(mesh_to_arm)
    obj.matrix_world = arm.matrix_world
    obj.parent = arm
    obj.parent_type = "OBJECT"
    obj.parent_bone = ""
    obj.matrix_parent_inverse.identity()
    obj.location = (0, 0, 0)
    obj.rotation_euler = (0, 0, 0)
    obj.scale = (1, 1, 1)
    obj.vertex_groups.clear()
    group = obj.vertex_groups.new(name=bone)
    group.add(range(len(obj.data.vertices)), 1.0, "REPLACE")
    for mod in list(_armature_modifiers(obj)):
        obj.modifiers.remove(mod)
    mod = obj.modifiers.new("Armature", "ARMATURE")
    mod.object = arm
    mod.use_vertex_groups = True
    mod.use_bone_envelopes = False
    after = _world_bbox(obj)
    if _bbox_delta(before, after) > 0.0005:
        raise RuntimeError(f"{obj.name} moved during safe binding repair")


class RVC_OT_check_vehicle(bpy.types.Operator):
    bl_idname = "rvc.check_vehicle"
    bl_label = "Check Vehicle"

    def execute(self, context):
        report = build_scene_report()
        path = _write_report(report)
        errors = sum(i["severity"] == "error" for i in report["issues"])
        self.report({"ERROR" if errors else "INFO"}, f"{errors} blocking errors; report: {path}")
        return {"FINISHED"}


class RVC_OT_apply_safe_fixes(bpy.types.Operator):
    bl_idname = "rvc.apply_safe_fixes"
    bl_label = "Apply Safe Binding Fixes"
    bl_description = "Checkpoint, repair deterministic movable-part binding, and verify visible bounds do not move"

    def execute(self, context):
        arm = _armature()
        if not arm:
            self.report({"ERROR"}, "No armature")
            return {"CANCELLED"}
        checkpoint = _checkpoint("pre_rvc_safe_fixes")
        fixed = []
        try:
            for obj in list(context.scene.objects):
                bone = _part_bone(obj) if obj.type == "MESH" else None
                if bone and bone in arm.data.bones and _binding_issues(obj, arm, bone):
                    _rigid_bind_preserve(obj, arm, bone)
                    fixed.append(obj.name)
        except Exception as exc:
            self.report({"ERROR"}, f"Repair stopped: {exc}; restore checkpoint {checkpoint}")
            return {"CANCELLED"}
        self.report({"INFO"}, f"Repaired {len(fixed)} parts; checkpoint {checkpoint}")
        return {"FINISHED"}


class RVC_OT_prepare_rig(bpy.types.Operator):
    bl_idname = "rvc.prepare_rig"
    bl_label = "Prepare Canonical SampleCar Rig"
    bl_description = "Extend the positioned vehicle armature to SampleCar's complete canonical 30-bone contract"

    def execute(self, context):
        arm = _armature()
        if not arm:
            self.report({"ERROR"}, "No positioned vehicle armature; create/import one first")
            return {"CANCELLED"}
        checkpoint = _checkpoint("pre_rvc_prepare_rig")
        bpy.context.view_layer.objects.active = arm
        arm.select_set(True)
        bpy.ops.object.mode_set(mode="EDIT")
        added = []
        for name in sorted(EXPECTED_BONES):
            if name in arm.data.edit_bones:
                continue
            parent_name = CANONICAL_PARENT[name]
            parent = arm.data.edit_bones.get(parent_name) if parent_name else None
            marker = bpy.data.objects.get(name)
            if marker:
                head = arm.matrix_world.inverted() @ marker.matrix_world.translation
            elif parent:
                head = parent.head.copy()
            else:
                head = Vector((0, 0, 0))
            direction = parent.vector.normalized() if parent and parent.length > 1e-5 else Vector((0, 1, 0))
            length = parent.length if parent and parent.length > 1e-5 else 0.5
            bone = arm.data.edit_bones.new(name)
            bone.head = head
            bone.tail = head + direction * length
            bone.parent = parent
            added.append(name)
        bpy.ops.object.mode_set(mode="OBJECT")
        if len(arm.data.bones) != 30:
            self.report({"ERROR"}, f"Canonical extension produced {len(arm.data.bones)} bones, expected 30; restore {checkpoint}")
            return {"CANCELLED"}
        self.report({"INFO"}, f"Added {len(added)} missing canonical bones without reskinning; checkpoint {checkpoint}")
        return {"FINISHED"}


class RVC_OT_export_vehicle(bpy.types.Operator):
    bl_idname = "rvc.export_vehicle"
    bl_label = "Checked Export"
    bl_description = "Block on checker errors, then call the existing slot-architecture exporter"

    def execute(self, context):
        report = build_scene_report()
        _write_report(report)
        errors = [issue for issue in report["issues"] if issue["severity"] == "error"]
        if errors:
            self.report({"ERROR"}, f"Export blocked by {len(errors)} checker errors; run Check Vehicle")
            return {"CANCELLED"}
        return bpy.ops.rpf.export_enfusion()


class RVC_OT_generate_glass_colliders(bpy.types.Operator):
    bl_idname = "rvc.generate_glass_colliders"
    bl_label = "Generate UTM_Glass Colliders"
    bl_description = "Checkpoint and extract detected Glass-material faces into non-visual UTM_Glass meshes"

    def execute(self, context):
        sources = {
            "windows_body": "UTM_Glass_Body",
            "door_FL": "UTM_Glass_FL", "door_FR": "UTM_Glass_FR",
            "door_RL": "UTM_Glass_RL", "door_RR": "UTM_Glass_RR",
        }
        checkpoint = _checkpoint("pre_rvc_glass_colliders")
        made = []
        for source_name, collider_name in sources.items():
            source = bpy.data.objects.get(source_name)
            if not source or source.type != "MESH" or bpy.data.objects.get(collider_name):
                continue
            glass_indices = {
                index for index, material in enumerate(source.data.materials)
                if material and "glass" in material.name.lower()
            }
            keep = [poly for poly in source.data.polygons if poly.material_index in glass_indices]
            if not keep:
                continue
            vertices = sorted({index for poly in keep for index in poly.vertices})
            remap = {old: new for new, old in enumerate(vertices)}
            mesh = bpy.data.meshes.new(collider_name)
            mesh.from_pydata(
                [source.data.vertices[index].co.copy() for index in vertices],
                [],
                [[remap[index] for index in poly.vertices] for poly in keep],
            )
            mesh.update()
            collider = bpy.data.objects.new(collider_name, mesh)
            context.scene.collection.objects.link(collider)
            collider.matrix_world = source.matrix_world.copy()
            collider.display_type = "WIRE"
            collider.hide_render = True
            bone = _part_bone(source) or "v_body"
            group = collider.vertex_groups.new(name=bone)
            group.add(range(len(mesh.vertices)), 1.0, "REPLACE")
            arm = _armature()
            if arm:
                collider.parent = arm
                collider.parent_type = "OBJECT"
                collider.matrix_parent_inverse = arm.matrix_world.inverted()
                mod = collider.modifiers.new("Armature", "ARMATURE")
                mod.object = arm
                mod.use_vertex_groups = True
                mod.use_bone_envelopes = False
            made.append(collider_name)
        self.report({"INFO"}, f"Generated {len(made)} glass colliders; checkpoint {checkpoint}")
        return {"FINISHED"}


class RVC_OT_open_setup_wizard(bpy.types.Operator):
    bl_idname = "rvc.open_setup_wizard"
    bl_label = "Open Setup Wizard"

    def execute(self, context):
        root = Path(__file__).resolve().parent
        launcher = ["py", "-3", "-m", "rvc_web.app"] if os.name == "nt" else [sys.executable, "-m", "rvc_web.app"]
        subprocess.Popen(launcher, cwd=root)
        self.report({"INFO"}, "Setup wizard opening at http://127.0.0.1:8765")
        return {"FINISHED"}


class RVC_OT_pack_bcr_nmo_textures(bpy.types.Operator):
    bl_idname = "rvc.pack_bcr_nmo_textures"
    bl_label = "Export Selected BCR / NMO"
    bl_description = "Pack selected vehicle materials into Enfusion BCR and DirectX -Y NMO source textures"
    bl_options = {"REGISTER"}

    @classmethod
    def poll(cls, context):
        return any(obj.type == "MESH" for obj in context.selected_objects)

    def execute(self, context):
        export_dir = bpy.path.abspath(context.scene.rvc_texture_export_dir)
        if context.scene.rvc_texture_use_vehicle_data and getattr(context.scene, "rpf_export_root", ""):
            export_dir = os.path.join(bpy.path.abspath(context.scene.rpf_export_root), "Data")
        materials = texture_packer.material_slots_from_selection(context)
        if not materials:
            self.report({"ERROR"}, "Selected meshes have no materials")
            return {"CANCELLED"}
        written = []
        fallback = int(context.scene.rvc_texture_fallback_size)
        for material in materials:
            if context.scene.rvc_texture_pack_bcr:
                written.append(texture_packer.pack_bcr(
                    material, export_dir, context.scene.rvc_texture_file_format, fallback
                ))
            if context.scene.rvc_texture_pack_nmo:
                written.append(texture_packer.pack_nmo(
                    material, export_dir, context.scene.rvc_texture_file_format, fallback,
                    context.scene.rvc_texture_directx_normal,
                ))
        for path in written:
            print("RVC_TEXTURE_EXPORTED", path)
        self.report({"INFO"}, f"Exported {len(written)} BCR/NMO texture sources to {export_dir}")
        return {"FINISHED"}


class RVC_PT_panel(bpy.types.Panel):
    bl_label = "Reforger Vehicle Checker"
    bl_idname = "RVC_PT_panel"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "RVC"

    def draw(self, context):
        layout = self.layout
        layout.operator("rvc.check_vehicle", icon="CHECKMARK")
        layout.operator("rvc.apply_safe_fixes", icon="FILE_TICK")
        layout.operator("rvc.prepare_rig", icon="ARMATURE_DATA")
        layout.operator("rvc.generate_glass_colliders", icon="MOD_PHYSICS")
        layout.operator("rvc.export_vehicle", icon="EXPORT")
        layout.operator("rvc.open_setup_wizard", icon="URL")
        box = layout.box()
        box.label(text="Enfusion BCR / NMO", icon="TEXTURE")
        box.prop(context.scene, "rvc_texture_use_vehicle_data")
        if not context.scene.rvc_texture_use_vehicle_data:
            box.prop(context.scene, "rvc_texture_export_dir")
        row = box.row(align=True)
        row.prop(context.scene, "rvc_texture_pack_bcr", toggle=True)
        row.prop(context.scene, "rvc_texture_pack_nmo", toggle=True)
        box.prop(context.scene, "rvc_texture_file_format")
        box.prop(context.scene, "rvc_texture_fallback_size")
        box.prop(context.scene, "rvc_texture_directx_normal")
        box.operator("rvc.pack_bcr_nmo_textures", icon="EXPORT")
        layout.prop(context.scene, "rvc_samplecar_fbx")
        layout.prop(context.scene, "rvc_triangle_budget")
        layout.prop(context.scene, "rvc_report_path")
        layout.separator()
        layout.label(text="Legacy rpf.* tools remain available")


CLASSES = (
    RVC_OT_check_vehicle,
    RVC_OT_apply_safe_fixes,
    RVC_OT_prepare_rig,
    RVC_OT_generate_glass_colliders,
    RVC_OT_export_vehicle,
    RVC_OT_open_setup_wizard,
    RVC_OT_pack_bcr_nmo_textures,
    RVC_PT_panel,
)


def register():
    importlib.reload(legacy_part_fixer)
    importlib.reload(texture_packer)
    try:
        legacy_part_fixer.register()
    except Exception as exc:
        print("RVC: legacy rpf registration skipped:", exc)
    for cls in CLASSES:
        bpy.utils.register_class(cls)
    bpy.types.Scene.rvc_samplecar_fbx = bpy.props.StringProperty(
        name="Canonical SampleCar FBX", subtype="FILE_PATH", default=CANONICAL_SAMPLE_FBX
    )
    bpy.types.Scene.rvc_triangle_budget = bpy.props.IntProperty(
        name="Triangle target", default=100000, min=1000
    )
    bpy.types.Scene.rvc_report_path = bpy.props.StringProperty(
        name="Report", subtype="FILE_PATH", default="//vehicle_check_report.json"
    )
    bpy.types.Scene.rvc_texture_use_vehicle_data = bpy.props.BoolProperty(
        name="Export to Vehicle Data Folder",
        description="Write textures to <vehicle export root>/Data",
        default=True,
    )
    bpy.types.Scene.rvc_texture_export_dir = bpy.props.StringProperty(
        name="Texture Export Directory", subtype="DIR_PATH", default="//Data"
    )
    bpy.types.Scene.rvc_texture_file_format = bpy.props.EnumProperty(
        name="Source Format",
        items=(("TIFF", "TIFF", "Preferred Workbench source"), ("PNG", "PNG", "Portable fallback")),
        default="TIFF",
    )
    bpy.types.Scene.rvc_texture_fallback_size = bpy.props.EnumProperty(
        name="Fallback Size",
        items=(("512", "512", ""), ("1024", "1024", ""), ("2048", "2048", ""), ("4096", "4096", "")),
        default="2048",
    )
    bpy.types.Scene.rvc_texture_pack_bcr = bpy.props.BoolProperty(name="BCR", default=True)
    bpy.types.Scene.rvc_texture_pack_nmo = bpy.props.BoolProperty(name="NMO", default=True)
    bpy.types.Scene.rvc_texture_directx_normal = bpy.props.BoolProperty(
        name="DirectX Normal -Y",
        description="Invert the normal green channel for Enfusion",
        default=True,
    )


def unregister():
    for name in (
        "rvc_samplecar_fbx", "rvc_triangle_budget", "rvc_report_path",
        "rvc_texture_use_vehicle_data", "rvc_texture_export_dir",
        "rvc_texture_file_format", "rvc_texture_fallback_size",
        "rvc_texture_pack_bcr", "rvc_texture_pack_nmo", "rvc_texture_directx_normal",
    ):
        if hasattr(bpy.types.Scene, name):
            delattr(bpy.types.Scene, name)
    for cls in reversed(CLASSES):
        try:
            bpy.utils.unregister_class(cls)
        except RuntimeError:
            pass
    try:
        legacy_part_fixer.unregister()
    except Exception:
        pass
