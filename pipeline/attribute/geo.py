#!/usr/bin/env python3
"""
Stage 3, geometry and grid sampling. Owner: Jaiveer.

Every distance, bearing and grid lookup in the scorer comes from here, once. This is
where silent errors live: a wrong distance does not raise, it just ranks the wrong
ship, and it fails differently at different latitudes so a bug that is invisible at
Galveston is material off Alaska.

    from geo import haversine_km, bearing_deg, OriginGrid

    grid = OriginGrid.load("cases/<id>/origin.json")
    grid.sample(lon, lat)        # 0.0 - 1.0, and 0.0 outside the grid

Two rules worth stating out loud:

  1. **Haversine, never Euclidean.** `hypot(dlon, dlat) * 111.32` is fine over 5 km at
     29 N and wrong enough to matter over 50 km — and its error grows with latitude,
     so it would be nearly right on the Gulf cases and visibly wrong on Alaska at
     59.5 N, which is exactly the sort of bug that survives testing and then moves a
     suspect two places on stage.

  2. **`origin.json` grid row 0 is NORTH.** An upside-down grid validates cleanly,
     scores cleanly, and points at the wrong water. Anushka's test 5d exists for this
     and so does ours (frozen convention 5).

Stdlib only — no new dependencies.
"""
import json
import math
from pathlib import Path

EARTH_RADIUS_KM = 6371.0088          # IUGG mean radius
KM_PER_DEG_LAT = 111.32              # what the rest of the project quotes


def haversine_km(lon1, lat1, lon2, lat2):
    """Great-circle distance in km between two [lon, lat] points, WGS84 degrees."""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = p2 - p1
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * EARTH_RADIUS_KM * math.asin(min(1.0, math.sqrt(a)))


def bearing_deg(lon1, lat1, lon2, lat2):
    """Initial bearing from point 1 to point 2, degrees clockwise from north, 0-360.

    Same convention as AIS course over ground, so it can be compared with `cog`
    directly (frozen convention 3).
    """
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dl = math.radians(lon2 - lon1)
    y = math.sin(dl) * math.cos(p2)
    x = math.cos(p1) * math.sin(p2) - math.sin(p1) * math.cos(p2) * math.cos(dl)
    return math.degrees(math.atan2(y, x)) % 360.0


def angular_difference_deg(a, b):
    """Smallest absolute angle between two bearings, 0-180.

    Wrapping matters: 355 deg and 5 deg are 10 degrees apart, not 350. Getting this
    wrong makes the trajectory component reject vessels heading almost due north.
    """
    return abs((a - b + 180.0) % 360.0 - 180.0)


def local_xy_km(lon, lat, lon0, lat0):
    """Project to local metres-as-km about (lon0, lat0). For short-range vector work
    only — parity and point-to-segment — never for reported distances, which use
    haversine."""
    k = math.cos(math.radians(lat0))
    return ((lon - lon0) * KM_PER_DEG_LAT * k, (lat - lat0) * KM_PER_DEG_LAT)


def point_to_segment_km(plon, plat, alon, alat, blon, blat):
    """Distance in km from point P to the segment AB, and how far along AB the
    closest point falls (0 at A, 1 at B). Used by closest-approach between reports
    and, in Phase 2, by parity and head-proximity."""
    px, py = local_xy_km(plon, plat, alon, alat)
    bx, by = local_xy_km(blon, blat, alon, alat)
    seg2 = bx * bx + by * by
    if seg2 <= 0.0:
        return haversine_km(plon, plat, alon, alat), 0.0
    t = max(0.0, min(1.0, (px * bx + py * by) / seg2))
    return math.hypot(px - t * bx, py - t * by), t


class OriginGrid:
    """The probability field from `origin.json`, sampled at a position.

    Decision D8: score the grid, not the r50 circle. Anushka measured the real cloud
    at 4.38:1 aspect with 44.7% of its high-probability mass outside r50, so circle
    membership names vessels sitting in near-empty water inside the circle and
    excludes vessels sitting in the bright streak just outside it.

    The grid is normalised to peak 1.0, so a sample **is** the proximity score — no
    further scaling.
    """

    __slots__ = ("west", "south", "east", "north", "rows", "cols", "values",
                 "centroid", "radius_50_km", "radius_90_km", "time_window",
                 "time_window_method", "abstain", "raw")

    def __init__(self, doc):
        b = doc["bounds"]
        self.west, self.south = float(b["west"]), float(b["south"])
        self.east, self.north = float(b["east"]), float(b["north"])
        self.rows, self.cols = int(doc["shape"][0]), int(doc["shape"][1])
        self.values = doc["values"]
        if len(self.values) != self.rows * self.cols:
            raise SystemExit(
                f"origin.json: shape {doc['shape']} implies {self.rows * self.cols} "
                f"values but the file has {len(self.values)}")
        if self.west >= self.east or self.south >= self.north:
            raise SystemExit("origin.json/bounds: need west < east and south < north "
                             "(this is the grid's own rectangle, not bounds.json)")
        self.centroid = [float(doc["centroid"][0]), float(doc["centroid"][1])]
        self.radius_50_km = float(doc["radius_50_km"])
        self.radius_90_km = float(doc["radius_90_km"])
        self.time_window = list(doc["time_window"])
        self.time_window_method = doc.get("time_window_method")
        self.abstain = bool(doc.get("abstain", False))
        self.raw = doc

    @classmethod
    def load(cls, path):
        return cls(json.loads(Path(path).read_text(encoding="utf-8")))

    def contains(self, lon, lat):
        return self.west <= lon <= self.east and self.south <= lat <= self.north

    def rowcol(self, lon, lat):
        """Fractional (row, col) for a position. **Row 0 is the NORTH edge** — latitude
        decreases as the row index rises (frozen convention 5)."""
        row = (self.north - lat) / (self.north - self.south) * (self.rows - 1)
        col = (lon - self.west) / (self.east - self.west) * (self.cols - 1)
        return row, col

    def sample(self, lon, lat):
        """Probability at a position, 0.0-1.0. Nearest cell, no interpolation.

        Outside the grid returns **0.0, not None**: a vessel that never entered the
        reconstructed origin has a measured proximity of zero, which is a real
        statement about it. Not-applicable is a different thing and belongs to
        components that cannot be evaluated at all.

        Nearest-cell rather than bilinear on purpose. The cells are of order a
        kilometre and the field behind them is a 50-member ensemble; smoothing
        between two cells would imply a precision the ensemble does not have.
        """
        if not self.contains(lon, lat):
            return 0.0
        row, col = self.rowcol(lon, lat)
        r = min(self.rows - 1, max(0, int(round(row))))
        c = min(self.cols - 1, max(0, int(round(col))))
        return float(self.values[r * self.cols + c])

    def peak_lonlat(self):
        """Position of the highest-probability cell. This is the point 'nearest the
        origin' means for a streak — the centroid of a 30 km streak is not where the
        oil most likely entered the water."""
        i = max(range(len(self.values)), key=self.values.__getitem__)
        r, c = divmod(i, self.cols)
        lat = self.north - (r / (self.rows - 1)) * (self.north - self.south)
        lon = self.west + (c / (self.cols - 1)) * (self.east - self.west)
        return lon, lat

    def __repr__(self):
        return (f"OriginGrid({self.rows}x{self.cols} "
                f"lon {self.west:.3f}..{self.east:.3f} lat {self.south:.3f}..{self.north:.3f} "
                f"r90={self.radius_90_km} abstain={self.abstain})")
