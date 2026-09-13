# Documentation index

Naap detects oil slicks in Sentinel-1 SAR, runs ocean physics backwards to reconstruct where the
oil entered the water, and scores vessels and infrastructure against that origin. This directory
holds the plan, the contracts, the method, the evidence and the history.

**If you read nothing else:** [`00_MASTER_PLAN.md`](00_MASTER_PLAN.md) Parts 1–5, then
[`TRAPS.md`](TRAPS.md).

---

## Reading paths

**New contributor — about 30 minutes.**
[`00_MASTER_PLAN.md`](00_MASTER_PLAN.md) §1–5 → [`architecture/README.md`](architecture/README.md)
→ the architecture page for your stage → your brief in [`team/`](team/) → the `CLAUDE.md` in the
directory you will work in → [`TRAPS.md`](TRAPS.md). Then
[`../CONTRIBUTING.md`](../CONTRIBUTING.md) before your first PR.

**Evaluating this project — a judge, a reviewer, a panel.**
[`../README.md`](../README.md) → [`architecture/README.md`](architecture/README.md) →
[`evaluation/README.md`](evaluation/README.md) (what every number measures, and what it does not)
→ [`receipts.md`](receipts.md) (the provenance of every pixel and figure) →
[`ANSWERS.README.md`](ANSWERS.README.md) (why the results were sealed until the demo).

**Resuming your own work after a break, or in a fresh AI chat.**
Your log in [`updates/`](updates/) — newest entry at the top — then your brief in
[`team/`](team/). The protocol is in [`updates/TEMPLATE.md`](updates/TEMPLATE.md).

**Running the demo.** [`operations/demo-runbook.md`](operations/demo-runbook.md), then
[`operations/runbook.md`](operations/runbook.md) for what to do when something breaks.

---

## The live contract

These four are cited from source comments across `pipeline/`, `scripts/` and `web/`. **Their
paths do not change.**

| Document | What it is |
|---|---|
| [`00_MASTER_PLAN.md`](00_MASTER_PLAN.md) | Single source of truth: architecture, the frozen contracts (Part 6, §6.1–6.9), ownership, dependencies, the decision log (Part 9), prior art, and the blind-evaluation protocol (Part 16). |
| [`CONTRACTS.md`](CONTRACTS.md) | Mirror of Master Part 6. Where the two disagree, **Master wins and this file is the bug.** |
| [`TRAPS.md`](TRAPS.md) | The bugs that actually happen — every one of them runs fine and produces confident wrong numbers. Read before debugging anything geospatial. |
| [`receipts.md`](receipts.md) | Provenance for every number and pixel: scene ids, fetch dates, API parameters, dataset DOIs. A judge asks "is this real data?" and this is the five-second answer. |

Schemas are frozen. If something genuinely cannot be expressed, raise it — do not extend a schema
unilaterally.

---

## Architecture — how the system works

| Document | What it covers |
|---|---|
| [`architecture/README.md`](architecture/README.md) | System overview, the no-imports file-handoff design and why it exists, the case bundle lifecycle, the data-flow diagram. |
| [`architecture/stage1-detection.md`](architecture/stage1-detection.md) | Scene classifier gating a U-Net, the classical feature layer, ship detection. |
| [`architecture/stage2-drift.md`](architecture/stage2-drift.md) | Backward advection, the ensemble, the origin probability grid, age estimation. |
| [`architecture/stage3-attribution.md`](architecture/stage3-attribution.md) | Four source types, component scoring, applicability gating, exclusions, the funnel. |
| [`architecture/stage4-verification.md`](architecture/stage4-verification.md) | Hand-authored verification against the investigation of record; hit / partial / miss. |

## Evaluation — what we measured and what it means

