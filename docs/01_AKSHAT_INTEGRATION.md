# AKSHAT — Integration, Cases, Contracts, Verification
*v2. Read with 00_MASTER_PLAN.md and 05_HARSHITA_INTEGRATION.md. Organised in phases, not days.*

> **You are the producer side of integration: everything upstream of the case bundle.** Harshita owns everything downstream of it. The handoff is a named gate (Part D). You are also the only person on this project with zero components of your own — that is deliberate. **Your value is slack.** When someone's handoff breaks, you are the person with room to fix it. Protect that by refusing extra work, not by taking it.

---

# PART A — WHERE YOU STAND

## A1. What you built

The JSON contracts. `case-000`. `validate_case.py`. `make_case000.py`. The repo skeleton and the three frozen conventions. The fencepost ruling (`n_steps` 96→97, commit `278f463`).

**That architecture decision is why this project is where it is.** Four people built four working components, in parallel, on four machines, without ever blocking each other — because nobody imports anybody and everything crosses through files. Most six-person student projects at this stage have three working parts and no system. You have four working parts and a defined seam.

## A2. What you have not done

Exported a single real SAR scene. Written any `verification.json`. Merged anything — **`main` still carries 2 commits while four branches hold the entire project.**

You *have* now done the case selection, and it took an entire evening of honest searching that produced more than the cases themselves. See A3.

## A3. What's now resolved — the case library is locked

**Six spill cases, all real data, no synthetic case.** Full details in Master §3.2. Summarised:

| # | Case | Scene status | What it gives you |
|---|---|---|---|
| 1 | **Menuett** — 30 Jul 2024, Atlantic | id truncated, **pull full id** | Hero. Gap detection on dense AIS. ⚠️ offshore AIS unverified |
| 2 | **Panagia Thalass…** — 17 Mar 2023, Pacific | id truncated, **pull full id** | Second basin, and hero backup |
| 3 | **Huntington Beach** — 2 Oct 2021 | `S1A_…_20211002T015821…_2BF9` confirmed, slick clear | Infrastructure + NTSB ground truth |
| 4 | **Alaska dark vessel** — 16 May 2023 | id truncated, **pull full id** | Real radar-vs-AIS cross-check |
| 5 | **Mumbai** — 3 Sep 2023 | id truncated, **pull full id** | All four source classes at once |
| 6 | **Jamnagar** — 23 Feb 2024 | `S1A_IW_GRDH_1SDV_20240223T011114_20240223T011139_052679_065FA4_546D` confirmed | The undocumented Indian discharge |
| 7 | **Look-alike** — Ennore 30 Nov 2023 | confirmed from the Arabian Sea sweep | Correct rejection |
| 8 | **No-spill** — Zenodo Part 3 | Soum nominates | Correct rejection |

**Golden Ray is dropped (D17).** No SAR-visible slick, and Huntington makes the infrastructure point better because it has a federal investigation behind it.

**Ennore 2017 is archived, not deleted (D18).** A published paper reports detecting this exact spill in Sentinel-1A, **visible in VV, using SLC data**. Our GRD probe found nothing. You cannot ship a "no SAR-visible slick" claim that contradicts the literature without reading the paper first. This is yours to close and it is not urgent — the library is complete without it.

**The rule that came out of it, and it is worth more than the case:**
> Before claiming any negative result about a documented incident, check whether someone has already published a positive one.

You caught that yourself, by reading around the case rather than by testing code. A judge asking *"where's the paper that says the opposite?"* would have been a much worse moment.

**What the search produced beyond the cases.** Five measured Indian-waters detection failures across two incidents — wind, revisit, timing, cloud, and a plume that probed as sediment rather than oil. Master §10 has the numbers. **That is a demo asset**, not wasted time: five failure modes with five different specific causes is the argument for why backward reconstruction exists, stated as evidence rather than assertion.

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
| A13 | Approve `natural_seep` as a fourth `source_type` (D19) | — | ruling, already made |
| A14 | Approve `ais_source` on `meta.json` (D20) | — | ruling, already made |
| A15 | Tell Jaiveer to **verify NOAA density at Menuett** before anything else | Jaiveer | one message, **blocking** |
| A16 | Tell the team the sealed answers file exists and you hold it (D21, Part H) | everyone | one message |

## A5. Problems I see that nobody raised

**`main` at two commits is the highest-probability catastrophic risk in the project.** Four laptops each hold work that exists nowhere else. One dead SSD and a component is gone. It costs thirty minutes.

