"""SYNTHETIC climate data for development and tests. Not real NASA data.

Replace with the real pipeline output (Bala's data layer). The synthetic IMERG-like rainfall is
made slightly drier and noisier than the POWER-like rainfall so source disagreement is visible.
"""
from __future__ import annotations

import numpy as np

from .models import SEASONS, ClimateData, Farm, RainStats, SoilTest, WeatherStats

# season: (rain mean, rain sd, heavy days mean, dry spell mean, et0 mean, heat days mean, soil moisture)
_BASE = {
    "kharif": (380, 100, 4, 12, 480, 18, 0.34),
    "rabi":   (520, 150, 8,  8, 380,  3, 0.42),
    "summer": (130,  60, 1, 25, 560, 35, 0.22),
}


def build_sample_climate(first_year: int = 2016, last_year: int = 2025, seed: int = 7) -> ClimateData:
    rng = np.random.default_rng(seed)
    years = range(first_year, last_year + 1)
    rain = {"power": {}, "imerg": {}}
    sm = {"smap": {}, "merra2": {}}
    weather = {}
    for y in years:
        for d in (rain["power"], rain["imerg"], sm["smap"], sm["merra2"], weather):
            d[y] = {}
        for s in SEASONS:
            rm, rsd, hv, dry, et0, heat, smm = _BASE[s]
            r_true = max(20.0, rng.normal(rm, rsd))
            h_true = max(0.0, rng.normal(hv, 1.5))
            d_true = max(2.0, rng.normal(dry, 4))
            rain["power"][y][s] = RainStats(round(r_true, 1), round(h_true, 1), round(d_true, 1))
            # imerg-like: drier on average and noisier
            r_i = max(15.0, r_true * 0.9 + rng.normal(0, rsd * 0.25))
            rain["imerg"][y][s] = RainStats(round(r_i, 1), round(max(0.0, h_true * 0.9), 1),
                                            round(d_true * 1.1, 1))
            sm_true = float(np.clip(rng.normal(smm, 0.06) + (r_true - rm) / (rm * 8), 0.05, 0.9))
            sm["smap"][y][s] = round(sm_true, 3)
            sm["merra2"][y][s] = round(float(np.clip(sm_true + 0.05 + rng.normal(0, 0.03), 0.05, 0.9)), 3)
            weather[y][s] = WeatherStats(round(et0 * rng.normal(1.0, 0.04), 1),
                                         round(max(0.0, rng.normal(heat, 4)), 1))
    return ClimateData(rain=rain, soil_moisture=sm, weather=weather)


def sample_farm(**overrides) -> Farm:
    """A made-up delta-district farm: rice, rice, fallow every year, borewell water."""
    base = dict(
        water_source="borewell",
        start_season="kharif",
        current_rotation=["Rice (short duration)", "Rice (short duration)", "Fallow"],
        last_crops=["Rice (short duration)", "Fallow"],
        soil=SoilTest(ph=None, ec=None, organic_carbon=0.4),
        priorities={"water": 4, "soil": 4, "cost": 2, "risk": 2},
        equipment=set(),
        irrigation_reliability=None,
    )
    base.update(overrides)
    return Farm(**base)
