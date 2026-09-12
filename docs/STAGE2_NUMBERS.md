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

## 8.4 OpenDrift agreement

**Not run.** Tier 1 commits to one case; it is Phase 7 for a reason — last, and droppable (F7).
If it does not happen we say we ran out of time rather than shipping a half-done comparison.

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

**Test suite: 10 suites, 65 assertions, green.** Including four that exist only to pin down where
the implementation had to depart from the brief, so a departure is testable rather than a comment
nobody reads.

Two stability checks worth quoting, because they show the upgrades did not quietly move the answer:
the GSHHG coastline moved case-000's origin **0.53 km**, and replacing the principal-axis finder
with PCA moved it **0.02 km** — both against an r50 of 8.8 km, and both with a fixed seed so the
shift is attributable rather than sampling.

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

- **8.4** OpenDrift agreement — Phase 7, not started, droppable
- **8.2** should be restated on a real case once Soum's detections land; today's r50/r90 are
  `case-000`'s synthetic slick over a real ocean, and that must be said if it is quoted
- **8.3** the N = 1 age line, if and only if Huntington's detection arrives and C3.1 fires
