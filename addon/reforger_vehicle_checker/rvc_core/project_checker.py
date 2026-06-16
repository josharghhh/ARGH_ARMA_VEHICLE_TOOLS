from __future__ import annotations

from collections import Counter
from pathlib import Path
import re
import socket

from .models import CheckReport, VehicleProject
from .paths import local_path


RESOURCE_RE = re.compile(r'\{[0-9A-Fa-f]{16}\}[^"\s]+')
PLACEHOLDER = "WORKBENCH_GUID_REQUIRED"
VEHICLE_METAL = "{CE9253778DD8FBDE}Common/Materials/Game/metal.gamemat"
TIRE_RUBBER = "{8F1BCCA995D7FA4B}Common/Materials/Game/rubber_tire.gamemat"
TIRE_RUBBER_4MM = "{C2BF4F9689827271}Common/Materials/Game/RubberTire/rubber_tire_4mm_min.gamemat"
FIREGEO_METAL = "{EDB153DC99889624}Common/Materials/Game/Metal/metal_3mm.gamemat"
WHEEL_METAL = "{1950188BB10D20EA}Common/Materials/Game/Metal/metal_5mm.gamemat"
LIGHT_PLASTIC = "{C17486F3DA1510F6}Common/Materials/Game/Plastic/plastic_3mm.gamemat"
THIN_GLASS = "{8D1F0255D835F302}Common/Materials/Game/Glass/glass_2mm_min.gamemat"
FABRIC = "{5EE22D6E62DCE04A}Common/Materials/Game/Fabric/fabric_6mm_min.gamemat"
ARMORED_METAL = "{469B8DA92D8109EC}Common/Materials/Game/Metal/metal_10mm_min.gamemat"
ARMORED_GLASS = (
    "{7BE37DA4E6BA2358}Common/Materials/Game/GlassArmored/glass_armored_10mm.gamemat"
)
LAMINATED_GLASS = (
    "{9CF9352E79A84A2A}Common/Materials/Game/Glass/glass_laminated_4mm.gamemat"
)
COMPONENT_MATERIALS = {
    "Battery": "{5D38201F93B9DE65}Common/Materials/Game/VehicleParts/vehicle_battery.gamemat",
    "Engine": "{0B9EB7B9C8DCC6A5}Common/Materials/Game/VehicleParts/engine.gamemat",
    "FuelTank": "{2E934203697527B6}Common/Materials/Game/VehicleParts/fuel_tank.gamemat",
    "Gearbox": "{427C6C77966E41CB}Common/Materials/Game/VehicleParts/differential.gamemat",
}
PLASTIC_NAME_HINTS = (
    "plastic", "panel", "trim", "bumper", "fender_flare", "grille",
)
GLASS_NAME_HINTS = (
    "glass", "window", "windscreen", "windshield", "lamp", "lamps", "light",
    "led", "indicator", "blinker", "amber", "mirror",
)
FABRIC_NAME_HINTS = (
    "fabric", "cloth", "carpet", "leather", "seat",
)
RUBBER_NAME_HINTS = (
    "rubber", "tire", "tyre",
)
METAL_NAME_HINTS = (
    "metal", "steel", "chrome", "carpaint", "body", "door", "hood", "trunk",
    "tailgate", "rear", "front", "exterior", "cab", "tray", "undercarriage",
    "chassis", "diamond", "diamont",
)
GEOMETRY_PARAM_RE = re.compile(
    r"(?P<header>    GeometryParam (?P<name>\S+) \{\n)"
    r"(?P<body>.*?)(?=    GeometryParam |\n   \})",
    re.DOTALL,
)


def _name_has(name: str, hints: tuple[str, ...]) -> bool:
    lower = name.lower()
    return any(hint in lower for hint in hints)


def inferred_vehicle_detail_surface(name: str, default_metal: str) -> list[str]:
    """Map generated collision names to valid stock gamemats, never render mats."""
    if _name_has(name, RUBBER_NAME_HINTS):
        return [TIRE_RUBBER_4MM]
    if _name_has(name, GLASS_NAME_HINTS):
        return [THIN_GLASS]
    if _name_has(name, PLASTIC_NAME_HINTS):
        return [LIGHT_PLASTIC]
    if _name_has(name, FABRIC_NAME_HINTS):
        return [FABRIC]
    return [default_metal]


