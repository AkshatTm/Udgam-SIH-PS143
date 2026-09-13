"""
train.py  -  Layer 3, the classical baseline.  Owner: Soum.

    python pipeline/detect/train.py

Trains on Zenodo Parts I+II and evaluates ONLY on Part III (decision D1).
Part III is the dataset authors' own designated test set; the earlier version of
this file re-split a single CSV, which meant every number came from data the
model had effectively seen. It is now a real holdout.

THREE FEATURE SETS, TRAINED AND REPORTED SIDE BY SIDE
-----------------------------------------------------
v1_absolute  the original 8 VV features
v2_vh        + vh_contrast_db, vh_mean_depth_db   (the measured 3x jump)
v3_relative  the same information expressed in units of the SCENE'S OWN NOISE

v3 exists because of a failure we can point at. The v2 model scored the real
Huntington Beach slick — 2.6 km2, elongation 3.8, contrast -6.06 dB, unmistakable
by eye — at confidence 0.00. Not because the features were uninformative but
because -6.06 dB lies outside the range the model was fitted on: Zenodo positives
run -0.44 to -1.04 dB at the 5th-95th percentiles. A random forest splits on
thresholds it saw in training and cannot extrapolate past them, so an unusually
STRONG slick falls off the end of its world and scores like background.

Dividing by the scene's own noise MAD fixes the units. "Three times deeper than
this scene's own clutter" means the same thing at -33 dB in Zenodo Part 1, -29 dB
in Part 3 and -20 dB in a GEE export. It is the same instinct that already makes
the DETECTOR thresholds noise-relative, and the same one the tile cache applies
as per-scene MAD normalisation (docs/02_SOUM_DETECTION.md 2.1).

THRESHOLD SELECTION (2.1 / 3.4)
-------------------------------
The operating threshold is chosen on a PR curve computed on a VALIDATION split
carved out of Parts I+II — never on Part III. Choosing it by looking at test
performance is test-set contamination through the back door, the same class of
error as a row-level split.

WHAT IS REPORTED
----------------
Precision / recall / F1 on the POSITIVE class only. With ~2% positives, overall
accuracy is meaningless and is deliberately not printed.
"""
from __future__ import annotations

import json
import os
import pickle

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import (precision_score, recall_score, f1_score,
                             confusion_matrix, precision_recall_curve)

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.abspath(os.path.join(_HERE, "..", ".."))
TRAIN_CSV = os.path.join(_ROOT, "data", "labels", "features_train.csv")
TEST_CSV = os.path.join(_ROOT, "data", "labels", "features_test.csv")
MODELS = os.path.join(_HERE, "models")
PKL = os.path.join(MODELS, "classifier.pkl")
FORDER = os.path.join(MODELS, "feature_order.json")
META = os.path.join(MODELS, "model_meta.json")
PKL_VV = os.path.join(MODELS, "classifier_vv_only.pkl")
META_VV = os.path.join(MODELS, "model_meta_vv_only.json")

BASE = ["area_km2", "elongation", "edge_gradient", "solidity", "is_linear"]

FEATURE_SETS = {
    # v1_absolute is also the VV-ONLY FALLBACK (D3). Not merely a historical
    # baseline: when a scene's VH sits at or below the sensor noise floor its VH
    # features are noise, and this is the model that must be used instead.
    "v1_absolute": BASE + ["contrast_db", "mean_depth_db", "max_depth_db"],
    "v2_vh":       BASE + ["contrast_db", "mean_depth_db", "max_depth_db",
                           "vh_contrast_db", "vh_mean_depth_db"],
    "v3_relative": BASE + ["contrast_snr", "depth_snr", "max_depth_snr",
                           "vh_contrast_snr", "vh_depth_snr"],
}
# Which set gets written to classifier.pkl: whichever wins on VALIDATION F1.
# Never on Part III — selecting a model by its test score is the same
# contamination as selecting a threshold that way.
#
# An earlier version of this file broke ties in favour of v3_relative, arguing
# that Part III could not measure the thing that made v3 better because it was
# the same sensor family as Parts I+II. That argument was wrong, and it is
# removed rather than quietly kept. Measured: Part III's scene noise MAD is
# 0.554 against Parts I+II's 2.533, and its positives sit 0.73 dB below
# background against 4.72 dB. Part III IS a different domain, it DOES test
# transfer, and v3 lost that test. The tie-break was a rationalisation.

