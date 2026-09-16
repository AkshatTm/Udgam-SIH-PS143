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
import ReRunButton from "./ReRunButton";
import type {
  AisSource,
  Bounds,
  CaseMeta,
  DetectionProperties,
  DischargeClass,
  Provenance,
} from "@/lib/contracts";
import type { AgeMethod, OriginBundle } from "@/lib/origin";
import type {
  DarkVessel,
  ExcludedVessel,
  Funnel,
  Infrastructure,
  NaturalSeep,
  Suspect,
  SuspectComponents,
  SuspectsBundle,
} from "@/lib/suspects";
import InfoDot from "@/components/InfoDot";

// Classification colours. The comment always claimed these matched the map; they did not — the
// panel was a hair redder and a shade lighter than the polygons beside it. Both now read the
// --oil / --reject tokens, which MapView's OIL_COLOR / LOOKALIKE_COLOR also carry, so a slick
// called red in this panel is the same red on the map.
const OIL_COLOR = "var(--oil)";
const LOOKALIKE_COLOR = "var(--reject)";

const fmt = (x: number | undefined, digits: number): string =>
  typeof x === "number" && Number.isFinite(x)
    ? x.toFixed(digits).replace("-", "−") // real minus sign
    : "—";

// Coordinates render as magnitude + hemisphere, never a signed number beside a fixed "N"/"E"
// (that printed "−79.68° E" on every US case). Bundles stay signed [lon, lat]; this is display.
const fmtLat = (v: number | undefined, digits: number): string =>
  typeof v === "number" && Number.isFinite(v)
    ? `${Math.abs(v).toFixed(digits)}° ${v < 0 ? "S" : "N"}`
    : "—";
const fmtLon = (v: number | undefined, digits: number): string =>
  typeof v === "number" && Number.isFinite(v)
    ? `${Math.abs(v).toFixed(digits)}° ${v < 0 ? "W" : "E"}`
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
    <div className="mt-5 t-label first:mt-0">
      {children}
    </div>
  );
}

/** Hairline divider */
function Divider() {
  return <div className="my-4 border-t border-line" />;
}

/** One row: label left, monospace value right */
function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-baseline justify-between gap-3 py-[3px]">
      <span className="t-small text-ink-2">{label}</span>
      <span className="font-mono text-[13px] text-ink tabular-nums">
        {value}
      </span>
    </div>
  );
}

/**
 * MetricRow — plain-language label first, muted technical term second,
 * optional InfoDot affordance (C4 + C5).
 */
function MetricRow({
  primary,
  technical,
  value,
  tip,
}: {
  primary: string;
  technical?: string;
  value: string;
  tip: string;
}) {
  return (
    // `relative` — the InfoDot's tooltip anchors to this row (see InfoDot.tsx), not to the
    // button itself, so it stays inside the panel regardless of how long `primary` is.
    <div className="relative flex items-start justify-between gap-3 py-[3px]">
      <span className="flex flex-col gap-0">
        <span className="flex items-center gap-1 t-small text-ink">
          {primary}
          <InfoDot tip={tip} />
        </span>
        {technical && (
          <span className="text-[11px] text-ink-3">{technical}</span>
        )}
      </span>
      <span className="font-mono text-[13px] text-ink tabular-nums shrink-0">
        {value}
      </span>
    </div>
  );
}

// docs/team/harshita-frontend.md Phase 5.3 — discharge_class badge (Master §6.3). Plain language first, technical
// enum second (C4), same convention as MetricRow. Renders the producer's value verbatim —
// never a stronger claim, never a frontend-inferred category.
const DISCHARGE_CLASS_PLAIN: Record<DischargeClass, string> = {
  chronic: "Chronic discharge",
  acute: "Acute discharge",
  unknown: "Discharge type unknown",
};

function DischargeBadge({ value }: { value: DischargeClass }) {
  return (
    <div className="mt-1.5 inline-flex items-baseline gap-1.5 rounded border border-line-strong bg-white/[0.05] px-2 py-1">
      <span className="text-[12px] font-semibold text-ink">
        {DISCHARGE_CLASS_PLAIN[value]}
      </span>
      <span className="font-mono text-[11px] text-ink-3">{value}</span>
    </div>
  );
}

// ─── Detect stage card ────────────────────────────────────────────────────────

/**
 * The classical rule's contrast threshold on every `satellite` bundle. It is passed to run.py as
 * `--rule-contrast -3.0` and NOT recorded in the bundle, so it is pinned here — verified 13 Sept by
 * back-solving each shipped feature's (confidence, contrast_db) against run.py's margin formula:
 * all seven live cases resolve to −3.0, re-checked after the D34 rerun. run.py now refuses to run
 * the classical path without the flag, but a rerun with a DIFFERENT value would still make this
 * label wrong without the bundle saying so — rerun the back-solve after any detector rerun.
 */
const RULE_CONTRAST_DB = -3.0;
/** Clear/marginal boundary. run.py maps contrast linearly: conf = 0.5 + 0.25·(−3.0 − c)/3.0,
 *  so −4.5 dB is exactly confidence 0.625. */
const CLEAR_CONTRAST_DB = -4.5;

/**
 * `confidence` is [0,1] on every case — and it is NOT the same quantity on every case.
 * Master §6.3 / D33: on `provenance: "benchmark"` the CNN scene classifier produced it and it is
 * a calibrated probability, so a percentage is honest. On `satellite` (our seven GEE cases, i.e.
 * everything we show on stage) the classical rule path produced it, and it is a MARGIN from the
 * decision boundary. Printing "87% confidence" there asserts a calibration nobody has measured.
 *
 * So on `satellite` we show the quantity the rule actually measures — dB of contrast — in two
 * bands (Soumirya, 13 Sept). A three-band split on the [0,1] number collapsed to 1/11/0 on the 12 live
 * oil detections. A look-alike is not banded: it may have been rejected on elongation or area, not
 * contrast, so a contrast band would imply a reason we did not check.
 */
