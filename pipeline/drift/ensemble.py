#!/usr/bin/env python3
"""
Stage 2 Phase 3 — the ensemble and the origin cloud. Owner: Anushka.

One backward run gives a trajectory. It does NOT give an answer, because the inputs are not
known exactly: the 3% wind rule is an empirical band, not a constant, and HYCOM on GEE is
DAILY, so a 24 h rewind interpolates between two snapshots and cannot see a sub-daily eddy
(docs/updates/anushka.md, Phase 2 open issue).

So we run it 50 times with the inputs jiggled inside their honest uncertainty, and the SPREAD
of where those runs land is the answer. That spread is the product of this file:

    wind coefficient  ~ U(0.025, 0.035)     the 3% rule is 2.5-3.5%, not exactly 3%
    current field     x N(1, 0.15)          carries the daily-HYCOM ignorance
    seed positions    +/- 300 m gaussian    the slick outline is not a survey boundary

WHAT IS NOT PERTURBED, AND WHY
    Wind direction and the wind field itself. ERA5 is hourly and well constrained over open
    ocean; the uncertainty that matters here is how much of the wind the oil feels (the
    coefficient), not what the wind was doing. Perturbing both would double-count.

MEMORY
    Full history for 50 x 3000 x 97 positions is ~230 MB. We never store it: each ensemble
    member keeps only its final positions and a per-step spread curve. The full history is
    kept for the control run alone, because that is what the animation needs.
"""
from datetime import timedelta

import numpy as np

from step import as_positions, deg_to_m, rk2_step

KM_PER_DEG_LAT = 111.32

# The ensemble's uncertainty budget. Every number here is defensible in December.
WIND_COEFF_LO = 0.025
WIND_COEFF_HI = 0.035
CURRENT_SIGMA = 0.15
SEED_JITTER_KM = 0.3
ABSTAIN_RADIUS_KM = 40.0        # a cloud wider than this refuses attribution
LAST_STRANDED = None            # bool[n] from the most recent run_once (Phase 4)


class PerturbedField:
    """A field with its CURRENT scaled by a constant. Wind passes through untouched.

    Wraps anything exposing get_uv/get_wind, so the ensemble works identically over the
    analytic ocean (tests) and over HYCOM+ERA5 (the real run). step.py never learns that
    the field it is integrating has been perturbed -- same design rule as Phase 2.
    """

    def __init__(self, base, current_scale=1.0):
        self.base = base
        self.current_scale = float(current_scale)

    def get_uv(self, lons, lats, when):
        u, v = self.base.get_uv(lons, lats, when)
        return np.asarray(u) * self.current_scale, np.asarray(v) * self.current_scale

    def get_wind(self, lons, lats, when):
        return self.base.get_wind(lons, lats, when)

    def __repr__(self):
        return f"PerturbedField({self.base!r}, current x{self.current_scale:.3f})"


def spread_km(pos):
    """RMS distance of a particle cloud from its own centroid, in km.

    This is the number whose minimum over time we call 'convergence': rewound particles are
    tightest at the moment they were released, IF the field has enough structure to squeeze
    them. In a smooth field it does not, and the curve stays flat -- which is why the caller
    must check that the dip is real before believing it.
    """
    p = as_positions(pos)
    clon = float(p[:, 0].mean())
    clat = float(p[:, 1].mean())
    dx, dy = deg_to_m(p[:, 0] - clon, p[:, 1] - clat, p[:, 1])
    return float(np.sqrt(np.mean(dx * dx + dy * dy)) / 1000.0)


def jitter_seed(seed_pos, rng, jitter_km=SEED_JITTER_KM):
    """Gaussian re-jitter of the seed, in metres-equivalent degrees at each particle's own
    latitude. Re-drawn per ensemble member: the slick outline is a detector output, not a
    survey boundary, so its exact edge is part of what we are uncertain about."""
    p = as_positions(seed_pos).copy()
    sig_lat = jitter_km / KM_PER_DEG_LAT
    coslat = np.maximum(np.cos(np.radians(p[:, 1])), 1e-6)
    p[:, 0] += rng.normal(0.0, sig_lat / coslat, size=p.shape[0])
    p[:, 1] += rng.normal(0.0, sig_lat, size=p.shape[0])
    return p


