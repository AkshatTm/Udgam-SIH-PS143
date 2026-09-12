# Stage 2 — Age estimation: what shipped, and the three places Part C had to change

*Anushka's lane, Phase 1 of `03_ANUSHKA_DRIFT.md`. Written 10 Sept 2026 after building C3.1–C3.4
and C4. **Akshat: five decisions at the bottom, two of them gate whether an age number can go on
a slide.** Soum: two asks. Urooz: one citation.*

**Code:** `pipeline/drift/age.py` (1044 lines) · `pipeline/drift/age_tests.py` (229 lines,
suite 6, 17 assertions) · `pipeline/drift/tests.py` now runs 6 suites, **6/6, 37/37 green**.
Untracked as of writing.

```
python pipeline/drift/age.py --case <id> --real [--volume-m3 93.5]
```

Patches only the four contract-blessed keys — `age_hours`, `age_method`, `age_weathering`,
`age_estimators` — into `<out>/origin.json` (Master §6.5). Full diagnostics, every candidate and
every skip reason, go to `<out>/age_<case>.json`, which is working space and never travels in the
bundle. **No key outside the frozen contract is written.**

---

## 1. Three departures from the brief, each forced by physics

All three were found by writing the tests, not by reading the code. Each one is now pinned by an
assertion so the departure is testable rather than a comment nobody reads.

### D-A  C3.1 cannot match on area. It matches on major-axis length.

**The brief says:** measure the modelled cloud's spread and find the age whose extent matches
Soum's observed `area_km2`.

**Why that cannot work:** a 2D incompressible flow preserves the area of a material patch —
det F = 1, so it stretches in one direction exactly as much as it thins in the other. HYCOM's
surface field is close to divergence-free and our wind term is a uniform 3% that translates
rather than stretches, so an advected cloud becomes a longer, thinner filament of roughly
constant area. Matching area is fitting noise.

This is the **same structural failure as the convergence time-window estimator**, with the same
cause: a smooth field advects and stretches, it does not squeeze or inflate. Real slicks do grow
in area, but by gravity-viscous spreading and turbulent diffusion — physics the model
deliberately excludes (F8). We cannot read an age off a growth process we do not model.

**Evidence — test 6c.** In a field with known shear S = 5×10⁻⁵ s⁻¹, across candidate ages
2 → 36 h: cloud **area ×1.02**, while the **major axis grows ×5.7** (0.953 → 5.460 km).

**What shipped:** the observable is the major axis, derived from the contract as
`2 · sqrt(area_km2 × elongation / π)` — both fields Soum already exports, so **no contract
change**. Area is still computed per candidate and reported as a diagnostic: if it moves
materially, the field has real divergence in it and that is worth knowing.

### D-B  C3.3's formula is 3.24× too long. Fixed to the exact patch inversion.

**The brief says:** `aspect(t) = sqrt(1 + (S t)²)`, hence `age ≈ elongation / S`.

**Why that is wrong:** `sqrt(1 + (St)²)` is the stretch of a material **line** initially
perpendicular to the flow. It is not the aspect ratio of a deformed circular patch, which is what
`elongation` measures in `detections.geojson`.

For incompressible 2D simple shear an initially isotropic patch is mapped by
`F = [[1, γ], [0, 1]]` with `γ = S t`. Its axes are the singular values of F, so its aspect ratio
is `a = λ_max(F Fᵀ)`, and since `det(F Fᵀ) = 1` we also have `λ_min = 1/a`. Taking the trace:

```
a + 1/a = 2 + γ²        →        γ = sqrt(a + 1/a − 2)        →        t = sqrt(a + 1/a − 2) / S
```

For `a >> 1` this is `γ ~ sqrt(a)`, not `γ ~ a`.

**Evidence — tests 6d and 6e.** 6d shears a real 4000-particle cloud for a known **6 h** in a
known field: measured aspect 2.795 against a closed-form 2.811, inverted to **5.97 h**, band
[3.88, 8.05] h. 6e takes the contract's example elongation of 8.2 at S = 1×10⁻⁵ s⁻¹: the exact
inversion gives **69.8 h**, the brief's form gives **226.1 h** — **×3.24**.

**What shipped:** `age_hours` uses the exact form. Both numbers appear in the diagnostics as
`central_hours` and `brief_formula_hours`, so the discrepancy is visible rather than resolved
silently. Second reason for the acute gate, beyond the one the brief gives: the derivation assumes
the patch was isotropic at release, which a chronic discharge never is.

### D-C  C3.2 is circular, and at SAR scale it is a regime test, not an age estimator.

**Two problems.**

