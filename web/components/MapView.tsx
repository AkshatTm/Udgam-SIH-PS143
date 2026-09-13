"use client";

// The one map. MapLibre GL JS, no token, no external tiles — the SAR raster is the backdrop
// and a plain dark background keeps the demo offline-safe (docs/04 allows this).
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
import { BitmapLayer, PathLayer, ScatterplotLayer } from "@deck.gl/layers";
import { useAppStore } from "@/lib/store";
import { tFromNorm } from "@/lib/timestep";
import { buildOriginImage, buildOriginRadiusRings, type OriginRing } from "@/lib/origin";
import { sceneAndVesselExtent, sceneParticleOriginExtent } from "@/lib/extent";
import type { Bounds, LonLat } from "@/lib/contracts";

// maplibre-gl v6 loads its GeoJSON/vector tiler in a separate ESM worker. Its built-in worker
// resolver needs an http(s) `import.meta.url`, which webpack replaces with a build-time
// file:// path — so it falls back to `new Worker("")` and no vector source ever renders (the
// SAR image layer still works because it decodes on the main thread). Point maplibre at a
// static copy of the worker instead; `predev`/`prebuild` copy it into public/maplibre/.
setWorkerUrl("/maplibre/maplibre-gl-worker.mjs");

const DARK_STYLE: StyleSpecification = {
  version: 8,
  sources: {},
  layers: [
    { id: "bg", type: "background", paint: { "background-color": "#0b0f14" } },
  ],
};

const OIL_COLOR = "#ff4d4d";
const LOOKALIKE_COLOR = "#9aa4b2";

// Particle dots — warm amber on the dark SAR backdrop. Reads clearly against the grayscale SAR
// image and distinguishes particles from the vessel layer (cool blue, future). V3 palette.
const PARTICLE_FILL: [number, number, number, number] = [251, 146, 60, 210];

// Origin cloud fade. Rewind fraction (0 at T−0, 1 at T−24h) is run through a smoothstep so the
// cloud is fully hidden near the detection time and eases in only as the slider approaches
// maximum rewind — "the origin becomes knowable the further back you drift" (docs/04 §Phase 3).
// This is the ONLY thing about the origin layer that changes on a scrub: a pure `opacity` prop,
// which the BitmapLayer applies without re-uploading its texture. The colour ramp and the
// alpha-proportional mapping live in lib/origin.ts (buildOriginImage); Urooz owns the palette.
const ORIGIN_FADE_IN_START = 0.2; // rewind fraction at which the cloud starts to appear
const ORIGIN_FADE_IN_FULL = 0.9; // rewind fraction at which it reaches full opacity

// 50 % / 90 % origin-probability rings — warm amber-yellow outlines over the origin cloud. The
// inner (50 %) ring is brighter; the outer (90 %) ring is softer but still readable. Both
// complement the warm origin-cloud colour ramp rather than clashing with a white outline. V3 palette.
const ORIGIN_RING_50: [number, number, number, number] = [251, 191, 36, 230];
const ORIGIN_RING_90: [number, number, number, number] = [251, 191, 36, 140];
const ORIGIN_RING_WIDTH_PX = 1.5;

// Hoisted so their identity is stable across renders — the ring geometry is static, so these
// accessors must never look like they changed (which would ask deck.gl to re-tessellate).
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
  path: LonLat[];
  role: VesselRole;
}

const VESSEL_COLOR_PLAIN: [number, number, number, number] = [96, 165, 250, 140];
const VESSEL_COLOR_SUSPECT: [number, number, number, number] = [56, 189, 248, 200];
const VESSEL_COLOR_TOP_SUSPECT: [number, number, number, number] = [56, 189, 248, 255];
// Excluded — muted, per docs/06 ("visually ruled out"). The strikethrough motif itself is
// applied on the exclusion card in ContextPanel; a dashed line isn't a deck.gl PathLayer
// primitive, so the map conveys "ruled out" via reduced opacity + thin width instead.
const VESSEL_COLOR_EXCLUDED: [number, number, number, number] = [148, 163, 184, 120];

const VESSEL_WIDTH_PLAIN = 1.2;
const VESSEL_WIDTH_SUSPECT = 1.8;
const VESSEL_WIDTH_TOP_SUSPECT = 3;
const VESSEL_WIDTH_EXCLUDED = 1;

