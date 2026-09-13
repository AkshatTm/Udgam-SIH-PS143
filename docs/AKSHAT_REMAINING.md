# AKSHAT — Everything Left (own work + Anushka's + Harshita's)

*Written 14 Sept 2026 from a full audit: plan docs, update logs, git history, `cases/`, and a code
read of `web/`. **Demo: 15 Sept, 17:00.** Their old docs are in `docs/_archive/` (see the README
there). Soum and Jaiveer keep their own work, which is not listed here except where it blocks you.*

**Priority key.** **P0**: needed for the demo. **P1**: do if time allows before 17:00. **P2**:
after the demo, before December.

> **Audited against the repo 14 Sept (late), at `94206c4`.** Every item below is either ticked or
> still genuinely open; stale claims are corrected in place and marked *(was: ...)*.
> **State right now:** `origin/main` and local `main` both at `94206c4`; validator 26/26; 100 Stage 3
> tests; `cases/` PASS on all 9 with 6 warnings, 3 of them by design on the no-oil cases.
> **What is actually left: §1A verification prose (nothing ships on Verify without it), §1E the deck
> itself, §1F rehearsals, §3B human QA, §3C the demo machine and the fallback video.** Everything
> else on this page is done.

---

## 0. First 30 minutes — clear the ground

- [x] **P0 — Get anything unpushed off their laptops.** Harshita has **no branch on origin**; her
  last commit on `main` is 13 Sept 13:56. Anushka's last commit is 13 Sept 15:05. Her log stops
  at Phase 4, so work may be sitting locally. Ask both: *"push everything now, even half-done, to
  `harshita` / `anushka`."* **Do this before touching `web/` or `pipeline/drift/`**, or your fixes
  will collide with theirs.
- [x] **P0 — Commit tonight's uncommitted rulings.** They are now on branch `akshat-takeover`,
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
- [x] **P0 — ~~Ask Jaiveer to re-score~~ DONE 14 Sept without him.** The parquets were only on his
  laptop, but NOAA Marine Cadastre is a public download: rebuilt in ~4 minutes, then Jacksonville,
  Farallones and Huntington re-scored. Jacksonville and Huntington reproduce his funnel and ranking
  exactly. D36 `closest_km` and the D37 fields are now in the bundles, and Jacksonville validates
  with **0 warnings**. *(was: "Mumbai uses `--no-ais`" — Mumbai now runs on real GFW AIS, D40.)*
- [x] **P0 — Resync the frontend copy after every bundle change.** `web/public/cases` is stale:
  - Farallones, Huntington and Mumbai lack `suspects.json` and the attribute act.
  - It still holds retired `case-golden-ray-2021` and `case-ennore-2017`.
  ```bash
  python scripts/sync_web_cases.py
  ```

---

## 1. Your own work

### 1A. Verification — Phase 4, pure writing, nobody else can do it (P0)

**`naap_result` is now filled in all six files from the bundles** (verified: no `TODO` left in any
of them), and the stale wind shares in the facts-to-weigh lists were corrected. Huntington's verdict
is pre-filled `partial` and Jamnagar's `not_applicable`; the other four are still `TODO`.
**What is still owed is the human prose: `caveat` where marked, `verdict`, `explanation`,
`what_would_have_helped`.** **No live case has the `verify` act** — checked, only the synthetic
fixtures do — so Screen 4 is still empty for every case in the demo.

Per-case fact sheets (bundle numbers, the sealed-record comparison, the traps) sit in the scratchpad
beside the map overlays. They contain ANSWERS content and must never be committed.

For each case: open `docs/ANSWERS.md` and the primary source → fill `official_finding.caveat` →
check `naap_result` against the bundle → write `assessment` by hand → add
`"verify"` to `meta.acts_available` → **drop that file's line from `.git/info/exclude`** → build →
validate → sync.

```bash
python pipeline/export/build_case.py --case <id>
python scripts/validate_case.py cases/<id>
python scripts/sync_web_cases.py
```

