# HARSHITA — Start Here
*Read this before you write any code. Simple language. About 30 minutes of setup. You need NO Python, NO Earth Engine, NO downloads.*

---

## 1. What is your job, in simple words

You build the only thing the judges actually look at.

Everyone else writes programs that produce numbers in files. Those files mean nothing to a judge. **Your screen is what turns their work into something a person can understand in five minutes.**

This is not "the frontend part" or support work. It is the deliverable. It is also the biggest single piece of work in the whole project.

## 2. What you are building

**One screen.** Not three pages. One map, with a slider under it.

- Middle: a map showing the satellite radar photo of the sea
- On top of the map: layers you can switch on and off — oil outlines, moving dots, a heat map, ship paths
- Left: three stage buttons (Detect, Trace, Attribute)
- Right: an information panel that changes depending on which stage is active
- Bottom: **the time slider**

**The slider is the centrepiece of the entire project.** The judge drags it backwards, and 3000 dots unwind across the sea, spreading out as they go further back in time, until they gather where the oil came from. Then we hand the judge the mouse and let them do it themselves.

If that one interaction feels smooth, we win the round. If it stutters, everything else stops mattering.

## 3. The most important thing to understand

**You never talk to Python. Ever.**

Everyone else's programs write plain data files into a folder. Your app just reads those files, like reading a JSON from any API.

```
cases/case-000/
  meta.json            information about this case
  sar.png              the satellite photo
  bounds.json          where on Earth that photo sits
  detections.geojson   the oil outlines
  particles.json       where all 3000 dots are at every time step
  origin.json          the heat map grid
  vessels.geojson      ship paths
  suspects.json        the ranked list of suspect ships
```

**This means you never wait for anyone.** Akshat gives you a folder of fake files today. You build the entire app against them. When the real files arrive on Tuesday, they have exactly the same shape, and your app just works.

If a file is missing or in the wrong shape, that is a bug in someone else's program. Show an error on screen and tell Akshat. **Never quietly fix their data inside your code** — it hides the bug until demo day.

## 4. Set up your computer

### Step A — Install (10 min)
1. **Node.js 20** from nodejs.org (choose the LTS version).
2. **Git** and **VS Code** if you do not have them.
3. Check:
```bash
node --version
git --version
```

### Step B — Get the project (5 min)
```bash
git clone <repo-url> naap
cd naap
git checkout -b harshita
```

### Step C — Make the app (10 min)
```bash
npx create-next-app@latest web
cd web
npm install maplibre-gl deck.gl @deck.gl/mapbox @deck.gl/layers zustand recharts
npm run dev
```
Open `localhost:3000`. You should see the starter page.

**Decide today: Next.js or Vite. Then never change it.** Both are fine. Switching mid-week costs a day you do not have.

### Step D — Get the fake data (5 min)
Ask Akshat for `cases/case-000/`. Copy that folder into `web/public/cases/case-000/`.

Test it by fetching `/cases/case-000/meta.json` in your app and printing it to the console. If you see the JSON, the plumbing works.

## 5. What the tools are

| Tool | What it does |
|---|---|
| **MapLibre GL JS** | Draws the map. Free, and needs no account or API key — one less thing to break on demo day. |
| **deck.gl** | Draws 3000 moving dots and the heat map using the graphics card. Normal web drawing cannot handle this many moving points. |
| **Zustand** | Remembers which case, which stage, and where the slider is. |
| **Recharts** | The small bar charts in the information panel. |
| **Tailwind** | Styling. |

**Never use localStorage or sessionStorage.** Keep everything in memory.

## 6. Your week

| Day | What you build | You are done when |
|---|---|---|
| Today | Map on screen, satellite photo placed correctly, layer on/off switches | Screenshot posted in group |
| **Monday** | **The slider and the moving dots** | **The slider drags smoothly with all 3000 dots** |
| Tuesday | Heat map, information panels, the bar charts | Click-through video posted |
| Wednesday | Swap in the real Ennore data, polish | Ready for the HOD demo |
| Thu–Fri | Ship paths, funnel, suspect cards, case switcher | Full demo works |

## 7. Monday is the day that decides the project

Everything rests on the slider being smooth. Not "mostly okay" — smooth.

**Test it with the full 3000 dots and 97 time steps.** Test it on your laptop AND on the laptop we will actually present from.

**If it stutters, you have two easy fixes and both are invisible to a viewer:**
1. Show every 2nd time step instead of every one.
2. Use 2000 dots instead of 3000.

**Three rules to keep it fast:**
- Read each file **once** into memory. Never re-read or re-parse while the slider moves.
- When the slider moves, only the dots layer should update — never the whole map component.
- Do not create new arrays inside the animation loop.

**Finding a problem on Monday is a success, not a failure.** Finding it on Wednesday is a disaster. Report the result either way.

## 8. Things that are easy to miss

**Not every case has all three stages.** The Ennore case has no ship data, because free ship data does not exist for Indian waters. Read `meta.json` → `acts_available`. If "attribute" is missing, grey out that stage button and show a small tooltip explaining why. **Do not crash.**

**One case has no oil at all.** That is on purpose — it proves our system can correctly say "nothing here." When `detections.geojson` has zero oil items, show a clear message on the map: "No spill detected in this scene." This is a designed screen, not an error screen.

**Everything is [longitude, latitude]** — the sideways number first. MapLibre and deck.gl both want it in this order, so if you just pass the file data straight through, you are fine.

## 9. How you use AI

You get **most of the Antigravity accounts** — use them for generating components, styling, and layout. Use your **Claude Pro for map and animation bugs**, which is where generated code most often needs real help.

**Start a new chat for each new bug.**

**How to start:**
> Read CLAUDE.md, web/CLAUDE.md and docs/04_HARSHITA_FRONTEND.md. I am on Phase 2. Add a time slider that controls a deck.gl ScatterplotLayer reading particles.positions[t], loaded once into memory.

**Working with Urooz:** she gives you colours, fonts, and card designs. You own how it works and how it is built. She owns how it looks. Sit together for about two hours a day.

## 10. Your checklist before Phase 1

- [ ] Node 20, Git, VS Code installed
- [ ] Repo cloned, branch `harshita` created
- [ ] App created and running on localhost
- [ ] All packages installed
- [ ] Next vs Vite decided (and written in the group so nobody asks again)
- [ ] `cases/case-000/` copied into `web/public/cases/`
- [ ] You can fetch and print `meta.json`

## 11. If you get stuck
deck.gl and MapLibre working together is the fiddliest part. **Stuck 45 minutes → message Akshat.** Also tell him immediately if any data file does not match the agreed shape — that is his job to fix, not yours to work around.
