# Stage 3 — Attribution: issue register

**Jaiveer · 13 September 2026 · for Akshat**
**Branch:** `jaiveer-phase2` @ `d39e619` · **Freeze:** Tue 15 Sept 05:00 IST

Every open problem in Stage 3, with the evidence behind it, why it matters, and what I need from
you. Companion to `docs/_archive/jaiveer/stage3-progress-2026-09-13-evening.md`, which covers what *works*.

**Nothing in this document has been fixed by changing a weight or a threshold.** Every one of these
could have been made to disappear that way, and that is exactly what D21 exists to prevent. Where a
fix required a decision that is not mine, I have written the decision up and left the code alone.

---

## How to read this

**Owner** — who has to act. **Severity** — impact if we ship without resolving it.

| Severity | Meaning |
|---|---|
| **BLOCKER** | Something visible on stage is wrong, or a stage cannot run |
| **HIGH** | A claim we make is weaker than it sounds, or a judge could take it apart |
| **MEDIUM** | Real, worth fixing, survivable if stated openly |
| **LOW** | Cosmetic or housekeeping |

---

## Summary

| # | Issue | Owner | Severity | Decision needed |
|---|---|---|---|---|
| **A · Scoring model** ||||
| A1 | Menuett is not a gap case | Akshat | HIGH | Yes — plan edit |
| A2 | `gap` rewards the wrong vessel on Jacksonville | — | MEDIUM | No — pre-registered |
| A3 | Box exits are indistinguishable from going dark | Fixed | MEDIUM | No — gate added |
| A4 | `trajectory` as specified could never fire | Fixed | HIGH | No |
| A5 | `trajectory` corrected barely discriminates | Akshat | HIGH | Yes — weight |
| A6 | `type_prior` discriminates nothing offshore | Akshat | MEDIUM | Yes — weight |
| A7 | A vessel on the origin peak can rank second | Akshat | MEDIUM | Related to B2 |
| A8 | Repeat offenders is structurally undemonstrable | Akshat | MEDIUM | Yes — reframe |
| A9 | Renormalised scores overstate confidence | Akshat + Harshita | **BLOCKER** | Yes — card design (data now shipped) |
| A10 | `temporality` is `null` on half the library | Anushka / Soumirya | HIGH | Yes — route |
| **B · Data and contract** ||||
| B1 | `age_method: none` on all six cases | Anushka | HIGH | Yes |
| B2 | `closest_km` does not mean what §6.7 implies | Akshat | HIGH | Yes — schema |
| B3 | Grid peak sits 10.65 km from the stated centroid | Akshat | MEDIUM | Yes — reference point |
| B4 | The `case-000-*` fixtures cannot be scored | Jaiveer | MEDIUM | **CLOSED** — replaced |
| B5 | 149 validator warnings on the hero case | Akshat + Anushka | HIGH | Yes — validator |
| B6 | `acts_available` excludes `attribute` on all six | Akshat | **BLOCKER** | Yes — edit |
| **C · Blocked on teammates** ||||
| C1 | `parity` returns `null` everywhere | Soumirya | **BLOCKER** | No — needs delivery |
| C2 | `ship_detections` cannot support the dark-vessel gates | Soumirya | HIGH | Yes — field or fallback |
| C3 | `discharge_class` disagreement | Soumirya / Anushka | MEDIUM | Yes |
| C4 | GFW acquisition path is unscoped | Akshat | HIGH | Yes |
| **D · Documentation and process** ||||
| D1 | Blind evaluation does not hold for four of six cases | Akshat | HIGH | Yes — wording |
| D2 | Master Part 3 is stale on Menuett and on distance | Akshat | MEDIUM | Yes — edit |
| D3 | Decision numbering has diverged (D22 vs D30/D31) | Akshat | MEDIUM | Yes |
| D4 | `component_notes` is unblessed | Akshat | HIGH | Yes — schema |
| D5 | Two unrelated 40s in the abstain logic | Akshat | LOW | Half done — my side renamed |
| D6 | First merge into `main` took an earlier commit | Fixed | MEDIUM | No |
| **E · Scope** ||||
| E1 | Phases 4, 5, 6 and 7 will not ship | Akshat | HIGH | Yes — narrative |

**Four items need a decision before Monday afternoon:** A9, B6, C4, D4. The rest can wait until
Monday evening, but not past it.

## Independent agreement, 14 Sept — the cross-check nobody planned

Jaiveer and Akshat implemented **D36, D37, the D28 `type_prior` gate and the exclusions fix
separately**, on the same evening, without seeing each other's code — and against **two
independently obtained AIS extracts** (his own parquets; a rebuild from the public NOAA archive).

**The outputs agree exactly** on all three scored cases: same funnel counts, same ranking, same
scores, same `closest_km` to the peak, same `weight_live`, same gating decision, same exclusion
reasons for the scored vessels. Jacksonville 0.693 / 0.650 at 1.30 / 1.13 km; Farallones 0.620 /
0.345 / 0.046 with `type_prior` gated to null; Huntington abstaining at 0.730 vs 0.729.

That is a stronger statement than either of us re-running our own code, and it is worth one line
on stage: *two implementations, two data pulls, same numbers.* It also retires any suspicion that
the D28 gate or the peak-based `closest_km` was fitted to a case.

**Two defects in the version that was merged, both found by measuring before shipping:**

- **A false exclusion reason.** `score_vessel` returns `None` when a vessel never touched *non-zero*
  origin probability — **not** when it has no report inside the window. The card text said "no AIS
  position report inside the release window" for every such vessel. Measured: **0 of 23** on
  Jacksonville, **1 of 65** on Huntington, and Farallones' NAVAJO has **138 reports inside the
  window**. The corrected sentence is also the stronger evidence: present and broadcasting
  throughout, and still never inside the cloud, closest approach 27.8 km from the peak.
- **A non-deterministic list.** 23 and 65 candidates against `MAX_EXCLUSIONS = 3`, taken in dict
  iteration order, so two runs of the same data named **different ships** — which is precisely why
  his three and ours differed. Now ordered nearest-to-peak, then MMSI; verified byte-identical
  across two runs. R10 claimed cross-platform determinism, and this was a hole in it.

