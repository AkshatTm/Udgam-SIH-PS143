#!/usr/bin/env python3
"""
Stage 2 geographic-convention tests (suite 7). Owner: Anushka.

Run through the main suite — not standalone:

    python pipeline/drift/tests.py

WHY THIS SUITE EXISTS
    Every test in suites 1-6 is seeded at Ennore, 80.35 E, 13.25 N. That single position hides two
    whole classes of bug, and the locked case library contains the cases that expose both:

      NEGATIVE LONGITUDE  Four of seven cases are west of Greenwich, from -79.6 (Jacksonville) to
                          -142.7 (Gulf of Alaska). A 0-360 convention leak is invisible at +80 E
                          because 80 is 80 in both conventions. It surfaces the instant a particle
                          sits at a negative longitude, or crosses the antimeridian. (TRAPS #19,
                          brief Phase 3.2, risk F3.)

      HIGH LATITUDE       Gulf of Alaska sits at 59.5 N, where a degree of longitude is about HALF
                          as wide as at 30 N. A cos(lat) term that was a rounding error on the
                          Atlantic cases is a factor of two there. It already bit the export side:
                          a GeoTIFF in EPSG:4326 carries no cos(lat) at all, which is how a box
                          that "fit" came back 25% over GEE's ceiling. (TRAPS #19, brief A3.)

    Note that a CONSISTENTLY missing cos(lat) cancels out of displacement_km(), because m_to_deg()
    and deg_to_m() are inverses of each other -- the particle would still report 18 km. So these
    tests check the LONGITUDE DELTA against an independently computed analytic value, which is the
    only form that can catch it.

    7g is the discipline from TRAPS #19 written down as an assertion: every position in the library
    gets checked from scratch, because "it worked on the last case" does not transfer.
"""
import math
from datetime import datetime, timedelta, timezone

import numpy as np

from fields import AnalyticField, ConstantField
from check_gee import pad_degrees, required_pad_km
from step import (FieldBoxEdge, M_PER_DEG_LAT, assert_inside_field_box,
                  displacement_km, edge_distance_km, integrate, wrap_lon)

T0 = datetime(2024, 7, 30, 23, 21, 29, tzinfo=timezone.utc)   # Jacksonville detection time

# Centre of each case's scene box, from cases/<id>/bounds.json. Four west, three east, and one
# of them at 59.6 N.
LIBRARY = [
    ("jacksonville",     -79.63480, 30.38400),
    ("farallones",      -123.90630, 37.79945),
    ("huntington",      -118.11000, 33.64250),
    ("gulf-alaska",     -142.71380, 59.55550),
    ("mumbai",            72.17705, 18.50475),
    ("jamnagar",          71.87870, 20.16465),
    ("ennore-lookalike",  80.36500, 13.20000),
]

EAST_MS = 0.5          # a constant 0.5 m/s eastward current
HOURS = 10.0           # for 10 h, which is 18.0 km exactly
EXPECT_KM = EAST_MS * HOURS * 3600.0 / 1000.0


def _run(lon, lat, hours=HOURS, field=None, dt_min=15, direction="forward"):
    """Advect one particle and return (final_position, expected_lon_delta_degrees)."""
    field = field if field is not None else ConstantField(current=(EAST_MS, 0.0), wind=(0.0, 0.0))
    steps = int(round(hours * 60.0 / dt_min))
    start = np.array([[lon, lat]], dtype=np.float64)
    history, _ = integrate(start, T0, field, steps + 1, dt_min, direction)
    # Independently computed: metres east / (metres per degree of longitude AT THIS LATITUDE).
    expect_dlon = (EAST_MS * hours * 3600.0) / (M_PER_DEG_LAT * math.cos(math.radians(lat)))
    return history[-1], expect_dlon


