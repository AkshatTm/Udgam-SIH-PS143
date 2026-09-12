# RECEIPTS — provenance for every number and pixel we show

*Owner: Akshat. Must be complete before the freeze.*

**Why this file exists:** a judge asks "is this real data?" and the answer has to be a scene id
on screen within five seconds, not a story. Internals are binding — whatever we show on
15 September we defend in December before an NTRO panel.

`TODO` below means genuinely not filled in yet. Do not delete a TODO by guessing.

---

## Sentinel-1 SAR scenes (Google Earth Engine, `COPERNICUS/S1_GRD`)

**All seven scene ids below are full and confirmed.** Every one was verified against GEE with
`bandNames()` on 2026-09-12: all carry `['VV', 'VH', 'angle']`, so no case runs VV-only.

| # | Case | `system:index` | Acquired (UTC) | Mode / pol / pass | Notes |
|---|---|---|---|---|---|
| 1 | case-jacksonville-2024 | `S1A_IW_GRDH_1SDV_20240730T232129_20240730T232154_054997_06B32C_7973` | 2024-07-30 23:21:29Z | IW / VV+VH / ASC, rel. orbit 150 | HERO. Open ocean ~170 km offshore. **Long sinuous chronic slick**, full scene height. Cerulean slick 3046293 (31.17 km, 4.55 km²). |
| 2 | case-farallones-2023 | `S1A_IW_GRDH_1SDV_20230317T142442_20230317T142507_047685_05BA4D_AFD8` | 2023-03-17 14:24:42Z | IW / VV+VH / DESC, rel. orbit 13 | **Ruler-straight discharge line** NW–SE. Cerulean slick 3687325 (19.63 km, 3.85 km²). Three other slicks share this scene — ours is the 19.6 km one. |
| 3 | case-huntington-2021 | `S1A_IW_GRDH_1SDV_20211002T015821_20211002T015850_039934_04B9C9_2BF9` | 2021-10-02 01:58:21Z | IW / VV+VH / ASC, rel. orbit 137 | +0.1 d after first alarm (1 Oct 23:10Z). **Clear comma-shaped slick**, ~8–10 dB VV depression. Not in Cerulean — NTSB is its ground truth. |
| 4 | case-gulf-alaska-2023 | `S1A_IW_GRDH_1SDV_20230516T155708_20230516T155736_048561_05D74A_DCBF` | 2023-05-16 15:57:08Z | IW / VV+VH / DESC, rel. orbit 14 | Dark-vessel cross-check. Cerulean slick 3630124 (2.48 km, 0.27 km²), **human-reviewed as `AMBIGUOUS`** — stated openly, see Master §3.2. |
| 5 | case-mumbai-2023 | `S1A_IW_GRDH_1SDV_20230903T010333_20230903T010358_050156_06095B_9215` | 2023-09-03 01:03:33Z | IW / VV+VH / DESC, rel. orbit 34 | Dark slick with broad head + long tail, plus **bright point targets** (ships/platforms). Cerulean slick 3612640 (20.55 km, 7.74 km²). |
| 6 | case-jamnagar-2024 | `S1A_IW_GRDH_1SDV_20240223T011114_20240223T011139_052679_065FA4_546D` | 2024-02-23 01:11:14Z | IW / VV+VH / DESC, rel. orbit 107 | **Hook-shaped slick**, found independently in GEE. Measured: slick VV −25.41 / VH −47.36; clean water VV −17.24 / VH −33.12 → ~8 dB VV depression. Cerulean also logged it (3477622). |
| 7 | case-ennore-lookalike-2023 | `S1A_IW_GRDH_1SDV_20231130T003201_20231130T003226_051439_06353D_343D` | 2023-11-30 00:32:01Z | IW / VV+VH / DESC | **−3.98 d before** the 4 Dec 2023 CPCL spill. `find_scenes.py` over 2023-11-20..12-10 returned **exactly one pass** in twenty days. Chennai coast, anchored vessels, dark low-wind patches that cannot be oil. |
| 8 | case-lookalike-zenodo | `P3_Lookalike_00134` | **none — see below** | — | Zenodo Part III `Lookalike/`. **Georeferenced: W −89.6488 S 29.1688 E −89.4649 N 29.3527** — Mississippi Delta, Gulf of Mexico. Natural seeps and rigs, which is *why* it is a convincing look-alike. 47 km², −9.05 dB, elongation 21.2. Rejected at P(oil) 0.0020. |
| 9 | case-nospill-zenodo | `P3_No oil_00091` | **none — see below** | — | Zenodo Part III `No oil/`. **Georeferenced: W 36.5090 S 35.1392 E 36.6930 N 35.3232** — Gulf of İskenderun, eastern Mediterranean. Rejected at P(oil) 0.0003. |

