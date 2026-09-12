# Naap

**Satellite forensics that traces an oil spill back to the ship that caused it.**
SIH 2026 · PS 26143 · Detect → Trace → Attribute → Verify.

1. **Detect** — find oil slicks in Sentinel-1 radar (SAR) imagery, separate them from
   look-alikes (algae, calm wind, rain cells), and compute geometric properties.
2. **Trace** — run ocean-current and wind physics *backwards in time* to reconstruct where and
   when the oil entered the water. The output is a probability cloud, never a point.
3. **Attribute** — score broadcasting vessels, dark vessels (radar sees a ship, AIS reports
   nothing) and fixed infrastructure (pipeline, platform, wreck) against that origin cloud and
   time window; produce a ranked shortlist plus at least one explicitly **excluded** vessel.
4. **Verify** — compare NAAP's conclusion against the official investigation (NTSB / USCG /
   documented press account), cited, with a `hit` / `partial` / `miss` verdict rendered as
   confidently either way.

The demo is one map screen with a scrubbable time slider. Drag it backwards and the slick
dissolves into particles drifting back toward their origin.

> *INCOIS tells the Coast Guard where the oil is going. Nobody tells them where it came from.
> We built the other half.*

---

## FROZEN CONVENTIONS — read before writing a line

Violating these is how this project dies. They are not preferences.

1. **Coordinates are `[longitude, latitude]`**, WGS84 (EPSG:4326). Everywhere. GeoJSON order.
   **Never `[lat, lon]`.**
2. **All times are UTC, ISO 8601, trailing `Z`** — `2017-01-29T00:14:00Z`. Timezone-aware
   datetimes only; a naive datetime is a bug.
3. **Units:** distances km, areas km², speeds m/s, angles degrees clockwise from north.
4. **Precision:** coordinates to 5 decimal places max in JSON (≈1 m; keeps files small).
5. **Python 3.11** + venv, deps pinned in `requirements.txt`. **Node 20 LTS** for `web/`.
   A new dependency is pinned with its justification next to it and announced to the group.

Full schemas: **[`docs/00_MASTER_PLAN.md`](docs/00_MASTER_PLAN.md) Part 6** — the live frozen
contract; [`docs/CONTRACTS.md`](docs/CONTRACTS.md) is the v1 record. Changes go through Akshat.
The bugs that will actually happen: **[`docs/TRAPS.md`](docs/TRAPS.md)** — read it before
debugging anything geospatial.

---

## Architecture — why six people don't block each other

**No module imports another module. Ever.** Each stage is a script that reads files from a case
folder and writes files back into it. The frontend fetches static JSON and never calls Python.

```
cases/<case_id>/
  meta.json               case info, which acts are available
  sar.png                 the radar scene rendered as an image
  sar_vv_vh.tif           2-band float32 dB GeoTIFF — Soum's real input
  bounds.json             geographic bounds + the dB clamp used
  thumb.png               gallery preview
  detections.geojson      Stage 1 out -> Stage 2 in
  particles.json          Stage 2 out (the backward rewind animation)
  particles_forward.json  Stage 2 out (forward prediction)
  origin.json             Stage 2 out -> Stage 3 in
  vessels.geojson         Stage 3 out (AIS tracks)
  suspects.json           Stage 3 out (ranked suspects, funnel, exclusions)
  verification.json       Stage 4 out (our answer vs the official finding)
cases/index.json          the gallery list, strongest case first
```

Every stage can be built and tested against fake files. Nobody ever waits for anybody.
Integration is just the files becoming real. If you are about to write
`from pipeline.drift import ...` in detection code, stop — you have misunderstood the design.

---

## Quickstart

```bash
git clone https://github.com/AkshatTm/SIH-PS143.git naap && cd naap
git checkout -b <yourname>          # akshat / soum / anushka / harshita / jaiveer / urooz

py -3.11 -m venv venv               # Windows;  python3.11 -m venv venv  elsewhere
venv\Scripts\activate               # Windows;  source venv/bin/activate elsewhere
pip install -r requirements.txt
```

