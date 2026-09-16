// Forward-slick loader (Master §6.10). Fetches /cases/<id>/forward_impact.json ONCE per case and
// parses it into the hourly envelope the map draws.
//
// UNLIKE origin.json, this file is OPTIONAL: it exists only where a trace was run, and only where
// Stage 2 had field coverage past t0. A 404 therefore resolves to `null` — "this case has no
// forward forecast" — and is NOT an error. Malformed content IS an error and throws, exactly like
// the other loaders: a wrong number is a contract bug for Akshat, never something to patch here.
//
// What the layer means, and what it must never be read as: the envelope is ensemble PRECISION.
// r50/r90 say where the 50 members agree the oil goes. They are not a guarantee that it goes
// there, and the UI labels them as agreement, never as a prediction of fact.

import type { LonLat } from "./contracts";

/** One hour of the forecast. Mirrors a §6.10 `envelope[]` row. */
export interface ForwardFrame {
  hours: number;
  radius50Km: number;
  radius90Km: number;
  centroid: LonLat; // [lon, lat]
  /** Sticky: a beached particle stays beached, so this never decreases. */
  strandedFraction: number;
}

/** forward_impact.json after parsing. */
export interface ForwardBundle {
  t0: string;
  horizonHours: number;
  ensembleRuns: number;
  particlesPerRun: number;
  envelope: ForwardFrame[];
  /** `null` when nothing beached — never `0`, which would claim landfall at t0 (Rule 4). */
  firstLandfallHours: number | null;
  strandedFractionAtHorizon: number;
  seededAshoreFraction: number;
  centroidDisplacementKm: number;
  /** `null` = not measured (no gazetteer / no cited asset layer), as distinct from measured-empty. */
  coastSegments: unknown[] | null;
  assetsAtRisk: unknown[] | null;
  horizonNote: string | null;
}

interface RawForwardFrame {
  hours: number;
  radius_50_km: number;
  radius_90_km: number;
  centroid: LonLat;
  stranded_fraction: number;
}

interface RawForwardBundle {
  t0: string;
  direction: string;
  horizon_hours: number;
  horizon_note?: string;
  ensemble_runs: number;
  particles_per_run: number;
  envelope: RawForwardFrame[];
  first_landfall_hours: number | null;
  stranded_fraction_at_horizon: number;
  seeded_ashore_fraction: number;
  centroid_displacement_km: number;
  coast_segments: unknown[] | null;
  assets_at_risk: unknown[] | null;
}

const EARTH_RADIUS_KM = 6371.0088;

function validate(raw: RawForwardBundle, id: string) {
  const where = `cases/${id}/forward_impact.json`;

  if (raw.direction !== "forward") {
    throw new Error(
      `${where}: direction is "${raw.direction}", expected "forward". A forward forecast is a ` +
        `second integration, not a relabelled rewind (Master §6.10).`,
    );
  }
  if (!Array.isArray(raw.envelope) || raw.envelope.length === 0) {
    throw new Error(`${where}: envelope must be a non-empty array, one row per hour`);
  }

  let prevHours = -Infinity;
  let prevStranded = -Infinity;
  raw.envelope.forEach((f, i) => {
    const at = `${where}: envelope[${i}]`;
    if (!Number.isFinite(f.hours) || f.hours <= prevHours) {
      throw new Error(`${at}: hours must increase strictly (got ${f.hours} after ${prevHours})`);
    }
    prevHours = f.hours;

    if (!Number.isFinite(f.radius_50_km) || !Number.isFinite(f.radius_90_km)) {
      throw new Error(`${at}: radius_50_km and radius_90_km must be finite numbers in km`);
    }
    if (f.radius_90_km < f.radius_50_km) {
      throw new Error(
        `${at}: radius_90_km (${f.radius_90_km}) < radius_50_km (${f.radius_50_km}) — 90% of ` +
          `the ensemble cannot sit inside a tighter circle than 50%`,
      );
    }
    if (!Array.isArray(f.centroid) || f.centroid.length !== 2) {
      throw new Error(`${at}: centroid must be [lon, lat]`);
    }
    const [lon, lat] = f.centroid;
    if (!Number.isFinite(lon) || lon < -180 || lon > 180) {
      throw new Error(`${at}: longitude ${lon} out of range — is this [lat, lon]?`);
    }
    if (!Number.isFinite(lat) || lat < -90 || lat > 90) {
      throw new Error(`${at}: latitude ${lat} out of range — coordinates are [lon, lat]`);
    }
    if (!Number.isFinite(f.stranded_fraction) || f.stranded_fraction < 0 || f.stranded_fraction > 1) {
      throw new Error(`${at}: stranded_fraction must be a fraction in [0, 1], never a percent`);
    }
    if (f.stranded_fraction < prevStranded - 1e-9) {
      throw new Error(
        `${at}: stranded_fraction drops ${prevStranded} → ${f.stranded_fraction}. Stranding is ` +
          `sticky — a particle cannot un-beach.`,
      );
    }
    prevStranded = f.stranded_fraction;
  });

  // Rule 4, mirrored from the validator so a bad bundle cannot reach the screen even if it
  // somehow bypassed scripts/validate_case.py.
  if (raw.stranded_fraction_at_horizon === 0 && raw.first_landfall_hours !== null) {
    throw new Error(
      `${where}: nothing is ashore but first_landfall_hours is ${raw.first_landfall_hours}. ` +
        `With no landfall the honest value is null, not a number (Rule 4).`,
    );
  }
}

