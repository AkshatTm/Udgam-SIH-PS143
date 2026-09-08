// Phase 5 vessel-bundle loader. Fetches /cases/<id>/vessels.geojson ONCE, validates it against
// CONTRACTS.md §7, and hands back plain [lon,lat] tracks for the deck.gl vessel PathLayer.
//
// Like particles.ts / origin.ts: on a missing or malformed file it throws a descriptive Error
// which the shell surfaces as a visible banner. It never silently patches data — a bad field is
// a contract bug for Jaiveer/Akshat, not something the frontend invents around.
//
// Vessel geometry is static per case (no timestep dependency at all) — this bundle is parsed
// once and never touched again while the slider moves.

import type { LonLat, RawVesselCollection, RawVesselFeature } from "./contracts";

/** One vessel track, exactly as CONTRACTS §7 defines it — nothing added, nothing computed. */
export interface VesselTrack {
  mmsi: string;
  name: string;
  vesselType: string;
  nPoints?: number;
  maxGapMinutes?: number;
  /** [lon, lat] pairs, in file order — never re-sorted, decimated, or smoothed here. */
  path: LonLat[];
}

export interface VesselBundle {
  tracks: VesselTrack[];
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

function validateFeature(f: RawVesselFeature, i: number, id: string): void {
  const where = `${id}/vessels.geojson[${i}]`;
  if (!f || f.type !== "Feature") {
    throw new Error(`${where}: not a GeoJSON Feature`);
  }
  const g = f.geometry;
  if (!g || g.type !== "LineString") {
    throw new Error(`${where}: geometry must be a LineString (vessel tracks are never Points/Polygons)`);
  }
  if (!Array.isArray(g.coordinates) || g.coordinates.length < 2) {
    throw new Error(`${where}: track needs at least 2 points, got ${g.coordinates?.length ?? 0}`);
  }
  for (let p = 0; p < g.coordinates.length; p++) {
    const pair = g.coordinates[p];
    if (!Array.isArray(pair) || pair.length !== 2 || !Number.isFinite(pair[0]) || !Number.isFinite(pair[1])) {
      throw new Error(`${where}/geometry/coordinates[${p}] is not a finite [lon, lat] pair`);
    }
    const [lon, lat] = pair;
    if (lon < -180 || lon > 180 || lat < -90 || lat > 90) {
      throw new Error(
        `${where}/geometry/coordinates[${p}] = [${lon}, ${lat}] is out of range — a [lat, lon] swap?`,
      );
    }
  }
  const props = f.properties;
  if (!props || typeof props !== "object") {
    throw new Error(`${where}: missing "properties"`);
  }
  if (typeof props.mmsi !== "string" || props.mmsi.length === 0) {
    throw new Error(`${where}/properties: "mmsi" must be a non-empty string`);
  }
  if (typeof props.name !== "string" || props.name.length === 0) {
    throw new Error(`${where}/properties: "name" must be a non-empty string`);
  }
  if (typeof props.vessel_type !== "string" || props.vessel_type.length === 0) {
    throw new Error(`${where}/properties: "vessel_type" must be a non-empty string`);
  }
}

export async function loadVesselBundle(id: string): Promise<VesselBundle> {
  const raw = await fetchJson<RawVesselCollection>(`/cases/${id}/vessels.geojson`);
  if (!raw || raw.type !== "FeatureCollection" || !Array.isArray(raw.features)) {
    throw new Error(`${id}/vessels.geojson: not a FeatureCollection with a features array`);
  }
  raw.features.forEach((f, i) => validateFeature(f, i, id));

  const tracks: VesselTrack[] = raw.features.map((f) => ({
    mmsi: f.properties.mmsi,
    name: f.properties.name,
    vesselType: f.properties.vessel_type,
    nPoints: f.properties.n_points,
    maxGapMinutes: f.properties.max_gap_minutes,
    path: f.geometry.coordinates,
  }));

  return { tracks };
}
