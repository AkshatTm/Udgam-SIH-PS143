#!/usr/bin/env python3
"""
gee_scene.py — export a Sentinel-1 scene as the four case artefacts. Owner: Akshat.

    python pipeline/export/gee_scene.py --project YOUR-PROJECT \
        --scene S1A_IW_GRDH_1SDV_20170129T003... --case case-ennore-2017 \
        --bbox 80.20 13.10 80.45 13.35

Writes into cases/<case_id>/:
    sar_vv_vh.tif   2-band float32 GeoTIFF, dB, near-native resolution — Soum's REAL input
    sar.png         VV backscatter, dB-clamped to 8-bit greyscale — display only
    thumb.png       small VV preview — the gallery card
    bounds.json     the exact geographic box + the dB clamp used + vh_available
    meta.json       case info (only if absent — an existing meta.json is never overwritten)

>>> STATUS: this file has had ZERO contact with the GEE API. check_ennore.py and the earlier
>>> single-band version were never run either (docs/updates/_INTEGRATION.md). Assume the first
>>> real run needs a fixing round — band names, the getDownloadURL size ceiling, the toDrive
>>> path, argument names. That run is Akshat's and needs `earthengine authenticate` first.

Three things that decide whether this works:

  1. TWO BANDS, FLOAT32. VH is Soum's single strongest feature and the signal is ~1 dB deep;
     an 8-bit PNG quantises it to nothing (ruling D14). sar_vv_vh.tif carries the real dB
     numbers; the PNG is display only. Never hand Soum the PNG as data.

  2. THE dB CLAMP (PNG only). Sentinel-1 GRD in GEE is already in decibels, ~-25..0 over sea.
     Wrong range -> a uniformly black or white PNG. The clamp is written into bounds.json so
     Soum maps the PNG back to dB with the SAME numbers; change it here and announce it, never
     silently (docs/TRAPS.md #7). The GeoTIFF is unclamped — it holds the true values.

  3. SIZE. Tighten --bbox around the slick BEFORE dropping resolution — matching Soum's 10 m
     Zenodo training data matters more than covering extra sea. A 0.6 deg box at 10 m x 2
     float bands is several hundred MB; getDownloadURL caps at ~50 MB, so a wide box forces
     the --drive path (Export.image.toDrive, then press RUN in the Tasks tab — nothing
     downloads until you do).

Sanity check the moment it lands: OPEN THE PNG (coastline west, sea grey static, slick a dark
streak) and check `gdalinfo -stats sar_vv_vh.tif` shows two bands with sane dB ranges.
"""
import argparse
import io
import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]

DB_MIN, DB_MAX = -25, 0          # PNG clamp only; docs/CONTRACTS.md section 3
DEFAULT_PNG_SCALE_M = 60         # metres per pixel for the display PNG
DEFAULT_TIF_SCALE_M = 10         # metres per pixel for the GeoTIFF — Soum's training resolution
DOWNLOAD_URL_PIXEL_CEILING = 8_000_000   # ~ getDownloadURL practical limit for 2 float bands


