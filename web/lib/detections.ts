// A no-spill result (docs/04 Part D, D1; Master §6.3): detections loaded, but not one feature
// is classified as oil. Look-alikes may still be present — the scene proves the system can
// say "no", it is not an error.
//
// Keyed on the actual `classification` field, never on `meta.case_type` (a Gallery hint), and
// guarded on a non-null collection so a missing / malformed detections.geojson (which is the
// contract-error path, handled at the CaseWorkspace level) can never read as no-spill.

import type { DetectionCollection } from "./contracts";

export function isNoSpill(detections: DetectionCollection | null): boolean {
  return (
    detections != null &&
    !detections.features.some((f) => f.properties.classification === "oil")
  );
}
