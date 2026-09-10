# ANUSHKA — Stage 2: Drift, Origin, Age
*v3. Read with 00_MASTER_PLAN.md. Organised in phases, not days.*

> **Note for Akshat:** Parts B and C explain what this stage does and why, in plain terms. Read them before reviewing her work. This is the stage whose errors are hardest to see, because a wrong answer here looks completely plausible — it is a map with a cloud on it, and nothing about it announces that the cloud is in the wrong place.

---

# PART A — WHERE YOU STAND

## A1. What you built, and why it is the most rigorous component in the project

**The integrator is exact.** 18.0000 km against 18.0 expected, 0.000% error. A 24-hour forward-then-backward round trip through a *varying* field closes to 0.0001 km. RK2 truncation is not a meaningful error source at 15-minute steps.

Worth knowing for the pitch: **OpenDrift's default propagation scheme is Euler**, with Runge-Kutta available as a configuration option. You built RK2 by default. Your integrator is numerically more accurate than the reference tool's out-of-the-box setting.

**Backward is implemented correctly** — a negative dt through the same field, not a sign flip on velocity. MET Norway's own documentation confirms this is the right design: OpenDrift *"may run backwards in time by simply specifying a negative time step."* You arrived at it independently. More importantly, **you tested it in a vortex field on purpose**, because a constant field passes even with the bug present. That is a test most people would not think to write.

**Stratified ensemble sampling.** You noticed that 50 independent draws from N(1, 0.15) landed with a *realised* mean about 3% fast, which pushed the whole origin cloud 1.4 km further from the slick than the physics warranted. **No test would have caught this** — every individual draw was legitimate. You caught it by checking realised moments against claimed ones. The pooled centroid now sits 95 m from the control endpoint.

That is a class of bug that survives in professional code for years.

**You caught the HYCOM ÷1000 error on the first real fetch, before a single particle was integrated.** Six of our own documents said ÷100, including one I wrote. GEE's ingestion of `HYCOM/sea_water_velocity` lists units of m/s with scale factor 0.001, so the stored integer is millimetres per second. Your permanent plausibility guard (`speed < 3 m/s`) fired immediately.

Then you did the thing that actually matters: **you corroborated the fix physically.** The corrected field flows south along the Coromandel coast at 0.3–1.1 m/s, which is the East India Coastal Current under the January north-east monsoon. You did not just check the number was small enough; you checked it was the *right ocean*.

**The silent case-mixup.** `--case case-gulf-2019` fell through to hardcoded Ennore defaults, downloaded Bay of Bengal water, and cached it under the Gulf's name. Nothing would have crashed. A Gulf of Mexico slick would have been rewound through Coromandel currents from seven years earlier and handed Stage 3 a perfectly plausible origin cloud. You fixed it three ways and **verified by forging bad caches**, not by reasoning about them.

**Land handling done honestly.** A cell with some wet corners falls back to the mean of the wet ones; a fully-land cell returns zero velocity and holds the particle. You wrote that the model *cannot* say where a beached slick came from and should not invent a velocity to pretend otherwise. Refusing rather than fabricating is the same instinct behind the abstain flag, and it is what makes this project defensible.

**Test 5d.** An upside-down heatmap validates cleanly, looks entirely plausible, and points Stage 3 at the wrong water. You made the test cloud deliberately bimodal so the two orientations are distinguishable. Nothing but a deliberate test catches that.

**Cross-platform determinism.** Identical output on Linux/3.10 and Windows/3.11 to the last decimal. Nobody asked for that.

## A2. What you flagged

| # | Item | Where handled |
|---|---|---|
| R1 | Fixed 0.5° field-box pad; Gulf Loop at 1.8 m/s covers 156 km in 24 h against a 55 km pad | Phase 3.1 — **Akshat has funded it** |
| R2 | Stage 3 scores an elongated cloud with circles | Ruled: Jaiveer scores the grid |
| R3 | Frontend rendering traps | Ruled: BitmapLayer; Harshita has the fixes |
| R4 | First contact with real detections | Phase 6 |
| R5 | A verified scene changes the ocean | Phase 6.5 |
| R6 | US case: HYCOM window, negative longitude, fast currents | Phases 3.2, 6.1 |
| R13 | Housekeeping residue in `data/fields/` | Phase 0.3 |
| — | Five uncommitted files | **Phase 0.1 — first thing** |
| — | Neither checkpoint image posted | Phase 0.2 |

