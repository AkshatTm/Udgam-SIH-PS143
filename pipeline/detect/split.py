#!/usr/bin/env python3
"""
split.py  —  the train/validation split, stratified by SLICK COVERAGE.  (plan E0)

    python pipeline/detect/split.py              # report the split vs the old one
    python pipeline/detect/split.py --fold 1     # the >=30% rotation

WHY THIS EXISTS — the measurement that justifies the whole file
---------------------------------------------------------------
`train_unet.py` splits with `train_test_split(uniq, test_size=0.15,
random_state=42)`: uniform over scene ids, no stratification by anything. Run it
and count what lands in validation:

    >=30% oil coverage :  1 scene
    10-30%             :  3 scenes
    (out of 190 validation oil scenes)

Those two bands hold roughly **75% of the Part III holdout's oil pixels**, because
pooled IoU weights a scene by its slick size. So every decision taken so far — the
early-stopping point, the binarisation threshold sweep, the domain-augmentation
win, model selection at 0.5 — was made against a validation metric that is
structurally incapable of seeing the regime that costs us 0.35 IoU.

That is why the shipped model can show validation IoU 0.679 while Part III pooled
is 0.435. The gap is not all generalisation. Part of it is that validation was
looking somewhere else.

Nothing downstream in the plan is interpretable until this is fixed, which is why
E0 runs before the normalisation work it is meant to evaluate.

THE >=30% ROTATION
------------------
There are 9 such scenes in all of Parts I+II. A 15% split gives 1.35 of them, and
a single scene is not a measurement. Instead the band is split into 3 folds of 3;
`--fold` selects which is held out. Report mean +/- spread across folds rather
than one number, and never tune on a difference smaller than that spread.
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

MANIFEST = os.path.join(_ROOT, "data", "cache", "manifest_P12.json")

# Bands match evaluate.py::_bands so the split and the report speak one language.
BANDS = [(0.00, 0.01, "0-1%"), (0.01, 0.03, "1-3%"), (0.03, 0.10, "3-10%"),
         (0.10, 0.30, "10-30%"), (0.30, 1.01, ">=30%")]
BIG_BAND = ">=30%"
N_FOLDS = 3
SEED = 42


def coverage_band(frac):
    for lo, hi, lbl in BANDS:
        if lo <= frac < hi:
            return lbl
    return BANDS[-1][2]


def load_manifest(path=MANIFEST):
    m = json.load(open(path, encoding="utf-8"))
    scenes = m.get("scenes", m)
    if isinstance(scenes, list):
        scenes = {r["scene_id"]: r for r in scenes}
    return scenes


def stratum(rec):
    """Stratify by class AND, for oil scenes, by coverage band.

    Look-alike and clean-ocean scenes have no coverage, so they stratify on class
    alone — but they must still be stratified, or a fold can end up with too few
    hard negatives to measure look-alike rejection against.
    """
    cls = rec.get("class", "?")
    if cls != "Oil":
        return cls
    return f"Oil/{coverage_band(float(rec.get('oil_frac', 0.0)))}"


def make_split(scenes, test_size=0.15, seed=SEED, fold=0):
    """-> (train_ids, val_ids, report dict). Scene-grouped by construction: the
    unit being split IS the scene, so no tile can straddle the boundary."""
    rng = np.random.default_rng(seed)
    by = {}
    for sid, rec in scenes.items():
        by.setdefault(stratum(rec), []).append(sid)

    train, val, report = [], [], {}
    for st in sorted(by):
        ids = sorted(by[st])
        if st == f"Oil/{BIG_BAND}":
            # Deterministic rotation, not a random draw — see the module docstring.
            idx = np.arange(len(ids))
            rng_fold = np.random.default_rng(seed)
            rng_fold.shuffle(idx)
            groups = np.array_split(idx, N_FOLDS)
            hold = set(int(i) for i in groups[fold % N_FOLDS])
            v = [ids[i] for i in range(len(ids)) if i in hold]
            t = [ids[i] for i in range(len(ids)) if i not in hold]
        else:
            perm = rng.permutation(len(ids))
            n_val = max(1, int(round(test_size * len(ids))))
            v = [ids[i] for i in perm[:n_val]]
            t = [ids[i] for i in perm[n_val:]]
        train += t
        val += v
        report[st] = {"n": len(ids), "train": len(t), "val": len(v)}
    return sorted(train), sorted(val), report


def naive_split(scenes, test_size=0.15, seed=SEED):
    """Exactly what train_unet.py does today, for the comparison in --report."""
    from sklearn.model_selection import train_test_split
    uniq = sorted(scenes)
    tr, va = train_test_split(uniq, test_size=test_size, random_state=seed)
    return sorted(tr), sorted(va)


def _report(fold=0):
    scenes = load_manifest()
    tr, va, rep = make_split(scenes, fold=fold)
    _, va_naive = naive_split(scenes)

    def counts(ids):
        out = {}
        for sid in ids:
            r = scenes[sid]
            if r.get("class") != "Oil":
                continue
            out[coverage_band(float(r.get("oil_frac", 0.0)))] = \
                out.get(coverage_band(float(r.get("oil_frac", 0.0))), 0) + 1
        return out

    new, old = counts(va), counts(va_naive)
    print(f"Parts I+II: {len(scenes)} scenes   ->   {len(tr)} train / {len(va)} val "
          f"(fold {fold} of {N_FOLDS} on the {BIG_BAND} band)\n")
    print(f"{'oil coverage band':<20}{'total':>7}{'OLD val':>9}{'NEW val':>9}")
    print("-" * 45)
    tot = {}
    for sid, r in scenes.items():
        if r.get("class") == "Oil":
            b = coverage_band(float(r.get("oil_frac", 0.0)))
            tot[b] = tot.get(b, 0) + 1
    for _, _, b in BANDS:
        print(f"{b:<20}{tot.get(b, 0):>7}{old.get(b, 0):>9}{new.get(b, 0):>9}")
    print()
    for st in sorted(rep):
        if st.startswith("Oil/"):
            continue
        print(f"  {st:<18} n={rep[st]['n']:>5}  train={rep[st]['train']:>5}  val={rep[st]['val']:>4}")
    print()
    print("The two right-hand columns are the point of this file. The old split's")
    print(f"{BIG_BAND} and 10-30% validation counts are what made every previous tuning")
    print("decision blind to ~75% of the holdout's oil mass.")
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--fold", type=int, default=0)
    a = ap.parse_args()
    sys.exit(_report(a.fold))
