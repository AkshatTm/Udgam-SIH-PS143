# Stage 1 — accuracy programme: live status

*Owner: Soumirya. **This file is updated as each item completes** — it is the board, not a log.
The narrative and the reasoning live in `docs/updates/soumirya.md`; this is the one-screen answer to
"where is it".*

**Last updated: 2026-09-16 10:45** — **Layer 1 recall FIXED without retraining**: Part III oil recall 0.873 → 0.927 by changing the threshold RULE. The gate is now free (matches ungated exactly). Previously — — **`--min-recall 0.95` FAILED** (recall 0.873 → 0.853) and Layer 1 training is **nondeterministic**. One rejected large slick costs **−0.046 pooled**. Programme frozen per Akshat's final-day brief. Previously — — **first END-TO-END gated number: 0.7566** on validation. Layer 1 retrained; the gate is essentially free. Previously — — **noise floor MEASURED at 3 seeds.** Pooled sd **0.0267**. Only the ≥30% result survives it. Previously — — **E2c MEASURED and the normalisation work is DONE.** E2c is the shippable configuration. The "band regressions" turn out to be training variance, not normalisation — see *What the normalisation actually touches*.

---

## What this is, and what it is NOT

`docs/team/soumirya-stage1-detection.md` — the Stage 1 task document, **7 phases and a 12-item definition of
done — is COMPLETE**. Nine cases PASS, `detections.geojson` ships for all of them, and the demo
loads none of this work.

This programme is **separate and additive**: it was written after the >85% accuracy target was
set. It is **December work, not demo work.** Nothing in it is on the critical path for
15 Sept 17:00, and nothing in it may overwrite `models/unet.pt` or `models/scene_classifier.pt`,
which are what the demo loads.

> **RESUMED 2026-09-15 19:25**, after the demo. The pause record below stands as written.
>
> **PAUSED 2026-09-15 for the demo.** Verified the same morning, read-only: nine cases **PASS**,
> `unet.pt` and `scene_classifier.pt` untouched since 12–13 Sept, the shipped checkpoint still
> reports `band_order`/`median`, and the live detections come from the **classical** path — the
> U-Net is not in the demo's critical path at all. No GPU work was run on demo day. Resume at
> **E2b**, below.

## The three numbers, which are different things

| | value | what it is |
|---|---|---|
| **measured today** | **0.4349** | our pooled oil-class IoU on the Part III holdout |
| **ceiling** | **0.8446** | what a GT-informed oracle scores — it is *handed* the sea reference. Verified independently (E8a) |
| **projection** | **0.8589** | arithmetic, *if* E2 lands the two heavy bands on their ceilings. **Not a result** |

**0.85 sits essentially on the ceiling**, so it requires beating an oracle. The reason that is
plausible: we already beat the oracle on three of five bands (E8a).

## Where the failure is

| oil coverage | n (P3) | ours | oracle | share of P3 oil mass |
|---|---|---|---|---|
| 0–1% | 18 | 0.6685 | 0.4387 | 0.7% |
| 1–3% | 39 | 0.7566 | 0.6601 | 5.1% |
| 3–10% | 52 | 0.7826 | 0.7429 | 19.5% |
| 10–30% | 29 | 0.6595 | **0.8123** | 36.4% |
| **≥30%** | **12** | **0.0848** | **0.9590** | **38.3%** |

Two bands hold **74.7%** of the metric and are the only two we lose.

---

## E2 RESULT — the first item in this programme to move a number

**Ungated U-Net, held-out val scenes, fold 0. Same budget, same fold, differing only in the cache.**

| band | baseline (median) | **E2 (sea)** | change | oracle | share of metric |
|---|---|---|---|---|---|
| 0-1% | 0.6121 | 0.5943 | -0.018 | 0.4387 | 0.7% |
| 1-3% | 0.7503 | 0.7133 | -0.037 | 0.6601 | 5.1% |
| 3-10% | 0.8377 | 0.7438 | -0.094 | 0.7429 | 19.5% |
| 10-30% | 0.8962 | 0.7357 | **-0.161** | 0.8123 | 36.4% |
| **>=30%** | **0.2820** | **0.8386** | **+0.557** | 0.9590 | 38.3% |
| | | | | | |
| **pooled** | **0.6894** | **0.7316** | **+0.042** | | |
| 95% CI | [0.584, 0.781] | [0.695, 0.764] | | | |
| mean IoU | 0.8386 | 0.8608 | +0.022 | | |
| macro/scene | 0.7287 | 0.6890 | -0.040 | | |

**The mechanism is confirmed.** The >=30% band goes **0.282 -> 0.839**, a 3x improvement landing
near the oracle's 0.959. That band is the entire reason this programme exists.

**But read the significance honestly.** Pooled +0.042 is *inside* the 0.0599 fold spread, so on
pooled alone this is **not yet a significant win**. What is well outside noise is the >=30%
change: +0.557 against an across-fold band range of 0.257.

**And four of five bands regressed**, worst at 10-30% (-0.161), which carries 36% of the metric.
`macro/scene` falling while `pooled` rises is the signature: most scenes slightly worse, a few
heavy ones much better.

**Best-of-both would be 0.8534** band-weighted - the target - *if* the regressions turn out to be
an artefact rather than intrinsic.

### The confound, flagged before the run and now load-bearing

The two caches differ in **three** ways, all from the coastline mask:
1. normalisation - median vs sea-referenced
2. **489 fewer tiles** (6,373 hard negatives vs 6,850)
3. **175 fewer source scenes** (2,395 vs 2,570) - the entirely-land scenes, dropped

