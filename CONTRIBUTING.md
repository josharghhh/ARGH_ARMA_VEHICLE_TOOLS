# Contributing

## Development Setup

1. Install Blender 4.x and Enfusion Blender Tools.
2. Install the official SampleMod_NewCar with `scripts/install_official_sample.ps1`.
3. Install or symlink `addon/reforger_vehicle_checker` into Blender's addons directory.
4. Test changes on a copied `.blend`, never the only source file.

## Pull Request Checks

- Keep the addon portable. Do not commit personal absolute paths.
- Do not commit Bohemia game data or copied SampleMod_NewCar assets.
- Preserve user-edited geometry unless an operator explicitly says it rebuilds it.
- Collision generation must keep each UCX object convex and at or below 200 faces.
- New destructive or broad actions must create a checkpoint first.
- Run `python -m compileall -q addon scripts`.
- Run `python scripts/build_release.py`.

## Documentation Screenshots

Screenshots should:

- Use a neutral example vehicle where possible.
- Clearly show the relevant panel and selected objects.
- Avoid exposing private project names or unrelated files.
- Include side, front, and top views for collision examples.
