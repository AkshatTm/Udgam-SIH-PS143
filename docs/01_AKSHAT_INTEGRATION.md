# AKSHAT — Integration, Contracts, Exporter, Deck
*Read with 00_MASTER_PLAN.md. You are the integrator: you own the seams, not any component. Your most valuable asset is SLACK — protect it by refusing extra tasks.*

## You produce
`docs/` contracts (frozen) · `/cases/case-000/` fake bundle · Ennore `sar.png` + `bounds.json` · `pipeline/export/` exporter · the integrated case bundles · `docs/receipts.md` · the deck narrative · the `demo` branch.

## You consume
Everyone's real files as they land (Tue evening), Ayushmaan's US-case shortlist (Mon), Urooz's design tokens.

## Tools
Claude Pro (both accounts — reserve ≥50% of quota for Tue–Wed wiring/debugging), Codex for boilerplate. AI writes all code; you make every judgement call (case choice, what to cut, whether an output is plausible).

---

## Phase 0 — TONIGHT (~1 h) · YOU with AI assistance
1. **Verify the Ennore scene.** GEE code editor or Python: filter `COPERNICUS/S1_GRD` to bounds ~(80.0–80.8 E, 12.9–13.6 N), dates 2017-01-28 → 2017-02-04, mode IW, polarisation VV. List scenes + dates. Record the `system:index` in receipts.md.
   - Scene within ~3 days of 28 Jan → green-light everything.
   - Only a later scene → still usable; the demo says "first available pass, N days after the incident" (that gap is literally why backtracking exists).
   - Nothing in 7 days → message me (Claude) before improvising; we re-plan to the US case as hero.
2. Ping Soum: download **Part III only** (9.9 GB). Ping Anushka + Harshita: start (their Phase 1s need no data).

## Phase 1 — Sun (~5 h) · AI codes, YOU review
1. **Repo skeleton** per Master §7, `.gitignore`, `README.md` with §3 conventions pasted at top, pinned `requirements.txt` (numpy, scipy, rasterio, geopandas, shapely, opencv-python, scikit-image, scikit-learn, earthengine-api, duckdb, pyarrow).
2. **Freeze the contracts**: copy Master §4 schemas into `docs/CONTRACTS.md`. Announce in the group: frozen. Changes only through you, broadcast immediately.
3. **case-000 generator** (`scripts/make_case000.py`): writes a complete fake bundle — grey noise `sar.png` (1400²), plausible bounds near Ennore, 2 fake detections (one oil-linear, one lookalike-blob), random-walk `particles.json` (3000×97 — full size, so Harshita's Mon stutter test is honest), gaussian-blob `origin.json`, 5 fake vessel tracks, fake `suspects.json` with funnel + 1 exclusion. Generator script, not hand-typed JSON — you'll regenerate when tweaking.
4. **Validator** (`scripts/validate_case.py <case_dir>`): asserts schemas, lon-lat order (lon must be ~80 not ~13 for Ennore!), value ranges, timestamps parse as UTC. **This script is your integration insurance — everyone runs it before handing anything to you.**

## Phase 2 — Mon (~5 h) · AI codes, YOU eyeball output
1. **GEE export** (`pipeline/export/gee_scene.py`): select the Ennore scene, VV band, clamp dB to [-25, 0], scale to 8-bit, export ~50–100 m/px (keeps PNG a few MB; do NOT fight 10 m full-res), write `sar.png` + `bounds.json`. Sanity: open the PNG — coastline visible top-left/west side, sea speckled grey, any slick a dark streak. If the image is blank/black, the dB clamp is wrong.
2. Hand to Soum. Exporter skeleton: `build_case(case_id)` that currently just copies stage outputs into `/cases/<id>/` and runs the validator.

## Phase 3 — Tue (~6 h)
1. Make the exporter real: gather `detect/out/`, `drift/out/`, (later `attribute/out/`) → bundle → validate.
2. **First wiring attempt the moment Soum's and Anushka's real files land.** Expected bug classes: lon-lat swaps (validator catches), timestamps off by hours (compare meta vs particles t0), particles seeded off the polygon (plot detections + particles[0] together — they must overlap), origin cloud on land (bounds/indexing bug in origin.json).
3. Anything broken → back to the owner same evening with the validator error. You do not fix their component; you prove where the seam broke.

## Phase 4 — Wed (~6 h)
Morning: full Acts 1+2 on Ennore in the browser. Run through Harshita's UI end to end twice. Afternoon: rehearse the HOD script (below). **HOD demo.**

## Phase 5 — Event days
US case bundle (Soum + Anushka rerun their stages; Jaiveer's files land; you assemble) · no-spill bundle (Soum picks a Part III look-alike scene; trivial once the exporter works) · `receipts.md` complete · **freeze 12 h before judging**: create `demo` branch, install on demo machine, run all cases, Harshita records fallback video · two timed rehearsals with someone playing hostile judge.

---

## HOD demo script (Wed, ~4 min)
1. Hook (20 s): the real Ennore SAR scene. "Jan 2017, two tankers collided off Ennore. This is the actual radar pass."
2. Act 1 (60 s): detection outlines appear; open the object card; feature bars; show one look-alike correctly grey.
3. Act 2 (90 s): drag the slider; particles unwind; cloud widens — "we give a probability field, not a point, because that's what the physics supports." Quote the time window. **Hand the HOD the mouse.**
4. Close (45 s): "INCOIS models where oil goes; nobody models where it came from. Stage 3 — matching this origin against ship transponders — is what we complete at the internal round." Roadmap framing, not apology.

## Q&A you must have cold (25 s each)
"Is this real data?" → GEE scene ID + incident reports, one click away in receipts.md. · "How accurate is detection?" → Soum's held-out precision/recall, stated plainly + why look-alikes are an open research problem (~53% IoU is the published deep-learning benchmark). · "Why no ship yet?" → free historical AIS exists for US waters, not Indian — that gap is part of our pitch; full chain on the 11th. · "What if you accuse an innocent ship?" → ranked leads + explicit exclusions + human investigator; nothing automatic.

## Your cut order if time collapses (cut top-down)
1. Second US-case polish → 2. no-spill case → 3. funnel animation (static image) → 4. anything of yours except integration and rehearsal. **Never cut: the Wed rehearsal, the freeze, the fallback video.**

## Definition of done
`validate_case.py` passes on every shipped bundle · Acts 1+2 run on Ennore Wed morning · full chain on US case by freeze · receipts.md complete · demo branch frozen and running on the demo machine · fallback video exists.
