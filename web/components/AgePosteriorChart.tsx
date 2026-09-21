"use client";

// Age engine v2 posterior (Master §6.5 age_posterior, D45). The shaded band is the 80 % HPD —
// the same interval the release window is measured from — and the tick is the median. The
// y axis is hidden on purpose: `prob` is a per-cell probability, and its magnitude means
// nothing to a judge; the shape and the band are the claim.

import {
  Area,
  AreaChart,
  ReferenceArea,
  ReferenceLine,
  ResponsiveContainer,
  XAxis,
  YAxis,
} from "recharts";
import type { AgePosterior } from "@/lib/origin";

/**
 * Where to stop the x axis.
 *
 * The domain used to be the producer's whole grid — always 0–72 h, with hardcoded ticks at
 * 12/24/48/72 — so on Jacksonville an 80 % interval of 0.5–13.5 h occupied under a fifth of
 * the width and the first tick gap swallowed nearly the entire claim.
 *
 * The axis now follows the probability mass: far enough to show where the distribution
 * actually ends, and never nearer than the shaded band. That clamp matters — `ReferenceArea`
 * is drawn with `ifOverflow="hidden"`, so a domain narrower than `hi` would silently clip the
 * 80 % band rather than erroring, which is the one failure this chart must not have.
 */
function axisMax(posterior: AgePosterior): number {
  const { hoursGrid, prob, hpd80 } = posterior;
  const gridMax = hoursGrid[hoursGrid.length - 1];
  let cum = 0;
  let cut = gridMax;
  for (let i = 0; i < prob.length; i += 1) {
    cum += prob[i];
    if (cum >= 0.995) {
      cut = hoursGrid[i];
      break;
    }
  }
  // A little headroom so the curve does not die exactly on the frame, then clamp to the band
  // and to the grid we actually have.
  return Math.min(gridMax, Math.max(hpd80[1] * 1.15, cut * 1.1, 1));
}

/** Round, readable ticks for whatever span we ended up with — never a fixed literal set. */
function axisTicks(max: number): number[] {
  const step = max <= 6 ? 1 : max <= 16 ? 2 : max <= 36 ? 6 : max <= 80 ? 12 : 24;
  const out: number[] = [];
  for (let t = 0; t <= max + 1e-9; t += step) out.push(Number(t.toFixed(2)));
  if (out[out.length - 1] < max - step * 0.35) out.push(Number(max.toFixed(1)));
  return out;
}

export default function AgePosteriorChart({ posterior }: { posterior: AgePosterior }) {
  const [lo, hi] = posterior.hpd80;
  const max = axisMax(posterior);
  // Clip the series to the domain. Recharts would otherwise keep computing a path across
  // points it never draws, which distorts the "monotone" curve near the right edge.
  const data = posterior.hoursGrid
    .map((h, i) => ({ h, p: posterior.prob[i] }))
    .filter((d) => d.h <= max);
  const ticks = axisTicks(max);
  const fmt = (t: number) => (t < 10 && !Number.isInteger(t) ? `${t.toFixed(1)} h` : `${Math.round(t)} h`);

  return (
    <div className="mt-2" aria-label={`Age posterior, 80% interval ${lo} to ${hi} hours`}>
      <ResponsiveContainer width="100%" height={88}>
        <AreaChart data={data} margin={{ top: 4, right: 4, bottom: 0, left: 4 }}>
          <XAxis
            dataKey="h"
            type="number"
            domain={[0, max]}
            ticks={ticks}
            tick={{ fill: "var(--ink-3)", fontSize: 10 }}
            tickFormatter={fmt}
            axisLine={{ stroke: "var(--line-strong)" }}
            tickLine={false}
          />
          <YAxis hide domain={[0, "dataMax"]} />
          <ReferenceArea x1={lo} x2={hi} fill="var(--drift-dim)" stroke="none" ifOverflow="hidden" />
          <Area
            type="monotone"
            dataKey="p"
            stroke="var(--drift)"
            strokeWidth={1.5}
            fill="var(--drift-dim)"
            isAnimationActive={false}
          />
          <ReferenceLine x={posterior.median} stroke="var(--ink-2)" strokeDasharray="2 2" />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}
