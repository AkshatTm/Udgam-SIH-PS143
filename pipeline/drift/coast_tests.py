#!/usr/bin/env python3
"""
Stage 2 coastline and stranding tests (suite 8). Owner: Anushka.

Run through the main suite — not standalone:

    python pipeline/drift/tests.py

WHY THIS SUITE EXISTS
    Phase 4 replaces a land mask derived from the velocity field's own validity -- 9 km, and
    partly-land cells inside San Pedro Bay and off Mumbai -- with a real GSHHG shoreline at
    about 1 km, and makes particles that reach it STRAND rather than being silently held at
    zero velocity.

    The old behaviour is the reason this needs testing rather than trusting: a particle held at
    zero velocity is indistinguishable from a particle sitting in genuinely slow water, so a
    beached parcel contributed an ordinary-looking endpoint to the origin cloud. Nothing
    announced it. These assertions are what make the difference visible.

    8c is the one that earns its place: `global_land_mask` takes (lat, lon) and this whole
    project is [lon, lat] (TRAPS #1). The swap happens in exactly one function, and this test
    is what keeps it there.
"""
import numpy as np
from datetime import datetime, timezone

import coastline
from fields import ConstantField
from step import integrate_stranding

T0 = datetime(2017, 1, 29, 0, 14, 0, tzinfo=timezone.utc)

# Centres of the seven case scene boxes. Every one must read as water; a case whose own centre
# is on land would mean the box, the mask or the coordinate order is wrong.
LIBRARY = [
    ("jacksonville",     -79.63480, 30.38400),
    ("farallones",      -123.90630, 37.79945),
    ("huntington",      -118.11000, 33.64250),
    ("gulf-alaska",     -142.71380, 59.55550),
    ("mumbai",            72.17705, 18.50475),
    ("jamnagar",          71.87870, 20.16465),
    ("ennore-lookalike",  80.36500, 13.20000),
]


def run(check):
    """Suite 8. `check` is tests.py's assertion recorder."""
    print("\nTest 8 - coastline and stranding (Phase 4): a real shoreline, and beaching is flagged")
    ok = True

    # --- 8a  the real shoreline is actually loaded --------------------------------------
    ok &= check("8a  a real GSHHG shoreline is available",
                coastline.available(),
                coastline.describe() if coastline.available()
                else f"NO COASTLINE: {coastline.why_unavailable()}")
    if not coastline.available():
        return False          # nothing below means anything without the mask

    # --- 8b  known land is land, known ocean is ocean, and every case centre is wet -----
    chennai = bool(coastline.is_land(80.27, 13.08))          # the city
    atlantic = bool(coastline.is_land(-40.0, 30.0))          # mid-ocean
    wet = {n: not bool(coastline.is_land(lo, la)) for n, lo, la in LIBRARY}
    ok &= check("8b  known land, known ocean, and all seven case centres in water",
                chennai and not atlantic and all(wet.values()),
                f"Chennai city land={chennai} · mid-Atlantic land={atlantic} · "
                f"case centres in water: {sum(wet.values())}/7"
                + ("" if all(wet.values())
                   else f" -- DRY: {[n for n, v in wet.items() if not v]}"))

    # --- 8c  the lat/lon swap, which is the one bug this wrapper can hide ---------------
    # global_land_mask takes (lat, lon); this project is [lon, lat]. Chennai is land; the
    # swapped pair (lon 13.08, lat 80.27) is Arctic ocean and must NOT be land.
    right = bool(coastline.is_land(80.27, 13.08))
    swapped = bool(coastline.is_land(13.08, 80.27))
    ok &= check("8c  the argument order is [lon, lat], converted in exactly one place",
                right and not swapped,
                f"is_land(lon=80.27, lat=13.08) = {right} (Chennai, land) vs "
                f"is_land(lon=13.08, lat=80.27) = {swapped} (Arctic ocean, water). "
                f"If both read the same the swap has leaked")

    # --- 8d  a particle driven ashore strands, stops, and stays stopped -----------------
    # 0.5 m/s due WEST from just off Ennore for 10 h -- 18 km, which is well inland. The
    # coast along 13.25 N sits at about 80.34 E.
    field = ConstantField(current=(-0.5, 0.0), wind=(0.0, 0.0))
    start = np.array([[80.35, 13.25]], dtype=np.float64)
    hist, _, stranded = integrate_stranding(start, T0, field, 41, 15, "forward",
                                            is_land=coastline.is_land)
    final_lon = float(hist[-1, 0, 0])
    distinct = len(np.unique(np.round(hist[:, 0, 0], 5)))
    unforced_lon = 80.35 - (0.5 * 10 * 3600) / (111320 * np.cos(np.radians(13.25)))
    ok &= check("8d  a particle driven ashore strands at its last wet position and stops",
                bool(stranded[0]) and final_lon > 80.30 and distinct <= 4,
                f"pushed west from 80.35: stranded={bool(stranded[0])}, stopped at "
                f"{final_lon:.4f} E after {distinct} distinct positions. Unstranded it would "
                f"have reached {unforced_lon:.4f} E, which is inland -- the old behaviour held "
                f"it there at zero velocity and reported it as an ordinary endpoint")

    # --- 8e  a particle seeded on land is stranded from step zero -----------------------
    inland = np.array([[80.20, 13.25]], dtype=np.float64)     # inland of Chennai
    h2, _, s2 = integrate_stranding(inland, T0, field, 9, 15, "forward",
                                    is_land=coastline.is_land)
    moved_km = float(np.abs(h2[-1, 0, 0] - h2[0, 0, 0]))
    ok &= check("8e  a particle seeded on land is stranded immediately and never moves",
                bool(s2[0]) and moved_km < 1e-9,
                f"seeded at 80.20 E (inland): stranded={bool(s2[0])}, longitude moved "
                f"{moved_km:.2e} deg over 2 h. Seeding on land is a Stage 1 problem, but "
                f"Stage 2 must not quietly drift it out to sea")

    # --- 8f  an open-ocean run strands nobody, so the flag is not just always true ------
    ocean = np.array([[-40.0, 30.0], [-41.0, 30.5], [-39.5, 29.5]], dtype=np.float64)
    _, _, s3 = integrate_stranding(ocean, T0, field, 41, 15, "forward",
                                   is_land=coastline.is_land)
    frac = float(np.mean(s3))
    ok &= check("8f  mid-ocean particles strand nobody (the flag is not always-on)",
                frac == 0.0 and 0.0 <= frac <= 1.0,
                f"three particles in the mid-Atlantic drifted 18 km west: stranded fraction "
                f"{frac:.3f}, which is the 0-1 range the validator requires for "
                f"stranded_fraction")

    return ok
