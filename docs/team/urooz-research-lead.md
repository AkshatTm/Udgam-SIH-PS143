# UROOZ — Research Lead
## Master document: how you work, and the standing context prompt

*Read this once, fully. Then work from it every time. Every research task is: this document's context prompt + one task document pasted after it.*

---

# PART A — YOUR ROLE

You are the team's research lead. You do not write code. You find out **what is already known**, so the five people building do not waste days rediscovering it or, worse, build something on an assumption that was never true.

Two of your three tasks are potentially the most valuable work anyone on this team does this week, because they could turn a hackathon entry into something with a life after the hackathon.

## Why this matters concretely
We have already been saved twice by knowing the literature. We were about to benchmark our detector against the wrong dataset's numbers until we found the actual paper for the dataset we use. And we found that the closest existing system to ours publishes its full methodology — which handed us three scoring metrics we would otherwise have invented badly. **That is what good research does here: it stops us being wrong in public.**

---

# PART B — YOUR TOOLS AND THE WORKFLOW

You have three AI tools and they do different jobs. **Use all three, in this order, every time.**

| Tool | Job |
|---|---|
| **Gemini Deep Research** | Runs a long autonomous investigation across many sources. Strong at breadth, follows citation trails, produces long reports. |
| **Perplexity Pro (Research mode)** | Second independent investigation. Different source ranking, different retrieval, often surfaces things Gemini misses. |
| **ChatGPT** | The synthesiser. It does not research — it takes the two reports and turns them into one structured document in our format. |

## The workflow, every single time

**Step 1 — Build the prompt.** Copy the standing context prompt (Part C below). Paste the task document's brief immediately after it. That is one long prompt.

**Step 2 — Run it in Gemini Deep Research.** Let it finish completely. Save the whole output to a file — `research/raw/<task>_gemini.md`.

**Step 3 — Run the exact same prompt in Perplexity Pro Research.** Do not tweak it between tools; you want two independent answers to the *same* question, because that is what lets you see disagreement. Save to `research/raw/<task>_perplexity.md`.

**Step 4 — Synthesise in ChatGPT.** Paste both raw reports plus the synthesis prompt (Part E). Get one structured document.

**Step 5 — Verify.** Part F. This step is not optional.

**Step 6 — Deliver.** Save to `docs/research/<task>.md` and post the summary in the group.

## Why two research tools and not one
Where both tools independently reach the same conclusion, that conclusion is probably solid. **Where they disagree, that disagreement is itself a finding** and must survive into the final document — do not let ChatGPT smooth it away. A contested question is something we need to know is contested before we assert it on stage.

---

# PART C — THE STANDING CONTEXT PROMPT

**Paste this at the top of every research prompt, exactly as written. Then paste the task brief after it.**

