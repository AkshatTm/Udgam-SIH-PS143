# Harshita — update log

*Newest entry at the TOP. Copy the block from `TEMPLATE.md`, fill four lines, commit it with
your code in the same push. Two minutes after each phase — non-negotiable.*

**Why:** your AI has no memory between chats. This file is the memory. It means you can close a
chat, switch from Claude to ChatGPT, hand your work to someone else, or come back after sleeping,
and lose nothing.

**To resume from it:** *"Here are the master plan, my task document, and my update log. Read the
top entry and tell me exactly where I left off and what the next step is."*

---

## [2026-09-10 13:46] W1 / Phase 5.1 — origin visualization: HeatmapLayer → BitmapLayer (ruling D11)

**Done:** The origin probability field now renders through a deck.gl `BitmapLayer`, never a
`HeatmapLayer` (ruling D11 — HeatmapLayer re-smooths in screen pixels and renormalises colour
per viewport, so the cloud changed shape/colour as a judge zoomed). `origin.ts` drops
`buildOriginPointCloud` / `OriginPointCloud`; `buildOriginImage(origin)` rasterises the
row-major 120×120 grid onto an `OffscreenCanvas` (grid row `r` → canvas row `r`, row 0 =
NORTH, no flip) and returns its `ImageBitmap` — a single fixed amber hue in every texel with
**alpha alone** carrying probability, `alpha = v**0.7 · 0.85 · 255`: proportional, gamma not
linear, no hard cutoff (docs/04 Phase 5.1 — a threshold left a just-above-cutoff fringe reading
as a phantom second cloud). `MapView` builds the image once per bundle, mounts one
`BitmapLayer` (id `origin`) georeferenced with **`origin.bounds`** (not bounds.json), and the
T−24h→T−0 fade + Origin toggle stay a pure `opacity` change with the layer kept mounted (the
slider-freeze fix is preserved). `originOpacity` smoothstep, the 50/90 % ring `PathLayer`,
camera, store, `ContextPanel`, `LayerToggles` and the particle layer are untouched.

**Files touched:** `web/lib/origin.ts` (modified — `buildOriginImage` via OffscreenCanvas,
removed `buildOriginPointCloud` + `OriginPointCloud`) · `web/components/MapView.tsx` (modified —
`BitmapLayer` replaces `HeatmapLayer`, removed the `@deck.gl/aggregation-layers` import and the
`ORIGIN_RADIUS_PIXELS` / `_INTENSITY` / `_THRESHOLD` / `_WEIGHTS_TEXTURE_SIZE` constants). No
data / case / schema / pipeline change. `@deck.gl/aggregation-layers` is now unused in
`web/package.json` — left in place (also a transitive dep of `deck.gl@9.4`), not touched.

**Run command:**
```bash
robocopy cases web\public\cases /MIR     # bundle copy (unchanged)
cd web && npm run dev                     # open http://localhost:3000/case/case-000/trace
```
Expected: enter Trace (Particles + Origin auto-on); at full rewind a soft amber cloud sits
concentric with the two amber rings; zooming in/out does not change the cloud's shape or colour
relative to the rings; dragging T−0→T−24h eases the cloud in with no hard edge and no slider
stall.

**Checkpoint artefact:**
- **Static (all PASS):** `npm run lint` → 0 warnings · `npx tsc --noEmit` → clean ·
  `npm run build` → `✓ Compiled successfully`, types + lint pass, 5/5 pages, `/` 11.2 kB /
  99.1 kB first load (dev server stopped first so `.next` was free).
- **Browser (Playwright MCP, Chromium on the dev server):** D11 zoom test — cloud shape and
  colour *relative to the 50/90 % rings* unchanged across zoom in +3 / out to −2. Fade at
  T−9h 30m: edges dissolve smoothly, no fringe / phantom second cloud. `origin.json` fetched
  **once**, not re-fetched on scrub / zoom / stage change. Console clean — the old
  `luma.gl: Binding weightsTexture not set` warning (HeatmapLayer-only) is gone. Origin toggle
  off/on drops and restores the cloud **and** rings together; particles unaffected. Trace card
  still shows centroid `80.64695, 13.46316`, radii `4.2 km` / `11.8 km`, window, `50` runs.
- `python scripts/validate_case.py cases/case-000` → `PASS`. Screenshots in the session
  scratchpad, not committed.

**Open issues:**
- Row-0-is-north can't be *proved* on case-000 — its origin blob is near-radially-symmetric, so
  a vertical flip renders identically. Verified only as concentric-with-rings. The definitive
  check is the real Ennore bundle (docs/04 §7.1: origin must be NE of and above the slick); if
  it renders flipped there, reverse the row index in `buildOriginImage`
  (`i → (rows-1-r)*cols + c`).
