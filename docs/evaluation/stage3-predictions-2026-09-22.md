# Stage 3 recalibration — predictions, written before the code

The point of this file is that it is dated and committed **before** the changes it predicts.
A fix that is chosen because of what it does to a known answer is not a fix; it is a tune. The
only defence against that is to state the mechanism and the expected outcome first, in a form
that can come out wrong, and then report the result either way.

Baseline: `docs/evaluation/stage3-baseline-2026-09-22.md`.

---

## The go/no-go probe on the merged AIS pool (§3.0)

Run 2026-09-22 against GFW `public-global-presence:latest`, same origin boxes and windows the
scorer uses.

| case | NOAA vessels | GFW vessels | overlap | new from GFW |
|---|---|---|---|---|
| jacksonville-2024 | 32 | 33 | 28 | **5** |
| farallones-2023 | 11 | 12 | 11 | **1** |
| huntington-2021 | 596 | 625 | 535 | **90** |

**The new vessels are not plausible spillers.** Jacksonville's five are `CG MAPLE` (a Coast Guard
cutter), `MARMAC 302` (a barge), `SIGNET WARHORSE I` (a tug), `SIMONE` and `PERLA DEL CARIBE`.
Farallones' one is `NOAHS ARK`, a fishing boat. Huntington's ninety are almost entirely
recreational passenger craft. Both reference culprits — MENUETT `563082600` and PANAGIA
THALASSINI `212656000` — were **already in the NOAA extract**.

**Conclusion, and it changes the framing of the whole merge:** the merged pool's value is *not*
new candidates. It is the coverage-hole correction below. That is worth stating on the slide
rather than claiming GFW "found more ships", which the numbers do not support.

---

## P1 — the coverage-hole gate (CONFIRMED, before any code)

**Mechanism.** `component_gap` (`score.py:228-274`) scores a transponder silence as evidence of
deliberate darkness. NOAA Marine Cadastre is a **terrestrial-receiver** archive: offshore, a
vessel can be transmitting normally and simply not be heard. A silence in NOAA is therefore not
by itself evidence of anything. If a second, independently-received source shows the vessel
broadcasting *inside* that silence, the silence is a property of the receiver network, not of
the vessel — and scoring it as darkness is a false positive.

**Measured on Jacksonville, 2026-09-22:**

| vessel | NOAA rows | longest silence in window | GFW rows inside it | reading |
|---|---|---|---|---|
| 210145000 STENA PROSPEROUS (#1 today) | 114 | **142.3 min** 16:44:22Z → 19:06:41Z | **3** (17:00, 18:00, 19:00) | coverage hole |
| 338305838 PATRIOT (#3 today) | 124 | 74.8 min 16:09:44Z → 17:24:33Z | **1** (17:00) | coverage hole |
| 563082600 MENUETT (the reference answer) | 340 | **none ≥ 30 min** | — | continuous |

The GFW fixes during STENA's "silence" are at lon −79.38…−79.42, lat 29.50…29.69 — well inside
the NOAA extract box (lat 28.70…31.13, lon −80.65…−78.89), so this is **not** the existing
box-edge artefact that `component_gap` already guards against at `score.py:268`. The vessel was
inside the searched area, transmitting, and unheard.

**Predicted consequence.** With `gap` gated to `null` for the whole scored set (source-determined
applicability is not comparable across candidates — §3.6) and `trajectory` gated by the existing
D28 rule (constant 1.0 across all three), live weight falls to 0.55 and:

| vessel | score today | predicted | rank today | predicted rank |
|---|---|---|---|---|
| **563082600 MENUETT** | 0.593 | **0.643** | 2 | **1** |
| 210145000 STENA PROSPEROUS | 0.734 | 0.589 | 1 | 2 |
| 338305838 PATRIOT | 0.569 | 0.334 | 3 | 3 |

**This matches the sealed answer, and it must be reported as a defect fix with a target-shaped
side effect, in those words.** The mechanism is AIS receiver coverage physics; it was stated and
measured before the code existed; and it would have been written down identically had the
reference named STENA instead. What it is *not* is evidence that our scorer was tuned to agree
with Cerulean.

The honest caveat that goes on the slide with it: **a 142-minute gap was never good evidence in
the first place**, and the old bundle's #1 rested on it. That is a defect we found in our own
scorer, not a win over anyone else's.

---

## P2 — Gulf of Alaska, AtoN filter

`941201607` / `941214805` / `941205333` / `941216622` ("MAJOR BUOY 4") are aids to navigation.
`941` is an unassigned ITU MID, which is the honest reason to reject them rather than
pattern-matching the literal prefix.

Predicted: `in_region` 14 unchanged, `dropped_non_vessel` ≈ 4, `plausible` 2 → 0, suspects 2 → 0,
`abstained: true` on "no vessel entered the reconstructed origin during the window".

Second-order and **not** certain: `dark.py`'s `scene_tracks` come from the same `load_tracks`, so
the buoys leave the dark cross-check pool too. Both GFW SAR contacts currently match to AIS and
`dark_vessels` is empty. If the buoys were what they matched to, removing them surfaces the dark
vessel — which is the reference answer for this case. **Verify; do not assume.** If it does not
happen, say so.

## P3 — Farallones

Named with `level: "low"`. Whether PANAGIA reaches #1 depends on (a) the age-grid fix extending
the release window to `t0` and (b) the tie-break order, which was chosen on principle in §2.3.

Measured in advance — peak origin-grid probability along each vessel's real NOAA track:

| vessel | window `[t0−18.5 h, t0−0.5 h]` | window extended to `t0` |
|---|---|---|
| 212656000 PANAGIA THALASSINI | 0.447 | **0.551** at t0−11 min |
| 248264000 TUGELA | 0.165 | 0.165 |
| 636016487 HORIZON | **0.000** | **0.000** |

HORIZON never enters the origin cloud at any time — while the current `verification.json` calls
it a `hit` at rank #1 with score 0.620. Report the outcome either way and **do not revisit the
tie-break because of it.**

## P4 — Jamnagar

3 named suspects, real MMSIs per the owner's ruling, `level: "low"` (separation < 3 % and
`weight_live` 0.35 < 0.40 both fire).

## P5 — Mumbai

Order unchanged; `level: "low"` on thin evidence. The reference expects zero vessel candidates
here; we will name three at low confidence, which is the owner's stated requirement. The
multi-source reading must come from `infrastructure[]` / `dark_vessels[]`, never from suppressing
the ranking.

## P6 — Huntington

Unchanged (case deferred to the infrastructure-layer phase). Confirm the merge does not disturb
it.
