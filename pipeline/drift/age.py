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
from slick import merge_oil_features, pick_slick
import step
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
# Age engine v2: E1 and E2 draw the release's initial sigma per member from this range instead.
RELEASE_SIGMA_RANGE_M = (50.0, 600.0)
# RAISED FROM 300 TO 2000 ON 16 SEPT 2026, and the number is derived rather than chosen.
#
# With diffusion on (Phase 1) the extent curve is STOCHASTIC, and `check_monotonic` refuses the
# whole estimator if modelled extent ever falls by more than tol_frac = 2% between candidates.
# The relative standard error of a sigma estimate from n particles is 1/sqrt(2(n-1)):
#
#       n =  300  ->  4.09%        n = 1200  ->  2.04%
#       n =  600  ->  2.89%        n = 2000  ->  1.58%
#
# At 300 the noise floor is TWICE the tolerance, so spurious monotonicity failures were
# structurally guaranteed the moment the random walk was switched on -- and that is exactly what
# happened: Huntington failed 6/20 members on dips of 2.8-3.3%, every one of them inside the
# n=300 noise band and none of them a field squeezing the cloud.
#
# The fix is to lower the noise, NOT to raise the tolerance. `check_monotonic` exists to catch a
# field that is genuinely converging, and widening it to swallow 4% sampling noise would blind it
# to a real 3% violation. 2000 puts the noise floor at 1.58%, below the 2% gate, with margin.
# Cost is ~6.7x the integration work in C3.1 only; nothing else in Stage 2 uses this.
SEED_PARTICLES = 2000


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
        "orientation_deg": round(axis_bearing_deg(vt[0][0], vt[0][1]), 2),
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


def axis_bearing_deg(vx_east, vy_north):
    """Bearing of an AXIS (not a direction), degrees clockwise from north, folded into [0, 180)."""
    return float(math.degrees(math.atan2(vx_east, vy_north)) % 180.0)


def pca_axes(pos):
    """(sd_major_km, sd_minor_km, bearing_deg) for a particle cloud.

    pca_extent() plus the orientation of the major axis. Orientation is the observable the old
    engine threw away: under a rotating wind or a tidal current a young and an old release point
    their long axes in different directions, and that separates ages that length alone cannot.
    """
    p = as_positions(pos)
    if p.shape[0] < 3:
        return 0.0, 0.0, 0.0
    clon, clat = float(p[:, 0].mean()), float(p[:, 1].mean())
    dx, dy = deg_to_m(p[:, 0] - clon, p[:, 1] - clat, p[:, 1])
    xy = np.column_stack([dx, dy]) / 1000.0
    evals, evecs = np.linalg.eigh(np.cov(xy, rowvar=False))
    v = evecs[:, 1]
    return (float(math.sqrt(max(evals[1], 0.0))), float(math.sqrt(max(evals[0], 0.0))),
            axis_bearing_deg(v[0], v[1]))


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


def check_monotonic(candidate_hours, areas, tol_frac=0.02, up_to=None):
    """The sanity gate from C3.1: modelled extent MUST increase with candidate age.

    If it does not, the field or the seeding is wrong -- stop and look, do not tune. A small
    tolerance absorbs sampling noise from a finite particle cloud; a real violation is a
    field that is squeezing the cloud.

    `up_to` LIMITS THE CHECK TO THE CANDIDATES THE INVERSION ACTUALLY USES (16 Sept 2026), and
    it is there because we stopped and looked, exactly as the paragraph above says to.

    WHAT WE SAW. At the 72 h horizon Huntington failed 20/20 members. The failures were not
    scattered the way sampling noise is -- ALL TWENTY fell at the same two candidates, 42 h and
    46 h, by 6-12% against a 1.58% noise floor, across members with different diffusivities and
    different wind coefficients. That is not noise and it is not a bug: it is a real convergence
    event in the field, about two days before the pass. The gate was right to flag it.

    WHY IT SHOULD NOT REFUSE THE ESTIMATE ANYWAY. Every one of those inversions crossed the
    observed extent at 2.0-7.4 h -- thirty-five hours before the dip. The gate exists to keep
    the INVERSION well-posed: a monotonic curve crosses the target exactly once, so the age is
    unique. A dip 35 h past the crossing cannot make that crossing ambiguous. Refusing on it
    discards a sound answer because of ocean behaviour at a time the answer does not depend on.

    Note that this is STRICTER where it matters, not looser: the original premise ("a smooth
    field advects and stretches, it does not converge") was calibrated on a 24-36 h rewind
    through DAILY HYCOM. The real cases fetch 3-hourly HYCOM, which resolves mesoscale structure
    a daily field cannot, so genuine convergence is now expected rather than anomalous. The
    check keeps its full force below the crossing, where a second crossing would make the answer
    ambiguous, and stops asserting a premise that no longer holds above it.

    Dips beyond `up_to` are still measured and still reported -- see `late_dips` in the
    diagnostics. They are a real statement about the field and worth keeping.

    Returns (ok, first_offending_index_or_None, detail).
    """
    a = np.asarray(areas, dtype=np.float64)
    last = a.size if up_to is None else min(int(up_to) + 1, a.size)
    for i in range(1, last):
        if a[i] < a[i - 1] * (1.0 - tol_frac):
            return False, i, (f"modelled area fell from {a[i-1]:.3f} km2 at "
                              f"{candidate_hours[i-1]:g} h to {a[i]:.3f} km2 at "
                              f"{candidate_hours[i]:g} h")
    scope = ("" if up_to is None else
             f" (checked to the inversion at {candidate_hours[last-1]:g} h; grid runs to "
             f"{candidate_hours[-1]:g} h)")
    return True, None, (f"area grows {a[0]:.3f} -> {a[last-1]:.3f} km2 across "
                        f"{candidate_hours[0]:g}-{candidate_hours[last-1]:g} h{scope}")


def crossing_index(values, target):
    """Index of the first candidate at or above `target`, or None if it is never reached.

    This is the candidate the inversion brackets against, and therefore the last one whose
    monotonicity can affect the answer. Deliberately separate from invert_curve so the gate and
    the interpolation cannot drift apart.
    """
    v = np.asarray(values, dtype=np.float64)
    target = float(target)
    if target <= v[0] or target >= v[-1]:
        return None
    return int(np.searchsorted(v, target))


def late_dips(candidate_hours, values, tol_frac=0.02, after=None):
    """Every monotonicity violation at or beyond `after`. Reported, never acted on."""
    a = np.asarray(values, dtype=np.float64)
    start = 1 if after is None else max(1, int(after) + 1)
    out = []
    for i in range(start, a.size):
        if a[i] < a[i - 1] * (1.0 - tol_frac):
            out.append({"from_hours": float(candidate_hours[i - 1]),
                        "to_hours": float(candidate_hours[i]),
                        "from_km": float(a[i - 1]), "to_km": float(a[i]),
                        "drop_frac": float(1.0 - a[i] / a[i - 1])})
    return out


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



# Band widening applied when the gate lets an `unknown` discharge through. See age_gate.
UNKNOWN_BAND_FRAC = 0.55
UNKNOWN_PERCENTILE = 5.0          # vs 10/90 for a class we actually know


