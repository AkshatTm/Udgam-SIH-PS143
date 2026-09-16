# Stage 1 — numbers for the jury round

*Owner: Soumirya. Every figure here is measured and traceable to a file named beside it.
**Each number states its split.** That is the point: a technical judge's first question is
"what did you evaluate on", and every row here answers it before being asked.*

---

## SLIDE 1 — Detection accuracy on the sealed holdout

**Zenodo Part III, 450 scenes, scene-level split, never trained on.**
Source: `pipeline/detect/results/eval_part3.json`

### Layer 1 — scene classifier

| metric | value |
|---|---|
| scene classification accuracy | **0.951** |
| oil recall (150 oil scenes) | **0.927** |
| look-alike rejection (150 scenes) | **0.940** |
| clean-ocean rejection (150 scenes) | **0.987** |

**Say out loud:** *"The decision threshold, 0.143, was chosen on a Parts I+II validation split
under a recall floor — not on the test set. Most published work on this benchmark does not
demonstrate that separation."*

### Layer 2 — segmentation, eight definitions, same model, same pixels

| definition | value |
|---|---|
| `iou_oil_pooled` — **what we report** | **0.435** |
| `iou_oil_macro_tile` | 0.494 |
| `dice_oil_pooled` | 0.606 |
| `iou_oil_macro_scene` | 0.683 |
| **`miou_pooled`** {background, oil} — **what this literature reports** | **0.687** |
| `iou_background_pooled` | 0.939 |
| `pixel_accuracy_positives` | 0.942 |
| `pixel_accuracy_all450` | 0.980 |

**Say:** *"We report 0.435 — the strictest of eight definitions. Published work on this benchmark
family reports mean IoU in the 67–69% range; on that same definition, same pixels, we are at
0.687. We name the definition so the comparison is like-for-like."*

**Do not** quote 0.687 as the headline. It is there to make comparison honest, not to pick the
flattering number.

### The gate earns its place

| model | look-alike rejection | pooled IoU |
|---|---|---|
| U-Net only, no gate | **0.46** | 0.449 |
| Classifier + U-Net | **0.94** | 0.435 |

**Say:** *"Ungating buys 0.014 IoU and costs look-alike rejection 0.94 → 0.46. We take the trade,
because a false spill alert is worse than a slightly looser outline."*

---

## SLIDE 2 — Where the model fails, and where it does not

**Per-scene IoU by oil coverage, Part III holdout.**

| oil coverage | n | mean IoU |
|---|---|---|
| 0–1% | 18 | 0.669 |
| 1–3% | 39 | 0.757 |
| 3–10% | 52 | 0.783 |
| 10–30% | 29 | 0.660 |
| **≥30%** | **12** | **0.085** |

**Say all three parts of this, or none of them:**

> *"138 of 150 scenes sit between 0.66 and 0.78. The pooled number collapses because of 12 scenes
> where oil covers more than 30% of the frame — those hold 38% of the benchmark's oil pixels, and
> pooled IoU weights a scene by its slick size. **The cause is identified**: our per-scene
> normalisation lets a slick that large become its own reference, erasing the contrast the model
> needs. **And no case in our demo library sits in that band** — measured coverage across the nine
> cases runs 0.00% to 2.25%."*

---

## SLIDE 3 — The fix, and the honest status of it

**This is the slide teams that hardcode results cannot give.**

**On held-out validation scenes** (Parts I+II, coverage-stratified split, scenes never trained on),
sea-referenced normalisation takes the failing band:

| ≥30% coverage band | value |
|---|---|
| baseline | **0.282** |
| after the fix, mean of 3 seeds | **0.816** ± 0.055 |

Source: `pipeline/detect/results/eval_val_e2c*.json`

**Say exactly this, including the last sentence:**

> *"On held-out validation scenes the failing band goes from 0.28 to 0.82, measured across three
> independent training runs. **This is a validation number, not our test number.** We ran the
> sealed holdout once on the frozen configuration and the band reached 0.16 there, not 0.82 — the
> fix does not fully transfer yet. So our headline stays 0.435, and closing that generalisation gap
> is our next piece of work."*

**Why say it:** it is true, it is checkable, and it demonstrates that we know the difference between
a development result and a test result. A panel that has heard three teams quote validation numbers
as accuracy will notice.

---

## SLIDE 4 — External validation

**Against Cerulean (SkyTruth's operational detector) on five real incidents.**
Source: `pipeline/detect/results/iou_cerulean.json`

| | value |
|---|---|
| median IoU | **0.483** |
| range | 0.165 – 0.728 |
| recall on their polygon | **0.796 – 0.942** |

**Say:** *"Recall is high and uniform — we find the slick on all five. IoU is limited by
over-extent: we draw it larger than they do. And this is agreement between two independent
detectors, not accuracy against ground truth. SkyTruth state plainly that SAR alone cannot
definitively identify oil, so we say it too."*

`case-gulf-alaska-2023` was classed **AMBIGUOUS by Cerulean's own human reviewer** — a poor IoU
there is the expected result and is reported, not hidden.

---

## The question you will be asked, and the answer

**"How does that compare on your test set?"**

> *"0.435 pooled oil-class IoU, gated, on the 450-scene Part III holdout — that is the number on
> the slide. The 0.82 figure is validation only, and I flagged it as such: on the holdout that band
> reaches 0.16, so the fix has not transferred yet."*

**"Why is your IoU low when your accuracy is 98%?"**

> *"Different metrics on the same predictions. Pixel accuracy is 0.980, but almost every pixel is
> sea — predicting no oil anywhere would score 0.98. Oil-class IoU is 0.435 because it only counts
> pixels that are oil or predicted oil. We report the strict one."*

**"Have you tuned on the test set?"**

> *"No. Architecture and threshold were both selected on a Parts I+II validation split. The holdout
> has been scored twice in the project's life, both times on a configuration frozen beforehand."*

---

## Do NOT say

- Any number without its split named.
- "Look-alike rejection 0.960" — that is a dead pre-augmentation checkpoint. It is **0.940**.
- "VH is the discriminator" — the feature was computed from the co-pol band. Say *"adding a second
  polarisation lifts validation F1 0.346 → 0.643 and Part III precision 5.8× at identical recall."*
- "The networks don't transfer to real exports" — false; that was a channel swap.
- "Dark vessel" for anything Stage 1 emits. Every contact we produce is **unattributed**.
- Any contact count as verified — the Ennore (72), Huntington (43) and nospill-zenodo (31) lists
  are **not yet land-masked**.
- Alaska has **zero** contacts and that is correct — it is a field-of-view limit, not a threshold.
