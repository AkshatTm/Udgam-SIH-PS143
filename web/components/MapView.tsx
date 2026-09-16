"use client";

// The one map. MapLibre GL JS, no token. The SAR raster sits on a light ocean basemap: Esri
// ocean tiles when online, over a bundled offline land/sea base that keeps the demo safe when
// the network is not (see OCEAN_STYLE below).
//
// The map object is created once. Store changes (case, layer visibility, selection) are pushed
// in via imperative map calls in effects — the map container never re-renders on those.
// deck.gl rides on top through a single MapboxOverlay control (created once, next to the map).
// The layer list is composed from two memoised pieces and pushed via one effect:
//   - the particle ScatterplotLayer (Phase 2) — the only layer that changes every playback tick;
//   - the origin BitmapLayer + 50/90 % radius rings (Phase 3) — built ONCE per origin bundle,
//     mounted as soon as the bundle loads and kept mounted for the life of the case, with the
//     T−24h→T−0 fade (and the Origin toggle) driven purely by `opacity`. The BitmapLayer does
//     no aggregation at all — a scrub only updates the layer's opacity uniform.
// The timestep only ever updates deck layers, never the map.

import { useEffect, useMemo, useRef, useState } from "react";
import {
  AttributionControl,
  Map as MlMap,
  NavigationControl,
  setWorkerUrl,
  type GeoJSONSource,
  type IControl,
  type ImageSource,
  type MapMouseEvent,
  type StyleSpecification,
} from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import { MapboxOverlay } from "@deck.gl/mapbox";
import { BitmapLayer, PathLayer, PolygonLayer, ScatterplotLayer } from "@deck.gl/layers";
import { RUN_DURATION_MS, useAppStore } from "@/lib/store";
import { tFromNorm } from "@/lib/timestep";
import { buildOriginImage, buildOriginRadiusRings, type OriginRing } from "@/lib/origin";
import { buildForwardRings, buildForwardTrack, type ForwardRing } from "@/lib/forward";
import { sceneAndVesselExtent, sceneParticleOriginExtent } from "@/lib/extent";
import type { Bounds, GeoBounds, LonLat } from "@/lib/contracts";

// maplibre-gl v6 loads its GeoJSON/vector tiler in a separate ESM worker. Its built-in worker
// resolver needs an http(s) `import.meta.url`, which webpack replaces with a build-time
// file:// path — so it falls back to `new Worker("")` and no vector source ever renders (the
// SAR image layer still works because it decodes on the main thread). Point maplibre at a
// static copy of the worker instead; `predev`/`prebuild` copy it into public/maplibre/.
setWorkerUrl("/maplibre/maplibre-gl-worker.mjs");

// A judge seeing the Trace union camera zoom out to fit a real off-scene origin cloud (Jacksonville
// sits ~130 km from its own SAR scene) was landing on a near-empty frame: no external tiles means
// no coastline, so the wide-zoomed background was just flat colour with nothing to read as "this
// is the ocean." Fixed with one bundled, static, offline asset — never a network fetch — rather
// than a hosted basemap: `land.geojson` is Natural Earth's 1:110m land-polygon layer (public
// domain, no attribution required, 127 features / ~135 KB, https://www.naturalearthdata.com),
// fetched once at https://cdn.jsdelivr.net/gh/nvkelso/natural-earth-vector and committed at
// web/public/basemap/ne_110m_land.geojson. It renders first (bottom of the style, under the SAR
// raster/detections layers added in `load` below, and under every deck.gl overlay, which always
// paints above the MapLibre canvas) and stays deliberately low-contrast against the `#0b0f14`
// ocean background — a shape to read as "Earth," never a layer competing with the evidence.
//
// 15 Sept: the dark style made the zoomed-out Trace view read as a black screen, so the map now
// uses a light ocean basemap in the manner of SkyTruth Cerulean. It is layered, not switched:
//   1. an OFFLINE base — light-blue sea + Natural Earth 1:50m land (public domain, committed at
//      web/public/basemap/ne_50m_land.geojson) — always renders, no network;
//   2. Esri World Ocean Base raster tiles on top, when the network allows. If the venue wifi
//      drops, the tiles simply fail to load and layer 1 shows through. No fallback logic to break.
// Esri's ocean basemap needs attribution, shown compact in the top-right.
const ESRI_ATTRIBUTION = "© Esri, GEBCO, NOAA, Garmin · Natural Earth";
const OCEAN_STYLE: StyleSpecification = {
  version: 8,
  sources: {
    land: { type: "geojson", data: "/basemap/ne_50m_land.geojson" },
    ocean: {
      type: "raster",
      tiles: [
        "https://server.arcgisonline.com/ArcGIS/rest/services/Ocean/World_Ocean_Base/MapServer/tile/{z}/{y}/{x}",
      ],
      tileSize: 256,
      // Open-ocean tiles above z10 are "data not yet available" placeholders; overzoom instead.
      maxzoom: 10,
      attribution: ESRI_ATTRIBUTION,
    },
  },
  layers: [
    { id: "bg", type: "background", paint: { "background-color": "#050a10" } },
    {
      id: "land-fill",
      type: "fill",
      source: "land",
      paint: { "fill-color": "#141c25", "fill-opacity": 1 },
    },
    {
      id: "land-outline",
      type: "line",
      source: "land",
      paint: { "line-color": "#3a5364", "line-width": 0.8 },
    },
    {
      id: "ocean-tiles",
      type: "raster",
      source: "ocean",
      // Esri's natural-colour World Ocean Base, shown as-is. Same offline-first behaviour as
      // before — if the venue wifi drops, the tiles simply fail to load and the offline land/sea
      // base (layer 1 above) shows through.
      paint: {
        "raster-opacity": 1,
        "raster-fade-duration": 150,
      },
    },
  ],
};

// Tuned for the dark basemap, and identical to the --oil / --reject tokens in globals.css so
// the panel and the map name the same thing in the same colour.
const OIL_COLOR = "#ff4d6d";
const LOOKALIKE_COLOR = "#7a8899";
const SCENE_OUTLINE_COLOR = "#2f5f7d";

