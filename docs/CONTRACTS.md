# CONTRACTS — the frozen file schemas (v4, current)

> ## Precedence, and the one rule that keeps this file honest
>
> **`docs/00_MASTER_PLAN.md` Part 6 (§6.1–6.9) is the source of truth. This file is a mirror.**
> Where the two disagree, Master wins and this file is the bug.
>
> **If you change a schema you change it in Master first, and mirror it here in the same commit.**
> That is the only condition under which having two copies is acceptable. This file was left
> frozen at v1 once before; the frontend's `web/lib/contracts.ts` kept pointing at it, and the
> result was a frontend missing `case_type`, `gallery`, `ais_source`, `known_origin` and
> `component_notes` — five fields it was supposed to render. That is what drift costs.
>
> Changes go through **Akshat only** and are broadcast to the group the moment they are made.
> Do not extend a schema unilaterally. If something genuinely cannot be expressed, ask.

**Why this file exists separately at all:** it is the thing you keep open in a second tab while
writing a producer or a consumer, without scrolling a 900-line plan. Nothing here is new; it is
Master Part 6 plus the decision numbers that explain *why* each field is shaped the way it is.

---

## 0. The conventions every file obeys

These are not per-schema. Violating one is how the project dies.

1. **Coordinates are `[longitude, latitude]`**, WGS84 / EPSG:4326, everywhere. Never `[lat, lon]`.
2. **Timestamps are UTC, ISO 8601, trailing `Z`, timezone-aware.** A naive datetime is a bug.
3. **Units:** km, km², m/s, degrees clockwise from north. Coordinates rounded to 5 dp in JSON.
4. **`duration = (n_steps − 1) × timestep_minutes`.** Never hardcode a frame count.
   97 steps × 15 min = exactly 24 h (**D13**).
5. **`origin.json` grid row 0 is NORTH.**
6. **`origin.bounds` is not `bounds.json`.** Different rectangles, deliberately.
7. **`null` ≠ `0`.** A not-applicable score is `null`; a measured zero is `0`. The frontend
   renders `null` as "n/a" and **never as a zero bar**. Rendering one as the other is an honesty
   bug, not a display bug.
8. **Pixel (0,0) is top-left = (west, north).**

---

## 1. `meta.json`

```json
{
  "case_id": "case-huntington-2021",
  "title": "Huntington Beach — San Pedro Bay Pipeline",
  "short_location": "Orange County, California",
  "case_type": "spill",
  "provenance": "satellite",
  "satellite": "Sentinel-1A",
  "scene_id": "<GEE system:index — the real one>",
  "detection_time": "2021-10-02T01:58:21Z",
  "acts_available": ["detect", "trace", "attribute", "verify"],
  "ais_source": "noaa_dense",
  "known_origin": {
    "lon": -118.11, "lat": 33.60,
    "label": "documented fixed source",
    "source_url": "https://www.ntsb.gov/..."
  },
  "gallery": {
    "thumbnail": "thumb.png",
    "blurb": "588 barrels of crude reached Orange County beaches. What released it?",
    "difficulty": "hard"
  },
  "notes": "free text"
}
```

| Field | Rule |
|---|---|
| `case_type` | `spill \| lookalike \| nospill` |
| `provenance` | `satellite \| benchmark` — optional, absent means `satellite` (D33) |
| `acts_available` | subset of `["detect","trace","attribute","verify"]`, non-empty |
| `gallery.difficulty` | `easy \| medium \| hard` |
| `gallery.blurb` | written as a **question** — it is the gallery card's hook |
| `ais_source` | `noaa_dense \| gfw_hourly` — **required whenever `attribute` is available** |

**Dependency rules the validator enforces:**
`trace` requires `detect` **or** `meta.known_origin` · `attribute` requires `trace` ·
`verify` requires `verification.json` to exist · `attribute` requires `ais_source`.

**`provenance` (D33).** Which corpus the pixels came from, and therefore which of Stage 1's two
detection paths runs: `satellite` (our GEE exports → classical CV + RandomForest) or `benchmark`
(Zenodo Part III → CNN scene classifier). `scene_provenance()` reads this field. It must **not**
sniff the CRS: Zenodo Part III tiles carry EPSG:4326 and a real geotransform just like a GEE
export, so that test never discriminated anything. It also decides what `detections.geojson/
confidence` means — model probability on `benchmark`, rule margin on `satellite`. See Master §6.1
and §6.3, which are the live contract; this file is the v1 record.

