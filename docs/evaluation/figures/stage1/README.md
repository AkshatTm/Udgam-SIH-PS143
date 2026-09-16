# Stage 1 — the evidence set

*Owner: Soumirya. Regenerate with `python pipeline/detect/make_figures.py --pair updated`.*

**These figures describe ONE pair: `unet_e2c_sea_refonly` + `scene_classifier_l1_e2c_recall`,**
scored on the Zenodo Part III holdout. `--pair shipped` rebuilds the same nine for the previously
shipped models; both were scored on the same holdout, so switching changes which model is
documented, not what a caption may claim.

**Competing teams hardcode results. You cannot out-argue that verbally, because a verbal claim and
a fabricated claim sound identical across a table. You out-EVIDENCE it.** Every figure here is
rebuilt from a JSON file committed to this repo, and **every caption prints the path it came from
and the split it was measured on.** The caption is the deliverable; the chart is just how you read
it quickly.

Rules applied to all nine: **no figure without n · no percentage without its metric named · every
caption carries its source path and its split.**

## The DECK set — four figures

`python pipeline/detect/make_figures.py --pair updated --l2-split validation --core`

| # | file | carries |
|---|---|---|
| **F1.1** | `F1.1_layer1_scores.png` | Layer 1's numbers, with the confusion matrix behind them |
| **F1.2** | `F1.2_layer2_scores.png` | Layer 2's numbers — all eight definitions, so a comparison is like-for-like |
| **F1.3** | `F1.3_gate_ablation.png` | the gate earns its place — the one design decision worth a slide |
| **F1.4** | `F1.4_cerulean_agreement.png` | an **independent** detector agrees with us on five real incidents |

Numbered in **presentation order**. That is the whole scores-and-system story.
**F1.4 is the one competing teams cannot produce**, and it is worth more than another chart of our
own numbers.

## The appendix — `appendix/`, kept not deleted

| # | file | carries |
|---|---|---|
| A1 | `appendix/A1_pr_curve_and_gate.png` | the threshold was set on **validation**, not on the test set |
| A2 | `appendix/A2_coverage_cliff.png` | per-scene IoU by oil coverage — and **no demo case sits in the failure band** |
| A3 | `appendix/A3_second_polarisation_ablation.png` | the second polarisation lifts val F1 **0.346 → 0.643**, precision **5.8×** at identical recall |
| A4 | `appendix/A4_rule_margin.png` | on satellite cases `confidence` is a **rule margin** in dB — 12 detections, 7 clear / 5 marginal |
| A5 | `appendix/A5_oracle_ceiling.png` | a GT-informed oracle ceilings at **0.8446** |

Methodology and diagnosis. Kept because *"we have the working behind it"* answers a question even
when it is not a slide, and they rebuild in seconds.

**Two worth open in a second tab:** **A2** carries *"no case in the demo library sits in the failure
band"* — the protection if anyone presses on the weak coverage band. **A1** carries *"the threshold
was chosen on validation, not on the test set"*, which most published work cannot demonstrate.

## Naming

Figure identity is a **slug**; the number comes from which set it lands in
(`DECK_NUM` / `APPX_NUM` in `make_figures.py`). The old numbering left gaps once five figures came
out — F1.1, F1.3, F1.4, F1.6 — and a gap in a deck reads as a missing slide.

## Three things to say out loud, because the figure alone does not say them

**F1.2** — *"The threshold was chosen on a Parts I+II validation split under a recall floor, not on
the 450 test scenes. Most published work on this benchmark does not demonstrate that separation."*

**F1.4** — *"We report 0.452, the strictest of eight definitions. On the definition this
literature uses, same model and same pixels, we are at 0.696."* **Do not quote 0.696 as the
headline.** It exists to make comparison like-for-like, not to pick the flattering number.

**F1.5** — say **all three** parts or none: *138 of 150 scenes are at 0.61–0.76* · *pooled collapses
because 12 scenes above 30% coverage hold ~38% of all oil pixels* · ***no case in the demo library
sits in that band, measured.***

## One honest caveat, carried on the figure itself

**F1.2 does not plot the shipped model's PR curve.** That model was trained on the pre-14-Sept
cache, which was rebuilt with the corrected channel order, so its validation probabilities are not
recoverable. The curve is drawn from the reproducible `l1_e2c` classifier and the shipped model
appears as a single operating point computed from its own stored confusion matrix. Both are
labelled. Drawing the shipped curve on the new cache would be a fabrication.
