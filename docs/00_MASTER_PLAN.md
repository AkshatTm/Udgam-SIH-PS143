# NAAP — MASTER PLAN v3
## SIH 2026 · PS 26143 · Final demo: 15 September, 17:00

> **This supersedes v1 and v2 completely.** It is the single source of truth for architecture, contracts, ownership, dependencies and decisions.
>
> **How to use it.** Read Parts 1–5 once, fully. Keep Part 6 (contracts) open while you code — that is where integration fails. Check Part 8 before you say you are blocked. If your personal document conflicts with this one, this one wins. If this one conflicts with reality, tell Akshat — never improvise a schema.
>
> **Everything is organised in PHASES, not days.** Finish a phase, log it, move on. Where a phase says WAIT, do the next unblocked phase and come back.

---

# PART 1 — WHAT WE ARE BUILDING

## 1.1 One sentence
Satellite forensics that traces an oil spill back to the ship that caused it.

## 1.2 The problem, and why it is not already solved here
Oil is spilled at sea; the ship sails away. Radar satellites revisit a given patch of ocean only every few days, so by the time a slick is visible it has been drifting for hours or days.

Europe has fused satellite spill detection with ship transponder data since the 2000s. India has **forward** drift prediction — INCOIS runs an operational advisory to the Indian Coast Guard — and **no backward attribution capability at all**.

> *"INCOIS tells the Coast Guard where the oil is going. Nobody tells them where it came from. We built the other half."*

## 1.3 Who this is for
Sponsored by **NTRO**, India's technical intelligence agency — not the environment ministry, not the Coast Guard. Their underlying interest is **maritime domain awareness**: identifying vessels that behave anomalously and go dark at sea. Spill attribution is the demonstrator; the capability generalises.

Two framings of the same system:
- **College jury:** environmental protection, catching polluters who think the ocean has no witnesses.
- **NTRO panel:** maritime domain awareness — correlating overhead imagery with transponder data to identify vessels operating dark.

## 1.4 The four stages
| Stage | Does | Owner |
|---|---|---|
| **1 Detect** | Find slicks in Sentinel-1 SAR, separate oil from look-alikes, measure geometry, find ships | Soum |
| **2 Trace** | Run currents and wind backwards to reconstruct where and when the oil entered the water | Anushka |
| **3 Attribute** | Score vessels, dark vessels and fixed infrastructure against that origin; rank and exclude | Jaiveer |
| **4 Verify** | Compare our conclusion against the official investigation, cited | Akshat writes, Harshita renders |

## 1.5 The binding honesty rule
Internals are binding — **whatever we present on 15 September we defend before an NTRO panel in December.** Therefore:
- No vessel name or MMSI on screen that is not in the real AIS file
- No detection the detector did not produce
- No accuracy number not measured on a held-out, scene-level split
- **A `MISS` on the verification screen ships as readily as a `HIT`**

Precomputation is fine and we say so openly: *"the pipeline runs offline and exports a case bundle; the interface plays it back — that's why it scrubs instantly and can't break on venue wifi."* Fabricated results are not fine.

---

# PART 2 — THE DEMO

## 2.1 Five screens, one direction
```
 GALLERY ──▶ DETECT ──▶ TRACE ──▶ ATTRIBUTE ──▶ VERIFY ──▶ back to GALLERY
 pick a      what is     where &     who did       were we
 case        the slick   when        it            right
```

**The HOD's requirement: a judge operates this with no instructions and nobody standing over them.** That reshapes the frontend from a dashboard into a guided flow. One primary action per screen, always bottom-right. Nothing blank on arrival. The Trace screen **auto-plays its rewind once** so the judge sees the interaction without being told. Idle reset to the gallery after ~90 s so the next judge gets a clean state.

## 2.2 What each screen shows
**0 Gallery** — case cards with thumbnail, title, location, date, a `SPILL`/`LOOK-ALIKE`/`NO SPILL` badge, and a blurb written as a question. First card visually emphasised. Strongest case first.

