# RUNBOOK — freeze, demo day, and what to do when something breaks
*Everyone reads this. Judges wander and ask whoever is nearest — "that's not my part" is the worst possible answer.*

---

## 1. The freeze — 12 hours before judging

Non-negotiable. Your own risk analysis names "someone pushes a small improvement the night before" as the most common way strong teams lose demos. An unrehearsed better demo loses to a rehearsed worse one.

**At freeze (Akshat runs this):**
```bash
git checkout -b demo && git push -u origin demo
```
- Demo machine checks out `demo` and **never** pulls again.
- `main` may keep moving. Nothing from `main` reaches the demo machine.
- Exceptions: **none.** Including for Akshat.

**Freeze checklist:**
- [ ] All case bundles present and `validate_case.py` PASSES on each
- [ ] App runs on the demo machine **with wifi turned off**
- [ ] Every case loads, every layer toggles, the slider scrubs, every panel populates
- [ ] Urooz's smoke-check list run end to end, on the demo machine
- [ ] Fallback video recorded (full run, screen capture, audio optional) and saved **locally on the demo machine plus one phone**
- [ ] `docs/receipts.md` complete: GEE scene IDs, Zenodo DOI, NOAA file names, incident references
- [ ] Deck exported to PDF, on the machine and on a phone
- [ ] Laptop charger, HDMI adapter, phone hotspot ready

**After freeze:** two full timed rehearsals with someone playing hostile judge. Fix only what the rehearsals expose, and only if the fix is under ten minutes.

---

## 2. Demo machine rules
Chosen by Tue 8 (Akshat's or Harshita's). Never present from a machine the app has not run on. Before judging: close everything else, disable notifications and auto-updates, set display to never sleep, plug in power, open the app in one browser window, no other tabs. Have a second laptop with the same repo and video as a cold spare.

---

## 3. When something breaks live

**The ladder — go down one rung at a time, never skip to the bottom.**

| Rung | Failure | Move |
|---|---|---|
| 1 | A layer or panel misbehaves | Toggle it off, keep talking, continue. Do not debug in front of a judge. |
| 2 | A case won't load | Switch to another case. "Let me show you this one instead." |
| 3 | The app is broken | Fallback video. "The pipeline output is precomputed — here's a recorded run, and I'll walk you through the code and the case files." |
| 4 | The laptop dies | Spare laptop, or the video from a phone. |
| 5 | Everything is gone | The deck plus the case JSON files on a phone. Talk through the architecture. |

**Never say:** "it was working ten minutes ago," "that's not my part," or "this is just a prototype."
**Say instead:** "That layer's misbehaving — let me show you the part that matters," then move on within five seconds. Judges forgive a bug. They do not forgive panic.

---

## 4. Division of labour during judging
- **Akshat** drives the narrative and answers architecture, methodology, and hostile questions.
- **Harshita** drives the laptop, so Akshat can face the judges and gesture at the screen.
- **Soum, Anushka, Jaiveer** each answer questions about their stage — one clear sentence, then hand back.
- **Urooz** watches the judges' faces and flags when they've lost the thread.
- One person talks at a time. Interrupting each other reads as a team that doesn't know its own project.

---

## 5. Q&A — everyone knows these cold, 25 seconds each

**"Is this real data?"** Real Sentinel-1 from Google Earth Engine, real HYCOM currents, real ERA5 winds, real NOAA Coast Guard AIS. Receipts are one click away — scene IDs, dataset DOI, file names. The only synthetic thing in the project is the fake bundle we used to build the frontend before the pipeline existed.

**"Is this precomputed?"** Yes, deliberately. The pipeline runs offline and exports a case bundle; the interface plays it back. That's why the slider is instant and why it can't break on venue wifi. Every serious demo works this way.

**"How accurate is detection?"** *(Soum's real held-out number.)* Then: separating oil from look-alikes is an open research problem — the published deep-learning benchmark is around 53% IoU, and it's 53% for everyone. That's precisely why the system doesn't rest on detection alone: drift and AIS are independent evidence streams.

**"Why is your origin a cloud and not a point?"** Because a point would be a lie. We run 50 perturbed simulations; the spread is the honest uncertainty, and it widens the further back we look. A team showing a sharp origin point is lucky or wrong.

**"What if you accuse an innocent ship?"** Nothing happens automatically. The output is a ranked, evidence-backed lead list — like a tip line. A human investigator verifies. And we actively exonerate: here's the exclusion panel and the reason for each.

**"Isn't this just CleanSeaNet?"** Yes, and that's the point. Europe has had this since the 2000s. India has forward drift prediction through INCOIS and no attribution capability at all. We're closing a national gap, not inventing a paradigm.

**"Why no ships on the Indian case?"** Free bulk historical AIS exists for US waters and not for Indian waters. That data gap is itself part of what we're pointing at. The full chain runs on our US case.

**"What's next?"** Deep-learning segmentation (dataset already downloaded), the dark-vessel cross-check — radar sees a ship, AIS doesn't — behavioural anomaly scoring, and repeat-offender tracking across incidents.

**"How much would this cost to run?"** Satellite data is free, currents and winds are free, AIS is free. The cost is compute per scene plus storage. *(Akshat: have a rough annual number for national coverage before the finale.)*

**Closing line, memorised by everyone:** *"INCOIS tells the Coast Guard where the oil is going. Nobody tells them where it came from. We built the other half."*

---

## 6. What we deliberately did not build — say it as roadmap, not apology
CNN segmentation · dark-vessel radar-vs-AIS cross-check · injected-offender evaluation curve · chronic-vs-acute discrimination · forward drift prediction · repeat-offender history · live-run API. Stating scope decisions confidently reads as engineering judgement. Discovering them under questioning reads as gaps.

---

## 7. After the internal round
Within 24 hours, before anyone forgets: write down every question asked and how it landed, what broke, what the judges reacted to, and what you'd cut or add. That document is worth more for December than any code written that week. **Internals are binding — this is the project you defend at the finale.**
