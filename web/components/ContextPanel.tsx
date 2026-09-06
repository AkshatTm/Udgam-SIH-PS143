"use client";

import { useAppStore } from "@/lib/store";
import { ACT_LABELS } from "@/lib/contracts";
import type { DetectionProperties } from "@/lib/contracts";

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-baseline justify-between gap-3 py-1 text-xs">
      <span className="text-white/45">{label}</span>
      <span className="font-mono text-white/90">{value}</span>
    </div>
  );
}

function DetectionCard({ p }: { p: DetectionProperties }) {
  const isOil = p.classification === "oil";
  return (
    <div>
      <span
        className={`inline-block rounded px-2 py-0.5 text-[11px] font-semibold uppercase tracking-wide ${
          isOil ? "bg-[#ff4d4d]/20 text-[#ff8a8a]" : "bg-white/10 text-white/60"
        }`}
      >
        {p.classification}
      </span>
      <div className="mt-3">
        <Row label="ID" value={p.id} />
        <Row label="Confidence" value={`${Math.round(p.confidence * 100)}%`} />
        <Row label="Area" value={`${p.area_km2} km²`} />
        <Row label="Elongation" value={`${p.elongation}`} />
        <Row label="Edge gradient" value={`${p.edge_gradient}`} />
        <Row label="Contrast" value={`${p.contrast_db} dB`} />
        <Row label="Shape class" value={p.shape_class} />
        <Row
          label="Centroid"
          value={`${p.centroid[0].toFixed(3)}, ${p.centroid[1].toFixed(3)}`}
        />
      </div>
    </div>
  );
}

export default function ContextPanel() {
  const activeStage = useAppStore((s) => s.activeStage);
  const detections = useAppStore((s) => s.detections);
  const selectedDetectionId = useAppStore((s) => s.selectedDetectionId);

  const oilCount =
    detections?.features.filter((f) => f.properties.classification === "oil").length ?? 0;
  const selected = detections?.features.find(
    (f) => f.properties.id === selectedDetectionId,
  );

  return (
    <aside className="flex w-80 shrink-0 flex-col gap-3 overflow-y-auto border-l border-white/10 bg-[#0b0f14] p-4">
      <div className="text-[11px] uppercase tracking-widest text-white/35">
        {ACT_LABELS[activeStage]}
      </div>

      {activeStage === "detect" && (
        <>
          {oilCount === 0 ? (
            <p className="rounded-md border border-white/10 bg-white/5 p-3 text-xs text-white/70">
              No spill detected in this scene.
            </p>
          ) : selected ? (
            <DetectionCard p={selected.properties} />
          ) : (
            <p className="text-xs text-white/40">Select a detection on the map.</p>
          )}
        </>
      )}

      {(activeStage === "trace" || activeStage === "attribute") && (
        <p className="text-xs text-white/40">
          {ACT_LABELS[activeStage]} — available in a later phase.
        </p>
      )}
    </aside>
  );
}