**1 Detect** — SAR scene, detection outlines already drawn, best oil detection pre-selected, object card with measured features and the "why this classification" bars. Look-alikes shown grey and clickable, showing *why* they were rejected.

**2 Trace** — the rewind slider. Particles unwind; the origin cloud blooms and **visibly widens** the further back you go. Live `T − Xh Ym` readout. Origin card with radii, release window and age band.

**3 Attribute** — the funnel (412 → 63 → 12 → 3), ranked suspect cards with per-component evidence, the exclusion panel, dark-vessel markers, infrastructure findings.

**4 Verify** — two columns: what NAAP concluded versus what the official investigation concluded, with the source document linked, and a verdict badge. **`MISS` is styled as confidently as `HIT`.**

## 2.3 The four claims the demo proves
1. We can tell oil from things that look like oil
2. We can run the physics backwards
3. We can quantify how unsure we are
4. We can turn that into a shortlist of ships — **and say who it wasn't**

---

# PART 3 — THE CASE LIBRARY

| # | Case | Type | Acts | Role |
|---|---|---|---|---|
| 1 | **Ennore, Chennai — 29 Jan 2017** | spill | detect, trace, verify | India relevance. INCOIS published a drift model we benchmark against. **No free AIS for Indian waters — no attribution, and we say why.** |
| 2 | **Huntington Beach / San Pedro Bay — Oct 2021** | spill | all | **Infrastructure + exoneration case.** NTSB MIR-24-01 names MSC DANIT and BEIJING. |
| 3 | **Golden Ray, St Simons Sound — Aug 2021** | spill | all | Fixed wreck source. SkyTruth published imagery. |
| 4 | **TBD — vessel source, US waters** | spill | all | A transiting-vessel discharge |
| 5 | **TBD — vessel source, US waters** | spill | all | Second, ideally a different basin |
| 6 | **Look-alike scene** (Zenodo Part 3) | lookalike | detect | System correctly says "not oil" |
| 7 | **No-spill scene** (Zenodo Part 3) | nospill | detect | System correctly says "nothing here" |

## 3.1 The four hard constraints on every US case
1. **US waters** — NOAA Marine Cadastre AIS is free and bulk-downloadable; Indian coastal AIS is not published
2. **Between Oct 2014 and 5 Sep 2024** — Sentinel-1 GRD starts Oct 2014; **HYCOM's GEE archive ends 2024-09-05**
3. **Sentinel-1 coverage confirmed** by running the finder script, not assumed
4. **A citable official finding** — NTSB, USCG, or a documented press account naming the vessel

## 3.2 Ennore — CONFIRMED
```
Scene:  S1A_IW_GRDH_1SDV_20170129T003132_20170129T003157_015039_01892E_6D04
Time:   2017-01-29 00:31:32 UTC  =  06:01 IST, the morning after the collision
Bands:  VV + VH + angle     Mode: IW
Box:    approx [80.0, 12.9, 80.8, 13.6]
```
Four Sentinel-1 passes exist over the box between 28 Jan and 15 Feb 2017, all IW, all VV+VH. Two of the four are adjacent frames of the same orbit pass 25 s apart; the frame grid does not align to the lat/lon box, so two catch only a sliver. `..._6D04` is the one with full coverage. Fallback: `..._49A5` (10 Feb).

**Still to confirm:** that a dark feature is actually visible on the water. A scene with no visible slick is not a hero case whatever the metadata says.

## 3.3 Finding cases 4 and 5
**SkyTruth's Cerulean public map** (`cerulean.skytruth.org`) is a searchable database of slick detections already attributed to named vessels. Filter to US waters, take two with clean linear slicks, and the Cerulean record becomes the verification source.

Two caveats that must carry into `verification.json`:
- Cerulean is **another algorithm's output, not court-proven ground truth.** Write *"SkyTruth Cerulean attributed this slick to vessel X"*, never *"vessel X was proven responsible"*.
- Cerulean is **prior art** — see Part 11.

Fallbacks: NOAA Incident News archive, USCG investigation reports.

---

# PART 4 — ARCHITECTURE

