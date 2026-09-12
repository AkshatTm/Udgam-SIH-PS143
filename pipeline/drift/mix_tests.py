"""Suite 11 -- the drift mix diagnostic (Phase 5.3).

Exists because of `case-gulf-alaska-2023`. Its origin rewinds WEST where the brief predicted
EAST, and nothing in the pipeline was wrong: the Alaska Current is absent from that field and a
persistent easterly wind supplies 81% of the drift. The failure mode being pinned here is not a
physics bug -- it is that the output gave a reviewer no way to distinguish "wind-dominated case"
from "someone flipped a sign", and those two have opposite remedies.

So these tests assert the diagnostic reports the right thing in the three regimes that matter,
and -- 11d, the one that actually earns its keep -- that a REAL sign error still moves the
answer, so the diagnostic cannot be used to explain one away.
"""
import math
from datetime import datetime, timedelta, timezone

import numpy as np

import run as drift_run
import step

T0 = datetime(2017, 1, 29, 0, 14, tzinfo=timezone.utc)


class MixField:
    """Uniform current and wind, each independently settable. No box: this is a lab field."""

    bbox = [79.0, 12.0, 82.0, 15.0]   # a real fetched field has a box; LabField drops it

    def __init__(self, cu=0.0, cv=0.0, wu=0.0, wv=0.0):
        self.c = (float(cu), float(cv))
        self.w = (float(wu), float(wv))

    def get_uv(self, lons, lats, when):
        n = np.shape(lons)
        return np.full(n, self.c[0]), np.full(n, self.c[1])

    def get_wind(self, lons, lats, when):
        n = np.shape(lons)
        return np.full(n, self.w[0]), np.full(n, self.w[1])


class LabField(MixField):
    """A synthetic field: same interface, but no bbox -- so it is not a fetched ocean.

    This mirrors ConstantField/AnalyticField, which DO implement get_wind (returning their
    configured constant, (0, 0) by default) but carry no box. `hasattr(field, "get_wind")` is
    therefore not a usable test for "was there real wind data", which is why the diagnostic
    keys off bbox -- the idiom run.py already uses for "this is a real field".
    """

    bbox = None


def _history(field, seed, steps=97, dt_min=15):
    hist, times, _ = step.integrate_stranding(
        seed, T0, field, steps, dt_min, direction="backward", is_land=None)
    return hist, times


