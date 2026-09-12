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


class WrongCase(SystemExit):
    """Raised when out/ holds a different case's run than the one being plotted."""


def assert_belongs_to_case(case_id, origin, parts, src):
    """Refuse to plot one case's cloud under another case's name.

    THE BUG THIS EXISTS FOR (2026-09-12). `out/origin.json` and `out/particles.json` are NOT
    case-scoped: run.py writes them to a single shared directory, so every case overwrites the
    last. Meanwhile --case here controls the FIELD, the SLICK OUTLINE and the OUTPUT FILENAME.
    So `plot_heatmap.py --case case-jacksonville-2024` cheerfully rendered a leftover Ennore
    cloud -- centroid 80.6 E, 13.7 N -- on Jacksonville's field at -79.6 W, and wrote it to
    heatmap_case-jacksonville-2024.png. 160 degrees of longitude apart, and nothing tripped.

    This is the same shape as the `--case case-gulf-2019` cache mixup that cost an evening on
    2026-09-07: an argument that labels the output without selecting the data. That one was
    fixed by re-deriving the box and time from the bundle and refusing a cache that disagreed.
    This is the same fix applied to the plot.

    Two checks, both from guarantees the contract already makes:
      1. CONTRACTS.md 6.4 -- particles.t0 must match meta.detection_time within 60 s. Seven
         years apart is not a rounding error.
      2. The origin centroid has to sit inside the field box the particles were integrated
         through. It cannot be somewhere the field does not exist.
    """
    meta_path = REPO / "cases" / case_id / "meta.json"
    if not meta_path.exists():
        raise WrongCase(f"no meta.json for {case_id} at {meta_path}")
    meta = json.loads(meta_path.read_text())
    want = datetime.fromisoformat(meta["detection_time"].replace("Z", "+00:00"))
    got = datetime.fromisoformat(str(parts["t0"]).replace("Z", "+00:00"))
    if abs((got - want).total_seconds()) > 60:
        raise WrongCase(
            f"{src / 'particles.json'} was produced for t0 {got:%Y-%m-%dT%H:%M:%SZ}, but "
            f"{case_id}'s detection_time is {want:%Y-%m-%dT%H:%M:%SZ}.\n"
            f"  out/ is NOT case-scoped -- it still holds a different case's run, and plotting "
            f"it would label that cloud {case_id}.\n"
            f"  Run the case first:\n"
            f"    python pipeline/drift/run.py --case {case_id} --real --particles 3000 --runs 50")

    clon, clat = float(origin["centroid"][0]), float(origin["centroid"][1])
    b = json.loads((REPO / "cases" / case_id / "bounds.json").read_text())
    # generous: the origin legitimately sits mostly OFF the SAR scene, so allow 5 degrees
    pad = 5.0
    if not (b["west"] - pad <= clon <= b["east"] + pad
            and b["south"] - pad <= clat <= b["north"] + pad):
        raise WrongCase(
            f"origin centroid ({clon:.4f}, {clat:.4f}) is nowhere near {case_id}, whose scene "
            f"box is [W {b['west']}, S {b['south']}, E {b['east']}, N {b['north']}].\n"
            f"  An origin cloud sitting mostly off-scene is normal and expected; being on "
            f"another ocean is not.\n"
            f"  out/ holds a different case's run.")


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
    assert_belongs_to_case(a.case, origin, parts, src)
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

    # Where did the origin land relative to the slick? The one number that says whether the
    # rewind went upstream or downstream, which is the check that actually matters.
    seed0 = pos[0]
    slick_c = (float(seed0[:, 0].mean()), float(seed0[:, 1].mean()))
    dx = (clon - slick_c[0]) * np.cos(np.deg2rad(clat)) * KM_PER_DEG
    dy = (clat - slick_c[1]) * KM_PER_DEG
    sep_km = float(np.hypot(dx, dy))
    bearing = float((np.degrees(np.arctan2(dx, dy)) + 360.0) % 360.0)

    out = Path(a.out) if a.out else HERE / "out" / f"heatmap_{a.case}.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(out, dpi=130, bbox_inches="tight")
    print(f"  wrote {out}")
    print(f"  centroid ({clon:.4f}, {clat:.4f})  r50 {r50:.1f} km  r90 {r90:.1f} km  "
          f"abstain={origin['abstain']}")
    print(f"  release window {tw[0]} -> {tw[1]}  ({method})")
    # The expected direction is PER CASE and lives in 03_ANUSHKA_DRIFT.md Phase 5.3. It used
    # to be hardcoded here as "NORTH-EAST ... upstream of a southward current", which is
    # Ennore's answer printed for every case -- worse than useless under the blind protocol,
    # because it tells you what to expect regardless of which case you ran.
    print(f"\n  Judge it: a coherent blob, in water, tens of km wide, and UPSTREAM of the")
    print(f"  slick for THIS case's current regime -- work out which way that is from the")
    print(f"  quiver before you look, not after. Expected direction per case: Phase 5.3.")
    print(f"  Slick centre ({slick_c[0]:.4f}, {slick_c[1]:.4f}) -> origin "
          f"({clon:.4f}, {clat:.4f}): bearing {bearing:.0f} deg, {sep_km:.1f} km.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
