// The case switcher's source. One synthetic case now; real bundles append here as they land.
// Labels are UI chrome — everything else about a case comes from its bundle.

export interface CaseEntry {
  id: string;
  label: string;
}

export const CASES: CaseEntry[] = [{ id: "case-000", label: "Case 000" }];

export const DEFAULT_CASE_ID = CASES[0].id;
