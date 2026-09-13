#!/usr/bin/env python3
"""
Real coastline for Stage 2. Owner: Anushka.   (docs/team/anushka-stage2-drift.md Phase 4, decision D7)

WHY THIS EXISTS
    Until now the land mask was derived from the VELOCITY FIELD'S OWN VALIDITY: a HYCOM cell
    whose corners are all NaN is land, anything else is water. That is a 9 km mask, and it is
    wrong in exactly the places the case library cares about. Huntington Beach sits inside San
    Pedro Bay and Mumbai sits on a complex, heavily-indented coast; a 9 km cell there is partly
    land and partly water, and the field cannot tell you which part a particle is in.

    Worse, the old behaviour for a fully-land cell was to HOLD the particle at zero velocity.
    A held particle is indistinguishable from a particle sitting in genuinely slow water, so a
    beached slick contributed a perfectly ordinary-looking endpoint to the origin cloud. That
    is the failure mode this whole component exists to refuse.

    So: a real shoreline, and particles that reach it are STRANDED AND FLAGGED.

WHY `global-land-mask` AND NOT CARTOPY
    Both wrap GSHHG, the shoreline OpenDrift uses. `global-land-mask` is 2.6 MB of numpy and
    nothing else; cartopy drags in GEOS and PROJ. Master §5 rule 8 bans new dependencies once
    the pipeline is assembling, and D7 approves the coastline upgrade -- so it has to be the
    small one. Resolution is about 1 km, which is nine times finer than the current field and
    is the point.

WHAT STRANDING MEANS HERE
    Irreversible. Once a particle touches land it stops and stays stopped, and it is counted.
    That is a modelling choice and it is the honest one for a backward run: the model cannot
    say where a beached parcel came from, so it must not invent a velocity that carries it on.
    `stranded_fraction` then goes into origin.json, because a high fraction is itself a finding
    -- it means the slick may have originated ashore, or the rewind is running past a coastline.
"""
import numpy as np

_MASK = None
_ERROR = None


def available():
    """True when a real shoreline is loaded. False means every guard falls back to open water."""
    _load()
    return _MASK is not None


def why_unavailable():
    _load()
    return _ERROR


def _load():
    global _MASK, _ERROR
    if _MASK is not None or _ERROR is not None:
        return
    try:
        from global_land_mask import globe
        _MASK = globe
    except Exception as exc:                      # noqa: BLE001 - any import failure is the same
        _ERROR = (f"global-land-mask is not installed ({exc.__class__.__name__}: {exc}). "
                  f"Phase 4 needs it:  pip install global-land-mask==1.0.0\n"
                  f"  Without it the land mask falls back to the velocity field's own "
                  f"validity, which is 9 km and wrong inside San Pedro Bay and off Mumbai.")


def is_land(lons, lats):
    """Boolean array: True where the position is on land, per GSHHG at about 1 km.

    Note the argument order. `global_land_mask` takes (lat, lon); everything in this project is
    [lon, lat] (TRAPS #1). The swap happens HERE, once, and nowhere else -- the same discipline
    as wrap_lon living in exactly one place.
    """
    _load()
    lon = np.asarray(lons, dtype=np.float64)
    lat = np.asarray(lats, dtype=np.float64)
    if _MASK is None:
        return np.zeros(lon.shape, dtype=bool)
    return np.asarray(_MASK.is_land(lat, lon), dtype=bool)


def land_fraction(positions):
    """Fraction of an [n, 2] lon/lat array that is on land. Convenience for reporting."""
    p = np.asarray(positions, dtype=np.float64)
    if p.size == 0:
        return 0.0
    return float(np.mean(is_land(p[:, 0], p[:, 1])))


def describe():
    """One line for the run banner, so which mask was used is never a guess."""
    if available():
        return "GSHHG via global-land-mask (~1 km), stranding ON"
    return "NO real coastline - velocity-field mask only (9 km), stranding OFF"