**Nobody owned `verification.json`.** It is the strongest new idea in the project and it is pure research and writing — which makes it yours, and it is the one thing here that cannot be delegated or generated.

**VV-only exports would cripple Soum.** ~~His single strongest feature is `vh_mean_depth_db`, at twice the weight of any VV feature.~~ **Corrected 13 Sept:** that feature was computed from Zenodo band 2, which is VV, not VH — the Zenodo band order is the reverse of ours. The rank-1 feature is real but is a *co-pol* statistic. **Keep checking `bandNames()` anyway:** the measured win comes from having a *second* polarisation at all (val F1 0.346 → 0.643), so a VV-only export still costs it. An 8-bit PNG quantises the whole usable dB range into 256 levels and destroys a signal that is only ~1 dB deep. **Every export must be a 2-band float32 GeoTIFF.** The PNG is generated separately, for display only. This is the most consequential technical detail in your lane.

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

**B8 — `natural_seep` is a fourth source type.** Cerulean flags the Mumbai case as sitting in a known natural seep area. Without a fourth class the system cannot say *"some of this may be geological"*, and that is both a real operational distinction and a credibility asset. It touches Jaiveer's `suspects.json` schema and Harshita's rendering.

**B9 — `ais_source` is required whenever `attribute` is available.** `noaa_dense` or `gfw_hourly`. GFW is one position per vessel per hour against NOAA's ~71 seconds, so on a GFW case `gap` is structurally impossible and `slowdown` is very coarse. Those components return `null`, not zero. Jaiveer already has applicability-gating machinery for port traffic; this is the same pattern with a different trigger.

**B10 — Blind evaluation.** You hold `docs/ANSWERS.md`; nobody else sees it. Tell the team it exists and who holds it, so they understand why *"is this right?"* goes unanswered during the week. Full reasoning in Part H.

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

## PHASE 1 — Case onboarding *(replaces the old case-selection phase; blocks everyone)*

The cases are chosen. What remains is turning six Cerulean records and two scene ids into something your team can run against. **This is the residual Phase 1–3 work and it is the bottleneck right now** — three people have been building against fixtures for days.

### 1.1 Pull the full Sentinel-1 scene ids
Cerulean truncates them in its detail panel (`S1A_IW_GRDH_1SDV_2024073…`). There is a **copy button** beside each. Get the full id for cases 1, 2, 4 and 5. Jamnagar and Huntington are already complete.

Without the full id the GEE export cannot select the scene, so this blocks Phase 2 entirely.

### 1.2 Download the Cerulean record for every case
Use the **download button** in the slick-details panel. Each record carries the slick polygon, the detection timestamp, the scene id, and the attributed source.

Two uses, and the second is the one people miss:
- It is the source material for `verification.json` (Phase 4)
- **The polygon is ground truth for Soum's segmentation on a real incident.** Right now every IoU number he has comes from the Zenodo test set. With these he can say *"on the Huntington Beach scene our segmentation achieves X IoU against SkyTruth Cerulean's operational detection of the same slick"* — a completely different and much stronger claim than benchmark-only figures. **Give him the polygons, not the answers** — see Part H.

### 1.3 Confirm VH availability per case
Run `img.bandNames()` on each selected scene. Every case must come back `["VV","VH","angle"]`. If any is VV-only, **tell Soum immediately and name the case** — he has a VV-only fallback but he needs to know which, and the results slide notes the degradation honestly.

### 1.4 Set `ais_source` per case
`noaa_dense` for cases 1–4 (US EEZ, NOAA Marine Cadastre). `gfw_hourly` for cases 5 and 6 (Indian EEZ, Global Fishing Watch). This field is **required** whenever `attribute` is in `acts_available`, and it decides which of Jaiveer's scoring components can fire at all (D20).

### 1.5 Global Fishing Watch — register and check coverage
Free API, **non-commercial use only**, and registration asks for a short description of your intended impact. Register early rather than at 2am.

**A correction to carry:** the GFW report in circulation claims the AIS Vessel Presence dataset returns MMSI, name, IMO and positions. **It does not.** GFW's own documentation says it *"shows vessel presence patterns and movement corridors, but does not provide individual vessel positions"* — it is a gridded layer served through the 4Wings tile API. For tracks you want the **Vessels API** and the **Events API**; the latter includes **AIS-disabling events**, which is Jaiveer's gap analysis already productised and computed on GFW's full-resolution underlying data, so gap analysis may still be reachable *through that endpoint* even though it is impossible from the hourly presence layer. There is also a **SAR vessel detections** endpoint that flags non-broadcasting vessels — use it to *validate* Soum's ship detector, never to replace it, because building it ourselves is the differentiator.

