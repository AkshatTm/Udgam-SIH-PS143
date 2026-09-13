# RESEARCH TASK 02 — The Oil Slick Age Engine
## Two linked investigations. This is the most valuable research on the board.

*Full workflow: context prompt from the master document, then the brief below, run in **both** Gemini Deep Research and Perplexity Pro, then synthesised in ChatGPT.*

---

# WHY THIS MATTERS

## For the hackathon
Knowing how old a slick is **is not a feature, it is a filter**. If we can bound a slick at 6–18 hours old instead of 0–72, the pool of suspect vessels shrinks by roughly an order of magnitude and every downstream score sharpens. The problem statement itself asks for slick age "if feasible" — most competing teams will treat that as optional and skip it.

## For everything after the hackathon
A general, physics-grounded engine that estimates **how long ago a surface phenomenon began, from a single remote-sensing observation** is a much bigger thing than an oil spill tool. If it works, it has applications well beyond this problem statement, and that is the difference between a hackathon project and something worth continuing.

**But it may not be possible to the accuracy we would want.** Finding that out, with citations and a clear explanation of *why*, is a completely acceptable and genuinely valuable outcome — it means we present a bounded estimate with a stated method instead of overclaiming and being taken apart at the finale. **Do not go looking for a yes.**

## The two-part structure
**Research A is pure science.** Can this be done, by what physics, to what accuracy, and what stops it? No architecture, no code, no product talk.

**Research B is engineering and application.** It takes Research A's finished output as an input and asks: given what is scientifically possible, how would you build it, and what else is it good for?

**Do them in order. B is not valid without A.**

---

# RESEARCH A — THE SCIENCE

## What to paste
Master context prompt, then everything in the box below.

```
=== RESEARCH TASK A: THE SCIENCE OF OIL SLICK AGE ESTIMATION ===

THE CENTRAL QUESTION
Given a single satellite observation of an oil slick on the sea surface, how
accurately can the time elapsed since the oil entered the water be estimated,
and what physical processes make that inference possible or impossible?

This is a pure science investigation. Do not discuss software architecture,
implementation, or applications. Establish what is physically knowable and to
what precision.

--- SECTION 1: THE WEATHERING PROCESSES ---

Oil on water changes over time through several processes. For EACH of the
following, establish:
  (a) the governing physics or chemistry, with the standard formulation used in
      the literature
  (b) the characteristic timescale over which it acts
  (c) whether it produces a measurable change in any remote-sensing observable
  (d) how strongly it depends on things we cannot observe from one image — oil
      type, released volume, sea state, water temperature, salinity
  (e) published quantitative relationships, with error bars where given

Processes to cover:
  - Spreading (gravity-inertial, gravity-viscous, surface-tension-viscous
    regimes; Fay's theory and its modern successors and criticisms)
  - Evaporation of light fractions
  - Emulsification / water-in-oil emulsion formation ("chocolate mousse")
  - Natural dispersion into the water column
  - Dissolution
  - Photo-oxidation
  - Biodegradation
  - Sedimentation and interaction with suspended particulate matter
  - Advective stretching and shear dispersion by ocean currents
  - Fragmentation of a continuous slick into patches

--- SECTION 2: OBSERVABLE SIGNATURES ---

For each remote-sensing modality, what changes measurably as a slick ages, and
what has actually been demonstrated in published work?

  - SAR backscatter and damping ratio (note: we already know damping ratio maps
    primarily to thickness, not age, and that wind confounds it — go beyond this)
  - Polarimetric SAR: co-polarised ratio, entropy, alpha angle, degree of
    polarisation, and any published use of polarimetry to infer weathering state
  - Multi-frequency SAR (X, C, L band): does damping behaviour differ with
    frequency in a way that indicates age or emulsification?
  - Slick geometry: area growth, perimeter complexity, fractal dimension,
    elongation under shear, fragmentation into multiple parts
  - The internal contrast gradient within a slick (centre versus edge)
  - Optical and hyperspectral: colour, thickness proxies, oil-water emulsion
    signatures
  - Thermal infrared
  - Fluorescence and any active sensing methods

For each: is this ESTABLISHED, EMERGING, or SPECULATIVE as an age indicator?
Give published accuracy figures where they exist.

--- SECTION 3: WHAT HAS ACTUALLY BEEN ATTEMPTED ---

  - Has anyone published a method that estimates oil slick age from remote
    sensing? Who, when, what accuracy, on what data, validated how?
  - Do any operational spill response systems estimate age? What do NOAA, EMSA,
    ITOPF, INCOIS, or national coast guards actually use in practice?
  - Are there controlled release experiments with known release times and
    subsequent satellite or airborne observation? (For example, the NOFO
    oil-on-water exercises in the North Sea.) These would be the gold-standard
    validation data — do they exist, and are they public?
  - Is age inferred indirectly in practice, for instance by back-calculating from
    a known incident time rather than from the observation itself?
  - What is the actual state of the art, stated as a number with an error bar?

--- SECTION 4: THE INVERSE PROBLEM ---

  - Framed formally: is estimating age from a single observation well-posed or
    ill-posed? What degeneracies exist — that is, which different combinations of
    (age, volume, oil type, sea state) produce indistinguishable observations?
  - What additional information would break each degeneracy?
  - What is the theoretical accuracy limit given only free public data
    (Sentinel-1 SAR, 9 km daily currents, hourly reanalysis winds)?
  - How much does that limit improve with each additional input: a finer current
    model, a second satellite pass, knowledge of the oil type, wave data,
    sea surface temperature?
  - Is there published work on multi-observation age estimation — two or more
    passes over the same slick?

--- SECTION 5: ADJACENT FIELDS ---

Has "time since onset" been successfully inferred from single remote-sensing
observations in ANY comparable domain? Look at:
  - Harmful algal blooms
  - Sargassum and floating vegetation mats
  - Marine plastic and debris accumulation
  - Wildfire smoke and volcanic ash plumes
  - Atmospheric pollution plumes
  - Sea ice formation
  - Glacial and lava flows

For any that succeeded: what made it tractable there, and does that transfer to
oil on water? This section may be the most valuable in the whole report — a
method that works in an adjacent field and has not been tried on oil slicks is
exactly the kind of finding we are looking for.

--- SECTION 6: THE HONEST BOTTOM LINE ---

  - Can oil slick age be estimated accurately from a single satellite
    observation? Answer directly, with a confidence label.
  - If yes: to what precision, under what conditions, and what breaks it?
  - If no: what is the best achievable bound, and what specifically prevents
    better?
  - What would a credible, defensible age estimate look like — a point estimate,
    a range, a probability distribution, or a qualitative class?
  - What claims about age estimation would a domain expert consider overclaiming?
    We need to know exactly which sentences NOT to say.

=== END OF TASK A ===
```

