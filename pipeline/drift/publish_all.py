#!/usr/bin/env python3
"""Run and publish every Stage 2 case, in order, with the out/ hazard handled.

    python pipeline/drift/publish_all.py                 # all cases
    python pipeline/drift/publish_all.py --case case-mumbai-2023 ...   # a subset
    python pipeline/drift/publish_all.py --dry-run       # show the plan, run nothing
    python pipeline/drift/publish_all.py --notes-only    # D35 seed note into meta.notes, no drift

WHY THIS EXISTS AND NOT A SHELL LOOP
    `run.py` writes `particles.json` and `origin.json` into ONE shared directory,
    `pipeline/drift/out/`, regardless of --case. That is the bug that once rendered an Ennore
    cloud under Jacksonville's name, 160 degrees of longitude away, with nothing tripping
    (docs/evaluation/stage2-numbers.md 8.7). Guards catch it at PLOT time now, but the hazard at PUBLISH
    time is the same shape: run six cases, then publish six times, and every bundle gets the
    last case's cloud.

    So each case is run AND PUBLISHED before the next one starts. Never reorder this loop into
    "run everything, then publish everything".

WHAT IT DOES PER CASE
    0  (--opendrift only)       age.py --request-only; odenv: opendrift_age.py, opendrift_origin.py
    1  age + backward ensemble  run.py --real --age drive  (+ --volume-m3 where published)
    2  (--opendrift only)       pool_models.py -> model_mix
    3  forward drift            run.py --real --forward
    4  acts_available           adds "trace" to cases/<id>/meta.json if absent, and says so
    5  publish                  pipeline/export/build_case.py --case <id> --stage trace
    6  validate                 scripts/validate_case.py cases/<id>

    Step 4 edits a file in the SHARED cases/ tree. It is announced loudly and listed in the
    summary, because Akshat owns that directory even though meta.json's own note says acts are
    "added as each stage lands".
"""
import argparse
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]

# Every case with a real detection. case-ennore-lookalike-2023 is deliberately absent: it holds
# zero 'oil' features, so run.py refuses it by design and 'trace' must NOT be added to its
# acts_available. That refusal is a designed state, not a gap -- see branch test 10b.
CASES = [
    "case-jacksonville-2024",
    "case-farallones-2023",
    "case-gulf-alaska-2023",
    "case-huntington-2021",
    "case-jamnagar-2024",
    "case-mumbai-2023",
]

# Independently reported release volumes, for C3.2. Fay needs a volume from an OUTSIDE source --
# deriving it from area_km2 is circular (the observed area lands on both sides of the spreading
# law). Only add an entry here when there is a published finding to cite.
VOLUMES_M3 = {
    "case-huntington-2021": (93.5, "588 barrels, NTSB MIR-24-01"),
}


def sh(cmd, label, dry):
    print(f"\n  $ {' '.join(str(c) for c in cmd)}")
    if dry:
        return 0
    rc = subprocess.run(cmd, cwd=REPO).returncode
    if rc != 0:
        print(f"  !! {label} exited {rc}")
    return rc


