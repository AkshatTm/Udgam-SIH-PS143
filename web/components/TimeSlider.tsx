"use client";

// The centrepiece control. The slider writes a single physical value in -1..1: T0 sits at the
// centre (0), the left half (-1..0) is the backward rewind and the right half (0..1) is the
// forward forecast. That physical value is split across two store fields so the rest of the app
// keeps its existing vocabulary — `tNorm` (0..1, backward, unchanged since Phase 2 — see
// lib/timestep.ts) and `forwardNorm` (0..1, forward, lib/forward.ts) — and the two are mutually
// exclusive: driving one always parks the other back at its T0 rest value (tNorm=1,
// forwardNorm=0). Play/pause for each direction runs its own auto-scrub (lib/usePlayback.ts,
// lib/useForwardPlayback.ts). Nothing here re-fetches or re-parses particles.json or
// forward_impact.json.
//
// The readout is deliberately the largest data on the screen: "how far back — or forward — in
// time am I" is the question the whole Trace stage exists to answer, and a judge dragging this
// should be able to read the answer from across a room.
//
// Physicality pass: a fill bar gives the drag continuous "weight" (plain React, same cadence as
// `sliderValue` already updates at — no new perf class); GSAP is reserved for the discrete
// moments layered on top (a quick overshoot on press, an elastic settle on release or when
// playback starts/stops, a snap-flash on the T0 label when the handle crosses it, and a pop-in
// on the play/pause icon swap instead of the previous instant cut). None of this touches
// MapView.tsx — the map keeps reading tNorm/forwardNorm via updateTriggers exactly as before.

import { useEffect, useRef, useState } from "react";
import { useAppStore } from "@/lib/store";
import { usePlayback } from "@/lib/usePlayback";
import { useForwardPlayback } from "@/lib/useForwardPlayback";
import { tFromNorm } from "@/lib/timestep";
import { forwardSpanHours } from "@/lib/forward";
import { gsap, useGSAP, prefersReducedMotion } from "@/lib/gsap";

/** Format a UTC ISO timestamp as "DD MMM YYYY · HH:MM UTC" — used in the readout.
 *  A negative offsetMinutes reads forward in time (used by the forward playhead). */
function fmtTimestamp(iso: string, offsetMinutes: number): string {
  const d = new Date(new Date(iso).getTime() - offsetMinutes * 60_000);
  if (Number.isNaN(d.getTime())) return "";
  const date = d.toLocaleDateString("en-GB", {
    day: "2-digit",
    month: "short",
    year: "numeric",
    timeZone: "UTC",
  });
  const time = d.toLocaleTimeString("en-GB", {
    hour: "2-digit",
    minute: "2-digit",
    timeZone: "UTC",
  });
  return `${date} · ${time} UTC`;
}

/** Quick press-down/up weight cue for a button — layered on top of the existing hover colour
 *  change, not a replacement for it. */
function pulseButton(el: HTMLElement | null) {
  if (!el || prefersReducedMotion()) return;
  gsap.to(el, { scale: 0.88, duration: 0.08, ease: "power1.out", yoyo: true, repeat: 1 });
}

/** Icon pop-in: React has already swapped the SVG by the time this runs (it's keyed off the
 *  same boolean prop), so this is a felt "arrival" for the new icon rather than a literal
 *  cross-dissolve between two mounted nodes — simpler and just as effective for "not an instant
 *  cut" without juggling two SVGs' hover/disabled states in parallel. */
function popIcon(el: HTMLElement | null) {
  if (!el || prefersReducedMotion()) return;
  gsap.fromTo(el, { opacity: 0, scale: 0.55 }, { opacity: 1, scale: 1, duration: 0.22, ease: "back.out(2.4)" });
}

