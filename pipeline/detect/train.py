"""
train.py  -  Phase 2, Step 3.  Owner: Soum.

Trains a RandomForest classifier on data/labels/features_t25.csv and saves
the model to pipeline/detect/models/classifier.pkl.

Critical design decisions:
  - SCENE-LEVEL SPLIT (TRAPS #10): rows from the same 2048x2048 scene are
    correlated. Splitting by row lets them leak between train and test,
    producing a flattering but meaningless accuracy number. We split by
    scene_id and then assign rows.
  - class_weight='balanced': with ~50:1 neg:pos ratio, a model predicting
    all-zero scores 98.5% accuracy and learns nothing. Balanced weights force
    it to actually find oil.
  - We report precision/recall/F1 on the POSITIVE class, not overall accuracy.
    Overall accuracy is misleading here and is intentionally omitted.
"""
from __future__ import annotations

import json
import os
import sys
import pickle

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import (precision_score, recall_score, f1_score,
                             confusion_matrix)

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
_HERE  = os.path.dirname(os.path.abspath(__file__))
_ROOT  = os.path.abspath(os.path.join(_HERE, "..", ".."))
CSV    = os.path.join(_ROOT, "data", "labels", "features_t25.csv")
MODELS = os.path.join(_HERE, "models")
PKL    = os.path.join(MODELS, "classifier.pkl")
FORDER = os.path.join(MODELS, "feature_order.json")

# Features used for training — order is saved to FORDER so run.py can
# reproduce the exact column order at inference time.  shape_class is encoded
# as is_linear (1/0) here; the raw string never enters sklearn.
FEATURES = [
    "area_km2",
    "contrast_db",
    "mean_depth_db",
    "max_depth_db",
    "elongation",
    "edge_gradient",
    "solidity",
    "is_linear",
]


def _try_split(scene_ids, has_pos_map, test_size, random_states):
    """Try multiple random_state seeds until test split has >= 3 pos scenes."""
    has_pos_arr = [has_pos_map[s] for s in scene_ids]
    for rs in random_states:
        tr, te = train_test_split(
            scene_ids, test_size=test_size, stratify=has_pos_arr, random_state=rs
        )
        te_pos = sum(has_pos_map[s] for s in te)
        if te_pos >= 3:
            return tr, te, rs
    # Last attempt — return whatever we got
    return tr, te, random_states[-1]


