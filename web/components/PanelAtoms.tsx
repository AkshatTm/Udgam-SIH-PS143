"use client";

// Shared small atoms for the ContextPanel stage cards (Detect/Trace/Attribute/Scene). Moved out
// of ContextPanel.tsx verbatim — no behaviour change — into their own file so components/trace/
// can import them without creating a circular import back into ContextPanel.tsx (which itself
// renders TraceCard).

import InfoDot from "@/components/InfoDot";

/** Dimmed uppercase section label */
export function SectionLabel({ children }: { children: React.ReactNode }) {
  return <div className="mt-5 t-label first:mt-0">{children}</div>;
}

/** Hairline divider */
export function Divider() {
  return <div className="my-4 border-t border-line" />;
}

/** One row: label left, monospace value right */
export function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-baseline justify-between gap-3 py-[3px]">
      <span className="t-small text-ink-2">{label}</span>
      <span className="font-mono text-[13px] text-ink tabular-nums">{value}</span>
    </div>
  );
}

/**
 * MetricRow — plain-language label first, muted technical term second,
 * optional InfoDot affordance (C4 + C5).
 */
export function MetricRow({
  primary,
  technical,
  value,
  tip,
}: {
  primary: string;
  technical?: string;
  value: string;
  tip: string;
}) {
  return (
    // `relative` — the InfoDot's tooltip anchors to this row (see InfoDot.tsx), not to the
    // button itself, so it stays inside the panel regardless of how long `primary` is.
    <div className="relative flex items-start justify-between gap-3 py-[3px]">
      <span className="flex flex-col gap-0">
        <span className="flex items-center gap-1 t-small text-ink">
          {primary}
          <InfoDot tip={tip} />
        </span>
        {technical && <span className="text-[11px] text-ink-3">{technical}</span>}
      </span>
      <span className="font-mono text-[13px] text-ink tabular-nums shrink-0">{value}</span>
    </div>
  );
}
