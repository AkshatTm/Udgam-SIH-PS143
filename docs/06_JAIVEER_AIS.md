# JAIVEER — Stage 3: Attribution
*v2. Read with 00_MASTER_PLAN.md. Organised in phases, not days.*

> **This stage is the centrepiece of the project.** The problem statement is named after it. It is the moment a judge sees a ship on screen. Detection and drift are the setup; this is the punchline. Everything below assumes that.

---

# PART A — WHERE YOU STAND

## A1. What you built, and why the data engineering is genuinely strong

**Filter-on-scan with DuckDB.** 800 MB CSV to 10.9 MB Parquet, ~73× compression, with the `WHERE` applied *during* the file scan so peak memory is the size of the result rather than the file. You avoided the documented laptop-killer (`pd.read_csv` on a full NOAA day) by inverting the order of operations rather than by buying more RAM. That is the right instinct.

**Track reconstruction on real data.** 677,093 rows, 987 MMSIs, 972 usable tracks, median reporting interval 71 seconds — consistent with Class A transponders reporting every 2–10 s underway and every 3 minutes at anchor across a mixed fleet. You checked that the number made physical sense rather than just recording it.

**The 30-minute interpolation ceiling, and the reasoning behind it.** *A long transponder silence is evidence, not a hole to patch.* Interpolating across a three-hour gap manufactures positions that never happened, and one of those fabricated points could land inside the origin cloud and score a vessel as a suspect. The system would then be accusing a ship on the strength of a line we drew ourselves. Your ceiling sits at roughly 25× a normal reporting interval, so it fires only on genuine silences. This is the same instinct as Anushka's abstain flag and it is what makes the project defensible.

**MMSI stored as VARCHAR**, deliberately, because it is an identifier and not a quantity — arithmetic on it is always a bug, and forcing the type at read time stops the string round-tripping through an int.

**Sentinel handling.** AIS encodes *unknown* as an in-range value, not a blank: SOG 102.3, COG 360.0, Heading 511. You found that **COG's sentinel affects 9.9% of rows** — that one would have silently become a measurement and poisoned every trajectory calculation.

**The fleet analysis is the most useful thing you produced, and it is a research result.** You took a specification written before anyone had seen real AIS, measured it against a real fleet, and found it wanting:
- 41.6% of vessels are tugs and tows, scored identically to sailing yachts
- 70.5% land in the `other` bucket, so `type_prior` barely discriminates
- 50% of tracks average under 0.5 knots all day — a port, not a shipping lane
- **64% of what the `gap` component catches is a docked boat whose transponder idled overnight.** The worst gap in the dataset, 996 minutes, belongs to a vessel averaging 0.01 knots. It never moved.
- **`slowdown` cannot fire for 66% of the fleet** (median SOG exactly 0), and where it does fire it mostly catches vessels arriving and mooring — the most ordinary thing a ship does in a harbour.

That is a proper measurement-against-specification exercise, and it is why the scorer you are about to write will be good rather than plausible.

## A2. What you flagged

| # | Item | Where handled |
|---|---|---|
| R1 | Scoring does not exist — dominates every other risk | Phases 1–2 |
| R2 | `gap` and `slowdown` misfire on port traffic | Phase 1.3, applicability gating |
| R3 | 13% of tracks truncated by the box edge | Phase 1.7 |
| R4 | Non-consecutive days merged would fabricate gaps | Phase 9.1, hard check |
| R5 | First contact with a real `origin.json` | Phase 9 |
| R6 | Origin cloud is a streak; scoring assumes a circle | Phase 1.2 — **Akshat has ruled: score the grid** |
| R7 | No test suite | Phase 0.3 |
| R8 | Raw AIS on one laptop, Parquet not backed up | Phase 0.5 |
| R9 | Every figure is Galveston-specific | Phase 10 |
| R10 | Reproducibility unverified | Phase 10.3 |

## A3. Problems I found that nobody raised

**Push your branch. Today.** All of Stage 3 is uncommitted or unpushed. As far as the team can see, this stage has not started — which is both a coordination problem and a single-laptop catastrophic risk.

**The `case-000` origin is over India and your AIS is US 2023.** Scoring against it returns zero of everything, which reads exactly like broken code and is not. A US-located fake origin is a 30-minute unblock and it has been the actual blocker on starting Phase 1.

**You have no test suite while Stage 2 has 20 assertions that caught a real 10× error before a single particle moved.** Your synthetic-CSV harness already produces known answers — committing it as `tests.py` is roughly an hour and it is the highest-leverage hour in your lane.

**Your closest-approach calculation will be wrong at the wrong moment.** Distance between two lat/lon points using naive Euclidean geometry is fine over 5 km at Galveston and wrong enough to matter over 50 km, and it fails differently at different latitudes. Use haversine or a local projection everywhere, once, in a helper.

**Nobody has told you the most important geometric fact in your stage.** For a chronic slick, the end nearest the vessel is the **head** — the freshest oil, released most recently. The far end is the oldest. Distances and timings should be computed against the **head**, not the centroid. Cerulean does this and it is the difference between a scorer that works on linear slicks and one that doesn't. See §B3.

---

# PART B — THE METHOD

## B1. What this stage does, plainly

Anushka hands you a patch of ocean and a window of time — the place and period the oil most likely entered the water. You find every vessel that was in that patch during that window, score them on evidence, and produce a ranked shortlist plus a list of vessels you explicitly ruled out and why.

