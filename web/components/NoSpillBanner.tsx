"use client";

// docs/team/harshita-frontend.md Part D, D1 — a *designed result*, never an error. Shown over the Detect map so the
// SAR scene and the grey dashed look-alike polygons stay visible underneath ("showing the
// rejection is what proves we're not just flagging dark pixels"). Informational only →
// pointer-events-none, so clicks pass straight through to the look-alike polygons below.
//
// Copy is count-derived only: no case-specific cause (never "calm-wind zone" / "algae bloom").
// CaseWorkspace only mounts this when stage === "detect", the case is loaded (!error), and
// isNoSpill(detections) — so `detections` is non-null here.

import { useAppStore } from "@/lib/store";

export default function NoSpillBanner() {
  const detections = useAppStore((s) => s.detections);
  if (!detections) return null;

  const count = detections.features.length;
  const sub =
    count === 0
      ? "The scene is clear — no dark features to assess."
      : `We checked ${count} dark patch${count === 1 ? "" : "es"} — none match oil. Click a grey patch on the map to see why it was rejected.`;

  return (
    <div className="pointer-events-none absolute left-1/2 top-4 z-10 w-[min(92%,30rem)] -translate-x-1/2">
      <div className="rounded border border-white/15 bg-[#0b0f14]/90 px-4 py-3 text-center shadow-lg backdrop-blur-sm">
        <div className="text-[13px] font-semibold text-white/90">
          No spill detected in this scene.
        </div>
        <p className="mt-1 text-[11px] leading-relaxed text-white/55">{sub}</p>
      </div>
    </div>
  );
}
