"use client";

// Redesigned Stage 02 — Trace panel. Was a flat Divider-separated stack (docs/updates/harshita.md
// Phase 5.3); now two bordered capsules — Origin (hero: centroid + 50/90% radii as pill chips)
// and Timing (release window + age, grouped because age is derived from time-since-release) —
// plus a GSAP entrance stagger, count-up numbers, and a one-shot "origin is now knowable" glow
// timed to the exact rewind position MapView.tsx's origin cloud reaches full opacity. Extracted
// out of ContextPanel.tsx so this file can own its own GSAP wiring without touching the other
// stage cards. No raw hex/px — every size/colour below resolves to an existing globals.css token.

import { useRef } from "react";
import { useAppStore } from "@/lib/store";
import { tFromNorm } from "@/lib/timestep";
import {
  ORIGIN_FADE_IN_FULL,
  originRewindFraction,
  type AgeMethod,
  type OriginBundle,
} from "@/lib/origin";
import { fmt, fmtLat, fmtLon, fmtDay, fmtTime } from "@/lib/format";
import { Divider, SectionLabel } from "@/components/PanelAtoms";
import InfoDot from "@/components/InfoDot";
import AnimatedNumber from "./AnimatedNumber";
import AgeDisclosure from "./AgeDisclosure";
import { gsap, useGSAP, prefersReducedMotion } from "@/lib/gsap";

// docs/team/harshita-frontend.md Phase 5.3 — age_method plain-language labels (Master §6.5, C4).
// "none" and "disagreement" are genuine estimator outcomes, not errors — worded as such.
const AGE_METHOD_LABEL: Record<AgeMethod, string> = {
  shear: "Estimated from current shear",
  fay: "Estimated from spreading rate",
  elongation: "Estimated from slick elongation",
  track: "Estimated from how far a ship's track has widened",
  combined: "Combined estimate",
  disagreement: "Estimators disagree — range widened",
  none: "No estimator produced a result — using the search bracket",
};

/** One 50%/90% radius chip in the Origin capsule. */
function RadiusChip({ label, km, tip }: { label: string; km: number; tip: string }) {
  return (
    <span className="relative inline-flex items-center gap-1.5 rounded-full border border-line-strong px-2.5 py-1 text-[11px] leading-none">
      <span className="text-ink-3">{label}</span>
      <span className="font-mono tabular-nums text-ink">
        <AnimatedNumber value={km} digits={1} format={fmt} />
        {" km"}
      </span>
      <InfoDot tip={tip} />
    </span>
  );
}

