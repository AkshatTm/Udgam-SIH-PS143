# JAIVEER — Start Here
*Read this before you write any code. Simple language. About 40 minutes of setup, plus a download in the background.*

---

## 1. What is your job, in simple words

You find the ship that did it.

Anushka's part tells us roughly where the oil started, and roughly when. Your job is to answer: **which ships were in that area at that time, and which one is most likely responsible?**

Big ships broadcast their position over radio every few minutes. This is called **AIS** — like a car number plate that keeps announcing itself. The American coast guard publishes years of these broadcasts for free, for anyone to download.

So you take the origin cloud and time window, look at every ship in that area, and score them.

**Nothing in your part uses AI or machine learning.** It is filtering, matching, and a weighted score. Every number is explainable, which is exactly what we want — we can tell a judge precisely why a ship ranked first.

## 2. Why your part matters more than it looks

The problem statement is literally named after this. "Identify vessel responsible for the spill." Detection and drift are the setup. **Your part is the punchline of the demo** — the moment a judge sees a named ship on screen.

## 3. What makes a ship look guilty

You give each ship a score from five signals:

| Signal | Meaning | Weight |
|---|---|---|
| Closeness | Was it inside the origin cloud during the time window? | 40% |
| Direction | Was it heading in a way consistent with being the source? | 20% |
| Slowdown | Did it slow down unusually? Ships often slow while dumping. | 15% |
| Radio gap | Did its transponder go silent during the window and come back after? | 15% |
| Ship type | Tankers and cargo ships are more likely than passenger ferries | 10% |

Then you show three things on screen:

**The funnel** — 412 ships in the region → 63 in the time window → 12 close enough → 3 scored. Those four numbers are the "filter out irrelevant traffic" requirement, made visible.

**Three suspect cards** — each with its score, how close it got, and short plain-English reasons.

**At least one excluded ship** — "this ship was nearby but was heading away the whole time, so we ruled it out." This matters more than it sounds. It shows we narrow down honestly instead of just accusing whoever is closest.

## 4. Your situation is different from everyone else's

You live far away. That is fine, because **your part needs nothing from anybody.**

You need an origin cloud, and Akshat gives you a fake one today. You build everything against that. When the real one arrives during the hackathon, you swap the file and rerun. No code changes.

**But there is a catch.** Because nobody can see your screen, nobody knows if you are stuck. So:

**Post a short update in the group every single evening.** Three lines: what you did, what is blocking you, what is next. Even on a bad day. Silence makes people worry, and worry makes them start duplicating your work.

**Your deadline is the 11th, not the 9th.** The Wednesday demo (Ennore) has no ships, because free ship data does not exist for Indian waters. So you have more time than the others. Use it well, do not use it to start late.

## 5. Set up your computer

### Step A — Install (15 min)
1. **Python 3.11** from python.org (tick "Add Python to PATH" on Windows).
2. **Git** and **VS Code**.
3. Then:
```bash
git clone <repo-url> naap
cd naap
git checkout -b jaiveer
python -m venv venv
```
Turn on the environment (every new terminal):
- Windows: `venv\Scripts\activate`
- Mac/Linux: `source venv/bin/activate`

```bash
pip install pandas geopandas shapely duckdb pyarrow matplotlib numpy
```

### Step B — Start a ship-data download (10 min to start)
Go to: `coast.noaa.gov/htdata/CMSP/AISDataHandler/`

No sign-up, no account, completely free and public.

Pick any few days from 2023 to begin with — you are just building the machinery, and you will swap in the real days once Akshat picks the case on Monday. Each day is roughly 1–3 GB zipped.

Save under `data/ais/`. This folder is ignored by Git — **never commit ship data. It stays on your laptop. Only your finished output files travel to the team.**

### Step C — Check it works (5 min)
```bash
python scripts/make_case000.py
python scripts/validate_case.py cases/case-000
```
Must print **PASS**.

## 6. The one mistake that will break your laptop

**Do not open the whole ship file with pandas.**

```python
df = pd.read_csv("AIS_2023_06_14.csv")   # DON'T — your laptop will freeze
```

These files have tens of millions of rows. Instead, filter as you read:
- Read in chunks and keep only rows inside your map area and time window, or
- Use DuckDB to read the CSV with a WHERE clause directly.

Then save the small filtered result as a **Parquet** file. After that, every query is instant. You do this expensive step once, ever.

## 7. Two more things to watch

**Do not build ship identity logic.** Ships have an ID number called MMSI. It is imperfect — sometimes reused, sometimes fake. Do not try to fix that. Group by MMSI, drop ships with fewer than 5 position reports, move on. We have one demo case; this is not worth solving.

**Do not fill in long radio gaps.** If a ship went silent for 3 hours, do not draw a straight line through the gap and pretend you know where it was. That invents a position that never happened, and then you might score it as a suspect. Only fill gaps under about 30 minutes. **A long gap is the evidence you are looking for, not a hole to patch.**

## 8. The honesty rule

Every ship name and number you put on screen must come from the real downloaded file. If the ship from the documented accident does not come out in your top 3, **that is the result we show and discuss.** We never adjust the weights to force the "right" answer.

This is not just ethics. Whatever we present in September, we defend in December in front of a national panel. A forced result would fall apart there.

Our closing line is "leads, not verdicts." The system narrows a field for a human investigator. It never decides.

## 9. Your week

| Day | What you build | You are done when |
|---|---|---|
| Today | Reading and filtering ship data, rebuilding paths | You post a picture of ~50 ship paths that look like real shipping |
| Monday | The scoring program, using the fake origin cloud | Funnel numbers go down sensibly |
| Tuesday | Write the two output files, run the checker | Checker prints PASS |
| Wed | Swap in real data for the US case once Akshat picks it | — |
| Thu–Fri | Connect to the real origin cloud, finish suspect + exclusion cards | Akshat has your final files |

## 10. How you use AI

You have Claude Pro and Codex.

**Start a new chat for each new bug.**

**How to start:**
> Read CLAUDE.md, pipeline/attribute/CLAUDE.md and docs/05_JAIVEER_AIS.md. I am on Phase 1. Write the AIS ingest script that filters a NOAA CSV to a bounding box and time window while reading, then writes Parquet.

**What the AI does:** all the code.
**What YOU do:** look at the results and judge them. Do the ship paths look like real ships — smooth lines along the coast, not jumping around? Do the funnel numbers get smaller each step? Read the top suspect's reasons out loud — does the story make sense? If your number one suspect is a fishing boat that never came near the origin, something is broken. Find it before a judge does.

## 11. Your checklist before Phase 1

- [ ] Python, Git, VS Code working
- [ ] Repo cloned, branch `jaiveer` created, venv on, packages installed
- [ ] Ship data download started
- [ ] Checker prints PASS on the fake folder
- [ ] `docs/updates/jaiveer.md` created
- [ ] You have posted your first evening update in the group

## 12. If you get stuck
45 minutes on the download or the data format → message Akshat with the exact error.

Because you are remote, **ask earlier than feels necessary.** A quick question costs five minutes. A silent stuck day costs the project.
