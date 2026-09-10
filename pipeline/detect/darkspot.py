"""
darkspot_v2.py — Phase 2 dark-spot finder, version 2. Owner: Soum.

Drop-in replacement for darkspot.py. Same public entry points
(`load_scene`, `detect`) and the same region-dict shape, so features.py /
make_labels.py keep working. Adds `detect_array` for arrays that don't come
from a Zenodo TIF (e.g. the GEE float GeoTIFF for Ennore).

WHY v1 FAILED (proved on synthetic data — see test_synthetic.py):
  v1 thresholded each pixel at  local_mean - k * local_std  using an annulus.
  The annulus protects a *compact* blob from contaminating its own stats, but a
  slick is a LINE: it leaves the guard box and runs straight through the
  annulus. Every pixel on a streak therefore has 20-40% slick in its own
  background sample, which (a) drags the local mean down and (b) inflates the
  local std (two populations mixed). The threshold moves *away* from the
  slick exactly on the slick. A -4 dB streak on a 1 dB sea becomes invisible.
  The std term is the culprit — it is self-defeating for extended targets.

WHAT v2 DOES (this is what SNAP's own Oil-Spill-Detection operator and the
Solberg / Brekke dark-spot literature do, plus two robustness upgrades):
  1. Land + nodata + bright-target masking BEFORE any statistics.
  2. Light speckle smoothing (5x5 median).
  3. "Depth" map = how far below the local surrounding sea each pixel sits, in
     dB. Estimated with a grey-level CLOSING (black top-hat) at several
     scales. A closing is robust to the feature itself (it only looks at the
     surrounding max), it does not ring at step edges (sub-swath seams pass
     through untouched), and thin lines get their full depth.
  4. Thresholds are in dB, RELATIVE TO THE SCENE'S OWN NOISE (median + MAD of
     the depth map over open sea) — never a fixed absolute dB, because Zenodo
     sits at ~-29 dB and GEE S1_GRD sits at ~-20 dB.
  5. Hysteresis: a region must contain a strong core (t_high) but is grown
     out to the weaker t_low, which keeps a whole slick as ONE region without
     letting noise in.
  6. Morphological close + connected components + area filter.

No opening step: opening erodes thin streaks to nothing. Hysteresis + the
area filter do the denoising job without eroding anything.
"""
from __future__ import annotations

import numpy as np
import cv2
from scipy import ndimage as ndi

try:
    import rasterio
except ImportError:  # detect_array still works without rasterio
    rasterio = None


# ---------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------

def load_scene(path, band=1):
    """Read one band of a Zenodo scene as float32 dB (raw, unmasked) plus
    pixel area in km^2 from the geotransform. Band 1 = VV, band 2 = VH.
    Masking is done in `prepare()` so the same code path serves GEE exports."""
    with rasterio.open(path) as src:
        arr = src.read(band).astype(np.float32)
        px_w, px_h = abs(src.transform.a), abs(src.transform.e)
    if px_w < 1.0:  # degrees, not metres
        px_w *= 111_320.0
        px_h *= 111_320.0
    if px_w == 0 or px_h == 0:  # no geotransform at all — assume 10 m
        px_w = px_h = 10.0
    return arr, float(px_w * px_h / 1e6)


# ---------------------------------------------------------------------------
# Masks
# ---------------------------------------------------------------------------