## A3. Problems I found that nobody raised

**The time window is your weakest defensible claim, and the UI renders it as a headline.** `[t0−24h, t0−8h]` with `method: "bounded"` is the rewind span minus eight hours. It is a bracket, not a measurement. Harshita's report confirms it appears in large type labelled "RELEASE WINDOW". A panel asking *"how did you derive 00:14 to 16:14?"* currently has no good answer. **Part C is entirely about fixing this**, and it is your highest-value work.

**Your convergence estimator failed for a structural reason, not a coding one.** All 50 members returned `conv_idx = 0` — spread was smallest at the seed and only ever grew. That is exactly what daily HYCOM predicts: across a 24-hour rewind the field is a linear blend of two snapshots, the flow is smooth, and the cloud **translates rather than converging**. There is no eddy structure to squeeze it. Tuning will not fix this, so you need estimators that do not rely on convergence at all.

**Only the `linear` seeding branch has run on real fields.** Blob, no-spill and abstain are untested paths. "Never executed" is never "known good."

**You now have something you did not have before: ground truth for age.** The four US cases have documented release times and known scene times. That means you can *validate* an age estimator instead of merely producing one. Nobody in this competition will have an age validation number.

**Your coastline handling is the weakest part of the physics, and two of our cases sit in enclosed water.** Golden Ray is inside St Simons Sound; Huntington Beach is inside San Pedro Bay. HYCOM's 9 km cells there are partly land, and your land mask is derived from the velocity field's own validity rather than from a real shoreline dataset. Phase 4 fixes this cheaply.

---

# PART B — WHAT THIS STAGE DOES

*Written so Akshat can supervise it. Anushka: skim B1–B2, read Parts C and D closely — those are the new work.*

## B1. The core idea

Oil found floating somewhere did not appear there. It was released elsewhere, earlier, and the ocean carried it. This stage runs the ocean backwards to find out where and when.

**The entire physics is one line:**
```
drift velocity = surface current + 0.03 × wind
```
Floating oil moves with the water, plus roughly 3% of the wind speed pushing on the exposed surface. That 3% is the only empirical constant in the whole stage, and it is a **band rather than a number** — OpenDrift's own tutorial demonstrates configuring 2%, and the published range is roughly 2.5–3.5%.

**That uncertainty is exactly why we run an ensemble.** We do not know the wind coefficient precisely, we do not know the current field precisely (HYCOM gives one snapshot per day at 9 km), and we do not know the slick's edge precisely. So the whole simulation runs 50 times with those three inputs perturbed inside their honest ranges. Fifty runs land in fifty slightly different places, and **the spread of those landings is the answer.**

It widens the further back you go, because errors compound. That is physically true and it is why the demo shows a widening cloud rather than a shrinking point. A team presenting a single sharp origin is either lucky or wrong, and an oceanographer would know within one question.

**No machine learning. No GPU. No training data.** Physics and arithmetic.

## B2. What limits accuracy — and it is not the model

This is the single most important thing for both of you to internalise, because it determines what is worth optimising.

**HYCOM in Earth Engine is 9 km resolution, one snapshot per day.** Over a 24-hour rewind, any model is interpolating between two daily snapshots of a coarse global field. A 9 km cell cannot represent a coastal eddy, a tidal reversal, or a river plume — and Ennore sits where all three matter.

The honest hierarchy of error sources:

| Rank | Source | Roughly |
|---|---|---|
| 1 | **Current field resolution and cadence** | dominant, by a wide margin |
| 2 | Wind coefficient uncertainty (2.5–3.5%) | second |
| 3 | Omitted physics (vertical mixing, weathering) | third, and only beyond ~48 h |
| 4 | Numerical integration scheme | negligible at our timescales |

**A perfect model on this data would barely tighten the origin cloud.** That is a strong thing to say on stage, not a weak one: *"our uncertainty is a property of the freely available current field, not of our code. A finer regional model would tighten it, and that's the roadmap."*

It also means: do not spend time optimising item 4, and do spend time on the cross-check that proves item 3 does not matter at our timescale (Part D).

---

# PART C — THE AGE PROBLEM

## C1. Why age matters more than it sounds

The problem statement asks for slick age "if feasible", and most teams will skip it as optional. **It is not decoration — it is a filter.** Bounding a slick at 6–18 hours instead of 0–72 shrinks Jaiveer's suspect pool by roughly an order of magnitude and sharpens every score downstream.

