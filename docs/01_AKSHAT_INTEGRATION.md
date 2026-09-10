# AKSHAT — Integration, Cases, Contracts, Verification
*v2. Read with 00_MASTER_PLAN.md and 05_HARSHITA_INTEGRATION.md. Organised in phases, not days.*

> **You are the producer side of integration: everything upstream of the case bundle.** Harshita owns everything downstream of it. The handoff is a named gate (Part D). You are also the only person on this project with zero components of your own — that is deliberate. **Your value is slack.** When someone's handoff breaks, you are the person with room to fix it. Protect that by refusing extra work, not by taking it.

---

# PART A — WHERE YOU STAND

## A1. What you built

The JSON contracts. `case-000`. `validate_case.py`. `make_case000.py`. The repo skeleton and the three frozen conventions. The fencepost ruling (`n_steps` 96→97, commit `278f463`).

**That architecture decision is why this project is where it is.** Four people built four working components, in parallel, on four machines, without ever blocking each other — because nobody imports anybody and everything crosses through files. Most six-person student projects at this stage have three working parts and no system. You have four working parts and a defined seam.

## A2. What you have not done

Exported a single real SAR scene. Picked any US case. Written any `verification.json`. Merged anything — **`main` still carries 2 commits while four branches hold the entire project.**

## A3. What's now resolved

**Ennore scene confirmed.** Four Sentinel-1 passes exist over the search box between 28 Jan and 15 Feb 2017, all `IW` mode, all `["VV","VH","angle"]`. The frame grid does not align to the lat/lon box, so two of the four are slivers. The usable one:

```
S1A_IW_GRDH_1SDV_20170129T003132_20170129T003157_015039_01892E_6D04
2017-01-29 00:31:32 UTC  =  06:01 IST, the morning after the collision
Full coverage of Ennore / Chennai · VV + VH
```

Two of those four are adjacent frames of the same orbit pass, 25 s apart — same flyover, different frames. `..._6D04` is the one with full coverage; `..._7843` catches only a sliver.

**Still to do on Ennore:** zoom in and confirm a dark feature is actually visible on the water. A scene with no visible slick is not a hero case regardless of what the metadata says. Fallback is `..._49A5` (10 Feb).

## A4. The backlog your team is waiting on

| # | Item | Raised by | Effort |
|---|---|---|---|
| A1 | `TRAPS.md` #2 says ÷100 for HYCOM; **correct is ÷1000** | Anushka | 5 min |
| A2 | **Merge all four branches to `main`** | everyone | 30 min |
| A3 | `HeatmapLayer` → **`BitmapLayer`** ruling | Harshita | ruling only |
| A4 | Bless `time_window_method` into CONTRACTS | Anushka, Harshita | done in Master v2; propagate |
| A5 | Tell Jaiveer to score the **grid**, not the r50 circle | Anushka | one message |
| A6 | `web/CLAUDE.md` still names `HeatmapLayer` — her AI re-reads it every session | Anushka | 5 min |
| A7 | Validator: origin-vs-scene bounds warning, `area_km2` vs polygon warning, tighten `Box` pad | Harshita, Anushka | ~1 h |
| A8 | Anushka has 5 uncommitted files; Jaiveer's Stage 1 unpushed; Harshita's `ContextPanel.tsx` uncommitted | all three | one message |
| A9 | Adaptive field-box pad — fund it | Anushka | **fund it** |
| A10 | Tug/tow display labels on suspect cards | Jaiveer | ruling |
| A11 | `suspects.json` schema extension (source types, components, dark vessels, infrastructure) | Jaiveer | approve |
| A12 | Confirm **2-band VV+VH GeoTIFF** exports, not PNG-only | Soum | commitment |

## A5. Problems I see that nobody raised

**`main` at two commits is the highest-probability catastrophic risk in the project.** Four laptops each hold work that exists nowhere else. One dead SSD and a component is gone. It costs thirty minutes.

**Nobody owned `verification.json`.** It is the strongest new idea in the project and it is pure research and writing — which makes it yours, and it is the one thing here that cannot be delegated or generated.

**VV-only exports would cripple Soum.** His single strongest feature is `vh_mean_depth_db`, at twice the weight of any VV feature. An 8-bit PNG quantises the whole usable dB range into 256 levels and destroys a signal that is only ~1 dB deep. **Every export must be a 2-band float32 GeoTIFF.** The PNG is generated separately, for display only. This is the most consequential technical detail in your lane.

