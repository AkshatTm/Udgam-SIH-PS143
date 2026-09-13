# Stage 2 — Drift Engine: Full Component Report

**Project:** NAAP · SIH 2026 · PS 26143 — oil spill detection, backtracking and vessel attribution
**Component:** Stage 2 (Trace) — backward particle drift, ensemble uncertainty, origin probability cloud
**Owner:** Anushka
**Report date:** 2026-09-08
**Code state described:** branch `anushka`, commit `fd5aaf4` (pushed), plus 5 files of uncommitted follow-up work (§16)
**Every number in this report was read out of the code or the output files, not from memory.** Where an earlier document quotes a different figure for the same quantity, both are shown with the definition that produced each.

---

## 0. One-page summary

**What this component does.** It takes an oil slick found in a satellite radar image and runs the ocean backwards. 3,000 virtual particles are placed on the slick, then advected backward in time through real ocean-current and wind fields for 24 hours in 15-minute steps. The whole physics is one line — `velocity = current + 0.03 × wind` — integrated with RK2. Doing this once gives a trajectory; doing it 50 times with the inputs perturbed inside their honest uncertainty gives an **answer with error bars**. The spread of those 50 runs *is* the uncertainty we report. No machine learning, no GPU, no training data.

**What it produces.** Two files that the rest of the project consumes:

| File | What it is | Consumed by |
|---|---|---|
| `particles.json` | The animation — one unperturbed control run, 97 frames × 3,000 particles, 6.34 MB | Frontend (the rewind slider) |
| `origin.json` | The answer — a 120×120 probability grid built from 150,000 ensemble endpoints, plus centroid, r50/r90 radii, time window, abstain flag | Stage 3 (attribution) and the frontend |

**Result on the Ennore box (real HYCOM + ERA5 fields, `case-000` seed polygon):**

```
origin centroid   (80.62097, 13.69967)
radius 50%        8.78 km          radius 90%   17.30 km
displacement      47.8 km from the slick, bearing 025° (north-east = upstream)
control run       median 48.4 km over exactly 24.00 h
ensemble          50 runs × 3,000 particles = 150,000 endpoints
time window       2017-01-28T00:14Z → 2017-01-28T16:14Z   method = "bounded"
abstain           false  (r90 17.3 km, well under the 40 km threshold)
tests             5/5 suites, 20/20 individual assertions
validator         PASS, 0 errors, 0 warnings
runtime           ~22 s for the full 50 × 3,000, deterministic at --seed 143
```

**How much of this is real.** The ocean is real: actual HYCOM currents and ERA5 winds, for the real Ennore box and the real dates, pulled from Google Earth Engine. The **slick is not** — it is `case-000`'s invented polygon, because Stage 1's real `detections.geojson` has not landed yet. So these coordinates prove the pipeline runs end to end; they are **not yet a claim about the Ennore spill** and must not appear on a slide labelled Ennore until the real detection and the verified scene arrive. When they do, nothing in the drift code changes — that was the point of the file-based seam.

**Accuracy, stated honestly.** There is no ground truth for where the Ennore oil actually entered the water, so we cannot quote a validation error in kilometres, and we do not. What we can defend is (a) the integrator is exact against known answers — 18.0000 km measured against 18.0 km expected, 0.000% error; a 24 h forward-then-backward round trip closes to 0.0001 km; (b) the physics constant, the field, and the uncertainty budget are all sourced and stated; (c) the reported spread is a measured ensemble spread, not an assumed one. **The honest claim is "the method is correct and its uncertainty is measured", not "the answer is accurate to 8.8 km".**

**Top three risks ahead.** (1) The downloaded ocean box is padded by a fixed 0.5° ≈ 55 km — fine for Ennore's 0.5 m/s currents, but the Gulf Loop Current at 1.8 m/s covers 156 km in 24 h and would silently pin particles to the edge of the box. (2) Stage 3 scores suspects with a circle, but the real cloud is a 4.4 : 1 streak, so ~45% of the high-probability area falls outside the r50 circle. (3) The whole component has only ever run against one synthetic slick on one laptop; the first contact with Stage 1's real output is also the first time several code paths execute.

Full detail follows. §9–§11 are the test data and results; §13 is every bug found; §15 is the risk register; §17 is what needs a decision from you.

---

## 1. Scope — what this component is and is not

### In scope
- Reading ocean current and 10 m wind fields for a case region and time window.
- Seeding particles onto a detected slick according to its shape.
- Integrating those particles backward in time.
- Running a 50-member perturbed ensemble and turning it into a probability field.
- Estimating **when** the oil entered the water, or refusing to and saying so.
- Writing the two contract files, and proving they are valid.

### Explicitly out of scope (and why)
| Not built | Why |
|---|---|
| Machine learning of any kind | The physics is deterministic and known. ML here would add opacity without accuracy. |
| Forward drift / prediction | Master plan §10 — October roadmap. |
| Oil weathering, evaporation, emulsification | We track *where* a parcel went, not what it became. A weathering model needs oil-type data we do not have. |
| 3D / subsurface transport | Surface slicks only; HYCOM surface layer (`velocity_u_0`) is the correct band. |
| Stokes drift / wave-induced transport | Folded into the empirical 3% wind coefficient, which is what that coefficient exists to represent. |
| Turbulent diffusion (random-walk dispersion) | Deliberate: our spread comes from *parameter* uncertainty, which is honest and defensible. Adding a diffusion coefficient we could not source would inflate the cloud with a number we invented. Stated as a limitation in §14. |
| OpenDrift validation | Master plan §10 — October. |

### The seam
Stage 2 imports nobody's code and nobody imports Stage 2. It reads `cases/<id>/{meta.json, bounds.json, detections.geojson}` and writes `out/{particles.json, origin.json}`. That is the entire interface. It is why Stage 2 could be finished before Stage 1 existed.

---

## 2. Architecture and code map

```
pipeline/drift/
├── CLAUDE.md            per-directory rules for any AI session opened here
├── fields.py     13.5 KB  field sources: ConstantField, AnalyticField, GriddedField, load_case_field
├── step.py        8.5 KB  the physics: drift_velocity, rk2_step, integrate, plausibility guards
├── ensemble.py   14.2 KB  PerturbedField, run_once, run_ensemble, radii_km, origin_grid, time_window
├── run.py        11.8 KB  CLI: seed → control run → ensemble → write the two files
├── fetch_fields.py 8.3 KB  GEE download → data/fields/<case>.npz (run once per case)
├── check_gee.py   8.6 KB  preflight: auth, collections, bands, magnitudes
├── tests.py      14.5 KB  5 known-answer test suites, 20 assertions
├── plot_quiver.py 4.9 KB  Phase 2 checkpoint picture
├── plot_heatmap.py 8.0 KB  Phase 3 checkpoint picture
└── out/                   particles.json, origin.json, ensemble_<case>.npz, the two PNGs
```

### Data flow

```
cases/<id>/meta.json ─┐
cases/<id>/bounds.json ┼─→ fetch_fields.py ──→ data/fields/<id>.npz   (GEE, once per case, cached)
                       │                              │
cases/<id>/detections.geojson                         │
          │                                           ▼
          │                              fields.load_case_field()  ── cache-vs-bundle guards
          ▼                                           │
   run.py: pick_slick() → seed_particles()            │
          │                                           │
          ├──── control run ── step.integrate() ──────┤ ──→ out/particles.json   (the animation)
          │                                           │
          └──── 50 members ── ensemble.run_ensemble() ┘ ──→ out/origin.json      (the answer)
                                                             out/ensemble_<case>.npz (endpoint pool)
```

### The design rule that everything obeys
Every field source — the constant ocean, the analytic vortex, the real HYCOM/ERA5 grid, and the perturbed wrapper around any of them — exposes exactly two methods:

```python
get_uv(lons, lats, when)   -> (u, v)   surface current, signed m/s
get_wind(lons, lats, when) -> (u, v)   10 m wind,       signed m/s
```

