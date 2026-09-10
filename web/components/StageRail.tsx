"use client";

import { useRouter } from "next/navigation";
import { useAppStore } from "@/lib/store";
import { ALL_ACTS, type Act } from "@/lib/contracts";
import { stageUnavailableReason } from "@/lib/flow";
import { isNoSpill } from "@/lib/detections";

const STAGE_NUMBERS: Record<Act, string> = {
  detect: "01",
  trace: "02",
  attribute: "03",
  verify: "04",
};

const STAGE_LABELS: Record<Act, string> = {
  detect: "DETECT",
  trace: "TRACE",
  attribute: "ATTRIBUTE",
  verify: "VERIFY",
};

export default function StageRail() {
  const router = useRouter();
  const meta = useAppStore((s) => s.meta);
  const activeStage = useAppStore((s) => s.activeStage);
  const activeCaseId = useAppStore((s) => s.activeCaseId);
  const setStage = useAppStore((s) => s.setStage);
  // docs/04 D1 — a no-spill scene greys Trace/Attribute with a specific "nothing to trace"
  // reason; every other case keeps the default STAGE_UNAVAILABLE_REASON string.
  const noSpill = isNoSpill(useAppStore((s) => s.detections));

  return (
    <nav className="flex w-[52px] shrink-0 flex-col gap-px border-r border-white/[0.08] bg-[#0b0f14] pt-3 pb-2">
      {ALL_ACTS.map((act) => {
        const available = meta?.acts_available.includes(act) ?? false;
        const active = activeStage === act;

        return (
          <button
            key={act}
            type="button"
            disabled={!available}
            onClick={() => {
              if (!available) return;
              setStage(act);
              router.push(`/case/${activeCaseId}/${act}`);
            }}
            title={
              available
                ? STAGE_LABELS[act]
                : `${STAGE_LABELS[act]} — ${stageUnavailableReason(act, { noSpill })}`
            }
            className={`
              relative flex flex-col items-center gap-1.5 py-4 text-center
              transition-colors duration-150
              ${
                active
                  ? "text-white"
                  : available
                    ? "text-white/35 hover:text-white/65"
                    : "cursor-not-allowed text-white/15"
              }
            `}
          >
            {/* Left active accent bar */}
            {active && (
              <span
                className="absolute left-0 top-3 bottom-3 w-[2px] rounded-r-full bg-[#f97316]"
                aria-hidden
              />
            )}

            {/* Stage number */}
            <span
              className={`font-mono text-[9px] leading-none tracking-widest ${
                active ? "text-[#f97316]" : "opacity-60"
              }`}
            >
              {STAGE_NUMBERS[act]}
            </span>

            {/* Stage label — rotated */}
            <span
              className="block text-[9px] font-semibold uppercase leading-none tracking-[0.12em]"
              style={{ writingMode: "vertical-rl", transform: "rotate(180deg)" }}
            >
              {STAGE_LABELS[act]}
            </span>
          </button>
        );
      })}
    </nav>
  );
}
