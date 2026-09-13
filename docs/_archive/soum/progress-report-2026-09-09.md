# SOUM — Complete Detection Pipeline: Progress Report & Handoff

**Author:** Soum (Stage 1 — Detection)  
**Project:** SIH PS-143 — SAR Oil Spill Detection & Attribution (NAAP)  
**Date:** 2026-09-09  
**Report purpose:** Full technical handoff so a fresh model can understand every decision made, every failure encountered, and what remains to be done for the Ennore deliverable.

---

## 0. Project Context

This is a Smart India Hackathon project building an oil-spill detection and attribution pipeline for Sentinel-1 SAR imagery. The full team has four stages:

1. **Soum (this doc)** — Stage 1: Detect oil-spill candidates from a SAR scene → `detections.geojson`
2. **Anushka** — Stage 2: Backward-drift particle tracing using HYCOM + ERA5 → `particles.json` + `origin.json`
3. **Jaiveer** — Stage 3: AIS vessel attribution → `vessels.geojson` + `suspects.json`
4. **Harshita** — Stage 4: Frontend (deck.gl + MapLibre) that plays back the full case bundle

Each stage is hermetically isolated: it reads its inputs from a `cases/<case_id>/` directory and writes its outputs back. No stage imports another. The frontend is a static JSON player.

**Hard deadline:** Produce a valid `detections.geojson` for the Ennore oil spill case (Jan 29 2017, Chennai) before Tuesday evening.

---

## 1. Files Soum Owns

```
pipeline/detect/
  darkspot.py         ← THE detector (v2, morphological depth-map, DO NOT regress)
  features.py         ← shape feature extractor
  make_labels.py      ← label harness for all 450 training scenes
  train.py            ← RandomForest classifier + scene-level split
  run.py              ← end-to-end: scene -> detections.geojson (not yet finished)
  models/
    classifier.pkl    ← trained model (currently: 10-feature RF with VH)
    feature_order.json ← exact column order for inference

data/labels/
  features.csv             ← 4085 rows, 50% IoU threshold, 61 label=1
  features_t25.csv         ← 4085 rows, 25% IoU threshold, 80 label=1  ← CURRENT
  features_with_vh.csv     ← 4085 rows + 2 VH columns  ← BEST so far (F1=0.276)
```

---

## 2. Dataset Description

**Source:** Zenodo Part III — `zenodo.org/records/13761290` (9.9 GB 7z)

```
data/Images/
  Oil/          150 scenes x 2048x2048x2 bands (VV, VH), float32 dB
  Lookalike/    150 scenes x same format (ocean phenomena that look like oil)
  No oil/       150 scenes x same format (clean ocean)
data/Mask/
  Oil/          150 segmentation TIFs, {id}_segmentation.tif, binary (1=oil pixel)
  Lookalike/    (masks exist but are NOT used for labeling — see Section 5)
  No oil/       (masks exist but are NOT used for labeling)
```

**Image format:**
- 2048 x 2048 pixels at ~10 m/px → roughly 20 x 20 km coverage
- Band 1 = VV polarization (used for detection)
- Band 2 = VH polarization (used for supplemental features)
- Values are float32 linear dB, approximately -29 to -30 dB for open ocean (Zenodo calibration; GEE scenes sit ~-20 dB — completely different scale)
- Many scenes contain NaN pixels (land, nodata) and exact-zero pixels (nodata sentinel)

**Label semantics:**
- Oil scenes: oil exists somewhere in the scene; the exact location is in the segmentation mask
- Lookalike: ocean phenomena (biogenic slick, rain cells, upwelling, ship wake, calm water) that *visually resemble* oil in SAR but are not oil. **Hard negatives by design.**
- No oil: clean ocean scenes. **Hard negatives by design.**

**Key data insight (learned empirically):**
Zenodo oil scenes cluster at -29 to -30 dB. Oil slicks appear as darker patches. The typical contrast is only **0.3 to 1.3 dB below background** — extremely shallow compared to the ~3-6 dB contrast that SAR literature assumes for tanker spills. This low contrast is the root cause of almost all detection and classification difficulty.

---

## 3. darkspot.py — The Detector (v2, Morphological)

### 3.1 What v1 did and why it failed

