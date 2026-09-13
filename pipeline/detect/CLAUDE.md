# Detection (Stage 1) — Soum

Owns: scene classifier → U-Net segmentation → classical features → ship detections →
`detections.geojson`. Full brief: `docs/team/soum-stage1-detection.md`. Architecture: Master v3 §4.3.

> **This file was rewritten 12 Sept.** The previous version said "NO deep learning this sprint,
> the CNN is October work" and "Zenodo Part III only". Both are now wrong — Master v3 §4.3 and
> decisions D2/D4 put the two networks in the shipped architecture, and Parts I+II are on disk.
> If you are reading a cached copy that says otherwise, this one wins.

## Three layers
```
Layer 1  scene classifier (SceneCNN)  "is there oil here at all?"  -> headline accuracy, and
                                       it GATES Layer 2 (D2 — the authors report their U-Net
                                       segments erroneously on look-alikes)
Layer 2  U-Net segmentation           "exactly which pixels?"      -> IoU, and the polygon
Layer 3  classical features           "why, and what shape?"       -> the explainability bars
```
The classical depth-map detector is **not** retired. It is the ablation baseline, the fallback
when a network misbehaves on a GEE-domain scene, and the ship detector.

## Non-negotiable
- **Per-scene MAD normalisation before any network sees a pixel.** Never raw dB. Measured on our
  own data: VV median is −33.3 dB in Part 1, −29.3 dB in Part 3, −20.2 dB in the Huntington GEE
  export, and MADs vary 10× *within Part 3 alone*. A model fitted on absolute values fails on
  another domain **without erroring**. It has already happened once: the absolute-dB RandomForest
  scored a textbook −6 dB slick at confidence 0.00. `nets.normalise_scene()` is the only
  normaliser; `build_cache.normalise()` must stay identical in meaning to it.
- **Train on Parts I+II, evaluate on Part III, never the reverse** (D1). Part III is the dataset
  authors' designated test set.
- **Split by SOURCE SCENE, not by row or tile.** Regions and tiles from one 2048×2048 image share
  background statistics and often the same slick.
- **Thresholds are chosen on a validation split, never on Part III.** Picking an operating point
  by looking at test performance is test-set contamination through the back door.
- `shape_class = "linear" if elongation > 3 else "blob"` — carries physics to Stage 2, don't drop it.
- Polygons go out in **[lon, lat]**, longitude first. Georeference from the **GeoTIFF's own affine
  transform**, not `bounds.json`'s `width_px`/`height_px` — those describe `sar.png`, which is a
  separately downsampled display raster (Huntington: PNG 505×577, GeoTIFF 1337×1281).

## Data on disk
```
data/Images/{Oil,Lookalike,No oil}/{id}.tif          Parts I+II — 1200 + 685 + 685 = 2570 scenes
data/Mask/{Oil,Lookalike,No oil}/{id}.tif            masks are {id}.tif  ← NO _segmentation suffix
data/test/Images/{class}/{id}.tif                    Part III — 150 + 150 + 150 = 450 scenes
data/test/Mask/{class}/{id}_segmentation.tif         masks ARE {id}_segmentation.tif here
data/cache/                                          tile cache (gitignored, ~10 GB)
```
Two traps, both of which fail **silently**:
1. The mask suffix differs between the parts. A missing mask means every oil region is labelled 0.
2. Ids are **sparse** (Part 1 Oil runs 00000–01339, 1200 files) and **collide across parts** —
   `Oil/00007` exists in Part 1 *and* Part 3 and they are different scenes. Hence `P12_`/`P3_`
   prefixes on every `scene_id`. Glob the directory; never iterate a numeric range.
3. Look-alike and no-oil masks are **entirely zero** — checked, not assumed. They localise
   nothing, so hard negatives are selected by darkness instead.

## Env
`numpy scipy opencv-python scikit-image scikit-learn rasterio shapely matplotlib` plus
**`torch==2.6.0` + `torchvision==0.21.0` (cu124)**, added 12 Sept, pinned with its
justification in `requirements-detect.txt` and broadcast by Akshat. Training needs the GPU; inference falls back to CPU.

## Order of operations
```bash
python pipeline/detect/make_labels.py --parts 1,2 --overlap-threshold 0.25 --out data/labels/features_train.csv
python pipeline/detect/make_labels.py --parts 3   --overlap-threshold 0.25 --out data/labels/features_test.csv
python pipeline/detect/build_cache.py --parts 1,2
python pipeline/detect/build_cache.py --parts 3
python pipeline/detect/train.py                 # Layer 3 / classical baseline
python pipeline/detect/train_classifier.py      # Layer 1
python pipeline/detect/train_unet.py            # Layer 2
python pipeline/detect/evaluate.py --report     # the ablation table
python pipeline/detect/run.py --case case-huntington-2021
```

## Check before handover — BOTH gates
```bash
python scripts/plot_detections.py --case <id>     # the human gate
python scripts/validate_case.py cases/<id>        # the schema gate
```
The validator proves a bundle is schema-valid. It will happily PASS a mirrored polygon, because
a mirror image shares a centroid. Look at the picture (Master §8.4).

## Self-tests that must keep passing
```bash
python pipeline/detect/features.py    # synthetic shape assertions
python pipeline/detect/ships.py       # ship merge + chronic/acute
python pipeline/detect/nets.py        # 50%-overlap tiling reconstructs with no seams
```
