// Phase 3 origin-bundle loader. Fetches /cases/<id>/origin.json ONCE, validates the fields the
// frontend consumes against CONTRACTS.md §6, and keeps the probability grid as a Float32Array.
// `buildOriginImage` then rasterises that grid into a BitmapLayer texture — ruling D11: never a
// HeatmapLayer, which re-smooths in screen pixels and renormalises per viewport so the cloud
// changes shape as a judge zooms.
//
// Like loadCase.ts / particles.ts: on a missing or malformed file it throws a descriptive
// Error which the shell surfaces as a visible banner. It never silently patches data — a bad
// field is a contract bug for Akshat.

import type { GeoBounds, LonLat, RawOriginBundle } from "./contracts";

/** origin.json after parsing. `shape` is unpacked to `rows`/`cols`; `values` is a Float32Array. */
export interface OriginBundle {
  bounds: GeoBounds;
  rows: number;
  cols: number;
  /**
   * Length `rows * cols`, row-major from the top-left (row 0 = NORTH edge). Normalised:
   * every value is `>= 0` and the peak is `1.0`.
   */
  values: Float32Array;
  centroid: LonLat; // [lon, lat]
  radius50Km: number;
  radius90Km: number;
  timeWindow: [string, string]; // [start, end] — doubles as the age statement
  timeWindowMethod: "bounded" | "convergence" | null;
  ensembleRuns: number;
  abstain: boolean;
}

// Origin-cloud display curve. Hue is a single amber (the 50/90 % rings' family, V3 palette);
// ALPHA alone carries probability, so colour never implies a magnitude. The mapping is a mild
// gamma, NOT linear and NOT a hard cutoff: case-000's median non-zero cell is ~0.011, so linear
// alpha renders the cloud invisible, and a hard threshold leaves a fringe of just-above-cutoff
// cells reading as a second, non-existent cloud (docs/04 Phase 5.1). These three constants are
// display-only — they never change a probability, only how visible one is — and are the first
// things to retune against the real Ennore bundle (docs/04 Phase 7.2). Urooz owns the final
// palette; `ORIGIN_ALPHA_GAMMA = 1` reverts to strictly-linear alpha.
const ORIGIN_RGB: readonly [number, number, number] = [251, 176, 59];
const ORIGIN_ALPHA_GAMMA = 0.7;
const ORIGIN_ALPHA_MAX = 0.85;

/**
 * Rasterise the row-major probability grid onto an `OffscreenCanvas` and hand back its
 * `ImageBitmap` for a deck.gl `BitmapLayer` (ruling D11 — never a `HeatmapLayer`; docs/04
 * Phase 5.1). One texel per grid cell, so the image is `cols × rows` (120 × 120 for case-000).
 *
 * Orientation: CONTRACTS §6 says `values` is row-major from the top-left, i.e. **row 0 is the
 * NORTH edge**. The grid is written straight into the canvas (grid row `r` → canvas row `r`,
 * top row = north) and `BitmapLayer`'s mesh maps texture row 0 to the `bounds` top edge — so
 * north stays at north with no vertical flip. (Verify by eye anyway, TRAPS #8: the bright core
 * must sit concentric with the 50/90 % rings, and NE of the slick on real Ennore.)
 *
 * The colour ramp is authored here in the same pass: a single fixed amber hue in EVERY texel
 * (including the fully-transparent ones, so bilinear edge samples blend to transparent-amber,
 * never transparent-black — no dark fringe), with **alpha alone** carrying probability. The
 * alpha curve is a mild gamma, never linear and never a hard cutoff (see the constants above).
 *
 * Pure and browser-only (`OffscreenCanvas` + `ImageBitmap`). Allocates once; the only caller
 * is `MapView`, a client-only (`ssr: false`) dynamic import that memoises on the bundle
 * identity — so this runs once per case, never on a slider tick.
 */
export function buildOriginImage(origin: OriginBundle): ImageBitmap {
  const { rows, cols, values } = origin;
  const canvas = new OffscreenCanvas(cols, rows);
  const ctx = canvas.getContext("2d");
  if (!ctx) {
    throw new Error(
      "origin.json: could not acquire a 2D context to rasterise the origin grid",
    );
  }
  const img = ctx.createImageData(cols, rows);
  const [r, g, b] = ORIGIN_RGB;
  for (let i = 0; i < values.length; i++) {
    const v = values[i];
    const o = i * 4;
    img.data[o] = r;
    img.data[o + 1] = g;
    img.data[o + 2] = b;
    img.data[o + 3] =
      v > 0 ? Math.round(v ** ORIGIN_ALPHA_GAMMA * ORIGIN_ALPHA_MAX * 255) : 0;
  }
  ctx.putImageData(img, 0, 0);
  return canvas.transferToImageBitmap();
}

