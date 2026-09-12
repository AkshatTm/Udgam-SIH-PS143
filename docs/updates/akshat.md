# Akshat — update log

*Newest entry at the TOP. Format: `docs/updates/TEMPLATE.md`.*

## [2026-09-13] D34 follow-up — rerun verified, edge rule declined, Zenodo indexed, sentinel date fixed

**Done:**
- **Soum's D34 rerun (`20594df`) verified.** All nine cases PASS with the D34 warnings gone. Every
  bundle carries a top-level `ship_detections`, and no feature carries its own copy. The rule
  threshold back-solves to −3.0 on all seven satellite cases. The forgotten-flag guard is a hard
  error.
- **Edge rule and `edge` flag declined, on Soum's evidence.** Checked independently: 2 of 173
  contacts sit at the edge, one of them Ennore's +10.27 dB port target. `_sea_level()` uses global
  median/MAD, so the truncated-window objection doesn't apply. The Delta contact is 29.7σ.
- **Corrected my own unverified claim.** I had written "among charted platforms" (D34, receipts,
  case notes) without checking any platform dataset.
- **Both Zenodo cases added to `index.json`** at slots 8–9. Before that could happen, fixed the
  header and gallery card, which would have rendered the 1970 sentinel as "01 Jan 1970". One helper
  now shows "time unknown".
- **Ruled that the rule threshold gets recorded in the bundle after the freeze,** not before.
- **Confirmed Anushka's `global-land-mask`** dependency.

**Files touched:** `cases/index.json` · `CLAUDE.md` · `requirements.txt` ·
`web/lib/cases.ts` (`formatAcquisitionDate`) · `web/components/{Header,Gallery,ContextPanel}.tsx` ·
`docs/00_MASTER_PLAN.md` (D34 wording) · `docs/receipts.md` · `cases/case-lookalike-zenodo/meta.json`

**Run command:**
```bash
python scripts/validate_case.py cases/case-lookalike-zenodo
```
Expected output: `PASS (1 warning(s))`. The warning is zero oil features, which is correct for a
look-alike.

**Checkpoint artefact:** all nine PASS · `tsc --noEmit` clean · edge and back-solve scripts in the
session scratchpad.

**Open issues:**
- **No browser check yet** of a zero-detection benchmark case. These are the first cases with
  `provenance: benchmark`, zero features and the time sentinel ever loaded in the UI. Open both
  before the demo.
- The ship detector's absolute −10 dB floor alone sets the threshold on Zenodo scenes
  (`k_sigma` is inert there). Known limitation, recorded in receipts, not tuned.
- The Delta contact's identity is unchecked against any infrastructure dataset.
- Recording the rule threshold in the bundle is deferred to October.

**Next:** a browser pass over cases 8 and 9, then the full nine-case demo run.

## [2026-09-13] D34 — scene-level ship_detections; "dark vessel" framing declined; dB confidence bands

**Done:** Ruled on Soum's §6.3 gap. `ship_detections` moves to the top level of the
`detections.geojson` FeatureCollection. Both Zenodo bundles had silently dropped their contacts
(1 + 31), and the map was drawing each contact once per feature (Ennore: 72 contacts → 2,088
markers). Declined his framing that a no-oil-plus-contact scene is "the dark-vessel case":
darkness needs AIS at a known time, and neither Zenodo case has one. The Delta contact sits in the
raster's top pixel row beside land, and our detector finds *no* contact on Alaska, the real
dark-vessel case. Replaced my invented 0.75/0.45 confidence bands with Soum's two dB bands.

**Files touched:** `docs/00_MASTER_PLAN.md` (§6.3, D34) · `docs/CONTRACTS.md` ·
`scripts/validate_case.py` (top-level contact checks; legacy warn-only) · `pipeline/detect/run.py`
(writes top-level, stops the per-feature copy) · `scripts/plot_detections.py` ·
`web/lib/{contracts,loadCase}.ts` · `web/components/MapView.tsx` (dedupe) ·
`web/components/ContextPanel.tsx` (dB bands) · `cases/case-{lookalike,nospill}-zenodo/meta.json` ·
`docs/receipts.md`

**Run command:**
```bash
python scripts/validate_case.py cases/case-nospill-zenodo
```
Expected output: `PASS (2 warning(s))`. The warnings say the top-level list is not recorded yet;
they go away when Soum reruns.

**Checkpoint artefact:**
- All nine live cases PASS.
- `ships.py` and `features.py` self-tests pass.
- `tsc --noEmit` is clean.
- Reproduced Soum's contact counts read-only (1 and 31).
- Back-solved the rule threshold from every shipped feature: −3.0 on all seven live cases.

**Open issues:**
- **run.py's new output is untested here.** `run.py` imports torch at module load, even on the
  classical path, and this venv has none. It passes `py_compile`; Soum's rerun is the real test.
- **Rerun hazard.** The −3.0 dB rule is passed by hand and recorded nowhere in the bundle.
  Without `--rule-contrast -3.0 --rule-elongation 2.5`, run.py uses −0.5 and reclassifies
  everything, and the frontend bands go silently wrong.
- **Soum's margin paragraph says "20 oil, median 0.578".** His own table and the bundles say 12,
  median 0.645. Nothing may quote 20.
- **Zenodo cases are still not in `cases/index.json`.** Presentation order is undecided.
- **Asked Soum:** should `detect_ships` reject contacts touching the raster border? That would
  remove the Delta contact.

**Next:** Soum reruns all nine with the flags, then rerun the back-solve and the validator. The
D34 warnings should disappear.

## [2026-09-13 ~11:00] Unblocking Soum's Stage 1 push — provenance field, gitignore, three corrections

