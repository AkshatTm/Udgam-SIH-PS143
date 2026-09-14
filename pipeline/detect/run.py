#!/usr/bin/env python3
"""
Stage 1 — detection.  Owner: Soumirya.

    python pipeline/detect/run.py --case case-huntington-2021

Reads  cases/<case_id>/sar_vv_vh.tif  (2-band float32 dB GeoTIFF: band 1 = VV,
band 2 = VH) and writes  pipeline/detect/out/detections.geojson, which
pipeline/export/build_case.py then copies into the bundle.

    sar_vv_vh.tif -> detect_array(VV, db_vh=VH)     dark-spot regions + VV/VH stats
                  -> add_shape_features_batch()      elongation, edge_gradient, solidity
                  -> detect_ships()                  bright targets -> Jaiveer's dark vessels
                  -> classify_discharge()            chronic | acute | unknown
                  -> classifier.predict_proba()      confidence -> oil | lookalike
                  -> contour px -> [lon, lat]        via the GeoTIFF's own transform
                  -> detections.geojson              Master section 6.3

GEOREFERENCING (TRAPS #1 and #8). We use the GeoTIFF's own affine transform, not
bounds.json's width_px/height_px — those describe sar.png, which is a separately
downsampled display raster (Huntington: sar.png is 505x577, the GeoTIFF 1337x1281).
The tif bbox is asserted against bounds.json so a genuinely wrong export still
fails loudly. GeoJSON is [lon, lat], longitude FIRST, always. Pixel (0,0) is
top-left = (west, north), so latitude DECREASES as row increases — the affine
handles that, which is precisely why we use it rather than re-deriving it.

THE -3 dB TRAP (docs/team/soumirya-stage1-detection.md 6.4). The documented fallback rule
"contrast < -3 dB AND elongation > 2.5" matches ZERO of our training positives:
Zenodo positives run -0.44 to -1.04 dB at the 5th-95th percentiles. It is not
hardcoded here. --rule-contrast / --rule-elongation exist so the rule is stated
explicitly per scene family when it is used at all, and the run prints the
contrast distribution the detector actually found so the choice is evidence-led.
"""
from __future__ import annotations

import argparse
import json
import os
import pickle
import sys
from pathlib import Path

import numpy as np
import rasterio

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
OUT = HERE / "out"
MODELS = HERE / "models"

if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from pipeline.detect.darkspot import detect_array                      # noqa: E402
from pipeline.detect.features import add_shape_features_batch          # noqa: E402
from pipeline.detect.ships import (detect_ships, classify_discharge,   # noqa: E402
                                   DEFAULT_MIN_DB, DEFAULT_K_SIGMA)
from pipeline.detect import nets                                       # noqa: E402

# How far the tif bbox may drift from bounds.json before we refuse to run.
BBOX_TOL_DEG = 1e-3

# Douglas-Peucker tolerance, in pixels, for the emitted ring.
SIMPLIFY_PX = 2.0

# Sentinel-1 IW noise-equivalent sigma-zero. Below roughly this level a VH pixel
# is thermal noise, not ocean backscatter — and oil cannot damp noise, so the
# channel carries no slick signal however clean it looks.
NESZ_VH_DB = -24.0


def vh_is_usable(vh, nodata_value=0.0, nesz_db=NESZ_VH_DB):
    """Decide, from the scene ALONE, whether the VH band carries real signal.

    This is a physics test applied before anything is detected, so it cannot be
    tuned toward a known answer: it never looks at where a slick is, only at
    where the sea sits relative to the sensor's noise floor.

    Why it exists. The classifier's two strongest features are VH-derived
    (0.55 + 0.14 = 69% of total importance), and "VH is the discriminator" holds
    only while VH is ABOVE the noise floor. In Zenodo the sea sits at ~-20.7 dB
    VH, comfortably above it, and oil damping is visible. In the Huntington GEE
    export the sea sits at -27.8 dB, at or below NESZ — measured VH contrast
    across a real slick there is +0.56 dB while VV is -5.78 dB. Trusting VH in
    that scene is how an unmistakable slick scores 0.010 and is called a
    look-alike.

    -> (usable: bool, sea_vh_db: float, reason: str)
    """
    if vh is None:
        return False, float("nan"), "no VH band in the export"
    v = vh[np.isfinite(vh) & (vh != nodata_value)]
    if v.size == 0:
        return False, float("nan"), "VH band is entirely nodata"
    sea = float(np.median(v))
    if sea <= nesz_db:
        return False, sea, (f"sea VH {sea:.1f} dB is at or below the IW noise floor "
                            f"({nesz_db:.0f} dB) — the band is noise, not backscatter")
    return True, sea, f"sea VH {sea:.1f} dB is above the noise floor ({nesz_db:.0f} dB)"



