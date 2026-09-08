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
    <div className="flex items-center gap-1">
      <span className="mr-2 text-[9px] font-semibold uppercase tracking-[0.14em] text-white/25">
        Layers
      </span>
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
            className={`rounded px-2.5 py-0.5 text-[10px] font-medium transition-colors ${
              !enabled
                ? "cursor-not-allowed text-white/15"
                : on
                  ? "bg-white/[0.10] text-white/80"
                  : "text-white/32 hover:text-white/55"
            }`}
          >
            {label}
          </button>
        );
      })}
    </div>
  );
}