def age_gate(discharge_class):
    """Should an age estimator run on this slick? -> (verdict, reason).

    verdict is one of:
      "allow"          run normally
      "allow_widened"  run, but widen the band and carry the caveat
      "refuse"         do not run; the answer would be meaningless

    THIS REPLACED AN `== "acute"` GATE ON 16 SEPT 2026, and the reason is measured, not stylistic.

    `discharge_class` comes from detect/ships.py:classify_discharge, which reads SHAPE ALONE:
    elongation < 3.0 -> 'acute'; elongation >= 5.0 AND straightness >= 0.60 -> 'chronic';
    everything between -> 'unknown'. Acute therefore requires a LOW elongation, and oil slicks
    are elongated. Measured against the live library on 16 Sept 2026: of the 17 features
    classified `oil` across the nine cases, 4 are 'chronic', 13 are 'unknown', and **none is
    'acute'** -- every 'acute' feature in every bundle is sub-0.5 km2 `lookalike` speckle. An
    acute-only gate is not strict, it is UNREACHABLE: it fired on nothing, which is why
    age_hours was null on all six spill cases.

    It was also circular, which age.py has flagged since 13 Sept: the gate is a threshold on
    elongation while C3.3 INVERTS elongation, so the gate and the estimator read the same number.

    What survives is the part that is real physics:

      chronic         REFUSE. A chronic discharge is a moving source, so the slick's long axis is
                      the vessel's TRACK. Both estimators read length as evidence of spreading,
                      and on a track that is simply false. Nothing here is missing -- the gate is
                      doing its job.
      acute           ALLOW. A release at a point, spread by the ocean. The assumption both
                      estimators are built on.
      unknown/absent  ALLOW, WIDENED. The detector could not place the geometry in either bucket.
                      That is a statement about the shape, not a missing field -- and it is not a
                      reason to emit nothing when 13 of 17 oil slicks land here. The slick may be
                      acute (estimate valid) or chronic (estimate an overestimate), so the band
                      is widened to span that ambiguity rather than pretending it is not there,
                      and `age_gate` travels with the result so a reader knows which it was.
                      Widening an honest band beats narrowing an invented one.
    """
    if discharge_class == "chronic":
        return "refuse", (
            "discharge_class is 'chronic': the source was under way, so the slick's long axis is "
            "the vessel's TRACK, not a patch spread by the ocean. Reading an age off it would be "
            "meaningless. The gate is correct and nothing is missing.")
    if discharge_class == "acute":
        return "allow", "discharge_class is 'acute': a release at a point, spread by the ocean."
    return "allow_widened", (
        f"discharge_class is {discharge_class!r}: detect/ships.py:classify_discharge could not "
        f"place this geometry in either bucket (it buckets on elongation alone -- <3.0 acute, "
        f">=5.0 and straight chronic, between unknown). The slick may be a point release or a "
        f"track, so the estimate runs but the band is WIDENED to span that ambiguity, and this "
        f"gate verdict travels with the result. Note the shape of the library: 13 of 17 oil "
        f"detections are 'unknown' and NONE is 'acute', so refusing 'unknown' -- as the gate did "
        f"until 16 Sept 2026 -- meant refusing every case.")


