# Tool Usage Guide

This guide covers the current Blender addon workflow for Arma Reforger wheeled vehicles.

## Install

1. Open Blender.
2. Open **Edit > Preferences > Add-ons**.
3. Select **Install from Disk**.
4. Choose `reforger_vehicle_checker.zip`.
5. Enable **Reforger Vehicle Checker**.
6. Press `N` in the 3D Viewport.

The addon adds two tabs:

- **Part Fixer**: mesh organization, rigging, memory points, collision, and legacy export tools.
- **RVC**: checks, safe fixes, texture packing, structured FBX profiles, and the optional web helper.

## Geometry Types

| Type | Purpose | Names |
|---|---|---|
| Visual body | What players see | `exterior`, `interior`, `door_FL` |
| Main vehicle physics | Driving/blocking collision | `UCX_MainCol_*`, `UBX_MainCol_*` |
| Mine triggers | Wheel mine interaction | `UCL_MT_wheel_L01/R01/L02/R02` |
| FireGeo | Bullet and damage hits | `UCX_FG_*`, `UTM_FG_*` |
| DST glass | Slot-mounted windows | `Glass_FL`, `UTM_Glass`, `snap_glass` |
| Wheel part | Slot-mounted wheel | `Wheel_FL`, `UCL_VC_wheel00` |
| Light part | Slot-mounted lights | `Light_FL`, `UTM_FG_Light_FL`, `snap_light` |
| Memory points | Positions used by scripts/prefabs | empties such as `driver_idle`, `snap_glass_FL` |
| Armature | Vehicle animation skeleton | `v_body`, `v_wheel_l01`, `v_door_l01` |

## Basic Workflow

1. Save a working copy of the vehicle `.blend`.
2. Set **Part Fixer > Setup > Asset** and **Export**.
3. Enter real wheelbase and wheel radius.
4. Run **Discover**.
5. Organize and review parts.
6. Build/review the rig.
7. Add memory points.
8. Build required collision.
9. Review collision views.
10. Run **RVC > Check Vehicle**.
11. Fix blocking errors.
12. Export with **RVC > Structured FBX Profiles**.
13. Import/rebuild in Workbench.
14. Test the vehicle in game.

## Part Fixer > Setup

Use this tab first.

- **Asset**: file/resource base name, for example `Begal`.
- **Export**: addon asset folder for FBX output.
- **Wheelbase**: front axle center to rear axle center in meters.
- **Wheel radius**: tire radius in meters.
- **Discover**: measures the vehicle and reports likely parts.
- **Auto-Setup**: scales and assigns source meshes into collections.
- **Organize**: applies predictable part grouping and names.
- **Apply Textures**: applies imported texture/material sources.
- **Check Transforms**: finds bad object transforms before rig/export.

Screenshot: TO BE ADDED

## Part Fixer > Parts

Use this tab to correct part assignment before rigging.

- **Quick Select**: selects all objects in a part group.
- **Review**: isolates or ghosts the active part.
- **Door Test-Open**: rotates a door group to expose wrong assignments.
- **Add Selected**: moves selected objects into the active part.
- **Finalize**: joins reviewed part groups into final named objects.

Do not finalize until doors, windows, wheels, lights, interior, and exterior are assigned correctly.

Screenshot: TO BE ADDED

## Rig

The vehicle rig follows the SampleCar-style bone contract.

Important bones:

- `v_root`
- `v_body`
- `v_axle_01`, `v_axle_02`
- `v_suspension_l01/r01/l02/r02`
- `v_rotator_l01/r01`
- `v_wheel_l01/r01/l02/r02`
- `v_door_l01/r01/l02/r02`
- `v_trunk`
- `v_steering_wheel`
- pedal and dashboard bones

Rigid movable parts should have:

- one exact vertex group matching the target bone;
- all vertices weighted `1.0` to that group;
- one Armature modifier targeting the vehicle armature;
- identity local transform after binding.

Use **RVC > Check Vehicle** to find broken bindings.

Screenshot: TO BE ADDED

## Memory Points

Memory points are empties used by slots, seats, actions, lights, and effects.

Common points:

