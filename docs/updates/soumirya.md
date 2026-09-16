# Soumirya — update log

*Newest entry at the TOP. Copy the block from `TEMPLATE.md`, fill four lines, commit it with
your code in the same push. Two minutes after each phase — non-negotiable.*

**Why:** your AI has no memory between chats. This file is the memory. It means you can close a
chat, switch from Claude to ChatGPT, hand your work to someone else, or come back after sleeping,
and lose nothing.

**To resume from it:** *"Here are the master plan, my task document, and my update log. Read the
top entry and tell me exactly where I left off and what the next step is."*

---

## [2026-09-16 12:30] P2 + P3 — Python pinned to 3.13, and the nine-figure evidence set

**Done:**

**P2 — the pin is 3.13.** Akshat ruled. `requirements.txt` and `CLAUDE.md` both said 3.11; every
model here was trained and is served on **3.13.5 / torch 2.6.0+cu124 / torchvision 0.21.0+cu124 /
CUDA 12.4**, so the docs described an environment nobody was running. Moving the models the day
before the demo is the riskier option, so the documentation moved. Full resolved table written to
`docs/receipts.md` with the one-line command that reproduces it. **Harshita is unblocked.**

It matters beyond tidiness: the checkpoints are `torch.save` pickles, and loading them under a
materially different torch is the class of failure that does not raise — it returns weights that
load and behave differently.

**P3 — nine figures, `pipeline/detect/make_figures.py` → `docs/evaluation/figures/stage1/`.**
200 dpi PNG, every caption printing its **source path** and its **split**, n on every bar. Nothing
is recomputed from a model — every number is read from a committed results file, so a figure can
never silently disagree with the deck.

| # | proves |
|---|---|
| F1.1 | 139/11/11/289 → accuracy 0.951, oil recall 0.927, look-alike 0.940, clean-ocean 0.987 |
| F1.2 | the threshold was set on **validation**, not on the test set |
| F1.3 | the gate costs 0.014 IoU, buys 0.48 look-alike rejection |
| F1.4 | 0.4349 is the strictest of eight; the literature's definition gives **0.6871** |
| F1.5 | the coverage cliff — and **no demo case sits in the failure band** |
| F1.6 | Cerulean agreement, median IoU 0.483, recall 0.796–0.942 |
| F1.7 | second polarisation: val F1 0.346→0.643, Part III precision 5.8× at identical recall |
| F1.8 | rule margin in dB, 12 detections, **7 clear / 5 marginal** |
| F1.9 | oracle ceiling 0.8446 — and **we beat it on 3 of 5 bands** |

**One thing I would not fake, and it is labelled on the figure.** F1.2 needs a PR *curve*, and the
shipped classifier's validation probabilities are **not recoverable** — it was trained on the
pre-14-Sept cache, which was rebuilt with the corrected channel order. So the curve is drawn from
the reproducible `l1_e2c` classifier, and the shipped model appears as a **single operating point
computed from its own stored confusion matrix**. Both are labelled on the axes. Drawing the shipped
curve on the new cache would have looked better and been a fabrication.

**Checked by eye, not just by exit code** — the farmland incident was found only by opening the
image. Fixed three layout faults that a glance caught: F1.2 had every operating point crushed into
one corner (now zoomed to recall ≥0.84 with leader lines), F1.4's range label sat on the title, and
F1.8's annotations sat on the bars.

**Files:** `pipeline/detect/make_figures.py` (new), `docs/evaluation/figures/stage1/*` (9 PNG +
README), `requirements.txt`, `CLAUDE.md`, `docs/receipts.md`

**Run:** `python pipeline/detect/make_figures.py`

**Open:** P3 acceptance asks the figure numbers be cross-checked against
`docs/evaluation/deck-numbers.md` — every figure reads from the same JSON that file cites, so they
cannot drift, but a human should still eyeball the deck once. Handoffs to Harshita (figures) and
Jaiveer (land-masked contacts + per-case pixel area) are ready.

## [2026-09-16 11:40] P1 — land-masked the ship contacts: 142 → 110

**Done:** Routed the ship detector through a **real coastline** instead of the brightness-inferred
land mask. `darkspot.prepare()` already had an `external_land` parameter for exactly this; `run.py`
was calling it without one, so contacts were being filtered only by a brightness heuristic that
(a) over-flags dark scenes and (b) misses a radar-dark shore entirely.

| case | before | after | coastline land |
|---|---|---|---|
| jacksonville | 2 | 2 | 0.0% |
| farallones | 0 | 0 | 0.0% |
| huntington | 43 | 43 | 0.7% |
| gulf-alaska | **0** | **0** | 0.0% |
| mumbai | 21 | 21 | 0.0% |
| jamnagar | 3 | 3 | 0.0% |
| **ennore** | **72** | **41** | **26.3%** |
| **lookalike-zenodo** | **1** | **0** | **59.0%** |
| nospill-zenodo | 0 | 0 | 0.0% |
| **TOTAL** | **142** | **110** | **32 land contacts removed** |

**The brief's hypothesis was right for Ennore and wrong for Huntington.** I checked every export
box against real geography before trusting the mask:

- **Ennore** 80.28–80.45 E, 13.10–13.30 N → **26.3% land**, the Chennai coast. 31 contacts removed.
- **Huntington** −118.17 to −118.05 W → **0.7% land**; the box is 99.3% water and the east edge only
  clips the shore. **Its 43 contacts are NOT land returns.** Brightest is **+23.5 dB**, which is a
  hard target, not a wave crest — this is a busy harbour approach.
- **Mumbai** 72.09–72.27 E, 18.40–18.61 N → **0.0%**, ~50 km SW of the city in open sea.
- **Jacksonville** −79.68 W, 30.2–30.6 N → **0.0%**, ~190 km offshore.
- **Alaska stays at zero.** Unchanged, as required.

**⚠ `case-lookalike-zenodo` is 59% land**, and its single contact sat on it. That is the same shape
of problem as the farmland scene that got `nospill-zenodo` replaced. **Case selection is Akshat's —
flagging, not acting.**

**Verified before committing:** every **oil feature is byte-identical** across all nine bundles —
only `ship_detections` changed, in 2 files. `k_sigma` unchanged at **4.0**. No bundle hand-edited.

