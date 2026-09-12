# Stage 2 — the numbers we will present

*Phase 8 of `03_ANUSHKA_DRIFT.md`. Anushka's lane, 13 Sept 2026. Every figure here is measured,
and the command that produces it is named. Rulings A1–A5 (Akshat, 13 Sept) are incorporated —
including the withdrawal of the four-case age claim.*

**Master §12's rule governs everything below: never a single unqualified percentage. Every number
carries its metric and its split.**

---

## 8.1 The integrator is exact

| Claim | Measured | Where |
|---|---|---|
| Constant current, 0.5 m/s east, 10 h | **18.0000 km** against 18.0 expected, **0.000%** error | test 1a |
| 24 h forward then backward, *varying* field | closes to **0.0001 km**, worst of 5 particles | test 2a |
| …and the trip was not trivial | median 16.21 km travelled outbound | test 2b |
| Same round trip at **59.56 N**, where a degree of longitude is half as wide | closes to **0.0004 km** after 21.00 km out | test 7f |
| Cross-platform | identical output on Linux/3.10 and Windows/3.11 to the last decimal | — |

**The line:** *"RK2 truncation is not a meaningful error source at 15-minute steps. We can show
that, forwards and backwards, in a field that varies."*

Worth saying once, without overclaiming: OpenDrift's default propagation scheme is Euler, with
Runge–Kutta available as configuration. We default to RK2.

---

## 8.2 Ensemble spread is PRECISION, not accuracy

`case-000`, 3000 particles × 50 members, real HYCOM + ERA5:

```
r50  8.8 km      r90  17.6 km      abstain false      150,000 endpoints
```

**Say:** *"Across the 50 runs of our uncertainty budget, half the endpoints landed within 8.8 km
of the cloud's centre."*

**Never say:** *"accurate to 8.8 km."* There is no ground truth for origin position on any case in
the library, and we will not imply one. This is the single easiest sentence in the whole project
to get wrong on stage.

The stratified sampling matters here and is worth thirty seconds: fifty *independent* draws from
N(1, 0.15) landed with a realised mean about 3% fast, which pushed the whole origin cloud 1.4 km
further from the slick than the physics warranted. Every individual draw was legitimate, so no
test would have caught it. Stratifying fixed it: the pooled centroid now sits **95 m** from the
control endpoint.

---

## 8.3 Age — an output, with no accuracy number

**The four-case validation claim is WITHDRAWN (A5, 13 Sept).** Akshat audited the library rather
than assuming: no indexed case carries a `detections.geojson`, none carries a release time, and
`discharge_class` is unset everywhere including `case-000`'s own `det-01`. Both acute-gated
estimators therefore fire on nothing today. **The claim failed on missing inputs, not on physics** —
and the gates that refuse are correct and stay.

So age ships as an output with `age_method` and the per-estimator breakdown, and **no hit rate**.

If Huntington's detection lands and C3.1 fires, we state an explicit **N = 1** with the
overestimate caveat attached — a 2.8 h old slick sits in the estimator's documented weak regime,
because gravity-viscous spreading dominates the first hours and the model omits it. That is a
result to state, not a surprise to absorb on stage.

### What the limitations slide carries instead

**The reachability ceiling.** Measured on the real Ennore field: a 200 m σ cloud stretches from
**0.79 km to 1.31 km over 24 h** — a factor of 1.66. Deformation rate at the origin is
1.36×10⁻⁵ s⁻¹ near t0, decaying to 4.79×10⁻⁶ s⁻¹ further back, so a 20–58 h shear timescale. The
shear estimator can therefore only date slicks whose major axis is about **0.8–1.3 km**. That is
not a coding limit — it is HYCOM's resolution again, the item ranked #1 in our own error budget.

**Fay's refusal, as evidence.** A 93.5 m³ release (Huntington's 588 barrels, NTSB MIR-24-01)
spreads to **0.508 km² at 24 h** and **0.880 km² even at the 72 h ceiling**, against observed
slicks of order 12 km² — off by **~14×**. Gravity-viscous spreading cannot set the area of a
SAR-detectable slick; shear and advection do. That refusal is independent evidence that the
shear estimator models the right process.

