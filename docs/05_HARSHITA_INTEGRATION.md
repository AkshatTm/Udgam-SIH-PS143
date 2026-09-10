# HARSHITA — Integration: the Human Gate
*v2. Companion to 04_HARSHITA_FRONTEND.md. Read with 00_MASTER_PLAN.md and 01_AKSHAT_INTEGRATION.md. Organised in phases, not days.*

> **Your frontend document covers what you build. This one covers what you do once real data starts arriving.** You are the second half of integration: Akshat owns everything upstream of the case bundle, you own everything downstream of it. He proves a bundle is *valid*; you prove it is *true*. Those are different questions and only one of them can be automated.

---

# PART A — WHY THIS ROLE IS YOURS

## A1. The gap that automation cannot close

`validate_case.py` checks schemas, coordinate order, array dimensions, timestamp parsing, and funnel monotonicity. It is good and it catches the classic seam bugs by name.

**It cannot tell you whether a bundle is renderable, or whether it is physically sensible.** It will happily PASS:

- an origin cloud sitting 98% outside the SAR scene, so the map frames almost nothing
- an origin **south-west** of the slick when the current runs south — physically backwards, schema-perfect
- a particle cloud that doesn't overlap the slick at frame 0
- an `origin.json` grid rendered upside down, which validates cleanly and points at the wrong water
- a suspect whose closest approach sits in empty water
- a slick polygon whose tilt is mirrored — and **mirror images share a centroid**, so a centroid check passes

You have already caught two of these class of bugs by looking: the §5.2 tilt bug, where you correctly diagnosed pixel-space versus lon/lat-space tilt and recognised that a centroid check would not have found it, and the `HeatmapLayer` camera dependence, which you found by reading deck.gl's source rather than arguing from principle.

**That is the skill this role needs, and nobody else on the team is positioned to use it**, because nobody else sees the data rendered.

## A2. The rule
**A bundle is not integrated until it passes both gates.** Validator PASS with a broken render is not done. Your sign-off is a required step, not a courtesy.

## A3. The rule that keeps it clean
**Never patch data in the frontend.** Not a coordinate flip, not a fallback value, not a `|| 0`. A frontend workaround hides the bug until demo day and then it belongs to whoever is standing in front of the judge. Surface the error, name the file and field, tell Akshat.

Corollary: he never hand-edits a bundle to make your render work either. Both fixes go into the producing code.

---

# PART B — THE PER-CASE QA PROTOCOL

Run this on every bundle, every time. It takes about ten minutes once you have done it twice.

## B1. Load and framing
- [ ] The case appears in the gallery with a thumbnail, title, date, badge
- [ ] It opens without a console error
- [ ] The SAR image is visible, correctly oriented, land where land should be
- [ ] The map frames the union of scene + particles + origin — nothing important off-screen

## B2. Detect
- [ ] Detection outlines sit **on** dark features, not beside them
- [ ] Coordinates are in the right hemisphere — Ennore ~80°E/13°N, California ~−118°E/33°N, Georgia ~−81°E/31°N
- [ ] `area_km2` looks plausible against the drawn polygon (a 12 km² slick should not span half the scene)
- [ ] `elongation` ≥ 1.0, `contrast_db` negative
- [ ] `shape_class` matches what you see — a long streak should not say `blob`
- [ ] Look-alikes render grey and clicking one gives a reason

## B3. Trace — the physics sanity checks
These are the ones that matter most, because a wrong answer here looks completely plausible.

- [ ] **At frame 0, particles overlap the slick polygon.** If they start somewhere else, the seeding is wrong
- [ ] Particles move **coherently**, not as random noise
- [ ] The cloud **widens** as you rewind — it must never narrow
- [ ] **The origin is upstream.** Work out the expected direction *before* you look:
  - **Ennore** — the coastal current runs south under the January north-east monsoon, so the origin must be **north-east** of the slick
  - For each US case, ask Anushka for the expected upstream direction and check against it
  - **If the origin sits downstream, something is flipped. Reject the bundle.**
- [ ] `r50 ≤ r90`, and both are plausible (single-digit to low-tens of km, not hundreds)
- [ ] The time readout counts in hours, matches `t0`, and is not off by 5:30 (IST leaking in)
- [ ] `time_window_method` renders honestly — a `bounded` bracket must not look like a measurement
- [ ] The origin heatmap has visible structure, not a uniform wash or a single pixel

