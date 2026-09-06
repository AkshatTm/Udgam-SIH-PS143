# UPDATE LOG — protocol and template
*Copy this to `docs/updates/TEMPLATE.md`. Each person keeps `docs/updates/<yourname>.md`. Newest entry at the TOP so a fresh chat reads current state first and can stop reading.*

## Why
Your AI has no memory between chats. This file is the memory. It means you can close a chat, switch from Claude to ChatGPT, hand your work to someone else, or come back after sleeping, and lose nothing. **Two minutes after each phase. Non-negotiable.**

## How to write one
Ask your AI at the end of a phase:
> Append an update-log entry for what we just did, using the template in docs/updates/TEMPLATE.md. Be specific about the run command and honest about what's still broken.

## How to resume
> Here are the master plan, my task document, and my update log. Read the log top entry and tell me exactly where I left off and what the next step is.

## Rules
- Newest first. Never delete old entries.
- **The run command must be real and pasteable.** If you can't paste it and have it work, the phase isn't done.
- Open issues are for things genuinely unresolved — an empty list on a phase that had problems is a lie your future self will pay for.
- Commit it with your code, same push.

---

# TEMPLATE — copy the block below

```markdown
## [YYYY-MM-DD HH:MM] Phase N — <short title>

**Done:** <2–3 sentences. What now exists that didn't before. Be concrete.>

**Files touched:** `path/one.py` (new) · `path/two.py` (modified) · `cases/case-xxx/file.json` (output)

**Run command:**
```bash
python pipeline/<x>/run.py --case case-ennore-2017
```
Expected output: <one line — what it prints or writes if it worked>

**Checkpoint artefact:** <plot / test result / screenshot — and where it is, e.g. "posted in group 21:10", "docs/img/quiver.png">

**Open issues:**
- <thing that is broken or unverified, and what you'd try next>
- <or: none>

**Next:** <the single next step>
```

---

# Worked example (Anushka, Phase 1)

```markdown
## [2026-09-07 22:40] Phase 1 — fake fields + known-answer tests

**Done:** Built `fields.py` with a `--fake` mode returning constant analytic current/wind, and
`step.py` with the RK2 integrator (velocity = current + 0.03*wind, dt = 15 min, vectorised over
an [n,2] lon/lat array). All four known-answer tests pass. No GEE involved yet.

**Files touched:** `pipeline/drift/fields.py` (new) · `pipeline/drift/step.py` (new) ·
`pipeline/drift/tests.py` (new) · `pipeline/drift/run.py` (new, --fake stub only)

**Run command:**
```bash
python -m pipeline.drift.tests
python pipeline/drift/run.py --fake --case case-000
```
Expected output: `4/4 tests passed`, then a schema-valid `particles.json` + `origin.json` of garbage.

**Checkpoint artefact:** test output pasted in group 22:35. Constant-current test lands at
18.02 km east (target 18.0).

**Open issues:**
- Test 2 (round trip) returns within 0.31 km, not 0.0 — expected from RK2 truncation error, but
  worth re-checking once real fields are in; if it grows past ~1 km something else is wrong.
- Haven't decided yet whether to cache GEE fields as .npz or .zarr. Going with .npz, simpler.

**Next:** Phase 2 — HYCOM + ERA5 loaders, remembering HYCOM bands are cm/s (divide by 100).
```

---

# Akshat's cross-team log — `docs/updates/_INTEGRATION.md`

Akshat additionally keeps one file recording every seam event, so the history of what broke between components is in one place:

```markdown
## [2026-09-08 19:20] First wiring attempt — Ennore

**Received:** detections.geojson (Soum, 18:40) · particles.json + origin.json (Anushka, 19:05)

**Validator:** FAIL — 2 errors.
- `particles.json/t0` was 2017-01-29T00:14:00 (naive). Anushka fixed 19:15, re-ran, PASS.
- `detections.geojson[1]` elongation 2.8 but shape_class "linear" — warning only, left as is.

**Verified by eye:** plotted particles[0] over detections — sits on the slick. Origin centroid
offshore, 11 km NE of the slick. Plausible.

**State:** cases/case-ennore-2017 PASSES with acts ["detect","trace"]. Loaded in Harshita's UI at
19:45, scrubs cleanly.

**Next:** no-spill bundle from Soum tomorrow; US case still waiting on the AIS file.
```
