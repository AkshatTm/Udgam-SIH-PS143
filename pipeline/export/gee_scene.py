#!/usr/bin/env python3
"""
gee_scene.py — export a Sentinel-1 scene as sar.png + bounds.json. Owner: Akshat.

    python pipeline/export/gee_scene.py --project YOUR-PROJECT \
        --scene S1A_IW_GRDH_1SDV_20170129T003... --case case-ennore-2017

Writes into cases/<case_id>/:
    sar.png       VV backscatter, dB clamped to [-25, 0], scaled to 8-bit greyscale
    bounds.json   the exact geographic box that PNG covers, plus the clamp used
    meta.json     case info (only if absent — an existing meta.json is never overwritten)

Two things that decide whether this works:

  1. THE dB CLAMP. Sentinel-1 GRD in GEE is already in decibels, typically -25..0 over sea.
     Scale with the wrong range and the PNG comes out uniformly black or white. Sea should look
     like grey static; a slick is a distinctly darker patch; land is brighter. If the image is
     flat, the clamp is wrong — that is the first thing to check, not the last.
     The clamp is written into bounds.json because Soum reads the 8-bit PNG back and must map it
     to dB with the SAME numbers. Change it here and his features shift silently
     (docs/TRAPS.md #7).

  2. RESOLUTION. Do not fight for 10 m full resolution — the download will hang or fail and the
     PNG must stay a few MB. 50-100 m/px is right for a display raster (docs/TRAPS.md #18).

Sanity check the moment it lands: OPEN THE PNG. Coastline visible on the west side, sea
speckled grey, any slick a dark streak. Then hand it to Soum.
"""
import argparse
import io
import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]

DB_MIN, DB_MAX = -25, 0          # frozen: docs/CONTRACTS.md section 3
DEFAULT_SCALE_M = 60             # metres per pixel


def main():
    ap = argparse.ArgumentParser(description="Export a Sentinel-1 scene to sar.png + bounds.json")
    ap.add_argument("--project", required=True, help="your GEE cloud project id")
    ap.add_argument("--scene", required=True,
                    help="system:index from scripts/check_ennore.py")
    ap.add_argument("--case", required=True, help="case id, e.g. case-ennore-2017")
    ap.add_argument("--cases-root", default=str(REPO / "cases"))
    ap.add_argument("--bbox", nargs=4, type=float, default=[80.0, 12.9, 80.8, 13.6],
                    metavar=("W", "S", "E", "N"),
                    help="clip box; defaults to the Ennore scene area")
    ap.add_argument("--scale", type=int, default=DEFAULT_SCALE_M,
                    help="metres per pixel (50-100 is the sane range)")
    ap.add_argument("--band", default="VV")
    ap.add_argument("--db-min", type=float, default=DB_MIN)
    ap.add_argument("--db-max", type=float, default=DB_MAX)
    ap.add_argument("--title", default=None)
    a = ap.parse_args()

    if not 20 <= a.scale <= 500:
        raise SystemExit(f"--scale {a.scale} m/px is outside the sane range. Below ~50 m the "
                         f"download hangs or fails; above ~100 m the slick stops being visible.")

    try:
        import ee
        import requests
        from PIL import Image
    except ImportError as e:
        raise SystemExit(f"missing dependency ({e.name}).  pip install -r requirements.txt")

    try:
        ee.Initialize(project=a.project)
    except Exception as e:
        raise SystemExit(f"Earth Engine init failed for project '{a.project}':\n  {e}\n"
                         f"Have you run `earthengine authenticate`?")

    img = ee.Image(f"COPERNICUS/S1_GRD/{a.scene}")
    try:
        props = img.getInfo()["properties"]
    except Exception as e:
        raise SystemExit(f"Could not load scene '{a.scene}':\n  {e}\n"
                         f"The id must be the system:index printed by scripts/check_ennore.py.")

    pols = props.get("transmitterReceiverPolarisation", [])
    if a.band not in pols:
        raise SystemExit(f"Scene has polarisations {pols}, not '{a.band}'. "
                         f"Pass --band {pols[0] if pols else 'VV'}.")

    acquired = datetime.fromtimestamp(props["system:time_start"] / 1000, tz=timezone.utc)
    region = ee.Geometry.Rectangle(a.bbox)

    # dB -> 0..255. unitScale clamps at the ends, which is exactly the behaviour we want.
    vis = (img.select(a.band)
              .clamp(a.db_min, a.db_max)
              .unitScale(a.db_min, a.db_max)
              .multiply(255).toByte()
              .clip(region))

    west, south, east, north = a.bbox
    # metres per degree at this latitude, used only to size the request
    mid_lat = (south + north) / 2
    w_px = int((east - west) * 111320 * math.cos(math.radians(mid_lat)) / a.scale)
    h_px = int((north - south) * 110540 / a.scale)
    print(f"Scene     {a.scene}")
    print(f"Acquired  {acquired.strftime('%Y-%m-%dT%H:%M:%SZ')}")
    print(f"Band      {a.band}   clamp [{a.db_min}, {a.db_max}] dB   {a.scale} m/px")
    print(f"Requesting ~{w_px} x {h_px} px ...")

    url = vis.getThumbURL({"region": region, "dimensions": f"{w_px}x{h_px}",
                           "format": "png", "min": 0, "max": 255})
    r = requests.get(url, timeout=300)
    if r.status_code != 200:
        raise SystemExit(f"Download failed ({r.status_code}). If the body mentions a size limit, "
                         f"raise --scale (fewer pixels).\n{r.text[:400]}")

    im = Image.open(io.BytesIO(r.content)).convert("L")

    case_dir = Path(a.cases_root) / a.case
    case_dir.mkdir(parents=True, exist_ok=True)
    png = case_dir / "sar.png"
    im.save(png)

    (case_dir / "bounds.json").write_text(json.dumps({
        "west": west, "south": south, "east": east, "north": north,
        "width_px": im.width, "height_px": im.height,
        "db_min": a.db_min, "db_max": a.db_max}, indent=2))

    meta_path = case_dir / "meta.json"
    if meta_path.exists():
        print(f"\n{meta_path.name} already exists — left untouched.")
    else:
        platform = props.get("platform_number")
        meta_path.write_text(json.dumps({
            "case_id": a.case,
            "title": a.title or a.case,
            "satellite": f"Sentinel-1{platform}" if platform else "Sentinel-1",
            "scene_id": a.scene,
            "detection_time": acquired.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "acts_available": ["detect"],
            "notes": "EDIT ME: add acts as stages land, and say what is and isn't available."
        }, indent=2))
        print(f"\nwrote {meta_path} — edit title/notes, and add acts as stages land.")

    stat = im.getextrema()
    px = im.load()
    mean = sum(px[x, y] for y in range(0, im.height, 16) for x in range(0, im.width, 16))
    mean /= len(range(0, im.height, 16)) * len(range(0, im.width, 16))

    print(f"wrote {png}  {im.width}x{im.height}  {png.stat().st_size / 1e6:.1f} MB")
    print(f"wrote {case_dir / 'bounds.json'}")
    print(f"\npixel range {stat}, mean {mean:.0f}")
    if stat[0] == stat[1]:
        print("WARNING: the image is a single flat value. The dB clamp is wrong.")
    elif mean < 12 or mean > 243:
        print("WARNING: the image is nearly all black or all white — check the dB clamp "
              "before handing this to Soum (docs/TRAPS.md #7).")
    else:
        print("Now OPEN THE PNG and look at it: coastline on the west side, sea like grey "
              "static,\nany slick a darker streak. Only then hand it to Soum.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
