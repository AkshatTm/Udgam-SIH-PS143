"use client";

import {
  Bar,
  BarChart,
  LabelList,
  ResponsiveContainer,
  XAxis,
  YAxis,
} from "recharts";
import { useAppStore } from "@/lib/store";
import { ACT_LABELS } from "@/lib/contracts";
import type { DetectionProperties } from "@/lib/contracts";
import type { OriginBundle } from "@/lib/origin";

// Classification colours — the same hex the map uses for the detection polygons, so the badge,
// the feature bars and the outline on the map all read as one object. No new tokens invented.
const OIL_COLOR = "#ff4d4d";
const LOOKALIKE_COLOR = "#9aa4b2";

const fmt = (x: number | undefined, digits: number): string =>
  typeof x === "number" && Number.isFinite(x)
    ? x.toFixed(digits).replace("-", "−") // real minus sign, reads better projected
    : "—";

// origin.time_window entries are UTC ISO 8601 with a trailing Z (validated in lib/origin.ts).
// Render the instant in UTC — same treatment as the header's detection_time — and keep the raw
// ISO string on `title` so the Z semantics are never lost. Falls back to the raw string if the
// timestamp somehow doesn't parse.
const fmtUtc = (iso: string): string => {
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
};

/**
 * Display-only scaling for the "why this classification" bars. These are NOT model
 * probabilities or decision thresholds — each geometric feature is drawn as a fraction of a
 * magnitude that reads as a strong oil signal, so the three are comparable at a glance. The
 * real measured value is always shown as text beside the bar.
 *   elongation    — major/minor axis ratio, ~[1, 15]; 1 is a circle (no linearity)
 *   edge_gradient — mean Sobel magnitude along the slick contour (edge sharpness)
 *   contrast_db   — mean dB inside minus the surrounding ring; −3 dB is the documented cutoff
 */
function featureRows(
  p: DetectionProperties,
): { label: string; value: string; frac: number }[] {
  const bar = (x: number, ref: number): number =>
    Number.isFinite(x) ? Math.max(0.02, Math.min(0.96, x / ref)) : 0;
  return [
    {
      label: "Elongation",
      value: fmt(p.elongation, 1),
      frac: bar(p.elongation - 1, 9),
    },
    {
      label: "Edge gradient",
      value: fmt(p.edge_gradient, 2),
      frac: bar(p.edge_gradient, 0.5),
    },
    {
      label: "Contrast",
      value: `${fmt(p.contrast_db, 1)} dB`,
      frac: bar(Math.abs(p.contrast_db), 10),
    },
  ];
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-baseline justify-between gap-3 py-1">
      <span className="text-sm text-white/50">{label}</span>
      <span className="font-mono text-sm text-white/90">{value}</span>
    </div>
  );
}

function DetectionCard({ p }: { p: DetectionProperties }) {
  const isOil = p.classification === "oil";
  const rows = featureRows(p);

  return (
    <div className="rounded-md border border-white/10 bg-white/[0.03] p-4">
      {/* classification — solid for oil, muted grey for a look-alike; unmistakable at a glance */}
      <div
        className={`inline-flex items-center rounded px-2.5 py-1 text-sm font-semibold uppercase tracking-wide ${
          isOil ? "bg-[#ff4d4d] text-white" : "bg-white/10 text-white/60"
        }`}
      >
        {isOil ? "Oil" : "Look-alike"}
      </div>

      {/* confidence — second in the hierarchy, after the badge */}
      <div className="mt-4">
        <div className="text-2xl font-semibold tabular-nums text-white">
          {Number.isFinite(p.confidence) ? Math.round(p.confidence * 100) : "—"}%
        </div>
        <div className="mt-0.5 text-xs uppercase tracking-wide text-white/40">
          classifier confidence
        </div>
      </div>

      {/* feature bars — "why this classification" */}
      <div className="mt-5">
        <div className="text-[11px] uppercase tracking-widest text-white/40">
          Why this classification
        </div>
        <div className="mt-2">
          <ResponsiveContainer width="100%" height={108}>
            <BarChart
              layout="vertical"
              data={rows}
              barCategoryGap={8}
              margin={{ top: 4, right: 44, bottom: 0, left: 0 }}
            >
              <XAxis type="number" domain={[0, 1]} hide />
              <YAxis
                type="category"
                dataKey="label"
                width={104}
                tick={{ fill: "rgba(255,255,255,0.65)", fontSize: 12 }}
                axisLine={false}
                tickLine={false}
              />
              <Bar
                dataKey="frac"
                fill={isOil ? OIL_COLOR : LOOKALIKE_COLOR}
                barSize={12}
                radius={2}
                isAnimationActive={false}
                background={{ fill: "rgba(255,255,255,0.09)" }}
              >
                <LabelList
                  dataKey="value"
                  position="right"
                  fill="rgba(255,255,255,0.92)"
                  fontSize={12}
                />
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
        <p className="mt-1 text-xs leading-snug text-white/40">
          Geometric features measured from the slick outline — not model probabilities.
        </p>
      </div>

      {/* reference metrics */}
      <div className="mt-4 border-t border-white/10 pt-3">
        <Metric label="Area" value={`${fmt(p.area_km2, 1)} km²`} />
        <Metric label="Shape class" value={p.shape_class} />
        <Metric
          label="Centroid"
          value={`${fmt(p.centroid?.[0], 3)}, ${fmt(p.centroid?.[1], 3)}`}
        />
        <Metric label="ID" value={p.id} />
      </div>
    </div>
  );
}