def main():
    ap = argparse.ArgumentParser(description="Export a Sentinel-1 scene to the 4 case artefacts")
    ap.add_argument("--project", required=True, help="your GEE cloud project id")
    ap.add_argument("--scene", required=True, help="system:index from scripts/check_ennore.py")
    ap.add_argument("--case", required=True, help="case id, e.g. case-ennore-2017")
    ap.add_argument("--cases-root", default=str(REPO / "cases"))
    ap.add_argument("--bbox", nargs=4, type=float, default=[80.20, 13.10, 80.45, 13.35],
                    metavar=("W", "S", "E", "N"),
                    help="clip box — tighten this around the slick before touching resolution")
    ap.add_argument("--png-scale", type=int, default=DEFAULT_PNG_SCALE_M,
                    help="m/px for sar.png (50-100 is sane)")
    ap.add_argument("--tif-scale", type=int, default=DEFAULT_TIF_SCALE_M,
                    help="m/px for sar_vv_vh.tif (10 matches the Zenodo training data)")
    ap.add_argument("--db-min", type=float, default=DB_MIN, help="PNG clamp low end")
    ap.add_argument("--db-max", type=float, default=DB_MAX, help="PNG clamp high end")
    ap.add_argument("--drive", action="store_true",
                    help="force the Export.image.toDrive path for the GeoTIFF (needed for a "
                         "box too large for a direct download)")
    ap.add_argument("--no-geotiff", action="store_true",
                    help="refresh sar.png / thumb.png / bounds.json only, skip the GeoTIFF")
    ap.add_argument("--title", default=None)
    a = ap.parse_args()

    if not 20 <= a.png_scale <= 500:
        raise SystemExit(f"--png-scale {a.png_scale} m/px is outside the sane range (~50-100).")
    if not 10 <= a.tif_scale <= 100:
        raise SystemExit(f"--tif-scale {a.tif_scale} m/px is outside the sane range (10-100).")

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
        band_names = img.bandNames().getInfo()
        props = img.getInfo()["properties"]
    except Exception as e:
        raise SystemExit(f"Could not load scene '{a.scene}':\n  {e}\n"
                         f"The id must be the system:index printed by scripts/check_ennore.py.")

    have_vv = "VV" in band_names
    have_vh = "VH" in band_names
    if not have_vv:
        raise SystemExit(f"Scene bands are {band_names} — no VV. This scene is unusable.")
    if not have_vh:
        print("\n" + "!" * 70)
        print(f"!!  {a.case}: scene is VV-ONLY (bands {band_names}).")
        print("!!  TELL SOUM NOW — his vh_mean_depth_db feature is unavailable for this case,")
        print("!!  he has a VV-only fallback but the results slide must note the degradation.")
        print("!" * 70 + "\n")

    acquired = datetime.fromtimestamp(props["system:time_start"] / 1000, tz=timezone.utc)
    west, south, east, north = a.bbox
    region = ee.Geometry.Rectangle(a.bbox)
    mid_lat = (south + north) / 2

    def px(scale_m):
        w = int((east - west) * 111320 * math.cos(math.radians(mid_lat)) / scale_m)
        h = int((north - south) * 110540 / scale_m)
        return w, h

    print(f"Scene     {a.scene}")
    print(f"Acquired  {acquired.strftime('%Y-%m-%dT%H:%M:%SZ')}")
    print(f"Bands     {band_names}   ({'VV+VH' if have_vh else 'VV only'})")

    case_dir = Path(a.cases_root) / a.case
    case_dir.mkdir(parents=True, exist_ok=True)

    # ---- sar.png + thumb.png : VV, dB-clamped, 8-bit, display only ----------------------
    vv_disp = (img.select("VV").clamp(a.db_min, a.db_max)
               .unitScale(a.db_min, a.db_max).multiply(255).toByte().clip(region))
    w_px, h_px = px(a.png_scale)
    print(f"PNG       ~{w_px} x {h_px} px @ {a.png_scale} m/px, clamp [{a.db_min}, {a.db_max}] dB")
    url = vv_disp.getThumbURL({"region": region, "dimensions": f"{w_px}x{h_px}",
                               "format": "png", "min": 0, "max": 255})
    r = requests.get(url, timeout=300)
    if r.status_code != 200:
        raise SystemExit(f"PNG download failed ({r.status_code}). Raise --png-scale.\n{r.text[:400]}")
    im = Image.open(io.BytesIO(r.content)).convert("L")
    im.save(case_dir / "sar.png")

    turl = vv_disp.getThumbURL({"region": region, "dimensions": "480x480",
                                "format": "png", "min": 0, "max": 255})
    tr = requests.get(turl, timeout=120)
    if tr.status_code == 200:
        Image.open(io.BytesIO(tr.content)).convert("L").save(case_dir / "thumb.png")
        print(f"          wrote sar.png ({im.width}x{im.height}) + thumb.png")
    else:
        print(f"          wrote sar.png ({im.width}x{im.height}); thumb.png failed ({tr.status_code})")

    # ---- sar_vv_vh.tif : 2-band (or 1-band) float32 dB GeoTIFF — the real input ---------
    if not a.no_geotiff:
        tif_bands = ["VV", "VH"] if have_vh else ["VV"]
        raw = img.select(tif_bands).toFloat().clip(region)
        tw, th = px(a.tif_scale)
        too_big = tw * th * len(tif_bands) > DOWNLOAD_URL_PIXEL_CEILING
        if a.drive or too_big:
            reason = "forced with --drive" if a.drive else f"~{tw}x{th}x{len(tif_bands)} exceeds the direct-download ceiling"
            task = ee.batch.Export.image.toDrive(
                image=raw, description=f"{a.case}_sar_vv_vh", folder="naap_exports",
                fileNamePrefix=f"{a.case}_sar_vv_vh", region=region,
                scale=a.tif_scale, crs="EPSG:4326", maxPixels=int(1e10),
                fileFormat="GeoTIFF")
            task.start()
            print(f"GeoTIFF   {reason}")
            print(f"          Export task '{a.case}_sar_vv_vh' STARTED. Now:")
            print(f"            1. open https://code.earthengine.google.com/ -> Tasks tab")
            print(f"            2. press RUN on '{a.case}_sar_vv_vh'  (nothing exports until you do)")
            print(f"            3. when it finishes, download from Drive/naap_exports/ into")
            print(f"               {case_dir / 'sar_vv_vh.tif'}")
        else:
            durl = raw.getDownloadURL({"region": region, "scale": a.tif_scale,
                                       "crs": "EPSG:4326", "format": "GEO_TIFF"})
            dr = requests.get(durl, timeout=600)
            if dr.status_code != 200:
                raise SystemExit(f"GeoTIFF download failed ({dr.status_code}). Retry with "
                                 f"--drive.\n{dr.text[:400]}")
            (case_dir / "sar_vv_vh.tif").write_bytes(dr.content)
            print(f"GeoTIFF   wrote sar_vv_vh.tif ({tw}x{th}, {len(tif_bands)} band(s), "
                  f"{len(dr.content) / 1e6:.1f} MB) @ {a.tif_scale} m/px")

    # ---- bounds.json ------------------------------------------------------------------
    (case_dir / "bounds.json").write_text(json.dumps({
        "west": west, "south": south, "east": east, "north": north,
        "width_px": im.width, "height_px": im.height,
        "db_min": a.db_min, "db_max": a.db_max,
        "vh_available": bool(have_vh)}, indent=2) + "\n", encoding="utf-8")

    # ---- meta.json (only if absent) ---------------------------------------------------
    meta_path = case_dir / "meta.json"
    if meta_path.exists():
        print(f"\n{meta_path.name} already exists — left untouched.")
    else:
        platform = props.get("platform_number")
        meta_path.write_text(json.dumps({
            "case_id": a.case,
            "title": a.title or a.case,
            "short_location": "EDIT ME",
            "case_type": "spill",
            "satellite": f"Sentinel-1{platform}" if platform else "Sentinel-1",
            "scene_id": a.scene,
            "detection_time": acquired.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "acts_available": ["detect"],
            "gallery": {"thumbnail": "thumb.png", "blurb": "EDIT ME: a question.",
                        "difficulty": "medium"},
            "notes": "EDIT ME: add acts as stages land; say what is and isn't available."
        }, indent=2) + "\n", encoding="utf-8")
        print(f"\nwrote {meta_path} — edit the EDIT ME fields, add acts as stages land.")

    stat = im.getextrema()
    if stat[0] == stat[1]:
        print("\nWARNING: sar.png is a single flat value — the dB clamp is wrong.")
    else:
        print("\nNow OPEN sar.png: coastline west, sea grey static, slick a darker streak.")
        if have_vh and not a.no_geotiff:
            print("Then check sar_vv_vh.tif has 2 bands with sane dB ranges before handing to Soum.")
    print("Record the scene id + UTC time in docs/receipts.md.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
