# Akshat — update log

*Newest entry at the TOP. Format: `docs/updates/TEMPLATE.md`.*

---

## [2026-09-10] Phase 1 — Huntington Beach confirmed as hero; Golden Ray + Ennore have no SAR slick

**Done:** GEE auth working (project `quizzer-dev-487316`). Wrote `scripts/find_scenes.py`
(generalised finder) and committed `scripts/inspect_db.py`. Ran the scene search + export +
dB-confirmation loop for the two US spill cases.

- **Huntington Beach — CONFIRMED.** `S1A_..._20211002T015821..._2BF9`, 2021-10-02 01:58:21Z,
  ~3 h after the pipeline started leaking. Clean sharp comma-shaped slick, ~8–10 dB VV
  depression. `cases/case-huntington-2021/` scaffolded (meta v3, bounds, sar.png, thumb);
  2-band `sar_vv_vh.tif` running as a Drive export. This is the hero detection case.
- **Golden Ray — no SAR slick.** `S1A_..._20210808T232953..._C7D5` (+9 d; only S1 pass over the
  sound). Enclosed calm water, nothing visible. Wreck + VB-10000 cluster images clearly.
  Scaffold + honest notes in `cases/case-golden-ray-2021/`.
- **Ennore** (yours) — recap: same problem, dawn low-wind, no clean slick.
- `verification/case-huntington-2021.json` + `case-golden-ray-2021.json` — `official_finding`
  researched (NTSB MIR-24-01, MAR-21/01), `assessment` left as Phase-4 human-prose TODO.
- `cases/index.json` → `[huntington, golden-ray]`, default huntington (case-000 dropped from the
  gallery — it stays a validator fixture only; `case-ennore-2017` left for you to add when you
  finish it — it's untracked and I didn't touch it). `receipts.md` SAR + incident tables filled
  for all three; "Ayushmaan" → "Urooz".

**Files touched:** `scripts/find_scenes.py`, `scripts/inspect_db.py` (new) ·
`pipeline/export/gee_scene.py` (fixed the stale "press RUN" message — `task.start()` is the
trigger) · `cases/case-huntington-2021/*`, `cases/case-golden-ray-2021/*`, `cases/index.json` ·
`verification/case-{huntington,golden-ray}-2021.json` (new) · `docs/receipts.md` ·
`docs/updates/_INTEGRATION.md`

**Run command:**
```bash
python scripts/find_scenes.py --project quizzer-dev-487316 --bbox -118.35 33.50 -117.75 33.85 --start 2021-09-30 --end 2021-10-08 --incident 2021-10-01
python scripts/validate_case.py cases/case-huntington-2021   # FAIL only on detections.geojson (Soum's stage) — correct
```

**Open issues / decisions for you:**
- **Push local `main`** — it's ahead of origin by this session + the `origin/harshita` FF
  (data-driven gallery + `verify` act). `git push origin main`.
- **Trace-without-detect contract change** — Golden Ray (and probably Ennore) run as
  trace+attribute+verify from a known source. `validate_case.py` errors on `trace` without
  `detect`. Needs a small relax + a `meta.known_origin` field. Your call — frozen schema.
- **Move the Huntington GeoTIFF** from Drive/naap_exports/ when the task completes.
- **Send** the three drafted messages in `_INTEGRATION.md` (Huntington announcement now; Urooz
  cases 4/5 ask; Soum cases 6/7 ask) + the Part B broadcast.
- Precise Huntington rupture coordinate still `~4.5 nm offshore` — pin from MIR-24-01 for Phase 4.

**Next:** your push + trace-without-detect ruling → then I can scaffold Golden Ray/Ennore as
trace cases and wire the first real Huntington bundle once Soum + Anushka + Jaiveer deliver.

---

## [2026-09-09] Phase 0 + 3 — merged all four branches, hardened the validator, 2-band exporter

**Done:** Merged `origin/{soum,jaiveer,harshita,anushka}` onto `main` on a local `integration`
branch (was the top catastrophic risk — 2 commits on main, 4 branches holding the project).
soum/jaiveer/harshita clean; anushka 2 trivial conflicts. Dropped Soum's two force-added
label CSVs (stay local); kept `classifier.pkl`. Anushka's ÷100→÷1000 fix (repo-wide, verified
2026-09-07) adopted as canonical; fixed one leftover contradictory sentence.

Hardened `validate_case.py`: `check_verification` (verdict enum, non-empty `source_url`),
`check_index` (`validate_case.py cases/` now validates the index + each listed case),
`origin.bounds` sanity + off-scene renderability warning (Harshita D2), `area_km2` vs polygon
shoelace, extended `suspects.json` (`source_type`, `components` null, `dark_vessels[]` with
`mmsi: null`, `infrastructure[]`), `verify` act, Box pad 2.0→0.5°, utf-8. `test_validator.py`
now 12/12. `build_case.py` gathers `verification.json` + optional trace/scene files, `--reindex`.
`gee_scene.py` rewritten for the 4-artefact 2-band float32 GeoTIFF export (D14). Ran the full
stub chain end to end (first time the pipeline has actually been run) → PASS, 0 warnings.

**Files touched:** `scripts/validate_case.py`, `scripts/test_validator.py`, `scripts/make_case000.py`
· `pipeline/export/{build_case,gee_scene,CLAUDE}.py|md` · `pipeline/detect/run.py` (stub area_km2)
· `pipeline/drift/check_gee.py` · `cases/index.json` (new) · `verification/{TEMPLATE.json,README.md}`
(new) · `docs/{CONTRACTS,receipts,PER_DIRECTORY_CLAUDE}.md` · `web/CLAUDE.md` · `.gitignore`
· `docs/updates/_INTEGRATION.md`

