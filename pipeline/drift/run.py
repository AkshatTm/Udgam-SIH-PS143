#!/usr/bin/env python3
"""
Stage 2 — backward drift. Owner: Anushka.

    python pipeline/drift/run.py --case case-000 --real          # PHASE 3, the real thing
    python pipeline/drift/run.py --case case-000 --fake          # analytic ocean, no GEE

PHASE 3. Reads `detections.geojson`, seeds particles off the highest-confidence oil feature,
rewinds them 24 h through the RK2 integrator (`step.py`), and writes the two files the rest of
the project consumes:

    out/particles.json   the animation  -- ONE control run, 3000 particles x 97 frames
    out/origin.json      the answer     -- 50 perturbed runs pooled into a probability grid

WHY TWO DIFFERENT THINGS
    The slider needs coherent trajectories a human can follow, so `particles.json` is the
    single unperturbed run. The origin cloud needs uncertainty, so `origin.json` comes from
    the 50-member ensemble in `ensemble.py`. Showing the ensemble as the animation would look
    like fog; showing the control run as the answer would claim a precision we do not have.

PHASE HISTORY
    Phase 1  real RK2 over an analytic ocean (`--fake`), four known-answer tests
    Phase 2  the analytic ocean swapped for HYCOM + ERA5 under the same two methods
    Phase 3  --real, the 50-run ensemble, the true histogram grid, the convergence window
"""
import argparse
import json
import math
import random
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np

import coastline
import ensemble as ens
from fields import load_case_field, make_fake
import step
from step import (assert_displacement_plausible, assert_field_covers,
                  assert_inside_field_box, displacement_km, edge_distance_km,
                  integrate, integrate_stranding)

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
OUT = HERE / "out"

KM_PER_DEG = 111.32
ABSTAIN_RADIUS_KM = ens.ABSTAIN_RADIUS_KM


def iso(dt):
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_ts(s):
    dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        raise SystemExit(f"'{s}' is timezone-naive — every timestamp needs the trailing Z")
    return dt


def r5(x):
    return round(float(x), 5)


def pick_slick(dets):
    """Highest-confidence 'oil' feature. Zero oil features is the no-spill case: Stage 2 has
    nothing to rewind, and that is a designed state, not a crash."""
    oil = [f for f in dets.get("features", [])
           if (f.get("properties") or {}).get("classification") == "oil"]
    if not oil:
        return None
    return max(oil, key=lambda f: f["properties"].get("confidence", 0.0))


def slick_rings(feat):
    """Every outer ring of a slick feature, as a list of vertex arrays.

    Polygon -> one ring. MultiPolygon -> one per part. A merged slick is a MultiPolygon, and
    code that reads `coordinates[0]` on one silently gets ONLY ITS FIRST PART -- which on
    Jacksonville would seed from 15 km of a 34 km ribbon and never say so.
    """
    g = feat.get("geometry") or {}
    c = g.get("coordinates")
    if not c:
        return []
    if g.get("type") == "Polygon":
        return [np.asarray(c[0], dtype=np.float64)]
    if g.get("type") == "MultiPolygon":
        return [np.asarray(part[0], dtype=np.float64) for part in c if part]
    return []


def ribbon_metrics(feats):
    """Is this set of oil features ONE broken ribbon, or separate slicks? Four measurements.

    Projects every vertex of every feature onto the principal axis of the whole set, then asks:

      aspect            combined along-axis extent / across-axis extent. A ribbon is long and
                        thin; two unrelated blobs are not.
      coverage          what fraction of the combined axis actually has oil on it. A broken
                        ribbon is nearly all covered; separated slicks leave the middle empty.
      max_gap_frac      the largest empty run along the axis, over the combined length.
      max_perp_frac     the furthest a part's centre sits off the shared axis, over the
                        combined width. Parts of one ribbon sit ON the line.

    THE THRESHOLDS COME FROM THE LIBRARY, NOT FROM TASTE. Measured 13 Sept:

      case-jacksonville-2024   aspect 17.9   coverage 99%   gap 0.005   perp 0.10   -> one ribbon
      case-mumbai-2023         aspect  4.5   coverage 85%   gap 0.15    perp 0.31   -> borderline
      case-gulf-alaska-2023    aspect  2.5   coverage 49%   gap 0.52    perp 0.31   -> separate

    Jacksonville and Gulf of Alaska fall on opposite sides of all four, so the gates are set
    between them and Mumbai lands outside -- deliberately, because at 85% coverage with a 2.5 km
    gap and 1.2 km of perpendicular scatter it is genuinely not clear, and a merge that changes
    the seed should not happen on a guess. Every number is printed either way.
    """
    pts = [r for f in feats for r in slick_rings(f)]
    if not pts:
        return None
    allpts = np.vstack(pts)
    lat0 = float(allpts[:, 1].mean())
    coslat = max(math.cos(math.radians(lat0)), 1e-9)
    xy = np.column_stack([allpts[:, 0] * coslat * KM_PER_DEG, allpts[:, 1] * KM_PER_DEG])
    mu = xy.mean(axis=0)
    centred = xy - mu
    _, _, vt = np.linalg.svd(centred, full_matrices=False)
    along = centred @ vt[0]
    across = centred @ vt[1]
    length = float(along.max() - along.min())
    width = float(across.max() - across.min())

    segs = []
    for f in feats:
        rings = slick_rings(f)
        if not rings:
            continue
        q = np.vstack(rings)
        qq = np.column_stack([q[:, 0] * coslat * KM_PER_DEG, q[:, 1] * KM_PER_DEG]) - mu
        a = qq @ vt[0]
        b = qq @ vt[1]
        segs.append({"id": f["properties"].get("id"),
                     "lo": float(a.min()), "hi": float(a.max()),
                     "perp": float(b.mean())})
    segs.sort(key=lambda s: s["lo"])
    covered = sum(s["hi"] - s["lo"] for s in segs)
    gaps = [segs[i + 1]["lo"] - segs[i]["hi"] for i in range(len(segs) - 1)]
    return {
        "n_features": len(segs),
        "length_km": round(length, 3),
        "width_km": round(width, 3),
        "aspect": round(length / width, 2) if width > 0 else None,
        "coverage": round(covered / length, 4) if length > 0 else None,
        "max_gap_km": round(max(gaps), 3) if gaps else 0.0,
        "max_gap_frac": round(max(gaps) / length, 4) if gaps and length > 0 else 0.0,
        "max_perp_km": round(max(abs(s["perp"]) for s in segs), 3),
        "max_perp_frac": (round(max(abs(s["perp"]) for s in segs) / width, 4)
                          if width > 0 else None),
        "segments": segs,
    }


