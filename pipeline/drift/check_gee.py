#!/usr/bin/env python3
"""
Earth Engine preflight for Stage 2. Owner: Anushka.

    python pipeline/drift/check_gee.py
    python pipeline/drift/check_gee.py --project my-ee-project --case case-000

Answers, in about ten seconds, the four questions that can otherwise eat an evening:

  1. Is Earth Engine authenticated and initialised?
  2. Does HYCOM/sea_water_velocity actually have imagery over this case's box and dates?
  3. Does ECMWF/ERA5/HOURLY?
  4. Are the band names the ones docs/team/anushka-stage2-drift.md says they are, and are the values
     the right order of magnitude?

Question 4 is the point. Auth failing is loud. A collection quietly returning zero images over
your region, or HYCOM handing you scaled integers when you assumed metres per second, is silent --
and silent is what costs a day. (docs/TRAPS.md #2)

Run this at the top of Phase 2, and again before the US case: HYCOM's GEE archive ends
2024-09-05, and the Gulf of Mexico sits at negative longitude, so both answers change.
"""
import argparse
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]

# Anushka's noncommercial EE project. Override with --project so this script works for anyone.
DEFAULT_PROJECT = "project-c6f47846-50cd-4991-94c"

# Ennore, matching docs/team/anushka-stage2-drift.md Phase 2. [west, south, east, north]
ENNORE_BBOX = [79.5, 12.0, 81.5, 14.5]
ENNORE_T0 = datetime(2017, 1, 29, 0, 14, 0, tzinfo=timezone.utc)
LOOKBACK_HOURS = 30

CURRENTS = "HYCOM/sea_water_velocity"
CURRENT_BANDS = ["velocity_u_0", "velocity_v_0"]        # surface layer, int * 0.001 m/s
WINDS = "ECMWF/ERA5/HOURLY"
WIND_BANDS = ["u_component_of_wind_10m", "v_component_of_wind_10m"]   # signed m/s

_failures = []


def report(ok, name, detail):
    print(f"  {'PASS' if ok else 'FAIL'}  {name}")
    for line in str(detail).splitlines():
        print(f"        {line}")
    if not ok:
        _failures.append(name)
    return ok


def load_case_window(case_id, cases_root, rewind_hours=24.0,
                     vmax_ms=None, pad_km=None):
    """Take the box and time from a real case bundle. A NAMED case must exist.

    This used to fall back to the Ennore defaults when the bundle was missing, which is how
    `--case case-gulf-2019` cheerfully downloaded January 2017 Bay of Bengal water and cached
    it under the Gulf's name (2026-09-07). Nothing in the resulting file revealed the swap:
    the values were a plausible ocean, and `case_id` inside the cache said what you asked
    for, not what you got. Stage 2's whole failure mode is wrong-but-running, so a missing
    bundle is now a stop, not a shrug.

    The Ennore defaults still exist for the no-argument preflight (`check_gee.py` with no
    --case), which is a "does my Earth Engine auth work at all" smoke test, not a case run.
    """
    case_dir = Path(cases_root) / case_id
    meta_path = case_dir / "meta.json"
    bounds_path = case_dir / "bounds.json"
    if not meta_path.exists():
        raise SystemExit(
            f"no case bundle at {case_dir}\n"
            f"  {meta_path.name} is missing, so there is no box and no detection time to "
            f"fetch for.\n"
            f"  Stage 2 will NOT silently substitute another case's ocean.\n"
            f"  Akshat exports meta.json + bounds.json with the scene; ask for them, or run "
            f"against a bundle that exists (cases/case-000).")

    meta = json.loads(meta_path.read_text())
    t0 = datetime.fromisoformat(meta["detection_time"].replace("Z", "+00:00"))
    if t0.tzinfo is None:
        raise SystemExit(f"{meta_path}: detection_time is timezone-naive")

    bbox = ENNORE_BBOX
    if bounds_path.exists():
        b = json.loads(bounds_path.read_text())
        bbox = padded_bbox(b, rewind_hours=rewind_hours,
                           vmax_ms=vmax_ms or DEFAULT_VMAX_MS, pad_km=pad_km)
    return bbox, t0.astimezone(timezone.utc), f"from cases/{case_id}"


