from __future__ import annotations

import os
from pathlib import Path
import re


def local_path(value: str | Path) -> Path:
    text = str(value)
    drive = re.match(r"^([A-Za-z]):[\\/](.*)$", text)
    if os.name != "nt" and drive:
        return Path("/mnt") / drive.group(1).lower() / drive.group(2).replace("\\", "/")
    mount = re.match(r"^/mnt/([A-Za-z])/(.*)$", text)
    if os.name == "nt" and mount:
        return Path(f"{mount.group(1).upper()}:\\{mount.group(2).replace('/', '\\')}")
    return Path(text)
