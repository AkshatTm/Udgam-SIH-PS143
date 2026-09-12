#!/usr/bin/env python3
"""
Phase 2 field fetcher. Owner: Anushka.

    python pipeline/drift/fetch_fields.py
    python pipeline/drift/fetch_fields.py --case case-000 --project my-ee-project

Pulls the real ocean once and caches it to `data/fields/<case>.npz`, so the rest of Phase 2
and all of Phase 3 iterate against a local file and never touch the network again.

What it fetches, over the case box and the 30 h before detection_time:
  - HYCOM/sea_water_velocity   velocity_u_0, velocity_v_0     surface current, SCALED INT
  - ECMWF/ERA5/HOURLY          u/v_component_of_wind_10m      10 m wind, already m/s

GEE serves HYCOM velocity as a raw integer with a scale factor of 0.001 and units of m/s --
i.e. millimetres per second. Divide by 1000, NOT by 100. The 100 in the older docs describes
raw HYCOM NetCDF, not Earth Engine's ingestion of it; measured against the real Ennore field
it inflates every current by 10x (median 4.8 m/s instead of 0.48 m/s). Verified 2026-09-07
against the catalog band table. The conversion happens HERE, once, on the way into the cache;
nothing downstream ever sees a scaled integer. (docs/TRAPS.md #2)

Why getRegion and not sampleRectangle: getRegion hands back an explicit longitude, latitude
and time with every single sample, so the grid axes are read off the data rather than inferred
from a projection transform. Coordinate order is the trap this component dies on (TRAPS #1);
this way there is nothing to get backwards.
"""
import argparse
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(HERE))

from check_gee import (CURRENTS, CURRENT_BANDS, WINDS, WIND_BANDS, LOOKBACK_HOURS,
                       DEFAULT_PROJECT, load_case_window, required_pad_km,
                       pad_degrees, DEFAULT_VMAX_MS)

# Native resolutions. HYCOM is 1/12 deg (~9 km); ERA5 is 0.25 deg (~28 km). Asking for finer
# than native just makes GEE resample and the download bigger for no extra information.
SCALE_CURRENTS_M = 9000
SCALE_WINDS_M = 27750

MAX_PLAUSIBLE_SPEED_MS = 3.0


def pull(ee, coll_id, bands, bbox, t0, hours, scale, label, divide_by=1.0):
    """One collection -> (lons, lats, times_utc, a, b) with a/b shaped [time, lat, lon]."""
    region = ee.Geometry.Rectangle(bbox)
    start = t0 - timedelta(hours=hours)
    coll = (ee.ImageCollection(coll_id)
            .filterBounds(region)
            .filterDate(start.strftime("%Y-%m-%dT%H:%M:%S"), t0.strftime("%Y-%m-%dT%H:%M:%S"))
            .select(bands))

    print(f"  {label}: requesting {coll_id} at {scale} m ...", flush=True)
    rows = coll.getRegion(region, scale).getInfo()
    if len(rows) < 2:
        raise SystemExit(f"{coll_id} returned no samples over {bbox}. Widen the window.")

    head = rows[0]
    ix = {name: head.index(name) for name in ("longitude", "latitude", "time")}
    ib = [head.index(b) for b in bands]
    body = rows[1:]

    # Round before uniquing: GEE returns float coords with tail jitter, and np.unique on raw
    # floats would invent hundreds of one-sample "grid lines".
    lon_all = np.round([r[ix["longitude"]] for r in body], 5)
    lat_all = np.round([r[ix["latitude"]] for r in body], 5)
    t_all = np.array([r[ix["time"]] for r in body], dtype=np.int64) // 1000   # ms -> s

    lons = np.unique(lon_all)
    lats = np.unique(lat_all)
    times = np.unique(t_all)

    a = np.full((times.size, lats.size, lons.size), np.nan)
    b = np.full_like(a, np.nan)
    li = np.searchsorted(lons, lon_all)
    ai = np.searchsorted(lats, lat_all)
    ti = np.searchsorted(times, t_all)
    for k, row in enumerate(body):
        va, vb = row[ib[0]], row[ib[1]]
        if va is not None:
            a[ti[k], ai[k], li[k]] = va / divide_by
        if vb is not None:
            b[ti[k], ai[k], li[k]] = vb / divide_by

    stamps = [datetime.fromtimestamp(int(t), tz=timezone.utc) for t in times]
    print(f"        grid {lons.size} lon x {lats.size} lat, {times.size} time step(s)")
    print(f"        {stamps[0]:%Y-%m-%d %H:%MZ} -> {stamps[-1]:%Y-%m-%d %H:%MZ}")
    if times.size > 1:
        gaps = np.diff(times) / 3600.0
        print(f"        cadence {gaps.min():.1f}-{gaps.max():.1f} h between steps")
    return lons, lats, times, a, b


