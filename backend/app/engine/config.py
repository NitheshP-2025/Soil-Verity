"""Tunable constants for the decision engine.

EVERY number here is a PLACEHOLDER chosen to make the engine runnable.
They must be reviewed (and sourced) by the agronomy side of the team before the demo.
Keeping them in one place makes that review easy and keeps the scoring transparent.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict


@dataclass(frozen=True)
class EngineConfig:
    # --- rotation structure ---
    cycle_length: int = 3               # seasons per rotation
    slot_days: int = 130                # longest crop duration that fits one season slot
    slot_months: float = 4.0            # months per season slot
    pool_size: int = 30                 # candidates kept for the stability checks
    max_years: int = 15                 # most recent years used for the checks

    # --- water balance ---
    effective_rain_factor: float = 0.8              # share of rain the crop can use
    soil_moisture_storage_mm: float = 100.0         # root-zone wetness 1.0 -> this many mm
    irrigation_mm: Dict[str, float] = field(default_factory=lambda: {
        "canal": 300.0, "borewell": 200.0, "rainfed": 0.0})   # seasonal irrigation allowance
    default_reliability: float = 0.8                # used when the farmer has not said
    irrigation_ref_mm: float = 800.0                # irrigation burden that scores zero
    stress_threshold: float = 0.15                  # unmet need share that counts as water stress
    et0_scale_min: float = 0.8
    et0_scale_max: float = 1.2

    # --- climate risk references (days) ---
    heat_ref_days: float = 15.0
    dry_ref_days: float = 20.0
    heavy_ref_days: float = 8.0
    risk_weights: Dict[str, float] = field(default_factory=lambda: {
        "heat": 0.4, "dry": 0.4, "wet": 0.2})

    # --- soil ---
    soil_defaults: Dict[str, float] = field(default_factory=lambda: {
        "ph": 7.0, "ec": 1.5, "organic_carbon": 0.5})   # used (and flagged) when not provided
    soil_weights: Dict[str, float] = field(default_factory=lambda: {
        "nitrogen": 0.30, "diversity": 0.25, "cover": 0.25, "fit": 0.20})
    legume_credit_per_crop: float = 0.8
    oc_low: float = 0.50                # Soil Health Card style thresholds (% organic carbon)
    oc_high: float = 0.75
    ec_decay_dsm: float = 6.0           # dS/m above threshold at which fit reaches zero
    ph_decay_per_unit: float = 0.25

    # --- economics ---
    cost_share: float = 0.6             # econ = cost_share*cost + (1-cost_share)*market
    fallow_econ: float = 0.15           # a fallow season earns nothing, so it is not rewarded for being cheap

    # --- traffic lights ---
    green_at: float = 0.66
    yellow_at: float = 0.40

    # --- stability labels (share of runs in which an option ranked first) ---
    solid_at: float = 0.80
    mixed_at: float = 0.50
    weight_perturbation: float = 0.20   # +/- change applied to each priority in the checks

    # --- switch-or-stay verdict ---
    verdict_margin: float = 0.02        # best must beat current by this much to count as a win
    switch_win_rate: float = 0.80
    switch_min_gap: float = 0.05
    maybe_win_rate: float = 0.50


DEFAULT_CONFIG = EngineConfig()
