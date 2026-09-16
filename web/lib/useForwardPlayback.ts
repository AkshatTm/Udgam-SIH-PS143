"use client";

// Auto-scrub loop for the forward-drift playhead. Mounted once (from TimeSlider), mirrors
// usePlayback.ts but drives `forwardNorm` (0 at T0, 1 at the forecast horizon) instead of an
// integer particle timestep. There is no fixed frame count to step through here — the forward
// cone is a continuous ensemble envelope (lib/forward.ts), not a positions-per-step array — so
// this advances `forwardNorm` continuously by elapsed time rather than in discrete ticks.

import { useEffect } from "react";
import { useAppStore } from "./store";

// Full T0 -> horizon sweep takes this many seconds. Independent of the actual horizon length in
// hours: a 24 h or a 48 h forecast both animate at the same pace, since what a judge is watching
// is "the cone growing", not real time.
export const FORWARD_PLAYBACK_SECONDS = 6;

export function useForwardPlayback(): void {
  const forwardPlaying = useAppStore((s) => s.forwardPlaying);
  const hasForward = useAppStore((s) => (s.forward?.envelope.length ?? 0) > 0);

  useEffect(() => {
    if (!forwardPlaying || !hasForward) return;

    const normPerMs = 1 / (FORWARD_PLAYBACK_SECONDS * 1000);
    let raf = 0;
    let last = performance.now();

    const tick = (now: number): void => {
      const dt = now - last;
      last = now;

      const { forwardNorm, setForwardNorm, setForwardPlaying } = useAppStore.getState();
      const next = forwardNorm + dt * normPerMs;

      if (next >= 1) {
        setForwardNorm(1); // rest fully forward at the horizon
        setForwardPlaying(false);
        return; // stop — do not schedule another frame
      }
      setForwardNorm(next);

      raf = requestAnimationFrame(tick);
    };

    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [forwardPlaying, hasForward]);
}
