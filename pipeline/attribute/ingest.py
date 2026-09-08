#!/usr/bin/env python3
"""
Stage 3, step 1 — AIS ingest. Owner: Jaiveer.

Filters raw NOAA Marine Cadastre daily AIS CSVs down to a bounding box and time
window **while reading**, and writes a small Parquet file. This is the expensive
step and you pay it once; every query after this is instant.

    python pipeline/attribute/ingest.py \
        --csv data/ais/AIS_2023_01_25.csv \
        --bbox -95.5 28.0 -93.5 29.8 \
        --out data/ais/gulf.parquet

Or derive the box and the window straight from an origin cloud, which is how
Phase 2 runs (the same command works for the fake origin and the real one —
that is the whole point of the contract):

    python pipeline/attribute/ingest.py \
        --csv data/ais/AIS_2023_01_25.csv \
        --from-origin cases/case-000/origin.json \
        --out data/ais/case.parquet

The NOAA daily files are ~800 MB unzipped and tens of millions of rows.
`pd.read_csv` on one will freeze the laptop (docs/TRAPS.md #12). DuckDB streams
the file and applies the WHERE clause during the scan, so peak memory is the
size of the *filtered* result, not the file.

Output columns
    mmsi          VARCHAR   as broadcast, no identity resolution (deliberate)
    ts            TIMESTAMPTZ  UTC, timezone-aware
    lon, lat      DOUBLE    WGS84, [longitude, latitude] order everywhere
    sog           DOUBLE    speed over ground, knots as NOAA publishes them
    cog           DOUBLE    course over ground, degrees clockwise from north
    heading       DOUBLE    may be null / 511 in the raw data
    name          VARCHAR   VesselName, may be blank
    type_code     INTEGER   raw AIS ship-type code
    vessel_type   VARCHAR   tanker | cargo | fishing | passenger | other

Raw AIS never leaves this laptop. `data/` is gitignored; only the finished
vessels.geojson / suspects.json travel to the team.
"""
import argparse
import json
import math
from datetime import datetime, timedelta, timezone
from pathlib import Path

import duckdb

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]

KM_PER_DEG = 111.32

# AIS ship-type codes -> the five categories TYPE_PRIOR scores in run.py.
# 80-89 tanker · 70-79 cargo · 30 fishing · 60-69 passenger · everything else other.
VESSEL_TYPE_SQL = """
    CASE
        WHEN try_cast(VesselType AS INTEGER) BETWEEN 80 AND 89 THEN 'tanker'
        WHEN try_cast(VesselType AS INTEGER) BETWEEN 70 AND 79 THEN 'cargo'
        WHEN try_cast(VesselType AS INTEGER) = 30            THEN 'fishing'
        WHEN try_cast(VesselType AS INTEGER) BETWEEN 60 AND 69 THEN 'passenger'
        ELSE 'other'
    END
"""


def parse_ts(s):
    """ISO 8601 with a trailing Z. A naive datetime is a bug (README, frozen rule 2)."""
    dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        raise SystemExit(f"'{s}' is timezone-naive — every timestamp needs the trailing Z")
    return dt.astimezone(timezone.utc)


def iso(dt):
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def box_from_origin(origin_path, pad_hours):
    """Bounding box + time window from an origin cloud, padded to 2x radius_90_km.

    2x radius_90 is not arbitrary: it is exactly the `plausible` cut in the funnel
    (docs/05_JAIVEER_AIS.md Phase 2), so nothing that could ever be called plausible
    gets filtered away here.
    """
    o = json.loads(Path(origin_path).read_text(encoding="utf-8"))
    b = o["bounds"]
    pad_km = 2.0 * float(o["radius_90_km"])
    lat_pad = pad_km / KM_PER_DEG
    mid_lat = (b["south"] + b["north"]) / 2.0
    lon_pad = pad_km / (KM_PER_DEG * max(math.cos(math.radians(mid_lat)), 0.01))

    t0, t1 = (parse_ts(t) for t in o["time_window"])
    pad = timedelta(hours=pad_hours)

    bbox = (b["west"] - lon_pad, b["south"] - lat_pad,
            b["east"] + lon_pad, b["north"] + lat_pad)
    return bbox, (t0 - pad, t1 + pad), o.get("abstain", False)