**`ais_source` (D20).** NOAA Marine Cadastre reports at a ~71-second median interval; Global
Fishing Watch's presence layer gives **one position per vessel per hour** — roughly 50× sparser.
At 12 knots a ship covers ~22 km in an hour, so on a `gfw_hourly` case the `gap` component is
**structurally impossible** and `slowdown` is very coarse. Those return `null`, the remaining
weights renormalise, and the card says "n/a". Say it openly rather than hiding it.

**`known_origin` (optional, D16).** A documented fixed source the trace stage seeds from when
there is no SAR-visible slick — a wreck, a pipeline right-of-way, a collision position. Either
`[lon, lat]` or an object with `lon`/`lat` plus optional `label` and `source_url`. When present it
substitutes for a detection: the bundle may carry `trace` (and `attribute`, `verify`) without
`detect`, and `detections.geojson` is not required. **The frontend must render such an origin as
*seeded from a documented source*, never as a UDGAM detection.** Allowed on a normal detection case
too, as a ground-truth pin. **No case in the current library uses this path.**

---

## 2. `bounds.json`

```json
{ "west": -118.17, "south": 33.585, "east": -118.05, "north": 33.70,
  "width_px": 505, "height_px": 577,
  "db_min": -25.0, "db_max": -5.0,
  "vh_available": true }
```

Describes `sar.png`. Pixel (0,0) is **top-left = (west, north)**.

