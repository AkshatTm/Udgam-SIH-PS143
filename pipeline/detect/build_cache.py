"""
build_cache.py  -  Phase 2, the tile cache.  Owner: Soum.

    python pipeline/detect/build_cache.py --parts 1,2
    python pipeline/detect/build_cache.py --parts 3

ONE pass over the scenes producing BOTH network inputs, because reading 3,020
scenes at 2048x2048x2 float32 is ~96 GB of disk traffic and doing it twice is an
hour we do not have:

  data/cache/scenes_<P>.npy    (N, 256, 256, 2) float16   -> Layer 1 classifier
  data/cache/tiles/*.npy       (n, 256, 256, 2) float16   -> Layer 2 U-Net
  data/cache/manifest_<P>.json  per-scene med/mad, labels, ids

PER-SCENE MAD NORMALISATION — the most important detail in this file
--------------------------------------------------------------------
    valid = finite, non-zero, inside the scene
    med   = median(valid)
    mad   = median(|valid - med|)
    norm  = clip((x - med) / (1.4826*mad + eps), -6, +6) / 6      ->  [-1, +1]

Never feed raw dB to a network. Measured on our own data, VV medians are -33.3 dB
in Part 1, -29.3 dB in Part 3 and -20.2 dB in the Huntington GEE export, and the
Huntington noise MAD is ~2.5x Zenodo's. A model fitted on absolute values fails
on the other domain WITHOUT ERRORING — it returns confident nonsense. We have
already watched this happen once: the absolute-dB RandomForest scored a textbook
-6 dB slick at 0.00.

MAD rather than mean/std because MAD is robust to the slick itself and to bright
ships, so a large slick cannot shift its own normalisation. The 1.4826 makes MAD
comparable to a standard deviation for Gaussian data.

med and mad are stored per scene per band. They are needed to invert the
normalisation when Layer 3 computes real contrast_db from the original dB.

HARD NEGATIVES
--------------
Part 2's look-alike and no-oil masks are entirely zero — checked, not assumed —
so they localise nothing and cannot tell us which tile holds the confusable
feature. We therefore select hard negatives by DARKNESS: the darkest tiles of a
look-alike scene are the ones that look like oil, which is the actual axis of
confusion. Taking all 64 tiles of every look-alike scene instead would bury the
positives under 44,000 mostly-empty negatives.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time

import numpy as np
import cv2
import rasterio

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.abspath(os.path.join(_HERE, "..", ".."))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from pipeline.detect.make_labels import PARTS, CLASSES, _build_jobs   # noqa: E402

CACHE = os.path.join(_ROOT, "data", "cache")
TILES = os.path.join(CACHE, "tiles")

TILE = 256
SCENE_SIZE = 256           # downsampled whole scene for the classifier
CLIP_SIGMA = 6.0
EPS = 1e-6

MIN_OIL_FRAC = 0.01        # a tile counts as positive at >= 1% oil pixels
MAX_INVALID_FRAC = 0.50    # drop tiles that are mostly land/nodata
DARK_NEG_PER_LOOKALIKE = 8  # hard negatives per look-alike scene
DARK_NEG_PER_NOOIL = 2      # clean-ocean variety
SHARD = 2000

# Cap per scene. Measured: a Zenodo oil scene yields ~24 of its 64 tiles at >=1%
# oil, so uncapped this is ~65,000 tiles and ~21 GB. Capping at 12+12 keeps the
# cache near 9 GB and, more usefully, stops a handful of enormous slicks from
# dominating the training set with near-duplicate tiles of the same feature.
# The richest tiles are kept: positives by oil fraction, negatives at random.
MAX_POS_PER_SCENE = 12
MAX_NEG_PER_SCENE = 12


NORMALISE_MODE = "sea"      # "median" reproduces the original cache exactly


def _norm(band, mode, transform=None):
    """THE normalisation, from pipeline/detect/normalise.py. This file used to hold a
    second copy of the same rule, which is the shape of bug that made the k_sigma fix
    inert for a day; there is now one implementation and both producers call it."""
    from pipeline.detect.normalise import normalise_band as _nb, sea_reference, valid_mask
    if mode == "sea":
        v = valid_mask(band, exclude_land=True, transform=transform)
        if not v.any():
            return np.zeros_like(band, np.float32), v, 0.0, 1.0
        ref, scale, _ = sea_reference(band, v, transform=transform)
        out = np.clip((band - ref) / scale, -CLIP_SIGMA, CLIP_SIGMA) / CLIP_SIGMA
        return np.where(v, out, 0.0).astype(np.float32), v, ref, scale
    out, v, ref, scale = _nb(band, "median")
    return out, v, ref, scale


def _median_reference(band):
    from pipeline.detect.normalise import median_reference
    return median_reference(band)


def normalise(band):
    """dB -> [-1, +1] using this scene's own median and MAD. Returns
    (norm float32, valid bool, med, mad). Invalid pixels are set to 0.0, which
    is the normalised sea level — not a dark value, so the network is not told
    there is a slick where there is land."""
    valid = np.isfinite(band) & (band != 0.0)
    if not valid.any():
        return np.zeros_like(band, np.float32), valid, 0.0, 1.0
    v = band[valid]
    med = float(np.median(v))
    mad = float(np.median(np.abs(v - med)))
    scale = 1.4826 * mad + EPS
    norm = np.clip((band - med) / scale, -CLIP_SIGMA, CLIP_SIGMA) / CLIP_SIGMA
    norm = np.where(valid, norm, 0.0).astype(np.float32)
    return norm, valid, med, mad


def scene_arrays(img_path, mode=None):
    """-> (norm (H,W,2) float32, valid (H,W) bool, stats dict).

    CHANNEL ORDER IS NOW CORRECT, and this is a breaking change to the cache.

    Zenodo Parts I-III tiles are **band 1 = VH, band 2 = VV** — measured over 297 Part
    III scenes, band 1 runs 8.15 dB darker and is darker in 290 of 297, and over ocean
    cross-pol sits 6-10 dB below co-pol by physics. Verified again from the old cache's
    own manifest: its `vv_med` field (read(1)) has median -32.87 dB against `vh_med`
    (read(2)) at -20.20 dB, channel 0 darker in 99.9% of 2,565 scenes.

    The old cache read band 1 as VV, so every model in models/ was trained with
    CROSS-POL in channel 0 while Akshat's GEE exports put CO-POL there. That mismatch is
    why Layer 1 returned P(oil) ~ 0.002 on real scenes and ~0.999 once the channels were
    matched by hand.

    Channel 0 is now VV (co-pol, the channel carrying the oil signal) and channel 1 is
    VH. **Any checkpoint trained on the old cache is incompatible with this one** — the
    channels are transposed. Retrain, do not mix.

    NOTE, measured rather than assumed: fixing this changed essentially nothing about
    ACCURACY. The E1 ablation (12 epochs, stratified fold) gave tile val IoU 0.6997 with
    the old order against 0.6911 with the new, and the confidence probe moved the wrong
    way. The rename is carried because a cache rebuild is the one moment it is free and
    leaving `vv` pointing at VH is a landmine — not because it buys a number.

    `mode` selects the normalisation, and defaults to NORMALISE_MODE:
      "median"  whole-scene median + 1.4826*MAD — the original
      "sea"     sea-referenced, plan E2 — brightest-mode selection with a coastline
                land mask, which un-compresses scenes where oil is a large fraction of
                the frame (scale was 1.8x-4.2x too wide on the >=30% band)
    """
    mode = mode or NORMALISE_MODE
    with rasterio.open(img_path) as src:
        vh_raw = src.read(1).astype(np.float32)                 # band 1 IS cross-pol
        vv_raw = src.read(2).astype(np.float32) if src.count >= 2 else vh_raw.copy()
        transform = src.transform
    n_vv, val_vv, ref_vv, sc_vv = _norm(vv_raw, mode=mode, transform=transform)
    n_vh, val_vh, ref_vh, sc_vh = _norm(vh_raw, mode=mode, transform=transform)
    norm = np.stack([n_vv, n_vh], axis=-1)                      # channel 0 = VV
    valid = val_vv & val_vh
    # Both references are stored. Layer 3 inverts contrast_db through the MEDIAN pair, so
    # keeping it means the reported decibels do not change meaning when `mode` changes.
    med_vv, mad_vv = _median_reference(vv_raw)
    med_vh, mad_vh = _median_reference(vh_raw)
    stats = {"vv_med": round(med_vv, 4), "vv_mad": round(mad_vv, 4),
             "vh_med": round(med_vh, 4), "vh_mad": round(mad_vh, 4),
             "vv_ref": round(ref_vv, 4), "vv_scale": round(sc_vv, 4),
             "vh_ref": round(ref_vh, 4), "vh_scale": round(sc_vh, 4),
             "norm_mode": mode}
    return norm, valid, stats


def load_mask(mask_path, shape):
    if not os.path.exists(mask_path):
        return np.zeros(shape, np.uint8)
    with rasterio.open(mask_path) as m:
        return (m.read(1) > 0).astype(np.uint8)


def tile_grid(h, w, size=TILE):
    for r in range(0, h - size + 1, size):
        for c in range(0, w - size + 1, size):
            yield r, c


class ShardWriter:
    """Accumulates tiles and flushes fixed-size .npy shards, so peak RAM stays
    bounded no matter how many scenes are processed."""

    def __init__(self, prefix):
        self.prefix = prefix
        self.imgs, self.msks, self.meta = [], [], []
        self.shard = 0
        self.total = 0
        os.makedirs(TILES, exist_ok=True)

    def add(self, img, msk, meta):
        self.imgs.append(img.astype(np.float16))
        self.msks.append(msk.astype(np.uint8))
        self.meta.append(meta)
        self.total += 1
        if len(self.imgs) >= SHARD:
            self.flush()

    def flush(self):
        if not self.imgs:
            return
        np.save(os.path.join(TILES, f"tiles_{self.prefix}_{self.shard:03d}.npy"),
                np.stack(self.imgs))
        np.save(os.path.join(TILES, f"masks_{self.prefix}_{self.shard:03d}.npy"),
                np.stack(self.msks))
        print(f"    shard {self.shard:03d}: {len(self.imgs)} tiles", flush=True)
        self.imgs, self.msks = [], []
        self.shard += 1

    def close(self):
        self.flush()
        with open(os.path.join(TILES, f"index_{self.prefix}.json"), "w") as fh:
            json.dump({"n_tiles": self.total, "n_shards": self.shard,
                       "tile_px": TILE, "shard_size": SHARD,
                       "meta": self.meta}, fh)


def run(parts_key, limit=None, suffix="", mode=None):
    os.makedirs(CACHE, exist_ok=True)
    prefix = PARTS[parts_key]["prefix"] + (suffix or "")
    # The old cache is NOT overwritten. A rebuild that turns out worse has to be
    # recoverable, and 10.7 GB against 139 GB free is a cheap insurance premium. The
    # sea-normalised cache lands as P12sea alongside P12, so both can be trained from
    # and compared without re-running anything.

    jobs = _build_jobs(parts_key)
    if limit:
        # Interleave the classes so a --limit smoke test still sees all three.
        by_cls = {c: [j for j in jobs if j[1] == c] for c in CLASSES}
        jobs = [j for i in range(limit) for c in CLASSES
                if i < len(by_cls[c]) for j in [by_cls[c][i]]]
    print(f"\n  {len(jobs)} scenes\n")

    scenes, scene_labels, scene_ids, manifest = [], [], [], {}
    writer = ShardWriter(prefix)
    rng = np.random.default_rng(42)
    n_pos_tiles = n_neg_tiles = n_hard_tiles = 0
    t0 = time.time()

    for i, (scene_id, cls, img_path, msk_path) in enumerate(jobs, 1):
        try:
            norm, valid, stats = scene_arrays(img_path, mode=mode)
            h, w = valid.shape
            gt = load_mask(msk_path, (h, w)) if cls == "Oil" else np.zeros((h, w), np.uint8)

            # ---- Layer 1 artefact: the whole scene at 256x256 ----------------
            small = cv2.resize(norm, (SCENE_SIZE, SCENE_SIZE), interpolation=cv2.INTER_AREA)
            scenes.append(small.astype(np.float16))
            scene_labels.append(1 if cls == "Oil" else 0)
            scene_ids.append(scene_id)
            manifest[scene_id] = {"class": cls, "label": 1 if cls == "Oil" else 0,
                                  "oil_frac": round(float(gt.mean()), 6), **stats}

            # ---- Layer 2 artefact: tiles ------------------------------------
            cand = []
            for r, c in tile_grid(h, w):
                vsl = valid[r:r + TILE, c:c + TILE]
                if (~vsl).mean() > MAX_INVALID_FRAC:
                    continue
                msl = gt[r:r + TILE, c:c + TILE]
                cand.append((r, c, float(msl.mean()),
                             float(norm[r:r + TILE, c:c + TILE, 0].mean())))

            if cls == "Oil":
                pos = [t for t in cand if t[2] >= MIN_OIL_FRAC]
                # Richest tiles first, then cap — a 30%-oil tile teaches more
                # than the twentieth 1% tile off the same slick.
                pos.sort(key=lambda t: -t[2])
                pos = pos[:MAX_POS_PER_SCENE]
                neg = [t for t in cand if t[2] == 0.0]
                # Equal number of random negatives from the SAME scene, so the
                # network cannot separate classes on scene-level appearance.
                if neg and pos:
                    n_take = min(len(pos), len(neg), MAX_NEG_PER_SCENE)
                    idx = rng.choice(len(neg), size=n_take, replace=False)
                    neg = [neg[k] for k in idx]
                else:
                    neg = []
                keep = [(t, "pos") for t in pos] + [(t, "neg") for t in neg]
                n_pos_tiles += len(pos)
                n_neg_tiles += len(neg)
            else:
                # Darkest first — the tiles that actually look like oil.
                k = DARK_NEG_PER_LOOKALIKE if cls == "Lookalike" else DARK_NEG_PER_NOOIL
                cand.sort(key=lambda t: t[3])
                keep = [(t, "hard") for t in cand[:k]]
                n_hard_tiles += len(keep)

            for (r, c, oil_frac, dark), kind in keep:
                writer.add(norm[r:r + TILE, c:c + TILE, :],
                           gt[r:r + TILE, c:c + TILE],
                           {"scene_id": scene_id, "class": cls, "row": r, "col": c,
                            "oil_frac": round(oil_frac, 5), "kind": kind})

        except Exception as exc:
            print(f"  [ERROR] {scene_id}: {exc}", flush=True)
            continue

        if i % 50 == 0 or i == len(jobs):
            el = time.time() - t0
            rate = i / max(el, 1e-9)
            print(f"  [{i:>4}/{len(jobs)}] {scene_id:<22} tiles={writer.total:>6}  "
                  f"{rate:.2f} scene/s  ETA {(len(jobs)-i)/max(rate,1e-9)/60:.1f} min",
                  flush=True)

    writer.close()

    scenes_arr = np.stack(scenes)
    np.save(os.path.join(CACHE, f"scenes_{prefix}.npy"), scenes_arr)
    with open(os.path.join(CACHE, f"manifest_{prefix}.json"), "w") as fh:
        json.dump({"prefix": prefix, "parts": parts_key,
                   "norm_mode": mode or NORMALISE_MODE,
                   "channel_order": "0=VV(co-pol, read band 2), 1=VH(cross-pol, read band 1)",
                   "scene_ids": scene_ids, "scene_labels": scene_labels,
                   "scene_px": SCENE_SIZE, "tile_px": TILE,
                   "clip_sigma": CLIP_SIGMA, "min_oil_frac": MIN_OIL_FRAC,
                   "n_tiles": writer.total, "scenes": manifest}, fh)

    print()
    print("=" * 70)
    print(f"  CACHE COMPLETE  ({parts_key})")
    print("=" * 70)
    print(f"  scenes  : {scenes_arr.shape}  {scenes_arr.nbytes/1e6:.0f} MB  "
          f"({sum(scene_labels)} oil / {len(scene_labels)-sum(scene_labels)} not)")
    print(f"  tiles   : {writer.total}  in {writer.shard} shard(s)")
    print(f"            {n_pos_tiles} positive, {n_neg_tiles} same-scene negative, "
          f"{n_hard_tiles} hard negative")
    print(f"  wrote   : {CACHE}/scenes_{prefix}.npy")
    print(f"            {CACHE}/manifest_{prefix}.json")
    print(f"            {TILES}/tiles_{prefix}_*.npy")
    print(f"  wall    : {(time.time()-t0)/60:.1f} min")

    if n_pos_tiles == 0 and parts_key != "3":
        print("\n  [WARNING] zero positive tiles — check the Oil mask paths.")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--parts", default="1,2", choices=sorted(PARTS))
    ap.add_argument("--limit", type=int, default=None,
                    help="process only N scenes per class — smoke test")
    ap.add_argument("--normalise", choices=("median", "sea"), default=NORMALISE_MODE,
                    help="median = the original whole-scene median+MAD. sea = plan E2, "
                         "sea-referenced, which un-compresses large-slick scenes where the "
                         "old scale was 1.8x-4.2x too wide.")
    ap.add_argument("--suffix", default="",
                    help="appended to the cache prefix, e.g. --suffix sea writes P12sea and "
                         "leaves the existing P12 cache untouched.")
    a = ap.parse_args()
    # suffix and mode MUST be passed. They were added as CLI flags and not wired to
    # this call, so --suffix was silently ignored and a 9-scene smoke build overwrote
    # the real 2,565-scene P12 cache. An accepted argument that changes nothing is
    # worse than no argument at all.
    run(a.parts, limit=a.limit, suffix=a.suffix, mode=a.normalise)