**On rows 8 and 9 — location yes, time no.** Both tiles carry **EPSG:4326 and a real
geotransform**, so `bounds.json` holds their true boxes and nothing about their placement on the
map is invented. They carry **no acquisition timestamp** — the only TIFF tag is `AREA_OR_POINT` —
so `detection_time` stays the deliberate `1970-01-01T00:00:00Z` sentinel and `meta.notes` says so
outright. If asked: *we show you where, we do not know when, and we do not guess.*

This also killed a design assumption. `pipeline/export/benchmark_scene.py` was written believing
these scenes were ungeoreferenced and wrote a Null Island placeholder box for them; that is fixed
(13 Sept) and it now reads the transform. The **same** false premise was load-bearing in Stage
1's `scene_provenance()`, which routed to the networks on "this file has no CRS" — a test that
matched every scene in both corpora and therefore discriminated nothing. Replaced by the explicit
`meta.provenance` field (Master §6.1, D33).

**dB clamps for these two are per-scene from their own P2/P98**, like every other case, and
neither is the default: `case-lookalike-zenodo` `[-31, -16]` · `case-nospill-zenodo` `[-28, -14]`.

**Archived:** `case-ennore-2017` — `S1A_IW_GRDH_1SDV_20170129T003132_20170129T003157_015039_01892E_6D04`,
2017-01-29 00:31:32Z, +1.0 d, dawn low-wind, **no clear slick in GRD**. Moved to `cases/_archive/`
pending the SLC retry that decision D18 requires. **Dropped entirely:** `case-golden-ray-2021` (D17).

Export settings actually used (these must match what `bounds.json` records):
- `sar_vv_vh.tif`: **2-band float32 GeoTIFF, dB, unclamped**, `--tif-scale 10` m/px on every case — Soum's real input. Band 1 = VV, band 2 = VH, labelled in the file. **Nodata is `-inf`, not a low dB value** — Jamnagar and Farallones have scene-edge nodata (86% and 82% coverage); treating it as backscatter would read as a huge false slick.
- `sar.png` / `thumb.png`: band **VV**, dB-clamped 8-bit, `--png-scale 25` m/px — display only.
- **The dB clamp is per case and derived, not guessed.** Each was taken from that box's own VV percentiles sampled in GEE at 60 m, then rounded: jacksonville `[-32, -19]` · farallones `[-28, -14]` · huntington `[-25, -5]` · gulf-alaska `[-29, -14]` · mumbai `[-28, -15]` · jamnagar `[-26, -13]` · ennore-lookalike `[-27, 0]` (wider because the box contains the Chennai coast, where land runs to +4 dB). Recorded per case in `bounds.json` as `db_min`/`db_max`. **Changing one is a broadcast, not a silent edit.**
- `bounds.json` also records `vh_available` — `true` on all seven. **`vh_available` means the
  band is present, NOT that it carries signal.** See the VH note below; do not read that `true`
  as evidence the dual-pol method fired.

**VH is below the sensor noise floor on all seven live cases** (Soum, 13 Sept). Measured sea VH
runs **−27.0 to −38.5 dB** against an IW noise-equivalent sigma-zero of **≈ −24 dB** — so what is
in band 2 on those scenes is thermal noise, not ocean backscatter. This is a property of IW mode
over calm water at C-band, not a fault in our export: it is **universal, not per-case**, and no
choice of scene from GEE would have avoided it.

**Consequence for the deck — the VH slide must be reframed, not deleted.** The dual-pol novelty
is real and measurable **on the Zenodo corpus** (sea VH −20.7 dB, and both newly accepted scenes
are usable at −21.9 and −11.6 dB) and **inoperative on every scene we will actually show**. That
contrast is what makes this a finding rather than a retreat: we can state precisely where the
method works, where it does not, and why — which is a stronger claim than an unqualified one, and
it is the version that survives a question from someone who knows what NESZ is. Urooz: the slide
says *"VH adds discrimination where VH clears the noise floor; on IW over calm sea it does not,
and we show you the numbers."* **Do not let a slide imply VH contributed to the seven live
detections.** It did not.
- Export boxes are the Cerulean slick polygon's own bbox padded 0.03–0.05°, then adjusted where the scene footprint cut into the box. They are recorded in each `meta.json`.
- **GEE's direct-download ceiling is 50,331,648 bytes (48 MiB)**, and the request is billed at **5 bytes per band-pixel** (float32 + a 1-byte validity mask). A GeoTIFF exported in EPSG:4326 has **no cos(lat) term** — the degree step is `scale / 111320` on both axes — so a high-latitude box is ~1/cos(lat) larger than a ground-square estimate suggests. `gee_scene.py` now predicts the exact raster.
- command: `python pipeline/export/gee_scene.py --project quizzer-dev-487316 --scene <index> --case <id> --bbox W S E N --png-scale 25 --db-min <m> --db-max <M>`
- generalised finder: `python scripts/find_scenes.py --project <id> --bbox W S E N --start <d> --end <d> [--incident <d>]`