**Done:** Soum's reply to `HANDOFF_SOUM_CASES.md` answered all four questions and returned three
findings I did not have, one of which invalidated a premise in my own code. Landed the schema
change he is blocked on (`meta.provenance`, D33) through the required order — Master §6.1 →
`CONTRACTS.md` → validator enum — so he can switch `scene_provenance()` off the CRS sniff. Fixed
`benchmark_scene.py`, which was built on the belief that Part III tiles are ungeoreferenced and
wrote a Null Island placeholder box for them; it now reads the real transform (verified round-trip
against the bounds Soum reported). Ignored `models/` before it could reach GitHub — 534 MB with
three blobs over the 100 MB hard limit. Pinned torch in a **separate** `requirements-detect.txt`,
because `--index-url` is not per-package and putting it in `requirements.txt` would repoint all
twelve shared dependencies at the PyTorch mirror. Recorded the corrected Stage 1 metrics and
killed the stale ones. Fixed the frontend rendering a rule margin as "87% confidence".

**Files touched:** `docs/00_MASTER_PLAN.md` (§6.1 `provenance`, §6.3 confidence semantics, D33) ·
`docs/CONTRACTS.md` (mirrored) · `scripts/validate_case.py` (provenance enum + non-finite JSON
guard) · `pipeline/export/benchmark_scene.py` (real bounds from the geotransform) · `.gitignore`
(`models/`) · `requirements-detect.txt` (new) · `requirements.txt` · `docs/receipts.md` (Stage 1
numbers, VH noise floor, cases 8–9) · `docs/TRAPS.md` (#24 nanmean/-inf→Infinity, #25 PROJ
hijack) · `web/lib/contracts.ts` · `web/components/ContextPanel.tsx` ·
`cases/case-lookalike-zenodo/meta.json` (new) · `cases/case-nospill-zenodo/meta.json`

**Run command:**
```bash
python scripts/validate_case.py cases/case-nospill-zenodo
```
Expected output: `FAIL — bounds.json: missing · detections.geojson: missing`. That is the
**correct** state today: both artefacts come off Soum's machine, and `meta.json` itself validates
clean with `provenance: "benchmark"`.

**Checkpoint artefact:** fed `benchmark_scene.py` a synthetic EPSG:4326 raster stamped with the
box Soum reported for `00134`; `bounds.json` came back `-89.6488, 29.1688 .. -89.4649, 29.3527`,
exact. The non-finite guard was tested by reproducing his bug directly — `np.nanmean` over an
array containing `-inf` → `json.dumps` → `{"contrast_db": -Infinity}` → validator fails it by
name. `npx tsc --noEmit` clean.

**Open issues:**
- **The push itself has not happened.** Everything above unblocks it; none of it is it. Stage 1 is
  still one commit from 9 Sept, and the seven live cases still fail the validator on a missing
  `detections.geojson`. That is the only thing between us and a working chain.
- `confidenceLabel()` bands the rule margin at 0.75 / 0.45 — those cutoffs are **my invention**
  and nothing has measured them. They are honest in kind (qualitative, not a percentage) but
  arbitrary in value. Ask Soum for the real margin distribution, or drop to two bands.
- The VH reframe is recorded in `receipts.md` but **the slide has not been changed.** Urooz has
  not seen this yet. If the deck ships claiming dual-pol discrimination on the seven live cases,
  it is claiming something we measured to be false.
- `features.py`'s `-inf` bug is fixed **at the gate, not at the source** — Soum is fixing the
  producing code. Until his push lands, the validator is the only thing catching it.
- Retrained-RF reproducibility is asserted, not demonstrated: nobody has retrained from
  `train.py` on a clean machine and compared to `model_meta.json`.

**Next:** Soum pushes Stage 1 → I merge → run the seven live cases through
`build_case.py --stage detect` and get `detections.geojson` on all of them. That is the last
structural gap in the chain.

---

## [2026-09-13, later] Integration-account pass — merged Anushka's plot guards, held her coastline commit on a dependency question

**Done:** Back as the integration account. `git fetch` found `origin/anushka` had pushed two more
commits since the last merge. Checked each independently before touching `main`: `88f8eef` (plot
guards) touches only `plot_heatmap.py`/`plot_quiver.py`, no new dependency — safe. `b4d280a`
(GSHHG coastline + stranding, decision D7) is real, tested work (8/8, 54/54 on her branch) but
pins `global-land-mask==1.0.0` after `requirements.txt`'s own no-new-dependencies date; she
flagged it herself and asked for confirmation. Asked the user how to handle it rather than
deciding unilaterally — chose to merge the safe commit and hold the dependency-bearing one.
Cherry-picked `88f8eef` (not a full merge, since `b4d280a` stays behind on her branch), verified
independently (`drift/tests.py` 7/7·48/48 unchanged, `test_validator.py` 21/21,
`validate_case.py cases/` still only missing `detections.geojson` × 7), pushed
(`3663d69..f399250`).

Also ruled out a false alarm before doing anything: a raw `main`-vs-`origin/anushka` diff touches
the Master Plan and every shared doc, which looks like the `626acce` regression pattern. Checked
directly — neither of her new commits touches those files; it's just that her branch forked
before this session's A1–A5 ratification landed on `main`. Worth remembering next time a branch
diff looks alarming: check which commits actually touched which files first.

**Files touched:** `pipeline/drift/plot_heatmap.py`, `pipeline/drift/plot_quiver.py` (Anushka's,
cherry-picked) · `docs/updates/_INTEGRATION.md`, `docs/updates/akshat.md` (this entry)

**Run command:**
```bash
git fetch --all && git log --oneline main..origin/anushka   # see what's new before touching anything
git cherry-pick 88f8eef
python pipeline/drift/tests.py            # 7/7, 48/48
python scripts/test_validator.py          # 21/21
python scripts/validate_case.py cases/    # fails only on detections.geojson x7
```

**Open issues / for the planning account:**
- **Confirm or decline `global-land-mask==1.0.0`.** If confirmed, merge `origin/anushka`'s
  `b4d280a` (predicted clean against current `main`, but re-check with `git merge-tree` first).
  If declined, tell Anushka Phase 4 needs a zero-dependency coastline source.
