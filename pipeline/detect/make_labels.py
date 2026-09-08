"""
make_labels.py  -  Phase 2, Step 3.  Owner: Soum.

Runs detect() + add_shape_features() over all 450 Part-III scenes and writes
data/labels/features.csv — one row per detected region.

Columns
-------
scene_id      globally unique: "Oil_00007", "Lookalike_00007", "No oil_00007"
              (Oil/00007 and Lookalike/00007 are DIFFERENT scenes — plain "00007"
              would collide and corrupt the scene-level train/test split)
class         "Oil" | "Lookalike" | "No oil"
label         1 = real oil region, 0 = non-oil / false alarm
area_km2, area_px, contrast_db, mean_depth_db, max_depth_db  (from darkspot.py)
elongation, edge_gradient, solidity, shape_class               (from features.py)

Labeling rule
-------------
Oil scenes     : label=1 if (region.mask & gt_mask).sum() / area_px >= 0.5
Lookalike / No oil : label=0 unconditionally — hard negatives by dataset design.
                     Masks for these folders are NEVER loaded or used.

Scene-level split warning (TRAPS #10)
--------------------------------------
scene_id is the grouping key for GroupShuffleSplit / LeaveOneGroupOut in
train.py.  Splitting by row instead of by scene lets regions from the same
2048x2048 image leak between train and test, producing a flattering but
meaningless accuracy number.  The column is here so the classifier can't
"accidentally" forget to use it.

NaN safety (TRAPS #11)
-----------------------
features.py fills NaNs before Sobel. This file asserts no NaN survives into
the CSV; any row with a NaN feature is dropped with a warning, not written.

Usage
-----
    python pipeline/detect/make_labels.py
    # output: data/labels/features.csv
"""
from __future__ import annotations

import csv
import os
import sys
import time
import traceback

import numpy as np

# ── repo root on path so imports work from any cwd ──────────────────────────
_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.abspath(os.path.join(_HERE, "..", ".."))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

import rasterio
from pipeline.detect.darkspot import detect
from pipeline.detect.features import add_shape_features_batch

# ── paths ────────────────────────────────────────────────────────────────────
DATA_DIR   = os.path.join(_ROOT, "data")
OUT_DIR    = os.path.join(DATA_DIR, "labels")
OUT_CSV    = os.path.join(OUT_DIR, "features.csv")

CLASSES = ["Oil", "Lookalike", "No oil"]   # "No oil" has a space — match exactly

# Label=1 threshold: fraction of the region's pixels that must overlap GT oil
OVERLAP_THRESHOLD = 0.5

# CSV columns — order matters; must match CONTRACTS.md field names where they overlap
FIELDNAMES = [
    "scene_id",        # globally unique, e.g. "Oil_00007"
    "class",           # Oil | Lookalike | No oil
    "label",           # 1 = oil, 0 = non-oil
    "area_km2",
    "area_px",
    "contrast_db",
    "mean_depth_db",
    "max_depth_db",
    "elongation",
    "edge_gradient",
    "solidity",
    "shape_class",
]


def _fmt(v, precision=6):
    """Format a scalar for CSV: floats to fixed precision, pass through others."""
    if isinstance(v, float):
        if np.isnan(v) or np.isinf(v):
            return ""          # sentinel — caller will catch and skip
        return f"{v:.{precision}f}"
    return str(v)


def _load_gt_mask(mask_path):
    """Load a segmentation TIF and return a bool array (True = oil pixel)."""
    with rasterio.open(mask_path) as m:
        return m.read(1) > 0


