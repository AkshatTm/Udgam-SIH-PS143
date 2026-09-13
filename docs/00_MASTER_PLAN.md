# NAAP — MASTER PLAN v4
## SIH 2026 · PS 26143 · Final demo: 15 September, 17:00

> **This supersedes v1, v2 and v3 completely.** It is the single source of truth for architecture,
> contracts, ownership, dependencies and decisions.
>
> **How to use it.** Read Parts 1–5 once, fully. Keep Part 6 (contracts) open while you code — that is where integration fails. Check Part 8 before you say you are blocked. If your personal document conflicts with this one, this one wins. If this one conflicts with reality, tell Akshat — never improvise a schema.
>
> **Everything is organised in PHASES, not days.** Finish a phase, log it, move on. Where a phase says WAIT, do the next unblocked phase and come back.

---

# PART 1 — WHAT WE ARE BUILDING

## 1.1 One sentence
Satellite forensics that traces an oil spill back to the ship that caused it.

## 1.2 The problem, and why it is not already solved here
Oil is spilled at sea; the ship sails away. Radar satellites revisit a given patch of ocean only every few days, so by the time a slick is visible it has been drifting for hours or days.

Europe has fused satellite spill detection with ship transponder data since the 2000s. India has **forward** drift prediction — INCOIS runs an operational advisory to the Indian Coast Guard — and **no backward attribution capability at all**.

> *"INCOIS tells the Coast Guard where the oil is going. Nobody tells them where it came from. We built the other half."*

## 1.3 Who this is for
Sponsored by **NTRO**, India's technical intelligence agency — not the environment ministry, not the Coast Guard. Their underlying interest is **maritime domain awareness**: identifying vessels that behave anomalously and go dark at sea. Spill attribution is the demonstrator; the capability generalises.

Two framings of the same system:
- **College jury:** environmental protection, catching polluters who think the ocean has no witnesses.
- **NTRO panel:** maritime domain awareness — correlating overhead imagery with transponder data to identify vessels operating dark.

## 1.4 The four stages
| Stage | Does | Owner |
|---|---|---|
| **1 Detect** | Find slicks in Sentinel-1 SAR, separate oil from look-alikes, measure geometry, find ships | Soum |
| **2 Trace** | Run currents and wind backwards to reconstruct where and when the oil entered the water | Anushka |
| **3 Attribute** | Score vessels, dark vessels and fixed infrastructure against that origin; rank and exclude | Jaiveer |
| **4 Verify** | Compare our conclusion against the official investigation, cited | Akshat writes, Harshita renders |

## 1.5 The binding honesty rule
Internals are binding — **whatever we present on 15 September we defend before an NTRO panel in December.** Therefore:
- No vessel name or MMSI on screen that is not in the real AIS file
- No detection the detector did not produce
- No accuracy number not measured on a held-out, scene-level split
- **A `MISS` on the verification screen ships as readily as a `HIT`**

Precomputation is fine and we say so openly: *"the pipeline runs offline and exports a case bundle; the interface plays it back — that's why it scrubs instantly and can't break on venue wifi."* Fabricated results are not fine.

**And the corollary, learned the hard way twice (D18, D24): before claiming any negative result about
a documented incident — "no SAR-visible slick", "no record of this spill" — check whether somebody
has already published a positive one.** A judge asking *"where's the paper that says the opposite?"*
is a much worse moment than a paragraph explaining why our product and theirs differ.

---

# PART 2 — THE DEMO

## 2.1 Five screens, one direction
```
 GALLERY ──▶ DETECT ──▶ TRACE ──▶ ATTRIBUTE ──▶ VERIFY ──▶ back to GALLERY
 pick a      what is     where &     who did       were we
 case        the slick   when        it            right
```

**The HOD's requirement: a judge operates this with no instructions and nobody standing over them.** That reshapes the frontend from a dashboard into a guided flow. One primary action per screen, always bottom-right. Nothing blank on arrival. The Trace screen **auto-plays its rewind once** so the judge sees the interaction without being told. Idle reset to the gallery after ~90 s so the next judge gets a clean state.

## 2.2 What each screen shows
**0 Gallery** — case cards with thumbnail, title, location, date, a `SPILL`/`LOOK-ALIKE`/`NO SPILL` badge, and a blurb written as a question. First card visually emphasised. Strongest case first.

**1 Detect** — SAR scene, detection outlines already drawn, best oil detection pre-selected, object card with measured features and the "why this classification" bars. Look-alikes shown grey and clickable, showing *why* they were rejected.

**2 Trace** — the rewind slider. Particles unwind; the origin cloud blooms and **visibly widens** the further back you go. Live `T − Xh Ym` readout. Origin card with radii, release window and age band.

**3 Attribute** — the funnel (412 → 63 → 12 → 3), ranked suspect cards with per-component evidence, the exclusion panel, dark-vessel markers, infrastructure findings.

**4 Verify** — two columns: what NAAP concluded versus what the official investigation concluded, with the source document linked, and a verdict badge. **`MISS` is styled as confidently as `HIT`.**

## 2.3 The four claims the demo proves
1. We can tell oil from things that look like oil
2. We can run the physics backwards
3. We can quantify how unsure we are
4. We can turn that into a shortlist of ships — **and say who it wasn't**

---

# PART 3 — THE CASE LIBRARY

**Eight bundles, six of them spill cases. Every one is real data — there is no synthetic case.** Each earns its slot by proving something the others cannot.

| # | Case | Type | Acts | AIS | Proves |
|---|---|---|---|---|---|
| 1 | **Jacksonville transit — 30 Jul 2024** · Atlantic, ~170 km off Jacksonville | spill | all | `noaa_dense` | **HERO.** The full chain end to end on a transiting vessel, on the **densest AIS in the library — a measured 69-second reporting interval, 170 km from shore.** The case that shows what the method does when the data is as good as it ever gets. |
| 2 | **Farallones — 17 Mar 2023** · Pacific, off San Francisco | spill | all | `noaa_dense` | Not a fluke: different basin, different year, same pipeline. **Also the hero backup** if Jacksonville's offshore AIS coverage fails. |
| 3 | **Huntington Beach — 2 Oct 2021** · San Pedro Bay | spill | all | `noaa_dense` | **Infrastructure + exoneration.** That we *don't* name a ship when a ship isn't the answer. The only case with a federal investigation as ground truth (NTSB MIR-24-01). |
| 4 | **Alaska dark vessel — 16 May 2023** · Gulf of Alaska | spill | all | `noaa_dense` | **Radar-versus-transponder cross-check, on real data — and the case that carries the silence argument.** A 40 m contact 4.5 km from the slick, dark to Cerulean's commercial AIS. Not a transponder that went quiet for a while: one that never spoke at all. |
| 5 | **Mumbai — 3 Sep 2023** · Indian EEZ | spill | detect, trace, attribute, verify | `gfw_hourly` | **A contested source type on one detection** — five infrastructure candidates and a dark vessel, while the model's own class says "vessel" and no human ever reviewed it. Deciding *what kind of thing* did this is the whole point. |
| 6 | **Jamnagar — 23 Feb 2024** · Arabian Sea | spill | detect, trace, attribute, verify | `gfw_hourly` | **The gap.** A deliberate discharge that an automated detector logged and nobody ever investigated. Found independently by us in an afternoon on free data. |
| 7 | **Look-alike — Ennore, 30 Nov 2023** | lookalike | detect | — | Correct rejection. Same coast and sensor as a real spill, with dark patches that **cannot** be oil because the spill had not happened yet. |
| 8 | **No-spill scene** (Zenodo Part 3) | nospill | detect | — | Correct rejection on clean ocean. |

**Presentation order is 1 → 8 and it is deliberate.** The judge watches the chain complete three times (1–3) before seeing it stop for want of AIS (5–6). The Indian gap then reads as a missing input rather than a weakness in the system, because they have already seen what that input does elsewhere. Jamnagar is the last real case, so it is what they walk away remembering.

## 3.1 The four hard constraints on every US case
1. **US waters** — NOAA Marine Cadastre AIS is free and bulk-downloadable; Indian coastal AIS is not published
2. **Between Oct 2014 and 5 Sep 2024** — Sentinel-1 GRD starts Oct 2014; **HYCOM's GEE archive ends 2024-09-05**
3. **Sentinel-1 coverage confirmed** by running the finder script, not assumed
4. **A citable official finding** — NTSB, USCG, or a documented press account naming the vessel

## 3.2 Confirmed scenes

**All six scene ids are now full and confirmed** — resolved from Cerulean's public API (D23), not
from the truncated strings in its detail panel. Every one carries VV+VH, IW mode.

**Jacksonville** — the hero. `2024-07-30 23:21:29 UTC`, 30.384 N −79.634 W, 31.2 km slick, 4.55 km², US EEZ.
Scene `S1A_IW_GRDH_1SDV_20240730T232129_20240730T232154_054997_06B32C_7973`.
Cerulean slick `3046293`, class *"Vessel, coincident"*, machine confidence 0.795.
✅ **The offshore-AIS risk is CLOSED, and it closed as a result rather than a hope.** Jaiveer pulled
NOAA for 30–31 July and filtered a box running 40–260 km offshore: the reporting interval at this
position is **69 seconds and stays there out to 240 km**, matching his Galveston baseline. No
thinning. The hero case stands and nobody replans. *(That check also corrected the distance — this
position is **~170 km** offshore, not the ~100 km earlier drafts claimed.)*

⚠️ **This is NOT a gap case, and earlier drafts said it was.** Inside Cerulean's own −8 h/+6 h
window the documented vessel broadcast **714 times covering 14.0 hours of 14**, with a longest
silence of **130 seconds**. There is no hole at either end. That is a measured result, not an
inconclusive check, and Cerulean's "1 AIS-off event" is almost certainly a vessel-level flag over a
much longer baseline. The gap argument moves to case 4 (**D30**).

⚠️ **Pre-registered, before the scoring run:** on this case the `gap` component works *against* the
documented vessel. A second vessel — 7.4 km from the slick, 12.5 knots, transponder silent for
142 minutes — takes full marks on `gap` while the documented vessel takes zero. That is not a bug;
a ship that close, that fast, silent that long is legitimately suspicious. **So case 1 may return
`partial` or `miss`, and we are writing that down now rather than explaining it afterwards.** Under
Part 1.5 a `miss` ships.

**Farallones** — second case and hero backup. `2023-03-17 14:24:42 UTC`, 37.807 N −123.886 W, 19.6 km, 3.85 km², US EEZ.
Scene `S1A_IW_GRDH_1SDV_20230317T142442_20230317T142507_047685_05BA4D_AFD8`. Cerulean slick `3687325`, class *"Vessel, coincident"*.
**Note:** the same scene carries three other, larger slicks (`3687317`, `3687321`). Ours is the 19.6 km one — the export box must be tight enough that Soum's detector is scored against the right feature.

