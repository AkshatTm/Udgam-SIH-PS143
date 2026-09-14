# HARSHITA — Frontend, then Integration
*v2. Read with 00_MASTER_PLAN.md. Organised in phases, not days.*

> ### Historical brief — kept as the record of what Harshita built
>
> Remaining work from this document transferred to [`docs/team/akshat-remaining.md`](akshat-remaining.md)
> on 14 Sept 2026. **Do not track live work here.** It is preserved, and promoted out of the
> archive, because it is the fullest account of the reasoning behind the frontend — read it to
> prepare, to review, or to pick the stage up.

> **You own the only thing the judges actually look at.** Four people produce numbers in files. Your screen is what turns those numbers into something a person understands in five minutes — and, per the HOD's requirement, understands **with nobody standing next to them.** That last part changes the job from "build the UI" to "build something that teaches itself", and Parts B and C are entirely about that.

---

# PART A — WHERE YOU STAND

## A1. What you built, and why the verification discipline is the best on the team

**60 fps locked with 3000 particles × 97 frames**, verified twice — including under `--disable-gpu` software rendering, which is strictly harder than the demo laptop will be. That was the checkpoint that decides the project and you passed it with margin, needing neither documented escape hatch.

**The blank-map bug, diagnosed properly.** Two independent causes — the CSS specificity collapse and maplibre v6's worker resolver — found and separated rather than patched together. Most people fix one, see it still broken, and start changing random things.

**The freeze bug, where you measured and rejected your first hypothesis** before finding layer remounting. Fixing the wrong thing there would have cost a day and left the real bug live.

**Geospatial traps handled in code, not just claimed.** Row 0 = north. `origin.bounds` is not `bounds.json`. `cos(lat)` on radii. `[lon, lat]` end to end, with loaders that **actively reject** a swap rather than silently rendering Africa.

**§5.2 fixed in the producer, not the bundle** — the exact rule from the Master, and it took a real diagnosis: pixel-space versus lon/lat-space tilt, and the recognition that mirror images share a centroid so a centroid check would have passed.

**The Attribute panel verified against live rendered DOM**, diffed by hand against the file, because you had already seen static checks let two defects through. That is the right response to being burned once.

**The `HeatmapLayer` analysis.** You read deck.gl's source rather than arguing from principle, and found that it re-smooths in *screen pixels* and renormalises colour per viewport — so a judge zooming in tightens the origin cloud and zooming out widens it. **The answer would change under their hand.** That is indefensible in December and you were right to escalate rather than ship it.

## A2. What you flagged, and Akshat's rulings

| # | Item | Ruling |
|---|---|---|
| H1 | `HeatmapLayer` is camera-dependent | **Switch to `BitmapLayer`.** Already in `@deck.gl/layers`, no new dependency. Sequence with the colour ramp — same lines. |
| H2 | `abstain` branches render identical text | Fix in Phase 0 |
| H3 | Hardcoded "did not converge" prose | **Fix in Phase 0 — this is an honesty bug, see A3** |
| H4 | Camera framing insufficient for real data | Phase 5.2, union framing |
| H5 | `ContextPanel.tsx` uncommitted | **Phase 0.1 — do this first** |
| H6 | Never run on the demo laptop | Phase 8 |
| H7 | `time_window_method` not in contract | **Now blessed into the contract.** Parse it. |
| — | Urooz's design work | **Yours now.** Keep it minimal — clarity beats polish, and Part C is where the effort goes. |

## A3. Problems I found that nobody raised

**Commit `ContextPanel.tsx` before anything else.** The funnel, suspect cards and exclusion cards — the part a judge actually looks at — exist in exactly one working tree with no branch record. One bad `git checkout` and the highest-value UI work in the project is gone.

**§11.1 fabricates a claim, in code, today.** The unconditional "the ensemble did not converge" line will assert that a measurement failed at the moment any case ships `method: "convergence"`. That is the honesty rule broken by a hardcoded string. It is a two-line fix and it should not survive the hour.

