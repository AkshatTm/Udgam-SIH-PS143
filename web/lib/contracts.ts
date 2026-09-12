// Types mirroring the frozen contract. SOURCE OF TRUTH: docs/00_MASTER_PLAN.md Part 6
// (§6.1–6.9); docs/CONTRACTS.md is a mirror of it. The contract, not the sample bundle, is
// what a field means. Coordinates are always [longitude, latitude].
//
// `null` NEVER means zero. A null score is "not applicable" and renders "n/a" — never a zero
// bar. Rendering one as the other is an honesty bug, not a styling choice (Master §5.7, D20).

export type Act = "detect" | "trace" | "attribute" | "verify";

export type LonLat = [number, number];

export type CaseType = "spill" | "lookalike" | "nospill";
export type Difficulty = "easy" | "medium" | "hard";

/**
 * Which AIS archive a case was attributed with, and therefore which scoring components could
 * fire at all (D20). `noaa_dense` reports every ~71 s; `gfw_hourly` gives ONE position per
 * vessel per hour — about 50× sparser — so `gap` is structurally impossible there and
 * `slowdown` is very coarse. Both come back null on such a case, and the card says "n/a".
 */
export type AisSource = "noaa_dense" | "gfw_hourly";

/** A documented fixed source the trace stage seeds from when there is no SAR-visible slick
 *  (D16). When present the Trace screen must say the origin was SEEDED FROM A DOCUMENTED
 *  SOURCE, never presented as a NAAP detection. No case in the current library uses it. Only
 *  the label is used on the Verify screen (P1.1). */
export type KnownOrigin =
  | LonLat
  | { lon: number; lat: number; label?: string; source_url?: string };

export interface CaseGallery {
  thumbnail?: string;
  blurb?: string;
  difficulty?: Difficulty;
}

export interface CaseMeta {
  case_id: string;
  title: string;
  short_location?: string;
  case_type?: CaseType;
  satellite: string;
  scene_id: string;
  detection_time: string; // UTC ISO 8601, trailing Z
  acts_available: Act[];
  ais_source?: AisSource; // required whenever `attribute` is available
  known_origin?: KnownOrigin; // optional, D16 — already flows through loadCase untouched
  gallery?: CaseGallery;
  notes?: string;
}

/** A bare geographic extent, WGS84 / EPSG:4326. `west < east`, `south < north`. */
export interface GeoBounds {
  west: number;
  south: number;
  east: number;
  north: number;
}

export interface Bounds {
  west: number;
  south: number;
  east: number;
  north: number;
  width_px: number;
  height_px: number;
  db_min?: number; // optional, defaults to -25
  db_max?: number; // optional, defaults to 0
  /** Whether sar_vv_vh.tif carries a second (VH) band. Display only cares in captions. */
  vh_available?: boolean;
}

export type Classification = "oil" | "lookalike";
export type ShapeClass = "linear" | "blob";
export type DischargeClass = "chronic" | "acute" | "unknown";

/** Master §6.3, docs/04 Phase 5.3 — a raw radar ship contact near a detection (Soum's output).
 *  `px_area`/`peak_db` are documented but not currently rendered by the frontend — only
 *  position is used for the map marker, same "documented, optional, not all consumed" treatment
 *  as `vessels.geojson`'s `n_points`/`max_gap_minutes`. */
export interface ShipDetection {
  lon: number;
  lat: number;
  px_area?: number;
  peak_db?: number;
}

export interface DetectionProperties {
  id: string;
  classification: Classification;
  confidence: number; // [0, 1]
  area_km2: number; // > 0
  elongation: number; // >= 1
  edge_gradient: number;
  contrast_db: number; // negative for a dark spot
  shape_class: ShapeClass;
  /** Master §6.3, docs/04 Phase 5.3 — Soum's chronic/acute/unknown classification, feeding
   *  Anushka's line-vs-point origin seeding on the producer side. Optional; absent hides the
   *  badge — never inferred from geometry on the frontend. */
  discharge_class?: DischargeClass;
  centroid: LonLat;
  /** Master §6.3, docs/04 Phase 5.3 — raw radar ship contacts near this detection (Soum's
   *  output). May be `[]` — valid and common. NOT suspects.json's `dark_vessels` (Jaiveer's
   *  already AIS-cross-checked subset) — this is the unfiltered candidate set, rendered as its
   *  own independent map layer. */
  ship_detections?: ShipDetection[];
}

export interface DetectionFeature {
  type: "Feature";
  geometry: { type: "Polygon"; coordinates: LonLat[][] };
  properties: DetectionProperties;
}

export interface DetectionCollection {
  type: "FeatureCollection";
  features: DetectionFeature[];
}

/**
 * particles.json exactly as it sits on disk (CONTRACTS.md §5). Stage 2 → frontend only.
 * `positions` is [n_steps][n_particles][lon, lat]; positions[0] is on the slick at `t0`,
 * positions[n_steps-1] is at `t0 − 24 h`. The frontend converts this to typed arrays once
 * (see lib/particles.ts) — this raw shape is never held in state.
 */
