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
import { useIdleReset } from "@/lib/useIdleReset";
import { isNoSpill } from "@/lib/detections";
import { isStage, primaryAction } from "@/lib/flow";
import type { Act } from "@/lib/contracts";
import StageSpine from "./StageSpine";
import TimeSlider from "./TimeSlider";
import LayerToggles from "./LayerToggles";
import PrimaryAction from "./PrimaryAction";
import VerifyScreen from "./VerifyScreen";
import NoSpillBanner from "./NoSpillBanner";
import RunOverlay from "./RunOverlay";

// MapLibre touches `window` — never render it on the server.
const MapView = dynamic(() => import("./MapView"), {
  ssr: false,
  loading: () => <div className="absolute inset-0 bg-abyss" />,
});

// The context panel pulls in Recharts — keep it out of the first-load bundle.
const ContextPanel = dynamic(() => import("./ContextPanel"), {
  ssr: false,
  loading: () => (
    <aside className="w-[22rem] shrink-0 border-l border-line bg-hull" />
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
  const detections = useAppStore((s) => s.detections);
  const activeCaseId = useAppStore((s) => s.activeCaseId);
  const setActiveCase = useAppStore((s) => s.setActiveCase);
  const loadActiveCase = useAppStore((s) => s.loadActiveCase);
  const setStage = useAppStore((s) => s.setStage);
  const particlesStatus = useAppStore((s) => s.particlesStatus);
  const originStatus = useAppStore((s) => s.originStatus);
  const initTrace = useAppStore((s) => s.initTrace);
  const resetToGallery = useAppStore((s) => s.resetToGallery);
  const revealed = useAppStore((s) => s.revealed);
  const traceRevealed = revealed.trace;
  const running = useAppStore((s) => s.running);
  const runStage = useAppStore((s) => s.runStage);

  // C8 — after ~90 s of no interaction, return to the Gallery in a clean state. Mounted here
  // so the timer/listeners exist only while a case is open; unmounts (and cleans up) on "/".
  useIdleReset();

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
  // Guided flow: the rewind only starts once the judge has pressed "Run backward drift".
  useEffect(() => {
    if (stage !== "trace" || caseId === null || activeCaseId !== caseId) return;
    if (!traceRevealed) return;
    if (particlesStatus === "ready" && originStatus === "ready") initTrace();
  }, [stage, caseId, activeCaseId, traceRevealed, particlesStatus, originStatus, initTrace]);

  const acts = meta?.acts_available;
  const action = primaryAction(stage, acts, revealed);
  const onPrimary = () => {
    if (running) return;
    if (action.kind === "run") {
      runStage(stage);
    } else if (action.kind === "next" && action.next) {
      // Moving on IS pressing that stage's Run button: navigate, and start its run there.
      const next = action.next;
      router.push(`/case/${caseId}/${next}`);
      runStage(next);
    } else {
      // Terminal stage → "Try another case": same clean-state reset as idle / Start over.
      resetToGallery();
      router.push("/");
    }
  };

  return (
    <div className="grid h-full min-w-0 grid-rows-[auto_1fr_auto] overflow-hidden bg-abyss text-ink">
      <StageSpine stage={stage} />

      {error ? (
        <div className="flex items-center justify-center p-8">
          <div className="max-w-md rounded-lg border border-alert/30 bg-alert/[0.07] p-5">
            <div className="t-subtitle text-alert">
              This case bundle would not load
            </div>
            <p className="mt-2 whitespace-pre-wrap font-mono text-[12px] text-ink-2">
              {error}
            </p>
            <p className="mt-3 t-small text-ink-3">
              This is a data problem, not a display one — the app does not patch bundle data.
            </p>
          </div>
        </div>
      ) : !meta ? (
        <div className="flex items-center justify-center">
          <span className="font-mono text-[13px] text-ink-3">Loading case…</span>
        </div>
      ) : !meta.acts_available.includes(stage) ? (
        // D3 — a direct URL to an act this case does not expose. The reconcile effect above
        // redirects to the first available stage on the next tick; until it lands, show a
        // neutral placeholder rather than flashing the map + a stale ContextPanel. Not an
        // error state — no red, no "failed".
        <div className="flex items-center justify-center">
          <span className="font-mono text-[13px] text-ink-3">
            Not part of this case — taking you to the first stage…
          </span>
        </div>
      ) : (
        <div className="grid min-h-0 min-w-0 grid-cols-[minmax(0,1fr)_auto]">
          <div className="relative min-w-0">
            <MapView />
            {/* D1 — a valid zero-oil scene is a *result*, not an error: an over-map banner
                while the SAR + grey look-alike polygons stay visible below it. */}
            {stage === "detect" && !error && revealed.detect && isNoSpill(detections) && (
              <NoSpillBanner />
            )}
            {stage !== "verify" && <RunOverlay stage={stage} />}
            {/* Verify replaces the map+panel view but keeps MapView mounted underneath so it
                is never torn down on stage navigation. ContextPanel and the footer controls
                are suppressed for this stage; PrimaryAction stays (it is "Try another case →"
                here, wired the same as every other stage). */}
            {stage === "verify" && <VerifyScreen />}
            {status === "loading" && (
              <div className="absolute left-1/2 top-3 -translate-x-1/2 rounded-full border border-line bg-overlay/85 px-3 py-1 backdrop-blur-sm">
                <span className="font-mono text-[12px] text-ink-2">Loading…</span>
              </div>
            )}
            <PrimaryAction
              label={action.label}
              onClick={onPrimary}
              disabled={running !== null}
            />
          </div>
          {stage !== "verify" && <ContextPanel />}
        </div>
      )}

      {meta && !error && stage !== "verify" && meta.acts_available.includes(stage) && (
        <footer className="flex flex-col bg-deep">
          {/* The rewind slider belongs to the drift result — it appears once that has been run. */}
          {revealed.trace && <TimeSlider />}
          <div className="flex items-center border-t border-line px-4 py-2">
            <LayerToggles />
          </div>
        </footer>
      )}
    </div>
  );
}
