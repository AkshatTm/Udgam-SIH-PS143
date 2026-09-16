#!/usr/bin/env python3
"""
Stage 2 — backward drift. Owner: Anushka.

    python pipeline/drift/run.py --case case-000 --real          # PHASE 3, the real thing
    python pipeline/drift/run.py --case case-000 --fake          # analytic ocean, no GEE

PHASE 3. Reads `detections.geojson`, seeds particles off the highest-confidence oil feature,
rewinds them 24 h through the RK2 integrator (`step.py`), and writes the two files the rest of
the project consumes:

    out/particles.json   the animation  -- ONE control run, 3000 particles x 97 frames
    out/origin.json      the answer     -- 50 perturbed runs pooled into a probability grid

WHY TWO DIFFERENT THINGS
    The slider needs coherent trajectories a human can follow, so `particles.json` is the
    single unperturbed run. The origin cloud needs uncertainty, so `origin.json` comes from
    the 50-member ensemble in `ensemble.py`. Showing the ensemble as the animation would look
    like fog; showing the control run as the answer would claim a precision we do not have.

PHASE HISTORY
    Phase 1  real RK2 over an analytic ocean (`--fake`), four known-answer tests
    Phase 2  the analytic ocean swapped for HYCOM + ERA5 under the same two methods
    Phase 3  --real, the 50-run ensemble, the true histogram grid, the convergence window
"""
import argparse
import json
import math
import random
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np

import coastline
import ensemble as ens
from fields import load_case_field, make_fake
import step
from step import (assert_displacement_plausible, assert_field_covers,
                  assert_inside_field_box, displacement_km, edge_distance_km,
                  integrate, integrate_stranding)
# Seeding and slick selection live in slick.py so that age.py can import them without a cycle
# back through run.py (Phase 0, 16 Sept 2026). Re-exported below for callers that still reach
# for `run.merge_oil_features`.
from slick import (KM_PER_DEG as _SLICK_KM_PER_DEG, is_one_ribbon, merge_oil_features,
                   merged_discharge_class, pick_slick, ribbon_metrics, seed_geometry,
                   seed_particles, slick_rings)

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
OUT = HERE / "out"

KM_PER_DEG = 111.32
ABSTAIN_RADIUS_KM = ens.ABSTAIN_RADIUS_KM


def iso(dt):
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_ts(s):
    dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        raise SystemExit(f"'{s}' is timezone-naive — every timestamp needs the trailing Z")
    return dt


def r5(x):
    return round(float(x), 5)




def subsample_for_output(history, integration_dt_min, output_dt_min):
    """Thin an integration history down to the frames that ship in particles.json.

    THE INTEGRATION TIMESTEP AND THE OUTPUT TIMESTEP ARE DIFFERENT THINGS, and conflating them
    is the next silent bug in this file. Integration runs at 15 min because that is what the RK2
    error budget and the known-answer tests are built on. OUTPUT runs at 45 min because the
    frontend animates it: at 72 h, 15-min frames would be 289 x 3000 positions, about 17 MB of
    JSON, against the 97 x 3000 the demo machine was actually tested on (web/CLAUDE.md).

    72 h at 45 min is 96 intervals = 97 stored positions -- byte-for-byte the same shape
    particles.json has always had, so nothing in web/ changes and frozen convention 4
    (duration = (n_steps - 1) x timestep_minutes) still holds exactly, now against the OUTPUT
    timestep that particles.json actually declares.

    Returns (frames, output_dt_min). Refuses rather than silently shipping a file whose declared
    timestep does not match its contents.
    """
    stride = output_dt_min / integration_dt_min
    if abs(stride - round(stride)) > 1e-9:
        raise SystemExit(
            f"--output-timestep-minutes {output_dt_min} is not a whole multiple of "
            f"--timestep-minutes {integration_dt_min}. particles.json declares ONE timestep and "
            f"the frontend derives every frame time from it, so a fractional stride would put "
            f"every rendered timestamp slightly wrong with nothing to catch it.")
    stride = int(round(stride))
    frames = history[::stride]
    span_in = (len(history) - 1) * integration_dt_min
    span_out = (len(frames) - 1) * output_dt_min
    if span_out != span_in:
        raise SystemExit(
            f"subsampling changed the span: {span_in} min integrated but {span_out} min would "
            f"be declared ({len(history)} frames at {integration_dt_min} min -> {len(frames)} "
            f"at {output_dt_min} min). Choose --steps so that (steps-1) is divisible by "
            f"{stride}.")
    return frames, output_dt_min


