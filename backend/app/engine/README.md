# SoilVerity decision engine (Nithesh)

Takes a farm, a crop table and climate data and returns the ranked rotations plus the three trust checks.
Pure Python + numpy. No machine learning. Runs in about 1 second.

## Run it

    cd backend
    pip install numpy pytest
    python -m app.engine.demo                      # prints a summary on synthetic data
    python -m app.engine.demo out.json             # also writes the full result JSON
    python -m pytest -q                            # 24 tests

## Use it from the API (Swetha)

    from app.engine.loader import load_crops
    from app.engine.pipeline import run_engine
    result = run_engine(farm, load_crops(), climate)     # -> JSON-serializable dict

`farm` is `models.Farm`, `climate` is `models.ClimateData`. See `contracts/engine_output_sample.json`
for the output shape (synthetic values).

## What the other modules must provide

| From | What |
|---|---|
| Bala (data) | `ClimateData`: per source, per year, per season: rainfall mm, heavy-rain days, longest dry spell, root-zone soil moisture (0..1), ET0 mm, heat days. At least two rainfall sources and two soil-moisture sources, otherwise the source-agreement check is reported as not comparable. |
| Jagadeesh (knowledge) | `knowledge/crops.csv` with reviewed values. The current file is PLACEHOLDER data. |
| Sriram (frontend) | Use `options[].lights`, `stability`, `facts.shortage_share_by_season`, `verdict`, `decisive_check`, `assumptions`. |

## The three trust checks

1. **Source agreement**: every option is scored under each rainfall x soil-moisture source pair, each historical
   year and 9 priority-weight sets. `stability.first_in` / `of` is how often the option ranked first.
   `source_agreement.agree` says whether every source pair picks the same top rotation.
2. **Switch or stay** (`verdict`): best option vs the farmer's current rotation across all climate variants.
   `switch` needs a win rate >= 0.8, a median gap >= 0.05 and agreeing sources.
3. **Decisive check**: for each missing input (EC, pH, organic carbon, irrigation reliability) the ranking is re-run
   with a low and a high value. If the top option changes, that input is reported.

## Known limits (be honest about these in the demo)

- Every number in `config.py` and `knowledge/crops.csv` is a placeholder and must be reviewed and sourced.
- Climate is seasonal, so shortages are reported per season, not per month.
- Traffic lights are averages over three seasons and can hide one stressed season. Show `shortage_share_by_season` too.
- Scores compare options on one farm. They are not yield or income forecasts.
- Stability counts depend on how different the sources really are. The sample data is synthetic.
