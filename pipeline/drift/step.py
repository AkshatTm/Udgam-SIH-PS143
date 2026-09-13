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


def integrate_stranding(positions, t0, field, n_steps, timestep_minutes=15,
                        direction="backward", wind_coeff=WIND_COEFF, guard=True,
                        is_land=None, return_strand_step=False):
    """integrate(), but particles that reach land STRAND: frozen in place and flagged.

    Returns (history, times, stranded) where `stranded` is a bool array [n].

    Deliberately a SEPARATE function rather than a flag on integrate(). integrate() is called
    from run.py, tests.py, age.py, geo_tests.py and ensemble.run_once; changing its return
    arity late in integration to add an optional feature is how a working component
    stops working. This one is additive and nothing that exists has to change.

    Stranding is STICKY. Once a particle touches land it stops and stays stopped, and it is
    still stopped at the end of the run. In a backward run that is the honest model: the
    reconstruction cannot say where a beached parcel came from, so it must not invent a
    velocity that carries it inland and back out again. (Phase 4.2)
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
    stranded = np.zeros(pos.shape[0], dtype=bool)
    # step index at which each particle stranded; -1 means it never did. This is what a coastal
    # impact ETA is made of (Phase 2.3) -- the bool alone says whether, never when.
    strand_step = np.full(pos.shape[0], -1, dtype=np.int64)
    if is_land is not None:
        seeded_ashore = is_land(pos[:, 0], pos[:, 1])
        stranded |= seeded_ashore
        strand_step[seeded_ashore] = 0

    history = np.empty((n_steps, pos.shape[0], 2), dtype=np.float64)
    times = []

    for k in range(n_steps):
        history[k] = pos
        times.append(t)
        if k == n_steps - 1:
            break
        moved = rk2_step(pos, t, dt, field, wind_coeff, guard)
        if is_land is not None:
            newly = is_land(moved[:, 0], moved[:, 1]) & ~stranded
            strand_step[newly] = k + 1
            stranded |= newly
            # a stranded particle keeps its LAST WET position; it does not step onto land
            moved[stranded] = pos[stranded]
        pos = moved
        t = t + timedelta(seconds=dt)

    if return_strand_step:
        return history, times, stranded, strand_step
    return history, times, stranded


# --------------------------------------------------------------------------------------
# Permanent plausibility guards (test 4). These run on fake fields AND on the real GEE
# fields from Phase 2 onward. They are the thing that catches the HYCOM mis-scaling bug
# without anybody having to notice it by eye. (They did, on 2026-09-07.)
# --------------------------------------------------------------------------------------

class ImplausibleDrift(AssertionError):
    """Raised when the numbers describe an ocean that does not exist."""


def assert_speed_plausible(u, v, limit=MAX_PLAUSIBLE_SPEED_MS):
    """No parcel of surface water moves faster than a few m/s. A field ~10x too fast is
    HYCOM's GEE scale factor missed: the bands are int * 0.001 m/s (docs/TRAPS.md #2)."""
    s = speed(u, v)
    worst = float(np.max(s)) if s.size else 0.0
    if worst > limit:
        raise ImplausibleDrift(
            f"drift speed {worst:.2f} m/s exceeds the {limit} m/s limit. "
            f"A real surface current is 0-1.5 m/s. GEE serves HYCOM as an integer with "
            f"scale 0.001, so the loader must DIVIDE BY 1000 -- not 100, which leaves the "
            f"field 10x too fast and is what tripped this guard on 2026-09-07. "
            f"(docs/TRAPS.md #2)")
    return worst


def edge_distance_km(positions, bbox):
    """Distance from each particle to the NEAREST edge of the field box, in km.

    Negative means the particle is already outside. `bbox` is [W, S, E, N] in degrees, as
    written into the cache by fetch_fields.py and exposed as GriddedField.bbox.

    Longitude distances are converted at each particle's own latitude, which is the whole point:
    at 59.6 N a degree of longitude is half as wide as at 30 N, so a box that looks generous in
    degrees is half as generous in kilometres.
    """
    p = as_positions(positions)
    lon, lat = p[:, 0], p[:, 1]
    w, s, e, n = (float(bbox[0]), float(bbox[1]), float(bbox[2]), float(bbox[3]))
    coslat = np.maximum(np.cos(np.radians(lat)), _MIN_COS_LAT)
    km_per_deg_lon = (M_PER_DEG_LAT / 1000.0) * coslat
    km_per_deg_lat = M_PER_DEG_LAT / 1000.0
    return np.minimum.reduce([
        (lon - w) * km_per_deg_lon,
        (e - lon) * km_per_deg_lon,
        (lat - s) * km_per_deg_lat,
        (n - lat) * km_per_deg_lat,
    ])


