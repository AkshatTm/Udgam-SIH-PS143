# Stage 1 — numbers for the jury round

*Owner: Soumirya. Every figure is measured and traceable to a file named beside it.*

> ## READ THIS FIRST
>
> **One pair:** `unet_e2c_sea_refonly` + `scene_classifier_l1_e2c_recall`.
>
> **The two layers are reported on DIFFERENT SPLITS, deliberately:**
>
> | | split | n |
> |---|---|---|
> | **Layer 1** | Zenodo Part III **HOLDOUT** | 450 scenes |
> | **Layer 2** | held-out **VALIDATION** (Parts I+II, fold 0) | 388 scenes, 182 oil |
>
> **Every slide states its split, and so must you.** A mixed-split deck is defensible; an
> unlabelled one is not, and the labelling is the only thing keeping it defensible.
>
> **The number you will be asked for:** Layer 2 on the Part III holdout is **pooled oil IoU
> 0.4516**, with the ≥30% band at **0.160**. Have it ready. It is the first thing a technical
> judge asks when a split label says "validation".
>
> Regenerate: `python pipeline/detect/make_figures.py --pair updated --l2-split validation`

---

## SLIDE 1a — Layer 1, scene classifier   *(F1.1)*

> **SPLIT: Zenodo Part III HOLDOUT — 450 scenes, scene-level, never trained on.**
> Source: `pipeline/detect/models/scene_classifier_l1_e2c_recall_meta.json`

| metric | value |
|---|---|
| scene classification accuracy | **0.942** |
| oil recall (150 oil scenes) | **0.927** |
| look-alike rejection (150 scenes) | **0.920** |
| clean-ocean rejection (150 scenes) | **0.980** |

Confusion matrix: **139 TP · 15 FP · 11 FN · 285 TN**

**Say:** *"This is the sealed holdout — 450 scenes the model never trained on. The decision
threshold, 0.128, was chosen on a Parts I+II validation split by a stated rule: the lowest
threshold holding validation precision above 0.95. Not on these test scenes. Most published work on
this benchmark does not demonstrate that separation."*

---

## SLIDE 1b — Layer 2, segmentation   *(F1.4)*

> **SPLIT: held-out VALIDATION scenes — Parts I+II, 388 scenes, fold 0.**
> Source: `pipeline/detect/results/eval_val_e2c_gated_recall.json`
> **This is not the test set. Say "validation" out loud when it goes up.**

| definition | value |
|---|---|
| `iou_oil_pooled` — **what we report** | **0.757** |
| `iou_oil_macro_tile` | 0.634 |
| `dice_oil_pooled` | 0.862 |
| `iou_oil_macro_scene` | 0.732 |
| **`miou_pooled`** {background, oil} | **0.874** |
| `iou_background_pooled` | 0.990 |
| `pixel_accuracy_positives` | 0.991 |
| **baseline on the SAME split**, for reference | **0.689** |

**Say, including the last sentence:** *"On held-out validation scenes, pooled oil-class IoU is
0.757, against 0.689 for the baseline on that same split. These are validation figures — on the
sealed Part III holdout this pair scores 0.452."*

**Do not drop that last clause.** The split label is on the slide; if you don't read it out, someone
else will, and then you're answering it on the back foot instead of having volunteered it.

### The gate earns its place   *(F1.3, validation)*

| | look-alike rejection | pooled IoU |
|---|---|---|
| U-Net only, no gate | **0.08** | 0.757 |
| Classifier + U-Net | **0.84** | 0.757 |

**Say:** *"The gate is free here — identical IoU — and takes look-alike rejection from 0.08 to 0.84.
Layer 2 alone floods look-alike scenes with false positives; Layer 1 removes 84% of them at no
segmentation cost."*

---

## SLIDE 2 — Where the model fails, and where it does not   *(F1.5)*

> **SPLIT: held-out VALIDATION scenes, 182 oil scenes.**

| oil coverage | n | mean IoU |
|---|---|---|
| 0–1% | 53 | 0.618 |
| 1–3% | 75 | 0.750 |
| 3–10% | 45 | 0.833 |
| 10–30% | **6** | 0.701 |
| **≥30%** | **3** | **0.824** |

**Say:** *"Performance is even across coverage — the large-slick regime is the one we had to fix,
and on validation it reaches 0.82. On the sealed holdout that band is still 0.16, so the fix has
not transferred yet. That gap is our current work."*

**The honest framing, and it is the strongest thing on this slide:** we identified a specific
failure mode, fixed it in development, tested it on a sealed holdout, and it did not transfer.
Saying that is what separates a measured system from a tuned demo.

**Also true and worth saying:** **no case in the demo library sits in the failure band** — measured
oil coverage across the nine cases runs **0.00% to 2.25%**.