And it is robust to the one uncited constant, which is why it ships (A4): Fay's **area goes as
k²**, so closing a 14× area gap would need **k ≈ 5.5** against a literature range of 1.1–1.5. A
Fay *age band* would not survive that uncertainty; the regime verdict does. Quote a Fay age and
the citation becomes mandatory again — so we quote none.

### Three physics corrections, ratified

| | The brief said | What is correct | Consequence |
|---|---|---|---|
| **C3.1** | match the modelled cloud's **area** to `area_km2` | match the **major axis** | a 2D incompressible flow preserves cloud area — measured ×1.000 over 34 h while the major axis grew ×5.6. Matching area is fitting noise |
| **C3.3** | aspect = `sqrt(1 + (St)²)` | `St = sqrt(a + 1/a − 2)` | the brief's form is a material-**line** stretch, not a **patch** aspect ratio |
| **C3.2** | volume from `area × thickness` | volume from the **official finding** | the observed area appeared on both sides of the law |

**On C3.3, the sentence that must not be shortened.** The error is **not a 3.2× conversion
factor.** The ratio is `sqrt(a²−1) / sqrt(a + 1/a − 2)`, and it climbs with elongation:

| elongation a | 2 | 8.2 | 20 | 50 | ~168 |
|---|---|---|---|---|---|
| brief's form is too long by | **2.45×** | **3.24×** | **4.70×** | **7.21×** | **~13×** |

Every case carries its own elongation, so no age computed under the brief's form can be corrected
by dividing — each is recomputed. Jacksonville's ribbon is aspect ~168. Asserted at four
elongations in test 6e precisely so the test's own output cannot be misquoted.

---

## 8.4 OpenDrift agreement — RUN, and it lands at 118 m

`case-000`, 3000 particles, 24 h backward, **our RK2 against OpenDrift 1.14's RK4**, both fed the
*identical* cached HYCOM + ERA5 field (re-expressed as CF NetCDF, nothing regridded).

| | Measured |
|---|---|
| Distance travelled, median | **48.4 km** (ours 48.392, OpenDrift 48.430) |
| Per-particle disagreement, **median** | **161 m** — 0.33% of the path |
| Per-particle disagreement, p95 | 449 m |
| Per-particle disagreement, worst of 3000 | 958 m — 2.0% of the path |
| **Origin centroid separation** | **118 m** |
| …against our own r50 of 8.84 km | **1.3% of it** |

**What this does and does not prove.** It cannot make our answer *true* — there is still no ground
truth for origin position on any case (8.2). What it does is separate two objections that a judge
will otherwise merge:

> *"Your physics is wrong"* — an independent implementation would have diverged.
> *"Your input field is coarse"* — an independent implementation agrees to 118 m, and **both** are
> still limited by HYCOM.

The second is our position, and this is the only independent evidence we have for it. It is also
the direct measurement behind **§8.5's rank 4**: the integration scheme is not a meaningful error
source. Two different schemes, RK2 and RK4, written by different people, disagree by **two orders
of magnitude less than our own precision radius.**

**The line:** *"We ran the same field through OpenDrift's RK4. The origin moved 118 metres. Our
uncertainty is the ocean model, not our code."*

### Making it apples-to-apples — every switch, and why

OpenDrift is a much larger model, so most of its processes had to be turned **off** or the
comparison would measure somebody else's turbulence scheme against our advection:

| Setting | Value | Why |
|---|---|---|
| `general:use_auto_landmask` | False | OpenDrift ships its own GSHHG mask. A stranded particle is a *stopped* particle — two coastlines would read as a physics disagreement. Our side runs `step.integrate` with no stranding to match |
| `drift:advection_scheme` | `runge-kutta4` | **OpenDrift's default is Euler.** Comparing our RK2 to their Euler would measure two schemes, not two implementations. RK4 is the strictest available check |
| `drift:vertical_advection` | False | **defaults to True** |
| `drift:vertical_mixing`, `drift:stokes_drift` | False | we model neither |
| `horizontal_diffusivity` | 0 | random-walk diffusion would make the comparison stochastic |
| `wind_drift_factor` | 0.03 | our single empirical constant, matched exactly |