def shear_dispersion_age(base_field, lon, lat, t0, observed_length_km, candidate_hours,
                         timestep_minutes=15, n_particles=SEED_PARTICLES, n_members=20,
                         seed=143, guard=True, discharge_class=None, release_points=None,
                         observed_width_km=None, observed_bearing_deg=None):
    """C3.1. Returns (band_or_None, diagnostics).

    v2 (16 Sept 2026): diagnostics also carry `loglik` -- the E1 shape likelihood on
    age_posterior.AGE_GRID_H -- and `release_points` moves each candidate's start to where a
    slick of that age was actually released. See shape_loglik() and _curve_with_wind().

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
    verdict, gate_reason = age_gate(discharge_class)
    if verdict == "refuse":
        return None, {
            "matched_on": "major_axis_length_km",
            "discharge_class": discharge_class,
            "age_gate": "chronic_refused",
            "skipped": gate_reason,
        }
    widened = verdict == "allow_widened"

    rng = np.random.default_rng(seed)
    winds, scales = ens._stratified_draws(n_members, rng)

    # Horizontal diffusivity is the THIRD perturbed quantity, drawn the same stratified way as
    # the other two (16 Sept 2026). One draw per equal-probability slice of the Okubo band, then
    # shuffled, so a 20-member ensemble samples the range evenly instead of clustering by luck.
    # Without this term the modelled extent tops out at ~1.3 km and no member brackets a real
    # slick -- see _curve_with_wind's docstring.
    # v2: SCALE-DEPENDENT diffusivity (Okubo), not a flat band. See okubo_member_ks: with K free
    # over three decades a young, fast-spreading slick and an old, slow one look identical and
    # the posterior carried 0.02 nats on Huntington -- i.e. nothing.
    if observed_length_km and observed_width_km:
        k_scale_m = 1000.0 * math.sqrt(float(observed_length_km) * float(observed_width_km))
    else:
        k_scale_m = 1000.0 * float(observed_length_km)
    ks = okubo_member_ks(k_scale_m, n_members, rng)
    k_lo, k_hi = float(ks.min()), float(ks.max())
    # v2: the release's initial size is unknown too -- a continuous leak or a large release is
    # wide before the ocean touches it, and a fixed 200 m seed forced every wide slick to be old
    # (Huntington, 2.8 h and 1.4 km wide, came out 13-58 h). Log-uniform per member.
    sigmas = step.stratified_loguniform(n_members, *RELEASE_SIGMA_RANGE_M, rng)

    fits, members, mono_failures, late_dip_members = [], [], [], []
    shape_L, shape_W, shape_B = [], [], []
    for m in range(n_members):
        wind_coeff = float(winds[m])
        scale = max(float(scales[m]), 0.05)
        diffusivity = float(ks[m])
        seed_sigma = float(sigmas[m])
        field = ens.PerturbedField(base_field, scale)

        # The perturbed wind coefficient enters through the INTEGRATOR, not the field object,
        # so it has to be passed where the trajectory is computed. shear_extent_curve() uses
        # the module default and would silently drop this member's wind draw -- which would
        # make the band narrower than the uncertainty budget actually is.
        areas_w, sd1_w, sd2_w, brg_w = _curve_with_wind(
            field, lon, lat, t0, candidate_hours, timestep_minutes, n_particles,
            wind_coeff=wind_coeff, seed=seed + 2000 + m, guard=guard,
            diffusivity=diffusivity, starts=release_points, with_axes=True,
            sigma_m=seed_sigma)

        lengths_w = 4.0 * sd1_w          # full major axis of the 2-sigma ellipse
        shape_L.append(lengths_w)
        shape_W.append(4.0 * sd2_w)
        shape_B.append(brg_w)

        # Monotonicity is checked only as far as the inversion reaches. See check_monotonic:
        # a dip beyond the crossing cannot make the crossing ambiguous, and at 72 h the real
        # field genuinely converges around 42-46 h on every member.
        xi = crossing_index(lengths_w, observed_length_km)
        if xi is None:
            # This member never reaches the observed extent, so it contributes no fit and there
            # is no inversion for the gate to protect. Checking its monotonicity anyway would
            # judge it on ocean behaviour at 40-70 h that nothing downstream reads -- and it is
            # already counted, honestly, in n_fitted. Conflating "did not bracket" with "the
            # field misbehaved" is what made this read 20/20 instead of the 9 members that
            # simply started above the target.
            ok, detail = True, "no crossing: this member contributes no fit"
        else:
            ok, idx, detail = check_monotonic(candidate_hours, lengths_w, up_to=xi)
        if not ok:
            mono_failures.append({"member": m, "detail": detail})
        _dips = late_dips(candidate_hours, lengths_w, after=xi)
        if _dips:
            late_dip_members.append({"member": m, "dips": _dips})

        t_fit = invert_curve(candidate_hours, lengths_w, observed_length_km)
        members.append({
            "member": m, "wind_coeff": wind_coeff, "current_scale": scale,
            "diffusivity_m2s": diffusivity, "release_sigma_m": seed_sigma,
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
        # Set here, before any of the skip returns below, so a refusal still says which way the
        # gate went. It used to be assigned only on the success path, which meant the one case
        # you most want it on -- a skipped estimator -- reported age_gate: null.
        "age_gate": "unknown_widened" if widened else "acute",
        "gate_reason": gate_reason,
        "n_members": n_members,
        "n_fitted": len(fits),
        "matched_on": "major_axis_length_km",
        "candidate_hours": [float(h) for h in candidate_hours],
        "observed_length_km": float(observed_length_km),
        "monotonicity_failures": mono_failures,
        "late_dips": late_dip_members,
        "late_dips_note": ("monotonicity violations BEYOND the candidate the inversion "
                           "brackets against. Recorded, never acted on: a dip past the "
                           "crossing cannot make the crossing ambiguous. On Huntington "
                           "at 72 h every member dips at 42-46 h by 6-12% while every "
                           "inversion sits at 2-7 h -- a real convergence event in the "
                           "field, not a modelling fault."),
        "median_area_ratio_first_to_last": (float(np.median(area_ratios))
                                            if area_ratios else None),
        "diffusivity_range_m2s": [float(k_lo), float(k_hi)],
        "diffusivity_note": ("horizontal turbulent diffusivity, drawn per member from Okubo's "
                             "scale-dependent relation at the observed slick size "
                             f"({k_scale_m:.0f} m), x/ {TRACK_OKUBO_SPREAD} at 1 sigma. An "
                             "ASSUMPTION with a range, not a measurement -- and the reason the "
                             "shape likelihood carries any age information at all (K and t are "
                             "otherwise degenerate)."),
        "diffusivity_scale_m": round(k_scale_m, 1),
        "members": members,
        "caveat": ("advective and shear spreading only -- no gravity-viscous phase, so this "
                   "OVERESTIMATES the age of a very young slick. Report as a lower-bounded "
                   "band."),
        "why_not_area": ("a 2D incompressible field preserves cloud area, so area carries no "
                         "age signal in this model; the major axis does. See the docstring."),
    }

    # ---- v2: the shape likelihood (E1) -----------------------------------------------
    # Computed BEFORE the band's refusal paths, because it does not share their failure modes:
    # it needs no unique crossing, so a non-monotonic curve just becomes a multimodal
    # likelihood, and a member that never reaches the target still says "not at this age".
    ll = shape_loglik(candidate_hours, shape_L, shape_W, shape_B, observed_length_km,
                      observed_width_km, observed_bearing_deg)
    diag["loglik"] = None if ll is None else [round(float(x), 4) for x in ll]
    diag["shape_observed"] = {"length_km": float(observed_length_km),
                              "width_km": observed_width_km,
                              "bearing_deg": observed_bearing_deg}
    diag["shape_curves"] = {"L_km": np.round(np.asarray(shape_L), 4).tolist(),
                            "W_km": np.round(np.asarray(shape_W), 4).tolist(),
                            "bearing_deg": np.round(np.asarray(shape_B), 2).tolist()}
    diag["release_points"] = (None if release_points is None else
                              [None if r is None else [round(float(r[0]), 5),
                                                       round(float(r[1]), 5)]
                               for r in release_points])

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

    # A class we know gets the 10/90 band. An `unknown` one gets 5/95 across the same member
    # fits -- a real distributional statement about the same ensemble, not a fudge factor, and
    # the honest response to not knowing whether the long axis is spreading or a ship's track.
    pct = UNKNOWN_PERCENTILE if widened else 10.0
    lo = float(np.percentile(fits, pct))
    hi = float(np.percentile(fits, 100.0 - pct))
    diag["band_percentiles"] = [pct, 100.0 - pct]
    return (lo, hi), diag


def _curve_with_wind(field, lon, lat, t0, candidate_hours, timestep_minutes, n_particles,
                     wind_coeff, seed, guard=True, diffusivity=0.0, starts=None,
                     with_axes=False, sigma_m=SEED_SIGMA_M):
    """shear_extent_curve() with an explicit wind coefficient. Split out because the ensemble
    perturbs the wind coefficient at the integrator, not inside the field object.

    THIS IS THE ONLY PLACE IN STAGE 2 THAT TURNS HORIZONTAL DIFFUSION ON (16 Sept 2026), and it
    is what makes C3.1 able to date a real slick at all.

    Advection alone reaches a modelled major axis of 0.8-1.3 km on real HYCOM (decision brief
    section 4) against observed slicks of 2.3-10.1 km, so `invert_curve` had no bracket and the
    estimator refused on every case in the library. That gap is a missing PROCESS: a 9 km daily
    cell cannot resolve the sub-grid turbulence that actually spreads a slick, and an
    incompressible advected patch preserves its area by construction (test 6c: area x1.02 while
    the major axis goes x5.7). Adding a diffusivity drawn from the Okubo shelf-scale band lets
    the modelled extent span the observed range, so the inversion has something to invert.

    It is an ASSUMPTION with a range, and it is published as one: the caller draws `diffusivity`
    per ensemble member across `step.DIFFUSIVITY_RANGE_M2S` and the drawn values go into the
    diagnostics, exactly like the wind coefficient. The default here stays 0.0 so that
    `shear_extent_curve` and every test that calls this directly keep the deterministic physics.

    AGE ENGINE v2 ADDITIONS (16 Sept 2026), both opt-in so every existing caller is unchanged:

      starts      one (lon, lat) per candidate: WHERE a slick of that age was released. For
                  candidate age t that is where the backward control cloud was t hours before
                  the pass, not the origin centroid -- a 6 h release and a 60 h release did not
                  start from the same spot, and the field they spread in differs accordingly.
                  The unit cloud is still ONE realisation, translated to each start, so
                  adjacent candidates still differ only by elapsed time and place.
      with_axes   also return the major-axis bearing per candidate (4-tuple).
    """
    rng = np.random.default_rng(seed)
    areas, majors, minors, bearings = [], [], [], []
    start0 = seed_cloud(lon, lat, n_particles, sigma_m=sigma_m, rng=rng)   # one realisation
    for j, t_h in enumerate(candidate_hours):
        start = start0
        if starts is not None and starts[j] is not None:
            start = start0 + (np.asarray(starts[j], dtype=np.float64) - np.array([lon, lat]))
        n_steps = int(round(t_h * 60.0 / timestep_minutes)) + 1
        history, _ = integrate(start, t0 - timedelta(hours=float(t_h)), field, n_steps,
                               timestep_minutes, direction="forward",
                               wind_coeff=wind_coeff, guard=guard,
                               diffusivity=diffusivity,
                               rng=(rng if diffusivity > 0.0 else None))
        final = history[-1]
        sd1, sd2, area = pca_extent(final)
        areas.append(area)
        majors.append(sd1)
        minors.append(sd2)
        if with_axes:
            bearings.append(pca_axes(final)[2])
    if with_axes:
        return (np.asarray(areas), np.asarray(majors), np.asarray(minors),
                np.asarray(bearings))
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
    at release breaks it -- which is a second reason the `chronic` refusal below is real physics
    rather than caution.

    THE GATE, and it is the whole point: this is only valid when the OCEAN did the stretching.
    A `chronic` discharge is long and thin because the SHIP WAS MOVING, so applying this there
    gives nonsense and `age_gate` refuses it.

    `unknown` USED TO BE REFUSED TOO. It no longer is (16 Sept 2026). The old comment here read
    "an ungated guess is worse than a null" -- true, but it was not a guess being avoided, it
    was every case: `discharge_class` buckets on elongation alone, acute needs elongation < 3.0,
    and 13 of the 17 oil detections in the library are 'unknown' with none 'acute'. Refusing
    `unknown` refused everything, and the gate read the same quantity this function inverts,
    which is circular. So `unknown` now runs with `band_frac` widened to UNKNOWN_BAND_FRAC and
    the verdict recorded. See age_gate.

    The band comes from the shear rate itself, which is a finite difference on a 9 km daily
    field and is the least certain input here; +/-35% is a deliberately generous acknowledgement
    of that rather than a measured error bar, and +/-55% on an `unknown` class widens it to
    cover not knowing whether the ocean or a ship did the stretching.
    """
    diag = {"observed_elongation": None if observed_elongation is None
            else float(observed_elongation),
            "shear_rate_s": None if shear_rate_s is None else float(shear_rate_s),
            "discharge_class": discharge_class,
            "band_frac": band_frac}

    verdict, gate_reason = age_gate(discharge_class)
    diag["age_gate"] = {"refuse": "chronic_refused", "allow": "acute",
                        "allow_widened": "unknown_widened"}[verdict]
    diag["gate_reason"] = gate_reason
    if verdict == "refuse":
        diag["skipped"] = gate_reason
        return None, diag
    if verdict == "allow_widened":
        band_frac = UNKNOWN_BAND_FRAC
        diag["band_frac"] = band_frac

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
# AGE ENGINE v2 -- likelihoods  (plan: stateless-bouncing-cerf.md, Akshat 16 Sept 2026)
# ---------------------------------------------------------------------------------------

# E1/E2 observation errors, in natural-log units for the two lengths and a von Mises
# concentration for the axis bearing. STARTING VALUES, recalibrated by age_twins.py and read
# back from age_calibration.json. What they absorb is mostly not SAR noise but the mismatch
# between "thresholded dark polygon" and "particle 2-sigma envelope" (see pca_extent).
SHAPE_SIGMA_LOG_L = 0.30
SHAPE_SIGMA_LOG_W = 0.50
SHAPE_KAPPA = 1.0
# If no member at any candidate comes within this many sigma of the observation, the slick is
# outside what the model can produce and the likelihood is refused rather than letting the
# nearest edge of the grid win by default.
SHAPE_MAX_SIGMA = 3.0

