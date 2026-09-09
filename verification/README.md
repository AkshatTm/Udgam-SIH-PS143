# verification/ — Stage 4 content, hand-authored

`verification.json` is not produced by a pipeline stage. It is **research and prose**, written by
hand per case (Master Plan Phase 4, `docs/01_AKSHAT_INTEGRATION.md` Part 4). This directory holds
the source files; `build_case.py` copies `verification/<case-id>.json` into
`cases/<case-id>/verification.json` when `verify` is in `acts_available`.

## Workflow per case

1. `cp verification/TEMPLATE.json verification/<case-id>.json`
2. Go to the **primary source** (the NTSB/USCG report itself, not a news summary). Fill
   `official_finding` — especially `caveat`, which often carries the whole case.
3. Run the stages. Fill `naap_result` from the **actual output files**, not memory.
4. Write `assessment` by hand. `verdict` ∈ `hit | partial | miss | not_applicable`.
   **Never generate the `explanation`.** A `miss` with a clear "why" ships as readily as a `hit`.
5. Add `"verify"` to `meta.json`'s `acts_available`, then
   `python pipeline/export/build_case.py --case <case-id>`.

## Schema

`docs/00_MASTER_PLAN.md` §6.8. The validator (`check_verification`) enforces: the three top-level
objects, `verdict` in the four allowed values, `source_url` present and non-empty, and a
non-empty `explanation`. Missing `volume_reported` / `caveat` are warnings.

## Every source URL also goes in `docs/receipts.md`

That is the file opened when a judge asks "is this real?".