export default function TimeSlider() {
  usePlayback();
  useForwardPlayback();

  const tNorm = useAppStore((s) => s.tNorm);
  const setTNorm = useAppStore((s) => s.setTNorm);
  const playing = useAppStore((s) => s.playing);
  const setPlaying = useAppStore((s) => s.setPlaying);
  const forwardNorm = useAppStore((s) => s.forwardNorm);
  const setForwardNorm = useAppStore((s) => s.setForwardNorm);
  const forwardPlaying = useAppStore((s) => s.forwardPlaying);
  const setForwardPlaying = useAppStore((s) => s.setForwardPlaying);
  const particles = useAppStore((s) => s.particles);
  const particlesStatus = useAppStore((s) => s.particlesStatus);
  const forward = useAppStore((s) => s.forward);
  const activeStage = useAppStore((s) => s.activeStage);
  const activeCaseId = useAppStore((s) => s.activeCaseId);
  const forwardLayerOn = useAppStore((s) => s.layers.forward);
  const toggleLayer = useAppStore((s) => s.toggleLayer);

  // Forward slick is drawn only while its layer toggle is on (LayerToggles), same as every
  // other optional layer. The playhead controls below are the "run" for it, so driving them
  // (drag or play) turns the layer on rather than leaving a judge scrubbing an invisible cone.
  const showForwardLayer = () => {
    if (!forwardLayerOn) toggleLayer("forward");
  };

  const nSteps = particles?.nSteps ?? 0;
  const canPlay = nSteps > 1;
  const t = tFromNorm(tNorm, nSteps);
  const minutesBack = canPlay ? t * particles!.timestepMinutes : 0;

  // The rewind span comes from the bundle, exactly as the forward span does. The left label
  // used to be the literal string "T−24h" while the readout beside it was computed — so on
  // every case in the library the track said 24 h and the readout said 72 h. The rewind is
  // now sized by the measured age, so the label has to be derived or it is wrong again.
  const backSpanHours = canPlay ? ((nSteps - 1) * particles!.timestepMinutes) / 60 : 0;
  const backSpanLabel = canPlay
    ? `T−${backSpanHours >= 10 ? Math.round(backSpanHours) : backSpanHours.toFixed(1)}h`
    : "T−0h";

  // The single most probable release time inside that span. The scrubber shows the range the
  // evidence allows; this shows where the evidence actually peaks, which is the question
  // anyone watching the rewind is really asking.
  const origin = useAppStore((s) => s.origin);
  const medianAgeH = origin?.agePosterior?.median ?? null;
  const medianPct =
    medianAgeH !== null && backSpanHours > 0 && medianAgeH <= backSpanHours
      ? 50 - (medianAgeH / backSpanHours) * 50
      : null;

  // Forward half. `forward` is optional (Master §6.10) — null on a case Stage 2 produced no
  // forecast for, which leaves the right half of the slider inert rather than erroring.
  const canPlayForward = (forward?.envelope.length ?? 0) > 0;
  const forwardSpan = canPlayForward ? forwardSpanHours(forward!) : 0;
  const inForwardZone = forwardNorm > 0;

  // Onboarding hint: shown once per case on the first Trace visit with particles ready, fades
  // after ~5.5 s, and dismisses immediately on any scrub / play-pause interaction.
  const [showHint, setShowHint] = useState(false);
  const hintedCaseRef = useRef<string | null>(null);
  useEffect(() => {
    if (activeStage !== "trace" || particlesStatus !== "ready") return;
    if (hintedCaseRef.current === activeCaseId) return;
    hintedCaseRef.current = activeCaseId;
    setShowHint(true);
    const timer = window.setTimeout(() => setShowHint(false), 5500);
    return () => window.clearTimeout(timer);
  }, [activeStage, particlesStatus, activeCaseId]);

  // Single physical handle position: negative is backward (tNorm below 1), positive is forward
  // (forwardNorm above 0). The two fields are kept mutually exclusive by every writer below, so
  // reading whichever one has moved off its T0 rest value is unambiguous.
  const sliderValue = inForwardZone ? forwardNorm : tNorm - 1;

  const onScrub = (v: number) => {
    setShowHint(false);
    if (playing) setPlaying(false); // manual drag takes over from playback
    if (forwardPlaying) setForwardPlaying(false);
    if (v <= 0) {
      if (forwardNorm !== 0) setForwardNorm(0);
      setTNorm(1 + v);
    } else if (canPlayForward) {
      if (tNorm !== 1) setTNorm(1);
      setForwardNorm(v);
      showForwardLayer();
    } // else: no forecast for this case — the right half stays inert, handle snaps back to 0
  };

  const backBtnRef = useRef<HTMLButtonElement>(null);
  const forwardBtnRef = useRef<HTMLButtonElement>(null);
  const backIconRef = useRef<HTMLSpanElement>(null);
  const forwardIconRef = useRef<HTMLSpanElement>(null);

  const onBackwardPlayPause = () => {
    setShowHint(false);
    pulseButton(backBtnRef.current);
    if (playing) {
      setPlaying(false);
      return;
    }
    if (forwardPlaying) setForwardPlaying(false);
    if (tNorm <= 0 || forwardNorm > 0) {
      // Already fully rewound, or sitting in the forward zone → restart from T0.
      setForwardNorm(0);
      setTNorm(1);
    }
    setPlaying(true);
  };

  const onForwardPlayPause = () => {
    setShowHint(false);
    pulseButton(forwardBtnRef.current);
    if (forwardPlaying) {
      setForwardPlaying(false);
      return;
    }
    if (playing) setPlaying(false);
    if (forwardNorm >= 1 || tNorm < 1) {
      // Already fully forward, or sitting in the backward zone → restart from T0.
      setTNorm(1);
      setForwardNorm(0);
    }
    showForwardLayer();
    setForwardPlaying(true);
  };

  // Icon pop-in whenever the button's own playing state flips (not on the other button's).
  useGSAP(() => popIcon(backIconRef.current), { dependencies: [playing] });
  useGSAP(() => popIcon(forwardIconRef.current), { dependencies: [forwardPlaying] });

  // Readout: relative time built from the integer timestep / forward hour, exact UTC stamp
  // stacked under it. The forward branch reads `forwardNorm` directly (continuous, no discrete
  // step) rather than through tFromNorm, which only ever indexes the backward particle bundle.
  const totalMinutesForward = canPlayForward ? Math.round(forwardNorm * forwardSpan * 60) : 0;
  const totalMinutesBack = Math.round(minutesBack);
  const hoursBack = Math.floor(totalMinutesBack / 60);
  const minsBack = totalMinutesBack % 60;
  const hoursFwd = Math.floor(totalMinutesForward / 60);
  const minsFwd = totalMinutesForward % 60;

  const relativeReadout = inForwardZone
    ? `T+${hoursFwd}h ${minsFwd}m`
    : canPlay
      ? `T−${hoursBack}h ${minsBack}m`
      : "—";
  const timestampReadout = inForwardZone
    ? fmtTimestamp(forward!.t0, -totalMinutesForward)
    : canPlay
      ? fmtTimestamp(particles!.t0, minutesBack)
      : particlesStatus === "loading"
        ? "loading…"
        : particlesStatus === "error"
          ? "unavailable"
          : "";

  // Resting thumb pulse — when the Trace scrubber is stopped fully rewound, or fully
  // forward at the horizon.
  const isResting =
    activeStage === "trace" &&
    ((canPlay && !playing && t === nSteps - 1) ||
      (canPlayForward && !forwardPlaying && forwardNorm >= 1));

  // Fill bar — the primary drag-weight cue. Plain React, same cadence sliderValue already
  // updates at (no new perf class). Grows from the T0 centre (50%) toward the thumb.
  const fillPct = ((sliderValue + 1) / 2) * 100; // 0..100, 50 = T0
  const fillRef = useRef<HTMLDivElement>(null);

  // Elastic settle whenever playback starts/stops (in addition to the pointerup handler below).
  const isMoving = playing || forwardPlaying;
  useGSAP(
    () => {
      if (!fillRef.current || prefersReducedMotion()) return;
      gsap.to(fillRef.current, { scaleY: 1, duration: 0.5, ease: "elastic.out(1, 0.5)" });
    },
    { dependencies: [isMoving] },
  );
  const onSliderPointerDown = () => {
    if (!fillRef.current || prefersReducedMotion()) return;
    gsap.to(fillRef.current, {
      scaleY: 1.4,
      duration: 0.08,
      ease: "power1.out",
      yoyo: true,
      repeat: 1,
      transformOrigin: "center",
    });
  };
  const onSliderPointerUp = () => {
    if (!fillRef.current || prefersReducedMotion()) return;
    gsap.to(fillRef.current, { scaleY: 1, duration: 0.5, ease: "elastic.out(1, 0.5)" });
  };

  // T0-crossing snap: a one-shot flash on the T0 label the moment the physical handle crosses
  // the boundary between rewind and forecast — the same instant onScrub's own `v <= 0` branch
  // switches which store field it writes to.
  const t0Ref = useRef<HTMLSpanElement>(null);
  const prevSignRef = useRef(Math.sign(sliderValue));
  useEffect(() => {
    const sign = Math.sign(sliderValue);
    if (sign !== 0 && prevSignRef.current !== 0 && sign !== prevSignRef.current && t0Ref.current) {
      if (!prefersReducedMotion()) {
        gsap.fromTo(
          t0Ref.current,
          { scale: 1.7, color: "var(--drift)" },
          { scale: 1, duration: 0.45, ease: "power2.out", clearProps: "color,scale" },
        );
      }
    }
    prevSignRef.current = sign;
  }, [sliderValue]);

  return (
    <div className="border-t border-line bg-deep px-4 py-3">
      <div className="flex items-center gap-4">
        <button
          ref={backBtnRef}
          type="button"
          onClick={onBackwardPlayPause}
          disabled={!canPlay}
          aria-label={playing ? "Pause the rewind" : "Play the rewind"}
          title="Backward drift"
          className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full border border-line-strong text-ink transition-colors enabled:hover:border-drift enabled:hover:bg-drift/10 enabled:hover:text-drift disabled:border-line disabled:text-ink-4"
        >
          <span ref={backIconRef} className="flex items-center justify-center">
            {playing ? (
              <svg width="11" height="12" viewBox="0 0 11 12" aria-hidden fill="currentColor">
                <rect x="0" y="0" width="3.5" height="12" rx="1" />
                <rect x="7.5" y="0" width="3.5" height="12" rx="1" />
              </svg>
            ) : (
              <svg width="11" height="12" viewBox="0 0 11 12" aria-hidden fill="currentColor">
                <path d="M10 0.9a.8.8 0 0 0-1.2-.7l-8 5.1a.8.8 0 0 0 0 1.4l8 5.1a.8.8 0 0 0 1.2-.7z" />
              </svg>
            )}
          </span>
        </button>

        <button
          ref={forwardBtnRef}
          type="button"
          onClick={onForwardPlayPause}
          disabled={!canPlayForward}
          aria-label={
            forwardPlaying
              ? "Pause the forward drift"
              : forwardLayerOn
                ? "Play the forward drift"
                : "Run forward slick"
          }
          title={forwardLayerOn ? "Forward drift" : "Run forward slick"}
          className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full border border-line-strong text-ink transition-colors enabled:hover:border-drift enabled:hover:bg-drift/10 enabled:hover:text-drift disabled:border-line disabled:text-ink-4"
        >
          <span ref={forwardIconRef} className="flex items-center justify-center">
            {forwardPlaying ? (
              <svg width="11" height="12" viewBox="0 0 11 12" aria-hidden fill="currentColor">
                <rect x="0" y="0" width="3.5" height="12" rx="1" />
                <rect x="7.5" y="0" width="3.5" height="12" rx="1" />
              </svg>
            ) : (
              <svg width="11" height="12" viewBox="0 0 11 12" aria-hidden fill="currentColor">
                <path d="M1 0.9a.8.8 0 0 1 1.2-.7l8 5.1a.8.8 0 0 1 0 1.4l-8 5.1A.8.8 0 0 1 1 11.1z" />
              </svg>
            )}
          </span>
        </button>

        <div className="flex min-w-0 flex-1 flex-col gap-1">
          <div className="flex items-baseline justify-between gap-3">
            <span className="t-label">Drift</span>
            <span
              aria-hidden={!showHint || activeStage !== "trace"}
              className={`shrink-0 t-small text-drift transition-opacity duration-700 ${
                showHint && activeStage === "trace" ? "opacity-100" : "opacity-0"
              }`}
            >
              Drag to rewind
            </span>
          </div>
          <div className="flex items-center gap-3">
            <span className="shrink-0 font-mono text-[11px] text-ink-3">{backSpanLabel}</span>
            <div className="relative w-full">
              <span
                ref={t0Ref}
                aria-hidden
                className="pointer-events-none absolute left-1/2 top-[-11px] -translate-x-1/2 font-mono text-[10px] text-ink-4"
              >
                T0
              </span>
              {/* Most probable release age, from the posterior's median. Drawn only when the
                  case carries a measured age — never a guess dressed as a tick. */}
              {medianPct !== null && (
                <>
                  <span
                    aria-hidden
                    className="pointer-events-none absolute top-1/2 h-[11px] w-px -translate-y-1/2 bg-drift/70"
                    style={{ left: `${medianPct}%` }}
                  />
                  <span
                    aria-hidden
                    className="pointer-events-none absolute top-[-11px] -translate-x-1/2 whitespace-nowrap font-mono text-[10px] text-drift/80"
                    style={{ left: `${medianPct}%` }}
                  >
                    {medianAgeH! < 10 ? medianAgeH!.toFixed(1) : Math.round(medianAgeH!)}h
                  </span>
                </>
              )}
              {/* Fill bar — weight cue, sits behind the native thumb/track. */}
              <div
                ref={fillRef}
                aria-hidden
                className="pointer-events-none absolute top-1/2 h-[3px] -translate-y-1/2 rounded-full bg-drift/35"
                style={{
                  left: `${Math.min(50, fillPct)}%`,
                  width: `${Math.abs(fillPct - 50)}%`,
                }}
              />
              <input
                type="range"
                min={-1}
                max={1}
                step={0.005}
                value={sliderValue}
                onChange={(e) => onScrub(Number(e.target.value))}
                onPointerDown={onSliderPointerDown}
                onPointerUp={onSliderPointerUp}
                className={`relative w-full${isResting ? " slider-resting" : ""}`}
                aria-label="Drift through the backward reconstruction and forward forecast"
                disabled={!canPlay && !canPlayForward}
              />
            </div>
            <span
              className={`shrink-0 font-mono text-[11px] ${canPlayForward ? "text-ink-3" : "text-ink-4"}`}
            >
              {canPlayForward ? `T+${Math.round(forwardSpan)}h` : "T+0h"}
            </span>
          </div>
        </div>

        <div className="flex w-44 shrink-0 flex-col items-end leading-none">
          <span className="font-mono text-[19px] font-medium tabular-nums text-ink">
            {relativeReadout}
          </span>
          <span className="mt-1 font-mono text-[11px] text-drift/80">{timestampReadout}</span>
        </div>
      </div>
    </div>
  );
}
