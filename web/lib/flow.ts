// The five-screen flow: Gallery → Detect → Trace → Attribute → Verify
// (docs/00_MASTER_PLAN.md §2.1). Gallery is a route of its own ("/"); the four in-case
// stages are the pipeline acts (§6.1). This module is the single source of truth for their
// order, their friendly flow labels, and "what comes next" given a case's acts_available.
// It is pure — no React, no store — so it stays trivially testable.

import type { Act } from "./contracts";
import { ALL_ACTS } from "./contracts";

/** The in-case stages, in flow order. Mirrors ALL_ACTS; named separately so call sites read
 *  as "the flow stages" rather than "the pipeline acts". */
export const FLOW_STAGES: readonly Act[] = ALL_ACTS;

/** Narrow an arbitrary path segment to a flow stage. */
export function isStage(value: string | undefined): value is Act {
  return value !== undefined && (FLOW_STAGES as readonly string[]).includes(value);
}

/** The stages this case actually exposes, in flow order. */
export function availableStages(acts: Act[] | undefined): Act[] {
  return FLOW_STAGES.filter((s) => acts?.includes(s) ?? false);
}

/** The next (dir 1) or previous (dir -1) available stage, or null at an end of the flow. */
export function adjacentStage(
  stage: Act,
  acts: Act[] | undefined,
  dir: 1 | -1,
): Act | null {
  const avail = availableStages(acts);
  const i = avail.indexOf(stage);
  if (i < 0) return null;
  const j = i + dir;
  return j >= 0 && j < avail.length ? avail[j] : null;
}

/** The stages a judge may click back (or forward) to in the progress bar: every available stage
 *  up to the first one that has not been revealed yet. Walking stops at the first unrevealed
 *  stage, so the guided order is preserved — Verify cannot be reached before Find has run, even
 *  though `revealed.verify` starts true (it has no Run animation of its own). */
export function navigableStages(
  acts: Act[] | undefined,
  revealed: Record<Act, boolean>,
): Act[] {
  const out: Act[] = [];
  for (const stage of availableStages(acts)) {
    if (!revealed[stage]) break;
    out.push(stage);
  }
  return out;
}

/** What pressing Run on a stage does, as a button label. */
export const RUN_LABEL: Record<Act, string> = {
  detect: "Run oil detection",
  trace: "Run backward drift",
  attribute: "Run attribution",
  verify: "Check our answer",
};

/** Present-tense line shown while a stage's Run animation plays. */
export const RUNNING_LABEL: Record<Act, string> = {
  detect: "Scanning the radar scene for dark, damped water…",
  trace: "Running 50 perturbed drift simulations backwards through currents and wind…",
  attribute: "Matching AIS tracks and radar contacts against the reconstructed origin…",
  verify: "",
};

/** The bottom-right primary action (docs/team/harshita-frontend.md Part B), for the guided flow:
 *  on a stage that has not been run yet it runs it; once it has, it moves to the next stage
 *  and runs that one. At the end of the flow it sends the judge back to the gallery. */
export function primaryAction(
  stage: Act,
  acts: Act[] | undefined,
  revealed: Record<Act, boolean>,
): { label: string; kind: "run" | "next" | "gallery"; next: Act | null } {
  if (!revealed[stage]) return { label: RUN_LABEL[stage], kind: "run", next: null };
  const next = adjacentStage(stage, acts, 1);
  if (!next) return { label: "Try another case", kind: "gallery", next: null };
  return { label: RUN_LABEL[next], kind: "next", next };
}

/** What clicking a step in the progress spine should do.
 *
 *  This is the union of what the old FlowBar and StageRail each allowed, with the guided order
 *  kept: a step whose results are already on screen is a plain destination, the one step the
 *  judge has not run yet behaves exactly like the primary action (go there AND run it), and
 *  anything further ahead stays inert with a reason. So a judge can jump forward without
 *  walking the primary button round the flow, and can never land on a stage whose results would
 *  appear without the run that produced them. */
export type StepTarget =
  | { kind: "current" }
  | { kind: "navigate" }
  | { kind: "run" }
  | { kind: "inert"; reason: string };

export function stepTarget(
  step: Act,
  current: Act,
  acts: Act[] | undefined,
  revealed: Record<Act, boolean>,
  ctx?: { noSpill?: boolean },
): StepTarget {
  if (step === current) return { kind: "current" };
  if (!(acts?.includes(step) ?? false)) {
    return { kind: "inert", reason: stageUnavailableReason(step, ctx) };
  }
  const reachable = navigableStages(acts, revealed);
  if (reachable.includes(step)) return { kind: "navigate" };
  // The first stage past the revealed chain — the same one `primaryAction` would offer next.
  const avail = availableStages(acts);
  const next = avail[reachable.length];
  if (next === step) return { kind: "run" };
  return { kind: "inert", reason: "run the step before it first" };
}

/** Why a stage is unavailable for a case — the default tooltip on the disabled rail item and
 *  progress step (docs/team/harshita-frontend.md Part D, D3). Ennore hits the `attribute` case. */
export const STAGE_UNAVAILABLE_REASON: Record<Act, string> = {
  detect: "no detection output for this case",
  trace: "no backward-drift reconstruction for this case",
  attribute: "no free historical AIS is published for these waters",
  verify: "no official finding to compare against yet",
};

/** The tooltip for a greyed act, given case context. On a no-spill scene (docs/team/harshita-frontend.md Part D, D1)
 *  the Trace / Attribute reasons are specific — "nothing to trace"; every other case keeps the
 *  static STAGE_UNAVAILABLE_REASON string above (Ennore's D3 "no free historical AIS…"
 *  included). */
export function stageUnavailableReason(
  act: Act,
  ctx?: { noSpill?: boolean },
): string {
  if (ctx?.noSpill) {
    if (act === "trace") return "nothing to trace — no oil was detected in this scene";
    if (act === "attribute") return "no oil origin to attribute";
  }
  return STAGE_UNAVAILABLE_REASON[act];
}

/** One dot in the five-step progress indicator (docs/team/harshita-frontend.md Part C, C3). */
export interface FlowStep {
  key: "pick" | "scene" | Act;
  label: string;
  available: boolean;
  /** Present only when `available` is false. */
  reason?: string;
}

export function flowSteps(
  acts: Act[] | undefined,
  ctx?: { noSpill?: boolean },
): FlowStep[] {
  const stage = (key: Act, label: string): FlowStep => ({
    key,
    label,
    available: acts?.includes(key) ?? false,
    reason: stageUnavailableReason(key, ctx),
  });
  return [
    { key: "pick", label: "Pick", available: true },
    // Not a pipeline act: the Detect screen before its Run button is pressed, showing the raw
    // radar scene on its own so the judge sees what the detector is about to look at.
    { key: "scene", label: "Scene", available: acts?.includes("detect") ?? false },
    stage("detect", "Detect"),
    stage("trace", "Trace"),
    stage("attribute", "Find"),
    stage("verify", "Verify"),
  ];
}