export default function TraceCard({ origin }: { origin: OriginBundle }) {
  const [start, end] = origin.timeWindow;

  const tNorm = useAppStore((s) => s.tNorm);
  const nSteps = useAppStore((s) => s.particles?.nSteps ?? 0);
  const traceEntranceKey = useAppStore((s) => s.traceEntranceKey);

  const rewind = originRewindFraction(tFromNorm(tNorm, nSteps), nSteps);
  const originKnowable = rewind >= ORIGIN_FADE_IN_FULL;

  const cardRef = useRef<HTMLDivElement>(null);
  const headerRef = useRef<HTMLDivElement>(null);
  const originCapsuleRef = useRef<HTMLDivElement>(null);
  const timingCapsuleRef = useRef<HTMLDivElement>(null);
  const footnoteRef = useRef<HTMLParagraphElement>(null);

  // Entrance stagger, re-fired each time Trace is (re-)entered for a case (traceEntranceKey,
  // bumped by store.ts's initTrace() — shared with TimeSlider.tsx / MapView.tsx so all three
  // animate off the same moment instead of drifting independently-timed mount effects).
  useGSAP(
    () => {
      const els = [
        headerRef.current,
        originCapsuleRef.current,
        timingCapsuleRef.current,
        footnoteRef.current,
      ].filter(Boolean) as HTMLElement[];
      if (els.length === 0) return;
      if (prefersReducedMotion()) {
        gsap.set(els, { opacity: 1, y: 0 });
        return;
      }
      gsap.set(els, { clearProps: "all" });
      gsap.from(els, { opacity: 0, y: 10, duration: 0.45, stagger: 0.07, ease: "power2.out" });
    },
    { dependencies: [traceEntranceKey], scope: cardRef },
  );

  // "The origin is now knowable" — one-shot glow on the Origin capsule the moment the rewind
  // crosses the same threshold at which MapView.tsx's origin cloud reaches full opacity.
  const pulsedAt = useRef<number | null>(null);
  useGSAP(() => {
    const el = originCapsuleRef.current;
    if (!el) return;
    if (!originKnowable) {
      pulsedAt.current = null;
      return;
    }
    if (pulsedAt.current === traceEntranceKey || prefersReducedMotion()) return;
    pulsedAt.current = traceEntranceKey;
    // rgba(var(--drift-rgb), α) — the box-shadow spread needs an alpha channel that the plain
    // `--drift` token (already fully opaque) can't give it, so this reads the channel form
    // directly rather than introducing a new literal colour (same pattern globals.css itself
    // uses for `--drift-dim`).
    gsap.fromTo(
      el,
      { boxShadow: "0 0 0 0 rgba(var(--drift-rgb), 0)" },
      {
        boxShadow: "0 0 0 1px var(--drift), 0 0 24px rgba(var(--drift-rgb), 0.35)",
        duration: 0.5,
        ease: "power2.out",
        yoyo: true,
        repeat: 1,
      },
    );
  }, { dependencies: [originKnowable, traceEntranceKey] });

  return (
    <div ref={cardRef} className="flex flex-col">
      {/* ── Header ── */}
      <div ref={headerRef}>
        <div className="t-label">Stage 02 — Trace</div>
        <div className="mt-1 t-title text-ink">Where the oil came from</div>
        <div className="mt-0.5 font-mono text-[11px] text-ink-3">
          {origin.ensembleRuns} simulations
        </div>
      </div>

      {/* ── Origin capsule (hero) ── */}
      <div ref={originCapsuleRef} className="mt-4 rounded border border-line bg-raised p-3">
        <SectionLabel>Origin</SectionLabel>
        {/* `relative` — see InfoDot.tsx: the tooltip anchors to this row, not the button. */}
        <div className="relative mt-1.5 flex items-start gap-1">
          <div className="flex-1">
            <div className="t-title font-mono leading-snug text-ink tabular-nums">
              {fmtLat(origin.centroid[1], 5)}
            </div>
            <div className="t-title font-mono leading-snug text-ink tabular-nums">
              {fmtLon(origin.centroid[0], 5)}
            </div>
          </div>
          <InfoDot
            align="right"
            tip="The centroid of the origin probability field — where the ensemble of backwards-drift runs most agree the oil entered the water."
          />
        </div>
        <div className="mt-3 flex flex-wrap items-center gap-2">
          <RadiusChip
            label="50%"
            km={origin.radius50Km}
            tip="Radius of the circle that contains half of the 50 backwards-drift simulations. Smaller means the origin is more certain."
          />
          <RadiusChip
            label="90%"
            km={origin.radius90Km}
            tip="Radius of the circle that contains nine out of ten simulations. It measures how closely the runs agree with each other (precision), not how close they are to the true release point."
          />
        </div>
      </div>

      {/* ── Timing capsule: release window + age (age is derived from time-since-release, so
          they're grouped) + the confidence/abstain banner as its closing element ── */}
      <div ref={timingCapsuleRef} className="mt-3 rounded border border-line bg-raised p-3">
        <SectionLabel>Released between</SectionLabel>
        <div className="relative mt-1.5 flex items-start gap-1">
          <div className="flex-1">
            <div className="font-mono text-[15px] font-semibold text-ink">{fmtDay(start)}</div>
            <div className="font-mono text-[13px] text-ink-2">
              {fmtTime(start)} – {fmtTime(end)} UTC
            </div>
          </div>
          <InfoDot
            align="right"
            tip="The time window during which the oil most plausibly entered the water, derived from backwards-drift timing across all simulations."
          />
        </div>

        {/* D12 — the method line says whether this window is a search bracket or a measured
            estimate. No always-on caption: it contradicted "Measured estimate". */}
        {origin.timeWindowMethod === "bounded" && (
          <p className="mt-2 text-[13px] leading-relaxed text-ink-2">
            Search bracket (not a measured release time)
          </p>
        )}
        {origin.timeWindowMethod === "convergence" && (
          <p className="mt-2 text-[13px] leading-relaxed text-ink-2">Measured estimate</p>
        )}
        {origin.timeWindowMethod === "age" && (
          <p className="mt-2 text-[13px] leading-relaxed text-ink-2">
            Measured from the slick&apos;s estimated age (80% interval)
          </p>
        )}

        {/* ageHours and ageMethod are independently optional (no invented pairing rule): each
            row renders only when its own field is present, and the whole block hides when both
            are absent. */}
        {(origin.ageHours || origin.ageMethod) && (
          <>
            <Divider />
            <SectionLabel>Estimated age</SectionLabel>
            <div className="relative mt-1.5 flex items-start gap-1">
              <div className="flex-1">
                {origin.ageHours && (
                  <div className="font-mono text-[15px] font-semibold text-ink tabular-nums">
                    <AnimatedNumber value={origin.ageHours[0]} digits={0} format={fmt} />
                    {" – "}
                    <AnimatedNumber value={origin.ageHours[1]} digits={0} format={fmt} />
                    {" hours"}
                  </div>
                )}
                {origin.ageMethod && (
                  <div className="mt-0.5 text-[13px] text-ink-2">{AGE_METHOD_LABEL[origin.ageMethod]}</div>
                )}
              </div>
              <InfoDot
                align="right"
                tip="How long ago the oil likely entered the water, estimated from how the slick has spread and sheared since release."
              />
            </div>
            {origin.ageEstimators && Object.keys(origin.ageEstimators).length > 0 && (
              <AgeDisclosure estimators={origin.ageEstimators} />
            )}
          </>
        )}

        {/* Origin-confidence state. The two branches are genuinely distinct:
            abstain === true  → the origin cloud is too diffuse to attribute from,
                                and Stage 3 names no suspects (docs/CONTRACTS.md §6);
            abstain === false → the origin is tight enough for attribution to run.
            bg-overlay (not bg-raised — the capsule already carries that) keeps this readable as
            a distinct closing note rather than an invisible nested box of the same tone. */}
        {origin.abstain ? (
          <div className="mt-3 rounded border border-line bg-overlay/60 px-2.5 py-1.5 text-[13px] leading-relaxed text-ink-2">
            Origin cloud too diffuse — no suspects can be named.
          </div>
        ) : (
          <div className="mt-3 border-t border-line pt-2 text-[10px] uppercase tracking-wide text-ink-3">
            Origin within attribution confidence
          </div>
        )}
      </div>

      {/* The drifting points are ONE control trajectory (particles.json); the uncertainty
          lives in the origin field and the 50 / 90 % regions above. */}
      <p ref={footnoteRef} className="mt-3 text-[12px] leading-relaxed text-ink-3">
        The drifting points trace one representative path, not a spread. The uncertainty is the
        origin probability field and the 50 / 90 % regions above, stacked from{" "}
        {origin.ensembleRuns} perturbed runs.
      </p>
    </div>
  );
}
