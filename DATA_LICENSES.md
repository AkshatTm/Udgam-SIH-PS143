# Data licences

**The code in this repository is Apache-2.0. The data in it is not.**

`cases/` commits nine case bundles derived from six upstream sources with six different sets of
terms. One of them — Global Fishing Watch — is **non-commercial only**, and that condition
travels with the two bundles built from it. Anyone cloning this repository to build something on
top of it needs this page before they need the code.

Provenance down to the scene id, the fetch date and the request parameters lives in
[`docs/receipts.md`](docs/receipts.md). This page is the licensing view of the same facts.

---

## Summary

| Source | What we take | Terms | Attribution required | Commercial use |
|---|---|---|---|---|
| Copernicus Sentinel-1 (via Google Earth Engine, `COPERNICUS/S1_GRD`) | SAR scenes → `sar.png`, `sar_vv_vh.tif`, `bounds.json` | Copernicus free, full and open data policy | **Yes** | Yes |
| Zenodo oil-spill dataset, DOI [10.5281/zenodo.13761290](https://doi.org/10.5281/zenodo.13761290) (Trujillo-Acatitla et al., *Mar Pollut Bull* 204:116549, 2024) | Part III test scenes → training/evaluation, two benchmark bundles | **CC-BY** | **Yes — on a slide** | Yes |
| HYCOM (via Google Earth Engine) | Ocean current fields → `particles.json`, `origin.json` | US Navy / NRL, freely available | Courtesy | Yes |
| ERA5 (Copernicus C3S, via Google Earth Engine) | 10 m wind components → drift wind term | Copernicus C3S licence | **Yes** | Yes |
| NOAA Marine Cadastre AIS | Vessel tracks → `vessels.geojson`, `suspects.json` | US Government work, public domain | Courtesy | Yes |
| Global Fishing Watch API v3 | Hourly vessel positions for the two Indian cases | **NON-COMMERCIAL USE ONLY** | **Yes** | **NO** |
| SkyTruth Cerulean public OGC API | Slick polygons → `cerulean_slick.geojson` | TODO — not verified; the API is public and unauthenticated, but the redistribution terms were never read | **Yes** | TODO |
| GSHHG shoreline (via `global-land-mask`) | Land mask for near-shore drift | GSHHG is LGPL / public-domain-derived | Courtesy | Yes |

`TODO` above means genuinely not established yet. Per the convention in `docs/receipts.md`:
**do not delete a TODO by guessing.**

---

## The one that constrains you: Global Fishing Watch

GFW API v3 (`gateway.api.globalfishingwatch.org`) is free and self-registration, and it is
licensed for **non-commercial use only**. That is not boilerplate we are being cautious about —
it is the stated condition of the token, it is written into `.env.example` and
`scripts/gfw_probe.py`, and it appears on the project's data-provenance slide.

It reaches exactly two committed bundles, the ones whose `meta.json` carries
`ais_source: "gfw_hourly"`:

- `cases/case-mumbai-2023/`
- `cases/case-jamnagar-2024/`

Their `vessels.geojson` and `suspects.json` are derived from GFW responses. **Do not use those
two bundles in a commercial product.** The other seven cases use NOAA Marine Cadastre AIS, which
is public domain, and carry no such restriction.

If you need the whole library commercially, re-derive those two cases from a source you are
licensed for; `pipeline/attribute/ingest.py` and `pipeline/attribute/ingest_gfw.py` write into
the same parquet schema, so nothing downstream changes.

---

## Zenodo — the attribution is mandatory, not polite

The Zenodo oil-spill dataset (Trujillo-Acatitla et al., *Mar Pollut Bull* 204:116549, 2024) is
**CC-BY**. Attribution is a licence condition. It is cited:

- on the project's data-provenance slide,
- in `docs/receipts.md`,
- in `NOTICE`,
- in the `notes` field of the two benchmark bundles (`case-lookalike-zenodo`,
  `case-nospill-zenodo`).

Part III (150 oil + 150 look-alike + 150 no-oil scenes) is the authors' designated test set and
is the held-out split behind every Stage 1 number this project reports. Part I was downloaded for
later CNN work and **was not used in this sprint** — do not claim it was.

This dataset is **not** the Krestenitis 5-class benchmark. That is a different, non-open dataset,
and conflating the two is how the widely-quoted ~53% IoU figure gets misattributed to this work.
Master Plan Part 10 and `docs/team/soum-stage1-detection.md` both carry the correction.

---

## Copernicus Sentinel-1

Copernicus data is free, full and open. The licence asks that modified data say so. The required
form, reproduced in `NOTICE`:

> Contains modified Copernicus Sentinel data (2021–2024), processed by Team Naap.

Exact scene identifiers for all nine cases are tabulated in `docs/receipts.md`.

---

## SkyTruth Cerulean — comparison target, never ground truth

`cerulean_slick.geojson` ships inside five bundles. It is **SkyTruth's polygon, not a Naap
detection**, and each file says so in its own contents. Cerulean themselves state that SAR alone
cannot definitively identify oil slicks and that their detections are *potential* slicks; this
project repeats that rather than quietly upgrading it to truth.

Two consequences that are licensing-adjacent and worth stating here:

1. Any IoU or agreement figure computed against a Cerulean polygon is **agreement with another
   algorithm**, never accuracy against ground truth. `docs/evaluation/` holds that line.
2. The **source attribution** returned by the same API — the MMSIs Cerulean associates with a
   slick — is deliberately excluded from every bundle and from this repository.
   `scripts/fetch_cerulean.py` splits the response so the polygon can be committed without the
   answer. See `docs/ANSWERS.README.md`.

---

## What is *not* in this repository

Committed outputs move between machines; raw inputs do not. `data/` is gitignored, so none of the
following is redistributed here, and none of it is yours to obtain from us:

- the Zenodo archives (Parts I–III),
- raw NOAA AIS daily CSVs,
- trained model weights over ~100 MB (`pipeline/detect/models/` ships metadata JSON and the small
  scene classifier only — see the reasoning in `.gitignore`),
- `docs/ANSWERS.md`, the sealed documented outcomes.

The single exception is `data/labels/features_test.csv`, the Part III holdout feature table, which
is committed on purpose because it is the evidence behind the reported classical numbers.

---

## Licence of this repository's own work

| Part | Licence |
|---|---|
| Source code (`pipeline/`, `scripts/`, `web/`) | Apache-2.0 — see [`LICENSE`](LICENSE) |
| Documentation (`docs/`, `*.md`) | CC-BY-4.0 |
| Case bundles (`cases/`) | Team Naap's contribution is CC-BY-4.0; **the upstream terms above still apply to the underlying data** |

If those two sets of terms ever conflict for a particular file, the upstream licence wins. We
cannot sublicense someone else's data more permissively than we received it.