`db_min`/`db_max` record the dB stretch used for the PNG **so Stage 1 can invert it exactly** —
read the PNG back to decibels with these numbers, not with a guess. **The clamp is per case**
(it is derived from that box's own VV percentiles), and **changing one is a broadcast, not a
silent edit.** `vh_available` says whether `sar_vv_vh.tif` carries a second band.

> **D26:** v1–v3 of this file described a `db_clamp: [min, max]` pair. It was never written by
> `gee_scene.py` nor read by anybody. The three scalars above are the shipped shape.

**`sar_vv_vh.tif`, alongside it:** 2-band float32 GeoTIFF in dB at 10 m, band 1 = VV, band 2 = VH,
**unclamped — it holds the true values** (**D14**). **Nodata is `-inf`, not a low dB number.**
Scene-edge nodata is real in this library; treating it as backscatter detects a giant false slick.

---

## 3. `detections.geojson`

FeatureCollection. Each feature:

```json
{ "type": "Feature",
  "geometry": {"type": "Polygon", "coordinates": [[[lon,lat], "..."]]},
  "properties": {
    "id": "det-01",
    "classification": "oil",
    "confidence": 0.87,
    "area_km2": 12.4,
    "elongation": 8.2,
    "edge_gradient": 0.34,
    "contrast_db": -6.2,
    "shape_class": "linear",
    "discharge_class": "chronic",
    "centroid": [-118.15, 33.62]
  } }
```

The scene's radar contacts sit **beside** `features`, on the FeatureCollection (D34):

```json
{ "type": "FeatureCollection",
  "ship_detections": [
    {"lon": -118.104, "lat": 33.602, "px_area": 340, "peak_db": -4.2}
  ],
  "features": [ ... ] }
```

`classification` ∈ `oil | lookalike` — **not** "none", **not** "oil_spill".
`shape_class` ∈ `linear | blob` · `discharge_class` ∈ `chronic | acute | unknown`.
`confidence` ∈ [0,1] · `contrast_db` **negative** for a dark spot · `elongation` **≥ 1.0**.
`ship_detections` is **top-level and scene-level** (D34): absent = the ship detector was not run
or not recorded, `[]` = it ran and found none. The per-feature `properties.ship_detections` of v1
is deprecated — still accepted, no longer written, and must agree with the top-level list if both
appear. It moved because a scene with zero detections had nowhere to put its contacts.
**A radar contact is not a dark vessel:** darkness needs an AIS cross-check at a known time, so a
contact without one is *unattributed*. Master §6.3 is the live contract; this file is the v1 record.

**A no-spill case is a FeatureCollection with zero `oil` features.** Look-alikes may still be
present, and showing them greyed with the reason they were rejected is the point of the screen.
Zero oil features is a **result**, not an empty file.

`discharge_class` changes what two other people do: `chronic` means the vessel was moving and the
origin is a **line segment**, not a point.

---

## 4. `particles.json` and `particles_forward.json`

```json
{ "t0": "2021-10-02T01:58:21Z",
  "direction": "backward",
  "timestep_minutes": 15,
  "n_steps": 97,
  "n_particles": 3000,
  "positions": [ [[-118.1, 33.6], "... n_particles pairs"], "... n_steps arrays" ] }
```

`positions[0]` is at `t0`; `positions[n_steps−1]` is at `t0 − (n_steps−1)×dt`. 97 steps at 15 min
is exactly `t0 − 24 h` (**D13**). `t0` must match `meta.detection_time` within 60 s.

**`particles_forward.json` is the same shape with `"direction": "forward"`. It is a SEPARATE
file and a second integration — never an overwrite or a relabelled copy of the rewind.** The
validator compares the two and rejects identical position arrays.

---

## 5. `origin.json`

```json
{ "bounds": {"west": -118.4, "south": 33.5, "east": -118.0, "north": 33.9},
  "shape": [120, 120],
  "values": ["... rows*cols floats, row-major from top-left, normalised 0–1"],
  "centroid": [-118.21, 33.71],
  "radius_50_km": 4.2,
  "radius_90_km": 11.8,
  "time_window": ["2021-10-01T08:00:00Z", "2021-10-01T20:00:00Z"],
  "time_window_method": "bounded",
  "ensemble_runs": 50,
  "abstain": false,

  "age_hours": [8, 16],
  "age_method": "combined",
  "age_weathering": "fresh",
  "age_estimators": {"shear": [7,18], "fay": null, "elongation": null, "track": [5,20]},
  "age_posterior": {"hours_grid": [1, 2, "... 72"], "prob": ["... sums to 1"],
                    "hpd80": [8.5, 16.5], "median": 11.2, "hypotheses": ["patch", "track"],
                    "evidence": ["shape", "track"], "models": ["udgam_rk2", "opendrift_openoil"],
                    "calibration_coverage": 0.81},

  "stranded_fraction": 0.03,
  "wind_share": 0.37,
  "opendrift_comparison": {"centroid_separation_km": 2.4, "r90_ratio": 1.08},
  "model_mix": {"models": [{"name": "udgam_rk2", "weight": 0.5, "points": 1080000},
                           {"name": "opendrift_oceandrift", "weight": 0.5, "points": 730000}]}
}
```

**`shape` is `[rows, cols]` and row 0 is NORTH.** `values` length must equal `rows × cols`, is
never negative, and is normalised to peak 1.0.

`time_window_method` ∈ `bounded | convergence | age`. **`bounded` means a SEARCH BRACKET, not a measured
release time — the frontend must render the two differently** (**D12**). This is a claim we have
to defend, which is why it is in the contract rather than in someone's head. **`age` (D45)** means
the window is the 80 % interval of this slick's age posterior and the origin is the ensemble
pooled over it. It requires `age_posterior`, and `age_hours` must equal `age_posterior.hpd80`.

`age_method` ∈ `shear | fay | elongation | track | combined | disagreement | none` ·
`age_weathering` ∈ `fresh | weathered | unknown` · an `age_estimators` entry is `[low, high]`
**or `null`** where that estimator did not apply.

`age_posterior` (D45, optional): hourly grid, `prob` summing to 1, `hpd80`, `median`, which
hypotheses and models contributed, and the held-out synthetic-twin coverage (or `null`). Absent
when no age was measured. `model_mix` (D45, optional): the models pooled into the origin grid,
weights summing to 1. A different claim from `opendrift_comparison`; never merge them.

`age_gate` (D45) ∈ `acute | chronic_track | unknown_both | no_detection`. `age_refusal` (D46,
optional): `{reason: low_information | no_estimator | no_detection, info_gain_nats, min_gain_nats}`,
only when `age_method` is `none` and never alongside `age_posterior`. Live text: Master §6.5.

`abstain: true` forces Stage 3 to return zero suspects. Agreed trigger: `radius_90_km > 40`.

The age, posterior, stranding, wind, comparison and model-mix blocks are **optional** — absence
hides a UI row, it does not throw.

**Score the grid, not the `radius_50_km` circle (D8).** The real cloud measured 4.38:1 aspect with
44.7% of high-probability mass outside r50. The radii stay as the one-number summary for the UI;
they are the wrong instrument for a membership test.

---

## 6. `vessels.geojson`

FeatureCollection of LineString tracks:

```json
{ "type": "Feature",
  "geometry": {"type": "LineString", "coordinates": [[-118.1, 33.6], "..."]},
  "properties": {"mmsi": "367123450", "name": "EXAMPLE STAR",
                 "vessel_type": "tanker", "n_points": 214,
                 "max_gap_minutes": 85} }
```

Plausible-set vessels only. Decimate to ≤500 rendered points with endpoints preserved;
`n_points` reports the **undecimated** count. **MMSI is a VARCHAR** — it is an identifier, not a
quantity, and arithmetic on it is always a bug.

---

## 7. `suspects.json`

```json
{
  "funnel": {"in_region": 412, "in_window": 63, "plausible": 12, "scored": 3,
             "dropped_short_track": 15},
  "suspects": [
    { "source_type": "vessel",
      "mmsi": "367123450", "name": "EXAMPLE STAR", "vessel_type": "tanker",
      "score": 0.82,
      "components": {"proximity": 0.91, "parity": 0.74, "temporality": 0.63,
                     "trajectory": 1.0, "gap": 1.0, "slowdown": null,
                     "type_prior": null},
      "component_notes": {
        "slowdown": "vessel never dropped below cruising speed in the window",
        "type_prior": "every candidate here is a tanker or cargo ship — no discrimination available"
      },
      "closest_km": 3.1, "closest_time": "2021-10-01T14:20:00Z",
      "grid_probability": 0.91,
      "heading_consistent": true, "ais_gap_minutes": 85,
      "edge_truncated": false,
      "repeat_offender": {"cases": ["case-x"], "best_rank": 2},
      "reasons": ["inside the high-probability origin region during the window",
                  "85-minute transponder gap overlapping the window",
                  "track runs parallel to the slick axis"] }
  ],
  "dark_vessels": [
    { "source_type": "dark_vessel", "name": "Unidentified radar contact",
      "mmsi": null,
      "lon": -118.104, "lat": 33.602, "est_length_m": 120,
      "score": 0.71, "angular_deviation_deg": 12,
      "reasons": ["radar detection with no AIS broadcast within 500 m at scene time"] }
  ],
  "infrastructure": [
    { "source_type": "infrastructure", "name": "San Pedro Bay Pipeline",
      "lon": -118.11, "lat": 33.60, "score": 0.88,
      "reasons": ["origin probability peak lies on the pipeline right-of-way",
                  "no vessel scored above threshold"] }
  ],
  "natural_seep": {
    "flagged": false,
    "source": null,
    "note": null
  },
  "excluded": [
    { "mmsi": "367999999", "name": "OTHER SHIP", "closest_km": 6.4,
      "reason": "heading away from the origin throughout the window" }
  ],
  "abstained": false,
  "abstain_reason": null
}
```

**Hard rules:**
- Funnel counts **decrease monotonically**; `funnel.scored` equals `len(suspects)`.
- Suspects sorted by **descending** score.
- **Every suspect `mmsi` must have a matching track in `vessels.geojson`.** The validator enforces
  it, and that is what makes the honesty rule mechanical rather than a promise.
- Dark vessels have **`mmsi: null`** and never an invented identity.
- `abstained: true` requires `suspects` empty. Same for `origin.abstain`.
- At least one `excluded` entry, each with a non-empty `reason` — **exoneration without a reason
  is worse than no exoneration.**

### 7.1 The four source types (D10, D19)

`source_type` ∈ `vessel | dark_vessel | infrastructure | natural_seep`.

A system that can only consider vessels **will name a vessel even when the source is a pipeline.**
That is a false accusation and the worst failure mode here, which is why source classification
runs *before* attribution:

```
origin reconstructed
  → fixed infrastructure at the origin?   → infrastructure
  → known natural seep area?              → natural_seep
  → radar ship with no AIS?               → dark_vessel
  → otherwise score the AIS fleet         → vessel
```

`natural_seep` is an **object, not a list**: either the detection sits in documented seep territory
or it does not. **`flagged: true` requires a citable `source` and a `note`** — a bare flag does not
go on screen. Not claimed on any case in the current library.

### 7.2 Applicability gating — `null`, never a stand-in number

A component returns `null` when it **cannot be measured**. This is a statement about
applicability, not a thumb on the scale, and it gets said out loud on the limitations slide.

| Component | `null` when | Ruling |
|---|---|---|
| `gap` | AIS too sparse to resolve a silence (`gfw_hourly`), the vessel was not under way, or the "silence" is the search-box edge | D9, D20 |
| `slowdown` | the vessel never varied speed enough for a slowdown to mean anything | D9 |
| `trajectory` | **no report outside `radius_90_km`** in the window — the vessel was never observed approaching, so there is no approach to assess | **D27** |
| `type_prior` | **every scored candidate shares a type class** — the component then adds the same constant to everyone, changing no ranking while inflating every score | **D28** |
| `parity` | `discharge_class != "chronic"` — a blob has no meaningful centerline | D9 |

**When a component is not applicable it contributes nothing and the remaining weights
renormalise.** The validator **errors** on a numeric `gap`/`slowdown` on a `gfw_hourly` case, and
**warns** when a non-null component holds the identical value for every scored suspect.

### 7.3 `component_notes` (D29)

Optional object keyed by component name, short plain-language string values.

**It is explanation, not evidence** — a note may not introduce any fact the card is not already
showing. **Every `null` component should carry one**, because the UI renders `null` as "n/a" and an
unexplained "n/a" on a judge-facing card reads as a broken feature rather than a deliberate refusal
to measure the unmeasurable. *"hourly AIS cannot resolve a transponder gap"* turns the weakest-
looking part of the screen into the most convincing.

---

## 8. `verification.json`

```json
{
  "official_finding": {
    "summary": "NTSB determined MSC Danit's anchor contact with the San Pedro Bay Pipeline on 25 Jan 2021 was the initiating event leading to the October 2021 crude release.",
    "responsible_parties": [
      {"name": "MSC DANIT", "mmsi": null, "imo": "9404649", "role": "initiating anchor strike"}
    ],
    "source_name": "NTSB Marine Investigation Report MIR-24-01",
    "source_url": "https://www.ntsb.gov/...",
    "source_type": "official_investigation",
    "volume_reported": "588 barrels",
    "caveat": "The anchor strike preceded the release by eight months. No vessel was the proximate source at detection time."
  },
  "udgam_result": {
    "origin_summary": "Origin cloud centred on the pipeline right-of-way, 2.1 km from the reported leak location.",
    "top_suspects": ["367123450"],
    "abstained": false
  },
  "assessment": {
    "verdict": "hit",
    "explanation": "HUMAN-WRITTEN PROSE. Never generated.",
    "what_would_have_helped": "..."
  }
}
```

`verdict` ∈ `hit | partial | miss | not_applicable`. `source_url` must be present and non-empty —
it is the "is this real?" link. `explanation` must be non-empty and is **written by hand**.

`source_type` ∈ `official_investigation | algorithmic_attribution | press | none`.
**SkyTruth Cerulean is `algorithmic_attribution`, never `official_investigation`** — it is another
algorithm's output with analyst review, not a court finding, and the wording is *"Cerulean
attributed this slick to vessel X"*, never *"X was proven responsible"*.

**A `miss` ships as readily as a `hit`**, and the screen styles it just as confidently.

> **Timing, and it matters: this file IS the answer.** It ships inside the bundle where everyone
> can read it, so writing it early ends the blind evaluation for that case. It is authored *after*
> the bundle validates, never before. See `verification/README.md`.

---

## 9. `cases/index.json`

```json
{ "cases": ["case-jacksonville-2024", "case-farallones-2023", "..."],
  "default": "case-jacksonville-2024" }
```

Presentation order, strongest first. **The frontend never hardcodes a case list.**
A case directory not listed here is not in the demo; `cases/_archive/` is skipped entirely.

---

## 10. What the validator will not catch

`python scripts/validate_case.py cases/<id>` proves a bundle is **schema-valid**. It says nothing
about whether it is **renderable or physically sensible** — it will happily pass an origin cloud
drifting upstream, an upside-down grid, or a mirrored polygon (mirror images share a centroid, so
a centroid check passes).

**A bundle is not integrated until it passes the validator *and* Harshita has opened it in the
browser.** Two gates, checking different things.
