#!/usr/bin/env python3
"""
Stage 2 known-answer tests. Owner: Anushka.

    python pipeline/drift/tests.py

Four tests. They must stay green on every change, forever, including after the real GEE
fields land in Phase 2. Wrong-but-running code is the failure mode of this component --
these exist so nobody has to catch a units bug by eye.

  1  Constant current   0.5 m/s east, no wind, 10 h  ->  18.0 km east (+/-2%)
                        x1000 off = units bug; moved north = u/v swap; west = sign bug.
  2  Round trip         forward 24 h then backward 24 h -> back within 0.5 km.
                        THE important one: it is what proves backward mode is real.
  3  Wind only          10 m/s wind, no current -> particle moves at 0.3 m/s.
  4  Plausibility       permanent guards: speed < 3 m/s, 48 h displacement 5-200 km.
                        Asserted in BOTH directions -- they must accept a real ocean and
                        reject a cm/s one, or they are decoration.
"""
import sys
import traceback
from datetime import datetime, timedelta, timezone

import numpy as np

from fields import AnalyticField, ConstantField
from step import (ImplausibleDrift, assert_displacement_plausible, assert_speed_plausible,
                  displacement_km, deg_to_m, drift_velocity, integrate)

T0 = datetime(2017, 1, 29, 0, 14, 0, tzinfo=timezone.utc)   # Ennore detection time
ENNORE = [80.35, 13.25]

_results = []


def check(name, condition, detail):
    _results.append((name, bool(condition), detail))
    print(f"  {'PASS' if condition else 'FAIL'}  {name}\n        {detail}")
    return bool(condition)


def run_for(positions, t0, field, hours, dt_min=15, direction="forward", guard=True):
    """Advect and return the FINAL state. integrate() records the state before each step, so
    reaching t0 +/- `hours` needs one extra recorded state."""
    steps = int(round(hours * 60.0 / dt_min))
    history, times = integrate(positions, t0, field, steps + 1, dt_min, direction, guard=guard)
    return history[-1], times[-1]


# ---------------------------------------------------------------------------- test 1
def test_1_constant_current():
    print("\nTest 1 - constant current, 0.5 m/s east, no wind, 10 h")
    field = ConstantField(current=(0.5, 0.0), wind=(0.0, 0.0))
    start = np.array([ENNORE], dtype=np.float64)
    end, t_end = run_for(start, T0, field, hours=10)

    dx_m, dy_m = deg_to_m(end[:, 0] - start[:, 0], end[:, 1] - start[:, 1], start[:, 1])
    east_km, north_km = float(dx_m[0]) / 1000.0, float(dy_m[0]) / 1000.0
    expected = 0.5 * 10 * 3600 / 1000.0                     # 18.0 km
    err_pct = abs(east_km - expected) / expected * 100.0

    ok = check("1a  eastward displacement is 18.0 km",
               err_pct <= 2.0,
               f"got {east_km:.4f} km, expected {expected:.1f} km ({err_pct:.3f}% error, "
               f"tolerance 2%)")
    ok &= check("1b  no northward drift (u/v not swapped)",
                abs(north_km) < 0.05,
                f"north component {north_km:+.6f} km")
    ok &= check("1c  moved EAST not west (sign convention)",
                east_km > 0,
                f"final lon {end[0, 0]:.5f} vs start {start[0, 0]:.5f}; "
                f"t_end = {t_end.isoformat().replace('+00:00', 'Z')}")
    return ok


# ---------------------------------------------------------------------------- test 2
def test_2_round_trip():
    print("\nTest 2 - round trip: forward 24 h, then backward 24 h, varying field")
    # A varying field on purpose. In a constant field the round trip is exact arithmetic
    # reversal and proves nothing.
    field = AnalyticField(ENNORE[0], ENNORE[1], amplitude=0.5, scale_deg=0.4, wind=(6.0, -4.0))
    start = np.array([
        [80.35, 13.25], [80.42, 13.31], [80.28, 13.19], [80.50, 13.40], [80.20, 13.10],
    ], dtype=np.float64)

    fwd, t_fwd = run_for(start, T0, field, hours=24, direction="forward")
    back, t_back = run_for(fwd, t_fwd, field, hours=24, direction="backward")

    err_km = displacement_km(start, back)
    travelled = displacement_km(start, fwd)
    worst = float(np.max(err_km))

    ok = check("2a  returns to the start within 0.5 km",
               worst < 0.5,
               f"worst particle off by {worst:.4f} km "
               f"(median {float(np.median(err_km)):.4f} km, n={len(start)})")
    ok &= check("2b  the trip was not trivial",
                float(np.median(travelled)) > 5.0,
                f"particles travelled a median {float(np.median(travelled)):.2f} km outbound, "
                f"so the field really was sampled")
    ok &= check("2c  time returned to t0",
                t_back == T0,
                f"t0 {T0.isoformat().replace('+00:00', 'Z')} -> forward "
                f"{t_fwd.isoformat().replace('+00:00', 'Z')} -> back "
                f"{t_back.isoformat().replace('+00:00', 'Z')}")
    return ok


