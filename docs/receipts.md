# RECEIPTS — provenance for every number and pixel we show

*Owner: Akshat. Must be complete before the freeze.*

**Why this file exists:** a judge asks "is this real data?" and the answer has to be a scene id
on screen within five seconds, not a story. Internals are binding — whatever we show on the 11th
we defend in December before an NTRO panel.

`TODO` below means genuinely not filled in yet. Do not delete a TODO by guessing.

---

## Sentinel-1 SAR scenes (Google Earth Engine, `COPERNICUS/S1_GRD`)

| Case | `system:index` | Acquired (UTC) | Days after incident | Mode / pol | Notes |
|---|---|---|---|---|---|
| case-ennore-2017 | `TODO` | `TODO` | `TODO` | IW / VV | run `python scripts/check_ennore.py --project <id>` and paste the winning row |
| case-us-`TODO` | `TODO` | `TODO` | `TODO` | IW / VV | US case not yet picked (Ayushmaan shortlists → Akshat decides Mon 7) |
| no-spill case | `TODO` | — | — | — | a Zenodo Part III look-alike scene, Soum picks |

Export settings actually used (these must match what `bounds.json` records):
- band **VV**, dB clamp **[-25, 0]**, scaled to 8-bit, **`TODO` m/px**
- command: `python pipeline/export/gee_scene.py --project <id> --scene <index> --case <id>`

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

Measured by Soum on a **scene-level** held-out split (never a row-level split — regions from one
2048×2048 scene are correlated and a row split would flatter us).

| Metric | Value | Split |
|---|---|---|
| Precision (oil) | `TODO` | held-out scenes, n=`TODO` |
| Recall (oil) | `TODO` | held-out scenes, n=`TODO` |
| Training rows | `TODO` | `data/labels/features.csv` |

Context we state alongside it: separating oil from look-alikes is an open research problem — the
published deep-learning benchmark is around **53% IoU**, and it is 53% for everyone. That is
precisely why the system does not rest on detection alone.

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

**US case** — `TODO` once picked. Needs: US waters · before Sep 2024 (HYCOM in GEE ends
2024-09-05) · Sentinel-1 coverage · a documented incident.

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
