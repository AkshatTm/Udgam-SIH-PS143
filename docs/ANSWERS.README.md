# `docs/ANSWERS.md` exists. Akshat holds it. You will not see it until 15 September.

This stub is committed on purpose. The file it describes is not.

## What it is

Every case in the library has a documented outcome — a SkyTruth Cerulean attribution, an NTSB
finding, a dark-vessel id. All of it is written down, in one file, on one laptop, gitignored.

## Why you are not getting it

Not because anyone distrusts you. Because of what knowing does to tuning.

If Jaiveer knows which vessel the answer names while he is weighting components, he will tune until
that vessel ranks first. If Soumirya knows where the slick is, he will lower the threshold until it
appears. If Anushka knows the origin, she will read a wrong cloud as close enough. **None of that is
dishonesty** — it is what anyone does when the target is visible. But it collapses *"our system
identified the vessel"* into *"we tuned it until it did"*, and an NTRO panel in December will ask
which one happened. We need to be able to answer.

## What this explains

**Akshat will not tell you whether your output is right.** Not a hint, not a nudge, not a raised
eyebrow at a number that looks off. That is not him being unhelpful — it is the one thing that makes
the Verify screen a genuine reveal instead of a restatement. He opens the file the moment your
bundle validates, and not before.

## What you do get

| You | Get | Do not get |
|---|---|---|
| **Soumirya** | `sar_vv_vh.tif`, `sar.png`, `bounds.json`, `ais_source`. `cerulean_slick.geojson` **after** your detector has produced its own polygon — then the IoU comparison is a measurement | Where the slick is, before you find it |
| **Anushka** | Case list with `detection_time` and bounds; Soumirya's detections when they land | The documented origin or release time |
| **Jaiveer** | Case list with dates, boxes and `ais_source`; real `origin.json` when it lands | Vessel names, MMSIs, IMOs. Your search box at `2 × radius_90_km` contains the culprit and plenty of decoys anyway |
| **Harshita** | Bundles as they are produced | The answers |

## Two things this changes about how you work

**Cases are named after places, never vessels.** `case-jacksonville-2024`, not the ship's name. If a
case id ever looks like it is naming a vessel, that is a bug — say so, do not "fix" it by renaming
back.

**If you find attribution data yourself, do not post it in the group.** Cerulean's public API returns
the polygon and the attributed MMSIs in the same response, so it is easy to trip over the answer by
accident. `scripts/fetch_cerulean.py` splits them for you — the polygon goes in the bundle, the
attribution only prints with `--answers`. If you see that block, close it and tell Akshat.

## When it opens

15 September, on the Verify screen, in front of the judges — **including the cases we got wrong.**
A `MISS` ships as readily as a `HIT`, with an explanation of why. That is the whole point of having
sealed it.

*Reasoning in full: `docs/00_MASTER_PLAN.md` Part 16 and decision D21.*
