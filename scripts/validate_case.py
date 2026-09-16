#!/usr/bin/env python3
"""
validate_case.py — integration insurance for UDGAM.

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


def _reject_constant(name):
    """json.loads accepts bare Infinity / -Infinity / NaN. The JSON spec does not, and neither
    does the browser's JSON.parse — so a bundle that loads fine here dies in the frontend with
    'Unexpected token I'. Python writes those tokens the moment a non-finite float reaches
    json.dumps, which is one np.nanmean() over an array containing -inf away at all times
    (nanmean ignores NaN but propagates -inf; TRAPS #22 nodata is -inf). Fail loudly instead."""
    raise ValueError(
        f"bare {name} — not valid JSON and the browser will refuse to parse this file. "
        f"A non-finite float reached json.dumps; find it in the PRODUCING code (a statistic "
        f"over nodata, most likely — mask on np.isfinite() first, see TRAPS #22) and never "
        f"patch the bundle by hand")


def load(path):
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"), parse_constant=_reject_constant)
    except json.JSONDecodeError as e:
        err(f"{path.name}: not valid JSON — {e}")
        return None
    except ValueError as e:
        err(f"{path.name}: {e}")
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


# How far a layer may legitimately sit from the scene, in km. The scene box is a tight pad
# around the slick (D14), but the trace and attribute layers leave it by construction:
# Jacksonville's origin is 132 km off-scene and its vessel tracks reach 226 km. Degrees were
# the wrong unit here, because a degree of longitude at Alaska is half the width it is at
# Mumbai. A 0-360 leak or a hemisphere flip is thousands of km out, so the warning still fires.
TRACE_REACH_KM = 300   # 24 h at ~3.5 m/s, faster than any surface current we will meet
VESSEL_REACH_KM = 400  # trace reach plus the 2 x radius_90_km AIS search box


class Box:
    def __init__(self, b, reach_km=None, label="the scene bounds"):
        self.w, self.s = float(b["west"]), float(b["south"])
        self.e, self.n = float(b["east"]), float(b["north"])
        self.label = label
        if reach_km is None:
            # pad: a detection belongs in the scene, but a 2 deg floor (~220 km) made the
            # "well outside" warning unreachable — keep it tight enough to still fire.
            self.pad_x = self.pad_y = max(0.5, 0.5 * max(self.e - self.w, self.n - self.s))
        else:
            mid = math.radians((self.s + self.n) / 2)
            self.pad_y = reach_km / 111.32
            self.pad_x = min(180.0, reach_km / (111.32 * max(math.cos(mid), 0.05)))

    def reach(self, reach_km, label):
        """The same scene, padded for a layer that legitimately leaves it."""
        return Box({"west": self.w, "south": self.s, "east": self.e, "north": self.n},
                   reach_km, label)

    def check(self, lon, lat, where):
        if not (-180 <= lon <= 180):
            err(f"{where}: longitude {lon} out of range — is this [lat, lon] instead of [lon, lat]?")
            return False
        if not (-90 <= lat <= 90):
            err(f"{where}: latitude {lat} out of range — coordinates are [lon, lat], not [lat, lon]")
            return False
        inside_swapped = (self.w - self.pad_x <= lat <= self.e + self.pad_x and
                          self.s - self.pad_y <= lon <= self.n + self.pad_y)
        inside = (self.w - self.pad_x <= lon <= self.e + self.pad_x and
                  self.s - self.pad_y <= lat <= self.n + self.pad_y)
        if not inside and inside_swapped:
            err(f"{where}: [{lon}, {lat}] is outside bounds but INSIDE them when swapped — "
                f"this file is writing [lat, lon]. Fix the producer, not this check.")
            return False
        if not inside:
            warn(f"{where}: [{lon}, {lat}] falls well outside {self.label}")
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


def check_infrastructure_candidates(m, box):
    """meta.infrastructure_candidates (Master §6.1, D38) — declared fixed sources Stage 3 scores.

    Optional list. Every entry needs name, lon, lat, kind and source, exactly what
    pipeline/attribute/infrastructure.py:load_candidates demands, so a bundle that would make
    the scorer raise fails here first. `source` is the provenance of the coordinate: these
    positions are case input, not something the pipeline found, and a structure named on
    screen with no source is the infrastructure version of a vessel name not in the AIS file.
    A structure may legitimately sit off the exported scene, so the box is the trace reach and
    'outside' is only a warning; a [lat, lon] swap is still an error.
    """
    raw = m.get("infrastructure_candidates")
    if raw is None:
        return
    where = "meta.json/infrastructure_candidates"
    if not isinstance(raw, list):
        err(f"{where}: must be a list of candidate objects")
        return
    for i, c in enumerate(raw):
        w = f"{where}[{i}]"
        if not isinstance(c, dict):
            err(f"{w}: must be an object with name, lon, lat, kind, source")
            continue
        missing = [k for k in ("name", "lon", "lat", "kind", "source")
                   if c.get(k) is None or (isinstance(c.get(k), str) and not c[k].strip())]
        if missing:
            err(f"{w}: missing {', '.join(missing)} — every declared structure needs a source "
                "for its coordinate")
            continue
        try:
            lon, lat = float(c["lon"]), float(c["lat"])
        except (TypeError, ValueError):
            err(f"{w}: lon/lat must be numbers, got {c['lon']!r}, {c['lat']!r}")
            continue
        if box:
            box.check(lon, lat, w)
        elif not (-180 <= lon <= 180 and -90 <= lat <= 90):
            err(f"{w}: [{lon}, {lat}] out of range — coordinates are [lon, lat]")


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

    # provenance (Master §6.1, D33) — which corpus the pixels came from, and therefore which of
    # Stage 1's two detection paths runs. Absent means "satellite", so the existing library needs
    # no backfill. This replaces a CRS sniff that never worked: Zenodo Part III tiles carry
    # EPSG:4326 like a GEE export, so "no CRS => benchmark" matched nothing it was meant to.
    prov = m.get("provenance")
    if prov is not None and prov not in ("satellite", "benchmark"):
        err(f"meta.json/provenance: must be satellite|benchmark, got {prov!r}")
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
    check_ship_detections(g, feats, box)


def _check_contacts(ships, box, where):
    """One list of radar contacts: [{lon, lat, px_area, peak_db}, ...]."""
    if not isinstance(ships, list):
        err(f"{where}: must be a list")
        return False
    for i, s in enumerate(ships):
        w = f"{where}[{i}]"
        if not need_keys(s, ["lon", "lat", "px_area", "peak_db"], w):
            continue
        lon, lat, px, pk = s["lon"], s["lat"], s["px_area"], s["peak_db"]
        if not all(isinstance(v, (int, float)) and math.isfinite(v) for v in (lon, lat, px, pk)):
            err(f"{w}: lon, lat, px_area and peak_db must all be finite numbers")
            continue
        if px <= 0:
            err(f"{w}: px_area must be positive")
        if box:
            box.check(float(lon), float(lat), w)
    return True


def check_ship_detections(g, feats, box):
    """Master §6.3 / D34. Radar contacts are a SCENE-level observation, so the canonical list is
    top-level on the FeatureCollection — the only place a scene with zero detections can keep
    them. Both Zenodo bundles silently dropped theirs (1 and 31) under the old per-feature shape.
    Absent = the detector was not run or not recorded; [] = it ran and found none (null ≠ 0).
    The per-feature copy is deprecated: accepted, never written by run.py, and must agree."""
    top = g.get("ship_detections")
    if top is None:
        warn("detections.geojson: no top-level ship_detections — the ship detector's result is "
             "not recorded, so contacts on this scene are unknown, not absent (Master §6.3, D34). "
             "Re-run pipeline/detect/run.py.")
    elif not _check_contacts(top, box, "detections.geojson/ship_detections"):
        return

    canon = json.dumps(top, sort_keys=True) if top is not None else None
    legacy = 0
    for i, f in enumerate(feats):
        per = (f.get("properties") or {}).get("ship_detections")
        if per is None:
            continue
        legacy += 1
        w = f"detections.geojson[{i}]/properties/ship_detections"
        if not _check_contacts(per, box, w):
            continue
        if canon is not None and json.dumps(per, sort_keys=True) != canon:
            warn(f"{w}: disagrees with the top-level ship_detections — two lists for one scene, "
                 "and the map will draw whichever it reads")
    if legacy:
        warn(f"detections.geojson: {legacy} feature(s) still carry the deprecated per-feature "
             "ship_detections (D34). Harmless, but re-run run.py so the scene list lives once.")


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
        warn(f"{fname}: run spans {span_h:.1f} h; Stage 2 is scoped to at most 72 h "
             f"(the rewind horizon, raised from 24 h on 16 Sept 2026)")
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
        # DERIVE THE CEILING FROM THE SPAN, do not hardcode it.
        #
        # This used to be a flat `dist > 400`, which was right for the only span that existed
        # when it was written (24 h). At the 72 h horizon Jacksonville travels ~443 km at a
        # perfectly plausible 1.7 m/s, so the flat number would have ERRORED on the hero case --
        # the exact failure step.py's own assert_displacement_plausible docstring describes:
        # "the guard was calibrated on the first case in the library and then met the second".
        #
        # MAX_PLAUSIBLE_SPEED_MS = 3.0 is step.py's, kept in sync by hand because this script is
        # deliberately stdlib-only so CI installs nothing. The warn threshold is the same speed
        # bound at a more ordinary 1.9 m/s.
        max_speed_ms = 3.0
        ceiling_km = max_speed_ms * 3.6 * span_h
        warn_km = 1.9 * 3.6 * span_h
        if dist > ceiling_km:
            err(f"{fname}: particle 0 travelled {dist:.0f} km in {span_h:.0f} h "
                f"= {dist / max(span_h, 1e-9) / 3.6:.2f} m/s, past the {max_speed_ms} m/s "
                f"ceiling ({ceiling_km:.0f} km over this span) "
                "— check current units (HYCOM on GEE is int x 0.001 m/s: divide by 1000)")
        elif dist < 0.5:
            err(f"{fname}: particle 0 barely moved ({dist:.2f} km) — fields may be zero")
        elif dist > warn_km:
            warn(f"{fname}: particle 0 travelled {dist:.0f} km in {span_h:.0f} h "
                 f"= {dist / max(span_h, 1e-9) / 3.6:.2f} m/s — high but not impossible")
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


def check_forward_impact(d, box, meta, backward):
    """forward_impact.json (Master 6.10) — optional, and only meaningful with a 'trace' act.

    The mirror of origin.json: same 50-member cloud, pushed forward from t0 instead of rewound.
    The checks that earn their place here are the ones that catch a forecast which LOOKS fine:
    a stranding curve that goes down (physically impossible — beaching is sticky), a landfall
    hour reported as 0 when nothing actually beached (Rule 4), and a [lat, lon] centroid.
    """
    f = load(d / "forward_impact.json")
    if f is None:
        return None
    if not need_keys(f, ["t0", "direction", "horizon_hours", "ensemble_runs", "envelope",
                         "first_landfall_hours", "stranded_fraction_at_horizon",
                         "coast_segments", "assets_at_risk"], "forward_impact.json"):
        return None

    if f["direction"] != "forward":
        err(f"forward_impact.json/direction is {f['direction']!r}, must be 'forward' — a forward "
            "forecast is a second integration, not a relabelled rewind (Master 6.10)")

    t0 = parse_ts(f["t0"], "forward_impact.json/t0")
    if t0 and backward and backward.get("t0"):
        bt0 = parse_ts(backward["t0"], "particles.json/t0")
        if bt0 and abs((t0 - bt0).total_seconds()) > 60:
            err(f"forward_impact.json/t0 ({f['t0']}) does not match particles.json/t0 "
                f"({backward['t0']}) — forward and backward must start from the same cloud")

    runs = f["ensemble_runs"]
    if not isinstance(runs, int) or runs < 1:
        err(f"forward_impact.json/ensemble_runs: {runs!r} — must be a positive integer")

    env = f["envelope"]
    if not isinstance(env, list) or not env:
        err("forward_impact.json/envelope: must be a non-empty list, one row per hour")
        return None

    prev_hours, prev_stranded = None, None
    for i, row in enumerate(env):
        where = f"forward_impact.json/envelope[{i}]"
        if not need_keys(row, ["hours", "radius_50_km", "radius_90_km", "centroid",
                               "stranded_fraction"], where):
            continue
        h = row["hours"]
        if i == 0 and h != 0:
            err(f"{where}/hours is {h}, must start at 0 — row 0 is the slick at t0")
        if prev_hours is not None and h <= prev_hours:
            err(f"{where}/hours {h} does not increase on {prev_hours} — one row per hour, "
                "strictly increasing")
        prev_hours = h

        r50, r90 = row["radius_50_km"], row["radius_90_km"]
        for name, r in (("radius_50_km", r50), ("radius_90_km", r90)):
            if not isinstance(r, (int, float)) or r < 0:
                err(f"{where}/{name}: {r!r} — must be a non-negative number in km")
        if isinstance(r50, (int, float)) and isinstance(r90, (int, float)) and r90 < r50:
            err(f"{where}: radius_90_km {r90} < radius_50_km {r50} — 90% of the ensemble cannot "
                "sit inside a tighter circle than 50%")

        c = row["centroid"]
        if not isinstance(c, list) or len(c) != 2:
            err(f"{where}/centroid: must be [lon, lat]")
        elif box:
            box.check(c[0], c[1], f"{where}/centroid")

        sf = row["stranded_fraction"]
        if not isinstance(sf, (int, float)) or not (0.0 <= sf <= 1.0):
            err(f"{where}/stranded_fraction: {sf!r} — must be a fraction in [0, 1], never a percent")
        elif prev_stranded is not None and sf < prev_stranded - 1e-9:
            err(f"{where}/stranded_fraction drops {prev_stranded} -> {sf} — stranding is sticky, "
                "so the curve can only rise or hold. A particle cannot un-beach.")
        if isinstance(sf, (int, float)):
            prev_stranded = sf

    horizon = f["horizon_hours"]
    if isinstance(horizon, (int, float)) and prev_hours is not None and prev_hours != horizon:
        err(f"forward_impact.json: horizon_hours is {horizon} but the last envelope row is "
            f"hour {prev_hours} — the forecast does not reach its stated horizon")

    # Rule 4, both directions. This is the check the whole file exists for: "no landfall" and
    # "landfall at t0" are opposite claims and a 0 here would silently make the second one.
    at_h = f["stranded_fraction_at_horizon"]
    first = f["first_landfall_hours"]
    if isinstance(at_h, (int, float)) and at_h == 0 and first is not None:
        err(f"forward_impact.json: stranded_fraction_at_horizon is 0 but first_landfall_hours is "
            f"{first!r} — with nothing ashore, landfall was never observed and the honest value "
            "is null, not a number (Rule 4)")
    if first is None and isinstance(at_h, (int, float)) and at_h > 0:
        err(f"forward_impact.json: stranded_fraction_at_horizon is {at_h} but first_landfall_hours "
            "is null — something beached, so there is a first time it happened")
    if first is not None:
        if not isinstance(first, (int, float)) or first < 0:
            err(f"forward_impact.json/first_landfall_hours: {first!r} — must be null or a "
                "non-negative number of hours")
        elif isinstance(horizon, (int, float)) and first > horizon:
            err(f"forward_impact.json/first_landfall_hours {first} is beyond the "
                f"{horizon} h horizon — nothing can beach after the run ends")

    if isinstance(at_h, (int, float)) and prev_stranded is not None:
        if abs(at_h - prev_stranded) > 1e-6:
            err(f"forward_impact.json: stranded_fraction_at_horizon {at_h} disagrees with the "
                f"last envelope row ({prev_stranded})")

    # null means "not measured"; [] would claim "measured, and there are none" (Master 6.10)
    for key in ("coast_segments", "assets_at_risk"):
        v = f[key]
        if v is not None and not isinstance(v, list):
            err(f"forward_impact.json/{key}: {v!r} — must be null (not measured) or a list")
        if v == []:
            err(f"forward_impact.json/{key} is [] — an empty list claims the search ran and found "
                "nothing. It has not run: no gazetteer, no cited asset layer. Use null (Rule 4).")
    return f


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
    elif twm not in ("bounded", "convergence", "age"):
        err(f"origin.json/time_window_method: must be bounded|convergence|age, got {twm!r}")

    # Optional v3/v4 blocks (Master §6.5). Absence hides a UI row; it must never throw.
    am = o.get("age_method")
    if am is not None and am not in ("shear", "fay", "elongation", "track", "combined",
                                     "disagreement", "none"):
        err(f"origin.json/age_method: must be shear|fay|elongation|track|combined|disagreement|"
            f"none, got {am!r}")

    # age_posterior (age engine v2, Master §6.5, 16 Sept 2026). A window that claims to be
    # MEASURED FROM AGE must carry the posterior it came from, and must agree with it.
    ap_ = o.get("age_posterior")
    if twm == "age" and ap_ is None:
        err("origin.json: time_window_method is 'age' but there is no age_posterior — a window "
            "cannot claim to be measured from an age it does not carry")
    if ap_ is not None:
        check_age_posterior(o, ap_)
    mm = o.get("model_mix")
    if mm is not None:
        check_model_mix(mm)
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
    # wind_share (Master §6.5): share of drift displacement due to windage, a 0-1 fraction.
    # Omitted, never zeroed, when the field is synthetic, since a 0 would claim a calm we never measured.
    ws = o.get("wind_share")
    if ws is not None and not (isinstance(ws, (int, float)) and not isinstance(ws, bool)
                               and 0 <= ws <= 1):
        err(f"origin.json/wind_share: must be a fraction in 0-1 (not a percent), got {ws!r}")
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


def check_age_posterior(o, ap_):
    """age_posterior: {hours_grid, prob, hpd80, median, hypotheses, evidence, models, ...}."""
    where = "origin.json/age_posterior"
    if not isinstance(ap_, dict):
        err(f"{where}: must be an object")
        return
    need_keys(ap_, ["hours_grid", "prob", "hpd80", "median"], where)
    g, p = ap_.get("hours_grid"), ap_.get("prob")
    if not (isinstance(g, list) and isinstance(p, list)):
        return
    if len(g) != len(p) or not g:
        err(f"{where}: hours_grid ({len(g)}) and prob ({len(p)}) must be the same non-zero length")
        return
    if len(g) > 200:
        err(f"{where}: {len(g)} grid points — the posterior is a summary, not a raw sample dump")
    if any(b <= a for a, b in zip(g, g[1:])):
        err(f"{where}/hours_grid: must be strictly ascending")
    if any(x < 0 for x in g):
        err(f"{where}/hours_grid: ages cannot be negative")
    if any((not isinstance(x, (int, float))) or x < 0 for x in p):
        err(f"{where}/prob: every value must be a non-negative number")
    elif abs(sum(p) - 1.0) > 1e-3:
        err(f"{where}/prob: must sum to 1 (got {sum(p):.5f}) — a probability, not a density")
    h = ap_.get("hpd80")
    if not (isinstance(h, list) and len(h) == 2 and h[0] <= h[1]):
        err(f"{where}/hpd80: must be [low, high]")
        return
    half = (g[1] - g[0]) / 2 if len(g) > 1 else 0.5
    if h[0] < g[0] - half - 1e-6 or h[1] > g[-1] + half + 1e-6:
        err(f"{where}/hpd80: {h} lies outside the grid {g[0]}..{g[-1]} h")
    m = ap_.get("median")
    if isinstance(m, (int, float)) and not (g[0] - half <= m <= g[-1] + half):
        err(f"{where}/median: {m} h lies outside the grid")
    ah = o.get("age_hours")
    if ah is not None and isinstance(ah, list) and len(ah) == 2 and \
            (abs(ah[0] - h[0]) > 0.051 or abs(ah[1] - h[1]) > 0.051):
        err(f"origin.json/age_hours {ah} disagrees with age_posterior.hpd80 {h} — one number, "
            f"shown twice, must not say two things")
    tw = o.get("time_window")
    if o.get("time_window_method") == "age" and isinstance(tw, list) and len(tw) == 2:
        try:
            t0s = datetime.fromisoformat(tw[0].replace("Z", "+00:00"))
            t1s = datetime.fromisoformat(tw[1].replace("Z", "+00:00"))
            span_h = (t1s - t0s).total_seconds() / 3600.0
            if abs(span_h - (h[1] - h[0])) > 0.26 and span_h > 0.26:
                err(f"origin.json/time_window spans {span_h:.2f} h but the age HPD it claims to "
                    f"come from spans {h[1] - h[0]:.2f} h")
        except Exception:                          # parse errors are reported elsewhere
            pass


def check_model_mix(mm):
    where = "origin.json/model_mix"
    if not isinstance(mm, dict) or not isinstance(mm.get("models"), list) or not mm["models"]:
        err(f"{where}: must be an object with a non-empty models list")
        return
    tot = 0.0
    for i, m in enumerate(mm["models"]):
        need_keys(m, ["name", "weight", "points"], f"{where}/models[{i}]")
        w = m.get("weight")
        if not isinstance(w, (int, float)) or w < 0:
            err(f"{where}/models[{i}].weight: must be a non-negative number, got {w!r}")
            continue
        tot += w
        sf = m.get("stranded_fraction")
        if sf is not None and not (isinstance(sf, (int, float)) and 0 <= sf <= 1):
            err(f"{where}/models[{i}].stranded_fraction: must be a 0-1 fraction, got {sf!r}")
    if abs(tot - 1.0) > 1e-6:
        err(f"{where}: model weights sum to {tot}, not 1")


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

        # weight_live / components_available / components_total (D37) — a renormalised
        # score says nothing about how much evidence stands behind it on its own. WARN,
        # not ERR: bundles scored before 14 Sept predate these fields and re-scoring them
        # is not this validator's job.
        if isinstance(comps, dict):
            for key in ("weight_live", "components_available", "components_total"):
                if key not in sus:
                    warn(f"{w}: missing '{key}' — re-score with current score.py so the "
                         "card can show how much evidence backs this score (D37)")
            if "components_available" in sus and "components_total" in sus:
                n_null = sum(1 for v in comps.values() if v is None)
                expect_available = len(comps) - n_null
                if sus["components_available"] != expect_available:
                    err(f"{w}: components_available={sus['components_available']} does not "
                        f"match {expect_available} non-null entries in components")
                if sus["components_total"] != len(comps):
                    err(f"{w}: components_total={sus['components_total']} does not match "
                        f"{len(comps)} entries in components")

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
            # A constant ZERO is exempt, and deliberately (14 Sept). It separates nobody
            # either, but it cannot inflate anything: it contributes nothing to the numerator
            # while keeping its weight in the denominator, so it holds every score DOWN by the
            # same factor. It is also a real measurement — Farallones' slowdown 0.0 says no
            # vessel slowed, which is evidence, not a missing value. Gating it to null would
            # RAISE every score on the case, which is the direction no automated advice should
            # ever push. Non-zero constants stay a warning: those are the inflating kind.
            if len(set(vals)) == 1 and vals[0] != 0:
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
    # No exclusions is a demo-requirement miss — EXCEPT where nothing was searched. On a case
    # with no AIS archive the funnel is all zeros and there is no vessel to exonerate; demanding
    # an exclusion there would be asking for a name we have no data behind (Mumbai, D20).
    searched = (s.get("funnel") or {}).get("in_region")
    if not s["excluded"] and searched:
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
    if not need_keys(v, ["official_finding", "udgam_result", "assessment"], "verification.json"):
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
    nr = v["udgam_result"]
    if need_keys(nr, ["origin_summary", "top_suspects", "abstained"], "verification.json/udgam_result"):
        if not isinstance(nr["top_suspects"], list):
            err("verification.json/udgam_result/top_suspects: must be a list (may be empty)")
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
    # trace and attribute layers leave the scene by construction — check them against
    # physical reach, not against a box padded only for the slick
    trace_box = box.reach(TRACE_REACH_KM, f"{TRACE_REACH_KM} km of the scene") if box else None
    vessel_box = box.reach(VESSEL_REACH_KM, f"{VESSEL_REACH_KM} km of the scene") if box else None

    if meta:
        check_known_origin(meta, box)
        check_infrastructure_candidates(meta, trace_box)

    if "detect" in acts:
        check_detections(d, box)
    if "trace" in acts:
        backward = check_particles(d, trace_box, meta)
        check_particles_forward(d, trace_box, meta, backward)
        check_forward_impact(d, trace_box, meta, backward)
        origin = check_origin(d, trace_box)
    else:
        origin = None
    if "attribute" in acts:
        known = check_vessels(d, vessel_box)
        check_suspects(d, known, origin, vessel_box, meta.get("ais_source") if meta else None)
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
