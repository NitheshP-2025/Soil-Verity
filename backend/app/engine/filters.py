"""Hard rules: remove rotations that cannot work on this farm.

The farmer's CURRENT rotation is never filtered out (it must always be compared),
but generated alternatives must pass every rule.
"""
from __future__ import annotations

from typing import Dict, Optional, Tuple

from .config import EngineConfig
from .models import Crop, Farm, Rotation


def crop_allowed(crop: Crop, season: str, farm: Farm, cfg: EngineConfig) -> Tuple[bool, str]:
    if season not in crop.seasons:
        return False, f"{crop.name} is not sown in {season}"
    if crop.duration_days > cfg.slot_days:
        return False, f"{crop.name} takes too long for one season slot"
    if crop.needs_irrigation and farm.water_source == "rainfed":
        return False, f"{crop.name} needs irrigation and the farm is rainfed"
    if crop.equipment and crop.equipment not in farm.equipment:
        return False, f"{crop.name} needs {crop.equipment}, which the farmer does not have"
    return True, ""


def _last_family(farm: Farm, crops: Dict[str, Crop]) -> Optional[str]:
    if not farm.last_crops:
        return None
    last = crops.get(farm.last_crops[-1])
    return last.family if last else None


def rotation_allowed(rot: Rotation, crops: Dict[str, Crop], farm: Farm,
                     cfg: EngineConfig) -> Tuple[bool, str]:
    prev_family = _last_family(farm, crops)
    fallow_count = 0
    for season, name in zip(rot.seasons, rot.crops):
        crop = crops[name]
        ok, why = crop_allowed(crop, season, farm, cfg)
        if not ok:
            return False, why
        if crop.is_fallow:
            fallow_count += 1
            prev_family = None
            continue
        if prev_family is not None and crop.family == prev_family:
            return False, f"{crop.name} repeats the previous crop family ({prev_family})"
        prev_family = crop.family
    if fallow_count > 1:
        return False, "more than one fallow season"
    return True, ""
