#!/usr/bin/env python3
"""
Phase 3 checkpoint picture. Owner: Anushka.

    python pipeline/drift/plot_heatmap.py --case case-000

The Phase 3 brief asks for exactly one thing before the files are handed over: a heatmap that
shows **a coherent cloud — not uniform noise, not a single pixel — sitting offshore**, with the
radii printed. This draws it, and draws it next to the context that makes it judgeable.

LEFT   the whole case region: land, the slick outline, a sample of control-run trajectories
       rewinding backwards, and the origin cloud where they end up.
RIGHT  the origin grid alone, as `origin.json` actually stores it (row 0 = north), with the
       50% and 90% circles drawn on top.

WHAT TO LOOK FOR
  1. The cloud is a blob, not a scatter of unrelated specks and not one hot pixel.
  2. It sits in WATER. An origin on land means the oil was released by a truck.
  3. It sits UPSTREAM: the current runs south along this coast, so rewinding 24 h must travel
     north-east of the slick. If the cloud is downstream, the sign of dt is wrong.
  4. r90 is tens of km, not hundreds and not metres.
  5. The trajectories fan out gradually. A sharp kink is a field-interpolation bug.
"""
import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(HERE))

from fields import load_case_field

KM_PER_DEG = 111.32


def slick_outline(case_id):
    path = REPO / "cases" / case_id / "detections.geojson"
    if not path.exists():
        return None
    fc = json.loads(path.read_text())
    oil = [f for f in fc.get("features", [])
           if (f.get("properties") or {}).get("classification") == "oil"]
    if not oil:
        return None
    best = max(oil, key=lambda f: f["properties"].get("confidence", 0))
    geom = best["geometry"]
    ring = geom["coordinates"][0] if geom["type"] == "Polygon" else geom["coordinates"][0][0]
    return np.array(ring)


def circle(lon, lat, radius_km, n=180):
    """A circle of constant GROUND radius, which is an ellipse in degrees away from the
    equator. Drawing it as a plain degree-circle would overstate the east-west extent."""
    th = np.linspace(0, 2 * np.pi, n)
    dlat = radius_km / KM_PER_DEG
    dlon = dlat / max(np.cos(np.radians(lat)), 1e-6)
    return lon + dlon * np.cos(th), lat + dlat * np.sin(th)


