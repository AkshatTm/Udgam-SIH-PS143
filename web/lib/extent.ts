// A reusable geographic-extent calculator, deliberately separate from any camera *policy*.
// This file only answers "what bounding box covers these sources" — it never decides when to
// point the camera at it. That decision (per-stage vs. a single global camera, whether to fold
// in particles/origin) is an open question (see the handoff, §11.3/§16 D4) that belongs to
// Akshat, not to this function.
//
// Scoped narrowly to what Attribute needs today: the scene raster + vessel tracks. Particle and
// origin extents are NOT included here — folding them in is a separate, larger decision (they
// already exceed the scene on real data) and is explicitly out of scope for this change.

import type { GeoBounds } from "./contracts";
import type { VesselBundle } from "./vessels";
import type { ParticleBundle } from "./particles";
import type { OriginBundle } from "./origin";

/** Returns `a` unchanged if it already contains `b`; otherwise the smallest box containing both. */
function unionBounds(a: GeoBounds, b: GeoBounds): GeoBounds {
  return {
    west: Math.min(a.west, b.west),
    south: Math.min(a.south, b.south),
    east: Math.max(a.east, b.east),
    north: Math.max(a.north, b.north),
  };
}

/** The bounding box of every [lon, lat] point across every vessel track. Returns null if empty. */
function vesselExtent(vessels: VesselBundle): GeoBounds | null {
  let west = Infinity;
  let south = Infinity;
  let east = -Infinity;
  let north = -Infinity;
  let any = false;
  for (const track of vessels.tracks) {
    for (const [lon, lat] of track.path) {
      any = true;
      if (lon < west) west = lon;
      if (lon > east) east = lon;
      if (lat < south) south = lat;
      if (lat > north) north = lat;
    }
  }
  return any ? { west, south, east, north } : null;
}

/**
 * The union of the scene bounds and every vessel track — pure, cheap (one pass over already-
 * loaded coordinates), and safe to call in a `useMemo` keyed on `[bounds, vessels]`. Never
 * mutates its inputs.
 */
export function sceneAndVesselExtent(scene: GeoBounds, vessels: VesselBundle | null): GeoBounds {
  if (!vessels) return scene;
  const ve = vesselExtent(vessels);
  return ve ? unionBounds(scene, ve) : scene;
}

/** The 2nd–98th percentile box of particle positions across the run. Returns null if empty.
 *
 *  15 Sept: this used the full min/max of every particle in every frame, so a handful of
 *  outliers set the camera and the scene shrank to a sliver on a mostly empty frame. The
 *  percentile box frames where the cloud actually is; the origin grid's own bounds are still
 *  unioned in by the caller, so the answer is never cropped. Every 4th frame is enough to find
 *  the envelope. */
function particleExtent(particles: ParticleBundle | null): GeoBounds | null {
  if (!particles) return null;
  const lons: number[] = [];
  const lats: number[] = [];
  for (let f = 0; f < particles.frames.length; f += 4) {
    const frame = particles.frames[f];
    for (let i = 0; i < frame.length; i += 2) {
      const lon = frame[i];
      const lat = frame[i + 1];
      if (!Number.isFinite(lon) || !Number.isFinite(lat)) continue;
      lons.push(lon);
      lats.push(lat);
    }
  }
  if (lons.length === 0) return null;
  lons.sort((a, b) => a - b);
  lats.sort((a, b) => a - b);
  const q = (arr: number[], p: number) => arr[Math.min(arr.length - 1, Math.floor(p * arr.length))];
  return { west: q(lons, 0.02), east: q(lons, 0.98), south: q(lats, 0.02), north: q(lats, 0.98) };
}

/**
 * The union of the scene bounds, every particle position across every timestep, and the
 * origin bounds. Returns scene unchanged if particles and origin are both absent.
 */
export function sceneParticleOriginExtent(
  scene: GeoBounds,
  particles: ParticleBundle | null,
  origin: OriginBundle | null,
): GeoBounds {
  let result = scene;
  const pe = particleExtent(particles);
  if (pe) {
    result = unionBounds(result, pe);
  }
  if (origin) {
    result = unionBounds(result, origin.bounds);
  }
  return result;
}

/**
 * D46 — the same union as `sceneParticleOriginExtent`, but over every independent spill group's
 * bundle at once, so the Trace camera frames every simultaneously-rendered cloud rather than
 * just the primary one. A group whose bundle has not finished loading yet is skipped, not
 * treated as empty space to frame — the camera catches up as each group's fetch resolves.
 */
export function sceneGroupsExtent(
  scene: GeoBounds,
  groupBundles: readonly { particles: ParticleBundle | null; origin: OriginBundle | null }[],
): GeoBounds {
  let result = scene;
  for (const g of groupBundles) {
    const pe = particleExtent(g.particles);
    if (pe) {
      result = unionBounds(result, pe);
    }
    if (g.origin) {
      result = unionBounds(result, g.origin.bounds);
    }
  }
  return result;
}