Particle identity was verified rather than assumed: **OpenDrift returns the trajectories in a
different order than seeded.** Matching by index gave a nonsense 6.1 km disagreement at t = 0 —
which is just the length of the seed line. A KD-tree match on the t0 positions is a verified
bijection, 3000/3000, with a 0.21 m residual.

### Two silent-failure traps found inside OpenDrift, worth one slide

Both are the same shape as the frozen-field bug in 8.7, and neither would have raised anything:

1. **`environment:fallback:x_sea_water_velocity` ships as `0`.** A particle outside reader
   coverage keeps integrating through a **dead ocean** — it simply stops moving and the run still
   completes and still writes output. Setting the fallbacks to `None` instead is what made our
   missing-wind problem raise an exception rather than quietly produce a wind-free trajectory and
   a large spurious disagreement with us.
2. **`reader_netCDF_CF_generic` silently truncates a file with a non-uniform final timestep.** A
   3 h pad appended to the hourly wind file moved its `end_time` from 00:00Z back to **23:00Z** —
   discarding the real last snapshot along with the pad, announced only at INFO level.

We hit both in an afternoon, on a mature and widely used model. That is the honest context for our
own guard work: this class of bug is not a beginner's mistake, it is what particle tracking is
actually like.

**Reproduce:** `/tmp/claude-0/odenv/bin/python pipeline/drift/opendrift_compare.py`
(OpenDrift is NOT added to `requirements.txt` — it pulls ~90 packages including Cartopy and
netCDF4, and it is a comparison tool, not a runtime dependency. `opendrift_compare.py` is
committed so the number is reproducible; the venv is not.)

---

## 8.5 The error budget

| Rank | Source | Weight |
|---|---|---|
| 1 | **Current field resolution** — 9 km | dominant, by a wide margin |
| 2 | Wind coefficient uncertainty, 2.5–3.5% | second |
| 3 | Omitted physics (vertical mixing, weathering) | third, and only beyond ~48 h |
| 4 | Numerical integration scheme | negligible at our timescales |

**One correction to Master §B2, and it is in our favour.** §B2 says HYCOM on GEE is *"one snapshot
per day."* True for Ennore 2017 — its cache held two daily snapshots. **Jacksonville's cache holds
ten, at three-hour spacing.** So cadence varies by case and era, and on the hero case the dominant
term is smaller than documented. It also means the convergence time-window estimator, which failed
on Ennore *because* daily data has no temporal structure to squeeze a cloud with, **may fire** —
turning `time_window_method: "bounded"` (a search bracket, and our weakest defensible claim) into
`"convergence"` (a measurement). Check per case; assume neither.

**The line:** *"Our uncertainty is a property of the freely available current field, not of our
code. A finer regional model would tighten it, and that's the roadmap."*

---

## 8.6 The ÷1000 story — thirty seconds, and the best evidence we test properly

GEE serves `HYCOM/sea_water_velocity` as a scaled integer: catalogue units m/s, scale factor
0.001. Six of our own documents said ÷100. A permanent plausibility guard (`speed < 3 m/s`) fired
on the **first real fetch, before a single particle was integrated.**

Then the part that actually matters: the fix was corroborated *physically*. The corrected field
flows south along the Coromandel coast at 0.3–1.1 m/s, which is the East India Coastal Current
under the January north-east monsoon. Not just "the number is small enough" — "it is the right
ocean."

---

## 8.7 Failures are loud — five guards that did not exist on 10 September

This is the Stage 2 story worth telling beyond any single number: **the uncertainty is measured,
and the failure modes are loud.** Every one of these was built because the silent version had
either already happened or was about to.

