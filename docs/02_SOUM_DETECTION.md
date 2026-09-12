# SOUM — Stage 1: Detection
*v2. Read with 00_MASTER_PLAN.md. Organised in phases, not days. Finish a phase, log it, move on.*

---

# PART A — WHERE YOU STAND

## A1. What you built, and what's genuinely good about it

**The v1 to v2 detector diagnosis.** You used an annulus CFAR detector, found it failing, and worked out *why*: the annulus protects a compact blob from contaminating its own background statistics, but an oil slick is a **line**. A linear slick runs straight through the guard ring, drags the local mean down, inflates the local std, and pushes the threshold away from the slick exactly where the slick is. A -4 dB streak on a -1 dB sea becomes invisible. You proved that synthetically in `test_synthetic.py` before abandoning v1.

That is a real diagnosis, not a guess, and most people would have tuned parameters for two days instead.

**The v2 morphological depth-map.** Multi-scale closing minus smoothed background, hysteresis at `med + max(2.0, 3*MAD)` strong and `med + max(1.0, 1.5*MAD)` weak, keeping weak components that touch a strong pixel. This matches what SNAP's oil-spill operator and the Solberg/Brekke literature actually do. Closing uses the surrounding maximum, so a feature cannot raise its own background estimate — the exact failure v1 had.

**Noise-relative thresholds.** Median + k*MAD instead of fixed dB. This is the single most important design decision in your code, because Zenodo scenes sit at ~-29 dB and GEE scenes at ~-20 dB. Any fixed-dB threshold would work on one and fail on the other. Hold onto this instinct — section D1 is entirely about extending it.

**Bright-outlier masking with a 5-px dilation halo.** Ships and rigs produce a dark halo that a naive detector reads as oil. You masked it. Nobody told you to.

**Scene-level split.** `train_test_split` on unique `scene_id` strings with `stratify` on has-positive. You did this when a row-level split would have handed you a much prettier number, and you wrote down why it would have been indefensible. That instinct is worth more than the model.

**Globally-unique scene ids** (`Oil_00007`, not `00007`) because `Oil/00007` and `Lookalike/00007` are different scenes sharing a number. That collision would have silently corrupted every scene-level grouping operation.

**The VH discovery — the single most valuable finding anyone on this team has made.**

```
vh_mean_depth_db   importance 0.3155   <- rank 1, 2x any VV feature
mean_depth_db      importance 0.1583
max_depth_db       importance 0.1483
...
vh_contrast_db     importance 0.0727   <- rank 6
```

F1 went 0.086 -> 0.276 on two features. Your physical explanation is correct and it is the reason this works: ocean clutter — upwelling, rain cells, wind shadow — damps the **VV** channel. Real oil damps capillary waves through Marangoni effects, which suppresses **both** polarisations. So dark-in-VV-but-normal-in-VH is a look-alike; dark-in-both is oil. **VH is the discriminator, and it is the physics of the problem.**

This gets its own slide, and it is the answer when a judge asks what is novel about your detection.

## A2. What you flagged

| # | Item | Status |
|---|---|---|
| S1 | VH features live in `scratch/add_vh.py`, not in `make_labels.py` | fixed in Phase 1 |
| S2 | `train.py` still on 8 features; current pickle came from a scratch script | fixed in Phase 1 |
| S3 | `run.py` is a stub — the actual deliverable | Phase 6 |
| S4 | VH availability for Ennore unknown | **RESOLVED — see A4** |
| S5 | Documented -3 dB fallback rule matches **zero** training positives | Phase 6.4 |
| S6 | VH region-matching by `area_px` proximity <10 px could mismatch | fixed in Phase 1.3 |

## A3. Problems I found that nobody raised

**You are data-starved, not method-broken. This is the headline.**

The dataset is titled *"Sentinel-1 SAR Oil spill image dataset for train, validate, and test deep learning models."* Parts I and II are the train/validate halves. **Part III is the designated test set.** You trained and tested on Part III alone. Two separate problems:

1. You used roughly a fifth of the available imagery — 450 scenes when 2,335 exist.
2. You used the authors' designated *test* set as *training* data, so you have no clean generalisation estimate at all. Every number you have is optimistic by an unknown amount.

**Your recall ceiling is set by the detector, not the classifier.** 121 of 150 oil scenes produce zero GT-overlapping candidates. Before the Random Forest sees a single row, ~80% of the oil is already gone. No classifier improvement can recover it. **This is why we are changing the architecture** (Part B) rather than tuning the RF.