**No machine learning.** Every number on a suspect card traces back to an arithmetic step, which is the point: we can tell a panel exactly why a vessel ranked where it did. A classifier could not.

Three things make this stage hard and interesting:
1. The origin is a **probability field**, not a point, so "was it near?" is a weighted question.
2. Vessels lie, or go silent. **A gap is evidence, not missing data.**
3. There are three kinds of culprit — a broadcasting vessel, a **dark vessel**, and **fixed infrastructure** — and the system must be able to say which.

## B2. The four source types *(this is new and it matters)*

The reference system in this field, SkyTruth's Cerulean, runs separate source-association algorithms per class. Ours must too, because **two of our six cases are not a vessel at all, and one carries three source types simultaneously.**

| Source type | What it means | Our case |
|---|---|---|
| **Broadcasting vessel** | A ship with AIS on, near the origin, at the right time | Menuett, Panagia |
| **Dark vessel** | Radar sees a ship; AIS reports nothing there | **Alaska** — real, and our best technical differentiator |
| **Fixed infrastructure** | A pipeline, platform or wreck — stationary, not a vessel | **Huntington Beach**, and one of Mumbai's |
| **Natural seep** | Geological seepage — oil nobody spilled | flagged on **Mumbai** |

**A system that can only consider vessels will name a vessel even when the source is a pipeline.** That is a false accusation and it is the worst failure mode you have. So source classification runs *before* attribution:

```
origin reconstructed
  → fixed infrastructure at the origin?   → infrastructure
  → known natural seep area?              → natural_seep
  → radar ship with no AIS?               → dark_vessel
  → otherwise score the AIS fleet         → vessel
```

Without it the correct answer on Huntington Beach is "no vessel is responsible", which reads as a failure. **With it, the answer is "the source is fixed infrastructure at this location, and all transiting vessels are excluded" — which is a hit**, and the verification screen then tells the anchor-strike story on top of it.

`natural_seep` exists because Cerulean flags the Mumbai detection as sitting in a known seep area. Presenting a case where the honest answer includes *"some of this may be geological"* is a credibility move, and separating seeps from discharges is a real enforcement problem. It is a **flag on the finding, not a ranked suspect** — you never score a seep, you report that the area has documented seepage and that it bears on interpretation.

Emit `source_type` in `suspects.json` per finding: `vessel | dark_vessel | infrastructure`, plus the `natural_seep` block when flagged.

**On stage:** *"Before we name a ship, we ask whether a ship is even the right kind of answer."*

## B2b. Two AIS regimes, and the scorer must know which it is in

`meta.ais_source` is `noaa_dense` or `gfw_hourly`, and it is **required** on every case with `attribute`.

| | NOAA Marine Cadastre | Global Fishing Watch |
|---|---|---|
| Interval | **~71 s median** — you measured this | **one position per vessel per hour** |
| Cases | Menuett, Panagia, Huntington, Alaska | Mumbai, Jamnagar |
| Coverage | US EEZ only | global; 400k+ vessels, the majority non-fishing |

At 12 knots a ship covers about **22 km in an hour**. So on a `gfw_hourly` case:

| Component | Status |
|---|---|
| proximity | Applicable, but precision drops to tens of km. **Do not interpolate to compensate** — that invents positions, which is exactly what your 30-minute ceiling already refuses to do |
| trajectory, parity | **Applicable.** Direction over hours is robust |
| temporality | Applicable, coarse |
| **gap** | **Structurally impossible.** You cannot see a 30-minute silence in hourly data. Returns `null` |
| **slowdown** | **Not applicable.** Returns `null` |
| type_prior | Applicable |

`null`, never zero — a zero says *"we measured this and it scored nothing"*, which is a different and false claim. The remaining weights renormalise, exactly as they do for your port-traffic gating.

**Say it on the limitations slide:** *"attribution confidence depends on AIS sampling density, and we state which source each case used."* That is a stronger position than pretending the two are equivalent.

**One correction to carry about GFW.** A report in circulation claims the AIS Vessel Presence dataset returns MMSI, name, IMO and positions. **It does not** — GFW's own documentation says it *"shows vessel presence patterns and movement corridors, but does not provide individual vessel positions."* It is a gridded layer on the 4Wings tile API. For tracks use the **Vessels API**; for behaviour use the **Events API**, which includes **AIS-disabling events** computed on GFW's full-resolution underlying data — so gap analysis may still be reachable through that endpoint even though it is impossible from the hourly presence layer. **Test that.** There is also a **SAR vessel detections** endpoint flagging non-broadcasting vessels: use it to *validate* your dark-vessel module, never to replace it, because building it ourselves is the differentiator.

**A cheap, high-value measurement.** Take the dense NOAA data from Menuett, downsample it to one position per hour, and re-run the scorer. That turns a caveat into a number — *"at hourly sampling the correct vessel fell from rank 1 to rank N, and the gap component became unavailable"* — and it adds sampling density as a third axis to your evaluation curve alongside traffic density and cloud size.


## B3. What we take from Cerulean, and what we do differently

**Prior art, stated first.** SkyTruth's Cerulean is a global, operational system that detects slicks in Sentinel-1 with a ResNet34-based U-Net and attributes them to AIS-broadcasting vessels. It is excellent and a judge may name it. Never pretend it doesn't exist.

### Three metrics worth taking outright, with attribution