def run_once(seed_pos, t0, field, n_steps, timestep_minutes=15, wind_coeff=0.03,
             direction="backward", keep_history=False, is_land=None,
             diffusivity=0.0, rng=None):
    """One member. Returns (final_positions, spread_curve, history_or_None).

    `n_steps` counts STORED POSITIONS: 97 at 15 min is exactly 24.0 h, because the seed state
    is one of them and only 96 intervals separate them. (docs/CONTRACTS.md 5)

    `diffusivity`/`rng` reach rk2_step and DEFAULT TO OFF. The capability is here so the origin
    ensemble can be given a random walk later, but turning it on changes `spread_km` -- and so
    `conv_idx`, the convergence time window, radius_50/90_km and the abstain decision -- all at
    once. It is deliberately left at 0.0 until that can be measured on its own rather than
    tangled with the age-band pooling landing in the same change.
    """
    if n_steps < 1:
        raise ValueError("n_steps must be at least 1")
    sign = -1.0 if direction == "backward" else 1.0
    dt = sign * float(timestep_minutes) * 60.0

    pos = as_positions(seed_pos).copy()
    # Phase 4: stranding, sticky. Kept local so the return signature does not change --
    # the fraction is read back through the module-level LAST_STRANDED below.
    stranded = np.zeros(pos.shape[0], dtype=bool)
    if is_land is not None:
        stranded |= is_land(pos[:, 0], pos[:, 1])
    spread = np.empty(n_steps, dtype=np.float64)
    history = np.empty((n_steps, pos.shape[0], 2)) if keep_history else None
    times = []
    t = t0

    for k in range(n_steps):
        if keep_history:
            history[k] = pos
        times.append(t)
        spread[k] = spread_km(pos)
        if k == n_steps - 1:
            break
        moved = rk2_step(pos, t, dt, field, wind_coeff=wind_coeff,
                         diffusivity=diffusivity, rng=rng)
        if is_land is not None:
            stranded |= is_land(moved[:, 0], moved[:, 1])
            moved[stranded] = pos[stranded]        # hold at the last wet position
        pos = moved
        t = t + timedelta(seconds=dt)

    global LAST_STRANDED
    LAST_STRANDED = stranded
    return pos, spread, history, times


def _stratified_draws(n, rng, current_sigma=None):
    """The 50 members' parameters, drawn by STRATIFICATION rather than independently.

    Fifty independent draws from N(1, 0.15) have a sample mean scattered by 0.021 and a
    sample sd that is itself uncertain, so a 50-member ensemble can end up quietly biased --
    on one seed the mean current came out 3% fast, which shifts the whole origin cloud 3%
    further from the slick. That is a sampling artefact being reported as physics.

    Stratifying fixes it for free: split each distribution into n equal-probability slices
    and take one draw from each. The realised mean and spread then match the distribution we
    claim to be sampling, and 50 members cover the tails instead of clumping in the middle.
    The two parameter lists are shuffled independently so wind and current stay uncorrelated.

    NormalDist comes from the standard library -- no new dependency (CLAUDE.md rule 4).
    """
    from statistics import NormalDist

    u = (np.arange(n) + rng.random(n)) / n           # one uniform per stratum
    winds = WIND_COEFF_LO + u * (WIND_COEFF_HI - WIND_COEFF_LO)

    nd = NormalDist(1.0, CURRENT_SIGMA if current_sigma is None else float(current_sigma))
    u2 = (np.arange(n) + rng.random(n)) / n
    scales = np.array([nd.inv_cdf(float(p)) for p in u2])

    rng.shuffle(winds)
    rng.shuffle(scales)
    return winds, scales


