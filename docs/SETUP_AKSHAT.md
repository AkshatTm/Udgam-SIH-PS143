# AKSHAT — Start Here
*Read this before you write any code. Simple language. About 60 minutes of setup.*

---

## 1. What is your job, in simple words

You are the **plumber**, not a builder.

Five people are each building one machine. Your job is to make sure all five machines fit together and pass their work to the next one correctly. You also make the fake sample files that let everyone start working today, before any real machine exists.

Think of it like this: everyone else cooks one dish. You lay the table, decide what plate each dish goes on, and make sure the meal arrives together.

**You must always keep some free time.** If Soum's work breaks on Tuesday night, you are the one who fixes the connection. If you are busy building your own thing, nobody can help.

## 2. What you will make

| Thing | In simple words |
|---|---|
| Rules file | A short list saying "everyone must write dates and locations in THIS exact way" |
| Fake sample folder | Made-up files in the correct shape, so others can build against them today |
| Checker script | A program that reads someone's file and says PASS or tells them what is wrong |
| Satellite picture | Download the real radar photo of Ennore from Google, save as an image |
| Assembler | Collects everyone's finished files into one folder |
| The demo | Wire it all together Wednesday morning and present it |

## 3. Set up your computer

### Step A — Install the basics (15 min)
1. Install **Python 3.11** from python.org. During install on Windows, tick "Add Python to PATH".
2. Install **Git** from git-scm.com.
3. Install **VS Code** from code.visualstudio.com.
4. Check both work. Open a terminal and type:
```bash
python --version
git --version
```
Both should print a version number. If not, restart your computer and try again.

### Step B — Make the project folder (10 min)
```bash
git clone <your-repo-url> naap
cd naap
python -m venv venv
```
Then turn on the virtual environment:
- Windows: `venv\Scripts\activate`
- Mac/Linux: `source venv/bin/activate`

You will see `(venv)` at the start of your terminal line. **Every time you open a new terminal, you must do this again.**

```bash
pip install numpy scipy rasterio geopandas shapely opencv-python scikit-image scikit-learn earthengine-api pillow pyarrow duckdb
pip freeze > requirements.txt
```

### Step C — Google Earth Engine (20 min, do this FIRST because approval can take time)
Google Earth Engine is a free website that stores satellite photos, ocean water speed, and wind data. We get everything from there instead of downloading big files.

1. Go to `earthengine.google.com`, click Sign Up, use your student Google account.
2. Choose **noncommercial / research** use. Note down your project ID.
3. In your terminal:
```bash
earthengine authenticate
```
A browser opens. Log in. Copy the code back into the terminal.

### Step D — Put the files in place (10 min)
Copy the documents I gave you into the folder like this:
```
naap/
  CLAUDE.md                 (file 07)
  docs/                     (files 00 to 06, 09, 11, 12, 13)
  docs/updates/TEMPLATE.md  (file 10)
  scripts/validate_case.py
  scripts/make_case000.py
```

Then test that everything works:
```bash
python scripts/make_case000.py
python scripts/validate_case.py cases/case-000
```
You should see **PASS**. If you see PASS, your computer is ready and so is everyone else's who copies these steps.

## 4. The very first thing you do (tonight, 1 hour)

**Check that a satellite photo of Ennore exists.**

The whole plan assumes a satellite passed over Ennore around 28 January 2017. If it did not, we must change the plan tonight, not on Monday.

Make a file `check_ennore.py`:
```python
import ee
ee.Initialize(project="YOUR-PROJECT-ID")

area = ee.Geometry.Rectangle([80.0, 12.9, 80.8, 13.6])
scenes = (ee.ImageCollection("COPERNICUS/S1_GRD")
          .filterDate("2017-01-28", "2017-02-08")
          .filterBounds(area))
print("Number of photos found:", scenes.size().getInfo())
for s in scenes.limit(10).getInfo()["features"]:
    print(s["id"])
```

Run it. What the answer means:
- **A photo within 3 days of 28 Jan** → perfect, continue with the plan.
- **Only a later photo** → still fine. We say "this was the first satellite pass after the accident." That gap is actually why our project exists.
- **Zero photos in 10 days** → stop. Message me (Claude) before changing anything. We switch to a different case.

Write down the photo ID in `docs/receipts.md`. Judges may ask "is this real?" and you must be able to show the exact ID in five seconds.

## 5. Then send three messages

Once the check passes:
1. **Soum** — start downloading Zenodo Part III (9.9 GB) now.
2. **Harshita** — start the map screen now, using the fake folder.
3. **Anushka** — start the physics tests now, no data needed.

None of these three need to wait for anything else.

## 6. How you use AI

You have two Claude accounts, one more coming on the 8th, plus Antigravity and Codex.

**Save half your Claude usage for Tuesday and Wednesday.** That is when things break and when a good AI helps most. Use Codex and Antigravity for simple, boring code before then.

**Start a new chat for every new bug.** Long chats resend the whole conversation every time and waste your limit fast.

**How to start a chat with Claude Code:**
> Read CLAUDE.md and docs/01_AKSHAT_INTEGRATION.md. I am on Phase 2. Write the GEE export script that downloads the Ennore scene as a PNG plus a bounds file.

## 7. Your checklist before Phase 1

- [ ] Python, Git, VS Code installed and working
- [ ] Repo cloned, venv working, packages installed
- [ ] Earth Engine account approved and authenticated
- [ ] `make_case000.py` and `validate_case.py` both run and print PASS
- [ ] Ennore photo check done, ID written in receipts.md
- [ ] Three start messages sent
- [ ] All documents copied into `docs/`

## 8. If you get stuck
You are the person others come to. When YOU get stuck for more than 45 minutes on Earth Engine or any Google service, come back to this Claude chat with the exact error message.

**Rule for everyone else:** when someone hands you a broken file, do not fix it yourself. Run the checker, send them the error, let them fix their own code. If you fix it, the same bug comes back tomorrow at a worse time.