# ---------------------------------------------------------------------------
# Inputs
# ---------------------------------------------------------------------------

def scene_provenance(case_dir):
    """Which corpus the pixels came from -> (kind, why). kind in {benchmark, satellite}.

    Reads meta.json's `provenance` field (Master 6.1, decision D33). Absent means
    "satellite", so nothing already in the library needs backfilling.

    THIS REPLACES A CHECK THAT NEVER WORKED. The previous version inferred
    provenance from the absence of a CRS on the GeoTIFF, on the belief that
    Zenodo tiles are ungeoreferenced. They are not: Part III scenes carry
    EPSG:4326 exactly like a GEE export, so the test matched both corpora and
    every benchmark bundle would have gone down the satellite path and quietly
    produced classical-path numbers on scenes presented as the network's work.
    It was not a fragile heuristic, it was inert. Routing on the absence of a
    property is the mistake; an explicit field is the fix.

    Why routing exists at all: Layers 1 and 2 reach 0.951 scene accuracy and
    0.435 gated IoU on the Zenodo Part III holdout and do NOT transfer to a GEE
    export — on Huntington, whose slick is unmistakable at -5.78 dB VV, Layer 1
    returns P(oil)=0.003. VH noise, ground scale, bright-ship masking, nodata
    fill and slick size were each tested and each ruled out. So benchmark scenes
    are judged by the networks, which is what they were trained and validated
    for, and satellite scenes by the classical detector plus the rule documented
    in the brief (D7, section 6.4). Both paths are reported, neither is hidden.
    """
    meta_path = case_dir / "meta.json"
    if not meta_path.exists():
        return "satellite", "no meta.json — defaulting to satellite"
    prov = (json.loads(meta_path.read_text()) or {}).get("provenance")
    if prov is None:
        return "satellite", "meta.provenance absent — defaults to satellite (D33)"
    if prov not in ("satellite", "benchmark"):
        raise SystemExit(
            f"meta.json/provenance is {prov!r}; must be 'satellite' or 'benchmark'. "
            f"The validator enforces this enum — fix the bundle, not this file.")
    return prov, f"meta.provenance = {prov!r}"



def load_bounds(case_dir):
    b = json.loads((case_dir / "bounds.json").read_text())
    b.setdefault("db_min", -25.0)
    b.setdefault("db_max", 0.0)
    return b


