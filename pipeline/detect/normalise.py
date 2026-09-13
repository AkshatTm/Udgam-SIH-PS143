#!/usr/bin/env python3
"""
normalise.py  —  THE single per-scene normalisation.  Owner: Soum.   (plan E2)

    python pipeline/detect/normalise.py          # self-test
    python pipeline/detect/normalise.py --audit  # idempotence check over Parts I+II

WHY THIS FILE EXISTS
--------------------
The same median/MAD normalisation was implemented twice — `build_cache.normalise()`
(training) and `nets.normalise_band()` (inference). Two copies of one rule is the
exact shape of the bug that made the k_sigma fix inert for a whole day: the module
read correctly in review while the pipeline used a stale duplicate. Both now call
in here, so a change cannot land on one side only.

THE PROBLEM THIS FIXES
----------------------
`median` assumes the sea is the majority of the scene. On Zenodo Part III that holds
for 138 of 150 oil scenes. On the other 12 — oil covering >30% of the frame — the
slick IS the median, the contrast the network needs is normalised away, and IoU
collapses to 0.085 against 0.66-0.78 everywhere else. At 78% coverage the U-Net's
maximum probability over the entire scene is 0.374: not one pixel crosses 0.5.

THE ESTIMATOR, AND WHY THIS ONE
-------------------------------
**Brightest-mode selection, with a sigma-clip polish.** The sea is the brightest
large population in the scene; oil is a darker mode. So: histogram the valid dB,
smooth it, find peaks that clear a prominence bar, and if two or more survive, cut
at the valley below the BRIGHTEST peak and estimate median/MAD above that cut. If
only one peak survives, fall straight through to the plain median — which is what
makes this safe on the 93% of scenes that already work.

FIRST ATTEMPT, AND WHY IT FAILED (kept because the failure is instructive):
iterative one-sided sigma-clipping, `keep = band > ref - 2*scale`, re-estimating
each pass. The self-test below killed it in one run. When oil is the MAJORITY the
median already sits inside the slick and MAD is inflated by the bimodality, so the
cut at ref-2*scale lands below everything: on a 78%-oil synthetic it kept 99.6% of
pixels, converged in one iteration, and returned -31.74 dB against a true sea of
-27.00. Clipping a dark tail cannot escape a dark mode that IS the bulk. The clip
survives only as a polish AFTER the mode is chosen.

Rejected alternatives, and the reason each fails:

  fixed high quantile  The correct quantile is (1 - coverage). Coverage is unknown
                       and spans 0.001 to 0.78, so no fixed choice works: p80 is
                       right at 20% oil, lands in the bright sea tail at 0.5% oil,
                       and is still inside the slick at 78%. This is why the earlier
                       percentile experiment degraded monotonically as p rose. (It
                       also proved nothing on its own terms — it was applied at
                       INFERENCE ONLY to a median-trained model, shifting every
                       input by a constant the network had never seen.)

  2-component GMM      Sound in principle, fragile in practice: 1,370 of 2,565
                       Parts I+II scenes contain no oil at all, so there is no
                       second component and the fit splits the sea itself. Needs a
                       BIC guard and a separation guard — most of the complexity
                       for none of the robustness.

  Otsu                 Always returns a split, even on unimodal data, and offers no
                       likelihood to test against. The peak-prominence test below is
                       the fix for exactly that objection: it is allowed to find ONE
                       mode and decline to split.

This is chosen because it is **coverage-adaptive** (the cut comes from where the
data actually separates, not from a constant quantile) and **idempotent on clean
scenes** (one mode -> plain median, bit-for-bit). Idempotence is what makes it safe
for the 93% of scenes that already work — and it is the property the audit below
measures rather than assumes.
"""
from __future__ import annotations

import argparse
import json
import os
import sys

import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.abspath(os.path.join(_HERE, "..", ".."))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

CLIP_SIGMA = 6.0            # matches build_cache.CLIP_SIGMA and nets.CLIP_SIGMA
EPS = 1e-6
SEA_BINS = 256              # histogram resolution for mode finding
SEA_MIN_PROM = 0.04         # a peak must clear 4% of the tallest peak to count
SEA_MIN_SEP_DB = 1.5        # two modes closer than this are one mode
SEA_MIN_FRAC = 0.02         # the bright mode must hold >=2% of valid pixels, or it
                            # is a handful of ships rather than the sea
SEA_MAX_SHIFT_DB = 9.0      # a "sea" mode more than this far above the scene median
                            # is not sea. Oil-vs-sea contrast at C-band VV is 4.3-9.0
                            # dB measured on this corpus, and the largest genuine
                            # shift over all of Parts I+II is 5.42 dB. The rejected
                            # cases run 10.6, 11.9, 14.0 and 21.0 dB — land.
