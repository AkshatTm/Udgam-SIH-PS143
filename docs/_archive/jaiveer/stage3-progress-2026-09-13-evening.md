# Stage 3 — Attribution: progress report

**Jaiveer · 13 September 2026, 19:30 IST · for Akshat**
**Branch:** `jaiveer-phase2` (merged up to `origin/main` @ `6147388`) · **Freeze:** Tue 15 Sept 05:00 IST — **33.5 h**

Supersedes `docs/STAGE3_PROGRESS_2026-09-13.md` (this morning). The headline change: **Stage 3 has
produced its first real attribution output on a real case.** Everything below is measured, not
projected.

---

## 1. Status at a glance

| Phase | State | Change since this morning |
|---|---|---|
| 0 · Unblock + the Menuett block | **Done** | — |
| 1 · Core scorer | **Done** | — |
| 2 · Parity, head-proximity, temporality | Blocked — Soumirya's slick polygon | Now **measured** as blocked: `parity` returns `null` on the real case |
| 3 · Dark vessel | Blocked — Soumirya's `ship_detections` | — |
| 4 · Infrastructure | Not started | — |
| 5 · Traffic prior | Not started | — |
| 6 · Repeat offenders | Structurally undemonstrable — reframe as roadmap | — |
| 7 · Chronic vs acute | Blocked — `discharge_class` | — |
| 8 · Evaluation curve | Not started | Now the critical path |
| 9 · Real cases | **1 of 6 done** | **Jacksonville shipped** |
| 10 · Robustness | 10.3 done (R10 closed) | — |

**Stage 3 is no longer the long pole on Jacksonville.** The remaining five real cases are the same
two commands each; two of them are `gfw_hourly` and need a different code path exercised (§7).

---

## 2. What changed since the morning report

1. **Merged `origin/main` into `jaiveer-phase2`** — your 13 Sept catch-up (`6147388`), which brought
   the six real Stage 2 bundles, the Stage 1 channel-order correction, and four branch merges.
   `git log --oneline jaiveer-phase2..origin/main` is now empty; 63 tests still pass.
2. **Ingested real NOAA AIS for 29 + 30 July 2024** against Anushka's published Jacksonville origin.
3. **Scored `case-jacksonville-2024`** and wrote `vessels.geojson` + `suspects.json` into the bundle.
4. **Validator PASS**, 149 warnings — all of them Stage 2's, none Stage 3's (§6.1).
5. Wrote `docs/HANDOFF_STAGE3_JAIVEER.md`, a full technical handoff so this work can be resumed by
   another session or another person without me.

### A merge note you should know about

Your first merge into `main` took an **earlier** commit from `jaiveer-phase2`, not the tip. For a
few hours `main` carried `geo.py` and the updated `ingest.py` but **no `score.py`**, no
`STAGE3_PROGRESS`, no `STAGE3_COMPONENT_REPORT`, and older `tests.py` / `make_fake_case.py`. Your
second pass (`14196b7`) fixed it. Flagging it only because a partially-merged Stage 3 is invisible —
`main` still validated PASS, because `acts_available` does not include `attribute`, so the validator
never looks for the files that were missing.

---

## 3. The Jacksonville run — full technical account

### 3.1 Inputs

| Input | Value |
|---|---|
| Case | `case-jacksonville-2024` (hero case; `index.json` default) |
| Origin | Anushka's published `origin.json`, 93,922 B, 120 × 120 grid, normalised to peak 1.0 |
| AIS | NOAA Marine Cadastre `AIS_2024_07_29.csv` (1,034,932,693 B) + `AIS_2024_07_30.csv` (1,012,903,535 B) |
| `ais_source` | `noaa_dense` (per `meta.json`) — so `gap` and `slowdown` are measurable, not `null` |
| Parquet | `data/ais/jacksonville.parquet`, DuckDB filter-on-scan, box + window derived from `origin.json` |

**Day selection is forced by the origin window**, not chosen: `time_window` is
`2024-07-29T23:21:29Z → 2024-07-30T07:39:29Z`, so the run needs 29 and 30 July. `AIS_2024_07_31.csv`
is downloaded and irrelevant. The D6 day-continuity guard accepted the pair as consecutive.

