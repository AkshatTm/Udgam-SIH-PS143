#!/usr/bin/env python3
"""
Stage 2 age-estimation known-answer tests (suite 6). Owner: Anushka.

Run through the main suite -- these are not meant to be run standalone:

    python pipeline/drift/tests.py

Same principle as tests 1-5: every assertion has an answer known in advance from a field whose
shear we chose, so a wrong-but-running estimator has nowhere to hide. Three of these exist
specifically to pin down the two places where the implementation had to DEPART from the brief,
so the departure is testable rather than a comment nobody reads:

  6c  a 2D incompressible flow PRESERVES cloud area   -> which is why C3.1 matches on the
                                                          major axis and not on area_km2
  6d  the exact patch-aspect inversion recovers a known age in a known shear
  6e  the brief's C3.3 error is a factor that CLIMBS with elongation, not a constant
"""
import math
from datetime import datetime, timezone

import numpy as np

from age import (SEED_SIGMA_M, _curve_with_wind, combine_bands, deformation_rate_s, elongation_age,
                 fay_age,
                 fay_predicted_area_km2, fay_radius_km, invert_curve, observed_major_axis_km,
                 polygon_major_axis_km, slick_major_axis_km,
                 pca_extent, seed_cloud, shear_dispersion_age, shear_extent_curve,
                 weathering_flag)
import step
from step import integrate, rk2_step

T0 = datetime(2017, 1, 29, 0, 14, 0, tzinfo=timezone.utc)
ENNORE = [80.35, 13.25]
KM_DEG = 111.32   # km per degree of latitude; the fixtures below are built at the equator

# Strong but physically plausible coastal shear. At 5e-5 1/s the shear timescale is 5.6 h, so
# a 6 h old patch is visibly stretched and the aspect ratio is well clear of measurement noise.
TEST_SHEAR_S = 5.0e-5
M_PER_DEG_LAT = 111320.0


class LinearShearField:
    """u = S * (northward offset from lat0), v = 0, no wind. Pure incompressible simple shear.

    Chosen because everything about it is known in closed form: the deformation rate is exactly
    S, a material patch's area is exactly preserved, and an initially isotropic patch's aspect
    ratio after time t is exactly lambda_max of F F^T with F = [[1, S t], [0, 1]].
    """

    def __init__(self, lat0, shear_s=TEST_SHEAR_S):
        self.lat0 = float(lat0)
        self.shear_s = float(shear_s)

    def get_uv(self, lons, lats, when):
        lats = np.asarray(lats, dtype=np.float64)
        dy_m = (lats - self.lat0) * M_PER_DEG_LAT
        return self.shear_s * dy_m, np.zeros_like(dy_m)

    def get_wind(self, lons, lats, when):
        z = np.zeros_like(np.asarray(lats, dtype=np.float64))
        return z, z.copy()

    def __repr__(self):
        return f"LinearShearField(S={self.shear_s:.1e} 1/s)"


def exact_aspect(gamma):
    """Aspect ratio of an initially isotropic patch after simple shear strain gamma = S*t.

    Singular values of F = [[1, gamma], [0, 1]]: aspect = lambda_max of F F^T, and since
    det = 1, lambda_min = 1 / lambda_max.
    """
    return 1.0 + gamma ** 2 / 2.0 + gamma * math.sqrt(1.0 + gamma ** 2 / 4.0)


