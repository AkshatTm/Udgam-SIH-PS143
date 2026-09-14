# Export + integration — Akshat

Owns: GEE scene export, the bundle assembler, `validate_case.py`, `make_case000.py`.
Full brief: `docs/team/akshat-integration.md`. Companion: `docs/team/harshita-integration.md`.

## Non-negotiable
- The exporter **copies stage outputs into `cases/<id>/` and runs the validator**. It does not compute anything and it does not repair other people's files.
- GEE export produces FOUR artefacts: `sar_vv_vh.tif` (2-band float32 dB GeoTIFF, ~10 m, bands labelled VV/VH — Soumirya's real input, ruling D14), `sar.png` (VV, dB-clamped 8-bit, ~20–25 m/px — display only; the clamp is per-case and recorded in `bounds.json`), `thumb.png` (gallery), `bounds.json` (box + `db_min`/`db_max` + `vh_available`). Never hand Soumirya the PNG as data. Tighten the bbox around the slick before dropping resolution.
- `bounds.json` and the PNG must agree exactly: pixel (0,0) = top-left = (west, north).
- When a bundle fails validation, the fix goes back to the producing owner with the validator error. Never patch a bundle by hand — the same bug will return on the next run.

## Integration debugging order (fastest first)
1. Run the validator — it names most seam bugs directly.
2. Plot `detections.geojson` and `particles.json[0]` together: particles must sit on the slick.
3. Compare `meta.detection_time` with `particles.t0`: must match within 60 s.
4. Check `origin.json` centroid isn't on land.

---

## What lives here
- `build_case.py --case <id>` — gathers `pipeline/*/out/` into `cases/<id>/`, then runs the
  validator and exits non-zero on failure. Copies and validates. Nothing else.
- `scripts/find_scenes.py --project P --bbox W S E N --start D --end D [--incident D]` — list
  every Sentinel-1 IW pass over the box. Generalised `check_ennore.py`. Pick the scene that
  covers your slick box (a footprint can clip it — check by exporting, not by trusting the list).
- `gee_scene.py --scene <system:index> --case <id> --bbox W S E N` — the scene export. Writes
  `sar_vv_vh.tif` (bands labelled VV/VH) + `sar.png` + `thumb.png` + `bounds.json`. GeoTIFF via
  direct download when the box fits ~8 M px × 2 bands, else `--drive` → `Export.image.toDrive`
  (`task.start()` runs it server-side; then move it from Drive). `--no-geotiff` for a
  PNG-only look. Battle-tested on Huntington Beach (2026-09-10).
- `scripts/inspect_db.py --scene S --slick lon lat ... --clean lon lat ...` — sample raw VV/VH
  dB. A real slick is several dB below clean sea in BOTH bands; dark in VV only = wind.

## Per-case export checklist (Phase 2.5 — do NOT batch, each case unblocks 3 people)

1. `find_scenes.py` over the search box + incident window. Note the `system:index`, UTC time, pol.
2. `gee_scene.py --no-geotiff` with a stretch tuned to the sea (`--db-min/--db-max`). **Open
   `sar.png`.** Coast where land is, grey speckle for sea, slick a dark streak with a *crisp*
   edge (a gradient edge is wind, not oil).
3. `inspect_db.py` on the feature. Record the VV/VH depression. No dual-band depression → it is
   not a hero detection case; say so (see `PHASE1_CASE_FINDINGS.md`).
4. Full `gee_scene.py` run with a **tight** `--bbox` on the slick. Confirm the GeoTIFF: 2 bands,
   `EPSG:4326`, bounds == `bounds.json`, VV median ≈ −20 dB.
5. Hand-edit `cases/<id>/meta.json` to real v3 values (`title`, `short_location`, `case_type`,
   `gallery.blurb` as a question, `difficulty`). `acts_available: ["detect"]` until stages land.
6. `verification/<id>.json` — fill `official_finding` from the primary source; leave
   `assessment.explanation` a Phase-4 TODO.
7. Add `<id>` to `cases/index.json` (strongest first).
8. Announce to the group: scene id · UTC · bounds · pol. Jaiveer downloads AIS, Anushka fetches
   the ocean, Soumirya runs inference — all keyed off that message.

**The `.tif` travels in git.** `cases/*/sar_vv_vh.tif` is whitelisted in `.gitignore` (the
no-imports architecture needs Stage 1's input to reach whoever runs Stage 1). ~8-10 MB/case.

Phase 0's go/no-go check is `scripts/check_ennore.py` — Ennore-specific; `find_scenes.py` is the
general one.