// Mean Earth radius (km) — WGS84 authalic sphere. At the case scales here (radii < ~15 km)
// the spherical small-circle approximation is well under 1 % off a true geodesic circle.
const EARTH_RADIUS_KM = 6371.0088;

/** One origin-uncertainty ring: a closed [lon,lat] polygon of `radiusKm` around the centroid. */
export interface OriginRing {
  kind: "r50" | "r90";
  radiusKm: number;
  /** Closed ring, [lon, lat] / EPSG:4326 — the first point is repeated as the last. */
  path: LonLat[];
}

/**
 * The 50 % and 90 % origin-probability radius rings, as closed [lon,lat] polygons around
 * `origin.centroid`, built once. `radius_50_km` / `radius_90_km` come straight from origin.json.
 *
 * The kilometre radius is converted to an angular offset on a sphere — **kilometres are never
 * treated as degrees**:
 *   Δlat°  = (r_km / R_earth) · 180/π
 *   Δlon°  = Δlat° / cos(latitude)          (a degree of longitude shrinks toward the poles)
 * deck.gl / MapLibre then project the resulting [lon,lat] ring like any other geometry, so the
 * circle stays geographically anchored while the map pans and zooms.
 *
 * Pure; allocates its arrays once. Callers memoise on the bundle identity, so no geometry is
 * regenerated while the slider moves.
 */
