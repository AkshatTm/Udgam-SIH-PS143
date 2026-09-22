#!/usr/bin/env python3
"""
Stage 3, step 1b — AIS ingest for the Indian cases, from Global Fishing Watch. Owner: Akshat.

    python pipeline/attribute/ingest_gfw.py --case case-mumbai-2023 --out data/ais/mumbai.parquet
    python pipeline/attribute/ingest_gfw.py --case case-jamnagar-2024 --out data/ais/jamnagar.parquet

NOAA Marine Cadastre is US waters only, so cases 5 and 6 had no AIS at all and Stage 3 could only
abstain with "nothing was searched". This fills that gap from GFW's public API and writes the SAME
parquet schema `ingest.py` writes, so `tracks.py` and `score.py` need no changes.

**A CORRECTION TO WHAT WE BELIEVED (14 Sept).** `scripts/gfw_probe.py` and Master §6.1 record that
GFW's presence layer "does not provide individual vessel positions" — that is what GFW's own
documentation says about the *map layer*. It is not true of the 4wings **report** endpoint at
`spatial-resolution=HIGH`, `temporal-resolution=HOURLY`, `spatial-aggregation=false`,
`group-by=VESSEL_ID`, which returns one row per vessel per hour per cell carrying `mmsi`,
`shipName`, `vesselType`, `flag`, `imo`, `lat` and `lon`. Measured on the Mumbai box: 13 distinct
vessels, 190 hourly rows over two days.

WHAT THESE POSITIONS ARE, AND WHAT THEY ARE NOT
    * A position is a **grid cell centre**, not a fix. At HIGH resolution that is 0.01 deg,
      roughly 1 km, so the position carries ~1 km of quantisation on top of everything else.
    * One row per **hour**, against NOAA's ~71 s. This is exactly the `gfw_hourly` regime D20
      describes, and `gap` and `slowdown` gate to null on it (§6.1).
    * **`sog` and `cog` are not published by this endpoint, so they are written NULL** rather than
      derived. A course computed between two 1 km cell centres an hour apart is a number with no
      measurement behind it, and `trajectory` gating to null is the honest outcome. Deriving one
      would manufacture the very precision this case does not have.
    * Non-commercial use only. That condition is real and belongs on the provenance slide.

So the Indian cases now run a real funnel over real vessels, scored on the components that hourly
sampling can actually support, and the card says which ones those are.
"""
import argparse
import json
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

import duckdb

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO / "scripts"))

from gfw_probe import BASE, geojson_box, load_token          # noqa: E402

TIMEOUT = 120
DATASET = "public-global-presence:latest"

# GFW publishes a coarse class string; map it onto the five classes TYPE_PRIOR scores. Anything
# unrecognised becomes 'other' rather than being guessed at.
GFW_TYPE = {
    "TANKER": "tanker", "CARGO": "cargo", "FISHING": "fishing", "PASSENGER": "passenger",
    "SEISMIC_VESSEL": "other", "BUNKER": "tanker", "CARRIER": "cargo", "SUPPORT": "other",
    "OTHER": "other", "GEAR": "other",
}


# D41. `ingest.py`'s 2 x r90 pad is right for 69 s NOAA reports, where any vessel crossing the
# box leaves dozens of fixes. At one fix per hour it is not: on the Indian cases 2 x r90 is ~7 km,
# a ship at 12 kn is inside that for well under an hour, and the extract held one or two hourly
# fixes per vessel. The pad is floored at one hour of travel at ~16 kn so a transiting vessel
# leaves at least two fixes in the box. Derived from the sampling interval, not from any case.
HOURLY_MIN_PAD_KM = 30.0


def window_from_origin(origin_path, pad_hours):
    """Bbox + window from an origin cloud, padded. Same convention as ingest.py --from-origin,
    except that the spatial pad is floored for hourly sampling (D41)."""
    o = json.loads(Path(origin_path).read_text(encoding="utf-8"))
    b = o["bounds"]
    pad_km = max(2.0 * float(o["radius_90_km"]), HOURLY_MIN_PAD_KM)
    lat_pad = pad_km / 111.32
    mid_lat = (b["south"] + b["north"]) / 2
    import math
    lon_pad = pad_km / (111.32 * max(math.cos(math.radians(mid_lat)), 0.01))
    t0 = datetime.fromisoformat(o["time_window"][0].replace("Z", "+00:00"))
    t1 = datetime.fromisoformat(o["time_window"][1].replace("Z", "+00:00"))
    pad = timedelta(hours=pad_hours)
    return ([b["west"] - lon_pad, b["south"] - lat_pad, b["east"] + lon_pad, b["north"] + lat_pad],
            (t0 - pad, t1 + pad))


def fetch(bbox, start, end, token):
    """One 4wings report, grouped by vessel. Returns the raw row list."""
    params = {
        "datasets[0]": DATASET,
        # the endpoint takes whole days; we filter to the exact window afterwards
        "date-range": f"{start.date()},{(end + timedelta(days=1)).date()}",
        "spatial-resolution": "HIGH",        # 0.01 deg cells
        "temporal-resolution": "HOURLY",
        "spatial-aggregation": "false",      # keep one row per cell, not a box total
        "group-by": "VESSEL_ID",             # carries mmsi, shipName, vesselType, flag, imo
        "format": "JSON",
    }
    url = f"{BASE}/4wings/report?" + urllib.parse.urlencode(params, doseq=True)
    req = urllib.request.Request(url, data=json.dumps({"geojson": geojson_box(bbox)}).encode(),
                                 method="POST")
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("Content-Type", "application/json")
    req.add_header("User-Agent", "udgam-sih2026/1.0")     # Cloudflare rejects urllib's default
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            doc = json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        raise SystemExit(f"GFW returned HTTP {e.code}: {e.read().decode()[:400]}")
    entries = doc.get("entries") or [{}]
    rows = []
    for entry in entries:
        for _key, val in entry.items():
            if val:
                rows.extend(val)
    return rows


