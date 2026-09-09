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
import type { DetectionProperties } from "@/lib/contracts";
import type { OriginBundle } from "@/lib/origin";
import type { ExcludedVessel, Funnel, Suspect, SuspectsBundle } from "@/lib/suspects";

// Classification colours — same hex as the map detection polygons.
const OIL_COLOR = "#ff4d4d";
const LOOKALIKE_COLOR = "#9aa4b2";

const fmt = (x: number | undefined, digits: number): string =>
  typeof x === "number" && Number.isFinite(x)
    ? x.toFixed(digits).replace("-", "−") // real minus sign
    : "—";



const fmtDay = (iso: string): string => {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d
    .toLocaleDateString("en-GB", {
      day: "2-digit",
      month: "short",
      year: "numeric",
      timeZone: "UTC",
    })
    .toUpperCase();
};

// HH:MM string only
const fmtTime = (iso: string): string => {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleTimeString("en-GB", {
    hour: "2-digit",
    minute: "2-digit",
    timeZone: "UTC",
  });
};

/**
 * Display-only scaling for the "why this classification" bars.
 * See original comments — these are NOT model probabilities.
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

// ─── Shared small atoms ──────────────────────────────────────────────────────

/** Dimmed uppercase section label */
function SectionLabel({ children }: { children: React.ReactNode }) {
  return (
    <div className="mt-5 text-[9px] font-semibold uppercase tracking-[0.16em] text-white/35 first:mt-0">
      {children}
    </div>
  );
}

/** Hairline divider */
function Divider() {
  return <div className="my-4 border-t border-white/[0.07]" />;
}

/** One row: label left, monospace value right */
function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-baseline justify-between gap-3 py-[3px]">
      <span className="text-[11px] text-white/45">{label}</span>
      <span className="font-mono text-[11px] text-white/85 tabular-nums">
        {value}
      </span>
    </div>
  );
}

// ─── Detect stage card ────────────────────────────────────────────────────────

function DetectionCard({ p }: { p: DetectionProperties }) {
  const isOil = p.classification === "oil";
  const rows = featureRows(p);
  const accentColor = isOil ? OIL_COLOR : LOOKALIKE_COLOR;

  // Object number from id: "det-01" → "01"
  const objNum = p.id.replace(/^det-?/i, "").padStart(2, "0").toUpperCase();

  return (
    <div className="flex flex-col">
      {/* ── Header ── */}
      <div className="border-l-2 pl-3" style={{ borderColor: accentColor }}>
        <div className="text-[9px] font-semibold uppercase tracking-[0.14em] text-white/35">
          Object {objNum}
        </div>
        <div
          className="mt-0.5 text-[22px] font-semibold leading-tight tracking-tight"
          style={{ color: isOil ? OIL_COLOR : LOOKALIKE_COLOR }}
        >
          {isOil ? "Oil Slick" : "Look-alike"}
        </div>
        <div className="mt-0.5 font-mono text-[11px] text-white/50">
          {Number.isFinite(p.confidence)
            ? `${Math.round(p.confidence * 100)}% confidence`
            : "— confidence"}
        </div>
      </div>

      <Divider />

      {/* ── Geometry ── */}
      <SectionLabel>Geometry</SectionLabel>
      <div className="mt-1.5 space-y-0.5">
        <Row label="Area" value={`${fmt(p.area_km2, 1)} km²`} />
        <Row
          label="Shape class"
          value={
            p.shape_class === "linear" ? "Linear / Elongated" : "Blob / Radial"
          }
        />
      </div>

      <Divider />

      {/* ── Centroid ── */}
      <SectionLabel>Centroid</SectionLabel>
      <div className="mt-1.5">
        <div className="font-mono text-[12px] leading-snug text-white/85 tabular-nums">
          {fmt(p.centroid?.[1], 5)}° N
        </div>
        <div className="font-mono text-[12px] leading-snug text-white/85 tabular-nums">
          {fmt(p.centroid?.[0], 5)}° E
        </div>
      </div>

      <Divider />

      {/* ── Why this classification ── */}
      <SectionLabel>Why this classification</SectionLabel>
      <div className="mt-2">
        <ResponsiveContainer width="100%" height={96}>
          <BarChart
            layout="vertical"
            data={rows}
            barCategoryGap={8}
            margin={{ top: 2, right: 40, bottom: 0, left: 0 }}
          >
            <XAxis type="number" domain={[0, 1]} hide />
            <YAxis
              type="category"
              dataKey="label"
              width={96}
              tick={{ fill: "rgba(255,255,255,0.50)", fontSize: 11 }}
              axisLine={false}
              tickLine={false}
            />
            <Bar
              dataKey="frac"
              fill={accentColor}
              barSize={10}
              radius={1}
              isAnimationActive={false}
              background={{ fill: "rgba(255,255,255,0.06)" }}
            >
              <LabelList
                dataKey="value"
                position="right"
                fill="rgba(255,255,255,0.80)"
                fontSize={11}
              />
            </Bar>
          </BarChart>
        </ResponsiveContainer>
        <p className="mt-1 text-[10px] leading-snug text-white/28">
          Geometric features from slick outline — not model probabilities.
        </p>
      </div>

      <Divider />

      {/* ── Detection ID ── */}
      <SectionLabel>Detection ID</SectionLabel>
      <div className="mt-1.5 font-mono text-[11px] text-white/60">{p.id}</div>
    </div>
  );
}

