#!/usr/bin/env python3
"""
Stage 1 - IoU against Cerulean's reference polygons.  Owner: Soumirya.

    python pipeline/detect/iou_cerulean.py --all

Rasterises our 'oil' detections and Cerulean's slick polygon onto the SAME scene
grid (the GeoTIFF's own affine) and reports intersection-over-union per case.

WHAT THIS NUMBER IS, AND IS NOT. Cerulean is an operational detector, not ground
truth, and SkyTruth state plainly that SAR alone cannot definitively identify oil
- the note carried in every one of these files says exactly that. So this is
agreement between two independent detectors on the same acquisition, which is a
far more honest claim than "accuracy" and is still the strongest external number
Stage 1 has. Where we disagree, the polygon is not automatically right.

case-gulf-alaska-2023 was classed AMBIGUOUS by Cerulean's own human reviewer. A
poor IoU there is the EXPECTED result and is reported, never hidden (A6, D2b).

WHY A SHARED RASTER AND NOT A VECTOR INTERSECTION. shapely would give an exact
polygon intersection, but our detections are pixel regions traced to contours, so
a vector intersection measures contour-tracing artefacts as much as real
disagreement. Rasterising both onto the detector's own grid compares them in the
units the detector actually works in, and matches how evaluate.py scores the
U-Net, so the two IoU numbers in the deck mean the same thing.

BLIND-EVALUATION ORDER (A6). These polygons stayed sealed until every detection
was committed AND pushed. Nothing here may be used to re-tune a threshold: this
script reads detections.geojson, it never writes one.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import rasterio
from rasterio.features import rasterize

ROOT = Path(__file__).resolve().parents[2]
CASES = ROOT / "cases"

# The five bundles carrying a reference polygon, in presentation order.
DEFAULT_CASES = ["case-jacksonville-2024", "case-farallones-2023",
                 "case-gulf-alaska-2023", "case-mumbai-2023", "case-jamnagar-2024"]

AMBIGUOUS = {"case-gulf-alaska-2023":
             "classed AMBIGUOUS by Cerulean's own human reviewer"}


def _px_km2(transform, height):
    """Pixel area in km2, using run.py's convention so the two agree."""
    lat_mid = transform.f + transform.e * (height / 2.0)
    m_lon = abs(transform.a) * 111_320.0 * np.cos(np.radians(lat_mid))
    m_lat = abs(transform.e) * 111_320.0
    return float(m_lon * m_lat / 1e6)


def _burn(geoms, shape_hw, transform):
    """Rasterise geometries to a bool mask on the scene grid."""
    if not geoms:
        return np.zeros(shape_hw, dtype=bool)
    return rasterize([(g, 1) for g in geoms], out_shape=shape_hw,
                     transform=transform, fill=0, all_touched=False,
                     dtype="uint8").astype(bool)


def _ours(case_dir, oil_only=True):
    fc = json.loads((case_dir / "detections.geojson").read_text(encoding="utf-8"))
    out = []
    for f in fc.get("features", []):
        if oil_only and f["properties"].get("classification") != "oil":
            continue
        out.append(f["geometry"])
    return out


def _cerulean(case_dir):
    """Polygon features only.

    The files also carry role='centerline' LineStrings. Those have zero area, so
    including them would contribute nothing to a union while LOOKING like they
    had been counted - a silent no-op is worse than a loud one, so they are
    dropped explicitly here rather than by accident in rasterize().
    """
    fc = json.loads((case_dir / "cerulean_slick.geojson").read_text(encoding="utf-8"))
    geoms, meta = [], {}
    for f in fc.get("features", []):
        if f["properties"].get("role") == "centerline":
            continue
        if f["geometry"]["type"] not in ("Polygon", "MultiPolygon"):
            continue
        geoms.append(f["geometry"])
        if not meta:
            meta = {k: f["properties"].get(k)
                    for k in ("machine_confidence", "slick_timestamp", "area")}
    return geoms, meta


