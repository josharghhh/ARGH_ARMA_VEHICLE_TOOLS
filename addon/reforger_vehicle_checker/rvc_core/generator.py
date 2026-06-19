from __future__ import annotations

from dataclasses import asdict
import json
from pathlib import Path
import re
import shutil

from .models import VehicleProject
from .paths import local_path


SAMPLE_BASE = "{4E8595C9A8254222}Prefabs/Vehicles/Wheeled/SampleCar_01/SampleCar_01_Base.et"
SAMPLE_GRAPH = "{08DD60EF4FC9988A}Assets/Vehicles/Wheeled/SampleCar_01/workspaces/SampleCar_01.agr"
SAMPLE_AST = "{1A2F06EF780C4C79}Assets/Vehicles/Wheeled/SampleCar_01/workspaces/SampleCar_01.ast"
SAMPLE_MESH_COMPONENT = "{51DAA09FEFBFC0E7}"
SAMPLE_RIGID_BODY_COMPONENT = "{51DAA09FECF52BBF}"
SAMPLE_SIM_COMPONENT = "{731B26FCA2F19855}"
SAMPLE_WHEELED_SIMULATION = "{4D8B26DEA5F25978}"
SAMPLE_FRONT_AXLE = "{4D8B26DF957A8E1C}"
SAMPLE_FRONT_WHEEL = "{4D8B26DFFE211745}"
SAMPLE_REAR_AXLE = "{4D8B26DF8CF2F3D8}"
SAMPLE_REAR_WHEEL = "{4D8B26DF30A4E4D7}"
SAMPLE_SLOT_COMPONENT = "{55BCE45E438E4CFF}"
SAMPLE_ANIMATION_COMPONENT = "{50B803EAA459B0AF}"
SAMPLE_PLAYER_INJECTION = "{50B803EA8AD25BC8}"
SAMPLE_GLASS_MESH_COMPONENT = "{54ACA4E7F43678F8}"
SAMPLE_LIGHT_MESH_COMPONENT = "{54DEF48745980A1F}"
PREFAB_OUTPUT_DIR = "Prefabs/Vehicles/Wheeled/RVC_VEHICLES"


def _clean(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9_]+", "_", name).strip("_") or "Vehicle"


def _write(path: Path, text: str, backup: bool = False) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    if backup and path.exists() and path.read_text(encoding="utf-8", errors="ignore") != text.rstrip() + "\n":
        shutil.copy2(path, path.with_suffix(path.suffix + ".rvc_backup"))
    path.write_text(text.rstrip() + "\n", encoding="utf-8")
    return str(path)


def _resource_path(resource: str) -> str:
    return resource.split("}", 1)[-1].replace("\\", "/").strip("/")


def _resource_directory(project: VehicleProject) -> str:
    if project.imported_xob_resource:
        return str(Path(_resource_path(project.imported_xob_resource)).parent).replace("\\", "/")
    addon = local_path(project.addon_root)
    output = local_path(project.output_directory)
    try:
        return output.relative_to(addon).as_posix()
    except ValueError:
        return f"Assets/Vehicles/Wheeled/{_clean(project.asset_name)}"


def _registered_resource(project: VehicleProject, relative: str) -> str:
    meta = local_path(project.addon_root) / f"{relative}.meta"
    if meta.is_file():
        match = re.search(r'\bName\s+"(\{[0-9A-Fa-f]{16}\}[^"]+)"', meta.read_text(
            encoding="utf-8", errors="ignore"
        ))
        if match:
            return match.group(1)
    return f"{{WORKBENCH_GUID_REQUIRED}}{relative}"


def _registered_or_path(project: VehicleProject, relative: str) -> str:
    resource = _registered_resource(project, relative)
    return relative if resource.startswith("{WORKBENCH_GUID_REQUIRED}") else resource


