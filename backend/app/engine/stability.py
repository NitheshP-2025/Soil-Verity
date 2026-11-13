"""How often does each option rank first when the evidence is varied?

`totals` has shape (R, V, W): R rotations, V climate variants (rain source x soil-moisture
source x year) and W priority-weight sets. Each (v, w) pair is one "check".
"""
from __future__ import annotations

from typing import Dict, List

import numpy as np

from .config import EngineConfig
from .models import Variant


def label_for(first_in: int, of: int, cfg: EngineConfig) -> str:
    share = first_in / of if of else 0.0
    if share >= cfg.solid_at:
        return "Solid"
    if share >= cfg.mixed_at:
        return "Mixed"
    return "Fragile"


def stability_summary(totals: np.ndarray, variants: List[Variant]) -> Dict:
    R, V, W = totals.shape
    top = totals.argmax(axis=0)                                  # (V, W), ties -> lowest index
    first_in = np.array([(top == r).sum() for r in range(R)])
    order = np.argsort(-totals, axis=0, kind="stable")[:3]       # (3, V, W)
    top3_in = np.array([(order == r).any(axis=0).sum() for r in range(R)])

    by_combo: Dict[str, np.ndarray] = {}
    for combo in sorted({v.combo for v in variants}):
        mask = np.array([v.combo == combo for v in variants])
        sub = top[mask]
        by_combo[combo] = np.array([(sub == r).sum() for r in range(R)])
    return {"first_in": first_in, "top3_in": top3_in, "of": V * W, "by_combo": by_combo}


def source_agreement(base_totals: np.ndarray, variants: List[Variant]) -> Dict:
    """base_totals: (R, V) with the farmer's own weights.

    For each source combination, average over years and find the top rotation.
    The sources 'agree' if every combination picks the same top rotation.
    """
    combos = sorted({v.combo for v in variants})
    tops: Dict[str, int] = {}
    for combo in combos:
        mask = np.array([v.combo == combo for v in variants])
        tops[combo] = int(base_totals[:, mask].mean(axis=1).argmax())
    return {"tops": tops, "agree": len(set(tops.values())) == 1, "n_combos": len(combos)}
