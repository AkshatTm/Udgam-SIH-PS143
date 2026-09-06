"use client";

import { useAppStore } from "@/lib/store";
import { CASES } from "@/lib/cases";

function formatUtc(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  const date = d.toLocaleDateString("en-GB", {
    day: "2-digit",
    month: "short",
    year: "numeric",
    timeZone: "UTC",
  });
  const time = d.toLocaleTimeString("en-GB", {
    hour: "2-digit",
    minute: "2-digit",
    timeZone: "UTC",
  });
  return `${date} ${time} UTC`;
}

export default function Header() {
  const meta = useAppStore((s) => s.meta);
  const activeCaseId = useAppStore((s) => s.activeCaseId);
  const setActiveCase = useAppStore((s) => s.setActiveCase);

  return (
    <header className="flex items-center justify-between gap-4 border-b border-white/10 bg-[#0b0f14] px-4 py-2.5">
      <div className="min-w-0">
        <div className="truncate text-sm font-semibold text-white">
          {meta?.title ?? "Loading case…"}
        </div>
        {meta && (
          <div className="truncate text-xs text-white/50">
            {meta.satellite} · {formatUtc(meta.detection_time)}
          </div>
        )}
      </div>

      <nav className="flex shrink-0 gap-1">
        {CASES.map((c) => {
          const active = c.id === activeCaseId;
          return (
            <button
              key={c.id}
              type="button"
              onClick={() => setActiveCase(c.id)}
              aria-pressed={active}
              className={`rounded px-3 py-1 text-xs font-medium transition-colors ${
                active
                  ? "bg-white/15 text-white"
                  : "text-white/40 hover:bg-white/5 hover:text-white/70"
              }`}
            >
              {c.label}
            </button>
          );
        })}
      </nav>
    </header>
  );
}
