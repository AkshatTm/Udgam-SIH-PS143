#!/usr/bin/env python3
"""
Stage 2 field sources. Owner: Anushka.

A *field source* answers two questions about a set of particle positions at one instant:

    get_uv(lons, lats, when)   -> (u, v)  surface current, m/s
    get_wind(lons, lats, when) -> (u, v)  10 m wind,       m/s

Phase 1 implements analytic sources only: no network, no GEE, no data files. Phase 2 adds a
`GriddedField` that reads `data/fields/<case>.npz` and exposes the SAME two methods, so
`step.py` and `run.py` never learn where the numbers came from.

Conventions (docs/00_MASTER_PLAN.md 3, docs/TRAPS.md):
  - Positions are [longitude, latitude] in degrees, WGS84. Never [lat, lon].  (TRAPS #1)
  - `when` is a timezone-aware UTC datetime. Naive datetimes raise.           (TRAPS #6)
  - Velocities are SIGNED COMPONENTS: u = eastward, v = northward, m/s.
    Never speed + bearing -- that conversion is where the met/ocean direction
    convention clash bites.                                                   (TRAPS #3, #4)
  - Longitudes stay in -180..180.                                             (TRAPS #5)
  - HYCOM ships cm/s. Phase 2 divides by 100 inside the loader, once, so nothing
    downstream ever sees cm/s.                                                (TRAPS #2)
"""
from datetime import datetime, timezone

import numpy as np

# A surface current above this is not physical. HYCOM is 0-1.5 m/s in the real ocean; a value
# of 50 means somebody forgot that HYCOM is cm/s. Guard lives in step.py, constant lives here.
MAX_PLAUSIBLE_SPEED_MS = 3.0


def require_aware(when):
    """Every timestamp in this project is timezone-aware UTC. Naive ones compare as if they
    were UTC right up until the moment they don't."""
    if not isinstance(when, datetime):
        raise TypeError(f"expected a datetime, got {type(when).__name__}")
    if when.tzinfo is None or when.tzinfo.utcoffset(when) is None:
        raise ValueError(f"timezone-naive datetime {when!r} -- construct it with "
                         f"tzinfo=timezone.utc, or parse with .replace('Z', '+00:00')")
    return when.astimezone(timezone.utc)


def _as_arrays(lons, lats):
    lon = np.asarray(lons, dtype=np.float64)
    lat = np.asarray(lats, dtype=np.float64)
    if lon.shape != lat.shape:
        raise ValueError(f"lons {lon.shape} and lats {lat.shape} must have the same shape")
    return lon, lat


class ConstantField:
    """A uniform, steady ocean. Not real -- but the answer is known exactly, which is the
    entire point of the Phase 1 known-answer tests."""

    def __init__(self, current=(0.0, 0.0), wind=(0.0, 0.0)):
        self.current = (float(current[0]), float(current[1]))
        self.wind = (float(wind[0]), float(wind[1]))

    def get_uv(self, lons, lats, when):
        require_aware(when)
        lon, _ = _as_arrays(lons, lats)
        return (np.full(lon.shape, self.current[0]), np.full(lon.shape, self.current[1]))

    def get_wind(self, lons, lats, when):
        require_aware(when)
        lon, _ = _as_arrays(lons, lats)
        return (np.full(lon.shape, self.wind[0]), np.full(lon.shape, self.wind[1]))

    def __repr__(self):
        return f"ConstantField(current={self.current} m/s, wind={self.wind} m/s)"


class AnalyticField:
    """A smooth, steady, spatially-varying current: a Taylor-Green vortex cell centred on
    (lon0, lat0). Divergence-free, peak speed = `amplitude`, so it behaves like a real eddy
    field without needing any data.

    Why this exists: a *constant* field makes the round-trip test pass trivially -- exact
    arithmetic reversal proves nothing about the integrator. A varying field means the
    forward and backward paths sample different velocities, so the round trip actually
    tests that backward mode is a negative dt through the same field rather than a sign
    flip on velocity.
    """

    def __init__(self, lon0, lat0, amplitude=0.5, scale_deg=0.4, wind=(0.0, 0.0)):
        self.lon0 = float(lon0)
        self.lat0 = float(lat0)
        self.amplitude = float(amplitude)
        self.scale_deg = float(scale_deg)
        self.wind = (float(wind[0]), float(wind[1]))

    def get_uv(self, lons, lats, when):
        require_aware(when)
        lon, lat = _as_arrays(lons, lats)
        x = np.pi * (lon - self.lon0) / self.scale_deg
        y = np.pi * (lat - self.lat0) / self.scale_deg
        u = self.amplitude * np.sin(y) * np.cos(x)
        v = -self.amplitude * np.cos(y) * np.sin(x)
        return (u, v)

    def get_wind(self, lons, lats, when):
        require_aware(when)
        lon, _ = _as_arrays(lons, lats)
        return (np.full(lon.shape, self.wind[0]), np.full(lon.shape, self.wind[1]))

    def __repr__(self):
        return (f"AnalyticField(centre=({self.lon0}, {self.lat0}), "
                f"amplitude={self.amplitude} m/s, scale={self.scale_deg} deg, "
                f"wind={self.wind} m/s)")


def make_fake(kind="analytic", lon0=80.35, lat0=13.25, **kw):
    """Factory behind `run.py --fake`. Phase 2 adds kind='gee' returning a GriddedField."""
    if kind == "constant":
        return ConstantField(**kw)
    if kind == "analytic":
        return AnalyticField(lon0, lat0, **kw)
    raise ValueError(f"unknown fake field kind {kind!r} -- use 'constant' or 'analytic'")


def speed(u, v):
    """Scalar speed from signed components. Use this; never build a bearing."""
    return np.hypot(np.asarray(u, dtype=np.float64), np.asarray(v, dtype=np.float64))
