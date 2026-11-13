"""Simple seasonal water balance: how much irrigation does a crop need, and can the farm supply it?

This is deliberately simple and transparent (a comparison tool, not a crop model):

    need         = crop water need, scaled by how hot/dry the season's ET0 is vs normal
    natural      = effective rain + a buffer from root-zone soil moisture
    irrigation   = what the crop needs on top of natural supply
    unmet        = irrigation needed beyond what the farm's water source can supply
"""
from __future__ import annotations

from dataclasses import dataclass

from .config import EngineConfig
from .models import Crop, Farm, SeasonClimate


@dataclass(frozen=True)
class SeasonWater:
    need_mm: float
    irrigation_needed_mm: float
    unmet_mm: float
    score: float          # 0..1, higher is better
    stressed: bool


def irrigation_allowance(farm: Farm, cfg: EngineConfig) -> float:
    base = cfg.irrigation_mm[farm.water_source]
    rel = farm.irrigation_reliability
    if rel is None:
        rel = cfg.default_reliability
    return base * max(0.0, min(1.0, rel))


def season_water(crop: Crop, sc: SeasonClimate, allowance_mm: float,
                 cfg: EngineConfig) -> SeasonWater:
    if crop.is_fallow or crop.water_need_mm <= 0:
        return SeasonWater(0.0, 0.0, 0.0, 1.0, False)

    scale = 1.0
    if sc.et0_mean > 0:
        scale = max(cfg.et0_scale_min, min(cfg.et0_scale_max, sc.et0_mm / sc.et0_mean))
    need = crop.water_need_mm * scale

    natural = cfg.effective_rain_factor * sc.rain_mm + sc.soil_moisture * cfg.soil_moisture_storage_mm
    irrigation_needed = max(0.0, need - natural)
    unmet = max(0.0, irrigation_needed - allowance_mm)

    unmet_share = unmet / need
    burden = min(1.0, irrigation_needed / cfg.irrigation_ref_mm)
    score = 1.0 - (0.5 * unmet_share + 0.5 * burden)
    return SeasonWater(need, irrigation_needed, unmet, max(0.0, min(1.0, score)),
                       unmet_share > cfg.stress_threshold)
