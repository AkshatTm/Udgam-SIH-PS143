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
        return json.loads(path.read_text(encoding="utf-8"))
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
        # pad: drift particles and vessel tracks legitimately leave the scene, but a
        # 2 deg floor (~220 km) made the "well outside" warning unreachable — keep it
        # generous enough for a 24 h drift excursion, tight enough to still fire.
        self.pad = max(0.5, 0.5 * max(self.e - self.w, self.n - self.s))

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


def known_origin_coords(ko, where):
    """A known_origin is either [lon, lat] or {"lon":..., "lat":..., "label":...}.
    Return (lon, lat) as floats, or None if absent or malformed (malformed appends
    an error). This is the documented fixed source a trace-without-detect case seeds
    from — Golden Ray's wreck, Ennore's collision position (Master §6.1, decision D16)."""
    if ko is None:
        return None
    if isinstance(ko, dict):
        if "lon" not in ko or "lat" not in ko:
            err(f"{where}: known_origin object needs 'lon' and 'lat'")
            return None
        lon, lat = ko["lon"], ko["lat"]
    elif isinstance(ko, (list, tuple)) and len(ko) == 2:
        lon, lat = ko[0], ko[1]
    else:
        err(f"{where}: known_origin must be [lon, lat] or an object with lon/lat")
        return None
    try:
        return float(lon), float(lat)
    except (TypeError, ValueError):
        err(f"{where}: known_origin lon/lat must be numbers, got {lon!r}, {lat!r}")
        return None


def check_known_origin(m, box):
    """Shape-check meta.known_origin and, via box.check, catch a [lat, lon] swap in it."""
    coords = known_origin_coords(m.get("known_origin"), "meta.json/known_origin")
    if coords and box:
        box.check(coords[0], coords[1], "meta.json/known_origin")


def polygon_area_km2(geom):
    """Rough planar area of a GeoJSON Polygon's outer ring, cos-lat scaled at its
    centroid. Good to a few % at slick scale — enough to catch an area_km2 that is
    off by a factor, not a rounding difference."""
    if geom.get("type") != "Polygon" or not geom.get("coordinates"):
        return None
    ring = geom["coordinates"][0]
    if len(ring) < 4:
        return None
    lat0 = sum(p[1] for p in ring) / len(ring)
    kx = 111.32 * math.cos(math.radians(lat0))
    ky = 111.32
    s = 0.0
    for (x1, y1), (x2, y2) in zip(ring, ring[1:]):
        s += (x1 * kx) * (y2 * ky) - (x2 * kx) * (y1 * ky)
    return abs(s) / 2.0


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
    bad = [a for a in acts if a not in ("detect", "trace", "attribute", "verify")]
    if bad:
        err(f"meta.json/acts_available: unknown act(s) {bad}")
    if "trace" in acts and "detect" not in acts and m.get("known_origin") is None:
        err("meta.json: 'trace' without 'detect' requires meta.known_origin (a documented "
            "fixed source to seed from) — got neither a detection nor a known origin")
    if "attribute" in acts and "trace" not in acts:
        err("meta.json: 'attribute' without 'trace' — attribution needs an origin cloud")
    if "verify" in acts and not (d / "verification.json").exists():
        err("meta.json: 'verify' in acts_available but verification.json is missing")

    # ais_source (Master §6.1, D20) — REQUIRED whenever attribution runs, because it decides
    # which of Jaiveer's scoring components can fire at all. NOAA reports every ~71 s; GFW's
    # presence layer gives one position per vessel per HOUR, so 'gap' is structurally
    # impossible there and 'slowdown' is very coarse. The scorer has to know which it is in.
    ais = m.get("ais_source")
    if ais is not None and ais not in ("noaa_dense", "gfw_hourly"):
        err(f"meta.json/ais_source: must be noaa_dense|gfw_hourly, got {ais!r}")
    if "attribute" in acts and ais is None:
        err("meta.json: 'attribute' is available but ais_source is missing — attribution "
            "confidence depends on AIS sampling density and every case must declare which "
            "regime it is in (noaa_dense ~71 s, gfw_hourly 1/hour)")

    # v3 meta fields — validated only if present (Master §6.1); case selection authors them
    ct = m.get("case_type")
    if ct is not None and ct not in ("spill", "lookalike", "nospill"):
        err(f"meta.json/case_type: must be spill|lookalike|nospill, got {ct!r}")
    gal = m.get("gallery")
    if isinstance(gal, dict):
        diff = gal.get("difficulty")
        if diff is not None and diff not in ("easy", "medium", "hard"):
            err(f"meta.json/gallery.difficulty: must be easy|medium|hard, got {diff!r}")
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
        geom = f.get("geometry", {})
        if geom.get("type") not in ("Polygon", "MultiPolygon"):
            err(f"{w}: detection geometry must be Polygon, got {geom.get('type')!r}")
        computed = polygon_area_km2(geom)
        if computed and p.get("area_km2", 0) > 0:
            ratio = computed / p["area_km2"]
            if ratio > 2 or ratio < 0.5:
                warn(f"{w}: area_km2 is {p['area_km2']} but the polygon measures "
                     f"~{computed:.1f} km2 ({ratio:.1f}x) — one of them is wrong")
        if box:
            box.check(float(p["centroid"][0]), float(p["centroid"][1]), w + "/centroid")
            walk_coords(geom, box, w + "/geometry")
    if oil == 0:
        warn("detections.geojson: zero 'oil' features — correct for a no-spill case, "
             "an error for any case with 'trace' in acts_available")