def main():
    os.makedirs(MODELS, exist_ok=True)

    # -----------------------------------------------------------------------
    # 1. Load
    # -----------------------------------------------------------------------
    print(f"Loading {CSV} ...")
    df = pd.read_csv(CSV)
    print(f"  Loaded {len(df)} rows, {df['label'].sum()} positive")

    # Encode shape_class -> is_linear
    df["is_linear"] = (df["shape_class"] == "linear").astype(int)

    # Drop rows with NaN in any feature or label column
    check_cols = FEATURES + ["label", "scene_id"]
    before = len(df)
    df = df.dropna(subset=check_cols)
    dropped = before - len(df)
    if dropped:
        print(f"  [WARN] dropped {dropped} rows with NaN/missing values")
    else:
        print(f"  No NaN rows — all {len(df)} rows kept")

    # -----------------------------------------------------------------------
    # 2. Scene-level stratified split  (TRAPS #10)
    # -----------------------------------------------------------------------
    print()
    print("=" * 62)
    print("  SCENE-LEVEL STRATIFIED SPLIT")
    print("=" * 62)

    # One row per unique scene_id: does it contain any positives?
    scene_label = df.groupby("scene_id")["label"].max()  # 1 if any positive
    unique_scenes = scene_label.index.tolist()
    has_pos_arr   = scene_label.values.tolist()

    pos_scenes = sum(has_pos_arr)
    print(f"  Unique scenes       : {len(unique_scenes)}")
    print(f"  Scenes with label=1 : {pos_scenes}")
    print(f"  Scenes with label=0 only: {len(unique_scenes) - pos_scenes}")

    has_pos_map = dict(zip(unique_scenes, has_pos_arr))

    train_scenes, test_scenes, used_rs = _try_split(
        unique_scenes, has_pos_map, test_size=0.2,
        random_states=[42, 7, 123]
    )
    print(f"  random_state used   : {used_rs}")
    print(f"  Train scenes: {len(train_scenes)}"
          f"  ({sum(has_pos_map[s] for s in train_scenes)} with positives)")
    print(f"  Test  scenes: {len(test_scenes)}"
          f"  ({sum(has_pos_map[s] for s in test_scenes)} with positives)")

    train_set = set(train_scenes)
    test_set  = set(test_scenes)

    df_train = df[df["scene_id"].isin(train_set)].copy()
    df_test  = df[df["scene_id"].isin(test_set)].copy()

    print()
    print(f"  Train rows: {len(df_train)}"
          f"  (pos={df_train['label'].sum()}, neg={len(df_train)-df_train['label'].sum()})")
    print(f"  Test  rows: {len(df_test)}"
          f"  (pos={df_test['label'].sum()}, neg={len(df_test)-df_test['label'].sum()})")

    # -----------------------------------------------------------------------
    # 3. Build feature matrices
    # -----------------------------------------------------------------------
    X_train = df_train[FEATURES].values
    y_train = df_train["label"].values
    X_test  = df_test[FEATURES].values
    y_test  = df_test["label"].values

    # -----------------------------------------------------------------------
    # 4. Train
    # -----------------------------------------------------------------------
    print()
    print("=" * 62)
    print("  TRAINING  RandomForest(n=300, class_weight='balanced')")
    print("=" * 62)

    clf = RandomForestClassifier(
        n_estimators=300,
        class_weight="balanced",
        random_state=42,
        n_jobs=-1,
    )
    clf.fit(X_train, y_train)
    print("  Done.")

    # -----------------------------------------------------------------------
    # 5. Evaluate
    # -----------------------------------------------------------------------
    print()
    print("=" * 62)
    print("  EVALUATION ON HELD-OUT TEST SET")
    print("=" * 62)

    y_pred = clf.predict(X_test)

    prec  = precision_score(y_test, y_pred, zero_division=0)
    rec   = recall_score(y_test, y_pred, zero_division=0)
    f1    = f1_score(y_test, y_pred, zero_division=0)
    cm    = confusion_matrix(y_test, y_pred)

    # cm layout for binary: [[TN, FP], [FN, TP]]
    tn, fp, fn, tp = cm.ravel() if cm.shape == (2, 2) else (cm[0,0], 0, 0, 0)

    print(f"  Positive class (oil) metrics:")
    print(f"    Precision : {prec:.3f}  ({tp} of {tp+fp} predicted-positive were real oil)")
    print(f"    Recall    : {rec:.3f}  ({tp} of {tp+fn} real-oil regions found)")
    print(f"    F1        : {f1:.3f}")
    print()
    print(f"  Confusion matrix (rows=actual, cols=predicted):")
    print(f"              pred=0   pred=1")
    print(f"    actual=0:  {tn:>5}    {fp:>5}    (TN={tn}, FP={fp})")
    print(f"    actual=1:  {fn:>5}    {tp:>5}    (FN={fn}, TP={tp})")

    # Scene-level hit rate: how many positive-containing test scenes had >= 1 TP?
    df_test = df_test.copy()
    df_test["y_pred"] = y_pred
    pos_test_scenes = [s for s in test_scenes if has_pos_map[s] == 1]
    scene_hits = 0
    scene_details = []
    for sid in pos_test_scenes:
        rows = df_test[df_test["scene_id"] == sid]
        scene_tp = int(((rows["label"] == 1) & (rows["y_pred"] == 1)).sum())
        scene_fn = int(((rows["label"] == 1) & (rows["y_pred"] == 0)).sum())
        scene_fp = int(((rows["label"] == 0) & (rows["y_pred"] == 1)).sum())
        hit = scene_tp > 0
        if hit:
            scene_hits += 1
        scene_details.append((sid, scene_tp, scene_fn, scene_fp, hit))

    print()
    print(f"  Scene-level hit rate (positive test scenes):")
    print(f"  {scene_hits} / {len(pos_test_scenes)} positive-containing test scenes"
          f" had >= 1 correct oil detection")
    print()
    print(f"  {'scene_id':<25}  TP  FN  FP  hit?")
    print(f"  {'-'*50}")
    for sid, stp, sfn, sfp, hit in scene_details:
        print(f"  {sid:<25}  {stp:>2}  {sfn:>2}  {sfp:>2}  {'YES' if hit else 'no'}")

    # -----------------------------------------------------------------------
    # 6. Feature importances
    # -----------------------------------------------------------------------
    print()
    print("=" * 62)
    print("  FEATURE IMPORTANCES (Gini, sorted)")
    print("=" * 62)
    importances = clf.feature_importances_
    order = np.argsort(importances)[::-1]
    for rank, idx in enumerate(order, 1):
        bar = "#" * int(importances[idx] * 60)
        print(f"  {rank:>2}. {FEATURES[idx]:<15}  {importances[idx]:.4f}  {bar}")

    # -----------------------------------------------------------------------
    # 7. Save model + feature order
    # -----------------------------------------------------------------------
    with open(PKL, "wb") as f:
        pickle.dump(clf, f)
    with open(FORDER, "w") as f:
        json.dump(FEATURES, f, indent=2)

    print()
    print("=" * 62)
    print(f"  Saved: {PKL}")
    print(f"  Saved: {FORDER}")
    print("=" * 62)


if __name__ == "__main__":
    main()
