# Stage 1 — evaluation artefacts

Generated files, committed on purpose. `.gitignore` argues the case: we ship code, not weights,
so **the training scripts and the metric files are the reproducible artefact**. Every Stage 1
number that reaches a slide is copied from one of these, never remembered.

These are outputs. Regenerate them with the command in the table; do not hand-edit one to change
a number.

| File | Produced by | What it holds |
|---|---|---|
| `eval_part3.json` | `python pipeline/detect/evaluate.py` | The Zenodo Part III holdout result, scene-level split. Carries `split`, `n_scenes`, `gate_threshold` and per-scene rows. A `--limit` run writes `eval_part3_smoke.json` instead, so a smoke run can never overwrite the authoritative numbers. |
| `eval_summary.csv` | `python pipeline/detect/eval_gt.py <data-root>` | One row per Part III scene from the classical v2 detector. Tune on Oil scenes 0–74, report on 75–149 — never tune and report on the same scenes. |
| `iou_cerulean.json` | `python pipeline/detect/iou_cerulean.py --all --json pipeline/detect/results/iou_cerulean.json` | Overlap between our polygon and SkyTruth Cerulean's for the same feature. **Agreement with another algorithm, not accuracy against ground truth** — see `docs/evaluation/README.md`. |
| `oracle_ceiling.json` | `python pipeline/detect/oracle_ceiling.py` | Upper bound on what the current representation can achieve, Parts I+II, weighted by Part III band oil mass. |
| `audit_shortcut.json` | `python pipeline/detect/audit_shortcut.py` | Shortcut audit — whether the classifier is separating oil or separating something correlated with it. |

Interpretation and the honesty rules that govern how these may be quoted:
[`docs/evaluation/README.md`](../../../docs/evaluation/README.md) and
[`docs/evaluation/stage1-accuracy-programme.md`](../../../docs/evaluation/stage1-accuracy-programme.md).