def write_particles(path, t0, positions, dt_min):
    path.write_text(json.dumps({
        "t0": iso(t0), "direction": "backward", "timestep_minutes": dt_min,
        "n_steps": len(positions), "n_particles": len(positions[0]),
        "positions": positions}))


def wind_share_of_drift(field, history, times, wind_coeff=step.WIND_COEFF):
    """What fraction of the drift that actually moved this cloud came from the wind term?

    Phase 5.3 found this the hard way. `case-gulf-alaska-2023` rewinds to an origin in the WEST
    where the brief predicted EAST, and neither the integrator nor any guard was wrong: the
    Alaska Current is simply absent from that field (24 h mean 0.041 m/s, direction wandering
    with no preferred heading) and a persistent easterly 4-6.5 m/s wind supplies 81% of the
    drift vector. The brief's prediction came from a basin-scale current climatology, which does
    not describe a 9 km HYCOM cell on one afternoon.

    Nothing in the output said so. A reviewer comparing the origin against a current atlas would
    have called it a sign error, and the only way to tell them apart was to decompose the field
    by hand. So it is decomposed here, once, along the control trajectory -- sampling the path
    the cloud took rather than a fixed point, because on a weak-current case the two differ
    (Huntington's origin bearing moves 143 degrees between a t0 sample and a window mean).

    The number is a DIAGNOSTIC, not an error bar. It does not widen the cloud and does not
    reduce confidence in the answer: the ensemble already perturbs the coefficient over
    U(0.025, 0.035), and across that honest range the origin direction moves at most 5 degrees
    on every case in the library. What a high share means is narrower and more useful -- that
    the answer rests on ERA5 and the 3% rule rather than on HYCOM, so it should be checked
    against a wind reanalysis and NOT against a current atlas.

    Returns None on a SYNTHETIC field, rather than 0.0. Every field class here implements
    get_wind -- the analytic and constant ones just return their configured constant, which is
    (0, 0) by default -- so `hasattr` is not the test. The test is whether the wind came from
    ERA5 at all, and the idiom for that in this file is already `bbox`: a real fetched field has
    a box, the lab fields do not. On a lab field the share would be a true statement about a
    field that is not an ocean, and writing it into origin.json would invite exactly the
    misreading the field exists to prevent (CONTRACTS.md 6.5, the rule stranded_fraction
    follows: absence hides a row, a false number misinforms one).
    """
    if getattr(field, "bbox", None) is None or not hasattr(field, "get_wind"):
        return None
    pos = np.asarray(history, dtype=np.float64)
    cur_mag, wind_mag = [], []
    for i, when in enumerate(times[:len(pos)]):
        lons, lats = pos[i][:, 0], pos[i][:, 1]
        cu, cv = field.get_uv(lons, lats, when)
        wu, wv = field.get_wind(lons, lats, when)
        cu, cv = np.asarray(cu, float), np.asarray(cv, float)
        wu, wv = np.asarray(wu, float), np.asarray(wv, float)
        if not np.isfinite(wu).any():
            return None
        cur_mag.append(np.nanmean(np.hypot(cu, cv)))
        wind_mag.append(wind_coeff * np.nanmean(np.hypot(wu, wv)))
    c, w = float(np.mean(cur_mag)), float(np.mean(wind_mag))
    if c + w <= 0.0:
        return None
    return w / (c + w), c, w