`step.py` and `run.py` never learn where the numbers came from. This is why Phase 2 (swapping the fake ocean for the real one) touched **zero lines** of `step.py`, `tests.py` or `run.py`, and why the 50-member ensemble works identically over the analytic field in the tests and over real HYCOM in production.

---

## 3. The physics and the numerical method

### 3.1 The one equation
```
drift velocity = surface current + 0.03 × wind_10m
```
The 3% rule is the single empirical constant in Stage 2: floating oil moves with the current plus roughly 3% of the 10 m wind speed. It is a well-established band in oil-spill modelling, not an exact number — which is precisely why the ensemble perturbs it over U(0.025, 0.035) rather than treating 0.03 as truth.

Velocities are always handled as **signed components** (u = eastward, v = northward, m/s). They are never converted to speed-and-bearing anywhere in the codebase. That conversion is where the meteorological convention ("wind *from* 270°") and the oceanographic convention ("current *towards* 90°") collide, and it is a classic silent sign error.

### 3.2 Integration — RK2 midpoint, dt = 15 min
```python
u1, v1 = velocity(pos, t)
mid    = pos + 0.5 · dt · u1        (converted to degrees)
u2, v2 = velocity(mid, t + dt/2)
new    = pos + dt · u2
```
Second-order accurate, vectorised over all 3,000 particles as a single NumPy `[n, 2]` array — no Python loop over particles. 15 minutes is short enough that RK2 truncation error is far below the field's own resolution error (§12).

### 3.3 Backward mode — the rule that matters most
> **Backward is a NEGATIVE dt through the same field. It is NOT a minus sign on velocity.**

In a steady uniform ocean these two are identical, which is exactly why a naive test cannot tell them apart. In a varying field they differ: with a negative dt the RK2 midpoint is evaluated at `t − dt/2`, so a backward step samples the field *half a step into the past*, which is the physically correct thing to do. The round-trip test (§9, test 2) is run in a **vortex field on purpose** so that it can distinguish the two; in a constant field it would pass even with the bug present.

### 3.4 Metres ↔ degrees
```python
dlat = dy / 111320
dlon = dx / (111320 · cos(lat))
```
WGS84 mean metres per degree, spherical earth. Good to ~0.5%, which over a 48 km displacement is ~240 m — an order of magnitude below the 8.78 km r50 the ensemble measures, so a spherical earth is the right simplification here and an ellipsoidal correction would be false precision. `cos(lat)` is floored at 1e-6 so the conversion cannot blow up at a pole (we are in the tropics, but the guard costs nothing).

### 3.5 The fencepost rule (was a real bug — see §13.5)
`n_steps` counts **stored positions, not physics steps.** Seeding a start state and then taking N backward steps leaves N+1 stored positions. Therefore:

```
duration = (n_steps − 1) × timestep_minutes
97 stored positions × 15 min  =  96 intervals  =  exactly 24.00 h
```

Never hardcode 96 or 97 anywhere — this rule is now written into `CONTRACTS.md` §5, into `integrate()`'s docstring, and into the frontend brief.

### 3.6 Longitude convention
Everything stays in −180…180 and is wrapped in exactly one place (`wrap_lon` in `step.py`). Ennore at 80°E is identical in both the −180…180 and 0…360 conventions, so a leak would stay invisible until the US case at negative longitude. Wrapping once, centrally, is the defence.

### 3.7 Time convention
Every timestamp is timezone-aware UTC. `require_aware()` raises on any naive datetime, on every call into every field. Naive datetimes compare as if they were UTC right up until the moment they don't.

---

## 4. Data sources

| | Currents | Winds |
|---|---|---|
| Collection | `HYCOM/sea_water_velocity` | `ECMWF/ERA5/HOURLY` |
| Bands | `velocity_u_0`, `velocity_v_0` (surface layer) | `u_component_of_wind_10m`, `v_component_of_wind_10m` |
| Native resolution | 0.08° ≈ 9 km | ~0.25° ≈ 28 km |
| Cadence in GEE | **daily** | hourly |
| Units as served | scaled integer, **catalog units m/s, scale 0.001 → divide by 1000** | signed m/s, no scaling |
| GEE archive coverage | 1992-10-02 → **2024-09-05** | ongoing |
| Sample scale used | 9,000 m | 27,750 m |

Access is via the Earth Engine Python API (`getRegion`), pulled once per case over a lookback window of **30 hours** ending at `detection_time`, and cached to `data/fields/<case>.npz`. Nothing re-fetches during iteration.

### The cached field actually in use (`data/fields/case-000.npz`, 18 KB)

```
case_id            case-000
bbox               79.60 – 81.20 E,  12.45 – 14.05 N
t0                 2017-01-29T00:14:00Z
current grid       19 lon × 20 lat × 2 time slices
current times      2017-01-28 00:00Z, 2017-01-29 00:00Z      ← 24 h apart. This is the daily-HYCOM limit.
wind grid          7 lon × 6 lat × 30 time slices (hourly)
land-masked        40.8 % of current cells
current speed      median 0.480 m/s   p99 1.063   max 1.097
wind speed         median 4.36 m/s    max 7.27
```

The current field flows **south along the Coromandel coast at 0.3–1.1 m/s**, which is the East India Coastal Current under the January north-east monsoon. That independent physical agreement — not just "the numbers look small enough" — is what confirms the ÷1000 scaling is right.

### Land handling
HYCOM masks land as NaN. A bilinear interpolation touching a single NaN corner poisons the whole sum, and a NaN position silently removes a particle from the ensemble — which would bias the origin cloud toward open water without any error being raised. So: a cell with some wet corners falls back to the mean of the wet ones; a cell that is entirely land returns velocity 0, holding the particle. That is the honest answer — **the model cannot say where a beached slick came from**, and it should not invent a velocity in order to pretend otherwise.

---

## 5. Seeding — from a detection polygon to 3,000 particles

`pick_slick()` takes the **highest-confidence feature whose `classification == "oil"`**. Zero oil features is not a crash — it is the designed no-spill case, and the run exits with a message saying `trace` should not be in `acts_available`.

`shape_class` then decides the geometry, and this field carries physics, not metadata:

| `shape_class` | Meaning | Seeding |
|---|---|---|
| `"linear"` (elongation > 3) | a moving ship discharging along its track | 3,000 particles spread uniformly along the polygon's principal axis, ± 300 m gaussian jitter |
| `"blob"` (elongation ≤ 3) | a stationary event — a collision, a grounding, a platform | gaussian around the centroid, σ = half the equivalent radius from `area_km2` |

The principal axis is approximated by the most-distant point pair in the polygon ring (sampled every 4th vertex — the ring has 41 points, so this is exact enough and cheap).

**Note on which field is trusted:** the linear seeder reads the **geometry**, not `area_km2`. The polygon is the measurement; `area_km2` is a derived summary. In `case-000` the two disagree — the `det-01` ring spans about 21 km, while `area_km2: 12.4` with `elongation: 8.2` implies a slick roughly half that length. Harmless in a synthetic bundle, but if Stage 1's real detector ever computes area from a different mask than the polygon it exports, Stage 2 seeds the wrong *length* of slick with no error anywhere. See §15, risk R7.

---

## 6. The ensemble — where the uncertainty comes from

One run gives a trajectory. It does not give an answer, because the inputs are not known exactly. So the run is repeated 50 times with the inputs jiggled inside their honest uncertainty, and **the spread of where those runs land is the answer.**

### 6.1 The perturbation budget — every number defensible

| Perturbed | Distribution | Why this and not something else |
|---|---|---|
| Wind coefficient | U(0.025, 0.035) | The 3% rule is a 2.5–3.5% band in the literature, not a constant. |
| Current field | × N(1, 0.15) | Carries the daily-HYCOM ignorance: across a 24 h rewind the field is a blend of two snapshots and cannot see a sub-daily eddy. 15% is the honest magnitude of that blindness. Clipped at 0.05 — a negative scale would reverse the ocean, which is not an uncertainty, it is a different planet. |
| Seed positions | ± 300 m gaussian, redrawn per member | The slick outline is a detector output, not a survey boundary. |