**The area-match VH join is a silent failure waiting to happen.** Matching regions between two `detect_array` calls by `area_px` difference under 10 pixels mismatches whenever two regions have similar areas — and it will not error, it will attach the wrong VH statistics to the wrong region. Since VH is your top feature, that corrupts your best signal invisibly. Fixed by extracting VH inside `extract_regions()` from the same mask.

**Your positives have a very shallow signal.** Contrast runs only -0.44 to -1.04 dB at the 5th-95th percentiles. SAR literature assumes 3-6 dB for tanker spills. Two consequences: your Zenodo training distribution is a *hard* distribution, and a real tanker collision may look nothing like it. Plan for the domain gap (D1); do not discover it on demo day.

**You have been benchmarking against the wrong number.** See B2.

## A4. What is now resolved — the case library is locked

**Six spill cases plus two rejection cases, all real data.** The library straddles both hemispheres and four ocean basins, which is good for your generalisation claim and dangerous for any assumption baked in against one case.

| # | Case | Where | Your job |
|---|---|---|---|
| 1 | **Menuett** 2024-07-30 | Atlantic, 30.4 N −79.6 W | Hero. 31 km linear slick, expect `chronic` |
| 2 | **Panagia Thalass…** 2023-03-17 | Pacific, 37.8 N −123.9 W | 20 km linear |
| 3 | **Huntington Beach** 2021-10-02 | San Pedro Bay, 33.6 N −118.1 W | Comma-shaped, sea −20.9 dB VV, core −28 to −32 |
| 4 | **Alaska dark vessel** 2023-05-16 | Gulf of Alaska, 59.6 N −142.7 W | 2 km, 0.3 km² — **the smallest slick in the library.** Also: **find the bright target 4.5 km away**, it is the whole case |
| 5 | **Mumbai** 2023-09-03 | Indian EEZ, 18.5 N 72.2 E | 21 km, 7.7 km². Carries infrastructure + dark vessel + natural-seep flag |
| 6 | **Jamnagar** 2024-02-23 | Arabian Sea, 20.15 N 71.9 E | 21 km hook — measured ~8 dB VV depression, VV −25.41 vs clean −17.24 |
| 7 | **Look-alike** Ennore 2023-11-30 | Bay of Bengal | **Correct output is zero oil features** |
| 8 | **No-spill** Zenodo Part 3 | — | **You nominate this one.** Correct output is zero oil features |

**Ennore 2017 is archived (D18) and Golden Ray is dropped (D17).** Neither is your problem any more.

**Akshat exports a 2-band float32 GeoTIFF in dB, not an 8-bit PNG.** Insist on this if it ever slips. Your signal is ~1 dB deep; an 8-bit PNG quantises the usable dB range into 256 levels and destroys VH precision. He generates the PNG separately, for display only.

> WAIT / FLAG: **VH per case is confirmed by Akshat running `bandNames()`** as he exports. Post-2016 acquisitions are overwhelmingly VV+VH IW, so this is very likely fine everywhere — but if any case comes back VV-only he tells you which, and the VV-only fallback applies for that case alone (D3), noted honestly on the results slide.

## A5. Two things that are new and both are for you

**You now have real-incident ground truth for segmentation.** Akshat is downloading the **Cerulean slick polygon** for every case it has. Right now every IoU number you own comes from the Zenodo test set. With those polygons you can say:
> *"On the Huntington Beach scene our segmentation achieves X IoU against SkyTruth Cerulean's operational detection of the same slick."*

That is a completely different claim from benchmark-only figures, and it is available for four or five cases rather than zero.

**But the polygons arrive AFTER your detector has run.** See A6.

## A6. Blind evaluation — read this before you start

**You are not told where the slick is.** Akshat holds the documented answer for every case in a sealed file. You get `sar_vv_vh.tif`, `sar.png`, `bounds.json`, and nothing else.

Why: if you know where the slick is, you will lower the threshold until it appears. That is not dishonesty, it is what anyone does when the target is visible — and it collapses *"our detector found it"* into *"we tuned until it did."* A December panel will ask which happened.

So: **run your pipeline, commit the output, and only then ask Akshat for the Cerulean polygon** to compute IoU. The comparison is only meaningful in that order.

He will not answer *"is this right?"* during the week. That is deliberate, not unhelpfulness.

---

# PART B — THE ARCHITECTURE

## B1. Three layers, not two