## SkyTruth Cerulean (case onboarding + segmentation reference)

Public OGC Features API, **no key, no authentication**: `https://api.cerulean.skytruth.org`,
collection `public.slick_plus`. Wrapped by `scripts/fetch_cerulean.py`. Fetched 2026-09-12.

Each bundle carries `cerulean_slick.geojson` — their polygon plus centerline for the same
feature. It is a **comparison target for Stage 1, not ground truth and not a NAAP detection**,
and it ships with that wording inside the file. Cerulean themselves state that SAR alone cannot
definitively identify oil slicks and that detections are *potential* slicks; we repeat that.

Source attribution returned by the same API is **deliberately excluded from every bundle** and
lives only in the sealed `docs/ANSWERS.md` (Master Part 16, D21).

`public.slick_to_source`, `public.source_vessel` and `public.source_type` return **403** — vessel
names, flags and IMOs are not available through the API and come from the per-slick web page.

## Global Fishing Watch (cases 5 and 6 only)

API v3, `gateway.api.globalfishingwatch.org`. **Free, self-registration, NON-COMMERCIAL USE
ONLY** — that condition is real and belongs on the data-provenance slide. Token in `.env` as
`GFW_API_TOKEN`, gitignored. Probed 2026-09-12 with `scripts/gfw_probe.py --all`:

| Case | Date | Presence | AIS-disabling events | SAR presence |
|---|---|---|---|---|
| case-mumbai-2023 | 2023-09-03 | ✅ responds | ✅ 10,992 returned (global, unfiltered) | ✅ responds |
| case-jamnagar-2024 | 2024-02-23 | ✅ responds | ✅ 9,638 returned (global, unfiltered) | ✅ responds |

**Cases 5 and 6 keep `attribute`.** `gap` and `slowdown` still come back `null` — that is hourly
sampling (D20), not a coverage failure, and the card says "n/a".

⚠️ **A false negative we nearly recorded here.** The first probe returned HTTP 403 on every
endpoint and the script concluded *"no usable GFW coverage — cases 5 and 6 drop to detect+trace."*
It was **Cloudflare error 1010, "browser signature banned"** — the gateway rejecting urllib's
default `Python-urllib/3.11` user-agent. A transport failure, saying nothing about the token or
the data. Sending a normal user-agent returned all three endpoints. **Two demo cases were one
unexamined error message away from being dropped for no reason.** `gfw_probe.py` now names that
error explicitly rather than folding it into a coverage verdict.

## Ocean and atmosphere (Google Earth Engine)

| What | Collection | Bands | Note |
|---|---|---|---|
| Currents | `HYCOM/sea_water_velocity` | `velocity_u_0`, `velocity_v_0` | **Scaled integer: catalog units m/s, scale 0.001 — divided by 1000.** Daily (24 h cadence), 0.08°, ends 2024-09-05 in GEE. Ennore field: median 0.48 m/s, max 1.10 m/s |
| Wind | `ECMWF/ERA5/HOURLY` | `u_component_of_wind_10m`, `v_component_of_wind_10m` | signed components, not speed/bearing |

Drift physics: surface oil moves at current + **3%** of wind speed (the "3% rule"), RK2,
dt = 15 min, **50**-run ensemble. Field cache: `data/fields/<case>.npz` — `TODO` confirm which
time span was pulled per case.

## Training data

