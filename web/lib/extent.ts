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
