"""
evaluate.py  -  The numbers.  Owner: Soum.   (docs/02_SOUM_DETECTION.md Phase 7)

    python pipeline/detect/evaluate.py --report

Everything here is measured on the Zenodo Part III holdout with a scene-level
split, and on nothing else. Part III is the dataset authors' designated test set
and this project never trains on it (decision D1).

Produces the ablation table:

  | Model                      | Scene acc | Look-alike rejection | Oil IoU |
  | Classical (depth-map + RF) |     -     |        ...           |    -    |
  | Classifier only            |    ...    |        ...           |    -    |
  | U-Net only (no gate)       |     -     |        ...           |   ...   |
  | Classifier + U-Net         |    ...    |        ...           |   ...   |

THE ROW THAT MATTERS IS THE DIFFERENCE BETWEEN THE LAST TWO
------------------------------------------------------------
"U-Net only" runs the segmenter on all 450 scenes. "Classifier + U-Net" runs it
only where Layer 1 said yes. The dataset's own authors report their U-Net
segments erroneously on look-alike images, so the gap between those two rows is
the measured value of the gate (D2) — and it is what makes demo cases 6 and 7,
whose entire purpose is for the system to say "no", actually work.

IoU IS REPORTED TWICE, DELIBERATELY
-----------------------------------
  oil-class IoU over POSITIVE scenes only  — how well we trace a slick we found
  oil-class IoU over ALL 450 scenes        — includes every false positive
                                             painted onto clean water
The first number is always prettier. Quoting it alone would be the kind of thing
we would not survive being asked about in December, so both ship.
"""
from __future__ import annotations

import argparse
import json
import os
import sys

import numpy as np
import rasterio

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.abspath(os.path.join(_HERE, "..", ".."))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from pipeline.detect.make_labels import _build_jobs                      # noqa: E402
from pipeline.detect import nets                                         # noqa: E402

CACHE = os.path.join(_ROOT, "data", "cache")
MODELS = os.path.join(_HERE, "models")
OUT_JSON = os.path.join(_HERE, "eval_part3.json")


def load_part3_scenes():
    """-> list of (scene_id, cls, img_path, mask_path)."""
    return _build_jobs("3")


def classical_row():
    """Read the classical baseline straight out of train.py's model_meta.json —
    recomputing it here would risk the two disagreeing."""
    p = os.path.join(MODELS, "model_meta.json")
    if not os.path.exists(p):
        return None
    m = json.loads(open(p).read())
    r = m.get("metrics_part3", {})
    return {"model": f"Classical ({m.get('feature_set','?')})",
            "scene_accuracy": None,
            "oil_recall": r.get("recall"),
            "lookalike_rejection": None,
            "precision": r.get("precision"), "f1": r.get("f1"),
            "scene_recall": r.get("scene_recall"),
            "iou_positives": None, "iou_all": None,
            "note": "row-level precision/recall/F1 on detected regions"}


def classifier_row():
    p = os.path.join(MODELS, "scene_classifier_meta.json")
    if not os.path.exists(p):
        return None, None
    m = json.loads(open(p).read())
    r = m["part3"]
    return {"model": "Classifier only",
            "scene_accuracy": r["scene_accuracy"],
            "oil_recall": r["oil_recall"],
            "lookalike_rejection": r["lookalike_rejection"],
            "cleanocean_rejection": r["cleanocean_rejection"],
            "precision": None, "f1": None, "scene_recall": None,
            "iou_positives": None, "iou_all": None,
            "note": "Layer 1 alone"}, m["threshold"]


