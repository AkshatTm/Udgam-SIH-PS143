#!/usr/bin/env python3
"""
Stage 2 age estimation. Owner: Anushka.   (docs/team/anushka-stage2-drift.md Part C, Phase 1)

    python pipeline/drift/age.py --case <id> --real
    python pipeline/drift/age.py --case case-000 --fake      # no GEE, for iteration

WHY THIS EXISTS
    `origin.json`'s time_window with method="bounded" is the rewind span minus eight hours.
    It is a BRACKET, not a measurement -- and the frontend renders it in large type labelled
    RELEASE WINDOW. A panel asking "how did you derive 00:14 to 16:14?" has no good answer
    today. This module is that answer.

    Age is also not decoration, it is a FILTER: bounding a slick at 6-18 h instead of 0-72
    shrinks Stage 3's suspect pool by roughly an order of magnitude and sharpens every score
    downstream.

WHAT DOES NOT WORK, AND WHY WE SAY SO  (Part C2)
    Reading age from radar brightness -- the damping ratio -- is the obvious approach, and it
    does not work here. Damping ratio primarily tracks oil THICKNESS rather than age; it
    DECREASES with wind speed, so wind is a confounder we cannot separate from age in a single
    image; and oil-sea contrast fails entirely below roughly 2-3 m/s and above roughly
    10-14 m/s wind. So it is a qualitative flag in this module -- fresh | weathered | unknown
    -- and NEVER hours. Stating why the obvious method fails belongs on the limitations slide.

THE THREE ESTIMATORS, IN ORDER OF STRENGTH
    1  shear dispersion   PRIMARY, and uniquely ours. Instead of a generic spreading law, ask
                          the real ocean: seed a tight cloud at the origin centroid, run it
                          FORWARD, and find the age whose modelled extent best matches the
                          observed slick. Captures the actual local shear and the actual
                          wind on that day -- two spills of identical age in different current
                          fields spread differently, and this estimator knows that.
                          CAVEAT, and it must be stated: this models ADVECTIVE and SHEAR
                          spreading only. It does not model gravity-viscous spreading, which
                          dominates the first hours after a fresh release, so for very young
                          slicks it OVERESTIMATES age.
    2  Fay spreading      Independent, generic, weaker. Gravity-viscous regime, r ~ t^(1/4).
                          Needs a volume estimate, so the thickness assumption is PUBLISHED
                          rather than buried, and the result is a band across the plausible
                          thickness range. Its value is being COMPLETELY INDEPENDENT of the
                          current field, so agreement with (1) means something real.
    3  elongation/shear   Cheap -- the observable is already free in the contract. GATED on
                          discharge_class == "acute", because a chronic discharge is elongated
                          by the ship's own motion, not by shear, and applying this there
                          gives nonsense.

COMBINING  (Part C4)
    Bands overlap     -> INTERSECTION, method="combined"
    Bands disagree    -> UNION, method="disagreement", and the UI says so
    Nothing fires     -> method="none", fall back to the bounded window, labelled a bracket
    Widening an honest band beats narrowing an invented one, and almost nobody does it.

OUTPUT
    Patches the four contract-blessed keys into <out>/origin.json (Master §6.5):
        age_hours, age_method, age_weathering, age_estimators
    Full diagnostics -- every candidate, every member, every skip reason -- go to
    <out>/age_<case>.json, which is WORKING SPACE and never travels in the case bundle.
    No key outside the frozen contract is written into origin.json.
"""
import argparse
import json
import math
import sys
from datetime import timedelta
from pathlib import Path

import numpy as np

import ensemble as ens
from fields import load_case_field, make_fake, require_aware, speed
from step import as_positions, deg_to_m, integrate

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
OUT = HERE / "out"

KM_PER_DEG_LAT = 111.32

# ---------------------------------------------------------------------------------------
# Physical constants.
#
# Every one of these is an ASSUMPTION with a range, not a measurement, and each is printed
# in the report so the number it produces can be argued with rather than trusted.
# ---------------------------------------------------------------------------------------

G = 9.81                      # m/s^2
NU_WATER = 1.0e-6             # kinematic viscosity of seawater, m^2/s
RHO_WATER = 1025.0            # kg/m^3
RHO_OIL_RANGE = (850.0, 950.0)   # crude; a light product or an emulsion sits outside this

# Fay's gravity-viscous constant, radius form:  r(t) = k * (dg V^2 / sqrt(nu))^(1/6) * t^(1/4)
#
# UNCITED, BY RULING (A4, 13 Sept 2026). The brief asked for a primary citation before quoting
# this. Akshat's ruling is that it is not needed, because of what the exponent does: Fay's AREA
# goes as k^2, so closing the measured ~14x gap between what spreading can reach and what SAR
# actually sees would need k ~ 5.5 against a literature range of 1.1-1.5. The regime verdict is
# robust to k; a Fay age band would not be. A3 means we never quote a Fay-derived number, so the
# band never ships and the constant never has to carry a citation. Quote a Fay AGE and the
# citation becomes mandatory again.
FAY_K_RANGE = (1.1, 1.5)

# There is deliberately NO thickness range here any more, and that is the fix for a
# circularity in the brief. C3.2 says to get the volume from `area_km2` x a thickness class --
# but then V = A*h is substituted into r = k (dg V^2 / sqrt(nu))^(1/6) t^(1/4), where r is
# itself sqrt(A/pi). The observed area appears on BOTH sides: the law becomes r ~ r^(2/3)
# t^(1/4), i.e. r ~ t^(3/4), which is not the gravity-viscous law being advertised, and the
# inversion is wildly sensitive to a thickness nobody measured.
#
# So Fay needs a volume from an INDEPENDENT source -- the reported release volume in the
# official finding (Huntington: 588 barrels = ~93.5 m3, NTSB MIR-24-01). Passed in with
# --volume-m3. With no volume, this estimator refuses rather than doing the circular thing.

# Reference age used when reporting what Fay CAN account for, in hours.
FAY_REFERENCE_HOURS = 24.0

# Damping-ratio / oil-sea contrast is only meaningful in this wind band (C3.4).
WEATHERING_WIND_LO_MS = 3.0
WEATHERING_WIND_HI_MS = 10.0

# Shear-dispersion seeding: a tight cloud, because we are measuring how the ocean spreads it,
# not how wide we made it.
SEED_SIGMA_M = 200.0
SEED_PARTICLES = 300


# ---------------------------------------------------------------------------------------
# Geometry helpers
# ---------------------------------------------------------------------------------------

def equivalent_radius_km(area_km2):
    """Radius of the circle with the same area. The scalar that lets a modelled cloud and a
    detected polygon be compared at all."""
    return math.sqrt(max(float(area_km2), 0.0) / math.pi)


def observed_major_axis_km(area_km2, elongation):
    """Full major-axis length of the ELLIPSE with this area and this aspect ratio.

    area = pi*a*b and elongation = a/b  ->  a = sqrt(area * elongation / pi),  length = 2a.

    THIS, not area, is what the shear estimator matches against. See the note in
    shear_dispersion_age(): a 2D incompressible flow preserves a cloud's area, so area carries
    no age signal in this model, while the major axis grows.

    FALLBACK ONLY -- prefer polygon_major_axis_km() when the polygon is available. The ellipse
    assumption fails badly on a real slick, and measurably so on the hero case. Jacksonville's
    det-01 reports area 4.479 km2 and elongation 7.93, which gives 6.72 km here; its polygon's
    actual principal-axis extent is 17.38 km. A factor of 2.6, because a sinuous filament at
    solidity 0.22 is not an ellipse: dividing area by the measured length gives a mean width of
    258 m, so the true filament aspect is about 67, not 7.93. Feeding 6.72 km to an estimator
    whose whole job is to match a length would have dated the wrong slick.
    """
    if area_km2 is None or elongation is None:
        return None
    e = max(float(elongation), 1.0)
    a = math.sqrt(max(float(area_km2), 0.0) * e / math.pi)
    return 2.0 * a