Your current pipeline is: threshold detector finds blobs -> hand-crafted features -> Random Forest sorts them. The detector is the bottleneck. We replace it and keep everything downstream.

```
+------------------------------------------------+
|  LAYER 1 - Scene classifier (small CNN)         |
|  "Is there any oil in this scene at all?"       |
|  -> yes/no + confidence                          |
|  -> THE HEADLINE ACCURACY NUMBER                 |
+------------------------+-----------------------+
                         | only if YES
+------------------------v-----------------------+
|  LAYER 2 - U-Net segmentation                   |
|  "Exactly which pixels?"                         |
|  -> binary mask -> contours -> polygons          |
|  -> THE IoU NUMBER, and the slick Stage 2 seeds  |
+------------------------+-----------------------+
                         | per region
+------------------------v-----------------------+
|  LAYER 3 - Your classical features (KEEP ALL)   |
|  elongation, edge_gradient, contrast_db,         |
|  solidity, vh_contrast, vh_mean_depth            |
|  -> shape_class, discharge_class, "why" bars     |
|  -> THE EXPLAINABILITY A CNN CANNOT GIVE         |
+------------------------------------------------+
```

**Why the classifier goes first, and why it is not optional.** The dataset's own authors built a two-step framework for exactly this reason: their paper reports the U-Net *segments erroneously on look-alike images*, and that the classification-then-segmentation scheme is what reduces false positives in look-alike scenarios. If you run U-Net alone, your look-alike case and your no-spill case come back with hallucinated oil — and those two cases exist in the demo specifically to prove the system can say **no**.

It is also cheap: a small CNN on downsampled whole scenes trains in minutes, not hours.

**Why your classical work is not thrown away.** Layer 3 is your existing `features.py`, unchanged, running on U-Net contours instead of threshold blobs. Every feature survives. The "why this classification" bar chart — the thing that makes a judge trust the answer — is only possible because of Layer 3. A pure CNN gives a mask and no reasoning.

Your existing depth-map detector also survives in three roles: the **ablation baseline**, the **fallback** when the CNN misbehaves on a GEE-domain scene, and the **ship detector** (5.1).

## B2. The accuracy question, answered honestly

You have been quoting ~53% IoU as the state of the art. That number is from the **Krestenitis** 5-class benchmark — the EMSA CleanSeaNet dataset that is not openly available and requires a proposal. **It is not your dataset.**

Your dataset's own authors published their results (Trujillo-Acatitla et al., *Marine Pollution Bulletin* 204:116549, 2024):

- **CNN scene classification: 99% accuracy** — six layers, 32 filters, two hidden layers
- **U-Net segmentation: 99% accuracy, 96% IoU** — deeper/wider U-Net using **Focal Loss**
- Their `16 -> 32 -> 64 -> 128 -> 256 -> 512 -> 1024` configuration with Upsampling2D in the expansion path achieved the highest IoU

So >80% is achievable. But **the framing matters more than the number**, and the honest framing is stronger than either:

> "We report on the dataset's own benchmark, where the authors achieve 96% IoU. We achieve X on their designated held-out test set — the same split they used. On the harder Krestenitis look-alike benchmark, published state of the art is around 53%. The gap between those two numbers is not a difference in model quality; it is a measure of how much look-alike variety a dataset contains. That gap is our result, not our excuse."

This inoculates you against the obvious attack — *"why is your number so much higher than the literature?"* — and turns it into evidence you understand your own evaluation.

**The four numbers to report, in this order:**

| Metric | What it means | Realistic target |
|---|---|---|
| **Scene classification accuracy** | Does this scene contain oil? | **>90%** — your headline |
| **Look-alike rejection rate** | Of 150 look-alike scenes, how many correctly called no-oil | **>85%** — arguably more persuasive than the headline |
| **Segmentation IoU** (oil class, positives only) | Pixel overlap with ground truth | 60-90% depending on how close you get to their config |
| **Classical baseline F1** | Your existing pipeline, same holdout | whatever it is — this is the ablation |

Never quote a single unqualified percentage. Always name the metric and the split.

---

# PART C — THE PHASES

## PHASE 1 — Data foundation

*Everything else rests on this. Nothing here needs Akshat.*

### 1.1 Download Parts 1 and 2
- **Part I** — `zenodo.org/records/8346860` — 40.7 GB, one `.7z`, 1,200 oil scenes + 1,200 masks
- **Part II** — `zenodo.org/records/8253899` — 685 oil-free + look-alike scenes with masks; **size unverified, check before you start**