// Particle dots — warm amber with a thin dark rim, so they read over dark sea, dark land and the
// grey SAR raster alike.
const PARTICLE_FILL: [number, number, number, number] = [249, 115, 22, 220];
const PARTICLE_LINE: [number, number, number, number] = [67, 20, 7, 160];

// The Run-detection scan line: a translucent band sweeping west→east across the SAR footprint.
const SCAN_FILL: [number, number, number, number] = [249, 115, 22, 70];
const SCAN_EDGE: [number, number, number, number] = [249, 115, 22, 255];

// Origin cloud fade. Rewind fraction (0 at T−0, 1 at T−24h) is run through a smoothstep so the
// cloud is fully hidden near the detection time and eases in only as the slider approaches
// maximum rewind — "the origin becomes knowable the further back you drift" (docs/team/harshita-frontend.md §Phase 3).
// This is the ONLY thing about the origin layer that changes on a scrub: a pure `opacity` prop,
// which the BitmapLayer applies without re-uploading its texture. The colour ramp and the
// alpha-proportional mapping live in lib/origin.ts (buildOriginImage); Urooz owns the palette.
const ORIGIN_FADE_IN_START = 0.2; // rewind fraction at which the cloud starts to appear
const ORIGIN_FADE_IN_FULL = 0.9; // rewind fraction at which it reaches full opacity
// 15 Sept: the cloud is never fully invisible on Trace — a floor keeps "where the oil came from"
// on screen from the first frame, and the fade still carries the "knowable further back" story.
const ORIGIN_OPACITY_FLOOR = 0.25;

// 50 % / 90 % origin-probability rings — warm amber-yellow outlines over the origin cloud. The
// inner (50 %) ring is brighter; the outer (90 %) ring is softer but still readable. Both
// complement the warm origin-cloud colour ramp rather than clashing with a white outline. V3 palette.
// Deepened to burnt amber on 15 Sept so both rings read against the light basemap.
const ORIGIN_RING_50: [number, number, number, number] = [180, 83, 9, 240];
const ORIGIN_RING_90: [number, number, number, number] = [180, 83, 9, 150];
const ORIGIN_RING_WIDTH_PX = 1.5;

// Hoisted so their identity is stable across renders — the ring geometry is static, so these
// accessors must never look like they changed (which would ask deck.gl to re-tessellate).
// Forward slick (Master 6.10). Deliberately NOT a new hue: this is the same 50-member ensemble
// as the origin cloud, integrated the other way, so it stays in the amber/drift family and is
// told apart by RENDERING instead — outline-only rings (the origin cloud is a filled bitmap),
// and opacity that decays into the future. Inventing a sixth colour here would imply a sixth
// kind of thing on a map that already carries five (blue = vessel, amber = particle/origin,
// red = oil, rose = dark vessel, violet = infrastructure).
//
// Opacity carries FORECAST HOUR, never probability or confidence. The +24 h ring is not less
// likely than the +1 h ring; it is further away in time, and the fade is the only thing that
// says so on a static map.
const FORWARD_RING_NEAR: [number, number, number, number] = [251, 176, 59, 200];
const FORWARD_RING_FAR: [number, number, number, number] = [251, 146, 60, 70];
const FORWARD_HORIZON_R50: [number, number, number, number] = [180, 83, 9, 245];
const FORWARD_TRACK_COLOR: [number, number, number, number] = [234, 88, 12, 225];
const FORWARD_RING_WIDTH_PX = 1.2;
const FORWARD_HORIZON_WIDTH_PX = 2.4;
const FORWARD_TRACK_WIDTH_PX = 2;

const forwardRingPath = (d: ForwardRing): ForwardRing["path"] => d.path;
// r50 at the horizon is the one ring a judge should be able to point at, so it gets full
// weight; every hourly r90 fades with `t`.
const forwardRingColor = (d: ForwardRing): [number, number, number, number] => {
  if (d.kind === "r50") return FORWARD_HORIZON_R50;
  const k = Math.min(Math.max(d.t, 0), 1);
  return [
    Math.round(FORWARD_RING_NEAR[0] + (FORWARD_RING_FAR[0] - FORWARD_RING_NEAR[0]) * k),
    Math.round(FORWARD_RING_NEAR[1] + (FORWARD_RING_FAR[1] - FORWARD_RING_NEAR[1]) * k),
    Math.round(FORWARD_RING_NEAR[2] + (FORWARD_RING_FAR[2] - FORWARD_RING_NEAR[2]) * k),
    Math.round(FORWARD_RING_NEAR[3] + (FORWARD_RING_FAR[3] - FORWARD_RING_NEAR[3]) * k),
  ];
};
const forwardRingWidth = (d: ForwardRing): number =>
  d.kind === "r50" || d.t >= 1 ? FORWARD_HORIZON_WIDTH_PX : FORWARD_RING_WIDTH_PX;

const originRingPath = (d: OriginRing): OriginRing["path"] => d.path;
const originRingColor = (d: OriginRing): [number, number, number, number] =>
  d.kind === "r50" ? ORIGIN_RING_50 : ORIGIN_RING_90;

// Vessel tracks (Phase 5) — cool blue family, distinct from the amber particle/origin palette
// and from the red/grey detection colours, so all three layers stay readable together. Role is
// conveyed by emphasis (opacity + width), not a hue change, to avoid inventing a new colour
// that could collide with an existing token the way the amber particle/origin-cloud colours did.
//
// IMPORTANT: role is only ever assigned when `origin.abstain` has been confirmed `false`. While
// abstain is `true`, or origin hasn't loaded yet, every track renders as "plain" — the map must
// never visually imply a vessel is responsible when the contract says attribution isn't possible.
type VesselRole = "top" | "suspect" | "excluded" | "plain";

interface VesselMapItem {
  mmsi: string;
  name: string;
  path: LonLat[];
  role: VesselRole;
}