def write_origin(path, endpoints, conv_idx, members, t0, timestep_minutes, n_steps,
                 n_runs, stranded_fraction=None, wind_share=None, pool=None,
                 age_block=None, model_mix=None):
    """The real thing: a histogram of every ensemble endpoint, radii measured from the raw
    points, and a time window that is honest about whether it was measured or bounded.

    AGE ENGINE v2:
      pool       (points, weights) from ens.age_weighted_pool -- the cloud at every plausible
                 age, weighted by that age's probability. Grid, radii and abstain all come from
                 this ONE pool, so they cannot disagree. None -> the final-step endpoints, as
                 before, bit for bit.
      age_block  the age keys from age.estimate_age, written verbatim. When it carries an
                 age_posterior AND a pool is given, the time window is the posterior's 80 % HPD
                 (method "age"); an age reported without driving the pool leaves the window
                 exactly as it was, so the two never contradict each other.
      model_mix  pool_models.py's record of which models the pool came from.
    """
    pts, w = (endpoints, None) if pool is None else pool
    (clon, clat), r50, r90 = ens.radii_km(pts, weights=w)
    bounds, values = ens.origin_grid(pts, weights=w)

    band = None
    if pool is not None and age_block and age_block.get("age_posterior"):
        band = age_block["age_hours"]
    start, end, method = ens.time_window(
        conv_idx,
        [m["spread_start_km"] for m in members],
        [m["spread_min_km"] for m in members],
        t0, timestep_minutes, n_steps, age_band=band)

    rows, cols = values.shape
    doc = {
        "bounds": bounds,
        "shape": [rows, cols],
        "values": [float(v) for v in values.reshape(-1)],
        "centroid": [r5(clon), r5(clat)],
        "radius_50_km": round(r50, 2),
        "radius_90_km": round(r90, 2),
        "time_window": [iso(start), iso(end)],
        "ensemble_runs": int(n_runs),
        "abstain": bool(r90 > ABSTAIN_RADIUS_KM),
        # Additive field the brief asks for (docs/team/anushka-stage2-drift.md Phase 3 step 3): says whether
        # the window was measured from ensemble convergence or is the bounded fallback.
        # Not part of the frozen schema — Akshat, flag it if you would rather it lived
        # somewhere else; nothing breaks if the frontend ignores it.
        "time_window_method": method,
    }
    # Phase 4.3. A high fraction is itself a signal -- it means the slick may have originated
    # ashore, or the rewind is running past a coastline. Either is worth surfacing, not hiding.
    # Omitted entirely when there is no real coastline, because 0.0 would be a claim we cannot
    # make: absence hides a UI row, a false zero misinforms one (CONTRACTS.md 6.5).
    if stranded_fraction is not None:
        doc["stranded_fraction"] = round(float(stranded_fraction), 4)
    # Phase 5.3. Says which input the answer actually rests on -- see wind_share_of_drift().
    # Omitted, never zeroed, when the field has no wind term.
    if wind_share is not None:
        doc["wind_share"] = round(float(wind_share), 4)
    if age_block:
        doc.update(age_block)
    if model_mix:
        doc["model_mix"] = model_mix
    path.write_text(json.dumps(doc))
    return clon, clat, r50, r90, method, doc["abstain"]


def run_age(a, meta, t0, field, feat, history, case_dir, land, span_h):
    """Age engine v2 inside the main run. Returns the age block for origin.json.

    Release points come from THIS run's control rewind (`history`), so the ages and the
    origin cloud are built on one backward trajectory. The full diagnostic record goes to
    out/age_<case>.json (working space, never in the bundle).
    """
    import age as age_engine
    lo, hi, st = 2.0, 72.0, 4.0
    cands = sorted({1.0, *[round(x, 6) for x in np.arange(lo, hi + 1e-9, st)]})
    cands = [h for h in cands if h <= span_h]
    if a.real:
        cov = age_engine.field_time_coverage(a.case, REPO)
        cands, dropped, _ = age_engine.clip_candidates_to_coverage(cands, t0, cov)
    release = age_engine.release_points_from_history(history, cands, a.timestep_minutes)
    out_dir = Path(a.out)
    opendrift = age_engine.load_opendrift_age(out_dir, a.case)
    c_centre, c_edge, cdiag = age_engine.sar_contrast(case_dir, feat)
    props = feat["properties"]
    print(f"              age  {len(cands)} candidates, OpenOil "
          f"{'loaded' if opendrift is not None else 'absent (our model only)'}")
    block, report = age_engine.estimate_age(
        field, feat, t0, cands, (float(props["centroid"][0]), float(props["centroid"][1])),
        release_points=release, volume_m3=a.volume_m3, n_members=a.age_members,
        timestep_minutes=a.timestep_minutes, seed=a.seed, opendrift=opendrift,
        contrast=(c_centre, c_edge), log=lambda s: print("                " + s))
    report.update({"case": a.case, "t0": meta["detection_time"], "sar_contrast": cdiag,
                   "release_points": [[round(x, 5), round(y, 5)] for x, y in release]})
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / f"age_{a.case}.json").write_text(
        json.dumps(report, indent=1, default=age_engine._json_default))
    post = report["posterior"]
    if post["status"] == "ok":
        print(f"              age  {block['age_hours']} h (80% HPD), median {post['median']} h, "
              f"method {block['age_method']}, gain {post['info_gain_nats']} nats")
    else:
        print(f"              age  none -- {post.get('reason')}")
    return block