def prepare(db, pixel_area_km2, bright_ceiling_db=-10.0, bright_dilate_px=5,
            land_delta_db=7.0, land_window_px=51, land_dilate_px=40,
            min_land_km2=0.5, nodata_value=0.0, external_land=None):
    """Split a raw dB array into (filled_image, valid_mask, land_mask, sea_ref).

    external_land — optional bool array from a real coastline (see
    land_mask_geo.py). If given it is OR-ed with the brightness-inferred mask,
    so a demo scene gets the real coast AND still drops bright rigs/islands.

    valid   — pixels we are allowed to detect on: finite, not nodata, not a
              bright point target (+ small halo), not (dilated) land.
    land    — dilated land mask (also excludes the coastal sidelobe zone).
    sea_ref — a robust "typical open-sea level" in dB for this scene.
    filled  — image with every invalid pixel replaced by sea_ref so the
              morphology never sees NaN or land. Filling with the sea level
              cannot create false dark pixels in real sea (closing is a max
              operation) — it only ever hides things inside the invalid zone,
              which we exclude anyway.
    """
    finite = np.isfinite(db) & (db != nodata_value)

    # --- sea reference from LOCAL means (robust to a scene that is 1/3 land)
    tmp = np.where(finite, db, np.nan)
    glob = float(np.nanmedian(tmp))
    loc = ndi.uniform_filter(np.where(finite, db, glob), size=land_window_px)
    sea_ref = float(np.percentile(loc[finite], 20)) if finite.any() else glob

    # --- bright point targets (ships, rigs): mask + small halo
    bright = finite & (db > bright_ceiling_db)
    if bright_dilate_px > 0:
        bright = ndi.binary_dilation(bright, iterations=bright_dilate_px)

    # --- land: anything whose LOCAL mean is well above the sea, or nodata.
    #     Then fill holes, drop tiny blobs (ships are handled above), dilate.
    land = (loc > sea_ref + land_delta_db) | ~finite
    land = ndi.binary_closing(land, iterations=5, border_value=0)
    land = ndi.binary_fill_holes(land)
    lbl, n = ndi.label(land)
    if n:
        sizes = ndi.sum(land, lbl, index=np.arange(1, n + 1)) * pixel_area_km2
        keep = np.zeros(n + 1, bool)
        keep[1:] = sizes >= min_land_km2
        land = keep[lbl]
    if land_dilate_px > 0 and land.any():
        land = ndi.binary_dilation(land, iterations=land_dilate_px)
    if external_land is not None:
        land = land | external_land.astype(bool)

    valid = finite & ~bright & ~land
    filled = np.where(finite & ~bright, db, sea_ref).astype(np.float32)
    filled = np.where(land, sea_ref, filled).astype(np.float32)
    return filled, valid, land, sea_ref


# ---------------------------------------------------------------------------
# Depth map
# ---------------------------------------------------------------------------

def _closing(img, size):
    k = cv2.getStructuringElement(cv2.MORPH_RECT, (size, size))
    return cv2.morphologyEx(img, cv2.MORPH_CLOSE, k)