**Still open (display, not correctness):** only 3 of 23 (Jacksonville) and 3 of 65 (Huntington)
exclusions are shown. The funnel carries the real counts, but a judge reading the card sees three.
Worth a count on screen after the demo.

---

## New, 14 Sept — raised by the GFW ingest, not yet ruled

**F1 · `MIN_POINTS = 5` is a different filter at hourly sampling, and on Mumbai it drops the only
vessel that touched the origin.** · Owner: Akshat · Severity: **HIGH** · Decision needed

`tracks.MIN_POINTS = 5` means "fewer than five reports is noise, not a path". At NOAA's ~71 s that
is about six minutes of presence. At GFW's one-per-hour it means **five hours inside the box**, so
any vessel that transits in under five hours is discarded before it is ever scored.

Measured on `case-mumbai-2023` (9 vessels, 31 vessel-hours):

| mmsi | reports | best grid probability | km to origin peak | kept? |
|---|---|---|---|---|
| 419001409 (SAGAR PRIDE) | 4 | **0.069** — above the 0.05 plausible floor | 5.0 | **dropped** |
| 419768000 | 9 | 0.000 | 12.6 | kept, not plausible |
| 419001287 | 8 | 0.000 | 12.3 | kept, not plausible |
| 6 others | 1–2 | 0.000–0.025 | 6.8–13.1 | dropped |

So the funnel reads `9 → 2 → 0 → 0` and the case abstains, when the one vessel that reached the
cloud was removed by a threshold calibrated for a different sampling regime.

**It has deliberately not been changed.** Mumbai's sealed record lists **zero** AIS vessel
candidates, so relaxing this gate now would push the system toward naming a vessel on a case whose
documented answer names none — tuning a threshold with the answer in view, which is exactly D21.
Recorded before any change, in the manner of D30.

