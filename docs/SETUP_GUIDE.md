# SETUP — do this before you write a line of code
*Target: everyone operational in under 45 minutes. If any step takes longer than 45 minutes, stop and message Akshat (the 45-minute rule applies to setup too).*

---

## Everyone — 15 minutes

**1. Repo**
```bash
git clone <repo-url> naap && cd naap
git checkout -b <yourname>          # akshat / soum / anushka / harshita / jaiveer / urooz
```

**2. Python** (skip if you're frontend-only)
```bash
python3.11 -m venv venv
source venv/bin/activate            # Windows: venv\Scripts\activate
pip install -r requirements.txt
```
If `python3.11` doesn't exist, 3.10 or 3.12 are fine — but tell the group which you're on, so a version-specific bug is diagnosable.

**3. Read, in this order:** `docs/00_MASTER_PLAN.md` §2–4 (architecture + contracts) → your personal doc → `CLAUDE.md` → `docs/TRAPS.md`. Twenty minutes, and it prevents the whole category of "I built it against the wrong shape."

**4. Prove your environment works**
```bash
python scripts/make_case000.py
python scripts/validate_case.py cases/case-000
```
Must print `PASS`. If it doesn't, your environment is broken and nothing else you do today is trustworthy.

---

## Google Earth Engine — Akshat, Anushka, Soum

Only these three touch GEE. Everyone else can skip.

1. Sign up at `earthengine.google.com` with your student Google account and register a **noncommercial / research** cloud project. Approval is usually minutes but has occasionally taken hours — **do this first, before anything else in your day**, so waiting doesn't block you.
2. ```bash
   pip install earthengine-api
   earthengine authenticate
   ```
   Browser opens, you paste a token back.
3. Verify:
   ```python
   import ee; ee.Initialize(project="<your-project-id>")
   print(ee.ImageCollection("COPERNICUS/S1_GRD")
           .filterDate("2017-01-28","2017-02-05")
           .filterBounds(ee.Geometry.Rectangle([80.0,12.9,80.8,13.6]))
           .size().getInfo())
   ```
   A number > 0 means Sentinel-1 covered Ennore in that window — **this is Akshat's Phase 0 go/no-go check.** Zero means widen the date range and tell Akshat immediately.

**Never commit credentials.** `~/.config/earthengine/` stays out of the repo.

---

## Frontend — Harshita (and Urooz for previewing)

```bash
cd web
npm install
npm run dev
```
Core deps: `maplibre-gl`, `deck.gl`, `@deck.gl/mapbox`, `@deck.gl/layers`, `zustand`, `recharts`, `tailwindcss`.

Serve the case bundles as static files — symlink or copy `cases/` into `web/public/cases/` and fetch from `/cases/case-000/meta.json`. Decide Next.js vs Vite today and never revisit it.

**First thing to render:** `sar.png` pinned to `bounds.json` on a MapLibre map. If that works, the hard part of the geospatial plumbing is done.

---

## Data downloads — start these NOW, they run unattended

| Who | What | Size | Where |
|---|---|---|---|
| **Soum** | Zenodo Part III — `zenodo.org/records/13761290` | 9.9 GB | `data/zenodo_p3/` |
| **Jaiveer** | NOAA Marine Cadastre AIS, a few days near your candidate case | ~1–3 GB/day | `data/ais/` |
| Soum (background, October) | Zenodo Part I — `zenodo.org/records/8346860` | 40.7 GB | external disk if needed |

Both Zenodo parts are single `.7z` archives — nothing is usable until the download completes, so start them before you do anything else. **Soum: check you have ~25 GB free before starting Part III** (archive + extraction coexist).

Everything under `data/` is gitignored. **Raw data never moves between laptops. Outputs move instead.**

---

## Sanity checklist — tick before you start Phase 1

- [ ] Repo cloned, your branch created, first push done (even if empty)
- [ ] `make_case000.py` + `validate_case.py` both run and print `PASS`
- [ ] You have read the contracts section and can say what your component outputs
- [ ] Your AI has been given the master plan + your personal doc
- [ ] `docs/updates/<yourname>.md` created with a first "setup done" entry
- [ ] Downloads started (Soum, Jaiveer)
- [ ] GEE verified (Akshat, Anushka, Soum)

---

## Demo machine — decide by Tue 8

One laptop is the demo machine (Akshat's or Harshita's). By Tuesday night it must have: the repo cloned, Python and Node environments working, all case bundles present, the app running offline, and the browser bookmarked. **Never present from a laptop the app has never run on.** At freeze it checks out the `demo` branch and nothing else.

## Backups — end of every day
Zip `cases/` and push to Google Drive. It's a few MB and it's the only artefact that cannot be regenerated quickly if a laptop dies.
