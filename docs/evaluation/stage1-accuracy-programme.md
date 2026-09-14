# Stage 1 — accuracy programme: live status

*Owner: Soumirya. **This file is updated as each item completes** — it is the board, not a log.
The narrative and the reasoning live in `docs/updates/soumirya.md`; this is the one-screen answer to
"where is it".*

**Last updated: 2026-09-14 05:40** — caches rebuilt, stopped for the night before the retrain.

---

## What this is, and what it is NOT

`docs/team/soumirya-stage1-detection.md` — the Stage 1 task document, **7 phases and a 12-item definition of
done — is COMPLETE**. Nine cases PASS, `detections.geojson` ships for all of them, and the demo
loads none of this work.

This programme is **separate and additive**: it was written after the >85% accuracy target was
set. It is **December work, not demo work.** Nothing in it is on the critical path for
15 Sept 17:00, and nothing in it may overwrite `models/unet.pt` or `models/scene_classifier.pt`,
which are what the demo loads.

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

## Status

| item | state | result |
|---|---|---|
| **E0** validation protocol | ✅ **done** | `split.py` + `evaluate_val.py`. Old split had **1** scene ≥30% in validation; now **3**, rotated over 3 folds. Proxy verified faithful (≥30% collapses to 0.17 vs 0.88 below it). **Fold spread 0.0599 — nothing smaller is measurable.** ⚠️ `train_unet` still selects on tile IoU, not val-scene |
| **E8a** oracle ceiling | ✅ **done** | **0.8446** verified independently (agent said 0.838). Boundary decomposition: at ≥30%, **81% of oracle error is within 5 px of the annotator's line** — that band is annotation-limited |
| **E1** channel fix + ablation | ✅ **done — NULL** | Four measurements agree it buys nothing: tile IoU 0.6997/0.6911/0.6994, pooled 0.6606/0.6513/0.6549 (spread 0.0093 vs fold noise 0.0599), ≥30% band 0.26–0.28 in all three. **Hypothesis retired.** Kept the rename for hygiene |
| **E2** sea-referenced normalisation | 🔄 **caches built — retrain is the next step** | Estimator built, safety gate **PASSES** on 2,570 scenes. Scale was **1.8×–4.2× too wide** on the ≥30% band; bands up to 3–10% untouched (0.000 shift, 1.000 scale). Both caches now on disk, channel order corrected (`vv_med` −20.20 dB, was −32.87). **Retrain not started — deliberately stopped here** |
| **E4** loss — Focal+Dice / Tversky | ⬆️ **promoted, not started** | E1 points here: **zero of 200 easy tiles exceed 0.99** in any config, and focal γ=2 de-weights confident pixels by construction |
| **E3** high-coverage regime | ❌ not started | Only **9** training scenes ≥30%, covering 38% of the holdout's oil mass |
| **E5** TTA + seed ensemble | ❌ not started | Deliberately last — running it early inflates every intermediate comparison |
| **E6** scene conditioning | ⏸ conditional | Only if E2 underdelivers. Same argument as E2, so likely redundant if E2 works |
| **E7** architecture | ⛔ **not doing** | The dominant error is an input-representation failure, invariant to architecture |
| **E8c** annotation ceiling + our-cases GT | ❌ not started | Human time approved. Decides whether 0.85 is a target or a mirage |

### Carry-overs outside both plans

| item | state |
|---|---|
| Python **3.13.5** vs the pinned **3.11** | ❓ open — Akshat's call. Only item that could break Stage 1 on another machine |
| `contrast_centre_db` / `contrast_edge_db` | ❓ dropped for demo; Anushka needs it for the weathering flag. ~10 lines, works on 11 of 12 oil features |
| **170 of 1,370 non-oil scenes are entirely land** | ⚠️ unreported to Akshat — "look-alike rejection 0.940" is partly measured on farmland |

---

## Running log of what each item actually cost

| item | estimated | actual | note |
|---|---|---|---|
| E0 | ~4 h | ~4 h | on target |
| E2 safety gate | **~15 min** | **~1 day** | **5 audit iterations.** Four of the five failures were my measurement, not the fix |
| E8a | ~1 day | ~1 h | faster than planned |
| E1 | ~1 h + 3 runs | ~6 h | 3 training runs + 3 scene evals |

**Price the remaining items on the E2 experience, not the plan's estimates.**

## Incidents

- **2026-09-14 — tile cache overwritten.** `--suffix`/`--normalise` were added to
  `build_cache.py` as CLI flags but never wired to the `run()` call, so a smoke test with
  `--suffix smoke` wrote to `P12`: manifest 2,565 → 9 scenes, index 28,059 → 56 tiles. The suffix
  existed precisely to make a bad rebuild recoverable. Cost: the A/B against the original cache.
  E1's numbers predate it and are unaffected. Both caches now rebuilding with the **same**
  corrected channel order, which isolates normalisation as the only variable.
- **Channel order in the new caches is transposed** relative to every existing checkpoint —
  channel 0 is now VV. Old models are incompatible. Retrains write to **tagged** files only.

## Caches on disk, ready to train from

| cache | scenes | tiles | normalisation | note |
|---|---|---|---|---|
| `P12` | 2,570 | 28,129 | median | the baseline |
| `P12sea` | 2,570 | 27,640 | sea-referenced (E2) | 489 fewer tiles, mostly hard negatives |

Both carry the corrected channel order: `vv_med` median **−20.20 dB** against `vh_med` **−32.87**,
i.e. VV is in channel 0, in 99.9% of scenes. The old cache had these transposed.

⚠️ **The two caches differ by TWO changes, not one.** Beyond normalisation, the sea cache's
coastline land mask marks land invalid, so more tiles exceed `MAX_INVALID_FRAC` and are dropped —
6,373 hard negatives against 6,850. Do not report the comparison as isolating normalisation.

## Next session — exact commands

```bash
# baseline and E2, same budget, same stratified fold, TAGGED outputs
python pipeline/detect/train_unet.py --epochs 12 --patience 12     --split stratified --fold 0 --tag base_median          # trains from P12
python pipeline/detect/train_unet.py --epochs 12 --patience 12     --split stratified --fold 0 --tag e2_sea               # NEEDS --cache P12sea (not yet wired)

python pipeline/detect/evaluate_val.py --fold 0 --ckpt pipeline/detect/models/unet_base_median.pt
python pipeline/detect/evaluate_val.py --fold 0 --ckpt pipeline/detect/models/unet_e2_sea.pt
```

**`train_unet.py` has no `--cache` flag yet** — it hardcodes `TileStore("P12")`. That is the first
edit of the next session, before any training.

**Read the ≥30% band, not the pooled number.** Pooled moves by less than the 0.0599 fold spread
unless that band moves a lot. Today it sits at 0.26–0.28; the oracle says 0.959 is available.