def write_particles_forward(path, t0, positions, dt_min):
    """particles_forward.json. A SEPARATE FILE and a SEPARATE INTEGRATION (Master 6.4).

    The validator compares the position array against particles.json and ERRORS if they are
    identical, so a relabelled copy is caught mechanically. It should be -- forward and backward
    answer different questions and a copy would answer neither.
    """
    path.write_text(json.dumps({
        "t0": iso(t0), "direction": "forward", "timestep_minutes": dt_min,
        "n_steps": len(positions), "n_particles": len(positions[0]),
        "positions": positions}))


def coastal_impact(history, times, strand_step, dt_min):
    """Phase 2.3. What the forward run says about the coast, and only what it can say.

    Forward-from-slick answers the question a coast guard actually asks -- which coastline is
    threatened, and when. Forward-from-origin would only recreate the slick we already detected.

    What is measurable here: whether particles beach, WHEN the first one does, WHERE, and how
    the stranded fraction grows with time. What is NOT measurable and is therefore not claimed:
    the NAME of the affected stretch. That needs a coastline gazetteer, which is another
    dependency and another thing to get wrong; the landfall footprint below is the honest
    substitute and a human can name it from a map in five seconds.
    """
    n = history.shape[1]
    # A particle SEEDED on land did not make landfall -- it was already ashore at t0, which is a
    # Stage 1 data-quality signal (the detected polygon overlaps the coast), not a forecast.
    # Conflating the two reports "first landfall 0.00 h" and misstates the coastal impact.
    seeded_ashore = strand_step == 0
    landed = strand_step > 0
    out = {
        "n_particles": int(n),
        "seeded_ashore_fraction": float(np.mean(seeded_ashore)),
        "stranded_fraction": float(np.mean(strand_step >= 0)),
        "landfall_fraction": float(np.mean(landed)),
        "span_hours": (len(times) - 1) * dt_min / 60.0,
        "first_landfall": None,
        "landfall_footprint": None,
        "eta_curve": [],
        "note": ("stretch NAMES are not reported: that needs a coastline gazetteer we do not "
                 "have. The footprint is the measured substitute."),
    }
    if seeded_ashore.any():
        out["seeded_ashore_warning"] = (
            f"{out['seeded_ashore_fraction'] * 100:.1f}% of particles were ON LAND at t0. They "
            f"are excluded from the landfall statistics because they never made landfall -- "
            f"they started ashore. This means the detected polygon overlaps the coastline, "
            f"which is Stage 1's to look at.")

    if not landed.any():
        out["verdict"] = ("no particle reached land within the modelled span -- no coastal "
                          "impact from this release at this horizon")
        return out

    k_first = int(strand_step[landed].min())
    who = int(np.argmax(strand_step == k_first))
    pos_first = history[k_first, who]
    out["first_landfall"] = {
        "hours_after_t0": k_first * dt_min / 60.0,
        "time": iso(times[k_first]),
        "position": [r5(float(pos_first[0])), r5(float(pos_first[1]))],
    }
    pts = np.array([history[int(strand_step[i]), i] for i in np.flatnonzero(landed)])
    out["landfall_footprint"] = {
        "west": r5(float(pts[:, 0].min())), "east": r5(float(pts[:, 0].max())),
        "south": r5(float(pts[:, 1].min())), "north": r5(float(pts[:, 1].max())),
        "centroid": [r5(float(pts[:, 0].mean())), r5(float(pts[:, 1].mean()))],
    }
    for hours in range(0, int(out["span_hours"]) + 1, 3):
        k = int(round(hours * 60.0 / dt_min))
        frac = float(np.mean(landed & (strand_step <= k)))
        out["eta_curve"].append({"hours": hours, "stranded_fraction": round(frac, 4)})
    out["verdict"] = (f"first landfall {out['first_landfall']['hours_after_t0']:.2f} h after "
                      f"detection, {out['landfall_fraction'] * 100:.1f}% of particles ashore "
                      f"by {out['span_hours']:.0f} h")
    return out


