"""Tests for the SoilVerity decision engine (run: cd backend && python -m pytest -q)."""
import json
from dataclasses import replace

import numpy as np
import pytest

from app.engine.config import DEFAULT_CONFIG as CFG
from app.engine.decisive import apply_value, unknown_inputs
from app.engine.filters import rotation_allowed
from app.engine.loader import load_crops
from app.engine.models import RainStats, Rotation, SeasonClimate, SoilTest, Variant
from app.engine.pipeline import run_engine
from app.engine.rotations import generate_candidates
from app.engine.sample_data import build_sample_climate, sample_farm
from app.engine.scoring import score_rotation, season_cycle
from app.engine.stability import label_for, stability_summary
from app.engine.verdict import decide

CROPS = load_crops()
RICE, BG, SESAME = "Rice (short duration)", "Black gram", "Sesame"


def climate_dict(rain=400.0, dry=10.0, heavy=3.0, sm=0.35, heat=10.0):
    sc = SeasonClimate(rain_mm=rain, heavy_rain_days=heavy, dry_spell_days=dry,
                       soil_moisture=sm, et0_mm=450.0, et0_mean=450.0, heat_days=heat)
    return {s: sc for s in ("kharif", "rabi", "summer")}


def rot(*crops, start="kharif"):
    return Rotation(season_cycle(start, len(crops)), tuple(crops))


# ---------------- hard rules ----------------

def test_candidates_follow_rules():
    farm = sample_farm()
    cands = generate_candidates(CROPS, farm, CFG)
    assert cands
    for r in cands:
        ok, why = rotation_allowed(r, CROPS, farm, CFG)
        assert ok, why
        assert r.crops.count("Fallow") <= 1


def test_equipment_filter():
    no_equip = generate_candidates(CROPS, sample_farm(equipment=set()), CFG)
    with_equip = generate_candidates(CROPS, sample_farm(equipment={"groundnut_digger"}), CFG)
    assert not any("Groundnut" in r.crops for r in no_equip)
    assert any("Groundnut" in r.crops for r in with_equip)


def test_rainfed_farm_excludes_irrigated_crops():
    cands = generate_candidates(CROPS, sample_farm(water_source="rainfed"), CFG)
    assert cands
    assert not any(RICE in r.crops for r in cands)


def test_current_rotation_always_compared_even_if_it_breaks_rules():
    result = run_engine(sample_farm(), CROPS, build_sample_climate())
    current = [o for o in result["options"] if o["is_current"]]
    assert len(current) == 1
    assert current[0]["crops"] == [RICE, RICE, "Fallow"]    # repeats a family: still evaluated


# ---------------- scoring ----------------

def test_scores_are_bounded():
    result = run_engine(sample_farm(), CROPS, build_sample_climate())
    for o in result["options"]:
        assert 0 <= o["mean_score"] <= 1
        assert all(0 <= v <= 1 for v in o["scores"].values())


def test_more_rain_improves_water_score():
    farm = sample_farm()
    r = rot(RICE, BG, SESAME)
    dry = score_rotation(r, CROPS, farm, climate_dict(rain=150), CFG)
    wet = score_rotation(r, CROPS, farm, climate_dict(rain=700), CFG)
    assert wet.water > dry.water


def test_legume_rotation_scores_better_soil_than_monoculture():
    farm = sample_farm()
    legume = score_rotation(rot(RICE, BG, SESAME), CROPS, farm, climate_dict(), CFG)
    mono = score_rotation(rot(RICE, RICE, "Fallow"), CROPS, farm, climate_dict(), CFG)
    assert legume.soil > mono.soil
    assert legume.legume_count == 1 and mono.family_repeats == 1


def test_high_salinity_lowers_soil_score_for_sensitive_crop():
    r = rot(RICE, BG, SESAME)
    low = score_rotation(r, CROPS, sample_farm(soil=SoilTest(ec=0.5, ph=7.0, organic_carbon=0.5)),
                         climate_dict(), CFG)
    high = score_rotation(r, CROPS, sample_farm(soil=SoilTest(ec=6.0, ph=7.0, organic_carbon=0.5)),
                          climate_dict(), CFG)
    assert high.soil < low.soil


def test_fallow_is_not_rewarded_as_income():
    farm = sample_farm()
    cropped = score_rotation(rot(RICE, BG, SESAME), CROPS, farm, climate_dict(), CFG)
    fallowed = score_rotation(rot("Fallow", BG, SESAME), CROPS, farm, climate_dict(), CFG)
    assert fallowed.bare_months > cropped.bare_months
    # replacing even the lowest-margin crop (rice) with fallow must lower the economic score,
    # because a fallow season earns nothing
    assert fallowed.econ < cropped.econ


