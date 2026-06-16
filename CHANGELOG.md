# Changelog

## 0.13.0

- Copy-decimate tool ("Selected -> Direct Collision Copy") now builds VALID convex UCX vehicle colliders: the UCX Vehicle target produces guaranteed-convex, face-capped (<=200), outlier-rejected hulls per selected part (or one merged hull with Merge Selected), instead of a non-convex raw copy. So you can copy interior/exterior/any selection straight into working UCX colliders. FireGeo/GlassFire/VehicleComplex targets keep the exact-shape copy as before.

## 0.12.2

- Fixed web tool dead on Blender: rvc_core/paths.py had a backslash inside an f-string expression (legal on Python 3.12+ but a SyntaxError on Blender 4.5's Python 3.11), which broke rvc_core import and the whole build/import web tool. Rebuilt with plain concatenation.
- Fixed the rpf web-helper absolute-import fallback to use this module's real package name (under Blender 4.5 it's bl_ext.<repo>.reforger_vehicle_checker, not a bare reforger_vehicle_checker).

## 0.12.1

- Separate Wheels now handles wheels that are baked into the body mesh: when no wheel-named meshes exist, it extracts wheels by proximity to the v_wheel_* bones (island-based, so the body shell is never grabbed) into wheel_FL/FR/RL/RR. Validated on the coupe (4485 body verts kept, ~2000 verts per wheel).
- Collision Review now uses a single Enfusion-style layer color palette, highlights the active review mode button, and wraps the growing Build/Export controls in collapsible accordion sections.
- Geometry / Parts now has direct copy buttons for `Selected -> UCX Copy` and explicit `Selected -> UTM FireGeo`, including Edit Mode selected-face support.
- Export now auto-repairs rigid part bindings with the same Skin All Parts pass when doors/wheels lose Armature modifiers or vertex groups, and the post-export Build / Import web helper is back in the Part Fixer export flow with vehicle settings prefilled.

## 0.12.0

- Rebuilt the build/import web tool on the Python standard library (http.server) — no FastAPI/uvicorn, zero external dependencies. The "Open Build / Import Web Tool" button now runs it IN-PROCESS inside Blender (background thread, uses Blender's own Python) and surfaces errors, instead of silently failing on a missing system-Python dependency. Endpoints verified: /, /api/status, /static/*, /api/generate (.et + import sources), /api/check.

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
