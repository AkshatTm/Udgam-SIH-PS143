// In-memory app state. NO persistence, NO localStorage/sessionStorage — Zustand only.

import { create } from "zustand";
import type { Act, Bounds, CaseMeta, DetectionCollection } from "./contracts";
import { DEFAULT_CASE_ID } from "./cases";
import { loadCase } from "./loadCase";
import { loadParticleBundle, type ParticleBundle } from "./particles";
import { loadOriginBundle, type OriginBundle } from "./origin";
import { loadVesselBundle, type VesselBundle } from "./vessels";
import { loadSuspectsBundle, type SuspectsBundle } from "./suspects";
import { loadVerificationBundle, type VerificationBundle } from "./verification";

export type LayerId = "sar" | "detections" | "particles" | "origin" | "vessels";

export type LoadStatus = "idle" | "loading" | "ready" | "error";

export interface AppState {
  activeCaseId: string;
  status: LoadStatus;
  error: string | null;

  meta: CaseMeta | null;
  bounds: Bounds | null;
  detections: DetectionCollection | null;
  /** The case offers `detect` but Stage 1 has not written detections.geojson yet. The Detect
   *  screen shows the SAR scene and says so, instead of rendering an empty map that reads as
   *  a broken feature. Distinct from `detections: null` on a case with no `detect` act. */
  detectionsPending: boolean;

  // Phase 2 particle playback. The bundle is fetched + parsed once per case and then only
  // indexed by timestep — never re-fetched or re-parsed while the slider moves.
  particles: ParticleBundle | null;
  particlesStatus: LoadStatus;
  particlesError: string | null;
  playing: boolean;
  // Slice 2 — true only while the one-time Trace arrival rewind is running. It lets
  // usePlayback pick the fast AUTOPLAY_STEPS_PER_SEC clock for that first pass and the
  // slower PLAYBACK_STEPS_PER_SEC for every manual play. Set by initTrace(); cleared by
  // every path that stops playback (setPlaying(false) / togglePlaying → paused / case load).
  autoPlaying: boolean;
  // Slice 1 — which case has run its one-time Trace arrival init (particle + origin layers
  // on, autoplay the rewind from T−0). In memory only: a page reload is a fresh session and
  // re-inits. `null` until a case's first Trace visit; reset on every case load.
  traceInitFor: string | null;

  // Phase 3 origin cloud. Same discipline as particles: fetched + parsed once per case, then
  // only read from memory — never re-fetched or re-parsed while the slider moves. MapView
  // consumes it: the origin HeatmapLayer + 50/90 % rings and the Trace-stage origin card are
  // both derived from this bundle.
  origin: OriginBundle | null;
  originStatus: LoadStatus;
  originError: string | null;

  // Phase 5 attribution. Same discipline as particles/origin: fetched + parsed once per case,
  // then only read from memory. `vessels` feeds the map's vessel PathLayer; `suspects` feeds
  // the Attribute context panel. They are independent of each other — a vessel-track failure
  // does not block the suspect cards, and vice versa.
  vessels: VesselBundle | null;
  vesselsStatus: LoadStatus;
  vesselsError: string | null;

  suspects: SuspectsBundle | null;
  suspectsStatus: LoadStatus;
  suspectsError: string | null;

  // Phase 4 (P1.1) verification. Same discipline as origin/suspects: fetched + parsed once per
  // case, then read from memory. Feeds the Verify screen only. Loaded in the background when
  // `verify` is in acts_available — never blocks the shell.
  verification: VerificationBundle | null;
  verificationStatus: LoadStatus;
  verificationError: string | null;

  activeStage: Act;
  selectedDetectionId: string | null;

  layers: Record<LayerId, boolean>;
  tNorm: number; // 0..1, 1 = "T-0 detect". Bound to an integer timestep via lib/timestep.ts.

  setActiveCase: (id: string) => void;
  loadActiveCase: () => Promise<void>;
  loadParticles: () => Promise<void>;
  loadOrigin: () => Promise<void>;
  loadVessels: () => Promise<void>;
  loadSuspects: () => Promise<void>;
  loadVerification: () => Promise<void>;
  setStage: (stage: Act) => void;
  selectDetection: (id: string | null) => void;
  toggleLayer: (id: LayerId) => void;
  setTNorm: (t: number) => void;
  setPlaying: (p: boolean) => void;
  togglePlaying: () => void;
  /** One-time Trace-stage arrival: enable the particle + origin layers and autoplay the
   *  rewind from T−0. No-ops unless particles + origin are both `ready` and this case has not
   *  been initialised yet, so it is safe to call on every render. */
  initTrace: () => void;
}

/** The `id` of the highest-confidence `"oil"` detection (first in file order on a tie), or
 *  `null` when the scene has no oil features. Reads the collection only — never mutates it. */
function bestOilDetectionId(d: DetectionCollection | null): string | null {
  if (d === null) return null;
  let bestId: string | null = null;
  let bestConf = -Infinity;
  for (const f of d.features) {
    const p = f.properties;
    if (p.classification !== "oil") continue;
    const conf = Number.isFinite(p.confidence) ? p.confidence : -Infinity;
    if (bestId === null || conf > bestConf) {
      bestId = p.id;
      bestConf = conf;
    }
  }
  return bestId;
}