**Huntington Beach** — `S1A_IW_GRDH_1SDV_20211002T015821_20211002T015850_039934_04B9C9_2BF9`,
`2021-10-02 01:58:21 UTC`, +2.8 h after the first leak alarm. **Not in Cerulean** — its ground truth is the NTSB report, which is stronger.
**Clear comma-shaped slick**: sea median −20.9 dB VV, slick core −28 to −32 dB, ~8–10 dB depression with a crisp boundary. Exported with a dB clamp of **[−25, −5]**, not the default [−25, 0].

**Alaska dark vessel** — `S1A_IW_GRDH_1SDV_20230516T155708_20230516T155736_048561_05D74A_DCBF`,
`2023-05-16 15:57:08 UTC`, 59.555 N −142.714 W, 2.5 km, 0.27 km², US EEZ (Alaska). Cerulean slick `3630124`, class *"Ambiguous"*.
Cerulean carries **a dark-vessel contact roughly 4.5 km from the slick**, estimated length 40 m ± 20%.
**That offset is the point** — the displacement is what the backward reconstruction has to recover, and
the contact's identifier and position live in `docs/ANSWERS.md`, not here, so the reconstruction is
scored against them rather than aimed at them.
Cerulean attaches the same contact to five separate slicks on this scene, which is corroboration, not five findings.
⚠️ **Say this one out loud before a judge does:** Cerulean's human reviewer marked this slick
**`AMBIGUOUS`** — *"not clear after human review if the detection is oil or some other slick."* That is
not a reason to drop the case; it is a reason to present it precisely. **Our claim is about the
radar-versus-transponder cross-check, not about certainty that this is oil** — and a case where an
expert reviewer hedged is the most honest possible place to show what our VH channel and our
explainability bars actually add. If Soum's classifier also hedges here, that is a result, not a failure.

**Mumbai** — `S1A_IW_GRDH_1SDV_20230903T010333_20230903T010358_050156_06095B_9215`,
`2023-09-03 01:03:33 UTC`, 18.518 N 72.198 E, 20.55 km, 7.74 km², Indian EEZ. Cerulean slick `3612640`.
Carries **five infrastructure candidates** and **one dark vessel** — their identifiers and positions
are in `docs/ANSWERS.md` — while Cerulean's model class for the slick itself is `VESSEL` and no human reviewer
ever looked at it. Three source hypotheses, no agreement between them, nobody adjudicating — which is
precisely the situation source classification exists for.

⚠️ **The "natural seep area" warning is NOT confirmed and must not be presented until it is.**
Cerulean's API exposes four AOI layers — EEZ, IHO Sea Areas, Marine Protected Area, User-generated —
and **no seep layer**. Their `cls` table does carry a `NATURAL` class *"such as oil seeps"*, but this
slick is classed `VESSEL`, not `NATURAL`. Either the warning came from somewhere else in their web UI
or it was misread. **Akshat: find the source or drop the claim.** The `natural_seep` source type
itself stays in the schema regardless — see D19.

**Jamnagar** — `S1A_IW_GRDH_1SDV_20240223T011114_20240223T011139_052679_065FA4_546D`,
`2024-02-23 01:11:14 UTC`, DESCENDING, relative orbit 107, VV+VH, IW. Slick at **20.14617 N 71.89911 E**, hook-shaped with vessel-track geometry.
**Measured by us, independently, in GEE**: inside VV −25.41 / VH −47.36 dB; clean water ~5 km away VV −17.24 / VH −33.12. **~8 dB VV depression.**
The VH figure is at or below Sentinel-1's noise floor, so it **corroborates rather than proves** — VV is the primary evidence, and we say that.
**Cerulean also logged this slick** (`3477622`, 7.97 km, 1.58 km², machine confidence 0.838, 0.2 km from our point) with four candidate MMSIs attached. That is independent confirmation the feature is real — and nobody investigated it anyway. See **D24**.

**Look-alike** — Ennore, `2023-11-30 00:32 UTC`, VV+VH. Four days *before* the December 2023 CPCL spill, so its dark patches are provably not oil.

## 3.3 What every case must satisfy, and how these were found

**Cerulean.** SkyTruth's public map (`cerulean.skytruth.org`) is a searchable database of slick detections already attributed to vessels, infrastructure or dark vessels. Cases 1, 2, 4 and 5 came from it, using the date filter **inside the HYCOM window** and the source filters — including the **"Dark vessels only"** toggle, which is how case 4 was found.

**It also has a public OGC API at `api.cerulean.skytruth.org` — no key, no auth (D23).** The
`public.slick_plus` collection returns the full Sentinel-1 scene id, the slick polygon, the
centerline, length/area/confidence, and the attributed source ids, filtered by `bbox` and `datetime`.
`scripts/fetch_cerulean.py` wraps it. The `public.slick_to_source`, `public.source_vessel` and
`public.source_type` tables return 403 — vessel names, flags and IMOs come from the per-slick web page.

**How to read their fields, because three of our claims turned on this:**
- `cls` is the **model's** class: `1 NOT_OIL · 2 ANTHRO · 3 NATURAL (seeps) · 4 INFRA · 5 VESSEL · 9 AMBIGUOUS · 10 LAND · 11 SEA_ICE · 12 ARTEFACT`.
- `hitl_cls` is the **human reviewer's** class, and it is often absent — nobody looked. `8 COIN_VESSEL` is their strongest ("responsible party highly likely to be determined"); `9 AMBIGUOUS` means a trained reviewer could not tell whether it was oil.
- `source_type_1/2/3_ids` are **vessel MMSIs / infrastructure ids / dark-vessel ids** respectively.
- `aoi_type_1/2/3_ids` are **EEZ / IHO sea area / Marine Protected Area** — there is **no seep layer**.
- `max_source_collated_score` is their confidence in the best source. It can be **negative**, which means their own scorer found nothing convincing. Jamnagar's is **−0.909**.

Two caveats that must carry into `verification.json`:
- Cerulean is **another algorithm's output, not court-proven ground truth.** Write *"SkyTruth Cerulean attributed this slick to vessel X"*, never *"vessel X was proven responsible"*.
- Cerulean is **prior art** — see Part 11. Using it to find cases is normal research practice; we cite it and state the four things we do differently.

**A dark-vessel case will never have a news story.** That is definitional, not bad luck: if a journalist could write about it, the vessel was not dark. Case 4 is presented that way deliberately — see Part 12.

**Download the Cerulean record for every case.** The slick polygon it contains is **ground truth for Soum's segmentation on a real incident**, which is a much stronger claim than benchmark-only IoU. It ships in the bundle as `cerulean_slick.geojson`. **The attributed source ids do not** — they are the answer, and they live only in `docs/ANSWERS.md` (Part 16).

---

# PART 4 — ARCHITECTURE

## 4.1 The rule that makes six people possible
**No module imports another module.** Every stage is a script that reads files from `cases/<case_id>/` and writes files back into it. The frontend fetches static JSON and never calls Python.

This is why four people built four working components in parallel on four machines without ever blocking each other. It stays.

## 4.2 The case bundle
```
cases/<case_id>/
  meta.json                 case info, which acts exist
  sar.png                   display raster
  sar_vv_vh.tif             2-band float32 dB GeoTIFF  ← Soum's real input
  bounds.json               geographic bounds + the dB clamp used
  thumb.png                 gallery preview
  cerulean_slick.geojson    SkyTruth's polygon — IoU reference, optional, never the answer
  detections.geojson        Stage 1 → Stage 2, and → frontend
  particles.json            Stage 2 → frontend (the rewind)
  particles_forward.json    Stage 2 → frontend (forward prediction)
  origin.json               Stage 2 → Stage 3, and → frontend
  vessels.geojson           Stage 3 → frontend
  suspects.json             Stage 3 → frontend
  verification.json         Stage 4 → frontend
cases/index.json            the gallery list
cases/_archive/             retired cases — never in the index, never validated
```

## 4.3 Stage 1's internal architecture
Three layers, not two:
```
Layer 1  scene classifier (small CNN)   "is there oil here at all?"   → headline accuracy
Layer 2  U-Net segmentation             "exactly which pixels?"       → IoU, and the polygon
Layer 3  classical hand-crafted features "why, and what shape?"        → the explainability bars
```
The classifier gates the U-Net because the dataset's own authors found U-Net **segments erroneously on look-alike images**. Without the gate, cases 7 and 8 come back with hallucinated oil — and those two cases exist specifically to prove the system can say no.

The classical detector survives as the **ablation baseline**, the **fallback**, and the **ship detector**.

## 4.4 Stage 2's model, and OpenDrift
Production is our own **reduced-order surface advection model**: `velocity = current + 0.03 × wind`, RK2, 15-minute steps, backward via negative dt, 50-member stratified ensemble.

**We do not switch to OpenDrift and we do not switch between models at a threshold.** We run both and render both clouds. Where they agree that is independent confirmation from MET Norway's operational tool; where they diverge, the pattern diagnoses which physics accounts for it.

**Why ours stays in production:** it is validated (5 suites, 20 assertions, exact to 0.000%), the stratified ensemble is the product and OpenDrift gives one trajectory per run, two other people consume its output, and because Anushka wrote every line her guard caught a 10× unit error before a single particle moved.

## 4.5 Stage 3's four source types
| Type | Meaning | Our cases |
|---|---|---|
| `vessel` | Broadcasting ship near the origin at the right time | 1, 2 |
| `dark_vessel` | Radar sees a ship; AIS reports nothing | **4**, and one of the sources on 5 |
| `infrastructure` | Pipeline, platform or wreck — stationary | **3**, and one of the sources on 5 |
| `natural_seep` | Geological seepage — oil nobody spilled | **no case currently uses it** — see §3.2 |

**A system that can only consider vessels will name a vessel even when the source is a pipeline.** That is a false accusation and it is the worst failure mode we have — which is why source classification runs *before* attribution:

```
origin reconstructed
  → fixed infrastructure at the origin?        → infrastructure
  → known natural seep area?                   → natural_seep
  → radar ship with no AIS?                    → dark_vessel
  → otherwise score the AIS fleet              → vessel
```

Without it the correct answer on Huntington Beach is "no vessel responsible", which reads as failure. **With it, the answer is "the source is fixed infrastructure and all transiting vessels are excluded" — which is a hit**, and it is what the NTSB concluded.

