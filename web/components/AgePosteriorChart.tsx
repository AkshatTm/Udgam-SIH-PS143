"use client";

// Age engine v2 posterior (Master §6.5 age_posterior, D45). The shaded band is the 80 % HPD —
// the same interval the release window is measured from — and the tick is the median. The
// y axis is hidden on purpose: `prob` is a per-hour probability, and its magnitude means
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

export default function AgePosteriorChart({ posterior }: { posterior: AgePosterior }) {
  const data = posterior.hoursGrid.map((h, i) => ({ h, p: posterior.prob[i] }));
  const [lo, hi] = posterior.hpd80;
  const maxH = posterior.hoursGrid[posterior.hoursGrid.length - 1];

  return (
    <div className="mt-2" aria-label={`Age posterior, 80% interval ${lo} to ${hi} hours`}>
      <ResponsiveContainer width="100%" height={88}>
        <AreaChart data={data} margin={{ top: 4, right: 4, bottom: 0, left: 4 }}>
          <XAxis
            dataKey="h"
            type="number"
            domain={[0, maxH]}
            ticks={[0, 12, 24, 48, maxH].filter((t, i, a) => t <= maxH && a.indexOf(t) === i)}
            tick={{ fill: "var(--ink-3)", fontSize: 10 }}
            tickFormatter={(t: number) => `${t} h`}
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
