# Stage 1 — accuracy programme: live status

*Owner: Soumirya. **This file is updated as each item completes** — it is the board, not a log.
The narrative and the reasoning live in `docs/updates/soumirya.md`; this is the one-screen answer to
"where is it".*

**Last updated: 2026-09-15 19:40** — demo done; programme **RESUMED**. E2b cache building.

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

## Status

| item | state | result |
|---|---|---|
| **E0** validation protocol | ✅ **done** | `split.py` + `evaluate_val.py`. Old split had **1** scene ≥30% in validation; now **3**, rotated over 3 folds. Proxy verified faithful (≥30% collapses to 0.17 vs 0.88 below it). **Fold spread 0.0599 — nothing smaller is measurable.** ⚠️ `train_unet` still selects on tile IoU, not val-scene |
| **E8a** oracle ceiling | ✅ **done** | **0.8446** verified independently (agent said 0.838). Boundary decomposition: at ≥30%, **81% of oracle error is within 5 px of the annotator's line** — that band is annotation-limited |
| **E1** channel fix + ablation | ✅ **done — NULL** | Four measurements agree it buys nothing: tile IoU 0.6997/0.6911/0.6994, pooled 0.6606/0.6513/0.6549 (spread 0.0093 vs fold noise 0.0599), ≥30% band 0.26–0.28 in all three. **Hypothesis retired.** Kept the rename for hygiene |
| **E2** sea-referenced normalisation | ✅ **MEASURED — works, with a trade** | **>=30% band 0.282 -> 0.839** (oracle 0.959). Pooled 0.6894 -> 0.7316, inside the fold spread. Four bands regressed, worst -0.161 at 10-30%. Confounded by 175 fewer scenes / 477 fewer hard negatives — isolation run needed. See the result block above |
| **E2b** isolation: sea norm, NO land exclusion | 🔄 **running** | `--no-land-mask` wired and verified (`4850e43`): bit-identical on open ocean, and on the Campeche coastal look-alike valid 0.943 → 1.000, reference moves 0.33 dB. Cache `P12seanl` building. Separates the normalisation fix from the data reduction — without it we cannot say which half produced +0.557, or which caused the regressions |
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

**Price the remaining items on the E2 experience, not the plan's estimates.**

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
| `P12seanl` | *building* | *expect 28,129* | sea-referenced, land exclusion **OFF** (E2b) | measurement only — **never ship a model trained on this**; land in the sea sample is what failed the first two E2 audits |

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

## Resume here — E2b, the isolation run

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
