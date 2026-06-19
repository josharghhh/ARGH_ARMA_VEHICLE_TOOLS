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
    forbidden_master_vehiclecomplex_issues,
    repair_vehicle_layer_presets,
    repair_vehicle_surface_properties,
    required_master_collider_issues,
    vehicle_layer_preset_issues,
    vehicle_surface_property_issues,
    wheel_slot_contract_issues,
)
from rvc_core.export_profiles import (
    classify_object_name,
    collider_profile,
    include_in_profile,
    profile_filename,
    slot_from_name,
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

    assert classify_object_name("glass_FL") == "glass"
    assert classify_object_name("Begal_glass_RR") == "glass"
    assert classify_object_name("headlight_L") == "light"
    assert classify_object_name("wheel_FL") == "wheel"
    assert classify_object_name("Steering_Wheel") == "body"
    assert classify_object_name("door_FL") == "door"
    assert include_in_profile("master", "exterior")
    assert include_in_profile("master", "UCX_MainCol_01_Chassis")
    assert include_in_profile("master", "UCX_FG_Engine")
    assert include_in_profile("master", "UCL_MT_wheel_L01")
    assert not include_in_profile("master", "glass_FL")
    assert not include_in_profile("master", "headlight_L")
    assert not include_in_profile("master", "wheel_FL")
    assert not include_in_profile("master", "door_FL")
    assert not include_in_profile("master", "UCL_VC_wheel00")
    assert not include_in_profile("master", "UTM_VC_exterior_body_01")
    assert collider_profile("UTM_VC_exterior_body_01") == "forbidden_master_vehiclecomplex"
    assert include_in_profile("glass", "UTM_Glass")
    assert include_in_profile("light", "UTM_FG_Light_FL")
    assert include_in_profile("wheel", "UCL_VC_wheel00")
    assert slot_from_name("glass_FR") == "FR"
    assert slot_from_name("Begal_Glass_R") == "R"
    assert profile_filename("Begal", "master") == "Begal.fbx"
    assert profile_filename("Begal", "glass", "FL") == "Begal_Glass_FL.fbx"

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

        master_meta = Path(temporary) / "master.xob.meta"
        master_meta.write_text(
            """MetaFileClass {
 Configurations {
  FBXResourceClass PC {
   GeometryParams {
    GeometryParam UTM_VC_exterior_body_01 {
     LayerPreset "VehicleComplex"
     SurfaceProperties {
      "{1950188BB10D20EA}Common/Materials/Game/Metal/metal_5mm.gamemat"
     }
     Mass 0
     Margin 0
    }
    GeometryParam UCL_MT_wheel_L01 {
     LayerPreset "MineTrigger"
     SurfaceProperties {
      "{8F1BCCA995D7FA4B}Common/Materials/Game/rubber_tire.gamemat"
     }
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
        master_text = master_meta.read_text(encoding="utf-8")
        assert forbidden_master_vehiclecomplex_issues(master_text) == ["UTM_VC_exterior_body_01"]
        missing = required_master_collider_issues(master_text)
        assert "UCL_MT_wheel_R01" in missing
        assert "UCX_FG_Engine" in missing

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
        base_prefab = addon / "Prefabs" / "Vehicles" / "Wheeled" / "RVC_VEHICLES" / "TestVehicle_Base.et"
        assert base_prefab.is_file()
        assert not wheel_slot_contract_issues(base_prefab.read_text(encoding="utf-8"))
        assert wheel_slot_contract_issues(
            'SCR_WheelSlotInfo Wheel_R01 { Prefab "{BAD}wheel.et" }'
        )
        report = check_project(project)
        assert not report.blocking

    print("smoke_test: OK")


if __name__ == "__main__":
    main()
