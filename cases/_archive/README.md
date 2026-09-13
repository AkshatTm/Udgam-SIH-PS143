# `cases/_archive/` — retired cases

Nothing in here is in `cases/index.json`, nothing in here is validated by
`scripts/validate_case.py cases/`, and nothing in here reaches the demo. A case lands here when it
has been dropped from the library but still has a reason to exist on disk.

---

## `case-ennore-2017` — archived, not deleted (Master Plan D18, D25)

**Why it left the library.** Our GRD probe through GEE found no coherent VV/VH damping on the
29 Jan 2017 dawn pass — imaged +1 day after the collision, low wind, sheltered water. The case was
scaffolded as a trace-without-detect bundle seeded from `meta.known_origin` (D16).

**Why it is not deleted.** Dasari, Lokam & Nadimikeri, *Marine Pollution Bulletin* 174(1):113182,
DOI `10.1016/j.marpolbul.2021.113182`, report **detecting this exact spill in Sentinel-1A, visible in
the VV channel, using Level-1 SLC data.**

> **We cannot ship a "no SAR-visible slick" claim that contradicts published literature.**

**What would bring it back.** Read the paper's figure and its scene id first, then test the three
explanations in order:

1. **Product** — they used SLC, we used GRD. SLC preserves phase and full resolution; GRD is
   multi-looked and detected. This is the most likely answer and it needs a Copernicus Data Space
   account, which nothing else in the project requires.
2. **Scene** — four Sentinel-1 passes exist in the window. We probed
   `S1A_IW_GRDH_1SDV_20170129T003132_20170129T003157_015039_01892E_6D04`. Theirs may be another.
3. **Location** — we may have sampled the wrong part of the scene.

If any of those turns up the slick, move the folder back to `cases/`, add it to `index.json`, and the
case returns as a detection case rather than a known-origin one.

**The rule it produced, which outlived it:**
> Before claiming any negative result about a documented incident, check whether someone has already
> published a positive one.

**Still open inside the bundle** — the `known_origin` pin is an approximation off the port entrance
and is flagged as such in `meta.json`. Pin it from the DG Shipping / MoEF enquiry or the INCOIS OSDAG
report before this case ever ships, and fill the `source_url` and volume TODOs in
`verification.json`.

---

## `case-golden-ray-2021` — deleted, not archived (D17)

Not here, and deliberately. No SAR-visible slick, and it made the same infrastructure point that
Huntington Beach makes better — Huntington has NTSB MIR-24-01 behind it. Two cases proving one thing,
where one of them has nothing to show, is a wasted slot. `git log` has it if it is ever wanted back.