def score(case_id):
    case_dir = CASES / case_id
    with rasterio.open(case_dir / "sar_vv_vh.tif") as ds:
        epsg = ds.crs.to_epsg() if ds.crs else None
        if epsg != 4326:
            sys.exit(f"[iou] FATAL: {case_id} is EPSG:{epsg}, expected 4326. Cerulean "
                     f"polygons are WGS84 lon/lat; burning them onto a projected grid "
                     f"without reprojecting would be silently wrong, not an error.")
        H, W, transform = ds.height, ds.width, ds.transform
    px = _px_km2(transform, H)

    cer_geoms, cer_meta = _cerulean(case_dir)
    gt = _burn(cer_geoms, (H, W), transform)
    oil = _burn(_ours(case_dir, True), (H, W), transform)
    allr = _burn(_ours(case_dir, False), (H, W), transform)

    def stats(pred):
        inter = float((pred & gt).sum())
        union = float((pred | gt).sum())
        return {"iou": (inter / union) if union else None,
                "recall": (inter / gt.sum()) if gt.sum() else None,
                "precision": (inter / pred.sum()) if pred.sum() else None,
                "pred_km2": float(pred.sum()) * px}

    r = {"case_id": case_id, "px_km2": px, "gt_km2": float(gt.sum()) * px,
         "cerulean_confidence": cer_meta.get("machine_confidence"),
         "slick_timestamp": cer_meta.get("slick_timestamp"),
         "oil": stats(oil), "all_regions": stats(allr),
         "n_oil": len(_ours(case_dir, True)),
         "n_regions": len(_ours(case_dir, False))}
    if case_id in AMBIGUOUS:
        r["caveat"] = AMBIGUOUS[case_id]
    return r


def main():
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--case", action="append", help="repeatable; default is all five")
    ap.add_argument("--all", action="store_true", help="all five reference cases")
    ap.add_argument("--json", default=None, help="also write the raw numbers here")
    a = ap.parse_args()

    rows = [score(c) for c in (a.case if a.case else DEFAULT_CASES)]

    def fmt(v, n=3):
        return "  --  " if v is None else f"{v:.{n}f}"

    print()
    print("Stage 1 vs Cerulean - AGREEMENT between two detectors on the same")
    print("acquisition. This is not accuracy against ground truth: Cerulean is an")
    print("operational detector and SkyTruth state that SAR alone cannot")
    print("definitively identify oil. Where we disagree, the polygon is not")
    print("automatically right.")
    print()
    hdr = (f"{'case':<28}{'IoU':>8}{'recall':>9}{'prec':>8}"
           f"{'ours km2':>11}{'theirs km2':>12}{'their conf':>12}")
    print(hdr)
    print("-" * len(hdr))
    for r in rows:
        o = r["oil"]
        print(f"{r['case_id']:<28}{fmt(o['iou']):>8}{fmt(o['recall']):>9}"
              f"{fmt(o['precision']):>8}{o['pred_km2']:>11.2f}{r['gt_km2']:>12.2f}"
              f"{fmt(r['cerulean_confidence'], 2):>12}")
    print()
    print("recall = how much of their polygon we covered.  prec = how much of ours")
    print("fell inside theirs.")
    print()
    print("Counting EVERY dark region we found, not only those the classifier called")
    print("oil - the detector's reach BEFORE classification:")
    print(f"{'case':<28}{'IoU':>8}{'recall':>9}{'prec':>8}{'regions':>9}")
    for r in rows:
        s = r["all_regions"]
        print(f"{r['case_id']:<28}{fmt(s['iou']):>8}{fmt(s['recall']):>9}"
              f"{fmt(s['precision']):>8}{r['n_regions']:>9}")
    print()
    for r in rows:
        if "caveat" in r:
            print(f"CAVEAT  {r['case_id']}: {r['caveat']}.")
            print("        A poor IoU here is the expected result, and is reported.")
    ious = [r["oil"]["iou"] for r in rows if r["oil"]["iou"] is not None]
    if ious:
        print()
        print(f"median IoU over {len(ious)} case(s): {np.median(ious):.3f}"
              f"   range {min(ious):.3f} - {max(ious):.3f}")

    if a.json:
        Path(a.json).write_text(json.dumps(rows, indent=2), encoding="utf-8")
        print(f"\nwrote {a.json}")


if __name__ == "__main__":
    main()