# ---------------------------------------------------------------------------- test 3
def test_3_wind_only():
    print("\nTest 3 - wind only, 10 m/s, no current -> 3% of wind = 0.3 m/s")
    field = ConstantField(current=(0.0, 0.0), wind=(10.0, 0.0))
    start = np.array([ENNORE], dtype=np.float64)

    u, v = drift_velocity(start, T0, field)
    s = float(np.hypot(u, v)[0])

    end, _ = run_for(start, T0, field, hours=1)
    dx_m, _ = deg_to_m(end[:, 0] - start[:, 0], end[:, 1] - start[:, 1], start[:, 1])
    measured = float(dx_m[0]) / 3600.0                      # m travelled in 1 h -> m/s

    ok = check("3a  drift velocity is 0.30 m/s",
               abs(s - 0.3) < 0.001,
               f"got {s:.6f} m/s from a 10 m/s wind (coefficient {s / 10:.4f})")
    ok &= check("3b  and the particle actually moves at that speed",
                abs(measured - 0.3) / 0.3 * 100 < 1.0,
                f"travelled {float(dx_m[0]):.1f} m in 1 h = {measured:.6f} m/s")
    return ok


# ---------------------------------------------------------------------------- test 4
def test_4_plausibility_guards():
    print("\nTest 4 - permanent plausibility guards (these also run on real GEE fields)")
    ok = True

    # 4a: a realistic field must PASS both guards.
    field = AnalyticField(ENNORE[0], ENNORE[1], amplitude=0.5, scale_deg=0.4, wind=(6.0, -4.0))
    start = np.array([[80.35, 13.25], [80.42, 13.31], [80.28, 13.19]], dtype=np.float64)
    end, _ = run_for(start, T0, field, hours=48, direction="backward")
    try:
        median = assert_displacement_plausible(start, end, hours=48)
        ok &= check("4a  a real-looking ocean passes the 48 h guard (5-200 km)",
                    True, f"median displacement {median:.2f} km over 48 h")
    except ImplausibleDrift as e:
        ok &= check("4a  a real-looking ocean passes the 48 h guard (5-200 km)", False, str(e))

    # 4b: the cm/s bug must be REJECTED. 0.5 m/s misread from HYCOM's cm/s is 50.
    try:
        run_for(start, T0, ConstantField(current=(50.0, 0.0)), hours=1)
        ok &= check("4b  a cm/s field (50 m/s) is rejected", False,
                    "the guard did NOT fire -- the HYCOM trap would pass silently")
    except ImplausibleDrift as e:
        ok &= check("4b  a cm/s field (50 m/s) is rejected", True,
                    f"raised as expected: {str(e).splitlines()[0]}")

    # 4c: a dead field must be REJECTED too -- zero drift is as wrong as infinite drift.
    dead = ConstantField(current=(0.0, 0.0), wind=(0.0, 0.0))
    end_dead, _ = run_for(start, T0, dead, hours=48)
    try:
        assert_displacement_plausible(start, end_dead, hours=48)
        ok &= check("4c  a dead (all-zero) field is rejected", False,
                    "the guard did NOT fire on zero displacement")
    except ImplausibleDrift as e:
        ok &= check("4c  a dead (all-zero) field is rejected", True,
                    f"raised as expected: {str(e).splitlines()[0]}")

    # 4d: the speed guard's own arithmetic.
    worst = assert_speed_plausible(np.array([1.2, -0.4]), np.array([0.3, 0.9]))
    ok &= check("4d  speed guard measures the fastest particle",
                abs(worst - float(np.hypot(1.2, 0.3))) < 1e-9,
                f"max speed {worst:.4f} m/s across the set")
    return ok


def main():
    print("=" * 78)
    print("NAAP Stage 2 (drift) - Phase 1 known-answer tests")
    print(f"seed position {ENNORE} (lon, lat)   t0 = "
          f"{T0.isoformat().replace('+00:00', 'Z')}   dt = 15 min   RK2")
    print("=" * 78)

    suites = [("1  constant current", test_1_constant_current),
              ("2  round trip", test_2_round_trip),
              ("3  wind only", test_3_wind_only),
              ("4  plausibility guards", test_4_plausibility_guards)]

    passed = 0
    for name, fn in suites:
        try:
            if fn():
                passed += 1
        except Exception:
            print(f"  FAIL  {name} raised:")
            traceback.print_exc()

    print("\n" + "=" * 78)
    checks_ok = sum(1 for _, c, _ in _results if c)
    print(f"{passed}/4 tests passed   ({checks_ok}/{len(_results)} individual assertions)")
    print("=" * 78)
    if passed != 4:
        print("\nFAILING. Fix the producing code -- never the expected value.")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
