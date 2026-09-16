# Anushka — update log  ·  Stage 2 (drift)

*Newest entry at the TOP. This file is the memory between chats: close a chat, switch tools,
sleep, hand over to someone else — read the top entry and you know exactly where things stand.*

**To resume:** *"Read docs/00_MASTER_PLAN.md §3–4, docs/03_ANUSHKA_DRIFT.md and
docs/updates/anushka.md. Read the top entry and tell me where I left off."*

---

## Phase status

| Phase | What | State |
|---|---|---|
| 0 | Setup: repo, branch `anushka`, venv, packages, GEE signup | ✅ done (GEE auth unverified — see open issues) |
| 1 | Fake fields + RK2 stepper + four known-answer tests | ✅ **code done — 4/4 green.** 3 human steps left, see "Phase 1 — what remains" |
| 2 | Real HYCOM + ERA5 loaders, quiver plot | ✅ **done 2026-09-07.** Field cached, quiver posted, test-4 guards green on real fields |
| 3 | Backward + 50-run ensemble → real `particles.json` / `origin.json` | ✅ **done 2026-09-07.** Real files written, validator PASS 0 warnings, tests 5/5. Rerun on Soumirya's real detections when they land |
| 4 | Coastline upgrade (GSHHG) + stranding, decision D7 | ✅ **done 2026-09-13.** Suite 8/8, 54/54. New dependency needs Akshat's confirmation (D7) |

---

## [2026-09-16] Final day — Akshat's rulings applied, P2 Version A (forward drift)

**Done:** Applied Akshat's 16 Sept rulings to the figures. Built forward drift Version A: the published 50-member ensemble run forward
24 h with stranding. Output is `F2.9_both_directions.png` (backward and forward r50/r90 on one axis, t0 at centre) and
`docs/evaluation/stage2-forward.md`. No schema change and no bundle written. **Result: 0% stranded and no landfall within 24 h on all six cases**
(tracker verified against a synthetic coast). Forward +24 h r90: Jacksonville 35.5 km … Gulf of Alaska 3.1 km.

**Rulings applied:**
- **`forward_impact.json` is DEFERRED to post-demo, not refused.** The `forward_<case>.json` numbers drop straight in.
- **F2.4 is a single-run trajectory comparison, not ensemble agreement.** `r90_ratio` is not computable and no bundle carries `opendrift_comparison`.
  Removed "we run both and render both clouds" from the caption. The D5 amendment and §6.5 annotation are Akshat's.
- **F2.6 now quotes Jacksonville mass only:** 3.67:1, 20.1% of high-probability mass outside r50. The cell-count stat is removed.
- **F2.7 now frames age as designed capability, not triggered on these scenes** (D19 precedent).
- **F2.3 caption:** the roadmap claim is scoped. A finer current field tightens Jacksonville (91%) and Mumbai (50%). On Farallones, Jamnagar and Huntington,
  slick size dominates. Also added the cross-check: Alaska wind 53% of variance agrees with wind_share 0.73.

**Checks Akshat asked for:**
- **Age fields:** every spill bundle has `age_method: "none"`, but `age_hours` is **present as `null`**, not absent. The validator accepts null.
  Making it absent means changing `run.py`'s `write_origin` and republishing six bundles. Not done on freeze day. **Needs Akshat's call.**
  Harshita still needs to confirm the Trace screen hides the age row on null.
- **Aspect 3.67 vs 3.68:** I cannot reproduce 3.68 from the shipped bundle. Endpoint PCA gives 3.665, grid-weighted PCA 3.661, and per-point cos(lat) 3.665–3.669.
  3.68 likely comes from an earlier run or a different projection. Suggest D36/§6.7 quote 3.67.
- **case-000 `wind_share`:** already **absent** from `cases/case-000/origin.json`, so no `make_case000.py` change is needed. The only 23% is the
  prose line in `docs/STAGE2_NUMBERS.md` §8.7 (a real-field diagnostic run). Annotated there as not in any bundle and not a Stage 1 metric.

**Files touched:** `pipeline/drift/eval_forward.py` (new) · `pipeline/drift/plot_evidence.py` (F2.3/4/6/7 captions, new F2.9) ·
`docs/evaluation/figures/stage2/F2.*.png` · `docs/evaluation/figures/stage2/data/forward_<case>.json` ×6 · `docs/evaluation/stage2-forward.md` (new) ·
`docs/STAGE2_NUMBERS.md` (§8.7 annotation)

**Run command:**
```bash
for c in case-jacksonville-2024 case-farallones-2023 case-jamnagar-2024 case-mumbai-2023 case-gulf-alaska-2023 case-huntington-2021; do python pipeline/drift/eval_forward.py --case $c; done
python pipeline/drift/plot_evidence.py
```