def has_cargo_column(csv_path):
    """Is there a Cargo column in this file? Older NOAA years vary."""
    with open(csv_path, encoding="utf-8", errors="replace") as f:
        header = [h.strip().lower() for h in f.readline().split(",")]
    return "cargo" in header


def ingest(csv_paths, bbox, window, out_path, keep_cargo):
    west, south, east, north = bbox
    if west >= east or south >= north:
        raise SystemExit(f"bbox looks wrong: --bbox WEST SOUTH EAST NORTH, got {bbox}")

    con = duckdb.connect()
    con.execute("SET TimeZone='UTC'")

    where = ["LON BETWEEN ? AND ?", "LAT BETWEEN ? AND ?"]
    params = [west, east, south, north]
    if window:
        where.append("BaseDateTime >= ? AND BaseDateTime < ?")
        params += [window[0].replace(tzinfo=None), window[1].replace(tzinfo=None)]

    # AIS "not available" sentinels are real values in the file and must become NULL here,
    # or they silently become measurements downstream (docs/TRAPS.md — Stage 3):
    #   SOG 102.3  -> a vessel appears to do 102 knots
    #   COG 360.0  -> "unknown heading" reads as "heading due north", straight into the
    #                 trajectory component, which is 20% of the score
    #   Heading 511-> same, for the gyro heading
    # DISTINCT ON drops exact duplicate (mmsi, timestamp) reports — two AIS messages landing
    # in the same second — which would otherwise put a zero-length interval in a track.
    sql = f"""
        SELECT DISTINCT ON (mmsi, ts) * FROM (
            SELECT
                MMSI                                AS mmsi,
                BaseDateTime AT TIME ZONE 'UTC'     AS ts,
                LON                                 AS lon,
                LAT                                 AS lat,
                CASE WHEN try_cast(SOG AS DOUBLE) >= 102 THEN NULL
                     ELSE try_cast(SOG AS DOUBLE) END      AS sog,
                CASE WHEN try_cast(COG AS DOUBLE) >= 360 THEN NULL
                     ELSE try_cast(COG AS DOUBLE) END      AS cog,
                CASE WHEN try_cast(Heading AS DOUBLE) >= 511 THEN NULL
                     ELSE try_cast(Heading AS DOUBLE) END  AS heading,
                nullif(trim(VesselName), '')        AS name,
                try_cast(VesselType AS INTEGER)     AS type_code,
                {VESSEL_TYPE_SQL}                   AS vessel_type,
                {"try_cast(Cargo AS INTEGER)" if keep_cargo else "NULL"} AS cargo_code
            FROM read_csv(?, header=true, union_by_name=true,
                          types={{'MMSI': 'VARCHAR', 'VesselName': 'VARCHAR'}})
            WHERE {' AND '.join(where)}
        )
        ORDER BY mmsi, ts
    """

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    con.execute(
        f"COPY ({sql}) TO '{out_path.as_posix()}' (FORMAT PARQUET)",
        [[str(p) for p in csv_paths]] + params,
    )

    # Timestamps come back as strings, not datetimes: DuckDB's Python conversion of
    # TIMESTAMPTZ wants pytz, which is not in requirements.txt and is not worth adding.
    summary = con.execute(f"""
        SELECT count(*)                                  AS rows,
               count(DISTINCT mmsi)                      AS vessels,
               strftime(min(ts), '%Y-%m-%dT%H:%M:%SZ')   AS first_ts,
               strftime(max(ts), '%Y-%m-%dT%H:%M:%SZ')   AS last_ts,
               min(lon), max(lon), min(lat), max(lat)
        FROM read_parquet('{out_path.as_posix()}')
    """).fetchone()
    types = con.execute(f"""
        SELECT vessel_type, count(DISTINCT mmsi) AS n
        FROM read_parquet('{out_path.as_posix()}')
        GROUP BY 1 ORDER BY n DESC
    """).fetchall()

    # What is the tug/tow fleet actually pushing? AIS ship-type 31/32/52 says a vessel is
    # towing, not what it is towing — so the Cargo field is the only thing in this data that
    # could separate an oil barge from a gravel barge. It is frequently blank; that is a
    # finding too, and it belongs on the limitations slide rather than in a guess.
    cargo = []
    if keep_cargo:
        cargo = con.execute(f"""
            SELECT coalesce(cargo_code, -1) AS code, count(DISTINCT mmsi) AS n
            FROM read_parquet('{out_path.as_posix()}')
            WHERE type_code IN (31, 32, 52)
            GROUP BY 1 ORDER BY n DESC LIMIT 12
        """).fetchall()
    con.close()
    return summary, types, cargo


