#!/usr/bin/env python3
"""
inspect_db.py — read raw Sentinel-1 VV/VH dB at points, to tell a slick from a look-alike.

    python scripts/inspect_db.py --project P --scene <system:index> \
        --slick 80.37,13.19 80.38,13.17 --clean 80.42,13.22 80.30,13.25

A real oil slick sits several dB below the surrounding clean sea in BOTH VV and VH.
A low-wind look-alike is dark in VV but much closer to the sea in VH (TRAPS / PART 15).
"""
import argparse
import sys


def parse_pt(s):
    lon, lat = s.split(",")
    return [float(lon), float(lat)]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", required=True)
    ap.add_argument("--scene", required=True)
    ap.add_argument("--slick", nargs="+", type=parse_pt, default=[])
    ap.add_argument("--clean", nargs="+", type=parse_pt, default=[])
    ap.add_argument("--radius", type=float, default=90.0, help="mean over this radius (m)")
    a = ap.parse_args()

    import ee
    ee.Initialize(project=a.project)
    img = ee.Image(f"COPERNICUS/S1_GRD/{a.scene}").select(["VV", "VH"])

    def sample(pt):
        g = ee.Geometry.Point(pt).buffer(a.radius)
        d = img.reduceRegion(ee.Reducer.mean(), g, scale=10).getInfo()
        return d.get("VV"), d.get("VH")

    rows = [("SLICK", p) for p in a.slick] + [("CLEAN", p) for p in a.clean]
    print(f"{'tag':6} {'lon':>9} {'lat':>8} {'VV dB':>9} {'VH dB':>9}")
    vals = {"SLICK": [], "CLEAN": []}
    for tag, pt in rows:
        vv, vh = sample(pt)
        vals[tag].append((vv, vh))
        vv_s = f"{vv:9.2f}" if vv is not None else f"{'n/a':>9}"
        vh_s = f"{vh:9.2f}" if vh is not None else f"{'n/a':>9}"
        print(f"{tag:6} {pt[0]:9.4f} {pt[1]:8.4f} {vv_s} {vh_s}")

    def avg(xs, i):
        xs = [x[i] for x in xs if x[i] is not None]
        return sum(xs) / len(xs) if xs else None

    if vals["SLICK"] and vals["CLEAN"]:
        for i, band in enumerate(("VV", "VH")):
            s, c = avg(vals["SLICK"], i), avg(vals["CLEAN"], i)
            if s is not None and c is not None:
                print(f"  {band} damping (clean - slick): {c - s:+.2f} dB")
        print("\n  read: a real slick is several dB below clean sea in BOTH bands. "
              "Dark in VV only = probably wind.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