The E2 audit measured normalisation as **identical** on the bands that regressed (0.000 shift,
1.000 scale up to 3-10%). So normalisation probably did **not** cause those regressions; less
training data and fewer hard negatives probably did.

**NEXT EXPERIMENT, now necessary rather than optional:** a third cache, sea-referenced
normalisation with **no land exclusion**. That separates "the fix" from "we trained on less".
~1 h rebuild + one training run.

---

## E2b RESULT — the confound is broken apart

**Same budget, same fold, same evaluation. `P12seanl` = sea normalisation with the coastline mask
OFF, so the scene and tile population is the baseline's.**

The cache was verified to be a single-variable change before training: tiles 28,129 (identical to
`P12`), all 175 scenes `P12sea` had lost are back, the **positive tile set is bit-identical**, and
only **13 tiles of 28,129 (0.05%)** differ — all hard negatives, whose darkness ranking is computed
*on* the normalisation under test. Normalisation genuinely differs on 118 scenes (4.6%), which is
the check that the flag did not silently fall back to median.

| band | n | baseline (median) | E2 (sea) | **E2b (sea, no land)** | reading |
|---|---|---|---|---|---|
| 0-1% | 53 | 0.6121 | 0.5943 | **0.6287** | recovered, now above baseline |
| 1-3% | 75 | 0.7503 | 0.7133 | **0.7490** | recovered to baseline |
| 3-10% | 45 | 0.8377 | 0.7438 | **0.8089** | mostly recovered, still -0.029 |
| 10-30% | **6** | 0.8962 | 0.7357 | **0.6543** | still down — **but n=6** |
| **≥30%** | **3** | **0.2820** | 0.8386 | **0.8275** | **the gain SURVIVES** |
| | | | | | |
| **pooled** | | 0.6894 | 0.7316 | **0.7503** | +0.0609 vs baseline |
| 95% CI | | [0.584, 0.781] | [0.695, 0.764] | **[0.700, 0.794]** | |
| mean IoU | | 0.8386 | 0.8608 | **0.8704** | best of the three |
| macro/scene | | 0.7287 | 0.6890 | **0.7269** | back to baseline |

### What it settles

1. **The ≥30% fix is the normalisation, not the data reduction.** With every dropped scene
   restored, the band still scores 0.8275 against the baseline's 0.2820. This was the one way E2's
   headline could have been an artefact, and it is not.
2. **The regressions were the data reduction.** Three of four bands recover once the 175 scenes and
   477 hard negatives come back. `macro/scene` returning to baseline (0.6890 → 0.7269) is the
   clearest signal: E2's "most scenes slightly worse" signature is gone.
3. **E2b is the best configuration measured** on pooled, mean IoU and macro/scene simultaneously.

### What it does NOT settle — read these before quoting anything

- **Pooled +0.0609 against a fold spread of 0.0599.** It clears the bar by 0.001. On pooled alone
  this is still not a result worth defending; the ≥30% band is.
- **The two heavy bands have n=6 and n=3 on this fold.** They carry 74.7% of the Part III metric
  and are measured here on nine scenes. The 10-30% "regression" (-0.24) rests on six scenes and may
  be noise. **Rotate the folds before believing either number.**
- **Band-weighted by Part III oil mass: baseline 0.6401, E2 0.7746, E2b 0.7554.** E2 scores *higher*
  than E2b here purely because 10-30% carries 36.4% of the mass — i.e. this ordering is decided by
  the n=6 band. Best-of-both-per-band is **0.8534**, unchanged.

### ⚠ E2b's cache is NOT shippable, and that is the point

`P12seanl` puts land back into the sea-reference sample — exactly what failed the first two E2
audits, where the estimator picked a coastline as "sea" and moved the reference by up to 21 dB, at
which point the entire ocean reads as oil. It is a **measurement instrument**, not a candidate.

So the result is not "ship E2b". It is: *we now want sea normalisation with the land exclusion ON
for correctness, but without losing 175 scenes of training data.*

### E2c — the structural fix this exposes

`build_cache._norm()` uses **one** mask for **two** different questions:

```python
v = valid_mask(band, exclude_land=exclude_land, transform=transform)
ref, scale, _ = sea_reference(band, v, transform=transform)   # (a) estimate the sea
return np.where(v, out, 0.0), v, ref, scale                   # (b) ...and mark tiles usable
```

`v` is returned as the scene's `valid` mask, and `run()` drops any tile with
`(~valid).mean() > MAX_INVALID_FRAC`. So "do not measure the sea level from land" silently became
"land pixels are unusable data" — which is what deleted 175 scenes and 477 hard negatives.

**These are separate questions and should use separate masks:**

