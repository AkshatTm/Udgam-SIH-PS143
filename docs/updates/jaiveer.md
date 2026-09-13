# Jaiveer — update log

*Newest entry at the TOP. Copy the block from `TEMPLATE.md`, fill four lines, commit it with
your code in the same push. Two minutes after each phase — non-negotiable.*

**Why:** your AI has no memory between chats. This file is the memory. It means you can close a
chat, switch from Claude to ChatGPT, hand your work to someone else, or come back after sleeping,
and lose nothing.

**To resume from it:** *"Here are the master plan, my task document, and my update log. Read the
top entry and tell me exactly where I left off and what the next step is."*

---

## [2026-09-13 12:30] Answers to the three open questions in `_INTEGRATION.md`

**Done:** Re-ran the Menuett gap analysis to settle Akshat's three questions, all from
`data/ais/menuett_2day.parquet`, no new downloads.

**Q1 — is "eleven of 52" before or after the box-boundary fix?** Before. **After the fix it is 6.**
Use 6 on any slide. The split is unusually clean: all five removed were among the five *longest*
"silences" (306–1399 min) and every one began exactly on the search boundary; the six that survive
are 57–144 min and all began mid-box.

```
SURVIVE (6)                       REMOVED as box exits (5)
CONCEPTION III      144.1 min     MSC DON GIOVANNI   1398.9 min   began lon -81.00
STENA PROSPEROUS    142.3 min     MARMAC 302         1264.2 min   began lat  28.51
SIGNET LIGHTNING     89.0 min     SIGNET WARHORSE I  1247.8 min   began lat  28.50
MR B                 80.9 min     CASPIAN DAWN        696.2 min   began lon -81.00
PATRIOT              74.8 min     MAGDALEN            305.8 min   began lon -81.00
SPIEKEROOG           57.5 min
```

Worth stating on the slide that the artefacts were the *biggest* numbers — an ungated version would
have led with a 23-hour blackout that was a ship leaving a rectangle.

**Q2 — does STENA PROSPEROUS survive?** Yes. Genuine, 142.3 min, silence began mid-box at
−79.29, 29.27, nowhere near an edge. The competing-candidate problem on Menuett stands.

**Q3 — does `component_notes` carry vessel identity?** No. Dumped all 119 notes across 17 vessels:
**zero vessel names, zero MMSIs.** IMO and callsign are never read by `score.py`. Ten distinct
wordings, all measurements and stated gate reasons, e.g. *"on approach 19 km out, course 0 deg
against 15 deg toward the origin (15 deg off)"*. Everything in them derives from the same AIS the
card already cites.

**Open issues:** the handoff cites **D27/D31**, but the master plan I hold is v4 and its decision
log stops at **D22** — either there is a newer plan I have not been sent or those references are
wrong. Also, none of the 12 Sept findings have reached the docs yet: `06_JAIVEER_AIS` is still
labelled v2 and its Phase 9.0 table still calls Menuett *"the only case where every component
fires, including gap"*, which the measurement below disproves; Master Part 3.2 still says ~100 km
offshore when it is 170.

**Next:** Phase 8 — the injected-offender ablation curve. It needs nobody, it is a named
deliverable in Master Part 14, and it is the only legitimate way to settle the `trajectory` and
`type_prior` weight questions raised on the 12th.

---

## [2026-09-12 18:00] Phase 1 — the core scorer, end to end

**Done:** `score.py` exists and runs. Seven components, each returning `(score, applicable)`, with
the weighted sum renormalised over the applicable weights only — a component we could not measure
never silently drags a score toward zero. Grid-sampled proximity per D8. Applicability gating per
D9, **plus a new box-boundary gate**: a silence whose last report sits on the search boundary is a
vessel leaving the rectangle, not going dark. Closest approach walks the track at 60-second cadence
through the window using `position_at`, which refuses to interpolate across a silence longer than
30 minutes, so no position is ever invented. Funnel with `dropped_short_track`, exclusions with
stated reasons, and all four abstention triggers.

`geo.py` holds every distance, bearing and grid lookup in one place: haversine (never Euclidean),
compass bearing comparable with `cog`, wrap-safe angular difference, point-to-segment, and an
`OriginGrid` that samples `origin.json` with **row 0 = NORTH**. Sampling is nearest-cell rather
than bilinear — the cells are of order a kilometre over a 50-member ensemble, and smoothing between
two of them would imply precision the ensemble does not have. Outside the grid returns a measured
`0.0`, never `null`.

**Output now goes into the case bundle.** `run.py` was writing to `out/`, which is gitignored,
while `validate_case.py` reads `cases/<id>/` — so the PASS quoted in `PHASE1_JAIVEER.md` was
validating Akshat's committed fixture, not our output. Corrected.

**Files touched:** `pipeline/attribute/score.py` (new) · `pipeline/attribute/geo.py` (new) ·
`pipeline/attribute/tests.py` (63 assertions) · `pipeline/attribute/make_fake_case.py` (v4 meta:
`ais_source`, `case_type`, `gallery`, `db_clamp`, `discharge_class`; scene footprint sized like a
real Sentinel-1 IW swath) · `pipeline/attribute/CLAUDE.md` (v1 → v4)

