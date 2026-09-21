#!/usr/bin/env python3
"""
Stage 3, step 3 — the scorer. Owner: Jaiveer.

Takes Anushka's origin cloud and my reconstructed AIS tracks, scores every vessel
that was in that patch of ocean during that window, and writes the two files the
Attribute screen is drawn from.

    python pipeline/attribute/score.py --case-dir pipeline/attribute/fixtures/case-gulf-fake \
           --parquet data/ais/gulf.parquet
    python pipeline/attribute/score.py --case case-huntington-2021 \
           --parquet data/ais/huntington.parquet

Writes `vessels.geojson` and `suspects.json` **into the case bundle**, so that
`python scripts/validate_case.py <case dir>` checks OUR output. The stub wrote to
`out/`, which is gitignored and which the validator never reads — the PASS in the
Phase 1 report was validating Akshat's committed fixture, not anything we produced.

NO MACHINE LEARNING. Every number on a suspect card traces to an arithmetic step
below, which is the point: a panel can be told exactly why a vessel ranked where it
did, and a classifier could not do that.

The three rules this file exists to honour
------------------------------------------
1. **Score the grid, not the circle** (D8). The real origin cloud is a 4.38:1 streak
   with 44.7% of its high-probability mass outside r50. Circle membership names
   vessels in near-empty water inside the circle and excludes vessels sitting in the
   bright streak just outside it.

2. **`null` is not `0`** (frozen convention 7). Every component returns
   `(score, applicable, note)`. Not-applicable contributes nothing and the remaining
   weights renormalise. A measured zero is a real statement about a vessel; a
   not-applicable is a statement about the data. Rendering one as the other is an
   honesty bug.

3. **Applicability is a stated rule, never a quiet conditional** (D9). Every gate
   below prints its reason into the suspect card, so what the scorer refused to
   measure is on screen rather than buried in an `if`.

Stdlib plus duckdb (via tracks.load_tracks). No new dependencies.
"""
import argparse
import json
import math
from datetime import datetime, timedelta, timezone
from pathlib import Path

import dark
import geo
from infrastructure import INFRA_SCORE_FLOOR, find_infrastructure
from tracks import load_tracks, regime

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]

# --------------------------------------------------------------------------- weights
# Named constants, deterministic, explainable. Master plan Part 6 / 06_JAIVEER_AIS B4.
# v4 moved 0.10 off proximity into parity and temporality: geometry and timing are
# stronger evidence than raw closeness.
W_PROXIMITY   = 0.30
W_PARITY      = 0.15
W_TEMPORALITY = 0.15
W_TRAJECTORY  = 0.15
W_GAP         = 0.15
W_SLOWDOWN    = 0.05
W_TYPE_PRIOR  = 0.05

WEIGHTS = {"proximity": W_PROXIMITY, "parity": W_PARITY, "temporality": W_TEMPORALITY,
           "trajectory": W_TRAJECTORY, "gap": W_GAP, "slowdown": W_SLOWDOWN,
           "type_prior": W_TYPE_PRIOR}

TYPE_PRIOR = {"tanker": 1.0, "cargo": 1.0, "fishing": 0.4, "passenger": 0.2, "other": 0.5}

# ----------------------------------------------------------------------- thresholds
PLAUSIBLE_GRID_MIN   = 0.05   # funnel: "touches non-negligible grid probability"
TRAJECTORY_CONE_DEG  = 60.0   # within +/- this of the bearing to the origin counts
GAP_MINUTES_MIN      = 30.0   # a silence worth calling a silence
UNDERWAY_KNOTS       = 2.0    # below this a vessel is moored or at anchor, not sailing
SLOWDOWN_FRACTION    = 0.40   # SOG must fall this far below the under-way median
SAMPLE_SECONDS       = 60     # walk each track at this cadence through the window
EDGE_DEGREES         = 0.02   # "on the search-box boundary", ~2 km

# ----------------------------------------------------------------------- abstention
ABSTAIN_SCORE_FLOOR  = 0.25   # nothing scores convincingly
ABSTAIN_TIE_FRACTION = 0.03   # top two indistinguishable
ABSTAIN_MAX_PLAUSIBLE_VESSELS = 40   # density too high to discriminate
# NOTE the collision the master plan has not resolved: the abstain trigger on cloud
# size is `radius_90_km > 40` (kilometres) and this one is 40 *vessels*. Two unrelated
# 40s. The one on this side of the fence is now named for what it counts; renaming the
# other is Akshat's call, since it comes from the plan and not from this file.

TOP_N = 3
MAX_EXCLUSIONS = 3


def parse_ts(s):
    dt = datetime.fromisoformat(str(s).replace("Z", "+00:00"))
    if dt.tzinfo is None:
        raise SystemExit(f"'{s}' is timezone-naive — every timestamp needs the trailing Z")
    return dt.astimezone(timezone.utc)


def iso(dt):
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def r5(x):
    return round(float(x), 5)


class Component:
    """One scoring signal. `applicable=False` means we could not measure it at all —
    which is different from measuring it and getting zero, and the difference reaches
    the suspect card as `null` versus `0`."""

    __slots__ = ("value", "applicable", "note")

    def __init__(self, value=None, applicable=True, note=""):
        self.applicable = applicable and value is not None
        self.value = float(value) if self.applicable else None
        self.note = note

    @classmethod
    def not_applicable(cls, why):
        return cls(None, False, why)


# ---------------------------------------------------------------------- the components

