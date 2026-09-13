#!/usr/bin/env python3
"""
make_fake_case.py — a US-located fake case bundle, so Stage 3 can be built today.
Owner: Jaiveer.

    python pipeline/attribute/make_fake_case.py

WHY THIS EXISTS
`cases/case-000/origin.json` sits over Ennore, India, in January 2017. My AIS is
Galveston, Texas, January 2023. Scoring against it returns zero of everything —
zero in every funnel count, no suspects — which reads exactly like broken code and
is not. Until a US-located origin exists, the scorer cannot be tested at all
(docs/team/jaiveer-stage3-attribution.md, Phase 0.2).

This writes a complete, schema-valid bundle over open water southeast of Galveston
on 25 January 2023, the day I already have AIS for. It touches nothing anyone else
owns: it is my script, in my directory, writing into my fixtures folder.

WHAT IS FAKE AND WHAT IS NOT
Everything this script writes is invented — the scene, the slick, the particles,
the origin cloud, the stub vessels. It is a fixture and `meta.notes` says so.
What is real is the *water it points at*: the box, the day and the time window were
chosen by measuring my actual NOAA extract, so that ~17 real vessels pass through
the origin cloud during the window and 15 of them are genuinely under way. A fixture
over an anchorage would have let the `gap` and `slowdown` gating pass untested.

THE ORIGIN CLOUD IS A STREAK, NOT A CIRCLE
Anushka measured the real cloud at 4.38:1 with 44.7% of its high-probability mass
outside the r50 circle, which is why Akshat ruled (D8) that Stage 3 scores the
probability grid rather than circle membership. A circular fixture cannot tell a
grid-sampling scorer apart from a circle-membership one, so this cloud is
elongated by default. On my extract the two disagree about nine real vessels.

Deps: numpy + pillow, both already pinned in requirements.txt. No new dependencies.
"""
import argparse
import json
import math
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
from PIL import Image

KM_PER_DEG = 111.32

# Defaults, all measured against data/ais/gulf.parquet (25 Jan 2023, Galveston box).
# The origin sits in the approach lane, not the anchorage — see the note above.
ORIGIN_LON, ORIGIN_LAT = -94.35, 29.00
ORIGIN_AXIS_DEG = 175.0          # compass bearing of the lane, from the COG histogram
ORIGIN_SIGMA_DEG = 0.025         # across-axis gaussian sigma
ORIGIN_ASPECT = 4.0              # along-axis stretch; Anushka's real cloud is 4.38:1
T0_DEFAULT = "2023-01-25T23:00:00Z"
WINDOW_BACK_HOURS = (20, 8)      # origin window is t0-20h .. t0-8h


def iso(dt):
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def r5(x):
    return round(float(x), 5)


def km_per_deg_lon(lat):
    return KM_PER_DEG * math.cos(math.radians(lat))


def unit_along(bearing_deg):
    """Compass bearing (clockwise from north) -> (east, north) unit vector."""
    th = math.radians(bearing_deg)
    return math.sin(th), math.cos(th)


def ellipse_ring(clon, clat, half_len_km, half_wid_km, bearing_deg, n=48):
    """Closed ring for an ellipse, long axis on the given compass bearing."""
    ex, ny = unit_along(bearing_deg)
    klon = km_per_deg_lon(clat)
    ring = []
    for i in range(n + 1):
        t = 2 * math.pi * i / n
        along, across = half_len_km * math.cos(t), half_wid_km * math.sin(t)
        # rotate: along -> (ex, ny), across -> perpendicular (ny, -ex)
        dx_km = along * ex + across * ny
        dy_km = along * ny - across * ex
        ring.append([r5(clon + dx_km / klon), r5(clat + dy_km / KM_PER_DEG)])
    ring[-1] = ring[0]
    return ring


