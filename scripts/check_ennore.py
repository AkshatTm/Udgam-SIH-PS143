#!/usr/bin/env python3
"""
check_ennore.py — Phase 0 go/no-go. Owner: Akshat. Run this TONIGHT.

    python scripts/check_ennore.py --project YOUR-GEE-PROJECT-ID

The entire plan assumes a Sentinel-1 radar satellite passed over Ennore (~13.25 N, 80.35 E)
shortly after the 28 January 2017 tanker collision. If it did not, we change the plan tonight,
not on Monday. Everything keys off this answer.

What the verdict means (docs/01_AKSHAT_INTEGRATION.md, Phase 0):
  GREEN  scene within ~3 days  -> green-light everything, record the id in docs/receipts.md
  AMBER  only a later scene    -> still usable. The demo says "the first available pass, N days
                                  after the incident" — and that gap is literally why
                                  backtracking exists. It strengthens the pitch.
  RED    nothing within 10 days -> stop. Do not improvise. Re-plan with the US case as hero.

Set up Earth Engine access first, and do it before anything else in your day — approval is
usually minutes but has occasionally taken hours:
    earthengine.google.com -> sign up -> noncommercial / research project
    pip install earthengine-api
    earthengine authenticate
"""
import argparse
import sys
from datetime import datetime, timezone

# The Ennore collision: MT Dawn Kanchipuram / MT Maple, off Kamarajar (Ennore) Port, Chennai.
INCIDENT = datetime(2017, 1, 28, tzinfo=timezone.utc)
BBOX = [80.0, 12.9, 80.8, 13.6]          # [west, south, east, north]
START, END = "2017-01-28", "2017-02-08"


def main():
    ap = argparse.ArgumentParser(description="Phase 0 go/no-go: does a Sentinel-1 scene exist?")
    ap.add_argument("--project", required=True, help="your GEE cloud project id")
    ap.add_argument("--start", default=START)
    ap.add_argument("--end", default=END)
    ap.add_argument("--bbox", nargs=4, type=float, default=BBOX,
                    metavar=("W", "S", "E", "N"))
    ap.add_argument("--any-polarisation", action="store_true",
                    help="drop the VV filter (use only if the VV-filtered search comes back empty)")
    a = ap.parse_args()

    try:
        import ee
    except ImportError:
        raise SystemExit("earthengine-api is not installed.  pip install -r requirements.txt")

    try:
        ee.Initialize(project=a.project)
    except Exception as e:
        print(f"Could not initialise Earth Engine with project '{a.project}':\n  {e}\n")
        print("Most likely one of:")
        print("  - you have not run `earthengine authenticate` yet")
        print("  - the project id is wrong (it is the CLOUD PROJECT id, not your email)")
        print("  - the project is not yet approved for Earth Engine access")
        print("\n45-minute rule: if this is still failing in 45 minutes, stop and post the exact "
              "error text.")
        return 2

    area = ee.Geometry.Rectangle(a.bbox)
    col = (ee.ImageCollection("COPERNICUS/S1_GRD")
           .filterDate(a.start, a.end)
           .filterBounds(area)
           .filter(ee.Filter.eq("instrumentMode", "IW")))
    if not a.any_polarisation:
        col = col.filter(ee.Filter.listContains("transmitterReceiverPolarisation", "VV"))

    print(f"Searching COPERNICUS/S1_GRD")
    print(f"  area   {a.bbox}  (Ennore / Chennai coast)")
    print(f"  dates  {a.start} .. {a.end}")
    print(f"  filter IW mode" + ("" if a.any_polarisation else ", VV polarisation"))
    print("-" * 66)

    try:
        info = col.sort("system:time_start").limit(25).getInfo()
    except Exception as e:
        raise SystemExit(f"Earth Engine query failed:\n  {e}")

    feats = info.get("features", [])
    if not feats:
        print("No scenes found.\n")
        print("VERDICT: RED")
        print("  Nothing in this window. Before improvising, try widening:")
        print(f"    python {sys.argv[0]} --project {a.project} --end 2017-02-20")
        print("    (and if that is still empty, --any-polarisation)")
        print("  If it stays empty, we re-plan with the US case as the hero. Message the group.")
        return 1

    best = None
    for f in feats:
        props = f.get("properties", {})
        idx = props.get("system:index", f.get("id", "?"))
        ms = props.get("system:time_start")
        when = datetime.fromtimestamp(ms / 1000, tz=timezone.utc) if ms else None
        days = (when - INCIDENT).total_seconds() / 86400 if when else None
        pol = ",".join(props.get("transmitterReceiverPolarisation", []))
        orbit = props.get("orbitProperties_pass", "?")
        stamp = when.strftime("%Y-%m-%d %H:%M:%SZ") if when else "unknown"
        print(f"  {stamp}   +{days:5.2f} d   {orbit:<10} {pol:<8} {idx}")
        if days is not None and days >= 0 and (best is None or days < best[0]):
            best = (days, idx, stamp)

    print("-" * 66)
    print(f"{len(feats)} scene(s) found.\n")

    if best is None:
        print("VERDICT: RED — scenes exist but none after the incident date.")
        return 1

    days, idx, stamp = best
    print(f"Earliest post-incident scene:  {idx}")
    print(f"  acquired {stamp}   =  {days:.2f} days after the collision\n")

    if days <= 3:
        print("VERDICT: GREEN — green-light everything.")
    elif days <= 10:
        print(f"VERDICT: AMBER — usable. Say it plainly on stage: 'the first available "
              f"satellite pass,\n  {days:.0f} days after the incident'. That gap is exactly "
              f"why backtracking exists.")
    else:
        print(f"VERDICT: RED — nearest pass is {days:.0f} days out. Message the group before "
              f"changing anything.")

    print("\nNext:")
    print(f"  1. Record this in docs/receipts.md — a judge asking 'is this real?' gets the")
    print(f"     scene id in five seconds:   {idx}")
    print(f"  2. Export it:")
    print(f"     python pipeline/export/gee_scene.py --project {a.project} \\")
    print(f"       --scene {idx} --case case-ennore-2017")
    return 0


if __name__ == "__main__":
    sys.exit(main())
