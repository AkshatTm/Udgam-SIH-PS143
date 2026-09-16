"""Forward drift as an impact forecast -- Version A (no schema change). Final-day brief P2.

Runs the SAME 50-member ensemble as the backward answer (same seed particles, same stratified
wind/current draws, seed 143) but FORWARD from t0, keeping hourly frames, and records per hour:
  - r50 / r90 of the pooled forward cloud (the mirror of F2.1)
  - the fraction of particles stranded on the GSHHG coastline (sticky), and first landfall

`compute()` holds the physics and returns the result dict. Two callers share it, so the bundle and
the evidence file can never drift apart into two sets of numbers:
  - this module's CLI writes docs/evaluation/figures/stage2/data/forward_<case>.json (evidence)
  - forward_impact.py writes cases/<case>/forward_impact.json (the bundle, Master 6.10)

Never touches particles.json, particles_forward.json, origin.json or meta.json (Rule 3).
The 16 Sept deferral of forward_impact.json was LIFTED by Akshat on 16 Sept; see Master 6.10.

HORIZON: the cached fields cover ~24-26 h past t0 on every case, and assert_field_covers refuses
anything longer, so the forecast is 24 h. +48 h and +72 h would need a wider GEE fetch; they are
NOT extrapolated through a frozen last snapshot.

    python pipeline/drift/eval_forward.py --case case-jacksonville-2024
"""
import argparse, json, sys
from datetime import timedelta
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(HERE))

import coastline          # noqa: E402
import ensemble as ens    # noqa: E402
import run                # noqa: E402
from step import assert_field_covers, assert_inside_field_box, FieldTimeSpan  # noqa: E402

FRAMES_PER_HOUR = 4
HORIZON_H = 24


def compute(case):
    """Run the 50-member forward ensemble for `case` and return the measured result dict.

    The single source of the forward numbers. Both the evidence file and the bundle's
    forward_impact.json are written from this return value, never recomputed separately.
    """
    result = {}

    def forward_ensemble(a, meta, t0, field, seed, feat, out_dir):
        try:
            assert_field_covers(field, t0, t0 + timedelta(hours=HORIZON_H), "forward ensemble")
        except FieldTimeSpan as exc:
            raise SystemExit(str(exc))
        land = coastline.is_land if coastline.available() else None
        if land is None:
            raise SystemExit("no coastline available -- a stranding curve without a coast is not a result")

        frames, strand_steps = [], []
        original = ens.run_once

        def recording(*args, **kw):
            state = {"k": 0, "first": None}

            def is_land(lon, lat):
                hit = land(lon, lat)
                if state["first"] is None:
                    state["first"] = np.full(hit.shape, -1, dtype=int)
                new = hit & (state["first"] < 0)
                state["first"][new] = state["k"]
                state["k"] += 1
                return hit

            kw["keep_history"] = True
            kw["direction"] = "forward"
            kw["is_land"] = is_land
            final, spread, history, times = original(*args, **kw)
            frames.append(history[::FRAMES_PER_HOUR].copy())
            strand_steps.append(state["first"])
            return final, spread, None, times

        ens.run_once = recording
        nprng = np.random.default_rng(a.seed)
        endpoints, _, members = ens.run_ensemble(seed, t0, field, a.steps, a.timestep_minutes,
                                                 n_runs=a.runs, rng=nprng, is_land=land)
        ens.run_once = original

        margin = assert_inside_field_box(endpoints, field.bbox, margin_km=10.0,
                                         label="forward ensemble endpoints")
        hist = np.stack(frames)                      # [runs, 25, particles, 2]
        ss = np.stack(strand_steps)                  # [runs, particles], -1 = never
        seeded_ashore = float(np.mean(ss == 0))
        landed = ss > 0
        seed_c = np.asarray(seed).mean(0)
        rows = []
        for h in range(hist.shape[1]):
            pts = hist[:, h].reshape(-1, 2)
            (clon, clat), r50, r90 = ens.radii_km(pts)
            k = h * FRAMES_PER_HOUR
            rows.append({"hours": h, "radius_50_km": round(r50, 3), "radius_90_km": round(r90, 3),
                         "centroid": [round(clon, 5), round(clat, 5)],
                         "stranded_fraction": round(float(np.mean(landed & (ss <= k))), 4)})
        first = None
        if landed.any():
            first = round(float(ss[landed].min()) * a.timestep_minutes / 60.0, 2)
        dx, dy = ens.deg_to_m(np.array([rows[-1]["centroid"][0] - seed_c[0]]),
                              np.array([rows[-1]["centroid"][1] - seed_c[1]]), np.array([seed_c[1]]))
        result.update({
            "case": a.case, "t0": run.iso(t0), "direction": "forward", "horizon_hours": HORIZON_H,
            "horizon_note": "field cache covers ~24-26 h past t0; 48 h and 72 h need a wider fetch and are not extrapolated",
            "n_runs": a.runs, "n_particles_per_run": int(hist.shape[2]),
            "wind_coeff": "stratified U(0.025, 0.035), same draws as the backward ensemble",
            "seeded_ashore_fraction": round(seeded_ashore, 4),
            "first_landfall_hours": first,
            "stranded_fraction_at_horizon": rows[-1]["stranded_fraction"],
            "centroid_displacement_km_at_horizon": round(float(np.hypot(dx, dy)[0]) / 1000.0, 2),
            "edge_margin_km": round(float(margin), 1),
            "envelope": rows,
            "source": f"re-run of run.py seeding for {a.case}, 50-member ensemble forward, GSHHG stranding on",
        })
        return 0

    original_run_forward = run.run_forward
    original_argv = sys.argv
    run.run_forward = forward_ensemble
    sys.argv = ["run.py", "--case", case, "--real", "--forward", "--particles", "3000",
                "--runs", "50", "--out", str(Path.home() / f"fwd_scratch_{case}")]
    try:
        run.main()
    finally:
        run.run_forward = original_run_forward
        sys.argv = original_argv
    return result


def summarise(case, result):
    e = result["envelope"]
    return (f"[forward] {case}: +24 h r50 {e[-1]['radius_50_km']} r90 {e[-1]['radius_90_km']}  "
            f"stranded {result['stranded_fraction_at_horizon']}  "
            f"first landfall {result['first_landfall_hours']}  "
            f"edge margin {result['edge_margin_km']} km")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--case", required=True)
    cli = ap.parse_args()
    result = compute(cli.case)
    out = REPO / "docs/evaluation/figures/stage2/data" / f"forward_{cli.case}.json"
    out.write_text(json.dumps(result, indent=1))
    print(summarise(cli.case, result))


if __name__ == "__main__":
    main()