function confidenceLabel(
  p: DetectionProperties,
  provenance: Provenance | undefined,
): string {
  if (provenance === "benchmark") {
    return Number.isFinite(p.confidence)
      ? `${Math.round(p.confidence * 100)}% confidence`
      : "— confidence";
  }
  const c = p.contrast_db;
  if (!Number.isFinite(c)) return "— rule margin";
  const db = `${c.toFixed(1)} dB`;
  const rule = `${RULE_CONTRAST_DB.toFixed(1)} dB rule`;
  if (p.classification !== "oil") return `not oil under rule · ${db} contrast`;
  if (c === RULE_CONTRAST_DB) return `at threshold · ${rule}`;
  if (c <= CLEAR_CONTRAST_DB) return `clear · ${db} vs ${rule}`;
  return `marginal · ${db} vs ${rule}`;
}

function DetectionCard({ p }: { p: DetectionProperties }) {
  const isOil = p.classification === "oil";
  const rows = featureRows(p);
  const accentColor = isOil ? OIL_COLOR : LOOKALIKE_COLOR;
  const provenance = useAppStore((s) => s.meta?.provenance);

  // Object number from id: "det-01" → "01"
  const objNum = p.id.replace(/^det-?/i, "").padStart(2, "0").toUpperCase();

  return (
    <div className="flex flex-col">
      {/* ── Header ── */}
      <div className="border-l-2 pl-3" style={{ borderColor: accentColor }}>
        <div className="t-label">
          Object {objNum}
        </div>
        <div
          className="mt-0.5 t-title"
          style={{ color: isOil ? OIL_COLOR : LOOKALIKE_COLOR }}
        >
          {isOil ? "Oil slick" : "Look-alike"}
        </div>
        <div className="mt-0.5 font-mono text-[13px] text-ink-2">
          {confidenceLabel(p, provenance)}
        </div>
        {p.discharge_class && <DischargeBadge value={p.discharge_class} />}
      </div>

      <Divider />

      {/* ── Measurements — plain-language first (C4 + C5) ── */}
      <SectionLabel>Measurements</SectionLabel>
      <div className="mt-1.5 space-y-1">
        <MetricRow
          primary="How big"
          technical="area"
          value={`${fmt(p.area_km2, 1)} km²`}
          tip="Total surface area of the dark patch measured from the satellite outline."
        />
        <MetricRow
          primary="How stretched"
          technical="elongation"
          value={fmt(p.elongation, 1)}
          tip="Length divided by width. Oil from a moving ship is long and thin; algae and wind slicks are usually round."
        />
        <MetricRow
          primary="How sharp-edged"
          technical="edge gradient"
          value={fmt(p.edge_gradient, 2)}
          tip="Strength of the brightness change at the patch border. Oil films produce a sharper edge than most natural look-alikes."
        />
        <MetricRow
          primary="How much darker"
          technical="contrast"
          value={`${fmt(p.contrast_db, 1)} dB`}
          tip="How much darker the patch is than the surrounding sea in radar backscatter. Oil dampens waves, reducing the return signal."
        />
        <MetricRow
          primary="Shape"
          technical="shape class"
          value={p.shape_class === "linear" ? "Linear / Elongated" : "Blob / Radial"}
          tip="Overall outline shape derived from the patch geometry. Linear patches are consistent with a moving vessel discharge."
        />
      </div>

      <Divider />

      {/* ── Centroid ── */}
      <SectionLabel>Centroid</SectionLabel>
      <div className="mt-1.5">
        <div className="font-mono text-[13px] leading-snug text-ink tabular-nums">
          {fmtLat(p.centroid?.[1], 5)}
        </div>
        <div className="font-mono text-[13px] leading-snug text-ink tabular-nums">
          {fmtLon(p.centroid?.[0], 5)}
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
        <p className="mt-1 text-[13px] leading-snug text-ink-3">
          Geometric features from slick outline — not model probabilities.
        </p>
      </div>

      <Divider />

      {/* ── Detection ID ── */}
      <SectionLabel>Detection ID</SectionLabel>
      <div className="mt-1.5 font-mono text-[13px] text-ink-2">{p.id}</div>
    </div>
  );
}

// docs/team/harshita-frontend.md Phase 5.3 — age_method plain-language labels (Master §6.5, C4). "none" and
// "disagreement" are genuine estimator outcomes, not errors — worded as such, not hidden.
const AGE_METHOD_LABEL: Record<AgeMethod, string> = {
  shear: "Estimated from current shear",
  fay: "Estimated from spreading rate",
  elongation: "Estimated from slick elongation",
  combined: "Combined estimate",
  disagreement: "Estimators disagree — range widened",
  none: "No estimator produced a result — using the search bracket",
};

// ─── Trace stage card ─────────────────────────────────────────────────────────