def main():
    ap = argparse.ArgumentParser(description="Filter NOAA AIS CSVs to a bbox + window.")
    ap.add_argument("--csv", nargs="+", required=True,
                    help="one or more NOAA daily CSVs (unzipped)")
    ap.add_argument("--out", required=True, help="output .parquet path")
    ap.add_argument("--bbox", nargs=4, type=float, metavar=("WEST", "SOUTH", "EAST", "NORTH"),
                    help="bounding box in degrees, WGS84")
    ap.add_argument("--from-origin", help="derive bbox + window from an origin.json")
    ap.add_argument("--start", help="UTC ISO 8601 with trailing Z")
    ap.add_argument("--end", help="UTC ISO 8601 with trailing Z")
    ap.add_argument("--pad-hours", type=float, default=6.0,
                    help="hours padded either side of an origin time_window (default 6)")
    args = ap.parse_args()

    if bool(args.bbox) == bool(args.from_origin):
        raise SystemExit("give exactly one of --bbox or --from-origin")

    for p in args.csv:
        if not Path(p).exists():
            raise SystemExit(f"no such file: {p}")

    if args.from_origin:
        bbox, window, abstain = box_from_origin(args.from_origin, args.pad_hours)
        if abstain:
            print("note: origin has abstain=true — Stage 3 must produce zero suspects.")
    else:
        bbox = tuple(args.bbox)
        window = None
        if args.start or args.end:
            if not (args.start and args.end):
                raise SystemExit("--start and --end go together")
            window = (parse_ts(args.start), parse_ts(args.end))

    print(f"bbox    lon {bbox[0]:.4f} .. {bbox[2]:.4f}   lat {bbox[1]:.4f} .. {bbox[3]:.4f}")
    print(f"window  {iso(window[0]) + ' .. ' + iso(window[1]) if window else 'whole file'}")
    print(f"reading {len(args.csv)} file(s) — streaming, this takes a minute or two per day\n")

    keep_cargo = has_cargo_column(args.csv[0])
    if not keep_cargo:
        print("note: no Cargo column in this file — cargo_code will be null.\n")

    (rows, vessels, first_ts, last_ts, wlon, elon, slat, nlat), types, cargo = ingest(
        args.csv, bbox, window, args.out, keep_cargo)

    if rows == 0:
        print("0 rows kept. The box is empty water, or the window misses these files.")
        print("Check the box against the traffic on marinecadastre.gov/accessais before rerunning.")
        raise SystemExit(1)

    size_mb = Path(args.out).stat().st_size / 1e6
    print(f"wrote {args.out}  ({size_mb:.1f} MB)")
    print(f"  {rows:,} position reports from {vessels:,} distinct MMSIs")
    print(f"  {first_ts} .. {last_ts}")
    print(f"  actual extent  lon {wlon:.4f} .. {elon:.4f}   lat {slat:.4f} .. {nlat:.4f}")
    print("  vessels by type: " + ", ".join(f"{t} {n}" for t, n in types))

    if cargo:
        total = sum(n for _, n in cargo)
        blank = sum(n for c, n in cargo if c in (-1, 0))
        print(f"\n  tug/tow fleet (codes 31/32/52): {total} vessels — what the Cargo field says")
        for code, n in cargo:
            label = "(not declared)" if code in (-1, 0) else f"cargo code {code}"
            print(f"    {label:<18} {n:>4}")
        if blank == total:
            print("    -> every one is blank. AIS does not tell us what these barges hold;")
            print("       that is a limitation to state, not a gap to fill with a guess.")
        else:
            print(f"    -> {total - blank} of {total} declare something. Worth looking up before")
            print("       any type_prior argument — see docs/PHASE1_JAIVEER.md, Problem 1.")


if __name__ == "__main__":
    main()
