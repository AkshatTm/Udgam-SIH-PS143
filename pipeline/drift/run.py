#!/usr/bin/env python3
"""
Stage 2 — backward drift. Owner: Anushka.

    python pipeline/drift/run.py --case case-000 --real          # PHASE 3, the real thing
    python pipeline/drift/run.py --case case-000 --fake          # analytic ocean, no GEE

PHASE 3. Reads `detections.geojson`, seeds particles off the highest-confidence oil feature,
rewinds them 24 h through the RK2 integrator (`step.py`), and writes the two files the rest of
the project consumes:

    out/particles.json   the animation  -- ONE control run, 3000 particles x 97 frames
    out/origin.json      the answer     -- 50 perturbed runs pooled into a probability grid

WHY TWO DIFFERENT THINGS
    The slider needs coherent trajectories a human can follow, so `particles.json` is the
    single unperturbed run. The origin cloud needs uncertainty, so `origin.json` comes from
    the 50-member ensemble in `ensemble.py`. Showing the ensemble as the animation would look
    like fog; showing the control run as the answer would claim a precision we do not have.

PHASE HISTORY
    Phase 1  real RK2 over an analytic ocean (`--fake`), four known-answer tests
    Phase 2  the analytic ocean swapped for HYCOM + ERA5 under the same two methods
    Phase 3  --real, the 50-run ensemble, the true histogram grid, the convergence window
"""
import argparse
import json
import math
import random
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np

import ensemble as ens
from fields import load_case_field, make_fake
from step import assert_displacement_plausible, displacement_km, integrate

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
OUT = HERE / "out"

KM_PER_DEG = 111.32
ABSTAIN_RADIUS_KM = ens.ABSTAIN_RADIUS_KM


def iso(dt):
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_ts(s):
    dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        raise SystemExit(f"'{s}' is timezone-naive — every timestamp needs the trailing Z")
    return dt


def r5(x):
    return round(float(x), 5)


def pick_slick(dets):
    """Highest-confidence 'oil' feature. Zero oil features is the no-spill case: Stage 2 has
    nothing to rewind, and that is a designed state, not a crash."""
    oil = [f for f in dets.get("features", [])
           if (f.get("properties") or {}).get("classification") == "oil"]
    if not oil:
        return None
    return max(oil, key=lambda f: f["properties"].get("confidence", 0.0))


def seed_particles(feat, n, rng):
    """KEEP THIS. shape_class decides the seeding geometry — that field carries physics."""
    props = feat["properties"]
    clon, clat = float(props["centroid"][0]), float(props["centroid"][1])
    klat = 1.0 / max(math.cos(math.radians(clat)), 1e-6)
    jitter_deg = 0.3 / KM_PER_DEG          # +/- 300 m

    if props.get("shape_class") == "linear":
        # principal axis of the polygon ring, approximated by its most distant point pair
        ring = feat["geometry"]["coordinates"][0]
        best, axis = -1.0, (1.0, 0.0)
        for i in range(0, len(ring), 4):
            for j in range(i + 1, len(ring), 4):
                dx = (ring[j][0] - ring[i][0]) * math.cos(math.radians(clat))
                dy = ring[j][1] - ring[i][1]
                d = dx * dx + dy * dy
                if d > best:
                    best, axis = d, (dx, dy)
        half = math.sqrt(best) / 2.0
        norm = math.hypot(*axis) or 1.0
        ux, uy = axis[0] / norm, axis[1] / norm
        pts = []
        for _ in range(n):
            t = rng.uniform(-half, half)
            pts.append([clon + (t * ux) * klat + rng.gauss(0, jitter_deg) * klat,
                        clat + (t * uy) + rng.gauss(0, jitter_deg)])
        return pts

    # blob: gaussian around the centroid, sigma ~ half the equivalent radius
    area = max(float(props.get("area_km2", 1.0)), 0.01)
    sigma = (math.sqrt(area / math.pi) / 2.0) / KM_PER_DEG
    return [[clon + rng.gauss(0, sigma) * klat, clat + rng.gauss(0, sigma)]
            for _ in range(n)]