| Document | What it covers |
|---|---|
| [`evaluation/README.md`](evaluation/README.md) | **The measurement charter.** What each figure measures, its sample size and split; the rules that keep the numbers defensible; an index of every evidence file. |
| [`evaluation/deck-numbers.md`](evaluation/deck-numbers.md) | Every figure cleared for a slide, each copied from a named source file. If a number is not here, it does not go on a slide. |
| [`evaluation/stage1-accuracy-programme.md`](evaluation/stage1-accuracy-programme.md) | Stage 1 accuracy status board. |
| [`evaluation/stage2-numbers.md`](evaluation/stage2-numbers.md) | Stage 2 measured figures. |
| [`evaluation/stage2-component-report.md`](evaluation/stage2-component-report.md) | Stage 2 component-by-component report. |
| [`evaluation/stage2-age-decision-brief.md`](evaluation/stage2-age-decision-brief.md) | The slick-age decision and its reasoning. |
| [`evaluation/stage3-injected-offender-curve.md`](evaluation/stage3-injected-offender-curve.md) | The only source of quoted attribution ranking figures — real traffic, a synthetic offender whose behaviour we control, therefore a rank we can check without touching a sealed answer. |
| [`evaluation/stage3-issue-register.md`](evaluation/stage3-issue-register.md) | Open Stage 3 problems, each with its evidence and the decision it needs. |

## Operations

| Document | What it covers |
|---|---|
| [`operations/demo-runbook.md`](operations/demo-runbook.md) | Demo machine: build, settings, click path. |
| [`operations/runbook.md`](operations/runbook.md) | Demo prep, demo day, and what to do when something breaks. |
| [`operations/prompting-playbook.md`](operations/prompting-playbook.md) | How the team drives AI tools without burning quota or generating code that runs and lies. |

## The team

[`team/README.md`](team/README.md) maps each person to their brief, their work log and their
archive. Briefs: [`akshat-remaining.md`](team/akshat-remaining.md) (the live task list),
[`akshat-integration.md`](team/akshat-integration.md),
[`soum-stage1-detection.md`](team/soum-stage1-detection.md),
[`anushka-stage2-drift.md`](team/anushka-stage2-drift.md),
[`jaiveer-stage3-attribution.md`](team/jaiveer-stage3-attribution.md),
[`harshita-frontend.md`](team/harshita-frontend.md),
[`harshita-integration.md`](team/harshita-integration.md),
[`urooz-research-lead.md`](team/urooz-research-lead.md).

## Research

[`research/age-engine-brief.md`](research/age-engine-brief.md) — the slick-age investigation.
Knowing a slick is 6–18 hours old rather than 0–72 shrinks the suspect pool by roughly an order
of magnitude.

## Work logs

[`updates/`](updates/) — one file per person, **newest entry at the top**, appended after every
phase using [`updates/TEMPLATE.md`](updates/TEMPLATE.md). This is how another person, or another
AI chat, resumes someone's work without them. These are append-only: historical entries are not
edited, including their now-outdated file paths.

## Sealed results

[`ANSWERS.README.md`](ANSWERS.README.md) — `docs/ANSWERS.md` exists, is gitignored, and is held
by Akshat alone. This stub is committed on purpose so the team knows the file exists and who has
it. Read it before you wonder why nobody will tell you if your output is right.

## History

[`_archive/`](_archive/) — retired documents and dated snapshots, with the full path history.

---

## Redirect table — reorganisation of 14 Sept 2026