def _workspace_resource(project: VehicleProject, suffix: str) -> str:
    resource_dir = _resource_directory(project)
    folder_stem = local_path(project.output_directory).name
    name = _clean(project.asset_name)
    for stem in dict.fromkeys((folder_stem, name)):
        relative = f"{resource_dir}/workspaces/{stem}_{suffix}"
        resource = _registered_resource(project, relative)
        if not resource.startswith("{WORKBENCH_GUID_REQUIRED}"):
            return resource
    return _registered_resource(project, f"{resource_dir}/workspaces/{name}_{suffix}")


def _workspace_or_sample(project: VehicleProject, suffix: str, sample: str) -> str:
    resource = _workspace_resource(project, suffix)
    return sample if resource.startswith("{WORKBENCH_GUID_REQUIRED}") else resource


def _resource_or_placeholder(project: VehicleProject) -> str:
    return project.imported_xob_resource or _registered_resource(
        project, f"{_resource_directory(project)}/{_clean(project.asset_name)}.xob"
    )


def _resolved_xob(project: VehicleProject) -> str | None:
    """Return a valid ``{GUID}path`` xob resource, or ``None`` if not registered yet.

    Lookup order: explicit pasted token -> canonical ``<name>.xob.meta`` ->
    any ``*.xob.meta`` in the addon whose stem matches the asset name. This never
    returns a ``{WORKBENCH_GUID_REQUIRED}`` placeholder -- a placeholder Object
    reference is exactly what leaves the MeshObject empty/broken in Workbench, so
    when nothing resolves we return ``None`` and the caller inherits the working
    SampleCar mesh instead.
    """
    token = project.imported_xob_resource
    if token and not token.startswith("{WORKBENCH_GUID_REQUIRED}"):
        return token
    canonical = _registered_resource(
        project, f"{_resource_directory(project)}/{_clean(project.asset_name)}.xob"
    )
    if not canonical.startswith("{WORKBENCH_GUID_REQUIRED}"):
        return canonical
    addon = local_path(project.addon_root)
    name = _clean(project.asset_name).lower()
    try:
        for meta in addon.rglob("*.xob.meta"):
            stem = meta.name[: -len(".xob.meta")]
            if _clean(stem).lower() == name:
                match = re.search(
                    r'\bName\s+"(\{[0-9A-Fa-f]{16}\}[^"]+)"',
                    meta.read_text(encoding="utf-8", errors="ignore"),
                )
                if match:
                    return match.group(1)
    except OSError:
        pass
    return None


