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
| 2 | Real HYCOM + ERA5 loaders, quiver plot | ⬜ not started (Mon) |
| 3 | Backward + 50-run ensemble → real `particles.json` / `origin.json` | ⬜ not started (**Tue evening, hard deadline**) |
| 4 | Buffer Wed; rerun on the US case | ⬜ not started |

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
| 0 | Merge `main` (see the block above) |  `origin/main` is 1 commit ahead and touches `run.py`. Do this before anything else. | ⬜ |
| 1 | Re-run both commands inside `venv\Scripts\activate` on Windows | The green result above came from Python 3.10.12 / NumPy 2.2.6 on a Linux shell. The project standard is 3.11. A result you haven't seen on your own machine isn't yours yet. | ⬜ |
| 2 | Post the test output in the group | This IS the Phase 1 checkpoint in `03_ANUSHKA_DRIFT.md`. Until it's posted, the team's picture of Stage 2 is "not started". | ⬜ |
| 3 | Commit the drift files + this log, push branch `anushka` | `run.py --fake` writes a schema-valid bundle Harshita can build the slider against. It helps nobody sitting on one laptop. **Commit only the 5 drift/log files** — see open issue #6. | ⬜ |

Nothing in Phase 2 is blocked by these. But #3 unblocks Harshita, so it is the one worth doing tonight.

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

6. **Uncommitted changes to `cases/case-000/`** (`bounds.json`, `meta.json`, `suspects.json`) and
   `.gitignore` were already modified in the working tree before Phase 1 started, by something
   else. Harshita builds against that fixture — check what they are before committing, and don't
   sweep them into a drift commit.
7. The vortex used in test 4a is a closed cell, so its 48 h displacement (8.81 km) sits near the
   5 km floor. Real HYCOM will move particles further. If the floor ever trips on real fields,
   look at the field before loosening the bound.

**Next:** Phase 2 — HYCOM (`HYCOM/sea_water_velocity`, bands `velocity_u_0`/`velocity_v_0`,
**cm/s → divide by 100**) and ERA5 (`ECMWF/ERA5/HOURLY`, `u_component_of_wind_10m` /
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
