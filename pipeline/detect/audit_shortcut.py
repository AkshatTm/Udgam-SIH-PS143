"""
audit_shortcut.py  -  Does Layer 1 detect OIL, or a dataset artefact?  Owner: Soum.

    python pipeline/detect/audit_shortcut.py

A scene classifier reporting 94.7% on a held-out split is only worth the number
if it is looking at the thing we claim. This is the counterfactual that checks:
take every Part III oil scene, replace the GT oil pixels with the surrounding
sea level, and re-score. The slick is gone; nothing else about the scene is.

  P stays HIGH  -> the model is reading a scene-level cue, not the slick, and
                   the headline accuracy is inflated by an unknown amount.
  P drops       -> the model needs the slick, which is what we claim it does.

We run this because "no accuracy number not measured on a held-out, scene-level
split" is necessary but not sufficient: a shortcut survives a perfect split.
Whatever this prints ships next to the headline (Master section 1.5).
"""
from __future__ import annotations

import json
import os
import sys

import numpy as np
import cv2
import rasterio
import torch

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.abspath(os.path.join(_HERE, "..", ".."))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from pipeline.detect import nets                                  # noqa: E402
from pipeline.detect.make_labels import _build_jobs               # noqa: E402

OUT = os.path.join(_HERE, "audit_shortcut.json")


def score(model, norm):
    small = cv2.resize(norm, (256, 256), interpolation=cv2.INTER_AREA)
    x = torch.from_numpy(small.astype(np.float32)).permute(2, 0, 1)[None].to(nets.DEVICE)
    with torch.no_grad():
        return float(torch.sigmoid(model(x)).item())


def main():
    model, thr = nets.load_classifier()
    if model is None:
        raise SystemExit("no scene classifier — run train_classifier.py first")

    jobs = [j for j in _build_jobs("3") if j[1] == "Oil"]
    rows = []
    for i, (sid, _, img, msk) in enumerate(jobs, 1):
        try:
            with rasterio.open(img) as s:
                vv = s.read(1).astype(np.float32)
                vh = s.read(2).astype(np.float32) if s.count >= 2 else None
            with rasterio.open(msk) as m:
                gt = m.read(1) > 0
            if not gt.any():
                continue

            n0, _, _ = nets.normalise_scene(vv, vh)
            p0 = score(model, n0)

            # Erase the slick: fill it with the median of the surrounding sea,
            # per band. Not zero, not NaN — those would be their own anomaly.
            sea = (~gt) & np.isfinite(vv) & (vv != 0)
            vv2 = vv.copy(); vv2[gt] = float(np.median(vv[sea]))
            vh2 = None
            if vh is not None:
                vh2 = vh.copy(); vh2[gt] = float(np.median(vh[sea]))
            n1, _, _ = nets.normalise_scene(vv2, vh2)
            p1 = score(model, n1)

            rows.append({"scene_id": sid, "oil_frac": float(gt.mean()),
                         "p_original": p0, "p_erased": p1})
        except Exception as exc:
            print(f"  [skip] {sid}: {exc}")
        if i % 25 == 0:
            print(f"  [{i}/{len(jobs)}]", flush=True)

    p0 = np.array([r["p_original"] for r in rows])
    p1 = np.array([r["p_erased"] for r in rows])
    frac = np.array([r["oil_frac"] for r in rows])

    det0 = p0 >= thr
    det1 = p1 >= thr
    # Of the scenes we correctly called oil, how many STILL say oil with no oil in them?
    survivors = int((det0 & det1).sum())
    result = {
        "threshold": thr,
        "n_scenes": len(rows),
        "median_p_original": round(float(np.median(p0)), 4),
        "median_p_erased": round(float(np.median(p1)), 4),
        "called_oil_original": int(det0.sum()),
        "called_oil_after_erasing": int(det1.sum()),
        "shortcut_rate": round(survivors / max(int(det0.sum()), 1), 4),
        "large_slick_failure": {
            "note": "scenes where oil dominates defeat per-scene MAD normalisation: "
                    "the slick becomes the median, so it normalises to 'background'",
            "oil_frac_over_30pct_n": int((frac > 0.30).sum()),
            "oil_frac_over_30pct_recall": round(float(det0[frac > 0.30].mean()), 4)
            if (frac > 0.30).any() else None,
            "oil_frac_under_30pct_recall": round(float(det0[frac <= 0.30].mean()), 4)
            if (frac <= 0.30).any() else None,
        },
        "scenes": rows,
    }

    print()
    print("=" * 70)
    print("  SHORTCUT AUDIT — Part III oil scenes, slick erased")
    print("=" * 70)
    print(f"  scenes tested                     : {result['n_scenes']}")
    print(f"  median P(oil) with the slick      : {result['median_p_original']}")
    print(f"  median P(oil) slick ERASED        : {result['median_p_erased']}")
    print(f"  called oil originally             : {result['called_oil_original']}")
    print(f"  STILL called oil with no slick    : {result['called_oil_after_erasing']}")
    print(f"  -> shortcut rate                  : {result['shortcut_rate']:.1%}")
    lf = result["large_slick_failure"]
    print()
    print(f"  recall, oil covers <=30% of scene : {lf['oil_frac_under_30pct_recall']}")
    print(f"  recall, oil covers  >30% of scene : {lf['oil_frac_over_30pct_recall']}"
          f"  (n={lf['oil_frac_over_30pct_n']})")
    print("  A slick that fills the scene becomes its own background — the same")
    print("  self-contamination that killed the v1 annulus CFAR detector.")
    with open(OUT, "w") as fh:
        json.dump(result, fh, indent=2)
    print(f"\n  wrote {OUT}")


if __name__ == "__main__":
    main()
