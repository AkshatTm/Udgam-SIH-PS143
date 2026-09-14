"use client";

// The centrepiece control. The slider writes `tNorm` (0..1); lib/timestep.ts maps that onto an
// integer particle timestep that MapView renders. Play/pause runs the auto-scrub in
// lib/usePlayback.ts. Nothing here re-fetches or re-parses particles.json.
//
// The readout is deliberately the largest data on the screen: "how far back in time am I" is
// the question the whole Trace stage exists to answer, and a judge dragging this should be able
// to read the answer from across a room.

import { useEffect, useRef, useState } from "react";
import { useAppStore } from "@/lib/store";
import { usePlayback } from "@/lib/usePlayback";
import { tFromNorm } from "@/lib/timestep";

/** Format a UTC ISO timestamp as "DD MMM YYYY · HH:MM UTC" — used in the readout. */
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

export default function TimeSlider() {
  usePlayback();

  const tNorm = useAppStore((s) => s.tNorm);
  const setTNorm = useAppStore((s) => s.setTNorm);
  const playing = useAppStore((s) => s.playing);
  const setPlaying = useAppStore((s) => s.setPlaying);
  const particles = useAppStore((s) => s.particles);
  const particlesStatus = useAppStore((s) => s.particlesStatus);
  const activeStage = useAppStore((s) => s.activeStage);
  const activeCaseId = useAppStore((s) => s.activeCaseId);

  const nSteps = particles?.nSteps ?? 0;
  const canPlay = nSteps > 1;
  const t = tFromNorm(tNorm, nSteps);
  const minutesBack = canPlay ? t * particles!.timestepMinutes : 0;

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

  const onScrub = (v: number) => {
    setShowHint(false);
    if (playing) setPlaying(false); // manual drag takes over from playback
    setTNorm(v);
  };

  const onPlayPause = () => {
    setShowHint(false);
    if (playing) {
      setPlaying(false);
      return;
    }
    if (tNorm <= 0) setTNorm(1); // already fully rewound → restart from T−0
    setPlaying(true);
  };

  // Readout: relative time built from the integer timestep, exact UTC stamp stacked under it.
  const totalMinutesBack = Math.round(minutesBack);
  const hoursBack = Math.floor(totalMinutesBack / 60);
  const minsBack = totalMinutesBack % 60;
  const relativeReadout = canPlay ? `T−${hoursBack}h ${minsBack}m` : "—";
  const timestampReadout = canPlay
    ? fmtTimestamp(particles!.t0, minutesBack)
    : particlesStatus === "loading"
      ? "loading…"
      : particlesStatus === "error"
        ? "unavailable"
        : "";

  // Resting thumb pulse — only when the Trace rewind is stopped fully rewound at T−24h.
  const isResting = canPlay && !playing && activeStage === "trace" && t === nSteps - 1;

  return (
    <div className="border-t border-line bg-deep px-4 py-3">
      <div className="flex items-center gap-4">
        <button
          type="button"
          onClick={onPlayPause}
          disabled={!canPlay}
          aria-label={playing ? "Pause the rewind" : "Play the rewind"}
          className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full border border-line-strong text-ink transition-colors enabled:hover:border-drift enabled:hover:bg-drift/10 enabled:hover:text-drift disabled:border-line disabled:text-ink-4"
        >
          {playing ? (
            <svg width="11" height="12" viewBox="0 0 11 12" aria-hidden fill="currentColor">
              <rect x="0" y="0" width="3.5" height="12" rx="1" />
              <rect x="7.5" y="0" width="3.5" height="12" rx="1" />
            </svg>
          ) : (
            <svg width="11" height="12" viewBox="0 0 11 12" aria-hidden fill="currentColor">
              <path d="M1 0.9a.8.8 0 0 1 1.2-.7l8 5.1a.8.8 0 0 1 0 1.4l-8 5.1A.8.8 0 0 1 1 11.1z" />
            </svg>
          )}
        </button>

        <div className="flex min-w-0 flex-1 flex-col gap-1">
          <div className="flex items-baseline justify-between gap-3">
            <span className="t-label">Rewind</span>
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
            <span className="shrink-0 font-mono text-[11px] text-ink-3">T−24h</span>
            <input
              type="range"
              min={0}
              max={1}
              step={0.005}
              value={tNorm}
              onChange={(e) => onScrub(Number(e.target.value))}
              className={`w-full${isResting ? " slider-resting" : ""}`}
              aria-label="Rewind through the drift reconstruction"
              disabled={!canPlay}
            />
            <span className="shrink-0 font-mono text-[11px] text-ink-3">T−0</span>
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