### 3.2 Origin cloud geometry, measured from the published grid

| Property | Value | Why it matters |
|---|---|---|
| Grid | 120 × 120, row 0 = north | Sampled nearest-cell by `geo.OriginGrid` |
| Bounds | W −79.88669, S 28.55414, E −79.53889, N 29.61825 | ≈ 34 km × 118 km |
| Centroid | `[-79.73175, 29.03215]` | What `suspects.json` measures distance to (see §6.2) |
| **Grid peak** | **`[-79.68210, 29.11749]`**, cell (row 56, col 70) | **10.65 km from the centroid** |
| `radius_50_km` | 13.1 | |
| `radius_90_km` | 31.11 | Also the `trajectory` approach radius — see §4.3 |
| **Aspect ratio** | **3.68 : 1** (probability-weighted second moments) | Vindicates **D8** on real data, again |
| Major axis | **170.1° from north** | Near north–south, consistent with Gulf Stream advection |
| `time_window_method` | `convergence` | A measured release window, not a bracket — frontend may render it as a measurement |
| `abstain` | `false` | `radius_90_km` 31.11 < the 40 km trigger |
| `age_method` | `none`, `age_hours: null`, `age_weathering: unknown` | Phase 7 stays blocked |

**D8 is not a theoretical concern on this case.** A 3.68:1 cloud with its peak 10.65 km off the
centroid is precisely the shape for which r50-circle membership gives the wrong answer. Both
suspects scored ≈0.94 grid probability at ≈10.2 km from the centroid — i.e. they were sitting on
the *peak*, not near the centre. A circle-based scorer would have ranked them by the wrong distance.

### 3.3 Funnel

```
in_region 48  ->  in_window 26  ->  plausible 2  ->  scored 2
dropped_short_track 2
```

- **48 in region** — the box is 34 × 118 km of open ocean 170 km offshore. Sparse traffic is
  expected and is exactly why this case is a good hero: the answer is not buried in a shipping lane.
- **26 in window** — the release window is 8.3 h wide.
- **26 → 2 is the big cut**, and it is `PLAUSIBLE_GRID_MIN = 0.05`: 24 vessels never touched a cell
  with ≥5% of peak probability. That is D8 doing its job — a circle of radius r50 = 13.1 km around
  the centroid would have admitted a different, larger and less discriminating set.
- **2 dropped for short track** (`MIN_POINTS`), reported separately so the funnel stays monotone.

Funnel counts decrease monotonically, as §6.7 requires.

### 3.4 Result

| # | MMSI | Name | Type | Score | Grid prob | Dist. to centroid | Closest-approach time |
|---|---|---|---|---|---|---|---|
| 1 | `636093219` | NAGOYA EXPRESS | cargo | **0.693** | 0.946 | 10.22 km | 2024-07-30T04:44:49Z |
| 2 | `367337960` | GALVESTON | other | **0.650** | 0.943 | 10.13 km | 2024-07-30T01:58:44Z |

`abstained: false`, `dark_vessels: []`, `infrastructure: []`, `excluded: []`.
`excluded` is empty because `plausible == scored == 2` — there was no pool left to exclude from.

`vessels.geojson`: 2 LineString features, `n_points` 456 and 385, neither decimated (both under the
500-point cap), `max_gap_minutes` 2.4 and 6.3. Every suspect `mmsi` has a matching track, as the
validator requires.

### 3.5 Component-by-component, both vessels

| Component | Weight | NAGOYA EXPRESS | GALVESTON | Note emitted |
|---|---|---|---|---|
| `proximity` | 0.30 | 0.946 | 0.943 | origin-grid probability at closest approach |
| `parity` | 0.15 | **`null`** | **`null`** | *"slick is unknown — parity needs a linear slick with a centerline"* |
| `temporality` | 0.15 | 0.701 | 0.632 | 1.2 h / 1.5 h from the centre of the release window |
| `trajectory` | 0.15 | 1.000 | 1.000 | on approach 31 km out: 168° vs 186° (**17° off**) / 1° vs 356° (**5° off**) |
| `gap` | 0.15 | **0.000** | **0.000** | longest silence overlapping the window: 2 min / 6 min |
| `slowdown` | 0.05 | **0.000** | **0.000** | 12.0 kn vs 12.5 kn median / 15.7 kn vs 15.2 kn median |
| `type_prior` | 0.05 | 1.000 | 0.500 | cargo / other |