- crew idle/get-in points;
- `snap_glass_<slot>` for glass exports;
- `snap_light_<slot>` for light exports;
- wheel, exhaust, light, and interaction markers.

Do not leave required crew or slot points at world origin unless that is intentional.

Screenshot: TO BE ADDED

## Collision

Main vehicle collision must be simple and convex.

Use these tools:

- **Required Vehicle Collision**: creates main UCX/UBX blocks, wheel mine triggers, and component boxes.
- **Selected Parts -> UCX Convex**: creates one convex `Vehicle` collider per selected part.
- **Edit Selection -> UCX**: builds controlled UCX from selected faces.
- **Selected -> Direct Collision Copy**: creates FireGeo, GlassFire, VehicleComplex, or validated UCX copies.
- **Fix Layer + Gamemats**: assigns Enfusion layer presets and stock game materials.
- **Validate UCX Physics**: checks face count, convexity, usage, transforms, and naming.
- **Convexify Selected UCX**: repairs selected adjusted UCX hulls.
- **Collision Review View**: isolates `Vehicle`, `FireGeo`, glass, wheels, MineTrigger, or all collision.

Do not make one full-body UCX hull around a concave vehicle. Use several hulls.

Screenshot: TO BE ADDED

## Part Fixer > Build

Use this tab for combined build and repair actions.

- **Required Vehicle Collision**: creates expected SampleCar-style vehicle collision.
- **Build FireGeo**: creates body, door, trunk, and component FireGeo.
- **Auto Tune From Mesh**: adjusts decomposition settings from selected mesh complexity.
- **Selected Parts -> UCX Convex**: builds capped convex hulls from selected parts.
- **Edit Selection -> UCX**: builds UCX from selected faces.
- **Selected -> Direct Collision Copy**: creates direct FireGeo, GlassFire, VehicleComplex, or validated UCX copies.
- **Validate UCX Physics**: checks convexity, face count, transforms, usage, and naming.
- **Convexify Selected UCX**: repairs selected UCX hull geometry.
- **Tidy / Remove Colliders**: removes generated, invalid, or all collision objects depending on mode.

Use one-click build actions as a starting point. Review the result before export.

Screenshot: TO BE ADDED

## LOD

LOD tools reduce visual triangle count for runtime performance.

Use LOD tools after:

- part assignment is correct;
- rig and collision are reviewed;
- a high-detail source `.blend` has been saved.

Inspect reduced meshes for damaged wheels, doors, glass, lights, and thin trim.

Screenshot: TO BE ADDED

## FireGeo

Use FireGeo for bullet and damage interaction.

Required component colliders:

- `UCX_FG_Engine`
- `UCX_FG_Battery`
- `UCX_FG_FuelTank`
- `UCX_FG_Gearbox`

Common detail colliders:

- `UTM_FG_Body_*`
- `UTM_FG_Door_*`
- `UTM_FG_Interior`
- `UTM_FG_Light_*`

FireGeo can follow the visual model more closely than main physics, but it should still be purposeful.

Screenshot: TO BE ADDED

## Glass

Current workflow: export glass as separate DST slot parts.

Each glass export should contain:

- visual mesh named `Glass_<slot>`;
- collider named `UTM_Glass`;
- empty named `snap_glass`.

Source snap empties should be named:

- `snap_glass_F`
- `snap_glass_FL`
- `snap_glass_FR`
- `snap_glass_RL`
- `snap_glass_RR`
- `snap_glass_R`

The exported child object uses `snap_glass`; the vehicle slot uses `ChildPivotID "snap_glass"`.

Screenshot: TO BE ADDED

## Wheels

Current workflow: export wheels as separate wheel slot parts.

Each wheel export should contain:

- wheel visual mesh;
- `UCL_VC_wheel00` on `VehicleComplex`;
- wheel FireGeo when needed for tire/rim hit detail.

The master vehicle keeps wheel bones and wheel slot definitions. The master does not export visual road wheels.

Screenshot: TO BE ADDED

## Lights

Current workflow: export light parts separately like glass.

Each light export should contain:

- visual mesh named `Light_<slot>`;
- collider named `UTM_FG_Light_<slot>`;
- empty named `snap_light`.