**Run command:**
```bash
python pipeline/attribute/make_fake_case.py
python pipeline/attribute/score.py --case-dir pipeline/attribute/fixtures/case-gulf-fake \
       --parquet data/ais/gulf.parquet --ranking
python scripts/validate_case.py pipeline/attribute/fixtures/case-gulf-fake
```

**Result on real Galveston AIS:** funnel `987 → 897 → 17 → 0`, 15 dropped for under 5 reports.
Zero because it **abstains** — the top two are 1.1% apart, which on a patch of ocean with no actual
spill is the correct answer, and it means the refusal path is demonstrable on real data today.
Moved the origin to a quieter position and it produces a clean top-3 with two stated exclusions.
Validator `PASS`, **0 warnings**, on both paths.

**R10 closed.** Identical ranking on Linux/container and Windows/Python 3.11. Reproducibility was
the last unverified item in the Phase 1 risk register.

**Open issues — all raised with Akshat on the 12th, none fixed unilaterally:**

- **`trajectory` as specified could never fire.** Measured on the real fleet: **0.00 for 16 of 17
  vessels, median 126 degrees off.** It is geometry, not data — at closest approach the bearing to
  the origin is by construction perpendicular to your course, so a ±60 degree cone can never be
  satisfied. Fixed *where* it is measured (last report before closest approach at which the vessel
  was still outside `radius_90_km`), which is the same class of change as D9. **But corrected it
  scores 1.00 for 13 of 15**, because any vessel that ended up inside the cloud was by definition
  heading toward it. Near-tautological for 15% of the weight. Parity is the component that would
  actually discriminate, and it waits on Soum.
- **`type_prior` scored 1.00 for all 17 vessels.** An offshore lane is all tankers and cargo, so it
  changes no ranking. Only 5%, but it is doing nothing.
- **A vessel on the origin peak can rank second.** EVERGLADES at grid probability 0.98, 2.3 km out,
  ranked below AP REVELIN at 0.31 and 17 km, because proximity is 30% while trajectory and gap are
  30% between them. EVERGLADES was loitering *inside* the cloud at 3.4 kn all window — which is why
  `trajectory` is `null` for it, and arguably the most suspicious profile on the board.
- **`component_notes` extends contract §6.7.** Useful for the cards; needs Akshat's blessing or it
  comes out.
- **No weight has been touched.** Every one of the above could be "fixed" by nudging numbers until
  the answer looks right, which is what D21 exists to prevent. Weights are Phase 8's job.

**Next:** Phase 8, the injected-offender curve.

---

## [2026-09-12 11:00] Phase 0 — day guard, US fake origin, test suite, and the Menuett block

**Done:**

**0.0 — the blocking task. NOAA AIS density at Menuett: coverage is dense, hero case confirmed, no
replan needed.** Pulled 30 and 31 July 2024, box from 40 km to 260 km offshore. Median reporting
interval is **69 s at Menuett's position and stays 69–70 s out to 240 km** — identical to the
Galveston baseline of 70 s, no thinning at all. Correction for the doc: the position is **~170 km**
off the Florida coast, not the ~100 km Part 3.2 states.

**But Menuett is not a gap case.** The vessel broadcast **714 times inside Cerulean's own −8h/+6h
window — 14.0 hours of 14, no coverage hole at either end — longest silence 130 seconds.** The
window is fully covered, so this is a finding, not an inconclusive check. Master Part 3's claim that
Menuett is "the only case that exercises gap detection" does not hold in the free NOAA data.
Proposed instead: let Alaska carry the gap story (a dark vessel is the same argument in its
strongest form), and back it with the Phase 8 curve.

**A real bug found in the process.** Five of eleven under-way silences were vessels leaving the
search box and returning, resuming exactly on the boundary — one apparently dark for 23 hours. The
existing under-way gate does not catch these, because they *were* under way on both sides. Box-
boundary gate added in Phase 1.

**0.1 Branch pushed** — `jaiveer-phase2`, verified local and remote tips match.
**0.2 US-located fake origin** — `make_fake_case.py` writes a complete schema-valid bundle over
open water southeast of Galveston on 25 Jan 2023. Position chosen by measuring the real extract, so
~17 real vessels pass through the cloud during the window and 15 are genuinely under way; a fixture
over the anchorage would have let the `gap` and `slowdown` gating pass untested. The cloud is a
**4:1 streak, not a circle** — on this extract the r50 circle catches 8 vessels and grid sampling
catches 17, so the fixture actually exercises D8 rather than letting a circle-membership scorer
look correct.
**0.3 `tests.py`** — stdlib only, no new dependencies. Mutation-tested: ten deliberate bugs
introduced, ten caught, including one round where a test built its fixture from the constant it was
checking and therefore caught nothing.
**0.5 Parquet backup** — deliberately **not** done. NOAA is a permanent free archive and the ingest
commands are in this log, so recovery is a download and two commands. The code push was the backup
that mattered. Recorded as a judgement call, not an oversight.

