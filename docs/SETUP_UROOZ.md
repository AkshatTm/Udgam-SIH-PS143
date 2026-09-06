# UROOZ — Start Here
*Read this before you start. Simple language. About 20 minutes of setup. You need NO Python, NO coding environment, NO downloads.*

---

## 1. What is your job, in simple words

You decide how the whole thing looks.

Five people are building programs that produce correct answers. Correct answers presented badly still lose. **You are the difference between "college assignment" and "national competition entry."**

Right now, nobody on the team is qualified to make design decisions except you. That is not a small role given to you because there was nothing else. It is the role only you can do.

## 2. What makes your job hard here

Everything sits on top of a **dark grey satellite radar photo** that looks like TV static. On that background you must make five different kinds of information readable at the same time:

- Oil patches
- Look-alike patches that are NOT oil
- 3000 moving dots
- A heat map cloud
- Ship paths, with one highlighted as the top suspect and one crossed out as ruled out

And a judge must understand all of it **from the back of a room, on a projector, in five minutes, having never seen it before.**

That is a real design problem.

## 3. What you will make

| Thing | In simple words |
|---|---|
| Colour and font guide | A short document telling Harshita exactly which colours and fonts to use |
| Four quiz pictures | Four small satellite images for the opening trick (see below) |
| Card designs | How the information panels look — spacing, sizes, layout |
| The slide deck | About 10 slides for the pitch |
| Demo checklist | A paper list of every click, so we can test nothing is broken |

## 4. The four quiz pictures — your most fun task

We open the demo with a trick. We show the judges four small dark satellite patches and say:

*"One of these is an oil spill. The others are calm wind, algae, and a rain cell. Which one is the oil?"*

They will guess wrong. **That is the point.** It proves the problem is genuinely hard before we tell them our accuracy numbers, so a modest number sounds impressive instead of weak.

**Your job:** pick the four pictures. Soum will give you a folder of about 20 real satellite images from a scientific dataset — some really are oil, some really are look-alikes.

**The test of a good choice:** if YOU can instantly tell which one is oil, it is a bad set. Pick ones where even you have to think.

Then export them as four square images, all with the same brightness setting, no labels or hints on the picture. Also write a small note saying which one is the oil and the one-line reason why (it is long and thin, its edges are sharp).

## 5. Set up (20 minutes)

You do not need a coding environment. You need to see the app and make files.

### Step A — See what the team is building (5 min)
Ask Harshita to share her screen or send screenshots once a day. That is your material.

If you want to run it yourself later, ask her to walk you through it — but it is not required.

### Step B — Your design tools (10 min)
Use whatever you already know — Figma, Canva, Illustrator, whatever you are fastest in. **Do not learn a new tool this week.**

For colours, one useful rule: use a **colour-blind-safe** palette. Around 8% of men cannot distinguish red from green, and there may well be a judge in that group. If our "oil" and "safe" colours only differ by red versus green, that judge sees nothing. Ask ChatGPT for a colour-blind-safe palette and check it with an online simulator.

### Step C — Where your files go (5 min)
You do not need Git if you do not want it. Send files to Harshita and Akshat directly, or use a shared Drive folder. If you do want Git, ask Harshita for ten minutes and she will set it up.

## 6. Your week

| Day | What you do | Time |
|---|---|---|
| Today | Colour and font guide | ~2 hours |
| Monday | The four quiz pictures | ~2 hours |
| Tuesday | Sit with Harshita, style the cards and panels | ~2 hours |
| Wednesday | Look at the app as a stranger, list what is unclear | ~1 hour |
| Thu–Fri | The slide deck | ~4 hours |
| Before the end | Write the click-by-click demo checklist | ~30 min |

You have about two hours a day after classes. That is enough for all of this if you do the tasks in this order.

## 7. How to make the colour guide (your first task)

Write a simple document with:

**Colours for:**
- Oil detection outline — must shout, this is the star of the show
- Look-alike outline — must clearly say "not important," use dashes and grey
- The moving dots — one bright warm colour
- The origin heat map — one colour going from dark to bright
- Ship paths — a cool colour, with the top suspect standing out
- **A ruled-out ship** — this should look visually "cancelled." A crossed-out or faded style. This is a small detail that says a lot about the system being fair.
- Panel backgrounds, main text, secondary text, one accent colour

**Rules to follow:**
- At most **3 loud colours** on the map at once. Everything else quiet. Too many colours is the most common design mistake and it makes screens unreadable.
- Two fonts maximum — one for headings, one for everything else. Free Google Fonts only.
- On the app, text at 14 pixels or bigger. On slides, 20 point or bigger.

**Test your guide like this:** take Harshita's screenshot, shrink it to 30% size, and squint at it. Can you still instantly tell oil from look-alike? If not, the colours are not different enough.

## 8. Rules for the slide deck (later in the week)

- One idea per slide. If a slide needs a paragraph, it is two slides.
- **Use real screenshots of the actual app**, never mockups. Judges can tell.
- One slide shows our honest accuracy numbers. **Design it as confidently as the good slides.** Being open about a hard problem is a strength, and it should not look like an apology.
- One slide gets this sentence alone, big: *"INCOIS tells the Coast Guard where the oil is going. Nobody tells them where it came from. We built the other half."*
- One slide lists where our data came from. Akshat has the exact text — the dataset we use requires us to credit its authors, so this is not optional.

## 9. How you use AI

You have ChatGPT and Antigravity.

**Use ChatGPT as an advisor, not a decision maker.** Ask it for colour palette options, font pairings, examples of good dashboard layouts, or to draft slide structure. Then **you** choose. Design taste is your job; it does not have any.

Good things to ask:
> Suggest three colour-blind-safe palettes for highlighting a bright object on a dark grey satellite image background.

> I am designing an information card showing five measured numbers with small bar charts. Suggest three layouts that stay readable when projected.

**Use Antigravity** if you want to try small styling changes yourself. But the main way you work is: you decide, Harshita implements.

## 10. Your checklist before you start

- [ ] You have seen a screenshot of what Harshita is building
- [ ] You have your design tool open and ready
- [ ] You have read section 7 and know what your first document contains
- [ ] You have asked Soum to send you sample satellite images when he can
- [ ] You know when Harshita is free each day for the two-hour styling session

## 11. If something needs to change in the data
Sometimes a design problem cannot be solved with colours. For example, if the heat map has no contrast because the underlying numbers are too flat. **Tell Akshat.** Do not work around it. Changing the data is his job, and a real fix beats a visual patch.

## 12. One last thing
On demo day, your job is to **watch the judges' faces** while Akshat is talking. If they look lost, signal him. Nobody else will be able to — they will all be watching the screen.
