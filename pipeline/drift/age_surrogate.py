#!/usr/bin/env python3
"""Stage 2 age engine v2 -- E8, the OPTIONAL learned surrogate (plan Phase 7).

    python pipeline/drift/age_surrogate.py evaluate    # leave-one-field-out, decides if it ships
    python pipeline/drift/age_surrogate.py fit         # all twins -> models/age_surrogate.pkl

WHY IT IS OPTIONAL, AND WHY IT IS SEPARATE
    pipeline/drift/CLAUDE.md says "No ML here." That rule protects the drift integrator and the
    origin cloud, and nothing in this file touches either. Akshat asked for this tier on
    16 Sept 2026 (plan decision 4) as a final, switch-off-able estimator; the physics engine
    never depends on it. Its weight is 0 unless `evaluate` shows it improves the held-out log
    score, and age_calibration.json records that decision.

WHAT IT IS
    Quantile gradient boosting (scikit-learn, already pinned -- no new dependency) from what
    Stage 2 can observe at t0 to log(age): the slick's length, width, aspect and area, its
    discharge class, and the local current, wind and strain rate. Trained ONLY on synthetic
    twins, never on a real case.

    Its output is p(age | x) under the twins' age distribution, which is the engine's own
    log-uniform prior. The fusion multiplies likelihoods onto that prior, so the prior is
    divided back out here -- otherwise it would be counted twice.
"""
import argparse
import json
import math
import pickle
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(HERE))

import age                                     # noqa: E402
import age_posterior as AP                     # noqa: E402

MODEL_PATH = HERE / "models" / "age_surrogate.pkl"
QUANTILES = (0.1, 0.5, 0.9)
Z90 = 1.2815515655446004
FEATURES = ["log_L", "log_W", "log_aspect", "log_area", "chronic", "acute",
            "current_ms", "wind_ms", "log_strain"]


def field_state(field, lon, lat, t0):
    import fields as F
    u, v = field.get_uv(np.array([lon]), np.array([lat]), t0)
    wind = age.mean_wind_ms(field, lon, lat, t0)
    s = age.deformation_rate_s(field, lon, lat, t0)
    return float(F.speed(u, v)[0]), float(wind), float(s)


def features_for(feature, field, t0):
    """Feature vector for one detection, or None if its shape is unmeasurable."""
    L, d = age.slick_major_axis_km(feature)
    W = d.get("bbox_width_km")
    if not L or not W:
        return None
    p = feature["properties"]
    lon, lat = float(p["centroid"][0]), float(p["centroid"][1])
    cur, wind, strain = field_state(field, lon, lat, t0)
    dc = p.get("discharge_class")
    return [math.log(L), math.log(W), math.log(L / W),
            math.log(max(float(p.get("area_km2") or L * W), 1e-4)),
            float(dc == "chronic"), float(dc == "acute"),
            cur, wind, math.log(max(strain, 1e-9))]


def twin_table():
    """(X, y, fields, ids) for every visible twin that has been prepared."""
    from datetime import datetime
    from fields import load_case_field
    import age_twins as T
    X, y, fl, ids = [], [], [], []
    for f in T.FIELDS:
        d = T.TWINS / f
        if not (d / "features_all.json").exists():
            continue
        truths = json.loads((d / "truths.json").read_text())
        t0 = datetime.fromisoformat(truths["t0"])
        field = load_case_field(f, repo_root=REPO)
        feats = json.loads((d / "features_all.json").read_text())
        for t in truths["truths"]:
            ft = feats.get(t["id"])
            if ft is None:
                continue
            x = features_for(ft, field, t0)
            if x is None:
                continue
            X.append(x)
            y.append(math.log(t["age_h"]))
            fl.append(f)
            ids.append(t["id"])
    return np.asarray(X), np.asarray(y), np.asarray(fl), ids