RIBBON_MIN_ASPECT = 6.0
RIBBON_MIN_COVERAGE = 0.75
RIBBON_MAX_GAP_FRAC = 0.10
RIBBON_MAX_PERP_FRAC = 0.20


def is_one_ribbon(m):
    """(verdict, reasons) against the four gates. Reasons are returned for BOTH outcomes."""
    if m is None:
        return False, ["no geometry to measure"]
    checks = [
        ("aspect", m["aspect"], RIBBON_MIN_ASPECT, "ge"),
        ("coverage", m["coverage"], RIBBON_MIN_COVERAGE, "ge"),
        ("max_gap_frac", m["max_gap_frac"], RIBBON_MAX_GAP_FRAC, "le"),
        ("max_perp_frac", m["max_perp_frac"], RIBBON_MAX_PERP_FRAC, "le"),
    ]
    reasons, ok = [], True
    for name, got, lim, sense in checks:
        if got is None:
            ok = False
            reasons.append(f"{name} could not be measured")
            continue
        passed = got >= lim if sense == "ge" else got <= lim
        ok &= passed
        reasons.append(f"{'PASS' if passed else 'FAIL'} {name} {got} "
                       f"{'>=' if sense == 'ge' else '<='} {lim}")
    return ok, reasons


def merged_discharge_class(feats):
    """One class for a merged slick, per Soum (13 Sept): take the defined one, never average.

    `discharge_class` is computed PER REGION from that region's own elongation, so the parts of
    one ribbon disagree -- Jacksonville's det-02 is 'chronic' while det-01 and det-03 are
    'unknown'. A merged object has no well-defined class, so:

      any part 'chronic'  -> 'chronic'. A 34 km ribbon broken into pieces IS a vessel track;
                             that is the physical reading, and it is also the conservative one,
                             because 'chronic' GATES the acute-only age estimators off rather
                             than letting them fire on a merged geometry.
      otherwise unanimous -> that value
      otherwise           -> 'unknown', and the fallback to shape_class says so out loud
    """
    vals = [f["properties"].get("discharge_class", "unknown") for f in feats]
    if "chronic" in vals:
        return "chronic", f"any part chronic ({vals}) -> chronic"
    uniq = set(vals)
    if len(uniq) == 1:
        return vals[0], f"all parts agree ({vals[0]})"
    return "unknown", f"parts disagree ({sorted(uniq)}) and none is chronic -> unknown"


