"""Suite 12 -- age engine v2: the posterior, the shape likelihood, the track estimator.

Known-answer tests again: every fixture is built so the right age is known before the engine
runs. The three combination rules in age_posterior's docstring each get a test that would fail
if the rule were broken the obvious way.
"""
import math

import numpy as np

import age
import age_posterior as AP


def _gauss_ll(centre_h, sd_log=0.3):
    return -0.5 * ((np.log(AP.AGE_GRID_H) - math.log(centre_h)) / sd_log) ** 2


def _track_feature(t_true_h, length_km=20.0, lat=30.0, lon=-79.0, sigma0=15.0, ratio=4.0):
    """A synthetic ship track whose widest end is exactly t_true_h old under Okubo diffusion.

    Width grows linearly in variance from the head (age 0) to the tail (t_true_h). The tail
    width w solves w = ratio * sqrt(sigma0^2 + 2 K(w) t) -- a fixed point, iterated.
    """
    t = t_true_h * 3600.0
    w = 100.0
    for _ in range(100):
        w = ratio * math.sqrt(sigma0 ** 2 + 2.0 * age.okubo_diffusivity_m2s(w) * t)
    w_head = ratio * sigma0
    n = 60
    s = np.linspace(0.0, 1.0, n)
    widths = np.sqrt(w_head ** 2 + (w ** 2 - w_head ** 2) * s)          # variance-linear
    x_km = s * length_km
    half_km = widths / 2000.0
    kx = 1.0 / (111.32 * math.cos(math.radians(lat)))
    ky = 1.0 / 111.32
    top = [[lon + xi * kx, lat + hi * ky] for xi, hi in zip(x_km, half_km)]
    bot = [[lon + xi * kx, lat - hi * ky] for xi, hi in zip(x_km[::-1], half_km[::-1])]
    ring = top + bot + [top[0]]
    return {"type": "Feature", "geometry": {"type": "Polygon", "coordinates": [ring]},
            "properties": {"id": "twin", "area_km2": 1.0, "elongation": 50.0,
                           "discharge_class": "chronic", "centroid": [lon, lat]}}, w