def anisotropic_grid(clon, clat, bounds, rows, cols, sigma_deg, aspect, bearing_deg):
    """Normalised probability grid, row 0 = NORTH (frozen convention 5)."""
    gx = np.linspace(bounds["west"], bounds["east"], cols)[None, :]
    gy = np.linspace(bounds["north"], bounds["south"], rows)[:, None]
    klat = math.cos(math.radians(clat))
    dx = (gx - clon) * klat                     # east component, degrees
    dy = (gy - clat)                            # north component, degrees
    ex, ny = unit_along(bearing_deg)
    along = dx * ex + dy * ny
    across = dx * ny - dy * ex
    grid = np.exp(-((along / aspect) ** 2 + across ** 2) / (2 * sigma_deg ** 2))
    return grid / grid.max(), dx, dy


def mass_radii(grid, dx, dy, clat):
    """r50/r90 as the circle radii containing 50% / 90% of the grid's mass.

    Derived rather than asserted: a bundle whose drawn radii disagree with its own
    probability mass will pass every schema check and still mislead a judge.
    """
    # dx already carries the cos-lat scaling, so both components convert with the
    # same km-per-degree factor.
    rad = np.hypot(dx * KM_PER_DEG, dy * KM_PER_DEG)
    order = np.argsort(rad.ravel())
    csum = np.cumsum(grid.ravel()[order]) / grid.sum()
    r = rad.ravel()[order]
    return float(r[np.searchsorted(csum, 0.50)]), float(r[np.searchsorted(csum, 0.90)])


def make_sar(path, bounds, slick_ring, px, rng):
    """Speckled open water with one dark linear slick. No land: this box is open Gulf,
    and drawing a coastline that is not there would be a lie in the picture."""
    img = rng.gamma(shape=4.0, scale=26.0, size=(px, px))
    yy, xx = np.mgrid[0:px, 0:px]
    lon = bounds["west"] + (xx + 0.5) / px * (bounds["east"] - bounds["west"])
    lat = bounds["north"] - (yy + 0.5) / px * (bounds["north"] - bounds["south"])
    ring = np.array(slick_ring)
    clon, clat = ring[:, 0].mean(), ring[:, 1].mean()
    half_len = np.hypot((ring[:, 0] - clon) * math.cos(math.radians(clat)),
                        ring[:, 1] - clat).max()
    dx = (lon - clon) * math.cos(math.radians(clat))
    dy = lat - clat
    ex, ny = unit_along(ORIGIN_AXIS_DEG)
    along = dx * ex + dy * ny
    across = dx * ny - dy * ex
    slick = (along / half_len) ** 2 + (across / (half_len / 8.2)) ** 2 < 1.0
    img[slick] *= 0.30                               # oil flattens waves -> dark
    Image.fromarray(np.clip(img, 0, 255).astype(np.uint8), mode="L").save(path)


