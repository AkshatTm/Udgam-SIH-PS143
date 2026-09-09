"use client";

// The strip under the header: back navigation (left), the five-step progress indicator
// (centre, docs/04 C3), and "Start over" (right, C8). Always visible while in a case.

import { useRouter } from "next/navigation";
import { useAppStore } from "@/lib/store";
import type { Act } from "@/lib/contracts";
import { adjacentStage, flowSteps } from "@/lib/flow";

export default function FlowBar({ stage }: { stage: Act }) {
  const router = useRouter();
  const meta = useAppStore((s) => s.meta);
  const activeCaseId = useAppStore((s) => s.activeCaseId);
  const acts = meta?.acts_available;

  const prev = adjacentStage(stage, acts, -1);
  const steps = flowSteps(acts);

  const goBack = () =>
    prev ? router.push(`/case/${activeCaseId}/${prev}`) : router.push("/");

  return (
    <div className="flex h-8 shrink-0 items-center justify-between gap-4 border-b border-white/[0.06] bg-[#0b0f14] px-4">
      <button
        type="button"
        onClick={goBack}
        className="flex shrink-0 items-center gap-1 text-[10px] font-medium text-white/40 transition-colors hover:text-white/75"
      >
        <span aria-hidden>‹</span>
        {prev ? "Back" : "Cases"}
      </button>

      <ol className="flex min-w-0 items-center gap-2 overflow-hidden">
        {steps.map((step, i) => {
          const isCurrent = step.key === stage;
          const dim = !step.available && step.key !== "pick";
          return (
            <li key={step.key} className="flex shrink-0 items-center gap-2">
              {i > 0 && <span className="text-white/10">·</span>}
              <span
                title={dim ? `${step.label} — ${step.reason}` : step.label}
                className={`flex items-center gap-1.5 text-[9px] font-semibold uppercase tracking-[0.12em] ${
                  isCurrent
                    ? "text-white"
                    : dim
                      ? "text-white/15"
                      : "text-white/40"
                }`}
              >
                <span
                  aria-hidden
                  className={`h-1.5 w-1.5 rounded-full ${
                    isCurrent
                      ? "bg-[#f97316]"
                      : dim
                        ? "bg-white/10"
                        : "bg-white/25"
                  }`}
                />
                {step.label}
              </span>
            </li>
          );
        })}
      </ol>

      <button
        type="button"
        onClick={() => router.push("/")}
        className="shrink-0 text-[10px] font-medium text-white/40 transition-colors hover:text-white/75"
      >
        Start over
      </button>
    </div>
  );
}
