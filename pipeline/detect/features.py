"""
features.py  -  Phase 2, Step 2.  Owner: Soum.

add_shape_features(region, db) -> region dict with four new keys:

  elongation    : major / minor axis  (>= 1.0 always)
  edge_gradient : mean Sobel magnitude along the contour boundary (dB/px)
  solidity      : area_px / convex_hull_area  (0 < s <= 1.0)
  shape_class   : "linear" if elongation > 3 else "blob"  [CONTRACTS.md sec 4]

Property names match CONTRACTS.md detections.geojson schema exactly.
Do NOT rename them — Akshat's build_case.py reads these names directly.

Traps avoided:
  TRAPS #11 - NaN/land pixels: Sobel is computed on db_filled (NaNs replaced
    with nanmean) because cv2.Sobel propagates NaN, corrupting edge_gradient.
  TRAPS #1  - coordinate order: contour[:,0]=x=col, contour[:,1]=y=row.
    NumPy arrays index [row, col], so we always use
      rows = np.clip(contour[:,1], 0, H-1)
      cols = np.clip(contour[:,0], 0, W-1)
    when sampling into the Sobel image.
"""
from __future__ import annotations

import numpy as np
import cv2


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def add_shape_features(region: dict, db: np.ndarray) -> dict:
    """Add elongation, edge_gradient, solidity, shape_class to *region* in-place.

    Parameters
    ----------
    region : dict
        A region dict from darkspot.py extract_regions().
        Must contain: contour (Nx2 int, (x,y) order), area_px (int),
        bbox ([left, top, width, height]).
    db : np.ndarray
        Full-scene dB array (float32/float64, may contain NaN for land/nodata).
        Must be same shape as region['mask'].

    Returns
    -------
    The same dict with four keys added in-place. If a feature cannot be
    computed, the key is set to -1.0 (numeric sentinel) or "unknown"
    (shape_class), so downstream code can filter without crashing.
    """
    contour = region["contour"]   # (N, 2) int, (x=col, y=row)
    area_px = region["area_px"]

    # ------------------------------------------------------------------
    # 1. Sobel gradient magnitude  --  computed on NaN-filled image
    # ------------------------------------------------------------------
    # Fill NaNs with nanmean before Sobel: cv2.Sobel propagates NaN,
    # which would silently corrupt every edge_gradient value (TRAPS #11).
    finite_mask = np.isfinite(db)
    fill_val = float(np.nanmean(db)) if finite_mask.any() else 0.0
    db_filled = np.where(finite_mask, db, fill_val).astype(np.float64)

    gx = cv2.Sobel(db_filled, cv2.CV_64F, 1, 0, ksize=3)
    gy = cv2.Sobel(db_filled, cv2.CV_64F, 0, 1, ksize=3)
    sobel_mag = np.hypot(gx, gy)          # shape (H, W)

    H, W = db.shape

    # Contour is (x=col, y=row) — convert to [row, col] for array indexing.
    # Clip to valid bounds: handles regions touching the frame edge.
    rows = np.clip(contour[:, 1], 0, H - 1)
    cols = np.clip(contour[:, 0], 0, W - 1)

    region["edge_gradient"] = (
        float(sobel_mag[rows, cols].mean()) if len(rows) > 0 else -1.0
    )

    # ------------------------------------------------------------------
    # 2. Elongation  (cv2.fitEllipse major/minor; bbox fallback)
    # ------------------------------------------------------------------
    region["elongation"] = _elongation(contour, region["bbox"])

    # ------------------------------------------------------------------
    # 3. Solidity  (area / convex hull area)
    # ------------------------------------------------------------------
    region["solidity"] = _solidity(contour, area_px)

    # ------------------------------------------------------------------
    # 4. Shape class  [CONTRACTS.md sec 4 exact rule]
    # ------------------------------------------------------------------
    region["shape_class"] = "linear" if region["elongation"] > 3 else "blob"

    return region


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _elongation(contour: np.ndarray, bbox: list) -> float:
    """major/minor axis ratio, always >= 1.0.

    Uses cv2.fitEllipse when >= 5 points; bounding-box ratio otherwise.
    Returns -1.0 on any unexpected error.
    """
    try:
        if contour.shape[0] >= 5:
            _, (ax1, ax2), _ = cv2.fitEllipse(contour.astype(np.float32))
            major = max(float(ax1), float(ax2))
            minor = min(float(ax1), float(ax2))
        else:
            w, h = float(bbox[2]), float(bbox[3])
            major, minor = max(w, h), min(w, h)

        if minor <= 0.0:
            return max(1.0, major)
        return max(1.0, major / minor)
    except Exception:
        return -1.0