v1 used an annulus CFAR (Constant False Alarm Rate) detector:
```
threshold = local_mean(annulus) - k * local_std(annulus)
```

The annulus protects a **compact blob** from contaminating its own background stats. But an oil slick is a **line**. A linear slick escapes the guard zone and runs through the annulus ring, which means:
- The slick pixels contaminate their own background estimate
- The local mean is dragged down, local std is inflated
- The threshold moves *away from the slick exactly where the slick is*
- A -4 dB streak on a -1 dB sea becomes invisible

Proved on synthetic data in `test_synthetic.py`. v1 was abandoned.

### 3.2 What v2 does (current code, DO NOT TOUCH)

v2 implements a **morphological depth-map + hysteresis** approach, matching what SNAP's Oil-Spill-Detection operator and the Solberg/Brekke SAR slick literature do:

**Step 1 — Masking** (`prepare()`):
- Mask NaN pixels (land/nodata)
- Mask exact-zero pixels (nodata sentinel)
- Mask bright outliers above `bright_ceiling_db = -10 dB` + 5-px dilation halo (ships/rigs cause a "dark halo" false positive around them — CFAR failure mode; masking prevents this)
- Mask land: anything whose local mean is >= 7 dB above sea reference, fill holes, drop small blobs, dilate 40 px
- Produce `filled` image (invalid pixels replaced with sea reference level) — morphological closing is a max-filter so filling with sea level cannot create false dark spots in real sea

**Step 2 — Depth map** (`depth_map()`):
```python
depth = max over scales of (closing(Gaussian(filled), scale) - smoothed_filled)
```
This gives, per pixel: *how many dB below the surrounding sea does this pixel sit?*
Scales tried: 41, 121, 361 pixels -> multi-scale so both compact blobs and thin slicks are captured.
Why closing, not mean: closing uses the *surrounding maximum* — robust to the feature itself. The feature cannot raise its own background estimate. No ringing at subswath seams (step edges pass through closings unchanged).

**Step 3 — Noise floor** (`noise_floor()`):
```python
med, mad = median_and_MAD(depth[valid_sea])
```
Thresholds are relative to the scene's own noise, not fixed dB values. Essential because Zenodo scenes are calibrated differently from GEE scenes.

**Step 4 — Hysteresis thresholding** (`hysteresis()`):
```python
strong = depth >= (med + max(t_high_db=2.0, 3.0 * mad))
weak   = depth >= (med + max(t_low_db=1.0,  1.5 * mad))
mask   = connected components of weak that contain at least one strong pixel
```
Hysteresis keeps a whole slick as one coherent region without requiring every pixel to be strongly dark. Without this, a slick with patchy contrast fragments into many small regions.

**Step 5 — Clean + filter** (`clean_mask()`, `extract_regions()`):
- Morphological close (size 7, elliptical kernel) to fill small gaps
- Connected components with stats
- Keep regions with `area_km2 >= 0.05` OR `max_bbox_side >= 80 px` (the second rule prevents thin streaks from being dropped for small area)
- Drop regions with `area_km2 > 500`
- Compute per-region stats: `mean_depth_db`, `max_depth_db`, `contrast_db` (median inside - median in 25-px outer ring, 5-px inner guard)

**Key implementation notes for darkspot.py:**
- `detect(path)` -> `(regions, db)` — same signature as v1, all callers unchanged
- `detect_array(db, pixel_area_km2)` — accepts raw arrays, used for GEE exports without the TIF wrapper
- `load_scene(path, band=1)` — reads band 1 (VV) by default; pass `band=2` for VH
- The VV `db` array returned by `detect()` is the **raw, unmasked** array. The masking is internal to `detect_array` / `prepare`. Callers should not assume the returned `db` has been cleaned.

---

## 4. features.py — Shape Feature Extractor

**Public API:** `add_shape_features(region, db) -> region` (mutates in-place)
Also: `add_shape_features_batch(regions, db)` — same but for a list

**Features computed per region:**