Cerulean scores each nearby AIS track against the **centerline of the slick** on:

> **Parity** — compare the length of the slick to its projected length along the AIS track. This measures how *parallel* the vessel's path is to the slick. Greater parallelism, higher score.
>
> **Proximity** — the distance from the **head of the slick** to the nearest point on the vessel's track. Closer, higher score.
>
> **Temporality** — the timestamp of the AIS broadcast that is spatially closest to the head of the slick. This estimates when the vessel was last polluting. The nearer that is to the image time, the higher the score.

**Parity is the idea worth stealing most.** None of your five specified components asks whether the track *geometry* matches the *slick geometry*. A vessel that happened to be close but crossed the slick perpendicular is a much weaker candidate than one that ran along it — and only parity captures that.

Their **dark vessel** module restricts to objects over 30 m estimated length, detected with high confidence, within 50 km of the slick, then scores on distance plus **angular deviation from the predicted path**, where the path is estimated at each end of the slick from the centerline. Take those parameters as a starting point rather than inventing your own.

Their **infrastructure** module finds points along the slick perimeter far enough from the centre to be a plausible terminus, then applies a distance decay so points nearer the terminus get higher probability. That is directly reusable for Huntington Beach and for Mumbai's infrastructure source.

Also worth noting: Cerulean only evaluates **long, linear detections** for vessel association, since that is the expected shape for a transiting-vessel slick. That independently validates Soum's `discharge_class` split — a blob should not be run through the vessel scorer at all.

### The four ways we differ — this is your slide

1. **We run the physics backwards.** Cerulean pulls AIS from 8 hours before the image to 6 hours after — it matches a slick to a *coincident* track. That works when the satellite catches the vessel in the act. **It cannot attribute a slick found days after release.** We reconstruct an origin cloud and time window from drift physics, so our AIS search is anchored to *when the oil entered the water*, not to when the picture was taken. That is the whole reason this problem statement exists: Sentinel-1's revisit gap means we usually see slicks late.
2. **We use VV and VH.** Cerulean's detection model runs on the VV polarisation alone. Soum's finding is that VH is the strongest single discriminator between oil and look-alikes.
3. **Free public AIS.** Cerulean uses commercial AIS (Spire, via Global Fishing Watch). We use NOAA Marine Cadastre, which is public domain and requires no account — which matters for a system anyone should be able to run.
4. **We publish exclusions.** We say who we ruled out and why. That converts the output from an accusation into an investigative shortlist.

**Their disclaimer is also our template.** Cerulean states plainly that it is not possible to definitively identify oil slicks from SAR alone, and that its detections should be considered *potential* slicks. If the leading operational system says that, we say it too — and it costs us nothing because "leads, not verdicts" was already our line.

## B4. The scoring model

### Components, weights as named constants at the top of the file

```python
W_PROXIMITY   = 0.30   # origin-grid probability density at closest approach
W_PARITY      = 0.15   # track/slick parallelism        (chronic only)
W_TEMPORALITY = 0.15   # how close in time to the release window
W_TRAJECTORY  = 0.15   # heading consistent with being the source
W_GAP         = 0.15   # AIS silence overlapping the window
W_SLOWDOWN    = 0.05   # unusual slowdown near the origin
W_TYPE_PRIOR  = 0.05   # tanker/cargo over ferry
```

Note the change from v1: **proximity drops from 0.40 to 0.30 and the freed weight goes to parity and temporality** — geometry and timing are stronger evidence than raw closeness, which is what Cerulean's design implies and what your fleet analysis supports.

### Proximity — score the grid, not the circle
Anushka measured the real origin cloud at aspect ratio **4.38 : 1**, with **44.7% of high-probability mass falling outside the r50 circle**. Circle membership would name vessels sitting in near-empty water inside the circle and exclude vessels sitting in the bright streak just outside it.

**Sample `origin.json`'s 120×120 probability grid at the vessel's position.** The grid, its bounds and its orientation are all in the file, and **row 0 is NORTH**:
```
row = (north - lat) / (north - south) * (rows - 1)
col = (lon - west)  / (east  - west ) * (cols - 1)
```
Take the maximum grid value the vessel touches during the time window. Since the grid is normalised to peak 1.0, that value *is* the proximity score, 0–1, no further scaling.

**Do not** discard `radius_50_km` / `radius_90_km` — they remain the right one-number summary for the UI and the deck. They are just the wrong instrument for a membership test.

### Applicability gating — stated rules, never quiet conditionals
Your measurements say the v1 spec fails on port traffic. The fix is not reweighting; it is **defining when a component is applicable**.

- **`gap` applies only when the vessel was under way on both sides of the silence.** A parked boat whose transponder idled overnight is not going dark; it is moored.
- **`slowdown` is scoped to the closest approach to the origin**, compared against an **under-way median** that excludes hours at rest. Comparing against a median of exactly 0.0 is unreachable by construction.
- **`parity` applies only when `discharge_class == "chronic"`.** A blob has no meaningful centerline.
- **When a component is not applicable it contributes nothing, and the remaining weights renormalise.** Say that out loud on the limitations slide. It is a statement about applicability, not a thumb on the scale.

Emit which components fired per suspect, so the frontend can show the reasoning and a judge can audit it.

