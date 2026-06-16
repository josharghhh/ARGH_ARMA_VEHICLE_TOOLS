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
- FireGeo, VehicleComplex, GlassFire, and MineTrigger layer presets.
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
| `UCL_VC_*` | `VehicleComplex` |
| `UCX_FG_*`, `UTM_FG_*` | `FireGeo` |
| DST/default `UTM_Glass*` | `FireGeo` |
| explicit legacy `UTM_GlassFire*`, `UTM_Detail_Glass` | `GlassFire` |

## Optional V-HACD / CoACD / vhacdx

The Build tab can generate tighter multi-hull UCX collision through CoACD or an external V-HACD executable. This is preferred for curved vehicle shells and hard wheel-arch/fender angles where single convex chunks bridge empty space.

Controls exposed in Blender:

- backend: Auto, CoACD, VHACD Python (`vhacdx`), External, or Fallback
- max hulls
- face cap
- input triangle target
- concavity
- voxel resolution, volume error, recursion depth, shrinkwrap, fill mode, max hull vertices, min voxel edge, best split plane, and pre-scale for `vhacdx`
- external V-HACD executable path

`Install deps` installs CoACD and NumPy into Blender Python, then tries to install `vhacdx==0.0.6` as an optional Enfusion-style backend. CoACD is enough for the `Auto` and `CoACD` backends; `vhacdx` is useful when you want the same knob set exposed by Enfusion Blender Tools. The add-on zip also bundles `tools/vhacd/TestVHACD.exe` when built from the local `v-hacd-4.1.0.zip`, so `Install deps` and the search button will prefer that packaged executable before checking `PATH`, Desktop, Downloads, Documents, `~/Tools`, or `~/bin`.

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
