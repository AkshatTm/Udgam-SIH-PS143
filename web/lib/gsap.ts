// Single registration point for GSAP. Every component imports { gsap, useGSAP } from here,
// never straight from "gsap"/"@gsap/react", so registerPlugin runs exactly once and there's
// one place to add a prefers-reduced-motion guard if that turns out to be worth centralising.
// GSAP owns UI-chrome micro-interactions only (Trace panel, slider, entrance timing) — deck.gl
// owns motion on the map layers themselves via its own `transitions` prop (web/CLAUDE.md: deck.gl
// owns the GPU on every case screen). No ScrollTrigger: nothing on a case screen scrolls.
import gsap from "gsap";
import { useGSAP } from "@gsap/react";

gsap.registerPlugin(useGSAP);

/** True when the viewer has asked for reduced motion. Check per-tween, not once at import time —
 *  it can change while the app is open. */
export function prefersReducedMotion(): boolean {
  if (typeof window === "undefined") return false;
  return window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}

export { gsap, useGSAP };