Source snap empties should use names such as:

- `snap_light_FL`
- `snap_light_FR`
- `snap_light_RL`
- `snap_light_RR`
- `snap_light_roofbar`
- `snap_light_grille_L`

Use this for headlights, brake lights, indicators, light covers, and emergency light parts.

Screenshot: TO BE ADDED

## RVC Tab

Use this tab before export.

- **Check Vehicle**: writes a report and lists blocking issues.
- **Apply Safe Binding Fixes**: repairs deterministic rigid binding problems after making a checkpoint.
- **Prepare Canonical SampleCar Rig**: adds missing canonical bones to an existing positioned rig.
- **Generate UTM_Glass Colliders**: extracts detected glass material faces into glass collision meshes.
- **Checked Export**: runs checks, then calls the legacy exporter if no blocking errors remain.
- **Structured FBX Profiles**: exports master, glass, wheels, lights, or all profiles.
- **Open Build / Import Web Tool**: starts the optional local project setup page.
- **Export Selected BCR / NMO**: writes selected material texture sources.

Screenshot: TO BE ADDED

## Structured FBX Profiles

Use this for the current split-export workflow.

| Button | Output | Contains |
|---|---|---|
| **Master** | `<Asset>.fbx` | Body, interior, exterior, skeleton, memory points, main `Vehicle` collision, wheel mine triggers, component FireGeo. |
| **Glass** | `Dst/<Asset>_Glass_<slot>.fbx` | `Glass_<slot>`, `UTM_Glass`, `snap_glass`. |
| **Wheels** | `VehParts/<Asset>_Wheel_<slot>.fbx` | Wheel visual, `UCL_VC_wheel00`. |
| **Lights** | `Lights/<Asset>_Light_<slot>.fbx` | `Light_<slot>`, `UTM_FG_Light_<slot>`, `snap_light`. |
| **Export All Profiles** | all profile outputs | Full vehicle FBX split. |

The master profile excludes:

- slot doors;
- road wheels;
- DST glass;
- DST lights;
- wheel `VehicleComplex`;
- non-wheel `UTM_VC_*`.

Screenshot: TO BE ADDED

## Workbench Import

After exporting:

1. Refresh Resource Manager.
2. Import/rebuild the master XOB.
3. Import/rebuild glass XOBs.
4. Import/rebuild wheel XOBs.
5. Import/rebuild light XOBs.
6. Check `.xob.meta` layer presets and game materials.
7. Open generated or hand-authored `.et` prefabs.
8. Confirm glass/light prefabs override the inherited MeshObject component, not add a duplicate MeshObject.
9. Spawn the runtime vehicle prefab.

Screenshot: TO BE ADDED

## Common Problems

| Problem | Cause | Fix |
|---|---|---|
| Vehicle sinks or creeps | Bad master collision, wheel slots, glass/light duplicate physics, or full-body `VehicleComplex` | Remove bad master `UTM_VC_*`, verify wheel slots, use separate DST glass/light exports. |
| Duplicate default cube in glass/light prefab | Child added a new MeshObject instead of overriding inherited MeshObject | Use the inherited component ID and point it at the correct XOB. |
| UCX validates as non-convex | Twisted faces or concave hull | Use **Convexify Selected UCX** or rebuild smaller hulls. |
| Door does not animate | Bad binding or wrong vertex group | Bind rigidly to the exact door bone. |
| Glass does not attach correctly | Missing or wrong `snap_glass` | Add `snap_glass_<slot>` in Blender and export glass profile again. |
| Light prefab attaches wrong | Missing or wrong `snap_light` | Add `snap_light_<slot>` and export light profile again. |
| Workbench reports wrong GUID | Resource path/GUID mismatch | Refresh/rebuild resource database and update the prefab resource token. |

## Runtime Test

Spawn the runtime vehicle prefab and check:

- rests on wheels;
- no idle creep;
- no ground sinking;
- wheels steer/spin;
- doors animate;
- glass appears and breaks correctly;
- lights attach at the correct points;
- no unresolved resource errors in logs.

Screenshot: TO BE ADDED
