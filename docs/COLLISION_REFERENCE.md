# Vehicle Collision Reference

## Guided Workflow

Use **Part Fixer > Build** after wheel separation, rig placement, and part finalization.

1. Separate wheels if the source mesh still has tire/rim geometry merged into the body.
2. Run **Analyze Vehicle Parts**. This tags meshes as exterior, cab, rear area/tray, hood, undercarriage, doors, glass, lights, wheels, brakes, interior, or mechanical.
3. Use the group selection buttons to visually check the analysis. Correct obvious source naming/collection issues before building collision.
4. Set the V-HACD/CoACD parameters: max hulls, face cap, input triangle target, concavity, and the advanced VHACD voxel controls when using the `vhacdx` backend.
5. Run **1-Click** with **Analyze** and **Use V-HACD/CoACD** enabled, or manually select a reviewed group and run **V-HACD -> Multi-Hull UCX**.
6. For problem areas, enter Edit Mode on the render mesh, select the exact panel/arch/cab region, and run **Edit Faces -> UCX**. Keep **Split islands** enabled for separated panels and hard body breaks.
7. Stop and inspect `UCX`, `FireGeo`, `Glass`, and wheel/detail review modes. `All Wheel` shows the full wheel collision set; `VehicleComplex` shows all VehicleComplex colliders including `UTM_VC_*` direct-detail copies; `Wheel FireGeo` and `MineTrigger` isolate the other wheel collider jobs.
8. Run **Fix Layer + Gamemats**, **Fix UCX Hulls**, and **Validate** before export.

The main physics rule is unchanged: `Vehicle` collision must be multiple convex hulls. Use V-HACD/CoACD for curved or highly concave vehicle shells where broad profile chunks bridge wheel arches or hard body angles.

## Layer And Gamemat Matrix

| Geometry name | Layer preset | Surface properties |
| --- | --- | --- |
| `UCX_MainCol_*`, `UBX_MainCol_*` | `Vehicle` | `Common/Materials/Game/metal.gamemat` |
| `UCX_FG_Engine` | `FireGeo` | `VehicleParts/engine.gamemat` |
| `UCX_FG_Battery` | `FireGeo` | `VehicleParts/vehicle_battery.gamemat` |
| `UCX_FG_FuelTank` | `FireGeo` | `VehicleParts/fuel_tank.gamemat` |
| `UCX_FG_Gearbox` | `FireGeo` | `VehicleParts/differential.gamemat` |
| `UTM_FG_Body_*`, `UTM_FG_Door_*`, `UTM_FG_Trunk` | `FireGeo` | metal thickness gamemat |
| `UTM_FG_Interior` | `FireGeo` | fabric or plastic gamemat |
| `UTM_FG_Light_*` | `FireGeo` | plastic or light-cover gamemat |
| `UCL_MT_wheel_*` | `MineTrigger` | tire rubber gamemat |
| `UCL_VC_wheel00` | `VehicleComplex` | tire rubber thickness gamemat |
| direct-copy `UTM_VC_*` | `VehicleComplex` | metal/detail gamemat by default |
| `UTM_FG_Wheel_Tire_*` | `FireGeo` | tire rubber gamemat |
| `UTM_FG_Wheel_Rim_*`, `UTM_FG_Wheel_Hub_*` | `FireGeo` | metal rim gamemat |
| generic `UTM_FG_Wheel_*` | `FireGeo` | tire rubber plus metal rim gamemats |
| DST/default `UTM_Glass` | `FireGeo` | laminated or armored glass gamemat |
| explicit legacy `UTM_GlassFire*` | `GlassFire` | laminated or armored glass gamemat |

Collision Review uses an Enfusion-style layer palette: `Vehicle` orange, `FireGeo` red, `GlassFire` cyan, `MineTrigger` green, and `VehicleComplex` yellow/gold. Generated colliders use the same palette in the viewport so layer mistakes are visible before export. Selecting a collider in Blender shows the detected layer preset and first surface-property gamemat in the Part Fixer review panel.

## Rig Assignment Before Export

Use **Part Fixer > Rig > Rig Assignment / Binding** when model object names do not match the stock SampleCar names. Manual assignment wins over regex guessing.