// ─── Trace stage card ─────────────────────────────────────────────────────────

function TraceCard({ origin }: { origin: OriginBundle }) {
  const [start, end] = origin.timeWindow;

  return (
    <div className="flex flex-col">
      {/* ── Header ── */}
      <div>
        <div className="text-[9px] font-semibold uppercase tracking-[0.14em] text-white/35">
          Stage 02 — Trace
        </div>
        <div className="mt-1 text-[22px] font-semibold leading-tight tracking-tight text-white">
          Origin Probability
        </div>
        <div className="mt-0.5 font-mono text-[11px] text-white/40">
          {origin.ensembleRuns} ensemble runs
        </div>
      </div>

      <Divider />

      {/* ── Centroid ── */}
      <SectionLabel>Centroid</SectionLabel>
      <div className="mt-1.5">
        <div className="font-mono text-[12px] leading-snug text-white/85 tabular-nums">
          {fmt(origin.centroid[1], 5)}° N
        </div>
        <div className="font-mono text-[12px] leading-snug text-white/85 tabular-nums">
          {fmt(origin.centroid[0], 5)}° E
        </div>
      </div>

      <Divider />

      {/* ── Uncertainty regions ── */}
      <SectionLabel>Uncertainty Regions</SectionLabel>
      <div className="mt-1.5 space-y-0.5">
        <Row label="50% region" value={`${fmt(origin.radius50Km, 1)} km`} />
        <Row label="90% region" value={`${fmt(origin.radius90Km, 1)} km`} />
      </div>

      <Divider />

      {/* ── Release window ── */}
      <SectionLabel>Release Window</SectionLabel>
      <div className="mt-1.5">
        <div className="font-mono text-[13px] font-semibold text-white/90">
          {fmtDay(start)}
        </div>
        <div className="font-mono text-[11px] text-white/70">
          {fmtTime(start)} – {fmtTime(end)} UTC
        </div>
      </div>

      {/* Bounded estimate badge */}
      {origin.abstain && (
        <div className="mt-3 rounded border border-white/10 px-2.5 py-1.5 text-[10px] uppercase tracking-wide text-white/40">
          Bounded Estimate
        </div>
      )}
      {!origin.abstain && (
        <div className="mt-3 rounded border border-white/[0.08] px-2.5 py-1.5 text-[10px] uppercase tracking-wide text-white/30">
          Bounded Estimate
        </div>
      )}

      {/* Interpretive note */}
      <p className="mt-4 text-[10px] leading-relaxed text-white/28">
        Released between these times — the ensemble did not converge on a single
        channel.
      </p>
      <p className="mt-2 text-[10px] leading-relaxed text-white/28">
        The cloud widens with rewind depth. The further back you drift, the less
        certain the origin.
      </p>
    </div>
  );
}

// ─── Attribute stage card ──────────────────────────────────────────────────────

// The contract's exact abstain-state wording (docs/CONTRACTS.md §6) — reused verbatim, not
// rewritten, so the frontend never claims something the pipeline didn't measure.
const ABSTAIN_MESSAGE = "Attribution not possible at acceptable confidence.";

/** Static 4-step bar — "no animation needed" per docs/04 Phase 5. Steps only ever shrink or
 * hold, left to right (CONTRACTS §8: funnel counts are non-increasing), so the bar length
 * itself carries the funnel's shape. */
function FunnelBar({ funnel }: { funnel: Funnel }) {
  const steps: { label: string; value: number }[] = [
    { label: "In Region", value: funnel.inRegion },
    { label: "In Window", value: funnel.inWindow },
    { label: "Plausible", value: funnel.plausible },
    { label: "Scored", value: funnel.scored },
  ];
  const max = Math.max(1, funnel.inRegion);
  return (
    <div className="space-y-2.5">
      {steps.map((s) => {
        const pct = funnel.inRegion > 0 ? Math.max(2, Math.min(100, (s.value / max) * 100)) : 0;
        return (
          <div key={s.label}>
            <div className="flex items-baseline justify-between">
              <span className="text-[10px] text-white/45">{s.label}</span>
              <span className="font-mono text-[11px] text-white/85 tabular-nums">
                {s.value}
              </span>
            </div>
            <div className="mt-1 h-1 rounded-full bg-white/[0.06]">
              <div
                className="h-1 rounded-full bg-[#f97316]"
                style={{ width: `${pct}%` }}
              />
            </div>
          </div>
        );
      })}
    </div>
  );
}

