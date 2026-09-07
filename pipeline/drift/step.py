#!/usr/bin/env python3
"""
Stage 2 integrator. Owner: Anushka.

The whole physics of this component is one line:

    velocity = current + 0.03 * wind

Everything else here is bookkeeping: RK2 in time, metres -> degrees in space, and doing it
for all 3000 particles at once with NumPy instead of a Python loop.

THE RULE THAT MATTERS
    Backward is a NEGATIVE dt through the same field. It is NOT a minus sign on velocity.
    Those two are identical in a steady uniform field and different everywhere else, which
    is exactly why the round-trip test in tests.py uses a varying field.

Positions are always an array of shape [n, 2]: column 0 = longitude, column 1 = latitude,
degrees, WGS84.  (docs/TRAPS.md #1)
"""
import numpy as np

from fields import MAX_PLAUSIBLE_SPEED_MS, require_aware, speed

# WGS84 mean metres per degree of latitude. Good to ~0.5% anywhere, which is far below the
# uncertainty the ensemble is measuring, so a spherical earth is the right simplification.
M_PER_DEG_LAT = 111320.0

# The 3% rule: floating oil moves with the current plus about 3% of the 10 m wind. This is
# the single empirical constant in Stage 2. Phase 3's ensemble perturbs it over U(0.025, 0.035);
# that spread IS the uncertainty we show.
WIND_COEFF = 0.03

# cos(lat) -> 0 at the poles and the metre->degree conversion blows up. We are working in the
# tropics, but a guard costs nothing and turns a silent infinity into a bounded number.
_MIN_COS_LAT = 1e-6


def m_to_deg(dx_m, dy_m, lats):
    """Metres east/north -> degrees lon/lat, at the given latitudes."""
    coslat = np.maximum(np.cos(np.radians(np.asarray(lats, dtype=np.float64))), _MIN_COS_LAT)
    return (np.asarray(dx_m, dtype=np.float64) / (M_PER_DEG_LAT * coslat),
            np.asarray(dy_m, dtype=np.float64) / M_PER_DEG_LAT)


def deg_to_m(dlon, dlat, lats):
    """Inverse of m_to_deg. Used by the tests and the plausibility guards to measure how far
    a particle actually went."""
    coslat = np.maximum(np.cos(np.radians(np.asarray(lats, dtype=np.float64))), _MIN_COS_LAT)
    return (np.asarray(dlon, dtype=np.float64) * M_PER_DEG_LAT * coslat,
            np.asarray(dlat, dtype=np.float64) * M_PER_DEG_LAT)


def wrap_lon(lon):
    """Keep longitudes in -180..180, once, here. Ennore at 80 E is identical in both
    conventions, so a 0..360 leak would hide until the Gulf of Mexico case."""
    return ((np.asarray(lon, dtype=np.float64) + 180.0) % 360.0) - 180.0


def as_positions(seq):
    """Coerce anything list-shaped into a validated float64 [n, 2] lon/lat array."""
    pos = np.asarray(seq, dtype=np.float64)
    if pos.ndim == 1:
        pos = pos.reshape(1, 2)
    if pos.ndim != 2 or pos.shape[1] != 2:
        raise ValueError(f"positions must be [n, 2] as [lon, lat]; got shape {pos.shape}")
    if np.any(np.abs(pos[:, 1]) > 90.0):
        raise ValueError("a latitude is outside -90..90 -- the columns are almost certainly "
                         "swapped. Positions are [longitude, latitude].")
    return pos


def drift_velocity(positions, when, field, wind_coeff=WIND_COEFF, guard=True):
    """The physics. Returns signed (u, v) in m/s for every particle."""
    require_aware(when)
    pos = as_positions(positions)
    lon, lat = pos[:, 0], pos[:, 1]

    cu, cv = field.get_uv(lon, lat, when)
    wu, wv = field.get_wind(lon, lat, when)

    u = np.asarray(cu, dtype=np.float64) + wind_coeff * np.asarray(wu, dtype=np.float64)
    v = np.asarray(cv, dtype=np.float64) + wind_coeff * np.asarray(wv, dtype=np.float64)

    if guard:
        assert_speed_plausible(u, v)
    return u, v


