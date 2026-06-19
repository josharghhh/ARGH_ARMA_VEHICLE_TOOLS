# Reforger Vehicle Tools

Blender tools for preparing, validating, and exporting wheeled vehicles for Arma Reforger.

## What The Tools Do

- **Part Fixer**: organizes imported vehicle meshes into doors, windows, wheels, lights, interior, exterior, and mechanical groups.
- **Rig tools**: builds and checks a SampleCar-style skeleton, wheel bones, door bones, rotators, suspension, pedals, gauges, and memory points.
- **Collision tools**: creates and reviews `Vehicle`, `FireGeo`, `MineTrigger`, glass, wheel, and component colliders.
- **Build tools**: run one-click collision/FireGeo/LOD passes, V-HACD/CoACD workflows, collider cleanup, and UCX repair.
- **LOD tools**: reduce visual meshes to a target triangle budget while keeping the source file intact.
- **RVC Checker**: reports blocking rig, binding, prefab, resource, and collision problems before export.
- **Structured FBX Profiles**: exports the vehicle as separate master, glass, wheel, and light FBX sets.
- **Texture tools**: packs selected material sources into Enfusion-friendly BCR/NMO texture files.
- **Workbench source generator**: creates SampleCar-style prefab/config sources through the optional local web tool.

## Install

1. Download `reforger_vehicle_checker.zip` from `dist/` or the latest release.
2. Open Blender.
3. Open **Edit > Preferences > Add-ons**.
4. Select **Install from Disk**.
5. Choose `reforger_vehicle_checker.zip`.
6. Enable **Reforger Vehicle Checker**.
7. Press `N` in the 3D Viewport.
8. Use the **Part Fixer** and **RVC** tabs.

Do not unzip the addon before installing it.

## Required Reference

Install the official SampleMod_NewCar reference:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/install_official_sample.ps1
```

See [Dependencies And References](docs/DEPENDENCIES.md).

## Standard Workflow

1. Save a working copy of the `.blend`.
2. In **Part Fixer > Setup**, set asset name, export folder, wheelbase, and wheel radius.
3. Run **Discover**.
4. Organize and review parts.
5. Build/review the SampleCar-style rig.
6. Add memory points and snap points.
7. Build required vehicle collision.
8. Review `Vehicle`, `FireGeo`, `MineTrigger`, glass, wheel, and all collision views.
9. Run **RVC > Check Vehicle**.
10. Fix blocking errors.
11. Export with **Structured FBX Profiles**.
12. Import/rebuild resources in Workbench.
13. Runtime test the prefab.

## Structured Export Profiles

Use **RVC > Structured FBX Profiles** for current vehicle exports.

| Button | Output | Use |
|---|---|---|
| **Master** | `<Asset>.fbx` | Body/interior/exterior, skeleton, memory points, main `Vehicle` collision, wheel mine triggers, and component FireGeo. |
| **Glass** | `Dst/<Asset>_Glass_<slot>.fbx` | DST window parts with `Glass_<slot>`, `UTM_Glass`, and `snap_glass`. |
| **Wheels** | `VehParts/<Asset>_Wheel_<slot>.fbx` | Wheel slot parts with wheel visual and `UCL_VC_wheel00`. |
| **Lights** | `Lights/<Asset>_Light_<slot>.fbx` | Light slot parts with `Light_<slot>`, `UTM_FG_Light_<slot>`, and `snap_light`. |
| **Export All Profiles** | all of the above | Full split export. |

The master export intentionally excludes doors, road wheels, DST glass, DST lights, wheel `VehicleComplex`, and non-wheel `UTM_VC_*`.

## Collision Rules

- `UCX_MainCol_*` and `UBX_MainCol_*` are main vehicle physics.
- Main vehicle physics must be simple and individually convex.
- `UCL_MT_wheel_*` mine triggers belong at the wheel slots.
- `UCX_FG_Engine`, `UCX_FG_Battery`, `UCX_FG_FuelTank`, and `UCX_FG_Gearbox` are required component FireGeo.
- `UTM_Glass` belongs in separate DST glass exports.
- `UCL_VC_wheel00` belongs in wheel part exports.
- Do not export full body/interior/door meshes as master `VehicleComplex`.

See [Collision Reference](docs/COLLISION_REFERENCE.md).

## Guides

- [Tool Usage Guide](docs/BEGINNER_GUIDE.md)
- [Collision Reference](docs/COLLISION_REFERENCE.md)
- [Vehicle ET Setup](docs/VEHICLE_ET_SETUP.md)
- [Dependencies And References](docs/DEPENDENCIES.md)
- [GitHub Publishing](docs/GITHUB_PUBLISHING.md)

## Optional Local Setup Wizard

The RVC panel can open a local web tool at `http://127.0.0.1:8765`.

Install optional packages:

```powershell
py -3 -m pip install -r requirements-wizard.txt
```

The Blender addon works without the web tool.

## Repository Layout

```text
addon/reforger_vehicle_checker/  Blender addon source
docs/                            guide and GitHub Pages files
dist/                            installable addon ZIP
scripts/                         packaging and reference helpers
reference/                       official-reference manifests
```

## Screenshots

TO BE ADDED

## References

- [Official Arma Reforger Samples](https://github.com/BohemiaInteractive/Arma-Reforger-Samples)
- [BK Reforger Blender Addons](https://github.com/steffenbk/bk-reforger-blender-addons)

## License

MIT. See [LICENSE](LICENSE).