def unet_rows(gate_threshold, use_gate_list=(False, True), limit=None):
    """Run the U-Net over Part III, ungated and gated, in one pass over the
    scenes — decoding 450 scenes twice would be pointless I/O."""
    clf, clf_thr = nets.load_classifier()
    unet, unet_thr = nets.load_unet()
    if unet is None:
        return [], None
    if clf is None and True in use_gate_list:
        print("  [skip] gated row: Layer 1 is not trained yet")
        use_gate_list = (False,)

    jobs = load_part3_scenes()
    if limit:
        jobs = jobs[:limit]

    acc = {g: {"inter_pos": 0.0, "union_pos": 0.0,
               "inter_all": 0.0, "union_all": 0.0,
               "pred_oil": 0, "gt_oil": 0,
               "look_fp": 0, "look_n": 0, "clean_fp": 0, "clean_n": 0,
               "oil_hit": 0, "oil_n": 0}
           for g in use_gate_list}

    for i, (scene_id, cls, img_path, msk_path) in enumerate(jobs, 1):
        with rasterio.open(img_path) as src:
            vv = src.read(1).astype(np.float32)
            vh = src.read(2).astype(np.float32) if src.count >= 2 else None
        norm, valid, _ = nets.normalise_scene(vv, vh)

        gt = np.zeros(vv.shape, bool)
        if cls == "Oil" and os.path.exists(msk_path):
            with rasterio.open(msk_path) as m:
                gt = m.read(1) > 0

        p_scene = nets.classify_scene(clf, norm) if clf is not None else 1.0
        prob = nets.segment_scene(unet, norm, valid)

        for gated in use_gate_list:
            a = acc[gated]
            if gated and p_scene < gate_threshold:
                pred = np.zeros_like(gt)
            else:
                pred = prob >= unet_thr

            inter = float((pred & gt).sum())
            union = float((pred | gt).sum())
            a["inter_all"] += inter
            a["union_all"] += union
            if cls == "Oil":
                a["inter_pos"] += inter
                a["union_pos"] += union
                a["oil_n"] += 1
                a["oil_hit"] += int(inter > 0)
            elif cls == "Lookalike":
                a["look_n"] += 1
                a["look_fp"] += int(pred.any())
            else:
                a["clean_n"] += 1
                a["clean_fp"] += int(pred.any())

        if i % 25 == 0 or i == len(jobs):
            print(f"  [{i:>3}/{len(jobs)}] {scene_id}", flush=True)

    rows = []
    for gated in use_gate_list:
        a = acc[gated]
        rows.append({
            "model": "Classifier + U-Net" if gated else "U-Net only (no gate)",
            "scene_accuracy": None,
            "oil_recall": round(a["oil_hit"] / max(a["oil_n"], 1), 4),
            "lookalike_rejection": round(1 - a["look_fp"] / max(a["look_n"], 1), 4),
            "cleanocean_rejection": round(1 - a["clean_fp"] / max(a["clean_n"], 1), 4),
            "precision": None, "f1": None, "scene_recall":
                f"{a['oil_hit']}/{a['oil_n']}",
            "iou_positives": round(a["inter_pos"] / max(a["union_pos"], 1), 4),
            "iou_all": round(a["inter_all"] / max(a["union_all"], 1), 4),
            "note": f"binarisation threshold {unet_thr}"})
    return rows, unet_thr


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--report", action="store_true")
    ap.add_argument("--limit", type=int, default=None, help="first N scenes — smoke test")
    ap.add_argument("--skip-unet", action="store_true")
    a = ap.parse_args()

    print("=" * 78)
    print("  PART III HOLDOUT — 450 scenes, scene-level split, never trained on")
    print("=" * 78)

    rows = []
    c = classical_row()
    if c:
        rows.append(c)
    else:
        print("  [skip] classical row: run train.py first")

    cl, gate_thr = classifier_row()
    if cl:
        rows.append(cl)
    else:
        print("  [skip] classifier row: run train_classifier.py first")
        gate_thr = 0.5

    if not a.skip_unet:
        ur, _ = unet_rows(gate_thr, limit=a.limit)
        rows.extend(ur)

    print()
    print("=" * 78)
    print("  ABLATION — every cell names its metric and its split")
    print("=" * 78)
    hdr = f"  {'Model':<24}{'SceneAcc':>10}{'LookRej':>9}{'OilRec':>8}{'IoU+':>8}{'IoUall':>8}"
    print(hdr)
    print("  " + "-" * (len(hdr) - 2))
    def f(v):
        return "   —  " if v is None else f"{v:.3f}"
    for r in rows:
        print(f"  {r['model']:<24}{f(r['scene_accuracy']):>10}"
              f"{f(r['lookalike_rejection']):>9}{f(r['oil_recall']):>8}"
              f"{f(r['iou_positives']):>8}{f(r['iou_all']):>8}")

    gated = next((r for r in rows if r["model"].startswith("Classifier + U-Net")), None)
    ungated = next((r for r in rows if r["model"].startswith("U-Net only")), None)
    if gated and ungated:
        print()
        print("  What the gate buys (decision D2):")
        print(f"    look-alike rejection  {ungated['lookalike_rejection']:.3f} "
              f"-> {gated['lookalike_rejection']:.3f}")
        print(f"    clean-ocean rejection {ungated['cleanocean_rejection']:.3f} "
              f"-> {gated['cleanocean_rejection']:.3f}")
        print(f"    IoU over all scenes   {ungated['iou_all']:.3f} "
              f"-> {gated['iou_all']:.3f}")
        print(f"    IoU over positives    {ungated['iou_positives']:.3f} "
              f"-> {gated['iou_positives']:.3f}   (the gate should barely move this)")

    with open(OUT_JSON, "w") as fh:
        json.dump({"split": "Zenodo Part III holdout, scene-level",
                   "gate_threshold": gate_thr, "rows": rows}, fh, indent=2)
    print(f"\n  wrote {OUT_JSON}")

    if a.report:
        print()
        print("  THE HONESTY PARAGRAPH (say this before anyone asks):")
        print("  On the dataset's own benchmark the authors report 99% classification")
        print("  accuracy and 96% IoU. We report ours on their designated held-out test")
        print("  set, the same split. On the harder Krestenitis look-alike benchmark,")
        print("  published state of the art is around 53%. The gap between those numbers")
        print("  is a measure of how much look-alike variety a dataset contains — that")
        print("  gap is our result, not our excuse.")


if __name__ == "__main__":
    main()
