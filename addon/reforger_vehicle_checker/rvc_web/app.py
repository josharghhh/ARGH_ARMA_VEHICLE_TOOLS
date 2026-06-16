"""Local browser companion for the Reforger Vehicle Checker.

Rebuilt on the Python standard library (http.server) so it has ZERO external
dependencies (no FastAPI/uvicorn) and can run either:

  * standalone:   python -m rvc_web.app      (cwd = addon folder)
  * in-process:   from .rvc_web import app; app.serve_in_thread()   (inside Blender)

The generate/check endpoints are pure file IO (rvc_core), so they are safe to
serve from a background thread without touching bpy.
"""
from __future__ import annotations

from dataclasses import asdict
import json
import os
from pathlib import Path
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

# Imports must work both as a top-level package (standalone, addon dir on path)
# and as a sub-package of reforger_vehicle_checker (in-process inside Blender).
try:
    from rvc_core import (
        VehicleProject, check_project, discover_addons, generate_vehicle_sources,
    )
    from rvc_core.project_checker import port_open
except ImportError:  # pragma: no cover - exercised inside Blender
    from ..rvc_core import (
        VehicleProject, check_project, discover_addons, generate_vehicle_sources,
    )
    from ..rvc_core.project_checker import port_open


ROOT = Path(__file__).resolve().parent
STATIC = ROOT / "static"
DEFAULT_ADDONS = Path(os.environ.get(
    "RVC_ADDONS_ROOT",
    str(Path.home() / "Documents" / "My Games" / "ArmaReforgerWorkbench" / "addons"),
))
PORT = int(os.environ.get("RVC_WEB_PORT", "8765"))

CONTENT_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".json": "application/json",
    ".png": "image/png",
    ".svg": "image/svg+xml",
    ".ico": "image/x-icon",
}


def _status() -> dict[str, object]:
    return {
        "blender_mcp": port_open(9876),
        "addons_root": str(DEFAULT_ADDONS),
        "local_only": True,
    }


class _Handler(BaseHTTPRequestHandler):
    server_version = "RVCWeb/1.0"

    def log_message(self, *_args):  # keep Blender console quiet
        pass

    def _send(self, code, payload, ctype="application/json"):
        if isinstance(payload, (bytes, bytearray)):
            data = bytes(payload)
        elif ctype.startswith("application/json"):
            data = json.dumps(payload).encode("utf-8")
        else:
            data = str(payload).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        try:
            self.wfile.write(data)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def _static(self, rel):
        target = (STATIC / rel).resolve()
        if STATIC.resolve() not in target.parents or not target.is_file():
            self._send(404, {"error": "not found"})
            return
        self._send(200, target.read_bytes(),
                   CONTENT_TYPES.get(target.suffix.lower(), "application/octet-stream"))

    def do_GET(self):
        url = urlparse(self.path)
        if url.path in ("/", "/index.html"):
            self._static("index.html")
        elif url.path == "/api/status":
            self._send(200, _status())
        elif url.path == "/api/addons":
            root = parse_qs(url.query).get("root", [str(DEFAULT_ADDONS)])[0]
            self._send(200, discover_addons(root))
        elif url.path.startswith("/static/"):
            self._static(url.path[len("/static/"):])
        else:
            self._send(404, {"error": "not found"})

    def do_POST(self):
        url = urlparse(self.path)
        length = int(self.headers.get("Content-Length", "0") or 0)
        raw = self.rfile.read(length) if length else b"{}"
        try:
            payload = json.loads(raw or b"{}")
        except Exception as exc:
            self._send(400, {"error": f"invalid JSON: {exc}"})
            return
        try:
            if url.path == "/api/check":
                project = VehicleProject(**payload)
                report = check_project(project)
                report.save(Path(project.output_directory) / "vehicle_check_report.json")
                self._send(200, {
                    "asset_name": report.asset_name,
                    "blocking_count": len(report.blocking),
                    "issues": [asdict(issue) for issue in report.issues],
                    "facts": report.facts,
                })
            elif url.path == "/api/generate":
                self._send(200, generate_vehicle_sources(VehicleProject(**payload)))
            else:
                self._send(404, {"error": "not found"})
        except Exception as exc:
            self._send(400, {"error": str(exc)})


_server = None


def serve(port=PORT, open_browser=True):
    """Run the server (blocking). If the port is already serving, just open the browser."""
    global _server
    url = f"http://127.0.0.1:{port}"
    if port_open(port):
        if open_browser:
            webbrowser.open(url)
        return None
    httpd = ThreadingHTTPServer(("127.0.0.1", port), _Handler)
    _server = httpd
    if open_browser:
        threading.Timer(0.6, lambda: webbrowser.open(url)).start()
    httpd.serve_forever()
    return httpd


def serve_in_thread(port=PORT, open_browser=True):
    """Start the server on a daemon thread (for in-process use inside Blender)."""
    url = f"http://127.0.0.1:{port}"
    if port_open(port):
        if open_browser:
            webbrowser.open(url)
        return None
    thread = threading.Thread(target=lambda: serve(port, open_browser), daemon=True)
    thread.start()
    return thread


def main():
    serve(PORT, True)


if __name__ == "__main__":
    main()
