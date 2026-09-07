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
| 3 | Backward + 50-run ensemble → real `particles.json` / `origin.json` | ⬜ not started (**Tue evening, hard deadline**) |
| 4 | Buffer Wed; rerun on the US case | ⬜ not started |

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

**Done:** Repo cloned to `Desktop/naap`, branch `anushka` checked out, `venv` created and
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
