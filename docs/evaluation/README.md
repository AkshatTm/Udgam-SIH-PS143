# Evaluation

**The rule this whole directory exists to enforce: every number carries its unit, its sample size,
its split, and what it measures.**

Internals are binding — whatever is presented is defended later, in front of people who can check
it. That makes a flattering number a liability rather than an asset, and it is why the evaluation
documents here are as concerned with what a figure *does not* say as with its value.

**If a number is not in [`deck-numbers.md`](deck-numbers.md) with a named source file, it does not
go on a slide.**

---

## The four rules

**1. Precision is never called accuracy.**
Different questions with different denominators. Reporting one as the other inflates by exactly
the amount a reviewer will notice.

**2. Agreement with another algorithm is never called ground truth.**
IoU against a SkyTruth Cerulean polygon measures whether two detectors agree. SkyTruth themselves
state SAR alone cannot definitively identify oil slicks and that their detections are *potential*
slicks. That caveat is repeated, not dropped.

**3. The split is by source scene, never by row.**
Regions cut from one 2048×2048 scene are correlated. A row-level split inflates the headline
number. Stage 1 trains on Zenodo Parts I+II and tests on Part III, the authors' designated test
set (decision D1).

**4. `null` ≠ `0`.**
A not-applicable score is `null`; a measured zero is `0`. On a `gfw_hourly` case the `gap` and
`slowdown` components are structurally unmeasurable and must be `null` — the validator fails on a
zero there, because it is an honesty bug rather than a display bug.

---

## What can and cannot be measured on the live cases

**Attribution accuracy cannot be quoted from the case library.** Every case has a documented
outcome sealed in `docs/ANSWERS.md`. A figure derived from a case whose answer was held while the
scorer was tuned is not a measurement of the scorer (decision D21).

**Origin position has no ground truth on any case.** There is no observed release point to compare
a reconstructed cloud against. The OpenDrift comparison proves the *physics implementation*, not
the answer, and must be described that way.

What that leaves, and what is therefore reported:

| Claim | Measured on | Where |
|---|---|---|
| Stage 1 scene classification, look-alike rejection, IoU, classical baseline | Zenodo Part III holdout, scene-level split | [`stage1-accuracy-programme.md`](stage1-accuracy-programme.md), `pipeline/detect/results/` |
| Stage 1 agreement with Cerulean | Five bundles carrying `cerulean_slick.geojson` | `pipeline/detect/results/iou_cerulean.json` — **agreement, not accuracy** |
| Stage 2 component behaviour | Test suites and the OpenDrift comparison | [`stage2-numbers.md`](stage2-numbers.md), [`stage2-component-report.md`](stage2-component-report.md) |
| Stage 3 ranking performance | **Injected synthetic offender in real AIS traffic** | [`stage3-injected-offender-curve.md`](stage3-injected-offender-curve.md), `pipeline/attribute/results/` |
| Bundle correctness | All nine committed cases | `python scripts/validate_case.py cases/` |

### The Stage 3 workaround, and its limits

Since no live case can supply an attribution number, the alternative is to build one where the
answer is known by construction: **real AIS traffic, a synthetic guilty vessel whose discharge
point, transponder gap, speed profile, course and type are all controlled, and therefore a rank
that can be checked.**

Every figure it produces is a **ranking** number given a stated origin quality. It is an upper
bound on end-to-end performance and is **never** to be quoted as accuracy on the live cases.
Abstention is reported separately and is never scored as a hit or a miss.

One result from building it is worth keeping as a cautionary note: the first version of the
generator made every injected offender a tanker, which inflated the `type_prior` component's
apparent contribution. **A benchmark that leaks the answer measures the leak.**

---

## The benchmark-gap framing

The Zenodo dataset's own authors report 99% classification accuracy and 96% IoU on their test set.
The widely-quoted ~53% IoU "state of the art" comes from the **Krestenitis** 5-class benchmark — a
*different*, non-open dataset that requires a proposal to access.

Quoting our number against the 53% would be a category error, and quoting it against the 96%
without saying so invites the obvious attack: *why is your number so much higher than the
literature?*

The honest framing is stronger than either:

> The gap between 96% and 53% is not a difference in model quality. It measures how much
> look-alike variety a dataset contains. That gap is our result, not our excuse.

---

## Evidence index

Committed generated files. These are outputs — regenerate them, never hand-edit one to change a
number.

| File | Produced by | Interpreted in |
|---|---|---|
| `pipeline/detect/results/eval_part3.json` | `pipeline/detect/evaluate.py` | [`stage1-accuracy-programme.md`](stage1-accuracy-programme.md) |
| `pipeline/detect/results/eval_summary.csv` | `pipeline/detect/eval_gt.py` | same |
| `pipeline/detect/results/iou_cerulean.json` | `pipeline/detect/iou_cerulean.py` | same, and [`../receipts.md`](../receipts.md) |
| `pipeline/detect/results/oracle_ceiling.json` | `pipeline/detect/oracle_ceiling.py` | same |
| `pipeline/detect/results/audit_shortcut.json` | `pipeline/detect/audit_shortcut.py` | same |
| `pipeline/detect/models/*.json` | training scripts | model metadata — committed even though the weights are not |
| `data/labels/features_test.csv` | `pipeline/detect/make_labels.py` | the Part III holdout feature table, 4,085 rows — the evidence behind every classical figure |
| `pipeline/attribute/results/phase8_*.json` | `pipeline/attribute/evaluate.py` | [`stage3-injected-offender-curve.md`](stage3-injected-offender-curve.md) |

Provenance for the inputs behind all of it — scene ids, fetch dates, API parameters, dataset DOIs
— is [`../receipts.md`](../receipts.md).

---

## The documents here

| Document | What it is |
|---|---|
| [`deck-numbers.md`](deck-numbers.md) | Every figure cleared for presentation, each copied from a named source file rather than remembered. The gate. |
| [`stage1-accuracy-programme.md`](stage1-accuracy-programme.md) | Stage 1 accuracy status board — updated as items complete, not a log. |
| [`stage2-numbers.md`](stage2-numbers.md) | Stage 2 measured figures. |
| [`stage2-component-report.md`](stage2-component-report.md) | Stage 2 component-by-component report. |
| [`stage2-age-decision-brief.md`](stage2-age-decision-brief.md) | The slick-age decision and its reasoning. |
| [`stage3-injected-offender-curve.md`](stage3-injected-offender-curve.md) | The injected-offender design, conditions, results and weight ablation. |
| [`stage3-issue-register.md`](stage3-issue-register.md) | Open Stage 3 problems with their evidence. **None of them was made to disappear by moving a weight or a threshold** — where a fix needed a decision, the decision was written up and the code left alone. |

---

## A note on the issue register

It is unusual to publish an open-problems list alongside results, and it is deliberate. Every item
in [`stage3-issue-register.md`](stage3-issue-register.md) could have been made to vanish by
adjusting a constant. Recording them instead is what makes the numbers that *are* reported worth
anything.
