from __future__ import annotations

from pathlib import Path
import shutil
import tempfile


ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT.parent / "Reforger-Vehicle-Tools-source.zip"


def main() -> None:
    TARGET.unlink(missing_ok=True)
    with tempfile.TemporaryDirectory() as temporary:
        staging = Path(temporary) / ROOT.name
        shutil.copytree(
            ROOT,
            staging,
            ignore=shutil.ignore_patterns(
                ".git", "__pycache__", "*.pyc", "*.pyo",
                "Reforger-Vehicle-Tools-source.zip",
            ),
        )
        archive = shutil.make_archive(
            str(TARGET.with_suffix("")),
            "zip",
            root_dir=staging.parent,
            base_dir=staging.name,
        )
    print(archive)


if __name__ == "__main__":
    main()