SEA_MAX_MAD_RATIO = 1.0     # the bright mode must be no ROUGHER than the dark one.
                            # Sea under steady wind is homogeneous speckle; oil sits
                            # near the noise floor and is structurally variable; LAND
                            # is very heterogeneous. Measured on the corpus: genuine
                            # large-slick scenes give 0.53-0.69, while P12_Oil_00127
                            # -- 3.2% oil, whose "bright mode" is a coastline at
                            # -14.1 dB -- gives 1.32. Without this guard that scene
                            # shifts its reference 8.26 dB onto land, which would
                            # make the entire ocean read as oil.
SEA_K = 2.0                 # polish: clip below ref - SEA_K*scale once the mode is chosen
SEA_POLISH_ITER = 3
SEA_TOL = 0.02              # dB; stop when the reference stops moving


LAND_WINDOW_PX = 51         # matches darkspot.prepare's land_window_px
LAND_DELTA_DB = 7.0         # matches darkspot.prepare's land_delta_db


def land_mask(band, finite=None, window=LAND_WINDOW_PX, delta=LAND_DELTA_DB):
    """Pixels whose LOCAL mean sits well above the sea -> land.

    This is the population filter the histogram needs, not a detection mask, so it
    is deliberately lighter than `darkspot.prepare()`: that one adds closing, hole
    filling, a minimum-area test and a 40 px dilation because it must not let a
    coastal sidelobe become a detection. Here we only need land OUT of the sample
    before estimating a sea level, and the local-mean test alone does that at a
    third of the cost. The two share the same two constants on purpose.

    `sea_ref` is the 20th percentile of local means, which is robust to a scene that
    is a third land — the same trick darkspot uses.
    """
    from scipy import ndimage as ndi
    if finite is None:
        finite = np.isfinite(band) & (band != 0.0)
    if not finite.any():
        return np.zeros_like(band, bool)
    glob = float(np.median(band[finite]))
    loc = ndi.uniform_filter(np.where(finite, band, glob).astype(np.float32), size=window)
    sea_ref = float(np.percentile(loc[finite], 20))
    return (loc > sea_ref + delta) | ~finite


def valid_mask(band, exclude_land=False):
    """Finite, not the exact-zero nodata sentinel (TRAPS #22), and optionally not land.

    WHY exclude_land EXISTS. `build_cache.normalise()`'s docstring has always said
    valid means "not NaN, not exact-zero, not masked land" — but the implementation
    never masked land. That gap is what failed the first two E2 audits: on 22 of the
    Parts I+II look-alike and no-oil scenes the brightest histogram mode is a
    coastline, so the estimator picked land as "sea" and moved the reference by up to
    21 dB. A reference on land makes the entire ocean read as oil.

    No threshold on the shift can fix that, and I tried: sweeping the cap from 9 dB
    down to 5 dB never separated the two populations, because genuine look-alike
    scenes with a 30-50% dark patch legitimately re-reference by 3-6 dB. What DOES
    separate them is where the reference lands — the land cases sit at -7 to -15 dB,
    which is not ocean. Excluding land from the sample is the fix; capping the
    symptom is not.
    """
    v = np.isfinite(band) & (band != 0.0)
    if exclude_land:
        v &= ~land_mask(band, v)
    return v


def median_reference(band, valid=None):
    """The ORIGINAL estimator: whole-scene median and 1.4826*MAD.

    Kept verbatim because Layer 3 inverts these to recover real decibels. Changing
    what `contrast_db` means is a separate decision from changing what the network
    sees, and this file deliberately does not couple them.
    """
    if valid is None:
        valid = valid_mask(band)
    if not valid.any():
        return 0.0, 1.0
    v = band[valid]
    med = float(np.median(v))
    mad = float(np.median(np.abs(v - med)))
    return med, 1.4826 * mad + EPS


