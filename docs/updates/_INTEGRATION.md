# Integration log — every seam event, in one place

*Owner: Akshat. Newest entry at the TOP.*

This file records what broke **between** components, so the history of seam failures lives
somewhere other than six people's memories. A component's own bugs go in that person's update
log; this file is only for the joins.

---

# ▶ START HERE — state of the world, 2026-09-12

*Written for whoever picks integration up next, including a fresh AI session. Read this section
first; everything below it is history.*

## Nobody is blocked on Akshat any more

| Person | Has what they need? | Next move |
|---|---|---|
| **Soum** | ✅ 7 scenes: `sar_vv_vh.tif` (2-band float32, 10 m), `sar.png`, `bounds.json` with the per-case dB clamp | Run Stage 1 on `case-jacksonville-2024` |
| **Anushka** | ✅ real `detection_time` + bounds on all 7 | Fetch fields; seeding waits on Soum's polygons |
| **Jaiveer** | ✅ dates, boxes, `ais_source`; D27–D31 ruled; GFW confirmed working | Phase 8 curve **with the per-component ablation** |
| **Harshita** | ✅ frontend loads all 7 cases; `sync_web_cases.py` feeds the browser | Detect screen's "stage pending" state |
| **Urooz** | ✅ never blocked | Research |

**The critical path now runs between teammates, not through Akshat:** Soum's detections gate
Anushka's seeding, and her `origin.json` gates Jaiveer's scoring.

## The loop, per case

```bash
python pipeline/detect/run.py         --case <id>          # Soum
python pipeline/export/build_case.py  --case <id> --stage detect
python pipeline/drift/run.py          --case <id>          # Anushka
python pipeline/export/build_case.py  --case <id> --stage trace
python pipeline/attribute/run.py      --case <id>          # Jaiveer
python pipeline/export/build_case.py  --case <id>
python scripts/validate_case.py cases/<id>                 # must PASS
python scripts/sync_web_cases.py                           # then Harshita QAs it
```

