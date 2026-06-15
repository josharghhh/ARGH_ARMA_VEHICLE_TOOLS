from __future__ import annotations

import argparse
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "reference" / "SampleMod_NewCar" / "expected_paths.txt"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--sample-root",
        type=Path,
        default=Path.home() / "Documents" / "My Games" / "ArmaReforgerWorkbench" / "addons" / "SampleMod_NewCar",
    )
    args = parser.parse_args()
    expected = [
        line.strip() for line in MANIFEST.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.startswith("#")
    ]
    missing = [relative for relative in expected if not (args.sample_root / relative).exists()]
    if missing:
        print("Missing official SampleMod_NewCar references:")
        for relative in missing:
            print(f"  {relative}")
        return 1
    print(f"Official SampleMod_NewCar reference is complete: {args.sample_root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