*The circularity.* The brief estimates volume as `area_km2 × a thickness class`, then substitutes
`V = A·h` into `r = k (Δg V² / √ν)^(1/6) t^(1/4)` where `r` is itself `sqrt(A/π)`. The observed
area appears on both sides: the law collapses to `r ∝ r^(2/3) t^(1/4)`, i.e. `r ∝ t^(3/4)`, which
is not the gravity-viscous law being advertised, and the inversion is wildly sensitive to a
thickness nobody measured. **Volume must come from an independent source** — the reported barrel
figure in the official finding.

*The scale.* Even with a real volume, Fay does not reach the observed area at any plausible age.
**Evidence — test 6i:** Huntington's 588 barrels (93.5 m³) spreads to **0.508 km² at 24 h** and
**0.880 km² even at the 72 h ceiling**, against an observed slick of order 12 km² — off by 14× or
more. Gravity-viscous spreading simply does not set the area of a SAR-detectable slick; shear and
advection do.

**What shipped:** `fay_age()` requires `--volume-m3` and declines without it, naming the
circularity. When the observed area exceeds what spreading can reach within the ceiling it returns
**no age** and records `regime: "shear_dominated"` with the measured ratio. When the slick genuinely
is in the gravity-viscous regime the inversion is legitimate and a band is returned — test 6j
round-trips a known 12 h from a 1000 m³ release to [5.41, 32.91] h.

**This is a gain, not a loss.** Fay's refusal is *independent evidence that shear set the area*,
i.e. that C3.1 is modelling the right process. It belongs on the limitations slide next to the
damping-ratio argument. What it must not do is get unioned into `age_hours` as a 400-hour band and
destroy an honest answer, which is exactly what it did on the first run.

---

## 2. C3.4 refuses, and that is the right answer

The observable the brief asks for is the **centre-versus-edge backscatter contrast inside the
slick**. That field is not in the contract. `contrast_db` is the slick against the surrounding sea
and `edge_gradient` is the sharpness of the boundary; neither is a gradient *within* the slick, and
`contrast_db` moves with wind and thickness together — precisely the confounding C2 rules out.

So `weathering_flag()` returns `unknown` and says why (tests 6n, 6o), and classifies properly the
moment the real pair is supplied (test 6p). Refusing rather than fabricating is the same instinct
as the abstain flag; a fabricated freshness call would be exactly the plausible-looking wrong
answer this stage exists to avoid.

On case-000 it returns `unknown` for a second, independent reason: mean wind at the origin is
2.64 m/s, below the 3–10 m/s band where oil–sea contrast means anything at all.

---

## 3. A new loud guard: the candidate grid runs past the end of the fetched field

`fetch_fields.py` pulls `detection_time − 30 h`, but **HYCOM is daily**, so case-000's cache holds
exactly two current snapshots:

```
currents  2017-01-28T00:00Z .. 2017-01-29T00:00Z     (2 daily snapshots)
winds     2017-01-27T19:00Z .. 2017-01-29T00:00Z     (30 hourly)
t0        2017-01-29T00:14:00Z
→ furthest honest candidate: 24.2 h before t0
```

The brief's C3.1 candidate grid runs to **36 h**. Beyond the last snapshot the field is **clamped,
not modelled** — it stops varying, the extent curve flattens and then falls, and the monotonicity
gate fails for a data reason with nothing to do with the ocean. Same failure family as a particle
finishing against the field-box wall (Phase 3.1): the number stays plausible while the physics
quietly stops.

`clip_candidates_to_coverage()` now drops out-of-coverage candidates and says so loudly. On
case-000 that dropped 6 of 18 candidates and took monotonicity failures from **20/20 to 5/20**.
The residual 5 are genuine: in a field this weak the growth per 2-hour step is small enough that
real field variation produces small dips.

**To use candidates past ~24 h, the fetch window must hold three HYCOM snapshots, not two.**

---

## 4. The finding that decides whether C3.1 fires at all

Measured on the **real** Ennore HYCOM + ERA5 fields, seeding the brief's 200 m σ cloud at the
origin centroid:

| | |
|---|---|
| modelled major axis, 2 h → 24 h | **0.79 km → 1.31 km** (×1.66) |
| deformation rate at the origin, at t0 | 1.36×10⁻⁵ s⁻¹ (shear timescale 20.4 h) |
| …at t0 − 24 h | 4.79×10⁻⁶ s⁻¹ (timescale 58 h) |
| cloud area ratio across the candidates | ×1.20 (near-preserved, as expected) |