def run_ensemble(seed_pos, t0, base_field, n_steps, timestep_minutes=15, n_runs=50,
                 rng=None, progress=None, is_land=None, current_sigma=None,
                 diffusivity=0.0, collect_steps=None, collect_particles=300):
    """The 50 runs. Returns (endpoints [n_runs*n, 2], conv_idx [n_runs], members).

    `endpoints` is every final position from every member pooled together -- 150,000 points
    for a 50 x 3000 ensemble. That pool IS the origin probability cloud; the histogram in
    origin_grid() is only how we hand it to a frontend.

    AGE ENGINE v2: with `collect_steps` (step indices), a FOURTH value is returned --
    {step: positions [n_runs * collect_particles, 2]} -- the cloud at each of those steps, so the
    origin can be pooled over the age posterior instead of read off the last step. A fixed
    random subset of `collect_particles` per member is kept (the same subset at every step):
    72 frames x 50 members x 3000 particles would be 10.8 M points for a KDE whose bandwidth is
    far wider than the particle spacing. With `collect_steps=None` nothing changes.
    """
    rng = rng if rng is not None else np.random.default_rng(143)
    seed_pos = as_positions(seed_pos)

    winds, scales = _stratified_draws(n_runs, rng, current_sigma=current_sigma)

    endpoints = []
    conv_idx = []
    members = []
    steps = None if collect_steps is None else sorted({int(k) for k in collect_steps
                                                       if 0 <= int(k) < n_steps})
    collected = {} if steps is None else {k: [] for k in steps}
    n_seed = seed_pos.shape[0]
    keep = (None if steps is None else
            np.random.default_rng(777).choice(n_seed, min(collect_particles, n_seed),
                                              replace=False))

    for r in range(n_runs):
        wind_coeff = float(winds[r])
        # A negative scale would reverse the ocean, which is not an uncertainty, it is a
        # different planet. N(1, 0.15) reaches zero at 6.7 sigma, but clip anyway.
        scale = max(float(scales[r]), 0.05)
        field = PerturbedField(base_field, scale)
        start = jitter_seed(seed_pos, rng)

        final, spread, hist, _ = run_once(start, t0, field, n_steps, timestep_minutes,
                                          wind_coeff=wind_coeff, is_land=is_land,
                                          diffusivity=diffusivity,
                                          keep_history=steps is not None,
                                          rng=(np.random.default_rng(4000 + r)
                                               if diffusivity > 0.0 else None))
        if steps is not None:
            for k in steps:
                collected[k].append(hist[k][keep])
            del hist
        stranded_frac = (float(np.mean(LAST_STRANDED))
                         if LAST_STRANDED is not None and is_land is not None else 0.0)
        endpoints.append(final)
        conv_idx.append(int(np.argmin(spread)))
        members.append({"run": r, "wind_coeff": wind_coeff, "current_scale": scale,
                        "stranded_fraction": stranded_frac,
                        "spread_start_km": float(spread[0]),
                        "spread_min_km": float(spread.min()),
                        "spread_end_km": float(spread[-1]),
                        "conv_idx": int(np.argmin(spread))})
        if progress:
            progress(r + 1, n_runs)

    if steps is not None:
        return (np.vstack(endpoints), np.asarray(conv_idx), members,
                {k: np.vstack(v) for k, v in collected.items()})
    return np.vstack(endpoints), np.asarray(conv_idx), members


def age_weighted_pool(collected, posterior_hours, posterior_prob, timestep_minutes,
                      min_prob=1e-4):
    """(points, weights) pooling the collected frames by the age posterior.

    Each grid age t maps to step round(t * 60 / dt). A frame gets the posterior mass of its
    age, spread evenly over its points, so a frame's total weight is its probability whatever
    its particle count. Ages with < `min_prob` mass are dropped (they would add points, not
    information). Weights sum to 1.
    """
    pts, wts = [], []
    for t, p in zip(posterior_hours, posterior_prob):
        if p < min_prob:
            continue
        k = int(round(float(t) * 60.0 / timestep_minutes))
        frame = collected.get(k)
        if frame is None or len(frame) == 0:
            continue
        pts.append(frame)
        wts.append(np.full(len(frame), float(p) / len(frame)))
    if not pts:
        return None, None
    w = np.concatenate(wts)
    return np.vstack(pts), w / w.sum()