**Check disk first.** Part 1 alone needs ~85 GB (archive and extraction coexisting). Budget ~150 GB across both. If you do not have it: extract Part 1, delete the archive, then do Part 2. Tell Akshat immediately if disk is the blocker — an external drive is a cheaper fix than a redesign.

Start both downloads before anything else; they run unattended.

### 1.2 Verify structure
Confirm Parts 1 and 2 match Part 3's layout: `Images/{class}/*.tif` at 2048x2048x2 float32 dB (band 1 = VV, band 2 = VH), `Mask/{class}/{id}_segmentation.tif` binary. If folder naming differs, adapt `make_labels.py`'s path logic rather than renaming 2,000 files.

**Prefix scene ids by part as well as class** — `P1_Oil_00007`, not `Oil_00007`. Part 1 and Part 3 both contain `Oil/00007` and they are different scenes. Same collision you already caught once, returning at a larger scale.

### 1.3 Fix the VH extraction (S1, S6)
Move VH out of the scratch script. Inside `extract_regions()`, load **both bands once** and compute VH statistics from the **same region mask** used for VV. This kills the area-match join entirely — there is no matching step left to get wrong.

Verify on a scene you already have numbers for: `vh_mean_depth_db` and `vh_contrast_db` should reproduce your scratch values for regions that were correctly matched, and differ for any that were not.

### 1.4 Build the label CSVs
```bash
python pipeline/detect/make_labels.py --parts 1,2 --overlap-threshold 0.25 \
       --out data/labels/features_train.csv
python pipeline/detect/make_labels.py --parts 3 --overlap-threshold 0.25 \
       --out data/labels/features_test.csv
```
Runtime scales from your measured ~2 s/scene: expect roughly 60-70 minutes for Parts 1+2. Run it once, correctly.

### 1.5 Retrain the classical model on the new split
Update `train.py`'s FEATURES to the full ten. Train on `features_train.csv`, evaluate **only** on `features_test.csv`. Keep `class_weight='balanced'`; keep reporting precision/recall/F1 on the positive class, never accuracy.

**Checkpoint — post in the group:** old F1 on the old contaminated split, new F1 on the clean Part 3 holdout, and the positive count in each. Even a modest improvement is a rigour story; the clean holdout is the real win regardless of the number.

---

## PHASE 2 — The tile cache

*One artefact feeding both Layer 1 and Layer 2. Build it once, properly.*

### 2.1 Per-scene normalisation — the most important detail in this document

Do **not** feed raw dB to any network. You already understood why when you made your classical thresholds relative to the scene's own noise. Extend that:

```
For each scene, per band:
    valid = pixels that are not NaN, not exact-zero, not masked land
    med   = median(valid)
    mad   = median(|valid - med|)
    norm  = clip( (x - med) / (1.4826 * mad + eps), -6, +6 ) / 6.0   ->  [-1, +1]
```

Why MAD and not mean/std: MAD is robust to the slick itself and to bright ships, so a large slick cannot shift its own normalisation. The 1.4826 factor makes MAD comparable to a standard deviation for Gaussian data.

**This is what makes Zenodo's -29 dB and GEE's -20 dB the same problem.** Absolute level disappears; only *how dark relative to this scene's own sea* survives — exactly the signal that means "oil". Without this, everything you train works on Zenodo and dies on Ennore, and it dies silently.

Store `med` and `mad` per scene per band in the cache manifest. You need them to invert normalisation when computing real `contrast_db` for Layer 3.

### 2.2 Tiles for the U-Net
- **256x256, 2 channels (VV, VH)**, stride 256 for training (overlap at inference — 2.5)
- 2048/256 = 8x8 = **64 tiles per scene**; 1,885 scenes = ~120k tiles before filtering
- **Filter:** keep every tile whose mask contains >=1% oil pixels, plus an equal number of random negatives, plus all tiles from look-alike scenes (your hard negatives — take generously). Expect 20-40k tiles.
- Save as `float16` `.npy` shards or one memory-mapped array. **Do not decode TIFFs during training** — your 4050 will sit idle waiting on I/O and you will blame the model.
- Drop tiles more than 50% invalid (land/NaN).

### 2.3 Downsampled scenes for the classifier
Separate, tiny artefact: each full scene resized 2048 -> **256x256**, 2 channels, normalised as in 2.1, plus a scene-level label (oil = 1 for Part 1 scenes containing oil; 0 for all Part 2 look-alike and no-oil scenes). 1,885 items — fits in RAM.