/**
 * Trace-stage origin card — the Stage 2 result the rewind converges on. Reads the already-parsed
 * `origin` bundle from the store (never re-fetched); the slider / map / particles update around
 * it without this card re-rendering. Fields per docs/04 §Phase 3: centroid, 50/90 % radii, the
 * origin time window (which doubles as the age statement — CONTRACTS §6), ensemble runs, and the
 * uncertainty note. Centroid is shown to 5 dp to match the coordinate-precision convention.
 */
function TraceCard({ origin }: { origin: OriginBundle }) {
  return (
    <div className="rounded-md border border-white/10 bg-white/[0.03] p-4">
      <Metric
        label="Centroid"
        value={`${fmt(origin.centroid[0], 5)}, ${fmt(origin.centroid[1], 5)}`}
      />
      <Metric label="50% radius" value={`${fmt(origin.radius50Km, 1)} km`} />
      <Metric label="90% radius" value={`${fmt(origin.radius90Km, 1)} km`} />
      <Metric label="Ensemble runs" value={`${origin.ensembleRuns}`} />

      {/* Time window — too long for a single justified Metric row; stack it. `title` keeps the
          raw ISO/Z string reachable. It doubles as the age statement (CONTRACTS §6). */}
      <div className="mt-3 border-t border-white/10 pt-3">
        <div className="text-sm text-white/50">Origin time window</div>
        <div
          className="mt-1 font-mono text-sm text-white/90"
          title={origin.timeWindow[0]}
        >
          {fmtUtc(origin.timeWindow[0])}
        </div>
        <div
          className="font-mono text-sm text-white/90"
          title={origin.timeWindow[1]}
        >
          <span className="text-white/40">→</span> {fmtUtc(origin.timeWindow[1])}
        </div>
      </div>

      <p className="mt-4 border-t border-white/10 pt-3 text-xs leading-snug text-white/40">
        The cloud widens with rewind depth — the further back you drift, the less
        certain the origin.
      </p>
    </div>
  );
}

export default function ContextPanel() {
  const activeStage = useAppStore((s) => s.activeStage);
  const detections = useAppStore((s) => s.detections);
  const selectedDetectionId = useAppStore((s) => s.selectedDetectionId);
  const origin = useAppStore((s) => s.origin);
  const originStatus = useAppStore((s) => s.originStatus);
  const originError = useAppStore((s) => s.originError);

  const oilCount =
    detections?.features.filter((f) => f.properties.classification === "oil")
      .length ?? 0;
  const selected = detections?.features.find(
    (f) => f.properties.id === selectedDetectionId,
  );

  return (
    <aside className="flex w-80 shrink-0 flex-col gap-3 overflow-y-auto border-l border-white/10 bg-[#0b0f14] p-4">
      <div className="text-[11px] uppercase tracking-widest text-white/35">
        {ACT_LABELS[activeStage]}
      </div>

      {activeStage === "detect" &&
        (oilCount === 0 ? (
          <>
            <p className="rounded-md border border-white/10 bg-white/5 p-3 text-sm text-white/70">
              No spill detected in this scene.
            </p>
            {selected && <DetectionCard p={selected.properties} />}
          </>
        ) : selected ? (
          <DetectionCard p={selected.properties} />
        ) : (
          <p className="text-sm text-white/40">Select a detection on the map.</p>
        ))}

      {activeStage === "trace" &&
        (originStatus === "error" ? (
          <div className="rounded-md border border-[#ff4d4d]/40 bg-[#ff4d4d]/10 p-3 text-sm text-[#ffb0b0]">
            <div className="font-semibold text-[#ff8a8a]">
              Origin bundle failed to load
            </div>
            <p className="mt-1 whitespace-pre-wrap text-xs text-[#ffb0b0]/80">
              {originError}
            </p>
            <p className="mt-2 text-xs text-[#ffb0b0]/60">
              This is a contract bug — tell Akshat. The frontend does not patch
              bundle data.
            </p>
          </div>
        ) : origin ? (
          <TraceCard origin={origin} />
        ) : (
          <p className="text-sm text-white/40">Loading origin estimate…</p>
        ))}

      {activeStage === "attribute" && (
        <p className="text-xs text-white/40">
          {ACT_LABELS[activeStage]} — available in a later phase.
        </p>
      )}
    </aside>
  );
}