## 4.1 The rule that makes six people possible
**No module imports another module.** Every stage is a script that reads files from `cases/<case_id>/` and writes files back into it. The frontend fetches static JSON and never calls Python.

This is why four people built four working components in parallel on four machines without ever blocking each other. It stays.

## 4.2 The case bundle
```
cases/<case_id>/
  meta.json                 case info, which acts exist
  sar.png                   display raster
  sar_vv_vh.tif             2-band float32 dB GeoTIFF  ← Soum's real input
  bounds.json               geographic bounds + the dB clamp used
  thumb.png                 gallery preview
  detections.geojson        Stage 1 → Stage 2, and → frontend
  particles.json            Stage 2 → frontend (the rewind)
  particles_forward.json    Stage 2 → frontend (forward prediction)
  origin.json               Stage 2 → Stage 3, and → frontend
  vessels.geojson           Stage 3 → frontend
  suspects.json             Stage 3 → frontend
  verification.json         Stage 4 → frontend
cases/index.json            the gallery list
```

## 4.3 Stage 1's internal architecture *(changed in v3)*
Three layers, not two:
```
Layer 1  scene classifier (small CNN)   "is there oil here at all?"   → headline accuracy
Layer 2  U-Net segmentation             "exactly which pixels?"       → IoU, and the polygon
Layer 3  classical hand-crafted features "why, and what shape?"        → the explainability bars
```
The classifier gates the U-Net because the dataset's own authors found U-Net **segments erroneously on look-alike images**. Without the gate, cases 6 and 7 come back with hallucinated oil — and those two cases exist specifically to prove the system can say no.

The classical detector survives as the **ablation baseline**, the **fallback**, and the **ship detector**.

## 4.4 Stage 2's model, and OpenDrift *(decided in v3)*
Production is our own **reduced-order surface advection model**: `velocity = current + 0.03 × wind`, RK2, 15-minute steps, backward via negative dt, 50-member stratified ensemble.

**We do not switch to OpenDrift and we do not switch between models at a threshold.** We run both and render both clouds. Where they agree that is independent confirmation from MET Norway's operational tool; where they diverge, the pattern diagnoses which physics accounts for it.

**Why ours stays in production:** it is validated (5 suites, 20 assertions, exact to 0.000%), the stratified ensemble is the product and OpenDrift gives one trajectory per run, two other people consume its output, and because Anushka wrote every line her guard caught a 10× unit error before a single particle moved.

## 4.5 Stage 3's three source types *(new in v3)*
| Type | Meaning | Our cases |
|---|---|---|
| `vessel` | Broadcasting ship near the origin at the right time | 4, 5 |
| `dark_vessel` | Radar sees a ship; AIS reports nothing | our best differentiator |
| `infrastructure` | Pipeline, platform or wreck — stationary | **2, 3** |

Without the infrastructure module the correct answer on Huntington Beach is "no vessel responsible", which reads as failure. **With it, the answer is "the source is fixed infrastructure and all transiting vessels are excluded" — which is a hit**, and it is what the NTSB concluded.

---

# PART 5 — FROZEN CONVENTIONS

Violating these is how the project dies. They are in `CLAUDE.md` too.

1. **Coordinates are `[longitude, latitude]`**, WGS84 (EPSG:4326), everywhere. Never `[lat, lon]`.
2. **Timestamps are UTC, ISO 8601, trailing `Z`, timezone-aware.** Naive datetimes are a bug.
3. **Units:** km, km², m/s, degrees clockwise from north. Coordinates to 5 dp in JSON.
4. **`duration = (n_steps − 1) × timestep_minutes`.** Never hardcode a frame count. 97 steps × 15 min = exactly 24 h.
5. **`origin.json` grid row 0 is NORTH.**
6. **`origin.bounds` is not `bounds.json`.** They are different rectangles.
7. **`null` ≠ `0`.** A not-applicable score is `null`; a measured zero is `0`. Rendering one as the other is an honesty bug.
8. Python 3.11 + venv, pinned. Node 20 for `web/`. **No new dependencies after the pipeline is assembling; none at all after the freeze.**

---

# PART 6 — THE FROZEN CONTRACTS

