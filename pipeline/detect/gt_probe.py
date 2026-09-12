"""
gt_probe.py — answer, for ONE Zenodo scene, the questions that decide whether
the detector *can* work before you tune anything:

  1. Are the masks aligned with the images?  (tries all 8 flips/rotations and
     reports the oil-vs-ring contrast for each — the true orientation is the
     one with by far the most negative contrast)
  2. How dark is the labelled oil, really?  (median inside GT minus median in
     a ring around it — per-pixel, so speckle is not averaged away)
  3. How THIN is it?  (area / skeleton length ≈ width in pixels)
  4. Does the v2 depth map see it?  (median depth inside GT vs this scene's
     thresholds)
  5. A FULL-RESOLUTION crop around the GT, because a 3-px-wide streak in a
     2048-px scene is invisible in any whole-scene plot — this is why the
     team "can't see it with the naked eye".

Usage:
  python gt_probe.py data/Images/Oil/00081.tif data/Mask/Oil/00081_segmentation.tif
"""
import sys
import numpy as np
import rasterio
from scipy import ndimage as ndi
from skimage.morphology import skeletonize
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from darkspot_v2 import load_scene, detect_array

img_path, mask_path = sys.argv[1], sys.argv[2]
db, px = load_scene(img_path)
with rasterio.open(mask_path) as m:
    gt_raw = m.read(1) > 0

finite = np.isfinite(db) & (db != 0)


def contrast(gt):
    if gt.sum() == 0:
        return float("nan")
    ring = ndi.binary_dilation(gt, iterations=30) & ~ndi.binary_dilation(gt, iterations=6) & finite
    return float(np.median(db[gt & finite]) - np.median(db[ring])) if ring.any() else float("nan")


orients = {
    "identity": gt_raw, "flip_ud": gt_raw[::-1], "flip_lr": gt_raw[:, ::-1],
    "rot180": gt_raw[::-1, ::-1], "transpose": gt_raw.T, "rot90": np.rot90(gt_raw),
    "rot270": np.rot90(gt_raw, 3), "transpose_anti": np.rot90(gt_raw, 2).T,
}
print(f"scene {img_path}: GT pixels = {gt_raw.sum()} ({gt_raw.mean():.2%} of frame), pixel area {px*1e6:.0f} m2")
print("\n1) mask orientation check — oil-vs-ring contrast under each transform (want ONE clearly negative):")
for k, g in orients.items():
    print(f"   {k:15s} {contrast(g):+6.2f} dB")
gt = gt_raw

# --- 2/3: how dark, how thin
c = contrast(gt)
skel = skeletonize(gt)
width_px = gt.sum() / max(skel.sum(), 1)
lbl, n = ndi.label(gt)
print(f"\n2) GT contrast (median in - median ring): {c:+.2f} dB")
print(f"3) GT pieces: {n}, mean width ≈ {width_px:.1f} px, total area {gt.sum()*px:.2f} km2")
in_vals = db[gt & finite]
print(f"   GT pixel values: p10/p50/p90 = {np.percentile(in_vals, 10):.1f}/{np.percentile(in_vals, 50):.1f}/{np.percentile(in_vals, 90):.1f} dB;"
      f"  sea p50 = {np.median(db[finite & ~ndi.binary_dilation(gt, iterations=6)]):.1f} dB")

# --- 4: does the depth map see it
regions, dbg = detect_array(db, px, return_debug=True)
depth = dbg["depth"]
print(f"\n4) v2 depth inside GT: p50 = {np.median(depth[gt]):.2f} dB, p90 = {np.percentile(depth[gt], 90):.2f} dB;"
      f"  scene thresholds high/low = {dbg['t_high']:.2f}/{dbg['t_low']:.2f} dB (noise med {dbg['noise_median']:.2f}, mad {dbg['noise_mad']:.2f})")
det = dbg["mask"]
recall = det[gt].mean()
hits = [r for r in regions if (r["mask"] & gt).sum() / r["area_px"] >= 0.3]
print(f"   v2 pixel recall on GT: {recall:.1%};  regions total {len(regions)}, regions overlapping GT>=30%: {len(hits)}")
print(f"   land masked: {dbg['land_frac']:.1%}   GT pixels lost to the land/valid mask: {(gt & ~dbg['valid']).mean()/max(gt.mean(),1e-9):.1%}")
if np.median(depth[gt]) < dbg["t_low"]:
    print("   -> the labelled oil is NOT deeper than this scene's noise floor. No threshold will find it cleanly;\n"
          "      either the label is weak/misaligned or this is a genuinely sub-noise slick. Do not tune on this scene.")
elif recall < 0.3:
    print("   -> depth sees it but the region logic drops it: lower --t-high/--k-high, or raise min_extent/close_size.")

# --- 5: full-res crop
ys, xs = np.where(gt)
pad = 96
y0, y1 = max(ys.min() - pad, 0), min(ys.max() + pad, db.shape[0])
x0, x1 = max(xs.min() - pad, 0), min(xs.max() + pad, db.shape[1])
crop = db[y0:y1, x0:x1]
v = crop[np.isfinite(crop) & (crop != 0)]
lo, hi = np.percentile(v, (1, 99))
fig, ax = plt.subplots(1, 3, figsize=(21, 7))
ax[0].imshow(crop, cmap="gray", vmin=lo, vmax=hi); ax[0].set_title("full-res crop (no overlay) — can YOU see it?")
ax[1].imshow(crop, cmap="gray", vmin=lo, vmax=hi)
ax[1].contour(gt[y0:y1, x0:x1], levels=[0.5], colors="lime", linewidths=0.7)
ax[1].contour(det[y0:y1, x0:x1], levels=[0.5], colors="red", linewidths=0.7); ax[1].set_title("green = GT, red = v2 detections")
ax[2].imshow(depth[y0:y1, x0:x1], cmap="magma", vmin=0, vmax=max(4, 2 * dbg["t_high"])); ax[2].set_title("v2 depth map (dB below sea)")
for a in ax:
    a.axis("off")
fig.tight_layout()
out = f"probe_{img_path.split('/')[-1].split(chr(92))[-1].replace('.tif', '')}.png"
fig.savefig(out, dpi=110)
print(f"\nwrote {out}  (crop rows {y0}:{y1}, cols {x0}:{x1})")
