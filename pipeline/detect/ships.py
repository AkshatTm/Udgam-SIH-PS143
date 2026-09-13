"""
ships.py  -  Radar ship detection.  Owner: Soum.   (docs/team/soum-stage1-detection.md 5.1)

The inverse of the dark-spot detector. Oil is DARK on SAR; a steel hull is a
corner reflector and is BRIGHT. darkspot.prepare() already finds those pixels
in order to throw them away — they otherwise produce a dark halo that the
detector reads as oil. This module keeps that half instead of discarding it.

Why it matters more than its line count suggests: Jaiveer cross-references every
radar ship against AIS. A ship radar can see but AIS cannot is a DARK VESSEL,
and next to a fresh slick that is the strongest single piece of evidence the
whole system produces — because it is independent of the drift model and does
not inherit its uncertainty.

Which is also why the threshold is deliberately high. A missed small vessel
costs us one line of evidence. A FALSE ship detection produces a false
dark-vessel claim about a real stretch of ocean, which is worse. An empty
list is a valid and common answer.

Output shape (Master section 6.3):
    {"lon": -118.10412, "lat": 33.60219, "px_area": 340, "peak_db": -4.2}
"""
from __future__ import annotations

import numpy as np
import cv2
from scipy import ndimage as ndi

# A ship sits far above the sea clutter. Both conditions must hold:
#   absolute  — brighter than this many dB (open ocean sits at -20 to -33)
#   relative  — and this many robust sigmas above the scene's own sea level,
#               so a scene with an unusually bright sea does not fill with
#               phantom vessels.
DEFAULT_MIN_DB = -10.0

# 4.0, not the 8.0 this started at. The threshold is max(absolute floor,
# median + k*MAD), so the two terms are an AND and whichever is stricter wins.
# At k=8 the scene-relative term always won and it won by an absurd margin: on
# the Gulf of Alaska scene (sea -18.30 dB, MAD 2.56) it demanded +2.19 dB, while
# the brightest pixel in the entire scene is -8.79 dB. The detector could not
# fire on that scene by construction, and the -10 dB floor was dead code
# everywhere. Requiring a return brighter than any ocean SAR pixel is not a
# definition of "ship", it is a bug.
#
# 4.0 is from CFAR practice: a Pfa around 1e-5..1e-6 on approximately Gaussian
# clutter sits near 4-5 sigma. It is chosen for that reason and applied to all
# seven live scenes at once. It is NOT chosen because it makes any particular
# case detect anything — the Alaska contact in section 6.6 is an answer we are
# not supposed to be optimising against (A6, D2b), and if this value still misses
# it then the miss gets reported with the diagnostics rather than tuned away.
DEFAULT_K_SIGMA = 4.0

# A Sentinel-1 IW GRD pixel is ~10 m. A 30 m tender is ~9 px; a 300 m ULCC with
# its sidelobes is a few thousand. Anything larger is an island or a rig glint.
MIN_PX = 4
MAX_PX = 4000

# A large vessel lights up as several bright fragments (bow, superstructure,
# stern). Merge detections whose centroids fall within this ground distance.
MERGE_M = 50.0


def _sea_level(db, finite):
    """Robust (median, 1.4826*MAD) of the scene's sea in dB."""
    v = db[finite]
    if v.size == 0:
        return 0.0, 1.0
    med = float(np.median(v))
    mad = float(np.median(np.abs(v - med))) * 1.4826
    return med, max(mad, 1e-3)