# ---------------------------------------------------------------------------------------
# The adaptive field-box pad (brief Phase 3.1, risk F2/F3b)
#
# The fields must cover where the particles drift TO, not just where the slick is. This used
# to be a flat 0.5 degrees, which is about 55 km at mid-latitude -- and the Gulf Stream at
# 2.0 m/s covers 173 km in 24 h. On case-jacksonville-2024 that is not a near miss.
#
# Two things the brief's spec gets wrong for this library, both the same root cause:
#
#   1. It says convert the pad "at mid-latitude". A degree of longitude at Gulf of Alaska
#      (59.6 N) is HALF as wide as at 30 N, so converting at mid-latitude silently halves the
#      pad in kilometres exactly where the box is hardest to get right. We convert at the
#      box edge FURTHEST from the equator, which is the worst case inside the box.
#   2. It says pad = p99_speed x rewind x safety. p99 is a property of the field we have not
#      fetched yet, so it cannot be an input to the fetch. Instead we pad from a stated
#      worst-case speed, and fetch_fields.py then MEASURES p99 and says loudly if the box it
#      just downloaded is too small for it. The guard in step.assert_inside_field_box is the
#      backstop that makes a wall-hugging cloud impossible to ship.
#
# The pad is cheap: HYCOM is 0.08 degrees, so even a 2-degree pad is ~25 cells per side. The
# GEE size ceiling that bit the export side is a 10 m SAR problem, not a 9 km field problem.
# ---------------------------------------------------------------------------------------

KM_PER_DEG_LAT = 111.32
PAD_FLOOR_KM = 55.0          # the old 0.5 deg at mid-latitude; never pad less than this
DEFAULT_VMAX_MS = 1.0        # a generous surface current for most of the ocean
PAD_SAFETY = 1.3


def required_pad_km(rewind_hours=24.0, vmax_ms=DEFAULT_VMAX_MS, safety=PAD_SAFETY,
                    floor_km=PAD_FLOOR_KM):
    """How far can a particle travel in the rewind, plus margin. Never below the floor."""
    reach_km = float(vmax_ms) * float(rewind_hours) * 3.6
    return max(float(floor_km), reach_km * float(safety))


def pad_degrees(pad_km, south, north):
    """(lon_pad_deg, lat_pad_deg) for a km pad, converted at the box's most poleward edge."""
    import math
    lat_ref = max(abs(float(south)), abs(float(north)))
    coslat = max(math.cos(math.radians(lat_ref)), 1e-6)
    return (float(pad_km) / (KM_PER_DEG_LAT * coslat),
            float(pad_km) / KM_PER_DEG_LAT)


def padded_bbox(b, rewind_hours=24.0, vmax_ms=DEFAULT_VMAX_MS, pad_km=None):
    """[W, S, E, N] for the scene bounds `b`, padded so particles cannot run out of field."""
    km = float(pad_km) if pad_km else required_pad_km(rewind_hours, vmax_ms)
    dlon, dlat = pad_degrees(km, b["south"], b["north"])
    return [b["west"] - dlon, b["south"] - dlat, b["east"] + dlon, b["north"] + dlat]


