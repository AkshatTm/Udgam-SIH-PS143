// Types mirroring docs/CONTRACTS.md. The contract file, not the sample bundle, is the
// source of truth for what a field means. Coordinates are always [longitude, latitude].

export type Act = "detect" | "trace" | "attribute" | "verify";

export type LonLat = [number, number];

export interface CaseMeta {
  case_id: string;
  title: string;
  satellite: string;
  scene_id: string;
  detection_time: string; // UTC ISO 8601, trailing Z
  acts_available: Act[];
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
}

export type Classification = "oil" | "lookalike";
export type ShapeClass = "linear" | "blob";

export interface DetectionProperties {
  id: string;
  classification: Classification;
  confidence: number; // [0, 1]
  area_km2: number; // > 0
  elongation: number; // >= 1
  edge_gradient: number;
  contrast_db: number; // negative for a dark spot
  shape_class: ShapeClass;
  centroid: LonLat;
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
  direction: string; // "backward"
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
  ensemble_runs: number;
  abstain: boolean;
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
}

export interface RawSuspect {
  mmsi: string;
  name: string;
  vessel_type?: string;
  score: number; // [0, 1]
  closest_km: number;
  closest_time?: string; // UTC ISO 8601, trailing Z
  heading_consistent?: boolean;
  ais_gap_minutes?: number;
  reasons: string[];
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
  excluded: RawExcludedVessel[];
}

/** The four in-case stages, in fixed flow order (Gallery is a route of its own). */
export const ALL_ACTS: Act[] = ["detect", "trace", "attribute", "verify"];

export const ACT_LABELS: Record<Act, string> = {
  detect: "Detect",
  trace: "Trace",
  attribute: "Attribute",
  verify: "Verify",
};