def sea_reference(band, valid=None, exclude_land=True, bins=SEA_BINS, min_prom=SEA_MIN_PROM,
                  min_sep_db=SEA_MIN_SEP_DB, min_frac=SEA_MIN_FRAC,
                  k=SEA_K, polish_iter=SEA_POLISH_ITER, tol=SEA_TOL):
    """Sea level as the BRIGHTEST significant mode -> (ref, scale, info).

    One mode found -> returns the plain median, bit-for-bit. That fall-through is
    the safety property: scenes that already work are not touched at all.

    info carries n_modes, cut_db, frac_sea and shift_db so the audit can show what
    moved and, more importantly, what did not.
    """
    from scipy.signal import find_peaks

    if valid is None:
        valid = valid_mask(band, exclude_land=exclude_land)
    med0, scale0 = median_reference(band, valid)
    info = {"n_modes": 0, "cut_db": None, "frac_sea": 1.0, "shift_db": 0.0,
            "mad_ratio": None, "rejected": None, "mode": "median"}
    if not valid.any():
        return med0, scale0, info

    v = band[valid]
    lo, hi = np.percentile(v, [0.5, 99.5])
    if not np.isfinite(lo) or not np.isfinite(hi) or (hi - lo) < 1e-3:
        return med0, scale0, info                      # degenerate, nothing to split

    hist, edges = np.histogram(v, bins=bins, range=(float(lo), float(hi)))
    centres = 0.5 * (edges[:-1] + edges[1:])
    kern = np.array([1.0, 4.0, 6.0, 4.0, 1.0]); kern /= kern.sum()
    h = np.convolve(hist.astype(float), kern, mode="same")

    db_per_bin = (hi - lo) / bins
    peaks, _ = find_peaks(h, prominence=min_prom * h.max(),
                          distance=max(1, int(round(min_sep_db / db_per_bin))))
    info["n_modes"] = int(len(peaks))

    # One mode (or none) -> unimodal scene -> the median IS the sea. Fall through.
    if len(peaks) < 2:
        return med0, scale0, info

    # Cut at the valley immediately below the brightest mode. Bins ascend in dB, so
    # the brightest mode is the last peak.
    hi_pk, lo_pk = peaks[-1], peaks[-2]
    valley = lo_pk + int(np.argmin(h[lo_pk:hi_pk + 1]))
    cut = float(centres[valley])
    sea = v[v > cut]

    # A "bright mode" made of a few hundred ship pixels is not the sea.
    if sea.size < max(64, int(min_frac * v.size)):
        return med0, scale0, info

    ref = float(np.median(sea))
    scale = 1.4826 * float(np.median(np.abs(sea - ref))) + EPS
    frac_sea = float(sea.size) / float(v.size)
    info["frac_sea"] = frac_sea

    # ------------------------------------------------------------------
    # WHICH OF THE TWO FAILURES IS THIS? They need different answers, and
    # conflating them is what made the first design unsafe.
    #
    # Measured on the 12 Part III scenes that score IoU 0.085:
    #   4 of 12 are >50% oil  -> the median sits INSIDE the slick.
    #                            Reference AND scale are wrong.
    #   8 of 12 are 30-50%    -> the median is still in the sea.
    #                            Only the SCALE is inflated by the bimodality.
    #
    # The 30-50% case is the majority AND the safe one: keeping the median as the
    # reference means the reference cannot be moved onto land, which is exactly the
    # accident that failed the first audit (p99 shift 13.96 dB on no-oil scenes,
    # max 21.0 dB). So the reference is only overridden when the dark mode is
    # genuinely the majority, and even then only if the move is physically
    # plausible for oil.
    # ------------------------------------------------------------------
    if frac_sea >= 0.5:
        # Median already sits in the bright (sea) mode. Keep it — take only the
        # uncontaminated scale.
        info.update(cut_db=cut, shift_db=0.0, mode="scale-only")
        return med0, scale, info

    # Dark mode is the majority: the median really is inside the slick.
    dark = v[v <= cut]
    if dark.size >= 64:
        dmed = float(np.median(dark))
        dmad = 1.4826 * float(np.median(np.abs(dark - dmed))) + EPS
        info["mad_ratio"] = float(scale / dmad)
        if scale / dmad > SEA_MAX_MAD_RATIO:
            info["rejected"] = "bright mode rougher than dark mode — land, not sea"
            return med0, scale0, info
    if (ref - med0) > SEA_MAX_SHIFT_DB:
        info["rejected"] = f"shift {ref - med0:.1f} dB exceeds the oil-contrast ceiling — land"
        return med0, scale0, info

    # Polish. Safe now: ref already sits in the sea mode, so clipping the dark tail
    # removes residual oil bleed rather than failing to escape the slick.
    for _ in range(polish_iter):
        keep = sea > (ref - k * scale)
        if keep.sum() < 64:
            break
        kv = sea[keep]
        new_ref = float(np.median(kv))
        new_scale = 1.4826 * float(np.median(np.abs(kv - new_ref))) + EPS
        moved = abs(new_ref - ref)
        ref, scale = new_ref, new_scale
        if moved < tol:
            break

    info.update(cut_db=cut, shift_db=float(ref - med0), mode="full-override")
    return ref, scale, info


