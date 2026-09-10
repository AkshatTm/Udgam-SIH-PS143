# web/ — the Naap frontend

**Owner: Harshita.** Nothing here yet but the rules — the app itself is Phase 1 of
`docs/04_HARSHITA_FRONTEND.md`, and the framework decision (Next.js 14 vs Vite + React) is
yours to make on day one and never revisit.

## Start

```bash
cd web
# npx create-next-app@latest . --typescript --tailwind --app     (or: npm create vite@latest .)
npm install maplibre-gl deck.gl @deck.gl/mapbox @deck.gl/layers zustand recharts
npm run dev
```

## Get the case bundles served

`web/public/cases/` is a gitignored copy of the repo-root `cases/` directory. From the repo root:

```powershell
robocopy cases web\public\cases /MIR
```

Then fetch `/cases/case-000/meta.json` from the app.

## First thing to render

`sar.png` pinned to `bounds.json` on a MapLibre map. If that works, the hard part of the
geospatial plumbing is done — everything after it is layers on the same projection.

Read `CLAUDE.md` in this directory before writing code, and `docs/CONTRACTS.md` for what every
field in a bundle means. `cases/case-000/` is fake data in exactly the real shape; build the
whole app against it and swap in the real Ennore bundle when it lands, as a data change only.
