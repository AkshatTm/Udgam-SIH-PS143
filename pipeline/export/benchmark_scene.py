#!/usr/bin/env python3
"""
benchmark_scene.py — build the case artefacts from a LOCAL benchmark GeoTIFF. Owner: Akshat.

    python pipeline/export/benchmark_scene.py \
        --tif "data/test/Images/Lookalike/00134.tif" \
        --case case-lookalike-zenodo \
        --scene-id "P3_Lookalike_00134" \
        --case-type lookalike

The Zenodo counterpart to gee_scene.py. Same four artefacts into cases/<case_id>/:

    sar_vv_vh.tif   the scene itself, band-labelled VV/VH — Soumirya's REAL input
    sar.png         VV backscatter, dB-clamped to 8-bit greyscale — display only
    thumb.png       small VV preview — the gallery card
    bounds.json     the placeholder box + the dB clamp actually used + vh_available
    meta.json       case info (only if absent — an existing meta.json is never overwritten)

Why this exists: gee_scene.py can only reach Google Earth Engine, and build_case.py refuses to
run until meta.json + bounds.json + sar.png already exist. A Zenodo Part III scene is a local
file on Soumirya's laptop, so nothing in the repo could turn one into a bundle. This closes that gap.

THREE THINGS THAT DECIDE WHETHER THIS WORKS
-------------------------------------------

  1. THE dB CLAMP IS COMPUTED, NEVER DEFAULTED. Zenodo scenes sit at ~-29 dB over open ocean;
     GEE exports sit at ~-20 dB. The repo-wide default clamp of [-25, 0] is a GEE number, and
     applying it to a Zenodo scene produces a black PNG and — far worse — makes Soumirya's PNG->dB
     inversion silently wrong. We take percentiles off the scene's own valid pixels and write
     those into bounds.json (docs/TRAPS.md #7: change the clamp and you announce it).

  2. NODATA IS -inf AND NaN, NOT A LOW dB VALUE (docs/TRAPS.md #22 and #11). Treated as
     backscatter, -inf is the darkest thing in the scene by an infinite margin and a dark-spot
     detector reports the missing corner as an enormous slick. Every statistic here runs over
     np.isfinite() pixels only, and the exact-zero nodata sentinel is excluded too.

  3. THESE SCENES ARE GEOREFERENCED. READ THE BOX, DO NOT INVENT ONE. An earlier draft of this
     file asserted the opposite — that Part III tiles carry no CRS — and wrote a placeholder box
     anchored at 0,0 for every scene. That was wrong. Soumirya checked the actual files on 13 Sept:
     they carry EPSG:4326 and real geotransforms, and the two we are shipping sit in the
     Mississippi Delta and the Gulf of İskenderun. So we take the real bounds off the transform
     and there is no honesty problem to solve — the map shows where the scene is.

     The placeholder path survives ONLY as a fallback for a tile that genuinely has no transform,
     because both gates hard-require a geographic box (validate_case.py errors on a missing
     bounds.json, web/lib/loadCase.ts throws on a degenerate one). If it ever fires it announces
     itself loudly and writes the disclaimer into meta.notes. It should never fire on Part III.

     Note what this cost us elsewhere: the SAME false premise was load-bearing in Stage 1, where
     scene_provenance() routed on "no CRS => benchmark". That test matched everything and
     discriminated nothing. The fix is meta.provenance (Master §6.1, D33), not a better sniff.
"""
import argparse
import json
import shutil
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]

# Zenodo Part III is 2048x2048 at ~10 m/px. Used only to give the placeholder box a size that
# matches the raster's real ground extent, so the aspect ratio on screen is honest even though
# the position is not.
DEFAULT_PIXEL_M = 10.0
M_PER_DEG = 111_320.0            # equirectangular, at the equator — where the anchor sits
THUMB_MAX = 480                  # gallery card; aspect preserved (gee_scene.py squashed this once)
PCT_LO, PCT_HI = 2.0, 98.0       # dB clamp percentiles over valid pixels


def load_bands(tif_path):
    """Return (vv, vh_or_None, px_m, geo_bounds_or_None).

    geo_bounds is the scene's REAL [west, south, east, north] in WGS84 degrees, or None if the
    file carries no usable georeference. Part III tiles do carry one — see the module docstring.
    """
    import numpy as np
    import rasterio
    from rasterio.warp import transform_bounds

    with rasterio.open(tif_path) as src:
        if src.count < 1:
            sys.exit(f"{tif_path}: no bands")
        vv = src.read(1).astype(np.float32)
        vh = src.read(2).astype(np.float32) if src.count >= 2 else None
        crs = src.crs
        tr = src.transform
        raw = src.bounds

        geo_bounds = None
        # An identity transform is rasterio's "there was nothing here" default, not a location.
        identity = (abs(tr.a) == 1.0 and abs(tr.e) == 1.0 and tr.c == 0.0 and tr.f == 0.0)
        if crs is not None and not identity:
            # Reproject to WGS84 if needed — a UTM tile would otherwise write metres into a
            # field the whole repo reads as degrees (TRAPS #1: everything downstream is lon/lat).
            w, s, e, n = transform_bounds(crs, "EPSG:4326", *raw, densify_pts=21)
            if all(map(np.isfinite, (w, s, e, n))) and e > w and n > s:
                geo_bounds = (w, s, e, n)

    if geo_bounds is not None:
        # Degrees -> metres for the reported resolution only. cos(lat) on the lon axis; a GeoTIFF
        # in EPSG:4326 has no cos(lat) term baked in (receipts.md says this about GEE exports too).
        mid_lat = (geo_bounds[1] + geo_bounds[3]) / 2.0
        px_m = abs(tr.a) * M_PER_DEG * max(0.01, np.cos(np.radians(mid_lat))) \
            if abs(tr.a) < 1.0 else abs(tr.a)
    else:
        px_m = DEFAULT_PIXEL_M

    return vv, vh, float(px_m), geo_bounds


