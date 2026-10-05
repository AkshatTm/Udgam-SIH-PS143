# Deck numbers: what we can say, with its receipt

*Regenerated 5 Oct 2026 against the repo at `697a630`. It replaces the 14 Sept compilation, which
pre-dated the age engine (D45, D53, D54, D56), the Stage 3 re-score (D48–D51, D55, D57) and the
Stage 1 jury pair. Every figure below is copied from a named source file, not remembered. If a
number isn't here, it doesn't go on a slide until it is. Verification verdicts are **not** here,
because they are the answers; they arrive with the Verify screen.*

**Framing rule for the whole deck:** every number carries its unit, its sample size and what it
measures. Precision is never called accuracy, and agreement with another algorithm is never called ground truth.

**Source precedence used to build this file.** When two sources disagree, the higher one wins:
(1) the committed case bundles `cases/<case_id>/*.json`, (2) the committed metric files in
`pipeline/detect/results/`, `pipeline/detect/models/*_meta.json` and `pipeline/attribute/results/`,
(3) `docs/evaluation/*.md` and the Master Plan decision log, (4) `docs/receipts.md`. Within a
bundle, a structured field beats the free-text `meta.notes`. Several notes still carry 14 Sept prose
that the fields have since overtaken (listed under "Change log", below).

**Bundle state when this was compiled:** `python scripts/validate_case.py cases/` returns PASS on
all nine indexed cases (warnings only), and `python scripts/test_validator.py` catches 36/36
mutations.

---

## Prior art (first content slide)

CleanSeaNet (EMSA), SkyTruth Cerulean, INCOIS. Master Plan Part 11 has the four things we do
differently. Cerulean is also where cases 1, 2, 4 and 5 came from; say so.

## Data provenance (mandatory)

- **Zenodo oil-spill dataset, Part III**, DOI **10.5281/zenodo.13761290**, **CC-BY-4.0**. The
  attribution must appear on a slide. Source: `docs/receipts.md` "Training data".
- **SkyTruth Cerulean** polygons in five bundles are **CC BY-SA 4.0** (attribution *and*
  ShareAlike). Source: `docs/receipts.md` "SkyTruth Cerulean", `DATA_LICENSES.md`.
- **Global Fishing Watch** hourly AIS and SAR vessel detections are **non-commercial use only**.
  That condition goes on the provenance slide. Source: `docs/receipts.md` "Global Fishing Watch".
- Sentinel-1 via Google Earth Engine; HYCOM currents (÷1000, not ÷100); ERA5 u/v wind; NOAA Marine Cadastre AIS.

---

## Stage 1: detection

**Which model each number describes.** The jury pair is `scene_classifier_l1_e2c_recall` +
`unet_e2c_sea_refonly` (`docs/evaluation/stage1-jury-numbers.md`). **Neither network produces the
detections on the map.** All nine bundles come from the classical path (D33 routing). The two
benchmark bundles' P(oil) values were produced by the previously shipped classifier
(`scene_classifier.pt`, `scene_classifier_meta.json`, threshold 0.143). Say which model a number
came from.

