# PROMPTING PLAYBOOK
*How the six of us drive AI without burning quota or generating code that runs and lies. Read once, keep open.*

---

## 1. Two AIs, two jobs

**ChatGPT = navigator.** Understands the phase, plans steps, explains what you're doing and why, reviews output, decides what to try next. It does not need to write production code.

**Claude Code / Antigravity = driver.** Writes the code, in a repo with `CLAUDE.md` present.

Why the split: the navigator holds long context cheaply, the driver has the files. Talking to the driver about strategy wastes its expensive context on conversation.

**Opening a navigator chat** (once per phase, not per message):
> I'm working on UDGAM, SIH 2026 PS 26143. Here is the master plan and my personal task document. I'm starting Phase N. Explain what this phase produces, walk me through it step by step, and tell me what to check before I move on. Don't write the full code — I'll get that from Claude Code.
>
> [paste 00_MASTER_PLAN.md §2–4 + your personal doc]

**Opening a driver chat:**
> [in the repo, CLAUDE.md is read automatically]
> Phase N, step 1: write `pipeline/<x>/<file>.py` that does <one thing>. It must write output matching the schema in docs/CONTRACTS.md. Follow the frozen conventions in CLAUDE.md.

---

## 2. The ten rules that save the most tokens

1. **Fresh chat per bug.** Every turn resends the whole thread. A 40-turn debugging thread costs more than the entire component did. When a bug is fixed, close the chat.
2. **One file or one function per request.** "Build the drift module" produces 400 lines you can't verify. "Write `get_uv(lons, lats, time)` that bilinearly interpolates the cached HYCOM array" produces 30 lines you can test.
3. **Paste the error, not the file.** Exact traceback + the function that failed. Not the repo, not the whole file, not a screenshot description.
4. **Never paste large data.** Paste `df.head()`, `arr.shape`, `arr.dtype`, `arr.min()/.max()` — five lines that describe a gigabyte.
5. **Ask "what's wrong" before "rewrite this."** Diagnosis is cheap; regeneration is expensive and often reintroduces fixed bugs.
6. **Don't ask it to re-explain the project.** That's what the pasted docs are for.
7. **Boilerplate goes to Codex/Antigravity.** Loaders, argparse, file I/O, React scaffolding, CSS. Save Claude for reasoning about why something is wrong.
8. **Reserve ~half your Claude quota for Tue–Wed.** Integration and debugging is where a good model is worth most. Sunday scaffolding is not.
9. **Stop re-prompting a stuck model.** Three attempts without progress means the problem is your framing, not its output. Change the question or go to the navigator.
10. **Don't ask for tests you won't run.** Ask for the four known-answer tests that are specified, then actually run them.

---

## 3. What to do when generated code runs but is wrong

This is the real risk on this project, not syntax errors. Geospatial code fails silently and confidently.

**Symptom → first suspect:**
| What you see | Look here first |
|---|---|
| Everything is 1000x or 0.001x off | Units. HYCOM on GEE is int × 0.001 m/s (÷1000, not ÷100). Metres vs km vs degrees. |
| Result is mirrored or rotated 90° | `[lat, lon]` vs `[lon, lat]`. |
| Everything is on land / in the wrong hemisphere | Longitude convention 0–360 vs −180–180, or a sign flip. |
| Off by exactly 5.5 hours, or 5:30 | Local time crept in. Everything is UTC with `Z`. |
| Image is black or white | dB clamp range wrong before the 8-bit scale. |
| Array shapes disagree by one | Row-major vs column-major, or north-up vs south-up row ordering. |

**The habit that catches all of these:** after every generated function, print or plot ONE concrete thing and ask yourself whether a physical object could behave that way. A ship does not move 1,800 km in a day. A slick is not 40,000 km². An ocean current is not 90 m/s.

**Ask the driver this exact question when unsure:**
> Before I run this, list every assumption you made about units, coordinate order, time zone, and array orientation. For each one, tell me the single line of code that would prove it right or wrong.

---

## 4. Phase discipline

Every phase in every personal document ends in a **checkpoint that produces an artefact** — a green test, a plot, a valid file, a screenshot. That is deliberate.

- Do not start the next phase until the checkpoint artefact exists and you have looked at it.
- Post the artefact in the group. It takes ten seconds and it is how Akshat knows where everyone is without asking.
- If a checkpoint fails, that is a good day — you found the problem early, which is the entire point of ordering the phases this way.

---

## 5. Handover protocol (so switching AI costs nothing)

After each phase, append to `docs/updates/<yourname>.md` using `docs/updates/TEMPLATE.md`. Four lines. It takes two minutes and it means:
- a fresh chat can resume your work from the file instead of from your memory,
- if you switch from Claude to ChatGPT mid-task, nothing is lost,
- if you're asleep and something breaks, Akshat can read what state you left it in.

**To resume from an update file:**
> Here is the master plan, my task document, and my update log. Read the log and tell me exactly where I left off and what the next step is.

---

## 6. Quota triage if you hit a wall

1. Switch that task to Codex or Antigravity — with `CLAUDE.md` pasted in, they follow the same rules.
2. Borrow: Akshat holds two Claude accounts; a third arrives on the 8th.
3. Downgrade the ask: get the driver to write a *skeleton with TODOs* and fill the middle yourself.
4. Escalate to Akshat rather than silently stalling. A blocked person nobody knows about is the expensive failure.

**Never** paste secrets, GEE credentials or account tokens into any chat.

---

## 7. Team-wide daily rhythm

- **21:30 sync, 15 minutes, everyone.** Three sentences each: done / blocked / next. Nothing else.
- Post checkpoint artefacts in the group as they happen, not at the sync.
- Jaiveer posts an end-of-day written update regardless, because nobody can see his screen.
- Anything that changes a contract, a deadline, or a cut decision goes through Akshat and gets broadcast to everyone. Silent local changes to shared shapes are how six people end up with five different projects.