**Deliberately NOT perturbed: wind direction and the wind field itself.** ERA5 is hourly and well constrained over open ocean. The uncertainty that matters is *how much* of the wind the oil feels (the coefficient), not what the wind was doing. Perturbing both would double-count the same ignorance and inflate the cloud with a number we made up.

### 6.2 Stratified sampling — a real bias, caught and fixed

Fifty **independent** draws from N(1, 0.15) have a sample mean that scatters by about 0.021. On the first run, the realised mean current came out ~3% fast — which pushed the entire origin cloud **1.4 km further from the slick than the physics warranted**. That is a sampling artefact being reported as physics, and no test would have flagged it because every individual number was legitimate.

The fix is stratification: split each distribution into 50 equal-probability slices and take one draw from each, then shuffle the two parameter lists independently so wind and current stay uncorrelated. `statistics.NormalDist.inv_cdf` from the standard library does the inverse-CDF — no new dependency.

**Measured effect, read out of `ensemble_case-000.npz`:**

| Parameter | Claimed | Realised across the 50 members | Range |
|---|---|---|---|
| Wind coefficient | U(0.025, 0.035), mean 0.030 | mean **0.03001**, sd 0.00291 | 0.0251 – 0.0348 |
| Current scale | N(1, 0.15) | mean **0.9982**, sd **0.149** | 0.625 – 1.329 |

And the bias is gone: the pooled ensemble centroid now sits **0.095 km** (95 m) from the control run's endpoint, against 1.4 km before the fix.

### 6.3 Memory
Full history for 50 × 3,000 × 97 positions is ~230 MB. It is never stored. Each ensemble member keeps only its final positions and a per-step spread curve; full history is kept for the control run alone, because that is the only run the animation needs.

---

## 7. The origin cloud — from 150,000 points to `origin.json`

### 7.1 Radii are measured from raw endpoints
`radius_50_km` and `radius_90_km` are the **50th and 90th percentiles of endpoint distance from the centroid** — not standard deviations. A real drift cloud is not gaussian and should not be quoted as if it were.

### 7.2 The grid
The 150,000 pooled endpoints go into a 120×120 2D histogram over a bounding box padded 5% around the cloud, then flipped so that **row 0 is NORTH** (row-major from the top-left), matching `bounds.json`'s pixel convention so the frontend can draw it straight over the scene without flipping anything.

### 7.3 Smoothing — a display choice, stated openly
The raw histogram is not the density. Two artefacts sit on top of it:
- **Shot noise** — 150,000 points over 14,400 cells averages ~10 counts a cell.
- **Member banding** — with a *linear* slick, each ensemble member translates the seed line almost rigidly, so 50 members land as 50 near-parallel ridges. Those ridges are an artefact of having 50 samples, not 50 distinct places the oil could have come from, and a grid that keeps them would tell Stage 3 to prefer stripes that mean nothing.

So the histogram is smoothed into a kernel density estimate with a **bandwidth tied to the cloud's own scale** — one tenth of r50, converted to grid cells, capped at rows/8 so it can never blur the cloud away. It is not eyeballed to make the picture look nice.

**Critically: this changes the picture, never the numbers.** Centroid, r50 and r90 are all measured from the raw endpoints in `radii_km()`, never from the grid. No reported quantity depends on the bandwidth. The gaussian blur is written out as two 1-D convolutions in pure NumPy on purpose — producing the handoff files must need nothing beyond NumPy, so it runs on whichever laptop happens to be free.

### 7.4 Abstention
`abstain = (radius_90_km > 40 km)`. When true, Stage 3 must return an empty `suspects` array (the validator enforces this) and the UI shows *"attribution not possible at acceptable confidence"*. This is a designed refusal and a feature to show off — a system that knows when it does not know is the difference between forensics and guessing. Ennore is `abstain: false`.

---

## 8. The time window — measured, or bounded and said so

### The preferred method
Each member's particle cloud is tightest at some step; rewound particles should be at their most concentrated at the moment they were released. Take the 10th–90th percentile of those convergence times across the 50 members, and that is a **measured** release window.

### Two guards that refuse to dress up noise
1. The median member must actually tighten to **≤ 90%** of its starting spread.
2. The dip must be **interior** to the run, not pinned to the first or last step.

If either fails, the estimator declines to fire and the bounded window `[t0 − 24 h, t0 − 8 h]` ships instead, marked as such.

### What happened at Ennore, and why it is the honest answer
Both guards fail, and the evidence is unambiguous. Read straight out of `ensemble_case-000.npz`:

```
conv_idx across all 50 members:   min 0,  max 0,  median 0
```

**Every single member's spread was smallest at step 0** — the seed itself. The cloud never converges going backwards; it only ever spreads. That is exactly what the physics predicts here: HYCOM on GEE is daily, so across a 24 h rewind the current field is a linear blend of two snapshots, the flow is smooth, and the particle cloud **translates rather than converging**. There is no eddy structure to squeeze it.

So we ship:
```
time_window        2017-01-28T00:14Z → 2017-01-28T16:14Z
time_window_method "bounded"
```

This is the cut-order outcome the brief explicitly anticipated, not a shortfall. The convergence estimator is fully implemented and unit-tested (tests 5g and 5h prove both branches), and it will switch on by itself the first time a case has a real eddy in it.

**Why this matters more than a key name:** it is the difference between *"we measured when the oil entered the water"* and *"we bounded when the oil entered the water"*. The second is what we can defend in December. If the UI implies a most-likely release moment inside a bounded window, that is the one number on screen we could not defend.

---

## 9. The test suite — 5 suites, 20 assertions

Run: `python pipeline/drift/tests.py` → `5/5 tests passed (20/20 individual assertions)`

These were written in Phase 1, **before any real data existed**, against analytic fields with exact known answers. That ordering is the whole defence of this component: wrong-but-running code is its failure mode, and a units bug produces a beautifully plausible wrong answer. The tests exist so nobody has to catch one by eye — and on 2026-09-07 they caught one on the very first real download (§13.1).

### Test 1 — Constant current, 0.5 m/s east, no wind, 10 h
Field: `ConstantField(current=(0.5, 0.0))`. Expected: 0.5 × 36,000 s = **18.0 km east**.

| ID | Assertion | Expected | Measured | |
|---|---|---|---|---|
| 1a | Eastward displacement | 18.0 km ± 2% | **18.0000 km**, 0.000% error | PASS |
| 1b | No northward drift (u/v not swapped) | < 0.05 km | **+0.000000 km** | PASS |
| 1c | Moved east not west (sign convention) | lon increases | 80.35000 → **80.51612** | PASS |

*What each failure mode would have meant:* off by ×1000 → units bug · moved north → u/v swapped · moved west → sign convention bug.

### Test 2 — Round trip: forward 24 h, then backward 24 h
Field: `AnalyticField` — a Taylor–Green vortex cell, amplitude 0.5 m/s, scale 0.4°, wind (6, −4) m/s. **A varying field on purpose:** in a constant field the round trip is exact arithmetic reversal and would pass even if backward mode were wrongly coded as a sign flip on velocity — the exact bug this test exists to catch. 5 particles.

| ID | Assertion | Expected | Measured | |
|---|---|---|---|---|
| 2a | Returns to start | within 0.5 km | **0.0001 km** worst of 5 | PASS |
| 2b | The trip was not trivial | > 5 km outbound | **16.21 km** median | PASS |
| 2c | Time returns to t0 | exact | 00:14Z → 30th 00:14Z → **00:14Z** | PASS |

**This is the single most important test in the component.** Backward mode is the entire point of Stage 2, and errors in it produce answers that look fine and are wrong.

### Test 3 — Wind only, 10 m/s, no current
| ID | Assertion | Expected | Measured | |
|---|---|---|---|---|
| 3a | Drift velocity | 0.30 m/s | **0.300000 m/s** (coefficient 0.0300) | PASS |
| 3b | …and it physically travels that far | 1,080 m in 1 h | **1,080.0 m** | PASS |

### Test 4 — Permanent plausibility guards
These are not test-only. They run inside `drift_velocity()` and at the end of **every real run**, on real GEE fields, forever. A guard that only confirms good data passes cannot fail, so each is asserted in **both** directions.

