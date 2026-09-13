# verification/ — Stage 4 content, hand-authored

`verification.json` is not produced by a pipeline stage. It is **research and prose**, written by
hand per case (Master Plan Phase 4, `docs/team/akshat-integration.md` Part 4). This directory holds
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

## ⚠️ Timing: do NOT write these early — a verification.json IS the answer

**This file ships inside the bundle, where everyone can read it.** The moment
`verification/case-jacksonville-2024.json` names a vessel, the blind evaluation is over for that
case: Jaiveer can read the answer he is supposed to be deriving (Master Part 16, D21).

So the sequence is not negotiable:

1. The case is exported and announced. **No verification file exists yet.**
2. Soum, Anushka and Jaiveer produce their stages **without** it.
3. The bundle validates.
4. *Then* Akshat writes `verification/<case-id>.json`, adds `"verify"` to `acts_available`, and
   rebuilds.

The research does not have to wait — it is already done and staged in the sealed
`docs/ANSWERS.md`. What waits is writing it into a file the team can read.

**Currently present:** `case-huntington-2021.json` only, and that one is safe to hold early
because its finding is an NTSB report about *infrastructure* — its conclusion is that **no vessel
was the proximate source**, so it gives away no attribution.

## Known-source cases (D16)

When a case has no SAR-visible slick and runs `trace`/`verify` seeded from `meta.known_origin`,
the Verify screen must state plainly that the origin was a **documented source, not a NAAP
detection**. Put that in `official_finding.caveat`, and make the `assessment.explanation` say what
the trace actually demonstrated (a physics reconstruction / sanity-check against the known
position and time), not an attribution result. **No case in the current library uses this path** —
Golden Ray is dropped (D17) and Ennore 2017 is archived (D18, D25).

## Cerulean-sourced cases (1, 2, 4, 5)

`source_type` is **`algorithmic_attribution`**, never `official_investigation`. The wording is
*"SkyTruth Cerulean attributed this slick to vessel X"* — it is another algorithm's output with
analyst review, not a court finding, and a judge may well probe the difference.

## Jamnagar (case 6) — where the finding is an absence

`official_finding` records the absence **explicitly** rather than being left empty, and it must be
precise: no investigation, no named party, no enforcement. **Not "no record anywhere"** — Cerulean
logged this slick and a judge can pull up their record in ten seconds (D24). Their detection is
corroboration that the slick is real; what is missing is anyone acting on it. Expected verdict
`not_applicable`; `what_would_have_helped` is published Indian coastal AIS.

## Schema

`docs/00_MASTER_PLAN.md` §6.8. The validator (`check_verification`) enforces: the three top-level
objects, `verdict` in the four allowed values, `source_url` present and non-empty, and a
non-empty `explanation`. Missing `volume_reported` / `caveat` are warnings.

## Every source URL also goes in `docs/receipts.md`

That is the file opened when a judge asks "is this real?".