def rk2_step(positions, when, dt_seconds, field, wind_coeff=WIND_COEFF, guard=True):
    """One midpoint (RK2) step. `dt_seconds` is SIGNED: negative runs time backwards.

    Note that the midpoint is evaluated at `when + dt/2`, so a backward step samples the
    field half a step into the past. Same field, negative dt.
    """
    require_aware(when)
    pos = as_positions(positions)
    dt = float(dt_seconds)

    u1, v1 = drift_velocity(pos, when, field, wind_coeff, guard)
    dlon1, dlat1 = m_to_deg(u1 * dt, v1 * dt, pos[:, 1])

    mid = np.empty_like(pos)
    mid[:, 0] = wrap_lon(pos[:, 0] + 0.5 * dlon1)
    mid[:, 1] = np.clip(pos[:, 1] + 0.5 * dlat1, -90.0, 90.0)

    from datetime import timedelta
    u2, v2 = drift_velocity(mid, when + timedelta(seconds=dt / 2.0), field, wind_coeff, guard)
    dlon2, dlat2 = m_to_deg(u2 * dt, v2 * dt, mid[:, 1])

    out = np.empty_like(pos)
    out[:, 0] = wrap_lon(pos[:, 0] + dlon2)
    out[:, 1] = np.clip(pos[:, 1] + dlat2, -90.0, 90.0)
    return out


def integrate(positions, t0, field, n_steps, timestep_minutes=15, direction="backward",
              wind_coeff=WIND_COEFF, guard=True):
    """Advect every particle for `n_steps`, recording the state BEFORE each step.

    Returns (history, times):
        history : ndarray [n_steps, n, 2]  -- history[0] is the seed state at t0
        times   : list[datetime]           -- times[k] is when history[k] holds

    `n_steps` counts STORED POSITIONS, not physics steps: seeding a start and then taking N
    backward RK2 steps leaves N + 1 stored positions. Duration is therefore always
    (n_steps - 1) x timestep_minutes -- so n_steps=97 at 15 min is exactly 24.0 h.
    Never hardcode a frame count anywhere. (docs/CONTRACTS.md 5, commit 278f463)
    """
    from datetime import timedelta

    if direction not in ("forward", "backward"):
        raise ValueError(f"direction must be 'forward' or 'backward', got {direction!r}")
    if n_steps < 1:
        raise ValueError("n_steps must be at least 1")

    t = require_aware(t0)
    sign = -1.0 if direction == "backward" else 1.0
    dt = sign * float(timestep_minutes) * 60.0

    pos = as_positions(positions).copy()
    history = np.empty((n_steps, pos.shape[0], 2), dtype=np.float64)
    times = []

    for k in range(n_steps):
        history[k] = pos
        times.append(t)
        pos = rk2_step(pos, t, dt, field, wind_coeff, guard)
        t = t + timedelta(seconds=dt)

    return history, times


# --------------------------------------------------------------------------------------
# Permanent plausibility guards (test 4). These run on fake fields AND on the real GEE
# fields from Phase 2 onward. They are the thing that catches the HYCOM cm/s bug without
# anybody having to notice it by eye.
# --------------------------------------------------------------------------------------

class ImplausibleDrift(AssertionError):
    """Raised when the numbers describe an ocean that does not exist."""


def assert_speed_plausible(u, v, limit=MAX_PLAUSIBLE_SPEED_MS):
    """No parcel of surface water moves faster than a few m/s. A field 100x too fast is
    HYCOM's cm/s read as m/s (docs/TRAPS.md #2)."""
    s = speed(u, v)
    worst = float(np.max(s)) if s.size else 0.0
    if worst > limit:
        raise ImplausibleDrift(
            f"drift speed {worst:.2f} m/s exceeds the {limit} m/s limit. "
            f"A real surface current is 0-1.5 m/s. If this is ~100x too fast, the current "
            f"field is still in cm/s -- divide by 100 in the loader (docs/TRAPS.md #2).")
    return worst


def displacement_km(start, end):
    """Great-circle-ish distance per particle, in km, using the local-metre conversion."""
    a = as_positions(start)
    b = as_positions(end)
    dx, dy = deg_to_m(b[:, 0] - a[:, 0], b[:, 1] - a[:, 1], 0.5 * (a[:, 1] + b[:, 1]))
    return np.hypot(dx, dy) / 1000.0


def assert_displacement_plausible(start, end, hours, lo_km=5.0, hi_km=200.0):
    """Over 48 h a drifting parcel covers between 5 and 200 km. Metres means the field is
    dead or the timestep is wrong; thousands of km means a units bug."""
    d = displacement_km(start, end)
    scale = float(hours) / 48.0
    lo, hi = lo_km * scale, hi_km * scale
    median = float(np.median(d))
    if median < lo:
        raise ImplausibleDrift(
            f"median displacement {median:.3f} km over {hours:.1f} h is below the {lo:.1f} km "
            f"floor -- the field may be zero, or dt is wrong.")
    if median > hi:
        raise ImplausibleDrift(
            f"median displacement {median:.1f} km over {hours:.1f} h exceeds the {hi:.1f} km "
            f"ceiling -- almost certainly a units bug (docs/TRAPS.md #2).")
    return median
