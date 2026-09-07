# NAAP — MASTER PLAN
## SIH 2026 · PS 26143 · Oil spill detection, backtracking, and vessel attribution

> **Read this first. Every team member's AI must be given this document plus that member's personal document before any work begins.** This document is the single source of truth for architecture, contracts, timeline, and rules. Personal documents describe each member's tasks. If a personal document conflicts with this one, this one wins. If anything here conflicts with reality, tell Akshat — do not silently improvise.

---

## 1. What we are building

**One sentence:** Naap — satellite forensics that traces an oil spill back to the ship that caused it.

**The pipeline, in three stages:**
1. **Detect** — find oil slicks in Sentinel-1 satellite radar (SAR) imagery, separate them from look-alikes (algae, calm wind, rain cells), and compute geometric properties (area, elongation, edge sharpness).
2. **Trace** — run ocean-current + wind physics *backwards in time* from the slick to reconstruct where and when the oil entered the water. Output is a probability cloud, never a point.
3. **Attribute** — query historical ship-transponder (AIS) data against that origin cloud and time window, and produce a ranked shortlist of suspect vessels plus at least one explicitly excluded vessel.

**The demo is ONE screen:** a map with a scrubbable time slider. The three stages are layers on that map. Dragging the slider backwards makes the slick dissolve into particles drifting back toward their origin. This is the centrepiece. Everything exists to make it work.

**Two deadlines:**
- **Wed 9 Sept — HOD demo.** Acts 1+2 only (Detect + Trace) on the Ennore 2017 case. No AIS needed.
- **Thu 10–Fri 11 Sept — internal hackathon (36h).** Full chain: add the US case with attribution, plus the no-spill case. Freeze 12 hours before judging.

**Honesty rule (binding):** internals are binding — whatever we show on the 11th we defend in December before an NTRO panel. Therefore: no vessel name that isn't in the real AIS file, no detection the detector didn't produce, no accuracy number we didn't measure. Precomputed is fine and we say so openly ("the pipeline runs offline and exports a case bundle; the interface plays it back — that's why it never breaks on venue wifi"). Hardcoded fake results are not fine.

---

## 2. Architecture — how six people link without blocking each other

**Nobody imports anybody's code. Ever.** Each stage is a script that reads files from a case folder and writes files back into it. The frontend reads only static JSON from that folder and never calls Python.

```
/cases/<case_id>/
  meta.json           # case info, which acts are available
  sar.png             # the radar scene rendered as an image
  bounds.json         # geographic bounds of sar.png
  detections.geojson  # Stage 1 output → Stage 2 input
  particles.json      # Stage 2 output (the rewind animation data)
  origin.json         # Stage 2 output → Stage 3 input
  vessels.geojson     # Stage 3 output (AIS tracks)
  suspects.json       # Stage 3 output (ranked suspects, funnel, exclusions)
```

**Why this works:** every stage can be built and tested against hand-written fake files. Nobody ever waits for anybody. Integration = the files being real instead of fake.

**Stub-first rule:** every member's FIRST commit is a script that writes their output file(s) in the correct shape with garbage numbers. This proves the wiring before the logic exists.

---

## 3. Frozen conventions — violating these is how the project dies

1. **Coordinates are `[longitude, latitude]`** in WGS84 (EPSG:4326). Everywhere. GeoJSON order. Never lat-lon.
2. **All times are UTC, ISO 8601, with trailing `Z`** (e.g. `2017-01-29T00:14:00Z`). Timezone-aware datetimes only; naive datetimes are a bug.
3. **Units:** distances km, areas km², speeds m/s, angles degrees clockwise from north.
4. **Precision:** coordinates to 5 decimal places max in JSON (≈1 m; keeps files small).
5. Python 3.11, `venv`, dependencies pinned in `requirements.txt`. Node 20 LTS for the frontend.

---

## 4. The frozen file contracts (full schemas)

### meta.json
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
`acts_available` ∈ subset of `["detect","trace","attribute"]`. The frontend MUST handle a missing act gracefully (greyed-out stage in the rail, short explanation on hover). Ennore has no AIS; the US case has all three.