def run_forward(a, meta, t0, field, seed, feat, out_dir):
    """PHASE 2. Forward from the slick at t0 -- which coast is threatened, and when.

    Deliberately does NOT touch particles.json or origin.json, and does not run the ensemble.
    Those are the backward product; Harshita builds against them and a forward run must not
    disturb them.
    """
    span_h = (a.steps - 1) * a.timestep_minutes / 60.0

    # The field must actually cover the future. Without this the run is a frozen snapshot.
    # Presented as a clean refusal rather than a traceback: this is a "refetch a wider window"
    # instruction for a person, not a crash.
    from step import FieldTimeSpan
    try:
        cov = assert_field_covers(field, t0, t0 + timedelta(hours=span_h), "forward run")
    except FieldTimeSpan as exc:
        raise SystemExit(str(exc))
    if cov is not None:
        print(f"              coverage  field spans {cov[0]:%Y-%m-%dT%H:%MZ} -> "
              f"{cov[1]:%Y-%m-%dT%H:%MZ}  (overhang {cov[2]:.2f} h, tolerated)")

    land = coastline.is_land if coastline.available() else None
    print(f"              coast  {coastline.describe()}")

    history, times, stranded, strand_step = integrate_stranding(
        seed, t0, field, a.steps, a.timestep_minutes, direction="forward",
        is_land=land, return_strand_step=True)

    positions = np.round(history, 5).tolist()
    out_dir.mkdir(parents=True, exist_ok=True)
    fwd_path = out_dir / "particles_forward.json"
    fwd_frames, fwd_dt = subsample_for_output(np.asarray(positions), a.timestep_minutes,
                                              a.output_timestep_minutes)
    write_particles_forward(fwd_path, t0, fwd_frames.tolist(), fwd_dt)

    impact = coastal_impact(history, times, strand_step, a.timestep_minutes)
    impact_path = out_dir / f"coastal_impact_{a.case}.json"
    impact_path.write_text(json.dumps(impact, indent=2))

    # a forward run must not be a relabelled backward run; prove it here rather than waiting
    # for the validator to catch it
    back_path = out_dir / "particles.json"
    if back_path.exists():
        back = json.loads(back_path.read_text())
        same = back.get("positions") == positions
        print(f"              distinct from particles.json: {not same}"
              + ("  !! IDENTICAL - the validator will reject this" if same else ""))

    dist = displacement_km(history[0], history[-1])
    print(f"[drift:FWD]   wrote {fwd_path}")
    print(f"              wrote {impact_path}   (working space - not in the bundle)")
    print(f"              seeded {a.particles} from {feat['properties']['id']}, ran FORWARD "
          f"{span_h:.2f} h in {a.steps} steps of {a.timestep_minutes} min")
    print(f"              t0 {iso(t0)} -> {iso(times[-1])}")
    print(f"              displacement  median {float(np.median(dist)):.1f} km   "
          f"max {float(dist.max()):.1f} km")
    if impact.get("seeded_ashore_warning"):
        print(f"              !! {impact['seeded_ashore_warning']}")
    print(f"              coastal impact: {impact['verdict']}")
    if impact["first_landfall"]:
        fl = impact["first_landfall"]
        fp = impact["landfall_footprint"]
        print(f"                first ashore at {fl['position']} at {fl['time']}")
        print(f"                footprint W {fp['west']} S {fp['south']} "
              f"E {fp['east']} N {fp['north']}")
    print(f"              NOTE {impact['note']}")
    return 0