def depth_map(img, scales=(41, 121, 361), smooth_px=3, bg_sigma=3.0, downsample_above=121):
    """dB below the surrounding sea, per pixel.

    depth = closing(BG) - IMG   where
      IMG = lightly smoothed image (small median, keeps 2-3 px streaks alive)
      BG  = strongly smoothed image (gaussian) used ONLY to estimate the
            surrounding-sea level. A closing is a max-filter followed by a
            min-filter; run on noisy pixels it is biased upward by ~2.5 sigma
            (it picks the noise maxima). Smoothing the background copy first
            shrinks that bias to ~nothing, while the closing itself stays
            robust to the feature (a slick narrower than the structuring
            element cannot raise the surrounding max, and a step edge passes
            through a closing unchanged — no ringing at sub-swath seams).
    Max over scales; big scales run on a 4x block-averaged copy for speed."""
    if smooth_px and smooth_px > 1:
        img = cv2.medianBlur(img, smooth_px)  # float32 ok for ksize 3/5
    bg_src = cv2.GaussianBlur(img, (0, 0), bg_sigma) if bg_sigma else img
    depth = np.zeros_like(img)
    h, w = img.shape
    for s in scales:
        if s > downsample_above:
            f = 4
            small = cv2.resize(bg_src, (w // f, h // f), interpolation=cv2.INTER_AREA)
            bg = cv2.resize(_closing(small, max(3, (s // f) | 1)), (w, h), interpolation=cv2.INTER_LINEAR)
        else:
            bg = _closing(bg_src, s | 1)
        np.maximum(depth, bg - img, out=depth)
    return depth


def noise_floor(depth, valid):
    """Median and robust std (1.4826*MAD) of the depth map over valid sea."""
    v = depth[valid]
    if v.size == 0:
        return 0.0, 1.0
    med = float(np.median(v))
    mad = float(np.median(np.abs(v - med))) * 1.4826
    return med, max(mad, 1e-3)


# ---------------------------------------------------------------------------
# Thresholding + regions
# ---------------------------------------------------------------------------

def hysteresis(depth, low, high, valid):
    strong = (depth >= high) & valid
    weak = (depth >= low) & valid
    lbl, n = ndi.label(weak, structure=np.ones((3, 3)))
    if n == 0:
        return np.zeros_like(weak)
    hit = np.zeros(n + 1, bool)
    hit[np.unique(lbl[strong])] = True
    hit[0] = False
    return hit[lbl]


def clean_mask(mask, close_size=7):
    m = mask.astype(np.uint8)
    k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (close_size, close_size))
    return cv2.morphologyEx(m, cv2.MORPH_CLOSE, k).astype(bool)


def extract_regions(mask, pixel_area_km2, depth=None, db=None, valid=None,
                    min_km2=0.05, max_km2=500.0, min_extent_px=80):
    """Connected components, size-filtered. A region survives if its area is
    >= min_km2 OR its bounding box is >= min_extent_px on its longer side —
    the second rule exists because a 2-px-wide, 1-km-long discharge streak
    is only ~200 px of area and would otherwise be thrown away as noise.
    Same dict shape as v1 plus depth/contrast stats for features.py."""
    num, labels, stats, _ = cv2.connectedComponentsWithStats(mask.astype(np.uint8), connectivity=8)
    regions = []
    for i in range(1, num):
        area_px = int(stats[i, cv2.CC_STAT_AREA])
        area_km2 = area_px * pixel_area_km2
        extent = max(stats[i, cv2.CC_STAT_WIDTH], stats[i, cv2.CC_STAT_HEIGHT])
        if area_km2 > max_km2 or (area_km2 < min_km2 and extent < min_extent_px):
            continue
        rm = labels == i
        contours, _ = cv2.findContours(rm.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            continue
        contour = max(contours, key=cv2.contourArea).squeeze(axis=1)
        if contour.ndim != 2 or contour.shape[0] < 5:
            continue
        r = {"mask": rm, "contour": contour, "area_km2": float(area_km2), "area_px": area_px,
             "bbox": [int(stats[i, cv2.CC_STAT_LEFT]), int(stats[i, cv2.CC_STAT_TOP]),
                      int(stats[i, cv2.CC_STAT_WIDTH]), int(stats[i, cv2.CC_STAT_HEIGHT])]}
        if depth is not None:
            r["mean_depth_db"] = float(depth[rm].mean())
            r["max_depth_db"] = float(depth[rm].max())
        if db is not None and valid is not None:
            ring = ndi.binary_dilation(rm, iterations=25) & ~ndi.binary_dilation(rm, iterations=5) & valid
            inside = db[rm & np.isfinite(db)]
            if inside.size and ring.any():
                r["contrast_db"] = float(np.median(inside) - np.median(db[ring]))
        regions.append(r)
    return regions


# ---------------------------------------------------------------------------
# End-to-end
# ---------------------------------------------------------------------------

def detect_array(db, pixel_area_km2, scales=(41, 121, 361), smooth_px=3, bg_sigma=3.0,
                 t_high_db=2.0, t_low_db=1.0, k_high=3.0, k_low=1.5,
                 close_size=11, min_km2=0.05, max_km2=500.0, min_extent_px=80,
                 return_debug=False,
                 **prepare_kw):
    """Raw dB array -> list of region dicts. Thresholds:
        high = noise_median + max(t_high_db, k_high * noise_mad)
        low  = noise_median + max(t_low_db,  k_low  * noise_mad)
    i.e. 'at least this many dB below the sea, AND clearly above this scene's
    own noise'. Tune t_high_db first (1.5-3.0); leave the k's alone."""
    filled, valid, land, sea_ref = prepare(db, pixel_area_km2, **prepare_kw)
    depth = depth_map(filled, scales=scales, smooth_px=smooth_px, bg_sigma=bg_sigma)
    med, mad = noise_floor(depth, valid)
    high = med + max(t_high_db, k_high * mad)
    low = med + max(t_low_db, k_low * mad)
    mask = hysteresis(depth, low, high, valid)
    mask = clean_mask(mask, close_size=close_size) & valid
    regions = extract_regions(mask, pixel_area_km2, depth=depth, db=db, valid=valid,
                              min_km2=min_km2, max_km2=max_km2, min_extent_px=min_extent_px)
    info = {"sea_ref_db": sea_ref, "noise_median": med, "noise_mad": mad,
            "t_high": high, "t_low": low, "land_frac": float(land.mean()),
            "valid_frac": float(valid.mean())}
    if return_debug:
        return regions, {"depth": depth, "valid": valid, "land": land, "mask": mask, **info}
    return regions, info


def detect(path, band=1, **kw):
    """Scene path -> (regions, db). Same signature as v1 so callers don't change."""
    db, pixel_area_km2 = load_scene(path, band=band)
    regions, _ = detect_array(db, pixel_area_km2, **kw)
    return regions, db


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    ap = argparse.ArgumentParser(description="Dark-spot detector v2: run on one scene, plot outlines.")
    ap.add_argument("tif_path")
    ap.add_argument("--band", type=int, default=1, help="1=VV (use this), 2=VH")
    ap.add_argument("--t-high", type=float, default=2.0, help="min core depth, dB (main knob)")
    ap.add_argument("--t-low", type=float, default=1.0, help="min grow-out depth, dB")
    ap.add_argument("--scales", type=int, nargs="+", default=[41, 121, 361])
    ap.add_argument("--min-km2", type=float, default=0.05)
    ap.add_argument("--max-km2", type=float, default=500.0)
    ap.add_argument("--k-high", type=float, default=3.0, help="core must be this many noise-MADs deep")
    ap.add_argument("--k-low", type=float, default=1.5)
    ap.add_argument("--mask", help="optional GT mask tif to overlay in green")
    ap.add_argument("--out", default="darkspot_v2_preview.png")
    a = ap.parse_args()

    db, px = load_scene(a.tif_path, band=a.band)
    regions, dbg = detect_array(db, px, scales=tuple(a.scales), t_high_db=a.t_high, t_low_db=a.t_low, k_high=a.k_high, k_low=a.k_low,
                                min_km2=a.min_km2, max_km2=a.max_km2, return_debug=True)
    print(f"sea_ref={dbg['sea_ref_db']:.2f} dB  noise med/mad={dbg['noise_median']:.2f}/{dbg['noise_mad']:.2f}  "
          f"thresholds high/low={dbg['t_high']:.2f}/{dbg['t_low']:.2f} dB  land={dbg['land_frac']:.1%}")
    print(f"{len(regions)} region(s)")
    for r in regions:
        print(f"  area_km2={r['area_km2']:.3f}  mean_depth={r.get('mean_depth_db', 0):.2f} dB  "
              f"contrast={r.get('contrast_db', float('nan')):.2f} dB  bbox={r['bbox']}")

    fig, axes = plt.subplots(1, 2, figsize=(16, 8))
    v = db[np.isfinite(db) & (db != 0)]
    lo, hi = np.percentile(v, 2), np.percentile(v, 98)
    axes[0].imshow(db, cmap="gray", vmin=lo, vmax=hi)
    axes[0].imshow(np.ma.masked_where(~dbg["land"], dbg["land"]), cmap="autumn", alpha=0.25)
    for r in regions:
        c = r["contour"]
        axes[0].plot(np.append(c[:, 0], c[0, 0]), np.append(c[:, 1], c[0, 1]), "r-", lw=1.2)
    if a.mask:
        with rasterio.open(a.mask) as m:
            gt = m.read(1) > 0
        axes[0].contour(gt, levels=[0.5], colors="lime", linewidths=0.8)
    axes[0].set_title(f"{a.tif_path}  regions={len(regions)}  (red=detected, green=GT, orange=land)")
    axes[1].imshow(dbg["depth"], cmap="magma", vmin=0, vmax=max(4, dbg["t_high"] * 2))
    axes[1].set_title("depth map (dB below surrounding sea)")
    for ax in axes:
        ax.axis("off")
    fig.tight_layout()
    fig.savefig(a.out, dpi=120)
    print(f"wrote {a.out}")
