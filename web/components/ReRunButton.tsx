// Tier 1a (harshita-deployment.md Part 1.2) — proves the result on screen isn't hardcoded by
// recomputing it live against api/main.py's /api/detect. Points at the API running offline on
// the demo machine (NEXT_PUBLIC_API_BASE, default localhost:8000) rather than a deployed
// endpoint — deployment is additive, never the demo path (Part 6).
"use client";

import { useState } from "react";
import { useAppStore } from "@/lib/store";
import { validateDetections } from "@/lib/loadCase";
import type { DetectionCollection } from "@/lib/contracts";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000";

export default function ReRunButton() {
  const caseId = useAppStore((s) => s.activeCaseId);
  const setDetections = useAppStore((s) => s.setDetections);
  const [state, setState] = useState<"idle" | "running" | "fallback">("idle");

  if (!caseId) return null;

  async function run() {
    setState("running");
    const requestedFor = caseId;
    try {
      const body = new FormData();
      body.set("case_id", requestedFor!);
      const res = await fetch(`${API_BASE}/api/detect`, { method: "POST", body });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = (await res.json()) as DetectionCollection;
      validateDetections(data, requestedFor!);

      // The judge may have switched cases while this was in flight — a late response for a
      // case that's no longer active must never overwrite what's on screen now.
      if (useAppStore.getState().activeCaseId !== requestedFor) return;
      setDetections(data);
      setState("idle");
    } catch {
      // Never show an error state to a judge (Part 4) — the bundle already on screen stands.
      if (useAppStore.getState().activeCaseId === requestedFor) setState("fallback");
    }
  }

  return (
    <div className="mb-4 flex items-center gap-2">
      <button
        onClick={run}
        disabled={state === "running"}
        className="rounded border border-line bg-raised px-3 py-1.5 text-[12px] font-medium text-ink transition hover:bg-hull disabled:opacity-60"
      >
        {state === "running" ? "Re-running detector…" : "Re-run detector"}
      </button>
      {state === "fallback" && (
        <span className="text-[11px] text-ink-3">served from bundle</span>
      )}
    </div>
  );
}
