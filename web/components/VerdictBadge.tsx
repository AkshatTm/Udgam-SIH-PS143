"use client";

import type { Verdict } from "@/lib/contracts";

// docs/team/harshita-frontend.md Screen 4: every verdict uses the SAME badge — same size, weight, shape, placement.
// Only the colour token changes. MISS must NOT read as an error (no red, no ✗); it is a
// result, styled as confidently as HIT. No success/failure icon on any verdict.

const VERDICT_LABEL: Record<Verdict, string> = {
  hit: "HIT",
  partial: "PARTIAL",
  miss: "MISS",
  not_applicable: "NOT APPLICABLE",
};

// green / amber / calm slate / neutral grey. `miss` is deliberately a cool slate, never red.
// Final tokens are Urooz's (D15) — these are named so a swap is one line each.
const VERDICT_COLOR: Record<Verdict, string> = {
  hit: "border-[#4ade80]/45 bg-[#4ade80]/[0.12] text-[#86efac]",
  partial: "border-[#fbbf24]/45 bg-[#fbbf24]/[0.12] text-[#fcd34d]",
  miss: "border-[#94a3b8]/45 bg-[#94a3b8]/[0.12] text-[#cbd5e1]",
  not_applicable: "border-line-strong bg-white/[0.05] text-ink-2",
};

export default function VerdictBadge({ verdict }: { verdict: Verdict }) {
  return (
    <div
      className={`inline-flex min-w-[180px] items-center justify-center rounded-full border px-8 py-3 text-[15px] font-semibold uppercase tracking-[0.22em] ${VERDICT_COLOR[verdict]}`}
    >
      {VERDICT_LABEL[verdict]}
    </div>
  );
}
