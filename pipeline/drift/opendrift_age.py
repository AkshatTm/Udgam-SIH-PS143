#!/usr/bin/env python3
"""Stage 2 age engine v2 -- E2/E3: OpenDrift OpenOil as the SECOND model of slick shape.

    odenv\\Scripts\\python pipeline/drift/opendrift_age.py --case case-huntington-2021

Runs in the throwaway OpenDrift venv (requirements-opendrift.txt), NEVER in the project venv
and never on the demo path. It talks to the rest of Stage 2 through two files:

    reads   pipeline/drift/out/age_request_<case>.json   (age.py --request-only, or any age.py run)
    writes  pipeline/drift/out/opendrift_age_<case>.npz  (read by age.load_opendrift_age)

WHY OPENOIL, AND WHY IT IS NOT A COPY OF OUR MODEL
    compare_opendrift.py switches every OpenDrift process OFF to check our integrator. This file
    does the opposite: it switches oil physics ON, because the point is an independent model of
    how a slick of a given age LOOKS, and our model has no oil physics at all.

      evaporation, emulsification, dispersion (wave entrainment)   the oil leaves the surface
      vertical mixing                                               submerged oil stops being SAR-visible
      Stokes drift, from wind (tabularised, no wave field needed)   a transport term we omit
      oil film thickness update                                     thinning as the slick spreads
      horizontal diffusivity, drawn per member                      same Okubo band as ours
      wind drift factor, drawn PER ELEMENT from U(0.025, 0.035)     same budget as ours
      GSHHG landmask, stranding on                                  its own coastline, not ours

    What 1.14.x does NOT have is an explicit Fay gravity-spreading switch, so OpenOil's early
    spreading comes from diffusivity + film thinning. That is written into the output's
    `physics` string so nobody later credits it with a process it did not run.

ONE SIMULATION PER (OIL TYPE, MEMBER), NOT PER CANDIDATE
    Each candidate age h is a cloud seeded at its own release point at t0 - h, tagged with
    `origin_marker = j`. OpenDrift integrates elements that were seeded at different times in
    the same run, so all candidates share one run to t0 and differ only in when and where they
    entered the water -- exactly the question. 20 candidates cost one run, not twenty.

THE SHAPE IS MEASURED THE SAME WAY AS OURS
    age.pca_axes on the surface-floating, non-stranded elements of each candidate at t0, times
    4 for full axes: the identical observable E1 uses, so E1 and E2 are two models of ONE
    observable and age_posterior.mix_logliks is the right way to combine them.
"""
import argparse
import datetime as dt
import json
import sys
import time
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(HERE))

# Ship discharges are mostly fuel/bilge; tanker and pipeline releases are crude. Three generic
# ADIOS records span light-to-heavy without pretending to know which one a slick is.
OIL_TYPES = ("GENERIC MEDIUM CRUDE", "GENERIC INTERMEDIATE FUEL OIL 180", "GENERIC DIESEL")
SURFACE_Z_M = -0.1                   # an element deeper than this is not visible to SAR
PHYSICS = ("OpenOil 1.14: evaporation, emulsification, dispersion, vertical mixing, "
           "tabularised Stokes drift, oil film thickness update, horizontal diffusivity "
           "per member, per-element wind drift factor U(0.025, 0.035), GSHHG stranding, RK4. "
           "No explicit Fay spreading term exists in this version.")


def parse_args(argv=None):
    ap = argparse.ArgumentParser(description="OpenOil candidate curves for the age engine")
    ap.add_argument("--case", required=True)
    ap.add_argument("--out", default=str(HERE / "out"))
    ap.add_argument("--request", default=None, help="default <out>/age_request_<case>.json")
    ap.add_argument("--members", type=int, default=4, help="members PER OIL TYPE")
    ap.add_argument("--elements", type=int, default=400, help="elements per candidate")
    ap.add_argument("--oil-types", nargs="*", default=list(OIL_TYPES))
    ap.add_argument("--seed", type=int, default=143)
    ap.add_argument("--timestep-minutes", type=int, default=15)
    ap.add_argument("--field-case", default=None,
                    help="use this case's cached field (default: --case)")
    ap.add_argument("--batch", action="store_true",
                    help="twin mode: read out/twins/<case>/age_batch_request.json "
                         "(age_twins.py prepare) and write opendrift_age_batch.npz there. "
                         "Use --members 1 --elements 150 to keep it tractable.")
    return ap.parse_args(argv)


