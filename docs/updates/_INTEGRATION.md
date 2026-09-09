# Integration log — every seam event, in one place

*Owner: Akshat. Newest entry at the TOP.*

This file records what broke **between** components, so the history of seam failures lives
somewhere other than six people's memories. A component's own bugs go in that person's update
log; this file is only for the joins.

---

## [2026-09-10] Phase 1 — Huntington Beach confirmed (hero); Golden Ray + Ennore show no SAR slick

**Merge is live.** `origin/main` now carries the 4-branch merge + validator hardening + exporter
(Akshat pushed; soum/jaiveer/anushka branches deleted). `origin/harshita` has 4 newer web
commits (data-driven gallery reading `cases/index.json`, `verify` added to `ALL_ACTS`) —
fast-forwarded into local `main` this session, **not yet pushed** (Akshat: `git push`, or PR).

**New tooling:** `scripts/find_scenes.py` (generalised `check_ennore.py` — any bbox/window, no
hardcoded verdict), `scripts/inspect_db.py` (VV/VH dB point sampler — committed).

### Case 2 — Huntington Beach: CONFIRMED, this is the hero detection case

```
scene       S1A_IW_GRDH_1SDV_20211002T015821_20211002T015850_039934_04B9C9_2BF9
acquired    2021-10-02T01:58:21Z   (S1A ascending, ~2.8 h after the first leak alarm)
bounds      W -118.17  S 33.585  E -118.05  N 33.70    (bbox tight on the slick)
bands       VV + VH + angle        vh_available: true
```

A clean, sharp-edged comma-shaped slick sits dead centre, ~8–10 dB below the surrounding sea in
VV (dense-grid dB sampling; VH baseline near noise floor so VH depression is weak but the
morphology is unambiguous). The anchorage (hundreds of container ships — the 2021 congestion) is
all in frame. Short rewind: oil was only ~3 h old at the pass. `cases/case-huntington-2021/`
holds all four artefacts, **committed** (the `.tif` now travels in git — `.gitignore`
whitelists `cases/*/sar_vv_vh.tif`). The GeoTIFF downloaded directly (8.6 MB, no Drive round
trip): 1112×1271, 2-band float32, bands labelled VV/VH, EPSG:4326, bounds == `bounds.json`, VV
median −20 dB. Two stale `case-huntington-2021_sar_vv_vh` toDrive files sit in Akshat's
Drive/naap_exports/ from earlier `--drive` runs — superseded, safe to delete.

**Draft announcement for the group (do not batch — send this one now):**
> 🚩 Case locked: **Huntington Beach / San Pedro Bay Pipeline, Oct 2021**
> scene `S1A_IW_GRDH_1SDV_20211002T015821_20211002T015850_039934_04B9C9_2BF9`
> detection_time `2021-10-02T01:58:21Z` · bounds `[-118.17, 33.585, -118.05, 33.70]` · VV+VH
> Clear oil slick in SAR. NTSB MIR-24-01: MSC DANIT (IMO 9404649) + "Beijing" dragged anchor
> 25 Jan 2021, pipeline leaked 8 months later → infrastructure + exoneration case.
> Soum: `sar.png` + `bounds.json` up now, 2-band GeoTIFF landing shortly.
> Jaiveer: NOAA AIS for San Pedro Bay, 30 Sep – 3 Oct 2021.
> Anushka: HYCOM/ERA5 for the box, detection_time − 30 h → detection_time.

### Case 1 (Ennore) and Case 3 (Golden Ray): no SAR-visible slick — decision needed

Both are enclosed/sheltered calm water imaged at low wind → dark, low-contrast SAR with no
coherent VV+VH depression (dB sampling confirms the eyeball read on both).
- **Ennore** `..._6D04` (2017-01-29 00:31Z, dawn): filaments near the port mouth, nothing that
  reads as oil vs. a wind shadow or freshwater plume. Akshat is still working this one.
- **Golden Ray** `..._C7D5` (2021-08-08 23:29Z, +9 d — the only S1 pass covering the sound, on a
  12-day ascending repeat): sound + Atlantic uniformly dark, no slick. The wreck + VB-10000
  salvage cluster images clearly at ~(-81.40, 31.13). `cases/case-golden-ray-2021/` has a
  scene-only scaffold with an honest `notes` block.

