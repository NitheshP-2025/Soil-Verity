"""Tiny stdlib web server joining the SoilVerity UI and decision engine.

Run from the repository root: python backend/server.py
The UI is served at http://localhost:8000 and the API at /api/*.
"""
from __future__ import annotations

import json
import sys
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
UI = ROOT / "TerraLoop"
sys.path.insert(0, str(ROOT / "backend"))

from app.engine.loader import load_crops  # noqa: E402
from app.engine.models import SoilTest  # noqa: E402
from app.engine.pipeline import run_engine  # noqa: E402
from app.engine.sample_data import build_sample_climate, sample_farm  # noqa: E402

CROPS = load_crops()
CLIMATE = build_sample_climate()


class SoilVerityHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(UI), **kwargs)

    def do_GET(self):
        if self.path == "/api/health":
            return self.send_json(200, {"ok": True, "mode": "synthetic demo data"})
        if self.path == "/api/crops":
            return self.send_json(200, {"crops": sorted(CROPS)})
        if self.path == "/":
            self.path = "/index.html"
        return super().do_GET()

    def do_POST(self):
        if self.path != "/api/recommendations":
            return self.send_json(404, {"error": "Not found"})
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length <= 0 or length > 100_000:
                return self.send_json(400, {"error": "Please submit farm details."})
            payload = json.loads(self.rfile.read(length))
            rotation = payload.get("current_rotation", [])
            if not isinstance(rotation, list) or len(rotation) != 3:
                return self.send_json(400, {"error": "Choose a crop for each of the three seasons."})
            soil_data = payload.get("soil", {})
            farm = sample_farm(
                water_source=payload.get("water_source", "borewell"),
                start_season=payload.get("start_season", "kharif"),
                current_rotation=rotation,
                last_crops=[c for c in rotation if c != "Fallow"][-2:],
                soil=SoilTest(
                    ph=self.optional_number(soil_data.get("ph")),
                    ec=self.optional_number(soil_data.get("ec")),
                    organic_carbon=self.optional_number(soil_data.get("organic_carbon")),
                ),
                priorities={
                    "water": float(payload.get("priorities", {}).get("water", 3)),
                    "soil": float(payload.get("priorities", {}).get("soil", 3)),
                    "cost": float(payload.get("priorities", {}).get("cost", 3)),
                    "risk": float(payload.get("priorities", {}).get("risk", 3)),
                },
            )
            result = run_engine(farm, CROPS, CLIMATE)
            result["demo_notice"] = (
                "Demo only: climate is synthetic, crop knowledge and engine settings are placeholders. "
                "This is not a real NASA feed, yield forecast, or agronomic prescription."
            )
            return self.send_json(200, result)
        except (ValueError, TypeError, KeyError, json.JSONDecodeError) as exc:
            return self.send_json(400, {"error": str(exc)})
        except Exception as exc:
            return self.send_json(500, {"error": f"Recommendation failed: {exc}"})

    @staticmethod
    def optional_number(value):
        if value is None or value == "":
            return None
        return float(value)

    def send_json(self, status, body):
        encoded = json.dumps(body).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(encoded)


def main():
    server = ThreadingHTTPServer(("127.0.0.1", 8000), SoilVerityHandler)
    print("SoilVerity is running at http://localhost:8000 (Ctrl+C to stop)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping SoilVerity.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
