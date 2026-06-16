from __future__ import annotations

from pathlib import Path
import tempfile

from rvc_core import VehicleProject, check_project, generate_vehicle_sources
from rvc_core.project_checker import (
    FABRIC,
    FIREGEO_METAL,
    LIGHT_PLASTIC,
    THIN_GLASS,
    TIRE_RUBBER_4MM,
    WHEEL_METAL,
    expected_vehicle_layer_preset,
    expected_vehicle_surface_properties,
    repair_vehicle_layer_presets,
    repair_vehicle_surface_properties,
    vehicle_layer_preset_issues,
    vehicle_surface_property_issues,
)
from rvc_core.rig_roles import (
    is_road_wheel_name,
    resolve_target_bone,
)


def main() -> None:
    assert resolve_target_bone("steeringwheel")[2] == "v_steering_wheel"
    assert resolve_target_bone("Steering_Wheel")[2] == "v_steering_wheel"
    assert resolve_target_bone("v_steeringwheel")[2] == "v_steering_wheel"
    assert resolve_target_bone("rotator_l")[2] == "v_rotator_l01"
    assert resolve_target_bone("rotor_FL")[2] == "v_rotator_l01"
    assert resolve_target_bone("rotatorR")[2] == "v_rotator_r01"
    assert resolve_target_bone("v_rotator_l01")[2] == "v_rotator_l01"
    assert resolve_target_bone("wheel_rotator_l01")[2] == "v_rotator_l01"
    assert resolve_target_bone("wheelFR")[2] == "v_wheel_r01"
    assert resolve_target_bone("anything", manual_role="CUSTOM", manual_target="v_test_custom")[2] == "v_test_custom"
    assert not is_road_wheel_name("v_Steering_Wheel")
    assert not is_road_wheel_name("wheel_rotator_l01")
    assert not is_road_wheel_name("front_suspension_l01")
    assert is_road_wheel_name("wheel_FL")

    assert expected_vehicle_layer_preset("UCX_MainCol_01_Chassis") == "Vehicle"
    assert expected_vehicle_layer_preset("UCL_MT_wheel_L01") == "MineTrigger"
    assert expected_vehicle_layer_preset("UCL_VC_wheel00") == "VehicleComplex"
    assert expected_vehicle_layer_preset("UTM_VC_Selected_01") == "VehicleComplex"
    assert expected_vehicle_layer_preset("UCX_FG_Engine") == "FireGeo"
    assert expected_vehicle_layer_preset("UTM_Glass") == "FireGeo"
    assert expected_vehicle_layer_preset("UTM_GlassFire_FL") == "GlassFire"
    assert expected_vehicle_surface_properties("UTM_FG_Wheel_L01") == [
        TIRE_RUBBER_4MM, WHEEL_METAL,
    ]
    assert expected_vehicle_surface_properties("UTM_FG_Wheel_Tire_L01") == [TIRE_RUBBER_4MM]
    assert expected_vehicle_surface_properties("UTM_FG_Wheel_Rim_L01") == [WHEEL_METAL]
    assert expected_vehicle_surface_properties("UTM_VC_exterior_carpaint_body_front_shell_59") == [WHEEL_METAL]
    assert expected_vehicle_surface_properties("UTM_VC_exterior_white_plastic_equip_45") == [LIGHT_PLASTIC]
    assert expected_vehicle_surface_properties("UTM_VC_exterior_int_plastic_24") == [LIGHT_PLASTIC]
    assert expected_vehicle_surface_properties("UTM_VC_exterior_ext_amberlight_equip_38") == [THIN_GLASS]
    assert expected_vehicle_surface_properties("UTM_VC_exterior_int_carpet_52") == [FABRIC]
    assert expected_vehicle_surface_properties("UTM_FG_Body_01") == [FIREGEO_METAL]

    with tempfile.TemporaryDirectory() as temporary:
        meta = Path(temporary) / "colliders.xob.meta"
        meta.write_text(
            """MetaFileClass {
 Configurations {
  FBXResourceClass PC {
   GeometryParams {
    GeometryParam UCL_VC_wheel00 {
     LayerPreset "FireGeo"
     SurfaceProperties {
      "{BAD0000000000000}Common/Materials/Game/metal.gamemat"
     }
     Mass 0
     Margin 0
    }
    GeometryParam UTM_Glass {
     LayerPreset "GlassFire"
     Mass 0
     Margin 0
    }
   }
  }
 }
}
""",
            encoding="utf-8",
        )
        assert vehicle_layer_preset_issues(meta.read_text(encoding="utf-8"))
        assert vehicle_surface_property_issues(meta.read_text(encoding="utf-8"))
        assert repair_vehicle_layer_presets(meta)
        assert repair_vehicle_surface_properties(meta)
        repaired = meta.read_text(encoding="utf-8")
        assert 'LayerPreset "VehicleComplex"' in repaired
        assert 'LayerPreset "FireGeo"' in repaired
        assert TIRE_RUBBER_4MM in repaired

        addon = Path(temporary) / "addon"
        output = addon / "Assets" / "Vehicles" / "Wheeled" / "TestVehicle"
        addon.mkdir()
        (addon / "addon.gproj").touch()
        project = VehicleProject(
            addon_root=str(addon),
            asset_name="TestVehicle",
            output_directory=str(output),
        )
        result = generate_vehicle_sources(project)
        assert result["generated"]
        assert (addon / "Prefabs" / "Vehicles" / "Wheeled" / "RVC_VEHICLES" / "TestVehicle_Base.et").is_file()
        report = check_project(project)
        assert not report.blocking

    print("smoke_test: OK")


if __name__ == "__main__":
    main()
