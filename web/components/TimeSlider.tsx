"use client";

// Present for layout and the demo narrative. Inert in Phase 1 — nothing consumes tNorm yet.
// Phase 2 binds it to particles.positions[t].

import { useAppStore } from "@/lib/store";

export default function TimeSlider() {
  const tNorm = useAppStore((s) => s.tNorm);
  const setTNorm = useAppStore((s) => s.setTNorm);

  return (
    <div className="flex items-center gap-3 border-t border-white/10 bg-[#0b0f14] px-4 py-2.5">
      <span className="shrink-0 text-[11px] text-white/40">T−24h</span>
      <input
        type="range"
        min={0}
        max={1}
        step={0.01}
        value={tNorm}
        onChange={(e) => setTNorm(Number(e.target.value))}
        className="h-1 w-full cursor-pointer appearance-none rounded bg-white/15 accent-white"
        aria-label="Time"
      />
      <span className="shrink-0 text-[11px] text-white/40">T−0 detect</span>
    </div>
  );
}