def detect_ships(db, transform, pixel_size_m=None,
                 min_db=DEFAULT_MIN_DB, k_sigma=DEFAULT_K_SIGMA,
                 min_px=MIN_PX, max_px=MAX_PX, merge_m=MERGE_M,
                 nodata_value=0.0, return_stats=False, exclude=None):
    """Bright point targets -> list of ship dicts in [lon, lat].

    db        : VV dB array (raw, unmasked — same array detect_array() takes)
    transform : an affine.Affine mapping (col, row) -> (lon, lat). Pass the
                rasterio dataset transform; pixel centres are (col+0.5, row+0.5).
    pixel_size_m : ground pixel size, for the merge radius. Estimated from the
                transform when omitted.
    return_stats : also return a diagnostics dict describing what was REJECTED
                and why.
    exclude   : optional bool mask of pixels that CANNOT hold a vessel — land,
                and the coastal sidelobe halo around it. Pass darkspot.prepare()'s
                land mask. Without it a port scene returns its own buildings as
                ships: the Ennore look-alike peaks at +34 dB on land and reported
                1,377 "vessels", which would have become 1,377 false dark-vessel
                claims in Jaiveer's cross-check. A ship detection on land is not
                a marginal call, it is definitionally wrong.

    On the diagnostics. The threshold is max(absolute floor, scene-relative), and
    the absolute floor is the part that can fail quietly at high latitude, where
    sea backscatter is lower and a small hull may peak below -10 dB. A 40 m vessel
    is already at the small end of what SAR resolves. If a vessel is missed we
    want that to be VISIBLE — a reported near-miss we can talk about — rather than
    an empty list that looks like a confident "no ships here".
    """
    stats_out = {"threshold_db": None, "sea_med_db": None, "sea_sigma_db": None,
                 "floor_binding": None, "n_components": 0,
                 "rejected_small": 0, "rejected_large": 0, "rejected_diffuse": 0,
                 "brightest_rejected_db": None, "n_merged": 0}

    def _ret(ships):
        return (ships, stats_out) if return_stats else ships

    finite = np.isfinite(db) & (db != nodata_value)
    if exclude is not None:
        finite &= ~np.asarray(exclude, dtype=bool)
    if not finite.any():
        return _ret([])

    med, sigma = _sea_level(db, finite)
    relative = med + k_sigma * sigma
    thresh = max(min_db, relative)
    stats_out.update(sea_med_db=round(med, 2), sea_sigma_db=round(sigma, 3),
                     threshold_db=round(thresh, 2),
                     # True means the fixed -10 dB floor, not the scene's own
                     # noise, is what a candidate had to clear. That is the
                     # regime where a faint small vessel goes missing.
                     floor_binding=bool(min_db > relative))
    bright = finite & (db > thresh)
    if not bright.any():
        return _ret([])

    # Close 3x3 so a hull broken by one dim pixel stays one component.
    bright = cv2.morphologyEx(bright.astype(np.uint8),
                              cv2.MORPH_CLOSE,
                              cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))).astype(bool)

    if pixel_size_m is None:
        # transform.a is degrees of longitude per pixel at this latitude.
        lat0 = float(transform.f)
        m_per_deg_lon = 111_320.0 * max(np.cos(np.radians(lat0)), 1e-6)
        pixel_size_m = float(abs(transform.a) * m_per_deg_lon)
        if pixel_size_m <= 0:
            pixel_size_m = 10.0

    num, labels, stats, centroids = cv2.connectedComponentsWithStats(
        bright.astype(np.uint8), connectivity=8)

    stats_out["n_components"] = num - 1
    raw = []
    brightest_rejected = None
    for i in range(1, num):
        px_area = int(stats[i, cv2.CC_STAT_AREA])
        w = int(stats[i, cv2.CC_STAT_WIDTH])
        h = int(stats[i, cv2.CC_STAT_HEIGHT])
        peak_db = float(db[labels == i].max())

        reason = None
        if px_area < min_px:
            reason = "rejected_small"
        elif px_area > max_px:
            reason = "rejected_large"
        elif px_area / max(w * h, 1) < 0.20:
            # Compactness: a vessel fills a decent share of its bounding box. A
            # long thin near-empty box is usually a sub-swath seam or a
            # coastline sliver that survived the land mask.
            reason = "rejected_diffuse"
        if reason:
            stats_out[reason] += 1
            if brightest_rejected is None or peak_db > brightest_rejected:
                brightest_rejected = peak_db
            continue

        raw.append({"col": float(centroids[i][0]), "row": float(centroids[i][1]),
                    "px_area": px_area, "peak_db": peak_db})

    if brightest_rejected is not None:
        stats_out["brightest_rejected_db"] = round(brightest_rejected, 2)
    ships = _merge_and_project(raw, transform, pixel_size_m, merge_m)
    stats_out["n_merged"] = len(raw) - len(ships)
    return _ret(ships)


