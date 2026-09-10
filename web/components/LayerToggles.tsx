"use client";

import { useAppStore, type LayerId } from "@/lib/store";

// SAR + Detections landed in Phase 1, Particles + Origin in Phases 2–3, Vessels in Phase 5.
// Particles/Origin are greyed for a case with no `trace` act; Vessels is greyed for a case with
// no `attribute` act (no vessels.geojson to show — same reasoning as the stage rail).
const TOGGLES: { id: LayerId; label: string; live: boolean }[] = [
  { id: "sar", label: "SAR", live: true },
  { id: "detections", label: "Detections", live: true },
  { id: "particles", label: "Particles", live: true },
  { id: "origin", label: "Origin", live: true },
  { id: "vessels", label: "Vessels", live: true },
];

export default function LayerToggles() {
  const layers = useAppStore((s) => s.layers);
  const toggleLayer = useAppStore((s) => s.toggleLayer);
  const meta = useAppStore((s) => s.meta);

  const traceAvailable = meta?.acts_available.includes("trace") ?? false;
  const attributeAvailable = meta?.acts_available.includes("attribute") ?? false;

  return (
    <div className="flex items-center gap-1">
      <span className="mr-2 text-[9px] font-semibold uppercase tracking-[0.14em] text-white/25">
        Layers
      </span>
      {TOGGLES.map(({ id, label, live }) => {
        const needsTrace = id === "particles" || id === "origin";
        const needsAttribute = id === "vessels";
        const enabled =
          live && (!needsTrace || traceAvailable) && (!needsAttribute || attributeAvailable);
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
                  : needsAttribute
                    ? `${label} — this case has no attribution stage`
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