**The particle cloud is not the uncertainty, and the copy currently implies it is.** `particles.json` is **one unperturbed control run**. It carries no uncertainty at all. The uncertainty lives entirely in `origin.json`, which is the stacked result of 50 perturbed runs. Any copy suggesting "watch the particles spread to see the uncertainty" is wrong, and an oceanographer would catch it. Reword in Phase 0.

**Your app will probably break offline.** MapLibre with a remote basemap style URL fails when the venue wifi does — and your own runbook names venue wifi as the classic demo disaster. **Test with wifi off in Phase 8**, and if the basemap is remote, either vendor a local style or drop the basemap entirely. The SAR raster is the real backdrop; a basemap is a nicety.

**Nobody has specified what happens between judges.** Judge A leaves the app on screen 3 with the slider half-scrubbed; Judge B walks up to a confusing middle state with no idea what they're looking at. **You need an idle reset** — see C8.

---

# PART B — THE COMPLETE USER WORKFLOW

*This is the spec. Build to it.*

## B0. The premise

A judge walks up to a laptop. **Nobody explains anything.** They have maybe four minutes and no domain knowledge. They must be able to: understand what this is, pick something, follow it through to an answer, and come away knowing whether the system was right.

Every design decision below serves that.

## B1. The journey, screen by screen

```
  GALLERY ──▶ DETECT ──▶ TRACE ──▶ ATTRIBUTE ──▶ VERIFY ──▶ back to GALLERY
   pick        what is    where &     who did      were we
   a case      the slick   when       it            right
```

Five screens, one direction, one big button at each step. **Back is always available; forward is always obvious.**

---

### SCREEN 0 — Gallery

**What they see on arrival**

Top: the project name, and one sentence that explains the whole thing to someone who has never heard of it —
> *"Satellite forensics: we find oil spills from space, run the ocean backwards to find where they started, and identify the ship responsible."*

Below: a grid of case cards. Each card carries:
- SAR thumbnail (`gallery.thumbnail`)
- Case title and `short_location`
- Date, human-formatted — "29 January 2017", not an ISO string
- A **badge** from `case_type`: `SPILL` / `LOOK-ALIKE` / `NO SPILL`
- The `gallery.blurb`, written as a **question** — *"588 barrels reached Orange County beaches. What released it?"* A question invites a click; a description does not.
- A difficulty chip

**The first card is visually emphasised** — slightly larger, or a soft "Start here" marker. A judge with no instructions needs one obvious entry point. Make it Ennore or Huntington Beach, whichever demos best.

**Ordering:** strongest case first, then the other spills, then look-alike and no-spill last. A judge who only clicks one card must land on your best one.

**Interaction:** whole card is clickable, generous hover state, cursor pointer. Nothing on this screen does anything except open a case.

---

### SCREEN 1 — Detect

**What they see the instant it loads**

- SAR scene filling the map
- **Detection outlines already drawn.** Do not make them hunt for a toggle.
- A headline in plain language above the panel: *"We found 3 dark patches. 1 is oil."*
- **The highest-confidence oil detection is already selected**, its object card populated in the right panel

**Never present a blank right panel.** A judge who has to figure out that polygons are clickable has already lost thirty seconds.

**The object card** — plain-language label first, technical term underneath:
```
OIL SPILL          87% confidence
─────────────────────────────────
How big          12.4 km²
How stretched     8.2 : 1        (elongation)
How sharp-edged   0.34           (edge gradient)
How much darker  -6.2 dB         (contrast)
Shape            LINEAR  →  deliberate discharge underway

Why we think this is oil
  stretched shape   ████████░░
  sharp edges       ██████░░░░
  darker in VH      ████░░░░░░
```

The "Why we think this is oil" bar chart is your single strongest demo asset. A neural network cannot produce it. Give it room.

**Rejected look-alikes** render in muted grey with a dashed outline and are clickable too — clicking one shows *why it was rejected*. **Encourage this.** A small caption: *"We also found 2 dark patches that aren't oil — click one to see why."* Showing the rejection is what proves we're not just flagging dark pixels.

