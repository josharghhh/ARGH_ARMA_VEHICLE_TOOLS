# Vehicle Collision Reference

## Main Physics

Main physics colliders use names such as `UCX_MainCol_01_Chassis` and the Enfusion `Vehicle` layer preset.

- Keep each object convex.
- Prefer several simple blocks over one detailed hull.
- Keep physics slightly inside the visible shell.
- Keep colliders away from the ground and inappropriate wheel contact areas.
- Keep each generated hull at or below 200 faces.

## Why Break A Vehicle Into Multiple UCX Objects

A vehicle side profile containing a hood, windshield, roof, turret, and rear step is concave. One object following the entire profile is not valid UCX physics.

Break it at visible changes in direction:

```text
front bumper | hood | windshield/front cabin | rear cabin | rear wall
                                   | turret/roof equipment |
```

Each block is independently convex. Adjacent blocks may touch or overlap slightly.

## FireGeo

FireGeo is for bullet and damage interaction. Use:

- `UCX_FG_Engine`
- `UCX_FG_Battery`
- `UCX_FG_FuelTank`
- `UCX_FG_Gearbox`
- `UTM_FG_Body_*`
- `UTM_FG_Door_*`

FireGeo can be more detailed than main physics. Do not use detailed body FireGeo as the main vehicle physics collider.

## Glass

Glass collision uses `UTM_Glass*` with the `GlassFire` preset. Visual glass and collision glass are separate responsibilities.

## MineTrigger

Wheel mine-trigger cylinders use `UCL_MT_wheel_*` with the `MineTrigger` preset.

## Validation

The addon's UCX validator checks:

- Face count.
- Mathematical convexity.
- Enfusion preset and collection.
- Applied scale.
- Naming.
- Movable-part bone binding.