---
```
=== CONTEXT: READ FULLY BEFORE RESEARCHING ===

You are supporting a technical research team building a satellite-based oil spill
forensics system. This context explains what we are building and what we already
know, so that your research adds to it rather than repeating it.

--- THE PROBLEM ---

When oil is spilled at sea, the ship responsible usually sails away. Satellites
photograph the ocean, but radar satellites revisit any given patch of sea only
every few days. So by the time a spill is visible in imagery, it has been
drifting for hours or days and the vessel that caused it is long gone.

Europe has systems that fuse satellite spill detection with ship transponder data.
India has forward drift prediction (INCOIS runs an operational advisory to the
Indian Coast Guard) but has no capability to work backwards and identify a source.
That gap is what we are building for.

This is an entry to India's Smart India Hackathon 2026, problem statement 26143,
sponsored by the National Technical Research Organisation (NTRO), India's technical
intelligence agency. Their underlying interest is maritime domain awareness — the
ability to identify vessels behaving anomalously, including vessels that switch off
their transponders. Oil spill attribution is one application of that capability.

--- WHAT WE HAVE BUILT ---

A four-stage pipeline. All data sources are free and public.

STAGE 1 — DETECTION
Input: Sentinel-1 synthetic aperture radar (SAR) imagery, both VV and VH
polarisations, obtained via Google Earth Engine.
Oil damps capillary waves on the sea surface, so slicks appear dark on radar.
The core difficulty is "look-alikes" — calm-wind zones, algae blooms, rain cells
and biogenic films all appear dark in exactly the same way.
We use a scene-level CNN classifier (is there oil in this scene at all?) followed
by a U-Net segmentation model, followed by classical hand-crafted geometric
features (area, elongation, edge sharpness, contrast in decibels) that provide
explainability the networks cannot.
A finding of ours: the VH polarisation is the single most discriminative feature.
Ocean clutter damps mainly VV; genuine mineral oil damps both polarisations
through Marangoni effects. Dark in VV but normal in VH suggests a look-alike;
dark in both suggests oil.

STAGE 2 — BACKWARD DRIFT
Input: the slick polygon, the image timestamp, HYCOM ocean surface currents
(0.08 degree, roughly 9 km, one snapshot per day) and ERA5 winds (hourly),
both via Google Earth Engine.
We built a reduced-order surface advection model: drift velocity = surface
current + approximately 3% of wind speed, integrated with RK2 at 15-minute
steps, run backwards in time using a negative timestep.
We run it 50 times with the wind coefficient, the current field and the slick
boundary perturbed within their honest uncertainty ranges. The 50 endpoints are
stacked into a probability grid. The output is therefore a probability field with
50% and 90% confidence radii, never a single point, and it widens the further
back in time we rewind.
We deliberately do not model vertical dispersion, emulsification, evaporation or
oil weathering chemistry.
KNOWN LIMITATION, AND IT IS THE DOMINANT ONE: our current field is 9 km
resolution at daily cadence. That error source dominates everything else,
including our choice of numerical scheme and our omitted physics.

STAGE 3 — VESSEL ATTRIBUTION
Input: the origin probability field and time window from Stage 2, plus historical
AIS (Automatic Identification System) vessel transponder data from the US NOAA
Marine Cadastre archive, which is public domain.
We score every vessel present on spatial proximity weighted by the origin
probability density, trajectory consistency, transponder gaps overlapping the
window, unusual slowdown, vessel type prior, and geometric agreement between the
vessel's track and the slick's shape. Output is a ranked shortlist plus explicitly
excluded vessels with stated reasons, or a refusal to attribute when confidence
is insufficient.
We also cross-check ships visible in the radar image against AIS: a vessel radar
can see that AIS does not report is a "dark vessel".

STAGE 4 — VERIFICATION
For each demonstration case we compare our system's conclusion against what the
official investigation actually concluded, with the source document cited.
We show misses as readily as hits.

--- WHAT WE ALREADY KNOW (DO NOT SPEND RESEARCH EFFORT RE-ESTABLISHING THIS) ---

- Oil appears dark on SAR because it damps short gravity and capillary waves.
- Look-alike discrimination is an open research problem, not an engineering task.
- The "damping ratio" (contrast between slicked and clean sea) is an established
  metric that relates primarily to oil THICKNESS, not directly to age, and the
  literature describes SAR thickness retrieval from damping ratio as not yet a
  mature application.
- Damping ratio decreases with increasing wind speed and turbulence, so wind is a
  confounder. Oil-sea contrast fails at very low wind (below roughly 2-3 m/s) and
  very high wind (above roughly 10-14 m/s).
- Backscatter is typically lower in the centre of a slick than at its edges,
  reflecting a thickness and weathering gradient.
- Fay's classical spreading theory describes three regimes; the gravity-viscous
  phase dominates for our timescales, with slick radius growing roughly as the
  fourth root of time.
- Surface oil drifts at the current velocity plus roughly 2.5-3.5% of wind speed.
- SkyTruth's Cerulean is an existing operational system that detects slicks in
  Sentinel-1 with a U-Net and attributes them to AIS vessels using metrics they
  call parity, proximity and temporality, over an AIS window from 8 hours before
  the image to 6 hours after.
- EMSA's CleanSeaNet performs satellite spill detection fused with AIS for
  European coast guards.
- INCOIS operates an Online Oil Spill Advisory system built on NOAA's GNOME
  trajectory model, running forwards only.
- OpenDrift, from MET Norway, is the standard open-source Lagrangian trajectory
  framework and includes an OpenOil module with weathering.

--- RESEARCH STANDARDS WE REQUIRE ---

1. Cite primary sources: peer-reviewed papers, official technical documentation,
   government or agency reports. Give authors, year, journal or publisher, and a
   working link or DOI. Secondary summaries are acceptable only when clearly
   labelled as such.
2. State your confidence for every substantive claim, using exactly these labels:
   [ESTABLISHED] - reproduced across multiple independent peer-reviewed sources
   [EMERGING]    - published but limited replication, or contested
   [SPECULATIVE] - plausible reasoning, no direct empirical support found
3. NEGATIVE RESULTS ARE VALUABLE. If something cannot be done, or has been tried
   and failed, say so plainly and cite it. "This is not currently possible
   because X" is a useful finding, not a failure of the research.
4. Do not fabricate citations. If you cannot find a source for a claim, say
   "no source found" rather than producing a plausible-looking reference.
5. Quantify wherever the literature does: accuracy figures, error bars, sample
   sizes, operating ranges, resolution limits. A number with a source beats an
   adjective.
6. Note publication dates and flag anything that may have been superseded.
7. Where sources disagree, present the disagreement rather than picking a side.

=== END OF CONTEXT. THE SPECIFIC RESEARCH TASK FOLLOWS. ===
```
---

# PART D — OUTPUT STRUCTURE

Every finished research document follows this shape. Give this to ChatGPT in the synthesis step.