def load_scene(case_dir, bounds):
    """-> (vv, vh_or_None, transform, pixel_area_km2, source_note).

    Prefers the 2-band float32 dB GeoTIFF (decision D14). Falls back to the
    8-bit sar.png inverted through bounds.json's db clamp, which is lossy: the
    oil signal is ~1 dB deep and 8 bits quantise the clamp range into 256
    levels, so VH precision in particular does not survive. That fallback exists
    so a case without an export still produces something, not because it is fine.
    """
    tif = case_dir / "sar_vv_vh.tif"
    if tif.exists():
        with rasterio.open(tif) as src:
            vv = src.read(1).astype(np.float32)
            vh = src.read(2).astype(np.float32) if src.count >= 2 else None
            transform = src.transform
            w, s, e, n = src.bounds.left, src.bounds.bottom, src.bounds.right, src.bounds.top
            width, height = src.width, src.height

        drift = {k: abs(a - b) for k, (a, b) in {
            "west": (w, bounds["west"]), "south": (s, bounds["south"]),
            "east": (e, bounds["east"]), "north": (n, bounds["north"])}.items()}
        bad = {k: v for k, v in drift.items() if v > BBOX_TOL_DEG}
        if bad:
            raise SystemExit(
                f"sar_vv_vh.tif bbox disagrees with bounds.json by {bad} deg "
                f"(tolerance {BBOX_TOL_DEG}).\n"
                f"  tif   : west={w:.5f} south={s:.5f} east={e:.5f} north={n:.5f}\n"
                f"  bounds: west={bounds['west']} south={bounds['south']} "
                f"east={bounds['east']} north={bounds['north']}\n"
                f"This is Akshat's export, not something to work around here.")

        # Ground pixel area. transform.a is deg lon/px, transform.e is deg lat/px
        # (negative). Longitude degrees shrink with latitude.
        lat_mid = 0.5 * (s + n)
        m_lon = abs(transform.a) * 111_320.0 * np.cos(np.radians(lat_mid))
        m_lat = abs(transform.e) * 111_320.0
        px_km2 = float(m_lon * m_lat / 1e6)
        note = (f"sar_vv_vh.tif {width}x{height}, {src.count} band(s), "
                f"{m_lon:.1f}x{m_lat:.1f} m/px")
        return vv, vh, transform, px_km2, note

    png = case_dir / "sar.png"
    if not png.exists():
        raise SystemExit(f"{case_dir}: neither sar_vv_vh.tif nor sar.png found.")

    from PIL import Image
    from affine import Affine
    img = np.asarray(Image.open(png).convert("L")).astype(np.float32)
    lo, hi = float(bounds["db_min"]), float(bounds["db_max"])
    vv = (img / 255.0) * (hi - lo) + lo
    height, width = vv.shape
    transform = Affine((bounds["east"] - bounds["west"]) / width, 0, bounds["west"],
                       0, -(bounds["north"] - bounds["south"]) / height, bounds["north"])
    lat_mid = 0.5 * (bounds["south"] + bounds["north"])
    m_lon = abs(transform.a) * 111_320.0 * np.cos(np.radians(lat_mid))
    m_lat = abs(transform.e) * 111_320.0
    px_km2 = float(m_lon * m_lat / 1e6)
    note = (f"sar.png {width}x{height} 8-bit, inverted through clamp [{lo}, {hi}] "
            f"— LOSSY, no VH. Ask Akshat for sar_vv_vh.tif (D14).")
    return vv, None, transform, px_km2, note


def load_model(vv_only=False):
    """-> (clf, feature_order, threshold, note). Any of these may be None.

    vv_only selects the D3 fallback: the model trained on VV features alone, for
    scenes whose VH band is at or below the sensor noise floor. We switch models
    rather than zero-filling the VH columns, because a zero is a value and the
    forest would happily split on it.
    """
    if vv_only:
        pkl = MODELS / "classifier_vv_only.pkl"
        meta_path = MODELS / "model_meta_vv_only.json"
        if not pkl.exists():
            return None, None, None, ("VH unusable but no VV-only model on disk — "
                                      "run train.py; falling back to the stated rule")
        meta = json.loads(meta_path.read_text()) if meta_path.exists() else {}
        features = meta.get("features")
        with open(pkl, "rb") as fh:
            clf = pickle.load(fh)
        threshold = float(meta.get("threshold", 0.5))
        m3 = meta.get("metrics_part3", {})
        note = (f"{type(clf).__name__} VV-ONLY (D3) with {len(features)} features, "
                f"threshold {threshold:.4f}. Part III F1 {m3.get('f1','?')} vs the "
                f"dual-pol model's — degradation is expected and is reported per case.")
        return clf, features, threshold, note

    pkl, forder = MODELS / "classifier.pkl", MODELS / "feature_order.json"
    if not pkl.exists() or not forder.exists():
        return None, None, None, "no model on disk — classification falls back to the rule"
    with open(pkl, "rb") as fh:
        clf = pickle.load(fh)
    features = json.loads(forder.read_text())

    threshold, extra = 0.5, ""
    meta_path = MODELS / "model_meta.json"
    if meta_path.exists():
        meta = json.loads(meta_path.read_text())
        threshold = float(meta.get("threshold", 0.5))
        extra = (f", trained on {meta.get('trained_on','?')}, "
                 f"evaluated on {meta.get('tested_on','?')}")
    note = (f"{type(clf).__name__} with {len(features)} features, "
            f"threshold {threshold}{extra}")
    return clf, features, threshold, note


# ---------------------------------------------------------------------------
# Geometry
# ---------------------------------------------------------------------------

def ring_lonlat(contour, transform, simplify_px=SIMPLIFY_PX):
    """OpenCV contour (N,2) as (x=col, y=row) -> closed [[lon,lat], ...] ring.

    Douglas-Peucker first, so we are not shipping a 4,000-vertex ring per slick;
    but a thin slick can legitimately be long and low-vertex, so the simplified
    ring is only accepted when it still has enough points to be a polygon.
    """
    import cv2
    pts = contour.astype(np.int32).reshape(-1, 1, 2)
    simp = cv2.approxPolyDP(pts, simplify_px, True).reshape(-1, 2)
    if simp.shape[0] < 4:
        simp = contour.reshape(-1, 2)

    ring = []
    for col, row in simp:
        lon, lat = transform * (float(col) + 0.5, float(row) + 0.5)
        ring.append([round(float(lon), 5), round(float(lat), 5)])
    if ring[0] != ring[-1]:
        ring.append(list(ring[0]))
    return ring