**Contact brightness after the mask** (the brief's second gate):

| case | n | max dB | median | min |
|---|---|---|---|---|
| jacksonville | 2 | −7.34 | −7.74 | −8.13 |
| huntington | 43 | +23.47 | +0.81 | −9.49 |
| mumbai | 21 | +17.17 | +3.68 | −6.94 |
| jamnagar | 3 | +8.74 | +2.63 | −2.02 |
| ennore | 41 | +22.21 | −2.09 | −6.12 |

**Files:** `pipeline/detect/run.py`, `cases/case-ennore-lookalike-2023/detections.geojson`,
`cases/case-lookalike-zenodo/detections.geojson`

**Run:**
```bash
python pipeline/detect/run.py --case <id> --rule-contrast -3.0 --rule-elongation 2.5
python pipeline/export/build_case.py --case <id> --stage detect
python scripts/validate_case.py cases/<id>     # 9/9 PASS
```

**Open — for Akshat:**
1. **`ship_detections` has no m² field.** Per 1.3 I did **not** add one (do not extend a schema
   unilaterally). Per-case pixel area is computed and handed to Jaiveer instead: **50.7 m²
   (Alaska) to 97.4 m² (Ennore), 1.92× spread**; `MIN_PX=4` → **203–389 m²**. `est_length_m` stays
   `null`.
2. **No `detections.geojson` carries a `meta` block at all** — `meta` is `null` in all nine. So
   `meta.provenance` is absent everywhere and D33 routes every case to `satellite`/classical. That
   matches the brief, **but `soumirya_case_nominations.md` states the two Zenodo cases "are
   benchmark-provenance, so run.py routes them to Layer 1 + Layer 2" — which is false as the
   bundles stand.** Either the doc or the bundles needs correcting.
3. **The brief's `case-nospill-zenodo` = 31 contacts is stale.** It is **0**, and has been since the
   farmland scene was replaced with `P3_No oil_00027`.

## [2026-09-16 09:40] P0 — deck corrections from Akshat's final-day brief

**Done:** Worked P0 of the final-day brief. Two of the three items were already closed by earlier
work; the third had two LIVE instances, one of them worse than the brief described.

- **0.1 "23% accuracy" — already struck.** Confirmed by grep across `docs/`, `web/` and the eval
  JSON/CSV. The only surviving `23` in Stage 1 context is `receipts.md:307` and `akshat.md:307`,
  both of which record that the figure does not exist. Stage 2's `0.23 h` overhang on `case-000`
  and a `scheduler@0.23.2` entry in `web/package-lock.json` are unrelated. **No action needed.**
- **0.2 `soumirya_case_nominations.md` — already corrected 13 Sept.** The file reads **0.940** and
  carries an explicit note recording the trade (rejection 0.960 → 0.940 bought oil recall
  0.893 → 0.927 and accuracy 0.947 → 0.951). **No action needed.**
- **0.3 two dead claims — FIXED, two live instances:**
  - `docs/architecture/stage1-detection.md` stated in its **Traps** list, as current fact: *"Band 1
    is VV, band 2 is VH. VH is the strongest feature."* **Both halves are wrong**, and the band-order
    half is the more dangerous one — a traps list is exactly where someone goes to check. Replaced
    with the measurement: over 297 Part III scenes Zenodo's band 1 runs **8.15 dB darker** and is
    darker in **290 of 297**, so Zenodo is band 1 = VH and the GEE exports are band 1 = VV. Decide
    from pixels, never the filename.
  - `docs/team/jaiveer-stage3-attribution.md` carried *"Soumirya's finding is that VH is the
    strongest single discriminator"* — inside a section headed **"this is your slide"**. Replaced
    with the channel-agnostic ablation (val F1 0.346 → 0.643, Part III precision 5.8x at identical
    recall, 4/36 both ways) and an explicit "do not name a polarisation on this slide".

**Also checked, and clean:** `web/src/` contains **no** hardcoded accuracy figures and none of the
dead claims — the UI reads from JSON as designed, so no deck number can drift there.

`deck-numbers.md` already lists both dead claims in its "dead claim" column, which is correct.
Remaining hits in `docs/updates/*.md` are historical log entries superseded by newer ones at the
top of each file; logs are append-only and were left as history.

**Files:** `docs/architecture/stage1-detection.md`, `docs/team/jaiveer-stage3-attribution.md`

**Run:** `grep -rniE "VH is the (strongest|discriminator)" docs/ web/ --include=*.md --include=*.html`

**Open:** P1 (land-mask the contacts), P2 (Python 3.13 ruling — Harshita is blocked on this),
P3 (nine figures). A Layer 1 `--min-recall 0.95` run was already in flight when the brief arrived;
it writes **tagged files only**, touches no shipped model, and its result stays out of the deck.

## [2026-09-14 20:10] Phase — Alaska ship_detections: why it is empty, and the px -> m question

**Done:** Answered both of Jaiveer's Stage 3 blockers with measurements, no code changed.
## [2026-09-14 04:10] Phase 7.3 — E1 closed as a NULL result; and I destroyed the tile cache

### E1 — the channel fix buys nothing. Four measurements agree.

Three configs, 12 epochs each, same stratified fold, same budget:

| config | tile IoU | confidence | pooled (scenes) | ≥30% band |
|---|---|---|---|---|
| **A** ch1 p=0.25 — the shipped bug | 0.6997 | 0.8860 | 0.6606 | 0.2821 |
| **B** ch0 p=0.10 — correct channel | 0.6911 | 0.8685 | 0.6513 | 0.2612 |
| **C** p=0.00 — no cross-pol dropout | 0.6994 | 0.8398 | 0.6549 | 0.2678 |

Pooled spread **0.0093** against a measured fold spread of **0.0599** — identical within noise by
a factor of six. The ≥30% band sits at 0.26–0.28 in all three, so the failure is untouched.

**The hypothesis was wrong and is retired.** "25% of training steps destroy the signal channel"
sounded like a major finding; measured, it is worth nothing. Note this is a DIFFERENT
manifestation from the inference-side channel bug, which was real and large (P(oil) 0.002 → 0.999
on live cases). Same root cause, opposite significance — only the inference one mattered.

**What did come out of it:** the underconfidence is real and systemic — **zero of 200 easy
positive tiles saturate above 0.99, in all four configs including the shipped one**, and 6% never
cross 0.5 despite being ≥30% oil. Since it survives removing the augmentation entirely, the
remaining suspect with a mechanism is **focal loss at γ=2**, which by construction de-weights
pixels the model is already confident about. **E4 is promoted above E3.**

Config C cut the never-crosses-threshold tail from 6% to 1% at a slightly lower mean. For
whole-scene IoU the tail is what matters — a scene dies when nothing crosses 0.5 — but it did not
show up at scene level, so it is noted rather than adopted.

### ⚠ I overwrote the tile cache, and the safety mechanism is what failed

`--suffix` and `--normalise` were added to `build_cache.py` as CLI flags but **never wired to the
`run()` call** — the edit that would have done it sat in a script that raised before writing. So a
"safe" smoke test with `--suffix smoke` wrote straight to `P12`: manifest **2,565 → 9 scenes**,
index **28,059 → 56 tiles**.

The suffix existed precisely so a bad rebuild would be recoverable. **An accepted argument that
changes nothing is worse than no argument**, and that is now a comment at the call site.

**Cost:** the ability to A/B against the original cache. The E1 checkpoints and every number above
are unaffected — measured before the overwrite, and the running eval had already loaded the good
manifest (it reports 387 held-out scenes, not 2). `manifest_P12.json` also feeds `split.py`, so it
had to be restored regardless.

**Recovery, which is not wasted work — the rebuild was next anyway:** both caches are being rebuilt
with the SAME corrected channel order, which is a cleaner comparison than originally planned
because it isolates normalisation as the only variable:
- `P12` — median normalisation, the baseline
- `P12sea` — sea-referenced, plan E2

**Channel order in both is transposed relative to every existing checkpoint** (channel 0 is now
VV). Old models are incompatible with the new caches — retrain, do not mix. Retrains must write to
a TAGGED file: `models/unet.pt` is what the demo loads and is not to be overwritten.

**Demo safety, stated explicitly:** the demo is 15 Sept 17:00. Nine cases PASS, their
`detections.geojson` came from the classical path and do not involve the U-Net at all, and
`unet.pt` / `scene_classifier.pt` are untouched with `_baseline` copies beside them. Nothing in
this programme is on the demo's critical path.

**Next:** rebuild finishes → retrain on `P12sea` vs `P12` → E4 loss ablation.

---

(1) The threshold that produced Alaska's empty list is **-8.06 dB** = sea -18.30 + 4.0 x 2.561,
i.e. the scene-relative term, NOT the -10 dB floor. The brightest water pixel in the entire tile
is -8.79 dB = **3.71 sigma**, so nothing clears the bar anywhere in the scene — this is not one
missed vessel. Swept k_sigma 4.0 -> 1.0: nothing appears until k<=3.25, where the -10 dB floor
clamps and 3 contacts of 4-6 px surface at 7.2/9.1/10.0 km from the slick centroid, peaks
-8.79/-9.66/-9.84 dB. Below k=3.25 the floor caps it and nothing further changes.
Cross-case evidence that those 3 are not vessels: on all six cases that DO yield contacts the
brightest sits at **+8.7 to +23.5 dB (11.2-17.5 sigma)**, and the faintest non-empty case
(Jacksonville) is -7.34 dB / 5.8 sigma. Alaska tops out below every one of them.
**The bigger finding is field of view, not threshold:** the export box is 7.96 x 11.81 km = 94 km2.
Only **40.8%** of the 4.5 km ring around the slick centroid is inside the raster, and Cerulean's
dark-vessel module searches 50 km (~7,850 km2) — we hold **1.2%** of that area. Recommendation:
keep k=4.0; a wider re-export is the only honest lever, and it is Akshat's call.
(2) px_area cannot be converted to a length. Measured ground pixel area across the nine cases
runs **50.7 - 97.4 m2 (1.92x spread)** because the exports use a fixed DEGREE step, so ground
pixel size is cos(lat)-dependent: 5.07 x 9.93 m at Alaska (59.6N) vs 9.74 x 9.93 m at Ennore
(13.2N). A fixed px_area floor is therefore a different physical size on every card. Ruling given
to Jaiveer: report footprint area in m2 (px_area x the case's own pixel area — a unit conversion,
legitimate), keep `est_length_m: null` (validator requires only lon/lat/score on dark_vessels, and
rule 4 says not-applicable is null), and state the size floor as the detector's existing MIN_PX=4,
which is 203 m2 (Alaska) to 390 m2 (Ennore) of radar footprint.

**Files touched:** none in `pipeline/` or `cases/` — diagnostics only, run from the scratchpad.
`docs/updates/soumirya.md` (this entry).

**Run command:**
```bash
python pipeline/detect/run.py --case case-gulf-alaska-2023 --rule-contrast -3.0 --rule-elongation 2.5
```
Expected output: `[detect] ships  : 0 bright radar contact(s)` followed by
`threshold -8.06 dB (sea -18.3 +/- 2.561); 0 candidate(s)` and the empty-list note. Add
`--ship-k-sigma 3.25` to reproduce the 3 sub-threshold contacts — **diagnostics only, do not ship
a bundle built that way.**

**Checkpoint artefact:** sigma-level table across all nine cases and the k_sigma sweep, sent to
Jaiveer 20:10.

**Open issues:**
- **Governance:** D34 already logged this exact finding on 13 Sept (threshold -8.06, peak -8.79)
  and ruled Alaska's dark-vessel contact is Cerulean's, never a UDGAM detection. Lowering k until
  Alaska yields a contact at a documented offset would be choosing a threshold against a sealed
  answer on a case already marked partially compromised (Part 16). Not done, and should not be.
- `cases/case-gulf-alaska-2023/meta.json` says "Exported raster is 1573 x 1190 at 10 m". It is
  1573 x 1190 at **5.07 x 9.93 m** — the same note warns to check the aspect ratio. Akshat's
  export script should be corrected at source, not the bundle hand-edited.
- `ships.py:_merge_and_project` derives `pixel_size_m` from `transform.a` only, so the 50 m merge
  radius is 50 m in x but **98 m in y** at Alaska (aspect 1.96). Harmless on the other eight cases
  (aspect 1.02-1.26) and it changes no current output. Deferred until after the demo on purpose.
- px_area -> length CAN be calibrated honestly: NOAA AIS carries a `Length` column
  (`pipeline/attribute/tests.py:50`), so Huntington's 43 contacts could be matched to AIS at scene
  time and footprint area regressed against real lengths. I cannot run it — no AIS on this machine.
  Jaiveer's half, post-demo.

**Next:** wait on Akshat re the Alaska export box; otherwise Alaska ships with `ship_detections: []`
and the silence argument stated on the slide.

---

<!-- Your first entry goes here. Setup counts as a phase: what you installed, what ran, what
     printed PASS, what is still broken. -->

## [2026-09-14 01:20] Phase 7.2 — E8a: the ceiling verified, and 0.85 looks reachable after all

**Done:** Plan E8a. `pipeline/detect/oracle_ceiling.py`, run over 228 Parts I+II oil scenes.
**No Part III pixel was read** — the ceiling is measured on the training halves and re-weighted
by Part III's band oil-mass, so the holdout stays untouched.

### The ceiling reproduces independently: **0.8446** (planning agent: 0.838)

The oracle cheats in exactly one way — it takes the sea reference **from the GT mask**.
Everything else is deliberately stupid: one band, one Gaussian blur (σ=3), one global threshold
(best: sea − 2.25σ), no texture, no shape, no context, nothing learned.

| band | n | oracle IoU | P3 oil mass | weighted |
|---|---|---|---|---|
| 0–1% | 61 | 0.4387 | 0.0071 | 0.0031 |
| 1–3% | 59 | 0.6601 | 0.0509 | 0.0336 |
| 3–10% | 60 | 0.7429 | 0.1949 | 0.1448 |
| 10–30% | 39 | 0.8123 | 0.3643 | 0.2959 |
| ≥30% | 9 | **0.9590** | 0.3829 | 0.3672 |
| | | | **CEILING** | **0.8446** |

Top two bands agree closely with the agent's figures (0.812 vs 0.827; 0.959 vs 0.961) and they
carry the weight. The light bands differ more but are worth 0.7% and 5.1% of the metric.

### The finding that changes the outlook

| band | ours (Part III) | oracle | beats oracle? |
|---|---|---|---|
| 0–1% | 0.6685 | 0.4387 | **YES** |
| 1–3% | 0.7566 | 0.6601 | **YES** |
| 3–10% | 0.7826 | 0.7429 | **YES** |
| 10–30% | 0.6595 | 0.8123 | no |
| **≥30%** | **0.0848** | **0.9590** | no |

**The model already beats a GT-informed threshold on three of five bands.** It is not broadly
weak. It fails precisely and only where the normalisation is broken — the two bands holding
**74.7%** of Part III's oil mass.

Arithmetic, if the fix lands those two bands on their ceilings:

```
pooled today (band-weighted reconstruction)  0.4685   (measured 0.4349)
if the top two bands reach their ceilings    0.8589
full oracle everywhere                       0.8446
```

**0.8589 is above the 0.85 target**, and above the full-oracle figure, because we out-perform
the oracle in the light bands. **This revises the plan's ~15% estimate for reaching 0.85 sharply
upward** — the plan assumed we could not reach the heavy-band ceilings; it did not notice we
already beat the oracle everywhere the data is adequate.

**It is a projection, not a measurement, and it is conditional.** It assumes the fix matches a
GT-informed threshold in both heavy bands, which is demanding. The ≥30% ceiling rests on 9
scenes. And the "ours" column is Part III while the oracle is Parts I+II, so the populations
differ slightly.

### Boundary decomposition — where the ceiling comes from

Share of oracle error lying within m px of the GT boundary:

| band | 2px | 5px | 10px | 15px |
|---|---|---|---|---|
| 1–3% | 0.31 | 0.67 | 0.86 | 0.90 |
| 3–10% | 0.29 | 0.63 | 0.83 | 0.88 |
| 10–30% | 0.37 | 0.63 | 0.77 | 0.83 |
| **≥30%** | **0.56** | **0.81** | 0.89 | 0.92 |

At ≥30% coverage, **81% of the oracle's residual error is within 5 px of the annotator's line**
— that band's 0.959 is already annotation-limited, and no method will do much better there. The
0–1% band is the opposite (0.19 at 5 px): its errors are whole missed objects, not edges, which
is why the oracle scores 0.44 there and we score 0.67.

**Next:** E1 — the channel-order fix and the augmentation ablation, which is the cheapest
remaining item and the one with a fast read-out (max probability on easy positive tiles should
move from ~0.85 toward >0.97).

---

## [2026-09-13 23:55] Phase 7.1 — accuracy programme, Week 1: both gates pass

**Done:** Plan E0 and E2's safety gate. No cache rebuilt, no model retrained, nothing in
`cases/` touched. New files: `pipeline/detect/normalise.py`, `split.py`, `evaluate_val.py`.

### E2 gate — PASS, on the fifth attempt

Final audit, all 2,570 Parts I+II scenes:

| population | n | p99 \|Δref\| | med scale × | p99 scale × |
|---|---|---|---|---|
| no oil | 1200 | 5.33 | 1.000 | 2.921 |
| 0–1% | 356 | **0.000** | **1.000** | **1.000** |
| 1–3% | 501 | **0.000** | **1.000** | **1.000** |
| 3–10% | 295 | **0.000** | **1.000** | **1.000** |
| 10–30% | 39 | 0.000 | 1.000 | 1.803 |
| **≥30%** | 9 | **4.988** | **2.219** | **4.127** |

The 93% that already work are untouched in both reference and scale; the target band moves
hard; no overridden reference lands off the ocean.

**The headline mechanism is a SCALE error, not a reference error.** The plan framed this as
"the slick becomes its own median". That is true for only **4 of the 12** failing Part III
scenes (>50% coverage). For the other **8** the median is still in the sea and the scale is
1.8×–4.2× too wide, compressing normalised contrast to ~40% of true. Both are now handled,
separately: `full-override` when the dark mode is genuinely the majority, `scale-only`
otherwise — and scale-only cannot move a reference onto land, which is most of the safety.

### Four of the five gate failures were my measurement, not the fix

Worth recording, because it re-prices the remaining plan items:

1. Iterative sigma-clipping cannot escape a dark mode that **is** the bulk — 99.6% kept,
   converged in one iteration at −31.74 dB against a true sea of −27.00. **Real design flaw**,
   caught by the self-test before it ever touched data.
2. The brightness land mask **ate the sea**: 31–65% of a land-free majority-oil scene flagged
   as land, because its reference is the p20 of local means, which sits inside the slick once
   oil is the bulk. **Real bug.** Modes collapsed 2→1 on seven of nine and the fix silently
   stopped firing on exactly the scenes it exists for.
3. My gate measured only the reference shift — could never pass, see above. **My error.**
4. My gate demanded no-oil scenes never move. Wrong in conception: a large dark patch is what
   *makes* a look-alike, so a coverage-adaptive estimator is supposed to re-reference them.
   **My error.**
5. My leak check tested references the estimator had never touched, flagging bands whose
   measured shift was 0.000. **My error.**

Before the coastline fix I tried and **falsified four discriminators**, all measured: MAD-ratio
roughness (land 0.27–0.97, overlapping), a shift cap (swept 9→5 dB, never separates), local
texture (land 2.11, oil 1.94, ocean 1.41), and land-mask coverage (a clean-ocean scene scored
67.7%). The answer was not a threshold: **use a real coastline.** `global-land-mask==1.0.0` was
already pinned at `requirements.txt:62` and merely uninstalled, so this adds no dependency.

**Plan estimate was off by an order of magnitude** — E2's "~15 min safety check" took a day.
Price the remaining E-items accordingly.

### E0 gate — the proxy is faithful, and is NOT a Part III predictor

Old split gave validation **1** scene ≥30% and **3** at 10–30%, out of 190 — blind to ~75% of
Part III's oil mass. `split.py` gives 3 and 6, with the 9 large-slick scenes rotated over 3
folds. Re-scoring the shipped checkpoint (fold 0, 387 held-out scenes):

pooled **0.6350**, CI [0.523, 0.744], macro/scene 0.6945, mean IoU 0.8108

| band | n | IoU |
|---|---|---|
| 0–1% | 53 | 0.6120 |
| 1–3% | 75 | 0.7047 |
| 3–10% | 44 | 0.7865 |
| 10–30% | 6 | 0.8832 |
| **≥30%** | **3** | **0.1714** |

The failure signature reproduces unmistakably — a 5× cliff into the top band. But pooled 0.635
is **not** comparable to Part III's 0.435: only 3 scenes sit in the collapsed band here versus
12 there, so it carries far less pooled weight, and 10–30% is genuinely easier on this
population (0.883 vs 0.660). **Use this metric for measuring change, never for predicting the
Part III value**, and do not quote a val delta as a Part III delta.

**3-fold rotation result — and the measurement floor is uncomfortably high.**

| fold | pooled | 95% CI | ≥30% band (n=3) |
|---|---|---|---|
| 0 | 0.6350 | [0.523, 0.744] | **0.1714** |
| 1 | 0.6252 | [0.493, 0.760] | **0.2737** |
| 2 | 0.6851 | [0.589, 0.761] | **0.4286** |
| | mean **0.6484**, spread **0.0599** | | mean ~0.29, range **0.257** |

Every other band is identical across folds (0.6120 / 0.7047 / 0.7865 / 0.8832), which confirms
the rotation touches only the ≥30% assignment as intended. But that band swings **0.17 to 0.43
on three scenes** — a 2.5× range. **Nothing below ~0.06 pooled, or a large move in the ≥30%
band, is measurable on this proxy.** The expected effect (a 2.2× scale correction) should clear
that comfortably; a modest one would not be distinguishable from fold noise.

**⚠ The baseline ≥30% numbers above are LEAKY and flatter the baseline.** The shipped checkpoint
was trained with the old `train_test_split(uniq, 0.15, random_state=42)`, which put **8 of the 9**
≥30% scenes into training. So most of what fold 0/1/2 "hold out" was in that model's training
set — and it still scores 0.17–0.43, which is the point. Every retrained model from here must use
`split.py`, or the comparison is not like-for-like.

### Dataset findings worth knowing independently of any retrain

- **170 of 1,370 non-oil scenes (12.4%) are entirely land** once a real coastline is applied.
  Look-alike rejection of 0.940 is partly measured on farmland. That is the third land scene
  after `No oil/00091` (already replaced as a demo case) and `No oil/00487` (100% land).
- Every Zenodo tile **is** georeferenced (EPSG:4326, real geotransform) — `land_mask_geo.py`'s
  claim that "the Zenodo scenes have no reliable land information" is false and should be
  corrected when that file is next touched.

**Next:** E8a (re-verify the 0.838 oracle independently — the ceiling claim the whole plan
leans on), then the E1 channel-fix ablation.

---

## [2026-09-13 22:15] Phase 6.8 — the networks DO transfer. It was a channel-order bug, and I had it wrong.

**Akshat asked whether he needed to re-export the cases in Zenodo's format. The answer is no — his
exports are correct. But the question sent me to compare the two side by side, and there is a bug.
It is in how we read the Zenodo files, not in his exports.**

**Nothing was retrained and no bundle was touched** (his §3 rule). All work in `scratch/`.

### The finding

Over ocean, cross-pol is always below co-pol — 6–10 dB below, by physics. Across **297 Part III
scenes**, Zenodo's **band 1 is 8.15 dB DARKER than band 2**, and band 1 < band 2 in **290 of 297**.
Band 1 median-of-medians is **−28.21 dB**, band 2 is **−20.12 dB**.

- Band 1 sits exactly where VH belongs. Band 2 sits exactly where VV belongs.
- **Zenodo is band 1 = VH, band 2 = VV.**
- `build_cache.py:107-108` and `make_labels.py:151` read band 1 as VV. So does everything built
  from them.
- Akshat's GEE exports are band 1 = VV, band 2 = VH — **correct**, and confirmed by the physics
  (farallones VV −18.0 / VH −27.0; huntington −20.2 / −27.8; alaska −18.3 / −27.3, all a clean
  +7.6 to +9.0 dB co-pol-over-cross-pol).

So the networks were trained with the channels in one order and shown the other order at inference.

### What happens when the channels are matched

| case | P(oil) as shipped | P(oil) corrected | U-Net px as shipped | corrected |
|---|---|---|---|---|
| jacksonville | 0.0019 | **0.9992** | 0 | 41,598 |
| mumbai | 0.0050 | **0.9999** | 0 | 63,922 |
| farallones | 0.0016 | **0.9993** | 0 | 21,396 |
| jamnagar | 0.0028 | **0.9997** | 0 | 15,710 |
| gulf-alaska | 0.0023 | **0.9575** | 0 | 10,125 |
| huntington | 0.0141 | **0.8364** | 0 | 15,644 |
| **ennore (look-alike)** | 0.0103 | **0.0021** | 0 | **0** |

Every spill case fires. **The look-alike still rejects, and rejects harder than before.** That last
row is what makes this a fix rather than a threshold being blown open.

### ⚠️ This invalidates a large block of my own earlier work

I concluded the networks "do not transfer to GEE exports" and built a decision on it. **That
conclusion was wrong.** They transfer fine. Everything I ruled out one at a time — VH noise floor,
ground scale at 80/60/40 m/px, bright-ship masking, nodata fill, slick size, domain augmentation —
was chasing a symptom of a channel swap. The domain-augmentation retrain that moved Huntington
0.0025 → 0.0141 was treating the wrong disease.

**D33 provenance routing was built on this false premise.** It still produces correct output, but
its stated justification is now wrong.

### What it does NOT change: the demo decision still stands, for a different reason

Layer 2 with corrected channels, against Cerulean:

| case | Layer 2 | classical | |
|---|---|---|---|
| jacksonville | **0.504** | 0.483 | L2 ahead |
| jamnagar | **0.613** | 0.452 | L2 ahead |
| mumbai | 0.681 | **0.728** | classical ahead |
| farallones | 0.344 | **0.624** | classical ahead |
| gulf-alaska | 0.024 | **0.165** | classical ahead |
| **median** | **0.504** | **0.483** | |

Ahead on the median by 0.021, **behind on three of five cases**. That is not a clear win, and
swapping the live pipeline 29 hours from freeze for +0.021 median while losing three cases is a bad
trade. **Recommend live cases stay classical** — now on evidence rather than on a false premise.

The two are complementary, which is worth a sentence in the deck: classical has recall 0.80–0.94
but precision 0.17–0.76 (over-extends); Layer 2 has precision 0.76–0.92 but recall 0.37–0.73
(under-extends).

### ⚠️ What it DOES break: two claims that must come off the deck as written

1. **"VH is the discriminator" — the novelty slide.** The feature named `vh_mean_depth_db`
   (importance 0.3155, rank 1) was computed from Zenodo **band 2, which is VV**. The channel names
   in the feature importances are swapped. **What survives:** adding the second polarisation
   nearly doubled validation F1 (0.346 → 0.643) and raised Part III precision 5.8× at identical
   recall. That ablation is real and channel-agnostic. **What does not survive:** naming which
   polarisation did it, and the physics story attached to that name.
2. **"The networks do not transfer to real Sentinel-1 exports."** Delete it. It is false.

**Benchmark numbers are unaffected** — training and evaluation both used the same (mislabelled)
convention, so 0.951 scene accuracy and 0.435 IoU are internally consistent and still stand. Only
the channel *names* were wrong.

### Open, and it is Akshat's call

Fixing the naming properly means re-reading Zenodo as (VH, VV) and rebuilding the cache, the label
CSVs and both models — a full retrain, well past the freeze. **Not proposing that now.** The
options before Tuesday are: (a) ship as-is, live cases classical, and remove the two broken claims
from the deck; or (b) also swap the channel order at inference so the benchmark bundles use the
matched order. (a) is my recommendation — it changes nothing that runs and only removes claims we
cannot defend.

---

## [2026-09-13 21:30] Phase 6.7 — Layer 2 measured against Akshat's bar: it scores zero, and retraining cannot help

**Done:** Measured, not assumed, what Layer 2 does on real scenes. Akshat's §2 ruling said Layer 2
replaces classical on a live case only if it *"beats classical on real scenes, measured as IoU
against `cerulean_slick.geojson`"*, by Monday 12:00. **That question is now closed by measurement
rather than by the deadline.** Nothing was retrained and no bundle was touched — all output went
to `scratch/nets/`.

**Files:** none changed. **Run:** `python pipeline/detect/run.py --case <id> --path networks --out scratch/nets/<id>.geojson`

### 1. Layer 2 vs Cerulean on the five reference cases: **IoU 0.000 on all five**

Forced down the network path, Layer 1 closes the gate on every one at **P(oil) 0.002–0.005**
against a 0.143 threshold — including Jacksonville's 31 km ribbon, which is unmistakable by eye.
So Layer 2 never executes. Classical scores **median 0.483** on the same five. The bar cannot be
cleared.

### 2. Bypassing the gate entirely: the U-Net still predicts **0.00 km²** on all five

| case | P(oil) | U-Net km² | Cerulean km² | IoU |
|---|---|---|---|---|
| jacksonville | 0.0019 | **0.00** | 4.54 | 0.000 |
| farallones | 0.0016 | **0.00** | 3.85 | 0.000 |
| gulf-alaska | 0.0023 | **0.00** | 0.27 | 0.000 |
| mumbai | 0.0050 | **0.00** | 7.77 | 0.000 |
| jamnagar | 0.0028 | **0.00** | 1.59 | 0.000 |

So it is **not** a gating problem that a better Layer 1 would fix. Both layers fail on GEE exports.

### 3. And it cannot be rescued by rethresholding — it is not localising at all

| scene | prob max | prob mean | px > 0.1 | of scene |
|---|---|---|---|---|
| jacksonville | 0.269 | 0.164 | 3,662,541 | **99.99%** |
| mumbai | 0.250 | 0.159 | 4,610,153 | ~99.9% |
| farallones | 0.230 | 0.107 | 3,854,331 | ~99.9% |

The probability field is **flat at ~0.16–0.27 across the whole scene**. Dropping the threshold to
0.2 does not reveal a faint slick, it paints the entire raster as oil. This is the signature of
domain shift — inputs outside the training distribution, so the network returns something near its
prior everywhere. **There is no threshold that makes this work.**

### 4. The control: in its own domain the U-Net is genuinely good

| Zenodo scene | oil fraction | prob max | IoU |
|---|---|---|---|
| P3_Oil_00081 | 0.37% | 0.592 | 0.125 |
| P3_Oil_00043 | 2.53% | 0.784 | **0.970** |
| P3_Oil_00103 | 4.32% | 0.835 | **0.836** |
| P3_Oil_00067 | **78.32%** | 0.374 | **0.000** |

This confirms the large-slick mechanism **directly**, at the probability level: at 78% oil the max
probability over the entire scene is 0.374 and **not one pixel** crosses 0.5. The slick has become
its own median under per-scene MAD normalisation and the contrast the model needs is gone.

**A better way to describe Layer 2, still honest:** on typical Part III scenes it reaches
**IoU 0.97 and 0.84**. Pooled over all 150 positives it is **0.435**, because the 12 scenes above
30% oil coverage collapse to 0.085 and carry a large share of all oil pixels. Say all three parts
or none of them.

### Why retraining is the wrong use of the remaining time

- **No demo case is in the failure band.** Measured oil coverage across the library: 0.00%, 1.13%,
  1.21%, 1.45%, 1.85%, 2.18%, 2.25%, and three at 0%. The >30% band **does not exist here**.
- **The networks contribute nothing to any live case** — gate closed, and ungated they emit zero
  pixels. Improving them changes a slide number and nothing a judge sees.
- On the two benchmark bundles the correct answer is zero oil, and the gate already delivers it.

**Recommendation: freeze the model work.** The remaining risk is not accuracy. It is the
Python 3.13-vs-3.11 divergence, which is the only open item that can stop Stage 1 running on
someone else's laptop.

**Post-freeze, ranked:** (1) the normalisation fix for large slicks — the only genuine defect, and
it is load-bearing so it needs a clean before/after on Part III; (2) domain adaptation for GEE
exports, which is a research problem, not a fix; (3) classical-path precision, which is **barred
now** because tuning after seeing the Cerulean polygons is exactly what A6 forbids.

---

## [2026-09-13 20:30] Phase 6.6 — the 0.435-vs-96% gap decomposed, and it is not what I predicted

**Done:** Plan items 3, 4 and 5. `evaluate.py` now prints every IoU variant **with its definition
named**, on the same 450-scene Part III holdout, same model, same pixels. No retraining.

**Files:** `pipeline/detect/evaluate.py`, `pipeline/detect/eval_part3.json`, all nine
`scratch/check_*.png`. **Run:** `python pipeline/detect/evaluate.py --report`

Headline rows are unchanged by any of this: gated **0.4349**, ungated **0.4485**.

### Item 3 — the decomposition

| metric | value | definition |
|---|---|---|
| `iou_oil_pooled` | **0.4349** | oil class only, pooled over positive scenes, background excluded both sides. **What we report.** |
| `iou_background_pooled` | 0.9392 | background as a class, same pooling |
| `miou_pooled` | **0.6871** | mean IoU over {background, oil} — the authors' likely definition |
| `pixel_accuracy_positives` | 0.9419 | over the 150 positive scenes |
| `pixel_accuracy_all450` | **0.9800** | over all 450 — the likelier match for their "99%" |
| `dice_oil_pooled` | 0.6061 | Dice/F1 on the oil class |
| `iou_oil_macro_scene` | **0.6825** | per-scene IoU averaged over 150 scenes |
| `iou_oil_macro_tile` | 0.4944 | per-tile over the 2,807 tiles containing oil |
| `invalid_px_fraction` | 0.0184 | land/NaN share, so nobody wonders if background is inflated |

**The gap splits three ways, and only the third is a defect:**

1. **Definition — about half.** 0.4349 → **0.6871** is the same predictions scored two ways.
   Pixel accuracy over all 450 is **0.980** against their quoted 99%: close enough that accuracy
   is roughly comparable, which is the evidence that the *IoU* definitions are not.
2. **Pooling — most of the rest.** 0.4349 pooled → **0.6825** per-scene, again identical
   predictions. Pooling weights each scene by its slick size.
3. **A real defect, and it is narrow.**

| oil coverage | n | mean per-scene IoU |
|---|---|---|
| 0–1% | 18 | 0.6685 |
| 1–3% | 39 | 0.7566 |
| 3–10% | 52 | 0.7826 |
| 10–30% | 29 | 0.6595 |
| **30–101%** | **12** | **0.0848** |

**138 of 150 scenes sit at 0.66–0.78. Twelve scenes where oil covers more than 30% of the frame
score 0.085.** Those twelve hold a large share of all oil pixels, which is exactly why the *pooled*
number collapses while the per-scene mean does not. The cause is already known and is mechanical:
**per-scene MAD normalisation lets a slick that large become its own median**, erasing the contrast
the model depends on. The model is not broadly weak — it fails on one identifiable class of scene.

**⚠️ This falsifies a hypothesis I put in the plan.** I wrote that part of the gap was *split
hardness* — "our validation IoU is 0.679 on same-population data; Part III is a different slick
population." **Wrong.** Part III per-scene macro is **0.6825** against validation **0.6793** —
statistically the same. Part III is **not** harder scene-for-scene. The whole pooled gap is
pooling plus those twelve scenes. I also predicted mean IoU ≈ 0.71 by assuming background IoU
0.99; it is 0.9392, so the real figure is 0.687.

**We keep reporting 0.4349.** The others exist so a comparison is like-for-like, not so we can
pick the flattering number (B2). Anyone quoting 0.687 must say "mean IoU over both classes" in
the same breath.

**Also fixed: `--limit` used to overwrite the authoritative results file.** A 10-scene smoke run
silently replaced the 450-scene `eval_part3.json` and it had to be restored from git. Partial runs
now write `eval_part3_smoke.json`, print `PARTIAL RUN — these numbers are NOT the Part III result`,
and stamp `"partial": true` and `"n_scenes"` into the JSON.

### Item 4 — all nine plotted and eyeballed, and it earned its place

Plots were **stale** (01:21 vs detections at 02:30); regenerated all nine first. Then looked at
every one.

| case | verdict |
|---|---|
| jacksonville | ribbon tracked along its long axis; the 3 oil features are visibly one ~31 km ribbon with real breaks; over-extent visible as perpendicular fronds |
| farallones | textbook — one ruler-straight filament, polygon hugging it |
| huntington | comma slick outlined tightly; 43 contacts sit on bright cross/sidelobe vessel signatures |
| gulf-alaska | **explains its own 0.165** — det-01 is on the real slick, det-02/03 sit in a large diffuse dark band Cerulean did not call oil. 0 contacts, as reported |
| mumbai | +72 E / +18 N correct, polygons tight on dark features |
| jamnagar | 21 km hook tracked; filament continues past the north end toward the swath edge, consistent with recall 0.916 |
| ennore | 0 oil — correct |
| lookalike-zenodo | delta, 0 oil, the single edge contact visible exactly where Akshat described |
| **nospill-zenodo** | **FAILED — was farmland. Replaced.** See `6a6f4cc` |

**The one defect, and it is mine.** `P3_No oil_00091` was not clean ocean; it was the Ghab plain —
fields, roads, a settlement, the Orontes river — ~150 km inland from the "Gulf of İskenderun" the
bundle's own `meta.json` named, and its 31 "radar contacts" were buildings. I had nominated it on
**statistics alone** (deepest dark feature, most candidate regions, therefore "hardest") and never
opened the image. Classifier correct, validator PASS, JSON strict-clean — **no automated gate in
this repo can catch "the ocean is a field."** Replaced with `P3_No oil_00027`, verified as water
rather than assumed: median −26.9 dB, MAD 0.47, 1–99th spread 3.6 dB, zero pixels above −5 dB,
zero contacts, and the plot shows open water with swell banding. 65 of 150 Part III no-oil scenes
qualify, so there was never a shortage — I picked on the wrong axis.

**One suspicion checked and withdrawn.** Ennore's plot *looked* like contacts were sitting on the
port and river. Measured instead of assumed: **0 of 72 on land**, 32 within 15 px (~130 m) of the
land-mask edge, which in a working port is the quayside — where berthed vessels are. Land masking
is doing its job (it had cut 1,377 → 72).

### Item 5 — reporting closed out

- **`features_test.csv` committed** (`fd4021e`), 4,085 rows, 1.0 MB — the evidence behind the
  classical numbers. While adding it, the gitignore un-ignore rule was pointing at `features.csv`,
  the **old contaminated-split** table; an un-ignore is an invitation, so it is ignored again on
  purpose with the reason in the rule. Same class as the root-anchored `models/*`.
- **Margin distribution** — delivered and corrected (Phase 6.3): 12 detections, median 0.645,
  bands 7 clear / 5 marginal.
- **VH sentence** — the defensible wording is in Phase 6.5; VH raises precision 5.8× at
  *identical* recall, so it is a discriminator, not a detector.
- **Zenodo DOI `10.5281/zenodo.13761290`** — verified already present in `docs/receipts.md`,
  `docs/updates/_INTEGRATION.md` and `docs/01_AKSHAT_INTEGRATION.md`. Nothing to add.

**Open for Akshat:** the `case-nospill-zenodo` gallery blurb. His "No oil — but not empty water /
does the system tell traffic from a spill?" was written for 31 contacts that were never vessels.
Set to "Open ocean, nothing on it. Does the system say so?" pending his call.

**Next:** nothing left in the plan. Remaining time is best spent on the 12 large-slick scenes if
anything, and that is a retrain — which the Layer 2 ruling puts behind a Monday 12:00 bar it does
not need to clear.

---

## [2026-09-13 19:40] Phase 6.5 — answering Akshat's handoff: §1 confirmed, §6 named, three stale numbers caught

**This entry is written to be quoted from.** Every number below carries its metric, its split and
its count, per Master §12.

---

### §1 CONFIRMED — every live case on `main` is classical output, not Layer 2

**No live case has ever gone through the networks.** Verified three ways: `meta.provenance` is
**absent** on all seven live bundles (D33: absent = satellite → classical), every run printed
`path : classical detector + stated rule (auto, by provenance)`, and the reran numbers reproduce
the committed bundles exactly. Anushka's seeds are safe.

The exact command behind every live case on `main`:

```bash
python pipeline/detect/run.py --case <case_id> --rule-contrast -3.0 --rule-elongation 2.5
python pipeline/export/build_case.py --case <case_id> --stage detect
```

`--min-oil-km2` was **not** passed; it takes its default of `0.10`, which is the value in your
handoff. Stating that precisely because "the default happened to be right" and "I passed the flag"
are different facts and only one of them is true.

**⚠️ Correction to your §1 mechanism.** You wrote that routing works because *"the Layer 1+2
networks only run on the CRS-less Zenodo tiles."* **The Zenodo tiles are not CRS-less.** All nine
bundles, benchmark included, are EPSG:4326 with real geotransforms — `benchmark_scene.py` writes
the true affine, which is exactly why `case-lookalike-zenodo`'s contact lands at the Mississippi
Delta rather than at pixel coordinates. Routing is by **`meta.provenance` (D33)**, never by CRS.
The CRS-sniffing heuristic was the *broken* version D33 replaced. Your conclusion is right and the
mechanism is not, and the difference bites: under your stated mechanism, giving a Zenodo bundle a
CRS would move it to the classical path. It would not. Only `meta.provenance` moves it.

### §2 / §3 / §5 — accepted

- **Layer 2 stays off live cases for the demo.** The bar is now a real number: classical scores
  **median IoU 0.483** against Cerulean (below). Layer 2 has to beat that *on real scenes*, by
  Monday 12:00, with both numbers side by side, or it appears in the deck through Zenodo held-out
  numbers only. That outcome is fine and I am not going to force it.
- **No live-case rerun without telling you first.** Noted and binding. (Today's D34 rerun of all
  nine was the one you asked for in that handoff.)
- **`contrast_centre_db` / `contrast_edge_db`: not building them.**
- **`discharge_class`: confirmed and not touched.** Across all oil features in the library:
  **4 `chronic`, 8 `unknown`, ZERO `acute`.** Anushka's age estimators refusing on every case is
  correct behaviour, not a bug. Worth knowing why: `acute` is common among *look-alike* features
  (ennore 28, jacksonville 18, huntington 8) and absent among oil ones, so the class only carries
  meaning after classification. I am not reclassifying anything to make an estimator fire.

### §4 DONE — IoU against Cerulean, five cases

Delivered in `0dce618`; tool is `pipeline/detect/iou_cerulean.py`, raw numbers in
`pipeline/detect/iou_cerulean.json`. Computed on the **shipped classical detections**, nothing
retuned after seeing the polygons.

| case | IoU | recall | precision | ours km² | theirs km² | their conf |
|---|---|---|---|---|---|---|
| mumbai | 0.728 | 0.942 | 0.762 | 9.60 | 7.77 | 0.93 |
| farallones | 0.624 | 0.796 | 0.742 | 4.13 | 3.85 | 0.93 |
| jacksonville | 0.483 | 0.825 | 0.537 | 6.97 | 4.54 | 0.80 |
| jamnagar | 0.452 | 0.916 | 0.471 | 3.10 | 1.59 | 0.84 |
| gulf-alaska | 0.165 | 0.797 | 0.173 | 1.23 | 0.27 | 0.76 |

**Median 0.483, range 0.165–0.728.** Method: both polygon sets burned onto the scene's own affine
grid; validated against Cerulean's own stated `area` property to within 0.8% on all five.

**On your Farallones note** — you said the scene holds several Cerulean slicks and the bundled one
is the ~19.6 km slick, so a much larger detection elsewhere is a different slick, not a miss. Our
Farallones excess is **1.07 km² and majority-margin around their polygon**, not a separate large
blob, so we are not being charged for the other slick. Good that you flagged it; it would have
been an easy wrong conclusion.

### §6 — named numbers, each with metric, split and count

**Layer 1, scene classifier (CNN, 63,873 params, `both32` variant):**

| metric | value | split | count |
|---|---|---|---|
| scene accuracy | **0.951** | Zenodo Part III holdout | 450 scenes (139 TP, 11 FP, 11 FN, 289 TN) |
| oil recall | **0.927** | Part III | 139 / 150 oil scenes |
| look-alike rejection | **0.940** | Part III | 141 / 150 look-alike scenes |
| clean-ocean rejection | **0.987** | Part III | 148 / 150 no-oil scenes |

Gate threshold **0.1427**, selected on a validation split of Parts I+II by PR curve under a 0.90
recall floor — *not* on Part III. Trained on Parts I+II, tested only on Part III (D1).

**⚠️ Stale number in `docs/updates/soumirya_case_nominations.md` line 7** — it says look-alike
rejection **0.960**. That is the *pre-domain-augmentation* classifier. The shipped model is
**0.940**. The augmentation traded look-alike rejection 0.960 → 0.940 for oil recall
0.893 → 0.927 and accuracy 0.947 → 0.951. Net positive, but it is a trade and the deck must not
quote the old rejection figure beside the new accuracy figure. **Use 0.940.**

**Layer 2, U-Net (depth 7, focal α=0.75 γ=2.0, binarised at 0.5):**

| metric | value | split | count |
|---|---|---|---|
| IoU, oil class only | **0.435** | Zenodo Part III, **gated** by Layer 1 | 138 / 150 oil scenes reached |
| IoU, oil class only | 0.449 | Part III, **ungated** | 145 / 150 scenes |
| IoU, oil class only | **0.679** | validation tiles, Parts I+II | 4,299 tiles |

Ungated buys +0.014 IoU and costs **look-alike rejection 0.94 → 0.46** — which is why D2 gates it.

**⚠️ There is no "23% accuracy" anywhere in my work.** I searched every doc, eval JSON and CSV.
The only 23% in the repo is Stage 2's `wind_share` on case-000 in `docs/STAGE2_NUMBERS.md` — I
think the wires crossed with Anushka's number. **Layer 2 has exactly one headline: 0.435 IoU,
oil-class-only, on the gated Part III holdout.** Please strike the 23%.

Note the definition, because it is the strictest available and the gap to the authors' "96%" is
mostly definitional: ours is **oil-class IoU with background excluded from both numerator and
denominator, pooled over whole 2048×2048 scenes**. Decomposing that gap is §E5 item 3, still open.

**Classical path:** the five per-case IoUs above.

### §6 VH sentence — close, but I want it more precise before I defend it

Your draft: *"VH is the strongest single feature on the Zenodo benchmark."* I never measured
per-feature importance, so I can't defend "strongest single feature". What I measured is a
feature-set ablation, and it says something sharper: **VH improves precision, not recall.**

| feature set | val F1 | Part III precision | Part III recall |
|---|---|---|---|
| `v1_absolute` (8 features, no VH) | 0.346 | 0.049 | 0.05 (4/36 scenes) |
| **`v2_vh` (+ 2 VH features)** | **0.643** | **0.286** | 0.05 (4/36 scenes) |

Recall is **identical**. VH does not help us find slicks; it helps us reject look-alikes — 5.8×
the precision at the same recall. The sentence I will defend:

> *"Adding the two VH features nearly doubles validation F1 (0.346 → 0.643) and lifts Part III
> precision 5.8× (0.049 → 0.286) at unchanged recall: on the Zenodo benchmark, cross-pol is what
> separates oil from look-alikes. On our own Sentinel-1 exports the sea sits at −27.0 to −38.5 dB
> in VH, below the ~−24 dB IW noise floor, so those features would carry noise and real-scene
> detection runs VV-only (D3). Both Zenodo benchmark bundles have usable VH (−21.9, −11.6 dB) —
> the contrast is what makes this a conditional finding rather than a retreat."*

### §7 — margin distribution DONE; and the environment is not what the docs say

- **Rule-margin distribution: delivered** (Phase 6.3 entry). 12 oil detections, confidence
  0.509–0.755, median 0.645. Your 0.75/0.45 bands collapse to 1/11/0; the dB bands you adopted
  split them **7 clear / 5 marginal**.
- **⚠️ torch resolution: it is a real, working install — but on Python 3.13.5, not 3.11.** This
  venv is `venv\Scripts\python.exe` → **Python 3.13.5**, with `torch 2.6.0+cu124`,
  `torchvision 0.21.0+cu124`, `cuda_available = True`. Every model in this repo was trained and is
  served on 3.13. `requirements.txt` and `CLAUDE.md` both say **Python 3.11**. So the 3.11
  resolution you asked about is *still* only index-verified — I verified 3.13 by using it. This is
  precisely the "six laptops silently disagree" risk that file warns about, and it is your call
  whether the documented version changes to 3.13 or I stand up a 3.11 venv to prove the pin. Say
  which and I will do it before Monday.

### §8 — blindness holds

I have opened `cerulean_slick.geojson` for IoU and nothing else. No news, no reports, no AIS, no
attribution. `docs/receipts.md`'s visual slick descriptions remain unread.

**Files:** `docs/updates/soumirya.md`.

**Next:** §E5 item 3 — decompose the 0.435-vs-96% metric gap in `evaluate.py`, no retraining.

---

## [2026-09-13 18:20] Phase 6.4 — Cerulean IoU on five cases: the first external number Stage 1 has

**Done:** Wrote `pipeline/detect/iou_cerulean.py` and ran it on the five bundles carrying
`cerulean_slick.geojson`. This converts every IoU we own from benchmark-only to a comparison
against the polygon an operational detector produced **for the same acquisition** — all five
`slick_timestamp` values match `meta.detection_time` exactly, so it is the same satellite pass.

**Files:** `pipeline/detect/iou_cerulean.py`, `pipeline/detect/iou_cerulean.json`.

**Run:** `python pipeline/detect/iou_cerulean.py --all --json pipeline/detect/iou_cerulean.json`

| case | IoU | recall | precision | ours km² | theirs km² | their conf |
|---|---|---|---|---|---|---|
| mumbai | **0.728** | 0.942 | 0.762 | 9.60 | 7.77 | 0.93 |
| farallones | **0.624** | 0.796 | 0.742 | 4.13 | 3.85 | 0.93 |
| jacksonville | **0.483** | 0.825 | 0.537 | 6.97 | 4.54 | 0.80 |
| jamnagar | **0.452** | 0.916 | 0.471 | 3.10 | 1.59 | 0.84 |
| gulf-alaska | **0.165** | 0.797 | 0.173 | 1.23 | 0.27 | 0.76 |

**Median IoU 0.483, range 0.165–0.728.**

**What this number is:** agreement between two independent detectors on one acquisition. It is
**not** accuracy against ground truth — SkyTruth state plainly that SAR alone cannot definitively
identify oil, and that note is carried inside every one of these files. Where we disagree the
polygon is not automatically right. Say it that way on the slide; "IoU vs Cerulean" alone invites
a judge to hear "ground truth", which we would not be able to defend.

**The shape of the disagreement is the actual finding, and it is favourable.** Recall is high and
uniform — **0.796 to 0.942** on all five — while precision ranges 0.173 to 0.762. We are not
missing slicks. We cover 80–94% of every polygon they drew, and our area exceeds theirs on all
five cases. **IoU here is limited by over-extent, not by misses**, which is the better failure
direction for a detector whose job is to not miss a spill.

Decomposing our excess area (pixels we call oil that they do not), by whether it sits within
12 px of their polygon or somewhere else entirely:

| case | excess km² | margin around theirs | disjoint elsewhere | of theirs we missed |
|---|---|---|---|---|
| farallones | 1.07 | **85%** | 15% | 0.79 km² |
| mumbai | 2.28 | **85%** | 15% | 0.45 km² |
| jacksonville | 3.22 | 61% | 39% | 0.79 km² |
| jamnagar | 1.64 | 59% | 41% | 0.13 km² |
| gulf-alaska | 1.02 | 8% | **92%** | 0.05 km² |

**Caveat on those percentages, added after a challenge: 12 px is an arbitrary radius and the
figures move with it.** Sweeping it 6 / 12 / 25 / 50 px, the margin share runs farallones
70/85/93/99%, mumbai 65/85/97/100%, jacksonville 50/61/69/77%, jamnagar 44/59/77/91% — and
gulf-alaska 7/8/10/12%. So **the exact 85% is not a measurement, it is a function of the radius**,
and should not be quoted as one. What IS robust is the *ordering*, which is identical at every
radius, and Alaska's isolation: its excess stays ~90% disjoint even at 50 px, while every other
case becomes majority-margin by 12 px. Quote the ranking and Alaska's separation, not the number.

On the two cases where they are most confident, our excess is overwhelmingly a slightly fatter
outline around the same slick. Their polygons are filamentary — `polsby_popper` 0.0095–0.103 and
`fill_factor` 0.046–0.28 — while our morphological detector traces the whole dark patch. Different
conventions for the same object, not a different object.

**Alaska is the exception and behaves exactly as its caveat predicts.** 92% of our excess is
*disjoint* from their polygon — separate dark regions, not a fatter outline. This is the case
Cerulean's own human reviewer classed **AMBIGUOUS**. Two detectors disagreeing about which dark
patch is the slick, on the one scene a human reviewer could not call, is a coherent result rather
than an embarrassing one. **It gets reported. It is not tuned.**

**The classifier earns its place — this is an ablation against an external reference.** Counting
every dark region the detector found instead of only those Layer 3 called oil, IoU falls on all
five: jacksonville 0.483 → 0.362, farallones 0.624 → 0.618, alaska 0.165 → 0.041, mumbai
0.728 → 0.661, jamnagar 0.452 → 0.443. The classifier discards regions an operational detector
also excluded, which is the first evidence for it that does not come from our own labels.

**One observation, deliberately undersold: our IoU tracks their confidence.** Ordered by their
`machine_confidence` — 0.93, 0.93, 0.84, 0.80, 0.76 — our IoU runs 0.728, 0.624, 0.452, 0.483,
0.165. Pearson r = 0.904 (p = 0.035), Spearman ρ = 0.800 (p = 0.104). **n = 5, one Spearman test
is not significant, and the correlation is carried largely by Alaska sitting low on both axes.**
It is suggestive that both detectors find the same scenes hard — which would mean the gap is scene
difficulty rather than a broken detector — but **it is an observation, not a result, and must not
be put on a slide as a statistic.**

**Method notes.** Both polygon sets are burned onto the scene's own affine grid rather than
intersected as vectors: our detections are pixel regions traced to contours, so a vector
intersection would measure contour-tracing artefacts as much as real disagreement, and rasterising
matches how `evaluate.py` scores the U-Net so the two IoU figures in the deck mean the same thing.
All five scenes are EPSG:4326 and the script exits rather than guessing if one is not. Every
Cerulean file also carries `role='centerline'` LineStrings — dropped explicitly, since zero-area
geometries would contribute nothing to the union while looking like they had been counted. Checked
before trusting any of it: **100% of every Cerulean polygon falls inside our exported crop**, so no
case is being penalised for a slick our bbox cut in half.

**Two validations run after the fact, because the whole item finished far faster than the ~1 h
budgeted and "the hard parts did not happen" is not the same as "nothing was missed".** It was
fast because all five scenes are already EPSG:4326 (no reprojection), nothing was clipped, and
every timestamp matched — three contingencies the estimate had budgeted for. The two checks that
*should* have run before I reported anything:

1. **Does my rasterisation reproduce Cerulean's own stated areas?** This was the real risk: their
   polygons are filamentary (`polsby_popper` down to 0.0095), and `all_touched=False` can drop a
   filament thinner than the gap between pixel centres, which would silently shrink their mask and
   flatter our precision. Burned area vs the `area` property they ship: jacksonville −0.2%,
   farallones −0.0%, gulf-alaska −0.5%, mumbai +0.5%, jamnagar +0.8%. **Nothing is being lost**,
   and interior rings are handled.
2. **Does my rasterisation of OUR oil match our own `area_km2` properties?** Within 2.1% on four
   cases; gulf-alaska is +6.7%, which is expected rather than wrong — its regions are the smallest
   in the library on a ~5 × 10 m pixel, so boundary pixels are a larger share of a small shape
   (≈ 4/√7600 ≈ 4.6% for a region that size). Our own oil polygons **do not overlap each other**
   on any case (0.000 km² double-counted), so the union is not hiding a double count.

**A6 satisfied:** the polygons stayed sealed until all nine detections were committed and pushed
(`20594df`). `iou_cerulean.py` reads `detections.geojson` and never writes one; nothing here can
re-tune a threshold.

**Next:** the U-Net metric question (§E5 item 3) — add background IoU, mean IoU, per-tile IoU and
Dice to `evaluate.py`, each printed with its definition named, so the 0.435-vs-96% gap can be
decomposed before any slide claims it.

---

## [2026-09-13 17:05] Phase 6.3 — D34 closed out: Akshat's two corrections applied, decisions recorded

**Done:** Merged `7d89a76`. Both Zenodo cases are now in `cases/index.json` at slots 8 and 9, so
the library is **9 indexed cases**. Applied both things Akshat asked for:

1. **Margin paragraph** — already corrected in `20594df`, before his handoff was written. The only
   two surviving mentions of "20 / 0.578" are inside blocks that explicitly label the figure wrong
   and explain its provenance. Nothing in the log can put 20 on a slide.
2. **Contact total: 173, not 174.** His count is right and mine was arithmetic sloppiness:
   72 + 43 + 31 + 21 + 3 + 2 + 1 + 0 + 0 = 173. Corrected — the edge finding is **2 of 173**.

**Files:** `docs/updates/soumirya.md`.

**His correction, recorded because it changes the shared record.** Akshat withdrew the claim that
the Delta contact sits "among charted platforms" — he had not checked any platform dataset at that
coordinate, and it was an inference written as a fact. `receipts.md`, D34 and the case notes now
say only what was measured. My own reasoning never rested on it: the argument was that geometry
cannot establish a contact's identity, which holds whatever is or isn't charted there. What
survives unchanged is that it is **not** a dark vessel — darkness needs an AIS check at a known
acquisition time, and that scene has none.

**Decided by Akshat, not to be reopened before the freeze:**
- **No edge rule and no `edge` flag.** My answer accepted in full, including the point that
  windowed-CFAR's edge objection does not apply to a globally-estimated background.
- **Do not change `DEFAULT_MIN_DB` before the freeze.** The floor-binding limitation on Zenodo
  scenes is recorded in `receipts.md`: a −12 dB hull on a −29 dB sea (≈22σ) would be missed. A
  scene-relative floor for benchmark scenes is October work and must ship with a before/after
  contact count on Part III.
- **Recording `--rule-contrast` in the bundle waits until October.** The frontend pins −3.0 as
  `RULE_CONTRAST_DB` and every bundle matches it today. **Standing rule I owe him: if I ever rerun
  a satellite case with anything but `--rule-contrast -3.0 --rule-elongation 2.5`, tell him before
  pushing** — the bands would be wrong on screen and the bundle would not reveal it.

**Guard rails through the demo (his, logged so they survive this chat):** no detector changes after
15 Sept 05:00 unless it is a bug fix and he is told first; **Alaska stays at zero contacts** and the
dark-vessel contact shown on that case is **Cerulean's**, never ours; and **nothing is called a
"dark vessel" at Stage 1** — every contact we emit is unattributed, only Stage 3 can call one dark.

**Next:** Cerulean IoU on the five cases carrying `cerulean_slick.geojson` (jacksonville,
farallones, gulf-alaska, jamnagar, mumbai). Comparison target, not ground truth; gulf-alaska was
classed AMBIGUOUS by Cerulean's own reviewer, so a poor IoU there is the expected result and gets
reported, not hidden.

---

## [2026-09-13 16:10] Phase 6.2 — D34 adopted, all nine reran, and the rerun hazard closed in code

**Done:** Merged Akshat's `c001423` (D34). Reran all nine cases; `ship_detections` is now
top-level on every bundle and the per-feature copy is gone everywhere. **All 32 previously
dropped contacts now reach the bundles** — lookalike-zenodo 1, nospill-zenodo 31. Six spill
cases validate with **0 warnings**; the three zero-oil cases keep the expected "zero 'oil'
features" warning. The legacy top-level warning Akshat predicted would clear, cleared.

The seven satellite cases reproduce their shipped numbers exactly under
`--rule-contrast -3.0 --rule-elongation 2.5` (oil 3/1/1/3/3/1/0, contacts 2/0/43/0/21/3/72),
which independently confirms his back-solve that −3.0 was the value used.

**Files:** `pipeline/detect/run.py`, all nine `cases/*/detections.geojson`, `docs/updates/soumirya.md`.

**Run:**
```bash
for c in case-jacksonville-2024 case-farallones-2023 case-huntington-2021 \
         case-gulf-alaska-2023 case-mumbai-2023 case-jamnagar-2024 case-ennore-lookalike-2023; do
  python pipeline/detect/run.py --case $c --rule-contrast -3.0 --rule-elongation 2.5
  python pipeline/export/build_case.py --case $c --stage detect
done
```

**Rerun hazard closed in code, not in a note.** Akshat flagged that the −3.0 rule is typed by
hand, stored in no bundle, and that forgetting it silently falls through to −0.5 and
reclassifies everything with no error. I did **not** change the default to −3.0: −0.5 is the
right number for Zenodo and −3.0 for our satellite exports, and baking either in is what the
"−3 dB trap" docstring says not to do. Instead both flags now default to `None` and the
**classical path refuses to guess** — it exits 1 naming the two values and which suits which
family. The network path still resolves −0.5 / 2.0 internally, since the rule barely matters
behind a closed Layer 1 gate. A silent wrong answer is now a loud failure.

**CORRECTED: my "20 oil detections, median 0.578" was wrong.** See the corrected block in the
Phase 6.1 entry below. The shipped figure is **12, median 0.645**; 20 was the pre-area-floor
rule-passing count. Akshat is right that nobody should quote 20.

**Answering his question — should `detect_ships` reject contacts touching the scene edge? No.**
Measured across all nine cases: only **2 of 173** contacts sit within 2 px of an edge, and one of
them is Ennore's **+10.27 dB, 60 px** target in a working port — almost certainly a real ship. A
blanket edge rule spends a confident true positive to remove one questionable contact.

There is also no statistical reason to distrust an edge detection *in this implementation*. The
classic CFAR objection is that a target at the border has a truncated guard/background window, so
its test statistic is computed on an incomplete neighbourhood. `detect_ships` doesn't use a local
window — `_sea_level()` estimates the sea median and sigma **globally over every valid pixel**, so
an edge contact is tested against exactly the same background as a centre-of-scene one.

And the Delta contact is not marginal. On `case-lookalike-zenodo` the sea sits at −29.46 dB with
σ = 0.793; that contact peaks at **−5.93 dB, i.e. 29.7 σ** above the sea. Something bright is
genuinely there. What is in doubt is *what it is* — platform or vessel — not whether it is a
return. **So the objection is about provenance, not geometry**, and the correct filter would be a
charted-infrastructure mask, which we do not have and cannot add under the dependency freeze. His
"unattributed radar contact" relabel is the right mitigation and already does the work. If he
wants it visible, the honest move is to **flag** the truncated extent (`edge: true` on the entry),
not to drop the detection — his call, I have not touched the entry schema.

Worth knowing separately: on `case-lookalike-zenodo` the ship threshold is **floor-binding** —
−10.0 dB absolute versus −26.3 dB scene-relative (−29.46 + 4 × 0.793). On Zenodo benchmark scenes
`k_sigma` is therefore inert and `DEFAULT_MIN_DB` alone decides what counts as a contact.

**Open:** both Zenodo cases are still absent from `cases/index.json` — Akshat's call, as he says.
`--rule-contrast` is still recorded in no bundle; the guard makes forgetting it loud, but it does
not make a *shipped* bundle self-describing. If he wants that, it is a top-level `detect_params`
key and needs his ruling, not mine.

**Next:** Cerulean IoU on the five cases carrying `cerulean_slick.geojson`.

---

## [2026-09-13 14:30] Phase 6.1 — nine cases PASS, k_sigma correction, and the contract gap measured

**Done:** Built the two Zenodo benchmark bundles (`case-lookalike-zenodo`, `case-nospill-zenodo`)
with `benchmark_scene.py`, leaving Akshat's `meta.json` files byte-identical (md5 verified before
and after). Both carry `provenance: "benchmark"`, so they are the **first and only cases to
exercise the Layer 1 + Layer 2 network path** — all seven live cases route classical, so that
branch had never run on a real bundle. It works: the gate closes at P(oil) 0.002 and 0.000
against the 0.143 threshold and both correctly emit zero oil features. All nine cases PASS.

