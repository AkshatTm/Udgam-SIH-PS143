#!/usr/bin/env python3
"""
find_scenes.py — list Sentinel-1 GRD scenes over a box in a window. Owner: Akshat.

    python scripts/find_scenes.py --project YOUR-GEE-PROJECT \
        --bbox -118.30 33.50 -117.80 33.80 --start 2021-10-01 --end 2021-10-06 \
        --incident 2021-10-02

The generalised version of check_ennore.py — no hardcoded incident, no GREEN/AMBER/RED
verdict, just the scene table. Use it for every US case (one of the four hard constraints,
Master §3.1: "Sentinel-1 coverage confirmed by running the finder script, not assumed").

Columns: UTC acquisition, orbit pass, polarisations, and — when --incident is given —
days after the incident. Then hand the winning system:index to gee_scene.py.
"""
import argparse
import sys
from datetime import datetime, timezone


def main():
    ap = argparse.ArgumentParser(description="List Sentinel-1 GRD scenes over a box/window")
    ap.add_argument("--project", required=True, help="your GEE cloud project id")
    ap.add_argument("--bbox", nargs=4, type=float, required=True,
                    metavar=("W", "S", "E", "N"), help="search box, lon/lat, WGS84")
    ap.add_argument("--start", required=True, help="YYYY-MM-DD (inclusive)")
    ap.add_argument("--end", required=True, help="YYYY-MM-DD (exclusive)")
    ap.add_argument("--incident", default=None,
                    help="YYYY-MM-DD — adds a 'days after' column and marks the first pass after it")
    ap.add_argument("--mode", default="IW", help="instrumentMode (default IW)")
    ap.add_argument("--any-polarisation", action="store_true",
                    help="drop the VV filter (only if the VV-filtered search is empty)")
    ap.add_argument("--limit", type=int, default=40)
    a = ap.parse_args()

    try:
        import ee
    except ImportError:
        raise SystemExit("earthengine-api is not installed.  pip install -r requirements.txt")
    try:
        ee.Initialize(project=a.project)
    except Exception as e:
        raise SystemExit(f"Earth Engine init failed for project '{a.project}':\n  {e}\n"
                         f"Run `earthengine authenticate` and check the project id.")

    incident = None
    if a.incident:
        incident = datetime.strptime(a.incident, "%Y-%m-%d").replace(tzinfo=timezone.utc)

    area = ee.Geometry.Rectangle(a.bbox)
    col = (ee.ImageCollection("COPERNICUS/S1_GRD")
           .filterDate(a.start, a.end)
           .filterBounds(area)
           .filter(ee.Filter.eq("instrumentMode", a.mode)))
    if not a.any_polarisation:
        col = col.filter(ee.Filter.listContains("transmitterReceiverPolarisation", "VV"))

    print("Searching COPERNICUS/S1_GRD")
    print(f"  box    {a.bbox}")
    print(f"  dates  {a.start} .. {a.end}   mode {a.mode}"
          + ("" if a.any_polarisation else "   pol VV"))
    print("-" * 78)

    try:
        info = col.sort("system:time_start").limit(a.limit).getInfo()
    except Exception as e:
        raise SystemExit(f"Earth Engine query failed:\n  {e}")

    feats = info.get("features", [])
    if not feats:
        print("No scenes found. Widen --end, or try --any-polarisation.")
        return 1

    first_after = None
    for f in feats:
        p = f.get("properties", {})
        idx = p.get("system:index", f.get("id", "?"))
        ms = p.get("system:time_start")
        when = datetime.fromtimestamp(ms / 1000, tz=timezone.utc) if ms else None
        stamp = when.strftime("%Y-%m-%d %H:%M:%SZ") if when else "unknown"
        orbit = p.get("orbitProperties_pass", "?")
        pol = ",".join(p.get("transmitterReceiverPolarisation", []))
        day_col = ""
        if incident and when:
            d = (when - incident).total_seconds() / 86400
            day_col = f"{d:+6.2f} d"
            if d >= 0 and first_after is None:
                first_after = idx
        mark = "  <-- first pass after incident" if idx == first_after and day_col else ""
        print(f"  {stamp}   {day_col:>9}   {orbit:<10} {pol:<10} {idx}{mark}")

    print("-" * 78)
    print(f"{len(feats)} scene(s). Next: pick the one covering your slick box and run")
    print(f"  python pipeline/export/gee_scene.py --project {a.project} --scene <index> "
          f"--case <case-id> --bbox W S E N")
    return 0


if __name__ == "__main__":
    sys.exit(main())
