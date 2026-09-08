"use client";

// The one map. MapLibre GL JS, no token, no external tiles — the SAR raster is the backdrop
// and a plain dark background keeps the demo offline-safe (docs/04 allows this).
//
// The map object is created once. Store changes (case, layer visibility, selection) are pushed
// in via imperative map calls in effects — the map container never re-renders on those.
// deck.gl rides on top through a single MapboxOverlay control (created once, next to the map).
// The layer list is composed from two memoised pieces and pushed via one effect:
//   - the particle ScatterplotLayer (Phase 2) — the only layer that changes every playback tick;
//   - the origin HeatmapLayer + 50/90 % radius rings (Phase 3) — built ONCE per origin bundle,
//     mounted as soon as the bundle loads and kept mounted for the life of the case, with the
//     T−24h→T−0 fade (and the Origin toggle) driven purely by `opacity`. deck.gl never re-runs
//     the expensive heatmap aggregation on a scrub — only the fully-faded pixels change.
// The timestep only ever updates deck layers, never the map.

import { useEffect, useMemo, useRef } from "react";
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
import { PathLayer, ScatterplotLayer } from "@deck.gl/layers";
import { HeatmapLayer } from "@deck.gl/aggregation-layers";
import { useAppStore } from "@/lib/store";
import { tFromNorm } from "@/lib/timestep";
import { buildOriginPointCloud, buildOriginRadiusRings, type OriginRing } from "@/lib/origin";
import type { Bounds } from "@/lib/contracts";

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

// Particle dots — a bright sky tone that reads on the dark SAR backdrop. Urooz owns final
// tokens; behaviour is what matters here.
const PARTICLE_FILL: [number, number, number, number] = [125, 211, 252, 190];

// Origin heatmap fade. Rewind fraction (0 at T−0, 1 at T−24h) is run through a smoothstep so
// the cloud is fully hidden near the detection time and eases in only as the slider approaches
// maximum rewind — "the origin becomes knowable the further back you drift" (docs/04 §Phase 3).
const ORIGIN_FADE_IN_START = 0.2; // rewind fraction at which the cloud starts to appear
const ORIGIN_FADE_IN_FULL = 0.9; // rewind fraction at which it reaches full opacity
// The origin grid has a long low-probability tail (~90 % of cells are non-zero), so keep the
// blur radius tight and push the transparency threshold up — that concentrates the visible
// cloud near the actual mass instead of blooming across the whole scene. The precise
// 50 % / 90 % extent is carried by the rings below; Urooz owns the final colour tokens.
const ORIGIN_RADIUS_PIXELS = 28;
const ORIGIN_INTENSITY = 0.6;
const ORIGIN_THRESHOLD = 0.18;
// HeatmapLayer aggregates its weighted points into a square GPU texture and then does a
// point-per-texel max-reduction pass. The default size is 2048 → a 4.2 M-vertex reduction
// that stalls integrated GPUs for ~1.6 s the first time it runs (measured on Intel UHD). The
// origin grid is only 120×120 over ~0.6°, so 512 is already finer than the data — it cuts
// that one-time cost ~16× while leaving the cloud visually identical.
const ORIGIN_WEIGHTS_TEXTURE_SIZE = 512;

// 50 % / 90 % origin-probability rings, drawn as thin white outlines over the heatmap. The
// inner (50 %) ring is a touch brighter; the outer (90 %) ring is slightly softer but still
// clearly readable where it crosses the bright part of the heatmap. Urooz owns final tokens.
const ORIGIN_RING_50: [number, number, number, number] = [255, 255, 255, 245];
const ORIGIN_RING_90: [number, number, number, number] = [255, 255, 255, 210];
const ORIGIN_RING_WIDTH_PX = 2;

// Hoisted so their identity is stable across renders — the ring geometry is static, so these
// accessors must never look like they changed (which would ask deck.gl to re-tessellate).
const originRingPath = (d: OriginRing): OriginRing["path"] => d.path;
const originRingColor = (d: OriginRing): [number, number, number, number] =>
  d.kind === "r50" ? ORIGIN_RING_50 : ORIGIN_RING_90;

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

  const activeCaseId = useAppStore((s) => s.activeCaseId);
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
  // grid is expanded once into a weighted [lon,lat] point cloud and memoised on the bundle
  // identity — it is never rebuilt on a scrub, and origin.json is never re-fetched.
  const origin = useAppStore((s) => s.origin);
  const originVisible = useAppStore((s) => s.layers.origin);
  const originCloud = useMemo(
    () => (origin ? buildOriginPointCloud(origin) : null),
    [origin],
  );
  // 50 % / 90 % rings around origin.centroid, using radius_50_km / radius_90_km. Built once
  // per bundle — the km→degree conversion never runs on a scrub (see lib/origin.ts).
  const originRings = useMemo(
    () => (origin ? buildOriginRadiusRings(origin) : null),
    [origin],
  );

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

  // Origin opacity — this is the ONLY thing about the origin layers that changes on a scrub.
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

  // Origin heatmap + 50/90 % rings — the backdrop the particles rewind into, drawn UNDERNEATH
  // them. Everything expensive about these layers is done ONCE, up front, and never on a scrub:
  //   - `originCloud` / `originRings` (grid → weighted points, km → ring polygons) are memoised
  //     on the bundle identity above;
  //   - the HeatmapLayer aggregates its points into a GPU texture and compiles three shader
  //     programs the first time it is drawn. That cost (~1 s wall, mostly async, on integrated
  //     GPUs) is paid as soon as the origin bundle loads, because the layers mount then and are
  //     kept mounted and drawn for the life of the case.
  // The T−24h → T−0 fade is therefore a pure `opacity` change, which deck.gl applies WITHOUT
  // re-aggregating or re-tessellating. Removing the layers from the list on fade-out instead
  // made deck.gl re-mount + re-aggregate on every re-entry — the 0.3–1.8 s "slider freeze"
  // this file used to have.
  const originLayerList = useMemo(() => {
    if (!originCloud) return [] as (HeatmapLayer | PathLayer<OriginRing>)[];
    const list: (HeatmapLayer | PathLayer<OriginRing>)[] = [
      new HeatmapLayer({
        id: "origin",
        data: originCloud,
        radiusPixels: ORIGIN_RADIUS_PIXELS,
        intensity: ORIGIN_INTENSITY,
        threshold: ORIGIN_THRESHOLD,
        weightsTextureSize: ORIGIN_WEIGHTS_TEXTURE_SIZE,
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
  }, [originCloud, originRings, originOpacity]);

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
      radiusMaxPixels: 3,
      stroked: false,
      pickable: false,
    });
  }, [particles, particlesVisible, t]);

  // Push the composed list into the deck overlay. Order is bottom→top: heatmap, rings,
  // particles. Runs only when one of the memoised pieces actually changes — never on a bare
  // animation frame — and never re-renders the map container.
  useEffect(() => {
    overlayRef.current?.setProps({ layers: [...originLayerList, particleLayer] });
  }, [originLayerList, particleLayer]);

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
    map.fitBounds(
      [
        [bounds.west, bounds.south],
        [bounds.east, bounds.north],
      ],
      { padding: 40, animate: false },
    );
  }, [activeCaseId, bounds]);

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
