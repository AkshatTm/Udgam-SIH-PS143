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

import type {
  RawDarkVessel,
  RawInfrastructure,
  RawExcludedVessel,
  RawFunnel,
  RawNaturalSeep,
  RawRepeatOffender,
  RawSuspect,
  RawSuspectComponents,
  RawSuspectsBundle,
  SourceType,
} from "./contracts";

export interface Funnel {
  inRegion: number;
  inWindow: number;
  plausible: number;
  scored: number;
  /** null when the bundle doesn't carry this field — never a fabricated 0. A side count
   *  (vessels dropped for <5 AIS reports), not a fifth narrowing stage. */
  droppedShortTrack: number | null;
}

/** Parsed per-component breakdown. Each field is `null` when the raw bundle omits it or sets
 *  it `null` — the two are treated identically ("not applicable"), never coerced to 0. */
export interface SuspectComponents {
  proximity: number | null;
  parity: number | null;
  temporality: number | null;
  trajectory: number | null;
  gap: number | null;
  slowdown: number | null;
  typePrior: number | null;
}

/** Cross-case vessel history (Master §6.7, docs/team/harshita-frontend.md Phase 3.7). `cases` are OTHER case ids this
 *  same vessel was also scored in — never dates, never incident descriptions, since none exist
 *  in the contract. Not validator-enforced; may never be populated by any real bundle. */
export interface RepeatOffender {
  cases: string[];
  bestRank: number;
}

export interface Suspect {
  mmsi: string;
  name: string;
  vesselType?: string;
  /** Master §4.5 — always `"vessel"` on a real suspect today; carried through, not assumed. */
  sourceType?: SourceType;
  score: number;
  /** null when the bundle carries no `components` breakdown at all (e.g. the v1 shape) —
   *  distinct from a present breakdown whose individual fields are null. */
  components: SuspectComponents | null;
  /** null when this suspect carries no repeat-offender record at all — never inferred from
   *  score, mmsi recurrence, or anything else computed client-side. */
  repeatOffender: RepeatOffender | null;
  closestKm: number;
  closestTime?: string;
  /** The origin grid's own probability at this suspect's closest-approach cell — distinct from
   *  `components.proximity`, which is a normalised score. Undefined when absent. */
  gridProbability?: number;
  headingConsistent?: boolean;
  aisGapMinutes?: number;
  /** D29 — why a component reads the way it does, keyed like `components`. Explanation, not
   *  evidence. Empty object when the bundle carries no notes. */
  componentNotes: Partial<Record<keyof SuspectComponents, string>>;
  /** D37 evidence breadth. Each `null` when the bundle omits it — never a guessed value. */
  weightLive: number | null;
  componentsAvailable: number | null;
  componentsTotal: number | null;
  /** Closest approach fell within one reporting interval of the search-box edge — `closestKm`
   *  may be understated. Surface it, don't hide it (contracts.ts). Undefined when absent. */
  edgeTruncated?: boolean;
  reasons: string[];
}

export interface ExcludedVessel {
  mmsi: string;
  name?: string;
  closestKm?: number;
  reason: string;
}

/** A radar contact with no AIS broadcast (Master §6.7). Deliberately has no `mmsi` field at
 *  all — one never exists for a dark vessel, so there is nothing to carry forward or render. */
export interface DarkVessel {
  name: string | null;
  lon: number;
  lat: number;
  estLengthM: number | null;
  score: number;
  angularDeviationDeg: number | null;
  reasons: string[];
}

/** A fixed, named facility scored against the origin (Master §6.7). Like `DarkVessel`, no
 *  `mmsi` — stationary infrastructure has no AIS identity either. Unlike `DarkVessel`, `name`
 *  is always present (validator-required). No distance/relevance field exists in the contract
 *  — only the raw position and the producer's own `reasons`. */
export interface Infrastructure {
  name: string;
  lon: number;
  lat: number;
  score: number;
  reasons: string[];
}

/** Master §6.7, D19 — geological seepage, the fourth source class. `flagged: true` is a
 *  citable claim, never a bare flag: `source`/`note` are guaranteed non-null whenever
 *  `flagged` is true (validated below), matching the validator's own `check_suspects` rule.
 *  This is contextual evidence about the *scene*, not a suspect — it is never added to
 *  `suspects` and carries no `score`/`mmsi`/rank. */
export interface NaturalSeep {
  flagged: boolean;
  source: string | null;
  note: string | null;
}

