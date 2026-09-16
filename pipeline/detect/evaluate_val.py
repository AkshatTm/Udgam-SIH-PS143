#!/usr/bin/env python3
"""
evaluate_val.py  —  the metric we are allowed to tune against.  (plan E0)

    python pipeline/detect/evaluate_val.py --fold 0
    python pipeline/detect/evaluate_val.py --all-folds

WHAT THIS IS FOR
----------------
Part III is the holdout. It gets run ONCE, at the end, on one configuration chosen
entirely here. Tune against Part III at every stage and by the third stage you have
fitted it and the final number means nothing.

So this is the stand-in: whole-scene tiled inference over held-out **Parts I+II**
scenes, using `split.py`'s coverage-stratified split, reported with exactly the
decomposition `evaluate.py` prints for Part III.

WHY IT IS NOT `train_unet.py`'s VALIDATION IoU
----------------------------------------------
Two differences, and both of them matter:

1. **Population.** The old split put 1 scene >=30% coverage and 3 at 10-30% into
   validation. Those bands carry ~75% of Part III's oil pixels. `split.py` fixes it.

2. **Unit.** `train_unet.py` scores pooled IoU over curated 256px TILES — the 12
   richest positives per scene plus matched negatives. Part III scores pooled IoU
   over whole 2048x2048 SCENES. The tile population is enormously enriched in oil,
   so the two are not the same quantity, and a threshold swept on tiles is
   systematically too low for whole-scene inference. That difference alone accounts
   for part of the 0.679-vs-0.435 gap that was previously read as generalisation
   failure.

This runs `nets.segment_scene` — the real inference path, 50% overlap and cosine
windowing — so what is measured here is what would ship.
"""
from __future__ import annotations

import argparse
import json
import os
import sys

import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.abspath(os.path.join(_HERE, "..", ".."))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from pipeline.detect.make_labels import _build_jobs                      # noqa: E402
from pipeline.detect import evaluate as ev                               # noqa: E402
from pipeline.detect.split import load_manifest, make_split, coverage_band  # noqa: E402

OUT_JSON = os.path.join(_HERE, "eval_val.json")


def val_jobs(fold=0, limit=None):
    """-> (jobs, val_ids). Jobs are (scene_id, cls, img, mask) for the held-out
    Parts I+II scenes only — the same tuple shape evaluate.unet_rows expects."""
    scenes = load_manifest()
    _, val_ids, _ = make_split(scenes, fold=fold)
    keep = set(val_ids)
    jobs = [j for j in _build_jobs("1,2") if j[0] in keep]
    if limit:
        jobs = jobs[:limit]
    return jobs, val_ids


def run_fold(fold, gate_thr, limit=None, ckpt=None, clf=None):
    jobs, val_ids = val_jobs(fold, limit)
    n_oil = sum(1 for j in jobs if j[1] == "Oil")
    print(f"\n=== fold {fold}: {len(jobs)} held-out scenes ({n_oil} oil) ===", flush=True)
    rows, _ = ev.unet_rows(gate_thr, jobs=jobs, ckpt=ckpt, clf_path=clf)
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fold", type=int, default=0)
    ap.add_argument("--all-folds", action="store_true",
                    help="rotate the >=30% band through all 3 folds and report the spread")
    ap.add_argument("--limit", type=int, default=None, help="smoke test")
    ap.add_argument("--ungated", action="store_true",
                    help="report the U-Net-only row instead of the gated one. REQUIRED "
                         "when comparing U-Net changes across a cache rebuild: the "
                         "Layer 1 classifier is trained on the OLD convention, and on "
                         "the new one it returns P(oil) 0.001-0.010 against a 0.143 "
                         "threshold, so the gate closes on every scene and the gated "
                         "row reads 0.0000 no matter how good Layer 2 is.")
    ap.add_argument("--ckpt", default=None,
                    help="explicit U-Net checkpoint; default is models/unet.pt")
    ap.add_argument("--clf", default=None,
                    help="explicit Layer 1 checkpoint for the GATED row. Without "
                         "this the gate uses the SHIPPED classifier, which is "
                         "trained on the old convention and closes on every scene - "
                         "so a gated number computed against a new-convention U-Net "
                         "reads 0.0000 no matter how good Layer 2 is.")
    ap.add_argument("--json", default=None)
    a = ap.parse_args()

    _, gate_thr = ev.classifier_row(a.clf)
    if gate_thr is None:
        gate_thr = 0.5
    if not a.ungated:
        print(f"  GATE: classifier={a.clf or 'models/scene_classifier.pt (SHIPPED)'} "
              f"threshold={gate_thr}")

    folds = range(3) if a.all_folds else [a.fold]
    out = {}
    for f in folds:
        rows = run_fold(f, gate_thr, a.limit, a.ckpt, a.clf)
        want = "U-Net only" if a.ungated else "Classifier + U-Net"
        shipped = next((r for r in rows if r["model"].startswith(want)), None)
        if shipped:
            out[f] = shipped

    print()
    print("=" * 78)
    print("  VALIDATION SCENES — tune against THIS, never against Part III")
    print("=" * 78)
    print(f"{'fold':<6}{'pooled IoU':>12}{'95% CI':>20}{'macro/scene':>13}{'mean IoU':>10}")
    print("-" * 62)
    pooled = []
    for f, r in out.items():
        md = r.get("metric_decomposition", {})
        p = md.get("iou_oil_pooled", {}).get("value")
        ci = md.get("pooled_ci95", {}).get("ci") or (None, None)
        ms = md.get("iou_oil_macro_scene", {}).get("value")
        mi = md.get("miou_pooled", {}).get("value")
        cis = f"[{ci[0]:.3f}, {ci[1]:.3f}]" if ci[0] is not None else "     —"
        print(f"{f:<6}{p if p is None else f'{p:.4f}':>12}{cis:>20}"
              f"{ms if ms is None else f'{ms:.4f}':>13}{mi if mi is None else f'{mi:.4f}':>10}")
        if p is not None:
            pooled.append(p)
    if len(pooled) > 1:
        print(f"\n  across folds: mean {np.mean(pooled):.4f}  spread "
              f"{max(pooled)-min(pooled):.4f}")
        print("  Do not act on a difference smaller than that spread.")

    # The band table is the diagnostic that matters — it is where the failure lives.
    for f, r in out.items():
        md = r.get("metric_decomposition", {})
        bands = md.get("iou_by_slick_size", {}).get("value") or {}
        if not bands:
            continue
        print(f"\n  fold {f} — per-scene IoU by oil coverage:")
        for b, st in bands.items():
            mi = "  n/a" if st["mean_iou"] is None else f"{st['mean_iou']:.4f}"
            print(f"    {b:<16} n={st['n']:>3}   mean IoU {mi}")

    path = a.json or OUT_JSON
    json.dump({"split": "Parts I+II held out, coverage-stratified (split.py)",
               "folds": {str(k): v for k, v in out.items()}},
              open(path, "w", encoding="utf-8"), indent=2)
    print(f"\n  wrote {path}")


if __name__ == "__main__":
    main()
