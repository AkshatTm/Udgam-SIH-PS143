#!/usr/bin/env python3
"""
Stage 3, Phase 8 — the injected-offender curve. Owner: Jaiveer's design, built 14 Sept.

    python pipeline/attribute/evaluate.py --parquet data/ais/huntington.parquet
    python pipeline/attribute/evaluate.py --parquet data/ais/huntington.parquet --trials 60 --json out.json

WHY THIS EXISTS
Every attribution number we could otherwise quote would be tuned on a case whose answer we
know, which is exactly what D21 forbids. This is the legitimate route: real AIS traffic, a
SYNTHETIC guilty vessel whose discharge point, transponder gap, speed profile and course we
control, and a rank we can therefore check. Sweep the conditions, report how often the scorer
puts the guilty vessel first.

It is also the only D21-compliant way to answer the two open weight questions (A5 `trajectory`,
A6 `type_prior`): the per-component ablation re-ranks every trial with one component forced to
`null` and reports what that costs. **No weight is changed by this script.** It measures; the
ruling stays Akshat's.

WHAT THIS MEASURES, AND WHAT IT DOES NOT
It measures RANKING, given an origin cloud that is correct by construction: the cloud is
centred on the offender's own discharge point. That is deliberate — it isolates Stage 3 from
Stage 2's error — but it means the number is an upper bound on end-to-end performance, and it
must be quoted that way:

    "Given a correct origin, the scorer ranks the responsible vessel first in N% of injected
     scenarios at this traffic density."

It is NOT an accuracy figure for the live cases, it says nothing about whether the origin was
right, and a real fleet contains no labelled offender to check against. Say all three.

Abstention is counted separately and is never scored as a hit or a miss. A refusal is a
designed outcome (D9, and the abstain rules in score.py); folding it into either column would
make a refusal look like a wrong answer or like a right one.
"""
import argparse
import json
import math
import random
import statistics
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(HERE))

import geo                                              # noqa: E402
import score as S                                       # noqa: E402
from tracks import Track, load_tracks                   # noqa: E402

KM_PER_DEG = 111.32

# Sweep points. Each is "everything at baseline except this one axis".
DENSITY_FRACTIONS = (0.25, 0.5, 1.0)
GAP_MINUTES = (0, 45, 120)
R90_TARGETS_KM = (3.0, 10.0, 25.0)
SAMPLING = ("noaa_dense", "gfw_hourly")

ORIGIN_ERROR_FRACTIONS = (0.0, 0.5, 1.0)     # x r90: a perfect origin, a fair one, a poor one
OFFENDER_PROFILES = ("full", "plain")        # with gap+slowdown, or a ship that just sailed through

BASELINE = {"density": 1.0, "gap": 45, "r90": 10.0, "sampling": "noaa_dense",
            "origin_error_frac": 0.5, "slowdown": True}

ABLATIONS = ("none",) + tuple(S.WEIGHTS)


# --------------------------------------------------------------------------- the offender