def main():
    ap = argparse.ArgumentParser(description="US-located fake case bundle for Stage 3")
    ap.add_argument("--out", default="pipeline/attribute/fixtures/case-gulf-fake")
    ap.add_argument("--case-id", default=None, help="defaults to the output directory name")
    ap.add_argument("--origin", type=float, nargs=2, metavar=("LON", "LAT"),
                    default=[ORIGIN_LON, ORIGIN_LAT])
    ap.add_argument("--axis-deg", type=float, default=ORIGIN_AXIS_DEG)
    ap.add_argument("--sigma", type=float, default=ORIGIN_SIGMA_DEG)
    ap.add_argument("--aspect", type=float, default=ORIGIN_ASPECT)
    ap.add_argument("--t0", default=T0_DEFAULT, help="satellite pass, UTC ISO 8601 with Z")
    ap.add_argument("--particles", type=int, default=800)
    ap.add_argument("--steps", type=int, default=97)     # (97-1) x 15 min = exactly 24 h
    ap.add_argument("--timestep-minutes", type=int, default=15)
    ap.add_argument("--px", type=int, default=700)
    ap.add_argument("--scene-pad-deg", type=float, default=0.85,
                    help="margin around the slick and origin for the SAR scene, degrees. "
                         "0.85 gives roughly a Sentinel-1 IW footprint")
    ap.add_argument("--seed", type=int, default=143)
    ap.add_argument("--ais-source", default="noaa_dense",
                    choices=("noaa_dense", "gfw_hourly"),
                    help="which AIS regime this case stands in for (D20)")
    ap.add_argument("--time-window-method", default="bounded",
                    choices=("bounded", "convergence"),
                    help="6.5: 'bounded' is a SEARCH BRACKET, 'convergence' is a measured "
                         "release time. The temporality component scores only against a "
                         "measurement and returns null against a bracket (D12), so this "
                         "flag is what gives that gate test coverage in both directions. "
                         "Default stays 'bounded' so existing fixtures do not move under "
                         "anyone building against them; pass 'convergence' for a fixture "
                         "that exercises temporality. Three of the six real cases are "
                         "'bounded', so both paths are live in production.")
    ap.add_argument("--discharge-class", default="chronic",
                    choices=("chronic", "acute", "unknown"),
                    help="Stage 1's field; gates the parity component")
    ap.add_argument("--abstain", action="store_true",
                    help="write abstain:true, to exercise the refusal path end to end")
    a = ap.parse_args()

    t0 = datetime.fromisoformat(a.t0.replace("Z", "+00:00"))
    if t0.tzinfo is None:
        raise SystemExit(f"--t0 '{a.t0}' is timezone-naive — every timestamp needs the trailing Z")
    out = Path(a.out)
    case_id = a.case_id or out.name
    out.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(a.seed)

    clon, clat = a.origin
    klon = km_per_deg_lon(clat)

    # --- the slick: 24 h of drift downstream of the origin, on the same axis
    ex, ny = unit_along(a.axis_deg)
    drift_km = 22.0
    slon = clon + (-drift_km * ex) / klon      # slick sits up-bearing from the origin
    slat = clat + (-drift_km * ny) / KM_PER_DEG
    half_len_km, half_wid_km = 9.0, 1.1        # elongation 8.2 -> shape_class "linear"
    slick_ring = ellipse_ring(slon, slat, half_len_km, half_wid_km, a.axis_deg)

    # --- scene bounds: contains the slick and the origin, with margin.
    # Padded toward a real Sentinel-1 IW footprint (~250 km swath) rather than tightly
    # around the slick. A 65 km scene is not what a real case looks like, and it made
    # the validator warn on every vessel that sailed off the edge during a 12-hour
    # window — 232 warnings that were an artefact of the fixture rather than a fault in
    # the output. Warnings are where real problems hide; a fixture should not manufacture
    # them.
    lons = [p[0] for p in slick_ring] + [clon]
    lats = [p[1] for p in slick_ring] + [clat]
    pad = a.scene_pad_deg
    # v4 Part 6.2 renamed the dB stretch to `db_clamp`. Both are written: `db_clamp` is
    # the live contract, `db_min`/`db_max` keep any v1-era reader working.
    bounds = {"west": r5(min(lons) - pad), "south": r5(min(lats) - pad),
              "east": r5(max(lons) + pad), "north": r5(max(lats) + pad),
              "width_px": a.px, "height_px": a.px,
              "db_clamp": [-25, 0], "db_min": -25, "db_max": 0}
    (out / "bounds.json").write_text(json.dumps(bounds, indent=2))

    # `ais_source` is required on every case with `attribute` (v4 Part 6.1, D20): it
    # decides whether `gap` and `slowdown` can fire at all. This fixture stands in for a
    # NOAA case, so `noaa_dense` — pass --ais-source gfw_hourly to exercise the other
    # regime, where those two components must return null rather than zero.
    (out / "meta.json").write_text(json.dumps({
        "case_id": case_id,
        "title": "FAKE — Galveston test origin (Stage 3 development fixture)",
        "short_location": "Galveston approaches, Texas",
        "case_type": "spill",
        "satellite": "Sentinel-1A (fake)", "scene_id": "FAKE-GULF",
        "detection_time": iso(t0),
        "acts_available": ["detect", "trace", "attribute"],
        "ais_source": a.ais_source,
        "gallery": {"thumbnail": "thumb.png",
                    "blurb": "Synthetic fixture. Not a case — never shown to a judge.",
                    "difficulty": "easy"},
        "notes": ("Synthetic. Never shown to a judge. Written by "
                  "pipeline/attribute/make_fake_case.py so Stage 3 scoring can be built "
                  "and tested against US AIS before the real US origin exists.")
    }, indent=2))

    make_sar(out / "sar.png", bounds, slick_ring, a.px, rng)

    # --- detections.geojson: one linear slick
    area_km2 = round(math.pi * half_len_km * half_wid_km, 1)
    (out / "detections.geojson").write_text(json.dumps({
        "type": "FeatureCollection",
        "features": [{
            "type": "Feature",
            "geometry": {"type": "Polygon", "coordinates": [slick_ring]},
            "properties": {"id": "det-01", "classification": "oil", "confidence": 0.87,
                           "area_km2": area_km2,
                           "elongation": round(half_len_km / half_wid_km, 1),
                           "edge_gradient": 0.34, "contrast_db": -6.2,
                           "shape_class": "linear",
                           "discharge_class": a.discharge_class,
                           "ship_detections": [],
                           "centroid": [r5(slon), r5(slat)]}}]}))

    # --- origin.json: the anisotropic cloud
    rows = cols = 120
    half = max(0.30, 4.0 * a.sigma * max(a.aspect, 1.0))
    obounds = {"west": r5(clon - half), "south": r5(clat - half),
               "east": r5(clon + half), "north": r5(clat + half)}
    grid, dx, dy = anisotropic_grid(clon, clat, obounds, rows, cols,
                                    a.sigma, a.aspect, a.axis_deg)
    r50, r90 = mass_radii(grid, dx, dy, clat)
    win = [iso(t0 - timedelta(hours=WINDOW_BACK_HOURS[0])),
           iso(t0 - timedelta(hours=WINDOW_BACK_HOURS[1]))]
    (out / "origin.json").write_text(json.dumps({
        "bounds": obounds, "shape": [rows, cols],
        "values": [round(v, 4) for v in grid.ravel().tolist()],
        "centroid": [r5(clon), r5(clat)],
        "radius_50_km": round(r50, 1), "radius_90_km": round(r90, 1),
        "time_window": win,
        "time_window_method": a.time_window_method,
        "ensemble_runs": 50, "abstain": bool(a.abstain)}))

    # --- particles.json: seeded on the slick at t0, ending in the origin cloud at t0-24h.
    # Final positions are drawn from the same anisotropic distribution the grid describes,
    # so the animation and the grid cannot drift apart.
    n = a.particles
    seed_t = rng.uniform(-1, 1, n)
    seed = np.stack([slon + seed_t * half_len_km * ex / klon,
                     slat + seed_t * half_len_km * ny / KM_PER_DEG], 1)
    seed += rng.normal(0, 0.004, (n, 2))
    fa = rng.normal(0, a.sigma * a.aspect, n)      # along-axis
    fc = rng.normal(0, a.sigma, n)                 # across-axis
    final = np.stack([clon + (fa * ex + fc * ny) / math.cos(math.radians(clat)),
                      clat + (fa * ny - fc * ex)], 1)
    k = np.linspace(0, 1, a.steps)[:, None, None]
    wobble = rng.normal(0, 0.0012, (a.steps, n, 2)) * k     # spread grows with rewind depth
    pos = seed[None, :, :] + k * (final - seed)[None, :, :] + wobble
    (out / "particles.json").write_text(json.dumps({
        "t0": iso(t0), "direction": "backward",
        "timestep_minutes": a.timestep_minutes, "n_steps": a.steps, "n_particles": n,
        "positions": np.round(pos, 5).tolist()}))

    # --- stub vessels + suspects (team rule: stub first, correct shape, garbage numbers).
    # DELETE these the moment score.py writes real ones. The MMSIs are invented and must
    # never reach a judge; every real name comes from the NOAA file.
    fleet = [("000000101", "FAKE ATLAS", "tanker", 0.00, 85),
             ("000000102", "FAKE MERIDIAN", "cargo", 0.06, 0),
             ("000000103", "FAKE PELICAN", "fishing", -0.08, 0),
             ("000000104", "FAKE CORAL", "cargo", 0.11, 0)]
    feats = []
    for mmsi, name, vtype, off, gap in fleet:
        kk = np.linspace(0, 1, 120)[:, None]
        start = np.array([clon - 0.30 + off, clat - 0.30])
        end = np.array([clon + 0.30 + off, clat + 0.30])
        track = start + kk * (end - start)
        feats.append({"type": "Feature",
                      "geometry": {"type": "LineString",
                                   "coordinates": np.round(track, 5).tolist()},
                      "properties": {"mmsi": mmsi, "name": name, "vessel_type": vtype,
                                     "n_points": 120, "max_gap_minutes": gap}})
    (out / "vessels.geojson").write_text(json.dumps(
        {"type": "FeatureCollection", "features": feats}))

    if a.abstain:
        suspects, funnel_scored = [], 0
    else:
        suspects = [
            {"source_type": "vessel", "mmsi": "000000101", "name": "FAKE ATLAS",
             "vessel_type": "tanker", "score": 0.82,
             # null is a not-applicable component, never a measured zero (frozen convention 7)
             "components": {"proximity": 0.91, "parity": None, "temporality": None,
                            "trajectory": 1.0, "gap": 1.0, "slowdown": None,
                            "type_prior": 1.0},
             "closest_km": 3.1, "closest_time": win[0], "grid_probability": 0.91,
             "heading_consistent": True, "ais_gap_minutes": 85, "edge_truncated": False,
             "reasons": ["STUB — inside the high-probability origin region during the window",
                         "STUB — 85-minute transponder gap overlapping the window"]},
            {"source_type": "vessel", "mmsi": "000000104", "name": "FAKE CORAL",
             "vessel_type": "cargo", "score": 0.41,
             "components": {"proximity": 0.44, "parity": None, "temporality": None,
                            "trajectory": 1.0, "gap": 0.0, "slowdown": None,
                            "type_prior": 1.0},
             "closest_km": 8.7, "closest_time": win[1], "grid_probability": 0.44,
             "heading_consistent": True, "ais_gap_minutes": 0, "edge_truncated": False,
             "reasons": ["STUB — inside the origin cloud, no transponder gap"]}]
        funnel_scored = len(suspects)

    (out / "suspects.json").write_text(json.dumps({
        "funnel": {"in_region": 987, "in_window": 899, "plausible": 17,
                   "scored": funnel_scored, "dropped_short_track": 15},
        "suspects": suspects,
        "dark_vessels": [], "infrastructure": [],
        "excluded": [
            {"mmsi": "000000103", "name": "FAKE PELICAN", "closest_km": 6.4,
             "reason": "STUB — heading away from the origin throughout the window"}],
        "abstained": bool(a.abstain),
        "abstain_reason": ("origin cloud too diffuse to attribute at acceptable confidence"
                           if a.abstain else None)}, indent=2))

    mb = sum(p.stat().st_size for p in out.iterdir()) / 1e6
    print(f"Wrote {out}  ({mb:.1f} MB)")
    for f in sorted(p.name for p in out.iterdir()):
        print("  ", f)
    print(f"\norigin  centroid {r5(clon)}, {r5(clat)}   "
          f"aspect {a.aspect:.1f}:1 on bearing {a.axis_deg:.0f} deg")
    print(f"        r50 {r50:.1f} km   r90 {r90:.1f} km   abstain={bool(a.abstain)}")
    print(f"        window {win[0]}  ->  {win[1]}")
    if r90 > 40 and not a.abstain:
        print("  WARNING: radius_90_km > 40 km is the agreed abstain trigger, but abstain "
              "is false — Stage 3 would refuse against this bundle")
    print(f"\nNow run:  python scripts/validate_case.py {out}")


if __name__ == "__main__":
    main()
