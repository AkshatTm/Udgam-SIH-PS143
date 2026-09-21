#!/usr/bin/env python3
"""
Stage 3, step 2 — track reconstruction. Owner: Jaiveer.

Turns the filtered Parquet from ingest.py into one time-ordered track per MMSI.

    python pipeline/attribute/tracks.py --parquet data/ais/gulf.parquet

Importable too — this is what the scorer will use:

    from tracks import load_tracks
    tracks = load_tracks("data/ais/gulf.parquet")
    t = tracks["367123450"]
    t.position_at(when)      # (lon, lat) or None
    t.max_gap_minutes        # largest silence in the whole track
    t.gap_overlapping(t0, t1)  # longest gap overlapping a window, minutes

Two rules that are easy to get wrong and expensive to get wrong:

  1. **No identity resolution.** MMSIs are sometimes reused and sometimes spoofed.
     We group by MMSI as broadcast and accept that as a known imperfection. One
     demo case; solving MMSI identity is not our problem.

  2. **Never interpolate across a long gap.** If a transponder went quiet for
     three hours, drawing a straight line through it invents a position that
     never happened — and then that invented position can score as a suspect.
     `position_at` returns None across any gap longer than MAX_INTERP_GAP_MIN.
     A long gap is the evidence we are hunting for, not a hole to patch.
"""
import argparse
from bisect import bisect_left
from datetime import datetime, timezone
from pathlib import Path

import duckdb

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]

MIN_POINTS = 5          # below this a "track" is noise, not a path
MAX_INTERP_GAP_MIN = 30  # never draw a position across a longer silence
MAX_TRACK_POINTS = 500   # contract §7: decimate so the map stays fast

# D41 — the two thresholds above were set for NOAA's ~69 s reporting and were being applied
# unchanged to GFW's one-fix-per-hour data, where they mean something else entirely:
#   * 5 points is 5 *hours* of presence. A ship crossing a search box at 12 kn is inside it
#     for one or two hours, so every transiting vessel was dropped before it was looked at
#     (Mumbai 7 of 9, Jamnagar 6 of 8).
#   * a 30-minute interpolation ceiling is shorter than the sampling interval itself, so no
#     position between two hourly fixes was ever considered, and a vessel crossing a 3.7 km
#     origin cloud between fixes could never be "in" it.
# Derived from the sampling interval, not tuned on any case: two fixes make a path, and a
# 75-minute ceiling joins consecutive hourly fixes while still refusing to bridge a missing
# hour. `noaa_dense` keeps the original values, so the US cases are unchanged.
REGIME = {
    "noaa_dense": {"min_points": MIN_POINTS, "max_interp_gap_min": MAX_INTERP_GAP_MIN},
    "gfw_hourly": {"min_points": 2, "max_interp_gap_min": 75},
}


def regime(ais_source):
    return REGIME.get(ais_source, REGIME["noaa_dense"])