**Zenodo oil-spill dataset, Part III** — DOI [10.5281/zenodo.13761290](https://doi.org/10.5281/zenodo.13761290)
- Licence **CC-BY** → **must be cited on a slide.** (Urooz: data-provenance slide.)
- 150 oil + 150 look-alike + 150 no-oil scenes, 2048×2048×2 (VV, VH) GeoTIFF in dB, plus masks.
- Part I (DOI 10.5281/zenodo.8346860, 40.7 GB) downloaded for the October CNN work. **Not used
  in this sprint** — do not claim it was.

## Detection accuracy — the honesty slide

Measured by Soum on a **scene-level** held-out split (the Zenodo Part III designated test set —
never a row-level split, because regions from one 2048×2048 scene are correlated and a row
split would flatter us). See Master Plan Part 12.

| Metric | Value | Split |
|---|---|---|
| Decision threshold | **0.143** | chosen on validation, never on Part III |
| Scene classification accuracy | **0.951** | all 450 Part III scenes |
| Look-alike rejection rate | **0.940** | all 450 Part III scenes |
| Clean-ocean rejection rate | **0.987** | all 450 Part III scenes |
| Oil recall | **0.927** | all 450 Part III scenes |
| Oil-class IoU (positives only) | `TODO` | Part III holdout |
| Classical baseline F1 (ablation) | `TODO` | same holdout |
| Training rows | `TODO` | `data/labels/features.csv` |

**Provenance of these five numbers** (Soum, 13 Sept). Trained on Parts I+II with an 85/15
by-scene validation split; evaluated on all 450 Part III scenes. **Both the threshold and the
architecture were chosen on validation, never on Part III** — that is what makes the row above a
held-out number and not a tuned one. Layers 1 and 2 are evaluated on the scene cache
(`data/cache/scenes_P3.npy` + `manifest_P3.json`).

**Two corrections, recorded because the wrong versions circulated first and may be in a draft
deck.** Both are on us to catch, not the judges.

- **0.960 / 0.987 / 0.434 are dead.** They are the pre-domain-augmentation classifier. The
  shipped model is the table above; in particular the **threshold is 0.143, not 0.434**. If a
  slide still says 0.434, it is describing a model we are not running.
- **These did not come from `features_test.csv`.** That CSV is the *classical* RandomForest's
  row-level feature table. It is a different artefact from the scene cache, and the two must not
  be conflated in the deck even though both are Part III, both scene-level, and neither was
  trained on. Two models, two evidence files; say which one a number came from.

**Reproducibility, stated at its real boundary.** A clean checkout **cannot** reproduce these,
and never will: the inputs are 40+ GB of Zenodo archives and `data/` is gitignored. What ships is
the code, the eval JSONs (`eval_part3.json`, `scene_classifier_meta.json`, `model_meta.json`) and
the small weights. The 204 MB / 121 MB artefacts are deliberately not in the repo — over GitHub's
100 MB blob limit, and a 300-tree unbounded RandomForest is cheaper to retrain than to store.
This is the same rule as everywhere else in the project: **outputs move, inputs stay put.** Say
it in exactly those terms if asked; it is a design decision, not a gap.

**Live check on the two accepted Zenodo cases**, at threshold 0.143: `00134` → P(oil) **0.0020**,
`00091` → P(oil) **0.0003**. Both correctly rejected.

**The two-benchmark framing (Master Plan Part 10 + Part 12).** The ~53% IoU figure that
circulates is from the **Krestenitis** 5-class benchmark — the EMSA CleanSeaNet dataset, which
is not openly available and is **not our dataset**. Our dataset's own authors (Trujillo-Acatitla
et al., *Mar Pollut Bull* 204:116549, 2024) report **99% classification accuracy and 96% IoU**
on their own designated test set. We report X on that same held-out split. The gap between 96%
and ~53% measures **how much look-alike variety a dataset contains — not model quality**. That
gap is our result, not our excuse. This is also why the system does not rest on detection alone:
drift and AIS are independent evidence streams.

## AIS (NOAA Marine Cadastre)

Source: `coast.noaa.gov/htdata/CMSP/AISDataHandler/` — no registration required.

| Case | Files used | Date range | Rows after bbox+time filter |
|---|---|---|---|
| case-jacksonville-2024 | `AIS_2024_07_30`, `AIS_2024_07_31` | 30–31 Jul 2024 | 52 vessels in the scoring window |
| others | `TODO` | `TODO` | `TODO` |

### AIS sampling density — measured, not assumed (2026-09-12)

This is a number we cite on the sampling-density slide, so it needs a receipt.

| What | Measured |
|---|---|
| Where | `case-jacksonville-2024`, 30.384 N −79.634 W — **~170 km offshore** (earlier drafts said ~100 km; that was wrong) |
| Method | NOAA Marine Cadastre for 30–31 Jul 2024, filtered to a box running **40 km to 260 km offshore** |
| **Reporting interval** | **69 seconds**, and it **holds out to 240 km** — no thinning with distance |
| Cross-check | Matches the Galveston baseline from the same pipeline |
| Consequence | The offshore-coverage risk on the hero case is **closed**. Nothing reshuffles. |

**Coverage of the documented vessel inside Cerulean's own −8 h/+6 h window:** 714 broadcasts
covering **14.0 hours of 14**, longest silence **130 seconds**, no hole at either end. That is why
case 1 is **not** a gap case (D30) — the claim it once carried was measurably false.

