# RECEIPTS — provenance for every number and pixel we show

*Owner: Akshat. Must be complete before the demo.*

**Why this file exists:** a judge asks "is this real data?" and the answer has to be a scene id
on screen within five seconds, not a story. Internals are binding — whatever we show on
15 September we defend in December before an NTRO panel.

`TODO` below means genuinely not filled in yet. Do not delete a TODO by guessing.

---

## Resolved runtime environment — Stage 1 models

*Recorded 2026-09-16 by Soumirya, per Akshat's ruling on Frozen Convention 8.*

**The documentation said Python 3.11. Every model in this repository was trained and is served on
Python 3.13.5.** Nobody was running 3.11. Rather than move the models the day before the demo, the
ruling amended the docs. This block exists so the deployment container and a developer laptop are
**provably** the same environment, rather than approximately.

| component | resolved version |
|---|---|
| Python | **3.13.5** |
| torch | **2.6.0+cu124** |
| torchvision | **0.21.0+cu124** |
| CUDA (torch build) | 12.4 |
| numpy | 2.5.3 |
| scipy | 1.18.1 |
| rasterio | 1.5.1 |
| opencv (cv2) | 5.0.0 |
| scikit-learn | 1.9.0 |
| matplotlib | 3.11.1 |
| global-land-mask | 1.0.0 |

**Why it matters beyond tidiness:** the checkpoints in `pipeline/detect/models/` are
`torch.save` pickles. Loading them under a materially different torch is the class of failure that
does not raise — it returns weights that load but behave differently. `requirements.txt` and
`CLAUDE.md` were both amended to 3.13 on the same day.

**Reproduce this table:**
```bash
venv/Scripts/python.exe -c "import sys,torch,torchvision;print(sys.version.split()[0],torch.__version__,torchvision.__version__)"
```

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

**Radar contacts per case — under the ship detector's genuinely active `k_sigma = 4`** (Soumirya,
13 Sept). Commit `72064c8` claimed k=4 but `run.py` shadowed it with a literal 8.0; those earlier
counts are dead. Current: jacksonville **2** · farallones **0** · huntington **43** · gulf-alaska
**0** · mumbai **21** · jamnagar **3** · ennore-lookalike **72** · lookalike-zenodo **1** ·
nospill-zenodo **31**. The last two were silently dropped from their bundles until D34 moved
`ship_detections` to the top level of the FeatureCollection — both scenes have zero detections, so
the old per-feature shape had nowhere to put them.

**Every one of these is an unattributed radar contact, not a dark vessel** (Master §6.3, D34). A
vessel is "dark" only once an AIS cross-check at a known time finds no match — that is Stage 3's
output, not Stage 1's. The two Zenodo cases have no acquisition time, so their darkness is `null`.
The single Delta contact is a genuine return — peak −5.93 dB against a sea of −29.46 dB (σ 0.793), **29.7σ** — so something bright is there; *what* it is has not been established. Checking it against a public offshore-infrastructure dataset is the way to answer that, and has not been done.

