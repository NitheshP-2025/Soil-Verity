"""Transparent scoring of one rotation under one climate variant.

Four sub-scores, each 0..1 (higher is better):
  water - does the rotation fit the farm's water (stress and irrigation burden)?
  soil  - nitrogen from legumes, family diversity, soil cover, fit to soil test values
  econ  - cost and market strength
  risk  - exposure to heat, dry spells and waterlogging

The farmer's priority sliders only decide how the four are combined (see pipeline).
"""
from __future__ import annotations

from typing import Dict, List

from .config import EngineConfig
from .models import SEASONS, Components, Crop, Farm, Rotation, SeasonClimate
from .water_balance import irrigation_allowance, season_water

PRIORITY_TO_COMPONENT = {"water": "water", "soil": "soil", "cost": "econ", "risk": "risk"}
COMPONENT_ORDER = ("water", "soil", "econ", "risk")


def season_cycle(start: str, n: int) -> tuple:
    i = SEASONS.index(start)
    return tuple(SEASONS[(i + k) % len(SEASONS)] for k in range(n))


def soil_value(farm: Farm, key: str, cfg: EngineConfig) -> float:
    v = {"ph": farm.soil.ph, "ec": farm.soil.ec, "organic_carbon": farm.soil.organic_carbon}[key]
    return cfg.soil_defaults[key] if v is None else v


def _clip01(x: float) -> float:
    return max(0.0, min(1.0, x))


def _soil_fit(crop: Crop, farm: Farm, cfg: EngineConfig) -> float:
    ec = soil_value(farm, "ec", cfg)
    ph = soil_value(farm, "ph", cfg)
    ec_fit = _clip01(1.0 - max(0.0, ec - crop.ec_threshold) / cfg.ec_decay_dsm)
    gap = max(0.0, crop.ph_min - ph, ph - crop.ph_max)
    ph_fit = _clip01(1.0 - gap * cfg.ph_decay_per_unit)
    return 0.5 * (ec_fit + ph_fit)


def _crop_risk(crop: Crop, sc: SeasonClimate, cfg: EngineConfig) -> float:
    if crop.is_fallow:
        return 0.0
    w = cfg.risk_weights
    heat = crop.heat_sensitivity * min(1.0, sc.heat_days / cfg.heat_ref_days)
    dry = crop.drought_sensitivity * min(1.0, sc.dry_spell_days / cfg.dry_ref_days)
    wet = crop.waterlogging_sensitivity * min(1.0, sc.heavy_rain_days / cfg.heavy_ref_days)
    return w["heat"] * heat + w["dry"] * dry + w["wet"] * wet


def score_rotation(rot: Rotation, crops: Dict[str, Crop], farm: Farm,
                   scs: Dict[str, SeasonClimate], cfg: EngineConfig) -> Components:
    allowance = irrigation_allowance(farm, cfg)
    n = len(rot.crops)

    water_scores: List[float] = []
    risks: List[float] = []
    econs: List[float] = []
    fits: List[float] = []
    stress: Dict[str, bool] = {}
    irrigation_total = 0.0
    bare = 0.0
    legumes = 0
    repeats = 0

    prev_family = None
    if farm.last_crops and farm.last_crops[-1] in crops:
        prev_family = crops[farm.last_crops[-1]].family

    for season, name in zip(rot.seasons, rot.crops):
        crop = crops[name]
        sc = scs[season]
        sw = season_water(crop, sc, allowance, cfg)
        water_scores.append(sw.score)
        stress[season] = sw.stressed
        irrigation_total += sw.irrigation_needed_mm
        risks.append(_crop_risk(crop, sc, cfg))

        if crop.is_fallow:
            econs.append(cfg.fallow_econ)
        else:
            cost_score = 1.0 - (crop.cost_level - 1) / 4.0
            market_score = (crop.market_level - 1) / 4.0
            econs.append(cfg.cost_share * cost_score + (1 - cfg.cost_share) * market_score)

        if crop.is_fallow:
            bare += cfg.slot_months
        else:
            bare += max(0.0, cfg.slot_months - crop.duration_days / 30.0)
            fits.append(_soil_fit(crop, farm, cfg))
            if crop.is_legume:
                legumes += 1
            if prev_family is not None and crop.family == prev_family:
                repeats += 1
        prev_family = None if crop.is_fallow else crop.family

    # soil sub-scores
    oc = soil_value(farm, "organic_carbon", cfg)
    legume_weight = 1.2 if oc < cfg.oc_low else (0.8 if oc > cfg.oc_high else 1.0)
    nitrogen = _clip01(cfg.legume_credit_per_crop * legumes * legume_weight)
    diversity = _clip01(1.0 - repeats / n)
    cover = _clip01(1.0 - bare / (n * cfg.slot_months))
    fit = sum(fits) / len(fits) if fits else 0.5
    sw_ = cfg.soil_weights
    soil = (sw_["nitrogen"] * nitrogen + sw_["diversity"] * diversity
            + sw_["cover"] * cover + sw_["fit"] * fit)

    return Components(
        water=sum(water_scores) / n,
        soil=_clip01(soil),
        econ=sum(econs) / n,
        risk=_clip01(1.0 - sum(risks) / n),
        legume_count=legumes,
        family_repeats=repeats,
        bare_months=round(bare, 2),
        irrigation_needed_mm=irrigation_total,
        stress=stress,
    )


def normalize_priorities(p: Dict[str, float]) -> Dict[str, float]:
    vals = {k: max(0.0, float(p.get(k, 0.0))) for k in PRIORITY_TO_COMPONENT}
    total = sum(vals.values())
    if total <= 0:
        return {k: 1.0 / len(vals) for k in vals}
    return {k: v / total for k, v in vals.items()}


def weight_vector(p: Dict[str, float]) -> List[float]:
    """Normalized weights in COMPONENT_ORDER (water, soil, econ, risk)."""
    n = normalize_priorities(p)
    inv = {v: k for k, v in PRIORITY_TO_COMPONENT.items()}
    return [n[inv[c]] for c in COMPONENT_ORDER]


def light(score: float, cfg: EngineConfig) -> str:
    if score >= cfg.green_at:
        return "green"
    if score >= cfg.yellow_at:
        return "yellow"
    return "red"
