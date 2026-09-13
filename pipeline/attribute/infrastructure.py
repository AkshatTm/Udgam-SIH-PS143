#!/usr/bin/env python3
"""
infrastructure.py — Stage 3 Phase 4: fixed-source association.

    from infrastructure import find_infrastructure

Two of our cases have a source that is not a vessel at all: the San Pedro Bay Pipeline at
Huntington Beach, and structure 121229 at Mumbai. Without this module the system's answer on
both is "no vessel is responsible", which reads as a failure. With it the answer is "the source
is fixed infrastructure at this position, and all transiting vessels are excluded" — which is
correct, and which is what the NTSB concluded at Huntington.

**The failure mode this exists to prevent is naming a ship for a pipeline leak.** A system that
can only consider vessels will always return a vessel, because a vessel is the only thing it can
see. That is a false accusation, and it is the worst thing this stage can do.

WHAT IS MEASURED HERE AND WHAT IS DECLARED
------------------------------------------
Two different kinds of input meet in this file and they must not be confused:

* **The termini are measured.** They come from Soum's slick polygon and Anushka's origin grid —
  our own pipeline, on this scene. Nothing external.
* **The candidate list is declared.** Where a pipeline or platform actually sits is not something
  this pipeline discovers; it is looked up from the investigation and written into `meta.json` as
  case input (06_JAIVEER_AIS section 4.1 permits exactly this, and requires the declaration).
  Every candidate therefore carries a `source` string naming where the coordinate came from, and
  a candidate without one is refused rather than silently scored.

So the honest claim is never "we found a pipeline". It is "the reconstructed origin lands on a
position that the investigation records as a pipeline, and no vessel explains it better".

THE SCORE
---------
Following Cerulean's infrastructure module: find points along the slick perimeter far enough
from its centre to be a plausible terminus, then apply a distance decay so candidates nearer a
terminus score higher. We add the origin grid, which Cerulean does not have, because a fixed
point sitting in high origin probability is the stronger half of the evidence:

    score = W_INFRA_ORIGIN * origin_grid_probability_at_candidate
          + W_INFRA_TERMINUS * exp(-km_to_nearest_terminus / TERMINUS_DECAY_KM)

Both terms are 0..1 and the weights sum to 1, so the score is 0..1 and comparable with a vessel
score — deliberately, because section 4.3's decision rule compares them.

WHAT THIS MODULE WILL NOT DO
----------------------------
It will not emit a finding for an unnamed fixed point. A dark vessel can honestly be reported as
"Unidentified radar contact" because the radar return is itself the evidence. There is no
equivalent here: a bright spot in the origin grid with no declared candidate is just water that
the drift model liked, and calling it infrastructure would be inventing a structure. When no
candidate is declared the module reports the terminus geometry as diagnostics and emits nothing.
"""
import math

import geo

# --------------------------------------------------------------------------------- weights
# Named constants, same discipline as score.py's component weights.
W_INFRA_ORIGIN   = 0.60   # the origin cloud is physics; it is the stronger half
W_INFRA_TERMINUS = 0.40   # slick geometry — where the visible oil actually ends

# --------------------------------------------------------------------------------- shape
# A perimeter vertex counts as a plausible terminus when it sits at least this fraction of the
# polygon's maximum radius from its centre. Cerulean's phrasing is "far enough from the centre
# to be a plausible terminus"; 0.75 keeps the ends of an elongated slick and discards the
# flanks. On a near-circular blob it keeps most of the rim, which is the correct behaviour —
# a blob genuinely does not tell you which end it came from.
TERMINUS_RIM_FRACTION = 0.75

# Decay length for distance from a terminus. 2 km is the scale of the Huntington origin cloud
# (r90 = 2.46 km), so a candidate one cloud-radius from the visible oil keeps about a third of
# the terminus term rather than falling off a cliff.
TERMINUS_DECAY_KM = 2.0

# Mirrors ABSTAIN_SCORE_FLOOR in score.py. Below this we do not name a structure any more than
# we would name a ship.
INFRA_SCORE_FLOOR = 0.25


def _ring_points(geometry):
    """Exterior ring of a Polygon or MultiPolygon, as [lon, lat] pairs.

    GeoJSON is lon-lat (docs/TRAPS.md). Nothing in this file ever swaps them.
    """
    kind = geometry.get("type")
    if kind == "Polygon":
        return list(geometry["coordinates"][0])
    if kind == "MultiPolygon":
        pts = []
        for poly in geometry["coordinates"]:
            pts.extend(poly[0])
        return pts
    return []


def slick_termini(detections_doc):
    """Plausible source termini along the perimeter of every oil-classified detection.

    Returns (termini, diagnostics). `termini` is a list of [lon, lat]. Look-alikes are skipped:
    scoring a structure against a wind shadow would be the infrastructure version of attributing
    a slick to the wrong ship.
    """
    termini, diag = [], []
    for feature in detections_doc.get("features", []):
        props = feature.get("properties") or {}
        if props.get("classification") != "oil":
            continue
        ring = _ring_points(feature.get("geometry") or {})
        if len(ring) < 4:
            continue

        centroid = props.get("centroid")
        if not centroid:
            centroid = [sum(p[0] for p in ring) / len(ring),
                        sum(p[1] for p in ring) / len(ring)]
        clon, clat = centroid[0], centroid[1]

        radii = [geo.haversine_km(clon, clat, p[0], p[1]) for p in ring]
        max_r = max(radii)
        if max_r <= 0:
            continue
        keep = [p for p, r in zip(ring, radii) if r >= TERMINUS_RIM_FRACTION * max_r]
        termini.extend([p[0], p[1]] for p in keep)
        diag.append({
            "detection_id": props.get("id"),
            "area_km2": props.get("area_km2"),
            "elongation": props.get("elongation"),
            "centroid": [clon, clat],
            "max_radius_km": round(max_r, 3),
            "perimeter_points": len(ring),
            "terminus_points": len(keep),
        })
    return termini, diag