**Open issues:**
- Forward horizon is 24 h (field cache ends ~24.6–26 h past t0). +48/+72 h need a wider fetch, which is post-demo.
- Assets at risk are not produced (no cited asset layer fetched).
- `meta.notes` is not written (bundle is produced by `build_case.py`, Akshat's lane).
- **Three Pythons are now confirmed:** Soum 3.13, repo pin 3.11, these runs 3.10. This feeds the Frozen Convention 8 ruling.

---

## [2026-09-16] Final day P1 — Stage 2 evidence set (F2.1–F2.8)

**Done:** Eight 200 dpi figures in `docs/evaluation/figures/stage2/`, each captioned with its source path and n. Built from the shipped bundles and measured data only; no bundle was written. F2.1 needed per-hour radii that the bundles do not store, so `eval_growth.py` re-runs the exact published ensemble (seed 143, 3000 × 50) with hourly frames kept, into a scratch dir. It refuses unless its 24 h r50/r90 match `origin.json`, and **all six reproduce** (e.g. Jacksonville 13.099 / 31.113 vs shipped 13.1 / 31.11). Drift tests re-run: **11/11 suites, 76/76 assertions**.

**Files touched:** `pipeline/drift/eval_growth.py` (new) · `pipeline/drift/plot_evidence.py` (new) · `docs/evaluation/figures/stage2/F2.1…F2.8_*.png` (output) · `docs/evaluation/figures/stage2/data/growth_<case>.json` ×6, `drift_tests_2026-09-16.txt` (evidence)

**Run command:**
```bash
for c in case-jacksonville-2024 case-farallones-2023 case-jamnagar-2024 case-mumbai-2023 case-gulf-alaska-2023 case-huntington-2021; do python pipeline/drift/eval_growth.py --case $c; done
python pipeline/drift/plot_evidence.py
```

**Where the brief and the data disagreed. The figures follow the data:**
1. **F2.2:** brief says 5 suites / 20 assertions. The suite is now 11 / 76.
2. **F2.3:** no measured weights existed, so the budget is now **measured**: pooled 24 h endpoint variance split into the current-scale term, the wind-coefficient term (linear fit over the 50 runs) and within-run spread. Current leads between runs on 5 of 6 cases (Jacksonville 91%). **Gulf of Alaska inverts** (wind 53%). Within-run spread (mostly slick length) is the largest block on Farallones, Jamnagar and Huntington. Omitted physics is not modelled, so it is stated in text, not drawn as a bar.
3. **F2.4:** `origin.json` has **no `opendrift_comparison` block** and `out/opendrift_*.json` are not on disk. The plot uses the §8.4 table in `docs/STAGE2_NUMBERS.md` (centroid separation vs travel, with r50 for scale). **`r90_ratio` does not exist** (the comparison was single-run) and is not plotted.
4. **F2.6:** 10.65 km / 3.68:1 are Jacksonville's, and they check out: measured **10.6 km, 3.67:1**. But **4.38:1 / 44.7% are case-000 (D8)**, not Jacksonville. On Jacksonville, **23.7%** of high-probability cells (≥0.5 of peak) lie outside r50, carrying **20.1%** of their mass. The caption says so.
5. **F2.7:** every estimator is `null` on all six cases (chronic/unknown gate, no independent volume, Huntington shear-dominated). **There is no N = 1**, so the figure shows 18 grey slots with reasons.
6. **F2.1:** growth is **not monotonic everywhere**. Farallones and Jamnagar are nearly flat, and Huntington dips after ~19 h. The caption says this rather than "widens every hour".

**Open issues:**
- `eval_growth.py` and the tests were run in a Linux VM (Python 3.10) with `scipy` and `global-land-mask` installed there; not yet re-run in the Windows venv.
- P2 (forward drift) not started; Akshat's ruling on `forward_impact.json` still to be asked.
- Jacksonville travel is quoted as 149 km (§8.9, merged ribbon) in F2.1 and 140.2 km (§8.4, OpenDrift run) in F2.4. Both are correct for their own run.

---

## [2026-09-13 00:20] Phase 4 — GSHHG coastline + stranding (decision D7)

**Done:** Six things landed together.

New `pipeline/drift/coastline.py` wraps GSHHG via `global-land-mask` at ~1 km, replacing a land
mask that was derived from the velocity field's own validity at 9 km. The (lat, lon) ->
[lon, lat] conversion happens in exactly one function.

`step.integrate_stranding()`: particles that reach land freeze at their LAST WET position and
are flagged. Sticky — a stranded particle stays stranded. Added as a separate function so
`integrate()`'s return signature does not change.

`ensemble.run_once` / `run_ensemble` carry an optional `is_land` mask without changing their
return arity; per-member stranded fraction recorded in `members[]`.

`origin.json` gains `stranded_fraction` (Phase 4.3). OMITTED entirely when no real coastline is
available, because a false `0.0` would be a claim we cannot make.

`run.py` prints which mask was used and the stranded fraction, and warns loudly above 10%.

New suite 8 in `pipeline/drift/coast_tests.py`, six assertions: shoreline loaded, known
land/ocean plus all seven case centres in water, the lat/lon swap, a particle driven ashore
stopping at its last wet position, a particle seeded on land never moving, and mid-ocean
particles stranding nobody. Suite now **8/8, 54/54**.

Phase 4.4 CHECK PASSED on case-000 at 3000 particles x 50 runs: origin moved 0.53 km
(centroid 80.62097, 13.69967 -> 80.6188, 13.6954), r90 17.30 -> 17.6 km, r50 8.78 -> 8.8 km,
1.31% of ensemble endpoints stranded (1.13% of the control run). Seed is fixed at 143, so the
move is attributable to stranding rather than sampling. Immaterial against r50 8.8 km.

Edge guard independently reported 11.6 km of clearance, matching the figure in the brief.

New dependency: `global-land-mask==1.0.0`, pinned in `requirements.txt` with its justification.

**Files touched:** `pipeline/drift/coastline.py` (new) · `pipeline/drift/coast_tests.py` (new) ·
`pipeline/drift/step.py` (modified) · `pipeline/drift/ensemble.py` (modified) ·
`pipeline/drift/run.py` (modified) · `pipeline/drift/tests.py` (modified) ·
`requirements.txt` (modified)

**Run command:**
```bash
python pipeline/drift/tests.py
```
Expected output: `8/8 tests passed (54/54 individual assertions)`.

**Checkpoint artefact:** `pipeline/drift/out/heatmap_case-000.png` via
`python pipeline/drift/plot_heatmap.py --case case-000`.

**Open issues:**
- `global-land-mask==1.0.0` lands after `requirements.txt`'s stated no-new-dependencies date and
  needs Akshat's confirmation under D7 (see `HANDOFF_ANUSHKA_ASK.md`) — Phase 4 comes back out
  if it's not confirmed.
- Phase 2 and the Phase 3.3 abstain bundle are the only remaining unblocked work.

---

## [2026-09-13 00:00] Phase 3 — adaptive field-box pad, loud edge guard, negative-longitude/high-latitude tests, acute gate on C3.1

**Done:** Four things landed together.

Phase 3.1 (adaptive pad): `check_gee.py` gains `required_pad_km` / `padded_bbox` /
`pad_degrees`. The pad is sized from rewind hours x a worst-case speed (with a 55 km floor),
and converted to degrees at the box's **poleward edge**, not mid-latitude — converting at
mid-latitude would have under-sized the Alaska pad by the cos(lat) ratio (1.70x at 59.56 N vs
30.38 N). `fetch_fields.py` gains `--vmax-ms`, `--pad-km`, `--rewind-hours`, and a post-fetch
p99 check that names the exact refetch command when the downloaded box turns out too small.

Phase 3.1 (loud guard): `step.assert_inside_field_box` + `edge_distance_km` +
`FieldBoxEdge`, wired into `run.py` **before any file is written**, so a cloud whose particles
reached the box edge cannot ship as a bundle. `case-000` clears the guard by ~14.8 km (limit
10 km).

Phase 3.2 + high latitude: new `pipeline/drift/geo_tests.py`, suite 7, ten assertions.
Covers negative longitude, the antimeridian wrap, `wrap_lon` against a 0-360 leak, the
cos(lat) longitude delta at 59.56 N, the 1.70x ratio against Jacksonville, a high-latitude
round trip, and all seven library positions checked from scratch.

`age.py`: C3.1 is now gated on `discharge_class == "acute"`, the same gate C3.3 already had,
because on a chronic slick the major axis reflects the vessel's track, not shear. New
assertion 6r.

Suite is now **7/7, 48/48**.

**Files touched:** `pipeline/drift/check_gee.py` (modified) · `pipeline/drift/fetch_fields.py`
(modified) · `pipeline/drift/step.py` (modified) · `pipeline/drift/run.py` (modified) ·
`pipeline/drift/geo_tests.py` (new) · `pipeline/drift/tests.py` (modified) ·
`pipeline/drift/age.py` (modified) · `pipeline/drift/age_tests.py` (modified)

**Run command:**
```bash
python pipeline/drift/tests.py
```
Expected output: `7/7 tests passed (48/48 individual assertions)`.

**Checkpoint artefact:** `python pipeline\drift\run.py --case case-000 --real --particles 600
--runs 6` prints `edge guard  closest particle sits 14.8 km inside the field box (limit 10
km)`. Pad check: `required_pad_km(24, 2.0)` = 224.64 km, `padded_bbox(...)` =
`[-146.77, 57.48, -138.65, 61.63]` for the Gulf of Alaska box.

**Open issues:**
- Jacksonville needs `--vmax-ms 2.0` at fetch time.
- Three Part C departures still awaiting Akshat's ratification
  (`docs/STAGE2_AGE_DECISION_BRIEF.md`).

**Next:** get Akshat's ratification on the Part C departures; rerun fetch for Jacksonville
with the correct `--vmax-ms`.

---

## [2026-09-12 00:00] Phase 1 — age estimation (Part C)

**Done:** Built `pipeline/drift/age.py`, implementing Part C of the brief: C3.1 shear
dispersion, C3.2 Fay spreading, C3.3 elongation-under-shear, C3.4 weathering flag, and the C4
combine rules. It patches `age_hours`, `age_method`, `age_weathering` and `age_estimators` into
`out/origin.json`, and writes full diagnostics to `out/age_<case>.json`, which stays out of the
case bundle. `pipeline/drift/age_tests.py` adds suite 6 (17 assertions), wired into
`tests.py`. Suite is now 6/6, 37/37.

Three departures from the brief's Part C are documented in `docs/STAGE2_AGE_DECISION_BRIEF.md`
and await Akshat's ratification:
- (a) C3.1 matches major-axis length, not area, because a 2D incompressible flow preserves a
  cloud's area.
- (b) C3.3 uses the exact patch-aspect inversion `St = sqrt(a + 1/a - 2)` instead of
  `sqrt(1 + (St)^2)`, which is about 3.2x shorter.
- (c) C3.2 requires an independently reported release volume and returns a regime verdict
  rather than an age at SAR scale.

Also added a field-time-coverage guard that drops candidate ages outside the cached field's
span, because `fetch_fields.py`'s 30 h window yields only ~24 h of daily HYCOM coverage.

**Files touched:** `pipeline/drift/age.py` (new) · `pipeline/drift/age_tests.py` (new) ·
`pipeline/drift/tests.py` (modified, wires in suite 6) · `docs/STAGE2_AGE_DECISION_BRIEF.md`
(new) · `docs/STAGE2_COMPONENT_REPORT.md` (new)

**Run command:**
```bash
python pipeline/drift/age.py --case <id> --real [--volume-m3 N]
```
Expected output: patched `out/origin.json` with `age_hours`/`age_method`/`age_weathering`/
`age_estimators`, plus `out/age_<case>.json` diagnostics.

**Checkpoint artefact:** `python pipeline\drift\tests.py` → `6/6 tests passed (37/37
individual assertions)`.

**Open issues:**
- 1.6 validation not run yet (blind protocol — bands first).
- `age_hours` emits `null` when no estimator fires, which may not satisfy the validator's new
  `[low, high]` check.
- `combine_bands` can return a degenerate band when two estimators touch at a single point.

**Next:** run 1.6 validation against `scripts/validate_case.py`, then get Akshat's ratification
on the three Part C departures above.

---

## [2026-09-07 23:10] Silent-fallback bug: a case that does not exist got another case's ocean  🐛→✅

**Found by running `--case case-gulf-2019` before that bundle existed.** Both `check_gee.py`
and `fetch_fields.py` fell back to the hardcoded Ennore defaults, downloaded **January 2017
Bay of Bengal** water, and cached it as `data/fields/case-gulf-2019.npz`. Everything printed
PASS. The field statistics looked like a real ocean, because they were one.

**Why this was the dangerous kind of wrong.** Nothing in the cache revealed the swap:
`fetch_fields.py` writes `case_id=<what you typed>`, so the file said "case-gulf-2019" inside
as well as outside. `run.py --real` loads whatever `data/fields/<case>.npz` holds. Had the
real Gulf bundle landed a day later, the cache would already have been there, `--force` would
never have been passed, and Stage 2 would have rewound a Gulf of Mexico slick through
Coromandel coast currents from seven years earlier — and handed Stage 3 a perfectly plausible
origin cloud. No crash, no NaN, no warning. This is the exact failure mode this component
exists to defend against, one directory up from the physics.

### Fixed three ways

| Fix | File | Behaviour now |
|---|---|---|
| A named case must exist | `check_gee.py` (`load_case_window`, used by both scripts) | Missing `meta.json` is a hard stop naming the directory. The Ennore defaults survive **only** for `check_gee.py` with no `--case`, which is an auth smoke test, not a case run |
| The cache must prove it belongs to the case | `fields.py` (`load_case_field`) | Re-derives box and time from `meta.json` + `bounds.json` and refuses a cache whose `t0` differs by >60 s, or whose bbox does not contain the scene. Also catches a **stale** cache after a scene, bounds or detection_time change |
| Fail before the network, not after | `fetch_fields.py` | Case resolved before `import ee` / `ee.Initialize()`, so a typo costs a second instead of an auth round trip |

### Verified by forging bad caches, not by reasoning about them

```
named case with no bundle      -> stops, names the directory, refuses to substitute
cache dated 2019 vs case 2017  -> "This cache is a different ocean than the case needs"
cache boxed on the Gulf        -> "covers [W -91.0 ...] which does not contain case-000's scene"
wider box, same place and time -> correctly ALLOWED (a superset is a valid cache)
```

Tests still 5/5, 20/20. `--real` on case-000 still reproduces
`origin (80.6210, 13.6997) r50=8.8 r90=17.3` exactly — the guards add no drift.

### Also fixed, same run

`check_gee.py`'s HYCOM sample-value message ended with a leftover **"Divide by 100 in the
loader, once."** immediately after the corrected sentence telling you to divide by 1000. The
2026-09-07 unit correction missed the trailing line. It printed on every preflight PASS, and
it is the single sentence most likely to be copied by someone in a hurry. Removed.

### Left for a human

`data/fields/_to_delete/case-gulf-2019.npz` — the bogus cache, moved aside rather than
deleted (the workspace cannot delete inside the repo). `data/` is gitignored, so it is
invisible to git; delete the folder when convenient.

---

## [2026-09-07 22:20] Phase 3 — backward ensemble, origin cloud, the handoff files  ✅

**Done:** Stage 2 now produces the two files the rest of the project consumes, from the real
Ennore ocean, with real uncertainty. `--real` drives the integrator off `load_case_field()`;
the 50-run ensemble lives in a new `ensemble.py`; the origin grid is a true 2D histogram of
150,000 endpoints instead of the stub's painted gaussian.

**The result** (case-000 detections, real HYCOM + ERA5 fields):

```
origin      (80.6210, 13.6997)   r50 8.8 km   r90 17.3 km   abstain=False
            49 km from the slick on a bearing of 025 deg -- NORTH-EAST, i.e. UPSTREAM of a
            south-running East India Coastal Current, which is the only direction a 24 h
            rewind can honestly go
control     median displacement 48.4 km (40.1-55.8) over exactly 24.00 h
ensemble    50 runs x 3000 particles = 150,000 endpoints
window      2017-01-28T00:14Z -> 2017-01-28T16:14Z   method=bounded
validator   PASS   acts=['detect','trace','attribute']   0 warnings
tests       5/5, 20/20 assertions
```

The one-run warning Phase 1 shipped with (`only 1 ensemble runs; uncertainty will look fake`)
is gone. This is the first Stage 2 output with **zero** validator warnings.

### Files touched

| File | Change |
|---|---|
| `pipeline/drift/ensemble.py` | **new** — `PerturbedField`, `run_once`, `run_ensemble`, `radii_km`, `origin_grid`, `time_window`, stratified parameter draws |
| `pipeline/drift/run.py` | `--real` (HYCOM+ERA5) alongside `--fake`; control run + ensemble; `write_origin` rewritten around the real histogram; `--runs`, `--out` |
| `pipeline/drift/tests.py` | **+test 5** (8 assertions): ensemble spread, no centroid bias, grid orientation, normalisation, both time-window branches |
| `pipeline/drift/plot_heatmap.py` | **new** — the Phase 3 checkpoint picture |
| `pipeline/drift/out/` | `particles.json` (6.34 MB), `origin.json` (14,400 floats), `ensemble_case-000.npz`, `heatmap_case-000.png` |

### Run command (this is the handoff)

```bash
venv\Scripts\activate
python pipeline/drift/run.py --case case-000 --real --particles 3000 --runs 50
python pipeline/drift/plot_heatmap.py --case case-000
python pipeline/drift/tests.py
# then copy out/particles.json + out/origin.json into cases/<case>/ and:
python scripts/validate_case.py cases/<case>
```
Runs in about 22 s for the full 50 x 3000. Deterministic: `--seed 143` reproduces these
numbers exactly.

### Three decisions worth defending

- **`particles.json` is ONE control run, not the ensemble.** The slider needs trajectories a
  human can follow; 50 overlaid members look like fog. The ensemble is the *answer*
  (`origin.json`), the control run is the *animation*. Showing the ensemble as the animation
  would be unreadable; showing the control run as the answer would claim a precision we do
  not have.
- **The ensemble parameters are stratified, not drawn independently.** 50 independent draws
  from N(1, 0.15) land with a sample mean scattered by ~0.02, and on the first run the mean
  current came out 3% fast — which pushed the entire origin cloud 1.4 km further from the
  slick than the physics warranted. That is a sampling artefact reported as physics.
  Stratifying (one draw per equal-probability slice, `statistics.NormalDist`, no new
  dependency) gives realised mean 0.9982 / sd 0.1488 against a claimed 1.00 / 0.15, and the
  pooled ensemble centroid now sits 80 m from the control endpoint instead of 1.4 km.
- **The grid is smoothed, and the bandwidth is derived, not eyeballed.** A raw histogram of a
  LINEAR slick is 50 near-parallel ridges — each member translates the seed line almost
  rigidly — which would tell Stage 3 to prefer stripes that mean nothing. The KDE bandwidth
  is fixed at a tenth of r50, tied to the cloud's own scale. It changes the picture only:
  every reported number (centroid, r50, r90) is measured from the raw endpoints.

### Open issues

1. **`time_window` is the bounded window, not a convergence measurement — and that is the
   honest answer here.** The refined method (10th-90th percentile of per-run convergence
   times) is implemented and tested, but it only fires when the rewound cloud actually
   tightens. Over Ennore it does not: HYCOM on GEE is daily, so across 24 h the field is a
   linear blend of two snapshots, the flow is smooth, and the cloud translates rather than
   converging. Two guards refuse to dress that up — the median member must tighten to <= 90%
   of its starting spread, and the dip must be interior. Both fail, so we ship
   `[t0-24h, t0-8h]` and say so. **This is the cut-order outcome the brief anticipated, not a
   shortfall.** If a case with a real eddy comes along the measured window switches on by
   itself; test 5g proves the branch works.
2. **`origin.json` carries one field beyond the frozen schema: `time_window_method`**
   ("bounded" or "convergence"). `03_ANUSHKA_DRIFT.md` asks for the window to be marked, and
   there was nowhere in the schema to mark it. Additive only — the validator passes and a
   frontend that ignores it loses nothing. **Akshat: reject it or bless it, but do not let it
   ship unnoticed.** It matters because it is the difference between "we measured when the
   oil went in" and "we bounded when the oil went in".
3. **case-000's `area_km2` disagrees with its own polygon.** The `det-01` ring spans about
   21 km; `area_km2: 12.4` with `elongation: 8.2` implies a slick about 10 km long. The
   seeder follows the *geometry* (correct — the polygon is the measurement), so it seeds a
   21 km line. Harmless in a synthetic bundle, but if Soumirya's real detector ever writes
   `area_km2` from a different mask than the polygon it exports, Stage 2 silently seeds the
   wrong length of slick. Worth one assertion in Stage 1.
4. **~~Not yet run in the Windows venv~~ — RESOLVED 2026-09-07 22:35.** Re-run inside
   `venv\Scripts\activate` on Python 3.11: **5/5, 20/20**, and every number identical to the
   Linux/3.10 run to the last decimal — including test 5's ensemble figures (control r90 2.36
   → ensemble 3.35 km, centroid offset 0.16 km, r50 1.81 km). The `--real` run reproduces
   `origin (80.6210, 13.6997)  r50=8.8  r90=17.3  abstain=False` exactly. Same outcome as
   Phase 1's cross-check. Nothing here uses scipy — the gaussian blur is written out in NumPy
   on purpose — so numpy + matplotlib is the whole requirement.

   *Note for whoever runs this next:* `tests.py` lives in `pipeline/drift/`, so from the repo
   root it is `python pipeline\drift\tests.py`, not `python tests.py`.