The framing: *"age estimation is not a feature, it's a filter."*

## C2. What does not work, and why we say so

The obvious approach is to read age from radar brightness — fresh oil damps waves harder than weathered oil, so a slick should brighten as it ages. The metric is the **damping ratio**, and it is real and widely used. But:

- Damping ratio primarily tracks **oil thickness**, not age directly, and the literature states plainly that SAR-based thickness estimation from damping ratio is still far from a mature application.
- **Damping ratio decreases with increasing wind speed and turbulence**, so wind is a confounder we cannot separate from age with one image.
- Oil–sea contrast fails entirely at very low wind (below roughly 2–3 m/s) and very high wind (above roughly 10–14 m/s).

So we use it as a **qualitative flag only** (C3.4), never as hours. Stating why the obvious method does not work is itself a credibility signal — put it on the limitations slide.

## C3. The three estimators, in order of strength

### C3.1 Shear dispersion — the primary, and uniquely ours

You have machinery nobody else has: a validated particle model driven by the *actual* current and wind field at that place and time. So instead of a generic spreading formula, ask the real ocean.

**Method.** Seed a tight point cloud (200–500 particles, gaussian σ ≈ 200 m) at the origin centroid. Run **forward** for candidate ages t ∈ {2, 4, 6, … 36} h. For each t, measure the cloud's spread — use the same PCA extent you already compute, or an equivalent-area radius. Find the t whose modelled extent best matches Soum's observed `area_km2`. Repeat across ensemble members to get a **band**, not a point.

**Why this beats a textbook law:** it captures the real local shear and the real wind on that day. Two spills of identical age in different current fields spread differently, and this estimator knows that.

**Sanity check:** modelled extent must increase **monotonically** with t. If it does not, the field or the seeding is wrong — stop and look, do not tune.

**The caveat you must state:** this models *advective and shear* spreading only. It does not model gravity-viscous spreading, which dominates in the first hours after a fresh release. **For very young slicks it will overestimate age.** Report as a lower-bounded band and say why.

### C3.2 Fay spreading — independent, generic, weaker

Classical oil spreading passes through three regimes; the **gravity-viscous** phase lasts longest and dominates for our timescales. In it, slick radius grows roughly as t^(1/4), so **area grows roughly as t^(1/2)**, with the constant depending on released volume, the oil–water density difference, and water's kinematic viscosity:

```
r(t) ≈ k · ( Δ g V² / √ν )^(1/6) · t^(1/4)
   Δ = (ρ_water − ρ_oil)/ρ_water     ν = kinematic viscosity of water ≈ 1e-6 m²/s
   k  ≈ 1.1–1.5   ← verify the constant against a published reference before quoting it
```

You need a volume estimate, from `area_km2` × a thickness class. **Publish the thickness assumption** rather than burying it — a sheen and an emulsion differ by orders of magnitude, and the assumption will dominate the answer. Report the band you get across the plausible thickness range, not a single value.

Its value is being **completely independent of the current field.** Agreement with C3.1 therefore means something real.

### C3.3 Elongation under shear — cheap, and the observable is already free

A blob dropped into a shear flow stretches. For a linear shear rate S, an initially circular patch develops aspect ratio roughly `sqrt(1 + (S t)²)`, which for `S t >> 1` simplifies to:

```
age ≈ observed elongation / S
```

Compute S directly from the HYCOM velocity gradient around the origin — a finite difference on the cached grid. Soum already exports `elongation` in the contract, so the observable costs nothing.

**Critical gate:** only valid when the slick was elongated *by the ocean*. A **`chronic`** discharge is elongated because **the ship was moving**, not because of shear — applying this there gives nonsense. So run C3.3 **only when `discharge_class == "acute"`**, and record why when you skip it.

That gate is a real physics link between Soum's stage and yours, and it is the kind of detail that reads as a designed system rather than three scripts.

### C3.4 Damping ratio — qualitative flag only

Backscatter is lower in the centre of a slick than at its edges, reflecting the thickness and weathering gradient. Use the centre-versus-edge contrast gradient to emit `fresh | weathered | unknown`. **Never hours.** Always report the mean wind speed alongside, and emit `unknown` when wind is outside roughly 3–10 m/s.

## C4. Combining them

