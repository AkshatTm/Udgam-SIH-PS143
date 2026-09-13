# Stage 3 — Attribution

**Question:** given where and when the oil entered the water, what put it there?

**In:** `origin.json`, `detections.geojson`, vessel AIS (NOAA Marine Cadastre or GFW)
**Out:** `vessels.geojson`, `suspects.json`
**Code:** `pipeline/attribute/` · **Brief:** [`../team/jaiveer-stage3-attribution.md`](../team/jaiveer-stage3-attribution.md)

```bash
python pipeline/attribute/run.py --case <case-id>
```

This is the stage the problem statement is named after, and the one that produces an output a
person can act on. It is also the stage where being wrong is most expensive, because being wrong
here means **naming an innocent ship**.

---

## Before naming a ship, ask whether a ship is the right kind of answer

A system that can only consider vessels **will name a vessel even when the source is a pipeline.**
That is a false accusation, and it is the worst failure mode in the project. So source
classification runs *before* attribution:

```
origin reconstructed
  → fixed infrastructure at the origin?   → infrastructure
  → known natural seep area?              → natural_seep
  → radar ship with no AIS?               → dark_vessel
  → otherwise, score the AIS fleet        → vessel
```

`source_type` ∈ `vessel | dark_vessel | infrastructure | natural_seep`.

The payoff is concrete. On a case whose source is a seabed pipeline, a vessel-only system's best
possible answer is "no vessel responsible", which reads as failure. With source classification the
answer is *"the source is fixed infrastructure and all transiting vessels are excluded"* — which
is a hit, and is what the federal investigation concluded (decision D10).

`natural_seep` exists because a system that cannot say *"some of this may be geological"* will
always name a culprit, and telling seeps from discharges is a real enforcement problem (D19). It
is implemented in the schema and the scorer but **is not claimed on any case in the library** —
the one candidate could not be substantiated against a citable source, and an unsourced flag does
not go on a screen. It ships as designed capability with an honest "not triggered on these
scenes".

---

## The funnel

Every case publishes how the candidate set narrowed, and the counts must decrease monotonically:

```
in_region  →  in_window  →  plausible  →  scored
```

plus `dropped_short_track`. This is what turns "here is a ship" into "here is a ship, out of 412
that were in the box, 63 that were there at the right time, and 12 that were plausible". The
validator enforces monotonicity.

---

## Component scoring

Seven components, weighted, with the weights as named constants at the top of
`pipeline/attribute/score.py`:

| Component | Weight | What it asks |
|---|---|---|
| `proximity` | 0.30 | Origin-grid probability density the vessel touched |
| `parity` | 0.15 | Does the track run *along* the slick, or across it? |
| `temporality` | 0.15 | How close in time to the release window? |
| `trajectory` | 0.15 | Is the heading consistent with being the source? |
| `gap` | 0.15 | AIS silence overlapping the window |
| `slowdown` | 0.05 | Unusual slowdown near the origin |
| `type_prior` | 0.05 | Tanker/cargo over ferry |

**Proximity scores the grid, not a circle.** The maximum grid value the vessel touches during the
window *is* the proximity score — the grid is normalised to peak 1.0, so no further scaling is
needed. Scoring an r50 circle instead would discard the 44.7% of high-probability mass that sits
outside r50 on a 4.38:1 cloud (decision D8).

**Parity is the component that separates a culprit from a passer-by.** A vessel that happened to
be close but crossed the slick perpendicular is a much weaker candidate than one that ran along
it. Raw closeness is the weakest of the geometric signals, which is why proximity's weight was cut
from 0.40 to 0.30 and the freed weight went to parity and temporality.

**`closest_km` is measured to the origin-grid peak, not to the centroid** (decision D36). On an
elongated cloud the two can be 10 km apart, and a vessel sitting exactly on the peak would
otherwise read as "10 km away". Anything rendering `closest_km` labels it as distance to the peak,
never "closest approach" to the centre of the rings.

### Applicability gating — the `null ≠ 0` rule, mechanised

A component that cannot be measured on a given case returns **`null`**, not `0`, and its weight is
removed from the denominator. `weight_live`, `components_available` and `components_total` record
what actually ran.

Gating rules are stated, never buried in a quiet conditional:

- **`parity`** applies only when the discharge is chronic. A blob has no meaningful centerline.
- **`trajectory`** applies only when the vessel was seen outside `radius_90_km` during the window.
  A vessel that was never observed approaching from anywhere scores `null`, not 1.0 (D27).
- **`type_prior`** applies only when the candidate fleet is mixed (D28). It returned 1.00 for all
  17 vessels on one offshore run, because an offshore lane is all tankers and cargo. **A component
  returning the same value for every candidate changes no ranking and quietly adds its full weight
  to everybody's displayed score.** When all scored candidates share a type class, it returns
  `null`.
