"use client";

// The persistent shell for the four in-case screens (Detect / Trace / Attribute / Verify).
// It lives in app/case/[id]/layout.tsx, so it stays mounted while the [stage] route changes —
// which is what keeps MapView (and its particle performance work) alive across stage
// navigation. The active stage is read from the URL and mirrored into the store; the store
// remains the single source of truth every child component already reads.
//
// This is the Phase 1.1 structure only. The Detect / Trace / Attribute screen internals
// (MapView, ContextPanel, TimeSlider, LayerToggles) are unchanged.

import { useEffect } from "react";
import { usePathname, useRouter } from "next/navigation";
import dynamic from "next/dynamic";
import { useAppStore } from "@/lib/store";
import { adjacentStage, isStage, primaryActionLabel } from "@/lib/flow";
import type { Act } from "@/lib/contracts";
import Header from "./Header";
import StageRail from "./StageRail";
import TimeSlider from "./TimeSlider";
import LayerToggles from "./LayerToggles";
import FlowBar from "./FlowBar";
import PrimaryAction from "./PrimaryAction";

// MapLibre touches `window` — never render it on the server.
const MapView = dynamic(() => import("./MapView"), {
  ssr: false,
  loading: () => <div className="absolute inset-0 bg-[#0b0f14]" />,
});

// The context panel pulls in Recharts — keep it out of the first-load bundle.
const ContextPanel = dynamic(() => import("./ContextPanel"), {
  ssr: false,
  loading: () => (
    <aside className="w-72 shrink-0 border-l border-white/[0.08] bg-[#0b0f14]" />
  ),
});

/** Parse "/case/<id>/<stage>" → its parts. `rawStage` is whatever the URL literally had. */
function parsePath(pathname: string): {
  caseId: string | null;
  stage: Act;
  rawStage: string | undefined;
} {
  const parts = pathname.split("/").filter(Boolean); // ["case", <id>, <stage>]
  const caseId = parts[0] === "case" && parts[1] ? parts[1] : null;
  const rawStage = parts[2];
  return { caseId, stage: isStage(rawStage) ? rawStage : "detect", rawStage };
}

export default function CaseWorkspace() {
  const pathname = usePathname() ?? "";
  const router = useRouter();
  const { caseId, stage, rawStage } = parsePath(pathname);

  const status = useAppStore((s) => s.status);
  const error = useAppStore((s) => s.error);
  const meta = useAppStore((s) => s.meta);
  const activeCaseId = useAppStore((s) => s.activeCaseId);
  const setActiveCase = useAppStore((s) => s.setActiveCase);
  const loadActiveCase = useAppStore((s) => s.loadActiveCase);
  const setStage = useAppStore((s) => s.setStage);
  const particlesStatus = useAppStore((s) => s.particlesStatus);
  const originStatus = useAppStore((s) => s.originStatus);
  const initTrace = useAppStore((s) => s.initTrace);

  // URL case → store. setActiveCase() no-ops when the id already matches, so kick off the
  // first load explicitly when the store is still idle for that id.
  useEffect(() => {
    if (!caseId) return;
    if (useAppStore.getState().activeCaseId !== caseId) {
      setActiveCase(caseId);
    } else if (useAppStore.getState().status === "idle") {
      void loadActiveCase();
    }
  }, [caseId, setActiveCase, loadActiveCase]);

  // A garbage stage segment (/case/<id>/banana) → send it to the flow's first stage.
  useEffect(() => {
    if (caseId && rawStage !== undefined && !isStage(rawStage)) {
      router.replace(`/case/${caseId}/detect`);
    }
  }, [caseId, rawStage, router]);

  // URL stage → store. setStage() itself refuses an act the case does not expose.
  useEffect(() => {
    setStage(stage);
  }, [stage, setStage]);

  // Reconcile the other way: once meta for THIS case is in, if the URL points at a stage the
  // case does not expose, replace it with the first stage it does.
  useEffect(() => {
    if (!meta || !caseId || activeCaseId !== caseId) return;
    if (!meta.acts_available.includes(stage)) {
      router.replace(`/case/${caseId}/${meta.acts_available[0]}`);
    }
  }, [meta, caseId, activeCaseId, stage, router]);

  // Slice 1 — Trace arrival is self-demonstrating: once particles + origin are ready, turn
  // those layers on and autoplay the rewind from T−0. initTrace() is guarded per case inside
  // the store, so calling it on a revisit or after a user layer toggle is a no-op.
  useEffect(() => {
    if (stage !== "trace" || caseId === null || activeCaseId !== caseId) return;
    if (particlesStatus === "ready" && originStatus === "ready") initTrace();
  }, [stage, caseId, activeCaseId, particlesStatus, originStatus, initTrace]);

  const acts = meta?.acts_available;
  const nextStage = adjacentStage(stage, acts, 1);
  const onPrimary = () => {
    if (nextStage) router.push(`/case/${caseId}/${nextStage}`);
    else router.push("/");
  };

  return (
    <div className="grid h-full grid-rows-[auto_auto_1fr_auto] bg-[#0b0f14] text-white">
      <Header />
      <FlowBar stage={stage} />

      {error ? (
        <div className="flex items-center justify-center p-8">
          <div className="max-w-md rounded border border-[#ff4d4d]/30 bg-[#ff4d4d]/[0.08] p-4">
            <div className="text-[11px] font-semibold text-[#ff8a8a]">
              Case bundle failed to load
            </div>
            <p className="mt-1 whitespace-pre-wrap text-[10px] text-[#ffb0b0]/70">
              {error}
            </p>
            <p className="mt-2 text-[10px] text-[#ffb0b0]/50">
              This is a contract bug — tell Akshat. The frontend does not patch
              bundle data.
            </p>
          </div>
        </div>
      ) : !meta ? (
        <div className="flex items-center justify-center">
          <span className="font-mono text-[11px] text-white/30">Loading case…</span>
        </div>
      ) : (
        <div className="grid min-h-0 grid-cols-[auto_1fr_auto]">
          <StageRail />
          <div className="relative min-w-0">
            <MapView />
            {status === "loading" && (
              <div className="absolute left-1/2 top-3 -translate-x-1/2 rounded border border-white/[0.08] bg-black/50 px-3 py-1">
                <span className="font-mono text-[10px] text-white/50">Loading…</span>
              </div>
            )}
            <PrimaryAction label={primaryActionLabel(stage, acts)} onClick={onPrimary} />
          </div>
          <ContextPanel />
        </div>
      )}

      {meta && !error && (
        <footer className="flex flex-col bg-[#0b0f14]">
          <TimeSlider />
          <div className="flex items-center border-t border-white/[0.06] px-4 py-1.5">
            <LayerToggles />
          </div>
        </footer>
      )}
    </div>
  );
}