| ID | Assertion | Expected | Measured | |
|---|---|---|---|---|
| 4a | A real-looking ocean **passes** the 48 h guard (5–200 km) | no raise | **8.81 km** median | PASS |
| 4b | A mis-scaled field (50 m/s) is **rejected** | raises | raised, with the ÷1000 message | PASS |
| 4c | A dead all-zero field is **rejected** | raises | raised (0.000 km below the 5 km floor) | PASS |
| 4d | Speed guard picks the fastest particle | 1.2369 m/s | **1.2369 m/s** | PASS |

The two live guards:
- `assert_speed_plausible` — no particle above **3.0 m/s**. A real surface current is 0–1.5 m/s; a field ~10× too fast is HYCOM's scale factor missed.
- `assert_displacement_plausible` — median displacement between **5 and 200 km per 48 h**, scaled linearly to the actual run length. Metres means the field is dead or dt is wrong; thousands of km means a units bug.

### Test 5 — Ensemble, grid orientation, time window (added in Phase 3)
Field: analytic vortex; 300 particles, 10 members, 49 steps (12 h — enough to separate members).

| ID | Assertion | Result |
|---|---|---|
| 5a | The ensemble is **wider** than one run | control r90 2.36 km → ensemble r90 **3.35 km** — +0.99 km of honest uncertainty. PASS |
| 5b | …but it does **not move the answer** | ensemble centroid **0.16 km** from control centroid (limit: 35% of r90). PASS |
| 5c | Radii ordered and positive | r50 1.81 km < r90 3.35 km. PASS |
| 5d | **Row 0 is NORTH** — the heatmap is not upside down | a deliberately bimodal cloud (90% north, 10% south) puts >75% of grid mass in the top half. PASS |
| 5e | Grid is 120×120, normalised to peak exactly 1.0 | PASS |
| 5f | `time_window` is ordered and inside the rewind | PASS |
| 5g | A **real** convergence dip is reported as `"convergence"` | synthetic tight dip → method=convergence. PASS |
| 5h | A **flat** spread curve falls back to `"bounded"` | spread 10.0 → 9.9 km → method=bounded. PASS |

Test 5d is the one worth calling out: an upside-down heatmap validates cleanly, looks entirely plausible, and points Stage 3 at the wrong water. **Nothing but a deliberate test catches it** — which is why the test cloud is bimodal rather than a symmetric blob, so the two orientations are genuinely distinguishable.

---

## 10. Test data — every input this component has ever been run against

### 10.1 Synthetic analytic fields (Phase 1, still used by the tests)
| Field | Definition | Used for |
|---|---|---|
| `ConstantField` | uniform steady current/wind, any values | tests 1, 3, 4b, 4c — exact known answers |
| `AnalyticField` | Taylor–Green vortex cell centred on the slick, divergence-free, peak speed = amplitude | tests 2, 4a, 5 — a smooth varying ocean with no data |

Standard test configuration: seed `[80.35, 13.25]` (lon, lat), `t0 = 2017-01-29T00:14:00Z`, dt = 15 min, RK2.

### 10.2 The seed slick — `cases/case-000/detections.geojson`
A **synthetic contract fixture**, built by `scripts/make_case000.py`. Two features:

| id | classification | confidence | area_km2 | elongation | shape_class | centroid | ring |
|---|---|---|---|---|---|---|---|
| `det-01` | **oil** | 0.87 | 12.4 | 8.2 | linear | [80.436, 13.310] | 41 pts, spans ~21 km |
| `det-02` | lookalike | 0.71 | 7.9 | 1.4 | blob | [80.262, 13.130] | 41 pts |

Stage 2 picks `det-01` (highest-confidence oil) and ignores `det-02` — which is itself a small test that the classification filter works.

Case metadata: `scene_id: "FAKE-000"`, `detection_time: 2017-01-29T00:14:00Z`, SAR scene bounds 80.10–80.70 E, 12.95–13.55 N, 1400 × 1400 px.

### 10.3 The real ocean — `data/fields/case-000.npz`
Real HYCOM and real ERA5, for the real Ennore box and the real dates. Full statistics in §4. **The fields are real; the slick is not.** That distinction is stated everywhere it could matter.

### 10.4 Forged bad caches (adversarial testing)
The cache-integrity guards were verified by **building broken caches and confirming they are refused**, not by reasoning about them:

| Forged input | Expected behaviour | Result |
|---|---|---|
| A named case with no bundle on disk | hard stop, name the directory, refuse to substitute | correct |
| Cache dated 2019 against a 2017 case | refuse: *"this cache is a different ocean than the case needs"* | correct |
| Cache boxed on the Gulf of Mexico | refuse: *"covers [W −91.0 …] which does not contain case-000's scene"* | correct |
| Wider box, same place and time | **allow** — a superset is a valid cache | correct |

### 10.5 Cross-platform reproduction
The full suite and the real run were executed on **two independent environments**: Linux / Python 3.10.12 / NumPy 2.2.6, and the project-standard Windows `venv` / Python 3.11. Every number was identical **to the last decimal**, including the ensemble figures. Nothing in Stage 2 uses SciPy — the gaussian blur is written out in NumPy on purpose — so NumPy plus matplotlib (plots only) is the entire requirement.

### 10.6 What has never been tested
Stated plainly, because it is where the next bug lives:
- Stage 1's **real** `detections.geojson` — never seen by this code.
- A **blob**-class slick end to end (only the `linear` branch has run on real fields).
- The **no-spill** path (zero oil features) end to end.
- The **abstain: true** state on real data (Ennore is comfortably `false`).
- **Negative longitudes** (the US case).
- The **convergence** time-window branch on a real field (only on synthetic input, test 5g).

---

## 11. Results — the Ennore run in full

Command (~22 s, deterministic at `--seed 143`):
```bash
python pipeline/drift/run.py --case case-000 --real --particles 3000 --runs 50
python pipeline/drift/plot_heatmap.py --case case-000
python pipeline/drift/tests.py
```

### `particles.json` — 6,337,296 bytes (6.34 MB)
```
t0                2017-01-29T00:14:00Z      direction  backward
timestep          15 min                    n_steps    97  (= exactly 24.00 h)
n_particles       3000                      array      97 × 3000 × 2
frame 0 centroid  (80.43586, 13.30979)   ← on the slick
frame 96 centroid (80.62143, 13.70040)   ← 24 h upstream
extent            lon 80.3448 … 80.7164     lat 13.2667 … 13.8108
control run       median displacement 48.4 km   (min 40.1, max 55.8)
```

### `origin.json` — 89,817 bytes
```
bounds       W 80.46498  S 13.47454  E 80.76801  N 13.96830   (32.8 km × 55.0 km)
shape        [120, 120]  =  14,400 floats, row 0 = NORTH, peak exactly 1.0
centroid     (80.62097, 13.69967)
radius_50    8.78 km        radius_90   17.30 km
time_window  2017-01-28T00:14:00Z → 2017-01-28T16:14:00Z
method       "bounded"      ensemble_runs 50      abstain false
peak cell    row 53, col 79  →  (80.6662, 13.7484)
mass         3,967 cells above 0.05 of peak · 1,321 cells above 0.5
```

### Measured properties of the answer
| Quantity | Value | How measured |
|---|---|---|
| Slick → origin distance | **47.8 km**, bearing **025°** | seed centroid to ensemble centroid |
| Control run median displacement | 48.4 km over exactly 24.00 h | per-particle, control run |
| Ensemble centroid vs control endpoint | **0.095 km** | the stratification check |
| Endpoint distance from centroid | p50 8.78 · p90 17.30 · p99 24.02 · max 30.79 km | 150,000 endpoints |
| Cloud shape (principal axes) | sd **10.76 km × 2.46 km**, aspect **4.38 : 1** | PCA on the endpoint pool |
| High-probability extent (cells ≥ 0.5 of peak) | 30.0 km N–S × 21.8 km E–W | grid |
| High-probability cells outside the r50 circle | **44.7%** | grid vs circle |
| Grid mass outside the SAR scene footprint | **98.1%** | grid vs `bounds.json` |
| Endpoints outside the SAR scene footprint | **98.4%** | 150,000 endpoints |
| Origin box north edge above the scene | **46.6 km** | 13.968 vs 13.550 |
| Control particles crossing the top of the scene | first at frame **45** (11.2 h) · median at frame **65** (16.2 h) · all by frame **85** (21.2 h) | control run |

