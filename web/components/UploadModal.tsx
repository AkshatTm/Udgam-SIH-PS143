"use client";

// Hero-level entry point that replaced the "Upload your own scene" card that used to sit as a
// tenth tile in the case grid (nine cases is a clean 3x3 there — a tenth card broke that).
// Same job, now a popup: left picks the SAR GeoTIFF, right captures where/when it was taken.
//
// The right-hand fields are optional. Tick "I don't know" and they're skipped — Detect runs
// alone, same as before. Fill them in and the app still only runs Detect today: Trace needs a
// live HYCOM/ERA5 fetch for that place and time, Attribute needs AIS coverage there, and
// neither is wired up for an arbitrary upload yet. We say that plainly rather than pretend to
// run stages we didn't (Master §1.5) — the coordinates/time are captured and shown back so
// nothing the judge typed is silently dropped.

import { useEffect, useRef, useState } from "react";
import type { DetectionCollection, DetectionProperties, Provenance } from "@/lib/contracts";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000";

const TRACE_ATTRIBUTE_REASON_UNKNOWN =
  "Trace and Attribute need two things this image doesn't carry: a published ocean-current " +
  "field for its date, and AIS coverage for its position. The nine cases in the gallery have both.";

const TRACE_ATTRIBUTE_REASON_KNOWN =
  "Coordinates and time are noted below. Trace and Attribute for uploaded scenes aren't wired " +
  "up yet — running them for an arbitrary point needs a live current/wind fetch for that place " +
  "and date, plus AIS coverage there. Only Detect runs on this scene for now.";

type UploadState =
  | { status: "idle" }
  | { status: "running" }
  | { status: "error"; message: string }
  | {
      status: "done";
      detections: DetectionCollection;
      bounds: Record<string, number>;
      provenance: Provenance;
    };

function dbBand(contrast_db: number): string {
  if (contrast_db <= -4.5) return "Clear (≤ −4.5 dB)";
  if (contrast_db <= -3.0) return "Marginal (−4.5 to −3.0 dB)";
  return "Below the oil threshold";
}

function ResultRow({ p, provenance }: { p: DetectionProperties; provenance: Provenance }) {
  const isOil = p.classification === "oil";
  return (
    <div className="flex items-center justify-between gap-4 border-b border-line py-2.5 text-[13px]">
      <div>
        <span className={isOil ? "font-semibold text-[var(--oil)]" : "text-ink-3"}>
          {isOil ? "Oil" : "Look-alike"}
        </span>
        <span className="ml-2 text-ink-3">
          {p.area_km2.toFixed(2)} km² · elongation {p.elongation.toFixed(1)}
        </span>
      </div>
      {provenance === "benchmark" ? (
        <div className="flex items-center gap-2">
          <div className="h-1.5 w-20 overflow-hidden rounded-full bg-raised">
            <div
              className="h-full bg-[var(--oil)]"
              style={{ width: `${Math.round(p.confidence * 100)}%` }}
            />
          </div>
          <span className="w-10 text-right font-mono text-[11px] text-ink-3">
            {Math.round(p.confidence * 100)}%
          </span>
        </div>
      ) : (
        <span className="text-[11px] text-ink-3">{dbBand(p.contrast_db)}</span>
      )}
    </div>
  );
}

const EMPTY: UploadState = { status: "idle" };

