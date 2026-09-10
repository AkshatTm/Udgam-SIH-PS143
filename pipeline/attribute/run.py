#!/usr/bin/env python3
"""
Stage 3 — AIS attribution. Owner: Jaiveer.

    python pipeline/attribute/run.py --case case-000 --stub

STUB ONLY. Reads `origin.json` and writes schema-valid `out/vessels.geojson` +
`out/suspects.json`. No AIS is read; the vessels are invented.

Two behaviours here are real and worth keeping, because the validator enforces them and the
demo depends on them:
  - the ABSTAIN path: origin.abstain == true  ->  suspects MUST be empty, funnel still
    populated, and the UI says "attribution not possible at acceptable confidence". The
    refusal is a designed feature, not a failure.
  - funnel consistency: in_region >= in_window >= plausible >= scored, scored == len(suspects),
    every suspect MMSI has a track in vessels.geojson, suspects sorted by descending score,
    and at least one exclusion carrying a plain-language reason.

DELETE `fake_fleet()` the moment real AIS lands. Those MMSIs and names are placeholders and
must never reach a judge: every vessel on screen comes from the real NOAA file, and if the
documented incident's vessel doesn't rank top-3, that is the result we show.

The real scoring is a deterministic weighted sum with the weights below as named constants —
no ML. See docs/06_JAIVEER_AIS.md Phase 2.

Deliberately stdlib-only. The real ingest needs duckdb/pyarrow/pandas/shapely.
"""
import argparse
import json
import math
import random
from datetime import datetime, timedelta, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
OUT = HERE / "out"

KM_PER_DEG = 111.32

# Scoring weights — named constants, deterministic, explainable. Used by the real scorer.
W_PROXIMITY = 0.40
W_TRAJECTORY = 0.20
W_SLOWDOWN = 0.15
W_GAP = 0.15
W_TYPE_PRIOR = 0.10
TYPE_PRIOR = {"tanker": 1.0, "cargo": 1.0, "fishing": 0.4, "passenger": 0.2, "other": 0.5}


def iso(dt):
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_ts(s):
    dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        raise SystemExit(f"'{s}' is timezone-naive — every timestamp needs the trailing Z")
    return dt


def r5(x):
    return round(float(x), 5)


def fake_fleet(clon, clat, rng, n_points=220):
    """DELETE THIS. Invented tracks crossing the origin region at different offsets."""
    klat = 1.0 / max(math.cos(math.radians(clat)), 1e-6)
    fleet = [("367000101", "FAKE ATLAS", "tanker", 0.00, 85),
             ("367000102", "FAKE MERIDIAN", "cargo", 0.09, 12),
             ("367000103", "FAKE PELICAN", "fishing", -0.11, 12),
             ("367000104", "FAKE CORAL", "cargo", 0.17, 12),
             ("367000105", "FAKE VESPER", "tanker", -0.19, 12)]
    feats = []
    for mmsi, name, vtype, off, gap in fleet:
        coords = []
        for i in range(n_points):
            k = i / (n_points - 1)
            lon = (clon - 0.34 * klat) + k * (0.68 * klat) + math.sin(k * 5) * 0.012 * klat
            lat = (clat - 0.24 + off) + k * 0.44 + math.cos(k * 4) * 0.010
            coords.append([r5(lon), r5(lat)])
        feats.append({"type": "Feature",
                      "geometry": {"type": "LineString", "coordinates": coords},
                      "properties": {"mmsi": mmsi, "name": name, "vessel_type": vtype,
                                     "n_points": n_points, "max_gap_minutes": gap}})
    return fleet, feats


def closest_km(track_coords, clon, clat):
    k = math.cos(math.radians(clat))
    return min(math.hypot((p[0] - clon) * k * KM_PER_DEG, (p[1] - clat) * KM_PER_DEG)
               for p in track_coords)


