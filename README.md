<div align="center">

# UDGAM

**Satellite forensics that traces an oil spill back to the ship that caused it.**

Smart India Hackathon 2026 · Problem statement 26143 (NTRO)

[![License](https://img.shields.io/badge/code-Apache--2.0-blue.svg)](LICENSE)
[![Docs](https://img.shields.io/badge/docs-CC--BY--4.0-lightgrey.svg)](DATA_LICENSES.md)
[![Python](https://img.shields.io/badge/python-3.11-3776AB.svg)](requirements.txt)
[![Node](https://img.shields.io/badge/node-20%20LTS-339933.svg)](web/package.json)
[![Cases](https://img.shields.io/badge/case%20library-9%20bundles-success.svg)](cases/index.json)

*Detect → Trace → Attribute → Verify*

</div>

---

> **INCOIS tells the Coast Guard where the oil is going. Nobody tells them where it came from.
> We built the other half.**

## Abstract

Oil slicks are routinely detected in Sentinel-1 radar imagery by operational systems — CleanSeaNet
in Europe, SkyTruth Cerulean globally. Detection is not the hard part, and neither is forecasting
where a slick will drift next. **The unanswered question is where it came from.**

UDGAM runs the transport physics backwards. From a detected slick it reconstructs a probability
cloud for where and when the oil entered the water, then scores every broadcasting vessel, every
dark vessel (radar sees a ship, AIS reports nothing) and every piece of fixed infrastructure
against that origin and time window. The output is a ranked, explainable shortlist — with at least
one vessel explicitly **excluded**, and with the option to **abstain**.

A fourth stage compares each conclusion against the official investigation of record and reports
`hit`, `partial` or `miss`. **The misses ship too.**

The demo is one map screen with a scrubbable time slider. Drag it backwards and the slick
dissolves into particles drifting back toward their origin.

---

## The four stages

1. **Detect** — find oil slicks in Sentinel-1 SAR, separate them from look-alikes (algae, calm
   wind, rain cells), compute geometric properties. A small CNN gates a U-Net, because the
   dataset's own authors found U-Net segments erroneously on look-alikes; a classical feature
   layer supplies the explainability bars a neural mask cannot.
2. **Trace** — run ocean-current and wind physics *backwards in time* to reconstruct where and
   when the oil entered the water. A 50-member stratified ensemble. **The output is a probability
   cloud, never a point.**
3. **Attribute** — classify the source type *before* naming anyone, because a system that can only
   consider vessels will name a vessel even when the source is a pipeline. Then score the fleet on
   seven components with stated applicability gating, and publish the funnel and the exclusions.
4. **Verify** — compare against the NTSB / USCG / documented account, cited, with the verdict
   rendered as confidently either way.

```
Sentinel-1 SAR ──▶ Detect ──▶ Trace ──▶ Attribute ──▶ Verify ──▶ one map screen
   HYCOM + ERA5 ──────────────┘            │
   NOAA AIS · GFW ─────────────────────────┘
```

Full method: **[`docs/architecture/`](docs/architecture/)**.

---

## Architecture — why six people never blocked each other

**No module imports another module. Ever.** Each stage is a script that reads files from a case
folder and writes files back into it. The frontend fetches static JSON and never calls Python.

```
cases/<case_id>/
  meta.json               case info, which acts are available
  sar.png                 the radar scene rendered as an image
  sar_vv_vh.tif           2-band float32 dB GeoTIFF — Stage 1's real input
  bounds.json             geographic bounds + the dB clamp used
  thumb.png               gallery preview
  cerulean_slick.geojson  SkyTruth's polygon — comparison target, never the answer
  detections.geojson      Stage 1 out → Stage 2 in
  particles.json          Stage 2 out (the backward rewind animation)
  particles_forward.json  Stage 2 out (forward prediction)
  origin.json             Stage 2 out → Stage 3 in
  vessels.geojson         Stage 3 out (AIS tracks)
  suspects.json           Stage 3 out (ranked suspects, funnel, exclusions)
  verification.json       Stage 4 out (our answer vs the official finding)
cases/index.json          the gallery list, strongest case first
```

Every stage can be built and tested against fake files, so nobody ever waits for anybody;
integration is just the files becoming real. It has a second payoff on the day: **the interface
has no runtime network dependency and runs with the wifi off.**

If you are about to write `from pipeline.drift import ...` in detection code, stop — you have
misunderstood the design.

---

## Frozen conventions — read before writing a line

Violating these is how this project dies. They are not preferences.

1. **Coordinates are `[longitude, latitude]`**, WGS84 (EPSG:4326). Everywhere. GeoJSON order.
   **Never `[lat, lon]`.**
2. **All times are UTC, ISO 8601, trailing `Z`** — `2021-10-01T14:20:00Z`. Timezone-aware only;
   a naive datetime is a bug.
3. **Units:** distances km, areas km², speeds m/s, angles degrees clockwise from north.
4. **Precision:** coordinates to 5 decimal places max in JSON.
5. **`null` ≠ `0`.** A not-applicable score is `null`; a measured zero is `0`.
6. **Python 3.11** + venv, deps pinned. **Node 20 LTS** for `web/`. A new dependency is pinned
   with its justification next to it and announced to the group.

Full schemas: **[`docs/00_MASTER_PLAN.md`](docs/00_MASTER_PLAN.md) Part 6** — the live frozen
contract; [`docs/CONTRACTS.md`](docs/CONTRACTS.md) mirrors it. The bugs that will actually happen:
**[`docs/TRAPS.md`](docs/TRAPS.md)** — read it before debugging anything geospatial.

---

## Quickstart

```bash
git clone https://github.com/AkshatTm/SIH-PS143.git udgam && cd udgam

py -3.11 -m venv venv               # Windows;  python3.11 -m venv venv  elsewhere
venv\Scripts\activate               # Windows;  source venv/bin/activate elsewhere
pip install -r requirements.txt
```

Prove your environment works — if this does not print `PASS`, nothing else you do is trustworthy:

```bash
python scripts/make_case000.py
python scripts/validate_case.py cases/case-000
python scripts/test_validator.py
```

`cases/case-000/` is a complete **fake** bundle in exactly the real shape. Build your entire
component against it. It is the only synthetic data in the repo and it is never shown to a judge.

### Run the whole pipeline end to end (all stubs, no real data)

The case folder is how stages hand off, so each stage is published into it before the next reads
it. This is the seam test — if it prints `PASS`, the architecture is wired:

```bash
python scripts/make_case000.py --out cases/case-smoke --case-id case-smoke --scene-only
python pipeline/detect/run.py        --case case-smoke --stub
python pipeline/export/build_case.py --case case-smoke --stage detect
python pipeline/drift/run.py         --case case-smoke --stub
python pipeline/export/build_case.py --case case-smoke --stage trace
python pipeline/attribute/run.py     --case case-smoke --stub
python pipeline/export/build_case.py --case case-smoke
```

### Run the interface

```bash
python scripts/sync_web_cases.py --clean    # copies bundles into web/public/cases
cd web && npm ci && npm run build && npm run start
```

---

## Reproducibility

```bash
python scripts/validate_case.py cases/<case_id>     # must print PASS
```

The validator catches lat/lon swaps, naive timestamps, unit errors, dimension mismatches and
funnel inconsistencies **by name**, and it has its own mutation suite that corrupts a good bundle
26 ways and checks each corruption is caught. **Fix failures in the producing code, never by
hand-editing a bundle** — a hand-patched bundle stops being evidence of what the code does.

| What | Where |
|---|---|
| Provenance for every number and pixel — scene ids, fetch dates, API parameters, DOIs | [`docs/receipts.md`](docs/receipts.md) |
| What each figure measures, its sample size and its split | [`docs/evaluation/README.md`](docs/evaluation/README.md) |
| Committed metric files (the evidence itself) | `pipeline/detect/results/`, `pipeline/attribute/results/` |
| Every figure cleared for presentation, with its source file | [`docs/evaluation/deck-numbers.md`](docs/evaluation/deck-numbers.md) |
| Open problems, unresolved, with their evidence | [`docs/evaluation/stage3-issue-register.md`](docs/evaluation/stage3-issue-register.md) |

Model weights are deliberately not committed — see the reasoning in `.gitignore`. We ship code;
the training scripts and the metric JSONs are the reproducible artefact.

---

## The honesty rule (binding)

Internals carry beyond the hackathon, to people who can check them.

**No vessel name that is not in the real AIS file. No detection the detector did not produce. No
accuracy number not measured on a held-out, scene-level split.**

Precomputed is fine and we say so openly: the pipeline runs offline and exports a case bundle, the
interface plays it back — that is why it never breaks on venue wifi. Hardcoded fake results are
not fine.

Three consequences worth stating up front, because they are visible in the repository:

- **The answers were sealed.** Every case has a documented outcome, held in one gitignored file by
  one person, so that no component was tuned against a visible target. Reasoning:
  [`docs/ANSWERS.README.md`](docs/ANSWERS.README.md).
- **Blindness is declared per case, not claimed in general.** Two cases were compromised; both are
  named, with how. A blanket claim would not survive one question.
- **The system abstains.** On two cases the funnel runs `9 → 2 → 0 → 0` — searched, and no vessel
  found in the origin cloud. That is a different claim from "nothing was searched", and it is
  reported as such.

---

## Repo map

| Path | What | Owner |
|---|---|---|
| [`docs/`](docs/) | Master plan, architecture, evaluation, contracts, traps, per-person briefs | Akshat |
| [`docs/updates/`](docs/updates/) | Per-person work logs — how a fresh AI chat resumes your work | everyone |
| `scripts/` | `validate_case.py`, `test_validator.py`, `make_case000.py`, provenance probes | Akshat |
| `pipeline/detect/` | Dark-spot finder → features → classifier → `detections.geojson` | Soumirya |
| `pipeline/drift/` | Backward advection, 50-run ensemble → `particles.json`, `origin.json` | Anushka |
| `pipeline/attribute/` | AIS ingest → tracks → scoring → `vessels.geojson`, `suspects.json` | Jaiveer |
| `pipeline/export/` | GEE scene export, bundle assembler | Akshat |
| `web/` | The judge-facing app (Next.js + MapLibre + deck.gl) | Harshita |
| `cases/` | Case bundles — committed, they are small JSON/PNG | Akshat |
| `verification/` | Stage 4 hand-authored source files | Akshat |
| `data/` | **Gitignored.** Raw AIS, Zenodo, GEE downloads | — |

Each pipeline directory has its own `CLAUDE.md` with role-specific rules on top of the root one.

**Big files never move between laptops. Outputs move instead.** The Zenodo dataset lives only on
one machine; only `detections.geojson` is committed. Raw AIS lives only on another; only
`vessels.geojson` and `suspects.json` are committed.

---

## Data sources and licensing

Sentinel-1 SAR, HYCOM currents and ERA5 winds via Google Earth Engine · ship AIS from NOAA Marine
Cadastre and Global Fishing Watch · training imagery from the Zenodo oil-spill dataset (DOI
[10.5281/zenodo.13761290](https://doi.org/10.5281/zenodo.13761290), CC-BY) · slick polygons from
SkyTruth Cerulean as a comparison target, never as ground truth.

**Code is Apache-2.0. Documentation is CC-BY-4.0. The data is neither.**

> ⚠️ Global Fishing Watch data is licensed **non-commercial only**, and that condition reaches
> `case-mumbai-2023` and `case-jamnagar-2024`. Read **[`DATA_LICENSES.md`](DATA_LICENSES.md)**
> before building anything on this repository.

Exact scene ids and file names: [`docs/receipts.md`](docs/receipts.md).

---

## Contributing

[`CONTRIBUTING.md`](CONTRIBUTING.md) has the workflow, the frozen conventions and the honesty
rule. [`SECURITY.md`](SECURITY.md) covers credentials and the sealed-answer discipline.
[`CODE_OF_CONDUCT.md`](CODE_OF_CONDUCT.md) applies to everyone.

Branch per person, push daily, PR to `main`.

## Citation

If you use this work, see [`CITATION.cff`](CITATION.cff) — GitHub renders a ready-made citation
from it in the sidebar.

## New here?

Read in this order: [`docs/00_MASTER_PLAN.md`](docs/00_MASTER_PLAN.md) §2–4 →
[`docs/architecture/README.md`](docs/architecture/README.md) → your brief in
[`docs/team/`](docs/team/) → the `CLAUDE.md` in your directory →
[`docs/TRAPS.md`](docs/TRAPS.md).

Thirty minutes, and it prevents the whole category of *"I built it against the wrong shape."*