def assert_inside_field_box(positions, bbox, margin_km=10.0, label="final positions"):
    """THE LOUD GUARD (brief Phase 3.1, risk F2/F3b). Raises if any particle finishes within
    `margin_km` of the field-box edge.

    This is the half of Phase 3.1 that matters. The adaptive pad lowers the PROBABILITY that
    particles reach the wall; this is what makes it impossible to ship a cloud that did.

    Why it has to be loud rather than a warning: a particle that runs out of field does not
    crash and does not look wrong. `GriddedField` clamps its interpolation indices at the grid
    edge, so the particle keeps moving — along the wall, at whatever the edge cell says — and
    lands somewhere entirely plausible. The Gulf Stream at 2.0 m/s covers 173 km in 24 h; the
    old fixed 0.5-degree pad was about 55 km. On `case-jacksonville-2024` that is a wrong origin
    cloud with nothing at all to announce it.
    """
    d = edge_distance_km(positions, bbox)
    worst = float(np.min(d))
    if worst >= margin_km:
        return worst
    n_touching = int(np.count_nonzero(d < margin_km))
    n_outside = int(np.count_nonzero(d < 0.0))
    raise FieldBoxEdge(
        f"{n_touching} of {d.size} {label} finished within {margin_km:.0f} km of the field-box "
        f"edge (worst {worst:.1f} km"
        + (f", {n_outside} already OUTSIDE the box" if n_outside else "")
        + f"). The box is [W {float(bbox[0]):.3f}, S {float(bbox[1]):.3f}, "
          f"E {float(bbox[2]):.3f}, N {float(bbox[3]):.3f}].\n"
        f"  These particles ran out of ocean. GriddedField clamps at the grid edge, so they did "
        f"not fail -- they slid along the wall and produced a plausible, WRONG origin cloud.\n"
        f"  Refetch with a bigger pad, then rerun:\n"
        f"    python pipeline/drift/fetch_fields.py --case <id> --vmax-ms 2.0 --force")


class FieldTimeSpan(ImplausibleDrift):
    """Raised when the cached field does not cover the time span being integrated."""


def assert_field_covers(field, t_start, t_end, label="run", tol_frac=0.05, tol_min_hours=1.0):
    """Refuse when the field's time axes do not span [t_start, t_end].

    THE BUG THIS EXISTS FOR. GriddedField clamps its time index at the edge of the axis, so a
    step past the last snapshot silently re-uses that snapshot. Measured on case-000: current
    and wind are bit-identical at t0, t0+6h, t0+12h and t0+24h, because fetch_fields.py used to
    pull only detection_time - 30 h -> detection_time. A 24 h FORWARD run through that cache is
    one frozen snapshot advecting particles for a day, and the output is a perfectly ordinary
    particles_forward.json.

    Analytic and constant fields are steady by construction and have no axes, so they pass.

    A SMALL overhang is tolerated, and that is deliberate rather than lax. `detection_time` is a
    satellite acquisition instant and HYCOM's snapshots are on the hour, so t0 routinely sits a
    few minutes past the last snapshot -- case-000's is 14 minutes past. Refusing every backward
    run over a 1% clamp would be useless. The tolerance is the larger of one hour and 5% of the
    span, which passes that and still refuses a 24 h forward run into a frozen field. A tolerated
    overhang is RETURNED so the caller can report it; it is not silently swallowed.

    Returns (cov_lo, cov_hi, overhang_hours). Raises FieldTimeSpan when the overhang is material.
    """
    ct = getattr(field, "ctime", None)
    wt = getattr(field, "wtime", None)
    if ct is None or wt is None:
        return None

    from datetime import datetime, timezone
    lo = max(int(np.min(ct)), int(np.min(wt)))
    hi = min(int(np.max(ct)), int(np.max(wt)))
    cov_lo = datetime.fromtimestamp(lo, tz=timezone.utc)
    cov_hi = datetime.fromtimestamp(hi, tz=timezone.utc)
    a, b = sorted((require_aware(t_start), require_aware(t_end)))

    short_before = max(0.0, (cov_lo - a).total_seconds() / 3600.0)
    short_after = max(0.0, (b - cov_hi).total_seconds() / 3600.0)
    overhang = short_before + short_after
    span_h = (b - a).total_seconds() / 3600.0
    tol = max(float(tol_min_hours), float(tol_frac) * span_h)

    if overhang <= tol:
        return (cov_lo, cov_hi, overhang)

    raise FieldTimeSpan(
        f"the cached field does not cover this {label}.\n"
        f"  needs     {a:%Y-%m-%dT%H:%MZ}  ->  {b:%Y-%m-%dT%H:%MZ}\n"
        f"  field has {cov_lo:%Y-%m-%dT%H:%MZ}  ->  {cov_hi:%Y-%m-%dT%H:%MZ}\n"
        + (f"  short by {short_before:.1f} h at the START\n" if short_before else "")
        + (f"  short by {short_after:.1f} h at the END\n" if short_after else "")
        + f"  overhang {overhang:.2f} h against a tolerance of {tol:.2f} h "
          f"({overhang / span_h * 100:.0f}% of a {span_h:.1f} h span)\n"
        + f"  Past the axis the field is CLAMPED, not modelled -- every step re-uses the edge\n"
          f"  snapshot and the output looks entirely normal. Refetch a wider window:\n"
          f"    python pipeline/drift/fetch_fields.py --case <id> --hours 30 "
          f"--forward-hours {max(24.0, short_after):.0f} --force")


class FieldBoxEdge(ImplausibleDrift):
    """Raised when particles reach the edge of the fetched field box."""


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