def main():
    ap = argparse.ArgumentParser(description="Stage 3 — AIS attribution (stub)")
    ap.add_argument("--case", required=True)
    ap.add_argument("--cases-root", default=str(REPO / "cases"))
    ap.add_argument("--stub", action="store_true", help="required until the real scorer exists")
    ap.add_argument("--seed", type=int, default=143)
    a = ap.parse_args()

    if not a.stub:
        raise SystemExit(
            "attribute/run.py has no real implementation yet — pass --stub.\n"
            "Building it is Phases 1-2 of docs/06_JAIVEER_AIS.md.")

    case_dir = Path(a.cases_root) / a.case
    org_path = case_dir / "origin.json"
    if not org_path.exists():
        raise SystemExit(f"{org_path} not found — Stage 3 scores against Stage 2's origin cloud. "
                         f"Run pipeline/drift/run.py first, or use cases/case-000.")

    org = json.loads(org_path.read_text())
    clon, clat = float(org["centroid"][0]), float(org["centroid"][1])
    win_start, win_end = parse_ts(org["time_window"][0]), parse_ts(org["time_window"][1])
    abstain = bool(org.get("abstain", False))

    rng = random.Random(a.seed)
    fleet, feats = fake_fleet(clon, clat, rng)

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "vessels.geojson").write_text(json.dumps(
        {"type": "FeatureCollection", "features": feats}))

    by_mmsi = {f["properties"]["mmsi"]: f for f in feats}
    dist = {m: closest_km(by_mmsi[m]["geometry"]["coordinates"], clon, clat) for m in by_mmsi}
    mid = win_start + (win_end - win_start) / 2

    if abstain:
        # The designed refusal. Funnel still populated so the judge sees the work that was done.
        suspects, excluded = [], [
            {"mmsi": m, "name": nm, "closest_km": round(dist[m], 1),
             "reason": "origin cloud too diffuse to attribute at acceptable confidence"}
            for m, nm, _, _, _ in fleet[:1]]
        funnel = {"in_region": 412, "in_window": 63, "plausible": 12, "scored": 0}
    else:
        ranked = sorted(fleet, key=lambda f: dist[f[0]])
        suspects = []
        for rank, (mmsi, name, vtype, _off, gap) in enumerate(ranked[:3]):
            proximity = max(0.0, 1.0 - dist[mmsi] / max(org["radius_90_km"] * 2, 1.0))
            trajectory = 1.0 if rank != 2 else 0.0
            slowdown = 1.0 if rank == 0 else 0.0
            gap_hit = 1.0 if gap >= 30 else 0.0
            score = (W_PROXIMITY * proximity + W_TRAJECTORY * trajectory +
                     W_SLOWDOWN * slowdown + W_GAP * gap_hit +
                     W_TYPE_PRIOR * TYPE_PRIOR.get(vtype, 0.5))
            reasons = []
            if dist[mmsi] <= org["radius_50_km"]:
                reasons.append("inside the 50% origin radius during the window")
            elif dist[mmsi] <= org["radius_90_km"]:
                reasons.append("inside the 90% origin radius during the window")
            else:
                reasons.append("at the edge of the 90% origin radius")
            if gap_hit:
                reasons.append(f"{gap}-minute transponder gap overlapping the window")
            if trajectory:
                reasons.append(f"{vtype} on a course consistent with the origin")
            suspects.append({
                "mmsi": mmsi, "name": name, "vessel_type": vtype,
                "score": round(min(score, 1.0), 3),
                "closest_km": round(dist[mmsi], 1), "closest_time": iso(mid),
                "heading_consistent": bool(trajectory),
                "ais_gap_minutes": gap, "reasons": reasons})
        suspects.sort(key=lambda s: s["score"], reverse=True)

        excluded = [{"mmsi": m, "name": nm, "closest_km": round(dist[m], 1),
                     "reason": "heading away from the origin throughout the window"}
                    for m, nm, _, _, _ in ranked[3:4]]
        excluded += [{"mmsi": m, "name": nm, "closest_km": round(dist[m], 1),
                      "reason": "left the region before the origin time window opened"}
                     for m, nm, _, _, _ in ranked[4:5]]
        funnel = {"in_region": 412, "in_window": 63, "plausible": 12, "scored": len(suspects)}

    (OUT / "suspects.json").write_text(json.dumps(
        {"funnel": funnel, "suspects": suspects, "excluded": excluded}, indent=2))

    print(f"[attrib:STUB] wrote {OUT / 'vessels.geojson'}  ({len(feats)} tracks)")
    print(f"              wrote {OUT / 'suspects.json'}")
    if abstain:
        print("              origin.abstain=true -> zero suspects (the designed refusal)")
    else:
        print(f"              funnel {funnel['in_region']} -> {funnel['in_window']} -> "
              f"{funnel['plausible']} -> {funnel['scored']}, "
              f"{len(excluded)} exclusion(s)")
        print(f"              top: {suspects[0]['name']} score={suspects[0]['score']} "
              f"closest={suspects[0]['closest_km']} km")


if __name__ == "__main__":
    main()
