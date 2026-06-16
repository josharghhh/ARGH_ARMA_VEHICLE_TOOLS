# Reforger Vehicle `.et` + Simulation Setup — Reference Skill

Authoritative breakdown of a **complete** wheeled-vehicle prefab, reverse-engineered from
`SampleMod_NewCar/.../SampleCar_01_Base.et` (the official sample) and cross-checked against
ARGH `Explorer_Base.et`, the ARGH kart, and the BI car-creation wiki PDFs in
`bearcat/docs`. Use this to (a) understand vehicle simulation and (b) make the RVC
generator emit a *full* vehicle instead of a 4-component stub.

> Companion docs (already exist, don't duplicate): `bearcat/docs/VEHICLE_MESH_PREP_PIPELINE.md`
> (mesh/collider/LOD prep) and `VEHICLE_RIGGING_USECASE.md` (skeleton/bones). This doc is the
> **prefab + simulation** layer that comes *after* a rigged, exported XOB.

---

## 1. Inheritance chain (critical)

```
Prefabs/Vehicles/Core/Wheeled_Car_Base.et      <- engine core: input, VehicleController, base behaviours
   └─ <Mod>/.../SampleCar_01_Base.et           <- per-vehicle CONFIG (this is the "real" work)
        └─ SampleCar_01.et / _white.et          <- thin colour/variant children (ID only)
```

A real vehicle Base inherits `Wheeled_Car_Base.et` and then **adds/overrides ~17 components**.
The thin child (`SampleCar_01.et`, 490 B) only sets an `ID`. **The RVC generator currently
inherits `SampleCar_01_Base` and overrides only 5 things — so it either inherits SampleCar's
lights/doors/sounds (wrong vehicle) or they read as "missing".** The fix is to inherit
`Wheeled_Car_Base.et` and author the per-vehicle components below, OR inherit `SampleCar_01_Base`
and override every resource/pivot to point at the new vehicle.

---

## 2. Full component checklist (SampleCar_01_Base)

| # | Component | Purpose | Per-vehicle data it needs |
|---|---|---|---|
| 1 | `SCR_VehicleSoundComponent` | engine/horn/damper/crash sounds + per-wheel sound points | `.acp` sound banks; `VehicleWheelSound` at each `v_wheel_*` pivot |
| 2 | `BaseLightManagerComponent` | all lights | `LightSlots` (head/hibeam/rear/brake/reverse/hazard/dash `.conf` at `v_light_*` + `ParentSurface`); `EmissiveSurfaceSlots` (the glowing `*_ES_*.et` light prefabs, `LightType`, `EmissiveMultiplier`, `EmissiveColorTint`); `LightAction` user actions |
| 3 | `MeshObject` | body render mesh | `Object "{GUID}…/Veh.xob"` |
| 4 | `RigidBody` | physics body | `Mass` (kg) |
| 5 | `SCR_BaseCompartmentManagerComponent` | doors + seats | `DoorInfoList` (CompartmentDoorInfo per door: contextName, open/close actions, entry/exit pivots, AnimDoorIndex); `CompartmentSlots` (Pilot + Cargo, seat type, passenger pivot `*_idle`, getin pivot) |
| 6 | `SCR_EditableVehicleComponent` | GM/editor entry | Name, Icon, preview, faction, labels |
| 7 | `SCR_FuelManagerComponent` | fuel | `MaxFuel`, `FuelCapPosition` at `v_fuel_cap` |
| 8 | `SCR_ResourceComponent` | supplies | usually a `.ct` template |
| 9 | `SCR_UniversalInventoryStorageComponent` | trunk inventory | size, volume, max weight, slots |
| 10 | `SCR_VehicleDamageManagerComponent` | hit zones + wreck | Hull (flammable + `m_sWreckModel` `_wreck.xob`); Engine/Gearbox/FuelTank/Battery hit zones each bound to a **`UCX_FG_*` collider name**; `m_fVehicleDestroyDamage` |
| 11 | `SCR_VehicleFactionAffiliationComponent` | faction | `"CIV"` / `"US"` / `"USSR"` etc. |
| 12 | `VehicleWheeledSimulation` | **the drive model** | see §3 |
| 13 | `BaseVehicleNodeComponent` | HUD + car controller | `SCR_BaseHUDComponent` (gauge max); `SCR_CarControllerComponent` (AirIntakes, ThrottleCurve, ClutchUncoupleRpm, Latency, Up/DownShiftRpm) |
| 14 | `CarProcAnimComponent` | procedural wheel/suspension/dash anim | `ProcAnimParams` mapping `.pap` to bones: `wheel_suspension.pap`→(`v_wheel`+`v_suspension`+`v_rotator`), `wheel.pap`→`v_wheel`, dashboard.pap→`v_dashboard_*`, trunk.pap→`v_trunk` |
| 15 | `SlotManagerComponent` | mounted parts | glass slots (DST glass at door pivots + `ChildPivotID snap_glass`), `ShadowAO`, **`SCR_WheelSlotInfo` Wheel_L01/L02/R01/R02** (wheel prefab at `v_wheel_*`, `MergePhysics 1`, `m_iWheelIndex`), supply storage |
| 16 | `ActionsManagerComponent` | all interaction contexts | UserActionContexts (doors+`_int`, seats, light_switch, fuel_cap, starter_switch, trunk, handbrake…) + additionalActions (push, engine start, trunk, storage load/unload) |
| 17 | `VehicleAnimationComponent` | anim graph | `AnimGraph` (.agr), `AnimInstance` (Vehicle.asi), `StartNode "VehicleMasterControl"`, `AnimInjection` (Player.asi) |

The RVC generator emits **3, 4, 12 (minimal), 15 (partial), 17** only. Items **1, 2, 5, 6, 7,
9, 10, 13, 14, 16** are the "so much missing" — most come free if you keep the parent config but
must be **re-pointed** to the new vehicle's prefabs/pivots, or authored fresh.

---

## 3. `VehicleWheeledSimulation` — the drive model (§ that the stub gets wrong)

```
VehicleWheeledSimulation "{GUID}" {
 Simulation Wheeled "{GUID}" {
  SolverUpdateRate 275
  Engine Engine Engine { Inertia 0.45 MaxPower 86 MaxTorque 155
                         RpmMaxPower 5800 RpmMaxTorque 4400 Steepness 41 RpmRedline 6500 RpmMax 7000 }
  Clutch Clutch Clutch { MaxClutchTorque 300 }
  Gearbox Gearbox Gearbox { Forward { 3.345 1.944 1.37 1.032 0.805 } Reverse 3.167 Output "Diff_01" }
  Axles {
   Axle "{GUID}" {                         # FRONT (driven here)
    TorqueShare 1
    Differential Differential Diff_01 { Type LSD Ratio 4.25 Strength 0.6
                                        "Anti slip" 3300 "Anti slip torque" 3607.5
                                        Output0 "Wheel_L01" Output1 "Wheel_R01" }
    Suspension Suspension "{GUID}" { SpringRate 35 CompressionDamper 6000 RelaxationDamper 3000
                                     MaxTravelUp 0.08 MaxTravelDown 0.08 }
    Wheel Wheel "{GUID}" { Radius 0.32 Mass 22 BrakeTorque 15000 }
    Tyre  Tyre  "{GUID}" { RollingResistance 0.3 RollingDrag 0.1 Tread 0.3 }
    WheelPositions { WheelPosition Wheel_L01 {} WheelPosition Wheel_R01 {} }
   }
   Axle "{GUID}" { TorqueShare 0 ... WheelPositions { Wheel_L02 Wheel_R02 } }   # REAR
  }
  InertiaOverrideEnabled 1
  InertiaOverride 2500 1300 1400
  Aerodynamics Aerodynamics "{GUID}" { ReferenceArea 0.5 DragCoefficient 0.31 }
  Pacejka Pacejka "{GUID}" : "{…}PacejkaTire_Offroad.conf" { }
 }
}
```

Key rules:
- **`WheelPosition` names (Wheel_L01…) must match the `SCR_WheelSlotInfo` slot names** in
  SlotManagerComponent and the `Differential Output0/Output1` + `Gearbox Output`.
- `TorqueShare` per axle splits engine torque (FWD = front 1/rear 0; RWD = 0/1; AWD = 0.5/0.5).
- `Wheel.Radius` must match the real tyre radius (the RVC measure-from-`wheel_FL` value).
- Drivetrain wiring: `Gearbox.Output -> Diff name`, `Diff.Output0/1 -> WheelPosition names`.
- The RVC stub omits Engine/Clutch/Gearbox/Suspension/Tyre/Aero/Pacejka → vehicle won't drive
  realistically. Inherit them from a Core sim config or author per the table.

---

## 4. Required pivots / bones (skeleton contract)

`v_root, v_body, v_axle_01, v_axle_02, v_wheel_l01/r01/l02/r02, v_suspension_l01/r01/(l02/r02),
v_rotator_l01/r01, v_door_l01/r01/l02/r02, v_trunk, v_steering_wheel, v_pedal_throttle/brake/clutch,
v_handbrake, v_gearshift, v_dashboard_speed/rpm/fuel/coolant_temp, v_light_FL/FR/RL/RR/interior,
v_light_switch/_signal/_hazard_switch, v_starter_switch, v_fuel_cap`.
Memory/empty pivots (not bones): `driver_idle/getIn, codriver_idle/getIn,
passenger{l,r,c}{_idle,_getin}, snap_glass` (on door/trunk children), `v_fx_exhaust`.
These are what the RVC rig (`build_rig` / SampleCar canonical) must create and what every
component above references by `PivotID`.

---

## 5. Slot wiring (SlotManagerComponent)

- **Wheels**: `SCR_WheelSlotInfo Wheel_L01..R02` → wheel prefab `…/VehParts/<Veh>_wheel.et` at
  `v_wheel_*`, `MergePhysics 1`, `DisablePhysicsInteraction 1`, `RegisterDamage 1`, `m_iWheelIndex 0..3`.
  R-side gets `Angles 0 180 0`. **One wheel prefab is reused for all four** (so the RVC wheel
  export only needs one centred wheel — matches the centred-wheel export).
- **Glass (DST)**: `glass_f` on body; `glass_fl/fr/rl/rr` parented `PivotID v_door_*` +
  `ChildPivotID snap_glass`; `glass_r` on `v_trunk`. Prefabs = `…/Dst/<Veh>_glass_*.et`.
- **ShadowAO** on `v_body`; **SupplyStorage** as `RegisteringComponentSlotInfo`.

---

## 6. Lights (BaseLightManagerComponent) — two halves

1. **`LightSlots`** = actual light projectors: `SCR_LightSlot : Light_Head/HiBeam/Rear/Brake/
   Reverse/HazardLeft/HazardRight/Dashboard.conf` with a `LightPositionInfo` at a `v_light_*`
   pivot (Offset/Angles) and `ParentSurface "Light_*"`.
2. **`EmissiveSurfaceSlots`** = the glowing lens prefabs (`<Veh>_ES_*.et`) with `LightType` (bit
   flags: 2=brake-ish, 10/512=head/hibeam, 256=indicator, 18=rear, 32=reverse, 64=brake,
   128=interior), `EmissiveMultiplier`, `EmissiveColorTint`, `RegisterDamage 1`, `LightSide 0/1`.
3. **`LightAction`** = `SCR_Lights{HiBeam,TurnLeft,TurnRight,Hazard,Dashboard,Presence}UserAction`
   bound to `light_switch*` contexts.
The RVC generator currently makes light *prefab stubs* but does not wire the LightManager.

---

## 7. Minimal-but-complete recipe for a NEW vehicle

1. Rig + export per the prep/rigging docs → `<Veh>.xob` (+ `_wheel.xob`, `_glass_*.xob`,
   `_ES_*` light xobs, `_wreck.xob`) with `UCX_MainCol_*` (convex, Vehicle preset),
   `UCL_MT_wheel_*` (MineTrigger), `UCX_FG_Engine/Gearbox/FuelTank/Battery`, `UTM_FG_*`.
2. Author Base prefab inheriting `Wheeled_Car_Base.et` (or copy `SampleCar_01_Base` and
   **re-point every resource GUID + pivot** to the new vehicle).
3. Set: MeshObject.Object, RigidBody.Mass, full VehicleWheeledSimulation (§3 with real radius/
   mass/gearing/torque-share), SlotManager wheels+glass (§5), LightManager (§6),
   CompartmentManager doors+seats, DamageManager hit zones→`UCX_FG_*` + wreck, FuelManager,
   FactionAffiliation, EditableVehicleComponent, ProcAnim bone maps, AnimationComponent (.agr/.asi).
4. Thin child prefab (ID only) for variants.

---

## 8. RVC generator gap → action list
Expand `rvc_core/generator.py` `_base_prefab` to emit (or correctly inherit+repoint): light
manager, compartment manager (doors/seats), damage manager hit zones + wreck, fuel manager,
faction, editable component, car controller + HUD, proc-anim bone maps, and a *full*
VehicleWheeledSimulation. Drive every `PivotID`/slot name from the rig contract in §4–5 and the
measured wheel radius. Keep the inherit-`SampleCar_01_Base` path but add a "repoint to this
vehicle's resources" pass so inherited lights/glass/wheel/sounds aren't SampleCar's.

_Sources: `SampleMod_NewCar/SampleCar_01_Base.et` (full read), `SampleMod_ModdedCar/UAZ469_Modded.et`
(thin override example), bearcat `Explorer_Base.et` (ARGH full vehicle), BI car-creation wiki PDFs
in `bearcat/docs`. CC-BY sample assets — credit Bohemia for sample-derived structure._