**Ask:** rule after the demo on making the minimum sampling-aware (e.g. "5 reports **or** 3 hours
of presence"), and validate it on the Phase 8 curve at `sampling=gfw_hourly`, never on Mumbai.

---

## Resolutions, 14 Sept (Akshat)

*Rulings on the items owned by Akshat. The sections below are left as written, as the record of what was raised.*

| # | Resolution |
|---|---|
| A1 | **Done.** Master §3.2 says Jacksonville is not a gap case and gives 170 km, not ~100 km. D30 moves the gap story to case 4. |
| A5 / A6 | **Measured 14 Sept — the Phase 8 curve now exists** (`docs/evaluation/stage3-injected-offender-curve.md`, `pipeline/attribute/evaluate.py`). Ablated on the hard condition (300 trials, offshore, offender with no behavioural signature): removing **`trajectory` costs −0.051 top-1, so A5 is answered — it does contribute**, about half of `temporality`. Removing **`type_prior` costs −0.024, so A6 is answered — it is nearly inert** (and an earlier −0.100 turned out to be an artefact of the generator always making the offender a tanker). **Still no weight moves before the demo**: one offender design, two parquets, hours before freeze. Both go on the honesty slide with these numbers instead of adjectives. |
| A2 | **Reproduced at scale and quantified.** In the hard condition, removing `gap` *improves* top-1 from 0.579 to 0.722 (**+0.143**): the offender never goes dark while real traffic does, so the component rewards innocent ships. It is worth a lot when the offender *does* go dark (0.910 with a 45-minute gap against 0.681 without). `gap` assumes the behaviour it looks for. December question, not a demo change. |
| A8 | **Roadmap, not a feature.** The `repeat_offender` block stays in §6.7. On stage: the data model supports it, and our library has no vessel overlap by construction (Atlantic and Pacific). Nothing is rendered for it. |
| B3 | **Rings stay centroid-centred; `closest_km` is to the peak (D36).** The card says "to the origin peak", never "closest approach". `trajectory` still bears toward `grid.centroid` (`score.py:194`). That is a known inconsistency, left unchanged for the demo because a component-definition change should come with the Phase 8 curve rather than go into a bundle on the last day. Revisit after 15 Sept. |
| B5 | **Solved by the reach fix** (`495dc73`). Trace layers are checked within 300 km and vessels within 400 km. Jacksonville went from 767 warnings to 1. It carries 7 today: six are the D37 fields missing, which clear on Jaiveer's re-score. The seventh, "no excluded vessels", is on all four scored cases and is a demo requirement, so it's routed to Jaiveer. Farallones also warns that `type_prior` is 1.0 and `slowdown` 0.0 across all 3 suspects. D28 says the first should gate to `null`, which is also routed. |
| D1 | **Declared per case in §16.1 (D31).** Amended 14 Sept: Farallones is *blind on weights, not provably on identity*, because its identity was in pushed docs between `ee19819` and `72b9540`. The stage line quotes no count. |
| D2 | **Done**, same edit as A1. |
| D3 | **Reconciled.** The Master Plan decision table runs D1–D38, and D32 was never assigned. Master is authoritative; `docs/CONTRACTS.md` is the v1 record. |
| E1 | **Narrative, updated 14 Sept.** Phase 8 (the injected-offender curve) **also shipped** — see `docs/evaluation/stage3-injected-offender-curve.md`. Phase 4 (infrastructure) **shipped**: code, tests and a D38 contract, with Huntington's candidate declared. Its honest result is below floor (D38). Phases 5 (traffic prior), 6 (repeat offenders, A8) and 7 (chronic vs acute, blocked on C3/B1) are **openly dropped for the demo** and presented as roadmap, not implied. |

---

# A · Scoring model

## A1 — Menuett is not a gap case

**Owner:** Akshat · **Severity:** HIGH · **Ruling:** D30

### What

Master plan Part 3 describes `case-jacksonville-2024` as *"the only case that exercises gap
detection"*. Measured against the real AIS, it is not a gap case at all.

### Evidence

Inside Cerulean's own −8 h / +6 h window around the detection, the documented vessel broadcast
**714 times**, covering **14.0 hours of the 14-hour window** with no coverage hole at either end.
The **longest silence was 130 seconds**.

The window being fully covered is what makes this a finding rather than an inconclusive check. If
there had been a hole at either end we could not have ruled a gap out; there is not, so we can.

### Why it matters

Three things follow. The demo narrative currently rests a component on a case that does not
exercise it. Part 3.2 also states the vessel is ~100 km offshore; the AIS-density check that
established the above measured it at **170 km**. And the `gap` component — 15% of the score — has
no case in the library that demonstrates it working correctly.

### Ask

1. Edit Master Part 3: Jacksonville is not the gap case, and the distance is 170 km not ~100 km.
2. Decide where the gap story lives instead. **My proposal: `case-gulf-alaska-2023`.** A dark vessel
   is a ship that never speaks at all — the same argument in its strongest possible form, already in
   the library, and unlike Menuett's gap it is actually present in the data. Back it with the
   Phase 8 curve rather than a single anecdote.

---

## A2 — `gap` rewards the wrong vessel on Jacksonville

**Owner:** — · **Severity:** MEDIUM · **Status:** pre-registered before scoring, per D30

### What

On the Jacksonville window, the `gap` component gives full marks to a vessel that is almost
certainly not the source, and zero to the documented one.

### Evidence

**STENA PROSPEROUS** — 7.4 km from the slick, under way at 12.5 kn, **142.3 minutes** of genuine
silence beginning mid-box at −79.29, 29.27 (i.e. not a box-exit artefact, see A3). It survives every
gate. The documented vessel scores 0.00 on `gap`, per A1.

### Why it matters

This is the component behaving exactly as specified and producing a misleading result, which is a
harder problem than a bug. It is also the clearest single argument for why `gap` needs the Phase 8
curve behind it before we claim anything about it on stage.

### Status

**Pre-registered with you before the case was scored**, and recorded in
`cases/case-jacksonville-2024/meta.json`. That pre-registration is the honest artefact here: we said
in advance that this case may return partial or miss, and it ships either way.

*Footnote for accuracy:* in the run against Anushka's published origin, STENA PROSPEROUS did not
reach the plausible set at all — it never touched ≥5% grid probability inside the 8.3-hour window.
The pre-registration describes a wider window than the published origin defines. Recording this so
nobody later reads its non-appearance as the prediction having been wrong.

---

## A3 — Box exits are indistinguishable from going dark

**Owner:** fixed in `score.py` · **Severity:** MEDIUM

### What

A vessel that sails out of the search rectangle and back looks, in the filtered data, exactly like a
vessel that switched its transponder off and on. Both produce a hole in the reports.

### Evidence

Of 11 under-way silences found in the Menuett analysis, **5 were box exits**. Every one of them
resumed broadcasting **exactly on the search boundary** (lon −81.00 or lat 28.50). The longest was
**1399 minutes** — 23 hours.

The split is unusually clean. All five artefacts were among the five *longest* silences (306–1399
minutes); the six genuine ones are 57–144 minutes and all began mid-box.

### Fix

`SearchBox.on_edge(lon, lat, tol)` with `EDGE_DEGREES = 0.02` (~2 km). A silence that begins or ends
within that tolerance of the box boundary is gated as a box exit and does not score.

### Why it still matters

**The honest figure for any slide is 6, not 11.** And it is worth saying that the artefacts were the
*biggest* numbers: an ungated version of this system would have led with a 23-hour blackout that was
a ship sailing out of a rectangle. That is a good story about why the gate exists, and a bad one if
a judge finds it first.

---

## A4 — `trajectory` as specified could never fire

**Owner:** fixed in `score.py` · **Severity:** HIGH

### What

The `trajectory` component asks whether a vessel was heading toward the origin. As specified it
measured this **at the point of closest approach**, and at that point the test is geometrically
impossible to pass.

### The geometry

The point of closest approach is *defined* as the point where the line from the vessel to the target
is perpendicular to the vessel's course. That is what "closest" means. So the angular difference
between COG and the bearing to the origin is ~90° by construction, and worse than 90° for any vessel
already past the origin. A ±60° acceptance cone can essentially never be satisfied.

### Evidence

**0.00 for 16 of 17 vessels, median 126° off.** That distribution — nearly all zeros, all clustered
at or beyond perpendicular — is what identified it as geometry rather than data. Real measurements
are messier than that.

### Fix

Changed **where** the component is measured, not **how much** it is worth. The scorer now walks the
track backwards from closest approach to the last report at which the vessel was still outside
`radius_90_km`, and compares COG to the bearing to the origin *there* — on the approach, before
arrival.

This is the same class of change as D9: a correction to what is being measured, not a tuning of a
weight. **No weight was touched.**

---

## A5 — `trajectory` corrected barely discriminates

**Owner:** Akshat · **Severity:** HIGH · **Decision needed**

### What

The corrected component now passes almost everything, which is the same failure in the other
direction.

### Evidence

| Dataset | Result |
|---|---|
| Synthetic fixture | **1.00 for 13 of 15**, median 25° off |
| Jacksonville, real AIS | **1.00 for 2 of 2** — 17° and 5° off |

### Why

To enter the candidate set at all, a vessel must reach the origin cloud. Any vessel that reached the
cloud was, by definition, heading toward it at some point on the approach. You cannot arrive
somewhere without having pointed at it.

So the corrected component largely restates *"this vessel came near the origin"* — which
`proximity` already measures, at double the weight.

### Why it matters

**15% of the total score is carrying almost no discriminating information.** Before the fix it was
broken; after the fix it is near-tautological. Both facts are worth stating rather than hiding.

### Options

1. **Leave the weight at 0.15 until Phase 8 measures it.** My preference, and the only D21-compliant
   route. Phase 8 can answer directly: does removing `trajectory` change the top-3 rate?
2. **Reallocate now on your authority.** Defensible if you rule it, since D21 binds me and not the
   integration lead — but the number would have no measurement behind it.
3. **Keep it and say on stage that it is a sanity check, not a discriminator.** Honest, and cheap.

### What would actually discriminate

`parity` — whether the vessel travelled **along** the slick's long axis or **across** it. A moving
vessel discharging oil lays it down in a line behind itself, so the slick's major axis should match
the vessel's course. A passer-by cuts across. That does not collapse into proximity. It is blocked
on C1.

---

## A6 — `type_prior` discriminates nothing offshore

**Owner:** Akshat · **Severity:** MEDIUM

### Evidence

**1.00 for all 17 vessels** in the Galveston test set. An offshore shipping lane is entirely tankers
and cargo; `TYPE_PRIOR` maps both to 1.0.

On Jacksonville it produced 1.00 (cargo) and 0.50 (other) — two values across two vessels, which is
better but not evidence of anything.

### Why it matters

5% of the weight, and in open-ocean cases it is a constant. A constant added to every score changes
no ranking. It is not harmful, but it is not doing work either, and if a judge asks "what does
`type_prior` contribute here?" the honest answer today is "nothing."

### Ask

Same as A5 — let Phase 8 measure it. It may earn its weight on a coastal case where fishing vessels
and passenger traffic are present. Jacksonville and Galveston are the wrong places to judge it.

---

## A7 — A vessel sitting on the origin peak can rank second

**Owner:** Akshat · **Severity:** MEDIUM

### Evidence

In the Galveston test set: **EVERGLADES**, grid probability 0.98 at 2.3 km, ranked **below**
**AP REVELIN**, grid probability 0.31 at 17 km.

### Why it happens

`proximity` is 30% of the score. A vessel can be strong on proximity and lose on the remaining 70%
to a vessel that is weaker on proximity but scores on components the first one could not be measured
for. That is the weighted sum working as designed.

### Why it matters

It is counter-intuitive on screen, and a judge will notice it before we explain it. "The ship
closest to where the oil started is ranked second" needs an answer ready.

The answer is that proximity is one signal of seven and the system is deliberately not a
nearest-neighbour lookup — but that answer is much stronger if the card shows *which* components
separated them. Which is D4.

Related to B2 and B3: what "closest" even means here depends on whether we measure to the grid peak
or the centroid.

---

## A8 — Repeat offenders is structurally undemonstrable

**Owner:** Akshat · **Severity:** MEDIUM

### What

Phase 6 was to identify vessels appearing as suspects in more than one case. This cannot be
demonstrated with the current library.

### Evidence

The two vessel-attribution cases are in the **Atlantic** and the **Pacific**. **No vessel appears in
both.** There is no overlap to find, and no amount of code changes that.

### Ask

Reframe as roadmap rather than delivering an empty feature. The schema already carries the
`repeat_offender` block in §6.7 — the honest position is *"the data model supports it and the
production system would populate it across a larger case library; our six-case demo library has no
overlap by construction."* That is a stronger statement than a feature that returns nothing.

---

## A9 — Renormalised scores overstate confidence  ⚠ BLOCKER

**Owner:** Akshat + Harshita · **Severity:** BLOCKER · **Decision needed before Monday afternoon**

### What

When components are not applicable, their weight is redistributed across the remaining ones (D9).
This is mathematically correct and is the honest way to handle missing data. But the resulting
score is displayed with no indication of how much evidence it rests on.

### Evidence

From tonight's `gfw_hourly` gating test (`pipeline/attribute/fixtures/case-gfw-fake`,
`data/ais/gulf.parquet`):