- Select a mesh, choose a role such as `Steering Wheel`, `Wheel`, `Rotator`, `Suspension`, `Door`, `Interior`, `Light`, `Glass`, or `Custom Bone`, then click **Assign Selected Object To Bone**.
- Use **Create Missing Bone** to add a SampleCar-style bone at the selected mesh center. Bone review buttons enter Armature Edit Mode so the head/tail can be moved directly.
- Use **Bind Whole Object 100%** for rigid objects such as steering wheels, rotator meshes, suspension objects, doors, and pedals.
- In Edit Mode, **Bind Edit Selection 100%** weights only the selected faces/vertices to the target bone.
- Use **Mirror Opposite Bone** after moving one side of a door, suspension, rotator, or wheel bone.
- The resolver accepts broad aliases such as `steeringwheel`, `v_steeringwheel`, `rotator_l`, `rotor_FL`, `wheelrotator_r`, `l01`, `r01`, `l02`, and `r02`.

## Main Physics

Main physics colliders use names such as `UCX_MainCol_01_Chassis` and the Enfusion `Vehicle` layer preset.

- Keep each object convex.
- Prefer many tight hulls over one loose hull.
- Keep physics slightly inside the visible shell.
- Do not bridge wheel arches, window openings, hood seams, roof breaks, trunk lines, or hard rocker/fender angles.
- Keep colliders away from the ground and inappropriate wheel contact areas.
- Keep each generated hull at or below 200 faces.

## V-HACD / CoACD / vhacdx

The Build tab supports both:

- CoACD installed into Blender Python.
- `vhacdx`, the same optional Python backend used by Enfusion Blender Tools.
- External V-HACD executable as fallback.
- Capped convex fallback when no decomposition backend is available.

Recommended starting point for coupe body shells:

- max hulls: `24`
- face cap: `200`
- input tris: `6000`
- concavity: `0.035`
- voxel resolution: `100000`
- volume error: `1.0`
- recursion depth: `10`
- max hull vertices: `64`
- shrinkwrap: on
- fill mode: flood

Lower concavity and higher hull count follow curvature and hard angles more closely, at the cost of more generated hulls.

Use **Edit Faces -> UCX** when automatic grouped decomposition bridges a wheel arch, window opening, tray gap, or fender crease. Select only the external shell region you want the collider to follow; the tool copies the selected faces into a temporary world-space mesh, optionally splits loose selected islands, decomposes that region, rebuilds each result as a mathematically convex hull, caps it to the configured face limit, and tags it as `Vehicle` with the stock metal gamemat.

If a backend returns more hulls than the configured hull cap, the tool must not keep the first arbitrary N hulls. It selects representative hulls across the full source bounds: largest hull first, then farthest/size-weighted hulls. This prevents the “roof/interior only, exterior missing” result that happens when CoACD returns 100+ hulls for an open car shell.

Use **Auto Tune From Mesh** before generating selected collision. Select the actual hood/door/body panel group first, then click the auto-tune button. The tool reads triangle count, open-edge ratio, bounds, and semantic hints, then resets risky values such as `Pre-scale` and chooses safer hull/concavity/decimation settings for that mesh. It intentionally recommends direct FireGeo/VehicleComplex workflows for glass, lights, wheels, seats, and interior detail instead of feeding those into main `Vehicle` UCX.

`Worker Threads` parallelizes decomposition for multiple selected render meshes. Blender mesh extraction and collider creation still run on the main thread because `bpy` is not thread-safe. Start with `2`; use `3-4` only when decomposing several separate selected parts and the machine remains responsive. External executable mode stays effectively serial to avoid launching many heavy processes at once.

Manual UCX builders append by default. Leave **Replace existing generated UCX** off while building panel-by-panel; enable it only when you deliberately want a clean regenerated pass. Full **1-Click** remains a rebuild command and still cleans generated collision at the start.

The manual UCX builders also support Edit Mode. With faces selected, **Selected Parts -> UCX Convex** creates one capped convex hull per selected face island, and **V-HACD -> Selected** decomposes those selected face islands instead of the whole object. Switch to Object Mode only when you want the whole selected mesh/object used as the source.

## Smart Part Analysis

The analyzer is non-destructive. It writes custom properties on render meshes:

- `rpf_category`: semantic class such as `cab`, `rear_area`, `glass`, `wheel`, or `door`
- `rpf_collision_group`: grouped input for hull generation
- `rpf_collision_role`: `vehicle`, `firegeo`, `dst-glass`, or `wheel-slot`
- `rpf_material_hint`: metal, glass, rubber, plastic, fabric, or unknown

