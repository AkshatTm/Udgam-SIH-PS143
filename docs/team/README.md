# The team

Six people, four stages, one interface. This page maps each person to everything they own and
everything they wrote, so nobody has to hunt for the record of their own work.

Ownership is Master Plan Part 7. Who is blocked on whom is Part 8 — **check it before saying you
are blocked**, because most of what looks like a dependency is not one.

---

## Who owns what

| Person | Owns | Brief | Work log |
|---|---|---|---|
| **Akshat** | Contracts, case selection, 2-band GEE exports, `verification.json`, the exporter, the validator, integration (producer side), deck, demo prep | [`akshat-remaining.md`](akshat-remaining.md) — the live task list · [`akshat-integration.md`](akshat-integration.md) | [`../updates/akshat.md`](../updates/akshat.md) · [`../updates/_INTEGRATION.md`](../updates/_INTEGRATION.md) |
| **Soumirya** | Stage 1 entire: scene classifier, U-Net, classical features, ship detections, chronic/acute | [`soumirya-stage1-detection.md`](soumirya-stage1-detection.md) | [`../updates/soumirya.md`](../updates/soumirya.md) |
| **Anushka** | Stage 2 entire: integrator, ensemble, origin, age estimation, forward drift, coastline, OpenDrift comparison | [`anushka-stage2-drift.md`](anushka-stage2-drift.md) | [`../updates/anushka.md`](../updates/anushka.md) |
| **Jaiveer** | Stage 3 entire: AIS, scoring, dark vessels, infrastructure, traffic prior, repeat offenders, evaluation curve | [`jaiveer-stage3-attribution.md`](jaiveer-stage3-attribution.md) | [`../updates/jaiveer.md`](../updates/jaiveer.md) |
| **Harshita** | Frontend entire (five screens, self-guiding UX), then integration (consumer side), demo machine | [`harshita-frontend.md`](harshita-frontend.md) · [`harshita-integration.md`](harshita-integration.md) | [`../updates/harshita.md`](../updates/harshita.md) |
| **Urooz** | Research lead — naming, then the slick-age investigations | [`urooz-research-lead.md`](urooz-research-lead.md) | [`../updates/urooz.md`](../updates/urooz.md) |

---

## Where the rest of your work is

| You | Code | Evidence you produced | Archive |
|---|---|---|---|
| **Akshat** | `pipeline/export/`, `scripts/`, `verification/` | [`../receipts.md`](../receipts.md), [`../evaluation/deck-numbers.md`](../evaluation/deck-numbers.md) | — |
| **Soumirya** | `pipeline/detect/` | [`../evaluation/stage1-accuracy-programme.md`](../evaluation/stage1-accuracy-programme.md), `pipeline/detect/results/`, `data/labels/features_test.csv` | [`../_archive/soumirya/`](../_archive/soumirya/) |
| **Anushka** | `pipeline/drift/` | [`../evaluation/stage2-numbers.md`](../evaluation/stage2-numbers.md), [`../evaluation/stage2-component-report.md`](../evaluation/stage2-component-report.md), [`../evaluation/stage2-age-decision-brief.md`](../evaluation/stage2-age-decision-brief.md) | — |
| **Jaiveer** | `pipeline/attribute/` | [`../evaluation/stage3-injected-offender-curve.md`](../evaluation/stage3-injected-offender-curve.md), [`../evaluation/stage3-issue-register.md`](../evaluation/stage3-issue-register.md), `pipeline/attribute/results/` | [`../_archive/jaiveer/`](../_archive/jaiveer/) |
| **Harshita** | `web/` | the interface itself; [`../operations/demo-runbook.md`](../operations/demo-runbook.md) | — |
| **Urooz** | — (research lead, no code) | [`../research/age-engine-brief.md`](../research/age-engine-brief.md) | [`../_archive/urooz/`](../_archive/urooz/) |

---

## A note on the briefs

Four of these documents — Anushka's, both of Harshita's, and Akshat's integration brief — carry a
banner saying they are historical, because remaining work from them transferred to
[`akshat-remaining.md`](akshat-remaining.md) on 14 Sept 2026.

**Historical does not mean irrelevant.** They are the fullest written account of the reasoning
behind each stage: why the model is what it is, what was tried and rejected, and what the traps
were. Read yours before you present, review or hand over. They were briefly archived and then
promoted back out precisely because archiving them buried the record of what each person built.

## Keeping a log

After each phase, append to your file in [`../updates/`](../updates/) using
[`../updates/TEMPLATE.md`](../updates/TEMPLATE.md). Four lines: what was done, files touched,
exact run command, open issues. Newest entry at the top.

Your AI has no memory between chats. That file is the memory — it is what lets you close a chat,
switch tools, hand your work to someone else, or come back after sleeping, and lose nothing.

To resume from it:

> Here are the master plan, my task document, and my update log. Read the top entry and tell me
> exactly where I left off and what the next step is.