### 2.4 Augmentation
Rotations (90/180/270), horizontal and vertical flips, mild contrast jitter, **applied after normalisation**. Standard, expected, unquestioned.

Do **not** synthesise SAR imagery. Generating fake radar means training a model to detect your own assumptions and then "validating" that it learned them. That is circular, and a remote-sensing person on the panel would find it in one question.

### 2.5 Inference tiling
At inference use **50% overlap** and average predictions in the overlap regions. Without this you get visible seams at tile boundaries, and a slick straddling a boundary splits into two detections — which produces two wrong polygons for Stage 2 to seed from.

---

## PHASE 3 — Layer 1: the scene classifier

*Cheap, fast, and it produces your headline number.*

### 3.1 Architecture
Follow the paper's reported optimum: **six convolutional layers, 32 filters, two hidden dense layers**, on 256x256x2 input, sigmoid output. Small enough to train on your 4050 in minutes.

### 3.2 Training
- Split Parts 1+2 train/val by **scene**, roughly 85/15
- Binary cross-entropy, or **Focal Loss** if class balance is skewed
- Early stopping on validation loss
- Expect minutes, not hours

### 3.3 Evaluate on Part 3 — never on anything else
Report on all 450 held-out scenes:
- **Overall scene accuracy** (the headline)
- **Recall on the 150 oil scenes** — how many spills we noticed at all
- **Look-alike rejection: of 150 look-alike scenes, how many correctly called no-oil**
- **Clean-ocean rejection: same for the 150 no-oil scenes**
- A confusion matrix. Look-alike-called-oil is your most interesting error and should be reported separately from clean-ocean-called-oil.

### 3.4 Threshold selection
Pick the operating point on a **PR curve computed on validation, not on Part 3.** Choosing a threshold by looking at test performance is test-set contamination through the back door — the same class of error as the row-level split you already correctly refused.

Prefer **recall over precision** here. A missed spill is invisible; a false positive gets rejected by Layer 2 or by a human. Say that out loud on stage — it is a design decision, not a compromise.

**Checkpoint:** post the confusion matrix and the four numbers.

---

## PHASE 4 — Layer 2: the U-Net

### 4.1 Architecture
Follow their best configuration: filters `16 -> 32 -> 64 -> 128 -> 256 -> 512 -> 1024`, **Focal Loss**, Upsampling2D in the expansion path. Input 256x256x2. If VRAM is tight on the 4050, cut the deepest block (stop at 512) before you cut the input size — spatial resolution matters more than depth for thin slicks.

Use **mixed precision** (float16 compute). Roughly doubles batch size on 6 GB and is close to free.

### 4.2 Training
- Train on tiles from **oil-containing scenes** plus hard negatives from look-alikes. Clean-ocean tiles teach little and there are a lot of them.
- Batch size 8-16 with mixed precision at 256x256x2
- **Focal Loss** — the paper's finding, and correct given oil is a small fraction of pixels even inside a positive tile. Standard cross-entropy converges to predicting all-background.
- Monitor validation **IoU on the oil class**, not accuracy. Accuracy is meaningless at this class balance.
- Expect a few hours on the 4050.

### 4.3 Evaluate on Part 3
- **IoU on the oil class**, positives only
- Also report IoU **including look-alike scenes** — this is the number showing whether Layer 1 earns its place. Run both ways: U-Net alone, and classifier-gated U-Net. The difference is a slide.
- Binarisation threshold: the paper needed 0.99 for probability-output models. Do not assume 0.5. Sweep it on validation.

### 4.4 Post-processing to polygons
Mask -> morphological close (you have this) -> connected components -> contours -> simplify (Douglas-Peucker, tolerance ~2 px) -> drop rings under ~40 vertices **only if also tiny in area**; a thin slick can be long and low-vertex.

**Then feed every region through Layer 3.** Features are computed from the *original dB array*, not the normalised one — invert using stored `med`/`mad`, or keep the raw array in memory alongside.

---

## PHASE 5 — Two new outputs the rest of the team needs

*Independent of Phases 3-4. Do these whenever a download is running.*

### 5.1 Ship detections — feeds our single best feature
Ships are **bright** on SAR, so this is the inverse of your detector: threshold *above* `med + k*MAD`, small compact regions, high peak. You already have the bright-outlier masking logic in `prepare()` — reuse the detection half instead of discarding those pixels.

