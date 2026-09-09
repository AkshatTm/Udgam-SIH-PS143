// Phase 5 suspects-bundle loader. Fetches /cases/<id>/suspects.json ONCE and validates it
// against CONTRACTS.md §8 — including the invariants the contract states explicitly (funnel
// counts non-increasing, `scored === suspects.length`, descending score order, every exclusion
// carries a non-empty reason). This mirrors the same defensive-validation discipline as
// origin.ts / particles.ts: a violation is a contract bug for Jaiveer/Akshat, surfaced as a
// visible error, never patched or re-sorted client-side.
//
// This file does NOT decide whether `origin.abstain` should suppress the suspect list — that
// is a cross-file, presentation-time decision made in the UI (ContextPanel), not a parsing
// concern here. This loader only asserts that suspects.json is internally well-formed.

import type { RawExcludedVessel, RawFunnel, RawSuspect, RawSuspectsBundle } from "./contracts";

export interface Funnel {
  inRegion: number;
  inWindow: number;
  plausible: number;
  scored: number;
}

export interface Suspect {
  mmsi: string;
  name: string;
  vesselType?: string;
  score: number;
  closestKm: number;
  closestTime?: string;
  headingConsistent?: boolean;
  aisGapMinutes?: number;
  reasons: string[];
}

export interface ExcludedVessel {
  mmsi: string;
  name?: string;
  closestKm?: number;
  reason: string;
}

export interface SuspectsBundle {
  funnel: Funnel;
  /** Sorted by descending score, exactly as the file provides — never re-sorted here. */
  suspects: Suspect[];
  excluded: ExcludedVessel[];
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

function validateFunnel(f: RawFunnel, id: string): void {
  const where = `${id}/suspects.json/funnel`;
  if (!f || typeof f !== "object") {
    throw new Error(`${where}: missing`);
  }
  for (const k of ["in_region", "in_window", "plausible", "scored"] as const) {
    if (!Number.isInteger(f[k]) || f[k] < 0) {
      throw new Error(`${where}.${k} must be a non-negative integer (got ${f[k]})`);
    }
  }
  const seq = [f.in_region, f.in_window, f.plausible, f.scored];
  for (let i = 1; i < seq.length; i++) {
    if (seq[i] > seq[i - 1]) {
      throw new Error(`${where}: counts must never increase down the funnel — got [${seq.join(", ")}]`);
    }
  }
}

function validateSuspect(s: RawSuspect, i: number, id: string): void {
  const where = `${id}/suspects.json/suspects[${i}]`;
  if (typeof s.mmsi !== "string" || s.mmsi.length === 0) {
    throw new Error(`${where}: "mmsi" must be a non-empty string`);
  }
  if (typeof s.name !== "string" || s.name.length === 0) {
    throw new Error(`${where}: "name" must be a non-empty string`);
  }
  if (typeof s.score !== "number" || !Number.isFinite(s.score) || s.score < 0 || s.score > 1) {
    throw new Error(`${where}: "score" ${s.score} must be a finite number in [0, 1]`);
  }
  if (typeof s.closest_km !== "number" || !Number.isFinite(s.closest_km) || s.closest_km < 0) {
    throw new Error(`${where}: "closest_km" must be a non-negative finite number`);
  }
  if (!Array.isArray(s.reasons) || s.reasons.length === 0) {
    throw new Error(`${where}: "reasons" must be a non-empty array — a judge-facing suspect needs a stated reason`);
  }
  for (const r of s.reasons) {
    if (typeof r !== "string" || r.trim().length === 0) {
      throw new Error(`${where}: "reasons" contains an empty string`);
    }
  }
  if (s.closest_time !== undefined) {
    if (typeof s.closest_time !== "string" || !s.closest_time.endsWith("Z")) {
      throw new Error(`${where}: "closest_time" must be UTC ISO 8601 with a trailing Z`);
    }
    if (!Number.isFinite(Date.parse(s.closest_time))) {
      throw new Error(`${where}: "closest_time" is not a parseable timestamp`);
    }
  }
  if (s.ais_gap_minutes !== undefined) {
    if (typeof s.ais_gap_minutes !== "number" || !Number.isFinite(s.ais_gap_minutes) || s.ais_gap_minutes < 0) {
      throw new Error(`${where}: "ais_gap_minutes" must be a non-negative finite number`);
    }
  }
  if (s.heading_consistent !== undefined && typeof s.heading_consistent !== "boolean") {
    throw new Error(`${where}: "heading_consistent" must be a boolean`);
  }
}

function validateExcluded(e: RawExcludedVessel, i: number, id: string): void {
  const where = `${id}/suspects.json/excluded[${i}]`;
  if (typeof e.mmsi !== "string" || e.mmsi.length === 0) {
    throw new Error(`${where}: "mmsi" must be a non-empty string`);
  }
  if (typeof e.reason !== "string" || e.reason.trim().length === 0) {
    throw new Error(
      `${where}: "reason" must be non-empty — exoneration without a reason is worse than no exoneration`,
    );
  }
  if (e.closest_km !== undefined && (typeof e.closest_km !== "number" || !Number.isFinite(e.closest_km))) {
    throw new Error(`${where}: "closest_km" must be a finite number when present`);
  }
}

export async function loadSuspectsBundle(id: string): Promise<SuspectsBundle> {
  const raw = await fetchJson<RawSuspectsBundle>(`/cases/${id}/suspects.json`);
  const where = `${id}/suspects.json`;
  if (!raw || typeof raw !== "object") {
    throw new Error(`${where}: not an object`);
  }
  if (!Array.isArray(raw.suspects)) {
    throw new Error(`${where}: "suspects" must be an array`);
  }
  if (!Array.isArray(raw.excluded)) {
    throw new Error(`${where}: "excluded" must be an array`);
  }

  validateFunnel(raw.funnel, id);
  if (raw.funnel.scored !== raw.suspects.length) {
    throw new Error(
      `${where}: funnel.scored is ${raw.funnel.scored} but ${raw.suspects.length} suspects are listed`,
    );
  }

  raw.suspects.forEach((s, i) => validateSuspect(s, i, id));
  for (let i = 1; i < raw.suspects.length; i++) {
    if (raw.suspects[i].score > raw.suspects[i - 1].score) {
      throw new Error(`${where}: "suspects" must be sorted by descending score`);
    }
  }

  raw.excluded.forEach((e, i) => validateExcluded(e, i, id));
  if (raw.excluded.length === 0) {
    throw new Error(`${where}: "excluded" is empty — at least one exclusion with a stated reason is required`);
  }

  return {
    funnel: {
      inRegion: raw.funnel.in_region,
      inWindow: raw.funnel.in_window,
      plausible: raw.funnel.plausible,
      scored: raw.funnel.scored,
    },
    suspects: raw.suspects.map((s) => ({
      mmsi: s.mmsi,
      name: s.name,
      vesselType: s.vessel_type,
      score: s.score,
      closestKm: s.closest_km,
      closestTime: s.closest_time,
      headingConsistent: s.heading_consistent,
      aisGapMinutes: s.ais_gap_minutes,
      reasons: s.reasons,
    })),
    excluded: raw.excluded.map((e) => ({
      mmsi: e.mmsi,
      name: e.name,
      closestKm: e.closest_km,
      reason: e.reason,
    })),
  };
}