def valid_mask(arr):
    """Finite, and not the exact-zero nodata sentinel. TRAPS #22 + #11."""
    import numpy as np
    return np.isfinite(arr) & (arr != 0)


def db_clamp(vv):
    """Percentile clamp off the scene's own valid pixels. Never the [-25, 0] GEE default."""
    import numpy as np
    v = vv[valid_mask(vv)]
    if v.size == 0:
        sys.exit("every pixel in band 1 is NaN, -inf or exactly zero — wrong file?")
    lo = float(np.percentile(v, PCT_LO))
    hi = float(np.percentile(v, PCT_HI))
    if not (hi > lo):
        sys.exit(f"degenerate dB range ({lo} .. {hi}) — the scene is flat")
    return round(lo, 1), round(hi, 1)


def to_png(vv, lo, hi, out_path, thumb_path):
    """VV -> 8-bit greyscale, clamped to [lo, hi]. Invalid pixels go to black."""
    import numpy as np
    from PIL import Image

    ok = valid_mask(vv)
    scaled = np.zeros(vv.shape, dtype=np.uint8)
    stretched = (np.clip(vv, lo, hi) - lo) / (hi - lo) * 255.0
    scaled[ok] = stretched[ok].astype(np.uint8)

    im = Image.fromarray(scaled, mode="L")
    im.save(out_path)

    thumb = im.copy()
    thumb.thumbnail((THUMB_MAX, THUMB_MAX))       # preserves aspect ratio
    thumb.save(thumb_path)
    return im.width, im.height


def label_bands(tif_path, have_vh):
    """Same courtesy gee_scene.py does — Soumirya reads 'VV'/'VH', not 'band 1'/'band 2'."""
    try:
        import rasterio
        with rasterio.open(tif_path, "r+") as ds:
            names = ["VV", "VH"] if have_vh else ["VV"]
            for i, n in enumerate(names, start=1):
                ds.set_band_description(i, n)
                ds.update_tags(i, POLARISATION=n, UNITS="dB")
    except Exception as e:
        print(f"  note: could not label bands ({e}) - harmless, the data is unchanged")