def expected_vehicle_layer_preset(name: str) -> str | None:
    """Return the stock Enfusion layer preset implied by a vehicle collider name."""
    if name.startswith("UCL_MT_"):
        return "MineTrigger"
    if name.startswith("UCL_VC_"):
        return "VehicleComplex"
    if name.startswith("UTM_VC_"):
        return "VehicleComplex"
    if name.startswith("UCX_MainCol_"):
        return "Vehicle"
    if name.startswith("UCX_FG_"):
        return "FireGeo"
    if name.startswith("UTM_GlassFire") or name == "UTM_Detail_Glass":
        return "GlassFire"
    if name.startswith("UTM_Glass"):
        return "FireGeo"
    if name.startswith("UTM_"):
        return "FireGeo"
    return None


def vehicle_layer_preset_issues(text: str) -> list[tuple[str, str | None, str]]:
    """List missing or incorrect vehicle collider layer presets."""
    issues: list[tuple[str, str | None, str]] = []
    for match in GEOMETRY_PARAM_RE.finditer(text):
        name = match.group("name")
        expected = expected_vehicle_layer_preset(name)
        if not expected:
            continue
        preset_match = re.search(r'^\s*LayerPreset "([^"]+)"', match.group("body"), re.MULTILINE)
        actual = preset_match.group(1) if preset_match else None
        if actual != expected:
            issues.append((name, actual, expected))
    return issues


def repair_vehicle_layer_presets(path: str | Path) -> list[tuple[str, str | None, str]]:
    """Safely repair vehicle collider layer presets in an existing XOB meta file."""
    path = Path(path)
    text = path.read_text(encoding="utf-8")
    issues = vehicle_layer_preset_issues(text)
    if not issues:
        return []

    expected_by_name = {name: expected for name, _actual, expected in issues}

    def repair(match: re.Match[str]) -> str:
        name = match.group("name")
        expected = expected_by_name.get(name)
        if not expected:
            return match.group(0)
        body = match.group("body")
        if re.search(r'^\s*LayerPreset "[^"]+"', body, re.MULTILINE):
            body = re.sub(
                r'^(\s*)LayerPreset "[^"]+"',
                rf'\1LayerPreset "{expected}"',
                body,
                count=1,
                flags=re.MULTILINE,
            )
        else:
            body = f'     LayerPreset "{expected}"\n{body}'
        return match.group("header") + body

    path.write_text(GEOMETRY_PARAM_RE.sub(repair, text), encoding="utf-8")
    return issues


def expected_vehicle_surface_properties(name: str, armored_body: bool = False) -> list[str]:
    """Return valid stock game-material resources for a vehicle collider."""
    if name.startswith("UCL_MT_"):
        return [TIRE_RUBBER]
    if name.startswith("UCL_VC_"):
        return [TIRE_RUBBER_4MM]
    if name.startswith("UTM_VC_"):
        return inferred_vehicle_detail_surface(name, WHEEL_METAL)
    if name.startswith("UCX_MainCol_"):
        return [VEHICLE_METAL]
    if name.startswith("UTM_FG_Wheel") and _name_has(name, ("tire", "tyre", "rubber")):
        return [TIRE_RUBBER_4MM]
    if name.startswith("UTM_FG_Wheel") and _name_has(name, ("rim", "hub", "middle", "metal", "inner")):
        return [WHEEL_METAL]
    if name.startswith("UTM_FG_Wheel"):
        return [TIRE_RUBBER_4MM, WHEEL_METAL]
    for component, material in COMPONENT_MATERIALS.items():
        if name in (f"UCX_FG_{component}", f"UTM_FG_{component}"):
            return [material]
    if name.startswith("UTM_FG_Light") or name.startswith("UCX_FG_Light"):
        return [LIGHT_PLASTIC]
    if name.startswith("UTM_Glass") or name == "UTM_Detail_Glass":
        return [ARMORED_GLASS if armored_body else LAMINATED_GLASS]
    if name.startswith("UTM_"):
        return inferred_vehicle_detail_surface(
            name,
            ARMORED_METAL if armored_body else FIREGEO_METAL,
        )
    return []


def vehicle_surface_property_issues(
    text: str, armored_body: bool = False
) -> list[tuple[str, list[str], list[str]]]:
    """List collider surface-property blocks missing required SampleCar gamemats."""
    issues: list[tuple[str, list[str], list[str]]] = []
    for match in GEOMETRY_PARAM_RE.finditer(text):
        name = match.group("name")
        expected = expected_vehicle_surface_properties(name, armored_body)
        if not expected:
            continue
        surface_match = re.search(
            r"     SurfaceProperties \{\n(?P<body>.*?)\n     \}",
            match.group("body"),
            re.DOTALL,
        )
        actual = RESOURCE_RE.findall(surface_match.group("body")) if surface_match else []
        if any(resource not in actual for resource in expected):
            issues.append((name, actual, expected))
    return issues


