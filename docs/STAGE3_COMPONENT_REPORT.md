# Stage 3 — AIS Attribution: Full Component Report

**Project:** NAAP · SIH 2026 · PS 26143 — oil spill detection, backtracking and vessel attribution
**Component:** Stage 3 (Attribute) — AIS ingest, track reconstruction, suspect scoring
**Owner:** Jaiveer
**Report date:** 2026-09-08
**Code state described:** `pipeline/attribute/{ingest.py, tracks.py, plot_tracks.py}`, uncommitted on branch `jaiveer` (§15)
**Phase covered:** **Phase 1 only.** Ingest and track reconstruction are built and run on real AIS. Scoring — the five weighted components, the funnel, the suspect cards, the exclusion — **is not written yet.** This report describes the half that exists and states plainly what does not.
**Every number in this report was read out of the output files or the code, not from memory.** Where a figure changed after a fix, both values appear with the reason.

---

## 0. One-page summary

**What this component does.** It answers *which ship did it*. Stage 2 hands over a patch of ocean and a time window — an origin cloud. Stage 3 finds every vessel that was inside that patch during that window, reconstructs each one's journey from raw transponder broadcasts, scores them on five deterministic signals, and produces a ranked shortlist plus at least one vessel explicitly ruled out with a stated reason. **No machine learning anywhere.** Every number on a suspect card can be traced to an arithmetic step, which is the point: we can tell a panel exactly why a vessel ranked where it did.

**What exists today.** The input half — everything up to but not including the score.

| File | What it does | State |
|---|---|---|
| `ingest.py` | streams an 800 MB NOAA daily CSV, applies a bbox + time filter during the scan, writes Parquet | **built, run on real data** |
| `tracks.py` | groups by MMSI into time-ordered journeys, gap measurement, guarded interpolation, contract-shaped GeoJSON features | **built, run on real data** |
| `plot_tracks.py` | the Phase 1 checkpoint picture | **built, run on real data** |
| *scoring* | five weighted components, funnel, suspect cards, exclusion, abstain | **not written** |

**Result on one Galveston day (real NOAA AIS, `AIS_2023_01_25.csv`):**

```
input                800 MB CSV, all US waters, one day
box                  lon -95.50 .. -93.50   lat 28.00 .. 29.80   (Houston Ship Channel approaches)
kept                 677,093 position reports          10.9 MB Parquet
distinct MMSIs       987
tracks (>= 5 pts)    972            dropped: 15 MMSIs with 1-4 reports
median track         563 points     longest 1,360     median reporting interval 71 s
median max-gap       9.0 min        p99 344 min       worst 996 min
output seam          stub -> validator PASS, acts=['detect','trace','attribute'], 0 warnings
runtime              ~2 min for the ingest, seconds for everything after
```

**How much of this is real.** The AIS is entirely real — real vessels, real MMSIs, real names, broadcast on 25 January 2023 and published by NOAA. **The box is not a case.** I chose Galveston because Phase 1 is case-independent and I needed water with enough traffic to prove the code. Nothing here is a claim about any spill. When Akshat picks the US case, the box stops being a flag I type and comes out of `origin.json` instead — no code changes (§3.4).

**Accuracy, stated honestly.** There is nothing to be accurate *about* yet: no scoring exists, so there is no ranking to be right or wrong. What Phase 1 can defend is that the extraction is faithful — the filter keeps what it claims to keep, the tracks are time-ordered and unbroken, the interpolation refuses to invent positions across long silences, and the reconstructed paths converge on the Galveston Bay entrance, which is where real traffic converges. **This is a data-plumbing claim, not an attribution claim.**

**The honest weakness, stated up front.** Stage 2 has a 20-assertion known-answer test suite written before any data existed. **Stage 3 has no test suite at all.** Verification so far is a synthetic-CSV harness and a set of one-off assertions I ran by hand (§8). That is the single largest gap in this component and it is where the next silent bug will live.

**Top three risks ahead.** (1) Scoring does not exist and the deadline is Friday — this is a schedule risk, not a technical one, and it dominates everything else. (2) Two of the five specified scoring components — `gap` and `slowdown` — misfire on port traffic in ways I have measured (§7.3); wiring them as written would put docked boats on suspect cards. (3) 13% of tracks are truncated by the box edge, so a vessel's journey may be cut off rather than ended (§14, R3).

Full detail follows. §7 is what the data actually looks like; §12 is every bug found; §14 is the risk register; §16 is what needs a decision.

---

## 1. Scope — what this component is and is not

### In scope
- Reading NOAA Marine Cadastre AIS at volume without loading it into memory.
- Filtering to a region and time window derived from an origin cloud.
- Reconstructing per-vessel journeys from scattered broadcasts.
- Measuring transponder silences and interpolating position, with a refusal rule.
- *(Phase 2, not built)* Scoring vessels on five deterministic components; the funnel counts; suspect cards with plain-language reasons; at least one exclusion; the abstain path.
- Writing `vessels.geojson` and `suspects.json`, and proving they validate.

### Explicitly out of scope (and why)

| Not built | Why |
|---|---|
| Machine learning of any kind | The brief forbids it and it would be wrong here. A weighted sum is explainable to a panel; a classifier is not. |
| MMSI identity resolution | MMSIs are sometimes reused, sometimes spoofed. One demo case; the brief says take MMSI as broadcast and treat the imperfection as known. Solving it is a research project. |
| Interpolation across long silences | Deliberate refusal. Inventing a position could put a fabricated point inside the origin cloud and rank a vessel on it. §3.3. |
| Vessel identity beyond AIS | No registry lookups, no ownership, no port records. Everything on screen comes from the one downloaded file. |
| Real-time / streaming AIS | Historical forensics only. The whole demo is precomputed. |
| Satellite AIS (open ocean) | NOAA Marine Cadastre is terrestrial-receiver coverage. Out past ~50 nm the data thins; our cases are coastal. |
| Barge cargo inference | AIS says a vessel is towing, not what it is towing. See §16, decision 1. |

### The seam
Stage 3 imports nobody's code and nobody imports Stage 3. It reads `cases/<id>/origin.json` and a local AIS file, and writes `out/{vessels.geojson, suspects.json}`. That is the entire interface, and it is why Stage 3 could start before Stage 2 produced anything real.

**One asymmetry worth naming:** Stage 2's input (`detections.geojson`) is small and lives in the repo. Stage 3's input is an 800 MB file per day that is gitignored and lives only on my laptop. Only the outputs travel. That is the Master §7 rule, and it means nobody else on the team can reproduce my numbers without downloading the same day first (§17).

---

## 2. Architecture and code map

```
pipeline/attribute/
├── CLAUDE.md         per-directory rules for any AI session opened here
├── ingest.py   9.9 KB  NOAA CSV -> bbox/time filter on read -> Parquet
├── tracks.py   8.2 KB  Parquet -> {mmsi: Track}; gaps, interpolation, GeoJSON features
├── plot_tracks.py 5.9 KB  Phase 1 checkpoint picture
├── run.py     11.8 KB  CLI + stub (Akshat's scaffold; the real scorer replaces its middle)
└── out/               vessels.geojson, suspects.json, tracks_check.png
```

