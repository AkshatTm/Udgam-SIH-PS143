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
  { id: "forward", label: "Forward slick", swatch: "var(--drift)" },
  { id: "vessels", label: "Ship tracks", swatch: "var(--contact)" },
  // The one marker on the map with no track and no name. It had no chip at all, so the
  // rose dot was the only thing on screen a judge could not look up in the legend.
  { id: "darkVessels", label: "Ghost ships", swatch: "var(--dark-vessel)" },
];

export default function LayerToggles() {
  const layers = useAppStore((s) => s.layers);
  const toggleLayer = useAppStore((s) => s.toggleLayer);
  const meta = useAppStore((s) => s.meta);
  const setForwardNorm = useAppStore((s) => s.setForwardNorm);
  const setForwardPlaying = useAppStore((s) => s.setForwardPlaying);

  const revealed = useAppStore((s) => s.revealed);
  const traceAvailable = (meta?.acts_available.includes("trace") ?? false) && revealed.trace;
  // Master 6.10: forward_impact.json is OPTIONAL even on a traced case. The chip stays disabled
  // rather than hidden, so "this case has no forecast" is visible instead of silently missing.
  const forwardBundle = useAppStore((s) => s.forward);
  const forwardAvailable = traceAvailable && forwardBundle !== null;
  // First press is a "Run": turning the layer on also plays the T0 -> horizon sweep once, the
  // same guided-reveal feel as "Run backward drift" (which turns particles/origin on and
  // autoplays via initTrace). Every press after that is a plain show/hide toggle.
  const onForwardChipClick = () => {
    if (!layers.forward) {
      toggleLayer("forward");
      setForwardNorm(0);
      setForwardPlaying(true);
    } else {
      toggleLayer("forward");
    }
  };
  const attributeAvailable =
    (meta?.acts_available.includes("attribute") ?? false) && revealed.attribute;

  return (
    <div className="flex items-center gap-1.5">
      <span className="mr-2 t-label">Layers</span>
      {TOGGLES.map(({ id, label, swatch }) => {
        const needsTrace = id === "particles" || id === "origin";
        const needsForward = id === "forward";
        const needsAttribute = id === "vessels" || id === "darkVessels";
        const enabled =
          (id !== "detections" || revealed.detect) &&
          (!needsTrace || traceAvailable) &&
          (!needsForward || forwardAvailable) &&
          (!needsAttribute || attributeAvailable);
        const on = layers[id];
        // Before its first run, the forward chip IS the "Run forward slick" action — pressing
        // it turns the layer on and plays the T0 -> horizon sweep once (onForwardChipClick).
        // Once on, it reverts to a plain show/hide toggle like every other chip.
        const isForwardRunCta = needsForward && enabled && !on;
        return (
          <button
            key={id}
            type="button"
            disabled={!enabled}
            onClick={() => (needsForward ? onForwardChipClick() : toggleLayer(id))}
            aria-pressed={on}
            title={
              enabled
                ? isForwardRunCta
                  ? "Run the forward forecast from T0 to the horizon"
                  : on
                    ? `Hide ${label}`
                    : `Show ${label}`
                : needsTrace
                  ? `${label} — appears once the drift has been run`
                  : needsForward
                    ? traceAvailable
                      ? `${label} — Stage 2 produced no forward forecast for this case`
                      : `${label} — appears once the drift has been run`
                    : needsAttribute
                      ? `${label} — appears once attribution has been run`
                      : `${label} — appears once detection has been run`
            }
            className={`flex items-center gap-1.5 rounded-full px-2.5 py-1 text-[12px] font-medium transition-colors duration-150 ${
              !enabled
                ? "cursor-not-allowed text-ink-4"
                : isForwardRunCta
                  ? "border border-drift/50 text-drift hover:border-drift hover:bg-drift/10"
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
            {isForwardRunCta ? "Run forward slick" : label}
          </button>
        );
      })}
    </div>
  );
}