| # | case | regions | oil | ships | discharge |
|---|---|---|---|---|---|
| 1 | jacksonville | 23 | 3 | 2 | 1 chronic |
| 2 | farallones | 2 | 1 | 0 | 1 chronic |
| 3 | huntington | 9 | 1 | 43 | — |
| 4 | gulf-alaska | 13 | 3 | 0 | 2 chronic |
| 5 | mumbai | 13 | 3 | 21 | — |
| 6 | jamnagar | 2 | 1 | 3 | — |
| 7 | ennore-lookalike | 29 | **0** | 72 | — |
| 8 | lookalike-zenodo | 0 | **0** | 1 detected, **0 in bundle** | — |
| 9 | nospill-zenodo | 0 | **0** | 31 detected, **0 in bundle** | — |

**Files:** `cases/case-lookalike-zenodo/*`, `cases/case-nospill-zenodo/*`, `pipeline/detect/run.py`.

**Run:**
```bash
python pipeline/detect/run.py --case case-lookalike-zenodo
python pipeline/export/build_case.py --case case-lookalike-zenodo --stage detect
python scripts/validate_case.py cases/case-lookalike-zenodo
```

**CORRECTION to commit 72064c8.** That message claimed `k_sigma 8.0 -> 4.0` was "applied to all
seven at once". It was not. `run.py` duplicated the default as a literal `8.0` in its own
argparse, which silently shadowed `ships.DEFAULT_K_SIGMA`, so the module read correctly in review
while the pipeline kept using 8.0 — the fix was inert. The seven-case numbers in that commit were
k=8 plus the land mask. `run.py` now **imports** `DEFAULT_MIN_DB` and `DEFAULT_K_SIGMA` from
`ships.py` so the two cannot drift again. Ship counts move under a genuinely active k=4:
jacksonville 0->2, jamnagar 1->3, mumbai 20->21, huntington 41->43, ennore 18->72. Same class of
failure as a root-anchored gitignore pattern: a stated fact that is not in effect.

