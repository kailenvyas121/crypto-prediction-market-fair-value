"""Run the empirical studies and save each result to docs/results/{name}.json.

    python scripts/run_studies.py                  # all studies
    python scripts/run_studies.py calibration lead # a subset
"""

import argparse
import importlib
import json
import time

from pinpricer.config import ROOT

STUDIES = ["calibration", "index_gap", "lead", "positioning", "beta", "events", "sentiment", "markouts"]

if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("names", nargs="*", default=STUDIES, choices=STUDIES)
    out = ROOT / "docs" / "results"
    out.mkdir(parents=True, exist_ok=True)
    for name in p.parse_args().names:
        t = time.time()
        res = importlib.import_module(f"pinpricer.research.{name}").run()
        (out / f"{name}.json").write_text(json.dumps(res, indent=2, default=float))
        print(f"{name}: done in {time.time() - t:.0f}s → docs/results/{name}.json")