def repair_vehicle_surface_properties(
    path: str | Path, armored_body: bool = False
) -> list[str]:
    """Replace collider render-material references with valid stock game materials."""
    path = Path(path)
    text = path.read_text(encoding="utf-8")
    changed: list[str] = []

    def repair(match: re.Match[str]) -> str:
        name = match.group("name")
        expected = expected_vehicle_surface_properties(name, armored_body)
        if not expected:
            return match.group(0)
        body = match.group("body")
        surface_match = re.search(
            r"     SurfaceProperties \{\n(?P<body>.*?)\n     \}",
            body,
            re.DOTALL,
        )
        actual = RESOURCE_RE.findall(surface_match.group("body")) if surface_match else []
        if actual and all(resource in actual for resource in expected):
            return match.group(0)
        replacement = "     SurfaceProperties {\n"
        replacement += "".join(f'      "{resource}"\n' for resource in expected)
        replacement += "     }"
        new_body, count = re.subn(
            r"     SurfaceProperties \{\n.*?\n     \}",
            replacement,
            body,
            count=1,
            flags=re.DOTALL,
        )
        if not count:
            insert_at = body.find("     Mass ")
            if insert_at >= 0:
                new_body = body[:insert_at] + replacement + "\n" + body[insert_at:]
            else:
                new_body = replacement + "\n" + body
            count = 1
        if count and new_body != body:
            changed.append(name)
        return match.group("header") + new_body

    repaired = GEOMETRY_PARAM_RE.sub(repair, text)
    if repaired != text:
        path.write_text(repaired, encoding="utf-8")
    return changed


def discover_addons(root: str | Path) -> list[dict[str, str]]:
    root = Path(root)
    found = []
    if not root.exists():
        return found
    for gproj in sorted(root.glob("*/addon.gproj")):
        found.append({"name": gproj.parent.name, "path": str(gproj.parent)})
    return found


def port_open(port: int, host: str = "127.0.0.1", timeout: float = 0.15) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def _resource_exists(addon_root: Path, resource: str) -> bool:
    if not resource:
        return False
    relative = resource.split("}", 1)[-1].replace("\\", "/")
    return (addon_root / relative).exists()


def _local_resource_guids(addon_root: Path) -> set[str]:
    guids: set[str] = set()
    for meta in addon_root.rglob("*.meta"):
        match = re.search(r'\bName\s+"(\{[0-9A-Fa-f]{16}\})', meta.read_text(
            encoding="utf-8", errors="ignore"
        ))
        if match:
            guids.add(match.group(1).upper())
    return guids


def _registered_source_issues(
    addon_root: Path, paths: list[Path], local_guids: set[str]
) -> tuple[list[str], list[str]]:
    placeholders: list[str] = []
    missing: list[str] = []
    for path in paths:
        if not path.is_file() or not path.with_suffix(path.suffix + ".meta").is_file():
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        if PLACEHOLDER in text:
            placeholders.append(str(path.relative_to(addon_root)))
        for resource in RESOURCE_RE.findall(text):
            guid = resource.split("}", 1)[0].upper() + "}"
            if guid in local_guids and not _resource_exists(addon_root, resource):
                missing.append(f"{path.relative_to(addon_root)} -> {resource}")
    return placeholders, missing


