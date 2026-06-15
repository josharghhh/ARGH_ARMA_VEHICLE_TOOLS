# Reforger Vehicle Tools

Blender tools for preparing, checking, and exporting wheeled vehicles for Arma Reforger.

This repository combines two workflows:

- **Reforger Vehicle Part Fixer**: separates and reviews vehicle parts, builds a SampleCar-style rig, creates and reviews collision geometry, places memory points, prepares LODs, and exports an Enfusion FBX set.
- **Reforger Vehicle Checker**: validates the vehicle, safely repairs rigid movable-part bindings, checks export readiness, creates glass colliders, packs BCR/NMO texture sources, and provides an optional local setup webpage.

The tools are designed for Blender 4.x and the official Enfusion Blender Tools workflow.

## Required References

Install the official SampleMod_NewCar reference:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/install_official_sample.ps1
```

This downloads the current official `SampleMod_NewCar` from Bohemia Interactive's samples repository into the standard Workbench addons folder. See [Dependencies And References](docs/DEPENDENCIES.md).

## Download And Install

1. Download `reforger_vehicle_checker.zip` from the latest release or the `dist` folder.
2. Open Blender.
3. Choose **Edit > Preferences > Add-ons**.
4. Click the small arrow/menu in the upper-right, then **Install from Disk**.
5. Select `reforger_vehicle_checker.zip`.
6. Enable **Reforger Vehicle Checker**.
7. Open the 3D Viewport and press `N`.
8. Use the **Part Fixer** and **RVC** tabs.

Do not unzip the release ZIP before installing it through Blender.

## Start Here

Read the [Absolute Beginner Guide](docs/BEGINNER_GUIDE.md) before modifying a vehicle.

To publish this repository and its website, follow [GitHub Publishing](docs/GITHUB_PUBLISHING.md).

The safest first session is:

1. Save the vehicle as a new `.blend`.
2. In **Part Fixer > Setup**, set the wheelbase and wheel radius.
3. Run **Discover** and inspect the console report.
4. Organize and review parts before finalizing.
5. Build and inspect the rig.
6. Build collision, then use **Validate**.
7. Run **RVC > Check Vehicle**.
8. Export only after blocking errors are resolved.

## Important Collision Rule

Every `UCX_*` object must be individually convex. A complete vehicle side outline is normally concave, so it must be represented by several overlapping or touching convex blocks.

Use:

- **Build Perceptive UCX Colliders** for a starting blockout.
- **Selected Parts -> UCX Convex** only on separated parts such as doors or bumpers.
- **Convexify Selected UCX** after manually adjusting collider points.
- **Validate** before export.

Never select the complete high-detail exterior and create one UCX hull around it.

## Repository Layout

```text
addon/reforger_vehicle_checker/  Blender addon source
docs/                            GitHub Pages site and beginner guide
dist/                            Built installable ZIP
scripts/                         Packaging helper
reference/                       Manifests for separately licensed official references
```

## Optional Local Setup Wizard

The RVC panel can open a local webpage at `http://127.0.0.1:8765`.

It requires Python packages from `requirements-wizard.txt`:

```powershell
py -3 -m pip install -r requirements-wizard.txt
```

The Blender tools work without the optional webpage.

## References

- [Official Arma Reforger Samples](https://github.com/BohemiaInteractive/Arma-Reforger-Samples)
- [BK Reforger Blender Addons](https://github.com/steffenbk/bk-reforger-blender-addons)

## License

MIT. See [LICENSE](LICENSE).