**Keep this section open while you code.** Every field, every allowed value.

## 6.1 `meta.json`
```json
{
  "case_id": "case-huntington-2021",
  "title": "Huntington Beach — San Pedro Bay Pipeline",
  "short_location": "Orange County, California",
  "case_type": "spill",
  "satellite": "Sentinel-1A",
  "scene_id": "<GEE system:index — the real one>",
  "detection_time": "2021-10-03T01:52:00Z",
  "acts_available": ["detect", "trace", "attribute", "verify"],
  "gallery": {
    "thumbnail": "thumb.png",
    "blurb": "588 barrels of crude reached Orange County beaches. What released it?",
    "difficulty": "hard"
  },
  "notes": "free text"
}
```
`case_type` ∈ `spill | lookalike | nospill` · `difficulty` ∈ `easy | medium | hard` · `acts_available` ⊆ `["detect","trace","attribute","verify"]`.

Dependency rules the validator enforces: `trace` requires `detect`; `attribute` requires `trace`; `verify` requires `verification.json` to exist.

## 6.2 `bounds.json`
```json
{ "west": -118.30, "south": 33.50, "east": -117.80, "north": 33.80,
  "width_px": 1400, "height_px": 1400,
  "db_clamp": [-25, 0] }
```
Pixel (0,0) is **top-left = (west, north)**. `db_clamp` records the stretch used for `sar.png` so Soum can invert it exactly. **If the clamp changes that is a broadcast, not a silent edit.**

## 6.3 `detections.geojson`
FeatureCollection. Each feature:
```json
{ "type": "Feature",
  "geometry": {"type": "Polygon", "coordinates": [[[lon,lat], ...]]},
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
    "centroid": [-118.15, 33.62],
    "ship_detections": [
      {"lon": -118.104, "lat": 33.602, "px_area": 340, "peak_db": -4.2}
    ]
  } }
```
`classification` ∈ `oil | lookalike` — not "none", not "oil_spill".
`shape_class` ∈ `linear | blob`. `discharge_class` ∈ `chronic | acute | unknown`.
`confidence` ∈ [0,1]. `contrast_db` **negative** for a dark spot. `elongation` **≥ 1.0**.
`ship_detections` may be `[]` — that is valid and common.
A no-spill case is a FeatureCollection with **zero `oil` features**; look-alikes may still be present.

## 6.4 `particles.json` and `particles_forward.json`
```json
{ "t0": "2021-10-03T01:52:00Z",
  "direction": "backward",
  "timestep_minutes": 15,
  "n_steps": 97,
  "n_particles": 3000,
  "positions": [ [[lon,lat], "... n_particles pairs"], "... n_steps arrays" ] }
```
`positions[0]` is at `t0`; `positions[n_steps−1]` is at `t0 − (n_steps−1)×dt`. With 97 steps at 15 min that is exactly `t0 − 24 h`.
`particles_forward.json` is identical with `"direction": "forward"`. **It is a separate file — never overwrite `particles.json`.**
`t0` must match `meta.detection_time` within 60 s.

## 6.5 `origin.json`
```json
{ "bounds": {"west":..., "south":..., "east":..., "north":...},
  "shape": [120, 120],
  "values": ["... rows*cols floats, row-major from top-left, normalised 0–1"],
  "centroid": [-118.21, 33.71],
  "radius_50_km": 4.2,
  "radius_90_km": 11.8,
  "time_window": ["2021-10-02T08:00:00Z", "2021-10-02T20:00:00Z"],
  "time_window_method": "bounded",
  "ensemble_runs": 50,
  "abstain": false,

  "age_hours": [8, 16],
  "age_method": "combined",
  "age_weathering": "fresh",
  "age_estimators": {"shear": [7,18], "fay": [9,15], "elongation": null},

  "stranded_fraction": 0.03,
  "opendrift_comparison": {"centroid_separation_km": 2.4, "r90_ratio": 1.08}
}
```
**`shape` is `[rows, cols]` and row 0 is NORTH.** `values` length must equal `rows × cols`. Grid normalised to peak 1.0.
`time_window_method` ∈ `bounded | convergence`. **`bounded` means a search bracket, not a measured release time — the frontend must render it differently.**
`age_method` ∈ `shear | fay | elongation | combined | disagreement | none`. `age_weathering` ∈ `fresh | weathered | unknown`.
`abstain: true` forces Stage 3 to return zero suspects. The agreed trigger is `radius_90_km > 40`.
The last four blocks are optional — absence hides a UI row, it does not throw.