**No edge rule, no `edge` flag** (ruled 13 Sept, on Soumirya's evidence). Only 2 of 173 contacts lie within 2 px of a raster edge, and one is Ennore's +10.27 dB, 60 px target in a working port — a border-rejection rule would spend a confident true positive to remove one doubtful contact. The usual CFAR objection to edge targets (a truncated background window) does not apply: `ships._sea_level()` takes the median and MAD over every valid pixel in the scene, so an edge contact is tested against exactly the statistics a centre-of-scene one is. The remaining doubt is identity, which the "unattributed" label already carries.

**On Zenodo scenes the ship threshold is set by the absolute floor alone.** `lookalike-zenodo`: floor −10.0 dB vs scene-relative −26.3 dB (sea + 4σ), so `k_sigma` is inert and `DEFAULT_MIN_DB` decides — a hull at, say, −12 dB on a −29 dB sea (≈ 22σ) would be missed. The floor was set on GEE exports (~−20 dB sea). Recorded as a known limitation, not tuned.

**Case 4 (Alaska) — the dark-vessel case — gets NO contact from our detector.** Scene threshold
−8.06 dB, brightest pixel −8.79 dB; reported, not tuned away. Its dark-vessel contact (4.5 km from
the slick, ~40 m) is **Cerulean's detection, not UDGAM's.** It may be shown as Cerulean's reference
and cross-checked against, but never rendered or narrated as something our detector found.

**The satellite-case rule threshold is −3.0 dB, and it is not recorded in any bundle.** It is passed
by hand (`--rule-contrast -3.0 --rule-elongation 2.5`). Since `20594df` (Soumirya, 13 Sept) omitting
either flag on the classical path is a **hard error** rather than a silent fall-through to the
Zenodo-domain −0.5, so a *forgotten* flag can no longer reach a bundle. A *different* value still
can, and the bundle would not say so. Verified after Soumirya's D34 rerun by back-solving every shipped
feature's confidence and contrast against `run.py`'s margin formula: all seven live cases resolve
to −3.0. The frontend's "clear / marginal" bands (≤ −4.5 dB / −4.5 to −3.0 dB) pin that value.

**Archived:** `case-ennore-2017` — `S1A_IW_GRDH_1SDV_20170129T003132_20170129T003157_015039_01892E_6D04`,
2017-01-29 00:31:32Z, +1.0 d, dawn low-wind, **no clear slick in GRD**. Moved to `cases/_archive/`
pending the SLC retry that decision D18 requires. **Dropped entirely:** `case-golden-ray-2021` (D17).

Export settings actually used (these must match what `bounds.json` records):
- `sar_vv_vh.tif`: **2-band float32 GeoTIFF, dB, unclamped**, `--tif-scale 10` m/px on every case — Soumirya's real input. Band 1 = VV, band 2 = VH, labelled in the file. **Nodata is `-inf`, not a low dB value** — Jamnagar and Farallones have scene-edge nodata (86% and 82% coverage); treating it as backscatter would read as a huge false slick.
- `sar.png` / `thumb.png`: band **VV**, dB-clamped 8-bit, `--png-scale 25` m/px — display only.
- **The dB clamp is per case and derived, not guessed.** Each was taken from that box's own VV percentiles sampled in GEE at 60 m, then rounded: jacksonville `[-32, -19]` · farallones `[-28, -14]` · huntington `[-25, -5]` · gulf-alaska `[-29, -14]` · mumbai `[-28, -15]` · jamnagar `[-26, -13]` · ennore-lookalike `[-27, 0]` (wider because the box contains the Chennai coast, where land runs to +4 dB). Recorded per case in `bounds.json` as `db_min`/`db_max`. **Changing one is a broadcast, not a silent edit.**
- `bounds.json` also records `vh_available` — `true` on all seven. **`vh_available` means the
  band is present, NOT that it carries signal.** See the VH note below; do not read that `true`
  as evidence the dual-pol method fired.

**VH is below the sensor noise floor on all seven live cases** (Soumirya, 13 Sept). Measured sea VH
runs **−27.0 to −38.5 dB** against an IW noise-equivalent sigma-zero of **≈ −24 dB** — so what is
in band 2 on those scenes is thermal noise, not ocean backscatter. This is a property of IW mode
over calm water at C-band, not a fault in our export: it is **universal, not per-case**, and no
choice of scene from GEE would have avoided it.

> ### ⚠ SUPERSEDED IN PART, 13 Sept (Soumirya) — read before building the VH slide
>
> The noise-floor measurement above still stands: sea VH on the seven live cases really is
> −27.0 to −38.5 dB against NESZ ≈ −24 dB. **What does NOT stand is the claim that our feature
> importances measured VH.** Zenodo tiles are **band 1 = VH, band 2 = VV** — band 1 is 8.15 dB
> darker across 297 Part III scenes, and cross-pol is always below co-pol over ocean. Our
> pipeline read band 1 as VV. So `vh_mean_depth_db` (importance 0.3155, rank 1) was computed
> from **VV**, and the channel names in every feature-importance figure are swapped.
>
> **What survives, and it is still a real result:** adding the *second polarisation* nearly
> doubled validation F1 (0.346 → 0.643) and raised Part III precision 5.8× (0.049 → 0.286) at
> **identical** recall. Dual-pol earns its place. **What must not be said:** that we measured
> *which* polarisation did it, or that our data demonstrates the Marangoni physics. The physics
> is standard and citable; our evidence for it is not, because it names the wrong channel.
>
> Safe slide sentence: *"Adding the second polarisation nearly doubles F1 and raises precision
> 5.8× at identical recall on the benchmark. On our own IW exports the cross-pol channel sits
> below the noise floor, so the live detections run co-pol only."*

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

**Licence: CC BY-SA 4.0** — SkyTruth licenses all its data sets, maps, images and related products
under Creative Commons Attribution-**ShareAlike** 4.0. Verified against their Terms of Service
14 Sept 2026. Commercial use is allowed; attribution and ShareAlike are both required, so the five
committed `cerulean_slick.geojson` files stay under that licence rather than this project's.
Details and the required citation format: `DATA_LICENSES.md`.

Each bundle carries `cerulean_slick.geojson` — their polygon plus centerline for the same
feature. It is a **comparison target for Stage 1, not ground truth and not a UDGAM detection**,
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

Re-run 2026-09-14 (same token, same result) after Jaiveer flagged that `gfw_probe.py`'s own
docstring still said "NOT yet run" — the banner was stale, not the finding; it is now corrected.
`case-mumbai-2023/meta.json` already had a scored `suspects.json`/`vessels.geojson` sitting
unused because `acts_available` had never been updated — added `attribute`, validates PASS.
**14 Sept: the ingest now exists, and both Indian cases are scored against real vessels.**
`pipeline/attribute/ingest_gfw.py` writes the same parquet schema as `ingest.py`, so nothing
downstream changed. `case-jamnagar-2024` gains `attribute`.

| Case | Vessels found | Vessel-hours | Funnel | Outcome |
|---|---|---|---|---|
| case-mumbai-2023 | 9 | 31 | 9 → 2 → 0 → 0 | abstains: **searched, and no vessel entered the origin cloud** |
| case-jamnagar-2024 | 8 | 43 | 8 → 2 → 0 → 0 | same |

That is a different and much stronger statement than the one these cases carried this morning,
which was "nothing was searched".

**15 Sept — superseded by D41. Do not quote the funnels above.** Those extracts were padded by
`2 × r90` (~7 km) and then filtered by a track-length rule written for 69-second NOAA data, so
most vessels were dropped before they were scored. With the pad floored at 30 km and the
thresholds keyed to the sampling regime, the same three cases look like this:

| Case | Vessels | Vessel-hours | Funnel | Outcome |
|---|---|---|---|---|
| case-mumbai-2023 | 42 | 386 | 42 → 29 → 0 → 0 | abstains — nearest candidate 8.3 km from the origin peak, at zero grid probability |
| case-jamnagar-2024 | 38 | 255 | 38 → 22 → 1 → 1 | **one suspect**, scored on 2 of 7 components (hourly sampling nulls the rest) |
| case-gulf-alaska-2023 | 13 | 45 | 13 → 9 → 0 → 0 | abstains — nearest candidate 9.4 km from the peak. NOAA has no data at 59.5 N; GFW is global |

Scene-time extracts for the dark-vessel check (`*_scene.parquet`, scene box + 30 km, acquisition
± 2 h): Mumbai 74 vessel-hours / 21 MMSI, Jamnagar 49 / 16, Gulf of Alaska 16 / 8.

### GFW Sentinel-1 vessel detections — used on one case, labelled on screen

`public-global-sar-presence` via the same 4wings report endpoint
(`pipeline/attribute/ingest_gfw_sar.py`). Used **only** on `case-gulf-alaska-2023`, where our own
ship detector finds no contact (threshold −8.06 dB against a brightest water pixel of −8.79 dB;
Soumirya refused to lower it to manufacture one). It returns **2 detections on that pass**, both
within 15 s of the scene time; our own AIS cross-check matched both. Three rules hold here:
GFW's own AIS identity match is **discarded** and ours is run instead; every card built from these
says the contact is GFW's and **not UDGAM's detector**; and **Cerulean's dark-vessel contact is
never used** — it is the answer (D34, D42).

⚠️ **A claim of ours that was wrong, corrected.** This section and `gfw_probe.py` both said GFW
"does not provide individual vessel positions". That is what GFW's documentation says about the
**map layer**, and we generalised it to the whole API. The 4wings **report** endpoint, at
`spatial-resolution=HIGH`, `temporal-resolution=HOURLY`, `spatial-aggregation=false` and
`group-by=VESSEL_ID`, returns one row per vessel per hour carrying `mmsi`, `shipName`,
`vesselType`, `flag`, `imo`, `lat` and `lon`. We had ruled out a data source on a documentation
sentence rather than on a request.

**What these positions are:** grid-cell centres at 0.01° (~1 km), one per hour. **`sog` and `cog`
are not published there and are written NULL, never derived** — a course taken between two 1 km
cell centres an hour apart is not a measurement. `gap` and `slowdown` gate to `null` on any
`gfw_hourly` case anyway (D20), and `trajectory` gates to null without a course.

⚠️ **A false negative we nearly recorded here.** The first probe returned HTTP 403 on every
endpoint and the script concluded *"no usable GFW coverage — cases 5 and 6 drop to detect+trace."*
It was **Cloudflare error 1010, "browser signature banned"** — the gateway rejecting urllib's
default `Python-urllib/3.11` user-agent. A transport failure, saying nothing about the token or
the data. Sending a normal user-agent returned all three endpoints. **Two demo cases were one
unexamined error message away from being dropped for no reason.** `gfw_probe.py` now names that
error explicitly rather than folding it into a coverage verdict.

## Rebuilding every AIS extract from scratch

`data/` is gitignored and never moves between laptops, so the extracts above are reproducible
rather than shipped. On a machine with the NOAA daily **zips** in `data/ais/` and `GFW_API_TOKEN`
in `.env`:

```bash
python scripts/run_attribute_all.py --refresh     # unzips, ingests, scores, validates all six
```

It expands each NOAA zip once into `data/ais/_csv/` (about 1 GB per day), writes both extracts per
case, fetches the GFW hourly extracts and the Alaska SAR contacts, runs `score.py` into each
bundle and then the validator. Without `--refresh` it reuses whatever is already in `data/ais/`.
The NOAA zips come from `coast.noaa.gov/htdata/CMSP/AISDataHandler/<year>/` and are the only
manual download.

## Ocean and atmosphere (Google Earth Engine)

| What | Collection | Bands | Note |
|---|---|---|---|
| Currents | `HYCOM/sea_water_velocity` | `velocity_u_0`, `velocity_v_0` | **Scaled integer: catalog units m/s, scale 0.001 — divided by 1000.** 0.08°, ends 2024-09-05 in GEE. **Cadence varies by case and era:** the Ennore 2017 cache held daily snapshots; Jacksonville's holds ten at **3-hour** spacing (Anushka, `docs/evaluation/stage2-numbers.md` §8.5). Check per case; do not quote "daily" as a rule. Ennore field: median 0.48 m/s, max 1.10 m/s |
| Wind | `ECMWF/ERA5/HOURLY` | `u_component_of_wind_10m`, `v_component_of_wind_10m` | signed components, not speed/bearing |

Drift physics: surface oil moves at current + **3%** of wind speed (the "3% rule"), RK2,
dt = 15 min, **50**-run ensemble. Field cache: `data/fields/<case>.npz` — `TODO` (still open 14 Sept: the caches are
not on Akshat's machine, so per-case HYCOM cadence can only be read on Anushka's) confirm which
time span was pulled per case (Anushka: the caches live on her machine; she refetched all six
with `--forward-hours 24` so each brackets t0).

**Independent-implementation check — OpenDrift (Anushka, `docs/_archive/anushka/docs/evaluation/stage2-numbers.md` §8.4).**
**Quote the real case, not the fixture:** on `case-jacksonville-2024` the origin centroids are
**550 m apart after a 140 km rewind** (0.39% of path). Across all six spill cases the separation is 0.26–1.05% of
path. Huntington is the worst at 1.05%, on 6.2 km of travel with a weak current and a 53% land field.
**The 118 m figure below is the synthetic `case-000` fixture and must never be quoted as a real-case number.**
On `case-000`, 3000 particles, 24 h backward, our RK2 against OpenDrift's RK4 on the identical cached
field: origin centroids **118 m** apart, median per-particle disagreement **161 m**, worst of 3000
**958 m**, against our own r50 of 8.84 km. OpenDrift's own landmask, vertical mixing, Stokes drift
and diffusivity were switched off so only the integrator differs. Reproduce with
`python pipeline/drift/opendrift_compare.py` in an environment with OpenDrift installed (it is
deliberately not in `requirements.txt`; the version used is printed by the script and saved in its
output). **Proves the physics implementation, not the answer** — there is no ground truth for
origin position on any case.

## Training data

**Zenodo oil-spill dataset, Part III** — DOI [10.5281/zenodo.13761290](https://doi.org/10.5281/zenodo.13761290)
- Full title: *Sentinel-1 SAR Oil spill image dataset for train, validate, and test deep learning
  models. Part III.*
- Authors: **Trujillo-Acatitla, Rubicel; Tuxpan-Vargas, José; Ovando-Vázquez, Cesaré;
  Monterrubio-Martínez, Erandi.** Verified against the Zenodo record 14 Sept 2026 — previously
  only "Trujillo-Acatitla et al." was recorded here.
- Dataset paper: *Marine oil spill detection and segmentation in SAR data with two steps Deep
  Learning framework*, **Mar Pollut Bull 204:116549 (2024)**,
  DOI [10.1016/j.marpolbul.2024.116549](https://doi.org/10.1016/j.marpolbul.2024.116549).
- Licence **CC-BY-4.0** → **must be cited on a slide.** (Urooz: data-provenance slide.) The
  attribution is a licence condition, not a courtesy — the wording to use is in `NOTICE`.
- **Not the Krestenitis benchmark.** Different dataset, not openly available, not used here — see
  Master Part 10, and do not quote its ~53% IoU as ours.
- 150 oil + 150 look-alike + 150 no-oil scenes, 2048×2048×2 (VV, VH) GeoTIFF in dB, plus masks.
- Part I (DOI 10.5281/zenodo.8346860, 40.7 GB) downloaded for the October CNN work. **Not used
  in this sprint** — do not claim it was.

## Detection accuracy — the honesty slide

Measured by Soumirya on a **scene-level** held-out split (the Zenodo Part III designated test set —
never a row-level split, because regions from one 2048×2048 scene are correlated and a row
split would flatter us). See Master Plan Part 12.

| Metric | Value | Split |
|---|---|---|
| Decision threshold | **0.143** | chosen on validation, never on Part III |
| Scene classification accuracy | **0.951** | all 450 Part III scenes |
| Look-alike rejection rate | **0.940** | all 450 Part III scenes |
| Clean-ocean rejection rate | **0.987** | all 450 Part III scenes |
| Oil recall | **0.927** | all 450 Part III scenes |
| Oil-class IoU, U-Net (Layer 2), gated by Layer 1 | **0.435** | Part III holdout, 138 / 150 oil scenes reached the U-Net |
| Oil-class IoU, U-Net, ungated (not shipped) | 0.449 | Part III, 145 / 150 — costs look-alike rejection 0.94 → 0.46, which is why it is gated |
| Classical baseline F1 (ablation) | **~0.1** — quote it that way, never to three decimals | same holdout, row-level on detected regions (0.085 in `eval_part3.json`; only 80 positives, so one detection moves it ~0.02) |
| Training rows (classical RandomForest) | **76,721** rows / 3,867 positives / 2,535 scenes | `data/labels/features_train.csv`, Parts I+II |

**Layer 2's IoU definition is the strictest available:** oil class only, background excluded from
numerator and denominator, pooled over whole 2048×2048 scenes (`pipeline/detect/results/eval_part3.json`,
`unet_meta.json`). **There is no "23% accuracy" figure for Layer 2** — Soumirya searched every eval file;
it was a crossed wire with Stage 2's 23% `wind_share`. Do not put 23% on a detection slide.

## Detection on real incidents — IoU against SkyTruth Cerulean

Soumirya, commit `0dce618`, validated in `18e986a`. Tool `pipeline/detect/iou_cerulean.py`, raw numbers
`pipeline/detect/results/iou_cerulean.json`. Computed on the **shipped classical detections**, nothing
retuned after the Cerulean polygons were seen (Part H). Both polygon sets burned onto the scene's own
affine grid; the method reproduces Cerulean's own stated `area` to within 0.8% on all five.

| case | IoU | recall | precision | ours km² | Cerulean km² |
|---|---|---|---|---|---|
| mumbai | 0.728 | 0.942 | 0.762 | 9.60 | 7.77 |
| farallones | 0.624 | 0.796 | 0.742 | 4.13 | 3.85 |
| jacksonville | 0.483 | 0.825 | 0.537 | 6.97 | 4.54 |
| jamnagar | 0.452 | 0.916 | 0.471 | 3.10 | 1.59 |
| gulf-alaska | 0.165 | 0.797 | 0.173 | 1.23 | 0.27 |

**Median 0.483, range 0.165–0.728, n = 5.** Cerulean's polygon is another algorithm's output, not
ground truth — say *"agreement with SkyTruth Cerulean's operational detection"*, never "accuracy".
Pattern worth stating: recall is high everywhere (0.80–0.94) and precision is what varies, i.e. our
outlines run larger than theirs. Huntington and Ennore-lookalike have no Cerulean record.

**Provenance of these five numbers** (Soumirya, 13 Sept). Trained on Parts I+II with an 85/15
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

Two extracts per case, both rebuilt by `scripts/run_attribute_all.py` (15 Sept):

| Case | Daily files | Extract | Box / window | Kept |
|---|---|---|---|---|
| case-jacksonville-2024 | `AIS_2024_07_29`, `AIS_2024_07_30` | `jacksonville.parquet` | origin box + 2 × r90, window ± 6 h | 11,689 rows · 48 MMSI |
| | `AIS_2024_07_30` | `jacksonville_scene.parquet` | scene box + 10 km, acquisition ± 90 min | 170 rows · 3 MMSI |
| case-farallones-2023 | `AIS_2023_03_16`, `AIS_2023_03_17` | `farallones.parquet` | as above | 815 rows · 6 MMSI |
| | `AIS_2023_03_17` | `farallones_scene.parquet` | as above | 108 rows · 1 MMSI |
| case-huntington-2021 | `AIS_2021_10_01`, `AIS_2021_10_02` | `huntington.parquet` | as above | 13,626 rows · 106 MMSI |
| | `AIS_2021_10_02` | `huntington_scene.parquet` | as above | 14,066 rows · 280 MMSI |

The `_scene` extracts are what makes the dark-vessel cross-check possible (D42): they cover the
**scene footprint at the acquisition time**, which the origin-window extract does not — on Mumbai
the release window ends eight hours before the satellite passed. Without one, a contact's darkness
is `null` and nothing is listed (D34).

**NOAA has no Alaska data.** Every daily file stops near 50 N (measured, commit `8ec1e11`), so
`case-gulf-alaska-2023` is `gfw_hourly`, not `noaa_dense` — see the GFW section below (D41).

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

**Ennore, 28 January 2017** (archived case, not in the demo) — collision in the early hours of
28 January between the tankers **BW Maple** (carrying LPG) and **Dawn Kanchipuram** (carrying
petroleum oil lubricant) off Kamarajar (Ennore) Port, Chennai; around 74 km of coastline affected,
tar balls collected along a 12 km stretch.
- Down To Earth, 4 Feb 2017: https://www.downtoearth.org.in/coverage/environment/chennai-oil-spill-planning-assessment-and-action-inadequate-56980 (verified 13 Sept 2026: names both tankers, the 74 km / 12 km figures, and an NGT application)
- `TODO` — one official reference (Coast Guard / DG Shipping / NGT order) before this case is ever un-archived.

**Huntington Beach / San Pedro Bay Pipeline, 1–2 October 2021** — pipeline P00547 (operator
Amplify Energy / Beta Offshore) ruptured 4.75 nm off Huntington Beach (NTSB casualty location
**33°34.20′ N, 118°7.26′ W** = `[-118.121, 33.570]`, declared as `meta.infrastructure_candidates`, D38); 588 barrels of crude,
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

**Ennore / CPCL, 4–5 December 2023** — oil released from Chennai Petroleum Corporation Limited's
refinery at Manali into floodwater during Cyclone Michaung, spreading at sea from the Kosasthalaiyar
river mouth to Kasimedu harbour, about 20 km². The NGT Southern Bench took the case up (O.A. 180 of
2023). CPCL's stated position was that there was no pipeline leak. Our case 7 is the 2023-11-30
pass, four days *before* it, used as a correct-rejection case.
- The Week, 13 Dec 2023: https://www.theweek.in/news/india/2023/12/13/ennore-residents-battle-health-issues-and-loss-of-livelihood-amid-blame-game-over-oil-spill.html (verified 13 Sept 2026: CPCL Manali refinery as source, Cyclone Michaung flooding, ~20 km² from Kosasthalaiyar to Kasimedu, NGT directions, CPCL's denial)
- NGT Southern Zone, O.A. No. 180 of 2023, report by the Tamil Nadu Pollution Control Board: https://www.greentribunal.gov.in/sites/default/files/news_updates/OA%20180%20of%202023%20Report%20by%20TNPCB.pdf (primary filing; located 13 Sept 2026, file too large to open in this pass — `TODO` read it and pin the release date and quantity before quoting either. 14 Sept: downloaded, 18.3 MB, 95 pages, **scanned images with no text layer**, so it needs reading by eye or with OCR. Until then **quote neither a date nor a quantity**; case 7 does not need either.)

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