Emit per Master section 4.4:
```json
"ship_detections": [
  {"lon": -118.10412, "lat": 33.60219, "px_area": 340, "peak_db": -4.2}
]
```
An empty array is valid and common.

**Why this matters:** Jaiveer cross-references each radar ship against AIS. **A ship radar can see but AIS cannot is a dark vessel** — and next to a fresh slick that is the strongest single piece of evidence the whole system can produce, because it is independent of the drift model and does not inherit its uncertainty. It is also exactly what NTRO cares about. **This is the highest-value 200 lines you will write.**

Practical notes: use a high threshold and accept missing small vessels; a false ship detection produces a false dark-vessel claim, which is worse than a miss. Merge detections within ~50 m — a large vessel produces multiple bright pixels.

### 5.2 Chronic vs acute
Add `discharge_class` per detection: `chronic | acute | unknown`.

- **chronic** — long, thin, roughly straight, often lane-aligned. A vessel washing tanks or dumping bilge **while underway**. The origin is a *line segment*, not a point.
- **acute** — radial spread from a point. Collision, grounding, platform release.

Rule: `chronic` when `elongation > 5` AND the principal axis is coherent along the region (low curvature); `acute` when `elongation < 3`; `unknown` between. Tune against Part 1's masks — you now have 1,200 real slicks, enough to check whether the split is meaningful.

**Why it matters:** it changes how Anushka seeds particles and how Jaiveer searches AIS. It also carries the strongest line in the pitch — *deliberate discharge is a crime, an accident is a misfortune, and the system that tells them apart is the one worth deploying.*

### 5.3 Stub both immediately
Emit both fields with garbage values in the right shape and run the validator, **before** the real logic exists.

> WAIT / FLAG: **Tell Jaiveer and Anushka the moment 5.3 lands.** Both are blocked on the *shape* of these fields, not their values. Jaiveer's dark-vessel module cannot start without `ship_detections` existing.

---

## PHASE 6 — Real-scene inference

> WAIT for Akshat, per case: `sar_vv_vh.tif` (2-band float32 dB) plus `bounds.json`. He delivers case by case; start each as it lands rather than waiting for all seven.

### 6.1 Complete `run.py`
```
load 2-band GeoTIFF -> per-scene normalise (2.1)
  -> Layer 1 classifier on downsampled scene
      -> if NO:  write detections.geojson with zero oil features. DONE. This is correct.
      -> if YES: Layer 2 U-Net, tiled with 50% overlap, averaged
  -> mask -> contours -> Layer 3 features (from raw dB)
  -> pixel -> lon/lat
  -> detections.geojson
```

### 6.2 Coordinate conversion (TRAPS #1 and #8)
```python
lon = west  + (col / width_px)  * (east  - west)
lat = north - (row / height_px) * (north - south)   # latitude DECREASES with row
```
GeoJSON is `[lon, lat]` — **longitude first**, always. Pixel (0,0) is top-left = (west, north).

OpenCV contours give `contour[:,0] = x = col` and `contour[:,1] = y = row`, while NumPy indexes `[row, col]`. You already handle this in `features.py`; carry the same discipline here.

### 6.3 Contract compliance
Exact property names, case-sensitive, per Master section 4:
`id, classification, confidence, area_km2, elongation, edge_gradient, contrast_db, shape_class, centroid` plus `ship_detections` and `discharge_class`.

- `classification` in {"oil","lookalike"} — not "none", not "oil_spill"
- `shape_class` in {"linear","blob"} — not "elongated"
- `confidence` in [0,1] from `predict_proba`
- `contrast_db` **negative** for a dark spot
- `elongation` **>= 1.0** always
- `centroid` is `[lon, lat]`

### 6.4 The threshold question, and the -3 dB trap
Your own report caught this: the documented fallback `contrast < -3 dB AND elongation > 2.5` would match **zero** of your training positives, because Zenodo positives run -0.44 to -1.04 dB. **Do not hardcode it.**

Instead: run the detector on each real scene, look at the distribution of `contrast_db` it actually reports, and set a **transparent, stated** rule per scene family. Because the CNN operates on normalised input it should be less sensitive to this than the classical path — but check, do not assume.