def centroid_lonlat(region, transform):
    rows, cols = np.nonzero(region["mask"])
    lon, lat = transform * (float(cols.mean()) + 0.5, float(rows.mean()) + 0.5)
    return [round(float(lon), 5), round(float(lat), 5)]


# ---------------------------------------------------------------------------
# Classification
# ---------------------------------------------------------------------------

def _apply_area_floor(regions, min_oil_km2):
    """Demote any 'oil' region below the minimum reportable area.

    A dark patch of a few hundred pixels is not a reportable spill, and at the
    rule boundary it is indistinguishable from clutter: on the Ennore look-alike
    the two regions that squeaked past the -3 dB rule were 0.065 and 0.053 km2
    at margins of 0.528 and 0.500 — i.e. sitting exactly ON the threshold.

    0.10 km2 is set from the LIBRARY, not from that case: section A4 records the
    Gulf of Alaska slick as the smallest we must detect at 0.3 km2, so this floor
    is three times below anything we are required to find. It is stated on the
    results slide rather than applied quietly.
    """
    if min_oil_km2 <= 0:
        return
    for r in regions:
        if r.get("classification") == "oil" and float(r.get("area_km2", 0.0)) < min_oil_km2:
            r["classification"] = "lookalike"
            r["confidence"] = min(float(r.get("confidence", 0.5)), 0.45)
            r["_demoted_area"] = True