def merge_oil_features(dets, mode="auto", verbose=True):
    """Pick the slick to seed from: one merged ribbon, or the single best feature.

    Soum's ruling (13 Sept) on Jacksonville: "one slick, genuine breaks -- treat it as one."
    The breaks are intrinsic, not our artefact; Cerulean's own polygon for the same slick is an
    18-part MultiPolygon, 31.2 km long, so an operational detector fragments the same ribbon
    eighteen ways. Seeding from the highest-confidence part alone would have seeded 15 km of a
    34 km ribbon.

    mode: 'auto' merges only when ribbon_metrics passes every gate; 'always' merges any case
    with more than one oil feature; 'never' keeps the old single-feature behaviour.

    Returns (feature, diag). The merged feature is a MultiPolygon whose `elongation` is
    deliberately set to None -- see the note in the body.
    """
    oil = [f for f in dets.get("features", [])
           if (f.get("properties") or {}).get("classification") == "oil"]
    if not oil:
        return None, {"decision": "no oil features"}
    best = max(oil, key=lambda f: f["properties"].get("confidence", 0.0))
    if len(oil) == 1 or mode == "never":
        return best, {"decision": "single feature" if len(oil) == 1 else "merge disabled",
                      "seeded_from": best["properties"].get("id"), "n_oil": len(oil)}

    m = ribbon_metrics(oil)
    verdict, reasons = is_one_ribbon(m)
    if mode == "always":
        verdict, reasons = True, reasons + ["--merge-oil always: gates overridden"]

    diag = {"n_oil": len(oil), "metrics": m, "gates": reasons}
    if not verdict:
        diag["decision"] = "NOT merged -- not one ribbon"
        diag["seeded_from"] = best["properties"].get("id")
        if verbose:
            print(f"[slick]  {len(oil)} oil features, NOT merged: they do not measure as one "
                  f"ribbon.")
            for r in reasons:
                print(f"         {r}")
            print(f"         seeding from {best['properties'].get('id')} alone "
                  f"(highest confidence). Pass --merge-oil always to override.")
        return best, diag

    order = sorted(oil, key=lambda f: -f["properties"].get("area_km2", 0.0))
    coords = [[r.tolist()] for f in oil for r in slick_rings(f)]
    area = float(sum(f["properties"].get("area_km2", 0.0) or 0.0 for f in oil))
    wsum = sum((f["properties"].get("area_km2", 0.0) or 0.0) for f in oil) or 1.0
    clon = sum(f["properties"]["centroid"][0] * (f["properties"].get("area_km2") or 0.0)
               for f in oil) / wsum
    clat = sum(f["properties"]["centroid"][1] * (f["properties"].get("area_km2") or 0.0)
               for f in oil) / wsum
    dc, dc_why = merged_discharge_class(oil)
    ids = [f["properties"].get("id") for f in order]

    merged = {
        "type": "Feature",
        "geometry": {"type": "MultiPolygon", "coordinates": coords},
        "properties": {
            "id": "+".join(ids),
            "classification": "oil",
            "area_km2": area,
            "centroid": [clon, clat],
            "discharge_class": dc,
            "shape_class": "linear" if (m["aspect"] or 0) >= 3.0 else "blob",
            "confidence": float(max(f["properties"].get("confidence", 0.0) for f in oil)),
            # ELONGATION IS DELIBERATELY None ON A MERGED SLICK, and that is load-bearing.
            # Soum (13 Sept): `elongation` is cv2.fitEllipse major/minor in PIXEL coordinates,
            # a shape descriptor feeding shape_class -- NOT a geometric aspect ratio, and not
            # invertible. On det-01 the fitted ellipse's minor axis spans the bow of the curve
            # rather than the filament width, so inverting it gives a ~2.2 km width against a
            # measured 258 m: an 8x error straight into the age estimate. There is also no
            # meaningful way to combine three per-region ellipse fits. None forces age.py down
            # its measured-from-polygon path, which is the only correct one.
            "elongation": None,
            "merged_from": ids,
            "merged_discharge_reason": dc_why,
        },
    }
    diag["decision"] = "MERGED into one ribbon"
    diag["seeded_from"] = merged["properties"]["id"]
    diag["merged_area_km2"] = round(area, 4)
    diag["discharge_reason"] = dc_why
    if verbose:
        print(f"[slick]  {len(oil)} oil features MERGED into one ribbon "
              f"({m['length_km']} km x {m['width_km']} km, aspect {m['aspect']}, "
              f"{100 * m['coverage']:.0f}% covered)")
        for r in reasons:
            print(f"         {r}")
        print(f"         parts {ids}   total area {area:.3f} km2")
        print(f"         discharge_class -> {dc!r}: {dc_why}")
        print(f"         NOTE Soum: our outline over-extends (Jacksonville IoU 0.483, "
              f"recall 0.825, precision 0.537), so a merged")
        print(f"         area is generous -- Cerulean's polygon for the same slick is "
              f"4.55 km2 against our {area:.2f} km2.")
    return merged, diag


def seed_geometry(props):
    """(geometry, reason) for this detection. `discharge_class` is the AUTHORITY (Phase 3.4).

    `shape_class` was always a proxy for the thing that actually matters: was the source moving?
    `discharge_class` says so directly, so it wins where it is known.

      chronic  -> the vessel was under way, so the origin is a LINE SEGMENT along the slick's
                  principal axis, and the backward cloud should come out elongated. The
                  reconstruction then implies a course and a speed, not just a place.
      acute    -> a release at a point, so seed from the centroid.
      unknown  -> fall back to shape_class, and SAY that is what happened. Stage 2 must not
                  present a fallback as a determination.
    """
    dc = props.get("discharge_class", "unknown")
    if dc == "chronic":
        return "line", "discharge_class=chronic - vessel under way, origin is a line segment"
    if dc == "acute":
        return "point", "discharge_class=acute - release at a point, seed from the centroid"
    sc = props.get("shape_class")
    if sc == "linear":
        return "line", f"discharge_class={dc!r}, FALLING BACK to shape_class=linear"
    return "point", f"discharge_class={dc!r}, FALLING BACK to shape_class={sc!r} (centroid)"