RF_KW = dict(n_estimators=300, class_weight="balanced", random_state=42, n_jobs=-1)


def derive(df):
    """Add is_linear and the scene-relative (SNR) columns.

    noise_mad is this scene's own robust noise level in dB, carried on every row
    by make_labels.py. Dividing by it turns an absolute depth into 'how many
    times deeper than this scene's clutter', which is domain-portable.
    """
    df = df.copy()
    df["is_linear"] = (df["shape_class"] == "linear").astype(int)
    mad = df["noise_mad"].replace(0, np.nan)
    med = df["noise_median"]
    # CENTRE, then scale. A depth is measured from zero, but the detector's own
    # floor sits at noise_median, so the meaningful quantity is "how many MADs
    # above this scene's noise floor". Dividing an uncentred depth by mad leaves
    # a med/mad term that re-introduces the very scene dependence we are trying
    # to remove. Measured on our own data, the centred form matches across
    # Parts I+II and Part III to 2% (1.87 vs 1.83) where the uncentred form
    # differs by 14% (3.20 vs 3.66).
    df["depth_snr"] = (df["mean_depth_db"] - med) / mad
    df["max_depth_snr"] = (df["max_depth_db"] - med) / mad
    df["vh_depth_snr"] = (df["vh_mean_depth_db"] - med) / mad
    # contrast_db is already a difference of two medians, so it only needs scaling.
    df["contrast_snr"] = df["contrast_db"] / mad
    df["vh_contrast_snr"] = df["vh_contrast_db"] / mad
    return df


def load(path, what):
    if not os.path.exists(path):
        raise SystemExit(
            f"{what} not found: {path}\n"
            f"Build it first:\n"
            f"  python pipeline/detect/make_labels.py --parts 1,2 --overlap-threshold 0.25 "
            f"--out data/labels/features_train.csv\n"
            f"  python pipeline/detect/make_labels.py --parts 3   --overlap-threshold 0.25 "
            f"--out data/labels/features_test.csv")
    df = derive(pd.read_csv(path))
    print(f"  {what:<18} {len(df):>6} rows  {int(df['label'].sum()):>5} positive  "
          f"{df['scene_id'].nunique():>5} scenes")
    return df


def best_threshold(y_true, proba):
    """Threshold maximising F1 on the PR curve. Validation data only."""
    prec, rec, thr = precision_recall_curve(y_true, proba)
    # precision_recall_curve returns len(thr) = len(prec) - 1
    f1 = np.where((prec[:-1] + rec[:-1]) > 0,
                  2 * prec[:-1] * rec[:-1] / np.maximum(prec[:-1] + rec[:-1], 1e-12),
                  0.0)
    if f1.size == 0:
        return 0.5, 0.0
    i = int(np.argmax(f1))
    return float(thr[i]), float(f1[i])


def evaluate(name, clf, feats, df_test, threshold):
    X = df_test[feats].values
    y = df_test["label"].values
    proba = clf.predict_proba(X)[:, 1]
    pred = (proba >= threshold).astype(int)

    prec = precision_score(y, pred, zero_division=0)
    rec = recall_score(y, pred, zero_division=0)
    f1 = f1_score(y, pred, zero_division=0)
    cm = confusion_matrix(y, pred, labels=[0, 1])
    tn, fp, fn, tp = cm.ravel()

    # Scene-level recall: of the held-out scenes that contain oil, in how many
    # did we flag at least one real oil region? This is closer to what the demo
    # actually needs than row-level recall.
    d = df_test.copy()
    d["pred"] = pred
    pos_scenes = d[d["label"] == 1]["scene_id"].unique()
    hits = sum(1 for s in pos_scenes
               if ((d["scene_id"] == s) & (d["label"] == 1) & (d["pred"] == 1)).any())

    return {"name": name, "threshold": round(threshold, 4),
            "precision": round(float(prec), 3), "recall": round(float(rec), 3),
            "f1": round(float(f1), 3),
            "tp": int(tp), "fp": int(fp), "fn": int(fn), "tn": int(tn),
            "scene_recall": f"{hits}/{len(pos_scenes)}",
            "scene_recall_frac": round(hits / max(len(pos_scenes), 1), 3)}


