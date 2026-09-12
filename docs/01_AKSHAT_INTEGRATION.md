# AKSHAT — Integration, Cases, Contracts, Verification
*v3. Read with 00_MASTER_PLAN.md (v4) and 05_HARSHITA_INTEGRATION.md. Organised in phases, not days.*

> **You are the producer side of integration: everything upstream of the case bundle.** Harshita owns everything downstream of it. The handoff is a named gate (Part D). You are also the only person on this project with zero components of your own — that is deliberate. **Your value is slack.** When someone's handoff breaks, you are the person with room to fix it. Protect that by refusing extra work, not by taking it.

---

# PART A — WHERE YOU STAND

## A1. What you built

The JSON contracts. `case-000`. `validate_case.py`. `make_case000.py`. The repo skeleton and the three frozen conventions. The fencepost ruling (`n_steps` 96→97, commit `278f463`). The merge that put all four branches on `main`. The 2-band exporter, run for real on Huntington. The D16 known-origin relax.

**That architecture decision is why this project is where it is.** Four people built four working components, in parallel, on four machines, without ever blocking each other — because nobody imports anybody and everything crosses through files. Most six-person student projects at this stage have three working parts and no system. You have four working parts and a defined seam.

## A2. What you have not done

Written any `verification.json` prose — the researched `official_finding` blocks exist, the human `assessment` does not. Exported anything but Huntington. Produced a single complete bundle: no case has been through all four stages and out the other side.

`main` now carries all four branches and the whole v3+v4 arc, so the catastrophic-risk item from v2 is closed.

## A3. The case library is locked, and every scene id is now full

**Six spill cases plus two rejection cases, all real data, no synthetic case.** Full detail in Master §3.2.

| # | Case | `case_id` | Scene status | What it gives you |
|---|---|---|---|---|
| 1 | **Jacksonville** — 30 Jul 2024, Atlantic | `case-jacksonville-2024` | ✅ full id | Hero. ✅ AIS density verified: 69 s, holds to 240 km. **Not a gap case** (D30) |
| 2 | **Farallones** — 17 Mar 2023, Pacific | `case-farallones-2023` | ✅ full id | Second basin, and hero backup |
| 3 | **Huntington Beach** — 2 Oct 2021 | `case-huntington-2021` | ✅ exported | Infrastructure + NTSB ground truth |
| 4 | **Alaska dark vessel** — 16 May 2023 | `case-gulf-alaska-2023` | ✅ full id | Real radar-vs-AIS cross-check |
| 5 | **Mumbai** — 3 Sep 2023 | `case-mumbai-2023` | ✅ full id | All four source classes at once |
| 6 | **Jamnagar** — 23 Feb 2024 | `case-jamnagar-2024` | ✅ full id | The Indian discharge nobody acted on |
| 7 | **Look-alike** — Ennore 30 Nov 2023 | `case-ennore-lookalike-2023` | finder script | Correct rejection |
| 8 | **No-spill** — Zenodo Part 3 | `case-nospill-zenodo` | Soum nominates | Correct rejection |

**How the ids got resolved, and why it matters beyond the ids.** Cerulean truncates scene ids in its
detail panel, and v2 of this document had you clicking a copy button six times. It has a **public OGC
API instead — `api.cerulean.skytruth.org`, no key, no auth (D23).** One query per case returns the
full scene id, the slick polygon, the centerline, length, area, machine confidence and the attributed
source ids. `scripts/fetch_cerulean.py` wraps it.

That changes three things at once:
- The **BLOCKING** scene-id item is closed.
- Soum gets a **real-incident IoU reference** in every bundle (`cerulean_slick.geojson`) instead of benchmark-only numbers.
- The **answers arrive with the data**, which is exactly why the `--answers` output goes to stdout and `docs/ANSWERS.md`, never into `cases/`.

**Golden Ray is deleted (D17, D25).** No SAR-visible slick, and Huntington makes the infrastructure point better because it has a federal investigation behind it.

**Ennore 2017 is archived to `cases/_archive/` (D18, D25).** A published paper reports detecting that exact spill in Sentinel-1A, **visible in VV, using SLC data**. Our GRD probe found nothing. You cannot ship a "no SAR-visible slick" claim that contradicts the literature without reading the paper first. It stays on disk for the SLC retry; the live Ennore slot is the **30 Nov 2023 look-alike**, a different case making a different point.

