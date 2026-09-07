# Per-directory CLAUDE.md files
*Claude Code reads the nearest `CLAUDE.md` walking up from the working directory, so a person working in `pipeline/drift/` gets the root file **plus** their own. Copy each block below into the stated path. Keep them short — the root file carries everything shared.*

---
## `pipeline/detect/CLAUDE.md` — Soum
```markdown
# Detection (Stage 1) — Soum

Owns: dark-spot finder → shape features → oil/look-alike classifier → `detections.geojson`.
Full brief: `docs/02_SOUM_DETECTION.md`.

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
```

---
## `pipeline/drift/CLAUDE.md` — Anushka
```markdown
# Drift (Stage 2) — Anushka

Owns: backward particle advection through real current+wind fields, 50-run ensemble, origin probability cloud. Full brief: `docs/03_ANUSHKA_DRIFT.md`.

## Non-negotiable
- **No ML here.** Pure physics: `velocity = current + 0.03 * wind`, RK2, dt = 15 min, vectorised NumPy.
- **Backward = negative dt through the same field.** NOT a minus sign on velocity.
- `drift/tests.py` must stay green on every change. Four known-answer tests: constant current (0.5 m/s east, 10 h → 18.0 km east), round trip (forward then backward returns within 0.5 km), wind-only (10 m/s → 0.3 m/s), and permanent plausibility asserts (speed < 3 m/s; 48 h displacement 5–200 km).
- **HYCOM velocity bands on GEE are a scaled integer (units m/s, scale 0.001) — divide by 1000, not 100.** This is the single most common silent bug in this component; ÷100 leaves every current 10× too fast.
- Longitudes stay in −180…180, never 0…360.
- Output is always a **probability grid**, never a point. Ensemble spread IS the uncertainty.

## Env
numpy, scipy, earthengine-api, matplotlib (for the sanity plots). No GPU.
Cache GEE fields to `data/fields/<case>.npz` — never re-fetch during iteration.

## Every phase ends in a picture
Quiver plot of the current field, track plot of one particle, heatmap of the origin cloud. Post them in the group. Wrong-but-running code is the failure mode these catch.
```

---
## `pipeline/attribute/CLAUDE.md` — Jaiveer
```markdown
# Attribution (Stage 3) — Jaiveer

Owns: AIS ingest → track reconstruction → scoring → `vessels.geojson` + `suspects.json`.
Full brief: `docs/05_JAIVEER_AIS.md`.

## Non-negotiable
- **No ML.** Deterministic weighted score; weights are named constants at the top of the file.
  proximity .40 · trajectory .20 · slowdown .15 · gap .15 · type_prior .10
- **Every vessel name and MMSI on screen must come from the real NOAA AIS file.** If the documented incident's vessel doesn't rank top-3, that is the result we show. Never reweight to force an outcome.
- The **funnel** counts (in_region ≥ in_window ≥ plausible ≥ scored) are requirement (c) made visible. They must decrease monotonically.
- At least **one exclusion with a stated plain-language reason**. Exoneration without a reason is worse than none.
- If `origin.json` has `abstain: true`, suspects MUST be empty. The refusal is a designed feature.
- Do NOT build MMSI identity resolution. One demo case; MMSI as-is; known imperfection.

## Env
duckdb or geopandas, pyarrow, shapely, pandas. **Filter to bbox+time on read** — never load a whole NOAA CSV into pandas. Raw AIS stays in `data/ais/` (gitignored) on your machine only.

## You are remote
Post an end-of-day update in the group every single day and append to `docs/updates/jaiveer.md`. Nobody can see your screen; silence reads as risk.
```

---
## `pipeline/export/CLAUDE.md` — Akshat
```markdown
# Export + integration — Akshat

Owns: GEE scene export, the bundle assembler, `validate_case.py`, `make_case000.py`.
Full brief: `docs/01_AKSHAT_INTEGRATION.md`.

## Non-negotiable
- The exporter **copies stage outputs into `cases/<id>/` and runs the validator**. It does not compute anything and it does not repair other people's files.
- GEE export: `COPERNICUS/S1_GRD`, VV band, clamp dB to [-25, 0], scale to 8-bit, ~50–100 m/px. Do not fight for 10 m full resolution — the PNG must stay a few MB.
- `bounds.json` and the PNG must agree exactly: pixel (0,0) = top-left = (west, north).
- When a bundle fails validation, the fix goes back to the producing owner with the validator error. Never patch a bundle by hand — the same bug will return on the next run.

## Integration debugging order (fastest first)
1. Run the validator — it names most seam bugs directly.
2. Plot `detections.geojson` and `particles.json[0]` together: particles must sit on the slick.
3. Compare `meta.detection_time` with `particles.t0`: must match within 60 s.
4. Check `origin.json` centroid isn't on land.
```

---
## `web/CLAUDE.md` — Harshita
```markdown
# Frontend — Harshita

Owns the entire judge-facing app. Full brief: `docs/04_HARSHITA_FRONTEND.md`.

## Non-negotiable
- **NEVER use localStorage or sessionStorage.** State lives in memory (Zustand).
- **The frontend never calls Python.** It fetches static JSON from `cases/<id>/`. If a field is missing or malformed, show a visible error and tell Akshat — do not patch data client-side.
- Stack is fixed: Next.js + MapLibre GL JS (no token) + deck.gl (ScatterplotLayer for particles, HeatmapLayer for origin) + Tailwind + Recharts + Zustand. Decide Next vs Vite on day one and never switch.
- `meta.acts_available` drives the stage rail. A missing act is a greyed stage with a tooltip, not a crash. Ennore has no `attribute`.
- Zero oil features in `detections.geojson` is the **no-spill case** — a designed state with a banner, not an error.

## Performance (the demo lives or dies here)
- Parse each bundle **once** into memory; consider Float32Array for particle positions.
- Scrubbing must not re-fetch, re-parse, or re-render the map container. Slider state feeds the deck layer only, via `updateTriggers`.
- No per-frame allocation in the animation loop.
- Test the full 3000 particles x 97 steps on the actual demo machine, not just yours.

## Escape hatches if it stutters (both invisible to a viewer)
Decimate to every 2nd timestep · drop to 2000 particles. Never change the schema.
```
