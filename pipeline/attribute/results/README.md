# Stage 3 — evaluation artefacts

Generated files, committed on purpose: they are the evidence behind every attribution figure this
project quotes.

**Why these exist at all.** Every live case has a documented outcome sealed in `docs/ANSWERS.md`,
so quoting attribution accuracy from a live case would mean quoting a number whose answer we hold
— which decision D21 forbids. The alternative is here: **real AIS traffic, a synthetic guilty
vessel whose discharge point, transponder gap, speed profile, course and type we control, and
therefore a rank we can check.**

| File | Condition |
|---|---|
| `phase8_jacksonville.json` | Offshore baseline, full sweep |
| `phase8_jacksonville_hard.json` | Offender with no behavioural signature (`--quick --plain`) |
| `phase8_huntington.json` | Near-shore, tighter cloud (`--r90 3`) |

Regenerate all three:

```bash
python pipeline/attribute/evaluate.py --parquet data/ais/jacksonville.parquet --trials 300     --json pipeline/attribute/results/phase8_jacksonville.json
python pipeline/attribute/evaluate.py --parquet data/ais/jacksonville.parquet --trials 300     --quick --plain --json pipeline/attribute/results/phase8_jacksonville_hard.json
python pipeline/attribute/evaluate.py --parquet data/ais/huntington.parquet --trials 150 --r90 3     --json pipeline/attribute/results/phase8_huntington.json
```

Deterministic for a given `--seed` (default 143), so every condition sees the same offenders and
a row differs from the baseline only by its own axis. The parquets are rebuilt from the public
NOAA archive; `data/` is gitignored, so the inputs stay put and only these results travel.

Every figure in these files is a **ranking** number given a stated origin quality. It is an upper
bound on end-to-end performance and is **never** to be quoted as accuracy on the live cases.
Abstention is reported separately and is never scored as a hit or a miss.

Read with [`docs/evaluation/stage3-injected-offender-curve.md`](../../../docs/evaluation/stage3-injected-offender-curve.md),
which explains the design, the conditions and the ablation.