**The rule that came out of it, and it is worth more than the case:**
> Before claiming any negative result about a documented incident, check whether someone has already published a positive one.

**And you nearly broke it again, on Jamnagar (D24).** The v4 draft said *"No record anywhere."* One API
query found Cerulean's own detection of the same slick — same scene, 0.2 km away, 0.838 confidence,
four candidate MMSIs attached. The case survives and is stronger for the reframe: an automated system
saw it, even named candidates, and **nothing happened.** Never say "no record anywhere" again; say
*"no investigation, no named party, no enforcement."*

## A4. The backlog, and what is left of it

| # | Item | Raised by | Status |
|---|---|---|---|
| A1 | `TRAPS.md` #2 says ÷100 for HYCOM; **correct is ÷1000** | Anushka | ✅ done |
| A2 | **Merge all four branches to `main`** | everyone | ✅ done |
| A3 | `HeatmapLayer` → **`BitmapLayer`** ruling | Harshita | ✅ ruled (D11) |
| A4 | Bless `time_window_method` into the contract | Anushka, Harshita | ✅ Master §6.5 |
| A5 | Tell Jaiveer to score the **grid**, not the r50 circle | Anushka | ✅ ruled (D8) — re-send with the case announcements |
| A6 | `web/CLAUDE.md` still names `HeatmapLayer` | Anushka | ✅ done |
| A7 | Validator: origin-vs-scene bounds, `area_km2` vs polygon, tighter `Box` pad | Harshita, Anushka | ✅ done |
| A8 | Uncommitted work on three laptops | all three | ✅ captured by the merge |
| A9 | Adaptive field-box pad | Anushka | ✅ funded |
| A10 | Tug/tow display labels on suspect cards | Jaiveer | ✅ ruled — display only |
| A11 | `suspects.json` schema extension | Jaiveer | ✅ approved, Master §6.7 |
| A12 | Confirm **2-band VV+VH GeoTIFF** exports | Soum | ✅ shipped (D14) |
| A13 | Approve `natural_seep` as a fourth `source_type` (D19) | — | ✅ ruled |
| A14 | Approve `ais_source` on `meta.json` (D20) | — | ✅ ruled + validated |
| A15 | Tell Jaiveer to **verify NOAA density at Jacksonville** | Jaiveer | ⬜ **still blocking — send it** |
| A16 | Tell the team `docs/ANSWERS.md` exists and you hold it | everyone | ⬜ send with the case broadcast |
| A17 | Broadcast **D23–D26** | everyone | ⬜ new, send with the case broadcast |

## A5. Problems that are still live

**Nobody but you can write `verification.json`.** It is the strongest new idea in the project, it is pure research and writing, and it is invisible until the last screen. The `official_finding` blocks are researched; the `assessment.explanation` for every case is still owed, by hand, after the stages run. The validator fails the bundle until it exists — that is deliberate.

**VV-only exports would cripple Soum.** His single strongest feature is `vh_mean_depth_db`, at twice the weight of any VV feature. Every export is a 2-band float32 GeoTIFF and the PNG is display only. Check `bandNames()` on every scene as it exports and name the case immediately if one comes back VV-only.

**You have now run the pipeline, once, on stubs and on one real export.** You have never run it on a case that went all the way through four stages. Jacksonville is where that happens, and it will be slower than you expect for reasons that have nothing to do with bugs.

**The library straddles both hemispheres.** −142.7° (Alaska) to +72.2° (Mumbai). A 0–360 longitude leak or a sign error that survives four Atlantic cases surfaces the moment you cross into the Indian Ocean. Alaska at 59.5°N is also the first case where `cos(lat)` matters — a degree of longitude there is about half as wide as at 30°N.

---

# PART B — DECISIONS YOU OWE, WITH THE REASONING TO GIVE

B1–B10 are all ruled and live in Master Part 9 as D8, D11, D12, D14, D19, D20, D21. What is left to
broadcast is **D23–D26**, in one message:

**D23 — Cerulean's public API is how cases get onboarded.** No key, no auth. It returns the full scene
id, the polygon and the attributed sources. Soum gets the polygon as an IoU reference *after* his own
detector has produced one; nobody gets the sources.

**D24 — Jamnagar is reframed.** Cerulean logged it. The claim is now "never investigated", not "no
record anywhere". This changes one deck line and the `verification.json` prose, and it is the second
time this project has been saved by checking a negative claim before shipping it.