- `@deck.gl/aggregation-layers` is now an unused dependency in `web/package.json` — drop it
  after the freeze, not now.
- Display constants (`ORIGIN_RGB`, `ORIGIN_ALPHA_GAMMA`, `ORIGIN_ALPHA_MAX`) are fitted to
  case-000's in-frame blob and are first-to-retune against the real bundle (docs/04 §7.2);
  Urooz owns the final palette tokens.
- This entry is written but **not committed** — no commit / push was performed for W1.

**Next:** W5 — union / per-stage camera (docs/04 §5.2): extend `lib/extent.ts` to
`bounds.json ∪ particle extent ∪ origin.bounds` so the cloud and particles are not framed
off-screen on real data.

---

## [2026-09-08 15:55] Phase 3 — origin heatmap + rings, Detect object card + feature bars, Trace card

**Done:** Phase 3 of the frontend is complete on `case-000`. Seven files:

- **`web/lib/origin.ts` (NEW).** `loadOriginBundle(id)` fetches `/cases/<id>/origin.json` **once**
  (`cache: "no-store"`), validates every field the frontend consumes against CONTRACTS §6 —
  `bounds` (4 finite numbers, `west<east`, `south<north`, lon −180..180, lat −90..90), `shape`
  `[rows,cols]` positive ints, `values` (`len == rows*cols`, each finite, `>= 0`, peak `<= 1`,
  peak `!= 0`), `centroid` (`[lon,lat]` in range — the [lat,lon]-swap guard), `radius_50_km` /
  `radius_90_km` (`>= 0`, `50 <= 90`), `time_window` (two strings, trailing `Z`, parseable,
  `start <= end`), `ensemble_runs` (int `>= 1`), `abstain` (boolean). A bad field throws a
  descriptive `Error` the shell surfaces as a banner — **never patched client-side**. Then
  `buildOriginPointCloud()` expands the row-major grid into a weighted `[lon,lat]` point cloud
  in deck.gl binary-attribute form — **row 0 = NORTH** (`lat = north − (r+0.5)/rows·latSpan`),
  C-order `values[r*cols+c]` (TRAPS #8/#9), cells `<= 0` dropped — and `buildOriginRadiusRings()`
  builds the 50 % / 90 % rings as closed `[lon,lat]` polygons around `centroid`, converting km to
  an angular offset on a sphere (`Δlat° = r/R_earth · 180/π`, `Δlon° = Δlat°/cos φ` — **km are
  never treated as degrees**). All three functions are pure and allocate once; callers memoise on
  the bundle identity, so nothing here runs on a scrub.
- **`web/lib/contracts.ts`.** Added `RawOriginBundle` (the on-disk shape, mirrors CONTRACTS §6
  field-for-field) and a bare `GeoBounds` helper (origin.json's `bounds` has no `width_px`/`db_*`
  unlike `bounds.json`). No change to the frozen `docs/CONTRACTS.md`.
- **`web/lib/store.ts`.** `origin` / `originStatus` / `originError` state (same discipline as
  particles: fetched + parsed once per case, then read from memory). `loadOrigin()` mirrors
  `loadParticles()` — guards a concurrent load, drops a stale response if the case switched
  mid-fetch. `loadActiveCase` fires **both** trace bundles in the background when
  `meta.acts_available` includes `"trace"` (CONTRACTS §1); both reset on a case switch.
- **`web/components/MapView.tsx`.** Origin `HeatmapLayer` (id `origin`, `weightsTextureSize: 512`)
  + 50/90 `PathLayer` (id `origin-radii`), drawn under the particles. `originCloud` / `originRings`
  are `useMemo`'d on the bundle identity; `originOpacity` is a `smoothstep(0.2, 0.9, t/(nSteps−1))`
  of the rewind fraction — **from the integer timestep `t`, not the raw `tNorm`** — and `0` when
  the Origin toggle is off. The origin layers stay mounted for the life of the case; the fade and
  the toggle are an `opacity`-only change, so **deck.gl never re-aggregates on a scrub**. Particle
  and origin layers are separate memos composed in one push effect. This same change is the
  slider-freeze performance fix — see the `[2026-09-08 11:55]` entry below for the profiling and
  before/after numbers.
- **`web/components/ContextPanel.tsx`.** Detect **object card** — classification badge (solid red
  "Oil" / muted grey "Look-alike"), confidence as the headline, then **Recharts horizontal feature
  bars** for elongation / edge gradient / contrast (display-only magnitudes, labelled *"not model
  probabilities"* — the measured value is always printed beside the bar), then area / shape class /
  centroid / id. New **`TraceCard`** for the Trace stage — centroid (5 dp), 50 % / 90 % radius (km),
  ensemble runs, the origin **time window** (rendered in UTC with the raw ISO/`Z` string kept on
  `title`), and the uncertainty note *"The cloud widens with rewind depth — the further back you
  drift, the less certain the origin."* Clean loading and error states; the Attribute branch is
  unchanged.
- **`web/components/LayerToggles.tsx`.** Origin toggle is now `live: true`, greyed (with tooltip)
  for a case with no `trace` act, same as Particles.
- **`web/components/AppShell.tsx`.** `ContextPanel` is now a `next/dynamic` (`ssr: false`) import
  with an `<aside>` skeleton — keeps Recharts out of the first-load bundle.

State is Zustand-in-memory only (no localStorage / no `persist`). The frontend calls no Python —
every `fetch` is a static `/cases/<id>/*.json`. No new package downloaded: `@deck.gl/aggregation-
layers` (for `HeatmapLayer`) was already in the lockfile as a direct dependency of `deck.gl@9.4.0`;
`package.json` now just declares it explicitly. No data / case / schema / pipeline change.

**Files touched:** `web/lib/origin.ts` (new) · `web/lib/contracts.ts` (modified — origin types) ·
`web/lib/store.ts` (modified — origin state + `loadOrigin`) · `web/components/MapView.tsx`
(modified — HeatmapLayer + rings + fade + perf fix) · `web/components/ContextPanel.tsx` (modified —
DetectCard + feature bars + TraceCard) · `web/components/LayerToggles.tsx` (modified — Origin live) ·
`web/components/AppShell.tsx` (modified — lazy ContextPanel) · `web/package.json` +
`web/package-lock.json` (modified — explicit `@deck.gl/aggregation-layers` declaration, no tree change)

**Run command:**
```bash
robocopy cases web\public\cases /MIR    # bundle copy (unchanged)
cd web && npm run dev                    # open http://localhost:3000
```
Expected: toggle **Particles** + **Origin** on. Click the oil slick → object card with the
classification badge, 87 % confidence, and the three feature bars. Left rail: click **Trace** →
origin card (centroid `80.64695, 13.46316`, radii `4.2 km` / `11.8 km`, window `28 Jan 2017
04:14 UTC → 16:14 UTC`, ensemble runs `50`, the uncertainty note). Drag / ▶ the slider toward
T−24h → the orange origin cloud + two white rings ease in with no slider stall; the Trace card
stays put while the map rewinds.

**Checkpoint artefact:**
- **Static (all PASS):** `npm run lint` → 0 warnings · `npx tsc --noEmit` → clean ·
  `npm run build` → compiled, `/` route 7.12 kB / 95 kB first load (built via a temp `distDir`
  because `next dev` holds `.next` on Windows).
- **Browser acceptance** — headed Chrome over CDP, real GPU (ANGLE / Intel UHD), temporary
  `_updateWeightmap` / `_updateBounds` / rAF-frame probes added for the measurement and then
  removed (not in the diff). Scripts + screenshots live in the session scratchpad, not committed.
  - Origin OFF and ON at T−0: heatmap hidden (`opacity 0`); no stall.
  - Drag T−0→T−24 with Origin ON: cloud + 50/90 rings fade in; **`_updateWeightmap` = 0**
    during the drag; p50 16.7 / p95 16.8 / max 17.0 ms.
  - Scrub across the fade threshold ×16–20: **`_updateWeightmap` = 0**, max 17.1 ms, 0 long frames
    (this crossing used to stall ~300 ms each time).
  - Play full rewind / play again: 60 fps, ends at `T−24.0 h`. Pause → readout freezes; resume →
    readout advances (`T−4.8 h` held, then `T−9.8 h` after resume).
  - Origin OFF scrub vs Origin ON scrub: identical timing (max 17.2 vs 17.0 ms).
  - Select oil `det-01`: card shows `Oil` / `87 %` / `12.4 km²` / elongation `8.2` / edge gradient
    `0.34` / contrast `−6.2 dB` / `linear` / `80.436, 13.310` / `det-01` + the Recharts bars —
    every value matches `detections.geojson`.
  - Select look-alike `det-02`: `Look-alike` / `71 %` / `7.9 km²` / `1.4` / `0.11` / `−3.1 dB` /
    `blob` / `80.262, 13.130` / `det-02` — matches `detections.geojson`.
  - Click empty water → selection cleared, panel returns to "Select a detection on the map."
  - Detect → Trace → Detect (and → Attribute): **map `<canvas>` identity unchanged** across every
    switch (no remount); slider stays interactive while on Trace (value `1 → 0.4`, timestep 58).
  - `TraceCard` vs `origin.json`: centroid `80.64695, 13.46316` (5 dp), `50% radius 4.2 km`,
    `90% radius 11.8 km`, `Ensemble runs 50`, window `28 Jan 2017 04:14 UTC` → `28 Jan 2017
    16:14 UTC` with the raw `2017-01-28T04:14:00Z` / `…16:14:00Z` on hover `title`, uncertainty
    note exact — all correct.
  - Rings: centre = `origin.centroid` exactly; r50 half-spans `Δlat 0.03777°` (`4.2/6371.0088·
    180/π`), `Δlon 0.03884°` (`÷ cos 13.463°`); r90 `Δlat 0.10612°` (`11.8 km`) — closed rings.
  - Particle deck-canvas pixels differ between `t=0` and `t=96` (particles keep updating).
  - `TraceCard` `innerText` byte-identical and the same DOM node before/after a full T−0→T−24
    drag (not remounted while the map / particles / origin update around it).
  - Console: **0 errors, 0 exceptions.** One benign warning only (see open issues).
- **Frame-time distribution** (5 scenarios, ~800–1600 samples each): every scenario p50 16.7 ms,
  p95 ≤ 16.9 ms, p99 ≤ 17.2 ms, max ≤ 17.7 ms, **0 frames > 50 ms**, `_updateWeightmap` = 0
  during all scrub / playback. Origin ON is indistinguishable from Origin OFF.

**Open issues (non-blocking):**
- **Greyed / unavailable StageRail path is UNVERIFIED at runtime.** `case-000` exposes all three
  acts (`acts_available: ["detect","trace","attribute"]`), so no greyed rail button exists to
  click. The code path is present (`disabled={!available}`, `cursor-not-allowed` styling, tooltip,
  `setStage` guard) — re-test against the Ennore two-act bundle (`acts_available: ["detect",
  "trace"]`) when it lands. Same for the truly-unavailable Attribute panel.
- **Synthetic `case-000` origin cloud/rings extend beyond the SAR frame.** `origin.json` `bounds`
  (80.347–80.947 E, 13.163–13.763 N) reach past `bounds.json` / the SAR image (80.1–80.7 E,
  12.95–13.55 N), so the cloud and the top-right of the rings render over black at full rewind.
  This is a property of the synthetic bundle, not a frontend bug — the layer draws where the grid
  says. Re-check on the real Ennore bundle.
- **Benign console warning:** `luma.gl: Binding weightsTexture not set: Not found in shader
  layout.` — fires once on first heatmap render; known deck.gl 9.4 `HeatmapLayer` issue; the
  heatmap renders correctly.
- Playing ▶ within ~1 s of the page finishing load (before the async shader compile settles) can
  show a few ~150 ms hitches on the first play-through. Not reproducible at any realistic pace
  (the fade alone gives a ~2.4 s runway from T−0); every subsequent play / scrub is clean.
- Not tested: the real Ennore bundle, any case other than `case-000`, the no-spill / `abstain`
  states, and the actual demo laptop (measurements are from this dev machine's Intel UHD).
- `web/public/cases/case-000/` is a gitignored copy — refresh it before running.

**Next:** Phase 4 — swap in the real Ennore bundle (a data-only change, per the architecture),
then polish loading / empty / unavailable states for the HOD demo and re-run the greyed-StageRail
check.

## [2026-09-08 11:55] Phase 3 bug fix — origin HeatmapLayer froze the slider on fade-in

**Done:** Playback/scrub stalled for 0.3–1.8 s whenever the origin cloud faded in. Profiled it
in headed Chrome over CDP (probe on `HeatmapLayer._updateWeightmap` / `_updateBounds` +
a rAF frame timer): the aggregation was **not** re-running per tick, but the layers were being
**added to / removed from** the deck list on the `fade > 0` boundary, so deck.gl re-mounted the
`HeatmapLayer` on every threshold crossing — each mount = allocate a 2048² rgba32float weights
texture + compile 3 shader programs + a 4.2 M-vertex max-reduction pass (~1.7 s first time,
~0.3 s after, on the demo-class Intel UHD GPU). That main-thread/GPU block was the "freeze".
Fix, all in `MapView.tsx`: (1) the origin `HeatmapLayer` + rings `PathLayer` are now built from
memoised data (`originCloud` / `originRings`, keyed on bundle identity — already the case) and
**stay mounted for the life of the case**; the T−24h→T−0 fade and the Origin toggle are a pure
`opacity` change (0 = hidden), which deck.gl applies without re-aggregating. (2) They mount as
soon as `origin.json` loads (opacity 0), so the one-time shader/texture cost is paid during the
existing "Loading…" state, not mid-playback. (3) `weightsTextureSize: 512` (was default 2048) —
the grid is 120×120 over ~0.6°, so 512 is finer than the data and cuts that one-time cost ~16×.
(4) fade is derived from the integer timestep `t`, not the raw `tNorm`, so it changes ≤ n_steps
times across a scrub, never continuously; particle layer and origin layers are separate `useMemo`s
composed in one push effect. No change to `origin.json`, `particles.json`, contracts, the store,
Anushka's pipeline, or any other component. Fade / 50-90 rings / Origin toggle / particle
performance all preserved.

**Files touched:** `web/components/MapView.tsx` (modified — deck layer composition only)

**Run command:**
```bash
robocopy cases web\public\cases /MIR    # bundle copy (unchanged)
cd web && npm run dev                    # open http://localhost:3000
```
Expected output: toggle Particles + Origin on. At T‑0 the heatmap is hidden; drag/▶ toward
T−24h and the orange origin cloud + two white 50/90 % rings ease in with **no slider stall** at
the fade point. `npm run lint`, `npx tsc --noEmit`, `npm run build` all pass (build via a temp
`distDir` because `next dev` holds `.next` on Windows).

**Checkpoint artefact:** CDP verification (`scratchpad/verify.mjs`, screenshots
`v_origin_on_T0.png` / `v_full_rewind.png` / `v_mid_fade.png`). Frame timing, max frame ms:
| scenario | before | after |
|---|---|---|
| play full rewind, Origin ON | ~1500 ms (3 long frames) | **17 ms (0)** |
| scrub across fade threshold ×12 | ~333 ms (10 long frames) | **17 ms (0)** |
| manual drag T‑0→T‑24, Origin ON | stall on fade-in | **17 ms (0)** |
| Origin OFF scrub vs Origin ON scrub | — | identical (17 ms) |
CPU profile of a warm playback: 92 % idle, no `_updateWeightmap`, no shader compile. Particle
readout advances T−2.8 h → T−9.0 h mid-playback (particles keep updating). 0 console errors.

**Open issues:**
- If you hit ▶ within ~1 s of the page finishing load (before the async shader compile settles)
  the first play-through can show a few ~150 ms hitches. Not reproducible at any realistic pace
  (the fade alone gives a ~2.4 s runway from T‑0), and every subsequent play/scrub is clean.
- Heatmap bloom still extends past the SAR frame at full rewind (radius/intensity/colour tokens
  are Urooz's — unchanged by this fix).
- `web/public/cases/case-000/` is a gitignored copy — refresh before running.

**Next:** the Trace-stage origin card — done later the same day; see the
[2026-09-08 15:55] Phase 3 implementation entry above. (Stage-rail `acts_available` logic
already landed in Phase 1.) Then Phase 4: swap in the real Ennore bundle.

## [2026-09-07 15:20] Phase 2 bug fix — T-0 particle cloud was mirrored across the slick

**Done:** At T-0 the particle cloud crossed the det-01 polygon in an X instead of lying along
it — only ~28% of `positions[0]` fell inside the slick. Root cause was in the data producer,
not the frontend: `scripts/make_case000.py` seeded the particles along `radians(-24)` **in
lon/lat space**, but the polygon (`ellipse_ring`) and the SAR slick (`make_sar`) apply that
-24 deg tilt **in pixel space**, and `px2ll` then flips the y axis (pixel y points south). Net
effect: polygon principal axis `+24 deg` in lon/lat, particle-cloud axis `-24 deg` — mirror
images sharing the centroid. Fixed the generator to seed at `+24 deg` (`cos` is even so the
longitude spread and every RNG draw are unchanged; only the latitude offset flips sign, so
`sar.png` / `detections.geojson` / `meta.json` / `bounds.json` / `suspects.json` regenerate
byte-identical, and `origin.json` / `vessels.geojson` shift only by the corrected final-cloud
mean). Regenerated the full bundle with `.venv` (Python 3.11.9, numpy + pillow) and re-ran the
validator — `PASS`, 0 warnings. After the fix `positions[0]` PCA axis is `+23.93 deg` (polygon
is `+24.00`) and **100%** of T-0 particles sit inside the det-01 polygon; `positions[0]` mean
`[80.4355, 13.3098]` lands on the det-01 centroid `[80.436, 13.31]`. Coordinates stay
`[lon, lat]` / EPSG:4326, all <=5 dp, in bounds. No schema, UI, or frontend-code change.

**Files touched:** `scripts/make_case000.py` (modified — seed axis `-24 -> +24 deg`) ·
`cases/case-000/particles.json` (regenerated output) · `cases/case-000/origin.json`
(regenerated — centroid follows the corrected cloud) · `cases/case-000/vessels.geojson`
(regenerated — tracks built from the origin centroid).

**Run command:**
```bash
.venv\Scripts\python scripts\make_case000.py
.venv\Scripts\python scripts\validate_case.py cases\case-000
```
Expected output: generator writes `cases/case-000/` (7 files, ~5.8 MB); validator prints
`PASS   acts=['detect', 'trace', 'attribute']  (0 warning(s))`.
In the app: toggle Particles on at T-0 → the blue cluster lies *along* the red slick outline,
not across it.

**Checkpoint artefact:** point-in-polygon check — `positions[0]` inside det-01: 28.3% before →
100.0% after; PCA axis 155.86 deg → 23.93 deg (det-01 polygon is 24.00 deg). `validate_case.py`
PASS, 0 warnings. Phase-2 frontend (`tsc --noEmit`, `next build`) unaffected — no web code
touched; deck.gl `ScatterplotLayer` already binds `positions[t]` as `[lon, lat]`.

**Open issues:**
- `web/public/cases/case-000/` is a gitignored copy — refresh it before running the app:
  `robocopy cases web\public\cases /MIR`.
- none outstanding on the fix itself.

**Next:** Phase 3 — Origin `HeatmapLayer` from `origin.json`, stage-aware right panel, stage-rail
logic from `acts_available`.

## [2026-09-07 00:45] Phase 2 — particle playback (slider + deck.gl ScatterplotLayer + play/pause)

**Done:** The time slider now drives 3000 particles across 96 timesteps and it is smooth. New
`lib/particles.ts` fetches `particles.json` **once** per case, validates it against CONTRACTS §5
(shape, `n_steps`/`n_particles` dimensions, `t0` trailing Z, `direction`, plus a [lon,lat]-order
/ swap spot-check on all four corners), and flattens each timestep into its own `Float32Array`
(`frames[t]`, laid out `[lon,lat,lon,lat,…]`). The store gained `particles` / `particlesStatus`
/ `particlesError` / `playing`; `loadActiveCase` kicks off `loadParticles()` in the background
only when the case has a `trace` act, and cross-checks `particles.t0` against
`meta.detection_time` (±60 s). `lib/timestep.ts` binds the existing continuous `tNorm` (0..1,
1 = T‑0) to an integer timestep `t = round((1−tNorm)·(nSteps−1))`. `MapView` creates **one**
`MapboxOverlay` (overlaid, not interleaved) as a MapLibre control at map-init and never
recreates it; a single effect keyed on `[particles, particlesVisible, t]` pushes a fresh
`ScatterplotLayer` whose `data` is the binary form `{length, attributes:{getPosition:{value:
frames[t], size:2}}}` — deck.gl re-uploads the position buffer on the new `data` object, and
`frames[t]` is pre-built so **no particle array is allocated on a tick**. `usePlayback.ts` runs
a `requestAnimationFrame` loop at `PLAYBACK_STEPS_PER_SEC = 8` (doc's "~8× real time" read as 8
timesteps/s → full 24 h rewind in ~12 s), advances `t` toward `nSteps−1`, stops at the end, and
`cancelAnimationFrame`s on pause / unmount / case-switch. Manual drag cancels playback. The
Particles toggle is now live (greyed for a case with no `trace` act); the slider shows a
`T−<h>` readout. All Phase 1 SAR/detection behaviour is untouched. State stays Zustand-in-memory
— no localStorage.

**Files touched:** `web/lib/particles.ts` (new) · `web/lib/timestep.ts` (new) ·
`web/lib/usePlayback.ts` (new) · `web/lib/contracts.ts` (modified — `RawParticleBundle`) ·
`web/lib/store.ts` (modified — particle state + `loadParticles` + `playing`) ·
`web/components/MapView.tsx` (modified — `MapboxOverlay` + particle `ScatterplotLayer`) ·
`web/components/TimeSlider.tsx` (modified — enabled, play/pause, readout) ·
`web/components/LayerToggles.tsx` (modified — Particles live)

**Run command:**
```bash
robocopy cases web\public\cases /MIR   # bundle copy (unchanged; particles.json already present)
cd web && npm run dev                   # single instance, open http://localhost:3000
```
Expected output: SAR + detections as before. Toggle **Particles** on → a tight blue cluster of
3000 dots sits on the slick at T‑0. Drag the slider left → the dots unwind and spread toward the
upper-right; readout counts up to `T−23.8 h`. ▶ auto-scrubs the rewind in ~12 s and stops at
T−24h; dragging pauses it.

**Checkpoint artefact (the project's most important):** headless-Chrome CDP test
(`scratchpad/ptest.mjs`, `report.json`, screenshots `01`–`08`).
- **Manual scrub (60 fps slider sweep, both directions, 3 s sample):** avg 16.67 ms, p95 16.7 ms,
  max 16.8 ms, **0 frames > 32 ms**. Locked 60 fps.
- **Playback (3.5 s sample):** avg 16.67 ms, max 16.8 ms, **0 jank**. Advances ~8.4 steps/s.
- Frames at t=0 vs t=95 verified distinct; playback stops at T−24h with the button reset to
  "Play"; pause holds position; Particles-off clears the deck layer; SAR + detections unaffected.
- **No console errors, exceptions, or network failures from Naap.** `npm run lint`,
  `npx tsc --noEmit`, `npm run build` all pass (`/` 6.25 kB; deck.gl is in the lazy MapView
  chunk, not first-load JS).
- Tested with `--disable-gpu` (SwiftShader software WebGL2) — a harder case than the demo
  laptop's real GPU — and it still held 60 fps. **No decimation / particle-count fallback
  needed.** The documented escape hatches (every 2nd step · 2000 particles) remain untouched.

**Open issues:**
- Screenshots are from headless SwiftShader at 1262×760. Still worth a 10-second eyeball on the
  actual demo laptop (real GPU, real resolution) before Wednesday — expected to be identical or
  better, but that's the machine that matters.
- `MapboxOverlay` + maplibre-gl **v6** is a new pairing (deck 9.4). Overlaid mode works here
  (deck canvas stacks above the map canvas, camera stays in sync while scrubbing). If a future
  maplibre bump breaks the sync, the fix is `interleaved` mode or a manual `move`-event sync —
  not a rewrite.
- `particles.json` is fetched `cache: "no-store"` (matches `loadCase`), so switching away from a
  case and back re-downloads its 6 MB bundle. Fine for the demo (one case, loaded once). If the
  case switcher feels heavy on event day, drop `no-store` for particles.
- `PLAYBACK_STEPS_PER_SEC` (8) is a single constant in `lib/usePlayback.ts` — retune on the demo
  laptop if 12 s feels too fast or too slow for the narration.

**Next:** Phase 3 — Origin `HeatmapLayer` from `origin.json`, stage-aware right panel (Detect
object card + Recharts feature bars; Trace origin card), stage-rail logic from `acts_available`.

## [2026-09-06 23:40] Phase 1 fix — map was blank in the browser; two bugs, both fixed + verified

**Done:** The Phase 1 map rendered nothing in a real browser (blank centre, shell fine). Traced
the MapLibre runtime chain end to end in headless Chrome. Two independent bugs:

1. **Container collapsed to 0 height.** `maplibre-gl.css` sets `.maplibregl-map { position:
   relative }` and its chunk loads *after* Tailwind, so it beat the `absolute` utility on the
   map `<div>` (equal specificity → source order wins). With `position: relative` the `inset-0`
   offsets did nothing, the div had no in-flow content, and it collapsed to 0 px — MapLibre
   then sized its canvas to the 400×300 fallback and `overflow:hidden` clipped it away.
   Fix: `className="!absolute inset-0"` (force the utility). One char.

2. **GeoJSON worker never started.** maplibre-gl v6 runs its GeoJSON/vector tiler in a separate
   ESM worker (`dist/maplibre-gl-worker.mjs`). Its built-in worker-URL resolver bails unless
   `import.meta.url` is an `http(s)` URL — webpack replaces it with a build-time
   `file:///C:/Users/hp/naap/web/node_modules/...` path, so maplibre fell back to
   `new Worker("")` and the worker silently died. Image/raster layers decode on the main thread
   so **SAR still drew** — but every vector source (the detections) stayed empty and the map
   never reached `idle`. Fix: copy the worker + its shared chunk into `public/maplibre/` (new
   `web/scripts/copy-maplibre-worker.mjs`, wired to `predev`/`prebuild`) and call
   `setWorkerUrl("/maplibre/maplibre-gl-worker.mjs")` at module load in `MapView.tsx`.

React Strict Mode double-mount was checked and is **not** a problem — the effect's `map.remove()`
cleanup handles it; `load` fires once on the surviving instance.

**Files touched:** `web/components/MapView.tsx` (modified — `!absolute`, `setWorkerUrl`) ·
`web/scripts/copy-maplibre-worker.mjs` (new) · `web/package.json` (modified — `predev`/`prebuild`
hooks) · `.gitignore` (modified — ignore `web/public/maplibre/`, it's a copy like `cases/`)

**Run command:**
```bash
robocopy cases web\public\cases /MIR   # bundle copy (unchanged)
cd web && npm run dev                  # predev copies the worker; open http://localhost:3001
```
Expected output: SAR scene between 80.1–80.7 E / 12.95–13.55 N, **det-01 solid red outline +
fill**, **det-02 grey dashed outline**, SAR/Detections toggles work, clicking det-01 fills the
right panel. `npm run build` then `npx next start` renders identically.

**Checkpoint artefact:** verified in headless Chrome (dev on :3001 and prod build on :3005).
`map.loaded()===true`, `queryRenderedFeatures` returns `det-fill:[det-01,det-02]`,
`det-outline-oil:[det-01]`, `det-outline-lookalike:[det-02]`. Screenshots (full map + zoomed
det-01 red solid + zoomed det-02 grey dashed) in scratchpad — post in group from the demo laptop.
`npm run lint`, `npx tsc --noEmit`, `npm run build` all pass.

**Open issues:**
- `web/public/maplibre/` must exist before `next dev`/`next build`. The `predev`/`prebuild`
  hooks create it automatically; a bare `next dev` (not via `npm`) would skip that. If the map
  goes blank again, check the two files are in `web/public/maplibre/`.
- If maplibre-gl is ever upgraded, the copied worker refreshes on the next `npm run dev/build` —
  no action needed, but don't hand-pin the worker.
- Port 3000 was occupied by a stale process during testing; used 3001/3005. Not our code.

**Next:** Phase 2 — time slider bound to `t`, deck.gl ScatterplotLayer reading
`particles.positions[t]` loaded once into memory, play/pause auto-scrub, smoothness checkpoint.

## [2026-09-06 22:30] Phase 1 — single-screen shell + SAR + detections

**Done:** Built the whole judge-facing shell in `web/` against `case-000`. One screen: header
(case title / satellite / detection time + case switcher), left Detect/Trace/Attribute rail
driven by `meta.acts_available` (greyed + tooltip when an act is missing), central MapLibre map
(plain dark style, no tiles) with `sar.png` pinned to `bounds.json` and `detections.geojson`
rendered as oil = solid red outline / look-alike = grey dashed, right stage-aware context panel
(Detect shows the clicked detection's contract properties; no-spill banner when zero oil
features; Trace/Attribute are "later phase" placeholders), bottom time slider (present, inert)
and SAR/Detections/Particles/Origin/Vessels toggles (SAR + Detections live, the other three
disabled). Click a polygon → selection stored in Zustand and highlighted white. State is
Zustand in-memory only, no persistence, no localStorage. Bundle loader validates shapes and
shows a visible error banner on any malformed/missing file — no client-side patching.

**Files touched:** `web/lib/contracts.ts` (new) · `web/lib/cases.ts` (new) ·
`web/lib/loadCase.ts` (new) · `web/lib/store.ts` (new) · `web/components/AppShell.tsx` (new) ·
`web/components/Header.tsx` (new) · `web/components/StageRail.tsx` (new) ·
`web/components/MapView.tsx` (new) · `web/components/ContextPanel.tsx` (new) ·
`web/components/TimeSlider.tsx` (new) · `web/components/LayerToggles.tsx` (new) ·
`web/app/page.tsx` (modified) · `web/app/layout.tsx` (modified) · `web/app/globals.css` (modified)

**Run command:**
```bash
robocopy cases web\public\cases /MIR   # refresh the bundle copy (already present)
cd web && npm run dev                   # open http://localhost:3000
```
Expected output: SAR scene on the map between 80.1–80.7 E / 12.95–13.55 N, two polygons
(det-01 red solid, det-02 grey dashed), SAR/Detections toggles work, clicking det-01 fills the
right panel with classification=oil, confidence 87%, area 12.4 km², etc.

**Checkpoint artefact:** `npm run lint`, `npx tsc --noEmit`, and `npm run build` all pass
(`/` route 4.78 kB, compiled + static). Dev server compiles `/` clean. Screenshot / on-map
visual check still TODO — post in group after opening it on the demo laptop.

**Open issues:**
- Client-side map render (MapLibre WebGL: SAR raster placement, polygon click) not yet verified
  in a browser — only compile/build. Needs an eyeball on localhost:3000.
- `next build` needs a clean `.next` and no running `next dev` on Windows, or it EPERM-locks on
  `.next/trace`. Stop the dev server before building.
- maplibre-gl is v6 (ESM, named exports only — no default import). Note when copying snippets
  from older docs.
- Time slider is intentionally inert this phase; `tNorm` is in the store awaiting Phase 2.
- deck.gl is installed but not wired yet — lands in Phase 2 with the particle ScatterplotLayer.

**Next:** Phase 2 — time slider bound to `t`, deck.gl ScatterplotLayer reading
`particles.positions[t]` loaded once into memory, play/pause auto-scrub, smoothness checkpoint.
