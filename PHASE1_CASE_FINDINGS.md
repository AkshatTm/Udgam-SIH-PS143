# Phase 1 — Case Selection Findings

*Akshat · 2026-09-10 · what the Sentinel-1 scenes actually show for the three spill cases.*

> **TL;DR.** Huntington Beach has a clean, sharp oil slick in SAR — it is the hero detection
> case. **Ennore and Golden Ray have no SAR-visible slick** (enclosed / sheltered calm water,
> low wind → dark sea, no contrast for oil to damp against). Both still work as
> *trace + verify from a documented known source*. Keep Ennore. Golden Ray is a
> keep-or-replace decision. Cases 4–7 are unstarted and now matter more.

---

## 1. What was done

GEE auth is live (project `quizzer-dev-487316`). For each of the three spill cases I ran:

1. `scripts/find_scenes.py` — list every Sentinel-1 IW pass over the search box in the window.
2. `pipeline/export/gee_scene.py --no-geotiff` — pull the VV display raster, look at it.
3. `scripts/inspect_db.py` + dense-grid dB sampling — measure VV/VH backscatter on the
   suspected slick vs. clean sea. **A real oil slick sits several dB below clean sea in both
   VV and VH.** Wind look-alikes are dark in VV only; glassy water shows nothing in either.

---

## 2. Results

| Case | Scene | Acquired (UTC) | vs incident | Slick in SAR? | Evidence |
|---|---|---|---|---|---|
| **Huntington Beach** | `S1A_..._20211002T015821..._2BF9` | 2021-10-02 01:58:21Z | +2.8 h after first leak alarm | **YES — clear** | Sharp comma-shaped slick, dead centre. Grid dB: sea median −20.9 dB VV, slick core −28 to −32 dB → **~8–10 dB VV depression**. Unambiguous morphology (crisp boundary, not a gradient). |
| **Golden Ray** | `S1A_..._20210808T232953..._C7D5` | 2021-08-08 23:29:53Z | +9 d after the 31 Jul release | **NO** | Sound + Atlantic uniformly dark. Grid dB: VV median −20.9, scattered −28 to −32 cells but **no coherent feature** — speckle, not a slick. VH at noise floor. Only S1 coverage of the sound is a 12-day ascending repeat, so no better pass exists. |
| **Ennore** | `S1A_..._20170129T003132..._6D04` | 2017-01-29 00:31:32Z | +1.0 d after the 28 Jan collision | **NO** | 06:01 IST dawn pass, near-zero wind. Coast-parallel transect: near-vs-offshore VV differences swing ±3–6 dB **at random**; VH damping essentially zero. Curvilinear dark filaments near the port mouth read as a wind shadow / freshwater plume, not oil. |

**Scene files on disk:** `cases/case-huntington-2021/` and `cases/case-golden-ray-2021/` hold
`meta.json` (v3) + `bounds.json` + `sar.png` + `thumb.png`. Huntington's 2-band
`sar_vv_vh.tif` finished as an Earth Engine Drive export (`naap_exports/`). `case-ennore-2017/`
is Akshat's — left untouched.

---

## 3. Why two of three show nothing

It is the same failure mode, and it is worth a sentence on the honesty slide:

- **SAR sees oil because oil damps the small (Bragg-scale) capillary waves that roughen the
  sea.** No roughness to damp → no signal. A glassy, sheltered, low-wind sea is *already* dark,
  so a slick has nothing to stand out against, and the cross-pol (VH) channel is sitting on the
  instrument noise floor with no dynamic range left.
- **Huntington worked** because San Pedro Bay is open enough, there was enough wind for a grey
  speckled backdrop, and the slick was hours old and thick.
- **Golden Ray** (enclosed sound) and **Ennore** (dawn, no wind) did not.

This is a real, defensible property of the sensor — *"SAR oil detection needs a roughened sea;
that is a known operational limit, and it is exactly why the system does not rest on detection
alone."* It is not a bug in our pipeline.

---

## 4. What each case becomes

### Huntington Beach — hero, full chain (`detect · trace · attribute · verify`)
Ship the scene to Soum / Anushka / Jaiveer now. Expected story: origin lands on the San Pedro
Bay Pipeline right-of-way; every transiting vessel excluded; verdict **hit** with Jaiveer's
infrastructure module (which is what the NTSB concluded — MSC DANIT + Beijing dragged anchor
25 Jan 2021, the pipeline leaked 8 months later). Caveat carries the case: *no vessel was the
proximate source at detection time.*

