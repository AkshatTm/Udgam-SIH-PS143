#!/usr/bin/env python3
"""
Stage 2 forward-drift and seeding-geometry tests (suite 9). Owner: Anushka.

Run through the main suite — not standalone:

    python pipeline/drift/tests.py

WHY THIS SUITE EXISTS
    Phase 2 runs the model FORWARD from the slick, which is a different question from the
    rewind: not "where did this come from" but "which coast is threatened, and when". Two things
    about it fail silently, and both are tested here.

    THE TIME AXIS. fetch_fields.py used to pull detection_time - 30 h -> detection_time, so the
    cache had nothing after t0. GriddedField clamps its time index at the edge of the axis, so a
    forward step past the last snapshot re-uses that snapshot -- measured on case-000, current
    and wind are bit-identical at t0, +6 h, +12 h and +24 h. A 24 h forward run on that cache is
    one frozen snapshot advecting particles for a day, and it writes a perfectly ordinary
    particles_forward.json. 9c and 9d are the guard that makes that impossible.

    SEEDED ASHORE IS NOT LANDFALL. A particle that was already on land at t0 never made
    landfall, and counting it as one reports "first landfall 0.00 h" -- which is false, and
    which case-000 actually produces because its polygon overlaps the Chennai coast. 9g keeps
    the two apart.

    Phase 3.4 lives here too: discharge_class, not shape_class, decides the seeding geometry,
    because the thing that matters is whether the SOURCE WAS MOVING.
"""
import json
import math
from datetime import datetime, timedelta, timezone

import numpy as np

import coastline
import run as R
from fields import AnalyticField, ConstantField, load_case_field
from step import (FieldTimeSpan, assert_field_covers, displacement_km, integrate,
                  integrate_stranding)

T0 = datetime(2017, 1, 29, 0, 14, 0, tzinfo=timezone.utc)
ENNORE = [80.35, 13.25]


def _ring(lon, lat, half_len_km, half_wid_km, bearing_deg=25.0):
    """A long thin rectangle, as a GeoJSON-style ring, for seeding tests."""
    km = 111.32
    coslat = math.cos(math.radians(lat))
    a = math.radians(bearing_deg)
    ux, uy = math.sin(a) / coslat, math.cos(a)          # along-axis unit, in degrees
    vx, vy = math.cos(a) / coslat, -math.sin(a)         # across-axis unit
    L, W = half_len_km / km, half_wid_km / km
    pts = []
    for sl, sw in ((1, 1), (1, -1), (-1, -1), (-1, 1), (1, 1)):
        pts.append([lon + sl * L * ux + sw * W * vx, lat + sl * L * uy + sw * W * vy])
    return pts


def _feature(discharge, shape, area_km2=12.4, elong=8.2):
    return {"type": "Feature",
            "geometry": {"type": "Polygon",
                         "coordinates": [_ring(ENNORE[0], ENNORE[1], 8.0, 1.0)]},
            "properties": {"id": "det-t1", "classification": "oil", "confidence": 0.9,
                           "area_km2": area_km2, "elongation": elong,
                           "shape_class": shape, "discharge_class": discharge,
                           "centroid": ENNORE}}


def _aspect(points):
    """Aspect ratio of a seeded cloud, in km-space."""
    p = np.asarray(points, dtype=np.float64)
    clat = float(p[:, 1].mean())
    xy = np.column_stack([(p[:, 0] - p[:, 0].mean()) * 111.32 * math.cos(math.radians(clat)),
                          (p[:, 1] - clat) * 111.32])
    ev = np.linalg.eigvalsh(np.cov(xy, rowvar=False))
    return math.sqrt(max(ev[1], 1e-12) / max(ev[0], 1e-12))


