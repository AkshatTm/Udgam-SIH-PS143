"""
train_classifier.py  -  Layer 1, the scene classifier.  Owner: Soumirya.

    python pipeline/detect/build_cache.py --parts 1,2
    python pipeline/detect/build_cache.py --parts 3
    python pipeline/detect/train_classifier.py

"Is there any oil in this scene at all?"  ->  yes/no + confidence.
This produces the HEADLINE ACCURACY NUMBER, and it is what gates the U-Net.

WHY THE GATE IS NOT OPTIONAL (decision D2)
------------------------------------------
The dataset's own authors report that their U-Net segments erroneously on
look-alike images, and that classification-then-segmentation is what reduces
false positives in look-alike scenarios. Run the U-Net alone and demo cases 6
and 7 — the look-alike scene and the clean-ocean scene, which exist SPECIFICALLY
to prove the system can say no — come back with hallucinated oil.

ARCHITECTURE
------------
The paper's reported optimum: six convolutional layers, 32 filters, two hidden
dense layers, sigmoid output, on 256x256x2 (VV, VH) per-scene-MAD-normalised
input. Small enough to train on a 6 GB laptop GPU in minutes.

THRESHOLD (3.4)
---------------
Chosen on a PR curve over the VALIDATION split of Parts I+II — never on Part III.
Picking an operating point by looking at test performance is test-set
contamination through the back door.

We deliberately prefer RECALL over precision. A missed spill is invisible; a
false positive gets rejected by Layer 2 or by a human looking at the screen.
That is a design decision, not a compromise, and it gets said out loud.

EVALUATION (3.3) — on Part III and nothing else
------------------------------------------------
  overall scene accuracy          the headline
  recall on the 150 oil scenes    how many spills we noticed at all
  look-alike rejection rate       of 150 look-alikes, how many correctly called no-oil
  clean-ocean rejection rate      same for the 150 no-oil scenes
Look-alike-called-oil is the interesting error and is reported separately from
clean-ocean-called-oil.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
from sklearn.metrics import precision_recall_curve, confusion_matrix
from sklearn.model_selection import train_test_split

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.abspath(os.path.join(_HERE, "..", ".."))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

CACHE = os.path.join(_ROOT, "data", "cache")
MODELS = os.path.join(_HERE, "models")
CKPT = os.path.join(MODELS, "scene_classifier.pt")
META = os.path.join(MODELS, "scene_classifier_meta.json")

DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")
DOMAIN_AUG = True   # set from --no-domain-aug


# ---------------------------------------------------------------------------
# Model
# ---------------------------------------------------------------------------

class SceneCNN(nn.Module):
    """6 conv layers -> global pool -> 2 hidden dense -> sigmoid.

    POOLING. The paper's configuration ends in global AVERAGE pooling. That is an
    average-shaped operation answering a max-shaped question: "is there oil
    ANYWHERE in this scene?" A slick covers a few percent of a 256x256 scene, and
    after six 2x poolings it occupies perhaps one of the final 4x4=16 cells, so
    averaging dilutes its evidence ~16x against the background it is competing
    with. Global MAX pooling reports the single most oil-like location and does
    not dilute; concatenating both keeps the average's robustness to speckle.
    Which one actually wins is decided on VALIDATION in main(), not asserted here.

    WIDTH. `filters` may be one int (the paper's flat 32) or a per-layer list.
    """

    def __init__(self, in_ch=2, filters=32, hidden=(128, 64), pool="avg", dropout=0.3):
        super().__init__()
        chans = [filters] * 6 if isinstance(filters, int) else list(filters)
        blocks, c = [], in_ch
        for ch in chans:
            blocks += [nn.Conv2d(c, ch, 3, padding=1),
                       nn.BatchNorm2d(ch),
                       nn.ReLU(inplace=True),
                       nn.MaxPool2d(2)]
            c = ch
        self.conv = nn.Sequential(*blocks)          # 256 -> 4
        self.pool = pool
        feat = c * (2 if pool == "both" else 1)
        self.head = nn.Sequential(
            nn.Linear(feat, hidden[0]), nn.ReLU(inplace=True), nn.Dropout(dropout),
            nn.Linear(hidden[0], hidden[1]), nn.ReLU(inplace=True), nn.Dropout(dropout * 0.67),
            nn.Linear(hidden[1], 1))

    def forward(self, x):
        z = self.conv(x)
        avg = F.adaptive_avg_pool2d(z, 1).flatten(1)
        mx = F.adaptive_max_pool2d(z, 1).flatten(1)
        if self.pool == "avg":
            v = avg
        elif self.pool == "max":
            v = mx
        else:
            v = torch.cat([avg, mx], dim=1)
        return self.head(v).squeeze(1)              # logits


# Variants trained and compared on VALIDATION. The paper's configuration is
# first and is the honest baseline; the rest are hypotheses that have to earn
# their place on held-out-from-training data, never on Part III.
VARIANTS = {
    "paper_avg32":  dict(filters=32, pool="avg"),
    "max32":        dict(filters=32, pool="max"),
    "both32":       dict(filters=32, pool="both"),
    "both_wide":    dict(filters=[32, 32, 64, 64, 128, 128], pool="both"),
}


# ---------------------------------------------------------------------------
# Data
# ---------------------------------------------------------------------------

def load_split(prefix):
    arr = np.load(os.path.join(CACHE, f"scenes_{prefix}.npy"))          # (N,256,256,2) f16
    man = json.loads(open(os.path.join(CACHE, f"manifest_{prefix}.json")).read())
    y = np.asarray(man["scene_labels"], dtype=np.float32)
    ids = man["scene_ids"]
    classes = [man["scenes"][s]["class"] for s in ids]
    print(f"  {prefix}: {arr.shape}  {int(y.sum())} oil / {int((1-y).sum())} not-oil")
    return arr, y, ids, classes


def _gaussian_blur(x, sigma):
    """Separable Gaussian on (B,C,H,W). Cheap, and keeps the batch on the GPU."""
    r = max(1, int(round(3 * sigma)))
    k = torch.arange(-r, r + 1, device=x.device, dtype=x.dtype)
    k = torch.exp(-(k ** 2) / (2 * sigma ** 2))
    k = k / k.sum()
    c = x.shape[1]
    x = torch.nn.functional.conv2d(x, k.view(1, 1, 1, -1).expand(c, 1, 1, -1),
                                   padding=(0, r), groups=c)
    return torch.nn.functional.conv2d(x, k.view(1, 1, -1, 1).expand(c, 1, -1, 1),
                                      padding=(r, 0), groups=c)


def augment(x, domain=True):
    """Geometric augmentation, plus DOMAIN augmentation when domain=True.

    The geometric half (rotations, flips, contrast) is standard and was always
    here. The domain half exists because of a measured failure: this classifier
    reached 0.947 scene accuracy on the Zenodo Part III holdout and then returned
    P(oil)=0.003 on the Huntington GEE export, whose slick is unmistakable at
    -5.78 dB VV. VH noise, ground scale, bright-ship masking, nodata fill and
    slick size were each tested and each ruled out. What is left is that the
    network learned Zenodo-specific scene APPEARANCE — and the shortcut audit
    agrees: 17.2% of scenes it calls oil still read as oil once the slick is
    erased from them.

    Geometric augmentation cannot fix that, because rotating a Zenodo scene
    leaves it a Zenodo scene. These four transforms span the axes a real sensor
    and a real processing chain actually vary on:

      blur      lower effective resolution / heavier multilooking. Measured,
                Huntington is SMOOTHER than the training median (Laplacian
                variance 0.085 vs 0.122).
      rescale   different ground sampling distance, via down-then-up sampling.
      speckle   the other direction — more residual noise than training has.
      dropout   rectangular nodata blocks, and VH corruption. The VH case is
                not hypothetical: where sea VH falls below the sensor noise
                floor the band is thermal noise, so a model that leans on VH
                (ours leans 69% of its importance on it) must survive losing it.

    DESIGNED, NOT TUNED. These ranges were chosen to bracket plausible sensor
    variation before retraining, and are not iterated against Huntington — that
    scene is a reported observation, never a selection criterion (A6). Epoch and
    threshold selection remain on validation.
    """
    k = int(torch.randint(0, 4, (1,)).item())
    if k:
        x = torch.rot90(x, k, dims=(2, 3))
    if torch.rand(1).item() < 0.5:
        x = torch.flip(x, dims=(3,))
    if torch.rand(1).item() < 0.5:
        x = torch.flip(x, dims=(2,))
    if torch.rand(1).item() < 0.3:                  # mild contrast jitter
        x = x * (0.9 + 0.2 * torch.rand(1, device=x.device))
    if not domain:
        return x

    if torch.rand(1).item() < 0.40:                 # resolution / multilooking
        sigma = 0.5 + 1.5 * float(torch.rand(1))
        x = _gaussian_blur(x, sigma)
    if torch.rand(1).item() < 0.30:                 # ground sampling distance
        f = float(0.5 + 0.4 * torch.rand(1))
        h, w = x.shape[-2:]
        small = torch.nn.functional.interpolate(x, scale_factor=f, mode="area")
        x = torch.nn.functional.interpolate(small, size=(h, w), mode="bilinear",
                                            align_corners=False)
    if torch.rand(1).item() < 0.30:                 # residual speckle
        x = x + torch.randn_like(x) * (0.02 + 0.06 * float(torch.rand(1)))
    if torch.rand(1).item() < 0.30:                 # nodata blocks
        h, w = x.shape[-2:]
        for _ in range(int(torch.randint(1, 4, (1,)).item())):
            bh = int(torch.randint(h // 10, h // 3, (1,)).item())
            bw = int(torch.randint(w // 10, w // 3, (1,)).item())
            r0 = int(torch.randint(0, max(1, h - bh), (1,)).item())
            c0 = int(torch.randint(0, max(1, w - bw), (1,)).item())
            x[:, :, r0:r0 + bh, c0:c0 + bw] = 0.0
    if torch.rand(1).item() < 0.25 and x.shape[1] >= 2:
        # VH becomes noise, or a copy of VV. Forces the model to stay usable
        # when the cross-pol channel carries nothing, which is what happens
        # below the sensor noise floor.
        if torch.rand(1).item() < 0.5:
            x[:, 1] = torch.randn_like(x[:, 1]) * 0.15
        else:
            x[:, 1] = x[:, 0]
    return x


def batches(arr, y, idx, bs, shuffle, aug):
    order = np.random.permutation(idx) if shuffle else idx
    for i in range(0, len(order), bs):
        sel = order[i:i + bs]
        xb = torch.from_numpy(arr[sel].astype(np.float32)).permute(0, 3, 1, 2).to(DEVICE)
        yb = torch.from_numpy(y[sel]).to(DEVICE)
        if aug:
            xb = augment(xb, domain=DOMAIN_AUG)
        yield xb, yb


@torch.no_grad()
def predict(model, arr, y, bs=32):
    model.eval()
    out = []
    for i in range(0, len(arr), bs):
        xb = torch.from_numpy(arr[i:i + bs].astype(np.float32)).permute(0, 3, 1, 2).to(DEVICE)
        out.append(torch.sigmoid(model(xb)).float().cpu().numpy())
    return np.concatenate(out)


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------

def report(proba, y, classes, threshold):
    pred = (proba >= threshold).astype(int)
    yi = y.astype(int)
    acc = float((pred == yi).mean())
    cm = confusion_matrix(yi, pred, labels=[0, 1])
    tn, fp, fn, tp = cm.ravel()

    per_class = {}
    for c in ("Oil", "Lookalike", "No oil"):
        m = np.array([k == c for k in classes])
        if not m.any():
            continue
        if c == "Oil":
            per_class[c] = {"n": int(m.sum()), "recall": float(pred[m].mean())}
        else:
            per_class[c] = {"n": int(m.sum()),
                            "rejection": float((pred[m] == 0).mean())}
    return {"threshold": round(float(threshold), 4),
            "scene_accuracy": round(acc, 4),
            "oil_recall": round(per_class.get("Oil", {}).get("recall", 0.0), 4),
            "lookalike_rejection": round(per_class.get("Lookalike", {}).get("rejection", 0.0), 4),
            "cleanocean_rejection": round(per_class.get("No oil", {}).get("rejection", 0.0), 4),
            "tp": int(tp), "fp": int(fp), "fn": int(fn), "tn": int(tn),
            "per_class": per_class}


def pick_threshold(y_val, p_val, min_recall):
    """Highest-F1 point on the validation PR curve, subject to a recall floor.

    The floor encodes the stated preference for recall: we would rather send a
    marginal scene to Layer 2, which can still reject it, than never look at it.
    """
    prec, rec, thr = precision_recall_curve(y_val, p_val)
    prec, rec = prec[:-1], rec[:-1]
    f1 = np.where(prec + rec > 0, 2 * prec * rec / np.maximum(prec + rec, 1e-12), 0.0)
    ok = rec >= min_recall
    if ok.any():
        i = int(np.argmax(np.where(ok, f1, -1)))
    else:
        i = int(np.argmax(f1))
        print(f"  [warn] no validation threshold reaches recall {min_recall}; "
              f"falling back to best F1")
    return float(thr[i])


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def train_one(name, kw, Xtr_all, ytr_all, tr_idx, va_idx, a):
    """Train one variant. Returns (model, best_val_loss, val_acc@0.5, n_params)."""
    torch.manual_seed(42)
    np.random.seed(42)
    model = SceneCNN(**kw).to(DEVICE)
    n_par = sum(p.numel() for p in model.parameters())

    pos_w = float((1 - ytr_all[tr_idx]).sum() / max(ytr_all[tr_idx].sum(), 1))
    crit = nn.BCEWithLogitsLoss(pos_weight=torch.tensor(pos_w, device=DEVICE))
    opt = torch.optim.Adam(model.parameters(), lr=a.lr)
    sched = torch.optim.lr_scheduler.ReduceLROnPlateau(opt, factor=0.5, patience=3)

    print("\n  --- %s  (%s params, pool=%s) ---" % (name, format(n_par, ","), kw["pool"]))
    best_loss, best_state, bad = np.inf, None, 0
    t0 = time.time()
    for ep in range(1, a.epochs + 1):
        model.train()
        tl = n = 0
        for xb, yb in batches(Xtr_all, ytr_all, tr_idx, a.batch_size, True, True):
            opt.zero_grad()
            loss = crit(model(xb), yb)
            loss.backward()
            opt.step()
            tl += float(loss) * len(yb)
            n += len(yb)

        model.eval()
        vl = vn = 0
        with torch.no_grad():
            for xb, yb in batches(Xtr_all, ytr_all, va_idx, a.batch_size, False, False):
                vl += float(crit(model(xb), yb)) * len(yb)
                vn += len(yb)
        val_loss = vl / max(vn, 1)
        sched.step(val_loss)

        p_va = predict(model, Xtr_all[va_idx], ytr_all[va_idx])
        va_acc = float(((p_va >= 0.5).astype(int) == ytr_all[va_idx].astype(int)).mean())
        flag = ""
        if val_loss < best_loss - 1e-4:
            best_loss, bad = val_loss, 0
            best_state = {k: v.detach().cpu().clone() for k, v in model.state_dict().items()}
            flag = "  *best"
        else:
            bad += 1
        if ep % 2 == 0 or flag:
            print("    ep %3d  train %.4f  val %.4f  val_acc@0.5 %.3f%s"
                  % (ep, tl / max(n, 1), val_loss, va_acc, flag), flush=True)
        if bad >= a.patience:
            print("    early stop at ep %d" % ep)
            break

    if best_state:
        model.load_state_dict(best_state)
    p_va = predict(model, Xtr_all[va_idx], ytr_all[va_idx])
    va_acc = float(((p_va >= 0.5).astype(int) == ytr_all[va_idx].astype(int)).mean())
    print("    done in %.1f min  best val loss %.4f  val_acc %.3f"
          % ((time.time() - t0) / 60, best_loss, va_acc))
    return model, float(best_loss), va_acc, n_par


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--epochs", type=int, default=40)
    ap.add_argument("--no-domain-aug", action="store_true",
                    help="geometric augmentation only — the pre-12-Sept baseline")
    ap.add_argument("--batch-size", type=int, default=32)
    ap.add_argument("--lr", type=float, default=1e-3)
    ap.add_argument("--patience", type=int, default=8)
    ap.add_argument("--min-recall", type=float, default=0.90,
                    help="validation recall floor when picking the threshold")
    ap.add_argument("--variants", default="all",
                    help="comma-separated subset of VARIANTS, or 'all'")
    a = ap.parse_args()

    global DOMAIN_AUG
    DOMAIN_AUG = not a.no_domain_aug
    print(f"  domain augmentation: {'ON' if DOMAIN_AUG else 'OFF (geometric only)'}")
    os.makedirs(MODELS, exist_ok=True)
    torch.manual_seed(42)
    np.random.seed(42)

    print("=" * 72)
    print("  LAYER 1 - scene classifier   device=%s" % DEVICE)
    print("=" * 72)
    Xtr_all, ytr_all, ids_tr, cls_tr = load_split("P12")
    Xte, yte, ids_te, cls_te = load_split("P3")

    if set(ids_tr) & set(ids_te):
        raise SystemExit("[FAIL] scene ids overlap between P12 and P3")

    idx = np.arange(len(ytr_all))
    tr_idx, va_idx = train_test_split(idx, test_size=0.15, stratify=ytr_all,
                                      random_state=42)
    print("  fit %d scenes / val %d scenes (val oil %d)"
          % (len(tr_idx), len(va_idx), int(ytr_all[va_idx].sum())))

    want = list(VARIANTS) if a.variants == "all" else [v.strip() for v in a.variants.split(",")]
    trained = {}
    for name in want:
        if name not in VARIANTS:
            print("  [skip] unknown variant %r" % name)
            continue
        model, vloss, vacc, npar = train_one(name, VARIANTS[name], Xtr_all, ytr_all,
                                             tr_idx, va_idx, a)
        trained[name] = {"model": model, "val_loss": vloss, "val_acc": vacc, "params": npar}

    if not trained:
        raise SystemExit("no variant trained")

    print()
    print("=" * 72)
    print("  VARIANT COMPARISON - selected on validation, Part III never consulted")
    print("=" * 72)
    print("  %-14s%10s%11s%10s" % ("variant", "params", "val_loss", "val_acc"))
    for n, d in sorted(trained.items(), key=lambda kv: kv[1]["val_loss"]):
        print("  %-14s%10s%11.4f%10.3f"
              % (n, format(d["params"], ","), d["val_loss"], d["val_acc"]))
    best_name = min(trained, key=lambda n: trained[n]["val_loss"])
    model = trained[best_name]["model"]
    print("\n  Selected: %s" % best_name)

    p_va = predict(model, Xtr_all[va_idx], ytr_all[va_idx])
    thr = pick_threshold(ytr_all[va_idx], p_va, a.min_recall)
    va_rep = report(p_va, ytr_all[va_idx], [cls_tr[i] for i in va_idx], thr)
    print("  validation threshold = %.4f (recall floor %.2f) -> val acc %.3f"
          % (thr, a.min_recall, va_rep["scene_accuracy"]))

    p_te = predict(model, Xte, yte)
    rep = report(p_te, yte, cls_te, thr)

    print()
    print("=" * 72)
    print("  PART III HOLDOUT - 450 scenes the model has never seen")
    print("=" * 72)
    print("  Scene classification accuracy : %.3f   <- headline" % rep["scene_accuracy"])
    print("  Recall on the 150 oil scenes  : %.3f" % rep["oil_recall"])
    print("  Look-alike rejection (of 150) : %.3f" % rep["lookalike_rejection"])
    print("  Clean-ocean rejection (of 150): %.3f" % rep["cleanocean_rejection"])
    print()
    print("  Confusion matrix (rows=actual, cols=predicted):")
    print("              pred=no-oil   pred=oil")
    print("    no-oil   %10d  %10d" % (rep["tn"], rep["fp"]))
    print("    oil      %10d  %10d" % (rep["fn"], rep["tp"]))
    print()
    n_look = sum(1 for c in cls_te if c == "Lookalike")
    n_clean = sum(1 for c in cls_te if c == "No oil")
    look_fp = int(round((1 - rep["lookalike_rejection"]) * n_look))
    clean_fp = int(round((1 - rep["cleanocean_rejection"]) * n_clean))
    print("  False positives split by cause - this is the interesting error:")
    print("    look-alike called oil : %d of %d   (the hard ones)" % (look_fp, n_look))
    print("    clean ocean called oil: %d of %d" % (clean_fp, n_clean))

    all_rep = {}
    for n, d in trained.items():
        pt = predict(d["model"], Xte, yte)
        all_rep[n] = report(pt, yte, cls_te, thr)
    print()
    print("  All variants on Part III (reported for honesty; selection was on validation):")
    print("  %-14s%8s%9s%9s%10s" % ("variant", "acc", "oil_rec", "lookRej", "cleanRej"))
    for n, r in all_rep.items():
        mark = "  <- shipped" if n == best_name else ""
        print("  %-14s%8.3f%9.3f%9.3f%10.3f%s"
              % (n, r["scene_accuracy"], r["oil_recall"],
                 r["lookalike_rejection"], r["cleanocean_rejection"], mark))

    kw = VARIANTS[best_name]
    torch.save({"state_dict": model.state_dict(), "arch": "SceneCNN",
                "in_ch": 2, "filters": kw["filters"], "pool": kw["pool"],
                "variant": best_name}, CKPT)
    with open(META, "w") as fh:
        json.dump({"variant": best_name, "config": kw,
                   "threshold": thr, "min_recall_floor": a.min_recall,
                   "threshold_selected_on": "validation split of Parts I+II, PR curve",
                   "variant_selected_on": "validation loss",
                   "trained_on": "Zenodo Parts I+II", "tested_on": "Zenodo Part III",
                   "n_parameters": trained[best_name]["params"],
                   "validation": va_rep, "part3": rep,
                   "all_variants_part3": all_rep}, fh, indent=2)
    print("\n  saved %s\n  saved %s" % (CKPT, META))
    print("\n  Quote as: scene classification accuracy on the Zenodo Part III holdout,")
    print("  scene-level split, threshold and architecture both chosen on validation.")


if __name__ == "__main__":
    main()