def build_readers(field_case):
    """Our cached field as CF NetCDF, via compare_opendrift's writer (no regridding)."""
    import compare_opendrift as C
    from opendrift.readers import reader_netCDF_CF_generic
    npz = REPO / "data" / "fields" / f"{field_case}.npz"
    if not npz.exists():
        raise SystemExit(f"no cached field: {npz}\n  run fetch_fields.py --case {field_case}")
    z = np.load(npz, allow_pickle=False)
    ct, cu, cv = C.hold_last_snapshot(z["current_times"], z["current_u"], z["current_v"])
    wt, wu, wv = C.hold_last_snapshot(z["wind_times"], z["wind_u"], z["wind_v"])
    cn = C.write_cf_netcdf(C.WORK / f"{field_case}_cur.nc", z["current_lons"],
                           z["current_lats"], ct, cu, cv, "u", "v",
                           "x_sea_water_velocity", "y_sea_water_velocity")
    wn = C.write_cf_netcdf(C.WORK / f"{field_case}_wind.nc", z["wind_lons"], z["wind_lats"],
                           wt, wu, wv, "u_wind", "v_wind", "x_wind", "y_wind")
    return [reader_netCDF_CF_generic.Reader(str(cn)), reader_netCDF_CF_generic.Reader(str(wn))]


def run_member(readers, t0, candidate_hours, release_points, oil_type, diffusivity, rng,
               n_el, timestep_minutes, sigma_m=200.0):
    """One OpenOil simulation. Returns dict of per-GROUP L, W, bearing, surface fraction.

    A group is one (age, release point) pair. For a single case the groups are its candidates;
    in --batch mode they are every twin's candidates, flattened, so a whole twin set shares one
    simulation per (oil type, member)."""
    import logging
    from opendrift.models.openoil import OpenOil
    import age

    o = OpenOil(loglevel=50, weathering_model="noaa")
    o.add_reader(readers)
    for k, v in (("processes:evaporation", True), ("processes:emulsification", True),
                 ("processes:dispersion", True), ("processes:update_oilfilm_thickness", True),
                 ("drift:vertical_mixing", True), ("drift:stokes_drift", True),
                 ("drift:use_tabularised_stokes_drift", True),
                 ("general:use_auto_landmask", True), ("general:coastline_action", "stranding"),
                 ("drift:advection_scheme", "runge-kutta4"),
                 ("environment:constant:horizontal_diffusivity", float(diffusivity))):
        o.set_config(k, v)
    # Same loud-miss rule as compare_opendrift: a particle outside the field must not drift
    # through a silent zero ocean.
    for k in ("x_sea_water_velocity", "y_sea_water_velocity", "x_wind", "y_wind"):
        o.set_config(f"environment:fallback:{k}", None)
    logging.getLogger("py.warnings").setLevel(logging.ERROR)

    for j, (h, (lon, lat)) in enumerate(zip(candidate_hours, release_points)):
        cloud = age.seed_cloud(lon, lat, n_el, sigma_m=sigma_m, rng=rng)
        o.seed_elements(lon=cloud[:, 0], lat=cloud[:, 1], z=0,
                        time=t0 - dt.timedelta(hours=float(h)), oil_type=oil_type,
                        origin_marker=j, number=n_el,
                        wind_drift_factor=rng.uniform(0.025, 0.035, n_el))
    o.run(end_time=t0, time_step=timestep_minutes * 60, time_step_output=3600)

    r = o.result
    wdf = np.asarray(r["wind_drift_factor"].values, dtype=float)
    if np.nanstd(wdf) <= 0:
        # requirements-opendrift.txt: a scalar silently applied to every element is the
        # version-specific failure to catch.
        raise SystemExit("wind_drift_factor has no per-element variance -- seeding API changed")
    # origin_marker is (trajectory, time) and NaN before an element is seeded -- a young
    # candidate's elements do not exist at the first output time -- so take the max over time,
    # never column 0 (which silently files every late-seeded element under marker 0).
    om = np.asarray(r["origin_marker"].values, dtype=float)
    marker = (np.nanmax(om, axis=1) if om.ndim == 2 else om).astype(int)
    lon = np.asarray(r["lon"].values, dtype=float)
    lat = np.asarray(r["lat"].values, dtype=float)
    z = np.asarray(r["z"].values, dtype=float)
    st = np.asarray(r["status"].values, dtype=float)
    mass = np.asarray(r["mass_oil"].values, dtype=float)
    # initial mass = the first finite value along each trajectory
    first = np.argmax(np.isfinite(mass), axis=1)
    m0 = mass[np.arange(mass.shape[0]), first]
    lastm = mass[:, -1]
    active_surface = (np.isfinite(lon[:, -1]) & (st[:, -1] == 0) & (z[:, -1] > SURFACE_Z_M))

    L, W, B, SF, N = [], [], [], [], []
    for j in range(len(candidate_hours)):
        sel = marker == j
        vis = sel & active_surface
        N.append(int(vis.sum()))
        tot = float(np.nansum(m0[sel]))
        SF.append(float(np.nansum(np.where(vis, lastm, 0.0))) / tot if tot > 0 else 0.0)
        if vis.sum() >= 10:
            sd1, sd2, brg = age.pca_axes(np.column_stack([lon[vis, -1], lat[vis, -1]]))
            L.append(4.0 * sd1)
            W.append(4.0 * sd2)
            B.append(brg)
        else:
            L.append(np.nan)
            W.append(np.nan)
            B.append(np.nan)
    return {"L": L, "W": W, "B": B, "SF": SF, "N": N}