function TraceCard({ origin }: { origin: OriginBundle }) {
  const [start, end] = origin.timeWindow;

  return (
    <div className="flex flex-col">
      {/* ── Header ── */}
      <div>
        <div className="t-label">
          Stage 02 — Trace
        </div>
        <div className="mt-1 t-title text-ink">
          Where the oil came from
        </div>
        <div className="mt-0.5 font-mono text-[11px] text-ink-3">
          {origin.ensembleRuns} simulations
        </div>
      </div>

      <Divider />

      {/* ── Best estimate ── */}
      <SectionLabel>Best estimate</SectionLabel>
      {/* `relative` — see InfoDot.tsx: the tooltip anchors to this row, not the button. */}
      <div className="relative mt-1.5 flex items-start gap-1">
        <div className="flex-1">
          <div className="font-mono text-[13px] leading-snug text-ink tabular-nums">
            {fmtLat(origin.centroid[1], 5)}
          </div>
          <div className="font-mono text-[13px] leading-snug text-ink tabular-nums">
            {fmtLon(origin.centroid[0], 5)}
          </div>
        </div>
        <InfoDot
          align="right"
          tip="The centroid of the origin probability field — where the ensemble of backwards-drift runs most agree the oil entered the water."
        />
      </div>

      <Divider />

      {/* ── Uncertainty regions — plain-language first (C4 + C5) ── */}
      <SectionLabel>Uncertainty</SectionLabel>
      <div className="mt-1.5 space-y-1">
        <MetricRow
          primary="Half the runs land within"
          technical="50 % radius"
          value={`${fmt(origin.radius50Km, 1)} km`}
          tip="Radius of the circle that contains half of the 50 backwards-drift simulations. Smaller means the origin is more certain."
        />
        <MetricRow
          primary="Nine in ten within"
          technical="90 % radius"
          value={`${fmt(origin.radius90Km, 1)} km`}
          tip="Radius of the circle that contains nine out of ten simulations. It measures how closely the runs agree with each other (precision), not how close they are to the true release point."
        />
      </div>

      <Divider />

      {/* ── Release window — plain-language first (C4 + C5) ── */}
      <SectionLabel>Released between</SectionLabel>
      {/* `relative` — see InfoDot.tsx: the tooltip anchors to this row, not the button. */}
      <div className="relative mt-1.5 flex items-start gap-1">
        <div className="flex-1">
          <div className="font-mono text-[15px] font-semibold text-ink">
            {fmtDay(start)}
          </div>
          <div className="font-mono text-[13px] text-ink-2">
            {fmtTime(start)} – {fmtTime(end)} UTC
          </div>
        </div>
        <InfoDot
          align="right"
          tip="The time window during which the oil most plausibly entered the water, derived from backwards-drift timing across all simulations."
        />
      </div>

      {/* D12 — the method line below says whether this window is a search bracket or a
          measured estimate. No always-on caption: it contradicted "Measured estimate". */}
      {origin.timeWindowMethod === "bounded" && (
        <p className="mt-2 text-[13px] leading-relaxed text-ink-2">
          Search bracket (not a measured release time)
        </p>
      )}
      {origin.timeWindowMethod === "convergence" && (
        <p className="mt-2 text-[13px] leading-relaxed text-ink-2">
          Measured estimate
        </p>
      )}

      {/* docs/team/harshita-frontend.md Phase 5.3 — estimated age (Master §6.5). ageHours and ageMethod are
          independently optional (no invented pairing rule): each row renders only when its
          own field is present, and the whole block hides when both are absent. */}
      {(origin.ageHours || origin.ageMethod) && (
        <>
          <Divider />
          <SectionLabel>Estimated age</SectionLabel>
          {/* `relative` — see InfoDot.tsx: the tooltip anchors to this row, not the button. */}
          <div className="relative mt-1.5 flex items-start gap-1">
            <div className="flex-1">
              {origin.ageHours && (
                <div className="font-mono text-[15px] font-semibold text-ink">
                  {fmt(origin.ageHours[0], 0)} – {fmt(origin.ageHours[1], 0)} hours
                </div>
              )}
              {origin.ageMethod && (
                <div className="mt-0.5 text-[13px] text-ink-2">
                  {AGE_METHOD_LABEL[origin.ageMethod]}
                </div>
              )}
            </div>
            <InfoDot
              align="right"
              tip="How long ago the oil likely entered the water, estimated from how the slick has spread and sheared since release."
            />
          </div>
          {/* Per-estimator bands, collapsed. A null band is "not applicable" — never a zero. */}
          {origin.ageEstimators && Object.keys(origin.ageEstimators).length > 0 && (
            <details className="mt-2 text-[13px] text-ink-2">
              <summary className="cursor-pointer select-none text-ink-3 hover:text-ink-2">
                Per-estimator bands
              </summary>
              <div className="mt-1 space-y-0.5">
                {Object.entries(origin.ageEstimators).map(([name, band]) => (
                  <Row
                    key={name}
                    label={name.charAt(0).toUpperCase() + name.slice(1)}
                    value={band === null ? "not applicable" : `${fmt(band[0], 0)} – ${fmt(band[1], 0)} h`}
                  />
                ))}
              </div>
            </details>
          )}
        </>
      )}

      {/* Origin-confidence state. The two branches are genuinely distinct:
          abstain === true  → the origin cloud is too diffuse to attribute from,
                              and Stage 3 names no suspects (docs/CONTRACTS.md §6);
          abstain === false → the origin is tight enough for attribution to run. */}
      {origin.abstain ? (
        <div className="mt-3 rounded border border-line bg-raised px-2.5 py-1.5 text-[13px] leading-relaxed text-ink-2">
          Origin cloud too diffuse — no suspects can be named.
        </div>
      ) : (
        <div className="mt-3 rounded border border-line px-2.5 py-1.5 text-[10px] uppercase tracking-wide text-ink-3">
          Origin within attribution confidence
        </div>
      )}

      {/* The drifting points are ONE control trajectory (particles.json); the
          uncertainty lives in the origin field and the 50 / 90 % regions above. */}
      <p className="mt-4 text-[13px] leading-relaxed text-ink-3">
        The drifting points trace one representative path, not a spread. The
        uncertainty is the origin probability field and the 50 / 90 % regions
        above, stacked from {origin.ensembleRuns} perturbed runs.
      </p>
    </div>
  );
}

// ─── Attribute stage card ──────────────────────────────────────────────────────

// The contract's exact abstain-state wording (docs/CONTRACTS.md §6) — reused verbatim, not
// rewritten, so the frontend never claims something the pipeline didn't measure.
const ABSTAIN_MESSAGE = "Attribution not possible at acceptable confidence.";

// D20 — which AIS archive scored this case, and therefore which sampling regime the funnel and
// every gap/slowdown "n/a" downstream of it are honest about. No fabricated label for a value
// the loader didn't recognize (only these two exist in the frozen contract).
const AIS_SAMPLING_LABEL: Record<AisSource, string> = {
  noaa_dense: "AIS: 71-second sampling (NOAA)",
  gfw_hourly: "AIS: hourly sampling (Global Fishing Watch)",
};

/** D19 — geological seepage is contextual evidence about the scene, never a suspect: it is
 * rendered above the ranked list, in its own caution tone (the same amber family as
 * VerdictBadge's "partial" — distinct from the orange suspect-score accent and the red
 * contract-error styling), and it is never added to `suspects` or scored/ranked. */
