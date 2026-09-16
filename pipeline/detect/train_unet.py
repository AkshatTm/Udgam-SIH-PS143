"""
train_unet.py  -  Layer 2, the segmenter.  Owner: Soumirya.

    python pipeline/detect/build_cache.py --parts 1,2
    python pipeline/detect/train_unet.py

"Exactly which pixels?"  ->  binary mask  ->  contours  ->  the polygon Stage 2
seeds from, and the IoU number.

ARCHITECTURE
------------
The paper's best configuration: 16 -> 32 -> 64 -> 128 -> 256 -> 512 -> 1024 with
Upsampling2D in the expansion path, Focal Loss, 256x256x2 input. On a 6 GB card
the deepest block is the first thing to drop (--depth 6), NEVER the input size:
spatial resolution matters more than depth for thin slicks, and a slick two
pixels wide does not survive being halved.

Mixed precision is on by default — roughly doubles the batch size for free.

LOSS (D4)
---------
Focal Loss, because oil is a small fraction of pixels even inside a positive
tile. Plain cross-entropy converges to predicting all-background and reports a
beautiful accuracy while segmenting nothing. If validation IoU sits at zero for
several epochs the model has collapsed that way: lower --alpha or raise the
positive tile fraction. Do not just train longer.

WHAT IS MONITORED
-----------------
Validation IoU on the OIL CLASS, never accuracy. At this class balance accuracy
is meaningless.

THRESHOLD
---------
Swept on validation. The paper needed 0.99 for its probability-output models, so
0.5 is not assumed.

SPLIT
-----
By SCENE, not by tile. Tiles from one 2048x2048 image share background
statistics, sensor geometry and often the same slick; splitting by tile lets
them leak and inflates the IoU we would put in front of judges.
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import sys
import time

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
from sklearn.model_selection import train_test_split

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.abspath(os.path.join(_HERE, "..", ".."))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

CACHE = os.path.join(_ROOT, "data", "cache")
TILES = os.path.join(CACHE, "tiles")
MODELS = os.path.join(_HERE, "models")
CKPT = os.path.join(MODELS, "unet.pt")


def _cache_convention(prefix):
    """-> {"norm_mode":..., "land_mask":...} read from the cache's OWN manifest.

    This used to be ("sea" if prefix.endswith("sea") else "median"), a filename
    heuristic standing in for data that the manifest records explicitly. It broke
    the moment a third cache appeared: P12seanl is sea-normalised but does not end
    in "sea", so the run stamped norm_mode="median" onto a sea-trained model and
    inference would have median-normalised it. Nothing would have errored; the
    scene-level score would simply have been wrong, which is the same failure mode
    that already cost a full train+eval cycle.
    """
    f = os.path.join(_ROOT, "data", "cache", "manifest_%s.json" % prefix)
    conv = {"norm_mode": "median", "land_mode": "full"}
    try:
        m = json.loads(open(f, encoding="utf-8").read())
        conv["norm_mode"] = m.get("norm_mode") or "median"
        lmode = m.get("land_mode")
        if lmode:
            conv["land_mode"] = lmode
        else:
            lm = m.get("land_mask")
            conv["land_mode"] = "full" if (lm is None or lm) else "none"
    except Exception as exc:
        print("  [WARN] cannot read %s (%s) - assuming %s" % (f, exc, conv))
    return conv
META = os.path.join(MODELS, "unet_meta.json")

DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")
FILTERS = [16, 32, 64, 128, 256, 512, 1024]


# ---------------------------------------------------------------------------
# Model
# ---------------------------------------------------------------------------

def conv_block(cin, cout):
    return nn.Sequential(
        nn.Conv2d(cin, cout, 3, padding=1), nn.BatchNorm2d(cout), nn.ReLU(inplace=True),
        nn.Conv2d(cout, cout, 3, padding=1), nn.BatchNorm2d(cout), nn.ReLU(inplace=True))


class UNet(nn.Module):
    """Upsampling2D (bilinear) expansion path, as in the paper's best run —
    not transposed convolutions, which checkerboard on thin features."""

    def __init__(self, in_ch=2, depth=7, filters=FILTERS):
        super().__init__()
        f = filters[:depth]
        self.downs = nn.ModuleList()
        c = in_ch
        for ch in f[:-1]:
            self.downs.append(conv_block(c, ch))
            c = ch
        self.bottom = conv_block(c, f[-1])
        self.ups = nn.ModuleList()
        rev = list(reversed(f[:-1]))
        c = f[-1]
        for ch in rev:
            self.ups.append(conv_block(c + ch, ch))
            c = ch
        self.out = nn.Conv2d(c, 1, 1)
        self.pool = nn.MaxPool2d(2)

    def forward(self, x):
        skips = []
        for d in self.downs:
            x = d(x)
            skips.append(x)
            x = self.pool(x)
        x = self.bottom(x)
        for u, s in zip(self.ups, reversed(skips)):
            x = F.interpolate(x, size=s.shape[-2:], mode="bilinear", align_corners=False)
            x = u(torch.cat([x, s], dim=1))
        return self.out(x).squeeze(1)          # logits (B,H,W)


# ---------------------------------------------------------------------------
# Loss and metric
# ---------------------------------------------------------------------------

def focal_loss(logits, target, alpha=0.75, gamma=2.0):
    """Binary focal loss. alpha weights the POSITIVE (oil) class."""
    p = torch.sigmoid(logits)
    ce = F.binary_cross_entropy_with_logits(logits, target, reduction="none")
    p_t = p * target + (1 - p) * (1 - target)
    a_t = alpha * target + (1 - alpha) * (1 - target)
    return (a_t * (1 - p_t) ** gamma * ce).mean()


def iou_oil(pred_bin, target):
    """Intersection over union on the OIL class, summed over the batch."""
    inter = float((pred_bin * target).sum())
    union = float(((pred_bin + target) > 0).sum())
    return inter, union


# ---------------------------------------------------------------------------
# Data
# ---------------------------------------------------------------------------

class TileStore:
    """Memory-maps the shards so the full cache never has to fit in RAM."""

    def __init__(self, prefix):
        idx_path = os.path.join(TILES, f"index_{prefix}.json")
        if not os.path.exists(idx_path):
            raise SystemExit(
                f"{idx_path} not found. Build the cache first:\n"
                f"  python pipeline/detect/build_cache.py --parts 1,2")
        index = json.loads(open(idx_path).read())
        self.meta = index["meta"]
        self.shard_size = index["shard_size"]
        self.imgs = [np.load(p, mmap_mode="r") for p in
                     sorted(glob.glob(os.path.join(TILES, f"tiles_{prefix}_*.npy")))]
        self.msks = [np.load(p, mmap_mode="r") for p in
                     sorted(glob.glob(os.path.join(TILES, f"masks_{prefix}_*.npy")))]
        self.counts = [len(a) for a in self.imgs]
        self.offsets = np.cumsum([0] + self.counts)
        self.n = int(self.offsets[-1])
        if self.n != len(self.meta):
            print(f"  [warn] {self.n} tiles on disk but {len(self.meta)} in the index")
            self.n = min(self.n, len(self.meta))

    def get(self, i):
        s = int(np.searchsorted(self.offsets, i, side="right") - 1)
        j = i - self.offsets[s]
        return self.imgs[s][j], self.msks[s][j]

    def batch(self, idx):
        x = np.stack([self.imgs[int(np.searchsorted(self.offsets, i, "right") - 1)]
                      [i - self.offsets[int(np.searchsorted(self.offsets, i, "right") - 1)]]
                      for i in idx]).astype(np.float32)
        y = np.stack([self.msks[int(np.searchsorted(self.offsets, i, "right") - 1)]
                      [i - self.offsets[int(np.searchsorted(self.offsets, i, "right") - 1)]]
                      for i in idx]).astype(np.float32)
        return (torch.from_numpy(x).permute(0, 3, 1, 2), torch.from_numpy(y))


def _gaussian_blur(x, sigma):
    """Separable Gaussian on (B,C,H,W), kept on-device."""
    r = max(1, int(round(3 * sigma)))
    k = torch.arange(-r, r + 1, device=x.device, dtype=x.dtype)
    k = torch.exp(-(k ** 2) / (2 * sigma ** 2)); k = k / k.sum()
    c = x.shape[1]
    x = F.conv2d(x, k.view(1, 1, 1, -1).expand(c, 1, 1, -1), padding=(0, r), groups=c)
    return F.conv2d(x, k.view(1, 1, -1, 1).expand(c, 1, -1, 1), padding=(r, 0), groups=c)


def augment(x, y, domain=True, xpol_ch=1, xpol_p=0.25):
    """Geometric augmentation, plus DOMAIN augmentation when domain=True.

    WHY THE DOMAIN HALF EXISTS — read the first training curve before changing
    this. Validation IoU peaked at 0.6843 on EPOCH 3 and then fell to 0.6258 by
    epoch 9 while the training loss kept dropping (0.01083 -> 0.00709). That is
    overfitting, not undertraining: 31.5M parameters against 23,760 tiles with
    geometric augmentation only. Training longer made it worse, so the fix is to
    regularise and then train longer under that regime.

    The same four transforms the scene classifier uses, for the same reason —
    they span what a real sensor and processing chain actually vary on, rather
    than just where north is:

      blur / rescale   effective resolution and ground sampling distance
      speckle          residual noise the training set does not contain
      dropout          nodata blocks, and VH corruption for the case where
                       cross-pol sits below the sensor noise floor

    Geometry transforms move the MASK with the image; the domain transforms do
    not, because blurring a tile does not move the oil in it. The one exception
    is nodata: a blanked block genuinely has no visible oil, so the target is
    zeroed there too. Getting that backwards would teach the network to predict
    oil under a blackout.
    """
    k = int(torch.randint(0, 4, (1,)).item())
    if k:
        x, y = torch.rot90(x, k, (2, 3)), torch.rot90(y, k, (1, 2))
    if torch.rand(1).item() < 0.5:
        x, y = torch.flip(x, (3,)), torch.flip(y, (2,))
    if torch.rand(1).item() < 0.5:
        x, y = torch.flip(x, (2,)), torch.flip(y, (1,))
    if torch.rand(1).item() < 0.3:
        x = x * (0.9 + 0.2 * torch.rand(1))
    if not domain:
        return x, y

    if torch.rand(1).item() < 0.40:
        x = _gaussian_blur(x, 0.5 + 1.5 * float(torch.rand(1)))
    if torch.rand(1).item() < 0.30:
        f = float(0.5 + 0.4 * torch.rand(1))
        h, w = x.shape[-2:]
        x = F.interpolate(F.interpolate(x, scale_factor=f, mode="area"),
                          size=(h, w), mode="bilinear", align_corners=False)
    if torch.rand(1).item() < 0.30:
        x = x + torch.randn_like(x) * (0.02 + 0.06 * float(torch.rand(1)))
    if torch.rand(1).item() < 0.25:
        h, w = x.shape[-2:]
        for _ in range(int(torch.randint(1, 3, (1,)).item())):
            bh = int(torch.randint(h // 10, h // 3, (1,)).item())
            bw = int(torch.randint(w // 10, w // 3, (1,)).item())
            r0 = int(torch.randint(0, max(1, h - bh), (1,)).item())
            c0 = int(torch.randint(0, max(1, w - bw), (1,)).item())
            x[:, :, r0:r0 + bh, c0:c0 + bw] = 0.0
            y[:, r0:r0 + bh, c0:c0 + bw] = 0.0      # no image, no oil to find
    # Cross-pol dropout. THE CHANNEL MATTERS: cache channel 0 is read(1) = VH and
    # channel 1 is read(2) = VV, so the historical default of 1 corrupts the CO-POL
    # channel — the only one carrying oil signal — in 25% of steps. Parameterised
    # rather than silently corrected so the ablation can measure what it was worth.
    if torch.rand(1).item() < xpol_p and x.shape[1] >= 2:
        other = 1 - xpol_ch
        if torch.rand(1).item() < 0.5:
            x[:, xpol_ch] = torch.randn_like(x[:, xpol_ch]) * 0.15
        else:
            x[:, xpol_ch] = x[:, other]
    return x, y


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--epochs", type=int, default=25)
    # 32, not the 8 the brief assumed. Measured on this card: the full
    # depth-7 (31.5M param) U-Net peaks at 2.85 GB at batch 32 out of 6.44 GB,
    # so the "cut the deepest block if VRAM is tight" contingency is not needed
    # and we keep the paper's architecture intact. 4x fewer optimiser steps per
    # epoch means more epochs in the time available, which is where the accuracy
    # actually comes from.
    ap.add_argument("--batch-size", type=int, default=32)
    ap.add_argument("--lr", type=float, default=1e-3)
    ap.add_argument("--depth", type=int, default=7,
                    help="7 = the paper's 16..1024; use 6 if VRAM is tight")
    ap.add_argument("--alpha", type=float, default=0.75, help="focal weight on oil")
    ap.add_argument("--gamma", type=float, default=2.0)
    ap.add_argument("--patience", type=int, default=6)
    ap.add_argument("--no-amp", action="store_true")
    ap.add_argument("--xpol-channel", type=int, default=1, choices=(0, 1),
                    help="which channel the cross-pol dropout corrupts. DEFAULT 1 IS THE "
                         "BUG: cache channel 1 is read(2), the CO-POL channel, verified "
                         "from the manifest where channel 0 runs 12.7 dB darker in 99.9%% "
                         "of 2565 scenes. Channel 0 is the real cross-pol. Kept as the "
                         "default so a plain run still reproduces the shipped model.")
    ap.add_argument("--xpol-p", type=float, default=0.25,
                    help="probability of the cross-pol dropout. At 0.25 on the wrong "
                         "channel, one training step in four shows a positive mask with "
                         "the only informative channel replaced by noise.")
    ap.add_argument("--split", choices=("legacy", "stratified"), default="legacy",
                    help="legacy = train_test_split(uniq, 0.15, seed 42), which put 8 of "
                         "the 9 >=30%%-coverage scenes into TRAINING. stratified = "
                         "split.py, coverage-stratified with a 3-fold rotation on that "
                         "band. Comparisons across runs must use the same one.")
    ap.add_argument("--fold", type=int, default=0, help="stratified split fold")
    ap.add_argument("--cache", default="P12",
                    help="tile-cache prefix: P12 (median, baseline) or P12sea (E2, "
                         "sea-referenced). Both carry the corrected channel order; a "
                         "checkpoint from one is NOT loadable against the other.")
    ap.add_argument("--tag", default="", help="suffix for the output files, so ablation "
                                              "runs do not overwrite each other")
    ap.add_argument("--no-domain-aug", action="store_true",
                    help="geometric augmentation only — the run that overfitted by epoch 3")
    ap.add_argument("--weight-decay", type=float, default=1e-4)
    ap.add_argument("--seed", type=int, default=42,
                    help="TRAINING seed only - weight init, shuffling, augmentation. "
                         "The split is NOT affected: split.py uses its own generator at "
                         "a fixed seed, so --seed re-rolls the model and holds the data "
                         "constant. That is what makes it a measurement of training "
                         "variance. Needed because one val scene swung IoU 0.82 -> 0.00 "
                         "between runs on BIT-IDENTICAL input, so the noise floor is "
                         "unknown and no change under it can be called an improvement.")
    a = ap.parse_args()

    os.makedirs(MODELS, exist_ok=True)
    torch.manual_seed(a.seed); np.random.seed(a.seed)
    amp = (not a.no_amp) and DEVICE.type == "cuda"

    print("=" * 72)
    print(f"  LAYER 2 — U-Net   device={DEVICE}  depth={a.depth}  amp={amp}")
    print("=" * 72)

    # The cache prefix decides which NORMALISATION the model is trained on:
    #   P12     median-referenced, the baseline
    #   P12sea  sea-referenced (plan E2)
    # This was hardcoded, so an E2 run would have silently trained on the baseline
    # cache and produced a meaningless null. Comparisons must differ ONLY in this.
    store = TileStore(a.cache)
    print(f"  cache : {a.cache}")
    scenes = np.array([m["scene_id"] for m in store.meta[:store.n]])
    oilfrac = np.array([m["oil_frac"] for m in store.meta[:store.n]])
    kinds = np.array([m["kind"] for m in store.meta[:store.n]])
    print(f"  {store.n} tiles from {len(set(scenes))} scenes  "
          f"({int((kinds=='pos').sum())} pos, {int((kinds=='neg').sum())} neg, "
          f"{int((kinds=='hard').sum())} hard)")
    print(f"  mean oil fraction over positive tiles: "
          f"{oilfrac[kinds=='pos'].mean() if (kinds=='pos').any() else 0:.4f}")

    if a.split == "stratified":
        from pipeline.detect.split import load_manifest, make_split
        tr_l, va_l, _ = make_split(load_manifest(), fold=a.fold)
        tr_s, va_s = set(tr_l), set(va_l)
        print(f"  split: STRATIFIED by coverage (split.py), fold {a.fold}")
    else:
        uniq = sorted(set(scenes))
        tr_s, va_s = train_test_split(uniq, test_size=0.15, random_state=42)
        tr_s, va_s = set(tr_s), set(va_s)
        print("  split: LEGACY — 1 scene >=30% in validation; see split.py")
    tr_idx = np.array([i for i in range(store.n) if scenes[i] in tr_s])
    va_idx = np.array([i for i in range(store.n) if scenes[i] in va_s])
    print(f"  split by SCENE: {len(tr_idx)} train tiles / {len(va_idx)} val tiles")

    model = UNet(depth=a.depth).to(DEVICE)
    print(f"  parameters: {sum(p.numel() for p in model.parameters()):,}")
    opt = torch.optim.Adam(model.parameters(), lr=a.lr, weight_decay=a.weight_decay)
    scaler = torch.amp.GradScaler("cuda", enabled=amp)
    sched = torch.optim.lr_scheduler.ReduceLROnPlateau(opt, mode="max", factor=0.5, patience=2)

    best_iou, best_state, bad = -1.0, None, 0
    t0 = time.time()
    for ep in range(1, a.epochs + 1):
        model.train()
        order = np.random.permutation(tr_idx)
        tl = n = 0
        for i in range(0, len(order), a.batch_size):
            xb, yb = store.batch(order[i:i + a.batch_size])
            xb, yb = augment(xb, yb, domain=not a.no_domain_aug,
                         xpol_ch=a.xpol_channel, xpol_p=a.xpol_p)
            xb, yb = xb.to(DEVICE), yb.to(DEVICE)
            opt.zero_grad(set_to_none=True)
            with torch.amp.autocast("cuda", enabled=amp):
                loss = focal_loss(model(xb), yb, a.alpha, a.gamma)
            scaler.scale(loss).backward()
            scaler.step(opt); scaler.update()
            tl += float(loss) * len(yb); n += len(yb)

        model.eval()
        inter = union = 0.0
        with torch.no_grad():
            for i in range(0, len(va_idx), a.batch_size):
                xb, yb = store.batch(va_idx[i:i + a.batch_size])
                xb, yb = xb.to(DEVICE), yb.to(DEVICE)
                with torch.amp.autocast("cuda", enabled=amp):
                    p = torch.sigmoid(model(xb)).float()
                ii, uu = iou_oil((p >= 0.5).float(), yb)
                inter += ii; union += uu
        v_iou = inter / max(union, 1.0)
        sched.step(v_iou)

        flag = ""
        if v_iou > best_iou + 1e-4:
            best_iou, bad = v_iou, 0
            best_state = {k: v.detach().cpu().clone() for k, v in model.state_dict().items()}
            # Also to DISK, every time. This used to live only in RAM until the run
            # finished, so a crash at epoch 29 of a 200-minute run lost everything.
            _t = CKPT.replace(".pt", f"_{a.tag}.pt") if a.tag else CKPT
            torch.save({"state_dict": best_state, "arch": "UNet", "depth": a.depth,
                        "in_ch": 2, "threshold": 0.5, "epoch": ep,
                        "val_iou_tiles": round(float(v_iou), 4), "partial": True},
                       _t.replace(".pt", "_running.pt"))
            flag = "  *best"
        else:
            bad += 1
        print(f"  ep {ep:>3}  loss {tl/max(n,1):.5f}  val_IoU@0.5 {v_iou:.4f}{flag}", flush=True)
        if v_iou == 0.0 and ep >= 5:
            print("  [D4] validation IoU still 0 — the model has collapsed to "
                  "all-background. Lower --alpha or raise the positive tile share; "
                  "do not just train longer.")
        if bad >= a.patience:
            print(f"  early stop (no IoU improvement for {a.patience} epochs)")
            break

    if best_state:
        model.load_state_dict(best_state)
    print(f"  trained in {(time.time()-t0)/60:.1f} min   best val IoU {best_iou:.4f}")

    # ---- sweep the binarisation threshold on VALIDATION ----------------------
    print("\n  threshold sweep on validation (0.5 is NOT assumed):")
    probs, targs = [], []
    model.eval()
    with torch.no_grad():
        for i in range(0, len(va_idx), a.batch_size):
            xb, yb = store.batch(va_idx[i:i + a.batch_size])
            with torch.amp.autocast("cuda", enabled=amp):
                p = torch.sigmoid(model(xb.to(DEVICE))).float().cpu()
            probs.append(p.numpy().astype(np.float16)); targs.append(yb.numpy().astype(np.uint8))
    probs = np.concatenate(probs); targs = np.concatenate(targs)

    best_t, best_t_iou = 0.5, -1.0
    for t in [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 0.95, 0.99]:
        pb = probs >= t
        inter = float((pb & (targs > 0)).sum())
        union = float((pb | (targs > 0)).sum())
        iou = inter / max(union, 1.0)
        mark = ""
        if iou > best_t_iou:
            best_t, best_t_iou, mark = t, iou, "  <-"
        print(f"    t={t:<5} IoU {iou:.4f}{mark}")

    ckpt_path = CKPT if not a.tag else CKPT.replace(".pt", f"_{a.tag}.pt")
    meta_path = META if not a.tag else META.replace(".json", f"_{a.tag}.json")
    torch.save({"state_dict": model.state_dict(), "arch": "UNet",
                "depth": a.depth, "in_ch": 2, "threshold": best_t}, ckpt_path)
    with open(meta_path, "w") as fh:
        json.dump({"depth": a.depth, "filters": FILTERS[:a.depth],
                   "loss": f"focal(alpha={a.alpha}, gamma={a.gamma})",
                   "threshold": best_t, "threshold_selected_on": "validation tiles",
                   "val_iou_at_threshold": round(best_t_iou, 4),
                   "val_iou_at_0.5": round(best_iou, 4),
                   "n_train_tiles": int(len(tr_idx)), "n_val_tiles": int(len(va_idx)),
                   "trained_on": "Zenodo Parts I+II tiles, split by scene",
                   # PROVENANCE. A checkpoint that does not say which convention it
                   # needs is how the channels got transposed at inference and both
                   # E2 models scored ~0.000 at scene level while training fine on
                   # tiles. nets.py reads these to build the input correctly.
                   "cache": a.cache,
                   "channel_order": ("vv_first" if a.cache != "P12legacy" else "band_order"),
                   **_cache_convention(a.cache),
                   "seed": a.seed,
                   "split": a.split, "fold": a.fold,
                   "xpol_channel": a.xpol_channel, "xpol_p": a.xpol_p}, fh, indent=2)
    print(f"\n  saved {ckpt_path}\n  saved {meta_path}")
    print(f"  best validation IoU {best_t_iou:.4f} at threshold {best_t}")
    print("\n  Part III IoU — gated and ungated — is evaluate_unet.py, not this file.")


if __name__ == "__main__":
    main()
