#!/usr/bin/env python3
"""Run and publish every Stage 2 case, in order, with the out/ hazard handled.

    python pipeline/drift/publish_all.py                 # all cases
    python pipeline/drift/publish_all.py --case case-mumbai-2023 ...   # a subset
    python pipeline/drift/publish_all.py --dry-run       # show the plan, run nothing

WHY THIS EXISTS AND NOT A SHELL LOOP
    `run.py` writes `particles.json` and `origin.json` into ONE shared directory,
    `pipeline/drift/out/`, regardless of --case. That is the bug that once rendered an Ennore
    cloud under Jacksonville's name, 160 degrees of longitude away, with nothing tripping
    (docs/STAGE2_NUMBERS.md 8.7). Guards catch it at PLOT time now, but the hazard at PUBLISH
    time is the same shape: run six cases, then publish six times, and every bundle gets the
    last case's cloud.

    So each case is run AND PUBLISHED before the next one starts. Never reorder this loop into
    "run everything, then publish everything".

WHAT IT DOES PER CASE
    1  backward ensemble        run.py --real --particles 3000 --runs 50
    2  age                      age.py --real   (+ --volume-m3 where an official figure exists)
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


def main():
    ap = argparse.ArgumentParser(description="Run and publish every Stage 2 case")
    ap.add_argument("--case", nargs="*", default=CASES, help="subset of cases")
    ap.add_argument("--particles", type=int, default=3000)
    ap.add_argument("--runs", type=int, default=50)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--skip-forward", action="store_true")
    a = ap.parse_args()

    py = sys.executable
    drift = REPO / "pipeline" / "drift"
    summary = []

    for case in a.case:
        print("\n" + "=" * 78)
        print(f"  {case}")
        print("=" * 78)

        rc = sh([py, drift / "run.py", "--case", case, "--real",
                 "--particles", str(a.particles), "--runs", str(a.runs)], "backward", a.dry_run)
        if rc != 0:
            summary.append((case, "FAILED at the backward run", False))
            continue

        age_cmd = [py, drift / "age.py", "--case", case, "--real"]
        if case in VOLUMES_M3:
            vol, cite = VOLUMES_M3[case]
            print(f"\n  using an independently reported volume: {vol} m3 ({cite})")
            age_cmd += ["--volume-m3", str(vol)]
        sh(age_cmd, "age", a.dry_run)          # age never blocks the bundle; it may report none

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