### Data flow

```
data/ais/AIS_YYYY_MM_DD.csv   (800 MB, gitignored, my laptop only)
          │
          │   ── bbox + time WHERE applied DURING the scan (DuckDB) ──
          ▼
data/ais/<case>.parquet        (10.9 MB — the expensive step, paid once)
          │
          ▼
tracks.load_tracks()  ──  {mmsi: Track}  ── 972 objects
          │                    │
          │                    ├── position_at(t)         interpolation, guarded
          │                    ├── max_gap_minutes        the gap component
          │                    ├── gap_overlapping(t0,t1) the gap component, windowed
          │                    ├── median_sog()           the slowdown component
          │                    └── to_feature()           a vessels.geojson Feature
          │
          ├──→ plot_tracks.py ──→ out/tracks_check.png     (the eyeball check)
          │
          └──→ [SCORING — NOT WRITTEN] ──→ out/vessels.geojson
                          ▲                out/suspects.json
                          │
              cases/<id>/origin.json  (Stage 2)
```

### The design rule everything obeys
`ingest.py` knows about CSVs and nothing else. `tracks.py` knows about Parquet and nothing else. Neither knows what an origin cloud is. Only the scorer will. This is why swapping the fake origin for the real one changes no code in either file — the origin only ever reaches `ingest.py` as four numbers and two timestamps, through `--from-origin` (§3.4).

---

## 3. The method

### 3.1 Filtering on read — why this is the whole trick

