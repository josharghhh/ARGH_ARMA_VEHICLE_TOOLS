# Dependencies And Official References

## Required Applications

- Arma Reforger.
- Arma Reforger Tools / Enfusion Workbench.
- Blender 4.x.
- Enfusion Blender Tools installed and enabled in Blender.

The addon does not replace Enfusion Blender Tools. It prepares names, collections, presets, geometry, rigging, and exports for that pipeline.

## Official SampleMod_NewCar

The official sample is the primary reference for:

- SampleCar bone hierarchy.
- Vehicle prefab structure.
- Wheels and slots.
- Animation workspaces.
- Vehicle physics collision.
- FireGeo, GlassFire, and MineTrigger layer presets.
- FBX/XOB import behavior.

Install it with:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/install_official_sample.ps1
```

Default destination:

```text
%USERPROFILE%\Documents\My Games\ArmaReforgerWorkbench\addons\SampleMod_NewCar
```

Important expected file:

```text
Assets/Vehicles/Wheeled/SampleCar_01/SampleCar_01.fbx
```

The official sample is not copied into this repository because it is large, independently maintained, and licensed under the Arma Public License. The installer downloads it from:

https://github.com/BohemiaInteractive/Arma-Reforger-Samples

## Enfusion Collision Presets

The addon assigns the Enfusion Blender Tools object property `usage` and places objects into the corresponding collider collection.

| Name | Required preset |
|---|---|
| `UCX_MainCol_*`, `UBX_MainCol_*` | `Vehicle` |
| `UCL_MT_*` | `MineTrigger` |
| `UCX_FG_*`, `UTM_FG_*` | `FireGeo` |
| `UTM_Glass*`, `UTM_Detail_Glass` | `GlassFire` |

## Optional Setup Wizard

The local RVC webpage requires:

```powershell
py -3 -m pip install -r requirements-wizard.txt
```

It runs only on `127.0.0.1:8765`.

## Licensing

- Reforger Vehicle Tools source: MIT.
- Bohemia Interactive samples: Arma Public License.
- Enfusion Blender Tools: supplied and licensed separately with the official tools.
- BK Reforger Blender Addons: external reference only; not bundled.