def check_project(project: VehicleProject) -> CheckReport:
    addon_root = local_path(project.addon_root)
    output = local_path(project.output_directory)
    report = CheckReport(project.asset_name)
    report.facts.update({
        "addon_root": str(addon_root),
        "output_directory": str(output),
        "blender_mcp_connected": port_open(9876),
        "project_file": str(addon_root / "addon.gproj"),
    })

    if not (addon_root / "addon.gproj").exists():
        report.add("project.gproj", "error", "addon.gproj is missing", False,
                   "Select a valid Reforger addon directory.")
    if not output.is_relative_to(addon_root):
        report.add("project.output_inside_addon", "error",
                   "Output directory is outside the selected addon.", False,
                   "Choose an output directory inside the addon.")
    if not project.imported_xob_resource:
        report.add("resource.xob.selected", "warning",
                   "No imported XOB resource token supplied.", False,
                   "Import/rebuild the master FBX in Workbench and paste its resource token.")
    elif not _resource_exists(addon_root, project.imported_xob_resource):
        report.add("resource.xob.exists", "warning",
                   f"XOB token does not resolve on disk: {project.imported_xob_resource}")

    source_blend = local_path(project.source_blend) if project.source_blend else None
    if source_blend and not source_blend.exists():
        report.add("source.blend.exists", "error", f"Missing source blend: {source_blend}")

    if project.imported_xob_resource:
        relative = project.imported_xob_resource.split("}", 1)[-1].replace("\\", "/")
        meta = addon_root / f"{relative}.meta"
    else:
        meta = output / f"{project.asset_name}.xob.meta"
    if meta.exists():
        text = meta.read_text(encoding="utf-8", errors="ignore")
        for key in ("ExportSkinning 1", "ExportSceneHierarchy 1", "Animated 1"):
            if key not in text:
                report.add(f"meta.{key.split()[0].lower()}", "error",
                           f"{meta.name} is missing `{key}`.", True,
                           "Apply safe metadata fixes.")
        report.facts["material_assign_count"] = text.count("MaterialAssignClass")
        layer_issues = vehicle_layer_preset_issues(text)
        if layer_issues:
            evidence = ", ".join(
                f"{name}: {actual or 'missing'} -> {expected}"
                for name, actual, expected in layer_issues
            )
            report.add(
                "meta.collider_layer_presets",
                "error",
                f"Invalid vehicle collider layer presets: {evidence}",
                True,
                "Apply safe metadata fixes, then rebuild the XOB in Workbench.",
            )
        report.facts["collider_layer_preset_issues"] = layer_issues
        surface_issues = vehicle_surface_property_issues(text)
        if surface_issues:
            evidence = ", ".join(
                f"{name}: {len(actual)} material(s) -> {len(expected)} expected"
                for name, actual, expected in surface_issues[:8]
            )
            report.add(
                "meta.collider_surface_properties",
                "error",
                f"Invalid vehicle collider surface properties: {evidence}",
                True,
                "Apply safe metadata fixes, then rebuild the XOB in Workbench.",
            )
        report.facts["collider_surface_property_issues"] = surface_issues
    else:
        report.add("meta.master.exists", "warning", f"Missing {meta.name}", False,
                   "Export/import the master FBX before final validation.")

    prefab_dir = addon_root / "Prefabs" / "Vehicles" / "Wheeled" / "RVC_VEHICLES"
    base = prefab_dir / f"{project.asset_name}_Base.et"
    child = prefab_dir / f"{project.asset_name.lower()}.et"
    for rule, path in (("prefab.base", base), ("prefab.child", child)):
        if not path.exists():
            report.add(rule, "warning", f"Missing generated prefab: {path.name}", True,
                       "Generate Enfusion sources.")

    duplicate_slots = []
    if base.exists():
        text = base.read_text(encoding="utf-8", errors="ignore")
        slots = re.findall(r"(?:SCR_WheelSlotInfo|EntitySlotInfo|RegisteringComponentSlotInfo)\s+(\w+)", text)
        duplicate_slots = [name for name, count in Counter(slots).items() if count > 1]
        if duplicate_slots:
            report.add("prefab.slots.unique", "error",
                       "Duplicate slot names: " + ", ".join(duplicate_slots))
    registered_sources = [base, child]
    registered_sources.extend(sorted((output / "workspaces").glob("*.aw")))
    registered_sources.extend(sorted((output / "workspaces").glob("*.asi")))
    placeholders, missing_resources = _registered_source_issues(
        addon_root, registered_sources, _local_resource_guids(addon_root)
    )
    if placeholders:
        report.add(
            "resource.registered_placeholders",
            "error",
            "Registered live sources still contain unresolved resource placeholders: "
            + ", ".join(placeholders),
            False,
            "Resolve each placeholder to its Workbench-registered GUID before runtime testing.",
        )
    if missing_resources:
        report.add(
            "resource.registered_paths",
            "warning",
            "Registered live sources reference local GUIDs at missing or stale paths: "
            + "; ".join(missing_resources[:8]),
            False,
            "Correct stale local resource paths or regenerate the affected source.",
        )
    report.facts["duplicate_slots"] = duplicate_slots
    report.facts["registered_placeholder_sources"] = placeholders
    report.facts["missing_registered_resources"] = missing_resources
    report.facts["pending_workbench_actions"] = [
        "Register/import generated TIFF textures and FBXs.",
        "Rebuild master XOB and generated glass/light resources.",
        "Compile generated TXA sources to ANM.",
        "Open generated child prefab and perform runtime drive test.",
    ]
    return report