### bounds.json
```json
{ "west": 80.10, "south": 12.95, "east": 80.70, "north": 13.55,
  "width_px": 1400, "height_px": 1400 }
```
Pixel (0,0) is the **top-left** = (west, north). Pixel→lon/lat is linear interpolation across bounds (acceptable at this scene size).

### detections.geojson  (Stage 1 → Stage 2, and → frontend)
GeoJSON FeatureCollection. Each feature:
```json
{ "type": "Feature",
  "geometry": { "type": "Polygon", "coordinates": [[[lon,lat], ...]] },
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
`classification` ∈ {"oil","lookalike"}. `shape_class` ∈ {"linear","blob"} — tells Stage 2 whether to seed particles along the principal axis (moving ship) or from the centroid (stationary event). A no-spill case = FeatureCollection with zero "oil" features (look-alikes may still be present).

### particles.json  (Stage 2 → frontend)
```json
{ "t0": "2017-01-29T00:14:00Z",
  "direction": "backward",
  "timestep_minutes": 15,
  "n_steps": 97,
  "n_particles": 3000,
  "positions": [ [[lon,lat],[lon,lat], "... n_particles pairs"], "... n_steps arrays" ] }
```
`positions[0]` = particle positions at t0. `positions[n_steps-1]` = positions at t0 − (n_steps−1) × timestep_minutes. With n_steps: 97 and timestep_minutes: 15 that is exactly t0 − 24 h. Duration is always derived as (n_steps−1) × dt — never hardcode the frame count anywhere. ~3000 particles × 97 steps ≈ 5 MB — acceptable. If bigger, decimate steps, never break the schema.

### origin.json  (Stage 2 → Stage 3, and → frontend)
```json
{ "bounds": { "west":..., "south":..., "east":..., "north":... },
  "shape": [120, 120],
  "values": ["... 14400 floats, row-major from top-left, normalised 0–1"],
  "centroid": [80.21, 13.31],
  "radius_50_km": 4.2,
  "radius_90_km": 11.8,
  "time_window": ["2017-01-28T08:00:00Z", "2017-01-28T20:00:00Z"],
  "ensemble_runs": 50,
  "abstain": false }
```
`time_window` doubles as the age statement (we quote the window; we do NOT run a separate age model). `abstain: true` = cloud too diffuse; Stage 3 must then refuse attribution and the frontend shows "attribution not possible at acceptable confidence".

### vessels.geojson  (Stage 3 → frontend)
FeatureCollection of LineString tracks:
```json
{ "type": "Feature",
  "geometry": { "type": "LineString", "coordinates": [[lon,lat], ...] },
  "properties": { "mmsi": "367123450", "name": "EXAMPLE STAR", "vessel_type": "tanker",
                  "n_points": 214, "max_gap_minutes": 85 } }
```

### suspects.json  (Stage 3 → frontend)
```json
{ "funnel": { "in_region": 412, "in_window": 63, "plausible": 12, "scored": 3 },
  "suspects": [
    { "mmsi": "367123450", "name": "EXAMPLE STAR", "vessel_type": "tanker",
      "score": 0.82, "closest_km": 3.1, "closest_time": "2017-01-28T14:20:00Z",
      "heading_consistent": true, "ais_gap_minutes": 85,
      "reasons": ["inside 50% origin radius during window", "85-min transponder gap overlapping window"] } ],
  "excluded": [
    { "mmsi": "367999999", "name": "OTHER SHIP", "closest_km": 6.4,
      "reason": "heading away from origin throughout the window" } ] }