```
funnel   987 -> 897 -> 17 -> 3

 #  score  live  vessel              prox  pari  temp  traj   gap  slow  type
 1  0.981  0.35  EVERGLADES          0.98   n/a   n/a   n/a   n/a   n/a  1.00
 2  0.926  0.35  SFL CONDUCTOR       0.91   n/a   n/a   n/a   n/a   n/a  1.00
 3  0.843  0.50  CMA CGM TAGE        0.74   n/a   n/a  1.00   n/a   n/a  1.00
```

**EVERGLADES scores 0.981 from two of seven components**, with a live weight of **0.35**. Five
components are unmeasurable, for four different reasons:

| Component | Why `null` here |
|---|---|
| `parity` | No slick polygon from Stage 1 (C1) |
| `temporality` | Origin `time_window_method` is `bounded` (A10) |
| `trajectory` | Vessel never reported from outside `radius_90_km` — no approach to measure |
| `gap` | `ais_source: gfw_hourly` — hourly sampling cannot resolve a 30-minute silence (D20) |
| `slowdown` | Same |

### Why it matters

A suspect card reading **0.98** reads as a near-certain identification. It is one strong signal and
one weak prior, with 65% of the evidence base absent. Nothing on the card says so.

**And this is not an edge case.** On `gfw_hourly` cases it is the default state — `gap` and
`slowdown` are permanently `null` there — and both Indian cases are `gfw_hourly`. Combined with A10,
Mumbai and Jamnagar will routinely produce high-looking scores from two or three live components.

This is the single most likely thing in Stage 3 to be taken apart in December. "Your system said
98%" — "it had two of seven inputs" is a bad exchange to have on stage rather than in the design.

### Options

1. **Surface the live weight on the card.** "2 of 7 signals available", or the live weight itself,
   rendered next to the score. **My preference** — it states what we measured without inventing
   anything.
2. **Discount the score when live weight is low.** Multiply by some function of live weight. This
   means a second formula stacked on the first, and the discount curve would itself need
   justification. Harder to defend, not easier.
3. **Leave it.** Only defensible if we say it out loud in the presentation, every time.

### What I have already done — 13 Sept, 22:00

I cannot fix the display, but I can make sure nobody waits on me once you rule. Every suspect in
`suspects.json` now carries three additional fields:

```json
"weight_live": 0.35,
"components_available": 2,
"components_total": 7
```

Verified on the `gfw_hourly` fixture:

```
EVERGLADES       score=0.981  weight_live=0.35  available=2/7
SFL CONDUCTOR    score=0.926  weight_live=0.35  available=2/7
CMA CGM TAGE     score=0.843  weight_live=0.50  available=3/7
```

The numbers were already computed inside the scorer for the renormalisation — they simply were not
being written out. Three new tests pin the arithmetic (`TestEvidenceBreadthReachesTheCard`).