function NaturalSeepNotice({ seep }: { seep: NaturalSeep }) {
  return (
    <div className="rounded border border-[#fbbf24]/30 bg-[#fbbf24]/[0.08] p-3">
      <div className="t-label text-[#fcd34d]/80">
        Documented natural seepage in this area
      </div>
      <p className="mt-1.5 text-[13px] leading-relaxed text-[#fde68a]/80">
        Some or all of this feature may be geological rather than a discharge.
      </p>
      {seep.note && (
        <p className="mt-1.5 text-[13px] leading-relaxed text-[#fde68a]/55">{seep.note}</p>
      )}
      {seep.source && (
        <p className="mt-1 text-[13px] text-[#fde68a]/40">Source: {seep.source}</p>
      )}
    </div>
  );
}

/** Static 4-step bar — "no animation needed" per docs/team/harshita-frontend.md Phase 5. Steps only ever shrink or
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
              <span className="text-[13px] text-ink-2">{s.label}</span>
              <span className="font-mono text-[13px] text-ink tabular-nums">
                {s.value}
              </span>
            </div>
            <div className="mt-1 h-1 rounded-full bg-white/[0.07]">
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

const COMPONENT_LABELS: { key: keyof SuspectComponents; label: string }[] = [
  { key: "proximity", label: "Proximity" },
  { key: "parity", label: "Parity" },
  { key: "temporality", label: "Temporality" },
  { key: "trajectory", label: "Trajectory" },
  { key: "gap", label: "Gap" },
  { key: "slowdown", label: "Slowdown" },
  { key: "typePrior", label: "Type prior" },
];

/** Score-component breakdown behind a suspect's overall score (docs/team/harshita-frontend.md Phase 3.2, Master
 * §6.7). Same bar-track visual language as FunnelBar — no new visual system. A `null`
 * component (e.g. `gap`/`slowdown` on a gfw_hourly case) renders "n/a" with NO bar underneath:
 * a zero-width bar would claim a measurement that was never possible. D29: an unexplained
 * "n/a" reads as a broken feature, so a null component with a matching producer-supplied note
 * renders that note verbatim underneath — never invented here, never shown for a real value. */
function ComponentBars({
  components,
  notes,
}: {
  components: SuspectComponents;
  notes: Suspect["componentNotes"];
}) {
  return (
    <div className="mt-2 space-y-1.5">
      {COMPONENT_LABELS.map(({ key, label }) => {
        const v = components[key];
        // D29 — an unexplained "n/a" reads as a broken feature. The note is the producer's
        // own words, rendered verbatim; nothing is written here when the bundle has none.
        // Producers note every component; inline only where the bar is "n/a" (D29's need),
        // hover title elsewhere, so three cards don't carry 21 lines of prose.
        const note = notes[key];
        return (
          <div key={key} title={v !== null ? note : undefined}>
            <div className="flex items-baseline justify-between">
              <span className="text-[13px] text-ink-2">{label}</span>
              <span className="font-mono text-[13px] text-ink-2 tabular-nums">
                {v === null ? "n/a" : v.toFixed(2)}
              </span>
            </div>
            {v !== null && (
              <div className="mt-0.5 h-1 rounded-full bg-white/[0.07]">
                <div
                  className="h-1 rounded-full bg-[#f97316]"
                  style={{ width: `${Math.max(2, Math.min(100, v * 100))}%` }}
                />
              </div>
            )}
            {v === null && note && (
              <p className="mt-0.5 text-[13px] leading-snug text-ink-3">{note}</p>
            )}
          </div>
        );
      })}
    </div>
  );
}

