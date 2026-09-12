#!/usr/bin/env python3
"""
plot_detections.py — the human gate.  Owner: Soum.

    python scripts/plot_detections.py --case case-huntington-2021

Draws detections.geojson over the case's SAR raster. This is the check the
validator cannot do: it will happily PASS a mirrored polygon, an upside-down
grid, or an origin sitting upstream-backwards, because a mirror image shares a
centroid (Master section 8.4). A bundle is not integrated until a person has
looked at this picture.

Oil is red, look-alikes grey, ship detections cyan crosses. The title carries
the hemisphere check so a [lat, lon] swap is visible without squinting.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

REPO = Path(__file__).resolve().parents[1]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--case", required=True)
    ap.add_argument("--cases-root", default=str(REPO / "cases"))
    ap.add_argument("--geojson", default=None,
                    help="defaults to the case bundle's detections.geojson")
    ap.add_argument("--out", default=None)
    a = ap.parse_args()

    case_dir = Path(a.cases_root) / a.case
    bounds = json.loads((case_dir / "bounds.json").read_text())
    gj_path = Path(a.geojson) if a.geojson else (case_dir / "detections.geojson")
    gj = json.loads(gj_path.read_text())

    # Prefer the real dB GeoTIFF for the backdrop; fall back to the display PNG.
    tif = case_dir / "sar_vv_vh.tif"
    if tif.exists():
        import rasterio
        with rasterio.open(tif) as src:
            img = src.read(1).astype(np.float32)
            extent_src = "sar_vv_vh.tif VV (dB)"
        v = img[np.isfinite(img) & (img != 0)]
        vmin, vmax = np.percentile(v, 2), np.percentile(v, 98)
    else:
        from PIL import Image
        img = np.asarray(Image.open(case_dir / "sar.png").convert("L")).astype(np.float32)
        vmin, vmax = 0, 255
        extent_src = "sar.png (8-bit display)"

    # Plot in GEOGRAPHIC coordinates, not pixels. A pixel-space plot would look
    # fine even if the lon/lat conversion were wrong, which is the whole point
    # of this check.
    extent = [bounds["west"], bounds["east"], bounds["south"], bounds["north"]]

    fig, ax = plt.subplots(figsize=(11, 11))
    ax.imshow(img, cmap="gray", vmin=vmin, vmax=vmax, extent=extent,
              origin="upper", aspect="auto")

    n_oil = n_look = 0
    for f in gj.get("features", []):
        p = f["properties"]
        is_oil = p["classification"] == "oil"
        n_oil += is_oil
        n_look += (not is_oil)
        # Look-alikes are drawn amber, not grey: grey outlines are invisible
        # against grey sea, and a rejected candidate you cannot see is a
        # rejection you cannot check.
        colour = "#ff2d2d" if is_oil else "#ffb000"
        for ring in f["geometry"]["coordinates"]:
            arr = np.asarray(ring, dtype=float)
            ax.plot(arr[:, 0], arr[:, 1], "-" if is_oil else "--", color=colour,
                    lw=1.9 if is_oil else 1.0, alpha=0.95)
        clon, clat = p["centroid"]
        ax.plot(clon, clat, "+", color=colour, ms=9, mew=1.6)
        ax.annotate(f"{p['id']} {p['confidence']:.2f} {p['contrast_db']:+.1f}dB"
                    + (f" {p['discharge_class']}" if is_oil else ""),
                    (clon, clat), color=colour, fontsize=7,
                    xytext=(4, 4), textcoords="offset points")

    ships = []
    for f in gj.get("features", []):
        ships = f["properties"].get("ship_detections") or ships
        if ships:
            break
    if ships:
        ax.plot([s["lon"] for s in ships], [s["lat"] for s in ships],
                "x", color="#00e5ff", ms=7, mew=1.4, label=f"{len(ships)} radar contacts")
        ax.legend(loc="lower right", framealpha=0.7)

    hemi = (f"{'E' if bounds['west'] > 0 else 'W'} / "
            f"{'N' if bounds['south'] > 0 else 'S'}")
    ax.set_title(f"{a.case}  —  {extent_src}\n"
                 f"{n_oil} oil (red), {n_look} look-alike (amber), {len(ships)} ships (cyan)  "
                 f"·  hemisphere {hemi}  ·  "
                 f"lon {bounds['west']}..{bounds['east']}  lat {bounds['south']}..{bounds['north']}",
                 fontsize=10)
    ax.set_xlabel("longitude"); ax.set_ylabel("latitude")
    ax.grid(alpha=0.15, color="cyan", lw=0.4)

    out = Path(a.out) if a.out else (REPO / "scratch" / f"check_{a.case}.png")
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(out, dpi=130)
    print(f"wrote {out}")
    print(f"  {n_oil} oil, {n_look} look-alike, {len(ships)} ship detections")
    print("  CHECK: do the outlines sit on dark water? are the coordinates in "
          "the right hemisphere? is anything mirrored?")


if __name__ == "__main__":
    main()
