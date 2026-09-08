"use client";

import { useAppStore, type LayerId } from "@/lib/store";

// SAR + Detections landed in Phase 1, Particles + Origin in Phases 2–3. Vessels is shown so the
// final shape is clear, but disabled — its layer doesn't exist yet. Particles and Origin are
// additionally greyed for a case with no `trace` act (no particle / origin bundle to show).
const TOGGLES: { id: LayerId; label: string; live: boolean }[] = [
  { id: "sar", label: "SAR", live: true },
  { id: "detections", label: "Detections", live: true },
  { id: "particles", label: "Particles", live: true },
  { id: "origin", label: "Origin", live: true },
  { id: "vessels", label: "Vessels", live: false },
];

export default function LayerToggles() {
  const layers = useAppStore((s) => s.layers);
  const toggleLayer = useAppStore((s) => s.toggleLayer);
  const meta = useAppStore((s) => s.meta);

  const traceAvailable = meta?.acts_available.includes("trace") ?? false;

  return (
    <div className="flex gap-1.5">
      {TOGGLES.map(({ id, label, live }) => {
        const needsTrace = id === "particles" || id === "origin";
        const enabled = live && (!needsTrace || traceAvailable);
        const on = layers[id];
        return (
          <button
            key={id}
            type="button"
            disabled={!enabled}
            onClick={() => toggleLayer(id)}
            aria-pressed={on}
            title={
              enabled
                ? label
                : needsTrace
                  ? `${label} — this case has no drift stage`
                  : `${label} — available in a later phase`
            }
            className={`rounded-full border px-3 py-1 text-[11px] font-medium transition-colors ${
              !enabled
                ? "cursor-not-allowed border-white/5 text-white/20"
                : on
                  ? "border-white/30 bg-white/15 text-white"
                  : "border-white/10 text-white/45 hover:text-white/80"
            }`}
          >
            {label}
          </button>
        );
      })}
    </div>
  );
}
