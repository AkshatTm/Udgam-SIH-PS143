# SOUM — Start Here
*Read this before you write any code. Simple language. About 45 minutes of setup, plus a download running in the background.*

---

## 1. What is your job, in simple words

You find the oil in the satellite photo.

A radar satellite photo of the sea looks like grey TV static. Oil makes the water smooth, and smooth water looks **dark** in these photos. So finding oil means finding dark patches.

The problem: many other things also look dark. Calm wind areas. Algae. Rain. These are called **look-alikes**. Telling real oil apart from look-alikes is the hard part, and it is hard for everybody in the world, not just us.

**Your solution is in two steps:**
1. Find every dark patch in the photo. (Simple image processing, no AI training.)
2. For each dark patch, measure a few numbers — how long and thin it is, how sharp its edges are, how much darker it is than the sea around it. Then a small program looks at those numbers and says "oil" or "look-alike."

Real oil dumped by a moving ship is **long and thin with sharp edges**. Algae is **rounded with soft, fuzzy edges**. The numbers capture that difference.

## 2. Very important: you are NOT training a deep learning model

We decided to skip the CNN this week. Do not start it. It needs 40 GB of downloads, many hours of setup, and we do not have the time.

**Also, our way is better for the demo.** Because we use measured numbers, we can show a judge a small bar chart saying "we said oil because it is 8 times longer than it is wide, and its edges are sharp." A neural network cannot explain itself like that. This is a selling point, not a compromise.

The big dataset is still downloading in the background for October. That is separate.

## 3. What you will make

| Thing | In simple words |
|---|---|
| Dark patch finder | Looks at a photo and draws outlines around every dark area |
| Number measurer | For each outline, measures length/width ratio, edge sharpness, darkness |
| Training table | A spreadsheet: one row per patch, the measured numbers, and whether it was really oil |
| Classifier | A small program trained on that table, that guesses oil or look-alike |
| `detections.geojson` | Your final output file, given to Akshat on Tuesday evening |

## 4. Set up your computer

### Step A — Check your disk space FIRST (2 min)
You need about **25 GB free**. The download is 9.9 GB and unzipping it needs the same again.
If you do not have space, clear it now or tell Akshat before you start.

### Step B — Start the download NOW (5 min to start, hours to finish)
Go to: `zenodo.org/records/13761290`
Download the single file `02_Test_images_and_ground_truth.7z` (9.9 GB).
Save it inside your project folder under `data/`.

**Do this before anything else.** It runs by itself while you do the rest of the setup.

You will need **7-Zip** to unzip it (7-zip.org on Windows, `brew install p7zip` on Mac).

**What is inside:** 450 real satellite photos. 150 have real oil, 150 have look-alikes, 150 have plain sea. Each photo comes with a "mask" — a black-and-white image showing exactly which pixels are oil. Scientists made these masks. That is how you get correct answers to train on, without hand-labelling anything.

### Step C — Install the basics (15 min)
1. Install **Python 3.11** from python.org (tick "Add Python to PATH" on Windows).
2. Install **Git** and **VS Code**.
3. Then:
```bash
git clone <repo-url> naap
cd naap
git checkout -b soum
python -m venv venv
```
Turn on the environment (do this in every new terminal):
- Windows: `venv\Scripts\activate`
- Mac/Linux: `source venv/bin/activate`

```bash
pip install numpy scipy opencv-python scikit-image scikit-learn rasterio shapely pillow matplotlib earthengine-api
```

### Step D — Google Earth Engine (15 min)
You need this later to read the Ennore photo Akshat gives you.
1. Sign up at `earthengine.google.com` with your student Google account, choose noncommercial use.
2. Run `earthengine authenticate` and follow the browser.

### Step E — Check it works (5 min)
```bash
python scripts/make_case000.py
python scripts/validate_case.py cases/case-000
```
Must print **PASS**.

## 5. Your first real task, in order

**Task 1 (today):** While the download runs, write a tiny script that opens ONE photo from the dataset and shows it on screen. Confirm the numbers inside are around −25 to 0 (these are decibels, a way of measuring radar brightness). If you can open one photo and see grey static with a dark patch, you are ready.

**Task 2 (today):** Write the "fake output" script. It produces a `detections.geojson` file with made-up numbers but the correct shape. Run the checker on it. This proves the connection to Akshat works before you build anything real.

**Task 3 (Monday):** Build the dark patch finder. Then **post 3 pictures in the group** showing your outlines drawn over real oil photos. If the outlines sit on the dark patches, you are on track. This picture is your checkpoint — do not move on without it.

**Task 4 (Monday):** Build the number measurer, then run everything over all 450 photos to build your training table.

**Task 5 (Tuesday):** Train the classifier. Then run it on the real Ennore photo from Akshat and give him `detections.geojson`. **This is your hard deadline: Tuesday evening.**

## 6. One rule that matters a lot

When you test how good your classifier is, **split by photo, not by row.**

Why: many dark patches come from the same photo, and patches from one photo look similar. If you mix them between training and testing, your score looks great but is fake. A judge could take that apart in one question. Split so that no photo appears in both training and testing.

Whatever score you get — even if it is not great — that is the number we tell the judges. Being honest about a hard problem is stronger than claiming a perfect one.

## 7. How you use AI

Until 8 September: **Codex and Antigravity.** This work is normal image processing and they handle it well. From the 8th: your own Claude Pro, mostly for fixing bugs.

**Start a new chat for each new bug.** Long chats waste your limit.

**How to start:**
> Read CLAUDE.md and docs/02_SOUM_DETECTION.md. I am on Phase 2. Write the dark spot detector: adaptive threshold on a decibel image, then morphological cleanup, then connected components, returning contours.

**What the AI does:** all the code.
**What YOU do:** look at the pictures and judge whether they make sense. Are the outlines on the dark patches? Is the length/width ratio between 1 and 15 (never below 1)? Is the darkness number negative? The AI cannot tell you if a result is physically silly. You can.

## 8. Your checklist before Phase 1

- [ ] 25 GB free disk confirmed
- [ ] Zenodo Part III download started
- [ ] 7-Zip installed
- [ ] Python, Git, VS Code working
- [ ] Repo cloned, branch `soum` created, venv on, packages installed
- [ ] Earth Engine authenticated
- [ ] Checker prints PASS on the fake folder
- [ ] You have opened one dataset photo and seen it

## 9. If you get stuck
45 minutes on the download, unzipping, or Earth Engine → message Akshat with the exact error text. Everything else, push through yourself with the AI.

You live with Akshat, so most problems are a two-minute conversation. Use that.