**Refusal path, demonstrated on real data:** on real Galveston AIS the funnel runs
**987 → 897 → 17** and the scorer **abstains**, top two within 1.1%. Correct behaviour on a patch of
ocean with no spill in it.

Known limitation we state openly: **MMSI is an imperfect identifier** — reused, spoofed,
sometimes zero. We group by MMSI as-is and do not attempt identity resolution. One demo case.

## Incident references

**Ennore, 28 January 2017** — collision between MT Dawn Kanchipuram and MT Maple off Kamarajar
(Ennore) Port, Chennai; heavy fuel oil released, extensive shoreline impact.
- `TODO` — paste 2–3 citable references (news / Coast Guard / NGT report) with URLs.

**Huntington Beach / San Pedro Bay Pipeline, 1–2 October 2021** — pipeline P00547 (operator
Amplify Energy / Beta Offshore) ruptured ~4.5 nm off Huntington Beach; 588 barrels of crude,
~$160M damage. NTSB (MIR-24-01) probable cause: anchorage proximity — the containerships
**MSC DANIT** (IMO 9404649) and **Beijing** dragged anchor and struck the pipeline on
25 Jan 2021; fatigue cracks grew and it leaked ~9 months later. Delayed shutdown by Beta
Offshore controllers increased the volume.
- NTSB MIR-24-01: https://www.ntsb.gov/investigations/AccidentReports/Reports/MIR2401.pdf
- NOAA DARRP case: https://darrp.noaa.gov/oil-spills/pipeline-p00547-huntington-beach-oil-spill
- USGS federal investigation summary: https://www.usgs.gov/centers/pcmsc/news/collaborative-federal-investigation-reveals-cause-huntington-oil-spill

**Golden Ray, St Simons Sound, Georgia, 31 July 2021** — oil flushed from the capsized car
carrier Golden Ray (IMO 9339722) during salvage lifting of Section Six; tidal flows carried it
onto St Simons and Jekyll Island beaches and marsh. Capsizing cause: NTSB MAR-21/01 (chief
officer's ballast-entry error → inadequate stability). Salvage operator T&T Salvage / VB-10000.
- NTSB MAR-21/01: https://www.ntsb.gov/investigations/AccidentReports/Reports/MAR2101.pdf
- Georgia Public Broadcasting coverage (31 Jul–6 Aug 2021): https://www.gpb.org/news/2021/08/06/changing-tides-spread-oil-golden-ray-wreck-st-simons-beaches-marshes
- SkyTruth (published optical imagery of the plume): https://skytruth.org

**Golden Ray is dropped (D17)** and the reference block above is kept only because the archived
Ennore bundle still cites it. No Golden Ray material appears in the demo.

**Cases 1, 2, 4 and 5 (Cerulean-sourced)** — the attribution for each exists and is held in the
sealed `docs/ANSWERS.md`. When it reaches `verification.json` it carries the caveat:
*"SkyTruth Cerulean attributed this slick to vessel X"*, never *"vessel X was proven
responsible"*, and `source_type` is `algorithmic_attribution`, never `official_investigation`.

**Jamnagar, 23 February 2024 — the case whose finding is an absence.** No investigation, no
named party, no enforcement. State it that way and **never** as "no record anywhere": SkyTruth
Cerulean's detector independently logged this slick (`3477622`,
https://cerulean.skytruth.org/slicks/3477622), 0.2 km from our GEE point on the same scene, at
0.838 machine confidence, and attached four candidate vessels — every one of which their own
scorer rated below zero, with no human review. Their record is **independent corroboration that
the slick is real**; the thing that is missing is anyone acting on it. See decision D24.

**Ennore / CPCL, 4 December 2023** — oil release during Cyclone Michaung. Our case 7 is the
2023-11-30 pass, four days *before* it, used as a correct-rejection case.
- `TODO` — paste 2–3 citable references for the December 2023 CPCL release with URLs.

---

## What is synthetic in this repo, stated plainly

`cases/case-000/` and every `--stub` mode under `pipeline/` are **invented data**, used to build
and wire the system before the real pipeline existed. They are never shown to a judge, and no
number from them appears on any slide. The vessel names in them (`FAKE ATLAS`, `FAKE CORAL`, …)
are deliberately labelled so they cannot be mistaken for AIS records.

Everything else — SAR scenes, currents, winds, AIS, training imagery — is real and listed above.

**"Is this precomputed?"** Yes, deliberately, and we say so: the pipeline runs offline and
exports a case bundle; the interface plays it back. That is why the slider is instant and why it
cannot break on venue wifi.