function SuspectCard({ s, rank }: { s: Suspect; rank: number }) {
  return (
    <div className="rounded border border-white/[0.08] p-3">
      <div className="flex items-start justify-between gap-2">
        <div>
          <div className="text-[9px] font-semibold uppercase tracking-[0.14em] text-white/35">
            Suspect {String(rank).padStart(2, "0")}
          </div>
          <div className="mt-0.5 text-[14px] font-semibold leading-tight text-white/90">
            {s.name}
          </div>
          <div className="mt-0.5 font-mono text-[10px] text-white/40">
            MMSI {s.mmsi}
            {s.vesselType ? ` · ${s.vesselType}` : ""}
          </div>
        </div>
        <div className="shrink-0 font-mono text-[15px] font-semibold text-[#f97316]">
          {fmt(s.score * 100, 0)}%
        </div>
      </div>

      <div className="mt-2 space-y-0.5">
        <Row label="Closest approach" value={`${fmt(s.closestKm, 1)} km`} />
        {s.closestTime && (
          <Row
            label="Closest time"
            value={`${fmtDay(s.closestTime)} ${fmtTime(s.closestTime)} UTC`}
          />
        )}
        {s.headingConsistent !== undefined && (
          <Row
            label="Heading"
            value={s.headingConsistent ? "Consistent" : "Inconsistent"}
          />
        )}
        {s.aisGapMinutes !== undefined && (
          <Row
            label="AIS gap"
            value={s.aisGapMinutes > 0 ? `${s.aisGapMinutes} min` : "None"}
          />
        )}
      </div>

      <ul className="mt-2 space-y-1">
        {s.reasons.map((r, i) => (
          <li key={i} className="flex gap-1.5 text-[10px] leading-snug text-white/50">
            <span className="shrink-0 text-white/25">–</span>
            <span>{r}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

/** Visually "ruled out" per docs/06 — muted + strikethrough on the name. The map's vessel
 * layer conveys the same role with reduced opacity/width (see MapView.tsx); this is the card
 * half of that motif. */
function ExcludedCard({ e }: { e: ExcludedVessel }) {
  return (
    <div className="rounded border border-white/[0.06] bg-white/[0.02] p-3">
      <div className="text-[13px] font-medium text-white/45 line-through decoration-white/25">
        {e.name ?? e.mmsi}
      </div>
      <div className="mt-0.5 font-mono text-[10px] text-white/30">
        MMSI {e.mmsi}
        {e.closestKm !== undefined ? ` · ${fmt(e.closestKm, 1)} km` : ""}
      </div>
      <p className="mt-1.5 text-[10px] leading-relaxed text-white/40">{e.reason}</p>
    </div>
  );
}

/**
 * `gate` decides whether the suspect/exclusion lists render:
 *  - "loading"  — origin.json hasn't resolved yet; abstain status is unknown. Show the funnel
 *                 only, never the suspect list, even though suspects.json may already be here.
 *  - "unknown"  — origin.json failed to load. Same caution as "loading" — we cannot confirm
 *                 abstain is false, so no suspect is named.
 *  - "abstain"  — origin.abstain === true. CONTRACTS §6/§8: suspects must be empty; the frontend
 *                 does not render one even if the file somehow contained one.
 *  - "clear"    — origin.abstain === false, confirmed. Render suspects.json as given.
 */
function AttributeCard({
  suspects,
  gate,
}: {
  suspects: SuspectsBundle;
  gate: "loading" | "unknown" | "abstain" | "clear";
}) {
  return (
    <div className="flex flex-col">
      <div>
        <div className="text-[9px] font-semibold uppercase tracking-[0.14em] text-white/35">
          Stage 03 — Attribute
        </div>
        <div className="mt-1 text-[22px] font-semibold leading-tight tracking-tight text-white">
          Vessel Attribution
        </div>
      </div>

      <Divider />

      <SectionLabel>Attribution Funnel</SectionLabel>
      <div className="mt-2">
        <FunnelBar funnel={suspects.funnel} />
      </div>

      <Divider />

      {gate === "loading" && (
        <p className="text-[11px] text-white/35">Confirming attribution status…</p>
      )}

      {gate === "unknown" && (
        <div className="rounded border border-white/10 bg-white/[0.03] p-3 text-[11px] leading-relaxed text-white/50">
          Origin estimate unavailable — the suspect list is withheld until abstain status can be
          confirmed.
        </div>
      )}

      {gate === "abstain" && (
        <div className="rounded border border-white/10 bg-white/[0.03] p-3 text-[11px] leading-relaxed text-white/55">
          {ABSTAIN_MESSAGE}
        </div>
      )}

      {gate === "clear" && (
        <>
          <SectionLabel>Suspects</SectionLabel>
          <div className="mt-2 space-y-2">
            {suspects.suspects.length === 0 ? (
              <p className="text-[11px] text-white/35">No suspects scored.</p>
            ) : (
              suspects.suspects.map((s, i) => (
                <SuspectCard key={s.mmsi} s={s} rank={i + 1} />
              ))
            )}
          </div>

          <Divider />

          <SectionLabel>Excluded</SectionLabel>
          <div className="mt-2 space-y-2">
            {suspects.excluded.map((e) => (
              <ExcludedCard key={e.mmsi} e={e} />
            ))}
          </div>
        </>
      )}
    </div>
  );
}

// ─── Main panel ───────────────────────────────────────────────────────────────

export default function ContextPanel() {
  const activeStage = useAppStore((s) => s.activeStage);
  const detections = useAppStore((s) => s.detections);
  const selectedDetectionId = useAppStore((s) => s.selectedDetectionId);
  const origin = useAppStore((s) => s.origin);
  const originStatus = useAppStore((s) => s.originStatus);
  const originError = useAppStore((s) => s.originError);
  const suspects = useAppStore((s) => s.suspects);
  const suspectsStatus = useAppStore((s) => s.suspectsStatus);
  const suspectsError = useAppStore((s) => s.suspectsError);

  const oilCount =
    detections?.features.filter((f) => f.properties.classification === "oil")
      .length ?? 0;
  const selected = detections?.features.find(
    (f) => f.properties.id === selectedDetectionId,
  );

  return (
    <aside className="flex w-72 shrink-0 flex-col overflow-y-auto border-l border-white/[0.08] bg-[#0b0f14] px-5 py-5">
      {/* ── Detect ── */}
      {activeStage === "detect" &&
        (oilCount === 0 ? (
          <>
            <p className="rounded border border-white/[0.08] bg-white/[0.03] p-3 text-[11px] text-white/55">
              No spill detected in this scene.
            </p>
            {selected && <DetectionCard p={selected.properties} />}
          </>
        ) : selected ? (
          <DetectionCard p={selected.properties} />
        ) : (
          <p className="text-[11px] text-white/35">
            Select a detection on the map.
          </p>
        ))}

      {/* ── Trace ── */}
      {activeStage === "trace" &&
        (originStatus === "error" ? (
          <div className="rounded border border-[#ff4d4d]/30 bg-[#ff4d4d]/[0.08] p-3">
            <div className="text-[11px] font-semibold text-[#ff8a8a]">
              Origin bundle failed to load
            </div>
            <p className="mt-1 whitespace-pre-wrap text-[10px] text-[#ffb0b0]/70">
              {originError}
            </p>
            <p className="mt-2 text-[10px] text-[#ffb0b0]/50">
              This is a contract bug — tell Akshat. The frontend does not patch
              bundle data.
            </p>
          </div>
        ) : origin ? (
          <TraceCard origin={origin} />
        ) : (
          <p className="text-[11px] text-white/35">Loading origin estimate…</p>
        ))}

      {/* ── Attribute ── */}
      {activeStage === "attribute" &&
        (suspectsStatus === "error" ? (
          <div className="rounded border border-[#ff4d4d]/30 bg-[#ff4d4d]/[0.08] p-3">
            <div className="text-[11px] font-semibold text-[#ff8a8a]">
              Suspects bundle failed to load
            </div>
            <p className="mt-1 whitespace-pre-wrap text-[10px] text-[#ffb0b0]/70">
              {suspectsError}
            </p>
            <p className="mt-2 text-[10px] text-[#ffb0b0]/50">
              This is a contract bug — tell Akshat. The frontend does not patch
              bundle data.
            </p>
          </div>
        ) : suspects ? (
          <AttributeCard
            suspects={suspects}
            gate={
              origin === null
                ? originStatus === "error"
                  ? "unknown"
                  : "loading"
                : origin.abstain
                  ? "abstain"
                  : "clear"
            }
          />
        ) : (
          <p className="text-[11px] text-white/35">Loading attribution…</p>
        ))}
    </aside>
  );
}
