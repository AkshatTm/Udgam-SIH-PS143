# SOUM — Stage 1: Detection
*Read with 00_MASTER_PLAN.md. You own detection end to end: dark-spot finder → features → classifier → `detections.geojson`. The CNN is killed for this sprint (October); do not start it.*

## You produce
`pipeline/detect/` · `data/labels/features.csv` (the labelled training table) · trained classifier pickle in `pipeline/detect/models/` · **real `detections.geojson` for the Ennore scene (Tue evening — this is your hard deadline)** · held-out precision/recall numbers · later: detections for the US scene and the no-spill scene.

## You consume
Zenodo Part III (your download) · `sar.png` + `bounds.json` from Akshat (Mon evening) · the contract in Master §4.

## Tools
Until the 8th: Codex + Antigravity (this work is very promptable — classical CV, no exotic APIs). From the 8th: your Claude Pro, spent mostly on debugging. GPU irrelevant — nothing here needs it. **Disk check first: you need ~25 GB free (9.9 GB archive + extraction).**

## AI split
AI writes 100% of the code. YOU judge: do the outlines sit on the dark patches when plotted? Are the feature values plausible (elongation 1–15, contrast negative, areas 0.1–100 km²)? Is held-out accuracy real (never test on training rows)?

---

## Phase 1 — Tonight/Sun (~3 h, mostly unattended)
1. Start Part III download: zenodo.org/records/13761290 (one 9.9 GB 7z). Extract → `data/zenodo_p3/` (gitignored). While it runs: GEE auth, repo clone, venv.
2. Verify: 150 oil + 150 lookalike + 150 no-oil TIFFs with masks, 2048×2048×2 (VV,VH), values in dB. AI writes `load_scene(path) -> np.ndarray` (rasterio; use VV band; handle NaNs by masking).
3. **Stub-first:** commit `detect/run.py --fake` that writes a schema-valid `detections.geojson` with garbage. Run Akshat's validator on it.

## Phase 2 — Mon (~5 h) · the detector and the label harness
1. **Dark-spot detector** (`detect/darkspot.py`): on the dB image → local adaptive threshold (pixel dark if below local mean − k·std over a large window; start k≈1.5), morphological open then close to denoise, connected components, drop regions < ~0.05 km² and > ~500 km², return region masks + contours. Tune k on 5 oil scenes until the slick is one coherent region.
   **Checkpoint (send to group):** 3 Part III oil images with detector outlines plotted over them — outlines visibly on the dark patches, mask overlap obvious.
2. **Features** (`detect/features.py`) per region: area_km2 (pixel area × pixel size), perimeter, **elongation** (major/minor axis via cv2.fitEllipse or PCA of pixel coords), **edge_gradient** (mean Sobel magnitude along the contour), **contrast_db** (mean inside − mean in a surrounding ring), std of dB inside, solidity (area/convex-hull area). `shape_class = "linear" if elongation > 3 else "blob"`.
3. **Label harness** (`detect/make_labels.py`): run the detector over ALL Part III scenes; each detected region → label **1 if ≥50% of its pixels overlap the ground-truth oil mask** (only oil scenes have nonzero masks), else 0. Regions from lookalike/no-oil scenes are automatic hard negatives. Write `features.csv` (one row per region: features + label + source scene). Expect several hundred rows. If oil rows < 50, loosen the threshold k and rerun — the detector is missing slicks.

## Phase 3 — Tue (~5 h) · classifier + the real deliverable
1. **Train** (`detect/train.py`): RandomForest (~300 trees) on features.csv. **Split by SOURCE SCENE, not by row** — rows from one scene are correlated; a row-level split will flatter you and a judge-facing number must be honest. Report held-out precision + recall for the oil class. Whatever the number is, it goes on the honesty slide. Commit the pickle.
2. **Run on Ennore** (`detect/run.py --case case-ennore-2017`): load Akshat's `sar.png` + `bounds.json` (8-bit PNG → map back to dB with the known clamp [-25,0]) → detector → features → classifier → polygons in pixel coords → **lon/lat via linear interpolation across bounds (pixel 0,0 = west,north — Master §4)** → write `detections.geojson`. Run the validator.
   **Sanity you personally do:** plot the geojson over the PNG — polygons on the dark streak, coordinates ~80.x E / 13.x N. If lon and lat look swapped the validator will scream; fix before handing over.
3. Hand to Akshat with the run command.

## Phase 4 — Wed
Buffer. Fix whatever integration exposed. If the classifier misfires on Ennore (different scene statistics than Zenodo — possible): fall back to detector + features with `classification` set by a transparent rule (oil if contrast < −3 dB AND elongation > 2.5), say so honestly, keep the feature card. The card is the demo asset; the label source is secondary for the HOD.

## Phase 5 — Event days
Run on the US scene (new sar.png from Akshat, same command). Pick one convincing Part III look-alike scene for the **no-spill case** and run it — output must contain zero "oil" features (look-alikes shown grey is even better). Give Urooz 4 good chips: 1 oil + 3 look-alikes, 512×512 PNG crops, dB-stretched the same way.

## Escalate to Akshat (45-min rule)
Download corrupt/stalled · masks not aligning with images · Ennore PNG stats look nothing like Zenodo (he may need to re-export with different clamp).

## Definition of done
`features.csv` committed (hundreds of rows) · scene-split precision/recall reported in the group · valid `detections.geojson` for Ennore Tue evening, plotted proof attached · US + no-spill detections by freeze · 4 quiz chips delivered to Urooz.
