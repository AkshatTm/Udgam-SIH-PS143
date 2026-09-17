"use client";

// Replaces the native <details>/<summary> the per-estimator age bands used to render in, with a
// GSAP height/opacity tween instead of the browser's instant jump-cut. Keeps the same keyboard
// operability a <details> gives for free via a real <button aria-expanded aria-controls>.

import { useId, useRef, useState } from "react";
import { gsap, useGSAP, prefersReducedMotion } from "@/lib/gsap";
import { Row } from "@/components/PanelAtoms";
import { fmt } from "@/lib/format";

export default function AgeDisclosure({
  estimators,
}: {
  estimators: Record<string, [number, number] | null>;
}) {
  const [open, setOpen] = useState(false);
  const contentRef = useRef<HTMLDivElement>(null);
  const id = useId();

  useGSAP(
    () => {
      const el = contentRef.current;
      if (!el) return;
      if (prefersReducedMotion()) {
        gsap.set(el, { height: open ? "auto" : 0, opacity: open ? 1 : 0 });
        return;
      }
      if (open) {
        const target = el.scrollHeight;
        gsap.fromTo(
          el,
          { height: 0, opacity: 0 },
          {
            height: target,
            opacity: 1,
            duration: 0.3,
            ease: "power2.out",
            onComplete: () => gsap.set(el, { height: "auto" }),
          },
        );
      } else {
        gsap.to(el, { height: 0, opacity: 0, duration: 0.22, ease: "power2.in" });
      }
    },
    { dependencies: [open], scope: contentRef },
  );

  return (
    <div className="mt-2 text-[13px] text-ink-2">
      <button
        type="button"
        aria-expanded={open}
        aria-controls={id}
        onClick={() => setOpen((v) => !v)}
        className="flex select-none items-center gap-1 text-ink-3 transition-colors hover:text-ink-2"
      >
        <span
          aria-hidden
          className="inline-block text-[10px] transition-transform duration-200"
          style={{ transform: open ? "rotate(90deg)" : "rotate(0deg)" }}
        >
          ▸
        </span>
        Per-estimator bands
      </button>
      <div ref={contentRef} id={id} className="overflow-hidden" style={{ height: 0, opacity: 0 }}>
        <div className="mt-1 space-y-0.5 pb-0.5">
          {Object.entries(estimators).map(([name, band]) => (
            <Row
              key={name}
              label={name.charAt(0).toUpperCase() + name.slice(1)}
              value={band === null ? "not applicable" : `${fmt(band[0], 0)} – ${fmt(band[1], 0)} h`}
            />
          ))}
        </div>
      </div>
    </div>
  );
}
