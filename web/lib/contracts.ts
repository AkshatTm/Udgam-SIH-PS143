// Types mirroring docs/CONTRACTS.md. The contract file, not the sample bundle, is the
// source of truth for what a field means. Coordinates are always [longitude, latitude].

export type Act = "detect" | "trace" | "attribute";

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

/** The three stages, in fixed rail order. */
export const ALL_ACTS: Act[] = ["detect", "trace", "attribute"];

export const ACT_LABELS: Record<Act, string> = {
  detect: "Detect",
  trace: "Trace",
  attribute: "Attribute",
};