# E4 track estimator assumptions -- each a range, each printed.
TRACK_WAKE_SIGMA_M = (5.0, 30.0)       # initial cross-track sigma: a ship's turbulent wake
TRACK_WIDTH_PER_SIGMA = (2.5, 5.0)     # visible SAR width / sigma of a gaussian cross-profile
TRACK_WIDTH_ERR_M = 15.0               # one Sentinel-1 IW GRD pixel-ish, 1 sigma
TRACK_OKUBO_SPREAD = 3.0               # multiplicative 1-sigma spread on Okubo's K
TRACK_MIN_ASPECT = 6.0                 # below this the shape is not a track
TRACK_END_FRAC = 0.2                   # "an end" = the outer 20 % of the along-axis extent

CALIBRATION_PATH = HERE / "age_calibration.json"
DEFAULT_WEIGHTS = {"shape": 1.0, "detect": 0.5, "track": 1.0, "surrogate": 0.0}


def shape_loglik(candidate_hours, L, W, B, obs_L, obs_W=None, obs_B=None,
                 sigma_L=SHAPE_SIGMA_LOG_L, sigma_W=SHAPE_SIGMA_LOG_W, kappa=SHAPE_KAPPA,
                 grid=None):
    """E1/E2. Log-likelihood of the observed slick shape at every grid age, or None.

    L, W, B are (members, candidates): modelled full major axis, full minor axis (both km,
    4 sigma) and major-axis bearing. For candidate j,

        lik_j = mean over members of  N(ln L_obs; ln L_mj, sigma_L)
                                    * N(ln W_obs; ln W_mj, sigma_W)
                                    * exp(kappa * (cos 2(B_obs - B_mj) - 1))

    The MEAN over members is the point: it marginalises the wind coefficient, the current
    scale and the diffusivity the ensemble samples, so their uncertainty is inside the
    likelihood rather than bolted on afterwards. The bearing term uses 2*delta because an
    axis has no sign. Constants common to every candidate are dropped.
    """
    import age_posterior as AP
    grid = AP.AGE_GRID_H if grid is None else grid
    L = np.asarray(L, dtype=np.float64)
    if L.size == 0 or obs_L is None or float(obs_L) <= 0:
        return None
    L = L.reshape(-1, len(candidate_hours))
    z = -0.5 * ((math.log(float(obs_L)) - np.log(np.maximum(L, 1e-6))) / sigma_L) ** 2
    if obs_W is not None and float(obs_W) > 0 and W is not None:
        Wm = np.asarray(W, dtype=np.float64).reshape(L.shape)
        z = z - 0.5 * ((math.log(float(obs_W)) - np.log(np.maximum(Wm, 1e-6))) / sigma_W) ** 2
    if obs_B is not None and B is not None:
        d = np.radians(np.asarray(B, dtype=np.float64).reshape(L.shape) - float(obs_B))
        z = z + kappa * (np.cos(2.0 * d) - 1.0)
    if float(np.max(z)) < -0.5 * SHAPE_MAX_SIGMA ** 2 * 2.0:
        return None
    return AP.interp_loglik(candidate_hours, np.exp(z).mean(axis=0), grid)


def _local_metres(coords_lonlat, lon0, lat0):
    c = np.asarray(coords_lonlat, dtype=np.float64)[:, :2]
    coslat = math.cos(math.radians(lat0))
    return np.column_stack([(c[:, 0] - lon0) * coslat * KM_PER_DEG_LAT * 1000.0,
                            (c[:, 1] - lat0) * KM_PER_DEG_LAT * 1000.0])


def feature_mask(feature, px_m=None, max_px=2500):
    """Rasterise a detection polygon in a local metric frame. Returns (mask, px_m) or (None, why).

    Local equirectangular metres about the polygon's own centre -- the same convention as
    polygon_major_axis_km -- which is accurate to far better than a pixel over a 30 km slick.
    """
    from shapely.geometry import shape as shp
    from shapely.ops import transform as sh_transform
    from rasterio.features import rasterize
    from rasterio.transform import Affine

    geom = (feature or {}).get("geometry")
    if not geom:
        return None, "no geometry"
    g = shp(geom)
    if g.is_empty:
        return None, "empty geometry"
    lon0, lat0 = g.centroid.x, g.centroid.y
    coslat = math.cos(math.radians(lat0))
    gm = sh_transform(lambda x, y, z=None: ((np.asarray(x) - lon0) * coslat * KM_PER_DEG_LAT * 1e3,
                                            (np.asarray(y) - lat0) * KM_PER_DEG_LAT * 1e3), g)
    xmin, ymin, xmax, ymax = gm.bounds
    extent = max(xmax - xmin, ymax - ymin)
    if px_m is None:
        px_m = max(10.0, extent / max_px)
    ncol = int(math.ceil((xmax - xmin) / px_m)) + 4
    nrow = int(math.ceil((ymax - ymin) / px_m)) + 4
    tr = Affine(px_m, 0.0, xmin - 2 * px_m, 0.0, -px_m, ymax + 2 * px_m)
    mask = rasterize([(gm, 1)], out_shape=(nrow, ncol), transform=tr, fill=0,
                     all_touched=False, dtype="uint8").astype(bool)
    if mask.sum() < 10:
        return None, f"polygon rasterises to only {int(mask.sum())} pixels at {px_m:.0f} m"
    return mask, px_m


def width_profile(feature, px_m=None):
    """Visible width along the slick's medial axis. Returns (profile, diag) or (None, diag).

    profile = {"along_m": [...], "width_m": [...]}, ordered along the principal axis. Width at
    a skeleton pixel is twice its distance to the edge -- the local full width, which for a
    sinuous filament is the width ACROSS the filament, not across the bounding box (the
    distinction that made the ellipse route wrong by 2.6x on Jacksonville).
    """
    from scipy.ndimage import distance_transform_edt
    from skimage.morphology import skeletonize

    mask, px = feature_mask(feature, px_m)
    if mask is None:
        return None, {"skipped": px}
    dist = distance_transform_edt(mask) * px
    skel = skeletonize(mask)
    rr, cc = np.nonzero(skel)
    if rr.size < 20:
        return None, {"skipped": f"medial axis has only {rr.size} pixels"}
    xy = np.column_stack([cc * px, -rr * px]).astype(np.float64)
    mr, mc = np.nonzero(mask)
    mxy = np.column_stack([mc * px, -mr * px]).astype(np.float64)
    centre = mxy.mean(axis=0)
    _, _, vt = np.linalg.svd(mxy - centre, full_matrices=False)
    along = (xy - centre) @ vt[0]
    order = np.argsort(along)
    width = 2.0 * dist[rr, cc]
    area_m2 = float(mask.sum()) * px * px
    skel_len_m = float(rr.size) * px
    return ({"along_m": along[order], "width_m": width[order]},
            {"px_m": round(px, 2), "skeleton_px": int(rr.size),
             "mean_width_m": round(area_m2 / skel_len_m, 1),
             "skeleton_length_km": round(skel_len_m / 1000.0, 3),
             "aspect": round(skel_len_m / max(area_m2 / skel_len_m, 1e-9), 2)})


def okubo_diffusivity_m2s(scale_m):
    """Okubo (1971) apparent diffusivity K = 0.0103 * l^1.15 cm^2/s, l in cm. Returned in m^2/s.

    Scale-DEPENDENT, which is the whole reason it is used here rather than step.py's flat
    10-100 m^2/s band: at a 200 m slick width Okubo gives ~0.1 m^2/s, at 10 km ~8 m^2/s. The
    flat band is sized for the kilometre-scale extent C3.1 matches; a cross-track width is two
    orders of magnitude smaller and diffuses accordingly.
    """
    return 0.0103 * (max(float(scale_m), 1.0) * 100.0) ** 1.15 * 1e-4


OKUBO_K_BOUNDS_M2S = (0.01, 200.0)


def slick_scale_m(feature):
    """The size Okubo's relation is evaluated at: sqrt(length x width) of the polygon, in m.
    One definition, used by E1 and handed to OpenOil, so both models spread at the same K."""
    L, d = slick_major_axis_km(feature)
    if not L:
        return None
    W = d.get("bbox_width_km")
    return round(1000.0 * (math.sqrt(L * W) if W else L), 1)