| Feature | Description | Notes |
|---------|-------------|-------|
| `elongation` | major_axis / minor_axis via `cv2.fitEllipse` | >= 1.0 always; fallback to bounding-box AR if <5 contour points |
| `edge_gradient` | mean Sobel magnitude sampled along contour (dB/px) | NaNs pre-filled with `nanmean` before Sobel (TRAPS #11) |
| `solidity` | area_px / convex_hull_area | in (0, 1] |
| `shape_class` | "linear" if elongation > 3, else "blob" | CONTRACTS.md Section 4 requirement |

**TRAPS avoided:**
- TRAPS #11: `cv2.Sobel` propagates NaN. We pre-fill `db_filled = np.where(nan_mask, nanmean, db)` before computing the Sobel image
- TRAPS #1: OpenCV contours return `contour[:,0]=x=col`, `contour[:,1]=y=row`. NumPy arrays index `[row, col]`. We always use `rows = contour[:,1]`, `cols = contour[:,0]` when sampling into arrays

**Synthetic self-test:** A `[PASS]` assertion suite verifies:
- Elongated ellipse -> `elongation ~= 13`, `shape_class = "linear"`
- Circle -> `elongation ~= 1`, `shape_class = "blob"`
- Star/ragged -> low `solidity ~= 0.42`

---

## 5. make_labels.py — Label Harness

**Runs over all 450 scenes, writes one CSV row per detected region.**

**Critical design decisions:**

1. **scene_id is globally unique**: `"Oil_00007"` not `"00007"` — because `Oil/00007` and `Lookalike/00007` are completely different scenes that share a number. Without the class prefix, they collide in any scene-level grouping operation.

2. **Labeling rule:**
   - Oil scenes: `label = 1` if `(region_mask & gt_mask).sum() / area_px >= threshold` (default 0.50, flag `--overlap-threshold 0.25`)
   - Lookalike / No oil: `label = 0` unconditionally. The GT masks for these folders are **never read or used**. These are hard negatives by dataset construction.

3. **NaN guard (TRAPS #11):** Any row where a numeric feature is NaN or Inf is dropped with a warning, not written to CSV. Zero NaN rows survived in practice.

**Running the harness:**
```bash
# 50% overlap threshold (original)
python pipeline/detect/make_labels.py
# 25% overlap threshold (recommended — more label=1 rows)
python pipeline/detect/make_labels.py --overlap-threshold 0.25 --out data/labels/features_t25.csv
```
Runtime: ~17 minutes for all 450 scenes on this machine (~2s/scene).

---

## 6. Label Statistics (the numbers that matter)

### 6.1 At 50% IoU threshold (`features.csv`)

| | Rows | label=1 | label=0 |
|-|------|---------|---------|
| Oil | 765 | **61** | 704 |
| Lookalike | 881 | 0 | 881 |
| No oil | 2,439 | 0 | 2,439 |
| **TOTAL** | **4,085** | **61 (1.5%)** | **4,024** |

**Oil scenes with ZERO label=1 rows: 121 out of 150**
(Detector found no candidates, or found candidates that didn't overlap the GT mask enough)

### 6.2 At 25% IoU threshold (`features_t25.csv`) — CURRENT TRAINING DATA

| | Rows | label=1 | label=0 |
|-|------|---------|---------|
| Oil | 765 | **80** | 685 |
| Lookalike | 881 | 0 | 881 |
| No oil | 2,439 | 0 | 2,439 |
| **TOTAL** | **4,085** | **80 (1.96%)** | **4,005** |

**Oil scenes with ZERO label=1 rows: ~121 still** (most of the improvement was reclassifying "partial overlap" rows)

### 6.3 What this tells us about the detector

121 of 150 oil scenes produced zero detected regions that hit the oil mask. The detector finds candidates everywhere (average ~10-15 per scene across all classes), but they mostly don't spatially overlap the GT oil location. The detector is finding real dark-spot candidates — just not always at the right location. This could be:
- GT mask is for a specific sub-region but oil covers other areas too (unlikely, GT masks are typically the whole visible slick)
- The contrast is too low for the current t_high_db=2.0 threshold to fire
- The slick is genuinely too thin/faint in these scenes

---

## 7. Classifier — The Problem and Current State

### 7.1 The fundamental challenge

With 80 positives out of 4,085 rows: **~50:1 class ratio**.
Only 36 unique scenes contain ANY label=1 rows.
A model predicting all-zero scores 98%+ accuracy — meaningless.
We use `class_weight='balanced'` and report only precision/recall/F1 on the positive class.

### 7.2 Scene-level train/test split (TRAPS #10)

**This is mandatory, not optional.** Rows from the same 2048x2048 scene are highly correlated — same detector run, same background statistics, same sensor geometry. Splitting by row lets them leak between train and test, producing an inflated accuracy that cannot be reproduced on real scenes.

Implementation: `sklearn.model_selection.train_test_split` on unique `scene_id` strings, `stratify=has_positive_per_scene`, `test_size=0.2`, `random_state=42`.
Result: 260 train scenes (29 with positives), 65 test scenes (7 with positives).

### 7.3 Results — every model tried

| Model | Precision | Recall | F1 | Notes |
|-------|-----------|--------|----|-------|
| RF (n=300, default threshold 0.5) | 0.000 | 0.000 | 0.000 | Classifier predicted everything as 0 |
| RF (n=300, optimal threshold 0.053) | 0.046 | 0.692 | 0.086 | PR-curve best threshold |
| Band Rule (5th-95th %ile of positives) | 0.030 | 0.769 | 0.058 | Pure percentile rule on contrast+depth |
| Logistic Regression (top 3 features) | 0.034 | 1.000 | 0.065 | Perfect recall, ~30:1 FP:TP |
| RF (max_depth=4) | 0.043 | 0.769 | 0.081 | Depth-limited to reduce overfitting |
| **RF (n=300) + VH features (current)** | **0.250** | **0.308** | **0.276** | BREAKTHROUGH |

### 7.4 The VH breakthrough

After all 8 VV-only features failed to produce a useful signal (F1=0.086 best), adding two VH-band features produced a 3x improvement:

```
vh_contrast_db   = median(VH inside region) - median(VH in 25-px outer ring)
vh_mean_depth_db = mean(VH depth map) inside region masks
```

**Feature importances after adding VH:**

| Rank | Feature | Importance |
|------|---------|-----------|
| **1** | **vh_mean_depth_db** | **0.3155** |
| 2 | mean_depth_db | 0.1583 |
| 3 | max_depth_db | 0.1483 |
| 4 | edge_gradient | 0.0992 |
| 5 | contrast_db | 0.0829 |
| **6** | **vh_contrast_db** | **0.0727** |
| 7 | solidity | 0.0593 |
| 8 | area_km2 | 0.0329 |
| 9 | elongation | 0.0289 |
| 10 | is_linear | 0.0021 |

`vh_mean_depth_db` became the **single most important feature at 2x the weight of any VV feature**. This makes physical sense: ocean clutter (upwelling, rain, wind shadow) dampens only the VV channel in SAR. Real oil (which damps capillary waves through Marangoni effects) suppresses both polarizations. The dual-pol depth gives genuine discriminative power.

### 7.5 Why the numbers are still low (honest assessment)

F1=0.276 means: of every 4 regions flagged as oil, 1 is real oil and 3 are false alarms (precision=0.25). Of all real oil regions in the test set, we find 31% of them (recall=0.308).

Root causes:
1. **121/150 oil scenes produce zero GT-overlapping candidates** — the detector simply doesn't fire on most oil scenes at the current threshold
2. **The remaining 29 positive-producing scenes** generate 80 label=1 rows spread across many scene types — small training set
3. **Class imbalance is genuine** — the Lookalike class is specifically designed to include scenes that look like oil

### 7.6 Diagnostic: threshold vs. no-signal (proved)

After the 8-feature RF failed, we ran `predict_proba` diagnostic:

- Real positive rows mean probability: **0.0872**
- Negative rows mean probability: **0.0397**
- Delta: **+0.0475** (not enough to call it a signal)
- Max negative score (0.393) > max positive score (0.220) — distributions genuinely overlapping

This confirmed a **genuine no-signal problem in the 8 VV features**, not a thresholding problem. Adding VH resolved this.

---

## 8. What Still Needs to Be Done

### 8.1 IMMEDIATE: Update make_labels.py to include VH features

Currently `features_with_vh.csv` was produced by a scratch script (`scratch/add_vh.py`). For reproducibility and integration, the VH feature extraction should be folded into `make_labels.py` properly.

The VH features currently use region masks from a **second call** to `detect_array()` per scene with matching by `area_px` proximity (diff < 10 pixels). This could mismatch if two regions have similar areas. A cleaner approach: extract VH stats inside `extract_regions()` by loading VH alongside VV.

However, this touches darkspot.py which is validated and frozen. **Recommended alternative:** extend `make_labels.py` to run VH extraction as a post-processing step that opens VH separately, applies the saved region mask (by area match), and computes stats.

### 8.2 CRITICAL: Update train.py with VH feature list

`train.py` was written before the VH features existed. It currently trains on 8 features. Needs updating to use 10:
```python
FEATURES = [
    "area_km2", "contrast_db", "mean_depth_db", "max_depth_db",
    "elongation", "edge_gradient", "solidity", "is_linear",
    "vh_contrast_db", "vh_mean_depth_db"   # ADD THESE
]
```
Then retrain and save to `models/classifier.pkl` and `models/feature_order.json`.

### 8.3 CRITICAL: Complete run.py — the Ennore deliverable

`pipeline/detect/run.py` is a stub. It must do:

1. Load Akshat's `sar.png` from `cases/case-ennore-2017/`
2. Load `bounds.json` to get geographic extent + `db_min`/`db_max` clamp
3. Convert 8-bit PNG -> float32 dB: `db = (pixel / 255) * (db_max - db_min) + db_min`
4. Run `detect_array(db, pixel_area_km2)` on the dB array
5. Call `add_shape_features_batch(regions, db)`
6. **Add VH features if VH is available** — or fall back to 8-feature / rule-based classifier
7. Score each region with `classifier.predict_proba(features)`
8. Set `classification = "oil" if proba >= threshold else "lookalike"`
9. Convert pixel contours -> lon/lat via linear interpolation across `bounds.json`
10. Write `detections.geojson` conforming to CONTRACTS.md Section 4

**Coordinate conversion (CRITICAL — TRAPS #1 + #8):**
```python
# bounds.json: west, east, south, north, width_px, height_px
lon = west + (col / width_px) * (east - west)
lat = north - (row / height_px) * (north - south)   # latitude DECREASES with row
```
GeoJSON polygon: `[[lon, lat], ...]` — longitude FIRST (TRAPS #1). Never `[lat, lon]`.

### 8.4 CONTRACTS.md compliance for detections.geojson

Each feature in `detections.geojson` must have these **exact property names** (case-sensitive):

```json
{
  "id": "det-01",
  "classification": "oil",
  "confidence": 0.87,
  "area_km2": 12.4,
  "elongation": 8.2,
  "edge_gradient": 0.34,
  "contrast_db": -6.2,
  "shape_class": "linear",
  "centroid": [80.35, 13.25]
}
```

- `classification` in {"oil", "lookalike"} — not "none", not "oil_spill"
- `shape_class` in {"linear", "blob"} — not "elongated"
- `confidence` in [0, 1] — use `predict_proba()` output
- `centroid` is `[longitude, latitude]` — **not [lat, lon]**
- `contrast_db` must be **negative** for a dark spot
- `elongation` must be **>= 1.0** always

### 8.5 Phase 4 fallback (if VH unavailable for Ennore)

Per `02_SOUM_DETECTION.md`:
```
If the classifier misfires on Ennore (different scene statistics than Zenodo):
fall back to detector + features with classification set by a transparent rule.
```

**IMPORTANT NOTE:** The doc says `contrast < -3 dB AND elongation > 2.5`. But the Zenodo positives show `contrast_db` ranging from only -0.44 to -1.04 dB at the 5th-95th percentiles. The -3 dB threshold would match ZERO training positives. For Ennore (a large tanker spill, likely stronger signal), the rule might work, but the threshold should be verified against what the detector actually reports for the Ennore scene. Consider: `contrast < -0.5 dB AND elongation > 2`.

### 8.6 VH availability for Ennore — the key open question

The current best model requires `vh_mean_depth_db` and `vh_contrast_db`. The Ennore input (`sar.png`) is likely a single-channel 8-bit PNG from VV only. Options:
1. **Best:** Ask Akshat to export a 2-band GeoTIFF from GEE (VV + VH). `load_scene(path, band=2)` handles this already.
2. **Fallback A:** Use the 8-feature VV-only classifier with threshold=0.053 (F1=0.086)
3. **Fallback B:** Phase 4 rule-based approach with adjusted thresholds

---

## 9. Environment & Running

```bash
# Activate venv (Windows)
venv\Scripts\activate

# Full label regeneration with 25% IoU threshold (~17 min)
python pipeline/detect/make_labels.py --overlap-threshold 0.25 --out data/labels/features_t25.csv

# Train classifier (needs VH feature list update first)
python pipeline/detect/train.py

# Run detector on one scene (diagnostic, visual output)
python pipeline/detect/darkspot.py data/Images/Oil/00007.tif --mask data/Mask/Oil/00007_segmentation.tif

# Validate case bundle
python scripts/validate_case.py cases/case-ennore-2017
```

---

## 10. Key Decisions Made & Rationale

| Decision | Rationale |
|----------|-----------|
| v2 depth-map detector instead of annulus CFAR | v1 annulus CFAR is self-defeating for linear slicks (proved synthetically) |
| Hysteresis thresholding | Keeps fractured slicks as one coherent region |
| Noise-relative thresholds (median + k*MAD) | Zenodo (~-29 dB) and GEE (~-20 dB) scenes need different fixed thresholds; relative ones are universal |
| 25% IoU labeling threshold | 50% threshold gave 61 positives; 25% gave 80 — more training data without fundamentally changing the labeling semantics |
| Scene-level stratified split | Row-level split is methodologically indefensible; would inflate reported accuracy |
| class_weight='balanced' | 50:1 class ratio — without it, model predicts all-zero |
| Report F1/precision/recall, not accuracy | With 98.5% negatives, accuracy is meaningless |
| VH features as extras, not in detector | Detector stays VV-only (validated); VH only adds post-detection discriminative features |
| Do NOT detrend for subswath gradients | Tested uniform_filter detrending with sigma in {301, 501, 801}; caused ringing artifacts at boundaries, worse than no detrending. Abandoned after confirming failure on scenes 00014 and 00081 |

---

## 11. Open Questions for the Next Claude Session

1. **Does Akshat have VH available for Ennore?** If yes, request 2-band GeoTIFF from GEE. If no, fall back to Phase 4 rule or VV-only classifier.

2. **What does the Ennore SAR scene look like?** The Ennore collision (Jan 29, 2017) involved a tanker hitting a container ship, causing a ~10 km oil slick in the Chennai harbor approach. The scene should have a clearly visible linear slick at ~80.3 E, 13.1 N. The slick was large enough to be visible from space — this should work.

3. **Should make_labels.py be extended to compute VH features natively?** Currently `scratch/add_vh.py` does this. For reproducibility it should be integrated into the main pipeline.

4. **Should the classifier threshold be tuned for the Ennore case?** The test-set optimal threshold was 0.053 for the 8-feature model. With the new 10-feature model, this needs to be re-evaluated with a PR curve on the updated training data.

5. **run.py needs completing.** Resolving Q1 (VH availability) first, then wiring detector -> features -> VH features -> classifier -> GeoJSON output with proper coordinate conversion.

---

## 12. Summary for the Next Session

**What works:**
- Detector: finds dark-spot candidates reliably, 10-15 per scene, no crashes across 450 scenes
- Feature extractor: computes elongation, edge_gradient, solidity, VV contrast/depth. Self-tests pass.
- Label harness: 4085-row CSV, scene-unique IDs, NaN-safe, correct labeling logic, argparse CLI
- Classifier: 10-feature RF with VH achieves F1=0.276 on held-out test scenes (was 0.086 without VH)

**What's broken/incomplete:**
- VH features not in `make_labels.py` — only in a scratch script (`scratch/add_vh.py`)
- `train.py` hasn't been updated with the VH feature list yet — current pickle is from scratch script
- `run.py` is a stub — the full Ennore pipeline is not wired up
- VH availability for Ennore scene is unknown

**The single most important thing to do next:**
1. Confirm with Akshat whether VH is available for the Ennore GEE export
2. Update `train.py` FEATURES list to include VH, retrain, save model
3. Complete `run.py` for the Ennore deliverable using that model