**D25 — Golden Ray deleted, Ennore 2017 archived.** `cases/_archive/` is not in `index.json` and not
validated. Ennore 2017 comes back only if the SLC retry finds what Dasari et al. report.

**D26 — `bounds.json` ships `db_min`/`db_max`/`vh_available`.** The contract is corrected to what the
exporter has always written, rather than four consumers being changed to match a doc.

---

# PART C — THE PHASES

## PHASE 0 — Unblock everyone ✅ COMPLETE
Merge, `TRAPS.md` ÷1000, `web/CLAUDE.md`, docs published, `receipts.md` and `_INTEGRATION.md` opened.

---

## PHASE 1 — Case onboarding ✅ COMPLETE except 1.5 and 1.6

### 1.1 Full Sentinel-1 scene ids ✅
All six resolved from the Cerulean API (D23). Master §3.2 carries them. `scripts/fetch_cerulean.py`
re-derives any of them in one command, so nothing here depends on a browser session.

### 1.2 The Cerulean record for every case ✅
`cases/<id>/cerulean_slick.geojson` in each bundle — polygon plus centerline, no attribution. Two uses:
- Source material for `verification.json` (Phase 4)
- **Ground truth for Soum's segmentation on a real incident.** *"On the Jacksonville scene our segmentation achieves X IoU against SkyTruth Cerulean's operational detection of the same slick"* is a much stronger claim than a benchmark figure. **Give him the polygon only after his own exists** — see Part H.

Huntington has **no** Cerulean record. Its ground truth is NTSB MIR-24-01, which is better.

### 1.3 VH availability per case
`gee_scene.py` prints `bandNames()` and shouts on a VV-only scene. Confirm as each export runs and
record it in `bounds.json` (`vh_available`).

### 1.4 `ais_source` per case ✅
`noaa_dense` for cases 1–4 (US EEZ, NOAA Marine Cadastre). `gfw_hourly` for cases 5 and 6 (Indian EEZ,
Global Fishing Watch). Required whenever `attribute` is in `acts_available`, and the validator now
enforces it. It decides which of Jaiveer's scoring components can fire at all (D20).

### 1.5 Global Fishing Watch — token in hand, coverage unchecked ⬜
Token goes in `.env` as `GFW_API_TOKEN`; `.env` is already gitignored. Run
`scripts/gfw_probe.py` for **2023-09-03** and **2024-02-23** over the Arabian Sea.

**A correction to carry:** the GFW report in circulation claims the AIS Vessel Presence dataset returns MMSI, name, IMO and positions. **It does not.** GFW's own documentation says it *"shows vessel presence patterns and movement corridors, but does not provide individual vessel positions"* — it is a gridded layer served through the 4Wings tile API. For tracks you want the **Vessels API** and the **Events API**; the latter includes **AIS-disabling events**, which is Jaiveer's gap analysis already productised on GFW's full-resolution underlying data, so gap analysis may still be reachable *through that endpoint* even though it is impossible from the hourly presence layer. There is also a **SAR vessel detections** endpoint that flags non-broadcasting vessels — use it to *validate* Soum's ship detector, never to replace it, because building it ourselves is the differentiator.

If coverage fails, cases 5 and 6 drop to `detect + trace` and the Indian story becomes *"the query reduces to one database lookup, and the database does not exist"* — which is still a strong screen. See Part I.

### 1.6 The no-spill scene ⬜
Ask Soum for one clean-ocean scene from Zenodo Part 3. Case 8 is scaffolded and **held out of
`cases/index.json`** until he nominates, so the gallery never 404s. The look-alike case is settled —
Ennore 30 Nov 2023 is better than anything from Zenodo, because it is the same coast and sensor as a
real spill with dark patches that provably cannot be oil.

### 1.7 `cases/index.json` and the `meta.json` stubs ✅
Presentation order 1 → 8 per Master §3, default `case-jacksonville-2024`.

### 1.8 Announce each case as it lands ⬜
> 🚩 **Do not batch this.** Every case unblocks three people on different tasks. Message the group per case with: scene id, UTC timestamp, bounding box, `ais_source`, and which acts apply.