| Case | Stage 3 state now | Expected verdict (pre-registered in the archived 01 §4.4) | Watch out for |
|---|---|---|---|
| Jacksonville | scored, 2 suspects 6.2% apart, **1.30 / 1.13 km from the origin peak**, 1 exclusion | open case (D31); reads as a **miss** on attribution | Neither Cerulean candidate is in our set, and the D30 competitor never reached it either. The likely cause is timing — we rewind 16–24 h with age not estimated. Say that; don't read it as "prediction wrong" |
| Farallones | scored 0.620 / 0.345 / 0.046; `type_prior` gated to null (D28) | reads as a **miss**; *(was: "headline blind result")* now **blind on weights, not provably on identity** (§16.1) | Ours is the 19.6 km slick, not the other Cerulean ones on the scene. Confirm the full vessel name from the slick page. Our #3 is one of Cerulean's co-candidates |
| Huntington | **abstained** (0.730 vs 0.729), **3 exclusions with reasons** | **`partial`** — measured, not assumed | The pipeline is declared (D38) and scores **≈0.006, below the 0.25 floor**: NTSB's point lies outside the origin grid, 6.75 km from the peak. So there is **no** infrastructure finding. The abstention is still the good part |
| Mumbai | **abstained after searching 9 vessels** (funnel 9 → 2 → 0 → 0) | likely `not_applicable` or `partial` | *(was: "no AIS searched")* **Changed by D40.** It now means "searched, and no vessel entered the origin cloud". The nearest — 5.0 km, grid probability 0.069 — was dropped by the 5-report minimum (issue F1). The natural-seep claim is **dropped**, not pending |
| Gulf of Alaska | trace only, no attribute (NOAA has no Alaska AIS) | `partial` at best; by the pre-registered origin-to-contact test it is a **miss** (16.6 km) | Origin is an **ERA5 (wind-driven) result, wind share 0.73** *(was: 81% — an earlier field)*. The radar contact is **Cerulean's**, never ours (D34) |
| Jamnagar | **attribute now runs**: 8 vessels searched, funnel 8 → 2 → 0 → 0, abstains | `not_applicable` | *(was: "trace only")* Searching and finding nobody in the cloud strengthens this verdict. Say "no investigation, no named party, no enforcement", **never** "no record anywhere" (D24). Don't reproduce Cerulean's candidate MMSIs |

The `explanation` is human prose. **Never generated.** A `miss` with a reason ships.

### 1B. Rulings still owed (P0 for the first two)

- [x] **Infrastructure candidates for Huntington (and Mumbai).** Jaiveer's Phase 4 module is built
  and tested, but `infrastructure[]` is **empty on every case**, because no candidate position is
  declared.
  - He needs a ruling on a new `meta.json` key, `infrastructure_candidates`: name, `[lon, lat]`,
    `source` URL.
  - Rule it into Master §6.1, add it to the validator, declare the San Pedro Bay Pipeline for
    Huntington from NTSB MIR-24-01, and have him rerun.
  - **Without it, Huntington's verdict is `partial`.**
  - Mumbai's candidate is already probed (score 0.368, sits on the slick's eastern tip, *outside*
    the origin grid). That tension should be stated, not hidden.
- [x] **Stage 3 issue register leftovers** (`docs/STAGE3_ISSUE_REGISTER.md`):
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
- [x] **`wind_share` into the contract** (Master §6.5 + validator + `web/lib/contracts.ts`), as a
  0–1 fraction, **omitted, never zeroed**, on synthetic fields. It's display-only until then.
- [x] **Reword D33's justification.** Behaviour stays; the stated reason was the channel-swap bug.

### 1C. Gallery copy fixes in `meta.json` (P0, 5 min)

- [x] `case-huntington-2021` blurb: *"Which ship released it?"* steers judges to a vessel when the
  source was a pipeline. Use *"What released it?"*
- [x] `case-gulf-alaska-2023` blurb: *"Radar sees a ship here"* implies **our** radar. Our detector
  finds no contact (D34). Reword so the contact is attributed to Cerulean, or drop the radar claim.

