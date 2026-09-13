#!/usr/bin/env python3
"""
Phase 2 checkpoint picture. Owner: Anushka.

    python pipeline/drift/plot_quiver.py --case case-000

Draws the cached field so a human can answer the only question that matters at the end of
Phase 2: *could the real ocean do this?* Wrong-but-running code is this component's failure
mode, and ten seconds of looking catches what an afternoon of reading will not.

Coastline note: HYCOM masks land, so the NaN pattern in the current field IS the coastline --
no cartopy, no shapefile, no extra dependency. If the grey blob does not look like the
Coromandel coast, the longitude/latitude axes are swapped. (docs/TRAPS.md #1)

What to look for:
  1. Grey land on the WEST, ocean on the east. Chennai coast runs roughly north-south.
  2. Arrows under ~1.5 m/s, and not all marching into the land.
  3. Arrows change smoothly across the picture -- a random-looking field means the grid
     reshape is scrambled.
  4. The red slick outline sits in the water, not inland.
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


def slick_outline(case_id):
    """Highest-confidence oil polygon from the case bundle, for scale and orientation.

    Returns (ring_or_None, source_label, note). The note is the point: this used to return a
    bare None when there was no detections.geojson, so the outline silently vanished while the
    closing guidance still told you to check that "the red slick outline sits in water". A
    sanity check you cannot see is worse than no sanity check, because you tick it off anyway.

    Falls back to cerulean_slick.geojson where a case carries one -- SkyTruth's reference
    polygon for the same feature. It is drawn in a DIFFERENT colour and labelled as theirs.
    It is a comparison target, NOT ground truth and NOT a NAAP detection (docs/ANSWERS.README),
    and nothing may ever seed from it.
    """
    path = REPO / "cases" / case_id / "detections.geojson"
    if not path.exists():
        cer = REPO / "cases" / case_id / "cerulean_slick.geojson"
        if cer.exists():
            fc = json.loads(cer.read_text())
            feats = fc.get("features") or []
            if feats:
                geom = feats[0]["geometry"]
                c = geom["coordinates"]
                ring = c[0] if geom["type"] == "Polygon" else c[0][0]
                return (np.array(ring), "cerulean",
                        "no detections.geojson yet -- drawing SkyTruth Cerulean's REFERENCE "
                        "polygon instead. It is not a NAAP detection and nothing seeds from it.")
        return (None, None,
                "no detections.geojson for this case, so NO slick outline is drawn. "
                "Stage 1 has not delivered yet -- do not read this plot as if the slick "
                "were shown on it.")
    fc = json.loads(path.read_text())
    # The property is "classification", not "class" (docs/CONTRACTS.md). This read the wrong
    # key until 2026-09-07: `.get("class", "oil")` returned the default for EVERY feature, so
    # the filter passed look-alikes too and the plot outlined whichever feature happened to
    # have the highest confidence. On case-000 that is the oil one, so it looked correct.
    oil = [f for f in fc.get("features", [])
           if (f.get("properties") or {}).get("classification") == "oil"]
    if not oil:
        return (None, None,
                "detections.geojson has ZERO oil features, so no outline is drawn. That is "
                "the no-spill / look-alike state and it is a designed answer, not a failure.")
    best = max(oil, key=lambda f: f.get("properties", {}).get("confidence", 0))
    geom = best["geometry"]
    ring = geom["coordinates"][0] if geom["type"] == "Polygon" else geom["coordinates"][0][0]
    return np.array(ring), "naap", None


def main():
    ap = argparse.ArgumentParser(description="Quiver sanity plot for the cached field")
    ap.add_argument("--case", default="case-000")
    ap.add_argument("--out", default=None, help="default pipeline/drift/out/quiver_<case>.png")
    a = ap.parse_args()

    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    f = load_case_field(a.case)
    t0 = datetime.fromtimestamp(int(np.load(f.path)["t0_epoch"]), tz=timezone.utc)
    print(f"  {f}")
    print(f"  detection_time {t0:%Y-%m-%d %H:%MZ}")

    LON, LAT = np.meshgrid(f.clon, f.clat)
    u, v = f.cu[-1], f.cv[-1]                      # slice nearest detection_time
    spd = np.hypot(u, v)
    land = ~np.isfinite(spd)

    wLON, wLAT = np.meshgrid(f.wlon, f.wlat)
    wu, wv = f.wu[-1], f.wv[-1]

    fig, axes = plt.subplots(1, 2, figsize=(15, 7), sharex=True, sharey=True)

    for ax, title in zip(axes, ["Surface current (HYCOM)", "10 m wind (ERA5)"]):
        ax.pcolormesh(LON, LAT, np.where(land, 1.0, np.nan),
                      cmap="Greys", vmin=0, vmax=1.6, shading="auto")
        ax.set_aspect(1.0 / np.cos(np.deg2rad(float(f.clat.mean()))))
        ax.set_xlabel("longitude (E)")
        ax.set_title(title)
        ring, ring_src, ring_note = slick_outline(a.case)
        if ring is not None:
            colour = "crimson" if ring_src == "naap" else "deepskyblue"
            label = ("NAAP detection" if ring_src == "naap"
                     else "Cerulean reference (NOT a NAAP detection)")
            ax.plot(ring[:, 0], ring[:, 1], color=colour, lw=1.8, zorder=5, label=label)
            ax.legend(loc="lower left", fontsize=7.5, framealpha=0.85)
    axes[0].set_ylabel("latitude (N)")

    q = axes[0].quiver(LON, LAT, u, v, spd, cmap="viridis", clim=(0, 1.2),
                       scale=12, width=0.004, zorder=3)
    fig.colorbar(q, ax=axes[0], label="current speed (m/s)", shrink=0.8)

    wspd = np.hypot(wu, wv)
    q2 = axes[1].quiver(wLON, wLAT, wu, wv, wspd, cmap="plasma", clim=(0, 10),
                        scale=120, width=0.005, zorder=3)
    fig.colorbar(q2, ax=axes[1], label="wind speed (m/s)", shrink=0.8)

    fin = spd[np.isfinite(spd)]
    fig.suptitle(f"{a.case} — field at detection time {t0:%Y-%m-%d %H:%MZ}   |   "
                 f"current median {np.median(fin):.2f}, max {fin.max():.2f} m/s   |   "
                 f"wind median {np.median(wspd):.1f} m/s", fontsize=11)

    out = Path(a.out) if a.out else HERE / "out" / f"quiver_{a.case}.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(out, dpi=130, bbox_inches="tight")
    print(f"\n  wrote {out.relative_to(REPO)}")
    print("\n  Look for: land shaded grey on the correct side, arrows not marching inland,")
    print("  and a smoothly varying field. Work out the expected upstream direction for THIS")
    print("  case before you run it (docs/team/anushka-stage2-drift.md Phase 5.3), then compare.")
    if ring is None:
        print(f"\n  !! NO SLICK OUTLINE: {ring_note}")
    elif ring_src == "cerulean":
        print(f"\n  !! OUTLINE IS NOT OURS: {ring_note}")
    else:
        print("  The crimson outline is NAAP's own highest-confidence oil detection.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
