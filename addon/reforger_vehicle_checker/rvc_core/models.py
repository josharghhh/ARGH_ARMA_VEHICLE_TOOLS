from __future__ import annotations

from dataclasses import asdict, dataclass, field
import json
from pathlib import Path
from typing import Any


@dataclass
class VehicleProject:
    addon_root: str
    asset_name: str
    output_directory: str
    imported_xob_resource: str = ""
    source_blend: str = ""
    template: str = "Explorer"
    template_sources: dict[str, str] = field(default_factory=dict)
    external_wheel_prefab: str = (
        "{B4743DC7327148B1}Prefabs/Vehicles/Wheeled/"
        "BRDM2/VehParts/Wheels/BRDM2_wheel_L01.et"
    )
    legacy_alias: str = ""
    features: dict[str, bool] = field(default_factory=lambda: {
        "doors": True,
        "glass": True,
        "lights": True,
        "emergency_lights": False,
        "animations": True,
    })
    measurements: dict[str, float] = field(default_factory=lambda: {
        "wheelbase": 3.0,
        "wheel_radius": 0.4,
        "track": 2.0,
        "body_height": 1.8,
        "mass": 1800.0,
    })

    @classmethod
    def load(cls, path: str | Path) -> "VehicleProject":
        return cls(**json.loads(Path(path).read_text(encoding="utf-8")))

    def save(self, path: str | Path) -> Path:
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(asdict(self), indent=2) + "\n", encoding="utf-8")
        return target


@dataclass
class CheckIssue:
    rule_id: str
    severity: str
    evidence: str
    safe_fix_available: bool = False
    required_action: str = ""


@dataclass
class CheckReport:
    asset_name: str
    issues: list[CheckIssue] = field(default_factory=list)
    facts: dict[str, Any] = field(default_factory=dict)

    @property
    def blocking(self) -> list[CheckIssue]:
        return [issue for issue in self.issues if issue.severity == "error"]

    def add(
        self,
        rule_id: str,
        severity: str,
        evidence: str,
        safe_fix_available: bool = False,
        required_action: str = "",
    ) -> None:
        self.issues.append(CheckIssue(
            rule_id, severity, evidence, safe_fix_available, required_action
        ))

    def save(self, path: str | Path) -> Path:
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "asset_name": self.asset_name,
            "blocking_count": len(self.blocking),
            "issues": [asdict(issue) for issue in self.issues],
            "facts": self.facts,
        }
        target.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        return target