def _merge_and_project(raw, transform, pixel_size_m, merge_m):
    """Merge near-coincident fragments, then convert (col,row) -> [lon,lat]."""
    merge_px = max(merge_m / max(pixel_size_m, 1e-6), 1.0)
    # Brightest first, so a merged cluster keeps the dominant return's position.
    raw.sort(key=lambda s: s["peak_db"], reverse=True)

    merged = []
    for s in raw:
        for m in merged:
            if np.hypot(s["col"] - m["col"], s["row"] - m["row"]) <= merge_px:
                m["px_area"] += s["px_area"]
                m["peak_db"] = max(m["peak_db"], s["peak_db"])
                break
        else:
            merged.append(dict(s))

    ships = []
    for m in merged:
        lon, lat = transform * (m["col"] + 0.5, m["row"] + 0.5)
        ships.append({"lon": round(float(lon), 5), "lat": round(float(lat), 5),
                      "px_area": int(m["px_area"]),
                      "peak_db": round(float(m["peak_db"]), 2)})
    ships.sort(key=lambda s: s["peak_db"], reverse=True)
    return ships


# ---------------------------------------------------------------------------
# Chronic vs acute  (docs/team/soum-stage1-detection.md 5.2)
# ---------------------------------------------------------------------------
#
# chronic — long, thin, roughly straight, often lane-aligned. A vessel washing
#           tanks or dumping bilge WHILE UNDERWAY. The origin is a LINE
#           SEGMENT, not a point, which is why Anushka needs this field: it
#           changes how particles are seeded.
# acute   — radial spread from a point. Collision, grounding, platform release.
#
# Deliberate discharge is a crime; an accident is a misfortune. The system that
# tells them apart is the one worth deploying.

CHRONIC_ELONGATION = 5.0
ACUTE_ELONGATION = 3.0
# 0.60, calibrated on data rather than on a synthetic ellipse.
#
# The original 0.80 was set from the smooth synthetic ellipse in this file's
# self-test, where straightness is ~1.0 by construction. Real contours are
# pixel-ragged, their perimeter runs long, and the ratio collapses — every one
# of the twelve oil detections across the seven live cases came back "unknown",
# including regions with elongation 19.0, 11.8 and 10.8, which are exactly the
# chronic-discharge shape the field exists to name.
#
# Measured on Part 1 ground-truth masks (2,769 slick components, 400 scenes):
# for elongation >= 5 straightness runs p10 0.654, median 0.819. 0.60 captures
# 94% of those. Chosen from Zenodo, never from a demo case.
#
# CAVEAT, measured and worth stating: detector contours score 0.15-0.20 LOWER
# than the hand-drawn masks this was calibrated on, because the detector follows
# a thresholded boundary. So 0.60 against detector output is roughly 0.75-0.80
# against a mask, and this threshold is more permissive than the number looks.
#
# It could NOT be calibrated on detector output directly: of 276 detector regions
# overlapping GT oil in Part 1, ZERO have elongation >= 5 (median 1.72, p90 2.66)
# — Part 1's slicks are broad and diffuse, so the detector fragments them into
# blobs and the corpus has no elongated population at all. The brief's
# "tune against Part 1's masks" (5.2) does not work for this split, and that is
# a finding rather than an omission.
STRAIGHTNESS_MIN = 0.60


def _straightness(contour):
    """How close the region's skeleton is to a straight line, in [0, 1].

    Measured as (extent along the principal axis) / (arc length of the medial
    path), approximated by comparing the PCA-major spread against the perimeter.
    A straight streak scores near 1; a meandering or branching slick scores low.
    Returns 1.0 when the contour is too small to judge (elongation then decides).
    """
    pts = contour.astype(np.float64)
    if pts.shape[0] < 5:
        return 1.0
    c = pts - pts.mean(axis=0)
    try:
        _, _, vt = np.linalg.svd(c, full_matrices=False)
    except np.linalg.LinAlgError:
        return 1.0
    proj = c @ vt[0]
    axis_len = float(proj.max() - proj.min())
    perim = float(cv2.arcLength(contour.astype(np.int32), True))
    if perim <= 0 or axis_len <= 0:
        return 1.0
    # For a thin straight streak the perimeter is ~2x the axis length.
    return float(np.clip(2.0 * axis_len / perim, 0.0, 1.0))


def classify_discharge(region):
    """-> 'chronic' | 'acute' | 'unknown'  (Master section 6.3)."""
    e = float(region.get("elongation", -1.0))
    if e < 1.0:                      # feature extraction failed
        return "unknown"
    if e >= CHRONIC_ELONGATION:
        contour = region.get("contour")
        if contour is None:
            return "unknown"
        return "chronic" if _straightness(contour) >= STRAIGHTNESS_MIN else "unknown"
    if e < ACUTE_ELONGATION:
        return "acute"
    return "unknown"