def component_proximity(track, grid, t0, t1, ais_source="noaa_dense"):
    """Highest origin-grid probability the vessel touched during the window.

    The grid is normalised to peak 1.0, so the sample IS the score — no scaling.
    Returns the score plus where and when it happened, because the suspect card
    quotes both and the checkpoint plot marks the point.

    Walking the track at a fixed cadence rather than only at its reports, because on
    a `gfw_hourly` case the reports are an hour apart. `position_at` refuses to
    interpolate across a silence longer than 30 minutes, so this never invents a
    position — it just fills in where the transponder was actually talking.

    The ceiling is per sampling regime (D41, `tracks.REGIME`): on `gfw_hourly` it joins
    consecutive hourly fixes, and the note says so when the peak came from between two.
    """
    max_gap = regime(ais_source)["max_interp_gap_min"]
    best = (0.0, None, None, False)
    for i, ts in enumerate(track.ts):
        if t0 <= ts <= t1:
            p = grid.sample(track.lon[i], track.lat[i])
            if p > best[0]:
                best = (p, ts, (track.lon[i], track.lat[i]), False)

    walk_from = max(t0, track.start)
    span = (min(t1, track.end) - walk_from).total_seconds()
    for k in range(1, int(span // SAMPLE_SECONDS) + 1):
        when = walk_from + timedelta(seconds=k * SAMPLE_SECONDS)
        pos = track.position_at(when, max_gap)
        if pos is None:          # a silence longer than the interpolation ceiling
            continue
        p = grid.sample(pos[0], pos[1])
        if p > best[0]:
            best = (p, when, pos, True)

    value, when, pos, interpolated = best
    if when is None:
        return Component.not_applicable("no AIS reports inside the origin time window"), None
    note = "origin-grid probability at closest approach"
    if interpolated and ais_source == "gfw_hourly":
        note += (" — position between two hourly fixes, linearly interpolated; the vessel's "
                 "actual path between fixes is not observed")
    return Component(value, note=note), (when, pos)


def component_trajectory(track, grid, when, pos, ais_source="noaa_dense"):
    """Was the vessel heading in a way consistent with being the source?

    MEASURED AT THE APPROACH, NOT AT CLOSEST APPROACH — and that is a correctness fix,
    not a preference. 06_JAIVEER_AIS 1.5 says to compare course over ground against the
    bearing to the origin *at closest approach*. Run against the Galveston fleet that
    scores **0 for 16 of 17 vessels, median 126 degrees off**, and it is not the data's
    fault: at the point of closest approach the line to the origin is by construction
    roughly perpendicular to your course, so the +/-60 cone can essentially never be
    satisfied. The component was structurally incapable of firing.

    So the test is applied where it means something: at the **last report before closest
    approach at which the vessel was still outside `radius_90_km`** — was it, from out
    there, heading in? That is scale-free across cases with different cloud sizes, and
    it is the same class of change as D9's gating: it defines *where* a component is
    measured, not how much it counts.

    HONEST CAVEAT, and it is on the limitations slide. Corrected this way the component
    scores 1 for 13 of 15 vessels (median 25 degrees off), because any vessel that ended
    up inside the cloud was, by definition, heading toward it beforehand. It is close to
    tautological on a transiting-vessel case and carries little information for 15% of
    the weight. The component that actually separates a source from a passer-by is
    **parity** — did the track run *along* the slick or *across* it — which is Phase 2
    and waits on Soumirya's polygon. Raised with Akshat; the weight is his call and Phase 8's
    measurement, never a silent edit here.

    COG 360.0 is AIS for 'not available'. `ingest.py` nulls it; here that null means
    **not applicable**, never 'due north'.
    """
    clon, clat = grid.centroid
    idx = None
    for i, ts in enumerate(track.ts):
        if ts > when:
            break
        if geo.haversine_km(track.lon[i], track.lat[i], clon, clat) >= grid.radius_90_km:
            idx = i

    if idx is None:
        return Component.not_applicable(
            f"vessel was never outside the {grid.radius_90_km:.0f} km origin radius before "
            "closest approach, so it has no approach direction to assess")
    cog = track.cog[idx]
    if cog is None:
        # D29: the note has to be TRUE, not merely present. On an hourly-presence source COG is
        # not published at all, so calling it an "AIS sentinel" (a vessel broadcasting 360) says
        # the transponder reported something it never reported. Measured: every card on
        # case-mumbai-2023 carries the sentinel wording today, and none of them is a sentinel.
        if ais_source == "gfw_hourly":
            return Component.not_applicable(
                "course over ground is not published by the hourly presence source, and a "
                "course derived from two 1 km cell centres an hour apart is not a measurement")
        return Component.not_applicable(
            "course over ground unavailable on approach (AIS sentinel)")

    to_origin = geo.bearing_deg(track.lon[idx], track.lat[idx], clon, clat)
    off = geo.angular_difference_deg(cog, to_origin)
    km = geo.haversine_km(track.lon[idx], track.lat[idx], clon, clat)
    return Component(1.0 if off <= TRAJECTORY_CONE_DEG else 0.0,
                     note=f"on approach {km:.0f} km out, course {cog:.0f} deg against "
                          f"{to_origin:.0f} deg toward the origin ({off:.0f} deg off)")


def component_gap(track, t0, t1, ais_source, box):
    """A transponder silence overlapping the release window.

    Three gates, each of them a measured rule rather than a hunch:

    * `gfw_hourly` — one position per vessel per hour. A 30-minute silence is
      **structurally invisible** at that sampling, so the answer is `null`, never a
      zero that reads as 'we looked and there was nothing' (D20).

    * **Under way on both sides.** 64% of gap hits in the Galveston fleet are docked
      boats whose transponder idled overnight. The worst gap in that dataset, 996
      minutes, belongs to a vessel averaging 0.01 knots. It never moved (D9).

    * **Not at the search-box boundary.** Measured on the Menuett box: 5 of 11
      under-way silences were vessels sailing out of the rectangle and back in, one
      of them apparently dark for 23 hours, resuming exactly on the edge. Leaving the
      box is not going dark, and the under-way test does not catch it because they
      were under way on both sides.
    """
    if ais_source == "gfw_hourly":
        return Component.not_applicable(
            "AIS source is hourly — a 30-minute silence cannot be observed")

    best, best_i = 0.0, None
    for i in range(len(track.ts) - 1):
        a, b = track.ts[i], track.ts[i + 1]
        if not (a < t1 and b > t0):
            continue
        mins = (b - a).total_seconds() / 60.0
        if mins > best:
            best, best_i = mins, i
    if best_i is None:
        return Component(0.0, note="continuous coverage through the window")

    sa, sb = track.sog[best_i], track.sog[best_i + 1]
    if sa is None or sb is None or sa < UNDERWAY_KNOTS or sb < UNDERWAY_KNOTS:
        return Component.not_applicable(
            f"{best:.0f}-minute silence, but the vessel was not under way on both sides "
            "of it — moored, not dark")

    if box and box.on_edge(track.lon[best_i], track.lat[best_i]):
        return Component.not_applicable(
            f"{best:.0f}-minute silence begins on the search-box boundary — the vessel "
            "left the search area and returned, which is not a transponder gap")

    return Component(1.0 if best >= GAP_MINUTES_MIN else 0.0,
                     note=f"longest silence overlapping the window: {best:.0f} minutes")


def component_slowdown(track, when, ais_source):
    """An unusual slowdown near the origin — a vessel stopping to do something.

    Compared against an **under-way median** that excludes hours at rest. The v1 spec
    compared against the vessel's own overall median, which is exactly 0.0 for 66% of
    the fleet, so the test was unreachable by construction: you cannot go slower than
    stopped (D9).
    """
    if ais_source == "gfw_hourly":
        return Component.not_applicable(
            "speed over ground is not published by the hourly presence source; a speed "
            "derived from 1 km cell centres an hour apart is not a measurement")
    underway = sorted(s for s in track.sog if s is not None and s >= UNDERWAY_KNOTS)
    if len(underway) < 3:
        return Component.not_applicable(
            "vessel was never meaningfully under way, so there is no cruising speed "
            "to have slowed down from")
    n = len(underway)
    med = underway[n // 2] if n % 2 else (underway[n // 2 - 1] + underway[n // 2]) / 2.0
    i = min(range(len(track.ts)), key=lambda j: abs((track.ts[j] - when).total_seconds()))
    sog = track.sog[i]
    if sog is None:
        return Component.not_applicable("speed unavailable at closest approach (AIS sentinel)")
    dropped = sog <= med * (1.0 - SLOWDOWN_FRACTION)
    return Component(1.0 if dropped else 0.0,
                     note=f"{sog:.1f} kn at closest approach against an under-way median "
                          f"of {med:.1f} kn")


def component_temporality(track, when, grid):
    """How close in time the vessel's closest approach is to the release window.

    Gated on `time_window_method`. Master plan 6.5 is explicit that `bounded` means a
    **search bracket, not a measured release time** — every vessel present in the
    bracket then scores much the same and the number says nothing. Scoring against a
    non-measurement is worse than declining to score, so `bounded` returns `null`.

    Phase 2 replaces this with Cerulean's version: the timestamp of the broadcast
    spatially nearest the *head* of the slick. That needs Soumirya's polygon.
    """
    # "age" (Stage 2 age engine v2, Master 6.5, 16 Sept 2026) is a MEASURED window too -- the
    # 80 % interval of the slick's own age posterior -- and a stronger claim than
    # "convergence". Leaving it out of this set would silently drop temporality on every
    # case the age engine dates.
    if grid.time_window_method not in ("convergence", "age"):
        return Component.not_applicable(
            f"origin time window is a search bracket, not a measured release time "
            f"(time_window_method={grid.time_window_method!r})")
    t0, t1 = (parse_ts(t) for t in grid.time_window)
    half = max((t1 - t0).total_seconds() / 2.0, 1.0)
    mid = t0 + (t1 - t0) / 2
    off = abs((when - mid).total_seconds())
    return Component(max(0.0, 1.0 - off / half),
                     note=f"closest approach {off / 3600:.1f} h from the centre of the "
                          "release window")


def component_parity(discharge_class):
    """Track/slick parallelism — Cerulean's strongest idea, and Phase 2 work.

    Chronic only: a blob has no meaningful centerline to be parallel to. Needs Soumirya's
    slick polygon, so until Phase 2 lands this is honestly not applicable rather than
    quietly zero.
    """
    if discharge_class != "chronic":
        return Component.not_applicable(
            f"slick is {discharge_class or 'unclassified'} — parity needs a linear "
            "slick with a centerline")
    return Component.not_applicable(
        "parity requires the slick centerline from Stage 1 (Phase 2, not yet built)")


def component_type_prior(vessel_type):
    """A small head start by vessel class. 5% — deliberately the smallest weight,
    because it is a prior about categories and not evidence about this vessel.

    Known limitation, measured and stated: 41.6% of the Galveston fleet are tugs and
    tows and they all land in `other` at 0.5. AIS type 31 says a vessel is towing, not
    what it is towing, so we cannot separate an oil barge from a gravel barge and we
    do not pretend to.
    """
    return Component(TYPE_PRIOR.get(vessel_type, 0.5),
                     note=f"vessel type {vessel_type or 'unknown'}")


# --------------------------------------------------------------------------- the box

class SearchBox:
    """The rectangle the AIS was filtered to. Derived from the extract itself, so it
    is always the real boundary rather than whatever was typed on the command line."""

    def __init__(self, west, south, east, north):
        self.west, self.south, self.east, self.north = west, south, east, north

    def on_edge(self, lon, lat, tol=EDGE_DEGREES):
        return (abs(lon - self.west) <= tol or abs(lon - self.east) <= tol or
                abs(lat - self.south) <= tol or abs(lat - self.north) <= tol)


# ------------------------------------------------------------------------- scoring

def weighted_score(comps):
    """(score, live_weight) over the applicable components only.

    Renormalise across what could actually be measured. A component we could not measure
    must not silently drag the score toward zero (D9).
    """
    live = sum(WEIGHTS[k] for k, c in comps.items() if c.applicable)
    total = (sum(WEIGHTS[k] * c.value for k, c in comps.items() if c.applicable) / live
             if live > 0 else 0.0)
    return total, live


def rescore(s):
    """Recompute score and weight_live from the components, in place.

    Used after a gate is applied post-ranking. Identical arithmetic to `score_vessel` -- if these
    two ever disagree the cards stop matching the ranking, so they stay in this file together
    rather than drifting apart. (Jaiveer's helper, merged from jaiveer-phase2.)
    """
    total, live = weighted_score(s["components"])
    s["score"] = round(min(1.0, max(0.0, total)), 3)
    s["weight_live"] = round(live, 3)
    return s


def gate_constant_components(scored, names=("type_prior",)):
    """D28: a component holding the SAME value for every scored candidate gates to `null`.

    It separates nobody, so all it does is add its full weight to every score on screen.
    `type_prior` is the case this was ruled for — it returned 1.00 for all 17 vessels in an
    offshore lane, and on Farallones 1.00 for all three (a tanker and two cargo ships both map
    to 1.0, so the gate is on the VALUE, not on the type string; that is also what the
    validator checks).

    Removing a constant is rank-preserving: every score becomes (S - w·c)/(1 - w), which is
    monotonic in S. So this changes what the cards claim, never who is on them. Scores are
    recomputed in place. Needs at least two scored candidates — one vessel cannot be constant.
    """
    if len(scored) < 2:
        return []
    gated = []
    for name in names:
        vals = [s["components"][name] for s in scored]
        if not all(c.applicable for c in vals):
            continue
        if len({round(c.value, 6) for c in vals}) != 1:
            continue
        for s in scored:
            s["components"][name] = Component.not_applicable(
                f"every scored candidate scores {vals[0].value:g} here, so it separates "
                f"nobody and is not counted (D28)")
            rescore(s)
        gated.append(name)
    return gated


def score_vessel(track, grid, t0, t1, ais_source, discharge_class, box):
    """All seven components for one vessel, then the renormalised weighted sum."""
    prox, approach = component_proximity(track, grid, t0, t1, ais_source)
    if approach is None:
        return None
    when, pos = approach

    comps = {
        "proximity": prox,
        "parity": component_parity(discharge_class),
        "temporality": component_temporality(track, when, grid),
        "trajectory": component_trajectory(track, grid, when, pos, ais_source),
        "gap": component_gap(track, t0, t1, ais_source, box),
        "slowdown": component_slowdown(track, when, ais_source),
        "type_prior": component_type_prior(track.vessel_type),
    }

    total, live = weighted_score(comps)

    return {
        "track": track,
        "components": comps,
        "score": round(min(1.0, max(0.0, total)), 3),
        "weight_live": round(live, 3),
        "closest_time": when,
        "closest_pos": pos,
        # D36: measured to the grid peak, not origin.centroid — on an elongated
        # cloud the two can be far apart (Jacksonville: peak 10.65 km off centroid),
        # and a vessel sitting on the peak should not read as "10 km away".
        "closest_km": round(geo.haversine_km(pos[0], pos[1], *grid.peak_lonlat()), 2),
        "grid_probability": round(prox.value, 3) if prox.applicable else 0.0,
        "edge_truncated": bool(box and box.on_edge(pos[0], pos[1])),
        "gap_minutes": track.gap_overlapping(t0, t1),
    }


def reasons_for(s):
    """1-3 short plain-language strings for a judge-facing card, generated from
    whichever components actually fired. These go on screen, so they say what was
    measured — including what could not be."""
    out, c = [], s["components"]
    p = c["proximity"]
    if p.applicable:
        if p.value >= 0.6:
            out.append("inside the high-probability region of the reconstructed origin "
                       "during the release window")
        elif p.value >= PLAUSIBLE_GRID_MIN:
            out.append("on the edge of the reconstructed origin during the release window")
    if c["gap"].applicable and c["gap"].value > 0:
        out.append(f"{s['gap_minutes']:.0f}-minute transponder gap overlapping the window")
    if c["trajectory"].applicable and c["trajectory"].value > 0:
        out.append(f"{s['track'].vessel_type} on a course consistent with the origin")
    if c["slowdown"].applicable and c["slowdown"].value > 0:
        out.append("unusual slowdown at closest approach")
    if s["edge_truncated"]:
        out.append("track truncated at the search boundary — closest approach may be "
                   "understated")
    if not out:
        out.append("present in the search area during the window; no component scored")
    return out[:4]


def rank_key(s):
    """A TOTAL order on scored candidates, so the same inputs name the same vessels.

    `plausible.sort(key=score)` alone is not deterministic. `tracks.load_tracks` groups by
    MMSI in DuckDB, whose GROUP BY makes no ordering guarantee and parallelises, so the
    input order varies between runs on identical data. Python's sort is stable, which
    faithfully preserves that arbitrary order -- and on an hourly case, where the D28 gate
    strips `type_prior` and leaves score == proximity, exact ties are the norm rather than
    the exception.

    Measured on case-mumbai-2023, 2026-09-22: three consecutive runs over an unchanged
    parquet named three DIFFERENT pairs of vessels at rank 2 and 3 -- LISA / MSC MADELEINE,
    then MSC MADELEINE / GENIUS ACE, then LISA / GENIUS ACE, all tied at exactly 0.781. We
    were naming real vessels as pollution suspects and which ones got named was chance.

    Every term is a number already on the card, and the order is "more evidence first, then
    the primary evidence, then distance". MMSI last is the deterministic backstop: arbitrary,
    but stated and stable, which an unstated arbitrary order is not.
    """
    return (-s["score"],
            -(s.get("weight_live") or 0.0),
            -sum(1 for c in s["components"].values() if c.applicable),
            -(s.get("grid_probability") or 0.0),
            s["closest_km"] if s.get("closest_km") is not None else float("inf"),
            s["track"].mmsi)


def exclusion_reason(s):
    """A stated disqualifying reason, or None if there is no clean one. An exclusion
    without a reason is worse than no exclusion — the validator rejects an empty
    string and so should we."""
    c = s["components"]
    if c["trajectory"].applicable and c["trajectory"].value == 0:
        return "heading away from the origin throughout the window"
    if c["gap"].applicable and c["gap"].value == 0 and c["proximity"].value < 0.3:
        # Lead with the measured reason, not the absence. "No transponder gap" reads as an
        # exoneration, and it is the weaker half of this test: what actually disqualifies the
        # vessel is that it never reached the origin. Stating the absence first also becomes
        # wrong under a merged AIS pool, where a vessel can have no gap MEASUREMENT at all
        # rather than a measured absence of one.
        return (f"never reached the high-probability region (peak grid probability "
                f"{c['proximity'].value:.2f}), and broadcast continuously while under way")
    if c["proximity"].applicable and c["proximity"].value < 0.15:
        return (f"never entered the high-probability region of the origin "
                f"(peak grid probability {c['proximity'].value:.2f})")
    return None


# ---------------------------------------------------------------------------- output

TRACK_PAD_HOURS = 1.0


def clipped_feature(track, t0, t1, pad_hours=TRACK_PAD_HOURS):
    """A `vessels.geojson` Feature holding only the part of the track inside the
    release window (padded), decimated per contract 6.6.

    `n_points` stays the **undecimated count of the clipped span**, and a
    `n_points_full` field records the whole track, so nothing about how much data
    stands behind the line is hidden by either the clip or the decimation.
    """
    a = t0 - timedelta(hours=pad_hours)
    b = t1 + timedelta(hours=pad_hours)
    idx = [i for i, ts in enumerate(track.ts) if a <= ts <= b]
    if len(idx) < 2:                      # keep it a valid LineString
        idx = list(range(min(2, len(track.ts))))
    n = len(idx)
    keep = idx if n <= 500 else [idx[round(k * (n - 1) / 499)] for k in range(500)]
    seen, ordered = set(), []
    for i in keep:
        if i not in seen:
            seen.add(i)
            ordered.append(i)
    return {
        "type": "Feature",
        "geometry": {"type": "LineString",
                     "coordinates": [[r5(track.lon[i]), r5(track.lat[i])] for i in ordered]},
        "properties": {
            "mmsi": track.mmsi,
            "name": track.name or "",
            "vessel_type": track.vessel_type,
            "n_points": n,
            "n_points_full": len(track.ts),
            "max_gap_minutes": track.max_gap_minutes,
        },
    }


def build_outputs(scored, funnel, grid, abstained, abstain_reason):
    """`suspects.json` per 6.7 — including `component_notes` (D29) and `weight_live` /
    `components_available` / `components_total` (D37), blessed into the schema 14 Sept.

    All four exist for the same reason: **the score alone does not say how much evidence
    stands behind it.**

    When components are not applicable their weight is redistributed across the rest
    (D9). That is the honest way to handle missing data, but the number that comes out
    the other side looks identical whether it rested on seven signals or two. Measured
    on a `gfw_hourly` fixture: a vessel scored **0.981 with a live weight of 0.35** —
    proximity and type_prior only, five components unmeasurable. A card rendering
    "0.98" with no caveat overstates that by a wide margin, and on the two `gfw_hourly`
    cases it is the normal state rather than an edge case.

    Emitting the numbers is not the fix — the fix is what the card shows, which is
    Akshat's ruling and Harshita's layout. The data was worth shipping ahead of the
    ruling so neither of them had to wait on it.
    """
    suspects = []
    for s in scored:
        t = s["track"]
        applicable = sum(1 for c in s["components"].values() if c.applicable)
        suspects.append({
            "source_type": "vessel",
            "mmsi": t.mmsi,
            "name": t.name or "",
            "vessel_type": t.vessel_type,
            "score": s["score"],
            "components": {k: (round(c.value, 3) if c.applicable else None)
                           for k, c in s["components"].items()},
            "component_notes": {k: c.note for k, c in s["components"].items()},
            "weight_live": s["weight_live"],
            "components_available": applicable,
            "components_total": len(WEIGHTS),
            "closest_km": s["closest_km"],
            "closest_time": iso(s["closest_time"]),
            "grid_probability": s["grid_probability"],
            "heading_consistent": bool(s["components"]["trajectory"].applicable and
                                       s["components"]["trajectory"].value > 0),
            "ais_gap_minutes": s["gap_minutes"],
            "edge_truncated": s["edge_truncated"],
            "reasons": reasons_for(s),
        })
    return {
        "funnel": funnel,
        "suspects": suspects,
        "dark_vessels": [],
        "infrastructure": [],
        "excluded": [],
        "abstained": abstained,
        "abstain_reason": abstain_reason,
    }


def main():
    ap = argparse.ArgumentParser(description="Stage 3 — score vessels against an origin cloud")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--case", help="case id under cases/")
    g.add_argument("--case-dir", help="explicit path to a case bundle")
    ap.add_argument("--parquet", help="output of ingest.py")
    ap.add_argument("--no-ais", action="store_true",
                    help="run without any AIS at all: fixed-source association only. For a "
                         "case in a region no AIS archive we hold covers. Must be passed "
                         "deliberately — it is never inferred from a missing --parquet, "
                         "because a forgotten argument would otherwise silently produce a "
                         "bundle that had considered no vessels.")
    ap.add_argument("--scene-parquet",
                    help="AIS extract over the scene footprint at acquisition time; enables the "
                         "radar-versus-AIS dark-vessel cross-check (dark.py)")
    ap.add_argument("--sar-contacts",
                    help="external radar contacts (ingest_gfw_sar.py output), cross-checked "
                         "like our own and labelled external on every card")
    ap.add_argument("--sar-label", default="GFW SAR vessel detections",
                    help="source named on cards for --sar-contacts")
    ap.add_argument("--out-dir", help="where to write (default: the case bundle itself)")
    ap.add_argument("--top", type=int, default=TOP_N)
    ap.add_argument("--ranking", action="store_true",
                    help="print the full scored ranking, including when we abstain. "
                         "Diagnostics only — it never changes what is written.")
    a = ap.parse_args()

    if bool(a.parquet) == bool(a.no_ais):
        raise SystemExit(
            "pass exactly one of --parquet or --no-ais.\n"
            "  --parquet is the normal path. --no-ais says, deliberately and on the record,\n"
            "  that no AIS archive covers this region, so no vessel can be considered at all.")

    case_dir = Path(a.case_dir) if a.case_dir else REPO / "cases" / a.case
    if not case_dir.is_dir():
        raise SystemExit(f"{case_dir} is not a directory")
    out_dir = Path(a.out_dir) if a.out_dir else case_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    grid = geo.OriginGrid.load(case_dir / "origin.json")
    meta = json.loads((case_dir / "meta.json").read_text(encoding="utf-8"))
    ais_source = meta.get("ais_source")
    if ais_source not in ("noaa_dense", "gfw_hourly"):
        raise SystemExit(
            f"meta.json/ais_source is {ais_source!r}; it is required on every case with "
            "`attribute` and decides which components can fire at all (D20). "
            "Expected 'noaa_dense' or 'gfw_hourly'.")

    discharge_class = None
    detections_doc = {}
    det_path = case_dir / "detections.geojson"
    if det_path.exists():
        detections_doc = json.loads(det_path.read_text(encoding="utf-8"))
        for f in detections_doc.get("features", []):
            if (f.get("properties") or {}).get("classification") == "oil":
                discharge_class = f["properties"].get("discharge_class")
                break

    t0, t1 = (parse_ts(t) for t in grid.time_window)
    print(f"case          {case_dir}")
    print(f"origin        {grid}")
    print(f"window        {iso(t0)} .. {iso(t1)}")
    print(f"ais_source    {ais_source}    discharge_class {discharge_class or '(none)'}")

    if a.no_ais:
        # ------------------------------------------------- no AIS archive for this region
        # Mumbai and Jamnagar sit outside NOAA Marine Cadastre, and Gulf of Alaska turns out
        # to as well — every NOAA daily file stops near 50 N. Without an AIS source there is
        # no vessel to consider, but the fixed-source and slick geometry are untouched by
        # that, so Phase 4 still has everything it needs.
        #
        # The funnel goes to zeros because the validator compares the four counts and needs
        # integers; nulls would not survive the monotonic check. That makes the counts the
        # one place in this file where a zero is doing a null's job, so the claim is stated
        # in `abstain_reason` instead, in words, where nothing can round it off: the counts
        # are zero because nothing was searched, NOT because the water was empty. Do not let
        # a card render "0 vessels in region" without that sentence next to it.
        tracks, in_window, plausible, near_miss, silent = {}, [], [], [], []
        in_region = dropped_short = 0
        box = None
        searched_empty = False
    else:
        in_window, plausible, near_miss, silent = [], [], [], []
        rg = regime(ais_source)
        tracks = load_tracks(a.parquet, rg["min_points"])

        import duckdb
        con = duckdb.connect()
        n_all, west, east, south, north = con.execute(
            "SELECT count(DISTINCT mmsi), min(lon), max(lon), min(lat), max(lat) "
            "FROM read_parquet(?)", [str(a.parquet)]).fetchone()
        con.close()
        # An empty extract is a searched negative (`ingest_gfw.py --allow-empty`): the query
        # ran and the water held no broadcasting vessel. That is a different sentence from
        # --no-ais, and the abstention below says which one it is.
        searched_empty = n_all == 0
        box = SearchBox(west, south, east, north) if not searched_empty else None

        in_region = n_all
        dropped_short = n_all - len(tracks)

        for t in tracks.values():
            if t.end < t0 or t.start > t1:
                continue
            in_window.append(t)

        for t in in_window:
            s = score_vessel(t, grid, t0, t1, ais_source, discharge_class, box)
            if not s:
                # Jaiveer's case (jaiveer-phase2, merged 14 Sept): score_vessel returns None
                # when the vessel never touched non-zero origin probability. Those vessels were
                # dropped silently, which is why three real cases shipped zero exclusions.
                silent.append(t)
                continue
            if s["grid_probability"] > PLAUSIBLE_GRID_MIN:
                plausible.append(s)
            else:
                # Scored, but it never touched non-negligible origin probability. These are
                # the honest exclusions: the funnel dropped them for a stated, measured
                # reason. Before this they were discarded here, so `excluded[]` could only
                # ever hold plausible-but-unranked vessels -- and it came out empty on every
                # real case, because every plausible vessel was also scored onto a card.
                near_miss.append(s)

        plausible.sort(key=rank_key)
        near_miss.sort(key=lambda s: (-(s["grid_probability"] or 0.0),
                                      s["track"].mmsi))
        gated = gate_constant_components(plausible)
        if gated:
            plausible.sort(key=rank_key)
            print(f"[gate]  {', '.join(gated)} is constant across all "
                  f"{len(plausible)} scored candidates -> null (D28)")

    # ------------------------------------------------------------------- abstention
    abstained, why = False, None
    if a.no_ais:
        abstained, why = True, (
            f"no AIS archive we hold covers this region, so no vessel was considered — the "
            f"funnel counts are zero because nothing was searched, not because the water was "
            f"empty. meta.json declares ais_source {ais_source!r}; that data was not "
            f"obtainable for this case. Fixed-source association is unaffected and is "
            f"reported below.")
    elif searched_empty:
        abstained, why = True, (
            f"the AIS archive ({ais_source}) was queried for the padded origin box and window "
            f"and returned no broadcasting vessel at all — the area was searched and found "
            f"empty, which is a result, not a missing input. Any vessel present was not "
            f"transmitting AIS.")
    elif grid.abstain:
        abstained, why = True, ("Stage 2 flagged the origin cloud as too diffuse to "
                                "attribute at acceptable confidence")
    elif len(plausible) > ABSTAIN_MAX_PLAUSIBLE_VESSELS:
        abstained, why = True, (f"{len(plausible)} vessels are plausible; above "
                                f"{ABSTAIN_MAX_PLAUSIBLE_VESSELS} the search area is too "
                                "crowded to discriminate between them")
    elif not plausible:
        abstained, why = True, "no vessel entered the reconstructed origin during the window"
    elif plausible[0]["score"] < ABSTAIN_SCORE_FLOOR:
        abstained, why = True, (f"the best score is {plausible[0]['score']:.2f}, below the "
                                f"{ABSTAIN_SCORE_FLOOR} floor for naming a vessel")
    elif (len(plausible) > 1 and
          plausible[0]["score"] - plausible[1]["score"] <
          ABSTAIN_TIE_FRACTION * max(plausible[0]["score"], 1e-9)):
        abstained, why = True, ("the top two vessels score within a few percent of each "
                                "other and cannot be separated on this evidence")

    top = [] if abstained else plausible[:a.top]

    funnel = {
        "in_region": in_region,
        "in_window": len(in_window),
        "plausible": len(plausible),
        # scored is 0 when we abstain: the validator enforces scored == len(suspects),
        # and `3 suspects, none listed` would read as a bug rather than a refusal.
        "scored": len(top),
        "dropped_short_track": dropped_short,
    }

    doc = build_outputs(top, funnel, grid, abstained, why)

    # ---------------------------------------------------------------- fixed infrastructure
    # Phase 4. This runs regardless of whether we abstained on vessels, and deliberately so:
    # abstention says "these ships cannot be separated", which is not the same claim as "no
    # vessel did it" and says nothing at all about a pipeline. Huntington is the case that
    # makes the difference concrete — the scorer refuses to separate its top two vessels, and
    # the correct finding there is still a fixed source.
    best_vessel = plausible[0]["score"] if plausible else None
    infra, infra_diag = find_infrastructure(meta, detections_doc, grid, best_vessel)
    doc["infrastructure"] = infra

    # -------------------------------------------------------------------- exclusions
    # Plausible-but-unranked first (they competed and lost), then the near misses in
    # descending grid probability (they were dropped by the funnel). Both carry a measured
    # reason or they are not listed at all -- an exclusion without one is worse than none.
    pool = (plausible[len(top):] if not abstained else list(plausible)) + near_miss
    for s in pool:
        # A vessel that was SCORED and ranked below the cut was not disqualified by anything
        # about itself -- it competed and lost. exclusion_reason() describes disqualification,
        # so letting it run first here labels a ranked-but-unnamed vessel as excluded for a
        # property it shares with the vessels we did name. The competed-and-lost sentence wins
        # unconditionally for anything in `plausible`; exclusion_reason() applies to near
        # misses, which really were dropped by the funnel.
        ranked_and_beaten = s in plausible and not abstained
        r = None if ranked_and_beaten else exclusion_reason(s)
        if ranked_and_beaten:
            lead = top[0]["score"] if top else 0.0
            r = (f"scored {s['score']:.2f} against {lead:.2f} for the leading candidate on the "
                 f"same {sum(1 for c in s['components'].values() if c.applicable)} components "
                 f"-- considered and ranked below the top {len(top)}, not excluded")
        if not r and abstained and s in plausible:
            # On an abstention the plausible vessels are not excluded for anything about
            # themselves: they are the nearest candidates, and they are not named because the
            # evidence cannot separate them. Say exactly that, with the measured numbers, so an
            # abstention shows who was considered rather than a blank.
            r = (f"plausible candidate — score {s['score']:.2f} on "
                 f"{sum(1 for c in s['components'].values() if c.applicable)} of {len(WEIGHTS)} "
                 f"components, peak grid probability {s['grid_probability']:.2f} — not named "
                 f"because {why}")
        if r:
            doc["excluded"].append({
                "mmsi": s["track"].mmsi,
                "name": s["track"].name or "",
                "closest_km": s["closest_km"],
                "reason": r,
            })
        if len(doc["excluded"]) >= MAX_EXCLUSIONS:
            break

    # Last, the vessels the scorer could not score at all. `score_vessel` returns None when the
    # vessel never touched NON-ZERO origin probability, which is two different situations, and
    # they need two different sentences. Jaiveer's branch said "no AIS position report inside the
    # release window" for all of them; measured against the real extracts that is false almost
    # everywhere -- 0 of 23 on Jacksonville, 1 of 65 on Huntington, and Farallones' NAVAJO has
    # 138 reports inside the window. Saying a ship was absent when it was present all along, on a
    # judge-facing card, is the kind of claim this project exists not to make.
    #
    # Ordering is nearest-to-the-peak first, then MMSI. There are 23 and 65 of these on the two
    # US cases against MAX_EXCLUSIONS of 3, so without a stated order which three appear depended
    # on dict iteration order, and two runs of the same data named different ships -- that is how
    # our list and Jaiveer's came out different. Nearest-first also puts the most interesting
    # exclusion on the card: the ship that got closest and still did not do it.
    def _silence(track):
        idx = [i for i, ts in enumerate(track.ts) if t0 <= ts <= t1]
        if not idx:
            return None, 0
        pk = grid.peak_lonlat()
        return min(geo.haversine_km(track.lon[i], track.lat[i], *pk) for i in idx), len(idx)

    measured = []
    for t in silent:
        km, n = _silence(t)
        measured.append((km if km is not None else float("inf"), t.mmsi, t, km, n))
    measured.sort(key=lambda r: (r[0], r[1]))

    for _key, _mmsi, t, km, n in measured:
        if len(doc["excluded"]) >= MAX_EXCLUSIONS:
            break
        if n == 0:
            # Genuinely absent: nothing to measure, so closest_km is null, not a number.
            reason = ("no AIS position report inside the release window — the track enters or "
                      "leaves the search box either side of it")
            km = None
        else:
            # Present and broadcasting the whole time, and still never inside the cloud. Every
            # sample it gave us scored zero grid probability, so "the report with the highest
            # grid probability" (D36) ties across all of them; the nearest is the honest reading
            # of the distance, and it is a real measurement rather than a stand-in.
            reason = (f"{n} AIS reports inside the release window and never entered the "
                      f"reconstructed origin — closest approach {km:.1f} km from the peak, at "
                      f"zero grid probability throughout")
        doc["excluded"].append({
            "mmsi": t.mmsi,
            "name": t.name or "",
            "closest_km": None if km is None else round(km, 2),
            "reason": reason,
        })

    # vessels.geojson: the plausible set only, so the map draws what was considered —
    # and clipped to the release window with an hour either side. The full 24-hour track
    # of a vessel that crossed the whole search box is neither what the Attribute screen
    # shows nor inside the scene bounds, and the validator rightly warns about every
    # point of it.
    features = [clipped_feature(s["track"], t0, t1) for s in plausible]

    # --------------------------------------------------------------- dark vessels (D42)
    # The radar-versus-transponder cross-check. It needs AIS searched at the SCENE's place and
    # time, which the origin-window extract above does not cover, so it runs on its own extract.
    # Without one, darkness is null (D34) and nothing is listed.
    bounds_path = case_dir / "bounds.json"
    bounds = json.loads(bounds_path.read_text(encoding="utf-8")) if bounds_path.exists() else None
    contacts = dark.contacts_from_detections(detections_doc, bounds)
    if a.sar_contacts:
        ext = dark.contacts_from_external(dark.load_external(a.sar_contacts), a.sar_label)
        contacts = (contacts or []) + ext
    scene_tracks = []
    if a.scene_parquet:
        scene_tracks = list(load_tracks(a.scene_parquet, 1).values())
    dark_list, dark_summary = dark.cross_check(
        contacts, scene_tracks, dark.scene_time(meta), ais_source, grid, detections_doc,
        have_scene_ais=bool(a.scene_parquet))
    doc["dark_vessels"] = dark_list

    (out_dir / "vessels.geojson").write_text(
        json.dumps({"type": "FeatureCollection", "features": features}), encoding="utf-8")
    (out_dir / "suspects.json").write_text(json.dumps(doc, indent=2), encoding="utf-8")

    # ------------------------------------------------------------------------ report
    print(f"\nfunnel        {funnel['in_region']} -> {funnel['in_window']} -> "
          f"{funnel['plausible']} -> {funnel['scored']}"
          f"   ({dropped_short} dropped for < {regime(ais_source)['min_points']} reports)")
    print(f"dark check    {dark_summary['contacts']} radar contacts, "
          f"{dark_summary['matched']} matched to AIS, {dark_summary['unmatched']} unmatched, "
          f"{dark_summary['relevant']} near the slick/origin, {dark_summary['listed']} listed"
          + ("" if dark_summary["ais_searched_at_scene_time"] else
             "   (no scene-time AIS: darkness not assessed)"))
    if a.ranking:
        print(f"\n{'#':>2} {'score':>6} {'live':>5}  {'vessel':24} " +
              "  ".join(f"{k[:4]:>5}" for k in WEIGHTS))
        for i, s in enumerate(plausible, 1):
            cells = "  ".join(
                ("  n/a" if not s["components"][k].applicable
                 else f"{s['components'][k].value:5.2f}") for k in WEIGHTS)
            print(f"{i:2} {s['score']:6.3f} {s['weight_live']:5.2f}  "
                  f"{(s['track'].name or s['track'].mmsi)[:24]:24} {cells}")

    if abstained:
        print(f"\nABSTAINED     {why}")
    else:
        for i, s in enumerate(top, 1):
            t = s["track"]
            live = ", ".join(f"{k} {c.value:.2f}" for k, c in s["components"].items()
                             if c.applicable)
            na = [k for k, c in s["components"].items() if not c.applicable]
            print(f"  {i}. {s['score']:.3f}  {t.name or t.mmsi:<22.22} {t.vessel_type:<10}"
                  f" {s['closest_km']:>6.1f} km  {iso(s['closest_time'])}")
            print(f"       {live}")
            if na:
                print(f"       n/a: {', '.join(na)}")
    print(f"\nexclusions    {len(doc['excluded'])}")
    for e in doc["excluded"]:
        print(f"  - {e['name'] or e['mmsi']}: {e['reason']}")
    print(f"\ninfrastructure {len(infra)} finding(s)   "
          f"[{infra_diag['candidates']} candidate(s) declared, "
          f"{infra_diag['termini']} terminus point(s) on the slick]")
    for f in infra:
        tkm = "n/a" if f["terminus_km"] is None else f"{f['terminus_km']:.2f} km"
        print(f"  - {f['name']} ({f['kind']})  score {f['score']:.3f}   "
              f"origin_p {f['origin_probability']:.2f}   terminus {tkm}")
        for r in f["reasons"]:
            print(f"      {r}")
    for name in infra_diag.get("below_floor", []):
        print(f"  - {name}: below the {INFRA_SCORE_FLOOR} floor, not reported")
    if infra_diag["candidates"] == 0 and infra_diag["termini"]:
        print("  no candidate declared in meta.json/infrastructure_candidates, so nothing is")
        print("  named. Slick termini were computed and are available; a fixed point with no")
        print("  declared structure behind it is water the drift model liked, not a finding.")

    print(f"\nwrote {out_dir / 'vessels.geojson'}  ({len(features)} tracks)")
    print(f"      {out_dir / 'suspects.json'}")
    print(f"\nNow run:  python scripts/validate_case.py {case_dir}")


if __name__ == "__main__":
    main()
