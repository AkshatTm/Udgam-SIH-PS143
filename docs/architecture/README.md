# System architecture

Naap answers one question: **a slick is visible in radar — which ship put it there?**

Existing operational systems answer the first half. CleanSeaNet and SkyTruth Cerulean detect
slicks; INCOIS forecasts where oil is *going*. Nobody routinely runs the physics backwards to say
where it *came from* and scores the traffic that was there when it did. That backward half is
what this system is.

The schemas referenced throughout are frozen in
[`../00_MASTER_PLAN.md`](../00_MASTER_PLAN.md) Part 6 (§6.1–6.9), mirrored in
[`../CONTRACTS.md`](../CONTRACTS.md). This page describes the design; it does not restate the
field lists.

---

## The rule that governs everything

**No module imports another module.**

Each stage is a standalone script that reads files from `cases/<case_id>/` and writes files back
into it. The frontend fetches static JSON and never calls Python.

```
                    cases/<case_id>/  ← the only interface between stages
                    ┌──────────────────────────────────────────────┐
  Sentinel-1 SAR ──▶│ sar_vv_vh.tif · sar.png · bounds.json        │
  (via GEE)         │ meta.json                                    │
                    └──────────────────────────────────────────────┘
                                      │
              ┌───────────────────────▼───────────────────────┐
              │ STAGE 1  pipeline/detect/run.py               │
              │ scene classifier → U-Net → classical features │
              └───────────────────────┬───────────────────────┘
                                      ▼  detections.geojson
              ┌───────────────────────────────────────────────┐
  HYCOM   ───▶│ STAGE 2  pipeline/drift/run.py                │
  ERA5    ───▶│ backward advection, 50-member ensemble        │
  (via GEE)   └───────────────────────┬───────────────────────┘
                                      ▼  particles.json · particles_forward.json
                                         origin.json
              ┌───────────────────────────────────────────────┐
  NOAA AIS ──▶│ STAGE 3  pipeline/attribute/run.py            │
  GFW      ──▶│ source classification → component scoring     │
              └───────────────────────┬───────────────────────┘
                                      ▼  vessels.geojson · suspects.json
              ┌───────────────────────────────────────────────┐
  NTSB /   ──▶│ STAGE 4  verification/<case-id>.json          │
  USCG        │ hand-authored, never generated                │
              └───────────────────────┬───────────────────────┘
                                      ▼  verification.json
              ┌───────────────────────────────────────────────┐
              │ web/  Next.js + MapLibre + deck.gl            │
              │ fetches static JSON, no runtime backend       │
              └───────────────────────────────────────────────┘
```

`pipeline/export/build_case.py` publishes each stage's output into the bundle; that publication
step is the seam.

### Why it is built this way

Six people built four components in parallel on four machines without blocking each other. Every
stage can be developed and tested against fake files before the real ones exist — `cases/case-000/`
is a complete synthetic bundle in exactly the real shape, and every stage ships a `--stub` path
that writes schema-valid garbage. Integration is then just the files becoming real.

It has a second payoff that matters more on the day: **the interface has no runtime network
dependency**. The pipeline runs offline and exports a bundle; the app plays it back. It works with
the wifi switched off. This is stated openly rather than hidden — precomputed is fine, hardcoded
fake results are not.

If you are about to write `from pipeline.drift import ...` in detection code, stop.

---

## The case bundle

A case is a directory. Everything about it — the imagery, every stage's output, the provenance —
is in that directory, and the gallery is one index file listing them.

```
cases/<case_id>/
  meta.json                 case info, which acts are available
  sar.png                   display raster
  sar_vv_vh.tif             2-band float32 dB GeoTIFF — Stage 1's real input
  bounds.json               geographic bounds + the dB clamp used
  thumb.png                 gallery preview
  cerulean_slick.geojson    SkyTruth's polygon — comparison target, optional, never the answer
  detections.geojson        Stage 1 → Stage 2, and → frontend
  particles.json            Stage 2 → frontend (the backward rewind)
  particles_forward.json    Stage 2 → frontend (forward prediction)
  origin.json               Stage 2 → Stage 3, and → frontend
  vessels.geojson           Stage 3 → frontend (AIS tracks)
  suspects.json             Stage 3 → frontend (ranked suspects, funnel, exclusions)
  verification.json         Stage 4 → frontend
cases/index.json            the gallery list, strongest case first
cases/_archive/             retired cases — never indexed, never validated
```

`meta.json`'s `acts_available` declares which stages exist for that case, so a detect-only
benchmark tile and a full four-stage case are the same kind of object with different contents.

### The validator is the contract

```bash
python scripts/validate_case.py cases/<case_id>     # must print PASS
```

It catches lat/lon swaps, naive timestamps, unit errors, dimension mismatches and funnel
inconsistencies **by name**, and it has its own mutation test suite (`scripts/test_validator.py`)
that deliberately corrupts a good bundle 26 ways and checks each corruption is caught.

**Failures are fixed in the producing code, never by hand-editing the bundle.** That rule is what
keeps a bundle usable as evidence of what the code actually does.

---

## The four stages

| Stage | Input | Output | Detail |
|---|---|---|---|
| 1 · Detect | `sar_vv_vh.tif` | `detections.geojson` | [stage1-detection.md](stage1-detection.md) |
| 2 · Trace | `detections.geojson` + ocean/wind fields | `particles*.json`, `origin.json` | [stage2-drift.md](stage2-drift.md) |
| 3 · Attribute | `origin.json` + AIS | `vessels.geojson`, `suspects.json` | [stage3-attribution.md](stage3-attribution.md) |
| 4 · Verify | the official investigation | `verification.json` | [stage4-verification.md](stage4-verification.md) |

---

## Conventions that are frozen across all of it

Violating any of these produces code that runs and returns confident wrong numbers, which is the
expensive failure mode in this domain. [`../TRAPS.md`](../TRAPS.md) catalogues the specific bugs.

1. Coordinates are **`[longitude, latitude]`**, WGS84 (EPSG:4326). Never `[lat, lon]`.
2. Timestamps are **UTC ISO 8601 with a trailing `Z`**, timezone-aware.
3. Units: km, km², m/s, degrees clockwise from north; coordinates to 5 dp in JSON.
4. `duration = (n_steps − 1) × timestep_minutes`. Never hardcode a frame count — 97 steps × 15 min
   is exactly 24 h.
5. `origin.json` grid row 0 is **north**. `origin.bounds` is **not** `bounds.json`; they are
   different rectangles.
6. **`null` ≠ `0`.** A not-applicable score is `null`; a measured zero is `0`. Rendering one as
   the other is an honesty bug, and the validator fails on it.

---

## What the design deliberately does not do

- **No live inference in the demo path.** Nothing loads a model over the network while a judge is
  watching.
- **No cross-stage imports**, so no stage can silently depend on another's in-memory state.
- **No model switching at a threshold.** Stage 2 runs its own model and OpenDrift and renders
  both, rather than picking one by a rule that cannot be validated (decision D6).
- **No naming a vessel when a vessel is not the right kind of answer.** Source classification runs
  before attribution; see [stage3-attribution.md](stage3-attribution.md).
