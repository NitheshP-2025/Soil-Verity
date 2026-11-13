"""Quick manual checks of the SoilVerity engine. Run:  python check.py"""
from app.engine.loader import load_crops
from app.engine.models import SoilTest
from app.engine.pipeline import run_engine
from app.engine.sample_data import build_sample_climate, sample_farm

crops, clim = load_crops(), build_sample_climate()


def run(**kw):
    return run_engine(sample_farm(**kw), crops, clim)


def check(name, ok, detail=""):
    print(("PASS  " if ok else "FAIL  ") + name + (f"   [{detail}]" if detail else ""))


base = run()
check("1. Current rotation is always in the output",
      any(o["is_current"] for o in base["options"]))
check("2. Scores stay between 0 and 1",
      all(0 <= o["mean_score"] <= 1 for o in base["options"]))
check("3. Every option has 360 checks (4 source pairs x 10 years x 9 weight sets)",
      all(o["stability"]["of"] == 360 for o in base["options"]), f"of={base['options'][0]['stability']['of']}")

no_eq = run()
with_eq = run(equipment={"groundnut_digger"})
used = lambda r: any("Groundnut" in o["crops"] for o in r["options"])
check("4. Groundnut needs equipment: absent without it", not used(no_eq))
check("4b. Equipment given: engine can now consider groundnut (candidate count rises)",
      with_eq["meta"]["n_candidates"] > no_eq["meta"]["n_candidates"],
      f"{no_eq['meta']['n_candidates']} -> {with_eq['meta']['n_candidates']}")

rainfed = run(water_source="rainfed")
check("5. Rainfed farm: rice (needs irrigation) is never recommended",
      not any("Rice" in c for o in rainfed["options"] if not o["is_current"] for c in o["crops"]))

known = run(soil=SoilTest(ph=7.0, ec=1.0, organic_carbon=0.5), irrigation_reliability=0.8)
check("6. All inputs known: no decisive check needed", known["decisive_check"] is None)
check("6b. Inputs missing: assumptions are listed", len(base["assumptions"]) >= 3,
      ", ".join(a["input"] for a in base["assumptions"]))

top = base["verdict"]["best"].split(" > ")
same = run(current_rotation=top)
check("7. Current = best rotation: verdict is stay",
      same["verdict"]["decision"] == "stay", same["verdict"]["reason_code"])

again = run()
check("8. Same input twice gives the same answer", base == again)

try:
    run(water_source="river")
    check("9. Bad input is rejected", False)
except ValueError as e:
    check("9. Bad input is rejected with a clear message", True, str(e)[:60])

print("\nTop pick:", base["verdict"]["best"])
print("Verdict :", base["verdict"]["decision"], f"({base['verdict']['reason_code']})")
