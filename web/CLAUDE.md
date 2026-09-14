# Frontend — Harshita

Owns the entire judge-facing app. Full brief: `docs/team/harshita-frontend.md`. Integration duties: `docs/team/harshita-integration.md`.

## Non-negotiable
- **NEVER use localStorage or sessionStorage.** State lives in memory (Zustand).
- **The frontend never calls Python.** It fetches static JSON from `cases/<id>/`. If a field is missing or malformed, show a visible error and tell Akshat — do not patch data client-side.
- Stack is fixed: Next.js + MapLibre GL JS (no token) + deck.gl (ScatterplotLayer for particles, **BitmapLayer** for the origin grid — never HeatmapLayer, it re-smooths in screen pixels and renormalises per viewport so the answer changes as a judge zooms, ruling D11) + Tailwind + Recharts + Zustand. Decide Next vs Vite on day one and never switch.
- `meta.acts_available` drives the **stage spine** (`components/StageSpine.tsx`, one top bar — it replaced the old `Header` + `FlowBar` + `StageRail`, which all showed the same position). A missing act is a greyed, inert step with its reason as a tooltip, not a crash, so the spine must look deliberate with stages missing. The navigation rules are pure functions in `lib/flow.ts` (`stepTarget`, `navigableStages`, `primaryAction`) — change them there, not in the component.
- `meta.ais_source` is `noaa_dense | gfw_hourly`. On a `gfw_hourly` case (Mumbai, Jamnagar) the `gap` and `slowdown` component bars are **`null`, and `null` renders as "n/a", never as a zero bar**. That is an honesty requirement, not a styling choice (D20).
- `suspects.natural_seep` is an optional object (`flagged`/`source`/`note`), not a list. No case in the library currently sets it.
- Zero oil features in `detections.geojson` is the **no-spill case** — a designed state with a banner, not an error.

## Design system — read before adding any colour or size
`app/globals.css` holds every token; `tailwind.config.ts` exposes them. Two rules:

1. **An interface colour is a map colour.** `--drift` is particles AND a running stage AND the
   active step; `--oil` is an oil detection; `--contact` is a radar contact / confirmed match;
   `--reject` is a look-alike or an excluded vessel; `--infra` is fixed infrastructure. The same
   hexes live in `MapView.tsx` as deck.gl arrays. Never introduce a colour that means something
   only in the panel — a judge should not have to learn two vocabularies.
2. **Never write a raw hex or a raw px font-size in a component.** Use the tokens and the
   `.t-display / .t-headline / .t-title / .t-subtitle / .t-body / .t-small / .t-label` scale.

Three traps that cost real debugging time here:
- Colour tokens are declared twice, as `--x-rgb: R G B` channels and as `--x: rgb(var(--x-rgb))`.
  Tailwind needs the channel form to build `bg-overlay/90`; hand it a finished `var()` and it
  emits **nothing at all**, which looks like a transparent panel, not like an error. Keep the
  two in step when you add a colour.
- **Restart the dev server after editing `tailwind.config.ts`.** Next does not pick it up on HMR
  and the failure is silent.
- `.anim-rise` sets `transform`, so it overrides Tailwind's `-translate-x-1/2`. Centre an
  animated overlay with `inset-x-0 mx-auto`.

Typeface is SF Pro Display when the machine has it, self-hosted Inter otherwise — one stack in
`--font-ui`, never a family name in a component. See `app/fonts/README.md`.

The home page (`components/Gallery.tsx`) is the only scrolling surface; it opts in with the
`udgam-scroll` class. Its WebGL background (`components/FlowField.tsx`) is home-page-only and
suspends off-screen, because deck.gl owns the GPU on every case screen.

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