**Files touched:** `pipeline/attribute/ingest.py` (day-continuity guard) ·
`pipeline/attribute/make_fake_case.py` (new) · `pipeline/attribute/fixtures/case-gulf-fake/` (new)
· `pipeline/attribute/tests.py` (new) · `.gitignore`

**Run command:**
```bash
python pipeline/attribute/tests.py
python pipeline/attribute/ingest.py --csv data/ais/AIS_2024_07_30.csv data/ais/AIS_2024_07_31.csv \
       --bbox -81.0 28.5 -78.7 31.6 --out data/ais/menuett_2day.parquet
python pipeline/attribute/tracks.py --parquet data/ais/menuett_2day.parquet
```

**Open issues:** blind evaluation does not hold for cases 1, 2, 4 and 5 — the Menuett check cannot
be run blind (finding the vessel *is* the check, and it sorts first by report count), and Master
Part 3.2 prints the MMSIs for cases 1 and 2 and the dark-vessel coordinates for 4 and 5 outright.
Raised with Akshat; better stated openly now than found by a panel in December.

**Next:** Phase 1, the core scorer.

---

## [2026-09-08 00:20] Phase 1 — AIS ingest + track reconstruction

**Done:** Stage 3 reads real NOAA AIS end to end. `ingest.py` streams a daily CSV through DuckDB
and applies the bbox + time filter during the scan, so an 800 MB file never enters memory — one
Galveston day comes out as an 11 MB Parquet (677,102 position reports, 987 distinct MMSIs).
`tracks.py` groups those into 972 per-vessel tracks with `position_at()`, `max_gap_minutes` and
`gap_overlapping()`, drops MMSIs under 5 points, and refuses to interpolate across any silence
longer than 30 min. `plot_tracks.py` draws a sample for eyeballing. Akshat's stub still passes the
validator, so the output seam is proven as well as the input.

**Files touched:** `pipeline/attribute/ingest.py` (new) · `pipeline/attribute/tracks.py` (new) ·
`pipeline/attribute/plot_tracks.py` (new) · `data/ais/gulf.parquet` (output, gitignored)

**Run command:**
```bash
python pipeline/attribute/ingest.py --csv data/ais/AIS_2023_01_25.csv \
       --bbox -95.5 28.0 -93.5 29.8 --out data/ais/gulf.parquet
python pipeline/attribute/tracks.py --parquet data/ais/gulf.parquet
python pipeline/attribute/plot_tracks.py --parquet data/ais/gulf.parquet
python pipeline/attribute/run.py --case case-000 --stub
python scripts/validate_case.py cases/case-000
```
Expected output: `677,102 position reports from 987 distinct MMSIs`, then `972 tracks with >= 5
points`, then a PNG in `pipeline/attribute/out/`, then `PASS acts=['detect', 'trace', 'attribute']`.

*(Correction, 12 Sept: that last PASS validated Akshat's committed fixture, not our output —
`run.py` writes to the gitignored `out/` while the validator reads `cases/<id>/`. Fixed in
`score.py`, which writes into the bundle.)*

`ingest.py --from-origin cases/case-000/origin.json` also works — derives bbox and window from an
origin cloud padded to 2× `radius_90_km` (the `plausible` cut), so the real origin swaps in with
no code change.

**Checkpoint artefact:** `pipeline/attribute/out/tracks_check.png` — 50 tracks sampled across
vessel types. They converge on Bolivar Roads at the Galveston Bay entrance, with lanes up the
Houston Ship Channel and out to open water. Smooth, no teleporting, so no lat/lon swap. Tankers
show tangled loops at the anchorages, which is vessels swinging at anchor, not a bug.

**Open issues:**
- **`type_prior` doesn't describe the Gulf.** 685 of 972 vessels land in `other`; 404 of those are
  tug/tow (AIS codes 31, 32, 52) — more than double the tanker count. Asking Akshat only for
  display labels so cards don't say "other" for a tug. NOT asking to reweight: I measured how many
  tugs there are, not how often tugs spill, and abundance is already counted via the funnel.
- **Half the fleet is parked.** 487 of 972 average under 0.5 kn all day. Of the 124 vessels with a
  30+ min AIS gap, 73 are parked boats whose transponder idled — so the `gap` component would be
  ~59% false positives as specified. `slowdown` has the same problem: undefined when a vessel's
  median SOG is ~0. Plan: gate both components on the vessel actually moving in the window, and
  state that rule openly rather than hiding it in an `if`.
- **15 vessels dropped silently** for having under 5 points. The drop is right (4 of 5 components
  would be blank) but the silence isn't. Plan: report the count under the funnel.
- The three CSVs I have are 25 Jan, 16 Feb, 28 Feb — three weeks apart, so they must NOT be
  ingested into one Parquet or every vessel gets a fake three-week gap. Real case needs consecutive
  days (incident ±2).
- Scoring against `cases/case-000/origin.json` will return zero of everything: that fake origin is
  over Ennore, India, Jan 2017, and my AIS is US 2023. Need a US-located fake origin before
  Phase 2 means anything.

**Next:** build the US fake origin, then Phase 2 scoring — the five weighted components against
it, funnel counts, and the exclusion.