**Primary action, bottom right, always the same place:**
> **`Trace this slick back →`**

---

### SCREEN 2 — Trace *(the centrepiece)*

**The problem:** the slider is the best thing in the project, and a judge who doesn't discover it never sees it.

**The solution: the screen demonstrates itself, once, automatically.**

On arrival, run a **single auto-play pass** — roughly four seconds, slider handle visibly travelling right-to-left, particles unwinding, origin cloud blooming at the end. Then it stops and rests at the fully-rewound state, with the handle at the left and a soft pulse on it.

The judge has now *seen* the interaction without being told. Almost all of them will then grab the handle.

Belt and braces: a small hint beside the handle for the first few seconds, `⟵ drag to rewind time`, fading after the first interaction.

**What they see**
- The slick where the satellite found it
- Particles drifting backwards as they scrub
- The origin cloud growing and **visibly widening** the further back they go
- A live time readout: **`T − 14h 15m`**, updating as they drag. Not a frame index.

**Right panel — origin card:**
```
WHERE THE OIL CAME FROM
─────────────────────────────────
Best estimate     28.41°N  89.92°W
Half the runs land within   4.2 km
Nine in ten within         11.8 km
Released between  28 Jan 08:00 – 20:00 UTC
Estimated age     8 – 16 hours
Based on          50 simulations
```

**Under it, in a muted box — this box is doing real work:**
> *"We can't give you a single point. We ran the physics 50 times across the honest range of wind and current uncertainty, and this is where they landed. The cloud gets wider the further back we look, because that's true."*

**Parse `time_window_method` and render honestly.** `"convergence"` → present as a measured estimate. `"bounded"` → present as a **bracket**, styled differently, labelled *"search bracket (not a measured release time)"*. Never let a bracket look like a measurement. And delete the hardcoded prose (A3).

**Also render** `age_hours` with `age_method`, and — if present — the per-estimator breakdown as a small expandable, so a curious judge can see *why* the age band is what it is.

**Primary action:**
> **`Find who did it →`**  *(or, when the case has no `attribute` act, `See what really happened →` jumping to Verify)*

---

### SCREEN 3 — Attribute

**What they see**

**The funnel, first and prominent** — it is requirement (c) made visible:
```
412 vessels in the area
 ↓
 63 present during the release window
 ↓
 12 close enough to the origin to matter
 ↓
  3 ranked suspects
```
A simple stepped graphic. It does not need to animate; it needs to be readable in two seconds.

**Then three suspect cards, ranked**, the top one expanded by default:
```
#1   EXAMPLE STAR              score 0.82
     Tanker · MMSI 367123450
     ─────────────────────────────────────
     Closest approach   3.1 km, 02 Oct 14:20 UTC
     Transponder gap    85 minutes during the window   ⚠
     Course             consistent with the origin
     Path               runs parallel to the slick

     Why this vessel
       • Inside the high-probability origin region during the window
       • 85-minute transponder gap overlapping the window
       • Track runs parallel to the slick axis
```
Hovering a card **highlights that vessel's track on the map**. This is the moment the map and the panel become one thing.

**The exclusion panel — do not bury it.** Give it a proper heading:
> **Vessels we ruled out**
> `OTHER SHIP` — heading away from the origin throughout the window
> `THIRD SHIP` — left the region before the window opened

**Dark vessels, when present** — this is the visual climax. A distinct marker on the map, and a card:
> **⚠ Unidentified radar contact** — the satellite saw a ship here. No transponder reported one.

Toggle the AIS layer beneath it so the judge sees the bright radar dot with **nothing underneath**.

**Infrastructure findings, when present:**
> **Source: San Pedro Bay Pipeline** — the origin lands on the pipeline right-of-way, and no vessel scored above threshold.

**Primary action:**
> **`Check our answer →`**

---

### SCREEN 4 — Verify

**Two columns, side by side, equal weight.**

