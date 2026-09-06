# Detection (Stage 1) — Soum

Owns: dark-spot finder → shape features → oil/look-alike classifier → `detections.geojson`.
Full brief: `docs/02_SOUM_DETECTION.md`. Setup: `docs/SETUP_SOUM.md`.

## Non-negotiable
- **NO deep learning this sprint.** The CNN is October work. Classical CV + RandomForest only.
- Train/test split is **by SOURCE SCENE, not by row.** Regions from one scene are correlated; a row-level split inflates the number we put in front of judges.
- `shape_class = "linear" if elongation > 3 else "blob"` — this field tells Stage 2 how to seed particles. It carries physics; don't drop it.
- Polygons go out in **[lon, lat]**. Pixel (0,0) = top-left = (west, north) from `bounds.json`; convert by linear interpolation.

## Data
Zenodo Part III only (`data/zenodo_p3/`, gitignored, ~9.9 GB): 150 oil + 150 look-alike + 150 no-oil, 2048x2048x2 GeoTIFF (VV,VH) in dB, plus masks. Masks are NOT georeferenced — treat them as plain arrays. Labels come from mask overlap (≥50% of a region's pixels), never by hand.

## Env
opencv-python, scikit-image, scikit-learn, rasterio, shapely, numpy. No GPU needed anywhere in this directory.

## Check before handover
Plot `detections.geojson` over `sar.png` — polygons must sit on the dark patches, coordinates ~80.x E / 13.x N for Ennore. Then `python scripts/validate_case.py cases/<id>`.

---

## The stub that is already here
`run.py --case <id> --stub` writes a schema-valid `out/detections.geojson` full of garbage. It exists to prove the seam before the logic exists. **Delete its `stub_detections()` wholesale** when the real detector lands — do not grow it into the real thing. The `--case` argument, the `out/` directory and the write helper are the parts worth keeping.

Read the dB clamp from `bounds.json` (`db_min` / `db_max`, defaulting to −25/0) rather than hardcoding it — that is how the 8-bit PNG maps back to decibels, and if Akshat re-exports with a different clamp your features shift silently.
