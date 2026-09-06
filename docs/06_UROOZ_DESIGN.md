# UROOZ — Design: Visual Language, Quiz Chips, Deck
*Read with 00_MASTER_PLAN.md. You own how this project LOOKS — the difference between "college assignment" and "national-round submission." You work ~2 h/day, mostly alongside Harshita. Most of your tasks are human-judgement work: ChatGPT is your advisor and reference-finder, not your executor. Antigravity only where marked.*

## You produce
Design tokens (colours/typography) as a short spec Harshita implements · 4 Act-1 quiz chips · styled cards and panels (paired with Harshita) · the pitch deck design · a demo smoke-check list.

## You consume
Harshita's running app · 4 chip crops from Soum (by the event; before that, practice on any Zenodo screenshots) · Akshat's deck narrative.

---

## Task 1 — Sun (~2 h) · the colour language  [YOU decide, GPT advises]
The map is mostly a dark grey SAR image — everything must read against that, projected, from the back of a room. Deliver `docs/design_tokens.md`:
- Oil detection: red/orange family outline+fill · Look-alike: neutral grey, dashed · Particles: a warm bright single colour · Origin heatmap: one dark→bright ramp (colour-blind-safe; ask GPT for a viridis-like ramp that isn't literally default-viridis) · Vessel tracks: cool blue; top suspect highlighted; **excluded vessel: visually "ruled out"** (muted + strikethrough motif) · Panel background, text hierarchy, one accent.
- Rule of restraint: at most 3 expressive colours on the map at once; everything else neutral.
- Font pairing (one display, one UI — free/Google fonts only) + sizes for projection (body ≥14 px on the app, ≥20 pt on slides).
Sanity test: view Harshita's screenshot at 30% zoom — can you still tell oil from look-alike instantly?

## Task 2 — Mon (~2 h) · the four quiz chips  [YOU pick, Antigravity/GPT helps crop]
From Zenodo Part III (ask Soum for a browsing folder of ~20 candidate scenes): pick **1 real oil + 3 convincing look-alikes** (ideally different types — calm-wind patch, algae/biogenic film, rain cell). The test of a good pick: YOU can't instantly tell which is oil. Export 4 × 512×512 PNGs, identical grey-stretch, no labels on the image. Name them `chip_a/b/c/d.png` + `chips_answer.md` (which is oil, and the one-line "why" for the reveal — elongation, edge sharpness). Deliver to Harshita's `web/public/chips/`.

## Task 3 — Tue (~2 h) · cards and panels  [YOU + Harshita pairing]
Live session with Harshita: object card (classification badge, feature bars readable at a glance), origin card, layer-toggle chips, stage rail states (active / available / greyed-unavailable with tooltip). Padding, alignment, hierarchy. You point, she (and Antigravity) implements. Priority order if time runs out: object card → stage rail → everything else.

## Task 4 — Wed (~1 h) · pre-HOD visual pass
Run through the app once as a stranger: anything unreadable, misaligned, or confusing at projector distance. 30-minute fix list to Harshita, ruthless triage — only things a judge would notice.

## Task 5 — Event days (~4 h) · the deck  [YOU design, GPT drafts structure, Akshat owns words]
~10 slides on the narrative Akshat gives you. Design rules: one idea per slide · screenshots of the REAL app, not mockups · the honesty slide (real numbers) styled as confidently as the wins — it's a feature · the India line ("INCOIS tells the Coast Guard where the oil is going. Nobody tells them where it came from. We built the other half.") gets its own slide · cite the Zenodo dataset (DOI 10.5281/zenodo.13761290, CC-BY) and GEE/NOAA sources on a data-provenance slide — Akshat's receipts.md has the exact strings.

## Task 6 — before freeze (~30 min) · smoke-check list  [YOU write, anyone runs]
A one-page paper checklist of every click in the demo path (load case → toggle layers → click detection → scrub → stage 3 → switch case → no-spill case). Someone runs it on the demo machine after freeze. If you have time and want to, a Selenium script that clicks through it is a bonus — the paper list is the requirement, the script is optional.

## Escalate
Anything where design needs a data change (e.g. "the heatmap ramp needs more contrast in the data itself") → Akshat, not a workaround.

## Definition of done
design_tokens.md delivered Sun · 4 chips + answer file delivered · cards styled by Wed morning · deck done before freeze · smoke-check list exists and was run once on the demo machine.