class Track:
    """One vessel's time-ordered path. Timestamps are tz-aware UTC."""

    __slots__ = ("mmsi", "name", "vessel_type", "type_code", "ts", "lon", "lat", "sog", "cog")

    def __init__(self, mmsi, name, vessel_type, type_code, ts, lon, lat, sog, cog):
        self.mmsi = mmsi
        self.name = name
        self.vessel_type = vessel_type
        self.type_code = type_code
        self.ts = ts        # list[datetime], ascending, tz-aware UTC
        self.lon = lon
        self.lat = lat
        self.sog = sog
        self.cog = cog

    def __len__(self):
        return len(self.ts)

    @property
    def start(self):
        return self.ts[0]

    @property
    def end(self):
        return self.ts[-1]

    @property
    def gaps_minutes(self):
        """Silence between each consecutive pair of reports, in minutes."""
        return [(b - a).total_seconds() / 60.0 for a, b in zip(self.ts, self.ts[1:])]

    @property
    def max_gap_minutes(self):
        g = self.gaps_minutes
        return round(max(g), 1) if g else 0.0

    def gap_overlapping(self, t0, t1):
        """Longest gap that overlaps [t0, t1], in minutes. 0.0 if none does.

        This is the `gap` scoring component: a transponder going dark *during the
        window* is interesting; one that went dark a day earlier is not.
        """
        best = 0.0
        for a, b, mins in zip(self.ts, self.ts[1:], self.gaps_minutes):
            if a < t1 and b > t0:
                best = max(best, mins)
        return round(best, 1)

    def position_at(self, when, max_gap_min=MAX_INTERP_GAP_MIN):
        """Linear interpolation to `when`. None outside the track, None across a long gap."""
        if when < self.ts[0] or when > self.ts[-1]:
            return None
        i = bisect_left(self.ts, when)
        if self.ts[i] == when:
            return (self.lon[i], self.lat[i])
        a, b = i - 1, i
        span_s = (self.ts[b] - self.ts[a]).total_seconds()
        if span_s <= 0:
            return (self.lon[a], self.lat[a])   # duplicate timestamps: no interval to divide by
        span = span_s / 60.0
        if span > max_gap_min:
            return None          # deliberately refuse to invent a position
        f = (when - self.ts[a]).total_seconds() / span_s
        return (self.lon[a] + f * (self.lon[b] - self.lon[a]),
                self.lat[a] + f * (self.lat[b] - self.lat[a]))

    def median_sog(self):
        vals = sorted(v for v in self.sog if v is not None)
        if not vals:
            return None
        n = len(vals)
        return vals[n // 2] if n % 2 else (vals[n // 2 - 1] + vals[n // 2]) / 2.0

    def coordinates(self, max_points=MAX_TRACK_POINTS):
        """[[lon, lat], ...] decimated to <= max_points, endpoints always kept."""
        n = len(self.ts)
        idx = range(n) if n <= max_points else \
            sorted({round(i * (n - 1) / (max_points - 1)) for i in range(max_points)})
        return [[round(self.lon[i], 5), round(self.lat[i], 5)] for i in idx]

    def to_feature(self):
        """A vessels.geojson Feature — contract §7."""
        return {
            "type": "Feature",
            "geometry": {"type": "LineString", "coordinates": self.coordinates()},
            "properties": {
                "mmsi": self.mmsi,
                "name": self.name or "",
                "vessel_type": self.vessel_type,
                "n_points": len(self.ts),
                "max_gap_minutes": self.max_gap_minutes,
            },
        }



# WHAT COUNTS AS A VESSEL. ITU-R M.585 assigns MMSI number ranges by station type, and several
# of them are not ships at all. Scoring one as a pollution suspect is not a ranking error, it
# is a category error -- case-gulf-alaska-2023 shipped with its only two "suspects" being aids
# to navigation, one of them named "MAJOR BUOY 4".
#
# Filtered HERE rather than at ingest or at scoring. Not at ingest, because the extract should
# stay a faithful record of what the archive returned and re-deciding this rule should not mean
# re-downloading. Not at scoring, because by then the buoy has already consumed a slot in
# in_window and plausible, and the funnel -- which exists to make the search visible -- would be
# counting things we do not consider candidates. tracks.py is where "what is a track" is already
# decided (MIN_POINTS), so a counted, printed drop belongs beside dropped_short_track.
NON_VESSEL_MMSI = (
    ("99", "aid to navigation (99MIDxxxx -- physical or virtual AtoN)"),
    ("98", "craft associated with a parent ship (98MIDxxxx -- tender, lifeboat)"),
    ("97", "search-and-rescue transmitter / AIS-SART / MOB / EPIRB-AIS (97xxxxxxx)"),
    ("111", "SAR aircraft (111MIDxxx)"),
    ("00", "coast station (00MIDxxxx)"),
    ("0", "group of ships or coast radio station (0MIDxxxxx)"),
)
# ITU maritime identification digits. A 9-digit MMSI whose first three are outside this range
# belongs to no flag administration. This is what rejects GFW's 941* presence records -- 941 is
# an unassigned MID, which is the honest reason, rather than pattern-matching the literal 941.
MID_MIN, MID_MAX = 201, 775


def non_vessel_reason(mmsi):
    """Why this MMSI is not a ship, or None if it is one."""
    m = str(mmsi)
    if not (len(m) == 9 and m.isdigit()):
        return f"not a 9-digit MMSI ({m!r})"
    for prefix, why in NON_VESSEL_MMSI:
        if m.startswith(prefix):
            return why
    mid = int(m[:3])
    if not (MID_MIN <= mid <= MID_MAX):
        return (f"MID {mid} is outside the ITU assigned range {MID_MIN}-{MID_MAX}, so this "
                f"identifier belongs to no flag administration")
    return None


def load_tracks(parquet_path, min_points=MIN_POINTS, diagnostics=False):
    """Parquet -> {mmsi: Track}. Sorted by time, short tracks dropped, non-vessels rejected.

    With `diagnostics=True` returns `(tracks, diag)` where diag counts what was dropped and
    why. score.py needs the breakdown: it derives dropped_short_track by subtracting from a
    raw count(DISTINCT mmsi), so without it the AtoN drops would be silently absorbed into
    dropped_short_track -- which is exactly the kind of hidden assumption the funnel exists
    to prevent.
    """
    con = duckdb.connect()
    con.execute("SET TimeZone='UTC'")
    # ts comes back as epoch seconds, not datetimes: DuckDB's Python conversion of
    # TIMESTAMPTZ wants pytz, which is not in requirements.txt and is not worth adding.
    # Epoch -> datetime is also several times faster than parsing ISO strings.
    rows = con.execute("""
        SELECT mmsi,
               max(name)                          AS name,
               any_value(vessel_type)             AS vessel_type,
               max(type_code)                     AS type_code,
               list(epoch(ts) ORDER BY ts)        AS ts,
               list(lon ORDER BY ts)              AS lon,
               list(lat ORDER BY ts)              AS lat,
               list(sog ORDER BY ts)              AS sog,
               list(cog ORDER BY ts)              AS cog
        FROM read_parquet(?)
        GROUP BY mmsi
        HAVING count(*) >= ?
    """, [str(parquet_path), min_points]).fetchall()
    con.close()

    tracks, rejected = {}, []
    for mmsi, name, vtype, tcode, ts, lon, lat, sog, cog in rows:
        why = non_vessel_reason(mmsi)
        if why:
            rejected.append((mmsi, name or "", why))
            continue
        ts = [datetime.fromtimestamp(e, timezone.utc) for e in ts]
        tracks[mmsi] = Track(mmsi, name, vtype, tcode, ts, lon, lat, sog, cog)
    rejected.sort()
    if not diagnostics:
        return tracks
    return tracks, {"dropped_non_vessel": len(rejected), "non_vessel": rejected}


def main():
    ap = argparse.ArgumentParser(description="Reconstruct per-MMSI tracks from filtered AIS.")
    ap.add_argument("--parquet", required=True, help="output of ingest.py")
    ap.add_argument("--min-points", type=int, default=MIN_POINTS)
    args = ap.parse_args()

    tracks = load_tracks(args.parquet, args.min_points)
    if not tracks:
        raise SystemExit(f"no track had >= {args.min_points} points — check the ingest output")

    lengths = sorted(len(t) for t in tracks.values())
    gaps = sorted(t.max_gap_minutes for t in tracks.values())
    n = len(tracks)
    by_type = {}
    for t in tracks.values():
        by_type[t.vessel_type] = by_type.get(t.vessel_type, 0) + 1

    print(f"{n:,} tracks with >= {args.min_points} points")
    print(f"  points per track   min {lengths[0]}  median {lengths[n // 2]}  max {lengths[-1]}")
    print(f"  max gap (minutes)  median {gaps[n // 2]:.1f}  worst {gaps[-1]:.1f}")
    print("  by type: " + ", ".join(f"{k} {v}" for k, v in
                                    sorted(by_type.items(), key=lambda kv: -kv[1])))
    named = sum(1 for t in tracks.values() if t.name)
    print(f"  {named:,} of {n:,} have a vessel name in the raw file")

    longest = max(tracks.values(), key=len)
    print(f"\nlongest track  {longest.mmsi}  {longest.name or '(no name)'}"
          f"  {longest.vessel_type}  {len(longest)} points")
    print(f"  {longest.start:%Y-%m-%dT%H:%M:%SZ} .. {longest.end:%Y-%m-%dT%H:%M:%SZ}"
          f"  max gap {longest.max_gap_minutes} min")


if __name__ == "__main__":
    main()
