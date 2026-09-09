# Export + integration — Akshat

Owns: GEE scene export, the bundle assembler, `validate_case.py`, `make_case000.py`.
Full brief: `docs/01_AKSHAT_INTEGRATION.md`. Companion: `docs/05_HARSHITA_INTEGRATION.md`.

## Non-negotiable
- The exporter **copies stage outputs into `cases/<id>/` and runs the validator**. It does not compute anything and it does not repair other people's files.
- GEE export produces FOUR artefacts: `sar_vv_vh.tif` (2-band float32 dB GeoTIFF, ~10 m — Soum's real input, ruling D14), `sar.png` (VV, dB-clamped [-25,0], 8-bit, ~50–100 m/px — display only), `thumb.png` (gallery), `bounds.json` (box + clamp + `vh_available`). Never hand Soum the PNG as data. Tighten the bbox around the slick before dropping resolution.
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
- `gee_scene.py --scene <system:index> --case <id> --bbox W S E N` — the scene export. Writes
  `sar_vv_vh.tif` + `sar.png` + `thumb.png` + `bounds.json`. The GeoTIFF goes via a direct
  download for a tight box, or `Export.image.toDrive` (press RUN in the Tasks tab) for a wide
  one. **Has never been run against GEE — assume the first real run needs a fixing round.**

Phase 0's go/no-go check is `scripts/check_ennore.py`, not here — it answers "does the scene
exist", which is a question about the plan, not about the pipeline.