export default function UploadModal({
  open,
  onClose,
}: {
  open: boolean;
  onClose: () => void;
}) {
  const [file, setFile] = useState<File | null>(null);
  const [provenance, setProvenance] = useState<Provenance>("benchmark");
  const [unknownLocation, setUnknownLocation] = useState(true);
  const [lon, setLon] = useState("");
  const [lat, setLat] = useState("");
  const [whenLocal, setWhenLocal] = useState("");
  const [state, setState] = useState<UploadState>(EMPTY);
  const dialogRef = useRef<HTMLDivElement>(null);

  // Reset to a blank form each time the modal is reopened, rather than leaving a stale
  // in-flight state from the last upload behind.
  useEffect(() => {
    if (!open) return;
    setFile(null);
    setProvenance("benchmark");
    setUnknownLocation(true);
    setLon("");
    setLat("");
    setWhenLocal("");
    setState(EMPTY);
  }, [open]);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  if (!open) return null;

  const lonNum = Number(lon);
  const latNum = Number(lat);
  const coordsValid =
    lon.trim() !== "" &&
    lat.trim() !== "" &&
    Number.isFinite(lonNum) &&
    lonNum >= -180 &&
    lonNum <= 180 &&
    Number.isFinite(latNum) &&
    latNum >= -90 &&
    latNum <= 90;
  const whenValid = whenLocal.trim() !== "";
  const locationKnown = !unknownLocation && coordsValid && whenValid;
  const canRun =
    !!file && state.status !== "running" && (unknownLocation || (coordsValid && whenValid));

  // The datetime-local input has no timezone of its own; we treat whatever the judge typed as
  // UTC directly (Frozen Convention 2) rather than reinterpreting it through the browser's
  // local zone, which is what `new Date(value).toISOString()` would silently do.
  const whenIso = whenValid ? `${whenLocal}:00Z` : null;

  async function runDetect() {
    if (!file) return;
    setState({ status: "running" });
    try {
      const body = new FormData();
      body.set("file", file);
      body.set("provenance", provenance);
      const res = await fetch(`${API_BASE}/api/detect/upload`, { method: "POST", body });
      if (!res.ok) {
        const text = await res.text();
        throw new Error(text || `HTTP ${res.status}`);
      }
      const data = (await res.json()) as {
        detections: DetectionCollection;
        bounds: Record<string, number>;
      };
      setState({ status: "done", detections: data.detections, bounds: data.bounds, provenance });
    } catch (e) {
      setState({ status: "error", message: e instanceof Error ? e.message : String(e) });
    }
  }

  const oilCount =
    state.status === "done"
      ? state.detections.features.filter((f) => f.properties.classification === "oil").length
      : 0;

  return (
    <div
      className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-abyss/80 px-4 py-8 backdrop-blur-sm sm:items-center"
      onMouseDown={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby="upload-modal-title"
        className="anim-rise w-full max-w-[880px] rounded-xl border border-line-strong bg-overlay shadow-[0_24px_70px_rgba(0,0,0,0.65)]"
      >
        <div className="flex items-start justify-between gap-4 border-b border-line px-6 py-5">
          <div>
            <h2 id="upload-modal-title" className="t-title text-ink">
              Upload custom case
            </h2>
            <p className="mt-1 t-small text-ink-2">
              A SAR GeoTIFF you provide, run through the real Detect stage.
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close"
            className="shrink-0 rounded-full border border-line px-2.5 py-1 text-[13px] text-ink-3 transition-colors hover:border-line-strong hover:text-ink"
          >
            Close
          </button>
        </div>

        <div className="grid gap-6 px-6 py-6 sm:grid-cols-2">
          {/* Left — the image */}
          <div>
            <div className="t-label text-ink-3">Scene</div>
            <label
              htmlFor="upload-modal-file"
              className="mt-2 flex min-h-[180px] cursor-pointer flex-col items-center justify-center rounded-lg border border-dashed border-line bg-raised/40 px-4 py-6 text-center transition-colors hover:border-drift"
            >
              <span
                aria-hidden
                className="flex h-10 w-10 items-center justify-center rounded-full border border-line-strong text-[18px] text-ink-2"
              >
                ↑
              </span>
              <span className="mt-3 t-small text-ink">
                {file ? file.name : "Choose a GeoTIFF"}
              </span>
              <span className="mt-1 text-[11px] text-ink-3">
                2-band VV/VH, max 200 MB · .tif / .tiff
              </span>
              <input
                id="upload-modal-file"
                type="file"
                accept=".tif,.tiff"
                onChange={(e) => setFile(e.target.files?.[0] ?? null)}
                className="sr-only"
              />
            </label>

            <div className="mt-5">
              <div className="t-label text-ink-3">Where did this scene come from?</div>
              <div className="mt-2 space-y-2">
                <label className="flex items-start gap-2 text-[13px] text-ink-2">
                  <input
                    type="radio"
                    name="upload-modal-provenance"
                    checked={provenance === "benchmark"}
                    onChange={() => setProvenance("benchmark")}
                    className="mt-1"
                  />
                  <span>
                    <span className="font-medium text-ink">Zenodo benchmark tile</span> — scored
                    by the CNN scene classifier → U-Net, confidence is a calibrated model
                    probability
                  </span>
                </label>
                <label className="flex items-start gap-2 text-[13px] text-ink-2">
                  <input
                    type="radio"
                    name="upload-modal-provenance"
                    checked={provenance === "satellite"}
                    onChange={() => setProvenance("satellite")}
                    className="mt-1"
                  />
                  <span>
                    <span className="font-medium text-ink">Sentinel-1 GRD export</span> — scored
                    by classical CV + the documented dB/elongation rule, confidence is a rule
                    margin, not a probability
                  </span>
                </label>
              </div>
            </div>
          </div>

          {/* Right — coordinates and time */}
          <div>
            <div className="t-label text-ink-3">Origin coordinates &amp; time</div>

            <label className="mt-3 flex items-start gap-2 text-[13px] text-ink-2">
              <input
                type="checkbox"
                checked={unknownLocation}
                onChange={(e) => setUnknownLocation(e.target.checked)}
                className="mt-1"
              />
              <span>I don&apos;t know the coordinates or the acquisition time.</span>
            </label>

            {unknownLocation ? (
              <p className="mt-4 t-small text-ink-3">
                Detect only. Trace and Attribute stay off this run — they need a place and a time
                to work from.
              </p>
            ) : (
              <div className="mt-4 space-y-4">
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label htmlFor="upload-modal-lon" className="t-label text-ink-3">
                      Longitude
                    </label>
                    <input
                      id="upload-modal-lon"
                      type="number"
                      step="any"
                      min={-180}
                      max={180}
                      placeholder="e.g. 72.81"
                      value={lon}
                      onChange={(e) => setLon(e.target.value)}
                      className="mt-1 w-full rounded border border-line bg-hull px-2.5 py-1.5 text-[13px] text-ink outline-none focus:border-drift"
                    />
                  </div>
                  <div>
                    <label htmlFor="upload-modal-lat" className="t-label text-ink-3">
                      Latitude
                    </label>
                    <input
                      id="upload-modal-lat"
                      type="number"
                      step="any"
                      min={-90}
                      max={90}
                      placeholder="e.g. 18.94"
                      value={lat}
                      onChange={(e) => setLat(e.target.value)}
                      className="mt-1 w-full rounded border border-line bg-hull px-2.5 py-1.5 text-[13px] text-ink outline-none focus:border-drift"
                    />
                  </div>
                </div>
                {(lon.trim() !== "" || lat.trim() !== "") && !coordsValid && (
                  <p className="text-[11px] text-alert">
                    Longitude must be −180–180 and latitude −90–90.
                  </p>
                )}

                <div>
                  <label htmlFor="upload-modal-when" className="t-label text-ink-3">
                    Acquisition date &amp; time (UTC)
                  </label>
                  <input
                    id="upload-modal-when"
                    type="datetime-local"
                    value={whenLocal}
                    onChange={(e) => setWhenLocal(e.target.value)}
                    className="mt-1 w-full rounded border border-line bg-hull px-2.5 py-1.5 text-[13px] text-ink outline-none focus:border-drift"
                  />
                  <p className="mt-1 text-[11px] text-ink-3">
                    Enter the UTC time directly — not your local timezone.
                  </p>
                </div>
              </div>
            )}

            <button
              onClick={runDetect}
              disabled={!canRun}
              className="mt-6 w-full rounded-full bg-drift px-4 py-2.5 text-[14px] font-semibold text-abyss transition-transform duration-200 ease-out enabled:hover:scale-[1.015] disabled:cursor-not-allowed disabled:opacity-40"
            >
              {state.status === "running"
                ? "Running detector…"
                : locationKnown
                  ? "Run Detect (full pipeline not yet available)"
                  : "Run Detect"}
            </button>
          </div>
        </div>

        {(state.status === "error" || state.status === "done") && (
          <div className="border-t border-line px-6 py-6">
            {state.status === "error" && (
              <div className="rounded border border-alert/30 bg-alert/[0.07] p-4 text-[13px] text-ink-2">
                <div className="font-semibold text-alert">Detection failed</div>
                <p className="mt-1 whitespace-pre-wrap font-mono text-[12px]">{state.message}</p>
              </div>
            )}

            {state.status === "done" && (
              <div>
                <div className="text-[12px] font-mono uppercase tracking-wide text-ink-3">
                  Path:{" "}
                  {provenance === "benchmark"
                    ? "CNN scene classifier → U-Net"
                    : "Classical CV + RandomForest rule"}
                </div>
                <p className="mt-2 text-[14px] font-semibold text-ink">
                  {state.detections.features.length === 0
                    ? "No oil in this scene."
                    : `${state.detections.features.length} dark patch${
                        state.detections.features.length === 1 ? "" : "es"
                      }, ${oilCount} oil.`}
                </p>

                {state.detections.features.length > 0 && (
                  <div className="mt-3">
                    {state.detections.features.map((f) => (
                      <ResultRow key={f.properties.id} p={f.properties} provenance={provenance} />
                    ))}
                  </div>
                )}

                {locationKnown && whenIso && (
                  <p className="mt-4 font-mono text-[12px] text-ink-3">
                    Noted origin: [{lonNum.toFixed(5)}, {latNum.toFixed(5)}] · {whenIso}
                  </p>
                )}

                <div className="mt-6 flex gap-3">
                  <button
                    disabled
                    title={
                      locationKnown ? TRACE_ATTRIBUTE_REASON_KNOWN : TRACE_ATTRIBUTE_REASON_UNKNOWN
                    }
                    className="cursor-not-allowed rounded border border-line px-3 py-1.5 text-[12px] text-ink-3 opacity-50"
                  >
                    Trace
                  </button>
                  <button
                    disabled
                    title={
                      locationKnown ? TRACE_ATTRIBUTE_REASON_KNOWN : TRACE_ATTRIBUTE_REASON_UNKNOWN
                    }
                    className="cursor-not-allowed rounded border border-line px-3 py-1.5 text-[12px] text-ink-3 opacity-50"
                  >
                    Attribute
                  </button>
                </div>
                <p className="mt-2 max-w-[60ch] text-[12px] leading-relaxed text-ink-3">
                  {locationKnown ? TRACE_ATTRIBUTE_REASON_KNOWN : TRACE_ATTRIBUTE_REASON_UNKNOWN}
                </p>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
