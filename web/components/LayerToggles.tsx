"use client";

import { useAppStore, type LayerId } from "@/lib/store";

// SAR + Detections are live in Phase 1. Particles / Origin / Vessels are shown so the final
// shape is clear, but disabled — their layers don't exist yet.
const TOGGLES: { id: LayerId; label: string; live: boolean }[] = [
  { id: "sar", label: "SAR", live: true },
  { id: "detections", label: "Detections", live: true },
  { id: "particles", label: "Particles", live: false },
  { id: "origin", label: "Origin", live: false },
  { id: "vessels", label: "Vessels", live: false },
];

export default function LayerToggles() {
  const layers = useAppStore((s) => s.layers);
  const toggleLayer = useAppStore((s) => s.toggleLayer);

  return (
    <div className="flex gap-1.5">
      {TOGGLES.map(({ id, label, live }) => {
        const on = layers[id];
        return (
          <button
            key={id}
            type="button"
            disabled={!live}
            onClick={() => toggleLayer(id)}
            aria-pressed={on}
            title={live ? label : `${label} — available in a later phase`}
            className={`rounded-full border px-3 py-1 text-[11px] font-medium transition-colors ${
              !live
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
