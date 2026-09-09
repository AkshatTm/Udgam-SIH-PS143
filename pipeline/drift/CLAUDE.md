# Drift (Stage 2) — Anushka

Owns: backward particle advection through real current+wind fields, 50-run ensemble, origin probability cloud.
Full brief: `docs/03_ANUSHKA_DRIFT.md`.

## Non-negotiable
- **No ML here.** Pure physics: `velocity = current + 0.03 * wind`, RK2, dt = 15 min, vectorised NumPy.
- **Backward = negative dt through the same field.** NOT a minus sign on velocity.
- `drift/tests.py` must stay green on every change. Four known-answer tests: constant current (0.5 m/s east, 10 h → 18.0 km east), round trip (forward then backward returns within 0.5 km), wind-only (10 m/s → 0.3 m/s), and permanent plausibility asserts (speed < 3 m/s; 48 h displacement 5–200 km).
- **HYCOM velocity bands are cm/s — divide by 100.** This is the single most common silent bug in this component.
- Longitudes stay in −180…180, never 0…360.
- Output is always a **probability grid**, never a point. Ensemble spread IS the uncertainty.

## Env
numpy, scipy, earthengine-api, matplotlib (for the sanity plots). No GPU.
Cache GEE fields to `data/fields/<case>.npz` — never re-fetch during iteration.

## Every phase ends in a picture
Quiver plot of the current field, track plot of one particle, heatmap of the origin cloud. Post them in the group. Wrong-but-running code is the failure mode these catch.

---

## The stub that is already here
`run.py --case <id> --stub` reads `cases/<id>/detections.geojson`, seeds off the highest-confidence oil feature, and writes schema-valid `out/particles.json` + `out/origin.json` by random walk. It exists to prove the seam before the physics exists.

**Keep** the seeding logic (it already implements the `shape_class` rule: `linear` → along the principal axis, `blob` → gaussian around the centroid) and the file writers. **Delete** `fake_walk()` and replace it with the real RK2 integrator. The stub deliberately does *not* touch GEE.
