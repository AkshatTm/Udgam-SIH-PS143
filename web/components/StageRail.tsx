"use client";

import { useAppStore } from "@/lib/store";
import { ALL_ACTS, ACT_LABELS, type Act } from "@/lib/contracts";

const ICONS: Record<Act, string> = {
  detect: "◎",
  trace: "↺",
  attribute: "⚓",
};

const UNAVAILABLE_HINT = "no free AIS for Indian waters";

export default function StageRail() {
  const meta = useAppStore((s) => s.meta);
  const activeStage = useAppStore((s) => s.activeStage);
  const setStage = useAppStore((s) => s.setStage);

  return (
    <nav className="flex w-20 flex-col gap-1 border-r border-white/10 bg-[#0b0f14] p-2">
      {ALL_ACTS.map((act) => {
        const available = meta?.acts_available.includes(act) ?? false;
        const active = activeStage === act;
        return (
          <button
            key={act}
            type="button"
            disabled={!available}
            onClick={() => setStage(act)}
            title={available ? ACT_LABELS[act] : `${ACT_LABELS[act]} — ${UNAVAILABLE_HINT}`}
            className={`flex flex-col items-center gap-1 rounded-md py-3 text-[11px] transition-colors ${
              active
                ? "bg-white/15 text-white"
                : available
                  ? "text-white/60 hover:bg-white/5 hover:text-white"
                  : "cursor-not-allowed text-white/20"
            }`}
          >
            <span className="text-lg leading-none">{ICONS[act]}</span>
            {ACT_LABELS[act]}
          </button>
        );
      })}
    </nav>
  );
}
