"""Decisive check: which MISSING input would change the top recommendation?

For each input the farmer did not provide, re-run the ranking with a plausible low and a
plausible high value. If the top rotation changes, getting that value measured is the most
useful next step.
"""
from __future__ import annotations

from dataclasses import replace
from typing import Callable, Dict, List, Optional

import numpy as np

from .models import Farm

# (key, label for the farmer, plausible low, plausible high)
TESTS = [
    ("soil_ec", "Soil salinity (EC) test", 0.8, 5.0),
    ("soil_ph", "Soil pH test", 5.8, 8.6),
    ("organic_carbon", "Soil organic carbon test", 0.3, 0.9),
    ("irrigation_reliability", "How reliable your irrigation water will be", 0.4, 1.0),
]


def unknown_inputs(farm: Farm) -> List[str]:
    out = []
    if farm.soil.ec is None:
        out.append("soil_ec")
    if farm.soil.ph is None:
        out.append("soil_ph")
    if farm.soil.organic_carbon is None:
        out.append("organic_carbon")
    if farm.irrigation_reliability is None:
        out.append("irrigation_reliability")
    return out


def apply_value(farm: Farm, key: str, value: float) -> Farm:
    if key == "soil_ec":
        return replace(farm, soil=replace(farm.soil, ec=value))
    if key == "soil_ph":
        return replace(farm, soil=replace(farm.soil, ph=value))
    if key == "organic_carbon":
        return replace(farm, soil=replace(farm.soil, organic_carbon=value))
    if key == "irrigation_reliability":
        return replace(farm, irrigation_reliability=value)
    raise KeyError(key)


def find_decisive(farm: Farm, evaluate: Callable[[Farm], np.ndarray], base_w: np.ndarray,
                  baseline_top: int, names: List[str]) -> Optional[Dict]:
    """evaluate(farm) -> array (4, R, V). Returns the most decisive missing input, or None."""
    best = None
    for order, (key, label, low, high) in enumerate(TESTS):
        if key not in unknown_inputs(farm):
            continue
        tops = {}
        for tag, val in (("low", low), ("high", high)):
            arr = evaluate(apply_value(farm, key, val))
            mean_total = np.einsum("krv,k->rv", arr, base_w).mean(axis=1)
            tops[tag] = int(mean_total.argmax())
        changed = {t: i for t, i in tops.items() if i != baseline_top}
        if not changed:
            continue
        candidate = {
            "input": key,
            "label": label,
            "tested_values": {"low": low, "high": high},
            "top_if_low": names[tops["low"]],
            "top_if_high": names[tops["high"]],
            "n_changes": len(changed),
            "order": order,
        }
        if best is None or (candidate["n_changes"], -candidate["order"]) > (best["n_changes"], -best["order"]):
            best = candidate
    if best:
        best.pop("order")
    return best