export interface SuspectsBundle {
  funnel: Funnel;
  /** Sorted by descending score, exactly as the file provides — never re-sorted here. */
  suspects: Suspect[];
  excluded: ExcludedVessel[];
  /** Always an array — absent-on-the-wire and present-but-empty both mean "no dark vessels for
   *  this case," which is the same thing to render (nothing). */
  darkVessels: DarkVessel[];
  /** Always an array, same convention as darkVessels. */
  infrastructure: Infrastructure[];
  /** `null` when the bundle carries no `natural_seep` block at all — distinct from a present
   *  block with `flagged: false`. Either way, nothing renders unless `flagged` is true. */
  naturalSeep: NaturalSeep | null;
  /** docs/team/harshita-frontend.md D2 — Stage 3 deliberately refused to attribute. When true, `suspects` is empty. */
  abstained: boolean;
  /** The case's stated reason for abstaining, exactly as supplied. `null` when not abstaining
   *  or when the bundle carries no reason. */
  abstainReason: string | null;
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
  if (f.dropped_short_track !== undefined) {
    if (!Number.isInteger(f.dropped_short_track) || f.dropped_short_track < 0) {
      throw new Error(
        `${where}.dropped_short_track must be a non-negative integer when present (got ${f.dropped_short_track})`,
      );
    }
  }
}

const COMPONENT_KEYS = [
  "proximity",
  "parity",
  "temporality",
  "trajectory",
  "gap",
  "slowdown",
  "type_prior",
] as const;

function validateComponents(c: RawSuspectComponents, where: string): void {
  if (!c || typeof c !== "object") {
    throw new Error(`${where}.components: must be an object when present`);
  }
  for (const k of COMPONENT_KEYS) {
    const v = c[k];
    if (v === undefined || v === null) continue;
    if (typeof v !== "number" || !Number.isFinite(v) || v < 0 || v > 1) {
      throw new Error(`${where}.components.${k} must be a finite number in [0, 1] or null (got ${v})`);
    }
  }
}