These are additive and outside §6.7, exactly like `component_notes` (D4). **If you refuse the schema
amendment, all four keys come out together.** But the frontend cannot render what it has not been
given, so the data ships now.

### Ask

Rule on the display, and tell Harshita, because it is a card-layout change and she is building now.
The data is in the file waiting for her either way.

---

## A10 — `temporality` is `null` on half the case library

**Owner:** Anushka (route A) / Soumirya (route B) · **Severity:** HIGH

### What

`temporality` — 15% of the score — is gated on `origin.time_window_method`. Where the window is a
search bracket rather than a measured release time, the component declines to score.

### The gate, and why it is correct

`score.py`:

> *"Master plan 6.5 is explicit that `bounded` means a **search bracket, not a measured release
> time** — every vessel present in the bracket then scores much the same and the number says
> nothing. Scoring against a non-measurement is worse than declining to score, so `bounded` returns
> `null`."*

This is D12 being honoured. Scoring against a bracket would generate a number with no measurement
behind it, which is precisely what we forbid elsewhere.

### Evidence — measured across all six real cases

| Case | `time_window_method` | `temporality` |
|---|---|---|
| `case-jacksonville-2024` | `convergence` | works — 0.701, 0.632 |
| `case-huntington-2021` | `convergence` | works |
| `case-gulf-alaska-2023` | `convergence` | works |
| **`case-farallones-2023`** | **`bounded`** | **`null`** |
| **`case-mumbai-2023`** | **`bounded`** | **`null`** |
| **`case-jamnagar-2024`** | **`bounded`** | **`null`** |

**Three of six.** Combined with C1 (`parity` null everywhere), those three cases lose 30% of the
weight before scoring starts — and two of them are also `gfw_hourly`, losing another 20%. On Mumbai
and Jamnagar the scorer will be working from **proximity, trajectory and type_prior alone**, which
is 50% of the designed evidence base. See A9.

### Two routes to a fix

**Route A — the window becomes a measurement.** Requires Anushka's backward drift to converge on
those three cases. See B1: no case in the library currently has an age estimate, which is likely
why they do not converge. **Ask, but do not ask her to relabel a bracket as a measurement** — that
would be writing down a number nobody measured.

**Route B — a different measurement entirely, which does not need the window.** `score.py` already
names it:

> *"Phase 2 replaces this with Cerulean's version: the timestamp of the broadcast spatially nearest
> the **head** of the slick. That needs Soumirya's polygon."*

A slick has a head and a tail; the head is the freshest oil and therefore the most recent discharge.
Asking *"which vessel was nearest the head, and when"* uses the slick's geometry instead of the
clock, and works on a `bounded` case.

**Route B is strictly better**, because the same polygon also unlocks `parity` (C1). **One delivery
from Soumirya fixes two of seven components across the whole library.** That makes it the highest-value
outstanding dependency in Stage 3 by a wide margin.

### What I have already done — 13 Sept, 22:00

The gate itself had **no test coverage in either direction**, because `make_fake_case.py` hardcoded
`time_window_method: "bounded"` and could not produce a `convergence` fixture. So the component that
decides 15% of the score on half the library had never been exercised.

Added `--time-window-method {bounded,convergence}` to the generator (default unchanged at `bounded`,
so nothing anyone is building against moves), plus four tests in `TestTemporalityGate`: a bracket
returns `null`, a measurement scores, the score decays correctly toward the window edge, and an
unrecognised method **fails closed** rather than being treated as a licence to score.

A `convergence` fixture now produces live temporality values for the first time — `temp` ranging
0.00 to 0.96 across 17 vessels, with live weights of 0.70 and 0.85 instead of a flat 0.50.

This does not resolve A10 — the three real cases are still `bounded` and that is Anushka's and
Soumirya's to change. It means the code path is proven, so when either route lands we are not debugging
it under time pressure.

---

# B · Data and contract

## B1 — `age_method: none` on all six cases

**Owner:** Anushka · **Severity:** HIGH

### Evidence

```
case-jacksonville-2024   age_method=none   age_hours=None
case-huntington-2021     age_method=none   age_hours=None
case-gulf-alaska-2023    age_method=none   age_hours=None
case-farallones-2023     age_method=none   age_hours=None
case-mumbai-2023         age_method=none   age_hours=None
case-jamnagar-2024       age_method=none   age_hours=None
```

§6.5 defines `age_method ∈ shear | fay | elongation | combined | disagreement | none`. Every case is
`none` and every `age_hours` is `null`.

### Why it matters for Stage 3

Two consequences. **Phase 7** (chronic vs acute discharge) cannot run at all. And the age estimate
is largely what allows a backward drift to pin a release *time* — so this is the probable root cause
of A10's three `bounded` cases.

### Ask

Is the age engine expected to land before freeze, and if it does, would it convert any of Farallones,
Mumbai or Jamnagar to `convergence`? A plain "no" is a perfectly good answer — I will plan around
it — but I need to know by Monday morning.

---

## B2 — `closest_km` does not mean what §6.7 implies

**Owner:** Akshat · **Severity:** HIGH · **Decision needed**

### What

`score.py`:

```python
"closest_km": round(geo.haversine_km(pos[0], pos[1], *grid.centroid), 2)
```

where `pos` is **the position at which the vessel touched its highest grid probability**.

So the field means *"distance from the origin centroid to the vessel's best-probability sample
point"*. It does **not** mean "how close the vessel came to the origin", which is what the name says
and how a frontend will render it.

### Why the difference is material

On Jacksonville, both suspects sat essentially **on the grid peak** — grid probability 0.946 and
0.943 — and the peak is **10.65 km from the centroid** (B3). So both report `closest_km ≈ 10.2 km`
while being, in the only sense the model cares about, *at* the most likely origin.

A card reading *"came within 10.2 km"* materially understates the finding. The correct statement is
closer to *"passed directly over the most probable release point"*.

### Options