`rpf_build_categories` is updated from the detected `vehicle` groups. Glass, lights, wheels, brakes, interior, and mechanical detail are tagged for the correct FireGeo/DST/wheel workflows and are not fed into main `Vehicle` UCX unless deliberately added.

## FireGeo

FireGeo is for bullet and damage interaction. It can conform more closely to visual meshes than main physics, but it should still be reviewed as separate geometry.

Use FireGeo for:

- body shell and doors
- interior and dashboard surfaces
- engine, battery, fuel tank, gearbox
- glass when exported as DST glass
- light covers and lenses
- wheel FireGeo in separate wheel-slot exports

Do not use detailed body FireGeo as the main vehicle physics collider.

## Direct Copy From Selected Meshes

For clean source vehicles, selected render surfaces can be duplicated directly into collision/detail geometry:

- **Selected -> UCX Copy** creates `UCX_MainCol_*_copy` on the `Vehicle` layer from the selected mesh or selected Edit Mode faces.
- **Selected -> UTM FireGeo** creates `UTM_FG_*` on the `FireGeo` layer.
- **Glass** creates `UTM_GlassFire_*` on the `GlassFire` layer for explicit legacy/master glass behavior.
- **UTM VehicleComplex Detail** creates `UTM_VC_*` on the `VehicleComplex` layer.

UCX direct copies are intentionally literal copies. Use them for clean convex-ish panels or as a fast starting point, then run **Validate** and **Fix UCX Hulls** before export. Non-convex UCX geometry will still be rejected by the checker.

Controls:

- copy ratio `1.0` keeps the mesh exactly
- lower copy ratio decimates the duplicate only
- merge joins selected duplicates into one collider object

This is intended for good external shell faces, DST/detail hit surfaces, light covers, tray/body panels, and other already-clean collision candidates. It does not replace main `Vehicle` physics: arbitrary copied render meshes are often concave or too dense, so main driving/blocking collision should still be `UCX_MainCol_*` convex hulls.

Collision `SurfaceProperties` must use stock game-material resources, not imported render material names. The metadata repair policy maps generated collision names like `carpaint`, `metal`, `body`, or `chrome` to valid metal gamemats; `plastic`/`panel` to plastic; `glass`/`lamp`/`light`/`amber`/`mirror` to glass; `carpet`/`leather`/`seat` to fabric; and tire/rubber names to tire rubber.

**Fix Layer + Gamemats** applies the same policy inside Blender before export. It sets the Enfusion `usage` property, moves the object into the matching `Colliders/<LayerPreset>` collection, creates Blender material slots named from the target gamemat resource, and stores `rpf_surface_properties` for review/repair tooling.

## Wheels

The master vehicle should contain `UCL_MT_wheel_L01/L02/R01/R02` on `MineTrigger`.

The optional wheel slot FBX follows the SampleCar pattern:

- `UCL_VC_wheel00` on `VehicleComplex`
- `UTM_FG_Wheel_Tire_L01` on `FireGeo`
- `UTM_FG_Wheel_Rim_L01` on `FireGeo`
- rubber tire gamemat for the outside
- metal gamemat for the inner rim/hub

Wheel slot export modes:

- **Single** exports one generic `<Asset>_Wheel.fbx`.
- **Front + Rear** exports `<Asset>_Wheel_Front.fbx`, `<Asset>_Wheel_Rear.fbx`, and a compatibility `<Asset>_Wheel.fbx` from the front wheel.
- **All four** exports FL/FR/RL/RR wheel FBXs.
- **Selected Alt** exports the selected wheel meshes together as `<Asset>_Wheel_Alt.fbx`.

Wheel visuals are duplicated into temporary centered export copies. The original wheel objects are not moved; the exported mesh is baked around the wheel's actual center so the FBX pivot sits at the tire center. Rear dually meshes should be exported with **Front + Rear** or **Selected Alt** so the rear dual tire spacing remains intact.

Visual road wheels remain in the Blender scene for bone placement and ride-height reference, but they are excluded from the master vehicle FBX. They export only through the separate wheel-slot FBX path with their wheel colliders. Cabin steering wheels are not road wheels; steering aliases are always included in the master render export and bind to `v_steering_wheel`.

## Validation

The addon's validator checks:

- face count
- mathematical convexity
- Enfusion layer preset and collection
- applied scale
- naming
- movable-part bone binding
- expected game-material surface properties in XOB metadata
