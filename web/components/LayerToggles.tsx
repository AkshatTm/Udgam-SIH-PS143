"use client";

import { useAppStore, type LayerId } from "@/lib/store";

// This row doubles as the map legend. Each chip carries the colour its layer is drawn in, so a
// judge reading "what is that orange dot on the map" finds the answer in the control that turns
// it on — no separate legend to maintain, and no second colour vocabulary to learn.
//
// Gating is unchanged: Particles/Origin need a `trace` act that has been run, Vessels needs
// `attribute`, and Detections needs Detect to have been run.
const TOGGLES: { id: LayerId; label: string; swatch: string }[] = [
  { id: "sar", label: "Radar scene", swatch: "#8fa8bb" },
  { id: "detections", label: "Detections", swatch: "var(--oil)" },
  { id: "particles", label: "Drift", swatch: "var(--drift)" },
  { id: "origin", label: "Origin", swatch: "var(--drift)" },
  { id: "vessels", label: "Ship tracks", swatch: "var(--contact)" },
];

export default function LayerToggles() {
  const layers = useAppStore((s) => s.layers);
  const toggleLayer = useAppStore((s) => s.toggleLayer);
  const meta = useAppStore((s) => s.meta);

  const revealed = useAppStore((s) => s.revealed);
  const traceAvailable = (meta?.acts_available.includes("trace") ?? false) && revealed.trace;
  const attributeAvailable =
    (meta?.acts_available.includes("attribute") ?? false) && revealed.attribute;

  return (
    <div className="flex items-center gap-1.5">
      <span className="mr-2 t-label">Layers</span>
      {TOGGLES.map(({ id, label, swatch }) => {
        const needsTrace = id === "particles" || id === "origin";
        const needsAttribute = id === "vessels";
        const enabled =
          (id !== "detections" || revealed.detect) &&
          (!needsTrace || traceAvailable) &&
          (!needsAttribute || attributeAvailable);
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
                ? on
                  ? `Hide ${label}`
                  : `Show ${label}`
                : needsTrace
                  ? `${label} — appears once the drift has been run`
                  : needsAttribute
                    ? `${label} — appears once attribution has been run`
                    : `${label} — appears once detection has been run`
            }
            className={`flex items-center gap-1.5 rounded-full px-2.5 py-1 text-[12px] font-medium transition-colors duration-150 ${
              !enabled
                ? "cursor-not-allowed text-ink-4"
                : on
                  ? "bg-white/[0.08] text-ink"
                  : "text-ink-3 hover:bg-white/[0.04] hover:text-ink-2"
            }`}
          >
            <span
              aria-hidden
              className="h-1.5 w-1.5 shrink-0 rounded-full transition-opacity duration-150"
              style={{ background: swatch, opacity: !enabled ? 0.25 : on ? 1 : 0.4 }}
            />
            {label}
          </button>
        );
      })}
    </div>
  );
}
