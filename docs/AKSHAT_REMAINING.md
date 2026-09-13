# AKSHAT — Everything Left (own work + Anushka's + Harshita's)

*Written 14 Sept 2026 from a full audit: plan docs, update logs, git history, `cases/`, and a code
read of `web/`. **Demo: 15 Sept, 17:00.** Their old docs are in `docs/_archive/` (see the README
there). Soum and Jaiveer keep their own work, which is not listed here except where it blocks you.*

**Priority key.** **P0**: needed for the demo. **P1**: do if time allows before 17:00. **P2**:
after the demo, before December.

---

## 0. First 30 minutes — clear the ground

- [ ] **P0 — Get anything unpushed off their laptops.** Harshita has **no branch on origin**; her
  last commit on `main` is 13 Sept 13:56. Anushka's last commit is 13 Sept 15:05. Her log stops
  at Phase 4, so work may be sitting locally. Ask both: *"push everything now, even half-done, to
  `harshita` / `anushka`."* **Do this before touching `web/` or `pipeline/drift/`**, or your fixes
  will collide with theirs.
- [ ] **P0 — Commit tonight's uncommitted rulings.** They are now on branch `akshat-takeover`,
  still uncommitted:
  - B6: `attribute` added to Farallones, Huntington and Mumbai (all three validate PASS)
  - D36: `score.py` now measures `closest_km` to the grid peak
  - D37: `weight_live` / `components_*` blessed, plus the validator WARN
  - GFW probe banner fix, `receipts.md` note
  - this archive move

  Your update log entry describing them is `docs/_archive/akshat/akshat.md` top.
  ```bash
  python scripts/test_validator.py            # expect 23/23
  python scripts/validate_case.py cases/      # expect PASS on index + all 9
  git check-ignore docs/ANSWERS.md            # must print the path, never commit it
  ```
  Then commit, PR to `main`, merge.
- [ ] **P0 — Ask Jaiveer to re-score** Jacksonville, Farallones, Huntington and Mumbai with the
  current `score.py`. That puts peak-based `closest_km` (D36) and the D37 fields into the
  committed bundles; the data is on his laptop only. Mumbai uses `--no-ais`. It clears the D37
  warnings.
- [ ] **P0 — Resync the frontend copy after every bundle change.** `web/public/cases` is stale:
  - Farallones, Huntington and Mumbai lack `suspects.json` and the attribute act.
  - It still holds retired `case-golden-ray-2021` and `case-ennore-2017`.
  ```bash
  python scripts/sync_web_cases.py
  ```

---

## 1. Your own work

### 1A. Verification — Phase 4, pure writing, nobody else can do it (P0)

All six files in `verification/` still carry `TODO` in `caveat`, `naap_result`, `verdict` and
`explanation`. **No live case has the `verify` act.** Screen 4 is empty for every case in the demo.

For each case: open `docs/ANSWERS.md` and the primary source → fill `official_finding.caveat` →
fill `naap_result` **from the bundle files, not memory** → write `assessment` by hand → add
`"verify"` to `meta.acts_available` → build → validate → sync.

```bash
python pipeline/export/build_case.py --case <id>
python scripts/validate_case.py cases/<id>
python scripts/sync_web_cases.py
```

| Case | Stage 3 state now | Expected verdict (pre-registered in the archived 01 §4.4) | Watch out for |
|---|---|---|---|
| Jacksonville | scored, 2 suspects, top two 6.2% apart | open case (D31); possibly `partial`/`miss` (D30) | The D30 pre-registered competitor never reached the plausible set — say so, don't read it as "prediction wrong" |
| Farallones | scored, clean separation | **headline blind result**, unknown until you open ANSWERS | Scene has other Cerulean slicks; ours is the 19.6 km one. Confirm full vessel name from the slick page |
| Huntington | **abstained** (0.730 vs 0.729) | `partial` unless infrastructure finding lands (see 1B) | Naming a transiting vessel would be wrong; the abstention is the good part |
| Mumbai | abstained, no AIS searched | multi-source / likely `not_applicable` or `partial` | "0 vessels" means **nothing searched**. Natural-seep claim still unsourced (1D) |
| Gulf of Alaska | trace only, no attribute (NOAA has no Alaska AIS) | `partial` at best | Origin is an **ERA5 (wind-driven) result**, 81% wind share. The radar contact is **Cerulean's**, never ours (D34) |
| Jamnagar | trace only | `not_applicable` | Say "no investigation, no named party, no enforcement", **never** "no record anywhere" (D24). Don't reproduce Cerulean's candidate MMSIs |

The `explanation` is human prose. **Never generated.** A `miss` with a reason ships.

### 1B. Rulings still owed (P0 for the first two)

