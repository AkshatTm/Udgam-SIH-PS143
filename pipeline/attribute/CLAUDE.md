# Attribution (Stage 3) — Jaiveer

Owns: AIS ingest → track reconstruction → scoring → `vessels.geojson` + `suspects.json`.
Full brief: `docs/06_JAIVEER_AIS.md`. Contracts: `docs/00_MASTER_PLAN.md` Part 6 (§6.6, §6.7).

## Non-negotiable

- **No ML.** Deterministic weighted sum; weights are named constants at the top of the file.
  Seven components (v4):

  | | |
  |---|---|
  | `proximity` | **0.30** — origin-grid probability at closest approach |
  | `parity` | 0.15 — track/slick parallelism · **chronic only** |
  | `temporality` | 0.15 — closeness in time to the release window |
  | `trajectory` | 0.15 — heading consistent with being the source |
  | `gap` | 0.15 — AIS silence overlapping the window |
  | `slowdown` | 0.05 — unusual slowdown near the origin |
  | `type_prior` | 0.05 — tanker/cargo over ferry |

- **Score the origin GRID, not the r50 circle** (D8). The real cloud is a 4.38:1 streak with
  44.7% of its high-probability mass outside r50. Sample `origin.json`'s 120×120 grid, and
  remember **row 0 is NORTH**:
  ```
  row = (north - lat) / (north - south) * (rows - 1)
  col = (lon - west)  / (east  - west ) * (cols - 1)
  ```
- **`null` ≠ `0`.** Each component returns `(score, applicable)`. Not-applicable contributes
  nothing and the remaining weights renormalise; a measured zero is a `0`. Rendering one as
  the other is an honesty bug (frozen convention 7).
- **Applicability gating, stated openly, never buried in an `if`** (D9):
  - `gap` — only when the vessel was under way on **both** sides of the silence. 64% of gap
    hits are docked boats.
  - `gap` — also discarded when the last report before the silence sits **on the search-box
    boundary**. Measured on case 1's box: 5 of 11 "silences" were vessels leaving the
    rectangle and returning, one of them apparently dark for 23 hours. Leaving the box is not
    going dark.
  - `slowdown` — scoped to the closest approach, compared against an **under-way median**
    that excludes hours at rest. Median SOG is exactly 0 for 66% of the fleet.
  - `parity` — only when `discharge_class == "chronic"`. A blob has no centerline.
- **`meta.ais_source` decides which components can fire at all** (D20). `noaa_dense` is ~71 s
  between reports; `gfw_hourly` is one position per vessel per hour, so `gap` is structurally
  impossible and `slowdown` is meaningless. Both return **`null`**, not zero. Never interpolate
  to compensate — that invents positions.
- **Four source types**, and classification runs *before* attribution:
  `vessel` · `dark_vessel` (mmsi `null`, never an invented identity) · `infrastructure` ·
  `natural_seep` (a flag on the finding, never a ranked suspect).
- **Every vessel name and MMSI on screen comes from the real AIS file.** If the documented
  vessel does not rank top-3, that is the result we show. Never reweight to force an outcome.
- The **funnel** is requirement (c) made visible: `in_region ≥ in_window ≥ plausible ≥ scored`,
  monotonic, plus `dropped_short_track` so no hidden assumption sits underneath it.
- At least **one exclusion with a plain-language reason** per case. Exoneration without a
  reason is worse than none.
- **Abstain** — zero suspects, funnel still populated — when `origin.abstain` is true, or more
  than ~40 vessels are plausible, or the top score is below 0.25. The refusal is a feature.
- Do NOT build MMSI identity resolution. One demo case; MMSI as-is; known imperfection.
- **Blind evaluation (D21).** Akshat holds the documented answers. Weights are set on the
  Phase 8 injected-offender curve, **never on a real case.**

## Env

`duckdb`, `pyarrow`, `pandas`, `numpy`, `matplotlib` — all pinned. **No new dependencies.**
Filter to bbox+time **on read**; never load a whole NOAA CSV into pandas (TRAPS #12).
Raw AIS stays in `data/ais/` (gitignored) on Jaiveer's machine only.
`SELECT *` on the parquet needs `pytz`, which we don't have — select `epoch(ts)`, not `ts`.

## What is here

| File | State |
|---|---|
| `ingest.py` | NOAA CSV → Parquet, filter-on-scan. Includes the **day-continuity guard** — refuses non-consecutive days, duplicate days, and files whose name disagrees with their contents (D6). |
| `tracks.py` | Parquet → per-MMSI `Track`. Drops <5 points, refuses to interpolate across >30 min. |
| `plot_tracks.py` | The eyeball check. |
| `tests.py` | **44 assertions, stdlib only.** `python pipeline/attribute/tests.py` — run it after every change. Mutation-tested: six deliberate bugs, six caught. |
| `make_fake_case.py` | US-located fake bundle over Galveston, so scoring is testable without waiting for Anushka. 4:1 streak cloud, so it actually exercises grid sampling. |
| `run.py` | **Stub only.** Delete `fake_fleet()` and its invented MMSIs the moment real scoring lands. |
| `score.py` | **Not written yet. This is the deliverable.** |

## Two traps already paid for

- **`run.py` writes to `out/`, which is gitignored — the validator reads `cases/<id>/`.** The
  "PASS" in the Phase 1 report validated Akshat's committed fixture, not our output. `score.py`
  must write **into the case bundle**.
- **AIS sentinels are in-range values, not blanks**: SOG 102.3, COG 360.0, Heading 511.
  COG's affects 9.9% of rows and would silently read as "steaming due north" — straight into
  trajectory, 15% of the score. Nulled in `ingest.py`, pinned by `tests.py`.

## You are remote

Post an end-of-day update in the group every single day and append to `docs/updates/jaiveer.md`
after each phase. Nobody can see your screen; silence reads as risk.
