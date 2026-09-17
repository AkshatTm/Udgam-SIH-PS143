#!/usr/bin/env python3
"""
Stage 2 — which slick do we seed from, and what shape is the seed? Owner: Anushka.

EXTRACTED FROM run.py, 16 Sept 2026. Pure move, no behaviour change.

WHY IT MOVED
    `run.py` needs these to seed the control run. `age.py` needs the SAME functions to pick the
    same slick and measure the same geometry -- and it used to get them by importing `run` from
    inside `main()` (`from run import merge_oil_features`), an import placed there precisely
    because a module-level one would have been a cycle.

    Phase 4 makes `run.py` call `age.estimate_age()` as a library, which turns that latent cycle
    into a real one. Moving the shared code down into a module neither of them owns makes the
    cycle impossible rather than merely avoided-by-luck. `publish_all.py` and
    `compare_opendrift.py` import from here too, so all four callers now agree by construction
    instead of by four copies staying in sync.

    `pick_slick` in particular existed TWICE -- run.py:66 and age.py:983, byte-identical. Two
    copies of "which slick is the answer about" is exactly the divergence this repo keeps
    getting bitten by.

WHAT IS HERE
    pick_slick              highest-confidence 'oil' feature, or None
    slick_rings             every outer ring, Polygon and MultiPolygon alike
    ribbon_metrics          the four measurements that decide one-ribbon vs separate slicks
    is_one_ribbon           those four against their gates, with reasons for BOTH outcomes
    merged_discharge_class  one class for a merged slick
    merge_oil_features      the decision, and the merged MultiPolygon feature
    group_oil_features      D46: partitions every oil feature into independent spill groups so
                             genuinely separate slicks (Gulf of Alaska, Mumbai) are never dropped
                             the way merge_oil_features's single-best fallback used to
    seed_geometry           line vs point, with discharge_class as the authority
    seed_particles          the actual seed cloud
"""
import math

import numpy as np