## 6.6 `vessels.geojson`
FeatureCollection of LineString tracks:
```json
{ "type": "Feature",
  "geometry": {"type": "LineString", "coordinates": [[lon,lat], ...]},
  "properties": {"mmsi": "367123450", "name": "EXAMPLE STAR",
                 "vessel_type": "tanker", "n_points": 214,
                 "max_gap_minutes": 85} }
```
Plausible-set vessels only. Decimate to ≤500 rendered points, endpoints preserved; `n_points` reports the **undecimated** count.

## 6.7 `suspects.json` *(extended in v3)*
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
                     "type_prior": 1.0},
      "closest_km": 3.1, "closest_time": "2021-10-02T14:20:00Z",
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
  "excluded": [
    { "mmsi": "367999999", "name": "OTHER SHIP", "closest_km": 6.4,
      "reason": "heading away from the origin throughout the window" }
  ],
  "abstained": false,
  "abstain_reason": null
}
```
Funnel counts must **decrease monotonically**. Suspects sorted by descending score. Every suspect `mmsi` must have a matching track in `vessels.geojson` — the validator enforces this, and it is what makes the honesty rule mechanical.
**`components` values are `null` when not applicable.** Dark vessels have `mmsi: null` and never an invented identity.
`abstained: true` requires `suspects` empty.

## 6.8 `verification.json`
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
  "naap_result": {
    "origin_summary": "Origin cloud centred on the pipeline right-of-way, 2.1 km from the reported leak location.",
    "top_suspects": ["<mmsi>"],
    "abstained": false
  },
  "assessment": {
    "verdict": "hit",
    "explanation": "HUMAN-WRITTEN PROSE. Never generated.",
    "what_would_have_helped": "..."
  }
}
```
`verdict` ∈ `hit | partial | miss | not_applicable`. `source_url` must be present and non-empty.

## 6.9 `cases/index.json`
```json
{ "cases": ["case-ennore-2017", "case-huntington-2021", "..."],
  "default": "case-ennore-2017" }
```
Order is presentation order, strongest first. **The frontend never hardcodes a case list.**

---

# PART 7 — OWNERSHIP

| Person | Owns | Primary AI |
|---|---|---|
| **Akshat** | Contracts, case selection, **2-band GEE exports**, `verification.json`, the exporter, the validator, integration (producer side), deck, freeze | Claude ×2, Codex |
| **Soum** | Stage 1 entire: scene classifier, U-Net, classical features, ship detections, chronic/acute | Claude, Codex, Antigravity |
| **Anushka** | Stage 2 entire: integrator, ensemble, origin, **age estimation**, forward drift, coastline, OpenDrift comparison | Claude |
| **Jaiveer** | Stage 3 entire: AIS, scoring, dark vessels, **infrastructure**, traffic prior, repeat offenders, evaluation curve | Claude, Codex |
| **Harshita** | Frontend entire (5 screens, self-guiding UX), **then integration (consumer side)**, demo machine | Antigravity (most accounts), Claude |
| **Urooz** | **Research lead** — naming, then the two age-engine investigations | Gemini Deep Research, Perplexity Pro, ChatGPT |

Urooz's former design work moved to Harshita; keep it minimal, clarity over polish.

---

# PART 8 — WHO WAITS ON WHOM

**Check this before saying you are blocked.** Most of what looks like a dependency is not one.

## 8.1 Blocked on nobody — start now
- Soum: download Parts 1+2, tile cache, ship detector, chronic/acute
- Anushka: age estimators, adaptive pad, negative-longitude test, coastline upgrade
- Jaiveer: **build a US-located fake origin and everything runs** — scorer, parity, traffic prior, evaluation curve
- Harshita: all five screens, self-guiding UX, `BitmapLayer`, union camera
- Urooz: all three research tasks
- Akshat: merge, rulings, validator hardening, `verification.json` research