- reference/scale → land-excluded sample (correct, audit-safe)
- tile eligibility → finite and non-zero only (the baseline's rule)

That should give the ≥30% fix *and* the full 28,129 tiles, with no land in the reference. It is the
configuration that could actually ship, and neither E2 nor E2b is.

---

## E2c RESULT — and what the normalisation actually touches

`P12seac`: land excluded from the **sea reference only**, tile eligibility back to the baseline's
finite+non-zero rule. Verified before training — identical sea reference to `P12sea` on all 2,400
scenes that have sea, **zero** matching the land-contaminated variant, the 170 entirely-land scenes
recovered, positives bit-identical to the baseline, 34 of 28,129 tiles differing (0.12%, all hard
negatives).

| band | n | baseline | E2 | E2b | **E2c** |
|---|---|---|---|---|---|
| 0-1% | 53 | 0.6121 | 0.5943 | 0.6287 | **0.6181** |
| 1-3% | 75 | 0.7503 | 0.7133 | 0.7490 | **0.7497** |
| 3-10% | 45 | 0.8377 | 0.7438 | 0.8089 | **0.8330** |
| 10-30% | **6** | 0.8962 | 0.7357 | 0.6543 | **0.7007** |
| ≥30% | **3** | 0.2820 | 0.8386 | 0.8275 | **0.8238** |
| | | | | | |
| **pooled** | | 0.6894 | 0.7316 | 0.7503 | **0.7567** |
| mean IoU | | 0.8386 | 0.8608 | 0.8704 | **0.8736** |
| macro/scene | | 0.7287 | 0.6890 | 0.7269 | **0.7316** |
| band-weighted | | 0.6401 | 0.7746 | 0.7554 | **0.7756** |

**E2c wins on every aggregate**, and is the only variant above baseline on `macro/scene`. It is the
first configuration that is simultaneously audit-safe, trained on the full data, and fixes the
large-slick collapse. **Neither E2 nor E2b can ship; E2c can.**

### ❗ The band "regressions" were never normalisation — they are training variance

This is the most important measurement of the session, and it retires a line of investigation.

**How often does sea normalisation change the network's input at all?**

| band | oil scenes | input changed |
|---|---|---|
| 0-1% | 353 | 5.9% |
| 1-3% | 502 | 4.6% |
| 3-10% | 297 | 7.1% |
| 10-30% | 39 | 25.6% |
| **≥30%** | **9** | **100%** |
| **all oil** | **1,200** | **7.0%** |

The estimator returns the plain median bit-for-bit whenever it finds one mode — that fall-through is
its safety property, and it fires on **93% of oil scenes**. So the normalisation is close to a no-op
everywhere except the band it was built for, where it fires on **every** scene.

**The 10-30% band, which looked like the last gap, is six scenes of which FIVE get byte-identical
input to the baseline.** Per-scene, at fold 0:

| scene | oil% | baseline | E2 | E2c | input vs baseline |
|---|---|---|---|---|---|
| `P12_Oil_00059` | 13.6% | 0.8235 | 0.7583 | **0.0000** | **IDENTICAL** |
| `P12_Oil_00134` | 15.6% | 0.8651 | 0.6839 | 0.8405 | IDENTICAL |
| `P12_Oil_00269` | 16.1% | 0.9821 | 0.9626 | 0.9593 | changed (scale) |
| `P12_Oil_00423` | 14.8% | 0.7948 | 0.5232 | 0.5851 | IDENTICAL |
| `P12_Oil_01210` | 12.6% | 0.9781 | 0.8567 | 0.9338 | IDENTICAL |
| `P12_Oil_01220` | 11.5% | 0.9336 | 0.6294 | 0.8857 | IDENTICAL |

`P12_Oil_00059` predicts **0.0% of the scene as oil** — a total miss on a scene with 13.6% coverage
and −8.5 dB contrast, whose input is *bit-identical* to the one the baseline scores 0.8235 on. The
normalisation cannot explain that. **Different weights can, and that is the whole explanation.**
Drop that single scene and E2c's band mean goes **0.7007 → 0.8409**.

**Consequences, and they are not small:**

1. **The ≥30% result stands and is causal** — 100% of those scenes have changed input, and the
   change is +0.55.
2. **Every other band comparison on this board is dominated by training variance**, because 93-95%
   of those scenes receive identical input. The apparent E2/E2b/E2c differences outside ≥30% are
   three draws from the same distribution.
3. **"Best-of-band 0.8534" is not a real target.** It takes a maximum over noisy per-band estimates,
   which is biased upward by construction. It should not be quoted as a reachable number.
4. **Seed variance is now the blocking measurement.** A single scene swung 0.82 → 0.00 on identical
   input. Until that spread is known, no future change under ~0.05 can be called an improvement —
   and that includes E4.

### The normalisation work is complete

E2 / E2b / E2c answered what they were built to answer. The ≥30% collapse is fixed, the cause is
established, and E2c is the configuration to carry forward. **More normalisation variants are not
where the remaining accuracy is.**

---

## 🚨 THE NOISE FLOOR — measured, and it retires most of this board

**E2c trained three times. Identical cache, identical fold, identical budget, byte-identical data.
The only difference is `--seed`.**

| band | n | seed 42 | seed 1 | seed 2 | spread | **sd** |
|---|---|---|---|---|---|---|
| 0-1% | 53 | 0.6181 | 0.6243 | 0.6376 | 0.0195 | 0.0100 |
| 1-3% | 75 | 0.7497 | 0.7302 | 0.7507 | 0.0205 | 0.0116 |
| 3-10% | 45 | 0.8330 | 0.7853 | 0.8119 | 0.0477 | 0.0239 |
| 10-30% | 6 | 0.7007 | 0.5836 | 0.6796 | 0.1171 | **0.0624** |
| ≥30% | 3 | 0.8238 | 0.7577 | 0.8671 | 0.1094 | **0.0551** |
| | | | | | | |
| **pooled** | | 0.7567 | 0.7140 | 0.7630 | **0.0490** | **0.0267** |
| mean IoU | | 0.8736 | 0.8517 | 0.8770 | 0.0253 | 0.0137 |
| macro/scene | | 0.7316 | 0.7086 | 0.7325 | 0.0239 | 0.0135 |

### What survives

| claim | effect | vs seed noise | verdict |
|---|---|---|---|
| **≥30% band: baseline → E2c** | **+0.5342** | **9.7 sd** | ✅ **REAL** |
| pooled: baseline → E2c | +0.0552 | 2.1 sd | ❌ **not established** |
| mean IoU: baseline → E2c | +0.0288 | 2.1 sd | ❌ not established |
| macro/scene: baseline → E2c | **−0.0045** | −0.3 sd | ❌ no effect |
| 10-30% "regression" | −0.1955 | 3.1x the band sd | ⚠ marginal |
| 3-10% "recovery" | −0.0047 | 0.2x | ❌ noise |

**And the comparison is kinder than it should be**: the baseline is itself a SINGLE draw, carrying
its own ±0.027. A proper test needs replicates on both sides, which would widen the interval
further. The ≥30% effect is large enough that none of this matters; nothing else is.

### What this means, stated plainly

1. **The programme has exactly one defensible result: the ≥30% band, 0.2820 → 0.8162 (mean of 3
   seeds), at 9.7 sd.** That is the failure that produced the 0.4349 headline, and it is fixed.
2. **The pooled improvement is not established.** +0.0552 against sd 0.0267 is 2.1 sd, and every
   narrative on this board about bands "recovering" or "regressing" across E2/E2b/E2c was reading
   seed noise as signal. The per-band commentary in the E2 and E2b result blocks should be read with
   that correction applied.
3. **E2c's benefit is concentrated entirely in large slicks** — which is exactly what it was built
   for. `macro/scene` weights every scene equally and shows **no effect at all** (−0.3 sd), while
   pooled weights by pixel and moves. Three huge scenes out of 182 cannot shift a per-scene average.
   **This is coherent, not contradictory**, and it is why the Part III projection is still favourable:
   that holdout's ≥30% band carries **38.3% of its oil mass** while scoring **0.0848**.
4. **A single-run experiment is no longer a measurement.** Anything moving pooled by less than
   **~0.08** (3 sd) is invisible. **This applies to E4, E3 and E5 before they are run.**

### The cost this imposes on everything that follows

Every future comparison needs **3 seeds** (~4.5 h per configuration) or it cannot be believed.
Options, in order of how much they actually buy:

- **Stop optimising pooled.** Target the ≥30% regime, where effects are 10x the noise. This is where
  the metric's mass is anyway.
- **Tune on a quieter metric.** `macro/scene` (sd 0.0135) and `mean IoU` (sd 0.0137) are **half as
  noisy as pooled**. Select on those, report pooled. Legitimate, and free.
- **Pay for 3 seeds per experiment.** Correct but expensive, and it triples the remaining programme.
- **Reduce the variance itself** — seed ensembling (E5) is the direct instrument, and its “run it
  last” rationale was that it inflates intermediate comparisons. That reasoning is now weaker: if
  variance is the binding constraint, averaging it away may be the most valuable single change
  rather than the last one.

---

## END-TO-END — the real two-layer pipeline, gated (2026-09-16)

Layer 1 retrained on `P12seac` (tagged `l1_e2c`; the shipped pair is untouched), Part III cache
rebuilt as `P3seac` under the corrected convention. **This is the first number in this programme
that measures the pipeline as it would actually run.**

| | ungated (Layer 2 alone) | **gated (real pipeline)** |
|---|---|---|
| pooled IoU | 0.7567 | **0.7566** |
| macro/scene | 0.7316 | 0.7313 |
| mean IoU | 0.8736 | 0.8735 |
| oil recall | 0.9945 | 0.9890 |
| **look-alike rejection** | **0.0777** | **0.9612** |

**The gate costs 0.0001 IoU and buys look-alike rejection from 0.078 to 0.961.** Layer 2 alone
floods look-alike scenes with false positives; Layer 1 removes 96% of them without measurably
harming segmentation. Verified genuinely gated: the run prints the classifier path and threshold
(0.4896) and records the `Classifier + U-Net` row.

### Layer 1, new vs shipped (Part III — disclosure, not selection)

| | shipped | `l1_e2c` | |
|---|---|---|---|
| scene accuracy | 0.951 | 0.940 | −0.011 |
| **oil recall** | 0.927 | **0.873** | **−0.053** |
| look-alike rejection | 0.940 | **0.960** | +0.020 |
| clean-ocean rejection | 0.987 | 0.987 | — |

The new classifier trades recall for look-alike rejection — arguably the wrong direction for a spill
detector, and **tunable**: the threshold moved from 0.1427 to 0.4896 under the same
`--min-recall 0.90` floor. Raising that floor is the cheap lever if the gate becomes the bottleneck.
Both are single draws and Layer 1 seed variance is **unmeasured**, so −0.011 may be noise.

Note the recall gap by population: **0.989 on validation vs 0.873 on Part III**. Validation is drawn
from Parts I+II, which the classifier trained on. The gate will be lossier on the true holdout.

### Where this leaves the target

| | value | measurement |
|---|---|---|
| programme start | **0.4349** | Part III, gated, shipped model |
| **now** | **0.7566** | **validation, gated, E2c + l1_e2c** |
| target | 0.85 | |

**These two are still not comparable** — different scene populations. They are now at least the same
KIND of measurement (gated, end-to-end), which they were not before tonight. Closing the gap
honestly requires running Part III, **which stays sealed** until a final configuration is chosen.

---

## ❌ `--min-recall 0.95` — a NEGATIVE result, and two things worth keeping

Run at Soum's request before Akshat's final-day brief arrived. **It did the opposite of its
intent**, and the reason is instructive.

| Part III | shipped | r90 | **r95** |
|---|---|---|---|
| scene accuracy | 0.951 | 0.940 | **0.931** |
| **oil recall** | 0.927 | 0.873 | **0.853** |
| look-alike rejection | 0.940 | 0.960 | 0.953 |
| threshold | 0.1427 | 0.4896 | **0.4709** |
| variant selected | `both32` | `both32` | **`both_wide`** |

### Why it failed: the floor does not bind where it matters

The recall floor is applied on the **validation** split, where Layer 1 already reaches **0.989**
recall. A 0.95 floor is **slack** there — it constrains nothing, which is why the threshold moved
only 0.4896 → 0.4709. Part III recall (0.87) is a different population and the floor never touches
it. **To bind at all, the floor would have to sit near 0.99.** That is a new experiment, not a
30-minute fix.

### Layer 1 training is NONDETERMINISTIC — `torch.manual_seed(42)` is not enough

Same seed, same data, same config, two runs:

| variant | r90 `val_loss` | r95 `val_loss` |
|---|---|---|
| `both32` | **0.0560** ← selected | 0.0633 |
| `both_wide` | 0.0628 | **0.0619** ← selected |
| `paper_avg32` | 0.0645 | 0.0673 |
| `max32` | 0.0767 | 0.0703 |

cuDNN autotuning and non-deterministic atomics leave real run-to-run variation. Consequences:

1. **The r90/r95 comparison is confounded** — the threshold changed AND the model changed.
2. **Variant selection is effectively a coin flip.** The `val_loss` gap between the top two
   (0.001–0.007) is smaller than the run-to-run variation (~0.007). In this run `paper_avg32`
   scored Part III 0.944 / 0.887 / 0.960 — better than the selected `both_wide` on every axis — but
   selecting on that would be tuning on the holdout.
3. **The shipped 0.951 vs our 0.940 is very likely noise**, not a regression.

### ❗ The finding worth keeping: one rejected large slick costs −0.046 pooled

Gated validation, r90 vs r95 — **four bands byte-identical, only `≥30%` moves**:

| band | r90 gated | r95 gated |
|---|---|---|
| 0-1% / 1-3% / 3-10% / 10-30% | identical | identical |
| **≥30%** | **0.8238** | **0.6087** |
| **pooled** | **0.7566** | **0.7110** |

The r95 classifier rejected **one** ≥30% scene (IoU ≈ 0.645 → 0). That single Layer 1 false negative
cost **−0.0456 pooled IoU** — larger than the entire measured baseline→E2c effect (+0.055).

**So Layer 1's recall on LARGE slicks specifically is worth far more than its headline accuracy.**
A classifier that is 1% more accurate overall but drops one big slick is a net loss. Any future
Layer 1 work should be selected on large-slick recall, not scene accuracy — and the shipped model's
much lower threshold (0.1427, recall 0.927) looks better-placed for this than either retrain.

**Status: frozen.** Akshat's final-day brief (16 Sept) freezes model work, and this result supports
that call — Layer 1 changes are inside the noise. All artefacts are tagged; the shipped pair is
untouched.

---

## ✅ Layer 1 recall, fixed by the threshold RULE — no retraining

After `--min-recall 0.95` failed, the fix turned out to be the **objective**, not the floor. The
threshold is a post-hoc scalar, so the existing `l1_e2c` weights were reused: **no retraining, and
therefore none of the nondeterminism confound that wrecked the r95 comparison.**

### Why the earlier attempts failed

- **`--min-recall 0.95`** — the floor is applied on validation, where recall is already **0.989**.
  Slack; it never binds. Threshold moved only 0.4896 → 0.4709.
- **A large-slick recall constraint** — **vacuous**. Validation holds only 11 scenes ≥10% coverage
  and **every threshold from 0.05 to 0.65 catches all of them.** Validation is saturated, so no rule
  keyed on big-slick recall can discriminate.
- **Not the split.** Layer 1's naive split actually holds *more* big scenes than Layer 2's
  coverage-stratified one (10-30%: 7 vs 6; ≥30%: 4 vs 3). The binding constraint is that only
  **9 scenes ≥30% exist in all of Parts I+II**.

### What worked: change the objective

`pick_threshold` maximises **F1**, which weights precision and recall equally. A gate's errors are
**asymmetric**, and the function's own docstring says so — *"we would rather send a marginal scene to
Layer 2, which can still reject it, than never look at it"* — but F1 does not encode it:

- **false negative** → scene never reaches Layer 2, scores **0 IoU**, unrecoverable. One ≥30% scene
  costs **−0.046 pooled**, larger than the entire measured baseline→E2c effect.
- **false positive** → recoverable; Layer 2 still segments and can reject.

**New rule, fixed on validation before Part III was read:** *the lowest threshold whose validation
precision stays ≥ 0.95.* It selects **0.1280** — which independently lands beside the shipped
model's **0.1427**, convergent evidence that the low gate is the right one.

### Result

| Part III (disclosure) | thr 0.4896 | **thr 0.1280** | |
|---|---|---|---|
| scene accuracy | 0.940 | **0.942** | +0.002 |
| **oil recall** | 0.873 | **0.927** | **+0.053** |
| look-alike rejection | 0.960 | 0.920 | −0.040 |
| clean-ocean rejection | 0.987 | 0.980 | −0.007 |

| gated validation | pooled | ≥30% | oil recall | look-alike rej |
|---|---|---|---|---|
| ungated (ceiling) | 0.7567 | 0.8238 | 0.9945 | 0.0777 |
| gated thr 0.4896 | 0.7566 | 0.8238 | 0.9890 | 0.9612 |
| gated thr 0.4709 (r95) | 0.7110 | 0.6087 | 0.9835 | 0.9417 |
| **gated thr 0.1280** | **0.7567** | **0.8238** | **0.9945** | 0.8447 |

**The gate is now free.** It matches the ungated ceiling exactly, loses **no** oil scene, and still
rejects 84% of look-alikes. This also confirms the design argument empirically: look-alike rejection
fell to 0.8447 and **pooled did not move at all**, because a look-alike reaching Layer 2 produces
almost no oil pixels — **Layer 2 is the second filter**, as intended.

### The decision this leaves open

The trade on Part III is **+0.053 oil recall for −0.040 look-alike rejection**. Which to carry is a
**judgement call, not a measurement**:

- for the **accuracy target** (pooled IoU) recall wins clearly — missed oil is unrecoverable;
- but **"look-alike rejection 0.940"** is a quoted deck figure, and this would make it 0.920.

Both are tagged and on disk. **Soum's call, post-demo.** Nothing shipped is affected.

---

## Status

| item | state | result |
|---|---|---|
| **E0** validation protocol | ✅ **done** | `split.py` + `evaluate_val.py`. Old split had **1** scene ≥30% in validation; now **3**, rotated over 3 folds. Proxy verified faithful (≥30% collapses to 0.17 vs 0.88 below it). **Fold spread 0.0599 — nothing smaller is measurable.** ⚠️ `train_unet` still selects on tile IoU, not val-scene |
| **E8a** oracle ceiling | ✅ **done** | **0.8446** verified independently (agent said 0.838). Boundary decomposition: at ≥30%, **81% of oracle error is within 5 px of the annotator's line** — that band is annotation-limited |
| **E1** channel fix + ablation | ✅ **done — NULL** | Four measurements agree it buys nothing: tile IoU 0.6997/0.6911/0.6994, pooled 0.6606/0.6513/0.6549 (spread 0.0093 vs fold noise 0.0599), ≥30% band 0.26–0.28 in all three. **Hypothesis retired.** Kept the rename for hygiene |
| **E2** sea-referenced normalisation | ✅ **MEASURED — works, with a trade** | **>=30% band 0.282 -> 0.839** (oracle 0.959). Pooled 0.6894 -> 0.7316, inside the fold spread. Four bands regressed, worst -0.161 at 10-30%. Confounded by 175 fewer scenes / 477 fewer hard negatives — isolation run needed. See the result block above |
| **E2c** sea reference, full training data | ✅ **MEASURED — the configuration that ships** | Best on every aggregate: pooled **0.7567**, mean IoU **0.8736**, macro/scene **0.7316** (only variant above baseline), band-weighted **0.7756**. Audit-safe reference AND the full 28,129 tiles |
| **E2b** isolation: sea norm, NO land exclusion | ✅ **MEASURED — it separates cleanly** | `--no-land-mask` wired and verified (`4850e43`): bit-identical on open ocean, and on the Campeche coastal look-alike valid 0.943 → 1.000, reference moves 0.33 dB. **Answer: the ≥30% gain is the NORMALISATION** (0.8275 with land exclusion off, against baseline 0.2820), **and the regressions were the DATA REDUCTION** — three of four recover, and `macro/scene` returns to baseline. See the result block below |
| **E4** loss — Focal+Dice / Tversky | ⬆️ **promoted, not started** | E1 points here: **zero of 200 easy tiles exceed 0.99** in any config, and focal γ=2 de-weights confident pixels by construction |
| **E3** high-coverage regime | ❌ not started | Only **9** training scenes ≥30%, covering 38% of the holdout's oil mass |
| **E5** TTA + seed ensemble | ❌ not started | Deliberately last — running it early inflates every intermediate comparison |
| **E6** scene conditioning | ⏸ conditional | Only if E2 underdelivers. Same argument as E2, so likely redundant if E2 works |
| **E7** architecture | ⛔ **not doing** | The dominant error is an input-representation failure, invariant to architecture |
| **E8c** annotation ceiling + our-cases GT | ❌ not started | Human time approved. Decides whether 0.85 is a target or a mirage |

### Carry-overs outside both plans

| item | state |
|---|---|
| **Layer 1 is stale against the new caches** | ⚠️ **NEW, and it blocks the gated metric.** The shipped classifier returns P(oil) **0.001-0.010** on new-convention input against a 0.143 threshold, so the gate closes on every scene. All E2 numbers above are therefore **ungated**. Layer 1 must be retrained on the new cache before any gated or end-to-end number means anything. **`--cache` now wired** (`4850e43`), so the retrain is unblocked |
| Python **3.13.5** vs the pinned **3.11** | ❓ open — Akshat's call. Only item that could break Stage 1 on another machine |
| `contrast_centre_db` / `contrast_edge_db` | ❓ dropped for demo; Anushka needs it for the weathering flag. ~10 lines, works on 11 of 12 oil features |
| **The `P3` holdout cache is STALE** | ⚠️ **NEW.** Built 12 Sept, before the channel-order fix — its manifest has no `channel_order`, i.e. channels TRANSPOSED relative to `P12`/`P12sea`. Any Part III number from a new-convention model is meaningless until it is rebuilt: `build_cache.py --parts 3 --normalise sea`. `train_classifier.py` now **aborts** on the mismatch rather than reporting nonsense |
| **170 of 1,370 non-oil scenes are entirely land** | ⚠️ unreported to Akshat — "look-alike rejection 0.940" is partly measured on farmland |

---

## Running log of what each item actually cost

| item | estimated | actual | note |
|---|---|---|---|
| E0 | ~4 h | ~4 h | on target |
| E2 safety gate | **~15 min** | **~1 day** | **5 audit iterations.** Four of the five failures were my measurement, not the fix |
| E8a | ~1 day | ~1 h | faster than planned |
| E1 | ~1 h + 3 runs | ~6 h | 3 training runs + 3 scene evals |
| E2 rebuild + retrain | ~5 h | ~8 h | 2 cache builds, 2 trainings, 3 evaluation attempts |
| E2b | ~3 h | ~3.2 h | 41 min build, 79 min train, 11 min eval. On estimate for once |
| E2c | ~3 h | ~3.5 h | 65 min build, 80 min train, 11 min eval, plus a convention bug caught pre-eval |

**Price the remaining items on the E2 experience, not the plan's estimates.**

## ⚠ The 0.0599 "fold spread" is not what it has been used as

Found 2026-09-15 while about to run `--all-folds` as a check on the n=6 / n=3 bands. It would have
been worse than useless, and the reason matters for every significance claim on this board.

**`split.py` rotates ONLY the `Oil/>=30%` stratum.** Every other stratum draws with the same seed
regardless of `--fold`, so folds 0, 1 and 2 have **byte-identical validation sets** outside that one
band — measured: 0 scenes differ. So:

- `--all-folds` cannot say anything about the **10-30% band (n=6)**. It scores the same six scenes
  three times.
- For the **>=30% band it leaks.** All 3 of fold 1's held-out scenes and all 3 of fold 2's are in
  fold 0's *training* set. Evaluating a fold-0 checkpoint across folds measures memorisation.

**What 0.0599 actually measures:** one fixed gated checkpoint, scored on three evaluation subsets
differing only in which 3 of 9 heavy scenes are included. That is *evaluation-set sensitivity* — a
real and useful quantity, but **not training-seed variance**.

**Why that matters here:** every comparison on this board (baseline vs E2 vs E2b) holds fold 0
fixed, so the evaluation set is identical and that sensitivity largely cancels. The noise floor
those comparisons actually need is **seed variance, which has never been measured.** 0.0599 is being
used as a conservative stand-in. It is not the matching quantity, and "+0.0609 clears 0.0599" should
not be read as a significance test.

**To measure it properly**, one of:
- **seed variance** — retrain one config with 2-3 seeds, same cache, same fold (~1.3 h per seed);
- **a true fold spread** — train one model *per fold* and score each on its own holdout (3 x ~1.3 h).

Until then, quote the **>=30% band change** (+0.55, far outside anything noise can explain) and treat
pooled movements under ~0.06 as unresolved.

## Incidents

- **2026-09-14 — tile cache overwritten.** `--suffix`/`--normalise` were added to
  `build_cache.py` as CLI flags but never wired to the `run()` call, so a smoke test with
  `--suffix smoke` wrote to `P12`: manifest 2,565 → 9 scenes, index 28,059 → 56 tiles. The suffix
  existed precisely to make a bad rebuild recoverable. Cost: the A/B against the original cache.
  E1's numbers predate it and are unaffected. Both caches now rebuilding with the **same**
  corrected channel order, which isolates normalisation as the only variable.
- **Channel order in the new caches is transposed** relative to every existing checkpoint -
  channel 0 is now VV. Old models are incompatible. Retrains write to **tagged** files only.
- **2026-09-15 - the E2 evaluation read 0.0000 and the model was fine.** Both retrained models
  scored ~0.000 at scene level while training to tile IoU 0.62. Cause: the **Layer 1 classifier**
  is trained on the old convention, returns P(oil) 0.001-0.010 on the new one, and the gate closed
  on every scene. The U-Net was producing 15,591 px over threshold the whole time. Unchecked, the
  conclusion would have been "E2 produces nothing, normalisation is not the problem" - and the
  programme would have been abandoned on a measurement artefact.
  **Fixes:** checkpoints now record `channel_order` / `norm_mode`, `nets.unet_convention()` reads
  it, and `evaluate_val --ungated` takes Layer 1 out of a Layer 2 comparison.
- **A merge reverted the checkpoint-provenance meta block**, which is *why* the transposition went
  unnoticed - a checkpoint that cannot state its own convention is how this happens. Restored.

## Caches on disk, ready to train from

| cache | scenes | tiles | normalisation | note |
|---|---|---|---|---|
| `P12` | 2,570 | 28,129 | median | the baseline |
| `P12sea` | 2,570 | 27,640 | sea-referenced (E2) | 489 fewer tiles, mostly hard negatives |
| `P12seac` | 2,570 | 28,129 | sea-referenced, land excluded from the **reference only** (E2c) | ✅ verified: same sea reference as `P12sea` on every scene that has sea, data mask never smaller, entirely-land scenes recovered rather than deleted |
| `P12seanl` | 2,570 | 28,129 | sea-referenced, land exclusion **OFF** (E2b) | ✅ verified single-variable vs `P12`: identical positives, 13 of 28,129 tiles differ. Measurement only — **never ship a model trained on this**; land in the sea sample is what failed the first two E2 audits |

Both carry the corrected channel order: `vv_med` median **−20.20 dB** against `vh_med` **−32.87**,
i.e. VV is in channel 0, in 99.9% of scenes. The old cache had these transposed.

⚠️ **The two caches differ by TWO changes, not one.** Beyond normalisation, the sea cache's
coastline land mask marks land invalid, so more tiles exceed `MAX_INVALID_FRAC` and are dropped —
6,373 hard negatives against 6,850. Do not report the comparison as isolating normalisation.

## If you are resuming cold

The reasoning lives in docstrings, not in anyone's head. Read these five in this order:

| file | what it explains |
|---|---|
| `pipeline/detect/normalise.py` | the sea-reference estimator, the four discriminators that were tried and falsified, and why a real coastline replaced the brightness heuristic |
| `pipeline/detect/split.py` | why the old split could not see the failure (1 scene ≥30% in validation) |
| `pipeline/detect/evaluate_val.py` | why tile IoU is the wrong metric, and why `--ungated` is mandatory right now |
| `pipeline/detect/oracle_ceiling.py` | how the 0.8446 ceiling is measured and why it decides the whole target |
| `pipeline/detect/build_cache.py::scene_arrays` | the channel order, and that old checkpoints are incompatible with the new caches |

`docs/updates/soumirya.md` carries the narrative; this file is the board.

## Model-swap policy — Soum's instruction, written down because it is easy to get wrong

- Every retrain writes to a **tagged** file. `models/unet.pt` and `models/scene_classifier.pt`
  are **never** written by an experiment. `_baseline` copies sit beside both.
- **The two layers swap as a PAIR or not at all.** A new Layer 1 with an old Layer 2 is exactly
  the mismatch that made the E2 evaluation read 0.0000: the shipped classifier returns
  P(oil) **0.001–0.010** on new-convention input, so the gate closes on every scene.
- A swap happens only when the **gated, end-to-end** val-scene number beats the shipped pair by
  **more than the 0.0599 fold spread** — and then on Soum's call, never silently.

## Resume here — a decision, then E4

Layer 1 is done and the pipeline measures end-to-end. **The next move is a judgement call about the
holdout, not a compute task.**

**The Part III question.** We now hold a complete, coherent configuration: `unet_e2c_sea_refonly` +
`scene_classifier_l1_e2c`. Running Part III would say where we actually stand against 0.85. But A6
says Part III runs ONCE, on a final configuration chosen entirely on validation — and E4, E3 and E5
are still unrun. Spending it now buys a progress number and costs the holdout's independence.
**Soum's call, and Akshat should know either way.**

**If we do not run it, the work continues on validation:**

```bash
# E4 - loss. At 3 seeds, because a single run can no longer detect anything under ~0.08 pooled.
for S in 42 1 2; do
  python pipeline/detect/train_unet.py --epochs 12 --patience 12 --split stratified --fold 0 --cache P12seac --tag e4_focaldice_s$S --seed $S
done
```

**Before E4, read the noise-floor block.** Pooled sd is 0.0267. Select on `macro/scene` or
`mean IoU` (sd ~0.0135, half as noisy) and report pooled. And E5 (seed ensembling) is now arguably
the highest-value item rather than the last, because it attacks the variance that is currently the
binding constraint on measuring anything at all.

**Cheap lever if the gate becomes the bottleneck:** retrain Layer 1 with `--min-recall 0.95`. Part
III oil recall is 0.873, i.e. 19 of 150 oil scenes never reach Layer 2.

---

## Superseded — E2b, the isolation run (kept: the commands are still the pattern)

**Why:** the E2 caches differ three ways, all from the coastline mask — normalisation, 489 fewer
tiles, and 175 fewer source scenes. The audit measured normalisation as *identical* (0.000 shift,
1.000 scale) on the bands that regressed, so the data reduction is the likelier cause. That is
inference, not measurement, and E2b settles it.

```bash
# 1. build_cache.py needs --no-land-mask; _norm() currently hardcodes exclude_land=True in sea mode
python pipeline/detect/build_cache.py --parts 1,2 --normalise sea --no-land-mask --suffix seanl
#    CHECK: P12seanl should match P12 at 28,129 tiles / 2,570 scenes. If it does not, the flag
#    did not take effect — that exact failure already cost one cache (see Incidents).

# 2. same budget and fold as the other two runs
python pipeline/detect/train_unet.py --epochs 12 --patience 12     --split stratified --fold 0 --cache P12seanl --tag e2b_sea_noland

# 3. --ungated is MANDATORY: Layer 1 is stale and closes the gate on everything
python pipeline/detect/evaluate_val.py --fold 0 --ungated     --ckpt pipeline/detect/models/unet_e2b_sea_noland.pt
```

**How to read it:** if E2b keeps the ≥30% gain **and** recovers the regressed bands, the land
exclusion caused the regressions and the fix is clean. If the regressions persist, they are
intrinsic to sea normalisation and the trade is real.

**Then Layer 1.** `--cache`, `--test-cache` and `--tag` are now wired (`4850e43`), so this is
unblocked. Two things were found while wiring it, and both are why it had not been safe to just run:

- the script wrote `models/scene_classifier.pt` **unconditionally** — the file the demo loads. It
  now refuses without `--tag` or an explicit `--overwrite-shipped`.
- the **`P3` cache is stale** (12 Sept, channels transposed). A new-convention classifier scored
  against it returns confident nonsense rather than an error, so the run now aborts on the mismatch.
  **Rebuild P3 before any holdout number**, matching the winning cache's normalisation.

```bash
# only after E2b has named a winner; --tag is mandatory, the shipped pair is not touched
python pipeline/detect/build_cache.py --parts 3 --normalise sea
python pipeline/detect/train_classifier.py --cache <winner> --test-cache P3 --tag l1_<winner>
```

It is a small CNN over 2,570 downsampled scenes, but it evaluates **four variants**. Only after this
does a *gated* number mean anything, and that is the number the swap decision needs.

**Then E4 (loss)** — still promoted above E3. E1's surviving finding: zero of 200 easy positive
tiles exceed 0.99 in *any* config including the shipped one, and it survives removing the
augmentation entirely. Focal γ=2 de-weights already-confident pixels by construction. Focal+Dice
first, then Tversky (α=0.3, β=0.7).

**Read the ≥30% band, not pooled.** Pooled moves less than the 0.0599 fold spread unless that band
moves a lot.
