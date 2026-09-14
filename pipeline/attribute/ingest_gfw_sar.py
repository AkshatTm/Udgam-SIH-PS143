#!/usr/bin/env python3
"""
Stage 3 — external radar contacts from Global Fishing Watch's Sentinel-1 vessel detections.

    python pipeline/attribute/ingest_gfw_sar.py --case case-gulf-alaska-2023 \
           --out data/ais/gulf-alaska_sar_contacts.json

WHY THIS EXISTS (D42). On Gulf of Alaska our own ship detector finds no contact: the brightest
water pixel sits below its threshold and the exported box is small (docs/updates/soumirya.md).
Lowering the threshold to manufacture one would be inventing a detection. GFW runs its own
detector over every Sentinel-1 pass, and its output is public and independent of us. We take the
contacts from the SAME pass (acquisition time +/- a few minutes) and run OUR AIS cross-check on
them (dark.py). Every card built from these says, in its name and its first reason, that the
contact is GFW's and not UDGAM's detector.

WHAT IS DELIBERATELY DROPPED
    GFW attaches its own AIS identity to contacts it matched (mmsi, shipName, ...). That is their
    cross-check, not ours, so it is discarded here: only position and time are kept, and dark.py
    decides matched/unmatched against the AIS extract we hold. Cerulean's contact is never used.

WHAT THE POSITIONS ARE
    4wings report cells at HIGH resolution: 0.01 deg cell centres, ~1 km of quantisation. No
    length estimate is published on this endpoint, so `length_m` is null, never guessed.

Non-commercial licence (GFW), stated on the provenance slide. Stdlib only.
"""
import argparse
import json
import math
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO / "scripts"))

from gfw_probe import call, geojson_box, load_token          # noqa: E402

DATASET = "public-global-sar-presence:latest"
SAME_PASS_MINUTES = 10     # an S1 IW slice is ~25 s; anything this close is the same acquisition
PAD_KM = 15.0              # contacts just off the exported box can still sit near the origin


def parse_ts(s):
    dt = datetime.fromisoformat(str(s).replace("Z", "+00:00"))
    if dt.tzinfo is None:
        raise SystemExit(f"'{s}' is timezone-naive — every timestamp needs the trailing Z")
    return dt.astimezone(timezone.utc)


def padded_box(bounds, pad_km):
    mid = math.radians((bounds["south"] + bounds["north"]) / 2.0)
    dlat = pad_km / 111.32
    dlon = pad_km / (111.32 * max(math.cos(mid), 0.01))
    return [bounds["west"] - dlon, bounds["south"] - dlat,
            bounds["east"] + dlon, bounds["north"] + dlat]


def main():
    ap = argparse.ArgumentParser(description="GFW Sentinel-1 vessel detections for one scene")
    ap.add_argument("--case", required=True, help="case id under cases/")
    ap.add_argument("--out", required=True, help="output .json path")
    ap.add_argument("--pad-km", type=float, default=PAD_KM)
    a = ap.parse_args()

    case_dir = REPO / "cases" / a.case
    meta = json.loads((case_dir / "meta.json").read_text(encoding="utf-8"))
    bounds = json.loads((case_dir / "bounds.json").read_text(encoding="utf-8"))
    t0 = parse_ts(meta["detection_time"])
    box = padded_box(bounds, a.pad_km)

    params = {
        "datasets[0]": DATASET,
        "date-range": f"{t0.date()},{(t0 + timedelta(days=1)).date()}",
        "spatial-resolution": "HIGH",
        "temporal-resolution": "HOURLY",
        "spatial-aggregation": "false",
        "format": "JSON",
    }
    ok, res = call("/4wings/report", load_token(), method="POST", params=params,
                   body={"geojson": geojson_box(box)})
    if not ok:
        raise SystemExit(f"GFW SAR presence request failed:\n{res}")

    rows = []
    for entry in res.get("entries") or []:
        for _k, v in entry.items():
            rows.extend(v or [])

    contacts = []
    for r in rows:
        ts = r.get("entryTimestamp")
        if r.get("lat") is None or r.get("lon") is None or not ts:
            continue
        when = parse_ts(ts)
        if abs((when - t0).total_seconds()) > SAME_PASS_MINUTES * 60:
            continue
        contacts.append({
            "lon": round(float(r["lon"]), 5),
            "lat": round(float(r["lat"]), 5),
            "timestamp": when.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "length_m": None,
        })

    doc = {
        "source": "Global Fishing Watch, public-global-sar-presence (Sentinel-1 vessel detections)",
        "licence": "GFW non-commercial",
        "scene_time": t0.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "box": [round(x, 5) for x in box],
        "note": "positions are 0.01 deg cell centres; GFW's own AIS identity is discarded",
        "contacts": contacts,
    }
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text(json.dumps(doc, indent=2), encoding="utf-8")
    print(f"box       {box[0]:.4f} {box[1]:.4f} {box[2]:.4f} {box[3]:.4f}")
    print(f"rows      {len(rows)} raw, {len(contacts)} on the same pass (+/-{SAME_PASS_MINUTES} min)")
    print(f"wrote     {a.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
