#!/usr/bin/env python3
"""
Stage 2 untested-branch tests (suite 10). Owner: Anushka.   (brief Phase 3.3)

Run through the main suite — not standalone:

    python pipeline/drift/tests.py

WHY THIS SUITE EXISTS
    Until now exactly one seeding path had ever run on real fields: `linear`. The brief's own
    words -- "Never executed" is never "known good." Three branches existed only on paper:

      BLOB        an isotropic slick seeded from the centroid rather than along an axis
      NO-SPILL    a detections file with zero oil features, which is a DESIGNED answer
      ABSTAIN     radius_90_km > 40, the deliberate refusal that Stage 3 must honour

    All three now execute here, on the real cached field where that is meaningful, so "it has
    never been run" stops being true and stays stopped.

    The abstain case matters beyond Stage 2: Harshita cannot build the refusal screen against a
    state that has never existed, and a hand-edited bundle would violate CLAUDE.md's rule that
    you fix the producing code and never patch data. So the fixture is PRODUCED by the pipeline
    with a widened, loudly-announced uncertainty budget.
"""
import json
import math
import random
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

import coastline
import ensemble as ens
import run as R
from fields import ConstantField, load_case_field
from step import displacement_km, integrate_stranding

T0 = datetime(2017, 1, 29, 0, 14, 0, tzinfo=timezone.utc)
ENNORE = [80.35, 13.25]
REPO = Path(__file__).resolve().parents[2]


def _blob_feature():
    """An isotropic slick: a rough circle, shape_class blob, discharge acute."""
    r = 2.0 / 111.32
    coslat = math.cos(math.radians(ENNORE[1]))
    ring = [[ENNORE[0] + r / coslat * math.cos(t), ENNORE[1] + r * math.sin(t)]
            for t in np.linspace(0, 2 * math.pi, 33)]
    return {"type": "Feature",
            "geometry": {"type": "Polygon", "coordinates": [ring]},
            "properties": {"id": "det-blob", "classification": "oil", "confidence": 0.88,
                           "area_km2": 12.6, "elongation": 1.05, "shape_class": "blob",
                           "discharge_class": "acute", "centroid": ENNORE}}


def run(check):
    """Suite 10. `check` is tests.py's assertion recorder."""
    print("\nTest 10 - the branches that had never executed (Phase 3.3): blob, no-spill, abstain")
    ok = True

    # --- 10a  the BLOB branch, end to end on the real cached field ----------------------
    field = load_case_field("case-000", repo_root=REPO)
    rng = random.Random(143)
    blob_seed = R.seed_particles(_blob_feature(), 1200, rng)
    p = np.asarray(blob_seed, dtype=np.float64)
    clat = float(p[:, 1].mean())
    xy = np.column_stack([(p[:, 0] - p[:, 0].mean()) * 111.32 * math.cos(math.radians(clat)),
                          (p[:, 1] - clat) * 111.32])
    ev = np.linalg.eigvalsh(np.cov(xy, rowvar=False))
    aspect = math.sqrt(max(ev[1], 1e-12) / max(ev[0], 1e-12))

    land = coastline.is_land if coastline.available() else None
    hist, _, stranded = integrate_stranding(blob_seed, T0, field, 97, 15,
                                            direction="backward", is_land=land)
    med_km = float(np.median(displacement_km(hist[0], hist[-1])))
    ok &= check("10a  a BLOB slick runs end to end on the real field",
                aspect < 1.5 and 5.0 < med_km < 200.0,
                f"seeded 1200 particles isotropically (aspect {aspect:.2f}:1, not a line) and "
                f"rewound 24 h through real HYCOM + ERA5: median displacement {med_km:.1f} km, "
                f"{float(np.mean(stranded)) * 100:.1f}% stranded. Before this, only the "
                f"`linear` branch had ever touched a real field")

    # --- 10b  the NO-SPILL branch: zero oil features is an ANSWER ----------------------
    ns = REPO / "cases" / "case-000-nospill" / "detections.geojson"
    if ns.exists():
        fc = json.loads(ns.read_text())
        classes = [(f.get("properties") or {}).get("classification") for f in fc["features"]]
        picked = R.pick_slick(fc)
        ok &= check("10b  a no-spill scene returns no slick, and that is a designed state",
                    picked is None and classes and all(c == "lookalike" for c in classes),
                    f"cases/case-000-nospill holds {len(classes)} features, all "
                    f"{set(classes)}, zero oil -> pick_slick returns None. run.py then exits "
                    f"saying 'trace' should not be in acts_available, rather than rewinding "
                    f"nothing and writing an empty cloud")
    else:
        ok &= check("10b  a no-spill scene returns no slick, and that is a designed state",
                    False, f"fixture missing at {ns}")

    # --- 10c  the ABSTAIN branch, produced by the pipeline not by hand ------------------
    # A constant 0.8 m/s rewinding OFFSHORE (so stranding does not collapse the cloud) with a
    # widened current-scale band. Deliberately synthetic: the point is that the bundle is
    # written by run.py, because CLAUDE.md forbids fixing a bundle by hand.
    cfield = ConstantField(current=(-0.8, 0.0), wind=(6.0, -4.0))
    seed = R.seed_particles(_blob_feature(), 400, random.Random(143))
    endpoints, conv_idx, members = ens.run_ensemble(
        seed, T0, cfield, 97, 15, n_runs=8, rng=np.random.default_rng(143),
        current_sigma=0.9)
    (clon, clat2), r50, r90 = ens.radii_km(endpoints)
    abstain = r90 > ens.ABSTAIN_RADIUS_KM
    ok &= check("10c  a widened ensemble trips abstain=true at r90 > 40 km",
                abstain and r90 > 40.0 and r50 < r90,
                f"current_sigma 0.9 instead of the honest {ens.CURRENT_SIGMA}: r50 {r50:.1f} km, "
                f"r90 {r90:.1f} km -> abstain={abstain} (trigger is "
                f"r90 > {ens.ABSTAIN_RADIUS_KM:.0f} km). At the honest sigma this case does NOT "
                f"abstain, which is the point -- refusal has to be earned")

    # --- 10d  ...and the honest budget does NOT abstain, so the flag means something ----
    endpoints2, _, _ = ens.run_ensemble(
        seed, T0, cfield, 97, 15, n_runs=8, rng=np.random.default_rng(143))
    _, r50b, r90b = ens.radii_km(endpoints2)
    ok &= check("10d  the same case at the honest sigma does NOT abstain",
                r90b <= ens.ABSTAIN_RADIUS_KM,
                f"current_sigma {ens.CURRENT_SIGMA}: r50 {r50b:.1f} km, r90 {r90b:.1f} km -> "
                f"abstain=False. An abstain flag that fired on everything would be a bug "
                f"dressed as caution")

    return ok