| | Definition | Jacksonville would report | Cost |
|---|---|---|---|
| **(a)** | Keep as is, rename to `centroid_km` | 10.22 km | §6.7 amendment, frontend string change |
| **(b)** | Measure to the **grid peak** instead | ≈0.5 km | Code change in `score.py`, no schema change |
| **(c)** | True minimum track-to-centroid distance | varies | Matches the field name; least informative; reintroduces circle thinking, which D8 exists to remove |

**My recommendation: (b)**, with the `component_notes` string stating which reference point was
used. It is consistent with D8's logic — the grid is the object of interest, not a circle around a
centroid — and it needs no schema amendment.

But this is schema semantics and therefore yours. **I have changed nothing.**

---

## B3 — The grid peak sits 10.65 km from the stated centroid

**Owner:** Akshat · **Severity:** MEDIUM

### Evidence, measured from Anushka's published `origin.json`

| Property | Value |
|---|---|
| Grid | 120 × 120, row 0 = north |
| Bounds | W −79.88669, S 28.55414, E −79.53889, N 29.61825 |
| Stated `centroid` | `[-79.73175, 29.03215]` |
| **Computed peak cell** | row 56, col 70 → **`[-79.68210, 29.11749]`** |
| **Peak-to-centroid** | **10.65 km** |
| Aspect ratio (probability-weighted 2nd moments) | **3.68 : 1** |
| Major-axis bearing | **170.1°** from north |
| `radius_50_km` / `radius_90_km` | 13.1 / 31.11 |

### Why it happens

The cloud is a long, curved streak, not a blob. On a curved or skewed distribution the centre of
mass is not the mode. A 3.68:1 streak with a bend will put the two 10 km apart routinely.

The bearing of 170.1° — near north–south — is consistent with Gulf Stream advection, and the
backward-drift direction checks out (150 km northward in ~20 h = 2.08 m/s, Gulf Stream core speed).
So the shape is physically right; it just is not a circle.

### Why it matters

Three components need a reference point: `proximity` (which uses the grid directly, so unaffected),
`trajectory` (bearing *toward* what?), and the reported `closest_km` (B2). Today `trajectory`
measures toward the centroid.

This is also a second independent confirmation of **D8**. A 3.68:1 cloud whose peak is 10.65 km off
the centroid is exactly the geometry for which r50-circle membership produces the wrong candidate
set — and on this run the plausible set was cut from 26 to 2 by grid probability, not by radius.

### Ask

State the reference point once, in §6.5 or §6.7, and I will make every component honour it.
My preference is the peak, for the same reason as B2.

---

## B4 — The `cases/case-000-*` fixtures cannot be scored

**Owner:** Jaiveer (replaced) · **Severity:** MEDIUM

### What

The synthetic test bundles in `cases/` cannot be run against any AIS data the repo holds.

### Evidence

`cases/case-000-gfw` has its origin at **lon 80.347…80.947, lat 13.163…13.763** — the Bay of Bengal
— with a window of **2017-01-28**. The only AIS parquets we hold are Galveston 2023 and the
Jacksonville 2024 extract. Running the scorer against it gives:

```
funnel  987 -> 0 -> 0 -> 0
ABSTAINED   no vessel entered the reconstructed origin during the window
```

### Why it matters

**That output looks like a pass and tests nothing.** No vessel was scored, so no component was
evaluated, so the `gfw_hourly` gating those fixtures exist to verify was never exercised. Anyone who
has "tested" against these has tested only that the scorer does not crash on an empty set.

### Fix

Built matching fixtures under `pipeline/attribute/fixtures/` at the generator's default location
(Galveston, `-94.35, 29.00`, `2023-01-25T23:00Z`), which is where `data/ais/gulf.parquet` actually
holds data. `case-gfw-fake` produced `funnel 987 → 897 → 17 → 3` with `gap` and `slowdown` correctly
`null` — see A9 for the output.

### Note

Flagging rather than fixing `cases/case-000-*` because those are not my files.

---

## B5 — 149 validator warnings on the hero case

**Owner:** Akshat + Anushka · **Severity:** HIGH

### Evidence

`python scripts/validate_case.py cases/case-jacksonville-2024` returns **PASS with 149 warnings**,
all of two forms:

```
WARN  particles_forward.json/positions[96]: [-78.6412, 31.33272] falls well outside the scene bounds
WARN  origin.json/centroid: [-79.73175, 29.03215] falls well outside the scene bounds
```

### Why they are not errors

Both are inevitable consequences of the case's own design:

- The scene box is a **0.03° pad around the slick** (`bounds.json`: W −79.6782 → E −79.5914,
  S 30.2139 → N 30.5541), deliberately tight because at 10 m across two float32 bands a wider box
  exceeds GEE's 48 MiB direct-download ceiling (**D14**).
- The origin is **170 km away**, and `particles_forward` runs further still.

A `trace` output that stayed inside the scene bounds would mean the drift model had not moved
anything. **The check is wrong for trace layers, not the data.**

### Why it matters

149 warnings on the default case in `index.json` is the first thing any reviewer sees. "PASS with 149
warnings" reads as a system nobody is maintaining, even when every warning is spurious.

### Options

1. Scope the scene-bounds check to `detect` outputs only.
2. Compare trace layers against `origin.bounds` rather than `bounds.json`.
3. Accept it and explain 149 warnings on stage.

`scripts/validate_case.py` is not my file, so this is yours and Anushka's.

---

## B6 — `acts_available` excludes `attribute` on all six cases  ⚠ BLOCKER

**Owner:** Akshat · **Severity:** BLOCKER · **Decision needed before Monday afternoon**

### Evidence

Every real case, including the hero:

```json
"acts_available": ["detect", "trace"]
```

### Why it matters

Two consequences, both bad:

1. **Harshita's Attribute panel does not switch on.** Stage 3's output is in the bundle and
   validates, but the frontend gates on `acts_available`.
2. **The validator does not check Stage 3's output.** This is how `main` carried no `score.py` for
   several hours and still printed PASS (D6 below) — nothing was looking for the files.

`meta.json` is shared, so this is your edit and not mine.

### Ask

Add `"attribute"` to `case-jacksonville-2024` tonight or first thing Monday, and to Huntington,
Gulf of Alaska and Farallones as each lands Monday morning.