export function buildOriginRadiusRings(origin: OriginBundle, segments = 128): OriginRing[] {
  const [lon0, lat0] = origin.centroid;
  const cosLat = Math.max(Math.cos((lat0 * Math.PI) / 180), 1e-6);

  const ring = (radiusKm: number): LonLat[] => {
    const dLatDeg = (radiusKm / EARTH_RADIUS_KM) * (180 / Math.PI);
    const dLonDeg = dLatDeg / cosLat;
    const path: LonLat[] = new Array(segments + 1);
    for (let i = 0; i <= segments; i++) {
      const a = (i / segments) * 2 * Math.PI;
      path[i] = [lon0 + dLonDeg * Math.sin(a), lat0 + dLatDeg * Math.cos(a)];
    }
    return path;
  };

  return [
    { kind: "r50", radiusKm: origin.radius50Km, path: ring(origin.radius50Km) },
    { kind: "r90", radiusKm: origin.radius90Km, path: ring(origin.radius90Km) },
  ];
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

function validate(raw: RawOriginBundle, id: string): void {
  const where = `${id}/origin.json`;
  if (!raw || typeof raw !== "object") {
    throw new Error(`${where}: not an object`);
  }

  // bounds — a bare extent (no width_px / db clamp, unlike bounds.json).
  const b = raw.bounds;
  if (!b || typeof b !== "object") {
    throw new Error(`${where}: missing "bounds"`);
  }
  for (const k of ["west", "south", "east", "north"] as const) {
    if (typeof b[k] !== "number" || !Number.isFinite(b[k])) {
      throw new Error(`${where}: bounds.${k} must be a finite number`);
    }
  }
  if (!(b.west < b.east)) {
    throw new Error(`${where}: bounds.west must be < bounds.east`);
  }
  if (!(b.south < b.north)) {
    throw new Error(`${where}: bounds.south must be < bounds.north`);
  }
  if (b.west < -180 || b.east > 180) {
    throw new Error(`${where}: bounds longitudes must be in -180..180 (never 0..360)`);
  }
  if (b.south < -90 || b.north > 90) {
    throw new Error(`${where}: bounds latitudes must be in -90..90`);
  }

  // shape [rows, cols]
  if (!Array.isArray(raw.shape) || raw.shape.length !== 2) {
    throw new Error(`${where}: "shape" must be [rows, cols]`);
  }
  const [rows, cols] = raw.shape;
  if (!Number.isInteger(rows) || rows < 1 || !Number.isInteger(cols) || cols < 1) {
    throw new Error(`${where}: "shape" entries must be positive integers (got [${rows}, ${cols}])`);
  }

  // values — flattened grid, row-major, normalised 0..1
  if (!Array.isArray(raw.values)) {
    throw new Error(`${where}: "values" must be an array`);
  }
  if (raw.values.length !== rows * cols) {
    throw new Error(
      `${where}: "values" has ${raw.values.length} entries, expected rows*cols = ${rows * cols}`,
    );
  }
  let peak = 0;
  for (let i = 0; i < raw.values.length; i++) {
    const v = raw.values[i];
    if (typeof v !== "number" || !Number.isFinite(v)) {
      throw new Error(`${where}: values[${i}] is not a finite number`);
    }
    if (v < 0) {
      throw new Error(`${where}: values[${i}] = ${v} is negative — the grid must be normalised >= 0`);
    }
    if (v > peak) peak = v;
  }
  if (peak > 1 + 1e-6) {
    throw new Error(`${where}: values peak at ${peak} — the grid must be normalised to <= 1`);
  }
  if (peak === 0) {
    throw new Error(`${where}: every value is 0 — the origin grid carries no probability mass`);
  }

  // centroid [lon, lat] — the #1 geospatial trap is a [lat, lon] swap.
  const c = raw.centroid as LonLat | undefined;
  if (!Array.isArray(c) || c.length !== 2 || !Number.isFinite(c[0]) || !Number.isFinite(c[1])) {
    throw new Error(`${where}: "centroid" is not a finite [lon, lat] pair`);
  }
  if (c[0] < -180 || c[0] > 180 || c[1] < -90 || c[1] > 90) {
    throw new Error(`${where}: centroid = [${c[0]}, ${c[1]}] is out of range — a [lat, lon] swap?`);
  }

  // radii — km; the 50% mass sits inside the 90% mass.
  for (const k of ["radius_50_km", "radius_90_km"] as const) {
    if (typeof raw[k] !== "number" || !Number.isFinite(raw[k]) || raw[k] < 0) {
      throw new Error(`${where}: "${k}" must be a non-negative number`);
    }
  }
  if (raw.radius_50_km > raw.radius_90_km) {
    throw new Error(
      `${where}: radius_50_km (${raw.radius_50_km}) must be <= radius_90_km (${raw.radius_90_km})`,
    );
  }

  // time_window [start, end] — UTC ISO 8601 with a trailing Z, start not after end.
  const tw = raw.time_window;
  if (!Array.isArray(tw) || tw.length !== 2 || typeof tw[0] !== "string" || typeof tw[1] !== "string") {
    throw new Error(`${where}: "time_window" must be [start, end] strings`);
  }
  if (!tw[0].endsWith("Z") || !tw[1].endsWith("Z")) {
    throw new Error(`${where}: "time_window" entries must be UTC ISO 8601 with a trailing Z`);
  }
  const start = Date.parse(tw[0]);
  const end = Date.parse(tw[1]);
  if (!Number.isFinite(start) || !Number.isFinite(end)) {
    throw new Error(`${where}: "time_window" entries are not parseable timestamps`);
  }
  if (start > end) {
    throw new Error(`${where}: time_window start (${tw[0]}) is after end (${tw[1]})`);
  }

  // time_window_method (optional) — "bounded" | "convergence"
  if (raw.time_window_method !== undefined && raw.time_window_method !== null) {
    if (raw.time_window_method !== "bounded" && raw.time_window_method !== "convergence") {
      throw new Error(
        `${where}: "time_window_method" must be "bounded" or "convergence" (got "${raw.time_window_method}")`,
      );
    }
  }

  // ensemble_runs — a positive integer count of drift runs.
  if (!Number.isInteger(raw.ensemble_runs) || raw.ensemble_runs < 1) {
    throw new Error(`${where}: "ensemble_runs" must be a positive integer (got ${raw.ensemble_runs})`);
  }

  // abstain — the "attribution not possible" flag.
  if (typeof raw.abstain !== "boolean") {
    throw new Error(`${where}: "abstain" must be a boolean`);
  }
}

export async function loadOriginBundle(id: string): Promise<OriginBundle> {
  const raw = await fetchJson<RawOriginBundle>(`/cases/${id}/origin.json`);
  validate(raw, id);
  return {
    bounds: {
      west: raw.bounds.west,
      south: raw.bounds.south,
      east: raw.bounds.east,
      north: raw.bounds.north,
    },
    rows: raw.shape[0],
    cols: raw.shape[1],
    values: new Float32Array(raw.values),
    centroid: [raw.centroid[0], raw.centroid[1]],
    radius50Km: raw.radius_50_km,
    radius90Km: raw.radius_90_km,
    timeWindow: [raw.time_window[0], raw.time_window[1]],
    timeWindowMethod:
      raw.time_window_method === "bounded"
        ? "bounded"
        : raw.time_window_method === "convergence"
          ? "convergence"
          : null,
    ensembleRuns: raw.ensemble_runs,
    abstain: raw.abstain,
  };
}
