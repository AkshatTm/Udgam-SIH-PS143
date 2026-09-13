"""
make_labels.py  -  Label harness.  Owner: Soum.

Runs detect() + add_shape_features() over every scene in the requested Zenodo
parts and writes one CSV row per detected region.

    python pipeline/detect/make_labels.py --parts 1,2 --overlap-threshold 0.25 \
           --out data/labels/features_train.csv
    python pipeline/detect/make_labels.py --parts 3   --overlap-threshold 0.25 \
           --out data/labels/features_test.csv

Parts and their ON-DISK layout — these genuinely differ, and getting it wrong
fails SILENTLY (a missing mask means every oil region is labelled 0):

    parts 1,2   data/Images/{class}/{id}.tif        data/Mask/{class}/{id}.tif
    part  3     data/test/Images/{class}/{id}.tif   data/test/Mask/{class}/{id}_segmentation.tif

Part ids are SPARSE (Part 1 Oil runs 00000..01339 with gaps, 1200 files), so
the image directory is globbed — never iterate a numeric range.

Columns
-------
scene_id      globally unique: "P12_Oil_00007", "P3_Lookalike_00007".
              The class prefix is there because Oil/00007 and Lookalike/00007
              are different scenes; the PART prefix is there because Part 1 and
              Part 3 ALSO both contain Oil/00007 and they are different scenes
              again. Either collision silently corrupts every scene-level
              grouping operation, including the train/test split.
class         "Oil" | "Lookalike" | "No oil"
label         1 = real oil region, 0 = non-oil / false alarm
area_km2, area_px, contrast_db, mean_depth_db, max_depth_db  (darkspot.py)
vh_contrast_db, vh_mean_depth_db                             (darkspot.py, VH band)
elongation, edge_gradient, solidity, shape_class             (features.py)
sea_ref_db, noise_median, noise_mad                          (scene-level, see below)

Why the three scene-level columns
---------------------------------
contrast_db and the depth features are ABSOLUTE decibels, and absolute decibels
do not survive a change of domain. Measured on our own data: VV median sits at
-33.3 dB in Zenodo Part 1, -29.3 dB in Part 3, and -20.2 dB in the Huntington
GEE export, whose noise MAD is also ~2.5x Zenodo's. A model trained on absolute
dB scores a real -6 dB slick at 0.00 confidence because -6 dB is off the end of
the distribution it was fitted on — that is not hypothetical, it is what the
8-feature RandomForest did to the Huntington slick.

Carrying the scene's own noise floor per row lets train.py derive scene-relative
features (depth / noise_mad, contrast / noise_mad) that mean the same thing in
every domain. It is the same instinct that already makes the DETECTOR thresholds
noise-relative, extended to the classifier — and the same instinct the tile cache
applies as per-scene MAD normalisation (docs/team/soum-stage1-detection.md 2.1).

Labeling rule
-------------
Oil scenes         : label=1 if (region.mask & gt_mask).sum() / area_px >= threshold
Lookalike / No oil : label=0 unconditionally — hard negatives by dataset design.
                     Masks for these folders are NEVER loaded or used.

Scene-level split warning (TRAPS #10)
--------------------------------------
scene_id is the grouping key. Splitting by row instead of by scene lets regions
from the same 2048x2048 image leak between train and test, producing a
flattering but meaningless accuracy number.

NaN safety (TRAPS #11)
-----------------------
features.py fills NaNs before Sobel. Any row with a NaN/Inf numeric feature is
dropped with a warning and a per-column tally, not written.
"""
from __future__ import annotations

import csv
import os
import sys
import time
import traceback
from collections import Counter
from concurrent.futures import ProcessPoolExecutor

import numpy as np

# ── repo root on path so imports work from any cwd ──────────────────────────
_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.abspath(os.path.join(_HERE, "..", ".."))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

import rasterio
from pipeline.detect.darkspot import load_scene, detect_array
from pipeline.detect.features import add_shape_features_batch

# ── paths ────────────────────────────────────────────────────────────────────
DATA_DIR = os.path.join(_ROOT, "data")
OUT_DIR = os.path.join(DATA_DIR, "labels")
OUT_CSV = os.path.join(OUT_DIR, "features.csv")

CLASSES = ["Oil", "Lookalike", "No oil"]   # "No oil" has a space — match exactly

# Layout per part group. mask_suffix is the ONLY thing that differs besides the
# root, and it is the thing that fails silently if assumed.
PARTS = {
    "1,2": {"prefix": "P12", "images": ("data", "Images"), "masks": ("data", "Mask"),
            "mask_suffix": ".tif"},
    "3":   {"prefix": "P3",  "images": ("data", "test", "Images"),
            "masks": ("data", "test", "Mask"), "mask_suffix": "_segmentation.tif"},
}

# Label=1 threshold: fraction of the region's pixels that must overlap GT oil
OVERLAP_THRESHOLD = 0.25