def check_particles(d, box, meta, fname="particles.json", expect="backward", required=True):
    """Validate one particle file. Runs twice: the backward rewind (required with 'trace')
    and, when present, particles_forward.json — a SEPARATE file, never an overwrite of the
    first (Master §6.4)."""
    p = load(d / fname)
    if p is None:
        if required:
            err(f"{fname}: missing (required whenever 'trace' is available)")
        return None
    if not need_keys(p, ["t0", "direction", "timestep_minutes", "n_steps",
                         "n_particles", "positions"], fname):
        return None
    t0 = parse_ts(p["t0"], f"{fname}/t0")
    if meta and t0:
        dt = parse_ts(meta["detection_time"], "meta.json/detection_time")
        if dt and abs((t0 - dt).total_seconds()) > 60:
            err(f"{fname}/t0 ({p['t0']}) does not match meta detection_time "
                f"({meta['detection_time']}) — the rewind must start at the satellite pass")
    if p["direction"] != expect:
        if expect == "forward":
            err(f"{fname}/direction is {p['direction']!r}, must be 'forward' — this looks like "
                "a copy of the backward run. The forward prediction is a second integration, "
                "not a renamed file (Master §6.4).")
        else:
            warn(f"{fname}/direction is {p['direction']!r}; the demo rewind expects 'backward'")
    pos = p["positions"]
    if not isinstance(pos, list) or not pos:
        err(f"{fname}/positions: must be a non-empty list of timesteps")
        return None
    if len(pos) != p["n_steps"]:
        err(f"{fname}: n_steps says {p['n_steps']} but positions has {len(pos)} timesteps")
    if len(pos[0]) != p["n_particles"]:
        err(f"{fname}: n_particles says {p['n_particles']} but step 0 has {len(pos[0])}")
    lens = {len(s) for s in pos}
    if len(lens) > 1:
        err(f"{fname}: timesteps have differing particle counts {sorted(lens)[:5]} — "
            "particles must never be added or dropped mid-run")
    span_h = (p["n_steps"] - 1) * p["timestep_minutes"] / 60
    if not 6 <= span_h <= 72:
        warn(f"{fname}: run spans {span_h:.1f} h; the demo is scoped to ~24 h")
    if box:
        for si in (0, len(pos) // 2, len(pos) - 1):
            for pt in pos[si][::max(1, len(pos[si]) // 50)]:
                box.check(float(pt[0]), float(pt[1]), f"{fname}/positions[{si}]")
    # displacement plausibility — the units bug catcher
    try:
        a, b = pos[0][0], pos[-1][0]
        mlat = math.radians((a[1] + b[1]) / 2)
        dx = (b[0] - a[0]) * 111.32 * math.cos(mlat)
        dy = (b[1] - a[1]) * 111.32
        dist = math.hypot(dx, dy)
        if dist > 400:
            err(f"{fname}: particle 0 travelled {dist:.0f} km in {span_h:.0f} h "
                "— check current units (HYCOM on GEE is int x 0.001 m/s: divide by 1000)")
        elif dist < 0.5:
            err(f"{fname}: particle 0 barely moved ({dist:.2f} km) — fields may be zero")
        elif dist > 250:
            warn(f"{fname}: particle 0 travelled {dist:.0f} km — high but not impossible")
    except (IndexError, TypeError):
        err(f"{fname}/positions: malformed coordinate arrays")
    return p


def check_particles_forward(d, box, meta, backward):
    """particles_forward.json is optional. When it exists it must be a genuine second run:
    same t0, opposite direction, and not a byte-for-byte twin of the rewind."""
    fwd = check_particles(d, box, meta, fname="particles_forward.json",
                          expect="forward", required=False)
    if fwd and backward and fwd.get("positions") == backward.get("positions"):
        err("particles_forward.json: positions are identical to particles.json — the forward "
            "prediction was never integrated, only relabelled")


def check_origin(d, box):
    o = load(d / "origin.json")
    if o is None:
        err("origin.json: missing (required whenever 'trace' is available)")
        return None
    if not need_keys(o, ["bounds", "shape", "values", "centroid", "radius_50_km",
                         "radius_90_km", "time_window", "ensemble_runs", "abstain"],
                     "origin.json"):
        return None
    ob = o["bounds"]
    if not need_keys(ob, ["west", "south", "east", "north"], "origin.json/bounds"):
        return None
    if ob["west"] >= ob["east"] or ob["south"] >= ob["north"]:
        err("origin.json/bounds: west<east and south<north required (this is the grid's "
            "own rectangle, not bounds.json)")
    elif box:
        # renderability hint (Harshita's point): a PASS should say whether the frontend
        # can frame this. A real origin cloud legitimately sits mostly off-scene, so this
        # is a warning, never an error — it only flags a rectangle so far out it reads
        # like a units or hemisphere bug rather than a long rewind.
        ow, oh = ob["east"] - ob["west"], ob["north"] - ob["south"]
        overshoot = max(box.w - ob["east"], ob["west"] - box.e,
                        box.s - ob["north"], ob["south"] - box.n)
        if overshoot > 3 * max(ow, oh):
            warn(f"origin.json/bounds sits {overshoot:.2f} deg beyond the scene on one side "
                 f"(> 3x its own {max(ow, oh):.2f} deg span) — check the rewind isn't running "
                 "the wrong direction or in the wrong longitude convention")
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

    # time_window_method (D12) — 'bounded' is a SEARCH BRACKET, not a measured release time,
    # and the frontend renders the two differently. An absent value is the dangerous case.
    twm = o.get("time_window_method")
    if twm is None:
        warn("origin.json: no time_window_method — the frontend cannot tell a measured window "
             "from a search bracket and will render a bracket as a measurement (D12)")
    elif twm not in ("bounded", "convergence"):
        err(f"origin.json/time_window_method: must be bounded|convergence, got {twm!r}")

    # Optional v3/v4 blocks (Master §6.5). Absence hides a UI row; it must never throw.
    am = o.get("age_method")
    if am is not None and am not in ("shear", "fay", "elongation", "combined",
                                     "disagreement", "none"):
        err(f"origin.json/age_method: must be shear|fay|elongation|combined|disagreement|none, "
            f"got {am!r}")
    aw = o.get("age_weathering")
    if aw is not None and aw not in ("fresh", "weathered", "unknown"):
        err(f"origin.json/age_weathering: must be fresh|weathered|unknown, got {aw!r}")
    ah = o.get("age_hours")
    if ah is not None:
        if not (isinstance(ah, list) and len(ah) == 2):
            err("origin.json/age_hours: must be [low, high]")
        elif ah[0] > ah[1]:
            err(f"origin.json/age_hours: low {ah[0]} exceeds high {ah[1]}")
        elif ah[0] < 0:
            err(f"origin.json/age_hours: negative age {ah[0]}")
    ae = o.get("age_estimators")
    if ae is not None:
        if not isinstance(ae, dict):
            err("origin.json/age_estimators: must be an object of estimator -> [low, high] or null")
        else:
            for k, v in ae.items():
                # null means this estimator did not apply — never render it as a zero band
                if v is None:
                    continue
                if not (isinstance(v, list) and len(v) == 2 and v[0] <= v[1]):
                    err(f"origin.json/age_estimators.{k}: must be null or [low, high], got {v!r}")
    sf = o.get("stranded_fraction")
    if sf is not None and not (isinstance(sf, (int, float)) and 0 <= sf <= 1):
        err(f"origin.json/stranded_fraction: must be a fraction in 0-1, got {sf!r}")
    oc = o.get("opendrift_comparison")
    if oc is not None:
        if not isinstance(oc, dict):
            err("origin.json/opendrift_comparison: must be an object")
        else:
            need_keys(oc, ["centroid_separation_km", "r90_ratio"],
                      "origin.json/opendrift_comparison")
            r = oc.get("r90_ratio")
            if isinstance(r, (int, float)) and r <= 0:
                err(f"origin.json/opendrift_comparison.r90_ratio: must be positive, got {r}")
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


def check_suspects(d, known_mmsi, origin, box=None, ais_source=None):
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
        st = sus.get("source_type")
        if st is not None and st not in ("vessel", "dark_vessel", "infrastructure",
                                         "natural_seep"):
            err(f"{w}: source_type must be vessel|dark_vessel|infrastructure|natural_seep, "
                f"got {st!r}")
        comps = sus.get("components")
        if isinstance(comps, dict):
            for cname, cval in comps.items():
                # null is meaningful — a not-applicable component, never rendered as 0
                if cval is not None and not (isinstance(cval, (int, float)) and 0 <= cval <= 1):
                    err(f"{w}: components.{cname} must be null or in 0–1, got {cval!r}")
            # D20: at one position per vessel per hour you cannot see a 30-minute silence.
            # A number here is not a low score, it is a fabricated measurement.
            if ais_source == "gfw_hourly":
                for cname in ("gap", "slowdown"):
                    if isinstance(comps.get(cname), (int, float)):
                        err(f"{w}: components.{cname} is {comps[cname]} on a gfw_hourly case — "
                            f"hourly AIS cannot resolve {cname}, so this must be null, not a "
                            "number. A zero where a null belongs is an honesty bug (D20).")

        # component_notes (D29) — explanation, not evidence. Keys must name real components,
        # and every gated (null) component should say why, because the UI renders null as
        # "n/a" and an unexplained "n/a" reads as a broken feature rather than a refusal to
        # measure something unmeasurable.
        notes = sus.get("component_notes")
        if notes is not None:
            if not isinstance(notes, dict):
                err(f"{w}: component_notes must be an object keyed by component name")
            else:
                # Only skippable when there is no components object at all to check against;
                # an EMPTY components dict still means the note names nothing real.
                have_comps = isinstance(comps, dict)
                for k, v in notes.items():
                    if have_comps and k not in comps:
                        err(f"{w}: component_notes.{k} names no component in components "
                            f"{sorted(comps)} — a note must explain a bar that exists")
                    if not str(v or "").strip():
                        err(f"{w}: component_notes.{k} is empty; drop the key or write the reason")
        if isinstance(comps, dict):
            missing = [c for c, v in comps.items()
                       if v is None and not str((notes or {}).get(c) or "").strip()]
            if missing:
                warn(f"{w}: components {missing} are null with no component_notes entry — "
                     "the card will render 'n/a' with nothing behind it (D29)")

    # A component that returns the SAME value for every scored suspect discriminates nothing:
    # it adds a constant to every score, changes no ranking, and inflates the numbers on screen
    # by its full weight. This is the check that catches type_prior = 1.00 across a homogeneous
    # offshore fleet mechanically, instead of someone noticing it by eye (D28).
    scored = [x for x in s["suspects"] if isinstance(x.get("components"), dict)]
    if len(scored) >= 3:
        names = set()
        for x in scored:
            names |= set(x["components"])
        for cname in sorted(names):
            vals = [x["components"].get(cname) for x in scored]
            if any(v is None for v in vals):
                continue
            if not all(isinstance(v, (int, float)) for v in vals):
                continue
            if len(set(vals)) == 1:
                warn(f"suspects.json: components.{cname} is {vals[0]} for all {len(scored)} "
                     "scored suspects — it separates nobody, so it only inflates every score "
                     "by its weight. Gate it to null instead (D28).")
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
    if s.get("abstained") and s["suspects"]:
        err("suspects.json: abstained=true, so suspects must be empty")

    # v3 extended source types (Master §6.7) — optional arrays, checked if present
    for i, dv in enumerate(s.get("dark_vessels", []) or []):
        w = f"suspects.json/dark_vessels[{i}]"
        if not need_keys(dv, ["lon", "lat", "score"], w):
            continue
        if dv.get("mmsi") is not None:
            err(f"{w}: a dark vessel has no AIS identity — mmsi must be null, got {dv['mmsi']!r}")
        if not 0 <= dv["score"] <= 1:
            err(f"{w}: score {dv['score']} outside 0–1")
        if box:
            box.check(float(dv["lon"]), float(dv["lat"]), w)
    for i, inf in enumerate(s.get("infrastructure", []) or []):
        w = f"suspects.json/infrastructure[{i}]"
        if not need_keys(inf, ["name", "lon", "lat", "score"], w):
            continue
        if not 0 <= inf["score"] <= 1:
            err(f"{w}: score {inf['score']} outside 0–1")
        if box:
            box.check(float(inf["lon"]), float(inf["lat"]), w)

    # natural_seep (D19) — the fourth source class. It is an object, not a list: either the
    # detection sits in documented seep territory or it does not. A flag raised without a
    # named source is exactly the claim we could not substantiate on Mumbai, so 'flagged'
    # true demands both a source and a note.
    ns = s.get("natural_seep")
    if ns is not None:
        if not isinstance(ns, dict):
            err("suspects.json/natural_seep: must be an object with flagged/source/note")
        elif not isinstance(ns.get("flagged"), bool):
            err("suspects.json/natural_seep.flagged: must be true or false")
        elif ns["flagged"]:
            for k in ("source", "note"):
                if not str(ns.get(k) or "").strip():
                    err(f"suspects.json/natural_seep.{k}: required when flagged is true — "
                        "a seep claim on screen needs a citable source, not a bare flag")


def check_verification(d):
    v = load(d / "verification.json")
    if v is None:
        err("verification.json: missing (required whenever 'verify' is available)")
        return
    if not need_keys(v, ["official_finding", "naap_result", "assessment"], "verification.json"):
        return
    of = v["official_finding"]
    if need_keys(of, ["summary", "responsible_parties", "source_name", "source_url",
                      "source_type"], "verification.json/official_finding"):
        if not isinstance(of["responsible_parties"], list):
            err("verification.json/official_finding/responsible_parties: must be a list")
        if not str(of["source_url"]).strip():
            err("verification.json/official_finding/source_url: must be present and non-empty — "
                "this is the 'is this real?' link")
        for opt in ("volume_reported", "caveat"):
            if not of.get(opt):
                warn(f"verification.json/official_finding: no {opt} — recommended for the Verify screen")
    nr = v["naap_result"]
    if need_keys(nr, ["origin_summary", "top_suspects", "abstained"], "verification.json/naap_result"):
        if not isinstance(nr["top_suspects"], list):
            err("verification.json/naap_result/top_suspects: must be a list (may be empty)")
    a = v["assessment"]
    if need_keys(a, ["verdict", "explanation"], "verification.json/assessment"):
        if a["verdict"] not in ("hit", "partial", "miss", "not_applicable"):
            err(f"verification.json/assessment/verdict: must be hit|partial|miss|not_applicable, "
                f"got {a['verdict']!r}")
        if not str(a["explanation"]).strip():
            err("verification.json/assessment/explanation: human-written prose, must not be empty")


def check_index(cases_root):
    idx = load(cases_root / "index.json")
    if idx is None:
        err("cases/index.json: missing")
        return []
    if not need_keys(idx, ["cases", "default"], "cases/index.json"):
        return []
    listed = idx["cases"]
    if not isinstance(listed, list) or not listed:
        err("cases/index.json/cases: must be a non-empty list, strongest case first")
        return []
    for cid in listed:
        if not (cases_root / cid / "meta.json").exists():
            err(f"cases/index.json: lists {cid!r} but cases/{cid}/meta.json does not exist")
    if idx["default"] not in listed:
        err(f"cases/index.json: default {idx['default']!r} is not in the cases list")
    return listed


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

    # Pointed at cases/ (an index, not a bundle): validate the index and every case it lists.
    if (d / "index.json").exists() and not (d / "meta.json").exists():
        listed = check_index(d)
        index_errors = list(ERRORS)
        for e in index_errors:
            print(f"  ERROR  {e}")
        rc = 1 if index_errors else 0
        for cid in listed:
            print(f"\n=== {cid} ===")
            if _run_bundle(d / cid, strict) != 0:
                rc = 1
        print("-" * 58)
        print("PASS   cases/index.json + all listed cases\n" if rc == 0
              else "FAIL   cases/ did not fully validate\n")
        return rc

    return _run_bundle(d, strict)


def _run_bundle(d, strict=False):
    del ERRORS[:]
    del WARNINGS[:]
    print(f"\nValidating {d}\n" + "-" * 58)
    meta = check_meta(d)
    acts = meta["acts_available"] if meta else []
    b = check_bounds(d)
    box = Box(b) if b else None

    if meta:
        check_known_origin(meta, box)

    if "detect" in acts:
        check_detections(d, box)
    if "trace" in acts:
        backward = check_particles(d, box, meta)
        check_particles_forward(d, box, meta, backward)
        origin = check_origin(d, box)
    else:
        origin = None
    if "attribute" in acts:
        known = check_vessels(d, box)
        check_suspects(d, known, origin, box, meta.get("ais_source") if meta else None)
    if "verify" in acts:
        check_verification(d)

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
