"""
nets.py  -  Layer 1 + Layer 2 inference.  Owner: Soumirya.

Shared by run.py (real scenes) and evaluate.py (Part III numbers) so the two can
never drift apart — the number we report and the number we ship must come from
exactly the same code path.

    normalise_scene()   per-scene MAD normalisation, identical to build_cache.py
    load_classifier()   Layer 1
    load_unet()         Layer 2
    classify_scene()    "is there oil here at all?"  -> probability
    segment_scene()     tiled U-Net inference -> per-pixel probability map

TILED INFERENCE AT 50% OVERLAP (2.5, risk D5)
----------------------------------------------
Tiles are taken at stride = TILE/2 and the predictions are AVERAGED in the
overlap regions, weighted by a raised-cosine window so a tile contributes most
at its centre and tapers to nothing at its edge.

Without this you get visible seams at multiples of 128 px, and — the part that
actually costs us — a slick straddling a tile boundary splits into TWO
detections, which hands Stage 2 two wrong polygons to seed particles from. The
seam is cosmetic; the split origin is a wrong answer.
"""
from __future__ import annotations

import json
import os

import numpy as np
import torch

_HERE = os.path.dirname(os.path.abspath(__file__))
MODELS = os.path.join(_HERE, "models")

TILE = 256
CLIP_SIGMA = 6.0
EPS = 1e-6

DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")


# ---------------------------------------------------------------------------
# Normalisation — must stay byte-identical in meaning to build_cache.normalise
# ---------------------------------------------------------------------------

def normalise_band(band):
    """dB -> [-1, +1] by this band's own median and MAD. Invalid pixels -> 0."""
    valid = np.isfinite(band) & (band != 0.0)
    if not valid.any():
        return np.zeros_like(band, np.float32), valid, 0.0, 1.0
    v = band[valid]
    med = float(np.median(v))
    mad = float(np.median(np.abs(v - med)))
    norm = np.clip((band - med) / (1.4826 * mad + EPS), -CLIP_SIGMA, CLIP_SIGMA) / CLIP_SIGMA
    return np.where(valid, norm, 0.0).astype(np.float32), valid, med, mad


def normalise_scene(vv, vh=None):
    """-> (norm (H,W,2) float32, valid (H,W) bool, stats dict).

    stats carries med/mad per band so Layer 3 can invert back to real decibels;
    a contrast_db computed on normalised data would be a unitless number wearing
    a dB label, which is exactly the kind of quiet dishonesty the contract's
    'contrast_db must be negative' check cannot catch.
    """
    n_vv, val_vv, med_vv, mad_vv = normalise_band(vv)
    if vh is None:
        n_vh, val_vh, med_vh, mad_vh = n_vv.copy(), val_vv, med_vv, mad_vv
    else:
        n_vh, val_vh, med_vh, mad_vh = normalise_band(vh)
    return (np.stack([n_vv, n_vh], axis=-1), val_vv & val_vh,
            {"vv_med": med_vv, "vv_mad": mad_vv, "vh_med": med_vh, "vh_mad": mad_vh,
             "vh_available": vh is not None})


# ---------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------

def load_classifier(path=None):
    """-> (model, threshold) or (None, None) if Layer 1 has not been trained."""
    from pipeline.detect.train_classifier import SceneCNN
    path = path or os.path.join(MODELS, "scene_classifier.pt")
    meta_p = os.path.join(MODELS, "scene_classifier_meta.json")
    if not os.path.exists(path):
        return None, None
    ck = torch.load(path, map_location=DEVICE, weights_only=False)
    # pool MUST come from the checkpoint. Training selects between avg/max/both
    # on validation, and loading a max-pool model as avg-pool silently produces
    # a different network with the same weights — garbage, with no error.
    model = SceneCNN(in_ch=ck.get("in_ch", 2),
                     filters=ck.get("filters", 32),
                     pool=ck.get("pool", "avg")).to(DEVICE)
    model.load_state_dict(ck["state_dict"])
    model.eval()
    thr = 0.5
    if os.path.exists(meta_p):
        thr = float(json.loads(open(meta_p).read()).get("threshold", 0.5))
    return model, thr


def load_unet(path=None):
    """-> (model, threshold) or (None, None) if Layer 2 has not been trained."""
    from pipeline.detect.train_unet import UNet
    path = path or os.path.join(MODELS, "unet.pt")
    if not os.path.exists(path):
        return None, None
    ck = torch.load(path, map_location=DEVICE, weights_only=False)
    model = UNet(in_ch=ck.get("in_ch", 2), depth=ck.get("depth", 7)).to(DEVICE)
    model.load_state_dict(ck["state_dict"])
    model.eval()
    return model, float(ck.get("threshold", 0.5))


# ---------------------------------------------------------------------------
# Layer 1
# ---------------------------------------------------------------------------

@torch.no_grad()
def classify_scene(model, norm):
    """norm (H,W,2) -> P(scene contains oil). Downsampled exactly as the cache
    did it, because a resize mismatch is a silent accuracy loss."""
    import cv2
    small = cv2.resize(norm, (256, 256), interpolation=cv2.INTER_AREA)
    x = torch.from_numpy(small.astype(np.float32)).permute(2, 0, 1)[None].to(DEVICE)
    return float(torch.sigmoid(model(x)).item())