So **C3.1's reachable major-axis range on real HYCOM is roughly 0.8–1.3 km.** It can only date
slicks about a kilometre across. That ceiling is not a coding limit — it is HYCOM's 9 km daily
resolution again, the item ranked #1 in the brief's own error hierarchy (B2). A 9 km cell cannot
hold the coastal front that would stretch a release into a multi-kilometre streak.

case-000's synthetic `det-01` is 39.3 km² at elongation 8.2 → a **20.26 km** major axis, about
15× outside what the field can produce. So **all four estimators return `none` on case-000, each
for a different and correct reason**, and `age_method` comes out `"none"` with the bounded window
standing as the bracket it is. This is `case-000 taught a wrong SHAPE` (Master Part 10) happening
a second time.

**The consequence, and the first number to check when Soum's detection lands:** whether C3.1
produces a band at all depends on Huntington's real slick being of order a kilometre across. Oil
~2.8 h old drifting at ~0.2 m/s makes that plausible — the pipeline began leaking at
2021-10-01T23:10Z and the S1A pass is 2021-10-02T01:58:21Z — but it is unknown until the real
`detections.geojson` exists.

---

## 5. Decisions needed — Akshat

| # | Decision | Cost | If we do nothing |
|---|---|---|---|
| **A1** | Ratify **D-A**: C3.1 matches major-axis length, not `area_km2`. No contract change; uses `area_km2` × `elongation`, both already exported. | zero — shipped | The brief and the code disagree on the primary estimator's observable |
| **A2** | Ratify **D-B**: the exact patch inversion `γ = sqrt(a + 1/a − 2)`. **This changes every elongation age by ~3.2× versus the brief.** | zero — shipped | Two formulas in circulation, and the deck could quote the wrong one |
| **A3** | Ratify **D-C**: Fay is a regime test, not an age estimator, and needs a volume from the official finding. Optional contract ask: a **numeric** volume field, since `verification.official_finding.volume_reported` is a free-text string (`"588 barrels"`). | zero shipped; ~10 min if you want the numeric field | Either a circular estimator or a 400-hour band unioned into `age_hours` |
| **A4** | **Cite the Fay constant k, or drop Fay from the deck.** The 1.1–1.5 range in the code is what secondary literature repeats and is *not* a checked primary citation. The whole band scales linearly with it. Route to Urooz. | Urooz, ~1 h | An uncited constant behind a number on a slide — the one thing this stage cannot afford |
| **A5** | **The C5 age-validation claim is currently 1 case, not 4.** Huntington has a documented alarm time (true age ≈ 2.8 h). Golden Ray was a continuous release with no detection. Ennore has no detection (D16). Cases 4 and 5 do not exist yet. Decide what the claim becomes. | decision only | "our age band contained the true value in N of 4" has no N |

**Note on A5, worth knowing before the numbers arrive:** a 2.8 h old slick sits squarely where
C3.1 is documented to **overestimate**, because gravity-viscous spreading dominates the first hours
and the model omits it. On the one case with ground truth, the estimator's known weak regime is the
regime we are in. That is a result to state, not a surprise to absorb on stage.

---

## 6. Asks routed to owners

**Soum — two:**
1. **`contrast_centre_db` and `contrast_edge_db`** per detection: two floats, sampled inside the
   polygon and in an annulus just inside its boundary. Without them C3.4 can only emit `unknown`.
   With them it classifies, and the threshold gets calibrated on the validation cases.
2. **Huntington's real slick major axis**, as soon as the detection exists. It is the number that
   decides whether C3.1 fires at all (§4).

**Akshat — two:**
1. Whether `fetch_fields.py` widens to a **3-snapshot HYCOM window**, or C3.1's candidate grid is
   capped at 24 h and we say so.
2. The **US case list with documented incident times** — still the only blocker on step 1.6, the
   age validation table.

**Urooz — one:** the **Fay gravity-viscous constant**, primary citation (A4).

---

## 7. Phase 1 definition-of-done status

- [x] Shear-dispersion estimator (C3.1), monotonicity verified before trusting anything
- [x] Fay estimator (C3.2), assumptions published rather than buried
- [x] Elongation-under-shear estimator (C3.3), gated on `discharge_class == "acute"`
- [x] Weathering flag (C3.4), with wind speed and the out-of-range `unknown`
- [x] Combined per C4 — intersection / union / `disagreement` / `none`, all four keys emitted
- [ ] **1.6 validated against documented release times** — blocked on Akshat (A5, §6)
- [x] 17 new assertions; suite green at 6/6, 37/37

**Checkpoint artefact for the group:** the four-case validation table cannot exist yet. What can be
posted now is §4 — the measured 0.8–1.3 km reachability ceiling on real HYCOM, and the fact that
every estimator refuses on case-000 for a different correct reason.