**Open — Akshat's ruling, blocking nothing but costing evidence.** The §6.3 contract gap logged
on 08-Sep as a prediction is now **measured, and larger than reported in chat**. `ship_detections`
lives inside a detection's `properties`, so a case with zero oil detections has nowhere to put its
ships. Both benchmark bundles have `features = 0`, top-level keys `['features', 'type']`, and
`ship_detections` appears **zero times** in either file:

- `case-lookalike-zenodo` — detector finds **1** radar contact, 0 reach the bundle
- `case-nospill-zenodo` — detector finds **31** radar contacts, 0 reach the bundle

That is **32 contacts silently dropped**, not the 1 first reported — the earlier figure read the
bundle rather than the detector. This bites hardest in the scenario that matters most: *no oil
plus a radar contact* is the dark-vessel case, so the contract cannot express our best evidence
precisely where NTRO cares. Minimal additive fix would be `ship_detections` as a top-level key on
the FeatureCollection, beside `features`. **Not implemented — §6.3 is frozen and CLAUDE.md
forbids extending a schema unilaterally.**

**Open — VH slide, for Urooz.** Both benchmark scenes have **usable** cross-pol (sea VH −21.9 and
−11.6 dB, above the ~−24 dB IW noise floor) while all seven live cases sit at −27.0 to −38.5 dB
and do not. D3's VV-only fallback is therefore universal on live data. The contrast is what makes
"VH is the discriminator" a **conditional finding** rather than a retreat, and the slide must say
so with the numbers.

