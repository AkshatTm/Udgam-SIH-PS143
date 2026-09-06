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

/** The three stages, in fixed rail order. */
export const ALL_ACTS: Act[] = ["detect", "trace", "attribute"];

export const ACT_LABELS: Record<Act, string> = {
  detect: "Detect",
  trace: "Trace",
  attribute: "Attribute",
};
