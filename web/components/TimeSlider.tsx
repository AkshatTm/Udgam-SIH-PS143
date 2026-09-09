"use client";

// The centrepiece control. The slider writes `tNorm` (0..1); lib/timestep.ts maps that onto
// an integer particle timestep that MapView renders. Play/pause runs the auto-scrub in
// lib/usePlayback.ts. Nothing here re-fetches or re-parses particles.json.

import { useAppStore } from "@/lib/store";
import { usePlayback } from "@/lib/usePlayback";
import { tFromNorm } from "@/lib/timestep";

// Format a UTC ISO timestamp as "DD MMM YYYY · HH:MM UTC" — used in the right readout.
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

  const nSteps = particles?.nSteps ?? 0;
  const canPlay = nSteps > 1;
  const t = tFromNorm(tNorm, nSteps);
  const hoursBack = canPlay ? (t * particles!.timestepMinutes) / 60 : 0;
  const minutesBack = canPlay ? t * particles!.timestepMinutes : 0;

  const onScrub = (v: number) => {
    if (playing) setPlaying(false); // manual drag takes over from playback
    setTNorm(v);
  };

  const onPlayPause = () => {
    if (playing) {
      setPlaying(false);
      return;
    }
    if (tNorm <= 0) setTNorm(1); // already fully rewound → restart from T−0
    setPlaying(true);
  };

  // Right-side timestamp: derive from particles.t0 minus the current rewind offset.
  const timestampReadout = canPlay
    ? fmtTimestamp(particles!.t0, minutesBack)
    : particlesStatus === "loading"
      ? "loading…"
      : particlesStatus === "error"
        ? "unavailable"
        : "";

  const hoursReadout = canPlay ? `T−${hoursBack.toFixed(1)} h` : "";

  return (
    <div className="border-t border-white/[0.08] bg-[#0b0f14] px-4 pt-2.5 pb-2">
      {/* Top row: label left, timestamp right */}
      <div className="mb-1.5 flex items-center justify-between">
        <span className="text-[9px] font-semibold uppercase tracking-[0.16em] text-white/30">
          Trace History
        </span>
        {timestampReadout && (
          <span className="font-mono text-[10px] text-[#f97316]/80">
            {timestampReadout}
          </span>
        )}
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
          className="w-full"
          aria-label="Trace time"
          disabled={!canPlay}
        />

        {/* Right label */}
        <span className="shrink-0 font-mono text-[9px] text-white/28">
          T−0
        </span>

        {/* Hours readout */}
        <span className="w-16 shrink-0 text-right font-mono text-[10px] text-white/45">
          {hoursReadout}
        </span>
      </div>
    </div>
  );
}