- Noticed but did not touch: untracked `pipeline/export/benchmark_scene.py` on disk, "Owner:
  Akshat" in its header, not committed anywhere. Not part of this session's work — flagging it in
  case it's mid-edit from another session and shouldn't be lost.
- Unchanged: Soum's `detections.geojson` on `case-jacksonville-2024` is still the critical-path
  item; no `origin/soum` branch exists. The reordered three asks to Soum and the downgraded ask
  to Urooz (both drafted in `_INTEGRATION.md`) are still not sent.

**Next:** planning account rules on the dependency → Soum delivers detections → first real
four-stage bundle.

---

## [2026-09-13] Ratified A1–A5 on Stage 2 age — all three physics departures accepted, the four-case age claim withdrawn

**Done:** Ruled on the five decisions the integration pass routed here (previous entry). Verified
each departure independently before signing, rather than accepting the brief's own derivations.

**A1 / D-A — yes.** C3.1 matches major-axis length, not area. `det F = 1` in an incompressible 2D
flow, so area is conserved and matching on it fits noise; test 6c measures area ×1.02 against
major axis ×5.7. No contract change. Knowingly buying one assumption: the
`2·sqrt(area × elongation / π)` observable treats the slick as an ellipse.

**A2 / D-B — yes, with a correction to how it gets quoted.** Re-derived from scratch: for
`F = [[1, γ], [0, 1]]`, `FFᵀ` has trace `2 + γ²` and det 1, so `a + 1/a = 2 + γ²`. The brief's
`sqrt(1 + (St)²)` is the stretch of a material *line* perpendicular to the flow — a different
quantity from a patch aspect ratio. Anushka is right. **But ×3.24 is not a conversion factor**: the
ratio is `sqrt(a² − 1)/sqrt(a + 1/a − 2)`, which climbs with elongation (2.45× at a=2, 3.24× at
a=8.2, 4.70× at a=20, 7.21× at a=50). No age may be corrected by dividing by 3.2 — each is
recomputed. That warning is now in the brief, and in `age.py`'s docstring where it is likeliest to
be copied.

**A3 / D-C — yes.** The circularity is real. **Numeric-volume contract field declined** — the freeze
holds and `--volume-m3` already carries it.

**A4 — narrowed, no longer blocking.** Fay's area scales as `k²`, so closing the measured 14× gap
would need `k ≈ 5.5` against a 1.1–1.5 literature range. The *regime verdict* is therefore robust to
`k` and ships uncited; only a Fay-*derived number* needs the citation, and A3 means we don't want
one. Urooz is unblocked.

**A5 — the four-case age claim is withdrawn.** Checked the live library before deciding: **no**
indexed case has a `detections.geojson`, **no** case carries a release time or volume in
`meta.json`, and `discharge_class` is unset everywhere including case-000's own `det-01`. Since
C3.3 is gated on `acute`, the estimator whose formula A2 corrects **currently fires on zero cases**
— so the claim failed on missing inputs, not on physics, and the true count was 0 cases rather
than the brief's 1. Age now ships as an output with method + breakdown and no accuracy number; if Huntington's
detection lands and C3.1 fires it becomes an explicit **N = 1** with its overestimate caveat
attached. Five sentences across three docs promised the four-case validation and were corrected.

**Files touched:** `docs/STAGE2_AGE_DECISION_BRIEF.md` (ratification header, D-B quoting box, D-C
`k`-robustness note, new §4a, §5 rewritten, §6 asks reordered/downgraded) ·
`docs/00_MASTER_PLAN.md` (the claims line) · `docs/03_ANUSHKA_DRIFT.md` (§"ground truth for age",
C5, step 1.6, 8.3, the DoD checkbox) · `pipeline/drift/age.py` (docstring warning only — **no
behaviour change**) · `docs/updates/akshat.md` (this entry)

**Run command:**
```bash
python pipeline/drift/tests.py             # 7/7, 48/48 — unchanged, nothing executable moved
python scripts/validate_case.py cases/case-000
```

Expected: `7/7 tests passed (48/48 individual assertions)`, then
`PASS acts=['detect','trace','attribute','verify'] (0 warning(s))`. Both confirmed after the edits.

**Open issues:**
- **Soum now has three asks, reordered.** `discharge_class` per detection is now #1 and outranks
  the two contrast fields — it is already in the frozen contract (§6.2) and C3.3 is inert without
  it. Not yet sent.
- Still owed by me: the 3-snapshot HYCOM window decision, and the US case list with documented
  incident times (now only gates the N = 1 check, not the deck).
- Anushka's `combine_bands` degenerate-band edge case and the `age_hours` null-vs-`[low, high]`
  validator question are still open from her Phase 1 entry; neither is touched by this ratification.

**Next:** send Anushka the three yes-es plus the "3.2× is not a conversion factor" warning; send
Soum the reordered three asks; tell Urooz A4 is downgraded.

---

## [2026-09-13] Integration-account pass — merged Anushka's Stage 2, routed A1–A5 instead of ruling on them

**Done:** Running under the integration-account role (`HANDOFF_ALT_ACCOUNT.md`): pipeline/merge/
validate only, no rulings. `git fetch --all` found `origin/anushka` had two new tested phases
(age estimation + the adaptive field-box pad/edge guard/high-latitude tests) not yet in `main`;
`origin/jaiveer-phase2` and `origin/harshita` were already fully merged. Predicted a clean merge
(`git merge-tree`, zero conflicts), merged, and verified independently rather than trusting the
branch's own log: `pipeline/drift/tests.py` 7/7 suites (48/48 assertions) matched exactly,
`test_validator.py` still 21/21, `validate_case.py cases/` still fails only on the expected
missing `detections.geojson` across all seven cases. Pushed (`b91eecf..3745d89`). Deleted the
stale local `akshat/v4-case-library` branch (no unique commits).