```
┌── WHAT UDGAM CONCLUDED ────────┬── WHAT THE INVESTIGATION FOUND ──┐
│ Origin on the pipeline        │ NTSB determined MSC Danit's      │
│ right-of-way, 2.1 km from     │ anchor contact with the San      │
│ the reported leak.            │ Pedro Bay Pipeline on 25 Jan     │
│ All transiting vessels        │ 2021 was the initiating event.   │
│ excluded.                     │                                  │
│                               │ Source: NTSB MIR-24-01  ↗        │
└───────────────────────────────┴──────────────────────────────────┘

                    ┌──────────────┐
                    │   PARTIAL    │
                    └──────────────┘

  UDGAM localised the origin to the pipeline corridor and correctly
  excluded all vessels present at detection time. It did not identify
  the anchor strike, which happened eight months earlier — outside
  any 24-hour rewind.
```

**Design `MISS` to look as confident as `HIT`.** Same size, same weight, same placement — a different colour and nothing else. It is a feature, not an apology, and the styling is what communicates that. If a miss looks like an error state, we've undone the whole point of the screen.

`source_url` is a real, clickable, external link. A judge who clicks through to an actual NTSB report has just verified us themselves.

**Primary action:**
> **`Try another case →`** → back to the gallery

---

# PART C — SELF-GUIDING UX

*Nine rules. These are the HOD's requirement, made concrete.*

**C1. Never a blank state.** Something is always pre-selected. Arriving on Detect selects the best detection; arriving on Attribute expands suspect #1. A judge should never have to discover that something is clickable in order to see anything.

**C2. One primary action per screen, always bottom-right, always the same shape and colour.** After the first screen they stop reading it and just move their hand there. That is the goal.

**C3. Progress is always visible.** A five-dot indicator: `Pick ○ Detect ● Trace ○ Find ○ Verify`. They know where they are and that it ends.

**C4. Plain language first, technical term second.** "How stretched" then "(elongation)". "Where the oil came from" then "(origin probability field)". The judge for whom the technical term means something still sees it; the judge for whom it doesn't isn't blocked.

**C5. Every number has an info affordance.** A small `ⓘ` opening one plain sentence. *"Elongation is length divided by width. Oil dumped by a moving ship is long and thin; algae is usually round."*

**C6. Demonstrate, don't instruct.** The auto-play on Trace is worth more than any tooltip. Where you can show the interaction, show it.

**C7. Nothing looks clickable unless it is.** The most common way a judge gets stuck is clicking something inert and concluding the app is broken.

**C8. Idle reset.** After ~90 seconds of no interaction, return to the gallery in a clean state. Judge B should never inherit Judge A's half-scrubbed slider. Also put a small **`Start over`** in the header for the same reason. **This is the single highest-value five lines in Part C** — without it the second judge's experience is worse than the first's, every time.

**C9. Test it on a stranger.** Someone who has never seen the project, no explanation, watch where they hesitate. Do this in Phase 7 with time left to act on it. Five minutes of watching is worth more than an hour of self-review.

---

# PART D — STATES THAT MUST NOT LOOK LIKE ERRORS

Four designed states. Each is a *result*, and each is currently missing or wrong.

**D1. No spill detected.** Zero oil features in `detections.geojson`.
> **No spill detected in this scene.**
> *"We found 2 dark patches. Neither matches oil. This is a calm-wind zone and an algae bloom."*

Show the rejected look-alikes in grey with their reasoning. Stage rail: Trace and Attribute greyed, tooltip *"nothing to trace"*. **This screen is a feature — it proves the system can say no.**

**D2. Attribution not possible.** `origin.abstain == true` or `suspects` empty.
> **Attribution not possible at acceptable confidence.**
> *"The origin cloud is too diffuse to distinguish between vessels. We'd rather say nothing than name the wrong ship."*

Still show the funnel counts, and the abstain reason. Refusing is a maturity signal — style it as a deliberate decision, not a failure.

**D3. Act unavailable.** `acts_available` missing an act. Grey the rail item, tooltip explaining **why**:
> *"No free historical AIS is published for Indian waters — that data gap is part of what this project points at."*