**CORRECTED — margin distribution. My "20 detections, median 0.578" was wrong; Akshat caught it.**
The shipped answer is **12 oil detections, confidence 0.509–0.755, median 0.645**. The 20 was a
different population: it is the count of regions that PASS the rule (contrast ≤ −3.0 dB AND
elongation ≥ 2.5) *before* `--min-oil-km2 0.10` demotes the sub-floor ones. Exactly 8 are demoted
— 0.048–0.073 km², all of them — and 20 − 8 = 12. So I measured the rule's output and reported it
as the detector's output. **Nobody should quote 20.** Per case: jacksonville 3, gulf-alaska 3,
mumbai 3, farallones 1, huntington 1, jamnagar 1, ennore 0.

The dB bands survive the correction and are no longer degenerate on the right population —
**7 clear / 5 marginal** across the 12:

| contrast | case | conf | band |
|---|---|---|---|
| −6.06 | huntington | 0.755 | clear |
| −5.11 | farallones | 0.676 | clear |
| −5.05 | jacksonville | 0.671 | clear |
| −5.04 | mumbai | 0.670 | clear |
| −4.91 | jacksonville | 0.659 | clear |
| −4.82 | gulf-alaska | 0.652 | clear |
| −4.65 | mumbai | 0.638 | clear |
| −4.39 | jacksonville | 0.616 | marginal |
| −4.05 | jamnagar | 0.588 | marginal |
| −3.50 | gulf-alaska | 0.542 | marginal |
| −3.23 | mumbai | 0.519 | marginal |
| −3.11 | gulf-alaska | 0.509 | marginal |

