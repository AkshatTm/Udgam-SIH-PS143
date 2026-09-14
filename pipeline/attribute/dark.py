#!/usr/bin/env python3
"""
Stage 3 — the radar-versus-transponder cross-check. Fills `suspects.json/dark_vessels[]`.

A radar contact is not a dark vessel (Master §6.3, D34). Darkness is the ABSENCE of an AIS match,
and an absence only means something if AIS was actually searched at the contact's place and time.
So this module needs two inputs and refuses to claim anything without both:

  * radar contacts — `detections.geojson/ship_detections` (our ship detector), and optionally an
    external contact list (`--sar-contacts`, GFW's Sentinel-1 vessel detections) that is labelled
    as external on every card it produces;
  * an AIS extract covering the scene footprint at the scene's acquisition time
    (`--scene-parquet`, written by ingest.py / ingest_gfw.py with --bbox around bounds.json).

THE MATCH RULE — stated, not tuned (D42)
    For every AIS vessel, at the acquisition time t0:
      * if its track can be interpolated to t0 within the regime's ceiling (tracks.REGIME), the
        vessel is PLACED there. Placed within MATCH_KM of the contact -> the contact is matched.
      * otherwise, a SPACE-TIME PRISM: take its last fix before t0 and first fix after (within
        REACH_WINDOW_MIN). The contact is matched if it lies inside the ellipse the vessel could
        have covered between those fixes, at up to PRISM_HEADROOM x the straight-line pace it
        actually kept (floored at PRISM_MIN_KNOTS, capped at REACH_KNOTS). One-sided: a circle.
    On hourly AIS the prism is the only branch that fires — hourly cell centres cannot place a
    vessel. The first version used a flat 25 kn circle around any fix within 90 minutes; in a
    30 km box that contains everything, so every contact "matched" and the check said nothing.
    The prism uses each vessel's own measured pace instead. It still errs toward matched: a real
    dark vessel may be missed on hourly AIS, a broadcasting ship is not called dark.

RELEVANCE — so every moored ship and platform in the scene is not reported as a ghost ship
    An unmatched contact is listed only if it touches the reconstructed origin (non-zero grid
    probability) or lies within max(r90, RELEVANCE_MIN_KM) of an oil detection. The rest are
    counted in the summary and not drawn as findings.

WHAT A LISTING DOES NOT SAY
    A single Sentinel-1 pass is not persistence-checked: an unmatched return can be a fixed
    structure, a buoy, or a vessel whose transponder is outside the AIS archive's receiver
    coverage. Every card says so.

Stdlib only. No module outside pipeline/attribute is imported.
"""
import json
import math
from datetime import datetime, timedelta, timezone

import geo
from tracks import regime

MATCH_KM = 1.0             # placed AIS vessel this close to a contact explains it
REACH_KNOTS = 25.0         # faster than almost any merchant ship; the prism's ceiling
REACH_WINDOW_MIN = 90      # fixes this far either side of t0 bound the prism
PRISM_HEADROOM = 1.5       # a vessel may go 50% faster than the straight-line pace it kept
PRISM_MIN_KNOTS = 6.0      # floor: a slow or stopped vessel can still get under way
RELEVANCE_MIN_KM = 5.0     # floor on "near the slick"
MAX_LISTED = 5
KM_PER_KNOT_HOUR = 1.852


def parse_ts(s):
    dt = datetime.fromisoformat(str(s).replace("Z", "+00:00"))
    if dt.tzinfo is None:
        raise ValueError(f"'{s}' is timezone-naive")
    return dt.astimezone(timezone.utc)


# ----------------------------------------------------------------------------- contacts

def pixel_size_m(bounds):
    """Mean ground size of one sar.png pixel, from bounds.json. Coarse, and said to be."""
    mid = (bounds["south"] + bounds["north"]) / 2.0
    w_km = geo.haversine_km(bounds["west"], mid, bounds["east"], mid)
    h_km = geo.haversine_km(bounds["west"], bounds["south"], bounds["west"], bounds["north"])
    return 1000.0 * math.sqrt((w_km / bounds["width_px"]) * (h_km / bounds["height_px"]))


def contacts_from_detections(detections_doc, bounds):
    """Our own ship detector's contacts. None when the detector was not run (key absent)."""
    if "ship_detections" not in detections_doc:
        return None
    px_m = pixel_size_m(bounds) if bounds else None
    out = []
    for c in detections_doc["ship_detections"]:
        length = None
        if px_m and c.get("px_area"):
            length = round(math.sqrt(float(c["px_area"])) * px_m)
        out.append({"lon": float(c["lon"]), "lat": float(c["lat"]),
                    "est_length_m": length, "external": None})
    return out