def run(check):
    """Suite 7. `check` is tests.py's assertion recorder."""
    print("\nTest 7 - geographic conventions: negative longitude, antimeridian, high latitude")
    ok = True

    # --- 7a  a negative longitude drifts east and stays negative -------------------------
    end, expect_dlon = _run(-118.0, 33.0)
    km = float(displacement_km(np.array([[-118.0, 33.0]]), end)[0])
    lon_end = float(end[0, 0])
    ok &= check("7a  0.5 m/s east for 10 h at -118 E lands 18.0 km east",
                abs(km - EXPECT_KM) / EXPECT_KM < 0.02 and lon_end > -118.0 and lon_end < 0.0,
                f"got {km:.4f} km, expected {EXPECT_KM:.1f} km "
                f"({abs(km - EXPECT_KM) / EXPECT_KM * 100:.3f}% error); "
                f"lon -118.00000 -> {lon_end:.5f}, still west of Greenwich")

    # --- 7b  wrap_lon maps 0-360 into -180..180 and leaves -180..180 alone ---------------
    w_242 = float(wrap_lon(242.0))
    w_neg = float(wrap_lon(-118.0))
    w_181 = float(wrap_lon(180.5))
    ok &= check("7b  wrap_lon folds 0-360 to -180..180 and is idempotent on -180..180",
                abs(w_242 + 118.0) < 1e-9 and abs(w_neg + 118.0) < 1e-9
                and abs(w_181 + 179.5) < 1e-9,
                f"242.0 -> {w_242:.5f}   -118.0 -> {w_neg:.5f}   180.5 -> {w_181:.5f}. "
                f"A 0-360 leak would leave -118 as 242 and every field lookup would miss")

    # --- 7c  crossing the antimeridian wraps, it does not run past 180 ------------------
    end, _ = _run(179.9, 33.0)
    lon_end = float(end[0, 0])
    ok &= check("7c  a particle crossing the antimeridian wraps to negative longitude",
                -180.0 <= lon_end <= 180.0 and lon_end < 0.0,
                f"179.90000 + 10 h east -> {lon_end:.5f} (not 180.09; the wrap happens in "
                f"exactly one place, step.wrap_lon)")

    # --- 7d  high latitude: the LONGITUDE delta is the cos(lat) test --------------------
    lat_hi = 59.5555
    end, expect_dlon_hi = _run(-142.7138, lat_hi)
    got_dlon_hi = float(end[0, 0]) - (-142.7138)
    km_hi = float(displacement_km(np.array([[-142.7138, lat_hi]]), end)[0])
    ok &= check("7d  at 59.56 N the longitude delta matches cos(lat) analytically",
                abs(got_dlon_hi - expect_dlon_hi) / expect_dlon_hi < 0.005
                and abs(km_hi - EXPECT_KM) / EXPECT_KM < 0.02,
                f"18 km east at 59.56 N moved {got_dlon_hi:.5f} deg of longitude, analytic "
                f"{expect_dlon_hi:.5f} deg ({abs(got_dlon_hi - expect_dlon_hi) / expect_dlon_hi * 100:.3f}% "
                f"error); displacement {km_hi:.4f} km")

    # --- 7e  ...and the ratio against a mid-latitude case is the factor of two ----------
    lat_mid = 30.3840
    end_mid, _ = _run(-79.6348, lat_mid)
    got_dlon_mid = float(end_mid[0, 0]) - (-79.6348)
    ratio = got_dlon_hi / got_dlon_mid
    expect_ratio = math.cos(math.radians(lat_mid)) / math.cos(math.radians(lat_hi))
    ok &= check("7e  the same 18 km costs 1.70x more longitude at Alaska than at Jacksonville",
                abs(ratio - expect_ratio) / expect_ratio < 0.005,
                f"ratio {ratio:.4f} against cos(30.38)/cos(59.56) = {expect_ratio:.4f}. "
                f"A missing cos(lat) cancels out of displacement_km but NOT out of this")

    # --- 7f  backward mode still closes where cos(lat) is large -------------------------
    # Offset from the vortex centre on purpose: a Taylor-Green cell has exactly zero velocity
    # at (lon0, lat0), so a particle seeded there never moves and the closure is meaningless.
    field = AnalyticField(-142.7138, lat_hi, amplitude=0.5, scale_deg=0.4, wind=(6.0, -4.0))
    start = np.array([
        [-142.65, 59.60], [-142.78, 59.51], [-142.60, 59.62],
        [-142.80, 59.49], [-142.69, 59.58],
    ], dtype=np.float64)
    steps = int(round(24 * 60.0 / 15))
    fwd, times = integrate(start, T0, field, steps + 1, 15, "forward")
    back, _ = integrate(fwd[-1], times[-1], field, steps + 1, 15, "backward")
    closure = float(np.max(displacement_km(start, back[-1])))
    outbound = float(np.median(displacement_km(start, fwd[-1])))
    ok &= check("7f  24 h forward then backward closes at 59.56 N in a varying field",
                closure < 0.5 and outbound > 1.0,
                f"worst closure {closure:.4f} km after a median {outbound:.2f} km outbound; "
                f"backward mode is a negative dt through the same field, and it still holds "
                f"where a degree of longitude is half as wide")

    # --- 7g  every position in the library, from scratch (TRAPS #19) --------------------
    worst_km, worst_dlon, worst_name = 0.0, 0.0, ""
    rows = []
    for name, lon, lat in LIBRARY:
        end, expect_dlon = _run(lon, lat)
        km = float(displacement_km(np.array([[lon, lat]]), end)[0])
        got_dlon = float(end[0, 0]) - lon
        e_km = abs(km - EXPECT_KM) / EXPECT_KM
        e_dlon = abs(got_dlon - expect_dlon) / expect_dlon
        rows.append(f"{name} {e_dlon * 100:.3f}%")
        if e_km > worst_km:
            worst_km, worst_name = e_km, name
        worst_dlon = max(worst_dlon, e_dlon)
    ok &= check("7g  all seven library positions convert correctly, checked from scratch",
                worst_km < 0.02 and worst_dlon < 0.005,
                f"worst displacement error {worst_km * 100:.3f}% ({worst_name}), worst longitude "
                f"error {worst_dlon * 100:.3f}%; per-case: {', '.join(rows)}")

    # --- 7h  the adaptive pad scales with reach and respects its floor -----------------
    pad_slow = required_pad_km(24.0, 0.1)
    pad_1 = required_pad_km(24.0, 1.0)
    pad_2 = required_pad_km(24.0, 2.0)
    ok &= check("7h  the pad is sized from reach, with a floor",
                abs(pad_slow - 55.0) < 1e-9 and abs(pad_2 / pad_1 - 2.0) < 1e-9
                and pad_2 > 170.0,
                f"0.1 m/s -> {pad_slow:.0f} km (floor holds) · 1.0 m/s -> {pad_1:.0f} km · "
                f"2.0 m/s -> {pad_2:.0f} km, which covers the Gulf Stream's 173 km in 24 h")

    # --- 7i  the pad must be converted at the case's own latitude, not "mid-latitude" --
    lon_hi, lat_pad_hi = pad_degrees(pad_2, 59.5021, 59.6089)     # gulf-alaska
    lon_mid, lat_pad_mid = pad_degrees(pad_2, 30.2139, 30.5541)   # jacksonville
    pad_ratio = lon_hi / lon_mid
    expect_pad_ratio = math.cos(math.radians(30.5541)) / math.cos(math.radians(59.6089))
    ok &= check("7i  the same km pad costs 1.70x more longitude at Alaska (the brief's bug)",
                abs(pad_ratio - expect_pad_ratio) / expect_pad_ratio < 0.005
                and abs(lat_pad_hi - lat_pad_mid) < 1e-9,
                f"{pad_2:.0f} km -> {lon_hi:.3f} deg lon at Alaska vs {lon_mid:.3f} at "
                f"Jacksonville (ratio {pad_ratio:.4f}, expected {expect_pad_ratio:.4f}); "
                f"latitude pad identical at {lat_pad_hi:.3f} deg. Converting at 'mid-latitude' "
                f"as the brief says would have halved the Alaska pad in km")

    # --- 7j  the loud edge guard fires, and measures in km not degrees ----------------
    box_mid = [-80.0, 30.0, -79.0, 31.0]
    safe = np.array([[-79.5, 30.5]], dtype=np.float64)
    near = np.array([[-79.02, 30.5]], dtype=np.float64)
    safe_margin = assert_inside_field_box(safe, box_mid, margin_km=10.0)
    fired = False
    try:
        assert_inside_field_box(near, box_mid, margin_km=10.0)
    except FieldBoxEdge as exc:
        fired = True
        msg = str(exc)

    # the same 0.02 deg offset is fewer km at high latitude -- which is exactly why the guard
    # cannot be written in degrees
    box_hi = [-143.0, 59.0, -142.0, 60.0]
    d_mid = float(edge_distance_km(near, box_mid)[0])
    d_hi = float(edge_distance_km(np.array([[-142.02, 59.5]]), box_hi)[0])
    km_ratio = d_hi / d_mid
    expect_km_ratio = math.cos(math.radians(59.5)) / math.cos(math.radians(30.5))
    ok &= check("7j  the edge guard fires inside the margin and measures in km",
                fired and safe_margin > 40.0
                and abs(km_ratio - expect_km_ratio) / expect_km_ratio < 0.005,
                f"a particle {safe_margin:.1f} km inside passes; one 0.02 deg from the east "
                f"edge raises FieldBoxEdge ({d_mid:.2f} km at 30.5 N). The identical 0.02 deg "
                f"at 59.5 N is only {d_hi:.2f} km — ratio {km_ratio:.4f} vs cos ratio "
                f"{expect_km_ratio:.4f}, so a guard written in degrees would be wrong by that "
                f"factor at Alaska")

    return ok
