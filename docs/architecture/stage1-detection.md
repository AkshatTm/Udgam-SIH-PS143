# Stage 1 — Detection

**Question:** is there oil in this radar scene, exactly which pixels, and why do we say so?

**In:** `sar_vv_vh.tif` (2-band float32 dB, VV and VH), `bounds.json`, `meta.json`
**Out:** `detections.geojson`
**Code:** `pipeline/detect/` · **Brief:** [`../team/soumirya-stage1-detection.md`](../team/soumirya-stage1-detection.md)

```bash
python pipeline/detect/run.py --case <case-id>
```

---

## Why this is hard

Oil damps capillary waves, so a slick returns less radar energy and appears as a **dark patch**.
So does a great deal else: low wind, algal blooms, rain cells, wind shadows behind land, internal
waves. These are *look-alikes*, and separating them from oil is the actual problem — finding dark
patches is easy.

Two of the nine cases in the library exist purely to test the negative: a look-alike scene and a
clean-ocean scene, where **the correct output is nothing**.

---

## Three layers, each answering a different question

```
Layer 1   scene classifier (small CNN)      "is there oil here at all?"
              │  gate
              ▼
Layer 2   U-Net segmentation                "exactly which pixels?"
              │  contours
              ▼
Layer 3   classical hand-crafted features   "why, and what shape?"
```

### Layer 1 — the gate

A small CNN over downsampled whole scenes. It is cheap to train and it exists for one structural
reason: **the dataset's own authors found that the U-Net segments erroneously on look-alike
images.** Run the U-Net unconditionally and the look-alike and clean-ocean cases come back with
hallucinated oil — precisely the two cases that exist to prove the system can say no.

So the classifier gates the U-Net (decision D2). On a `benchmark`-provenance scene the confidence
reported downstream is a **model probability**; on a satellite export it is a rule margin, and
`meta.json` records which, because the two are not the same quantity.

### Layer 2 — the polygon

U-Net segmentation produces the mask, and the mask produces the polygon that Stage 2 consumes.
This is where segmentation IoU is measured.

### Layer 3 — the reasoning

The classical feature layer (`pipeline/detect/features.py`) runs on U-Net contours instead of
threshold blobs. Every feature survives the move.

It is kept for three concrete jobs, not sentiment (decision D3):

1. **The explainability bars.** A judge trusts an answer they can interrogate. A CNN gives a mask
   and no reasoning; the geometric features give *why* — elongation, contrast, edge gradient,
   shape regularity.
2. **The ablation baseline.** The classical path is what the learned path is measured against.
3. **The ship detector.** Bright point targets in the same scene become radar contacts, which is
   what makes dark-vessel attribution possible in Stage 3.

---

## The diagnosis that shaped the detector

The first detector used annulus CFAR — a standard adaptive-threshold method that estimates
background statistics from a ring around each candidate, with a guard band so a compact target
does not contaminate its own background.

It failed, and the reason generalises: **an oil slick is not a compact blob, it is a line.** A
linear slick runs straight through the guard ring. That drags the local mean down and inflates the
local standard deviation, pushing the threshold *away* from the slick exactly where the slick is.
A −4 dB streak on a −1 dB sea becomes invisible.

This was proven synthetically in `pipeline/detect/test_synthetic.py` before the approach was
abandoned — a diagnosis rather than two days of parameter tuning, and worth recording as the
reason the architecture looks the way it does.

---

## Training and evaluation

