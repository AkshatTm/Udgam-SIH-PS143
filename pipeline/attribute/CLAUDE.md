# Attribution (Stage 3) — Jaiveer

Owns: AIS ingest → track reconstruction → scoring → `vessels.geojson` + `suspects.json`.
Full brief: `docs/05_JAIVEER_AIS.md`. Setup: `docs/SETUP_JAIVEER.md`.

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

---

## The stub that is already here
`run.py --case <id> --stub` reads `cases/<id>/origin.json` and writes schema-valid `out/vessels.geojson` + `out/suspects.json`. It exists to prove the seam before any AIS is downloaded.

It already implements two things worth keeping because the validator enforces them: the **abstain path** (`origin.abstain == true` → empty suspects, funnel still populated) and the funnel/suspect consistency rules (monotonic counts, `scored == len(suspects)`, every suspect MMSI present in `vessels.geojson`, descending score order). **Delete** `fake_fleet()` and the invented MMSIs the moment real AIS lands — those names are placeholders and must never reach a judge.
