# Deferred: D46 `age_refusal` / `age_gate` (Track A)

**Status:** not merged. Deferred 22 Sept 2026 rather than force-reconciled with Track B.
**Recovery:** `git show archive/stage2-age-integration-track-a` — full commit still exists under
that tag (`67dc3ae`), not just this summary. `git diff main archive/stage2-age-integration-track-a -- <path>`
to see what changed per file.

## Why this was deferred instead of merged

This work was built in the `stage2-age-integration` branch/worktree at the same time another
worktree (`worktree-stage2-age-stage3-recal`, 14 commits, D47–D55) was independently doing
Stage 2 age-fusion fixes and Stage 3 rescoring in the same files. That branch landed on `main`
first (clean fast-forward, tested, documented). Merging Track A on top produced **7 conflicting
files, 15 conflict hunks** — including a genuine add/add conflict where both branches had
independently created `web/components/AgePosteriorChart.tsx`. Rather than resolve that blind
(risking silently breaking the age-fusion logic both sides touched, or duplicating a component
that already exists a different way on `main` now), the merge was aborted and this branch was
deleted. **Re-implement this against current `main`, not by replaying this diff verbatim** — the
underlying `age.py` / `origin.ts` have moved on (D47–D55) since this was written.

## What it did

Adds a `age_refusal` / `age_gate` pair to the origin contract (Master §6.5) so the panel can say
**why** no age was claimed, instead of a generic "no estimator produced a result" — the Huntington
case in particular refuses with a `convergence` window, not a search bracket, and the old copy
called that a bracket even on fresh data.

- **`pipeline/drift/age.py`** — when the age engine declines to date a slick, emits
  `age_refusal: {reason: "low_information" | "no_estimator" | "no_detection", info_gain_nats, min_gain_nats}`
  alongside the existing `age_gate`. Only ever present when `age_method` is `"none"`, never beside
  `age_posterior`.
- **`pipeline/drift/publish_all.py`** — runs `sync_web_cases.py --clean` automatically once every
  case passes, so a regeneration can't silently go stale in `web/public/cases/` again (root cause
  of why the D45 posterior went unseen on the demo panel before this).
- **`scripts/validate_case.py`** — `check_age_refusal()`: validates the enum, the sign of
  `info_gain_nats`/`min_gain_nats`, and the mutual-exclusion rule against `age_posterior`; warns
  if `age_method == "none"` with no `age_refusal` at all.
- **`docs/00_MASTER_PLAN.md` / `docs/CONTRACTS.md`** — schema text for `age_gate` and
  `age_refusal`, plus a D46 changelog entry.
- **`web/lib/origin.ts`** — `AgeGate`, `AgeWeathering`, `AgeRefusal` types; parses/validates the
  two new fields; restructured `modelMix` to carry `centroidSeparationKm`.
- **`web/lib/contracts.ts`** — matching raw-bundle field additions.
- **`web/components/AgePosteriorChart.tsx`** (new) — small `recharts` area chart of the age
  posterior: shaded 80% HPD band, dashed median line, hidden y-axis (the probability magnitude
  isn't the claim, the shape and band are).
- **`web/components/ContextPanel.tsx`** — wires the chart in; `ageRefusalText()` renders the
  specific refusal reason instead of a generic message; shows pooled model-mix weights when
  `modelMix.models.length > 1`; cross-midnight time windows now show both dates instead of a
  zero-looking `01:11 – 01:11`; per-estimator bands render to 1 decimal instead of 0.

## Files touched (9)

`docs/00_MASTER_PLAN.md`, `docs/CONTRACTS.md`, `pipeline/drift/age.py`,
`pipeline/drift/publish_all.py`, `scripts/validate_case.py`,
`web/components/AgePosteriorChart.tsx` (new), `web/components/ContextPanel.tsx`,
`web/lib/contracts.ts`, `web/lib/origin.ts`. +296/−17.

## Files that actually conflicted against Track B

`docs/00_MASTER_PLAN.md`, `pipeline/drift/age.py`, `scripts/validate_case.py`,
`web/components/AgePosteriorChart.tsx` (add/add — Track B built its own version of this file),
`web/components/ContextPanel.tsx`, `web/lib/contracts.ts`, `web/lib/origin.ts`.
(`docs/CONTRACTS.md` and `pipeline/drift/publish_all.py` merged cleanly.)

## To redo

1. Check what `main` now has for `AgePosteriorChart.tsx` and `modelMix` — Track B may have already
   built an equivalent chart or a different `modelMix` shape as part of D47–D55.
2. If `age_refusal`/`age_gate` aren't already on `main` in some form, reapply the `age.py` /
   `validate_case.py` / schema-doc changes above against current `age.py` (which now has D47–D55's
   fusion fixes) — don't just cherry-pick `67dc3ae`, the surrounding code has changed.
3. Re-wire `ContextPanel.tsx`'s refusal text and cross-midnight window fix — these are additive UI
   changes and should apply cleanly regardless of what happened to the chart/model-mix pieces.