def okubo_member_ks(scale_m, n, rng, spread=TRACK_OKUBO_SPREAD):
    """n diffusivities for an ensemble: Okubo's K at this scale, times a stratified lognormal
    with a `spread`-fold 1-sigma factor.

    WHY THIS AND NOT A FLAT BAND (16 Sept 2026). Shape-based age is degenerate in K: the cloud
    variance grows as 2 K t, so K x 10 at t / 10 gives the same width. With K log-uniform over
    [0.05, 100] Huntington's posterior moved 0.02 nats off the prior -- nothing. Okubo's
    diffusion diagram is the standard empirical relation between a patch's size and its
    apparent diffusivity, and using it turns K from a free parameter into a measured-scale one
    with a stated factor-of-3 scatter. `scale_m` is the observed slick's size.
    """
    from statistics import NormalDist
    u = (np.arange(n) + rng.random(n)) / n
    z = np.array([NormalDist().inv_cdf(float(min(max(x, 1e-9), 1 - 1e-9))) for x in u])
    rng.shuffle(z)
    ks = okubo_diffusivity_m2s(scale_m) * np.exp(math.log(spread) * z)
    return np.clip(ks, *OKUBO_K_BOUNDS_M2S)


def track_age(feature, discharge_class=None, n_mc=4000, seed=143, grid=None):
    """E4. Age of the OLDEST visible oil in a track-shaped slick, from its cross-track width.

    A moving ship lays oil along its track. Each segment then spreads sideways by turbulent
    diffusion, sigma^2(t) = sigma_0^2 + 2 K t, so the widest end is the oldest and

        age_tail = (sigma_tail^2 - sigma_0^2) / (2 K)

    Every term is sampled from a stated range (wake sigma_0, width-per-sigma, Okubo K with a 3x
    spread, a pixel of width error), and the likelihood is the KDE of the resulting ages. This
    is what turns age_gate's `chronic` refusal into an answer: on a track the LENGTH is the
    ship's doing, but the WIDTH is still the ocean's.

    Returns (band_or_None, diag); diag["loglik"] is on age_posterior.AGE_GRID_H.
    """
    import age_posterior as AP
    grid = AP.AGE_GRID_H if grid is None else grid
    diag = {"estimator": "track_width", "discharge_class": discharge_class,
            "assumptions": {"wake_sigma_m": list(TRACK_WAKE_SIGMA_M),
                            "width_per_sigma": list(TRACK_WIDTH_PER_SIGMA),
                            "width_err_m": TRACK_WIDTH_ERR_M,
                            "okubo_spread_x": TRACK_OKUBO_SPREAD}}
    if discharge_class == "acute":
        diag["skipped"] = "discharge_class is 'acute': a point release, not a track"
        return None, diag
    prof, pdiag = width_profile(feature)
    diag["profile"] = pdiag
    if prof is None:
        diag["skipped"] = pdiag["skipped"]
        return None, diag
    if pdiag["aspect"] < TRACK_MIN_ASPECT:
        diag["skipped"] = (f"filament aspect {pdiag['aspect']} is below {TRACK_MIN_ASPECT}: "
                           f"this shape is a patch, not a track")
        return None, diag

    a, w = prof["along_m"], prof["width_m"]
    span = a.max() - a.min()
    lo_end = w[a <= a.min() + TRACK_END_FRAC * span]
    hi_end = w[a >= a.max() - TRACK_END_FRAC * span]
    w_lo, w_hi = float(np.median(lo_end)), float(np.median(hi_end))
    w_tail, w_head = max(w_lo, w_hi), min(w_lo, w_hi)
    diag.update({"width_tail_m": round(w_tail, 1), "width_head_m": round(w_head, 1),
                 "tail_over_head": round(w_tail / max(w_head, 1e-9), 2),
                 "okubo_K_at_tail_m2s": round(okubo_diffusivity_m2s(w_tail), 4)})

    rng = np.random.default_rng(seed)
    wt = np.maximum(w_tail + rng.normal(0.0, TRACK_WIDTH_ERR_M, n_mc), 1.0)
    ratio = rng.uniform(*TRACK_WIDTH_PER_SIGMA, n_mc)
    sig = wt / ratio
    sig0 = rng.uniform(*TRACK_WAKE_SIGMA_M, n_mc)
    K = np.array([okubo_diffusivity_m2s(x) for x in wt]) * np.exp(
        rng.normal(0.0, math.log(TRACK_OKUBO_SPREAD), n_mc))
    age_h = (sig ** 2 - sig0 ** 2) / (2.0 * K) / 3600.0
    lo_c = int(np.sum(age_h < grid[0]))
    hi_c = int(np.sum(age_h > grid[-1]))
    inside = age_h[(age_h >= grid[0]) & (age_h <= grid[-1])]
    ll = AP.loglik_from_samples(inside, grid, lo_censored=lo_c, hi_censored=hi_c,
                                lo_bound=float(grid[0]), hi_bound=float(grid[-1]))
    diag["loglik"] = None if ll is None else [round(float(x), 4) for x in ll]
    diag["mc"] = {"n": n_mc, "younger_than_grid": lo_c, "older_than_grid": hi_c,
                  "median_hours": round(float(np.median(age_h)), 2),
                  "p10_hours": round(float(np.percentile(age_h, 10)), 2),
                  "p90_hours": round(float(np.percentile(age_h, 90)), 2)}
    band = (max(float(np.percentile(age_h, 10)), 0.0),
            min(float(np.percentile(age_h, 90)), float(grid[-1])))
    if band[1] <= band[0]:
        return None, diag
    return band, diag


def detectability_loglik(candidate_hours, surface_fraction, lo=0.05, hi=0.30, grid=None):
    """E3. Soft upper bound from OpenOil's weathering: can this much oil still be on the surface?

    surface_fraction is (members, candidates): the fraction of released oil still floating at
    t0 (not evaporated, dispersed or stranded). A slick needs enough of it left to damp waves;
    the threshold is unknown, so it is taken as uniform on [lo, hi] and the likelihood is the
    probability the fraction clears it. An ASSUMPTION, weighted down (DEFAULT_WEIGHTS["detect"])
    and never calibrated against OpenOil twins, which would be circular.
    """
    import age_posterior as AP
    grid = AP.AGE_GRID_H if grid is None else grid
    sf = np.asarray(surface_fraction, dtype=np.float64)
    if sf.size == 0:
        return None
    sf = sf.reshape(-1, len(candidate_hours))
    lik = np.clip((sf - lo) / (hi - lo), 0.0, 1.0).mean(axis=0)
    return AP.interp_loglik(candidate_hours, lik, grid)


def sar_contrast(case_dir, feature, ring_px=3):
    """(contrast_centre_db, contrast_edge_db, diag) measured from the bundle's own SAR raster.

    Stage 2 reading a file in cases/<id>/ is the architecture, not a shortcut -- it unblocks
    C3.4 without waiting on a Stage 1 contract field. Centre = pixels deeper than `ring_px`
    inside the polygon; edge = the `ring_px`-wide band just inside the boundary; both are the
    median VV in dB minus the median of a same-width annulus OUTSIDE the polygon (clean sea).
    Returns (None, None, diag) whenever the raster or geometry does not support it.
    """
    from pathlib import Path as _P
    diag = {}
    tif = _P(case_dir) / "sar_vv_vh.tif"
    if not tif.exists():
        diag["skipped"] = "no sar_vv_vh.tif in the bundle"
        return None, None, diag
    try:
        import rasterio
        from rasterio.features import rasterize
        from shapely.geometry import shape as shp
        from scipy.ndimage import binary_erosion, binary_dilation
        with rasterio.open(tif) as src:
            vv = src.read(1).astype(np.float64)
            crs = src.crs
            tr = src.transform
            nodata = src.nodata
            desc = src.descriptions
        geom = shp(feature["geometry"])
        if crs is not None and not crs.is_geographic:
            from rasterio.warp import transform_geom
            geom = shp(transform_geom("EPSG:4326", crs, feature["geometry"]))
        inside = rasterize([(geom, 1)], out_shape=vv.shape, transform=tr, fill=0,
                           dtype="uint8").astype(bool)
        valid = np.isfinite(vv) & ((vv != nodata) if nodata is not None else True)
        if np.nanmax(vv[valid]) > 0 and np.nanmin(vv[valid]) >= 0:
            vv = 10.0 * np.log10(np.maximum(vv, 1e-6))      # linear power -> dB
            diag["converted"] = "linear -> dB"
        core = binary_erosion(inside, iterations=ring_px)
        edge = inside & ~core
        outer = binary_dilation(inside, iterations=ring_px * 2) & ~inside
        n = {k: int((m & valid).sum()) for k, m in
             (("core", core), ("edge", edge), ("sea", outer))}
        diag.update({"pixels": n, "bands": list(desc) if desc else None})
        if min(n.values()) < 10:
            diag["skipped"] = f"too few pixels for a contrast: {n}"
            return None, None, diag
        sea = float(np.median(vv[outer & valid]))
        c = float(np.median(vv[core & valid])) - sea
        e = float(np.median(vv[edge & valid])) - sea
        diag.update({"sea_db": round(sea, 2), "centre_db": round(c, 2), "edge_db": round(e, 2)})
        return c, e, diag
    except Exception as exc:                      # never let a raster quirk block the age
        diag["skipped"] = f"{type(exc).__name__}: {exc}"
        return None, None, diag


