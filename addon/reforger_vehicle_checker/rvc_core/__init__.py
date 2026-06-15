"""Shared core for Reforger Vehicle Checker."""

from .models import CheckIssue, CheckReport, VehicleProject
from .project_checker import (
    check_project,
    discover_addons,
    expected_vehicle_layer_preset,
    expected_vehicle_surface_properties,
    repair_vehicle_layer_presets,
    repair_vehicle_surface_properties,
    vehicle_layer_preset_issues,
)
from .generator import generate_vehicle_sources
from .paths import local_path

__all__ = [
    "CheckIssue",
    "CheckReport",
    "VehicleProject",
    "check_project",
    "discover_addons",
    "expected_vehicle_layer_preset",
    "expected_vehicle_surface_properties",
    "generate_vehicle_sources",
    "repair_vehicle_layer_presets",
    "repair_vehicle_surface_properties",
    "vehicle_layer_preset_issues",
]
