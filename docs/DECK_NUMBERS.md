# Deck numbers: what we can say, with its receipt

*Compiled 14 Sept by Akshat for the Phase 6 deck. Every figure below is copied from a named source file,
not remembered. If a number isn't here, it doesn't go on a slide until it is. Verification verdicts are
**not** here, because they are the answers; they arrive with the Verify screen.*

**Framing rule for the whole deck:** every number carries its unit, its sample size and what it
measures. Precision is never called accuracy, and agreement with another algorithm is never called ground truth.

---

## Prior art (first content slide)

CleanSeaNet (EMSA), SkyTruth Cerulean, INCOIS. Master Plan Part 11 has the four things we do
differently. Cerulean is also where cases 1, 2, 4 and 5 came from; say so.

## Data provenance (mandatory)

- **Zenodo oil-spill dataset, Part III**, DOI **10.5281/zenodo.13761290**, **CC-BY**. The attribution
  must appear on a slide. Source: `docs/receipts.md` "Training data".
- Sentinel-1 via Google Earth Engine; HYCOM currents (÷1000, not ÷100); ERA5 u/v wind; NOAA Marine Cadastre AIS.

## Stage 1: detection

| Say | Number | Source | Never say |
|---|---|---|---|
| Scene classification on the authors' held-out test set | accuracy **0.951**, look-alike rejection **0.940**, oil recall **0.927**, all 450 Part III scenes, threshold 0.143 chosen on validation | `receipts.md` "Detection accuracy" | 0.960 / 0.987 / 0.434 (dead model) |
| U-Net oil-class IoU, gated | **0.435** (138/150 oil scenes) | same | "23%" anything on detection (that was a `wind_share`) |
| Adding a second polarisation | val F1 **0.346 → 0.643**, Part III precision **5.8×** at identical recall | `receipts.md` L104, `docs/updates/soum.md` §622 | "VH is the discriminator" (the top feature was computed from VV) |
| Agreement with Cerulean on real incidents | median IoU **0.483**, range 0.165–0.728, **n = 5**, recall 0.80–0.94 | `receipts.md` "IoU against SkyTruth Cerulean" | "accuracy" on real cases |
| Networks and live cases | networks transfer once channels match; live cases stay classical on evidence (Layer 2 median 0.504 vs 0.483, behind on 3 of 5) | Master §6.1 / D33 amendment | "the networks don't transfer" |
| The benchmark gap | authors report 99% / 96% IoU on their set; ~53% is Krestenitis (a different dataset). The gap measures look-alike variety | `receipts.md` "two-benchmark framing" | ~53% as our number |
| Correct rejections | Ennore look-alike: zero oil features. Zenodo look-alike P(oil) 0.0020 | case bundles | — |

## Stage 2: trace

Per case, from the published `origin.json` (cross-checked against `docs/_archive/anushka/STAGE2_NUMBERS.md` §8.9):

| case | r50 | r90 | median travel | wind share | release window |
|---|---|---|---|---|---|
| Jacksonville | 13.1 km | 31.1 km | 148.7 km | 0.04 | **measured** (convergence) 8.3 h |
| Farallones | 4.4 km | 8.8 km | 35.5 km | 0.37 | bounded 16 h bracket |
| Gulf of Alaska | 1.4 km | 2.6 km | 12.0 km | **0.73** | **measured** 2.0 h |
| Huntington | 1.4 km | 2.5 km | 6.2 km | 0.38 | **measured** 2.3 h |
| Jamnagar | 2.3 km | 3.7 km | 16.7 km | **0.62** | bounded 16 h bracket |
| Mumbai | 2.0 km | 3.7 km | 16.7 km | 0.37 | bounded 16 h bracket |

| Say | Never say |
|---|---|
| r50/r90 are **precision** across a 50-member ensemble, and r50 tracks path length, not case difficulty | "accurate to X km" |
| OpenDrift (RK4) agrees within **550 m on Jacksonville over a 140 km rewind**, 0.26–1.05% of path on all six | "118 m" as a real-case number (that is synthetic `case-000`) |
| Age: **not estimated**. The gate is that no detection is `acute` | any age accuracy claim, including "N = 1 on Huntington" (withdrawn) |
| Direction arrows on **Jacksonville and Farallones only** | arrows on Huntington (143° reversal), Mumbai, Jamnagar |
| Alaska and Jamnagar origins are **wind-driven** (ERA5), the other four current-driven. The error budget is a library average and inverts on those two | an error budget as universal |
| One trace per spill event, and the seed is recorded in `meta.notes` (D35). Mumbai seeds the 1.48 km² fragment of 9.55 km² | "trace this slick" per detection |

## Stage 3: attribute

| Say | Number | Source | Never say |
|---|---|---|---|
| The refusal path on real AIS | Galveston funnel **987 → 897 → 17**, then **abstain** (top two within 1.1%) | `receipts.md` AIS | — |
| Abstention on a real case | Huntington: 106 → 75 → 5, abstains, names no transiting ship (NTSB: none was the proximate source) | bundle | — |
| AIS density on the hero case | **69 s** reporting interval, holds to 240 km offshore; position ~170 km out | `receipts.md` | ~100 km; "gap case" (D30) |
| Evidence breadth is shown with every score (D37) | e.g. 5 of 7 components live | `suspects.json` | a bare score |
| `null` ≠ 0: gap/slowdown are n/a on hourly AIS (D20) | — | Master §6.1 | — |
| **Both Indian cases now search real vessels** (GFW hourly, D40) | Mumbai 9 vessels / 31 vessel-hours, funnel 9 → 2 → 0 → 0; Jamnagar 8 / 43, 8 → 2 → 0 → 0. Both abstain because **no vessel entered the origin cloud** | `docs/receipts.md` GFW section | "no AIS available in Indian waters" — that was our error, corrected 14 Sept |
| Infrastructure association is built and contracted (D38) | — | Master §6.1 | that it found the Huntington pipeline (it scores below floor) |
| **Injected-offender curve (Phase 8), offshore, 300 trials/point** | top-1 **0.910** [0.87–0.94], top-3 0.964, 23/300 abstained, given a cloud with 0.5 × r90 of error | `docs/STAGE3_PHASE8.md` | any of it as an accuracy figure for the six live cases |
| Sampling density is the biggest lever | dense **0.910** → hourly **0.488** offshore; 0.782 → 0.296 in port | same | — |
| Origin quality sets the ceiling | perfect cloud **1.000**; error of one r90 **0.653** | same | — |
| A hard offender (no gap, no slowdown) | top-1 **0.556**, top-3 0.923 | same | quoting only the baseline |
| It refuses as water crowds | port, 25 km cloud: **111 of 150 trials abstained** | same | — |
| Honesty slide, now measured: `trajectory` **−0.051** top-1 when removed, `type_prior` **−0.024**, `gap` **+0.143** (removing it helps when the offender never goes dark). **No weight moved.** | — | `STAGE3_PHASE8.md` ablation | that we tuned anything on a real case |
| Repeat offenders: in the data model, roadmap | — | A8 | a working feature |

## Blind evaluation

State it per case (Master §16.1). **Don't quote a count.** Farallones is blind on weights, not
provably on identity. Weights and thresholds were set on injected scenarios only.

## Roadmap (not claimed as built)

Traffic prior (Phase 5) · repeat offenders (Phase 6) · chronic-vs-acute (Phase 7) · age estimation to
bound the rewind · per-detection tracing · GFW hourly AIS for Indian cases.