def write_particles(path, t0, positions, dt_min):
    path.write_text(json.dumps({
        "t0": iso(t0), "direction": "backward", "timestep_minutes": dt_min,
        "n_steps": len(positions), "n_particles": len(positions[0]),
        "positions": positions}))


def write_origin(path, endpoints, conv_idx, members, t0, timestep_minutes, n_steps, n_runs):
    """The real thing: a histogram of every ensemble endpoint, radii measured from the raw
    points, and a time window that is honest about whether it was measured or bounded."""
    (clon, clat), r50, r90 = ens.radii_km(endpoints)
    bounds, values = ens.origin_grid(endpoints)

    start, end, method = ens.time_window(
        conv_idx,
        [m["spread_start_km"] for m in members],
        [m["spread_min_km"] for m in members],
        t0, timestep_minutes, n_steps)

    rows, cols = values.shape
    doc = {
        "bounds": bounds,
        "shape": [rows, cols],
        "values": [float(v) for v in values.reshape(-1)],
        "centroid": [r5(clon), r5(clat)],
        "radius_50_km": round(r50, 2),
        "radius_90_km": round(r90, 2),
        "time_window": [iso(start), iso(end)],
        "ensemble_runs": int(n_runs),
        "abstain": bool(r90 > ABSTAIN_RADIUS_KM),
        # Additive field the brief asks for (03_ANUSHKA_DRIFT.md Phase 3 step 3): says whether
        # the window was measured from ensemble convergence or is the bounded fallback.
        # Not part of the frozen schema — Akshat, flag it if you would rather it lived
        # somewhere else; nothing breaks if the frontend ignores it.
        "time_window_method": method,
    }
    path.write_text(json.dumps(doc))
    return clon, clat, r50, r90, method, doc["abstain"]


