# Soum — update log

*Newest entry at the TOP. Copy the block from `TEMPLATE.md`, fill four lines, commit it with
your code in the same push. Two minutes after each phase — non-negotiable.*

**Why:** your AI has no memory between chats. This file is the memory. It means you can close a
chat, switch from Claude to ChatGPT, hand your work to someone else, or come back after sleeping,
and lose nothing.

**To resume from it:** *"Here are the master plan, my task document, and my update log. Read the
top entry and tell me exactly where I left off and what the next step is."*

---

<!-- Your first entry goes here. Setup counts as a phase: what you installed, what ran, what
     printed PASS, what is still broken. -->

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
`docs/updates/soum_case_nominations.md` (new) · `models/unet.pt` + `scene_classifier.pt`
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

**5. Cases 6/7/8 nominated** — `docs/updates/soum_case_nominations.md`, closing Master §14's
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

## [08-Sep-2026] , 6:45 PM IST — Soum

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