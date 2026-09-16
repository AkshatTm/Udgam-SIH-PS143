"""Stage 2 age engine v2 -- the posterior. Pure maths, no file I/O, no field access.

    Plan: ~/.claude/plans/stateless-bouncing-cerf.md (Akshat, 16 Sept 2026)

WHY THIS EXISTS
    age.py's C4 combined estimator bands by intersection when they overlap and union when they
    do not (`combine_bands`). That rule has no notion of HOW MUCH an estimator supports each
    age, so it cannot be calibrated: there is no number whose coverage can be measured. This
    module replaces it with a posterior over one shared age grid,

        log p(t) = log prior(t) + sum_i  w_i * log L_i(t)

    where each estimator contributes a log-likelihood curve and w_i <= 1 tempers it. The
    weights are fitted on synthetic twins (age_twins.py) so that the 80 % interval covers the
    truth about 80 % of the time -- which is the one accuracy statement a single SAR image
    can honestly support.

THREE RULES THAT ARE EASY TO GET WRONG, AND ARE TESTED (age_tests.py, suite 6, 6dd..6kk)
    1  Two MODELS of the SAME observable are MIXED, never multiplied (`mix_logliks`). Our RK2
       and OpenDrift's OpenOil both predict the slick's shape; multiplying their likelihoods
       would count one observation twice and halve the band for no reason.
    2  Two HYPOTHESES about what the slick IS (a patch released at a point, or a track laid by
       a moving ship) are averaged as POSTERIORS (`average_posteriors`), not as likelihoods --
       their likelihoods are densities of different observables and are not comparable.
    3  An estimator that refuses contributes NOTHING, not a flat zero-information term with a
       weight -- and if nothing contributes, the answer is "none", never the prior dressed up
       as a measurement.
"""
import math

import numpy as np

# The shared grid. 1 h resolution to the 72 h rewind horizon (check_gee.REWIND_HOURS).
AGE_GRID_H = np.arange(1.0, 73.0, 1.0)

# Prior support. Log-uniform: a slick is equally likely to be 1-2 h old as 10-20 h old. That is
# the scale-free choice when nothing else is known, and it is deliberately NOT uniform in hours,
# which would put 2/3 of the prior mass past 24 h -- i.e. assert that most slicks we see are old,
# which nobody has measured. SAR-visible ship discharges are also short-lived (hours to a day or
# two), which the log-uniform shape respects without inventing a lifetime.
PRIOR_LO_H = 0.5
PRIOR_HI_H = 72.0

HPD_MASS = 0.80

# Information gain (KL(posterior || prior), nats) below which the evidence is too weak to call a
# measurement. 0.10 nats is roughly the gain from narrowing a flat prior by 10 %. Recalibrated by
# age_twins.py; this is the conservative starting value.
MIN_INFO_GAIN_NATS = 0.10

# Floor on any likelihood, relative to its own maximum. Keeps one estimator that puts literally
# zero mass somewhere from vetoing a region outright on the strength of a finite ensemble -- a
# 20-member Monte Carlo cannot establish that an age is impossible, only that it is unlikely.
LIK_FLOOR_REL = 1e-4


def log_uniform_prior(grid=AGE_GRID_H, lo=PRIOR_LO_H, hi=PRIOR_HI_H):
    """log p(t) for a log-uniform prior on [lo, hi], evaluated on `grid`, normalised on the grid.

    Grid points outside [lo, hi] get -inf."""
    g = np.asarray(grid, dtype=np.float64)
    lp = np.where((g >= lo) & (g <= hi), -np.log(np.maximum(g, 1e-12)), -np.inf)
    return lp - _logsumexp(lp)


def _logsumexp(a):
    a = np.asarray(a, dtype=np.float64)
    m = np.max(a)
    if not np.isfinite(m):
        return m
    return float(m + np.log(np.sum(np.exp(a - m))))


def floor_loglik(ll, rel=LIK_FLOOR_REL):
    """Raise every value to at least max + log(rel). See LIK_FLOOR_REL."""
    ll = np.asarray(ll, dtype=np.float64)
    top = np.max(ll[np.isfinite(ll)]) if np.any(np.isfinite(ll)) else 0.0
    return np.maximum(np.where(np.isfinite(ll), ll, -np.inf), top + math.log(rel))


