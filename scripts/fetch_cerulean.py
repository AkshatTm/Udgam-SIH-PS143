#!/usr/bin/env python3
"""
fetch_cerulean.py — pull a slick record from SkyTruth Cerulean's public API. Owner: Akshat.

    # find candidates over a box and date
    python scripts/fetch_cerulean.py --search --bbox -80.2 30.0 -79.1 30.8 --date 2024-07-30

    # fetch one slick into a case bundle
    python scripts/fetch_cerulean.py --case case-jacksonville-2024 --slick 3046293

    # ...and show the sealed attribution (Akshat's terminal ONLY)
    python scripts/fetch_cerulean.py --case case-jacksonville-2024 --slick 3046293 --answers

Cerulean's API is a public OGC Features service — no key, no auth, no registration
(decision D23). Collection `public.slick_plus` carries, per detection: the FULL Sentinel-1
scene id, the slick polygon, the centerline, length/area/perimeter, the model confidence,
and the attributed source ids. That single query replaced the "copy the truncated scene id
out of the web panel" chore that was BLOCKING the whole case library.

>>> THE SPLIT THIS SCRIPT EXISTS TO ENFORCE (Master Part 16, blind evaluation)
>>>
>>>   cases/<id>/cerulean_slick.geojson  <-- the POLYGON. Ships in the bundle. It is Soumirya's
>>>                                          IoU reference on a real incident, and it says
>>>                                          nothing about who did it.
>>>   stdout, only with --answers         <-- the SOURCE IDS. The answer. Never written to
>>>                                          disk by this script, never pasted in the group.
>>>
>>> Hand Soumirya the polygon only AFTER his detector has produced its own, or the comparison is
>>> not a measurement, it is a lookup.

Two other things worth knowing:
  * `public.slick_to_source` and `public.source_vessel` return 403. Vessel names, flags and
    IMOs come from the per-slick web page (`slick_url`), not from this API.
  * One Sentinel-1 scene often carries several slicks. Match on length and area against
    Master Plan section 3.2 before you commit a slick id to a case — case 2's scene has four.
"""
import argparse
import json
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

API = "https://api.cerulean.skytruth.org/collections/public.slick_plus/items"
TIMEOUT = 90
DEFAULT_PAD_DEG = 0.12          # export-box padding around the slick, ~13 km

# Properties that describe the SLICK — safe to ship in the bundle.
KEEP = ["id", "slick_timestamp", "s1_scene_id", "length", "area", "perimeter",
        "machine_confidence", "polsby_popper", "fill_factor", "linearity"]

# Properties that describe the SOURCE — the answer. Never written to disk.
SEALED = ["cls", "hitl_cls", "hitl_cls_name", "source_type_1_ids", "source_type_2_ids",
          "source_type_3_ids", "max_source_collated_score", "aoi_type_1_ids",
          "aoi_type_2_ids", "aoi_type_3_ids", "slick_url"]


def get(params):
    url = f"{API}?{urllib.parse.urlencode(params)}"
    try:
        with urllib.request.urlopen(url, timeout=TIMEOUT) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        raise SystemExit(f"Cerulean API returned {e.code} for:\n  {url}\n  {e.read()[:300]!r}")
    except Exception as e:
        raise SystemExit(f"Cerulean API request failed:\n  {url}\n  {e}")


def ring_points(geom):
    """Every [lon, lat] in a Polygon or MultiPolygon, flat."""
    t, c = geom.get("type"), geom.get("coordinates") or []
    if t == "Polygon":
        return [p for ring in c for p in ring]
    if t == "MultiPolygon":
        return [p for poly in c for ring in poly for p in ring]
    raise SystemExit(f"unexpected geometry type {t!r} — expected Polygon or MultiPolygon")


def bbox_of(geom):
    pts = ring_points(geom)
    lons = [p[0] for p in pts]
    lats = [p[1] for p in pts]
    return min(lons), min(lats), max(lons), max(lats)


def round_coords(obj, dp=5):
    """Master Plan section 5.3: coordinates to 5 dp in JSON."""
    if isinstance(obj, list):
        if len(obj) == 2 and all(isinstance(v, (int, float)) for v in obj):
            return [round(float(obj[0]), dp), round(float(obj[1]), dp)]
        return [round_coords(v, dp) for v in obj]
    if isinstance(obj, dict):
        return {k: round_coords(v, dp) for k, v in obj.items()}
    return obj


def summarise(p, geom=None):
    w, s, e, n = bbox_of(geom) if geom else (0, 0, 0, 0)
    return (f"  slick {p['id']:>8}  {p['slick_timestamp']}  "
            f"{(p.get('length') or 0)/1000:6.1f} km  {(p.get('area') or 0)/1e6:6.2f} km2  "
            f"conf {(p.get('machine_confidence') or 0):.3f}"
            + (f"\n            centre {(w+e)/2:.4f}, {(s+n)/2:.4f}" if geom else "")
            + f"\n            {p.get('s1_scene_id')}")


def do_search(a):
    lon0, lat0, lon1, lat1 = a.bbox
    params = {"bbox": f"{lon0},{lat0},{lon1},{lat1}", "limit": str(a.limit), "f": "geojson"}
    if a.date:
        params["datetime"] = f"{a.date}T00:00:00Z/{a.date}T23:59:59Z"
    fc = get(params)
    feats = fc.get("features", [])
    print(f"Cerulean public.slick_plus — {len(feats)} slick(s) in "
          f"[{lon0}, {lat0}, {lon1}, {lat1}]" + (f" on {a.date}" if a.date else ""))
    print("-" * 78)
    for f in feats:
        print(summarise(f["properties"], f["geometry"]))
    print("-" * 78)
    print("Match length + area against Master Plan section 3.2 before committing a slick id —")
    print("one scene often carries several slicks. Then:")
    print("  python scripts/fetch_cerulean.py --case <case-id> --slick <id>")
    return 0 if feats else 1