export const useAppStore = create<AppState>((set, get) => ({
  activeCaseId: DEFAULT_CASE_ID,
  status: "idle",
  error: null,

  meta: null,
  bounds: null,
  detections: null,
  detectionsPending: false,

  particles: null,
  particlesStatus: "idle",
  particlesError: null,
  playing: false,
  autoPlaying: false,
  traceInitFor: null,

  origin: null,
  originStatus: "idle",
  originError: null,

  vessels: null,
  vesselsStatus: "idle",
  vesselsError: null,

  suspects: null,
  suspectsStatus: "idle",
  suspectsError: null,

  verification: null,
  verificationStatus: "idle",
  verificationError: null,

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
      // Reset Stage 1 state for the incoming case, so a pending banner from the previous
      // case can never bleed onto one whose detections did load.
      detections: null,
      detectionsPending: false,
      // Reset playback state for the incoming case.
      particles: null,
      particlesStatus: "idle",
      particlesError: null,
      playing: false,
      autoPlaying: false,
      traceInitFor: null,
      tNorm: 1,
      // Reset the origin cloud for the incoming case.
      origin: null,
      originStatus: "idle",
      originError: null,
      // Reset attribution for the incoming case.
      vessels: null,
      vesselsStatus: "idle",
      vesselsError: null,
      suspects: null,
      suspectsStatus: "idle",
      suspectsError: null,
      // Reset verification for the incoming case.
      verification: null,
      verificationStatus: "idle",
      verificationError: null,
    });
    try {
      const { meta, bounds, detections, detectionsPending } = await loadCase(id);
      // Guard against a stale response if the case was switched mid-fetch.
      if (get().activeCaseId !== id) return;
      const activeStage: Act = meta.acts_available.includes(get().activeStage)
        ? get().activeStage
        : meta.acts_available[0];
      set({
        status: "ready",
        meta,
        bounds,
        detections,
        detectionsPending,
        activeStage,
        // Detect arrives with the best oil detection already selected (docs/04 C1).
        selectedDetectionId: bestOilDetectionId(detections),
      });
      // Fetch the trace-stage bundles in the background — they must not block the map /
      // detections. Both files are required whenever the `trace` act is available (CONTRACTS §1).
      if (meta.acts_available.includes("trace")) {
        void get().loadParticles();
        void get().loadOrigin();
      }
      // Fetch the attribution bundles in the background. CONTRACTS §1: `attribute` requires
      // vessels.geojson + suspects.json (and trace, so origin.abstain is always available
      // alongside them — the Attribute panel depends on that to gate the suspect list).
      if (meta.acts_available.includes("attribute")) {
        void get().loadVessels();
        void get().loadSuspects();
      }
      // Fetch the Verify bundle in the background. CONTRACTS §6.1: `verify` in acts_available
      // guarantees verification.json exists (the validator enforces it).
      if (meta.acts_available.includes("verify")) {
        void get().loadVerification();
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

  loadOrigin: async () => {
    const id = get().activeCaseId;
    if (get().originStatus === "loading") return;
    set({ originStatus: "loading", originError: null });
    try {
      const bundle = await loadOriginBundle(id);
      // A different case was selected while this bundle was in flight — drop it.
      if (get().activeCaseId !== id) return;
      set({ origin: bundle, originStatus: "ready" });
    } catch (err) {
      if (get().activeCaseId !== id) return;
      set({ origin: null, originStatus: "error", originError: (err as Error).message });
    }
  },

  loadVessels: async () => {
    const id = get().activeCaseId;
    if (get().vesselsStatus === "loading") return;
    set({ vesselsStatus: "loading", vesselsError: null });
    try {
      const bundle = await loadVesselBundle(id);
      // A different case was selected while this bundle was in flight — drop it.
      if (get().activeCaseId !== id) return;
      set({ vessels: bundle, vesselsStatus: "ready" });
    } catch (err) {
      if (get().activeCaseId !== id) return;
      set({ vessels: null, vesselsStatus: "error", vesselsError: (err as Error).message });
    }
  },

  loadSuspects: async () => {
    const id = get().activeCaseId;
    if (get().suspectsStatus === "loading") return;
    set({ suspectsStatus: "loading", suspectsError: null });
    try {
      const bundle = await loadSuspectsBundle(id);
      // A different case was selected while this bundle was in flight — drop it.
      if (get().activeCaseId !== id) return;
      set({ suspects: bundle, suspectsStatus: "ready" });
    } catch (err) {
      if (get().activeCaseId !== id) return;
      set({ suspects: null, suspectsStatus: "error", suspectsError: (err as Error).message });
    }
  },

  loadVerification: async () => {
    const id = get().activeCaseId;
    if (get().verificationStatus === "loading") return;
    set({ verificationStatus: "loading", verificationError: null });
    try {
      const bundle = await loadVerificationBundle(id);
      // A different case was selected while this bundle was in flight — drop it.
      if (get().activeCaseId !== id) return;
      set({ verification: bundle, verificationStatus: "ready" });
    } catch (err) {
      if (get().activeCaseId !== id) return;
      set({
        verification: null,
        verificationStatus: "error",
        verificationError: (err as Error).message,
      });
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
  // Stopping playback always clears the autoplay flag, so a resumed play is manual speed.
  setPlaying: (p) => set(p ? { playing: true } : { playing: false, autoPlaying: false }),
  togglePlaying: () =>
    set((s) => (s.playing ? { playing: false, autoPlaying: false } : { playing: true })),

  initTrace: () => {
    const s = get();
    if (s.traceInitFor === s.activeCaseId) return; // already initialised this case
    if (s.particlesStatus !== "ready" || s.originStatus !== "ready") return; // wait for data
    set((st) => ({
      traceInitFor: s.activeCaseId,
      layers: { ...st.layers, particles: true, origin: true },
      tNorm: 1, // T−0 / positions[0]
      playing: true, // existing usePlayback rewinds T−0 → T−24h once, then stops
      autoPlaying: true, // Slice 2 — run that first rewind at AUTOPLAY_STEPS_PER_SEC
    }));
  },
}));
