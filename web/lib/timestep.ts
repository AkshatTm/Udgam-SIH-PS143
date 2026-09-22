// Maps the continuous slider value (`tNorm`, 0..1) onto an integer particle timestep.
//
// Slider geometry (see TimeSlider + docs/team/harshita-frontend.md): the handle at the far RIGHT is "T−0 detect"
// (tNorm = 1) and shows positions[0] — particles sitting on the slick. The far LEFT is
// "T−24h" (tNorm = 0) and shows positions[n_steps − 1] — the fully rewound cloud.
// So a smaller tNorm means a deeper rewind, i.e. a larger timestep index.

/** Integer timestep in 0..nSteps-1 for a slider value. Returns 0 until a bundle is loaded. */
export function tFromNorm(tNorm: number, nSteps: number): number {
  if (nSteps < 2) return 0;
  const t = Math.round((1 - tNorm) * (nSteps - 1));
  return Math.min(nSteps - 1, Math.max(0, t));
}

/** Slider value that lands exactly on timestep `t`. */
export function normFromT(t: number, nSteps: number): number {
  if (nSteps < 2) return 1;
  const clamped = Math.min(nSteps - 1, Math.max(0, t));
  return 1 - clamped / (nSteps - 1);
}

// ── Multi-group playback: one wall-clock timebase, many bundles ──────────────────────────────
//
// A case with independent spill groups (D46) ships one particles bundle PER GROUP, and those
// bundles do not agree on length: each group's rewind is truncated to its own measured age
// (D56), so Gulf of Alaska publishes 43, 32 and 31 frames and Mumbai 98, 61 and 49.
//
// The bug this replaces: MapView derived a single integer `t` from the PRIMARY bundle and used
// it to index every group's `frames[]`. Three things went wrong at once, and all three were
// visible on screen. Groups longer than the primary froze partway through their own rewind
// while the slider read "fully rewound". When the cadences also differed (45 min vs 15 min,
// pre-D56) the same `t` put different groups at different wall-clock times, so clouds that
// should converge never did. And a group SHORTER than the primary fell through the
// `frames[t] ?? frames[0]` guard, teleporting its whole cloud back onto the slick — the
// vanishing patch.
//
// The fix is to make hours-before-detection the master clock and let every bundle answer for
// itself where it is at that hour. Hours, not frames: frames are a per-bundle artefact,
// wall-clock time is the thing the groups actually share.

/** Hours before detection for a slider value, against a span in hours. tNorm = 1 is T−0. */
export function hoursBackFromNorm(tNorm: number, spanHours: number): number {
  if (!(spanHours > 0)) return 0;
  const h = (1 - tNorm) * spanHours;
  return Math.min(spanHours, Math.max(0, h));
}

/** Slider value that lands exactly on `hoursBack`. Inverse of hoursBackFromNorm. */
export function normFromHoursBack(hoursBack: number, spanHours: number): number {
  if (!(spanHours > 0)) return 1;
  const h = Math.min(spanHours, Math.max(0, hoursBack));
  return 1 - h / spanHours;
}

/** The hours-before-detection a bundle's last frame reaches. */
export function bundleSpanHours(timestepMinutes: number, nSteps: number): number {
  if (!(nSteps > 1) || !(timestepMinutes > 0)) return 0;
  return ((nSteps - 1) * timestepMinutes) / 60;
}

/**
 * The frame in THIS bundle that sits at `hoursBack`, clamped to its last frame.
 *
 * Clamped, never wrapped and never defaulted to frame 0: a group whose measured window ends
 * earlier than another's has no evidence past its own horizon, so it holds where the
 * measurement stopped. Snapping it back to the slick would assert the opposite of what the
 * data says, which is exactly the bug this replaces.
 */
export function frameForHoursBack(
  hoursBack: number,
  timestepMinutes: number,
  nSteps: number,
): number {
  if (nSteps < 2 || !(timestepMinutes > 0)) return 0;
  const idx = Math.round((hoursBack * 60) / timestepMinutes);
  return Math.min(nSteps - 1, Math.max(0, idx));
}

/**
 * The longest rewind any of these bundles reaches, in hours — the span the slider must cover.
 *
 * Taken across ALL groups, not from the primary: on Gulf of Alaska the primary is dated 7.75 h
 * while group-1 reaches 10.5 h, so a track sized to the primary would label the case "T−8h" and
 * leave two and a half hours of a real group's rewind unreachable.
 */
export function longestSpanHours(
  bundles: ReadonlyArray<{ timestepMinutes: number; nSteps: number } | null | undefined>,
): number {
  let max = 0;
  for (const b of bundles) {
    if (!b) continue;
    const span = bundleSpanHours(b.timestepMinutes, b.nSteps);
    if (span > max) max = span;
  }
  return max;
}