def interp_loglik(candidate_hours, lik_values, grid=AGE_GRID_H):
    """Put a likelihood evaluated at a few candidate ages onto the shared grid.

    Interpolated LINEARLY IN LOG-AGE and in LIKELIHOOD (not log-likelihood): a candidate grid
    of 1, 2, 4, 8 ... is log-spaced in spirit, and interpolating the likelihood itself keeps a
    zero between two positive candidates from becoming a spike. Beyond the candidate range the
    end values are held, which is the honest statement: the model was not run there.
    """
    h = np.asarray(candidate_hours, dtype=np.float64)
    v = np.asarray(lik_values, dtype=np.float64)
    order = np.argsort(h)
    h, v = h[order], np.maximum(v[order], 0.0)
    g = np.asarray(grid, dtype=np.float64)
    out = np.interp(np.log(g), np.log(h), v)
    with np.errstate(divide="ignore"):
        return floor_loglik(np.log(out))


def loglik_from_samples(samples, grid=AGE_GRID_H, bw_log=None, lo_censored=0, hi_censored=0,
                        lo_bound=None, hi_bound=None):
    """Log-likelihood curve from Monte Carlo age samples, by a gaussian KDE in log-age.

    `lo_censored`/`hi_censored` count members that only told us "younger than lo_bound" /
    "older than hi_bound" (their curve never crossed the target). They are NOT dropped -- that
    would bias the band towards whichever side the fitting members happened to fall -- they
    contribute a uniform-in-log slab below/above the bound, weighted by their count.
    """
    g = np.asarray(grid, dtype=np.float64)
    lg = np.log(g)
    s = np.asarray([x for x in samples if x is not None and x > 0], dtype=np.float64)
    n_total = s.size + int(lo_censored) + int(hi_censored)
    if n_total == 0:
        return None
    dens = np.zeros_like(g)
    if s.size:
        ls = np.log(s)
        if bw_log is None:
            # Silverman in log space, floored so a tight cluster still has width: 20 members is
            # not enough to claim better than ~15 % precision on anything.
            sd = float(np.std(ls)) if s.size > 1 else 0.0
            bw_log = max(1.06 * sd * s.size ** (-0.2), 0.15)
        z = (lg[:, None] - ls[None, :]) / bw_log
        dens += np.exp(-0.5 * z * z).sum(axis=1) / (bw_log * math.sqrt(2 * math.pi))
    width = np.gradient(lg)
    if lo_censored and lo_bound is not None:
        slab = (g <= lo_bound).astype(float)
        if slab.sum():
            dens += lo_censored * slab / float((slab * width).sum())
    if hi_censored and hi_bound is not None:
        slab = (g >= hi_bound).astype(float)
        if slab.sum():
            dens += hi_censored * slab / float((slab * width).sum())
    with np.errstate(divide="ignore"):
        return floor_loglik(np.log(dens / n_total))


def mix_logliks(lls, weights=None):
    """log( sum_i a_i L_i ) for two or more MODELS of the SAME observable. Rule 1.

    `None` entries are dropped (a model that did not run is not a model that said nothing), and
    the remaining weights are renormalised. Each L_i is first scaled to unit maximum so a model
    whose likelihood is numerically larger only because its observation error is narrower does
    not silently outvote the other one -- the mixture is over MODELS, equal weight by default,
    because there is no ground truth for origin or age that could justify anything else.
    """
    live = [(np.asarray(l, dtype=np.float64), (1.0 if weights is None else float(weights[i])))
            for i, l in enumerate(lls) if l is not None]
    if not live:
        return None
    tot = sum(a for _, a in live)
    terms = [l - np.max(l) + math.log(a / tot) for l, a in live]
    stacked = np.vstack(terms)
    m = np.max(stacked, axis=0)
    return m + np.log(np.sum(np.exp(stacked - m), axis=0))


def fuse(terms, prior=None, grid=AGE_GRID_H):
    """Posterior from (name, loglik_or_None, weight) terms. Returns (post, used) or (None, used).

    `used` lists the names that actually contributed. No contributing term -> None: the prior
    is not an answer (rule 3).
    """
    lp = log_uniform_prior(grid) if prior is None else np.asarray(prior, dtype=np.float64)
    used = []
    for name, ll, w in terms:
        if ll is None or w <= 0:
            continue
        lp = lp + float(w) * np.asarray(ll, dtype=np.float64)
        used.append(name)
    if not used:
        return None, used
    lp = lp - _logsumexp(lp)
    post = np.exp(lp)
    return post / post.sum(), used