### The funnel — requirement (c), made visible
```
in_region   distinct MMSIs inside the search box
in_window   ...also present during the origin time window
plausible   ...whose closest approach touches non-negligible grid probability (> 0.05)
scored      top 3 by score
```
Must decrease monotonically; the validator enforces it. **Also report `dropped_short_track`** — vessels excluded for fewer than 5 reports — so no hidden assumption sits under the funnel.

### Exclusions — mandatory, at least one per case
Among the plausible-but-not-top-3, pick vessels with a clear disqualifying reason and state it in plain language:
- *"heading away from the origin throughout the window"*
- *"left the region before the origin time window opened"*
- *"track runs perpendicular to the slick axis"* (parity ≈ 0)
- *"no transponder gap and continuous coverage through the window"*

This is what makes the system read as narrowing rather than accusing, and it is the natural answer to the hardest question we will face.

### Abstention — build the refusal in
Return zero suspects, with the funnel still populated, when any of:
- `origin.abstain == true` from Stage 2 (validator enforces this)
- more than ~40 vessels in the plausible set — density too high for discrimination
- the top score is below a floor (say 0.25), or the top two are within a few percent of each other

Message: *"attribution not possible at acceptable confidence."* Building in the refusal is a maturity signal and it is one of the states we most want to demonstrate.

---

# PART C — THE PHASES

## PHASE 0 — Unblock yourself, and one task that blocks the whole team

### 0.0 THE BLOCKING TASK — verify NOAA AIS density at Menuett
**Do this before anything else in this document.**

Menuett is the hero case: `2024-07-30 23:21:29 UTC`, **30.384 N −79.634 W**. That is roughly **100 km off Jacksonville**, and NOAA Marine Cadastre is built primarily on **terrestrial AIS receivers**, whose coverage thins with distance from shore.

Pull the NOAA file for 2024-07-30, filter to a box around that position, and **count distinct MMSIs**.

- A few hundred vessels with dense reporting → the hero case is confirmed. Tell Akshat, carry on
- A handful of positions → **the hero case has no AIS.** Panagia becomes hero, Alaska moves up, and the presentation order reshuffles

This is the only open item in the whole project that could still force a replan. Twenty minutes, and three other people are waiting behind it.

### The rest of Phase 0 *(about an hour)*

0.1 **Push branch `jaiveer`.** All of it — `ingest.py`, `tracks.py`, `plot_tracks.py`, the update log, the report.
0.2 **Build a US-located fake origin.** Copy `case-000/origin.json`, move `bounds`, `centroid` and `time_window` into your Galveston box on 25 Jan 2023, keep the grid shape. Now Phase 1 is testable today without waiting for anyone.
0.3 **Commit the synthetic-CSV harness as `pipeline/attribute/tests.py`** with real assertions — the ten one-off checks from your report become ten permanent tests.
0.4 Post the track-check plot in the group.
0.5 **Back up `gulf.parquet` to Drive.** It is 10.9 MB and it represents an 800 MB download.

---

## PHASE 1 — The core scorer

### 1.1 Geometry helpers, once
Haversine distance, bearing, point-to-segment distance, and lat/lon ↔ local metres. Put them in one module and use them everywhere. This is where silent errors live.

### 1.2 Grid sampling
Per §B4. Write a test that samples a known grid at a known position and returns the expected value, including a check that **row 0 is north** — Anushka's test 5d exists because an upside-down grid validates cleanly and points at the wrong water.

### 1.3 The seven components with applicability gating
Per §B4. Each returns `(score, applicable)`, never a silent zero — a zero and a not-applicable are different things and conflating them is a scoring bug.

### 1.4 Closest approach
For each vessel, walk its track through the origin time window and find the point of maximum grid probability. Record position, time, distance to origin centroid (for display), and the grid value (for scoring).

### 1.5 Trajectory consistency
At closest approach, compare the vessel's course over ground to the bearing from its position toward the origin centroid. Within ±60° counts as consistent. Remember COG's 360.0 sentinel means "not available" — treat as not applicable, not as due north.

### 1.6 The funnel, exclusions, abstention
Per §B4.

### 1.7 Box-edge truncation guard
**131 of your tracks (13%) touch a box edge.** For those, the first or last stored position is where the vessel left your rectangle, not where it went. Closest approach and trajectory are both computed from a truncated path and nothing raises.

Mitigation: `--from-origin` already pads to 2 × `radius_90_km`. Add a **flag** on any suspect whose closest approach occurs within one reporting interval of the box edge, and surface it in the reasons: *"track truncated at search boundary — closest approach may be understated."* Honesty about a known limitation beats silently ranking on a cut-off path.

### 1.8 Output
`vessels.geojson` (plausible set only, decimated to ≤500 points, endpoints preserved, `n_points` reporting the *undecimated* count) and `suspects.json`. Validator PASS.

**Checkpoint:** run against the US fake origin and real Galveston AIS. Post the funnel counts and the top suspect's track with its closest-approach point marked.

---

## PHASE 2 — Geometric scoring: parity, head-proximity, temporality

> **WAIT for Soum's `discharge_class`** — his stub lands before his real values, and the stub is enough to build against.

### 2.1 The slick centerline and its head
From Soum's polygon: compute the principal axis, then the centerline as the skeleton or simply the line through the extreme points along that axis. **The head is the end nearest the reconstructed origin** — that is the freshest oil, released most recently. The tail is the oldest.

This matters because a chronic slick can be tens of kilometres long. Measuring distance to the *centroid* of a 30 km streak is close to meaningless.

