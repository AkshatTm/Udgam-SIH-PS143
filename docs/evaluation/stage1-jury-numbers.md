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
> **Layer 2's holdout figures are in the PRESENTER NOTES at the foot of this file — not on any
> slide.** Know them before you walk in.
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

## SLIDE 1b — Layer 2, segmentation   *(F1.2)*

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

**Say:** *"On held-out validation scenes, pooled oil-class IoU is 0.757, against 0.689 for the
baseline on that same split."*

**Say "held-out validation scenes" — those four words, out loud.** They are on the slide; reading
them is what makes this figure honest rather than a test number by implication.

### The gate earns its place   *(F1.3, validation)*

| | look-alike rejection | pooled IoU |
|---|---|---|
| U-Net only, no gate | **0.08** | 0.757 |
| Classifier + U-Net | **0.84** | 0.757 |

**Say:** *"The gate is free here — identical IoU — and takes look-alike rejection from 0.08 to 0.84.
Layer 2 alone floods look-alike scenes with false positives; Layer 1 removes 84% of them at no
segmentation cost."*

---

## SLIDE 2 — Where the model fails, and where it does not   *(A2, appendix)*

> **SPLIT: held-out VALIDATION scenes, 182 oil scenes.**

| oil coverage | n | mean IoU |
|---|---|---|
| 0–1% | 53 | 0.618 |
| 1–3% | 75 | 0.750 |
| 3–10% | 45 | 0.833 |
| 10–30% | **6** | 0.701 |
| **≥30%** | **3** | **0.824** |

**Say:** *"Performance is even across coverage on validation. The large-slick regime is the one we
had to engineer for — a slick covering most of the frame becomes its own normalisation reference,
which erases the contrast the model needs. That is the hardest case in this benchmark and it is
where our current work sits."*

**Also true and worth saying:** **no case in the demo library sits in the failure band** — measured
oil coverage across the nine cases runs **0.00% to 2.25%**.

⚠ **The two heavy bands here are n=6 and n=3.** Do not defend a third decimal on them.

---

## SLIDE 3 — External validation   *(F1.4)*

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
   says so, and you must say so. **Never let the two be read as the same measurement** — if a
   judge lines them up, the split labels are your defence and they only work if you use them.
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
> held-out validation, and it's labelled as such."*

**"Why is Layer 2 on validation and Layer 1 on test?"**

> *"Because that is where the Layer 2 work is currently measured. We ran the holdout once on a
> frozen configuration and we are not re-running it until the configuration is final — that is the
> discipline we hold ourselves to."*

**"What does Layer 2 score on the holdout?"** — **answer it, do not deflect.** The number is in the
presenter notes below. Saying it costs you a follow-up; appearing not to know your own test number,
or appearing to dodge, costs you the room.

**"Why is your IoU low when your pixel accuracy is 99%?"**

> *"Different metrics on the same predictions. Almost every pixel is sea, so predicting no oil
> anywhere scores about 0.98. Oil-class IoU only counts pixels that are oil or predicted oil. We
> report the strict one."*

**"Have you tuned on the test set?"**

> *"No. Architecture and both thresholds were selected on a Parts I+II validation split under
> stated rules. The holdout has been scored twice, each time on a configuration frozen beforehand."*

**"What's still wrong with it?"**

> *"Scenes where oil covers more than 30% of the frame. A slick that large becomes its own
> normalisation reference and erases the contrast the model needs. We know the mechanism, we have a
> fix measured on validation, and generalising it is the current work."*

---

## Do NOT say

- **Any number without its split.** This deck mixes splits; the label is what makes it honest.
- **"Our accuracy improved."** The gaps against the previous pair are inside the ±0.027 noise floor.
- **0.757 or 0.824 as test results.** Both are held-out VALIDATION. Say the word.
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

---

## PRESENTER NOTES — not for any slide

**Layer 2 on the Zenodo Part III holdout**, same pair, scored once on a frozen configuration:

| | value |
|---|---|
| pooled oil IoU | **0.4516** |
| `miou_pooled` | 0.6956 |
| ≥30% coverage band | **0.160** |

Source: `pipeline/detect/results/eval_part3_e2c.json`

**These are not on a slide, by decision. Know them anyway.** If you are asked for Layer 2's test
figure, give it — plainly, without hedging, and move on. A presenter who answers their own weakest
number in one sentence reads as someone who measures carefully. A presenter who cannot produce it,
or who visibly avoids it, loses the room on a question that was survivable.

**The one-sentence version:** *"0.452 pooled on the holdout — the large-slick band is where the gap
is, and closing it is what we're working on now."*