`natural_seep` exists because a system that cannot say *"some of this may be geological"* will always
name a culprit, and distinguishing seeps from discharges is a real operational problem for enforcement.
It stays in the schema and the scorer as the fourth class. **It is not claimed on any case in the
library** — the Mumbai seep warning could not be substantiated against Cerulean's API (§3.2), and we do
not put an unsourced flag on a screen. If the source turns up, Mumbai gets it back; if it does not, the
class ships as designed capability with an honest *"not triggered on these six scenes."*

**On stage:** *"Before we name a ship, we ask whether a ship is even the right kind of answer."*

---

# PART 5 — FROZEN CONVENTIONS

Violating these is how the project dies. They are in `CLAUDE.md` too.

1. **Coordinates are `[longitude, latitude]`**, WGS84 (EPSG:4326), everywhere. Never `[lat, lon]`.
2. **Timestamps are UTC, ISO 8601, trailing `Z`, timezone-aware.** Naive datetimes are a bug.
3. **Units:** km, km², m/s, degrees clockwise from north. Coordinates to 5 dp in JSON.
4. **`duration = (n_steps − 1) × timestep_minutes`.** Never hardcode a frame count. 97 steps × 15 min = exactly 24 h.
5. **`origin.json` grid row 0 is NORTH.**
6. **`origin.bounds` is not `bounds.json`.** They are different rectangles.
7. **`null` ≠ `0`.** A not-applicable score is `null`; a measured zero is `0`. Rendering one as the other is an honesty bug.
8. Python 3.11 + venv, pinned. Node 20 for `web/`. **A new dependency is pinned with its justification written next to it, and announced to the group.**

---

# PART 6 — THE FROZEN CONTRACTS

**Keep this section open while you code.** Every field, every allowed value.

## 6.1 `meta.json`
```json
{
  "case_id": "case-huntington-2021",
  "title": "Huntington Beach — San Pedro Bay Pipeline",
  "short_location": "Orange County, California",
  "case_type": "spill",
  "provenance": "satellite",
  "satellite": "Sentinel-1A",
  "scene_id": "<GEE system:index — the real one>",
  "detection_time": "2021-10-02T01:58:21Z",
  "acts_available": ["detect", "trace", "attribute", "verify"],
  "ais_source": "noaa_dense",
  "known_origin": {
    "lon": -81.40, "lat": 31.13,
    "label": "documented fixed source",
    "source_url": "https://www.ntsb.gov/..."
  },
  "gallery": {
    "thumbnail": "thumb.png",
    "blurb": "588 barrels of crude reached Orange County beaches. What released it?",
    "difficulty": "hard"
  },
  "notes": "free text"
}
```
`case_type` ∈ `spill | lookalike | nospill` · `provenance` ∈ `satellite | benchmark` · `difficulty` ∈ `easy | medium | hard` · `acts_available` ⊆ `["detect","trace","attribute","verify"]`.

**`provenance` (optional, D33).** Where the pixels came from — `satellite` for a scene we
exported from GEE ourselves, `benchmark` for a tile out of the Zenodo Part III corpus. Absent
means `satellite`, so nothing already in the library needs backfilling.

It exists because Stage 1 has **two detection paths** and something has to choose between them:
the classical CV + RandomForest path that runs on our own GEE exports, and the CNN scene
classifier that was trained on the Zenodo corpus. `scene_provenance()` originally chose by
sniffing for a missing CRS. That heuristic never worked — **Zenodo Part III tiles carry
EPSG:4326 and a real geotransform, exactly like a GEE export** — so the sniff matched everything
and routed both corpora down the same path. Routing on the *absence* of a property is an
invisible tripwire; this field is the source of truth and the CRS is not consulted.

*Amended 14 Sept.* Two paths were first justified by the belief that the networks do not
transfer to GEE exports. **That was wrong.** It was a channel swap (Soum, `docs/updates/soum.md`).
With channels matched, every live spill case fires and the Ennore look-alike still rejects. Live
cases stay on the classical path **on measured evidence**: Layer 2 beats classical on median IoU
against Cerulean by only 0.504 vs 0.483, and loses on three of five cases. That is too thin a win to
swap the live path this close to the demo. The routing, and this field, are unchanged.

Two consequences that are not optional:

- **It decides what `detections.geojson/confidence` means** (see §6.3). On a `benchmark` case
  the number is a model probability. On a `satellite` case it is a rule margin. The frontend
  must not render the second one as a model confidence bar.
- **It does not license a placeholder coordinate.** Both Zenodo cases are georeferenced, so
  `bounds.json` carries their real boxes. `benchmark` marks the *corpus*, not "no location".

**`known_origin` (optional, D16).** A documented fixed source the trace stage seeds from when
there is no SAR-visible slick — a wreck, a pipeline right-of-way, a collision position. Either
`[lon, lat]` or an object with `lon`/`lat` and an optional `label` and `source_url`. When present
it substitutes for a detection: a bundle may then carry `trace` (and `attribute`, `verify`)
without `detect`, and `detections.geojson` is not required. The frontend must render the origin
as *seeded from a documented source*, never as a NAAP detection. Allowed (and coord-checked) on
a normal detection case too, as a ground-truth pin.

**`infrastructure_candidates` (optional, D38).** Fixed structures Stage 3's infrastructure module
scores against the origin grid and the slick termini (`pipeline/attribute/infrastructure.py`):
```json
"infrastructure_candidates": [
  {"name": "San Pedro Bay Pipeline", "kind": "pipeline", "lon": -118.121, "lat": 33.57,
   "source": "NTSB MIR-24-01, casualty fact table: 33°34.20' N, 118°7.26' W (https://...)"}
]
```
All five keys are required, and `[lon, lat]` is checked for a swap against the trace reach. A structure may sit
off the exported scene; that is a warning, never an error. **`source` is mandatory** because these
positions are *declared case input, not a discovery*, and the finding card says so. Two rules keep
this honest:
- **A candidate comes from a primary public source** (an investigation report, an operator filing).
  **Never from `docs/ANSWERS.md` or from a Cerulean source id.** Declaring an answer-sourced structure
  would hand Stage 3 the answer it is meant to derive.
- **The declaration never moves because of how it scores.** On Huntington, NTSB's own coordinate
  scores below the 0.25 floor (outside the origin grid, 8.2 km from the nearest slick terminus). That is a
  result to report, not a coordinate to adjust.

**`ais_source` (required when `attribute` is available).** `noaa_dense | gfw_hourly`.
NOAA Marine Cadastre reports at a ~71-second median interval; Global Fishing Watch's AIS Vessel
Presence gives **one position per vessel per hour** — roughly 50× sparser. At 12 knots a ship covers
about 22 km in an hour, so on a `gfw_hourly` case the `gap` component is **structurally impossible**
(you cannot see a 30-minute silence in hourly data) and `slowdown` is very coarse. Those components
return `null`, not zero, and the remaining weights renormalise. The frontend renders them "n/a".
Say it openly: *"attribution confidence depends on AIS sampling density, and we state which source
each case used."* See D20.

Dependency rules the validator enforces: `trace` requires `detect` **or** `meta.known_origin`;
`attribute` requires `trace`; `verify` requires `verification.json` to exist; `attribute` requires
`ais_source`.

## 6.2 `bounds.json`
```json
{ "west": -118.17, "south": 33.585, "east": -118.05, "north": 33.70,
  "width_px": 505, "height_px": 577,
  "db_min": -25.0, "db_max": -5.0,
  "vh_available": true }
```
Pixel (0,0) is **top-left = (west, north)**. `db_min`/`db_max` record the stretch used for `sar.png`
so Soum can invert it exactly; `vh_available` says whether `sar_vv_vh.tif` has a second band.
**If the clamp changes that is a broadcast, not a silent edit.**
*(v3 and earlier described this field as a `db_clamp: [min, max]` pair. The shipped shape is the
three scalars above — what `gee_scene.py` writes and what every consumer already reads. See D26.)*

## 6.3 `detections.geojson`
FeatureCollection, with the scene's radar contacts beside `features` (D34):
```json
{ "type": "FeatureCollection",
  "ship_detections": [
    {"lon": -118.104, "lat": 33.602, "px_area": 340, "peak_db": -4.2}
  ],
  "features": [ ... ] }
```
Each feature:
```json
{ "type": "Feature",
  "geometry": {"type": "Polygon", "coordinates": [[[lon,lat], ...]]},
  "properties": {
    "id": "det-01",
    "classification": "oil",
    "confidence": 0.87,
    "area_km2": 12.4,
    "elongation": 8.2,
    "edge_gradient": 0.34,
    "contrast_db": -6.2,
    "shape_class": "linear",
    "discharge_class": "chronic",
    "centroid": [-118.15, 33.62]
  } }
```
`classification` ∈ `oil | lookalike` — not "none", not "oil_spill".
`shape_class` ∈ `linear | blob`. `discharge_class` ∈ `chronic | acute | unknown`.
`confidence` ∈ [0,1]. `contrast_db` **negative** for a dark spot. `elongation` **≥ 1.0**.

**What `confidence` means depends on `meta.provenance` — and it is not the same quantity.**
On a `benchmark` case the detector is the CNN scene classifier and the number is a calibrated
model probability P(oil). On a `satellite` case the classical path produces it, and it is a
**stated rule margin** — how far the feature sits from the decision boundary, not a probability
of anything. The range is [0,1] in both, which is exactly why this is dangerous: the two look
identical in JSON and mean different things.

**The frontend must not render a `satellite` confidence as a model confidence bar.** A bar
asserts calibration we have not measured on those seven cases. Show the margin **in the unit
the rule actually measures — dB of contrast** — as one of two bands, with the value and the rule
named: **clear** at `contrast_db ≤ −4.5` and **marginal** between −4.5 and the −3.0 dB rule, with
a detection sitting exactly on −3.0 labelled *at threshold*. (The rule maps contrast linearly,
`conf = 0.5 + 0.25·(−3.0 − contrast)/3.0`, so −4.5 dB is exactly confidence 0.625.) A
three-band split on the [0,1] number was tried and collapsed: 1 strong, 11 moderate, 0 weak on
the 12 live oil detections. Reserve the percentage for `provenance: "benchmark"`. No new field
for this: `provenance` already separates the two paths one-to-one. If they ever cross — a model
scoring a satellite case — that stops being true and we add an explicit `confidence_kind` then,
not before.

**`ship_detections` is scene-level and lives on the FeatureCollection, not in a feature (D34).**
Radar contacts are an observation about the scene, not about any one slick. Top-level
`ship_detections` is the canonical list: **absent** means the ship detector was not run or not
recorded, **`[]`** means it ran and found nothing — `null ≠ 0` applies here too. Each entry needs
finite `lon`/`lat` inside `bounds.json`, `px_area > 0` and a finite `peak_db`. The old per-feature
`properties.ship_detections` is **deprecated**: still accepted for back-compat, never written by
`run.py`, and if both are present they must agree.

