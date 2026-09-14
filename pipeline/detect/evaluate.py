"""
evaluate.py  -  The numbers.  Owner: Soumirya.   (docs/team/soumirya-stage1-detection.md Phase 7)

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
OUT_JSON = os.path.join(_HERE, "results", "eval_part3.json")


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


TILE = 256


def _wrap(text, width):
    """Tiny word-wrap so each definition prints beside its number."""
    words, lines, cur = text.split(), [], ""
    for w in words:
        if len(cur) + len(w) + 1 > width:
            lines.append(cur)
            cur = w
        else:
            cur = f"{cur} {w}".strip()
    if cur:
        lines.append(cur)
    return lines


def _accumulate_decomposition(a, pred, gt, valid):
    """Accumulate everything the metric decomposition needs, for ONE positive scene.

    Called only on Oil scenes. Costs no extra I/O — the masks are already in hand.
    """
    a["inter_bg"] += float((~pred & ~gt).sum())
    a["union_bg"] += float((~pred | ~gt).sum())
    a["correct_px"] += float((pred == gt).sum())
    a["total_px"] += float(gt.size)
    a["pred_sum"] += float(pred.sum())
    a["gt_sum"] += float(gt.sum())
    if valid is not None:
        a["invalid_px"] += float((~valid).sum())

    union = float((pred | gt).sum())
    if union:                       # a positive scene always has gt, so always true
        a["scene_ious"].append(float((pred & gt).sum()) / union)
        # Keep the oil FRACTION beside each scene's IoU. Pooled IoU weights a scene by
        # its slick size, macro-per-scene weights every scene equally, and the two differ
        # by 0.25 here — so which scenes we fail on is the whole explanation, and it is
        # only answerable if the pairing is recorded rather than inferred.
        a["scene_oil_frac"].append(float(gt.sum()) / float(gt.size))
        a["scene_iu"].append((float((pred & gt).sum()), union))

    h, w = gt.shape
    for r0 in range(0, h - TILE + 1, TILE):
        for c0 in range(0, w - TILE + 1, TILE):
            g = gt[r0:r0 + TILE, c0:c0 + TILE]
            if not g.any():         # "oil tiles" only — see decompose()
                continue
            p = pred[r0:r0 + TILE, c0:c0 + TILE]
            u = float((p | g).sum())
            if u:
                a["tile_ious"].append(float((p & g).sum()) / u)


def bootstrap_pooled(scene_iu, n=2000, seed=0):
    """Scene-level bootstrap CI for POOLED IoU -> (lo, hi) at 95%.

    Pooled IoU weights a scene by its slick size, so a handful of scenes dominate:
    on Part III the single largest scene is ~5% of the number and the top twelve are
    ~38%. A point estimate quoted to three decimals is therefore overclaiming.
    Resample SCENES (not pixels) with replacement — the scene is the unit of
    independence here, because tiles within a scene share a slick.
    """
    if not scene_iu:
        return None, None
    rng = np.random.default_rng(seed)
    iu = np.asarray(scene_iu, dtype=float)
    idx = rng.integers(0, len(iu), size=(n, len(iu)))
    inter = iu[idx, 0].sum(axis=1)
    union = iu[idx, 1].sum(axis=1)
    vals = np.divide(inter, union, out=np.zeros_like(inter), where=union > 0)
    return float(np.percentile(vals, 2.5)), float(np.percentile(vals, 97.5))


def _bands(ious, fracs):
    """Mean per-scene IoU inside oil-fraction bands -> {band: {n, mean_iou}}."""
    edges = [(0.00, 0.01), (0.01, 0.03), (0.03, 0.10), (0.10, 0.30), (0.30, 1.01)]
    out = {}
    for lo, hi in edges:
        sel = [i for i, f in zip(ious, fracs) if lo <= f < hi]
        out[f"{lo*100:.0f}-{hi*100:.0f}% oil"] = {
            "n": len(sel),
            "mean_iou": round(float(np.mean(sel)), 4) if sel else None}
    return out


def decompose(a):
    """Turn the accumulators into named metrics, each with its definition.

    WHY THIS EXISTS. We report 0.435 and the dataset's authors report 96% IoU.
    Before any slide claims that gap is model quality, it has to be established
    that the two numbers measure the same thing — and the evidence says they do
    not. The authors quote "99% accuracy" beside their 96%, and at the 2-4% oil
    pixel rate in this dataset, predicting ALL BACKGROUND already scores 96-98%
    accuracy. So their accuracy is background-inclusive, and an "IoU" quoted
    beside it is very likely mean-IoU over {background, oil} rather than the
    oil class alone.

    Every number below is on the SAME model, SAME pixels, SAME split. Only the
    definition changes. That is the point.
    """
    def d(x, y):
        return round(x / y, 4) if y else None

    iou_oil = d(a["inter_pos"], a["union_pos"])
    iou_bg = d(a["inter_bg"], a["union_bg"])
    miou = round((iou_oil + iou_bg) / 2, 4) if (iou_oil is not None and iou_bg is not None) else None
    return {
        "iou_oil_pooled": {
            "value": iou_oil,
            "definition": "oil class only; intersection and union POOLED over whole "
                          "positive scenes; background excluded from numerator and "
                          "denominator. The strictest of these, and what we report."},
        "iou_background_pooled": {
            "value": iou_bg,
            "definition": "background class only, same pooling. Near 1.0 because "
                          "background is 96-98% of every scene."},
        "miou_pooled": {
            "value": miou,
            "definition": "mean IoU over {background, oil}. THE AUTHORS' LIKELY "
                          "DEFINITION — it is what 'IoU' usually means in a "
                          "segmentation paper quoting accuracy beside it."},
        "pixel_accuracy_positives": {
            "value": d(a["correct_px"], a["total_px"]),
            "definition": "pixels classified correctly, over POSITIVE scenes only. "
                          "The strict population: every scene here actually contains "
                          "oil, so background-guessing earns less."},
        "pixel_accuracy_all450": {
            "value": d(a["correct_px_all"], a["total_px_all"]),
            "definition": "pixels classified correctly over ALL 450 scenes. The "
                          "authors quote '99% accuracy' without naming the population, "
                          "and the 300 negative scenes are nearly free marks, so this "
                          "is the more likely match for their figure. Both are measured "
                          "because guessing which one they meant is not evidence."},
        "dice_oil_pooled": {
            "value": d(2 * a["inter_pos"], a["pred_sum"] + a["gt_sum"]),
            "definition": "Dice / F1 on the oil class, pooled. Always >= IoU; "
                          "Dice = 2*IoU/(1+IoU)."},
        "iou_oil_macro_scene": {
            "value": round(float(np.mean(a["scene_ious"])), 4) if a["scene_ious"] else None,
            "definition": f"oil IoU computed PER SCENE then averaged over the "
                          f"{len(a['scene_ious'])} positive scenes. Differs from pooled "
                          f"because pooling lets the largest slicks dominate.",
            "n": len(a["scene_ious"])},
        "iou_oil_macro_tile": {
            "value": round(float(np.mean(a["tile_ious"])), 4) if a["tile_ious"] else None,
            "definition": f"oil IoU per {TILE}x{TILE} tile, averaged over the "
                          f"{len(a['tile_ious'])} tiles that CONTAIN oil. Easier again: "
                          f"a tile with oil in it is a pre-localised problem. A plausible "
                          f"alternative reading of the authors' number.",
            "n": len(a["tile_ious"])},
        "iou_by_slick_size": {
            "value": _bands(a["scene_ious"], a["scene_oil_frac"]),
            "definition": "mean per-scene oil IoU, split by how much of the scene is "
                          "oil. Pooled IoU weights a scene by its slick size, so if the "
                          "big slicks are the weak ones, pooled collapses while "
                          "macro-per-scene does not. This says whether that is what "
                          "is happening."},
        "pooled_ci95": {
            "value": None,
            "ci": bootstrap_pooled(a["scene_iu"]),
            "definition": "95% scene-level bootstrap interval on iou_oil_pooled. "
                          "Quote the interval, not the third decimal of the point "
                          "estimate — a few large scenes dominate the pooled number."},
        "invalid_px_fraction": {
            "value": d(a["invalid_px"], a["total_px"]),
            "definition": "share of pixels masked invalid (land/NaN) across positive "
                          "scenes. Reported so nobody wonders whether the background "
                          "numbers are inflated by masked-out area."},
    }


def unet_rows(gate_threshold, use_gate_list=(False, True), limit=None, jobs=None,
              ckpt=None):
    """Run the U-Net over Part III, ungated and gated, in one pass over the
    scenes — decoding 450 scenes twice would be pointless I/O."""
    clf, clf_thr = nets.load_classifier()
    unet, unet_thr = nets.load_unet(ckpt)
    if unet is None:
        return [], None
    if clf is None and True in use_gate_list:
        print("  [skip] gated row: Layer 1 is not trained yet")
        use_gate_list = (False,)

    # jobs=None means the Part III holdout. evaluate_val.py passes its own list so
    # the validation number and the headline number cannot drift apart — the same
    # argument that put normalisation in one file.
    jobs = load_part3_scenes() if jobs is None else jobs
    if limit:
        jobs = jobs[:limit]

    acc = {g: {"inter_pos": 0.0, "union_pos": 0.0,
               "inter_all": 0.0, "union_all": 0.0,
               "pred_oil": 0, "gt_oil": 0,
               "look_fp": 0, "look_n": 0, "clean_fp": 0, "clean_n": 0,
               "oil_hit": 0, "oil_n": 0,
               # --- metric decomposition (see decompose() and the block in main) ---
               # Everything below is accumulated over POSITIVE scenes only, in the
               # same single pass, so none of it costs extra I/O.
               "inter_bg": 0.0, "union_bg": 0.0,     # background treated as a class
               "correct_px": 0.0, "total_px": 0.0,   # for pixel accuracy
               "pred_sum": 0.0, "gt_sum": 0.0,       # for Dice
               "scene_ious": [],                     # macro: one IoU per scene
               "scene_oil_frac": [],                 # paired oil fraction per scene
               "scene_iu": [],                       # (inter, union) per scene, for the CI
               "tile_ious": [],                      # macro: one IoU per oil TILE
               "invalid_px": 0.0,
               # Pixel accuracy over ALL 450 scenes, not just positives. The authors
               # quote "99% accuracy" without naming the population, and the two
               # populations give very different answers, so both are measured rather
               # than one being estimated from the other.
               "correct_px_all": 0.0, "total_px_all": 0.0}
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
            a["correct_px_all"] += float((pred == gt).sum())
            a["total_px_all"] += float(gt.size)
            if cls == "Oil":
                a["inter_pos"] += inter
                a["union_pos"] += union
                a["oil_n"] += 1
                a["oil_hit"] += int(inter > 0)
                _accumulate_decomposition(a, pred, gt, valid)
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
            "note": f"binarisation threshold {unet_thr}",
            "metric_decomposition": decompose(a)})
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

    # ---- the metric decomposition (section E5 item 3) -----------------------
    shipped = next((r for r in rows if r["model"].startswith("Classifier + U-Net")), None)
    if shipped and shipped.get("metric_decomposition"):
        md = shipped["metric_decomposition"]
        print()
        print("=" * 78)
        print("  WHY 0.435 AND 96% ARE NOT THE SAME MEASUREMENT")
        print("=" * 78)
        print("  Same model, same pixels, same split. Only the DEFINITION changes.")
        print("  Reported so the gap can be decomposed instead of hand-waved.")
        print()
        for key, m in md.items():
            v = m["value"]
            if m.get("ci") is not None and m["ci"][0] is not None:
                lo, hi = m["ci"]
                print(f"  {key:<26} [{lo:.4f}, {hi:.4f}]")
            elif isinstance(v, dict):
                print(f"  {key:<26}")
                for band, s in v.items():
                    mi = "  n/a" if s["mean_iou"] is None else f"{s['mean_iou']:.4f}"
                    print(f"      {band:<16} n={s['n']:>3}   mean IoU {mi}")
            else:
                print(f"  {key:<26} {'  n/a' if v is None else f'{v:.4f}'}")
            for line in _wrap(m["definition"], 68):
                print(f"      {line}")
            print()
        print("  WHAT THE MEASUREMENT ACTUALLY SAID (13 Sept, 450 scenes):")
        print("  1. DEFINITION explains about half the gap. Oil-only pooled 0.435 vs")
        print("     mean-IoU-over-both-classes 0.687 is the SAME predictions scored two")
        print("     ways. Pixel accuracy over all 450 scenes is 0.980 against the")
        print("     authors' quoted 99% - close, so accuracy is roughly comparable and")
        print("     the IoU definitions are very likely not.")
        print("  2. POOLING explains most of the rest. Pooled 0.435 vs per-scene mean")
        print("     0.683, again identical predictions. Pooling weights each scene by")
        print("     its slick size.")
        print("  3. WHAT IS LEFT IS A REAL DEFECT, AND IT IS NARROW. Look at the size")
        print("     bands: 138 of 150 scenes sit at 0.66-0.78, and the 12 scenes where")
        print("     oil covers more than 30% of the frame score 0.085. Those 12 hold a")
        print("     large share of all oil pixels, which is why pooled collapses. The")
        print("     cause is known: per-scene MAD normalisation lets a slick that big")
        print("     become its own median, erasing the contrast the model needs.")
        print()
        print("  So the model is not broadly weak - it fails on one identifiable class")
        print("  of scene. NOT a reason to quote 0.687. WE KEEP REPORTING 0.435: it is")
        print("  the strictest and the honest one. The others exist so the comparison is")
        print("  like-for-like, NOT so we can pick the flattering number (B2).")

    out_path = OUT_JSON
    if a.limit:
        # A smoke run must never overwrite the authoritative numbers. It did once,
        # silently, and the 450-scene results had to be restored from git.
        out_path = OUT_JSON.replace(".json", "_smoke.json")
        print(f"\n  [--limit {a.limit}] PARTIAL RUN — these numbers are NOT the "
              f"Part III result.")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump({"split": "Zenodo Part III holdout, scene-level",
                   "n_scenes": a.limit or 450,
                   "partial": bool(a.limit),
                   "gate_threshold": gate_thr, "rows": rows}, fh, indent=2)
    print(f"\n  wrote {out_path}")

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