def _weighted_percentile(x, w, q):
    order = np.argsort(x)
    cw = np.cumsum(w[order])
    return float(np.interp(q / 100.0 * cw[-1], cw, x[order]))


def radii_km(points, centroid=None, weights=None):
    """(centroid, r50, r90): radii of the circles around the centroid containing 50% and 90%
    of the ensemble endpoints. Percentiles of distance, not standard deviations -- a real
    cloud is not gaussian and we should not quote it as if it were.

    `weights` (v2): percentiles and centroid of the WEIGHTED pool -- the age-posterior pool,
    where a point's weight is the probability of the age it was sampled at."""
    p = as_positions(points)
    w = None if weights is None else np.asarray(weights, dtype=np.float64)
    if centroid is None:
        if w is None:
            clon, clat = float(p[:, 0].mean()), float(p[:, 1].mean())
        else:
            clon = float(np.average(p[:, 0], weights=w))
            clat = float(np.average(p[:, 1], weights=w))
    else:
        clon, clat = float(centroid[0]), float(centroid[1])
    dx, dy = deg_to_m(p[:, 0] - clon, p[:, 1] - clat, p[:, 1])
    d = np.hypot(dx, dy) / 1000.0
    if w is None:
        return (clon, clat), float(np.percentile(d, 50)), float(np.percentile(d, 90))
    return (clon, clat), _weighted_percentile(d, w, 50), _weighted_percentile(d, w, 90)


def _gaussian_blur(grid, sigma):
    """Separable gaussian blur in pure NumPy — deliberately no scipy.

    A 2D gaussian is the product of two 1D gaussians, so blurring the rows then the columns
    gives the identical result at a fraction of the cost. Written out here rather than
    imported so that producing the handoff files needs nothing beyond NumPy: this must run
    on whichever laptop happens to be free on Tuesday night.
    """
    r = max(int(3.0 * sigma), 1)
    x = np.arange(-r, r + 1, dtype=np.float64)
    k = np.exp(-(x * x) / (2.0 * sigma * sigma))
    k /= k.sum()
    out = np.apply_along_axis(lambda row: np.convolve(row, k, mode="same"), 1, grid)
    out = np.apply_along_axis(lambda col: np.convolve(col, k, mode="same"), 0, out)
    return out


def origin_grid(points, rows=120, cols=120, pad_frac=0.05, bandwidth_frac=0.10, weights=None):
    """2D histogram of the ensemble endpoints -> a normalised probability grid.

    Row 0 is NORTH (row-major from the top-left), matching bounds.json's pixel convention so
    the frontend can draw it straight over the scene without flipping anything.

    The raw histogram is NOT the density. Two artefacts sit on top of it:

      - shot noise: 150k points over 14,400 cells averages ~10 counts a cell
      - member banding: with a LINEAR slick every member translates the seed line almost
        rigidly, so 50 members land as 50 near-parallel ridges. Those ridges are an artefact
        of having 50 samples, not 50 distinct places the oil could have come from, and a
        grid that keeps them tells Stage 3 to prefer stripes.

    So the histogram is smoothed into a kernel density estimate. The bandwidth is NOT eyeballed
    to make the picture look nice -- it is tied to the cloud's own scale at
    `bandwidth_frac` x r50 (default a tenth of the 50% radius), which is wide enough to close
    the member spacing and far narrower than any feature we would claim to resolve.

    This is a display choice and it is stated openly: it changes the PICTURE, never the
    numbers -- the radii are measured from the raw endpoints in radii_km(), never from this
    grid, so no reported quantity depends on the bandwidth.
    """
    p = as_positions(points)
    lon, lat = p[:, 0], p[:, 1]

    west, east = float(lon.min()), float(lon.max())
    south, north = float(lat.min()), float(lat.max())
    padx = max((east - west) * pad_frac, 0.01)
    pady = max((north - south) * pad_frac, 0.01)
    west, east = west - padx, east + padx
    south, north = south - pady, north + pady

    # np.histogram2d gives row = x-bin; we want row = lat, descending north-first.
    # `weights` (v2): the age-posterior pool, where each point carries the probability of the
    # age it was sampled at. The box still spans every point -- a low-weight point is still a
    # place the oil could have come from -- only the density changes.
    H, _, _ = np.histogram2d(lat, lon, bins=[rows, cols],
                             range=[[south, north], [west, east]], weights=weights)
    H = H[::-1, :]                        # flip so row 0 = north

    # Bandwidth from the cloud's own scale: a tenth of r50, expressed in grid cells.
    _, r50, _ = radii_km(p, weights=weights)
    cell_km = ((north - south) / rows) * KM_PER_DEG_LAT
    sigma_cells = max(1.0, (bandwidth_frac * r50) / max(cell_km, 1e-9))
    sigma_cells = min(sigma_cells, rows / 8.0)          # never blur away the cloud itself
    H = _gaussian_blur(H, float(sigma_cells))

    peak = float(H.max())
    if peak <= 0:
        raise ValueError("origin grid is entirely zero -- the ensemble produced no endpoints")
    values = np.round(H / peak, 4)

    bounds = {"west": round(west, 5), "south": round(south, 5),
              "east": round(east, 5), "north": round(north, 5)}
    return bounds, values