## B4. Attribute
- [ ] Funnel counts decrease monotonically
- [ ] Every suspect's track exists on the map
- [ ] Closest-approach markers sit in high-probability regions, not empty water
- [ ] Tracks look like shipping — smooth lines, no teleporting
- [ ] `null` components render as **"n/a"**, never as a zero bar
- [ ] At least one exclusion, with a readable reason
- [ ] Dark-vessel markers, if present, have nothing under them when you toggle the AIS layer off
- [ ] **Read the top suspect's reasons out loud.** Do they make sense as a story? A fishing boat that never entered the origin ranking first is a bug, not a result

## B5. Verify
- [ ] Both columns populated, verdict badge showing
- [ ] `source_url` opens a real external page
- [ ] A `MISS` looks as confident as a `HIT`

## B6. Sign off
Post in the group: `case-<id>: QA PASS` or `QA REJECT — <symptom>, <file>, <field>`. Log it in `docs/updates/harshita.md`.

---

# PART C — TRIAGE: RENDER BUG OR DATA BUG

Your first diagnostic question, always. Getting this wrong wastes two people's time.

| Symptom | Verdict | Route to |
|---|---|---|
| Polygons mirrored or in the wrong hemisphere | **data** | Soum / export |
| Origin downstream of the slick | **data** | Anushka |
| Particles don't overlap the slick at frame 0 | **data** | Anushka (seeding) or Soum (polygon) |
| Origin heatmap upside down | **data** | Anushka — row 0 must be north |
| Cloud renders off-screen | **render** | you — union camera |
| Heatmap changes shape on zoom | **render** | you — BitmapLayer |
| Fringe of faint cells reading as a second cloud | **render** | you — alpha cutoff, use alpha-proportional |
| Suspect with no matching track | **data** | Jaiveer (validator should have caught it) |
| Component bar shows 0 where it should be n/a | **render** | you — `null ≠ zero` |
| Slider stutters | **render** | you — decimate or reduce particles |
| Time off by hours | **data** | timezone; check `t0` vs `detection_time` |
| Blank map with wifi off | **render** | you — remote basemap style |
| Validator PASS but something looks impossible | **data** | Akshat, and the validator needs a new check |

**That last row matters.** When you find a class of bug the validator missed, tell Akshat to add a check for it. Your finding should become a permanent gate, not a one-off catch. Two of your findings — origin-vs-scene bounds and `area_km2` vs polygon — are already going in for exactly this reason.

---

# PART D — THE PHASES

## PHASE 1 — Before real data arrives
1.1 Build the QA checklist (Part B) as a physical page you tick, not something you hold in your head.
1.2 Add a small **debug overlay**, toggled by a keystroke, showing the loaded case id, file sizes, `n_steps`, `n_particles`, `origin.shape`, `time_window_method`, and the current frame's UTC time. This turns "something looks off" into "field X is wrong" in seconds. **Hide it behind a key nobody will press by accident** — a judge must never see it.
1.3 Make every optional field absent-safe. `age_hours` missing should hide a row, not throw. Fields are still arriving from three people.
1.4 Do the dry run with Akshat on `case-000` through `build_case.py` — he has never run the pipeline, and finding the environment and path problems on the fake bundle is free.

## PHASE 2 — Ennore, the first real bundle
> 🚩 **WAIT for Akshat's first real bundle.**

2.1 Run the full Part B protocol. Expect to reject it at least once — that is the gate working.
2.2 **Re-tune every visual constant.** All were fitted to a round in-frame blob; on a 4.4:1 streak sitting mostly off-screen, particle radius, opacity ramps, colour domain and zoom limits are all wrong simultaneously. Your own report names this as the highest-probability failure and it is a schedule risk, not a code risk. **Start the hour the bundle lands.**
2.3 Log every reject and its resolution in `docs/updates/harshita.md`.

## PHASE 3 — The US cases
> 🚩 WAIT per case.

3.1 **Re-run every check from scratch on the first US case.** Ennore at 80°E is identical in both longitude conventions; a 0–360 leak, a sign error or a hemisphere assumption stays invisible until California at −118°E. Nothing transfers.
3.2 Huntington Beach specifically: expect an **infrastructure** finding and vessel **exclusions**. If a transiting vessel is ranked #1 there, that is very likely wrong — the anchor strike preceded the release by eight months. Flag it rather than shipping it.
3.3 Golden Ray: expect the origin on the wreck. Salvage vessels should appear as exclusions, not suspects.

## PHASE 4 — The designed states
> 🚩 WAIT for Soum's zero-oil case and Anushka's forced-abstain bundle. **Chase both** — you cannot build these against a state that has never existed, and both are strong demo moments.

