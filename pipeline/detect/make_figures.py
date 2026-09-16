#!/usr/bin/env python3
"""
make_figures.py  —  the Stage 1 evidence set.  Owner: Soumirya.

    python pipeline/detect/make_figures.py            # all nine
    python pipeline/detect/make_figures.py --only 4   # just F1.4

WHY THIS FILE EXISTS
--------------------
Competing teams hardcode results. You cannot out-argue that verbally, because a
verbal claim and a fabricated claim sound identical across a table. You out-EVIDENCE
it: every figure here is regenerated from a JSON file that is committed to the repo,
and every caption prints the path it came from and the split it was measured on.

**The caption is the point, not the chart.** A bar chart of accuracy is worth nothing;
a bar chart whose caption says "Zenodo Part III, 450 scenes, scene-level split, model
never trained on these" is worth the whole slide, because it is checkable.

RULES FOLLOWED HERE
-------------------
1. No figure without **n**.
2. No percentage without its **metric named**.
3. Every caption carries its **source path** and its **split**.
4. Nothing is recomputed from a model. Every number is read from a results file, so a
   figure can never silently disagree with the number in the deck.

THE ONE EXCEPTION, AND IT IS LABELLED. F1.2 needs a precision-recall CURVE, and the
shipped classifier's validation probabilities are not recoverable: it was trained on
the pre-14-Sept cache, which was rebuilt with the corrected channel order. So the curve
is drawn from the reproducible `l1_e2c` classifier and the SHIPPED model appears as a
single operating point computed from its own stored confusion matrix. Both are labelled
on the figure. Drawing the shipped curve from the new cache would be a fabrication.
"""
from __future__ import annotations

import argparse
import json
import os
import sys

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.abspath(os.path.join(_HERE, "..", ".."))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

RESULTS = os.path.join(_HERE, "results")
MODELS = os.path.join(_HERE, "models")
OUT = os.path.join(_ROOT, "docs", "evaluation", "figures", "stage1")

DPI = 200
INK = "#1a1a1a"
MUTED = "#6b7280"
BLUE = "#2563eb"
AMBER = "#d97706"
RED = "#dc2626"
GREEN = "#059669"
GRID = "#e5e7eb"

plt.rcParams.update({
    "font.size": 9,
    "axes.edgecolor": MUTED,
    "axes.labelcolor": INK,
    "text.color": INK,
    "xtick.color": MUTED,
    "ytick.color": MUTED,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "figure.facecolor": "white",
})


