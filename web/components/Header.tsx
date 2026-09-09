"use client";

import { useAppStore } from "@/lib/store";
import { CASES } from "@/lib/cases";
import { ACT_LABELS } from "@/lib/contracts";

export default function Header() {
  const meta = useAppStore((s) => s.meta);
  const activeCaseId = useAppStore((s) => s.activeCaseId);
  const activeStage = useAppStore((s) => s.activeStage);
  const setActiveCase = useAppStore((s) => s.setActiveCase);

  return (
    <header className="flex h-9 shrink-0 items-center justify-between gap-4 border-b border-white/[0.08] bg-[#0b0f14] px-4">
      {/* Left: wordmark + breadcrumb */}
      <div className="flex min-w-0 items-center gap-3">
        <span className="shrink-0 text-[11px] font-semibold uppercase tracking-[0.18em] text-white/90">
          NAAP
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

      {/* Right: case pills + satellite/date */}
      <div className="flex shrink-0 items-center gap-3">
        {meta && (
          <span className="text-[10px] text-white/30 font-mono">
            {meta.satellite}
            {" · "}
            {new Date(meta.detection_time).toLocaleDateString("en-GB", {
              day: "2-digit",
              month: "short",
              year: "numeric",
              timeZone: "UTC",
            })}
          </span>
        )}

        {/* Case selector */}
        <nav className="flex gap-0.5">
          {CASES.map((c) => {
            const active = c.id === activeCaseId;
            return (
              <button
                key={c.id}
                type="button"
                onClick={() => setActiveCase(c.id)}
                aria-pressed={active}
                className={`rounded px-2.5 py-1 text-[10px] font-medium uppercase tracking-wide transition-colors ${
                  active
                    ? "bg-white/[0.12] text-white"
                    : "text-white/35 hover:bg-white/[0.06] hover:text-white/60"
                }`}
              >
                {c.label}
              </button>
            );
          })}
        </nav>
      </div>
    </header>
  );
}
