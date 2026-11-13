"""Load the crop knowledge table (owned by Jagadeesh) into Crop objects."""
from __future__ import annotations

import csv
from pathlib import Path
from typing import Dict

from .models import FALLOW, Crop

DEFAULT_CROPS_CSV = Path(__file__).resolve().parents[1] / "knowledge" / "crops.csv"

_TRUE = {"1", "true", "yes", "y", "t"}


def _b(value: str) -> bool:
    return str(value).strip().lower() in _TRUE


def load_crops(path: Path | str = DEFAULT_CROPS_CSV) -> Dict[str, Crop]:
    crops: Dict[str, Crop] = {}
    with open(path, newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            if not row.get("name") or row["name"].startswith("#"):
                continue
            crop = Crop(
                name=row["name"].strip(),
                family=row["family"].strip(),
                seasons=tuple(s.strip() for s in row["seasons"].split("|") if s.strip()),
                duration_days=int(row["duration_days"]),
                water_need_mm=float(row["water_need_mm"]),
                is_legume=_b(row["is_legume"]),
                needs_irrigation=_b(row["needs_irrigation"]),
                equipment=(row.get("equipment") or "").strip() or None,
                cost_level=int(row["cost_level"]),
                labour_level=int(row["labour_level"]),
                market_level=int(row["market_level"]),
                heat_sensitivity=float(row["heat_sensitivity"]),
                drought_sensitivity=float(row["drought_sensitivity"]),
                waterlogging_sensitivity=float(row["waterlogging_sensitivity"]),
                ec_threshold=float(row["ec_threshold"]),
                ph_min=float(row["ph_min"]),
                ph_max=float(row["ph_max"]),
            )
            crops[crop.name] = crop
    crops[FALLOW.name] = FALLOW
    return crops
