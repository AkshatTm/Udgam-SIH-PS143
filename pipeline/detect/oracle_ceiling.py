#!/usr/bin/env python3
"""
oracle_ceiling.py  —  how good could ANY radiometric method be?   (plan E8a)

    python pipeline/detect/oracle_ceiling.py --per-band 60

WHY THIS DECIDES THE PROGRAMME
------------------------------
The target is pooled oil-class IoU above 0.85. Before spending weeks on it, we need
to know whether 0.85 is even available — and the cheapest way to bound that is to
give a trivially simple method the answer and see how well it does.

This oracle CHEATS, deliberately and in exactly one way: it takes the sea reference
from the ground-truth mask. Everything else is as dumb as possible — one band, one
blur, one global threshold, no texture, no shape, no context, nothing learned. If a
GT-informed threshold cannot reach 0.85, then a learned model must BEAT an oracle
to get there, which is a real requirement rather than a rounding error.

The number this replaces was measured by a planning agent and taken on trust while
the plan was written. It is the only load-bearing figure in that plan I had not
checked myself, so it gets checked here.

WHY PARTS I+II AND NOT PART III
-------------------------------
Part III is the holdout and gets run once, at the end. A ceiling is a property of
the imagery and the annotation, not of a particular split, so it is measured on the
training halves and then re-weighted by Part III's band oil-mass to give a figure
comparable to the headline. Nothing here reads a Part III pixel.

THE BOUNDARY DECOMPOSITION
--------------------------
IoU on a thin filament is dominated by where the annotator drew the edge. Recomputing
it with a +/-m pixel band around the GT boundary excluded from BOTH numerator and
denominator says how much of the residual is edge placement rather than detection. If
most of the error is inside a few pixels of the boundary, the ceiling is the
annotation's, not the model's, and no amount of training moves it.
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

BANDS = [(0.00, 0.01, "0-1%"), (0.01, 0.03, "1-3%"), (0.03, 0.10, "3-10%"),
         (0.10, 0.30, "10-30%"), (0.30, 1.01, ">=30%")]

# Part III oil-MASS share per band — pooled IoU weights a scene by its slick size,
# so this is what makes a Parts I+II measurement comparable to the headline.
# Measured directly from the Part III masks (counts only, no pixels read into the
# ceiling itself).
P3_MASS = None          # filled by _p3_mass()

KS = np.arange(0.5, 6.01, 0.25)     # threshold sweep, in sea sigmas below the sea
BLUR_SIGMA = 3.0
EDGE_BANDS = [0, 2, 5, 10, 15]


def band_of(f):
    for lo, hi, lbl in BANDS:
        if lo <= f < hi:
            return lbl
    return BANDS[-1][2]


def _p3_mass():
    """Oil-pixel share per coverage band on Part III. Reads only mask geometry."""
    import glob
    import rasterio
    mass = {b: 0.0 for _, _, b in BANDS}
    for p in sorted(glob.glob(os.path.join(_ROOT, "data", "test", "Mask", "Oil",
                                           "*_segmentation.tif"))):
        with rasterio.open(p) as ds:
            g = ds.read(1) > 0
        mass[band_of(g.mean())] += float(g.sum())
    tot = sum(mass.values()) or 1.0
    return {k: v / tot for k, v in mass.items()}


def oracle_scene(db, gt):
    """-> (inter[k], union[k]) arrays over the threshold sweep, plus edge-band data.

    The ONLY cheat: sea_med/sea_mad come from ~gt.
    """
    from scipy import ndimage as ndi
    finite = np.isfinite(db) & (db != 0.0)
    sea = db[(~gt) & finite]
    if sea.size < 1000:
        return None
    med = float(np.median(sea))
    mad = 1.4826 * float(np.median(np.abs(sea - med))) + 1e-6
    z = np.where(finite, (db - med) / mad, 0.0).astype(np.float32)
    z = ndi.gaussian_filter(z, BLUR_SIGMA)

    inter = np.empty(len(KS)); union = np.empty(len(KS))
    for i, k in enumerate(KS):
        pred = z < -k
        inter[i] = float((pred & gt).sum())
        union[i] = float((pred | gt).sum())
    return inter, union


def edge_decomposition(db, gt, k):
    """At the chosen k, how much of the error sits within m px of the GT boundary?"""
    from scipy import ndimage as ndi
    finite = np.isfinite(db) & (db != 0.0)
    sea = db[(~gt) & finite]
    med = float(np.median(sea))
    mad = 1.4826 * float(np.median(np.abs(sea - med))) + 1e-6
    z = ndi.gaussian_filter(np.where(finite, (db - med) / mad, 0.0).astype(np.float32),
                            BLUR_SIGMA)
    pred = z < -k
    err = pred ^ gt
    if not err.any():
        return {m: (0.0, 0.0) for m in EDGE_BANDS}
    # distance to the nearest GT boundary pixel
    inside = ndi.distance_transform_edt(gt)
    outside = ndi.distance_transform_edt(~gt)
    dist = np.where(gt, inside, outside)
    out = {}
    for m in EDGE_BANDS:
        near = err & (dist <= m)
        out[m] = (float(near.sum()), float(err.sum()))
    return out


def main():
    import rasterio
    from pipeline.detect.make_labels import _build_jobs

    ap = argparse.ArgumentParser()
    ap.add_argument("--per-band", type=int, default=60,
                    help="scenes sampled per coverage band (small bands taken whole)")
    ap.add_argument("--json", default=os.path.join(_HERE, "oracle_ceiling.json"))
    a = ap.parse_args()

    man = json.load(open(os.path.join(_ROOT, "data", "cache", "manifest_P12.json"),
                         encoding="utf-8"))["scenes"]
    by = {}
    for sid, rec in man.items():
        if rec.get("class") != "Oil":
            continue
        by.setdefault(band_of(float(rec.get("oil_frac", 0.0))), []).append(sid)
    rng = np.random.default_rng(42)
    pick = set()
    for _, _, b in BANDS:
        ids = sorted(by.get(b, []))
        if len(ids) <= a.per_band:
            pick |= set(ids)
        else:
            pick |= set(rng.choice(ids, a.per_band, replace=False).tolist())

    jobs = [j for j in _build_jobs("1,2") if j[0] in pick and j[1] == "Oil"]
    print(f"oracle over {len(jobs)} Parts I+II oil scenes "
          f"(sea reference taken FROM the GT mask; one band, one blur, one threshold)\n",
          flush=True)

    acc = {b: {"inter": np.zeros(len(KS)), "union": np.zeros(len(KS)), "n": 0}
           for _, _, b in BANDS}
    keep = []
    for i, (sid, _cls, img, msk) in enumerate(jobs, 1):
        try:
            with rasterio.open(img) as ds:
                db = ds.read(2).astype(np.float32)       # co-pol: the signal channel
            with rasterio.open(msk) as ds:
                gt = ds.read(1) > 0
        except Exception:
            continue
        if not gt.any():
            continue
        r = oracle_scene(db, gt)
        if r is None:
            continue
        inter, union = r
        b = band_of(float(gt.mean()))
        acc[b]["inter"] += inter
        acc[b]["union"] += union
        acc[b]["n"] += 1
        keep.append((sid, b, img, msk))
        if i % 25 == 0:
            print(f"  [{i}/{len(jobs)}]", flush=True)

    # global best k, chosen on the pooled curve across all bands
    tot_i = sum(acc[b]["inter"] for _, _, b in BANDS)
    tot_u = sum(acc[b]["union"] for _, _, b in BANDS)
    gi = int(np.argmax(np.divide(tot_i, tot_u, out=np.zeros_like(tot_i), where=tot_u > 0)))
    best_k = float(KS[gi])

    mass = _p3_mass()
    print(f"\nglobal best threshold: sea - {best_k:.2f} sigma\n")
    print(f"{'band':<10}{'n':>5}{'oracle IoU':>12}{'P3 oil mass':>13}{'weighted':>10}")
    print("-" * 52)
    weighted = 0.0
    per_band = {}
    for _, _, b in BANDS:
        if not acc[b]["n"]:
            continue
        iou = float(acc[b]["inter"][gi] / max(acc[b]["union"][gi], 1e-9))
        per_band[b] = {"n": acc[b]["n"], "iou": round(iou, 4), "p3_mass": round(mass[b], 4)}
        weighted += iou * mass[b]
        print(f"{b:<10}{acc[b]['n']:>5}{iou:>12.4f}{mass[b]:>13.4f}{iou*mass[b]:>10.4f}")
    print("-" * 52)
    print(f"{'CEILING':<10}{'':>5}{'':>12}{'':>13}{weighted:>10.4f}")
    print()
    print("This is what a GT-INFORMED threshold achieves. A learned model must BEAT")
    print("this to go higher, using texture, shape and context the oracle ignores.")

    # boundary decomposition at the chosen k, on a subsample
    print("\nboundary decomposition — share of oracle error within m px of the GT edge")
    print(f"{'band':<10}" + "".join(f"{m:>8}px" for m in EDGE_BANDS))
    print("-" * (10 + 10 * len(EDGE_BANDS)))
    edge = {}
    for _, _, b in BANDS:
        sel = [x for x in keep if x[1] == b][:12]
        if not sel:
            continue
        near = {m: 0.0 for m in EDGE_BANDS}
        tot = 0.0
        for sid, _b, img, msk in sel:
            with rasterio.open(img) as ds:
                db = ds.read(2).astype(np.float32)
            with rasterio.open(msk) as ds:
                gt = ds.read(1) > 0
            d = edge_decomposition(db, gt, best_k)
            for m in EDGE_BANDS:
                near[m] += d[m][0]
            tot += d[EDGE_BANDS[0]][1]
        edge[b] = {m: round(near[m] / max(tot, 1e-9), 4) for m in EDGE_BANDS}
        print(f"{b:<10}" + "".join(f"{near[m]/max(tot,1e-9):>10.2f}" for m in EDGE_BANDS))

    json.dump({"best_k": best_k, "per_band": per_band, "weighted_ceiling": round(weighted, 4),
               "edge": edge, "note": "Parts I+II only; weighted by Part III band oil mass"},
              open(a.json, "w", encoding="utf-8"), indent=2)
    print(f"\nwrote {a.json}")


if __name__ == "__main__":
    main()