Prove your environment works — if this doesn't print `PASS`, nothing else you do today is
trustworthy:

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

---

## Before you hand anything over

```bash
python scripts/validate_case.py cases/<case_id>
```

Must print `PASS`. It catches lat/lon swaps, naive timestamps, unit errors, dimension mismatches
and funnel inconsistencies **by name**. **Fix failures in the producing code, never by
hand-editing a bundle** — a hand-patched bundle means the same bug returns at the worst moment.

---

## Repo map

| Path | What | Owner |
|---|---|---|
| `docs/` | Master plan, per-person briefs, contracts, traps, runbook | Akshat |
| `docs/updates/` | Per-person work logs — how a fresh AI chat resumes your work | everyone |
| `scripts/` | `make_case000.py`, `validate_case.py`, `test_validator.py`, `find_scenes.py`, `inspect_db.py` | Akshat |
| `pipeline/detect/` | Dark-spot finder → features → classifier → `detections.geojson` | Soum |
| `pipeline/drift/` | Backward advection, 50-run ensemble → `particles.json`, `origin.json` | Anushka |
| `pipeline/attribute/` | AIS ingest → tracks → scoring → `vessels.geojson`, `suspects.json` | Jaiveer |
| `pipeline/export/` | GEE scene export, bundle assembler | Akshat |
| `web/` | The judge-facing app (Next.js + MapLibre + deck.gl) | Harshita |
| `cases/` | Case bundles — committed, they're small JSON/PNG | Akshat |
| `data/` | **Gitignored.** Raw AIS, Zenodo, GEE downloads | — |

Each directory has its own `CLAUDE.md` with role-specific rules on top of the root one.

**Big files never move between laptops. Outputs move instead.** The Zenodo dataset lives only on
Soum's machine; only `detections.geojson` is committed. Raw AIS lives only on Jaiveer's machine;
only `vessels.geojson` / `suspects.json` are committed.

---

## Working rules

- **Stub first.** Your first commit writes a schema-valid output file full of garbage. Wiring
  before logic. Every stage in `pipeline/` already has one — run it, then replace its middle.
- **Nothing is handed over without a run command** — one pasteable line producing a valid file.
- **45-minute rule.** Stuck on an external service (GEE, downloads, auth) for 45 minutes? Stop,
  message Akshat with what you tried, the exact error text, and a minimal repro. Push through
  everything else yourself.
- **Fresh AI chat per bug.** Long threads resend the whole conversation every turn.
- After each phase, append to `docs/updates/<yourname>.md` using
  [`docs/updates/TEMPLATE.md`](docs/updates/TEMPLATE.md). Four lines. This is how another person
  — or another AI chat — resumes your work without you.
- Branch per person, push daily, PR to `main`, Akshat merges.

## The honesty rule (binding)

Internals carry to December, before an NTRO panel. **No vessel name that isn't in the real AIS
file. No detection the detector didn't produce. No accuracy number we didn't measure** on a
held-out, scene-level split.

Precomputed is fine and we say so openly: the pipeline runs offline and exports a case bundle,
the interface plays it back — that's why it never breaks on venue wifi. Hardcoded fake results
are not fine.

## Data sources

Sentinel-1 SAR, HYCOM currents and ERA5 winds via Google Earth Engine · ship AIS from NOAA
Marine Cadastre · training imagery from the Zenodo oil-spill dataset
(DOI [10.5281/zenodo.13761290](https://doi.org/10.5281/zenodo.13761290), CC-BY — cited on a
slide). Exact scene ids and file names: [`docs/receipts.md`](docs/receipts.md).

## New here?

Read in this order: [`docs/00_MASTER_PLAN.md`](docs/00_MASTER_PLAN.md) §2–4 → your personal doc
in `docs/` → the `CLAUDE.md` in your directory → [`docs/TRAPS.md`](docs/TRAPS.md).
Twenty minutes, and it prevents the whole category of "I built it against the wrong shape."
