#!/usr/bin/env python3
"""
test_validator.py — prove the validator actually catches things.

    python scripts/test_validator.py

`validate_case.py` is the most load-bearing file in this repo: six people trust its PASS before
handing work over. A validator that passes everything is worse than no validator, because it
converts "unchecked" into "checked and fine".

So: copy a known-good bundle, break it in one specific way, and assert the validator FAILS and
names the problem. Each mutation is a real bug from docs/TRAPS.md that has cost other teams days.

Requires cases/case-000 to exist and pass. Regenerate it with:
    python scripts/make_case000.py
"""
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
VALIDATOR = REPO / "scripts" / "validate_case.py"
GOLDEN = REPO / "cases" / "case-000"


def run_validator(case_dir):
    r = subprocess.run([sys.executable, str(VALIDATOR), str(case_dir)],
                       capture_output=True, text=True)
    return r.returncode, r.stdout + r.stderr


def read(d, name):
    return json.loads((d / name).read_text())


def write(d, name, obj):
    (d / name).write_text(json.dumps(obj))


# ---------------------------------------------------------------- mutations

def swap_detection_lonlat(d):
    """TRAPS #1 — the [lat, lon] swap. Every human instinct says lat-lon; GeoJSON says lon-lat."""
    g = read(d, "detections.geojson")
    f = g["features"][0]
    f["geometry"]["coordinates"] = [[[pt[1], pt[0]] for pt in ring]
                                    for ring in f["geometry"]["coordinates"]]
    f["properties"]["centroid"] = [f["properties"]["centroid"][1],
                                   f["properties"]["centroid"][0]]
    write(d, "detections.geojson", g)
    return "swapped"


def naive_timestamp(d):
    """TRAPS #6 — a naive datetime that silently compares as if it were UTC, until it doesn't."""
    p = read(d, "particles.json")
    p["t0"] = p["t0"].replace("Z", "")
    write(d, "particles.json", p)
    return "timezone-naive"


def hycom_misscaled(d):
    """TRAPS #2 — HYCOM on GEE is int x 0.001 m/s. Get the scaling wrong and particles cross
    an ocean in a day. (x100 here is deliberately extreme; the real 2026-09-07 bug was x10.)"""
    p = read(d, "particles.json")
    o = p["positions"][0]
    p["positions"] = [[[o[i][0] + (pt[0] - o[i][0]) * 100,
                        o[i][1] + (pt[1] - o[i][1]) * 100]
                       for i, pt in enumerate(step)] for step in p["positions"]]
    write(d, "particles.json", p)
    return "units"


def funnel_increases(d):
    """The funnel IS requirement (c) on screen. Counts that go up mean the filter is wrong."""
    s = read(d, "suspects.json")
    s["funnel"]["plausible"] = s["funnel"]["in_window"] + 10
    write(d, "suspects.json", s)
    return "funnel"


def origin_grid_size_lies(d):
    """TRAPS #9 — shape and values disagreeing is how a flipped or F-ordered grid shows up."""
    o = read(d, "origin.json")
    o["values"] = o["values"][:-5]
    write(d, "origin.json", o)
    return "shape"


def suspect_not_in_ais(d):
    """The honesty rule, mechanised: no vessel on screen that isn't in the real AIS file."""
    s = read(d, "suspects.json")
    s["suspects"][0]["mmsi"] = "000000000"
    write(d, "suspects.json", s)
    return "no track in vessels.geojson"


MUTATIONS = [
    ("detection polygon written as [lat, lon]", swap_detection_lonlat, "swapped"),
    ("particles.t0 missing its trailing Z",     naive_timestamp,       "naive"),
    ("particle drift mis-scaled (x100)",        hycom_misscaled,       "units"),
    ("funnel counts increasing",                funnel_increases,      "funnel"),
    ("origin values shorter than shape",        origin_grid_size_lies, "shape"),
    ("suspect MMSI absent from vessels.geojson", suspect_not_in_ais,   "vessels.geojson"),
]


def main():
    if not GOLDEN.is_dir():
        raise SystemExit(f"{GOLDEN} not found. Run:  python scripts/make_case000.py")

    rc, out = run_validator(GOLDEN)
    if rc != 0:
        print(out)
        raise SystemExit("The golden bundle itself does not pass. Fix that before testing "
                         "the mutations — every result below would be meaningless.")
    print(f"golden bundle {GOLDEN.name} passes\n")

    passed = 0
    for label, mutate, expect in MUTATIONS:
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp) / "case-mutant"
            shutil.copytree(GOLDEN, d)
            mutate(d)
            rc, out = run_validator(d)

            if rc == 0:
                print(f"  MISSED  {label}")
                print(f"          validator returned PASS on a bundle broken this way")
            elif expect.lower() not in out.lower():
                print(f"  VAGUE   {label}")
                print(f"          correctly failed, but the message never mentions "
                      f"'{expect}' — someone debugging this will not know where to look")
            else:
                print(f"  caught  {label}")
                passed += 1

    print(f"\n{passed}/{len(MUTATIONS)} mutations correctly caught and named")
    if passed != len(MUTATIONS):
        print("The validator is not the safety net it is being trusted as. Fix it before "
              "anyone relies on a PASS.")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