def load_calibration(path=CALIBRATION_PATH):
    """Weights and observation errors fitted by age_twins.py, or the defaults with a flag."""
    cal = {"weights": dict(DEFAULT_WEIGHTS), "sigma_L": SHAPE_SIGMA_LOG_L,
           "sigma_W": SHAPE_SIGMA_LOG_W, "kappa": SHAPE_KAPPA,
           "min_gain": None, "coverage80": None, "source": "defaults (uncalibrated)"}
    p = Path(path)
    if p.exists():
        loaded = json.loads(p.read_text())
        cal.update({k: v for k, v in loaded.items() if k != "weights"})
        cal["weights"].update(loaded.get("weights", {}))
        cal["source"] = str(p.name)
    return cal


def control_release_points(field, feature, t0, candidate_hours, timestep_minutes=15,
                           n=400, seed=143, is_land=None):
    """Where a slick of each candidate age was released: the median of a backward control
    cloud, seeded exactly as run.py seeds it, at t0 - age. One cheap run for all candidates."""
    import random
    from slick import seed_particles
    from step import integrate_stranding
    seed_pos = seed_particles(feature, n, random.Random(seed))
    n_steps = int(round(max(candidate_hours) * 60.0 / timestep_minutes)) + 1
    history, _, _ = integrate_stranding(seed_pos, t0, field, n_steps, timestep_minutes,
                                        direction="backward", is_land=is_land)
    return release_points_from_history(history, candidate_hours, timestep_minutes)


def release_points_from_history(history, candidate_hours, timestep_minutes):
    """Median control-cloud position at each candidate age. `history` is (steps, n, 2)."""
    h = np.asarray(history)
    out = []
    for t_h in candidate_hours:
        k = min(int(round(float(t_h) * 60.0 / timestep_minutes)), h.shape[0] - 1)
        out.append((float(np.median(h[k, :, 0])), float(np.median(h[k, :, 1]))))
    return out


def load_opendrift_age(out_dir, case_id):
    """OpenOil candidate curves written by opendrift_age.py (odenv), or None if absent."""
    p = Path(out_dir) / f"opendrift_age_{case_id}.npz"
    if not p.exists():
        return None
    z = np.load(p, allow_pickle=False)
    if str(z["case"]) != case_id:
        raise SystemExit(f"{p} belongs to {z['case']}, not {case_id} -- refusing to mix cases")
    return {k: z[k] for k in z.files}