### 2.2 Parity
Project the AIS track onto the slick's axis. Compare the projected length to the slick's actual length. A vessel that ran along the slick scores high; one that crossed it scores near zero. **Chronic only.**

### 2.3 Head-proximity
Distance from the slick head to the nearest point on the vessel's track. Distinct from the grid-density proximity in 1.4, and complementary — grid density asks "was it in the reconstructed origin", head-proximity asks "was it at the fresh end of the visible slick".

### 2.4 Temporality
Take the AIS broadcast spatially nearest the head. How close is its timestamp to the origin time window? That is an estimate of when the vessel was last discharging.

### 2.5 Cite it
On the methods slide: *"Our geometric scoring follows the parity/proximity/temporality framework published by SkyTruth's Cerulean, applied to a physics-reconstructed origin rather than a coincident AIS track."* Citing prior art and stating what you added is what a researcher does.

---

## PHASE 3 — Dark vessel cross-check *(our best technical differentiator)*

> **WAIT for Soum's `ship_detections`** — his Phase 5.1.

### 3.1 The cross-check
For each radar ship detection, ask whether any AIS track reported a vessel within a tolerance of that position at the scene timestamp. Tolerance should account for the reporting interval — a vessel at 12 knots moves ~370 m in a minute — so use roughly 500 m plus speed × time-since-last-report.

**A ship radar can see but AIS cannot is a dark vessel.**

### 3.2 Why this is the strongest evidence the system can produce
It is **independent** of the drift model, so it does not inherit drift uncertainty. Everything else in this stage is conditioned on Anushka's origin being roughly right; this is not. Next to a fresh slick, a dark vessel is worth more than any proximity score. It is also exactly the capability NTRO cares about — vessels operating dark is maritime domain awareness, and spill attribution is the demonstrator.

And it is visually spectacular: a bright dot on the radar layer with nothing beneath it on the AIS layer.

### 3.3 Scoring, borrowing Cerulean's parameters
Restrict to detections above a size floor (they use ~30 m estimated length) with high confidence, within ~50 km of the slick. Score on distance from the slick plus **angular deviation from the slick's axis** — a dark object aligned with the discharge direction is far more suspicious than one sitting off to the side.

Emit as a finding with `source_type: "dark_vessel"`, `mmsi: null`, and a name like `"Unidentified radar contact"`. **Never invent an identity.**

### 3.4 Handle the false-positive direction carefully
A false ship detection produces a false dark-vessel claim, which is worse than a miss because it is an accusation against nobody with no way to check it. Prefer a high threshold. If Soum's detections look noisy on a case, say so and drop the module for that case rather than shipping a bad claim.

### 3.5 The honest caveat
Legitimate signal loss happens — terrestrial AIS coverage thins offshore, and small vessels are not required to carry AIS at all. **A dark vessel raises suspicion; it is never proof.** That is why it feeds a ranked score rather than a verdict. Raise this yourself before a judge does; it shows you understand the adversarial nature of the problem, which is very much NTRO's world.

Also: AIS-gap analysis as a signal is **established practice in fisheries enforcement**, not our invention. Reframe honestly — *"applying it to spill attribution, where the gap coincides with a physically-derived origin window, is a much stronger inference than a gap alone."* Still a real contribution, and it signals you read the literature.

---

## PHASE 4 — Infrastructure source association *(this turns Huntington Beach into a hit)*