~~**One message goes out first:** Jaiveer verifies NOAA AIS density at Jacksonville.~~ **DONE, and it came back clean** — 69-second reporting interval at the case-1 position, holding out to 240 km, no thinning. Hero confirmed; nothing reshuffles. The check also corrected the distance: **~170 km offshore, not ~170 km.**

---

## PHASE 2 — The export pipeline

### 2.1 The four artefacts per case ✅ built, runs per case
| File | What | For |
|---|---|---|
| `sar_vv_vh.tif` | **2-band float32 GeoTIFF, dB, native 10 m** | Soum's classifier — the real numbers |
| `sar.png` | VV, 8-bit, clamped and stretched | display only |
| `bounds.json` | west/south/east/north + width_px/height_px + **the dB clamp used** + `vh_available` | everyone |
| `thumb.png` | small preview | the gallery |

The clamp is recorded so Soum can invert it exactly. Huntington needed **[−25, −5]**, not the [−25, 0]
default — a clamp is per-case, and changing one is a broadcast, not a silent edit.

### 2.2 Export mechanics
`Export.image.toDrive` with `crs: 'EPSG:4326'`, `maxPixels: 1e10`. **`task.start()` submits it** — the
old "press RUN in the Tasks tab" note was wrong and is fixed. Watch with `earthengine task list`, then
move `Drive/naap_exports/<case>_sar_vv_vh.tif` into `cases/<case>/sar_vv_vh.tif`.

On size: a 0.6° × 0.6° box at 10 m across two float bands is roughly 6600 × 6600 × 2 — several hundred MB. **Tighten the box around the slick before you drop resolution**, because 10 m is what Soum's Zenodo training data uses and matching it matters more than covering extra sea. `fetch_cerulean.py` prints a padded box derived from the real polygon; start there.

### 2.3 Verify every export by eye
Coastline where land should be, sea as grey speckle, any slick a visible dark streak. Blank or black means the clamp is wrong.

### 2.4 Scaffold `meta.json` BEFORE exporting
`gee_scene.py` never overwrites an existing `meta.json`, so hand-authored metadata survives. Export
into a case folder that already has its meta, or you will get an `EDIT ME` stub you then have to redo.

### 2.5 Deliver case by case
> 🚩 Soum's real-scene inference is blocked per case on this. Anushka's field fetch is blocked on `meta.detection_time` being real.

**Deliver in library order** — Jacksonville first, since it is the hero and the one the deck is built around. Then Farallones, Huntington (done), Alaska, Mumbai, Jamnagar, and the two rejection cases last.

---

## PHASE 3 — Validator hardening and the exporter ✅ COMPLETE

Done in the v3 pass and extended in the v4 pass: `verification.json` checks, `cases/index.json`,
extended `suspects.json`, `origin.bounds` vs scene bounds, `area_km2` vs polygon shoelace, the span
fencepost, the `Box` pad, `known_origin` (D16), **`ais_source` (D20), the `natural_seep` block,
`particles_forward.json`, the `origin` age block, and the `gfw_hourly` null-not-zero warning.**
`build_case.py` assembles and checks; it does not compute and it never repairs another stage's output.

---

## PHASE 4 — Verification content *(yours alone, and it is writing not coding)*

For each case with `verify`, research and write `verification.json` by hand.

### 4.1 Go to the primary source
For Huntington Beach that is **NTSB MIR-24-01 itself**, not a news summary — it is the only case in the library with a federal investigation behind it, and it is a document a judge can go and read.

For Jacksonville, Farallones, Alaska and Mumbai the source is the **Cerulean record**, plus any press that exists. Write it as *"SkyTruth Cerulean attributed this slick to vessel X"*, **never** *"vessel X was proven responsible"* — it is another algorithm's output with analyst review, not a court finding, and `source_type` is `algorithmic_attribution`, never `official_investigation`.

For **Jamnagar the finding is the absence of one, and it must be stated precisely (D24):** Cerulean's
detector logged the slick and listed candidate vessels; no investigation was opened, no party was
named, no enforcement followed. `official_finding` records that explicitly, cites the Cerulean slick,
and `source_type` is `none`.

### 4.2 Fill `official_finding`
Summary, responsible parties with IMO where you have it, source name and URL, source type, volume, and — importantly — `caveat`. Huntington Beach's caveat carries the whole case: **the anchor strike preceded the release by eight months, so no vessel was the proximate source at detection time.**

### 4.3 Fill `naap_result` from the actual output files
After the stages have run. Not from memory, not from an earlier draft, not from what you hoped.

