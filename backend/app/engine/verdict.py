"""Switch-or-stay verdict: is the best option clearly better than what the farmer does now?"""
from __future__ import annotations

from typing import Dict

import numpy as np

from .config import EngineConfig


def decide(diffs: np.ndarray, current_is_best: bool, sources_agree: bool,
           cfg: EngineConfig) -> Dict:
    """diffs: best-minus-current score in every climate variant (farmer's own weights)."""
    if current_is_best:
        return {"decision": "stay", "reason_code": "current_is_best",
                "win_rate": 0.0, "median_gap": 0.0}

    win_rate = float((diffs > cfg.verdict_margin).mean())
    median_gap = float(np.median(diffs))

    if win_rate >= cfg.switch_win_rate and median_gap >= cfg.switch_min_gap:
        if sources_agree:
            decision, code = "switch", "clear_advantage"
        else:
            decision, code = "maybe", "sources_disagree"
    elif win_rate >= cfg.maybe_win_rate:
        decision, code = "maybe", "leans_switch"
    else:
        decision, code = "stay", "not_enough_evidence"
    return {"decision": decision, "reason_code": code,
            "win_rate": round(win_rate, 3), "median_gap": round(median_gap, 4)}