| Guard | The silent failure it replaces | Measured |
|---|---|---|
| **Field-box edge** | particles run out of ocean, slide along the grid wall and produce a plausible wrong cloud | case-000 clears by **11.5 km**; Jacksonville's p99 of 1.881 m/s reaches 162 km in 24 h against an old fixed pad of about **48 km** at that latitude |
| **Field time coverage** | a step past the last snapshot re-uses it — current and wind measured **bit-identical at t0, +6 h, +12 h, +24 h**, so a forward run was a frozen-snapshot extrapolation | refuses at >5% of span; tolerates and *reports* the routine 0.23 h overhang |
| **Candidate-age coverage** | age candidates beyond the cache silently flatten the extent curve | dropped 6 of 18 candidates on case-000, taking monotonicity failures from 20/20 to 5/20 |
| **Cross-case plotting** | one case's cloud rendered under another's name — a leftover **Ennore** cloud was written as `heatmap_case-jacksonville-2024.png`, **160 degrees of longitude** apart, and nothing tripped | refuses on a `t0` mismatch (§6.4) or an out-of-region centroid |
| **Coastline stranding** | a beached particle held at zero velocity is indistinguishable from one in slow water, and contributes an ordinary-looking endpoint | GSHHG at ~1 km; **1.36%** stranded on case-000, reported as `stranded_fraction` |
| **Drift mix** (6th, 13 Sept) | a wind-dominated origin is indistinguishable from a flipped sign, and the two have opposite remedies — Alaska rewinds *opposite* the current atlas and nothing said why | `wind_share` in `origin.json`; **23%** on case-000, **81%** on Alaska's field; warns at ≥50% |

**Test suite: 11 suites, 70 assertions, green.** Including four that exist only to pin down where
the implementation had to depart from the brief, so a departure is testable rather than a comment
nobody reads.

**One artefact a judge will point at, so have the answer ready.** The origin heatmap for
`case-000` shows a small second bright spot **on top of the slick**, separate from the main cloud.
It is real and it is explained: `case-000`'s own slick polygon overlaps the coast, so **1.20% of
the 3000 seeds start on land**, strand immediately, and are held at their seed position for the
whole rewind. They land in the grid as a tight, therefore bright, knot.

Quantified rather than waved away — removing every endpoint within 1 km of its nearest seed point
(1.36% of 150,000, matching `stranded_fraction` exactly) moves the answer by:

| | centroid | r50 | r90 |
|---|---|---|---|
| as shipped | (80.6187, 13.6952) | 8.84 km | 17.64 km |
| stuck mode removed | (80.6225, 13.7011) | 8.69 km | 17.21 km |
| **change** | **0.77 km** | **−0.15 km (1.7%)** | −0.43 km |

So it is immaterial at the same order as the coastline upgrade's 0.53 km, and it is *flagged* —
`stranded_fraction: 0.0136` is in `origin.json` precisely so this is visible rather than inferred
from a picture. The honest sentence is *"1.4% of our particles never left the beach, we report that
number, and removing them moves the origin 770 metres against a precision radius of 8.8 km."*

Two stability checks worth quoting, because they show the upgrades did not quietly move the answer:
the GSHHG coastline moved case-000's origin **0.53 km**, and replacing the principal-axis finder
with PCA moved it **0.02 km** — both against an r50 of 8.8 km, and both with a fixed seed so the
shift is attributable rather than sampling.

---

## 8.8 The direction check — and the case where the brief's oceanography does not apply

Phase 5.3 calls this *"the single most effective check you have, because a wrong origin looks
exactly like a right one."* Run on all six fetched caches. Drift sampled at the scene centre,
`current + 0.03 × wind`, averaged over the 24 h rewind window.

| case | current | wind | 0.03×wind | wind share | **origin** | brief predicted |
|---|---|---|---|---|---|---|
| `case-jacksonville-2024` | 1.688 | 1.74 | 0.052 | **3%** | **SSW 199°** | SW ✅ |
| `case-farallones-2023` | 0.247 | 5.19 | 0.156 | 39% | **N 359°** | N ✅ |
| `case-huntington-2021` | 0.073 | 1.06 | 0.032 | 30% | SE 136° | deliberately unclear |
| `case-gulf-alaska-2023` | 0.041 | 5.73 | 0.172 | **81%** | **W 265°** | E ❌ |
| `case-mumbai-2023` | 0.149 | 2.52 | 0.076 | 34% | NNW 337° | ? |
| `case-jamnagar-2024` | 0.081 | 3.86 | 0.116 | 59% | NW 312° | ? |

**Gulf of Alaska is not a flipped sign, and the code is not wrong.** The brief predicted an origin
to the east because the Alaska Current runs west. That current is *not in the field at this scene*:
its 24 h mean is **0.041 m/s** — 3.5 km/day, indistinguishable from still water — and its
instantaneous direction wanders N → NNE → NW → NNW across the window with no preferred heading.
What sets the answer is a **persistent easterly 4.2–6.5 m/s wind, holding E/ESE at every one of nine
3-hourly samples**, contributing 81% of the drift vector. A basin-scale current climatology does not
predict a 9 km HYCOM cell on one afternoon. **Verify with Akshat before the deck: the prediction and
the measurement are answering different questions, and the measurement is the one we ship.**

