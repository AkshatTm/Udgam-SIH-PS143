// Phase 1 bundle loader. Fetches static JSON from /cases/<id>/ only — never calls Python.
// On a missing or malformed file it throws a descriptive Error; the shell surfaces that as a
// visible banner. It must NOT silently patch data — a bad field is a contract bug for Akshat.

import type { Bounds, CaseMeta, DetectionCollection } from "./contracts";
import { ALL_ACTS } from "./contracts";

export interface LoadedCase {
  meta: CaseMeta;
  bounds: Bounds;
  detections: DetectionCollection;
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

function validateMeta(meta: CaseMeta, id: string): void {
  if (!meta || typeof meta.title !== "string") {
    throw new Error(`${id}/meta.json: missing "title"`);
  }
  if (typeof meta.detection_time !== "string" || !meta.detection_time.endsWith("Z")) {
    throw new Error(`${id}/meta.json: "detection_time" must be UTC ISO 8601 with trailing Z`);
  }
  if (!Array.isArray(meta.acts_available) || meta.acts_available.length === 0) {
    throw new Error(`${id}/meta.json: "acts_available" must be a non-empty array`);
  }
  const unknown = meta.acts_available.filter((a) => !ALL_ACTS.includes(a));
  if (unknown.length > 0) {
    throw new Error(`${id}/meta.json: unknown act(s) ${unknown.join(", ")}`);
  }
}

function validateBounds(b: Bounds, id: string): void {
  for (const k of ["west", "south", "east", "north"] as const) {
    if (typeof b[k] !== "number") {
      throw new Error(`${id}/bounds.json: missing numeric "${k}"`);
    }
  }
  if (!(b.west < b.east)) {
    throw new Error(`${id}/bounds.json: west must be < east`);
  }
  if (!(b.south < b.north)) {
    throw new Error(`${id}/bounds.json: south must be < north`);
  }
  if (b.west < -180 || b.east > 180) {
    throw new Error(`${id}/bounds.json: longitudes must be in -180..180 (never 0..360)`);
  }
}

function validateDetections(d: DetectionCollection, id: string): void {
  if (!d || d.type !== "FeatureCollection" || !Array.isArray(d.features)) {
    throw new Error(`${id}/detections.geojson: not a FeatureCollection with a features array`);
  }
  for (const f of d.features) {
    const p = f?.properties;
    if (!p || typeof p.id !== "string") {
      throw new Error(`${id}/detections.geojson: a feature is missing properties.id`);
    }
    if (p.classification !== "oil" && p.classification !== "lookalike") {
      throw new Error(
        `${id}/detections.geojson: ${p.id} has classification "${p.classification}" (expected oil|lookalike)`,
      );
    }
  }
}

export async function loadCase(id: string): Promise<LoadedCase> {
  const base = `/cases/${id}`;
  const [meta, bounds, detections] = await Promise.all([
    fetchJson<CaseMeta>(`${base}/meta.json`),
    fetchJson<Bounds>(`${base}/bounds.json`),
    fetchJson<DetectionCollection>(`${base}/detections.geojson`),
  ]);

  validateMeta(meta, id);
  validateBounds(bounds, id);
  validateDetections(detections, id);

  return { meta, bounds, detections };
}