**A radar contact is not a dark vessel.** Darkness is the *absence of an AIS match*, which needs
an AIS cross-check at a known acquisition time. A contact on a case with no AIS, or with the 1970
`detection_time` sentinel, is an **unattributed radar contact** — its darkness is `null`, not
`true`, and it is labelled that way on screen and in notes.
A no-spill case is a FeatureCollection with **zero `oil` features**; look-alikes may still be present.

## 6.4 `particles.json` and `particles_forward.json`
```json
{ "t0": "2021-10-02T01:58:21Z",
  "direction": "backward",
  "timestep_minutes": 15,
  "n_steps": 97,
  "n_particles": 3000,
  "positions": [ [[lon,lat], "... n_particles pairs"], "... n_steps arrays" ] }
```
`positions[0]` is at `t0`; `positions[n_steps−1]` is at `t0 − (n_steps−1)×dt`. With 97 steps at 15 min that is exactly `t0 − 24 h`.
`particles_forward.json` is identical with `"direction": "forward"`. **It is a separate file — never overwrite `particles.json`.**
`t0` must match `meta.detection_time` within 60 s.

## 6.5 `origin.json`
```json
{ "bounds": {"west":..., "south":..., "east":..., "north":...},
  "shape": [120, 120],
  "values": ["... rows*cols floats, row-major from top-left, normalised 0–1"],
  "centroid": [-118.21, 33.71],
  "radius_50_km": 4.2,
  "radius_90_km": 11.8,
  "time_window": ["2021-10-01T08:00:00Z", "2021-10-01T20:00:00Z"],
  "time_window_method": "bounded",
  "ensemble_runs": 50,
  "abstain": false,

  "age_hours": [8, 16],
  "age_method": "combined",
  "age_weathering": "fresh",
  "age_estimators": {"shear": [7,18], "fay": [9,15], "elongation": null},

  "stranded_fraction": 0.03,
  "wind_share": 0.37,
  "opendrift_comparison": {"centroid_separation_km": 2.4, "r90_ratio": 1.08}
}
```
**`shape` is `[rows, cols]` and row 0 is NORTH.** `values` length must equal `rows × cols`. Grid normalised to peak 1.0.
`time_window_method` ∈ `bounded | convergence`. **`bounded` means a search bracket, not a measured release time — the frontend must render it differently.**
`age_method` ∈ `shear | fay | elongation | combined | disagreement | none`. `age_weathering` ∈ `fresh | weathered | unknown`.
`abstain: true` forces Stage 3 to return zero suspects. The agreed trigger is `radius_90_km > 40`.
The last five blocks are optional — absence hides a UI row, it does not throw.

**`wind_share` (optional, 0–1 fraction).** The share of ensemble drift displacement contributed by
the windage term (`run.py:wind_share_of_drift`). It says which input the origin actually rests on:
Jacksonville is current-driven at 0.04, while Gulf of Alaska is wind-driven at 0.73. **A fraction, never a
percent. Omitted, never zeroed**, when the field is synthetic, because a `0` would claim a calm that was never
measured. It is display-only and no Stage 3 component reads it. The validator errors outside [0, 1].

**One trace per case, not per detection (D35).** A case with several `oil` features still has
exactly one `particles.json` and one `origin.json`. Stage 2 picks the seed: every oil feature merged
into one ribbon when `ribbon_metrics` passes every gate (Jacksonville), otherwise the single
highest-confidence oil feature (Mumbai, Gulf of Alaska). Selecting a different detection on screen
does **not** change the trace. Which feature(s) seeded it is written into `meta.notes`, so the
choice is on the record rather than silent.

## 6.6 `vessels.geojson`
FeatureCollection of LineString tracks:
```json
{ "type": "Feature",
  "geometry": {"type": "LineString", "coordinates": [[lon,lat], ...]},
  "properties": {"mmsi": "367123450", "name": "EXAMPLE STAR",
                 "vessel_type": "tanker", "n_points": 214,
                 "max_gap_minutes": 85} }
```
Plausible-set vessels only. Decimate to ≤500 rendered points, endpoints preserved; `n_points` reports the **undecimated** count.

## 6.7 `suspects.json`
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
                     "type_prior": null},
      "component_notes": {"slowdown": "vessel never dropped below cruising speed in the window",
                          "type_prior": "every candidate in this window is a tanker or cargo ship — no discrimination available"},
      "weight_live": 0.65, "components_available": 5, "components_total": 7,
      "closest_km": 3.1, "closest_time": "2021-10-01T14:20:00Z",
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
  "natural_seep": {
    "flagged": true,
    "source": "<citable seep-area source; illustrative only, since Cerulean exposes no seep layer (§3.2)>",
    "note": "Detection falls in an area with documented natural seepage. Some or all of this feature may be geological."
  },
  "excluded": [
    { "mmsi": "367999999", "name": "OTHER SHIP", "closest_km": 6.4,
      "reason": "heading away from the origin throughout the window" }
  ],
  "abstained": false,
  "abstain_reason": null
}
```
Funnel counts must **decrease monotonically**. Suspects sorted by descending score. Every suspect `mmsi` must have a matching track in `vessels.geojson` — the validator enforces this, and it is what makes the honesty rule mechanical.
**`components` values are `null` when not applicable.** Dark vessels have `mmsi: null` and never an invented identity.
`source_type` ∈ `vessel | dark_vessel | infrastructure | natural_seep`.
**On a `gfw_hourly` case, `gap` and `slowdown` must be `null`** — the validator warns on a number, because a zero where a `null` belongs is an honesty bug, not a display bug (D20).
`abstained: true` requires `suspects` empty.

**`closest_km` is measured to the origin-grid peak (D36)** — the distance from the grid's
highest-probability cell to the vessel's report with the highest grid probability. It is **not**
distance to `origin.centroid`. On an elongated cloud the two can be far apart (Jacksonville: peak
10.65 km off the centroid, aspect 3.68:1), and a vessel sitting on the peak would read as "10 km
away". `grid_probability` remains the primary proximity evidence. Anything rendering `closest_km`
labels it as distance to the peak, never "closest approach" to the centre of the rings.

**Applicability gating, the full set.** A component returns `null` when it cannot be measured, never
a number standing in for "we couldn't tell":

| Component | `null` when | Ruling |
|---|---|---|
| `gap` | the AIS is too sparse to resolve a silence (`gfw_hourly`), or the vessel was not under way | D9, D20 |
| `slowdown` | the vessel never varied speed enough for a slowdown to mean anything | D9 |
| `trajectory` | the vessel has **no report outside `radius_90_km`** in the window — it was never observed approaching from anywhere, so there is no approach to assess | **D27** |
| `type_prior` | **every scored candidate falls in the same type class** — the component then adds the same constant to everyone, changing no ranking while inflating every score | **D28** |

**`component_notes` (optional, D29).** An object whose keys are drawn from `components` and whose
values are short plain-language strings. It is **explanation, not evidence** — it may not introduce
any fact the card is not already showing. **Every `null` component should carry one:** the frontend
renders `null` as "n/a", and an unexplained "n/a" invites precisely the question we want answered on
screen. The validator warns when a `null` has no note, and warns when a **non-null component holds
the identical value for every scored suspect** — a constant contributes nothing but score inflation,
and that is the check that catches a `type_prior` of 1.00 across the whole fleet mechanically.

**`weight_live`, `components_available`, `components_total` (blessed, D37 — expected on every
suspect scored by current `score.py`, validator warns rather than fails when absent).**
A renormalised score (D9) says nothing about how much evidence it rests on — 0.98 from two
components out of seven reads as certainty it has not earned. `weight_live` is the summed weight
of the components that were `applicable` for this suspect (so it is `1.0` only when all seven
scored); `components_available` / `components_total` is the same fact as a count, currently always
`7`. Frontend cards must render evidence breadth next to the score — a fixed presentation is not
mandated here, but a bare score with no indication of `weight_live` is what this ruling exists to
prevent. This is the normal case, not an edge case: on every `gfw_hourly` case `gap` and `slowdown`
are permanently `null`, so both Indian cases routinely score from a minority of components.
**Validator note:** a WARN rather than an ERR here on purpose — at the moment this was blessed
(14 Sept), three of four scored real cases (Jacksonville, Huntington, Mumbai) still carried
`suspects.json` written before these fields existed, and hard-failing them the same day would have
turned three PASSes into FAILs over a field, not a wrong number. Re-score to clear the warning.

## 6.8 `verification.json`
```json
{
  "official_finding": {
    "summary": "NTSB determined MSC Danit's anchor contact with the San Pedro Bay Pipeline on 25 Jan 2021 was the initiating event leading to the October 2021 crude release.",
    "responsible_parties": [
      {"name": "MSC DANIT", "mmsi": null, "imo": "9404649", "role": "initiating anchor strike"}
    ],
    "source_name": "NTSB Marine Investigation Report MIR-24-01",
    "source_url": "https://www.ntsb.gov/...",
    "source_type": "official_investigation",
    "volume_reported": "588 barrels",
    "caveat": "The anchor strike preceded the release by eight months. No vessel was the proximate source at detection time."
  },
  "naap_result": {
    "origin_summary": "Origin cloud centred on the pipeline right-of-way, 2.1 km from the reported leak location.",
    "top_suspects": ["<mmsi>"],
    "abstained": false
  },
  "assessment": {
    "verdict": "hit",
    "explanation": "HUMAN-WRITTEN PROSE. Never generated.",
    "what_would_have_helped": "..."
  }
}
```
`verdict` ∈ `hit | partial | miss | not_applicable`. `source_url` must be present and non-empty.
`source_type` ∈ `official_investigation | algorithmic_attribution | press | none` — Cerulean is
`algorithmic_attribution`, never `official_investigation`.

## 6.9 `cases/index.json`
```json
{ "cases": ["case-jacksonville-2024", "case-farallones-2023", "..."],
  "default": "case-jacksonville-2024" }