### 4.4 Write `assessment` honestly
`verdict` ∈ `hit | partial | miss | not_applicable`. **The `explanation` is human prose. Never generate it.**

Expected verdicts, written now so you notice if reality diverges:
- **Jacksonville** — **no longer blind** (D31: verifying AIS density required identifying the vessel) and **pre-registered as a possible `partial`/`miss`**: the `gap` component gives full marks to a competing vessel 7.4 km out, 12.5 kn, silent 142 minutes, and zero to the documented one. If it outranks, that is the verdict we ship, and the explanation is already written.
- **Farallones** — genuinely unknown until it runs, and therefore **the headline blind result**. **A `miss` ships**, and a team that shows one with an explanation of *why* reads as engineering; a team that shows only hits reads as marketing.
- **Huntington Beach** — `hit` if the infrastructure module lands: origin on the pipeline right-of-way, every transiting vessel excluded, which is what the NTSB concluded. `partial` without it. **Naming a transiting vessel here would be wrong.**
- **Alaska** — `hit` if the origin cloud lands on or near the radar contact 4.5 km away. **State the asymmetry plainly:** a vessel dark to Cerulean's *commercial* AIS is a strong claim; a vessel absent from our *free NOAA* archive might be a coverage hole. Two independent absences is evidence; one is not.
- **Mumbai** — expect a multi-source finding. The honest assessment may well be *"infrastructure and a dark vessel are both plausible, and the area has documented natural seepage."* That is a real analytical outcome, not a fudge, and it is the best possible demonstration of why source classification runs before attribution.
- **Jamnagar** — `not_applicable`. There is no official finding because nobody investigated. `what_would_have_helped` says: published Indian coastal AIS, and an authority with a mandate to act on an automated detection.

### 4.5 `docs/receipts.md`
Every GEE scene id and UTC timestamp · every Cerulean slick id and URL · every NOAA AIS filename · **Zenodo DOI 10.5281/zenodo.13761290, CC-BY — mandatory attribution, must appear on a slide** · every verification source URL · the Trujillo-Acatitla paper citation · SkyTruth Cerulean where used.

This is the file you open when a judge asks *"is this real?"* — five seconds, one click.

---

## PHASE 5 — Per-case integration

The loop, per case:

```
  1  you      select + export        → sar_vv_vh.tif, sar.png, bounds.json, thumb.png
  2  Soum     detections.geojson
  3  Anushka  particles.json, origin.json, particles_forward.json
  4  Jaiveer  vessels.geojson, suspects.json
  5  you      build_case.py → validate → PASS
  6  Harshita browser QA → SIGN OFF or REJECT          ← the human gate
  7  you      route the rejection to its owner
```

### 5.1 Jacksonville first, all the way to the browser
Expected bug classes, in the order they usually appear:
1. Coordinate swaps — the validator names them
2. `meta.detection_time` vs `particles.t0` mismatch — validator catches >60 s
3. Particles seeded off the polygon — **plot `detections.geojson` and `particles[0]` together; they must overlap**
4. Origin cloud on land — check the centroid against a coastline
5. Origin cloud rendering off-screen — expected, and it is Harshita's union-camera fix, not a data bug

### 5.2 Then Farallones, Huntington and Alaska — and re-run every check from scratch each time
Jacksonville at −79.6°E, Farallones at −123.9°E, Alaska at −142.7°E, Mumbai at +72.2°E, Jamnagar at +71.9°E. **The library straddles both hemispheres.** Do not assume anything transfers between cases. Alaska at 59.5°N is the highest latitude in the library and the first place `cos(lat)` matters.

### 5.3 Then Mumbai and Jamnagar, then the two rejection cases
Mumbai and Jamnagar are `gfw_hourly`, so Jaiveer's `gap` and `slowdown` must come back `null` rather than zero. **The validator now warns on this** — a zero where a `null` belongs is an honesty bug, not a display bug.

Cases 7 and 8 are cheap once the exporter works — detect-only, and the correct output is zero oil features.

### 5.4 Log every seam event
`docs/updates/_INTEGRATION.md`: what you received, what the validator said, what broke, who fixed it, what state the bundle ended in.

---

## PHASE 6 — The deck and the narrative

