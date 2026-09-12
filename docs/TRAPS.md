# TRAPS — the bugs that will actually happen
*Read before debugging anything geospatial. Every entry here is a bug that RUNS FINE and produces confident wrong numbers. Syntax errors are easy; these are what cost days.*

---

## The universal first move
Print or plot one concrete thing and ask: **could a physical object behave this way?**
A ship does not move 1,800 km in a day. An ocean current is not 90 m/s. A slick is not 40,000 km². An elongation ratio is never below 1. Contrast for a dark spot is never positive.

Then run `python scripts/validate_case.py cases/<id>` — it catches most of the below by name.

---

## 1. Coordinate order · affects everyone
GeoJSON is `[longitude, latitude]`. Every human instinct says lat-lon. Every mapping library disagrees with a different one.
- **Symptom:** everything renders mirrored, rotated, or in the middle of Africa (lat/lon of Jamnagar swapped ≈ 20°E 71°N — dry land in Algeria).
- **Catch:** the validator explicitly tests "outside bounds but inside when swapped" and names the file.
- **Rule:** MapLibre and deck.gl want `[lon, lat]`. Shapely wants `(x, y)` = `(lon, lat)`. `rasterio` row/col is `(y, x)`. NumPy arrays index `[row, col]` = `[y, x]` = `[lat, lon]`. **The array is the odd one out — convert at the boundary and never carry both conventions in one function.**

## 2. HYCOM on GEE is a scaled integer — divide by 1000 · Anushka
`HYCOM/sea_water_velocity` bands carry catalog **units m/s with scale factor 0.001**, so the
value `getRegion` hands you is millimetres per second. **Divide by 1000, not 100.**
- **Do not trust the "cm/s, divide by 100" advice** that circulates for HYCOM — it describes
  the raw NetCDF distribution, not Earth Engine's ingestion of it. Dividing by 100 leaves
  every current **10x too fast**.
- **Symptom:** median current ~4.8 m/s instead of ~0.48 m/s over the case box; particles
  travel hundreds of km in 24 h.
- **Catch:** test 4 asserts speed < 3 m/s; `fetch_fields.py` prints median/p90/p99/max and
  `GriddedField` refuses to load a field whose p99 exceeds 3 m/s.
- **Verified** 2026-09-07 against the GEE catalog band table, and confirmed by the resulting
  field: median 0.48 m/s, max 1.10 m/s, southward along the Coromandel coast — the January
  East India Coastal Current.

## 3. ERA5 wind is u/v components · Anushka
Bands are `u_component_of_wind_10m` / `v_component_of_wind_10m` — signed eastward/northward m/s, **not** speed and bearing. Wind speed is `hypot(u, v)`. The 3% rule applies to the vector.
- **Symptom:** drift direction is systematically wrong by a rotation.

## 4. Meteorological vs oceanographic direction convention · Anushka
Wind "from" vs current "towards" is a real convention clash in the literature. Because GEE gives you signed u/v components you sidestep it — **do not let generated code convert to bearings and back.** If a function takes `wind_direction_deg`, be suspicious.

## 5. Longitude 0–360 vs −180–180 · Anushka
Some ocean datasets use 0-360. The Indian cases at +72degE are identical in both, so **this bug hides on Mumbai and Jamnagar and appears the moment you cross into the Atlantic or Pacific** — Jacksonville is -79.6, Farallones -123.9, Gulf of Alaska -142.7, which read as 280, 236 and 217 in the other convention.
- **Rule:** normalise everything to −180…180 at the loader boundary, once.

## 6. Naive datetimes · everyone
Python's `datetime.now()` and `fromisoformat("...T00:14:00")` produce timezone-naive objects that silently compare as if UTC — until they don't.
- **Symptom:** off by 5:30 (IST), or a `TypeError` comparing naive and aware.
- **Rule:** always `.replace("Z","+00:00")` when parsing, always `tzinfo=timezone.utc` when constructing. Validator rejects naive timestamps.

## 7. dB clamp makes the image black or white · Akshat, Soum
Sentinel-1 GRD in GEE is already in dB, typically −25 to 0 for sea. Scaling with the wrong range gives a flat image.
- **Symptom:** `sar.png` is uniformly black, white, or has no visible speckle.
- **Fix:** clamp to [−25, 0] then scale to 0–255. Sea should look like grey static; a slick is a distinctly darker patch; land is brighter.
- **Second-order trap:** Soum reads the 8-bit PNG back and must map it to dB using **the same clamp**. If Akshat changes the clamp, Soum's features change. Put the clamp values in `bounds.json` or announce any change.