def estimate_age(field, feature, t0, candidate_hours, origin_lonlat, *, release_points=None,
                 volume_m3=None, n_members=20, n_particles=SEED_PARTICLES,
                 timestep_minutes=15, seed=143, guard=True, opendrift=None,
                 contrast=(None, None), calibration=None, log=print):
    """THE AGE ENGINE. Pure: no file reads or writes. Returns (block, report).

    `block` holds exactly the origin.json keys this stage owns: age_hours, age_method,
    age_weathering, age_estimators, age_gate, and -- only when there is a measured age --
    age_posterior (Master 6.5, 16 Sept 2026). `report` is the full diagnostic record.

    Two hypotheses about what the slick IS, averaged as posteriors (age_posterior rule 2):
      patch  released at a point, spread by the ocean   -> E1 our model (+) E2 OpenOil, x E3
      track  laid by a moving ship                      -> E4 cross-track width,       x E3
    `discharge_class` decides which are live: acute -> patch, chronic -> track, else both.
    """
    import age_posterior as AP
    cal = calibration or load_calibration()
    wts = cal["weights"]
    grid = AP.AGE_GRID_H
    olon, olat = origin_lonlat
    props = feature["properties"]
    discharge = props.get("discharge_class", "unknown")
    area = float(props["area_km2"])
    elong = props.get("elongation")

    # ---- observables ----------------------------------------------------------------
    length, axis_diag = slick_major_axis_km(feature)
    width = axis_diag.get("bbox_width_km")
    bearing = axis_diag.get("orientation_deg")
    log(f"observed  L {length if length is None else round(length, 2)} km   "
        f"W {width} km   bearing {bearing} deg   ({axis_diag.get('route')})")

    # ---- E1 our model (+ the legacy C3.1 band) --------------------------------------
    if length is None:
        shear_band, shear_diag = None, {"skipped": "no observable major axis", "axis": axis_diag}
    else:
        shear_band, shear_diag = shear_dispersion_age(
            field, olon, olat, t0, length, candidate_hours, timestep_minutes=timestep_minutes,
            n_particles=n_particles, n_members=n_members, seed=seed, guard=guard,
            discharge_class=discharge, release_points=release_points,
            observed_width_km=width, observed_bearing_deg=bearing)
        shear_diag["axis"] = axis_diag
        if shear_diag.get("loglik") is not None:
            # recompute with calibrated sigmas when they differ from the defaults
            if (cal["sigma_L"], cal["sigma_W"], cal["kappa"]) != (
                    SHAPE_SIGMA_LOG_L, SHAPE_SIGMA_LOG_W, SHAPE_KAPPA):
                ll = shape_loglik(candidate_hours, shear_diag["shape_curves"]["L_km"],
                                  shear_diag["shape_curves"]["W_km"],
                                  shear_diag["shape_curves"]["bearing_deg"], length, width,
                                  bearing, cal["sigma_L"], cal["sigma_W"], cal["kappa"])
                shear_diag["loglik"] = None if ll is None else ll.tolist()
    ll_ours = None if shear_diag.get("loglik") is None else np.asarray(shear_diag["loglik"])
    log(f"E1 ours      {'likelihood' if ll_ours is not None else 'none'}   legacy band "
        f"{round_band(shear_band)}")

    # ---- E2 / E3 OpenOil -------------------------------------------------------------
    ll_od, ll_det, od_diag = None, None, {"available": opendrift is not None}
    if opendrift is not None and length is not None and discharge != "chronic":
        ch = np.asarray(opendrift["candidate_hours"], dtype=np.float64)
        ll_od = shape_loglik(ch, opendrift["L_km"], opendrift["W_km"],
                             opendrift["bearing_deg"], length, width, bearing,
                             cal["sigma_L"], cal["sigma_W"], cal["kappa"])
        od_diag["shape_loglik"] = None if ll_od is None else [round(float(x), 4) for x in ll_od]
    if opendrift is not None and "surface_fraction" in opendrift:
        ll_det = detectability_loglik(np.asarray(opendrift["candidate_hours"]),
                                      opendrift["surface_fraction"])
        od_diag["detect_loglik"] = (None if ll_det is None
                                    else [round(float(x), 4) for x in ll_det])
    log(f"E2 OpenOil   {'likelihood' if ll_od is not None else 'none'}   "
        f"E3 detectability {'likelihood' if ll_det is not None else 'none'}")

    # ---- E4 track --------------------------------------------------------------------
    track_band, track_diag = track_age(feature, discharge, seed=seed)
    ll_track = None if track_diag.get("loglik") is None else np.asarray(track_diag["loglik"])
    log(f"E4 track     {round_band(track_band)}   "
        f"{track_diag.get('skipped', track_diag.get('mc', ''))}")

    # ---- legacy diagnostics: Fay regime (veto only), elongation band -----------------
    fay_band, fay_diag = fay_age(area, volume_m3=volume_m3)
    shear_rate = deformation_rate_s(field, olon, olat, t0)
    elong_band, elong_diag = elongation_age(elong, shear_rate, discharge)

    # ---- C3.4 weathering flag, now with a measured contrast --------------------------
    wind = mean_wind_ms(field, olon, olat, t0)
    flag, weather_diag = weathering_flag(wind, contrast[0], contrast[1])

    # ---- E8 optional surrogate (weight 0 unless calibration switched it on) -----------
    ll_sur = None
    if wts.get("surrogate", 0.0) > 0:
        import age_surrogate
        ll_sur = age_surrogate.surrogate_loglik(feature, field, t0)
        log(f"E8 surrogate {'likelihood' if ll_sur is not None else 'none (no trained model)'}")

    # ---- fuse ------------------------------------------------------------------------
    shape_mix = AP.mix_logliks([ll_ours, ll_od])
    sur_w = wts.get("surrogate", 0.0)
    patch_post, patch_used = AP.fuse([("shape", shape_mix, wts["shape"]),
                                      ("detect", ll_det, wts["detect"]),
                                      ("surrogate", ll_sur, sur_w)])
    track_post, track_used = AP.fuse([("track", ll_track, wts["track"]),
                                      ("detect", ll_det, wts["detect"]),
                                      ("surrogate", ll_sur, sur_w)])
    # a hypothesis with no direct shape evidence (only E3 and/or the surrogate) is not a
    # measurement of THIS slick under that hypothesis
    if not {"shape"} & set(patch_used):
        patch_post = None
    if not {"track"} & set(track_used):
        track_post = None

    floor = cal.get("min_gain") or AP.MIN_INFO_GAIN_NATS
    mixture_note = None
    if discharge == "acute":
        post, hyp = patch_post, ["patch"]
    elif discharge == "chronic":
        post, hyp = track_post, ["track"]
    else:
        # discharge_class == "unknown": classify_discharge's elongation bands (detect/ships.py)
        # leave a real gap between "acute" (<3.0) and "chronic" (>=5.0, and straight), and a
        # slick sitting IN that gap is not evidence-free -- it is just evidence the label
        # collapsed. Averaging patch_post and track_post 50/50 assumes the two hypotheses are
        # equally likely regardless of how well either explains the observed shape.
        #
        # A first attempt weighted by each hypothesis's raw marginal likelihood (the textbook
        # Bayes-factor quantity). MEASURED, that made things worse on all three cases it was
        # meant to fix: patch (E1/E2, a Gaussian shape-likelihood model calibrated on
        # sigma_L/sigma_W/kappa) and track (E4, a Monte-Carlo width-profile sampler with its
        # own noise model) are different model FAMILIES with no shared calibration, so their
        # raw likelihood magnitudes are not on a comparable absolute scale -- one being
        # numerically larger everywhere does not mean it explains the data better, only that
        # its family's typical likelihood values run higher. On Mumbai/Jamnagar/Huntington that
        # scale mismatch consistently favoured patch, the near-uninformative hypothesis
        # (info_gain_nats 0.001-0.005) over track, the informative one (0.026-0.041) -- moving
        # the fused gain FURTHER below the 0.02 floor than the plain 50/50 average already was.
        #
        # info_gain_nats does not have that problem: it is KL(posterior_h || the SAME prior on
        # the SAME grid) for every hypothesis, so it is commensurable across families by
        # construction, independent of how either likelihood was computed. Weight by that
        # instead -- and only trust a hypothesis's contribution once it independently clears
        # the same honesty floor every other estimator in this file is held to (D9/D28's
        # pattern: an untrusted measurement does not get to vote).
        if patch_post is not None and track_post is not None:
            gp = AP.summarise(patch_post, ["patch"], min_gain=0.0)["info_gain_nats"]
            gt = AP.summarise(track_post, ["track"], min_gain=0.0)["info_gain_nats"]
            clears_patch, clears_track = gp >= floor, gt >= floor
            if clears_patch and not clears_track:
                post, hyp = patch_post, ["patch"]
                mixture_note = (
                    f"discharge_class was 'unknown' (elongation {elong:.2f} falls between the "
                    f"acute and chronic bands). Of the two hypotheses, only the patch/spreading "
                    f"one moved the prior enough to call a measurement ({gp:.3f} nats vs "
                    f"{gt:.3f} for the track hypothesis), so it alone is reported.")
            elif clears_track and not clears_patch:
                post, hyp = track_post, ["track"]
                mixture_note = (
                    f"discharge_class was 'unknown' (elongation {elong:.2f} falls between the "
                    f"acute and chronic bands). Of the two hypotheses, only the moving-source "
                    f"track one moved the prior enough to call a measurement ({gt:.3f} nats vs "
                    f"{gp:.3f} for the patch hypothesis), so it alone is reported.")
            elif clears_patch and clears_track:
                w = [gp / (gp + gt), gt / (gp + gt)]
                post = AP.average_posteriors([patch_post, track_post], weights=w)
                hyp = ["patch", "track"]
                mixture_note = (
                    f"discharge_class was 'unknown' (elongation {elong:.2f} falls between the "
                    f"acute and chronic bands). Both hypotheses independently cleared the "
                    f"information floor, so they were mixed in proportion to how much each "
                    f"moved the prior on its own: patch {w[0]:.0%}, track {w[1]:.0%}.")
            else:
                post = AP.average_posteriors([patch_post, track_post])
                hyp = ["patch", "track"]
        else:
            post = AP.average_posteriors([patch_post, track_post])
            hyp = [h for h, p in (("patch", patch_post), ("track", track_post)) if p is not None]
    summary = AP.summarise(post, hyp, min_gain=floor)

    models = []
    if ll_ours is not None:
        models.append("udgam_rk2")
    if ll_od is not None or ll_det is not None:
        models.append("opendrift_openoil")
    evidence = []
    if "patch" in hyp:
        evidence += [n for n in patch_used]
    if "track" in hyp:
        evidence += [n for n in track_used if n not in evidence]

    if summary["status"] == "ok":
        band = tuple(summary["hpd80"])
        if len(evidence) >= 2:
            method = "combined"
        else:
            method = {"shape": "shear", "track": "track"}.get(evidence[0], "combined")
    else:
        band, method = None, "none"

    gate = {"acute": "acute", "chronic": "chronic_track"}.get(discharge, "unknown_both")
    block = {
        "age_hours": round_band(band),
        "age_method": method,
        "age_weathering": flag,
        "age_estimators": {"shear": round_band(shear_band), "fay": round_band(fay_band),
                           "elongation": round_band(elong_band),
                           "track": round_band(track_band)},
        "age_gate": gate,
    }
    # Master 6.5 age_estimator_notes -- the D29 component_notes pattern, applied to the age
    # panel. Every refusal path in this file already records WHY it refused, and every one of
    # those strings was being thrown away, so the screen could only say "not applicable" four
    # times. Huntington's Fay refusal is a finding, not an absence: "gravity-viscous spreading
    # of 93.5 m3 reaches at most 0.880 km2 even at the 72 h ceiling, but the observed slick is
    # 2.64 km2 -- 3x larger ... which is independent evidence that the shear estimator is
    # modelling the right process."
    #
    # Introduces no new fact. It surfaces a string the pipeline already computed.
    _diags = {"shear": shear_diag, "fay": fay_diag,
              "elongation": elong_diag, "track": track_diag}
    notes = {}
    for _name, _band in block["age_estimators"].items():
        if _band is not None:
            continue
        _why = (_diags.get(_name) or {}).get("skipped")
        if _why:
            notes[_name] = str(_why).strip()
    if mixture_note:
        notes["mixture"] = mixture_note
    if notes:
        block["age_estimator_notes"] = notes
    if summary["status"] != "ok":
        # Master §6.5 age_refusal: WHY no age is claimed, so the panel does not have to guess.
        # "no_estimator" -- nothing produced a likelihood; "low_information" -- estimators ran but
        # the posterior barely moved off the prior, which is a refusal, not a failure.
        block["age_refusal"] = {
            "reason": "low_information" if "info_gain_nats" in summary else "no_estimator",
            "info_gain_nats": summary.get("info_gain_nats"),
            "min_gain_nats": float(cal.get("min_gain") or AP.MIN_INFO_GAIN_NATS),
        }
    if summary["status"] == "ok":
        block["age_posterior"] = {
            "hours_grid": summary["hours_grid"],
            "prob": summary["prob"],
            "hpd80": summary["hpd80"],
            "median": summary["median"],
            "hypotheses": hyp,
            "evidence": evidence,
            "models": models,
            "calibration_coverage": cal.get("coverage80"),
        }
    report = {
        "engine": "age engine v2",
        "observed": {"id": props.get("id"), "area_km2": area, "elongation": elong,
                     "discharge_class": discharge, "length_km": length, "width_km": width,
                     "bearing_deg": bearing},
        "calibration": {k: cal.get(k) for k in ("source", "weights", "sigma_L", "sigma_W",
                                                 "kappa", "min_gain", "coverage80")},
        "posterior": summary,
        "hypotheses": {"patch": {"used": patch_used,
                                 "hpd80": None if patch_post is None
                                 else list(AP.hpd(patch_post)[:2])},
                       "track": {"used": track_used,
                                 "hpd80": None if track_post is None
                                 else list(AP.hpd(track_post)[:2])}},
        "result": block,
        "shear": shear_diag,
        "opendrift": od_diag,
        "track": track_diag,
        "fay": fay_diag,
        "elongation": elong_diag,
        "weathering": weather_diag,
    }
    return block, report


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


