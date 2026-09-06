# Akshat — update log

*Newest entry at the TOP. Format: `docs/updates/TEMPLATE.md`.*

---

## [2026-09-06] Phase 1 — repo skeleton, frozen contracts, case-000, stubs for every stage

**Done:** Turned 22 loose documents into the repo layout the docs describe. Contracts extracted
from Master §4 into `docs/CONTRACTS.md` and marked FROZEN. `case-000` generates and validates
clean (0 warnings). Every stage now has a working `--stub` that writes schema-valid output, so
the full Detect → Trace → Attribute chain runs end to end today, on garbage, before any real
logic exists. Added `scripts/test_validator.py` because the validator had never been proven to
catch anything — it now catches 6/6 deliberately broken bundles and names each fault. Python
3.11.9 + venv, deps pinned. GEE scripts written but NOT yet run (no auth).

**Files touched:** `docs/*` (moved, 22 files) · `CLAUDE.md`, `pipeline/*/CLAUDE.md`,
`web/CLAUDE.md` (new) · `docs/CONTRACTS.md`, `docs/receipts.md` (new) · `.gitignore`,
`requirements.txt`, `README.md` (new/rewritten) · `scripts/make_case000.py` (added `--case-id`,
`--scene-only`) · `scripts/test_validator.py`, `scripts/check_ennore.py` (new) ·
`pipeline/{detect,drift,attribute}/run.py` (new stubs) · `pipeline/export/build_case.py`,
`pipeline/export/gee_scene.py` (new) · `cases/case-000/` (output)

**Run command:**
```bash
python scripts/make_case000.py
python scripts/validate_case.py cases/case-000
python scripts/test_validator.py
```
Expected output: `PASS acts=['detect', 'trace', 'attribute'] (0 warning(s))`, then
`6/6 mutations correctly caught and named`.

Full seam test (all three stubs, publishing through the case folder between stages):
```bash
python scripts/make_case000.py --out cases/case-smoke --case-id case-smoke --scene-only
python pipeline/detect/run.py        --case case-smoke --stub
python pipeline/export/build_case.py --case case-smoke --stage detect
python pipeline/drift/run.py         --case case-smoke --stub
python pipeline/export/build_case.py --case case-smoke --stage trace
python pipeline/attribute/run.py     --case case-smoke --stub
python pipeline/export/build_case.py --case case-smoke
```
Expected output: `PASS`. Verified 2026-09-06.

**Checkpoint artefact:** `cases/case-000/` committed (8.4 MB, 8 files) — the thing everyone
builds against. Validator self-test output above.

**Open issues:**
- **Phase 0 is NOT done.** The Ennore scene has not been verified — needs GEE signup, a
  noncommercial/research project, and `earthengine authenticate`. `scripts/check_ennore.py` is
  written and syntax-checked but has never made a real API call. This is the go/no-go the whole
  plan keys off, and it is the 45-minute-rule risk item. **Do it first tomorrow morning.**
- `pipeline/export/gee_scene.py` likewise unrun. The `getThumbURL` path and the pixel-dimension
  arithmetic are untested against the real API; expect at least one round of fixing.
- **Contract addition, announced not yet acknowledged:** `bounds.json` now carries optional
  `db_min` / `db_max` (the dB clamp). Reason in `docs/CONTRACTS.md` §3 and `docs/TRAPS.md` #7 —
  Soum reads the 8-bit PNG back to decibels and must use the same clamp. Additive only;
  consumers default to [-25, 0] when absent. Needs broadcasting to the group.
- Environment deviates from the frozen convention in one place: **Node 24** is installed, not
  Node 20 LTS. Harshita's lane only. Worth a decision before she scaffolds `web/`.
- `build_case.py --stage <act>` was added mid-session and is not in any personal doc: the case
  folder is the hand-off medium, so Stage 2 cannot read Stage 1 until Stage 1 is published into
  the case folder. Mention it at the sync so nobody rediscovers it.

**Next:** GEE auth → `check_ennore.py` → record the scene id in `docs/receipts.md` → export
`sar.png` + `bounds.json` for Ennore and hand to Soum (Handoff #2, due Mon evening).