### 6.5 Per-case verification, before handover
For every case, do all four:
1. Plot `detections.geojson` over `sar.png` — polygons must sit on dark features
2. Check coordinates are in the right hemisphere. **The library straddles both**: Menuett −79.6, Panagia −123.9, Huntington −118.1, Alaska −142.7, Mumbai +72.2, Jamnagar +71.9. A sign error that survives four Atlantic cases surfaces the moment you cross into the Indian Ocean
3. Read the Layer 1 confidence — if the classifier says 0.51, say so rather than presenting certainty
4. `python scripts/validate_case.py cases/<id>` -> PASS

### 6.6 Two cases that need specific attention

**Alaska is the hardest detection in the library.** 2 km long, 0.3 km² — an order of magnitude smaller than the others, at 59.6 N where incidence-angle effects and sea state differ from the mid-latitude cases. If your classifier gates it out, that is a real result and you report it. But **do not lower the threshold to force it through** — you would be tuning against an answer you are not supposed to know.

**The ship detector matters more on Alaska than anywhere else.** Cerulean places a dark vessel at 59.546 N −142.639 W, roughly 4.5 km from the slick, estimated 40 m ± 20%. **Your bright-point detector finding that contact independently is the entire case.** A 40 m vessel is at the small end of what SAR resolves reliably — if you find it, say so with the measured peak dB; if you do not, say that too, because a missed contact is honest and a fabricated one is not.

**Mumbai carries three source types at once** — infrastructure, a dark vessel, and a natural-seep flag. Your `discharge_class` and `ship_detections` both feed the source classification that sorts them out. Expect a messier scene than the open-ocean cases.

### 6.7 Cases 7 and 8 — the rejection pair
**Case 7 is already chosen**: the Ennore scene of **2023-11-30 00:32 UTC**, from the Arabian Sea sweep. It is four days *before* the December 2023 CPCL spill, so its dark patches provably cannot be oil. That is a better look-alike than anything in Zenodo because it is the same coast and sensor as a real incident.

**Case 8 is yours to nominate**: one clean-ocean scene from Zenodo Part 3.

Run your pipeline on both — **the correct output is zero oil features.** That fifteen seconds on stage, where the system loads a scene and correctly reports nothing, answers three hostile questions at once.

---

## PHASE 7 — The numbers

### 7.1 Final table on the Part 3 holdout, scene-level split

| Model | Scene acc | Look-alike rejection | Oil IoU | Notes |
|---|---|---|---|---|
| Classical (depth-map + RF) | — | | — | your baseline |
| Classifier only | | | — | |
| U-Net only (no gate) | — | | | shows what the gate buys |
| **Classifier + U-Net** | | | | the shipped system |

### 7.2 The ablation paragraph
"Our classical baseline achieves X. Adding a scene classifier lifts look-alike rejection from A to B. Adding U-Net segmentation lifts IoU from C to D. The classical layer is retained because it produces the per-detection feature explanation that neither network can."

### 7.3 The VH slide
Feature importances, the F1 jump, and the physics: clutter damps VV, oil damps both. This is your novelty claim.

### 7.4 The honesty paragraph
The two-benchmark framing from B2, stated before anyone asks.

---

# PART D — RISKS

## D1. Domain gap — the one most likely to hurt you *(HIGH, silent)*
Zenodo scenes sit at ~-29 dB; GEE scenes at ~-20 dB. A model trained on absolute values fails on the other domain **without erroring** — it returns confident nonsense.

**Primary mitigation:** per-scene MAD normalisation (2.1), applied identically at train and inference. Non-negotiable.
**Secondary:** run inference on a couple of GEE-domain scenes early and compare input statistics against your training distribution. If the normalised histograms look wildly different, you know before demo day.
**Tertiary:** keep the classical detector live as a fallback. A scene that confuses the CNN still produces something.

## D2. The U-Net hallucinates on look-alikes *(MEDIUM, loud if you test for it)*
The paper reports exactly this. Layer 1 is the mitigation; 4.3's gated-vs-ungated comparison is how you prove it works. If look-alike scenes still leak through, raise the classifier threshold — better to miss a marginal spill than fabricate one on a demo case whose whole purpose is to be rejected.

## D2b. Alaska's slick is too small to detect *(MEDIUM, and it is a legitimate outcome)*
0.3 km² at 59.6 N. If Layer 1 gates it out or Layer 2 finds nothing, **report that** — and note that the ship detection may still succeed, which would make it a dark-vessel case with no confirmed slick of our own. Resist the urge to tune it in; you do not know the answer and tuning against a suspicion is the same error as tuning against a known one.