def seed_particles(feat, n, rng):
    """Seeding geometry comes from seed_geometry() — that field carries physics."""
    props = feat["properties"]
    clon, clat = float(props["centroid"][0]), float(props["centroid"][1])
    klat = 1.0 / max(math.cos(math.radians(clat)), 1e-6)
    jitter_deg = 0.3 / KM_PER_DEG          # +/- 300 m

    geom_kind, _ = seed_geometry(props)
    if geom_kind == "line":
        # Principal axis of the polygon ring, by PCA on its vertices.
        #
        # This REPLACED a most-distant-point-pair scan that stepped through the ring with
        # range(0, len(ring), 4) to keep the O(n^2) search cheap. That subsampling can miss the
        # true major axis: on a 5-vertex rectangle it compared exactly one pair -- the SHORT
        # edge -- and seeded the line ACROSS the slick instead of along it. Real polygons have
        # more vertices (case-000 has 41, Cerulean's Jacksonville ribbon 71) so it usually found
        # something close, but "usually" is not a property to rely on for the chronic seeding
        # that implies a vessel's course.
        #
        # PCA is exact, O(n), uses every vertex, and is cheaper than the scan it replaces. The
        # along-axis half-length is taken as the actual projected extent of the ring, so the
        # seeded segment matches the slick rather than a covariance-derived proxy.
        rings = slick_rings(feat)
        if not rings:
            raise SystemExit("slick has no usable ring to take a principal axis from")
        ring = np.vstack(rings)          # every part: a merged ribbon is a MultiPolygon
        coslat = math.cos(math.radians(clat))
        xy = np.column_stack([(ring[:, 0] - ring[:, 0].mean()) * coslat,
                              ring[:, 1] - ring[:, 1].mean()])
        evals, evecs = np.linalg.eigh(np.cov(xy, rowvar=False))
        major = evecs[:, int(np.argmax(evals))]          # unit vector in (deg*coslat, deg)
        proj = xy @ major
        half = float(proj.max() - proj.min()) / 2.0      # degrees along the axis
        ux, uy = float(major[0]), float(major[1])
        pts = []
        for _ in range(n):
            t = rng.uniform(-half, half)
            pts.append([clon + (t * ux) * klat + rng.gauss(0, jitter_deg) * klat,
                        clat + (t * uy) + rng.gauss(0, jitter_deg)])
        return pts

    # point: gaussian around the centroid, sigma ~ half the equivalent radius
    area = max(float(props.get("area_km2", 1.0)), 0.01)
    sigma = (math.sqrt(area / math.pi) / 2.0) / KM_PER_DEG
    return [[clon + rng.gauss(0, sigma) * klat, clat + rng.gauss(0, sigma)]
            for _ in range(n)]


def write_particles(path, t0, positions, dt_min):
    path.write_text(json.dumps({
        "t0": iso(t0), "direction": "backward", "timestep_minutes": dt_min,
        "n_steps": len(positions), "n_particles": len(positions[0]),
        "positions": positions}))


def wind_share_of_drift(field, history, times, wind_coeff=step.WIND_COEFF):
    """What fraction of the drift that actually moved this cloud came from the wind term?

    Phase 5.3 found this the hard way. `case-gulf-alaska-2023` rewinds to an origin in the WEST
    where the brief predicted EAST, and neither the integrator nor any guard was wrong: the
    Alaska Current is simply absent from that field (24 h mean 0.041 m/s, direction wandering
    with no preferred heading) and a persistent easterly 4-6.5 m/s wind supplies 81% of the
    drift vector. The brief's prediction came from a basin-scale current climatology, which does
    not describe a 9 km HYCOM cell on one afternoon.

    Nothing in the output said so. A reviewer comparing the origin against a current atlas would
    have called it a sign error, and the only way to tell them apart was to decompose the field
    by hand. So it is decomposed here, once, along the control trajectory -- sampling the path
    the cloud took rather than a fixed point, because on a weak-current case the two differ
    (Huntington's origin bearing moves 143 degrees between a t0 sample and a window mean).

    The number is a DIAGNOSTIC, not an error bar. It does not widen the cloud and does not
    reduce confidence in the answer: the ensemble already perturbs the coefficient over
    U(0.025, 0.035), and across that honest range the origin direction moves at most 5 degrees
    on every case in the library. What a high share means is narrower and more useful -- that
    the answer rests on ERA5 and the 3% rule rather than on HYCOM, so it should be checked
    against a wind reanalysis and NOT against a current atlas.

    Returns None on a SYNTHETIC field, rather than 0.0. Every field class here implements
    get_wind -- the analytic and constant ones just return their configured constant, which is
    (0, 0) by default -- so `hasattr` is not the test. The test is whether the wind came from
    ERA5 at all, and the idiom for that in this file is already `bbox`: a real fetched field has
    a box, the lab fields do not. On a lab field the share would be a true statement about a
    field that is not an ocean, and writing it into origin.json would invite exactly the
    misreading the field exists to prevent (CONTRACTS.md 6.5, the rule stranded_fraction
    follows: absence hides a row, a false number misinforms one).
    """
    if getattr(field, "bbox", None) is None or not hasattr(field, "get_wind"):
        return None
    pos = np.asarray(history, dtype=np.float64)
    cur_mag, wind_mag = [], []
    for i, when in enumerate(times[:len(pos)]):
        lons, lats = pos[i][:, 0], pos[i][:, 1]
        cu, cv = field.get_uv(lons, lats, when)
        wu, wv = field.get_wind(lons, lats, when)
        cu, cv = np.asarray(cu, float), np.asarray(cv, float)
        wu, wv = np.asarray(wu, float), np.asarray(wv, float)
        if not np.isfinite(wu).any():
            return None
        cur_mag.append(np.nanmean(np.hypot(cu, cv)))
        wind_mag.append(wind_coeff * np.nanmean(np.hypot(wu, wv)))
    c, w = float(np.mean(cur_mag)), float(np.mean(wind_mag))
    if c + w <= 0.0:
        return None
    return w / (c + w), c, w


