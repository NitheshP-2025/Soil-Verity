"""End-to-end decision engine: farm + crop table + climate data  ->  engine result (dict).

Steps
  1. validate inputs
  2. build climate variants (rain source x soil-moisture source x year)
  3. generate candidate rotations (hard rules), pre-rank on mean climate, keep a pool
  4. score every pool rotation in every variant
  5. stability checks, source agreement, switch-or-stay verdict, decisive check
  6. assemble the result for the API / Rotation Card
"""
from __future__ import annotations

from typing import Dict, List, Tuple

import numpy as np

from .config import DEFAULT_CONFIG, EngineConfig
from .decisive import find_decisive, unknown_inputs
from .models import (FALLOW, SEASONS, ClimateData, Components, Crop, Farm, Rotation,
                     SeasonClimate, Variant)
from .rotations import generate_candidates
from .scoring import (COMPONENT_ORDER, PRIORITY_TO_COMPONENT, light, normalize_priorities,
                      score_rotation, season_cycle, soil_value, weight_vector)
from .stability import label_for, source_agreement, stability_summary
from .verdict import decide


def validate(farm: Farm, crops: Dict[str, Crop], cfg: EngineConfig) -> None:
    if farm.water_source not in cfg.irrigation_mm:
        raise ValueError(f"water_source must be one of {sorted(cfg.irrigation_mm)}")
    if farm.start_season not in SEASONS:
        raise ValueError(f"start_season must be one of {SEASONS}")
    if len(farm.current_rotation) != cfg.cycle_length:
        raise ValueError(f"current_rotation must list {cfg.cycle_length} crops (one per season)")
    for name in farm.current_rotation:
        if name not in crops:
            raise ValueError(f"Unknown crop in current_rotation: {name!r}")
    for k in PRIORITY_TO_COMPONENT:
        if k not in farm.priorities:
            raise ValueError(f"priorities is missing {k!r}")
    if farm.irrigation_reliability is not None and not 0.0 <= farm.irrigation_reliability <= 1.0:
        raise ValueError("irrigation_reliability must be between 0 and 1")


def build_variants(climate: ClimateData, cfg: EngineConfig) -> List[Variant]:
    years = climate.years()[-cfg.max_years:]
    if not years:
        raise ValueError("Climate data has no year covered by every source")
    return [Variant(rs, ss, y)
            for rs in sorted(climate.rain)
            for ss in sorted(climate.soil_moisture)
            for y in years]


def _mean_climate(cache: Dict[Variant, Dict[str, SeasonClimate]]) -> Dict[str, SeasonClimate]:
    out = {}
    for s in SEASONS:
        items = [c[s] for c in cache.values()]
        n = len(items)
        out[s] = SeasonClimate(
            rain_mm=sum(i.rain_mm for i in items) / n,
            heavy_rain_days=sum(i.heavy_rain_days for i in items) / n,
            dry_spell_days=sum(i.dry_spell_days for i in items) / n,
            soil_moisture=sum(i.soil_moisture for i in items) / n,
            et0_mm=sum(i.et0_mm for i in items) / n,
            et0_mean=items[0].et0_mean,
            heat_days=sum(i.heat_days for i in items) / n)
    return out


def _weight_sets(base: List[float], cfg: EngineConfig) -> np.ndarray:
    """Base weights plus each priority raised and lowered by `weight_perturbation`."""
    sets = [list(base)]
    for i in range(len(base)):
        for f in (1 + cfg.weight_perturbation, 1 - cfg.weight_perturbation):
            w = list(base)
            w[i] *= f
            total = sum(w)
            sets.append([x / total for x in w])
    return np.array(sets)          # (W, 4); row 0 is the base weights


def _evaluate(pool: List[Rotation], crops: Dict[str, Crop], farm: Farm,
              variants: List[Variant], cache, cfg: EngineConfig
              ) -> Tuple[np.ndarray, List[List[Components]]]:
    comps: List[List[Components]] = []
    arr = np.zeros((len(COMPONENT_ORDER), len(pool), len(variants)))
    for r, rot in enumerate(pool):
        row = []
        for v, var in enumerate(variants):
            c = score_rotation(rot, crops, farm, cache[var], cfg)
            row.append(c)
            for k, name in enumerate(COMPONENT_ORDER):
                arr[k, r, v] = getattr(c, name)
        comps.append(row)
    return arr, comps


def _assumptions(farm: Farm, cfg: EngineConfig) -> List[Dict]:
    out = []
    labels = {"soil_ec": ("ec", "Soil EC"), "soil_ph": ("ph", "Soil pH"),
              "organic_carbon": ("organic_carbon", "Organic carbon")}
    for key in unknown_inputs(farm):
        if key == "irrigation_reliability":
            out.append({"input": key, "assumed": cfg.default_reliability,
                        "note": "not provided; default share of irrigation allowance assumed"})
        else:
            sk, _ = labels[key]
            out.append({"input": key, "assumed": cfg.soil_defaults[sk],
                        "note": "not provided; district default assumed (low confidence)"})
    return out