## 8.2 The real dependencies
```
Akshat: case selected + 2-band export
   ├──▶ Soum: real-scene inference          (needs sar_vv_vh.tif + bounds.json)
   └──▶ Anushka: field fetch                (needs real detection_time)

Soum: detections.geojson  ──▶ Anushka: seeding
Soum: ship_detections     ──▶ Jaiveer: dark-vessel cross-check
Soum: discharge_class     ──▶ Anushka: line-vs-point seeding
                          ──▶ Jaiveer: search strategy

Anushka: origin.json      ──▶ Jaiveer: real scoring
Anushka: abstain bundle   ──▶ Harshita: refusal screen
Soum: zero-oil case       ──▶ Harshita: no-spill screen

everyone ──▶ Akshat: build_case + validate ──▶ Harshita: browser QA ──▶ sign-off
```

## 8.3 Stub-first kills most of these
**Every new field is stubbed with garbage in the right shape before the real logic exists.** Soum's `ship_detections: []` stub unblocks Jaiveer's whole dark-vessel module days before real values arrive. This is the single most effective thing anyone can do for someone else.

## 8.4 The integration gate
```
1 Akshat    export
2 Soum      detections.geojson
3 Anushka   particles + origin + particles_forward
4 Jaiveer   vessels + suspects            (US cases only)
5 Akshat    build_case → validate → PASS
6 Harshita  browser QA → SIGN OFF or REJECT     ← the human gate
7 Akshat    route the rejection to its owner
```
**Two gates, checking different things.** The validator proves a bundle is *schema-valid*. Harshita proves it is *renderable and physically sensible* — it will happily PASS an origin cloud sitting upstream-backwards, or an upside-down grid, or a mirrored polygon (mirror images share a centroid, so a centroid check passes). **A bundle is not integrated until both pass.**

---

# PART 9 — DECISION LOG

Settled. Do not relitigate; if you think one is wrong, raise it with Akshat rather than working around it.

| # | Decision | Reason |
|---|---|---|
| D1 | **Train on Zenodo Parts 1+2, test on Part 3** | Part 3 is the authors' designated test set. Training on it means no clean generalisation estimate, and it is a fifth of the data. |
| D2 | **Scene classifier gates the U-Net** | The dataset authors report U-Net segments erroneously on look-alikes. The gate is what makes cases 6 and 7 work. |
| D3 | **Keep the classical feature layer** | It produces the explainability bars. A CNN cannot. It is also the ablation baseline and the ship detector. |
| D4 | **No CNN before the classical path works** | Classifier first, U-Net second, classical detector supplies polygons meanwhile. |
| D5 | **Our advection model stays in production; OpenDrift is a second opinion** | Ours is validated, the ensemble is the product, two people consume its output. |
| D6 | **No model-switch threshold at 48 h or near shore** | The threshold is indefensible without crossover validation, a particle cannot know its future position, and a hybrid cloud is not a coherent uncertainty statement. |
| D7 | **GSHHG coastline upgrade** | Cheap fix for near shore. Golden Ray and Huntington Beach are both enclosed water. |
| D8 | **Score the origin grid, not the r50 circle** | Real cloud is 4.38:1 aspect with 44.7% of high-probability mass outside r50. |
| D9 | **Applicability gating on gap and slowdown** | 64% of gap hits are docked boats; slowdown is structurally inert for 66% of the fleet. Not-applicable ≠ zero. |
| D10 | **Infrastructure source association** | Two of five cases have a fixed source. Turns Huntington Beach from a miss into a hit. |
| D11 | **`BitmapLayer`, not `HeatmapLayer`** | HeatmapLayer re-smooths in screen pixels and renormalises per viewport — the answer would change as a judge zooms. |
| D12 | **`time_window_method` is in the contract** | Protects a claim we must defend; the frontend needs it to avoid rendering a bracket as a measurement. |
| D13 | **97 steps, not 96** | `positions[n_steps−1] = t0 − (n_steps−1)×dt`; 97×15 min = exactly 24 h, matching what we say on stage. |
| D14 | **2-band float32 GeoTIFF exports, not PNG-only** | VH is Soum's strongest feature and the signal is ~1 dB deep; 8-bit quantisation destroys it. |
| D15 | **Urooz is research lead** | Design work moves to Harshita; her research could outlive the hackathon. |

