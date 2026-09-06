// In-memory app state. NO persistence, NO localStorage/sessionStorage — Zustand only.

import { create } from "zustand";
import type { Act, Bounds, CaseMeta, DetectionCollection } from "./contracts";
import { DEFAULT_CASE_ID } from "./cases";
import { loadCase } from "./loadCase";

export type LayerId = "sar" | "detections" | "particles" | "origin" | "vessels";

export type LoadStatus = "idle" | "loading" | "ready" | "error";

export interface AppState {
  activeCaseId: string;
  status: LoadStatus;
  error: string | null;

  meta: CaseMeta | null;
  bounds: Bounds | null;
  detections: DetectionCollection | null;

  activeStage: Act;
  selectedDetectionId: string | null;

  layers: Record<LayerId, boolean>;
  tNorm: number; // 0..1, 1 = "T-0 detect". Stored now; consumed in Phase 2.

  setActiveCase: (id: string) => void;
  loadActiveCase: () => Promise<void>;
  setStage: (stage: Act) => void;
  selectDetection: (id: string | null) => void;
  toggleLayer: (id: LayerId) => void;
  setTNorm: (t: number) => void;
}

export const useAppStore = create<AppState>((set, get) => ({
  activeCaseId: DEFAULT_CASE_ID,
  status: "idle",
  error: null,

  meta: null,
  bounds: null,
  detections: null,

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
    set({ status: "loading", error: null, selectedDetectionId: null });
    try {
      const { meta, bounds, detections } = await loadCase(id);
      // Guard against a stale response if the case was switched mid-fetch.
      if (get().activeCaseId !== id) return;
      const activeStage: Act = meta.acts_available.includes(get().activeStage)
        ? get().activeStage
        : meta.acts_available[0];
      set({ status: "ready", meta, bounds, detections, activeStage });
    } catch (err) {
      if (get().activeCaseId !== id) return;
      set({ status: "error", error: (err as Error).message });
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
}));