Two of our cases have a **fixed** source: the San Pedro Bay Pipeline at Huntington Beach, and structure 121229 at Mumbai (18.577 N 72.241 E, from Cerulean's record). Without this module the system's answer on both is "no vessel responsible", which reads as a failure. With it, the answer is *"the source is fixed infrastructure at this position, and all transiting vessels are excluded"* — which is correct, and impressive.

**Mumbai additionally carries a natural-seep flag**, so its output is not a single source but a ranked set across three classes plus a seepage caveat. Build for that rather than assuming one winner.

### 4.1 Candidate infrastructure
Public sources: Global Fishing Watch publishes offshore infrastructure locations; NOAA and BOEM publish US pipeline and platform data. For our two cases the location is known from the investigation, so **hardcoding a small per-case candidate list is acceptable** — just declare it in `meta.json` as case input rather than pretending it was discovered.

### 4.2 Terminus scoring
Following Cerulean's approach: find points along the slick perimeter far enough from the centre to be a plausible terminus, then apply a **distance decay** so candidates nearer that terminus get higher probability. Combine with the origin grid — a fixed point sitting in high origin probability with no vessel nearby is a strong infrastructure finding.

### 4.3 The decision rule, stated
Report `source_type: "infrastructure"` when a fixed candidate sits in high origin probability **and** no vessel scores above the floor. Report both when both are plausible; that is a real analytical outcome, not a fudge.

### 4.4 What this lets you say
> *"The origin reconstructs onto the pipeline right-of-way, not onto any vessel track. Every transiting ship in the window is excluded, with reasons. The system's finding is that this was an infrastructure release — which is what the NTSB concluded."*

---

## PHASE 5 — Traffic-density prior

A slick in a busy shipping lane and a slick in empty water mean very different things: many weak candidates versus few strong ones. Straightforward Bayesian reasoning, and it makes the scores meaningful rather than arbitrary.

5.1 Build a lane-density map from the AIS you already have — grid the region, count distinct vessel-hours per cell over the window.
5.2 Use it as a **prior on how much a proximity score should count.** In a dense lane, being near the origin is weak evidence because everyone was near it. In empty water it is strong.
5.3 Emit the density at the origin so the frontend can show it, and so the reasons can say *"origin lies in a low-traffic area; only three vessels were within range."*
5.4 The heat map is also a good visual on its own.

---

## PHASE 6 — Repeat offenders

With five cases you can finally do this. **One event is an accusation; a pattern is a case** — and intelligence rather than forensics is precisely NTRO's business.

6.1 After each case runs, append its scored vessels to `data/attribute/vessel_history.parquet` with case id, score and rank.
6.2 On each run, check whether any suspect appears in another case's scored set. Emit:
```json
"repeat_offender": {"cases": ["case-x", "case-y"], "best_rank": 1}
```
6.3 **Be honest about what this proves.** With five cases and dense shipping, a coincidental repeat is entirely possible — especially for vessels that work a fixed route. Report it as a flag to investigate, never as corroboration. If the same vessel appears twice by coincidence, saying so is better than being caught.
6.4 This is also the natural answer to *"where does this go next"* — the module scales with the number of incidents processed, and a national system would process thousands.

---

## PHASE 7 — Chronic vs acute search strategy

> **WAIT for Soum's `discharge_class`.**

Soum's field changes how you search, and treating every slick identically is what most teams will do.

**`chronic`** — the vessel was **moving**, and the origin is a **line segment**, not a point. Search AIS along that vector. Weight parity and trajectory much more heavily. Expect the culprit to be underway at cruising speed, so `slowdown` becomes less relevant and `gap` more so.

**`acute`** — stationary or instantaneous. Collision, grounding, platform release. Search a point cloud. Parity is not applicable. Expect low speed or a stop, so `slowdown` becomes more relevant.

Distinguishing deliberate discharge from accident is what an enforcement analyst does first, and it carries the strongest line in the whole pitch: **deliberate discharge is a crime, an accident is a misfortune, and the system that tells them apart is the one worth deploying.**

---

## PHASE 8 — The evaluation curve *(your headline number)*

Your weights are chosen. If a judge asks *"why is proximity 0.30?"*, the honest answer is "we chose it" — a weak moment, **unless you have measured what the choice buys.**

We will never have many real incidents with a confirmed culprit — five at most, which is not a sample. So generate the sample.

### 8.1 The injected offender
Take **real AIS traffic** and add a **synthetic guilty vessel** whose discharge point, discharge time, transponder gap, speed profile and manoeuvre you control. Run the scorer. Did it rank first? Top three?

### 8.2 Sweep the conditions
Several hundred scenarios varying:
- traffic density in the search window (5, 10, 20, 40, 80 vessels)
- gap duration (none, 30 min, 2 h, 6 h)
- origin cloud size (r90 from 5 km to 40 km)
- vessel type and speed profile
- whether the offender went dark at all

### 8.3 The curve
> *"Across N injected scenarios on real AIS traffic, the responsible vessel ranked in our top 3 in X% of cases. Performance degrades sharply above roughly 40 vessels in the search window, and above that threshold we abstain."*

**Almost no student team presents a performance curve with a stated operating limit.** It is the clearest available signal of engineering maturity, and the injection generates the data automatically — this is a cheap way to get a real number.

### 8.4 Use it to tune, honestly
This is also the legitimate way to set your weights: pick the ones that maximise top-3 rate on injected scenarios, then report that you did so. That is calibration on synthetic data, disclosed — completely different from adjusting weights until a real case comes out right, which we never do.

### 8.5 The limitation, stated
The injected offender behaves how *we think* an offender behaves. If real polluters behave differently, the curve is optimistic. Say it.

---

## PHASE 9 — The real cases

> **WAIT for Akshat** (case list, dates, bounds, `ais_source`) **and Anushka** (real `origin.json` per case).

### 9.0 The library, and what each case asks of you

| # | Case | `ais_source` | What your stage must do |
|---|---|---|---|
| 1 | **Menuett** 2024-07-30, 30.38 N −79.63 W | `noaa_dense` | **Hero.** The only case where **every** component fires, including `gap` — Cerulean records 1 AIS-off event. This is the case the accuracy claim rests on |
| 2 | **Panagia** 2023-03-17, 37.81 N −123.89 W | `noaa_dense` | Full chain, Pacific. **Hero backup** |
| 3 | **Huntington** 2021-10-02, 33.6 N −118.1 W | `noaa_dense` | **Infrastructure finding + vessel exclusions.** Naming a transiting vessel here would be *wrong* |
| 4 | **Alaska** 2023-05-16, 59.56 N −142.71 W | `noaa_dense` | **Dark-vessel cross-check on real data.** Contact ~4.5 km from the slick |
| 5 | **Mumbai** 2023-09-03, 18.52 N 72.20 E | `gfw_hourly` | **All four source classes at once.** `gap` and `slowdown` return `null` |
| 6 | **Jamnagar** 2024-02-23, 20.15 N 71.90 E | `gfw_hourly` | Undocumented discharge. `gap`/`slowdown` `null`. Anonymise the top candidate on screen |

**Blind evaluation applies to you more than anyone.** Akshat holds the documented answer for every case — vessel names, MMSIs, IMOs — in a sealed file. **You do not get them.** If you knew Menuett was the answer while tuning weights, you would tune until Menuett ranked first. That is not dishonesty, it is what anyone does when the target is visible, and it collapses *"our system identified the vessel"* into *"we tuned it until it did."* A December panel will ask which happened.

Your search box at `2 × radius_90_km` contains the culprit and plenty of decoys anyway. **Tune on the injected-offender curve (Phase 8), never on a real case.** That is calibration on synthetic data, disclosed — completely different from adjusting weights until a real case comes out right, which we never do.

He will not answer *"is this right?"* during the week. That is deliberate.

### 9.1 Download consecutive days
Incident ±2 days. **Never merge non-consecutive days into one Parquet** — `lag(ts)` would compute a three-week interval as a transponder gap for every vessel and `max_gap_minutes` becomes meaningless, so the `gap` component would fire on the entire fleet. Your three files on hand are 25 Jan, 16 Feb, 28 Feb; they must never be ingested together. **Add a hard check in `ingest.py` that refuses inputs more than ~2 days apart.**

### 9.2 Note the window difference from Cerulean
They pull −8 h to +6 h around the image. **Ours is anchored to the origin time window from Stage 2**, which can be up to 24 h before the image, padded. That is why we need multiple days and they do not — and it is exactly the capability that lets us attribute a slick found late. Say so.

### 9.3 Run
`--from-origin cases/<id>/origin.json`. No code changes; that is the seam working.

### 9.4 Read the story before shipping
If your number one suspect is a passenger ferry that never entered the high-probability region, something is buggy — find it before a judge does. Read the reasons out loud. Do they make sense as a narrative?

### 9.5 The honesty rule, binding
Every name and MMSI on screen comes from the real AIS file. **If the documented vessel does not rank top-3, that is the result we show**, and the verification screen says so. We never reweight to force an outcome — internals are binding and we defend these numbers in December.

Expected outcomes to prepare for:
- **Huntington Beach** — infrastructure finding plus vessel exclusions. The anchor strike was eight months before the release, so no vessel was the proximate source at detection time. Naming a transiting ship there would be *wrong*.
- **Alaska** — a dark-vessel finding, and **state the asymmetry in the `reasons` array, not just on a slide**: a vessel dark to Cerulean's *commercial* AIS is a strong claim; a vessel absent from our *free NOAA* archive might be a coverage hole. Two independent absences is evidence. One is not.
- **Mumbai** — expect multiple source types to score at once. The honest output may be *"infrastructure and a dark vessel are both plausible, and the area carries documented natural seepage."* That is a real analytical outcome, not a failure to decide, and it is the best demonstration in the library of why source classification exists.
- **Jamnagar** — no official finding exists, so whatever you produce is a lead with no way to check it. That is exactly why *leads, not verdicts* is the frame. **Anonymise on screen**: mask the MMSI, label it "Vessel A", keep the full data one click away. Naming a real vessel as a polluter with no investigation behind it is a real exposure and you gain nothing from it.

---

## PHASE 10 — Robustness and the numbers

10.1 **Recompute the fleet analysis per case.** Every figure in your report is one box, one day, at the busiest petrochemical port in the US. Fleet mix, parked fraction and gap distribution will all differ. Recompute before any of it reaches a slide.
10.2 **Report `dropped_short_track`** so the funnel has no hidden assumption underneath it.
10.3 **Run once on another machine** to close the reproducibility gap. Stage 2 verified identical output across two OSes; yours has never left one laptop.
10.4 **Instrument peak memory** once, so the "memory is the size of the result" claim is a measurement rather than an inference. You flagged this yourself.
10.5 Assemble the numbers: the evaluation curve with its operating limit, per-case funnel counts, dark-vessel findings, and the exclusion count.

---

# PART D — RISKS

## D1. Scoring does not exist yet *(CRITICAL, loud)*
This dominates everything else in this register. Phases 1–2 are the whole deliverable. Everything from Phase 5 onward is scaling — valuable, and **droppable in this order if time runs short: repeat offenders → traffic prior → evaluation curve → parity/temporality.** Never drop: the funnel, exclusions, abstention, or the grid-based proximity.

## D2. Circle-vs-grid geometry *(HIGH, silent — now fixed by design)*
Fixed by scoring the grid. Since the scorer is unwritten, this costs nothing now and would have been a rewrite later.

## D3. `gap` and `slowdown` on port traffic *(HIGH, silent)*
You measured it: 64% of gap hits are docked boats, and slowdown is inert for 66% of the fleet. Fixed by applicability gating (§B4). **These must be stated rules on the limitations slide, not conditionals buried in an `if`.**

## D4. Box-edge truncation *(MEDIUM, silent)*
13% of tracks. Padding reduces it; the flag makes it visible. Directly analogous to Anushka's field-box edge problem — the same class of bug in two different stages.

## D5. False dark-vessel claims *(MEDIUM)*
An accusation against nobody, unverifiable. High threshold, and drop the module per case if Soum's ship detections look noisy there.

## D6. Non-consecutive-day merge *(MEDIUM, silent)*
Hard check in `ingest.py`. This one would poison the `gap` component across the whole fleet and look like a genuine signal.

## D7. MMSI is not a clean identifier *(LOW, known)*
Reused, spoofed, mistyped, sometimes zero. **Do not build identity resolution** — it is a research project and we have one demo case per incident. Group by MMSI, drop tracks under 5 points, state the limitation. The failure mode is a teleporting track, which the checkpoint plot would reveal.

## D8. Repeat-offender coincidence *(LOW, but it's a credibility risk)*
Five cases and dense shipping means a coincidental repeat is plausible. Present as a flag to investigate, never as corroboration.

## D9. Raw AIS on one laptop *(MEDIUM, total if it fires)*
Three files, 2.4 GB, gitignored by design. The Parquet is 10.9 MB — back it up (Phase 0.5).

## D10. Every figure is Galveston-specific *(MEDIUM, not a defect)*
Stated so nobody lifts a number onto a slide labelled with a different case.

---

# PART E — REFERENCE

## E1. Contract additions for `suspects.json`
```json
{
  "funnel": {"in_region": 412, "in_window": 63, "plausible": 12, "scored": 3,
             "dropped_short_track": 15},
  "suspects": [
    { "source_type": "vessel",
      "mmsi": "367123450", "name": "EXAMPLE STAR", "vessel_type": "tanker",
      "score": 0.82,
      "components": {"proximity": 0.91, "parity": 0.74, "temporality": 0.63,
                     "trajectory": 1.0, "gap": 1.0, "slowdown": null,
                     "type_prior": 1.0},
      "closest_km": 3.1, "closest_time": "2021-10-02T14:20:00Z",
      "grid_probability": 0.91,
      "heading_consistent": true, "ais_gap_minutes": 85,
      "edge_truncated": false,
      "repeat_offender": {"cases": ["case-x"], "best_rank": 2},
      "reasons": ["inside the high-probability origin region during the window",
                  "85-minute transponder gap overlapping the window",
                  "track runs parallel to the slick axis"] }
  ],
  "dark_vessels": [
    { "source_type": "dark_vessel", "name": "Unidentified radar contact",
      "lon": -118.104, "lat": 33.602, "est_length_m": 120,
      "score": 0.71, "angular_deviation_deg": 12,
      "reasons": ["radar detection with no AIS broadcast within 500 m at scene time"] }
  ],
  "infrastructure": [
    { "source_type": "infrastructure", "name": "San Pedro Bay Pipeline",
      "lon": -118.11, "lat": 33.60, "score": 0.88,
      "reasons": ["origin probability peak lies on the pipeline right-of-way",
                  "no vessel scored above threshold"] }
  ],
  "excluded": [
    { "mmsi": "367999999", "name": "OTHER SHIP", "closest_km": 6.4,
      "reason": "heading away from the origin throughout the window" }
  ],
  "abstained": false,
  "abstain_reason": null
}
```
`components` values are `null` when not applicable — **null and zero are different and must stay different.** Clear this schema with Akshat before shipping; it extends the frozen contract.

## E2. Commands
```bash
python pipeline/attribute/ingest.py --csv data/ais/AIS_2021_10_02.csv data/ais/AIS_2021_10_03.csv \
       --from-origin cases/case-huntington-2021/origin.json --out data/ais/huntington.parquet
python pipeline/attribute/tracks.py   --parquet data/ais/huntington.parquet
python pipeline/attribute/score.py    --case case-huntington-2021
python pipeline/attribute/evaluate.py --scenarios 500 --out docs/img/eval_curve.png
python scripts/validate_case.py cases/case-huntington-2021
```

## E3. Data
NOAA Marine Cadastre AIS — `coast.noaa.gov/htdata/CMSP/AISDataHandler/<year>/`, one zipped CSV per day, all US waters, no registration. **Not** the AccessAIS map tool: it needs an emailed order (an external dependency close to the demo) and it pre-filters, which means our own bbox filter — the thing producing the funnel's `in_region` count — never gets exercised on real volume.

Sentinels to null: SOG 102.3, COG 360.0, Heading 511.

## E4. You are remote
Post an end-of-day update in the group **every single day**, and append to `docs/updates/jaiveer.md` after each phase. Nobody can see your screen; silence reads as risk and makes people start duplicating your work. Ask earlier than feels necessary — a question costs five minutes, a silent stuck day costs the project.

## E5. Escalate to Akshat (45-minute rule)
NOAA download route changed · incident days missing your region · `origin.json` not matching the contract · a funnel that returns all-zero after you have confirmed the box is right · anything where you are about to extend the contract.

## E6. Definition of done
- [ ] Branch pushed; `tests.py` committed with assertions; Parquet backed up
- [ ] Grid-based proximity with row-0-is-north verified by test
- [ ] Seven components with applicability gating; null ≠ zero
- [ ] Funnel monotonic, `dropped_short_track` reported
- [ ] At least one exclusion per case with a plain-language reason
- [ ] Abstention path exercised and demonstrable
- [ ] Parity, head-proximity and temporality implemented and Cerulean cited
- [ ] Dark-vessel cross-check running against Soum's `ship_detections`
- [ ] **Menuett AIS density verified and reported to Akshat — before anything else**
- [ ] Infrastructure association working on Huntington Beach and Mumbai
- [ ] `natural_seep` flag emitted on Mumbai
- [ ] `ais_source` gating: `gap` and `slowdown` return `null` on the two `gfw_hourly` cases
- [ ] Sampling-density experiment run (downsample Menuett to hourly, re-score, report the rank change)
- [ ] Traffic-density prior and repeat-offender history
- [ ] Chronic vs acute changing the search strategy
- [ ] Evaluation curve with a stated operating limit
- [ ] All four US cases run, validated, and the story read before shipping
- [ ] Fleet analysis recomputed per case; run once on a second machine