def main():
    ap = argparse.ArgumentParser(description="Stage 2 — backward drift + 50-run ensemble")
    ap.add_argument("--case", required=True)
    ap.add_argument("--cases-root", default=str(REPO / "cases"))
    ap.add_argument("--real", action="store_true",
                    help="PHASE 3: real HYCOM + ERA5 from data/fields/<case>.npz")
    ap.add_argument("--fake", action="store_true",
                    help="real RK2 integrator driven by analytic fields (Phase 1)")
    ap.add_argument("--stub", action="store_true", help=argparse.SUPPRESS)  # back-compat alias
    ap.add_argument("--field", choices=["analytic", "constant"], default="analytic",
                    help="with --fake: analytic = a vortex cell on the slick; constant = uniform")
    ap.add_argument("--wind", type=float, nargs=2, default=(6.0, -4.0), metavar=("U", "V"),
                    help="with --fake: 10 m wind, signed m/s components (east, north)")
    ap.add_argument("--fake-current", type=float, nargs=2, default=(0.5, 0.0),
                    metavar=("U", "V"),
                    help="with --fake --field constant: the uniform current, signed m/s. "
                         "ConstantField defaults to a DEAD ocean (0, 0), which makes the mode "
                         "wind-only and means --current-sigma has nothing to scale. 0.5 m/s "
                         "east matches the convention in tests.py.")
    ap.add_argument("--particles", type=int, default=3000)
    ap.add_argument("--runs", type=int, default=50,
                    help="ensemble members. The cut order allows 25; say so in origin.json.")
    ap.add_argument("--steps", type=int, default=289,
                    help="STORED POSITIONS, not physics steps: 289 = t0 + 288 backward "
                         "intervals of 15 min = exactly 72.0 h (CONTRACTS.md 5). Was 97 (24 h) "
                         "until 16 Sept 2026; the rewind now has to be able to reach a release "
                         "two days before the pass, and the age band picks the slice.")
    ap.add_argument("--timestep-minutes", type=int, default=15,
                    help="INTEGRATION timestep. Not what particles.json declares -- see "
                         "--output-timestep-minutes.")
    ap.add_argument("--output-timestep-minutes", type=int, default=45,
                    help="timestep particles.json DECLARES and ships. 72 h at 45 min is 97 "
                         "frames, the same size the frontend was tested at; 15-min frames over "
                         "72 h would be ~17 MB of JSON.")
    ap.add_argument("--seed", type=int, default=143)
    ap.add_argument("--merge-oil", choices=["auto", "always", "never"], default="auto",
                    help="a slick broken into several oil features is ONE slick when it "
                         "measures as one ribbon (Soumirya, 13 Sept: Jacksonville is one slick "
                         "with genuine breaks). 'auto' merges only when all four ribbon gates "
                         "pass and prints them either way; 'never' restores the old "
                         "single-highest-confidence behaviour.")
    ap.add_argument("--current-sigma", type=float, default=None,
                    help="width of the current-scale perturbation. Default is the honest "
                         f"{ens.CURRENT_SIGMA} (+/-15%%). Widening it is how the ABSTAIN fixture "
                         "is produced (Phase 3.3): the pipeline writes a real schema-valid "
                         "bundle with abstain=true instead of anyone hand-editing one. A "
                         "non-default value is announced in the output and must never be "
                         "presented as a case result.")
    ap.add_argument("--forward", action="store_true",
                    help="PHASE 2: run FORWARD from the slick at t0 and write "
                         "particles_forward.json + a coastal impact summary. Does not touch "
                         "particles.json or origin.json, and does not run the ensemble.")
    ap.add_argument("--out", default=str(OUT), help="directory for particles.json/origin.json")
    ap.add_argument("--age", choices=["off", "report", "drive"], default="report",
                    help="AGE ENGINE v2. off: no age. report: write the age keys, origin "
                         "unchanged. drive: the origin cloud, radii, abstain and time_window "
                         "come from the ensemble pooled over the age posterior.")
    ap.add_argument("--volume-m3", type=float, default=None,
                    help="official release volume, for the Fay regime verdict only")
    ap.add_argument("--age-members", type=int, default=20)
    a = ap.parse_args()

    if not (a.real or a.fake or a.stub):
        raise SystemExit(
            "choose an ocean: --real (HYCOM + ERA5, Phase 3) or --fake (analytic, Phase 1).\n"
            "--real needs data/fields/<case>.npz — run pipeline/drift/fetch_fields.py first.")
    if a.real and a.fake:
        raise SystemExit("--real and --fake are mutually exclusive.")

    case_dir = Path(a.cases_root) / a.case
    det_path = case_dir / "detections.geojson"
    if not det_path.exists():
        raise SystemExit(f"{det_path} not found — Stage 2 seeds from Stage 1's output. "
                         f"Run pipeline/detect/run.py first, or use cases/case-000.")

    meta = json.loads((case_dir / "meta.json").read_text())
    t0 = parse_ts(meta["detection_time"])
    feat, slick_diag = merge_oil_features(json.loads(det_path.read_text()),
                                          mode=a.merge_oil)
    if feat is None:
        raise SystemExit(
            "detections.geojson contains zero 'oil' features. That is the no-spill case — "
            "there is nothing to rewind, and 'trace' should not be in meta.acts_available.")

    rng = random.Random(a.seed)
    seed = seed_particles(feat, a.particles, rng)

    if a.real:
        field = load_case_field(a.case, repo_root=REPO)
        tag = "REAL"
    else:
        clon0 = float(feat["properties"]["centroid"][0])
        clat0 = float(feat["properties"]["centroid"][1])
        fake_kw = {"wind": tuple(a.wind)}
        if a.field == "constant":
            fake_kw["current"] = tuple(a.fake_current)
        field = make_fake(a.field, lon0=clon0, lat0=clat0, **fake_kw)
        tag = "FAKE"

    geom_kind, geom_why = seed_geometry(feat["properties"])
    print(f"[drift:{tag}]  seeding {geom_kind.upper()}: {geom_why}")

    if a.forward:
        return run_forward(a, meta, t0, field, seed, feat, Path(a.out))

    span_h = (a.steps - 1) * a.timestep_minutes / 60.0    # states recorded, not steps taken

    # ---- control run: the animation ---------------------------------------------------
    # The BACKWARD run needs coverage too, and did not check it. Jacksonville is the case that
    # showed why: fetched with filterDate(start, t0), its last HYCOM snapshot lands 2.36 h
    # BEFORE t0, because the 3-hourly snapshots go ...18:00, 21:00, 00:00 and t0 is 23:21. So
    # the first 2.36 h of the rewind -- the end NEAREST the detection, where the answer is most
    # sensitive -- ran through a frozen field, silently. --forward-hours fixes both directions
    # at once, because it pulls the snapshots that bracket t0 instead of stopping short of it.
    from step import FieldTimeSpan
    try:
        cov = assert_field_covers(field, t0, t0 - timedelta(hours=span_h), "backward run")
        if cov is not None and cov[2] > 0.0:
            print(f"              coverage  field spans {cov[0]:%Y-%m-%dT%H:%MZ} -> "
                  f"{cov[1]:%Y-%m-%dT%H:%MZ}  (overhang {cov[2]:.2f} h, tolerated)")
    except FieldTimeSpan as exc:
        raise SystemExit(str(exc))

    land = coastline.is_land if coastline.available() else None
    print(f"              coast  {coastline.describe()}")
    if not coastline.available():
        print(f"              NOTE   {coastline.why_unavailable()}")
    history, times, stranded_ctl = integrate_stranding(
        seed, t0, field, a.steps, a.timestep_minutes, direction="backward", is_land=land)
    positions = np.round(history, 5).tolist()

    # ---- ensemble: the answer ---------------------------------------------------------
    if a.current_sigma is not None and abs(a.current_sigma - ens.CURRENT_SIGMA) > 1e-9:
        print(f"[drift:{tag}]  !! CURRENT SIGMA OVERRIDDEN: {a.current_sigma} instead of the "
              f"honest {ens.CURRENT_SIGMA}.")
        print(f"              This widens the uncertainty budget beyond what the physics "
              f"supports. The only sanctioned use is")
        print(f"              producing the Phase 3.3 abstain fixture. This output is NOT a "
              f"case result and must not be shown as one.")

    nprng = np.random.default_rng(a.seed)

    def tick(done, total):
        if done == 1 or done % 10 == 0 or done == total:
            print(f"              ensemble {done}/{total}", flush=True)

    # ---- age engine v2: how old is this slick? ----------------------------------------
    # Runs BEFORE the ensemble because the ensemble needs to know which steps to keep. A
    # failure here must never block the bundle: the narrow except degrades to "no age",
    # which reproduces the pre-v2 origin exactly.
    age_block = None
    if a.age != "off" and not a.stub:
        try:
            age_block = run_age(a, meta, t0, field, feat, history, case_dir, land, span_h)
        except Exception as exc:                                     # noqa: BLE001
            print(f"[drift:{tag}]  !! AGE ENGINE FAILED, continuing without an age: "
                  f"{type(exc).__name__}: {exc}")
            age_block = None
    post = (age_block or {}).get("age_posterior")
    drive = a.age == "drive" and post is not None
    collect = None
    if drive:
        collect = [int(round(h * 60.0 / a.timestep_minutes)) for h in post["hours_grid"]]

    res = ens.run_ensemble(
        seed, t0, field, a.steps, a.timestep_minutes, n_runs=a.runs, rng=nprng, progress=tick,
        is_land=land, current_sigma=a.current_sigma, collect_steps=collect)
    pool = None
    if drive:
        endpoints, conv_idx, members, collected = res
        pool = ens.age_weighted_pool(collected, post["hours_grid"], post["prob"],
                                     a.timestep_minutes, hpd=post["hpd80"])
        if pool[0] is None:
            pool = None
        else:
            np.savez_compressed(Path(a.out) / f"age_pool_{a.case}.npz", points=pool[0],
                                weights=pool[1])
            print(f"              age pool  {len(pool[0]):,} points over "
                  f"{len(set(collect))} frames, weighted by the posterior")
    else:
        endpoints, conv_idx, members = res
    # the reported fraction is the ENSEMBLE's, not the control run's: origin.json describes the
    # cloud, and the cloud is the ensemble
    strand_frac = (float(np.mean([m["stranded_fraction"] for m in members]))
                   if land is not None else None)

    # ---- the loud edge guard (Phase 3.1) ----------------------------------------------
    # Runs BEFORE anything is written. A cloud whose particles reached the wall must not be
    # able to leave this script as a bundle -- that is the whole point of the guard. A real
    # field has a box; the analytic and constant fields do not, so there is nothing to check.
    box = getattr(field, "bbox", None)
    if box is not None:
        checked = np.vstack([history[-1], endpoints])
        margin = assert_inside_field_box(checked, box, margin_km=10.0,
                                         label="control + ensemble endpoints")
        print(f"              edge guard  closest particle sits {margin:.1f} km inside the "
              f"field box (limit 10 km)")

    # ---- Phase 5.3: which input is the answer resting on? -----------------------------
    ws = wind_share_of_drift(field, history, times)
    wind_share = None
    if ws is not None:
        wind_share, c_mag, w_mag = ws
        print(f"              drift mix  current {c_mag:.3f} m/s + 0.03xwind {w_mag:.3f} m/s "
              f"= wind is {100 * wind_share:.0f}% of the drift")
        if wind_share >= 0.5:
            print(f"              !! WIND-DOMINATED CASE  the origin direction is set by ERA5 "
                  f"and the 0.03 rule, NOT by HYCOM.")
            print(f"              Check it against a WIND reanalysis. A current atlas will "
                  f"disagree and that disagreement is not an error.")
            print(f"              (Ensemble already spans U(0.025, 0.035); direction moves "
                  f"<=5 deg across that range, so this is a provenance note, not a wider cloud.)")

    out_dir = Path(a.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_frames, out_dt = subsample_for_output(np.asarray(positions), a.timestep_minutes,
                                              a.output_timestep_minutes)
    write_particles(out_dir / "particles.json", t0, out_frames.tolist(), out_dt)
    clon, clat, r50, r90, method, abstain = write_origin(
        out_dir / "origin.json", endpoints, conv_idx, members,
        t0, a.timestep_minutes, a.steps, a.runs, stranded_fraction=strand_frac,
        wind_share=wind_share, pool=pool, age_block=age_block)

    # The endpoint pool, kept so plot_heatmap.py can draw the cloud without rerunning 50 runs.
    np.savez_compressed(out_dir / f"ensemble_{a.case}.npz",
                        endpoints=endpoints,
                        control_final=history[-1],
                        seed=np.asarray(seed, dtype=np.float64),
                        conv_idx=conv_idx,
                        wind_coeff=np.array([m["wind_coeff"] for m in members]),
                        current_scale=np.array([m["current_scale"] for m in members]))

    # The permanent plausibility guard, on every real run, not just in tests.py.
    med_km = assert_displacement_plausible(history[0], history[-1], hours=span_h)
    dist = displacement_km(history[0], history[-1])
    ws = np.array([m["wind_coeff"] for m in members])
    cs = np.array([m["current_scale"] for m in members])

    print(f"[drift:{tag}]  wrote {out_dir / 'particles.json'}")
    print(f"              wrote {out_dir / 'origin.json'}")
    print(f"              field  {field}")
    print(f"              seeded {a.particles} from {feat['properties']['id']} "
          f"({feat['properties']['shape_class']}), rewound {span_h:.2f} h "
          f"in {a.steps} steps of {a.timestep_minutes} min")
    print(f"              t0 {iso(t0)} -> {iso(times[-1])}")
    print(f"              control displacement  median {med_km:.1f} km   "
          f"min {float(dist.min()):.1f}   max {float(dist.max()):.1f}")
    print(f"              ensemble {a.runs} runs x {a.particles} = {len(endpoints):,} endpoints"
          f"   wind_coeff {ws.min():.4f}-{ws.max():.4f}   current x{cs.min():.2f}-{cs.max():.2f}")
    print(f"              origin ({clon:.4f}, {clat:.4f})  "
          f"r50={r50:.1f} km  r90={r90:.1f} km  abstain={abstain}")
    print(f"              time_window method={method}")
    if strand_frac is not None:
        ctl = float(np.mean(stranded_ctl))
        print(f"              stranded  {strand_frac * 100:.2f}% of ensemble endpoints "
              f"({ctl * 100:.2f}% of the control run) reached land and were held")
        if strand_frac > 0.10:
            print(f"              !! {strand_frac * 100:.0f}% stranded is high. Either the slick "
                  f"originated ashore or the rewind runs past a coastline -- look at the "
                  f"heatmap before believing the origin.")


if __name__ == "__main__":
    main()
