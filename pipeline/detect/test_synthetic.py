"""
test_synthetic.py — proves the v1 failure mode and checks v2, on a synthetic
scene built with the SAME statistics Soum measured on Zenodo Part III:
sea mean -29.3 dB, sea std 0.9 dB, oil contrast -4.25 dB (scene 00081),
plus every nuisance that appears in the real scenes.

Run:  python test_synthetic.py
Expect: v1 recall on the thin streak ~0%, v2 recall > 80%, and v2 producing
no regions on the land block, the seam, or the ship halo.
"""
import os
import numpy as np
from scipy import ndimage as ndi
import cv2

from darkspot import detect_array

rng = np.random.default_rng(0)
H = W = 2048
PIX_KM2 = 1e-4  # 10 m pixels

# ---- sea with realistic std + a smooth low-wind band + a diagonal step seam
sea = rng.normal(-29.3, 0.9, (H, W)).astype(np.float32)
yy, xx = np.mgrid[0:H, 0:W]
sea += (-1.5 * np.exp(-((xx - 0.55 * W + 0.3 * yy) ** 2) / (2 * 180 ** 2))).astype(np.float32)  # curved wind band
sea += np.where(xx + 0.4 * yy > 1500, 2.0, 0.0).astype(np.float32)                              # sub-swath seam (+2 dB step)

gt = np.zeros((H, W), bool)

# ---- thin wiggly streak, 6 px wide, -4.25 dB (the 00081 case)
t = np.linspace(0, 1, 4000)
sx = (300 + 1500 * t).astype(int)
sy = (600 + 250 * np.sin(6 * t) + 120 * t).astype(int)
streak = np.zeros((H, W), bool)
streak[sy, sx] = True
streak = ndi.binary_dilation(streak, iterations=3)
gt |= streak

# ---- compact blob, r=120, -3 dB
blob = (xx - 1500) ** 2 + (yy - 1500) ** 2 < 120 ** 2
gt |= blob

# ---- wide weak slick, ~700 px across, -2 dB  (the "30 % of frame" case)
wide = ((xx - 500) / 350.0) ** 2 + ((yy - 1600) / 260.0) ** 2 < 1
gt |= wide

img = sea.copy()
img[streak] -= 4.25
img[blob] -= 3.0
img[wide] -= 2.0

# ---- land block (bright, textured), a zero-fill corner, a ship
land = (yy < 450) & (xx < 700)
img[land] = rng.normal(-9.0, 4.0, land.sum()).astype(np.float32)
img[:150, :150] = 0.0
img[1000:1004, 1000:1004] = 4.0


# ---------------------------------------------------------------- v1 (verbatim)
def v1_adaptive_dark_mask(db, k=1.5, guard=25, window=71):
    valid = np.isfinite(db)
    filled = np.where(valid, db, np.nanmean(db))
    box = lambda a, s: ndi.uniform_filter(a, size=s) * (s * s)
    outer_sum, inner_sum = box(filled, window), box(filled, guard)
    outer_sq, inner_sq = box(filled * filled, window), box(filled * filled, guard)
    n_bg = window * window - guard * guard
    bg_mean = (outer_sum - inner_sum) / n_bg
    bg_var = np.maximum((outer_sq - inner_sq) / n_bg - bg_mean * bg_mean, 0.0)
    dark = filled < (bg_mean - k * np.sqrt(bg_var))
    return dark & valid, bg_mean, np.sqrt(bg_var)


def v1_clean(mask, open_size=3, close_size=15):
    m = mask.astype(np.uint8)
    m = cv2.morphologyEx(m, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (open_size, open_size)))
    m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (close_size, close_size)))
    return m.astype(bool)


db_v1 = np.where(np.isfinite(img) & (img != 0) & (img < -10), img, np.nan).astype(np.float32)
dark, bg_mean, bg_std = v1_adaptive_dark_mask(db_v1)
v1_mask = v1_clean(dark)


def recall(mask, part):
    return mask[part].mean()


print("=== v1 (k*std annulus CFAR) ===")
print(f"  streak recall : {recall(v1_mask, streak):.1%}")
print(f"  blob recall   : {recall(v1_mask, blob):.1%}")
print(f"  wide recall   : {recall(v1_mask, wide):.1%}")
print(f"  local std ON the streak vs open sea: {np.nanmedian(bg_std[streak]):.2f} vs {np.nanmedian(bg_std[~gt & ~land]):.2f} dB")
print(f"  local mean ON the streak vs open sea: {np.nanmedian(bg_mean[streak]):.2f} vs {np.nanmedian(bg_mean[~gt & ~land]):.2f} dB")
print("  -> the streak inflates its OWN threshold: mean drops and std doubles right on the line.")

# ---------------------------------------------------------------- v2
regions, dbg = detect_array(img, PIX_KM2, return_debug=True)
v2_mask = dbg["mask"]
print("\n=== v2 (morphological depth + hysteresis) ===")
print(f"  thresholds high/low = {dbg['t_high']:.2f}/{dbg['t_low']:.2f} dB, noise med/mad = "
      f"{dbg['noise_median']:.2f}/{dbg['noise_mad']:.2f}, land masked = {dbg['land_frac']:.1%}")
print(f"  streak recall : {recall(v2_mask, streak):.1%}")
print(f"  blob recall   : {recall(v2_mask, blob):.1%}")
print(f"  wide recall   : {recall(v2_mask, wide):.1%}")
fp = v2_mask & ~ndi.binary_dilation(gt, iterations=10)
print(f"  false-positive pixels outside GT: {fp.sum()} ({fp.mean():.3%} of frame)")
print(f"  regions: {len(regions)}")
for r in regions:
    hit = (r['mask'] & gt).sum() / r['area_px']
    print(f"    area={r['area_km2']:.2f} km2  depth={r['mean_depth_db']:.2f} dB  contrast={r.get('contrast_db', float('nan')):.2f} dB  GT-overlap={hit:.0%}")

# ---------------------------------------------------------------- picture
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
fig, ax = plt.subplots(1, 3, figsize=(21, 7))
lo, hi = np.percentile(img[np.isfinite(img) & (img != 0)], (2, 98))
for a, m, title in [(ax[0], gt, "ground truth"), (ax[1], v1_mask, "v1 detections"), (ax[2], v2_mask, "v2 detections")]:
    a.imshow(img, cmap="gray", vmin=lo, vmax=hi)
    a.contour(m, levels=[0.5], colors="lime" if title == "ground truth" else "red", linewidths=0.8)
    a.set_title(title)
    a.axis("off")
fig.tight_layout()
# Diagnostic picture, regenerable in seconds -> out/ (scratch, gitignored), not
# results/ (committed evidence). Script-relative so it lands in the same place
# wherever this is run from.
_OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "out")
os.makedirs(_OUT, exist_ok=True)
_png = os.path.join(_OUT, "synthetic_v1_vs_v2.png")
fig.savefig(_png, dpi=90)
print(f"\nwrote {_png}")
