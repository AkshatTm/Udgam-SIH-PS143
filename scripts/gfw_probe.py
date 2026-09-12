#!/usr/bin/env python3
"""
gfw_probe.py — does Global Fishing Watch actually cover our Indian cases? Owner: Akshat.

    python scripts/gfw_probe.py --case case-jamnagar-2024
    python scripts/gfw_probe.py --date 2023-09-03 --bbox 72.09 18.40 72.27 18.61
    python scripts/gfw_probe.py --all            # both Indian cases, one run

Cases 5 and 6 are `gfw_hourly` (Master §6.1, D20). This script answers the one question that
decides whether they keep the `attribute` act at all: **is there usable AIS-derived data over
the Arabian Sea on 2023-09-03 and 2024-02-23?**

If the answer is no, those two cases drop to `detect + trace` and the Indian screen becomes the
stronger story from 01_AKSHAT_INTEGRATION Part I — a backward reconstruction that yields a
course, a speed and an outbound track, reducing an unsolved discharge to a single database
query, and then showing that the query cannot be run.

>>> STATUS: written against GFW's documented v3 API but NOT yet run against it — there was no
>>> token on disk when it was written. Expect one round of fixing (dataset ids and the report
>>> body are the likely culprits). Every response is printed raw on failure so the fix is
>>> obvious rather than guessed. Treat the 45-minute rule as applying here.

**The correction this script exists to respect.** A report in circulation claims GFW's AIS
Vessel Presence dataset returns MMSI, name, IMO and positions. It does not — GFW's own docs say
it "shows vessel presence patterns and movement corridors, but does not provide individual
vessel positions". It is a gridded layer. So:

  * 4wings report on the presence layer -> IS THERE TRAFFIC HERE AT ALL (a grid, not tracks)
  * Vessels API                         -> identity lookup
  * Events API, gap events              -> AIS-disabling, computed on GFW's full-resolution
                                           data, so gap analysis may be reachable through
                                           that endpoint even though it is impossible from
                                           the hourly presence layer

Token: put it in .env at the repo root as GFW_API_TOKEN=... (.env is gitignored). Free, but
NON-COMMERCIAL USE ONLY — that condition is real and it belongs on the provenance slide.
"""
import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
BASE = "https://gateway.api.globalfishingwatch.org/v3"
TIMEOUT = 90

# The two cases this exists for. bbox = the exported scene box (see cases/<id>/bounds.json).
INDIAN_CASES = {
    "case-mumbai-2023":   ("2023-09-03", [72.0863, 18.4023, 72.2678, 18.6072]),
    "case-jamnagar-2024": ("2024-02-23", [71.8138, 20.0934, 71.9436, 20.2359]),
}


def load_token():
    tok = os.environ.get("GFW_API_TOKEN")
    if tok:
        return tok.strip()
    env = REPO / ".env"
    if env.exists():
        for line in env.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line.startswith("GFW_API_TOKEN="):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    raise SystemExit(
        "No GFW_API_TOKEN.\n"
        "  1. https://globalfishingwatch.org/our-apis/tokens — free, non-commercial only\n"
        f"  2. put it in {env} as:  GFW_API_TOKEN=eyJ...\n"
        "  .env is gitignored, so it will not be pushed.")


def call(path, token, method="GET", body=None, params=None):
    url = f"{BASE}{path}"
    if params:
        from urllib.parse import urlencode
        url += "?" + urlencode(params, doseq=True)
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("Accept", "application/json")
    if data:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            return True, json.load(r)
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")[:600]
        return False, f"HTTP {e.code} {e.reason}\n      {url}\n      {detail}"
    except Exception as e:
        return False, f"{type(e).__name__}: {e}\n      {url}"


def geojson_box(bbox):
    w, s, e, n = bbox
    return {"type": "Polygon",
            "coordinates": [[[w, s], [e, s], [e, n], [w, n], [w, s]]]}