// docs/04 Phase 3.5 — dark vessels (Master §6.7). A radar contact with no AIS at all: a point,
// never a track, never linked to `vessels.geojson`. Deliberately its own colour family (rose),
// unused everywhere else in this app (blue = vessel, amber = particle/origin, red = oil,
// grey = look-alike/excluded) — an alert marker must not read as any of those.
interface DarkVesselMapItem {
  position: LonLat;
}
const DARK_VESSEL_COLOR: [number, number, number, number] = [244, 63, 94, 235];
const DARK_VESSEL_LINE_COLOR: [number, number, number, number] = [255, 255, 255, 200];
const DARK_VESSEL_RADIUS_PX = 7;

// docs/04 Phase 3.6 — infrastructure findings (Master §6.7). Also a stationary point with no
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

// docs/04 Phase 5.3 — ship_detections (Master §6.3, D34). Soum's RAW radar contacts for the whole
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
const SHIP_DETECTION_LINE_COLOR: [number, number, number, number] = [255, 255, 255, 200];
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

  // Phase 5 attribution. `vessels` is static geometry (no timestep dependency at all) — the
  // PathLayer built from it is memoised on the bundle + suspects identity, never on `t`.
  const vessels = useAppStore((s) => s.vessels);
  const vesselsVisible = useAppStore((s) => s.layers.vessels);
  const suspects = useAppStore((s) => s.suspects);
  // docs/04 Phase 3.3 — hover-to-highlight. Purely presentational: never touches vesselItems
  // (the parsed track geometry), never refetches, never rebuilds the map or its camera.
  const hoveredMmsi = useAppStore((s) => s.hoveredSuspectMmsi);

  // Role (top suspect / suspect / excluded) is only ever attached once origin.abstain is
  // confirmed false — see the comment on VesselRole above. `origin` is read from the store
  // above (Phase 3 origin cloud); this reuses that same value rather than re-fetching anything.
  const abstainConfirmedFalse = origin !== null && origin.abstain === false;

  const vesselItems = useMemo(() => {
    if (!vessels) return [] as VesselMapItem[];
    if (!abstainConfirmedFalse || !suspects) {
      return vessels.tracks.map((t) => ({ mmsi: t.mmsi, path: t.path, role: "plain" as const }));
    }
    const topMmsi = suspects.suspects[0]?.mmsi;
    const suspectMmsi = new Set(suspects.suspects.map((s) => s.mmsi));
    const excludedMmsi = new Set(suspects.excluded.map((e) => e.mmsi));
    return vessels.tracks.map((t) => {
      let role: VesselRole = "plain";
      if (t.mmsi === topMmsi) role = "top";
      else if (suspectMmsi.has(t.mmsi)) role = "suspect";
      else if (excludedMmsi.has(t.mmsi)) role = "excluded";
      return { mmsi: t.mmsi, path: t.path, role };
    });
  }, [vessels, suspects, abstainConfirmedFalse]);

  const vesselLayer = useMemo(() => {
    if (!vesselsVisible || vesselItems.length === 0) return null;
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
      pickable: false,
      updateTriggers: { getColor: [hoveredMmsi], getWidth: [hoveredMmsi] },
    });
  }, [vesselItems, vesselsVisible, hoveredMmsi]);

  // docs/04 Phase 3.5 — dark-vessel markers. Independent of `vesselsVisible` on purpose: the
  // whole point of the AIS-off reveal (docs/05 §3.3) is that toggling the AIS track layer off
  // leaves this marker alone with nothing beneath it. No mmsi exists to share with the hover
  // highlight (Phase 3.3) or the vessel PathLayer, so the two features cannot collide.
  const darkVesselItems = useMemo(() => {
    if (!suspects) return [] as DarkVesselMapItem[];
    return suspects.darkVessels.map((dv) => ({ position: [dv.lon, dv.lat] as LonLat }));
  }, [suspects]);

  const darkVesselLayer = useMemo(() => {
    if (darkVesselItems.length === 0) return null;
    return new ScatterplotLayer<DarkVesselMapItem>({
      id: "dark-vessels",
      data: darkVesselItems,
      getPosition: (d) => d.position,
      getFillColor: DARK_VESSEL_COLOR,
      getLineColor: DARK_VESSEL_LINE_COLOR,
      getRadius: DARK_VESSEL_RADIUS_PX,
      radiusUnits: "pixels",
      lineWidthUnits: "pixels",
      getLineWidth: 1.5,
      stroked: true,
      pickable: false,
    });
  }, [darkVesselItems]);

  // docs/04 Phase 3.6 — infrastructure markers. Same independent-of-`vesselsVisible` reasoning
  // as dark vessels doesn't apply here (no toggle-driven reveal is described for infrastructure
  // in any doc) — it simply renders whenever the bundle has findings, like the dark-vessel layer.
  const infrastructureItems = useMemo(() => {
    if (!suspects) return [] as InfrastructureMapItem[];
    return suspects.infrastructure.map((inf) => ({ position: [inf.lon, inf.lat] as LonLat }));
  }, [suspects]);

  const infrastructureLayer = useMemo(() => {
    if (infrastructureItems.length === 0) return null;
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
  }, [infrastructureItems]);

  // docs/04 Phase 5.3 — ship_detections (Master §6.3, D34). Read the top-level scene list. Only a
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
    if (shipDetectionItems.length === 0) return null;
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
      pickable: false,
    });
  }, [shipDetectionItems]);

  // Create the map exactly once.
  useEffect(() => {
    if (!containerRef.current || mapRef.current) return;
    const b = useAppStore.getState().bounds;

    const map = new MlMap({
      container: containerRef.current,
      style: DARK_STYLE,
      center: b ? [(b.west + b.east) / 2, (b.south + b.north) / 2] : [80.4, 13.25],
      zoom: 8,
      attributionControl: false,
    });
    map.addControl(new NavigationControl({ showCompass: false }), "top-left");
    mapRef.current = map;

    // deck.gl particle layer rides on top of the map through a single MapboxOverlay control.
    // Overlaid (not interleaved) mode keeps it independent of the map's style/GL state — it
    // just tracks the camera. Layers are pushed in via overlay.setProps() from the effect
    // below; the map itself never re-renders when the timestep changes.
    const overlay = new MapboxOverlay({ interleaved: false, layers: [] });
    map.addControl(overlay as unknown as IControl);
    overlayRef.current = overlay;

    map.on("load", () => {
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
      // oil = solid red outline, look-alike = grey dashed (docs/04). Split into two layers
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
        paint: { "line-color": "#ffffff", "line-width": 3 },
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
  // 0 when Origin is toggled off. Otherwise the rewind fraction (0 at T−0, 1 at T−24h) run
  // through a smoothstep, so the cloud is hidden near the detection time and eases in only as
  // the slider nears maximum rewind ("the origin becomes knowable the further back you drift",
  // docs/04 §Phase 3). Taken from the integer timestep `t`, NOT the raw slider value, so it
  // changes at most n_steps times across a full scrub — never continuously as the handle drags.
  const originOpacity = useMemo(() => {
    if (!originVisible) return 0;
    const nSteps = particles?.nSteps ?? 0;
    const rewind = nSteps > 1 ? t / (nSteps - 1) : 0;
    return smoothstep(ORIGIN_FADE_IN_START, ORIGIN_FADE_IN_FULL, rewind);
  }, [originVisible, t, particles]);

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
      getRadius: 2,
      radiusUnits: "pixels",
      radiusMinPixels: 1,
      radiusMaxPixels: 4,
      stroked: false,
      pickable: false,
    });
  }, [particles, particlesVisible, t]);

  // Push the composed list into the deck overlay. Order is bottom→top: origin bitmap, rings,
  // vessel tracks, particles, dark-vessel markers, infrastructure markers, ship-detection
  // markers (all three point layers drawn last so none is ever hidden under a track line).
  // Runs only when one of the memoised pieces actually changes — never on a bare animation
  // frame — and never re-renders the map container.
  useEffect(() => {
    overlayRef.current?.setProps({
      layers: [
        ...originLayerList,
        vesselLayer,
        particleLayer,
        darkVesselLayer,
        infrastructureLayer,
        shipDetectionLayer,
      ],
    });
  }, [
    originLayerList,
    vesselLayer,
    particleLayer,
    darkVesselLayer,
    infrastructureLayer,
    shipDetectionLayer,
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
        ? sceneAndVesselExtent(bounds, vessels)
        : activeStage === "trace"
          ? sceneParticleOriginExtent(bounds, particles, origin)
          : bounds;
    map.fitBounds(
      [
        [target.west, target.south],
        [target.east, target.north],
      ],
      { padding: 40, animate: false },
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
  }, [layers.sar, layers.detections]);

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
  const { layers } = useAppStore.getState();
  const set = (id: string, visible: boolean) => {
    if (map.getLayer(id)) {
      map.setLayoutProperty(id, "visibility", visible ? "visible" : "none");
    }
  };
  set("sar-layer", layers.sar);
  set("det-fill", layers.detections);
  set("det-outline-oil", layers.detections);
  set("det-outline-lookalike", layers.detections);
  set("det-selected", layers.detections);
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
