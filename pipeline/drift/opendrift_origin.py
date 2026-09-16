#!/usr/bin/env python3
"""Stage 2 -- OpenDrift OceanDrift as a SECOND MODEL of the origin cloud (decision C).

    odenv\\Scripts\\python pipeline/drift/opendrift_origin.py --case case-jacksonville-2024

writes  pipeline/drift/out/opendrift_origin_<case>.npz   (read by pool_models.py)

NOT compare_opendrift.py. That file switches OpenDrift's physics OFF to test our integrator and
its 31-550 m agreement number stays exactly as published. This one switches physics ON, because
a second model that is a copy of the first adds no independent information to a pooled cloud:

    Stokes drift (tabularised from wind)      we omit wave transport
    vertical mixing                           we are a pure surface model
    horizontal diffusivity, Okubo at the slick scale, drawn per member
    wind drift factor per element, U(0.025, 0.035)   same budget as ours
    GSHHG landmask + stranding                its own coastline, not ours
    RK4, backward

Frames are stored HOURLY to the rewind horizon, so pool_models.py can weight them by the same age
posterior that weights our frames. Runs in odenv only; nothing on the demo path imports it.
"""
import argparse
import datetime as dt
import json
import random
import sys
import time
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(HERE))

PHYSICS = ["stokes_drift(tabularised)", "vertical_mixing", "horizontal_diffusivity(okubo)",
           "wind_drift_factor U(0.025,0.035) per element", "gshhg_stranding", "rk4"]


def _origin_member(job):
    """One OceanDrift member, backward. Module-level for Windows spawn workers."""
    import logging
    from opendrift.models.oceandrift import OceanDrift
    from opendrift_age import _worker_readers
    (case, t0, seed, K, seedseq, n_el, hours) = job
    logging.getLogger("py.warnings").setLevel(logging.ERROR)
    rng = np.random.default_rng(seedseq)
    o = OceanDrift(loglevel=50)
    o.add_reader(_worker_readers(case))
    for k, v in (("drift:stokes_drift", True), ("drift:use_tabularised_stokes_drift", True),
                 ("drift:vertical_mixing", True), ("general:use_auto_landmask", True),
                 ("general:coastline_action", "stranding"),
                 ("drift:advection_scheme", "runge-kutta4"),
                 ("environment:constant:horizontal_diffusivity", float(K))):
        o.set_config(k, v)
    for k in ("x_sea_water_velocity", "y_sea_water_velocity", "x_wind", "y_wind"):
        o.set_config(f"environment:fallback:{k}", None)
    o.seed_elements(lon=seed[:, 0], lat=seed[:, 1], z=0, time=t0, number=n_el,
                    wind_drift_factor=rng.uniform(0.025, 0.035, n_el))
    o.run(duration=dt.timedelta(hours=hours), time_step=-900, time_step_output=-3600)
    r = o.result
    lon = np.asarray(r["lon"].values, dtype=float)       # (elements, times)
    lat = np.asarray(r["lat"].values, dtype=float)
    st = np.asarray(r["status"].values, dtype=float)
    # a stranded element is held where it beached, as ours are
    for arr in (lon, lat):
        for j in range(1, arr.shape[1]):
            bad = ~np.isfinite(arr[:, j])
            arr[bad, j] = arr[bad, j - 1]
    return np.stack([lon.T, lat.T], axis=-1), float(np.mean(np.nanmax(st, axis=1) == 1))


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--case", required=True)
    ap.add_argument("--hours", type=float, default=72.0)
    ap.add_argument("--members", type=int, default=5)
    ap.add_argument("--elements", type=int, default=2000, help="per member")
    ap.add_argument("--seed", type=int, default=143)
    ap.add_argument("--out", default=str(HERE / "out"))
    ap.add_argument("--jobs", type=int, default=4, help="members in parallel; 1 = serial")
    a = ap.parse_args(argv)

    import opendrift
    import age
    from slick import merge_oil_features, seed_particles

    cdir = REPO / "cases" / a.case
    meta = json.loads((cdir / "meta.json").read_text())
    t0 = dt.datetime.fromisoformat(meta["detection_time"].replace("Z", "+00:00")).replace(
        tzinfo=None)
    feat, _ = merge_oil_features(json.loads((cdir / "detections.geojson").read_text()))
    if feat is None:
        raise SystemExit("no oil detection -- nothing to rewind")
    scale = age.slick_scale_m(feat) or 1000.0
    rng = np.random.default_rng(a.seed)
    ks = age.okubo_member_ks(scale, a.members, rng)

    tic = time.time()
    seeds = np.random.SeedSequence(a.seed).spawn(len(ks))
    jobs = [(a.case, t0,
             np.asarray(seed_particles(feat, a.elements, random.Random(a.seed + m))),
             float(K), seeds[m], a.elements, a.hours) for m, K in enumerate(ks)]

    def report(i, res, secs):
        print(f"  member {i}  K {ks[i]:6.2f} m2/s  stranded {res[1]:.2%}  [{secs:.0f} s]",
              flush=True)

    from opendrift_age import run_members
    results = run_members(jobs, a.jobs, report, fn=_origin_member)
    frames = [r[0] for r in results]                          # (times, elements, 2) each
    stranded = [r[1] for r in results]

    pos = np.concatenate(frames, axis=1)                        # (times, members*elements, 2)
    hours = np.arange(pos.shape[0], dtype=float)                # hourly output, 0 = t0
    path = Path(a.out) / f"opendrift_origin_{a.case}.npz"
    path.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(path, case=np.array(a.case), hours=hours, positions=pos,
                        stranded_fraction=np.array(float(np.mean(stranded))),
                        diffusivity_m2s=ks, physics=np.array(json.dumps(PHYSICS)),
                        opendrift_version=np.array(opendrift.__version__))
    print(f"wrote {path}  {pos.shape}  ({time.time() - tic:.0f} s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