def check_collection(ee, cid, bands, bbox, t0, hours, unit_note):
    region = ee.Geometry.Rectangle(bbox)            # [west, south, east, north] = lon, lat
    start = (t0 - timedelta(hours=hours)).strftime("%Y-%m-%dT%H:%M:%S")
    end = t0.strftime("%Y-%m-%dT%H:%M:%S")

    coll = ee.ImageCollection(cid).filterBounds(region).filterDate(start, end)
    n = coll.size().getInfo()
    if n == 0:
        return report(False, f"{cid} has imagery",
                      f"ZERO images over this box between {start}Z and {end}Z.\n"
                      f"Widen the window, or the archive does not cover this date/region.")
    report(True, f"{cid} has imagery", f"{n} image(s) between {start}Z and {end}Z")

    first = ee.Image(coll.first())
    available = first.bandNames().getInfo()
    missing = [b for b in bands if b not in available]
    if missing:
        return report(False, f"{cid} band names",
                      f"missing {missing}\navailable: {available}")
    report(True, f"{cid} band names", f"{bands} present ({len(available)} bands total)")

    stats = first.select(bands).reduceRegion(
        reducer=ee.Reducer.mean(), geometry=region, scale=25000, maxPixels=1e9,
        bestEffort=True).getInfo()
    vals = {k: (round(v, 4) if isinstance(v, (int, float)) else v) for k, v in stats.items()}
    if all(v is None for v in stats.values()):
        return report(False, f"{cid} values", "every band sampled as null over this box — "
                                              "the region may be entirely land or masked")
    return report(True, f"{cid} sample values", f"{vals}\n{unit_note}")


def main():
    ap = argparse.ArgumentParser(description="Earth Engine preflight for Stage 2")
    ap.add_argument("--project", default=DEFAULT_PROJECT, help="your EE cloud project id")
    ap.add_argument("--case", default=None, help="take box and time from cases/<id>")
    ap.add_argument("--cases-root", default=str(REPO / "cases"))
    ap.add_argument("--hours", type=int, default=LOOKBACK_HOURS,
                    help="how far before detection_time to look for imagery")
    a = ap.parse_args()

    print("=" * 78)
    print("NAAP Stage 2 — Earth Engine preflight")
    print("=" * 78)

    try:
        import ee
    except ImportError:
        print("  FAIL  earthengine-api is not installed")
        print("        pip install earthengine-api      (activate your venv first)")
        return 1

    try:
        ee.Initialize(project=a.project)
        report(True, "Earth Engine initialised", f"project {a.project}")
    except Exception as e:
        report(False, "Earth Engine initialised",
               f"{type(e).__name__}: {e}\n"
               f"Try:  earthengine authenticate     then re-run.\n"
               f"If the project id is wrong, pass --project <id> (find it at "
               f"code.earthengine.google.com).\n"
               f"Stuck 45 minutes on this? Message Akshat — that is the protocol, not giving up.")
        return 1

    try:
        print(f"  ....  round trip: 1 + 1 = {ee.Number(1).add(1).getInfo()}")
    except Exception as e:
        report(False, "compute round trip", f"{type(e).__name__}: {e}")
        return 1

    if a.case:
        bbox, t0, origin = load_case_window(a.case, a.cases_root)
    else:
        bbox, t0, origin = ENNORE_BBOX, ENNORE_T0, "Ennore defaults (pass --case to override)"

    print(f"\n  region  [W {bbox[0]}, S {bbox[1]}, E {bbox[2]}, N {bbox[3]}]   ({origin})")
    print(f"  window  {(t0 - timedelta(hours=a.hours)).isoformat().replace('+00:00', 'Z')}"
          f"  ->  {t0.isoformat().replace('+00:00', 'Z')}\n")

    check_collection(ee, CURRENTS, CURRENT_BANDS, bbox, t0, a.hours,
                     "HYCOM on GEE is a SCALED INTEGER: catalog units m/s, scale 0.001. A "
                     "reading of 480 here is 0.48 m/s. Divide by 1000 in the loader, once -- "
                     "NOT by 100, which is the raw-NetCDF convention and inflates by 10x. "
                     "(docs/TRAPS.md #2)")
    print()
    check_collection(ee, WINDS, WIND_BANDS, bbox, t0, a.hours,
                     "ERA5 wind is signed u/v components in m/s, already. Not speed and bearing "
                     "— never convert to a compass direction. (docs/TRAPS.md #3, #4)")

    print("\n" + "=" * 78)
    if _failures:
        print(f"{len(_failures)} check(s) FAILED: {', '.join(_failures)}")
        print("=" * 78)
        return 1
    print("All checks passed — Phase 2 has real data waiting for it.")
    print("=" * 78)
    return 0


if __name__ == "__main__":
    sys.exit(main())
