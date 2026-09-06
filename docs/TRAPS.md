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
- **Symptom:** everything renders mirrored, rotated, or in the middle of Africa (lat/lon of Ennore swapped ≈ 13°E 80°N).
- **Catch:** the validator explicitly tests "outside bounds but inside when swapped" and names the file.
- **Rule:** MapLibre and deck.gl want `[lon, lat]`. Shapely wants `(x, y)` = `(lon, lat)`. `rasterio` row/col is `(y, x)`. NumPy arrays index `[row, col]` = `[y, x]` = `[lat, lon]`. **The array is the odd one out — convert at the boundary and never carry both conventions in one function.**

## 2. HYCOM is cm/s · Anushka
`HYCOM/sea_water_velocity` bands are centimetres per second. Divide by 100.
- **Symptom:** particles travel hundreds or thousands of km in 24 h.
- **Catch:** validator errors above 400 km; test 4 asserts speed < 3 m/s.

## 3. ERA5 wind is u/v components · Anushka
Bands are `u_component_of_wind_10m` / `v_component_of_wind_10m` — signed eastward/northward m/s, **not** speed and bearing. Wind speed is `hypot(u, v)`. The 3% rule applies to the vector.
- **Symptom:** drift direction is systematically wrong by a rotation.

## 4. Meteorological vs oceanographic direction convention · Anushka
Wind "from" vs current "towards" is a real convention clash in the literature. Because GEE gives you signed u/v components you sidestep it — **do not let generated code convert to bearings and back.** If a function takes `wind_direction_deg`, be suspicious.

## 5. Longitude 0–360 vs −180–180 · Anushka
Some ocean datasets use 0–360. Ennore at 80°E is identical in both, so **this bug will hide during Ennore and appear on the US case** (Gulf of Mexico is ≈ −90°, which is 270° in the other convention).
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
Parse each bundle once into memory. 3000 × 96 positions re-parsed per frame will stutter no matter how fast deck.gl is.

## 17. localStorage in the browser · Harshita
Not available in some embedded/preview contexts and unnecessary here. All state in Zustand, in memory.

## 18. GEE export size limits · Akshat, Anushka
`getInfo()` and direct downloads cap out. Full-resolution 10 m over a large region will fail or hang.
- **Fix:** export at 50–100 m/px for the display PNG; for fields, request a small region and coarse scale, and **cache to `.npz` so you never re-fetch during iteration.**

## 19. The bug that only appears on the second case · everyone
Ennore (80°E, 13°N, northern hemisphere, eastern longitudes) hides sign and convention bugs that surface in the Gulf of Mexico (−90°E, 28°N). **When you rerun on the US case, re-run every sanity check from scratch.** Do not assume "it worked for Ennore" transfers.

## 20. Fixing a bundle by hand · everyone
Editing a JSON output to make the validator pass means the same bug returns on the next run, at the worst possible moment. **Fix the producing code. Always.**

---

## Escalation
Stuck 45 minutes on any of the above, or on any external service? Message Akshat with: what you tried, the exact error text, and a minimal reproduction. That is not giving up — it is the protocol.