```

---

## 5. Team, ownership, tools

| Person | Owns | Primary AI | Machine notes |
|---|---|---|---|
| **Akshat** | Contracts, case-000, GEE scene export, exporter, integration, deck narrative | Claude Pro ×2, Codex | Integrator — keeps slack deliberately |
| **Soum** | Stage 1 entire: dark-spot detector, label harness (Zenodo Part III), classifier, detections.geojson | Codex/Antigravity now; Claude Pro from the 8th | 4050 GPU; holds the Zenodo data. CNN track is KILLED for this sprint (October work) |
| **Anushka** | Stage 2 entire: fake fields + tests, HYCOM/ERA5 loaders, backward ensemble, particles/origin files | Claude Pro | No GPU needed (none of Stage 2 needs one) |
| **Harshita** | Frontend entire: map, layers, slider, panels, funnel, case switcher | Antigravity (give her most accounts) + Claude Pro | Largest volume of work in the project |
| **Jaiveer** | Stage 3 entire: AIS ingest, tracks, scoring, suspects/vessels files | Claude Pro + Codex | Remote — fully self-contained lane, deadline is the 11th not the 9th |
| **Urooz** | Colour language, Act-1 quiz chips, card styling, deck design | ChatGPT + Antigravity | ~2 h/day; human-judgement tasks |
| Ayushmaan (support) | US case hunt (see §9) | ChatGPT Go | Optional capacity |

**AI working model (everyone):** ChatGPT is the **navigator** — paste your personal doc + relevant Master sections at the start of a chat; it explains the current phase, plans steps, reviews outputs. Claude Code / Antigravity is the **driver** — it writes the code. Fresh chat per bug (long threads burn quota). After each phase, your AI appends to `docs/updates/<yourname>.md`: what was done, files touched, exact run command, open issues — so any other AI can pick up mid-stream.

---

## 6. Timeline

| Day | Akshat | Soum | Anushka | Harshita | Jaiveer | Urooz |
|---|---|---|---|---|---|---|
| **Sun 7*** | Freeze contracts, write case-000, verify Ennore scene in GEE | Download Zenodo Part III (9.9 GB), GEE auth | Fake fields + known-answer tests (no data needed) | Map shell, SAR raster from case-000, layer toggles | NOAA ingest machinery on any month, track rebuild | Colour language |
| **Mon 7** | Export Ennore sar.png + bounds.json; exporter skeleton | Dark-spot detector + label harness → feature CSV | HYCOM + ERA5 loaders, quiver plot sanity check | **Slider + particle animation — must scrub smoothly (day's checkpoint)** | Scoring engine vs fake origin.json | Quiz chips from Part III |
| **Tue 8** | Real exporter, first wiring | Train classifier, run on Ennore scene → real detections.geojson | Backward + ensemble → real particles.json, origin.json | Origin heatmap layer, object card, feature bars | vessels.geojson + suspects.json (fake origin), funnel counts | Card + panel styling |
| **Wed 9** | Integrate morning, rehearse, **HOD demo** | Buffer / fix | Buffer / fix | Polish Acts 1+2 | Swap in real US AIS once case is picked | Visual pass |
| **Thu 10–Fri 11** | US case bundle, no-spill bundle, receipts, **freeze 12 h before judging**, fallback video, rehearse | Run detection on US scene | Rerun drift for US case | Vessels layer, funnel, suspect + exclusion cards, case switcher | Wire scoring to real origin cloud | Deck design |

\* If today is later than Sun 6, compress from the left — never from the Wed 9 rehearsal.

**The four handoffs (the only synchronisation points):**
1. **Sun night** — Akshat publishes frozen contracts + `/cases/case-000/` (fake). Everyone builds against it.
2. **Mon evening** — Akshat → Soum: real `sar.png` + `bounds.json` for Ennore.
3. **Tue evening** — Soum → repo: real `detections.geojson`. Anushka → repo: real `particles.json` + `origin.json`.
4. **Wed morning** — Akshat wires it. Only integration event before the HOD.

**Daily checkpoints:** Sun = case picked, contracts frozen, everyone on fakes · Mon = slider scrubs fake particles smoothly · Tue = every stage writes real files · Wed = Acts 1+2 end-to-end on Ennore.

---

## 7. Code, data, and model sharing

**GitHub — one repo:**
```
naap/
  README.md            # conventions of §3 pasted at the top
  docs/                # this file, personal docs, updates/, receipts.md
  pipeline/
    detect/  drift/  attribute/  export/
  web/                 # Next.js app
  cases/               # committed — bundles are small JSON/PNG
  data/                # GITIGNORED — raw AIS, Zenodo, GEE downloads
  scripts/
