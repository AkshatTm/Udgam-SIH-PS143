# Contributing to Naap

Everything below is already how this project works — this page collects it in one place so a new
contributor does not have to reconstruct it from six documents. The authoritative sources are
[`docs/00_MASTER_PLAN.md`](docs/00_MASTER_PLAN.md) (architecture, contracts, decisions) and the
root [`CLAUDE.md`](CLAUDE.md) (the same rules, addressed to AI coding agents).

---

## The architecture rule that governs everything

**No module imports another module.** Each stage is a script that reads files from
`cases/<case_id>/` and writes files back into it. The frontend fetches static JSON and never
calls Python.

If you are about to write `from pipeline.drift import ...` in detection code, stop — you have
misunderstood the design. It exists so six people can work in parallel without blocking each
other, and so any stage can be built and tested against fake files before the real ones land.

---

## Frozen conventions — never violate, never "improve"

1. Coordinates are **`[longitude, latitude]`**, WGS84 (EPSG:4326), always. Never `[lat, lon]`.
2. Timestamps are **UTC ISO 8601 with a trailing `Z`**, timezone-aware. A naive datetime is a bug.
3. Units: km, km², m/s, degrees clockwise from north. Coordinates rounded to 5 dp in JSON.
4. **`null` ≠ `0`.** A not-applicable score is `null`; a measured zero is `0`. On a `gfw_hourly`
   case the `gap` and `slowdown` components are structurally unmeasurable and must be `null` — a
   zero there is an honesty bug, and the validator fails on it.
5. Python 3.11 + venv; Node 20 for `web/`.

File schemas live in [`docs/00_MASTER_PLAN.md`](docs/00_MASTER_PLAN.md) Part 6 (§6.1–6.9) — the
live contract the validator enforces. [`docs/CONTRACTS.md`](docs/CONTRACTS.md) mirrors it. They
are frozen. If something genuinely cannot be expressed, raise it with the maintainer; do not
extend a schema unilaterally.

---

## Before you hand anything over

```bash
python scripts/validate_case.py cases/<case_id>
```

Must print `PASS`. It catches lat/lon swaps, naive timestamps, unit errors, dimension mismatches
and funnel inconsistencies **by name**.

**Fix failures in the producing code, never by hand-editing the bundle.** A hand-patched bundle
means the same bug returns at the worst possible moment, and the bundle stops being evidence for
what the code actually does.

---

## Working rules

- **Stub first.** Your first commit writes a schema-valid output file full of garbage. Wiring
  before logic. Every stage in `pipeline/` already has a `--stub` path — run it, then replace its
  middle.
- **Every handover includes one pasteable run command** that produces a valid output file.
- **A new dependency is pinned with its justification written next to it in `requirements.txt`,
  and announced to the group.** Unannounced, six laptops silently disagree at the worst moment.
  See the `global-land-mask` entry for the expected shape of a justification.
- **45-minute rule.** Stuck on an external service (GEE, downloads, auth) for 45 minutes? Stop,
  report what you tried, the exact error text, and a minimal repro. Push through everything else
  yourself.
- **Big files never move between laptops. Outputs move instead.** `data/` is gitignored.
- After each phase, append to `docs/updates/<yourname>.md` using
  [`docs/updates/TEMPLATE.md`](docs/updates/TEMPLATE.md). Four lines: what was done, files
  touched, exact run command, open issues. This is how another person — or another AI chat —
  resumes your work without you.

---

## The honesty rule (binding)

Internals carry beyond the hackathon, to a technical panel that can check them.

**No vessel name that is not in the real AIS file. No detection the detector did not produce. No
accuracy number not measured on a held-out, scene-level split.**

Precomputed is fine and we say so openly: the pipeline runs offline and exports a case bundle,
the interface plays it back. Hardcoded fake results are not fine.

Three corollaries that come up constantly:

- Precision is never called accuracy.
- Agreement with another algorithm (e.g. a SkyTruth Cerulean polygon) is never called ground
  truth.
- Every reported figure carries its unit, its sample size and what it measures. If a number is
  not in [`docs/evaluation/deck-numbers.md`](docs/evaluation/deck-numbers.md) with a named source
  file, it does not go on a slide.

---

## Blind evaluation — why you will not be told if you are right

Documented outcomes for the case library live in a single gitignored file held by the maintainer.
This is deliberate, and [`docs/ANSWERS.README.md`](docs/ANSWERS.README.md) explains the reasoning
in full: if you know which vessel the answer names while you are weighting components, you will
tune until that vessel ranks first. That is not dishonesty — it is what anyone does when the
target is visible — but it collapses *"our system identified the vessel"* into *"we tuned it
until it did"*.

Two rules follow, and they bind contributors:

1. **Cases are named after places, never vessels.** `case-jacksonville-2024`, not the ship's name.
   If a case id looks like it names a vessel, that is a bug — say so, do not "fix" it by renaming.
2. **If you come across attribution data, do not paste it into the repo or the group chat.**
   Cerulean's API returns attribution alongside the polygon; `scripts/fetch_cerulean.py` splits
   them for you. If you see that block, close it and tell the maintainer.

---

## Git workflow

- Branch per person; push daily; PR to `main`; the maintainer merges.
- Line endings are normalised by `.gitattributes` (`* text=auto eol=lf`). Do not fight it.
- Bundle outputs are marked `linguist-generated` so PR diffs collapse them — reviewing 3000×96
  coordinates by eye is not a review, and the validator is what actually checks them.
- Never commit: `.env`, `credentials.json`, `*.pem`, `docs/ANSWERS.md`, anything under `data/`
  beyond the one un-ignored labelled table, or model weights over ~100 MB. See
  [`SECURITY.md`](SECURITY.md).

Before opening a PR:

```bash
python scripts/validate_case.py cases/     # PASS on index + all cases
python scripts/test_validator.py           # the validator's own mutation tests
```

---

## Repository layout

| Path | What |
|---|---|
| `docs/` | Master plan, contracts, traps, receipts, architecture, evaluation, per-person plans |
| `pipeline/detect/` | Stage 1 — dark-spot finder → features → classifier → `detections.geojson` |
| `pipeline/drift/` | Stage 2 — backward advection, ensemble → `particles.json`, `origin.json` |
| `pipeline/attribute/` | Stage 3 — AIS ingest → tracks → scoring → `vessels.geojson`, `suspects.json` |
| `pipeline/export/` | GEE scene export, bundle assembler |
| `scripts/` | Validator, fake-case generator, provenance probes, web sync |
| `web/` | The judge-facing app (Next.js + MapLibre + deck.gl) |
| `cases/` | Case bundles — committed, they are small JSON/PNG |
| `verification/` | Stage 4 hand-authored source files |
| `data/` | **Gitignored.** Raw AIS, Zenodo, GEE downloads |

Each pipeline directory has its own `CLAUDE.md` with role-specific rules layered on the root one.
Read [`docs/README.md`](docs/README.md) for the documentation index and reading paths.

---

## Licensing of contributions

By contributing you agree that your contribution is licensed under Apache-2.0 (code) and
CC-BY-4.0 (documentation), matching the repository. Note that data committed under `cases/`
carries **upstream** terms that Apache-2.0 does not override — read
[`DATA_LICENSES.md`](DATA_LICENSES.md) before adding a case built on a new source.
