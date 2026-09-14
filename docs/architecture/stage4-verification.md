# Stage 4 — Verify

**Question:** was the system right, and how do we know?

**In:** the official investigation of record (NTSB, USCG, or a documented account), plus this
system's actual output files
**Out:** `verification.json`
**Source files:** `verification/<case-id>.json`, copied into the bundle by
`pipeline/export/build_case.py` when `verify` is in `acts_available`

---

## This stage is not a pipeline stage

`verification.json` is **not produced by code.** It is research and prose, written by hand, per
case. There is no `run.py` here and there should not be.

The reason is structural: this is the one place where the system's claim is checked against
external reality, and a generated check would be the system grading its own homework. The
`explanation` field is explicitly never generated.

```
1. cp verification/TEMPLATE.json verification/<case-id>.json
2. Go to the PRIMARY source — the NTSB/USCG report itself, not a news summary.
   Fill official_finding, especially `caveat`, which often carries the whole case.
3. Run the stages. Fill udgam_result from the ACTUAL output files, not memory.
4. Write `assessment` by hand. verdict ∈ hit | partial | miss | not_applicable.
5. Add "verify" to meta.json's acts_available, then rebuild the bundle.
```

---

## What it records

Three blocks (schema: [`../00_MASTER_PLAN.md`](../00_MASTER_PLAN.md) §6.8):

**`official_finding`** — the summary, the responsible parties, the citation, and the **caveat**.
`source_url` must be present and non-empty. `source_type` ∈ `official_investigation |
algorithmic_attribution | press | none`, and a SkyTruth Cerulean attribution is
`algorithmic_attribution`, **never** `official_investigation`. Those are different epistemic
objects and collapsing them would be the single easiest way to overstate this project.

The `caveat` field earns its place. On one case the anchor strike that caused the pipeline rupture
preceded the release by eight months, so **no vessel was the proximate source at detection time**.
Without that caveat on screen, the system's own answer looks like a miss when it is a hit.

**`udgam_result`** — origin summary, top suspects, whether the system abstained. Filled from the
output files, not from recollection.

**`assessment`** — the verdict and human prose explaining it, plus `what_would_have_helped`.

---

## A miss ships as readily as a hit

`verdict` ∈ `hit | partial | miss | not_applicable`, and all four render with the same confidence.

This is the point of having sealed the answers at all. A verification screen that only ever shows
hits is a restatement, not a check. **The cases the system got wrong are shown, with an
explanation of why** — which is the only version of this screen that is worth a panel's attention.

---

## The sealed answers

Every case has a documented outcome. All of them live in `docs/ANSWERS.md`, which is gitignored
and held by one person. [`../ANSWERS.README.md`](../ANSWERS.README.md) is committed in its place so
the team knows the file exists and who has it.

The reasoning is about tuning, not trust: if the person weighting attribution components knows
which vessel the answer names, they will tune until it ranks first. If the detector's author knows
where the slick is, they will lower the threshold until it appears. None of that is dishonesty —
it is what anyone does when the target is visible — but it turns *"our system identified the
vessel"* into *"we tuned it until it did"*.

Two working rules follow:

1. **Cases are named after places, never vessels.** A case id that names a ship hands over the
   answer in the folder name. Do not "fix" a geographic name back.
2. **Attribution data found by accident is not pasted into the repository or the group chat.**
   Cerulean's API returns the polygon and the attributed MMSIs in the same response;
   `scripts/fetch_cerulean.py` splits them.

### Timing matters

A `verification.json` **is** the answer, and it ships inside the bundle where everyone can read
it. The moment one names a vessel, blind evaluation is over for that case. So verification files
are written *after* Stage 3 has scored the case, not before — and several are deliberately held
back from the repository via `.git/info/exclude` until then.

---

## Blindness is declared per case, not claimed in general

**A blanket claim of blind evaluation would not survive one question from an informed panel, so
this project does not make one.** Master Plan §16.1 declares the status of every case
individually, including the two where blindness was compromised and how.

Both compromises were found and reported by the person they disadvantaged rather than buried, and
one of them was unavoidable: verifying AIS reporting density at a case's origin *requires*
identifying the vessel — the check and the answer are the same operation.

Where a case is not blind, the rule that still holds is stated precisely: **no weight or threshold
was set using it.** That is a narrower claim than "nobody has seen the answer", and it is the one
that is true.

This per-case declaration is the honesty rule applied to the project's own evaluation, and it is
worth more than a clean-looking blanket claim would be.
