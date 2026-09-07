# ANUSHKA — Start Here
*Read this before you write any code. Simple language. About 40 minutes of setup. You need NO GPU and NO big downloads.*

---

## 1. What is your job, in simple words

You run time backwards.

Soum finds an oil patch in a satellite photo taken at, say, midnight. But the oil did not appear there. It was dumped somewhere else, hours earlier, and then the ocean carried it.

Your job: take the oil patch, and calculate where it came from.

**How:** oil floating on the sea moves with two things — the ocean current, and the wind pushing on the surface. Scientists found that oil moves at the current speed, plus about 3% of the wind speed. That is the whole physics.

So you put 3000 imaginary dots on the oil patch. Then you step time backwards, 15 minutes at a time, moving each dot against the current and wind. After 96 backward steps (stored as 97 positions, including the start) you have gone back 24 hours, and the dots have gathered near where the oil started.

**The most important part:** you do this 50 times, each time changing the numbers slightly (maybe the wind effect was 2.5%, maybe 3.5%). The 50 answers spread out. That spread IS your honest uncertainty. You never give one exact point — you give a cloud, and it gets wider the further back you look. That is physically true, and saying so is what makes judges trust us.

**No AI, no machine learning, no training in your part.** It is pure physics and maths.

## 2. What you will make

| Thing | In simple words |
|---|---|
| Field reader | Downloads ocean current speed and wind speed for our area and dates |
| Stepper | Moves the dots one time-step, forwards or backwards |
| Tests | Four checks that prove your maths is right |
| `particles.json` | Where every dot was at every time-step — this drives the slider animation |
| `origin.json` | The cloud showing where the oil probably started, and when |

## 3. Set up your computer

### Step A — Install the basics (15 min)
1. Install **Python 3.11** from python.org (tick "Add Python to PATH" on Windows).
2. Install **Git** and **VS Code**.
3. Then:
```bash
git clone <repo-url> naap
cd naap
git checkout -b anushka
python -m venv venv
```
Turn on the environment (needed in every new terminal):
- Windows: `venv\Scripts\activate`
- Mac/Linux: `source venv/bin/activate`

```bash
pip install numpy scipy matplotlib earthengine-api pillow
```

### Step B — Google Earth Engine (20 min, do this early)
This is a free Google website that stores ocean and weather data. We get everything from there instead of downloading huge science files.

1. Sign up at `earthengine.google.com` with your student Google account. Choose **noncommercial / research**. Note your project ID.
2. Run:
```bash
earthengine authenticate
```
A browser opens, log in, paste the code back.

Approval is usually quick but can take a few hours. **Start it first thing**, then do everything else while you wait — your first task does not need it.

### Step C — Check it works (5 min)
```bash
python scripts/make_case000.py
python scripts/validate_case.py cases/case-000
```
Must print **PASS**.

## 4. Your first task — and it needs NO data at all

This is the smart part of your plan. You build and test the whole physics engine using made-up numbers first.

**Make a fake ocean.** Write code that pretends the current is exactly 0.5 metres per second flowing east, everywhere, always. No wind. It is not real, but you know exactly what should happen.

**Then write four tests:**

1. **Straight line test.** One dot, fake eastward current, 10 hours. It must end up **18 kilometres east**. (0.5 m/s × 36000 seconds = 18000 metres.)
   - If you get 18,000 km, your units are wrong.
   - If it went north, you mixed up east and north.
   - If it went west, you have a minus sign wrong.

2. **Round trip test.** Move a dot forward 24 hours, then move it backward 24 hours. It must come back to where it started, within half a kilometre.
   - **This is the most important test.** It proves your backwards mode works. Backwards is the whole point of your component, and mistakes here produce answers that look fine but are wrong.

3. **Wind test.** No current, wind of 10 m/s. The dot must move at 0.3 m/s (3% of 10).

4. **Sanity limits.** Add permanent checks: no dot ever moves faster than 3 m/s, and over 48 hours a dot travels between 5 and 200 km. If these ever fail, something broke.

**Post your test results in the group when all four pass.** That is your checkpoint for today.

## 5. The one bug that will definitely happen

The ocean current data from Google is in **centimetres per second**, not metres per second.

If you forget to divide by 100, your dots will fly hundreds of kilometres and the whole answer is nonsense. It will not crash. It will just be silently wrong.

Test 4 above catches it automatically. That is exactly why you write the tests first.

Two smaller versions of the same trap:
- Wind data comes as two numbers (east amount, north amount), not as "speed and direction". Do not let the AI convert to compass directions.
- Locations are always written **[longitude, latitude]** — the sideways number first, then the up-down number. Everyone's instinct is the opposite. Getting it backwards puts Ennore in the middle of nowhere.

## 6. How you work through the week

| Day | What you do | You are done when |
|---|---|---|
| Today | Fake ocean + four tests | All four tests pass, posted in group |
| Monday | Real current and wind data from Google | You draw an arrow map of the ocean and the arrows look sensible |
| Tuesday | Backwards mode + 50 runs + write the files | You have a heat map picture, and Akshat has your two files |
| Wednesday | Spare day, fix anything broken | — |

**Tuesday evening is your hard deadline.** Akshat needs `particles.json` and `origin.json` to build the demo.

**Every step ends in a picture or a test result.** This is on purpose. Wrong code that still runs is the danger in this component, and looking at a picture catches it in ten seconds.

## 7. How you use AI

You have Claude Pro. Use it as your main tool.

**Use a separate fresh chat for each of the four phases above.** Do not use one giant chat for everything — it wastes your limit and confuses the AI.

**How to start a chat:**
> Read CLAUDE.md and docs/03_ANUSHKA_DRIFT.md. I am on Phase 1. Write the fake constant field and the RK2 stepper, plus the four known-answer tests described in the doc.

**Useful question when you are unsure:**
> Before I run this, list every assumption you made about units, coordinate order, and time zone. For each one, tell me the single line of code that would prove it right or wrong.

**What the AI does:** all the code, including the tests.
**What YOU do:** run the tests, look at the pictures, and ask "could the real ocean do this?" A sea current is never 90 m/s. A dot never travels 1800 km in a day.

## 8. Your checklist before Phase 1

- [ ] Python, Git, VS Code working
- [ ] Repo cloned, branch `anushka` created, venv on, packages installed
- [ ] Earth Engine sign-up started (you can begin Phase 1 while waiting)
- [ ] Checker prints PASS on the fake folder
- [ ] You have read section 5 of this document twice

## 9. If you get stuck
Google Earth Engine is the only part likely to fight you, and it is not your fault when it does. **Stuck for 45 minutes on it → message Akshat immediately** with the exact error. Do not spend an evening on it.

Everything else, push through with the AI. Harshita is with you if you want a second pair of eyes.