**Deliberately not decided here** — five methodology calls in the new
`docs/STAGE2_AGE_DECISION_BRIEF.md` (A1–A5) are explicitly addressed to the planning account.
Two matter most: **A2** changes every elongation-based age estimate by ~3.2× versus the original
brief (already shipped, needs sign-off before it's quoted anywhere), and **A5** is that the
age-validation claim is currently "1 of 1" (only Huntington has a documented incident time),
not the "4 cases" framing the plan assumed — worth deciding what that claim becomes before it's
on a slide. Full list, plus the routed-not-sent asks to Soum (two new contrast fields per
detection + Huntington's real major axis) and Urooz (a citation for the Fay constant), is in
`docs/updates/_INTEGRATION.md`'s dated entry — read that before ratifying anything by memory.

**Files touched:** merge of `pipeline/drift/{age.py,age_tests.py,geo_tests.py,check_gee.py,
fetch_fields.py,run.py,step.py,tests.py}` (Anushka's, all new/modified) ·
`docs/STAGE2_AGE_DECISION_BRIEF.md`, `docs/STAGE2_COMPONENT_REPORT.md` (new, Anushka's) ·
`docs/updates/anushka.md` (her entries) · `docs/updates/_INTEGRATION.md`, `docs/updates/akshat.md`
(this entry)

**Run command:**
```bash
git fetch --all && git log --oneline main..origin/anushka   # confirms what's new before merging
git merge origin/anushka --no-edit
python pipeline/drift/tests.py            # 7/7, 48/48
python scripts/test_validator.py          # 21/21
python scripts/validate_case.py cases/    # fails only on detections.geojson x7
```

**Open issues / for the planning account:**
- Rule on A1–A5 in `docs/STAGE2_AGE_DECISION_BRIEF.md` — A2 and A5 are the ones that change what
  goes on a slide.
- Send the routed asks to Soum and Urooz (text is in `_INTEGRATION.md`, not sent from here).
- Everything else is unchanged from the prior entry: Soum's `detections.geojson` is still the
  critical-path item; no `origin/soum` branch exists yet.

**Next:** planning account rules on A1–A5 → Soum delivers `case-jacksonville-2024` detections →
first real four-stage bundle becomes possible.

---

## [2026-09-12] Doc-regression fix + GFW coverage confirmed + case-1 flag resolved

**Done:** Found that commit `626acce` ("Update master plan and per-person docs", pushed to
`origin/main` before this session) had silently overwritten `00_MASTER_PLAN.md`,
`01_AKSHAT_INTEGRATION.md`, `03_ANUSHKA_DRIFT.md`, `04_HARSHITA_FRONTEND.md`,
`05_HARSHITA_INTEGRATION.md` and `06_JAIVEER_AIS.md` with a stale pre-v4 snapshot — deleting D23–
D31, **reintroducing the case-1 and case-2 vessel names into the shared Master Plan** (not
repeated here either; a live blind-eval leak on case 2, the headline blind result), and reintroducing Jaiveer's
already-fixed, geometrically-broken `trajectory` spec as current guidance. Reverted six files to
`e1379b9` (exact match, verified by diff), kept `02_SOUM_DETECTION.md`'s genuine improvement from
that commit, verified zero vessel-name hits outside `docs/ANSWERS.md`, committed (`084d4c2`) and
pushed. Full writeup in `docs/updates/_INTEGRATION.md`.

Then cleared two items that were stale in the just-restored docs but already resolved in reality:
**GFW Arabian Sea coverage** — token was already in `.env`; ran `gfw_probe.py --all`, presence +
AIS-disabling events + SAR presence all answer for both `case-mumbai-2023` and
`case-jamnagar-2024`, so both keep `attribute`. Flagged one open sub-item for Jaiveer: the gap-
events count (~10–11k) looks unfiltered by bbox, needs client-side filtering before use as a local
statistic. **Case-1 vessel flag** — cross-checked the MMSI/IMO against three independent AIS
registries; the old "CHN" note was wrong, MID 563/Singapore is correct, vessel type corrected too.
`docs/ANSWERS.md` updated. Case 2's vessel was deliberately not looked up (D31).

Propagated both closures into Master Part 14 and `01_AKSHAT_INTEGRATION.md` A4/§1.5.
`test_validator.py` still 21/21; `validate_case.py cases/` still fails only on the expected
missing `detections.geojson` across all seven live cases (no regressions from the doc revert,
since it touched no code or case data).

**Files touched:** `docs/00_MASTER_PLAN.md`, `docs/01_AKSHAT_INTEGRATION.md`,
`docs/02_SOUM_DETECTION.md`, `docs/03_ANUSHKA_DRIFT.md`, `docs/04_HARSHITA_FRONTEND.md`,
`docs/05_HARSHITA_INTEGRATION.md`, `docs/06_JAIVEER_AIS.md` (revert commit `084d4c2`) ·
`docs/00_MASTER_PLAN.md`, `docs/01_AKSHAT_INTEGRATION.md` (status updates, this commit) ·
`docs/ANSWERS.md` (gitignored, not pushed) · `docs/updates/_INTEGRATION.md`

**Run command:**
```bash
git log --oneline -5 -- docs/01_AKSHAT_INTEGRATION.md   # confirms 626acce sits directly on e1379b9
git diff e1379b9 -- docs/00_MASTER_PLAN.md               # empty after the revert = exact match
python scripts/gfw_probe.py --all                         # presence/events/SAR all OK for cases 5-6
python scripts/test_validator.py                          # 21/21
python scripts/validate_case.py cases/                    # fails only on detections.geojson × 7
```

**Open issues / for you:**
- **Check `origin/main` teammates may have already pulled `626acce`.** If anyone branched off it,
  their branch carries the vessel names and the broken formula — worth a one-line heads-up to
  rebase onto `084d4c2` or later.
- **Send Jaiveer the GFW gap-events bbox-filtering caveat** — not yet confirmed whether the
  endpoint filters server-side at all.
- Everything else open is unchanged from the previous entry: per-case announcements, Soum's
  no-spill nomination, Mumbai's unsourced natural-seep claim, `verification.json` for all six
  spill cases (still deliberately unwritten — see `verification/README.md`).

**Next:** confirm no teammate branch is built on the bad commit → Soum's `detections.geojson` on
Jacksonville is still the critical-path item → first real four-stage bundle.

---

## [2026-09-12] Phase 1/2 — Master Plan v4: eight-case library onboarded, six scenes exported, answers sealed

**Done:** Replaced the v3 planning docs with **Master Plan v4** and **01_AKSHAT_INTEGRATION v3**,
then executed the case onboarding they describe. The library is now seven live cases plus one
waiting on Soum.

**The finding that unblocked everything: SkyTruth Cerulean has a public OGC API** —
`api.cerulean.skytruth.org`, **no key, no auth**. Collection `public.slick_plus` returns the
**full** Sentinel-1 scene id, the slick polygon, the centerline, length/area/confidence and the
attributed source ids, filtered by `bbox` + `datetime`. That killed the BLOCKING "pull the
truncated scene ids out of the web panel" item outright, and it hands Soum a real-incident IoU
reference. Wrapped as `scripts/fetch_cerulean.py` (**D23**). Note `public.slick_to_source`,
`public.source_vessel` and `public.source_type` return 403 — names/flags/IMOs are a browser job.

**All six scene ids resolved and verified in GEE. Every one is VV+VH — no VV-only fallback
needed.** Six scenes exported at 10 m, 2-band float32, direct download, no Drive round-trip.
Every PNG eyeballed and every slick is visibly there:

| case | scene time | what the raster shows |
|---|---|---|
| `case-jacksonville-2024` | 2024-07-30 23:21:29Z | long sinuous chronic slick, full scene height |
| `case-farallones-2023` | 2023-03-17 14:24:42Z | ruler-straight discharge line NW–SE |
| `case-gulf-alaska-2023` | 2023-05-16 15:57:08Z | short dark curve, exactly on the slick bbox |
| `case-mumbai-2023` | 2023-09-03 01:03:33Z | broad head + long tail, **plus bright ship/platform returns** |
| `case-jamnagar-2024` | 2024-02-23 01:11:14Z | hook-shaped, textbook vessel-track geometry |
| `case-ennore-lookalike-2023` | 2023-11-30 00:32:01Z | Chennai coast, anchored ships, dark low-wind patches |

**Three corrections that stopped us shipping something checkable and false:**
1. **Jamnagar — Cerulean HAD logged it** (slick 3477622, same scene, 0.2 km from the GEE point,
   0.838 confidence, four candidate MMSIs). The deck line *"No record anywhere"* would have died
   in front of a judge. Reframed to **"no investigation, no named party, no enforcement"**, which
   is stronger: their own scorer rated all four candidates **below zero** and no human reviewed
   it. Their detection now corroborates that our slick is real (**D24**).
2. **Mumbai's "natural seep area" warning could not be substantiated.** Cerulean's AOI layers are
   EEZ / IHO / MPA / user-generated — **no seep layer** — and the slick is classed `VESSEL`, not
   `NATURAL`. The `natural_seep` class stays in the schema; the Mumbai claim does not ship until
   sourced (**D19 amended**). Also: that slick has **zero vessel candidates**, so "all four source
   classes on one detection" was wrong — it is five infrastructure candidates and a dark vessel.
3. **Gulf of Alaska is human-reviewed `AMBIGUOUS`** — a Cerulean analyst could not tell whether it
   is oil. Kept, and said out loud: our claim there is the radar-vs-transponder cross-check, not
   certainty that it is oil.

**Blind evaluation nearly broke on naming.** v4 called cases 1 and 2 `case-menuett-2024` and
`case-panagia-2023` — **the attributed vessels themselves**. Jaiveer would have had the answer from
the folder name. Renamed to `case-jacksonville-2024` / `case-farallones-2023`, and
`case-alaska-dark-2023` → `case-gulf-alaska-2023` (`dark` leaked the source type). Every vessel
name scrubbed from both shared docs (37 mentions).

**`docs/ANSWERS.md` written and sealed** — gitignored, `git check-ignore` verified. Committed
`docs/ANSWERS.README.md` in its place so the team knows it exists and why (**D21**).

**Validator + exporter hardening:**
- `ais_source` required when `attribute` is available, enum-checked (**D20**)
- **`gap`/`slowdown` numeric on a `gfw_hourly` case is now an ERROR**, not a style note
- `natural_seep` block; `source_type` enum += `natural_seep`
- `particles_forward.json` validated, including "is it just a copy of the rewind"
- `origin` age block + `opendrift_comparison`; missing `time_window_method` now warns
- `test_validator.py` **14/14 → 18/18**
- `gee_scene.py`: GEE's real ceiling is **50,331,648 bytes at 5 bytes per band-pixel** (float32 +
  a 1-byte mask), and an EPSG:4326 export has **no cos(lat) term** — the old estimate was wrong in
  both directions and two exports failed before it was fixed. Now predicts the exact raster.
  Added `--direct`; fixed the squashed 480×480 thumbnail.

**Files touched:** `docs/00_MASTER_PLAN.md` (v3→v4), `docs/01_AKSHAT_INTEGRATION.md` (v2→v3) ·
`scripts/fetch_cerulean.py`, `scripts/gfw_probe.py`, `.env.example` (new) ·
`scripts/validate_case.py`, `scripts/test_validator.py`, `scripts/make_case000.py` ·
`pipeline/export/gee_scene.py` · `cases/case-{jacksonville-2024,farallones-2023,gulf-alaska-2023,
mumbai-2023,jamnagar-2024,ennore-lookalike-2023,nospill-zenodo}/` (new), `cases/index.json`,
`cases/case-huntington-2021/meta.json` · `cases/_archive/` (new, Ennore 2017) ·
`cases/case-golden-ray-2021/` + its verification (deleted, D17) · `docs/receipts.md`,
`docs/TRAPS.md`, `CLAUDE.md`, `web/CLAUDE.md`, `docs/PER_DIRECTORY_CLAUDE.md`,
`verification/README.md` · `.gitignore` · `docs/ANSWERS.README.md` (new)

**Run command:**
```bash
python scripts/test_validator.py          # 18/18 caught and named
python scripts/validate_case.py cases/    # index + 7 cases; ONLY detections.geojson missing
python scripts/fetch_cerulean.py --case case-jacksonville-2024 --slick 3046293
```
Every case now fails on **exactly one** thing — `detections.geojson`, which is Soum's stage.
Zero schema errors, zero warnings.

**Open issues / for you:**
- **SEND THE PER-CASE ANNOUNCEMENTS** — drafted in `_INTEGRATION.md`, one message per case, never
  batched. Three people have been on fixtures for days and six real scenes are now on disk.
- **Jaiveer first, before anything else:** NOAA AIS density at 30.384 N −79.634 W (~100 km
  offshore). Still the only item that could force a replan.
- **GFW token is not on disk.** `scripts/gfw_probe.py` is written but has never made a live call —
  put the token in `.env` as `GFW_API_TOKEN` and run `--all`. Expect a fixing round on dataset ids.
- **`verification.json` deliberately NOT written for the new cases.** It ships inside the bundle,
  so writing it now would publish the answers and end the blind evaluation. The research is
  already staged in `ANSWERS.md`; it becomes a file after each bundle validates. Reasoning is in
  `verification/README.md`.
- **Case 8 needs Soum's no-spill nomination** — scaffolded, held out of `index.json` so the gallery
  cannot 404.
- ~~Confirm the case-1 vessel flag~~ — **done 2026-09-12**, see the entry above. `ANSWERS.md` had
  the old note down as CHN, which didn't match its own MID; corrected to Singapore.
- `acts_available` is `["detect"]` on every case by design — add acts as stages land, so no bundle
  ever claims a screen it cannot render.

**Next:** announcements out → Jaiveer's density check → Soum's detections on Jacksonville → the
first bundle that goes all the way through four stages.

---

## [2026-09-10] Phase 1/3 — D16 ruling: trace-without-detect via `meta.known_origin`; Golden Ray + Ennore scaffolded as known-source cases

**Done:** Ruled and implemented the trace-without-detect contract change the last entry left
open. New optional `meta.json` field **`known_origin`** (`[lon,lat]` or `{lon,lat,label,source_url}`):
a documented fixed source the trace stage seeds from when there is no SAR-visible slick. A bundle
with `known_origin` may carry `trace`/`attribute`/`verify` without `detect`, and
`detections.geojson` is no longer required. Master Plan §6.1 + Part 3 (Ennore row) + Part 9
(**D16**) updated; `docs/CONTRACTS.md` left frozen (Master wins). Validator relaxed to match:
new `check_known_origin` (shape + reuses the lon/lat-swap detector on the pin), `check_meta`
gate now accepts `known_origin` in place of `detect`. `test_validator.py` 12→**14/14** (added a
"trace, no detect, no known_origin" mutation and a "known_origin as [lat,lon]" mutation).

Scaffolded both no-slick cases on the new shape:
- **`cases/case-golden-ray-2021/meta.json`** → acts `["trace","attribute","verify"]`,
  `known_origin` = wreck at `[-81.40, 31.13]` (inside bounds). Validates cleanly except for the
  not-yet-produced stage outputs — the "trace without detect" error is gone.
- **`cases/case-ennore-2017/meta.json`** → acts `["trace","verify"]` (no attribute: no public
  Indian AIS), `known_origin` = collision position **APPROX `[80.36, 13.235]`** — flagged in
  `notes` for Akshat to pin from the DG Shipping / INCOIS report. Was untracked; `git add` it.
- **`verification/case-ennore-2017.json`** (new) — `official_finding` drafted from widely-reported
  facts with explicit TODO markers on `source_url`, IMO numbers, and the volume figure (do not
  ship until checked); `assessment.explanation` left as Phase-4 human prose.
- **`cases/index.json`** → `["case-huntington-2021", "case-ennore-2017", "case-golden-ray-2021"]`,
  default huntington. Order is a proposal — change if you want Golden Ray second.

**Files touched:** `scripts/validate_case.py`, `scripts/test_validator.py` (modified) ·
`cases/case-golden-ray-2021/meta.json`, `cases/case-ennore-2017/meta.json`, `cases/index.json` ·
`verification/case-ennore-2017.json` (new), `verification/README.md` ·
`docs/00_MASTER_PLAN.md` (§6.1, Part 3, Part 9) · `docs/updates/_INTEGRATION.md`

**Run command:**
```bash
python scripts/test_validator.py                          # 14/14 caught and named
python scripts/validate_case.py cases/case-golden-ray-2021  # FAIL only on missing stage outputs — NOT "trace without detect"
python scripts/validate_case.py cases/case-ennore-2017      # same
```

**Open issues / for you:**
- **Pin the Ennore collision coordinate** and add `source_url` + IMO numbers to
  `verification/case-ennore-2017.json` and `cases/case-ennore-2017/meta.json`. Current pin is a
  guess off the port entrance.
- **Confirm the Ennore oil-volume figure** and its revision history before that case ships.
- **Phase 4 prose** still owed by hand for all three verify cases (Huntington, Golden Ray,
  Ennore) — after the stages run.
- **Route to Harshita:** `web/lib/loadCase.ts` fetches `detections.geojson` unconditionally —
  must be gated on `"detect" in acts_available` or known-source cases 404 on load. Trace origin
  card needs a "seeded from documented source" state. `contracts.ts` `CaseMeta` wants optional
  `known_origin`.
- **Route to Anushka:** drift stage must seed from `meta.known_origin` when `detections.geojson`
  is absent (Golden Ray, Ennore).
- **Route to Jaiveer:** Golden Ray needs NOAA AIS for St Simons Sound ~31 Jul–9 Aug 2021; salvage
  fleet → `excluded[]`, wreck → `infrastructure[]`.
- Broadcast D16 + the `known_origin` shape to the group (draft in `_INTEGRATION.md`).

**Next:** send the routed messages + D16 broadcast → then Anushka/Jaiveer can produce the
Golden Ray + Ennore stage outputs and the first real known-source bundle can be wired.

---

## [2026-09-10] Phase 1 — Huntington Beach confirmed as hero; Golden Ray + Ennore have no SAR slick

**Done:** GEE auth working (project `quizzer-dev-487316`). Wrote `scripts/find_scenes.py`
(generalised finder) and committed `scripts/inspect_db.py`. Ran the scene search + export +
dB-confirmation loop for the two US spill cases.

- **Huntington Beach — CONFIRMED.** `S1A_..._20211002T015821..._2BF9`, 2021-10-02 01:58:21Z,
  ~3 h after the pipeline started leaking. Clean sharp comma-shaped slick, ~8–10 dB VV
  depression. `cases/case-huntington-2021/` scaffolded (meta v3, bounds, sar.png, thumb);
  2-band `sar_vv_vh.tif` running as a Drive export. This is the hero detection case.
- **Golden Ray — no SAR slick.** `S1A_..._20210808T232953..._C7D5` (+9 d; only S1 pass over the
  sound). Enclosed calm water, nothing visible. Wreck + VB-10000 cluster images clearly.
  Scaffold + honest notes in `cases/case-golden-ray-2021/`.
- **Ennore** (yours) — recap: same problem, dawn low-wind, no clean slick.
- `verification/case-huntington-2021.json` + `case-golden-ray-2021.json` — `official_finding`
  researched (NTSB MIR-24-01, MAR-21/01), `assessment` left as Phase-4 human-prose TODO.
- `cases/index.json` → `[huntington, golden-ray]`, default huntington (case-000 dropped from the
  gallery — it stays a validator fixture only; `case-ennore-2017` left for you to add when you
  finish it — it's untracked and I didn't touch it). `receipts.md` SAR + incident tables filled
  for all three; "Ayushmaan" → "Urooz".

**Files touched:** `scripts/find_scenes.py`, `scripts/inspect_db.py` (new) ·
`pipeline/export/gee_scene.py` (fixed the stale "press RUN" message — `task.start()` is the
trigger) · `cases/case-huntington-2021/*`, `cases/case-golden-ray-2021/*`, `cases/index.json` ·
`verification/case-{huntington,golden-ray}-2021.json` (new) · `docs/receipts.md` ·
`docs/updates/_INTEGRATION.md`

**Run command:**
```bash
python scripts/find_scenes.py --project quizzer-dev-487316 --bbox -118.35 33.50 -117.75 33.85 --start 2021-09-30 --end 2021-10-08 --incident 2021-10-01
python scripts/validate_case.py cases/case-huntington-2021   # FAIL only on detections.geojson (Soum's stage) — correct
```

**Open issues / decisions for you:**
- **Push local `main`** — it's ahead of origin by this session + the `origin/harshita` FF
  (data-driven gallery + `verify` act). `git push origin main`.
- **Trace-without-detect contract change** — Golden Ray (and probably Ennore) run as
  trace+attribute+verify from a known source. `validate_case.py` errors on `trace` without
  `detect`. Needs a small relax + a `meta.known_origin` field. Your call — frozen schema.
- **Move the Huntington GeoTIFF** from Drive/naap_exports/ when the task completes.
- **Send** the three drafted messages in `_INTEGRATION.md` (Huntington announcement now; Urooz
  cases 4/5 ask; Soum cases 6/7 ask) + the Part B broadcast.
- Precise Huntington rupture coordinate still `~4.5 nm offshore` — pin from MIR-24-01 for Phase 4.

**Next:** your push + trace-without-detect ruling → then I can scaffold Golden Ray/Ennore as
trace cases and wire the first real Huntington bundle once Soum + Anushka + Jaiveer deliver.

---

## [2026-09-09] Phase 0 + 3 — merged all four branches, hardened the validator, 2-band exporter

**Done:** Merged `origin/{soum,jaiveer,harshita,anushka}` onto `main` on a local `integration`
branch (was the top catastrophic risk — 2 commits on main, 4 branches holding the project).
soum/jaiveer/harshita clean; anushka 2 trivial conflicts. Dropped Soum's two force-added
label CSVs (stay local); kept `classifier.pkl`. Anushka's ÷100→÷1000 fix (repo-wide, verified
2026-09-07) adopted as canonical; fixed one leftover contradictory sentence.

Hardened `validate_case.py`: `check_verification` (verdict enum, non-empty `source_url`),
`check_index` (`validate_case.py cases/` now validates the index + each listed case),
`origin.bounds` sanity + off-scene renderability warning (Harshita D2), `area_km2` vs polygon
shoelace, extended `suspects.json` (`source_type`, `components` null, `dark_vessels[]` with
`mmsi: null`, `infrastructure[]`), `verify` act, Box pad 2.0→0.5°, utf-8. `test_validator.py`
now 12/12. `build_case.py` gathers `verification.json` + optional trace/scene files, `--reindex`.
`gee_scene.py` rewritten for the 4-artefact 2-band float32 GeoTIFF export (D14). Ran the full
stub chain end to end (first time the pipeline has actually been run) → PASS, 0 warnings.

**Files touched:** `scripts/validate_case.py`, `scripts/test_validator.py`, `scripts/make_case000.py`
· `pipeline/export/{build_case,gee_scene,CLAUDE}.py|md` · `pipeline/detect/run.py` (stub area_km2)
· `pipeline/drift/check_gee.py` · `cases/index.json` (new) · `verification/{TEMPLATE.json,README.md}`
(new) · `docs/{CONTRACTS,receipts,PER_DIRECTORY_CLAUDE}.md` · `web/CLAUDE.md` · `.gitignore`
· `docs/updates/_INTEGRATION.md`

**Run command:**
```bash
python scripts/validate_case.py cases/case-000     # PASS, 0 warnings
python scripts/validate_case.py cases/             # index + all listed cases
python scripts/test_validator.py                   # 12/12 caught and named
python pipeline/export/build_case.py --case case-000
```

**Open issues:**
- **`integration` branch is not pushed.** Fast-forward `main` to it and `git push`, then
  `git push origin --delete` the four feature branches. This is the one thing blocking everyone
  from a single source of truth.
- **Harshita, routed:** `MapView.tsx` uses `HeatmapLayer` for the origin — must be `BitmapLayer`
  (D11). `web/lib/contracts.ts` needs `"verify"` in `ALL_ACTS`/`Act` for screen 4.
- **GEE still untouched.** `check_ennore.py` + `gee_scene.py` unrun. Auth → confirm the Ennore
  slick is visible → `receipts.md` → export. First real run of `gee_scene.py` will need fixing.
- `verification.json` tooling is in (`verification/TEMPLATE.json`, validator, `build_case`) but
  no case has real prose yet — Phase 4.
- Frontend `contracts.ts`/`loadCase.ts` predate the v3 `suspects.json`/`origin.json` fields;
  Harshita renders them for screens 3–4.

**Next:** push `main` → broadcast Part B → GEE auth → Ennore confirm → case selection.

---

## [2026-09-06] Phase 1 — repo skeleton, frozen contracts, case-000, stubs for every stage

**Done:** Turned 22 loose documents into the repo layout the docs describe. Contracts extracted
from Master §4 into `docs/CONTRACTS.md` and marked FROZEN. `case-000` generates and validates
clean (0 warnings). Every stage now has a working `--stub` that writes schema-valid output, so
the full Detect → Trace → Attribute chain runs end to end today, on garbage, before any real
logic exists. Added `scripts/test_validator.py` because the validator had never been proven to
catch anything — it now catches 6/6 deliberately broken bundles and names each fault. Python
3.11.9 + venv, deps pinned. GEE scripts written but NOT yet run (no auth).

**Files touched:** `docs/*` (moved, 22 files) · `CLAUDE.md`, `pipeline/*/CLAUDE.md`,
`web/CLAUDE.md` (new) · `docs/CONTRACTS.md`, `docs/receipts.md` (new) · `.gitignore`,
`requirements.txt`, `README.md` (new/rewritten) · `scripts/make_case000.py` (added `--case-id`,
`--scene-only`) · `scripts/test_validator.py`, `scripts/check_ennore.py` (new) ·
`pipeline/{detect,drift,attribute}/run.py` (new stubs) · `pipeline/export/build_case.py`,
`pipeline/export/gee_scene.py` (new) · `cases/case-000/` (output)

**Run command:**
```bash
python scripts/make_case000.py
python scripts/validate_case.py cases/case-000
python scripts/test_validator.py
```
Expected output: `PASS acts=['detect', 'trace', 'attribute'] (0 warning(s))`, then
`6/6 mutations correctly caught and named`.

Full seam test (all three stubs, publishing through the case folder between stages):
```bash
python scripts/make_case000.py --out cases/case-smoke --case-id case-smoke --scene-only
python pipeline/detect/run.py        --case case-smoke --stub
python pipeline/export/build_case.py --case case-smoke --stage detect
python pipeline/drift/run.py         --case case-smoke --stub
python pipeline/export/build_case.py --case case-smoke --stage trace
python pipeline/attribute/run.py     --case case-smoke --stub
python pipeline/export/build_case.py --case case-smoke
```
Expected output: `PASS`. Verified 2026-09-06.

**Checkpoint artefact:** `cases/case-000/` committed (8.4 MB, 8 files) — the thing everyone
builds against. Validator self-test output above.

**Open issues:**
- **Phase 0 is NOT done.** The Ennore scene has not been verified — needs GEE signup, a
  noncommercial/research project, and `earthengine authenticate`. `scripts/check_ennore.py` is
  written and syntax-checked but has never made a real API call. This is the go/no-go the whole
  plan keys off, and it is the 45-minute-rule risk item. **Do it first tomorrow morning.**
- `pipeline/export/gee_scene.py` likewise unrun. The `getThumbURL` path and the pixel-dimension
  arithmetic are untested against the real API; expect at least one round of fixing.
- **Contract addition, announced not yet acknowledged:** `bounds.json` now carries optional
  `db_min` / `db_max` (the dB clamp). Reason in `docs/CONTRACTS.md` §3 and `docs/TRAPS.md` #7 —
  Soum reads the 8-bit PNG back to decibels and must use the same clamp. Additive only;
  consumers default to [-25, 0] when absent. Needs broadcasting to the group.
- Environment deviates from the frozen convention in one place: **Node 24** is installed, not
  Node 20 LTS. Harshita's lane only. Worth a decision before she scaffolds `web/`.
- `build_case.py --stage <act>` was added mid-session and is not in any personal doc: the case
  folder is the hand-off medium, so Stage 2 cannot read Stage 1 until Stage 1 is published into
  the case folder. Mention it at the sync so nobody rediscovers it.

**Next:** GEE auth → `check_ennore.py` → record the scene id in `docs/receipts.md` → export
`sar.png` + `bounds.json` for Ennore and hand to Soum (Handoff #2, due Mon evening).
