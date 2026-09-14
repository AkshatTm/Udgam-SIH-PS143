# Stage 3 Phase 8 — the injected-offender curve

*Built and run 14 Sept (Akshat, on Jaiveer's design from `docs/_archive/jaiveer/stage3-progress-2026-09-13-evening.md` §8.3).
Tool: `pipeline/attribute/evaluate.py`. Raw results: `pipeline/attribute/results/phase8_*.json`.*

## Why it exists

Every attribution number we could otherwise quote would come from a case whose answer we know,
which is what D21 forbids. This is the alternative: **real AIS traffic, a synthetic guilty vessel
whose discharge point, transponder gap, speed profile, course and type we control**, and therefore
a rank we can check. It also answers the two open weight questions (A5 `trajectory`, A6
`type_prior`) by ablation instead of by argument.

**No weight was changed by any of this.** The script measures; the ruling stays Akshat's.

## What it measures — and what it does not

The offender is injected into a real fleet, at a real time, **on top of a real vessel's position**,
so the competitors are genuine traffic. The origin cloud is synthetic, elongated 4:1, sized to a
target r90, and by default centred **0.5 × r90 away from the true discharge point**, because Stage 2
has its own error and a scorer that only works on a perfect origin is not what we ship.

> **The quoting rule.** These are **ranking** numbers, given an origin cloud of stated quality. They
> are an **upper bound** on end-to-end performance and they are **not** an accuracy figure for the
> six live cases. A real fleet contains no labelled offender to check against — that is the whole
> reason this file exists.

**Abstention is counted separately, never as a hit or a miss.** A refusal is a designed outcome;
folding it into either column would make it look like an answer.

## Results

**Offshore (`jacksonville.parquet`, 46 real vessels, 300 trials per point).** Baseline is r90 10 km,
origin error 0.5 × r90, a 45-minute gap, dense AIS. Rates are over decided (non-abstained) trials,
with a 95% Wilson interval.

| condition | top-1 | top-3 | abstained | median plausible set |
|---|---|---|---|---|
| **baseline** | **0.910** [0.87–0.94] | 0.964 | 23/300 | 3 |
| origin error 0 (perfect cloud) | 1.000 [0.99–1.00] | 1.000 | 11 | 3 |
| origin error 1.0 × r90 | 0.653 [0.59–0.71] | 0.780 | 64 | 2 |
| cloud r90 3 km | 0.906 | 0.968 | 22 | 2 |
| cloud r90 25 km | 0.777 [0.72–0.82] | 0.938 | 26 | 4 |
| traffic × 0.25 | 0.979 | 0.989 | 19 | 1 |
| traffic × 1.0 | 0.910 | 0.964 | 23 | 3 |
| no gap injected | 0.681 [0.62–0.73] | 0.938 | 40 | 3 |
| hourly AIS (GFW regime) | **0.488** [0.42–0.56] | 0.662 | 93 | 2 |
| **offender with no behavioural signature** | **0.556** [0.49–0.62] | 0.923 | 52 | 3 |

**Crowded port (`huntington.parquet`, 100 real vessels, 150 trials, baseline r90 3 km).**

| condition | top-1 | top-3 | abstained | median plausible set |
|---|---|---|---|---|
| baseline | 0.782 [0.70–0.85] | 0.960 | 26/150 | 9.5 |
| cloud r90 10 km | 0.765 | 0.857 | 52 | 29 |
| cloud r90 25 km | 0.718 | 0.769 | 111 | 50 |
| hourly AIS | 0.296 [0.22–0.39] | 0.461 | 35 | 5 |

Three things fall out of that pair, and all three are worth saying on stage:

1. **Sampling density is the single biggest lever.** Dense → hourly takes 0.910 to 0.488 offshore
   and 0.782 to 0.296 in port. This is the measurement behind D20, and it is why `ais_source` is in
   the contract.
2. **The system refuses rather than guesses as water gets crowded.** In port with a 25 km cloud, 111
   of 150 trials abstained. Top-3 stays high among the ones it does answer.
3. **Origin quality dominates the rest.** A perfect cloud is 1.000; an error of one r90 is 0.653.
   Stage 3's ceiling is set by Stage 2.

## Per-component ablation — the answer to A5 and A6

Re-ranked with one component forced to `null`. **At the easy baseline this is uninformative** (every
delta ≤ 0.05, because the score saturates at 0.91), so the table that matters is the **hard**
condition: an offender with no gap and no slowdown, i.e. a ship that simply sailed through. 300
trials, offshore, top-1 0.579 with everything on.

| component removed | top-1 | delta | reading |
|---|---|---|---|
| nothing (baseline) | 0.579 | — | |
| `proximity` | 0.472 | **−0.107** | the strongest single signal, as designed |
| `temporality` | 0.512 | **−0.067** | earns its 0.10 |
| `trajectory` | 0.528 | **−0.051** | **A5 answered: it does contribute**, about half of temporality |
| `type_prior` | 0.555 | −0.024 | **A6 answered: nearly inert**, and see the caveat below |
| `slowdown` | 0.586 | +0.007 | contributes nothing measurable here |
| `parity` | 0.579 | 0.000 | never applicable — Phase 2 was not built (C1) |
| **`gap`** | **0.722** | **+0.143** | **removing it makes the scorer better** |

**The `gap` finding, stated carefully.** In this condition the offender never goes dark, while real
vessels in real traffic routinely do — so `gap` rewards innocent ships. That is A2 ("gap rewards the
wrong vessel on Jacksonville") reproduced at scale and quantified. It does **not** mean the component
is wrong: when the offender *does* go dark, it is worth a lot (baseline 0.910 with a 45-minute gap
against 0.681 without one). `gap` is a component that assumes the behaviour it looks for. On a fleet
where the guilty party does not go dark, it costs 0.143.

**Two honesty notes on this table.**
- An early version of the generator made every offender a **tanker**, and `type_prior` scored −0.100
  — not because the component works but because the guilty vessel was always the class it scores
  highest. Drawing the offender's type from the background fleet's own distribution dropped it to
  −0.024. A benchmark that leaks the answer through a side channel measures the leak.
- `parity` is structurally 0.000 here: it has never been implemented (blocked on Soumirya's centreline).
  It is in the table so the zero is visible rather than absent.

## What this does not settle

**No weight moves before the demo.** These numbers were produced hours before a freeze, on one
synthetic offender design, on two US parquets. They are strong enough to say `trajectory` earns its
place and `type_prior` does not, and strong enough to put a real question mark over `gap` — but a
weight change wants a second offender design and a look at whether `gap` should be conditioned on
the vessel having been under way rather than dropped. That is December work, and it is now backed by
a measurement rather than an opinion.

## Reproduce

```bash
python pipeline/attribute/evaluate.py --parquet data/ais/jacksonville.parquet --trials 300 \
    --json pipeline/attribute/results/phase8_jacksonville.json
python pipeline/attribute/evaluate.py --parquet data/ais/jacksonville.parquet --trials 300 \
    --quick --plain --json pipeline/attribute/results/phase8_jacksonville_hard.json
python pipeline/attribute/evaluate.py --parquet data/ais/huntington.parquet --trials 150 --r90 3 \
    --json pipeline/attribute/results/phase8_huntington.json
```

Deterministic for a given `--seed` (default 143); every condition sees the same offenders, so a row
differs from the baseline only by its own axis. The parquets are rebuilt from the public NOAA
archive — `data/` is gitignored, so the inputs stay put and only these results travel.