function SuspectCard({ s, rank }: { s: Suspect; rank: number }) {
  // docs/team/harshita-frontend.md Phase 3.3 — hover lifts through the same store selectedDetectionId already uses,
  // no new state mechanism. MapView reads hoveredSuspectMmsi to emphasise/dim the matching
  // vessel track; leaving the card clears it, restoring normal styling everywhere.
  const hoveredSuspectMmsi = useAppStore((st) => st.hoveredSuspectMmsi);
  const setHoveredSuspect = useAppStore((st) => st.setHoveredSuspect);
  const isHovered = hoveredSuspectMmsi === s.mmsi;
  // D37 — a 0.98 from two of seven components must not look like certainty. Prefer the
  // producer's counts; with a breakdown but no counts, count the non-null components (the same
  // fact, D37). With neither, show nothing rather than invent a breadth.
  const breadth =
    s.componentsAvailable !== null && s.componentsTotal !== null
      ? { available: s.componentsAvailable, total: s.componentsTotal }
      : s.components
        ? {
            available: Object.values(s.components).filter((v) => v !== null).length,
            total: COMPONENT_LABELS.length,
          }
        : null;
  return (
    <div
      className={`rounded border p-3 transition-colors ${
        isHovered ? "border-[#f97316]/60 bg-[#f97316]/[0.04]" : "border-line"
      }`}
      onMouseEnter={() => setHoveredSuspect(s.mmsi)}
      onMouseLeave={() => setHoveredSuspect(null)}
    >
      <div className="flex items-start justify-between gap-2">
        <div>
          <div className="t-label">
            Suspect {String(rank).padStart(2, "0")}
          </div>
          <div className="mt-0.5 flex items-center gap-1.5">
            <span className="text-[13px] font-semibold leading-tight text-ink">
              {s.name}
            </span>
            {/* docs/team/harshita-frontend.md Phase 3.7 — badge near identity, per the roadmap's own placement ask.
                Only ever rendered from a real repeat_offender record — never inferred from
                score, mmsi recurrence, or anything computed here. */}
            {s.repeatOffender && (
              <span className="inline-flex shrink-0 items-center rounded-full border border-drift/40 bg-drift/10 px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-drift">
                Repeat
              </span>
            )}
          </div>
          <div className="mt-0.5 font-mono text-[11px] text-ink-3">
            MMSI {s.mmsi}
            {s.vesselType ? ` · ${s.vesselType}` : ""}
          </div>
          {s.repeatOffender && (
            <p className="mt-1 text-[13px] leading-relaxed text-drift/70">
              Also scored in {s.repeatOffender.cases.length} other case
              {s.repeatOffender.cases.length === 1 ? "" : "s"} — best rank #
              {s.repeatOffender.bestRank}
            </p>
          )}
        </div>
        <div className="shrink-0 font-mono text-[15px] font-semibold text-drift">
          {fmt(s.score * 100, 0)}%
        </div>
      </div>
      {breadth && (
        <div className="mt-1 text-right font-mono text-[13px] text-ink-2 tabular-nums">
          scored from {breadth.available} of {breadth.total} components
        </div>
      )}

      <div className="mt-2 space-y-0.5">
        {/* D36 — closest_km is measured to the origin-grid peak, not the ring centre. */}
        <div className="relative flex items-baseline justify-between gap-3 py-[3px]">
          <span className="flex items-center gap-1 text-[13px] text-ink-2">
            Distance to origin peak
            <InfoDot tip="Measured from the highest-probability cell of the origin grid to this vessel's report there — not from the centre of the rings." />
          </span>
          <span className="font-mono text-[13px] text-ink tabular-nums">
            {fmt(s.closestKm, 1)} km
          </span>
        </div>
        {s.edgeTruncated && (
          <p className="text-[13px] leading-snug text-[#fcd34d]/75">
            Track is cut off at the search-box edge — this distance may be understated.
          </p>
        )}
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

      {/* null (no `components` on this bundle at all) → section hidden entirely, never a
          fabricated breakdown. Present-but-per-field-null is handled inside ComponentBars. */}
      {s.components && (
        <>
          <div className="relative mt-2.5 flex items-center gap-1 t-label">
            Score Breakdown
            <InfoDot
              tip={`The score is renormalised over the components that could be measured for this vessel${
                s.weightLive !== null ? ` (they carry ${fmt(s.weightLive * 100, 0)}% of the full weight)` : ""
              }. "n/a" means not measurable here, never a zero.`}
            />
          </div>
          <ComponentBars components={s.components} notes={s.componentNotes} />
        </>
      )}

      <ul className="mt-2 space-y-1">
        {s.reasons.map((r, i) => (
          <li key={i} className="flex gap-1.5 text-[13px] leading-snug text-ink-2">
            <span className="shrink-0 text-ink-4">–</span>
            <span>{r}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

/** Visually "ruled out" per docs/team/jaiveer-stage3-attribution.md — muted + strikethrough on the name. The map's vessel
 * layer conveys the same role with reduced opacity/width (see MapView.tsx); this is the card
 * half of that motif. */
function ExcludedCard({ e }: { e: ExcludedVessel }) {
  return (
    <div className="rounded border border-line bg-raised/60 p-3">
      <div className="text-[13px] font-medium text-ink-2 line-through decoration-white/25">
        {e.name ?? e.mmsi}
      </div>
      <div className="mt-0.5 font-mono text-[11px] text-ink-3">
        MMSI {e.mmsi}
        {/* `!= null` on purpose, so it catches an explicit null as well as an absent field: a
            vessel excluded for having no report inside the window has no closest approach to
            measure, and the producer says so with null. Rendering "· — km" there would show a
            missing measurement as a dash where no measurement exists. */}
        {e.closestKm != null ? ` · ${fmt(e.closestKm, 1)} km` : ""}
      </div>
      <p className="mt-1.5 text-[13px] leading-relaxed text-ink-3">{e.reason}</p>
    </div>
  );
}

// Same rose accent as the map's dark-vessel ScatterplotLayer (MapView.tsx DARK_VESSEL_COLOR) —
// the card and the marker are visibly the same thing. No MMSI row: a dark vessel has no AIS
// identity by definition (docs/team/harshita-frontend.md Phase 3.5, Master §6.7), so there is nothing to show there.
function DarkVesselCard({ v }: { v: DarkVessel }) {
  return (
    <div className="rounded border border-[#f43f5e]/25 bg-[#f43f5e]/[0.05] p-3">
      <div className="flex items-start justify-between gap-2">
        <div className="text-[13px] font-medium text-[#fda4af]">
          {v.name ?? `Radar contact ${fmt(v.lat, 3)}°, ${fmt(v.lon, 3)}°`}
        </div>
        <div className="shrink-0 text-right">
          <div className="font-mono text-[15px] font-semibold text-[#fda4af]">
            {fmt(v.score, 2)}
          </div>
          <div className="text-[10px] uppercase tracking-wider text-[#fda4af]/50">relevance</div>
        </div>
      </div>
      <div className="mt-1 space-y-0.5">
        {v.estLengthM !== null && (
          <Row label="Size (coarse)" value={`~${fmt(v.estLengthM, 0)} m`} />
        )}
        {v.angularDeviationDeg !== null && (
          <Row label="Off the slick's axis" value={`${fmt(v.angularDeviationDeg, 0)}°`} />
        )}
      </div>
      {v.reasons.length > 0 && (
        <ul className="mt-1.5 space-y-1">
          {v.reasons.map((r, i) => (
            <li key={i} className="flex gap-1.5 text-[13px] leading-snug text-[#fda4af]/70">
              <span className="shrink-0 text-[#fda4af]/40">–</span>
              <span>{r}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

// Same violet accent as the map's infrastructure ScatterplotLayer (MapView.tsx
// INFRASTRUCTURE_COLOR). No MMSI row (stationary, no AIS identity — same reasoning as
// DarkVesselCard). Wording stays neutral ("Infrastructure Finding") — proximity is not
// attribution, and any causal claim comes only from the producer's own `reasons` text,
// never from a label this component invents.
function InfrastructureCard({ f }: { f: Infrastructure }) {
  return (
    <div className="rounded border border-[#a78bfa]/25 bg-[#a78bfa]/[0.05] p-3">
      <div className="flex items-start justify-between gap-2">
        <div className="text-[13px] font-medium text-[#c4b5fd]">{f.name}</div>
        <div className="shrink-0 font-mono text-[15px] font-semibold text-[#c4b5fd]">
          {fmt(f.score * 100, 0)}%
        </div>
      </div>
      {f.reasons.length > 0 && (
        <ul className="mt-1.5 space-y-1">
          {f.reasons.map((r, i) => (
            <li key={i} className="flex gap-1.5 text-[13px] leading-snug text-[#c4b5fd]/70">
              <span className="shrink-0 text-[#c4b5fd]/40">–</span>
              <span>{r}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

/**
 * `gate` decides whether the suspect/exclusion lists render:
 *  - "loading"  — origin.json hasn't resolved yet; abstain status is unknown. Show the funnel
 *                 only, never the suspect list, even though suspects.json may already be here.
 *  - "unknown"  — origin.json failed to load. Same caution as "loading" — we cannot confirm
 *                 abstain is false, so no suspect is named.
 *  - "abstain"  — origin.abstain === true (diffuse origin) OR suspects.abstained === true
 *                 (Stage 3's deliberate refusal for any reason). docs/team/harshita-frontend.md D2: a maturity signal,
 *                 not a failure — funnel + headline + the case's abstain reason; no suspect.
 *                 Scene-level findings (natural seep, dark vessels, infrastructure) still render.
 *  - "clear"    — neither abstains, confirmed. Render suspects.json as given.
 */
function AttributeCard({
  suspects,
  gate,
  aisSource,
  shipContacts,
}: {
  suspects: SuspectsBundle;
  gate: "loading" | "unknown" | "abstain" | "clear";
  aisSource?: AisSource;
  /** Length of detections.ship_detections, or null when the ship detector was not recorded. */
  shipContacts: number | null;
}) {
  return (
    <div className="flex flex-col">
      <div>
        <div className="t-label">
          Stage 03 — Attribute
        </div>
        <div className="mt-1 t-title text-ink">
          Who was there
        </div>
        {/* Absent only when the bundle predates this field or the case has no attribution act
            yet — no guessed regime is ever shown in its place. */}
        {aisSource && (
          <div className="mt-1 text-[13px] text-ink-3">{AIS_SAMPLING_LABEL[aisSource]}</div>
        )}
      </div>

      <Divider />

      <SectionLabel>Attribution funnel</SectionLabel>
      <div className="mt-2">
        <FunnelBar funnel={suspects.funnel} />
        {/* A side count, not a fifth narrowing stage — kept out of FunnelBar's bars so it can
            never be misread as part of the in_region→scored sequence. null (field absent) ≠ 0
            (field present and zero) — see Funnel.droppedShortTrack. */}
        {suspects.funnel.droppedShortTrack !== null && (
          <p className="mt-2 text-[13px] leading-relaxed text-ink-2">
            {suspects.funnel.droppedShortTrack} dropped — fewer than{" "}
            {aisSource === "gfw_hourly" ? "2 hourly AIS positions" : "5 AIS reports"}
          </p>
        )}
      </div>

      <Divider />

      {gate === "loading" && (
        <p className="text-[13px] text-ink-3">Confirming attribution status…</p>
      )}

      {gate === "unknown" && (
        <div className="rounded border border-line bg-raised p-3 text-[13px] leading-relaxed text-ink-2">
          Origin estimate unavailable — the suspect list is withheld until abstain status can be
          confirmed.
        </div>
      )}

      {gate === "abstain" && (
        // docs/team/harshita-frontend.md D2 — style as a deliberate decision, never a failure. No red, no ✗.
        <div className="rounded border border-line bg-raised p-3">
          <div className="t-label">
            Deliberate abstention
          </div>
          <p className="mt-1.5 text-[13px] font-medium leading-relaxed text-ink-2">
            {ABSTAIN_MESSAGE}
          </p>
          {suspects.abstainReason && (
            <p className="mt-2 text-[13px] leading-relaxed text-ink-2">
              {suspects.abstainReason}
            </p>
          )}
        </div>
      )}

      {/* An abstention is a result, not a blank: show who was considered and why nobody is
          named. On an abstain, score.py lists the plausible candidates first, each with its
          measured score and the abstain reason, then the nearest vessels the funnel dropped. */}
      {gate === "abstain" && suspects.excluded.length > 0 && (
        <>
          <Divider />
          <SectionLabel>Nearest candidates — and why none is named</SectionLabel>
          <div className="mt-2 space-y-2">
            {suspects.excluded.map((e) => (
              <ExcludedCard key={e.mmsi} e={e} />
            ))}
          </div>
        </>
      )}

      {/* D19 — contextual evidence about the scene, rendered ABOVE the ranked list and never
          inside it: natural_seep is not a suspect and carries no rank/score. Shown on abstain
          too — declining to name a vessel says nothing about the scene. */}
      {(gate === "clear" || gate === "abstain") && suspects.naturalSeep?.flagged && (
        <div className={gate === "abstain" ? "mt-3" : "mb-3"}>
          <NaturalSeepNotice seep={suspects.naturalSeep} />
        </div>
      )}

      {gate === "clear" && (
        <>
          <SectionLabel>Suspects</SectionLabel>
          <div className="mt-2 space-y-2">
            {suspects.suspects.length === 0 ? (
              <p className="text-[13px] text-ink-3">No suspects scored.</p>
            ) : (
              suspects.suspects.map((s, i) => (
                <SuspectCard key={s.mmsi} s={s} rank={i + 1} />
              ))
            )}
          </div>

          <Divider />

          <SectionLabel>Excluded</SectionLabel>
          <div className="mt-2 space-y-2">
            {suspects.excluded.length === 0 ? (
              <p className="text-[13px] text-ink-3">No vessels excluded.</p>
            ) : (
              suspects.excluded.map((e) => <ExcludedCard key={e.mmsi} e={e} />)
            )}
          </div>
        </>
      )}

      {/* Dark vessels and infrastructure render on "clear" AND "abstain": a vessel abstention
          is not "no infrastructure" — the fixed-source association runs regardless (Huntington
          abstains on vessels, and its pipeline finding must stay visible). */}
      {(gate === "clear" || gate === "abstain") && (
        <>
          {/* docs/team/harshita-frontend.md Phase 3.5 — hidden entirely when empty, same convention as Score
              Breakdown: a rare/exceptional category should not clutter the panel with a
              "none" message the way Suspects/Excluded (always-expected sections) do. */}
          <Divider />
          <SectionLabel>Dark vessels — radar vs transponder</SectionLabel>
          {suspects.darkVessels.length > 0 ? (
            <div className="mt-2 space-y-2">
              {suspects.darkVessels.map((v, i) => (
                <DarkVesselCard key={i} v={v} />
              ))}
            </div>
          ) : (
            <p className="mt-2 text-[13px] leading-relaxed text-ink-2">
              {shipContacts === null
                ? "No radar-contact list was recorded for this scene, so darkness was not assessed."
                : shipContacts === 0
                  ? "UDGAM's ship detector found no radar contact on this scene, and no listed radar contact is unexplained by AIS."
                  : `UDGAM's ship detector found ${shipContacts} radar contact${
                      shipContacts === 1 ? "" : "s"
                    } on this scene. None is both unexplained by AIS at acquisition time and near the slick or origin.`}
            </p>
          )}

          {/* docs/team/harshita-frontend.md Phase 3.6 — same hidden-when-empty convention as Dark Vessels/Score
              Breakdown. Order (Suspects → Excluded → Dark Vessels → Infrastructure) matches
              docs/team/harshita-frontend.md Screen 3 exactly. */}
          {suspects.infrastructure.length > 0 && (
            <>
              <Divider />
              <SectionLabel>Infrastructure</SectionLabel>
              <div className="mt-2 space-y-2">
                {suspects.infrastructure.map((f, i) => (
                  <InfrastructureCard key={i} f={f} />
                ))}
              </div>
            </>
          )}
        </>
      )}
    </div>
  );
}

// ─── Guided flow: before a stage has been run ────────────────────────────────

/** The "Scene" step: the raw radar image, before the detector has been run on it. Everything
 *  here is scene metadata the export recorded — nothing about what the detector found. */
function SceneCard({ meta, bounds }: { meta: CaseMeta; bounds: Bounds | null }) {
  const midLat = bounds ? (bounds.south + bounds.north) / 2 : 0;
  const widthKm = bounds
    ? (bounds.east - bounds.west) * 111.32 * Math.cos((midLat * Math.PI) / 180)
    : null;
  const heightKm = bounds ? (bounds.north - bounds.south) * 111.32 : null;
  const benchmark = meta.provenance === "benchmark";
  return (
    <div className="flex flex-col">
      <div className="t-label">
        The scene
      </div>
      <div className="mt-1 t-title text-ink">
        {meta.title}
      </div>
      {meta.short_location && (
        <div className="mt-0.5 text-[13px] text-ink-2">{meta.short_location}</div>
      )}
      <Divider />
      <SectionLabel>What you are looking at</SectionLabel>
      <p className="mt-2 text-[13px] leading-relaxed text-ink-2">
        A synthetic-aperture radar image. The satellite sends microwaves down and measures what
        bounces back. Wind-roughened sea scatters it back and looks bright; oil smooths the
        surface, so a slick looks <span className="font-semibold text-ink">dark</span>.
      </p>
      <p className="mt-2 text-[13px] leading-relaxed text-ink-2">
        Calm water, rain cells and algae look dark too. Telling them apart is the detector&apos;s
        job.
      </p>
      <Divider />
      <SectionLabel>Acquisition</SectionLabel>
      <div className="mt-2 space-y-0.5">
        <Row label="Satellite" value={meta.satellite} />
        {!benchmark && (
          <Row
            label="Time (UTC)"
            value={`${fmtDay(meta.detection_time)} ${fmtTime(meta.detection_time)}`}
          />
        )}
        {bounds && <Row label="Polarisation" value={bounds.vh_available ? "VV + VH" : "VV"} />}
        {widthKm !== null && heightKm !== null && (
          <Row label="Footprint" value={`${fmt(widthKm, 1)} × ${fmt(heightKm, 1)} km`} />
        )}
        {bounds && bounds.db_min !== undefined && bounds.db_max !== undefined && (
          <Row
            label="Display stretch"
            value={`${fmt(bounds.db_min, 0)} to ${fmt(bounds.db_max, 0)} dB`}
          />
        )}
      </div>
      {!benchmark && (
        <p className="mt-2 break-all font-mono text-[11px] leading-snug text-ink-3">
          {meta.scene_id}
        </p>
      )}
    </div>
  );
}

const STAGE_HEADER: Record<"trace" | "attribute", { n: string; title: string; body: string }> = {
  trace: {
    n: "02",
    title: "Backward drift",
    body:
      "The slick has been moving since it was spilled, carried by surface currents plus about 3% " +
      "of the wind. Running that physics backwards, 50 times with perturbed inputs, shows where " +
      "the oil most likely entered the water and how unsure we are.",
  },
  attribute: {
    n: "03",
    title: "Attribution",
    body:
      "Every AIS-broadcasting vessel near the reconstructed origin is scored on evidence: was it " +
      "inside the origin cloud during the release window, how did it move, did its transponder " +
      "go silent. Radar contacts with no AIS broadcast are cross-checked separately.",
  },
};

function PendingStageCard({ stage, running }: { stage: "trace" | "attribute"; running: boolean }) {
  const h = STAGE_HEADER[stage];
  return (
    <div className="flex flex-col">
      <div className="t-label">
        Stage {h.n}
      </div>
      <div className="mt-1 t-title text-ink">
        {h.title}
      </div>
      <Divider />
      <p className="text-[13px] leading-relaxed text-ink-2">{h.body}</p>
      <p className="mt-3 text-[13px] font-medium text-[#fb923c]">
        {running ? "Running…" : "Not run yet — press the button at the bottom right."}
      </p>
    </div>
  );
}

// ─── Main panel ───────────────────────────────────────────────────────────────

export default function ContextPanel() {
  const activeStage = useAppStore((s) => s.activeStage);
  const meta = useAppStore((s) => s.meta);
  const detections = useAppStore((s) => s.detections);
  const detectionsPending = useAppStore((s) => s.detectionsPending);
  const selectedDetectionId = useAppStore((s) => s.selectedDetectionId);
  const origin = useAppStore((s) => s.origin);
  const originStatus = useAppStore((s) => s.originStatus);
  const originError = useAppStore((s) => s.originError);
  const suspects = useAppStore((s) => s.suspects);
  const suspectsStatus = useAppStore((s) => s.suspectsStatus);
  const suspectsError = useAppStore((s) => s.suspectsError);
  const bounds = useAppStore((s) => s.bounds);
  const revealed = useAppStore((s) => s.revealed);
  const running = useAppStore((s) => s.running);

  const oilCount =
    detections?.features.filter((f) => f.properties.classification === "oil")
      .length ?? 0;
  const lookalikeCount =
    detections?.features.filter(
      (f) => f.properties.classification === "lookalike",
    ).length ?? 0;
  const selected = detections?.features.find(
    (f) => f.properties.id === selectedDetectionId,
  );

  return (
    <aside className="flex w-[22rem] shrink-0 flex-col overflow-y-auto border-l border-line bg-hull px-6 py-6">
      {activeStage === "detect" && !revealed.detect && meta && (
        <SceneCard meta={meta} bounds={bounds} />
      )}
      {activeStage === "trace" && !revealed.trace && (
        <PendingStageCard stage="trace" running={running === "trace"} />
      )}
      {activeStage === "attribute" && !revealed.attribute && (
        <PendingStageCard stage="attribute" running={running === "attribute"} />
      )}

      {activeStage === "detect" && revealed.detect &&
        (detectionsPending ? (
          // Stage 1 genuinely hasn't run for this case yet (loadCase.ts: a 404 on
          // detections.geojson degrades to `detections: null` + `detectionsPending: true`,
          // never a crash). `null` here means "not measured", never "measured as zero" — the
          // D1 zero-oil branch below must not fire for this case, or it would claim a
          // completed detection pass that never happened (the honesty rule, Master §5.7).
          <div className="rounded border border-line bg-raised p-3">
            <div className="t-label">
              Stage 01 — Detect
            </div>
            <div className="mt-1 text-[13px] font-semibold leading-tight text-ink">
              Detection stage pending
            </div>
            <p className="mt-1.5 text-[13px] leading-relaxed text-ink-2">
              The scene is loaded, the detector hasn&apos;t run.
            </p>
          </div>
        ) : oilCount === 0 ? (
          // D1 — a designed result, not an error (docs/team/harshita-frontend.md Part D). Guide the judge to the
          // rejected look-alikes; their DetectionCard carries the "why not oil" evidence.
          <>
            <ReRunButton />
            <div className="mb-4 rounded border border-line bg-raised p-3">
              <div className="t-label">
                Stage 01 — Detect
              </div>
              <div className="mt-1 text-[13px] font-semibold leading-tight text-ink">
                No oil in this scene
              </div>
              <p className="mt-1.5 text-[13px] leading-relaxed text-ink-2">
                {lookalikeCount === 0
                  ? "The scene is clear — no dark features to assess."
                  : `We checked ${lookalikeCount} dark patch${
                      lookalikeCount === 1 ? "" : "es"
                    } — none match oil. Click a grey patch on the map to see why it was rejected.`}
              </p>
            </div>
            {selected && <DetectionCard p={selected.properties} />}
          </>
        ) : (
          <>
            <ReRunButton />
            {/* Screen-1 oil-detection headline (docs/team/harshita-frontend.md Screen 1).
                Shown only when oilCount > 0 — D1 (oilCount === 0) has its own messaging above. */}
            <div className="mb-4">
              <p className="text-[13px] font-semibold leading-snug text-ink">
                We found{" "}
                {(oilCount + lookalikeCount) === 1
                  ? "1 dark patch"
                  : `${oilCount + lookalikeCount} dark patches`}
                .{" "}
                <span style={{ color: OIL_COLOR }}>
                  {oilCount === 1 ? "1 is oil" : `${oilCount} are oil`}.
                </span>
              </p>
            </div>
            {selected ? (
              <DetectionCard p={selected.properties} />
            ) : (
              <p className="text-[13px] text-ink-3">
                Select a detection on the map.
              </p>
            )}
          </>
        ))}


      {/* ── Trace ── */}
      {activeStage === "trace" && revealed.trace &&
        (originStatus === "error" ? (
          <div className="rounded border border-alert/30 bg-alert/[0.07] p-3">
            <div className="text-[13px] font-semibold text-alert">
              Origin bundle failed to load
            </div>
            <p className="mt-1 whitespace-pre-wrap text-[13px] text-ink-2">
              {originError}
            </p>
            <p className="mt-2 text-[13px] text-ink-3">
              This is a contract bug — tell Akshat. The frontend does not patch
              bundle data.
            </p>
          </div>
        ) : origin ? (
          <TraceCard origin={origin} />
        ) : (
          <p className="text-[13px] text-ink-3">Loading origin estimate…</p>
        ))}

      {/* ── Attribute ── */}
      {activeStage === "attribute" && revealed.attribute &&
        (suspectsStatus === "error" ? (
          <div className="rounded border border-alert/30 bg-alert/[0.07] p-3">
            <div className="text-[13px] font-semibold text-alert">
              Suspects bundle failed to load
            </div>
            <p className="mt-1 whitespace-pre-wrap text-[13px] text-ink-2">
              {suspectsError}
            </p>
            <p className="mt-2 text-[13px] text-ink-3">
              This is a contract bug — tell Akshat. The frontend does not patch
              bundle data.
            </p>
          </div>
        ) : suspects ? (
          <AttributeCard
            suspects={suspects}
            aisSource={meta?.ais_source}
            shipContacts={detections?.ship_detections?.length ?? null}
            gate={
              origin === null
                ? originStatus === "error"
                  ? "unknown"
                  : "loading"
                : origin.abstain || suspects.abstained
                  ? "abstain"
                  : "clear"
            }
          />
        ) : (
          <p className="text-[13px] text-ink-3">Loading attribution…</p>
        ))}

      {/* Verify has its own full-screen view (VerifyScreen), rendered by CaseWorkspace in
          place of the map + this panel — nothing for the ContextPanel to show on that stage. */}
    </aside>
  );
}