```json
"age_hours": [8, 16],
"age_method": "combined",
"age_weathering": "fresh",
"age_estimators": {"shear": [7, 18], "fay": [9, 15], "elongation": null}
```
`age_method` ∈ `shear | fay | elongation | combined | disagreement | none`.

**Rules.** Bands overlap → take the **intersection**, mark `combined`. Bands do not overlap → take the **union**, mark `disagreement`, and say so in the UI. Nothing fires → `none`, fall back to the bounded window, and label it a bracket.

**Widening the band when estimators disagree is the honest move and it is also the impressive one.** Almost nobody does it.

Ship the per-estimator breakdown — it lets the frontend show *why* the band is what it is, and lets a judge see the agreement rather than being asked to trust it.

## C5. The validation that turns this into a claim

The four US cases have documented release times and known scene timestamps, so you know the true age. Run all four:

> *"Across four independent incidents with documented release times, our age band contained the true value in N of 4, with a median band width of X hours."*

**Report a miss as readily as a hit.** A 2-of-4 with an honest explanation is far stronger than a claimed 4-of-4 nobody can check.

---

# PART D — THE DUAL-MODEL DECISION

## D1. What we are doing, and what we are not

**We are not switching to OpenDrift, and we are not switching between models at a threshold.**

We considered a rule like "use our model below 48 h, OpenDrift above, and OpenDrift near shore." Three reasons it fails:

1. **You cannot defend the threshold.** "Why 48?" has no answer without crossover validation, and there is no ground truth for origin position on any case. It would be the one assertion in an otherwise rigorous stage that you could not back up.
2. **A particle does not know at t=0 where it will be at t=30 h.** A near-shore switch cannot be decided upfront, so you would be swapping physics mid-trajectory — a discontinuity, and "which model produced this cloud?" becomes unanswerable.
3. **The ensemble breaks.** Your uncertainty comes from 50 perturbed runs. OpenDrift gives one trajectory per run out of the box, so a hybrid cloud would be half-ensemble and half-single-run — not a coherent uncertainty statement.

**Instead: run both, always, on the same case, and render both clouds.**

Where they agree, that is independent confirmation from MET Norway's operational model. Where they diverge, that is a *finding with a diagnosis attached*:
- divergence growing with rewind depth → vertical mixing
- a roughly constant offset → the wind coefficient
- divergence concentrated near the coast → beaching and coastline resolution

You assert nothing you cannot demonstrate, you get a validation claim on every case rather than one, and disagreement becomes information rather than something hidden behind a threshold.

**The demo line:**
> *"We ran both our model and MET Norway's operational OpenDrift on every case. Here are both origin clouds. They agree within X kilometres — and where they don't, here's which physics accounts for it."*

## D2. Why ours stays in production

- **It is validated and OpenDrift would not be.** Five suites, twenty assertions, exact against known answers. A fresh OpenDrift install has none of that on our data.
- **The ensemble is the product**, and the stratified sampling is yours. You would have to rebuild it on top of OpenDrift anyway.
- **Two other people consume your output.** A swap means new numbers, new bundles, and re-verification in Jaiveer's and Harshita's lanes.
- **Instrumentability.** Because you wrote every line, your guard caught the ÷1000 error. Inside OpenDrift that would have been buried in a reader you did not write.

## D3. Near shore — a cheaper fix than OpenDrift

The near-shore gap is the **coastline dataset**, not the model. OpenDrift uses GSHHG, a proper high-resolution global shoreline. That is available directly in Python — `global-land-mask` is the simplest option, cartopy/GSHHG the fuller one — and dropping it into your existing model is a couple of hours.

**Do this regardless of what happens with OpenDrift.** It matters concretely: Golden Ray is inside St Simons Sound and Huntington Beach is inside San Pedro Bay, both enclosed water where 9 km cells are partly land.

## D4. The tiers

| Tier | Scope | Status |
|---|---|---|
| **1 — must happen** | Your model in production on all five cases · GSHHG coastline upgrade · OpenDrift comparison on **one** case, reported honestly | commit to this |
| **2 — the good version** | OpenDrift on all five as a second opinion, both clouds rendered, agreement reported per case | if Phase 7 goes smoothly |
| **3 — spare time only** | 50-member OpenDrift ensemble so both clouds are like-for-like (~30 s per 66 h run × 50 ≈ 25 min compute; the cost is wiring time, not machine time) | only with real slack |
| **dropped** | The switch rule | do not build |