# ---------------------------------------------------------------------------
# Self-test:  python pipeline/detect/ships.py
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    from affine import Affine

    print("=" * 62)
    print("  ships.py self-test")
    print("=" * 62)

    rng = np.random.default_rng(0)
    H = W = 512
    db = rng.normal(-22.0, 1.1, (H, W)).astype(np.float32)

    # Three separate vessels, plus one large vessel returning as two fragments.
    # The gap is 3 px — wider than the 3x3 closing can bridge, so they stay two
    # components and the MERGE path is what has to join them. Their centroids
    # are 7 px = 70 m apart: beyond the 50 m default, inside a 100 m radius.
    truth = [(100, 120), (300, 380), (450, 60)]
    for r, c in truth:
        db[r:r + 3, c:c + 4] = -3.0
    db[200:203, 200:204] = -2.0
    db[200:203, 207:211] = -2.5

    # 10 m pixels near 33.6 N.
    deg = 10.0 / (111_320.0 * np.cos(np.radians(33.6)))
    tr = Affine(deg, 0, -118.20, 0, -10.0 / 111_320.0, 33.70)

    ships = detect_ships(db, tr, pixel_size_m=10.0)
    print(f"\n  {len(ships)} ship(s) at the default 50 m merge (expect 5 — 60 m is too far):")
    for s in ships:
        print(f"    lon={s['lon']:.5f} lat={s['lat']:.5f} px_area={s['px_area']:>4} peak_db={s['peak_db']}")

    ok = True
    if len(ships) != 5:
        print(f"\n  [FAIL] expected 5 detections at merge_m=50, got {len(ships)}"); ok = False

    # Same scene, merge radius wide enough to span the hull: the two fragments
    # must collapse into one detection carrying the summed area and the
    # brighter peak.
    wide = detect_ships(db, tr, pixel_size_m=10.0, merge_m=100.0)
    print(f"\n  {len(wide)} ship(s) at a 100 m merge (expect 4 — the hull merges):")
    for s in wide:
        print(f"    lon={s['lon']:.5f} lat={s['lat']:.5f} px_area={s['px_area']:>4} peak_db={s['peak_db']}")
    if len(wide) != 4:
        print(f"  [FAIL] expected 4 merged detections, got {len(wide)}"); ok = False
    elif max(s["px_area"] for s in wide) != 24:
        print("  [FAIL] merged detection did not sum the fragment areas"); ok = False

    if any(not (-118.21 < s["lon"] < -118.15) for s in ships):
        print("  [FAIL] longitude outside the scene"); ok = False
    if any(not (33.60 < s["lat"] < 33.71) for s in ships):
        print("  [FAIL] latitude outside the scene"); ok = False

    # Clean sea must produce nothing.
    empty = detect_ships(rng.normal(-22.0, 1.1, (H, W)).astype(np.float32), tr, pixel_size_m=10.0)
    print(f"\n  clean-sea scene -> {len(empty)} detections (expect 0)")
    if empty:
        print("  [FAIL] false ships on clean sea"); ok = False

    # discharge_class
    print()
    cases = []
    for name, (ax, ay), expect in [("long straight streak", (150, 6), "chronic"),
                                   ("round blob", (60, 58), "acute"),
                                   ("moderate oval", (70, 20), "unknown")]:
        m = np.zeros((H, W), np.uint8)
        cv2.ellipse(m, (256, 256), (ax, ay), 20, 0, 360, 1, -1)
        cnt = max(cv2.findContours(m, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)[0],
                  key=cv2.contourArea).squeeze(axis=1)
        (_, (a1, a2), _) = cv2.fitEllipse(cnt.astype(np.float32))
        elong = max(a1, a2) / max(min(a1, a2), 1e-6)
        got = classify_discharge({"elongation": elong, "contour": cnt})
        cases.append((name, elong, got, expect))
        print(f"  {name:<22} elongation={elong:6.2f}  -> {got:<8} (expect {expect})")
    for name, _, got, expect in cases:
        if got != expect:
            print(f"  [FAIL] {name}: got {got}, expected {expect}"); ok = False

    print("\n  [PASS] all ship + discharge assertions hold" if ok else "\n  [FAIL] see above")