def normalise_band(band, mode="median"):
    """dB -> [-1, +1]. -> (norm float32, valid bool, ref, scale).

    mode="median"  the shipped behaviour, bit-for-bit
    mode="sea"     sea-referenced (plan E2)

    Invalid pixels are set to 0.0 — the normalised SEA level, not a dark value, so
    the network is never told there is a slick where there is land.
    """
    valid = valid_mask(band)
    if not valid.any():
        return np.zeros_like(band, np.float32), valid, 0.0, 1.0
    if mode == "sea":
        ref, scale, _ = sea_reference(band, valid)
    elif mode == "median":
        ref, scale = median_reference(band, valid)
    else:
        raise ValueError(f"mode must be 'median' or 'sea', got {mode!r}")
    norm = np.clip((band - ref) / scale, -CLIP_SIGMA, CLIP_SIGMA) / CLIP_SIGMA
    return np.where(valid, norm, 0.0).astype(np.float32), valid, ref, scale


# ---------------------------------------------------------------------------
# Self-test
# ---------------------------------------------------------------------------

def _selftest():
    rng = np.random.default_rng(7)
    ok = True

    # 1. Bit-for-bit agreement with the shipped implementation, which is what makes
    #    it safe to route build_cache and nets through here before any retrain.
    band = (rng.normal(-27.0, 0.7, (512, 512))).astype(np.float32)
    band[:10, :10] = 0.0                                   # nodata sentinel
    v = valid_mask(band)
    med = float(np.median(band[v]))
    mad = float(np.median(np.abs(band[v] - med)))
    want = np.clip((band - med) / (1.4826 * mad + EPS), -CLIP_SIGMA, CLIP_SIGMA) / CLIP_SIGMA
    want = np.where(v, want, 0.0).astype(np.float32)
    got, _, _, _ = normalise_band(band, "median")
    same = np.array_equal(got, want)
    print(f"  median mode reproduces the shipped formula exactly : {same}")
    ok &= same

    # 2. Idempotence: on a sea-only scene the sea reference must barely move.
    ref, scale, info = sea_reference(band)
    d = abs(ref - med)
    print(f"  clean scene   shift {d:6.3f} dB  ({info['n_modes']} mode(s), "
          f"{100*info['frac_sea']:.1f}% sea)   want < 0.15")
    ok &= d < 0.15

    # 3. The failure case: 78% of the scene is oil, 5 dB darker. The plain median
    #    lands INSIDE the slick; the sea reference must find the sea.
    scene = rng.normal(-27.0, 0.7, (512, 512)).astype(np.float32)
    oil = np.zeros((512, 512), bool)
    oil[:, :400] = True                                    # 78.1%
    # Oil is noisier than sea, not just darker: damped water sits nearer the noise
    # floor and a slick has internal thickness structure. Measured on the corpus,
    # bright/dark MAD ratio runs 0.53-0.69 on real large-slick scenes. Modelling oil
    # with the SAME sigma as sea would park this test exactly on SEA_MAX_MAD_RATIO
    # and make it flake.
    scene[oil] = rng.normal(-32.0, 1.3, int(oil.sum())).astype(np.float32)
    med2, _ = median_reference(scene)
    ref2, _, info2 = sea_reference(scene)
    sea_true = float(np.median(scene[~oil]))
    print(f"  78% oil scene median {med2:7.2f} dB (in the slick), "
          f"sea_reference {ref2:7.2f} dB, true sea {sea_true:7.2f} dB")
    close = abs(ref2 - sea_true) < 0.5
    print(f"  sea_reference recovers the true sea within 0.5 dB  : {close}  "
          f"({info2['n_modes']} modes, cut {info2['cut_db']}, "
          f"{100*info2['frac_sea']:.1f}% sea)")
    ok &= close

    # 4. And the normalised slick depth must come back, which is the whole point.
    n_med, _, _, _ = normalise_band(scene, "median")
    n_sea, _, _, _ = normalise_band(scene, "sea")
    dep_med = float(n_med[oil].mean() - n_med[~oil].mean())
    dep_sea = float(n_sea[oil].mean() - n_sea[~oil].mean())
    print(f"  normalised oil-vs-sea separation  median {dep_med:+.3f} -> "
          f"sea {dep_sea:+.3f}   (want |sea| > |median|)")
    ok &= abs(dep_sea) > abs(dep_med)

    print(f"\n  [{'PASS' if ok else 'FAIL'}] normalise.py")
    return 0 if ok else 1


