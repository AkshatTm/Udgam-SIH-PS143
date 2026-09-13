# CLAUDE.md — repo root
*Claude Code reads this automatically. Antigravity/Codex users: paste it at the top of a new chat. Nested `CLAUDE.md` files in `pipeline/*/` and `web/` add role-specific rules on top of this one.*

## Project in five lines
Naap: oil spill detection → backward drift to origin → vessel attribution, from Sentinel-1 SAR + ocean/wind fields + ship AIS. SIH 2026, PS 26143. Demo is ONE map screen with a time slider; three stages are layers on it. **Final demo: 15 September, 17:00** (full chain, internal round). Work is organised in PHASES, not days — finish a phase, log it, move on. Full context: `docs/00_MASTER_PLAN.md`.

## Architecture rule that governs everything
**No module imports another module.** Each stage is a script that reads files from `cases/<case_id>/` and writes files back into it. The frontend fetches static JSON and never calls Python. If you are about to write `from pipeline.drift import ...` in detection code, stop — you have misunderstood the design.

## Frozen conventions — never violate, never "improve"
1. Coordinates are **`[longitude, latitude]`**, WGS84, always. Never `[lat, lon]`.
2. Timestamps are **UTC ISO 8601 with trailing `Z`**, timezone-aware. Naive datetimes are a bug.
3. Units: km, km², m/s, degrees clockwise from north. Coordinates rounded to 5 dp in JSON.
4. **`null` ≠ `0`.** A not-applicable score is `null`; a measured zero is `0`. On a `gfw_hourly` case the `gap` and `slowdown` components are structurally unmeasurable and must be `null` — a zero there is an honesty bug, and the validator now fails on it.
5. Python 3.11 + venv; Node 20 for `web/`. Pinned deps. **A new dependency is pinned with its justification written next to it, and announced to the group** — so every laptop installs the same thing.
6. File schemas live in `docs/00_MASTER_PLAN.md` Part 6 (§6.1–6.9) — the live contract the validator enforces. `docs/CONTRACTS.md` is the v1 record, kept for history. They are frozen. If something genuinely cannot be expressed, ask Akshat — do not extend a schema unilaterally.

## The case library and the sealed answers
Nine live cases in `cases/index.json`, presentation order, strongest first: seven satellite exports, then the two Zenodo Part III benchmark tiles (`provenance: "benchmark"`, real location, no acquisition time). `cases/_archive/` is retired work — not indexed, not validated. **Cases are named after places, never vessels** — naming a bundle after the ship that caused it hands away the answer. Every documented outcome lives in `docs/ANSWERS.md`, which is gitignored and held by Akshat alone (`docs/ANSWERS.README.md` explains why). If you come across attribution data — Cerulean's API returns it alongside the polygon — do not paste it into the repo or the group chat.

## Before you hand anything over
```bash
python scripts/validate_case.py cases/<case_id>
```
Must print `PASS`. It catches lat/lon swaps, naive timestamps, unit errors, dimension mismatches and funnel inconsistencies by name. **Fix failures in the producing code, never by hand-editing the bundle.**

## Working rules
- **Stub first.** Your first commit writes a schema-valid output file full of garbage. Wiring before logic.
- **Every handover includes one pasteable run command** that produces a valid output file.
- **45-minute rule.** Stuck on an external service (GEE, downloads, auth) for 45 minutes? Stop, message Akshat with what you tried, the exact error text, and a minimal repro. Push through everything else yourself.
- **Never invent data a judge could check.** No vessel name not in the real AIS file, no detection the detector didn't produce, no accuracy number not measured on a held-out split. Internals are binding — we defend these numbers in December.
- Branch per person; push daily; PR to `main`; Akshat merges.
- `data/` is gitignored. Large files never move between laptops — **outputs move, inputs stay put.**

## Token discipline (this is a shared, finite resource)
- **Fresh chat per bug.** Long threads resend the whole conversation every turn.
- Paste `docs/00_MASTER_PLAN.md` §3–4 + your personal doc at the start of a chat, then work. Don't re-paste them every message.
- Ask for **one file or one function** at a time, not "build the component".
- Paste the **error text and the relevant function**, not the whole file, not the whole repo.
- Prefer "here's the failing output, what's wrong" over "rewrite this".
- Reserve roughly half of Claude quota for the integration and debugging phases, where it is worth most. Use Codex/Antigravity for boilerplate and scaffolding.
- Full guidance: `docs/PROMPTING_PLAYBOOK.md`.

## After each phase
Append to `docs/updates/<yourname>.md` using the format in `docs/updates/TEMPLATE.md`. Four lines: what was done, files touched, exact run command, open issues. This is how another AI (or another person) resumes your work without you.

## Known traps
Read `docs/TRAPS.md` before debugging anything geospatial. HYCOM on GEE is a scaled int — divide by 1000. GeoJSON is lon-lat. Pixel (0,0) is top-left = (west, north). ERA5 wind is u/v components, not speed/direction.