FIELDNAMES = [
    "scene_id",
    "class",
    "label",
    "area_km2",
    "area_px",
    "contrast_db",
    "mean_depth_db",
    "max_depth_db",
    "vh_contrast_db",
    "vh_mean_depth_db",
    "elongation",
    "edge_gradient",
    "solidity",
    "shape_class",
    "sea_ref_db",        # scene-level, repeated per row: this scene's sea level
    "noise_median",      # scene-level: median of the depth map over valid sea
    "noise_mad",         # scene-level: 1.4826 * MAD of the same — the unit that
]                        # makes contrast_db comparable across domains

NUMERIC = [k for k in FIELDNAMES
           if k not in ("scene_id", "class", "label", "shape_class")]


def _load_gt_mask(mask_path):
    """Load a segmentation TIF and return a bool array (True = oil pixel)."""
    with rasterio.open(mask_path) as m:
        return m.read(1) > 0


def _scene_rows(job):
    """Process ONE scene. Returns (scene_id, rows, n_regions, n_dropped, drop_cols, err).

    Runs in a worker process: it must return plain data, never numpy masks —
    a 2048x2048 bool mask per region would pickle megabytes back to the parent.
    """
    scene_id, cls, img_path, msk_path = job
    try:
        # One detection pass serves labeling, features and the scene statistics.
        # db_vh makes extract_regions measure the VH statistics from the SAME
        # region mask and the SAME background ring as VV — no cross-run matching.
        db, px_km2 = load_scene(img_path, band=1)
        db_vh, _ = load_scene(img_path, band=2)
        regions, info = detect_array(db, px_km2, db_vh=db_vh)
        scene_stats = {"sea_ref_db": float(info["sea_ref_db"]),
                       "noise_median": float(info["noise_median"]),
                       "noise_mad": float(info["noise_mad"])}
        if not regions:
            return scene_id, [], 0, 0, Counter(), None

        add_shape_features_batch(regions, db)

        gt_mask = None
        if cls == "Oil":
            if os.path.exists(msk_path):
                gt_mask = _load_gt_mask(msk_path)
            else:
                return scene_id, [], len(regions), 0, Counter(), f"GT mask missing: {msk_path}"

        rows, dropped, drop_cols = [], 0, Counter()
        for r in regions:
            if cls == "Oil" and gt_mask is not None:
                overlap = int((r["mask"] & gt_mask).sum())
                label = 1 if (overlap / max(r["area_px"], 1)) >= _THRESHOLD[0] else 0
            else:
                label = 0   # Lookalike / No oil are hard negatives by design

            row = {"scene_id": scene_id, "class": cls, "label": label,
                   "area_px": r.get("area_px", 0),
                   "shape_class": r.get("shape_class", "unknown")}
            for k in NUMERIC:
                if k == "area_px":
                    continue
                row[k] = float(scene_stats[k]) if k in scene_stats \
                    else float(r.get(k, float("nan")))

            bad = [k for k in NUMERIC
                   if isinstance(row[k], float) and not np.isfinite(row[k])]
            if bad:
                dropped += 1
                drop_cols.update(bad)
                continue
            rows.append(row)

        return scene_id, rows, len(regions), dropped, drop_cols, None

    except Exception as exc:
        return scene_id, [], 0, 0, Counter(), f"{exc}\n{traceback.format_exc()}"


# Set once per worker at pool construction; avoids threading the threshold
# through every pickled job tuple.
_THRESHOLD = [OVERLAP_THRESHOLD]


def _init_worker(threshold):
    _THRESHOLD[0] = threshold


def _build_jobs(parts_key):
    """Enumerate (scene_id, cls, img_path, msk_path) for every scene in a part."""
    spec = PARTS[parts_key]
    img_root = os.path.join(_ROOT, *spec["images"])
    msk_root = os.path.join(_ROOT, *spec["masks"])
    jobs = []
    for cls in CLASSES:
        img_dir = os.path.join(img_root, cls)
        msk_dir = os.path.join(msk_root, cls)
        if not os.path.isdir(img_dir):
            print(f"[WARN] image dir not found: {img_dir} — skipping class")
            continue
        names = sorted(f for f in os.listdir(img_dir) if f.endswith(".tif"))
        for fname in names:
            num = os.path.splitext(fname)[0]
            jobs.append((f"{spec['prefix']}_{cls}_{num}", cls,
                         os.path.join(img_dir, fname),
                         os.path.join(msk_dir, num + spec["mask_suffix"])))
        print(f"  {spec['prefix']} {cls:<12}: {len(names)} scenes")
    return jobs


