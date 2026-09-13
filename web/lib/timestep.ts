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
