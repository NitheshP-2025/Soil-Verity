"""Run the engine on synthetic data and print a readable summary.

    cd backend && python -m app.engine.demo
"""
from __future__ import annotations

import json
import sys

from .loader import load_crops
from .pipeline import run_engine
from .sample_data import build_sample_climate, sample_farm


def main(out_path: str | None = None) -> None:
    result = run_engine(sample_farm(), load_crops(), build_sample_climate())
    v = result["verdict"]
    print(f"Candidates: {result['meta']['n_candidates']}  |  checks per option: "
          f"{result['meta']['checks_per_option']}  |  sources: {result['meta']['sources']}\n")
    for o in result["options"]:
        s = o["stability"]
        tag = " (current)" if o["is_current"] else ""
        print(f"#{o['rank']} {o['name']}{tag}\n"
              f"   score {o['mean_score']:.3f}  lights {o['lights']}\n"
              f"   first in {s['first_in']} of {s['of']} checks -> {s['label']}")
    print(f"\nVerdict: {v['decision'].upper()} ({v['reason_code']}), "
          f"win rate {v['win_rate']}, median gap {v['median_gap']}")
    print(f"Sources agree on top pick: {result['source_agreement']['agree']}")
    print(f"Decisive check: {result['decisive_check']}")
    if out_path:
        with open(out_path, "w", encoding="utf-8") as fh:
            json.dump(result, fh, indent=2)
        print(f"\nWrote {out_path}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else None)