// The claim "repeat offender" only means something with actual supporting cases — an empty
// `cases` array would assert the label while citing zero evidence for it.
function validateRepeatOffender(ro: RawRepeatOffender, where: string): void {
  if (!ro || typeof ro !== "object") {
    throw new Error(`${where}.repeat_offender: must be an object when present`);
  }
  if (!Array.isArray(ro.cases) || ro.cases.length === 0) {
    throw new Error(`${where}.repeat_offender.cases: must be a non-empty array — a repeat-offender claim needs at least one other case as evidence`);
  }
  for (const c of ro.cases) {
    if (typeof c !== "string" || c.trim().length === 0) {
      throw new Error(`${where}.repeat_offender.cases: contains a non-string or empty case id`);
    }
  }
  if (!Number.isInteger(ro.best_rank) || ro.best_rank < 1) {
    throw new Error(`${where}.repeat_offender.best_rank: must be a positive integer (got ${ro.best_rank})`);
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
  if (s.components !== undefined) {
    validateComponents(s.components, where);
  }
  if (s.repeat_offender !== undefined) {
    validateRepeatOffender(s.repeat_offender, where);
  }
  if (s.component_notes !== undefined) {
    if (!s.component_notes || typeof s.component_notes !== "object" || Array.isArray(s.component_notes)) {
      throw new Error(`${where}: "component_notes" must be an object keyed by component name`);
    }
    for (const [k, v] of Object.entries(s.component_notes)) {
      if (typeof v !== "string" || v.trim().length === 0) {
        throw new Error(`${where}: "component_notes.${k}" must be a non-empty string`);
      }
    }
  }
  if (s.weight_live !== undefined) {
    if (typeof s.weight_live !== "number" || !Number.isFinite(s.weight_live) || s.weight_live < 0 || s.weight_live > 1) {
      throw new Error(`${where}: "weight_live" must be a finite number in [0, 1] (got ${s.weight_live})`);
    }
  }
  for (const k of ["components_available", "components_total"] as const) {
    const v = s[k];
    if (v !== undefined && (!Number.isInteger(v) || v < 0)) {
      throw new Error(`${where}: "${k}" must be a non-negative integer (got ${v})`);
    }
  }
  if (
    s.components_available !== undefined &&
    s.components_total !== undefined &&
    s.components_available > s.components_total
  ) {
    throw new Error(
      `${where}: components_available (${s.components_available}) exceeds components_total (${s.components_total})`,
    );
  }
  if (s.edge_truncated !== undefined && typeof s.edge_truncated !== "boolean") {
    throw new Error(`${where}: "edge_truncated" must be a boolean`);
  }
}

// Raw component keys → parsed SuspectComponents keys. Notes keyed by an unknown component are
// dropped here (the validator already errors on them), never rendered against a wrong bar.
const NOTE_KEY: Record<string, keyof SuspectComponents> = {
  proximity: "proximity",
  parity: "parity",
  temporality: "temporality",
  trajectory: "trajectory",
  gap: "gap",
  slowdown: "slowdown",
  type_prior: "typePrior",
};

function parseNotes(raw: Record<string, string> | undefined): Partial<Record<keyof SuspectComponents, string>> {
  const out: Partial<Record<keyof SuspectComponents, string>> = {};
  for (const [k, v] of Object.entries(raw ?? {})) {
    const key = NOTE_KEY[k];
    if (key) out[key] = v;
  }
  return out;
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

// Mirrors the lon/lat range + swap-guard already used in vessels.ts / loadCase.ts — never
// trust a coordinate pair without checking it, even on an optional field.
function validateDarkVessel(dv: RawDarkVessel, i: number, id: string): void {
  const where = `${id}/suspects.json/dark_vessels[${i}]`;
  if (typeof dv.lon !== "number" || !Number.isFinite(dv.lon) || dv.lon < -180 || dv.lon > 180) {
    throw new Error(`${where}: "lon" must be a finite number in [-180, 180]`);
  }
  if (typeof dv.lat !== "number" || !Number.isFinite(dv.lat) || dv.lat < -90 || dv.lat > 90) {
    throw new Error(`${where}: "lat" must be a finite number in [-90, 90]`);
  }
  if (typeof dv.score !== "number" || !Number.isFinite(dv.score) || dv.score < 0 || dv.score > 1) {
    throw new Error(`${where}: "score" must be a finite number in [0, 1]`);
  }
  // A dark vessel has no AIS identity by definition — the validator (check_dark_vessels)
  // rejects a non-null mmsi outright, and so does this loader.
  if (dv.mmsi !== undefined && dv.mmsi !== null) {
    throw new Error(`${where}: a dark vessel has no AIS identity — "mmsi" must be null or absent`);
  }
  if (dv.est_length_m !== undefined && (typeof dv.est_length_m !== "number" || !Number.isFinite(dv.est_length_m) || dv.est_length_m < 0)) {
    throw new Error(`${where}: "est_length_m" must be a non-negative finite number when present`);
  }
  if (
    dv.angular_deviation_deg !== undefined &&
    (typeof dv.angular_deviation_deg !== "number" || !Number.isFinite(dv.angular_deviation_deg))
  ) {
    throw new Error(`${where}: "angular_deviation_deg" must be a finite number when present`);
  }
  if (dv.reasons !== undefined) {
    if (!Array.isArray(dv.reasons)) {
      throw new Error(`${where}: "reasons" must be an array when present`);
    }
    for (const r of dv.reasons) {
      if (typeof r !== "string" || r.trim().length === 0) {
        throw new Error(`${where}: "reasons" contains an empty string`);
      }
    }
  }
}

function validateInfrastructure(inf: RawInfrastructure, i: number, id: string): void {
  const where = `${id}/suspects.json/infrastructure[${i}]`;
  if (typeof inf.name !== "string" || inf.name.trim().length === 0) {
    throw new Error(`${where}: "name" must be a non-empty string`);
  }
  if (typeof inf.lon !== "number" || !Number.isFinite(inf.lon) || inf.lon < -180 || inf.lon > 180) {
    throw new Error(`${where}: "lon" must be a finite number in [-180, 180]`);
  }
  if (typeof inf.lat !== "number" || !Number.isFinite(inf.lat) || inf.lat < -90 || inf.lat > 90) {
    throw new Error(`${where}: "lat" must be a finite number in [-90, 90]`);
  }
  if (typeof inf.score !== "number" || !Number.isFinite(inf.score) || inf.score < 0 || inf.score > 1) {
    throw new Error(`${where}: "score" must be a finite number in [0, 1]`);
  }
  if (inf.reasons !== undefined) {
    if (!Array.isArray(inf.reasons)) {
      throw new Error(`${where}: "reasons" must be an array when present`);
    }
    for (const r of inf.reasons) {
      if (typeof r !== "string" || r.trim().length === 0) {
        throw new Error(`${where}: "reasons" contains an empty string`);
      }
    }
  }
}

// Mirrors validate_case.py's check_suspects natural_seep rule exactly: a flag raised without
// a named source is the same unsubstantiated claim Mumbai's own meta.json warns against — a
// citable seep claim needs both source and note, never a bare boolean.
function validateNaturalSeep(ns: RawNaturalSeep, id: string): void {
  const where = `${id}/suspects.json/natural_seep`;
  if (!ns || typeof ns !== "object") {
    throw new Error(`${where}: must be an object when present`);
  }
  if (typeof ns.flagged !== "boolean") {
    throw new Error(`${where}.flagged: must be true or false`);
  }
  if (ns.flagged) {
    if (typeof ns.source !== "string" || ns.source.trim().length === 0) {
      throw new Error(`${where}.source: required non-empty string when flagged is true`);
    }
    if (typeof ns.note !== "string" || ns.note.trim().length === 0) {
      throw new Error(`${where}.note: required non-empty string when flagged is true`);
    }
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
  if (raw.dark_vessels !== undefined && !Array.isArray(raw.dark_vessels)) {
    throw new Error(`${where}: "dark_vessels" must be an array when present`);
  }
  (raw.dark_vessels ?? []).forEach((dv, i) => validateDarkVessel(dv, i, id));
  if (raw.infrastructure !== undefined && !Array.isArray(raw.infrastructure)) {
    throw new Error(`${where}: "infrastructure" must be an array when present`);
  }
  (raw.infrastructure ?? []).forEach((inf, i) => validateInfrastructure(inf, i, id));
  if (raw.natural_seep !== undefined) {
    validateNaturalSeep(raw.natural_seep, id);
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
  // An empty `excluded` on a scored case is a validator WARN, not an ERR (Master §6.7 does not
  // require one), so it must not become a contract-error card here: Jacksonville and Farallones
  // both PASS with none. The Excluded section renders its "No vessels excluded." state instead,
  // and the missing exclusions are a producer follow-up, not something to hide or invent.

  // Abstention (docs/team/harshita-frontend.md D2, CONTRACTS §8). Optional fields, but a malformed one is a contract
  // bug — surfaced, never coerced or guessed around.
  if ("abstained" in raw && typeof raw.abstained !== "boolean") {
    throw new Error(`${where}: "abstained" must be a boolean when present`);
  }
  const abstained = raw.abstained === true;
  if (
    "abstain_reason" in raw &&
    raw.abstain_reason !== null &&
    typeof raw.abstain_reason !== "string"
  ) {
    throw new Error(`${where}: "abstain_reason" must be a string or null when present`);
  }
  const abstainReason =
    typeof raw.abstain_reason === "string" && raw.abstain_reason.trim().length > 0
      ? raw.abstain_reason
      : null;
  if (abstained && raw.suspects.length > 0) {
    throw new Error(
      `${where}: "abstained" is true but ${raw.suspects.length} suspect(s) are listed — an abstaining bundle names none`,
    );
  }

  return {
    funnel: {
      inRegion: raw.funnel.in_region,
      inWindow: raw.funnel.in_window,
      plausible: raw.funnel.plausible,
      scored: raw.funnel.scored,
      droppedShortTrack:
        raw.funnel.dropped_short_track !== undefined ? raw.funnel.dropped_short_track : null,
    },
    suspects: raw.suspects.map((s) => ({
      mmsi: s.mmsi,
      name: s.name,
      vesselType: s.vessel_type,
      sourceType: s.source_type,
      score: s.score,
      components: s.components
        ? {
            proximity: s.components.proximity ?? null,
            parity: s.components.parity ?? null,
            temporality: s.components.temporality ?? null,
            trajectory: s.components.trajectory ?? null,
            gap: s.components.gap ?? null,
            slowdown: s.components.slowdown ?? null,
            typePrior: s.components.type_prior ?? null,
          }
        : null,
      repeatOffender: s.repeat_offender
        ? { cases: s.repeat_offender.cases, bestRank: s.repeat_offender.best_rank }
        : null,
      closestKm: s.closest_km,
      closestTime: s.closest_time,
      gridProbability: s.grid_probability,
      headingConsistent: s.heading_consistent,
      aisGapMinutes: s.ais_gap_minutes,
      componentNotes: parseNotes(s.component_notes),
      weightLive: s.weight_live ?? null,
      componentsAvailable: s.components_available ?? null,
      componentsTotal: s.components_total ?? null,
      edgeTruncated: s.edge_truncated,
      reasons: s.reasons,
    })),
    excluded: raw.excluded.map((e) => ({
      mmsi: e.mmsi,
      name: e.name,
      closestKm: e.closest_km,
      reason: e.reason,
    })),
    darkVessels: (raw.dark_vessels ?? []).map((dv) => ({
      name: dv.name ?? null,
      lon: dv.lon,
      lat: dv.lat,
      estLengthM: dv.est_length_m ?? null,
      score: dv.score,
      angularDeviationDeg: dv.angular_deviation_deg ?? null,
      reasons: dv.reasons ?? [],
    })),
    infrastructure: (raw.infrastructure ?? []).map((inf) => ({
      name: inf.name,
      lon: inf.lon,
      lat: inf.lat,
      score: inf.score,
      reasons: inf.reasons ?? [],
    })),
    naturalSeep: raw.natural_seep
      ? {
          flagged: raw.natural_seep.flagged,
          source: raw.natural_seep.source ?? null,
          note: raw.natural_seep.note ?? null,
        }
      : null,
    abstained,
    abstainReason,
  };
}