def fit_models(X, y):
    from sklearn.ensemble import HistGradientBoostingRegressor
    return {q: HistGradientBoostingRegressor(loss="quantile", quantile=q, max_iter=200,
                                             learning_rate=0.05, max_leaf_nodes=8,
                                             min_samples_leaf=8, random_state=0).fit(X, y)
            for q in QUANTILES}


def loglik_from_quantiles(q10, q50, q90, grid=None):
    """Likelihood on the age grid: a log-normal fitted to the quantiles, prior divided out."""
    grid = AP.AGE_GRID_H if grid is None else grid
    lo, hi = sorted((q10, q90))
    sd = max((hi - lo) / (2 * Z90), 0.1)
    lg = np.log(grid)
    log_post = -0.5 * ((lg - q50) / sd) ** 2
    return AP.floor_loglik(log_post - AP.log_uniform_prior(grid))


def surrogate_loglik(feature, field, t0, path=MODEL_PATH):
    """Production entry point: None when no trained model exists."""
    if not Path(path).exists():
        return None
    x = features_for(feature, field, t0)
    if x is None:
        return None
    models = pickle.loads(Path(path).read_bytes())
    q = [float(models[k].predict(np.asarray([x]))[0]) for k in QUANTILES]
    return loglik_from_quantiles(*q)


def cmd_evaluate(a):
    X, y, fl, ids = twin_table()
    fields = sorted(set(fl))
    print(f"{len(y)} twins across {len(fields)} fields, {X.shape[1]} features")
    if len(fields) < 2:
        raise SystemExit("need at least two fields")
    cov, logs, errs = [], [], []
    per, heldout = {}, {}
    ids = np.asarray(ids)
    for f in fields:
        tr, te = fl != f, fl == f
        m = fit_models(X[tr], y[tr])
        q = {k: m[k].predict(X[te]) for k in QUANTILES}
        c_f = []
        for i, tid in enumerate(ids[te]):
            heldout[str(tid)] = [float(q[0.1][i]), float(q[0.5][i]), float(q[0.9][i])]
        for i in range(int(te.sum())):
            ll = loglik_from_quantiles(q[0.1][i], q[0.5][i], q[0.9][i])
            post, _ = AP.fuse([("s", ll, 1.0)])
            t = math.exp(y[te][i])
            lo, hi, _ = AP.hpd(post)
            c_f.append(lo <= t <= hi)
            k = int(np.argmin(np.abs(AP.AGE_GRID_H - t)))
            logs.append(math.log(max(post[k], 1e-12)))
            errs.append(abs(q[0.5][i] - y[te][i]) / math.log(2))
        cov += c_f
        per[f] = round(float(np.mean(c_f)), 3)
    res = {"n": int(len(y)), "coverage80_heldout": round(float(np.mean(cov)), 3),
           "mean_log_score": round(float(np.mean(logs)), 3),
           "median_abs_log2_error": round(float(np.median(errs)), 3),
           "per_field_coverage": per,
           "prior_only_log_score": round(float(np.mean(
               [AP.log_uniform_prior()[int(np.argmin(np.abs(AP.AGE_GRID_H - math.exp(v))))]
                for v in y])), 3)}
    out = HERE / "out" / "twins" / "surrogate_eval.json"
    out.write_text(json.dumps(res, indent=1))
    (HERE / "out" / "twins" / "surrogate_heldout.json").write_text(json.dumps(heldout))
    print(json.dumps(res, indent=1))
    print(f"wrote {out}")


def cmd_fit(a):
    X, y, _, _ = twin_table()
    models = fit_models(X, y)
    MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    MODEL_PATH.write_bytes(pickle.dumps(models))
    print(f"wrote {MODEL_PATH}  ({len(y)} twins)")


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["evaluate", "fit"])
    a = ap.parse_args(argv)
    {"evaluate": cmd_evaluate, "fit": cmd_fit}[a.cmd](a)
    return 0


if __name__ == "__main__":
    sys.exit(main())