# ---------------- trust checks ----------------

def test_stability_counts_and_labels():
    totals = np.array([[[0.9], [0.8], [0.4]],
                       [[0.5], [0.6], [0.7]]])           # (R=2, V=3, W=1)
    variants = [Variant("a", "x", 2020), Variant("a", "x", 2021), Variant("b", "x", 2020)]
    s = stability_summary(totals, variants)
    assert list(s["first_in"]) == [2, 1] and s["of"] == 3
    assert list(s["by_combo"]["a+x"]) == [2, 0]
    assert label_for(9, 10, CFG) == "Solid"
    assert label_for(6, 10, CFG) == "Mixed"
    assert label_for(2, 10, CFG) == "Fragile"


def test_verdict_rules():
    strong = np.full(40, 0.2)
    assert decide(strong, False, True, CFG)["decision"] == "switch"
    assert decide(strong, False, False, CFG)["reason_code"] == "sources_disagree"
    assert decide(strong, True, True, CFG)["reason_code"] == "current_is_best"
    leaning = np.concatenate([np.full(24, 0.1), np.full(16, -0.1)])      # wins 60%
    assert decide(leaning, False, True, CFG)["decision"] == "maybe"
    tiny = np.full(40, 0.005)
    v = decide(tiny, False, True, CFG)
    assert v["decision"] == "stay" and v["reason_code"] == "not_enough_evidence"


def test_stay_when_current_rotation_is_already_best():
    first = run_engine(sample_farm(), CROPS, build_sample_climate())
    top = first["verdict"]["best"].split(" > ")
    result = run_engine(sample_farm(current_rotation=top, last_crops=["Rice (short duration)", "Fallow"]),
                        CROPS, build_sample_climate())
    assert result["verdict"]["decision"] == "stay"
    assert result["verdict"]["reason_code"] == "current_is_best"


def test_strongly_disagreeing_sources_are_detected_and_downgrade_verdict():
    clim = build_sample_climate()
    for src, f in (("imerg", 0.6), ("power", 1.4)):
        for y in clim.rain[src]:
            for s, r in clim.rain[src][y].items():
                clim.rain[src][y][s] = RainStats(r.rain_mm * f, r.heavy_rain_days, r.dry_spell_days)
    result = run_engine(sample_farm(priorities={"water": 4, "soil": 4, "cost": 2, "risk": 2}),
                        CROPS, clim)
    assert result["source_agreement"]["agree"] is False
    assert result["verdict"]["decision"] != "switch"
    assert result["verdict"]["reason_code"] in ("sources_disagree", "leans_switch", "not_enough_evidence")


def test_single_source_is_not_called_comparable():
    clim = build_sample_climate()
    clim.rain.pop("imerg")
    clim.soil_moisture.pop("merra2")
    result = run_engine(sample_farm(), CROPS, clim)
    assert result["source_agreement"]["comparable"] is False


# ---------------- decisive check ----------------

def test_no_decisive_check_when_every_input_is_known():
    farm = sample_farm(soil=SoilTest(ph=7.0, ec=1.0, organic_carbon=0.5), irrigation_reliability=0.8)
    assert unknown_inputs(farm) == []
    assert run_engine(farm, CROPS, build_sample_climate())["decisive_check"] is None


def test_decisive_check_structure_and_assumptions():
    result = run_engine(sample_farm(), CROPS, build_sample_climate())
    d = result["decisive_check"]
    if d is not None:
        assert {"input", "label", "tested_values", "top_if_low", "top_if_high"} <= set(d)
        assert d["top_if_low"] != d["top_if_high"] or d["n_changes"] >= 1
    assumed = {a["input"] for a in result["assumptions"]}
    assert {"soil_ec", "soil_ph", "irrigation_reliability"} <= assumed


def test_apply_value_does_not_mutate_original():
    farm = sample_farm()
    new = apply_value(farm, "soil_ec", 4.0)
    assert new.soil.ec == 4.0 and farm.soil.ec is None


# ---------------- plumbing ----------------

def test_output_is_deterministic_and_json_serializable():
    a = run_engine(sample_farm(), CROPS, build_sample_climate())
    b = run_engine(sample_farm(), CROPS, build_sample_climate())
    assert json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)


@pytest.mark.parametrize("change", [
    {"water_source": "river"},
    {"start_season": "winter"},
    {"current_rotation": [RICE, RICE]},
    {"current_rotation": [RICE, "Wheat", "Fallow"]},
    {"priorities": {"water": 3, "soil": 3, "cost": 3}},
    {"irrigation_reliability": 1.5},
])
def test_invalid_input_is_rejected_with_clear_error(change):
    with pytest.raises(ValueError):
        run_engine(sample_farm(**change), CROPS, build_sample_climate())