def _base_prefab(project: VehicleProject) -> str:
    template = local_path(project.template_sources.get("prefab", ""))
    xob = _resolved_xob(project)
    if template.is_file():
        text = template.read_text(encoding="utf-8", errors="ignore")
        # Only rewrite the mesh Object when we have a real registered xob; otherwise
        # leave the template's own (valid) Object reference untouched.
        if xob:
            text = re.sub(
                r'(\bObject\s+")\{[0-9A-Fa-f]{16}\}[^"]+(")',
                rf'\1{xob}\2', text, count=1,
            )
        return text
    name = _clean(project.asset_name)
    m = project.measurements
    radius = m.get("wheel_radius", 0.4)
    mass = m.get("mass", 1800)
    com_y = max(radius + 0.35, min(m.get("body_height", 1.8) * 0.42, 1.1))
    wheel = project.external_wheel_prefab
    anim_instance = _workspace_resource(project, "Vehicle.asi")
    anim_graph = _workspace_or_sample(project, "Vehicle.agr", SAMPLE_GRAPH)

    components: list[str] = []
    # MeshObject: override only with a real xob. With no registered xob we omit the
    # override so the component inherits the working SampleCar mesh (a broken
    # {WORKBENCH_GUID_REQUIRED} Object is what produced the empty/invisible vehicle).
    if xob:
        components.append(
            f'  MeshObject "{SAMPLE_MESH_COMPONENT}" {{\n'
            f'   Object "{xob}"\n'
            f'  }}'
        )
    components.append(
        f'  RigidBody "{SAMPLE_RIGID_BODY_COMPONENT}" {{\n'
        f'   Mass {mass:.0f}\n'
        f'   CenterOfMass 0 {com_y:.3f} 0\n'
        f'   LinearSleepingThreashold 0.4\n'
        f'   AngularSleepingThreashold 0.5\n'
        f'  }}'
    )
    components.append(
        f'  VehicleWheeledSimulation "{SAMPLE_SIM_COMPONENT}" {{\n'
        f'   Simulation Wheeled "{SAMPLE_WHEELED_SIMULATION}" {{\n'
        f'    Axles {{\n'
        f'     Axle "{SAMPLE_FRONT_AXLE}" {{ Wheel Wheel "{SAMPLE_FRONT_WHEEL}" {{ Radius {radius:.3f} }} }}\n'
        f'     Axle "{SAMPLE_REAR_AXLE}" {{ Wheel Wheel "{SAMPLE_REAR_WHEEL}" {{ Radius {radius:.3f} }} }}\n'
        f'    }}\n'
        f'    InertiaOverrideEnabled 1\n'
        f'    InertiaOverride {mass * 0.8:.0f} {mass * 0.6:.0f} {mass * 0.5:.0f}\n'
        f'   }}\n'
        f'  }}'
    )
    components.append(
        f'  SlotManagerComponent "{SAMPLE_SLOT_COMPONENT}" {{\n'
        f'   Slots {{\n'
        f'    EntitySlotInfo glass_f {{ Prefab "" }}\n'
        f'    EntitySlotInfo glass_fl {{ Prefab "" }}\n'
        f'    EntitySlotInfo glass_fr {{ Prefab "" }}\n'
        f'    EntitySlotInfo glass_r {{ Prefab "" }}\n'
        f'    EntitySlotInfo glass_rl {{ Prefab "" }}\n'
        f'    EntitySlotInfo glass_rr {{ Prefab "" }}\n'
        f'    EntitySlotInfo ShadowAO {{ Prefab "" }}\n'
        f'    SCR_WheelSlotInfo Wheel_L01 {{ PivotID "v_wheel_l01" MergePhysics 1 Prefab "{wheel}" DisablePhysicsInteraction 1 RegisterDamage 1 m_iWheelIndex 0 }}\n'
        f'    SCR_WheelSlotInfo Wheel_R01 {{ PivotID "v_wheel_r01" Angles 0 180 0 MergePhysics 1 Prefab "{wheel}" DisablePhysicsInteraction 1 RegisterDamage 1 m_iWheelIndex 1 }}\n'
        f'    SCR_WheelSlotInfo Wheel_L02 {{ PivotID "v_wheel_l02" MergePhysics 1 Prefab "{wheel}" DisablePhysicsInteraction 1 RegisterDamage 1 m_iWheelIndex 2 }}\n'
        f'    SCR_WheelSlotInfo Wheel_R02 {{ PivotID "v_wheel_r02" Angles 0 180 0 MergePhysics 1 Prefab "{wheel}" DisablePhysicsInteraction 1 RegisterDamage 1 m_iWheelIndex 3 }}\n'
        f'    RegisteringComponentSlotInfo SupplyStorage_01 {{ Prefab "" }}\n'
        f'   }}\n'
        f'  }}'
    )
    # VehicleAnimationComponent: override only when our generated ASI is registered;
    # otherwise inherit the working SampleCar animation rather than a placeholder.
    if not anim_instance.startswith("{WORKBENCH_GUID_REQUIRED}"):
        injection = _player_injection(project)
        injection = f"\n{injection}" if injection else ""
        components.append(
            f'  VehicleAnimationComponent "{SAMPLE_ANIMATION_COMPONENT}" {{\n'
            f'   AnimGraph "{anim_graph}"\n'
            f'   AnimInstance "{anim_instance}"\n'
            f'   StartNode "VehicleMasterControl"{injection}\n'
            f'  }}'
        )
    body = "\n".join(components)
    return (
        f'Vehicle : "{SAMPLE_BASE}" {{\n'
        f' ID "RVC_{name}_BASE"\n'
        f' components {{\n'
        f'{body}\n'
        f' }}\n'
        f'}}'
    )