def main_batch(a):
    """Twin mode: E2/E3 curves for every twin in out/twins/<case>/age_batch_request.json."""
    import opendrift
    import step
    d = HERE / "out" / "twins" / a.case
    req = json.loads((d / "age_batch_request.json").read_text())
    t0 = dt.datetime.fromisoformat(req["t0"].replace("Z", "+00:00")).replace(tzinfo=None)
    hours = [float(h) for h in req["candidate_hours"]]
    import age as _age
    ids = [b["id"] for b in req["batch"]]
    nt, nc = len(ids), len(hours)
    # K is global to an OpenOil run, but the Okubo prior depends on each twin's own scale, so
    # twins are grouped into scale terciles and each group gets its own K draws.
    scales = np.array([float(b.get("okubo_scale_m") or 1000.0) for b in req["batch"]])
    groups = [g for g in np.array_split(np.argsort(scales), min(3, nt)) if len(g)]
    readers = build_readers(a.case)
    rng = np.random.default_rng(a.seed)
    per = {k: [[] for _ in range(nt)] for k in ("L", "W", "B", "SF")}
    tic = time.time()
    for oil in a.oil_types:
        for g in groups:
            scale = float(np.exp(np.mean(np.log(scales[g]))))
            gh, gp = [], []
            for i in g:
                gh += hours
                gp += [tuple(p) for p in req["batch"][i]["release_points"]]
            sig = step.stratified_loguniform(a.members, *_age.RELEASE_SIGMA_RANGE_M, rng)
            for K, s0 in zip(_age.okubo_member_ks(scale, a.members, rng), sig):
                res = run_member(readers, t0, gh, gp, oil, K, rng, a.elements,
                                 a.timestep_minutes, sigma_m=float(s0))
                for k in per:
                    blk = np.asarray(res[k], dtype=float).reshape(len(g), nc)
                    for r, i in enumerate(g):
                        per[k][i].append(blk[r])
                print(f"  batch {oil:<34} scale {scale:7.0f} m  K {K:6.2f}  {len(g)} twins  "
                      f"[{time.time() - tic:.0f} s]", flush=True)
    # -> (twins, members, cands)
    arr = {k: np.asarray(v, dtype=float) for k, v in per.items()}
    gone = ~np.isfinite(arr["L"])
    arr["L"][gone], arr["W"][gone], arr["B"][gone] = 1e-3, 1e-3, 0.0
    path = d / "opendrift_age_batch.npz"
    np.savez_compressed(path, case=np.array(a.case), ids=np.array(ids),
                        candidate_hours=np.asarray(hours), L_km=arr["L"], W_km=arr["W"],
                        bearing_deg=arr["B"], surface_fraction=arr["SF"],
                        physics=np.array(PHYSICS),
                        opendrift_version=np.array(opendrift.__version__))
    print(f"wrote {path}  ({len(ids)} twins, {time.time() - tic:.0f} s)")
    return 0