> *Reconciliation note:* the frontend brief quotes "42.4 × 9.9 km, aspect 4.3 : 1, 49% outside r50, 85% outside the scene". Those used a different high-probability threshold and counted cells rather than mass. The numbers above state their definition explicitly. Both sets support the same conclusions: **the cloud is a streak, not a circle, and it is almost entirely outside the satellite image.**

### Is the direction right?
Yes, and this is the physical sanity check that matters most. The current at Ennore runs **south** along the Coromandel coast (East India Coastal Current, January NE monsoon). Rewinding 24 hours therefore has to travel **north — upstream**. The origin sits at bearing 025° from the slick, north-east and offshore. If a render ever puts the origin *downstream* (south-west, below the slick), something is flipped.

### Validation
```
python scripts/validate_case.py cases/<case>
→ PASS  acts=['detect','trace','attribute']  (0 warnings)
```
The first Stage 2 output with **zero** warnings — the Phase 1 warning `only 1 ensemble runs; uncertainty will look fake` is gone now that there are 50.

The validator independently checks, among ~40 rules: `t0` agrees with `meta.detection_time`; `n_steps` agrees with the actual frame count; particles are never added or dropped mid-run; every coordinate is in range and not lat/lon-swapped (it explicitly detects the swapped case); particle 0's displacement is physically bounded; the grid length matches `shape`; values are non-negative and peak at 1.0; `time_window` is ordered; `r50 ≤ r90`; and `abstain` agrees with the 40 km rule.

---

## 12. How accurate is this, honestly

This is the section to read before anyone puts a number on a slide.

### What we can defend
1. **The integrator is exact against known answers.** 18.0000 km against 18.0 km expected — 0.000% error. A 24 h forward-then-backward round trip through a varying field closes to **0.0001 km**. RK2 truncation error is not a meaningful contributor at 15-minute steps.
2. **The uncertainty is measured, not assumed.** r50 = 8.78 km and r90 = 17.30 km are percentiles of 150,000 actual ensemble endpoints, not a fitted gaussian and not a guess.
3. **The perturbation budget is sourced.** The 2.5–3.5% wind band is the literature range; the 15% current spread is the stated magnitude of the daily-HYCOM blindness; the ±300 m seed jitter is the detector's own edge uncertainty.
4. **The ensemble does not bias the answer.** Pooled centroid sits 95 m from the control endpoint (§6.2).
5. **The direction is independently corroborated** by the East India Coastal Current under the January monsoon.

### What we cannot claim, and will not
- **There is no ground truth.** Nobody has told us where the Ennore oil actually entered the water at what hour. So there is **no validation error in kilometres**, and any statement of the form "accurate to within X km" would be fabricated. What r50 = 8.8 km means is: *"across the 50 runs of our uncertainty budget, half the endpoints landed within 8.8 km of the cloud's centre."* It is a precision statement, not an accuracy statement.
- **Absolute accuracy is bounded by HYCOM, not by us.** A ~9 km, once-daily model of a coastal current is the floor on how well anyone can do this from free data.
- **The current numbers are not an Ennore claim** — the ocean is real, the slick is `case-000`'s invention (§10.2).
- **The time window is a bracket, not a measurement** (§8).

### Error budget — where the uncertainty actually comes from

| Source | Rough magnitude over 24 h | Carried by | Notes |
|---|---|---|---|
| **HYCOM temporal resolution (daily)** | dominant | current × N(1, 0.15) | Only 2 snapshots, 24 h apart, across the whole rewind. Sub-daily eddies are invisible. |
| **HYCOM spatial resolution (~9 km)** | large | same | Sub-mesoscale structure is unresolved by construction. |
| **Wind coefficient (3% rule)** | ~±0.5 m/s × 0.005 ≈ ±2 km over 24 h at typical 4.4 m/s winds | U(0.025, 0.035) | Small here because the winds were light. Would grow in a storm. |
| **Detection polygon geometry** | ±300 m at seed, grows with the run | seed jitter | Will be replaced by the real detector's real uncertainty. |
| **RK2 truncation at dt = 15 min** | negligible | — | Round trip closes to 0.1 m. |
| **Spherical-earth metre↔degree** | ~0.5% ≈ 240 m over 48 km | — | An order of magnitude below r50. |
| **Turbulent diffusion** | **not modelled** | — | See §14. The cloud is narrower than reality by an unquantified amount. |
| **Oil weathering / vertical mixing** | **not modelled** | — | Surface-only transport. |

### The right sentence for the demo
> *"We do not claim a point. We claim a probability cloud whose spread we measured by running the physics 50 times across the honest range of its inputs. Half our endpoints land within 8.8 km, ninety percent within 17.3 km, and we say when we cannot tighten the release time rather than inventing one."*

---

## 13. Every bug found, and how it was caught

### 13.1 HYCOM unit scaling — every current was 10× too fast ★ the big one
**What was wrong.** Six of our own documents said *"HYCOM velocity bands are cm/s — divide by 100."* That is true of the raw HYCOM NetCDF distribution. It is **not** true of Google Earth Engine's ingestion, which is what we actually query: the GEE catalog band table lists `velocity_u_0`/`velocity_v_0` as **units m/s, scale factor 0.001**. The integer `getRegion` returns is millimetres per second. The correct divisor is **1000**.

**Measured impact over the Ennore box:**

| Divisor | Median current | Max | Verdict |
|---|---|---|---|
| ÷100 (old docs) | 4.80 m/s | 10.97 m/s | physically impossible |
| **÷1000 (correct)** | **0.48 m/s** | **1.10 m/s** | a real coastal ocean |

**Why it was the dangerous kind of wrong.** Nothing would have crashed. Particles would simply have been rewound ~500 km instead of ~50 km, and the origin cloud handed to Stage 3 would have pointed at open ocean hundreds of kilometres from any real vessel track — with a perfectly plausible-looking heatmap.

**How it was caught.** By **test 4**, the permanent plausibility guard (`speed < 3 m/s`), on the very first real fetch, **before a single particle was integrated**. This is the concrete receipt for why the known-answer tests were written in Phase 1, before any data existed. It is worth one line in the demo narrative.

**Confidence.** Verified against the GEE catalog band table, not inferred from plausibility alone — and independently corroborated by the corrected field flowing south along the Coromandel coast at 0.3–1.1 m/s, which is the East India Coastal Current under the January NE monsoon.

**Propagated to:** `docs/TRAPS.md` #2, `docs/team/anushka-stage2-drift.md`, `SETUP_ANUSHKA.md`, the per-directory `CLAUDE.md` files, `docs/operations/prompting-playbook.md`, `docs/receipts.md` (judge-facing), root `CLAUDE.md`, `pipeline/drift/CLAUDE.md`, `check_gee.py`, `fields.py`.

### 13.2 A case that did not exist silently got another case's ocean ★ the second big one
**What happened.** Running `--case case-gulf-2019` before that bundle existed made both `check_gee.py` and `fetch_fields.py` fall back to hardcoded Ennore defaults, download **January 2017 Bay of Bengal** water, and cache it as `data/fields/case-gulf-2019.npz`. Everything printed PASS. The field statistics looked like a real ocean — because they were one.

**Why it was dangerous.** Nothing in the cache revealed the swap: `fetch_fields.py` writes `case_id = <whatever you typed>`, so the file said "case-gulf-2019" inside as well as outside. Had the real Gulf bundle landed a day later, the cache would already have been there, `--force` would never have been passed, and Stage 2 would have rewound a Gulf of Mexico slick through Coromandel currents from seven years earlier — and handed Stage 3 a perfectly plausible origin cloud. No crash, no NaN, no warning.

**Fixed three ways:**