def _child_prefab(project: VehicleProject) -> str:
    name = _clean(project.asset_name)
    parent = _registered_resource(
        project, f"{PREFAB_OUTPUT_DIR}/{name}_Base.et"
    )
    return f'''Vehicle : "{parent}" {{
 ID "RVC_{name}_CHILD"
}}'''


def _alias_prefab(project: VehicleProject) -> str:
    name = _clean(project.asset_name)
    parent = _registered_resource(
        project, f"{PREFAB_OUTPUT_DIR}/{name.lower()}.et"
    )
    return f'''Vehicle : "{parent}" {{
 ID "RVC_{name}_LEGACY_ALIAS"
}}'''


def _apr(name: str) -> str:
    return f'''$animExportProfile {{
 $tracks {{
   "Scene_Root"       ""                 "TRA"
   "Armature"         "Scene_Root"       "RA"
   "v_root"           "Armature"         "RA"
   "v_body"           "v_root"           "RA"
   "v_steering_wheel" "v_body"           "RA"
   "v_pedal_throttle" "v_body"           "RA"
 }}
}}'''


def _steering_txa() -> str:
    return '''$animation "" {
 #version 2
 #fps 30
 #numFrames 2
 $node "Scene_Root" { $keys t q { $frame 0 2 { } }
  $node "Armature" { $keys t q { $frame 0 2 { } }
   $node "v_root" { $keys t q { $frame 0 2 { } }
    $node "v_body" { $keys t q { $frame 0 2 { } }
     $node "v_steering_wheel" {
      $keys q {
       $frame 0 { #q 0 0 -0.7071068 0.7071068 }
       $frame 2 { #q 0 0 0.7071068 0.7071068 }
      }
     }
    }
   }
  }
 }
}'''


def _throttle_txa() -> str:
    return '''$animation "" {
 #version 2
 #fps 30
 #numFrames 2
 $node "Scene_Root" { $keys t q { $frame 0 2 { } }
  $node "Armature" { $keys t q { $frame 0 2 { } }
   $node "v_root" { $keys t q { $frame 0 2 { } }
    $node "v_body" { $keys t q { $frame 0 2 { } }
     $node "v_pedal_throttle" {
      $keys q {
       $frame 0 { #q 0 0 0 1 }
       $frame 2 { #q 0.0871557 0 0 0.9961947 }
      }
     }
    }
   }
  }
 }
}'''


def _player_injection(project: VehicleProject) -> str:
    player = _workspace_resource(project, "Player.asi")
    if player.startswith("{WORKBENCH_GUID_REQUIRED}"):
        return ""
    return f'''   AnimInjection AnimationAttachmentInfo "{SAMPLE_PLAYER_INJECTION}" {{
    AnimGraph "{SAMPLE_GRAPH}"
    AnimInstance "{player}"
   }}'''


def _asi(project: VehicleProject, name: str, resource_dir: str) -> str:
    steering = _registered_resource(project, f"{resource_dir}/Anims/Steering_{name}.anm")
    throttle = _registered_resource(project, f"{resource_dir}/Anims/Throttle_{name}.anm")
    template = _workspace_or_sample(project, "Vehicle.ast", SAMPLE_AST)
    return f'''AnimSetInstanceSource {{
 Template "{template}"
 Lines {{
  AnimSetInstanceSource_Line "VehicleActions.Veh/Play.SteeringExtreme" {{
   Resource "{steering}"
  }}
  AnimSetInstanceSource_Line "VehicleActions.Veh/Play.SteeringMain" {{
   Resource "{steering}"
  }}
  AnimSetInstanceSource_Line "VehicleActions.Veh/Play.Throttle" {{
   Resource "{throttle}"
  }}
 }}
}}'''


