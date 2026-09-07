// In-memory app state. NO persistence, NO localStorage/sessionStorage — Zustand only.

import { create } from "zustand";
import type { Act, Bounds, CaseMeta, DetectionCollection } from "./contracts";
import { DEFAULT_CASE_ID } from "./cases";
import { loadCase } from "./loadCase";
import { loadParticleBundle, type ParticleBundle } from "./particles";

export type LayerId = "sar" | "detections" | "particles" | "origin" | "vessels";

export type LoadStatus = "idle" | "loading" | "ready" | "error";

export interface AppState {
  activeCaseId: string;
  status: LoadStatus;
  error: string | null;

  meta: CaseMeta | null;
  bounds: Bounds | null;
  detections: DetectionCollection | null;

  // Phase 2 particle playback. The bundle is fetched + parsed once per case and then only
  // indexed by timestep — never re-fetched or re-parsed while the slider moves.
  particles: ParticleBundle | null;
  particlesStatus: LoadStatus;
  particlesError: string | null;
  playing: boolean;

  activeStage: Act;
  selectedDetectionId: string | null;

  layers: Record<LayerId, boolean>;
  tNorm: number; // 0..1, 1 = "T-0 detect". Bound to an integer timestep via lib/timestep.ts.

  setActiveCase: (id: string) => void;
  loadActiveCase: () => Promise<void>;
  loadParticles: () => Promise<void>;
  setStage: (stage: Act) => void;
  selectDetection: (id: string | null) => void;
  toggleLayer: (id: LayerId) => void;
  setTNorm: (t: number) => void;
  setPlaying: (p: boolean) => void;
  togglePlaying: () => void;
}

export const useAppStore = create<AppState>((set, get) => ({
  activeCaseId: DEFAULT_CASE_ID,
  status: "idle",
  error: null,

  meta: null,
  bounds: null,
  detections: null,

  particles: null,
  particlesStatus: "idle",
  particlesError: null,
  playing: false,

  activeStage: "detect",
  selectedDetectionId: null,

  layers: {
    sar: true,
    detections: true,
    particles: false,
    origin: false,
    vessels: false,
  },
  tNorm: 1,

  setActiveCase: (id) => {
    if (id === get().activeCaseId) return;
    set({ activeCaseId: id });
    void get().loadActiveCase();
  },

  loadActiveCase: async () => {
    const id = get().activeCaseId;
    set({
      status: "loading",
      error: null,
      selectedDetectionId: null,
      // Reset playback state for the incoming case.
      particles: null,
      particlesStatus: "idle",
      particlesError: null,
      playing: false,
      tNorm: 1,
    });
    try {
      const { meta, bounds, detections } = await loadCase(id);
      // Guard against a stale response if the case was switched mid-fetch.
      if (get().activeCaseId !== id) return;
      const activeStage: Act = meta.acts_available.includes(get().activeStage)
        ? get().activeStage
        : meta.acts_available[0];
      set({ status: "ready", meta, bounds, detections, activeStage });
      // Fetch the particle bundle in the background — it must not block the map / detections.
      if (meta.acts_available.includes("trace")) {
        void get().loadParticles();
      }
    } catch (err) {
      if (get().activeCaseId !== id) return;
      set({ status: "error", error: (err as Error).message });
    }
  },

  loadParticles: async () => {
    const id = get().activeCaseId;
    if (get().particlesStatus === "loading") return;
    set({ particlesStatus: "loading", particlesError: null });
    try {
      const bundle = await loadParticleBundle(id);
      // A different case was selected while this bundle was in flight — drop it.
      if (get().activeCaseId !== id) return;
      const meta = get().meta;
      if (meta) {
        // CONTRACTS §5: particles.t0 must match meta.detection_time within 60 s.
        const dt = Date.parse(meta.detection_time);
        const t0 = Date.parse(bundle.t0);
        if (Number.isFinite(dt) && Number.isFinite(t0) && Math.abs(dt - t0) > 60_000) {
          set({
            particles: null,
            particlesStatus: "error",
            particlesError: `particles.json t0 (${bundle.t0}) does not match meta detection_time (${meta.detection_time})`,
          });
          return;
        }
      }
      set({ particles: bundle, particlesStatus: "ready" });
    } catch (err) {
      if (get().activeCaseId !== id) return;
      set({ particles: null, particlesStatus: "error", particlesError: (err as Error).message });
    }
  },

  setStage: (stage) => {
    const meta = get().meta;
    if (meta && !meta.acts_available.includes(stage)) return;
    set({ activeStage: stage });
  },

  selectDetection: (id) => set({ selectedDetectionId: id }),

  toggleLayer: (id) =>
    set((s) => ({ layers: { ...s.layers, [id]: !s.layers[id] } })),

  setTNorm: (t) => set({ tNorm: Math.min(1, Math.max(0, t)) }),
  setPlaying: (p) => set({ playing: p }),
  togglePlaying: () => set((s) => ({ playing: !s.playing })),
}));