### 6.1 Structure, roughly ten slides
1. The hook — a real SAR scene, and the fact the ship sailed away
2. The problem: satellites see slicks days late; nobody runs the model backwards
3. **The India gap** — *"INCOIS tells the Coast Guard where the oil is going. Nobody tells them where it came from. We built the other half."*
4. The system — one diagram, three stages plus verification
5. Detection, **the VH finding**, and the Cerulean-polygon IoU on real incidents
6. Trace — the ensemble, and why the answer is a cloud
7. Attribute — the funnel, dark vessels, exclusions
8. **The honesty slide** — Soum's held-out numbers, Jaiveer's evaluation curve with its operating limit, Anushka's age validation
9. **Prior art** — CleanSeaNet, Cerulean, INCOIS, and the four things we do differently
10. Data provenance and roadmap

### 6.2 The honesty slide is designed as confidently as the wins
Real numbers, named metrics, named splits. *"Leads, not verdicts."*

### 6.3 Prior art, said first
Never pretend CleanSeaNet or Cerulean don't exist — especially now that we use Cerulean's API to onboard cases and its polygons as reference. Master Part 11 has the three responses.

---

## PHASE 7 — Freeze and demo day

### 7.1 Freeze, twelve hours before 15 Sept 17:00
```bash
git checkout -b demo && git push -u origin demo
```
Demo machine runs `demo` and never pulls again. **No exceptions, including for you.**

### 7.2 Freeze checklist
- [ ] Every bundle in `cases/index.json` present, `validate_case.py` PASS on each
- [ ] App runs on the demo machine **with wifi off**
- [ ] Every case loads, every layer toggles, the slider scrubs, every panel populates
- [ ] Click-path check run end to end on the demo machine
- [ ] **Fallback video recorded** and saved locally plus on a phone
- [ ] `receipts.md` complete
- [ ] Deck exported to PDF, on the machine and on a phone
- [ ] Charger, HDMI adapter, hotspot

### 7.3 Two timed rehearsals with someone playing hostile judge.

### 7.4 Demo-day roles
**You** drive the narrative and the hostile questions. **Harshita** drives the laptop so you can face the judges. **Soum, Anushka, Jaiveer** each answer on their own stage — one sentence, then hand back.

---

# PART H — BLIND EVALUATION *(yours to enforce)*

Every case has a documented outcome — a Cerulean attribution, an NTSB finding, a dark-vessel id. **All of it lives in `docs/ANSWERS.md`, which is gitignored and nobody else sees.** `docs/ANSWERS.README.md` is committed in its place so the team knows it exists.

**Why this matters more than it sounds.** If Jaiveer knows which vessel the answer names while tuning weights, he will tune until that vessel ranks first. If Soum knows where the slick is, he will lower the threshold until it appears. If Anushka knows the origin, she will read a wrong cloud as close enough. **None of that is dishonesty** — it is what anyone does when the target is visible. But it collapses "our system identified the vessel" into "we tuned it until it did", and a December panel will ask which happened.

**The Cerulean API makes this harder to hold, not easier.** One query returns the polygon *and* the
attributed MMSIs together. `fetch_cerulean.py` therefore splits them by construction: the polygon is
written into the bundle, the sources are printed to your terminal only. **Do not paste that terminal
output into the group.**

| Person | Gets | Never gets |
|---|---|---|
| Soum | `sar_vv_vh.tif`, `sar.png`, `bounds.json`. `cerulean_slick.geojson` **only after** his detector has produced its own polygon, so the IoU comparison is honest | Where the slick is, before he finds it |
| Anushka | Case list with `detection_time` and bounds; Soum's detections when they land | The documented origin or release time |
| Jaiveer | Case list with dates, bounding boxes and `ais_source`; real `origin.json` when it lands | **Vessel names, MMSIs, IMOs** |
| Harshita | Bundles as produced | The answers |

**Tell everyone the file exists and that you hold it.** Hiding its existence would be worse.

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

You have reduced an unsolved discharge to a single database query, and then shown that the query cannot be run.

**Anonymise the top suspect on screen** for both Indian cases. Mask the MMSI, label it "Vessel A", keep the full data one click away. Naming a real vessel as a polluter with no investigation behind it is a real exposure, and you lose nothing — *leads, not verdicts* was already the line. **This applies to Cerulean's candidate MMSIs on Jamnagar too** — citing that Cerulean listed candidates is fine; reproducing the four numbers on a slide is not.

