#!/usr/bin/env python3
"""
make_case000.py — generate the fake case bundle.

    python scripts/make_case000.py                    # writes cases/case-000/
    python scripts/make_case000.py --out cases/case-000 --particles 3000 --steps 97

This is the CONTRACT MADE CONCRETE. Harshita builds the entire frontend against
it before any real pipeline exists; Anushka and Jaiveer read its detections and
origin grid as stand-in inputs. Numbers are invented, shapes are exact.

Deliberately full-size (3000 particles x 97 steps) so the Monday stutter test is
an honest test of the real workload.

Regenerate rather than hand-editing. Requires numpy + Pillow.
"""
import argparse
import json
import math
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
from PIL import Image

# Ennore-ish, so the fake bundle geolocates where the real hero case will
WEST, SOUTH, EAST, NORTH = 80.10, 12.95, 80.70, 13.55
T0 = datetime(2017, 1, 29, 0, 14, tzinfo=timezone.utc)


def iso(dt):
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def r5(x):
    return round(float(x), 5)


def make_sar(path, w, h, rng):
    """Speckled sea, a land wedge, a dark linear slick and a dark blob."""
    img = rng.gamma(shape=4.0, scale=26.0, size=(h, w))          # sea speckle
    yy, xx = np.mgrid[0:h, 0:w]

    land = (xx + yy * 0.55) < w * 0.20                            # coast, west side
    img[land] = rng.gamma(4.0, 34.0, size=land.sum())

    ang = math.radians(-24)
    cx, cy = w * 0.56, h * 0.40
    u = (xx - cx) * math.cos(ang) + (yy - cy) * math.sin(ang)
    v = -(xx - cx) * math.sin(ang) + (yy - cy) * math.cos(ang)
    slick = (u / (w * 0.16)) ** 2 + (v / (h * 0.018)) ** 2 < 1.0  # linear = oil
    img[slick] *= 0.30

    blob = ((xx - w * 0.27) / (w * 0.075)) ** 2 + ((yy - h * 0.70) / (h * 0.065)) ** 2 < 1.0
    img[blob] *= 0.45                                             # rounded = look-alike

    img = np.clip(img, 0, 255).astype(np.uint8)
    Image.fromarray(img, mode="L").save(path)


def px2ll(px, py, w, h):
    """Pixel (0,0) is top-left = (west, north). Master section 4."""
    return [r5(WEST + (px / w) * (EAST - WEST)),
            r5(NORTH - (py / h) * (NORTH - SOUTH))]