Confirm Arabian Sea coverage for 2023-09-03 and 2024-02-23 at usable resolution. If it fails, cases 5 and 6 drop to `detect + trace` and the Indian story becomes *"the query reduces to one database lookup, and the database does not exist"* — which is still a strong screen. See Part I.

### 1.6 The no-spill scene
Ask Soum for one clean-ocean scene from Zenodo Part 3. **The look-alike case is already settled** — the Ennore 30 Nov 2023 scene is better than anything from Zenodo, because it is the same coast and sensor as a real spill with dark patches that provably cannot be oil.

### 1.7 Write `cases/index.json` and the `meta.json` stubs
Presentation order is 1 → 8 per Master §3. Each `meta.json` gets `case_id`, `title`, `short_location`, `case_type`, `scene_id`, `detection_time`, `acts_available`, `ais_source`, and the `gallery` block with a blurb written as a question.

### 1.8 Announce each case as it lands
> 🚩 **Do not batch this.** Every case unblocks three people on different tasks. Message the group per case with: scene id, UTC timestamp, bounding box, `ais_source`, and which acts apply. Jaiveer needs the date to download AIS, Anushka needs it to fetch the ocean, Soum needs the export.

**One message that goes out first, before any case:** Jaiveer verifies NOAA AIS density at Menuett's position (30.384 N −79.634 W, ~100 km offshore). It is your hero case and NOAA leans on terrestrial receivers. If it comes back with a handful of positions rather than hundreds of vessels, **Panagia becomes hero and the presentation order reshuffles.** That is the only open item that could still force a replan.


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

**Deliver in library order** — Menuett first, since it is the hero and the one the deck is built around. Then Panagia, Huntington, Alaska, Mumbai, Jamnagar, and the two rejection cases last (they are detect-only and cheap once the exporter works).

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
For Huntington Beach that is **NTSB MIR-24-01 itself**, not a news summary — it is the only case in the library with a federal investigation behind it, and it is a document a judge can go and read.

For Menuett, Panagia, Alaska and Mumbai the source is the **Cerulean record you downloaded in Phase 1.2**, plus any press that exists. Write it as *"SkyTruth Cerulean attributed this slick to vessel X"*, **never** *"vessel X was proven responsible"* — it is another algorithm's output with analyst review, not a court finding, and the distinction is one a judge may well probe.

For **Jamnagar there is no source at all**, and that absence is the finding. `official_finding` records it explicitly rather than being left empty: no investigation, no named vessel, no published record, because India has no capability to produce one.

### 4.2 Fill `official_finding`
Summary, responsible parties with IMO where you have it, source name and URL, source type, volume, and — importantly — `caveat`. Huntington Beach's caveat carries the whole case: **the anchor strike preceded the release by eight months, so no vessel was the proximate source at detection time.**

### 4.3 Fill `naap_result` from the actual output files
After the stages have run. Not from memory, not from an earlier draft, not from what you hoped.

### 4.4 Write `assessment` honestly
`verdict` ∈ `hit | partial | miss | not_applicable`. **The `explanation` is human prose. Never generate it.**

Expected verdicts, written now so you notice if reality diverges:
- **Menuett and Panagia** — genuinely unknown until they run. This is the point of the blind evaluation (Part H). **A `miss` ships**, and a team that shows one with an explanation of *why* reads as engineering; a team that shows only hits reads as marketing.
- **Huntington Beach** — `hit` if the infrastructure module lands: origin on the pipeline right-of-way, every transiting vessel excluded, which is what the NTSB concluded. `partial` without it. **Naming a transiting vessel here would be wrong** — the anchor strike preceded the release by eight months, so no vessel was the proximate source at detection time. That caveat carries the whole case.
- **Alaska** — `hit` if the origin cloud lands on or near the radar contact 4.5 km away. **State the asymmetry plainly:** a vessel dark to Cerulean's *commercial* AIS is a strong claim; a vessel absent from our *free NOAA* archive might be a coverage hole. Two independent absences is evidence; one is not.
- **Mumbai** — expect a multi-source finding. The honest assessment may well be *"infrastructure and a dark vessel are both plausible, and the area has documented natural seepage."* That is a real analytical outcome, not a fudge, and it is the best possible demonstration of why source classification runs before attribution.
- **Jamnagar** — `not_applicable`. There is no official finding because nobody investigated. The `official_finding` block records that absence explicitly rather than being left empty, and `what_would_have_helped` says: published Indian coastal AIS.

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

