"use client";

import { useState, useRef, useCallback } from "react";

/**
 * InfoDot — a tiny inline affordance that shows a one-sentence plain-language
 * explanation on hover or keyboard focus.
 *
 * Accessibility (WCAG 2.1 / ARIA 1.2):
 * - The trigger is a native <button> (implicit role "button" — no role override).
 * - The tooltip <span> carries role="tooltip" and a stable id.
 * - The button references the tooltip via aria-describedby at all times so
 *   screen-readers can announce it; the span is always in DOM (aria-hidden
 *   when not shown, visible when shown) to satisfy the reference.
 * - Keyboard: Tab reaches the button; focus opens the tooltip; Escape / blur closes it.
 * - No external UI library. No layout shifts (tooltip is absolute, out of flow).
 * - Matches the dark UI type scale (globals.css type scale).
 *
 * Positioning: the tooltip is anchored to the nearest positioned ANCESTOR, not
 * to the tiny "i" button itself — the caller's row (e.g. `MetricRow`'s root
 * div) must carry `relative`. Anchoring to the row (a fixed, panel-width box)
 * rather than the button keeps the tooltip inside the ~288 px ContextPanel
 * regardless of where the button ends up sitting inline (label text length
 * varies, so the button's own x-position is not reliable to anchor from —
 * anchoring to it directly caused real overflow on the longer Detect labels).
 * `align` then just picks which edge of that row box the tooltip hangs from:
 * "left" (default) for a dot after a leading label; "right" for a dot
 * trailing a value column near the row's right edge.
 */
export default function InfoDot({
  tip,
  align = "left",
}: {
  tip: string;
  align?: "left" | "right";
}) {
  const [visible, setVisible] = useState(false);
  const btnRef = useRef<HTMLButtonElement>(null);
  // Stable unique id — one per instance, never changes on re-render.
  const idRef = useRef(`infodot-${Math.random().toString(36).slice(2)}`);

  const open = useCallback(() => setVisible(true), []);
  const close = useCallback(() => setVisible(false), []);

  const handleKeyDown = useCallback((e: React.KeyboardEvent) => {
    if (e.key === "Escape") setVisible(false);
  }, []);

  // Delay so Tab-to-next-element does not flicker: only close if focus truly left.
  const handleBlur = useCallback(() => {
    setTimeout(() => {
      if (document.activeElement !== btnRef.current) setVisible(false);
    }, 0);
  }, []);

  return (
    // No `relative` here on purpose — the tooltip below anchors to the caller's
    // row (see the Positioning note above), not to this wrapper.
    <span className="inline-flex items-center">
      {/* Native button — no role override; aria-describedby always points to the tooltip id. */}
      <button
        ref={btnRef}
        type="button"
        aria-label="More information"
        aria-describedby={idRef.current}
        onMouseEnter={open}
        onMouseLeave={close}
        onFocus={open}
        onBlur={handleBlur}
        onKeyDown={handleKeyDown}
        className={[
          "inline-flex h-[14px] w-[14px] items-center justify-center",
          "rounded-full border text-[9px] font-semibold leading-none",
          "transition-colors duration-100 select-none",
          "focus:outline-none focus-visible:ring-1 focus-visible:ring-white/40",
          visible
            ? "border-drift/50 bg-drift/15 text-drift"
            : "border-line-strong bg-transparent text-ink-3 hover:border-drift/40 hover:text-drift",
        ].join(" ")}
      >
        i
      </button>

      {/*
        Tooltip span is ALWAYS in the DOM so aria-describedby is never a dangling ref.
        aria-hidden="true" when closed keeps it silent for screen-readers in that state.
        pointer-events-none prevents it from intercepting mouse events beneath.
        w-52 (208 px) fits safely inside the ContextPanel — anchored from the
        button's left edge normally, or its right edge when `align="right"` so a
        trailing dot near the panel's right edge doesn't push the tooltip off-panel.
      */}
      <span
        id={idRef.current}
        role="tooltip"
        aria-hidden={!visible}
        className={[
          "absolute bottom-full z-50 mb-1.5",
          align === "right" ? "right-0" : "left-0",
          "w-52 rounded-lg border border-line-strong",
          "bg-overlay px-3 py-2.5",
          "text-[12px] leading-relaxed text-ink-2",
          "shadow-[0_10px_28px_rgba(0,0,0,0.55)] pointer-events-none",
          "transition-opacity duration-100",
          visible ? "opacity-100" : "opacity-0 pointer-events-none",
        ].join(" ")}
      >
        {tip}
      </span>
    </span>
  );
}