**You have never actually run the pipeline.** Every component owner has run their own code hundreds of times. You have run none of it. The first time you assemble a bundle will be slower than you expect for reasons that have nothing to do with bugs — environment, paths, argument names. Do one dry run early (Phase 3.4) rather than discovering it under pressure.

---

# PART B — DECISIONS YOU OWE, WITH THE REASONING TO GIVE

Broadcast all of these in one message. Each is blocking someone.

**B1 — `BitmapLayer`, switch.** Harshita read deck.gl's source: `HeatmapLayer` re-smooths in *screen pixels* and renormalises colour per viewport, so a judge zooming in tightens the origin cloud and zooming out widens it. **The answer changes under their hand.** Indefensible in December. `BitmapLayer` is already in `@deck.gl/layers` — no new dependency. Sequence it with the colour-ramp work; same lines.

**B2 — `time_window_method` is in the contract.** She shipped it, it protects a claim we must defend, and the frontend needs it to avoid rendering a bracket as a measurement.

**B3 — Jaiveer scores the grid, not the circle.** Anushka measured the real cloud at 4.38:1 aspect with 44.7% of high-probability mass outside the r50 circle. Circle membership would name vessels in near-empty water and exclude vessels in the bright streak. His scorer is unwritten, so this costs nothing now and is a rewrite later.

**B4 — Fund the adaptive field-box pad.** Gulf Loop at 1.8 m/s covers 156 km in 24 h against a fixed 55 km pad. Particles would pile against an invisible wall and produce a perfectly plausible wrong answer. Fund the loud edge guard too — that is the half that makes the failure impossible to miss.

**B5 — Tug/tow are display labels only.** Show the vessel type on the card for legibility; do not change `type_prior` weights on the strength of a one-port fleet sample.

**B6 — Approve Jaiveer's `suspects.json` extension** (source types, per-component scores with `null` for not-applicable, dark vessels, infrastructure, exclusions). Then update `CONTRACTS.md` and tell Harshita, because she renders every one of those fields.

**B7 — 2-band GeoTIFF, committed.** Per A5.

---

# PART C — THE PHASES

## PHASE 0 — Unblock everyone *(before anything else)*
0.1 Fix `TRAPS.md` #2 to ÷1000. Grep the repo for "divide by 100" and kill every instance — it is in several files including judge-facing ones.
0.2 **Merge `anushka`, `jaiveer`, `soum`, `harshita` into `main`.** Chase the three uncommitted items first (A8) so the merge captures everything.
0.3 Broadcast all of Part B in one message.
0.4 Fix `web/CLAUDE.md`'s HeatmapLayer line — her AI re-reads it every session and will keep reintroducing the wrong layer.
0.5 Publish Master Plan v2 and the five personal docs into `docs/`.
0.6 Set up `docs/receipts.md` and `docs/updates/_INTEGRATION.md`.

---

## PHASE 1 — Case selection *(blocks literally everyone)*

### 1.1 Confirm Ennore
Zoom to the tight box `[80.20, 13.10, 80.45, 13.35]` on scene `..._6D04`, VV stretched `{min:-22, max:-3}` and VH `{min:-28, max:-12}`. Look for a **dark streak or patch on the water**, ideally visible in both. Use the Inspector to read raw dB on the water — a real slick reads several dB below the surrounding sea.

If nothing is visible: widen the VV stretch to `{min:-25,max:0}` first, then fall back to `..._49A5`. If neither shows anything, Ennore becomes a detect-only case with an honest note, and Huntington Beach becomes the hero. **That is survivable now — Ennore is 1 of 7, not 1 of 1.**

### 1.2 Lock Huntington Beach
Slick detected 1–3 Oct 2021, San Pedro Bay / Orange County. Search box roughly `[-118.3, 33.5, -117.8, 33.8]`. Source: **NTSB Marine Investigation Report MIR-24-01**, which determined MSC Danit's anchor contact with the San Pedro Bay Pipeline on 25 January 2021 was the initiating event leading to the October release.

**This is our exoneration-and-infrastructure case.** Expect the origin to land on the pipeline right-of-way, and expect every transiting vessel to be excluded. With Jaiveer's infrastructure module that is a **hit**, not a miss.