## 8. Pixel origin · Akshat, Soum, Harshita
Pixel (0, 0) is **top-left = (west, north)**. Latitude decreases as row index increases.
- **Symptom:** detections appear vertically mirrored relative to the image.
- **Same trap in `origin.json`:** row 0 of the grid is the NORTH edge. Get this backwards and the heatmap flips.

## 9. Row-major flattening · Anushka, Harshita
`origin.json/values` is row-major from top-left, length = `shape[0] * shape[1]`. NumPy's default `.ravel()` is row-major (C order) — correct. If anyone reaches for `order='F'`, that's the bug.

## 10. Scene-level vs row-level train split · Soum
Regions extracted from the same 2048×2048 scene are highly correlated. A random row split gives a flattering, false accuracy number that a judge could dismantle.
- **Rule:** split by source scene. The number you report is the one you defend in December.

## 11. NaN and land pixels in SAR · Soum
Zenodo TIFFs contain NaNs and land. `np.mean` on an array with NaNs returns NaN and every downstream feature becomes NaN.
- **Fix:** mask explicitly, use `np.nanmean`, and assert no NaNs survive into `features.csv`.

## 12. Loading a whole NOAA CSV into pandas · Jaiveer
Daily AIS files are large. `pd.read_csv(whole_file)` will swap or die.
- **Fix:** chunked read with bbox+time filter applied per chunk, or DuckDB reading the CSV directly with a WHERE clause. Write Parquet once, query that forever after.

## 13. MMSI is not a clean identifier · Jaiveer
Reused, spoofed, mistyped, sometimes zero. **Do not build identity resolution.** Group by MMSI, drop tracks with <5 points, move on. One demo case.

## 14. Interpolating a vessel position across a gap · Jaiveer
Linear interpolation across a 3-hour AIS silence invents a position that never happened — and then scores it as a suspect.
- **Fix:** only interpolate across gaps under ~30 minutes. Longer gaps are exactly the signal you're looking for, not something to smooth over.

## 15. deck.gl doesn't re-render on data change · Harshita
Mutating the data array without `updateTriggers` leaves the layer showing the old frame.
- **Symptom:** slider moves, particles don't.
- **Related:** re-rendering the map container on every slider tick tanks the frame rate. Slider state must feed the layer, not the map component.

## 16. Re-parsing JSON on every scrub · Harshita
Parse each bundle once into memory. 3000 × 97 positions re-parsed per frame will stutter no matter how fast deck.gl is.

## 17. localStorage in the browser · Harshita
Not available in some embedded/preview contexts and unnecessary here. All state in Zustand, in memory.

## 18. GEE export size limits · Akshat, Anushka
`getInfo()` and direct downloads cap out. Full-resolution 10 m over a large region will fail or hang.
- **Fix:** export at 50–100 m/px for the display PNG; for fields, request a small region and coarse scale, and **cache to `.npz` so you never re-fetch during iteration.**

## 19. The bug that only appears on the second case · everyone
The library straddles both hemispheres: Gulf of Alaska -142.7, Farallones -123.9, Huntington -118.1, Jacksonville -79.6, Jamnagar +71.9, Mumbai +72.2. Eastern longitudes hide sign and convention bugs that surface instantly in the western ones. **Re-run every sanity check from scratch on each case.** Do not assume "it worked on the last one" transfers.

Gulf of Alaska at **59.5degN** is the other trap: a degree of longitude there is about half as wide as at 30degN. A cos(lat) term that was a rounding error on the Atlantic cases is a factor-of-two there — and a GeoTIFF exported in EPSG:4326 has **no** cos(lat) term at all, which is how an export that "fit" came back 25% over GEE's size ceiling.

## 20. Fixing a bundle by hand · everyone
Editing a JSON output to make the validator pass means the same bug returns on the next run, at the worst possible moment. **Fix the producing code. Always.**

## 21. A PASS that validated somebody else's files · everyone
**This has already happened here.** A stage wrote its output to `pipeline/*/out/` (gitignored) while `validate_case.py` reads `cases/<id>/`. The validator ran, went green, and was measuring the fixture bundle the whole time. Nobody did anything wrong — the two paths were never written down in the same place — but a green check on the wrong file is the most dangerous state in this project, because it converts "unchecked" into "checked and fine".