def run(overlap_threshold=OVERLAP_THRESHOLD, out_csv=OUT_CSV):
    os.makedirs(OUT_DIR, exist_ok=True)

    total_scenes = 0
    total_rows   = 0
    pos_rows     = 0   # label=1
    neg_rows     = 0   # label=0

    # Per-class counters
    class_rows   = {c: 0 for c in CLASSES}
    class_pos    = {c: 0 for c in CLASSES}

    # Oil-specific: scenes that produced zero label=1 rows
    oil_zero_hit_scenes = 0

    t_start = time.time()

    with open(out_csv, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=FIELDNAMES)
        writer.writeheader()

        for cls in CLASSES:
            img_dir  = os.path.join(DATA_DIR, "Images", cls)
            mask_dir = os.path.join(DATA_DIR, "Mask",   cls)

            if not os.path.isdir(img_dir):
                print(f"[WARN] image dir not found: {img_dir} — skipping class")
                continue

            scene_files = sorted(
                f for f in os.listdir(img_dir) if f.endswith(".tif")
            )

            print(f"\n{'='*62}")
            print(f"  Class: {cls}  ({len(scene_files)} scenes)")
            print(f"{'='*62}")

            for fname in scene_files:
                scene_num = os.path.splitext(fname)[0]          # e.g. "00007"
                scene_id  = f"{cls}_{scene_num}"                # globally unique
                img_path  = os.path.join(img_dir, fname)
                msk_path  = os.path.join(mask_dir, scene_num + "_segmentation.tif")

                total_scenes += 1

                try:
                    # ── 1. Detect (one call; reuse for both labeling and features) ──
                    regions, db = detect(img_path)

                    if not regions:
                        # Nothing detected — valid, not an error; just skip
                        if cls == "Oil":
                            oil_zero_hit_scenes += 1
                        continue

                    # ── 2. Add shape features to all regions ──────────────────────
                    add_shape_features_batch(regions, db)

                    # ── 3. Load GT mask (Oil only) ────────────────────────────────
                    gt_mask = None
                    if cls == "Oil":
                        if os.path.exists(msk_path):
                            gt_mask = _load_gt_mask(msk_path)
                        else:
                            print(f"  [WARN] {scene_id}: GT mask missing at {msk_path}")

                    # ── 4. Label + write rows ─────────────────────────────────────
                    scene_pos = 0
                    rows_written = 0

                    for r in regions:
                        # Determine label
                        if cls == "Oil" and gt_mask is not None:
                            overlap = int((r["mask"] & gt_mask).sum())
                            label = 1 if (overlap / max(r["area_px"], 1)) >= overlap_threshold else 0
                        else:
                            label = 0   # Lookalike / No oil are hard negatives

                        row = {
                            "scene_id":     scene_id,
                            "class":        cls,
                            "label":        label,
                            "area_km2":     r.get("area_km2", float("nan")),
                            "area_px":      r.get("area_px", 0),
                            "contrast_db":  r.get("contrast_db", float("nan")),
                            "mean_depth_db":r.get("mean_depth_db", float("nan")),
                            "max_depth_db": r.get("max_depth_db", float("nan")),
                            "elongation":   r.get("elongation", float("nan")),
                            "edge_gradient":r.get("edge_gradient", float("nan")),
                            "solidity":     r.get("solidity", float("nan")),
                            "shape_class":  r.get("shape_class", "unknown"),
                        }

                        # TRAPS #11: assert no NaN survives into the CSV
                        numeric_keys = [k for k in FIELDNAMES
                                        if k not in ("scene_id", "class", "label", "shape_class")]
                        has_nan = any(
                            isinstance(row[k], float) and (np.isnan(row[k]) or np.isinf(row[k]))
                            for k in numeric_keys
                        )
                        if has_nan:
                            nan_cols = [k for k in numeric_keys
                                        if isinstance(row[k], float)
                                        and (np.isnan(row[k]) or np.isinf(row[k]))]
                            print(f"  [WARN] {scene_id} region dropped: NaN in {nan_cols}")
                            continue

                        writer.writerow(row)
                        rows_written += 1
                        total_rows   += 1
                        class_rows[cls] += 1

                        if label == 1:
                            pos_rows += 1
                            class_pos[cls] += 1
                            scene_pos += 1
                        else:
                            neg_rows += 1

                    if cls == "Oil" and scene_pos == 0:
                        oil_zero_hit_scenes += 1

                    # ── 5. Running progress every scene ───────────────────────────
                    elapsed = time.time() - t_start
                    print(f"  [{total_scenes:>3}] {scene_id:<20}  "
                          f"regions={len(regions):>3}  written={rows_written:>3}  "
                          f"label1={scene_pos:>2}  "
                          f"running total: pos={pos_rows} neg={neg_rows}  "
                          f"({elapsed:.0f}s)")

                except Exception as exc:
                    print(f"  [ERROR] {scene_id}: {exc}")
                    traceback.print_exc()
                    continue

    # ── Final summary ─────────────────────────────────────────────────────────
    elapsed = time.time() - t_start
    print()
    print("=" * 62)
    print("  MAKE_LABELS COMPLETE")
    print("=" * 62)
    print(f"  Scenes processed : {total_scenes}")
    print(f"  Total rows       : {total_rows}")
    print(f"  label=1 (oil)    : {pos_rows}  ({100*pos_rows/max(total_rows,1):.1f}%)")
    print(f"  label=0 (non-oil): {neg_rows}  ({100*neg_rows/max(total_rows,1):.1f}%)")
    print()
    print("  Rows per class:")
    for cls in CLASSES:
        print(f"    {cls:<12}: {class_rows[cls]:>5} rows  "
              f"({class_pos[cls]} label=1)")
    print()
    print(f"  Oil scenes with ZERO label=1 rows: {oil_zero_hit_scenes}")
    print(f"  (detector found nothing, or found candidates but none overlapped GT)")
    print()
    print(f"  Output: {out_csv}")
    print(f"  Wall time: {elapsed:.0f}s")

    if pos_rows < 50:
        print()
        print("  [WARNING] Fewer than 50 label=1 rows — classifier will be unreliable.")
        print("  Consider lowering t_high_db in darkspot.py or the overlap threshold here.")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--overlap-threshold", type=float, default=OVERLAP_THRESHOLD)
    parser.add_argument("--out", type=str, default=OUT_CSV)
    args = parser.parse_args()
    
    run(overlap_threshold=args.overlap_threshold, out_csv=args.out)
