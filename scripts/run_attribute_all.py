#!/usr/bin/env python3
"""
Run Stage 3 end to end on every attribute case, and validate each bundle.

    python scripts/run_attribute_all.py                      # use extracts already in data/ais/
    python scripts/run_attribute_all.py --refresh --csv-dir <unzipped NOAA CSVs>
    python scripts/run_attribute_all.py --only case-mumbai-2023

Per case, subprocesses only (no stage imports another — CLAUDE.md):
  1. AIS for the origin window        ingest.py (NOAA, US)  /  ingest_gfw.py --case (GFW)
  2. AIS at scene time over the scene ingest.py --bbox       /  ingest_gfw.py --bbox
  3. external radar contacts          ingest_gfw_sar.py (Gulf of Alaska only, D42)
  4. score.py                         writes suspects.json + vessels.geojson INTO the case folder
  5. validate_case.py

Never run build_case.py for `attribute`: pipeline/attribute/out/ holds the stub's fake fleet and
would overwrite these bundles.

Extracts are reused when present; --refresh re-downloads GFW and re-filters NOAA (which needs the
unzipped daily CSVs, since data/ is not moved between laptops).
"""
import argparse
import json
import math
import subprocess
import sys
import zipfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
PY = sys.executable
ATTR = REPO / "pipeline" / "attribute"
AIS = REPO / "data" / "ais"

SCENE_PAD_KM = {"noaa_dense": 10.0, "gfw_hourly": 30.0}
SCENE_HALF_WINDOW_MIN = {"noaa_dense": 90, "gfw_hourly": 120}

# case id -> short name used for data/ais/<name>*.parquet, and the NOAA daily files it needs
CASES = {
    "case-jacksonville-2024": ("jacksonville", ["AIS_2024_07_29.csv", "AIS_2024_07_30.csv"]),
    "case-farallones-2023":   ("farallones",   ["AIS_2023_03_16.csv", "AIS_2023_03_17.csv"]),
    "case-huntington-2021":   ("huntington",   ["AIS_2021_10_01.csv", "AIS_2021_10_02.csv"]),
    "case-mumbai-2023":       ("mumbai",       None),
    "case-jamnagar-2024":     ("jamnagar",     None),
    "case-gulf-alaska-2023":  ("gulf-alaska",  None),
}
EXTERNAL_SAR = {"case-gulf-alaska-2023"}


def iso(dt):
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def run(cmd):
    printable = " ".join(f'"{c}"' if " " in str(c) else str(c) for c in cmd)
    print(f"\n$ {printable}", flush=True)
    r = subprocess.run([str(c) for c in cmd], cwd=REPO)
    if r.returncode != 0:
        raise SystemExit(f"step failed (exit {r.returncode}): {printable}")


def noaa_csvs(days, csv_dir):
    """The unzipped NOAA daily CSVs, extracting them from data/ais/*.zip when needed.

    The zips are what actually travels (data/ is gitignored and inputs stay put, CLAUDE.md), and
    each unzips to ~1 GB, so they are expanded once into data/ais/_csv/ and reused. --csv-dir
    overrides when the CSVs already live somewhere else.
    """
    if csv_dir:
        return [Path(csv_dir) / d for d in days]
    out = AIS / "_csv"
    out.mkdir(parents=True, exist_ok=True)
    paths = []
    for d in days:
        csv = out / d
        if not csv.exists():
            zip_path = AIS / d.replace(".csv", ".zip")
            if not zip_path.exists():
                raise SystemExit(
                    f"missing {csv} and {zip_path}.\n"
                    f"  Download the NOAA daily file from marinecadastre.gov/accessais into "
                    f"data/ais/, or pass --csv-dir with the unzipped CSVs.")
            print(f"\n# unzipping {zip_path.name} -> {out}", flush=True)
            with zipfile.ZipFile(zip_path) as z:
                z.extractall(out)
        paths.append(csv)
    return paths


