from __future__ import annotations

from pathlib import Path
import shutil
import tempfile


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "addon" / "reforger_vehicle_checker"
TARGET = ROOT / "dist" / "reforger_vehicle_checker.zip"
DOC_TARGET = ROOT / "docs" / "downloads" / TARGET.name


def main() -> None:
    TARGET.parent.mkdir(parents=True, exist_ok=True)
    TARGET.unlink(missing_ok=True)
    with tempfile.TemporaryDirectory() as temporary:
        staging = Path(temporary) / SOURCE.name
        shutil.copytree(
            SOURCE,
            staging,
            ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "*.pyo"),
        )
        archive = shutil.make_archive(
            str(TARGET.with_suffix("")),
            "zip",
            root_dir=staging.parent,
            base_dir=staging.name,
        )
    DOC_TARGET.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(archive, DOC_TARGET)
    print(archive)


if __name__ == "__main__":
    main()