def write_origin(path, endpoints, conv_idx, members, t0, timestep_minutes, n_steps,
                 n_runs, stranded_fraction=None, wind_share=None):
    """The real thing: a histogram of every ensemble endpoint, radii measured from the raw
    points, and a time window that is honest about whether it was measured or bounded."""
    (clon, clat), r50, r90 = ens.radii_km(endpoints)
    bounds, values = ens.origin_grid(endpoints)

    start, end, method = ens.time_window(
        conv_idx,
        [m["spread_start_km"] for m in members],
        [m["spread_min_km"] for m in members],
        t0, timestep_minutes, n_steps)

    rows, cols = values.shape
    doc = {
        "bounds": bounds,
        "shape": [rows, cols],
        "values": [float(v) for v in values.reshape(-1)],
        "centroid": [r5(clon), r5(clat)],
        "radius_50_km": round(r50, 2),
        "radius_90_km": round(r90, 2),
        "time_window": [iso(start), iso(end)],
        "ensemble_runs": int(n_runs),
        "abstain": bool(r90 > ABSTAIN_RADIUS_KM),
        # Additive field the brief asks for (03_ANUSHKA_DRIFT.md Phase 3 step 3): says whether
        # the window was measured from ensemble convergence or is the bounded fallback.
        # Not part of the frozen schema — Akshat, flag it if you would rather it lived
        # somewhere else; nothing breaks if the frontend ignores it.
        "time_window_method": method,
    }
    # Phase 4.3. A high fraction is itself a signal -- it means the slick may have originated
    # ashore, or the rewind is running past a coastline. Either is worth surfacing, not hiding.
    # Omitted entirely when there is no real coastline, because 0.0 would be a claim we cannot
    # make: absence hides a UI row, a false zero misinforms one (CONTRACTS.md 6.5).
    if stranded_fraction is not None:
        doc["stranded_fraction"] = round(float(stranded_fraction), 4)
    # Phase 5.3. Says which input the answer actually rests on -- see wind_share_of_drift().
    # Omitted, never zeroed, when the field has no wind term.
    if wind_share is not None:
        doc["wind_share"] = round(float(wind_share), 4)
    path.write_text(json.dumps(doc))
    return clon, clat, r50, r90, method, doc["abstain"]


def write_particles_forward(path, t0, positions, dt_min):
    """particles_forward.json. A SEPARATE FILE and a SEPARATE INTEGRATION (Master 6.4).

    The validator compares the position array against particles.json and ERRORS if they are
    identical, so a relabelled copy is caught mechanically. It should be -- forward and backward
    answer different questions and a copy would answer neither.
    """
    path.write_text(json.dumps({
        "t0": iso(t0), "direction": "forward", "timestep_minutes": dt_min,
        "n_steps": len(positions), "n_particles": len(positions[0]),
        "positions": positions}))


def coastal_impact(history, times, strand_step, dt_min):
    """Phase 2.3. What the forward run says about the coast, and only what it can say.

    Forward-from-slick answers the question a coast guard actually asks -- which coastline is
    threatened, and when. Forward-from-origin would only recreate the slick we already detected.

    What is measurable here: whether particles beach, WHEN the first one does, WHERE, and how
    the stranded fraction grows with time. What is NOT measurable and is therefore not claimed:
    the NAME of the affected stretch. That needs a coastline gazetteer, which is another
    dependency and another thing to get wrong; the landfall footprint below is the honest
    substitute and a human can name it from a map in five seconds.
    """
    n = history.shape[1]
    # A particle SEEDED on land did not make landfall -- it was already ashore at t0, which is a
    # Stage 1 data-quality signal (the detected polygon overlaps the coast), not a forecast.
    # Conflating the two reports "first landfall 0.00 h" and misstates the coastal impact.
    seeded_ashore = strand_step == 0
    landed = strand_step > 0
    out = {
        "n_particles": int(n),
        "seeded_ashore_fraction": float(np.mean(seeded_ashore)),
        "stranded_fraction": float(np.mean(strand_step >= 0)),
        "landfall_fraction": float(np.mean(landed)),
        "span_hours": (len(times) - 1) * dt_min / 60.0,
        "first_landfall": None,
        "landfall_footprint": None,
        "eta_curve": [],
        "note": ("stretch NAMES are not reported: that needs a coastline gazetteer we do not "
                 "have. The footprint is the measured substitute."),
    }
    if seeded_ashore.any():
        out["seeded_ashore_warning"] = (
            f"{out['seeded_ashore_fraction'] * 100:.1f}% of particles were ON LAND at t0. They "
            f"are excluded from the landfall statistics because they never made landfall -- "
            f"they started ashore. This means the detected polygon overlaps the coastline, "
            f"which is Stage 1's to look at.")

    if not landed.any():
        out["verdict"] = ("no particle reached land within the modelled span -- no coastal "
                          "impact from this release at this horizon")
        return out

    k_first = int(strand_step[landed].min())
    who = int(np.argmax(strand_step == k_first))
    pos_first = history[k_first, who]
    out["first_landfall"] = {
        "hours_after_t0": k_first * dt_min / 60.0,
        "time": iso(times[k_first]),
        "position": [r5(float(pos_first[0])), r5(float(pos_first[1]))],
    }
    pts = np.array([history[int(strand_step[i]), i] for i in np.flatnonzero(landed)])
    out["landfall_footprint"] = {
        "west": r5(float(pts[:, 0].min())), "east": r5(float(pts[:, 0].max())),
        "south": r5(float(pts[:, 1].min())), "north": r5(float(pts[:, 1].max())),
        "centroid": [r5(float(pts[:, 0].mean())), r5(float(pts[:, 1].mean()))],
    }
    for hours in range(0, int(out["span_hours"]) + 1, 3):
        k = int(round(hours * 60.0 / dt_min))
        frac = float(np.mean(landed & (strand_step <= k)))
        out["eta_curve"].append({"hours": hours, "stranded_fraction": round(frac, 4)})
    out["verdict"] = (f"first landfall {out['first_landfall']['hours_after_t0']:.2f} h after "
                      f"detection, {out['landfall_fraction'] * 100:.1f}% of particles ashore "
                      f"by {out['span_hours']:.0f} h")
    return out