export async function loadForwardBundle(id: string): Promise<ForwardBundle | null> {
  let res: Response;
  try {
    res = await fetch(`/cases/${id}/forward_impact.json`, { cache: "no-store" });
  } catch (err) {
    throw new Error(`Could not fetch cases/${id}/forward_impact.json: ${(err as Error).message}`);
  }
  // Optional by contract — absence is a fact about the case, not a failure.
  if (res.status === 404) return null;
  if (!res.ok) {
    throw new Error(`Failed to fetch cases/${id}/forward_impact.json: HTTP ${res.status}`);
  }

  let raw: RawForwardBundle;
  try {
    raw = (await res.json()) as RawForwardBundle;
  } catch {
    throw new Error(`cases/${id}/forward_impact.json is not valid JSON`);
  }
  validate(raw, id);

  return {
    t0: raw.t0,
    horizonHours: raw.horizon_hours,
    ensembleRuns: raw.ensemble_runs,
    particlesPerRun: raw.particles_per_run,
    envelope: raw.envelope.map((f) => ({
      hours: f.hours,
      radius50Km: f.radius_50_km,
      radius90Km: f.radius_90_km,
      centroid: [f.centroid[0], f.centroid[1]] as LonLat,
      strandedFraction: f.stranded_fraction,
    })),
    firstLandfallHours: raw.first_landfall_hours,
    strandedFractionAtHorizon: raw.stranded_fraction_at_horizon,
    seededAshoreFraction: raw.seeded_ashore_fraction,
    centroidDisplacementKm: raw.centroid_displacement_km,
    coastSegments: raw.coast_segments ?? null,
    assetsAtRisk: raw.assets_at_risk ?? null,
    horizonNote: raw.horizon_note ?? null,
  };
}

export interface ForwardRing {
  hours: number;
  kind: "r50" | "r90";
  radiusKm: number;
  /** 0 at t0 → 1 at the horizon. Drives opacity so the cone reads as time, not as probability. */
  t: number;
  path: LonLat[];
}

function circle(centre: LonLat, radiusKm: number, segments: number): LonLat[] {
  const [lon0, lat0] = centre;
  const cosLat = Math.max(Math.cos((lat0 * Math.PI) / 180), 1e-6);
  const dLatDeg = (radiusKm / EARTH_RADIUS_KM) * (180 / Math.PI);
  const dLonDeg = dLatDeg / cosLat;
  const path: LonLat[] = new Array(segments + 1);
  for (let i = 0; i <= segments; i++) {
    const a = (i / segments) * 2 * Math.PI;
    path[i] = [lon0 + dLonDeg * Math.sin(a), lat0 + dLatDeg * Math.cos(a)];
  }
  return path;
}

/** Hours spanned by the forecast, endpoint of the forward playhead (forwardNorm 0..1 * this). */
export function forwardSpanHours(forward: ForwardBundle): number {
  return Math.max(forward.envelope[forward.envelope.length - 1].hours, 1);
}

/**
 * The spreading cone: one r90 ring per hour, drawn around that hour's centroid, plus the r50/r90
 * pair at the horizon. Built ONCE per bundle — the km→degree conversion never runs on a scrub,
 * the same discipline as buildOriginRadiusRings. MapView filters the result down to the rings at
 * or before the forward playhead on every scrub — a cheap array filter over pre-tessellated
 * paths, never a re-tessellation.
 *
 * Every hour is drawn rather than only the endpoint because the shape between them is the actual
 * result: the slick both travels (centroid moves) and spreads (radius grows), and a single
 * end-state circle hides which of the two dominates.
 */
export function buildForwardRings(forward: ForwardBundle, segments = 96): ForwardRing[] {
  const last = forward.envelope[forward.envelope.length - 1];
  const span = forwardSpanHours(forward);
  const rings: ForwardRing[] = [];

  for (const f of forward.envelope) {
    rings.push({
      hours: f.hours,
      kind: "r90",
      radiusKm: f.radius90Km,
      t: f.hours / span,
      path: circle(f.centroid, f.radius90Km, segments),
    });
  }
  // The horizon pair is drawn last so it sits on top of the cone it terminates.
  rings.push({
    hours: last.hours,
    kind: "r50",
    radiusKm: last.radius50Km,
    t: 1,
    path: circle(last.centroid, last.radius50Km, segments),
  });
  return rings;
}

/** The centroid's path from t0 to the horizon — "where it drifts", as distinct from "how far it spreads". */
export function buildForwardTrack(forward: ForwardBundle): LonLat[] {
  return forward.envelope.map((f) => f.centroid);
}
