#!/usr/bin/env python3
"""
validate_case.py — integration insurance for Naap.

Run this on any case bundle BEFORE handing anything to Akshat.
    python scripts/validate_case.py cases/case-000
    python scripts/validate_case.py cases/case-ennore-2017 --strict

Checks: required files exist, schemas match docs/CONTRACTS.md, every coordinate
is [lon, lat] and lands inside bounds.json (this is what catches lat/lon swaps),
timestamps are timezone-aware UTC, array dimensions agree with their declared
counts, and values are physically plausible.

Exit 0 = clean. Exit 1 = errors. Warnings never fail unless --strict.
"""
import json
import sys
import math
from datetime import datetime, timezone
from pathlib import Path

ERRORS = []
WARNINGS = []


def err(msg):
    ERRORS.append(msg)


def warn(msg):
    WARNINGS.append(msg)


def load(path):
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text())
    except json.JSONDecodeError as e:
        err(f"{path.name}: not valid JSON — {e}")
        return None


def need_keys(obj, keys, where):
    if not isinstance(obj, dict):
        err(f"{where}: expected an object, got {type(obj).__name__}")
        return False
    missing = [k for k in keys if k not in obj]
    if missing:
        err(f"{where}: missing required key(s) {missing}")
        return False
    return True


def parse_ts(value, where):
    if not isinstance(value, str):
        err(f"{where}: timestamp must be a string, got {type(value).__name__}")
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        err(f"{where}: '{value}' is not ISO 8601 (want e.g. 2017-01-29T00:14:00Z)")
        return None
    if dt.tzinfo is None:
        err(f"{where}: '{value}' is timezone-naive — every timestamp needs the trailing Z")
        return None
    if dt.utcoffset() != timezone.utc.utcoffset(None):
        warn(f"{where}: '{value}' is not UTC")
    return dt


class Box:
    def __init__(self, b):
        self.w, self.s = float(b["west"]), float(b["south"])
        self.e, self.n = float(b["east"]), float(b["north"])
        # generous pad: drift particles and vessel tracks legitimately leave the scene
        self.pad = max(2.0, 0.5 * max(self.e - self.w, self.n - self.s))

    def check(self, lon, lat, where):
        if not (-180 <= lon <= 180):
            err(f"{where}: longitude {lon} out of range — is this [lat, lon] instead of [lon, lat]?")
            return False
        if not (-90 <= lat <= 90):
            err(f"{where}: latitude {lat} out of range — coordinates are [lon, lat], not [lat, lon]")
            return False
        inside_swapped = (self.w - self.pad <= lat <= self.e + self.pad and
                          self.s - self.pad <= lon <= self.n + self.pad)
        inside = (self.w - self.pad <= lon <= self.e + self.pad and
                  self.s - self.pad <= lat <= self.n + self.pad)
        if not inside and inside_swapped:
            err(f"{where}: [{lon}, {lat}] is outside bounds but INSIDE them when swapped — "
                f"this file is writing [lat, lon]. Fix the producer, not this check.")
            return False
        if not inside:
            warn(f"{where}: [{lon}, {lat}] falls well outside the scene bounds")
        return True


