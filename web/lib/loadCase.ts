// Phase 1 bundle loader. Fetches static JSON from /cases/<id>/ only — never calls Python.
// On a missing or malformed file it throws a descriptive Error; the shell surfaces that as a
// visible banner. It must NOT silently patch data — a bad field is a contract bug for Akshat.

import type { Bounds, CaseMeta, DetectionCollection } from "./contracts";
import { ALL_ACTS } from "./contracts";

export interface LoadedCase {
  meta: CaseMeta;
  bounds: Bounds;
  /** null when Stage 1 has not produced detections for this case yet, OR when the case has no
   *  `detect` act at all (D16 known-origin cases run trace/attribute/verify from a documented
   *  source with no SAR-visible slick, so there is no detections.geojson to fetch). */
  detections: DetectionCollection | null;
  /** true when the case offers `detect` but detections.geojson is not on disk yet. */
  detectionsPending: boolean;
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

/**
 * Fetch a stage output that may not exist yet.
 *
 * MISSING IS NOT BROKEN, and the difference is the whole point of this function. A bundle is
 * assembled one stage at a time: the scene lands first and detections arrive when Soum's stage
 * runs. A 404 therefore means "not produced yet" and must degrade to null, so the rest of the
 * team can open a case and look at the SAR scene while Stage 1 is still being written.
 *
 * Anything else still throws. Malformed JSON is a contract bug and has to stay loud — this is
 * NOT a general-purpose "swallow the error" helper, and it must not become one.
 */
async function fetchJsonIfPresent<T>(url: string): Promise<T | null> {
  let res: Response;
  try {
    res = await fetch(url, { cache: "no-store" });
  } catch (err) {
    throw new Error(`Could not fetch ${url}: ${(err as Error).message}`);
  }
  if (res.status === 404) return null;
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

const DISCHARGE_CLASSES = ["chronic", "acute", "unknown"];

/** ship_detections — may be []. Same lon/lat swap-guard used everywhere else in this app, even on
 *  an optional field. Applied to the top-level list (Master §6.3, D34) and to the deprecated
 *  per-feature copy older bundles still carry. */
function validateShipDetections(ships: unknown, where: string): void {
  if (ships === undefined) return;
  if (!Array.isArray(ships)) {
    throw new Error(`${where} must be an array when present`);
  }
  ships.forEach((sd, i) => {
    if (typeof sd?.lon !== "number" || !Number.isFinite(sd.lon) || sd.lon < -180 || sd.lon > 180) {
      throw new Error(`${where}[${i}].lon must be a finite number in [-180, 180]`);
    }
    if (typeof sd?.lat !== "number" || !Number.isFinite(sd.lat) || sd.lat < -90 || sd.lat > 90) {
      throw new Error(`${where}[${i}].lat must be a finite number in [-90, 90]`);
    }
  });
}

function validateDetections(d: DetectionCollection, id: string): void {
  if (!d || d.type !== "FeatureCollection" || !Array.isArray(d.features)) {
    throw new Error(`${id}/detections.geojson: not a FeatureCollection with a features array`);
  }
  validateShipDetections(d.ship_detections, `${id}/detections.geojson: ship_detections`);
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
    // discharge_class (optional, docs/team/harshita-frontend.md Phase 5.3) — chronic|acute|unknown.
    if (p.discharge_class !== undefined && !DISCHARGE_CLASSES.includes(p.discharge_class)) {
      throw new Error(
        `${id}/detections.geojson: ${p.id} has discharge_class "${p.discharge_class}" (expected chronic|acute|unknown)`,
      );
    }
    // Deprecated per-feature copy (D34) — still validated while older bundles carry it.
    validateShipDetections(p.ship_detections, `${id}/detections.geojson: ${p.id}.ship_detections`);
  }
}

export async function loadCase(id: string): Promise<LoadedCase> {
  const base = `/cases/${id}`;
  const [meta, bounds] = await Promise.all([
    fetchJson<CaseMeta>(`${base}/meta.json`),
    fetchJson<Bounds>(`${base}/bounds.json`),
  ]);

  validateMeta(meta, id);
  validateBounds(bounds, id);

  // Only a case that offers `detect` has detections at all — the same act-gating the store
  // already applies to the trace and attribute bundles. A look-alike or no-spill case still
  // offers `detect`; its correct output is a FeatureCollection with zero oil features, which
  // is a real answer and not an absence.
  let detections: DetectionCollection | null = null;
  let detectionsPending = false;
  if (meta.acts_available.includes("detect")) {
    detections = await fetchJsonIfPresent<DetectionCollection>(`${base}/detections.geojson`);
    if (detections === null) {
      detectionsPending = true;
    } else {
      validateDetections(detections, id);
    }
  }

  return { meta, bounds, detections, detectionsPending };
}
