# Stage 2 — Trace

**Question:** where and when did this oil enter the water?

**In:** `detections.geojson`, HYCOM currents and ERA5 winds (via Google Earth Engine)
**Out:** `particles.json`, `particles_forward.json`, `origin.json`
**Code:** `pipeline/drift/` · **Brief:** [`../team/anushka-stage2-drift.md`](../team/anushka-stage2-drift.md)

```bash
python pipeline/drift/run.py --case <case-id>
```

---

## The idea

A slick on the sea surface is not where it was released. It has been pushed by currents and wind
for hours. Run that transport **backwards in time** from the observed polygon and the particles
converge on where they started.

**The output is a probability cloud, never a point.** The inputs have real uncertainty — HYCOM
cells are ~9 km, ERA5 is coarser still, and the windage coefficient is an approximation — so a
single back-trajectory would be a false claim of precision. The honest object is a normalised
probability grid with r50 and r90 radii, and that is what `origin.json` carries.

This is the half of the problem operational systems do not do. INCOIS tells the Coast Guard where
the oil is going; the same physics run in reverse tells them where it came from.

---

## The model

Production is a **reduced-order surface advection model**, written in-house:

```
velocity = current + 0.03 × wind
```

- **RK2** integration, **15-minute** steps, backward via negative `dt`.
- **50-member stratified ensemble**, perturbing the inputs across their uncertainty.
- Grid row 0 is **north**; values normalised to peak 1.0.

`duration = (n_steps − 1) × timestep_minutes`. 97 steps × 15 min is exactly 24 h — the frame count
is never hardcoded (decision D13), because `positions[n_steps−1] = t0 − (n_steps−1)×dt` and an
off-by-one here silently misstates the window on stage.

### Why not OpenDrift

OpenDrift (MET Norway's operational tool) is run as a **second opinion**, not as production, and
neither model is switched to at a threshold (decisions D5, D6).

Both clouds are computed and rendered. Where they agree, that is independent confirmation from an
operational tool. Where they diverge, the *pattern* of divergence diagnoses which physics accounts
for it. `origin.json` carries the comparison as `opendrift_comparison`.

The case for keeping the in-house model in production is specific: it is validated (five suites,
exact to 0.000%), the **stratified ensemble is the product** while OpenDrift gives one trajectory
per run, two downstream consumers depend on its output format, and — the argument that actually
decided it — writing every line meant the author's own guard caught a 10× unit error before a
single particle moved.

A threshold-based hybrid was explicitly rejected: the switch point is indefensible without
crossover validation, a particle cannot know its future position, and a cloud stitched from two
models is not a coherent uncertainty statement.

OpenDrift is deliberately not in `requirements.txt` — see `pipeline/drift/requirements-opendrift.txt`.

---

## What `origin.json` says, and what it does not

| Field | Meaning |
|---|---|
| `values` + `shape` + `bounds` | The probability grid. `shape` is `[rows, cols]`, row 0 north, `values` row-major from top-left, normalised to peak 1.0. |
| `centroid`, `radius_50_km`, `radius_90_km` | Summary geometry of the cloud. |
| `time_window` + `time_window_method` | When the oil entered the water. |
| `age_hours`, `age_method`, `age_estimators` | Slick age, and which estimators produced it. |
| `wind_share` | Fraction of ensemble drift displacement contributed by the windage term. |
| `stranded_fraction` | Share of particles that hit land. |
| `abstain` | If true, Stage 3 must return zero suspects. |

Three of these carry a claim that is easy to overstate, so each is constrained by the contract:

**`time_window_method`** is `bounded` or `convergence`. **`bounded` means a search bracket, not a
measured release time**, and the frontend is required to render the two differently (decision
D12). A bracket displayed as a measurement is a fabricated precision.

**`wind_share`** is a fraction in [0, 1], never a percent. It says which input the origin actually
rests on — a current-driven case and a wind-driven case are different kinds of claim. It is
**omitted, never zeroed**, when the field is synthetic, because a `0` would assert a calm nobody
measured. This is the `null ≠ 0` rule in its most concrete form.

**`age_hours`** is a range from up to three independent estimators (shear, Fay spreading,
elongation), and `age_method` can be `disagreement` — a first-class outcome, not a failure. Age
matters because it is a *filter*: bounding a slick at 6–18 hours rather than 0–72 shrinks the
suspect pool by roughly an order of magnitude. Reasoning:
[`../research/age-engine-brief.md`](../research/age-engine-brief.md) and
[`../evaluation/stage2-age-decision-brief.md`](../evaluation/stage2-age-decision-brief.md).

### One trace per case, not per detection

A case with several `oil` features still has exactly one `particles.json` and one `origin.json`
(decision D35). Stage 2 chooses the seed: all oil features merged into one ribbon when the ribbon
metrics pass every gate, otherwise the single highest-confidence feature. Which feature seeded it
is written into `meta.notes`, so the choice is on the record rather than silent. Selecting a
different detection in the interface does not change the trace.

### Abstention

`abstain: true` forces Stage 3 to return zero suspects. The agreed trigger is
`radius_90_km > 40` — a cloud that large does not constrain anything, and searching it would
produce a ranked list that means nothing.

---

## Scoring the grid, not the circle

Stage 3 scores vessel positions against **the probability grid**, not against the r50 circle
(decision D8). The clouds are not round: a measured case ran 4.38:1 in aspect with 44.7% of its
high-probability mass outside r50. A circular proxy would exclude nearly half the evidence and
include a lot of empty water.

The same reasoning drives decision D36 in Stage 3: `closest_km` is measured to the **grid peak**,
not to the centroid.

---

## Coastline

Near shore, a land mask derived from the velocity field's own validity is ~9 km — too coarse
inside San Pedro Bay or off Mumbai, where cells are partly land. GSHHG shoreline at ~1 km replaced
it (decision D7), via the `global-land-mask` package, chosen over cartopy specifically because it
is 2.6 MB of pure numpy rather than a GEOS/PROJ install on six laptops.

`stranded_fraction` reports the share of particles that beached.

---

## Traps specific to this stage

- **HYCOM on GEE is a scaled integer — divide by 1000.** Skip this and currents come out in the
  thousands of m/s, which is obviously wrong; get it half right and they are merely plausible and
  wrong.
- **ERA5 wind is u/v components, not speed/direction.** Treating u as speed produces a drift that
  runs at a confident, consistent, incorrect angle.
- An ocean current is not 90 m/s. A ship does not move 1,800 km in a day. Plot one concrete thing
  and ask whether a physical object could behave that way.

Full list: [`../TRAPS.md`](../TRAPS.md).

## Validation

The model's own test suites live alongside the code: `pipeline/drift/tests.py`, `geo_tests.py`,
`mix_tests.py`, `coast_tests.py`, `forward_tests.py`, `branch_tests.py`, `age_tests.py`.
`compare_opendrift.py` produces the second-opinion comparison — **it proves the physics
implementation, not the answer.** There is no ground truth for origin position on any case in the
library, and no figure here should be presented as though there were.