def describe(label, u, v, unit="m/s"):
    """The honest look at the field. A silent unit bug shows up here as a factor of 100."""
    sp = np.hypot(u, v)
    finite = np.isfinite(sp)
    n_ok = int(finite.sum())
    if n_ok == 0:
        raise SystemExit(f"{label}: every sample is masked. Box may be entirely land.")
    s = sp[finite]
    pct_masked = 100.0 * (sp.size - n_ok) / sp.size
    print(f"\n  {label} speed ({unit})")
    print(f"        median {np.median(s):6.3f}   p90 {np.percentile(s, 90):6.3f}   "
          f"p99 {np.percentile(s, 99):6.3f}   max {s.max():6.3f}")
    print(f"        {pct_masked:.0f}% of the box is masked (land / no data)")
    return float(np.median(s)), float(np.percentile(s, 99)), float(s.max())


def main():
    ap = argparse.ArgumentParser(description="Fetch and cache real current + wind fields")
    ap.add_argument("--case", default="case-000")
    ap.add_argument("--project", default=DEFAULT_PROJECT)
    ap.add_argument("--hours", type=int, default=LOOKBACK_HOURS)
    ap.add_argument("--out", default=None, help="default data/fields/<case>.npz")
    ap.add_argument("--force", action="store_true", help="refetch even if the cache exists")
    ap.add_argument("--rewind-hours", type=float, default=24.0,
                    help="how far back run.py will rewind; the pad is sized from this")
    ap.add_argument("--vmax-ms", type=float, default=DEFAULT_VMAX_MS,
                    help="worst-case surface current for the pad. Use 2.0 for the Gulf Stream "
                         "(case-jacksonville-2024) and anywhere else fast (Phase 3.1)")
    ap.add_argument("--pad-km", type=float, default=None,
                    help="override the computed pad entirely, in km")
    a = ap.parse_args()

    out = Path(a.out) if a.out else REPO / "data" / "fields" / f"{a.case}.npz"
    if out.exists() and not a.force:
        print(f"cache already present: {out}\n(delete it or pass --force to refetch)")
        return 0
    out.parent.mkdir(parents=True, exist_ok=True)

    # Resolve the case BEFORE touching Earth Engine. A typo'd or not-yet-created case should
    # fail in a second, not after an auth round trip -- and it must never get far enough to
    # write a cache under a name it does not belong to.
    bbox, t0, origin = load_case_window(a.case, REPO / "cases",
                                        rewind_hours=a.rewind_hours,
                                        vmax_ms=a.vmax_ms, pad_km=a.pad_km)
    pad_km_used = a.pad_km if a.pad_km else required_pad_km(a.rewind_hours, a.vmax_ms)

    import ee
    ee.Initialize(project=a.project)
    print("=" * 78)
    print(f"  case    {a.case}  ({origin})")
    print(f"  region  [W {bbox[0]:.3f}, S {bbox[1]:.3f}, E {bbox[2]:.3f}, N {bbox[3]:.3f}]")
    _dlon, _dlat = pad_degrees(pad_km_used, bbox[1], bbox[3])
    print(f"  pad     {pad_km_used:.0f} km  =  {_dlon:.3f} deg lon x {_dlat:.3f} deg lat "
          f"(converted at the poleward edge, {max(abs(bbox[1]), abs(bbox[3])):.1f} deg)")
    print(f"          sized for {a.rewind_hours:.0f} h of rewind at up to {a.vmax_ms:.1f} m/s")
    print(f"  window  {(t0 - timedelta(hours=a.hours)):%Y-%m-%dT%H:%MZ}  ->  {t0:%Y-%m-%dT%H:%MZ}")
    print("=" * 78)

    # HYCOM arrives as int * 0.001 m/s. This division is the only place it happens.
    clon, clat, ctime, cu, cv = pull(ee, CURRENTS, CURRENT_BANDS, bbox, t0, a.hours,
                                     SCALE_CURRENTS_M, "currents", divide_by=1000.0)
    wlon, wlat, wtime, wu, wv = pull(ee, WINDS, WIND_BANDS, bbox, t0, a.hours,
                                     SCALE_WINDS_M, "winds", divide_by=1.0)

    c_med, c_p99, c_max = describe("current", cu, cv)
    describe("wind", wu, wv)

    np.savez_compressed(
        out,
        current_lons=clon, current_lats=clat, current_times=ctime, current_u=cu, current_v=cv,
        wind_lons=wlon, wind_lats=wlat, wind_times=wtime, wind_u=wu, wind_v=wv,
        case_id=a.case, bbox=np.array(bbox), t0_epoch=np.int64(t0.timestamp()),
        current_source=CURRENTS, wind_source=WINDS, current_units="m/s (HYCOM raw int / 1000; GEE scale 0.001)",
        fetched_at=datetime.now(timezone.utc).isoformat(),
    )
    size_mb = out.stat().st_size / 1e6
    print(f"\n  cached -> {out.relative_to(REPO)}  ({size_mb:.2f} MB)")

    print("\n" + "=" * 78)
    if c_p99 > MAX_PLAUSIBLE_SPEED_MS:
        print(f"  WARNING  99th-percentile current is {c_p99:.2f} m/s, above the "
              f"{MAX_PLAUSIBLE_SPEED_MS} m/s limit.")
        print("           A real surface current is 0-1.5 m/s. Either the /1000 scaling is")
        print("           missing, or these are land-edge pixels. Look at the quiver plot")
        print("           before trusting this field. (docs/TRAPS.md #2)")
    elif c_med > 1.5:
        print(f"  WARNING  median current {c_med:.2f} m/s is high for a coastal shelf.")
    else:
        print(f"  Current field looks like an ocean: median {c_med:.2f} m/s, max {c_max:.2f} m/s.")
    # Phase 3.1: the pad was sized from an ASSUMED worst-case speed. Now that the field is
    # here, check that assumption against the field's own p99 -- this is the only moment the
    # two numbers can be compared, and a pad that is too small is silent afterwards.
    needed_km = required_pad_km(a.rewind_hours, max(c_p99, 0.01))
    if needed_km > pad_km_used * 1.001:
        print(f"  !! PAD TOO SMALL  the field's 99th-percentile current is {c_p99:.2f} m/s, which "
              f"reaches {c_p99 * a.rewind_hours * 3.6:.0f} km in {a.rewind_hours:.0f} h.")
        print(f"                    With safety that needs a {needed_km:.0f} km pad; this cache "
              f"has {pad_km_used:.0f} km.")
        print(f"                    Particles can reach the box edge, slide along it, and produce "
              f"a plausible WRONG cloud.")
        print(f"                    Refetch:  python pipeline/drift/fetch_fields.py --case "
              f"{a.case} --vmax-ms {max(c_p99, a.vmax_ms) + 0.2:.1f} --force")
    else:
        print(f"  Pad check: p99 {c_p99:.2f} m/s needs {needed_km:.0f} km, cache has "
              f"{pad_km_used:.0f} km. OK.")
    print("  Next: python pipeline/drift/plot_quiver.py --case " + a.case)
    print("=" * 78)
    return 0


if __name__ == "__main__":
    sys.exit(main())
