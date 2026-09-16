"""Uncertainty growth with hours-back, for evidence figure F2.1.

Re-runs run.py's backward ensemble EXACTLY (same seed, same args as publish_all.py) with one
change: every member's positions are also kept at hourly frames, so r50/r90 can be measured at
every hour of the rewind instead of only at the end. Writes to a scratch --out, NEVER to the
case bundle, then checks the 24 h radii against the published cases/<id>/origin.json. If they do
not match, the curve is refused -- a growth curve that ends somewhere other than the shipped
answer would be describing a different run.

    python pipeline/drift/eval_growth.py --case case-jacksonville-2024

Output: docs/evaluation/figures/stage2/data/growth_<case>.json
"""
import argparse, json, sys, tempfile
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(HERE))

import ensemble as ens   # noqa: E402
import run               # noqa: E402

FRAMES_PER_HOUR = 4      # 15-minute steps


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--case", required=True)
    a = ap.parse_args()

    kept = []
    original = ens.run_once

    def recording_run_once(*args, **kw):
        kw["keep_history"] = True
        final, spread, history, times = original(*args, **kw)
        kept.append(history[::FRAMES_PER_HOUR].copy())
        return final, spread, None, times

    ens.run_once = recording_run_once
    scratch = Path(tempfile.mkdtemp(prefix=f"growth_{a.case}_"))
    sys.argv = ["run.py", "--case", a.case, "--real", "--particles", "3000", "--runs", "50",
                "--out", str(scratch)]
    run.main()
    ens.run_once = original

    hist = np.stack(kept)                       # [runs, hours+1, particles, 2]
    n_runs, n_frames, n_part, _ = hist.shape
    rows = []
    for h in range(n_frames):
        pts = hist[:, h].reshape(-1, 2)
        _, r50, r90 = ens.radii_km(pts)
        rows.append({"hours_back": h, "radius_50_km": round(r50, 3), "radius_90_km": round(r90, 3)})

    shipped = json.loads((REPO / "cases" / a.case / "origin.json").read_text())
    rerun = json.loads((scratch / "origin.json").read_text())
    ok = (abs(rerun["radius_50_km"] - shipped["radius_50_km"]) < 0.01 and
          abs(rerun["radius_90_km"] - shipped["radius_90_km"]) < 0.01)
    end_ok = (abs(rows[-1]["radius_50_km"] - shipped["radius_50_km"]) < 0.06 and
              abs(rows[-1]["radius_90_km"] - shipped["radius_90_km"]) < 0.06)
    report = {
        "case": a.case,
        "source": f"cases/{a.case}/origin.json (24 h end state) + re-run of run.py --real "
                  f"--particles 3000 --runs 50 with hourly frames kept",
        "n_runs": n_runs, "n_particles_per_run": n_part, "n_points_per_hour": n_runs * n_part,
        "shipped": {"radius_50_km": shipped["radius_50_km"], "radius_90_km": shipped["radius_90_km"]},
        "rerun_origin": {"radius_50_km": rerun["radius_50_km"], "radius_90_km": rerun["radius_90_km"]},
        "reproduces_shipped": bool(ok and end_ok),
        "growth": rows,
    }
    out = REPO / "docs/evaluation/figures/stage2/data" / f"growth_{a.case}.json"
    out.write_text(json.dumps(report, indent=1))
    print(f"[growth] {a.case}: 24 h r50 {rows[-1]['radius_50_km']} / r90 {rows[-1]['radius_90_km']}"
          f"  shipped {shipped['radius_50_km']} / {shipped['radius_90_km']}"
          f"  reproduces={report['reproduces_shipped']}")
    if not report["reproduces_shipped"]:
        raise SystemExit("growth curve does NOT reproduce the shipped origin.json -- refused")


if __name__ == "__main__":
    main()
