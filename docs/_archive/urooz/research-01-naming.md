# RESEARCH TASK 01 — Project Naming
*Quick task. ChatGPT only — no deep research needed. Do this first; it unblocks the deck, the UI header and the repo.*

---

## Why this matters more than it sounds

The name appears on every slide, in the UI header, in the repo, and in every sentence anyone says about the project for the next three months. **Internals are binding — whatever we present in September we defend at the national finale in December.** Renaming later is possible but embarrassing.

The current working name is **UDGAM**. It is not good enough. It reads as arbitrary, it does not expand to anything, and it says nothing about what the system does.

## What good looks like in this field

Systems in this exact space are named in two recognisable registers:

**Register A — evocative single word, often with a backronym.** `CleanSeaNet` (EMSA). `Cerulean` (SkyTruth). `GNOME` (NOAA's trajectory model). `OpenDrift` (MET Norway). `SEASTAR`, `TRITON`, `NEPTUNE` in the wider maritime domain.

**Register B — Indian agency style, often Sanskrit or Hindi, often with an English expansion.** Indian defence and space programmes lean heavily on this — mythological or elemental names, short, pronounceable, with a technical backronym underneath. This register carries real weight with an Indian panel, and NTRO is an Indian intelligence agency.

**The strongest names sit in both registers at once:** a meaningful word that *also* expands to a technical description.

## Selection criteria — rank candidates against these

1. **It expands.** Each letter maps to a real word describing what the system does. Not forced — a strained backronym is worse than none.
2. **It means something on its own.** Ideally connected to oceans, sight, tracing, justice, attribution, or water.
3. **Pronounceable on first sight** by an Indian panel and by an international one. Two or three syllables.
4. **Not already taken** in this domain. Check: existing maritime systems, Indian naval exercises and programmes, satellite missions, and active open-source projects. **This check is the part that needs actual searching.**
5. **Works as a spoken sentence** — "we built X" has to sound natural said out loud, twenty times, on stage.
6. **Available-ish as a handle** — a GitHub org or domain that is not obviously occupied is a bonus, not a requirement.

## What the name should convey

Pick concepts from what the system actually does:
- Tracing something back to its origin
- Seeing what is hidden (dark vessels, ships that go quiet)
- Attribution, accountability, evidence
- Ocean, water, coastline
- Reversal — running time backwards
- Watching over, guardianship

Words the expansion could plausibly draw on: **maritime, marine, ocean, satellite, radar, aperture, spill, slick, source, origin, attribution, tracing, tracking, reverse, backtrack, drift, vessel, identification, intelligence, awareness, analysis, network, engine, platform, system, forensics.**

## The prompt to use

Paste this into ChatGPT. **Turn on web search** so it can actually check whether names are taken.

```
I need a name for a technical system. Generate candidates and check availability.

THE SYSTEM
A satellite-based oil spill forensics platform. It detects oil slicks in
Sentinel-1 radar imagery, runs ocean current and wind physics backwards in time
to reconstruct where and when the oil entered the water, then correlates that
reconstructed origin against historical ship transponder (AIS) data to produce a
ranked shortlist of suspect vessels — plus vessels it explicitly rules out. It
also flags "dark vessels": ships visible to radar that broadcast no transponder
signal.

It is an entry to India's Smart India Hackathon 2026, sponsored by the National
Technical Research Organisation (NTRO), India's technical intelligence agency.
The framing for that audience is maritime domain awareness — identifying vessels
operating dark — with spill attribution as the demonstrator.

The core idea in one line: satellite forensics that traces an oil spill back to
the ship that caused it.

WHAT I WANT
20 candidate names. For each one give me:
  - the name
  - the acronym or backronym expansion, if it has one
  - the literal meaning or origin of the word, if it is a real word
  - one line on why it fits this system
  - an availability check: is this name already used by an existing maritime
    monitoring system, satellite mission, Indian defence or space programme,
    naval exercise, or an active open-source project? Search for this; do not
    guess. Say clearly if you find a conflict.

SPLIT THE 20 ACROSS THREE GROUPS
  Group A (8): Sanskrit, Hindi or Indian-mythological words that ALSO work as a
    backronym. Give the literal meaning. Prefer words connected to oceans, water,
    sight, justice, order, or tracing.
  Group B (8): English or Latinate words that work as both a real word and an
    acronym.
  Group C (4): pure constructed acronyms where the expansion is the point and the
    word is built from it.

CONSTRAINTS
  - 2-3 syllables, pronounceable on first sight
  - the expansion must describe the system honestly, not vaguely
  - avoid anything already strongly associated with an existing Indian defence,
    space or naval programme
  - avoid names that are hard to say for a non-Indian audience OR for an Indian
    audience — it has to work for both
  - it must sound natural in the sentence "we built ___"

THEN
Shortlist your top 5 with reasoning, and for each write the single sentence we
would use to introduce it on stage, in the form:
"___ — satellite forensics that traces an oil spill back to the ship that caused it."

Flag honestly if any of your top 5 has an availability conflict.
```

## Deliverable

A short document — `docs/research/naming.md` — containing:
- The full table of 20 candidates
- The top 5 shortlist with reasoning and availability status
- **Your own recommendation**, with one paragraph of reasoning

**Give a recommendation, don't just hand over a list.** You are the person on this team with the best judgement about how things read and sound, and that is exactly what this decision needs. Akshat makes the final call, but he should be choosing between your top two, not sifting twenty.

## Time
Under an hour. Do not over-invest — this is the smallest of your three tasks. The two age-engine research tasks are where your effort should go.