| Fix | File | Behaviour now |
|---|---|---|
| A named case must exist | `check_gee.py` (`load_case_window`) | Missing `meta.json` is a hard stop naming the directory. Ennore defaults survive only for `check_gee.py` with no `--case`, which is an auth smoke test |
| The cache must prove it belongs to the case | `fields.py` (`load_case_field`) | Re-derives box and time from `meta.json` + `bounds.json`; refuses a cache whose `t0` differs by > 60 s or whose bbox does not contain the scene. Also catches a **stale** cache after a scene or `detection_time` change |
| Fail before the network, not after | `fetch_fields.py` | Case resolved before `ee.Initialize()`, so a typo costs a second instead of an auth round trip |

**Verified by forging bad caches** (§10.4), not by reasoning about them. Tests stayed 5/5, and the real run still reproduces `origin (80.6210, 13.6997) r50 8.78 r90 17.30` exactly — the guards add no drift.

### 13.3 Ensemble sampling bias — 1.4 km of "physics" that was a sampling artefact
50 independent draws from N(1, 0.15) landed with a realised mean ~3% fast, pushing the entire origin cloud 1.4 km further from the slick than warranted. Fixed by stratified sampling; the offset is now 0.095 km. Full detail in §6.2. **No test would have caught this** — every individual draw was legitimate. It was caught by checking the realised moments against the claimed ones.

### 13.4 Member banding in the raw histogram
With a linear slick, 50 members produce 50 near-parallel ridges in the raw 2D histogram — an artefact of having 50 samples, which would have told Stage 3 to prefer meaningless stripes. Fixed with a scale-derived KDE bandwidth (§7.3), documented as a display-only choice that touches no reported number.

### 13.5 The 24 h fencepost — 96 vs 97 stored positions
`n_steps: 96` gave a rewind of 23.75 h, not 24 h. Resolved jointly with Akshat (commit `278f463` on `main`): `n_steps` is now **97**, and the rule *"duration is always (n_steps − 1) × timestep_minutes; never hardcode a frame count"* is written into `CONTRACTS.md` §5, `integrate()`'s docstring and the frontend brief.

### 13.6 `plot_quiver.py` read the wrong property key
It filtered detections on `"class"` instead of `"classification"` — the only place in the repo that did. Because `.get()` defaulted, the filter passed *every* feature and the plot outlined whichever detection had the highest confidence overall. Correct on `case-000` by luck (the oil feature also has the highest confidence). Fixed.

### 13.7 A leftover "divide by 100" line printed after the correction
`check_gee.py` printed *"Divide by 100 in the loader, once."* immediately after the corrected sentence saying to divide by 1000 — the unit correction had missed the trailing line. It printed on **every preflight PASS**, and it is the single sentence most likely to be copied by someone in a hurry. Removed. (`docs/receipts.md`, the judge-facing file, was already correct.)

### 13.8 Phantom CRLF modifications to `cases/case-000/`
Three JSONs showed as modified but were byte-identical apart from line endings, which something on Windows had rewritten to CRLF against `.gitattributes` (`* text=auto eol=lf`). Reverted; nothing lost. **If they reappear, find out which tool is rewriting line endings — it will keep doing it.**

### Swept and confirmed clean
No naive datetimes anywhere · no exception handlers that swallow errors · the ÷1000 correction fully propagated including to judge-facing docs · no NaN leaks from land cells (verified by a 60×60 sweep over the whole box, all finite).

---

## 14. Limitations — what this model does not model

Every one of these is a deliberate choice with a reason, and each should be said out loud rather than discovered by a judge.

| Limitation | Consequence | Why it stands |
|---|---|---|
| **HYCOM on GEE is daily** — only 2 snapshots across a 24 h rewind | Sub-daily eddies invisible; the cloud translates instead of converging, which is why the time window is bounded | It is the free data that exists. The ensemble's current × N(1, 0.15) is what carries this ignorance rather than hiding it. |
| **~9 km current grid, ~28 km wind grid** | Sub-mesoscale structure unresolved | Same. |
| **No turbulent diffusion** | The cloud is narrower than physical reality by an unquantified amount | Our spread comes from *parameter* uncertainty, which is defensible. A diffusion coefficient we could not source would be an invented number widening an honest one. |
| **Surface only, no vertical mixing** | Oil that submerges and resurfaces is not tracked | Correct for a 24 h fresh-slick rewind. |
| **No weathering, evaporation or emulsification** | The parcel is treated as a passive tracer | Needs oil-type data we do not have. |
| **No Stokes drift term** | — | Absorbed into the empirical 3% wind coefficient, which is what it is for. |
| **Bilinear space / linear time interpolation** | Smooths real gradients | Appropriate to the source resolution; a fancier scheme would be false precision on a daily field. |
| **Spherical earth** | ~0.5% metre↔degree error | ~240 m over 48 km, an order of magnitude below r50. |
| **Beached particles are held, not resuspended** | A slick that reaches land stops there | Honest: the model cannot say where a beached slick came from. |
| **Fixed 24 h rewind horizon** | Older releases are not reachable | Scoped for the demo; the horizon is a CLI flag, not an assumption in the code. |
| **No ground-truth validation** | No accuracy figure in km | Nobody published where the Ennore oil entered the water. Stated, not papered over. |

---

## 15. Risk register — what I expect to go wrong next

Ordered by expected damage. "Silent" means it produces a plausible wrong answer rather than an error.

### R1 — The field box is padded by a constant, and a fast current will run out of ocean · **HIGH · silent**
`check_gee.py` pads the case bounds by a fixed **0.5° ≈ 55 km** to decide how much ocean to download. When a particle drifts past the edge of the downloaded grid, the interpolator **clamps its coordinates to the boundary and keeps feeding it the edge velocity** — the particle slides along the wall and the origin cloud piles up against it, looking entirely plausible.