### The wind coefficient decides Alaska's answer — but its calibration does not

| | k=0.000 | k=0.025 | k=0.030 | k=0.035 | swing across the ensemble range |
|---|---|---|---|---|---|
| `case-jacksonville-2024` | SSW 199° | SSW 199° | SSW 199° | SSW 199° | **0°** |
| `case-farallones-2023` | NNE 16° | N 1° | N 359° | N 357° | **2°** |
| `case-huntington-2021` | ESE 110° | SE 132° | SE 136° | SE 141° | **5°** |
| `case-gulf-alaska-2023` | S 183° | W 262° | W 265° | W 267° | **3°** |
| `case-mumbai-2023` | N 356° | NNW 339° | NNW 337° | NNW 335° | **2°** |
| `case-jamnagar-2024` | NNW 330° | NW 314° | NW 312° | NW 311° | **1°** |

This is the reassuring half. Across U(0.025, 0.035) — the honest range the ensemble already samples —
**the origin direction moves by at most 5° on any case.** Dropping the wind term entirely swings
Alaska by **82°** and Huntington by **26°**. So on the wind-dominated cases it is the *existence* of
the 3% term that decides the answer, not its calibration, and the ensemble's spread is not hiding a
directional coin-flip.

### Two cases cannot carry a direction claim

Sampling the same field at t0 instead of over the window:

| case | t0 instant | 24 h mean | disagreement |
|---|---|---|---|
| `case-jacksonville-2024` | SSW 200° | SSW 199° | **1°** |
| `case-farallones-2023` | N 359° | N 359° | **0°** |
| `case-gulf-alaska-2023` | WSW 248° | W 265° | 17° |
| `case-mumbai-2023` | NW 318° | NNW 337° | 18° |
| `case-jamnagar-2024` | N 1° | NW 312° | **49°** |
| `case-huntington-2021` | W 279° | SE 136° | **143°** |

**Huntington reverses.** A single point sample says the origin is west; the window mean says
south-east. At 0.073 m/s current in a bay that is **53% land**, there is no direction to claim — which
makes it the honest case for the coastline guard (D7) and stranding, and *not* a case to show a
heatmap arrow on. Jamnagar's 49° is the same effect, milder.

**Consequence for §8.5's error budget.** The ranking — current resolution #1, wind coefficient #2 —
holds averaged over the library and on the hero case, where wind is 3% of Jacksonville's drift. It
**inverts** on Alaska and Jamnagar, where the current field is too weak to resolve anything and the
wind is effectively the whole signal. Quote the ranking as a library average, not a per-case law.

**Only Jacksonville and Farallones are direction-stable enough to put a bearing on a slide** (1° and
0° across sampling, 0° and 2° across the coefficient range). Both match their prediction.

### Reproducing 8.8

```bash
python pipeline/drift/plot_quiver.py --case <id>     # the field, per case
```

---

## The demo sentence

> *"We don't claim a point. We claim a probability field whose spread we measured by running the
> physics fifty times across the honest range of its inputs — and we say when we can't tighten the
> release time rather than inventing one."*

## Reproducing every number here

```bash
python pipeline/drift/tests.py                                    # 8.1, and every guard
python pipeline/drift/run.py --case case-000 --real --particles 3000 --runs 50   # 8.2, 8.7
python pipeline/drift/age.py  --case case-000 --real              # 8.3
python pipeline/drift/plot_quiver.py  --case <id>                 # 8.6, the right ocean
python pipeline/drift/plot_heatmap.py --case <id>                 # the cloud, per case
```

## Still outstanding before the deck is final

- ~~**8.4** OpenDrift agreement~~ — **DONE**, 118 m on case-000
- **8.2** should be restated on a real case once Soum's detections land; today's r50/r90 are
  `case-000`'s synthetic slick over a real ocean, and that must be said if it is quoted
- **8.3** the N = 1 age line, if and only if Huntington's detection arrives and C3.1 fires
