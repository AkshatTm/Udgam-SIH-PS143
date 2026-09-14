# Stage 3 — Attribution: progress report

**Jaiveer · 13 September 2026 · for Akshat**
**Branch:** `jaiveer-phase2` · **Freeze:** Tue 15 Sept 05:00

---

## Status at a glance

| Phase | State |
|---|---|
| 0 · Unblock + the Menuett block | **Done** — all items, including the blocking task |
| 1 · The core scorer | **Done** — runs end to end, validator PASS, 0 warnings |
| 2 · Parity, head-proximity, temporality | Blocked — needs Soumirya's slick polygon |
| 3 · Dark vessel | Blocked — needs Soumirya's `ship_detections` |
| 4 · Infrastructure | Not started |
| 5 · Traffic prior | Not started |
| 6 · Repeat offenders | Not started — and structurally undemonstrable, see below |
| 7 · Chronic vs acute | Blocked — needs `discharge_class` |
| 8 · Evaluation curve | **Starting now.** My critical path |
| 9 · Real cases | Blocked — needs Anushka's real `origin.json` |
| 10 · Robustness | 10.3 done (R10 closed), rest pending |

**I am not the long pole.** Real per-case runs are gated on Stage 2, and that was true before
Soumirya's Layer 2 news.

---

## What runs today

```bash
python pipeline/attribute/tests.py
python pipeline/attribute/make_fake_case.py
python pipeline/attribute/score.py --case-dir pipeline/attribute/fixtures/case-gulf-fake \
       --parquet data/ais/gulf.parquet --ranking
python scripts/validate_case.py pipeline/attribute/fixtures/case-gulf-fake
```

**Real Galveston AIS, 25 Jan 2023:**

```
funnel   987 -> 897 -> 17 -> 0      (15 dropped for < 5 reports)
ABSTAINED  the top two vessels score within a few percent of each other
PASS       acts=['detect','trace','attribute']  (0 warnings)
```

The zero is the **refusal firing, not a failure** — top two 1.1% apart, which on a patch of ocean
with no actual spill is the correct answer. Moving the origin to a quieter position produces a
clean top-3 with two stated exclusions, also PASS with 0 warnings. **Both paths are demonstrable
on real data today.**

**R10 is closed.** Identical ranking on Linux/container and Windows/Python 3.11.

### Files

| File | What |
|---|---|
| `ingest.py` | NOAA CSV → Parquet, filter-on-scan. **+ day-continuity guard** (D6) |
| `tracks.py` | per-MMSI tracks, 30-min interpolation ceiling |
| `geo.py` | **new** — haversine, bearing, angular difference, `OriginGrid` (row 0 = NORTH) |
| `score.py` | **new** — seven components, funnel, exclusions, abstention. Writes into the bundle |
| `tests.py` | **new** — 63 stdlib assertions, mutation-tested ten ways |
| `make_fake_case.py` | **new** — US-located fixture, 4:1 streak cloud so it exercises D8 |

---

## What I need from you

**1. Edit Master Part 3.** Menuett is not "the only case that exercises gap detection". Measured:
the vessel broadcast **714 times inside Cerulean's own −8h/+6h window — 14.0 hours of 14, no
coverage hole at either end — longest silence 130 seconds.** The window is fully covered, so this
is a finding, not an inconclusive check. Part 3.2 also says ~100 km offshore; it is **170 km**.

**2. Where does the gap story live instead?** My proposal: **Alaska.** A dark vessel is a ship that
never speaks at all — the same argument in its strongest form, already in the library, and unlike
Menuett's gap it is actually in the data. Back it with the Phase 8 curve.

**3. `trajectory` needs a ruling.** As specified it **cannot fire**: 0.00 for 16 of 17 vessels,
median 126° off. That is geometry, not data — at closest approach the bearing to the origin is
perpendicular to your course, so a ±60° cone can never be satisfied. I fixed *where* it is measured
(last report before closest approach at which the vessel was still outside `radius_90_km`), which
is the same class of change as D9. **But corrected it scores 1.00 for 13 of 15**, because any
vessel that ended up inside the cloud was by definition heading toward it. Near-tautological, for
15% of the weight. **No weight touched** — that is Phase 8's job or yours.