---

# PART 10 — CORRECTIONS TO EARLIER DOCUMENTS

**`docs/TRAPS.md` #2 is WRONG.** It says HYCOM velocity is cm/s, divide by 100. **GEE lists m/s with scale factor 0.001 — the correct divisor is 1000.** Anushka's plausibility guard caught this on the first real fetch, before a single particle was integrated. Grep the repo for "divide by 100" and kill every instance.

**The ~53% IoU benchmark is from the wrong dataset.** That figure is from the **Krestenitis** 5-class benchmark, which is not openly available. Our dataset's own authors (Trujillo-Acatitla et al., *Mar Pollut Bull* 204:116549, 2024) report **99% classification accuracy and 96% IoU** on their own test set. Both numbers are real; **the gap between them measures look-alike variety, not model quality** — see Part 12.

**`case-000` taught a wrong SHAPE, not just wrong values.** Three people independently reported this. The real origin cloud is a 4.38:1 streak sitting ~98% outside the SAR scene; the fixture is a tidy circle inside it. **Rule: the first time you see real upstream data, re-check every assumption your stub baked in.**

**`validate_case.py` gaps found by the team:** the `Box` pad is so generous the off-scene warning cannot fire; no `area_km2`-versus-polygon check; `origin.bounds` never compared against scene bounds; span check has a fencepost. All Akshat's, all small.

---

# PART 11 — PRIOR ART

Three systems will be named by an informed judge. **Never pretend they don't exist.** Teams that cite prior art and show what they added look like researchers; teams that hide it look ignorant when a judge names it.

**EMSA CleanSeaNet** (Europe, since the 2000s) — satellite slick detection fused with AIS.
> *"Europe has had this for twenty years. India has forward drift prediction through INCOIS and no attribution capability at all. We're closing a national gap, not inventing a paradigm."*

**SkyTruth Cerulean** — global, automated, ResNet34 U-Net slick detection with AIS attribution, scoring on parity, proximity and temporality over an AIS window from 8 h before the image to 6 h after.
> *"Cerulean is the closest thing to us and it's excellent. Four differences. We run the physics backwards to reconstruct an origin rather than matching a coincident track — so we can attribute a slick found days later, which matters because Sentinel-1's revisit gap means we usually see slicks late. We use VV and VH; they use VV alone. We use free public AIS; they use commercial. And we publish exclusions, not just matches."*

We borrow their parity/proximity/temporality framework **and cite them for it.**

Their disclaimer is also our template: they state plainly that SAR alone cannot definitively identify oil slicks and that detections are *potential* slicks. If the leading operational system says that, we say it too.

**INCOIS OOSA** (India) — operational forward drift advisory to the Indian Coast Guard, built on NOAA's GNOME. Our line in 1.2.

**AIS-gap analysis is not our invention** — it is established practice in fisheries enforcement. Reframe honestly: *"applying it to spill attribution, where the gap coincides with a physically-derived origin window, is a much stronger inference than a gap alone."*

---

# PART 12 — THE NUMBERS WE WILL PRESENT

Every number gets its metric and its split named. **Never a single unqualified percentage.**

**Detection (Soum)** — scene classification accuracy, look-alike rejection rate, oil-class IoU, and the classical baseline F1, all on the Part 3 holdout with a scene-level split. Plus the two-benchmark framing:
> *"On the dataset's own benchmark the authors achieve 96% IoU. We achieve X on their designated held-out test set. On the harder Krestenitis look-alike benchmark, published state of the art is around 53%. The gap between those numbers is a measure of how much look-alike variety a dataset contains — that gap is our result, not our excuse."*