def main():
    ap = argparse.ArgumentParser(description="Phase 3 checkpoint: the origin cloud")
    ap.add_argument("--case", default="case-000")
    ap.add_argument("--src", default=None, help="directory holding particles.json/origin.json")
    ap.add_argument("--out", default=None, help="default out/heatmap_<case>.png")
    ap.add_argument("--tracks", type=int, default=120, help="control trajectories to draw")
    a = ap.parse_args()

    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    src = Path(a.src) if a.src else HERE / "out"
    origin = json.loads((src / "origin.json").read_text())
    parts = json.loads((src / "particles.json").read_text())
    grid = np.asarray(origin["values"], dtype=float).reshape(origin["shape"])
    b = origin["bounds"]
    clon, clat = origin["centroid"]
    r50, r90 = origin["radius_50_km"], origin["radius_90_km"]

    pos = np.asarray(parts["positions"], dtype=float)          # [n_steps, n, 2]
    step = max(1, pos.shape[1] // a.tracks)
    tracks = pos[:, ::step, :]

    field = load_case_field(a.case, repo_root=REPO)
    spd = np.hypot(field.cu[-1], field.cv[-1])
    land = ~np.isfinite(spd)
    LON, LAT = np.meshgrid(field.clon, field.clat)
    ring = slick_outline(a.case)
    aspect = 1.0 / np.cos(np.deg2rad(clat))

    fig, (axL, axR) = plt.subplots(1, 2, figsize=(15.5, 7.2))

    # ---------------------------------------------------------------- left: the context
    axL.pcolormesh(LON, LAT, np.where(land, 1.0, np.nan),
                   cmap="Greys", vmin=0, vmax=1.6, shading="auto")
    axL.plot(tracks[:, :, 0], tracks[:, :, 1], color="#3b82f6", lw=0.35, alpha=0.30,
             zorder=2)
    # Per-cell alpha, not a hard mask. Over the map an unmasked grid paints a black
    # rectangle that hides the coastline, and a hard mask leaves a dark fringe of
    # just-above-threshold cells that reads as a second, non-existent cloud. Fading each
    # cell by its own probability shows the tail honestly without either artefact.
    axL.imshow(grid, extent=[b["west"], b["east"], b["south"], b["north"]],
               origin="upper", cmap="inferno", zorder=3, interpolation="bilinear",
               alpha=np.clip(grid * 1.6, 0.0, 1.0) * 0.92)
    if ring is not None:
        axL.plot(ring[:, 0], ring[:, 1], color="crimson", lw=2.0, zorder=6)
        axL.plot([], [], color="crimson", lw=2.0, label="slick at t0 (detection)")
    axL.plot(clon, clat, "x", color="white", ms=11, mew=2.5, zorder=7)
    axL.plot([], [], color="#3b82f6", lw=1.2, label="control run, rewinding 24 h")
    axL.plot([], [], color="#f59e0b", lw=2.0, label="origin cloud (50 runs)")
    # Frame the action (slick + cloud) with enough margin to keep the coast in shot, rather
    # than the whole downloaded box -- most of which is empty ocean nobody needs to see.
    xs = [b["west"], b["east"], clon]
    ys = [b["south"], b["north"], clat]
    if ring is not None:
        xs += [float(ring[:, 0].min()), float(ring[:, 0].max())]
        ys += [float(ring[:, 1].min()), float(ring[:, 1].max())]
    mx, my = 0.35, 0.25
    axL.set_xlim(max(field.clon.min(), min(xs) - mx), min(field.clon.max(), max(xs) + mx))
    axL.set_ylim(max(field.clat.min(), min(ys) - my), min(field.clat.max(), max(ys) + my))
    axL.set_aspect(aspect)
    axL.set_xlabel("longitude (E)")
    axL.set_ylabel("latitude (N)")
    axL.set_title("Where the oil came from — whole scene")
    axL.legend(loc="lower left", fontsize=8, framealpha=0.9)

    # ---------------------------------------------------------------- right: the grid
    im = axR.imshow(grid, extent=[b["west"], b["east"], b["south"], b["north"]],
                    origin="upper", cmap="inferno", interpolation="nearest")
    fig.colorbar(im, ax=axR, label="normalised probability", shrink=0.85)
    for r, style, lab in ((r50, "-", f"50% — {r50:.1f} km"), (r90, "--", f"90% — {r90:.1f} km")):
        x, y = circle(clon, clat, r)
        axR.plot(x, y, style, color="#22d3ee", lw=1.8, label=lab)
    axR.plot(clon, clat, "x", color="white", ms=11, mew=2.5)
    axR.set_aspect(aspect)
    axR.set_xlabel("longitude (E)")
    axR.set_title(f"origin.json as stored — {origin['shape'][0]}x{origin['shape'][1]}, "
                  f"row 0 = north")
    axR.legend(loc="upper right", fontsize=9)

    tw = origin["time_window"]
    method = origin.get("time_window_method", "?")
    nonzero = float((grid > 0.05).mean() * 100)
    fig.suptitle(
        f"{a.case} — origin cloud from {origin['ensemble_runs']} runs x "
        f"{parts['n_particles']} particles   |   centroid ({clon:.4f}, {clat:.4f})   |   "
        f"r50 {r50:.1f} km, r90 {r90:.1f} km   |   abstain={origin['abstain']}\n"
        f"release window {tw[0]} -> {tw[1]}  ({method})   |   "
        f"{nonzero:.0f}% of the grid carries >5% probability",
        fontsize=10.5)

    out = Path(a.out) if a.out else HERE / "out" / f"heatmap_{a.case}.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(out, dpi=130, bbox_inches="tight")
    print(f"  wrote {out}")
    print(f"  centroid ({clon:.4f}, {clat:.4f})  r50 {r50:.1f} km  r90 {r90:.1f} km  "
          f"abstain={origin['abstain']}")
    print(f"  release window {tw[0]} -> {tw[1]}  ({method})")
    print("\n  Judge it: a coherent blob, in water, NORTH-EAST of the slick (upstream of a")
    print("  southward current), tens of km wide. Anything else is a bug, not a finding.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
