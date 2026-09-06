#!/usr/bin/env python3
"""
build_case.py — the bundle assembler. Owner: Akshat.

    python pipeline/export/build_case.py --case case-ennore-2017
    python pipeline/export/build_case.py --case case-000 --dry-run

Gathers each stage's `out/` directory into `cases/<case_id>/`, then runs the validator.

It COPIES AND VALIDATES. It computes nothing, and it repairs nobody's files. When a bundle
fails validation the fix goes back to the producing owner with the validator error attached —
never patch a bundle by hand, or the same bug returns on the next run at a worse time
(docs/TRAPS.md #20).

meta.json, bounds.json and sar.png are scene inputs and are expected to be in the case
directory already, put there by gee_scene.py. This script never overwrites them.
"""
import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]

# stage output directory -> files it is expected to contribute, and the act that requires them
SOURCES = [
    ("detect",    REPO / "pipeline" / "detect" / "out",    ["detections.geojson"]),
    ("trace",     REPO / "pipeline" / "drift" / "out",     ["particles.json", "origin.json"]),
    ("attribute", REPO / "pipeline" / "attribute" / "out", ["vessels.geojson", "suspects.json"]),
]

SCENE_FILES = ["meta.json", "bounds.json", "sar.png"]


def main():
    ap = argparse.ArgumentParser(description="Assemble a case bundle and validate it")
    ap.add_argument("--case", required=True, help="case id, e.g. case-ennore-2017")
    ap.add_argument("--cases-root", default=str(REPO / "cases"))
    ap.add_argument("--stage", choices=[s[0] for s in SOURCES], default=None,
                    help="publish ONE stage's outputs into the case folder and skip validation. "
                         "The case folder is how stages hand off to each other, so Stage 2 cannot "
                         "read Stage 1 until Stage 1 has been published. Omit for the full "
                         "assemble-and-validate.")
    ap.add_argument("--dry-run", action="store_true", help="report what would be copied, copy nothing")
    ap.add_argument("--strict", action="store_true", help="pass --strict to the validator")
    a = ap.parse_args()

    case_dir = Path(a.cases_root) / a.case
    if not case_dir.is_dir():
        raise SystemExit(f"{case_dir} does not exist. The scene export creates it:\n"
                         f"  python pipeline/export/gee_scene.py --scene <system:index> --case {a.case}")

    missing_scene = [f for f in SCENE_FILES if not (case_dir / f).exists()]
    if missing_scene:
        raise SystemExit(f"{case_dir} is missing scene input(s) {missing_scene}. "
                         f"These come from the GEE export, not from a stage.")

    meta = json.loads((case_dir / "meta.json").read_text())
    acts = meta.get("acts_available", [])
    print(f"Assembling {a.case}   acts_available={acts}")
    print("-" * 58)

    copied, absent = [], []
    for act, src, names in SOURCES:
        if a.stage and act != a.stage:
            continue
        if act not in acts:
            print(f"  skip   {act:<10} not in acts_available")
            continue
        for name in names:
            s = src / name
            if not s.exists():
                absent.append((act, s))
                print(f"  MISS   {act:<10} {s}")
                continue
            if a.dry_run:
                print(f"  would  {act:<10} {s}  ->  {case_dir / name}")
            else:
                shutil.copy2(s, case_dir / name)
                print(f"  copy   {act:<10} {name:<20} {s.stat().st_size / 1e6:6.2f} MB")
            copied.append(name)

    if absent:
        print("-" * 58)
        print(f"FAIL   {len(absent)} required output(s) not produced yet.")
        for act, s in absent:
            print(f"       '{act}' is in acts_available but {s} is missing.")
        print("       Either that stage has not run, or the act should not be listed in meta.json.")
        return 1

    if a.dry_run:
        print("-" * 58)
        print(f"DRY RUN — {len(copied)} file(s) would be copied. Nothing written.")
        return 0

    print("-" * 58)
    if a.stage:
        print(f"Published '{a.stage}' into {case_dir} ({len(copied)} file(s)). "
              f"Validation skipped — the bundle is still incomplete.")
        return 0

    cmd = [sys.executable, str(REPO / "scripts" / "validate_case.py"), str(case_dir)]
    if a.strict:
        cmd.append("--strict")
    sys.stdout.flush()          # the child writes straight to the console; keep the order honest
    rc = subprocess.run(cmd).returncode
    if rc != 0:
        print("Bundle assembled but INVALID. Send the errors above to the owner of the failing "
              "stage.\nDo not hand-edit the bundle.")
    return rc


if __name__ == "__main__":
    sys.exit(main())