export interface RawParticleBundle {
  t0: string; // UTC ISO 8601, trailing Z — equals meta.detection_time within 60 s
  /** "backward" in particles.json, "forward" in particles_forward.json — a SEPARATE file,
   *  never an overwrite of the first (Master §6.4). */
  direction: "backward" | "forward";
  timestep_minutes: number;
  n_steps: number;
  n_particles: number;
  positions: LonLat[][];
}

/**
 * origin.json exactly as it sits on disk (CONTRACTS.md §6). Stage 2 → Stage 3, and → frontend.
 * `values` is the flattened probability grid, row-major from the top-left (row 0 = NORTH edge),
 * normalised so the peak is 1.0 and never negative. The frontend converts it to a Float32Array
 * once (see lib/origin.ts) — this raw shape is never held in state.
 */
export interface RawOriginBundle {
  bounds: GeoBounds;
  shape: number[]; // [rows, cols]
  values: number[]; // length rows * cols
  centroid: LonLat; // [lon, lat]
  radius_50_km: number;
  radius_90_km: number;
  time_window: string[]; // [start, end] — UTC ISO 8601, trailing Z
  /** "bounded" is a SEARCH BRACKET, not a measured release time. The two must not be
   *  rendered the same way — that is the entire reason this field is in the contract (D12). */
  time_window_method?: "bounded" | "convergence";
  ensemble_runs: number;
  abstain: boolean;

  // Optional blocks. Absence hides a UI row; it must never throw (Master §6.5).
  age_hours?: [number, number];
  age_method?: "shear" | "fay" | "elongation" | "combined" | "disagreement" | "none";
  age_weathering?: "fresh" | "weathered" | "unknown";
  /** Per-estimator band, or null where that estimator did not apply — never a zero band. */
  age_estimators?: Record<string, [number, number] | null>;
  stranded_fraction?: number;
  opendrift_comparison?: { centroid_separation_km: number; r90_ratio: number };
}

/**
 * vessels.geojson exactly as it sits on disk (CONTRACTS.md §7). Stage 3 → frontend.
 * `n_points` / `max_gap_minutes` are documented but not enforced by validate_case.py — treated
 * as optional here so a producer that omits them doesn't break the frontend.
 */
export interface RawVesselProperties {
  mmsi: string;
  name: string;
  vessel_type: string;
  n_points?: number;
  max_gap_minutes?: number;
}

export interface RawVesselFeature {
  type: "Feature";
  geometry: { type: "LineString"; coordinates: LonLat[] };
  properties: RawVesselProperties;
}

export interface RawVesselCollection {
  type: "FeatureCollection";
  features: RawVesselFeature[];
}

/**
 * suspects.json exactly as it sits on disk (CONTRACTS.md §8). Stage 3 → frontend.
 * Only `mmsi/name/score/closest_km/reasons` (suspects) and `mmsi/reason` (excluded) are
 * enforced by validate_case.py — everything else is "where available" per the contract's own
 * example, so it is optional here. The frontend never fills in a missing field with a guess.
 */
export interface RawFunnel {
  in_region: number;
  in_window: number;
  plausible: number;
  scored: number;
  /** Optional (Master §6.7, absent from the v1/CONTRACTS.md shape) — vessels excluded before
   *  scoring for having fewer than 5 AIS position reports. Not part of the narrowing sequence
   *  above; a side count, not a fifth stage. */
  dropped_short_track?: number;
}

/** Before naming a ship we ask whether a ship is even the right kind of answer (Master §4.5). */
export type SourceType = "vessel" | "dark_vessel" | "infrastructure" | "natural_seep";

/**
 * Master §6.7 — the per-component score breakdown behind a suspect's overall `score`. Each
 * key is optional/nullable: absent or `null` both mean "not applicable for this vessel/case"
 * (e.g. `gap`/`slowdown` on a gfw_hourly case) — never a fabricated 0. Values, when present,
 * are in [0, 1] like `score`. Gated to null by: `gap`/`slowdown` on a gfw_hourly case or a
 * vessel that was not under way (D9, D20); `trajectory` when the vessel was never seen outside
 * radius_90_km (D27); `type_prior` when every candidate shares a type class (D28). The index
 * signature lets a producer add a new component without a contract break.
 */
export interface RawSuspectComponents {
  proximity?: number | null;
  parity?: number | null;
  temporality?: number | null;
  trajectory?: number | null;
  gap?: number | null;
  slowdown?: number | null;
  type_prior?: number | null;
  [component: string]: number | null | undefined;
}

/** Master §6.7, `06_JAIVEER_AIS.md:374-379` — cross-case vessel history. `cases` are OTHER
 *  case ids where this same vessel was also scored; `best_rank` is its best (lowest) rank
 *  across those. Not validator-enforced anywhere (unlike dark_vessels/infrastructure) — this
 *  is a documented-but-unvalidated shape, same category as `dropped_short_track`. Jaiveer's own
 *  doc calls this "a flag to investigate, never as corroboration" — never overclaim it. */
export interface RawRepeatOffender {
  cases: string[];
  best_rank: number;
}