**Check before building the long-rewind path at all:** does any case actually exceed 48 hours? Ennore is roughly 24 h from collision to pass. Huntington Beach is short. Golden Ray was a continuous release. If cases 4 and 5 are also short, a >48 h branch is engineering for a situation the demo never reaches.

---

# PART E — THE PHASES

## PHASE 0 — Close the loop *(minutes, first)*
0.1 **Commit and push the five uncommitted files.** 126 insertions of proven work on one laptop is the cheapest catastrophic risk in the project to close.
0.2 **Post the quiver and heatmap images.** As far as the team can see, the furthest-ahead component has not started. Both already exist in `pipeline/drift/out/`.
0.3 Delete `data/fields/case-000-WRONG.npz`, `case-000.npz.tmp`, `_to_delete/case-gulf-2019.npz`. A `.tmp` beside the real cache is what someone renames at 11pm.

## PHASE 1 — Age estimation *(highest value)*
1.1 Shear-dispersion estimator (C3.1). Verify monotonicity before trusting anything.
1.2 Fay spreading estimator (C3.2). Publish the thickness assumption.
1.3 Elongation-under-shear estimator (C3.3), gated on `discharge_class == "acute"`.
1.4 Weathering flag (C3.4), with wind speed and the out-of-range `unknown`.
1.5 Combine per C4; emit `age_hours`, `age_method`, `age_weathering`, `age_estimators`.
1.6 **Validate against the four known release times** (C5).
> 🚩 1.6 needs Akshat's US case list with documented incident times.

**Checkpoint:** post the four-case validation table.

## PHASE 2 — Forward drift and coastal impact
2.1 **Seed forward from the slick at t0**, not from the reconstructed origin. Forward-from-slick answers *"which coastline is threatened and when"* — what a coast guard actually asks. Forward-from-origin merely recreates the slick you already detected.
2.2 Write `particles_forward.json`, same schema, `"direction": "forward"`. **Do not touch `particles.json`** — Harshita builds against it.
2.3 Coastal impact summary: nearest shoreline, ETA, which stretch. With the GSHHG upgrade (Phase 4) this becomes "first particle intersects land at t = X, at position Y", which falls out of the run you are already doing.

This is what lets us say the same pipeline serves **enforcement and response**, and it connects to what the Indian Coast Guard actually does under NOSDCP.

## PHASE 3 — Robustness
3.1 **Adaptive field-box pad.** Replace the fixed 0.5° with `pad ≈ p99_speed × rewind_hours × safety_factor`, converted to degrees at mid-latitude, floored at 0.5°. Add a **guard that fails loudly** if any particle finishes within ~10 km of the box edge. Ennore survived with 11.6 km to spare; Gulf Loop at 1.8 m/s covers 156 km in 24 h and the Gulf Stream at 2.0 m/s covers 173 km. Against a 55 km pad, particles slide along the wall and produce a plausible, wrong cloud.
3.2 **Negative-longitude test.** Ennore at 80°E is identical in both conventions, so a 0–360 leak stays invisible until California at −118°E. Add a constant-current test seeded at −118°, 33° that lands the expected distance east.
3.3 **Exercise the untested branches:** a blob slick end to end on real fields; the no-spill path; and force `abstain: true` once to produce a **real abstaining bundle**. Harshita cannot build the refusal screen against a state that has never existed, and that screen is one of the better things we have to show.
3.4 **Chronic vs acute seeding.** `chronic` → the vessel was moving and the origin is a **line segment**; seed along the principal axis and expect an elongated backward cloud. `acute` → seed from the centroid.
> 🚩 3.4 needs Soum's `discharge_class`; his stub lands before his real values and is enough to build against.

## PHASE 4 — Coastline upgrade *(cheap, do it early)*
4.1 Replace the velocity-derived land mask with **GSHHG** via `global-land-mask` or cartopy.
4.2 Particles that reach land are **stranded and flagged**, not silently held at zero velocity.
4.3 Report the stranded fraction in `origin.json`. A high fraction is itself a signal: it means the slick may have originated ashore or the rewind is running past a coastline, and either is worth surfacing rather than hiding.
4.4 Re-run Ennore and check the origin does not move materially. If it does, that is a finding, not a bug.

## PHASE 5 — Run all five spill cases
> 🚩 **WAIT for Akshat** (verified scene + real `detection_time`) **and Soum** (real `detections.geojson`), per case. They deliver case by case — start each as it lands.

