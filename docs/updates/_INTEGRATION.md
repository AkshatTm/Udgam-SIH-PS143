# Integration log — every seam event, in one place

*Owner: Akshat. Newest entry at the TOP.*

This file records what broke **between** components, so the history of seam failures lives
somewhere other than six people's memories. A component's own bugs go in that person's update
log; this file is only for the joins.

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
