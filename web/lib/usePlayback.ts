"use client";

// Auto-scrub loop for the time slider. Mounted once (from TimeSlider). While `playing` is
// true it advances the rewind on a requestAnimationFrame clock and writes the matching
// slider value back into the store; nothing here touches particles.json.

import { useEffect, useMemo } from "react";
import { useAppStore } from "./store";
import { hoursBackFromNorm, longestSpanHours, normFromHoursBack } from "./timestep";

// docs/team/harshita-frontend.md asks for "~8× real time" playback. Read here as 8 timesteps per second: the
// 97-step / 24-hour case-000 rewind then plays in ~12 s, which is a good demo length.
// (Taking the 15-minute timestep literally in seconds gives absurd run times.) This is the
// one knob — raise it for a faster scrub, lower it to linger. Retune at the Monday checkpoint.
export const PLAYBACK_STEPS_PER_SEC = 8;

// The one-time Trace arrival rewind runs faster so it reads as a quick "here is where it
// came from" flourish rather than a slow scrub the judge has to wait out: 24 steps/s puts
// the 96-step / 24-hour case-000 rewind at ~4 s. Any manual play afterwards uses
// PLAYBACK_STEPS_PER_SEC. Selected via the store's `autoPlaying` flag, set by initTrace().
export const AUTOPLAY_STEPS_PER_SEC = 24;

// Fallback cadence when no bundle has declared one yet. Every bundle in the library integrates
// at 15 min and, since D56, publishes at 15 min too.
const FALLBACK_STEP_MINUTES = 15;

export function usePlayback(): void {
  const playing = useAppStore((s) => s.playing);
  const particles = useAppStore((s) => s.particles);
  const groupBundles = useAppStore((s) => s.groupBundles);
  const medianAgeH = useAppStore((s) => s.origin?.agePosterior?.median ?? null);

  // Wall-clock, not frame indices: the groups' bundles differ in length (see lib/timestep.ts).
  const spanHours = useMemo(
    () => longestSpanHours([particles, ...groupBundles.map((gb) => gb.particles)]),
    [particles, groupBundles],
  );
  const stepMinutes = particles?.timestepMinutes ?? FALLBACK_STEP_MINUTES;

  // WHERE THE ARRIVAL REWIND COMES TO REST.
  //
  // The track spans the whole 80 % age band, because that band is the evidence and a judge must
  // be able to drag across all of it. But the band's UPPER EDGE is not the answer — the
  // posterior's median is, and it is the number the panel quotes two inches away. Resting on
  // the upper edge meant Jacksonville rewound the full 10.1 h while its own card read 1.8 h,
  // and the origin cloud only reached full opacity out at 10.1 h, so the cloud a judge was
  // looking at was never the one the case actually claims.
  //
  // So the ARRIVAL rewind stops at the median. A manual press of play afterwards runs the full
  // span — that is the judge asking to see the rest of the band, and the band is still there.
  const restHours = useMemo(() => {
    if (medianAgeH === null || !(medianAgeH > 0) || !(spanHours > 0)) return spanHours;
    return Math.min(medianAgeH, spanHours);
  }, [medianAgeH, spanHours]);

  useEffect(() => {
    if (!playing || !(spanHours > 0)) return;

    // Read the autoplay flag once at loop start (not as an effect dependency): it only ever
    // flips together with `playing`, so the effect already re-runs when it matters and the
    // rAF loop never restarts mid-pass.
    const autoPlaying = useAppStore.getState().autoPlaying;
    const stepsPerSec = autoPlaying ? AUTOPLAY_STEPS_PER_SEC : PLAYBACK_STEPS_PER_SEC;
    const stopAt = autoPlaying ? restHours : spanHours;
    const stepMs = 1000 / stepsPerSec;
    const stepHours = stepMinutes / 60;
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
        const next = hoursBackFromNorm(tNorm, spanHours) + advance * stepHours;

        if (next >= stopAt - 1e-9) {
          setTNorm(normFromHoursBack(stopAt, spanHours)); // rest on the best estimate
          setPlaying(false);
          return; // stop — do not schedule another frame
        }
        setTNorm(normFromHoursBack(next, spanHours));
      }

      raf = requestAnimationFrame(tick);
    };

    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [playing, spanHours, stepMinutes, restHours]);
}
