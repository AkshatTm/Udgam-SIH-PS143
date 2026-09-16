# Stage 2 — forward drift, Version A (no schema change)

*Anushka, 16 Sept 2026. Akshat's ruling (16 Sept): `forward_impact.json` is **deferred, not refused** — Version A ships for
the demo, and the numbers below drop straight into that file when it lands post-demo. No bundle was written.*

## What was run

The same 50-member ensemble as the published backward answer (same seed particles, seed 143, same stratified wind-coefficient
and current-scale draws), run **forward** from t0 with GSHHG stranding on and hourly frames kept.
Hour 0 is identical in both directions on every case, which is the check that the two runs start from the same cloud.

```bash
python pipeline/drift/eval_forward.py --case <id>     # writes docs/evaluation/figures/stage2/data/forward_<id>.json
python pipeline/drift/plot_evidence.py                # F2.9_both_directions.png
```

## Results — 24 h horizon

r50 / r90 in km. Spread is **precision, not accuracy**.

| case | origin (−24 h) | t0 | +12 h | +24 h | centroid moves (km, +24 h) | stranded at +24 h | first landfall (h) | seeded ashore | edge margin (km) |
|---|---|---|---|---|---|---|---|---|---|
| `case-jacksonville-2024` | 13.1 / 31.1 | 8.9 / 15.7 | 12.0 / 25.5 | 16.2 / 35.5 | 137.0 | 0.00 | null | 0.0000 | 98 |
| `case-farallones-2023` | 4.4 / 8.8 | 4.4 / 7.7 | 4.2 / 7.1 | 5.7 / 9.1 | 27.0 | 0.00 | null | 0.0000 | 84 |
| `case-jamnagar-2024` | 2.3 / 3.7 | 2.0 / 3.5 | 2.1 / 4.1 | 2.3 / 4.9 | 19.5 | 0.00 | null | 0.0000 | 91 |
| `case-mumbai-2023` | 2.0 / 3.7 | 1.3 / 2.3 | 1.7 / 3.1 | 2.6 / 5.8 | 27.9 | 0.00 | null | 0.0000 | 84 |
| `case-gulf-alaska-2023` | 1.4 / 2.6 | 0.8 / 1.4 | 1.0 / 2.0 | 1.5 / 3.1 | 21.1 | 0.00 | null | 0.0000 | 91 |
| `case-huntington-2021` | 1.4 / 2.5 | 1.1 / 2.0 | 1.4 / 2.5 | 1.6 / 3.3 | 6.0 | 0.00 | null | 0.0000 | 108 |

n = 50 runs × 3000 particles = 150,000 endpoints per case, per hour.

## What this says, and what it does not

- **No particle reaches the coastline within 24 h on any of the six cases.** `first_landfall_hours` is `null`, not `0`.
  That matches the single control run in `pipeline/drift/out/coastal_impact_<case>.json`.
- **The stranding tracker was checked, not assumed.** Re-run on Huntington with a synthetic coastline across the drift path, it
  reported 11.7% seeded ashore (excluded from landfall), first landfall at 0.25 h, and a monotone curve reaching 76.7% by 24 h.
  So the zeros above are measured zeros.
- **Horizon is 24 h, not 72 h.** The cached HYCOM + ERA5 fields end 24.6–26.0 h after t0 on every case, and
  `assert_field_covers` refuses a longer run rather than extrapolating through a frozen last snapshot. +48 h and +72 h need a
  wider GEE fetch. Past ~48 h omitted physics enters the error budget, so a 72 h number would also be a weaker claim than a 24 h one.
- **Assets at risk are not produced.** Every asset needs a citable source (WDPA etc.) with URL and retrieval date. None has been
  fetched, and with no landfall and no cloud reaching the coast at 24 h, nothing can be listed yet.
- **Windage is 0.03, not tuned.** Stratified U(0.025, 0.035), same as the backward ensemble.
- **`meta.notes` was not written.** `meta.json` is produced by `pipeline/export/build_case.py`; adding a note there is Akshat's call
  (Rule 3: never hand-edit a bundle).

## For `forward_impact.json`, post-demo

The per-hour `envelope` (r50, r90, centroid, stranded_fraction), `first_landfall_hours` and `horizon_hours` in each
`forward_<case>.json` map one-to-one onto the proposed shape. `coast_segments` and `assets_at_risk` need a gazetteer and a
cited asset layer first.