def _sample_workspace_candidates(project: VehicleProject) -> list[Path]:
    explicit = local_path(project.template_sources.get("animation", ""))
    candidates = [explicit] if str(explicit) not in ("", ".") else []
    addon = local_path(project.addon_root)
    candidates.extend([
        addon.parent / "SampleMod_NewCar" / "Assets" / "Vehicles" / "Wheeled" / "SampleCar_01" / "workspaces",
        Path.home() / "Documents" / "My Games" / "ArmaReforgerWorkbench" / "addons"
        / "SampleMod_NewCar" / "Assets" / "Vehicles" / "Wheeled" / "SampleCar_01" / "workspaces",
    ])
    found = []
    for candidate in candidates:
        if candidate.is_dir() and candidate not in found:
            found.append(candidate)
    return found


def _workspace_target_name(source: Path, asset_name: str) -> str:
    suffix = source.suffix.lower()
    if suffix in {".aw", ".agr", ".ast"}:
        return f"{asset_name}_Vehicle{suffix}"
    if suffix == ".asi":
        stem = source.stem.lower()
        lane = "Player" if "player" in stem else "Vehicle"
        return f"{asset_name}_{lane}.asi"
    stem = source.stem.replace("SampleCar_01", asset_name).replace("SampleCar", asset_name)
    stem = stem.replace("Explorer", asset_name).replace("ExploreCruiser", asset_name)
    return f"{stem}{source.suffix}"


def _clone_workspace_text(text: str, asset_name: str, resource_dir: str) -> str:
    text = text.replace("Assets/Vehicles/Wheeled/SampleCar_01", resource_dir)
    text = text.replace("SampleCar_01", asset_name)
    text = text.replace("SampleCar", asset_name)
    text = text.replace("Assets/Vehicles/Wheeled/ExploreCruiser", resource_dir)
    text = text.replace("ExploreCruiser", asset_name).replace("Explorer", asset_name)
    text = text.replace("steeringwheel_explorer", f"Steering_{asset_name}")
    return text


def _glass_prefab(project: VehicleProject, name: str, tag: str, resource_dir: str) -> str:
    xob = _registered_or_path(project, f"{resource_dir}/Dst/{name}_Glass_{tag}.xob")
    return f'''GenericEntity : "{{474FBF7F46802ACD}}Prefabs/Vehicles/Wheeled/SampleCar_01/Dst/SampleCar_01_glass_base.et" {{
 ID "RVC_{name}_GLASS_{tag}"
 components {{
  MeshObject "{SAMPLE_GLASS_MESH_COMPONENT}" {{
   Object "{xob}"
  }}
 }}
}}'''


def _light_prefab(project: VehicleProject, name: str, kind: str, side: str, resource_dir: str) -> str:
    xob = _registered_or_path(project, f"{resource_dir}/Lights/{name}_{kind}_{side}.xob")
    return f'''GameEntity : "{{A50B7F75B249F351}}Prefabs/Vehicles/Core/Lights/VehicleEmissiveSurface_Base.et" {{
 ID "RVC_{name}_{kind}_{side}"
 components {{
  MeshObject "{SAMPLE_LIGHT_MESH_COMPONENT}" {{
   Object "{xob}"
  }}
 }}
}}'''


def _glass_emat(name: str, tint: str, resource_dir: str) -> str:
    return f'''MatPBRBasicGlass {{
 Emissive {tint}
 EmissiveLV 5.757
 BCRMap "{{WORKBENCH_GUID_REQUIRED}}{resource_dir}/Data/{name}_Lights_BCR.edds"
 OpacityMap "{{WORKBENCH_GUID_REQUIRED}}{resource_dir}/Data/{name}_Lights_NMO.edds"
 NormalPower 1.0
 NMOMap "{{WORKBENCH_GUID_REQUIRED}}{resource_dir}/Data/{name}_Lights_NMO.edds"
}}'''