**Drift (Anushka)** — integrator exactness (18.0000 vs 18.0 km; round trip 0.0001 km), ensemble spread as **precision not accuracy**, age validation against four documented release times, and OpenDrift agreement.
> *"Across the 50 runs of our uncertainty budget, half the endpoints landed within 8.8 km of the cloud's centre."* **Never** *"accurate to 8.8 km"* — there is no ground truth for origin position.

**Attribution (Jaiveer)** — the injected-offender curve with a stated operating limit:
> *"Across N injected scenarios on real AIS traffic, the responsible vessel ranked top-3 in X% of cases. Performance degrades sharply above roughly 40 vessels in the search window, and above that we abstain."*

**The error budget.** Current field resolution dominates; wind coefficient second; omitted physics third and only past 48 h; integration scheme negligible.
> *"Our uncertainty is a property of the freely available current field, not of our code. A finer regional model would tighten it — that's the roadmap."*

---

# PART 13 — RULES

1. **Stub first.** First commit of anything new writes a schema-valid file of garbage.
2. **Nothing handed over without a pasteable run command** that produces a valid file.
3. **`python scripts/validate_case.py cases/<id>` must PASS** before handover. Fix the producing code, **never** hand-edit a bundle, **never** patch data in the frontend.
4. **45-minute rule** on external services — stop, message Akshat with what you tried and the exact error.
5. **Fresh AI chat per phase or bug.** Log to `docs/updates/<name>.md` after each phase.
6. **Post checkpoint artefacts in the group** as they happen. Three people finished major work the team could not see because images were never posted.
7. **Push daily.** `main` carrying two commits while four branches hold the project is the highest-probability catastrophic risk here.
8. **Freeze twelve hours before 15 Sept 17:00.** `demo` branch, demo machine runs only that, fallback video recorded **before** the freeze, two rehearsals. No exceptions, including Akshat.

---

# PART 14 — OPEN ITEMS

| Item | Owner | Blocks |
|---|---|---|
| Confirm a slick is visible in the Ennore scene | Akshat | the hero case |
| Pick US cases 4 and 5 | Urooz researches → Akshat decides | Jaiveer's AIS download |
| Confirm VH availability per US case | Akshat | Soum's best model |
| Nominate cases 6 and 7 from Zenodo Part 3 | Soum | two demo screens |
| Project name | Urooz | deck, UI header, repo |
| Deployment cost figure for national coverage | Akshat | a Q&A answer |
| `docs/receipts.md` complete | Akshat | the "is this real?" question |

## Deliberately not building
Repeat-offender tracking at scale · polarimetric decomposition · multi-pass age estimation · live API · auth and multi-user · offline mode. **Stating scope decisions confidently reads as engineering judgement; being caught by them reads as gaps.**

---

# PART 15 — GLOSSARY

**SAR** — synthetic aperture radar; oil damps capillary waves so slicks appear dark. **VV / VH** — polarisations; ocean clutter damps mainly VV, real oil damps both, so VH is the discriminator. **Look-alike** — algae, calm wind, rain cells that also appear dark; the core difficulty. **dB** — backscatter in decibels. **Damping ratio** — contrast between slicked and clean sea; tracks thickness, not age. **AIS** — ship transponder broadcasts. **MMSI** — vessel id in AIS; imperfect, do not build identity resolution. **Dark vessel** — visible to radar, absent from AIS. **Chronic** — deliberate discharge underway; long, thin, lane-aligned. **Acute** — accident; radial from a point. **HYCOM** — global ocean currents, 0.08° daily, GEE archive ends 2024-09-05, **scale 0.001 → divide by 1000**. **ERA5** — hourly wind reanalysis; signed u/v components. **GEE** — Google Earth Engine. **3% rule** — surface oil moves at current + ~2.5–3.5% of wind speed. **Ensemble** — 50 perturbed reruns; the spread IS the uncertainty. **Abstention** — designed refusal when confidence is insufficient; a feature. **Parity / proximity / temporality** — Cerulean's vessel-scoring metrics, which we borrow and cite. **Verification** — screen 4; our answer against the official finding.