⚠ **The two heavy bands here are n=6 and n=3.** Do not defend a third decimal on them.

---

## SLIDE 3 — External validation   *(F1.6)*

> **Against Cerulean (SkyTruth's operational detector), five real incidents.**
> Source: `pipeline/detect/results/iou_cerulean.json`

| | value |
|---|---|
| median IoU | **0.483** |
| range | 0.165 – 0.728 |
| recall on their polygon | **0.796 – 0.942** |

**Say:** *"Recall is high and uniform — we find the slick on all five, and draw it larger. IoU here
is limited by over-extent, not by misses. And this is agreement between two independent detectors,
not accuracy against ground truth: SkyTruth state plainly that SAR alone cannot definitively
identify oil, so we say it too."*

`case-gulf-alaska-2023` was classed **AMBIGUOUS by Cerulean's own human reviewer** — a poor IoU
there is the expected result, and is reported rather than hidden.

> **For you, not the slide:** this runs on the **classical** detector, which is what produces the
> nine bundles on screen. It is independent of which Layer 2 the accuracy slides describe.

---

## Things to know that are NOT slide material

1. **The two layers are on different splits.** Layer 1 holdout, Layer 2 validation. Every slide
   says so. If a judge lines them up and asks why, the answer is: *"Layer 2's holdout figure is
   0.452; we're showing validation because it's where our current work is measured, and we've
   labelled it."* That answer works. Pretending the splits match does not.
2. **Against the previously shipped pair, the differences are inside the noise.** Layer 2 holdout
   0.435 → 0.452; Layer 1 accuracy 0.951 → 0.942. Measured seed-to-seed variation is **±0.027
   pooled**. **Never say "our accuracy improved."** These are our numbers, not better numbers.
3. **Neither Layer 2 produces the detections on screen.** All nine demo bundles come from the
   **classical** path (D33 routing). The accuracy slides describe benchmark performance; the map
   shows the classical detector. Say exactly that if asked — it is a design choice, not an omission.
4. **Part III has been scored twice** in this project's life, each time on a configuration frozen
   beforehand, never tuned against.

---

## The questions you will be asked, and the answers

**"Is that your test set or your validation set?"**

> *"Layer 1 is the test set — the 450-scene Zenodo Part III holdout. Layer 2 on that slide is
> validation, and it's labelled. Layer 2's holdout number is 0.452 pooled oil IoU."*

**"Why is Layer 2 on validation and Layer 1 on test?"**

> *"Because that's where the Layer 2 work is currently measured. The holdout figure is 0.452. We
> ran the holdout once on a frozen configuration and we're not re-running it until the
> configuration is final — that's the discipline, not an evasion."*

**"Why is your IoU low when your pixel accuracy is 99%?"**

> *"Different metrics on the same predictions. Almost every pixel is sea, so predicting no oil
> anywhere scores about 0.98. Oil-class IoU only counts pixels that are oil or predicted oil. We
> report the strict one."*

**"Have you tuned on the test set?"**

> *"No. Architecture and both thresholds were selected on a Parts I+II validation split under
> stated rules. The holdout has been scored twice, each time on a configuration frozen beforehand."*

**"What's still wrong with it?"**

> *"Scenes where oil covers more than 30% of the frame. We know the mechanism, we have a fix that
> reaches 0.82 on that band on validation, and it reaches only 0.16 on the holdout. It hasn't
> transferred yet, and we're not quoting it as a result until it does."*

---

## Do NOT say

- **Any number without its split.** This deck mixes splits; the label is what makes it honest.
- **"Our accuracy improved."** The gaps against the previous pair are inside the ±0.027 noise floor.
- **0.757 or 0.824 as test results.** Both are validation. The holdout figures are **0.452** and
  **0.160**.
- "Look-alike rejection 0.960" — a dead pre-augmentation checkpoint. This pair is **0.920** on the
  holdout.
- "VH is the discriminator" — the feature was computed from the co-pol band. Say *"adding a second
  polarisation lifts validation F1 0.346 → 0.643 and Part III precision 5.8× at identical recall."*
- "The networks don't transfer to real exports" — false; that was a channel swap.
- **"Dark vessel"** for anything Stage 1 emits. Every contact is **unattributed** — it becomes a
  dark-vessel claim only after Stage 3 fails to match it to AIS.
- Stale contact counts. Land-masked 16 Sept with a real coastline: **Ennore 72 → 41**,
  `lookalike-zenodo` 1 → 0, total **142 → 110**. Huntington (43), Mumbai (21), Jamnagar (3) and
  Jacksonville (2) are unchanged — those boxes are 0.0–0.7% land, so they were never land returns.
- Alaska has **zero** contacts and that is correct — a field-of-view limit, not a threshold.
