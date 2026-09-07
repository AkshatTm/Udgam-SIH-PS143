#!/usr/bin/env python3
"""
Stage 2 — backward drift. Owner: Anushka.

    python pipeline/drift/run.py --case case-000 --stub

STUB ONLY. Reads `detections.geojson`, seeds particles off the highest-confidence oil feature,
random-walks them "backwards", and writes schema-valid `out/particles.json` + `out/origin.json`.
No physics, no GEE, no ensemble — this exists so the seam is wired before the physics is.

What to KEEP when the real engine lands:
  - `seed_particles()`. It already implements the contract rule that `shape_class` carries
    physics: "linear" seeds along the polygon's principal axis (a moving ship), "blob" seeds
    gaussian around the centroid (a stationary event).
  - `write_particles()` / `write_origin()` — the file shapes are frozen.
What to DELETE:
  - `fake_walk()`, replaced by RK2 through real HYCOM + ERA5 fields:
    velocity = current + 0.03 * wind, dt = 15 min, backward = NEGATIVE dt through the same
    field (not a minus sign on velocity), vectorised NumPy over an [n, 2] lon/lat array.
    HYCOM velocity bands are cm/s -> divide by 100 (docs/TRAPS.md #2).

Deliberately stdlib-only. The real engine needs numpy, scipy, earthengine-api, matplotlib.
"""
import argparse
import json
import math
import random
from datetime import datetime, timedelta, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
OUT = HERE / "out"

KM_PER_DEG = 111.32
ABSTAIN_RADIUS_KM = 40.0     # agreed rule: a cloud wider than this refuses attribution


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


def fake_walk(seed, steps, rng):
    """DELETE THIS. A biased random walk standing in for advection. Drift is chosen to land
    in the tens-of-km range over 24 h, which is what a real ocean does — so the validator's
    plausibility guards are actually exercised rather than trivially satisfied."""
    drift = (0.0022, 0.0016)                 # degrees per 15-min step
    positions, cur = [], [list(p) for p in seed]
    for s in range(steps):
        positions.append([[r5(p[0]), r5(p[1])] for p in cur])
        # spread grows with rewind depth — the honest bit the demo shows
        spread = 0.00042 * (1 + 2.2 * s / steps)
        for p in cur:
            p[0] += drift[0] + rng.gauss(0, spread)
            p[1] += drift[1] + rng.gauss(0, spread)
    return positions


def write_particles(path, t0, positions, dt_min):
    path.write_text(json.dumps({
        "t0": iso(t0), "direction": "backward", "timestep_minutes": dt_min,
        "n_steps": len(positions), "n_particles": len(positions[0]),
        "positions": positions}))


def write_origin(path, final, t0, span_h, runs):
    """120x120 normalised probability grid, row-major from the top-left (row 0 = NORTH)."""
    n = len(final)
    clon = sum(p[0] for p in final) / n
    clat = sum(p[1] for p in final) / n
    klat = math.cos(math.radians(clat))

    d = [math.hypot((p[0] - clon) * klat * KM_PER_DEG, (p[1] - clat) * KM_PER_DEG)
         for p in final]
    d.sort()
    r50 = d[int(0.50 * (n - 1))]
    r90 = d[int(0.90 * (n - 1))]

    rows = cols = 120
    half = max(r90 * 1.8 / KM_PER_DEG, 0.05)
    west, east = clon - half / max(klat, 1e-6), clon + half / max(klat, 1e-6)
    south, north = clat - half, clat + half
    sigma = max(r50, 0.5) / KM_PER_DEG

    values, peak = [], 0.0
    for r in range(rows):
        lat = north - (north - south) * r / (rows - 1)     # row 0 = north
        for c in range(cols):
            lon = west + (east - west) * c / (cols - 1)
            dd = ((lon - clon) * klat) ** 2 + (lat - clat) ** 2
            v = math.exp(-dd / (2 * sigma * sigma))
            peak = max(peak, v)
            values.append(v)
    values = [round(v / peak, 4) for v in values]           # normalise to peak 1.0

    path.write_text(json.dumps({
        "bounds": {"west": r5(west), "south": r5(south), "east": r5(east), "north": r5(north)},
        "shape": [rows, cols], "values": values,
        "centroid": [r5(clon), r5(clat)],
        "radius_50_km": round(r50, 2), "radius_90_km": round(r90, 2),
        "time_window": [iso(t0 - timedelta(hours=span_h)),
                        iso(t0 - timedelta(hours=span_h / 3))],
        "ensemble_runs": runs,
        "abstain": r90 > ABSTAIN_RADIUS_KM}))
    return clon, clat, r50, r90


def main():
    ap = argparse.ArgumentParser(description="Stage 2 — backward drift (stub)")
    ap.add_argument("--case", required=True)
    ap.add_argument("--cases-root", default=str(REPO / "cases"))
    ap.add_argument("--stub", action="store_true", help="required until the real engine exists")
    ap.add_argument("--particles", type=int, default=3000)
    ap.add_argument("--steps", type=int, default=97)
    ap.add_argument("--timestep-minutes", type=int, default=15)
    ap.add_argument("--seed", type=int, default=143)
    a = ap.parse_args()

    if not a.stub:
        raise SystemExit(
            "drift/run.py has no real implementation yet — pass --stub.\n"
            "Building it is Phases 1-3 of docs/03_ANUSHKA_DRIFT.md. Tests come first.")

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
    positions = fake_walk(seed, a.steps, rng)

    OUT.mkdir(parents=True, exist_ok=True)
    write_particles(OUT / "particles.json", t0, positions, a.timestep_minutes)
    span_h = (a.steps - 1) * a.timestep_minutes / 60
    clon, clat, r50, r90 = write_origin(OUT / "origin.json", positions[-1], t0, span_h, 50)

    p0, pn = positions[0][0], positions[-1][0]
    km = math.hypot((pn[0] - p0[0]) * KM_PER_DEG * math.cos(math.radians(clat)),
                    (pn[1] - p0[1]) * KM_PER_DEG)
    print(f"[drift:STUB]  wrote {OUT / 'particles.json'}")
    print(f"              wrote {OUT / 'origin.json'}")
    print(f"              seeded {a.particles} from {feat['properties']['id']} "
          f"({feat['properties']['shape_class']}), rewound {span_h:.0f} h in {a.steps} steps")
    print(f"              particle 0 travelled {km:.1f} km   "
          f"origin ({clon:.4f}, {clat:.4f})  r50={r50:.1f} km  r90={r90:.1f} km")


if __name__ == "__main__":
    main()
