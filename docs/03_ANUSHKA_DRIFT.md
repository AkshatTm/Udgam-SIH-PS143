# ANUSHKA — Stage 2: Drift Engine
*Read with 00_MASTER_PLAN.md. You own the physics: particles drifting backwards through real current + wind fields, 50-run ensemble, origin probability cloud. No ML anywhere in this component. No GPU needed.*

## You produce
`pipeline/drift/` · **real `particles.json` + `origin.json` for Ennore (Tue evening — hard deadline)** · the known-answer test suite (green) · quiver-plot sanity image · later: rerun for the US case.

## You consume
`detections.geojson` (until Tue, use case-000's fake one — your code must not care which) · HYCOM + ERA5 from GEE · contracts in Master §4.

## Tools
Your Claude Pro. Work in **four separate fresh chats, one per phase below** — each phase ends in a picture or a green test, which is how we catch wrong-but-running code cheaply. Paste this doc + Master §3–4 at the start of each chat.

## AI split
AI writes 100% of the code including the tests. YOU judge plausibility: ocean currents are ~0–1.5 m/s, a drifting particle covers tens of km per day (never hundreds, never metres), arrows in the quiver plot shouldn't all point into land. **The tests exist so you don't have to catch unit bugs by eye — run them on every change.**

---

## Phase 1 — TODAY (~3 h, no data, no GEE) · fake fields + known-answer tests
Build the integrator against analytic fields first. `drift/fields.py` exposes `get_uv(lons, lats, time) -> (u, v)` in m/s; a `--fake` mode returns constant fields.

`drift/step.py`: velocity = current + 0.03 × wind; RK2; dt = 15 min; vectorised NumPy over all particles (positions array shape [n,2] in lon/lat; convert displacement m → degrees: dlat = dy/111320, dlon = dx/(111320·cos lat)).

**Tests (`drift/tests.py`, run as assertions, must stay green forever):**
1. **Constant current** 0.5 m/s east, no wind, 1 particle, 10 h → lands 18.0 km east (±2%). Wrong by ×1000 = units bug; wrong axis = u/v swap; wrong sign = convention bug.
2. **Round trip**: forward 24 h then backward 24 h through the same field → returns within 0.5 km of start. *This is the test that validates backward mode — backward is a negative dt through the same field, not a minus sign on velocity.*
3. **Wind only**: 10 m/s wind, no current → particle moves 0.3 m/s.
4. **Plausibility asserts** (permanent, run on real fields too): speed < 3 m/s everywhere; 48 h total displacement between 5 and 200 km.

**Checkpoint:** tests 1–3 green. Post in group. Also commit the stub: `drift/run.py --fake` writing schema-valid garbage `particles.json` + `origin.json` (Harshita may use it).

## Phase 2 — Mon (~5 h) · real fields
GEE Python API (`ee.Initialize()` after auth):
- Currents: `HYCOM/sea_water_velocity`, bands `velocity_u_0`,`velocity_v_0` (surface). **Units are cm/s → divide by 100** — this is the classic silent bug here; test 4 catches it if you forget.
- Winds: `ECMWF/ERA5/HOURLY` (fall back to `ECMWF/ERA5_LAND/HOURLY` only if needed — we're over ocean, so use ERA5), bands `u_component_of_wind_10m`, `v_component_of_wind_10m`.
- Pull a small grid around the case (Ennore: 79.5–81.5 E, 12.0–14.5 N), time span detection_time − 30 h → detection_time, into NumPy via `sampleRectangle` or `getRegion` (AI chooses; region is small). Cache to `data/fields/<case>.npz` so you never re-fetch.
- `get_uv` = bilinear in space, linear in time, over the cached arrays. Longitudes: keep everything in −180…180.

**Checkpoint:** quiver plot of HYCOM at detection_time over the case region, coastline drawn — arrows plausible (≲1.5 m/s, not uniformly into land). Post the image. Test 4 green on real fields.

## Phase 3 — Tue (~5 h) · backward, ensemble, files
1. Seeding from `detections.geojson`: take the highest-confidence "oil" feature. `shape_class=="linear"` → seed 3000 particles along the polygon's principal axis (jitter ±300 m); `"blob"` → gaussian around centroid (σ ≈ half the equivalent radius). t0 = detection_time.
2. Backward 24 h (96 steps → 97 stored positions, including the start), storing every step → `particles.json` (positions[0] = on-slick).
3. **Ensemble:** 50 runs perturbing wind coefficient ~ U(0.025, 0.035), current field × N(1, 0.15) per run, seed jitter. Collect all 50×3000 final positions → 2D histogram (120×120 over a bounds box that contains them) → normalise → `origin.json` with centroid, radius_50_km/radius_90_km (radii of circles around centroid containing 50%/90% of mass), `time_window` = [t0−24h + spread where particle density peaks — AI implements: the window between the 10th and 90th percentile of per-run convergence times; if that's unstable, simply report [t0−24h, t0−8h] and mark method="bounded"], `ensemble_runs: 50`, `abstain` = true if radius_90 > 40 km.
4. Run the validator; plot heatmap over the map; hand to Akshat with the run command.

**Checkpoint:** heatmap image — a coherent cloud (not uniform noise, not a single pixel), offshore, radii printed.

## Phase 4 — Wed + event days
Buffer/fix Wed. Event days: `drift/run.py --case case-us-…` on the US bundle — same code, new detections + new cached fields. If GEE fights you on the US region, escalate immediately (45-min rule).

## Cut order if behind
The refined time_window method (ship the simple bounded window) → ensemble 50→25 runs (say so in origin.json) → NEVER cut: tests, backward mode, the ensemble itself.

## Definition of done
Tests 1–4 green and committed · quiver + heatmap images posted · valid `particles.json` + `origin.json` for Ennore Tue evening · rerun on US case by freeze.
