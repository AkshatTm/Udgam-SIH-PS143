// Phase 4 (P1.1) verification-bundle loader. Fetches /cases/<id>/verification.json ONCE and
// validates the fields the Verify screen consumes against docs/00_MASTER_PLAN.md §6.8 and the
// validator's check_verification. verification.json is hand-authored research prose, not a
// pipeline output — this loader never generates, rewrites, or patches any of it. A malformed
// field throws a descriptive Error which the shell surfaces as a visible banner (a contract
// bug for Akshat), exactly like origin.ts / suspects.ts.
//
// Unknown top-level or nested keys (e.g. a scaffold file's "_status") are ignored: we read
// only the fields we render and never assert the object has nothing else.

import type {
  RawAssessment,
  RawNaapResult,
  RawOfficialFinding,
  RawResponsibleParty,
  RawVerification,
  Verdict,
} from "./contracts";

const VERDICTS: readonly Verdict[] = ["hit", "partial", "miss", "not_applicable"];

export interface ResponsibleParty {
  name: string;
  /** null is valid and expected — the official finding may name a party with no MMSI. */
  mmsi: string | null;
  imo: string | null;
  role: string | null;
}

export interface OfficialFinding {
  summary: string;
  responsibleParties: ResponsibleParty[];
  sourceName: string;
  /** Raw string from the file — the Verify screen scheme-checks it before rendering an href. */
  sourceUrl: string;
  sourceType: string;
  volumeReported: string | null;
  caveat: string | null;
}

export interface NaapResult {
  originSummary: string;
  /** MMSI strings exactly as the file provides them — never enriched from suspects.json. */
  topSuspects: string[];
  abstained: boolean;
}

export interface Assessment {
  verdict: Verdict;
  /** Human-written prose, rendered verbatim. */
  explanation: string;
  whatWouldHaveHelped: string | null;
}

export interface VerificationBundle {
  officialFinding: OfficialFinding;
  naapResult: NaapResult;
  assessment: Assessment;
}

async function fetchJson<T>(url: string): Promise<T> {
  let res: Response;
  try {
    res = await fetch(url, { cache: "no-store" });
  } catch (err) {
    throw new Error(`Could not fetch ${url}: ${(err as Error).message}`);
  }
  if (!res.ok) {
    throw new Error(`Failed to fetch ${url}: HTTP ${res.status}`);
  }
  try {
    return (await res.json()) as T;
  } catch {
    throw new Error(`${url} is not valid JSON`);
  }
}

function nonEmptyString(v: unknown, where: string): string {
  if (typeof v !== "string" || v.trim().length === 0) {
    throw new Error(`${where}: must be a non-empty string`);
  }
  return v;
}

function optionalString(v: unknown, where: string): string | null {
  if (v === undefined || v === null) return null;
  if (typeof v !== "string") {
    throw new Error(`${where}: must be a string when present`);
  }
  return v.trim().length === 0 ? null : v;
}

function validateOfficialFinding(of: RawOfficialFinding, id: string): void {
  const where = `${id}/verification.json/official_finding`;
  if (!of || typeof of !== "object") {
    throw new Error(`${where}: missing`);
  }
  nonEmptyString(of.summary, `${where}.summary`);
  nonEmptyString(of.source_name, `${where}.source_name`);
  // Non-empty only — the scheme check happens at render time (a bad scheme is a contract
  // issue to surface, not a load failure).
  nonEmptyString(of.source_url, `${where}.source_url`);
  nonEmptyString(of.source_type, `${where}.source_type`);
  if (!Array.isArray(of.responsible_parties)) {
    throw new Error(`${where}.responsible_parties: must be an array (may be empty)`);
  }
  of.responsible_parties.forEach((p: RawResponsibleParty, i: number) => {
    const pw = `${where}.responsible_parties[${i}]`;
    nonEmptyString(p?.name, `${pw}.name`);
    if (p.mmsi !== null && p.mmsi !== undefined && typeof p.mmsi !== "string") {
      throw new Error(`${pw}.mmsi: must be a string or null`);
    }
  });
}

function validateNaapResult(nr: RawNaapResult, id: string): void {
  const where = `${id}/verification.json/naap_result`;
  if (!nr || typeof nr !== "object") {
    throw new Error(`${where}: missing`);
  }
  nonEmptyString(nr.origin_summary, `${where}.origin_summary`);
  if (!Array.isArray(nr.top_suspects) || nr.top_suspects.some((s) => typeof s !== "string")) {
    throw new Error(`${where}.top_suspects: must be an array of strings (may be empty)`);
  }
  if (typeof nr.abstained !== "boolean") {
    throw new Error(`${where}.abstained: must be a boolean`);
  }
}

function validateAssessment(a: RawAssessment, id: string): void {
  const where = `${id}/verification.json/assessment`;
  if (!a || typeof a !== "object") {
    throw new Error(`${where}: missing`);
  }
  if (!VERDICTS.includes(a.verdict)) {
    throw new Error(
      `${where}.verdict: must be one of ${VERDICTS.join(" | ")} (got ${JSON.stringify(a.verdict)})`,
    );
  }
  nonEmptyString(a.explanation, `${where}.explanation`);
}

export async function loadVerificationBundle(id: string): Promise<VerificationBundle> {
  const raw = await fetchJson<RawVerification>(`/cases/${id}/verification.json`);
  const where = `${id}/verification.json`;
  if (!raw || typeof raw !== "object") {
    throw new Error(`${where}: not an object`);
  }
  validateOfficialFinding(raw.official_finding, id);
  validateNaapResult(raw.naap_result, id);
  validateAssessment(raw.assessment, id);

  const of = raw.official_finding;
  const nr = raw.naap_result;
  const a = raw.assessment;

  return {
    officialFinding: {
      summary: of.summary,
      responsibleParties: of.responsible_parties.map((p) => ({
        name: p.name,
        mmsi: p.mmsi ?? null,
        imo: p.imo ?? null,
        role: optionalString(p.role, `${where}/official_finding/responsible_parties/role`),
      })),
      sourceName: of.source_name,
      sourceUrl: of.source_url,
      sourceType: of.source_type,
      volumeReported: optionalString(of.volume_reported, `${where}/official_finding/volume_reported`),
      caveat: optionalString(of.caveat, `${where}/official_finding/caveat`),
    },
    naapResult: {
      originSummary: nr.origin_summary,
      topSuspects: [...nr.top_suspects],
      abstained: nr.abstained,
    },
    assessment: {
      verdict: a.verdict,
      explanation: a.explanation,
      whatWouldHaveHelped: optionalString(
        a.what_would_have_helped,
        `${where}/assessment/what_would_have_helped`,
      ),
    },
  };
}
