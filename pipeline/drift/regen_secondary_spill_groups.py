#!/usr/bin/env python3
"""
D46 one-off: for a case with more than one independent spill group, compute real backward drift
for every group EXCEPT the primary one, and write meta.spill_groups.

    python pipeline/drift/regen_secondary_spill_groups.py --case case-gulf-alaska-2023 --real

WHY A SEPARATE SCRIPT, NOT `run.py --real` DIRECTLY
    `run.py`'s primary control run + 50-member ensemble (age engine included) is orchestrated by
    `publish_all.py` together with `pool_models.py` (OpenDrift pooling -> `model_mix`) and a
    separate publish step (`pipeline/export/build_case.py`) that copies `pipeline/drift/out/`
    into `cases/<id>/`. Re-running `run.py --real` bare would rewrite `cases/<id>/particles.json`
    /`origin.json` from a DIFFERENT pipeline than the one that actually produced the shipped
    bundle (no OpenDrift pooling here), risking a silent regression in already-published,
    already-verified fields (`model_mix`, `age_posterior`) for a bug fix that has nothing to do
    with them. So this script never touches the primary bundle at all: `cases/<id>/particles.json`
    and `origin.json` are read only to confirm they already exist, never written. It calls
    `merge_oil_features()` (unchanged) purely to identify which group is already the primary one
    on disk, and `run_backward_group()` (D46, run.py) only for every OTHER group.

Working files (the per-group ensemble .npz) land in `pipeline/drift/out/<case>/`, never in
`cases/<id>/` -- same "working space, not in the bundle" discipline `run.py` already uses for
`coastal_impact_<case>.json`. Only the two bundle files per secondary group are copied into
`cases/<id>/`.
"""
import argparse
import json
import random
from datetime import timedelta
from pathlib import Path

import numpy as np

import coastline
from fields import load_case_field, make_fake
from run import parse_ts, run_backward_group
from slick import group_oil_features, merge_oil_features

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--case", required=True)
    ap.add_argument("--cases-root", default=str(REPO / "cases"))
    ap.add_argument("--real", action="store_true")
    ap.add_argument("--fake", action="store_true")
    ap.add_argument("--field", choices=["analytic", "constant"], default="analytic")
    ap.add_argument("--wind", type=float, nargs=2, default=(6.0, -4.0))
    ap.add_argument("--particles", type=int, default=3000)
    ap.add_argument("--runs", type=int, default=50)
    ap.add_argument("--steps", type=int, default=289)
    ap.add_argument("--timestep-minutes", type=int, default=15)
    ap.add_argument("--output-timestep-minutes", type=int, default=45)
    ap.add_argument("--seed", type=int, default=143)
    ap.add_argument("--merge-oil", choices=["auto", "always", "never"], default="auto")
    ap.add_argument("--current-sigma", type=float, default=None)
    ap.add_argument("--out", default=str(HERE / "out"))
    a = ap.parse_args()
    if not (a.real or a.fake):
        raise SystemExit("choose an ocean: --real or --fake")

    case_dir = Path(a.cases_root) / a.case
    dets_raw = json.loads((case_dir / "detections.geojson").read_text())
    meta = json.loads((case_dir / "meta.json").read_text())
    t0 = parse_ts(meta["detection_time"])

    if not (case_dir / "particles.json").exists() or not (case_dir / "origin.json").exists():
        raise SystemExit(f"{case_dir}: particles.json/origin.json missing -- this script only "
                         f"adds SECONDARY groups to a case whose primary bundle already exists. "
                         f"Run pipeline/drift/run.py --case {a.case} --real first.")

    # Identify the primary feature EXACTLY as run.py's main() does -- same function, same mode
    # -- so the group we skip below is provably the one that seeded the already-shipped bundle.
    primary_feat, _ = merge_oil_features(dets_raw, mode=a.merge_oil)
    primary_ids = set(primary_feat["properties"].get("merged_from")
                      or [primary_feat["properties"].get("id")])

    groups, _ = group_oil_features(dets_raw, mode=a.merge_oil, verbose=True)
    if len(groups) == 1:
        raise SystemExit(f"{a.case}: only one spill group found -- nothing for this script to "
                         f"do. Use pipeline/drift/backfill_spill_groups.py instead.")

    if a.real:
        field = load_case_field(a.case, repo_root=REPO)
    else:
        prim_clon = float(primary_feat["properties"]["centroid"][0])
        prim_clat = float(primary_feat["properties"]["centroid"][1])
        field = make_fake(a.field, lon0=prim_clon, lat0=prim_clat, wind=tuple(a.wind))
    land = coastline.is_land if coastline.available() else None
    print(f"[regen-groups]  {a.case}  coast: {coastline.describe()}")

    work_dir = Path(a.out) / a.case
    work_dir.mkdir(parents=True, exist_ok=True)

    meta_groups = []
    for gi, g in enumerate(groups, start=1):
        gid = f"group-{gi}"
        is_primary = set(g["member_ids"]) == primary_ids
        if is_primary:
            meta_groups.append({
                "id": gid, "member_detection_ids": g["member_ids"], "is_primary": True,
                "particles_file": "particles.json", "origin_file": "origin.json",
                "total_area_km2": round(g["total_area_km2"], 4),
                "merged_ribbon": g["ribbon"]["merged"],
            })
            continue
        pfile, ofile = f"particles_{gid}.json", f"origin_{gid}.json"
        work_p, work_o = work_dir / pfile, work_dir / ofile
        print(f"[regen-groups]  {gid}  {g['member_ids']}  "
              f"area {g['total_area_km2']:.3f} km2  seeding independently")
        gdiag = run_backward_group(a, t0, field, land, g["feature"], work_p, work_o,
                                   group_label=gid, seed_offset=1000 * gi)
        print(f"                origin r50={gdiag['r50']:.1f} km  r90={gdiag['r90']:.1f} km  "
              f"abstain={gdiag['abstain']}  method={gdiag['method']}")
        (case_dir / pfile).write_text(work_p.read_text())
        (case_dir / ofile).write_text(work_o.read_text())
        print(f"                published {case_dir / pfile}")
        print(f"                published {case_dir / ofile}")
        meta_groups.append({
            "id": gid, "member_detection_ids": g["member_ids"], "is_primary": False,
            "particles_file": pfile, "origin_file": ofile,
            "total_area_km2": round(g["total_area_km2"], 4),
            "merged_ribbon": g["ribbon"]["merged"],
        })

    meta["spill_groups"] = meta_groups
    (case_dir / "meta.json").write_text(json.dumps(meta, indent=2))
    print(f"[regen-groups]  wrote spill_groups ({len(meta_groups)} group(s)) into "
          f"{case_dir / 'meta.json'}")


if __name__ == "__main__":
    main()
