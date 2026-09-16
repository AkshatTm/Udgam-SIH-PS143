"use client";

// Attribution evidence primitives, shared by the Attribute stage card (ContextPanel) and the
// Verify screen. These lived as module-private helpers inside ContextPanel until the Verify
// screen needed to show the same evidence behind its own verdict; they were moved here
// verbatim rather than reimplemented, so a funnel bar means the same thing on both screens and
// a null component renders "n/a" identically in both places.
//
// Nothing in this module fetches, derives, or reformats a measurement. It renders what the
// parsed bundle already holds.

import type { AisSource } from "@/lib/contracts";
import type { Funnel, Suspect, SuspectComponents } from "@/lib/suspects";

// D20 — which AIS archive scored this case, and therefore which sampling regime the funnel and
// every gap/slowdown "n/a" downstream of it are honest about. No fabricated label for a value
// the loader didn't recognize (only these two exist in the frozen contract).
export const AIS_SAMPLING_LABEL: Record<AisSource, string> = {
  noaa_dense: "AIS: 71-second sampling (NOAA)",
  gfw_hourly: "AIS: hourly sampling (Global Fishing Watch)",
};

/** Static 4-step bar — "no animation needed" per docs/team/harshita-frontend.md Phase 5. Steps only ever shrink or
 * hold, left to right (CONTRACTS §8: funnel counts are non-increasing), so the bar length
 * itself carries the funnel's shape. */
export function FunnelBar({ funnel }: { funnel: Funnel }) {
  const steps: { label: string; value: number }[] = [
    { label: "In Region", value: funnel.inRegion },
    { label: "In Window", value: funnel.inWindow },
    { label: "Plausible", value: funnel.plausible },
    { label: "Scored", value: funnel.scored },
  ];
  const max = Math.max(1, funnel.inRegion);
  return (
    <div className="space-y-2.5">
      {steps.map((s) => {
        const pct = funnel.inRegion > 0 ? Math.max(2, Math.min(100, (s.value / max) * 100)) : 0;
        return (
          <div key={s.label}>
            <div className="flex items-baseline justify-between">
              <span className="text-[13px] text-ink-2">{s.label}</span>
              <span className="font-mono text-[13px] text-ink tabular-nums">
                {s.value}
              </span>
            </div>
            <div className="mt-1 h-1 rounded-full bg-white/[0.07]">
              <div
                className="h-1 rounded-full bg-[#f97316]"
                style={{ width: `${pct}%` }}
              />
            </div>
          </div>
        );
      })}
    </div>
  );
}

export const COMPONENT_LABELS: { key: keyof SuspectComponents; label: string }[] = [
  { key: "proximity", label: "Proximity" },
  { key: "parity", label: "Parity" },
  { key: "temporality", label: "Temporality" },
  { key: "trajectory", label: "Trajectory" },
  { key: "gap", label: "Gap" },
  { key: "slowdown", label: "Slowdown" },
  { key: "typePrior", label: "Type prior" },
];

/** Score-component breakdown behind a suspect's overall score (docs/team/harshita-frontend.md Phase 3.2, Master
 * §6.7). Same bar-track visual language as FunnelBar — no new visual system. A `null`
 * component (e.g. `gap`/`slowdown` on a gfw_hourly case) renders "n/a" with NO bar underneath:
 * a zero-width bar would claim a measurement that was never possible. D29: an unexplained
 * "n/a" reads as a broken feature, so a null component with a matching producer-supplied note
 * renders that note verbatim underneath — never invented here, never shown for a real value. */
export function ComponentBars({
  components,
  notes,
}: {
  components: SuspectComponents;
  notes: Suspect["componentNotes"];
}) {
  return (
    <div className="mt-2 space-y-1.5">
      {COMPONENT_LABELS.map(({ key, label }) => {
        const v = components[key];
        // D29 — an unexplained "n/a" reads as a broken feature. The note is the producer's
        // own words, rendered verbatim; nothing is written here when the bundle has none.
        // Producers note every component; inline only where the bar is "n/a" (D29's need),
        // hover title elsewhere, so three cards don't carry 21 lines of prose.
        const note = notes[key];
        return (
          <div key={key} title={v !== null ? note : undefined}>
            <div className="flex items-baseline justify-between">
              <span className="text-[13px] text-ink-2">{label}</span>
              <span className="font-mono text-[13px] text-ink-2 tabular-nums">
                {v === null ? "n/a" : v.toFixed(2)}
              </span>
            </div>
            {v !== null && (
              <div className="mt-0.5 h-1 rounded-full bg-white/[0.07]">
                <div
                  className="h-1 rounded-full bg-[#f97316]"
                  style={{ width: `${Math.max(2, Math.min(100, v * 100))}%` }}
                />
              </div>
            )}
            {v === null && note && (
              <p className="mt-0.5 text-[13px] leading-snug text-ink-3">{note}</p>
            )}
          </div>
        );
      })}
    </div>
  );
}