```markdown
# RESEARCH: <title>
*Compiled by Urooz · Sources: Gemini Deep Research + Perplexity Pro · <date>*

## 1. EXECUTIVE SUMMARY
Half a page maximum. What was asked, what was found, and the single most
important consequence for our project. Written so someone who reads only this
section is not misled.

## 2. THE DIRECT ANSWER
The question, answered in plain terms, with a confidence label.

## 3. WHAT IS ESTABLISHED
Findings supported by multiple independent peer-reviewed sources. Each with
citation and, where the literature gives one, a number.

## 4. WHAT IS EMERGING OR CONTESTED
Published but not settled. Say who claims what, and why it is contested.

## 5. WHAT IS NOT KNOWN
Explicit gaps. What nobody has done, or what has been tried and failed.
This section is as valuable as section 3 — do not leave it thin.

## 6. WHERE THE TWO RESEARCH TOOLS DISAGREED
Any point where Gemini and Perplexity reached different conclusions, with both
positions stated. Do not resolve these silently.

## 7. IMPLICATIONS FOR UDGAM
Concrete, specific, addressed to our system. Which stage does this affect, what
should change, what should not. Name the team member whose work it touches.

## 8. WHAT WE COULD CLAIM ON STAGE
Sentences we could honestly say to judges, each with its supporting citation.
Also: sentences we must NOT say, and why.

## 9. OPEN QUESTIONS FOR FURTHER RESEARCH
What a follow-up investigation should ask.

## 10. SOURCE LIST
Full citations, grouped by section, with links. Mark any you personally
verified with [VERIFIED].
```

---

# PART E — THE SYNTHESIS PROMPT

Paste this into ChatGPT along with both raw reports.

```
I have two independent AI research reports on the same question, produced by
Gemini Deep Research and Perplexity Pro. Synthesise them into a single document
using the exact structure I give below.

Rules:
- Do not add information that is not in either report. You are structuring, not
  researching.
- Where the two reports agree, state it once and note that both found it.
- Where they DISAGREE, put it in section 6 with both positions. Do not pick a
  side and do not smooth it over. Disagreement is a finding.
- Preserve every citation, author, year and link exactly as given.
- Preserve confidence labels: [ESTABLISHED], [EMERGING], [SPECULATIVE].
- If a claim appears in only one report, keep it and mark which one.
- Keep every number. Do not round, generalise, or convert quantitative findings
  into adjectives.
- Write in plain, direct English. No filler, no hedging language, no
  "it is important to note".

[paste the output structure from Part D here]

REPORT 1 (Gemini Deep Research):
[paste]

REPORT 2 (Perplexity Pro Research):
[paste]
```

---

# PART F — VERIFICATION (NOT OPTIONAL)

Deep research tools sometimes produce citations that look real and are not. **A fabricated citation in front of an NTRO panel would be worse than having no research at all.** Before delivering anything:

1. **Spot-check at least three citations** — ideally the three the document leans on most heavily. Open the link. Confirm the paper exists, the authors match, and it actually says what the report claims. Mark each `[VERIFIED]` in the source list.
2. **Check any number we might quote on stage.** If a figure could end up on a slide, it gets verified.
3. **Flag anything you could not verify** in section 6 or 9 rather than deleting it — an unverified lead is still a lead, as long as it is labelled.
4. **Sanity-check the dates.** A 2011 result may have been superseded.

If a source turns out to be fabricated, say so in the delivery message. That tells us how much to trust the rest of that report.

---

# PART G — DELIVERY

1. Save the finished document to `docs/research/<task-name>.md` in the repo.
2. Keep both raw reports in `docs/research/raw/` — Akshat may want to check something you summarised.
3. Post in the group: the task name, the one-line answer, and the single most important implication. Three sentences.
4. If a finding **contradicts something we currently believe**, say that first and loudly. That is the highest-value output you can produce and it is time-sensitive — someone may be building on the wrong assumption right now.

---

# PART H — YOUR RESEARCH QUEUE

| # | Task | Tool | Document | Priority |
|---|---|---|---|---|
| 1 | Project naming | ChatGPT only, no deep research | `docs/_archive/urooz/research-01-naming.md` | Quick — do first, it unblocks the deck and the UI |
| 2 | The science of oil slick age estimation | Full workflow | `docs/research/age-engine-brief.md`, Research A | **Highest** |
| 3 | Architecture and applications of an age engine | Full workflow, **takes Research A's output as input** | `docs/research/age-engine-brief.md`, Research B | **Highest** |

**Do them in order.** Task 3 explicitly depends on task 2's output.

Later tasks Akshat may add: finding two more US demonstration cases via SkyTruth Cerulean's public map, and deployment cost figures for national-scale coverage.

---

# PART I — WHAT MAKES YOUR RESEARCH GOOD

**Specificity beats breadth.** A page with five cited numbers is worth more than ten pages of context we already have.

**Say what cannot be done.** Our whole pitch rests on being honest about limits. If the answer to "can we accurately estimate slick age" turns out to be "not reliably, and here is exactly why", **that is a genuinely valuable finding** — it means we present a bounded estimate with a stated method instead of overclaiming and getting dismantled in December.

**Follow the trail.** If a paper mentions a technique, find who else used it and whether it worked for them.

**Watch for operational versus academic.** A method that works on a curated dataset and a method deployed by a coast guard are different claims. Distinguish them.

**Bring back the language.** Note the exact technical terms the field uses. Using the right vocabulary in front of an NTRO panel signals we read the literature; using approximate vocabulary signals we did not.