def time_window(conv_idx, spreads_start, spreads_min, t0, timestep_minutes, n_steps,
                dip_ratio=0.90, age_band=None):
    """When did the oil enter the water?

    AGE ENGINE v2, tried FIRST: `age_band` = (lo_h, hi_h), the age posterior's 80 % HPD. The
    window is then [t0 - hi, t0 - lo] and the method is "age" -- a measurement of THIS slick,
    stronger than "convergence" (a property of the ensemble) and far stronger than "bounded"
    (a property of the rewind length). With age_band=None the behaviour below is unchanged.

    Preferred method: each member's cloud is tightest at some step; take the 10th-90th
    percentile of those times across the ensemble. That is only meaningful if the tightening
    is REAL -- in a smooth field the cloud just translates, the spread curve is flat, and
    argmin picks up numerical noise. Two guards:

      1. the median member must actually tighten to <= dip_ratio of its starting spread
      2. the dip must be interior, not pinned to the first or last step

    If either fails we do NOT dress up noise as a measurement. We ship the bounded window
    [t0-24h, t0-8h] and say so in `time_window_method`, exactly as the cut order allows
    (docs/team/anushka-stage2-drift.md, Phase 3 step 3).

    Returns (start_dt, end_dt, method).
    """
    span_h = (n_steps - 1) * timestep_minutes / 60.0
    if age_band is not None:
        lo_h, hi_h = max(float(age_band[0]), 0.0), min(float(age_band[1]), span_h)
        # a zero-width window is not a window: at least one timestep wide
        hi_h = max(hi_h, lo_h + timestep_minutes / 60.0)
        return (t0 - timedelta(hours=hi_h), t0 - timedelta(hours=lo_h), "age")
    bounded = (t0 - timedelta(hours=span_h), t0 - timedelta(hours=span_h / 3.0), "bounded")

    conv_idx = np.asarray(conv_idx, dtype=float)
    if conv_idx.size == 0:
        return bounded

    ratio = float(np.median(np.asarray(spreads_min) / np.maximum(np.asarray(spreads_start), 1e-9)))
    med = float(np.median(conv_idx))
    if ratio > dip_ratio or med <= 1 or med >= n_steps - 2:
        return bounded

    k_lo = float(np.percentile(conv_idx, 10))
    k_hi = float(np.percentile(conv_idx, 90))
    if k_hi - k_lo < 1.0:                       # a zero-width window is not a window
        k_lo, k_hi = max(k_lo - 1.0, 0.0), min(k_hi + 1.0, float(n_steps - 1))
    if k_hi <= k_lo:
        return bounded

    # Backward run: a LARGER step index is FURTHER in the past, so it is the window's start.
    start = t0 - timedelta(minutes=k_hi * timestep_minutes)
    end = t0 - timedelta(minutes=k_lo * timestep_minutes)
    return start, end, "convergence"