def contacts_from_external(doc, label):
    """An external contact list, e.g. GFW SAR vessel detections written by ingest_gfw_sar.py."""
    out = []
    for c in doc.get("contacts", []):
        length = c.get("length_m")
        out.append({"lon": float(c["lon"]), "lat": float(c["lat"]),
                    "est_length_m": round(float(length)) if length else None,
                    "external": label})
    return out


# ------------------------------------------------------------------------------ matching

def implied_knots(t, i, j):
    """Straight-line speed between fixes i and j — a LOWER bound on the vessel's real speed."""
    hours = (t.ts[j] - t.ts[i]).total_seconds() / 3600.0
    if hours <= 0:
        return None
    return geo.haversine_km(t.lon[i], t.lat[i], t.lon[j], t.lat[j]) / KM_PER_KNOT_HOUR / hours


def speed_bound_knots(t, i, j):
    """The speed this vessel is allowed in the prism: its own measured pace with headroom,
    floored so a drifting or manoeuvring vessel is not pinned in place, capped at REACH_KNOTS."""
    v = implied_knots(t, i, j)
    if v is None:
        return REACH_KNOTS
    return min(REACH_KNOTS, max(PRISM_MIN_KNOTS, v * PRISM_HEADROOM))


def could_have_been_here(contact, t, t0):
    """Space-time prism test. None when the track has no fix within REACH_WINDOW_MIN of t0."""
    window = REACH_WINDOW_MIN * 60
    before = [i for i, ts in enumerate(t.ts) if ts <= t0 and (t0 - ts).total_seconds() <= window]
    after = [i for i, ts in enumerate(t.ts) if ts >= t0 and (ts - t0).total_seconds() <= window]
    a = before[-1] if before else None
    b = after[0] if after else None
    if a is None and b is None:
        return None
    c = (contact["lon"], contact["lat"])

    if a is not None and b is not None and a != b:
        # Both sides: the vessel went from fix a to fix b, so the contact must lie inside the
        # ellipse d(a,c) + d(c,b) <= v * (tb - ta), v bounded by the pace it actually kept.
        v = speed_bound_knots(t, a, b)
        hours = (t.ts[b] - t.ts[a]).total_seconds() / 3600.0
        budget = v * KM_PER_KNOT_HOUR * hours + 2 * MATCH_KM
        path = (geo.haversine_km(t.lon[a], t.lat[a], *c) +
                geo.haversine_km(*c, t.lon[b], t.lat[b]))
        return path <= budget

    # One side only: a circle around that fix, at the pace of the nearest pair on that side.
    k = a if a is not None else b
    nb = (k - 1) if a is not None else (k + 1)
    v = (speed_bound_knots(t, min(k, nb), max(k, nb)) if 0 <= nb < len(t.ts) else REACH_KNOTS)
    hours = abs((t.ts[k] - t0).total_seconds()) / 3600.0
    return geo.haversine_km(t.lon[k], t.lat[k], *c) <= v * KM_PER_KNOT_HOUR * hours + MATCH_KM


def match_contact(contact, tracks, t0, ais_source):
    """(matched, how) for one contact against every AIS track. `how` is a short string."""
    ceiling = regime(ais_source)["max_interp_gap_min"]
    if ais_source == "gfw_hourly":
        ceiling = 0          # hourly cell centres cannot PLACE a vessel; the prism only
    for t in tracks:
        if ceiling:
            pos = t.position_at(t0, ceiling)
            if pos is not None:
                d = geo.haversine_km(pos[0], pos[1], contact["lon"], contact["lat"])
                if d <= MATCH_KM:
                    return True, f"AIS vessel placed {d:.2f} km away at acquisition time"
                continue     # placed elsewhere: this vessel is accounted for
        if could_have_been_here(contact, t, t0):
            return True, "an AIS vessel's space-time prism at acquisition time contains the contact"
    return False, None


# ----------------------------------------------------------------------------- relevance

def oil_features(detections_doc):
    out = []
    for f in detections_doc.get("features", []):
        p = f.get("properties") or {}
        if p.get("classification") != "oil":
            continue
        g = f.get("geometry") or {}
        if g.get("type") == "Polygon":
            ring = g["coordinates"][0]
        elif g.get("type") == "MultiPolygon":
            ring = [pt for poly in g["coordinates"] for pt in poly[0]]
        else:
            continue
        if len(ring) < 3:
            continue
        c = p.get("centroid") or [sum(q[0] for q in ring) / len(ring),
                                  sum(q[1] for q in ring) / len(ring)]
        out.append({"ring": ring, "centroid": c, "axis_deg": long_axis_deg(ring, c)})
    return out


