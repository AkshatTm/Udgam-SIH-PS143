"use client";

import { useEffect } from "react";
import dynamic from "next/dynamic";
import { useAppStore } from "@/lib/store";
import Header from "./Header";
import StageRail from "./StageRail";
import TimeSlider from "./TimeSlider";
import LayerToggles from "./LayerToggles";

// MapLibre touches `window` — never render it on the server.
const MapView = dynamic(() => import("./MapView"), {
  ssr: false,
  loading: () => <div className="absolute inset-0 bg-[#0b0f14]" />,
});

// The context panel pulls in Recharts (for the Detect object-card feature bars). Keep it out
// of the first-load bundle — it only matters once a case has loaded, same as the map.
const ContextPanel = dynamic(() => import("./ContextPanel"), {
  ssr: false,
  loading: () => (
    <aside className="w-80 shrink-0 border-l border-white/10 bg-[#0b0f14]" />
  ),
});

export default function AppShell() {
  const status = useAppStore((s) => s.status);
  const error = useAppStore((s) => s.error);
  const meta = useAppStore((s) => s.meta);
  const loadActiveCase = useAppStore((s) => s.loadActiveCase);

  useEffect(() => {
    void loadActiveCase();
  }, [loadActiveCase]);

  if (status === "error") {
    return (
      <div className="flex h-full items-center justify-center bg-[#0b0f14] p-8">
        <div className="max-w-md rounded-md border border-[#ff4d4d]/40 bg-[#ff4d4d]/10 p-4 text-sm text-[#ffb0b0]">
          <div className="font-semibold text-[#ff8a8a]">Case bundle failed to load</div>
          <p className="mt-1 whitespace-pre-wrap text-[#ffb0b0]/80">{error}</p>
          <p className="mt-2 text-xs text-[#ffb0b0]/60">
            This is a contract bug — tell Akshat. The frontend does not patch bundle data.
          </p>
        </div>
      </div>
    );
  }

  // First load, nothing to show yet.
  if (!meta) {
    return (
      <div className="flex h-full items-center justify-center bg-[#0b0f14] text-sm text-white/50">
        Loading case…
      </div>
    );
  }

  return (
    <div className="grid h-full grid-rows-[auto_1fr_auto] bg-[#0b0f14] text-white">
      <Header />

      <div className="grid min-h-0 grid-cols-[auto_1fr_auto]">
        <StageRail />
        <div className="relative min-w-0">
          <MapView />
          {status === "loading" && (
            <div className="absolute left-1/2 top-3 -translate-x-1/2 rounded bg-black/60 px-3 py-1 text-xs text-white/70">
              Loading…
            </div>
          )}
        </div>
        <ContextPanel />
      </div>

      <footer className="flex flex-col gap-2 bg-[#0b0f14] pb-2.5">
        <TimeSlider />
        <div className="px-4">
          <LayerToggles />
        </div>
      </footer>
    </div>
  );
}