- [ ] **Infrastructure candidates for Huntington (and Mumbai).** Jaiveer's Phase 4 module is built
  and tested, but `infrastructure[]` is **empty on every case**, because no candidate position is
  declared.
  - He needs a ruling on a new `meta.json` key, `infrastructure_candidates`: name, `[lon, lat]`,
    `source` URL.
  - Rule it into Master §6.1, add it to the validator, declare the San Pedro Bay Pipeline for
    Huntington from NTSB MIR-24-01, and have him rerun.
  - **Without it, Huntington's verdict is `partial`.**
  - Mumbai's candidate is already probed (score 0.368, sits on the slick's eastern tip, *outside*
    the origin grid). That tension should be stated, not hidden.
- [ ] **Stage 3 issue register leftovers** (`docs/STAGE3_ISSUE_REGISTER.md`):
  - A1: Menuett is not a gap case, so plan text needs an edit.
  - A5 / A6: `trajectory` and `type_prior` weights. **No weight moves** until Jaiveer's Phase 8
    curve exists. Say that on the honesty slide.
  - A8: repeat offenders can't be demonstrated. Reframe it as roadmap.
  - B3: the peak sits 10.65 km from the centroid, so the r50/r90 rings are centroid-centred.
  - B5: validator warnings, mostly solved by the reach fix.
  - D1: blindness wording (also 1D).
  - D2: Master Part 3 is stale on Menuett and on distance.
  - D3: D-number drift.
  - E1: narrative for Phases 4–7 that won't ship.
- [ ] **`wind_share` into the contract** (Master §6.5 + validator + `web/lib/contracts.ts`), as a
  0–1 fraction, **omitted, never zeroed**, on synthetic fields. It's display-only until then.
- [ ] **Reword D33's justification.** Behaviour stays; the stated reason was the channel-swap bug.

### 1C. Gallery copy fixes in `meta.json` (P0, 5 min)

- [ ] `case-huntington-2021` blurb: *"Which ship released it?"* steers judges to a vessel when the
  source was a pipeline. Use *"What released it?"*
- [ ] `case-gulf-alaska-2023` blurb: *"Radar sees a ship here"* implies **our** radar. Our detector
  finds no contact (D34). Reword so the contact is attributed to Cerulean, or drop the radar claim.

### 1D. Claims, sources, receipts (P0 before the deck is final)

- [ ] **Mumbai "natural seep area"**: source it or remove it (D19 amended). It is unsourced today.
- [ ] `receipts.md` TODOs: CPCL release date and quantity (read the NGT O.A. 180/2023 PDF), HYCOM
  cadence per case, Ennore 2017 official reference.
- [ ] **Vessel IDs in pushed git history** (`ee19819` → `72b9540`). Decide: amend Master §16.1 to
  say Farallones' blindness assumes nobody read that window, or rewrite history (not advised this
  close). Case 1's name is also in `jaiveer.md` and the progress docs; case 1 is open, so it's
  flagged, not scrubbed.

### 1E. The deck — Phase 6 (P0)

About ten slides; structure in `docs/_archive/akshat/01_AKSHAT_INTEGRATION.md` Phase 6. What is
**safe** and what is **dead**:

| Say | Never say |
|---|---|
| Adding a second polarisation took val F1 0.346 → 0.643 | "VH is the discriminator" (the feature was computed from VV) |
| Networks transfer once channels match; live cases stay classical (median IoU vs Cerulean 0.483) | "The networks don't transfer" |
| r50/r90 = **precision** across 50 runs | "accurate to X km" |
| OpenDrift agrees within **550 m on Jacksonville** over a 140 km rewind | "118 m" as a real-case number. 118 m was measured on synthetic `case-000` (`STAGE2_NUMBERS.md` §8.4 vs line 145); `receipts.md` quotes it unqualified, so fix that |
| Age ships as **not estimated**, with the gate reason (no detection is `acute`) | Any age accuracy claim, including "N = 1 on Huntington" (withdrawn) |
| Direction arrows on Jacksonville and Farallones only | Arrows on Huntington (143° reversal), Mumbai, Jamnagar |
| Error budget as a **library average** (inverts on Alaska and Jamnagar) | Error budget as universal |
| Galveston 987 → 897 → 17 → abstain; Huntington abstains on a real case | Attribution top-3 % (the Phase 8 curve doesn't exist yet) |
| Zenodo DOI 10.5281/zenodo.13761290, CC-BY, **mandatory on a slide** | — |

Prior-art slide first: CleanSeaNet, Cerulean, INCOIS (Master Part 11).

### 1F. Demo prep — Phase 7 (P0, see also §3C)

- [ ] Demo machine pulls latest validated `main`, then runs `python scripts/validate_case.py cases/`
- [ ] Deck PDF on the machine and on a phone
- [ ] **Two timed rehearsals** with someone playing hostile judge (Q&A list: archived 01, Part E)
- [ ] Charger, HDMI adapter, hotspot
- [ ] **Decide who drives the laptop.** It was Harshita, so that you face the judges. Confirm she's
  still doing it.

### 1G. P2

`verification.json` for Ennore-2017 (SLC retry, D18) · deployment-cost figure · rename channels in
`build_cache.py` (needs retrain) · a Python 3.11 venv check of the torch install (Soum).

---

## 2. Anushka's remaining work (Stage 2)

Stage 2 is **functionally complete**: all six spill cases ship `particles.json`,
`particles_forward.json` and `origin.json`; OpenDrift is compared; coastline and stranding are in.
**Test 6r now passes** (verified 14 Sept). The suite then stops only on a missing local
`data/fields/case-000.npz` cache, which is environmental. What's left is small.

- [ ] **P0 — D35 seed note.** No case's `meta.json` records which detection seeded the trace
  (`grep seeded_from cases/*/meta.json` finds nothing).
  - Append `seeded_from` (det id or "merged ribbon"), `n_oil` and merged yes/no to `meta.notes`
    from `pipeline/drift/publish_all.py` (`ensure_trace`, line ~70).
  - Write through the producer, **not by hand**.
  - UTF-8 read/write explicitly: the mojibake bug `4b7c304` came from exactly this function.
  - Matters most on Mumbai: seed `det-01` is 1.5 km² while `det-02` is 5× larger.
  - Check `ensure_trace` touches only `meta.json` before running it, so it doesn't re-integrate
    drift.
- [ ] **P1 — Mumbai grid extent.** Jaiveer measured slick termini spanning 72.137–72.240°E against
  an origin grid ending at 72.151°E. Most of the 21 km slick lies east of the grid.
  - Likely cause: the trace seeds from the small `det-01`, not the whole event.
  - Look at the heatmap with the detections overlaid before quoting anything about Mumbai's origin.
  ```bash
  python pipeline/drift/plot_heatmap.py --case case-mumbai-2023
  ```
- [ ] **P0 — Stage 2 slide numbers.** Pull the per-case r50/r90, `wind_share` and the OpenDrift
  550 m from `docs/_archive/anushka/STAGE2_NUMBERS.md` into the deck. Framing rules are the §1E
  table above.
- [ ] **P1 — Per-case physics sanity (her Phase 5.3 list).** For each spill case:
  - particles at frame 0 overlap the slick
  - origin centroid not on land
  - `particles.t0` = `meta.detection_time`
  - origin upstream of the expected current

  This overlaps the browser QA in §3B, so do both in one pass.
- [ ] **P2 — `temporality` null on half the library** (A10). Farallones, Mumbai and Jamnagar are
  `bounded`. The route is Soum's polygon feeding head-proximity timing, not Stage 2.
- [ ] **P2 — Weathering flag.** It stays "unknown" until Soum emits `contrast_centre_db` /
  `contrast_edge_db`.
- [ ] **P2 — Full suite on a machine with the field cache.**
  ```bash
  python pipeline/drift/fetch_fields.py --case case-000
  python pipeline/drift/tests.py
  ```

---

## 3. Harshita's remaining work (frontend + integration)

The frontend is **real and builds clean**: `tsc --noEmit` 0 errors and `npm run build` succeeded
(checked 14 Sept). Every screen and designed state in her Phase 0–5 plan exists in code. What's
left is a set of correctness fixes, the human QA gate she never ran past Detect, and the demo
machine.

### 3A. Code fixes (P0 unless marked; each is a few lines)

| # | Fix | Where | Why |
|---|---|---|---|
| 1 | **Render Infrastructure findings in the abstain state too.** The block sits inside `gate === "clear"`. Move it (and Dark Vessels) out of that branch | `web/components/ContextPanel.tsx` ~L885–947 | Vessel abstention ≠ no infrastructure (Jaiveer's module runs regardless). Huntington abstains, so its pipeline finding would be **invisible** the moment 1B lands |
| 2 | **Signed coordinates → hemisphere.** Shows "-79.68° E" | `ContextPanel.tsx` L392–395 (Trace best estimate) | Wrong on every US case, on the centrepiece screen |
| 3 | Delete or condition the always-on caption *"a bracket, not a single measured release time"* | `ContextPanel.tsx` L445–448 | Contradicts the "Measured estimate" label on `convergence` cases |
| 4 | Tooltip *"The true release point is almost certainly inside this circle"* → precision wording | `ContextPanel.tsx` L419 | Accuracy claim the plan forbids (D8, Part 12) |
| 5 | **D36 copy:** "Closest approach" → "Distance to origin peak" | `ContextPanel.tsx` L680 | `closest_km` is now measured to the grid peak |
| 6 | **D35 copy:** "Trace this slick back" → "Trace this spill back" (one trace per event) | `web/lib/flow.ts` L44 | UI implied a per-detection trace |
| 7 | **Parse and show `component_notes`** under each "n/a" bar | `web/lib/suspects.ts` (not parsed at all), `ContextPanel.tsx` `ComponentBars` L601 | Jacksonville and Farallones ship notes; every n/a currently has no reason (D29) |
| 8 | **Evidence breadth on the card (A9 BLOCKER / D37):** show `weight_live` or "scored from 5 of 7 components" next to the score. Parse the three fields in `suspects.ts` | `SuspectCard`, `ContextPanel.tsx` ~L674 | A 0.98 from 2 of 7 components must not look like certainty |
| 9 | Confirm Farallones' `suspects.json` (has D37 keys) and Mumbai's no-AIS abstain load without a contract-error card. Mumbai must show the "nothing was searched" sentence beside the zero funnel | browser | The loader is strict; the new keys were untested |
| 10 | P1: `edge_truncated` flag on the card; `age_estimators` expandable | `contracts.ts` L276 / L178 (declared, never rendered) | Minor honesty detail |
| 11 | P1: cache bundles across case switches (`cache: "no-store"` re-downloads MBs) | `web/lib/loadCase.ts` L22, L50 | Slow switching on the demo laptop |
| 12 | P2: hidden debug overlay on a key nobody presses by accident | new | QA speed |

Check after the fixes:
```bash
cd web && npx tsc --noEmit && npm run build && npm run dev
```
**Never patch data in the frontend.** If a bundle looks wrong, fix the producer.

### 3B. The human QA gate — per case (P0)

Only **Detect** was ever signed off (all 9, 13 Sept). Trace, Attribute and Verify have never been
QA'd on a real bundle. After `sync_web_cases.py`, run on each case and log `QA PASS` or
`QA REJECT — symptom, file, field` in the log below.

| Case | Needs QA of |
|---|---|
| Jacksonville | Trace, Attribute, Verify (once 1A done) |
| Farallones | Trace, Attribute, Verify |
| Huntington | Trace, Attribute (abstain + infrastructure), Verify |
| Mumbai | Trace, Attribute (no-AIS abstain), Verify |
| Gulf of Alaska | Trace, greyed Attribute tooltip, Verify |
| Jamnagar | Trace, greyed Attribute tooltip, Verify |
| 3 rejection cases | nothing new (Detect done) |

Condensed checklist (full version: `docs/_archive/harshita/05_HARSHITA_INTEGRATION.md` Part B):
- **Load:** no console error; map frames scene + particles + origin; nothing important off-screen.
- **Trace:**
  - particles overlap the slick at frame 0
  - cloud widens as you rewind
  - origin upstream
  - r50 ≤ r90 and plausible
  - readout in UTC hours, not off by 5:30
  - bounded bracket doesn't look like a measurement
  - heatmap has structure
  - auto-play runs once and rests rewound
- **Attribute:**
  - funnel monotone
  - every suspect has a track
  - closest points sit in high-probability water
  - n/a not zero
  - ≥1 exclusion with a reason
  - top suspect's reasons read as a sensible story out loud
  - hover a card and its track highlights
- **Verify:** both columns filled; badge; `source_url` opens; MISS looks as confident as HIT.

### 3C. Demo machine — she owned this (P0)

- [ ] Clone, install, all 9 bundles, `npm run build && npm run start` (production, not dev)
- [ ] **Run with wifi off**: the full click path across all 9 cases
- [ ] Frame times with all cases loaded. 60 fps was measured only on synthetic `case-000`, on her
  laptop
- [ ] Notifications and auto-updates off, display never sleeps, plugged in, one browser window
- [ ] **Record the fallback video on this machine** (full demo run). Save locally and on a phone.
  Re-record if the build changes.
- [ ] Before each pull onto it: validator PASS, then re-run the click path
- [ ] Break ladder rehearsed: toggle the layer off → switch case → fallback video → spare laptop →
  deck on phone. Between judges, press **Start over**.

---

## 4. Suggested order to 17:00 on 15 Sept

1. §0: pushes, commit, re-score request, sync
2. §3A fixes 1–6: an hour of small edits, and they touch what judges see
3. §1C blurbs, §2 D35 seed note
4. §1B infrastructure ruling, then Jaiveer's rerun
5. §1A verification prose, case by case in library order, with §3B QA right after each case
6. §3A 7–9 (component notes, evidence breadth)
7. §1E deck, §1D claims
8. §3C demo machine + fallback video, §1F rehearsals ×2

---

## Log

*Newest at the top. Format: `docs/updates/TEMPLATE.md`: what was done, files touched, run command,
open issues.*

<!-- first entry here -->
