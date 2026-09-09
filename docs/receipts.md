# RECEIPTS — provenance for every number and pixel we show

*Owner: Akshat. Must be complete before the freeze.*

**Why this file exists:** a judge asks "is this real data?" and the answer has to be a scene id
on screen within five seconds, not a story. Internals are binding — whatever we show on
15 September we defend in December before an NTRO panel.

`TODO` below means genuinely not filled in yet. Do not delete a TODO by guessing.

---

## Sentinel-1 SAR scenes (Google Earth Engine, `COPERNICUS/S1_GRD`)

| Case | `system:index` | Acquired (UTC) | Days after incident | Mode / pol | Notes |
|---|---|---|---|---|---|
| case-ennore-2017 | `S1A_IW_GRDH_1SDV_20170129T003132_20170129T003157_015039_01892E_6D04` | 2017-01-29 00:31:32Z | +1.0 d | IW / VV+VH | 06:01 IST, dawn low-wind. Full coverage of Ennore. **No clear slick** — see _INTEGRATION 2026-09-09. Akshat working it. |
| case-huntington-2021 | `S1A_IW_GRDH_1SDV_20211002T015821_20211002T015850_039934_04B9C9_2BF9` | 2021-10-02 01:58:21Z | +0.1 d (first alarm 1 Oct 23:10Z) | IW / VV+VH | **Clear sharp comma-shaped slick**, ~8–10 dB VV depression at core. S1A ascending, oil still leaking. HERO detection case. |
| case-golden-ray-2021 | `S1A_IW_GRDH_1SDV_20210808T232953_20210808T233018_039145_049EAB_C7D5` | 2021-08-08 23:29:53Z | +9 d | IW / VV+VH | Only S1 coverage of the sound (12-day ascending repeat). Enclosed calm water, **no SAR-visible slick**. Wreck cluster clearly imaged. Infrastructure case, trace-from-known-source. |
| case 4 (vessel, US) | `TODO` | `TODO` | `TODO` | — | Urooz: SkyTruth Cerulean `cerulean.skytruth.org` / `api.cerulean.skytruth.org`, US waters, clean linear slick + named vessel, Oct 2014–Sep 2024 |
| case 5 (vessel, US) | `TODO` | `TODO` | `TODO` | — | second, ideally a different basin |
| case 6 (look-alike) | `TODO` | — | — | — | Zenodo Part III `Lookalike/` folder, Soum picks |
| case 7 (no-spill) | `TODO` | — | — | — | Zenodo Part III `No oil/` folder, Soum picks |

Export settings actually used (these must match what `bounds.json` records):
- `sar_vv_vh.tif`: **2-band float32 GeoTIFF, dB, unclamped**, `--tif-scale 10` m/px — Soum's real input
- `sar.png` / `thumb.png`: band **VV**, dB-clamped 8-bit, `--png-scale 20–25` m/px — display only. Clamp recorded per case in `bounds.json` (`db_min`/`db_max`). Huntington: `[-25, -5]`, Golden Ray: `[-24, -4]`, Ennore: `[-20, -6]`.
- `bounds.json` also records `vh_available` (all three US-relevant scenes: VV+VH present)
- command: `python pipeline/export/gee_scene.py --project <id> --scene <index> --case <id> --bbox W S E N`
- generalised finder: `python scripts/find_scenes.py --project <id> --bbox W S E N --start <d> --end <d> [--incident <d>]`

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
| Scene classification accuracy | `TODO` | Part III holdout, n=`TODO` scenes |
| Look-alike rejection rate | `TODO` | Part III holdout |
| Oil-class IoU (positives only) | `TODO` | Part III holdout |
| Classical baseline F1 (ablation) | `TODO` | same holdout |
| Training rows | `TODO` | `data/labels/features.csv` |

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
| case-us-`TODO` | `TODO` | `TODO` | `TODO` |

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

**Cases 4 & 5 (transiting-vessel discharges, US waters)** — `TODO`, Urooz researching via
SkyTruth Cerulean. Carry the caveat: *"SkyTruth Cerulean attributed this slick to vessel X"*,
never *"vessel X was proven responsible"*.

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