### 5.1 Menuett first, all the way to the browser
Expected bug classes, in the order they usually appear:
1. Coordinate swaps — the validator names them
2. `meta.detection_time` vs `particles.t0` mismatch — validator catches >60 s
3. Particles seeded off the polygon — **plot `detections.geojson` and `particles[0]` together; they must overlap**
4. Origin cloud on land — check the centroid against a coastline
5. Origin cloud rendering off-screen — expected, and it is Harshita's union-camera fix, not a data bug

### 5.2 Then Panagia, Huntington and Alaska — and re-run every check from scratch each time
Menuett at −79.6°E, Panagia at −123.9°E, Alaska at −142.7°E, Mumbai at +72.2°E, Jamnagar at +71.9°E. **The library straddles both hemispheres**, which is good for robustness and dangerous for assumptions. A 0–360 longitude leak or a sign error that survives four Atlantic cases will surface the moment you cross into the Indian Ocean. Do not assume anything transfers between cases.

Alaska at 59.5°N is also the highest latitude in the library. `cos(lat)` corrections that were negligible at 30°N matter there — a degree of longitude is about half as wide.

### 5.3 Then Mumbai and Jamnagar, then the two rejection cases
Mumbai and Jamnagar are `gfw_hourly`, so Jaiveer's `gap` and `slowdown` components should come back `null` rather than zero. **Check that in the bundle** — a zero where a `null` belongs is an honesty bug, not a display bug.

Cases 7 and 8 are cheap once the exporter works — detect-only, and the correct output is zero oil features.

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

## PHASE 7 — Demo prep and demo day

### 7.1 The demo machine runs the latest validated `main`
Work continues on `main` up to the demo. Before anything reaches the demo machine:
```bash
git pull && python scripts/validate_case.py cases/
```
A pull that changes what is shown means re-running 7.2 on that machine.

### 7.2 Demo-prep checklist
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

# PART H — BLIND EVALUATION *(yours to enforce)*

Every case has a documented outcome — a Cerulean attribution, an NTSB finding, a dark-vessel id. **All of it lives in `docs/ANSWERS.md`, which you hold and nobody else sees.** Not in the repo, not in the group, not on a slide until Phase 4.

**Why this matters more than it sounds.** If Jaiveer knows Menuett is the answer while tuning weights, he will tune until Menuett ranks first. If Soum knows where the slick is, he will lower the threshold until it appears. If Anushka knows the origin, she will read a wrong cloud as close enough. **None of that is dishonesty** — it is what anyone does when the target is visible. But it collapses "our system identified the vessel" into "we tuned it until it did", and a December panel will ask which happened.

**What you hand over, and what you hold back:**

| Person | Gets | Never gets |
|---|---|---|
| Soum | `sar_vv_vh.tif`, `sar.png`, `bounds.json`. Cerulean's slick polygon **only after** his detector has produced its own, so the IoU comparison is honest | Where the slick is, before he finds it |
| Anushka | Case list with `detection_time` and bounds; Soum's detections when they land | The documented origin or release time |
| Jaiveer | Case list with dates, bounding boxes and `ais_source`; real `origin.json` when it lands | **Vessel names, MMSIs, IMOs.** His box at `2 × radius_90_km` contains the culprit and plenty of decoys anyway |
| Harshita | Bundles as produced | The answers |

**Tell everyone the file exists and that you hold it.** Hiding its existence would be worse — it explains why you are not answering *"is this right?"* during the week, and it turns the verification screen into a genuine reveal rather than a restatement. Including when it is wrong.

**And hold the line.** No hints, no nudges, no raised eyebrows when someone's number looks off. The moment a bundle validates, you open the file and the comparison is real.

---

# PART I — THE INDIAN CASES

Cases 5 and 6 are different in kind from 1–4 and the difference is the point.

**They are `gfw_hourly`.** One position per vessel per hour against NOAA's ~71 seconds. `gap` cannot fire; `slowdown` is coarse; proximity precision drops to tens of km. Those are `null`, and the screen says "n/a".

