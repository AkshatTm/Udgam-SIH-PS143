# Integration log — every seam event, in one place

*Owner: Akshat. Newest entry at the TOP.*

This file records what broke **between** components, so the history of seam failures lives
somewhere other than six people's memories. A component's own bugs go in that person's update
log; this file is only for the joins.

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
