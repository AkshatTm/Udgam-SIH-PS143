# Jaiveer — update log

*Newest entry at the TOP. Copy the block from `TEMPLATE.md`, fill four lines, commit it with
your code in the same push. Two minutes after each phase — non-negotiable.*

**Why:** your AI has no memory between chats. This file is the memory. It means you can close a
chat, switch from Claude to ChatGPT, hand your work to someone else, or come back after sleeping,
and lose nothing.

**To resume from it:** *"Here are the master plan, my task document, and my update log. Read the
top entry and tell me exactly where I left off and what the next step is."*

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
