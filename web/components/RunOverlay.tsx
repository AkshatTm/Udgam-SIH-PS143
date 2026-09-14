"use client";

// Guided-flow chrome over the map: what the judge is looking at before a stage is run, the
// "running" card while its Run animation plays, and a standing caption that the results are a
// replay of the offline pipeline run (Master §1.5 — precomputation is fine and we say so;
// fabricated results are not). The scan-line sweep itself is drawn by MapView.

import { useEffect, useState } from "react";
import { useAppStore, RUN_DURATION_MS } from "@/lib/store";
import { RUN_LABEL, RUNNING_LABEL } from "@/lib/flow";
import type { Act } from "@/lib/contracts";

// Each stage opens with the question it is about to answer, in the words a judge would use.
const WAITING: Record<Act, { question: string; body: string }> = {
  detect: {
    question: "Is any of this oil?",
    body: "This is the raw Sentinel-1 radar image. Oil flattens the sea surface, so a slick shows as a dark streak — but so do calm water, rain and algae.",
  },
  trace: {
    question: "Where did it start?",
    body: "The slick was seen at one moment. Run the currents and wind backwards to find where the oil entered the water, and when.",
  },
  attribute: {
    question: "Who was there?",
    body: "Which ships were at that origin when the oil entered the water — and which radar contacts carried no transponder at all?",
  },
  verify: { question: "", body: "" },
};

export default function RunOverlay({ stage }: { stage: Act }) {
  const running = useAppStore((s) => s.running);
  const revealed = useAppStore((s) => s.revealed[stage]);
  const [progress, setProgress] = useState(0);

  useEffect(() => {
    if (running !== stage) {
      setProgress(0);
      return;
    }
    const start = performance.now();
    const total = RUN_DURATION_MS[stage];
    let raf = 0;
    const tick = (now: number) => {
      const p = Math.min(1, (now - start) / total);
      setProgress(p);
      if (p < 1) raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [running, stage]);

  const isRunning = running === stage;
  // Centred with `inset-x-0 mx-auto`, NOT `left-1/2 -translate-x-1/2`: this card also carries
  // `anim-rise`, whose keyframes set `transform`, which silently wins over Tailwind's translate
  // utility and left the card sitting half a card-width right of centre over the map.
  const card =
    "pointer-events-none absolute inset-x-0 top-5 z-10 mx-auto w-[min(560px,calc(100%-3rem))] rounded-xl border bg-overlay/95 px-5 py-4 shadow-[0_18px_50px_rgba(0,0,0,0.6)] backdrop-blur-md";

  return (
    <>
      {!revealed && !isRunning && (
        <div className={`${card} anim-rise border-line-strong`}>
          <h2 className="t-title text-ink">{WAITING[stage].question}</h2>
          <p className="mt-2 t-small text-pretty text-ink-2">{WAITING[stage].body}</p>
          <p className="mt-3 t-small text-ink-2">
            Press{" "}
            <span className="font-medium text-drift">{RUN_LABEL[stage]}</span> to find out.
          </p>
        </div>
      )}

      {isRunning && (
        <div className={`${card} anim-fade border-drift/45`}>
          <div className="flex items-center gap-2.5">
            <span className="relative flex h-2.5 w-2.5 shrink-0">
              <span className="anim-ping absolute inset-0 rounded-full bg-drift" aria-hidden />
              <span className="relative h-2.5 w-2.5 rounded-full bg-drift" />
            </span>
            <span className="t-body font-medium text-ink">{RUNNING_LABEL[stage]}</span>
          </div>
          <div className="relative mt-3 h-1 overflow-hidden rounded-full bg-white/[0.08]">
            <div
              className="h-full rounded-full bg-drift transition-[width] duration-100 ease-linear"
              style={{ width: `${Math.round(progress * 100)}%` }}
            />
            {/* A highlight travelling the bar, so the wait reads as work rather than a stall. */}
            <div
              aria-hidden
              className="anim-sweep absolute inset-y-0 left-0 w-1/4"
              style={{
                background:
                  "linear-gradient(90deg, transparent, rgba(255,255,255,0.45), transparent)",
              }}
            />
          </div>
        </div>
      )}

      <div className="pointer-events-none absolute bottom-12 left-5 z-10 max-w-[360px] rounded-lg border border-line bg-overlay/90 px-3 py-2 text-[11px] leading-snug text-ink-3 backdrop-blur-sm">
        Replaying UDGAM&apos;s offline pipeline run for this scene. Every result shown was
        computed by our detector, drift model and scorer — not generated in the browser.
      </div>
    </>
  );
}
