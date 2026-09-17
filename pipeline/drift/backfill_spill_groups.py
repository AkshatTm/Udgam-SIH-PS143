#!/usr/bin/env python3
"""
D46 one-off: write meta.spill_groups for a case that group_oil_features() finds only ONE group
for, WITHOUT touching particles.json/origin.json or running any physics.

    python pipeline/drift/backfill_spill_groups.py --case case-jacksonville-2024

Every case in the library except case-gulf-alaska-2023 and case-mumbai-2023 already has exactly
one independent spill group (a single oil feature, or several that measure as one ribbon), so
the existing particles.json/origin.json are already that group's bundle — nothing needs to be
recomputed, only recorded. Refuses (tells the operator to do a real rerun with
pipeline/drift/run.py --real instead) when group_oil_features finds more than one group, so this
script can never be used to paper over a genuinely multi-spill case.
"""
import argparse
import json
from pathlib import Path

from slick import group_oil_features

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--case", required=True)
    ap.add_argument("--cases-root", default=str(REPO / "cases"))
    a = ap.parse_args()

    d = Path(a.cases_root) / a.case
    dets_path = d / "detections.geojson"
    dets = json.loads(dets_path.read_text())
    groups, _ = group_oil_features(dets, mode="auto", verbose=True)
    if len(groups) != 1:
        raise SystemExit(
            f"{a.case}: group_oil_features finds {len(groups)} independent spill groups -- "
            f"this case needs a real rerun (pipeline/drift/run.py --case {a.case} --real), "
            f"not a backfill, or every group but the primary would be missing its own "
            f"particles/origin bundle.")

    g = groups[0]
    meta_path = d / "meta.json"
    meta = json.loads(meta_path.read_text())
    meta["spill_groups"] = [{
        "id": "group-1",
        "member_detection_ids": g["member_ids"],
        "is_primary": True,
        "particles_file": "particles.json",
        "origin_file": "origin.json",
        "total_area_km2": round(g["total_area_km2"], 4),
        "merged_ribbon": g["ribbon"]["merged"],
    }]
    meta_path.write_text(json.dumps(meta, indent=2))
    print(f"{a.case}: wrote spill_groups (1 group, {g['member_ids']}) into {meta_path}")


if __name__ == "__main__":
    main()