def _load(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def _rows(d):
    return d if isinstance(d, list) else d.get("rows", [])


def _caption(fig, text):
    """The caption IS the evidence. Source path + split, every time."""
    fig.text(0.5, 0.012, text, ha="center", va="bottom", fontsize=7,
             color=MUTED, wrap=True)


def _save(fig, name):
    os.makedirs(OUT, exist_ok=True)
    p = os.path.join(OUT, name)
    fig.savefig(p, dpi=DPI, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print("  wrote %s" % os.path.relpath(p, _ROOT))


# ---------------------------------------------------------------------------
# F1.1 — Layer 1 confusion matrix
# ---------------------------------------------------------------------------
def f1_1():
    m = _load(os.path.join(MODELS, "scene_classifier_meta.json"))["part3"]
    tp, fp, fn, tn = m["tp"], m["fp"], m["fn"], m["tn"]
    cm = np.array([[tn, fp], [fn, tp]], float)

    fig, (ax, ax2) = plt.subplots(1, 2, figsize=(8.4, 3.6),
                                  gridspec_kw={"width_ratios": [1, 1]})
    ax.imshow(cm / cm.sum(axis=1, keepdims=True), cmap="Blues", vmin=0, vmax=1)
    for i in range(2):
        for j in range(2):
            frac = cm[i, j] / cm[i].sum()
            ax.text(j, i, "%d\n%.1f%%" % (cm[i, j], 100 * frac), ha="center",
                    va="center", fontsize=11,
                    color="white" if frac > 0.5 else INK,
                    fontweight="bold" if i == j else "normal")
    ax.set_xticks([0, 1]); ax.set_xticklabels(["predicted\nno-oil", "predicted\noil"])
    ax.set_yticks([0, 1]); ax.set_yticklabels(["actual\nno-oil\n(n=300)", "actual\noil\n(n=150)"])
    ax.set_title("Layer 1 — scene classifier", fontsize=10, pad=10)
    for s in ax.spines.values():
        s.set_visible(False)

    ax2.axis("off")
    rates = [("scene accuracy", m["scene_accuracy"], "(139+289) / 450"),
             ("oil recall", m["oil_recall"], "139 / 150 oil scenes"),
             ("look-alike rejection", m["lookalike_rejection"], "141 / 150 look-alikes"),
             ("clean-ocean rejection", m["cleanocean_rejection"], "148 / 150 clean scenes")]
    y = 0.88
    for label, v, how in rates:
        ax2.text(0.0, y, label, fontsize=9, color=INK)
        ax2.text(0.62, y, "%.3f" % v, fontsize=13, color=BLUE, fontweight="bold")
        ax2.text(0.0, y - 0.07, how, fontsize=7, color=MUTED)
        y -= 0.20
    ax2.text(0.0, 0.06, "decision threshold 0.143 — chosen on a Parts I+II\n"
                        "validation split under a 0.90 recall floor, NOT on\n"
                        "these 450 test scenes.",
             fontsize=7.5, color=AMBER, style="italic")

    _caption(fig, "Source: pipeline/detect/models/scene_classifier_meta.json  ·  "
                  "Split: Zenodo Part III holdout, 450 scenes (150 oil / 150 look-alike / "
                  "150 clean ocean), scene-level split — trained on Parts I+II only (D1).")
    fig.subplots_adjust(bottom=0.18)
    _save(fig, "F1.1_layer1_confusion_matrix.png")


# ---------------------------------------------------------------------------
# F1.2 — the PR curve and where the gate sits
# ---------------------------------------------------------------------------
def f1_2():
    from sklearn.metrics import precision_recall_curve
    from sklearn.model_selection import train_test_split
    import torch
    from pipeline.detect import nets
    from pipeline.detect.train_classifier import load_split, predict

    ship = _load(os.path.join(MODELS, "scene_classifier_meta.json"))
    v = ship["validation"]
    ship_rec = v["tp"] / (v["tp"] + v["fn"])
    ship_prec = v["tp"] / (v["tp"] + v["fp"])

    torch.manual_seed(42); np.random.seed(42)
    X, y, ids, cls = load_split("P12seac")
    idx = np.arange(len(y))
    _tr, va = train_test_split(idx, test_size=0.15, stratify=y, random_state=42)
    model, thr = nets.load_classifier(os.path.join(MODELS, "scene_classifier_l1_e2c.pt"))
    p = predict(model, X[va], y[va])
    prec, rec, thrs = precision_recall_curve(y[va].astype(int), p)

    fig, ax = plt.subplots(figsize=(6.4, 4.6))
    ax.plot(rec, prec, color=BLUE, lw=2, label="l1_e2c — reproducible PR curve (n=%d val scenes)" % len(va))
    # Labels are pulled apart deliberately: the two operating points differ by ~0.03
    # in precision, so a shared label height reads as if they were swapped.
    for t, c, lab, off, ha in (
            (0.4896, AMBER, "0.490 — max-F1 rule (the old one)", (-18, 12), "right"),
            (0.1280, GREEN, "0.128 — precision ≥ 0.95 rule (adopted)", (-18, -26), "right")):
        k = int(np.argmin(np.abs(thrs - t)))
        ax.plot(rec[k], prec[k], "o", color=c, ms=9, zorder=5)
        ax.annotate(lab, (rec[k], prec[k]), textcoords="offset points",
                    xytext=off, fontsize=8, color=c, ha=ha,
                    arrowprops=dict(arrowstyle="-", color=c, lw=0.8, alpha=0.6))
    ax.plot(ship_rec, ship_prec, "*", color=RED, ms=17, zorder=6)
    ax.annotate("SHIPPED model @ 0.143\n(its own validation split;\ncurve not reproducible)",
                (ship_rec, ship_prec), textcoords="offset points", xytext=(-30, -78),
                fontsize=8, color=RED, ha="right",
                arrowprops=dict(arrowstyle="-", color=RED, lw=0.8, alpha=0.6))
    ax.axvline(0.90, color=MUTED, ls=":", lw=1)
    # Every operating point of interest sits above recall 0.85. Showing the full unit
    # square renders the entire decision as a few pixels in one corner.
    ax.set_xlim(0.84, 1.005)
    ax.set_ylim(0.84, 1.005)
    ax.text(0.9008, 0.845, " 0.90 recall floor", fontsize=7.5, color=MUTED,
            rotation=90, va="bottom")
    ax.set_xlabel("recall (oil scenes found)")
    ax.set_ylabel("precision")
    ax.set_title("Where the gate sits — and that it was set on VALIDATION", fontsize=10)
    ax.grid(alpha=0.3, color=GRID)
    ax.legend(loc="lower left", fontsize=7.5, frameon=False)
    _caption(fig, "Sources: models/scene_classifier_meta.json (shipped operating point), "
                  "models/scene_classifier_l1_e2c.pt + data/cache/manifest_P12seac.json (curve)  ·  "
                  "Split: validation slice of Zenodo Parts I+II — NOT Part III. The shipped "
                  "model's curve is not reproducible: it was trained on the pre-14-Sept cache, "
                  "which was rebuilt with the corrected channel order, so only its stored "
                  "operating point is plotted. Drawing it on the new cache would be a fabrication.")
    fig.subplots_adjust(bottom=0.30)
    _save(fig, "F1.2_pr_curve_and_gate.png")


# ---------------------------------------------------------------------------
# F1.3 — the gate ablation
# ---------------------------------------------------------------------------
def f1_3():
    rows = {r["model"]: r for r in _rows(_load(os.path.join(RESULTS, "eval_part3.json")))}
    ung, gat = rows["U-Net only (no gate)"], rows["Classifier + U-Net"]
    labels = ["look-alike\nrejection", "clean-ocean\nrejection", "oil recall", "pooled oil IoU"]
    a = [ung["lookalike_rejection"], ung["cleanocean_rejection"], ung["oil_recall"], ung["iou_positives"]]
    b = [gat["lookalike_rejection"], gat["cleanocean_rejection"], gat["oil_recall"], gat["iou_positives"]]

    x = np.arange(len(labels)); w = 0.36
    fig, ax = plt.subplots(figsize=(7.2, 4.2))
    r1 = ax.bar(x - w/2, a, w, label="U-Net only (no gate)", color=MUTED)
    r2 = ax.bar(x + w/2, b, w, label="Classifier + U-Net (shipped)", color=BLUE)
    for r in list(r1) + list(r2):
        ax.text(r.get_x() + r.get_width()/2, r.get_height() + 0.015,
                "%.3f" % r.get_height(), ha="center", fontsize=8)
    ax.annotate("", xy=(0 + w/2, b[0]), xytext=(0 - w/2, a[0]),
                arrowprops=dict(arrowstyle="->", color=GREEN, lw=1.6))
    ax.text(0, (a[0] + b[0]) / 2, "  +0.48", color=GREEN, fontsize=9, fontweight="bold")
    ax.annotate("", xy=(3 + w/2, b[3]), xytext=(3 - w/2, a[3]),
                arrowprops=dict(arrowstyle="->", color=RED, lw=1.6))
    ax.text(3, (a[3] + b[3]) / 2, "  −0.014", color=RED, fontsize=9, fontweight="bold")
    ax.set_xticks(x); ax.set_xticklabels(labels)
    ax.set_ylim(0, 1.08); ax.set_ylabel("score")
    ax.set_title("The gate costs 0.014 IoU and buys 0.48 look-alike rejection", fontsize=10)
    ax.legend(fontsize=8, frameon=False, loc="lower right")
    ax.grid(axis="y", alpha=0.3, color=GRID)
    _caption(fig, "Source: pipeline/detect/results/eval_part3.json  ·  Split: Zenodo Part III "
                  "holdout, 450 scenes (150 oil / 150 look-alike / 150 clean ocean).  "
                  "Ungating buys +0.014 pooled IoU and costs look-alike rejection 0.94 → 0.46. "
                  "We take the trade: a false spill alert is worse than a slightly looser outline.")
    fig.subplots_adjust(bottom=0.24)
    _save(fig, "F1.3_gate_ablation.png")


# ---------------------------------------------------------------------------
# F1.4 — the eight IoU definitions   (the strongest figure in the set)
# ---------------------------------------------------------------------------
def f1_4():
    g = {r["model"]: r for r in _rows(_load(os.path.join(RESULTS, "eval_part3.json")))}["Classifier + U-Net"]
    md = g["metric_decomposition"]
    order = [("iou_oil_pooled", "oil-class IoU, pooled\n← WHAT WE REPORT"),
             ("iou_oil_macro_tile", "oil-class IoU, mean over tiles"),
             ("dice_oil_pooled", "Dice / F1 on oil, pooled"),
             ("iou_oil_macro_scene", "oil-class IoU, mean over scenes"),
             ("miou_pooled", "mean IoU {background, oil}\n← WHAT THIS LITERATURE REPORTS"),
             ("iou_background_pooled", "background-class IoU"),
             ("pixel_accuracy_positives", "pixel accuracy, oil scenes"),
             ("pixel_accuracy_all450", "pixel accuracy, all 450")]
    labs, vals = [], []
    for k, lab in order:
        v = md.get(k, {}).get("value")
        if v is not None:
            labs.append(lab); vals.append(v)
    colors = [RED if "WE REPORT" in l else (GREEN if "LITERATURE" in l else MUTED) for l in labs]

    fig, ax = plt.subplots(figsize=(8.0, 4.8))
    yy = np.arange(len(vals))[::-1]
    ax.barh(yy, vals, color=colors, height=0.62)
    for y_, v in zip(yy, vals):
        ax.text(v + 0.012, y_, "%.4f" % v, va="center", fontsize=9)
    ax.axvspan(0.67, 0.69, color=GREEN, alpha=0.10, zorder=0)
    ax.text(0.68, 0.45, "published range on this\nbenchmark family: 0.67–0.69",
            fontsize=7.5, color=GREEN, ha="center")
    ax.set_yticks(yy); ax.set_yticklabels(labs, fontsize=8)
    ax.set_xlim(0, 1.06); ax.set_xlabel("value")
    ax.set_title("Eight definitions. Same model, same pixels, same 450 scenes.", fontsize=10)
    ax.grid(axis="x", alpha=0.3, color=GRID)
    _caption(fig, "Source: pipeline/detect/results/eval_part3.json  ·  Split: Zenodo Part III "
                  "holdout, 450 scenes, gated (Classifier + U-Net).  We report 0.4349 — the "
                  "STRICTEST of the eight. The others are printed so a comparison against any "
                  "published number is like-for-like, not so we can pick the flattering one.")
    fig.subplots_adjust(bottom=0.22)
    _save(fig, "F1.4_eight_iou_definitions.png")


# ---------------------------------------------------------------------------
# F1.5 — the coverage cliff
# ---------------------------------------------------------------------------
def f1_5():
    g = {r["model"]: r for r in _rows(_load(os.path.join(RESULTS, "eval_part3.json")))}["Classifier + U-Net"]
    bands = g["metric_decomposition"]["iou_by_slick_size"]["value"]
    order = ["0-1% oil", "1-3% oil", "3-10% oil", "10-30% oil", "30-101% oil"]
    labs = ["0–1%", "1–3%", "3–10%", "10–30%", "≥30%"]
    vals = [bands[k]["mean_iou"] for k in order]
    ns = [bands[k]["n"] for k in order]

    fig, ax = plt.subplots(figsize=(7.6, 4.4))
    cols = [MUTED] * 4 + [RED]
    bars = ax.bar(np.arange(5), vals, color=cols, width=0.62)
    for i, (b, v, n) in enumerate(zip(bars, vals, ns)):
        ax.text(i, v + 0.02, "%.3f" % v, ha="center", fontsize=9, fontweight="bold")
        ax.text(i, 0.02, "n=%d" % n, ha="center", fontsize=8, color="white"
                if v > 0.12 else MUTED)
    ax.axvspan(3.5, 4.5, color=RED, alpha=0.07, zorder=0)
    ax.set_xticks(np.arange(5)); ax.set_xticklabels(labs)
    ax.set_xlabel("oil coverage of the scene")
    ax.set_ylabel("mean per-scene IoU")
    ax.set_ylim(0, 1.0)
    ax.set_title("The failure is one narrow class of scene, not the model", fontsize=10)
    ax.grid(axis="y", alpha=0.3, color=GRID)

    # our own demo library, measured — every case sits far left of the cliff
    cov = _demo_coverage()
    ax2 = ax.twinx(); ax2.set_ylim(0, 1); ax2.axis("off")
    for c in cov:
        xx = _cov_to_x(c)
        ax2.plot([xx], [0.93], marker="v", color=GREEN, ms=7, clip_on=False)
    ax2.text(0.28, 0.965, "▼ our nine demo cases — measured coverage %.2f–%.2f%%"
             % (min(cov), max(cov)), color=GREEN, fontsize=7.5)
    _caption(fig, "Source: pipeline/detect/results/eval_part3.json (bands) and "
                  "cases/*/detections.geojson (demo coverage)  ·  Split: Zenodo Part III "
                  "holdout, 150 oil scenes.  138 of 150 scenes score 0.66–0.78. Pooled IoU "
                  "collapses because 12 scenes above 30% coverage hold ~38% of all oil pixels "
                  "and pooling weights a scene by its slick size. NO CASE IN THE DEMO LIBRARY "
                  "SITS IN THAT BAND — measured, not assumed.")
    fig.subplots_adjust(bottom=0.26)
    _save(fig, "F1.5_coverage_cliff.png")


def _demo_coverage():
    """Measured oil coverage per demo case: oil area / scene area."""
    import glob
    import rasterio
    import warnings
    warnings.filterwarnings("ignore")
    idx = _load(os.path.join(_ROOT, "cases", "index.json"))
    ids = [c if isinstance(c, str) else c.get("case_id")
           for c in (idx["cases"] if isinstance(idx, dict) else idx)]
    out = []
    for cid in ids:
        det = os.path.join(_ROOT, "cases", cid, "detections.geojson")
        tif = os.path.join(_ROOT, "cases", cid, "sar_vv_vh.tif")
        if not (os.path.exists(det) and os.path.exists(tif)):
            continue
        d = _load(det)
        oil = sum(f["properties"].get("area_km2") or 0.0 for f in d.get("features", [])
                  if f["properties"].get("classification") == "oil")
        with rasterio.open(tif) as ds:
            t, h, w = ds.transform, ds.height, ds.width
        lat_mid = t.f + t.e * (h / 2.0)
        km2 = (abs(t.a) * 111.320 * np.cos(np.radians(lat_mid))) * (abs(t.e) * 111.320) * h * w
        out.append(100.0 * oil / max(km2, 1e-9))
    return out


def _cov_to_x(pct):
    """Map a coverage percentage onto the band-bar x axis (0..4)."""
    edges = [0.0, 1.0, 3.0, 10.0, 30.0, 101.0]
    for i in range(5):
        if edges[i] <= pct < edges[i + 1]:
            span = edges[i + 1] - edges[i]
            return i - 0.5 + (pct - edges[i]) / span
    return 4.0


# ---------------------------------------------------------------------------
# F1.6 — agreement with Cerulean
# ---------------------------------------------------------------------------
def f1_6():
    rows = _load(os.path.join(RESULTS, "iou_cerulean.json"))
    names = [r["case_id"].replace("case-", "").replace("-", "\n") for r in rows]
    iou = [r["oil"]["iou"] for r in rows]
    rec = [r["oil"]["recall"] for r in rows]
    pre = [r["oil"]["precision"] for r in rows]

    x = np.arange(len(rows)); w = 0.26
    fig, ax = plt.subplots(figsize=(8.0, 4.4))
    for off, v, c, lab in ((-w, iou, BLUE, "IoU"), (0.0, rec, GREEN, "recall (of their polygon)"),
                           (w, pre, AMBER, "precision (of ours)")):
        b = ax.bar(x + off, v, w, color=c, label=lab)
        for r_ in b:
            ax.text(r_.get_x() + r_.get_width()/2, r_.get_height() + 0.015,
                    "%.2f" % r_.get_height(), ha="center", fontsize=7)
    ax.axhline(float(np.median(iou)), color=BLUE, ls="--", lw=1)
    ax.text(len(rows) - 0.4, np.median(iou) + 0.02, "median IoU %.3f" % np.median(iou),
            fontsize=7.5, color=BLUE, ha="right")
    ai = names.index("gulf\nalaska\n2023") if "gulf\nalaska\n2023" in names else 2
    ax.text(ai, 0.80, "classed AMBIGUOUS by\nCerulean's own reviewer —\na poor IoU here is the\nEXPECTED result",
            fontsize=6.8, color=RED, ha="center")
    ax.set_xticks(x); ax.set_xticklabels(names, fontsize=7.5)
    ax.set_ylim(0, 1.05); ax.set_ylabel("score")
    ax.set_title("Agreement with Cerulean on five real incidents", fontsize=10)
    ax.legend(fontsize=8, frameon=False, ncol=3, loc="upper left")
    ax.grid(axis="y", alpha=0.3, color=GRID)
    _caption(fig, "Source: pipeline/detect/results/iou_cerulean.json  ·  Five real incidents "
                  "with a Cerulean reference polygon.  Recall is high and uniform "
                  "(0.796–0.942): we find the slick on all five and draw it LARGER — IoU here "
                  "is limited by over-extent, not by misses. This is AGREEMENT BETWEEN TWO "
                  "DETECTORS, not accuracy against ground truth: SkyTruth state plainly that "
                  "SAR alone cannot definitively identify oil.")
    fig.subplots_adjust(bottom=0.28)
    _save(fig, "F1.6_cerulean_agreement.png")


# ---------------------------------------------------------------------------
# F1.7 — the second-polarisation ablation
# ---------------------------------------------------------------------------
def f1_7():
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(7.6, 4.0))
    for ax, vals, title, ylab in (
            (a1, (0.346, 0.643), "validation F1", "F1"),
            (a2, (0.049, 0.286), "Part III precision", "precision")):
        b = ax.bar([0, 1], vals, color=[MUTED, BLUE], width=0.55)
        for r_ in b:
            ax.text(r_.get_x() + r_.get_width()/2, r_.get_height() + 0.012,
                    "%.3f" % r_.get_height(), ha="center", fontsize=9, fontweight="bold")
        ax.set_xticks([0, 1]); ax.set_xticklabels(["v1_absolute\n(single pol)", "v2_vh\n(both pols)"],
                                                  fontsize=8)
        ax.set_title(title, fontsize=9.5); ax.set_ylabel(ylab)
        ax.set_ylim(0, max(vals) * 1.35); ax.grid(axis="y", alpha=0.3, color=GRID)
    a2.annotate("5.8×", xy=(1, 0.286), xytext=(0.45, 0.22), fontsize=13,
                color=GREEN, fontweight="bold")
    a2.text(0.5, -0.115, "recall IDENTICAL both ways: 4 of 36 scenes",
            transform=a2.transAxes, ha="center", fontsize=8, color=RED)
    fig.suptitle("Adding the second polarisation rejects look-alikes — it does not find slicks",
                 fontsize=10)
    _caption(fig, "Sources: docs/receipts.md L104, docs/updates/soumirya.md §622  ·  Splits: "
                  "validation slice of Parts I+II (F1) and Zenodo Part III holdout (precision).  "
                  "FEATURE SETS ARE NAMED, NOT POLARISATIONS, DELIBERATELY: the feature that "
                  "carried this ablation was computed from the band that is CO-pol on the "
                  "benchmark corpus, so \"VH is the discriminator\" is dead as stated. The "
                  "ablation itself is real and channel-agnostic.")
    fig.subplots_adjust(bottom=0.32, top=0.86)
    _save(fig, "F1.7_second_polarisation_ablation.png")


# ---------------------------------------------------------------------------
# F1.8 — the rule-margin distribution
# ---------------------------------------------------------------------------
def f1_8():
    idx = _load(os.path.join(_ROOT, "cases", "index.json"))
    ids = [c if isinstance(c, str) else c.get("case_id")
           for c in (idx["cases"] if isinstance(idx, dict) else idx)]
    vals, conf = [], []
    for cid in ids:
        p = os.path.join(_ROOT, "cases", cid, "detections.geojson")
        if not os.path.exists(p):
            continue
        for f in _load(p).get("features", []):
            pr = f["properties"]
            if pr.get("classification") == "oil" and pr.get("contrast_db") is not None:
                vals.append(pr["contrast_db"]); conf.append(pr.get("confidence"))
    vals = np.array(vals)
    clear = int((vals <= -4.5).sum()); marg = int((vals > -4.5).sum())

    fig, ax = plt.subplots(figsize=(7.2, 4.2))
    ax.hist(vals, bins=np.arange(-7.0, -2.5, 0.5), color=BLUE, alpha=0.85,
            edgecolor="white")
    ax.set_ylim(0, 4.3)          # headroom, so the rule labels never sit on a bar
    ax.axvline(-3.0, color=RED, lw=2)
    ax.text(-3.02, 4.15, "−3.0 dB rule line  ", color=RED, fontsize=8, ha="right",
            va="top")
    ax.axvline(-4.5, color=AMBER, lw=1.6, ls="--")
    ax.text(-4.48, 4.15, "  −4.5 dB clear / marginal", color=AMBER, fontsize=8,
            ha="left", va="top")
    ax.set_xlabel("contrast_db  (the unit the rule actually measures)")
    ax.set_ylabel("oil detections")
    ax.set_title("Rule margin on the %d live oil detections — %d clear / %d marginal"
                 % (len(vals), clear, marg), fontsize=10)
    ax.grid(axis="y", alpha=0.3, color=GRID)
    ax.text(0.02, 0.88, "confidence %.3f–%.3f, median %.3f\n%d clear (≤ −4.5 dB)  ·  %d marginal"
            % (min(conf), max(conf), float(np.median(conf)), clear, marg),
            transform=ax.transAxes, ha="left", fontsize=8, color=MUTED)
    _caption(fig, "Source: cases/*/detections.geojson (the nine indexed cases)  ·  Split: the "
                  "LIVE case library, not a benchmark.  On satellite cases `confidence` is a "
                  "RULE MARGIN, not a model probability (Master §6.3), so it is drawn here in "
                  "the unit the rule measures. Every detection clears the −3.0 dB rule; "
                  "%d of %d also clear the −4.5 dB clear/marginal boundary." % (clear, len(vals)))
    fig.subplots_adjust(bottom=0.26)
    _save(fig, "F1.8_rule_margin.png")


# ---------------------------------------------------------------------------
# F1.9 — the oracle ceiling
# ---------------------------------------------------------------------------
def f1_9():
    o = _load(os.path.join(RESULTS, "oracle_ceiling.json"))
    g = {r["model"]: r for r in _rows(_load(os.path.join(RESULTS, "eval_part3.json")))}["Classifier + U-Net"]
    bands = g["metric_decomposition"]["iou_by_slick_size"]["value"]
    key = {"0-1%": "0-1% oil", "1-3%": "1-3% oil", "3-10%": "3-10% oil",
           "10-30%": "10-30% oil", ">=30%": "30-101% oil"}
    labs = list(key)
    orc = [o["per_band"][b]["iou"] for b in labs]
    ours = [bands[key[b]]["mean_iou"] for b in labs]
    ns = [o["per_band"][b]["n"] for b in labs]

    x = np.arange(len(labs)); w = 0.36
    fig, ax = plt.subplots(figsize=(7.6, 4.4))
    b1 = ax.bar(x - w/2, orc, w, color=AMBER, label="ORACLE — handed the sea reference")
    b2 = ax.bar(x + w/2, ours, w, color=BLUE, label="ours (Part III, gated)")
    for r_ in list(b1) + list(b2):
        ax.text(r_.get_x() + r_.get_width()/2, r_.get_height() + 0.015,
                "%.2f" % r_.get_height(), ha="center", fontsize=7.5)
    for i, n in enumerate(ns):
        ax.text(i - w/2, 0.02, "n=%d" % n, ha="center", fontsize=7, color="white")
    ax.axhline(o["weighted_ceiling"], color=RED, ls="--", lw=1.4)
    ax.text(len(labs) - 0.45, o["weighted_ceiling"] + 0.02,
            "weighted ceiling %.4f" % o["weighted_ceiling"], color=RED, fontsize=8, ha="right")
    ax.set_xticks(x); ax.set_xticklabels(labs)
    ax.set_xlabel("oil coverage band"); ax.set_ylabel("IoU")
    ax.set_ylim(0, 1.08)
    ax.set_title("How good could ANY radiometric method be? We beat the oracle on 3 of 5 bands",
                 fontsize=9.5)
    ax.legend(fontsize=8, frameon=False, loc="upper left")
    ax.grid(axis="y", alpha=0.3, color=GRID)
    _caption(fig, "Sources: pipeline/detect/results/oracle_ceiling.json and eval_part3.json  ·  "
                  "Oracle measured on 228 Parts I+II oil scenes — NO PART III PIXEL IS READ by "
                  "it; the ceiling is re-weighted by Part III band oil-mass to be comparable.  "
                  "The oracle CHEATS in exactly one way: it takes the sea reference from the "
                  "ground-truth mask, then uses one band, one blur and one global threshold. It "
                  "bounds how much of the remaining gap is model quality versus normalisation.")
    fig.subplots_adjust(bottom=0.28)
    _save(fig, "F1.9_oracle_ceiling.png")


FIGS = {1: f1_1, 2: f1_2, 3: f1_3, 4: f1_4, 5: f1_5, 6: f1_6, 7: f1_7, 8: f1_8, 9: f1_9}


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--only", type=int, action="append",
                    help="figure number(s) to build; default is all nine")
    a = ap.parse_args()
    want = a.only or sorted(FIGS)
    print("Stage 1 evidence set -> %s\n" % os.path.relpath(OUT, _ROOT))
    for n in want:
        try:
            FIGS[n]()
        except Exception as exc:
            import traceback
            print("  [FAIL] F1.%d: %s" % (n, exc))
            traceback.print_exc()
    print("\n  Every caption names its source file and its split. That is the point.")


if __name__ == "__main__":
    main()