def polygon_major_axis_km(ring):
    """MEASURED major-axis length of a detection polygon, in km, by PCA on its vertices.

    The preferred input to C3.1. A1 ruled that the shear estimator matches the observed major
    axis rather than the area; this measures that axis from the geometry Soumirya actually ships
    instead of inferring it from two scalars under an ellipse assumption that the shape does not
    satisfy (see observed_major_axis_km for the numbers).

    Projects [lon, lat] to km with cos(lat) taken at the ring's own mean latitude -- the same
    convention as step.displacement_km -- then returns the peak-to-peak extent along the first
    principal component. Peak-to-peak, not a standard deviation, because the quantity being
    matched is a physical end-to-end length.

    Returns (length_km, diag). `diag` carries the minor extent, the area-derived mean width and
    the implied filament aspect, so a caller can see how far from an ellipse the shape is rather
    than having to trust that it is one.
    """
    pts = np.asarray(ring, dtype=np.float64)
    if pts.ndim != 2 or pts.shape[0] < 3:
        return None, {"skipped": f"need at least 3 vertices, got {pts.shape}"}
    if pts.shape[1] > 2:
        pts = pts[:, :2]

    # DROP THE CLOSING VERTEX. A GeoJSON ring repeats its first point to close the polygon
    # (RFC 7946 3.1.6), and PCA weights vertices, so that duplicate counts one corner twice
    # and drags the centroid off the shape's centre -- which ROTATES the principal axis. On a
    # 10 x 1 km rectangle it read 10.015 x 1.168 km instead of 10.000 x 1.000: a 17% error on
    # the width and a tilted axis, from one repeated point. Every real ring has one.
    closed = pts.shape[0] > 3 and np.allclose(pts[0], pts[-1])
    if closed:
        pts = pts[:-1]

    lat0 = float(np.mean(pts[:, 1]))
    coslat = max(math.cos(math.radians(lat0)), 1e-9)
    xy = np.column_stack([pts[:, 0] * coslat * KM_PER_DEG_LAT, pts[:, 1] * KM_PER_DEG_LAT])
    centred = xy - xy.mean(axis=0)
    try:
        _, _, vt = np.linalg.svd(centred, full_matrices=False)
    except np.linalg.LinAlgError as exc:
        return None, {"skipped": f"SVD failed on the ring: {exc}"}
    major = centred @ vt[0]
    minor = centred @ vt[1]
    length = float(major.max() - major.min())
    width = float(minor.max() - minor.min())
    return length, {
        "measured_on": "polygon PCA (peak-to-peak along the principal axis)",
        "length_km": round(length, 4),
        "bbox_width_km": round(width, 4),
        "bbox_aspect": round(length / width, 2) if width > 0 else None,
        "mean_lat": round(lat0, 5),
        "n_vertices": int(pts.shape[0]),
        "closing_vertex_dropped": bool(closed),
    }


def slick_major_axis_km(feature):
    """(length_km, diag) for one detection feature -- MEASURED if possible, derived if not.

    One place decides, so a caller cannot accidentally take the ellipse path when the polygon is
    right there. The diag always says which route was taken and, when both are available, what
    the ellipse form would have said -- the discrepancy is a property of the slick's shape and
    belongs in the output rather than in a comment.
    """
    props = (feature or {}).get("properties") or {}
    geom = (feature or {}).get("geometry") or {}
    coords = geom.get("coordinates")
    # EVERY part, not just the first. A merged slick is a MultiPolygon, and taking
    # coordinates[0][0] would have measured 15 km of Jacksonville's 34 km ribbon -- a number
    # that looks entirely reasonable and is wrong by more than half.
    ring = None
    if geom.get("type") == "Polygon" and coords:
        ring = coords[0]
    elif geom.get("type") == "MultiPolygon" and coords:
        rings = [np.asarray(part[0], dtype=np.float64) for part in coords if part]
        if rings:
            ring = np.vstack(rings)

    derived = observed_major_axis_km(props.get("area_km2"), props.get("elongation"))
    if ring is None:
        return derived, {"route": "ellipse (no polygon available)",
                         "derived_km": derived if derived is None else round(derived, 4)}

    measured, diag = polygon_major_axis_km(ring)
    if measured is None:
        return derived, {"route": "ellipse (polygon unusable)", **diag,
                         "derived_km": derived if derived is None else round(derived, 4)}

    diag["route"] = "measured from polygon"
    area = props.get("area_km2")
    if area and measured > 0:
        mean_width_km = float(area) / measured
        diag["mean_width_m"] = round(mean_width_km * 1000.0, 1)
        diag["filament_aspect"] = round(measured / mean_width_km, 2) if mean_width_km > 0 else None
    if derived is not None:
        diag["derived_km"] = round(derived, 4)
        diag["measured_over_derived"] = round(measured / derived, 3) if derived > 0 else None
        diag["reported_elongation"] = props.get("elongation")
    return measured, diag


def pca_extent(pos):
    """(sd_major_km, sd_minor_km, area_km2) for a particle cloud.

    Principal-axis standard deviations, because a real drift cloud is a streak, not a disc --
    the Ennore control cloud runs 4.38:1. `area_km2` is the area of the 2-sigma ellipse,
    pi * (2*sd1) * (2*sd2), which holds about 86% of a gaussian cloud's particles.

    THE COMPARABILITY CAVEAT, and it is a real source of bias: Soumirya's `area_km2` is the area
    of a thresholded dark polygon -- where oil is optically thick enough to damp waves --
    while this is the area of a particle spread envelope. They are not the same quantity.
    A 2-sigma ellipse is the closest honest match, and the direction of the residual bias
    (SAR sees less than the model spreads) means shear ages skew HIGH, on top of the
    gravity-viscous caveat that already does.
    """
    p = as_positions(pos)
    clon, clat = float(p[:, 0].mean()), float(p[:, 1].mean())
    dx, dy = deg_to_m(p[:, 0] - clon, p[:, 1] - clat, p[:, 1])
    xy = np.column_stack([dx, dy]) / 1000.0
    if xy.shape[0] < 3:
        return 0.0, 0.0, 0.0
    cov = np.cov(xy, rowvar=False)
    evals = np.linalg.eigvalsh(cov)              # ascending, real, symmetric matrix
    sd_minor = float(math.sqrt(max(evals[0], 0.0)))
    sd_major = float(math.sqrt(max(evals[1], 0.0)))
    return sd_major, sd_minor, float(math.pi * (2.0 * sd_major) * (2.0 * sd_minor))


def seed_cloud(lon, lat, n=SEED_PARTICLES, sigma_m=SEED_SIGMA_M, rng=None):
    """A tight gaussian point cloud, sigma in metres, converted at this latitude."""
    rng = rng if rng is not None else np.random.default_rng(143)
    sig_lat = (sigma_m / 1000.0) / KM_PER_DEG_LAT
    coslat = max(math.cos(math.radians(lat)), 1e-6)
    return np.column_stack([lon + rng.normal(0.0, sig_lat / coslat, n),
                            lat + rng.normal(0.0, sig_lat, n)])


def deformation_rate_s(field, lon, lat, when, dx_km=4.5):
    """Total 2D deformation (strain) rate of the current field at a point, in 1/s.

        S = sqrt( (du/dx - dv/dy)^2 + (dv/dx + du/dy)^2 )

    i.e. sqrt(stretching^2 + shearing^2), the standard rate-of-strain magnitude. A finite
    difference on the cached grid; `dx_km` defaults to half a HYCOM cell (9 km), because a
    stencil finer than the data is measuring the interpolator, not the ocean.

    Note this is the CURRENT field only. Wind shear is not in it: the 3% factor is uniform in
    our model, so wind adds translation, not stretching, and including it would be inventing
    structure the model does not have.
    """
    require_aware(when)
    dlat = dx_km / KM_PER_DEG_LAT
    dlon = dlat / max(math.cos(math.radians(lat)), 1e-6)

    lons = np.array([lon - dlon, lon + dlon, lon, lon], dtype=np.float64)
    lats = np.array([lat, lat, lat - dlat, lat + dlat], dtype=np.float64)
    u, v = field.get_uv(lons, lats, when)
    u = np.asarray(u, dtype=np.float64)
    v = np.asarray(v, dtype=np.float64)

    two_dx_m = 2.0 * dx_km * 1000.0
    du_dx = (u[1] - u[0]) / two_dx_m
    dv_dx = (v[1] - v[0]) / two_dx_m
    du_dy = (u[3] - u[2]) / two_dx_m
    dv_dy = (v[3] - v[2]) / two_dx_m

    stretching = du_dx - dv_dy
    shearing = dv_dx + du_dy
    return float(math.hypot(stretching, shearing))


