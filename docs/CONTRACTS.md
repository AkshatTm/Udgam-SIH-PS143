# CONTRACTS — FROZEN (v1 — superseded by Master Plan §6)

> **Read `00_MASTER_PLAN.md` Part 6 (§6.1–6.9) for the live contract.** This file is the v1
> record and is missing the v3 additions the validator now enforces: `verification.json`,
> `cases/index.json`, the `verify` act, extended `suspects.json` (`source_type`, `components`
> with `null`, `dark_vessels[]`, `infrastructure[]`), and the v3 `meta.json` / `origin.json`
> fields. Where the two disagree, Master §6 wins. Kept for history, not extended further.

**Status: FROZEN as of Sun 6 Sept 2026.** Extracted verbatim from `00_MASTER_PLAN.md` Part 6.

Changes go through **Akshat only**, and are broadcast to the whole group the moment they are
made. Do not extend a schema unilaterally — if something genuinely cannot be expressed in these
shapes, say so and we change it here, once, for everyone.

Before handing anything to Akshat:
```bash
python scripts/validate_case.py cases/<case_id>
```
Must print `PASS`. Fix failures in the **producing code**, never by hand-editing a bundle
(`TRAPS.md` #20 — a hand-patched bundle means the same bug returns at the worst moment).

---

## 0. Conventions that apply to every file (Master §3)

1. Coordinates are **`[longitude, latitude]`**, WGS84 / EPSG:4326. GeoJSON order. **Never `[lat, lon]`.**
2. All times are **UTC, ISO 8601, trailing `Z`** — `2017-01-29T00:14:00Z`. Timezone-aware only;
   a naive datetime is a bug.
3. Units: distances **km**, areas **km²**, speeds **m/s**, angles **degrees clockwise from north**.
4. Coordinates rounded to **5 decimal places** max in JSON (≈1 m; keeps files small).
5. Pixel `(0, 0)` is **top-left = (west, north)**. Latitude *decreases* as row index increases.
   Pixel → lon/lat is linear interpolation across `bounds.json`.

---

## 1. The bundle

Every case is one directory. No stage imports another stage; each reads files from the case
folder and writes files back into it. The frontend fetches static JSON and never calls Python.

```
cases/<case_id>/
  meta.json           case info, which acts are available
  sar.png             the radar scene rendered as an image
  bounds.json         geographic bounds of sar.png
  detections.geojson  Stage 1 output → Stage 2 input, and → frontend
  particles.json      Stage 2 output (the rewind animation data)
  origin.json         Stage 2 output → Stage 3 input, and → frontend
  vessels.geojson     Stage 3 output (AIS tracks)
  suspects.json       Stage 3 output (ranked suspects, funnel, exclusions)
```

Which files are required is driven by `meta.acts_available`:

| act | requires |
|---|---|
| `detect` | `detections.geojson` |
| `trace` | `particles.json`, `origin.json` (and `detect`) |
| `attribute` | `vessels.geojson`, `suspects.json` (and `trace`) |

`meta.json`, `bounds.json` and `sar.png` are required in every bundle.

---

## 2. meta.json

```json
{
  "case_id": "case-ennore-2017",
  "title": "Ennore collision — Chennai, Jan 2017",
  "satellite": "Sentinel-1A",
  "scene_id": "<GEE system:index of the scene>",
  "detection_time": "2017-01-29T00:14:00Z",
  "acts_available": ["detect", "trace"],
  "notes": "No free AIS for Indian waters; attribution act intentionally unavailable."
}
```

- `acts_available` ⊆ `["detect", "trace", "attribute"]`, non-empty.
- The frontend **must handle a missing act gracefully** — greyed-out stage in the rail with a
  short explanation on hover. Not a crash. Ennore has no AIS; the US case has all three.
- `detection_time` is the satellite pass. `particles.t0` must equal it.

## 3. bounds.json

```json
{ "west": 80.10, "south": 12.95, "east": 80.70, "north": 13.55,
  "width_px": 1400, "height_px": 1400,
  "db_min": -25, "db_max": 0 }
```

- Pixel `(0, 0)` is top-left = `(west, north)`.
- `west < east`, `south < north`, longitudes in −180…180 (**never 0…360** — see `TRAPS.md` #5).
- `db_min` / `db_max` are **optional and additive** (added Sun 6 Sept, announced to the group).
  They record the dB clamp used when the 8-bit PNG was written, so Stage 1 can map the PNG back
  to decibels with the *same* clamp. Without them, if the exporter's clamp ever changes, every
  feature Soum computes shifts silently (`TRAPS.md` #7, second-order trap). Consumers must
  default to `[-25, 0]` when the keys are absent.

## 4. detections.geojson — Stage 1 → Stage 2, and → frontend

GeoJSON `FeatureCollection`. Each feature:

```json
{ "type": "Feature",
  "geometry": { "type": "Polygon", "coordinates": [[[lon, lat], "..."]] },
  "properties": {
    "id": "det-01",
    "classification": "oil",
    "confidence": 0.87,
    "area_km2": 12.4,
    "elongation": 8.2,
    "edge_gradient": 0.34,
    "contrast_db": -6.2,
    "shape_class": "linear",
    "centroid": [80.35, 13.25]
  } }
```

- `classification` ∈ `{"oil", "lookalike"}`.
- `shape_class` ∈ `{"linear", "blob"}`, defined as `"linear" if elongation > 3 else "blob"`.
  **This field carries physics** — it tells Stage 2 whether to seed particles along the principal
  axis (a moving ship) or from the centroid (a stationary event). Don't drop it.
- `elongation` is major/minor axis, so it is **never below 1**.
- `contrast_db` is inside-minus-surrounding, so for a dark spot it is **negative**.
- `confidence` ∈ [0, 1]. `area_km2` > 0.
- **A no-spill case is a FeatureCollection with zero `"oil"` features.** Look-alikes may still be
  present. This is a designed state, not an error.

## 5. particles.json — Stage 2 → frontend

```json
{ "t0": "2017-01-29T00:14:00Z",
  "direction": "backward",
  "timestep_minutes": 15,
  "n_steps": 97,
  "n_particles": 3000,
  "positions": [ [[lon, lat], "... n_particles pairs"], "... n_steps arrays" ] }
```

- `positions[0]` = particle positions at `t0`. `positions[n_steps - 1]` = positions at
  `t0 − (n_steps − 1) × timestep_minutes`. With `n_steps: 97` and `timestep_minutes: 15` that is
  exactly `t0 − 24 h`. **Duration is always derived as `(n_steps − 1) × timestep_minutes` — never
  hardcode the frame count anywhere.**
- `len(positions) == n_steps`; every timestep has exactly `n_particles` entries. Particles are
  never added or dropped mid-run.
- `t0` must match `meta.detection_time` within 60 s — the rewind starts at the satellite pass.
- ~3000 × 97 ≈ 5 MB, which is acceptable. If it grows, **decimate steps; never break the schema.**

## 6. origin.json — Stage 2 → Stage 3, and → frontend

```json
{ "bounds": { "west": 0, "south": 0, "east": 0, "north": 0 },
  "shape": [120, 120],
  "values": ["... 14400 floats, row-major from top-left, normalised 0–1"],
  "centroid": [80.21, 13.31],
  "radius_50_km": 4.2,
  "radius_90_km": 11.8,
  "time_window": ["2017-01-28T08:00:00Z", "2017-01-28T20:00:00Z"],
  "ensemble_runs": 50,
  "abstain": false }
```

- `shape` is `[rows, cols]`; `len(values) == rows * cols`.
- `values` is **row-major from the top-left**, i.e. **row 0 is the NORTH edge**. NumPy's default
  `.ravel()` (C order) is correct; `order='F'` is the bug (`TRAPS.md` #9).
- Values normalised to peak at 1.0, never negative.
- `radius_50_km <= radius_90_km` (the 50% mass sits inside the 90% mass).
- `time_window` **doubles as the age statement.** We quote the window; we do *not* run a separate
  age model.
- `abstain: true` means the cloud is too diffuse (agreed rule: `radius_90_km > 40`). Stage 3 must
  then produce **zero suspects**, and the frontend shows "attribution not possible at acceptable
  confidence". The refusal is a designed feature, not a failure.

## 7. vessels.geojson — Stage 3 → frontend

`FeatureCollection` of `LineString` tracks:

```json
{ "type": "Feature",
  "geometry": { "type": "LineString", "coordinates": [[80.1, 13.2], "..."] },
  "properties": { "mmsi": "367123450", "name": "EXAMPLE STAR", "vessel_type": "tanker",
                  "n_points": 214, "max_gap_minutes": 85 } }
```

- At least 2 points per track. Decimate to ≲500 points so the map stays fast.
- Every MMSI referenced in `suspects.json` must have a track here.

## 8. suspects.json — Stage 3 → frontend

```json
{ "funnel": { "in_region": 412, "in_window": 63, "plausible": 12, "scored": 3 },
  "suspects": [
    { "mmsi": "367123450", "name": "EXAMPLE STAR", "vessel_type": "tanker",
      "score": 0.82, "closest_km": 3.1, "closest_time": "2017-01-28T14:20:00Z",
      "heading_consistent": true, "ais_gap_minutes": 85,
      "reasons": ["inside 50% origin radius during window",
                  "85-min transponder gap overlapping window"] } ],
  "excluded": [
    { "mmsi": "367999999", "name": "OTHER SHIP", "closest_km": 6.4,
      "reason": "heading away from origin throughout the window" } ] }
```

- **Funnel counts must decrease monotonically**: `in_region ≥ in_window ≥ plausible ≥ scored`.
  These four numbers are requirement (c) made visible on screen.
- `funnel.scored == len(suspects)`.
- `suspects` sorted by **descending** `score`; `score` ∈ [0, 1].
- **At least one exclusion, with a stated plain-language reason.** Exoneration without a reason
  is worse than no exoneration. Empty `reason` strings are rejected.
- If `origin.abstain` is true, `suspects` **must** be empty (funnel is still populated).

---

## 9. Honesty rule (binding)

Internals carry to December before an NTRO panel. No vessel name or MMSI that isn't in the real
AIS file. No detection the detector didn't produce. No accuracy number not measured on a
held-out, **scene-level** split.

Precomputed is fine and we say so openly: the pipeline runs offline and exports a case bundle,
the interface plays it back — that's why it never breaks on venue wifi. Hardcoded fake results
are not fine. `cases/case-000/` is the one synthetic bundle in the repo and it is never shown
to a judge.
