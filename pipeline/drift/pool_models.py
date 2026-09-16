#!/usr/bin/env python3
"""Stage 2 -- pool our origin cloud with OpenDrift OceanDrift's into ONE grid (decision C).

    python pipeline/drift/pool_models.py --case case-jacksonville-2024

reads   out/origin.json                       run.py's output for this case (must match --case)
        out/age_pool_<case>.npz               our cloud, age-weighted   (run.py --age drive)
          or out/ensemble_<case>.npz          our final-step endpoints  (no age posterior)
        out/opendrift_origin_<case>.npz       OceanDrift's hourly frames (opendrift_origin.py)
writes  out/origin.json                       bounds/values/centroid/radii/abstain + model_mix

EQUAL WEIGHT PER MODEL. There is no ground truth for origin position on any case (Master 8.2),
so any skill-based weighting would be invented. Each model's points are scaled to total 0.5.

STRUCTURAL FALLBACK, NOT A try/except: no OceanDrift file -> exit 0, origin.json untouched, no
model_mix key. Absence hides a UI row; the demo path is run.py alone.

Two keys, two claims, never merged: `opendrift_comparison` (physics off, "is our integrator
right?") and `model_mix` (physics on, "what does a second model say the origin is?").
Stranded fractions are reported PER MODEL inside model_mix and never averaged into
`stranded_fraction`, which describes our ensemble only -- the two coastlines differ.
"""
import argparse
import json
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import ensemble as ens                                   # noqa: E402
from run import ABSTAIN_RADIUS_KM, r5                    # noqa: E402

OUT = HERE / "out"


def opendrift_pool(z, post):
    """OceanDrift frames weighted by the age posterior (or the last frame if there is none)."""
    pos = z["positions"]                                  # (hours+1, n, 2)
    hours = z["hours"]
    if post is None:
        pts = pos[-1]
        return pts, np.full(len(pts), 1.0 / len(pts)), "final frame"
    pts, wts = [], []
    lo, hi = post["hpd80"]
    for t, p in zip(post["hours_grid"], post["prob"]):
        # same window as our pool (ensemble.age_weighted_pool): only ages inside the stated
        # release window, so both models describe the event the window claims
        if p < 1e-4 or not (lo - 1e-9 <= float(t) <= hi + 1e-9):
            continue
        j = int(np.argmin(np.abs(hours - float(t))))
        f = pos[j]
        f = f[np.all(np.isfinite(f), axis=1)]
        if len(f):
            pts.append(f)
            wts.append(np.full(len(f), float(p) / len(f)))
    w = np.concatenate(wts)
    return np.vstack(pts), w / w.sum(), "age posterior"


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--case", required=True)
    ap.add_argument("--out", default=str(OUT))
    a = ap.parse_args(argv)
    out = Path(a.out)

    od_path = out / f"opendrift_origin_{a.case}.npz"
    if not od_path.exists():
        print(f"[pool] no {od_path.name} -- single-model origin stands, no model_mix written")
        return 0
    origin_path = out / "origin.json"
    origin = json.loads(origin_path.read_text())
    z_od = np.load(od_path, allow_pickle=False)
    if str(z_od["case"]) != a.case:
        raise SystemExit(f"{od_path} belongs to {z_od['case']}, not {a.case}")

    post = origin.get("age_posterior") if origin.get("time_window_method") == "age" else None
    age_pool = out / f"age_pool_{a.case}.npz"
    if post is not None:
        if not age_pool.exists():
            raise SystemExit(f"origin.json is age-driven but {age_pool.name} is missing -- "
                             f"rerun run.py --case {a.case} --age drive")
        zp = np.load(age_pool)
        ours_pts, ours_w = zp["points"], zp["weights"]
        ours_basis = "age posterior"
    else:
        ze = np.load(out / f"ensemble_{a.case}.npz")
        ours_pts = ze["endpoints"]
        ours_w = np.full(len(ours_pts), 1.0 / len(ours_pts))
        ours_basis = "final frame"
    # guard against pooling a different case's origin.json (out/ is not case-scoped)
    c = np.average(ours_pts, axis=0, weights=ours_w)
    if abs(c[0] - origin["centroid"][0]) > 0.5 or abs(c[1] - origin["centroid"][1]) > 0.5:
        raise SystemExit(f"out/origin.json does not look like {a.case}'s -- rerun run.py first")

    od_pts, od_w, od_basis = opendrift_pool(z_od, post)
    pts = np.vstack([ours_pts, od_pts])
    w = np.concatenate([0.5 * ours_w / ours_w.sum(), 0.5 * od_w / od_w.sum()])

    (clon, clat), r50, r90 = ens.radii_km(pts, weights=w)
    bounds, values = ens.origin_grid(pts, weights=w)
    (oc, _, o90) = ens.radii_km(ours_pts, weights=ours_w)
    (dc, _, d90) = ens.radii_km(od_pts, weights=od_w)
    sep_km = float(np.hypot((oc[0] - dc[0]) * 111.32 * np.cos(np.radians(oc[1])),
                            (oc[1] - dc[1]) * 111.32))
    rows, cols = values.shape
    origin.update({
        "bounds": bounds, "shape": [rows, cols],
        "values": [float(v) for v in values.reshape(-1)],
        "centroid": [r5(clon), r5(clat)],
        "radius_50_km": round(r50, 2), "radius_90_km": round(r90, 2),
        "abstain": bool(r90 > ABSTAIN_RADIUS_KM),
        "model_mix": {
            "models": [
                {"name": "udgam_rk2", "weight": 0.5, "points": int(len(ours_pts)),
                 "pooled_over": ours_basis, "radius_90_km": round(o90, 2),
                 "stranded_fraction": origin.get("stranded_fraction"),
                 "physics": ["current + wind_coeff x wind", "rk2", "coastline stranding"]},
                {"name": "opendrift_oceandrift", "weight": 0.5, "points": int(len(od_pts)),
                 "pooled_over": od_basis, "radius_90_km": round(d90, 2),
                 "stranded_fraction": round(float(z_od["stranded_fraction"]), 4),
                 "version": str(z_od["opendrift_version"]),
                 "physics": json.loads(str(z_od["physics"]))},
            ],
            "centroid_separation_km": round(sep_km, 2),
            "weighting": ("equal per model: no ground truth for origin position exists on "
                          "any case, so any skill weighting would be invented"),
        },
    })
    origin_path.write_text(json.dumps(origin))
    print(f"[pool] {a.case}: r50 {r50:.2f} km  r90 {r90:.2f} km  abstain {origin['abstain']}  "
          f"models {sep_km:.2f} km apart (ours r90 {o90:.2f}, OceanDrift r90 {d90:.2f})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