4.1 No-spill screen, against the real bundle.
4.2 Abstain screen, against the real bundle.
4.3 Ennore's greyed Attribute stage with its tooltip.

## PHASE 5 — Gallery assembly
5.1 Read `cases/index.json`; confirm ordering puts the strongest case first — a judge who clicks only one card must land on your best.
5.2 Check every thumbnail renders and every blurb reads as a question rather than a description.
5.3 Verify badges match `case_type` and the first card is visually emphasised.

## PHASE 6 — The demo machine *(you own this)*
6.1 Decide the machine with Akshat, then set it up: clone, install, all seven bundles, app running.
6.2 **Run with wifi off.** If the basemap style is remote, vendor it locally or drop the basemap — the SAR raster is the real backdrop.
6.3 Re-measure frame times with all seven cases loaded. You verified 60 fps at 3000 × 97 under software rendering; confirm it holds here.
6.4 Close everything else, disable notifications and auto-updates, display never sleeps, power plugged in, one browser window, no other tabs.
6.5 Full click-path check across all seven cases.
6.6 **Record the fallback video on this machine, before the freeze.** Full demo run, screen capture. Save locally and on a phone. This is the thing that always gets skipped and it is the only thing that saves you if the laptop dies.
6.7 At freeze: check out `demo`, never pull again.

## PHASE 7 — Demo day
7.1 **You drive the laptop** so Akshat can face the judges and gesture at the screen.
7.2 When a judge takes the laptop, hand it over cleanly and step back. The self-guiding work (frontend doc, Part C) is what carries it — resist narrating.
7.3 Between judges, hit **Start over**. The idle reset should handle it, but do not rely on the timer with someone waiting.
7.4 If something breaks, go down the ladder one rung at a time: toggle the layer off and keep talking → switch cases → fallback video → spare laptop → deck on a phone. **Never debug in front of a judge.** Move on within five seconds.
7.5 Answer on the frontend and on any stage you know. One person talks at a time.

---

# PART E — RISKS

**E1. QA becomes a rubber stamp *(HIGH)*.** Under time pressure, "it loaded, ship it" is the natural failure. The physics checks in B3 are the ones that matter and they are the ones most likely to be skipped, because a wrong origin looks exactly like a right one. Use the checklist as a physical page.

**E2. You get pulled into fixing data bugs *(MEDIUM)*.** You will often be able to see the fix. Don't. Route it. A frontend workaround hides the bug and moves ownership to the wrong person at the worst time.

**E3. Re-tuning eats the schedule *(HIGH)*.** Phase 2.2. It is a known, dateable cost — spend it the hour the first bundle lands rather than discovering it late.

**E4. The demo machine is set up too late *(MEDIUM, total if it fires)*.** Never present from a machine the app has never run on. Decide it early.

**E5. Offline failure *(MEDIUM, total)*.** Phase 6.2.

**E6. The designed states never get built *(MEDIUM)*.** They depend on other people producing unusual bundles. Chase early; they are among the strongest fifteen seconds in the demo.

---

# PART F — REFERENCE

**F1. Your two channels.** Sign-offs and rejects go in the group with the case id. Detail goes in `docs/updates/harshita.md`. Akshat logs the seam side in `docs/updates/_INTEGRATION.md`.

**F2. Reject format.** `QA REJECT case-<id> — <symptom>, file <name>, field <name>, expected <x>, got <y>.` Specific enough that the owner can start without asking you a question.

**F3. Contract reminders.** `[lon, lat]` everywhere · `origin.json` row 0 is **north** · `origin.bounds ≠ bounds.json` · `duration = (n_steps − 1) × timestep_minutes` · timestamps UTC with `Z` · `null ≠ zero`.

**F4. Escalate to Akshat immediately.** Any bundle field not matching the contract · a validator PASS on something physically impossible · anything you are tempted to work around in the frontend.

**F5. Definition of done**
- [ ] QA checklist exists as a physical page; debug overlay built and hidden
- [ ] Every one of the seven bundles has an explicit `QA PASS` from you
- [ ] Every reject logged with symptom, file, field, and resolution
- [ ] Visual constants re-tuned against real data
- [ ] No-spill, abstain and disabled-act states built against real bundles
- [ ] Gallery ordered, thumbnails and badges verified
- [ ] Demo machine set up, verified **with wifi off**, frame times re-measured
- [ ] Click path run across all seven cases on the demo machine
- [ ] Fallback video recorded before the freeze
- [ ] `demo` branch checked out at freeze and never pulled again