def field_time_coverage(case_id, repo_root=None):
    """(current_start, current_end, wind_start, wind_end) of the cached field, as UTC datetimes.

    THE LOUD GUARD THIS EXISTS FOR: fetch_fields.py pulls detection_time - 30 h, but HYCOM is
    DAILY, so a 30 h request lands only two snapshots and the real current coverage is about
    24 h. The brief's C3.1 candidate grid runs to 36 h. Candidates past the last snapshot are
    not modelled, they are CLAMPED to the edge snapshot -- the field silently stops varying,
    the extent curve flattens and then falls, and the monotonicity check fails for a reason
    that has nothing to do with the ocean.

    Same failure family as a particle finishing against the field-box wall (Phase 3.1): the
    number stays plausible while the physics quietly stops. So it fails loudly instead.
    """
    from datetime import datetime, timezone

    root = Path(repo_root) if repo_root else REPO
    path = root / "data" / "fields" / f"{case_id}.npz"
    if not path.exists():
        return None
    z = np.load(path, allow_pickle=False)

    def span(key):
        t = np.asarray(z[key], dtype=np.int64)
        return (datetime.fromtimestamp(int(t.min()), tz=timezone.utc),
                datetime.fromtimestamp(int(t.max()), tz=timezone.utc))

    c0, c1 = span("current_times")
    w0, w1 = span("wind_times")
    return c0, c1, w0, w1


def clip_candidates_to_coverage(candidate_hours, t0, coverage):
    """Drop candidates whose start time falls before the cached field begins.

    Returns (kept, dropped, detail). Refusing to run them is right: an extrapolated candidate
    produces a real-looking number from a field that has stopped moving.
    """
    if coverage is None:
        return list(candidate_hours), [], "no cached field to check (analytic run)"
    c0, c1, w0, w1 = coverage
    earliest = max(c0, w0)                      # both must cover it
    max_h = (t0 - earliest).total_seconds() / 3600.0
    kept = [h for h in candidate_hours if h <= max_h]
    dropped = [h for h in candidate_hours if h > max_h]
    detail = (f"cached field covers currents {c0:%Y-%m-%dT%H:%MZ}..{c1:%Y-%m-%dT%H:%MZ} "
              f"and winds {w0:%Y-%m-%dT%H:%MZ}..{w1:%Y-%m-%dT%H:%MZ}, so the furthest "
              f"honest candidate is {max_h:.1f} h before t0")
    return kept, dropped, detail


def mean_wind_ms(field, lon, lat, when):
    """Scalar 10 m wind speed at a point. Reported alongside every weathering flag, because
    the flag is meaningless without it."""
    require_aware(when)
    wu, wv = field.get_wind(np.array([lon]), np.array([lat]), when)
    return float(speed(wu, wv)[0])


# ---------------------------------------------------------------------------------------
# C3.1  shear dispersion -- the primary estimator
# ---------------------------------------------------------------------------------------

def shear_extent_curve(field, lon, lat, t0, candidate_hours, timestep_minutes=15,
                       n_particles=SEED_PARTICLES, rng=None, guard=True):
    """Modelled slick area at t0 for each candidate age.

    For a candidate age t, the cloud must be released at t0 - t and observed AT t0. So each
    candidate is its own forward run from its own start time -- one long run recorded at
    intervals would answer a different question (released at t0 - max, observed early), and
    over a 36 h window through a daily field the two are not interchangeable.

    Returns (areas_km2, sd_major_km, sd_minor_km), one entry per candidate.
    """
    rng = rng if rng is not None else np.random.default_rng(143)
    areas, majors, minors = [], [], []

    # ONE cloud realisation, reused for every candidate. Drawing a fresh cloud per candidate
    # makes adjacent candidates differ by sampling noise as well as by elapsed time, and in a
    # weakly-sheared field the noise is LARGER than the growth -- which shows up as a
    # non-monotonic curve and gets the whole estimator (correctly) refused. The candidates must
    # differ only in how long the ocean had to work on the same blob.
    start0 = seed_cloud(lon, lat, n_particles, rng=rng)

    for t_h in candidate_hours:
        n_steps = int(round(t_h * 60.0 / timestep_minutes)) + 1     # stored positions
        history, _ = integrate(start0, t0 - timedelta(hours=float(t_h)), field,
                               n_steps, timestep_minutes, direction="forward", guard=guard)
        sd1, sd2, area = pca_extent(history[-1])
        areas.append(area)
        majors.append(sd1)
        minors.append(sd2)

    return np.asarray(areas), np.asarray(majors), np.asarray(minors)


def check_monotonic(candidate_hours, areas, tol_frac=0.02):
    """The sanity gate from C3.1: modelled extent MUST increase with candidate age.

    If it does not, the field or the seeding is wrong -- stop and look, do not tune. A small
    tolerance absorbs sampling noise from a finite particle cloud; a real violation is a
    field that is squeezing the cloud, which over a 24-36 h rewind through daily HYCOM should
    not happen (the cloud translates, it does not converge -- that is the same structural
    reason the convergence time-window estimator failed).

    Returns (ok, first_offending_index_or_None, detail).
    """
    a = np.asarray(areas, dtype=np.float64)
    for i in range(1, a.size):
        if a[i] < a[i - 1] * (1.0 - tol_frac):
            return False, i, (f"modelled area fell from {a[i-1]:.3f} km2 at "
                              f"{candidate_hours[i-1]:g} h to {a[i]:.3f} km2 at "
                              f"{candidate_hours[i]:g} h")
    return True, None, (f"area grows {a[0]:.3f} -> {a[-1]:.3f} km2 across "
                        f"{candidate_hours[0]:g}-{candidate_hours[-1]:g} h")


def invert_curve(candidate_hours, values, target):
    """Age at which a monotonically increasing curve crosses `target`, linearly interpolated.

    Returns None when the target lies outside the modelled range -- which is information, not
    failure: below the first candidate means the slick is younger than the grid resolves,
    above the last means older than the rewind we ran.
    """
    h = np.asarray(candidate_hours, dtype=np.float64)
    v = np.asarray(values, dtype=np.float64)
    target = float(target)

    if target <= v[0] or target >= v[-1]:
        return None
    i = int(np.searchsorted(v, target))
    i = max(1, min(i, v.size - 1))
    v_lo, v_hi = v[i - 1], v[i]
    if v_hi <= v_lo:
        return float(h[i])
    frac = (target - v_lo) / (v_hi - v_lo)
    return float(h[i - 1] + frac * (h[i] - h[i - 1]))



def _gate_reason(discharge_class, estimator, physics):
    """Why an acute-gated estimator declined -- and WHOSE problem it is.

    Two very different situations produce the same refusal, and conflating them hides a blocker:

      chronic          a real physical reason. The gate is doing its job and nothing is missing.
      unknown/absent   a MISSING INPUT. Stage 1 has not emitted discharge_class -- it is in the
                       contract and assigned to Soumirya, but detect/run.py has never written it, so
                       it will not appear just because his backlog clears. Akshat's A5 audit
                       (13 Sept 2026) found it unset on EVERY case including case-000's own
                       det-01, which is why both acute-gated estimators currently fire on
                       nothing. That is a data gap, not a property of any slick.
    """
    if discharge_class == "chronic":
        return (f"discharge_class is 'chronic'. {estimator} {physics}, so the result would be "
                f"meaningless. The gate is correct and nothing is missing.")
    return (f"discharge_class is {discharge_class!r}. {estimator} {physics}, so it needs to "
            f"know whether the source was moving before it can run, and 'unknown' does not say. "
            f"This is NOT a missing field -- Stage 1 emits it (detect/run.py:551 via "
            f"ships.classify_discharge). It is computed from SHAPE ALONE: elongation < 3.0 -> "
            f"'acute', elongation >= 5.0 AND straightness >= 0.60 -> 'chronic', everything "
            f"between -> 'unknown'. So 'unknown' means the detector could not place this slick "
            f"in either bucket, which is a real statement about the geometry rather than a gap "
            f"in the contract. Two consequences worth knowing: NO oil detection in the library "
            f"is 'acute' (0 of 13), because acute requires LOW elongation and oil slicks are "
            f"elongated -- so this estimator fires on nothing, structurally, and A5's conclusion "
            f"stands for a stronger reason than it was originally given. And because the gate is "
            f"a threshold on elongation while C3.3 INVERTS elongation, the gate and the "
            f"estimator read the same quantity -- flagged to Akshat 13 Sept as circular.")