def generate_vehicle_sources(project: VehicleProject) -> dict[str, object]:
    addon = local_path(project.addon_root)
    output = local_path(project.output_directory)
    name = _clean(project.asset_name)
    resource_dir = _resource_directory(project)
    prefab_root = addon / PREFAB_OUTPUT_DIR
    written = [
        _write(prefab_root / f"{name}_Base.et", _base_prefab(project), backup=True),
        _write(prefab_root / f"{name.lower()}.et", _child_prefab(project), backup=True),
        _write(output / "Anims" / f"Steering_{name}.txa", _steering_txa()),
        _write(output / "Anims" / f"Throttle_{name}.txa", _throttle_txa()),
        _write(output / "workspaces" / f"{name}_Vehicle.asi", _asi(project, name, resource_dir)),
        _write(output / "export_profiles" / f"{name}.apr", _apr(name)),
    ]
    if project.features.get("glass", True):
        for tag in ("F", "FL", "FR", "R", "RL", "RR", "Light_FL", "Light_FR", "Light_RL", "Light_RR"):
            written.append(_write(prefab_root / "Dst" / f"{name}_glass_{tag}.et", _glass_prefab(project, name, tag, resource_dir)))
    if project.features.get("lights", True):
        for kind in ("Headlight", "Brakelight"):
            for side in ("L", "R"):
                written.append(_write(prefab_root / "Lights" / f"{name}_{kind}_{side}.et", _light_prefab(project, name, kind, side, resource_dir)))
        written.append(_write(output / "Lights" / "Data" / "headlight_glass.emat", _glass_emat(name, "0.95 0.95 1 1", resource_dir)))
        written.append(_write(output / "Lights" / "Data" / "brakelight_glass.emat", _glass_emat(name, "1 0.03 0.03 1", resource_dir)))
    for animation_template in _sample_workspace_candidates(project):
        for source in animation_template.glob("*"):
            if source.suffix.lower() not in {".aw", ".agr", ".agf", ".ast", ".asi"}:
                continue
            target_name = _workspace_target_name(source, name)
            # Keep our generated Vehicle.asi because it maps the steering/throttle
            # TXA resources for this vehicle. Clone graph/template/workspace files
            # around it instead of reusing a stock ASI that points at SampleCar ANMs.
            if target_name == f"{name}_Vehicle.asi":
                continue
            text = _clone_workspace_text(
                source.read_text(encoding="utf-8", errors="ignore"),
                name,
                resource_dir,
            )
            text = text.replace(
                f"{{WORKBENCH_GUID_REQUIRED}}{resource_dir}/{name}.xob",
                _resource_or_placeholder(project),
            )
            written.append(_write(output / "workspaces" / target_name, text, backup=True))
        break
    if project.legacy_alias:
        alias = prefab_root / project.legacy_alias
        if alias.exists() and alias.with_suffix(alias.suffix + ".meta").exists():
            pending_alias = output / "pending" / project.legacy_alias
            written.append(_write(pending_alias, _alias_prefab(project)))
        else:
            written.append(_write(alias, _alias_prefab(project), backup=True))
    pending = {
        "asset_name": name,
        "generated": written,
        "pending_workbench_actions": [
            "Replace WORKBENCH_GUID_REQUIRED placeholders after resource registration.",
            "Register/import master FBX, generated TXAs, and packed TIFF textures.",
            "Rebuild XOB/ANM resources and open the generated child prefab.",
            "Replace a preserved live legacy alias with the generated pending thin alias only after the child prefab has a Workbench GUID.",
        ],
    }
    _write(output / "rvc_generation_manifest.json", json.dumps(pending, indent=2))
    project.save(output / "vehicle_project.json")
    return pending
