# Harshita — update log

*Newest entry at the TOP. Copy the block from `TEMPLATE.md`, fill four lines, commit it with
your code in the same push. Two minutes after each phase — non-negotiable.*

**Why:** your AI has no memory between chats. This file is the memory. It means you can close a
chat, switch from Claude to ChatGPT, hand your work to someone else, or come back after sleeping,
and lose nothing.

**To resume from it:** *"Here are the master plan, my task document, and my update log. Read the
top entry and tell me exactly where I left off and what the next step is."*

---

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
