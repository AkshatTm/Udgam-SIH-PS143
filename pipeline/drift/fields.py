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
  - HYCOM on GEE ships a scaled integer: catalog units m/s, scale factor 0.001. Phase 2
    divides by 1000 inside the loader, once, so nothing downstream ever sees a raw
    count. NOT 100 -- that is the raw-NetCDF convention and inflates 10x.     (TRAPS #2)
"""
from datetime import datetime, timezone

import numpy as np

# A surface current above this is not physical. HYCOM is 0-1.5 m/s in the real ocean; a value
# in the tens means the GEE scale factor (0.001) was not applied. Guard lives in step.py,
# constant lives here. This guard is what caught the /100-vs-/1000 error on 2026-09-07.
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


class GriddedField:
    """The real ocean, read from `data/fields/<case>.npz` written by fetch_fields.py.

    Exposes exactly the same two methods as ConstantField and AnalyticField, so step.py and
    run.py never learn where the numbers came from -- that is the whole design of Phase 2.

    Interpolation is bilinear in space and linear in time. Current and wind live on different
    grids with different cadences (HYCOM ~9 km daily, ERA5 ~28 km hourly), so each is
    interpolated on its own axes.

    Land is masked in HYCOM, so some grid corners are NaN. A particle whose four surrounding
    corners are not all wet falls back to the nearest wet corner rather than returning NaN --
    a NaN position silently removes a particle from the ensemble and biases the origin cloud
    towards open water. Particles that drift fully onto land are held (velocity 0), which is
    the honest answer: the model cannot say where a beached slick came from.
    """

    def __init__(self, path, wind_coeff_note=None):
        self.path = str(path)
        z = np.load(self.path, allow_pickle=False)
        self.clon = z["current_lons"]; self.clat = z["current_lats"]
        self.ctime = z["current_times"].astype(np.int64)
        self.cu = z["current_u"]; self.cv = z["current_v"]
        self.wlon = z["wind_lons"]; self.wlat = z["wind_lats"]
        self.wtime = z["wind_times"].astype(np.int64)
        self.wu = z["wind_u"]; self.wv = z["wind_v"]
        self.bbox = z["bbox"]
        self.case_id = str(z["case_id"])
        self.units = str(z["current_units"]) if "current_units" in z else "m/s"
        self._check()

    def _check(self):
        """Refuse to load a field that cannot be physical. Cheaper than debugging a heatmap."""
        sp = np.hypot(self.cu, self.cv)
        finite = sp[np.isfinite(sp)]
        if finite.size == 0:
            raise ValueError(f"{self.path}: current field is entirely masked")
        p99 = float(np.percentile(finite, 99))
        if p99 > MAX_PLAUSIBLE_SPEED_MS:
            raise ValueError(
                f"{self.path}: 99th-percentile current is {p99:.2f} m/s, above the "
                f"{MAX_PLAUSIBLE_SPEED_MS} m/s limit. GEE serves HYCOM as an integer with "
                f"scale 0.001 -- the loader must divide by 1000, not 100. (TRAPS #2)")

    def _interp(self, lons, lats, when, lon_ax, lat_ax, t_ax, A, B):
        lon, lat = _as_arrays(lons, lats)
        t = require_aware(when).timestamp()

        # --- time: linear between the two bracketing slices -------------------------------
        if t_ax.size == 1:
            k0 = k1 = 0
            wt = 0.0
        else:
            k1 = int(np.clip(np.searchsorted(t_ax, t), 1, t_ax.size - 1))
            k0 = k1 - 1
            span = float(t_ax[k1] - t_ax[k0])
            wt = 0.0 if span == 0 else float(np.clip((t - t_ax[k0]) / span, 0.0, 1.0))

        # --- space: bilinear on the [lat, lon] plane ---------------------------------------
        j = np.clip(np.searchsorted(lon_ax, lon) , 1, lon_ax.size - 1)
        i = np.clip(np.searchsorted(lat_ax, lat), 1, lat_ax.size - 1)
        x0, x1 = lon_ax[j - 1], lon_ax[j]
        y0, y1 = lat_ax[i - 1], lat_ax[i]
        fx = np.where(x1 > x0, (np.clip(lon, lon_ax[0], lon_ax[-1]) - x0) / (x1 - x0), 0.0)
        fy = np.where(y1 > y0, (np.clip(lat, lat_ax[0], lat_ax[-1]) - y0) / (y1 - y0), 0.0)

        out = []
        for F in (A, B):
            slab = F[k0] * (1.0 - wt) + F[k1] * wt if k0 != k1 else F[k0]
            c00 = slab[i - 1, j - 1]; c01 = slab[i - 1, j]
            c10 = slab[i, j - 1];     c11 = slab[i, j]
            val = ((1 - fy) * ((1 - fx) * c00 + fx * c01)
                   + fy * ((1 - fx) * c10 + fx * c11))
            # Any NaN corner poisons the whole bilinear sum -> fall back to nanmean of the
            # wet corners, then to 0.0 if the cell is entirely land.
            bad = ~np.isfinite(val)
            if bad.any():
                corners = np.stack([c00, c01, c10, c11])
                wet = np.isfinite(corners)
                n_wet = wet.sum(axis=0)
                # Cells with zero wet corners are fully inland; guard the divide rather than
                # letting nanmean warn on an empty slice.
                near = np.where(n_wet > 0,
                                np.where(wet, corners, 0.0).sum(axis=0) / np.maximum(n_wet, 1),
                                np.nan)
                val = np.where(bad, np.where(np.isfinite(near), near, 0.0), val)
            out.append(val)
        return out[0], out[1]

    def get_uv(self, lons, lats, when):
        return self._interp(lons, lats, when, self.clon, self.clat, self.ctime, self.cu, self.cv)

    def get_wind(self, lons, lats, when):
        return self._interp(lons, lats, when, self.wlon, self.wlat, self.wtime, self.wu, self.wv)

    def __repr__(self):
        return (f"GriddedField({self.case_id}, current {self.clon.size}x{self.clat.size} "
                f"x{self.ctime.size}t, wind {self.wlon.size}x{self.wlat.size}"
                f"x{self.wtime.size}t, {self.units})")


def make_fake(kind="analytic", lon0=80.35, lat0=13.25, **kw):
    """Factory behind `run.py --fake`. The real field comes from load_case_field()."""
    if kind == "constant":
        return ConstantField(**kw)
    if kind == "analytic":
        return AnalyticField(lon0, lat0, **kw)
    raise ValueError(f"unknown fake field kind {kind!r} -- use 'constant' or 'analytic'")


def load_case_field(case_id, repo_root=None, **kw):
    """The real field for a case. Phase 2 onward, this is what run.py should reach for.

    The cache is checked AGAINST THE BUNDLE before it is trusted. A file called
    `case-gulf-2019.npz` is not evidence that it holds the Gulf in 2019 -- the name is
    whatever was typed on the command line. So we re-derive the box and time from
    `cases/<id>/meta.json` + `bounds.json` and refuse a cache that disagrees.

    This catches the two ways a wrong ocean reaches the integrator: a cache fetched under a
    case that did not exist yet, and a stale cache left behind after the scene, the bounds or
    the detection time changed. Both produce a completely plausible origin cloud.
    """
    import json
    from datetime import datetime, timezone
    from pathlib import Path

    root = Path(repo_root) if repo_root else Path(__file__).resolve().parents[2]
    path = root / "data" / "fields" / f"{case_id}.npz"
    if not path.exists():
        raise SystemExit(f"no cached field at {path}\n"
                         f"run: python pipeline/drift/fetch_fields.py --case {case_id}")
    field = GriddedField(path, **kw)

    case_dir = root / "cases" / case_id
    meta_path, bounds_path = case_dir / "meta.json", case_dir / "bounds.json"
    if meta_path.exists():
        z = np.load(path, allow_pickle=False)
        meta = json.loads(meta_path.read_text())
        t0 = datetime.fromisoformat(meta["detection_time"].replace("Z", "+00:00"))
        cached_t0 = datetime.fromtimestamp(int(z["t0_epoch"]), tz=timezone.utc)
        if abs((cached_t0 - t0).total_seconds()) > 60:
            raise SystemExit(
                f"{path} was fetched for {cached_t0:%Y-%m-%dT%H:%MZ} but {case_id}'s "
                f"detection_time is {t0:%Y-%m-%dT%H:%MZ}.\n"
                f"  This cache is a different ocean than the case needs. Refetch:\n"
                f"  python pipeline/drift/fetch_fields.py --case {case_id} --force")
        if bounds_path.exists():
            b = json.loads(bounds_path.read_text())
            bb = z["bbox"]
            # the cache must COVER the scene; a wider download is fine, a shifted one is not
            if (bb[0] > b["west"] + 1e-6 or bb[1] > b["south"] + 1e-6
                    or bb[2] < b["east"] - 1e-6 or bb[3] < b["north"] - 1e-6):
                raise SystemExit(
                    f"{path} covers [W {bb[0]}, S {bb[1]}, E {bb[2]}, N {bb[3]}] which does "
                    f"not contain {case_id}'s scene "
                    f"[W {b['west']}, S {b['south']}, E {b['east']}, N {b['north']}].\n"
                    f"  This cache belongs to a different place. Refetch:\n"
                    f"  python pipeline/drift/fetch_fields.py --case {case_id} --force")
    return field


def speed(u, v):
    """Scalar speed from signed components. Use this; never build a bearing."""
    return np.hypot(np.asarray(u, dtype=np.float64), np.asarray(v, dtype=np.float64))