KM_PER_DEG = 111.32


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
    """One class for a merged slick, per Soumirya (13 Sept): take the defined one, never average.

    `discharge_class` is computed PER REGION from that region's own elongation, so the parts of
    one ribbon disagree -- Jacksonville's det-02 is 'chronic' while det-01 and det-03 are
    'unknown'. A merged object has no well-defined class, so:

      any part 'chronic'  -> 'chronic'. A 34 km ribbon broken into pieces IS a vessel track;
                             that is the physical reading, and it is also the conservative one,
                             because 'chronic' is the one class `age.age_gate` REFUSES outright
                             (source motion, not shear, set the major axis) rather than letting
                             an age estimate fire on a merged geometry.
      otherwise unanimous -> that value
      otherwise           -> 'unknown', and the fallback to shape_class says so out loud

    NOTE, 16 Sept 2026: this used to say 'chronic' GATES THE ACUTE-ONLY estimators off. The
    acute-only gate is gone -- `age.age_gate` now refuses `chronic` on physics and lets
    `unknown` through with a widened band. The conservative reading above is unchanged and so is
    this function, but the reason is now "chronic is refused" rather than "only acute is
    allowed".
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

    Soumirya's ruling (13 Sept) on Jacksonville: "one slick, genuine breaks -- treat it as one."
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
            # Soumirya (13 Sept): `elongation` is cv2.fitEllipse major/minor in PIXEL coordinates,
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
        print(f"         NOTE Soumirya: our outline over-extends (Jacksonville IoU 0.483, "
              f"recall 0.825, precision 0.537), so a merged")
        print(f"         area is generous -- Cerulean's polygon for the same slick is "
              f"4.55 km2 against our {area:.2f} km2.")
    return merged, diag


def _build_merged_feature(members, m):
    """A MultiPolygon merging `members` (>=2 features already confirmed one ribbon by the
    caller). Extracted verbatim from merge_oil_features's own merge branch above so
    group_oil_features can build a multi-member group's seed geometry the identical way -- one
    copy of "how a merge is built", the same rule this module's own docstring states about
    pick_slick. merge_oil_features itself is left untouched (still builds its own copy inline)
    so its exact behaviour -- and the tests pinned on it -- never move."""
    order = sorted(members, key=lambda f: -(f["properties"].get("area_km2", 0.0) or 0.0))
    coords = [[r.tolist()] for f in members for r in slick_rings(f)]
    area = float(sum(f["properties"].get("area_km2", 0.0) or 0.0 for f in members))
    wsum = sum((f["properties"].get("area_km2", 0.0) or 0.0) for f in members) or 1.0
    clon = sum(f["properties"]["centroid"][0] * (f["properties"].get("area_km2") or 0.0)
               for f in members) / wsum
    clat = sum(f["properties"]["centroid"][1] * (f["properties"].get("area_km2") or 0.0)
               for f in members) / wsum
    dc, dc_why = merged_discharge_class(members)
    ids = [f["properties"].get("id") for f in order]
    return {
        "type": "Feature",
        "geometry": {"type": "MultiPolygon", "coordinates": coords},
        "properties": {
            "id": "+".join(ids),
            "classification": "oil",
            "area_km2": area,
            "centroid": [clon, clat],
            "discharge_class": dc,
            "shape_class": "linear" if (m["aspect"] or 0) >= 3.0 else "blob",
            "confidence": float(max(f["properties"].get("confidence", 0.0) for f in members)),
            "elongation": None,
            "merged_from": ids,
            "merged_discharge_reason": dc_why,
        },
    }


def _partitions(items):
    """Yield every set partition of `items` (a list) as a list of lists, deterministically."""
    if not items:
        yield []
        return
    first, rest = items[0], items[1:]
    for smaller in _partitions(rest):
        yield [[first]] + smaller
        for i in range(len(smaller)):
            yield smaller[:i] + [[first] + smaller[i]] + smaller[i + 1:]


MAX_OIL_FOR_EXHAUSTIVE_PARTITION = 8   # Bell(8)=4140, instant; refuse above rather than hang


def group_oil_features(dets, mode="auto", verbose=True):
    """Partition every 'oil' feature into independent spill GROUPS.

    merge_oil_features() above answers "one ribbon, or the single best feature" -- adequate when
    a scene has one slick fragmented by detector noise (Jacksonville), but on a scene with
    several GENUINELY separate spills (case-gulf-alaska-2023, case-mumbai-2023) its fallback
    silently drops every oil feature except the single highest-confidence one. This answers the
    harder question instead: which features belong together, and which are independent -- no
    feature may ever be dropped.

    Reuses ribbon_metrics/is_one_ribbon UNCHANGED -- same four gates, same thresholds -- only the
    search over WHICH subsets to test is new: merge_oil_features tests only "all of them, or
    none"; this exhaustively searches every set partition (small n -- an operational detector
    rarely emits more than 3-4 disjoint oil polygons) for the COARSEST partition where every
    group of size >=2 passes is_one_ribbon on its own combined metrics.

    mode: 'never' -> every feature its own singleton group. 'always' -> one group of everyone.
    'auto' (default) -> the search above; ties (equal group count) broken by generation order of
    _partitions() over id-sorted input, which is deterministic.

    Returns (groups, diag). `groups` is ordered by descending total_area_km2:
        [{"feature": <Feature, Polygon or MultiPolygon>,
          "member_ids": [<detection id>, ...],
          "ribbon": {"merged": bool, "metrics": {...}|None, "gates": [...]|None},
          "total_area_km2": float}, ...]
    Zero oil features -> ([], diag).
    """
    oil = [f for f in dets.get("features", [])
           if (f.get("properties") or {}).get("classification") == "oil"]
    diag = {"n_oil": len(oil), "mode": mode}
    if not oil:
        diag["decision"] = "no oil features"
        return [], diag
    oil = sorted(oil, key=lambda f: f["properties"].get("id") or "")

    if len(oil) == 1 or mode == "never":
        partition = [[f] for f in oil]
        diag["decision"] = "singletons" if mode == "never" else "single feature"
    elif mode == "always":
        partition = [oil]
        diag["decision"] = "always merged into one group"
    else:
        if len(oil) > MAX_OIL_FOR_EXHAUSTIVE_PARTITION:
            raise SystemExit(
                f"{len(oil)} oil features on one scene -- more than the "
                f"{MAX_OIL_FOR_EXHAUSTIVE_PARTITION} this exhaustive grouping search is sized "
                f"for. Pass --merge-oil never or always, or raise the cap deliberately.")
        cache = {}

        def _valid(g):
            if len(g) == 1:
                return True
            key = frozenset(f["properties"].get("id") for f in g)
            if key not in cache:
                cache[key] = is_one_ribbon(ribbon_metrics(g))[0]
            return cache[key]

        best = None
        for part in _partitions(oil):
            if all(_valid(g) for g in part) and (best is None or len(part) < len(best)):
                best = part
        partition = best   # all-singletons is always valid, so best is never None
        diag["decision"] = f"{len(oil)} oil features -> {len(partition)} group(s)"

    groups = []
    for members in partition:
        if len(members) == 1:
            feat, ribbon_diag = members[0], {"merged": False, "metrics": None, "gates": None}
        else:
            m = ribbon_metrics(members)
            _, reasons = is_one_ribbon(m)
            feat, ribbon_diag = _build_merged_feature(members, m), {
                "merged": True, "metrics": m, "gates": reasons}
        groups.append({
            "feature": feat,
            "member_ids": [f["properties"].get("id") for f in members],
            "ribbon": ribbon_diag,
            "total_area_km2": float(sum(f["properties"].get("area_km2", 0.0) or 0.0
                                        for f in members)),
        })
    groups.sort(key=lambda g: -g["total_area_km2"])
    diag["n_groups"] = len(groups)
    if verbose:
        print(f"[slick]  {len(oil)} oil feature(s) -> {len(groups)} independent spill group(s)")
        for g in groups:
            print(f"         {g['member_ids']}  area {g['total_area_km2']:.3f} km2  "
                  f"{'MERGED ribbon' if g['ribbon']['merged'] else 'singleton'}")
    return groups, diag


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