def run_engine(farm: Farm, crops: Dict[str, Crop], climate: ClimateData,
               cfg: EngineConfig = DEFAULT_CONFIG) -> Dict:
    validate(farm, crops, cfg)
    seasons = season_cycle(farm.start_season, cfg.cycle_length)
    et0_mean = climate.et0_means()
    variants = build_variants(climate, cfg)
    cache = {v: {s: climate.resolve(v.rain_source, v.soil_moisture_source, v.year, s, et0_mean[s])
                 for s in SEASONS} for v in variants}

    base_w = np.array(weight_vector(farm.priorities))
    current = Rotation(seasons=seasons, crops=tuple(farm.current_rotation))

    # --- candidates: pre-rank on the mean climate, keep a pool, always include current ---
    cands = generate_candidates(crops, farm, cfg)
    mean_sc = _mean_climate(cache)
    pre = []
    for rot in cands:
        c = score_rotation(rot, crops, farm, mean_sc, cfg)
        pre.append((-sum(base_w[i] * getattr(c, n) for i, n in enumerate(COMPONENT_ORDER)),
                    rot.name, rot))
    pre.sort(key=lambda t: (t[0], t[1]))
    pool = [t[2] for t in pre[:cfg.pool_size]]
    if current not in pool:
        pool.append(current)
    names = [r.name for r in pool]
    cur_idx = pool.index(current)

    # --- score everything ---
    arr, comps = _evaluate(pool, crops, farm, variants, cache, cfg)
    W = _weight_sets(list(base_w), cfg)
    totals = np.einsum("krv,wk->rvw", arr, W)               # (R, V, W)
    base_totals = totals[:, :, 0]                            # farmer's own weights, (R, V)
    mean_base = base_totals.mean(axis=1)
    best_idx = int(mean_base.argmax())
    order = [int(i) for i in np.argsort(-mean_base, kind="stable")]

    # --- the trust checks ---
    stab = stability_summary(totals, variants)
    agree = source_agreement(base_totals, variants)
    diffs = base_totals[best_idx] - base_totals[cur_idx]
    verdict = decide(diffs, best_idx == cur_idx, agree["agree"], cfg)
    weights_flip = any(int(totals[:, :, w].mean(axis=1).argmax()) != best_idx
                       for w in range(1, totals.shape[2]))
    decisive = find_decisive(
        farm, lambda f: _evaluate(pool, crops, f, variants, cache, cfg)[0],
        base_w, best_idx, names)

    # --- assemble ---
    shown = order[:3]
    if cur_idx not in shown:
        shown.append(cur_idx)
    options = []
    for rank, r in enumerate(order, start=1):
        if r not in shown:
            continue
        cs = comps[r]
        mean = {n: float(np.mean([getattr(c, n) for c in cs])) for n in COMPONENT_ORDER}
        shortage = {s: round(float(np.mean([c.stress[s] for c in cs])), 3) for s in pool[r].seasons}
        first = int(stab["first_in"][r])
        options.append({
            "name": pool[r].name,
            "crops": list(pool[r].crops),
            "seasons": list(pool[r].seasons),
            "is_current": r == cur_idx,
            "is_top": r == best_idx,
            "rank": rank,
            "mean_score": round(float(mean_base[r]), 4),
            "scores": {k: round(v, 4) for k, v in mean.items()},
            "lights": {"water": light(mean["water"], cfg),
                       "soil": light(mean["soil"], cfg),
                       "cost_risk": light((mean["econ"] + mean["risk"]) / 2, cfg)},
            "facts": {
                "legume_count": cs[0].legume_count,
                "family_repeats": cs[0].family_repeats,
                "bare_months": cs[0].bare_months,
                "irrigation_needed_mm": round(float(np.mean([c.irrigation_needed_mm for c in cs])), 1),
                "shortage_share_by_season": shortage,
            },
            "stability": {
                "first_in": first, "of": stab["of"],
                "top3_in": int(stab["top3_in"][r]),
                "label": label_for(first, stab["of"], cfg),
                "first_in_by_source": {k: int(v[r]) for k, v in stab["by_combo"].items()},
            },
        })

    return {
        "options": options,
        "verdict": {**verdict, "best": names[best_idx], "current": names[cur_idx]},
        "source_agreement": {
            "agree": agree["agree"], "n_combos": agree["n_combos"],
            "comparable": agree["n_combos"] > 1,
            "top_by_source": {k: names[i] for k, i in agree["tops"].items()}},
        "weights_flip_top": bool(weights_flip),
        "decisive_check": decisive,
        "assumptions": _assumptions(farm, cfg),
        "meta": {
            "n_candidates": len(cands), "pool_size": len(pool),
            "n_variants": len(variants), "n_weight_sets": int(W.shape[0]),
            "checks_per_option": int(stab["of"]),
            "top_two_gap": round(float(mean_base[order[0]] - mean_base[order[1]]), 4) if len(order) > 1 else None,
            "years": sorted({v.year for v in variants}),
            "sources": sorted({v.combo for v in variants}),
            "priorities_normalized": {k: round(v, 3)
                                      for k, v in normalize_priorities(farm.priorities).items()},
            "note": "Scores compare options on this farm. They are not yield or income forecasts."},
    }
