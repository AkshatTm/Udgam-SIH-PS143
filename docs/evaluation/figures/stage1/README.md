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

| # | file | what it proves | source | split |
|---|---|---|---|---|
| F1.1 | `F1.1_layer1_confusion_matrix.png` | Layer 1: 139 TP / 15 FP / 11 FN / 285 TN → accuracy **0.942**, oil recall **0.927**, look-alike rejection **0.920**, clean-ocean rejection **0.980** | `models/scene_classifier_l1_e2c_recall_meta.json` | Part III holdout, 450 scenes |
| F1.2 | `F1.2_pr_curve_and_gate.png` | the decision threshold was set on **validation**, not on the test set | `models/scene_classifier_meta.json`, `models/scene_classifier_l1_e2c.pt` | validation slice of Parts I+II |
| F1.3 | `F1.3_gate_ablation.png` | the gate costs **0.008 IoU** and buys **0.60** look-alike rejection | `results/eval_part3_e2c.json` | Part III holdout, 450 scenes |
| F1.4 | `F1.4_eight_iou_definitions.png` | we report **0.452**, the strictest of eight definitions; the literature's definition gives **0.696** on the same pixels | `results/eval_part3_e2c.json` | Part III holdout, gated |
| F1.5 | `F1.5_coverage_cliff.png` | 138 of 150 scenes score 0.61–0.76; **12 scenes ≥30% coverage** drag pooled down — and **no demo case sits in that band** | `results/eval_part3_e2c.json`, `cases/*/detections.geojson` | Part III, 150 oil scenes |
| F1.6 | `F1.6_cerulean_agreement.png` | median IoU **0.483** vs an operational detector, recall **0.796–0.942** | `results/iou_cerulean.json` | five real incidents |
| F1.7 | `F1.7_second_polarisation_ablation.png` | the second polarisation lifts val F1 **0.346 → 0.643** and Part III precision **5.8×** at identical recall | `receipts.md` L104, `updates/soumirya.md` §622 | validation + Part III |
| F1.8 | `F1.8_rule_margin.png` | on satellite cases `confidence` is a **rule margin**, drawn in dB — 12 detections, **7 clear / 5 marginal** | `cases/*/detections.geojson` | the live case library |
| F1.9 | `F1.9_oracle_ceiling.png` | a GT-informed oracle ceilings at **0.8446**; we beat it on the three smallest bands | `results/oracle_ceiling.json`, `results/eval_part3_e2c.json` | oracle on 228 Parts I+II scenes — no Part III pixel read |

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
