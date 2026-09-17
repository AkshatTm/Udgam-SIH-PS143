// D46 — pure helpers over meta.spill_groups. No store/React dependency, so MapView, ContextPanel
// and the store itself can all reuse the same "which group is this detection in" logic without
// three slightly different copies.

import type { SpillGroup } from "./contracts";

/** The spill group a detection id belongs to, or null when there is no grouping data yet
 *  (still loading) or the id matches nothing (should not happen — every oil id is covered by
 *  exactly one group, per scripts/validate_case.py's check_spill_groups). */
export function spillGroupFor(
  detectionId: string | null,
  groups: SpillGroup[] | null,
): SpillGroup | null {
  if (!detectionId || !groups) return null;
  return groups.find((g) => g.member_detection_ids.includes(detectionId)) ?? null;
}

/** Every detection id in the SAME group as `detectionId` — "all the spills selected together".
 *  Falls back to `[detectionId]` alone when there is no grouping data (pre-D46 case, or still
 *  loading), so a bare click still highlights something instead of nothing. */
export function groupMemberIdsFor(
  detectionId: string | null,
  groups: SpillGroup[] | null,
): string[] {
  if (!detectionId) return [];
  return spillGroupFor(detectionId, groups)?.member_detection_ids ?? [detectionId];
}