**Open — Gulf of Alaska finds no radar contact** even under k=4: threshold −8.06 dB, scene peaks
−8.79 dB. Reported, not tuned away (A6, D2b).

**Next:** Cerulean IoU on the five cases carrying `cerulean_slick.geojson`. Unblocked — detections
are committed and pushed, so A6's sealed-answer protocol is satisfied.

---

## [2026-09-13 09:20] Phase 6.0 — merged a9087b0, fixed the -inf bug at source, Stage 1 pushed

**Done:** Merged Akshat's unblock commit. Fixed the `-inf` nodata bug in `features.py` at the
source (not left to the validator gate) and added a regression test for it. Switched
`scene_provenance()` off the CRS sniff and onto `meta.provenance` (D33). Corrected an anchoring
bug in the new `.gitignore` that would have had the push rejected. **Stage 1 is on the remote.**

**Files touched:** `pipeline/detect/features.py` (the fix + regression test) ·
`pipeline/detect/run.py` (`scene_provenance` reads `meta.provenance`) · `.gitignore` (anchoring) ·
whole of `pipeline/detect/` now tracked

**Run command:**
```bash
venv\Scripts\python pipeline\detect\features.py     # regression test for -inf
venv\Scripts\python pipeline\detect\ships.py
venv\Scripts\python pipeline\detect\nets.py
```

**1. `.gitignore` did not ignore anything — caught before staging.** Akshat's block used
`models/*`. A gitignore pattern containing a slash is anchored to the directory holding the
.gitignore, so `models/*` matches a top-level `models/` that does not exist; the real path is
`pipeline/detect/models/`. All 534 MB was still stageable and the push would have been rejected
by GitHub. Changed to `**/models/*` with the negations likewise. Separately, `classifier.pkl`
was already TRACKED from 0b506af, so ignoring could never have helped it — `git rm --cached`
was needed. Largest blob now added: `scene_classifier.pt` at 268 KB.