- **`gap` and `slowdown` are structurally `null` on a `gfw_hourly` case** (D20). GFW publishes
  hourly cell centres; a transponder gap and a speed profile are not measurable at that sampling,
  and `sog`/`cog` are written NULL rather than derived — a course between two 1 km cell centres an
  hour apart is not a measurement. **The validator fails on a zero here**, because a zero where a
  null belongs is an honesty bug, not a display bug.

`component_notes` carries the human-readable reason a component was inapplicable, so a card can
say "n/a — vessel never dropped below cruising speed in the window" rather than showing a silent
blank.

---

## Exclusions are mandatory

Every case publishes at least one vessel it ruled out, with the reason:

> *"heading away from the origin throughout the window"*
> *"track runs perpendicular to the slick axis"*

This is what converts the output from an accusation into an investigative shortlist. A system that
only ever produces suspects is not showing its work.

## Abstention is built in

`abstained: true` requires an empty `suspects` list, and Stage 2 can force it via
`origin.abstain`. On two cases the funnel runs `9 → 2 → 0 → 0`: the system searched and found no
vessel inside the origin cloud. **That is a searched negative, and it is a different claim from
"nothing was searched."** The refusal is a feature, not a gap.

---

## Dark vessels and infrastructure

**Dark vessels** — a radar contact from Stage 1 with no AIS broadcast nearby at scene time — carry
`mmsi: null` and `name: "Unidentified radar contact"`. They **never** get an invented identity.
The validator enforces that every suspect `mmsi` has a matching track in `vessels.geojson`, which
is what makes the honesty rule mechanical rather than aspirational.

**Infrastructure** candidates (pipeline, platform, wreck) are stationary and must carry a citable
source; the validator rejects one without.

---

## Data sources

| Source | Cases | Notes |
|---|---|---|
| NOAA Marine Cadastre | the seven US cases | Public domain. Filtered on scan with DuckDB — the `WHERE` is applied *during* the file scan, so peak memory is the size of the result rather than the 800 MB CSV. |
| Global Fishing Watch API v3 | the two Indian cases | **Non-commercial only.** `/v3/4wings/report` at hourly resolution grouped by vessel returns real per-vessel positions (D40). `ingest_gfw.py` writes the same parquet schema as `ingest.py`, so nothing downstream changed. |

The GFW licence condition reaches the committed bundles — see [`../../DATA_LICENSES.md`](../../DATA_LICENSES.md).

Two traps live in the AIS data itself:

- **AIS encodes *unknown* as an in-range value, not a blank.** SOG 102.3, COG 360.0, Heading 511.
  COG's sentinel affects ~9.9% of rows; treated as a measurement it silently poisons every
  trajectory calculation.
- **Box-edge truncation.** ~13% of tracks touch a box edge, where the first or last stored position
  is where the vessel left the rectangle, not where it went. Closest approach and trajectory are
  both computed from a truncated path, and nothing raises unless it is guarded — `edge_truncated`
  records it.

---

## Prior art, and what is different here

The parity / proximity / temporality framework is SkyTruth Cerulean's, and it is cited as theirs.
Four things differ:

1. **The physics runs backwards.** Cerulean matches a slick to a *coincident* AIS track, pulling
   AIS from ~8 h before the image to ~6 h after. That works when the satellite catches the vessel
   in the act; it cannot attribute a slick found days after release. Here the AIS search is
   anchored to a reconstructed release window — which is the whole reason this problem exists,
   since Sentinel-1's revisit gap means slicks are usually seen late.
2. **VV and VH**, where Cerulean's detection model uses VV alone.
3. **Free public AIS** (NOAA Marine Cadastre), not commercial AIS — it matters for a system anyone
   should be able to run.
4. **Published exclusions.**

Their disclaimer is also the template here: if the leading operational system says SAR alone
cannot definitively identify oil slicks, this project says it too.

---

## How this stage is evaluated

Not on the live cases. Every case in the library has a documented outcome sealed in
`docs/ANSWERS.md`, so any accuracy figure quoted from one would be a figure whose answer was held
while the scorer was tuned (decision D21).

Instead: **real AIS traffic, a synthetic offender whose discharge point, transponder gap, speed
profile, course and type are controlled, and therefore a rank that can be checked.** Design,
conditions, results and the weight ablation:
[`../evaluation/stage3-injected-offender-curve.md`](../evaluation/stage3-injected-offender-curve.md).
Raw output: `pipeline/attribute/results/`.

Every figure from it is a **ranking** number given a stated origin quality — an upper bound on
end-to-end performance, never accuracy on the live cases.