---

# C · Blocked on teammates

## C1 — `parity` returns `null` everywhere  ⚠ BLOCKER

**Owner:** Soumirya · **Severity:** BLOCKER

### Evidence

On the real Jacksonville run, both suspects:

```
"parity": null
"component_notes.parity": "slick is unknown — parity needs a linear slick with a centerline"
```

Same on every synthetic fixture.

### What parity does, and why losing it hurts most

`parity` asks whether a vessel travelled **along** the slick's long axis or **across** it. A vessel
discharging while under way lays the oil down in a line behind itself, so the slick's major axis
should be parallel to the vessel's course. A vessel that merely passed nearby cuts across it.

This is the **only component that separates a source from a passer-by on geometry alone**.
`proximity` says a vessel was near the oil; so were all the others in the lane. `trajectory` is
near-tautological (A5). `gap` and `slowdown` are behavioural and often unmeasurable. Parity is the
one that answers *"did this vessel draw this shape?"*

### Second-order value

Per A10 Route B, the same polygon also unlocks the head-proximity form of `temporality`, which works
on `bounded` cases. **One delivery, two components, across the whole library.**

### Ask

The highest-value outstanding dependency in Stage 3. Even a rough polygon on one case would let me
prove the component works. A stub with a plausible centreline would let me prove the *plumbing*
works, which is worth having before freeze even if the numbers are not real.

---

## C2 — `ship_detections` cannot support the dark-vessel gates

**Owner:** Soumirya · **Severity:** HIGH

### What

§6.3 defines `ship_detections` entries as `lon, lat, px_area, peak_db`.

Phase 3.3 gates dark-vessel candidates on **">30 m estimated length, high confidence"**, and §6.7
requires an `est_length_m` field on every dark-vessel suspect.

**Neither `est_length_m` nor any confidence field exists in the produced data.**

### Why it matters

`case-gulf-alaska-2023` is the dark-vessel case, and per A1 it is now also the intended home for the
gap narrative. Without a length estimate the module cannot gate, and without gating it will report
every radar contact — including buoys, platforms, and speckle — as a candidate dark vessel.

### Options

1. **Soumirya adds `est_length_m` and a confidence score** to `ship_detections`. Cleanest.
2. **I derive length from `px_area` plus the pixel scale** and ship with no confidence gate. Possible
   — `bounds.json` carries `width_px` / `height_px` so the ground sample distance is recoverable —
   but it makes **D5 materially worse**, because an underived confidence gate means we cannot say
   which contacts we trust.
3. Drop the dark-vessel module and lose the Alaska story.

### Ask

Choose one. Option 2 is achievable by me alone if you rule for it, so it is the safe fallback — but
you should rule on it knowingly rather than have it happen by default.

---

## C3 — `discharge_class` disagreement

**Owner:** Soumirya / Anushka · **Severity:** MEDIUM

### What

`main` carries `discharge_class: unknown`. Anushka has stated the Jacksonville slick is `chronic`.

### Why it matters

`component_parity` is gated on `discharge_class` — the parity argument only holds for a discharge
laid down by a moving vessel. It also gates Phase 7 (chronic vs acute). With `unknown`, both stay
off regardless of what else lands.

### Ask

Establish which is correct and get it into the bundle. This is cheap and it unblocks two phases the
moment C1 lands.

---

## C4 — GFW acquisition path is unscoped

**Owner:** Akshat · **Severity:** HIGH · **Decision needed before Monday afternoon**

### What

`case-mumbai-2023` and `case-jamnagar-2024` both carry `ais_source: gfw_hourly`. NOAA Marine
Cadastre covers US waters only, so neither can use the ingest path every other case uses.

**Nobody has specified how we obtain Global Fishing Watch data** — API access, credentials, rate
limits, or the format it arrives in.

### Why it matters

Two of six cases — a third of the library, and the entire Indian-waters half of the demo narrative,
which matters for an NTRO problem statement. If there is no path, both ship with `detect` and `trace`
only.

The scorer side is ready: the `gfw_hourly` gating is now tested and works (A9). The blocker is
purely data acquisition.

### Ask

Either point me at the access path, or confirm both cases ship without Attribute so I can plan
around it and say so in the writeup. **A "no" answered tonight is worth more than a "maybe" answered
Monday.**

---

# D · Documentation and process

## D1 — Blind evaluation does not hold for four of six cases

**Owner:** Akshat · **Severity:** HIGH · **Ruling:** D31

### What

D21 establishes that the answers live in a sealed file only you hold, so that weights are not tuned
toward known outcomes. That protection does not currently hold.

### How it is broken, in two distinct ways

**Cases 1 and 2 — the MMSIs are printed in Part 3.2.** Anyone reading the master plan has the
answer. I have read the master plan.

**Cases 4 and 5 — the dark-vessel coordinates are printed.** This is worse, because a dark vessel
has no name and no MMSI to withhold. The only possible answer to "who did it" *is* a position. For
these cases the printed coordinate is not a partial leak — it is the entire answer.

**Case 3 is non-blind by construction.** The Menuett density check sorts vessels by report count, so
finding the vessel *is* the check. This one cannot be fixed by scrubbing a document.

### Why it matters

A claimed blind evaluation that turns out not to be blind is worse than never claiming one. If a
panel member opens the plan in December and finds the MMSIs, the credibility loss extends well
beyond the evaluation number.

### Options

1. **Scrub and reissue** — move the MMSIs and coordinates into `ANSWERS.md`. Only works going
   forward: I have already seen them, so those cases cannot be my blind test even after a scrub.
2. **State it openly** — *"positions for cases 4 and 5 were disclosed in the planning document; the
   dark-vessel result is therefore not blind"* — and report the blind figure only over the cases
   where blindness held.

**My preference: 2, plus 1 for the future.** Less impressive and completely defensible.

Either way it must be one of them. Leaving it unstated is the only genuinely bad option.

---

## D2 — Master Part 3 is stale on Menuett and on distance

**Owner:** Akshat · **Severity:** MEDIUM

Two factual corrections, both established by measurement (A1):

