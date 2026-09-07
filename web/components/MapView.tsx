"use client";

// The one map. MapLibre GL JS, no token, no external tiles — the SAR raster is the backdrop
// and a plain dark background keeps the demo offline-safe (docs/04 allows this).
//
// The map object is created once. Store changes (case, layer visibility, selection) are pushed
// in via imperative map calls in effects — the map container never re-renders on those.
// deck.gl / MapboxOverlay is intentionally NOT wired here yet; it arrives in Phase 2 with the
// particle ScatterplotLayer.

import { useEffect, useRef } from "react";
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
import { ScatterplotLayer } from "@deck.gl/layers";
import { useAppStore } from "@/lib/store";
import { tFromNorm } from "@/lib/timestep";
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

  // Particle frame. Runs only when the integer timestep, the toggle, or the (once-loaded)
  // bundle changes — NOT on every animation frame, and never re-fetching particles.json.
  // A new ScatterplotLayer with a fresh `data` object is deck.gl's signal to re-upload the
  // position buffer; `frames[t]` is a pre-built view, so no particle array is allocated here.
  useEffect(() => {
    const overlay = overlayRef.current;
    if (!overlay) return;

    if (!particles || !particlesVisible) {
      overlay.setProps({ layers: [] });
      return;
    }

    const frame = particles.frames[t] ?? particles.frames[0];
    overlay.setProps({
      layers: [
        new ScatterplotLayer({
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
        }),
      ],
    });
  }, [particles, particlesVisible, t]);

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
