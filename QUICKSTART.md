# QUICKSTART — get UDGAM running

*Practical companion to the [`README`](README.md). The README explains what the project is; this
explains what to type. Demo-day procedure is a different document —
[`docs/operations/runbook.md`](docs/operations/runbook.md).*

---

## TL;DR — the app, on a machine that is already set up

```bash
cd web
npm run dev
```

Open **http://localhost:3000**. That is the whole thing.

The interface never calls Python. It reads static JSON out of `web/public/cases/`, so the app runs
with **the wifi switched off** and does not need the pipeline, the venv, or a single API key.

> `npm run dev` and `npm run build` copy `cases/` into `web/public/cases/` themselves (the
> `predev`/`prebuild` hook runs `web/scripts/sync-cases.mjs`), so a fresh clone needs no Python to
> start the app. If you change a bundle **while the dev server is running**, re-run
> `node web/scripts/sync-cases.mjs` (or `python scripts/sync_web_cases.py --clean`) — an un-synced
> bundle shows **stale data, not an error**.

---

## First run on a fresh clone

### 1. Python — the pipeline and the validator

```bash
py -3.11 -m venv venv               # Windows;  python3.11 -m venv venv  elsewhere
venv\Scripts\activate               # Windows;  source venv/bin/activate elsewhere
pip install -r requirements.txt
```

`requirements-detect.txt` is Stage 1's ML stack (torch). It is a **separate file on purpose** and
needs its own index — the reasoning is written at the top of the file:

```bash
pip install -r requirements-detect.txt --index-url https://download.pytorch.org/whl/cu124
```

You only need it to run or train the detector. The case bundles are already built, so for running
the app or the other stages, skip it.

### 2. Prove the environment before trusting anything else

```bash
python scripts/make_case000.py
python scripts/validate_case.py cases/case-000
python scripts/test_validator.py
```

If `validate_case.py` does not print **`PASS`**, stop and fix that first. `cases/case-000/` is a
complete **fake** bundle in exactly the real shape — build components against it; never show it to
a judge.

### 3. Node — the interface

```bash
cd web                                     # web/public/cases/ is gitignored; predev syncs it

npm ci
npm run dev
```

`predev`/`prebuild` vendor the MapLibre worker out of `node_modules` automatically, so there is no
CDN dependency at runtime.

### 4. Secrets — almost certainly not needed

```bash
cp .env.example .env
```

The **only** secret in this project is `GFW_API_TOKEN`, and it is needed only by
`scripts/gfw_probe.py` and Stage 3 on the two `gfw_hourly` cases. Everything else is public or
uses `earthengine authenticate`. Running the app needs nothing.

---

## Running the interface: dev vs production

| | Command | Use it for |
|---|---|---|
| Development | `npm run dev` | Building. Hot reload. |
| Production | `npm run build && npm run start` | **This is what the demo runs.** |

**Never `npm run dev` in front of judges** — see
[`docs/operations/demo-runbook.md`](docs/operations/demo-runbook.md).

---

## Running the pipeline end to end (stubs, no real data)

The seam test. Each stage is published into the case folder before the next one reads it — that is
the whole architecture, and if this prints `PASS`, it is wired correctly:

```bash
python scripts/make_case000.py --out cases/case-smoke --case-id case-smoke
python pipeline/drift/run.py         --case case-smoke --stub
python pipeline/export/build_case.py --case case-smoke --stage trace
python pipeline/attribute/run.py     --case case-smoke --stub
python pipeline/export/build_case.py --case case-smoke
python scripts/validate_case.py cases/case-smoke
```

Ends in `PASS   acts=['detect', 'trace', 'attribute']` with one `WARN` about a missing
`ship_detections` key — expected, because the fake bundle's `detections.geojson` came from
`make_case000.py` and not from the real ship detector.

`cases/case-smoke/` is gitignored — it is a scratch bundle, regenerate it freely.

> **Stage 1 is not in this chain, and that is not an oversight.** `pipeline/detect/run.py` has no
> `--stub` flag and imports `torch`, so it cannot run without `requirements-detect.txt`. The
> version of this chain printed in [`README.md`](README.md) still lists
> `pipeline/detect/run.py --case case-smoke --stub`; that command does not exist and the chain
> above is the one that runs. `make_case000.py` supplies a schema-valid `detections.geojson` in its
> place. To exercise Stage 1 for real, install the detect extras and run it against a case that has
> `sar_vv_vh.tif`.

---

## Checking everything still holds

```bash
python scripts/validate_case.py cases/          # every bundle + index.json
python scripts/test_validator.py                # the validator's own mutation suite
cd web && npx tsc --noEmit                      # frontend typecheck
```

`validate_case.py` catches lat/lon swaps, naive timestamps, unit errors, dimension mismatches and
funnel inconsistencies **by name**. **Fix failures in the producing code, never by hand-editing a
bundle** — a hand-patched bundle stops being evidence of what the code does.

Three cases print a `WARN` about zero `oil` features — `case-ennore-lookalike-2023`,
`case-lookalike-zenodo` and `case-nospill-zenodo`. That is **correct**: they are the negative
cases, and finding nothing is the right answer. Warnings are not failures; only `PASS` vs `FAIL`
on the last line matters.

---

## When it will not start

### Port 3000 is already in use

Usually a dev server you forgot about. On Windows:

```powershell
Get-NetTCPConnection -LocalPort 3000 -State Listen | Select-Object -ExpandProperty OwningProcess -Unique
taskkill /PID <pid> /T /F
```

macOS / Linux: `lsof -ti:3000 | xargs kill -9`.

Or just let Next.js pick the next free port — it does that on its own and prints the URL.

### The map is empty, or the case loads with no data

`web/public/cases/` is out of date or missing. Re-run from the repo root:

```bash
python scripts/sync_web_cases.py --clean
```

### The map has no coastline and the sea is flat colour

Expected with no network. The basemap is layered deliberately: a bundled offline sea + Natural
Earth coastline always renders, and Esri's ocean tiles (bathymetry) draw on top **when the network
allows**. If the venue wifi drops, the tiles simply fail and the offline layer shows through —
there is no fallback logic to break. See `OCEAN_STYLE` in `web/components/MapView.tsx`.

### The map renders nothing at all in the browser

The vendored MapLibre worker is missing. `npm run dev` runs `predev` which copies it, but if you
started the server some other way:

```bash
cd web && node scripts/copy-maplibre-worker.mjs
```

### `ModuleNotFoundError` from a pipeline script

The venv is not active, or you are not at the repo root. Every command in this file is run **from
the repo root** with the venv activated.

### Node version

The project pins **Node 20 LTS**. Newer majors currently work, but if you hit a build error that
looks like it came from Next.js internals rather than from our code, check `node --version` before
debugging anything else.

---

## Where to go next

| You want | Read |
|---|---|
| What the project actually does | [`README.md`](README.md) |
| The method, in full | [`docs/00_MASTER_PLAN.md`](docs/00_MASTER_PLAN.md) |
| File schemas — the frozen contract | `docs/00_MASTER_PLAN.md` Part 6 (§6.1–6.9) |
| The geospatial bugs that will actually happen | [`docs/TRAPS.md`](docs/TRAPS.md) |
| Rules for working in `web/` | [`web/CLAUDE.md`](web/CLAUDE.md) |
| Demo day | [`docs/operations/runbook.md`](docs/operations/runbook.md) |

**Read [`docs/TRAPS.md`](docs/TRAPS.md) before debugging anything geospatial.** HYCOM on GEE is a
scaled int. GeoJSON is lon-lat. ERA5 wind is u/v components, not speed and direction.