def run_forward(a, meta, t0, field, seed, feat, out_dir):
    """PHASE 2. Forward from the slick at t0 -- which coast is threatened, and when.

    Deliberately does NOT touch particles.json or origin.json, and does not run the ensemble.
    Those are the backward product; Harshita builds against them and a forward run must not
    disturb them.
    """
    span_h = (a.steps - 1) * a.timestep_minutes / 60.0

    # The field must actually cover the future. Without this the run is a frozen snapshot.
    # Presented as a clean refusal rather than a traceback: this is a "refetch a wider window"
    # instruction for a person, not a crash.
    from step import FieldTimeSpan
    try:
        cov = assert_field_covers(field, t0, t0 + timedelta(hours=span_h), "forward run")
    except FieldTimeSpan as exc:
        raise SystemExit(str(exc))
    if cov is not None:
        print(f"              coverage  field spans {cov[0]:%Y-%m-%dT%H:%MZ} -> "
              f"{cov[1]:%Y-%m-%dT%H:%MZ}  (overhang {cov[2]:.2f} h, tolerated)")

    land = coastline.is_land if coastline.available() else None
    print(f"              coast  {coastline.describe()}")

    history, times, stranded, strand_step = integrate_stranding(
        seed, t0, field, a.steps, a.timestep_minutes, direction="forward",
        is_land=land, return_strand_step=True)

    positions = np.round(history, 5).tolist()
    out_dir.mkdir(parents=True, exist_ok=True)
    fwd_path = out_dir / "particles_forward.json"
    write_particles_forward(fwd_path, t0, positions, a.timestep_minutes)

    impact = coastal_impact(history, times, strand_step, a.timestep_minutes)
    impact_path = out_dir / f"coastal_impact_{a.case}.json"
    impact_path.write_text(json.dumps(impact, indent=2))

    # a forward run must not be a relabelled backward run; prove it here rather than waiting
    # for the validator to catch it
    back_path = out_dir / "particles.json"
    if back_path.exists():
        back = json.loads(back_path.read_text())
        same = back.get("positions") == positions
        print(f"              distinct from particles.json: {not same}"
              + ("  !! IDENTICAL - the validator will reject this" if same else ""))

    dist = displacement_km(history[0], history[-1])
    print(f"[drift:FWD]   wrote {fwd_path}")
    print(f"              wrote {impact_path}   (working space - not in the bundle)")
    print(f"              seeded {a.particles} from {feat['properties']['id']}, ran FORWARD "
          f"{span_h:.2f} h in {a.steps} steps of {a.timestep_minutes} min")
    print(f"              t0 {iso(t0)} -> {iso(times[-1])}")
    print(f"              displacement  median {float(np.median(dist)):.1f} km   "
          f"max {float(dist.max()):.1f} km")
    if impact.get("seeded_ashore_warning"):
        print(f"              !! {impact['seeded_ashore_warning']}")
    print(f"              coastal impact: {impact['verdict']}")
    if impact["first_landfall"]:
        fl = impact["first_landfall"]
        fp = impact["landfall_footprint"]
        print(f"                first ashore at {fl['position']} at {fl['time']}")
        print(f"                footprint W {fp['west']} S {fp['south']} "
              f"E {fp['east']} N {fp['north']}")
    print(f"              NOTE {impact['note']}")
    return 0