export interface RawSuspect {
  source_type?: SourceType;
  mmsi: string;
  name: string;
  vessel_type?: string;
  score: number; // [0, 1]
  components?: RawSuspectComponents;
  /** Why a component reads the way it does — keyed by component name. Explanation, not
   *  evidence: it never adds a fact the card is not already showing. Render it wherever a
   *  bar is "n/a", because an unexplained "n/a" reads as a broken feature (D29). */
  component_notes?: Record<string, string>;
  repeat_offender?: RawRepeatOffender;
  closest_km: number;
  closest_time?: string; // UTC ISO 8601, trailing Z
  grid_probability?: number;
  heading_consistent?: boolean;
  ais_gap_minutes?: number;
  /** Closest approach happened within one reporting interval of the search-box edge, so the
   *  track is cut off and closest_km may be understated. Surface it, don't hide it. */
  edge_truncated?: boolean;
  reasons: string[];
}

/** Master §6.7, validator `check_dark_vessels` — a radar contact with NO corresponding AIS
 *  broadcast. `mmsi` is always null/absent by definition (no AIS = no identity) and the
 *  validator rejects a non-null value outright. Only `lon`/`lat`/`score` are required. */
export interface RawDarkVessel {
  source_type?: "dark_vessel";
  mmsi?: null;
  name?: string;
  lon: number;
  lat: number;
  est_length_m?: number;
  score: number; // [0, 1]
  angular_deviation_deg?: number;
  reasons?: string[];
}

/** Master §6.7, validator (`suspects.json/infrastructure[i]`) — a fixed, named facility (pipeline,
 *  platform, wreck) scored against the origin. No `mmsi` (stationary, no AIS identity). Unlike
 *  `RawDarkVessel`, `name` is required — the validator's `need_keys` demands it. There is no
 *  `distance`/`facility_type`/`relevance` field anywhere in the contract; only `reasons[]`
 *  (producer prose) explains the finding. */
export interface RawInfrastructure {
  source_type?: "infrastructure";
  name: string;
  lon: number;
  lat: number;
  score: number; // [0, 1]
  reasons?: string[];
}

/** Geological seepage — oil nobody spilled (D19). `flagged: true` requires a citable `source`;
 *  a bare flag does not go on screen. Not claimed on any case in the current library. */
export interface RawNaturalSeep {
  flagged: boolean;
  source?: string;
  note?: string;
}

export interface RawExcludedVessel {
  mmsi: string;
  name?: string;
  closest_km?: number;
  reason: string;
}

export interface RawSuspectsBundle {
  funnel: RawFunnel;
  suspects: RawSuspect[];
  /** Optional (Master §6.7, absent from the v1/CONTRACTS.md shape) — radar contacts with no
   *  AIS. Absent entirely on every fixture that currently exists. */
  dark_vessels?: RawDarkVessel[];
  /** Optional (Master §6.7) — fixed infrastructure findings. Absent on every current fixture. */
  infrastructure?: RawInfrastructure[];
  natural_seep?: RawNaturalSeep;
  excluded: RawExcludedVessel[];
  /** §6.7 — Stage 3's deliberate refusal to attribute (docs/04 D2). `true` ⇒ `suspects` empty,
   *  a feature not a failure — the screen says why. */
  abstained?: boolean;
  /** The human "why" for the abstention. `null` / absent when not abstaining. */
  abstain_reason?: string | null;
}

/**
 * verification.json exactly as it sits on disk (docs/00_MASTER_PLAN.md §6.8, validator
 * `check_verification`). Stage 4 is hand-authored research prose, not a pipeline output — the
 * frontend renders it verbatim and NEVER generates or edits the `explanation`. Unknown keys
 * (e.g. a scaffold's `_status`) are ignored, never rejected. A `miss` is styled as confidently
 * as a `hit` — see `VerdictBadge`.
 */
export type Verdict = "hit" | "partial" | "miss" | "not_applicable";

export interface RawResponsibleParty {
  name: string;
  mmsi: string | null; // null is valid and expected — never an invented identity
  imo?: string | null;
  role?: string;
}

export interface RawOfficialFinding {
  summary: string;
  responsible_parties: RawResponsibleParty[];
  source_name: string;
  source_url: string; // required, non-empty; scheme-checked before it ever becomes an href
  source_type: string;
  volume_reported?: string;
  caveat?: string;
}

export interface RawNaapResult {
  origin_summary: string;
  top_suspects: string[]; // MMSI strings, may be empty; rendered as provided (no cross-bundle enrichment)
  abstained: boolean;
}

export interface RawAssessment {
  verdict: Verdict;
  explanation: string; // required, non-empty, human-written
  what_would_have_helped?: string;
}

export interface RawVerification {
  official_finding: RawOfficialFinding;
  naap_result: RawNaapResult;
  assessment: RawAssessment;
}

/** The four in-case stages, in fixed flow order (Gallery is a route of its own). */
export const ALL_ACTS: Act[] = ["detect", "trace", "attribute", "verify"];

export const ACT_LABELS: Record<Act, string> = {
  detect: "Detect",
  trace: "Trace",
  attribute: "Attribute",
  verify: "Verify",
};