- **Fix:** the case folder is the hand-off medium. Publish into it before you validate:
  `python pipeline/export/build_case.py --case <id> --stage <act>`.
- **Check:** `validate_case.py` prints the directory it is reading on its first line. **Read that line.** If it is not the directory your stage just wrote to, the PASS is meaningless.

## 22. GeoTIFF nodata is `-inf`, not a very low dB value · Soum, Akshat
`sar_vv_vh.tif` is clipped to a rectangle, but a Sentinel-1 scene footprint is a slanted parallelogram — so some exports have real nodata in the corners. **Jamnagar is 86% covered and Farallones 82%**; the rest of each raster is `-inf`, flagged as the file's nodata value.

Treated as backscatter, `-inf` is the darkest thing in the scene by an infinite margin, and **a dark-spot detector will happily report the missing corner as an enormous slick.** Mask on `np.isfinite()` before any statistic — a median or a percentile over a band containing `-inf` is meaningless too.

- **Check:** `rasterio` reports `ds.nodata == -inf`. Coverage per case is recorded in `docs/receipts.md` and in each `meta.json`.

## 23. A component that scores the same for everybody · Jaiveer, Harshita
`type_prior` returned **1.00 for all 17 vessels** in an offshore lane, because an offshore lane is all tankers and cargo. It ranked nobody above anybody, and it silently added its full weight to every score on screen. `trajectory`, once its geometry was fixed, did nearly the same thing at 1.00 for 13 of 15.

A constant is not a score. **If a component cannot discriminate on this case, it is `null`, not a number** (D27, D28) — and `null` renders "n/a" with a `component_notes` line saying why, never a zero bar.

- **Check:** `validate_case.py` now warns when a non-null component holds the identical value for every scored suspect. Take that warning seriously; it means a bar on the card is decoration.

## 24. `np.nanmean` does not protect you from `-inf` · Soum, Akshat
The obvious defensive move against nodata is to reach for the `nan`-aware reductions. **They do not help here.** `np.nanmean` ignores `NaN` and *propagates* `-inf` — so on a scene with real nodata corners (Trap 22: Farallones, Jamnagar, Huntington) it returns `-inf`, Sobel over that emits `inf`, and those flow straight into the feature dict.

Then the real damage: **`json.dumps` writes bare `Infinity` / `NaN` into the file.** That is not valid JSON. Python's `json.loads` accepts it — so every Python-side check passes — and the browser's `JSON.parse` **throws**, so the bundle dies in the frontend with `Unexpected token I` and nothing upstream ever complained. This was found in `pipeline/detect/features.py` on 13 Sept before it shipped.

- **Fix:** mask on `np.isfinite()` *before* the statistic. `nanmean` is not a substitute for a finite-mask; it solves a different problem.
- **Check:** `validate_case.py` now passes `parse_constant=` to every `json.loads` and fails the bundle by name on a bare `Infinity`/`NaN`. The guard is permanent — but it catches this at the gate, not at the source. **Fix it in the producing code**, per the repo rule.

## 25. A stray PROJ installation hijacks `rasterio` · Akshat, Soum
`rasterio.open(..., crs='EPSG:4326')` failed on Akshat's laptop with `CRSError: The EPSG code is unknown`, pointing at `C:\Program Files\PostgreSQL\18\...\proj\proj.db` — **PostGIS's PROJ database, found ahead of rasterio's bundled one** and too old to read (`DATABASE.LAYOUT.VERSION.MINOR = 2`, needs ≥ 5). Any unrelated GIS install (PostGIS, QGIS, OSGeo4W) can do this by putting `PROJ_LIB`/`PROJ_DATA` in the environment.

The failure is loud, which is the good news — but it looks like a broken GeoTIFF or a bad EPSG code, so the hour goes into the wrong file.

- **Fix:** point PROJ at the venv's own copy before running anything geospatial:
  `export PROJ_DATA="$PWD/venv/Lib/site-packages/rasterio/proj_data"` (and `PROJ_LIB` to the same path for older PROJ).
- **Check:** `python -c "import rasterio; print(rasterio.crs.CRS.from_epsg(4326))"` must print `EPSG:4326` and not raise.

---

## Escalation
Stuck 45 minutes on any of the above, or on any external service? Message Akshat with: what you tried, the exact error text, and a minimal reproduction. That is not giving up — it is the protocol.