# ---------------------------------------------------------------------------
# Audit — the E2 safety gate, run over the real corpus before any rebuild
# ---------------------------------------------------------------------------

def _audit(limit=None):
    """Measure |sea_ref - median| across Parts I+II.

    GATE (plan E2): p99 of |shift| must be < 0.15 dB on the no-oil scenes, and the
    >=30%-coverage scenes must move by several dB. Passing means the estimator is
    safe for the 93% of scenes that already work, which is the entire risk of E2.
    """
    import rasterio
    from pipeline.detect.make_labels import _build_jobs

    man_p = os.path.join(_ROOT, "data", "cache", "manifest_P12.json")
    frac = {}
    if os.path.exists(man_p):
        m = json.load(open(man_p, encoding="utf-8"))
        rows = m.get("scenes", m) if isinstance(m, dict) else m
        if isinstance(rows, dict):
            rows = [dict(v, scene_id=k) for k, v in rows.items()]
        for r in rows:
            frac[r.get("scene_id") or r.get("scene")] = r.get("oil_frac", 0.0)

    jobs = _build_jobs("1,2")
    if limit:
        jobs = jobs[:limit]
    print(f"auditing {len(jobs)} Parts I+II scenes "
          f"(prominence={SEA_MIN_PROM}, min_sep={SEA_MIN_SEP_DB} dB, polish k={SEA_K})")

    def band_of(f):
        for lo, hi, lbl in ((0, .01, "0-1%"), (.01, .03, "1-3%"), (.03, .10, "3-10%"),
                            (.10, .30, "10-30%"), (.30, 1.01, ">=30%")):
            if lo <= f < hi:
                return lbl
        return "?"

    out = {}
    for i, (sid, cls, img, _msk) in enumerate(jobs, 1):
        try:
            with rasterio.open(img) as ds:
                # Band 2 is the CO-POL channel on Zenodo tiles (band 1 is VH — see
                # build_cache.scene_arrays). The co-pol channel is where the oil
                # signal lives, so it is the one whose reference matters.
                b = ds.read(2).astype(np.float32)
        except Exception:
            continue
        # Land OUT of the sample before anything is estimated — that is the fix the
        # first two audits forced. Both estimators see the same population, so the
        # shift measured below is purely the estimator's effect, not land's.
        v = valid_mask(b, exclude_land=True)
        if not v.any():
            continue
        med, _ = median_reference(b, v)
        ref, _, info = sea_reference(b, v)
        key = "no oil" if cls != "Oil" else band_of(frac.get(sid, 0.0))
        out.setdefault(key, []).append((abs(ref - med), info["n_modes"], info["frac_sea"]))
        if i % 250 == 0:
            print(f"  [{i}/{len(jobs)}]", flush=True)

    print(f"\n{'population':<12}{'n':>6}{'median |d|':>12}{'p99 |d|':>10}"
          f"{'max |d|':>10}{'modes':>7}{'sea%':>8}")
    print("-" * 65)
    order = ["no oil", "0-1%", "1-3%", "3-10%", "10-30%", ">=30%"]
    gate_ok = True
    for k in order:
        if k not in out:
            print(f"{k:<12}   ABSENT — gate cannot pass without it")
            gate_ok = False
            continue
        d = np.array([x[0] for x in out[k]])
        it = np.mean([x[1] for x in out[k]])
        kp = np.mean([x[2] for x in out[k]])
        print(f"{k:<12}{len(d):>6}{np.median(d):>12.3f}{np.percentile(d, 99):>10.3f}"
              f"{d.max():>10.3f}{it:>7.1f}{100*kp:>7.1f}%")
        if k in ("no oil", "0-1%", "1-3%", "3-10%"):
            # These are the 93% that already work. They must be left alone.
            gate_ok &= float(np.percentile(d, 99)) < 0.15
        if k == ">=30%":
            gate_ok &= float(np.median(d)) > 1.0

    print()
    print("GATE (plan E2):  p99 |shift| < 0.15 dB on every band up to 3-10% (the 93%")
    print("                 that already work must be untouched)  AND  >=30% median shift > 1.0 dB")
    print(f"GATE: {'PASS — safe to rebuild the cache' if gate_ok else 'FAIL — tune SEA_K before rebuilding'}")
    return 0 if gate_ok else 1


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--audit", action="store_true", help="run the E2 safety gate over Parts I+II")
    ap.add_argument("--limit", type=int, default=None)
    a = ap.parse_args()
    sys.exit(_audit(a.limit) if a.audit else _selftest())