5. **Not yet committed or pushed.** Branch `anushka` is still at `8b2ee64` (Phase 2). Phase 1's
   open items #2 (post the checkpoint) and #3 (push the branch) are still open and still
   blocking Harshita.

**Checkpoint image:** `pipeline/drift/out/heatmap_case-000.png` — left: the slick, the control
run rewinding, and the cloud it lands in, with the coast for scale. Right: `origin.json`
exactly as stored, 120x120 row-0-is-north, with the 50% and 90% circles. Post in group.

**Next:** Phase 4. When Soumirya's real `detections.geojson` for Ennore lands, `fetch_fields.py
--case <real-case>` then the same run command — nothing in the drift code needs to change,
which is the whole point of the seam. Then the US case: re-run `check_gee.py` first, because
HYCOM's GEE archive ends 2024-09-05 and the Gulf sits at negative longitude.

---

## [2026-09-07 21:30] Phase 2 — real fields  ✅

**Done:** `get_uv` / `get_wind` now return real HYCOM current and ERA5 wind for Ennore.
`step.py`, `tests.py` and `run.py` were not touched, which was the design goal — the field
source is swapped underneath them.

### ⚠️ Unit correction that affects the whole team

`docs/TRAPS.md` #2 (and five other docs) said **HYCOM is cm/s → divide by 100**. That is wrong
for Earth Engine. The GEE catalog band table gives `velocity_u_0` / `velocity_v_0` as
**units m/s with scale factor 0.001**, so `getRegion` returns millimetres per second:
**divide by 1000.** The ÷100 figure describes the raw HYCOM NetCDF distribution.

Dividing by 100 gave a median current of **4.8 m/s** over the Ennore box (max 11.0 m/s) — a
physically impossible ocean. Dividing by 1000 gives **median 0.48 m/s, max 1.10 m/s**, flowing
south along the Coromandel coast, which is the January East India Coastal Current under the NE
monsoon. Verified against the catalog, not just by plausibility.

**Test 4 caught this on the first fetch**, exactly as designed — the p99 guard fired before any
particle was integrated. This is the receipt for why the tests were written before the data.

Corrected in: `docs/TRAPS.md`, `docs/03_ANUSHKA_DRIFT.md`, `docs/SETUP_ANUSHKA.md`,
`docs/PER_DIRECTORY_CLAUDE.md`, `docs/PROMPTING_PLAYBOOK.md`, `docs/receipts.md`, `CLAUDE.md`,
`pipeline/drift/CLAUDE.md`. **Akshat: `receipts.md` is judge-facing — this was in it.**

### Files touched

| File | Change |
|---|---|
| `pipeline/drift/fetch_fields.py` | **new** — pulls HYCOM + ERA5 via `getRegion`, caches to `data/fields/<case>.npz`, prints field statistics |
| `pipeline/drift/fields.py` | **+`GriddedField`** (bilinear space, linear time, land-aware) and `load_case_field()` |
| `pipeline/drift/plot_quiver.py` | **new** — the checkpoint picture; coastline comes free from HYCOM's own land mask, no cartopy |
| `pipeline/drift/check_gee.py` | corrected the unit note it prints |
| `data/fields/case-000.npz` | **new**, 0.02 MB — gitignored |

### The cached field

- Currents: 19 lon × 20 lat, **2 time steps, 24 h apart** (HYCOM on GEE is daily)
- Winds: 7 lon × 6 lat, 30 time steps, hourly
- 41 % of the box is land-masked in HYCOM

**Open issue — currents are daily, not hourly.** Over a 24 h rewind the current field is a
linear blend of just two snapshots, so sub-daily eddies are invisible. This is a real limit on
how tight the origin cloud can honestly be, and it belongs in the receipts and the demo
narrative rather than being hidden. The Phase 3 ensemble (current × N(1, 0.15)) is what carries
this uncertainty. Wind is hourly, so no issue there.

### Verified on real fields, not just fakes

```
60x60 sweep over the whole box          all finite (land falls back, no NaN leaks)
24 h backward, 200 particles            97 frames, exactly 24.0 h
  displacement                          median 50.6 km (min 41.1, max 57.0)  -> plausible
  centroid                              [80.450, 13.298] -> [80.644, 13.710]