Training data is the Zenodo oil-spill dataset (DOI
[10.5281/zenodo.13761290](https://doi.org/10.5281/zenodo.13761290), CC-BY, Trujillo-Acatitla et
al., *Mar Pollut Bull* 204:116549, 2024): 2048×2048×2 float32 dB GeoTIFFs with binary masks, in
three classes — oil, look-alike, no-oil.

**Train on Parts I+II, test on Part III** (decision D1). Part III is the authors' designated test
set; training on it would mean no clean generalisation estimate.

**The split is by source scene, never by row.** Regions cut from one 2048×2048 scene are
correlated, and a row-level split inflates the number that goes in front of judges. This is not a
technicality — it is the difference between a defensible figure and a flattering one.

### Reporting rules

Four numbers, always named with their metric and their split, never a single unqualified
percentage:

| Metric | What it answers |
|---|---|
| Scene classification accuracy | Does this scene contain oil? |
| Look-alike rejection rate | Of the look-alike scenes, how many were correctly called no-oil? |
| Segmentation IoU (oil class, positives only) | Pixel overlap with ground truth |
| Classical baseline F1 | The ablation — the classical pipeline on the same holdout |

**The benchmark-gap framing.** The dataset's authors report 99% classification accuracy and 96%
IoU on their own test set. The widely-quoted ~53% IoU state of the art is from the **Krestenitis**
5-class benchmark — a *different*, non-open dataset. Quoting our number against theirs would be a
category error. The honest statement is that the gap between 96% and 53% measures **how much
look-alike variety a dataset contains**, not model quality.

Current measured values live in
[`../evaluation/stage1-accuracy-programme.md`](../evaluation/stage1-accuracy-programme.md) and
[`../evaluation/deck-numbers.md`](../evaluation/deck-numbers.md); raw evidence is in
`pipeline/detect/results/`.

### Comparison against Cerulean is not ground truth

Five bundles carry `cerulean_slick.geojson`, SkyTruth's polygon for the same feature. IoU against
it (`pipeline/detect/results/iou_cerulean.json`) is **agreement between two algorithms**. SkyTruth
themselves state that SAR alone cannot definitively identify oil slicks and that their detections
are *potential* slicks; that caveat is repeated rather than quietly dropped.

The polygon is fetched with `scripts/fetch_cerulean.py`, which deliberately splits the response so
the polygon can be committed without the attribution that arrives alongside it.

---

## Output

`detections.geojson` — a FeatureCollection whose features carry classification, confidence and the
geometric feature values behind the explainability bars. Radar ship contacts travel in the same
file. Exact schema: [`../00_MASTER_PLAN.md`](../00_MASTER_PLAN.md) §6.3.

A no-spill case correctly produces **zero features classified `oil` and zero radar contacts**. The
validator warns rather than errors on that, because it is right for a no-spill case and wrong for
any case with `trace` in `acts_available`.

---

## Traps specific to this stage

- Pixel (0, 0) is top-left = (west, north). Getting this wrong flips every polygon vertically and
  the result still looks like a plausible slick.
- **Band order is NOT the same in both corpora, and assuming it is has already cost us a full
  train-and-evaluate cycle.** Measured over 297 Part III scenes: Zenodo's band 1 runs **8.15 dB
  darker** than band 2 and is darker in **290 of 297** — i.e. Zenodo is **band 1 = VH (cross-pol),
  band 2 = VV (co-pol)**, because over ocean cross-pol sits 6–10 dB below co-pol by physics. The
  GEE exports are the other way round: **band 1 = VV**. Decide from the pixels, never from the
  filename (`nets._looks_like_zenodo`). Getting this wrong does not error — it returns confident
  nonsense.
- **"VH is the strongest feature" is dead as stated.** The feature that carried the ablation was
  computed from band 2, which on Zenodo is **VV**. The channel *names* were swapped, not the
  result: adding the second polarisation is still real and still worth a slide (val F1
  0.346 → 0.643, Part III precision 0.049 → 0.286 at identical recall). Quote the ablation, not a
  polarisation, until a retrain fixes the naming.
- The signal is ~1 dB deep, which is why exports are 2-band float32 GeoTIFF rather than 8-bit PNG
  (decision D14) — quantisation destroys it.
- Contrast for a dark spot is never positive. An elongation ratio is never below 1.

Full list: [`../TRAPS.md`](../TRAPS.md).
