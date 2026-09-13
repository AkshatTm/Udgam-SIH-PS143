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

/** Label for the bottom-right primary action while on `stage` (docs/04 Part B). At the end
 *  of the flow it always sends the judge back to the gallery. */
export function primaryActionLabel(stage: Act, acts: Act[] | undefined): string {
  const next = adjacentStage(stage, acts, 1);
  if (!next) return "Try another case";
  switch (stage) {
    case "detect":
      return "Trace this spill back";
    case "trace":
      return next === "verify" ? "See what really happened" : "Find who did it";
    case "attribute":
      return "Check our answer";
    default:
      return "Continue";
  }
}

/** Why a stage is unavailable for a case — the default tooltip on the disabled rail item and
 *  progress step (docs/04 Part D, D3). Ennore hits the `attribute` case. */
export const STAGE_UNAVAILABLE_REASON: Record<Act, string> = {
  detect: "no detection output for this case",
  trace: "no backward-drift reconstruction for this case",
  attribute: "no free historical AIS is published for these waters",
  verify: "no official finding to compare against yet",
};

/** The tooltip for a greyed act, given case context. On a no-spill scene (docs/04 Part D, D1)
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

/** One dot in the five-step progress indicator (docs/04 Part C, C3). */
export interface FlowStep {
  key: "pick" | Act;
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
    stage("detect", "Detect"),
    stage("trace", "Trace"),
    stage("attribute", "Find"),
    stage("verify", "Verify"),
  ];
}
