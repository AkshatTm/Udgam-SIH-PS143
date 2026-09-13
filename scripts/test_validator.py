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


def run_validator(case_dir, strict=False):
    cmd = [sys.executable, str(VALIDATOR), str(case_dir)]
    if strict:
        cmd.append("--strict")
    r = subprocess.run(cmd, capture_output=True, text=True)
    return r.returncode, r.stdout + r.stderr


def read(d, name):
    return json.loads((d / name).read_text(encoding="utf-8"))


def write(d, name, obj):
    (d / name).write_text(json.dumps(obj), encoding="utf-8")


VALID_VERIFICATION = {
    "official_finding": {
        "summary": "Test finding.", "responsible_parties": [{"name": "X", "mmsi": None}],
        "source_name": "Test", "source_url": "https://example.gov/report",
        "source_type": "official_investigation", "volume_reported": "1 bbl", "caveat": "none",
    },
    "naap_result": {"origin_summary": "Test.", "top_suspects": [], "abstained": False},
    "assessment": {"verdict": "not_applicable", "explanation": "Test prose.",
                   "what_would_have_helped": "n/a"},
}


def add_verify_act(d):
    m = read(d, "meta.json")
    if "verify" not in m["acts_available"]:
        m["acts_available"].append("verify")
    write(d, "meta.json", m)


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


def detection_not_polygon(d):
    """A detection geometry that isn't a Polygon — a LineString slick can't be measured."""
    g = read(d, "detections.geojson")
    f = g["features"][0]
    f["geometry"] = {"type": "LineString", "coordinates": f["geometry"]["coordinates"][0]}
    write(d, "detections.geojson", g)
    return "Polygon"


def area_km2_wrong(d):
    """area_km2 that disagrees with the polygon it belongs to — a units or axis slip."""
    g = read(d, "detections.geojson")
    g["features"][0]["properties"]["area_km2"] = 0.2
    write(d, "detections.geojson", g)
    return "area_km2"


def verify_verdict_invalid(d):
    """verification.json with a verdict outside hit|partial|miss|not_applicable."""
    add_verify_act(d)
    v = json.loads(json.dumps(VALID_VERIFICATION))
    v["assessment"]["verdict"] = "correct"
    write(d, "verification.json", v)
    return "verdict"


def verify_missing_source_url(d):
    """'verify' act with an empty source_url — the 'is this real?' link is the whole point."""
    add_verify_act(d)
    v = json.loads(json.dumps(VALID_VERIFICATION))
    v["official_finding"]["source_url"] = ""
    write(d, "verification.json", v)
    return "source_url"


def trace_without_known_origin(d):
    """D16 — a trace bundle with no 'detect' act and no meta.known_origin has nothing to
    seed the rewind from."""
    m = read(d, "meta.json")
    m["acts_available"] = [a for a in m["acts_available"] if a != "detect"]
    m.pop("known_origin", None)
    write(d, "meta.json", m)
    return "known_origin"


def known_origin_lonlat_swapped(d):
    """meta.known_origin written as [lat, lon] — the same swap the coordinate checker
    catches everywhere else, now on the documented fixed source."""
    m = read(d, "meta.json")
    b = read(d, "bounds.json")
    lon = (b["west"] + b["east"]) / 2
    lat = (b["south"] + b["north"]) / 2
    m["known_origin"] = [lat, lon]  # deliberately swapped
    write(d, "meta.json", m)
    return "swapped"


def dark_vessel_has_mmsi(d):
    """A dark vessel is radar-only — giving it an MMSI invents an AIS identity."""
    s = read(d, "suspects.json")
    s["dark_vessels"] = [{"source_type": "dark_vessel", "name": "Radar contact",
                          "lon": 80.4, "lat": 13.2, "score": 0.6, "mmsi": "123456789"}]
    write(d, "suspects.json", s)
    return "mmsi must be null"


def ais_source_missing(d):
    """'attribute' without ais_source. The scorer cannot know whether gap and slowdown are
    even measurable, so every component score becomes uninterpretable (D20)."""
    m = read(d, "meta.json")
    m.pop("ais_source", None)
    write(d, "meta.json", m)
    return "ais_source"


def gfw_hourly_reports_a_gap(d):
    """The honesty bug this whole rule exists for: at one position per vessel per hour you
    cannot observe a 30-minute transponder silence. A number here is not a low score — it is
    a measurement that was never made."""
    m = read(d, "meta.json")
    m["ais_source"] = "gfw_hourly"
    write(d, "meta.json", m)
    s = read(d, "suspects.json")
    s["suspects"][0].setdefault("components", {})["gap"] = 0.0
    write(d, "suspects.json", s)
    return "null"


def forward_particles_are_a_copy(d):
    """particles_forward.json relabelled from the rewind instead of integrated forwards."""
    p = read(d, "particles.json")
    write(d, "particles_forward.json", p)
    return "forward"


def seep_flagged_without_a_source(d):
    """A natural-seep flag with nothing behind it — the exact claim we could not substantiate
    on Mumbai. 'Some of this may be geological' needs a citation or it does not go on screen."""
    s = read(d, "suspects.json")
    s["natural_seep"] = {"flagged": True, "source": "", "note": ""}
    write(d, "suspects.json", s)
    return "natural_seep"


