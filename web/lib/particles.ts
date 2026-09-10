// Phase 2 particle-bundle loader. Fetches /cases/<id>/particles.json ONCE, validates its
// shape against CONTRACTS.md §5, and flattens each timestep into a Float32Array so the
// deck.gl ScatterplotLayer can bind it as a binary attribute with zero per-frame copying.
//
// Like loadCase.ts: on a missing / malformed file it throws a descriptive Error which the
// shell surfaces as a visible banner. It never silently patches data — a bad field is a
// contract bug for Akshat.

import type { LonLat, RawParticleBundle } from "./contracts";

/** particles.json after parsing: positions flattened, one Float32Array per timestep. */
export interface ParticleBundle {
  t0: string;
  direction: string;
  timestepMinutes: number;
  nSteps: number;
  nParticles: number;
  /** frames[t] is a length `nParticles * 2` array laid out [lon, lat, lon, lat, ...]. */
  frames: Float32Array[];
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

function validate(raw: RawParticleBundle, id: string): void {
  const where = `${id}/particles.json`;
  if (!raw || typeof raw !== "object") {
    throw new Error(`${where}: not an object`);
  }
  if (typeof raw.t0 !== "string" || !raw.t0.endsWith("Z")) {
    throw new Error(`${where}: "t0" must be UTC ISO 8601 with a trailing Z`);
  }
  if (raw.direction !== "backward") {
    throw new Error(`${where}: "direction" is "${raw.direction}" (expected "backward")`);
  }
  if (!Number.isInteger(raw.n_steps) || raw.n_steps < 2) {
    throw new Error(`${where}: "n_steps" must be an integer >= 2 (got ${raw.n_steps})`);
  }
  if (!Number.isInteger(raw.n_particles) || raw.n_particles < 1) {
    throw new Error(`${where}: "n_particles" must be a positive integer (got ${raw.n_particles})`);
  }
  if (typeof raw.timestep_minutes !== "number" || !(raw.timestep_minutes > 0)) {
    throw new Error(`${where}: "timestep_minutes" must be a positive number`);
  }
  if (!Array.isArray(raw.positions) || raw.positions.length !== raw.n_steps) {
    const got = Array.isArray(raw.positions) ? raw.positions.length : typeof raw.positions;
    throw new Error(`${where}: "positions" must have n_steps (${raw.n_steps}) entries, got ${got}`);
  }
  for (let s = 0; s < raw.positions.length; s++) {
    const step = raw.positions[s];
    if (!Array.isArray(step) || step.length !== raw.n_particles) {
      const got = Array.isArray(step) ? step.length : typeof step;
      throw new Error(`${where}: positions[${s}] must have n_particles (${raw.n_particles}) entries, got ${got}`);
    }
  }
  // Spot-check the corners for [lon, lat] order and finite values — the #1 geospatial trap.
  const rows: [number, number][] = [
    [0, 0],
    [0, raw.n_particles - 1],
    [raw.n_steps - 1, 0],
    [raw.n_steps - 1, raw.n_particles - 1],
  ];
  for (const [s, p] of rows) {
    const pair = raw.positions[s][p] as LonLat | undefined;
    if (!Array.isArray(pair) || pair.length !== 2 || !Number.isFinite(pair[0]) || !Number.isFinite(pair[1])) {
      throw new Error(`${where}: positions[${s}][${p}] is not a finite [lon, lat] pair`);
    }
    const [lon, lat] = pair;
    if (lon < -180 || lon > 180 || lat < -90 || lat > 90) {
      throw new Error(`${where}: positions[${s}][${p}] = [${lon}, ${lat}] is out of range — a [lat, lon] swap?`);
    }
  }
}

function flatten(raw: RawParticleBundle): Float32Array[] {
  const { n_steps, n_particles } = raw;
  const frames: Float32Array[] = new Array(n_steps);
  for (let s = 0; s < n_steps; s++) {
    const src = raw.positions[s];
    const arr = new Float32Array(n_particles * 2);
    for (let p = 0; p < n_particles; p++) {
      const pair = src[p];
      arr[p * 2] = pair[0]; // lon
      arr[p * 2 + 1] = pair[1]; // lat
    }
    frames[s] = arr;
  }
  return frames;
}

export async function loadParticleBundle(id: string): Promise<ParticleBundle> {
  const raw = await fetchJson<RawParticleBundle>(`/cases/${id}/particles.json`);
  validate(raw, id);
  return {
    t0: raw.t0,
    direction: raw.direction,
    timestepMinutes: raw.timestep_minutes,
    nSteps: raw.n_steps,
    nParticles: raw.n_particles,
    frames: flatten(raw),
  };
}