```
Ennore, measured:    closest control-run particle   26.6 km from the north edge
                     closest ensemble endpoint      11.6 km from the north edge   ← survived, but not by much
Gulf Loop Current:   1.8 m/s  →  156 km in 24 h   against a 55 km pad
Gulf Stream:         2.0 m/s  →  173 km in 24 h
```
**Fix (~30 min, entirely inside Stage 2's files):** derive the pad from the region's own p99 current speed instead of a constant, and add a permanent guard that **fails loudly** if any particle finishes near the box edge. **Needs a ruling** because it is new code and rule 5 says freeze means freeze — cheap and safe now, neither on Thursday. If the US case is not happening, this work is unnecessary.

### R2 — Stage 3 scores an elongated cloud with circles · **HIGH · silent · not my lane**
`pipeline/attribute/run.py` ranks suspects by distance from the origin **centroid** (`dist <= radius_50_km` → *"inside the 50% origin radius"*). Correct for a round cloud. Measured on the real one: aspect **4.38 : 1**, and **44.7% of the high-probability cells fall outside the r50 circle**. So the current rule will name vessels sitting in near-empty water inside the circle and exclude vessels sitting in the bright streak just outside it.

The radii themselves are correct and should stay — they are the honest one-number summary for the UI and the deck. They are simply the wrong instrument for a membership test.

**Fix, and it is small:** sample the 120×120 probability grid at the vessel's position instead of testing circle membership. The grid, its bounds and its orientation are all already in `origin.json`. **This changes Jaiveer's scoring *method*, not a bug in his code**, and he wires it Thursday — so it needs a direct message from you, not a patch landing in his lane from mine.

### R3 — The frontend renders the answer in the wrong place · **HIGH · silent**
Four documented ways a reasonable frontend gets this wrong without erroring:
1. Framing the map camera to `bounds.json` → **98% of the answer is off-screen** (measured). The camera must fit the *union* of `bounds.json`, the particle extent, and `origin.json.bounds`, with padding. Never clip a layer to the SAR footprint.
2. Georeferencing the grid with `bounds.json` instead of **`origin.json.bounds`** → right picture, wrong place. The two overlap by only ~15%.
3. Flipping row order → an upside-down cloud that validates cleanly and looks plausible. Row 0 is NORTH; the bright part of the Ennore cloud should sit toward the **top-right** of its own box.
4. Feeding a finished raster to deck.gl's `HeatmapLayer` → that layer consumes **point** data and computes its own density, throwing away our 150,000-endpoint answer and re-deriving a worse one in the browser. The right layer is **`BitmapLayer`** from a 120×120 canvas, with **alpha proportional to value** (a hard alpha cutoff leaves a fringe of just-above-threshold cells that reads as a second, non-existent cloud — this happened in our own plots).

`web/CLAUDE.md` currently names `HeatmapLayer`, and it is a per-directory file, so Harshita's AI re-reads that wrong guidance at the start of every session. One line, five minutes — her file, so I have not touched it. Full rendering recipe is in `docs/STAGE2_FOR_FRONTEND.md`.

### R4 — First contact with Stage 1's real detections · **MEDIUM · loud, probably**
Stage 2 has only ever seeded from `case-000`'s invented polygon. When the real `detections.geojson` lands, the untested paths are: a **blob**-class slick, a polygon with a very different vertex count or winding, a degenerate ring, and `area_km2`/geometry disagreement (R7). The seeding code is defensive, but "never executed" is never "known good". **Mitigation:** re-run `tests.py` plus the full `--real` run immediately on arrival, and *look at the quiver and heatmap pictures* before believing any number.

### R5 — The verified Ennore scene changes the ocean · **MEDIUM · now guarded**
`case-000`'s `scene_id` is literally `"FAKE-000"` and its `detection_time` is a placeholder. That timestamp selects which HYCOM and ERA5 slices get used, so **a different verified scene means a different ocean and a different origin**. Until the scene lands, Stage 2 cannot pin its answer. The stale-cache guard (§13.2) now catches this — it will refuse a cache fetched for the old time — but it means a refetch, a rerun, and new numbers on every downstream slide.

### R6 — The US case fights us in three specific ways · **MEDIUM**
1. **HYCOM's GEE archive ends 2024-09-05** and Sentinel-1 GRD starts 2014-10-03, so a usable case must fall in **Oct 2014 – Sep 2024**. The 2024 ceiling is the easy one to trip over because it feels recent.
2. **Negative longitude.** Ennore at 80°E is identical in both longitude conventions, so a 0…360 leak would stay invisible until the Gulf. Wrapping is centralised in one function, but this is its first real exercise.
3. **Fast currents** — see R1.
**Mitigation:** re-run `check_gee.py` against the US box and dates *before* anything else; escalate at 45 minutes per rule 3.

### R7 — `area_km2` disagreeing with its own polygon · **MEDIUM · silent · Stage 1's file**
`case-000`'s `det-01` already disagrees with itself: the ring spans ~21 km while `area_km2: 12.4` with `elongation: 8.2` implies ~10 km. Stage 2 seeds from the **geometry**, which is correct. But if the real detector computes area from one mask and exports a polygon from another, Stage 2 silently seeds the wrong length of slick. **Proposed:** shoelace the ring in `validate_case.py` and warn past roughly a 2× disagreement (a polygon is often a simplified outline of a ragged mask, so 20% is normal and 200% is a different mask). **Not yet implemented** — see §17, decision 2.

### R8 — `abstain: true` has never been produced on real data · **LOW-MEDIUM**
Ennore is comfortably `false` (r90 17.3 km against a 40 km threshold). The refusal state is a designed feature we want to show off, but the frontend must **force the flag by hand** to build and test that screen. If a real case ever does abstain, that will be the first time the path runs for real.

### R9 — The no-spill path has never run end to end · **LOW**
`pick_slick()` returns `None` and `run.py` exits with a clear message. Correct behaviour, never exercised as part of a real bundle.

### R10 — Single laptop, single environment · **LOW but total if it fires**
Everything lives on one machine. Mitigations already in place: the branch is pushed, the field cache is small (18 KB) though gitignored, the run is deterministic at `--seed 143`, and it reproduces identically on Linux/3.10 and Windows/3.11. Mitigation to add: the `/cases/` zip to Drive at end of day, per Master §7.

### R11 — GEE auth or quota fails at the wrong moment · **LOW · loud**
`check_gee.py` is the preflight, and everything downstream reads from a **local cache**, so a GEE outage cannot break a rerun of an already-fetched case. It can only block a *new* case. 45-minute rule applies.

### R12 — Dependency drift · **LOW**
`requirements.txt` pins the versions. Stage 2 needs only NumPy (plus matplotlib for the two pictures) — the gaussian blur is hand-written specifically so SciPy is not required. No new dependencies after Tue 8 in the pipeline, none anywhere after the freeze.

### R13 — Housekeeping residue in `data/fields/` · **LOW · but it looks like a live cache**
Three files are sitting there from the adversarial testing: `case-000-WRONG.npz`, `case-000.npz.tmp` (both contain the *Gulf-named* forged field, bbox 79.5–81.5/12.0–14.5), and `_to_delete/case-gulf-2019.npz`. All are gitignored and none is loaded by the current code path, but a file named `case-000.npz.tmp` next to the real `case-000.npz` is exactly the sort of thing someone renames at 11pm. **Delete all three.**

---

## 16. Repository state

```
branch          anushka  →  origin/anushka   (pushed)
HEAD            fd5aaf4  Stage 2 Phase 3: 50-run backward ensemble, real origin cloud, stratified members
                8b2ee64  Stage 2 Phase 2: real HYCOM + ERA5 fields, GriddedField, quiver plot
                0c13783  Log: Phase 1 verified on Windows after rebase onto 278f463
                402acbd  Stage 2 Phase 1: RK2 drift engine, analytic fields, four known-answer tests
                278f463  (main) Fix particles.json fencepost bug: n_steps 96 → 97
```

**Uncommitted — the §13.2 silent-fallback fix, 126 insertions across 5 files:**
```
 docs/updates/anushka.md         +51
 pipeline/drift/fields.py        +44   ← the cache-vs-bundle guards
 pipeline/drift/check_gee.py     +28   ← case must exist; the ÷100 line removed
 pipeline/drift/fetch_fields.py   +7   ← resolve the case before touching the network
 pipeline/drift/plot_quiver.py    +6   ← the "class" → "classification" fix
```
**This is proven work sitting on one laptop. Committing and pushing it is the highest-value five minutes available to me right now.**

### Process drift worth naming honestly
Neither the Phase 1 nor the Phase 3 checkpoint has been posted in the group, and the plan makes posting them the definition of a phase being done. **As far as the team can see, the component that is furthest ahead has not started.** Two images are sitting in `pipeline/drift/out/` waiting: `quiver_case-000.png` (the real current field, arrows 0.3–1.1 m/s running south, land to the west, slick outlined in water) and `heatmap_case-000.png` (left: the slick, the control run rewinding, and the cloud it lands in, with the coast for scale; right: `origin.json` exactly as stored, 120×120, row 0 north, with the 50% and 90% circles).

---

## 17. Decisions I need from you

| # | Decision | Owner of the file | Cost | If we do nothing |
|---|---|---|---|---|
| 1 | Accept, move, or reject `time_window_method` in `origin.json` | Akshat (contracts) | zero — already written | An undocumented key ships to the demo |
| 2 | Add the `area_km2`-vs-polygon **warning** to `validate_case.py` | Akshat (validator) | ~30 min | A silent path into wrong seeding survives |
| 3 | Tell Jaiveer his scoring assumes a round cloud | Jaiveer (Stage 3) | his call, ~1 h | Suspect ranking is geometrically wrong on real data |
| 4 | Correct `web/CLAUDE.md`'s `HeatmapLayer` line | Harshita (frontend) | 5 min | Her AI re-derives the wrong plan every session |
| 5 | Fund the field-box pad fix before the US case | me (Stage 2) | ~30 min | A fast-current case silently pins particles to a wall |

**On decision 1:** `origin.json` carries one additive key beyond the frozen schema — `"time_window_method": "bounded" | "convergence"`. The brief (Phase 3, step 3) asks for the window to be marked when the bounded fallback is used, and the frozen schema has nowhere to mark it. The validator passes; a frontend that ignores it loses nothing. My recommendation is to bless it and add it to `CONTRACTS.md`, because it is one string, it is already produced, and it protects the claim in §8. The alternatives are to move it somewhere you prefer (a `notes` string, `meta.json`), or reject it — in which case the frontend needs an explicit instruction never to imply a measured release moment.

**On decision 2, one correction to my own earlier brief:** I previously listed *two* validator checks to add. On re-reading the file, the **`shape_class`-vs-`elongation` check already exists** (`validate_case.py`, added in `8b2ee64`) — it warns on any disagreement with the `elongation > 3` rule, though without the tolerance band I had suggested, so an elongation of 3.05 will nag. Only the `area_km2`-vs-polygon check (R7) is genuinely missing. Warnings rather than errors, deliberately: a hard error here fires at 10pm on the tightest handoff night, possibly over a marginal judgement call, and a false positive that blocks the pipeline is worse than the bug it guards against.

### The one insight behind three of these
`cases/case-000/` was built as a **contract fixture** — correct shapes, invented numbers, so everyone could build without waiting. It did that job perfectly. But people did not only build against its *shape*; they built against its *values*, and its values are physically unlike what the real pipeline produces:

| | case-000 (what three people built against) | real Stage 2 output |
|---|---|---|
| origin cloud form | compact, round | **4.38 : 1 streak** |
| where it sits | roughly over the SAR scene | **98% outside it; north edge 46.6 km above the image** |
| `radius_90_km` | 11.8 | 17.3 |
| particles | stay near the scene | **first leaves the top of the scene at frame 45 of 97 (11.2 h)** |

Nobody did anything wrong; the fixture taught a shape it was never meant to teach. Worth one line in the Wednesday integration checklist: **the first time any stage sees real upstream data, re-check the assumptions its stub baked in.**

---

## 18. Reproducing everything in this report

```bash
# once per case — needs GEE auth
python pipeline/drift/check_gee.py                              # preflight: auth, collections, bands, magnitudes
python pipeline/drift/fetch_fields.py --case case-000           # add --force to refetch
python pipeline/drift/plot_quiver.py  --case case-000           # Phase 2 checkpoint picture

# the run — about 22 s, deterministic at --seed 143
python pipeline/drift/run.py --case case-000 --real --particles 3000 --runs 50
python pipeline/drift/plot_heatmap.py --case case-000           # Phase 3 checkpoint picture
python pipeline/drift/tests.py                                  # 5/5, 20/20

# then copy out/particles.json + out/origin.json into cases/<case>/ and:
python scripts/validate_case.py cases/<case>                    # PASS, 0 warnings
```

No network is needed after the fetch — everything downstream reads `data/fields/<case>.npz`. `--fake` runs the identical integrator over an analytic ocean with no GEE at all, which is what makes this component testable on any laptop.

**Environment:** Python 3.11 (project standard; verified identical on 3.10.12), NumPy, matplotlib for the two plots. **No SciPy, no GPU, no downloads beyond an 18 KB cache file.** Determinism: `--seed 143` seeds both the Python `random` used for particle seeding and the NumPy generator used for the ensemble draws; two runs on two operating systems produced identical output to the last decimal.

**Key CLI flags:** `--case` (required) · `--real` / `--fake` (mutually exclusive, one required) · `--particles` (3000) · `--runs` (50; the cut order permits 25, and `origin.json` says which) · `--steps` (97 stored positions = 24.00 h) · `--timestep-minutes` (15) · `--seed` (143) · `--out`.

---

## 19. Definition of done — status

| Requirement (`docs/team/anushka-stage2-drift.md`) | Status |
|---|---|
| Tests 1–4 green and committed | ✅ plus test 5 — 5/5, 20/20 |
| Quiver image posted | ⬜ **produced, not yet posted in the group** |
| Heatmap image posted | ⬜ **produced, not yet posted in the group** |
| Valid `particles.json` + `origin.json` for Ennore by Tue evening | ✅ produced Sunday night, ahead of a Tuesday deadline — validator PASS, 0 warnings. **Against `case-000`'s slick, not a real detection** |
| Rerun on the US case by freeze | ⬜ blocked on the case being picked (Master §9) |

### The three things blocking a real Ennore answer — none of them Stage 2
1. **Soum's real `detections.geojson` is not in the repo.** The fields underneath are real HYCOM and ERA5 for the actual Ennore box and dates, so the physics is real — but the slick being rewound is not a detection. *The origin coordinates must not appear on a slide labelled Ennore until this lands.*
2. **The Ennore Sentinel-1 scene is unverified.** `scene_id: "FAKE-000"`, placeholder `detection_time` — and that timestamp selects the ocean.
3. **The US case is unpicked**, with the Oct 2014 – Sep 2024 window constraint above.

When 1 and 2 land, the procedure is: `fetch_fields.py --case <real-case>`, then the same run command. **Nothing in the drift code changes.** That is the whole point of the seam.

---

## Appendix A — Output schemas as actually written

### `particles.json`
```jsonc
{
  "t0": "2017-01-29T00:14:00Z",   // the detection moment
  "direction": "backward",
  "timestep_minutes": 15,
  "n_steps": 97,                  // STORED FRAMES, not physics steps
  "n_particles": 3000,
  "positions": [ /* 97 arrays, each of 3000 [lon, lat] pairs, 5 dp */ ]
}
```
`positions[0]` is **t0** — particles on the slick. `positions[k]` is at **t0 − k × 15 min**, so a *larger index is further in the past*. `positions[96]` is t0 − 24 h exactly. Duration is always `(n_steps − 1) × timestep_minutes`. Coordinates are `[lon, lat]`, which is already what MapLibre and deck.gl want — no conversion, and if something looks misplaced the bug is not the coordinate order.

### `origin.json`
```jsonc
{
  "bounds": {"west": 80.46498, "south": 13.47454, "east": 80.76801, "north": 13.96830},
  "shape": [120, 120],
  "values": [ /* 14400 floats, 0..1, row-major from top-left, row 0 = NORTH, peak exactly 1.0 */ ],
  "centroid": [80.62097, 13.69967],
  "radius_50_km": 8.78,
  "radius_90_km": 17.3,
  "time_window": ["2017-01-28T00:14:00Z", "2017-01-28T16:14:00Z"],
  "ensemble_runs": 50,
  "abstain": false,
  "time_window_method": "bounded"   // additive; see §17 decision 1
}
```
Grid indexing:
```
lat = north − (north − south) × row / (rows − 1)
lon = west  + (east  − west ) × col / (cols − 1)
```
**`bounds` here is NOT `bounds.json`.** It describes the cloud, not the scene, and the two overlap by only about 15%.

---

## Appendix B — Glossary

**SAR** — synthetic aperture radar; oil flattens waves so slicks appear dark. **HYCOM** — global ocean current model; on GEE, daily, 0.08°, archive ends 2024-09-05. **ERA5** — ECMWF wind reanalysis; hourly on GEE. **GEE** — Google Earth Engine, our single data source. **RK2** — second-order Runge–Kutta (midpoint) time integration. **The 3% rule** — surface oil moves at current + ~3% of the 10 m wind. **Ensemble** — 50 perturbed reruns; the spread *is* the uncertainty. **Stratified sampling** — one draw per equal-probability slice instead of independent draws, so the realised mean matches the claimed one. **KDE** — kernel density estimate; here, a gaussian blur of the endpoint histogram, display-only. **r50 / r90** — radii of circles around the centroid containing 50% / 90% of ensemble endpoints. **Abstention** — designed refusal when r90 > 40 km; a feature, not a failure. **Bounded vs convergence window** — whether the release time was *bracketed* or *measured*.

---

*Report compiled 2026-09-08 from `pipeline/drift/*.py`, `pipeline/drift/out/*`, `data/fields/case-000.npz`, `scripts/validate_case.py` and `docs/updates/anushka.md` at commit `fd5aaf4` + 5 uncommitted files. Figures were recomputed from the output files rather than copied from earlier notes; where an earlier document quotes a different value for the same quantity, both appear with the definition that produced each.*