def do_fetch(a):
    fc = get({"filter": f"id={a.slick}", "limit": "1", "f": "geojson"})
    feats = fc.get("features", [])
    if not feats:
        raise SystemExit(f"No slick with id {a.slick}. Run --search to find the right one.")
    feat = feats[0]
    p, geom = feat["properties"], feat["geometry"]

    print(f"Cerulean slick {p['id']}")
    print(f"  acquired   {p['slick_timestamp']}Z")
    print(f"  scene      {p['s1_scene_id']}")
    print(f"  geometry   {geom['type']}, {len(ring_points(geom))} vertices")
    print(f"  length     {(p.get('length') or 0)/1000:.2f} km")
    print(f"  area       {(p.get('area') or 0)/1e6:.2f} km2")
    print(f"  confidence {(p.get('machine_confidence') or 0):.3f}")

    w, s, e, n = bbox_of(geom)
    print(f"\n  slick bbox   {w:.4f} {s:.4f} {e:.4f} {n:.4f}")
    pw, ps, pe, pn = w - a.pad, s - a.pad, e + a.pad, n + a.pad
    print(f"  export bbox  {pw:.4f} {ps:.4f} {pe:.4f} {pn:.4f}   (+{a.pad} deg pad)")

    out = Path(a.out) if a.out else REPO / "cases" / a.case / "cerulean_slick.geojson"
    if not a.dry_run:
        out.parent.mkdir(parents=True, exist_ok=True)
        props = {k: p.get(k) for k in KEEP}
        props["source"] = "SkyTruth Cerulean, public API (api.cerulean.skytruth.org)"
        props["note"] = ("Reference polygon from an operational detector. NOT ground truth and "
                         "NOT a UDGAM detection — Cerulean state plainly that SAR alone cannot "
                         "definitively identify oil. Source attribution deliberately omitted "
                         "(Master Plan Part 16).")
        features = [{"type": "Feature", "geometry": round_coords(geom), "properties": props}]
        cl = p.get("centerlines")
        if isinstance(cl, dict):
            for i, c in enumerate(cl.get("features", [])):
                features.append({"type": "Feature", "geometry": round_coords(c["geometry"]),
                                 "properties": {"role": "centerline", "index": i,
                                                **(c.get("properties") or {})}})
        out.write_text(json.dumps({"type": "FeatureCollection", "features": features},
                                  indent=1) + "\n", encoding="utf-8")
        print(f"\nwrote {out.relative_to(REPO) if out.is_relative_to(REPO) else out}"
              f"  ({len(features)} feature(s): 1 slick"
              + (f" + {len(features)-1} centerline(s)" if len(features) > 1 else "") + ")")

    print("\nNext — export the scene:")
    print(f"  python pipeline/export/gee_scene.py --project {a.project} \\")
    print(f"    --scene {p['s1_scene_id']} \\")
    print(f"    --case {a.case} --bbox {pw:.4f} {ps:.4f} {pe:.4f} {pn:.4f}")

    if a.answers:
        print("\n" + "!" * 74)
        print("!!  SEALED — blind evaluation (D21). Akshat's terminal only.")
        print("!!  Do NOT paste this in the group. Do NOT write it into cases/.")
        print("!" * 74)
        for k in SEALED:
            if p.get(k) not in (None, [], ""):
                print(f"    {k:<26} {p[k]}")
        print("!" * 74)
        print("Vessel names / flags / IMOs are NOT in this API (source_vessel returns 403).")
        print("Open slick_url in a browser for those, then record everything in docs/ANSWERS.md.")
    else:
        print("\n(attribution withheld — re-run with --answers if you are Akshat and need it)")
    return 0


def main():
    ap = argparse.ArgumentParser(description="Fetch a SkyTruth Cerulean slick record")
    ap.add_argument("--search", action="store_true", help="list slicks over --bbox / --date")
    ap.add_argument("--bbox", nargs=4, type=float, metavar=("W", "S", "E", "N"))
    ap.add_argument("--date", help="YYYY-MM-DD (search mode)")
    ap.add_argument("--limit", type=int, default=20)
    ap.add_argument("--case", help="case id, e.g. case-jacksonville-2024")
    ap.add_argument("--slick", type=int, help="Cerulean slick id")
    ap.add_argument("--pad", type=float, default=DEFAULT_PAD_DEG,
                    help=f"degrees of padding on the export box (default {DEFAULT_PAD_DEG})")
    ap.add_argument("--answers", action="store_true",
                    help="ALSO print the sealed source attribution — Akshat only")
    ap.add_argument("--out", default=None, help="override the output path")
    ap.add_argument("--dry-run", action="store_true", help="print, write nothing")
    ap.add_argument("--project", default="quizzer-dev-487316",
                    help="GEE project id, for the printed export command")
    a = ap.parse_args()

    if a.search:
        if not a.bbox:
            raise SystemExit("--search needs --bbox W S E N (and usually --date)")
        return do_search(a)
    if not (a.case and a.slick):
        raise SystemExit("give either --search --bbox ..., or --case <id> --slick <id>")
    return do_fetch(a)


if __name__ == "__main__":
    sys.exit(main())
