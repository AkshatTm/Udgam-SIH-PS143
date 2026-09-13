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
import re
from datetime import date, datetime, timedelta, timezone
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


NOAA_DAY_RE = re.compile(r"AIS_(\d{4})_(\d{2})_(\d{2})", re.IGNORECASE)


def first_row_date(csv_path):
    """UTC date of the first data row. Two lines read, not the whole file.

    Read from the data rather than the filename because a renamed or re-saved file
    is exactly the case a filename check would wave through.
    """
    with open(csv_path, encoding="utf-8", errors="replace") as f:
        header = [h.strip().lower() for h in f.readline().split(",")]
        if "basedatetime" not in header:
            return None
        col = header.index("basedatetime")
        row = f.readline()
    if not row:
        return None
    try:
        return datetime.fromisoformat(row.split(",")[col].strip().replace("Z", "")).date()
    except (ValueError, IndexError):
        return None


def check_consecutive_days(csv_paths):
    """Refuse a set of daily files that is not one consecutive run of days.

    This is a hard stop, not a warning, because the failure is silent and looks like
    a result. tracks.py measures transponder silence with lag(ts) over the merged
    rows. Ingest 25 Jan together with 16 Feb and every vessel in the file acquires a
    three-week gap: max_gap_minutes stops meaning anything and the `gap` component
    fires on the entire fleet as a plausible signal rather than as an error.
    Risk D6; docs/team/jaiveer-stage3-attribution.md Phase 9.1.

    'Consecutive' is the rule, not 'narrow'. An incident +/- 2 days is a five-day
    span and must pass; what must fail is a hole in the middle of it, so the test is
    on each adjacent pair, never on the total span.
    """
    dated = []
    for p in csv_paths:
        d = first_row_date(p)
        if d is None:
            print(f"note: no readable BaseDateTime in {Path(p).name} — "
                  "day continuity NOT checked for this run.\n")
            return
        name_match = NOAA_DAY_RE.search(Path(p).name)
        if name_match:
            named = date(*(int(g) for g in name_match.groups()))
            if named != d:
                raise SystemExit(
                    f"{Path(p).name} is named for {named} but its first row is {d}.\n"
                    "  The file has been renamed or the wrong day was downloaded. Fix the\n"
                    "  filename or re-download before ingesting — a mislabelled day is how\n"
                    "  the wrong window silently gets scored.")
        dated.append((d, Path(p).name))

    dated.sort()
    for (d1, n1), (d2, n2) in zip(dated, dated[1:]):
        span = (d2 - d1).days
        if span == 0:
            raise SystemExit(
                f"{n1} and {n2} both cover {d1}.\n"
                "  Ingesting the same day twice duplicates every position report and\n"
                "  corrupts the reporting intervals. Pass each day once.")
        if span > 1:
            missing = ", ".join(str(d1 + timedelta(days=i)) for i in range(1, min(span, 6)))
            raise SystemExit(
                f"{n1} ({d1}) and {n2} ({d2}) are {span} days apart — not consecutive.\n"
                f"  Missing: {missing}{' ...' if span > 6 else ''}\n"
                "  Merging them would record the whole hole as a transponder gap for every\n"
                "  vessel, and the `gap` component would fire on the entire fleet. Download\n"
                "  the intervening days, or ingest each run into its own Parquet.")

    days = [d for d, _ in dated]
    if len(days) == 1:
        print(f"days    {days[0]} (single day)")
    else:
        print(f"days    {days[0]} .. {days[-1]} — {len(days)} consecutive days")


def print_rejects(con, csv_paths):
    """Count and report lines the CSV reader could not parse. Best-effort: see the call site.

    Nothing is recovered here and nothing is repaired — this only answers "how much did the
    reader throw away", so the number can sit next to the funnel instead of being invisible.
    """
    try:
        con.execute("DROP TABLE IF EXISTS reject_errors")
        con.execute("DROP TABLE IF EXISTS reject_scans")
        con.execute(
            "CREATE TEMP TABLE _rejcount AS "
            "SELECT count(*) AS n FROM read_csv(?, header=true, store_rejects=true, "
            "types={'MMSI': 'VARCHAR', 'VesselName': 'VARCHAR'})",
            [[str(p) for p in csv_paths]],
        )
        rejected = con.execute("SELECT count(*) FROM reject_errors").fetchone()[0]
    except duckdb.Error as exc:
        print(f"note: could not count malformed CSV lines ({type(exc).__name__}).")
        print("      The ingest above still stands — it tolerates unparseable rows — but the")
        print("      number thrown away is unknown for this run. Say so if it reaches a slide.\n")
        return

    if rejected:
        print(f"note: {rejected} malformed CSV line(s) rejected by the reader, not ingested.")
        print("      Structurally broken rows cannot be repaired without inventing fields.")
        print("      Report this count alongside the funnel if it is ever more than a handful.\n")


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
            FROM read_csv(?, header=true, union_by_name=true, ignore_errors=true,
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

    # NOAA's daily exports occasionally carry a structurally broken line. AIS_2023_05_15 has
    # exactly one in 8,904,500: a row with a leading empty field, which shifts every column
    # right by one and puts the MMSI where BaseDateTime belongs. Without `ignore_errors` the
    # whole scan dies on it and the case cannot be ingested at all.
    #
    # A shifted row is NOT repaired. There is no recoverable MMSI in it, and guessing the
    # alignment would fabricate a position report — the same sin as interpolating across a
    # transponder gap. It is dropped. But a row silently vanishing is exactly the kind of
    # hidden assumption the funnel exists to prevent, so it is also counted and printed.
    #
    # The count needs a second pass: DuckDB refuses `store_rejects` alongside `union_by_name`,
    # and `union_by_name` is the thing that lets NOAA's schema drift between years. So the
    # scan above tolerates, and this pass counts. It is best-effort by design — if the files
    # disagree on schema badly enough that a single-schema read fails, the ingest still stands
    # and the count reports as unknown rather than taking the run down with it.
    print_rejects(con, csv_paths)

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

    check_consecutive_days(args.csv)

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
