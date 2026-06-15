# Absolute Beginner Guide

This guide assumes you have a vehicle model in Blender but have never prepared an Arma Reforger vehicle.

## 1. Understand The Different Types Of Geometry

Your vehicle contains several different kinds of objects. They do different jobs and must not be confused.

| Type | Purpose | Typical names |
|---|---|---|
| Visual model | What the player sees | `exterior`, `interior`, `door_FL` |
| Vehicle physics | What stops the vehicle hitting the world | `UCX_MainCol_*`, `UBX_*` |
| Mine trigger | Wheel areas used for mine interaction | `UCL_MT_wheel_*` |
| FireGeo | Where bullets and damage hit | `UCX_FG_*`, `UTM_FG_*` |
| Glass FireGeo | Bullet interaction for glass | `UTM_Glass*` |
| Memory points | Invisible positions for seats, lights, and actions | empties such as `driver_idle` |
| Armature | Bones that move wheels, doors, gauges, and controls | `Armature`, `v_body`, `v_door_l01` |

The visual model can be detailed. Vehicle physics should be simple.

## 2. Install The Addon

1. Open Blender.
2. Choose **Edit > Preferences > Add-ons**.
3. Choose **Install from Disk**.
4. Select `reforger_vehicle_checker.zip`.
5. Enable **Reforger Vehicle Checker**.
6. Close Preferences.
7. In the 3D Viewport, press `N`.

You should now see:

- **Part Fixer**: the main preparation workflow.
- **RVC**: checks, safe fixes, texture packing, and checked export.

## 3. Make A Safety Copy

Before pressing preparation buttons:

1. Choose **File > Save As**.
2. Save a working copy with a clear name.
3. Keep the original source model unchanged.

Many tool actions automatically create checkpoint `.blend` files. Keep them until the vehicle works in Workbench.

## 4. Learn Blender Selection Basics

- Left-click selects an object.
- `Shift` + left-click adds or removes objects from the selection.
- `A` selects everything.
- `Alt+A` deselects everything.
- Numpad `1`, `3`, and `7` show front, side, and top views.
- Press `N` to open the tool sidebar.

If a button says **Selected**, it only affects objects you selected.

## 5. Setup Tab

Open **Part Fixer > Setup**.

### Asset

Enter a short asset name without spaces. Example: `ArmoredTruck`.

### Export

Choose the folder inside your Reforger addon where exported vehicle assets should be written.

### Wheelbase

Enter the real distance in meters between the front and rear axle centers.

### Wheel Radius

Enter the tire radius in meters, not the diameter.

### Discover

Run **Discover** first. It reports:

- Vehicle dimensions.
- Current polygon count.
- Possible wheel objects.
- Possible material assignments.
- Whether the long vehicle axis appears correct.

Discover does not intentionally rebuild the vehicle.

### Auto-Setup

Auto-Setup scales and organizes the source model. Review the result immediately. Restore the generated checkpoint if the scale or assignment is wrong.

### Organize

Organize places parts into predictable collections and names them for review.

## 6. Parts Tab

Use the **Parts** tab before rigging.

### Quick Select

Click a part name to select every object assigned to that part.

### Review

Review isolates or ghosts the rest of the vehicle. Use it to find pieces assigned to the wrong door, interior, or exterior group.

### Door Test-Open

Test-open each door. A correctly assigned door should rotate as one rigid part. If trim or glass stays behind, move it into the correct door group.

### Finalize

Finalize joins reviewed part groups into their final named objects.

Only finalize after the assignments are correct.

## 7. Rig Tab

The rig follows the SampleCar-style Enfusion bone contract.

1. Place or verify wheel targets.
2. Build the rig.
3. Skin parts.
4. Click individual bones to review them.
5. Test doors and controls.

Rigid vehicle parts should normally have:

- One exact vertex group matching their bone.
- Every vertex weighted `1.0` to that group.
- One Armature modifier targeting the vehicle armature.

Run **RVC > Check Vehicle** to find broken bindings.

## 8. Memory Tab

Memory points are invisible positions used by Enfusion.

Common examples:

- Driver and passenger idle positions.
- Get-in positions.
- Headlights and emergency lights.
- Exhaust, steering, and interaction positions.

Use the buttons to place initial sockets, then move them manually while viewing the vehicle from several directions.

Do not leave required crew positions at world origin.

## 9. Collision: The Most Important Beginner Section

Open **Part Fixer > Exp > Collision Review**.

Use the review buttons:

