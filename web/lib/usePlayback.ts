"use client";

// Auto-scrub loop for the time slider. Mounted once (from TimeSlider). While `playing` is
// true it advances the timestep on a requestAnimationFrame clock and writes the matching
// slider value back into the store; nothing here touches particles.json.

import { useEffect } from "react";
import { useAppStore } from "./store";
import { normFromT, tFromNorm } from "./timestep";

// docs/04 asks for "~8× real time" playback. Read here as 8 timesteps per second: the
// 97-step / 24-hour case-000 rewind then plays in ~12 s, which is a good demo length.
// (Taking the 15-minute timestep literally in seconds gives absurd run times.) This is the
// one knob — raise it for a faster scrub, lower it to linger. Retune at the Monday checkpoint.
export const PLAYBACK_STEPS_PER_SEC = 8;

// The one-time Trace arrival rewind runs faster so it reads as a quick "here is where it
// came from" flourish rather than a slow scrub the judge has to wait out: 24 steps/s puts
// the 96-step / 24-hour case-000 rewind at ~4 s. Any manual play afterwards uses
// PLAYBACK_STEPS_PER_SEC. Selected via the store's `autoPlaying` flag, set by initTrace().
export const AUTOPLAY_STEPS_PER_SEC = 24;

export function usePlayback(): void {
  const playing = useAppStore((s) => s.playing);
  const nSteps = useAppStore((s) => s.particles?.nSteps ?? 0);

  useEffect(() => {
    if (!playing || nSteps < 2) return;

    // Read the autoplay flag once at loop start (not as an effect dependency): it only ever
    // flips together with `playing`, so the effect already re-runs when it matters and the
    // rAF loop never restarts mid-pass.
    const stepsPerSec = useAppStore.getState().autoPlaying
      ? AUTOPLAY_STEPS_PER_SEC
      : PLAYBACK_STEPS_PER_SEC;
    const stepMs = 1000 / stepsPerSec;
    let raf = 0;
    let last = performance.now();
    let acc = 0;

    const tick = (now: number): void => {
      acc += now - last;
      last = now;

      if (acc >= stepMs) {
        const advance = Math.floor(acc / stepMs);
        acc -= advance * stepMs;

        const { tNorm, setTNorm, setPlaying } = useAppStore.getState();
        const next = tFromNorm(tNorm, nSteps) + advance;

        if (next >= nSteps - 1) {
          setTNorm(normFromT(nSteps - 1, nSteps)); // rest fully rewound at T−24h
          setPlaying(false);
          return; // stop — do not schedule another frame
        }
        setTNorm(normFromT(next, nSteps));
      }

      raf = requestAnimationFrame(tick);
    };

    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [playing, nSteps]);
}