With `parity` not applicable, the remaining weights renormalise over 0.85 — **D9 working on real
data for the first time.**

---

## 4. What this run establishes

### 4.1 The `null` / `0` distinction is now demonstrated, not just asserted

On one card, in one run, we have both:

- `parity: null` — *structurally unmeasurable*, because Stage 1 has not published a slick polygon.
- `gap: 0.0` and `slowdown: 0.0` — *measured and genuinely zero*. This is `noaa_dense`; a 2-minute
  worst silence is a real finding about the vessel, not a hole in the data.

That contrast is the cleanest possible illustration of frozen convention 4, and it is worth a slide.

### 4.2 D8 is vindicated on real data for the second time

3.68:1 aspect, peak 10.65 km off centroid, and the plausible set cut from 26 to 2 by grid
probability rather than radius. See §3.2.

### 4.3 `trajectory` reproduces its near-tautology on real data

Both vessels score **1.00**, at 17° and 5° off. The note text confirms the corrected measurement
point is working as designed — *"on approach 31 km out"* is `radius_90_km = 31.11`, i.e. the last
report before the vessel entered the 90% mass contour.

But 2 of 2 at 1.00 is the same pattern as the synthetic case (13 of 15). **`trajectory` is carrying
15% of the weight and separating nothing.** Restating the position from this morning: the fix was to
*where* it is measured, not *how much* it is worth, and **no weight has been touched**. Settling the
weight is Phase 8's job or yours (§8).

### 4.4 The D30 pre-registered failure mode did not fire here

The pre-registration was that `gap` would award full marks to a competing vessel (STENA PROSPEROUS,
7.4 km, 12.5 kn, 142 min silent) and zero to the documented one. **STENA PROSPEROUS is not in the
plausible set for this run at all** — it never touched ≥5% grid probability inside the 8.3 h window.
The pre-registration stands as written; it simply describes a different window than the one
Anushka's published origin defines. Worth recording so nobody later reads its non-appearance as the
prediction having been wrong.

### 4.5 The margin is thin, and should be said out loud

0.693 vs 0.650 is **6.2%**, against `ABSTAIN_TIE_FRACTION = 0.03`. The scorer named names, but it
was roughly two percentage points from refusing. On a slide that is a strength — the system has a
refusal mode and came close to using it — but only if we say it before a judge computes it.

---

## 5. Defects and semantic issues found

### 5.1 `closest_km` does not mean what §6.7 implies — **needs your ruling**

`score.py` computes:

```python
"closest_km": round(geo.haversine_km(pos[0], pos[1], *grid.centroid), 2)
```

where `pos` is **the position at which the vessel touched its highest grid probability**. So the
field is *"distance from the origin centroid to the vessel's best-probability sample point"* — not
"how close the vessel came to the origin", which is how the name reads and how a frontend will
render it.

On this case the difference is material. Both vessels sat essentially **on the grid peak** (0.946,
0.943) — and the peak is 10.65 km from the centroid. So they report `closest_km` ≈ 10.2 km while
being, in the only sense the model cares about, *at* the most likely origin. A card reading
*"came within 10.2 km"* understates the finding.

Three options, all defensible, but it must be one of them and stated:

- **(a)** Keep the definition, rename the field to `centroid_km` — requires a §6.7 amendment.
- **(b)** Measure to the **grid peak** instead of the centroid. Consistent with D8's logic
  (the grid is the object, not a circle around a centroid), and would report ≈0.5 km here.
- **(c)** Redefine as true minimum track-to-centroid distance. Matches the field name, but is the
  least informative of the three and reintroduces circle thinking.

**My recommendation: (b), with the note text saying which reference point was used.** But this is a
schema-semantics call, so it is yours, and I have changed nothing.

This is the same peak-vs-centroid question I raised this morning, now with a concrete consequence.

### 5.2 The 149 validator warnings are Stage 2's, not Stage 3's

All 149 are of two forms:

```
WARN  particles_forward.json/positions[96]: [-78.xxxxx, 31.xxxxx] falls well outside the scene bounds
WARN  origin.json/centroid: [-79.73175, 29.03215] falls well outside the scene bounds
```

Both are expected consequences of the case's own design, not errors:

- The scene box is a **0.03° pad around the slick** (`bounds.json`: W −79.6782 → E −79.5914,
  S 30.2139 → N 30.5541), deliberately tight to stay under GEE's 48 MiB direct-download ceiling at
  10 m (D14).
- The origin is **170 km away** and the forward particles run *further* away still. Of course they
  are outside a 10 km × 38 km box.

**The validator's "outside the scene bounds" check is wrong for `trace` outputs**, which by
construction leave the scene. Suggest either scoping that check to `detect` outputs only, or
comparing against `origin.bounds` rather than `bounds.json` for the trace layers. Anushka's and
yours to decide — I have not touched it. Flagging it because 149 warnings on the hero case will be
the first thing a reviewer sees.

### 5.3 `acts_available` still excludes `attribute` — **blocks Harshita**

`cases/case-jacksonville-2024/meta.json` has `"acts_available": ["detect", "trace"]`. Stage 3's
output is now in the bundle and validates, but:

- the validator never checks it, and
- Harshita's Attribute panel does not switch on.

`meta.json` is shared, so this is your edit, not mine. Requesting `"attribute"` be added to
Jacksonville once you have looked at the output.

### 5.4 `component_notes` is still unblessed

Present in the output, not in §6.7. Eleven distinct strings across the two vessels, all
measurements or gate reasons, **zero vessel names, zero MMSIs** (re-verified on this run). It is
what makes D9's "stated rules, not quiet conditionals" visible on the card. Bless it into §6.7 or
tell me to drop it — but the frontend needs to know now, not on Monday.

---

## 6. What I need from you, ranked

| # | Ask | Blocks |
|---|---|---|
| 1 | Add `"attribute"` to `acts_available` on `case-jacksonville-2024` | Harshita's integration and QA |
| 2 | Rule on `closest_km` semantics — (a), (b) or (c) in §5.1 | Frontend card copy; possibly a §6.7 amendment |
| 3 | Bless or kill `component_notes` | Frontend card layout |
| 4 | Rule on the scene-bounds warnings (§5.2) — scope the check, or accept 149 warnings on the hero case | Reviewer's first impression |
| 5 | `trajectory` weight: leave at 0.15 pending Phase 8, or reallocate now on your authority | §4.3 |
| 6 | Edit Master Part 3 — Menuett is not a gap case (D30); it says ~100 km, it is 170 km | Slide accuracy |
| 7 | Decide the Part 16 wording given D31 — cases 1, 2, 4, 5 are not blind | Honesty of the evaluation claim |
| 8 | Master plan decision table stops at **D22**; your handoff and the case `meta.json` cite **D30/D31** | Anyone reading the plan as the source of truth |

---

## 7. The remaining five cases, and the trap in them

Same two commands each. But:

| Case | `ais_source` | Note |
|---|---|---|
| `case-farallones-2023` | expected `noaa_dense` | US Pacific — NOAA coverage |
| `case-huntington-2021` | expected `noaa_dense` | Infrastructure case (D10); needs Phase 4 for full value |
| `case-gulf-alaska-2023` | expected `noaa_dense` | **The dark-vessel case.** Per D30's fallout this is where the "went dark" story now lives. Needs Soumirya's `ship_detections` with `est_length_m` |
| `case-mumbai-2023` | **`gfw_hourly`** | NOAA does not cover Indian waters |
| `case-jamnagar-2024` | **`gfw_hourly`** | Same |

**The GFW pair is the untested code path.** Per D20 and frozen convention 4, on those cases `gap`
and `slowdown` must return **`null`**, and the validator now *fails* on a zero there. I have a
synthetic fixture for it (`cases/case-000-gfw`) but have not yet run the gating end to end. That is
the first thing I will do after this report, because a `0.0` where a `null` belongs is an honesty
bug that would fail the hero of the Indian-waters half of the library.

I also have not yet exercised the abstain path against `cases/case-000-abstain`.

---