## What good output looks like
Not "age estimation is challenging". Rather: *"Fay's gravity-viscous regime predicts area growth as t^(1/2) with constant k, validated against N experimental releases to within X% for volumes between A and B — but the relationship degenerates once the slick fragments, typically after Y hours, and no published method resolves that."*

Numbers, sources, and clearly-marked limits.

---

# RESEARCH B — ARCHITECTURE AND APPLICATIONS

> **Do not start B until A is finished, synthesised and verified.** B takes A's completed document as an input.

## What to paste
Master context prompt → **the entire finished Research A document** → then everything in the box below.

```
=== RESEARCH TASK B: ARCHITECTURE AND APPLICATIONS OF AN AGE ESTIMATION ENGINE ===

I have attached a completed scientific review of oil slick age estimation
(Research A, above). Take its findings as your starting point — its constraints
are real constraints, and do not propose anything it establishes is impossible.

THE QUESTION
Given what Research A establishes is scientifically possible, how would one build
a standalone engine that estimates the age of a surface phenomenon from remote
sensing — and what is such an engine worth beyond oil spills?

--- SECTION 1: ARCHITECTURE OPTIONS ---

Evaluate each of these approaches against Research A's findings:

  (a) Pure forward physics with inversion: simulate spreading and weathering
      forward for candidate ages, find the age reproducing the observation
  (b) Data-driven: learn age from labelled examples — and address head-on
      whether enough labelled data with known release times exists
  (c) Hybrid physics-informed ML: physics-constrained networks, differentiable
      simulators, neural operators
  (d) Bayesian inverse modelling with explicit uncertainty propagation
  (e) Ensemble or multi-estimator approaches that combine independent estimators
      and report agreement

For each: data required, computational cost, interpretability, robustness when
inputs are missing, and how it degrades when assumptions are violated.
State which is most appropriate given Research A's constraints, and why.

--- SECTION 2: INPUTS AND THEIR AVAILABILITY ---

  - What inputs does each architecture need?
  - Which are freely and globally available, and which are paid, regional, or
    restricted? Name specific datasets and access routes.
  - What accuracy is achievable using ONLY free global data?
  - Rank additional paid or restricted inputs by accuracy gained per unit of
    cost or difficulty. We want to know what the cheapest meaningful upgrade is.

--- SECTION 3: CALIBRATION AND VALIDATION ---

This is the hardest engineering problem and the section we care most about.

  - Ground truth for age is scarce. What validation strategies exist when you
    have very few examples with a known release time?
  - Can controlled release experiments, documented incidents with known incident
    times, or synthetic-but-physically-grounded data substitute? What are the
    failure modes of each?
  - How should an engine express uncertainty so it is trustworthy — confidence
    intervals, calibrated probability distributions, or explicit refusal to
    answer outside its validated range?
  - How would you demonstrate the engine is calibrated rather than merely
    confident? What does a calibration curve look like for a quantity like this?
  - What would a credible peer-reviewable validation protocol look like?

--- SECTION 4: FAILURE MODES AND ABSTENTION ---

  - Under what conditions should such an engine REFUSE to estimate?
  - How would it detect that it is outside its validated envelope?
  - What are the consequences of a wrong age estimate in each application in
    section 5 — and where is a wrong answer actually dangerous rather than merely
    unhelpful?

--- SECTION 5: APPLICATIONS BEYOND OIL SPILLS ---

This section determines whether this is a hackathon feature or a real product.

  5a. WITHIN oil spill response and enforcement:
      - Does age change what a responder should do? Is fresh oil recoverable
        while weathered oil is not, and at what point does that switch?
      - Legal and liability use: does establishing timing matter in prosecution
        or insurance? Cite actual cases or regulatory frameworks if they exist.
      - Distinguishing chronic operational discharge from acute accidental
        release
      - Distinguishing natural seeps from anthropogenic spills
      - Prioritising which of many detections to respond to first

  5b. BEYOND oil, in other domains. For each, assess whether the same
      "time since onset from a single observation" engine transfers, what would
      change, and who would pay for it:
      - Harmful algal bloom age and stage, for fisheries and public health
      - Sargassum drift and landfall forecasting
      - Marine plastic accumulation and source attribution
      - Illegal discharge and dumping enforcement generally
      - Wildfire and volcanic plume age, for air quality forecasting
      - Industrial effluent and wastewater plume tracing in rivers and coasts
      - Chemical or radiological release timing
      - Search and rescue: how long has an object been drifting?
      - Environmental forensics and compliance monitoring
      - Insurance, reinsurance and catastrophe modelling
      - Defence and intelligence: inferring timing of an observed event from a
        single overhead observation

      For each: is the underlying inverse problem the SAME problem, a RELATED
      one, or a different one that merely looks similar? Be strict about this
      distinction — the value of a general engine depends entirely on it.

  5c. What is the most defensible general claim about what such an engine is?
      Give the single most accurate one-sentence description.

--- SECTION 6: PRIOR ART AND POSITIONING ---

  - Does anything like this already exist, in any domain, commercially or
    academically?
  - Who would be building this if it were valuable — and if nobody is, what is
    the most likely reason?
  - What would be genuinely novel about building it, and what would merely be
    reimplementation?

--- SECTION 7: SPECIFIC RECOMMENDATIONS FOR OUR PROJECT ---

Our current system runs a 24-hour backward drift and outputs an origin
probability field plus a time window. We currently estimate age using three
independent estimators — a shear-dispersion approach using our own advection
model, a Fay spreading-law approach, and an elongation-under-shear approach —
and we combine them by intersection when they agree and union when they do not.

  - Given Research A's findings, is that approach sound? Where is it weak?
  - What is the single highest-value improvement we could make?
  - What accuracy could we honestly claim, and in exactly what words?
  - What must we NOT claim?
  - How much does a better age estimate actually narrow the vessel search space,
    quantitatively, given typical shipping densities?
  - Is a standalone age engine a credible thing to present as a distinct
    contribution, or is it better framed as a component of the pipeline? Give a
    direct recommendation either way.

=== END OF TASK B ===
```

---

# WHAT WE DO WITH THE RESULTS

**If the science supports a defensible engine:** it becomes a named contribution in the pitch, Anushka's Phase 1 gets rebuilt around the best method the literature offers, and Section 5b becomes a roadmap slide that shows this outlives the hackathon.

**If the science says it cannot be done accurately:** that is equally useful, and arguably safer. We present a **bounded estimate with a stated method and stated limits** — which is exactly the register the rest of the project already works in — and Section 6 of Research A tells us precisely which sentences to avoid. Being the team that knows why the obvious method doesn't work is a stronger position than being the team that claimed it did.

**Either way, Section 5 of Research B is the slide that separates us.** Every other team will present an oil spill tool. A team that can say *"this component is a general inverse-timing engine, and here are four other domains where the same problem appears"* is presenting something with a future.

## Delivery
Both documents to `docs/research/`, raw reports to `docs/research/raw/`. Post the one-line answer from each in the group.

**Flag immediately, before finishing the write-up, if either research contradicts something we currently believe.** Anushka is building age estimators right now. If the literature says one of her three approaches is known not to work, she needs to know today, not when the document is polished.