- **Model**: visual model only.
- **UCX**: vehicle physics and wheel MineTriggers over the model.
- **FireGeo**: bullet/damage geometry over the model.
- **All**: every section.
- **L/R/F/B/Top**: quick orthographic review directions.
- **Sort + Collapse Enfusion**: repairs Enfusion preset collections and cleans the Outliner view.

### Why One Big UCX Does Not Work

UCX physics objects must be convex.

A shape is convex when a straight line between any two points inside it never leaves the shape. A vehicle outline with a hood, windshield, roof, turret, and rear step is concave.

Therefore, build it from several convex objects:

- Lower chassis.
- Hood/front.
- Front cabin/windshield.
- Rear cabin.
- Turret or roof equipment.

Each object can touch or overlap slightly. Each object must remain convex.

### Build Perceptive UCX Colliders

This creates a starting blockout based on the vehicle and rig dimensions. It is not a finished artistic result. Review and adjust the points so the colliders sit slightly inside the visual shell.

### Selected Parts -> UCX Convex

This creates one convex collider for each selected separated part.

Good selections:

- One door.
- One bumper.
- One turret.
- One detached roof box.

Bad selections:

- The complete exterior.
- The complete interior.
- Every object at once.
- Windows or tiny decorative objects.

Generated hulls are limited to 200 faces and assigned to the Enfusion `Vehicle` preset.

### Convexify Selected UCX

Use this after manually moving UCX vertices.

It rebuilds the selected collider faces from the collider's current points while preserving placement, dimensions, presets, and rigid binding. This repairs twisted or non-planar faces.

### Validate

Validate checks:

- The 200-face limit.
- True convexity.
- Enfusion `Vehicle` usage.
- Correct collection placement.
- Applied scale.
- Naming.
- Required rigid bone bindings.

Do not export while validation reports errors.

## 10. FireGeo And Glass

FireGeo controls bullet and damage interaction. It can be more detailed than vehicle physics, but should still be purposeful.

- Use component boxes for engine, battery, fuel tank, and gearbox.
- Use body and door FireGeo for weapon hits.
- Use `UTM_Glass*` for glass bullet interaction.
- Do not use detailed FireGeo as the main vehicle physics shape.

## 11. LOD Tab

LOD tools reduce visual triangle count.

Always keep an untouched high-detail source file. Inspect reduced meshes for broken wheels, doors, lights, and thin panels.

## 12. RVC Checks And Safe Fixes

Open the **RVC** tab.

### Check Vehicle

Creates a JSON report and identifies blocking errors and warnings.

### Apply Safe Binding Fixes

Creates a checkpoint and repairs deterministic rigid-part binding problems. It verifies that visible object bounds do not move during the repair.

### Prepare Canonical SampleCar Rig

Adds missing canonical bones to an existing positioned armature. This is not a replacement for correctly placing the important bones.

### Generate UTM_Glass Colliders

Extracts detected glass-material faces into glass collision objects.

### Checked Export

Runs the checker first. Export is blocked when errors remain.

## 13. Export

Before export:

1. Save the `.blend`.
2. Run UCX **Validate**.
3. Run **RVC > Check Vehicle**.
4. Resolve blocking errors.
5. Confirm the export directory.
6. Confirm the required export sections.
7. Use **Checked Export**.

After export, import through Enfusion Blender Tools and inspect the generated resources in Workbench.

## 14. Common Problems

### The UCX Looks Correct But Validation Says Non-Convex

The points may be correct while one or more faces are twisted or non-planar. Select the collider and use **Convexify Selected UCX**.

### A Door Collider Does Not Move

The collider needs the same rigid vertex group and Armature modifier as the door.

### The Vehicle Bounces Or Catches The Ground

The lower physics collider may extend below the intended chassis floor or overlap wheel contact areas.

### The Collider Covers Empty Space

The source selection was too large or compound. Delete that generated collider and create several smaller convex colliders.

### Everything Is Wireframe And Hard To Read

Use **Collision Review > UCX** or **Model** instead of **All**.

## 15. Screenshots Needed For This Guide

Useful screenshots to add later:

1. Blender Add-ons installation screen.
2. The Part Fixer Setup tab.
3. Correctly organized parts in the Outliner.
4. A door test-open example.
5. Correct wheel and door bones.
6. Side, front, and top UCX review examples.
7. A good multi-block convex vehicle outline.
8. FireGeo and glass review.
9. A clean RVC check report.
10. Enfusion Workbench import settings and final vehicle test.