def run(check):
    """Suite 9. `check` is tests.py's assertion recorder."""
    print("\nTest 9 - forward drift and seeding geometry (Phase 2, Phase 3.4)")
    ok = True
    import random

    # --- 9a  discharge_class outranks shape_class, and a fallback says so ---------------
    g_chronic, w_chronic = R.seed_geometry({"discharge_class": "chronic", "shape_class": "blob"})
    g_acute, w_acute = R.seed_geometry({"discharge_class": "acute", "shape_class": "linear"})
    g_unk, w_unk = R.seed_geometry({"discharge_class": "unknown", "shape_class": "linear"})
    ok &= check("9a  discharge_class decides the seeding geometry, not shape_class",
                g_chronic == "line" and g_acute == "point" and g_unk == "line"
                and "FALLING BACK" in w_unk,
                f"chronic+blob -> {g_chronic} · acute+linear -> {g_acute} · "
                f"unknown+linear -> {g_unk} and the reason says {w_unk!r}")

    # --- 9b  and the geometry really is different on the ground -------------------------
    rng = random.Random(143)
    line_pts = R.seed_particles(_feature("chronic", "blob"), 2000, rng)
    rng = random.Random(143)
    point_pts = R.seed_particles(_feature("acute", "linear"), 2000, rng)
    a_line, a_point = _aspect(line_pts), _aspect(point_pts)
    ok &= check("9b  a chronic slick seeds an elongated line, an acute one a compact point",
                a_line > 4.0 and a_point < 1.5,
                f"chronic seeding aspect {a_line:.2f}:1 (a line segment along the principal "
                f"axis, so the backward cloud comes out elongated and implies a course) vs "
                f"acute {a_point:.2f}:1 (isotropic around the centroid)")

    # --- 9c  the frozen-field bug: a forward run on a past-only cache must refuse -------
    from pathlib import Path
    field = load_case_field("case-000", repo_root=Path(__file__).resolve().parents[2])
    refused = False
    try:
        assert_field_covers(field, T0, T0 + timedelta(hours=24), "forward run")
    except FieldTimeSpan as exc:
        refused = "CLAMPED" in str(exc)
    ok &= check("9c  a forward run past the end of the cached field is REFUSED",
                refused,
                f"case-000's cache ends at the detection time, so 24 h forward is 101% "
                f"outside it. Unguarded, GriddedField clamps and every step re-uses the last "
                f"snapshot -- verified bit-identical at t0, +6 h, +12 h, +24 h")

    # --- 9d  ...but the routine 14-minute overhang is tolerated, and reported -----------
    cov = assert_field_covers(field, T0, T0 - timedelta(hours=24), "backward run")
    ok &= check("9d  a backward run passes, with its small overhang reported not hidden",
                cov is not None and 0.0 < cov[2] < 1.0,
                f"overhang {cov[2]:.2f} h -- t0 is a satellite acquisition instant and HYCOM "
                f"snapshots are on the hour, so t0 sits minutes past the last one. Tolerance "
                f"is max(1 h, 5% of span); refusing a 24 h run over a 1% clamp would be useless")

    # --- 9e  forward is a second integration, not a relabelled copy ---------------------
    afield = AnalyticField(ENNORE[0], ENNORE[1], amplitude=0.5, scale_deg=0.4, wind=(6.0, -4.0))
    seed = np.array([[80.35, 13.25], [80.40, 13.30], [80.30, 13.20]], dtype=np.float64)
    fwd, _ = integrate(seed, T0, afield, 97, 15, direction="forward")
    back, _ = integrate(seed, T0, afield, 97, 15, direction="backward")
    sep = float(np.median(displacement_km(fwd[-1], back[-1])))
    ok &= check("9e  forward and backward from the same seed land in different places",
                not np.allclose(fwd, back) and sep > 1.0,
                f"endpoints separated by a median {sep:.2f} km. The validator ERRORS if "
                f"particles_forward.json's array equals particles.json's, so a relabelled copy "
                f"is caught mechanically -- this proves there is nothing to relabel")

    # --- 9f  strand_step tells seeded-ashore (0) from landfall (>0) ---------------------
    if coastline.available():
        wfield = ConstantField(current=(-0.5, 0.0), wind=(0.0, 0.0))     # due west, into land
        mixed = np.array([[80.20, 13.25],        # already inland
                          [80.35, 13.25]],       # offshore, will beach
                         dtype=np.float64)
        _, _, stranded, step = integrate_stranding(mixed, T0, wfield, 41, 15, "forward",
                                                   is_land=coastline.is_land,
                                                   return_strand_step=True)
        ok &= check("9f  strand_step separates 'seeded ashore' from 'made landfall'",
                    bool(stranded.all()) and step[0] == 0 and step[1] > 0,
                    f"inland particle strand_step={int(step[0])} (already ashore at t0) vs "
                    f"offshore particle strand_step={int(step[1])} "
                    f"(= {int(step[1]) * 15 / 60:.2f} h after t0). Both are 'stranded'; only "
                    f"one made landfall")

        # --- 9g  and coastal_impact does not report a 0.00 h landfall ------------------
        hist, times, _, step2 = integrate_stranding(mixed, T0, wfield, 41, 15, "forward",
                                                    is_land=coastline.is_land,
                                                    return_strand_step=True)
        imp = R.coastal_impact(hist, times, step2, 15)
        fl_h = imp["first_landfall"]["hours_after_t0"] if imp["first_landfall"] else None
        ok &= check("9g  coastal_impact excludes seeded-ashore particles from landfall stats",
                    imp["seeded_ashore_fraction"] == 0.5 and imp["landfall_fraction"] == 0.5
                    and fl_h is not None and fl_h > 0.0,
                    f"seeded ashore {imp['seeded_ashore_fraction']:.2f}, landfall "
                    f"{imp['landfall_fraction']:.2f}, first landfall {fl_h:.2f} h -- not 0.00 h. "
                    f"case-000's own polygon overlaps the coast, so this is not hypothetical")
    else:
        print("        (9f, 9g skipped - no coastline available)")

    return ok