**The story that makes it land:**
> *"Attribution quality is bounded by AIS sampling density, not by our method. In US waters at 71-second sampling we resolve to a single vessel with a transponder gap as evidence. In Indian waters at hourly sampling we resolve to a small candidate set and cannot assess gaps at all. Same pipeline, same physics — different data."*

That is a policy conclusion drawn from your own measurements, and it is exactly the register NTRO works in.

**If GFW coverage fails entirely**, the Indian cases run `detect + trace` and the screen becomes stronger rather than weaker. A chronic slick has vessel-track geometry, so the backward reconstruction yields a **line segment**, not a point — which gives you the vessel's course, an implied speed from slick length over the age band, and a projected outbound track from the head:
> *"A vessel was here, on this heading, at roughly this speed, discharging over this window. Here is its outbound track. Any AIS record covering this box and this window would resolve it to a specific ship in seconds."*

You have reduced an unsolved discharge to a single database query, and then shown that the query cannot be run. The gap stops being something you assert and becomes something the judge watches you hit.

**Anonymise the top suspect on screen** for both Indian cases. Mask the MMSI, label it "Vessel A", keep the full data one click away. Naming a real vessel as a polluter with no investigation behind it is a real exposure, and you lose nothing — *leads, not verdicts* was already the line.

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

**F1. Menuett's AIS coverage is unverified.** It is the hero, at ~100 km offshore where NOAA's terrestrial receivers thin. **This is the only open item that could still force a replan.** Jaiveer checks it first; Panagia is the fallback hero and Alaska moves up.

**F1b. Case onboarding slips.** The cases are chosen but the scene ids are truncated and nothing is exported. Three people are still on fixtures. Announce per case, never batched.
**F2. You take on component work.** Your value is slack. If Ennore fails, if an export is wrong, if a seam breaks — you are the person with room. Guard it.
**F3. Negative longitude.** Everything works at 80°E and breaks at −118°. Phase 5.2.
**F4. `verification.json` gets deprioritised.** It is the strongest new idea and it is invisible until the last screen. Do it in Phase 4, not at the end.

**F4b. The blind evaluation quietly erodes.** Under pressure someone asks "is this right?" and you answer. Then the claim is gone and you cannot get it back. Hold it.
**F5. Numbers change under you.** A re-verified scene changes the ocean, which changes the origin, which changes the suspects, which changes the deck. Log every change in `_INTEGRATION.md` and re-check the slides.
**F6. An unvalidated change reaches the demo machine.** Every pull onto it is followed by the validator and the click path (Phase 7.1).

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
- Jamnagar scene: `S1A_IW_GRDH_1SDV_20240223T011114_20240223T011139_052679_065FA4_546D`, 2024-02-23 01:11:14 UTC, DESCENDING, rel. orbit 107, VV+VH, IW
- Jamnagar slick, measured: inside VV −25.41 / VH −47.36 dB; clean water VV −17.24 / VH −33.12 — ~8 dB VV depression
- Huntington scene: `S1A_…_20211002T015821…_2BF9`, 2021-10-02 01:58:21 UTC; sea median −20.9 dB VV, slick core −28 to −32 dB
- Archived: Ennore 2017 scene `S1A_IW_GRDH_1SDV_20170129T003132_20170129T003157_015039_01892E_6D04` (D18)
- HYCOM GEE archive ends **2024-09-05** — every case must predate it
- HYCOM velocity: scale 0.001, **divide by 1000**
- `duration = (n_steps − 1) × timestep_minutes`; 97 steps × 15 min = 24 h exactly

**G3. Definition of done**
- [ ] `main` carries all four branches; `TRAPS.md` fixed; all Part B rulings broadcast
- [ ] Menuett's NOAA AIS density verified, hero confirmed or reassigned
- [ ] Full scene ids pulled for cases 1, 2, 4, 5; Cerulean records downloaded for all
- [ ] `ais_source` set on every case with `attribute`; GFW registered and Arabian Sea coverage checked
- [ ] Eight bundles selected, verified, and announced individually
- [ ] `docs/ANSWERS.md` created and held; the team told it exists
- [ ] 2-band GeoTIFF + PNG + bounds + thumb exported for every case
- [ ] Validator hardened; `build_case.py` assembling and checking
- [ ] `verification.json` written by hand for every case that has one
- [ ] `receipts.md` complete, including the CC-BY attribution
- [ ] All seven bundles validated **and** signed off by Harshita in the browser
- [ ] Deck done, two rehearsals, demo-prep checklist run, fallback video exists