5.1 **Check the HYCOM window first.** The GEE archive ends **2024-09-05**. A case after that has no current field and must be rejected at selection time, not discovered here.
5.2 `fetch_fields.py --case <id>`, then control + 50-member ensemble + age + forward.
5.3 **Look at the quiver and heatmap for every case before believing any number.** Work out the expected direction *beforehand*:
- **Ennore** — coastal current runs south under the January NE monsoon, so the origin must be **north-east**. It is, at bearing 025°.
- For each US case, look up the prevailing current and write down the expected upstream direction **before** you run it. If the origin lands downstream, something is flipped.
5.4 Validator PASS, hand to Akshat with the run command.
5.5 **Remember your own finding:** `case-000` taught a *shape*, not just values. The real cloud is a 4.4:1 streak sitting ~98% outside the SAR scene. Every case has its own geometry, and assumptions baked in against the last one may not hold for the next.

## PHASE 6 — First contact and re-verification
6.1 Real detections will bring blob-class slicks, unusual vertex counts, degenerate rings, and `area_km2` disagreeing with its own polygon. Re-run the full suite plus a real run on arrival.
6.2 **If Akshat re-verifies a scene, your numbers change.** `detection_time` selects the HYCOM and ERA5 slices, so a different scene means a different ocean and a different origin. Your stale-cache guard catches it — but it means a refetch, a rerun, and new numbers on downstream slides. **Tell Akshat the moment your numbers change.**

## PHASE 7 — OpenDrift as second opinion
7.1 `pip install opendrift`. Use `OceanDrift` for pure advection (the like-for-like comparison) or `OpenOil` for oil-specific behaviour. Feed the same HYCOM and ERA5 through a netCDF reader.

Useful confirmations from MET Norway's documentation:
- **Backward runs use a negative time step** — your design, independently
- Roughly 30 s for a 66-hour run with 1,000 particles
- `time_step=900` seconds is 15 minutes — your step
- Wind drift factor is configurable (their tutorial demonstrates 2%; our ensemble spans 2.5–3.5%)
- Default scheme is **Euler**, RK configurable — **you default to RK2**
- `openoil.seed_from_gml` seeds within satellite-detected slick contours — precisely our use case
- Their gallery includes a **back-and-forth** example: a forward-then-backward round trip, the same validation you built as test 2

7.2 Same case, same fields, same seed, same duration. Compare origin centroids and cloud spread; report separation in km.
7.3 Report honestly either way. Agreement is a validation against the tool real responders use. Disagreement is a diagnosis — and finding it now beats finding it in December.
7.4 If Tier 2 (D4), run all five and hand Harshita a second cloud to render.
7.5 **Frame your own model correctly:** a **reduced-order surface advection model** — surface transport without vertical mixing or weathering chemistry. A named scientific simplification with a reason, not a shortcut.

## PHASE 8 — The numbers
8.1 Integrator exactness — 18.0000 vs 18.0 km; round trip 0.0001 km.
8.2 **Measured ensemble spread** — r50 and r90 as **precision**, not accuracy. Say: *"across the 50 runs of our uncertainty budget, half the endpoints landed within 8.8 km of the cloud's centre."* **Never** *"accurate to 8.8 km"* — there is no ground truth for origin position and we will not imply one.
8.3 **Age validation** from C5 — this is your one real accuracy claim.
8.4 **OpenDrift agreement** from 7.2.
8.5 **The error budget** (B2), with HYCOM's daily 9 km resolution named as the dominant term and stated as the floor on what anyone can do from free data.
8.6 **The ÷1000 story.** How the tests caught a 10× error before a single particle moved. Thirty seconds of narrative, and the best evidence in the project that this team tests properly.

**The demo sentence:**
> *"We don't claim a point. We claim a probability field whose spread we measured by running the physics fifty times across the honest range of its inputs — and we say when we can't tighten the release time rather than inventing one."*

---

# PART F — RISKS

**F1. Age estimators disagree *(MEDIUM, survivable)*.** That is a result, not a failure. Report the union, mark `disagreement`, name the assumption each rests on. A widened honest band beats a narrow invented one.

**F2. Fast currents pin particles to the box edge *(HIGH, silent)*.** Phase 3.1. The adaptive pad lowers the probability; **the loud guard is the half that matters**, because otherwise the failure is invisible.

**F3. Negative-longitude leak *(MEDIUM, silent until the first US case)*.** Phase 3.2. The danger is precisely that Ennore cannot reveal it.