| Say | Number | Source | Never say |
|---|---|---|---|
| Layer 1 scene classification on the authors' **held-out test set** (Zenodo Part III, scene-level, never trained on) | accuracy **0.942**, oil recall **0.927** (n = 150 oil scenes), look-alike rejection **0.920** (n = 150), clean-ocean rejection **0.980** (n = 150); confusion 139 TP · 15 FP · 11 FN · 285 TN over **450 scenes**; threshold **0.128**, chosen on a Parts I+II validation split as the lowest threshold holding validation precision ≥ 0.95 | `pipeline/detect/models/scene_classifier_l1_e2c_recall_meta.json` → `part3`, `threshold_selected_on`; `pipeline/detect/results/eval_part3_e2c.json` → `rows[1]` | 0.951 / 0.940 / 0.987 at threshold 0.143 as the presented pair (previous pair, see change log). "Our accuracy improved" or "regressed": the gap between the two pairs is inside the measured **±0.027** seed-to-seed noise (`stage1-jury-numbers.md`). 0.960 / 0.987 / 0.434 (dead model) |
| Layer 2 U-Net oil-class IoU on **held-out VALIDATION** scenes (Parts I+II, fold 0; say the word "validation") | pooled oil IoU **0.757**, 95% scene-bootstrap CI **0.705–0.805**, **n = 388 scenes, 182 oil**; gated recall 181/182 | `pipeline/detect/results/eval_val_e2c_gated_recall.json` → `folds.0.metric_decomposition.iou_oil_pooled`, `pooled_ci95` | 0.757 (or the ≥30% band's 0.824) as a test result. "23%" anything on detection (that was a `wind_share`) |
| The gate earns its place (validation, same split) | look-alike rejection **0.08** ungated → **0.84** gated, pooled IoU 0.757 both ways | `eval_val_e2c.json` → `folds.0.lookalike_rejection` (0.0777); `eval_val_e2c_gated_recall.json` → `folds.0.lookalike_rejection` (0.8447), `iou_positives` | — |
| **Presenter notes only, never on a slide:** Layer 2 on the Part III holdout, same pair, scored once on a frozen configuration | pooled oil IoU **0.452**, 95% CI **0.353–0.562**, 139/150 oil scenes reached the U-Net; ≥30%-coverage band **0.160** (n = 12) | `pipeline/detect/results/eval_part3_e2c.json` → `rows[3]` | 0.435 (previous pair's gated holdout figure). Dodging the question: answer it in one sentence |
| Where it fails: scenes where oil covers ≥ 30% of the frame. No demo case is in that band | demo-library oil coverage **0.00%–2.25%** across the nine cases; validation ≥ 30% band has **n = 3** | `stage1-jury-numbers.md` Slide 2; band n from `eval_val_e2c_gated_recall.json` → `iou_by_slick_size` | a third decimal on the n = 6 or n = 3 bands |
| Adding a second polarisation | val F1 **0.346 → 0.643**, Part III precision **5.8×** (0.049 → 0.286) at identical recall | `receipts.md` "SUPERSEDED IN PART, 13 Sept" block | "VH is the discriminator" (the top feature was computed from VV). That VH contributed to any live detection (VH is below the noise floor on all seven live scenes) |
| Agreement with SkyTruth Cerulean on real incidents, **classical detector**. Always state n | **n = 5:** median IoU **0.483**, range 0.165–0.728. **n = 4** (Gulf of Alaska excluded, since Cerulean's own reviewer classed it AMBIGUOUS): median **0.553**, range 0.452–0.728. Recall on their polygon **0.796–0.942** | per-case values `pipeline/detect/results/iou_cerulean.json` → `[i].oil.iou`, `.oil.recall`; n = 5 median `receipts.md`; n = 4 median `stage1-jury-numbers.md` Slide 3 | "accuracy" on real cases. Either median without its n. Hiding the fifth case: if asked, Alaska is 0.165 |
| Networks and live cases | networks transfer once channels match; live cases stay classical on evidence (Layer 2 median 0.504 vs classical 0.483 against Cerulean, behind on 3 of 5). **Measured on the pre-e2c Layer 2** | Master Plan D33 amendment | "the networks don't transfer" |
| The benchmark gap | authors report 99% / 96% IoU on their set; ~53% is Krestenitis (a different dataset). The gap measures look-alike variety | `receipts.md` "two-benchmark framing" | ~53% as our number |
| Correct rejections | Ennore look-alike: **0 oil** features, 29 look-alike features. Zenodo no-spill (`P3_No oil_00027`): 0 features, 0 contacts. Zenodo look-alike (`P3_Lookalike_00134`): P(oil) **0.0020** at threshold 0.143, **scored by the previously shipped classifier** | `cases/case-ennore-lookalike-2023/detections.geojson`; `cases/case-nospill-zenodo/detections.geojson`; `cases/case-lookalike-zenodo/meta.json` → `notes` | 0.0020 beside the 0.128 threshold (different classifier). `P3_No oil_00091` or its P(oil) 0.0003: that tile was farmland and was replaced |
| Radar contacts are **unattributed**, never dark vessels, until Stage 3 cross-checks them | **110** contacts across the nine bundles, land-masked with a real coastline: Huntington 43 · Ennore 41 · Mumbai 21 · Jamnagar 3 · Jacksonville 2 · Farallones, Gulf of Alaska and both Zenodo cases 0 | `cases/*/detections.geojson` → `ship_detections` (length) | 142 total; Ennore 72; `lookalike-zenodo` 1; `nospill-zenodo` 31 (all pre-land-mask or pre-replacement). "Dark vessel" for anything Stage 1 emits |
| Gulf of Alaska has **zero** UDGAM contacts, and that is correct | threshold −8.06 dB against a brightest water pixel of −8.79 dB | `receipts.md` "Case 4 (Alaska)" | that we lowered a threshold to find one |

---

## Stage 2: trace

Per case, from the published primary `origin.json`. "Age 80%" is `age_posterior.hpd80` (= `age_hours`),
the window is that interval mapped back from `meta.detection_time`, and the median is
`age_posterior.median`. "Models apart" is `model_mix.centroid_separation_km`.

| case | r50 | r90 | wind share | age 80% interval | age median | release window (UTC), method | models apart |
|---|---|---|---|---|---|---|---|
| Jacksonville | 12.3 km | 28.98 km | 0.0548 | 0.125–10.125 h | 1.845 h | 2024-07-30 13:13:59Z → 23:13:59Z, `age` | 0.83 km |
| Farallones | 5.11 km | 11.22 km | 0.4416 | 0.125–15.125 h | 2.912 h | 2023-03-16 23:17:12Z → 03-17 14:17:12Z, `age` | 0.83 km |
| Gulf of Alaska (primary, group-2) | 1.07 km | 2.29 km | 0.4494 | 0.125–7.625 h | 1.249 h | 2023-05-16 08:19:38Z → 15:49:38Z, `age` | 0.35 km |
| Huntington | 2.18 km | 4.59 km | 0.401 | 0.125–17.875 h | 4.078 h | 2021-10-01 08:05:51Z → 10-02 01:50:51Z, `age` | 0.74 km |
| Jamnagar | 2.81 km | 5.21 km | **0.567** | 0.125–14.125 h | 2.672 h | 2024-02-22 11:03:44Z → 02-23 01:03:44Z, `age` | 0.78 km |
| Mumbai (primary, group-2) | 2.57 km | 4.73 km | 0.376 | 0.125–14.875 h | 3.089 h | 2023-09-02 10:11:03Z → 09-03 00:56:03Z, `age` | 0.66 km |

Every primary: `ensemble_runs` 50, `abstain: false`, `stranded_fraction` 0.0,
`age_method: "combined"`. The age gate is `chronic_track` on Jacksonville, Farallones and Alaska and
`unknown_both` on Huntington, Jamnagar and Mumbai, which date on the track hypothesis alone (D54).

**Secondary spill groups (D56),** each with its own age, from `origin_group-*.json`:

| group | seed | r50 | r90 | age 80% interval | window method |
|---|---|---|---|---|---|
| Gulf of Alaska group-1 | det-02, 0.596 km² | 1.08 km | 2.37 km | 0.125–10.375 h | `age` |
| Gulf of Alaska group-3 | det-03, 0.184 km² | 0.85 km | 1.66 km | 0.125–7.375 h | `age` |
| Mumbai group-1 | det-02, 7.606 km² | 3.95 km | 8.24 km | 0.125–24.125 h | `age` |
| Mumbai group-3 | det-04, 0.470 km² | 1.51 km | 3.24 km | 0.125–11.875 h | `age` |

Seeds and areas: `meta.json` → `spill_groups`.

| Say | Number | Source | Never say |
|---|---|---|---|
| r50/r90 are **precision** across a 50-member ensemble pooled over the age posterior, not distance from a true origin. There is no ground truth for origin position on any case | per-case table above | `origin.json` → `radius_50_km`, `radius_90_km` | "accurate to X km". 13.1 / 31.1 (Jacksonville), 4.4 / 8.8, 1.4 / 2.6, 1.4 / 2.5, 2.3 / 3.7, 2.0 / 3.7 (the 13 Sept 24 h-rewind radii). 14.7 / 33.9 and the other 17 Sept radii |
| The on-screen cloud is an **equal-weight mix of two models**: our RK2 and OpenDrift OceanDrift with its own physics **on** (Stokes, vertical mixing, Okubo diffusivity, per-element wind factor, GSHHG stranding, RK4), both pooled over the age posterior. Their centroids sit **0.35–0.83 km apart** across the six primaries | per-case "models apart" column | `origin.json` → `model_mix.centroid_separation_km`, `model_mix.models[1].physics`, `model_mix.weighting` | "OpenDrift confirms our origin". That the 50/50 weighting reflects skill (it doesn't: with no ground truth, any skill weight would be invented) |
| **OpenDrift integrator check (physics OFF).** Our RK2 against OpenDrift 1.14.11's RK4 on the identical cached field, 3000 particles, **24 h backward, pure advection**: landmask, vertical mixing, Stokes drift and diffusivity all switched off so only the integrator differs. On Jacksonville the origin centroids sit **550 m apart after a 140 km rewind** (0.39% of path); across all six spill cases, **0.26–1.05% of path**. It proves the physics implementation, not the answer | 550.3 m; 140.2 km median travel; 0.26–1.05% (n = 6) | `stage2-numbers.md` §8.4 table; `receipts.md` "Independent-implementation check" | **The 550 m describes the integrator check with the physics switched off. It does not describe the rewind on screen**: that one is age-truncated, age-pooled and mixed with an OceanDrift run whose physics are on. Its comparable figure is the 0.83 km model separation above. Never put 550 m or 140 km beside the map's cloud. "118 m" as a real-case number (that is synthetic `case-000`) |
| Age is an **80% interval, not a point.** On **144 held-out synthetic twins** run through the six cases' own HYCOM + ERA5 fields, each scored by the model that did not generate it, the interval contained the true age **81%** of the time (70 answered, 74 refused; target band 0.75–0.85). Typical error of the median ≈ ×2 (median \|log₂(median/truth)\| = 1.1). Old slicks read too young | coverage **0.81** (0.814 as stamped), n = 144 twins | `stage2-age-engine.md` §4; `origin.json` → `age_posterior.calibration_coverage` | "81% accurate" (it is interval coverage). Any single age as "the age". Any live-case age as validated. **Caveat to carry:** the twins were scored 17 Sept (`pipeline/drift/age_calibration.json`, `a8cff2f`), before the 0.25 h grid (D53) and the information-gain fusion (D54); the 0.814 in each bundle is that run's figure, not a re-measurement |
| The release window is that 80% interval in UTC, method `age` on all six primaries and all four secondary groups. The map's rewind **rests on the posterior median** and the band stays draggable | per-case table | `origin.json` → `time_window`, `time_window_method`, `age_posterior.median`; playback rule in commit `eb274d9` | "measured (convergence) 8.3 h" (Jacksonville), "measured 2.0 h" (Alaska), "measured 2.3 h" (Huntington), "bounded 16 h bracket" (Farallones, Jamnagar, Mumbai), "48 h bracket": all superseded. "Age: not estimated" and "the gate is that no detection is `acute`" (pre-D45). "On Huntington the engine declined to give an age" (17 Sept, before D54; the bundle now carries one) |
| Direction arrows on **Jacksonville and Farallones only** (the only two direction-stable cases: 1° and 0° across sampling, 0° and 2° across the wind-coefficient range) | — | `stage2-numbers.md` §8.8 (measured 13 Sept on the 24 h window, not re-measured on the age windows) | arrows on Huntington (143° reversal), Mumbai, Jamnagar |
| `wind_share` is a display-only 0–1 fraction of the drift (D38). **Only Jamnagar (0.567)** crosses the 0.50 level at which `run.py` prints its wind-dominated warning; Farallones, Alaska and Huntington sit at 0.40–0.45, Mumbai 0.38, Jacksonville 0.05 | per-case table | `origin.json` → `wind_share`; threshold `pipeline/drift/mix_tests.py:85` | "Alaska and Jamnagar are wind-driven". Alaska "wind_share 0.73" (still in its `meta.notes`, stale) or Jamnagar 0.62. The §8.8 field-sample shares (Alaska 81%, Jamnagar 59%) beside `wind_share`: they measure a different thing. An error budget as universal |
| One trace per **spill group** (D35, D56), and the seed is recorded in `meta.notes` / `meta.spill_groups`. Jacksonville merges three oil features (7.12 km²) into one ribbon; Alaska and Mumbai each carry three groups, each dated on its own slick | — | `meta.json` → `spill_groups`, `notes` "D35 seed" | "trace this slick" per click / "selecting a detection re-traces it". "Mumbai's trace uses 1.48 of 9.55 km²" as the whole story (true of the primary only; the other two groups now carry their own trace) |
| Forward drift, +24 h, published on **two** cases | Jacksonville: r50 **16.2** / r90 **35.5 km**, centroid displaced **137.0 km**. Farallones: **5.7 / 9.1 km**, **27.0 km**. Both: 0% stranded, `first_landfall_hours: null` (no landfall within 24 h), 50 runs × 3000 particles | `forward_impact.json` → `envelope[24]`, `centroid_displacement_km`, `first_landfall_hours`, `stranded_fraction_at_horizon` | a Jamnagar forward layer or "2.3 / 4.9 km" (file removed 22 Sept in `cf75393`: HYCOM's horizon doesn't reach far enough past that t0, and the file that had shipped was Mumbai's run). Any horizon beyond 24 h. "No assets at risk" (`assets_at_risk` is `null`: not measured, not empty) |

---

## Stage 3: attribute

Per case, from the published `suspects.json`. The funnel is
`in_region → in_window → plausible → scored`.

| case | `ais_source` | funnel | named | outcome | evidence breadth (per named suspect) |
|---|---|---|---|---|---|
| Jacksonville | `noaa_dense` | 38 → 22 → 3 → 3 (1 short track dropped) | 3 | `ranking_confidence` **low**, separation 3.0% | 4 of 7, `weight_live` 0.765 |
| Farallones | `noaa_dense` | 12 → 7 → 2 → 2 | 2 | **high**, separation 62.7% | 4 of 7, 0.765 |
| Gulf of Alaska | `gfw_hourly` | 14 → 2 → 0 → 0 (11 non-vessel identities dropped at ingest) | 0 | **abstains**: "no vessel entered the reconstructed origin during the window" | — |
| Huntington | `noaa_dense` | 686 → 587 → 7 → 3 (17 short tracks dropped) | 3 | **high**, separation 29.4% | 5 of 7, 0.824 |
| Jamnagar | `gfw_hourly` | 111 → 102 → 10 → 3 (2 short, 1 non-vessel) | 3 | **low**: rests on 2 of 7 components | 2 of 7, 0.35 |
| Mumbai | `gfw_hourly` | 74 → 65 → 14 → 3 (3 short, 1 non-vessel) | 3 | **low**: rests on 2 of 7 components | 2 of 7, 0.35 |

**Abstentions: 1 of 6** (Gulf of Alaska). Source: `suspects.json` → `funnel`, `abstained`,
`abstain_reason`, `ranking_confidence`, `suspects[].components_available`, `weight_live`.
`infrastructure` is `[]` on all six.

| Say | Number | Source | Never say |
|---|---|---|---|
| The system names ranked suspects whenever any are plausible, and says how confident the **ordering** is (D49). It refuses only when there is nothing to rank: no AIS, an empty search, or Stage 2's own cloud too diffuse | `level` + `separation` per case, table above | `suspects.json` → `ranking_confidence`; Master D49 | a named suspect as an identification. "High confidence" as guilt, or `separation` as a probability. "Huntington abstains / names no transiting ship". "Mumbai abstains", "Jamnagar abstains", "Jamnagar has one suspect" |
| The refusal path, on a live case | Gulf of Alaska: **14 → 2 → 0 → 0, abstains**: no vessel entered the reconstructed origin during the window | `cases/case-gulf-alaska-2023/suspects.json` | The Galveston funnel **987 → 897 → 17 "then abstains, top two within 1.1%"** as current behaviour: D49 removed the tie trigger it relied on (it is in `receipts.md` and Master Part 12 only, with no committed output behind it). "Nearest candidate 9.4 km from the peak" (Alaska) and "8.3 km" (Mumbai): pre-D49/D51 |
| A buoy is not a suspect (D51): AIS identities in unassigned MID classes are dropped at ingest and counted | Gulf of Alaska: **11** dropped (`dropped_non_vessel`) | `suspects.json` → `funnel.dropped_non_vessel` | Alaska "13 vessels, 13 → 9 → 0 → 0" (D41) or "14 → 12 → 2 → 2" (17 Sept, two buoys scored) |
| Evidence breadth is shown with every score (D37) | e.g. Jacksonville 4 of 7 components live, `weight_live` 0.765 | `suspects.json` → `components_available`, `components_total`, `weight_live` | a bare score |
| `null` ≠ 0: on `gfw_hourly` cases `gap` and `slowdown` are structurally unmeasurable (D20), and `temporality` and `trajectory` are null too, because GFW publishes no speed or course. Jamnagar and Mumbai therefore score on 2 of 7 | — | Master §6.1; `suspects.json` → `components`, `component_notes` | — |
| `parity` carries no weight (D48): it has never had a centreline to measure. **Declared as a weight change made after the sealed answers were known**; scores are unchanged to the decimal | — | Master D48, Part 16.2 | that it was a tuning gain |
| AIS density on the hero case | **69 s** reporting interval, holds to 240 km offshore; position ~170 km out | `receipts.md` "AIS sampling density" | ~100 km; "gap case" (D30) |
| **Both Indian cases search real vessels** (GFW hourly, D40, thresholds per sampling regime D41) | funnels in the table above | `suspects.json` | "no AIS available in Indian waters" (our error, corrected 14 Sept). The superseded GFW extract counts: 9 vessels / 31 vessel-hours (Mumbai) and 8 / 43 (Jamnagar), both from 14 Sept and still in those cases' `meta.notes`; 42 / 386 and 38 / 255 (D41). The pre-D41 funnels 9 → 2 → 0 → 0 and 8 → 2 → 0 → 0, and the D41 funnels 42 → 29 → 0 → 0 and 38 → 22 → 1 → 1 |
| The NOAA + GFW merged pool on the US cases: its value is the **coverage-hole correction** (D50), not new candidates | GFW added 5 / 1 / 90 vessels over NOAA on the three US cases, all tugs, tenders, fishing or pleasure craft | Master Part 16.2 | "GFW found more ships" |
| Infrastructure association is built and contracted (D38) | `infrastructure: []` on all six bundles | Master §6.1; `suspects.json` → `infrastructure` | that it found the Huntington pipeline. "6.7 km" / "6.74 km" from the origin peak to NTSB's coordinate (measured on the 14 Sept origin; superseded, and verdict-adjacent) |
| Repeat offenders: in the data model, roadmap | — | A8 | a working feature |

### Radar versus transponder cross-check (D42, D57)

| case | contacts | listed as unmatched | what can be said | Never say |
|---|---|---|---|---|
| Jacksonville (`noaa_dense`) | 2, UDGAM detector | **2**, both "no AIS broadcast within 1 km at acquisition time"; one inside the origin (grid probability 0.57) | exact under a one-vessel-one-place matching (D57). **Single pass, not persistence-checked**: may be a fixed structure or a transponder outside receiver coverage | an unmatched contact as a proven dark vessel |
| Huntington (`noaa_dense`) | 43 | 0 | 43 contacts assign to **43 distinct vessels** out of 280 in the scene-time extract, exact under maximum matching (D57) | — |
| Mumbai (`gfw_hourly`) | 21 | 0 | hourly AIS cannot place a vessel, so the test is **reachability**, and one MMSI is credited with 17 of 21 contacts. A maximum matching covers only **7**; **14 cannot be jointly explained by AIS, but no individual contact can be named as dark** (D57) | "**21/21 matched**". "None is unexplained by AIS" |
| Jamnagar (`gfw_hourly`) | 3 | 0 | same reachability test as Mumbai; not re-analysed under D57 | "3/3 matched" as proof nothing is dark |
| Gulf of Alaska (`gfw_hourly`) | 0 from UDGAM; GFW's own Sentinel-1 detections used instead, labelled as GFW's | **1** GFW contact, 3.6 km from an oil detection, "no vessel in the hourly AIS record could have reached this position" | hourly AIS is weaker evidence than dense; single pass | "Alaska 2/2 matched" (D42, pre-D51: the buoys' AIS was matching it away). That UDGAM detected it. Anything using Cerulean's contact (it is the answer) |
| Farallones | 0 | 0 | — | — |

Sources: `cases/*/suspects.json` → `dark_vessels` (count, `reasons`); `cases/*/detections.geojson` →
`ship_detections`; Master D42 and D57 for the matching counts.

### Injected-offender curve (Phase 8)

> **Read before quoting any row.** Every figure here comes from
> `pipeline/attribute/results/phase8_*.json`, committed **14 Sept** (seed 143) and **not re-run
> since.** On 22 Sept `evaluate.py` was moved to the D49 meaning of abstention (`38aff35`:
> abstain = nothing plausible). The committed counts were made under the old tie, crowded and floor
> triggers. So **abstention counts describe a scorer we no longer ship**, and top-1 and top-3 are
> rates over the trials that scorer decided. Quote them as *"measured on the 14 Sept scorer"*.
> These are **ranking** numbers given an origin of stated quality: an upper bound, never accuracy
> on the six live cases.

| Say | Number | Source | Never say |
|---|---|---|---|
| **Offshore, dense AIS, 300 trials/point**, real fleet of 46 vessels, synthetic offender, cloud r90 10 km with **0.5 × r90** of origin error, 45 min gap | top-1 **0.910** [0.870–0.938], top-3 0.964, 23/300 abstained (14 Sept rules) | `phase8_jacksonville.json` → `conditions.baseline` | any of it as an accuracy figure for the six live cases |
| Origin quality sets the ceiling | perfect cloud **1.000** [0.987–1.000]; error of one r90 **0.653** [0.590–0.710] | same → `origin_err=0.0xr90`, `origin_err=1.0xr90` | — |
| A hard offender (no gap, no slowdown) | top-1 **0.556** [0.494–0.617], top-3 0.923 | same → `conditions["offender=plain"]` | quoting only the baseline |
| Crowded port, dense AIS, 150 trials, 100 real vessels, r90 3 km | top-1 **0.782** [0.702–0.846], top-3 0.960 | `phase8_huntington.json` → `conditions.baseline` | — |
| Honesty slide, ablation on the hard condition (300 trials, top-1 0.579 with everything on): removing `proximity` −0.107, `temporality` −0.067, `trajectory` **−0.051**, `type_prior` **−0.024**, `slowdown` +0.007, `parity` 0.000, `gap` **+0.143** (removing it helps when the offender never goes dark). **No weight moved on it** | — | `phase8_jacksonville_hard.json` → `ablation` | that we tuned anything on a real case. The −0.100 `type_prior` figure (leaky all-tanker generator) |
| Sampling density is the biggest lever | **not quotable from a committed file today**: see "Unsourced" | — | **0.488 / 0.296** (the hourly rows still sitting in the committed JSONs are the pre-D41 defect numbers). 0.486 / 0.398 until a JSON carrying them is committed |
| — | — | — | "It refuses as water crowds: 111 of 150 abstained" as current behaviour. D49 removed the crowded-box trigger that produced it |

---

## Blind evaluation

State it per case (Master §16.1). **Don't quote a count.** Farallones is blind on weights, not
provably on identity. Weights and thresholds were set on injected scenarios only. The two declared
exceptions to that rule from the 22 Sept re-score are written up in the **Master Part 16.2
calibration declaration**: quote that section as written and don't compress it into a number.

## Roadmap (not claimed as built)

Traffic prior (Phase 5) · repeat offenders (Phase 6) · chronic-vs-acute (Phase 7) · a slick
centreline, so `parity` has something to measure · persistence checks on radar contacts · a forward
layer for Jamnagar once the field fetch reaches past its t0.

*(Removed from the 14 Sept list because they are now built: age estimation to bound the rewind
(D45), per-group tracing (D56), GFW hourly AIS for Indian cases (D40).)*

---

## Unsourced: do not put on a slide

Each of these was on the 14 Sept sheet or is in circulation, and **cannot be traced to a committed
output that reflects the current pipeline**.

| Figure | Why it is held back |
|---|---|
| Median travel distance per case (148.7 / 35.5 / 12.0 / 6.2 / 16.7 / 16.7 km) | Measured on the 13 Sept 24 h rewind (`stage2-numbers.md` §8.4, §8.9). The current rewind is age-pooled and truncated to the age band. No bundle or metric file records a travel distance for it |
| Hourly-AIS injected-offender rates after the D41 fix: 0.486 [0.42–0.55] offshore (top-3 0.793), 0.398 [0.32–0.49] in port (top-3 0.561) | Stated in `stage3-injected-offender-curve.md` and Master D39/D41, but the committed `phase8_*.json` still carries the pre-fix 0.488 / 0.296. Re-run `evaluate.py` and commit the JSON before quoting |
| Any injected-offender figure under the current (D49) abstain rule | Not measured: `evaluate.py` was updated on 22 Sept and not re-run |
| Layer 2 "baseline 0.689 on the same split" | In `stage1-jury-numbers.md` only. No committed metric file holds it. `unet_baseline_meta.json` has a tile-level 0.690, which is a different measurement |
| `P3_No oil_00027` P(oil) 0.0004 | Only in `docs/updates/soumirya_case_nominations.md`, scored by the previous classifier. Not in the bundle |
| A Huntington N = 1 age statement under the current engine | The only written N = 1 line ("declined to give an age", `stage2-age-engine.md` §5) predates D54, and the bundle now carries an age. No committed document compares that interval with the NTSB timeline |
| Age-interval coverage for the D53/D54 engine | The 0.81 / 0.814 is from the 17 Sept twin run. The twins have not been re-scored since the 0.25 h grid and the information-gain fusion |

---

## Change log, 14 Sept → 5 Oct

### Figures replaced (each old value is now in a "Never say" cell)

| Item | 14 Sept sheet | Now | Source of the new value |
|---|---|---|---|
| Layer 1 accuracy / look-alike rejection / clean-ocean rejection / threshold | 0.951 / 0.940 / 0.987 / 0.143 | 0.942 / 0.920 / 0.980 / 0.128 (jury pair; oil recall unchanged at 0.927) | `scene_classifier_l1_e2c_recall_meta.json` |
| Layer 2 gated IoU | 0.435 on Part III (138/150) | 0.757 on validation for the slide; 0.452 on Part III for presenter notes (139/150) | `eval_val_e2c_gated_recall.json`, `eval_part3_e2c.json` |
| Cerulean agreement | n = 5 only | n = 5 (0.483) and the slide's n = 4 (0.553), each stated with its n | `iou_cerulean.json`, `stage1-jury-numbers.md` |
| Zenodo no-spill case | (implicit) `00091`, P(oil) 0.0003 | `00027`, 0 features, 0 contacts | `cases/case-nospill-zenodo/` |
| Radar contacts | Ennore 72, Zenodo 1 and 31, total 142 | Ennore 41, Zenodo 0 and 0, total 110 | `detections.geojson` `ship_detections` |
| Jacksonville r50 / r90 / window | 13.1 / 31.1 km, "measured (convergence) 8.3 h" | 12.3 / 28.98 km, 13:13:59Z–23:13:59Z (`age`, 80% band 0.125–10.125 h) | `origin.json` |
| Farallones | 4.4 / 8.8 km, bounded 16 h | 5.11 / 11.22 km, `age` 0.125–15.125 h | `origin.json` |
| Gulf of Alaska | 1.4 / 2.6 km, wind 0.73, measured 2.0 h | 1.07 / 2.29 km, wind 0.4494, `age` 0.125–7.625 h | `origin.json` |
| Huntington | 1.4 / 2.5 km, wind 0.38, measured 2.3 h | 2.18 / 4.59 km, wind 0.401, `age` 0.125–17.875 h | `origin.json` |
| Jamnagar | 2.3 / 3.7 km, wind 0.62, bounded 16 h | 2.81 / 5.21 km, wind 0.567, `age` 0.125–14.125 h | `origin.json` |
| Mumbai | 2.0 / 3.7 km, wind 0.37, bounded 16 h | 2.57 / 4.73 km, wind 0.376, `age` 0.125–14.875 h | `origin.json` |
| Median travel column | 148.7 / 35.5 / 12.0 / 6.2 / 16.7 / 16.7 km | removed (Unsourced) | — |
| Wind-driven cases | Alaska and Jamnagar | Jamnagar only crosses 0.50 | `origin.json` `wind_share`; `mix_tests.py:85` |
| Age | "not estimated" | 80% interval on all six; 0.81 coverage on 144 twins | `origin.json` `age_posterior`; `stage2-age-engine.md` §4 |
| Forward drift | (not on sheet; D44 listed three cases) | two cases; Jamnagar's file removed | `forward_impact.json` |
| Huntington Stage 3 | 106 → 75 → 5, abstains | 686 → 587 → 7 → 3, names 3, high | `suspects.json` |
| Mumbai Stage 3 | 42 → 29 → 0 → 0, abstains | 74 → 65 → 14 → 3, names 3, low | `suspects.json` |
| Jamnagar Stage 3 | 38 → 22 → 1 → 1, one suspect | 111 → 102 → 10 → 3, names 3, low | `suspects.json` |
| Gulf of Alaska Stage 3 | 13 → 9 → 0 → 0, abstains | 14 → 2 → 0 → 0, abstains, 11 non-vessels dropped | `suspects.json` |
| Refusal-path example | Galveston 987 → 897 → 17 tie | Gulf of Alaska, live case | `suspects.json`; D49 |
| Dark-vessel cross-check | Jacksonville 2 unmatched; Huntington 43/43, Mumbai 21/21, Jamnagar 3/3, Alaska 2/2 matched | Jacksonville 2 listed; Huntington 43 exact; Mumbai: max matching 7 of 21, none nameable; Jamnagar 3 (reachability only); Alaska 1 GFW contact listed | `suspects.json` `dark_vessels`; D57 |
| Hourly injected-offender rows | 0.486 / 0.398 | held back (Unsourced): committed JSON holds 0.488 / 0.296 | `phase8_*.json` |
| Injected-offender abstention | presented as current | flagged: measured under pre-D49 rules | `38aff35` |

### Conflicts between sources, and how each was resolved

1. **Bundle prose against bundle fields** (field wins; the notes should be fixed in the producing code, not by hand):
   `case-gulf-alaska-2023/meta.json` notes "wind_share 0.73" against `origin.json` 0.4494;
   `case-mumbai-2023` and `case-jamnagar-2024` notes give the 14 Sept GFW funnels (9 → 2 → 0 → 0,
   8 → 2 → 0 → 0, "abstains") against `suspects.json`; `case-huntington-2021` notes "Stage 3 abstains
   on vessels" and "~6.7 km from NTSB's casualty location" against `suspects.json` (`abstained: false`)
   and a re-centred origin; `case-lookalike-zenodo` notes "1 contact" against `ship_detections: []`.
2. **Bundles against `stage2-numbers.md` §8.9** (13 Sept, 24 h rewind) and **`stage2-age-engine.md` §5**
   (17 Sept): every r50/r90/window differs. Bundle wins.
3. **Bundles against Master D42** ("21/21, 3/3, 2/2 matched") and **D41** (funnels): bundle and the later D51/D57 win.
4. **Bundles against `receipts.md`** for contact counts (72 / 1 / 31), the no-spill tile (00091), the
   Indian-case GFW tables and the Galveston abstention: bundle wins; receipts is lowest precedence.
5. **Committed `phase8_*.json` (0.488 / 0.296) against `stage3-injected-offender-curve.md` and D39/D41
   (0.486 / 0.398).** Precedence says the JSON wins, but the decision log records the JSON values as
   a defect's output. Neither is cleared: the JSON values are "Never say" and the doc values are
   Unsourced until re-run.
6. **Two Layer 1 metric files, both committed:** `eval_part3.json` (previous pair, 0.951) and
   `eval_part3_e2c.json` (jury pair, 0.942). Not a contradiction, since they are two models. The deck
   follows `stage1-jury-numbers.md` and presents the jury pair; `receipts.md` still quotes the previous one.
7. **Master D44** lists a Jamnagar forward layer; the bundle has none (`cf75393`). Bundle wins.