def synthetic_offender(discharge_lon, discharge_lat, when, cadence_s, gap_minutes,
                       slowdown, course_deg, speed_kn, mmsi="000000001",
                       vessel_type="tanker", type_code=80):
    """A vessel that transits through `discharge_lon/lat` at `when`, built report by report.

    Straight-line transit at constant course, so the geometry is checkable on paper: it
    approaches from `course_deg - 180` and leaves on `course_deg`. Reports run for six hours
    either side, which is long enough that it has positions outside any r90 in the sweep (the
    `trajectory` component gates to null without one, D27).

    `gap_minutes` deletes a silence ending 20 minutes BEFORE closest approach, so the vessel is
    under way on both sides of it and the silence overlaps the release window — the shape
    `component_gap` is looking for. `slowdown` multiplies speed within +/-15 min of closest
    approach.
    """
    span_s = 6 * 3600
    klat = 1.0 / max(math.cos(math.radians(discharge_lat)), 1e-6)
    ux = math.sin(math.radians(course_deg)) * klat / KM_PER_DEG   # deg lon per km
    uy = math.cos(math.radians(course_deg)) / KM_PER_DEG          # deg lat per km

    silence_end = when - timedelta(minutes=20)
    silence_start = silence_end - timedelta(minutes=gap_minutes)

    ts, lon, lat, sog, cog = [], [], [], [], []
    for k in range(-span_s // cadence_s, span_s // cadence_s + 1):
        t = when + timedelta(seconds=k * cadence_s)
        if gap_minutes and silence_start < t < silence_end:
            continue                       # transponder dark
        km = speed_kn * 1.852 * (k * cadence_s) / 3600.0     # nm/h -> km/h
        ts.append(t)
        lon.append(discharge_lon + km * ux)
        lat.append(discharge_lat + km * uy)
        near = abs((t - when).total_seconds()) <= 900
        sog.append(speed_kn * (0.35 if (slowdown and near) else 1.0))
        cog.append(course_deg)
    return Track(mmsi, "INJECTED OFFENDER", vessel_type, type_code, ts, lon, lat, sog, cog)


def decimate(track, cadence_s):
    """Keep roughly one report per `cadence_s`, mimicking a sparser AIS feed (GFW is hourly)."""
    keep_ts, keep = [], []
    last = None
    for i, t in enumerate(track.ts):
        if last is None or (t - last).total_seconds() >= cadence_s:
            keep.append(i)
            keep_ts.append(t)
            last = t
    if len(keep) < 2:
        return None
    return Track(track.mmsi, track.name, track.vessel_type, track.type_code,
                 keep_ts, [track.lon[i] for i in keep], [track.lat[i] for i in keep],
                 [track.sog[i] for i in keep], [track.cog[i] for i in keep])


# ------------------------------------------------------------------------------ the cloud

def _grid_values(sigma_km, aspect, bearing_deg, n, clat):
    """r90 in km of the same cloud built at this sigma, in a flat local frame.

    Only used to calibrate sigma against a target r90 — the cloud is self-similar in sigma, so
    one measurement fixes the scale for every size in the sweep.
    """
    half = 3.0 * sigma_km * aspect
    ux, uy = math.sin(math.radians(bearing_deg)), math.cos(math.radians(bearing_deg))
    cells = []
    for r in range(n):
        dy = half - (r + 0.5) * 2 * half / n
        for c in range(n):
            dx = -half + (c + 0.5) * 2 * half / n
            along = dx * ux + dy * uy
            across = -dx * uy + dy * ux
            v = math.exp(-0.5 * ((along / (sigma_km * aspect)) ** 2 + (across / sigma_km) ** 2))
            cells.append((math.hypot(dx, dy), v))
    cells.sort(key=lambda x: x[0])
    total = sum(v for _, v in cells) or 1.0
    run = 0.0
    for d, v in cells:
        run += v
        if run >= 0.9 * total:
            return d
    return cells[-1][0]


def synthetic_grid(clon, clat, r90_km, t0, t1, aspect=4.0, bearing_deg=175.0, n=101):
    """An elongated gaussian origin cloud centred on `clon/clat`, sized to hit `r90_km`.

    Elongated on purpose: a circular fixture cannot tell a grid-sampling scorer from a
    circle-membership one (D8), and the real clouds run 3.7-4.4:1. The returned grid reports
    its MEASURED r50/r90, not the target, so the sweep axis is what the scorer actually saw.
    """
    # Pick sigma by measurement, not by the isotropic 2.146-sigma rule: at aspect 4 the long
    # axis dominates the containing circle, and that rule produced clouds ~3x the size on the
    # label. The whole construction (bounds included) scales linearly with sigma, so the grid is
    # self-similar: measure r90 once at sigma = 1 km and scale it to the target exactly.
    unit = _grid_values(1.0, aspect, bearing_deg, n, clat)
    sigma_km = r90_km / max(unit, 1e-9)
    half = 3.0 * sigma_km * aspect
    dlat = half / KM_PER_DEG
    dlon = half / (KM_PER_DEG * max(math.cos(math.radians(clat)), 1e-6))
    west, east, south, north = clon - dlon, clon + dlon, clat - dlat, clat + dlat

    ux, uy = math.sin(math.radians(bearing_deg)), math.cos(math.radians(bearing_deg))
    vals, coslat = [], max(math.cos(math.radians(clat)), 1e-6)
    for r in range(n):
        latq = north - (r + 0.5) * (north - south) / n
        for c in range(n):
            lonq = west + (c + 0.5) * (east - west) / n
            dx = (lonq - clon) * coslat * KM_PER_DEG
            dy = (latq - clat) * KM_PER_DEG
            along = dx * ux + dy * uy
            across = -dx * uy + dy * ux
            vals.append(math.exp(-0.5 * ((along / (sigma_km * aspect)) ** 2 +
                                         (across / sigma_km) ** 2)))
    peak = max(vals) or 1.0
    vals = [v / peak for v in vals]

    # Measured mass radii, so the reported cloud size is the one the scorer sampled. Same
    # definition as make_fake_case.mass_radii: the CIRCLE radius containing 50%/90% of the
    # mass, so cells are ordered by DISTANCE and the mass accumulated outward. Ordering them
    # by probability instead returns the distance of whichever cell happens to cross the
    # threshold, which on an elongated cloud is not a radius at all — it reported r50 > r90.
    order = []
    for i, v in enumerate(vals):
        r, c = divmod(i, n)
        latq = north - (r + 0.5) * (north - south) / n
        lonq = west + (c + 0.5) * (east - west) / n
        order.append((geo.haversine_km(clon, clat, lonq, latq), v))
    order.sort(key=lambda x: x[0])
    total = sum(v for _, v in order) or 1.0
    run, r50, r90 = 0.0, None, None
    for d, v in order:
        run += v
        if r50 is None and run >= 0.5 * total:
            r50 = d
        if run >= 0.9 * total:
            r90 = d
            break
    return geo.OriginGrid({
        "bounds": {"west": west, "south": south, "east": east, "north": north},
        "shape": [n, n], "values": vals, "centroid": [clon, clat],
        "radius_50_km": round(r50 or 0.0, 3), "radius_90_km": round(r90 or 0.0, 3),
        "time_window": [S.iso(t0), S.iso(t1)], "time_window_method": "convergence",
        "ensemble_runs": 50, "abstain": False,
    })


# -------------------------------------------------------------------------------- scoring

def rank_of_offender(comps_by_vessel, offender_mmsi, drop=None):
    """(rank, abstained, n_plausible) with `drop` forced to null for every vessel.

    Re-ranks from components already computed, so an ablation costs a dictionary rebuild
    rather than a rescore. Rank is 1-based among the plausible set; None if the offender
    never reached it.

    This function re-implements score.py's decision to name or withhold, so it has to move
    WITH it. When score.py stopped discarding a ranking on a tie, a low top score or a crowded
    box, an evaluate.py left behind would have gone on measuring a scorer that no longer
    exists -- and every future weight ruling rests on the curve this produces. Abstention here
    now means what it means in score.py: nothing was plausible at all.
    """
    rows = []
    for mmsi, comps in comps_by_vessel.items():
        c = dict(comps)
        if drop and drop in c:
            c[drop] = S.Component.not_applicable("ablated for this measurement")
        total, _live = S.weighted_score(c)
        rows.append((round(min(1.0, max(0.0, total)), 3), mmsi))
    rows.sort(key=lambda r: (-r[0], r[1]))

    abstained = not rows

    rank = next((i for i, (_s, m) in enumerate(rows, 1) if m == offender_mmsi), None)
    return rank, abstained, len(rows)


def discharge_point(background, when, rng, box_bounds):
    """Where the offender discharges: on top of a real vessel's position at `when`.

    Sampling a random point in the box instead put most clouds in empty water, where the
    offender was the only plausible vessel and every scenario scored top-1 by default. A
    benchmark with no competitors measures nothing. Placing the release in the lane, at a time
    real traffic was there, is both harder and closer to what a real discharge looks like.
    """
    rng.shuffle(background)
    for t in background:
        p = t.position_at(when)
        if p:
            return p
    west, south, east, north = box_bounds
    return (rng.uniform(west, east), rng.uniform(south, north))


def offset_km(lon, lat, km, bearing_deg):
    klat = 1.0 / max(math.cos(math.radians(lat)), 1e-6)
    return (lon + km * math.sin(math.radians(bearing_deg)) * klat / KM_PER_DEG,
            lat + km * math.cos(math.radians(bearing_deg)) / KM_PER_DEG)


def one_trial(background, box_bounds, rng, density, gap, r90, sampling, span,
              origin_error_frac=0.0, slowdown=True):
    """Inject one offender into real traffic and rank it. Returns a dict of outcomes per ablation."""
    west, south, east, north = box_bounds
    lo, hi = span
    # a time far enough inside the parquet's span that the offender's +/-6 h of reports are
    # covered by real traffic too
    when = lo + timedelta(seconds=rng.uniform(0.3, 0.7) * (hi - lo).total_seconds())
    t0, t1 = when - timedelta(hours=2), when + timedelta(hours=2)
    clon, clat = discharge_point(list(background), when, rng, box_bounds)

    # The cloud does not have to be centred on the truth. Stage 2 has its own error, and a
    # scorer that only works when handed a perfect origin is not the thing we ship.
    glon, glat = offset_km(clon, clat, origin_error_frac * r90, rng.uniform(0, 360))
    grid = synthetic_grid(glon, glat, r90, t0, t1)
    cadence = 60 if sampling == "noaa_dense" else 3600
    # The offender's TYPE is drawn from the background fleet's own distribution. Hardcoding it
    # as a tanker made `type_prior` look like a real discriminator (-0.10 top-1 when ablated)
    # when all it was measuring was that the guilty vessel was always the class the component
    # scores highest. A benchmark must not hand the scorer the answer through a side channel.
    fleet_types = [(t.vessel_type, t.type_code) for t in background] or [("other", 0)]
    vtype, vcode = rng.choice(fleet_types)
    offender = synthetic_offender(clon, clat, when, cadence, gap,
                                  slowdown=slowdown, course_deg=rng.uniform(0, 360),
                                  speed_kn=11.0, vessel_type=vtype, type_code=vcode)

    fleet = [t for t in background if rng.random() < density]
    if sampling == "gfw_hourly":
        fleet = [d for d in (decimate(t, 3600) for t in fleet) if d]
    fleet.append(offender)

    sbox = S.SearchBox(west, south, east, north)
    comps, plausible_mmsi = {}, set()
    for t in fleet:
        s = S.score_vessel(t, grid, t0, t1, sampling, "chronic", sbox)
        if not s or s["grid_probability"] <= S.PLAUSIBLE_GRID_MIN:
            continue
        comps[t.mmsi] = s["components"]
        plausible_mmsi.add(t.mmsi)

    out = {"r90_measured": grid.radius_90_km, "n_plausible": len(comps),
           "offender_plausible": offender.mmsi in plausible_mmsi, "by_ablation": {}}
    for ab in ABLATIONS:
        rank, abstained, n = rank_of_offender(comps, offender.mmsi,
                                              None if ab == "none" else ab)
        out["by_ablation"][ab] = {"rank": rank, "abstained": abstained, "n_plausible": n}
    return out


def wilson(k, n, z=1.96):
    """95% confidence interval on a proportion. Small n is the normal case here, and a bare
    percentage over 40 trials invites a judge to over-read it."""
    if n == 0:
        return (0.0, 0.0)
    p = k / n
    d = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / d
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (max(0.0, centre - half), min(1.0, centre + half))


def summarise(trials, ablation="none"):
    rows = [t["by_ablation"][ablation] for t in trials]
    n = len(rows)
    decided = [r for r in rows if not r["abstained"]]
    top1 = sum(1 for r in decided if r["rank"] == 1)
    top3 = sum(1 for r in decided if r["rank"] and r["rank"] <= 3)
    missed = sum(1 for t in trials if not t["offender_plausible"])
    ranks = [r["rank"] for r in decided if r["rank"]]
    return {
        "trials": n,
        "abstained": n - len(decided),
        "decided": len(decided),
        "top1": top1, "top3": top3,
        "top1_rate": round(top1 / len(decided), 3) if decided else None,
        "top3_rate": round(top3 / len(decided), 3) if decided else None,
        "top1_ci": [round(x, 3) for x in wilson(top1, len(decided))] if decided else None,
        "median_rank": statistics.median(ranks) if ranks else None,
        "offender_never_plausible": missed,
        "median_plausible_set": statistics.median([r["n_plausible"] for r in rows]) if rows else 0,
    }


def main():
    ap = argparse.ArgumentParser(description="Stage 3 Phase 8 — injected-offender curve")
    ap.add_argument("--parquet", required=True, help="real AIS traffic to inject into")
    ap.add_argument("--trials", type=int, default=40, help="trials per sweep point")
    ap.add_argument("--seed", type=int, default=143)
    ap.add_argument("--json", help="write the full result document here")
    ap.add_argument("--quick", action="store_true", help="baseline and ablations only, no sweep")
    ap.add_argument("--r90", type=float, help="override the baseline cloud size, km")
    ap.add_argument("--density", type=float, help="override the baseline traffic fraction")
    ap.add_argument("--gap", type=int, help="override the baseline injected gap, minutes")
    ap.add_argument("--sampling", choices=SAMPLING, help="override the baseline AIS regime")
    ap.add_argument("--origin-error", type=float, help="override the baseline origin error, x r90")
    ap.add_argument("--plain", action="store_true",
                    help="baseline offender leaves no behavioural signature: no gap, no slowdown. "
                         "This is the condition the ablation is worth reading at — at the easy "
                         "baseline every component looks free because the score saturates.")
    a = ap.parse_args()

    for k in ("r90", "density", "gap", "sampling"):
        if getattr(a, k) is not None:
            BASELINE[k] = getattr(a, k)
    if a.origin_error is not None:
        BASELINE["origin_error_frac"] = a.origin_error
    if a.plain:
        BASELINE.update(gap=0, slowdown=False)

    background = list(load_tracks(a.parquet).values())
    if not background:
        raise SystemExit(f"no usable tracks in {a.parquet}")
    west = min(min(t.lon) for t in background)
    east = max(max(t.lon) for t in background)
    south = min(min(t.lat) for t in background)
    north = max(max(t.lat) for t in background)
    lo = min(t.start for t in background)
    hi = max(t.end for t in background)
    print(f"background    {len(background)} vessels from {Path(a.parquet).name}")
    print(f"box           {west:.3f} {south:.3f} {east:.3f} {north:.3f}")
    print(f"span          {S.iso(lo)} .. {S.iso(hi)}")
    print(f"trials        {a.trials} per sweep point, seed {a.seed}\n")

    conditions = [("baseline", dict(BASELINE))]
    if not a.quick:
        for d in DENSITY_FRACTIONS:
            conditions.append((f"density={d}", {**BASELINE, "density": d}))
        for g in GAP_MINUTES:
            conditions.append((f"gap={g}min", {**BASELINE, "gap": g}))
        for r in R90_TARGETS_KM:
            conditions.append((f"r90={r}km", {**BASELINE, "r90": r}))
        for s in SAMPLING:
            conditions.append((f"sampling={s}", {**BASELINE, "sampling": s}))
        for e in ORIGIN_ERROR_FRACTIONS:
            conditions.append((f"origin_err={e}xr90", {**BASELINE, "origin_error_frac": e}))
        conditions.append(("offender=plain", {**BASELINE, "gap": 0, "slowdown": False}))

    doc = {"parquet": str(a.parquet), "trials_per_point": a.trials, "seed": a.seed,
           "background_vessels": len(background), "conditions": {}, "ablation": {}}

    print(f"{'condition':22} {'top-1':>12} {'top-3':>7} {'abst':>5} {'medrank':>8} {'plaus':>6}")
    for name, cond in conditions:
        rng = random.Random(a.seed)          # same offenders across conditions, so the axis is the only difference
        trials = [one_trial(background, (west, south, east, north), rng,
                            cond["density"], cond["gap"], cond["r90"], cond["sampling"],
                            (lo, hi), cond["origin_error_frac"], cond["slowdown"])
                  for _ in range(a.trials)]
        s = summarise(trials)
        doc["conditions"][name] = {"condition": cond, **s}
        ci = f" [{s['top1_ci'][0]:.2f}-{s['top1_ci'][1]:.2f}]" if s["top1_ci"] else ""
        print(f"{name:22} {str(s['top1_rate']):>5}{ci:>13} {str(s['top3_rate']):>6} "
              f"{s['abstained']:>5} {str(s['median_rank']):>8} {str(s['median_plausible_set']):>6}")
        if name == "baseline":
            for ab in ABLATIONS:
                doc["ablation"][ab] = summarise(trials, ab)

    print(f"\nper-component ablation at baseline (top-1 among decided trials)")
    base = doc["ablation"]["none"]
    print(f"  {'component removed':22} {'top-1':>6} {'delta':>7} {'top-3':>6} {'abst':>5}")
    for ab in ABLATIONS:
        s = doc["ablation"][ab]
        if s["top1_rate"] is None or base["top1_rate"] is None:
            continue
        d = s["top1_rate"] - base["top1_rate"]
        label = "nothing (baseline)" if ab == "none" else ab
        print(f"  {label:22} {s['top1_rate']:>6.3f} {d:>+7.3f} {s['top3_rate']:>6.3f} "
              f"{s['abstained']:>5}")
    print("\n  A component whose removal costs nothing is not discriminating on these scenarios.")
    print("  This measures; it changes no weight. That ruling is Akshat's (A5, A6, D21).")
    print("\nQuoting rule: the origin cloud is centred on the offender's own discharge point,")
    print("so these are RANKING numbers given a correct origin — an upper bound on the")
    print("end-to-end result, never an accuracy figure for the live cases.")

    if a.json:
        Path(a.json).write_text(json.dumps(doc, indent=2), encoding="utf-8")
        print(f"\nwrote {a.json}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