def run(check):
    print("\nTest 12 - age engine v2: posterior, shape likelihood, track width")
    ok = True
    g = AP.AGE_GRID_H

    # 12a -------------------------------------------------------------------------------
    post, used = AP.fuse([("shape", _gauss_ll(8.0), 1.0)])
    ok &= check("12a a posterior is normalised and peaks where its evidence does",
                abs(post.sum() - 1.0) < 1e-9 and 6.0 <= g[int(np.argmax(post))] <= 9.0,
                f"sum {post.sum():.12f}, mode {g[int(np.argmax(post))]:.0f} h for evidence "
                f"centred at 8 h under a log-uniform prior")

    # 12b rule 1: mixing two identical models changes nothing; multiplying would ----------
    ll = _gauss_ll(12.0)
    mixed = AP.mix_logliks([ll, ll])
    p_mix, _ = AP.fuse([("shape", mixed, 1.0)])
    p_one, _ = AP.fuse([("shape", ll, 1.0)])
    p_prod, _ = AP.fuse([("a", ll, 1.0), ("b", ll, 1.0)])
    w_one = np.subtract(*AP.hpd(p_one)[1::-1])
    w_prod = np.subtract(*AP.hpd(p_prod)[1::-1])
    ok &= check("12b two models of ONE observable are mixed, not multiplied (rule 1)",
                np.allclose(p_mix, p_one, atol=1e-12) and w_prod < 0.85 * w_one,
                f"mixture == single model exactly; the product would have narrowed the 80% "
                f"band from {w_one:.1f} h to {w_prod:.1f} h on no new evidence")

    # 12c rule 3: nothing contributing is not an answer ----------------------------------
    p_none, used_none = AP.fuse([("shape", None, 1.0), ("track", _gauss_ll(5.0), 0.0)])
    s_none = AP.summarise(p_none, used_none)
    ok &= check("12c no contributing estimator -> 'none', never the prior (rule 3)",
                p_none is None and s_none["status"] == "none",
                f"post {p_none}, status {s_none['status']!r}")

    # 12d rule 2: hypotheses average as posteriors, and a missing one drops out -----------
    pa, _ = AP.fuse([("x", _gauss_ll(3.0), 1.0)])
    pb, _ = AP.fuse([("y", _gauss_ll(40.0), 1.0)])
    avg = AP.average_posteriors([pa, pb])
    solo = AP.average_posteriors([pa, None])
    lo, hi, multi = AP.hpd(avg)
    ok &= check("12d two hypotheses average as posteriors; the band spans both and says so",
                np.allclose(solo, pa) and lo < 4.0 and hi > 30.0 and multi,
                f"hpd80 [{lo:.1f}, {hi:.1f}] h, multimodal={multi}; a None hypothesis leaves "
                f"the other unchanged")

    # 12e the HPD holds its mass ----------------------------------------------------------
    lo, hi, _ = AP.hpd(p_one)
    inside = p_one[(g >= lo) & (g <= hi)].sum()
    ok &= check("12e the 80% HPD set holds at least 80% and not much more",
                0.80 <= inside <= 0.90, f"mass inside [{lo:.1f}, {hi:.1f}] h = {inside:.3f}")

    # 12f a flat likelihood is refused on information gain ------------------------------
    p_flat, u_flat = AP.fuse([("shape", np.zeros_like(g), 1.0)])
    s_flat = AP.summarise(p_flat, u_flat)
    ok &= check("12f evidence that does not move the prior is refused",
                s_flat["status"] == "none" and s_flat["info_gain_nats"] < 1e-9,
                f"gain {s_flat['info_gain_nats']} nats -> {s_flat['status']}")

    # 12g KDE likelihood and censoring --------------------------------------------------
    rng = np.random.default_rng(1)
    samples = np.exp(rng.normal(math.log(10.0), 0.2, 200))
    l_kde = AP.loglik_from_samples(samples)
    l_cen = AP.loglik_from_samples(samples, hi_censored=200, hi_bound=60.0)
    ok &= check("12g sample likelihood peaks at the samples; censored members are not dropped",
                8.0 <= g[int(np.argmax(l_kde))] <= 12.0 and l_cen[-1] > l_kde[-1] + 1.0,
                f"peak {g[int(np.argmax(l_kde))]:.0f} h; the 60-72 h tail rises by "
                f"{l_cen[-1] - l_kde[-1]:.1f} log units once 'older than 60 h' members count")

    # 12h the shape likelihood recovers a known age --------------------------------------
    cands = [1, 2, 4, 8, 12, 16, 24, 36, 48, 72]
    members = 12
    L = np.array([[0.6 * (1 + 0.05 * m) * math.sqrt(t) for t in cands] for m in range(members)])
    W = L / 4.0
    Bm = np.array([[10.0 * math.log(t) for t in cands] for _ in range(members)])
    t_true = 16.0
    obs_L = 0.6 * 1.25 * math.sqrt(t_true)
    ll_s = age.shape_loglik(cands, L, W, Bm, obs_L, obs_L / 4.0, 10.0 * math.log(t_true))
    p_s, _ = AP.fuse([("shape", ll_s, 1.0)])
    lo, hi, _ = AP.hpd(p_s)
    ok &= check("12h shape likelihood (length, width, bearing) brackets a known 16 h",
                lo <= t_true <= hi, f"80% HPD [{lo:.1f}, {hi:.1f}] h, median "
                f"{AP.quantile(p_s, 0.5):.1f} h")
    far = age.shape_loglik(cands, L, W, Bm, 500.0, 100.0, 0.0)
    ok &= check("12i a slick far outside anything the model produces is refused, not "
                "pinned to the grid edge", far is None, f"shape_loglik -> {far}")

    # 12j width-along-track recovers a known age ----------------------------------------
    hits = []
    for t_true in (3.0, 12.0):
        feat, w_tail = _track_feature(t_true)
        band, d = age.track_age(feat, "chronic", n_mc=3000)
        p_t, _ = AP.fuse([("track", np.asarray(d["loglik"]), 1.0)])
        lo, hi, _ = AP.hpd(p_t)
        hits.append((t_true, lo, hi, d["width_tail_m"], round(w_tail, 1)))
    ok &= check("12j width-along-track: the widest end dates a synthetic ship track",
                all(lo <= t <= hi for t, lo, hi, _, _ in hits),
                "; ".join(f"true {t:g} h -> HPD [{lo:.1f}, {hi:.1f}] h (tail width measured "
                          f"{wm} m vs built {wb} m)" for t, lo, hi, wm, wb in hits))
    blob = {"type": "Feature", "geometry": {"type": "Polygon", "coordinates": [[
        [0, 0], [0.02, 0], [0.02, 0.02], [0, 0.02], [0, 0]]]},
        "properties": {"discharge_class": "unknown"}}
    b_band, bd = age.track_age(blob, "unknown")
    ok &= check("12k a square patch is not read as a track",
                b_band is None and bd.get("loglik") is None and bool(bd.get("skipped")),
                f"refused: {bd.get('skipped', '')}")

    # 12m-12p the age drives the origin ------------------------------------------------
    import ensemble as ens
    from datetime import datetime, timedelta, timezone
    from fields import ConstantField
    T0 = datetime(2024, 7, 30, 23, 21, tzinfo=timezone.utc)
    seed = np.column_stack([np.full(200, -79.6), np.linspace(30.30, 30.32, 200)])
    field = ConstantField(current=(0.5, 0.0), wind=(0.0, 0.0))
    steps = 4 * 24 + 1                                    # 24 h at 15 min
    rng1, rng2 = np.random.default_rng(5), np.random.default_rng(5)
    e_plain = ens.run_ensemble(seed, T0, field, steps, 15, n_runs=6, rng=rng1)
    e_coll = ens.run_ensemble(seed, T0, field, steps, 15, n_runs=6, rng=rng2,
                              collect_steps=[4 * h for h in range(1, 25)],
                              collect_particles=50)
    ok &= check("12m collecting frames leaves the endpoints bit-identical",
                len(e_coll) == 4 and np.array_equal(e_plain[0], e_coll[0])
                and len(e_coll[3]) == 24 and e_coll[3][4].shape == (300, 2),
                f"{len(e_coll[3])} frames of {e_coll[3][4].shape[0]} points; endpoints equal")

    grid24 = np.arange(1.0, 25.0)
    young = np.where(grid24 <= 3, 1.0, 0.0)
    old = np.where(grid24 >= 20, 1.0, 0.0)
    py, wy = ens.age_weighted_pool(e_coll[3], grid24, young / young.sum(), 15)
    po, wo = ens.age_weighted_pool(e_coll[3], grid24, old / old.sum(), 15)
    (cy, _, _), (co, _, _) = ens.radii_km(py, weights=wy), ens.radii_km(po, weights=wo)
    # 0.5 m/s east, rewound: a young slick's origin sits ~1-3 h west of it, an old one ~20-24 h
    dx_y = (seed[:, 0].mean() - cy[0]) * 111.32 * math.cos(math.radians(30.31))
    dx_o = (seed[:, 0].mean() - co[0]) * 111.32 * math.cos(math.radians(30.31))
    ok &= check("12n the age posterior moves the origin: a young slick's origin is near, an "
                "old one's far",
                3.0 < dx_y < 6.5 and 35.0 < dx_o < 44.0 and abs(wy.sum() - 1) < 1e-9,
                f"young (1-3 h) origin {dx_y:.1f} km upstream, old (20-24 h) {dx_o:.1f} km "
                f"upstream; at 0.5 m/s the true spans are 1.8-5.4 and 36-43 km")

    spread = np.full(24, 1.0 / 24)
    pa, wa = ens.age_weighted_pool(e_coll[3], grid24, spread, 15)
    _, r50w, r90w = ens.radii_km(pa, weights=wa)
    _, _, r90y = ens.radii_km(py, weights=wy)
    ok &= check("12o an uncertain age honestly widens the cloud; a sharp one keeps it tight",
                r90w > 3 * r90y, f"r90 {r90y:.1f} km for a 1-3 h posterior vs {r90w:.1f} km "
                f"when every hour to 24 h is equally likely")

    s, e, m = ens.time_window([], [], [], T0, 15, steps, age_band=(4.5, 12.5))
    s0, e0, m0 = ens.time_window([], [], [], T0, 15, steps)
    ok &= check("12p an age band becomes the window, method 'age'; no band leaves today's "
                "behaviour untouched",
                m == "age" and (T0 - s) == timedelta(hours=12.5)
                and (T0 - e) == timedelta(hours=4.5) and m0 == "bounded",
                f"window {s:%H:%M}-{e:%H:%M} method {m}; without a band -> {m0}")

    # 12l PIT ---------------------------------------------------------------------------
    pits = [AP.pit(p_one, t) for t in (1.0, 12.0, 72.0)]
    ok &= check("12l PIT of a truth is a probability and increases with the truth",
                0.0 <= pits[0] < pits[1] < pits[2] <= 1.0 + 1e-9,
                f"PIT at 1, 12, 72 h = {[round(p, 3) for p in pits]}")
    return ok