def ensure_trace(case, dry):
    """Add 'trace' to acts_available, or report that it is already there.

    build_case.py skips any act not listed (build_case.py:83), so without this the publish
    copies zero files and still exits 0 -- which reads as success.
    """
    meta_path = REPO / "cases" / case / "meta.json"
    # explicit utf-8: Windows defaults to cp1252 and turned every em dash in meta.json into mojibake
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    acts = meta.get("acts_available", [])
    if "trace" in acts:
        return False
    print(f"  ** EDITING A SHARED FILE: adding 'trace' to {meta_path.relative_to(REPO)}")
    print(f"     was {acts} -> {acts + ['trace']}   (tell Akshat; cases/ is his)")
    if dry:
        return True
    # insert after 'detect' so the list stays in pipeline order rather than append order
    order = ["detect", "trace", "attribute", "verify"]
    acts = sorted(set(acts) | {"trace"}, key=lambda a: order.index(a) if a in order else 99)
    meta["acts_available"] = acts
    meta_path.write_text(json.dumps(meta, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return True


SEED_NOTE_TAG = "D35 seed:"
SEED_MATCH_KM = 1.0


def seed_note(case, dry):
    """Append which detection(s) seeded the trace to meta.notes (Master §6.5, D35).

    The seed choice is recomputed with the SAME function run.py uses, merge_oil_features in
    its default 'auto' mode, then checked against the committed particles.json. Both seeders in
    run.py (line along the principal axis, gaussian at a point) are symmetric about the seed's
    `centroid`, so the mean frame-0 position must land within SEED_MATCH_KM of it. It must also
    be closer to it than to the alternative seed (the merged ribbon if 'auto' did not merge, the
    best single feature if it did). A bounding-box test was tried first and is wrong: chronic seeding
    lays a straight segment through a curved ribbon, and on Jacksonville that overshoots the ribbon's
    end by ~3 km while being the merged seed beyond doubt. If the check fails, the published trace
    was seeded some other way, and writing the note would put a false statement on the record,
    so this refuses.

    Touches meta.json only; no drift is integrated. Idempotent: an existing note is replaced.
    Returns (ok, message).
    """
    import math
    import re
    sys.path.insert(0, str(HERE))
    from slick import merge_oil_features   # same package; Stage 2's own seed logic

    cdir = REPO / "cases" / case
    dets = json.loads((cdir / "detections.geojson").read_text(encoding="utf-8"))
    feat, diag = merge_oil_features(dets, mode="auto", verbose=False)
    if feat is None:
        return False, "no oil features -- nothing seeds a trace"

    def km(a, b):
        mid = math.radians((a[1] + b[1]) / 2)
        return math.hypot((a[0] - b[0]) * 111.32 * math.cos(mid), (a[1] - b[1]) * 111.32)

    frame0 = json.loads((cdir / "particles.json").read_text(encoding="utf-8"))["positions"][0]
    mean0 = [sum(p[0] for p in frame0) / len(frame0), sum(p[1] for p in frame0) / len(frame0)]
    d_chosen = km(mean0, feat["properties"]["centroid"])
    alt_mode = "never" if diag.get("decision") == "MERGED into one ribbon" else "always"
    alt, _ = merge_oil_features(dets, mode=alt_mode, verbose=False)
    d_alt = km(mean0, alt["properties"]["centroid"])
    distinct = km(feat["properties"]["centroid"], alt["properties"]["centroid"]) > 1e-6
    if d_chosen > SEED_MATCH_KM or (distinct and d_alt <= d_chosen):
        return False, (f"frame-0 mean is {d_chosen:.2f} km from {diag.get('seeded_from')} and "
                       f"{d_alt:.2f} km from the alternative seed -- the published trace was not "
                       "seeded the way 'auto' would seed it; note NOT written")

    n_oil = diag.get("n_oil", 1)
    merged = diag.get("decision") == "MERGED into one ribbon"
    if merged:
        why = f"merged: yes, {n_oil} oil features pass all four ribbon gates"
    elif n_oil > 1:
        why = (f"merged: no, {n_oil} oil features do not measure as one ribbon, so the "
               "highest-confidence feature alone")
    else:
        why = "merged: no, the only oil feature"
    oil_area = sum(f["properties"].get("area_km2") or 0.0 for f in dets.get("features", [])
                   if (f.get("properties") or {}).get("classification") == "oil")
    seed_area = feat["properties"].get("area_km2") or 0.0
    note = (f"{SEED_NOTE_TAG} trace seeded from {diag['seeded_from']} ({why}); "
            f"n_oil={n_oil}; seed area {seed_area:.2f} of {oil_area:.2f} km2 of oil on the scene. "
            "One trace per spill event; selecting another detection does not re-trace.")

    meta_path = cdir / "meta.json"
    # explicit utf-8, same reason as ensure_trace
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    notes = meta.get("notes") or ""
    base = re.split(r"\s*" + re.escape(SEED_NOTE_TAG), notes, maxsplit=1)[0].rstrip()
    new = (base + " " + note).strip()
    if new == notes:
        return True, f"unchanged -- {note}"
    if not dry:
        meta["notes"] = new
        meta_path.write_text(json.dumps(meta, indent=2, ensure_ascii=False) + "\n",
                             encoding="utf-8")
    return True, f"{'would write' if dry else 'wrote'} -- {note}"


def main():
    ap = argparse.ArgumentParser(description="Run and publish every Stage 2 case")
    ap.add_argument("--case", nargs="*", default=CASES, help="subset of cases")
    ap.add_argument("--particles", type=int, default=3000)
    ap.add_argument("--runs", type=int, default=50)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--skip-forward", action="store_true")
    ap.add_argument("--age", choices=["off", "report", "drive"], default="drive",
                    help="run.py's age mode (age engine v2, D45). drive: the origin is pooled "
                         "over the age posterior and the window is method 'age'")
    ap.add_argument("--opendrift", action="store_true",
                    help="also run OpenOil (age) and OceanDrift (origin) from odenv/ and pool "
                         "them. Off the demo path; absent odenv -> our model alone")
    ap.add_argument("--notes-only", action="store_true",
                    help="only write the D35 seed note into meta.notes; runs no drift")
    a = ap.parse_args()

    if a.notes_only:
        rc = 0
        for case in a.case:
            ok, msg = seed_note(case, a.dry_run)
            print(f"  {case:<28} {'OK ' if ok else 'REFUSED'}  {msg}")
            rc |= 0 if ok else 1
        return rc

    py = sys.executable
    drift = REPO / "pipeline" / "drift"
    summary = []

    for case in a.case:
        print("\n" + "=" * 78)
        print(f"  {case}")
        print("=" * 78)

        # ---- age engine v2: OpenDrift's two models first, in their own venv (optional) ----
        if a.opendrift:
            odpy = REPO / "odenv" / "Scripts" / "python.exe"
            if not odpy.exists():
                odpy = REPO / "odenv" / "bin" / "python"
            if not odpy.exists():
                print("  !! --opendrift given but no odenv/ -- continuing with our model only")
            else:
                sh([py, drift / "age.py", "--case", case, "--real", "--request-only"],
                   "age request", a.dry_run)
                sh([odpy, "-W", "ignore", drift / "opendrift_age.py", "--case", case],
                   "OpenOil age curves", a.dry_run)          # failure -> structural fallback
                sh([odpy, "-W", "ignore", drift / "opendrift_origin.py", "--case", case],
                   "OceanDrift origin frames", a.dry_run)

        # The age now runs INSIDE run.py (before the ensemble, which needs to know which
        # steps to keep), so there is one writer of origin.json and no separate age step.
        cmd = [py, drift / "run.py", "--case", case, "--real", "--particles", str(a.particles),
               "--runs", str(a.runs), "--age", a.age]
        if case in VOLUMES_M3:
            vol, cite = VOLUMES_M3[case]
            print(f"\n  using an independently reported volume: {vol} m3 ({cite})")
            cmd += ["--volume-m3", str(vol)]
        rc = sh(cmd, "backward + age", a.dry_run)
        if rc != 0:
            summary.append((case, "FAILED at the backward run", False))
            continue
        if a.opendrift:
            sh([py, drift / "pool_models.py", "--case", case], "pool models", a.dry_run)

        if not a.skip_forward:
            sh([py, drift / "run.py", "--case", case, "--real", "--forward"],
               "forward", a.dry_run)

        edited = ensure_trace(case, a.dry_run)

        rc = sh([py, REPO / "pipeline" / "export" / "build_case.py",
                 "--case", case, "--stage", "trace"], "build_case", a.dry_run)
        if rc != 0:
            summary.append((case, "FAILED at build_case", edited))
            continue

        rc = sh([py, REPO / "scripts" / "validate_case.py", REPO / "cases" / case],
                "validate", a.dry_run)
        summary.append((case, "PASS" if rc == 0 else f"validator exit {rc}", edited))

    print("\n" + "=" * 78)
    print("  SUMMARY")
    print("=" * 78)
    for case, state, edited in summary:
        print(f"  {case:<28} {state:<28} {'meta.json edited' if edited else ''}")
    edits = [c for c, _, e in summary if e]
    if edits:
        print(f"\n  {len(edits)} meta.json file(s) in cases/ were edited to add 'trace'.")
        print(f"  That directory is Akshat's -- tell him rather than letting him find it in a diff:")
        for c in edits:
            print(f"    cases/{c}/meta.json")
    print("\n  Expect MANY 'falls well outside the scene bounds' warnings. They are correct:")
    print("  Jacksonville travels 148.7 km against a scene about 50 km across, so the origin")
    print("  cloud is legitimately off-scene. The validator warns rather than failing for")
    print("  exactly this reason. A validator ERROR is a different matter -- bring it here.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
