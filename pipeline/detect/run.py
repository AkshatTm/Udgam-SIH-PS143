#!/usr/bin/env python3
"""
Stage 1 — detection. Owner: Soum.

    python pipeline/detect/run.py --case case-000 --stub

STUB ONLY. Writes a schema-valid `out/detections.geojson` full of invented numbers, so every
downstream seam can be wired and tested before the real detector exists (Master section 8, rule 1:
"first commit = correctly-shaped garbage").

The real implementation replaces `stub_detections()` and nothing else:
    sar.png (8-bit) -> dB via the clamp in bounds.json -> adaptive threshold -> morphology ->
    connected components -> shape features -> RandomForest -> polygons in pixel coords ->
    lon/lat by linear interpolation across bounds.

Deliberately stdlib-only so it runs on a half-built environment. The real detector will need
opencv-python, scikit-image, scikit-learn, rasterio.
"""
import argparse
import json
import math
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
OUT = HERE / "out"


def load_bounds(case_dir):
    b = json.loads((case_dir / "bounds.json").read_text())
    # db_min/db_max are optional; the real detector needs them to map the PNG back to decibels
    # and must default to the agreed clamp when they are absent (docs/TRAPS.md #7).
    b.setdefault("db_min", -25)
    b.setdefault("db_max", 0)
    return b


def r5(x):
    return round(float(x), 5)


def ellipse_ring(clon, clat, a_deg, b_deg, rot_rad, n=48):
    """Closed [lon, lat] ring. Longitude radius is stretched by 1/cos(lat) so the shape is
    round on the ground rather than round in degrees."""
    k = 1.0 / max(math.cos(math.radians(clat)), 1e-6)
    ring = []
    for i in range(n + 1):
        t = 2 * math.pi * i / n
        dx, dy = a_deg * math.cos(t), b_deg * math.sin(t)
        rx = dx * math.cos(rot_rad) - dy * math.sin(rot_rad)
        ry = dx * math.sin(rot_rad) + dy * math.cos(rot_rad)
        ring.append([r5(clon + rx * k), r5(clat + ry)])
    ring[-1] = list(ring[0])
    return ring


def ellipse_km2(a_deg_lon, b_deg_lat):
    """Ground area of the ellipse ellipse_ring() draws — keeps area_km2 consistent with the
    polygon so the validator's shoelace check stays quiet on the stub bundle."""
    return round(math.pi * (a_deg_lon * 111.32) * (b_deg_lat * 111.32), 1)


def stub_detections(b):
    """Two invented regions placed by fraction of the scene: one elongated 'oil', one round
    'lookalike'. DELETE THIS FUNCTION when the real detector lands."""
    w, s, e, n = b["west"], b["south"], b["east"], b["north"]
    dlon, dlat = e - w, n - s

    def at(fx, fy):
        # fy is measured from the NORTH edge, matching pixel row order (0,0) = (west, north)
        return w + fx * dlon, n - fy * dlat

    feats = []

    olon, olat = at(0.56, 0.40)
    feats.append({
        "type": "Feature",
        "geometry": {"type": "Polygon",
                     "coordinates": [ellipse_ring(olon, olat, dlon * 0.16, dlat * 0.018,
                                                  math.radians(-24))]},
        "properties": {"id": "det-01", "classification": "oil", "confidence": 0.87,
                       "area_km2": ellipse_km2(dlon * 0.16, dlat * 0.018),
                       "elongation": 8.2, "edge_gradient": 0.34,
                       "contrast_db": -6.2, "shape_class": "linear",
                       "centroid": [r5(olon), r5(olat)]},
    })

    llon, llat = at(0.27, 0.70)
    feats.append({
        "type": "Feature",
        "geometry": {"type": "Polygon",
                     "coordinates": [ellipse_ring(llon, llat, dlon * 0.075, dlat * 0.065, 0.0)]},
        "properties": {"id": "det-02", "classification": "lookalike", "confidence": 0.71,
                       "area_km2": ellipse_km2(dlon * 0.075, dlat * 0.065),
                       "elongation": 1.4, "edge_gradient": 0.11,
                       "contrast_db": -3.1, "shape_class": "blob",
                       "centroid": [r5(llon), r5(llat)]},
    })
    return feats


def main():
    ap = argparse.ArgumentParser(description="Stage 1 — detection (stub)")
    ap.add_argument("--case", required=True, help="case id, e.g. case-000")
    ap.add_argument("--cases-root", default=str(REPO / "cases"))
    ap.add_argument("--stub", action="store_true",
                    help="required until the real detector exists")
    a = ap.parse_args()

    if not a.stub:
        raise SystemExit(
            "detect/run.py has no real implementation yet — pass --stub.\n"
            "Building it is Phase 2 of docs/02_SOUM_DETECTION.md.")

    case_dir = Path(a.cases_root) / a.case
    if not (case_dir / "bounds.json").exists():
        raise SystemExit(f"{case_dir}/bounds.json not found — Stage 1 needs Akshat's scene export "
                         f"(sar.png + bounds.json) before it can run.")

    b = load_bounds(case_dir)
    feats = stub_detections(b)

    OUT.mkdir(parents=True, exist_ok=True)
    dst = OUT / "detections.geojson"
    dst.write_text(json.dumps({"type": "FeatureCollection", "features": feats}))

    oil = sum(1 for f in feats if f["properties"]["classification"] == "oil")
    print(f"[detect:STUB] wrote {dst}")
    print(f"              {len(feats)} region(s), {oil} classified 'oil'  "
          f"(dB clamp {b['db_min']}..{b['db_max']})")
    print(f"              next: python pipeline/export/build_case.py --case {a.case}")


if __name__ == "__main__":
    main()