def long_axis_deg(ring, centroid):
    """Bearing (0-180) of the polygon's principal axis, from its perimeter points."""
    xs, ys = zip(*(geo.local_xy_km(q[0], q[1], centroid[0], centroid[1]) for q in ring))
    mx, my = sum(xs) / len(xs), sum(ys) / len(ys)
    sxx = sum((x - mx) ** 2 for x in xs)
    syy = sum((y - my) ** 2 for y in ys)
    sxy = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    theta = 0.5 * math.atan2(2 * sxy, sxx - syy)        # radians from +x (east)
    return (90.0 - math.degrees(theta)) % 180.0          # clockwise from north, undirected


def nearest_oil(contact, oils):
    best = None
    for o in oils:
        d = min(geo.haversine_km(contact["lon"], contact["lat"], q[0], q[1]) for q in o["ring"])
        if best is None or d < best[0]:
            best = (d, o)
    return best


# ---------------------------------------------------------------------------------- main

def cross_check(contacts, tracks, t0, ais_source, grid, detections_doc, have_scene_ais):
    """Returns (dark_vessels list for suspects.json, summary dict)."""
    summary = {"contacts": 0 if contacts is None else len(contacts), "matched": 0,
               "unmatched": 0, "relevant": 0, "listed": 0,
               "ais_searched_at_scene_time": bool(have_scene_ais)}
    if not contacts:
        return [], summary
    if not have_scene_ais:
        # D34: darkness needs an AIS search at the contact's place and time. Without it the
        # contact's darkness is null, and null is not listed as a dark vessel.
        return [], summary

    oils = oil_features(detections_doc)
    radius = max(grid.radius_90_km, RELEVANCE_MIN_KM)
    found = []
    for c in contacts:
        matched, _how = match_contact(c, tracks, t0, ais_source)
        if matched:
            summary["matched"] += 1
            continue
        summary["unmatched"] += 1

        p_grid = grid.sample(c["lon"], c["lat"])
        near = nearest_oil(c, oils)
        d_oil = near[0] if near else None
        if p_grid <= 0 and (d_oil is None or d_oil > radius):
            continue
        summary["relevant"] += 1

        score = max(p_grid, (1.0 - d_oil / radius) if d_oil is not None else 0.0)
        score = round(min(1.0, max(0.0, score)), 3)

        dev = None
        if near:
            o = near[1]
            # Angle between the line contact->slick and the slick's long axis, folded to 0-90:
            # 0 means the contact sits on the slick's axis line, as a ship at its head would.
            b = geo.bearing_deg(c["lon"], c["lat"], o["centroid"][0], o["centroid"][1])
            diff = geo.angular_difference_deg(b % 180.0, o["axis_deg"])
            dev = round(min(diff, 180.0 - diff), 1)

        reasons = []
        if c["external"]:
            reasons.append(f"radar contact from {c['external']} — not produced by UDGAM's "
                           f"ship detector")
        if ais_source == "gfw_hourly":
            reasons.append("no vessel in the hourly AIS record could have reached this position "
                           "at acquisition time — hourly AIS is weaker evidence than dense AIS")
        else:
            reasons.append(f"radar return with no AIS broadcast within {MATCH_KM:g} km at "
                           f"acquisition time")
        if p_grid > 0:
            reasons.append(f"sits inside the reconstructed origin (grid probability {p_grid:.2f})")
        elif d_oil is not None:
            reasons.append(f"{d_oil:.1f} km from the edge of an oil detection")
        reasons.append("single satellite pass: not persistence-checked, so it may be a fixed "
                       "structure or a transponder outside the archive's receiver coverage")

        entry = {
            "source_type": "dark_vessel",
            "mmsi": None,
            "name": ("Unidentified radar contact" if not c["external"] else
                     f"Unidentified radar contact ({c['external']}, not UDGAM's detector)"),
            "lon": round(c["lon"], 5),
            "lat": round(c["lat"], 5),
            "est_length_m": c["est_length_m"],
            "score": score,
            "angular_deviation_deg": dev,
            "reasons": reasons,
        }
        found.append(entry)

    found.sort(key=lambda e: e["score"], reverse=True)
    listed = found[:MAX_LISTED]
    summary["listed"] = len(listed)
    return listed, summary


def scene_time(meta):
    return parse_ts(meta["detection_time"])


def scene_window(t0, minutes):
    return t0 - timedelta(minutes=minutes), t0 + timedelta(minutes=minutes)


def load_external(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)
