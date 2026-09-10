"use client";

// The centrepiece control. The slider writes `tNorm` (0..1); lib/timestep.ts maps that onto
// an integer particle timestep that MapView renders. Play/pause runs the auto-scrub in
// lib/usePlayback.ts. Nothing here re-fetches or re-parses particles.json.

import { useEffect, useRef, useState } from "react";
import { useAppStore } from "@/lib/store";
import { usePlayback } from "@/lib/usePlayback";
import { tFromNorm } from "@/lib/timestep";

// Format a UTC ISO timestamp as "DD MMM YYYY · HH:MM UTC" — used in the readout.
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

  // Onboarding hint: shown once per case on the first Trace visit with particles ready,
  // fades after ~5.5 s, and dismisses immediately on any scrub / play-pause interaction.
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
  const relativeReadout = canPlay ? `T − ${hoursBack}h ${minsBack}m` : "";
  const timestampReadout = canPlay
    ? fmtTimestamp(particles!.t0, minutesBack)
    : particlesStatus === "loading"
      ? "loading…"
      : particlesStatus === "error"
        ? "unavailable"
        : "";

  // Resting thumb pulse — only when the Trace rewind is stopped fully rewound at T−24h.
  const isResting =
    canPlay && !playing && activeStage === "trace" && t === nSteps - 1;

  return (
    <div className="border-t border-white/[0.08] bg-[#0b0f14] px-4 pt-2.5 pb-2">
      {/* Top row: label left, onboarding hint right */}
      <div className="mb-1.5 flex items-center justify-between">
        <span className="text-[9px] font-semibold uppercase tracking-[0.16em] text-white/30">
          Trace History
        </span>
        <span
          aria-hidden={!showHint}
          className={`font-mono text-[10px] text-white/40 transition-opacity duration-700 ${
            showHint ? "opacity-100" : "opacity-0"
          }`}
        >
          ← drag to rewind time
        </span>
      </div>

      {/* Controls row */}
      <div className="flex items-center gap-3">
        {/* Play/pause button */}
        <button
          type="button"
          onClick={onPlayPause}
          disabled={!canPlay}
          aria-label={playing ? "Pause playback" : "Play rewind"}
          className="flex h-5 w-5 shrink-0 items-center justify-center rounded border border-white/[0.14] text-[9px] text-white/70 transition-colors enabled:hover:border-white/30 enabled:hover:text-white disabled:cursor-not-allowed disabled:border-white/[0.06] disabled:text-white/20"
        >
          {playing ? "❚❚" : "▶"}
        </button>

        {/* Left label */}
        <span className="shrink-0 font-mono text-[9px] text-white/28">
          T−24h
        </span>

        {/* Scrubber — styled via globals.css */}
        <input
          type="range"
          min={0}
          max={1}
          step={0.005}
          value={tNorm}
          onChange={(e) => onScrub(Number(e.target.value))}
          className={`w-full${isResting ? " slider-resting" : ""}`}
          aria-label="Trace time"
          disabled={!canPlay}
        />

        {/* Right label */}
        <span className="shrink-0 font-mono text-[9px] text-white/28">
          T−0
        </span>

        {/* Readout — relative time with the exact UTC timestamp stacked underneath */}
        <div className="flex w-36 shrink-0 flex-col items-end leading-tight">
          <span className="font-mono text-[10px] text-white/45">
            {relativeReadout}
          </span>
          <span className="font-mono text-[9px] text-[#f97316]/70">
            {timestampReadout}
          </span>
        </div>
      </div>
    </div>
  );
}
