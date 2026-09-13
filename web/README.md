# `web/` — the Naap interface

The judge-facing application. **Owner: Harshita.**

One map screen with a scrubbable time slider; the four pipeline stages are layers on it. Drag the
slider backwards and the slick dissolves into particles drifting back toward their origin.

Brief: [`../docs/team/harshita-frontend.md`](../docs/team/harshita-frontend.md) ·
Integration: [`../docs/team/harshita-integration.md`](../docs/team/harshita-integration.md) ·
Rules for working in here: [`CLAUDE.md`](CLAUDE.md)

---

## The one architectural rule

**The frontend never calls Python.** It fetches static JSON from `cases/<id>/` and renders it.

There is no API, no server-side rendering of case data, and no runtime network dependency — local
fonts, no basemap tiles, static JSON. **The app runs with the wifi switched off**, which is why it
does not break in a venue.

If a field is missing or malformed, show a visible error and report it. **Do not patch data
client-side** — that turns a pipeline bug into an invisible pipeline bug.

## Stack

Next.js 14 (App Router) · MapLibre GL JS (no token) · deck.gl · Tailwind · Recharts · Zustand.
Node 20 LTS.

Two choices worth knowing about because they are rulings, not preferences:

- **`BitmapLayer` for the origin grid, never `HeatmapLayer`** (decision D11). HeatmapLayer
  re-smooths in screen pixels and renormalises per viewport — the answer would change as a judge
  zooms.
- **No `localStorage` or `sessionStorage`.** State lives in memory, in Zustand.

## Running it

```bash
# from the repo root — web/public/cases/ is a gitignored copy, not a source
python scripts/sync_web_cases.py --clean

cd web
npm ci
npm run dev            # development
npm run build && npm run start   # production — this is what the demo runs
```

`predev`/`prebuild` vendor the MapLibre worker out of `node_modules` via
`scripts/copy-maplibre-worker.mjs`, so the app has no CDN dependency at runtime.

**Never `npm run dev` in front of judges.** Demo procedure:
[`../docs/operations/demo-runbook.md`](../docs/operations/demo-runbook.md).

Re-run the sync after **every** change to `cases/`. A bundle that changed in `cases/` but was not
synced shows stale data rather than an error.

## Layout

```
app/
  page.tsx                    gallery
  case/[id]/page.tsx          the case workspace
  case/[id]/[stage]/page.tsx  deep link to one stage
components/
  MapView.tsx        the map and every deck.gl layer
  CaseWorkspace.tsx  the screen that composes everything
  StageRail.tsx      detect / trace / attribute / verify, driven by meta.acts_available
  TimeSlider.tsx     the scrub control
  ContextPanel.tsx   suspects, components, funnel, exclusions
  VerifyScreen.tsx   our answer against the official finding
  VerdictBadge.tsx   hit / partial / miss, rendered with equal confidence
  Gallery.tsx  FlowBar.tsx  LayerToggles.tsx  NoSpillBanner.tsx  ...
lib/
  loadCase.ts  bundleCache.ts  cases.ts     fetching and caching
  contracts.ts                              the bundle types
  detections.ts particles.ts origin.ts
  vessels.ts    suspects.ts   verification.ts
  usePlayback.ts timestep.ts  useIdleReset.ts
  store.ts                                  Zustand
```

`lib/contracts.ts` mirrors the frozen schemas. **[`../docs/00_MASTER_PLAN.md`](../docs/00_MASTER_PLAN.md)
Part 6 is the source of truth for what a field means** — not the sample data, and not this file.
Letting the two drift once already cost the interface five fields it was supposed to render.

## Rendering rules that are honesty requirements

These are not styling choices. Each one exists because the alternative would misrepresent a
result.

- **`null` renders as "n/a", never as a zero bar.** On a `gfw_hourly` case (Mumbai, Jamnagar) the
  `gap` and `slowdown` components are structurally unmeasurable and arrive as `null`. A zero bar
  would assert a measurement nobody made.
- **`time_window_method: "bounded"` is a search bracket, not a measured release time**, and must
  render differently from `"convergence"` (decision D12).
- **`closest_km` is distance to the origin-grid peak**, not "closest approach" to the centre of
  the rings, and is labelled that way (D36).
- **Zero oil features is the no-spill case** — a designed state with a banner, not an error.
- **A missing act is a greyed stage with a tooltip, not a crash.** `meta.acts_available` drives
  the rail, and the rail must look deliberate when stages are absent.
- **The case list is never hardcoded.** It comes from `cases/index.json`.

## Performance

The demo lives or dies here.

- Parse each bundle **once** into memory.
- Scrubbing must not re-fetch, re-parse, or re-render the map container. Slider state feeds the
  deck layer only, via `updateTriggers`.
- No per-frame allocation in the animation loop.
- Test the full particle count × 97 steps on the **actual demo machine**, not a dev laptop.

If it stutters, two escape hatches are available and both are invisible to a viewer: decimate to
every second timestep, or drop the particle count. **Never change the schema.**