**`build_case.py` is not optional.** A stage that writes to `out/` and a validator that reads
`cases/<id>/` gave us a green PASS on the wrong files once already (TRAPS #21).

## Standing rules that must survive the account switch

1. **Weights and thresholds are set on injected scenarios only, never on a real case** (D27, D31).
   Case 1 is formally open for diagnostics; it is still not a tuning set.
2. **`docs/ANSWERS.md` is never committed.** It is gitignored. `git check-ignore` it before any
   commit that touches `docs/`.
3. **`verification.json` is written only after a bundle validates** — it contains the answer, and
   it ships inside the bundle (`verification/README.md`).
4. **Cases are named after places, never vessels.** A case id that looks like a ship's name is a
   bug; report it, do not rename it back.
5. **Master Plan §6 is the contract. `docs/CONTRACTS.md` mirrors it** — change Master first and
   mirror in the same commit, or the drift starts again.
6. **Before claiming any negative result, check for a published positive one.** This project has
   nearly shipped three false negatives (Ennore, Jamnagar, and GFW below).

## Open, in priority order

- **Soum owes the no-spill scene** (`case-nospill-zenodo` is scaffolded and deliberately held out
  of `index.json` until it lands).
- **Three questions to Jaiveer** are in the reply drafted below — the "eleven of 52" one affects a
  slide number.
- **`verification.json` for all six spill cases** — Akshat's, by hand, after each bundle validates.
- **Mumbai's "natural seep" claim** is unsourced and must not ship until it is (D19 amended).
- ~~Vessel names/flags/IMOs for cases 1 and 2 need confirming~~ — **case 1 done 2026-09-12**, see
  below. Case 2's vessel deliberately stays unchecked — it is the headline blind result (D31) and
  confirming its identity now would be the same mistake as verifying its AIS density would have
  been for case 1.
- ~~GFW Arabian Sea coverage for cases 5–6~~ — **done 2026-09-12**, see below.

---

## [2026-09-12] Doc-regression fix (commit `626acce`) + GFW coverage confirmed + case-1 flag resolved

### The seam failure this entry exists to record

A prior session's commit `626acce` ("Update master plan and per-person docs") **silently
overwrote** `00_MASTER_PLAN.md`, `01_AKSHAT_INTEGRATION.md`, `03_ANUSHKA_DRIFT.md`,
`04_HARSHITA_FRONTEND.md`, `05_HARSHITA_INTEGRATION.md` and `06_JAIVEER_AIS.md` with a stale
snapshot that predated D23–D31, the case renames, and the Cerulean-API case-onboarding — almost
certainly written from a cached copy of the docs rather than the files actually on disk. Already
pushed to `origin/main` before this was caught.

**What it actually broke, not just "was out of date":**
- **Reintroduced the case-1 and case-2 vessel names directly into the shared, pushed Master Plan**
  (table row + prose, both cases) and into Anushka's doc. Case 2 is the **headline blind result**
  (D31) — this is a live blind-evaluation leak in a document the whole team reads, not a cosmetic
  staleness issue. (Not repeating the names here either, on the same principle — see
  `docs/ANSWERS.md` if you need them.)
- **Reintroduced Jaiveer's original `trajectory` spec** ("compare course to the bearing toward the
  origin *at closest approach*") as current guidance in `06_JAIVEER_AIS.md`, after it had been
  found geometrically unsatisfiable, fixed, and blessed (D27). Anyone re-reading that doc for the
  formula gets the broken one back.
- Deleted D23–D31 wholesale (nine rulings) and reset several closed items (GFW token, NOAA
  density, scene ids) back to "blocking"/"pending" text.

**Fix:** `git revert 626acce` for six of the seven files (exact match to `e1379b9`, verified with
`git diff e1379b9 -- <file>` = empty). Kept one genuine, non-leaking improvement `626acce` made to
`02_SOUM_DETECTION.md` (an updated, real run command for `case-jacksonville-2024` + a
`build_case.py`/TRAPS#21 reminder) by cherry-picking just that file's current content instead of
reverting it. Verified zero hits for the sealed vessel names anywhere outside the gitignored
`docs/ANSWERS.md`. Committed as `084d4c2` and pushed — `origin/main` no longer carries the leak.

**Lesson for whoever picks this up next, including a fresh AI session:** if you are asked to
"update the master plan" or any frozen-contract doc, **diff your intended output against what's
actually on disk (or the latest committed version) before writing it** — do not regenerate a
long-lived doc from a remembered/cached version of its own content. This is the doc equivalent of
TRAPS #21 (validating `out/` while the real file lives in `cases/`): a plausible-looking write to
the right path that is actually stale.

### GFW Arabian Sea coverage — ✅ confirmed, cases 5–6 keep `attribute`

`GFW_API_TOKEN` was already populated in `.env` (782 chars) this session. Ran
`python scripts/gfw_probe.py --all`:

| Case | Date | Presence | AIS-disabling events | SAR presence |
|---|---|---|---|---|
| case-mumbai-2023 | 2023-09-03 | ✅ | ✅ 10,992 returned | ✅ |
| case-jamnagar-2024 | 2024-02-23 | ✅ | ✅ 9,638 returned | ✅ |

Already recorded in `docs/receipts.md` (pre-existing, untouched by the regression). Propagated the
"done" status into Master Part 14 and `01_AKSHAT_INTEGRATION.md` A4/§1.5, which still read
"token empty" / "coverage unchecked" from the `e1379b9` baseline.

⚠️ **Open sub-item for Jaiveer:** the AIS-disabling-events counts (~10–11k) look like a wide-area
or global count, not local to the case bbox — unconfirmed whether that endpoint accepts a
region/bbox filter server-side. Filter client-side by position before using it as a local gap
statistic.

### Case 1 vessel flag — ✅ resolved

`docs/ANSWERS.md` flagged a CHN-vs-MID-563(Singapore) inconsistency on the case-1 MMSI. Cross-
checked the MMSI/IMO pair against three independent AIS registries (VesselTracker, VesselFinder,
MyShipTracking) — the old "CHN" note was simply wrong; flag is Singapore, consistent with MID 563,
and vessel type is Chemical/Oil Products Tanker (not "Other"). `docs/ANSWERS.md` updated with the
correction and sources. Case 2's vessel identity was deliberately **not** looked up — see "Open,
in priority order" above.

---

## [2026-09-12] Final unblock pass — pushed, frontend fixed, GFW confirmed

**Everything is on `origin/main`.** Two sessions of work were sitting on a local branch where
nobody could see it; `main` is fast-forwarded and pushed, ~123 MB of GeoTIFFs included.

**Frontend unblocked — and this is a logged ONE-OFF exception to D1.** Akshat's call. `web/` is
Harshita's, and the next `web/` bug still routes to her; this was done here only because it was
blocking four people's work from being visible at all.

- `loadCase.ts` fetched `detections.geojson` unconditionally and threw, so **all seven cases
  crashed the Detect screen.** Now gated on the `detect` act, and **a 404 degrades to
  `detections: null` + `detectionsPending`** instead of throwing. **Malformed JSON still throws** —
  missing ≠ broken, and that distinction is the whole point of `fetchJsonIfPresent`.
- `store.ts` carries `detectionsPending` and resets it per case, so Harshita can render *"Stage 1
  has not produced detections for this case yet"* rather than an empty map that reads as broken.
- `contracts.ts` was still mirroring the **v1** contract — missing `case_type`, `gallery`,
  `ais_source`, `known_origin`, `component_notes`, `discharge_class`, `ship_detections`, the origin
  age block, the four source types and the whole verification bundle. All added. `tsc --noEmit`
  and `next build` both clean; all 7 case routes return 200 with thumbnails.

**`scripts/sync_web_cases.py` (new).** Nothing copied bundles into `web/public/cases/`, so the app
could not see `cases/` at all. Skips `sar_vv_vh.tif`: **3.9 MB copied instead of 127 MB.**

**`docs/CONTRACTS.md` brought current to v4** with a precedence banner — Master §6 wins, mirror in
the same commit. It had been frozen at v1, which is exactly how `contracts.ts` drifted.

**GFW works. Cases 5 and 6 keep `attribute`.** And a false negative was caught in the act: the
first probe returned 403 everywhere and the script concluded *"no usable GFW coverage"*. It was
**Cloudflare error 1010 — urllib's user-agent is banned outright.** A transport failure, nothing to
do with the token or the data. With a normal user-agent all three endpoints answer for both cases.
**Two demo cases were one unexamined error message away from being dropped.** The script now names
that error instead of folding it into a coverage verdict.

**TRAPS #21–23 added:** the PASS that validated the wrong directory; GeoTIFF nodata is `-inf` and a
dark-spot detector will call it an enormous slick; and a component that scores identically for
every suspect is decoration, not evidence.

---

## [2026-09-12] Jaiveer's Phase 0/1 — hero confirmed, two specs broken, blindness declared per case

### The seam failure, which is what this file is for

**Jaiveer's `run.py` was writing to `out/` (gitignored) while `validate_case.py` reads
`cases/<id>/`.** So the PASS in his Phase 1 report was validating *our fixture*, not his output.
He found it and fixed it. Nobody did anything wrong — the two paths were never stated in the same
place — but it is the exact shape of failure that loses a demo: a green check measuring the wrong
thing. **The case folder is the hand-off medium; `build_case.py --stage attribute` is the publish
step.** If your validator passes and you have not run that, you have validated somebody else's file.

### The BLOCKING item is closed

Hero stands. 69-second reporting interval at the case-1 position, holding to 240 km, NOAA 30–31 Jul,
box 40–260 km offshore. No thinning. Distance corrected to **~170 km**, not ~100 km — fixed in four
places across the docs and in `meta.json`.

### Rulings — D27 to D31, all in Master Part 9

- **D27 `trajectory` was geometrically impossible as specified.** It compared course to the bearing
  toward the origin *at closest approach* — the one point where those are perpendicular by
  construction. 0.00 for 16 of 17 vessels. Jaiveer's fix is blessed (measure at the last report
  outside `radius_90_km`) **plus a `null` gate** for vessels never seen outside that radius, which
  is what stops the corrected version scoring 1.00 for 13 of 15. **No weight moves** until the
  Phase 8 ablation.
- **D28 `type_prior` gates to `null` on a homogeneous fleet.** 1.00 for all 17 is not a score, it is
  a constant that inflates everyone equally.
- **D29 `component_notes` blessed** into §6.7. Explanation, not evidence. Every `null` should carry
  one, because the UI renders `null` as "n/a" and an unexplained "n/a" reads as a broken feature.
- **D30 the gap story moves to case 4.** Case 1's Part 3 line was false and is rewritten.
  **STENA PROSPEROUS pre-registered** as a competing candidate, with the prediction that case 1 may
  return `partial`/`miss`, written down *before* the scoring run.
- **D31 blindness declared per case** — table in Part 16. Case 1 open, case 2 the headline blind
  result, cases 4–5 partially compromised and stated as such.

### The scrub

Alaska's dark-vessel identifier and coordinates, and Mumbai's infrastructure and dark-vessel ids,
were sitting in Master §3.2 — a document the whole team reads. Moved to `docs/ANSWERS.md`. (The ids
are deliberately not repeated here either; this log is as public as the file they came out of.)
The mechanical check, with the ids read out of the sealed file:

```bash
# take the identifiers out of the sealed file, then prove none of them appear anywhere public
grep -oE '`D[0-9.]+`|`[0-9]{6}`' docs/ANSWERS.md | tr -d '`' | sort -u > /tmp/ids
grep -rnFf /tmp/ids docs/ cases/ --exclude=ANSWERS.md   # must return nothing
rm /tmp/ids
```

Jaiveer also reported that §3.2 prints the case-1 MMSI. **It does not** — that was scrubbed during
the v4 rewrite; he is reading the v4 *draft*, not the committed file. Worth telling him so he is
working from the repo.

### Validator

`check_suspects` now takes `component_notes`, warns on a `null` with no note, and **warns when a
non-null component holds the same value for every scored suspect** — the check that catches a
`type_prior` of 1.00 across the fleet without anyone noticing by eye. `test_validator.py`
**18/18 → 21/21**.

### Still open

- **`.env` has `GFW_API_TOKEN=` empty.** The file is `.env.example` renamed; the token was never
  pasted in. `gfw_probe.py` cannot run until it is.

### The reply to Jaiveer — send this

> All seven points read. Four rulings, three answers, three questions back.
>
> **The density check is the most valuable thing anyone has produced this week** — it closed the
> one item that could still have forced a replan, and it closed it as a measurement rather than a
> hope. It also corrected the distance: ~170 km, not ~100 km. Fixed everywhere.
>
> **You were right about the gap claim and I've rewritten it (D30).** 714 broadcasts covering 14.0
> of 14 hours, longest silence 130 seconds — that is a result, not an inconclusive check, and the
> Part 3 line was simply false. The gap argument moves to Alaska, where a ship that never speaks at
> all makes the same point more strongly. **STENA PROSPEROUS is now written into Master §3.2 and
> Part 12 as a pre-registered competing candidate**, with the prediction that case 1 may come back
> `partial` or `miss`. Recording that *before* the run is worth far more than explaining it after,
> so thank you for flagging it rather than quietly hoping.
>
> **`trajectory` (D27) — your fix is blessed, with one addition.** You found a geometry error in a
> spec I wrote: closest approach is by definition where the bearing to the origin is perpendicular
> to the course, so a ±60° cone could never fire. Measuring at the last report outside
> `radius_90_km` is right. The addition: **a vessel with no report outside that radius gets `null`,
> not 1.0** — it was never observed approaching from anywhere. That is what stops the corrected
> version being tautological. `06_JAIVEER_AIS.md` §1.5 is rewritten, with the old version quoted and
> a note saying why it cannot come back.
>
> **`type_prior` (D28) — same treatment.** 1.00 for all 17 is a constant, not a score. Gate to
> `null` when every candidate shares a type class.
>
> **No weight moves on either, and this is the important part.** You did not propose one and you
> were right not to. A weight changed because a component looked weak on one real case is
> indistinguishable in December from a weight changed to make that case come out right. The Phase 8
> curve with a **per-component ablation** is the only thing that can justify touching them — that is
> now a named deliverable in Part 14.
>
> **`component_notes` — blessed (D29)**, with one condition: it is *explanation, not evidence*. It
> may not introduce a fact the card is not already showing. And **every `null` should carry one** —
> the UI renders `null` as "n/a" and an unexplained "n/a" looks like a broken feature instead of a
> deliberate refusal to measure the unmeasurable. The validator now warns on both.
>
> **The `out/` bug is in the integration log, not your update log**, because it is a seam failure
> and not your bug: the two paths were never written down in the same place. `build_case.py --stage
> attribute` is the publish step. Good catch — a green check measuring the wrong file is exactly how
> demos die.
>
> **On blindness (D31) — you were right to raise it and I have declared it per case rather than
> defended it.** Part 16 now carries a table: case 1 **open** (the density check *was* the answer),
> case 2 **blind and the headline result**, cases 4 and 5 **partially compromised** because their
> source coordinates were sitting in §3.2, cases 6–8 blind. Those coordinates are scrubbed into
> `ANSWERS.md`. *One correction in your favour: §3.2 does **not** print the case-1 MMSI — that came
> out during the v4 rewrite. You're reading the draft, not the committed file. Work from the repo.*
>
> **Case 1 is formally open**: use the documented vessel for diagnostics and worked examples, but
> **set no weight or threshold on it.** Weights come from injected scenarios only.
>
> **Three questions:**
> 1. **Is "eleven of 52" before or after the box-boundary fix?** Five were artefacts, so the honest
>    figure is either 11 or 6 — and we will be quoting it on a slide.
> 2. Does STENA PROSPEROUS survive that fix, or was it one of the five?
> 3. Confirm `component_notes` carries no vessel identity beyond what the card already shows.
>
> Nothing here blocks you. The abstention on real Galveston AIS (987 → 897 → 17, top two within
> 1.1%) is a demo asset and it is going on the honesty slide as-is.

---

## [2026-09-12] v4 case library landed — SEND THESE, ONE PER CASE, NOT BATCHED

Six real scenes are on disk. Three people have been building against fixtures. **Every message
below unblocks somebody different — send them separately so each lands as its own event.**

### 0. ~~Goes out FIRST — to Jaiveer~~ ✅ DONE, and it came back clean

The AIS-density check has been run and the hero is confirmed: **69-second reporting interval,
holding to 240 km, no thinning.** Nothing reshuffles. Replaced by the reply in the entry above —
send that instead, since it also carries the D27–D31 rulings he is waiting on.

### 1. Goes out SECOND — to everyone (rulings + the sealed file)

> Four rulings, all in `docs/00_MASTER_PLAN.md` Part 9:
> **D23** — SkyTruth Cerulean has a public API (no key). It gave us every full scene id, and it
> puts their reference polygon in each bundle as `cerulean_slick.geojson`. Soum: that is a
> comparison target, **not** ground truth, and you get it only after your detector has produced
> its own polygon — otherwise the IoU number isn't a measurement.
> **D24** — Jamnagar is "no investigation, no named party, no enforcement". **Never** "no record
> anywhere" — Cerulean logged it and a judge can pull that up in ten seconds.
> **D25** — Golden Ray is deleted; Ennore 2017 is archived to `cases/_archive/`. The Ennore slot
> is now the 30 Nov 2023 look-alike.
> **D26** — `bounds.json` ships `db_min`/`db_max`/`vh_available`. That is what the exporter has
> always written; the doc was wrong, not the code.
>
> Also: **`docs/ANSWERS.md` exists and I hold it.** Every documented outcome is in it, it is
> gitignored, and nobody else sees it until 15 September. Read `docs/ANSWERS.README.md` — it
> explains why, and why I will not answer "is this right?" this week. Two consequences for you:
> **cases are named after places, never vessels** (if a case id looks like a ship's name, that's a
> bug — tell me, don't rename it back), and **if you stumble on attribution data, don't paste it in
> here.** Cerulean's API hands back the polygon and the MMSIs in the same response.

### 2. Then one message per case. Template:

> **`<case_id>` is live.**
> Scene `<scene_id>` · `<detection_time>` · VV+VH, IW
> Box `W S E N` · `ais_source: <...>` · acts now: `["detect"]`
> On disk: `sar_vv_vh.tif` (2-band float32 dB @10 m), `sar.png`, `thumb.png`, `bounds.json`,
> `cerulean_slick.geojson`
> **Soum** — real-scene inference unblocked. **Anushka** — `detection_time` is real, fetch fields.
> **Jaiveer** — AIS window and box are above.
> `<the one thing that is specific to this case>`

Per-case "one thing", so no message is generic:

| case | the line that must be in its message |
|---|---|
| `case-jacksonville-2024` | HERO. ~170 km offshore, AIS density **verified at 69 s** — send it. Long sinuous chronic slick, runs the full height of the scene. **Not a gap case** (D30). |
| `case-farallones-2023` | **Three other Cerulean slicks share this scene**, two of them 6× larger. Ours is the 19.6 km one. A much bigger detection means a different slick, not a better one. |
| `case-huntington-2021` | Already exported. Its answer is **infrastructure** — naming a transiting vessel here would be wrong, and the NTSB agrees. |
| `case-gulf-alaska-2023` | 59.5 N — first case where `cos(lat)` bites; a degree of longitude is half as wide as at 30 N. Cerulean's human reviewer called this slick **AMBIGUOUS**; if your classifier hedges here, that's a result. |
| `case-mumbai-2023` | `gfw_hourly`: `gap` and `slowdown` must be **`null`, never 0**. Scene has bright point targets near the slick head — real ship/platform returns for the detector. |
| `case-jamnagar-2024` | `gfw_hourly`, same null rule. Scene-edge **nodata is `-inf`** over ~14% of the raster — do not read it as very low backscatter or you'll detect a giant fake slick. |
| `case-ennore-lookalike-2023` | **Correct answer is zero `oil` features.** Look-alikes are welcome and get shown grey with their rejection reason. Box contains the Chennai coast, so land runs bright (+4 dB). |

### State of every bundle right now

`python scripts/validate_case.py cases/` → all seven fail on **exactly one** thing each:
`detections.geojson`. No schema errors, no warnings. That is the intended handoff state — the
next file to exist in any bundle comes from Stage 1.

### Seam risks created by this change, logged so they are not a surprise

- **`web/lib/loadCase.ts` fetches `detections.geojson` unconditionally.** Every case is
  `acts_available: ["detect"]` with no detections yet, so the gallery will 404 on load until
  Soum's stage lands. Routed to Harshita: gate the fetch on the act, and render a "stage pending"
  state rather than throwing.
- **`case-nospill-zenodo` is scaffolded but deliberately NOT in `cases/index.json`** — it has no
  scene yet. Do not add it until Soum nominates one, or the gallery gets a dead card.
- **Case ids changed.** Anything pinned to `case-menuett-2024`, `case-panagia-2023`,
  `case-alaska-dark-2023`, `case-golden-ray-2021` or `case-ennore-2017` needs updating.
- **`verification.json` is intentionally absent** on the new cases. It contains the answer, so it
  gets written after a bundle validates, not before. See `verification/README.md`.

---

## [2026-09-10] D16 — trace-without-detect via `meta.known_origin`; Golden Ray + Ennore scaffolded

**The ruling (frozen-schema change, Akshat's).** `trace` may now run without `detect` when
`meta.json` carries **`known_origin`** — a documented fixed source (`[lon,lat]` or
`{lon,lat,label,source_url}`). `detections.geojson` is then not required. Master §6.1, Part 3
(Ennore), Part 9 (**D16**) updated. `docs/CONTRACTS.md` left frozen. The frontend must render such
an origin as *seeded from a documented source*, not a NAAP detection.

**Validator (`scripts/validate_case.py`, `test_validator.py` 12→14):** new `check_known_origin`
(shape-check + runs the pin through the existing lon/lat-swap detector); `check_meta` accepts
`known_origin` in place of `detect`; `check_detections` already gated on `"detect" in acts`. Two
new self-test mutations: trace act with neither detect nor known_origin (caught), and
`known_origin` written `[lat,lon]` (caught by the swap detector).

**Scaffolds:**
- `cases/case-golden-ray-2021/meta.json` — acts `["trace","attribute","verify"]`,
  `known_origin` wreck `[-81.40, 31.13]`. Validator now FAILs only on the missing stage outputs
  (`particles`/`origin`/`vessels`/`suspects`) + unfinished `verification.json` — the correct
  scaffold state.
- `cases/case-ennore-2017/meta.json` — acts `["trace","verify"]` (no `attribute`: no public
  Indian AIS). `known_origin` collision position **APPROX `[80.36, 13.235]`**, flagged in `notes`
  for Akshat to pin from the DG Shipping / INCOIS OSDAG report. Previously untracked — now needs
  `git add cases/case-ennore-2017/`.
- `verification/case-ennore-2017.json` (new) — `official_finding` drafted from widely-reported
  facts, with explicit TODO markers on `source_url`, IMO numbers and the oil-volume figure.
  `naap_result` + `assessment.explanation` are Phase-4 human TODO.
- `cases/index.json` → `["case-huntington-2021", "case-ennore-2017", "case-golden-ray-2021"]`.

### Routed to owners
- **Harshita:** `web/lib/loadCase.ts` fetches `detections.geojson` unconditionally (~L83–91) —
  gate on `"detect" in meta.acts_available` or known-source cases 404 on load. Trace origin card
  needs a "seeded from documented source: `<known_origin.label>`" state. `contracts.ts` `CaseMeta`
  → optional `known_origin`.
- **Anushka:** drift stage seeds from `meta.known_origin` when `detections.geojson` is absent
  (Golden Ray, Ennore). Ensemble / origin grid / forward drift unchanged.
- **Jaiveer:** Golden Ray `vessels.geojson` + `suspects.json` — NOAA AIS St Simons Sound
  ~31 Jul–9 Aug 2021; salvage fleet (VB-10000, T&T Salvage) → `excluded[]` as responders; wreck
  → `infrastructure[]`. Ennore has no attribute act.

### Draft broadcast for the group (Akshat sends)
> 🚩 **Contract change D16 — `meta.known_origin`.** Cases with no SAR-visible slick but a
> documented source (Golden Ray wreck, Ennore collision) now run `trace`/`attribute`/`verify`
> without `detect`. `meta.json` gets an optional `known_origin` (`[lon,lat]` or
> `{lon,lat,label,source_url}`); when it's set, `detections.geojson` isn't required. Master §6.1
> + Part 9 (D16). Validator already enforces it (`test_validator.py` 14/14).
> - **Harshita:** `loadCase.ts` must stop fetching `detections.geojson` unconditionally — gate on
>   `"detect" in acts_available`. Origin card: "seeded from documented source", not a detection.
> - **Anushka:** seed the trace from `meta.known_origin` when there's no `detections.geojson`
>   (Golden Ray, Ennore).
> - **Jaiveer:** Golden Ray is on — NOAA AIS St Simons Sound 31 Jul–9 Aug 2021, salvage fleet
>   excluded as responders, wreck as an infrastructure finding.

---

## [2026-09-10] Phase 1 — Huntington Beach confirmed (hero); Golden Ray + Ennore show no SAR slick

**Merge is live.** `origin/main` now carries the 4-branch merge + validator hardening + exporter
(Akshat pushed; soum/jaiveer/anushka branches deleted). `origin/harshita` has 4 newer web
commits (data-driven gallery reading `cases/index.json`, `verify` added to `ALL_ACTS`) —
fast-forwarded into local `main` this session, **not yet pushed** (Akshat: `git push`, or PR).

**New tooling:** `scripts/find_scenes.py` (generalised `check_ennore.py` — any bbox/window, no
hardcoded verdict), `scripts/inspect_db.py` (VV/VH dB point sampler — committed).

### Case 2 — Huntington Beach: CONFIRMED, this is the hero detection case

```
scene       S1A_IW_GRDH_1SDV_20211002T015821_20211002T015850_039934_04B9C9_2BF9
acquired    2021-10-02T01:58:21Z   (S1A ascending, ~2.8 h after the first leak alarm)
bounds      W -118.17  S 33.585  E -118.05  N 33.70    (bbox tight on the slick)
bands       VV + VH + angle        vh_available: true
```

A clean, sharp-edged comma-shaped slick sits dead centre, ~8–10 dB below the surrounding sea in
VV (dense-grid dB sampling; VH baseline near noise floor so VH depression is weak but the
morphology is unambiguous). The anchorage (hundreds of container ships — the 2021 congestion) is
all in frame. Short rewind: oil was only ~3 h old at the pass. `cases/case-huntington-2021/`
holds all four artefacts, **committed** (the `.tif` now travels in git — `.gitignore`
whitelists `cases/*/sar_vv_vh.tif`). The GeoTIFF downloaded directly (8.6 MB, no Drive round
trip): 1112×1271, 2-band float32, bands labelled VV/VH, EPSG:4326, bounds == `bounds.json`, VV
median −20 dB. Two stale `case-huntington-2021_sar_vv_vh` toDrive files sit in Akshat's
Drive/naap_exports/ from earlier `--drive` runs — superseded, safe to delete.

**Draft announcement for the group (do not batch — send this one now):**
> 🚩 Case locked: **Huntington Beach / San Pedro Bay Pipeline, Oct 2021**
> scene `S1A_IW_GRDH_1SDV_20211002T015821_20211002T015850_039934_04B9C9_2BF9`
> detection_time `2021-10-02T01:58:21Z` · bounds `[-118.17, 33.585, -118.05, 33.70]` · VV+VH
> Clear oil slick in SAR. NTSB MIR-24-01: MSC DANIT (IMO 9404649) + "Beijing" dragged anchor
> 25 Jan 2021, pipeline leaked 8 months later → infrastructure + exoneration case.
> Soum: `sar.png` + `bounds.json` up now, 2-band GeoTIFF landing shortly.
> Jaiveer: NOAA AIS for San Pedro Bay, 30 Sep – 3 Oct 2021.
> Anushka: HYCOM/ERA5 for the box, detection_time − 30 h → detection_time.

### Case 1 (Ennore) and Case 3 (Golden Ray): no SAR-visible slick — decision needed

Both are enclosed/sheltered calm water imaged at low wind → dark, low-contrast SAR with no
coherent VV+VH depression (dB sampling confirms the eyeball read on both).
- **Ennore** `..._6D04` (2017-01-29 00:31Z, dawn): filaments near the port mouth, nothing that
  reads as oil vs. a wind shadow or freshwater plume. Akshat is still working this one.
- **Golden Ray** `..._C7D5` (2021-08-08 23:29Z, +9 d — the only S1 pass covering the sound, on a
  12-day ascending repeat): sound + Atlantic uniformly dark, no slick. The wreck + VB-10000
  salvage cluster images clearly at ~(-81.40, 31.13). `cases/case-golden-ray-2021/` has a
  scene-only scaffold with an honest `notes` block.

**The call (Akshat's):** run Golden Ray — and likely Ennore — as **trace + attribute + verify
seeded from the documented known source**, not as detection cases. Golden Ray is a strong
infrastructure/exoneration case even without a SAR detection (origin on the wreck, salvage fleet
excluded as responders — exactly the D10 story). This needs one contract change:
`validate_case.py check_meta` currently errors on `trace` without `detect`. Relax it to allow a
`["trace","attribute","verify"]` bundle whose origin is a known fixed source (add a
`meta.known_origin: [lon,lat]` field, documented). Small change; I did not make it — it's a
frozen-schema decision.

`cases/index.json` → `["case-huntington-2021", "case-golden-ray-2021"]`, default huntington.
`case-000` is not in the gallery index (validator fixture only). `case-ennore-2017` is untracked
and left alone for Akshat — add it to the index when its strategy is settled.

`verification/case-huntington-2021.json` and `verification/case-golden-ray-2021.json` scaffolded:
`official_finding` is researched and citable; `assessment.explanation` is a Phase-4 HUMAN-PROSE
TODO and the files deliberately won't validate until written.

### Cases 4 & 5 — Urooz (draft ask for Akshat to forward)
> Urooz — case-selection research, blocks Jaiveer's AIS download. Find **two** transiting-vessel
> oil discharges in **US waters**, **Oct 2014 – Sep 2024**, ideally different basins:
> 1. SkyTruth Cerulean — map `cerulean.skytruth.org`, or API `api.cerulean.skytruth.org`
>    (OGC-compliant). Filter to US waters; want a clean linear slick attributed to a named
>    vessel with an MMSI.
> 2. Fallbacks: NOAA Incident News archive, USCG investigation reports.
> For each candidate give: date/time, lat-lon, vessel name + MMSI, the Cerulean/report URL.
> Caveat to record: *"Cerulean attributed this slick to vessel X"*, never *"proven responsible"*.
> Then Akshat runs `scripts/find_scenes.py` to confirm Sentinel-1 coverage.

### Cases 6 & 7 — Soum (draft ask)
> Soum — nominate the two detect-only demo scenes from **Zenodo Part III** (DOI
> 10.5281/zenodo.13761290): one **look-alike** (`Lookalike/` folder) where the dark feature is
> genuinely convincing, and one **clean ocean** (`No oil/` folder). Give the folder/scene names.
> Correct NAAP output on both is zero oil features. We'll wrap each as a case bundle.

### Part B rulings — still not broadcast (Phase 0.3). Draft for Akshat to send:
> Rulings, all blocking someone:
> - **B1 BitmapLayer, not HeatmapLayer** for the origin grid — HeatmapLayer renormalises per
>   viewport so the answer changes as a judge zooms (D11). `web/CLAUDE.md` fixed; Harshita's
>   `MapView.tsx` still imports HeatmapLayer — needs the switch.
> - **B2 `time_window_method` is in the contract** — ships as-is; frontend renders a `bounded`
>   bracket differently from a measurement.
> - **B3 Jaiveer scores the origin grid, not the r50 circle** (44.7% of high-prob mass sits
>   outside r50 on the real cloud shape).
> - **B4 Fund the adaptive field-box pad + the loud edge guard** (Gulf Loop covers 156 km/24 h
>   vs a fixed 55 km pad).
> - **B5 Tug/tow are display labels only** — no `type_prior` change on a one-port sample.
> - **B6 Approve Jaiveer's extended `suspects.json`** (source_type, per-component null,
>   dark_vessels, infrastructure) — already in the validator and CONTRACTS pointer.
> - **B7 2-band float32 GeoTIFF exports, committed** — done; `gee_scene.py` produces it.

---

## [2026-09-09] Handoff #2 — four branches merged to main, validator hardened

**The merge.** `origin/{soum, jaiveer, harshita, anushka}` all merged onto `main` (was 2 commits
while four branches held the whole project — the top catastrophic risk in the plan). Order:
soum → jaiveer → harshita clean; anushka had 2 trivial conflicts (`docs/03_ANUSHKA_DRIFT.md`
HYCOM line — took main's v3, which already carries the ÷1000 correction; `docs/SETUP_ANUSHKA.md`
modify/delete — dropped, it's a v1 doc). Landed on a local `integration` branch; **not pushed —
Akshat pushes.**

- **Soum's** `data/labels/features_t25.csv` + `features_with_vh.csv` (~4000 rows each) were
  force-added past `.gitignore` — removed from the merge, they stay local on his machine.
  `classifier.pkl` (5.4 MB) kept — the detector needs it.
- **Anushka** had already fixed the ÷100 → ÷1000 bug repo-wide (TRAPS #2 + 9 other files,
  verified 2026-09-07). Adopted as canonical. Fixed one leftover contradictory sentence in
  `check_gee.py`.
- **Harshita's** `web/` (full Next.js app) merged clean. Her case-000 particle-seeding fix
  (`axis = radians(24)`) is in.

**Validator hardening** (`scripts/validate_case.py`, `test_validator.py` now 12/12):
`check_verification` (Master §6.8), `check_index` (`validate_case.py cases/` validates the index
+ every listed case), `origin.bounds` sanity + off-scene renderability warning, `area_km2` vs
polygon shoelace, extended `suspects.json` (`source_type`, `components` null, `dark_vessels[]`
with `mmsi: null`, `infrastructure[]`), `verify` is a valid act, Box pad 2.0→0.5°, utf-8.

**`build_case.py`:** gathers `verification/<case>.json` → `verification.json`, optional
`particles_forward.json`, notes missing `sar_vv_vh.tif`/`thumb.png`; `--reindex` rewrites
`cases/index.json`. **`gee_scene.py`** rewritten for the 4-artefact 2-band GeoTIFF export
(ruling D14) — still zero GEE contact, first real run is Akshat's.

**Dry run (the "you've never run the pipeline" check):** built a fresh `case-dry` end to end
through all three stubs + `build_case.py` → final PASS, 0 warnings. Found + fixed: the detect
stub and `make_case000` emitted a hardcoded `area_km2` that tripped the new shoelace check —
both now compute it from the polygon.

**State:** `integration` branch = `main` + 4 branches + this work. `validate_case.py cases/`
PASSES. Awaiting Akshat: push; then the two frontend items below.

**Routed to owners:**
- **Harshita:** `web/components/MapView.tsx` implements `HeatmapLayer` for the origin — must
  become `BitmapLayer` (ruling D11). `web/lib/contracts.ts` `ALL_ACTS` needs `"verify"` added
  (screen 4) — `loadCase.ts` currently throws on it.
- **Akshat:** GEE auth → `check_ennore.py` → case selection; Part B broadcast; Phase 4
  `verification.json` prose.

---

## [2026-09-06] Handoff #1 — contracts frozen, case-000 published, all stubs wired

**Published:** `docs/CONTRACTS.md` (frozen) · `cases/case-000/` (fake, full-size: 3000 particles
× 97 steps, 8.4 MB) · a working `--stub` in every stage · `scripts/validate_case.py` +
`scripts/test_validator.py`.

**Validator:** PASS on `case-000`, 0 errors, 0 warnings.

**Seam test:** ran the full chain on a scene-only case (`case-smoke`) with all three stubs,
publishing each stage into the case folder before the next read it. Final assemble validated
PASS. So the architecture is proven wired before any real logic exists — which was the whole
point of today.

**Verified by eye:** drift stub seeded from `det-01` (`shape_class: "linear"`, so along the
principal axis, as the contract requires) and particle 0 travelled 29.2 km over the 24 h rewind
— tens of km per day, which is what an ocean actually does. Origin cloud r50 = 5.5 km,
r90 = 9.9 km, `abstain: false`. Attribution funnel 412 → 63 → 12 → 3, monotonic, with 2
exclusions carrying stated reasons.

**One design point discovered while wiring, worth knowing:** the case folder is the hand-off
medium, so Stage 2 genuinely cannot read Stage 1 until Stage 1's output has been *published*
into `cases/<id>/`. `build_case.py --stage <act>` does that publish step without validating an
incomplete bundle. The stage `out/` directories are working space; the case folder is the
contract.

**State:** `cases/case-000` PASSES with acts `["detect", "trace", "attribute"]`. Everyone can
build against it now.

**Not yet done — the real Phase 0:** the Ennore Sentinel-1 scene is still unverified. No GEE
call has been made from this repo. `scripts/check_ennore.py` and `pipeline/export/gee_scene.py`
are written and syntax-checked but unrun, so both should be assumed to need a round of fixing on
first contact with the API.

**Next seam events expected:**
- **Handoff #2, Mon evening** — Akshat → Soum: real `sar.png` + `bounds.json` for Ennore.
- **Handoff #3, Tue evening** — Soum → repo: real `detections.geojson`; Anushka → repo: real
  `particles.json` + `origin.json`.
- **Handoff #4, Wed morning** — first real wiring. Expected bug classes, in the order they
  usually appear: lon/lat swaps (validator catches by name), timestamps off by hours (compare
  `meta.detection_time` against `particles.t0`), particles seeded off the polygon (plot
  detections and `positions[0]` together — they must overlap), origin cloud on land
  (bounds/indexing bug in `origin.json`).