def round_band(band, nd=3):
    """2 dp since the age grid went to 0.25 h resolution -- at 1 dp a 0.125 h band edge rounds
    to 0.1 and the validator's age_hours-vs-hpd80 equality check compares two different
    numbers."""
    if band is None:
        return None
    return [round(float(band[0]), nd), round(float(band[1]), nd)]


# ---------------------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------------------

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
    ap.add_argument("--candidates", default="2:72:4", metavar="LO:HI:STEP",
                    help="candidate ages in hours for the shear estimator. Reaches 72 h from "
                         "16 Sept 2026 (was 2:36:2) because the rewind does. The step widens "
                         "2 -> 4 to hold runtime roughly constant: candidates are separate "
                         "forward runs and the later ones are the long ones, so a 2 h step to "
                         "72 h would be ~4x the work, not 2x.")
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
    ap.add_argument("--request-only", action="store_true",
                    help="write out/age_request_<case>.json for opendrift_age.py and stop")
    ap.add_argument("--no-opendrift", action="store_true",
                    help="ignore out/opendrift_age_<case>.npz even if present")
    ap.add_argument("--patch-origin", action="store_true",
                    help="also patch the age keys into an existing origin.json "
                         "(run.py owns origin.json from v2 on; this is for iteration)")
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

    meta = json.loads((case_dir / "meta.json").read_text())
    t0 = parse_ts(meta["detection_time"])
    origin = json.loads(origin_path.read_text()) if origin_path.exists() else None

    lo, hi, step_h = (float(x) for x in a.candidates.split(":"))
    candidate_hours = sorted({1.0, *[round(x, 6) for x in np.arange(lo, hi + 1e-9, step_h)]})

    print("=" * 78)
    print(f"UDGAM Stage 2 - age engine v2   case {a.case}   t0 = "
          f"{t0.isoformat().replace('+00:00', 'Z')}")
    print("=" * 78)

    # ---- the observable ---------------------------------------------------------------
    det_path = case_dir / "detections.geojson"
    feat = None
    if det_path.exists():
        # Same slick selection as run.py, so the age is measured on the geometry the origin
        # was actually seeded from.
        feat, _ = merge_oil_features(json.loads(det_path.read_text()), mode=a.merge_oil)

    if feat is None:
        # D16: a known_origin case has no detection, so there is no slick to read an age off.
        reason = ("no oil detection to measure: "
                  + ("detections.geojson has zero oil features"
                     if det_path.exists() else "there is no detections.geojson"))
        if meta.get("known_origin") is not None:
            reason += (" -- this is a known_origin case (D16): the source is documented rather "
                       "than detected, so age is genuinely not available, not merely unmeasured.")
        print(f"\n  age_method = none\n        {reason}")
        import age_posterior as AP
        block = {"age_hours": None, "age_method": "none", "age_weathering": "unknown",
                 "age_estimators": {"shear": None, "fay": None, "elongation": None,
                                    "track": None},
                 "age_gate": "no_detection",
                 "age_refusal": {"reason": "no_detection", "info_gain_nats": None,
                                 "min_gain_nats": float(load_calibration().get("min_gain")
                                                        or AP.MIN_INFO_GAIN_NATS)}}
        _finish(a, origin_path, origin, block, {"skipped": reason, "case": a.case}, out_dir)
        return 0

    # ---- the ocean --------------------------------------------------------------------
    props = feat["properties"]
    olon, olat = float(props["centroid"][0]), float(props["centroid"][1])
    if a.real:
        field = load_case_field(a.case, repo_root=REPO)
    else:
        field = make_fake(a.field, lon0=olon, lat0=olat, wind=tuple(a.wind))
    print(f"field  {field}")

    coverage = field_time_coverage(a.case, REPO) if a.real else None
    candidate_hours, dropped, cov_detail = clip_candidates_to_coverage(
        candidate_hours, t0, coverage)
    if dropped:
        print(f"  !! DROPPED {len(dropped)} candidate ages outside the cached field: "
              f"{', '.join(f'{h:g}' for h in dropped)} h\n     {cov_detail}")
    if not candidate_hours:
        raise SystemExit(f"no candidate ages inside the cached field.\n  {cov_detail}")

    # ---- where each candidate was released --------------------------------------------
    # Our own control rewind, seeded exactly as run.py seeds it. age.py no longer needs a
    # previous origin.json to exist: the release point for candidate age t is where the
    # backward cloud was t hours ago, not a single centroid shared by every candidate.
    import coastline
    land = coastline.is_land if coastline.available() else None
    release = control_release_points(field, feat, t0, candidate_hours, a.timestep_minutes,
                                     seed=a.seed, is_land=land)
    print(f"release points  {len(release)} candidates, "
          f"{release[0][0]:.4f},{release[0][1]:.4f} (1 h) -> "
          f"{release[-1][0]:.4f},{release[-1][1]:.4f} ({candidate_hours[-1]:g} h)")

    request = {"case": a.case, "t0": meta["detection_time"],
               "candidate_hours": candidate_hours,
               "release_points": [[round(x, 5), round(y, 5)] for x, y in release],
               "slick_centroid": [olon, olat],
               "okubo_scale_m": slick_scale_m(feat),
               "timestep_minutes": a.timestep_minutes,
               "note": "read by opendrift_age.py (odenv). Working space, never in the bundle."}
    out_dir.mkdir(parents=True, exist_ok=True)
    req_path = out_dir / f"age_request_{a.case}.json"
    if not a.dry_run:
        req_path.write_text(json.dumps(request, indent=1))
        print(f"wrote  {req_path}")
    if a.request_only:
        print("--request-only: stopping here. Next, in odenv:\n"
              f"  odenv\\Scripts\\python pipeline/drift/opendrift_age.py --case {a.case}")
        return 0

    opendrift = None if a.no_opendrift else load_opendrift_age(out_dir, a.case)
    print(f"OpenOil curves  {'loaded' if opendrift is not None else 'absent -- our model only'}")

    c_centre, c_edge, cdiag = sar_contrast(case_dir, feat)
    print(f"SAR contrast    centre {c_centre}  edge {c_edge}  {cdiag.get('skipped', '')}")

    block, report = estimate_age(
        field, feat, t0, candidate_hours, (olon, olat), release_points=release,
        volume_m3=a.volume_m3, n_members=a.members, n_particles=a.particles,
        timestep_minutes=a.timestep_minutes, seed=a.seed, opendrift=opendrift,
        contrast=(c_centre, c_edge), log=lambda s: print("  " + s))
    report.update({"case": a.case, "t0": meta["detection_time"], "field": repr(field),
                   "sar_contrast": cdiag, "release_points": request["release_points"]})

    post = report["posterior"]
    print("\n" + "-" * 78)
    if post["status"] == "ok":
        print(f"age_hours = {block['age_hours']}  (80% HPD)   median {post['median']} h   "
              f"method {block['age_method']}   evidence {post['used']}"
              f"{'   MULTIMODAL' if post['multimodal'] else ''}")
        print(f"information gain {post['info_gain_nats']} nats   calibration "
              f"{report['calibration']['source']}")
    else:
        print(f"age_method = none   {post.get('reason')}")
    print("-" * 78)
    _finish(a, origin_path, origin, block, report, out_dir)
    return 0


def _finish(a, origin_path, origin, block, report, out_dir):
    """Patch the age keys into origin.json (if one exists) and drop the diagnostics sidecar.

    run.py is the primary writer of origin.json from v2 on; this path is for iteration.
    """
    report_path = out_dir / f"age_{a.case}.json"
    if a.dry_run:
        print(f"\n[dry-run] would write {report_path}")
        print(json.dumps({k: v for k, v in block.items() if k != "age_posterior"}, indent=2))
        return
    out_dir.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=1, default=_json_default))
    print(f"\n[age]  wrote   {report_path}   (working space -- not part of the bundle)")
    if origin is not None and a.patch_origin:
        origin = {k: v for k, v in origin.items() if k != "age_posterior"}
        origin.update(block)
        origin_path.write_text(json.dumps(origin))
        print(f"[age]  patched {origin_path}")


def _json_default(o):
    if isinstance(o, np.ndarray):
        return o.tolist()
    if isinstance(o, (np.floating, np.integer)):
        return o.item()
    return str(o)


if __name__ == "__main__":
    sys.exit(main())