```
Order is presentation order, strongest first. **The frontend never hardcodes a case list.**
A case directory that is not listed here is not in the demo. `cases/_archive/` is skipped entirely.

---

# PART 7 — OWNERSHIP

| Person | Owns | Primary AI |
|---|---|---|
| **Akshat** | Contracts, case selection, **2-band GEE exports**, `verification.json`, the exporter, the validator, integration (producer side), deck, demo prep | Claude ×2, Codex |
| **Soum** | Stage 1 entire: scene classifier, U-Net, classical features, ship detections, chronic/acute | Claude, Codex, Antigravity |
| **Anushka** | Stage 2 entire: integrator, ensemble, origin, **age estimation**, forward drift, coastline, OpenDrift comparison | Claude |
| **Jaiveer** | Stage 3 entire: AIS, scoring, dark vessels, **infrastructure**, traffic prior, repeat offenders, evaluation curve | Claude, Codex |
| **Harshita** | Frontend entire (5 screens, self-guiding UX), **then integration (consumer side)**, demo machine | Antigravity (most accounts), Claude |
| **Urooz** | **Research lead** — naming, then the two age-engine investigations | Gemini Deep Research, Perplexity Pro, ChatGPT |

Urooz's former design work moved to Harshita; keep it minimal, clarity over polish.

---

# PART 8 — WHO WAITS ON WHOM

**Check this before saying you are blocked.** Most of what looks like a dependency is not one.

## 8.1 Blocked on nobody — start now
- Soum: download Parts 1+2, tile cache, ship detector, chronic/acute
- Anushka: age estimators, adaptive pad, negative-longitude test, coastline upgrade
- Jaiveer: **verify Jacksonville's AIS density first (§14), then build a US-located fake origin and everything runs** — scorer, parity, traffic prior, evaluation curve
- Harshita: all five screens, self-guiding UX, `BitmapLayer`, union camera
- Urooz: all three research tasks
- Akshat: merge, rulings, validator hardening, `verification.json` research

## 8.2 The real dependencies
```
Akshat: case selected + 2-band export
   ├──▶ Soum: real-scene inference          (needs sar_vv_vh.tif + bounds.json)
   └──▶ Anushka: field fetch                (needs real detection_time)

Soum: detections.geojson  ──▶ Anushka: seeding
Soum: ship_detections     ──▶ Jaiveer: dark-vessel cross-check
Soum: discharge_class     ──▶ Anushka: line-vs-point seeding
                          ──▶ Jaiveer: search strategy

Anushka: origin.json      ──▶ Jaiveer: real scoring
Anushka: abstain bundle   ──▶ Harshita: refusal screen
Soum: zero-oil case       ──▶ Harshita: no-spill screen