**The call (Akshat's):** run Golden Ray — and likely Ennore — as **trace + attribute + verify
seeded from the documented known source**, not as detection cases. Golden Ray is a strong
infrastructure/exoneration case even without a SAR detection (origin on the wreck, salvage fleet
excluded as responders — exactly the D10 story). This needs one contract change:
`validate_case.py check_meta` currently errors on `trace` without `detect`. Relax it to allow a
`["trace","attribute","verify"]` bundle whose origin is a known fixed source (add a
`meta.known_origin: [lon,lat]` field, documented). Small change; I did not make it — it's a
frozen-schema decision.

`cases/index.json` → `["case-huntington-2021", "case-golden-ray-2021"]`, default huntington.
`case-000` is not in the gallery index (validator fixture only). `case-ennore-2017` is untracked
and left alone for Akshat — add it to the index when its strategy is settled.

`verification/case-huntington-2021.json` and `verification/case-golden-ray-2021.json` scaffolded:
`official_finding` is researched and citable; `assessment.explanation` is a Phase-4 HUMAN-PROSE
TODO and the files deliberately won't validate until written.

### Cases 4 & 5 — Urooz (draft ask for Akshat to forward)
> Urooz — case-selection research, blocks Jaiveer's AIS download. Find **two** transiting-vessel
> oil discharges in **US waters**, **Oct 2014 – Sep 2024**, ideally different basins:
> 1. SkyTruth Cerulean — map `cerulean.skytruth.org`, or API `api.cerulean.skytruth.org`
>    (OGC-compliant). Filter to US waters; want a clean linear slick attributed to a named
>    vessel with an MMSI.
> 2. Fallbacks: NOAA Incident News archive, USCG investigation reports.
> For each candidate give: date/time, lat-lon, vessel name + MMSI, the Cerulean/report URL.
> Caveat to record: *"Cerulean attributed this slick to vessel X"*, never *"proven responsible"*.
> Then Akshat runs `scripts/find_scenes.py` to confirm Sentinel-1 coverage.

### Cases 6 & 7 — Soum (draft ask)
> Soum — nominate the two detect-only demo scenes from **Zenodo Part III** (DOI
> 10.5281/zenodo.13761290): one **look-alike** (`Lookalike/` folder) where the dark feature is
> genuinely convincing, and one **clean ocean** (`No oil/` folder). Give the folder/scene names.
> Correct NAAP output on both is zero oil features. We'll wrap each as a case bundle.

### Part B rulings — still not broadcast (Phase 0.3). Draft for Akshat to send:
> Rulings, all blocking someone:
> - **B1 BitmapLayer, not HeatmapLayer** for the origin grid — HeatmapLayer renormalises per
>   viewport so the answer changes as a judge zooms (D11). `web/CLAUDE.md` fixed; Harshita's
>   `MapView.tsx` still imports HeatmapLayer — needs the switch.
> - **B2 `time_window_method` is in the contract** — ships as-is; frontend renders a `bounded`
>   bracket differently from a measurement.
> - **B3 Jaiveer scores the origin grid, not the r50 circle** (44.7% of high-prob mass sits
>   outside r50 on the real cloud shape).
> - **B4 Fund the adaptive field-box pad + the loud edge guard** (Gulf Loop covers 156 km/24 h
>   vs a fixed 55 km pad).
> - **B5 Tug/tow are display labels only** — no `type_prior` change on a one-port sample.
> - **B6 Approve Jaiveer's extended `suspects.json`** (source_type, per-component null,
>   dark_vessels, infrastructure) — already in the validator and CONTRACTS pointer.
> - **B7 2-band float32 GeoTIFF exports, committed** — done; `gee_scene.py` produces it.

---

## [2026-09-09] Handoff #2 — four branches merged to main, validator hardened