def main():
    ap = argparse.ArgumentParser(description="Stage 2 — backward drift + 50-run ensemble")
    ap.add_argument("--case", required=True)
    ap.add_argument("--cases-root", default=str(REPO / "cases"))
    ap.add_argument("--real", action="store_true",
                    help="PHASE 3: real HYCOM + ERA5 from data/fields/<case>.npz")
    ap.add_argument("--fake", action="store_true",
                    help="real RK2 integrator driven by analytic fields (Phase 1)")
    ap.add_argument("--stub", action="store_true", help=argparse.SUPPRESS)  # back-compat alias
    ap.add_argument("--field", choices=["analytic", "constant"], default="analytic",
                    help="with --fake: analytic = a vortex cell on the slick; constant = uniform")
    ap.add_argument("--wind", type=float, nargs=2, default=(6.0, -4.0), metavar=("U", "V"),
                    help="with --fake: 10 m wind, signed m/s components (east, north)")
    ap.add_argument("--fake-current", type=float, nargs=2, default=(0.5, 0.0),
                    metavar=("U", "V"),
                    help="with --fake --field constant: the uniform current, signed m/s. "
                         "ConstantField defaults to a DEAD ocean (0, 0), which makes the mode "
                         "wind-only and means --current-sigma has nothing to scale. 0.5 m/s "
                         "east matches the convention in tests.py.")
    ap.add_argument("--particles", type=int, default=3000)
    ap.add_argument("--runs", type=int, default=50,
                    help="ensemble members. The cut order allows 25; say so in origin.json.")
    ap.add_argument("--steps", type=int, default=97,
                    help="STORED POSITIONS, not physics steps: 97 = t0 + 96 backward "
                         "intervals = exactly 24.0 h (CONTRACTS.md 5)")
    ap.add_argument("--timestep-minutes", type=int, default=15)
    ap.add_argument("--seed", type=int, default=143)
    ap.add_argument("--merge-oil", choices=["auto", "always", "never"], default="auto",
                    help="a slick broken into several oil features is ONE slick when it "
                         "measures as one ribbon (Soum, 13 Sept: Jacksonville is one slick "
                         "with genuine breaks). 'auto' merges only when all four ribbon gates "
                         "pass and prints them either way; 'never' restores the old "
                         "single-highest-confidence behaviour.")
    ap.add_argument("--current-sigma", type=float, default=None,
                    help="width of the current-scale perturbation. Default is the honest "
                         f"{ens.CURRENT_SIGMA} (+/-15%%). Widening it is how the ABSTAIN fixture "
                         "is produced (Phase 3.3): the pipeline writes a real schema-valid "
                         "bundle with abstain=true instead of anyone hand-editing one. A "
                         "non-default value is announced in the output and must never be "
                         "presented as a case result.")
    ap.add_argument("--forward", action="store_true",
                    help="PHASE 2: run FORWARD from the slick at t0 and write "
                         "particles_forward.json + a coastal impact summary. Does not touch "
                         "particles.json or origin.json, and does not run the ensemble.")
    ap.add_argument("--out", default=str(OUT), help="directory for particles.json/origin.json")
    a = ap.parse_args()

    if not (a.real or a.fake or a.stub):
        raise SystemExit(
            "choose an ocean: --real (HYCOM + ERA5, Phase 3) or --fake (analytic, Phase 1).\n"
            "--real needs data/fields/<case>.npz — run pipeline/drift/fetch_fields.py first.")
    if a.real and a.fake:
        raise SystemExit("--real and --fake are mutually exclusive.")

    case_dir = Path(a.cases_root) / a.case
    det_path = case_dir / "detections.geojson"
    if not det_path.exists():
        raise SystemExit(f"{det_path} not found — Stage 2 seeds from Stage 1's output. "
                         f"Run pipeline/detect/run.py first, or use cases/case-000.")

    meta = json.loads((case_dir / "meta.json").read_text())
    t0 = parse_ts(meta["detection_time"])
    feat, slick_diag = merge_oil_features(json.loads(det_path.read_text()),
                                          mode=a.merge_oil)
    if feat is None:
        raise SystemExit(
            "detections.geojson contains zero 'oil' features. That is the no-spill case — "
            "there is nothing to rewind, and 'trace' should not be in meta.acts_available.")

    rng = random.Random(a.seed)
    seed = seed_particles(feat, a.particles, rng)

    if a.real:
        field = load_case_field(a.case, repo_root=REPO)
        tag = "REAL"
    else:
        clon0 = float(feat["properties"]["centroid"][0])
        clat0 = float(feat["properties"]["centroid"][1])
        fake_kw = {"wind": tuple(a.wind)}
        if a.field == "constant":
            fake_kw["current"] = tuple(a.fake_current)
        field = make_fake(a.field, lon0=clon0, lat0=clat0, **fake_kw)
        tag = "FAKE"

    geom_kind, geom_why = seed_geometry(feat["properties"])
    print(f"[drift:{tag}]  seeding {geom_kind.upper()}: {geom_why}")

    if a.forward:
        return run_forward(a, meta, t0, field, seed, feat, Path(a.out))

    span_h = (a.steps - 1) * a.timestep_minutes / 60.0    # states recorded, not steps taken

    # ---- control run: the animation ---------------------------------------------------
    # The BACKWARD run needs coverage too, and did not check it. Jacksonville is the case that
    # showed why: fetched with filterDate(start, t0), its last HYCOM snapshot lands 2.36 h
    # BEFORE t0, because the 3-hourly snapshots go ...18:00, 21:00, 00:00 and t0 is 23:21. So
    # the first 2.36 h of the rewind -- the end NEAREST the detection, where the answer is most
    # sensitive -- ran through a frozen field, silently. --forward-hours fixes both directions
    # at once, because it pulls the snapshots that bracket t0 instead of stopping short of it.
    from step import FieldTimeSpan
    try:
        cov = assert_field_covers(field, t0, t0 - timedelta(hours=span_h), "backward run")
        if cov is not None and cov[2] > 0.0:
            print(f"              coverage  field spans {cov[0]:%Y-%m-%dT%H:%MZ} -> "
                  f"{cov[1]:%Y-%m-%dT%H:%MZ}  (overhang {cov[2]:.2f} h, tolerated)")
    except FieldTimeSpan as exc:
        raise SystemExit(str(exc))

    land = coastline.is_land if coastline.available() else None
    print(f"              coast  {coastline.describe()}")
    if not coastline.available():
        print(f"              NOTE   {coastline.why_unavailable()}")
    history, times, stranded_ctl = integrate_stranding(
        seed, t0, field, a.steps, a.timestep_minutes, direction="backward", is_land=land)
    positions = np.round(history, 5).tolist()

    # ---- ensemble: the answer ---------------------------------------------------------
    if a.current_sigma is not None and abs(a.current_sigma - ens.CURRENT_SIGMA) > 1e-9:
        print(f"[drift:{tag}]  !! CURRENT SIGMA OVERRIDDEN: {a.current_sigma} instead of the "
              f"honest {ens.CURRENT_SIGMA}.")
        print(f"              This widens the uncertainty budget beyond what the physics "
              f"supports. The only sanctioned use is")
        print(f"              producing the Phase 3.3 abstain fixture. This output is NOT a "
              f"case result and must not be shown as one.")

    nprng = np.random.default_rng(a.seed)

    def tick(done, total):
        if done == 1 or done % 10 == 0 or done == total:
            print(f"              ensemble {done}/{total}", flush=True)

    endpoints, conv_idx, members = ens.run_ensemble(
        seed, t0, field, a.steps, a.timestep_minutes, n_runs=a.runs, rng=nprng, progress=tick,
        is_land=land, current_sigma=a.current_sigma)
    # the reported fraction is the ENSEMBLE's, not the control run's: origin.json describes the
    # cloud, and the cloud is the ensemble
    strand_frac = (float(np.mean([m["stranded_fraction"] for m in members]))
                   if land is not None else None)

    # ---- the loud edge guard (Phase 3.1) ----------------------------------------------
    # Runs BEFORE anything is written. A cloud whose particles reached the wall must not be
    # able to leave this script as a bundle -- that is the whole point of the guard. A real
    # field has a box; the analytic and constant fields do not, so there is nothing to check.
    box = getattr(field, "bbox", None)
    if box is not None:
        checked = np.vstack([history[-1], endpoints])
        margin = assert_inside_field_box(checked, box, margin_km=10.0,
                                         label="control + ensemble endpoints")
        print(f"              edge guard  closest particle sits {margin:.1f} km inside the "
              f"field box (limit 10 km)")

    # ---- Phase 5.3: which input is the answer resting on? -----------------------------
    ws = wind_share_of_drift(field, history, times)
    wind_share = None
    if ws is not None:
        wind_share, c_mag, w_mag = ws
        print(f"              drift mix  current {c_mag:.3f} m/s + 0.03xwind {w_mag:.3f} m/s "
              f"= wind is {100 * wind_share:.0f}% of the drift")
        if wind_share >= 0.5:
            print(f"              !! WIND-DOMINATED CASE  the origin direction is set by ERA5 "
                  f"and the 0.03 rule, NOT by HYCOM.")
            print(f"              Check it against a WIND reanalysis. A current atlas will "
                  f"disagree and that disagreement is not an error.")
            print(f"              (Ensemble already spans U(0.025, 0.035); direction moves "
                  f"<=5 deg across that range, so this is a provenance note, not a wider cloud.)")

    out_dir = Path(a.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    write_particles(out_dir / "particles.json", t0, positions, a.timestep_minutes)
    clon, clat, r50, r90, method, abstain = write_origin(
        out_dir / "origin.json", endpoints, conv_idx, members,
        t0, a.timestep_minutes, a.steps, a.runs, stranded_fraction=strand_frac,
        wind_share=wind_share)

    # The endpoint pool, kept so plot_heatmap.py can draw the cloud without rerunning 50 runs.
    np.savez_compressed(out_dir / f"ensemble_{a.case}.npz",
                        endpoints=endpoints,
                        control_final=history[-1],
                        seed=np.asarray(seed, dtype=np.float64),
                        conv_idx=conv_idx,
                        wind_coeff=np.array([m["wind_coeff"] for m in members]),
                        current_scale=np.array([m["current_scale"] for m in members]))

    # The permanent plausibility guard, on every real run, not just in tests.py.
    med_km = assert_displacement_plausible(history[0], history[-1], hours=span_h)
    dist = displacement_km(history[0], history[-1])
    ws = np.array([m["wind_coeff"] for m in members])
    cs = np.array([m["current_scale"] for m in members])

    print(f"[drift:{tag}]  wrote {out_dir / 'particles.json'}")
    print(f"              wrote {out_dir / 'origin.json'}")
    print(f"              field  {field}")
    print(f"              seeded {a.particles} from {feat['properties']['id']} "
          f"({feat['properties']['shape_class']}), rewound {span_h:.2f} h "
          f"in {a.steps} steps of {a.timestep_minutes} min")
    print(f"              t0 {iso(t0)} -> {iso(times[-1])}")
    print(f"              control displacement  median {med_km:.1f} km   "
          f"min {float(dist.min()):.1f}   max {float(dist.max()):.1f}")
    print(f"              ensemble {a.runs} runs x {a.particles} = {len(endpoints):,} endpoints"
          f"   wind_coeff {ws.min():.4f}-{ws.max():.4f}   current x{cs.min():.2f}-{cs.max():.2f}")
    print(f"              origin ({clon:.4f}, {clat:.4f})  "
          f"r50={r50:.1f} km  r90={r90:.1f} km  abstain={abstain}")
    print(f"              time_window method={method}")
    if strand_frac is not None:
        ctl = float(np.mean(stranded_ctl))
        print(f"              stranded  {strand_frac * 100:.2f}% of ensemble endpoints "
              f"({ctl * 100:.2f}% of the control run) reached land and were held")
        if strand_frac > 0.10:
            print(f"              !! {strand_frac * 100:.0f}% stranded is high. Either the slick "
                  f"originated ashore or the rewind runs past a coastline -- look at the "
                  f"heatmap before believing the origin.")


if __name__ == "__main__":
    main()
