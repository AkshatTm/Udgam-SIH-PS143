## What this changes

<!-- One paragraph. What is different after this merges, and why. -->

## Run command

<!-- One pasteable line that produces a valid output file. Nothing is handed over without one. -->

```bash

```

## Checklist

- [ ] `python scripts/validate_case.py cases/` prints **PASS**
- [ ] `python scripts/test_validator.py` passes
- [ ] Any failure was fixed **in the producing code**, not by hand-editing a bundle
- [ ] Coordinates are `[lon, lat]`; timestamps are UTC ISO 8601 with a trailing `Z`
- [ ] A not-applicable score is `null`, not `0`
- [ ] Any new dependency is **pinned** with its justification written next to it, and announced
- [ ] `docs/updates/<yourname>.md` has an entry for this phase
- [ ] No vessel name, MMSI, IMO or attribution data that belongs in the sealed answers
- [ ] No credential, `.env`, or anything under `data/` beyond what is deliberately un-ignored

## Numbers

<!-- If this PR changes a reported figure, name the figure, its new value, its sample size,
     its split, and the file that is the receipt for it. If it changes none, write "none". -->

none
