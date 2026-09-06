# HARSHITA — The Frontend
*Read with 00_MASTER_PLAN.md. You own the entire judge-facing application. This is the largest single body of work in the project and the thing judges stare at for five minutes — it is a first-class deliverable, not a wrapper. You build against fake data from hour one and never wait for anyone.*

## You produce
`web/` — the complete app: map, five layers, time slider, stage rail, context panels, funnel, case switcher, no-spill state. Plus (before freeze) the recorded fallback video.

## You consume
`/cases/<id>/` bundles only — starting with fake `case-000` today. **You never call Python. You fetch static JSON.** If a file or field is missing or malformed, that's a contract bug: show a visible error and message Akshat; do not silently patch data in the frontend.

## Tools
Antigravity (you get most of the team's accounts) for generation; your Claude Pro for debugging map/animation issues (that's where generated code most often needs real help). Urooz pairs with you ~2 h/day on styling — you own structure and behaviour, she owns look.

## Stack (fixed — don't relitigate)
Next.js 14 (or Vite+React if Next fights you — your call, decide Sun, don't switch later) · **MapLibre GL JS** (no token needed) · **deck.gl** ScatterplotLayer (particles) + HeatmapLayer (origin) via `@deck.gl/mapbox` overlay · Tailwind · Recharts (feature bars) · Zustand for state (activeCase, activeStage, t, layer toggles). No Redux. **No localStorage** — state in memory.

## The screen (from Master + the agreed mockup)
Header: case title + case switcher tabs · Left rail: three stage dots (Detect / Trace / Attribute) — active, available, and unavailable states (`meta.acts_available`; unavailable = greyed with tooltip "no free AIS for Indian waters") · Centre: map · Right: context panel swapping per stage · Bottom: time slider (T−24h → T−0) + five layer toggles (SAR, Detections, Particles, Origin, Vessels).

---

## Phase 1 — TODAY (~5 h)
1. App scaffold, load `cases/case-000/meta.json` + `bounds.json` + `sar.png`.
2. MapLibre map (dark basemap style from a free tile source, or plain dark background — the SAR raster is the real backdrop) with the PNG as an `image` source pinned to bounds. Layer toggle machinery.
3. `detections.geojson` rendered: oil = red outline, look-alike = grey dashed (Urooz will refine tokens). Click a polygon → store selected detection.
**Checkpoint:** screenshot in group — SAR image on map, two fake polygons, toggles working.

## Phase 2 — Mon (~5 h) · THE DAY THAT DECIDES THE PROJECT
1. Time slider bound to `t` in the store (0…n_steps−1).
2. deck.gl ScatterplotLayer reading `particles.positions[t]` — **load positions once into memory (consider Float32Array conversion), never re-fetch or re-parse on scrub**. Update via layer `data`/`updateTriggers` on t change.
3. Play/pause auto-scrub (~8× real time) plus manual drag.
**Checkpoint (the project's most important):** scrubbing 3000×96 fake particles is visually smooth on your laptop AND one weaker laptop. If it stutters: decimate to every 2nd timestep, drop to 2000 particles, ensure no per-frame allocation. Both fixes are invisible to a viewer. Report the result either way — finding a problem today is a win, not a failure.

## Phase 3 — Tue (~5 h)
1. Origin HeatmapLayer from `origin.json` (grid → weighted points; fade in as t approaches max rewind). 50%/90% radius circles.
2. Right panel, stage-aware: **Detect** = object card for selected detection (classification badge, confidence, area, elongation, edge gradient, contrast, shape class + Recharts horizontal feature bars — "why this classification"); **Trace** = origin card (centroid, radii, time window, ensemble runs) + the uncertainty note ("cloud widens with rewind depth").
3. Stage rail logic driven by `acts_available`.
**Checkpoint:** click-through video/gif of Acts 1+2 on case-000.

## Phase 4 — Wed (~4 h)
Swap in the real Ennore bundle the moment Akshat's integration lands (should be a data change only — that's the whole architecture). Polish for the HOD: loading states, empty states, the unavailable-Attribute tooltip. You drive the laptop at the HOD demo if Akshat wants a second pair of hands.

## Phase 5 — Event days
1. Vessels layer: LineString tracks from `vessels.geojson`, highlight on suspect hover.
2. **Attribute panel:** funnel (static, from `suspects.funnel` — a simple 4-bar/step graphic, no animation needed), ranked suspect cards (score, closest approach, gap minutes, reasons list), and the exclusion card(s) — visually distinct (e.g. struck-through / muted with the stated reason).
3. Case switcher wired to all bundles; **no-spill state**: zero oil features → centre-map banner "No spill detected in this scene" + look-alikes shown grey. This is a designed state, not an error.
4. Record the fallback video (full demo run, screen capture, on the demo machine). Freeze with everyone else — nothing new in the last 12 h.

## Performance rules
Parse each bundle once, keep in memory · never mutate deck.gl data arrays in place without updateTriggers · no React re-render of the map container on t change (slider state → deck layer only) · test on the actual demo machine Tue night.

## Escalate (45-min rule)
deck.gl overlay refuses to sync with MapLibre · stutter survives both mitigations · any bundle file that doesn't match the contract.

## Definition of done
Mon stutter checkpoint passed and reported · Acts 1+2 polished for Wed morning · all three cases switchable with Attribute live on the US case by freeze · no-spill state works · fallback video recorded.
