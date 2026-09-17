"use client";

// Counts a number up from 0 to its real value on mount/change. Writes straight to the DOM via a
// ref inside GSAP's onUpdate (no per-frame React state) — the same no-per-frame-allocation
// discipline MapView.tsx already uses for its RAF-driven scan-line/ship-tracker effects
// (web/CLAUDE.md's performance section). Only ever wraps a bare number: hemisphere-swap
// coordinate strings (fmtLat/fmtLon) don't tween meaningfully and are excluded on purpose.

import { useEffect, useRef } from "react";
import { gsap, prefersReducedMotion } from "@/lib/gsap";

export default function AnimatedNumber({
  value,
  digits,
  format,
  duration = 0.6,
  className,
}: {
  value: number;
  digits: number;
  /** Formats the (already-rounded) intermediate value for display, e.g. fmt(x, digits). */
  format: (x: number, digits: number) => string;
  duration?: number;
  className?: string;
}) {
  const ref = useRef<HTMLSpanElement>(null);
  const prev = useRef(0);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const from = { v: prev.current };
    if (prefersReducedMotion()) {
      el.textContent = format(value, digits);
      prev.current = value;
      return;
    }
    const tween = gsap.to(from, {
      v: value,
      duration,
      ease: "power2.out",
      onUpdate: () => {
        el.textContent = format(from.v, digits);
      },
      onComplete: () => {
        prev.current = value;
      },
    });
    return () => {
      tween.kill();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [value, digits, duration]);

  return (
    <span ref={ref} className={className}>
      {format(0, digits)}
    </span>
  );
}
