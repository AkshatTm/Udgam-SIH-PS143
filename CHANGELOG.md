# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project aims at
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

This file starts at the point the repository was given a public-facing structure. Earlier history
is in the git log and, in narrative form, in `docs/updates/` (per-person work logs, newest entry
at the top) and `docs/_archive/`.

## [Unreleased]

### Added
- `LICENSE` (Apache-2.0), `NOTICE`, and `DATA_LICENSES.md` — the last stating plainly that
  Global Fishing Watch data is non-commercial only and that the condition reaches
  `case-mumbai-2023` and `case-jamnagar-2024`.
- `CITATION.cff`, `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`, `SECURITY.md`, this changelog.
- `docs/README.md` — documentation index, reading paths, and the old-path → new-path redirect
  table for this reorganisation.
- `docs/architecture/` — system overview plus a method write-up per stage.
- `docs/evaluation/README.md` — the measurement charter and an index of every evidence file.
- `docs/team/README.md` — per-person pointer to plan document, work log and archive.
- `.github/` — pull request template, issue templates, and a CI workflow that runs
  `scripts/validate_case.py` and `scripts/test_validator.py` on a stdlib-only Python 3.11.
- `pipeline/detect/results/` and `pipeline/attribute/results/`, each with a README naming the
  script that produces every file in it.

### Changed
- `docs/` reorganised into `architecture/`, `evaluation/`, `operations/`, `team/`, `research/`,
  `updates/` and `_archive/`. `00_MASTER_PLAN.md`, `CONTRACTS.md`, `TRAPS.md`, `receipts.md` and
  `ANSWERS.README.md` deliberately keep their paths — they are cited from source comments across
  `pipeline/`, `scripts/` and `web/`.
- Per-person plan documents for all six contributors are now collected in `docs/team/`, including
  the three that had been archived. Every person can find the record of what they built in one
  place.
- Generated evaluation artefacts moved out of the source directories they were produced in and
  into `pipeline/<stage>/results/`.
- `README.md` rewritten as a research-project front page; `web/README.md` rewritten to describe
  the application that exists rather than how to bootstrap one.
- `web/DEMO_RUNBOOK.md` moved to `docs/operations/demo-runbook.md` — it is a whole-project
  runbook, not frontend documentation.

### Removed
- `docs/PER_DIRECTORY_CLAUDE.md` — a copy-paste template whose blocks were already pasted into
  the five per-directory `CLAUDE.md` files, and which had since drifted to cite archived paths.
- `docs/img/tracks_check.png` — orphaned; `pipeline/attribute/plot_tracks.py` regenerates it.

### Fixed
- Stale documentation paths in source comments across `pipeline/`, `scripts/` and `web/`, left
  behind by an earlier archival pass.
- `pipeline/detect/eval_gt.py` wrote `eval_summary.csv` relative to the working directory rather
  than to the script, so the file landed wherever it happened to be run from.

## [0.4.0] — 2026-09-14

The state of the system at the internal-round freeze. Recorded from the repository, not from
memory; every figure referenced here is defined and sourced in `docs/evaluation/`.

### Added
- Four-stage pipeline: detection (Sentinel-1 SAR), backward drift to an origin probability cloud,
  vessel and infrastructure attribution, and verification against the official investigation of
  record.
- Case library of nine indexed bundles in `cases/index.json` — seven satellite exports and two
  Zenodo Part III benchmark tiles — all validating `PASS`.
- Master Plan v4 and frozen contracts v4 (`docs/00_MASTER_PLAN.md` Part 6, mirrored in
  `docs/CONTRACTS.md`).
- Schema validator (`scripts/validate_case.py`) with its own mutation test suite
  (`scripts/test_validator.py`), which catches lat/lon swaps, naive timestamps, unit errors,
  dimension mismatches and funnel inconsistencies by name.
- Stage 3 injected-offender evaluation (`pipeline/attribute/evaluate.py`) — the only source of
  quoted attribution ranking figures, since every live case has a sealed answer.
- Next.js + MapLibre + deck.gl interface: one map screen, a scrubbable time slider, and the four
  stages as layers on it. No runtime network dependency.

### Notes
- Documented outcomes for the case library are sealed in a gitignored file held by the
  maintainer. See `docs/ANSWERS.README.md` for why, and `docs/00_MASTER_PLAN.md` Part 16 for
  which results are declared blind per case.

[Unreleased]: https://github.com/AkshatTm/SIH-PS143/compare/main...HEAD