def walk_coords(geom, box, where, limit=400):
    """Yield-check coordinates of a Point/LineString/Polygon, sampled."""
    t = geom.get("type")
    coords = geom.get("coordinates")
    if t == "Point":
        flat = [coords]
    elif t == "LineString":
        flat = coords
    elif t == "Polygon":
        flat = [pt for ring in coords for pt in ring]
    elif t == "MultiPolygon":
        flat = [pt for poly in coords for ring in poly for pt in ring]
    else:
        err(f"{where}: unsupported geometry type '{t}'")
        return
    if not flat:
        err(f"{where}: geometry has no coordinates")
        return
    step = max(1, len(flat) // limit)
    for pt in flat[::step]:
        if not (isinstance(pt, (list, tuple)) and len(pt) >= 2):
            err(f"{where}: bad coordinate {pt!r}")
            return
        if not box.check(float(pt[0]), float(pt[1]), where):
            return


# ---------------------------------------------------------------- validators

def check_meta(d):
    m = load(d / "meta.json")
    if m is None:
        err("meta.json: missing — every bundle needs one")
        return None
    if not need_keys(m, ["case_id", "title", "detection_time", "acts_available"], "meta.json"):
        return None
    parse_ts(m["detection_time"], "meta.json/detection_time")
    acts = m["acts_available"]
    if not isinstance(acts, list) or not acts:
        err("meta.json/acts_available: must be a non-empty list")
        return None
    bad = [a for a in acts if a not in ("detect", "trace", "attribute")]
    if bad:
        err(f"meta.json/acts_available: unknown act(s) {bad}")
    if "trace" in acts and "detect" not in acts:
        err("meta.json: 'trace' without 'detect' — trace needs a slick to seed from")
    if "attribute" in acts and "trace" not in acts:
        err("meta.json: 'attribute' without 'trace' — attribution needs an origin cloud")
    return m


def check_bounds(d):
    b = load(d / "bounds.json")
    if b is None:
        err("bounds.json: missing")
        return None
    if not need_keys(b, ["west", "south", "east", "north"], "bounds.json"):
        return None
    if b["west"] >= b["east"]:
        err("bounds.json: west must be less than east")
    if b["south"] >= b["north"]:
        err("bounds.json: south must be less than north")
    if not (-180 <= b["west"] <= 180 and -180 <= b["east"] <= 180):
        err("bounds.json: longitudes out of range (use -180..180, never 0..360)")
    if not (-90 <= b["south"] <= 90 and -90 <= b["north"] <= 90):
        err("bounds.json: latitudes out of range")
    if not (d / "sar.png").exists():
        err("sar.png: missing — bounds.json describes an image that isn't there")
    return b


def check_detections(d, box):
    g = load(d / "detections.geojson")
    if g is None:
        err("detections.geojson: missing (required whenever 'detect' is available)")
        return
    if g.get("type") != "FeatureCollection":
        err("detections.geojson: top level must be a FeatureCollection")
        return
    feats = g.get("features", [])
    if not isinstance(feats, list):
        err("detections.geojson: 'features' must be a list")
        return
    oil = 0
    for i, f in enumerate(feats):
        w = f"detections.geojson[{i}]"
        p = f.get("properties") or {}
        if not need_keys(p, ["id", "classification", "confidence", "area_km2", "elongation",
                             "edge_gradient", "contrast_db", "shape_class", "centroid"],
                         w + "/properties"):
            continue
        if p["classification"] not in ("oil", "lookalike"):
            err(f"{w}: classification must be 'oil' or 'lookalike', got {p['classification']!r}")
        if p["classification"] == "oil":
            oil += 1
        if p["shape_class"] not in ("linear", "blob"):
            err(f"{w}: shape_class must be 'linear' or 'blob', got {p['shape_class']!r}")
        if not 0 <= p["confidence"] <= 1:
            err(f"{w}: confidence {p['confidence']} outside 0–1")
        if p["area_km2"] <= 0:
            err(f"{w}: area_km2 must be positive")
        elif not 0.01 <= p["area_km2"] <= 2000:
            warn(f"{w}: area_km2 {p['area_km2']} is implausible for a slick")
        if p["elongation"] < 1:
            err(f"{w}: elongation {p['elongation']} < 1 — it is major/minor axis, so never below 1")
        if p["contrast_db"] > 0:
            warn(f"{w}: contrast_db {p['contrast_db']} is positive — a dark spot should be negative")
        declared = (p["shape_class"] == "linear")
        if declared != (p["elongation"] > 3):
            warn(f"{w}: shape_class {p['shape_class']!r} disagrees with elongation {p['elongation']}")
        if box:
            box.check(float(p["centroid"][0]), float(p["centroid"][1]), w + "/centroid")
            walk_coords(f.get("geometry", {}), box, w + "/geometry")
    if oil == 0:
        warn("detections.geojson: zero 'oil' features — correct for a no-spill case, "
             "an error for any case with 'trace' in acts_available")


def check_particles(d, box, meta):
    p = load(d / "particles.json")
    if p is None:
        err("particles.json: missing (required whenever 'trace' is available)")
        return
    if not need_keys(p, ["t0", "direction", "timestep_minutes", "n_steps",
                         "n_particles", "positions"], "particles.json"):
        return
    t0 = parse_ts(p["t0"], "particles.json/t0")
    if meta and t0:
        dt = parse_ts(meta["detection_time"], "meta.json/detection_time")
        if dt and abs((t0 - dt).total_seconds()) > 60:
            err(f"particles.json/t0 ({p['t0']}) does not match meta detection_time "
                f"({meta['detection_time']}) — the rewind must start at the satellite pass")
    if p["direction"] != "backward":
        warn(f"particles.json/direction is {p['direction']!r}; the demo rewind expects 'backward'")
    pos = p["positions"]
    if not isinstance(pos, list) or not pos:
        err("particles.json/positions: must be a non-empty list of timesteps")
        return
    if len(pos) != p["n_steps"]:
        err(f"particles.json: n_steps says {p['n_steps']} but positions has {len(pos)} timesteps")
    if len(pos[0]) != p["n_particles"]:
        err(f"particles.json: n_particles says {p['n_particles']} but step 0 has {len(pos[0])}")
    lens = {len(s) for s in pos}
    if len(lens) > 1:
        err(f"particles.json: timesteps have differing particle counts {sorted(lens)[:5]} — "
            "particles must never be added or dropped mid-run")
    span_h = (p["n_steps"] - 1) * p["timestep_minutes"] / 60
    if not 6 <= span_h <= 72:
        warn(f"particles.json: rewind spans {span_h:.1f} h; the demo is scoped to ~24 h")
    if box:
        for si in (0, len(pos) // 2, len(pos) - 1):
            for pt in pos[si][::max(1, len(pos[si]) // 50)]:
                box.check(float(pt[0]), float(pt[1]), f"particles.json/positions[{si}]")
    # displacement plausibility — the units bug catcher
    try:
        a, b = pos[0][0], pos[-1][0]
        mlat = math.radians((a[1] + b[1]) / 2)
        dx = (b[0] - a[0]) * 111.32 * math.cos(mlat)
        dy = (b[1] - a[1]) * 111.32
        dist = math.hypot(dx, dy)
        if dist > 400:
            err(f"particles.json: particle 0 travelled {dist:.0f} km in {span_h:.0f} h "
                "— check current units (HYCOM is cm/s, divide by 100)")
        elif dist < 0.5:
            err(f"particles.json: particle 0 barely moved ({dist:.2f} km) — fields may be zero")
        elif dist > 250:
            warn(f"particles.json: particle 0 travelled {dist:.0f} km — high but not impossible")
    except (IndexError, TypeError):
        err("particles.json/positions: malformed coordinate arrays")


def check_origin(d, box):
    o = load(d / "origin.json")
    if o is None:
        err("origin.json: missing (required whenever 'trace' is available)")
        return None
    if not need_keys(o, ["bounds", "shape", "values", "centroid", "radius_50_km",
                         "radius_90_km", "time_window", "ensemble_runs", "abstain"],
                     "origin.json"):
        return None
    sh = o["shape"]
    if not (isinstance(sh, list) and len(sh) == 2):
        err("origin.json/shape: must be [rows, cols]")
    elif len(o["values"]) != sh[0] * sh[1]:
        err(f"origin.json: shape {sh} implies {sh[0]*sh[1]} values but got {len(o['values'])}")
    vals = o["values"]
    if vals:
        lo, hi = min(vals), max(vals)
        if lo < 0:
            err(f"origin.json/values: negative value {lo} — the grid is a normalised probability")
        if hi <= 0:
            err("origin.json/values: grid is entirely zero — the ensemble produced nothing")
        elif abs(hi - 1.0) > 0.01:
            warn(f"origin.json/values: max is {hi:.3f}; normalise the grid to peak at 1.0")
    tw = o["time_window"]
    if not (isinstance(tw, list) and len(tw) == 2):
        err("origin.json/time_window: must be [start, end]")
    else:
        a, b = parse_ts(tw[0], "origin.json/time_window[0]"), parse_ts(tw[1], "origin.json/time_window[1]")
        if a and b and a >= b:
            err("origin.json/time_window: start must be before end")
    if o["radius_50_km"] > o["radius_90_km"]:
        err("origin.json: radius_50_km exceeds radius_90_km — 50% mass sits inside 90% mass")
    if o["radius_90_km"] > 40 and not o["abstain"]:
        warn(f"origin.json: radius_90_km is {o['radius_90_km']} km but abstain is false — "
             "the agreed rule abstains above 40 km")
    if o["ensemble_runs"] < 10:
        warn(f"origin.json: only {o['ensemble_runs']} ensemble runs; uncertainty will look fake")
    if box:
        box.check(float(o["centroid"][0]), float(o["centroid"][1]), "origin.json/centroid")
    return o


def check_vessels(d, box):
    g = load(d / "vessels.geojson")
    if g is None:
        err("vessels.geojson: missing (required whenever 'attribute' is available)")
        return set()
    seen = set()
    for i, f in enumerate(g.get("features", [])):
        w = f"vessels.geojson[{i}]"
        p = f.get("properties") or {}
        if not need_keys(p, ["mmsi", "name", "vessel_type"], w + "/properties"):
            continue
        seen.add(str(p["mmsi"]))
        if f.get("geometry", {}).get("type") != "LineString":
            err(f"{w}: vessel tracks must be LineString")
            continue
        n = len(f["geometry"]["coordinates"])
        if n < 2:
            err(f"{w}: track has {n} point(s) — need at least 2")
        elif n > 800:
            warn(f"{w}: track has {n} points; decimate to ~500 to keep the map fast")
        if box:
            walk_coords(f["geometry"], box, w + "/geometry")
    return seen


def check_suspects(d, known_mmsi, origin):
    s = load(d / "suspects.json")
    if s is None:
        err("suspects.json: missing (required whenever 'attribute' is available)")
        return
    if not need_keys(s, ["funnel", "suspects", "excluded"], "suspects.json"):
        return
    f = s["funnel"]
    if need_keys(f, ["in_region", "in_window", "plausible", "scored"], "suspects.json/funnel"):
        seq = [f["in_region"], f["in_window"], f["plausible"], f["scored"]]
        if any(b > a for a, b in zip(seq, seq[1:])):
            err(f"suspects.json/funnel: counts must never increase down the funnel — got {seq}")
        if f["scored"] != len(s["suspects"]):
            err(f"suspects.json: funnel/scored is {f['scored']} but {len(s['suspects'])} suspects listed")
    for i, sus in enumerate(s["suspects"]):
        w = f"suspects.json/suspects[{i}]"
        if not need_keys(sus, ["mmsi", "name", "score", "closest_km", "reasons"], w):
            continue
        if not 0 <= sus["score"] <= 1:
            err(f"{w}: score {sus['score']} outside 0–1")
        if known_mmsi and str(sus["mmsi"]) not in known_mmsi:
            err(f"{w}: mmsi {sus['mmsi']} has no track in vessels.geojson — "
                "every named vessel must come from the real AIS file")
        if not sus["reasons"]:
            warn(f"{w}: no reasons given; judge-facing cards need plain-language justification")
    scores = [x.get("score", 0) for x in s["suspects"]]
    if scores != sorted(scores, reverse=True):
        err("suspects.json: suspects are not sorted by descending score")
    for i, ex in enumerate(s["excluded"]):
        if not need_keys(ex, ["mmsi", "reason"], f"suspects.json/excluded[{i}]"):
            continue
        if not str(ex["reason"]).strip():
            err(f"suspects.json/excluded[{i}]: reason must not be empty — "
                "exoneration without a reason is worse than no exoneration")
    if not s["excluded"]:
        warn("suspects.json: no excluded vessels; at least one exclusion is a demo requirement")
    if origin and origin.get("abstain") and s["suspects"]:
        err("suspects.json: origin.json has abstain=true, so suspects must be empty")


# ---------------------------------------------------------------------- main

def main():
    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    strict = "--strict" in sys.argv
    if not args:
        print(__doc__)
        return 2
    d = Path(args[0])
    if not d.is_dir():
        print(f"FAIL  {d} is not a directory")
        return 1

    print(f"\nValidating {d}\n" + "-" * 58)
    meta = check_meta(d)
    acts = meta["acts_available"] if meta else []
    b = check_bounds(d)
    box = Box(b) if b else None

    if "detect" in acts:
        check_detections(d, box)
    if "trace" in acts:
        check_particles(d, box, meta)
        origin = check_origin(d, box)
    else:
        origin = None
    if "attribute" in acts:
        known = check_vessels(d, box)
        check_suspects(d, known, origin)

    for w in WARNINGS:
        print(f"  WARN   {w}")
    for e in ERRORS:
        print(f"  ERROR  {e}")

    print("-" * 58)
    if ERRORS:
        print(f"FAIL   {len(ERRORS)} error(s), {len(WARNINGS)} warning(s)")
        print("       Fix in the producing stage, never by editing the bundle by hand.\n")
        return 1
    if WARNINGS and strict:
        print(f"FAIL   0 errors but {len(WARNINGS)} warning(s) under --strict\n")
        return 1
    print(f"PASS   acts={acts}  ({len(WARNINGS)} warning(s))\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