## D3. A case turns out VV-only *(LOW-MEDIUM)*
Then `vh_contrast_db` and `vh_mean_depth_db` are unavailable for that case. Have a VV-only variant of both the classifier and the RF trained and ready — same pipeline, one channel — and **note the degradation honestly per case** on the results slide. Do not silently zero-fill the VH features; a zero is a value and the model will treat it as one.

## D4. Class imbalance defeats training *(MEDIUM, loud)*
Oil is a tiny fraction of pixels. Focal Loss plus oil-tile-biased sampling is the answer. If validation IoU sits at zero for several epochs, the model collapsed to all-background — lower the loss alpha or raise the positive tile fraction. Do not just train longer.

## D5. Tile-boundary artefacts *(MEDIUM, silent)*
A slick straddling a tile edge splits into two detections, producing two wrong polygons for Anushka to seed from. 50% overlap with averaged predictions (2.5) fixes it. Verify by looking for suspiciously straight edges at multiples of 128 px.

## D6. Disk and download *(MEDIUM, loud)*
~150 GB across both parts. Check first, escalate to Akshat early if it is a wall.

## D7. Training time collapses the schedule *(MEDIUM)*
If the U-Net is not converging usefully, **the classifier alone plus your classical detector is a complete, shippable system.** Classifier gives the headline number and the reject cases; classical gives the polygons and the features. Say so on stage as a roadmap item rather than shipping a broken segmenter.

---

# PART E — REFERENCE

## E1. Commands
```bash
# labels
python pipeline/detect/make_labels.py --parts 1,2 --overlap-threshold 0.25 --out data/labels/features_train.csv
python pipeline/detect/make_labels.py --parts 3   --overlap-threshold 0.25 --out data/labels/features_test.csv

# cache
python pipeline/detect/build_cache.py --parts 1,2 --tiles --scenes

# train
python pipeline/detect/train_classifier.py
python pipeline/detect/train_unet.py
python pipeline/detect/train.py            # classical baseline, updated FEATURES

# evaluate - Part 3 only, always
python pipeline/detect/evaluate.py --test data/labels/features_test.csv --report

# inference — the hero case; seven real scenes are on disk, `ls cases/` for the list
python pipeline/detect/run.py --case case-jacksonville-2024
python pipeline/export/build_case.py --case case-jacksonville-2024 --stage detect
python scripts/validate_case.py cases/case-jacksonville-2024
python scripts/sync_web_cases.py     # so the browser sees it
```

> **Do not skip the `build_case.py` line.** The case folder is the hand-off medium: if your stage
> writes to `out/` and you validate `cases/<id>/`, you are validating somebody else's file and the
> PASS means nothing. That has already happened once on this project (TRAPS #21).

## E2. Environment
`numpy scipy opencv-python scikit-image scikit-learn rasterio shapely matplotlib` plus PyTorch or TensorFlow with CUDA for Phases 3-4. **No new dependencies get added to `requirements.txt` after the freeze** — pin the DL framework now if you are adding one.

## E3. Escalate to Akshat (45-minute rule)
Disk full, corrupt archive, a case delivered as PNG-only or VV-only, a real scene whose normalised statistics look nothing like the training distribution, or anything where you are about to change a contract field.

## E4. Log after every phase
`docs/updates/soum.md`, newest first, per `docs/updates/TEMPLATE.md`. What was done, files touched, the exact run command, open issues. Post checkpoint artefacts in the group as they happen — three of your teammates finished major work the team could not see because the images never got posted.

## E5. Definition of done
- [ ] Parts 1+2 downloaded, extracted, labelled; **Part 3 held out and never trained on**
- [ ] VH extracted inside `extract_regions()`; area-match join gone
- [ ] Tile cache with per-scene MAD normalisation
- [ ] Scene classifier trained; confusion matrix and four numbers posted
- [ ] U-Net trained; IoU on Part 3, gated and ungated
- [ ] Classical baseline retrained on the clean split — the ablation row
- [ ] `ship_detections` and `discharge_class` shipping, stubbed early for Jaiveer and Anushka
- [ ] Valid `detections.geojson` for all eight cases, each plotted and eyeballed
- [ ] Alaska's 40 m radar contact searched for, and the result reported either way
- [ ] Case 8 nominated; cases 7 and 8 verified to produce zero oil features
- [ ] IoU against Cerulean polygons computed **after** your own detections were committed
- [ ] Numbers table and the VH slide ready for the deck