| Old path | New path |
|---|---|
| `docs/02_SOUM_DETECTION.md` | [`docs/team/soum-stage1-detection.md`](team/soum-stage1-detection.md) |
| `docs/06_JAIVEER_AIS.md` | [`docs/team/jaiveer-stage3-attribution.md`](team/jaiveer-stage3-attribution.md) |
| `docs/07_UROOZ_RESEARCH.md` | [`docs/team/urooz-research-lead.md`](team/urooz-research-lead.md) |
| `docs/07_UROOZ_RESEARCH_01_NAMING.md` | [`docs/_archive/urooz/research-01-naming.md`](_archive/urooz/research-01-naming.md) |
| `docs/07_UROOZ_RESEARCH_02_AGE_ENGINE.md` | [`docs/research/age-engine-brief.md`](research/age-engine-brief.md) |
| `docs/AKSHAT_REMAINING.md` | [`docs/team/akshat-remaining.md`](team/akshat-remaining.md) |
| `docs/STAGE1_ACCURACY_PROGRAMME.md` | [`docs/evaluation/stage1-accuracy-programme.md`](evaluation/stage1-accuracy-programme.md) |
| `docs/STAGE3_PHASE8.md` | [`docs/evaluation/stage3-injected-offender-curve.md`](evaluation/stage3-injected-offender-curve.md) |
| `docs/STAGE3_ISSUE_REGISTER.md` | [`docs/evaluation/stage3-issue-register.md`](evaluation/stage3-issue-register.md) |
| `docs/DECK_NUMBERS.md` | [`docs/evaluation/deck-numbers.md`](evaluation/deck-numbers.md) |
| `docs/STAGE2_NUMBERS.md` | [`docs/evaluation/stage2-numbers.md`](evaluation/stage2-numbers.md) |
| `docs/STAGE2_COMPONENT_REPORT.md` | [`docs/evaluation/stage2-component-report.md`](evaluation/stage2-component-report.md) |
| `docs/STAGE2_AGE_DECISION_BRIEF.md` | [`docs/evaluation/stage2-age-decision-brief.md`](evaluation/stage2-age-decision-brief.md) |
| `docs/STAGE3_PROGRESS_2026-09-13.md` | [`docs/_archive/jaiveer/stage3-progress-2026-09-13.md`](_archive/jaiveer/stage3-progress-2026-09-13.md) |
| `docs/STAGE3_PROGRESS_2026-09-13_EVENING.md` | [`docs/_archive/jaiveer/stage3-progress-2026-09-13-evening.md`](_archive/jaiveer/stage3-progress-2026-09-13-evening.md) |
| `docs/RUNBOOK.md` | [`docs/operations/runbook.md`](operations/runbook.md) |
| `docs/PROMPTING_PLAYBOOK.md` | [`docs/operations/prompting-playbook.md`](operations/prompting-playbook.md) |
| `web/DEMO_RUNBOOK.md` | [`docs/operations/demo-runbook.md`](operations/demo-runbook.md) |
| `docs/updates/soum_progress_report.md` | [`docs/_archive/soum/progress-report-2026-09-09.md`](_archive/soum/progress-report-2026-09-09.md) |
| `docs/01_AKSHAT_INTEGRATION.md` | [`docs/team/akshat-integration.md`](team/akshat-integration.md) |
| `docs/03_ANUSHKA_DRIFT.md` | [`docs/team/anushka-stage2-drift.md`](team/anushka-stage2-drift.md) |
| `docs/04_HARSHITA_FRONTEND.md` | [`docs/team/harshita-frontend.md`](team/harshita-frontend.md) |
| `docs/05_HARSHITA_INTEGRATION.md` | [`docs/team/harshita-integration.md`](team/harshita-integration.md) |
| `docs/PER_DIRECTORY_CLAUDE.md` | **Deleted.** Its blocks are the five per-directory `CLAUDE.md` files, which are the source of truth. |
| `docs/img/tracks_check.png` | **Deleted.** Regenerated by `pipeline/attribute/plot_tracks.py` into `pipeline/attribute/out/`. |

**Unchanged, deliberately:** `00_MASTER_PLAN.md`, `CONTRACTS.md`, `TRAPS.md`, `receipts.md`,
`ANSWERS.README.md`, and everything in `updates/`.

`updates/soum_case_nominations.md` also stays put — it is cited by name inside
`cases/case-nospill-zenodo/meta.json`, and a bundle is never hand-edited.