// Darkened for the light basemap (15 Sept): the old sky-blues vanished against blue sea.
// Lifted off the old light basemap: a navy track was invisible on a night sea. Plain traffic is
// a cool slate, a suspect steps up in teal, and the top suspect is full --contact.
const VESSEL_COLOR_PLAIN: [number, number, number, number] = [110, 133, 158, 150];
const VESSEL_COLOR_SUSPECT: [number, number, number, number] = [45, 180, 180, 215];
const VESSEL_COLOR_TOP_SUSPECT: [number, number, number, number] = [45, 212, 191, 255];
// Excluded — muted, per docs/team/jaiveer-stage3-attribution.md ("visually ruled out"). The strikethrough motif itself is
// applied on the exclusion card in ContextPanel; a dashed line isn't a deck.gl PathLayer
// primitive, so the map conveys "ruled out" via reduced opacity + thin width instead.
const VESSEL_COLOR_EXCLUDED: [number, number, number, number] = [90, 105, 122, 120];

const VESSEL_WIDTH_PLAIN = 1.2;
const VESSEL_WIDTH_SUSPECT = 1.8;
const VESSEL_WIDTH_TOP_SUSPECT = 3;
const VESSEL_WIDTH_EXCLUDED = 1;

// docs/team/harshita-frontend.md Phase 3.5 — dark vessels (Master §6.7). A radar contact with no AIS at all: a point,
// never a track, never linked to `vessels.geojson`. Deliberately its own colour family (rose),
// unused everywhere else in this app (blue = vessel, amber = particle/origin, red = oil,
// grey = look-alike/excluded) — an alert marker must not read as any of those.
interface DarkVesselMapItem {
  position: LonLat;
  name: string;
  reasons: string[];
}
const DARK_VESSEL_COLOR: [number, number, number, number] = [244, 63, 94, 235];
const DARK_VESSEL_LINE_COLOR: [number, number, number, number] = [76, 5, 25, 255];
const DARK_VESSEL_RADIUS_PX = 8;

// docs/team/harshita-frontend.md Phase 3.6 — infrastructure findings (Master §6.7). Also a stationary point with no
// AIS identity, but a distinct category from a dark vessel (a named, known facility being
// scored — not an anomaly). Its own colour (violet) — unclaimed by any other layer in this
// app (blue = vessel, amber = particle/origin, red = oil, grey = look-alike/excluded, rose =
// dark vessel) — so the two "no-AIS point" categories never read as the same thing on the map.
interface InfrastructureMapItem {
  position: LonLat;
}
const INFRASTRUCTURE_COLOR: [number, number, number, number] = [167, 139, 250, 235];
const INFRASTRUCTURE_LINE_COLOR: [number, number, number, number] = [255, 255, 255, 200];
const INFRASTRUCTURE_RADIUS_PX = 7;

// docs/team/harshita-frontend.md Phase 5.3 — ship_detections (Master §6.3, D34). Soumirya's RAW radar contacts for the whole
// scene, top-level on the FeatureCollection. UNATTRIBUTED — NOT the same list as suspects.json's
// `dark_vessels` (Jaiveer's already AIS-cross-checked "no match" subset, Phase 3.5 above). A
// contact is never "dark" until that check has run at a known time. This renders every candidate
// contact the detector found, independent of any attribution result. Its own colour (teal) — unclaimed
// by any existing layer (blue = vessel, amber = particle/origin, red = oil, grey =
// look-alike/excluded, rose = dark vessel, violet = infrastructure).
interface ShipDetectionMapItem {
  position: LonLat;
}
const SHIP_DETECTION_COLOR: [number, number, number, number] = [45, 212, 191, 235];
const SHIP_DETECTION_LINE_COLOR: [number, number, number, number] = [4, 47, 46, 230];
const SHIP_DETECTION_RADIUS_PX = 6;

const vesselTrackPath = (d: VesselMapItem): LonLat[] => d.path;
const vesselTrackColor = (d: VesselMapItem): [number, number, number, number] => {
  switch (d.role) {
    case "top":
      return VESSEL_COLOR_TOP_SUSPECT;
    case "suspect":
      return VESSEL_COLOR_SUSPECT;
    case "excluded":
      return VESSEL_COLOR_EXCLUDED;
    default:
      return VESSEL_COLOR_PLAIN;
  }
};
const vesselTrackWidth = (d: VesselMapItem): number => {
  switch (d.role) {
    case "top":
      return VESSEL_WIDTH_TOP_SUSPECT;
    case "suspect":
      return VESSEL_WIDTH_SUSPECT;
    case "excluded":
      return VESSEL_WIDTH_EXCLUDED;
    default:
      return VESSEL_WIDTH_PLAIN;
  }
};

function smoothstep(edge0: number, edge1: number, x: number): number {
  const u = Math.min(1, Math.max(0, (x - edge0) / (edge1 - edge0)));
  return u * u * (3 - 2 * u);
}

function unionGeo(a: GeoBounds, b: GeoBounds): GeoBounds {
  return {
    west: Math.min(a.west, b.west),
    south: Math.min(a.south, b.south),
    east: Math.max(a.east, b.east),
    north: Math.max(a.north, b.north),
  };
}