1. Jacksonville is described as *"the only case that exercises gap detection"*. It is not a gap case.
2. Part 3.2 gives the distance as ~100 km offshore. The AIS-density check measured **170 km**.

The corrections are already recorded in `cases/case-jacksonville-2024/meta.json`, but the master plan
is what people read.

---

## D3 — Decision numbering has diverged

**Owner:** Akshat · **Severity:** MEDIUM

`docs/00_MASTER_PLAN.md`'s decision table ends at **D22**. Your handoff and
`cases/case-jacksonville-2024/meta.json` both cite **D30** and **D31**.

So there are rulings in force that do not appear in the document people treat as the source of
truth. Either there is a newer plan I have not been sent, or D23–D31 exist only in the case metadata.

Being two versions behind on the master plan cost me a day on the 11th, which is why I am raising a
numbering gap rather than assuming it is cosmetic.

**Ask:** reconcile the table, or tell me which document is authoritative.

---

## D4 — `component_notes` is unblessed

**Owner:** Akshat · **Severity:** HIGH · **Decision needed before Monday afternoon**

### What

`score.py` emits a `component_notes` object on every suspect — one short string per component, giving
the measurement or the reason the component was gated. It is **not in §6.7**.

### Examples, from the real Jacksonville output

```
"trajectory": "on approach 31 km out, course 168 deg against 186 deg toward the origin (17 deg off)"
"gap":        "longest silence overlapping the window: 2 minutes"
"slowdown":   "12.0 kn at closest approach against an under-way median of 12.5 kn"
"parity":     "slick is unknown — parity needs a linear slick with a centerline"
```

### Why it earns its place

D9 requires that applicability be *"a stated rule, never a quiet conditional"*. `component_notes` is
what makes that statement visible on the card rather than buried in an `if`. It is also most of the
answer to A7 and A9 — it is how a viewer sees *why* one vessel outranked another, and *what* the
scorer could not measure.

### Identity-leak check

Re-verified on the Jacksonville run and on the earlier 17-vessel set: **zero vessel names, zero
MMSIs** across all notes. `score.py` never reads IMO or callsign. Every value is derived from the
same AIS the card already cites.

### Ask

Bless it into §6.7 or tell me to drop it. **Harshita needs to know before she lays out the card**,
which is tonight or tomorrow morning, not Monday evening.

---

## D5 — Two unrelated 40s in the abstain logic

**Owner:** Akshat · **Severity:** LOW

The origin-diffuseness abstain trigger is `radius_90_km > 40` — **40 kilometres**.
The density abstain trigger is `ABSTAIN_MAX_VESSELS = 40` — **40 vessels**.

Two unrelated quantities with the same magic number, in adjacent code paths. Nothing is wrong today;
it is a maintenance trap and a confusing thing to explain on stage.

**Half done.** I have renamed the one that lives in my file: `ABSTAIN_MAX_VESSELS` is now
`ABSTAIN_MAX_PLAUSIBLE_VESSELS`. The 40 km cloud-diffuseness trigger comes from the master plan, so
renaming that one is yours.

---

## D6 — The first merge into `main` took an earlier commit, not the branch tip

**Owner:** resolved · **Severity:** MEDIUM

### What happened

The first merge of `jaiveer-phase2` into `main` picked up an earlier commit. For several hours
`main` carried `geo.py` and the updated `ingest.py` but **no `score.py`**, no
`docs/_archive/jaiveer/stage3-progress-2026-09-13.md`, no `STAGE3_COMPONENT_REPORT.md`, and older `tests.py` and
`make_fake_case.py`. Your second pass (`14196b7`) resolved it.

### Why it is worth recording

**`main` still validated PASS the whole time.** Because `acts_available` excludes `attribute` (B6),
the validator never looks for `suspects.json` or `vessels.geojson` — so an entire missing stage was
invisible to our only automated check.

That is the real lesson here, and it is B6's second consequence: **the validator cannot catch a
missing stage it has not been told to expect.** Worth a line in the runbook.

---

# E · Scope

## E1 — Phases 4, 5, 6 and 7 will not ship

**Owner:** Akshat · **Severity:** HIGH

With 31 hours to freeze, these will not land:

| Phase | Reason | Blocked on |
|---|---|---|
| 4 · Infrastructure source association | Not started; Huntington needs it for full value (D10) | Me — time |
| 5 · Traffic prior | Not started, lowest value of the four | Me — time |
| 6 · Repeat offenders | Structurally undemonstrable (A8) | Nothing — the library has no overlap |
| 7 · Chronic vs acute | `discharge_class` unknown (C3), `age_method: none` everywhere (B1) | Soumirya, Anushka |

**Three of the four are blocked on someone other than me**, and A8 is blocked on the case library
rather than on anyone.

### What will ship

Phases 0, 1, 8, 9 and most of 10: the scorer complete and tested, real attribution output on up to
four real cases, the injected-offender evaluation curve, and cross-platform determinism (R10 closed).

### Ask

Build the demo narrative around what exists, and do it now rather than Monday night. A phase openly
dropped on Sunday is a plan; a phase quietly missing on Tuesday morning is a problem.

---

# Appendix — what I need decided, by when

| When | Items | Why the deadline |
|---|---|---|
| **Tonight / Monday 09:00** | **B6** (`acts_available`), **C4** (GFW path), **D4** (`component_notes`) | Harshita is building now; C4 determines whether Monday evening has work in it |
| **Monday afternoon** | **A9** (confidence display), **B2** (`closest_km`) | Both are card-layout changes and both need frontend time |
| **Monday evening** | **A1**, **A5**, **A8**, **B3**, **B5**, **D1**, **D2**, **D3** | Documentation and narrative; no code depends on them |
| **Whenever** | **C1**, **C2**, **C3**, **B1** | Not yours — they need Soumirya and Anushka; I need visibility, not a decision |

**Reproduction for everything in this document:** see §9 of
`docs/_archive/jaiveer/stage3-progress-2026-09-13-evening.md`. Every figure here is measured, deterministic, and
re-derivable from the repo at `jaiveer-phase2` @ `d39e619`.