def run(parts_key="3", overlap_threshold=OVERLAP_THRESHOLD, out_csv=OUT_CSV, workers=1):
    os.makedirs(os.path.dirname(out_csv) or OUT_DIR, exist_ok=True)

    print("=" * 66)
    print(f"  MAKE_LABELS  parts={parts_key}  threshold={overlap_threshold}  workers={workers}")
    print(f"  out: {out_csv}")
    print("=" * 66)
    jobs = _build_jobs(parts_key)
    print(f"  {len(jobs)} scenes queued\n")

    total_rows = pos_rows = neg_rows = 0
    dropped_rows = 0
    drop_cols = Counter()
    class_rows = {c: 0 for c in CLASSES}
    class_pos = {c: 0 for c in CLASSES}
    oil_zero_hit_scenes = 0
    errors = []
    done = 0
    t_start = time.time()

    with open(out_csv, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=FIELDNAMES)
        writer.writeheader()

        def consume(result):
            nonlocal total_rows, pos_rows, neg_rows, dropped_rows, oil_zero_hit_scenes, done
            scene_id, rows, n_regions, n_dropped, cols, err = result
            done += 1
            if err:
                errors.append((scene_id, err.splitlines()[0]))
            dropped_rows += n_dropped
            drop_cols.update(cols)
            # "P12_No oil_00007" -> "No oil"  (the class can contain a space)
            cls = scene_id.split("_", 1)[1].rsplit("_", 1)[0]
            scene_pos = 0
            for row in rows:
                writer.writerow(row)
                total_rows += 1
                class_rows[cls] += 1
                if row["label"] == 1:
                    pos_rows += 1
                    class_pos[cls] += 1
                    scene_pos += 1
                else:
                    neg_rows += 1
            if cls == "Oil" and scene_pos == 0:
                oil_zero_hit_scenes += 1
            if done % 25 == 0 or done == len(jobs):
                el = time.time() - t_start
                rate = done / max(el, 1e-9)
                eta = (len(jobs) - done) / max(rate, 1e-9)
                print(f"  [{done:>4}/{len(jobs)}] {scene_id:<22} regions={n_regions:>3}  "
                      f"pos={pos_rows} neg={neg_rows}  "
                      f"{rate:.2f} scene/s  ETA {eta/60:.1f} min", flush=True)

        if workers <= 1:
            _init_worker(overlap_threshold)
            for job in jobs:
                consume(_scene_rows(job))
        else:
            with ProcessPoolExecutor(max_workers=workers,
                                     initializer=_init_worker,
                                     initargs=(overlap_threshold,)) as pool:
                for result in pool.map(_scene_rows, jobs, chunksize=4):
                    consume(result)

    elapsed = time.time() - t_start
    print()
    print("=" * 66)
    print("  MAKE_LABELS COMPLETE")
    print("=" * 66)
    print(f"  Scenes processed : {done}")
    print(f"  Total rows       : {total_rows}")
    print(f"  label=1 (oil)    : {pos_rows}  ({100*pos_rows/max(total_rows,1):.2f}%)")
    print(f"  label=0 (non-oil): {neg_rows}  ({100*neg_rows/max(total_rows,1):.2f}%)")
    print()
    print("  Rows per class:")
    for cls in CLASSES:
        print(f"    {cls:<12}: {class_rows[cls]:>6} rows  ({class_pos[cls]} label=1)")
    print()
    print(f"  Oil scenes with ZERO label=1 rows: {oil_zero_hit_scenes}")
    if dropped_rows:
        print(f"  Rows dropped for NaN/Inf: {dropped_rows}  by column: {dict(drop_cols)}")
    if errors:
        print(f"\n  [ERRORS] {len(errors)} scene(s):")
        for sid, msg in errors[:20]:
            print(f"    {sid}: {msg}")
        if len(errors) > 20:
            print(f"    ... and {len(errors)-20} more")
    print()
    print(f"  Output: {out_csv}")
    print(f"  Wall time: {elapsed/60:.1f} min")

    # Sanity gate: the hard-negative classes must contribute exactly zero
    # positives. If they ever do, the labeling rule has been broken.
    bad = [c for c in ("Lookalike", "No oil") if class_pos[c] != 0]
    if bad:
        print(f"\n  [FAIL] {bad} produced label=1 rows — the hard-negative rule is broken.")
    if pos_rows < 50:
        print("\n  [WARNING] Fewer than 50 label=1 rows — classifier will be unreliable.")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--parts", default="3", choices=sorted(PARTS),
                        help="'1,2' = Zenodo Parts I+II (train), '3' = Part III (held-out test)")
    parser.add_argument("--overlap-threshold", type=float, default=OVERLAP_THRESHOLD)
    parser.add_argument("--out", type=str, default=OUT_CSV)
    parser.add_argument("--workers", type=int, default=8,
                        help="parallel scene workers; 1 = serial")
    args = parser.parse_args()

    run(parts_key=args.parts, overlap_threshold=args.overlap_threshold,
        out_csv=args.out, workers=args.workers)
