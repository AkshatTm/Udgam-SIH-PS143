# JAIVEER — Stage 3: AIS + Attribution
*Read with 00_MASTER_PLAN.md. You own attribution end to end. Your lane is fully self-contained by design: you build against a fake origin cloud and never wait for anyone. Your deadline is the 11th (internal round), not the 9th (HOD demo) — but your stubs and daily updates are how the team knows you're on track, so post every evening.*

## You produce
`pipeline/attribute/` · `vessels.geojson` + `suspects.json` (fake-origin versions by Tue, real by the event) · the funnel counts · at least one exclusion with a stated reason.

## You consume
`origin.json` (use case-000's fake one until the real US one exists — your code must not care which) · NOAA AIS (your download) · contracts in Master §4.

## Tools
Your Claude Pro + Codex. Post an end-of-day update in the group every day (nobody can see your screen — silence reads as risk). Append to `docs/updates/jaiveer.md` after each phase.

## AI split
AI writes 100% of the code. YOU judge: do the reconstructed tracks look like ship tracks when plotted (smooth lines along coasts/lanes, not teleporting zigzags)? Do the funnel numbers decrease sensibly? Does the top suspect's story make sense when you read its reasons?

---

## Phase 1 — Sun/Mon (~5 h) · ingest + tracks (case-independent)
1. Data: NOAA Marine Cadastre AIS — daily zipped CSVs at coast.noaa.gov/htdata/CMSP/AISDataHandler/ (no registration). Until the US case is picked, use ANY 2023 Gulf-of-Mexico-relevant days just to build the machinery; you will swap files later with zero code change.
2. `attribute/ingest.py`: stream-read the CSV (columns include MMSI, BaseDateTime, LAT, LON, SOG, COG, VesselName, VesselType), **filter to a bbox + time window on read** (never load a whole file into pandas), write Parquet to `data/ais/` (gitignored). Query layer with DuckDB or GeoPandas — your pick.
3. `attribute/tracks.py`: group by MMSI, sort by time → per-vessel track; linear interpolation `position_at(mmsi, t)`; per-vessel `max_gap_minutes` (largest silence between consecutive reports). Drop MMSIs with <5 points. Do NOT build identity resolution — MMSI as-is, known imperfection, one demo case.
4. **Stub-first:** commit `attribute/run.py --fake` writing schema-valid garbage `vessels.geojson` + `suspects.json`; run Akshat's validator.
**Checkpoint:** plot of ~50 reconstructed tracks over a coastline — they look like shipping.

## Phase 2 — Mon/Tue (~5 h) · scoring against the FAKE origin
Scoring per vessel, deterministic and explainable (weights are constants at the top of the file):
```
proximity   = origin-grid probability density at the vessel's closest-approach point,
              0 if it never enters the origin bounds during time_window        (w=0.40)
trajectory  = 1 if course within ±60° of bearing toward origin centroid
              around closest approach, else 0                                  (w=0.20)
slowdown    = 1 if SOG dropped >40% below that vessel's median inside window   (w=0.15)
gap         = 1 if an AIS gap ≥30 min overlaps time_window                     (w=0.15)
type_prior  = tanker/cargo 1.0 · fishing 0.4 · passenger 0.2 · other 0.5       (w=0.10)
score       = Σ w·component   →  rank descending, top 3 = suspects
```
**Funnel** (these four counts ARE requirement (c) on screen): `in_region` = distinct MMSIs in bbox · `in_window` = also inside time_window · `plausible` = closest approach < 2× radius_90_km · `scored` = 3.
**Exclusion:** among the plausible-but-not-top-3, pick the closest vessel whose trajectory component = 0 → excluded list with reason "heading away from origin throughout the window" (or gap-free equivalent). If `origin.abstain` is true → suspects empty, funnel still populated, note "attribution not possible at acceptable confidence".
`reasons`: 1–3 short human-readable strings per suspect, generated from whichever components fired. These go on judge-facing cards — plain language.
**Checkpoint:** run on fake origin + real AIS → valid files, funnel decreasing, plotted top-suspect track with closest-approach point marked.

## Phase 3 — Wed–event · the real thing
1. When Akshat confirms the US case: download the actual incident days (±2 days), rerun ingest. Everything downstream unchanged.
2. When the real US `origin.json` lands (event days): rerun scoring → real `vessels.geojson` (plausible-set tracks only, decimated to ≤500 points each — Harshita renders these) + real `suspects.json`. Run validator, hand to Akshat with the run command.
3. Read the top suspect's story yourself before shipping: if the #1 vessel is, say, a passenger ferry that never entered the 90% radius, the weights or a component are buggy — debug before it reaches a judge.

## Honesty constraints (binding — internals carry to December)
Vessel names/MMSIs on screen come only from the real AIS file. If the documented incident's vessel doesn't rank top-3, that is the result we show and discuss — we do not reweight to force it. "Leads, not verdicts" is the closing line for a reason.

## Escalate (45-min rule)
NOAA download dead/moved · the incident days' files missing the region · anything in origin.json that doesn't match the contract.

## Cut order if behind
Slowdown component (drop, reweight proportionally) → reasons strings (cards show numbers only) → NEVER cut: the funnel, one exclusion, the abstain path.

## Definition of done
Track-plot checkpoint posted · fake-origin run valid by Tue · real US suspects.json + vessels.geojson by freeze · exclusion present · daily updates posted every evening.
