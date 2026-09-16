"""Stage 2 producer for `cases/<case_id>/forward_impact.json` (Master 6.10).

Forward drift is the question a coast guard asks and the backward rewind cannot answer: given the
slick we just detected, where does it go and what does it threaten. This writes that forecast into
the bundle so the map can draw it, in the frozen 6.10 shape.

HISTORY. Forward drift shipped on 16 Sept as "Version A" -- measured, figure'd, but deliberately
NOT in any bundle, because adding a file to a frozen schema is not a one-person decision. Akshat
lifted that deferral on 16 Sept; 6.10 is the resulting contract. The numbers did not change when
the deferral lifted, and they must not: the physics lives in `eval_forward.compute()`, and both
the evidence file and this bundle file are written from that one return value.

WHAT IS AND IS NOT CLAIMED. The envelope is ensemble PRECISION, not accuracy -- it says where the
50 members agree the oil goes, not that the oil goes there. `coast_segments` and `assets_at_risk`
are `null`, not `[]`: naming a threatened stretch needs a coastline gazetteer, and listing an asset
needs a citable source (WDPA etc.) with a URL and a retrieval date. Neither has been fetched, and
`null` says "not measured" where `[]` would claim "measured, and there are none" (Rule 4).

HORIZON. 24 h. The cached HYCOM + ERA5 fields end 24.6-26.0 h past t0 on every case and
`assert_field_covers` refuses a longer run rather than extrapolating through a frozen last
snapshot. 48 h and 72 h need a wider GEE fetch.

    python pipeline/drift/forward_impact.py --case case-jacksonville-2024
    python pipeline/drift/forward_impact.py --all
    python pipeline/drift/forward_impact.py --case case-mumbai-2023 --from-evidence
"""
import argparse, json, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(HERE))

import eval_forward  # noqa: E402

CASES = REPO / "cases"
OUT = HERE / "out"
EVIDENCE = REPO / "docs/evaluation/figures/stage2/data"

# Why the two list fields are null rather than empty. Written into the bundle so the reason
# travels with the file instead of living only in a commit message.
UNMEASURED_NOTE = ("coast_segments needs a coastline gazetteer and assets_at_risk needs a cited "
                   "asset layer (WDPA or equivalent) with a URL and retrieval date. Neither has "
                   "been fetched, so both are null -- not measured, as distinct from measured "
                   "and empty.")


def to_bundle(result):
    """Reshape a measured `eval_forward.compute()` result into the frozen 6.10 shape.

    Reshapes only. Every number here is carried across unchanged; nothing is recomputed,
    rescaled or rounded a second time.
    """
    stranded_at_horizon = result["stranded_fraction_at_horizon"]
    first_landfall = result["first_landfall_hours"]

    # Rule 4 in the producing code, not just in the validator. Nothing stranded means landfall
    # was never observed, which is `null`. A `0.0` here would claim landfall at t0.
    if stranded_at_horizon == 0 and first_landfall is not None:
        raise SystemExit(f"{result['case']}: {stranded_at_horizon=} but {first_landfall=} -- "
                         "a first landfall with nothing ashore is a contradiction, not a result")

    return {
        "t0": result["t0"],
        "direction": "forward",
        "horizon_hours": result["horizon_hours"],
        "horizon_note": result["horizon_note"],
        "ensemble_runs": result["n_runs"],
        "particles_per_run": result["n_particles_per_run"],
        "wind_coeff": result["wind_coeff"],
        "envelope": result["envelope"],
        "first_landfall_hours": first_landfall,
        "stranded_fraction_at_horizon": stranded_at_horizon,
        "seeded_ashore_fraction": result["seeded_ashore_fraction"],
        "centroid_displacement_km": result["centroid_displacement_km_at_horizon"],
        "edge_margin_km": result["edge_margin_km"],
        "coast_segments": None,
        "assets_at_risk": None,
        "unmeasured_note": UNMEASURED_NOTE,
        "source": result["source"],
    }


def traceable(case):
    """A forward forecast only means something where a trace was run. Detect-only cases
    (look-alikes, no-spill tiles) have no slick to push forward."""
    meta_path = CASES / case / "meta.json"
    if not meta_path.exists():
        return False
    return "trace" in json.loads(meta_path.read_text(encoding="utf-8")).get("acts_available", [])


def write_case(case, from_evidence=False, mirror_to_out=False):
    evidence_path = EVIDENCE / f"forward_{case}.json"
    if from_evidence:
        if not evidence_path.exists():
            raise SystemExit(f"{case}: no measured evidence at {evidence_path} -- run without "
                             "--from-evidence to produce it")
        result = json.loads(evidence_path.read_text(encoding="utf-8"))
    else:
        result = eval_forward.compute(case)
        # Keep the evidence file and the bundle provably in step: one run, both outputs.
        evidence_path.parent.mkdir(parents=True, exist_ok=True)
        evidence_path.write_text(json.dumps(result, indent=1), encoding="utf-8")

    bundle = json.dumps(to_bundle(result), indent=2)
    out = CASES / case / "forward_impact.json"
    out.write_text(bundle, encoding="utf-8")
    print(eval_forward.summarise(case, result))
    print(f"[forward] wrote {out}")
    if mirror_to_out:
        # build_case.py gathers the trace act from here, so a later `--stage trace` rebuild
        # carries the file too. Single-case only: out/ holds one case at a time, like run.py.
        OUT.mkdir(parents=True, exist_ok=True)
        (OUT / "forward_impact.json").write_text(bundle, encoding="utf-8")
        print(f"[forward] mirrored {OUT / 'forward_impact.json'}   (for build_case.py)")
    return out


def main():
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--case")
    g.add_argument("--all", action="store_true",
                   help="every indexed case whose acts_available includes 'trace'")
    ap.add_argument("--from-evidence", action="store_true",
                    help="reshape the committed measured run instead of re-running the ensemble "
                         "(for laptops without the cached HYCOM/ERA5 fields in data/)")
    a = ap.parse_args()

    if a.all:
        indexed = json.loads((CASES / "index.json").read_text(encoding="utf-8"))["cases"]
        cases = [c for c in indexed if traceable(c)]
        print(f"[forward] {len(cases)} of {len(indexed)} indexed cases have a trace act: "
              f"{', '.join(cases)}")
    else:
        cases = [a.case]
        if not traceable(a.case):
            raise SystemExit(f"{a.case}: acts_available has no 'trace' -- there is no slick to "
                             "push forward, and a forward_impact.json here would be invented")

    for c in cases:
        write_case(c, from_evidence=a.from_evidence, mirror_to_out=not a.all)
    return 0


if __name__ == "__main__":
    sys.exit(main())