def average_posteriors(posts, weights=None):
    """Bayesian model average over HYPOTHESES (rule 2). `None` posts are dropped."""
    live = [(np.asarray(p, dtype=np.float64), (1.0 if weights is None else float(weights[i])))
            for i, p in enumerate(posts) if p is not None]
    if not live:
        return None
    tot = sum(a for _, a in live)
    out = sum(p * (a / tot) for p, a in live)
    return out / out.sum()


def hpd(post, grid=AGE_GRID_H, mass=HPD_MASS):
    """Highest-density set holding `mass`. Returns (lo, hi, multimodal).

    The band is the span of the set -- conservative when the set is not contiguous, and the
    `multimodal` flag says so rather than hiding a second peak inside a wide band. Band edges
    are the grid cell edges (+/- half a cell), so a posterior that sits in one cell still has a
    non-zero width.
    """
    p = np.asarray(post, dtype=np.float64)
    g = np.asarray(grid, dtype=np.float64)
    order = np.argsort(p)[::-1]
    cum = np.cumsum(p[order])
    k = int(np.searchsorted(cum, mass)) + 1
    chosen = np.sort(order[:k])
    half = 0.5 * (g[1] - g[0]) if g.size > 1 else 0.5
    lo = max(float(g[chosen[0]]) - half, 0.0)
    # capped at the last grid age: the rewind (and the fetched field) ends there, so a band
    # edge past it would be a claim about hours nothing was modelled for
    hi = min(float(g[chosen[-1]]) + half, float(g[-1]))
    multimodal = bool(np.any(np.diff(chosen) > 1))
    return lo, hi, multimodal


def quantile(post, q, grid=AGE_GRID_H):
    """q-quantile of the posterior, interpolated on the grid CDF."""
    p = np.asarray(post, dtype=np.float64)
    cdf = np.cumsum(p)
    return float(np.interp(q, cdf, np.asarray(grid, dtype=np.float64)))


def info_gain_nats(post, prior=None, grid=AGE_GRID_H):
    """KL(post || prior) in nats. How much the evidence actually moved us."""
    lp = log_uniform_prior(grid) if prior is None else np.asarray(prior, dtype=np.float64)
    pr = np.exp(lp)
    pr = pr / pr.sum()
    p = np.asarray(post, dtype=np.float64)
    m = p > 0
    return float(np.sum(p[m] * (np.log(p[m]) - np.log(np.maximum(pr[m], 1e-300)))))


def pit(post, truth_h, grid=AGE_GRID_H):
    """Probability integral transform of a known truth under the posterior. For calibration:
    across many twins a calibrated engine gives PIT ~ Uniform(0, 1)."""
    p = np.asarray(post, dtype=np.float64)
    return float(np.interp(truth_h, np.asarray(grid, dtype=np.float64), np.cumsum(p)))


def summarise(post, used, grid=AGE_GRID_H, prior=None, min_gain=MIN_INFO_GAIN_NATS):
    """Everything downstream needs from a posterior, or a refusal. Returns a dict.

    Keys: status ("ok" | "none"), reason, hpd80 [lo, hi], median, mode, multimodal,
    info_gain_nats, used, prob (rounded, on `grid`), hours_grid.
    """
    if post is None:
        return {"status": "none", "reason": "no estimator contributed", "used": list(used)}
    gain = info_gain_nats(post, prior, grid)
    lo, hi, multi = hpd(post, grid)
    out = {
        "status": "ok",
        "hours_grid": [float(x) for x in grid],
        # 5 dp, not 4: 72 values each rounded by <= 5e-6 keep the sum within 4e-4 of 1, inside
        # the validator's 1e-3 tolerance. At 4 dp the worst case (3.6e-3) is not.
        "prob": [round(float(x), 5) for x in post],
        "hpd80": [round(lo, 1), round(hi, 1)],
        "median": round(quantile(post, 0.5, grid), 1),
        "mode": float(np.asarray(grid)[int(np.argmax(post))]),
        "multimodal": multi,
        "info_gain_nats": round(gain, 3),
        "used": list(used),
    }
    if gain < min_gain:
        out["status"] = "none"
        out["reason"] = (f"information gain {gain:.3f} nats is below {min_gain} -- the evidence "
                         f"barely moved the prior, so there is no measured age to report")
    return out