def main():
    ap = argparse.ArgumentParser(
        description="Build case artefacts from a local benchmark GeoTIFF (Zenodo Part III).")
    ap.add_argument("--tif", required=True, help="path to the source scene, e.g. data/test/Images/Lookalike/00134.tif")
    ap.add_argument("--case", required=True, help="case id, e.g. case-lookalike-zenodo")
    ap.add_argument("--scene-id", required=True, help="benchmark scene id, e.g. P3_Lookalike_00134")
    ap.add_argument("--case-type", required=True, choices=["spill", "lookalike", "nospill"])
    ap.add_argument("--cases-root", default=str(REPO / "cases"))
    ap.add_argument("--anchor", nargs=2, type=float, metavar=("LON", "LAT"), default=[0.0, 0.0],
                    help="FALLBACK ONLY — placeholder box origin (west, south), used when the "
                         "scene has no georeference. Ignored when it does, which is the normal "
                         "case. Default 0 0 (Null Island, a deliberate sentinel).")
    ap.add_argument("--pixel-m", type=float, default=None,
                    help=f"override the pixel size in metres (default: read, else {DEFAULT_PIXEL_M})")
    ap.add_argument("--no-geotiff", action="store_true",
                    help="refresh sar.png / thumb.png / bounds.json only, skip copying the scene")
    a = ap.parse_args()

    tif = Path(a.tif)
    if not tif.exists():
        sys.exit(f"{tif}: not found. The Zenodo corpus is gitignored and lives only on Soumirya's "
                 f"machine — run this there.")

    case_dir = Path(a.cases_root) / a.case
    case_dir.mkdir(parents=True, exist_ok=True)

    print(f"reading {tif}")
    vv, vh, px_m, geo_bounds = load_bands(tif)
    if a.pixel_m:
        px_m = a.pixel_m
    have_vh = vh is not None
    h, w = vv.shape

    if geo_bounds is not None:
        print(f"  georeferenced: real bounds {geo_bounds[0]:.4f},{geo_bounds[1]:.4f} .. "
              f"{geo_bounds[2]:.4f},{geo_bounds[3]:.4f} - using these, no placeholder")
    else:
        print("  WARNING: no usable georeference in this file. Falling back to a PLACEHOLDER "
              "box. Part III tiles DO carry EPSG:4326, so this almost certainly means the wrong "
              "file, or a transform stripped in preprocessing. Check before you ship it.")

    lo, hi = db_clamp(vv)
    print(f"  {w}x{h}, {'VV+VH' if have_vh else 'VV only'}, {px_m:.0f} m/px")
    print(f"  dB clamp from the scene's own P{PCT_LO:g}/P{PCT_HI:g}: [{lo}, {hi}]"
          f"   (NOT the [-25, 0] GEE default)")

    # ---- sar.png + thumb.png ----------------------------------------------------------
    png_w, png_h = to_png(vv, lo, hi, case_dir / "sar.png", case_dir / "thumb.png")
    print(f"  wrote sar.png ({png_w}x{png_h}) + thumb.png")

    # ---- sar_vv_vh.tif ----------------------------------------------------------------
    if not a.no_geotiff:
        dest = case_dir / "sar_vv_vh.tif"
        shutil.copy2(tif, dest)
        label_bands(dest, have_vh)
        print(f"  wrote sar_vv_vh.tif ({dest.stat().st_size / 1e6:.1f} MB)")

    # ---- bounds.json ------------------------------------------------------------------
    # The scene's real box when it has one (the normal case), else a declared placeholder
    # sized to the raster's true ground extent so at least the aspect ratio is honest.
    if geo_bounds is not None:
        west, south, east, north = geo_bounds
        placeholder = False
    else:
        west, south = float(a.anchor[0]), float(a.anchor[1])
        east = west + (w * px_m) / M_PER_DEG
        north = south + (h * px_m) / M_PER_DEG
        placeholder = True

    (case_dir / "bounds.json").write_text(json.dumps({
        "west": round(west, 5), "south": round(south, 5),
        "east": round(east, 5), "north": round(north, 5),
        "width_px": png_w, "height_px": png_h,
        "db_min": lo, "db_max": hi,
        "vh_available": bool(have_vh)}, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    tag = "PLACEHOLDER box" if placeholder else "real bounds"
    print(f"  wrote bounds.json - {tag} {west:.5f},{south:.5f} .. {east:.5f},{north:.5f}")

    # ---- meta.json (only if absent) ---------------------------------------------------
    meta_path = case_dir / "meta.json"
    if meta_path.exists():
        print(f"\nmeta.json already exists - left untouched. Check that it carries "
              f'"provenance": "benchmark" and a real scene_id.')
    else:
        if placeholder:
            where = "Zenodo Part III benchmark — not geolocated"
            location_note = (
                "This scene carried no usable georeference, so bounds.json holds a PLACEHOLDER "
                "box anchored at 0,0, sized to the raster's true ground extent. It is not a "
                "claim about where the scene was acquired and must never be presented as one. ")
        else:
            where = "EDIT ME — the real place, from bounds.json"
            location_note = (
                "bounds.json holds the scene's REAL box, read from its EPSG:4326 geotransform. "
                "Part III tiles are georeferenced; nothing here is a placeholder. ")

        meta_path.write_text(json.dumps({
            "case_id": a.case,
            "title": "EDIT ME",
            "short_location": where,
            "case_type": a.case_type,
            "provenance": "benchmark",
            "satellite": "Sentinel-1",
            "scene_id": a.scene_id,
            "detection_time": "1970-01-01T00:00:00Z",
            "acts_available": ["detect"],
            "gallery": {"thumbnail": "thumb.png", "blurb": "EDIT ME: a question.",
                        "difficulty": "medium"},
            "notes": (
                "Zenodo Part III benchmark scene (DOI 10.5281/zenodo.13761290, CC-BY — the "
                "attribution is mandatory and must appear on a slide). " + location_note +
                "detection_time is the deliberate 1970-01-01 epoch sentinel: the TIFFs carry no "
                "acquisition timestamp (the only tag is AREA_OR_POINT), so there is no real time "
                "to recover and none is implied. detections.geojson is expected to contain zero "
                "features classified 'oil'; that is the correct result, not a failure. "
                "confidence on this case is a model probability — provenance is 'benchmark', so "
                "the CNN scene classifier ran, not the rule path (Master §6.3).")
        }, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"\nwrote {meta_path} - edit title and gallery.blurb.")

    print("\nNext:")
    print(f"  python pipeline/detect/run.py --case {a.case}")
    print(f"  python pipeline/export/build_case.py --case {a.case} --stage detect")
    print(f"  python scripts/validate_case.py cases/{a.case}")
    print("\nNow OPEN sar.png: sea should be grey speckle with visible structure, not flat "
          "black and not blown white.")


if __name__ == "__main__":
    main()
