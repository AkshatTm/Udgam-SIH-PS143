"""
land_mask_geo.py — a REAL coastline land mask for the Ennore / US demo scenes
(anything that has lon/lat bounds, i.e. Akshat's GEE export + bounds.json).

The Zenodo scenes have no reliable land information, so darkspot_v2 infers
land from brightness. For the demo scenes we know where we are on Earth, so
use an actual coastline instead: `global-land-mask` (pip install
global-land-mask) is a ~1 km land/sea raster, offline, no API, no token.
Dilate it a few hundred metres so coastline sidelobes and surf are excluded.

Usage inside detect/run.py:
    from land_mask_geo import land_mask_from_bounds
    land = land_mask_from_bounds(db.shape, bounds, dilate_px=30)
    regions, info = detect_array(db, px_km2, external_land=land)   # see note below

bounds.json convention (Master §4): pixel (0,0) = west, north; linear lon/lat
across the raster:  {"west": 80.20, "east": 80.45, "south": 13.10, "north": 13.35}
"""
import numpy as np
from scipy import ndimage as ndi
from global_land_mask import globe


def land_mask_from_bounds(shape, bounds, dilate_px=30):
    h, w = shape
    lons = np.linspace(bounds["west"], bounds["east"], w)
    lats = np.linspace(bounds["north"], bounds["south"], h)  # row 0 = north
    lon_g, lat_g = np.meshgrid(lons, lats)
    land = globe.is_land(lat_g, lon_g)
    if dilate_px:
        land = ndi.binary_dilation(land, iterations=dilate_px)
    return land


if __name__ == "__main__":
    # Ennore, Chennai coast — sanity check that the coastline lands where expected
    b = {"west": 80.20, "east": 80.45, "south": 13.10, "north": 13.35}
    m = land_mask_from_bounds((512, 512), b, dilate_px=0)
    print(f"land fraction in Ennore box: {m.mean():.1%}  (west column land: {m[:, 0].mean():.0%}, east column land: {m[:, -1].mean():.0%})")