def scene_box(bounds, pad_km):
    mid = math.radians((bounds["south"] + bounds["north"]) / 2.0)
    dlat = pad_km / 111.32
    dlon = pad_km / (111.32 * max(math.cos(mid), 0.01))
    return [round(bounds["west"] - dlon, 4), round(bounds["south"] - dlat, 4),
            round(bounds["east"] + dlon, 4), round(bounds["north"] + dlat, 4)]


def one_case(case_id, refresh, csv_dir):
    name, noaa_days = CASES[case_id]
    case_dir = REPO / "cases" / case_id
    meta = json.loads((case_dir / "meta.json").read_text(encoding="utf-8"))
    bounds = json.loads((case_dir / "bounds.json").read_text(encoding="utf-8"))
    src = meta["ais_source"]
    t0 = datetime.fromisoformat(meta["detection_time"].replace("Z", "+00:00")).astimezone(timezone.utc)

    print(f"\n{'=' * 78}\n{case_id}   ais_source {src}\n{'=' * 78}")
    origin_pq = AIS / f"{name}.parquet"
    scene_pq = AIS / f"{name}_scene.parquet"
    half = timedelta(minutes=SCENE_HALF_WINDOW_MIN[src])
    box = scene_box(bounds, SCENE_PAD_KM[src])

    if src == "noaa_dense":
        need_csv = refresh or not origin_pq.exists() or not scene_pq.exists()
        csvs = noaa_csvs(noaa_days, csv_dir) if need_csv else []
        if refresh or not origin_pq.exists():
            run([PY, ATTR / "ingest.py", "--csv", *[c for c in csvs if c.exists()],
                 "--from-origin", case_dir / "origin.json", "--out", origin_pq])
        if refresh or not scene_pq.exists():
            day = [c for c in csvs if t0.strftime("%Y_%m_%d") in c.name and c.exists()]
            run([PY, ATTR / "ingest.py", "--csv", *day, "--bbox", *box,
                 "--start", iso(t0 - half), "--end", iso(t0 + half), "--out", scene_pq])
    else:
        if refresh or not origin_pq.exists():
            run([PY, ATTR / "ingest_gfw.py", "--case", case_id, "--allow-empty", "--out", origin_pq])
        if refresh or not scene_pq.exists():
            run([PY, ATTR / "ingest_gfw.py", "--bbox", *box, "--start", iso(t0 - half),
                 "--end", iso(t0 + half), "--allow-empty", "--out", scene_pq])

    # D48 -- the merged pool. On a dense-AIS case we ALSO pass the hourly presence extract,
    # when one has been fetched. It adds almost no new candidates (measured: 5 / 1 / 90 on the
    # three US cases, all of them tugs, buoy tenders, fishing boats and pleasure craft), and
    # that is not what it is for. It is for telling a transponder gap apart from a receiver
    # coverage hole: NOAA Marine Cadastre is a terrestrial network, and offshore a vessel can
    # be transmitting normally and simply not be heard.
    pool = [origin_pq]
    gfw_pq = AIS / f"{name}_gfw.parquet"
    if src == "noaa_dense" and gfw_pq.exists():
        pool.append(gfw_pq)
    score = [PY, ATTR / "score.py", "--case", case_id, "--parquet", *pool,
             "--scene-parquet", scene_pq]
    if case_id in EXTERNAL_SAR:
        sar = AIS / f"{name}_sar_contacts.json"
        if refresh or not sar.exists():
            run([PY, ATTR / "ingest_gfw_sar.py", "--case", case_id, "--out", sar])
        score += ["--sar-contacts", sar]
    run(score)
    run([PY, REPO / "scripts" / "validate_case.py", case_dir])


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    ap.add_argument("--only", nargs="+", choices=sorted(CASES))
    ap.add_argument("--refresh", action="store_true")
    ap.add_argument("--csv-dir", help="directory holding the unzipped NOAA daily CSVs")
    a = ap.parse_args()
    for case_id in (a.only or CASES):
        one_case(case_id, a.refresh, a.csv_dir)
    print("\nall attribute cases scored and validated")


if __name__ == "__main__":
    main()