**The merge.** `origin/{soum, jaiveer, harshita, anushka}` all merged onto `main` (was 2 commits
while four branches held the whole project — the top catastrophic risk in the plan). Order:
soum → jaiveer → harshita clean; anushka had 2 trivial conflicts (`docs/03_ANUSHKA_DRIFT.md`
HYCOM line — took main's v3, which already carries the ÷1000 correction; `docs/SETUP_ANUSHKA.md`
modify/delete — dropped, it's a v1 doc). Landed on a local `integration` branch; **not pushed —
Akshat pushes.**

- **Soum's** `data/labels/features_t25.csv` + `features_with_vh.csv` (~4000 rows each) were
  force-added past `.gitignore` — removed from the merge, they stay local on his machine.
  `classifier.pkl` (5.4 MB) kept — the detector needs it.
- **Anushka** had already fixed the ÷100 → ÷1000 bug repo-wide (TRAPS #2 + 9 other files,
  verified 2026-09-07). Adopted as canonical. Fixed one leftover contradictory sentence in
  `check_gee.py`.
- **Harshita's** `web/` (full Next.js app) merged clean. Her case-000 particle-seeding fix
  (`axis = radians(24)`) is in.

**Validator hardening** (`scripts/validate_case.py`, `test_validator.py` now 12/12):
`check_verification` (Master §6.8), `check_index` (`validate_case.py cases/` validates the index
+ every listed case), `origin.bounds` sanity + off-scene renderability warning, `area_km2` vs
polygon shoelace, extended `suspects.json` (`source_type`, `components` null, `dark_vessels[]`
with `mmsi: null`, `infrastructure[]`), `verify` is a valid act, Box pad 2.0→0.5°, utf-8.

**`build_case.py`:** gathers `verification/<case>.json` → `verification.json`, optional
`particles_forward.json`, notes missing `sar_vv_vh.tif`/`thumb.png`; `--reindex` rewrites
`cases/index.json`. **`gee_scene.py`** rewritten for the 4-artefact 2-band GeoTIFF export
(ruling D14) — still zero GEE contact, first real run is Akshat's.

**Dry run (the "you've never run the pipeline" check):** built a fresh `case-dry` end to end
through all three stubs + `build_case.py` → final PASS, 0 warnings. Found + fixed: the detect
stub and `make_case000` emitted a hardcoded `area_km2` that tripped the new shoelace check —
both now compute it from the polygon.

**State:** `integration` branch = `main` + 4 branches + this work. `validate_case.py cases/`
PASSES. Awaiting Akshat: push; then the two frontend items below.

**Routed to owners:**
- **Harshita:** `web/components/MapView.tsx` implements `HeatmapLayer` for the origin — must
  become `BitmapLayer` (ruling D11). `web/lib/contracts.ts` `ALL_ACTS` needs `"verify"` added
  (screen 4) — `loadCase.ts` currently throws on it.
- **Akshat:** GEE auth → `check_ennore.py` → case selection; Part B broadcast; Phase 4
  `verification.json` prose.

---

## [2026-09-06] Handoff #1 — contracts frozen, case-000 published, all stubs wired

**Published:** `docs/CONTRACTS.md` (frozen) · `cases/case-000/` (fake, full-size: 3000 particles
× 97 steps, 8.4 MB) · a working `--stub` in every stage · `scripts/validate_case.py` +
`scripts/test_validator.py`.

**Validator:** PASS on `case-000`, 0 errors, 0 warnings.

**Seam test:** ran the full chain on a scene-only case (`case-smoke`) with all three stubs,
publishing each stage into the case folder before the next read it. Final assemble validated
PASS. So the architecture is proven wired before any real logic exists — which was the whole
point of today.

**Verified by eye:** drift stub seeded from `det-01` (`shape_class: "linear"`, so along the
principal axis, as the contract requires) and particle 0 travelled 29.2 km over the 24 h rewind
— tens of km per day, which is what an ocean actually does. Origin cloud r50 = 5.5 km,
r90 = 9.9 km, `abstain: false`. Attribution funnel 412 → 63 → 12 → 3, monotonic, with 2
exclusions carrying stated reasons.

**One design point discovered while wiring, worth knowing:** the case folder is the hand-off
medium, so Stage 2 genuinely cannot read Stage 1 until Stage 1's output has been *published*
into `cases/<id>/`. `build_case.py --stage <act>` does that publish step without validating an
incomplete bundle. The stage `out/` directories are working space; the case folder is the
contract.

**State:** `cases/case-000` PASSES with acts `["detect", "trace", "attribute"]`. Everyone can
build against it now.

**Not yet done — the real Phase 0:** the Ennore Sentinel-1 scene is still unverified. No GEE
call has been made from this repo. `scripts/check_ennore.py` and `pipeline/export/gee_scene.py`
are written and syntax-checked but unrun, so both should be assumed to need a round of fixing on
first contact with the API.

**Next seam events expected:**
- **Handoff #2, Mon evening** — Akshat → Soum: real `sar.png` + `bounds.json` for Ennore.
- **Handoff #3, Tue evening** — Soum → repo: real `detections.geojson`; Anushka → repo: real
  `particles.json` + `origin.json`.
- **Handoff #4, Wed morning** — first real wiring. Expected bug classes, in the order they
  usually appear: lon/lat swaps (validator catches by name), timestamps off by hours (compare
  `meta.detection_time` against `particles.t0`), particles seeded off the polygon (plot
  detections and `positions[0]` together — they must overlap), origin cloud on land
  (bounds/indexing bug in `origin.json`).