def run(check):
    ok = True
    seed = np.array([[80.40, 13.25], [80.41, 13.26], [80.39, 13.24]])

    # ---- 11a  a current-dominated case reports a small share -------------------------
    # Jacksonville's regime: 1.7 m/s current against a 1.7 m/s wind, so 0.03 x wind is ~3%.
    f = MixField(cu=1.688, cv=0.0, wu=1.74, wv=0.0)
    hist, times = _history(f, seed)
    share, c, w = drift_run.wind_share_of_drift(f, hist, times)
    expect = 0.03 * 1.74 / (1.688 + 0.03 * 1.74)
    ok &= check("11a current-dominated field reports a ~3% wind share",
                abs(share - expect) < 1e-6 and share < 0.05,
                f"current {c:.3f} m/s vs 0.03xwind {w:.3f} m/s gives share {share:.4f} "
                f"(exact {expect:.4f}) — this is the Jacksonville regime, where a current "
                f"atlas IS the right reference")

    # ---- 11b  Alaska's regime crosses the flag threshold ------------------------------
    # The measured field: 0.041 m/s of current under a 5.73 m/s wind.
    f = MixField(cu=0.0, cv=0.041, wu=5.73, wv=0.0)
    hist, times = _history(f, seed)
    share, c, w = drift_run.wind_share_of_drift(f, hist, times)
    expect = 0.03 * 5.73 / (0.041 + 0.03 * 5.73)
    ok &= check("11b Alaska's measured field reports ~81% and trips the >=50% flag",
                abs(share - expect) < 1e-6 and share >= 0.50 and 0.79 < share < 0.82,
                f"current {c:.3f} m/s vs 0.03xwind {w:.3f} m/s gives share {share:.4f}. "
                f"Above 0.50 run.py prints the wind-dominated warning, which is the whole "
                f"point: the origin is an ERA5 result, not a HYCOM one")

    # ---- 11c  a synthetic field is omitted, never reported as a number ----------------
    # A lab field with a real wind constant would happily produce a share. It must not: the
    # number would be true about a field that is not an ocean. Both lab cases return None.
    lab_windy = LabField(cu=0.0, cv=0.041, wu=5.73, wv=0.0)   # would have read 0.81
    lab_calm = LabField(cu=0.3, cv=0.0, wu=0.0, wv=0.0)       # would have read 0.00
    hw, tw = _history(lab_windy, seed)
    hc, tc = _history(lab_calm, seed)
    got_w = drift_run.wind_share_of_drift(lab_windy, hw, tw)
    got_c = drift_run.wind_share_of_drift(lab_calm, hc, tc)
    ok &= check("11c a synthetic field returns None, never a number",
                got_w is None and got_c is None,
                f"windy lab field -> {got_w!r} (would have read 0.81), calm lab field -> "
                f"{got_c!r} (would have read 0.00). Neither is a fetched ocean, so neither "
                f"gets a wind_share in origin.json. CONTRACTS.md 6.5: absence hides a UI row, "
                f"a plausible-looking number misinforms one")

    # ---- 11d  the diagnostic cannot excuse a real sign error --------------------------
    # THE TEST THAT MATTERS. If 'wind-dominated' could absorb a flipped sign, it would be worse
    # than no diagnostic at all. Flip the wind's sign in Alaska's regime: the share is IDENTICAL
    # (it is built from magnitudes) while the origin swings ~180 deg. So a high share never
    # explains a reversed answer -- it only says which field to check it against.
    base = MixField(cu=0.0, cv=0.041, wu=5.73, wv=0.0)
    flip = MixField(cu=0.0, cv=0.041, wu=-5.73, wv=0.0)
    hb, tb = _history(base, seed)
    hf, tf = _history(flip, seed)
    sb = drift_run.wind_share_of_drift(base, hb, tb)[0]
    sf = drift_run.wind_share_of_drift(flip, hf, tf)[0]

    def bearing(hist):
        start = np.mean(hist[0], axis=0)
        end = np.mean(hist[-1], axis=0)
        dlon = (end[0] - start[0]) * math.cos(math.radians(start[1]))
        return (math.degrees(math.atan2(dlon, end[1] - start[1])) + 360) % 360

    swing = abs((bearing(hb) - bearing(hf) + 540) % 360 - 180)
    # Asserted against the DERIVED swing, not a hand-picked threshold. Flipping the wind mirrors
    # the drift vector about the north axis while the current survives untouched, so the swing is
    # 2*atan2(k*wu, cv) -- and it is deliberately NOT 180 deg: the residual 27 deg IS the 0.041
    # m/s of current still in there. A test that demanded 180 would be asserting the current had
    # vanished.
    expect_swing = 2.0 * math.degrees(math.atan2(0.03 * 5.73, 0.041))
    ok &= check("11d flipping the wind sign leaves the share identical but swings the origin",
                abs(sb - sf) < 1e-12 and abs(swing - expect_swing) < 1.0,
                f"share {sb:.4f} -> {sf:.4f} (unchanged, it is built from magnitudes) while the "
                f"origin bearing swings {swing:.1f} deg against a derived 2*atan2(k*wu, cv) = "
                f"{expect_swing:.1f} deg. Short of 180 by {180 - expect_swing:.0f} deg because "
                f"the current does not flip. So the diagnostic says WHICH field the answer rests "
                f"on and can never wave away a sign error — those stay separately detectable, "
                f"which is the only way this field is safe to ship")

    # ---- 11e  the share is what the ensemble's own coefficient range implies -----------
    # A high share is a provenance note, not a wider cloud: across U(0.025, 0.035) the DIRECTION
    # barely moves even at Alaska's 81%. Assert that here so 8.8's claim is testable.
    cu, cv, wu, wv = 0.0, 0.041, 5.73, 0.0
    bearings = []
    for k in (0.025, 0.030, 0.035):
        du, dv = cu + k * wu, cv + k * wv
        bearings.append((math.degrees(math.atan2(-du, -dv)) + 360) % 360)
    spread = max(abs((b - bearings[1] + 540) % 360 - 180) for b in bearings)
    ok &= check("11e across U(0.025,0.035) Alaska's origin direction moves only a few degrees",
                spread < 6.0,
                f"origin bearing spans {spread:.1f} deg across the ensemble's honest coefficient "
                f"range. The wind term DECIDES this case (dropping it swings ~82 deg) but its "
                f"CALIBRATION does not, so 81% is not a confidence problem")

    return ok
