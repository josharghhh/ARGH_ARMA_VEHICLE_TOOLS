from __future__ import annotations

from pathlib import Path
import tempfile

from rvc_core import VehicleProject, check_project, generate_vehicle_sources
from rvc_core.project_checker import expected_vehicle_layer_preset


def main() -> None:
    assert expected_vehicle_layer_preset("UCX_MainCol_01_Chassis") == "Vehicle"
    assert expected_vehicle_layer_preset("UCL_MT_wheel_L01") == "MineTrigger"
    assert expected_vehicle_layer_preset("UCX_FG_Engine") == "FireGeo"
    assert expected_vehicle_layer_preset("UTM_Glass_FL") == "GlassFire"

    with tempfile.TemporaryDirectory() as temporary:
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