### 1D. Claims, sources, receipts (P0 before the deck is final)

- [x] **Mumbai "natural seep area"**: source it or remove it (D19 amended). It is unsourced today.
- [ ] `receipts.md` TODOs — **partly closed.** Done: the 118 m OpenDrift figure is qualified as
  synthetic and Jacksonville's 550 m added; NTSB's 4.75 nm and casualty coordinate added; the GFW
  section rewritten for D40. **Still open:** CPCL release date and quantity (the NGT O.A. 180/2023
  PDF is a 95-page scan with no text layer, so it needs OCR or reading by eye), per-case HYCOM
  cadence (the field caches are on Anushka's machine), Ennore 2017 official reference (P2).
- [x] **Vessel IDs in pushed git history** (`ee19819` → `72b9540`). Decide: amend Master §16.1 to
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
| OpenDrift agrees within **550 m on Jacksonville** over a 140 km rewind | "118 m" as a real-case number — that is synthetic `case-000`. *(`receipts.md` is fixed: it qualifies the 118 m and carries the 550 m.)* |
| Age ships as **not estimated**, with the gate reason (no detection is `acute`) | Any age accuracy claim, including "N = 1 on Huntington" (withdrawn) |
| Direction arrows on Jacksonville and Farallones only | Arrows on Huntington (143° reversal), Mumbai, Jamnagar |
| Error budget as a **library average** (inverts on Alaska and Jamnagar) | Error budget as universal |
| Galveston 987 → 897 → 17 → abstain; Huntington abstains on a real case with **3 named exclusions** | — |
| **The Phase 8 curve now exists** (D39, `docs/STAGE3_PHASE8.md`): offshore top-1 **0.910**, **0.488** on hourly AIS, **0.653** at one r90 of origin error, **0.556** against an offender with no behavioural signature | *(was: "the Phase 8 curve doesn't exist yet")* Any of it as **accuracy on the six live cases** — it is a *ranking* number given a stated origin quality, and an upper bound |
| Both Indian cases **search real vessels** and abstain because none entered the origin cloud (D40) | "there is no AIS in Indian waters" — that was our own error, corrected 14 Sept |
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

- [x] **P0 — D35 seed note.** No case's `meta.json` records which detection seeded the trace
  (`grep seeded_from cases/*/meta.json` finds nothing).
  - Append `seeded_from` (det id or "merged ribbon"), `n_oil` and merged yes/no to `meta.notes`
    from `pipeline/drift/publish_all.py` (`ensure_trace`, line ~70).
  - Write through the producer, **not by hand**.
  - UTF-8 read/write explicitly: the mojibake bug `4b7c304` came from exactly this function.
  - Matters most on Mumbai: seed `det-01` is 1.5 km² while `det-02` is 5× larger.
  - Check `ensure_trace` touches only `meta.json` before running it, so it doesn't re-integrate
    drift.
- [x] **P1 — Mumbai grid extent.** Jaiveer measured slick termini spanning 72.137–72.240°E against
  an origin grid ending at 72.151°E. Most of the 21 km slick lies east of the grid.
  - Likely cause: the trace seeds from the small `det-01`, not the whole event.
  - Look at the heatmap with the detections overlaid before quoting anything about Mumbai's origin.
  ```bash
  python pipeline/drift/plot_heatmap.py --case case-mumbai-2023
  ```
- [x] **P0 — Stage 2 slide numbers.** Pull the per-case r50/r90, `wind_share` and the OpenDrift
  550 m from `docs/_archive/anushka/STAGE2_NUMBERS.md` into the deck. Framing rules are the §1E
  table above.
- [x] **P1 — Per-case physics sanity (her Phase 5.3 list).** For each spill case:
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
| 1 | **Render Infrastructure findings in the abstain state too.** The block sits inside `gate === "clear"`. Move it (and Dark Vessels) out of that branch | `web/components/ContextPanel.tsx` ~L885–947 | Vessel abstention ≠ no infrastructure. **Done in the frontend pass.** Note the outcome: Huntington's pipeline scores below the floor, so `infrastructure[]` stays **empty** — the block must render nothing there and must not imply "pipeline excluded" |
| 2 | **Signed coordinates → hemisphere.** Shows "-79.68° E" | `ContextPanel.tsx` L392–395 (Trace best estimate) | Wrong on every US case, on the centrepiece screen |
| 3 | Delete or condition the always-on caption *"a bracket, not a single measured release time"* | `ContextPanel.tsx` L445–448 | Contradicts the "Measured estimate" label on `convergence` cases |
| 4 | Tooltip *"The true release point is almost certainly inside this circle"* → precision wording | `ContextPanel.tsx` L419 | Accuracy claim the plan forbids (D8, Part 12) |
| 5 | **D36 copy:** "Closest approach" → "Distance to origin peak" | `ContextPanel.tsx` L680 | `closest_km` is now measured to the grid peak |
| 6 | **D35 copy:** "Trace this slick back" → "Trace this spill back" (one trace per event) | `web/lib/flow.ts` L44 | UI implied a per-detection trace |
| 7 | **Parse and show `component_notes`** under each "n/a" bar | `web/lib/suspects.ts` (not parsed at all), `ContextPanel.tsx` `ComponentBars` L601 | Jacksonville and Farallones ship notes; every n/a currently has no reason (D29) |
| 8 | **Evidence breadth on the card (A9 BLOCKER / D37):** show `weight_live` or "scored from 5 of 7 components" next to the score. Parse the three fields in `suspects.ts` | `SuspectCard`, `ContextPanel.tsx` ~L674 | A 0.98 from 2 of 7 components must not look like certainty |
| 9 | **CHANGED 14 Sept (D40).** Mumbai's funnel is no longer zero — it is 9 → 2 → 0 → 0, abstaining because *no vessel entered the origin cloud*, so the "nothing was searched" sentence is **wrong there now** and must not be shown. Jamnagar has gained `attribute` with the same shape, so its Attribute screen is no longer greyed. Re-check both, plus Farallones' D37 keys, for contract-error cards | browser | The loader is strict, and two cases changed shape after the frontend pass |
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
| Jamnagar | Trace, **Attribute — it now runs (searched, then abstained), so it is no longer greyed**, Verify |
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

~~1. §0~~ · ~~2. §3A fixes 1–6~~ · ~~3. §1C blurbs, §2 D35 seed note~~ · ~~4. §1B infrastructure
ruling and the re-score~~ · ~~6. §3A 7–9~~ — **all done 14 Sept.**

What is left, in order:

1. **§1A verification prose**, case by case in library order, with §3B QA right after each case.
   Nothing ships on Screen 4 until this exists, and only you can write it.
2. **§3A item 9 re-check** — Mumbai and Jamnagar changed shape after the frontend pass (D40).
3. **§1E the deck itself.** Every number is in `docs/DECK_NUMBERS.md` with its receipt and its
   "never say"; the slides still have to be built.
4. **§3C demo machine + fallback video**, then **§1F rehearsals ×2**.
5. If time: §1D's remaining receipts (CPCL needs OCR), §2's P2 items, issue **F1**.

---

## Log

*Newest at the top. Format: `docs/updates/TEMPLATE.md`: what was done, files touched, run command,
open issues.*

<!-- first entry here -->

### 14 Sept (late) — Jaiveer's remaining work, done here: AIS rebuilt, Phase 8, GFW

**Done.**
- **AIS is no longer a dependency.** `data/ais/*.parquet` existed only on Jaiveer's laptop; rebuilt from the public NOAA Marine Cadastre archive in ~4 minutes (six daily files, ~2 GB, no auth). **Jacksonville and Huntington reproduce his funnel and ranking exactly**, which is the check that the rebuild is faithful.
- **Three cases re-scored.** Jacksonville's suspects are **1.30 and 1.13 km from the origin peak** (was 10.2/10.1 to the centroid, D36); D37 fields land; Jacksonville is now **0 warnings**.
- **D28 implemented** — it was in the contract but never in the code. Farallones' `type_prior` (1.0 for a tanker and two cargo ships) now gates to null; scores fall to 0.620/0.345/0.046, rank preserved by construction.
- **Exclusions exist for the first time.** The pool only ever held plausible-but-unranked vessels, which was empty on every case. It now draws on the near misses the funnel dropped, with the measured grid probability in the reason. Jacksonville 1, Huntington 3.
- **Validator:** a constant **zero** no longer warns (it cannot inflate a score, and gating it would raise every score on the case); cases where nothing was searched are exempt from the exclusion warning.
- **Phase 8 shipped** (`pipeline/attribute/evaluate.py`, `docs/STAGE3_PHASE8.md`, **D39**). Offshore top-1 **0.910** [0.87–0.94]; **0.488** on hourly AIS; **1.000** perfect cloud vs **0.653** at one r90 of error; **0.556** against an offender with no behavioural signature; in port with a 25 km cloud **111 of 150 trials abstain**. Ablation answers **A5** (`trajectory` −0.051, it contributes) and **A6** (`type_prior` −0.024, inert), and shows **removing `gap` improves top-1 by 0.143** when the offender does not go dark (A2 at scale).
- **D40: the Indian cases have real AIS.** GFW's 4wings report *does* return per-vessel hourly positions; we had ruled it out on a documentation sentence without issuing the request. `ingest_gfw.py` writes the same parquet schema. Mumbai 9 vessels / 31 vessel-hours, Jamnagar 8 / 43 — both abstain because **no vessel entered the origin cloud**, a searched negative rather than "nothing was searched". **Jamnagar gains `attribute`.**

**Files touched:** `pipeline/attribute/{score,evaluate,ingest_gfw,tests}.py` · `scripts/{validate_case,gfw_probe}.py` ·
`cases/case-{jacksonville,farallones,huntington,mumbai,jamnagar}/*` · `docs/{00_MASTER_PLAN,STAGE3_PHASE8,STAGE3_ISSUE_REGISTER,DECK_NUMBERS,receipts}.md` · `verification/*.json`

**Run command:**
```bash
bash <scratchpad>/get_ais.sh                                     # rebuilds the three NOAA parquets
python pipeline/attribute/ingest_gfw.py --case case-mumbai-2023 --out data/ais/mumbai.parquet
python pipeline/attribute/evaluate.py --parquet data/ais/jacksonville.parquet --trials 300
python scripts/test_validator.py && python pipeline/attribute/tests.py && python scripts/validate_case.py cases/
```
Expected: 26/26, 100 tests OK, PASS on all 9 (6 warnings, 3 of them by design on no-oil cases).

**Open issues.**
- **F1 (new, HIGH):** `MIN_POINTS=5` means five *hours* of presence at hourly sampling and drops the one Mumbai vessel that reached the origin cloud (grid probability 0.069 at 5.0 km). **Deliberately not changed** — Mumbai's sealed record names no AIS vessel, so relaxing it now would be tuning with the answer in view. Rule after the demo, validated on the Phase 8 curve.
- Verification prose for six cases is still the critical path, and no case has `verify` yet.
- Two harness bugs found and fixed by their own tests, worth remembering: the first offender generator made every offender a tanker (inflating `type_prior` to −0.100), and the Phase 8 mass radii were ordered by probability rather than distance (clouds ~3× their label, r50 > r90).


### 14 Sept — §0–§2: rulings D38, seed notes, claims, verification prep (Claude, parallel to the §3 session)

**Done.**
- **§0.**
  - Validator 23/23 and `cases/` PASS.
  - `akshat-takeover` merged into `main` and pushed (`cf728c2`).
  - `sync_web_cases.py --clean` run.
  - Mumbai `--no-ais` re-scored locally with current `score.py`: byte-identical to the bundle, so no Mumbai re-score is needed.
  - The Jaiveer re-score request (Jacksonville, Farallones, Huntington) is **drafted, not yet sent**.
- **§1C.** Huntington blurb "What released it?". Gulf of Alaska blurb no longer claims our radar, and its notes drop the stale "radar-versus-AIS cross-check" claim.
- **§1B, D38.**
  - `meta.infrastructure_candidates` is ruled into Master §6.1. Primary public sources only, never ANSWERS or Cerulean ids.
  - Validator check added: missing `source` and lon/lat swap. `wind_share` is in §6.5 and validated as a 0–1 fraction.
  - Three new mutations, **26/26**.
  - Huntington declares the San Pedro Bay Pipeline at **NTSB MIR-24-01's casualty location 33°34.20′ N 118°7.26′ W**, read from the report PDF.
  - **Measured before the re-score:** the point is outside the origin grid, 6.75 km from the peak and 8.2 km from the slick terminus. It scores ≈0.006, below the 0.25 floor, so **Huntington stays `partial`**. Not tuned.
- **D33 reworded.** Networks do transfer once channels match; live cases stay classical on the IoU evidence.
- **Issue register.** Resolutions table added for A1, A5/A6, A8, B3, B5, D1, D2, D3 and E1.
- **§1D.**
  - Natural-seep claim removed from `02_SOUM_DETECTION.md`, the §6.7 example and the open-items row.
  - Glossary "VH is the discriminator" removed.
  - §16.1 / D31: Farallones is **blind on weights, not provably on identity**, because Jaiveer's asks came from reading `ee19819`. The stage line quotes no count.
  - `receipts.md`: 118 m qualified as synthetic, 550 m Jacksonville added, NTSB 4.75 nm and coordinate added.
  - The NGT PDF is a 95-page scan with no text layer, so that TODO stays.
- **§2.**
  - `publish_all.py --notes-only` writes the D35 seed sentence into all six `meta.notes`. It reuses `run.merge_oil_features` and checks that the frame-0 mean matches the chosen seed and not the alternative (≤0.04 km vs ≥3.9 km). Idempotent.
  - **Mumbai seeds det-01 = 1.48 of 9.55 km².**
  - The Mumbai "grid extent" concern is not a grid bug. The origin is correctly up-drift (NNW). The unseeded det-02 is where Cerulean's candidates sit.
  - Physics sanity on all six: t0 = detection_time, r50 ≤ r90, centroid and peak off land (GSHHG), frame-0 inside the slick 0.93–0.99.
- **§1A prep.**
  - `naap_result` filled from the bundles in all six `verification/*.json`. Stale wind shares corrected in the facts-to-weigh lists: Alaska 0.73, Jamnagar 0.62.
  - `caveat`, `verdict` and `explanation` are **left for Akshat**. `verify` is not added.
  - Per-case fact sheets live outside the repo, because they contain ANSWERS content.
- **§1E.** `docs/DECK_NUMBERS.md`: every safe number with its receipt and its "never say".

**Files touched:** `scripts/validate_case.py` · `scripts/test_validator.py` · `pipeline/drift/publish_all.py` ·
`cases/case-*/meta.json` (6) · `docs/00_MASTER_PLAN.md` · `docs/STAGE3_ISSUE_REGISTER.md` · `docs/receipts.md` ·
`docs/02_SOUM_DETECTION.md` · `docs/DECK_NUMBERS.md` · `verification/case-huntington-2021.json` (+5 untracked drafts)

**Run command:**
```bash
python scripts/test_validator.py                        # 26/26
python pipeline/drift/publish_all.py --notes-only       # six OK, second run "unchanged"
python scripts/validate_case.py cases/                  # PASS
```

**Open issues.**
- **Verdicts will read worse than pre-registered, and that needs deciding before the deck.**
  - On both Cerulean vessel cases, our plausible set contains **none** of Cerulean's attributed vessels.
  - The likely common cause is timing: we rewind 16–24 h with age not estimated.
  - Gulf of Alaska's origin is 16.6 km from the contact.
  - Detail is in the fact sheets.
- Jaiveer: re-score ×3; `excluded[]` empty on all scored cases; Farallones `type_prior` not gating (D28).
- Web session: `wind_share?: number` in `contracts.ts`.
- Still open: CPCL date/quantity (needs OCR or reading by eye), per-case HYCOM cadence (Anushka's cache), Mumbai merged-ribbon re-trace (post-demo, invalidates the score).
- `trajectory` still bears toward the centroid (B3), left until after the demo.

### 14 Sept — §3 frontend fixes + automated pre-QA (Claude, parallel to the §0–2 session)

**Done.**
- **§3A fixes.**
  - 1: infrastructure, dark vessels and natural seep now render on abstain.
  - 2: hemisphere-aware coordinates (Trace best estimate and Detect centroid).
  - 3: the always-on bracket caption is deleted.
  - 4: the r90 tooltip is precision wording.
  - 5: "Distance to origin peak" with an InfoDot.
  - 6: "Trace this spill back".
  - 7: `component_notes` are parsed and validated. They show inline under n/a bars and as a hover title on measured bars.
  - 8: `weight_live` / `components_available` / `components_total` are parsed. "scored from N of 7 components" sits under the score, derived from non-null components when the counts are absent (Jacksonville until re-score).
  - 10: `edge_truncated` warning row.
  - 11: `age_estimators` expander; null shows "not applicable".
  - 12: in-memory cache of parsed bundles (`web/lib/bundleCache.ts`), reset by page reload.
  - 13 (debug overlay) skipped.
- **Two bugs found in QA and fixed.**
  - (a) `suspects.ts` threw on an empty `excluded[]`, which is only a validator WARN. **Attribute showed a contract-error card on Jacksonville and Farallones.** It now shows "No vessels excluded."
  - (b) Camera race in `MapView.tsx`: if bundles resolved before the map's `load`, Trace stayed on the scene-only fit and the origin was off-screen (seen on Alaska). A `mapReady` state now re-runs the fit.
- **§3B pre-QA (automated, not the human sign-off).**
  - All 9 bundles load through the real frontend loaders (sucrase-transpiled `web/lib` + a fetch shim). Particles t0 = detection_time, r50 ≤ r90, funnels monotone, every suspect has a track.
  - Headless Chrome screenshots of Trace and Attribute were checked by eye: Jacksonville, Farallones, Huntington, Mumbai, Alaska and Jamnagar. There were no error cards, and Trace frames scene + particles + origin.
  - **Verify was not QA'd:** no case has the `verify` act yet (§1A).
- **§3C:** `web/DEMO_RUNBOOK.md` covers the pull→validate→sync→build→start sequence, OS settings, offline check, fallback video and the break ladder. There is no runtime network dependency (local fonts, no tiles).

**Files.** `web/components/{ContextPanel,MapView}.tsx`, `web/lib/{suspects,origin,contracts,flow,store,bundleCache}.ts`, `web/DEMO_RUNBOOK.md`.

**Run.** `python scripts/sync_web_cases.py --clean && cd web && npx tsc --noEmit && npm run build && npm run start`

**Open issues.**
- **Producer (Jaiveer):**
  - Jacksonville and Farallones ship `excluded: []`. The funnel drops vessels, but no exclusion with a reason is listed, and the demo requirement wants at least one.
  - Farallones `type_prior` is 1.00 on every suspect (D28 warn).
  - Mumbai's `abstain_reason` says the fixed-source result "is reported below", but `infrastructure[]` is empty until the §1B candidate lands.
  - Huntington's reason cites "the top two vessels" while `scored` is 0. The wording is worth checking.
- **Stage 2:** Mumbai's origin sits at the scene's NW corner, off the main slick body. This matches §2 P1 (seed det-01); look before quoting it.
- **Human QA still owed (§3B):**
  - origin upstream
  - particles overlap the slick at frame 0
  - track hover highlight
  - reasons read sensibly out loud
  - greyed Attribute tooltip on Alaska/Jamnagar
  - scrub smoothness on the demo laptop
  - all of Verify
- Re-run `sync_web_cases.py` after the §1A verification and Jaiveer's re-score, then re-check the Farallones/Jacksonville cards.
