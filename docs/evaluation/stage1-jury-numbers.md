# Stage 1 — numbers for the jury round

*Owner: Soumirya. Every figure is measured and traceable to a file named beside it.
**Each number states its split.** A technical judge's first question is "what did you evaluate on",
and every row here answers it before being asked.*

> **THE DECK DESCRIBES ONE PAIR: `unet_e2c_sea_refonly` + `scene_classifier_l1_e2c_recall`.**
> Every number below is that pair scored on the **Zenodo Part III holdout, 450 scenes**, on a
> configuration frozen and recorded *before* the run. No second model appears anywhere, and no
> validation figure is quoted as an accuracy.
>
> Regenerate the figures with `python pipeline/detect/make_figures.py --pair updated`.

---

## SLIDE 1 — Detection accuracy on the sealed holdout

**Zenodo Part III, 450 scenes, scene-level split, never trained on.**
Sources: `pipeline/detect/results/eval_part3_e2c.json`,
`pipeline/detect/models/scene_classifier_l1_e2c_recall_meta.json`

### Layer 1 — scene classifier   *(figure F1.1)*

| metric | value |
|---|---|
| scene classification accuracy | **0.942** |
| oil recall (150 oil scenes) | **0.927** |
| look-alike rejection (150 scenes) | **0.920** |
| clean-ocean rejection (150 scenes) | **0.980** |

Confusion matrix: **139 TP · 15 FP · 11 FN · 285 TN**.

**Say out loud:** *"The decision threshold, 0.128, was chosen on a Parts I+II validation split by a
stated rule — the lowest threshold holding validation precision above 0.95 — not on these 450 test
scenes. Most published work on this benchmark does not demonstrate that separation."*

### Layer 2 — segmentation, eight definitions, same model, same pixels   *(F1.4)*

| definition | value |
|---|---|
| `iou_oil_pooled` — **what we report** | **0.452** |
| `iou_oil_macro_tile` | 0.527 |
| `dice_oil_pooled` | 0.622 |
| `iou_oil_macro_scene` | 0.669 |
| **`miou_pooled`** {background, oil} — **what this literature reports** | **0.696** |
| `iou_background_pooled` | 0.940 |
| `pixel_accuracy_positives` | 0.943 |
| `pixel_accuracy_all450` | 0.980 |

**Say:** *"We report 0.452 — the strictest of eight definitions. Published work on this benchmark
family reports mean IoU in the 67–69% range; on that same definition, same model, same pixels, we
are at 0.696. We name the definition so the comparison is like-for-like."*

**Do not** quote 0.696 as the headline. It exists to make comparison honest, not to pick the
flattering number.

### The gate earns its place   *(F1.3)*

| | look-alike rejection | pooled IoU |
|---|---|---|
| U-Net only, no gate | **0.31** | 0.460 |
| Classifier + U-Net | **0.91** | 0.452 |

**Say:** *"Ungating buys 0.008 IoU and costs look-alike rejection 0.91 → 0.31. We take the trade: a
false spill alert is worse than a slightly looser outline."*

---

## SLIDE 2 — Where the model fails, and where it does not   *(F1.5)*

**Per-scene IoU by oil coverage, Part III holdout, 150 oil scenes.**

| oil coverage | n | mean IoU |
|---|---|---|
| 0–1% | 18 | 0.687 |
| 1–3% | 39 | 0.746 |
| 3–10% | 52 | 0.755 |
| 10–30% | 29 | 0.610 |
| **≥30%** | **12** | **0.160** |

**Say all three parts of this, or none of them:**

> *"138 of 150 scenes sit between 0.61 and 0.76. The pooled number collapses because of 12 scenes
> where oil covers more than 30% of the frame — those hold 38% of the benchmark's oil pixels, and
> pooled IoU weights a scene by its slick size. **The cause is identified**: per-scene normalisation
> lets a slick that large become its own reference, erasing the contrast the model needs. **And no
> case in our demo library sits in that band** — measured coverage across the nine cases runs 0.00%
> to 2.25%."*