---

# PART D — THE INTEGRATION PROTOCOL WITH HARSHITA

## D1. The split
**You own everything upstream of the bundle.** Data acquisition, exports, contracts, verification content, `build_case.py`, the validator, routing.
**She owns everything downstream of it.** Browser QA, visual verification, gallery assembly, the demo machine, the fallback video.

The bundle is the boundary.

## D2. Two gates, and they check different things
| Gate | Owner | Answers |
|---|---|---|
| `validate_case.py` | you | Is it schema-valid? Right coordinate order? Dimensions agree? Timestamps parse? |
| Browser QA | Harshita | Is it *renderable*? Does it look physically sensible? Does the story hold? |

**A bundle is not integrated until both pass.**

## D3. Triage — who owns a symptom
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
A short sync every time a bundle changes state: the bundle id and its state — `exported / stages complete / validated / QA passed / rejected: <reason>`.

## D5. The rule that keeps this clean
**Never patch a bundle by hand, and never let her patch data in the frontend.** Fix in the producing code, re-run, re-validate.

---

# PART E — Q&A YOU MUST HAVE COLD

**"Is this real data?"** → `receipts.md`, one click. Real Sentinel-1 via GEE, real HYCOM, real ERA5, real NOAA Coast Guard AIS, real SkyTruth Cerulean records. The only synthetic thing in the project is the fake bundle we used to build the frontend before the pipeline existed.

**"Is this precomputed?"** → Yes, deliberately. The pipeline runs offline and exports a case bundle; the interface plays it back. That is why it scrubs instantly and why it cannot break on venue wifi.

**"Isn't this just CleanSeaNet / Cerulean?"** → Agree enthusiastically, then Master Part 11. Four differences: we run the physics *backwards* so we can attribute a slick found days later rather than matching a coincident track; we use VV **and** VH; we use free public AIS rather than commercial; we publish exclusions.

**"You used Cerulean to find your cases."** → Yes, and we cite it. It is a searchable database of detections; using it for case selection is normal research practice. We also benchmark our segmentation against their polygons, which is a harder test than our own dataset. What we do not take from them is the answer — that is sealed until the bundle validates.

**"How accurate is detection?"** → Soum's held-out, scene-level numbers on the dataset's own designated test set, the two-benchmark framing, and the Cerulean-polygon IoU on five real incidents.

**"How accurate is attribution?"** → Jaiveer's injected-offender curve, with its stated operating limit and the abstention rule above it.

**"Why is your origin a cloud, not a point?"** → Because a point would be a lie. 50 perturbed runs; the spread is the honest uncertainty and it widens with rewind depth.

**"What if you falsely accuse an innocent ship?"** → Nothing happens automatically. Ranked, evidence-backed leads, like a tip line, with a human investigator. And we actively exonerate — here is the exclusion panel and the reason for each.

**"Why no ships on the Indian case?"** → Free bulk historical AIS exists for US waters and not Indian waters. That gap is itself part of what we are pointing at.

**"You got this one wrong."** → Screen 4 already said so. Here is why, and here is what would have caught it.

**"What would it cost to deploy?"** → Satellite data free, currents free, winds free, AIS free. Cost is compute per scene plus storage. **Have a rough annual number for national coverage before the finale.**

---

# PART F — RISKS

**F1. ~~Jacksonville's AIS coverage~~ — CLOSED.** 69 s interval at ~170 km offshore, holding to 240 km. The hero stands.

**F1b. Two scoring components have been measured as near-inert, and the temptation will be to reweight.** `trajectory` scored 1.00 for 13 of 15 once its geometry was fixed; `type_prior` scored 1.00 for all 17 in an offshore lane. Both are now gated to `null` where they cannot discriminate (D27, D28). **Do not let anyone move a weight until the Phase 8 ablation says what the weight buys** — a weight chosen because a component looked weak on one real case is indistinguishable, in December, from a weight chosen to make that case come out right.

**F2. You take on component work.** Your value is slack. Guard it.

**F3. Negative longitude.** Everything works at 80°E and breaks at −118°. Phase 5.2.

**F4. `verification.json` gets deprioritised.** It is the strongest new idea and it is invisible until the last screen. Do it in Phase 4, not at the end.

**F4b. The blind evaluation quietly erodes.** Under pressure someone asks "is this right?" and you answer. **The Cerulean API makes this easier to get wrong** — the answer now arrives in the same response as the data. Keep `--answers` output off the group chat.