def shear_dispersion_age(base_field, lon, lat, t0, observed_length_km, candidate_hours,
                         timestep_minutes=15, n_particles=SEED_PARTICLES, n_members=20,
                         seed=143, guard=True, discharge_class=None):
    """C3.1. Returns (band_or_None, diagnostics).

    !! GATED ON discharge_class == "acute", FOR THE SAME REASON C3.3 IS. !!

    The brief gates only C3.3 on acute, because it reads age off the observed elongation. But this
    estimator matches the observed MAJOR AXIS (see the next note), and on a chronic discharge the
    major axis is the VESSEL'S TRACK, not the ocean stretching a patch. `case-jacksonville-2024`
    is the worked example: a 31.17 km ribbon of 4.55 km2, an aspect ratio near 170 and a width of
    about 190 m. No plausible ocean turns an 800 m blob into a 31 km thread in 36 h; the ship did
    that, at transit speed. Run this on a chronic slick and it either refuses for the wrong reason
    or, in a strongly sheared field, returns a confident wrong number.

    So `acute` only, and the skip reason is recorded.

    For the record, because it is the obvious next question: the physically right observable on a
    chronic ribbon is its WIDTH, not its length -- cross-track spreading really is the ocean's
    work, and the minor axis is derivable from the contract as sqrt(area / (pi * elongation)).
    It is NOT implemented here, deliberately, for two reasons. The initial width is the vessel's
    wake, which nobody measured and which would dominate the answer exactly as the thickness
    assumption dominates Fay. And cross-track spreading at these scales is largely turbulent
    diffusion, which this model does not carry at all (F8). Both would have to be invented. If a
    chronic age matters for the demo, that is a conversation with Akshat, not a quiet default.

    !! MATCHES ON MAJOR-AXIS LENGTH, NOT AREA. The brief says area; area cannot work here. !!

    A 2D incompressible flow preserves the area of a material patch: whatever it stretches in
    one direction it thins in the other, so det F = 1 and the cloud's ellipse area is constant.
    HYCOM's surface field is close to divergence-free, and our wind term is a uniform 3% that
    adds translation rather than stretching -- so a cloud advected by this model becomes a
    longer, thinner filament of ROUGHLY CONSTANT AREA. Matching modelled area against Soumirya's
    observed `area_km2` therefore has no age signal to find: the curve is flat, the inversion
    is noise, and `check_monotonic` would (correctly) refuse it.

    This is the same structural failure as the convergence time-window estimator, and it has
    the same cause: a smooth field advects and stretches, it does not squeeze or inflate.
    Real slicks DO grow in area, but by gravity-viscous spreading and turbulent diffusion --
    physics this model deliberately excludes (F8). We cannot read an age off a growth process
    we do not model.

    What the model does produce, robustly and monotonically, is FILAMENT LENGTH. So the
    observable becomes the major axis, derived from the contract as
    sqrt(area_km2 * elongation / pi) * 2 -- both quantities Soumirya already exports. Area is still
    computed and reported per candidate, as a check that the field is behaving as expected: if
    modelled area grows or shrinks materially across the candidates, the field has real
    divergence in it and that is worth knowing.

    Repeated across perturbed ensemble members -- the same stratified wind coefficient and
    current scale draws the origin cloud uses -- so the answer is a BAND from the same
    uncertainty budget as the rest of Stage 2, not a point dressed up with error bars.
    """
    if discharge_class != "acute":
        return None, {
            "matched_on": "major_axis_length_km",
            "discharge_class": discharge_class,
            "skipped": _gate_reason(discharge_class, "C3.1",
                                    "matches the observed major axis, and on a chronic slick "
                                    "the major axis is the vessel's track rather than shear "
                                    "stretching a patch"),
        }

    rng = np.random.default_rng(seed)
    winds, scales = ens._stratified_draws(n_members, rng)

    fits, members, mono_failures = [], [], []
    for m in range(n_members):
        wind_coeff = float(winds[m])
        scale = max(float(scales[m]), 0.05)
        field = ens.PerturbedField(base_field, scale)

        # The perturbed wind coefficient enters through the INTEGRATOR, not the field object,
        # so it has to be passed where the trajectory is computed. shear_extent_curve() uses
        # the module default and would silently drop this member's wind draw -- which would
        # make the band narrower than the uncertainty budget actually is.
        areas_w, sd1_w, sd2_w = _curve_with_wind(
            field, lon, lat, t0, candidate_hours, timestep_minutes, n_particles,
            wind_coeff=wind_coeff, seed=seed + 2000 + m, guard=guard)

        lengths_w = 4.0 * sd1_w          # full major axis of the 2-sigma ellipse
        ok, idx, detail = check_monotonic(candidate_hours, lengths_w)
        if not ok:
            mono_failures.append({"member": m, "detail": detail})

        t_fit = invert_curve(candidate_hours, lengths_w, observed_length_km)
        members.append({
            "member": m, "wind_coeff": wind_coeff, "current_scale": scale,
            "age_hours": t_fit, "monotonic": bool(ok),
            "length_first_km": float(lengths_w[0]), "length_last_km": float(lengths_w[-1]),
            # area is the diagnostic, not the observable: near-constant is the expected,
            # correct behaviour for a divergence-free field.
            "area_first_km2": float(areas_w[0]), "area_last_km2": float(areas_w[-1]),
            "area_ratio": float(areas_w[-1] / areas_w[0]) if areas_w[0] > 0 else None,
        })
        if t_fit is not None:
            fits.append(t_fit)

    area_ratios = [m["area_ratio"] for m in members if m["area_ratio"]]
    diag = {
        "n_members": n_members,
        "n_fitted": len(fits),
        "matched_on": "major_axis_length_km",
        "candidate_hours": [float(h) for h in candidate_hours],
        "observed_length_km": float(observed_length_km),
        "monotonicity_failures": mono_failures,
        "median_area_ratio_first_to_last": (float(np.median(area_ratios))
                                            if area_ratios else None),
        "members": members,
        "caveat": ("advective and shear spreading only -- no gravity-viscous phase, so this "
                   "OVERESTIMATES the age of a very young slick. Report as a lower-bounded "
                   "band."),
        "why_not_area": ("a 2D incompressible field preserves cloud area, so area carries no "
                         "age signal in this model; the major axis does. See the docstring."),
    }

    if len(fits) < max(3, n_members // 4):
        diag["skipped"] = (f"only {len(fits)}/{n_members} members bracketed the observed major "
                           f"axis {observed_length_km:.2f} km -- the slick is outside the "
                           f"modelled stretch range, so there is no band to report")
        return None, diag
    if mono_failures:
        diag["skipped"] = (f"{len(mono_failures)}/{n_members} members produced a "
                           f"NON-MONOTONIC extent curve. C3.1 says stop and look, do not "
                           f"tune -- the field or the seeding is wrong.")
        return None, diag

    lo = float(np.percentile(fits, 10))
    hi = float(np.percentile(fits, 90))
    return (lo, hi), diag


def _curve_with_wind(field, lon, lat, t0, candidate_hours, timestep_minutes, n_particles,
                     wind_coeff, seed, guard=True):
    """shear_extent_curve() with an explicit wind coefficient. Split out because the ensemble
    perturbs the wind coefficient at the integrator, not inside the field object."""
    rng = np.random.default_rng(seed)
    areas, majors, minors = [], [], []
    start0 = seed_cloud(lon, lat, n_particles, rng=rng)   # one realisation, see above
    for t_h in candidate_hours:
        n_steps = int(round(t_h * 60.0 / timestep_minutes)) + 1
        history, _ = integrate(start0, t0 - timedelta(hours=float(t_h)), field, n_steps,
                               timestep_minutes, direction="forward",
                               wind_coeff=wind_coeff, guard=guard)
        sd1, sd2, area = pca_extent(history[-1])
        areas.append(area)
        majors.append(sd1)
        minors.append(sd2)
    return np.asarray(areas), np.asarray(majors), np.asarray(minors)


# ---------------------------------------------------------------------------------------
# C3.2  Fay gravity-viscous spreading -- independent of the current field
# ---------------------------------------------------------------------------------------

def fay_radius_km(t_hours, volume_m3, k, rho_oil):
    """r(t) = k * (delta g V^2 / sqrt(nu))^(1/6) * t^(1/4), in km.

    The gravity-viscous phase: the longest-lived of Fay's three regimes and the one that
    dominates at our timescales. r ~ t^(1/4), so AREA ~ t^(1/2).
    """
    delta = (RHO_WATER - float(rho_oil)) / RHO_WATER
    if delta <= 0 or volume_m3 <= 0 or t_hours <= 0:
        return 0.0
    c = (delta * G * volume_m3 ** 2 / math.sqrt(NU_WATER)) ** (1.0 / 6.0)
    return float(k) * c * (float(t_hours) * 3600.0) ** 0.25 / 1000.0


def fay_predicted_area_km2(t_hours, volume_m3, k, rho_oil):
    """Area a slick of this volume would have at this age FROM SPREADING ALONE."""
    r = fay_radius_km(t_hours, volume_m3, k, rho_oil)
    return math.pi * r * r


def fay_age(observed_area_km2, volume_m3=None, k_range=FAY_K_RANGE,
            rho_oil_range=RHO_OIL_RANGE, max_hours=72.0,
            reference_hours=FAY_REFERENCE_HOURS):
    """C3.2. Returns (band_or_None, diagnostics).

    !! TWO DEPARTURES FROM THE BRIEF, BOTH FORCED BY THE PHYSICS. !!

    1. THE VOLUME CANNOT COME FROM THE OBSERVED AREA. C3.2 says to estimate volume as
       `area_km2 x a thickness class`, but the observed area is what we are trying to explain,
       so it appears on both sides of the law and the inversion collapses (see the note where
       THICKNESS_RANGE_M used to be). Volume must come from the official finding -- a reported
       barrel figure -- or this estimator declines.

    2. AT SAR SCALE, FAY DOES NOT REACH THE OBSERVED AREA AT ANY PLAUSIBLE AGE, so it is
       usually a REGIME TEST rather than an age estimator. A 93 m3 release (Huntington's 588
       barrels) spreads to roughly half a square kilometre in 24 h by gravity-viscous
       spreading. The slicks we detect are several to tens of square kilometres. The area we
       observe is therefore set by SHEAR AND ADVECTION, not by spreading -- an order of
       magnitude or more of it. The ratio is measured and reported per case rather than
       asserted here.

       That is not a disappointment, it is the strongest thing this estimator produces: it is
       independent evidence that C3.1 is modelling the right process, and it belongs on the
       limitations slide next to the damping-ratio argument. What it must NOT do is get unioned
       into `age_hours` as a 400-hour band and destroy an honest answer -- so when Fay cannot
       account for the area within `max_hours`, it returns None and records the verdict.

    When the slick IS small enough for gravity-viscous spreading to explain it -- a fresh,
    modest release imaged early -- the inversion is legitimate and a band is returned across
    the k and density ranges.
    """
    r_obs_km = equivalent_radius_km(observed_area_km2)
    diag = {
        "observed_area_km2": float(observed_area_km2),
        "equivalent_radius_km": r_obs_km,
        "volume_m3": None if volume_m3 is None else float(volume_m3),
        "assumptions": {
            "fay_k_range": list(k_range),
            "rho_oil_range_kgm3": list(rho_oil_range),
            "rho_water_kgm3": RHO_WATER,
            "nu_water_m2s": NU_WATER,
        },
        "k_citation": (
            "SHIPS UNCITED, and that is a ruling not an oversight (A4, Akshat 13 Sept 2026). "
            "Fay's AREA goes as k^2, so closing an area gap of factor F needs k scaled by "
            "sqrt(F). On Huntington -- the only case with an independently published volume -- "
            "the MEASURED gap is 3x (0.880 km2 reachable against a 2.64 km2 detection), which "
            "would need k ~ 2.25 against a literature range of 1.1-1.5: outside it, but only by "
            "about 50%. The REGIME VERDICT therefore still holds, and it holds with LESS room "
            "than an earlier draft of this message claimed. That draft said 14x and k ~ 5.5, "
            "computed against an ASSUMED 12 km2 slick before any real detection existed; the "
            "real one is 2.64 km2. Quote the measured 3x, never the 14x. A Fay age BAND would "
            "not survive this, which is why A3 means we quote no Fay-derived number and the "
            "constant never has to carry a citation -- quote a Fay age and it becomes mandatory."),
    }

    if volume_m3 is None or float(volume_m3) <= 0:
        diag["skipped"] = (
            "no independently reported release volume. Deriving V from area_km2 x a thickness "
            "class -- as the brief suggests -- is circular, because the observed area then "
            "appears on both sides of the spreading law. Pass --volume-m3 from the official "
            "finding (e.g. Huntington: 588 barrels = 93.5 m3, NTSB MIR-24-01).")
        return None, diag

    volume = float(volume_m3)

    # What can spreading alone account for?
    ref_areas = {f"k={k},rho={rho}": fay_predicted_area_km2(reference_hours, volume, k, rho)
                 for k in k_range for rho in rho_oil_range}
    max_area_at_ceiling = max(fay_predicted_area_km2(max_hours, volume, k, rho)
                              for k in k_range for rho in rho_oil_range)
    diag["predicted_area_km2_at_reference"] = {kk: round(v, 4) for kk, v in ref_areas.items()}
    diag["reference_hours"] = reference_hours
    diag["max_predicted_area_km2_at_ceiling"] = max_area_at_ceiling

    if float(observed_area_km2) > max_area_at_ceiling:
        ratio = float(observed_area_km2) / max_area_at_ceiling if max_area_at_ceiling else None
        diag["regime"] = "shear_dominated"
        diag["skipped"] = (
            f"gravity-viscous spreading of {volume:.1f} m3 reaches at most "
            f"{max_area_at_ceiling:.3f} km2 even at the {max_hours:.0f} h ceiling, but the "
            f"observed slick is {float(observed_area_km2):.2f} km2 -- "
            f"{ratio:.0f}x larger. Fay cannot account for this area at any age we model, so "
            f"there is no Fay age to report. The area is set by shear and advection, which is "
            f"independent evidence that the shear estimator is modelling the right process.")
        return None, diag

    diag["regime"] = "gravity_viscous"
    corners, ages = [], []
    for k in k_range:
        for rho in rho_oil_range:
            delta = (RHO_WATER - rho) / RHO_WATER
            c = (delta * G * volume ** 2 / math.sqrt(NU_WATER)) ** (1.0 / 6.0)
            if c <= 0:
                continue
            # r = k*c*t^(1/4)/1000  ->  t = (1000*r/(k*c))^4 seconds
            t_h = (1000.0 * r_obs_km / (k * c)) ** 4 / 3600.0
            corners.append({"k": k, "rho_oil": rho, "age_hours": t_h})
            ages.append(t_h)
    diag["corners"] = corners

    if not ages:
        diag["skipped"] = "no valid assumption corner -- check densities"
        return None, diag

    lo, hi = float(min(ages)), float(max(ages))
    if hi > max_hours:
        diag["note"] = (f"upper corner reached {hi:.1f} h, past the {max_hours:.0f} h ceiling "
                        f"where weathering and Fay's later regimes take over -- clipped")
        hi = max_hours
    if lo >= hi:
        diag["skipped"] = f"degenerate band [{lo:.2f}, {hi:.2f}]"
        return None, diag
    return (lo, hi), diag


# ---------------------------------------------------------------------------------------
# C3.3  elongation under shear -- gated on discharge_class
# ---------------------------------------------------------------------------------------

def elongation_age(observed_elongation, shear_rate_s, discharge_class,
                   band_frac=0.35, max_hours=72.0):
    """C3.3. Returns (band_or_None, diagnostics).

    !! THIS DEPARTS FROM THE FORMULA IN THE BRIEF, DELIBERATELY. Read this before quoting it. !!

    docs/team/anushka-stage2-drift.md C3.3 gives `aspect(t) = sqrt(1 + (S t)^2)`, hence `age ~ elongation / S`.
    That expression is the stretch of a material LINE initially perpendicular to the flow. It
    is not the aspect ratio of a deformed circular patch, which is what `elongation` measures
    in the detections contract.

    For incompressible 2D simple shear, an initially isotropic patch is mapped by
    F = [[1, gamma], [0, 1]] with gamma = S*t. The patch's axes are the singular values of F,
    so its aspect ratio is a = lambda_max of F F^T, and because det(F F^T) = 1 we also have
    lambda_min = 1/a. Taking the trace:

        a + 1/a = 2 + gamma^2      ->      gamma = sqrt(a + 1/a - 2)
        t = sqrt(a + 1/a - 2) / S

    For a >> 1 this is gamma ~ sqrt(a), not gamma ~ a. The difference is not cosmetic: at the
    contract's example elongation of 8.2 the brief's form gives gamma = 8.2 and this one gives
    gamma = 2.51, so the brief's age is about 3.2x too LONG. Since age is being used as a
    filter on Stage 3's suspect pool, and since the one case with a documented release time is
    a ~3 h old slick, a 3x bias in the wrong direction matters.

    DO NOT QUOTE 3.2x AS A CONVERSION FACTOR. It is the ratio at a = 8.2 and nowhere else. The
    ratio is sqrt(a^2 - 1) / sqrt(a + 1/a - 2), which CLIMBS with elongation: 2.45x at a = 2,
    3.24x at a = 8.2, 4.70x at a = 20, 7.21x at a = 50. Every case carries its own elongation,
    so an age computed under the brief's form cannot be corrected by dividing -- it has to be
    recomputed here. Ratified by Akshat 13 Sept 2026 (docs/evaluation/stage2-age-decision-brief.md, D-B).

    Both are computed and both are reported in the diagnostics, so the discrepancy is visible
    rather than resolved silently. `age_hours` uses the exact form.

    Assumes simple shear and an initially isotropic patch. A patch that was already elongated
    at release breaks it -- which is a second reason for the acute gate below, beyond the one
    the brief gives.

    THE GATE, and it is the whole point: this is only valid when the OCEAN did the stretching.
    A `chronic` discharge is long and thin because the SHIP WAS MOVING, so applying this there
    gives nonsense. `unknown` is refused too -- an ungated guess is worse than a null.

    The band comes from the shear rate itself, which is a finite difference on a 9 km daily
    field and is the least certain input here; +/-35% is a deliberately generous acknowledgement
    of that rather than a measured error bar.
    """
    diag = {"observed_elongation": None if observed_elongation is None
            else float(observed_elongation),
            "shear_rate_s": None if shear_rate_s is None else float(shear_rate_s),
            "discharge_class": discharge_class,
            "band_frac": band_frac}

    if discharge_class != "acute":
        diag["skipped"] = _gate_reason(discharge_class, "C3.3",
                                       "reads age off the observed elongation, and a chronic "
                                       "slick is elongated by the vessel's motion rather than "
                                       "by shear")
        return None, diag

    if observed_elongation is None or shear_rate_s is None:
        diag["skipped"] = "missing elongation or shear rate"
        return None, diag

    e = float(observed_elongation)
    s = float(shear_rate_s)
    if e <= 1.0:
        diag["skipped"] = (f"elongation {e:.2f} is not above 1.0 -- the slick is not stretched, "
                           f"so there is no shear age to read from it")
        return None, diag
    if s <= 0.0:
        diag["skipped"] = "shear rate is zero -- a uniform field cannot stretch anything"
        return None, diag

    gamma_exact = math.sqrt(max(e + 1.0 / e - 2.0, 0.0))   # patch aspect ratio inversion
    gamma_brief = math.sqrt(max(e * e - 1.0, 0.0))         # the brief's line-stretch form

    t_h = (gamma_exact / s) / 3600.0
    lo = t_h * (1.0 - band_frac)
    hi = t_h * (1.0 + band_frac)
    diag["central_hours"] = t_h
    diag["gamma_exact"] = gamma_exact
    diag["gamma_brief_formula"] = gamma_brief
    diag["brief_formula_hours"] = (gamma_brief / s) / 3600.0
    diag["formula"] = "gamma = sqrt(a + 1/a - 2), patch aspect under incompressible simple shear"
    diag["formula_note"] = ("the brief's sqrt(a^2 - 1) is a material-line stretch, not a patch "
                            "aspect ratio; it is reported here as brief_formula_hours for "
                            "comparison but is NOT what age_hours uses")
    diag["shear_timescale_hours"] = (1.0 / s) / 3600.0

    if lo >= max_hours:
        diag["skipped"] = (f"implied age {t_h:.1f} h is past the {max_hours:.0f} h ceiling -- "
                           f"the shear rate is too small to have produced this elongation "
                           f"within any timescale we model")
        return None, diag
    return (max(lo, 0.0), min(hi, max_hours)), diag


# ---------------------------------------------------------------------------------------
# C3.4  weathering flag -- qualitative, never hours
# ---------------------------------------------------------------------------------------

def weathering_flag(wind_ms, contrast_centre_db=None, contrast_edge_db=None,
                    lo=WEATHERING_WIND_LO_MS, hi=WEATHERING_WIND_HI_MS):
    """C3.4. Returns (flag, diagnostics) with flag in {fresh, weathered, unknown}. NEVER hours.

    The observable the brief asks for is the CENTRE-versus-EDGE backscatter contrast inside
    the slick: fresher, thicker oil damps harder in the middle, so a steep centre-to-edge
    gradient reads fresh and a flat one reads weathered.

    THAT FIELD IS NOT IN THE CONTRACT. `detections.geojson` carries `contrast_db` (slick
    against surrounding sea) and `edge_gradient` (sharpness of the boundary); neither is a
    gradient WITHIN the slick, and neither is a substitute -- `contrast_db` moves with wind and
    thickness together, which is precisely the confounding C2 rules out.

    So this returns `unknown` and says why, unless the real pair is passed in. Refusing rather
    than fabricating is the same instinct as the abstain flag, and a fabricated freshness call
    would be exactly the kind of plausible-looking wrong answer this stage exists to avoid.
    ROUTE TO SOUMIRYA: two floats per detection, `contrast_centre_db` and `contrast_edge_db`,
    sampled inside the polygon and in an annulus just inside its boundary.
    """
    diag = {"wind_ms": None if wind_ms is None else float(wind_ms),
            "valid_wind_band_ms": [lo, hi]}

    if wind_ms is None:
        diag["reason"] = "no wind speed available"
        return "unknown", diag
    if not (lo <= float(wind_ms) <= hi):
        diag["reason"] = (f"mean wind {float(wind_ms):.1f} m/s is outside the {lo}-{hi} m/s "
                          f"band where oil-sea contrast is meaningful -- below it the sea is "
                          f"too smooth to show damping, above it wind erases the signal")
        return "unknown", diag

    if contrast_centre_db is None or contrast_edge_db is None:
        diag["reason"] = ("centre-vs-edge contrast is not in the detections contract; "
                          "contrast_db and edge_gradient are not substitutes. Needs "
                          "contrast_centre_db + contrast_edge_db from Stage 1 (Soumirya).")
        return "unknown", diag

    gradient = float(contrast_edge_db) - float(contrast_centre_db)
    diag["centre_minus_edge_db"] = -gradient
    diag["gradient_db"] = gradient
    # A steep gradient -- the centre markedly darker than the rim -- reads as a thick, fresh
    # core. A flat one reads as weathered, spread thin and uniform. 2 dB is a threshold to be
    # calibrated on the four validation cases, not a published constant.
    if gradient >= 2.0:
        diag["reason"] = f"centre {gradient:.1f} dB darker than the edge -- thick, fresh core"
        return "fresh", diag
    diag["reason"] = (f"centre-to-edge gradient only {gradient:.1f} dB -- thickness is uniform, "
                      f"consistent with a weathered, spread slick")
    return "weathered", diag


# ---------------------------------------------------------------------------------------
# C4  combining
# ---------------------------------------------------------------------------------------

def combine_bands(bands):
    """C4. `bands` maps estimator name -> (lo, hi) or None. Returns (band_or_None, method).

    Overlap    -> INTERSECTION, "combined"
    Disagree   -> UNION,        "disagreement"     <- the honest move, and the impressive one
    One only   -> that band,    that estimator's name
    None fire  -> None,         "none"             <- caller falls back to the bounded window
    """
    live = {k: (float(v[0]), float(v[1])) for k, v in bands.items() if v is not None}
    if not live:
        return None, "none"
    if len(live) == 1:
        name, band = next(iter(live.items()))
        return band, name

    lo_max = max(b[0] for b in live.values())
    hi_min = min(b[1] for b in live.values())
    if lo_max <= hi_min:
        return (lo_max, hi_min), "combined"

    return (min(b[0] for b in live.values()), max(b[1] for b in live.values())), "disagreement"


def round_band(band, nd=1):
    if band is None:
        return None
    return [round(float(band[0]), nd), round(float(band[1]), nd)]


# ---------------------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------------------

def pick_slick(dets):
    oil = [f for f in dets.get("features", [])
           if (f.get("properties") or {}).get("classification") == "oil"]
    if not oil:
        return None
    return max(oil, key=lambda f: f["properties"].get("confidence", 0.0))


def parse_ts(s):
    from datetime import datetime
    return datetime.fromisoformat(str(s).replace("Z", "+00:00"))


def main():
    ap = argparse.ArgumentParser(
        description="Stage 2 age estimation (docs/team/anushka-stage2-drift.md Part C)")
    ap.add_argument("--case", required=True)
    ap.add_argument("--cases-root", default=str(REPO / "cases"))
    ap.add_argument("--real", action="store_true", help="cached HYCOM + ERA5")
    ap.add_argument("--fake", action="store_true", help="analytic field, no GEE")
    ap.add_argument("--field", choices=["analytic", "constant"], default="analytic")
    ap.add_argument("--wind", type=float, nargs=2, default=(6.0, -4.0), metavar=("U", "V"))
    ap.add_argument("--out", default=str(OUT))
    ap.add_argument("--origin", default=None,
                    help="origin.json to read the centroid from and patch "
                         "(default <out>/origin.json)")
    ap.add_argument("--candidates", default="2:36:2", metavar="LO:HI:STEP",
                    help="candidate ages in hours for the shear estimator")
    ap.add_argument("--merge-oil", choices=["auto", "always", "never"], default="auto",
                    help="must match run.py's setting -- the age is read off the same slick "
                         "the origin was seeded from")
    ap.add_argument("--volume-m3", type=float, default=None,
                    help="reported release volume, from the OFFICIAL FINDING (588 barrels = "
                         "93.5 m3). C3.2 declines without it rather than deriving volume from "
                         "the observed area, which is circular. 1 bbl = 0.159 m3.")
    ap.add_argument("--particles", type=int, default=SEED_PARTICLES)
    ap.add_argument("--members", type=int, default=20,
                    help="ensemble members for the shear band")
    ap.add_argument("--timestep-minutes", type=int, default=15)
    ap.add_argument("--seed", type=int, default=143)
    ap.add_argument("--dry-run", action="store_true",
                    help="print everything, write nothing")
    a = ap.parse_args()

    if not (a.real or a.fake):
        raise SystemExit("choose an ocean: --real (cached HYCOM + ERA5) or --fake (analytic).")
    if a.real and a.fake:
        raise SystemExit("--real and --fake are mutually exclusive.")

    case_dir = Path(a.cases_root) / a.case
    out_dir = Path(a.out)
    origin_path = Path(a.origin) if a.origin else out_dir / "origin.json"

    if not origin_path.exists():
        raise SystemExit(f"{origin_path} not found -- age is measured from the origin cloud.\n"
                         f"  run: python pipeline/drift/run.py --case {a.case} "
                         f"{'--real' if a.real else '--fake'}")

    meta = json.loads((case_dir / "meta.json").read_text())
    origin = json.loads(origin_path.read_text())
    t0 = parse_ts(meta["detection_time"])
    olon, olat = float(origin["centroid"][0]), float(origin["centroid"][1])

    lo, hi, step = (float(x) for x in a.candidates.split(":"))
    candidate_hours = [round(x, 6) for x in np.arange(lo, hi + 1e-9, step)]

    print("=" * 78)
    print(f"UDGAM Stage 2 - age estimation   case {a.case}")
    print(f"origin centroid ({olon:.5f}, {olat:.5f})   t0 = "
          f"{t0.isoformat().replace('+00:00', 'Z')}")
    print("=" * 78)

    # ---- the observable ---------------------------------------------------------------
    det_path = case_dir / "detections.geojson"
    feat = None
    if det_path.exists():
        # Same slick selection as run.py, so the age is measured on the geometry the origin
        # was actually seeded from. Importing it rather than re-implementing is the point:
        # two different answers to "which slick?" is the kind of divergence nobody notices.
        sys.path.insert(0, str(HERE))
        from run import merge_oil_features
        feat, slick_diag = merge_oil_features(json.loads(det_path.read_text()),
                                              mode=a.merge_oil)

    if feat is None:
        # D16: a known_origin case has no detection, so there is no observed area or
        # elongation -- and every estimator here reads age OFF THE OBSERVED SLICK.
        reason = ("no oil detection to measure: "
                  + ("detections.geojson has zero oil features"
                     if det_path.exists() else "there is no detections.geojson"))
        if meta.get("known_origin") is not None:
            reason += (" -- this is a known_origin case (D16), where the source is documented "
                       "rather than detected, so slick geometry does not exist to read an age "
                       "from. Age is genuinely not available, not merely unmeasured.")
        print(f"\n  age_method = none\n        {reason}")
        block = {"age_hours": None, "age_method": "none", "age_weathering": "unknown",
                 "age_estimators": {"shear": None, "fay": None, "elongation": None}}
        _finish(a, origin_path, origin, block,
                {"skipped": reason, "case": a.case}, out_dir)
        return 0

    props = feat["properties"]
    observed_area = float(props["area_km2"])
    observed_elong = props.get("elongation")
    discharge = props.get("discharge_class", "unknown")
    print(f"\nObserved slick  {props['id']}  area {observed_area:.2f} km2   "
          f"elongation {observed_elong}   discharge_class {discharge!r}")

    # ---- the ocean --------------------------------------------------------------------
    if a.real:
        field = load_case_field(a.case, repo_root=REPO)
    else:
        field = make_fake(a.field, lon0=olon, lat0=olat, wind=tuple(a.wind))
    print(f"field  {field}")

    # ---- the loud coverage guard ------------------------------------------------------
    coverage = field_time_coverage(a.case, REPO) if a.real else None
    candidate_hours, dropped, cov_detail = clip_candidates_to_coverage(
        candidate_hours, t0, coverage)
    if dropped:
        print(f"\n  !! DROPPED {len(dropped)} candidate ages that fall outside the cached "
              f"field: {', '.join(f'{h:g}' for h in dropped)} h")
        print(f"     {cov_detail}")
        print("     Past the last snapshot the field is CLAMPED, not modelled: the extent "
              "curve flattens and then")
        print("     falls, and the monotonicity gate fails for a DATA reason, not a physical "
              "one. HYCOM is daily, so")
        print("     a 36 h candidate needs 3 snapshots in the cache, not 2 -- refetch a wider "
              "window to use them.")
    if not candidate_hours:
        raise SystemExit(
            "no candidate ages left inside the cached field's time coverage.\n"
            f"  {cov_detail}\n"
            "  refetch a wider window, or lower --candidates.")

    # ---- C3.1 shear dispersion --------------------------------------------------------
    # MEASURE the major axis off the polygon; fall back to the ellipse form only if there is
    # no usable geometry. On Jacksonville's det-01 the two disagree by 2.6x (17.38 km measured
    # against 6.72 km derived) because the slick is a sinuous filament, not an ellipse, so
    # which route ran is printed and recorded rather than assumed.
    observed_length, axis_diag = slick_major_axis_km(feat)
    print(f"\nC3.1 shear dispersion  ({a.members} members x {len(candidate_hours)} candidates "
          f"x {a.particles} particles)")
    if observed_length is None:
        shear_band, shear_diag = None, {
            "skipped": ("no usable polygon and no area_km2 x elongation to fall back on, so "
                        "there is no observed major axis to match; matching on area cannot "
                        "work in a divergence-free field"),
            "axis": axis_diag}
        print(f"  -> none: {shear_diag['skipped']}")
    else:
        print(f"  observed major axis {observed_length:.2f} km  ({axis_diag['route']}) "
              f"-- matching on LENGTH, not area")
        if axis_diag.get("derived_km") is not None and axis_diag["route"].startswith("measured"):
            print(f"     the ellipse form (area {observed_area:.2f} km2 x elongation "
                  f"{observed_elong}) would have said {axis_diag['derived_km']:.2f} km, "
                  f"a factor of {axis_diag.get('measured_over_derived')}")
            if axis_diag.get("filament_aspect"):
                print(f"     mean width {axis_diag['mean_width_m']:.0f} m over the measured "
                      f"length -> filament aspect {axis_diag['filament_aspect']}, against a "
                      f"reported elongation of {observed_elong}")
        shear_band, shear_diag = shear_dispersion_age(
            field, olon, olat, t0, observed_length, candidate_hours,
            timestep_minutes=a.timestep_minutes, n_particles=a.particles,
            n_members=a.members, seed=a.seed, discharge_class=discharge)
        # How the matched length was obtained is part of the result, not trivia: a band read off
        # a derived axis and one read off a measured axis are different claims.
        shear_diag["axis"] = axis_diag
    if shear_band:
        print(f"  -> [{shear_band[0]:.1f}, {shear_band[1]:.1f}] h   "
              f"({shear_diag['n_fitted']}/{shear_diag['n_members']} members fitted)")
        print(f"     CAVEAT {shear_diag['caveat']}")
    else:
        print(f"  -> none: {shear_diag.get('skipped')}")

    # ---- C3.2 Fay ---------------------------------------------------------------------
    print("\nC3.2 Fay gravity-viscous spreading")
    print(f"  k {FAY_K_RANGE}  rho_oil {RHO_OIL_RANGE} kg/m3  "
          f"volume {a.volume_m3 if a.volume_m3 else 'NOT SUPPLIED'}")
    fay_band, fay_diag = fay_age(observed_area, volume_m3=a.volume_m3)
    if fay_diag.get("regime"):
        print(f"  regime {fay_diag['regime']}   spreading alone reaches "
              f"{fay_diag['max_predicted_area_km2_at_ceiling']:.3f} km2 at the ceiling")
    if fay_band:
        print(f"  -> [{fay_band[0]:.1f}, {fay_band[1]:.1f}] h")
    else:
        print(f"  -> none: {fay_diag.get('skipped')}")
    print(f"  k: {fay_diag['k_citation']}")

    # ---- C3.3 elongation under shear --------------------------------------------------
    print("\nC3.3 elongation under shear")
    shear_rate = deformation_rate_s(field, olon, olat, t0)
    if shear_rate > 0:
        print(f"  deformation rate S = {shear_rate:.3e} 1/s  "
              f"(timescale {1.0 / shear_rate / 3600.0:.1f} h)")
    else:
        print("  deformation rate S = 0 -- a uniform field has no shear to read")
    elong_band, elong_diag = elongation_age(observed_elong, shear_rate, discharge)
    if elong_band:
        print(f"  -> [{elong_band[0]:.1f}, {elong_band[1]:.1f}] h")
    else:
        print(f"  -> none: {elong_diag.get('skipped')}")

    # ---- C3.4 weathering --------------------------------------------------------------
    print("\nC3.4 weathering flag (qualitative, never hours)")
    wind = mean_wind_ms(field, olon, olat, t0)
    flag, weather_diag = weathering_flag(
        wind,
        props.get("contrast_centre_db"),
        props.get("contrast_edge_db"))
    print(f"  mean wind {wind:.2f} m/s  ->  {flag}")
    print(f"     {weather_diag.get('reason')}")

    # ---- C4 combine -------------------------------------------------------------------
    bands = {"shear": shear_band, "fay": fay_band, "elongation": elong_band}
    combined, method = combine_bands(bands)

    print("\n" + "-" * 78)
    print(f"C4 combine   shear {round_band(shear_band)}   fay {round_band(fay_band)}   "
          f"elongation {round_band(elong_band)}")
    if combined is None:
        print(f"  age_hours = null   age_method = {method}")
        # READ the window's method, do not assume it. This line used to say "the bounded
        # time_window stands, and it is a BRACKET" unconditionally -- which on
        # case-jacksonville-2024 is simply false: its HYCOM is 3-hourly, the ensemble spread
        # really does converge, and the window is measured. Announcing our own strongest
        # available claim as our weakest one is a bad way to lose an argument on stage.
        tw_method = (origin or {}).get("time_window_method", "bounded")
        if tw_method == "convergence":
            print("  nothing fired -- but the time_window on this case is MEASURED "
                  "(method=convergence),")
            print("  not a bracket. The release window stands on the ensemble's own "
                  "convergence, not on")
            print("  the rewind span minus eight hours. Say 'measured', not 'bounded'.")
        else:
            print(f"  nothing fired -- the time_window stands (method={tw_method}), "
                  f"and it is a BRACKET")
    else:
        print(f"  age_hours = [{combined[0]:.1f}, {combined[1]:.1f}]   age_method = {method}")
        if method == "disagreement":
            print("  estimators DISAGREE -> union reported. This is a result, not a failure:"
                  "\n  a widened honest band beats a narrow invented one, and the UI must "
                  "say so.")
    print("-" * 78)

    block = {
        "age_hours": round_band(combined),
        "age_method": method,
        "age_weathering": flag,
        "age_estimators": {"shear": round_band(shear_band),
                           "fay": round_band(fay_band),
                           "elongation": round_band(elong_band)},
    }
    report = {
        "case": a.case,
        "t0": meta["detection_time"],
        "origin_centroid": [olon, olat],
        "observed": {"id": props["id"], "area_km2": observed_area,
                     "elongation": observed_elong, "discharge_class": discharge},
        "field": repr(field),
        "result": block,
        "shear": shear_diag,
        "fay": fay_diag,
        "elongation": elong_diag,
        "weathering": weather_diag,
    }
    _finish(a, origin_path, origin, block, report, out_dir)
    return 0


def _finish(a, origin_path, origin, block, report, out_dir):
    """Patch the four contract keys into origin.json and drop the diagnostics sidecar."""
    report_path = out_dir / f"age_{a.case}.json"
    if a.dry_run:
        print(f"\n[dry-run] would patch {origin_path}")
        print(f"[dry-run] would write {report_path}")
        print(json.dumps(block, indent=2))
        return

    origin.update(block)
    out_dir.mkdir(parents=True, exist_ok=True)
    origin_path.write_text(json.dumps(origin))
    report_path.write_text(json.dumps(report, indent=2, default=str))
    print(f"\n[age]  patched {origin_path}")
    print(f"[age]  wrote   {report_path}   (working space -- not part of the bundle)")
    print(f"[age]  next    python scripts/validate_case.py cases/{a.case}")


if __name__ == "__main__":
    sys.exit(main())