---

## SLIDE 3 — External validation   *(F1.6)*

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

> **Note for you, not the slide:** this comparison runs on the **classical** detector, which is what
> produces the nine bundles on screen. It is independent of which Layer 2 the accuracy slides
> describe, so it does not change when the pair does.

---

## ONE pair, ONE split — deliberately

Every accuracy number in this deck is `unet_e2c_sea_refonly` + `scene_classifier_l1_e2c_recall` on
the Part III holdout. A mixed deck invites *"which model is that number from?"*, and the answer has
to be instant. Here it always is.

**Two things to know yourself, which are not slide material:**

1. **The differences against the previously shipped pair are inside the noise.** Layer 2 pooled
   0.435 → 0.452 and mIoU 0.687 → 0.696; Layer 1 accuracy 0.951 → 0.942. Measured seed-to-seed
   variation on this pipeline is **±0.027 pooled**, so **none of those gaps is an established
   improvement.** Present these as *our* numbers, not as *better* numbers.
2. **Neither Layer 2 model produces the detections on screen.** All nine demo bundles come from the
   **classical** path. The accuracy slides describe benchmark performance; the map screen shows the
   classical detector. If asked, say exactly that — it is a design choice (D33 routing), not an
   omission.

---

## The questions you will be asked, and the answers

**"Is that your test set or your validation set?"**

> *"Test. Every number on these slides is the Zenodo Part III holdout — 450 scenes, scene-level
> split, the model never trained on any of them. The only figure drawn from validation is the
> threshold selection in F1.2, and it is labelled on the axes."*

**"Why is your IoU low when your accuracy is 98%?"**

> *"Different metrics on the same predictions. Pixel accuracy is 0.980, but almost every pixel is
> sea — predicting no oil anywhere would score 0.98. Oil-class IoU is 0.452 because it only counts
> pixels that are oil or predicted oil. We report the strict one."*

**"Have you tuned on the test set?"**

> *"No. Architecture and both thresholds were selected on a Parts I+II validation split under
> stated rules. The holdout has been scored twice in this project's life, each time on a
> configuration frozen beforehand."*

**"What's still wrong with it?"**

> *"Scenes where oil covers more than 30% of the frame — 12 of the 150, scoring 0.16. We know the
> mechanism and we have a fix that reaches 0.82 on that band on held-out validation scenes. It does
> not transfer to the sealed holdout yet, so we are not quoting it as a result."*

---

## Do NOT say

- Any number without its split named.
- **"Our accuracy improved."** The gaps against the previous pair are inside the measured noise
  floor of ±0.027. These are our numbers, not better numbers.
- Any **validation** figure as an accuracy — in particular the 0.75 pooled and the 0.82 band result.
  Both are validation; the holdout figures are 0.452 and 0.160.
- "Look-alike rejection 0.960" — a dead pre-augmentation checkpoint. This pair is **0.920**.
- "VH is the discriminator" — the feature was computed from the co-pol band. Say *"adding a second
  polarisation lifts validation F1 0.346 → 0.643 and Part III precision 5.8× at identical recall."*
- "The networks don't transfer to real exports" — false; that was a channel swap.
- **"Dark vessel"** for anything Stage 1 emits. Every contact is **unattributed** — it becomes a
  dark-vessel claim only after Stage 3 fails to match it to AIS.
- Stale contact counts. Land-masked 16 Sept with a real coastline: **Ennore 72 → 41**,
  `lookalike-zenodo` 1 → 0, total **142 → 110**. Huntington (43), Mumbai (21), Jamnagar (3) and
  Jacksonville (2) are unchanged — those boxes are 0.0–0.7% land, so they were never land returns.
- Alaska has **zero** contacts and that is correct — a field-of-view limit, not a threshold.