**4. `component_notes` extends §6.7.** A per-component string carrying the stated gate reason, e.g.
*"39-minute silence, but the vessel was not under way on both sides of it — moored, not dark"*.
It makes D9's "stated rules, not quiet conditionals" visible on the card. Bless it or I drop it.

**5. Blind evaluation does not hold for cases 1, 2, 4 and 5.** The Menuett density check cannot be
run blind — finding the vessel *is* the check, and it sorts first by report count. Part 3.2 also
prints the MMSIs for cases 1 and 2 and the dark-vessel coordinates for 4 and 5, which for a dark
vessel *is* the answer since there is no name to withhold. Better stated openly than found by a
panel in December.

**6. `ship_detections` still cannot support the dark-vessel gates.** §6.3 gives `lon, lat, px_area,
peak_db`. Phase 3.3 gates on ">30 m estimated length, high confidence" and §6.7 requires
`est_length_m`. Neither field exists. Either Soumirya adds them, or I derive length from `px_area` plus
the pixel scale and ship with no confidence gate — which makes D5 materially worse.

**7. Which decision log is current?** Your handoff cites **D27/D31**; the master plan I hold is v4
and stops at **D22**. Either there is a newer plan I have not been sent, or those references are
wrong. Being two versions behind is what cost me a day on the 11th.

---

## Answers to your three questions

**Q1 — "eleven of 52", before or after the box-boundary fix?** Before. **After the fix it is 6.**
Use 6 on the slide. The split is unusually clean: all five removed were among the five *longest*
"silences" (306–1399 min) and every one began exactly on the search boundary; the six that survive
are 57–144 min and all began mid-box. Worth saying on the slide that the artefacts were the
*biggest* numbers — an ungated version would have led with a 23-hour blackout that was a ship
sailing out of a rectangle.

**Q2 — does STENA PROSPEROUS survive?** Yes. Genuine, 142.3 min, began mid-box at −79.29, 29.27.
The competing-candidate problem on Menuett stands: it is 7.4 km from the slick, under way at
12.5 kn, and takes the full `gap` 15% while the documented vessel takes zero.

**Q3 — does `component_notes` leak identity?** No. All 119 notes across 17 vessels checked:
**zero vessel names, zero MMSIs.** IMO and callsign are never read by `score.py`. Ten distinct
wordings, all measurements and gate reasons, every value derived from the AIS the card already
cites.

---

## Findings, with the evidence behind them

| Finding | Evidence |
|---|---|
| Menuett is not a gap case | 714 reports across 14.0 of Cerulean's 14 h window; worst silence 130 s |
| `gap` favours the wrong vessel there | STENA PROSPEROUS 142 min at 7.4 km vs the documented vessel at 0 |
| Box exits look identical to going dark | 5 of 11 under-way silences resumed exactly on the boundary. **Gate added** |
| `trajectory` as specified cannot fire | 0.00 for 16 of 17, median 126° off |
| `type_prior` discriminates nothing offshore | 1.00 for all 17 — an offshore lane is all tankers and cargo |
| A vessel on the origin peak can rank second | EVERGLADES, grid 0.98 at 2.3 km, below AP REVELIN at 0.31 and 17 km |
| Repeat offenders is undemonstrable | The two vessel cases are Atlantic and Pacific; no vessel appears in both. Reframe as roadmap |

**Nothing above was fixed by changing a weight.** Every one of them could be, and that is precisely
what D21 exists to prevent.

---

## Blocked on

| Need | From | Unblocks |
|---|---|---|
| Real `origin.json` per case | Anushka | Phase 9 — every real run |
| `discharge_class` | Soumirya | Phases 2 and 7 |
| `ship_detections` + length/confidence | Soumirya | Phase 3, Alaska |

Stubs are enough for 2, 3 and 7 — `ship_detections: []` would unblock the whole dark-vessel module
today.

---

## Next

**Phase 8, the injected-offender curve.** It needs nobody, it is a named deliverable in Part 14, and
it is the only legitimate way to settle the `trajectory` and `type_prior` weight questions above.
Real AIS traffic plus a synthetic guilty vessel whose discharge point, gap, speed profile and
manoeuvre I control; sweep traffic density, gap duration, cloud size and sampling rate; report
top-3 rate with a stated operating limit.

Also queued and dependency-free: the GFW events-endpoint bbox check for cases 5 and 6, and the
sampling-density experiment (downsample Menuett to hourly, re-score, report the rank change).
