"use client";

// The single navigation surface for a case. It replaces three controls that all said the same
// thing — the header breadcrumb, the six-dot progress strip, and the vertical stage rail — so
// the judge's position in the flow is stated once, and the whole left edge goes back to the map.
//
// Behaviour is the union of what those three allowed, with the guided order kept; the rules
// themselves live in lib/flow.ts (`stepTarget`) so they stay pure and testable:
//   · a step already on screen      → plain navigation, nothing re-runs
//   · the one step not yet run      → navigate AND run it, exactly like the primary action
//   · an act this case does not have→ inert, with the reason as its tooltip (D1/D3)
//
// Numbering is used because this genuinely is a sequence: you cannot trace a slick you have not
// detected, or attribute an origin you have not traced.

import { useRouter } from "next/navigation";
import { useAppStore } from "@/lib/store";
import type { Act } from "@/lib/contracts";
import { adjacentStage, flowSteps, stepTarget } from "@/lib/flow";
import { isNoSpill } from "@/lib/detections";
import { formatAcquisitionDate } from "@/lib/cases";

export default function StageSpine({ stage }: { stage: Act }) {
  const router = useRouter();
  const meta = useAppStore((s) => s.meta);
  const activeCaseId = useAppStore((s) => s.activeCaseId);
  const resetToGallery = useAppStore((s) => s.resetToGallery);
  const revealed = useAppStore((s) => s.revealed);
  const running = useAppStore((s) => s.running);
  const runStage = useAppStore((s) => s.runStage);
  const noSpill = isNoSpill(useAppStore((s) => s.detections));

  const acts = meta?.acts_available;
  const steps = flowSteps(acts, { noSpill });
  // The Detect screen before its Run button is the "Scene" step, not Detect itself.
  const currentKey = stage === "detect" && !revealed.detect ? "scene" : stage;
  const currentIndex = steps.findIndex((s) => s.key === currentKey);

  // Every path back to the gallery goes through the same clean-state reset as the idle timer
  // (docs/team/harshita-frontend.md C8); going forward through a stage never does.
  const toGallery = () => {
    resetToGallery();
    router.push("/");
  };

  const prev = adjacentStage(stage, acts, -1);
  const goBack = () =>
    prev ? router.push(`/case/${activeCaseId}/${prev}`) : toGallery();

  return (
    <header className="shrink-0 border-b border-line bg-deep">
      <div className="flex h-14 min-w-0 items-center gap-4 px-4">
        {/* ── Identity ── */}
        <div className="flex min-w-0 shrink items-center gap-3">
          <button
            type="button"
            onClick={goBack}
            title={prev ? `Back to ${prev}` : "Back to the case library"}
            className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full text-ink-3 transition-colors hover:bg-white/[0.06] hover:text-ink"
          >
            <span aria-hidden className="text-[15px] leading-none">‹</span>
            <span className="sr-only">Back</span>
          </button>
          <span className="shrink-0 text-[13px] font-semibold tracking-[0.14em] text-ink">
            UDGAM
          </span>
          {meta && (
            <span className="truncate t-small text-ink-2" title={meta.title}>
              {meta.title}
            </span>
          )}
        </div>

        {/* ── The sequence ── */}
        <ol className="flex min-w-0 flex-1 items-center justify-center gap-0">
          {steps.map((step, i) => {
            const isCurrent = i === currentIndex;
            const done = currentIndex >= 0 && i < currentIndex && step.available;
            const target =
              step.key === "pick"
                ? ({ kind: "navigate" } as const)
                : step.key === "scene"
                  ? // "Scene" is the Detect screen before its Run button — never a destination
                    // of its own, and nothing to go back to once detections are on the map.
                    ({ kind: "inert", reason: "the scene as the detector received it" } as const)
                  : stepTarget(step.key as Act, stage, acts, revealed, { noSpill });

            const go =
              isCurrent || running !== null
                ? null
                : step.key === "pick"
                  ? toGallery
                  : target.kind === "navigate"
                    ? () => router.push(`/case/${activeCaseId}/${step.key}`)
                    : target.kind === "run"
                      ? () => {
                          const next = step.key as Act;
                          router.push(`/case/${activeCaseId}/${next}`);
                          runStage(next);
                        }
                      : null;

            const locked = target.kind === "inert";
            const title = isCurrent
              ? step.label
              : locked
                ? `${step.label} — ${target.reason}`
                : target.kind === "run"
                  ? `${step.label} — run this step`
                  : `Go to ${step.label}`;

            const tone = isCurrent
              ? "text-ink"
              : locked
                ? "text-ink-4"
                : done
                  ? "text-ink-2"
                  : "text-ink-3";

            return (
              <li key={step.key} className="flex min-w-0 items-center">
                {i > 0 && (
                  // The connector is the progress bar: it is lit behind the judge and faint
                  // ahead of them, so how far through the case they are needs no counting.
                  <span
                    aria-hidden
                    className={`mx-1.5 h-px w-3 shrink transition-colors duration-500 xl:w-7 ${
                      i <= currentIndex ? "bg-drift/55" : "bg-line-strong"
                    }`}
                  />
                )}
                <button
                  type="button"
                  onClick={go ?? undefined}
                  disabled={!go}
                  title={title}
                  aria-current={isCurrent ? "step" : undefined}
                  className={`flex items-center gap-2 rounded-full py-1 pl-1 pr-2.5 transition-colors duration-200 ${tone} ${
                    go ? "hover:bg-white/[0.05] hover:text-ink" : "cursor-default"
                  }`}
                >
                  <span className="relative flex h-[18px] w-[18px] shrink-0 items-center justify-center">
                    {isCurrent && (
                      <span
                        aria-hidden
                        className="anim-ping absolute inset-0 rounded-full bg-drift/45"
                      />
                    )}
                    <span
                      className={`relative flex h-[18px] w-[18px] items-center justify-center rounded-full font-mono text-[10px] leading-none ${
                        isCurrent
                          ? "bg-drift text-abyss"
                          : done
                            ? "bg-drift/20 text-drift ring-1 ring-inset ring-drift/40"
                            : locked
                              ? "text-ink-4 ring-1 ring-inset ring-line"
                              : "text-ink-3 ring-1 ring-inset ring-line-strong"
                      }`}
                    >
                      {i + 1}
                    </span>
                  </span>
                  {/* Labels are the first thing to go when the row is tight; the numbered
                      markers and the lit connector still carry the position. */}
                  <span className="hidden whitespace-nowrap text-[13px] font-medium xl:inline">
                    {step.label}
                  </span>
                </button>
              </li>
            );
          })}
        </ol>

        {/* ── Provenance ── */}
        <div className="flex shrink-0 items-center gap-4">
          {meta && (
            <span className="hidden text-right font-mono text-[11px] leading-tight text-ink-3 xl:block">
              {meta.satellite}
              <br />
              {formatAcquisitionDate(meta.detection_time) ?? "—"}
            </span>
          )}
          <button
            type="button"
            onClick={toGallery}
            className="rounded-full px-3 py-1.5 text-[13px] font-medium text-ink-3 transition-colors hover:bg-white/[0.06] hover:text-ink"
          >
            Start over
          </button>
        </div>
      </div>
    </header>
  );
}