everyone ──▶ Akshat: build_case + validate ──▶ Harshita: browser QA ──▶ sign-off
```

## 8.3 Stub-first kills most of these
**Every new field is stubbed with garbage in the right shape before the real logic exists.** Soum's `ship_detections: []` stub unblocks Jaiveer's whole dark-vessel module days before real values arrive. This is the single most effective thing anyone can do for someone else.

## 8.4 The integration gate
```
1 Akshat    export
2 Soum      detections.geojson
3 Anushka   particles + origin + particles_forward
4 Jaiveer   vessels + suspects            (US cases only)
5 Akshat    build_case → validate → PASS
6 Harshita  browser QA → SIGN OFF or REJECT     ← the human gate
7 Akshat    route the rejection to its owner
```
**Two gates, checking different things.** The validator proves a bundle is *schema-valid*. Harshita proves it is *renderable and physically sensible* — it will happily PASS an origin cloud sitting upstream-backwards, or an upside-down grid, or a mirrored polygon (mirror images share a centroid, so a centroid check passes). **A bundle is not integrated until both pass.**

---

# PART 9 — DECISION LOG

Settled. Do not relitigate; if you think one is wrong, raise it with Akshat rather than working around it.

| # | Decision | Reason |
|---|---|---|
| D1 | **Train on Zenodo Parts 1+2, test on Part 3** | Part 3 is the authors' designated test set. Training on it means no clean generalisation estimate, and it is a fifth of the data. |
| D2 | **Scene classifier gates the U-Net** | The dataset authors report U-Net segments erroneously on look-alikes. The gate is what makes cases 7 and 8 work. |
| D3 | **Keep the classical feature layer** | It produces the explainability bars. A CNN cannot. It is also the ablation baseline and the ship detector. |
| D4 | **No CNN before the classical path works** | Classifier first, U-Net second, classical detector supplies polygons meanwhile. |
| D5 | **Our advection model stays in production; OpenDrift is a second opinion** | Ours is validated, the ensemble is the product, two people consume its output. |
| D6 | **No model-switch threshold at 48 h or near shore** | The threshold is indefensible without crossover validation, a particle cannot know its future position, and a hybrid cloud is not a coherent uncertainty statement. |
| D7 | **GSHHG coastline upgrade** | Cheap fix for near shore. Huntington Beach is inside San Pedro Bay, where 9 km current cells are partly land. |
| D8 | **Score the origin grid, not the r50 circle** | Real cloud is 4.38:1 aspect with 44.7% of high-probability mass outside r50. |
| D9 | **Applicability gating on gap and slowdown** | 64% of gap hits are docked boats; slowdown is structurally inert for 66% of the fleet. Not-applicable ≠ zero. |
| D10 | **Infrastructure source association** | Two cases have a fixed source. Turns Huntington Beach from a miss into a hit. |
| D11 | **`BitmapLayer`, not `HeatmapLayer`** | HeatmapLayer re-smooths in screen pixels and renormalises per viewport — the answer would change as a judge zooms. |
| D12 | **`time_window_method` is in the contract** | Protects a claim we must defend; the frontend needs it to avoid rendering a bracket as a measurement. |
| D13 | **97 steps, not 96** | `positions[n_steps−1] = t0 − (n_steps−1)×dt`; 97×15 min = exactly 24 h, matching what we say on stage. |
| D14 | **2-band float32 GeoTIFF exports, not PNG-only** | VH is Soum's strongest feature and the signal is ~1 dB deep; 8-bit quantisation destroys it. |
| D15 | **Urooz is research lead** | Design work moves to Harshita; her research could outlive the hackathon. |
| D16 | **`trace` may run without `detect` when `meta.known_origin` is set** | Kept for any future case with a citable known source but no SAR-visible slick. The origin is seeded from the documented coordinate, not detected — the Trace and Verify screens say so, and it stays honest because `known_origin` carries a `source_url`. `detections.geojson` is then not required. **No case in the current library uses this path**, since all six spill cases have a visible slick. |
| D17 | **Golden Ray DROPPED** | No SAR-visible slick, and it made the same infrastructure point Huntington makes better — Huntington has a federal investigation as ground truth. Two cases proving one thing, where one of them has no visible slick, is a wasted slot. |
| D18 | **Ennore 2017 ARCHIVED, not deleted** | Dasari, Lokam & Nadimikeri, *Mar Pollut Bull* 174(1):113182, DOI 10.1016/j.marpolbul.2021.113182, report **detecting this spill in Sentinel-1A, visible in the VV channel, using Level-1 SLC data.** Our probe used GRD via GEE and found no coherent damping. **We cannot ship a "no SAR-visible slick" claim that contradicts published literature without addressing it.** Read the paper's figure and scene id first. Possible explanations: different product (SLC vs GRD), different scene (4 passes exist in the window), or we probed the wrong part of the scene. |
| D19 | **`natural_seep` is a fourth source type** | Without a fourth class the system cannot express "some of this may be geological", which is both a real operational distinction and a credibility asset. **Amended v4:** the original justification — *"Cerulean flags case 5 as a known seep area"* — could not be substantiated. Their API exposes four AOI layers (EEZ, IHO, MPA, user-generated) and no seep layer, and the Mumbai slick is classed `VESSEL`, not `NATURAL`. The class stays because the design argument stands on its own; **the Mumbai claim does not ship until sourced.** |
| D20 | **`ais_source` on every case with `attribute`** | GFW is one position per vessel per hour versus NOAA's ~71 s. `gap` is structurally impossible at hourly sampling and `slowdown` is very coarse. The scorer must know which regime it is in and return `null`, not a misleading zero. |
| D21 | **Blind evaluation: the answers live in a sealed file only Akshat holds** | If Jaiveer knows which vessel the answer names while tuning weights, he will — without meaning to — tune until that vessel ranks first. Same for Soum with the slick location and Anushka with the origin. That is not dishonesty, it is how anyone works when the target is visible, and it destroys the claim. Teammates are **told the file exists and who holds it** — so they understand why "is this right?" goes unanswered during the week — but never its contents. See Part 16. |
| D22 | **No synthetic case in the library** | Real dark-vessel cases exist (case 4), so the planned simulated ghost-ship scenario is dropped entirely. Every bundle is real data, which removes the labelling burden and the honesty exposure that came with it. |
| D23 | **Cerulean's public OGC API is the case-onboarding tool** | `api.cerulean.skytruth.org` needs no key. `public.slick_plus` returns the **full** Sentinel-1 scene id, the slick polygon, the centerline, length/area/confidence and the attributed source ids — which killed the "truncated scene id" blocker outright. Scripted in `scripts/fetch_cerulean.py`. The polygon ships in the bundle as Soum's IoU reference; **the source ids never do** — they are the answer and go to `docs/ANSWERS.md` only. |
| D24 | **Jamnagar is "never investigated", not "no record anywhere"** | Cerulean independently logged this slick (`3477622`, confidence 0.838, 0.2 km from our GEE point) with four candidate MMSIs. The original claim was checkable and would have failed in front of a judge. The reframe is stronger: an automated detector saw it, even produced candidate vessels, and **nothing happened** — no investigation, no named party, no enforcement. Their detection also becomes independent corroboration that our slick is real, and our detector-vs-theirs comparison becomes a result. Applies the Part 1.5 corollary to ourselves. |
| D25 | **Golden Ray deleted from the tree; Ennore 2017 archived to `cases/_archive/`** | D17 is final, so Golden Ray leaves the working tree (history keeps it). Ennore 2017 stays on disk pending the SLC retry D18 requires, but out of `cases/index.json` and out of the validator's sweep. The Ennore slot in the live library is now the **30 Nov 2023 look-alike**, which is a different case making a different point. |
| D26 | **`bounds.json` ships `db_min` / `db_max` / `vh_available`** | v3 §6.2 described a `db_clamp: [min, max]` pair that was never written by `gee_scene.py` nor read by anybody. The contract is corrected to the shipped shape rather than four consumers being changed to match a doc. |
| D27 | **`trajectory` is measured on approach, not at closest approach — and gates to `null`** | The original spec (`docs/team/jaiveer-stage3-attribution.md` §1.5) compared course to the bearing toward the origin *at closest approach*. That can never fire: closest approach is by construction the point where the line to the origin is roughly perpendicular to the course, so a ±60° cone is unsatisfiable. Measured on a real fleet: **0.00 for 16 of 17 vessels, median 126° off.** It is a geometry error, not a data problem. Now measured at the **last report before closest approach at which the vessel was still outside `radius_90_km`** — was it heading in from out there. A vessel with no report outside that radius was never observed approaching at all, so its `trajectory` is **`null`**, not 1.0, which is what stops the corrected component being tautological (it scored 1.00 for 13 of 15 without the gate, because anything that ended up inside the cloud was by definition heading toward it). **No weight moves** until the Phase 8 injected-offender curve reports top-3 rate with and without this component. Changing a weight because a component looks weak on one real case is exactly the tuning D21 exists to prevent. |
| D28 | **`type_prior` gates to `null` on a homogeneous fleet** | It scored **1.00 for all 17** vessels in an offshore lane, where everything is a tanker or a cargo ship. A component that returns the same value for every candidate changes no ranking and inflates every displayed score by its full weight. When all scored candidates share a type class it returns `null` and the remaining weights renormalise. Same principle as D9, third component. |
| D29 | **`component_notes` is blessed into `suspects.json`** | Jaiveer proposed it and it earns its place: a gated component renders as "n/a", and an unexplained "n/a" on a judge-facing card is worse than no card. Optional object keyed by component name, short strings, **explanation not evidence** — it may not introduce a fact the card is not already showing. Every `null` should carry one. |
| D30 | **The gap story moves from case 1 to case 4** | Case 1's Part 3 line — "the only case that exercises gap detection" — was **false**, and measurably so: 714 broadcasts covering 14.0 of 14 hours inside Cerulean's own window, longest silence 130 seconds. Case 4's dark vessel carries the argument better anyway, because a ship that never speaks at all is a stronger version of the same point and it is actually present in the data. Recorded at the same time, before the scoring run: on case 1 the `gap` component gives full marks to a **competing candidate** (7.4 km, 12.5 kn, 142 minutes silent) and zero to the documented vessel, so **case 1 may return `partial` or `miss`**. Writing that down in advance is worth more than explaining it afterwards. |
| D31 | **Blindness is declared per case, never claimed globally** | Verifying AIS density at case 1 *required* identifying the vessel — the check and the answer are the same operation, so that case was never going to stay blind. Separately, Alaska's and Mumbai's source identifiers and coordinates were sitting in §3.2 of a document the whole team reads. Both are now stated openly per case (Part 16) rather than papered over with a blanket claim a panel could take apart in one question. **Case 1 is open**: its documented vessel may be used for diagnostics and worked examples, but **no weight or threshold may be chosen using it** — weights are set on injected scenarios only. Case 2 becomes the headline blind result. **Amended 14 Sept:** case 2's identity was in pushed shared docs between `ee19819` and `72b9540`, so it is blind on weights, not provably on identity (§16.1). |
| D33 | **Detector routing moves to an explicit `meta.provenance` field; the CRS sniff is deleted** | Stage 1 has two detection paths (classical CV + RandomForest for our GEE exports, CNN scene classifier for the Zenodo corpus) and `scene_provenance()` chose between them by testing whether the GeoTIFF had a CRS. That test was **always false**: Zenodo Part III tiles carry EPSG:4326 and a real geotransform exactly like a GEE export, so the sniff matched both corpora and discriminated nothing — every Zenodo bundle would have gone down the classical path. Two rules were violated at once: routing on the *absence* of a property is an invisible tripwire, and the same false premise had been written into `benchmark_scene.py`, which was emitting a Null Island placeholder box for scenes that are georeferenced. `provenance` ∈ `satellite \| benchmark`, optional, absent means `satellite` so nothing needs backfilling. It also carries a second meaning we were going to need anyway: it is what tells the frontend whether `confidence` is a model probability or a rule margin (§6.3). Found by Soum, 13 Sept. **Amended 14 Sept:** the background belief that the networks do not transfer to GEE exports was a channel swap, not a domain gap. With channels matched they do transfer. The behaviour stands on measured evidence: Layer 2's median IoU against Cerulean is 0.504 vs classical 0.483, and it is behind on three of five cases, so live cases stay classical (§6.1). |
| D34 | **Radar contacts move to a top-level `ship_detections` on the FeatureCollection; a contact is never called a dark vessel without an AIS check** | `ship_detections` was nested in each detection's `properties`, but it is a scene-level observation: `run.py` already copied the identical full list onto every feature, so a scene with zero detections had nowhere to put its contacts — both Zenodo bundles silently dropped them (1 on `case-lookalike-zenodo`, 31 on `case-nospill-zenodo`, measured by Soum and reproduced independently) — and the map flattened every feature's copy, drawing Ennore's 72 contacts as 2,088 stacked markers. Top-level key is canonical (absent = not recorded, `[]` = ran and found none); per-feature copy deprecated, accepted, no longer written. **Soum's framing was declined:** he called a no-oil-plus-contact scene the dark-vessel case. Darkness is an absent AIS match and needs AIS at a known time; the Zenodo cases have neither (1970 sentinel), and the Delta contact is a genuine return (29.7σ above the sea) whose identity is unestablished — a structure-or-vessel question no geometric rule can answer. The library's dark-vessel case is Alaska (case 4) — and there our detector finds **no** contact (threshold −8.06, peak −8.79 dB), so its dark-vessel contact is Cerulean's and must never be shown as a NAAP detection. Found by Soum, 13 Sept. |
| D35 | **Trace is per spill event, not per detection** | Mumbai and Gulf of Alaska each carry three oil detections, and `merge_oil_features()` seeds one trace per case: a merged ribbon when the ribbon gates pass (Jacksonville, where Cerulean's own polygon is an 18-part MultiPolygon of the same slick), otherwise the highest-confidence feature. That is deliberate and physically motivated (`docs/evaluation/stage2-numbers.md` §8.4b), but no contract said so. The frontend copy implied per-detection tracing ("Trace this slick back"), and nothing in the bundle recorded the seed — on Mumbai the trace uses `det-01` (1.5 km²) while `det-02` is 5× larger. Ruling: one trace per event, the pipeline chooses the seed, the UI does not promise a re-trace per click, and the seed decision (`seeded_from`, `n_oil`, merged or not) is appended to `meta.notes`. **No schema change.** Per-detection tracing was declined: it would be a schema extension two days from the demo. Raised by Harshita, 13 Sept. |
| D36 | **`closest_km` is measured to the origin-grid peak, not the centroid** | `score.py` measured from `origin.centroid` to the vessel's highest-probability report. On Jacksonville both suspects sat on the grid peak (grid probability 0.946 and 0.943), but the peak is 10.65 km from the centroid on a 3.68:1 cloud, so the cards read "10.2 km" for vessels at the most likely origin. That is D8's argument again — the grid is the object, not a circle around its centroid. Field name and type unchanged; the meaning is fixed in §6.7, and the note text names the reference point. **Known cost:** the map's r50/r90 rings stay centred on the centroid, so the card must say "to the peak", not "closest approach". No score, component or weight is affected. Raised by Jaiveer, 13 Sept. **Ruled but not yet coded** as of 13 Sept — `score.py` still called `grid.centroid`; fixed 14 Sept to call `grid.peak_lonlat()` (already present in `geo.py`), so committed `suspects.json` bundles predating the fix (Jacksonville, Huntington, Farallones, Mumbai) still carry centroid-based `closest_km` until re-scored against real AIS. |
| D37 | **`weight_live`, `components_available`, `components_total` are blessed into `suspects.json` (§6.7)** | Same motivation as D29: a renormalised score (D9) can read 0.98 off two live components of seven with no indication of that on the card. Jaiveer shipped the three fields ahead of the ruling, stated they would come out together if refused, and verified no identity leak (no MMSI/name ever feeds a component). Blessed as a set, required on every suspect. Card design — how evidence breadth is shown, not whether — is Harshita's, informed by these numbers. |
| D40 | **The Indian cases get real AIS: GFW's 4wings report does return per-vessel hourly positions** | We had ruled GFW out for tracks on a sentence in its documentation — *"does not provide individual vessel positions"* — which is true of the **map layer** and which we generalised to the whole API without issuing the request. It is wrong: `/v3/4wings/report` at `spatial-resolution=HIGH`, `temporal-resolution=HOURLY`, `spatial-aggregation=false`, `group-by=VESSEL_ID` returns one row per vessel per hour with `mmsi`, `shipName`, `vesselType`, `flag`, `imo`, `lat`, `lon`. `pipeline/attribute/ingest_gfw.py` writes it into the same parquet schema as `ingest.py`, so nothing downstream changed. **Mumbai: 9 vessels, 31 vessel-hours, funnel 9 → 2 → 0 → 0. Jamnagar: 8 vessels, 43 vessel-hours, 8 → 2 → 0 → 0, and it gains the `attribute` act.** Both abstain — but now because **no vessel entered the origin cloud**, which is a searched negative, not the "nothing was searched" they carried before. Positions are 0.01° (~1 km) cell centres; **`sog`/`cog` are not published there and are written NULL, never derived**, because a course between two 1 km cell centres an hour apart is not a measurement. Non-commercial licence, stated on the provenance slide. The lesson worth keeping: *we ruled out a data source on documentation instead of on a request.* Found 14 Sept. |
| D39 | **Phase 8 shipped: attribution is quoted from the injected-offender curve, never from a live case** | `pipeline/attribute/evaluate.py` injects a synthetic offender — discharge point, gap, speed profile, course and type all controlled — into real NOAA traffic, and reports top-1/top-3 by condition (`docs/evaluation/stage3-injected-offender-curve.md`). Offshore baseline **top-1 0.910** [0.87–0.94] given a cloud carrying 0.5 × r90 of error; **0.488 on hourly AIS**; **1.000 on a perfect cloud, 0.653 at one r90 of error**; **0.556** against an offender with no behavioural signature. Every figure is a **ranking** number given a stated origin quality, an upper bound on end-to-end performance, and is never to be quoted as accuracy on the six live cases. Abstention is reported separately and is never scored as a hit or a miss. The ablation answers **A5** (`trajectory` −0.051, it contributes) and **A6** (`type_prior` −0.024, nearly inert), and raises a new question on `gap`: removing it *improves* top-1 by 0.143 when the offender does not go dark, because real traffic does. **No weight moves before the demo** — one offender design, hours before freeze — but the December decision now rests on a measurement. Also recorded: the first version of the generator made every offender a tanker, which inflated `type_prior` to −0.100; a benchmark that leaks the answer measures the leak. Built 14 Sept on Jaiveer's design. |
| D38 | **`meta.infrastructure_candidates` is blessed (§6.1); `origin.wind_share` enters the contract (§6.5)** | Jaiveer's Phase 4 infrastructure module was built and tested, but `infrastructure[]` was empty on every case because nothing declared a structure. The key already existed in `infrastructure.py:load_candidates`, so the contract is written to the shipped shape `{name, kind, lon, lat, source}`, and the validator now fails on a missing `source` or a swapped coordinate. **Candidates come from primary public sources only, never from `ANSWERS.md` or a Cerulean source id.** Huntington declares the San Pedro Bay Pipeline at NTSB MIR-24-01's casualty location. Mumbai declares nothing: its candidates are Cerulean's attribution, i.e. the answer. **Recorded before the re-score:** NTSB's coordinate lies outside Huntington's origin grid and 8.2 km from the nearest terminus of our oil detection, so the module scores it about 0.006, below the 0.25 floor. Huntington's verdict is therefore expected `partial`, not the `hit` D10 anticipated, and the reason is that our reconstructed origin sits ~6.7 km from the documented rupture. Not tuned. `wind_share` was already emitted on all six spill cases; it is ruled a display-only 0–1 fraction, omitted rather than zeroed on synthetic fields. Ruled 14 Sept. |

---

# PART 10 — CORRECTIONS TO EARLIER DOCUMENTS

**`docs/TRAPS.md` #2 is WRONG.** It says HYCOM velocity is cm/s, divide by 100. **GEE lists m/s with scale factor 0.001 — the correct divisor is 1000.** Anushka's plausibility guard caught this on the first real fetch, before a single particle was integrated. Grep the repo for "divide by 100" and kill every instance.

**The ~53% IoU benchmark is from the wrong dataset.** That figure is from the **Krestenitis** 5-class benchmark, which is not openly available. Our dataset's own authors (Trujillo-Acatitla et al., *Mar Pollut Bull* 204:116549, 2024) report **99% classification accuracy and 96% IoU** on their own test set. Both numbers are real; **the gap between them measures look-alike variety, not model quality** — see Part 12.

**`case-000` taught a wrong SHAPE, not just wrong values.** Three people independently reported this. The real origin cloud is a 4.38:1 streak sitting ~98% outside the SAR scene; the fixture is a tidy circle inside it. **Rule: the first time you see real upstream data, re-check every assumption your stub baked in.**

**`validate_case.py` gaps found by the team:** the `Box` pad is so generous the off-scene warning cannot fire; no `area_km2`-versus-polygon check; `origin.bounds` never compared against scene bounds; span check has a fencepost. All fixed in the v3 hardening pass.

**Ennore 2017 — a published paper may contradict our finding.** See D18. This was caught by Akshat reading around the case rather than by anyone testing the code, and it produced a rule worth carrying:
> **Before claiming any negative result about a documented incident, check whether someone has already published a positive one.**
A judge asking *"where's the paper that says the opposite?"* is a much worse moment than a paragraph explaining why our product and theirs differ.

**Jamnagar — we nearly broke that same rule ourselves.** The v4 draft said *"No record anywhere"*.
A single API query found SkyTruth Cerulean's own detection of the same slick, on the same scene, at
0.838 confidence. The claim is reframed (D24) and the rule now applies to negatives about *data* as
well as negatives about *incidents*.

**Indian-waters detection failures — five measured findings, and they are a demo asset, not an embarrassment.** Ennore 2017 Sentinel-1: imaged +1 day, dawn wind below the contrast floor, VV/VH differences swing ±3–6 dB at random. Ennore 2017 optical: Sentinel-2's nearest pass 3 days late, Landsat 8's 8 days late. Ennore 2023 (CPCL / Cyclone Michaung, 4 Dec): the only Sentinel-1 pass in eight weeks fell on 30 November — **four days before the spill**. Ennore 2023 Sentinel-2: nearest usable pass 6 Dec at 87.2% cloud, and an Inspector probe of the visible plume gave B8 451–532 against clean water at 470 — a ~4% delta, so **sediment, not oil**, since oil absorbs strongly in the near-infrared and would read far lower.
Five failure modes, five different specific causes, two incidents, one coastline. **If detection were reliable and prompt, running the physics backwards would be unnecessary.** That is the argument for the project, stated as evidence.

---

# PART 11 — PRIOR ART

Three systems will be named by an informed judge. **Never pretend they don't exist.** Teams that cite prior art and show what they added look like researchers; teams that hide it look ignorant when a judge names it.

**EMSA CleanSeaNet** (Europe, since the 2000s) — satellite slick detection fused with AIS.
> *"Europe has had this for twenty years. India has forward drift prediction through INCOIS and no attribution capability at all. We're closing a national gap, not inventing a paradigm."*

**SkyTruth Cerulean** — global, automated, ResNet34 U-Net slick detection with AIS attribution, scoring on parity, proximity and temporality over an AIS window from 8 h before the image to 6 h after.
> *"Cerulean is the closest thing to us and it's excellent. Four differences. We run the physics backwards to reconstruct an origin rather than matching a coincident track — so we can attribute a slick found days later, which matters because Sentinel-1's revisit gap means we usually see slicks late. We use VV and VH; they use VV alone. We use free public AIS; they use commercial. And we publish exclusions, not just matches."*

We borrow their parity/proximity/temporality framework **and cite them for it.** We also use their
public API to onboard cases and their polygons as segmentation reference (D23) — and we say so.

Their disclaimer is also our template: they state plainly that SAR alone cannot definitively identify oil slicks and that detections are *potential* slicks. If the leading operational system says that, we say it too.

**INCOIS OOSA** (India) — operational forward drift advisory to the Indian Coast Guard, built on NOAA's GNOME. Our line in 1.2.

**AIS-gap analysis is not our invention** — it is established practice in fisheries enforcement. Reframe honestly: *"applying it to spill attribution, where the gap coincides with a physically-derived origin window, is a much stronger inference than a gap alone."*

---

# PART 12 — THE NUMBERS WE WILL PRESENT

Every number gets its metric and its split named. **Never a single unqualified percentage.**

**Detection (Soum)** — scene classification accuracy, look-alike rejection rate, oil-class IoU, and the classical baseline F1, all on the Part 3 holdout with a scene-level split. Plus the two-benchmark framing:
> *"On the dataset's own benchmark the authors achieve 96% IoU. We achieve X on their designated held-out test set. On the harder Krestenitis look-alike benchmark, published state of the art is around 53%. The gap between those numbers is a measure of how much look-alike variety a dataset contains — that gap is our result, not our excuse."*

**Plus a second, harder detection number, free from D23:** IoU against SkyTruth Cerulean's
operational polygon on five real incidents. *"On the Jacksonville scene our segmentation achieves X IoU
against the polygon an operational system produced for the same slick"* is a different claim from a
benchmark score, and a judge understands it immediately.

**Drift (Anushka)** — integrator exactness (18.0000 vs 18.0 km; round trip 0.0001 km), ensemble spread as **precision not accuracy**, and OpenDrift agreement. **Age ships as an output, not an accuracy claim** — see `docs/evaluation/stage2-age-decision-brief.md` §5/A5, ratified 13 Sept 2026. The four-case validation this line used to promise does not exist: only one case in the library has a documented release time, and the detections it would be measured on have not landed. If Huntington's detection arrives and C3.1 fires, the claim is an explicit **N = 1** with its caveat attached, never "N of 4".
> *"Across the 50 runs of our uncertainty budget, half the endpoints landed within 8.8 km of the cloud's centre."* **Never** *"accurate to 8.8 km"* — there is no ground truth for origin position.

**Attribution (Jaiveer)** — the injected-offender curve with a stated operating limit:
> *"Across N injected scenarios on real AIS traffic, the responsible vessel ranked top-3 in X% of cases. Performance degrades sharply above roughly 40 vessels in the search window, and above that we abstain."*

**The curve must include a per-component ablation** — top-3 rate with and without each component.
That is not a nice-to-have: two components have already been measured as near-inert on real data
(`trajectory` at 1.00 for 13 of 15 once corrected, `type_prior` at 1.00 for all 17 in an offshore
lane), and the ablation is the only evidence that could justify moving a weight. **Until it exists,
no weight moves** (D27, D28).

**Say the refusal path out loud, because it already works on real data.** On real Galveston AIS the
funnel runs **987 → 897 → 17** and the system **abstains** — the top two candidates within 1.1% of
each other. That is the correct answer on a patch of ocean with no spill in it, and it means the
abstention is demonstrable today rather than asserted.

**And the pre-registered one (D30).** On case 1 the `gap` component favours a vessel that is not the
documented one. We wrote that down before the scoring run:
> *"Before we ran this case we recorded that a second ship — seven kilometres from the slick, at
> twelve knots, transponder silent for over two hours — would score higher on transponder silence
> than the vessel the record names. If it outranks, we show that, because a system that only ever
> agrees with the answer key isn't being tested."*

**The error budget.** Current field resolution dominates; wind coefficient second; omitted physics third and only past 48 h; integration scheme negligible.
> *"Our uncertainty is a property of the freely available current field, not of our code. A finer regional model would tighten it — that's the roadmap."*

**Sampling density (Jaiveer, cheap and worth doing).** Take the dense NOAA data from a hero case, downsample it to one position per hour, and re-run the scorer. That turns a qualitative caveat into a measured result — *"at hourly sampling the correct vessel fell from rank 1 to rank N, and the gap component became unavailable"* — and it gives the two-regime comparison a number behind it:
> *"Attribution quality is bounded by AIS sampling density, not by our method. In US waters at 71-second sampling we resolve to a single vessel with a transponder gap as evidence. In Indian waters at hourly sampling we resolve to a small candidate set and cannot assess gaps at all. Same pipeline, same physics — different data. That is the argument for India publishing coastal AIS."*

**Case 4, the dark vessel — lead with the absence, do not apologise for it.**
> *"This one has no news article, no investigation, no named vessel. That is not a gap in our case — that *is* the case. A ship went dark, discharged, and left. Nobody could identify it because nobody has a system that looks. Radar saw it. The transponder record does not. Our origin reconstruction puts the release four and a half kilometres from where the radar contact sits."*

Honest caveat to state alongside it: a vessel dark to Cerulean's **commercial** AIS is a strong claim; a vessel absent from our **free NOAA** archive might be a coverage hole. Two absences from two independent sources is evidence. One is not.

**Case 6, Jamnagar — the sentence that lands hardest in the whole deck (reframed, D24):**
> *"February 2024, Arabian Sea, the approach lanes to the largest refinery in the world. A deliberate discharge — eight decibels of damping, the track geometry of a vessel that turned while dumping. We found it in an afternoon, with free public data, on a student laptop. And here's the part that should bother you: an automated system had already flagged it. SkyTruth's detector logged this slick at 0.84 confidence. It listed four candidate vessels and scored every one of them below zero — its own scorer could not choose between them, because it was matching coincident tracks instead of running the physics backwards. No human ever reviewed it. No investigation was opened. No party was named. The problem isn't that nobody saw it — it's that seeing it was never enough."*

**Never say "no record anywhere" about Jamnagar.** Cerulean's record exists and a judge can pull it
up in ten seconds. The absence we are pointing at is enforcement, not observation.

---

# PART 13 — RULES

1. **Stub first.** First commit of anything new writes a schema-valid file of garbage.
2. **Nothing handed over without a pasteable run command** that produces a valid file.
3. **`python scripts/validate_case.py cases/<id>` must PASS** before handover. Fix the producing code, **never** hand-edit a bundle, **never** patch data in the frontend.
4. **45-minute rule** on external services — stop, message Akshat with what you tried and the exact error.
5. **Fresh AI chat per phase or bug.** Log to `docs/updates/<name>.md` after each phase.
6. **Post checkpoint artefacts in the group** as they happen. Three people finished major work the team could not see because images were never posted.
7. **Push daily.** `main` carrying two commits while four branches hold the project is the highest-probability catastrophic risk here.
8. **Demo prep before 15 Sept 17:00.** The demo machine runs the latest validated `main`, the fallback video is recorded on it, and two rehearsals happen on it. Every bundle shown must PASS the validator.

---

# PART 14 — OPEN ITEMS

| Item | Owner | Blocks | Priority |
|---|---|---|---|
| ~~Verify NOAA AIS density at Jacksonville's position~~ | Jaiveer | — | **DONE** — 69 s interval, holds to 240 km, no thinning. Hero confirmed, no replan. §3.2 |
| **Phase 8 injected-offender curve, with a per-component ablation** | **Jaiveer** | any weight change; the honesty slide | **high** — two components measured near-inert, and nothing moves without this |
| ~~Put the GFW token in `.env`~~ | Akshat | — | **DONE** — token loaded, 782 chars |
| ~~Full Sentinel-1 scene ids for cases 1, 2, 4, 5~~ | Akshat | — | **DONE** — all six resolved from the Cerulean API (D23), §3.2 |
| ~~Download the Cerulean record for every case~~ | Akshat | — | **DONE** — `scripts/fetch_cerulean.py`, polygons in each bundle |
| Confirm VH availability per case via `bandNames()` | Akshat | Soum's best model | high — runs with each export |
| ~~GFW Arabian Sea coverage check for cases 5 and 6~~ | Akshat | — | **DONE** — `gfw_probe.py --all`, 2026-09-12: presence, gap events and SAR-detection endpoints all answer for both `2023-09-03` (Mumbai) and `2024-02-23` (Jamnagar). Cases 5–6 keep `attribute`. ⚠️ Gap-events endpoint returns a large unfiltered count (~10–11k) — **not yet confirmed it accepts a bbox/region filter**; Jaiveer must filter client-side before using it, or the "events" figure is national, not local. |
| ~~Source the Mumbai "natural seep area" warning, or drop it~~ (§3.2, D19) | Akshat | — | **DROPPED** 14 Sept. No source found, so no case claims `natural_seep` and no bundle carries the flag. The class ships as designed capability, "not triggered on these scenes". |
| ~~Confirm the case-1 vessel flag~~ | Akshat | — | **DONE** — cross-checked against three independent AIS databases; the old "CHN" note was wrong, MID `563` (Singapore) is correct. Detail in `docs/ANSWERS.md`. |
| Nominate the no-spill scene from Zenodo Part 3 | Soum | one demo screen | medium — case 8 is held out of `index.json` until it lands |
| Read Dasari et al. 2021 and resolve the Ennore contradiction (D18) | Akshat | whether Ennore 2017 returns from `cases/_archive/` | medium |
| Project name | Urooz | deck, UI header, repo | medium |
| Deployment cost figure for national coverage | Akshat | a Q&A answer | low |
| `docs/receipts.md` complete | Akshat | the "is this real?" question | before the demo |

## Deliberately not building
Repeat-offender tracking at scale · polarimetric decomposition · multi-pass age estimation · live API · auth and multi-user · offline mode. **Stating scope decisions confidently reads as engineering judgement; being caught by them reads as gaps.**

---

# PART 16 — BLIND EVALUATION

**The answers are sealed.** Every case in the library has a documented outcome — a Cerulean attribution, an NTSB finding, a dark-vessel id. Akshat holds all of them in `docs/ANSWERS.md`, which is **gitignored, not pushed, and not shared.** `docs/ANSWERS.README.md` is committed in its place so everyone knows the file exists.

**Why.** If Jaiveer knows which vessel the answer names while he is tuning weights, he will tune until that vessel ranks first. If Soum knows where the slick is, he will tune the threshold until it appears. If Anushka knows the origin, she will read a wrong cloud as close enough. None of that is dishonesty — it is what anyone does when the target is visible — and it destroys the claim, because "our system identified the vessel" collapses into "we tuned it until it did." A December panel will ask which one happened.

**What each person gets:**

| Person | Gets | Does not get |
|---|---|---|
| Soum | `sar_vv_vh.tif`, `sar.png`, `bounds.json`, `ais_source` | Where the slick is. His detector has to find it. **`cerulean_slick.geojson` only after his own polygon exists** — then the IoU comparison is honest. |
| Anushka | Case list with `detection_time` and bounds; Soum's detections when they land | The documented origin or release time |
| Jaiveer | Case list with dates and bounding boxes; real `origin.json` when it lands | **The vessel names and MMSIs.** The box is wide enough to contain the culprit plus decoys anyway, at `2 × radius_90_km`. |
| Harshita | Bundles as they are produced | The answers |
| **Akshat alone** | `docs/ANSWERS.md` | — |

**Cases are named after PLACES, never after vessels.** `case-jacksonville-2024`, not
`case-<vessel>-2024`. The v4 draft named the first two cases after the ships Cerulean attributed them
to, which handed Jaiveer the answer in the folder name — thirty seconds of AIS search and the blind
evaluation is over before it starts. Every case id and every case title in every shared document is a
geographic one. **Do not "fix" these names back.** The vessel names exist in exactly one place, and
they come out on 15 September.

## 16.1 Which results are actually blind — declared per case (D31)

**A blanket claim of blind evaluation would not survive one question from an informed panel, so we
do not make one.** Two things broke it, both found by Jaiveer and both reported rather than buried:

- **Verifying AIS density at case 1 required identifying the vessel.** The check and the answer are
  the same operation — you cannot measure reporting interval "at the vessel's position" without
  knowing which vessel. That check was necessary and correct to run; it simply cost us blindness on
  that case, and it was always going to.
- **Cases 4 and 5 had their source identifiers and coordinates printed in §3.2** of a document the
  whole team reads. They are now scrubbed into `ANSWERS.md`, but scrubbing stops the leak going
  forward — it cannot unread what was read.

| Case | Blind? | Status |
|---|---|---|
| 1 Jacksonville | ❌ **Open** | The density check required finding the vessel. Usable for diagnostics and worked examples; **no weight or threshold may be set using it.** |
| 2 Farallones | ⚠️ **Blind on weights, not provably blind on identity** | The vessel identity was in pushed shared docs from `ee19819` (13 Sept 03:29) until `72b9540` restored the scrubbed versions. Jaiveer's asks #3 and #6–#8 are known to come from reading that version, and he scored this case afterwards. Nobody has claimed to have noticed the name, but we cannot prove nobody did. History was not rewritten. What still holds: **no weight or threshold was set on this case** (the D31 rule), so the result is an honest test of a scorer tuned elsewhere. Say that, not "nobody has seen the answer". |
| 3 Huntington | ➖ n/a | The answer is a published NTSB finding about infrastructure. Blindness was never the claim; the claim is that we reach "no vessel is responsible" independently. |
| 4 Alaska | ⚠️ **Partially compromised** | Dark-vessel position was in a shared doc before the scrub. The *identity* was never exposed, and the real task — recovering a 4.5 km displacement — is still scored, not aimed. |
| 5 Mumbai | ⚠️ **Partially compromised** | Same: infrastructure and dark-vessel positions were in a shared doc. Declared, not hidden. |
| 6 Jamnagar | ✅ **Blind** | There is no answer to leak — that is the case. |
| 7 Ennore · 8 No-spill | ✅ **Blind** | The correct output is "no oil", and the detector has to reach it. |

**The standing rule that survives all of this: weights and thresholds are set on injected scenarios
only, never on a real case.** That is the claim we actually have to defend in December, and it is
unaffected by any of the above — a compromised case can still honestly *test* a model that was
tuned somewhere else.

**On stage this is a strength, said plainly:** *"We'll tell you exactly which of our results were
produced blind and why the others weren't."* (Don't quote a count. Farallones moved on 14 Sept, see the table.) A team that reports the boundary of
its own protocol is doing science. A team that claims a clean one and gets caught is not.

**Everyone is told the file exists and who holds it.** Hiding its existence would be worse — it explains why "is this right?" goes unanswered during the week, and it makes the verification screen a genuine reveal rather than a restatement. Including when it is wrong.

**Akshat does not answer "is this right?" before a case is complete.** Not a hint, not a nudge, not a raised eyebrow. The moment the stages have run and the bundle validates, he opens the file and the comparison is real.

---

# PART 15 — GLOSSARY

**SAR** — synthetic aperture radar; oil damps capillary waves so slicks appear dark. **VV / VH** — polarisations; adding the second polarisation took val F1 0.346 → 0.643, but the feature that did it was computed from VV, so never say "VH is the discriminator". **Look-alike** — algae, calm wind, rain cells that also appear dark; the core difficulty. **dB** — backscatter in decibels. **Damping ratio** — contrast between slicked and clean sea; tracks thickness, not age. **AIS** — ship transponder broadcasts. **MMSI** — vessel id in AIS; imperfect, do not build identity resolution. **Dark vessel** — visible to radar, absent from AIS. **Chronic** — deliberate discharge underway; long, thin, lane-aligned. **Acute** — accident; radial from a point. **HYCOM** — global ocean currents, 0.08° daily, GEE archive ends 2024-09-05, **scale 0.001 → divide by 1000**. **ERA5** — hourly wind reanalysis; signed u/v components. **GEE** — Google Earth Engine. **3% rule** — surface oil moves at current + ~2.5–3.5% of wind speed. **Ensemble** — 50 perturbed reruns; the spread IS the uncertainty. **Abstention** — designed refusal when confidence is insufficient; a feature. **Parity / proximity / temporality** — Cerulean's vessel-scoring metrics, which we borrow and cite. **Verification** — screen 4; our answer against the official finding. **Natural seep** — geological seepage; oil nobody spilled, and a fourth source class. **GFW** — Global Fishing Watch; free global AIS-derived data, one position per vessel per hour, covering 400,000+ vessels of which the majority are non-fishing. **`ais_source`** — `noaa_dense` (~71 s interval) or `gfw_hourly` (1/hour); decides which scoring components are applicable. **Blind evaluation** — teammates build without knowing the documented answer, which lives in a sealed file only Akshat holds. **`slick_plus`** — Cerulean's public API view carrying scene id, polygon, centerline and attributed sources for every detection in their database.
