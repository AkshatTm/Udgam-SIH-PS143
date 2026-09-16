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

## SLIDE 3 — External validation

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

## ONE model, ONE split — deliberately

Every figure and every number in this file comes from **the shipped pair** scored on the **Zenodo
Part III holdout, 450 scenes**. There is no second model anywhere in the deck, and no validation
number is quoted as an accuracy.

That is a presentation decision AND a defensive one: a mixed deck invites "which model is that
number from?", and the answer has to be instant. Here it always is.

**If asked whether you have anything better in development:** yes, and say it plainly —
*"We have a fix for the large-slick failure that reaches 0.82 on that band on held-out validation
scenes. It does not transfer to the sealed holdout yet, where it reaches 0.16, so we are not
quoting it as a result."* That answer is stronger than the number would have been.

## The question you will be asked, and the answer

**"Is that your test set or your validation set?"**

> *"Test. Every number on these slides is the Zenodo Part III holdout — 450 scenes, scene-level
> split, the model never trained on any of them. The only figure drawn from validation is the
> threshold selection in F1.2, and it is labelled on the axes."*

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
- **Contact counts: use the CURRENT ones.** They were land-masked on 16 Sept with a real coastline:
  **Ennore 72 → 41**, `lookalike-zenodo` 1 → 0, total **142 → 110**. Huntington (43), Mumbai (21),
  Jamnagar (3) and Jacksonville (2) are unchanged — those boxes are 0.0–0.7% land, so their contacts
  were never land returns. Huntington's brightest is **+23.5 dB**, a hard target.
- **"Dark vessel"** for anything Stage 1 emits. Every contact we produce is **unattributed** — a
  contact becomes a dark-vessel claim only after Stage 3 fails to match it to AIS.
- Alaska has **zero** contacts and that is correct — it is a field-of-view limit, not a threshold.