round trip fwd->back through real field returns within 0.000 km
tests.py                                4/4, 12/12 assertions
```

Origin sits **north-east and offshore** of the slick, which is the correct direction: the
current runs south-west, so rewinding travels upstream against it. The quiver plot agrees.

**Run command:**
```bash
venv\Scripts\activate
python pipeline/drift/check_gee.py
python pipeline/drift/fetch_fields.py --case case-000        # add --force to refetch
python pipeline/drift/plot_quiver.py --case case-000
python pipeline/drift/tests.py
```

**Checkpoint image:** `pipeline/drift/out/quiver_case-000.png` — land west, arrows 0.3–1.1 m/s
running south, slick outline in water. Post in group.

**Next:** Phase 3 (Tue, hard deadline) — seed from `detections.geojson`, 24 h backward, 50-run
ensemble, 2D histogram → real `particles.json` + `origin.json` for Akshat. `GriddedField` is
ready; `run.py` still calls the fake field and needs switching to `load_case_field()`.

---

## Test scoreboard — last run 2026-09-06, all four green

| # | Test | Expected | Measured | Result |
|---|---|---|---|---|
| 1a | Constant current 0.5 m/s east, 10 h | 18.0 km east ±2% | **18.0000 km** (0.000% error) | ✅ PASS |
| 1b | No northward drift (u/v not swapped) | < 0.05 km | **+0.000000 km** | ✅ PASS |
| 1c | Moved east, not west (sign convention) | lon increases | 80.35000 → **80.51612** | ✅ PASS |
| 2a | Round trip fwd 24 h + bwd 24 h | within 0.5 km | **0.0001 km** worst of 5 particles | ✅ PASS |
| 2b | The trip was not trivial | > 5 km outbound | **16.21 km** median | ✅ PASS |
| 2c | Time returns to t0 | exact | 00:14Z → 30th 00:14Z → **00:14Z** | ✅ PASS |
| 3a | Wind 10 m/s, no current | 0.30 m/s | **0.300000 m/s** (coeff 0.0300) | ✅ PASS |
| 3b | …and it physically travels that far | 1080 m in 1 h | **1080.0 m** | ✅ PASS |
| 4a | Guard ACCEPTS a real-looking ocean | 5–200 km / 48 h | **8.81 km** median | ✅ PASS |
| 4b | Guard REJECTS a cm/s field (50 m/s) | raises | raised, with the "divide by 100" message | ✅ PASS |
| 4c | Guard REJECTS a dead all-zero field | raises | raised (0.000 km < 5 km floor) | ✅ PASS |
| 4d | Speed guard picks the fastest particle | 1.2369 m/s | **1.2369 m/s** | ✅ PASS |

**4/4 tests, 12/12 individual assertions. Zero failures.**

Caveat on where this was run — see open issue #1.

---

## Phase 1 — what remains

**Merge `main` before committing.** `origin/main` moved to `278f463` while Phase 1 was being
written. His commit edits the same two lines of `run.py` that Phase 1 edits (`--steps` default,
`span_h` formula) to the same values, so expect a small conflict there — take either side, they
agree. It also regenerates `cases/case-000/{particles,origin,vessels}.json`, which is why the
stray CRLF-only modifications must be reverted first or the pull will refuse:

```bash
git checkout -- .gitignore cases/case-000/     # discards CRLF-only noise; content is identical
git pull --rebase origin main
python pipeline/drift/tests.py                 # must still be 4/4 after the merge
python pipeline/drift/run.py --case case-000 --fake
```


The code is finished and proven. Three things are outstanding, and none of them are code:

| # | Step | Why it matters | Status |
|---|---|---|---|
| 0 | Merge `main` | Done — rebased onto `278f463`. One conflict in `run.py` (both sides had changed the same two lines to the same values); kept the local side, which carries the explanatory help text. | ✅ |
| 1 | Re-run both commands in the Windows venv | Done, post-rebase. 4/4, 12/12. `rewound 24.00 h in 97 steps`, `t0 2017-01-29T00:14:00Z -> 2017-01-28T00:14:00Z`. Identical to the Linux/3.10 run to the last decimal — median 14.0 km, origin (80.3363, 13.2336), r50 6.2, r90 9.6. | ✅ |
| 2 | Post the test output in the group | This IS the Phase 1 checkpoint in `03_ANUSHKA_DRIFT.md`. Until it's posted, the team's picture of Stage 2 is "not started". | ⬜ |
| 3 | **Push branch `anushka`** | Committed as `5ec0aa4`, rebased onto `278f463`. Not yet pushed — `git push origin anushka`. `run.py --fake` writes a schema-valid bundle Harshita can build the slider against; it helps nobody sitting on one laptop. | ⬜ |

Nothing in Phase 2 is blocked by these. **#3 unblocks Harshita, so it is the one worth doing tonight.**

---

## [2026-09-06 21:15] Phase 1 — fake fields + known-answer tests

**Done:** The whole Stage 2 integrator now exists and is proven against analytic fields, with no
data, no GEE and no network. `fields.py` provides two analytic oceans (`ConstantField` for exact
known answers, `AnalyticField` — a Taylor–Green vortex cell — for tests a constant field would
pass trivially), both exposing `get_uv` / `get_wind` returning signed u/v in m/s. `step.py` is the
real physics: `velocity = current + 0.03 × wind`, RK2 midpoint, dt = 15 min, vectorised NumPy over
an `[n, 2]` lon/lat array, with backward implemented as a **negative dt through the same field**.
`run.py` no longer random-walks — `fake_walk()` is deleted and `--fake` drives the true integrator,
producing a bundle that validates.

**Files touched:** `pipeline/drift/fields.py` (new) · `pipeline/drift/step.py` (new) ·
`pipeline/drift/check_gee.py` (new — EE preflight, replaces the deleted root-level `test_ee.py`) ·
`pipeline/drift/tests.py` (new) · `pipeline/drift/run.py` (modified — `fake_walk()` removed,
`--fake` added, `--stub` kept as a silent alias so nobody's existing command breaks) ·
`pipeline/drift/out/particles.json` + `out/origin.json` (output)

**Run command:**
```bash
python pipeline/drift/tests.py
python pipeline/drift/run.py --case case-000 --fake
```
Expected output: `4/4 tests passed   (12/12 individual assertions)`, then a `[drift:FAKE]` block
reporting median displacement ~14 km, origin ≈ (80.336, 13.235), r50 ≈ 6.1 km, r90 ≈ 9.5 km.

**Validator:**
```bash
python scripts/validate_case.py cases/case-000     # after copying out/*.json into a case folder
```
→ `PASS  acts=['detect','trace','attribute']  (1 warning)`. The one warning is
`only 1 ensemble runs; uncertainty will look fake` — correct and honest for Phase 1; Phase 3
makes it 50.

**Checkpoint artefact:** test output above. Not yet posted in the group.

**Two design decisions worth defending:**
- *The round-trip test uses a varying field, not a constant one.* In a constant field,
  forward-then-backward is exact arithmetic reversal — the test would pass even if backward mode
  were wrongly coded as a sign flip on velocity, which is the exact bug it exists to catch. With a
  vortex the two directions sample different velocities, so closing to 10 cm means something.
- *Test 4 asserts in both directions.* A guard that only confirms good data passes cannot fail.
  It must also reject the cm/s field and the dead field, and it does.

**Open issues:**
1. **Tests have not yet been run in the Windows venv.** They were run with Python 3.10.12 /
   NumPy 2.2.6. The project standard is Python 3.11. Re-run both commands inside
   `venv\Scripts\activate` and confirm 4/4 before posting the checkpoint. If NumPy is missing
   there: `pip install numpy scipy matplotlib`.
2. **GEE auth is unverified — but there is now a preflight for it.**
   `pipeline/drift/check_gee.py` replaces the old root-level `test_ee.py` (deleted: wrong
   location, pytest-colliding name, hardcoded personal project id). It checks auth, then that
   HYCOM and ERA5 actually return imagery over the case box and dates, that the band names match
   the doc, and that the sampled values are the right order of magnitude.
   **Run it before starting Phase 2 — it has never been executed against real credentials:**
   ```bash
   python pipeline/drift/check_gee.py
   ```
   Expected: `All checks passed`. Anything else is the 45-minute-rule item; escalate to Akshat
   rather than losing an evening. Re-run it before the US case too — HYCOM's GEE archive ends
   2024-09-05 and the Gulf sits at negative longitude, so both answers change.
3. **`ensemble_runs` is 1 and `origin.json` says so.** Not a bug, but it must not reach the demo.
   Phase 3.
4. **`time_window` is still the stub's crude `[t0−span, t0−span/3]`,** not a convergence estimate.
   Phase 3 replaces it, or ships the bounded window and marks `method: "bounded"` per the cut order.
5. **~~23.75 h vs 24 h~~ — RESOLVED by Akshat, commit `278f463` on `main`.** `n_steps` is now
   **97**: the `t0` position plus 96 backward intervals = exactly 24.0 h. The rule is now written
   into `CONTRACTS.md` §5: *duration is always derived as `(n_steps − 1) × timestep_minutes`; never
   hardcode a frame count.* Applied locally — `--steps` default is 97 and `run.py` reports
   `rewound 24.00 h`, `t0 2017-01-29T00:14:00Z -> 2017-01-28T00:14:00Z`. Tests still 4/4.
   `step.py`'s `integrate()` docstring now states the fencepost rule so the next person doesn't
   reintroduce it.

6. **~~Uncommitted changes to `cases/case-000/`~~ — RESOLVED, they were noise.** The three JSONs
   were byte-identical to the committed versions; only the line endings had been changed to CRLF
   by something on Windows, which `.gitattributes` (`* text=auto eol=lf`) flags. The `.gitignore`
   edit appended `venv/` and `data/`, both already covered on lines 11 and 2. All four reverted
   with `git checkout --`; nothing was lost. *If they reappear, find out which tool is rewriting
   line endings — it will keep doing it.*
7. The vortex used in test 4a is a closed cell, so its 48 h displacement (8.81 km) sits near the
   5 km floor. Real HYCOM will move particles further. If the floor ever trips on real fields,
   look at the field before loosening the bound.

**Next:** Phase 2 — HYCOM (`HYCOM/sea_water_velocity`, bands `velocity_u_0`/`velocity_v_0`,
**cm/s → divide by 100** — ⚠️ SUPERSEDED 2026-09-07: the correct divisor is **1000**, see the
Phase 2 entry above) and ERA5 (`ECMWF/ERA5/HOURLY`, `u_component_of_wind_10m` /
`v_component_of_wind_10m`) into a `GriddedField` with the same `get_uv` / `get_wind` methods,
cached to `data/fields/<case>.npz`. Nothing in `step.py`, `tests.py` or `run.py` should need to
change. Checkpoint is a quiver plot over Ennore with plausible arrows, plus test 4 green on the
real field.

---

## [2026-09-06 20:20] Phase 0 — setup

**Done:** Repo cloned to `Desktop/udgam`, branch `anushka` checked out, `venv` created and
populated (numpy, scipy, matplotlib, earthengine-api, pillow). Earth Engine signup started;
`test_ee.py` written against project `project-c6f47846-50cd-4991-94c`.

**Files touched:** `test_ee.py` (new, untracked — scratch, not part of the pipeline)

**Run command:**
```bash
venv\Scripts\activate
python scripts/make_case000.py && python scripts/validate_case.py cases/case-000
```
Expected output: `PASS`.

**Open issues:** GEE authentication not confirmed working (see Phase 1 open issue #2).

**Next:** Phase 1.