A NOAA daily file is ~800 MB of text covering every US water: Alaska, Hawaii, both coasts, the Great Lakes, the Gulf. `pd.read_csv` on one builds the entire table in RAM first and then filters, which on this machine means several gigabytes for a result that is 10.9 MB. It is the documented laptop-killer (`docs/TRAPS.md` #12).

DuckDB inverts the order. It scans the file and applies the `WHERE` clause during the scan, so a broadcast off Maine is tested and discarded before it ever occupies memory. Peak memory is the size of the *result*, not the file.

```sql
SELECT ... FROM read_csv(<files>, header=true, union_by_name=true,
                         types={'MMSI':'VARCHAR','VesselName':'VARCHAR'})
WHERE LON BETWEEN ? AND ? AND LAT BETWEEN ? AND ?
  AND BaseDateTime >= ? AND BaseDateTime < ?
```

Measured: 677,093 rows survive out of the whole US day — **10.9 MB of Parquet from 800 MB of CSV.**

*Honest caveat:* I have not instrumented peak RSS. The claim "memory is the size of the result" is the documented behaviour of a streaming scan plus the observation that the machine did not swap; it is not a measurement. Worth doing before anyone repeats it to a judge.

### 3.2 Why Parquet, and why only once

The scan is the expensive step, and you would otherwise repay it every time you tweak a scoring weight. Parquet is columnar and binary: the filtered result reads back in well under a second with no parsing. One scan, then a week of instant iteration.

**MMSI is stored as VARCHAR, not an integer**, deliberately. It is an identifier, not a quantity — arithmetic on it is always a bug, and the contract (§7) specifies `"mmsi": "367123450"` as a string. Forcing the type at read time means the string never round-trips through an int.

### 3.3 Interpolation, and the refusal that matters most

> **A long transponder silence is evidence. It is not a hole to patch.**

`position_at(when)` linearly interpolates between the two bracketing reports — but only if the interval between them is **≤ 30 minutes**. Beyond that it returns `None`.

This is not conservatism for its own sake. If a vessel went dark for three hours and we drew a straight line through the gap, we would manufacture positions that never happened — and one of those fabricated points could land inside the origin cloud and score the vessel as a suspect. The system would then be accusing a ship on the strength of a line we drew ourselves. The refusal is the honest behaviour, and it is the same instinct as Stage 2's abstain flag.

The 30-minute ceiling is generous relative to the data: the **median reporting interval is 71 seconds** (p90 182 s), so the ceiling is roughly 25× a normal interval. It fires only on genuine silences.

### 3.4 The origin seam — one flag, two files, no code change

```
--bbox -95.5 28.0 -93.5 29.8                    Phase 1: a box I typed
--from-origin cases/case-000/origin.json        the fake origin
--from-origin cases/case-us-xxxx/origin.json    the real one, event week
```

`--from-origin` reads `bounds` and `time_window` out of the contract file and pads the box by **2 × `radius_90_km`**, converted to degrees at the box's own mid-latitude. That constant is not arbitrary: `plausible` in the funnel is defined as *closest approach < 2 × radius_90_km*, so filtering any tighter would discard vessels the funnel is supposed to count. The time window is padded by ±6 h (`--pad-hours`).

The code never asks whether an origin is fake or real. That is what makes the swap free.

### 3.5 Time convention
`BaseDateTime` is naive text in the CSV and is UTC by NOAA's definition. It is converted once, at read, with `AT TIME ZONE 'UTC'`, and stored as `TIMESTAMP WITH TIME ZONE`. `parse_ts()` raises on any naive datetime reaching the CLI. Nothing downstream ever sees a naive timestamp.

*One implementation note:* DuckDB's Python conversion of `TIMESTAMPTZ` requires `pytz`, which is not in `requirements.txt`. Rather than add a dependency two days before the freeze, timestamps cross into Python as **epoch seconds** and are rebuilt with `datetime.fromtimestamp(e, timezone.utc)`. Also several times faster than parsing ISO strings.

### 3.6 Coordinates
`[longitude, latitude]`, WGS84, everywhere, per the frozen convention. Measured extent of the extract is `lon -95.50000 .. -93.50002, lat 28.00008 .. 29.80000` — flush against the requested box on all four sides, which is itself a check that the filter is applied in the right axis order. A lat/lon swap would have produced an empty result, not a subtle one, because latitude 28-29 is not a valid longitude for this box.

---

## 4. Data source

| | |
|---|---|
| Source | NOAA / BOEM / USCG **Marine Cadastre AIS** |
| URL | `coast.noaa.gov/htdata/CMSP/AISDataHandler/<year>/` (302s to `chs.coast.noaa.gov`) |
| Granularity | one zipped CSV per day, all US waters |
| Volume | 110.4 GB for all of 2023 → ~300 MB zipped per day, ~800 MB unzipped |
| Registration | none — public, no account |
| Coverage | terrestrial AIS receivers; coastal, thins offshore |
| Columns used | `MMSI, BaseDateTime, LAT, LON, SOG, COG, Heading, VesselName, VesselType, Cargo` |

**A note on the download route.** The interactive **AccessAIS** map tool at `marinecadastre.gov/accessais` is *not* the right path. It requires drawing an area of interest and submitting an email order, and the result is a pre-filtered extract. Two problems: the queue is an external dependency at freeze time, and pre-filtering means our own bbox filter — the thing that produces the funnel's `in_region` count — is never exercised on real volume. The plain directory listing gives whole days immediately. This cost about an hour to discover (§12.1).

### Files on hand

| File | Size | Note |
|---|---|---|
| `AIS_2023_01_25.csv` | 797 MB | the one all figures in this report come from |
| `AIS_2023_02_16.csv` | 779 MB | |
| `AIS_2023_02_28.csv` | 834 MB | |

**These three are three weeks apart and must never be ingested into one Parquet.** Merged, `lag(ts)` would compute a three-week interval as a transponder gap for every vessel, and `max_gap_minutes` becomes meaningless. Consecutive days are required for the real case (incident ±2). See §14, R4.

### The AIS "not available" sentinels

AIS encodes *unknown* as a specific in-range value, not as a blank. These are real values in the file that must become NULL, or they silently become measurements. Counts from the 677k-row extract:

| Field | Sentinel | Means | Rows affected | Share |
|---|---|---|---|---|
| `SOG` | 102.3 | speed not available | 346 | 0.05% |
| `COG` | 360.0 | course not available | **66,838** | **9.9%** |
| `Heading` | 511 | gyro heading not available | 235,529 | 34.8% |

The `COG` one is the dangerous member of that set — see §12.2.

---

## 5. Ingest — from 800 MB to 10.9 MB

`ingest.py` produces one Parquet with this schema:

| Column | Type | Note |
|---|---|---|
| `mmsi` | VARCHAR | as broadcast, no identity resolution |
| `ts` | TIMESTAMP WITH TIME ZONE | UTC |
| `lon`, `lat` | DOUBLE | WGS84, `[lon, lat]` order |
| `sog` | DOUBLE | knots as NOAA publishes; 102.3 → NULL |
| `cog` | DOUBLE | degrees from north; 360.0 → NULL |
| `heading` | DOUBLE | 511 → NULL |
| `name` | VARCHAR | `VesselName`, blank → NULL |
| `type_code` | INTEGER | the raw AIS ship-type code, **kept deliberately** |
| `vessel_type` | VARCHAR | our five categories |
| `cargo_code` | INTEGER | the AIS `Cargo` field, added 8 Sept |

**Keeping `type_code` alongside `vessel_type` is the reason §7.2 exists.** The five-category mapping is lossy by construction — `ELSE 'other'` swallows everything the four rules miss. Had ingest written only the category and discarded the number, the fact that 404 of the 685 "other" vessels are tugs and tows would have been invisible without re-scanning 800 MB. **Store what you computed *from*, not only what you computed.** The same principle now applies to `cargo_code`.

### The category mapping

```sql
CASE
    WHEN VesselType BETWEEN 80 AND 89 THEN 'tanker'
    WHEN VesselType BETWEEN 70 AND 79 THEN 'cargo'
    WHEN VesselType = 30              THEN 'fishing'
    WHEN VesselType BETWEEN 60 AND 69 THEN 'passenger'
    ELSE 'other'
END
```

Ranges are ITU-R M.1371, as published in NOAA's own vessel-type lookup. `'other'` is **not a label in the data** — it is what our rule produces for anything it does not recognise. That distinction is the whole of §7.2.

### Deduplication
`SELECT DISTINCT ON (mmsi, ts)` drops exact duplicate reports — two AIS messages landing in the same second. Nine such rows in this extract (§12.3).

---

## 6. Track reconstruction

`load_tracks()` returns `{mmsi: Track}`. One DuckDB `GROUP BY mmsi` with `list(... ORDER BY ts)` aggregates does the grouping and sorting in the engine rather than in Python.

### The `MIN_POINTS = 5` rule
MMSIs with fewer than five reports **in the box** are dropped. Measured: 15 MMSIs, being 5 with one report, 3 with two, 4 with three, 3 with four.

You cannot build a path from one dot. More importantly, four of the five scoring components would be undefined for it — no heading, no speed history, no second point against which to measure a gap. It would score on proximity alone and could reach a suspect card on a single ping, which collapses the moment a panel asks "and where was it going?"

**But note what the rule is applied to.** The cutoff runs *after* the box filter. A vessel with one report inside the box almost certainly has hundreds just outside it — it clipped a corner and carried on. It is not a vessel that pinged once; it is a vessel that pinged once *in the rectangle I drew*. This is why `--from-origin` pads to 2 × `radius_90_km` (§3.4) and why the drop count must be reported rather than hidden (§16, decision 3).

### What a `Track` exposes

| Member | What it is | Used by |
|---|---|---|
| `ts, lon, lat, sog, cog` | parallel lists, ascending by time | everything |
| `gaps_minutes` | interval between each consecutive pair | the gap component |
| `max_gap_minutes` | the largest silence in the whole track | `vessels.geojson` property |
| `gap_overlapping(t0, t1)` | longest gap **overlapping a window** | the gap component, properly scoped |
| `position_at(when)` | interpolated `(lon, lat)`, or `None` | the proximity component |
| `median_sog()` | median speed, NULLs excluded | the slowdown component |
| `coordinates(max_points)` | decimated `[[lon,lat],…]` | `vessels.geojson` geometry |
| `to_feature()` | a contract-shaped GeoJSON Feature | `vessels.geojson` |

`gap_overlapping` exists because `max_gap_minutes` is the wrong question for scoring. A transponder that went dark a day before the spill is not interesting; one that went dark *during the window* is the single most incriminating pattern in the data. The component must be windowed, and the contract's `ais_gap_minutes` field is per-suspect for exactly that reason.

### Decimation
`coordinates()` caps a track at **500 points**, endpoints always kept, per contract §7. Measured: **522 of 972 tracks (54%) exceed 500 points** and will be decimated; the longest is 1,360. This is not a rare path — it is the common one, and it runs on every track Harshita renders.

---

## 7. What the data actually looks like

All figures from `data/ais/gulf.parquet`, one Galveston day.

### 7.1 Shape of the extract

```
rows                  677,093        distinct MMSIs   987
tracks (>= 5 points)  972            dropped          15
time span             2023-01-25T00:00:00Z .. 23:59:59Z
extent                lon -95.50000 .. -93.50002    lat 28.00008 .. 29.80000
Parquet               10.9 MB
```

**Integrity checks, all clean:** 0 null coordinates · 0 coordinates outside WGS84 range · 0 MMSIs of anything other than 9 digits · 7 rows with no vessel name · 7 with no vessel type.

**Points per track:** p0 5 · p10 175 · p25 362 · **p50 563** · p75 1,232 · p90 1,252 · p100 1,360.

**Reporting interval:** median **71 s** (p10 70 s, p90 182 s). Class A transponders report every 2–10 s while under way and every 3 min at anchor; a 71 s median across a mixed fleet is consistent with that.

**Transponder gaps:** median max-gap **9.0 min** · p75 15 · p90 36 · p95 81 · p99 344 · **max 996 min (16.6 h)**. **124 tracks (13%) have a gap ≥ 30 min.**

### 7.2 Fleet composition — and the hole in our categories

| Category | Vessels | Share |
|---|---|---|
| `other` | **685** | 70.5% |
| `tanker` | 156 | 16.0% |
| `cargo` | 64 | 6.6% |
| `passenger` | 45 | 4.6% |
| `fishing` | 22 | 2.3% |

Seven in ten vessels land in the leftover pile, so `type_prior` — the 10% component — is doing almost nothing to separate this fleet. Opening the pile on the raw codes we kept:

| AIS code | Meaning | Vessels |
|---|---|---|
| 31 | Towing | **362** |
| 37 | Pleasure craft | 100 |
| 90 | Other type | 56 |
| 57 | Spare, local vessel | 40 |
| 52 | Tug | **39** |
| 36 | Sailing | 39 |
| 33 | Dredging | 12 |
| 0 | Not available | 12 |
| 50 | Pilot vessel | 8 |
| 32 | Towing, >200 m or >25 m beam | **3** |
| — | 12 further codes | ~14 |

**404 vessels — 41.6% of the fleet — are tugs and tows.** More than double the tanker count, and currently scored 0.5, identical to the 139 sailing yachts and pleasure craft.

**What this proves and does not prove.** It proves the category structure does not describe the Gulf. It does **not** prove tugs deserve a higher prior: I counted how many are in the water, not how often they spill. There is also a double-counting trap — abundance already feeds the funnel, since more tugs in the water means more tugs in the plausible set, so raising the prior on top of that counts the same fact twice. Tank barges do carry ~65% of US coastwise refined product tonnage (CRS R43653), which is a real argument for a higher prior; but AIS code 31 means *towing something*, not *towing oil*, and Galveston has gravel barges and ship-assist tugs too. See §16, decision 1.

### 7.3 Motion — and why two scoring components misfire

**Half this fleet is not going anywhere.** 490 of 972 tracks (50%) average under 0.5 knots for the entire day: moored at docks, swinging at anchorages. Only 267 (27%) average ≥ 2 knots. This is normal for a box containing a major port, and it breaks two of the five specified components.

**The `gap` component** (15%) is meant to catch a vessel going dark while it discharges. Of the tracks with a gap ≥ 30 min:

| | Tracks |
|---|---|
| parked all day (avg < 0.5 kn) | **73** |
| genuinely under way (avg ≥ 2 kn) | 41 |

**64% of what this component catches is a docked boat whose transponder idled overnight.** The single worst gap in the dataset — 996 minutes — belongs to a vessel averaging 0.01 knots. It never moved.

**The `slowdown` component** (15%) is worse, and fails in two opposite directions at once:

- **It cannot fire for two-thirds of the fleet.** 638 of 972 tracks have a median SOG of exactly 0.0. "More than 40% below the median" is "below zero", which is unreachable. The component is silently inert for 66% of vessels.
- **Where it does fire, it mostly fires on normal behaviour.** 304 tracks (31%) trip it, and **77 of those match the pattern "median ≥ 4 kn, minimum exactly 0"** — under way, then stopped. That is arriving and mooring, the most ordinary thing a vessel does in a harbour.

A component that fires on a third of the fleet, largely for berthing, is not measuring suspicion.

**The fix is not reweighting.** It is defining *when a component is applicable*: gate `gap` on the vessel being under way on both sides of the silence, and scope `slowdown` to the closest approach to the origin rather than anywhere in the window, comparing against an *under-way* median that excludes the hours at rest. That is a statement about applicability, not a thumb on the scale — and it must be written down as a stated rule, not buried in an `if`. See §16, decision 2.

Worth noting the brief's cut order already lists `slowdown` as the first component to drop if we run short. These measurements say that was right on merit, not only on schedule.

---

## 8. Verification — what was actually checked, and what was not

**This is the section where Stage 3 is weakest, and it should be read as such.**

Stage 2 has 5 test suites and 20 known-answer assertions, written in Phase 1 before any data existed, and they caught a 10× units error on the first real fetch. **Stage 3 has no test suite.** What exists instead:

### 8.1 The synthetic-CSV harness
A generator produces a file with the **real NOAA header** and known contents — 70 vessels, half deliberately placed inside the Galveston box and half up near Boston, mixed vessel types, injected long gaps, and some vessels with fewer than 5 points. Running the pipeline against it checks that the filter keeps exactly the in-box vessels and that the `MIN_POINTS` rule drops exactly the short ones. It is also what the sentinel and dedupe fixes were regression-tested against (§12).

This harness is what let the code be written and debugged before the 800 MB download finished, and it is the closest thing here to Stage 2's Phase-1-first discipline. It is **not** in the repo yet — it lives in a scratch directory, which is a gap.

### 8.2 One-off assertions run by hand
Executed against the real extract, all passing:

| Check | Result |
|---|---|
| Interpolation across a **short** gap returns a point strictly between the bracketing positions | pass |
| Interpolation across a **long** (83 min) gap returns `None` | pass |
| A query before the track start returns `None` | pass |
| An exact-timestamp query returns that stored point, not an interpolation | pass |
| `gap_overlapping` returns the gap for an overlapping window and 0.0 for a distant one | pass |
| `to_feature()` produces contract-shaped output; coordinates are `[lon, lat]` in range | pass |
| Decimation caps a 2,900-point track at exactly 500 | pass |
| Filter keeps only in-box vessels on the synthetic file | pass |
| `--from-origin` against `case-000` produces a correctly-padded India box and exits cleanly on 0 rows | pass |
| A CSV with no `Cargo` column degrades gracefully rather than erroring | pass |

### 8.3 The eyeball check — the Phase 1 checkpoint
50 tracks, sampled evenly across all five vessel types, plotted (`out/tracks_check.png`). What it shows: smooth lines converging on a single point near **−94.72, 29.33**, which is Bolivar Roads at the Galveston Bay entrance, with one lane running north-west up the Houston Ship Channel and another south-east to open water. Tankers show tangled loops at the anchorages — vessels swinging at anchor, which is real behaviour.

**Why this counts as evidence:** a latitude/longitude swap, a mis-sorted track, or an MMSI shared by two vessels all produce visible scrambling. None is present. This is a weak test in the sense that it cannot be automated, and the strongest test this component currently has.

*Note on the plot itself:* the first version drew the 50 **longest** tracks, and every one came out `other` — because the longest-reporting vessels in a ship channel are tugs and pilot boats. A one-colour picture of a five-colour fleet. Now round-robins across types.

### 8.4 The output seam
```
python pipeline/attribute/run.py --case case-000 --stub
python scripts/validate_case.py cases/case-000
→ funnel 412 -> 63 -> 12 -> 3, 2 exclusion(s)
→ PASS  acts=['detect','trace','attribute']  (0 warning(s))
```
Those funnel numbers and the vessel `FAKE ATLAS` are **invented by the stub** — no AIS is involved. What it proves is the *shape* of the output slot: coordinate order, timestamp format, monotonic funnel, every suspect having a track, at least one exclusion carrying a reason, and the abstain rule. The real scorer will drop into a mould already proven to fit, and Harshita's map can already read it.

### 8.5 What has never been tested
Stated plainly, because it is where the next bug lives:

- **Any scoring at all.** It does not exist.
- **A real `origin.json` from Stage 2** — `--from-origin` has only run against `case-000`'s fixture.
- **`abstain: true`** on anything other than the stub.
- **Negative-longitude arithmetic in scoring** — ingest handles it (the whole Galveston box is negative), but bearing and distance maths is unwritten.
- **Multi-day ingest** — every run so far is a single CSV.
- **Cross-platform reproduction.** Stage 2 verified identical output on Linux/3.10 and Windows/3.11. Stage 3 has run on **one machine, one Python**. Unverified.
- **Peak memory** — never instrumented (§3.1).

---

## 9. Test data — every input this component has run against

### 9.1 `AIS_2023_01_25.csv` — real NOAA AIS
797 MB, one day, all US waters. Real vessels, real MMSIs, real names. Full statistics in §7. **Chosen, not given:** Galveston is not a case, it is dense traffic that makes errors visible. Everything derived from it is a statement about that box on that day.

### 9.2 The synthetic NOAA-format CSV
6,375 rows, 70 vessels, real header, known contents (§8.1). Deliberately includes: vessels far outside the box, vessels below `MIN_POINTS`, injected 45–180 min gaps, all five vessel-type categories, and an empty `Cargo` column.

### 9.3 `cases/case-000/origin.json` — the contract fixture
Used only through `--from-origin`. Bounds 80.34–80.94 E, 13.16–13.76 N; `radius_90_km` 11.8; window 2017-01-28T04:14Z → 16:14Z; `abstain` false.

**This fixture cannot be scored against with US AIS**, and the failure is silent-looking: the box is over Ennore, India, in January 2017, and the AIS is US 2023, so every funnel count comes back zero. That reads as broken code and is not. A US-located fake origin is required before Phase 2 can be tested at all (§16, decision 4). Verified: `--from-origin case-000` against the Galveston CSV correctly derives a padded India box and exits with `0 rows kept`.

### 9.4 A CSV with the `Cargo` column removed
Forged by deleting the column, to confirm `has_cargo_column()` detects its absence and degrades to a null `cargo_code` rather than erroring. Correct.

---

## 10. Results — the Galveston run in full

```bash
python pipeline/attribute/ingest.py --csv data/ais/AIS_2023_01_25.csv \
       --bbox -95.5 28.0 -93.5 29.8 --out data/ais/gulf.parquet
python pipeline/attribute/tracks.py --parquet data/ais/gulf.parquet
python pipeline/attribute/plot_tracks.py --parquet data/ais/gulf.parquet
```

### `gulf.parquet` — 10.9 MB
```
rows              677,093        distinct MMSIs   987
span              2023-01-25T00:00:00Z .. 2023-01-25T23:59:59Z
extent            lon -95.50000 .. -93.50002   lat 28.00008 .. 29.80000
compression       800 MB CSV -> 10.9 MB Parquet  (~73x)
```

### Tracks
```
tracks            972            dropped 15 (1-4 reports each)
points/track      min 5   median 563   max 1,360
report interval   median 71 s
max gap           median 9.0 min   p99 344 min   worst 996 min
named             972 of 972 carry a VesselName
over 500 points   522 (54%) — decimation active on the majority
edge-touching     131 (13%) — journeys truncated by the box, not ended
```

### Measured properties

| Quantity | Value | How measured |
|---|---|---|
| Filter selectivity | 677,093 of a full US day | row count |
| Distinct vessels | 987 → 972 with usable tracks | `count(DISTINCT mmsi)`, then `HAVING count(*) >= 5` |
| Parked all day (avg < 0.5 kn) | **490 (50%)** | per-track mean SOG |
| Under way (avg ≥ 2 kn) | 267 (27%) | same |
| Median SOG exactly 0 | 638 (66%) | per-track median |
| Tug/tow (codes 31, 32, 52) | **404 (41.6%)** | raw `type_code` |
| Tracks with gap ≥ 30 min | 124 (13%) — 73 parked, 41 under way | `lag(ts)` |
| Tracks touching a box edge | 131 (13%) | per-track bbox vs the requested box |
| Duplicate (mmsi, ts) pairs | 9 → 0 after dedupe | `GROUP BY mmsi, ts HAVING count(*) > 1` |
| COG sentinel rows | 66,838 (9.9%) → NULL | `cog = 360` |

### Does the picture make sense?
Yes, and this is the physical sanity check. The reconstructed tracks converge on Bolivar Roads at the Galveston Bay entrance and split into the Houston Ship Channel and the open Gulf. That is where real traffic in this box goes. If a render ever shows tracks converging somewhere with no harbour, or crossing land, something is flipped.

### Validation
```
python scripts/validate_case.py cases/case-000
→ PASS  acts=['detect','trace','attribute']  (0 warning(s))
```
Against the stub's invented output, not against real scoring (§8.4).

---

## 11. How reliable is this, honestly

### What can be defended
1. **The extraction is faithful.** The kept extent is flush against all four requested edges; zero coordinates fall outside WGS84 range; every MMSI is exactly 9 digits; no nulls in position.
2. **The tracks are well-formed.** Time-ordered by construction (sorted in the engine), no duplicate timestamps after dedupe, and a median reporting interval of 71 s that matches what Class A transponders actually do.
3. **The interpolation refuses rather than invents**, with a 30-minute ceiling that is ~25× the median reporting interval, so it fires only on real silences.
4. **The output slot is proven** by the stub against the validator.
5. **The reconstruction is physically corroborated** — tracks converge on a real harbour entrance.
6. **The three AIS sentinels are now handled**, including the COG one that would have fed 9.9% of rows into the trajectory component as "due north" (§12.2).

### What cannot be claimed, and will not
- **There is no attribution accuracy figure, because there is no attribution.** Scoring is unwritten. Any statement about ranking quality today would be fabricated.
- **No ground truth exists for these vessels.** Nobody has told us which ship spilled anything on 25 January 2023 off Galveston, because as far as we know nothing did. This box is a test fixture.
- **The fleet statistics are about Galveston, not about US waters.** It fronts the busiest petrochemical complex in the country, so 41.6% tug-and-tow is likely near the top of the realistic range. Whichever case Akshat picks will have its own mix and every figure in §7 must be recomputed on it.
- **Vessel type is self-reported.** AIS ship type is what the vessel broadcasts about itself; 12 vessels here broadcast code 0, "not available". We take it as given, per the brief.
- **Peak memory is asserted, not measured** (§3.1).
- **This component has run on one machine only.** Stage 2 verified cross-platform reproduction to the last decimal; Stage 3 has not.

### The right sentence for the demo
> *"We do not search the ocean for a ship. We take the origin cloud, pull every transponder broadcast inside it from the public NOAA archive, rebuild each vessel's journey, and score them on five signals we can each explain. When a transponder went dark we say so rather than drawing a line through the silence — the silence is the evidence."*

---

## 12. Every bug found, and how it was caught

### 12.1 The wrong download route — an hour, and a near-miss on empty water
The setup doc points at the AccessAIS map tool. Drawing an area of interest there produced an order of **461,642 sq mi over three days estimated at `<0.01 GB`** — which is not a small extract, it is *almost no vessels*. The box had been drawn in open Atlantic east of the coast, where the traffic isn't.

Had that order been submitted, the entire pipeline would have been built and "verified" against a few hundred position reports, and it would have looked like it worked. **Caught by reading the size estimate rather than the map.** Resolved by abandoning AccessAIS for the plain directory listing (§4) — whole days, no queue, and our own filter gets exercised on real volume.

### 12.2 Three AIS "not available" sentinels read as real measurements ★ the big one
AIS encodes *unknown* as an in-range value. All three were being ingested as data:

| Field | Sentinel | Rows | What it became |
|---|---|---|---|
| `COG` | 360.0 | **66,838 (9.9%)** | "course unknown" read as **course due north** |
| `Heading` | 511 | 235,529 (34.8%) | same, for gyro heading |
| `SOG` | 102.3 | 346 | a vessel doing 102 knots |

**Why COG is the dangerous one.** The `trajectory` component — 20% of the score, the second-heaviest — asks whether a vessel's course is within ±60° of the bearing to the origin centroid. Feeding it 66,838 rows of fabricated northward course would have biased that component systematically, in favour of any origin that happens to sit north of the traffic, and **nothing would have crashed**. One in ten rows is enough to move a ranking.

The SOG one is smaller but measurable: 15 vessels had their maximum speed reported as 102.3 knots, and one vessel had 22% of its reports as sentinel — close enough to half that its median could have flipped to 102.3, at which point the slowdown test would fire on every single reading.

**How it was caught.** By auditing the extract for sentinel values while compiling this report — not by a test, because there is no test suite. Had scoring been written first, this would have shipped.

**Fix:** all three are `CASE WHEN … THEN NULL` in the ingest query. `median_sog()` already excludes NULLs. Regression-tested on the synthetic CSV.

### 12.3 Duplicate `(mmsi, timestamp)` reports — a latent divide-by-zero
Nine rows across 8 MMSIs carry an exact duplicate `(mmsi, ts)` — two AIS messages landing in the same second. That puts a **zero-length interval** inside a track, and `position_at` divides by the interval to get its interpolation fraction.

Probed directly: the bug is currently **unreachable**, because `bisect_left` returns the leftmost index and so never selects the duplicated pair as its bracket. But that safety is an accident of one library's tie-breaking, not a property of the code. Fixed both ways — `DISTINCT ON (mmsi, ts)` in the ingest, and an explicit zero-span guard in `position_at` that returns the stored position rather than dividing.

### 12.4 DuckDB's timestamp conversion wanted an undeclared dependency
Reading `TIMESTAMP WITH TIME ZONE` back into Python raised `ModuleNotFoundError: pytz` — a package not in `requirements.txt`, on the day dependencies freeze. Rather than add one, timestamps now cross as epoch seconds and are rebuilt with `datetime.fromtimestamp(e, timezone.utc)`. Faster too. **Caught by the synthetic-CSV harness before the real data had finished downloading**, which is the one place Phase-1-first discipline paid off here.

### 12.5 The checkpoint plot was a one-colour picture of a five-colour fleet
`plot_tracks.py` drew the 50 **longest** tracks. In a ship channel the longest-reporting vessels are tugs and pilot boats, so every line came out `other` and the legend had one entry. Not a data bug — a bug in what the picture claims to show, which for a component whose main verification is visual is not cosmetic. Now round-robins across vessel types.

### 12.6 Packages installed outside the venv
First run of all three scripts failed with `ModuleNotFoundError: duckdb` despite `(venv)` in the prompt. `python -m pip install` rather than bare `pip` fixes it by guaranteeing the interpreter and the installer match. Worth one line in the setup doc, since it will happen to someone else.

### Swept and confirmed clean
No naive datetimes reach any code path · no bare `except` swallowing errors · MMSI never round-trips through an integer · coordinates are `[lon, lat]` at every boundary · `data/` is gitignored and no AIS has been committed.

---

## 13. Limitations — what this component does not do

| Limitation | Consequence | Why it stands |
|---|---|---|
| **No MMSI identity resolution** | A reused or spoofed MMSI merges two vessels into one track | Brief's explicit instruction. One demo case; the failure mode is visible as a teleporting track, which the checkpoint plot would show. |
| **No interpolation past 30 min** | A vessel's position is unknown across long silences | Deliberate. Inventing it could manufacture a suspect. |
| **Terrestrial AIS only** | Coverage thins offshore | It is the free data that exists. Our cases are coastal. |
| **Vessel type is self-reported** | Wrong or absent types (12 vessels broadcast code 0) | Correcting it would need a registry we do not have. |
| **`type_prior` has five categories that do not fit the Gulf** | 70% of vessels in one bucket; the component barely discriminates | Measured, §7.2. Frozen contract; raised as a decision rather than patched. |
| **`gap` and `slowdown` misfire on port traffic** | 64% of gap hits are docked boats; slowdown inert for 66% of the fleet | Measured, §7.3. Fix is applicability gating, §16 decision 2. |
| **Box-edge truncation** | 13% of tracks end at the box, not at the vessel's actual destination | Mitigated by the 2×`radius_90_km` pad; not eliminated. §14 R3. |
| **Single day per Parquet** | Multi-day cases need consecutive files | Non-consecutive days would fabricate gaps. §14 R4. |
| **No cargo inference** | Cannot tell an oil barge from a gravel barge | AIS type says *towing*, not *towing what*. `cargo_code` now kept to test whether the field helps. |
| **One machine, one Python** | Reproducibility unverified | Should be fixed before freeze; costs one run on another laptop. |
| **No test suite** | Regressions will be silent | The real gap. §16 decision 5. |

---

## 14. Risk register — what I expect to go wrong next

Ordered by expected damage. "Silent" means a plausible wrong answer rather than an error.

### R1 — Scoring does not exist and the deadline is Friday · **CRITICAL · loud**
Phase 1 is done; Phase 2 has not started; the internal round is the 11th. Everything a judge actually sees — the funnel, the three suspect cards, the reasons, the exclusion — is unwritten. This dominates every other risk in this register.
**Mitigation:** start against a US fake origin immediately (§16, decision 4) rather than waiting for Akshat's case. The cut order (`slowdown` first, then reasons strings; never the funnel, the exclusion or the abstain path) exists for exactly this and should be invoked early rather than late.

### R2 — `gap` and `slowdown` wired as specified · **HIGH · silent**
Measured in §7.3: 73 of 114 gap hits are parked vessels, and `slowdown` cannot fire for 66% of the fleet while firing on 77 vessels that simply moored. Implementing the brief literally puts docked boats on suspect cards with a plausible-looking score.
**Fix:** applicability gating (§16, decision 2). ~1 h.

### R3 — Box-edge truncation cuts journeys short · **MEDIUM · silent**
**131 tracks (13%) touch a box edge.** For those, the first or last stored position is where the vessel left my rectangle, not where it went. Closest-approach and trajectory are both computed from a truncated path, and neither raises anything. Directly analogous to Stage 2's R1, where particles pin to the edge of the downloaded field.
**Mitigation in place:** `--from-origin` pads to 2 × `radius_90_km`. **Not sufficient on its own** — a vessel transiting fast still exits. Worth a warning when a vessel's closest approach occurs within one reporting interval of the box edge.

### R4 — Non-consecutive days merged into one Parquet · **MEDIUM · silent**
The three files on hand are 25 Jan, 16 Feb, 28 Feb. Ingested together, `lag(ts)` computes a three-week interval as a transponder gap for every vessel, `max_gap_minutes` becomes meaningless, and the `gap` component fires on the entire fleet.
**Mitigation:** one day per Parquet until the real case; then download consecutive days (incident ±2). Worth a hard check in `ingest.py` that refuses inputs more than ~2 days apart.

### R5 — First contact with a real `origin.json` · **MEDIUM · partly loud**
`--from-origin` has only run against `case-000`'s fixture, which is in the eastern hemisphere. The real origin will be at negative longitude with different radii and a different window shape. Untested paths: a very large `radius_90_km` producing an enormous box, `abstain: true` arriving from Stage 2, and a window that falls outside the downloaded day.

### R6 — The origin cloud is a streak and my scoring assumes a circle · **HIGH · silent · flagged by Anushka**
Stage 2 measured its real origin cloud at aspect **4.38 : 1**, with **44.7% of the high-probability mass falling outside the r50 circle**. My scoring, as specified, uses `dist <= radius_50_km`. That will name vessels sitting in near-empty water inside the circle and exclude vessels sitting in the bright streak just outside it.
**Fix, and it is small because the scorer is unwritten:** sample the 120×120 probability grid at the vessel's position instead of testing circle membership. The grid, its bounds and its orientation are all already in `origin.json`, and `values` is row-major with **row 0 = NORTH**. This is a *method* change, not a bug fix, and doing it now costs nothing because there is nothing to rewrite.

### R7 — No test suite · **MEDIUM · silent, cumulative**
Every verification in §8 is a one-off I ran by hand. Nothing re-runs. The sentinel bug (§12.2) survived until a manual audit, and it would have shipped had scoring been written first.
**Mitigation:** the synthetic-CSV harness already exists and produces known answers — turning it into a committed `tests.py` with assertions is perhaps an hour, and it is the highest-leverage hour available if Phase 2 lands early.

### R8 — Raw AIS lives on one laptop · **MEDIUM · total if it fires**
Three files, 2.4 GB, gitignored by design (Master §7). If this machine dies, the outputs are gone and the download is hours. Mitigated only by the fact that the Parquet is 10.9 MB and could be backed up trivially. **Not currently backed up.**

### R9 — Every figure in this report is Galveston-specific · **MEDIUM · not a defect**
The fleet mix, the parked fraction, the gap distribution — all are properties of one box on one day at the busiest petrochemical port in the US. They will be different on the real case, and the §7.3 conclusions must be recomputed there before they are quoted. Stated so nobody lifts a number onto a slide labelled with the real case.

### R10 — Reproducibility unverified · **LOW-MEDIUM**
One machine, one Python. Stage 2 verified identical output across Linux/3.10 and Windows/3.11. Costs one run to close.

### R11 — The `Cargo` field may be empty · **LOW**
Added to `ingest.py` to test whether petroleum-carrying tugs can be distinguished. For towing vessels this field is frequently blank; if it is, the answer is simply that AIS cannot separate an oil barge from a gravel barge, and that is a limitation to state rather than a gap to fill.

### R12 — Dependency drift · **LOW**
Stage 3 needs `duckdb`, `pyarrow`, `pandas`, `matplotlib`, `numpy` — all pinned in `requirements.txt`. Deliberately **not** installed: `rasterio`, `opencv-python`, `scikit-image`, `earthengine-api`, which belong to other stages and are slow to build on Windows. `geopandas` and `shapely` are in the setup doc but unused; DuckDB covers the spatial filtering.

---

## 15. Repository state

```
branch          jaiveer  (created; push not confirmed at time of writing)
new files       pipeline/attribute/ingest.py        9.9 KB
                pipeline/attribute/tracks.py        8.2 KB
                pipeline/attribute/plot_tracks.py   5.9 KB
                docs/updates/jaiveer.md             Phase 1 entry
                docs/PHASE1_JAIVEER.md              plain-language summary
                docs/img/tracks_check.png           checkpoint plot
                docs/STAGE3_COMPONENT_REPORT.md     this file
untracked       data/ais/*.csv, *.parquet           gitignored by design
```

**All of this is uncommitted or unpushed.** As far as the team can see, Stage 3 has not started. The checkpoint plot has been produced but not posted in the group, and the plan makes posting it the definition of the phase being done — the same process drift Anushka names in her §16, and worth fixing in the same five minutes.

---

## 16. Decisions needed

| # | Decision | Owner | Cost | If we do nothing |
|---|---|---|---|---|
| 1 | Display labels for tug/tow on suspect cards | Akshat (contracts) | ~10 min | 404 vessels display as "other" |
| 2 | Applicability gating for `gap` and `slowdown` | me | ~1 h | Docked boats reach suspect cards |
| 3 | Report the count of vessels dropped for too few reports | me | 2 lines | A hidden assumption sits under the funnel |
| 4 | A US-located fake origin for Phase 2 testing | me, needs Akshat's nod | ~30 min | Phase 2 cannot be tested at all |
| 5 | Turn the synthetic-CSV harness into a committed test suite | me | ~1 h | Regressions stay silent |
| 6 | Score against the probability grid, not the r50 circle | me, raised by Anushka | ~1 h | Suspect ranking is geometrically wrong |

**On decision 1.** Two asks, deliberately separate. *Ask A:* add `tug` and `tow` as **display labels only**, `type_prior` untouched, nothing reranks. Safe, and it stops a card saying "other" for a visibly-a-tug vessel. *Ask B:* whether petroleum-carrying tugs should take the tanker prior of 1.0 — a real argument (tank barges carry ~65% of US coastwise refined product, CRS R43653) that I cannot yet connect to my 404, because AIS code 31 means *towing*, not *towing oil*. **Ask A stands regardless; Ask B only if the data supports it.** Note that if it ever does, the correct form is not a new invented number but *an existing category that was mis-assigned* — which survives being asked "why 0.7?"

**On decision 2.** Not a reweighting. Gate `gap` on the vessel being under way on both sides of the silence; scope `slowdown` to the closest approach and compare against an under-way median. Both must be **stated rules** in the code and on the limitations slide, not quiet conditionals.

**On decision 4, and it is the blocker.** `cases/case-000/origin.json` is over Ennore, India, in January 2017. My AIS is US, 2023. Scoring against it returns zero of everything — every funnel count zero, no suspects — which looks exactly like broken code and is not. Until a US-located fake origin exists, **Phase 2 cannot be tested at all.** This is the single thing standing between now and starting the scorer.

### The one insight behind three of these
The five `type_prior` categories, the `gap` rule and the `slowdown` rule were all specified before anyone had looked at real AIS. They are reasonable a-priori choices and they are measurably wrong about port traffic — not because anyone erred, but because a specification written against an imagined fleet meets a real one for the first time on contact. Anushka reached the same conclusion from the other side: `case-000` taught a *shape* it was never meant to teach, and three stages built against its values. **The rule worth carrying into Wednesday: the first time any stage sees real data, re-check the assumptions its stub baked in.**

---

## 17. Reproducing everything in this report

```bash
# 1. get the day — 800 MB, no account needed
#    https://coast.noaa.gov/htdata/CMSP/AISDataHandler/2023/AIS_2023_01_25.zip
#    unzip into data/ais/   (gitignored — raw AIS never leaves the laptop)

# 2. the ingest — the expensive step, ~2 min, paid once
python pipeline/attribute/ingest.py --csv data/ais/AIS_2023_01_25.csv \
       --bbox -95.5 28.0 -93.5 29.8 --out data/ais/gulf.parquet

# 3. tracks and the checkpoint picture — seconds
python pipeline/attribute/tracks.py      --parquet data/ais/gulf.parquet
python pipeline/attribute/plot_tracks.py --parquet data/ais/gulf.parquet

# 4. the output seam
python pipeline/attribute/run.py  --case case-000 --stub
python scripts/validate_case.py   cases/case-000

# the origin-driven path (Phase 2), same command, no code change:
python pipeline/attribute/ingest.py --csv data/ais/AIS_2023_01_25.csv \
       --from-origin cases/case-000/origin.json --out data/ais/case.parquet
```

**Nobody else on the team can run step 2 without step 1**, because the input is gitignored and 800 MB. That is the Master §7 rule working as intended, but it means my figures are verifiable only by someone willing to download the same day.

**Environment:** Python 3.11, `duckdb==1.5.5`, `pyarrow==25.0.1`, `pandas==3.0.5`, `matplotlib==3.11.1`, `numpy==2.4.6` — all pinned in `requirements.txt`. No GPU, no network after the download, no GEE. Install with `python -m pip install`, not bare `pip` (§12.6).

**Key CLI flags:** `--csv` (one or more) · `--out` · `--bbox W S E N` **or** `--from-origin <origin.json>` (exactly one) · `--start`/`--end` (UTC, trailing `Z`) · `--pad-hours` (6).

---

## 18. Definition of done — status

| Requirement (`05_JAIVEER_AIS.md`) | Status |
|---|---|
| **Phase 1** — ingest, tracks, `position_at`, `max_gap_minutes`, drop <5 | ✅ built and run on real NOAA AIS |
| Stub-first: schema-valid output through the validator | ✅ `PASS`, 0 warnings |
| Track-plot checkpoint | ⬜ **produced, not posted in the group** |
| **Phase 2** — scoring against the fake origin, funnel decreasing | ⬜ **not started** |
| Fake-origin run valid by Tuesday | ⬜ **missed** — today is Tuesday |
| **Phase 3** — real US suspects + vessels by freeze | ⬜ blocked on the case being picked |
| Exclusion present | ⬜ not started |
| Daily updates posted | ⬜ log written, not pushed |

### The three things blocking Phase 2 — two of them mine
1. **No US-located fake origin.** Scoring against `case-000` returns zero of everything. Mine, ~30 min, and it is the actual blocker.
2. **The US case is unpicked**, so I cannot download the right days. Akshat's.
3. **`gap` and `slowdown` need applicability gating** before they are wired, or they will need rewiring after. Mine, ~1 h.

None of these blocks *starting*. The scorer can be written against a US fake origin today and pointed at the real one when it lands — which is the whole point of the seam.

---

## Appendix A — schemas as actually written

### `data/ais/<case>.parquet` — internal, not a contract file
```
mmsi         VARCHAR                    as broadcast, 9 digits, no identity resolution
ts           TIMESTAMP WITH TIME ZONE   UTC
lon, lat     DOUBLE                     WGS84, [lon, lat] order
sog          DOUBLE                     knots; 102.3 sentinel -> NULL
cog          DOUBLE                     degrees from north; 360.0 sentinel -> NULL
heading      DOUBLE                     511 sentinel -> NULL
name         VARCHAR                    VesselName; blank -> NULL
type_code    INTEGER                    raw AIS ship-type code — kept deliberately
vessel_type  VARCHAR                    tanker | cargo | fishing | passenger | other
cargo_code   INTEGER                    raw AIS Cargo field
```

### `vessels.geojson` — contract §7, produced by `Track.to_feature()`
```jsonc
{ "type": "Feature",
  "geometry": { "type": "LineString", "coordinates": [[-94.35433, 28.97789], "..."] },
  "properties": { "mmsi": "367123450", "name": "EXAMPLE STAR", "vessel_type": "tanker",
                  "n_points": 214, "max_gap_minutes": 85 } }
```
Coordinates are `[lon, lat]` at 5 decimal places (~1 m), decimated to ≤ 500 points with endpoints preserved. `n_points` is the **undecimated** count, so it reports the real density of the track rather than the render budget.

### `suspects.json` — contract §8, **not yet produced by real scoring**
```jsonc
{ "funnel": { "in_region": 412, "in_window": 63, "plausible": 12, "scored": 3 },
  "suspects": [ { "mmsi": "…", "name": "…", "vessel_type": "tanker", "score": 0.82,
                  "closest_km": 3.1, "closest_time": "…Z", "heading_consistent": true,
                  "ais_gap_minutes": 85, "reasons": ["…"] } ],
  "excluded":  [ { "mmsi": "…", "name": "…", "closest_km": 6.4,
                   "reason": "heading away from origin throughout the window" } ] }
```
Funnel counts must decrease monotonically; `scored == len(suspects)`; suspects sorted by descending score; at least one exclusion with a non-empty reason; `origin.abstain == true` forces `suspects` empty.

---

## Appendix B — Glossary

**AIS** — Automatic Identification System; vessels broadcast position, speed and course over VHF every few seconds to minutes. **MMSI** — the 9-digit identifier in each broadcast; imperfect, sometimes reused or spoofed, taken as-is here. **SOG / COG** — speed and course over ground; both carry "not available" sentinels (102.3 and 360.0). **Marine Cadastre** — the NOAA/BOEM/USCG programme publishing historical US AIS free. **Parquet** — columnar binary table format; the filtered extract lives here so the expensive scan is paid once. **DuckDB** — in-process analytical database; applies the filter *during* the file scan so peak memory is the result, not the file. **Track** — one vessel's time-ordered journey, reconstructed by grouping broadcasts on MMSI. **The funnel** — `in_region ≥ in_window ≥ plausible ≥ scored`, the four counts that make "filter out irrelevant traffic" visible on screen. **Origin cloud** — Stage 2's output: a probability grid, a centroid, r50/r90 radii and a time window. **`type_prior`** — the 10% scoring component that gives a vessel a head start based on what kind of ship it is. **Abstention** — when `origin.abstain` is true, Stage 3 must return zero suspects; a designed refusal, enforced by the validator. **Exclusion** — a vessel explicitly ruled out with a stated plain-language reason; at least one is mandatory.

---

*Report compiled 2026-09-08 from `pipeline/attribute/*.py`, `data/ais/gulf.parquet` (677,093 rows), `pipeline/attribute/out/*` and `scripts/validate_case.py`. Every figure was recomputed from the output files for this report rather than copied from earlier notes. Figures marked post-fix were recomputed by applying the sentinel and dedupe rules to the existing extract; the 800 MB source has not been re-scanned since those fixes, so the committed `gulf.parquet` still contains the sentinel values until the ingest is rerun.*