**2. The `-inf` fix, at the source.** `np.nanmean` ignores NaN but NOT +/-inf, so on any GEE
export (nodata `-inf`, TRAPS #22) it returned `-inf`, Sobel emitted `inf` along every
valid/nodata boundary, and `json.dumps` wrote a bare `Infinity` — which `json.loads` accepts and
`JSON.parse` rejects (TRAPS #24), so it would have died in Harshita's app with nothing upstream
complaining. Now masks first, then means. `add_shape_features_batch` additionally replaces any
non-finite feature with the -1.0 sentinel, because `inf` is not an exception and the existing
try/except never saw it. Regression test added using a real `-inf` wedge with a contour that
touches it: edge_gradient 7.89 (finite), serialises under `allow_nan=False`.

**3. Also fixed while in there:** the `features.py` PART 2 self-test read
`data/Mask/Oil/{id}_segmentation.tif`, which is Part III naming. Parts 1+2 masks are `{id}.tif`,
so that block had been erroring since the data landed.

**4. `scene_provenance()` now reads `meta.provenance`.** Verified: the seven satellite cases have
no field and default to `satellite`; both Zenodo bundles report `benchmark`. The old CRS check is
gone entirely rather than kept as a fallback — it never discriminated, so a fallback to it would
only restore the bug.

**Answers sent to Akshat:** torch/torchvision resolve on Python 3.11 (see open issues) ·
the two corrections to the headline numbers are in `receipts.md` · margin distribution still owed.

**Open issues:**
- **Python 3.11 torch resolve: confirmed by index query, NOT by installing.** There is no 3.11
  interpreter on this machine (only 3.13.5). Both `torch-2.6.0+cu124-cp311-cp311-win_amd64.whl`
  and `torchvision-0.21.0+cu124-cp311-cp311-win_amd64.whl` are published on the cu124 index, so a
  3.11 venv resolves to the same pin. If anyone has a 3.11 box, a real install is still worth one
  minute of their time.
- **Rule-margin distribution still owed to Akshat** for his 0.75/0.45 confidence bands — needs
  the seven live cases run, which is next.
- The seven live cases still have no `detections.geojson`; that is the last structural gap.

**Next:** run all seven satellite cases, then build the two benchmark bundles.

---

## [2026-09-13 00:40] Phase 6 — regularised U-Net, backfill closed, cases nominated

**Done:** Diagnosed the U-Net as OVERFITTING rather than undertrained, retrained it with domain
augmentation + weight decay, and **Part III IoU rose 15%**. Backfilled every missing label scene
(0 still failing). Nominated cases 6/7/8. Retrained Layer 1 with domain augmentation.
case-huntington-2021 still PASSES with 0 warnings.

**Files touched:** `pipeline/detect/train_unet.py` (domain aug, weight decay) ·
`train_classifier.py` (domain aug) · `backfill_labels.py` (new) ·
`docs/updates/soumirya_case_nominations.md` (new) · `models/unet.pt` + `scene_classifier.pt`
(baselines preserved as `*_baseline.pt`) · `data/labels/features_train.csv`

**Run command:**
```bash
venv\Scripts\python pipeline\detect\backfill_labels.py --parts 1,2 --out data\labels\features_train.csv --workers 4
venv\Scripts\python pipeline\detect\train.py
venv\Scripts\python pipeline\detect\train_classifier.py
venv\Scripts\python pipeline\detect\train_unet.py --epochs 45 --patience 12
venv\Scripts\python pipeline\detect\evaluate.py --report
venv\Scripts\python pipeline\detect\run.py --case case-huntington-2021 --rule-contrast -3.0 --rule-elongation 2.5
venv\Scripts\python scripts\validate_case.py cases\case-huntington-2021
```

**THE ABLATION TABLE — updated (Part III holdout, scene-level split):**

| Model | SceneAcc | LookRej | OilRec | IoU+ | IoUall |
|---|---|---|---|---|---|
| Classical (v2_vh) | - | - | 0.050 | - | - |
| Classifier only | **0.951** | 0.940 | 0.927 | - | - |
| U-Net only (no gate) | - | 0.460 | 0.967 | 0.449 | 0.404 |
| **Classifier + U-Net** | - | **0.940** | 0.920 | **0.435** | **0.426** |

**What the gate buys (D2):** look-alike rejection **0.460 -> 0.940**, clean-ocean
**0.827 -> 0.987**, IoU-over-all-scenes 0.404 -> 0.426. Larger than before.

**1. "Train longer" was the wrong prescription; the curve said overfitting.**
The first U-Net peaked at val IoU 0.6843 on **epoch 3** and decayed to 0.6258 by epoch 9 while
train loss kept falling — 31.5M parameters against 23,760 tiles with geometric augmentation
only. More epochs would have made it worse. Retrained with the same domain augmentation Layer 1
uses (blur / rescale / speckle / nodata+VH dropout) plus weight decay 1e-4, 45 epochs, patience
12. Early-stopped at epoch 31, 198.7 min.

| | baseline | regularised |
|---|---|---|
| best **validation** IoU | 0.6843 (ep 3) | 0.6793 (ep 19) |
| **Part III** IoU+ gated | 0.377 | **0.435** |
| **Part III** IoU all gated | 0.373 | **0.426** |
| train->test gap | 0.307 | **0.244** |

Validation flat, holdout up 15%. That is the signature of regularisation working, and it
confirms the diagnosis. Worth saying on stage: we did not train longer, we trained *regularised*
and then longer, because the loss curve told us which problem we had.

**2. Backfill closed — the earlier "20 scenes lost" was wrong in BOTH directions.**
55 scenes were absent from features_train.csv, not 20 (the error list in the log was truncated
at 20). Of those, **20 were real OOM failures and 35 simply produce no detections**, which is a
valid result and not a loss. All 55 re-run at 4 workers: **0 still failing.**
CSV is now 76,721 rows / 3,867 positives / 2,535 scenes producing rows, out of all 2,570
processed. The correct phrasing is "all 2,570 scenes processed", not "2,550 of 2,570".

**3. The classical baseline's Part III F1 is not a precise number.**
Adding 0.8% more training data moved it from 0.123 to 0.085 while precision IMPROVED 0.206 ->
0.286 (TP 7->4, FP 27->10). With only 80 positives in the holdout a single detection moves F1 by
~0.02. **Quote it as "F1 ~ 0.1", never to three decimals**, and say so before a judge notices it
differs between slides.

**4. Layer 1 domain augmentation: small win on the benchmark, no win on transfer.**
Scene accuracy 0.947 -> **0.951**, oil recall 0.893 -> **0.927**, look-alike rejection 0.960 ->
0.940. On Huntington it moved P(oil) 0.0025 -> 0.0141 — 5.6x, still 10x below the 0.143
threshold. **Domain augmentation does not fix the transfer gap.** The cause is not low-level
image statistics; blur/resolution/speckle/nodata are exactly what augmentation covers and they
were not it. Provenance routing stands.

**5. Cases 6/7/8 nominated** — `docs/updates/soumirya_case_nominations.md`, closing Master §14's
open item. Chosen on DETECTOR evidence, never on what the classifier says about them, so they
are the hardest available rather than staged wins. Case 6 `P3_Lookalike_00134` is a −9.05 dB,
47.4 km², elongation-21.2 streak that reads exactly like a chronic discharge — rejected at
**P=0.0020** against a 0.143 threshold (0.0008 before the retrain). Cases 7/8 `P3_No oil_00091` / `P3_No oil_00027` rejected
at 0.0003 / 0.0013. All three re-verified after the Layer 1 retrain: no regression.

**6. A hypothesis I tested and dropped.** The large-slick failure (recall 0.167 above 30% oil
coverage) looked like it should be fixed by using a high percentile instead of the median as the
normalisation reference, since sea is brighter than oil. Tested on the 12 affected scenes: it
made things **strictly worse** (recall 0.167 -> 0.083 -> 0.000 at p70/p80/p90), because the model
was trained on median-normalised input and any shift compounds the mismatch. Testing it properly
needs a 100-minute cache rebuild plus retrain, and the evidence points away. Dropped rather than
pursued. It stays a reported limitation.

**Open issues:**
- The honest headline is still two numbers: **0.951 scene accuracy / 0.435 gated oil IoU on the
  Zenodo Part III holdout**, AND **the networks do not transfer to GEE exports — real cases run
  the classical detector with a stated rule.**
- **Shortcut rate is 20.1% on the shipped classifier** (re-measured after the retrain; it was
  17.2% before, so augmentation made it slightly WORSE). Of 139 Part III scenes called oil, 28
  are still called oil once the slick is erased from them. Median P(oil) collapses 0.996 ->
  0.0048, so the model overwhelmingly does use the slick — but that fifth rests on scene-level
  appearance and ships next to the headline, stated, not waited-for.
- **The large-slick failure improved a lot and is no longer the worst caveat.** Recall above 30%
  oil coverage went 0.167 -> **0.417** (n=12), and below it 0.957 -> 0.971 — almost certainly the
  nodata-block augmentation teaching the network to survive large uniform regions. Still a real
  limitation, still reported: a slick that fills the frame becomes its own median.
- Stale `case-ennore-2017` / `case-golden-ray-2021` folders and their `cases/index.json` entries
  should be removed (D17/D18) — the frontend reads that index.
- Master §8.2's dependency graph still shows a `known_origin` path for trace. D17/D18 removed
  both known_origin cases, so **every trace case now requires detections.geojson from Stage 1.**
  Anushka has been told; Akshat should update the graph.
- Five of six real cases (Menuett, Panagia, Alaska, Mumbai, Jamnagar) have no GeoTIFF yet.
  Mumbai and Jamnagar are EASTERN hemisphere — the first cases where a longitude sign error
  cannot hide.

**Next:** re-run `audit_shortcut.py` against the new Layer 1; run the remaining five cases as
Akshat's exports land.

---

## [2026-09-12 21:00] Phases 2-5 — networks trained, audited, and routed around honestly

**Done:** Tile cache built (28,059 tiles, 11 GB). Layer 1 and Layer 2 trained and evaluated on
the Part III holdout. Ran a shortcut audit on the classifier. Found the networks do NOT transfer
to GEE case exports, chased that down properly, and routed real cases to the classical detector
plus the brief's documented rule. **case-huntington-2021 now PASSES with 0 warnings and
correctly returns exactly 1 oil feature on the real slick.**

**Files touched:** `pipeline/detect/build_cache.py` · `train_classifier.py` · `train_unet.py` ·
`nets.py` · `evaluate.py` · `audit_shortcut.py` (new) · `run.py` (`scene_provenance`,
`vh_is_usable`, `--path`) · `models/{scene_classifier,unet}.pt` ·
`cases/case-huntington-2021/detections.geojson`

**Run command:**
```bash
venv\Scripts\python pipeline\detect\build_cache.py --parts 1,2
venv\Scripts\python pipeline\detect\train_classifier.py
venv\Scripts\python pipeline\detect\train_unet.py
venv\Scripts\python pipeline\detect\evaluate.py --report
venv\Scripts\python pipeline\detect\audit_shortcut.py
venv\Scripts\python pipeline\detect\run.py --case case-huntington-2021 --rule-contrast -3.0 --rule-elongation 2.5
venv\Scripts\python pipeline\export\build_case.py --case case-huntington-2021
venv\Scripts\python scripts\validate_case.py cases\case-huntington-2021
```
Expected: `PASS acts=['detect'] (0 warning(s))`, 9 features, 1 'oil', 42 ships.

**THE ABLATION TABLE (Part III holdout, scene-level split):**

| Model | SceneAcc | LookRej | OilRec | IoU+ | IoUall |
|---|---|---|---|---|---|
| Classical (v2_vh) | - | - | 0.087 | - | - |
| Classifier only | **0.947** | 0.960 | 0.893 | - | - |
| U-Net only (no gate) | - | 0.560 | 0.927 | 0.382 | 0.363 |
| **Classifier + U-Net** | - | **0.960** | 0.893 | 0.377 | **0.373** |

**What the gate buys (D2, measured):** look-alike rejection **0.560 -> 0.960**, clean-ocean
**0.660 -> 0.987**, while IoU on positives barely moves (0.382 -> 0.377). The dataset authors'
claim that U-Net segments erroneously on look-alikes is confirmed on our own run, and the gate
is what fixes it. This is a slide.

**THE CAVEATS THAT SHIP NEXT TO 0.947 — measured, not hedged:**

1. **Shortcut rate 17.2%.** `audit_shortcut.py` erases the GT slick from all 150 Part III oil
   scenes (filling with surrounding sea level) and re-scores. Median P(oil) collapses 0.9967 ->
   0.0025, so the classifier overwhelmingly IS looking at the slick. But of 134 scenes it called
   oil, **23 still say oil with no oil in them.** That fraction of the headline rests on
   scene-level appearance, not on the slick. Report it; do not wait to be asked.
2. **It fails when oil dominates the scene.** Recall is 0.957 when oil covers <=30% of the frame
   and **0.167 when it covers >30%** (n=12). Per-scene MAD normalisation makes a huge slick its
   own median, so the oil normalises to "background" — the same self-contamination that killed
   the v1 annulus CFAR detector, reappearing one layer up.

**THE BIG ONE — the networks do not transfer to GEE exports.**
Layer 1 returns **P(oil) = 0.003** on Huntington, whose slick is unmistakable at -5.78 dB VV.
Before routing around this I ruled out, one at a time:
- VH noise — feeding (VV,VV) instead of (VV,VH) made it *worse* (0.0004)
- ground scale — resampling to 80/60/40 m/px to match the training footprint: 0.0020/0.0033/0.0016
- bright ships — masking the 42 anchored vessels at -10/-13/-15 dB: 0.0045/0.0060/0.0049
- nodata — filling the wedge with sea level instead of 0: 0.0014
- slick size — ruled out hardest: Part III scenes at Huntington's exact oil fraction
  (0.010-0.020) are detected **100% of the time at median P=0.999**

I also built a statistical domain check and **threw it away**: measured against all 2,565
training scenes, Huntington sits INSIDE the training range on texture (lap-var 0.085 in
0.035-0.144), spread and nodata. Picking cutoffs that excluded it would have been fitting the
check to one scene, which A6 forbids.

**Resolution (D7 + section 6.4):** `scene_provenance()` routes by PROVENANCE, which is known a
priori and cannot be rigged — Zenodo benchmark scenes carry no CRS, GEE exports carry EPSG:4326.
Benchmark scenes -> the networks, which is what they were trained and validated for. Case
exports -> the classical detector plus the rule documented in the brief, `contrast_db <= -3.0
AND elongation >= 2.5`. On Huntington that rule separates the slick (-6.06 dB, elongation 3.77)
from eight clutter regions (-1.70 to -1.93 dB) cleanly. **The rule predates the scene** — it is
section 6.4's, written before anyone looked at this imagery — and no threshold was moved toward
it. Rule verdicts report a stated MARGIN in [0,1], not a manufactured probability.

**Checkpoint artefact:** `scratch/check_case-huntington-2021.png` — oil polygon traces the slick,
8 look-alikes correctly amber in the coastal wind-shadow band, 42 ship crosses on the bright
targets, hemisphere W/N, nothing mirrored. Both gates pass.

**Open issues:**
- **The honest headline is two numbers, not one.** "0.947 scene accuracy on the Zenodo Part III
  holdout" AND "the networks do not currently transfer to GEE-domain scenes; real cases run the
  classical detector with a stated rule." Anything that implies the CNN is finding the
  Huntington slick would be false.
- **Domain augmentation is the real fix** and was not attempted (blur / resolution / speckle /
  nodata jitter, then retrain). It is the single highest-value remaining experiment, ~30-40 min,
  and it could put the networks back on the real cases. Worth doing before the freeze if time.
- Layer 2's validation IoU was 0.69 but Part III IoU is 0.377 — the same train/test population
  gap as the classical model. Reported, not hidden.
- The 20 OOM-dropped scenes from Phase 1 are still missing (2,550 of 2,570 used).
- Cases 6/7/8 (Zenodo look-alike, no-spill, `P3_No oil_00027`) not yet built as bundles. They
  ARE benchmark scenes, so they route to the networks, which is where the networks are strong —
  look-alike rejection 0.960, clean-ocean 0.987.

**Next:** build cases 6/7/8 from Part III scenes and verify each returns zero oil features; then
domain augmentation for Layer 1 if time allows.

---

## [2026-09-12 16:35] Phase 1 — clean split, 48x more positives, and three findings that matter

**Done:** Labelled all 3,020 scenes with the part-aware harness. Retrained the classical model
on the real split (fit on Parts I+II, evaluate ONLY on Part III). Added a VV-only fallback model
and an a-priori VH-usability test. Fixed a design error in my own scene-relative features.

**Files touched:** `pipeline/detect/make_labels.py` · `pipeline/detect/train.py` ·
`pipeline/detect/run.py` (`vh_is_usable`) · `data/labels/features_train.csv` (75,708 rows) ·
`data/labels/features_test.csv` (4,085 rows) · `models/classifier.pkl` +
`models/classifier_vv_only.pkl`

**Run command:**
```bash
venv\Scripts\python pipeline\detect\make_labels.py --parts 1,2 --overlap-threshold 0.25 --out data\labels\features_train.csv --workers 8
venv\Scripts\python pipeline\detect\make_labels.py --parts 3   --overlap-threshold 0.25 --out data\labels\features_test.csv  --workers 8
venv\Scripts\python pipeline\detect\train.py
```
Expected: 75,708 train rows / 3,851 positives; the three-row ablation table; two .pkl files.

**Checkpoint artefact:** the ablation table below. Data starvation is FIXED — 3,851 positive
rows against the 80 we had (48x), 5.09% positive rate against 1.96%, and Lookalike/No-oil
contributed exactly 0 positives as the hard-negative rule requires.

| feature set | val F1 | Part III F1 | precision | recall |
|---|---|---|---|---|
| v1_absolute (= VV-only fallback) | 0.347 | 0.077 | 0.079 | 0.075 |
| **v2_vh (shipped)** | **0.656** | **0.123** | 0.206 | 0.087 |
| v3_relative | 0.647 | 0.031 | 0.042 | 0.025 |

**THREE FINDINGS, all of which change what we say on stage:**

1. **Parts I+II and Part III are different slick populations.** Part I positives sit 4.72 dB
   below background on seas with noise MAD 2.53; Part III positives sit 0.73 dB below on seas
   with MAD 0.55. The classical RF does not transfer between them: validation F1 0.657 ->
   holdout F1 0.123. I tried six regularisation settings (max_depth, min_samples_leaf) chosen
   on validation — **every one made Part III strictly worse, five of them to F1 0.000.** This
   is not a tuning problem. It is the honest ablation number and it is the argument for the
   network path, which normalises per scene instead of using absolute features.

2. **"VH is the discriminator" needs a qualifier: only while VH is above the sensor noise
   floor.** Measured inside vs outside the Huntington slick polygon: **VV −5.78 dB, VH +0.56 dB.**
   Sea VH there sits at −27.8 dB, at/below Sentinel-1 IW NESZ (~−24 dB), so the band is thermal
   noise — and oil cannot damp noise. Zenodo's sea VH is ~−20.7 dB, above the floor, which is
   why VH works there. Since the shipped model's top two features are VH (69% of importance
   combined), silently trusting VH is exactly how an unmistakable slick scores 0.01. Handled by
   `vh_is_usable()` in run.py: a scene-level physics test that never looks at where a slick is,
   switching to the VV-only model (D3) rather than zero-filling VH columns.

3. **My v3_relative hypothesis was wrong and is withdrawn.** I predicted scene-relative (SNR)
   features would transfer better. They transfer *worse* (F1 0.031 vs 0.123). I did find and fix
   a real error in them along the way — I divided depth by MAD without subtracting the noise
   floor first, leaving a med/mad term that re-introduced the scene dependence I was removing;
   centred, the feature matches across parts to 2% where the uncentred form differed by 14%.
   Centring improved v3 (0.020 -> 0.031) but nowhere near enough. I also removed the tie-break
   in train.py that preferred v3 on the argument that "Part III cannot measure transfer" —
   Part III demonstrably IS a different domain, so it does measure transfer, and v3 lost.
   Selection is now purely validation F1, which picks v2_vh.

**Open issues:**
- **20 of 2,570 scenes (0.8%) were lost to out-of-memory during labelling** — the run used 12
  workers while the tile cache was building concurrently, and each worker holds a full-scene
  bool mask per region. 5 were Oil scenes. Negligible for training, but the numbers are "2,550
  of 2,570 scenes" and should be quoted that way. Re-running just those 20 is cheap if wanted.
- **Huntington still classifies as 0 oil.** The detector finds the slick perfectly (det-09,
  −6.06 dB, 2.64 km², elongation 3.77) but no classical model scores it above threshold. On
  held-out data this model's positives score 0.128 and its negatives reach 0.257 at p95 — the
  distributions overlap, so there is no operating point that works. NOT fixed by tuning toward
  Huntington (A6: it is a reported observation, never a selection criterion). The real fix is
  Layer 1 + Layer 2; if they also fail, the documented §6.4 rule (contrast < −3 dB AND
  elongation > 2.5) cleanly separates det-09 from the other eight on this scene — and that rule
  is the brief's, written before anyone saw this scene.
- `area_km2` may carry an inverse size bias from the labelling rule: a region is positive only
  at >=25% GT overlap, which large regions rarely achieve against small GT masks, so training
  positives have median area 0.07 km2. Not confirmed as harmful (importance only 0.13, and
  zeroing it out barely moved the score), but worth a look if the RF is ever revisited.

**Next:** Phase 2 tile cache finishes (~58 min, 8.3 GB, 23.6k tiles so far), then Layer 1
(`train_classifier.py`) and Layer 2 (`train_unet.py`). Those are the product; the classical
path above is the ablation baseline and the ship detector.

---

## [2026-09-12 05:10] Phase 0 — real run.py, ship detections, chronic/acute, first PASS

**Done:** `run.py` is no longer a stub — it reads `sar_vv_vh.tif`, runs the detector with VH,
adds shape features, detects ships, classifies discharge, scores regions and writes a
contract-compliant `detections.geojson`. **`cases/case-huntington-2021` PASSES the validator**
(1 warning, see below). `ship_detections` and `discharge_class` are now shipping with REAL
values, not stubs — Jaiveer and Anushka are unblocked. VH extraction moved inside
`extract_regions()`, which deletes the `area_px`-proximity join that could silently attach the
wrong VH stats to a region (S1 + S6 both closed). CUDA PyTorch 2.6.0+cu124 installed and
verified on the RTX 4050 — **this amends the dependency freeze, see open issues.**

**Files touched:** `pipeline/detect/run.py` (rewritten) · `pipeline/detect/ships.py` (new) ·
`pipeline/detect/darkspot.py` (modified — `db_vh=` on `detect_array`/`extract_regions`) ·
`pipeline/detect/make_labels.py` (rewritten — part-aware layout, VH, scene stats, parallel) ·
`scripts/plot_detections.py` (new) · `requirements.txt` (torch pinned) ·
`cases/case-huntington-2021/detections.geojson` (output)

**Run command:**
```bash
venv\Scripts\python pipeline\detect\run.py --case case-huntington-2021
venv\Scripts\python pipeline\export\build_case.py --case case-huntington-2021
venv\Scripts\python scripts\validate_case.py cases\case-huntington-2021
venv\Scripts\python scripts\plot_detections.py --case case-huntington-2021
venv\Scripts\python pipeline\detect\ships.py          # self-test
```
Expected output: 9 regions, 42 radar contacts, `PASS acts=['detect'] (1 warning(s))`, and
`scratch/check_case-huntington-2021.png`.

**Checkpoint artefact:** `scratch/check_case-huntington-2021.png`. The detector's `det-09`
polygon traces the Huntington slick almost exactly — centroid `[-118.09044, 33.6397]`,
2.64 km², elongation 3.77, **contrast −6.06 dB**. The other 8 candidates all sit in a broad
faint band along the coast (wind shadow) at ~−1.8 dB and are correctly rejected. The 42 ship
crosses land dead on the bright targets — San Pedro Bay was at the peak of the 2021 container
backlog, so a full anchorage is the expected answer, not a bug.

**Open issues:**
- **det-09 is scored `lookalike` at confidence 0.00 — the one real error, and it is the
  classifier, not the detector.** The 8-feature RF was trained on Zenodo, whose positives run
  −0.44 to −1.04 dB. A −6.06 dB slick is off the end of its training distribution and a random
  forest cannot extrapolate. This is decision-D1's domain gap, now demonstrated rather than
  predicted. Fix in progress: `make_labels.py` now also records `sea_ref_db`, `noise_median`
  and `noise_mad` per scene so `train.py` can build scene-RELATIVE features
  (`contrast_db / noise_mad`) that mean the same thing in every domain. Evidence it will work:
  `P3_No oil_00010` already has `sea_ref_db −19.2, noise_mad 2.11` — Huntington-like statistics
  inside Zenodo, so the training set does contain the domain.
- **Dependency freeze amended — Akshat must broadcast.** `torch==2.6.0` + `torchvision==0.21.0`
  (cu124) added to `requirements.txt`. Master v3 §4.3 and D2/D4 make the CNN and U-Net part of
  the shipped architecture, so the old "nothing here needs a GPU" note no longer holds for
  `pipeline/detect/`. Install via the PyTorch index, not plain PyPI.
- **`bounds.json` vs GeoTIFF mismatch on Huntington.** `bounds.json` says 505×577 (that is
  `sar.png`); `sar_vv_vh.tif` is 1337×1281. Worked around by georeferencing from the tif's own
  affine transform, with a hard assert that its bbox matches `bounds.json`. Akshat to confirm
  this is intended and not a truncated export.
- **Contract gap:** `ship_detections` is nested inside a detection's `properties` (§6.3), but
  ships are a scene-level observation. Currently the full scene list is attached to every
  feature. A case with ZERO detections has nowhere to put its ships. Akshat's call.
- The detector's threshold on Huntington resolved to 8.34 dB because `k_high × noise_mad`
  (3 × 1.95) dominates the 2.0 dB floor. It still found the slick, but on a fainter real slick
  it would not. Revisit once the normalised path exists.
- `pipeline/detect/CLAUDE.md` still says "NO deep learning this sprint" and "Zenodo Part III
  only" — both now contradicted by Master v3 and by what is on disk. Update in Phase 6.

**Next:** Phase 1.4 — retrain on the clean split (train on Parts 1+2, evaluate ONLY on Part 3)
with the scene-relative features added. Label runs for all 3,020 scenes are in flight.

---

## [08-Sep-2026] , 6:45 PM IST — Soumirya

DONE:
- Fixed 4 real bugs in pipeline/detect/darkspot.py's local-threshold detector:
  (1) hardcoded -25/0 display clamp was rendering real scenes as solid black
      (Oil scenes actually sit ~-29 to -30 dB); fixed with per-scene p2/p98
      percentile display clamp.
  (2) Zenodo Part III uses exact 0.0 as land/nodata fill (not NaN, no rasterio
      nodata tag) — was silently corrupting CFAR background stats; now masked.
  (3) bright point-targets (ships, >~-10dB) were inflating nearby background
      mean/std, causing false "dark halo" rings around them; now masked.
  (4) plain box-average local threshold self-contaminates on any feature wide
      relative to the window (mean/std pulled toward the feature); replaced
      with annulus/CFAR-style background (window minus a guard hole).

NOT DONE / BLOCKED:
- Ran check_gt_overlap.py across 10 random Oil scenes (00103, 00033, 00114,
  00055, 00130, 00065, 00014, 00145, 00137, 00131) at k=1.5/guard=25/window=71:
  0/10 scenes produced any region overlapping real GT oil.
- Root cause investigation found: at least one large scene (00014, 29.77% GT
  oil coverage) shows scene-wide diagonal brightness banding (subswath seam /
  antenna roll-off) spanning several hundred px per band — likely larger than
  any single practical window size, meaning local mean/std stays unreliable
  scene-wide, not just near oil. Attempting a detrend-then-threshold fix
  (large-kernel trend removal before CFAR) as of this log; result TBD.
- Separately confirmed via a synthetic test (matched to real measured stats:
  sea std=0.9dB, oil contrast=-4.25dB) that proximity to land/strong features
  independently suppresses real detections by contaminating nearby background
  stats — a second, distinct mechanism from the banding issue above.

FILES TOUCHED: pipeline/detect/darkspot.py, scripts/check_gt_overlap.py,
scripts/where_is_oil.py (new diagnostic scripts, not part of the pipeline
contract — safe to keep or delete later)

RUN COMMAND: python pipeline/detect/darkspot.py data/Images/Oil/<id>.tif --out preview.png
             python scripts/check_gt_overlap.py <id>

OPEN QUESTION FOR TEAM: classical adaptive thresholding may not be reliable
across this dataset's scene-to-scene radiometric variation (subswath seams,
large slick-to-frame-size ratio up to ~30%). CLAUDE.md's own note that the
published CNN benchmark sits ~53% IoU suggests this is a genuinely hard
problem, not something classical CV should be expected to nail cleanly —
worth discussing whether the Tuesday plan needs adjusting (e.g. lean harder
on VH band, which is currently unused, or accept a narrower target: reliable
detection on Ennore specifically rather than general robustness across all
150 dataset scenes).