def main(argv=None):
    a = parse_args(argv)
    if a.batch:
        return main_batch(a)
    out_dir = Path(a.out)
    req_path = Path(a.request) if a.request else out_dir / f"age_request_{a.case}.json"
    if not req_path.exists():
        raise SystemExit(f"{req_path} not found.\n  run first (project venv): "
                         f"python pipeline/drift/age.py --case {a.case} --real --request-only")
    req = json.loads(req_path.read_text())
    if req["case"] != a.case:
        raise SystemExit(f"{req_path} is for {req['case']}, not {a.case}")
    import opendrift
    import step
    t0 = dt.datetime.fromisoformat(req["t0"].replace("Z", "+00:00")).replace(tzinfo=None)
    hours = [float(h) for h in req["candidate_hours"]]
    rel = [tuple(p) for p in req["release_points"]]
    readers = build_readers(a.field_case or a.case)

    rng = np.random.default_rng(a.seed)
    k_lo, k_hi = step.DIFFUSIVITY_RANGE_M2S
    rows = {"L": [], "W": [], "B": [], "SF": [], "N": []}
    meta = []
    tic = time.time()
    import age as _age
    for oil in a.oil_types:
        # Same Okubo prior as E1, at the same observed scale -- two models, one K budget.
        if req.get("okubo_scale_m"):
            ks = _age.okubo_member_ks(float(req["okubo_scale_m"]), a.members, rng)
        else:
            ks = step.stratified_loguniform(a.members, k_lo, k_hi, rng)
        # the release's initial size is a nuisance parameter here exactly as in E1
        sig = step.stratified_loguniform(a.members, *_age.RELEASE_SIGMA_RANGE_M, rng)
        for m, K in enumerate(ks):
            res = run_member(readers, t0, hours, rel, oil, K, rng, a.elements,
                             a.timestep_minutes, sigma_m=float(sig[m]))
            for k in rows:
                rows[k].append(res[k])
            meta.append({"oil_type": oil, "diffusivity_m2s": round(float(K), 2),
                         "release_sigma_m": round(float(sig[m]), 1)})
            print(f"  {oil:<36} K {K:6.1f}  visible/candidate "
                  f"{min(res['N'])}-{max(res['N'])}  surface frac "
                  f"{res['SF'][0]:.2f} (1st) -> {res['SF'][-1]:.2f} (last)   "
                  f"[{time.time() - tic:.0f} s]", flush=True)

    # A member/candidate with too few visible elements has no shape. Its likelihood is taken
    # as "this age produces no visible slick": L = W = a tiny value, so it scores ~0 in E2 --
    # which is exactly the information (fully weathered/stranded = not what SAR saw).
    L = np.asarray(rows["L"], dtype=float)
    W = np.asarray(rows["W"], dtype=float)
    B = np.asarray(rows["B"], dtype=float)
    gone = ~np.isfinite(L)
    L[gone], W[gone], B[gone] = 1e-3, 1e-3, 0.0

    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"opendrift_age_{a.case}.npz"
    np.savez_compressed(path, case=np.array(a.case), candidate_hours=np.asarray(hours),
                        L_km=L, W_km=W, bearing_deg=B,
                        surface_fraction=np.asarray(rows["SF"], dtype=float),
                        visible=np.asarray(rows["N"], dtype=int),
                        members=np.array(json.dumps(meta)),
                        physics=np.array(PHYSICS),
                        opendrift_version=np.array(opendrift.__version__),
                        field_case=np.array(a.field_case or a.case))
    print(f"wrote {path}   ({len(meta)} members x {len(hours)} candidates, "
          f"{time.time() - tic:.0f} s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