**F5. Numbers change under you.** A re-verified scene changes the ocean, which changes the origin, which changes the suspects, which changes the deck. Log every change in `_INTEGRATION.md` and re-check the slides.

**F6. Freeze slips.** An unrehearsed better demo loses to a rehearsed worse one.

---

# PART G — REFERENCE

**G1. Commands**
```bash
python scripts/fetch_cerulean.py --case case-jacksonville-2024 --slick 3046293
python scripts/fetch_cerulean.py --search --bbox -80.2 30.0 -79.1 30.8 --date 2024-07-30
python scripts/gfw_probe.py --date 2024-02-23 --bbox 71.0 19.5 72.8 21.0
python scripts/find_scenes.py --project quizzer-dev-487316 --bbox W S E N --start YYYY-MM-DD --end YYYY-MM-DD
python pipeline/export/gee_scene.py --project quizzer-dev-487316 --scene <id> --case <case-id> --bbox W S E N
python scripts/validate_case.py cases/<id>
python scripts/validate_case.py cases/
python scripts/test_validator.py
python pipeline/export/build_case.py --case <case-id>
```

**G2. Confirmed constants**
- GEE project: `quizzer-dev-487316`
- Cerulean API: `https://api.cerulean.skytruth.org`, collection `public.slick_plus`, **no auth**
- Jacksonville: `S1A_IW_GRDH_1SDV_20240730T232129_20240730T232154_054997_06B32C_7973`, 2024-07-30 23:21:29Z, Cerulean slick 3046293
- Farallones: `S1A_IW_GRDH_1SDV_20230317T142442_20230317T142507_047685_05BA4D_AFD8`, 2023-03-17 14:24:42Z, Cerulean slick 3687325
- Huntington: `S1A_IW_GRDH_1SDV_20211002T015821_20211002T015850_039934_04B9C9_2BF9`, 2021-10-02 01:58:21Z; sea median −20.9 dB VV, slick core −28 to −32 dB; clamp [−25, −5]
- Alaska: `S1A_IW_GRDH_1SDV_20230516T155708_20230516T155736_048561_05D74A_DCBF`, 2023-05-16 15:57:08Z, Cerulean slick 3630124 (dark-vessel id in `ANSWERS.md`, not here)
- Mumbai: `S1A_IW_GRDH_1SDV_20230903T010333_20230903T010358_050156_06095B_9215`, 2023-09-03 01:03:33Z, Cerulean slick 3612640
- Jamnagar: `S1A_IW_GRDH_1SDV_20240223T011114_20240223T011139_052679_065FA4_546D`, 2024-02-23 01:11:14Z, DESCENDING, rel. orbit 107, VV+VH, IW; slick 20.14617 N 71.89911 E; inside VV −25.41 / VH −47.36, clean water VV −17.24 / VH −33.12 — ~8 dB VV depression; Cerulean slick 3477622
- Archived: Ennore 2017 scene `S1A_IW_GRDH_1SDV_20170129T003132_20170129T003157_015039_01892E_6D04` (D18, `cases/_archive/`)
- HYCOM GEE archive ends **2024-09-05** — every case must predate it
- HYCOM velocity: scale 0.001, **divide by 1000**
- `duration = (n_steps − 1) × timestep_minutes`; 97 steps × 15 min = 24 h exactly

**G3. Definition of done**
- [x] `main` carries all four branches; `TRAPS.md` fixed; Part B rulings broadcast
- [ ] Jacksonville's NOAA AIS density verified, hero confirmed or reassigned
- [x] Full scene ids for every case; Cerulean records fetched
- [x] `ais_source` set on every case with `attribute`
- [ ] GFW Arabian Sea coverage checked for 2023-09-03 and 2024-02-23
- [ ] Eight bundles selected, verified, and announced individually
- [x] `docs/ANSWERS.md` created and held; the team told it exists
- [ ] 2-band GeoTIFF + PNG + bounds + thumb exported for every case
- [x] Validator hardened; `build_case.py` assembling and checking
- [ ] `verification.json` written by hand for every case that has one
- [ ] `receipts.md` complete, including the CC-BY attribution
- [ ] All bundles validated **and** signed off by Harshita in the browser
- [ ] Deck done, two rehearsals, freeze executed, fallback video exists