# ---------------------------------------------------------------------------
# Layer 2
# ---------------------------------------------------------------------------

def _cosine_window(size=TILE):
    """Raised-cosine taper, 2-D. Never exactly zero at the border, or edge
    pixels covered by only one tile would divide by ~0."""
    w = 0.5 - 0.5 * np.cos(2 * np.pi * (np.arange(size) + 0.5) / size)
    w = np.maximum(w, 1e-3)
    return np.outer(w, w).astype(np.float32)


@torch.no_grad()
def segment_scene(model, norm, valid=None, tile=TILE, overlap=0.5, batch=8,
                  amp=None):
    """-> per-pixel P(oil), same H,W as norm.

    Scenes smaller than one tile are zero-padded to a full tile and cropped back,
    so a 505x577 case export works without a special path.
    """
    if amp is None:
        amp = DEVICE.type == "cuda"
    h, w = norm.shape[:2]
    pad_h, pad_w = max(0, tile - h), max(0, tile - w)
    if pad_h or pad_w:
        norm = np.pad(norm, ((0, pad_h), (0, pad_w), (0, 0)))
    H, W = norm.shape[:2]

    stride = max(1, int(tile * (1.0 - overlap)))
    rows = list(range(0, max(H - tile, 0) + 1, stride))
    cols = list(range(0, max(W - tile, 0) + 1, stride))
    if rows[-1] != H - tile:
        rows.append(H - tile)
    if cols[-1] != W - tile:
        cols.append(W - tile)

    acc = np.zeros((H, W), np.float32)
    wsum = np.zeros((H, W), np.float32)
    win = _cosine_window(tile)

    coords = [(r, c) for r in rows for c in cols]
    for i in range(0, len(coords), batch):
        chunk = coords[i:i + batch]
        x = np.stack([norm[r:r + tile, c:c + tile, :] for r, c in chunk])
        xt = torch.from_numpy(x.astype(np.float32)).permute(0, 3, 1, 2).to(DEVICE)
        with torch.amp.autocast("cuda", enabled=amp):
            p = torch.sigmoid(model(xt)).float().cpu().numpy()
        for (r, c), pm in zip(chunk, p):
            acc[r:r + tile, c:c + tile] += pm * win
            wsum[r:r + tile, c:c + tile] += win

    prob = acc / np.maximum(wsum, 1e-6)
    prob = prob[:h, :w]
    if valid is not None:
        prob = np.where(valid, prob, 0.0)
    return prob.astype(np.float32)


# ---------------------------------------------------------------------------
# Mask -> regions
# ---------------------------------------------------------------------------

def mask_to_regions(prob, threshold, pixel_area_km2, db, db_vh=None, valid=None,
                    close_size=7, min_km2=0.02, max_km2=500.0, min_extent_px=60,
                    simplify=True):
    """U-Net probability map -> the same region dicts extract_regions() produces,
    so Layer 3 (features.py, ships.py) runs on U-Net output unchanged.

    Statistics are measured on the ORIGINAL dB array, never the normalised one —
    contrast_db has to be real decibels.
    """
    import cv2
    from scipy import ndimage as ndi
    from pipeline.detect.darkspot import extract_regions, depth_map, prepare

    binary = (prob >= threshold)
    if valid is not None:
        binary &= valid
    if not binary.any():
        return []

    k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (close_size, close_size))
    binary = cv2.morphologyEx(binary.astype(np.uint8), cv2.MORPH_CLOSE, k).astype(bool)

    filled, vmask, _, _ = prepare(db, pixel_area_km2)
    depth = depth_map(filled)
    depth_vh = None
    if db_vh is not None:
        filled_vh, _, _, _ = prepare(db_vh, pixel_area_km2)
        depth_vh = depth_map(filled_vh)

    return extract_regions(binary, pixel_area_km2, depth=depth, db=db,
                           valid=vmask if valid is None else (valid & vmask),
                           db_vh=db_vh, depth_vh=depth_vh,
                           min_km2=min_km2, max_km2=max_km2,
                           min_extent_px=min_extent_px)


if __name__ == "__main__":
    # Overlap-averaging sanity check: a constant-1 "model" must reconstruct
    # exactly 1.0 everywhere, including across every seam.
    class Ones(torch.nn.Module):
        def forward(self, x):
            return torch.full(x.shape[0:1] + x.shape[2:], 20.0, device=x.device)

    norm = np.zeros((600, 700, 2), np.float32)
    p = segment_scene(Ones(), norm, amp=False)
    print(f"  reconstructed min={p.min():.6f} max={p.max():.6f} "
          f"(sigmoid(20) ~ 1.0 everywhere, no seams)")
    assert p.min() > 0.999, "overlap averaging leaves seams"

    small = segment_scene(Ones(), np.zeros((120, 90, 2), np.float32), amp=False)
    print(f"  sub-tile scene shape {small.shape} (expect (120, 90))")
    assert small.shape == (120, 90)
    print("  [PASS] tiled inference reconstructs cleanly")