def to_records(rows, start, end):
    """GFW rows -> the parquet schema ingest.py writes. Filtered to the padded window."""
    out = []
    for r in rows:
        mmsi = r.get("mmsi")
        if not mmsi or r.get("lat") is None or r.get("lon") is None:
            continue
        try:
            ts = datetime.strptime(r["date"], "%Y-%m-%d %H:%M").replace(tzinfo=timezone.utc)
        except (KeyError, ValueError):
            continue
        if not (start <= ts <= end):
            continue
        out.append({
            "mmsi": str(mmsi),
            "ts": ts,
            "lon": float(r["lon"]),
            "lat": float(r["lat"]),
            # not published by this endpoint; NULL, never derived (see the module docstring)
            "sog": None,
            "cog": None,
            "heading": None,
            "name": (r.get("shipName") or "").strip(),
            "type_code": None,
            "vessel_type": GFW_TYPE.get((r.get("vesselType") or "").upper(), "other"),
            # Per-ROW provenance, not per-file. A merged pool puts NOAA fixes and GFW cells in
            # the SAME track, and component_gap has to ask which rows bound a given silence --
            # a per-track flag cannot answer that.
            "source": "gfw",
        })
    out.sort(key=lambda x: (x["mmsi"], x["ts"]))
    return out


def write_parquet(records, out_path):
    con = duckdb.connect()
    con.execute("SET TimeZone='UTC'")
    con.execute("""
        CREATE TABLE ais (mmsi VARCHAR, ts TIMESTAMPTZ, lon DOUBLE, lat DOUBLE,
                          sog DOUBLE, cog DOUBLE, heading DOUBLE, name VARCHAR,
                          type_code INTEGER, vessel_type VARCHAR, source VARCHAR)
    """)
    if records:
        con.executemany(
            "INSERT INTO ais VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            [(r["mmsi"], r["ts"], r["lon"], r["lat"], r["sog"], r["cog"], r["heading"],
              r["name"], r["type_code"], r["vessel_type"], r.get("source", "gfw"))
             for r in records])
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    con.execute("COPY ais TO ? (FORMAT PARQUET)", [str(out_path)])
    con.close()


def main():
    ap = argparse.ArgumentParser(description="Stage 3 — AIS ingest from Global Fishing Watch")
    ap.add_argument("--case", help="case id under cases/; uses its origin.json for box and window")
    ap.add_argument("--bbox", nargs=4, type=float, metavar=("W", "S", "E", "N"))
    ap.add_argument("--start", help="UTC ISO 8601 with trailing Z")
    ap.add_argument("--end", help="UTC ISO 8601 with trailing Z")
    ap.add_argument("--pad-hours", type=float, default=6.0)
    ap.add_argument("--out", required=True, help="output .parquet path")
    ap.add_argument("--allow-empty", action="store_true",
                    help="write an empty parquet when GFW returns nothing, so score.py records a "
                         "searched negative ('queried, found empty') instead of the case staying "
                         "on --no-ais ('nothing searched')")
    a = ap.parse_args()

    if bool(a.case) == bool(a.bbox):
        raise SystemExit("pass exactly one of --case or --bbox")

    if a.case:
        bbox, (start, end) = window_from_origin(REPO / "cases" / a.case / "origin.json",
                                                a.pad_hours)
    else:
        bbox = a.bbox
        if not (a.start and a.end):
            raise SystemExit("--bbox needs --start and --end")
        start = datetime.fromisoformat(a.start.replace("Z", "+00:00"))
        end = datetime.fromisoformat(a.end.replace("Z", "+00:00"))

    token = load_token()
    print(f"box       {bbox[0]:.4f} {bbox[1]:.4f} {bbox[2]:.4f} {bbox[3]:.4f}")
    print(f"window    {start:%Y-%m-%dT%H:%M:%SZ} .. {end:%Y-%m-%dT%H:%M:%SZ}")
    rows = fetch(bbox, start, end, token)
    records = to_records(rows, start, end)
    if not records and not a.allow_empty:
        raise SystemExit("GFW returned no vessel-hours in that box and window. That is a result, "
                         "not a crash — rerun with --allow-empty to record it as a searched "
                         "negative.")
    write_parquet(records, a.out)
    if not records:
        print(f"\nrows      0 — GFW returned no vessel-hours; wrote an EMPTY extract to {a.out}")
        print("score.py will record this as a searched negative, not as 'nothing searched'.")
        return 0

    vessels = {r["mmsi"] for r in records}
    types = {}
    for r in records:
        types[r["vessel_type"]] = types.get(r["vessel_type"], 0) + 1
    print(f"\nrows      {len(records)} vessel-hours from {len(rows)} raw rows")
    print(f"vessels   {len(vessels)} distinct MMSI")
    print(f"types     " + ", ".join(f"{k} {v}" for k, v in sorted(types.items())))
    print(f"wrote     {a.out}")
    print("\nsog/cog are NULL by design — GFW does not publish them here, and a course derived")
    print("from 1 km cell centres an hour apart is not a measurement. gap and slowdown gate to")
    print("null on any gfw_hourly case anyway (D20).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
