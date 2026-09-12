# Cases 6, 7, 8 — Soum's nominations for Akshat

*Master §14 open item "Nominate cases 6 and 7 from Zenodo Part 3 — Owner: Soum". Closed here.*

These are Zenodo Part III scenes. They are **benchmark-provenance**, so `run.py --path auto`
routes them to Layer 1 + Layer 2 — which is where the networks are strongest (look-alike
rejection 0.940, clean-ocean rejection 0.987 on the Part III holdout, 150 scenes each).

> **Corrected 13 Sept.** This line read **0.960** for look-alike rejection. That was the
> pre-domain-augmentation classifier. The shipped model is **0.940**: the augmentation traded
> rejection 0.960 → 0.940 for oil recall 0.893 → 0.927 and scene accuracy 0.947 → 0.951. Net
> positive, but a trade — and quoting the old rejection beside the new accuracy would overstate
> both. Use 0.940.

## How they were chosen — and why that matters

Selected on **detector evidence only**: the scenes whose darkest / largest / most elongated dark
feature is the most oil-like, ranked from `features_test.csv`. The classifier's opinion was
**not** used to pick them. That ordering matters — choosing reject cases the model already
rejects confidently would be staging a win. These were picked as the *hardest* available, and
what the model then says about them is a result.

| # | Scene | File | Why it is hard | Layer 1 P(oil) | Verdict |
|---|---|---|---|---|---|
| 6 | `P3_Lookalike_00134` | `data/test/Images/Lookalike/00134.tif` | deepest region **−9.05 dB**, **47.4 km²**, **elongation 21.2** — reads exactly like a chronic vessel discharge | **0.0008** | correctly rejected |
| 7 | ~~`P3_No oil_00091`~~ **WITHDRAWN — see below** | ~~`data/test/Images/No oil/00091.tif`~~ | ~~clean ocean that still yields an −9.78 dB dark feature and 85 candidate regions~~ | 0.0022 | **not ocean — replaced by 00027** |
| 8 | `P3_No oil_00027` | `data/test/Images/No oil/00027.tif` | the most statistically typical clean-ocean scene; carries strong swell banding | **0.0004** | correctly rejected |

Threshold is 0.434. All three are rejected by 2–3 orders of magnitude, not marginally.

> ### ⚠ CORRECTION, 13 Sept — nomination 7 was wrong and I did not look at the picture
>
> **`P3_No oil_00091` is not clean ocean. It is farmland.** Field parcels, roads, a settlement and
> the Orontes river, in the Ghab plain at 35.14–35.32 N — roughly 150 km inland from the "Gulf of
> İskenderun" the bundle's `meta.json` had named. Its −9.78 dB "dark feature" and 85 "candidate
> regions" are field boundaries, and the ship detector's **31 "radar contacts" are buildings and
> vehicles.** Akshat's blurb asked whether the system can tell traffic from a spill; that would have
> put land clutter in front of a judge as marine traffic, on a scene anyone could check on a map.
>
> **Root cause, and it is mine:** I selected this scene on *statistics alone* — it was the deepest,
> busiest no-oil scene, therefore "hardest" — and never opened the image. Every automated gate
> passed it: the classifier correctly returns P(oil) = 0.0022, the validator returns PASS, the JSON
> is strict-clean. Only 6.5's "plot it and eyeball it" catches this, which is exactly why that gate
> is in the definition of done and not optional.
>
> **Replaced by `P3_No oil_00027`** — already the vetted runner-up below. Verified as ocean rather
> than assumed: median **−26.9 dB**, MAD **0.47**, 1st–99th percentile spread **3.6 dB**, **zero**
> pixels above −5 dB, ship detector returns **zero** contacts, and the plot shows open water with
> strong wind/swell banding and no structures. Box W 35.1126 S 34.6950 E 35.2966 N 34.8790, eastern
> Mediterranean. Rebuilt, re-run and re-validated: **0 oil, 0 contacts, P(oil) 0.001, PASS.**
>
> Of the 150 Part III no-oil scenes, **65 are unambiguously open water** on those criteria. There
> was never a shortage; I just picked on the wrong axis.

**Runners-up**, if any of the above is unsuitable for display:
`P3_Lookalike_00142` (56.99 km², elongation 14.0, P=0.0019) · `P3_Lookalike_00002`
(−11.95 dB, P=0.0032) · `P3_No oil_00019` (−9.47 dB, P=0.0019).

## What Akshat needs to build

Standard bundle per Master §4.2: `meta.json` (`case_type: lookalike` for 6, `nospill` for 7/8;
`acts_available: ["detect"]`), `bounds.json`, `sar.png`, `thumb.png`, and the scene itself as
`sar_vv_vh.tif`.

**One thing to preserve:** these Zenodo GeoTIFFs carry **no CRS**, and `run.py`'s
`scene_provenance()` uses exactly that to route them to the networks rather than to the
classical path. If the export adds a CRS to make `bounds.json` meaningful, the routing flips and
these scenes go down the classical path instead. Either keep them ungeoreferenced, or tell me
and I will switch the routing to an explicit `meta.json` field — cleaner anyway, and it should
probably become one before the freeze.

## The line this pays for on stage

> "This is a 47 square-kilometre dark streak, nine decibels below the surrounding sea, twenty-one
> times longer than it is wide. It looks like a ship washing its tanks. The system says it is not
> oil — and it says so at a confidence of 0.0008."

That fifteen seconds answers three hostile questions at once, which is why cases 6–8 exist.