def main():
    os.makedirs(MODELS, exist_ok=True)

    print("=" * 74)
    print("  LOADING  (train = Zenodo Parts I+II, test = Part III holdout, D1)")
    print("=" * 74)
    df_tr_all = load(TRAIN_CSV, "features_train")
    df_te = load(TEST_CSV, "features_test")

    overlap = set(df_tr_all["scene_id"]) & set(df_te["scene_id"])
    if overlap:
        raise SystemExit(f"[FAIL] {len(overlap)} scene_id(s) appear in BOTH train and test — "
                         f"the part prefix is not doing its job: {sorted(overlap)[:5]}")
    print(f"  scene_id overlap train/test: 0  (clean holdout)")

    # ---- validation split, by SCENE, for threshold selection only -----------
    scene_lab = df_tr_all.groupby("scene_id")["label"].max()
    scenes, has_pos = scene_lab.index.tolist(), scene_lab.values.tolist()
    tr_scenes, va_scenes = train_test_split(scenes, test_size=0.15,
                                            stratify=has_pos, random_state=42)
    df_tr = df_tr_all[df_tr_all["scene_id"].isin(set(tr_scenes))]
    df_va = df_tr_all[df_tr_all["scene_id"].isin(set(va_scenes))]
    print(f"  fit split : {len(df_tr)} rows / {len(tr_scenes)} scenes "
          f"({int(df_tr['label'].sum())} pos)")
    print(f"  val split : {len(df_va)} rows / {len(va_scenes)} scenes "
          f"({int(df_va['label'].sum())} pos)   <- threshold chosen here, never on Part III")

    results, trained = [], {}
    for name, feats in FEATURE_SETS.items():
        missing = [c for c in feats if c not in df_tr_all.columns]
        if missing:
            print(f"\n  [SKIP] {name}: missing columns {missing}")
            continue

        sub_tr = df_tr.dropna(subset=feats + ["label"])
        sub_va = df_va.dropna(subset=feats + ["label"])
        sub_te = df_te.dropna(subset=feats + ["label"])

        print(f"\n{'='*74}")
        print(f"  {name}   {len(feats)} features")
        print(f"{'='*74}")
        print(f"  usable rows  fit={len(sub_tr)} val={len(sub_va)} test={len(sub_te)}  "
              f"(dropped {len(df_tr)-len(sub_tr)}/{len(df_va)-len(sub_va)}/"
              f"{len(df_te)-len(sub_te)} for NaN)")

        clf = RandomForestClassifier(**RF_KW)
        clf.fit(sub_tr[feats].values, sub_tr["label"].values)

        thr, va_f1 = best_threshold(sub_va["label"].values,
                                    clf.predict_proba(sub_va[feats].values)[:, 1])
        print(f"  validation PR-optimal threshold = {thr:.4f}  (val F1 {va_f1:.3f})")

        res = evaluate(name, clf, feats, sub_te, thr)
        res["val_f1"] = round(va_f1, 4)
        results.append(res)
        trained[name] = (clf, feats, thr)

        print(f"  PART III HOLDOUT   precision {res['precision']:.3f}   "
              f"recall {res['recall']:.3f}   F1 {res['f1']:.3f}")
        print(f"    TP={res['tp']}  FP={res['fp']}  FN={res['fn']}  TN={res['tn']}")
        print(f"    scene-level recall: {res['scene_recall']} oil scenes had >=1 correct hit")

        imp = sorted(zip(feats, clf.feature_importances_), key=lambda t: -t[1])
        print("    feature importance:")
        for rank, (f, v) in enumerate(imp, 1):
            print(f"      {rank:>2}. {f:<18} {v:.4f}  {'#' * int(v * 50)}")

    if not results:
        raise SystemExit("no feature set could be trained — check the CSV columns")

    # ---- the table that goes on the slide -----------------------------------
    print()
    print("=" * 74)
    print("  CLASSICAL BASELINE on the Part III holdout, scene-level split")
    print("=" * 74)
    print(f"  {'feature set':<14}{'thr':>8}{'valF1':>8}{'prec':>8}{'recall':>8}{'F1':>8}"
          f"{'TP':>5}{'FP':>6}{'FN':>5}   scene recall")
    for r in results:
        print(f"  {r['name']:<14}{r['threshold']:>8.4f}{r['val_f1']:>8.3f}"
              f"{r['precision']:>8.3f}{r['recall']:>8.3f}{r['f1']:>8.3f}"
              f"{r['tp']:>5}{r['fp']:>6}{r['fn']:>5}   {r['scene_recall']}")

    # ---- model selection, on VALIDATION --------------------------------------
    best = max(results, key=lambda r: r["val_f1"])
    ship = best["name"]
    why = f"best validation F1 ({best['val_f1']:.3f})"
    print(f"\n  Selected on VALIDATION, not on Part III: '{ship}' — {why}.")
    clf, feats, thr = trained[ship]
    chosen = next(r for r in results if r["name"] == ship)

    with open(PKL, "wb") as fh:
        pickle.dump(clf, fh)
    with open(FORDER, "w") as fh:
        json.dump(feats, fh, indent=2)
    with open(META, "w") as fh:
        json.dump({"feature_set": ship, "selected_because": why,
                   "features": feats, "threshold": thr,
                   "trained_on": "Zenodo Parts I+II (features_train.csv)",
                   "tested_on": "Zenodo Part III (features_test.csv)",
                   "threshold_selected_on": "validation split of Parts I+II, PR curve",
                   "metrics_part3": chosen,
                   "all_feature_sets": results}, fh, indent=2)

    # ---- also ship the VV-only model (D3) ------------------------------------
    # "Have a VV-only variant trained and ready, and note the degradation
    # honestly per case. Do NOT silently zero-fill the VH features — a zero is a
    # value and the model will treat it as one." The measured need: the
    # Huntington export has VH sea level at -27.8 dB, at/below Sentinel-1 IW
    # NESZ, so VH reads +0.56 dB across a slick that is -5.78 dB in VV. Feeding
    # that to a model whose top two features are VH is how a real slick scores
    # 0.010 and is called a look-alike.
    if "v1_absolute" in trained:
        vclf, vfeats, vthr = trained["v1_absolute"]
        vres = next(r for r in results if r["name"] == "v1_absolute")
        with open(PKL_VV, "wb") as fh:
            pickle.dump(vclf, fh)
        with open(META_VV, "w") as fh:
            json.dump({"feature_set": "v1_absolute", "role": "VV-only fallback (D3)",
                       "features": vfeats, "threshold": vthr,
                       "trained_on": "Zenodo Parts I+II (features_train.csv)",
                       "tested_on": "Zenodo Part III (features_test.csv)",
                       "metrics_part3": vres,
                       "use_when": "scene VH sea level at or below the sensor noise "
                                   "floor, or VH contrast near zero where VV "
                                   "contrast is strong"}, fh, indent=2)
        print(f"  VV-only fallback (D3) saved: {PKL_VV}")

    print(f"  Saved:\n    {PKL}\n    {FORDER}\n    {META}")
    print()
    print("  Quote it as: precision/recall/F1 on the POSITIVE class, Zenodo Part III")
    print("  holdout, scene-level split, threshold chosen on validation. Never an")
    print("  unqualified percentage.")


if __name__ == "__main__":
    main()