### Ennore — KEEP. Run as `trace · verify` from the known collision point
The India-relevance case does not need a NAAP detection to make its point. Seed the drift from
the documented collision location (~13.24 N, 80.34 E, MT Dawn Kanchipuram × MT BW Maple,
28 Jan 2017) and benchmark the forward drift against the INCOIS advisory. The Verify screen
shows the honest low-contrast SAR and says plainly: *"the dawn pass was too calm to image the
slick — here is the scene — but the source is known, and here is where the physics says the oil
went."* No AIS for Indian waters anyway, so no `attribute` act — which is itself part of the
point we are making.

### Golden Ray — KEEP-OR-REPLACE (your call)
- **Keep** as an infrastructure / exoneration case: `trace · attribute · verify` seeded from
  the wreck position (~31.13 N, 81.40 W). Origin on the wreck; the salvage fleet (VB-10000,
  tugs) shows in AIS and is **excluded as responders** — the D10 story, and a good one. The
  wreck + salvage cluster images perfectly in the scene we have.
- **Replace** with a transiting-vessel Cerulean case (case 4) that *is* SAR-visible, and demote
  Golden Ray or drop it. Cleaner if cases 4/5 come through strong.

Recommendation: **keep it as a trace case for now**, revisit once Urooz delivers cases 4/5. It
costs little to carry and the infrastructure-exoneration angle is distinctive.

---

## 5. Contract implication

`scripts/validate_case.py` (`check_meta`) currently **errors on `trace` without `detect`**
("trace needs a slick to seed from"). Ennore and (if kept) Golden Ray need a bundle with
`acts_available` = `["trace", ...]` and **no `detect`**, seeded from a documented origin.

**Proposed change (frozen schema — Akshat approves):**
- Relax the rule: `trace` without `detect` is allowed **iff** `meta.known_origin` is present.
- Add `meta.known_origin: [lon, lat]` — the documented source coordinate, with a
  `meta.known_origin_source` string (the citation).
- The Trace stage seeds from `known_origin` instead of `detections.geojson` when there is no
  detect act.
- Propagate to `docs/00_MASTER_PLAN.md` §6.1 and the CONTRACTS pointer.

Small change. I have not made it.

---

## 6. Still open

| Item | Owner | Status |
|---|---|---|
| Cases 4 & 5 — transiting-vessel discharges, US waters, SAR-visible | Urooz | not started; **matters more now** — draft ask in `_INTEGRATION.md`. Cerulean API is at `api.cerulean.skytruth.org`. |
| Cases 6 & 7 — look-alike + clean-ocean from Zenodo Part III | Soum | not started; draft ask in `_INTEGRATION.md` |
| Precise Huntington rupture coordinate | Akshat | `~4.5 nm offshore` — pin from NTSB MIR-24-01 for Phase 4 |
| `trace`-without-`detect` contract change | Akshat | ruling needed (§5 above) |
| Golden Ray keep/replace | Akshat | decision (§4 above) |
| `verification/*.json` prose | Akshat | Phase 4 — `official_finding` researched, `assessment` is a HUMAN-PROSE TODO |
| Send the 4 drafted messages (Huntington announce, Urooz 4/5, Soum 6/7, Part B) | Akshat | in `_INTEGRATION.md` |

---

## 7. Case library after this session

| # | Case | Type | Acts (planned) | State |
|---|---|---|---|---|
| 1 | Ennore, Chennai — 29 Jan 2017 | spill | trace · verify | scene locked; no SAR slick; trace-from-known-origin |
| 2 | **Huntington Beach — 2 Oct 2021** | spill | detect · trace · attribute · verify | **scene confirmed, slick clear, scaffolded** |
| 3 | Golden Ray — 8 Aug 2021 | spill | trace · attribute · verify | scene locked; no SAR slick; keep-or-replace |
| 4 | TBD — vessel, US waters | spill | all | Urooz researching |
| 5 | TBD — vessel, US waters | spill | all | Urooz researching |
| 6 | Look-alike (Zenodo Part III) | lookalike | detect | Soum picks |
| 7 | No-spill (Zenodo Part III) | nospill | detect | Soum picks |
