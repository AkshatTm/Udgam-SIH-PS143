"use client";

// The centrepiece control. The slider writes `tNorm` (0..1); lib/timestep.ts maps that onto
// an integer particle timestep that MapView renders. Play/pause runs the auto-scrub in
// lib/usePlayback.ts. Nothing here re-fetches or re-parses particles.json.

import { useAppStore } from "@/lib/store";
import { usePlayback } from "@/lib/usePlayback";
import { tFromNorm } from "@/lib/timestep";

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

  const onScrub = (v: number) => {
    if (playing) setPlaying(false); // a manual drag takes over from playback
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

  const readout = canPlay
    ? `T−${hoursBack.toFixed(1)} h`
    : particlesStatus === "loading"
      ? "loading…"
      : particlesStatus === "error"
        ? "unavailable"
        : "";

  return (
    <div className="flex items-center gap-3 border-t border-white/10 bg-[#0b0f14] px-4 py-2.5">
      <button
        type="button"
        onClick={onPlayPause}
        disabled={!canPlay}
        aria-label={playing ? "Pause playback" : "Play rewind"}
        className="shrink-0 rounded-full border border-white/15 px-2.5 py-1 text-xs leading-none text-white/80 transition-colors enabled:hover:bg-white/10 disabled:cursor-not-allowed disabled:text-white/25"
      >
        {playing ? "❚❚" : "▶"}
      </button>
      <span className="shrink-0 text-[11px] text-white/40">T−24h</span>
      <input
        type="range"
        min={0}
        max={1}
        step={0.01}
        value={tNorm}
        onChange={(e) => onScrub(Number(e.target.value))}
        className="h-1 w-full cursor-pointer appearance-none rounded bg-white/15 accent-white"
        aria-label="Time"
      />
      <span className="shrink-0 text-[11px] text-white/40">T−0 detect</span>
      <span className="w-20 shrink-0 text-right font-mono text-[11px] text-white/55">
        {readout}
      </span>
    </div>
  );
}