def _solidity(contour: np.ndarray, area_px: int) -> float:
    """area_px / convex_hull_area.  Returns 1.0 on degenerate hull."""
    try:
        hull = cv2.convexHull(contour)
        hull_area = cv2.contourArea(hull)
        if hull_area <= 0.0:
            return 1.0
        return max(0.0, min(1.0, float(area_px) / hull_area))
    except Exception:
        return -1.0


# ---------------------------------------------------------------------------
# Batch helper
# ---------------------------------------------------------------------------

def add_shape_features_batch(regions: list, db: np.ndarray) -> list:
    """Apply add_shape_features to every region; never aborts the batch."""
    for r in regions:
        try:
            add_shape_features(r, db)
        except Exception as exc:
            for key in ("elongation", "edge_gradient", "solidity"):
                if key not in r:
                    r[key] = -1.0
            if "shape_class" not in r:
                r["shape_class"] = "unknown"
            r["_feature_error"] = str(exc)
    return regions


# ---------------------------------------------------------------------------
# Self-test  (python features.py  from repo root)
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys, os

    print("=" * 62)
    print("PART 1 -- Synthetic shapes")
    print("=" * 62)

    rng = np.random.default_rng(42)
    H, W = 512, 512
    sea_db, noise_std = -29.0, 0.9

    def _fresh_sea():
        return rng.normal(sea_db, noise_std, (H, W)).astype(np.float32)

    def _region_from_mask(mask, db, name):
        contours, _ = cv2.findContours(
            mask.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            print(f"  [{name}] no contour found"); return None
        c = max(contours, key=cv2.contourArea).squeeze(axis=1)
        if c.ndim != 2:
            c = contours[0].reshape(-1, 2)
        ys, xs = np.where(mask)
        area_px = int(mask.sum())
        x0, y0 = int(xs.min()), int(ys.min())
        bw, bh = int(xs.max() - xs.min() + 1), int(ys.max() - ys.min() + 1)
        return {"mask": mask, "contour": c, "area_px": area_px,
                "area_km2": area_px * 1e-4, "bbox": [x0, y0, bw, bh]}

    # Shape 1: thin elongated ellipse (expect elongation > 5, shape=linear)
    db1 = _fresh_sea()
    m1 = np.zeros((H, W), np.uint8)
    cv2.ellipse(m1, (256, 256), (130, 10), 30, 0, 360, 1, -1)
    db1[m1 > 0] -= 4.0
    r1 = _region_from_mask(m1.astype(bool), db1, "elongated-ellipse")

    # Shape 2: circle (expect elongation ~1, shape=blob)
    db2 = _fresh_sea()
    m2 = np.zeros((H, W), np.uint8)
    cv2.circle(m2, (256, 256), 65, 1, -1)
    db2[m2 > 0] -= 4.0
    r2 = _region_from_mask(m2.astype(bool), db2, "circle")

    # Shape 3: star polygon (expect solidity < 0.8)
    db3 = _fresh_sea()
    m3 = np.zeros((H, W), np.uint8)
    pts = []
    for i in range(12):
        angle = np.radians(i * 30)
        rad = 80 if i % 2 == 0 else 28
        pts.append([int(256 + rad * np.cos(angle)), int(256 + rad * np.sin(angle))])
    cv2.fillPoly(m3, [np.array(pts)], 1)
    db3[m3 > 0] -= 4.0
    r3 = _region_from_mask(m3.astype(bool), db3, "star-ragged")

    for label, r, dba in [("elongated-ellipse", r1, db1),
                           ("circle",            r2, db2),
                           ("star-ragged",       r3, db3)]:
        if r is None: continue
        add_shape_features(r, dba)
        print(f"\n  {label}")
        print(f"    elongation    = {r['elongation']:.3f}")
        print(f"    edge_gradient = {r['edge_gradient']:.4f} dB/px")
        print(f"    solidity      = {r['solidity']:.3f}")
        print(f"    shape_class   = {r['shape_class']}")

    # --- assertions ---
    fail = False
    if r1 is not None and r1["elongation"] <= 5:
        print(f"\n[FAIL] ellipse elongation {r1['elongation']:.2f} should be >5"); fail=True
    if r2 is not None and r2["elongation"] >= 2:
        print(f"\n[FAIL] circle elongation {r2['elongation']:.2f} should be <2"); fail=True
    if r3 is not None and r3["solidity"] >= 0.80:
        print(f"\n[FAIL] star solidity {r3['solidity']:.3f} should be <0.80"); fail=True
    if r2 is not None and r2["shape_class"] != "blob":
        print(f"\n[FAIL] circle shape_class should be blob"); fail=True
    if r1 is not None and r1["shape_class"] != "linear":
        print(f"\n[FAIL] ellipse shape_class should be linear"); fail=True
    if not fail:
        print("\n  [PASS] all synthetic shape assertions hold")

    # ====================================================================
    print()
    print("=" * 62)
    print("PART 2 -- Real scenes  (00007, 00046, 00104)")
    print("=" * 62)

    # Insert repo root so 'from pipeline.detect.darkspot import detect' works
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)

    try:
        import rasterio as _rio
    except ImportError:
        print("[SKIP] rasterio not importable. Run: venv\\Scripts\\python features.py")
        sys.exit(0)

    from pipeline.detect.darkspot import detect

    DATA = os.path.join(repo_root, "data")
    SCENES = ["00007", "00046", "00104"]

    for sid in SCENES:
        img_p  = os.path.join(DATA, "Images", "Oil", sid + ".tif")
        msk_p  = os.path.join(DATA, "Mask",   "Oil", sid + "_segmentation.tif")

        if not os.path.exists(img_p):
            print(f"\n  [SKIP] {sid} -- file not found"); continue

        print(f"\n  Scene {sid}")
        regions, db = detect(img_p)
        if not regions:
            print("    0 regions returned by detector"); continue

        with _rio.open(msk_p) as _m:
            gt_oil = _m.read(1) > 0

        add_shape_features_batch(regions, db)

        hdr = ("  {:>3}  {:>9}  {:>10}  {:>9}  {:>8}  {:>11}  {:>11}"
               .format("idx", "area_km2", "elongation", "edge_grad",
                       "solidity", "shape_class", "GT_overlap%"))
        print(hdr)
        print("  " + "-" * (len(hdr) - 2))

        hits, fas = [], []
        for i, r in enumerate(regions):
            ov_px  = int((r["mask"] & gt_oil).sum())
            ov_pct = 100.0 * ov_px / max(r["area_px"], 1)
            tag    = "HIT " if ov_pct >= 50 else ("part" if ov_pct > 0 else "    ")
            print("  {:>3}  {:>9.3f}  {:>10.3f}  {:>9.4f}  {:>8.3f}  {:>11}  {:>10.1f}%  {}"
                  .format(i, r["area_km2"], r["elongation"], r["edge_gradient"],
                          r["solidity"], r["shape_class"], ov_pct, tag))
            (hits if ov_pct >= 50 else fas).append(r)

        def _mean(lst, key):
            v = [r[key] for r in lst
                 if isinstance(r.get(key), float) and r[key] >= 0]
            return float(np.mean(v)) if v else float("nan")

        if hits and fas:
            print(f"\n    Feature means -- HITS (n={len(hits)}) vs FALSE ALARMS (n={len(fas)}):")
            for feat in ("elongation", "edge_gradient", "solidity"):
                hm, fm = _mean(hits, feat), _mean(fas, feat)
                print(f"      {feat:15s}: hits={hm:7.4f}  fa={fm:7.4f}  diff={hm-fm:+.4f}")
        elif hits:
            print(f"    All {len(hits)} region(s) are GT hits (no false alarms)")
        else:
            print(f"    No GT hits among {len(regions)} region(s)")