def score_regions(regions, clf, features, threshold, rule_contrast, rule_elongation,
                  force_rule=False, min_oil_km2=0.0):
    """Attach 'confidence' and 'classification' to every region.

    Returns the method actually used, so the run can say so out loud rather than
    implying a model spoke when a rule did.
    """
    def value(region, name):
        if name == "is_linear":
            return 1.0 if region.get("shape_class") == "linear" else 0.0
        return float(region.get(name, np.nan))

    if clf is not None and features and not force_rule:
        missing = sorted({f for f in features
                          for r in regions
                          if f != "is_linear" and f not in r})
        if not missing:
            X = np.array([[value(r, f) for f in features] for r in regions],
                         dtype=np.float64)
            if np.isfinite(X).all():
                proba = clf.predict_proba(X)[:, 1]
                for r, p in zip(regions, proba):
                    r["confidence"] = float(p)
                    r["classification"] = "oil" if p >= threshold else "lookalike"
                _apply_area_floor(regions, min_oil_km2)
                return f"model (threshold {threshold}, area >= {min_oil_km2} km2)"
            reason = "non-finite feature values"
        else:
            reason = f"regions missing {missing}"
    else:
        reason = ("the model is out of its domain on a case export"
                  if force_rule else "no model loaded")

    for r in regions:
        is_oil = (r.get("contrast_db", 0.0) <= rule_contrast
                  and r.get("elongation", 0.0) >= rule_elongation)
        r["classification"] = "oil" if is_oil else "lookalike"
        # A rule is a decision, not a probability, so we do not manufacture one.
        # The number reported is how far past the stated threshold the region
        # sits, mapped monotonically into [0,1] and centred on 0.5 at the
        # threshold itself. It is a margin, and the run says so out loud.
        margin = (rule_contrast - r.get("contrast_db", 0.0)) / max(abs(rule_contrast), 1e-6)
        conf = 0.5 + 0.25 * max(-2.0, min(2.0, margin))
        r["confidence"] = float(min(0.95, max(0.05, conf)))
    _apply_area_floor(regions, min_oil_km2)
    return (f"RULE contrast_db <= {rule_contrast} and elongation >= {rule_elongation}, "
            f"area >= {min_oil_km2} km2 ({reason})")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(description="Stage 1 — detection")
    ap.add_argument("--case", required=True, help="case id, e.g. case-huntington-2021")
    ap.add_argument("--cases-root", default=str(REPO / "cases"))
    ap.add_argument("--out", default=None, help="override the output geojson path")
    ap.add_argument("--t-high", type=float, default=2.0,
                    help="detector core depth in dB (main knob)")
    ap.add_argument("--t-low", type=float, default=1.0)
    ap.add_argument("--threshold", type=float, default=None,
                    help="override the classifier probability threshold")
    ap.add_argument("--rule-contrast", type=float, default=None,
                    help="fallback rule: contrast_db at or below this is oil. NOT -3 on "
                         "benchmark scenes; see the -3 dB trap in this file's docstring. "
                         "REQUIRED on the classical path — there is no safe default, so "
                         "omitting it is a hard error rather than a silent reclassification")
    ap.add_argument("--min-oil-km2", type=float, default=0.10,
                    help="a region smaller than this is never classified 'oil'. 0.10 km2 "
                         "sits well below the smallest slick in the library (Alaska, "
                         "0.3 km2, section A4) so it cannot suppress anything we must find")
    ap.add_argument("--rule-elongation", type=float, default=None,
                    help="fallback rule: elongation at or above this is oil. REQUIRED on "
                         "the classical path, for the same reason as --rule-contrast")
    ap.add_argument("--no-ships", action="store_true", help="skip the ship detector")
    # Defaults come FROM ships.py, never duplicated here. They were duplicated,
    # and the copy went stale: ships.DEFAULT_K_SIGMA was corrected 8.0 -> 4.0 but
    # this argparse default stayed at 8.0 and silently shadowed it, so the fix was
    # inert through the pipeline while the module looked correct in review.
    ap.add_argument("--ship-min-db", type=float, default=DEFAULT_MIN_DB,
                    help="absolute brightness floor for a radar contact. Raising it "
                         "loses small vessels; lowering it invents them, and a false "
                         "dark-vessel claim is worse than a miss")
    ap.add_argument("--ship-k-sigma", type=float, default=DEFAULT_K_SIGMA,
                    help="scene-relative floor, in robust sigmas above the sea")
    ap.add_argument("--path", choices=("auto", "networks", "classical"), default="auto",
                    help="auto routes by provenance: Zenodo benchmark scenes to the "
                         "networks (what they were trained for), GEE case exports to the "
                         "classical detector plus the documented rule (D7, 6.4)")
    a = ap.parse_args()

    case_dir = Path(a.cases_root) / a.case
    if not (case_dir / "bounds.json").exists():
        raise SystemExit(f"{case_dir}/bounds.json not found — Stage 1 needs Akshat's "
                         f"scene export (sar_vv_vh.tif + bounds.json) first.")

    bounds = load_bounds(case_dir)
    vv, vh, transform, px_km2, src_note = load_scene(case_dir, bounds)
    vh_ok, sea_vh, vh_reason = vh_is_usable(vh)
    clf, features, model_threshold, model_note = load_model(vv_only=not vh_ok)
    threshold = a.threshold if a.threshold is not None else (model_threshold or 0.5)

    print(f"[detect] case   : {a.case}")
    print(f"[detect] source : {src_note}")
    print(f"[detect] pixel  : {px_km2*1e6:.0f} m2  ({px_km2:.6f} km2)")
    print(f"[detect] VH     : {'USABLE' if vh_ok else 'NOT USABLE'} — {vh_reason}")
    print(f"[detect] model  : {model_note}")

    # ---- Layer 1 / Layer 2, falling back to the classical detector ----------
    kind, why = scene_provenance(case_dir)
    use_nets = (a.path == "networks") or (a.path == "auto" and kind == "benchmark")
    print(f"[detect] scene   : {kind.upper()} — {why}")
    print(f"[detect] path    : {'Layer 1 + Layer 2 networks' if use_nets else 'classical detector + stated rule'}"
          f"{'' if a.path != 'auto' else '  (auto, by provenance)'}")

    # THE RERUN HAZARD (Akshat, D34). The rule threshold is passed on the command line
    # and recorded in no bundle, so a rerun that forgets --rule-contrast used to fall
    # through to -0.5 and silently reclassify every detection — no error, different
    # answer, and the dB confidence bands wrong with it. The default is now None and
    # the classical path REFUSES to guess. -0.5 is not restored as a default because it
    # is the right number for Zenodo and the wrong one for a satellite export; that is
    # exactly the choice the docstring says must be stated per scene family.
    NL = chr(10)
    if use_nets:
        rule_contrast = -0.5 if a.rule_contrast is None else a.rule_contrast
        rule_elongation = 2.0 if a.rule_elongation is None else a.rule_elongation
    else:
        missing = [f for f, v in (("--rule-contrast", a.rule_contrast),
                                  ("--rule-elongation", a.rule_elongation)) if v is None]
        if missing:
            sys.exit(NL.join([
                f"[detect] FATAL: {' and '.join(missing)} not given, and this scene",
                f"         takes the classical path ({why}), where the rule decides",
                 "         oil vs look-alike. There is no safe default: -0.5 dB suits",
                 "         Zenodo, -3.0 dB suits our satellite exports, and guessing",
                 "         silently changes every label. The seven live cases ship with:",
                 "             --rule-contrast -3.0 --rule-elongation 2.5",
            ]))
        rule_contrast, rule_elongation = a.rule_contrast, a.rule_elongation
    print(f"[detect] rule   : contrast <= {rule_contrast:+.2f} dB AND elongation >= {rule_elongation:.2f}")
    scene_cnn, gate_thr = nets.load_classifier() if use_nets else (None, None)
    unet, unet_thr = nets.load_unet() if use_nets else (None, None)
    layer1_prob = None
    gated_off = False
    regions, info = [], {}

    if scene_cnn is not None or unet is not None:
        norm, valid, nstats = nets.normalise_scene(vv, vh)
        if scene_cnn is not None:
            layer1_prob = nets.classify_scene(scene_cnn, norm)
            gated_off = layer1_prob < gate_thr
            verdict = "NO oil in this scene" if gated_off else "oil present"
            print(f"[detect] layer1 : P(oil) = {layer1_prob:.3f} vs threshold "
                  f"{gate_thr:.3f}  ->  {verdict}")
            if gated_off:
                # Stopping here IS the answer, not a failure. This is the path
                # demo cases 6 and 7 exist to exercise (D2).
                print("[detect]          gate closed — writing zero oil features, "
                      "which is the correct output for a look-alike or clean scene.")

    if not gated_off and unet is not None:
        prob = nets.segment_scene(unet, norm, valid)
        regions = nets.mask_to_regions(prob, unet_thr, px_km2, vv, db_vh=vh, valid=valid)
        print(f"[detect] layer2 : U-Net @ {unet_thr} -> {len(regions)} region(s) "
              f"(50% overlap, averaged)")
    elif not gated_off:
        regions, info = detect_array(vv, px_km2, db_vh=vh,
                                     t_high_db=a.t_high, t_low_db=a.t_low)
        print(f"[detect] scene  : sea_ref={info['sea_ref_db']:.2f} dB  "
              f"noise med/mad={info['noise_median']:.2f}/{info['noise_mad']:.2f}  "
              f"thresholds {info['t_low']:.2f}/{info['t_high']:.2f} dB  "
              f"land={info['land_frac']:.1%}")
        print(f"[detect] regions: {len(regions)}  (classical depth-map detector"
              f"{' — networks not trained yet' if unet is None else ''})")

    ships, ship_stats = ([], None)
    if not a.no_ships:
        # Exclude land first. prepare() already derives the land mask and its
        # dilated coastal halo for the dark-spot path; the ship detector was
        # running on the raw array, so a port scene returned its own buildings
        # as vessels (Ennore: 1,377 of them, peaking at +34 dB on land).
        from pipeline.detect.darkspot import prepare as _prepare
        _, _, _land, _ = _prepare(vv, px_km2)
        ships, ship_stats = detect_ships(vv, transform, min_db=a.ship_min_db,
                                         k_sigma=a.ship_k_sigma, return_stats=True,
                                         exclude=_land)
    print(f"[detect] ships  : {len(ships)} bright radar contact(s)")
    if ship_stats:
        print(f"[detect]          threshold {ship_stats['threshold_db']} dB "
              f"(sea {ship_stats['sea_med_db']} +/- {ship_stats['sea_sigma_db']}); "
              f"{ship_stats['n_components']} candidate(s), rejected "
              f"{ship_stats['rejected_small']} small / "
              f"{ship_stats['rejected_large']} large / "
              f"{ship_stats['rejected_diffuse']} diffuse")
        if ship_stats["floor_binding"]:
            # Say it out loud: a faint small vessel can be lost here, and on a
            # dark-vessel case that miss IS the result.
            print(f"[detect]          NOTE the fixed {a.ship_min_db} dB floor is what "
                  f"candidates had to clear, not this scene's own noise. A small "
                  f"faint hull could fall below it — relevant on a dark-vessel case.")
        if ship_stats["brightest_rejected_db"] is not None:
            print(f"[detect]          brightest REJECTED candidate: "
                  f"{ship_stats['brightest_rejected_db']} dB")

    features_out = []
    if regions:
        add_shape_features_batch(regions, vv)

        # Evidence for the threshold choice (6.4) — print what the detector
        # actually measured on THIS scene before saying what we did about it.
        cd = np.array([r.get("contrast_db", np.nan) for r in regions], dtype=float)
        cd = cd[np.isfinite(cd)]
        if cd.size:
            print(f"[detect] contrast_db on this scene: min={cd.min():+.2f} "
                  f"p5={np.percentile(cd,5):+.2f} med={np.median(cd):+.2f} "
                  f"p95={np.percentile(cd,95):+.2f} max={cd.max():+.2f}")

        method = score_regions(regions, clf, features, threshold,
                               rule_contrast, rule_elongation,
                               force_rule=not use_nets, min_oil_km2=a.min_oil_km2)
        print(f"[detect] scored by: {method}")

        order = np.argsort([-r.get("confidence", 0.0) for r in regions])
        for rank, idx in enumerate(order, 1):
            r = regions[idx]
            props = {
                "id": f"det-{rank:02d}",
                "classification": r["classification"],
                "confidence": round(float(r["confidence"]), 3),
                "area_km2": round(float(r["area_km2"]), 3),
                "elongation": round(float(r["elongation"]), 2),
                "edge_gradient": round(float(r["edge_gradient"]), 4),
                "contrast_db": round(float(r.get("contrast_db", 0.0)), 2),
                "shape_class": r["shape_class"],
                "discharge_class": classify_discharge(r),
                "centroid": centroid_lonlat(r, transform),
                # ship_detections is NOT written here any more (Master 6.3, D34).
                # Contacts are a scene-level observation; they live once, top-level
                # on the FeatureCollection below. Copying the scene list onto every
                # feature lost it entirely on a zero-detection scene (both Zenodo
                # cases: 1 and 31 contacts dropped) and made the map draw each
                # contact once per feature (Ennore: 72 contacts, 2,088 markers).
            }
            if "vh_contrast_db" in r:
                props["vh_contrast_db"] = round(float(r["vh_contrast_db"]), 3)
            if "vh_mean_depth_db" in r:
                props["vh_mean_depth_db"] = round(float(r["vh_mean_depth_db"]), 3)
            props["solidity"] = round(float(r["solidity"]), 3)
            props["mean_depth_db"] = round(float(r.get("mean_depth_db", 0.0)), 3)

            features_out.append({
                "type": "Feature",
                "geometry": {"type": "Polygon",
                             "coordinates": [ring_lonlat(r["contour"], transform)]},
                "properties": props,
            })

    out_path = Path(a.out) if a.out else (OUT / "detections.geojson")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    # Top-level, beside `features`: valid GeoJSON (RFC 7946 §6.1 foreign member).
    # [] means the detector ran and found nothing; --no-ships omits the key, because
    # a detector that did not run found nothing only in the sense of null, not 0.
    collection = {"type": "FeatureCollection"}
    if not a.no_ships:
        collection["ship_detections"] = ships
    collection["features"] = features_out
    out_path.write_text(json.dumps(collection, indent=1))

    n_oil = sum(1 for f in features_out if f["properties"]["classification"] == "oil")
    n_chronic = sum(1 for f in features_out if f["properties"]["discharge_class"] == "chronic")
    if layer1_prob is not None:
        # Report the gate's confidence rather than implying certainty (6.5 #3).
        band = ("confident" if abs(layer1_prob - 0.5) > 0.35 else
                "MARGINAL — say so rather than presenting certainty")
        print(f"[detect] layer1 confidence {layer1_prob:.3f} — {band}")
    print(f"[detect] wrote  : {out_path}")
    print(f"[detect]          {len(features_out)} feature(s), {n_oil} 'oil', "
          f"{n_chronic} chronic, {len(ships)} ship(s)")
    if not ships:
        print("[detect]          (an empty ship_detections list is valid and common)")
    if n_oil == 0:
        print("[detect]          zero 'oil' features — the correct answer for a "
              "look-alike or no-spill case; an error for a spill case.")
    print(f"[detect] next   : python pipeline/export/build_case.py --case {a.case}")


if __name__ == "__main__":
    main()
