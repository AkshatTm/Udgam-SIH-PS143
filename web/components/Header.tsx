"use client";

import { useAppStore } from "@/lib/store";
import { ACT_LABELS } from "@/lib/contracts";
import { formatAcquisitionDate } from "@/lib/cases";

// Case switching moved to the Gallery (Screen 0) with the five-screen flow — the header no
// longer carries case pills. It is the wordmark, the current case, the stage breadcrumb, and
// the acquisition line.

export default function Header() {
  const meta = useAppStore((s) => s.meta);
  const activeStage = useAppStore((s) => s.activeStage);

  return (
    <header className="flex h-9 shrink-0 items-center justify-between gap-4 border-b border-white/[0.08] bg-[#0b0f14] px-4">
      {/* Left: wordmark + breadcrumb */}
      <div className="flex min-w-0 items-center gap-3">
        <span className="shrink-0 text-[11px] font-semibold uppercase tracking-[0.18em] text-white/90">
          UDGAM
        </span>

        {meta && (
          <>
            <span className="shrink-0 text-white/20">|</span>
            {/* Case title */}
            <span className="truncate text-[11px] text-white/45">
              {meta.title}
            </span>
            {/* Breadcrumb chevron + stage */}
            <span className="shrink-0 text-white/20">›</span>
            <span className="shrink-0 text-[11px] font-medium text-white/70">
              {ACT_LABELS[activeStage].toUpperCase()}
            </span>
          </>
        )}
      </div>

      {/* Right: satellite / acquisition date */}
      {meta && (
        <span className="shrink-0 font-mono text-[10px] text-white/30">
          {meta.satellite}
          {" · "}
          {formatAcquisitionDate(meta.detection_time) ?? "—"}
        </span>
      )}
    </header>
  );
}