def load_candidates(meta):
    """Declared fixed-source candidates from `meta.json`, validated.

    Expected shape, and every field is required:

        "infrastructure_candidates": [
          {"name": "San Pedro Bay Pipeline", "lon": -118.11, "lat": 33.60,
           "kind": "pipeline", "source": "NTSB report DCA22FM001"}
        ]

    `source` is not decoration. Section 4.1 allows hardcoding these coordinates precisely
    because they are declared case input rather than a discovery, and the declaration is what
    keeps that distinction visible to anyone reading the bundle. A candidate missing any field
    raises rather than being scored — a structure named on screen with no provenance behind it
    is the same class of problem as a vessel name that is not in the AIS file.
    """
    raw = meta.get("infrastructure_candidates") or []
    out = []
    for i, c in enumerate(raw):
        missing = [k for k in ("name", "lon", "lat", "kind", "source") if c.get(k) in (None, "")]
        if missing:
            raise SystemExit(
                f"meta.json/infrastructure_candidates[{i}] is missing {', '.join(missing)}.\n"
                "  Every candidate needs name, lon, lat, kind and source. `source` records where\n"
                "  the coordinate came from — these positions are declared case input, not\n"
                "  something this pipeline discovered, and the bundle has to say so.")
        if not (-180 <= c["lon"] <= 180 and -90 <= c["lat"] <= 90):
            raise SystemExit(
                f"meta.json/infrastructure_candidates[{i}] ({c['name']}) has lon={c['lon']} "
                f"lat={c['lat']}.\n  Coordinates are [longitude, latitude], WGS84 — that pair "
                "looks swapped or out of range.")
        out.append(dict(c))
    return out


def find_infrastructure(meta, detections_doc, grid, best_vessel_score):
    """Score every declared fixed candidate. Returns (findings, diagnostics).

    `best_vessel_score` is the top vessel score on this case, or None when no vessel was
    scorable. It never changes a candidate's score — it only shapes the reasons, so that the
    card says whether a vessel was a competing explanation or not. Section 4.3 is explicit
    that when both a structure and a vessel are plausible we report both; deciding between
    them on this evidence is not something the data supports, and pretending otherwise would
    be the fudge that rule exists to forbid.
    """
    candidates = load_candidates(meta)
    termini, diag = slick_termini(detections_doc)
    if not candidates:
        return [], {"termini": len(termini), "detections": diag, "candidates": 0}

    findings = []
    for c in candidates:
        lon, lat = float(c["lon"]), float(c["lat"])
        p_origin = grid.sample(lon, lat) if grid.contains(lon, lat) else 0.0

        if termini:
            km = min(geo.haversine_km(lon, lat, t[0], t[1]) for t in termini)
            decay = math.exp(-km / TERMINUS_DECAY_KM)
        else:
            km, decay = None, 0.0

        score = W_INFRA_ORIGIN * p_origin + W_INFRA_TERMINUS * decay

        reasons = []
        if p_origin >= 0.5:
            reasons.append(f"sits in the high-probability region of the reconstructed origin "
                           f"(grid probability {p_origin:.2f})")
        elif p_origin > 0:
            reasons.append(f"sits inside the reconstructed origin cloud but away from its peak "
                           f"(grid probability {p_origin:.2f})")
        else:
            reasons.append("lies outside the reconstructed origin cloud entirely")

        if km is not None:
            reasons.append(f"{km:.1f} km from the nearest plausible terminus of the visible "
                           f"slick")
        else:
            reasons.append("no oil-classified detection on this scene, so slick geometry "
                           "contributes nothing")

        if best_vessel_score is None:
            reasons.append("no vessel was scorable on this case, so no vessel competes with "
                           "this explanation")
        elif best_vessel_score < INFRA_SCORE_FLOOR:
            reasons.append(f"no vessel scored above the {INFRA_SCORE_FLOOR} floor "
                           f"(best {best_vessel_score:.2f})")
        else:
            reasons.append(f"a vessel explanation also remains plausible (best vessel "
                           f"{best_vessel_score:.2f}); both are reported rather than one "
                           f"being chosen on this evidence")

        reasons.append(f"position is declared case input, not a detection — source: "
                       f"{c['source']}")

        findings.append({
            "source_type": "infrastructure",
            "name": c["name"],
            "kind": c["kind"],
            "lon": round(lon, 5),
            "lat": round(lat, 5),
            "score": round(score, 3),
            "origin_probability": round(p_origin, 3),
            "terminus_km": None if km is None else round(km, 3),
            "declared_source": c["source"],
            "reasons": reasons,
        })

    findings.sort(key=lambda f: f["score"], reverse=True)
    kept = [f for f in findings if f["score"] >= INFRA_SCORE_FLOOR]
    return kept, {
        "termini": len(termini),
        "detections": diag,
        "candidates": len(candidates),
        "below_floor": [f["name"] for f in findings if f["score"] < INFRA_SCORE_FLOOR],
    }