```
- One branch per person (`akshat`, `soum`, ...). Push at least daily. PR to `main`; Akshat merges. Because nobody imports anybody, conflicts are near-impossible.
- `.gitignore`: `data/`, `*.tif`, `*.7z`, `*.zip`, `node_modules/`, `venv/`, anything >20 MB.
- **Big files never move between laptops. Outputs move instead.** The Zenodo dataset lives only on Soum's machine; detection runs there and only `detections.geojson` is committed. Raw AIS lives only on Jaiveer's machine; only `vessels.geojson`/`suspects.json` are committed. The trained classifier is a tiny scikit-learn pickle (kilobytes) — commit it to `pipeline/detect/models/` anyway, but nobody else ever needs to run it.
- **Backup:** zip `/cases/` to Google Drive at the end of every day.
- **Demo machine:** decide by Tue (Akshat's or Harshita's laptop). Clone, install, run all cases on it Wed. Create branch `demo` at freeze; the demo machine only ever runs `demo`.

---

## 8. Rules that prevent the known failure modes

1. **Stub first.** First commit = correctly-shaped garbage output.
2. **Nothing is handed over without a run command.** One pasteable line that produces a valid output file.
3. **45-minute rule.** Stuck >45 min on an external service (GEE, downloads, auth)? Stop and message Akshat with: what you tried, exact error text, minimal repro. Push through everything else yourself.
4. **Fresh chat per bug.**
5. **Freeze means freeze.** Nothing new in the last 12 h before judging — including from Akshat. Fix only what dry runs exposed.
6. **No new dependencies after Tue 8** in the pipeline; after the freeze anywhere.
7. **Daily 15-min sync** (fixed time, e.g. 21:30) — each person: done / blocked / next. WhatsApp group for everything else; Jaiveer especially posts an end-of-day update since nobody can see his screen.

---

## 9. Open items and who closes them

| Item | Owner | Deadline |
|---|---|---|
| Verify Sentinel-1 scene over Ennore (~13.25 N, 80.35 E) within 28 Jan–3 Feb 2017 in `COPERNICUS/S1_GRD` | Akshat | Tonight — everything keys off it. Fallback: nearest scene ≤7 days after; state the gap openly |
| Pick the US case (US waters · before Sep 2024 · S1 coverage · documented incident; hunt Gulf of Mexico / US East Coast) | Ayushmaan shortlists → Akshat decides | Mon 7 |
| Faculty request for the Krestenitis 5-class dataset (October work) | Akshat sends, any faculty | This week, non-blocking |
| `docs/receipts.md` — GEE scene IDs, Zenodo DOI 10.5281/zenodo.13761290 (CC-BY: cite it on a slide), NOAA file names, Ennore incident references | Akshat | Before freeze |
| Fallback demo video recorded | Harshita records, Akshat verifies | Before freeze |

## 10. Deliberately NOT building this sprint
CNN segmentation (October — Zenodo Part I is downloaded for it) · dark-vessel radar-vs-AIS cross-check · injected-offender evaluation · chronic-vs-acute discrimination · forward drift · repeat-offender history · live FastAPI run button · OpenDrift validation · auth/multi-user/offline. Saying "that's our October roadmap" on stage is a strength.

## 11. Glossary (so every AI speaks the same language)
**SAR** — synthetic aperture radar; oil flattens waves so slicks appear dark. **Look-alike** — algae/calm-wind/rain patches that also appear dark; the core detection difficulty. **dB** — backscatter in decibels. **AIS** — ship transponder broadcasts (position, speed, course, MMSI id). **MMSI** — vessel identifier in AIS (imperfect; don't over-engineer identity). **HYCOM** — global ocean current model (GEE: `HYCOM/sea_water_velocity`, daily, 0.08°, ends 2024-09-05 in GEE). **ERA5** — wind reanalysis (GEE: `ECMWF/ERA5/HOURLY`). **GEE** — Google Earth Engine, our single data source for SAR + currents + winds. **3% rule** — surface oil moves at current + ~3% of wind speed. **Ensemble** — 50 perturbed reruns; the spread IS our uncertainty. **Abstention** — designed refusal when confidence is insufficient; a feature, not a failure.
