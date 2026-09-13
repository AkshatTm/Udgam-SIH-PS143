#!/usr/bin/env python3
"""
probe_confidence.py  —  is the model UNDERCONFIDENT?   (plan E1 read-out)

    python pipeline/detect/probe_confidence.py
    python pipeline/detect/probe_confidence.py --ckpt models/unet_xpol0.pt

WHAT THIS MEASURES, AND WHY IT IS THE RIGHT READ-OUT FOR E1
----------------------------------------------------------
On an EASY positive tile — a clear slick, a sea reference inside the tile, fully in
distribution — a healthy segmenter saturates near 0.999 on the interior pixels of
the object. If it tops out around 0.85, the probability scale is compressed toward
the middle, and then it takes only a modest degradation to push a whole scene under
the 0.5 binarisation threshold. That is exactly what a 78%-coverage scene shows:
max probability 0.374 over the entire raster, nothing crossing 0.5.

So this number is a leading indicator. It moves within ONE short training run,
whereas whole-scene IoU needs a full run plus a 20-minute evaluation, which makes it
the cheapest way to tell whether the E1 channel fix did anything at all.

THE HYPOTHESIS IT TESTS
-----------------------
`train_unet.py::augment` corrupts `x[:, 1]` in 25% of training steps — replacing it
with noise or with a copy of `x[:, 0]`. Cache channel 1 is `read(2)`, which is the
CO-POL channel: verified from the cache's own manifest, where channel 0 runs 12.7 dB
darker than channel 1 in 99.9% of 2,565 scenes, and cross-pol always sits below
co-pol over ocean. The augmentation was written to simulate "cross-pol below the
noise floor" and, because of the channel-order bug, aims at the wrong channel.

One training step in four therefore shows a positive mask with the only informative
channel replaced by noise. If that is depressing confidence, fixing the target
channel should raise this number.
"""
from __future__ import annotations

import argparse
import os
import sys

import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.abspath(os.path.join(_HERE, "..", ".."))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)


def main():
    import torch
    from pipeline.detect.train_unet import TileStore, UNet
    from pipeline.detect.split import load_manifest, make_split

    ap = argparse.ArgumentParser()
    ap.add_argument("--ckpt", default=os.path.join(_HERE, "models", "unet.pt"))
    ap.add_argument("--min-oil", type=float, default=0.30,
                    help="tile oil fraction above which a tile counts as EASY")
    ap.add_argument("--limit", type=int, default=200)
    ap.add_argument("--fold", type=int, default=0)
    a = ap.parse_args()

    dev = "cuda" if torch.cuda.is_available() else "cpu"
    ck = torch.load(a.ckpt, map_location=dev, weights_only=False)
    model = UNet(in_ch=ck.get("in_ch", 2), depth=ck.get("depth", 7)).to(dev)
    model.load_state_dict(ck["state_dict"])
    model.eval()

    store = TileStore("P12")
    meta = store.meta
    scenes = load_manifest()
    _, val_ids, _ = make_split(scenes, fold=a.fold)
    val = set(val_ids)

    # Easy positives, held out. "Easy" is the point: if the model is unsure HERE,
    # the compression is systemic rather than a property of hard scenes.
    idx = [i for i in range(store.n)
           if meta[i].get("scene_id") in val
           and float(meta[i].get("oil_frac", 0.0)) >= a.min_oil]
    if not idx:
        sys.exit("no held-out tiles above that oil fraction — check --min-oil")
    idx = idx[:a.limit]

    maxes, p95s = [], []
    with torch.no_grad():
        for s in range(0, len(idx), 16):
            xb, yb = store.batch(np.array(idx[s:s + 16]))
            xb = xb.to(dev)
            prob = torch.sigmoid(model(xb)).cpu().numpy()
            y = yb.numpy() > 0.5
            for p, m in zip(prob, y):
                if m.any():
                    maxes.append(float(p[m].max()))
                    p95s.append(float(np.percentile(p[m], 95)))

    mx = np.array(maxes)
    print(f"\n  checkpoint : {os.path.basename(a.ckpt)}")
    print(f"  tiles      : {len(mx)} held-out tiles with >= {100*a.min_oil:.0f}% oil (fold {a.fold})")
    print()
    print(f"  max probability over oil pixels")
    print(f"     mean {mx.mean():.4f}   p5 {np.percentile(mx,5):.4f}   "
          f"p50 {np.median(mx):.4f}   p95 {np.percentile(mx,95):.4f}")
    print(f"  fraction of tiles whose max prob exceeds 0.99 : {(mx > 0.99).mean():.3f}")
    print(f"  fraction of tiles whose max prob is under 0.50: {(mx < 0.50).mean():.3f}")
    print()
    print("  A healthy segmenter saturates near 0.999 on easy positives. Around 0.85")
    print("  means the scale is compressed and a modest degradation drops a whole")
    print("  scene under the 0.5 threshold — which is what the 78%-coverage scene does.")


if __name__ == "__main__":
    main()
