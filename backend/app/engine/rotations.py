"""Generate candidate rotations from the crop table and the hard rules."""
from __future__ import annotations

from itertools import product
from typing import Dict, List

from .config import EngineConfig
from .filters import crop_allowed, rotation_allowed
from .models import Crop, Farm, Rotation
from .scoring import season_cycle


def generate_candidates(crops: Dict[str, Crop], farm: Farm, cfg: EngineConfig) -> List[Rotation]:
    seasons = season_cycle(farm.start_season, cfg.cycle_length)
    per_season = []
    for s in seasons:
        options = [c.name for c in crops.values() if crop_allowed(c, s, farm, cfg)[0]]
        per_season.append(sorted(options))      # sorted -> deterministic order
    out: List[Rotation] = []
    for combo in product(*per_season):
        rot = Rotation(seasons=seasons, crops=tuple(combo))
        if rotation_allowed(rot, crops, farm, cfg)[0]:
            out.append(rot)
    return out