## 8. Next, in order

1. **`gfw_hourly` gating test** against `case-000-gfw`, and the abstain path against
   `case-000-abstain`. Dependency-free, and it de-risks two of the five remaining cases.
2. **The remaining five real cases**, subject to AIS availability. NOAA days are ~1 GB each; the
   GFW pair needs a different acquisition path entirely, which is unscoped — flag if you know it.
3. **Phase 8, the injected-offender curve** (`pipeline/attribute/evaluate.py`). Needs nobody, is a
   named Part 14 deliverable, and is the only legitimate way to settle the `trajectory` and
   `type_prior` weight questions without violating D21. Real AIS traffic plus a synthetic guilty
   vessel whose discharge point, gap, speed profile and manoeuvre I control; sweep traffic density,
   gap duration, cloud size and sampling rate; report top-3 rate with a stated operating limit.
4. Sampling-density experiment: downsample Menuett to hourly, re-score, report the rank change.
   This is the empirical backing for D20 and it is cheap.

**Nothing on that list requires a weight change, and none will be made.** Every finding in this
report could have been made to disappear by adjusting one number, which is precisely what D21 exists
to prevent.

---

## 9. Reproduction

```powershell
git checkout jaiveer-phase2

python pipeline/attribute/tests.py                    # 63 assertions, stdlib unittest

python pipeline/attribute/ingest.py `
    --csv data/ais/AIS_2024_07_29.csv data/ais/AIS_2024_07_30.csv `
    --from-origin cases/case-jacksonville-2024/origin.json `
    --out data/ais/jacksonville.parquet

python pipeline/attribute/score.py --case case-jacksonville-2024 `
    --parquet data/ais/jacksonville.parquet --ranking

python scripts/validate_case.py cases/case-jacksonville-2024
```

Deterministic — R10 closed, identical ranking on Linux/container and Windows/Python 3.11.
Stage 3 adds no dependency beyond `duckdb`; tests are stdlib `unittest`, not pytest.

---

## 10. Appendix — `suspects.json` as written

```json
{
  "funnel": {"in_region": 48, "in_window": 26, "plausible": 2, "scored": 2,
             "dropped_short_track": 2},
  "suspects": [
    { "source_type": "vessel", "mmsi": "636093219", "name": "NAGOYA EXPRESS",
      "vessel_type": "cargo", "score": 0.693,
      "components": {"proximity": 0.946, "parity": null, "temporality": 0.701,
                     "trajectory": 1.0, "gap": 0.0, "slowdown": 0.0, "type_prior": 1.0},
      "component_notes": {
        "proximity": "origin-grid probability at closest approach",
        "parity": "slick is unknown — parity needs a linear slick with a centerline",
        "temporality": "closest approach 1.2 h from the centre of the release window",
        "trajectory": "on approach 31 km out, course 168 deg against 186 deg toward the origin (17 deg off)",
        "gap": "longest silence overlapping the window: 2 minutes",
        "slowdown": "12.0 kn at closest approach against an under-way median of 12.5 kn",
        "type_prior": "vessel type cargo"},
      "closest_km": 10.22, "closest_time": "2024-07-30T04:44:49Z",
      "grid_probability": 0.946, "heading_consistent": true,
      "ais_gap_minutes": 2.4, "edge_truncated": false,
      "reasons": ["inside the high-probability region of the reconstructed origin during the release window",
                  "cargo on a course consistent with the origin"] },
    { "source_type": "vessel", "mmsi": "367337960", "name": "GALVESTON",
      "vessel_type": "other", "score": 0.65,
      "components": {"proximity": 0.943, "parity": null, "temporality": 0.632,
                     "trajectory": 1.0, "gap": 0.0, "slowdown": 0.0, "type_prior": 0.5},
      "closest_km": 10.13, "closest_time": "2024-07-30T01:58:44Z",
      "grid_probability": 0.943, "heading_consistent": true,
      "ais_gap_minutes": 6.3, "edge_truncated": false }
  ],
  "dark_vessels": [], "infrastructure": [], "excluded": [],
  "abstained": false, "abstain_reason": null
}
```

*(GALVESTON's `component_notes` and `reasons` elided here for length; both are present in the file.)*