def ellipse_ring(cx, cy, a, b, ang, w, h, n=40):
    ring = []
    for i in range(n + 1):
        t = 2 * math.pi * i / n
        dx, dy = a * math.cos(t), b * math.sin(t)
        ring.append(px2ll(cx + dx * math.cos(ang) - dy * math.sin(ang),
                          cy + dx * math.sin(ang) + dy * math.cos(ang), w, h))
    ring[-1] = ring[0]
    return ring


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="cases/case-000")
    ap.add_argument("--case-id", default=None,
                    help="meta.json/case_id; defaults to the output directory name")
    ap.add_argument("--scene-only", action="store_true",
                    help="write only meta.json + bounds.json + sar.png — the state a real case "
                         "starts in, before any stage has run. Used by the end-to-end seam test.")
    ap.add_argument("--particles", type=int, default=3000)
    ap.add_argument("--steps", type=int, default=97)
    ap.add_argument("--px", type=int, default=1400)
    ap.add_argument("--seed", type=int, default=143)
    a = ap.parse_args()

    out = Path(a.out)
    case_id = a.case_id or out.name
    out.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(a.seed)
    W = H = a.px

    # ---- sar.png + bounds.json
    make_sar(out / "sar.png", W, H, rng)
    (out / "bounds.json").write_text(json.dumps(
        {"west": WEST, "south": SOUTH, "east": EAST, "north": NORTH,
         "width_px": W, "height_px": H,
         # the clamp the 8-bit PNG was written with, so Stage 1 maps it back to dB
         # with the same numbers (docs/TRAPS.md #7)
         "db_min": -25, "db_max": 0}, indent=2))

    # ---- meta.json  (all three acts, so the frontend exercises every panel)
    (out / "meta.json").write_text(json.dumps({
        "case_id": case_id, "title": "FAKE bundle — contract reference only",
        "satellite": "Sentinel-1A (fake)", "scene_id": "FAKE-000",
        "detection_time": iso(T0),
        "acts_available": ["detect", "trace", "attribute"],
        "notes": "Synthetic. Never shown to a judge. Regenerate with scripts/make_case000.py."
    }, indent=2))

    if a.scene_only:
        print(f"Wrote {out} (scene only: meta.json, bounds.json, sar.png)")
        print("No stage outputs — run the pipeline stubs to fill them in.")
        return

    # ---- detections.geojson
    slick_c = (W * 0.56, H * 0.40)
    dets = [{
        "type": "Feature",
        "geometry": {"type": "Polygon",
                     "coordinates": [ellipse_ring(*slick_c, W * 0.16, H * 0.018,
                                                  math.radians(-24), W, H)]},
        "properties": {"id": "det-01", "classification": "oil", "confidence": 0.87,
                       "area_km2": 12.4, "elongation": 8.2, "edge_gradient": 0.34,
                       "contrast_db": -6.2, "shape_class": "linear",
                       "centroid": px2ll(*slick_c, W, H)}
    }, {
        "type": "Feature",
        "geometry": {"type": "Polygon",
                     "coordinates": [ellipse_ring(W * 0.27, H * 0.70, W * 0.075, H * 0.065,
                                                  0.0, W, H)]},
        "properties": {"id": "det-02", "classification": "lookalike", "confidence": 0.71,
                       "area_km2": 7.9, "elongation": 1.4, "edge_gradient": 0.11,
                       "contrast_db": -3.1, "shape_class": "blob",
                       "centroid": px2ll(W * 0.27, H * 0.70, W, H)}
    }]
    (out / "detections.geojson").write_text(json.dumps(
        {"type": "FeatureCollection", "features": dets}))

    # ---- particles.json : seeded along the slick axis, drifting back NE
    n, steps = a.particles, a.steps
    c = np.array(px2ll(*slick_c, W, H))
    # The polygon (ellipse_ring) and SAR image (make_sar) tilt the slick -24 deg in PIXEL
    # space; px2ll then flips pixel-y (which points south), so the slick's axis is +24 deg
    # in lon/lat. Seed along +24 deg here so the cloud lies ALONG the slick at T-0 — seeding
    # at -24 deg mirrors it and the cloud crosses the slick in an X (bounds are square, so
    # deg/px is equal on both axes and this angle maps 1:1).
    axis = math.radians(24)
    t = rng.uniform(-1, 1, n)
    seed = c + np.stack([t * 0.052 * math.cos(axis), t * 0.052 * math.sin(axis)], 1) \
             + rng.normal(0, 0.0016, (n, 2))
    drift = np.array([0.0022, 0.0016])                      # deg per 15-min step
    pos, cur = [], seed.copy()
    for s in range(steps):
        pos.append(np.round(cur, 5).tolist())
        # spread grows with rewind depth — the honest bit the demo shows
        cur = cur + drift + rng.normal(0, 0.00042 * (1 + 2.2 * s / steps), (n, 2))
    (out / "particles.json").write_text(json.dumps({
        "t0": iso(T0), "direction": "backward", "timestep_minutes": 15,
        "n_steps": steps, "n_particles": n, "positions": pos}))

    # ---- origin.json : gaussian blob at the final particle centroid
    fin = np.array(pos[-1])
    oc = fin.mean(0)
    gw = gh = 120
    ow, oe = oc[0] - 0.30, oc[0] + 0.30
    os_, on = oc[1] - 0.30, oc[1] + 0.30
    gx = np.linspace(ow, oe, gw)[None, :]
    gy = np.linspace(on, os_, gh)[:, None]                  # row 0 = north
    klat = math.cos(math.radians(float(oc[1])))
    d2 = (((gx - oc[0]) * klat) ** 2 + (gy - oc[1]) ** 2)
    grid = np.exp(-d2 / (2 * 0.075 ** 2))
    grid /= grid.max()
    (out / "origin.json").write_text(json.dumps({
        "bounds": {"west": r5(ow), "south": r5(os_), "east": r5(oe), "north": r5(on)},
        "shape": [gh, gw], "values": [round(v, 4) for v in grid.ravel().tolist()],
        "centroid": [r5(oc[0]), r5(oc[1])],
        "radius_50_km": 4.2, "radius_90_km": 11.8,
        "time_window": [iso(T0 - timedelta(hours=20)), iso(T0 - timedelta(hours=8))],
        "ensemble_runs": 50, "abstain": False}))

    # ---- vessels.geojson + suspects.json
    fleet = [("367000101", "FAKE ATLAS", "tanker", 0.0), ("367000102", "FAKE MERIDIAN", "cargo", 0.09),
             ("367000103", "FAKE PELICAN", "fishing", -0.11), ("367000104", "FAKE CORAL", "cargo", 0.17),
             ("367000105", "FAKE VESPER", "tanker", -0.19)]
    feats = []
    for mmsi, name, vtype, off in fleet:
        k = np.linspace(0, 1, 220)[:, None]
        start = np.array([oc[0] - 0.34, oc[1] - 0.24 + off])
        end = np.array([oc[0] + 0.34, oc[1] + 0.20 + off])
        track = start + k * (end - start) + np.stack(
            [np.sin(k[:, 0] * 5) * 0.012, np.cos(k[:, 0] * 4) * 0.010], 1)
        feats.append({"type": "Feature",
                      "geometry": {"type": "LineString",
                                   "coordinates": np.round(track, 5).tolist()},
                      "properties": {"mmsi": mmsi, "name": name, "vessel_type": vtype,
                                     "n_points": 220,
                                     "max_gap_minutes": 85 if mmsi == "367000101" else 12}})
    (out / "vessels.geojson").write_text(json.dumps(
        {"type": "FeatureCollection", "features": feats}))

    (out / "suspects.json").write_text(json.dumps({
        "funnel": {"in_region": 412, "in_window": 63, "plausible": 12, "scored": 3},
        "suspects": [
            {"mmsi": "367000101", "name": "FAKE ATLAS", "vessel_type": "tanker", "score": 0.82,
             "closest_km": 3.1, "closest_time": iso(T0 - timedelta(hours=14)),
             "heading_consistent": True, "ais_gap_minutes": 85,
             "reasons": ["inside the 50% origin radius during the window",
                         "85-minute transponder gap overlapping the window",
                         "tanker on a course consistent with the origin"]},
            {"mmsi": "367000104", "name": "FAKE CORAL", "vessel_type": "cargo", "score": 0.44,
             "closest_km": 8.7, "closest_time": iso(T0 - timedelta(hours=17)),
             "heading_consistent": True, "ais_gap_minutes": 0,
             "reasons": ["inside the 90% origin radius", "no transponder gap"]},
            {"mmsi": "367000102", "name": "FAKE MERIDIAN", "vessel_type": "cargo", "score": 0.28,
             "closest_km": 11.2, "closest_time": iso(T0 - timedelta(hours=11)),
             "heading_consistent": False, "ais_gap_minutes": 0,
             "reasons": ["at the edge of the 90% origin radius"]}],
        "excluded": [
            {"mmsi": "367000103", "name": "FAKE PELICAN", "closest_km": 6.4,
             "reason": "heading away from the origin throughout the window"},
            {"mmsi": "367000105", "name": "FAKE VESPER", "closest_km": 9.9,
             "reason": "left the region before the origin time window opened"}]
    }, indent=2))

    files = sorted(p.name for p in out.iterdir())
    mb = sum(p.stat().st_size for p in out.iterdir()) / 1e6
    print(f"Wrote {out}  ({mb:.1f} MB)")
    for f in files:
        print("  ", f)
    print("\nNow run:  python scripts/validate_case.py", out)


if __name__ == "__main__":
    main()