function escapeHtml(s: string): string {
  return s.replace(/[&<>"']/g, (c) =>
    c === "&" ? "&amp;" : c === "<" ? "&lt;" : c === ">" ? "&gt;" : c === '"' ? "&quot;" : "&#39;",
  );
}

function footprintGeoJSON(b: Bounds | null): GeoJSON.FeatureCollection {
  if (!b) return { type: "FeatureCollection", features: [] };
  return {
    type: "FeatureCollection",
    features: [
      {
        type: "Feature",
        properties: {},
        geometry: {
          type: "LineString",
          coordinates: [
            [b.west, b.north],
            [b.east, b.north],
            [b.east, b.south],
            [b.west, b.south],
            [b.west, b.north],
          ],
        },
      },
    ],
  };
}

function imageCoordinates(b: Bounds): [
  [number, number],
  [number, number],
  [number, number],
  [number, number],
] {
  // top-left, top-right, bottom-right, bottom-left — pixel (0,0) is (west, north).
  return [
    [b.west, b.north],
    [b.east, b.north],
    [b.east, b.south],
    [b.west, b.south],
  ];
}

export default function MapView() {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<MlMap | null>(null);
  const overlayRef = useRef<MapboxOverlay | null>(null);
  const styleReadyRef = useRef(false);
  // Mirrors styleReadyRef as state so the camera effect re-runs once the map loads. Without it,
  // bundles that resolve BEFORE "load" (fast or cached) leave the camera on the scene-only fit.
  const [mapReady, setMapReady] = useState(false);

  const activeCaseId = useAppStore((s) => s.activeCaseId);
  const activeStage = useAppStore((s) => s.activeStage);
  const bounds = useAppStore((s) => s.bounds);
  const detections = useAppStore((s) => s.detections);
  const layers = useAppStore((s) => s.layers);
  const selectedDetectionId = useAppStore((s) => s.selectedDetectionId);
  // Guided flow: each stage's overlays stay hidden until its Run button has been pressed.
  const detectRevealed = useAppStore((s) => s.revealed.detect);
  const attributeRevealed = useAppStore((s) => s.revealed.attribute);
  const running = useAppStore((s) => s.running);

  // Phase 2 particle playback. `t` is the integer timestep the slider currently points at;
  // it only changes ~8×/s during playback, so the deck layer effect below stays cheap.
  const particles = useAppStore((s) => s.particles);
  const particlesVisible = useAppStore((s) => s.layers.particles);
  const tNorm = useAppStore((s) => s.tNorm);
  const t = tFromNorm(tNorm, particles?.nSteps ?? 0);

  // Phase 3 origin cloud. Step 1 parsed origin.json once into the store; here the row-major
  // probability grid is rasterised once into a 120×120 RGBA image (one texel per cell) and
  // memoised on the bundle identity — never rebuilt on a scrub, and origin.json is never
  // re-fetched.
  const origin = useAppStore((s) => s.origin);
  const originVisible = useAppStore((s) => s.layers.origin);
  const originImage = useMemo(
    () => (origin ? buildOriginImage(origin) : null),
    [origin],
  );
  // 50 % / 90 % rings around origin.centroid, using radius_50_km / radius_90_km. Built once
  // per bundle — the km→degree conversion never runs on a scrub (see lib/origin.ts).
  const originRings = useMemo(
    () => (origin ? buildOriginRadiusRings(origin) : null),
    [origin],
  );

  // Master 6.10 forward slick. Static geometry with no timestep dependency: the existing slider
  // runs T-24h -> T-0 (the rewind), and the forecast lives on the far side of t0. Rather than
  // overload one slider with two time domains, the whole 24 h cone is drawn at once and the
  // fade carries the hour. `forward` is null on a case Stage 2 produced no forecast for.
  const forward = useAppStore((s) => s.forward);
  const forwardVisible = useAppStore((s) => s.layers.forward);
  const forwardRings = useMemo(
    () => (forward ? buildForwardRings(forward) : null),
    [forward],
  );
  const forwardTrack = useMemo(
    () => (forward ? buildForwardTrack(forward) : null),
    [forward],
  );

  // Phase 5 attribution. `vessels` is static geometry (no timestep dependency at all) — the
  // PathLayer built from it is memoised on the bundle + suspects identity, never on `t`.
  const vessels = useAppStore((s) => s.vessels);
  const vesselsVisible = useAppStore((s) => s.layers.vessels);
  const suspects = useAppStore((s) => s.suspects);
  // docs/team/harshita-frontend.md Phase 3.3 — hover-to-highlight. Purely presentational: never touches vesselItems
  // (the parsed track geometry), never refetches, never rebuilds the map or its camera.
  const hoveredMmsi = useAppStore((s) => s.hoveredSuspectMmsi);

  // Role (top suspect / suspect / excluded) is only ever attached once origin.abstain is
  // confirmed false — see the comment on VesselRole above. `origin` is read from the store
  // above (Phase 3 origin cloud); this reuses that same value rather than re-fetching anything.
  const abstainConfirmedFalse = origin !== null && origin.abstain === false;

  const vesselItems = useMemo(() => {
    if (!vessels) return [] as VesselMapItem[];
    if (!abstainConfirmedFalse || !suspects) {
      return vessels.tracks.map((t) => ({
        mmsi: t.mmsi,
        name: t.name,
        path: t.path,
        role: "plain" as const,
      }));
    }
    const topMmsi = suspects.suspects[0]?.mmsi;
    const suspectMmsi = new Set(suspects.suspects.map((s) => s.mmsi));
    const excludedMmsi = new Set(suspects.excluded.map((e) => e.mmsi));
    return vessels.tracks.map((t) => {
      let role: VesselRole = "plain";
      if (t.mmsi === topMmsi) role = "top";
      else if (suspectMmsi.has(t.mmsi)) role = "suspect";
      else if (excludedMmsi.has(t.mmsi)) role = "excluded";
      return { mmsi: t.mmsi, name: t.name, path: t.path, role };
    });
  }, [vessels, suspects, abstainConfirmedFalse]);

  const vesselLayer = useMemo(() => {
    if (!attributeRevealed || !vesselsVisible || vesselItems.length === 0) return null;
    // Edge case: a hovered mmsi with no matching track (shouldn't happen — Master §6.7 requires
    // every suspect mmsi to have a track — but defended anyway) falls back to plain role styling
    // for every track, rather than dimming everything with nothing highlighted.
    const hoveredMmsiValid =
      hoveredMmsi !== null && vesselItems.some((v) => v.mmsi === hoveredMmsi);
    const getColor = (d: VesselMapItem): [number, number, number, number] => {
      const [r, g, b, a] = vesselTrackColor(d);
      if (!hoveredMmsiValid) return [r, g, b, a];
      return d.mmsi === hoveredMmsi ? [r, g, b, 255] : [r, g, b, Math.round(a * 0.25)];
    };
    const getWidth = (d: VesselMapItem): number => {
      const w = vesselTrackWidth(d);
      if (!hoveredMmsiValid) return w;
      return d.mmsi === hoveredMmsi ? w + 2 : Math.max(0.6, w * 0.6);
    };
    return new PathLayer<VesselMapItem>({
      id: "vessels",
      data: vesselItems,
      getPath: vesselTrackPath,
      getColor,
      getWidth,
      widthUnits: "pixels",
      widthMinPixels: 1,
      capRounded: true,
      jointRounded: true,
      pickable: true,
      updateTriggers: { getColor: [hoveredMmsi], getWidth: [hoveredMmsi] },
    });
  }, [vesselItems, vesselsVisible, hoveredMmsi, attributeRevealed]);

  // docs/team/harshita-frontend.md Phase 3.5 — dark-vessel markers. Independent of `vesselsVisible` on purpose: the
  // whole point of the AIS-off reveal (docs/team/harshita-integration.md §3.3) is that toggling the AIS track layer off
  // leaves this marker alone with nothing beneath it. No mmsi exists to share with the hover
  // highlight (Phase 3.3) or the vessel PathLayer, so the two features cannot collide.
  const darkVesselItems = useMemo(() => {
    if (!suspects) return [] as DarkVesselMapItem[];
    return suspects.darkVessels.map((dv) => ({
      position: [dv.lon, dv.lat] as LonLat,
      name: dv.name ?? "Unidentified radar contact",
      reasons: dv.reasons,
    }));
  }, [suspects]);

  const darkVesselLayer = useMemo(() => {
    if (!attributeRevealed || darkVesselItems.length === 0) return null;
    return new ScatterplotLayer<DarkVesselMapItem>({
      id: "dark-vessels",
      data: darkVesselItems,
      getPosition: (d) => d.position,
      getFillColor: DARK_VESSEL_COLOR,
      getLineColor: DARK_VESSEL_LINE_COLOR,
      getRadius: DARK_VESSEL_RADIUS_PX,
      radiusUnits: "pixels",
      lineWidthUnits: "pixels",
      getLineWidth: 2.5,
      stroked: true,
      pickable: true,
    });
  }, [darkVesselItems, attributeRevealed]);

  // docs/team/harshita-frontend.md Phase 3.6 — infrastructure markers. Same independent-of-`vesselsVisible` reasoning
  // as dark vessels doesn't apply here (no toggle-driven reveal is described for infrastructure
  // in any doc) — it simply renders whenever the bundle has findings, like the dark-vessel layer.
  const infrastructureItems = useMemo(() => {
    if (!suspects) return [] as InfrastructureMapItem[];
    return suspects.infrastructure.map((inf) => ({ position: [inf.lon, inf.lat] as LonLat }));
  }, [suspects]);

  const infrastructureLayer = useMemo(() => {
    if (!attributeRevealed || infrastructureItems.length === 0) return null;
    return new ScatterplotLayer<InfrastructureMapItem>({
      id: "infrastructure",
      data: infrastructureItems,
      getPosition: (d) => d.position,
      getFillColor: INFRASTRUCTURE_COLOR,
      getLineColor: INFRASTRUCTURE_LINE_COLOR,
      getRadius: INFRASTRUCTURE_RADIUS_PX,
      radiusUnits: "pixels",
      lineWidthUnits: "pixels",
      getLineWidth: 1.5,
      stroked: true,
      pickable: false,
    });
  }, [infrastructureItems, attributeRevealed]);

  // docs/team/harshita-frontend.md Phase 5.3 — ship_detections (Master §6.3, D34). Read the top-level scene list. Only a
  // bundle written before D34 lacks it; those carry the SAME full scene list on every feature, so
  // the fallback flattens AND deduplicates by position — flattening alone drew each contact once
  // per feature (Ennore: 72 contacts rendered as 2,088 stacked markers). Independent of
  // `selectedDetectionId` and of `acts_available` gating already applied upstream in loadCase.ts —
  // `detections` is null on a D16 known-origin case, which this guards the same way
  // `darkVesselItems`/`infrastructureItems` guard on a null `suspects`.
  const shipDetectionItems = useMemo(() => {
    if (!detections) return [] as ShipDetectionMapItem[];
    if (detections.ship_detections) {
      return detections.ship_detections.map((sd) => ({ position: [sd.lon, sd.lat] as LonLat }));
    }
    const seen = new Set<string>();
    const items: ShipDetectionMapItem[] = [];
    for (const f of detections.features) {
      for (const sd of f.properties.ship_detections ?? []) {
        const key = `${sd.lon},${sd.lat}`;
        if (seen.has(key)) continue;
        seen.add(key);
        items.push({ position: [sd.lon, sd.lat] });
      }
    }
    return items;
  }, [detections]);

  const shipDetectionLayer = useMemo(() => {
    if (!detectRevealed || shipDetectionItems.length === 0) return null;
    return new ScatterplotLayer<ShipDetectionMapItem>({
      id: "ship-detections",
      data: shipDetectionItems,
      getPosition: (d) => d.position,
      getFillColor: SHIP_DETECTION_COLOR,
      getLineColor: SHIP_DETECTION_LINE_COLOR,
      getRadius: SHIP_DETECTION_RADIUS_PX,
      radiusUnits: "pixels",
      lineWidthUnits: "pixels",
      getLineWidth: 1.5,
      stroked: true,
      pickable: true,
    });
  }, [shipDetectionItems, detectRevealed]);

  // The Run-detection scan line. Driven by requestAnimationFrame only while `running` is
  // "detect"; at every other moment `scanFrac` is null and no layer exists.
  const [scanFrac, setScanFrac] = useState<number | null>(null);
  useEffect(() => {
    if (running !== "detect") {
      setScanFrac(null);
      return;
    }
    const start = performance.now();
    const total = RUN_DURATION_MS.detect;
    let raf = 0;
    const tick = (now: number) => {
      const f = Math.min(1, (now - start) / total);
      setScanFrac(f);
      if (f < 1) raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [running]);

  const scanLayers = useMemo(() => {
    if (scanFrac === null || !bounds) return [] as (PolygonLayer | PathLayer<LonLat[]>)[];
    const w = bounds.east - bounds.west;
    const x = bounds.west + w * scanFrac;
    const x0 = Math.max(bounds.west, x - w * 0.12);
    return [
      new PolygonLayer<LonLat[]>({
        id: "scan-band",
        data: [
          [
            [x0, bounds.south],
            [x, bounds.south],
            [x, bounds.north],
            [x0, bounds.north],
          ],
        ],
        getPolygon: (d) => d,
        getFillColor: SCAN_FILL,
        stroked: false,
        pickable: false,
      }),
      new PathLayer<LonLat[]>({
        id: "scan-edge",
        data: [
          [
            [x, bounds.south],
            [x, bounds.north],
          ],
        ],
        getPath: (d) => d,
        getColor: SCAN_EDGE,
        getWidth: 3,
        widthUnits: "pixels",
        pickable: false,
      }),
    ];
  }, [scanFrac, bounds]);

  // Create the map exactly once.
  useEffect(() => {
    if (!containerRef.current || mapRef.current) return;
    const b = useAppStore.getState().bounds;

    const map = new MlMap({
      container: containerRef.current,
      style: OCEAN_STYLE,
      center: b ? [(b.west + b.east) / 2, (b.south + b.north) / 2] : [80.4, 13.25],
      zoom: 8,
      attributionControl: false,
    });
    map.addControl(new NavigationControl({ showCompass: false }), "top-left");
    // Bottom-LEFT: the bottom-right corner is where the primary action lives on every stage,
    // and the compact attribution button was sitting underneath it.
    map.addControl(new AttributionControl({ compact: true }), "bottom-left");
    mapRef.current = map;

    // deck.gl particle layer rides on top of the map through a single MapboxOverlay control.
    // Overlaid (not interleaved) mode keeps it independent of the map's style/GL state — it
    // just tracks the camera. Layers are pushed in via overlay.setProps() from the effect
    // below; the map itself never re-renders when the timestep changes.
    // Hover tooltips carry the producer's own words — a dark-vessel marker shows its name (which
    // names an external contact source when there is one) and its reasons, verbatim.
    const overlay = new MapboxOverlay({
      interleaved: false,
      layers: [],
      getTooltip: ({ object, layer }) => {
        if (!object || !layer) return null;
        const style = {
          background: "#0b1624",
          color: "#e2e8f0",
          fontSize: "11px",
          maxWidth: "280px",
          padding: "8px 10px",
          borderRadius: "6px",
          lineHeight: "1.4",
        };
        if (layer.id === "dark-vessels") {
          const d = object as DarkVesselMapItem;
          return {
            html: `<b>${escapeHtml(d.name)}</b><br/>${d.reasons.map((r) => `– ${escapeHtml(r)}`).join("<br/>")}`,
            style,
          };
        }
        if (layer.id === "vessels") {
          const d = object as VesselMapItem;
          const role =
            d.role === "top" ? "top suspect" : d.role === "suspect" ? "suspect" :
            d.role === "excluded" ? "excluded" : "considered";
          return { html: `<b>${escapeHtml(d.name || d.mmsi)}</b><br/>MMSI ${escapeHtml(d.mmsi)} · ${role}`, style };
        }
        if (layer.id === "ship-detections") {
          return {
            html: "<b>Radar contact</b><br/>A bright point target found by UDGAM's ship detector. Whether it carried AIS is checked in Attribute.",
            style,
          };
        }
        return null;
      },
    });
    map.addControl(overlay as unknown as IControl);
    overlayRef.current = overlay;

    // "style.load", not "load": "load" waits for every initial tile, and when the Esri tiles
    // cannot be fetched (venue wifi down) it never fires — the SAR, detections and camera then
    // never initialise and the demo shows an empty basemap. Measured with the tile host blocked.
    // The style is inline, so "style.load" fires as soon as it is parsed, online or not.
    map.once("style.load", () => {
      if (styleReadyRef.current) return;
      styleReadyRef.current = true;
      setMapReady(true);
      const state = useAppStore.getState();
      const bb = state.bounds;
      if (bb) {
        map.addSource("sar", {
          type: "image",
          url: `/cases/${state.activeCaseId}/sar.png`,
          coordinates: imageCoordinates(bb),
        });
        map.addLayer({
          id: "sar-layer",
          type: "raster",
          source: "sar",
          paint: { "raster-opacity": 0.92, "raster-fade-duration": 0 },
        });
        map.fitBounds(
          [
            [bb.west, bb.south],
            [bb.east, bb.north],
          ],
          { padding: 40, animate: false },
        );
      }

      // The SAR footprint as a thin outline, so the scene stays findable when Trace or
      // Attribute zooms out to an origin far off the image.
      map.addSource("scene-footprint", {
        type: "geojson",
        data: footprintGeoJSON(bb),
      });
      map.addLayer({
        id: "scene-footprint-line",
        type: "line",
        source: "scene-footprint",
        paint: { "line-color": SCENE_OUTLINE_COLOR, "line-width": 1.5, "line-dasharray": [3, 2] },
      });

      map.addSource("detections", {
        type: "geojson",
        data: state.detections ?? { type: "FeatureCollection", features: [] },
      });
      map.addLayer({
        id: "det-fill",
        type: "fill",
        source: "detections",
        paint: {
          "fill-color": [
            "match",
            ["get", "classification"],
            "oil",
            OIL_COLOR,
            LOOKALIKE_COLOR,
          ],
          "fill-opacity": 0.18,
        },
      });
      // oil = solid red outline, look-alike = grey dashed (docs/team/harshita-frontend.md). Split into two layers
      // because line-dasharray is not reliably data-driven.
      map.addLayer({
        id: "det-outline-oil",
        type: "line",
        source: "detections",
        filter: ["==", ["get", "classification"], "oil"],
        paint: { "line-color": OIL_COLOR, "line-width": 2 },
      });
      map.addLayer({
        id: "det-outline-lookalike",
        type: "line",
        source: "detections",
        filter: ["==", ["get", "classification"], "lookalike"],
        paint: {
          "line-color": LOOKALIKE_COLOR,
          "line-width": 1.5,
          "line-dasharray": [2, 1.5],
        },
      });
      map.addLayer({
        id: "det-selected",
        type: "line",
        source: "detections",
        filter: ["==", ["get", "id"], "__none__"],
        // A selection GLOW, not a replacement outline. A solid white 3 px line sat on top of
        // the classification colour and hid it, so the selected feature stopped saying whether
        // it was oil — the one thing this layer exists to communicate. A wide, soft, low-alpha
        // white reads as "this is the one you picked" while the red/slate line shows through.
        paint: {
          "line-color": "#ffffff",
          "line-width": 6,
          "line-opacity": 0.28,
          "line-blur": 2,
        },
      });

      // Apply current visibility + selection immediately.
      syncVisibility(map);
      syncSelection(map);
    });

    map.on("click", "det-fill", (e) => {
      const id = e.features?.[0]?.properties?.id;
      if (typeof id === "string") {
        e.originalEvent.stopPropagation();
        useAppStore.getState().selectDetection(id);
      }
    });
    map.on("click", (e: MapMouseEvent) => {
      const hits = map.queryRenderedFeatures(e.point, { layers: ["det-fill"] });
      if (hits.length === 0) useAppStore.getState().selectDetection(null);
    });
    map.on("mouseenter", "det-fill", () => {
      map.getCanvas().style.cursor = "pointer";
    });
    map.on("mouseleave", "det-fill", () => {
      map.getCanvas().style.cursor = "";
    });

    return () => {
      map.remove(); // also disposes the MapboxOverlay control + its deck.gl instance
      mapRef.current = null;
      overlayRef.current = null;
      styleReadyRef.current = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Origin opacity — this is the ONLY thing about the origin layer that changes on a scrub.
  // 0 when Origin is toggled off. On Trace, the rewind fraction (0 at T−0, 1 at T−24h) runs
  // through a smoothstep, so the cloud is hidden near the detection time and eases in only as
  // the slider nears maximum rewind ("the origin becomes knowable the further back you drift",
  // docs/team/harshita-frontend.md §Phase 3). Taken from the integer timestep `t`, NOT the raw slider value, so it
  // changes at most n_steps times across a full scrub — never continuously as the handle drags.
  // Outside Trace (e.g. Attribute), there is no rewind narrative to earn — the toggle alone
  // should show the cloud at full opacity, since the footer's slider still defaults to T−0
  // (rewind 0) there and would otherwise make "Origin" a no-op until the user drags it.
  const originOpacity = useMemo(() => {
    if (!originVisible) return 0;
    if (activeStage !== "trace") return 1;
    const nSteps = particles?.nSteps ?? 0;
    const rewind = nSteps > 1 ? t / (nSteps - 1) : 0;
    return (
      ORIGIN_OPACITY_FLOOR +
      (1 - ORIGIN_OPACITY_FLOOR) * smoothstep(ORIGIN_FADE_IN_START, ORIGIN_FADE_IN_FULL, rewind)
    );
  }, [originVisible, activeStage, t, particles]);

  // Origin cloud + 50/90 % rings — the backdrop the particles rewind into, drawn UNDERNEATH
  // them. Ruling D11: a BitmapLayer, never a HeatmapLayer. HeatmapLayer aggregates its points
  // and renormalises colour in screen space, so the cloud's shape changes as a judge zooms —
  // indefensible for an uncertainty visual. The BitmapLayer samples a fixed 120×120 texture
  // through a fixed bilinear filter, so the cloud is identical at every zoom.
  //
  // Everything expensive is done ONCE and never on a scrub:
  //   - `originImage` (grid → RGBA texels) and `originRings` (km → ring polygons) are memoised
  //     on the bundle identity above;
  //   - the BitmapLayer uploads that one 120×120 texture when the bundle loads and keeps it for
  //     the life of the case — no aggregation, no per-texel reduction pass.
  // The T−24h → T−0 fade is therefore a pure `opacity` change, which deck.gl applies WITHOUT
  // re-uploading the texture. `origin` is read for `origin.bounds` — the origin grid's own
  // rectangle, NOT bounds.json (CONTRACTS §6, Master §5.6).
  const originLayerList = useMemo(() => {
    if (!originImage || !origin) return [] as (BitmapLayer | PathLayer<OriginRing>)[];
    const list: (BitmapLayer | PathLayer<OriginRing>)[] = [
      new BitmapLayer({
        id: "origin",
        image: originImage,
        bounds: [
          origin.bounds.west,
          origin.bounds.south,
          origin.bounds.east,
          origin.bounds.north,
        ],
        opacity: originOpacity,
        pickable: false,
      }),
    ];
    if (originRings) {
      list.push(
        new PathLayer<OriginRing>({
          id: "origin-radii",
          data: originRings,
          getPath: originRingPath,
          getColor: originRingColor,
          getWidth: ORIGIN_RING_WIDTH_PX,
          widthUnits: "pixels",
          widthMinPixels: 1,
          capRounded: true,
          jointRounded: true,
          opacity: originOpacity,
          pickable: false,
        }),
      );
    }
    return list;
  }, [originImage, origin, originRings, originOpacity]);

  // Forward cone + centroid track. Built once per bundle and toggled purely by visibility, so
  // turning it on costs nothing and a scrub never touches it.
  const forwardLayerList = useMemo(() => {
    if (!forwardVisible || !forwardRings || !forwardTrack) return [];
    return [
      new PathLayer<ForwardRing>({
        id: "forward-rings",
        data: forwardRings,
        getPath: forwardRingPath,
        getColor: forwardRingColor,
        getWidth: forwardRingWidth,
        widthUnits: "pixels",
        widthMinPixels: 1,
        capRounded: true,
        jointRounded: true,
        pickable: false,
      }),
      new PathLayer<{ path: LonLat[] }>({
        id: "forward-track",
        data: [{ path: forwardTrack }],
        getPath: (d) => d.path,
        getColor: FORWARD_TRACK_COLOR,
        getWidth: FORWARD_TRACK_WIDTH_PX,
        widthUnits: "pixels",
        widthMinPixels: 1,
        capRounded: true,
        jointRounded: true,
        pickable: false,
      }),
    ];
  }, [forwardVisible, forwardRings, forwardTrack]);

  // Particle cloud — one pre-built binary position frame per timestep (Phase 2). This is the
  // only deck layer that is rebuilt on every playback tick; `frames[t]` is a pre-computed view,
  // so nothing large is allocated here.
  const particleLayer = useMemo(() => {
    if (!particles || !particlesVisible) return null;
    const frame = particles.frames[t] ?? particles.frames[0];
    return new ScatterplotLayer({
      id: "particles",
      data: {
        length: particles.nParticles,
        attributes: { getPosition: { value: frame, size: 2 } },
      },
      getFillColor: PARTICLE_FILL,
      getLineColor: PARTICLE_LINE,
      getRadius: 2.2,
      radiusUnits: "pixels",
      radiusMinPixels: 1,
      radiusMaxPixels: 4,
      stroked: true,
      lineWidthUnits: "pixels",
      getLineWidth: 0.5,
      pickable: false,
    });
  }, [particles, particlesVisible, t]);

  // Push the composed list into the deck overlay. Order is bottom→top: origin bitmap, rings,
  // forward cone + centroid track, vessel tracks, particles, dark-vessel markers,
  // infrastructure markers, ship-detection
  // markers (all three point layers drawn last so none is ever hidden under a track line).
  // Runs only when one of the memoised pieces actually changes — never on a bare animation
  // frame — and never re-renders the map container.
  useEffect(() => {
    overlayRef.current?.setProps({
      layers: [
        ...originLayerList,
        ...forwardLayerList,
        vesselLayer,
        particleLayer,
        infrastructureLayer,
        shipDetectionLayer,
        // Last among the markers: a dark vessel is one of the ship detections, cross-checked, so
        // it sits exactly on a teal contact marker and must be drawn over it.
        darkVesselLayer,
        ...scanLayers,
      ],
    });
  }, [
    originLayerList,
    forwardLayerList,
    vesselLayer,
    particleLayer,
    darkVesselLayer,
    infrastructureLayer,
    shipDetectionLayer,
    scanLayers,
  ]);

  // SAR source follows the active case / bounds.
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !styleReadyRef.current || !bounds) return;
    const src = map.getSource("sar") as ImageSource | undefined;
    if (src) {
      src.updateImage({
        url: `/cases/${activeCaseId}/sar.png`,
        coordinates: imageCoordinates(bounds),
      });
    }
    (map.getSource("scene-footprint") as GeoJSONSource | undefined)?.setData(
      footprintGeoJSON(bounds),
    );
  }, [activeCaseId, bounds]);

  // Camera. Detect and Trace fit exactly to the scene raster — byte-identical to this file
  // before Phase 5, so their framing is unaffected by anything below. Attribute fits to the
  // union of the scene + every vessel track (lib/extent.ts) instead, because vessel tracks
  // legitimately run past the scene edge (they do even in the synthetic case-000 bundle) and a
  // scene-only camera would guarantee some are clipped.
  //
  // This is deliberately the ONLY stage-dependent camera behaviour in the app. It does not fold
  // in particles/origin extents and does not decide the larger per-stage-vs-global camera
  // question for them — that is a separate, larger decision (see docs/HANDOFF_HARSHITA…, §11.3 /
  // §16 D4) left for Akshat. `sceneAndVesselExtent` is a pure calculator with no opinion on when
  // to use it; this effect is the one place that opinion lives, and it only ever applies to the
  // Attribute stage.
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !styleReadyRef.current || !bounds) return;
    const target =
      activeStage === "attribute"
        ? // The origin cloud is what the vessels are scored against, so keep it in frame.
          sceneAndVesselExtent(origin ? unionGeo(bounds, origin.bounds) : bounds, vessels)
        : activeStage === "trace"
          ? sceneParticleOriginExtent(bounds, particles, origin)
          : bounds;
    map.fitBounds(
      [
        [target.west, target.south],
        [target.east, target.north],
      ],
      { padding: activeStage === "detect" ? 40 : 60, animate: false },
    );
  }, [activeStage, bounds, vessels, particles, origin, mapReady]);

  // Detection features follow the store.
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !styleReadyRef.current) return;
    const src = map.getSource("detections") as GeoJSONSource | undefined;
    src?.setData(detections ?? { type: "FeatureCollection", features: [] });
  }, [detections]);

  // Layer toggles.
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !styleReadyRef.current) return;
    syncVisibility(map);
  }, [layers.sar, layers.detections, detectRevealed]);

  // Selection highlight.
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !styleReadyRef.current) return;
    syncSelection(map);
  }, [selectedDetectionId]);

  // `!absolute` (not plain `absolute`): maplibre-gl.css sets `.maplibregl-map { position: relative }`
  // and that chunk loads after Tailwind, so an un-forced `absolute` utility loses the cascade —
  // the container then collapses to 0 height and the whole map is invisible.
  return <div ref={containerRef} className="!absolute inset-0" />;
}

function syncVisibility(map: MlMap) {
  const { layers, revealed } = useAppStore.getState();
  const showDetections = layers.detections && revealed.detect;
  const set = (id: string, visible: boolean) => {
    if (map.getLayer(id)) {
      map.setLayoutProperty(id, "visibility", visible ? "visible" : "none");
    }
  };
  set("sar-layer", layers.sar);
  set("det-fill", showDetections);
  set("det-outline-oil", showDetections);
  set("det-outline-lookalike", showDetections);
  set("det-selected", showDetections);
}

function syncSelection(map: MlMap) {
  const { selectedDetectionId } = useAppStore.getState();
  if (map.getLayer("det-selected")) {
    map.setFilter("det-selected", [
      "==",
      ["get", "id"],
      selectedDetectionId ?? "__none__",
    ]);
  }
}