### 1.3 Lock Golden Ray
Significant discharge during salvage, ~31 Jul – 2 Aug 2021, St Simons Sound, Georgia. SkyTruth published satellite imagery showing plumes as far as 15 km from the site. Fixed wreck source. Search box roughly `[-81.5, 31.0, -81.2, 31.3]`.

### 1.4 Find cases 4 and 5
Transiting-vessel discharges in US waters. Primary source: **SkyTruth Cerulean's public map** (`cerulean.skytruth.org`) filtered to US waters — it is a searchable database of already-attributed slick/vessel pairs. Want a clean linear slick, a named vessel, and a date inside Oct 2014 – Sep 2024.

**Two caveats to carry into `verification.json`:** Cerulean is another algorithm's output, not court-proven ground truth — write it as *"SkyTruth Cerulean attributed this slick to vessel X"*, never *"vessel X was proven responsible"*. And Cerulean is prior art; see Master §7 for how we answer that on stage.

Fallbacks if Cerulean does not yield two: NOAA Incident News archive, USCG investigation reports.

**This is the natural first research task for Urooz.**

### 1.5 Cases 6 and 7
Ask Soum for one convincing look-alike scene and one clean-ocean scene from Zenodo Part 3. He has 300 to choose from and he knows which fool the detector.

### 1.6 The four checks, every case
US waters (except Ennore) · date in Oct 2014 – **Sep 2024** (HYCOM's GEE archive ends 2024-09-05) · Sentinel-1 coverage confirmed by running the finder script · a **citable** official finding.

### 1.7 Announce each as it lands
> 🚩 **Do not batch this.** Every case unblocks three people. Message the group per case with: scene id, UTC timestamp, bounds, polarisations. Jaiveer needs the date to download AIS; Anushka needs it to fetch the ocean; Soum needs the export.

---

## PHASE 2 — The export pipeline

### 2.1 Rewrite `pipeline/export/gee_scene.py` for 2-band output
Per case, produce four artefacts:

| File | What | For |
|---|---|---|
| `sar_vv_vh.tif` | **2-band float32 GeoTIFF, dB, native 10 m** | Soum's classifier — the real numbers |
| `sar.png` | VV, 8-bit, clamped and stretched | display only |
| `bounds.json` | west/south/east/north + width_px/height_px + **the dB clamp used** | everyone |
| `thumb.png` | small preview | the gallery |

Record the clamp in `bounds.json` so Soum can invert it exactly and nobody has to guess. If you ever change a clamp, that is a broadcast, not a silent edit.

### 2.2 Export mechanics
`Export.image.toDrive` with `crs: 'EPSG:4326'`, `maxPixels: 1e10`. Then press **RUN in the Tasks tab** — nothing downloads until you do, and this catches everyone the first time.

On size: a 0.6° × 0.6° box at 10 m across two float bands is roughly 6600 × 6600 × 2 — several hundred MB. **Tighten the box around the slick before you drop resolution**, because 10 m is what Soum's Zenodo training data uses and matching it matters more than covering extra sea.

### 2.3 Verify every export by eye
Coastline where land should be, sea as grey speckle, any slick a visible dark streak. Blank or black means the clamp is wrong.

### 2.4 Confirm bands per case
Run `img.bandNames()` on every selected scene. If any US case comes back VV-only, **tell Soum immediately** — he has a VV-only fallback but he needs to know which case, and the results slide notes the degradation honestly.

### 2.5 Deliver case by case
> 🚩 Soum's real-scene inference is blocked per case on 2.5. Anushka's field fetch is blocked on `meta.detection_time` being real.

---

## PHASE 3 — Validator hardening and the exporter

### 3.1 Validator additions
- Warn when `origin.bounds` extends materially beyond the scene bounds — Harshita's point that a `PASS` currently says nothing about whether the bundle is *renderable*
- Tighten the `Box` pad so the off-scene warning can actually fire
- Warn when `area_km2` disagrees with the shoelace area of its own polygon by more than ~2×
- Fix the span check fencepost: `span_h = (n_steps - 1) * timestep_minutes / 60`
- Add `verification.json`: `verdict` in the four allowed values, `source_url` present and non-empty when `verify` is in `acts_available`
- Add the new `meta.json` fields and validate `cases/index.json` — every listed case exists on disk
- Add Jaiveer's extended `suspects.json`: `null` allowed in `components`, dark vessels have `mmsi: null`, infrastructure findings need a position

### 3.2 `build_case.py`
Gathers stage outputs into `cases/<id>/`, writes `meta.json`, runs the validator, exits non-zero on failure. It **assembles and checks. It does not compute, and it never repairs another stage's output.**

### 3.3 `cases/index.json`
Ordered list, strongest case first. Harshita's gallery reads this and hardcodes nothing.

### 3.4 Do one full dry run now
Build a bundle from `case-000` end to end through `build_case.py`, then load it in Harshita's app. **You have never run the pipeline.** Find the environment and path problems now, not on the first real case.

---

## PHASE 4 — Verification content *(yours alone, and it is writing not coding)*

For each case with `verify`, research and write `verification.json` by hand.

### 4.1 Go to the primary source
For Huntington Beach that is NTSB MIR-24-01 itself, not a news summary. For Golden Ray, USCG/Unified Command releases plus SkyTruth's published imagery. For Cerulean-sourced cases, the Cerulean record plus whatever press exists.

### 4.2 Fill `official_finding`
Summary, responsible parties with IMO where you have it, source name and URL, source type, volume, and — importantly — `caveat`. Huntington Beach's caveat carries the whole case: **the anchor strike preceded the release by eight months, so no vessel was the proximate source at detection time.**

### 4.3 Fill `naap_result` from the actual output files
After the stages have run. Not from memory, not from an earlier draft, not from what you hoped.

### 4.4 Write `assessment` honestly
`verdict` ∈ `hit | partial | miss | not_applicable`. **The `explanation` is human prose. Never generate it.**

Expected verdicts:
- **Huntington Beach** — `hit` if the infrastructure module lands (origin on the pipeline, all vessels excluded, which is what NTSB concluded); `partial` without it
- **Golden Ray** — `hit` if the origin lands on the wreck. Watch for salvage vessels appearing as suspects; they should be excluded as responders, and saying so explicitly is a good detail
- **Cases 4 and 5** — genuinely unknown until they run. **A `miss` ships.** A team that shows a miss with an explanation of *why* reads as engineering; a team that shows only hits reads as marketing.

### 4.5 `docs/receipts.md`
Every GEE scene id and UTC timestamp · every NOAA AIS filename · **Zenodo DOI 10.5281/zenodo.13761290, CC-BY — mandatory attribution, must appear on a slide** · every verification source URL · the Trujillo-Acatitla paper citation · SkyTruth Cerulean where used.

This is the file you open when a judge asks *"is this real?"* — five seconds, one click.

---

## PHASE 5 — Per-case integration

The loop, per case:

```
  1  you      select + export        → sar_vv_vh.tif, sar.png, bounds.json, thumb.png
  2  Soum     detections.geojson
  3  Anushka  particles.json, origin.json, particles_forward.json
  4  Jaiveer  vessels.geojson, suspects.json          (US cases only)
  5  you      build_case.py → validate → PASS
  6  Harshita browser QA → SIGN OFF or REJECT          ← the human gate
  7  you      route the rejection to its owner
```

**Step 6 is the part that was missing from the old plan.** The validator proves a bundle is *schema-valid*. It says nothing about whether it is *renderable* or *sensible*. Only Harshita can tell, because only she sees it. See Part D and her document.

### 5.1 Ennore first, all the way to the browser
Expected bug classes, in the order they usually appear:
1. Coordinate swaps — the validator names them
2. `meta.detection_time` vs `particles.t0` mismatch — validator catches >60 s
3. Particles seeded off the polygon — **plot `detections.geojson` and `particles[0]` together; they must overlap**
4. Origin cloud on land — check the centroid against a coastline
5. Origin cloud rendering off-screen — expected, and it is Harshita's union-camera fix, not a data bug

### 5.2 Then Huntington Beach — and re-run every check from scratch
**Ennore at 80°E is identical in both longitude conventions.** A 0–360 leak, a sign error, or a hemisphere assumption stays invisible until California at −118°E. Do not assume anything transfers. This is the single most likely place for a new bug after everything already works.

### 5.3 Then Golden Ray, cases 4 and 5, then 6 and 7
Cases 6 and 7 are cheap once the exporter works — detect-only, and the correct output is zero oil features.

### 5.4 Log every seam event
`docs/updates/_INTEGRATION.md`: what you received, what the validator said, what broke, who fixed it, what state the bundle ended in. When four people's numbers change under you, this is the only record of why.

---

## PHASE 6 — The deck and the narrative

### 6.1 Structure, roughly ten slides
1. The hook — a real SAR scene, and the fact the ship sailed away
2. The problem: satellites see slicks days late; nobody runs the model backwards
3. **The India gap** — *"INCOIS tells the Coast Guard where the oil is going. Nobody tells them where it came from. We built the other half."*
4. The system — one diagram, three stages plus verification
5. Detection, and **the VH finding** (Soum's — this is the novelty claim)
6. Trace — the ensemble, and why the answer is a cloud
7. Attribute — the funnel, dark vessels, exclusions
8. **The honesty slide** — Soum's held-out numbers, Jaiveer's evaluation curve with its operating limit, Anushka's age validation
9. **Prior art** — CleanSeaNet, Cerulean, INCOIS, and the four things we do differently
10. Data provenance and roadmap

### 6.2 The honesty slide is designed as confidently as the wins
Real numbers, named metrics, named splits. *"Leads, not verdicts."* A team that shows its error rate and has a rehearsed answer for "what if you're wrong" reads as engineering maturity, which is exactly what wins this category.

### 6.3 Prior art, said first
Never pretend CleanSeaNet or Cerulean don't exist. Master §7 has the three responses. Teams that cite prior art and show what they added look like researchers; teams that hide it look ignorant when a judge names it.

---

## PHASE 7 — Freeze and demo day

### 7.1 Freeze, twelve hours before 15 Sept 17:00
```bash
git checkout -b demo && git push -u origin demo
```
Demo machine runs `demo` and never pulls again. `main` may keep moving. **No exceptions, including for you** — your own runbook names the night-before improvement as the most common way strong teams lose demos.

### 7.2 Freeze checklist
- [ ] All seven bundles present, `validate_case.py` PASS on each
- [ ] App runs on the demo machine **with wifi off**
- [ ] Every case loads, every layer toggles, the slider scrubs, every panel populates
- [ ] Click-path check run end to end on the demo machine
- [ ] **Fallback video recorded** and saved locally plus on a phone
- [ ] `receipts.md` complete
- [ ] Deck exported to PDF, on the machine and on a phone
- [ ] Charger, HDMI adapter, hotspot

### 7.3 Two timed rehearsals with someone playing hostile judge.

### 7.4 Demo-day roles
**You** drive the narrative and the hostile questions. **Harshita** drives the laptop so you can face the judges. **Soum, Anushka, Jaiveer** each answer on their own stage — one sentence, then hand back. One person talks at a time.

---

# PART D — THE INTEGRATION PROTOCOL WITH HARSHITA

## D1. The split
**You own everything upstream of the bundle.** Data acquisition, exports, contracts, verification content, `build_case.py`, the validator, routing.
**She owns everything downstream of it.** Browser QA, visual verification, gallery assembly, the demo machine, the fallback video.

The bundle is the boundary. It is the same boundary that made the whole project parallelisable, applied to integration itself.

## D2. Two gates, and they check different things
| Gate | Owner | Answers |
|---|---|---|
| `validate_case.py` | you | Is it schema-valid? Right coordinate order? Dimensions agree? Timestamps parse? |
| Browser QA | Harshita | Is it *renderable*? Does it look physically sensible? Does the story hold? |

**A bundle is not integrated until both pass.** A PASS from the validator with a broken render is not done.

## D3. Triage — who owns a symptom
When she reports something wrong, this is how you route it. Do not debug her side; do not let her patch yours.

| Symptom | Owner |
|---|---|
| Polygons in the wrong hemisphere / mirrored | data — coordinate conversion, Soum or export |
| Origin renders south-west when the current runs south | data — Anushka, direction is flipped |
| Cloud renders off-screen | **render** — Harshita's union camera. Expected, not a bug |
| Heatmap changes shape on zoom | **render** — BitmapLayer |
| Particles don't overlap the slick at frame 0 | data — Anushka's seeding, or the polygon |
| Suspect with no matching track | data — Jaiveer; the validator should have caught it |
| A component bar shows zero that should be n/a | **render** — `null ≠ zero` |
| Slider stutters | **render** — decimate or reduce particles |
| Time readout wrong by hours | data — timezone; check `t0` vs `detection_time` |
| Blank map, wifi off | **render** — remote basemap style |

## D4. Cadence
A short sync between the two of you every time a bundle changes state. Not a meeting — a message with the bundle id and its state: `exported / stages complete / validated / QA passed / rejected: <reason>`.

## D5. The rule that keeps this clean
**Never patch a bundle by hand, and never let her patch data in the frontend.** Both hide the bug until demo day, and then it belongs to whoever is standing in front of the judge. Fix in the producing code, re-run, re-validate.

---

# PART E — Q&A YOU MUST HAVE COLD

**"Is this real data?"** → `receipts.md`, one click. Real Sentinel-1 via GEE, real HYCOM, real ERA5, real NOAA Coast Guard AIS. The only synthetic thing in the project is the fake bundle we used to build the frontend before the pipeline existed.

**"Is this precomputed?"** → Yes, deliberately. The pipeline runs offline and exports a case bundle; the interface plays it back. That is why it scrubs instantly and why it cannot break on venue wifi.

**"Isn't this just CleanSeaNet / Cerulean?"** → Agree enthusiastically, then Master §7. For Cerulean specifically, the four differences: we run the physics *backwards* so we can attribute a slick found days later rather than matching a coincident track; we use VV **and** VH; we use free public AIS rather than commercial; we publish exclusions.

**"How accurate is detection?"** → Soum's held-out, scene-level numbers on the dataset's own designated test set, plus the two-benchmark framing: 96% IoU is the authors' number on this dataset, ~53% is the state of the art on the harder Krestenitis look-alike benchmark, and **the gap between them is a measure of look-alike variety, not model quality.**

**"How accurate is attribution?"** → Jaiveer's injected-offender curve, with its stated operating limit and the abstention rule above it.

**"Why is your origin a cloud, not a point?"** → Because a point would be a lie. 50 perturbed runs; the spread is the honest uncertainty and it widens with rewind depth.

**"What if you falsely accuse an innocent ship?"** → Nothing happens automatically. Ranked, evidence-backed leads, like a tip line, with a human investigator. And we actively exonerate — here is the exclusion panel and the reason for each.

**"Why no ships on the Indian case?"** → Free bulk historical AIS exists for US waters and not Indian waters. That gap is itself part of what we are pointing at.

**"You got this one wrong."** → Screen 4 already said so. Here is why, and here is what would have caught it.

**"What would it cost to deploy?"** → Satellite data free, currents free, winds free, AIS free. Cost is compute per scene plus storage. **Have a rough annual number for national coverage before the finale** — winning teams consistently report that deployment and cost figures differentiate them at the final round.

---

# PART F — RISKS

**F1. Case selection slips.** Everything is downstream. Announce per case, never batched.
**F2. You take on component work.** Your value is slack. If Ennore fails, if an export is wrong, if a seam breaks — you are the person with room. Guard it.
**F3. Negative longitude.** Everything works at 80°E and breaks at −118°. Phase 5.2.
**F4. `verification.json` gets deprioritised.** It is the strongest new idea and it is invisible until the last screen. Do it in Phase 4, not at the end.
**F5. Numbers change under you.** A re-verified scene changes the ocean, which changes the origin, which changes the suspects, which changes the deck. Log every change in `_INTEGRATION.md` and re-check the slides.
**F6. Freeze slips.** An unrehearsed better demo loses to a rehearsed worse one.

---

# PART G — REFERENCE

**G1. Commands**
```bash
python scripts/make_case000.py
python scripts/validate_case.py cases/<id>
python pipeline/export/gee_scene.py --case <id>
python pipeline/export/build_case.py --case <id>
```

**G2. Confirmed constants**
- Ennore scene: `S1A_IW_GRDH_1SDV_20170129T003132_20170129T003157_015039_01892E_6D04`, 2017-01-29 00:31:32 UTC, VV+VH, IW
- HYCOM GEE archive ends **2024-09-05** — every case must predate it
- HYCOM velocity: scale 0.001, **divide by 1000**
- `duration = (n_steps − 1) × timestep_minutes`; 97 steps × 15 min = 24 h exactly

**G3. Definition of done**
- [ ] `main` carries all four branches; `TRAPS.md` fixed; all Part B rulings broadcast
- [ ] Seven cases selected, verified, and announced individually
- [ ] 2-band GeoTIFF + PNG + bounds + thumb exported for every case
- [ ] Validator hardened; `build_case.py` assembling and checking
- [ ] `verification.json` written by hand for every case that has one
- [ ] `receipts.md` complete, including the CC-BY attribution
- [ ] All seven bundles validated **and** signed off by Harshita in the browser
- [ ] Deck done, two rehearsals, freeze executed, fallback video exists
