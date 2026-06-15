# Changelog

## 0.11.0

- One-click collision is now GROUPED by category: it merges each part (body `exterior`, and each door) into one mass and decomposes THAT, instead of building a hull per tiny sub-material object. Result: far fewer, cleaner collision hulls (a body shell set + one set per door) that are much easier to read and bake. Glass/lights/wheels are excluded from the grouped collision.

## 0.10.3

- Fixed spiky/oversized UCX hulls: hull builders now reject stray outlier vertices (MAD-based, conservative — validated to drop 4 fliers on a door and shrink its hull from 2.56 m to 1.42 m while leaving clean parts untouched).
- Convex hulls are now triangulated, fixing false "non-convex geometry" validation errors.
- One-click now auto-runs Fix UCX before validating, so it self-heals any remaining bad hulls.
- FireGeo now works on multi-object / renamed parts: it gathers a whole part (collection pieces or name-prefixed pieces like `exterior.metal`), joins a copy, and decimates — instead of needing one object named exactly `exterior`/`door_FL`.

## 0.10.2

- One-click no longer hard-freezes: it now V-HACDs only heavy parts (>=2500 tris) with coarse settings (decimate 1500, threshold 0.12, max 8 hulls) and gives small parts a fast single convex hull.
- V-HACD prints per-part progress to the system console (Window > Toggle System Console) so a long run never looks dead.

## 0.10.1

- New dedicated "Build" tab holds the one-click pipeline, tidy/fix, collision (UCX), V-HACD, and FireGeo/Separate-Wheels; the "Exp" tab is now export-only.

## 0.10.0

- Added "1-Click: Clean + Collision + FireGeo + LOD" — one button runs the whole physics/geo pass: tidy old colliders, build collision (V-HACD multi-hull if available else perceptive convex), build FireGeo, bake LOD, validate.
- Added "Tidy / Remove Colliders" with modes: Generated (this tool's), Invalid only (non-convex/over-cap/unapplied-scale/numeric-suffix/empty), or All collision — and prunes empty collider collections.
- Added "Fix UCX Hulls": applies stray scale, strips numeric suffixes, re-assigns the Vehicle preset, and rebuilds non-convex/over-cap hulls as guaranteed-convex (turning the validator into an actual repair).
- V-HACD now decimates each part to a target tri count before decomposition (default 4000) so Blender no longer freezes on dense bodies.

## 0.9.1

- Fixed V-HACD `AttributeError: 'tuple' object has no attribute 'x'`: decomposed hull points are now normalised to Vector before the convex/cap step. Separate Wheels confirmed working.

## 0.9.0

- Added "Separate Wheels" operator: detects wheel meshes (any naming), splits joined wheel sets into loose parts, clusters them into four quadrants, and names/moves each as wheel_FL/FR/RL/RR into its part collection (front=+Y, left=-X).
- Added V-HACD multi-hull convex decomposition for collision/LOD geometry: CoACD python module if installed, else an external V-HACD (TestVHACD v4) exe, else a single guaranteed-convex fallback. Each hull is rebuilt convex and capped to the face limit and placed as UCX_MainCol via the Vehicle preset.
- Added "Install V-HACD deps (CoACD)" operator that pip-installs coacd + numpy into Blender's bundled Python, and an optional V-HACD exe path setting.
- Reference pass against `Arma-Reforger-Samples`.

## 0.8.8

- Fixed the Export tickbox bug: the master body FBX no longer leaks wheels and windows.
- Body-export classification (`include_master`) is now name-robust — wheels, windows/glass, and light lenses are detected by intent (case-insensitive, any naming) instead of exact stock names, so imported/renamed vehicles keep slot visuals out of the body. Wheel arches/fenders/mudguards are guarded as genuine body parts.
- Collision/FireGeo prefixes (UTM_/UCX_/UCL_) are classified before visual matchers, and the separate wheel FBX export falls back to any wheel-named mesh when `wheel_FL` is absent.
- Reference pass against `Arma-Reforger-Samples` SampleCar_01 confirmed the body / VehParts(wheel) / Dst(glass) / Lights separation.

## 0.8.7

- One-click web tool: fixed generated vehicles loading with broken/empty components.
- (A) Added Measurements & Features inputs to the web form so generated RigidBody mass/centre-of-mass, axle wheel radius, and inertia match the real vehicle instead of hardcoded mid-size-car defaults.
- (B) Auto-resolve the master XOB GUID from its `.xob.meta` (canonical name or any matching meta in the addon) when no token is pasted.
- (C) Never emit `{WORKBENCH_GUID_REQUIRED}` placeholders into the live base prefab: the MeshObject and VehicleAnimationComponent overrides are now only written when the resource resolves, so an unregistered vehicle inherits the working SampleCar mesh/animation instead of an empty/broken component.

## 0.8.6

- Combined Reforger Vehicle Part Fixer and Reforger Vehicle Checker.
- Added true-convex UCX generation with a strict 200-face cap.
- Added selected-UCX convexification that preserves manual placement.
- Added collision layer review views and quick viewport directions.
- Added Enfusion collection sorting and Outliner collapse.
- Added rigid movable-part binding checks and safe repairs.
- Added SampleCar-style rig preparation and checked export.
- Added FireGeo, glass collision, memory point, LOD, and BCR/NMO workflows.
- Added beginner documentation, GitHub Pages site, and official SampleMod_NewCar installer.