**Run command:**
```bash
python scripts/validate_case.py cases/case-000     # PASS, 0 warnings
python scripts/validate_case.py cases/             # index + all listed cases
python scripts/test_validator.py                   # 12/12 caught and named
python pipeline/export/build_case.py --case case-000
```

**Open issues:**
- **`integration` branch is not pushed.** Fast-forward `main` to it and `git push`, then
  `git push origin --delete` the four feature branches. This is the one thing blocking everyone
  from a single source of truth.
- **Harshita, routed:** `MapView.tsx` uses `HeatmapLayer` for the origin — must be `BitmapLayer`
  (D11). `web/lib/contracts.ts` needs `"verify"` in `ALL_ACTS`/`Act` for screen 4.
- **GEE still untouched.** `check_ennore.py` + `gee_scene.py` unrun. Auth → confirm the Ennore
  slick is visible → `receipts.md` → export. First real run of `gee_scene.py` will need fixing.
- `verification.json` tooling is in (`verification/TEMPLATE.json`, validator, `build_case`) but
  no case has real prose yet — Phase 4.
- Frontend `contracts.ts`/`loadCase.ts` predate the v3 `suspects.json`/`origin.json` fields;
  Harshita renders them for screens 3–4.

**Next:** push `main` → broadcast Part B → GEE auth → Ennore confirm → case selection.

---

## [2026-09-06] Phase 1 — repo skeleton, frozen contracts, case-000, stubs for every stage

**Done:** Turned 22 loose documents into the repo layout the docs describe. Contracts extracted
from Master §4 into `docs/CONTRACTS.md` and marked FROZEN. `case-000` generates and validates
clean (0 warnings). Every stage now has a working `--stub` that writes schema-valid output, so
the full Detect → Trace → Attribute chain runs end to end today, on garbage, before any real
logic exists. Added `scripts/test_validator.py` because the validator had never been proven to
catch anything — it now catches 6/6 deliberately broken bundles and names each fault. Python
3.11.9 + venv, deps pinned. GEE scripts written but NOT yet run (no auth).

**Files touched:** `docs/*` (moved, 22 files) · `CLAUDE.md`, `pipeline/*/CLAUDE.md`,
`web/CLAUDE.md` (new) · `docs/CONTRACTS.md`, `docs/receipts.md` (new) · `.gitignore`,
`requirements.txt`, `README.md` (new/rewritten) · `scripts/make_case000.py` (added `--case-id`,
`--scene-only`) · `scripts/test_validator.py`, `scripts/check_ennore.py` (new) ·
`pipeline/{detect,drift,attribute}/run.py` (new stubs) · `pipeline/export/build_case.py`,
`pipeline/export/gee_scene.py` (new) · `cases/case-000/` (output)

**Run command:**
```bash
python scripts/make_case000.py
python scripts/validate_case.py cases/case-000
python scripts/test_validator.py
```
Expected output: `PASS acts=['detect', 'trace', 'attribute'] (0 warning(s))`, then
`6/6 mutations correctly caught and named`.

Full seam test (all three stubs, publishing through the case folder between stages):
```bash
python scripts/make_case000.py --out cases/case-smoke --case-id case-smoke --scene-only
python pipeline/detect/run.py        --case case-smoke --stub
python pipeline/export/build_case.py --case case-smoke --stage detect
python pipeline/drift/run.py         --case case-smoke --stub
python pipeline/export/build_case.py --case case-smoke --stage trace
python pipeline/attribute/run.py     --case case-smoke --stub
python pipeline/export/build_case.py --case case-smoke
```
Expected output: `PASS`. Verified 2026-09-06.

**Checkpoint artefact:** `cases/case-000/` committed (8.4 MB, 8 files) — the thing everyone
builds against. Validator self-test output above.

**Open issues:**
- **Phase 0 is NOT done.** The Ennore scene has not been verified — needs GEE signup, a
  noncommercial/research project, and `earthengine authenticate`. `scripts/check_ennore.py` is
  written and syntax-checked but has never made a real API call. This is the go/no-go the whole
  plan keys off, and it is the 45-minute-rule risk item. **Do it first tomorrow morning.**
- `pipeline/export/gee_scene.py` likewise unrun. The `getThumbURL` path and the pixel-dimension
  arithmetic are untested against the real API; expect at least one round of fixing.
- **Contract addition, announced not yet acknowledged:** `bounds.json` now carries optional
  `db_min` / `db_max` (the dB clamp). Reason in `docs/CONTRACTS.md` §3 and `docs/TRAPS.md` #7 —
  Soum reads the 8-bit PNG back to decibels and must use the same clamp. Additive only;
  consumers default to [-25, 0] when absent. Needs broadcasting to the group.
- Environment deviates from the frozen convention in one place: **Node 24** is installed, not
  Node 20 LTS. Harshita's lane only. Worth a decision before she scaffolds `web/`.
- `build_case.py --stage <act>` was added mid-session and is not in any personal doc: the case
  folder is the hand-off medium, so Stage 2 cannot read Stage 1 until Stage 1 is published into
  the case folder. Mention it at the sync so nobody rediscovers it.

**Next:** GEE auth → `check_ennore.py` → record the scene id in `docs/receipts.md` → export
`sar.png` + `bounds.json` for Ennore and hand to Soum (Handoff #2, due Mon evening).