def main():
    ap = argparse.ArgumentParser(description="Stage 2 — backward drift + 50-run ensemble")
    ap.add_argument("--case", required=True)
    ap.add_argument("--cases-root", default=str(REPO / "cases"))
    ap.add_argument("--real", action="store_true",
                    help="PHASE 3: real HYCOM + ERA5 from data/fields/<case>.npz")
    ap.add_argument("--fake", action="store_true",
                    help="real RK2 integrator driven by analytic fields (Phase 1)")
    ap.add_argument("--stub", action="store_true", help=argparse.SUPPRESS)  # back-compat alias
    ap.add_argument("--field", choices=["analytic", "constant"], default="analytic",
                    help="with --fake: analytic = a vortex cell on the slick; constant = uniform")
    ap.add_argument("--wind", type=float, nargs=2, default=(6.0, -4.0), metavar=("U", "V"),
                    help="with --fake: 10 m wind, signed m/s components (east, north)")
    ap.add_argument("--particles", type=int, default=3000)
    ap.add_argument("--runs", type=int, default=50,
                    help="ensemble members. The cut order allows 25; say so in origin.json.")
    ap.add_argument("--steps", type=int, default=97,
                    help="STORED POSITIONS, not physics steps: 97 = t0 + 96 backward "
                         "intervals = exactly 24.0 h (CONTRACTS.md 5)")
    ap.add_argument("--timestep-minutes", type=int, default=15)
    ap.add_argument("--seed", type=int, default=143)
    ap.add_argument("--out", default=str(OUT), help="directory for particles.json/origin.json")
    a = ap.parse_args()

    if not (a.real or a.fake or a.stub):
        raise SystemExit(
            "choose an ocean: --real (HYCOM + ERA5, Phase 3) or --fake (analytic, Phase 1).\n"
            "--real needs data/fields/<case>.npz — run pipeline/drift/fetch_fields.py first.")
    if a.real and a.fake:
        raise SystemExit("--real and --fake are mutually exclusive.")

    case_dir = Path(a.cases_root) / a.case
    det_path = case_dir / "detections.geojson"
    if not det_path.exists():
        raise SystemExit(f"{det_path} not found — Stage 2 seeds from Stage 1's output. "
                         f"Run pipeline/detect/run.py first, or use cases/case-000.")

    meta = json.loads((case_dir / "meta.json").read_text())
    t0 = parse_ts(meta["detection_time"])
    feat = pick_slick(json.loads(det_path.read_text()))
    if feat is None:
        raise SystemExit(
            "detections.geojson contains zero 'oil' features. That is the no-spill case — "
            "there is nothing to rewind, and 'trace' should not be in meta.acts_available.")

    rng = random.Random(a.seed)
    seed = seed_particles(feat, a.particles, rng)

    if a.real:
        field = load_case_field(a.case, repo_root=REPO)
        tag = "REAL"
    else:
        clon0 = float(feat["properties"]["centroid"][0])
        clat0 = float(feat["properties"]["centroid"][1])
        field = make_fake(a.field, lon0=clon0, lat0=clat0, wind=tuple(a.wind))
        tag = "FAKE"

    span_h = (a.steps - 1) * a.timestep_minutes / 60.0    # states recorded, not steps taken

    # ---- control run: the animation ---------------------------------------------------
    history, times = integrate(seed, t0, field, a.steps, a.timestep_minutes,
                               direction="backward")
    positions = np.round(history, 5).tolist()

    # ---- ensemble: the answer ---------------------------------------------------------
    nprng = np.random.default_rng(a.seed)

    def tick(done, total):
        if done == 1 or done % 10 == 0 or done == total:
            print(f"              ensemble {done}/{total}", flush=True)

    endpoints, conv_idx, members = ens.run_ensemble(
        seed, t0, field, a.steps, a.timestep_minutes, n_runs=a.runs, rng=nprng, progress=tick)

    out_dir = Path(a.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    write_particles(out_dir / "particles.json", t0, positions, a.timestep_minutes)
    clon, clat, r50, r90, method, abstain = write_origin(
        out_dir / "origin.json", endpoints, conv_idx, members,
        t0, a.timestep_minutes, a.steps, a.runs)

    # The endpoint pool, kept so plot_heatmap.py can draw the cloud without rerunning 50 runs.
    np.savez_compressed(out_dir / f"ensemble_{a.case}.npz",
                        endpoints=endpoints,
                        control_final=history[-1],
                        seed=np.asarray(seed, dtype=np.float64),
                        conv_idx=conv_idx,
                        wind_coeff=np.array([m["wind_coeff"] for m in members]),
                        current_scale=np.array([m["current_scale"] for m in members]))

    # The permanent plausibility guard, on every real run, not just in tests.py.
    med_km = assert_displacement_plausible(history[0], history[-1], hours=span_h)
    dist = displacement_km(history[0], history[-1])
    ws = np.array([m["wind_coeff"] for m in members])
    cs = np.array([m["current_scale"] for m in members])

    print(f"[drift:{tag}]  wrote {out_dir / 'particles.json'}")
    print(f"              wrote {out_dir / 'origin.json'}")
    print(f"              field  {field}")
    print(f"              seeded {a.particles} from {feat['properties']['id']} "
          f"({feat['properties']['shape_class']}), rewound {span_h:.2f} h "
          f"in {a.steps} steps of {a.timestep_minutes} min")
    print(f"              t0 {iso(t0)} -> {iso(times[-1])}")
    print(f"              control displacement  median {med_km:.1f} km   "
          f"min {float(dist.min()):.1f}   max {float(dist.max()):.1f}")
    print(f"              ensemble {a.runs} runs x {a.particles} = {len(endpoints):,} endpoints"
          f"   wind_coeff {ws.min():.4f}-{ws.max():.4f}   current x{cs.min():.2f}-{cs.max():.2f}")
    print(f"              origin ({clon:.4f}, {clat:.4f})  "
          f"r50={r50:.1f} km  r90={r90:.1f} km  abstain={abstain}")
    print(f"              time_window method={method}")


if __name__ == "__main__":
    main()