DETREND ATTEMPT (later same night):
Tried removing the large-scale gradient via uniform_filter (box blur) at 
sigma=301/501/801 before running CFAR, on scenes 00014 and 00081. Checked 
the residual visually BEFORE running detection (per stop condition), per 
instructions.

RESULT: Failed cleanly, did not proceed to detection.
- Banding did not disappear at any tested sigma — still clearly visible in 
  all residual plots.
- Residual std slightly INCREASED with larger sigma (00014: 0.76 -> 0.81; 
  00081: 2.18 -> 2.54), the opposite of what successful detrending should do.
- Diagnosis: uniform_filter is a box blur, which handles sharp discontinuities 
  (like these subswath seam edges) poorly — smoothing across a sharp boundary 
  creates a ringing artefact (dark/bright overshoot) right at the edge instead 
  of removing it. The seams appear to be closer to step-like boundaries than 
  smooth gradients, so a moving-average detrend is the wrong tool.
- STOPPING HERE for tonight per plan. Not attempting further fixes solo — 
  escalating to team.

STATUS: Phase 2 Step 1 (dark-spot detector) is NOT producing reliable 
real-oil detections as of tonight. 4 real bugs fixed and confirmed with 
evidence; underlying scene-wide radiometric variation (subswath banding) 
appears to be a structural limitation of single-scale local thresholding on 
this dataset, not something more k/window/close tuning will resolve. Needs 
team discussion before further solo debugging.

NEXT IDEA (not attempted, logged for later — NOT tonight):
Try scipy.ndimage.median_filter instead of uniform_filter for the trend 
estimate — medians handle step edges without the ringing a box-mean 
introduces. Worth one clean test with fresh eyes, not at 2+ AM.