def probe(label, date, bbox, token, window_days):
    from datetime import datetime, timedelta, timezone
    d0 = datetime.strptime(date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    start = (d0 - timedelta(days=window_days)).strftime("%Y-%m-%d")
    end = (d0 + timedelta(days=window_days)).strftime("%Y-%m-%d")
    w, s, e, n = bbox
    print(f"\n=== {label} ===")
    print(f"  date {date}  window {start}..{end}  bbox {w} {s} {e} {n}")

    verdict = {}

    # 1. Presence: is there any AIS-derived traffic in this box at all?
    ok, res = call("/4wings/report", token, method="POST",
                   params={"datasets[0]": "public-global-presence:latest",
                           "date-range": f"{start},{end}",
                           "spatial-resolution": "HIGH",
                           "temporal-resolution": "DAILY",
                           "group-by": "VESSEL_ID",
                           "format": "JSON"},
                   body={"geojson": geojson_box(bbox)})
    if ok:
        rows = res.get("entries") or res.get("data") or res
        n_rows = len(rows) if isinstance(rows, list) else "?"
        print(f"  presence      OK — {n_rows} grouped entr(ies)")
        verdict["presence"] = n_rows
    else:
        print(f"  presence      FAILED\n      {res}")
        verdict["presence"] = None

    # 2. AIS-disabling ("gap") events — the only route to gap analysis on GFW data
    ok, res = call("/events", token,
                   params={"datasets[0]": "public-global-gaps-events:latest",
                           "start-date": start, "end-date": end,
                           "limit": 50, "offset": 0})
    if ok:
        total = res.get("total", len(res.get("entries", [])))
        print(f"  gap events    OK — {total} AIS-disabling event(s) returned "
              f"(NOTE: unfiltered by bbox unless the endpoint accepts a region body)")
        verdict["gaps"] = total
    else:
        print(f"  gap events    FAILED\n      {res}")
        verdict["gaps"] = None

    # 3. SAR detections — use to VALIDATE Soum's ship detector, never to replace it
    ok, res = call("/4wings/report", token, method="POST",
                   params={"datasets[0]": "public-global-sar-presence:latest",
                           "date-range": f"{start},{end}",
                           "spatial-resolution": "HIGH",
                           "temporal-resolution": "DAILY", "format": "JSON"},
                   body={"geojson": geojson_box(bbox)})
    print(f"  sar presence  {'OK' if ok else 'FAILED'}"
          + ("" if ok else f"\n      {res}"))
    verdict["sar"] = ok
    return verdict


def main():
    ap = argparse.ArgumentParser(description="Probe GFW coverage for the Indian cases")
    ap.add_argument("--case", help="case id from cases/ (uses its date and export box)")
    ap.add_argument("--all", action="store_true", help="probe both Indian cases")
    ap.add_argument("--date", help="YYYY-MM-DD")
    ap.add_argument("--bbox", nargs=4, type=float, metavar=("W", "S", "E", "N"))
    ap.add_argument("--window-days", type=int, default=1,
                    help="days either side of the date (default 1)")
    a = ap.parse_args()

    token = load_token()
    print(f"GFW v3 API — token loaded ({len(token)} chars). Non-commercial use only.")

    targets = []
    if a.all:
        targets = [(cid, d, b) for cid, (d, b) in INDIAN_CASES.items()]
    elif a.case:
        if a.case not in INDIAN_CASES:
            raise SystemExit(f"{a.case} is not a gfw_hourly case. Known: "
                             f"{', '.join(INDIAN_CASES)}")
        d, b = INDIAN_CASES[a.case]
        targets = [(a.case, d, b)]
    elif a.date and a.bbox:
        targets = [("ad-hoc", a.date, a.bbox)]
    else:
        raise SystemExit("give --all, or --case <id>, or --date plus --bbox")

    results = {lbl: probe(lbl, d, b, token, a.window_days) for lbl, d, b in targets}

    print("\n" + "-" * 70)
    usable = [k for k, v in results.items() if v.get("presence")]
    if len(usable) == len(results):
        print("GFW answers for every probed case. Cases 5 and 6 keep 'attribute' —")
        print("but gap and slowdown STILL return null at hourly sampling (D20), and the")
        print("frontend renders them 'n/a'. That is a data property, not a bug.")
    elif usable:
        print(f"Partial: {', '.join(usable)} answered; the rest did not.")
        print("Decide per case whether 'attribute' stays in acts_available.")
    else:
        print("No usable GFW coverage. Cases 5 and 6 drop to detect + trace, and the Indian")
        print("screen becomes the stronger story: a reconstruction that yields a course, a")
        print("speed and an outbound track — one database query away from a name, and the")
        print("database does not exist. See 01_AKSHAT_INTEGRATION Part I.")
    print("Record whatever happened in docs/receipts.md and docs/updates/_INTEGRATION.md.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