def component_note_names_nothing(d):
    """A note explaining a bar that does not exist. Either the component was renamed and the
    note was left behind, or the note is inventing a component the card never shows."""
    s = read(d, "suspects.json")
    sus = s["suspects"][0]
    sus.setdefault("components", {})
    sus["component_notes"] = {"kraken_index": "no kraken detected in the window"}
    write(d, "suspects.json", s)
    return "component_notes.kraken_index"


def null_component_without_a_note(d):
    """A gated component with nothing behind it. The card renders 'n/a' and the judge asks why —
    which is the one question we should always be able to answer (D29)."""
    s = read(d, "suspects.json")
    sus = s["suspects"][0]
    sus.setdefault("components", {})["slowdown"] = None
    sus.pop("component_notes", None)
    write(d, "suspects.json", s)
    return "component_notes"


def component_is_constant_across_the_fleet(d):
    """type_prior = 1.00 for every vessel in an offshore lane. It ranks nobody above anybody and
    silently adds its full weight to every score on screen (D28)."""
    s = read(d, "suspects.json")
    for sus in s["suspects"]:
        sus.setdefault("components", {})["type_prior"] = 1.0
        sus.setdefault("component_notes", {})
    write(d, "suspects.json", s)
    return "separates nobody"


def vessel_track_lonlat_swapped(d):
    """TRAPS #1 on the attribute layer. Trace and vessel layers are checked against physical
    reach (hundreds of km), not the tight scene box, and the swap must still be caught there."""
    v = read(d, "vessels.geojson")
    f = v["features"][0]
    f["geometry"]["coordinates"] = [[pt[1], pt[0]] for pt in f["geometry"]["coordinates"]]
    write(d, "vessels.geojson", v)
    return "swapped"


def origin_in_the_wrong_hemisphere(d):
    """A sign flip on longitude: the origin lands an ocean away. The reach box is generous
    enough for a Gulf Stream rewind, and must still not be generous enough to hide this."""
    o = read(d, "origin.json")
    o["centroid"] = [-o["centroid"][0], o["centroid"][1]]
    write(d, "origin.json", o)
    return "km of the scene"


MUTATIONS = [
    ("detection polygon written as [lat, lon]", swap_detection_lonlat,   "swapped",  False),
    ("particles.t0 missing its trailing Z",     naive_timestamp,         "naive",    False),
    ("particle drift mis-scaled (x100)",        hycom_misscaled,         "units",    False),
    ("funnel counts increasing",                funnel_increases,        "funnel",   False),
    ("origin values shorter than shape",        origin_grid_size_lies,   "shape",    False),
    ("suspect MMSI absent from vessels.geojson", suspect_not_in_ais,     "vessels.geojson", False),
    ("detection geometry is not a Polygon",     detection_not_polygon,   "Polygon",  False),
    ("area_km2 disagrees with its polygon",     area_km2_wrong,          "area_km2", True),
    ("verification verdict not in the 4 values", verify_verdict_invalid, "verdict",  False),
    ("verification source_url empty",           verify_missing_source_url, "source_url", False),
    ("dark vessel carries an invented MMSI",    dark_vessel_has_mmsi,    "mmsi must be null", False),
    ("trace act with no detect and no known_origin", trace_without_known_origin, "known_origin", False),
    ("meta.known_origin written as [lat, lon]", known_origin_lonlat_swapped, "swapped", False),
    ("attribute act with no ais_source",        ais_source_missing,      "ais_source", False),
    ("gfw_hourly case reports a numeric gap",   gfw_hourly_reports_a_gap, "null",    False),
    ("particles_forward is a copy of the rewind", forward_particles_are_a_copy, "forward", False),
    ("natural_seep flagged with no source",     seep_flagged_without_a_source, "natural_seep", False),
    ("component_notes names a component that doesn't exist", component_note_names_nothing,
     "component_notes.kraken_index", False),
    ("null component with no note behind it",   null_component_without_a_note, "component_notes", True),
    ("a component scoring identically for every suspect", component_is_constant_across_the_fleet,
     "separates nobody", True),
    ("vessel track written as [lat, lon]",      vessel_track_lonlat_swapped, "swapped", False),
    ("origin centroid in the wrong hemisphere", origin_in_the_wrong_hemisphere,
     "km of the scene", True),
]


def test_index():
    """cases/index.json that lists a case with no meta.json on disk."""
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp) / "cases"
        shutil.copytree(GOLDEN, root / "case-000")
        (root / "index.json").write_text(
            json.dumps({"cases": ["case-000", "case-ghost"], "default": "case-000"}))
        rc, out = run_validator(root)
        ok = rc != 0 and "case-ghost" in out
        print(f"  {'caught' if ok else 'MISSED'}  cases/index.json lists a case that isn't on disk")
        return ok


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
    for label, mutate, expect, strict in MUTATIONS:
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp) / "case-mutant"
            shutil.copytree(GOLDEN, d)
            mutate(d)
            rc, out = run_validator(d, strict=strict)

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

    total = len(MUTATIONS) + 1
    if test_index():
        passed += 1

    print(f"\n{passed}/{total} mutations correctly caught and named")
    if passed != total:
        print("The validator is not the safety net it is being trusted as. Fix it before "
              "anyone relies on a PASS.")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