Ennore hits this. It must never crash and it must never look like a bug.

**D4. Loading.** Bundles run to megabytes. Show a skeleton with the case title and a progress hint, never a white screen. Show the map and SAR as soon as they're available and layer the rest in progressively.

> 🚩 **You need real bundles for D1 and D2.** Ask Soumirya for the zero-oil case and Anushka for a deliberately abstaining bundle. Both are on their task lists; chase them, because you cannot build these states against something that has never existed.

---

# PART E — THE PHASES

## PHASE 0 — Honesty and safety *(minutes, do first)*
0.1 **Commit and push `ContextPanel.tsx`.**
0.2 Delete the unconditional "did not converge" line; make the two `abstain` branches actually differ.
0.3 Reword any Trace copy implying the particle spread is the uncertainty. Particles are one control run; the ensemble is in `origin.json`.

## PHASE 1 — Routing and the gallery
1.1 Five routes with shared state: `/`, `/case/:id/detect`, `/trace`, `/attribute`, `/verify`.
1.2 Gallery reads `cases/index.json` then each `meta.json`. **Never hardcode the case list.**
1.3 Progress indicator, primary-action button component, back navigation.
1.4 Stage rail driven by `acts_available` with the D3 tooltips.

## PHASE 2 — Rebuild Detect and Trace into the flow
2.1 Existing map, layers and slider become screens 1 and 2. Most of this is re-parenting, not rewriting.
2.2 Pre-selection on arrival (C1).
2.3 **Trace auto-play** (B/Screen 2). Runs once, then rests fully-rewound with a pulsing handle.
2.4 Live `T − Xh Ym` readout, not a frame index.
2.5 Parse `time_window_method`; render bounded vs convergence differently.

## PHASE 3 — Attribute
3.1 Funnel graphic from `suspects.funnel`, including `dropped_short_track`.
3.2 Suspect cards with the `components` breakdown; **null ≠ zero** — a not-applicable component renders as "n/a", never as a zero bar.
3.3 Hover-a-card → highlight-that-track.
3.4 Exclusion panel, prominent.
3.5 `dark_vessels` markers + the AIS-layer-off reveal.
3.6 `infrastructure` findings.
3.7 `repeat_offender` badge where present.

## PHASE 4 — Verify
4.1 Two-column layout from `verification.json`.
4.2 Verdict badge, four values, **`MISS` styled as confidently as `HIT`**.
4.3 `source_url` as a real external link.
4.4 The human-written `explanation`, rendered as prose.

## PHASE 5 — The deferred rendering fixes
5.1 **`BitmapLayer`** — render the 120×120 grid to an `OffscreenCanvas` with **alpha proportional to value**. A hard alpha cutoff leaves a fringe of just-above-threshold cells that reads as a second, non-existent cloud. Author the colour ramp in the same pass.
5.2 **Union camera framing** — extend `lib/extent.ts` to `bounds.json ∪ particle extent ∪ origin.bounds`. The real cloud sits ~98% outside the SAR scene and particles leave the top of frame around frame 45 of 97. Use a **per-stage camera** so Detect can frame the scene tightly while Trace fits the union — otherwise Detect loses 40% of its scale to make Trace possible.
5.3 New fields: `ship_detections` as a map layer, `discharge_class` as a badge on the object card, `age_hours` + `age_method` on the origin card.

## PHASE 6 — Self-guiding pass
Part C, C1 through C8. Then C9 — test on a stranger, watch, fix.

## PHASE 7 — Real data
> 🚩 **WAIT for Akshat's first real bundle.**

7.1 Load Ennore. Directional sanity: slick low and slightly west, particles fanning up and right, cloud north-east and above the top of the image. **If the origin ever renders south-west of the slick, something is flipped.**
7.2 **Re-tune every visual constant.** All were fitted to a round in-frame blob; on a 4.4:1 streak sitting mostly off-screen, particle radius, opacity ramps, colour domain and zoom limits are all wrong at once. Your own report names this as the highest-probability failure and it is a schedule problem, not a code problem — start the hour the first bundle lands.
7.3 Then each US case. **Watch negative longitude** — everything worked at 80°E; California is −118°.
7.4 Build D1 and D2 against the real bundles when they arrive.