def run(check):
    """Suite 6. `check` is tests.py's assertion recorder."""
    print("\nTest 6 - age estimation (Part C): shear dispersion, Fay, elongation, combine")
    ok = True

    field = LinearShearField(ENNORE[1])
    rng = np.random.default_rng(143)

    # --- 6a  the shear rate we built is the shear rate we measure ------------------------
    s_measured = deformation_rate_s(field, ENNORE[0], ENNORE[1], T0)
    ok &= check("6a  deformation rate recovers a known shear",
                abs(s_measured - TEST_SHEAR_S) / TEST_SHEAR_S < 0.01,
                f"built S = {TEST_SHEAR_S:.3e} 1/s, measured {s_measured:.3e} 1/s "
                f"({abs(s_measured - TEST_SHEAR_S) / TEST_SHEAR_S * 100:.2f}% error); "
                f"shear timescale {1.0 / s_measured / 3600.0:.1f} h")

    # --- 6b  filament length grows monotonically with age -------------------------------
    candidates = [2.0, 6.0, 12.0, 18.0, 24.0, 30.0, 36.0]
    areas, majors, minors = shear_extent_curve(
        field, ENNORE[0], ENNORE[1], T0, candidates, n_particles=2000,
        rng=np.random.default_rng(7))
    lengths = 4.0 * majors
    grows = bool(np.all(np.diff(lengths) > 0))
    ok &= check("6b  modelled filament LENGTH grows monotonically with candidate age",
                grows,
                f"major axis {lengths[0]:.3f} -> {lengths[-1]:.3f} km across "
                f"{candidates[0]:g}-{candidates[-1]:g} h, strictly increasing at every step")

    # --- 6c  ...but AREA does not. This is why C3.1 cannot match on area. ---------------
    area_ratio = float(areas[-1] / areas[0])
    ok &= check("6c  cloud AREA is preserved (so area carries no age signal)",
                abs(area_ratio - 1.0) < 0.15,
                f"area {areas[0]:.4f} -> {areas[-1]:.4f} km2 over 34 h = x{area_ratio:.3f}. "
                f"An incompressible flow has det F = 1: it stretches and thins, it does not "
                f"inflate. Matching Soumirya's area_km2 against this would be fitting noise -- "
                f"hence C3.1 matches the major axis instead (departure from the brief)")

    # --- 6d  the elongation estimator recovers a known age ------------------------------
    t_true_h = 6.0
    n_steps = int(round(t_true_h * 60.0 / 15.0)) + 1
    start = seed_cloud(ENNORE[0], ENNORE[1], 4000, rng=rng)
    history, _ = integrate(start, T0, field, n_steps, 15, direction="forward")
    sd1, sd2, _ = pca_extent(history[-1])
    aspect = sd1 / sd2
    aspect_theory = exact_aspect(TEST_SHEAR_S * t_true_h * 3600.0)

    band, diag = elongation_age(aspect, s_measured, "acute")
    contains = band is not None and band[0] <= t_true_h <= band[1]
    ok &= check("6d  elongation inversion recovers a known age in a known shear",
                contains,
                f"cloud sheared for {t_true_h:g} h reached aspect {aspect:.3f} "
                f"(closed form {aspect_theory:.3f}); inverted to "
                f"{diag.get('central_hours', float('nan')):.2f} h, band "
                f"[{band[0]:.2f}, {band[1]:.2f}] h contains the true {t_true_h:g} h"
                if band else f"no band returned: {diag.get('skipped')}")

    # --- 6e  the brief's formula is wrong by a factor that CLIMBS with elongation -------
    # Ratified by Akshat 13 Sept 2026, and his correction to how it gets quoted: 3.24x is the
    # ratio at a = 8.2 and NOWHERE ELSE. sqrt(a^2-1)/sqrt(a+1/a-2) grows without bound, so no
    # age computed under the brief's form can be fixed by dividing -- each one is recomputed.
    # Asserted at four elongations precisely so this test's own output cannot be misquoted as
    # a single conversion factor. Jacksonville's ribbon is aspect ~168, where it is ~13x.
    expected = {2.0: 2.45, 8.2: 3.24, 20.0: 4.70, 50.0: 7.21}
    got, worst = {}, 0.0
    for a_val, want in expected.items():
        _, d = elongation_age(a_val, 1.0e-5, "acute")
        r = d["brief_formula_hours"] / d["central_hours"]
        got[a_val] = r
        worst = max(worst, abs(r - want) / want)
    climbs = all(got[k1] < got[k2] for k1, k2 in zip(sorted(got), sorted(got)[1:]))
    ok &= check("6e  the brief's C3.3 error is a factor that CLIMBS, not a 3.2x constant",
                worst < 0.01 and climbs,
                "ratio sqrt(a^2-1)/sqrt(a+1/a-2) by elongation: "
                + " · ".join(f"a={k:g} -> x{v:.2f}" for k, v in sorted(got.items()))
                + f" (worst deviation from the ruling's table {worst * 100:.2f}%). "
                  f"Strictly increasing, so an age under the brief's form CANNOT be corrected "
                  f"by dividing by 3.2 -- it has to be recomputed. At Jacksonville's aspect "
                  f"~168 the factor is ~13x")

    # --- 6f  the acute gate actually gates ----------------------------------------------
    chronic_band, chronic_diag = elongation_age(8.2, 1.0e-5, "chronic")
    ok &= check("6f  a chronic discharge is refused, not estimated",
                chronic_band is None and "chronic" in chronic_diag.get("skipped", ""),
                f"discharge_class='chronic' -> None. {chronic_diag.get('skipped')}")

    # --- 6g  Fay's exponent -------------------------------------------------------------
    r1 = fay_radius_km(1.0, 1000.0, 1.3, 900.0)
    r16 = fay_radius_km(16.0, 1000.0, 1.3, 900.0)
    ok &= check("6g  Fay radius grows as t^(1/4) (so area as t^(1/2))",
                abs(r16 / r1 - 2.0) < 1e-6,
                f"r(16 h)/r(1 h) = {r16 / r1:.6f}, expected 16^(1/4) = 2 exactly "
                f"({r1:.4f} -> {r16:.4f} km)")

    # --- 6h  Fay refuses to derive its own volume from the observed area ---------------
    fband, fdiag = fay_age(12.4, volume_m3=None)
    ok &= check("6h  Fay declines without an independent volume (the brief's V=A*h is circular)",
                fband is None and "circular" in fdiag.get("skipped", ""),
                f"area 12.4 km2, no volume -> None. {fdiag.get('skipped')}")

    # --- 6i  ...and at SAR scale it is a REGIME TEST, not an age estimator ------------
    huntington_m3 = 588 * 0.159          # 588 barrels, NTSB MIR-24-01
    fband, fdiag = fay_age(12.4, volume_m3=huntington_m3)
    reach_24h = fay_predicted_area_km2(24.0, huntington_m3, 1.5, 850.0)
    ok &= check("6i  a SAR-scale slick is shear-dominated, so Fay reports no age",
                fband is None and fdiag.get("regime") == "shear_dominated",
                f"{huntington_m3:.1f} m3 spreads to only {reach_24h:.3f} km2 in 24 h and "
                f"{fdiag['max_predicted_area_km2_at_ceiling']:.3f} km2 at the 72 h ceiling, "
                f"against an observed 12.4 km2 -> regime={fdiag.get('regime')}, no band. "
                f"This is independent evidence that shear, not spreading, set the area")

    # --- 6j  ...but when the slick IS in Fay's reach, the inversion round-trips --------
    vol, t_true = 1000.0, 12.0
    r_true_km = fay_radius_km(t_true, vol, 1.3, 900.0)
    area_true = math.pi * r_true_km ** 2
    fband, fdiag = fay_age(area_true, volume_m3=vol)
    ok &= check("6j  inside the gravity-viscous regime, Fay recovers a known age",
                fband is not None and fband[0] <= t_true <= fband[1]
                and fdiag.get("regime") == "gravity_viscous",
                f"{vol:g} m3 spread for {t_true:g} h -> r {r_true_km:.3f} km, "
                f"area {area_true:.3f} km2; inverted to "
                f"[{fband[0]:.2f}, {fband[1]:.2f}] h across {len(fdiag['corners'])} "
                f"k/density corners, containing the true {t_true:g} h"
                if fband else f"no band: {fdiag.get('skipped')}")

    # --- 6k/6l/6m  the combine rules ---------------------------------------------------
    band, method = combine_bands({"shear": (7.0, 18.0), "fay": (9.0, 15.0),
                                  "elongation": None})
    ok &= check("6k  overlapping bands -> intersection, method='combined'",
                band == (9.0, 15.0) and method == "combined",
                f"shear [7,18] & fay [9,15] -> {band} method={method}")

    band, method = combine_bands({"shear": (2.0, 5.0), "fay": (20.0, 30.0)})
    ok &= check("6l  disagreeing bands -> UNION, method='disagreement'",
                band == (2.0, 30.0) and method == "disagreement",
                f"shear [2,5] vs fay [20,30] -> {band} method={method}. A widened honest "
                f"band beats a narrow invented one")

    band, method = combine_bands({"shear": None, "fay": None, "elongation": None})
    ok &= check("6m  nothing fires -> method='none', caller falls back to the bracket",
                band is None and method == "none",
                f"all three null -> {band} method={method}")

    # --- 6n/6o/6p  the weathering flag refuses rather than guesses ---------------------
    flag, wdiag = weathering_flag(1.5)
    ok &= check("6n  wind outside 3-10 m/s -> 'unknown', never a freshness call",
                flag == "unknown",
                f"1.5 m/s -> {flag}: {wdiag['reason']}")

    flag, wdiag = weathering_flag(6.0)
    ok &= check("6o  no centre-vs-edge observable -> 'unknown', not a proxy guess",
                flag == "unknown" and "contract" in wdiag["reason"],
                f"6 m/s but the contract has no centre-vs-edge field -> {flag}. "
                f"contrast_db and edge_gradient are NOT substitutes (C2's confounding). "
                f"Needs contrast_centre_db + contrast_edge_db from Stage 1")

    flag, wdiag = weathering_flag(6.0, contrast_centre_db=-12.0, contrast_edge_db=-8.0)
    ok &= check("6p  a real centre-vs-edge gradient does classify",
                flag == "fresh",
                f"centre -12 dB vs edge -8 dB = {wdiag['gradient_db']:.1f} dB gradient "
                f"-> {flag}")

    # --- 6r  C3.1 carries the SAME acute gate as C3.3 ----------------------------------
    # On a chronic discharge the major axis is the vessel's track, not shear stretching a
    # patch: case-jacksonville-2024 is a 31.17 km ribbon of 4.55 km2, aspect ~170, width
    # ~190 m. No ocean does that in 36 h; a ship at transit speed does. So an estimator that
    # matches the major axis must refuse there, or it returns a confident wrong number.
    gated, gdiag = shear_dispersion_age(field, ENNORE[0], ENNORE[1], T0, 31.17, [2.0, 4.0],
                                        n_members=2, discharge_class="chronic")
    open_gate, odiag = shear_dispersion_age(field, ENNORE[0], ENNORE[1], T0, 31.17, [2.0, 4.0],
                                            n_members=2, discharge_class="acute")
    # The refusal must also say WHOSE problem it is, and WHAT IT IS.
    #
    # THIS ASSERTION CHANGED ON 13 SEPT, AND THE REASON MATTERS. It used to require the word
    # "MISSING INPUT" in the 'unknown' message, because A5 had found discharge_class unset on
    # every case and absent from every detections.geojson. Soumirya's detections then landed for all
    # seven live cases and discharge_class IS emitted on every feature -- so the old wording was
    # asserting something factually false, and a test that pins a false claim is worse than no
    # test. The claim it replaces is stronger, not weaker: classify_discharge() reads SHAPE
    # ALONE (elongation < 3 -> acute, >= 5 and straight -> chronic, else unknown), so 0 of the
    # 13 oil detections in the library are acute and none ever can be. A5's conclusion survives
    # structurally; only its stated cause was wrong.
    unset, udiag = shear_dispersion_age(field, ENNORE[0], ENNORE[1], T0, 31.17, [2.0, 4.0],
                                        n_members=2, discharge_class="unknown")
    ok &= check("6r  C3.1 refuses a chronic slick, runs on an acute one, and names the cause",
                gated is None and "'chronic'" in gdiag.get("skipped", "")
                and "nothing is missing" in gdiag.get("skipped", "")
                and unset is None
                and "NOT a missing field" in udiag.get("skipped", "")
                and "SHAPE ALONE" in udiag.get("skipped", "")
                and "0 of 13" in udiag.get("skipped", "")
                and "members" in odiag,
                f"chronic -> None, and the reason says the gate is correct and nothing is "
                f"missing. unknown -> None, and the reason says it is NOT a missing field -- "
                f"discharge_class IS emitted, it is computed from SHAPE ALONE, and 0 of 13 oil "
                f"detections can ever be acute. "
                f"acute -> ran {odiag.get('n_members')} members, {odiag.get('n_fitted')} fits "
                f"against a 31.17 km axis. Those are three different situations and the "
                f"diagnostics now distinguish them")

    # --- 6s  the major axis is MEASURED off the polygon, not inferred from an ellipse --
    # A1 made C3.1 match the observed major axis. Deriving that axis from area x elongation
    # assumes the slick is an ellipse, and a real one is not: Jacksonville's det-01 has
    # solidity 0.223. So this pins the measurement against a synthetic shape whose answer is
    # known exactly, then against the failure mode that motivated the change.
    #
    # A 10 km x 1 km rectangle at the equator: the principal axis is 10 km by construction.
    rect = [[0.0, 0.0], [10.0 / KM_DEG, 0.0], [10.0 / KM_DEG, 1.0 / KM_DEG],
            [0.0, 1.0 / KM_DEG], [0.0, 0.0]]
    length, ldiag = polygon_major_axis_km(rect)
    ok &= check("6s  polygon PCA recovers a known major axis and minor width",
                length is not None and abs(length - 10.0) < 0.02
                and abs(ldiag["bbox_width_km"] - 1.0) < 0.02,
                f"a 10.00 x 1.00 km rectangle measures {length:.4f} km along its principal "
                f"axis and {ldiag['bbox_width_km']:.4f} km across -- peak-to-peak, because the "
                f"quantity C3.1 matches is a physical end-to-end length, not a sigma")

    # --- 6t  and it disagrees with the ellipse form exactly where the shape is not one --
    # A 10 x 1 km SINUOUS filament: same 10 km span, but folded so it encloses far less area.
    # The ellipse form reads the small area as a short slick; the measurement does not.
    import math as _m
    n = 61
    wig = [[(10.0 * i / (n - 1)) / KM_DEG,
            (0.35 * _m.sin(6.0 * _m.pi * i / (n - 1))) / KM_DEG] for i in range(n)]
    wig = wig + [[p[0], p[1] + 0.06 / KM_DEG] for p in reversed(wig)]
    wlen, _ = polygon_major_axis_km(wig)
    feat = {"geometry": {"type": "Polygon", "coordinates": [wig]},
            "properties": {"area_km2": 0.6, "elongation": 4.0}}
    chosen, cdiag = slick_major_axis_km(feat)
    derived = observed_major_axis_km(0.6, 4.0)
    ok &= check("6t  a sinuous filament is measured, and the ellipse form underreads it",
                abs(chosen - wlen) < 1e-9 and cdiag["route"].startswith("measured")
                and chosen > 2.0 * derived
                and cdiag["filament_aspect"] > float(feat["properties"]["elongation"]),
                f"measured {chosen:.2f} km vs ellipse-derived {derived:.2f} km "
                f"(x{cdiag['measured_over_derived']}); mean width "
                f"{cdiag['mean_width_m']:.0f} m gives a filament aspect of "
                f"{cdiag['filament_aspect']} against a reported elongation of 4.0. "
                f"Jacksonville's det-01 is this shape: 17.38 km measured, 6.72 km derived")

    # --- 6u  with no polygon it still answers, and SAYS it fell back ---------------------
    bare = {"properties": {"area_km2": 12.4, "elongation": 8.2}}
    fb, fbdiag = slick_major_axis_km(bare)
    ok &= check("6u  no polygon -> ellipse fallback, and the route is recorded",
                fb is not None and abs(fb - observed_major_axis_km(12.4, 8.2)) < 1e-9
                and "ellipse" in fbdiag["route"],
                f"no geometry -> {fb:.2f} km via '{fbdiag['route']}'. The fallback is allowed, "
                f"but a band read off a derived axis is a different claim from one read off a "
                f"measured axis, so the route travels with the result")

    # --- 6q  an age outside the modelled range is reported as absent, not clamped ------
    out_of_range = invert_curve([2.0, 6.0, 12.0], [1.0, 2.0, 3.0], 99.0)
    length = observed_major_axis_km(12.4, 8.2)
    ok &= check("6q  a target outside the modelled range returns None, never a clamped edge",
                out_of_range is None and abs(length - 11.38) < 0.05,
                f"target 99 against a 1-3 curve -> {out_of_range}; and area 12.4 km2 with "
                f"elongation 8.2 -> major axis {length:.2f} km")

    # === Phase 1, 16 Sept 2026: horizontal diffusion ===================================
    # These four exist because diffusion is the one term in this stage that is STOCHASTIC and
    # OFF BY DEFAULT. Both properties are load-bearing and both are easy to break silently.

    shear_field = LinearShearField(ENNORE[1])

    # --- 6v  K=0 reproduces the deterministic curve EXACTLY (the regression pin) --------
    base = _curve_with_wind(shear_field, ENNORE[0], ENNORE[1], T0, [6.0, 12.0], 15, 400,
                            wind_coeff=0.03, seed=143)
    again = _curve_with_wind(shear_field, ENNORE[0], ENNORE[1], T0, [6.0, 12.0], 15, 400,
                             wind_coeff=0.03, seed=143, diffusivity=0.0)
    ok &= check("6v  diffusivity=0 is bit-identical to the deterministic curve",
                np.array_equal(base[1], again[1]),
                f"major axes {base[1].round(4).tolist()} both ways. The default must never "
                f"perturb the advection-only physics every other test asserts exactly")

    # --- 6w  K>0 grows the cloud by the analytic TAYLOR-DISPERSION amount --------------
    #
    # THE OBVIOUS EXPECTATION IS WRONG HERE, and getting it wrong first is what makes this test
    # worth having. Adding a random walk of sigma = sqrt(2KT) in quadrature with the advective
    # axis predicts 2.14 km; the model produces 3.67 km. That is not a bug, it is SHEAR-DIFFUSION
    # COUPLING: a particle that diffuses across-stream lands in water moving at a different
    # speed and is then carried differentially downstream. For simple shear u = S*y the
    # along-stream variance is
    #
    #     sigma_xx^2(t) = sigma_0^2 (1 + S^2 t^2)  +  2 K t  +  (2/3) S^2 K t^3
    #                     \_ pure shear _/            \_ walk _/   \_ Taylor _/
    #
    # and at K = 50, S = 5e-5, t = 12 h the t^3 term alone is 60% of the total variance.
    #
    # That is the whole reason Phase 1 unblocks C3.1. Plain diffusion would add ~2 km to a
    # 0.5 km axis; diffusion THROUGH A SHEARED FIELD adds enough to reach the 2.3-10.1 km slicks
    # the library actually contains. The estimator is measuring the real ocean's dispersion, and
    # this closed form is the only place it can be checked against something known exactly.
    K = 50.0
    T_h = 12.0
    n_p = 2000
    wet = _curve_with_wind(shear_field, ENNORE[0], ENNORE[1], T0, [T_h], 15, n_p,
                           wind_coeff=0.03, seed=143, diffusivity=K)
    dry = _curve_with_wind(shear_field, ENNORE[0], ENNORE[1], T0, [T_h], 15, n_p,
                           wind_coeff=0.03, seed=143, diffusivity=0.0)
    t_s = T_h * 3600.0
    s0 = SEED_SIGMA_M
    var_shear = s0 * s0 * (1.0 + (TEST_SHEAR_S * t_s) ** 2)
    var_walk = 2.0 * K * t_s
    var_taylor = (2.0 / 3.0) * TEST_SHEAR_S ** 2 * K * t_s ** 3
    predicted = math.sqrt(var_shear + var_walk + var_taylor) / 1000.0
    naive = math.hypot(float(dry[1][0]), math.sqrt(var_walk) / 1000.0)
    measured = float(wet[1][0])
    ok &= check("6w  K>0 spreads the cloud by the analytic Taylor-dispersion amount",
                abs(measured - predicted) / predicted < 0.12,
                f"K={K:g} m2/s over {T_h:g} h: major-axis sigma {measured:.3f} km against the "
                f"closed form {predicted:.3f} km. The naive no-coupling guess is {naive:.3f} km "
                f"-- the (2/3)S^2Kt^3 Taylor term is "
                f"{100 * var_taylor / (var_shear + var_walk + var_taylor):.0f}% of the variance. "
                f"Advection alone gives {float(dry[1][0]):.3f} km, which is why C3.1 stalled at "
                f"~1.3 km on real HYCOM and refused on every case")

    # --- 6x  the random walk is SEEDED: same seed, same answer -------------------------
    r1 = _curve_with_wind(shear_field, ENNORE[0], ENNORE[1], T0, [6.0], 15, 300,
                          wind_coeff=0.03, seed=77, diffusivity=40.0)
    r2 = _curve_with_wind(shear_field, ENNORE[0], ENNORE[1], T0, [6.0], 15, 300,
                          wind_coeff=0.03, seed=77, diffusivity=40.0)
    r3 = _curve_with_wind(shear_field, ENNORE[0], ENNORE[1], T0, [6.0], 15, 300,
                          wind_coeff=0.03, seed=78, diffusivity=40.0)
    ok &= check("6x  a seeded diffusive run is reproducible, and a different seed differs",
                np.array_equal(r1[1], r2[1]) and not np.array_equal(r1[1], r3[1]),
                f"seed 77 twice -> {float(r1[1][0]):.5f} km both times; seed 78 -> "
                f"{float(r3[1][0]):.5f} km. A stochastic model nobody can re-run is not a model")

    # --- 6y  K>0 with no rng REFUSES rather than silently seeding itself ---------------
    raised = False
    try:
        rk2_step(np.array([[80.35, 13.25]]), T0, 900.0, shear_field, diffusivity=25.0, rng=None)
    except ValueError as exc:
        raised = "rng" in str(exc)
    ok &= check("6y  diffusivity>0 without an rng raises, never quietly picks a seed",
                raised,
                "an unseeded random walk makes two runs of the same case disagree with nothing "
                "to point at, so rk2_step refuses -- loudly, like every other guard in step.py")

    return ok
