from __future__ import annotations

from dataclasses import asdict
import os
from pathlib import Path
import socket
import threading
import webbrowser

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
import uvicorn

from rvc_core import VehicleProject, check_project, discover_addons, generate_vehicle_sources
from rvc_core.project_checker import port_open


ROOT = Path(__file__).resolve().parent
STATIC = ROOT / "static"
DEFAULT_ADDONS = Path(os.environ.get(
    "RVC_ADDONS_ROOT",
    str(Path.home() / "Documents" / "My Games" / "ArmaReforgerWorkbench" / "addons"),
))

app = FastAPI(title="Reforger Vehicle Checker", version="0.1.0")
app.mount("/static", StaticFiles(directory=STATIC), name="static")


@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC / "index.html")


@app.get("/api/status")
def status() -> dict[str, object]:
    return {
        "blender_mcp": port_open(9876),
        "addons_root": str(DEFAULT_ADDONS),
        "local_only": True,
    }


@app.get("/api/addons")
def addons(root: str = str(DEFAULT_ADDONS)) -> list[dict[str, str]]:
    return discover_addons(root)


@app.post("/api/check")
def check(payload: dict[str, object]) -> dict[str, object]:
    try:
        project = VehicleProject(**payload)
        report = check_project(project)
        report.save(Path(project.output_directory) / "vehicle_check_report.json")
        return {
            "asset_name": report.asset_name,
            "blocking_count": len(report.blocking),
            "issues": [asdict(issue) for issue in report.issues],
            "facts": report.facts,
        }
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/generate")
def generate(payload: dict[str, object]) -> dict[str, object]:
    try:
        return generate_vehicle_sources(VehicleProject(**payload))
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


def main() -> None:
    url = "http://127.0.0.1:8765"
    threading.Timer(0.8, lambda: webbrowser.open(url)).start()
    uvicorn.run(app, host="127.0.0.1", port=8765)


if __name__ == "__main__":
    main()