## PHASE 8 — Demo machine and offline
8.1 Run on the actual demo laptop. Re-measure frame times with all seven cases loaded.
8.2 **Run with wifi off.** If the basemap style is remote, vendor it locally or drop the basemap.
8.3 Fix the bundle re-download on case switch-back — with seven cases it will bite.
8.4 Record the fallback video on the demo machine, and re-record it whenever the build shown changes.

## PHASE 9 — Integration alongside Akshat
He drives the pipeline side of each case; you drive the frontend side. When a bundle looks wrong on screen, you diagnose whether it is a render bug or a data bug and route it to the right owner. **Never patch data in the frontend** — surface the error, name the file, tell Akshat. A frontend workaround hides the bug until demo day and then it is someone else's.

---

# PART F — RISKS

**F1. Re-tuning against real data *(HIGH, and it's a schedule risk not a code risk)*.** Every constant was fitted to `case-000`. Phase 7.2 is the mitigation and it must start the moment the first real bundle exists.

**F2. Offline failure *(MEDIUM, total if it fires)*.** Remote basemap plus dead venue wifi equals a blank map. Phase 8.2.

**F3. Seven bundles at several MB each *(MEDIUM)*.** Cache parsed bundles in memory, keyed by case id. Never re-parse on switch-back.

**F4. Judge finds a dead control *(MEDIUM)*.** Nothing on screen may be inert. Better four things that work than eleven where three don't.

**F5. Contract drift *(MEDIUM)*.** New fields are arriving from three people. Every optional field needs a safe absent-path. A missing `age_hours` should hide a row, not throw.

**F6. `null` rendered as zero *(MEDIUM, silent and it's an honesty bug)*.** Jaiveer's not-applicable components are `null`. A zero-height bar says "we measured this and it scored nothing" — which is a different and false claim. Render "n/a".

**F7. Idle state between judges *(LOW, high embarrassment)*.** C8.

---

# PART G — REFERENCE

**G1. Stack, fixed.** Next.js · MapLibre GL JS (no token) · deck.gl `ScatterplotLayer` + `BitmapLayer` · Tailwind · Recharts · Zustand. **No localStorage or sessionStorage** — all state in memory. A new dependency is pinned and announced to the group.

**G2. Performance rules.** Parse each bundle once; consider `Float32Array` for particle positions. Slider state feeds the deck layer only, never re-renders the map container. `updateTriggers` on data change. No per-frame allocation. Escape hatches if it ever stutters: decimate to every 2nd timestep, or 2000 particles — both invisible to a viewer, and **neither changes the schema**.

**G3. Contract reminders.** `[lon, lat]` everywhere · `origin.json` grid **row 0 is north** · `origin.bounds ≠ bounds.json` · `duration = (n_steps − 1) × timestep_minutes`, never hardcoded · timestamps UTC with `Z`.

**G4. Escalate to Akshat (45-minute rule).** deck.gl/MapLibre sync failures · stutter surviving both escape hatches · **any bundle field that doesn't match the contract** — that is his to fix, not yours to work around.

**G5. Definition of done**
- [ ] `ContextPanel.tsx` committed; the fabricated-claim line deleted
- [ ] Five screens routed, gallery reading `index.json`
- [ ] Trace auto-plays once and rests; live time readout
- [ ] Attribute: funnel, suspects with `null`-safe components, exclusions, dark vessels, infrastructure
- [ ] Verify: two columns, `MISS` as confident as `HIT`, live source link
- [ ] `BitmapLayer` with alpha-proportional rendering; union per-stage camera
- [ ] All four designed states built against **real** bundles
- [ ] Self-guiding pass complete, including idle reset — and tested on a stranger
- [ ] All seven cases load and switch without re-download
- [ ] Verified on the demo laptop **with wifi off**
- [ ] Fallback video recorded of the build being demoed
