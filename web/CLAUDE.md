# Frontend — Harshita

Owns the entire judge-facing app. Full brief: `docs/04_HARSHITA_FRONTEND.md`. Integration duties: `docs/05_HARSHITA_INTEGRATION.md`.

## Non-negotiable
- **NEVER use localStorage or sessionStorage.** State lives in memory (Zustand).
- **The frontend never calls Python.** It fetches static JSON from `cases/<id>/`. If a field is missing or malformed, show a visible error and tell Akshat — do not patch data client-side.
- Stack is fixed: Next.js + MapLibre GL JS (no token) + deck.gl (ScatterplotLayer for particles, HeatmapLayer for origin) + Tailwind + Recharts + Zustand. Decide Next vs Vite on day one and never switch.
- `meta.acts_available` drives the stage rail. A missing act is a greyed stage with a tooltip, not a crash. Ennore has no `attribute`.
- Zero oil features in `detections.geojson` is the **no-spill case** — a designed state with a banner, not an error.

## Performance (the demo lives or dies here)
- Parse each bundle **once** into memory; consider Float32Array for particle positions.
- Scrubbing must not re-fetch, re-parse, or re-render the map container. Slider state feeds the deck layer only, via `updateTriggers`.
- No per-frame allocation in the animation loop.
- Test the full 3000 particles x 97 steps on the actual demo machine, not just yours.

## Escape hatches if it stutters (both invisible to a viewer)
Decimate to every 2nd timestep · drop to 2000 particles. Never change the schema.

---

## Getting the bundles in front of the app
`web/public/cases/` is gitignored — it is a copy, not a source. Refresh it from the repo root
whenever a bundle changes:

```powershell
robocopy cases web\public\cases /MIR      # Windows
```
```bash
rsync -a --delete cases/ web/public/cases/   # macOS/Linux
```

Then fetch `/cases/case-000/meta.json`. The bundle shapes are frozen in `docs/CONTRACTS.md` —
that file, not the sample data, is the source of truth for what a field means.