**F4. First contact with real detections *(MEDIUM, probably loud)*.** Phase 6.1. Look at the pictures before believing any number.

**F5. A re-verified scene changes your numbers *(MEDIUM)*.** Phase 6.2. Guarded, but it propagates to two other people and to the deck.

**F6. HYCOM archive boundary *(LOW, loud)*.** Check at case selection, not at fetch.

**F7. OpenDrift eats time *(LOW-MEDIUM)*.** Heavy dependencies and its own config model. It is Phase 7 for a reason — last, and droppable. **Do not let it take time belonging to Phase 5.** If it costs more than a few hours, stop and say we ran out of time rather than shipping a half-done comparison.

**F8. Turbulent diffusion is not modelled *(stated limitation, not a bug)*.** Our spread comes from *parameter* uncertainty, which is defensible and measured. A diffusion coefficient we could not source would be an invented number widening an honest one. Keep it out, keep saying why — and state that our cloud is therefore narrower than physical reality by an unquantified amount.

---

# PART G — REFERENCE

## G1. Commands
```bash
python pipeline/drift/check_gee.py                                   # preflight
python pipeline/drift/fetch_fields.py --case <id>                    # --force to refetch
python pipeline/drift/plot_quiver.py  --case <id>                    # look at this
python pipeline/drift/run.py --case <id> --real --particles 3000 --runs 50
python pipeline/drift/run.py --case <id> --real --forward            # Phase 2
python pipeline/drift/age.py --case <id>                             # Phase 1
python pipeline/drift/plot_heatmap.py --case <id>                    # look at this too
python pipeline/drift/compare_opendrift.py --case <id>               # Phase 7
python pipeline/drift/tests.py                                       # must stay green
python scripts/validate_case.py cases/<id>                           # PASS before handover
```

## G2. Data sources
| | Currents | Winds |
|---|---|---|
| Collection | `HYCOM/sea_water_velocity` | `ECMWF/ERA5/HOURLY` |
| Bands | `velocity_u_0`, `velocity_v_0` | `u_component_of_wind_10m`, `v_component_of_wind_10m` |
| Resolution | 0.08° ≈ 9 km, **daily** | ~0.25° ≈ 28 km, hourly |
| Units | **scale 0.001 → divide by 1000** | signed m/s, no scaling |
| Archive | 1992-10-02 → **2024-09-05** | ongoing |

## G3. Contract additions
```json
"age_hours": [8, 16],
"age_method": "combined",
"age_weathering": "fresh",
"age_estimators": {"shear": [7,18], "fay": [9,15], "elongation": null},
"stranded_fraction": 0.03,
"opendrift_comparison": {"centroid_separation_km": 2.4, "r90_ratio": 1.08}
```
Clear with Akshat before shipping — these extend the frozen contract, and Harshita renders all of them.

## G4. Rules that do not change
- Coordinates `[lon, lat]`, wrapped to −180…180 in exactly **one** place
- Every timestamp timezone-aware UTC; `require_aware()` raises on naive
- `duration = (n_steps − 1) × timestep_minutes`; **never hardcode a frame count**
- Velocities as signed u/v, **never converted to speed-and-bearing** — that conversion is where the meteorological "wind from" and oceanographic "current towards" conventions collide
- Tests green on every change; plausibility guards run on every real run, forever
- Every phase ends in a picture or a green test, and it gets posted

## G5. Escalate to Akshat (45-minute rule)
GEE auth or quota · a case date outside the HYCOM archive · `detections.geojson` not matching the contract · **your origin numbers changing after a scene is re-verified** (downstream slides depend on them) · OpenDrift taking more than a few hours.

## G6. Definition of done
- [ ] Five files pushed; both images posted; `data/fields/` cleaned
- [ ] Three age estimators implemented, combined, emitted
- [ ] Age validated against four known release times; hit rate reported
- [ ] Forward drift + coastal impact shipping as `particles_forward.json`
- [ ] Adaptive field pad + loud edge guard
- [ ] Negative-longitude test in the suite
- [ ] Blob, no-spill and abstain branches exercised; a **real abstaining bundle** handed to Harshita
- [ ] `discharge_class` driving line-vs-point seeding
- [ ] GSHHG coastline in place; stranded fraction reported
- [ ] All five spill cases run, quiver and heatmap eyeballed, validator PASS
- [ ] OpenDrift comparison on at least one case, reported honestly
